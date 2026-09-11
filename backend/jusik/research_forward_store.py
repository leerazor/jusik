from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, localcontext
from pathlib import Path

from jusik.research_forward_models import (
    ForwardConfig,
    ForwardCorporateAction,
    ForwardDecision,
    ForwardEvent,
    ForwardFill,
    ForwardIntent,
    ForwardLedger,
    ForwardObservation,
    ForwardPosition,
    ForwardSession,
)
from jusik.research_quote_models import ResearchQuote


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value: object) -> str:
    return hashlib.sha256(_json(value).encode()).hexdigest()


@dataclass(frozen=True)
class CorporateActionRegistration:
    session_id: str
    symbol: str
    exchange: str
    factor: int
    source_url: str
    evidence_id: str
    evidence_sha256: str
    observed_at: datetime
    effective_at: datetime
    registered_at: datetime


class ForwardStore:
    """Private, transactionally updated paper ledger; it never submits broker orders."""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode=WAL;
                PRAGMA foreign_keys=ON;
                CREATE TABLE IF NOT EXISTS forward_sessions (
                    id TEXT PRIMARY KEY, activated_at TEXT NOT NULL,
                    next_due_at TEXT NOT NULL, source_run_id TEXT NOT NULL,
                    policy_hash TEXT NOT NULL, config_json TEXT NOT NULL,
                    state TEXT NOT NULL, cash_krw TEXT NOT NULL,
                    lifetime_high_water_krw TEXT NOT NULL,
                    episode_high_water_krw TEXT NOT NULL,
                    liquidation_completed_at TEXT,
                    next_recovery_check_at TEXT,
                    recovery_confirmations INTEGER NOT NULL,
                    active INTEGER NOT NULL CHECK(active IN (0,1))
                );
                CREATE UNIQUE INDEX IF NOT EXISTS one_active_forward_session
                    ON forward_sessions(active) WHERE active=1;
                CREATE TABLE IF NOT EXISTS forward_observations (
                    id TEXT PRIMARY KEY, session_id TEXT NOT NULL,
                    symbol TEXT NOT NULL, minute_key TEXT NOT NULL,
                    market_at TEXT NOT NULL, received_at TEXT NOT NULL,
                    reason TEXT NOT NULL, quote_json TEXT NOT NULL,
                    UNIQUE(session_id, symbol, minute_key, reason),
                    FOREIGN KEY(session_id) REFERENCES forward_sessions(id)
                );
                CREATE TABLE IF NOT EXISTS forward_input_versions (
                    id TEXT PRIMARY KEY, session_id TEXT NOT NULL,
                    cutoff_at TEXT NOT NULL, payload_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES forward_sessions(id)
                );
                CREATE TABLE IF NOT EXISTS forward_decisions (
                    id TEXT PRIMARY KEY, session_id TEXT NOT NULL,
                    due_at TEXT NOT NULL, recorded_at TEXT NOT NULL,
                    input_version TEXT NOT NULL, state TEXT NOT NULL,
                    reason TEXT NOT NULL, expires_at TEXT,
                    target_weights_json TEXT NOT NULL, intents_json TEXT NOT NULL,
                    volatility_proxy TEXT, volatility_scale TEXT,
                    UNIQUE(session_id, due_at),
                    FOREIGN KEY(session_id) REFERENCES forward_sessions(id)
                );
                CREATE TABLE IF NOT EXISTS forward_positions (
                    session_id TEXT NOT NULL, symbol TEXT NOT NULL,
                    currency TEXT NOT NULL, quantity INTEGER NOT NULL,
                    average_cost_krw TEXT NOT NULL, updated_at TEXT NOT NULL,
                    PRIMARY KEY(session_id, symbol),
                    FOREIGN KEY(session_id) REFERENCES forward_sessions(id)
                );
                CREATE TABLE IF NOT EXISTS forward_fills (
                    id TEXT PRIMARY KEY, session_id TEXT NOT NULL,
                    decision_id TEXT NOT NULL, symbol TEXT NOT NULL,
                    side TEXT NOT NULL, quantity INTEGER NOT NULL,
                    market_at TEXT NOT NULL, received_at TEXT NOT NULL,
                    local_price TEXT NOT NULL, fx_rate TEXT NOT NULL,
                    notional_krw TEXT NOT NULL, transaction_cost_krw TEXT NOT NULL,
                    fx_cost_krw TEXT NOT NULL, cash_after_krw TEXT NOT NULL,
                    quote_id TEXT NOT NULL, payload_json TEXT NOT NULL,
                    UNIQUE(session_id, decision_id, symbol),
                    FOREIGN KEY(session_id) REFERENCES forward_sessions(id),
                    FOREIGN KEY(decision_id) REFERENCES forward_decisions(id)
                );
                CREATE TABLE IF NOT EXISTS forward_execution_quotes (
                    fill_id TEXT PRIMARY KEY,
                    quote_json TEXT NOT NULL,
                    quote_sha256 TEXT NOT NULL,
                    captured_at TEXT NOT NULL,
                    FOREIGN KEY(fill_id) REFERENCES forward_fills(id)
                );
                CREATE TABLE IF NOT EXISTS forward_events (
                    id TEXT PRIMARY KEY, session_id TEXT NOT NULL,
                    occurred_at TEXT NOT NULL, kind TEXT NOT NULL,
                    detail TEXT NOT NULL, reference_id TEXT,
                    UNIQUE(session_id, kind, reference_id),
                    FOREIGN KEY(session_id) REFERENCES forward_sessions(id)
                );
                CREATE TABLE IF NOT EXISTS forward_corporate_actions (
                    session_id TEXT NOT NULL, symbol TEXT NOT NULL,
                    action_key TEXT NOT NULL, applied_at TEXT NOT NULL,
                    PRIMARY KEY(session_id, symbol, action_key)
                );
                CREATE TABLE IF NOT EXISTS forward_corporate_action_metadata (
                    id TEXT PRIMARY KEY, session_id TEXT NOT NULL,
                    symbol TEXT NOT NULL, exchange TEXT NOT NULL,
                    numerator INTEGER NOT NULL, denominator INTEGER NOT NULL,
                    factor INTEGER NOT NULL, source_url TEXT NOT NULL,
                    evidence_id TEXT NOT NULL, evidence_sha256 TEXT NOT NULL,
                    operator_verified INTEGER NOT NULL CHECK(operator_verified=1),
                    observed_at TEXT NOT NULL, effective_at TEXT NOT NULL,
                    registered_at TEXT NOT NULL,
                    UNIQUE(session_id, symbol, effective_at),
                    FOREIGN KEY(session_id) REFERENCES forward_sessions(id)
                );
                CREATE TABLE IF NOT EXISTS forward_corporate_action_applications (
                    action_id TEXT PRIMARY KEY, applied_at TEXT NOT NULL,
                    before_quantity INTEGER NOT NULL,
                    after_quantity INTEGER NOT NULL,
                    before_average_cost_krw TEXT NOT NULL,
                    after_average_cost_krw TEXT NOT NULL,
                    FOREIGN KEY(action_id)
                        REFERENCES forward_corporate_action_metadata(id)
                );
                CREATE TABLE IF NOT EXISTS forward_checkpoints (
                    id TEXT PRIMARY KEY, session_id TEXT NOT NULL,
                    checkpoint_at TEXT NOT NULL, actually_known_at TEXT NOT NULL,
                    equity_krw TEXT NOT NULL, cash_krw TEXT NOT NULL,
                    positions_json TEXT NOT NULL,
                    UNIQUE(session_id, checkpoint_at)
                );
                """
            )
            columns = {
                str(row["name"])
                for row in connection.execute(
                    "PRAGMA table_info(forward_sessions)"
                ).fetchall()
            }
            if "next_recovery_check_at" not in columns:
                connection.execute(
                    """ALTER TABLE forward_sessions
                    ADD COLUMN next_recovery_check_at TEXT"""
                )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def active_session(self) -> ForwardSession | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM forward_sessions WHERE active=1"
            ).fetchone()
        return self._session(row) if row else None

    def activate(
        self,
        *,
        activated_at: datetime,
        next_due_at: datetime,
        source_run_id: str,
        config: ForwardConfig,
    ) -> ForwardSession:
        if activated_at.tzinfo is None or next_due_at.tzinfo is None:
            raise ValueError("Forward timestamps must be timezone-aware.")
        existing = self.active_session()
        if existing is not None:
            return existing
        policy_hash = _hash(config.model_dump(mode="json"))
        session_id = _hash(
            {
                "activated_at": activated_at.astimezone(UTC).isoformat(),
                "policy_hash": policy_hash,
                "source_run_id": source_run_id,
                "initial_cash_krw": str(config.initial_cash_krw),
            }
        )
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO forward_sessions (
                id, activated_at, next_due_at, source_run_id, policy_hash,
                config_json, state, cash_krw, lifetime_high_water_krw,
                episode_high_water_krw, liquidation_completed_at,
                next_recovery_check_at, recovery_confirmations, active
                ) VALUES
                (?, ?, ?, ?, ?, ?, 'waiting_cadence', ?, ?, ?, NULL, NULL, 0, 1)""",
                (
                    session_id,
                    activated_at.astimezone(UTC).isoformat(),
                    next_due_at.astimezone(UTC).isoformat(),
                    source_run_id,
                    policy_hash,
                    config.model_dump_json(),
                    str(config.initial_cash_krw),
                    str(config.initial_cash_krw),
                    str(config.initial_cash_krw),
                ),
            )
            self._insert_event(
                connection,
                session_id,
                activated_at,
                "session_activated",
                "1억원 현금으로 분리된 전진 PAPER 원장을 활성화했습니다.",
                session_id,
            )
        result = self.active_session()
        if result is None:
            raise RuntimeError("Forward session activation did not persist.")
        return result

    @staticmethod
    def _session(row: sqlite3.Row) -> ForwardSession:
        return ForwardSession(
            id=row["id"],
            activated_at=row["activated_at"],
            next_due_at=row["next_due_at"],
            source_run_id=row["source_run_id"],
            policy_hash=row["policy_hash"],
            config=ForwardConfig.model_validate_json(row["config_json"]),
            state=row["state"],
            cash_krw=row["cash_krw"],
            lifetime_high_water_krw=row["lifetime_high_water_krw"],
            episode_high_water_krw=row["episode_high_water_krw"],
            liquidation_completed_at=row["liquidation_completed_at"],
            next_recovery_check_at=row["next_recovery_check_at"],
            recovery_confirmations=row["recovery_confirmations"],
        )

    def save_observation(
        self, session_id: str, quote: ResearchQuote, reason: str = "minute_sample"
    ) -> ForwardObservation:
        normalized = quote.model_copy(
            update={
                "market_at": quote.market_at.astimezone(UTC),
                "received_at": quote.received_at.astimezone(UTC),
            }
        )
        minute = normalized.market_at.replace(second=0, microsecond=0).isoformat()
        identity = _hash(
            {
                "session": session_id,
                "symbol": quote.symbol,
                "minute": minute,
                "reason": reason,
            }
        )
        with self._connect() as connection:
            connection.execute(
                """INSERT OR IGNORE INTO forward_observations
                (id, session_id, symbol, minute_key, market_at, received_at,
                 reason, quote_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    identity,
                    session_id,
                    quote.symbol,
                    minute,
                    normalized.market_at.isoformat(),
                    normalized.received_at.isoformat(),
                    reason,
                    normalized.model_dump_json(),
                ),
            )
            row = connection.execute(
                """SELECT * FROM forward_observations
                WHERE session_id=? AND symbol=? AND minute_key=? AND reason=?""",
                (session_id, quote.symbol, minute, reason),
            ).fetchone()
        if row is None:
            raise RuntimeError("Forward observation did not persist.")
        return ForwardObservation(
            id=row["id"],
            quote=ResearchQuote.model_validate_json(row["quote_json"]),
            persisted_reason=row["reason"],
        )

    def save_input_version(
        self, session_id: str, cutoff_at: datetime, payload: dict[str, object]
    ) -> str:
        content = _json(payload)
        identity = _hash(
            {"session": session_id, "cutoff": cutoff_at.isoformat(), "payload": payload}
        )
        with self._connect() as connection:
            connection.execute(
                """INSERT OR IGNORE INTO forward_input_versions
                VALUES (?, ?, ?, ?, ?)""",
                (
                    identity,
                    session_id,
                    cutoff_at.astimezone(UTC).isoformat(),
                    content,
                    datetime.now(UTC).isoformat(),
                ),
            )
        return identity

    def record_decision(
        self,
        *,
        session_id: str,
        due_at: datetime,
        recorded_at: datetime,
        input_version: str,
        reason: str,
        expires_at: datetime | None,
        target_weights: dict[str, Decimal],
        intents: list[ForwardIntent],
        volatility_proxy: Decimal | None = None,
        volatility_scale: Decimal | None = None,
    ) -> ForwardDecision:
        decision_id = _hash({"session": session_id, "due_at": due_at.isoformat()})
        state = (
            "awaiting_quotes"
            if any(x.state == "pending" for x in intents)
            else "completed"
        )
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """INSERT OR IGNORE INTO forward_decisions VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    decision_id,
                    session_id,
                    due_at.astimezone(UTC).isoformat(),
                    recorded_at.astimezone(UTC).isoformat(),
                    input_version,
                    state,
                    reason,
                    expires_at.astimezone(UTC).isoformat() if expires_at else None,
                    _json({key: str(value) for key, value in target_weights.items()}),
                    _json([item.model_dump(mode="json") for item in intents]),
                    str(volatility_proxy) if volatility_proxy is not None else None,
                    str(volatility_scale) if volatility_scale is not None else None,
                ),
            )
            connection.execute(
                "UPDATE forward_sessions SET state=? WHERE id=?", (state, session_id)
            )
            self._insert_event(
                connection,
                session_id,
                recorded_at,
                "decision_recorded",
                "사전 고정 정책의 PAPER 결정을 기록했습니다.",
                decision_id,
            )
        result = self.decision(decision_id)
        if result is None:
            raise RuntimeError("Forward decision did not persist.")
        return result

    def decision(self, decision_id: str) -> ForwardDecision | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM forward_decisions WHERE id=?", (decision_id,)
            ).fetchone()
        return self._decision(row) if row else None

    @staticmethod
    def _decision(row: sqlite3.Row) -> ForwardDecision:
        return ForwardDecision(
            id=row["id"],
            session_id=row["session_id"],
            due_at=row["due_at"],
            recorded_at=row["recorded_at"],
            input_version=row["input_version"],
            state=row["state"],
            reason=row["reason"],
            expires_at=row["expires_at"],
            target_weights=json.loads(row["target_weights_json"]),
            intents=[
                ForwardIntent.model_validate(item)
                for item in json.loads(row["intents_json"])
            ],
            volatility_proxy=row["volatility_proxy"],
            volatility_scale=row["volatility_scale"],
        )

    def pending_decisions(self, session_id: str) -> list[ForwardDecision]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT * FROM forward_decisions WHERE session_id=?
                AND state IN ('awaiting_quotes','partially_completed')
                ORDER BY due_at""",
                (session_id,),
            ).fetchall()
        return [self._decision(row) for row in rows]

    def block_pending_buys(self, session_id: str) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                """SELECT * FROM forward_decisions WHERE session_id=?
                AND state IN ('awaiting_quotes','partially_completed')""",
                (session_id,),
            ).fetchall()
            for row in rows:
                decision = self._decision(row)
                intents = [
                    item.model_copy(update={"state": "blocked"})
                    if item.side == "buy" and item.state == "pending"
                    else item
                    for item in decision.intents
                ]
                pending = any(item.state == "pending" for item in intents)
                state = "partially_completed" if pending else "completed"
                connection.execute(
                    """UPDATE forward_decisions SET intents_json=?, state=?
                    WHERE id=?""",
                    (
                        _json([item.model_dump(mode="json") for item in intents]),
                        state,
                        decision.id,
                    ),
                )

    def positions(self, session_id: str) -> list[ForwardPosition]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM forward_positions WHERE session_id=? ORDER BY symbol",
                (session_id,),
            ).fetchall()
        return [
            ForwardPosition(
                symbol=row["symbol"],
                currency=row["currency"],
                quantity=row["quantity"],
                average_cost_krw=row["average_cost_krw"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    def apply_fill(
        self,
        *,
        decision: ForwardDecision,
        intent: ForwardIntent,
        quote: ResearchQuote,
        quote_id: str,
        fx_rate: Decimal,
        quantity: int,
        local_fill_price: Decimal,
        transaction_cost_krw: Decimal,
        fx_cost_krw: Decimal,
    ) -> ForwardFill | None:
        if quantity <= 0:
            raise ValueError("Paper fill quantity must be positive.")
        fill_id = _hash(
            {
                "session": decision.session_id,
                "decision": decision.id,
                "symbol": intent.symbol,
            }
        )
        notional = local_fill_price * quantity * fx_rate
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            duplicate = connection.execute(
                """SELECT payload_json FROM forward_fills
                WHERE session_id=? AND decision_id=? AND symbol=?""",
                (decision.session_id, decision.id, intent.symbol),
            ).fetchone()
            if duplicate:
                return ForwardFill.model_validate_json(duplicate["payload_json"])
            due_action = connection.execute(
                """SELECT m.effective_at
                FROM forward_corporate_action_metadata m
                LEFT JOIN forward_corporate_action_applications a
                    ON a.action_id=m.id
                WHERE m.session_id=? AND m.symbol=? AND m.effective_at<=?
                    AND a.action_id IS NULL
                LIMIT 1""",
                (
                    decision.session_id,
                    intent.symbol,
                    quote.received_at.astimezone(UTC).isoformat(),
                ),
            ).fetchone()
            if due_action is not None:
                return None
            applied_action = connection.execute(
                """SELECT m.effective_at
                FROM forward_corporate_action_metadata m
                JOIN forward_corporate_action_applications a ON a.action_id=m.id
                WHERE m.session_id=? AND m.symbol=?
                ORDER BY m.effective_at DESC LIMIT 1""",
                (decision.session_id, intent.symbol),
            ).fetchone()
            if applied_action is not None and quote.market_at.astimezone(
                UTC
            ) < datetime.fromisoformat(applied_action["effective_at"]).astimezone(UTC):
                return None
            current_decision = connection.execute(
                "SELECT intents_json FROM forward_decisions WHERE id=?",
                (decision.id,),
            ).fetchone()
            if current_decision is None:
                raise ValueError("Forward decision is unavailable.")
            current_intents = [
                ForwardIntent.model_validate(item)
                for item in json.loads(current_decision["intents_json"])
            ]
            persisted_intent = next(
                (item for item in current_intents if item.symbol == intent.symbol), None
            )
            if persisted_intent is None or persisted_intent.state != "pending":
                return None
            if persisted_intent != intent:
                return None
            intent = persisted_intent
            session = connection.execute(
                "SELECT * FROM forward_sessions WHERE id=?", (decision.session_id,)
            ).fetchone()
            position = connection.execute(
                """SELECT * FROM forward_positions
                WHERE session_id=? AND symbol=?""",
                (decision.session_id, intent.symbol),
            ).fetchone()
            if session is None:
                raise ValueError("Forward session is unavailable.")
            cash = Decimal(session["cash_krw"])
            held = int(position["quantity"]) if position else 0
            if intent.side == "buy":
                cash_after = cash - notional - transaction_cost_krw - fx_cost_krw
                quantity_after = held + quantity
                if cash_after < 0:
                    raise ValueError("Paper fill would make cash negative.")
                previous_cost = (
                    Decimal(position["average_cost_krw"]) * held
                    if position
                    else Decimal()
                )
                average_cost = (
                    previous_cost + notional + transaction_cost_krw + fx_cost_krw
                ) / quantity_after
            else:
                if quantity > held:
                    raise ValueError("Paper sell exceeds the held quantity.")
                cash_after = cash + notional - transaction_cost_krw - fx_cost_krw
                quantity_after = held - quantity
                average_cost = (
                    Decimal(position["average_cost_krw"]) if position else Decimal()
                )
            now = quote.received_at.astimezone(UTC)
            fill = ForwardFill(
                id=fill_id,
                session_id=decision.session_id,
                decision_id=decision.id,
                symbol=intent.symbol,
                side=intent.side,
                quantity=quantity,
                market_at=quote.market_at.astimezone(UTC),
                received_at=now,
                local_price=local_fill_price,
                fx_rate=fx_rate,
                notional_krw=notional,
                transaction_cost_krw=transaction_cost_krw,
                fx_cost_krw=fx_cost_krw,
                cash_after_krw=cash_after,
                quote_id=quote_id,
            )
            connection.execute(
                "UPDATE forward_sessions SET cash_krw=? WHERE id=?",
                (str(cash_after), decision.session_id),
            )
            connection.execute(
                """INSERT INTO forward_positions VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id,symbol) DO UPDATE SET
                quantity=excluded.quantity, average_cost_krw=excluded.average_cost_krw,
                updated_at=excluded.updated_at""",
                (
                    decision.session_id,
                    intent.symbol,
                    quote.currency,
                    quantity_after,
                    str(average_cost),
                    now.isoformat(),
                ),
            )
            connection.execute(
                """INSERT INTO forward_fills VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    fill.id,
                    fill.session_id,
                    fill.decision_id,
                    fill.symbol,
                    fill.side,
                    fill.quantity,
                    fill.market_at.isoformat(),
                    fill.received_at.isoformat(),
                    str(fill.local_price),
                    str(fill.fx_rate),
                    str(fill.notional_krw),
                    str(fill.transaction_cost_krw),
                    str(fill.fx_cost_krw),
                    str(fill.cash_after_krw),
                    fill.quote_id,
                    fill.model_dump_json(),
                ),
            )
            execution_quote_json = quote.model_dump_json()
            connection.execute(
                """INSERT INTO forward_execution_quotes
                (fill_id, quote_json, quote_sha256, captured_at)
                VALUES (?, ?, ?, ?)""",
                (
                    fill.id,
                    execution_quote_json,
                    hashlib.sha256(execution_quote_json.encode()).hexdigest(),
                    now.isoformat(),
                ),
            )
            self._consume_intent(connection, decision, intent.symbol, "filled")
            self._insert_event(
                connection,
                decision.session_id,
                now,
                "fill_recorded",
                "정규장 시세로 가상 전량 체결을 기록했습니다.",
                fill.id,
            )
        return fill

    def consume_intent(
        self, decision: ForwardDecision, symbol: str, detail: str
    ) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._consume_intent(connection, decision, symbol, "consumed")
            self._insert_event(
                connection,
                decision.session_id,
                datetime.now(UTC),
                "intent_consumed",
                detail,
                f"{decision.id}:{symbol}",
            )

    def _consume_intent(
        self,
        connection: sqlite3.Connection,
        decision: ForwardDecision,
        symbol: str,
        state: str,
    ) -> None:
        row = connection.execute(
            "SELECT intents_json FROM forward_decisions WHERE id=?", (decision.id,)
        ).fetchone()
        if row is None:
            raise ValueError("Forward decision is unavailable.")
        current = [
            ForwardIntent.model_validate(item)
            for item in json.loads(row["intents_json"])
        ]
        intents = [
            item.model_copy(update={"state": state})
            if item.symbol == symbol and item.state == "pending"
            else item
            for item in current
        ]
        pending = any(item.state == "pending" for item in intents)
        next_state = "partially_completed" if pending else "completed"
        connection.execute(
            "UPDATE forward_decisions SET intents_json=?, state=? WHERE id=?",
            (
                _json([item.model_dump(mode="json") for item in intents]),
                next_state,
                decision.id,
            ),
        )
        connection.execute(
            "UPDATE forward_sessions SET state=? WHERE id=?",
            (
                "risk_liquidation"
                if decision.expires_at is None and pending
                else next_state,
                decision.session_id,
            ),
        )

    def fills(self, session_id: str, limit: int = 200) -> list[ForwardFill]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT payload_json FROM forward_fills WHERE session_id=?
                ORDER BY received_at DESC LIMIT ?""",
                (session_id, min(max(limit, 1), 500)),
            ).fetchall()
        return [ForwardFill.model_validate_json(row["payload_json"]) for row in rows]

    def decisions(self, session_id: str, limit: int = 100) -> list[ForwardDecision]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT * FROM forward_decisions WHERE session_id=?
                ORDER BY due_at DESC LIMIT ?""",
                (session_id, min(max(limit, 1), 500)),
            ).fetchall()
        return [self._decision(row) for row in rows]

    def observations(
        self, session_id: str, limit: int = 500
    ) -> list[ForwardObservation]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT * FROM forward_observations WHERE session_id=?
                ORDER BY received_at DESC LIMIT ?""",
                (session_id, min(max(limit, 1), 1000)),
            ).fetchall()
        return [
            ForwardObservation(
                id=row["id"],
                quote=ResearchQuote.model_validate_json(row["quote_json"]),
                persisted_reason=row["reason"],
            )
            for row in rows
        ]

    def latest_quotes(self, session_id: str) -> dict[str, ForwardObservation]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT o.* FROM forward_observations o
                JOIN (
                    SELECT symbol, MAX(market_at) AS market_at
                    FROM forward_observations WHERE session_id=? GROUP BY symbol
                ) latest ON latest.symbol=o.symbol AND latest.market_at=o.market_at
                WHERE o.session_id=? ORDER BY o.symbol""",
                (session_id, session_id),
            ).fetchall()
        return {
            str(row["symbol"]): ForwardObservation(
                id=row["id"],
                quote=ResearchQuote.model_validate_json(row["quote_json"]),
                persisted_reason=row["reason"],
            )
            for row in rows
        }

    def advance_due(self, session_id: str, next_due_at: datetime, state: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE forward_sessions SET next_due_at=?, state=? WHERE id=?",
                (next_due_at.astimezone(UTC).isoformat(), state, session_id),
            )

    def set_state(self, session_id: str, state: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE forward_sessions SET state=? WHERE id=?", (state, session_id)
            )

    def record_checkpoint(
        self,
        session_id: str,
        checkpoint_at: datetime,
        actually_known_at: datetime,
        equity_krw: Decimal,
        cash_krw: Decimal,
        positions: dict[str, Decimal],
        *,
        update_episode: bool = True,
    ) -> bool:
        identity = _hash(
            {"session": session_id, "checkpoint": checkpoint_at.isoformat()}
        )
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """INSERT OR IGNORE INTO forward_checkpoints
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    identity,
                    session_id,
                    checkpoint_at.astimezone(UTC).isoformat(),
                    actually_known_at.astimezone(UTC).isoformat(),
                    str(equity_krw),
                    str(cash_krw),
                    _json({key: str(value) for key, value in positions.items()}),
                ),
            )
            if cursor.rowcount:
                row = connection.execute(
                    "SELECT * FROM forward_sessions WHERE id=?", (session_id,)
                ).fetchone()
                if row is not None:
                    lifetime = max(Decimal(row["lifetime_high_water_krw"]), equity_krw)
                    episode = Decimal(row["episode_high_water_krw"])
                    if update_episode:
                        episode = max(episode, equity_krw)
                    connection.execute(
                        """UPDATE forward_sessions SET lifetime_high_water_krw=?,
                        episode_high_water_krw=? WHERE id=?""",
                        (str(lifetime), str(episode), session_id),
                    )
        return bool(cursor.rowcount)

    def complete_liquidation(self, session_id: str, at: datetime) -> None:
        threshold = at.astimezone(UTC) + timedelta(days=28)
        next_check = threshold.replace(hour=0, minute=0, second=0, microsecond=0)
        next_check += timedelta(days=(7 - next_check.weekday()) % 7)
        if next_check < threshold:
            next_check += timedelta(days=7)
        with self._connect() as connection:
            connection.execute(
                """UPDATE forward_sessions SET state='cooldown',
                liquidation_completed_at=?, next_recovery_check_at=?,
                recovery_confirmations=0 WHERE id=?""",
                (at.astimezone(UTC).isoformat(), next_check.isoformat(), session_id),
            )
            self._insert_event(
                connection,
                session_id,
                at,
                "liquidation_complete",
                "가상 청산 완료 후 28일 회복 대기를 시작했습니다.",
                at.astimezone(UTC).isoformat(),
            )

    def set_recovery(
        self,
        session_id: str,
        *,
        confirmations: int,
        next_check_at: datetime | None,
        state: str,
        episode_high_water_krw: Decimal | None = None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """UPDATE forward_sessions SET recovery_confirmations=?,
                next_recovery_check_at=?, state=?,
                episode_high_water_krw=COALESCE(?,episode_high_water_krw)
                WHERE id=?""",
                (
                    confirmations,
                    next_check_at.astimezone(UTC).isoformat()
                    if next_check_at
                    else None,
                    state,
                    str(episode_high_water_krw) if episode_high_water_krw else None,
                    session_id,
                ),
            )

    def begin_reentry_episode(
        self, session_id: str, episode_high_water_krw: Decimal
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """UPDATE forward_sessions SET liquidation_completed_at=NULL,
                next_recovery_check_at=NULL, recovery_confirmations=0,
                episode_high_water_krw=?, state='decision_recorded' WHERE id=?""",
                (str(episode_high_water_krw), session_id),
            )

    def record_event(
        self,
        session_id: str,
        occurred_at: datetime,
        kind: str,
        detail: str,
        reference_id: str | None,
    ) -> None:
        with self._connect() as connection:
            self._insert_event(
                connection, session_id, occurred_at, kind, detail, reference_id
            )

    def event_exists(self, session_id: str, kind: str, reference_id: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT 1 FROM forward_events
                WHERE session_id=? AND kind=? AND reference_id=?""",
                (session_id, kind, reference_id),
            ).fetchone()
        return row is not None

    def events(self, session_id: str, limit: int = 200) -> list[ForwardEvent]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT * FROM forward_events WHERE session_id=?
                ORDER BY occurred_at DESC LIMIT ?""",
                (session_id, min(max(limit, 1), 500)),
            ).fetchall()
        return [ForwardEvent(**dict(row)) for row in rows]

    def register_corporate_action(
        self,
        *,
        session_id: str,
        symbol: str,
        exchange: str,
        factor: int,
        source_url: str,
        evidence_id: str,
        evidence_sha256: str,
        observed_at: datetime,
        effective_at: datetime,
        registered_at: datetime,
    ) -> ForwardCorporateAction:
        return self.register_corporate_actions(
            [
                CorporateActionRegistration(
                    session_id=session_id,
                    symbol=symbol,
                    exchange=exchange,
                    factor=factor,
                    source_url=source_url,
                    evidence_id=evidence_id,
                    evidence_sha256=evidence_sha256,
                    observed_at=observed_at,
                    effective_at=effective_at,
                    registered_at=registered_at,
                )
            ]
        )[0]

    def register_corporate_actions(
        self, registrations: list[CorporateActionRegistration]
    ) -> list[ForwardCorporateAction]:
        if not registrations:
            return []
        action_ids: list[tuple[str, datetime]] = []
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            for registration in registrations:
                action_ids.append(
                    (
                        self._register_corporate_action(connection, registration),
                        registration.registered_at,
                    )
                )
        return [
            self.corporate_action(action_id, registered_at)
            for action_id, registered_at in action_ids
        ]

    def _register_corporate_action(
        self,
        connection: sqlite3.Connection,
        registration: CorporateActionRegistration,
    ) -> str:
        timestamps = (
            registration.observed_at,
            registration.effective_at,
            registration.registered_at,
        )
        if any(value.tzinfo is None for value in timestamps):
            raise ValueError("Corporate action timestamps must be timezone-aware.")
        observed = registration.observed_at.astimezone(UTC)
        effective = registration.effective_at.astimezone(UTC)
        registered = registration.registered_at.astimezone(UTC)
        if registration.factor <= 1:
            raise ValueError("Only integer forward splits are supported.")
        if registration.exchange not in {"KRX", "NAS", "NYS", "AMS"}:
            raise ValueError("Corporate action exchange is unsupported.")
        if observed > registered or registered > effective:
            raise ValueError("Corporate action verification was not timely.")
        action_id = _hash(
            {
                "session": registration.session_id,
                "symbol": registration.symbol,
                "effective_at": effective.isoformat(),
            }
        )
        values = (
            action_id,
            registration.session_id,
            registration.symbol,
            registration.exchange,
            registration.factor,
            1,
            registration.factor,
            registration.source_url,
            registration.evidence_id,
            registration.evidence_sha256,
            1,
            observed.isoformat(),
            effective.isoformat(),
            registered.isoformat(),
        )
        session = connection.execute(
            "SELECT activated_at FROM forward_sessions WHERE id=?",
            (registration.session_id,),
        ).fetchone()
        if session is None:
            raise ValueError("Forward session is unavailable.")
        activated = datetime.fromisoformat(session["activated_at"]).astimezone(UTC)
        if registered < activated or effective <= activated:
            raise ValueError(
                "Corporate action does not belong to this forward session."
            )
        existing = connection.execute(
            """SELECT * FROM forward_corporate_action_metadata
            WHERE session_id=? AND symbol=? AND effective_at=?""",
            (
                registration.session_id,
                registration.symbol,
                effective.isoformat(),
            ),
        ).fetchone()
        if existing is not None:
            persisted_evidence = (
                existing["exchange"],
                int(existing["numerator"]),
                int(existing["denominator"]),
                int(existing["factor"]),
                existing["source_url"],
                existing["evidence_id"],
                existing["evidence_sha256"],
                int(existing["operator_verified"]),
                existing["observed_at"],
            )
            submitted_evidence = (
                registration.exchange,
                registration.factor,
                1,
                registration.factor,
                registration.source_url,
                registration.evidence_id,
                registration.evidence_sha256,
                1,
                observed.isoformat(),
            )
            if persisted_evidence != submitted_evidence:
                raise ValueError(
                    "Corporate action registration conflicts with evidence."
                )
        else:
            connection.execute(
                """INSERT INTO forward_corporate_action_metadata VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                values,
            )
            self._insert_event(
                connection,
                registration.session_id,
                registered,
                "corporate_action_registered",
                "운영자가 검증한 정수 정방향 분할을 등록했습니다.",
                action_id,
            )
        return action_id

    def corporate_action(
        self, action_id: str, status_at: datetime | None = None
    ) -> ForwardCorporateAction:
        current = (status_at or datetime.now(UTC)).astimezone(UTC)
        with self._connect() as connection:
            row = connection.execute(
                """SELECT m.*, a.applied_at, a.before_quantity, a.after_quantity
                FROM forward_corporate_action_metadata m
                LEFT JOIN forward_corporate_action_applications a
                    ON a.action_id=m.id
                WHERE m.id=?""",
                (action_id,),
            ).fetchone()
            if row is None:
                raise KeyError(action_id)
            blocked = self._corporate_action_block_reason(connection, row, current)
        return self._corporate_action_model(row, blocked)

    def corporate_actions(
        self,
        session_id: str,
        status_at: datetime | None = None,
        limit: int = 200,
    ) -> list[ForwardCorporateAction]:
        current = (status_at or datetime.now(UTC)).astimezone(UTC)
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT m.*, a.applied_at, a.before_quantity, a.after_quantity
                FROM forward_corporate_action_metadata m
                LEFT JOIN forward_corporate_action_applications a
                    ON a.action_id=m.id
                WHERE m.session_id=? ORDER BY m.effective_at DESC, m.id DESC
                LIMIT ?""",
                (session_id, min(max(limit, 1), 500)),
            ).fetchall()
            results = [
                self._corporate_action_model(
                    row,
                    self._corporate_action_block_reason(connection, row, current),
                )
                for row in rows
            ]
        return results

    @staticmethod
    def _corporate_action_block_reason(
        connection: sqlite3.Connection, row: sqlite3.Row, status_at: datetime
    ) -> str | None:
        if row["applied_at"] is not None:
            return None
        observed = datetime.fromisoformat(row["observed_at"]).astimezone(UTC)
        registered = datetime.fromisoformat(row["registered_at"]).astimezone(UTC)
        effective = datetime.fromisoformat(row["effective_at"]).astimezone(UTC)
        if observed > registered or registered > effective:
            return "verification_not_timely"
        if effective > status_at:
            return None
        prior_unapplied = connection.execute(
            """SELECT 1 FROM forward_corporate_action_metadata prior
            LEFT JOIN forward_corporate_action_applications prior_application
                ON prior_application.action_id=prior.id
            WHERE prior.session_id=? AND prior.symbol=?
                AND prior.effective_at<? AND prior_application.action_id IS NULL
            LIMIT 1""",
            (row["session_id"], row["symbol"], row["effective_at"]),
        ).fetchone()
        if prior_unapplied is not None:
            return "prior_split_unapplied"
        fill = connection.execute(
            """SELECT 1 FROM forward_fills
            WHERE session_id=? AND symbol=? AND received_at>=? LIMIT 1""",
            (row["session_id"], row["symbol"], row["effective_at"]),
        ).fetchone()
        if fill is not None:
            return "fill_at_or_after_effective_at"
        checkpoint = connection.execute(
            """SELECT 1 FROM forward_checkpoints
            WHERE session_id=? AND checkpoint_at>=? LIMIT 1""",
            (row["session_id"], row["effective_at"]),
        ).fetchone()
        if checkpoint is not None:
            return "checkpoint_at_or_after_effective_at"
        legacy = connection.execute(
            """SELECT 1 FROM forward_corporate_actions
            WHERE session_id=? AND symbol=? AND action_key=? LIMIT 1""",
            (row["session_id"], row["symbol"], row["id"]),
        ).fetchone()
        return "application_metadata_missing" if legacy is not None else None

    @staticmethod
    def _corporate_action_model(
        row: sqlite3.Row, blocked_reason: str | None
    ) -> ForwardCorporateAction:
        if row["operator_verified"] != 1:
            raise ValueError("corporate action operator verification is invalid")
        applied = row["applied_at"] is not None
        return ForwardCorporateAction(
            id=row["id"],
            session_id=row["session_id"],
            symbol=row["symbol"],
            exchange=row["exchange"],
            numerator=row["numerator"],
            denominator=row["denominator"],
            factor=row["factor"],
            source_url=row["source_url"],
            evidence_id=row["evidence_id"],
            evidence_sha256=row["evidence_sha256"],
            operator_verified=True,
            observed_at=row["observed_at"],
            effective_at=row["effective_at"],
            registered_at=row["registered_at"],
            applied_at=row["applied_at"],
            before_quantity=row["before_quantity"],
            after_quantity=row["after_quantity"],
            state=(
                "applied" if applied else "blocked" if blocked_reason else "registered"
            ),
            blocked_reason=blocked_reason,
        )

    def ledger(self, session_id: str) -> ForwardLedger:
        session = self.active_session()
        if session is None or session.id != session_id:
            raise KeyError(session_id)
        return ForwardLedger(
            session=session,
            cash_krw=session.cash_krw,
            positions=self.positions(session_id),
            fills=self.fills(session_id),
            valuated_equity_krw=None,
            valuation_at=None,
            fx_proxy_observed_on=None,
            limitations=[
                "가상 정수 수량 전량 체결이며 부분 체결과 시장 충격을 "
                "재현하지 않습니다.",
                "USD 환산은 일별 USD/KRW 대용치를 사용하며 "
                "실시간 환전 호가가 아닙니다.",
                "실제 브로커 주문을 생성하거나 전송하지 않습니다.",
                "서로 다른 시장의 비동시 체결과 매도 비용으로 다른 보유 비중이 "
                "일시적으로 한도를 넘으면 지연 한도 이벤트로 기록합니다.",
            ],
        )

    def ledger_asof(
        self, session_id: str, at: datetime
    ) -> tuple[Decimal, dict[str, int]] | None:
        """Replay persisted fills effective by a checkpoint, excluding later rows."""
        if at.tzinfo is None:
            raise ValueError("Ledger replay timestamp must be timezone-aware.")
        session = self.active_session()
        if session is None or session.id != session_id:
            raise KeyError(session_id)
        cutoff = at.astimezone(UTC).isoformat()
        with self._connect() as connection:
            legacy = connection.execute(
                """SELECT 1 FROM forward_corporate_actions legacy
                LEFT JOIN forward_corporate_action_metadata metadata
                    ON metadata.id=legacy.action_key
                    AND metadata.session_id=legacy.session_id
                    AND metadata.symbol=legacy.symbol
                LEFT JOIN forward_corporate_action_applications application
                    ON application.action_id=metadata.id
                WHERE legacy.session_id=?
                    AND (metadata.id IS NULL OR application.action_id IS NULL)
                LIMIT 1""",
                (session_id,),
            ).fetchone()
            if legacy is not None:
                return None
            fills = connection.execute(
                """SELECT id, received_at, payload_json FROM forward_fills
                WHERE session_id=? AND received_at<=?""",
                (session_id, cutoff),
            ).fetchall()
            splits = connection.execute(
                """SELECT m.id, m.symbol, m.factor, m.effective_at,
                    a.before_quantity, a.after_quantity
                FROM forward_corporate_action_metadata m
                LEFT JOIN forward_corporate_action_applications a
                    ON a.action_id=m.id
                WHERE m.session_id=? AND m.effective_at<=?""",
                (session_id, cutoff),
            ).fetchall()
        if any(row["before_quantity"] is None for row in splits):
            return None
        cash = session.config.initial_cash_krw
        positions: dict[str, int] = {}
        events: list[tuple[str, int, str, sqlite3.Row]] = [
            (str(row["received_at"]), 1, str(row["id"]), row) for row in fills
        ] + [(str(row["effective_at"]), 0, str(row["id"]), row) for row in splits]
        for _timestamp, kind, _identity, row in sorted(events):
            if kind == 0:
                before = positions.get(str(row["symbol"]), 0)
                after = before * int(row["factor"])
                if before != int(row["before_quantity"]) or after != int(
                    row["after_quantity"]
                ):
                    raise ValueError("Persisted split ledger is inconsistent.")
                positions[str(row["symbol"])] = after
                continue
            fill = ForwardFill.model_validate_json(row["payload_json"])
            current = positions.get(fill.symbol, 0)
            if fill.side == "buy":
                cash -= fill.notional_krw + fill.transaction_cost_krw + fill.fx_cost_krw
                positions[fill.symbol] = current + fill.quantity
            else:
                cash += fill.notional_krw - fill.transaction_cost_krw - fill.fx_cost_krw
                positions[fill.symbol] = current - fill.quantity
            if cash < 0 or positions[fill.symbol] < 0:
                raise ValueError("Persisted forward ledger cannot be replayed safely.")
        return cash, positions

    def apply_due_corporate_actions(
        self, session_id: str, applied_at: datetime
    ) -> list[ForwardCorporateAction]:
        if applied_at.tzinfo is None:
            raise ValueError("Corporate action timestamps must be timezone-aware.")
        current = applied_at.astimezone(UTC)
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT id FROM forward_corporate_action_metadata
                WHERE session_id=? AND effective_at<=?
                ORDER BY effective_at, id""",
                (session_id, current.isoformat()),
            ).fetchall()
        results: list[ForwardCorporateAction] = []
        for row in rows:
            action_id = str(row["id"])
            self._apply_registered_split(action_id, current)
            results.append(self.corporate_action(action_id, current))
        return results

    def _apply_registered_split(self, action_id: str, applied_at: datetime) -> bool:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """SELECT m.*, a.applied_at
                FROM forward_corporate_action_metadata m
                LEFT JOIN forward_corporate_action_applications a
                    ON a.action_id=m.id
                WHERE m.id=?""",
                (action_id,),
            ).fetchone()
            if row is None:
                raise KeyError(action_id)
            if row["applied_at"] is not None:
                return False
            effective = datetime.fromisoformat(row["effective_at"]).astimezone(UTC)
            observed = datetime.fromisoformat(row["observed_at"]).astimezone(UTC)
            registered = datetime.fromisoformat(row["registered_at"]).astimezone(UTC)
            if effective > applied_at:
                return False
            if observed > registered or registered > effective:
                raise ValueError("Corporate action verification was not timely.")
            blocked = self._corporate_action_block_reason(connection, row, applied_at)
            if blocked is not None:
                return False
            position = connection.execute(
                """SELECT quantity, average_cost_krw FROM forward_positions
                WHERE session_id=? AND symbol=?""",
                (row["session_id"], row["symbol"]),
            ).fetchone()
            before_quantity = int(position["quantity"]) if position is not None else 0
            before_average_cost = (
                Decimal(position["average_cost_krw"])
                if position is not None
                else Decimal()
            )
            factor = int(row["factor"])
            after_quantity = before_quantity * factor
            with localcontext() as context:
                context.prec = 40
                after_average_cost = (
                    before_average_cost / factor if before_quantity > 0 else Decimal()
                )
            if position is not None:
                connection.execute(
                    """UPDATE forward_positions
                    SET quantity=?, average_cost_krw=?, updated_at=?
                    WHERE session_id=? AND symbol=?""",
                    (
                        after_quantity,
                        str(after_average_cost),
                        applied_at.isoformat(),
                        row["session_id"],
                        row["symbol"],
                    ),
                )
            connection.execute(
                "INSERT INTO forward_corporate_actions VALUES (?, ?, ?, ?)",
                (row["session_id"], row["symbol"], action_id, applied_at.isoformat()),
            )
            connection.execute(
                """INSERT INTO forward_corporate_action_applications VALUES
                (?, ?, ?, ?, ?, ?)""",
                (
                    action_id,
                    applied_at.isoformat(),
                    before_quantity,
                    after_quantity,
                    str(before_average_cost),
                    str(after_average_cost),
                ),
            )
            self._insert_event(
                connection,
                row["session_id"],
                applied_at,
                "corporate_action",
                "검증된 정수 정방향 분할을 PAPER 원장에 반영했습니다.",
                action_id,
            )
        return True

    def split_is_applied(
        self,
        session_id: str,
        symbol: str,
        effective_at: datetime,
        factor: int,
    ) -> bool:
        with self._connect() as connection:
            return (
                connection.execute(
                    """SELECT 1 FROM forward_corporate_action_metadata m
                    JOIN forward_corporate_action_applications a ON a.action_id=m.id
                    WHERE m.session_id=? AND m.symbol=? AND m.effective_at=?
                        AND m.factor=? LIMIT 1""",
                    (
                        session_id,
                        symbol,
                        effective_at.astimezone(UTC).isoformat(),
                        factor,
                    ),
                ).fetchone()
                is not None
            )

    def quote_is_post_split(
        self, session_id: str, symbol: str, market_at: datetime
    ) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT m.effective_at
                FROM forward_corporate_action_metadata m
                JOIN forward_corporate_action_applications a ON a.action_id=m.id
                WHERE m.session_id=? AND m.symbol=?
                ORDER BY m.effective_at DESC LIMIT 1""",
                (session_id, symbol),
            ).fetchone()
        return row is None or market_at.astimezone(UTC) >= datetime.fromisoformat(
            row["effective_at"]
        ).astimezone(UTC)

    def apply_split(
        self,
        session_id: str,
        symbol: str,
        action_key: str,
        numerator: int,
        denominator: int,
        applied_at: datetime,
    ) -> bool:
        if numerator <= 0 or denominator <= 0:
            raise ValueError("Split factors must be positive.")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                """SELECT 1 FROM forward_corporate_actions
                WHERE session_id=? AND symbol=? AND action_key=?""",
                (session_id, symbol, action_key),
            ).fetchone()
            if existing:
                return False
            position = connection.execute(
                """SELECT quantity FROM forward_positions
                WHERE session_id=? AND symbol=?""",
                (session_id, symbol),
            ).fetchone()
            if position is None:
                raise ValueError("Corporate action symbol is not held.")
            before = int(position["quantity"])
            scaled = before * numerator
            if scaled % denominator:
                raise ValueError(
                    "Ambiguous fractional split is blocked pending review."
                )
            connection.execute(
                """UPDATE forward_positions SET quantity=?, updated_at=?
                WHERE session_id=? AND symbol=?""",
                (
                    scaled // denominator,
                    applied_at.astimezone(UTC).isoformat(),
                    session_id,
                    symbol,
                ),
            )
            connection.execute(
                "INSERT INTO forward_corporate_actions VALUES (?, ?, ?, ?)",
                (
                    session_id,
                    symbol,
                    action_key,
                    applied_at.astimezone(UTC).isoformat(),
                ),
            )
            self._insert_event(
                connection,
                session_id,
                applied_at,
                "corporate_action",
                "확인된 정수 분할을 원장에 한 번 반영했습니다.",
                action_key,
            )
        return True

    @staticmethod
    def _insert_event(
        connection: sqlite3.Connection,
        session_id: str,
        occurred_at: datetime,
        kind: str,
        detail: str,
        reference_id: str | None,
    ) -> None:
        event_id = _hash(
            {"session": session_id, "kind": kind, "reference": reference_id}
        )
        connection.execute(
            "INSERT OR IGNORE INTO forward_events VALUES (?, ?, ?, ?, ?, ?)",
            (
                event_id,
                session_id,
                occurred_at.astimezone(UTC).isoformat(),
                kind,
                detail,
                reference_id,
            ),
        )
