import json
import sqlite3
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import cast
from uuid import uuid4
from zoneinfo import ZoneInfo

from jusik.operations_models import (
    DEFAULT_UNIVERSE,
    AiReservation,
    AiStatus,
    PaperAccount,
    PaperFill,
    ProposalDecision,
    Quote,
    ResearchSchedule,
    ResearchScheduleUpdate,
    SignalProposal,
    SignalProposalCreate,
    StrategyDefinition,
    StrategyVersionRecord,
    UniverseUpdate,
    next_schedule_time,
    utc_now,
)

INITIAL_PAPER_CASH = Decimal("100000000")
FEE_RATE = Decimal("0.00015")
SELL_TAX_RATE = Decimal("0.0018")
KST = ZoneInfo("Asia/Seoul")

BUILT_IN_STRATEGIES = (
    StrategyDefinition(
        version="trend_20_v1",
        name="20일 추세",
        fast_window=20,
        definition="수정 종가가 20일 이동평균보다 높을 때 보유합니다.",
    ),
    StrategyDefinition(
        version="trend_20_60_v1",
        name="20/60일 추세",
        fast_window=20,
        slow_window=60,
        definition=(
            "수정 종가가 20일 평균보다 높고 20일 평균이 "
            "60일 평균보다 높을 때 보유합니다."
        ),
    ),
    StrategyDefinition(
        version="trend_volume_20_60_v1",
        name="추세·거래량 확인",
        fast_window=20,
        slow_window=60,
        min_volume_ratio=Decimal("1.1"),
        definition=(
            "20/60일 상승 추세에서 거래량이 20일 평균의 1.1배 이상일 때 보유합니다."
        ),
    ),
)


class OperationsStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        now = utc_now()
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS operations_settings (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS strategy_versions (
                    version TEXT PRIMARY KEY,
                    definition_json TEXT NOT NULL,
                    source TEXT NOT NULL,
                    recommended INTEGER NOT NULL DEFAULT 0,
                    active_for_paper INTEGER NOT NULL DEFAULT 0,
                    reason TEXT NOT NULL,
                    last_run_id TEXT,
                    out_of_sample_return_pct TEXT,
                    out_of_sample_max_drawdown_pct TEXT,
                    passed INTEGER,
                    proposed_after_date TEXT,
                    provenance_json TEXT,
                    evaluation_start TEXT,
                    evaluation_end TEXT,
                    evaluation_run_id TEXT,
                    evaluation_input_hash TEXT,
                    evaluation_implementation_hash TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS signal_proposals (
                    id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    limit_price TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    strategy_version TEXT NOT NULL,
                    signal_date TEXT NOT NULL,
                    source_run_id TEXT NOT NULL DEFAULT 'legacy',
                    signal_input_hash TEXT NOT NULL DEFAULT 'legacy',
                    reason TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    decided_at TEXT,
                    decision_reason TEXT
                );
                CREATE UNIQUE INDEX IF NOT EXISTS one_pending_proposal
                    ON signal_proposals(symbol, side, strategy_version)
                    WHERE status = 'pending';
                CREATE TABLE IF NOT EXISTS proposal_signal_claims (
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    strategy_version TEXT NOT NULL,
                    signal_date TEXT NOT NULL,
                    proposal_id TEXT NOT NULL UNIQUE,
                    PRIMARY KEY (symbol, side, strategy_version, signal_date)
                );
                CREATE TABLE IF NOT EXISTS proposal_signal_claims_v2 (
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    strategy_version TEXT NOT NULL,
                    signal_date TEXT NOT NULL,
                    signal_input_hash TEXT NOT NULL,
                    proposal_id TEXT NOT NULL UNIQUE,
                    PRIMARY KEY (
                        symbol, side, strategy_version, signal_date,
                        signal_input_hash
                    )
                );
                CREATE TABLE IF NOT EXISTS paper_account (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    cash TEXT NOT NULL,
                    positions_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS paper_fills (
                    id TEXT PRIMARY KEY,
                    proposal_id TEXT NOT NULL UNIQUE,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    price TEXT NOT NULL,
                    notional TEXT NOT NULL,
                    fee TEXT NOT NULL,
                    tax TEXT NOT NULL,
                    filled_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS operation_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS ai_runs (
                    id TEXT PRIMARY KEY,
                    model TEXT,
                    prompt_version TEXT NOT NULL,
                    request_json TEXT,
                    status TEXT NOT NULL DEFAULT 'completed',
                    reserved_tokens INTEGER NOT NULL DEFAULT 0,
                    input_tokens INTEGER NOT NULL,
                    output_tokens INTEGER NOT NULL,
                    analysis TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL
                );
                """
            )
            connection.execute(
                """
                INSERT OR IGNORE INTO proposal_signal_claims (
                    symbol, side, strategy_version, signal_date, proposal_id
                )
                SELECT symbol, side, strategy_version, signal_date, id
                FROM signal_proposals ORDER BY created_at
                """
            )
            ai_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(ai_runs)").fetchall()
            }
            if "request_json" not in ai_columns:
                connection.execute("ALTER TABLE ai_runs ADD COLUMN request_json TEXT")
            if "status" not in ai_columns:
                connection.execute(
                    "ALTER TABLE ai_runs ADD COLUMN status TEXT NOT NULL "
                    "DEFAULT 'completed'"
                )
            if "reserved_tokens" not in ai_columns:
                connection.execute(
                    "ALTER TABLE ai_runs ADD COLUMN reserved_tokens INTEGER "
                    "NOT NULL DEFAULT 0"
                )
            strategy_columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(strategy_versions)"
                ).fetchall()
            }
            strategy_migrations = {
                "proposed_after_date": "TEXT",
                "provenance_json": "TEXT",
                "evaluation_start": "TEXT",
                "evaluation_end": "TEXT",
                "evaluation_run_id": "TEXT",
                "evaluation_input_hash": "TEXT",
                "evaluation_implementation_hash": "TEXT",
            }
            for column, data_type in strategy_migrations.items():
                if column not in strategy_columns:
                    connection.execute(
                        f"ALTER TABLE strategy_versions ADD COLUMN {column} {data_type}"
                    )
            proposal_columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(signal_proposals)"
                ).fetchall()
            }
            if "source_run_id" not in proposal_columns:
                connection.execute(
                    """
                    ALTER TABLE signal_proposals
                    ADD COLUMN source_run_id TEXT NOT NULL DEFAULT 'legacy'
                    """
                )
            if "signal_input_hash" not in proposal_columns:
                connection.execute(
                    """
                    ALTER TABLE signal_proposals
                    ADD COLUMN signal_input_hash TEXT NOT NULL DEFAULT 'legacy'
                    """
                )
            connection.execute(
                """
                INSERT OR IGNORE INTO proposal_signal_claims_v2 (
                    symbol, side, strategy_version, signal_date,
                    signal_input_hash, proposal_id
                )
                SELECT symbol, side, strategy_version, signal_date,
                       signal_input_hash, id
                FROM signal_proposals ORDER BY created_at
                """
            )
            connection.execute(
                "INSERT OR IGNORE INTO paper_account VALUES (1, ?, '{}', ?)",
                (str(INITIAL_PAPER_CASH), now.isoformat()),
            )
            self._insert_setting(
                connection, "universe", DEFAULT_UNIVERSE, now, if_missing=True
            )
            self._insert_setting(
                connection, "stream_enabled", False, now, if_missing=True
            )
            self._insert_setting(
                connection,
                "schedule",
                {
                    "enabled": False,
                    "interval_hours": 24,
                    "lookback_days": 730,
                    "next_run_at": next_schedule_time(24, now=now).isoformat(),
                    "last_started_at": None,
                    "last_run_id": None,
                    "last_error": None,
                },
                now,
                if_missing=True,
            )
            for definition in BUILT_IN_STRATEGIES:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO strategy_versions (
                        version, definition_json, source, reason, created_at
                    ) VALUES (?, ?, 'built_in', ?, ?)
                    """,
                    (
                        definition.version,
                        definition.model_dump_json(),
                        "아직 독립 검증 결과가 없습니다.",
                        now.isoformat(),
                    ),
                )

    @staticmethod
    def _insert_setting(
        connection: sqlite3.Connection,
        key: str,
        value: object,
        now: datetime,
        *,
        if_missing: bool = False,
    ) -> None:
        statement = (
            "INSERT OR IGNORE INTO operations_settings VALUES (?, ?, ?)"
            if if_missing
            else "INSERT INTO operations_settings VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json, "
            "updated_at=excluded.updated_at"
        )
        connection.execute(
            statement,
            (key, json.dumps(value, ensure_ascii=False), now.isoformat()),
        )

    def universe(self) -> list[str]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value_json FROM operations_settings WHERE key='universe'"
            ).fetchone()
        assert row is not None
        return UniverseUpdate(symbols=json.loads(row["value_json"])).symbols

    def update_universe(self, update: UniverseUpdate) -> list[str]:
        with self._connect() as connection:
            self._insert_setting(connection, "universe", update.symbols, utc_now())
        return self.universe()

    def stream_enabled(self) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value_json FROM operations_settings WHERE key='stream_enabled'"
            ).fetchone()
        assert row is not None
        return bool(json.loads(row["value_json"]))

    def update_stream_enabled(self, enabled: bool) -> bool:
        with self._connect() as connection:
            self._insert_setting(connection, "stream_enabled", enabled, utc_now())
        return enabled

    def schedule(self) -> ResearchSchedule:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value_json FROM operations_settings WHERE key='schedule'"
            ).fetchone()
        assert row is not None
        return ResearchSchedule.model_validate(json.loads(row["value_json"]))

    def update_schedule(self, update: ResearchScheduleUpdate) -> ResearchSchedule:
        current = self.schedule()
        schedule = ResearchSchedule(
            **update.model_dump(),
            next_run_at=next_schedule_time(update.interval_hours),
            last_started_at=current.last_started_at,
            last_run_id=current.last_run_id,
            last_error=None,
        )
        with self._connect() as connection:
            self._insert_setting(
                connection,
                "schedule",
                schedule.model_dump(mode="json"),
                utc_now(),
            )
        return schedule

    def schedule_due(self, now: datetime) -> bool:
        schedule = self.schedule()
        return schedule.enabled and schedule.next_run_at <= now

    def mark_schedule_started(self, run_id: str, now: datetime) -> None:
        current = self.schedule()
        updated = current.model_copy(
            update={
                "last_started_at": now,
                "last_run_id": run_id,
                "last_error": None,
                "next_run_at": next_schedule_time(current.interval_hours, now=now),
            }
        )
        with self._connect() as connection:
            self._insert_setting(
                connection,
                "schedule",
                updated.model_dump(mode="json"),
                now,
            )

    def mark_schedule_error(self, message: str, now: datetime) -> None:
        current = self.schedule()
        updated = current.model_copy(
            update={
                "last_error": message,
                "next_run_at": next_schedule_time(current.interval_hours, now=now),
            }
        )
        with self._connect() as connection:
            self._insert_setting(
                connection,
                "schedule",
                updated.model_dump(mode="json"),
                now,
            )

    def versions(self) -> list[StrategyVersionRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM strategy_versions ORDER BY created_at, version"
            ).fetchall()
        return [self._version(row) for row in rows]

    def reserve_ai_run(
        self,
        *,
        model: str | None,
        prompt_version: str,
        request: object,
        daily_budget: int,
        conservative_input_tokens: int,
        desired_output_tokens: int = 500,
    ) -> AiReservation | None:
        if daily_budget <= 0 or conservative_input_tokens <= 0:
            return None
        now = utc_now()
        today = now.date().isoformat()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT COALESCE(SUM(
                    CASE WHEN status IN ('reserved', 'failed')
                         THEN reserved_tokens
                         ELSE input_tokens + output_tokens END
                ), 0) AS tokens
                FROM ai_runs WHERE substr(created_at, 1, 10)=?
                """,
                (today,),
            ).fetchone()
            assert row is not None
            remaining = daily_budget - int(row["tokens"])
            max_output = min(
                desired_output_tokens, remaining - conservative_input_tokens
            )
            if max_output < 64:
                return None
            reservation = AiReservation(
                id=uuid4().hex,
                max_output_tokens=max_output,
                reserved_tokens=conservative_input_tokens + max_output,
            )
            connection.execute(
                """
                INSERT INTO ai_runs (
                    id, model, prompt_version, request_json, status,
                    reserved_tokens, input_tokens, output_tokens, analysis,
                    error, created_at
                ) VALUES (?, ?, ?, ?, 'reserved', ?, 0, 0, NULL, NULL, ?)
                """,
                (
                    reservation.id,
                    model,
                    prompt_version,
                    json.dumps(request, ensure_ascii=False, default=str),
                    reservation.reserved_tokens,
                    now.isoformat(),
                ),
            )
            return reservation

    def complete_ai_run(
        self,
        reservation_id: str,
        *,
        input_tokens: int,
        output_tokens: int,
        analysis: str | None,
        error: str | None,
    ) -> None:
        status = "failed" if error else "completed"
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE ai_runs
                SET status=?, input_tokens=?, output_tokens=?, analysis=?, error=?
                WHERE id=? AND status='reserved'
                """,
                (
                    status,
                    input_tokens,
                    output_tokens,
                    analysis,
                    error,
                    reservation_id,
                ),
            )
            if cursor.rowcount != 1:
                raise KeyError(reservation_id)

    def save_ai_suggestion(
        self,
        definition: StrategyDefinition,
        reason: str,
        *,
        proposed_after_date: date,
        provenance: dict[str, str],
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO strategy_versions (
                    version, definition_json, source, reason,
                    proposed_after_date, provenance_json, created_at
                ) VALUES (?, ?, 'openai_suggestion', ?, ?, ?, ?)
                """,
                (
                    definition.version,
                    definition.model_dump_json(),
                    reason,
                    proposed_after_date.isoformat(),
                    json.dumps(provenance, ensure_ascii=False, sort_keys=True),
                    utc_now().isoformat(),
                ),
            )

    def ai_status(
        self,
        *,
        enabled: bool,
        configured: bool,
        model: str | None,
        daily_token_budget: int,
        prompt_version: str,
    ) -> AiStatus:
        today = utc_now().date().isoformat()
        with self._connect() as connection:
            latest = connection.execute(
                "SELECT * FROM ai_runs ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            usage = connection.execute(
                """
                SELECT COALESCE(SUM(
                    CASE WHEN status IN ('reserved', 'failed')
                         THEN reserved_tokens
                         ELSE input_tokens + output_tokens END
                ), 0) AS tokens
                FROM ai_runs WHERE substr(created_at, 1, 10)=?
                """,
                (today,),
            ).fetchone()
        assert usage is not None
        return AiStatus(
            enabled=enabled,
            configured=configured,
            model=model,
            daily_token_budget=daily_token_budget,
            used_tokens_today=int(usage["tokens"]),
            last_run_at=datetime.fromisoformat(latest["created_at"])
            if latest is not None
            else None,
            last_error=latest["error"] if latest is not None else None,
            last_analysis=latest["analysis"] if latest is not None else None,
            prompt_version=prompt_version,
        )

    @staticmethod
    def _version(row: sqlite3.Row) -> StrategyVersionRecord:
        passed = row["passed"]
        return StrategyVersionRecord(
            definition=StrategyDefinition.model_validate_json(row["definition_json"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            source=cast(str, row["source"]),
            recommended=bool(row["recommended"]),
            active_for_paper=bool(row["active_for_paper"]),
            reason=cast(str, row["reason"]),
            last_run_id=cast(str | None, row["last_run_id"]),
            out_of_sample_return_pct=Decimal(row["out_of_sample_return_pct"])
            if row["out_of_sample_return_pct"] is not None
            else None,
            out_of_sample_max_drawdown_pct=Decimal(
                row["out_of_sample_max_drawdown_pct"]
            )
            if row["out_of_sample_max_drawdown_pct"] is not None
            else None,
            passed=bool(passed) if passed is not None else None,
            proposed_after_date=date.fromisoformat(row["proposed_after_date"])
            if row["proposed_after_date"]
            else None,
            provenance=json.loads(row["provenance_json"])
            if row["provenance_json"]
            else {},
            evaluation_start=date.fromisoformat(row["evaluation_start"])
            if row["evaluation_start"]
            else None,
            evaluation_end=date.fromisoformat(row["evaluation_end"])
            if row["evaluation_end"]
            else None,
            evaluation_run_id=row["evaluation_run_id"],
            evaluation_input_hash=row["evaluation_input_hash"],
            evaluation_implementation_hash=row["evaluation_implementation_hash"],
        )

    def activate_paper(self, version: str) -> StrategyVersionRecord:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            exists = connection.execute(
                """
                SELECT source, passed, proposed_after_date, evaluation_start,
                       evaluation_end, evaluation_run_id,
                       evaluation_input_hash, evaluation_implementation_hash
                FROM strategy_versions WHERE version=?
                """,
                (version,),
            ).fetchone()
            if exists is None:
                raise KeyError(version)
            if exists["source"] == "openai_suggestion":
                complete_evaluation = all(
                    exists[field] is not None
                    for field in (
                        "proposed_after_date",
                        "evaluation_start",
                        "evaluation_end",
                        "evaluation_run_id",
                        "evaluation_input_hash",
                        "evaluation_implementation_hash",
                    )
                )
                if exists["passed"] != 1 or not complete_evaluation:
                    raise ValueError(
                        "AI suggested strategies require a passing later-period "
                        "evaluation."
                    )
            connection.execute("UPDATE strategy_versions SET active_for_paper=0")
            connection.execute(
                "UPDATE strategy_versions SET active_for_paper=1 WHERE version=?",
                (version,),
            )
            connection.execute(
                """
                UPDATE signal_proposals
                SET status='expired', decided_at=?,
                    decision_reason='운영 paper 전략 버전 변경'
                WHERE status='pending' AND strategy_version<>?
                """,
                (utc_now().isoformat(), version),
            )
            self._audit(connection, "strategy_activated", version, {"mode": "paper"})
        return next(
            item for item in self.versions() if item.definition.version == version
        )

    def record_validation(
        self,
        *,
        run_id: str,
        recommended_version: str,
        candidate_return_pct: Decimal,
        candidate_drawdown_pct: Decimal,
        candidate_passed: bool,
        reason: str,
    ) -> None:
        with self._connect() as connection:
            connection.execute("UPDATE strategy_versions SET recommended=0")
            connection.execute(
                """
                UPDATE strategy_versions
                SET recommended=1, last_run_id=?, reason=?
                WHERE version=?
                """,
                (run_id, reason, recommended_version),
            )
            connection.execute(
                """
                UPDATE strategy_versions
                SET last_run_id=?, out_of_sample_return_pct=?,
                    out_of_sample_max_drawdown_pct=?, passed=?, reason=?
                WHERE version='trend_20_60_v1'
                """,
                (
                    run_id,
                    str(candidate_return_pct),
                    str(candidate_drawdown_pct),
                    int(candidate_passed),
                    reason,
                ),
            )

    def record_version_validation(
        self,
        *,
        run_id: str,
        version: str,
        return_pct: Decimal,
        drawdown_pct: Decimal,
        passed: bool,
        reason: str,
        evaluation_start: date,
        evaluation_end: date,
        input_hash: str,
        implementation_hash: str,
    ) -> None:
        if evaluation_end < evaluation_start:
            raise ValueError("Evaluation end must not precede its start.")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                """
                SELECT source, proposed_after_date, evaluation_run_id
                FROM strategy_versions WHERE version=?
                """,
                (version,),
            ).fetchone()
            if existing is None:
                raise KeyError(version)
            if existing["source"] == "openai_suggestion":
                if existing["proposed_after_date"] is None:
                    raise ValueError("AI suggestion has no immutable proposal cutoff.")
                cutoff = date.fromisoformat(existing["proposed_after_date"])
                if evaluation_start <= cutoff:
                    raise ValueError(
                        "AI evaluation must start after its immutable proposal cutoff."
                    )
                if existing["evaluation_run_id"] is not None:
                    raise ValueError("AI suggestion was already evaluated.")
            cursor = connection.execute(
                """
                UPDATE strategy_versions
                SET last_run_id=?, out_of_sample_return_pct=?,
                    out_of_sample_max_drawdown_pct=?, passed=?, reason=?,
                    evaluation_start=?, evaluation_end=?, evaluation_run_id=?,
                    evaluation_input_hash=?, evaluation_implementation_hash=?
                WHERE version=?
                """,
                (
                    run_id,
                    str(return_pct),
                    str(drawdown_pct),
                    int(passed),
                    reason,
                    evaluation_start.isoformat(),
                    evaluation_end.isoformat(),
                    run_id,
                    input_hash,
                    implementation_hash,
                    version,
                ),
            )
            if cursor.rowcount != 1:
                raise KeyError(version)

    def mark_version_pending(self, version: str, reason: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE strategy_versions
                SET passed=NULL, reason=? WHERE version=?
                """,
                (reason, version),
            )

    def recommend(self, version: str, reason: str, run_id: str) -> None:
        with self._connect() as connection:
            connection.execute("UPDATE strategy_versions SET recommended=0")
            connection.execute(
                """
                UPDATE strategy_versions
                SET recommended=1, reason=?, last_run_id=? WHERE version=?
                """,
                (reason, run_id, version),
            )

    def create_proposal(self, create: SignalProposalCreate) -> SignalProposal:
        now = utc_now()
        self.expire_pending(now)
        proposal = SignalProposal(
            id=uuid4().hex,
            **create.model_dump(exclude={"expires_in_seconds"}),
            expires_at=now + timedelta(seconds=create.expires_in_seconds),
            status="pending",
            created_at=now,
        )
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            claimed = connection.execute(
                """
                SELECT proposal_id FROM proposal_signal_claims_v2
                WHERE symbol=? AND side=? AND strategy_version=? AND signal_date=?
                  AND signal_input_hash=?
                """,
                (
                    create.symbol,
                    create.side,
                    create.strategy_version,
                    create.signal_date.isoformat(),
                    create.signal_input_hash,
                ),
            ).fetchone()
            if claimed is not None:
                return self.get_proposal(claimed["proposal_id"], connection)
            try:
                connection.execute(
                    """
                    INSERT INTO signal_proposals (
                        id, symbol, side, quantity, limit_price, expires_at,
                        strategy_version, signal_date, source_run_id,
                        signal_input_hash, reason, status, created_at,
                        decided_at, decision_reason
                    ) VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, NULL, NULL
                    )
                    """,
                    (
                        proposal.id,
                        proposal.symbol,
                        proposal.side,
                        proposal.quantity,
                        str(proposal.limit_price),
                        proposal.expires_at.isoformat(),
                        proposal.strategy_version,
                        proposal.signal_date.isoformat(),
                        proposal.source_run_id,
                        proposal.signal_input_hash,
                        proposal.reason,
                        proposal.created_at.isoformat(),
                    ),
                )
                self._audit(
                    connection,
                    "proposal_created",
                    proposal.id,
                    create.model_dump(mode="json"),
                )
                connection.execute(
                    """
                    INSERT INTO proposal_signal_claims_v2
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        create.symbol,
                        create.side,
                        create.strategy_version,
                        create.signal_date.isoformat(),
                        create.signal_input_hash,
                        proposal.id,
                    ),
                )
            except sqlite3.IntegrityError:
                row = connection.execute(
                    """
                    SELECT * FROM signal_proposals
                    WHERE symbol=? AND side=? AND strategy_version=?
                      AND status='pending'
                    """,
                    (create.symbol, create.side, create.strategy_version),
                ).fetchone()
                if row is None:
                    raise
                return self._proposal(row)
        return proposal

    def expire_pending(self, now: datetime | None = None) -> int:
        moment = now or utc_now()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE signal_proposals
                SET status='expired', decided_at=?, decision_reason='승인 유효시간 만료'
                WHERE status='pending' AND expires_at <= ?
                """,
                (moment.isoformat(), moment.isoformat()),
            )
            return cursor.rowcount

    def expire_incompatible_proposals(
        self,
        *,
        symbol: str,
        strategy_version: str,
        valid_side: str | None,
        signal_date: date,
        signal_input_hash: str,
    ) -> int:
        now = utc_now()
        with self._connect() as connection:
            if valid_side is None:
                cursor = connection.execute(
                    """
                    UPDATE signal_proposals
                    SET status='expired', decided_at=?,
                        decision_reason='최신 확정 일봉에서 신호 근거가 해제됨'
                    WHERE status='pending' AND symbol=? AND strategy_version=?
                    """,
                    (now.isoformat(), symbol, strategy_version),
                )
            else:
                cursor = connection.execute(
                    """
                    UPDATE signal_proposals
                    SET status='expired', decided_at=?,
                        decision_reason='최신 확정 일봉 또는 입력 스냅샷으로 교체됨'
                    WHERE status='pending' AND symbol=? AND strategy_version=?
                      AND (side<>? OR signal_date<>? OR signal_input_hash<>?)
                    """,
                    (
                        now.isoformat(),
                        symbol,
                        strategy_version,
                        valid_side,
                        signal_date.isoformat(),
                        signal_input_hash,
                    ),
                )
            return cursor.rowcount

    def expire_proposal(self, proposal_id: str, reason: str) -> SignalProposal:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE signal_proposals
                SET status='expired', decided_at=?, decision_reason=?
                WHERE id=? AND status='pending'
                """,
                (utc_now().isoformat(), reason, proposal_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("Proposal is no longer pending.")
        return self.get_proposal(proposal_id)

    def proposals(self, limit: int = 100) -> list[SignalProposal]:
        self.expire_pending()
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM signal_proposals ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._proposal(row) for row in rows]

    @staticmethod
    def _proposal(row: sqlite3.Row) -> SignalProposal:
        return SignalProposal(
            id=row["id"],
            symbol=row["symbol"],
            side=row["side"],
            quantity=row["quantity"],
            limit_price=Decimal(row["limit_price"]),
            expires_at=datetime.fromisoformat(row["expires_at"]),
            strategy_version=row["strategy_version"],
            signal_date=date.fromisoformat(row["signal_date"]),
            source_run_id=row["source_run_id"],
            signal_input_hash=row["signal_input_hash"],
            reason=row["reason"],
            status=row["status"],
            created_at=datetime.fromisoformat(row["created_at"]),
            decided_at=datetime.fromisoformat(row["decided_at"])
            if row["decided_at"]
            else None,
            decision_reason=row["decision_reason"],
        )

    def decide(
        self,
        proposal_id: str,
        decision: ProposalDecision,
        quote: Quote | None,
        *,
        now: datetime | None = None,
        quote_max_age_seconds: int = 15,
        signal_max_age_days: int = 7,
    ) -> tuple[SignalProposal, PaperFill | None]:
        moment = now or utc_now()
        if decision.execution_mode != "paper":
            raise ValueError("Live execution is not supported.")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM signal_proposals WHERE id=?", (proposal_id,)
            ).fetchone()
            if row is None:
                raise KeyError(proposal_id)
            proposal = self._proposal(row)
            if proposal.strategy_version != decision.expected_version:
                raise ValueError("Strategy version changed before approval.")
            if decision.action == "approve":
                active = connection.execute(
                    """
                    SELECT version FROM strategy_versions
                    WHERE active_for_paper=1
                    """
                ).fetchone()
                if active is None or active["version"] != proposal.strategy_version:
                    raise ValueError(
                        "The active paper strategy changed before approval."
                    )
            existing_fill = connection.execute(
                "SELECT * FROM paper_fills WHERE proposal_id=?", (proposal_id,)
            ).fetchone()
            if (
                proposal.status == "filled"
                and existing_fill is not None
                and decision.action == "approve"
            ):
                return proposal, self._fill(existing_fill)
            if proposal.status != "pending":
                raise ValueError(f"Proposal is already {proposal.status}.")
            if proposal.expires_at <= moment:
                connection.execute(
                    """
                    UPDATE signal_proposals SET status='expired', decided_at=?
                    WHERE id=?
                    """,
                    (moment.isoformat(), proposal_id),
                )
                self._audit(connection, "proposal_expired", proposal_id, {})
                connection.commit()
                raise ValueError("Proposal approval window expired.")
            if decision.action == "reject":
                connection.execute(
                    """
                    UPDATE signal_proposals
                    SET status='rejected', decided_at=?, decision_reason=? WHERE id=?
                    """,
                    (moment.isoformat(), decision.reason, proposal_id),
                )
                self._audit(connection, "proposal_rejected", proposal_id, {})
                return self.get_proposal(proposal_id, connection), None
            if quote is None or quote.symbol != proposal.symbol:
                raise ValueError("A matching real-time quote is required.")
            quote_received = quote.received_at.astimezone(UTC)
            quote_market = quote.market_at.astimezone(UTC)
            if quote_received > moment + timedelta(
                seconds=2
            ) or quote_market > moment + timedelta(seconds=2):
                raise ValueError("The quote timestamp is in the future.")
            if moment - quote_received > timedelta(seconds=quote_max_age_seconds):
                raise ValueError("The quote is stale; approval was not filled.")
            if moment - quote_market > timedelta(seconds=quote_max_age_seconds):
                raise ValueError("The market price timestamp is stale.")
            signal_today = moment.astimezone(KST).date()
            if proposal.signal_date >= signal_today:
                raise ValueError(
                    "The signal must come from a completed prior daily bar."
                )
            if (signal_today - proposal.signal_date).days > signal_max_age_days:
                raise ValueError("The closed-bar signal is stale.")
            fill_price = (
                quote.ask or quote.price
                if proposal.side == "buy"
                else quote.bid or quote.price
            )
            if proposal.side == "buy" and fill_price > proposal.limit_price:
                raise ValueError("Current ask exceeds the approved price bound.")
            if proposal.side == "sell" and fill_price < proposal.limit_price:
                raise ValueError("Current bid is below the approved price bound.")
            account_row = connection.execute(
                "SELECT * FROM paper_account WHERE id=1"
            ).fetchone()
            assert account_row is not None
            cash = Decimal(account_row["cash"])
            positions: dict[str, int] = json.loads(account_row["positions_json"])
            notional = fill_price * proposal.quantity
            fee = notional * FEE_RATE
            tax = notional * SELL_TAX_RATE if proposal.side == "sell" else Decimal()
            if proposal.side == "buy":
                if cash < notional + fee:
                    raise ValueError("Paper account cash is insufficient.")
                cash -= notional + fee
                positions[proposal.symbol] = (
                    positions.get(proposal.symbol, 0) + proposal.quantity
                )
            else:
                held = positions.get(proposal.symbol, 0)
                if held < proposal.quantity:
                    raise ValueError("Paper position is insufficient.")
                cash += notional - fee - tax
                if held == proposal.quantity:
                    positions.pop(proposal.symbol)
                else:
                    positions[proposal.symbol] = held - proposal.quantity
            fill = PaperFill(
                id=uuid4().hex,
                proposal_id=proposal.id,
                symbol=proposal.symbol,
                side=proposal.side,
                quantity=proposal.quantity,
                price=fill_price,
                notional=notional,
                fee=fee,
                tax=tax,
                filled_at=moment,
            )
            connection.execute(
                "INSERT INTO paper_fills VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    fill.id,
                    fill.proposal_id,
                    fill.symbol,
                    fill.side,
                    fill.quantity,
                    str(fill.price),
                    str(fill.notional),
                    str(fill.fee),
                    str(fill.tax),
                    fill.filled_at.isoformat(),
                ),
            )
            connection.execute(
                """
                UPDATE paper_account SET cash=?, positions_json=?, updated_at=?
                WHERE id=1
                """,
                (str(cash), json.dumps(positions, sort_keys=True), moment.isoformat()),
            )
            connection.execute(
                """
                UPDATE signal_proposals
                SET status='filled', decided_at=?, decision_reason=? WHERE id=?
                """,
                (moment.isoformat(), decision.reason, proposal.id),
            )
            self._audit(
                connection,
                "paper_fill",
                fill.id,
                {"proposal_id": proposal.id, "execution": "app_simulated"},
            )
            return self.get_proposal(proposal.id, connection), fill

    def get_proposal(
        self, proposal_id: str, connection: sqlite3.Connection | None = None
    ) -> SignalProposal:
        if connection is not None:
            row = connection.execute(
                "SELECT * FROM signal_proposals WHERE id=?", (proposal_id,)
            ).fetchone()
        else:
            with self._connect() as own:
                row = own.execute(
                    "SELECT * FROM signal_proposals WHERE id=?", (proposal_id,)
                ).fetchone()
        if row is None:
            raise KeyError(proposal_id)
        return self._proposal(row)

    def paper_account(self) -> PaperAccount:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM paper_account WHERE id=1"
            ).fetchone()
            fills = connection.execute(
                "SELECT * FROM paper_fills ORDER BY filled_at DESC LIMIT 100"
            ).fetchall()
        assert row is not None
        return PaperAccount(
            cash=Decimal(row["cash"]),
            positions=json.loads(row["positions_json"]),
            fills=[self._fill(item) for item in fills],
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    @staticmethod
    def _fill(row: sqlite3.Row) -> PaperFill:
        return PaperFill(
            id=row["id"],
            proposal_id=row["proposal_id"],
            symbol=row["symbol"],
            side=row["side"],
            quantity=row["quantity"],
            price=Decimal(row["price"]),
            notional=Decimal(row["notional"]),
            fee=Decimal(row["fee"]),
            tax=Decimal(row["tax"]),
            filled_at=datetime.fromisoformat(row["filled_at"]),
        )

    @staticmethod
    def _audit(
        connection: sqlite3.Connection, event: str, entity_id: str, details: object
    ) -> None:
        connection.execute(
            """
            INSERT INTO operation_audit(event, entity_id, details_json, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                event,
                entity_id,
                json.dumps(details, ensure_ascii=False, default=str),
                utc_now().isoformat(),
            ),
        )
