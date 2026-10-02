"""User-selected research instruments, isolated from the operations universe."""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ApprovedInstrument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    market: Literal["KR", "US"]
    exchange: Literal["KRX", "NAS", "NYS", "AMS"]
    symbol: str

    @model_validator(mode="after")
    def normalize(self) -> ApprovedInstrument:
        self.symbol = self.symbol.strip().upper()
        if self.market == "KR":
            if self.exchange != "KRX" or not re.fullmatch(r"[0-9A-Z]{6}", self.symbol):
                raise ValueError("KR requires KRX and a six-character code")
        elif self.exchange == "KRX" or not re.fullmatch(
            r"[A-Z][A-Z0-9.\-]{0,14}", self.symbol
        ):
            raise ValueError("US requires NAS, NYS or AMS and a ticker")
        return self


class ApprovedUniverseUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision: int = Field(ge=0)
    instruments: list[ApprovedInstrument] = Field(max_length=100)

    @model_validator(mode="after")
    def unique(self) -> ApprovedUniverseUpdate:
        keys = {(item.market, item.exchange, item.symbol) for item in self.instruments}
        if len(keys) != len(self.instruments):
            raise ValueError("duplicate instrument")
        return self


class ApprovedUniverseSnapshot(BaseModel):
    revision: int
    updated_at: datetime | None
    instruments: list[ApprovedInstrument]


class StaleApprovedUniverseError(ValueError):
    """An update was based on a previous revision."""


class ApprovedUniverseStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS approved_universe (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    revision INTEGER NOT NULL,
                    updated_at TEXT NOT NULL,
                    instruments_json TEXT NOT NULL
                )"""
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _snapshot(row: sqlite3.Row | None) -> ApprovedUniverseSnapshot:
        if row is None:
            return ApprovedUniverseSnapshot(revision=0, updated_at=None, instruments=[])
        return ApprovedUniverseSnapshot(
            revision=int(row["revision"]),
            updated_at=datetime.fromisoformat(str(row["updated_at"])),
            instruments=[
                ApprovedInstrument.model_validate(item)
                for item in json.loads(str(row["instruments_json"]))
            ],
        )

    def read(self) -> ApprovedUniverseSnapshot:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM approved_universe WHERE id = 1"
            ).fetchone()
        return self._snapshot(row)

    def replace(self, update: ApprovedUniverseUpdate) -> ApprovedUniverseSnapshot:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM approved_universe WHERE id = 1"
            ).fetchone()
            previous = self._snapshot(row)
            if previous.revision != update.revision:
                raise StaleApprovedUniverseError("approved universe revision changed")
            revision = previous.revision + 1
            updated_at = datetime.now(UTC).isoformat()
            instruments_json = json.dumps(
                [item.model_dump() for item in update.instruments],
                separators=(",", ":"),
            )
            connection.execute(
                """INSERT INTO approved_universe
                   (id, revision, updated_at, instruments_json)
                   VALUES (1, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET revision=excluded.revision,
                   updated_at=excluded.updated_at,
                   instruments_json=excluded.instruments_json""",
                (revision, updated_at, instruments_json),
            )
        return ApprovedUniverseSnapshot(
            revision=revision,
            updated_at=datetime.fromisoformat(updated_at),
            instruments=update.instruments,
        )
