from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError

from jusik.market_history_models import (
    STAGED_FEE_RATE,
    STAGED_INITIAL_CASH_KRW,
    STAGED_SELL_TAX_RATE,
    STAGED_SLIPPAGE_RATE,
    CandidateEvidence,
    MarketHistorySnapshot,
    MarketReadiness,
    MarketResearchRequest,
    MarketResearchResult,
    MarketResearchRun,
    ResearchEquityPoint,
    ResearchTrade,
)


def _persisted_request(payload: object) -> MarketResearchRequest:
    """Read old staged rows without making them eligible for promotion."""
    try:
        return MarketResearchRequest.model_validate(payload)
    except ValidationError as original_error:
        if not isinstance(payload, dict) or payload.get("stage") not in {
            "pilot",
            "final",
        }:
            raise
        try:
            values = dict(payload)
            values["market"] = str(values["market"])
            values["start_date"] = date.fromisoformat(str(values["start_date"]))
            values["end_date"] = date.fromisoformat(str(values["end_date"]))
            values["initial_cash_krw"] = Decimal(str(values["initial_cash_krw"]))
            values["fee_rate"] = Decimal(str(values["fee_rate"]))
            values["slippage_rate"] = Decimal(str(values["slippage_rate"]))
            values["sell_tax_rate"] = Decimal(str(values["sell_tax_rate"]))
            if values["market"] not in {"KR", "US"}:
                raise ValueError("invalid persisted market")
            if values["end_date"] < values["start_date"]:
                raise ValueError("invalid persisted period")
            if values["stage"] == "pilot" and values.get("pilot_run_id") is not None:
                raise ValueError("invalid persisted pilot reference")
            if values["stage"] == "final" and not values.get("pilot_run_id"):
                raise ValueError("invalid persisted final reference")
            if not (
                values["initial_cash_krw"] > 0
                and Decimal(0) <= values["fee_rate"] <= Decimal("0.1")
                and Decimal(0) <= values["slippage_rate"] <= Decimal("0.1")
                and Decimal(0) <= values["sell_tax_rate"] <= Decimal("0.1")
            ):
                raise ValueError("invalid persisted execution assumptions")
            if all(
                values[name] == expected
                for name, expected in {
                    "initial_cash_krw": STAGED_INITIAL_CASH_KRW,
                    "fee_rate": STAGED_FEE_RATE,
                    "slippage_rate": STAGED_SLIPPAGE_RATE,
                    "sell_tax_rate": STAGED_SELL_TAX_RATE,
                }.items()
            ):
                raise original_error
            return MarketResearchRequest.model_construct(**values)
        except (KeyError, TypeError, ValueError):
            raise original_error


def _persisted_result(payload: object) -> MarketResearchResult:
    if not isinstance(payload, dict):
        return MarketResearchResult.model_validate(payload)
    try:
        return MarketResearchResult.model_validate(payload)
    except ValidationError:
        values = dict(payload)
        values["request"] = _persisted_request(values["request"])
        values["readiness"] = MarketReadiness.model_validate(values["readiness"])
        values["candidate_evidence"] = tuple(
            CandidateEvidence.model_validate(item)
            for item in values.get("candidate_evidence", ())
        )
        values["trades"] = tuple(
            ResearchTrade.model_validate(item) for item in values.get("trades", ())
        )
        values["equity"] = tuple(
            ResearchEquityPoint.model_validate(item)
            for item in values.get("equity", ())
        )
        values["metrics"] = {
            str(key): Decimal(str(value))
            for key, value in values.get("metrics", {}).items()
        }
        return MarketResearchResult.model_construct(**values)


def _uses_historical_assumptions(request: MarketResearchRequest) -> bool:
    return request.stage in {"pilot", "final"} and any(
        value != expected
        for value, expected in (
            (request.initial_cash_krw, STAGED_INITIAL_CASH_KRW),
            (request.fee_rate, STAGED_FEE_RATE),
            (request.slippage_rate, STAGED_SLIPPAGE_RATE),
            (request.sell_tax_rate, STAGED_SELL_TAX_RATE),
        )
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
        request_payload = json.loads(row["request_json"])
        request = _persisted_request(request_payload)
        result = (
            _persisted_result(json.loads(row["result_json"]))
            if row["result_json"]
            else None
        )
        run_values = {
            "id": row["id"],
            "status": row["status"],
            "request": request,
            "result": result,
            "input_hash": row["input_hash"],
            "created_at": datetime.fromisoformat(row["created_at"]),
            "updated_at": datetime.fromisoformat(row["updated_at"]),
            "error": row["error"],
            "stage": row["stage"] or "legacy",
            "pilot_run_id": row["pilot_run_id"],
            "data_contract_hash": row["data_contract_hash"],
        }
        if _uses_historical_assumptions(request):
            return MarketResearchRun.model_construct(**run_values)
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
