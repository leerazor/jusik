from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jusik.research_universe_data import CollectedUniverseSnapshot
from jusik.research_universe_models import (
    OfflineResearchRequest,
    OfflineResearchSnapshot,
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


class UniverseInputStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS universe_snapshots (
                    id TEXT PRIMARY KEY,
                    instrument_id TEXT NOT NULL,
                    requested_start TEXT NOT NULL,
                    requested_end TEXT NOT NULL,
                    actual_start TEXT NOT NULL,
                    actual_end TEXT NOT NULL,
                    evaluation_start TEXT NOT NULL,
                    warmup_bars INTEGER NOT NULL,
                    evaluation_bars INTEGER NOT NULL,
                    raw_json TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    normalized_json TEXT NOT NULL,
                    captured_at TEXT NOT NULL,
                    UNIQUE(instrument_id, id)
                );
                CREATE TABLE IF NOT EXISTS universe_collection_state (
                    instrument_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    snapshot_id TEXT,
                    error TEXT,
                    updated_at TEXT NOT NULL,
                    last_success_at TEXT,
                    FOREIGN KEY (snapshot_id) REFERENCES universe_snapshots(id)
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def save_success(self, collected: CollectedUniverseSnapshot) -> bool:
        item = collected.snapshot.instruments[0]
        dates = [bar.date for bar in item.bars]
        warmup = sum(day < collected.request.start_date for day in dates)
        evaluation = sum(
            collected.request.start_date <= day <= collected.request.end_date
            for day in dates
        )
        captured_at = collected.snapshot.captured_at.isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO universe_snapshots (
                    id, instrument_id, requested_start, requested_end,
                    actual_start, actual_end, evaluation_start, warmup_bars,
                    evaluation_bars, raw_json, request_json, normalized_json,
                    captured_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    collected.content_hash,
                    item.symbol,
                    collected.snapshot.requested_start.isoformat(),
                    collected.snapshot.requested_end.isoformat(),
                    dates[0].isoformat(),
                    dates[-1].isoformat(),
                    collected.snapshot.evaluation_start.isoformat(),
                    warmup,
                    evaluation,
                    json.dumps(
                        collected.raw_payload,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    collected.request.model_dump_json(),
                    collected.snapshot.model_dump_json(),
                    captured_at,
                ),
            )
            connection.execute(
                """
                INSERT INTO universe_collection_state (
                    instrument_id, status, snapshot_id, error, updated_at,
                    last_success_at
                ) VALUES (?, 'success', ?, NULL, ?, ?)
                ON CONFLICT(instrument_id) DO UPDATE SET
                    status='success', snapshot_id=excluded.snapshot_id,
                    error=NULL, updated_at=excluded.updated_at,
                    last_success_at=excluded.last_success_at
                """,
                (item.symbol, collected.content_hash, captured_at, captured_at),
            )
        return cursor.rowcount == 1

    def record_failure(self, instrument_id: str, message: str) -> None:
        now = _now()
        with self._connect() as connection:
            previous = connection.execute(
                """
                SELECT snapshot_id, last_success_at FROM universe_collection_state
                WHERE instrument_id=?
                """,
                (instrument_id,),
            ).fetchone()
            status = (
                "stale" if previous is not None and previous["snapshot_id"] else "error"
            )
            connection.execute(
                """
                INSERT INTO universe_collection_state (
                    instrument_id, status, snapshot_id, error, updated_at,
                    last_success_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(instrument_id) DO UPDATE SET
                    status=excluded.status, error=excluded.error,
                    updated_at=excluded.updated_at
                """,
                (
                    instrument_id,
                    status,
                    previous["snapshot_id"] if previous else None,
                    message,
                    now,
                    previous["last_success_at"] if previous else None,
                ),
            )

    def load_latest(
        self, instrument_id: str
    ) -> tuple[str, OfflineResearchRequest, OfflineResearchSnapshot] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT s.id, s.request_json, s.normalized_json
                FROM universe_collection_state c
                JOIN universe_snapshots s ON s.id=c.snapshot_id
                WHERE c.instrument_id=?
                """,
                (instrument_id,),
            ).fetchone()
        if row is None:
            return None
        return (
            str(row["id"]),
            OfflineResearchRequest.model_validate_json(row["request_json"]),
            OfflineResearchSnapshot.model_validate_json(row["normalized_json"]),
        )

    def load_asof(
        self, instrument_id: str, cutoff_at: datetime
    ) -> tuple[str, OfflineResearchRequest, OfflineResearchSnapshot] | None:
        """Load only a snapshot captured no later than the decision cutoff."""
        if cutoff_at.tzinfo is None:
            raise ValueError("cutoff_at must include a timezone.")
        with self._connect() as connection:
            row = connection.execute(
                """SELECT id, request_json, normalized_json
                FROM universe_snapshots
                WHERE instrument_id=? AND captured_at<=?
                ORDER BY captured_at DESC, id DESC LIMIT 1""",
                (instrument_id, cutoff_at.astimezone(UTC).isoformat()),
            ).fetchone()
        if row is None:
            return None
        return (
            str(row["id"]),
            OfflineResearchRequest.model_validate_json(row["request_json"]),
            OfflineResearchSnapshot.model_validate_json(row["normalized_json"]),
        )

    def statuses(self) -> dict[str, dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT c.*, s.requested_start, s.requested_end, s.actual_start,
                    s.actual_end, s.evaluation_start, s.warmup_bars,
                    s.evaluation_bars
                FROM universe_collection_state c
                LEFT JOIN universe_snapshots s ON s.id=c.snapshot_id
                ORDER BY c.instrument_id
                """
            ).fetchall()
        return {str(row["instrument_id"]): dict(row) for row in rows}


class UniverseResultStore:
    """Additive universe mapping stored beside existing optimizer results."""

    def __init__(self, optimizer_path: Path) -> None:
        self.path = optimizer_path
        optimizer_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS universe_optimizer_state (
                    instrument_id TEXT PRIMARY KEY,
                    snapshot_id TEXT NOT NULL,
                    batch_id TEXT,
                    status TEXT NOT NULL,
                    error TEXT,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def update(
        self,
        instrument_id: str,
        snapshot_id: str,
        *,
        batch_id: str | None,
        status: str,
        error: str | None = None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO universe_optimizer_state (
                    instrument_id, snapshot_id, batch_id, status, error,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(instrument_id) DO UPDATE SET
                    snapshot_id=excluded.snapshot_id,
                    batch_id=excluded.batch_id, status=excluded.status,
                    error=excluded.error, updated_at=excluded.updated_at
                """,
                (instrument_id, snapshot_id, batch_id, status, error, _now()),
            )

    def statuses(self) -> dict[str, dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM universe_optimizer_state ORDER BY instrument_id"
            ).fetchall()
        return {str(row["instrument_id"]): dict(row) for row in rows}

    def batch_details(self, batch_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            batch = connection.execute(
                "SELECT * FROM optimizer_batches WHERE id=?", (batch_id,)
            ).fetchone()
            if batch is None:
                return None
            folds = connection.execute(
                """
                SELECT f.*, r.device, r.winner_id, r.baseline_final_json,
                    r.winner_final_json,
                    (SELECT COUNT(*) FROM optimizer_candidates c
                     WHERE c.optimizer_run_id=f.optimizer_run_id) AS candidate_count
                FROM optimizer_batch_folds f
                LEFT JOIN optimizer_runs r ON r.id=f.optimizer_run_id
                WHERE f.batch_id=? ORDER BY f.fold_index
                """,
                (batch_id,),
            ).fetchall()
        result = dict(batch)
        result["summary"] = (
            json.loads(result.pop("summary_json"))
            if result.get("summary_json")
            else None
        )
        result["tail"] = json.loads(result.pop("tail_json"))
        result["risk"] = json.loads(result.pop("risk_json"))
        result["folds"] = [dict(row) for row in folds]
        return result
