from __future__ import annotations

import builtins
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Literal, cast
from uuid import uuid4

from jusik.research_models import (
    BacktestResult,
    ResearchInputSnapshot,
    ResearchRun,
    ResearchRunRequest,
    ResearchRunSummary,
    RunStatus,
    SymbolMetadata,
    utc_now,
)


class ResearchStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS research_runs (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    input_json TEXT,
                    result_json TEXT,
                    input_hash TEXT,
                    error TEXT,
                    replay_of TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS symbol_metadata (
                    symbol TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def upsert_symbol_metadata(self, symbol: str, name: str) -> SymbolMetadata:
        metadata = SymbolMetadata(symbol=symbol, name=name, updated_at=utc_now())
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO symbol_metadata (symbol, name, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    name=excluded.name, updated_at=excluded.updated_at
                """,
                (metadata.symbol, metadata.name, metadata.updated_at.isoformat()),
            )
        return metadata

    def list_symbol_metadata(self) -> builtins.list[SymbolMetadata]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT symbol, name, updated_at FROM symbol_metadata ORDER BY symbol"
            ).fetchall()
        return [
            SymbolMetadata(
                symbol=row["symbol"],
                name=row["name"],
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )
            for row in rows
        ]

    def create(
        self,
        request: ResearchRunRequest,
        *,
        replay_of: str | None = None,
        snapshot: ResearchInputSnapshot | None = None,
        run_id: str | None = None,
        if_exists: bool = False,
    ) -> ResearchRun:
        selected_id = run_id or uuid4().hex
        now = utc_now()
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO research_runs (
                        id, status, request_json, input_json, result_json, input_hash,
                        error, replay_of, created_at, updated_at
                    ) VALUES (?, 'queued', ?, ?, NULL, NULL, NULL, ?, ?, ?)
                    """,
                    (
                        selected_id,
                        request.model_dump_json(),
                        snapshot.model_dump_json() if snapshot else None,
                        replay_of,
                        now.isoformat(),
                        now.isoformat(),
                    ),
                )
        except sqlite3.IntegrityError:
            if not if_exists:
                raise
            existing = self.get(selected_id)
            if existing.request != request or existing.replay_of != replay_of:
                raise ValueError(
                    "Scheduled run identity has conflicting inputs."
                ) from None
            return existing
        return self.get(selected_id)

    def update_status(self, run_id: str, status: RunStatus) -> None:
        self._update(run_id, status=status)

    def save_snapshot(
        self, run_id: str, snapshot: ResearchInputSnapshot, input_hash: str
    ) -> None:
        existing = self.get(run_id).input_snapshot
        if existing is not None and existing != snapshot:
            raise ValueError("An immutable research input snapshot cannot be replaced.")
        self._update(
            run_id,
            status="running",
            input_json=snapshot.model_dump_json(),
            input_hash=input_hash,
        )

    def complete(self, run_id: str, result: BacktestResult) -> None:
        self._update(
            run_id,
            status="completed",
            result_json=result.model_dump_json(),
            input_hash=result.input_hash,
            error=None,
        )

    def fail(
        self, run_id: str, status: Literal["insufficient", "failed"], message: str
    ) -> None:
        self._update(run_id, status=status, error=message)

    def _update(self, run_id: str, **fields: object) -> None:
        allowed = {"status", "input_json", "result_json", "input_hash", "error"}
        if not fields or not fields.keys() <= allowed:
            raise ValueError("Invalid research store update.")
        fields["updated_at"] = utc_now().isoformat()
        assignments = ", ".join(f"{key} = ?" for key in fields)
        with self._connect() as connection:
            cursor = connection.execute(
                f"UPDATE research_runs SET {assignments} WHERE id = ?",  # noqa: S608
                (*fields.values(), run_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(run_id)

    def get(self, run_id: str) -> ResearchRun:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM research_runs WHERE id = ?", (run_id,)
            ).fetchone()
        if row is None:
            raise KeyError(run_id)
        return self._parse(row)

    def list(self, limit: int = 50) -> list[ResearchRunSummary]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM research_runs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [
            ResearchRunSummary.model_validate(self._parse(row).model_dump())
            for row in rows
        ]

    def recover_interrupted(self) -> int:
        now = utc_now().isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE research_runs
                SET status = 'failed',
                    error = 'Research worker stopped before this run completed.',
                    updated_at = ?
                WHERE status IN ('collecting', 'running')
                """,
                (now,),
            )
            return cursor.rowcount

    def queued_ids(self, limit: int = 10) -> builtins.list[str]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id FROM research_runs WHERE status='queued'
                ORDER BY created_at LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [cast(str, row["id"]) for row in rows]

    @staticmethod
    def _parse(row: sqlite3.Row) -> ResearchRun:
        request = ResearchRunRequest.model_validate(json.loads(row["request_json"]))
        snapshot = (
            ResearchInputSnapshot.model_validate(json.loads(row["input_json"]))
            if row["input_json"]
            else None
        )
        result = (
            BacktestResult.model_validate(json.loads(row["result_json"]))
            if row["result_json"]
            else None
        )
        return ResearchRun(
            id=cast(str, row["id"]),
            status=cast(RunStatus, row["status"]),
            request=request,
            input_snapshot=snapshot,
            result=result,
            input_hash=cast(str | None, row["input_hash"]),
            error=cast(str | None, row["error"]),
            replay_of=cast(str | None, row["replay_of"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
