from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from jusik.market_history_models import (
    MarketHistorySnapshot,
    MarketResearchRequest,
    MarketResearchResult,
    MarketResearchRun,
)


class MarketHistoryStore:
    """SQLite ledger for immutable PIT snapshots and append-only run results."""

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
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS pit_snapshots (
                    input_hash TEXT PRIMARY KEY,
                    market TEXT NOT NULL,
                    requested_start TEXT NOT NULL,
                    requested_end TEXT NOT NULL,
                    body TEXT NOT NULL,
                    captured_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS pit_runs (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    result_json TEXT,
                    input_hash TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS pit_artifacts (
                    content_sha256 TEXT PRIMARY KEY,
                    content BLOB NOT NULL,
                    content_type TEXT NOT NULL,
                    captured_at TEXT NOT NULL
                )
                """
            )
            columns = {
                str(row["name"])
                for row in connection.execute("PRAGMA table_info(pit_runs)").fetchall()
            }
            for name, definition in {
                "stage": "TEXT NOT NULL DEFAULT 'legacy'",
                "pilot_run_id": "TEXT",
                "data_contract_hash": "TEXT",
            }.items():
                if name not in columns:
                    connection.execute(
                        f"ALTER TABLE pit_runs ADD COLUMN {name} {definition}"
                    )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_pit_runs_stage ON pit_runs(stage)"
            )

    def save_snapshot(self, snapshot: MarketHistorySnapshot) -> str:
        digest = snapshot.input_hash
        body = snapshot.model_dump_json()
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT body FROM pit_snapshots WHERE input_hash = ?", (digest,)
            ).fetchone()
            if existing is not None:
                if existing["body"] != body:
                    raise ValueError("snapshot hash collision or conflicting revision")
                return digest
            connection.execute(
                """
                INSERT INTO pit_snapshots
                    (
                        input_hash, market, requested_start, requested_end, body,
                        captured_at
                    )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    digest,
                    snapshot.market,
                    snapshot.requested_start.isoformat(),
                    snapshot.requested_end.isoformat(),
                    body,
                    snapshot.captured_at.isoformat(),
                ),
            )
        return digest

    def get_snapshot(self, input_hash: str) -> MarketHistorySnapshot:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT body FROM pit_snapshots WHERE input_hash = ?", (input_hash,)
            ).fetchone()
        if row is None:
            raise KeyError(input_hash)
        return MarketHistorySnapshot.model_validate(json.loads(row["body"]))

    def save_artifact(
        self, content: bytes, *, content_type: str, captured_at: datetime
    ) -> str:
        digest = hashlib.sha256(content).hexdigest()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO pit_artifacts
                    (content_sha256, content, content_type, captured_at)
                VALUES (?, ?, ?, ?)
                """,
                (digest, content, content_type, captured_at.isoformat()),
            )
        return digest

    def get_artifact(self, artifact_id: str) -> tuple[bytes, str]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT content, content_type FROM pit_artifacts "
                "WHERE content_sha256 = ?",
                (artifact_id,),
            ).fetchone()
        if row is None:
            raise KeyError(artifact_id)
        return bytes(row["content"]), str(row["content_type"])

    def create_run(
        self, request: MarketResearchRequest, *, run_id: str | None = None
    ) -> MarketResearchRun:
        selected = run_id or uuid4().hex
        now = datetime.now(UTC)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO pit_runs
                    (
                        id, status, request_json, result_json, input_hash, error,
                        created_at, updated_at, stage, pilot_run_id, data_contract_hash
                    )
                VALUES (?, 'queued', ?, NULL, NULL, NULL, ?, ?, ?, ?, NULL)
                """,
                (
                    selected,
                    request.model_dump_json(),
                    now.isoformat(),
                    now.isoformat(),
                    request.stage,
                    request.pilot_run_id,
                ),
            )
        return self.get_run(selected)

    def update_run(
        self,
        run_id: str,
        *,
        status: str,
        result: MarketResearchResult | None = None,
        input_hash: str | None = None,
        error: str | None = None,
        data_contract_hash: str | None = None,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        result_json = result.model_dump_json() if result else None
        effective_contract_hash = (
            data_contract_hash
            if data_contract_hash is not None
            else (result.data_contract_hash if result is not None else None)
        )
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT status, result_json, input_hash, error, data_contract_hash "
                "FROM pit_runs WHERE id = ?",
                (run_id,),
            ).fetchone()
            if existing is None:
                raise KeyError(run_id)
            if existing["status"] in {"completed", "insufficient", "failed"}:
                if (
                    existing["status"] != status
                    or existing["result_json"] != result_json
                    or existing["input_hash"] != input_hash
                    or existing["error"] != error
                    or existing["data_contract_hash"] != effective_contract_hash
                ):
                    raise ValueError("terminal research runs are immutable")
                return
            cursor = connection.execute(
                """
                UPDATE pit_runs
                SET status = ?, result_json = ?, input_hash = ?, error = ?,
                    updated_at = ?, data_contract_hash = ?
                WHERE id = ?
                """,
                (
                    status,
                    result_json,
                    input_hash,
                    error,
                    now,
                    effective_contract_hash,
                    run_id,
                ),
            )
            if cursor.rowcount != 1:
                raise KeyError(run_id)

    def get_run(self, run_id: str) -> MarketResearchRun:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM pit_runs WHERE id = ?", (run_id,)
            ).fetchone()
        if row is None:
            raise KeyError(run_id)
        request = MarketResearchRequest.model_validate(json.loads(row["request_json"]))
        result = (
            MarketResearchResult.model_validate(json.loads(row["result_json"]))
            if row["result_json"]
            else None
        )
        return MarketResearchRun(
            id=row["id"],
            status=row["status"],
            request=request,
            result=result,
            input_hash=row["input_hash"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            error=row["error"],
            stage=row["stage"] or "legacy",
            pilot_run_id=row["pilot_run_id"],
            data_contract_hash=row["data_contract_hash"],
        )

    def list_runs(self, limit: int = 50) -> list[MarketResearchRun]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id FROM pit_runs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self.get_run(row["id"]) for row in rows]
