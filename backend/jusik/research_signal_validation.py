from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Literal, Self, TypedDict
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from jusik.research_forward_models import ForwardDecision, ForwardFill
from jusik.research_market_calendar import MarketCalendar, load_market_calendar
from jusik.research_quote_models import ResearchFeedStatus, ResearchQuote
from jusik.research_universe_data import REGISTRY


class SignalGap(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    start_at: datetime
    end_at: datetime
    minutes: int = Field(gt=0)

    @field_validator("start_at", "end_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Signal validation timestamps must be aware.")
        return value.astimezone(UTC)


class SymbolSignalCoverage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: str
    exchange: str
    local_date: date
    session_state: Literal[
        "completed", "partial", "not_started", "closed", "unavailable"
    ]
    expected_completed_minutes: int = Field(ge=0)
    observed_completed_minutes: int = Field(ge=0)
    missing_minutes: int = Field(ge=0)
    persisted_rows: int = Field(ge=0)
    outside_regular_rows: int = Field(ge=0)
    incomplete_minute_rows: int = Field(ge=0)
    gaps: list[SignalGap]

    @model_validator(mode="after")
    def counts_reconcile(self) -> Self:
        if (
            self.observed_completed_minutes + self.missing_minutes
            != self.expected_completed_minutes
        ):
            raise ValueError("Signal minute coverage counts do not reconcile.")
        return self


class SignalLatency(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    sample_count: int = Field(ge=0)
    median_milliseconds: Decimal | None = Field(default=None, allow_inf_nan=False)
    p95_milliseconds: int | None = None
    maximum_milliseconds: int | None = None
    over_15_seconds_count: int = Field(ge=0)
    future_over_2_seconds_count: int = Field(ge=0)


class _SignalLatencyValues(TypedDict):
    sample_count: int
    median_milliseconds: Decimal | None
    p95_milliseconds: int | None
    maximum_milliseconds: int | None
    over_15_seconds_count: int
    future_over_2_seconds_count: int


class SymbolSignalLatency(SignalLatency):
    symbol: str
    exchange: str


class LatencyAnomaly(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    observation_id: str
    symbol: str
    exchange: str
    reason: str
    market_at: datetime
    received_at: datetime
    milliseconds: Decimal = Field(allow_inf_nan=False)
    kind: Literal["future", "stale"]

    @field_validator("market_at", "received_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Latency anomaly timestamps must be aware.")
        return value.astimezone(UTC)


class LatencyAnomalies(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    total_count: int = Field(ge=0)
    limit: Literal[50] = 50
    truncated: bool
    items: list[LatencyAnomaly] = Field(max_length=50)


class ExecutionQuoteEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    decision_id: str
    decision_due_at: datetime
    decision_recorded_at: datetime
    input_version: str
    input_cutoff_at: datetime | None
    decision_expires_at: datetime | None
    fill_id: str
    symbol: str
    side: Literal["buy", "sell"]
    quantity: int = Field(gt=0)
    fill_market_at: datetime
    fill_received_at: datetime
    fill_local_price: str
    quote_id: str
    evidence: Literal["captured", "legacy_sample_only", "missing", "mismatch"]
    execution_quote: ResearchQuote | None
    quote_sha256: str | None = None

    @field_validator(
        "decision_due_at",
        "decision_recorded_at",
        "input_cutoff_at",
        "decision_expires_at",
        "fill_market_at",
        "fill_received_at",
    )
    @classmethod
    def aware_optional(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("Execution evidence timestamps must be aware.")
        return value.astimezone(UTC) if value is not None else None


class DecisionEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    decision_id: str
    due_at: datetime
    recorded_at: datetime
    expires_at: datetime | None
    input_version: str
    input_cutoff_at: datetime | None
    state: str
    intent_count: int = Field(ge=0)
    pending_intent_count: int = Field(ge=0)
    fill_count: int = Field(ge=0)

    @field_validator("due_at", "recorded_at", "expires_at", "input_cutoff_at")
    @classmethod
    def aware_optional(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("Decision evidence timestamps must be aware.")
        return value.astimezone(UTC) if value is not None else None


class DurableFeedEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_count: int = Field(ge=0)
    first_event_at: datetime | None
    last_event_at: datetime | None


class SignalValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    generated_at: datetime
    session_id: str
    local_date: date
    coverage: list[SymbolSignalCoverage]
    latency: SignalLatency
    symbol_latency: list[SymbolSignalLatency]
    latency_anomalies: LatencyAnomalies
    decisions: list[DecisionEvidence]
    executions: list[ExecutionQuoteEvidence]
    durable_feed: DurableFeedEvidence
    current_feed: ResearchFeedStatus | None
    operational_evidence: Literal["captured_fills", "operational_unproven"]
    limitations: list[str]

    @field_validator("generated_at")
    @classmethod
    def aware_generated(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("generated_at must be aware.")
        return value.astimezone(UTC)


def latest_completed_signal_date(
    now: datetime, *, calendar: MarketCalendar | None = None
) -> date:
    current = now.astimezone(UTC)
    fixed_calendar = calendar or load_market_calendar()
    if not fixed_calendar.available:
        raise ValueError("Verified market calendar unavailable.")
    exchanges = {instrument.exchange for instrument in REGISTRY}
    for offset in range(8):
        candidate = current.date() - timedelta(days=offset)
        lookups = [fixed_calendar.lookup(exchange, candidate) for exchange in exchanges]
        if any(lookup.state == "unavailable" for lookup in lookups):
            raise ValueError("Verified market calendar date unavailable.")
        sessions = [lookup.session for lookup in lookups if lookup.session is not None]
        if sessions and all(session.close_at <= current for session in sessions):
            return candidate
    raise ValueError("No completed trading date is available in the latest seven days.")


def validate_signal_store(
    database: Path,
    *,
    local_date: date,
    now: datetime,
    current_feed: ResearchFeedStatus | None = None,
    calendar: MarketCalendar | None = None,
) -> SignalValidationResult:
    current = now.astimezone(UTC)
    latest_local_date = max(
        current.astimezone(ZoneInfo(instrument.timezone)).date()
        for instrument in REGISTRY
    )
    if local_date > latest_local_date or (latest_local_date - local_date).days > 7:
        raise ValueError(
            "Signal validation date must be within the latest seven local dates."
        )
    fixed_calendar = calendar or load_market_calendar()
    if not fixed_calendar.available:
        raise ValueError("Verified market calendar unavailable.")
    with sqlite3.connect(
        f"file:{database}?mode=ro", uri=True, timeout=0.1
    ) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("BEGIN")
        session = connection.execute(
            """SELECT id, activated_at FROM forward_sessions
            ORDER BY activated_at DESC LIMIT 1"""
        ).fetchone()
        if session is None:
            raise ValueError("Forward session unavailable.")
        session_id = str(session["id"])
        activated_at = datetime.fromisoformat(session["activated_at"]).astimezone(UTC)
        range_start = datetime.combine(
            local_date - timedelta(days=1), datetime.min.time(), UTC
        ).isoformat()
        range_end = datetime.combine(
            local_date + timedelta(days=2), datetime.min.time(), UTC
        ).isoformat()
        observation_rows = connection.execute(
            """SELECT id, symbol, reason, quote_json FROM forward_observations
            WHERE session_id=? AND market_at>=? AND market_at<? ORDER BY market_at""",
            (
                session_id,
                range_start,
                range_end,
            ),
        ).fetchall()
        listed_decision_rows = connection.execute(
            """SELECT * FROM forward_decisions
            WHERE session_id=? AND due_at>=? AND due_at<? ORDER BY due_at""",
            (session_id, range_start, range_end),
        ).fetchall()
        fill_rows = connection.execute(
            """SELECT payload_json FROM forward_fills
            WHERE session_id=? AND market_at>=? AND market_at<? ORDER BY received_at""",
            (session_id, range_start, range_end),
        ).fetchall()
        fill_models = [
            ForwardFill.model_validate_json(row["payload_json"]) for row in fill_rows
        ]
        relevant_fills = [
            fill for fill in fill_models if _fill_on_local_date(fill, local_date)
        ]
        listed_decision_ids = {str(row["id"]) for row in listed_decision_rows}
        referenced_decision_ids = {
            fill.decision_id for fill in relevant_fills
        } - listed_decision_ids
        referenced_decision_rows = (
            connection.execute(
                """SELECT * FROM forward_decisions
                WHERE session_id=? AND id IN ({})""".format(
                    ",".join("?" for _item in referenced_decision_ids)
                ),
                (session_id, *sorted(referenced_decision_ids)),
            ).fetchall()
            if referenced_decision_ids
            else []
        )
        all_decisions = [
            _decision(row) for row in (*listed_decision_rows, *referenced_decision_rows)
        ]
        decisions = [
            item
            for item in all_decisions
            if item.due_at.astimezone(UTC).date() == local_date
        ]
        input_ids = {item.input_version for item in all_decisions}
        input_rows = {
            str(row["id"]): datetime.fromisoformat(row["cutoff_at"]).astimezone(UTC)
            for row in connection.execute(
                """SELECT id, cutoff_at FROM forward_input_versions
                WHERE session_id=? AND id IN ({})""".format(
                    ",".join("?" for _item in input_ids) or "NULL"
                ),
                (session_id, *sorted(input_ids)),
            ).fetchall()
        }
        feed_rows = connection.execute(
            """SELECT occurred_at, detail FROM forward_events
            WHERE session_id=? AND kind='feed_state_changed' ORDER BY occurred_at""",
            (session_id,),
        ).fetchall()
        fill_ids = {item.id for item in relevant_fills}
        if (
            fill_ids
            and connection.execute(
                """SELECT 1 FROM sqlite_master
            WHERE type='table' AND name='forward_execution_quotes'"""
            ).fetchone()
        ):
            quote_rows = {
                str(row["fill_id"]): row
                for row in connection.execute(
                    (
                        "SELECT * FROM forward_execution_quotes WHERE fill_id IN ({})"
                    ).format(",".join("?" for _item in fill_ids)),
                    tuple(sorted(fill_ids)),
                ).fetchall()
            }
        else:
            quote_rows = {}
        observation_ids = {item.quote_id for item in relevant_fills}
        observation_by_id = (
            {
                str(row["id"]): row
                for row in connection.execute(
                    """SELECT id, quote_json FROM forward_observations
                    WHERE session_id=? AND id IN ({})""".format(
                        ",".join("?" for _item in observation_ids)
                    ),
                    (session_id, *sorted(observation_ids)),
                ).fetchall()
            }
            if observation_ids
            else {}
        )
    quotes_by_symbol: dict[str, list[tuple[str, ResearchQuote]]] = defaultdict(list)
    latencies: list[int] = []
    future_count = 0
    stale_count = 0
    symbol_latencies: dict[str, list[int]] = {
        instrument.symbol: [] for instrument in REGISTRY
    }
    symbol_future_count: dict[str, int] = defaultdict(int)
    symbol_stale_count: dict[str, int] = defaultdict(int)
    anomalies: list[LatencyAnomaly] = []
    instruments_by_symbol = {instrument.symbol: instrument for instrument in REGISTRY}
    for row in observation_rows:
        quote = ResearchQuote.model_validate_json(row["quote_json"])
        instrument = instruments_by_symbol.get(quote.symbol)
        if (
            instrument is None
            or quote.market_at.astimezone(ZoneInfo(instrument.timezone)).date()
            != local_date
        ):
            continue
        quotes_by_symbol[quote.symbol].append((str(row["reason"]), quote))
        lookup = fixed_calendar.lookup(instrument.exchange, local_date)
        if (
            lookup.session is not None
            and lookup.session.open_at
            <= quote.market_at.astimezone(UTC)
            < lookup.session.close_at
        ):
            raw_latency = quote.received_at.astimezone(
                UTC
            ) - quote.market_at.astimezone(UTC)
            latency_ms = round(raw_latency.total_seconds() * 1000)
            latencies.append(latency_ms)
            symbol_latencies[quote.symbol].append(latency_ms)
            is_future = raw_latency < -timedelta(seconds=2)
            is_stale = raw_latency > timedelta(seconds=15)
            future_count += is_future
            stale_count += is_stale
            symbol_future_count[quote.symbol] += is_future
            symbol_stale_count[quote.symbol] += is_stale
            if is_future or is_stale:
                anomalies.append(
                    LatencyAnomaly(
                        observation_id=row["id"],
                        symbol=quote.symbol,
                        exchange=instrument.exchange,
                        reason=row["reason"],
                        market_at=quote.market_at,
                        received_at=quote.received_at,
                        milliseconds=_exact_milliseconds(raw_latency),
                        kind="future" if is_future else "stale",
                    )
                )
    coverage = [
        _symbol_coverage(
            instrument.symbol,
            instrument.exchange,
            instrument.timezone,
            local_date,
            current,
            activated_at,
            quotes_by_symbol[instrument.symbol],
            fixed_calendar,
        )
        for instrument in REGISTRY
    ]
    symbol_latency = [
        SymbolSignalLatency(
            symbol=instrument.symbol,
            exchange=instrument.exchange,
            **_latency_values(
                symbol_latencies[instrument.symbol],
                symbol_future_count[instrument.symbol],
                symbol_stale_count[instrument.symbol],
            ),
        )
        for instrument in REGISTRY
    ]
    anomalies.sort(key=lambda item: (item.symbol, item.observation_id))
    anomalies.sort(key=lambda item: item.received_at, reverse=True)
    anomalies.sort(key=lambda item: item.market_at, reverse=True)
    decision_by_id = {item.id: item for item in all_decisions}
    executions = [
        _execution_evidence(
            fill,
            decision_by_id,
            input_rows,
            quote_rows,
            observation_by_id,
        )
        for fill in relevant_fills
    ]
    decision_evidence = [
        DecisionEvidence(
            decision_id=decision.id,
            due_at=decision.due_at,
            recorded_at=decision.recorded_at,
            expires_at=decision.expires_at,
            input_version=decision.input_version,
            input_cutoff_at=input_rows.get(decision.input_version),
            state=decision.state,
            intent_count=len(decision.intents),
            pending_intent_count=sum(
                intent.state == "pending" for intent in decision.intents
            ),
            fill_count=sum(fill.decision_id == decision.id for fill in relevant_fills),
        )
        for decision in decisions
    ]
    first_event = (
        datetime.fromisoformat(feed_rows[0]["occurred_at"]) if feed_rows else None
    )
    last_event = (
        datetime.fromisoformat(feed_rows[-1]["occurred_at"]) if feed_rows else None
    )
    return SignalValidationResult(
        generated_at=current,
        session_id=session_id,
        local_date=local_date,
        coverage=coverage,
        latency=SignalLatency(**_latency_values(latencies, future_count, stale_count)),
        symbol_latency=symbol_latency,
        latency_anomalies=LatencyAnomalies(
            total_count=len(anomalies),
            truncated=len(anomalies) > 50,
            items=anomalies[:50],
        ),
        decisions=decision_evidence,
        executions=executions,
        durable_feed=DurableFeedEvidence(
            event_count=len(feed_rows),
            first_event_at=first_event,
            last_event_at=last_event,
        ),
        current_feed=current_feed,
        operational_evidence=(
            "captured_fills"
            if any(item.evidence == "captured" for item in executions)
            else "operational_unproven"
        ),
        limitations=[
            "저장된 분 표본 수이며 전체 tick 수나 시세 가용성 SLA가 아닙니다.",
            (
                "미관측 분은 거래 공백, 저장 정책 또는 연결 상태를 "
                "구분해 확정하지 않습니다."
            ),
            (
                "현재 ACK·protocol counter는 현재 프로세스 연결 epoch이며 "
                "과거 일 누계가 아닙니다."
            ),
        ],
    )


def _symbol_coverage(
    symbol: str,
    exchange: str,
    timezone_name: str,
    local_date: date,
    now: datetime,
    activated_at: datetime,
    rows: list[tuple[str, ResearchQuote]],
    calendar: MarketCalendar,
) -> SymbolSignalCoverage:
    lookup = calendar.lookup(exchange, local_date)
    if lookup.session is None:
        state: Literal["closed", "unavailable"] = (
            "closed" if lookup.state == "closed" else "unavailable"
        )
        return SymbolSignalCoverage(
            symbol=symbol,
            exchange=exchange,
            local_date=local_date,
            session_state=state,
            expected_completed_minutes=0,
            observed_completed_minutes=0,
            missing_minutes=0,
            persisted_rows=len(rows),
            outside_regular_rows=len(rows),
            incomplete_minute_rows=0,
            gaps=[],
        )
    session = lookup.session
    first = max(session.open_at, _ceil_minute(activated_at))
    completed_end = min(session.close_at, _floor_minute(now))
    if completed_end <= first:
        expected: list[datetime] = []
    else:
        expected = [
            first + timedelta(minutes=index)
            for index in range(int((completed_end - first).total_seconds() // 60))
        ]
    expected_set = set(expected)
    observed: set[datetime] = set()
    outside = incomplete = 0
    deduplicated = {
        (
            quote.market_at.astimezone(UTC).replace(second=0, microsecond=0),
            reason,
        ): quote
        for reason, quote in rows
    }
    for (minute, _reason), quote in deduplicated.items():
        if not session.open_at <= quote.market_at.astimezone(UTC) < session.close_at:
            outside += 1
        elif minute not in expected_set:
            incomplete += 1
        else:
            observed.add(minute)
    missing = sorted(expected_set - observed)
    if now < session.open_at:
        session_state: Literal["completed", "partial", "not_started"] = "not_started"
    elif now < session.close_at:
        session_state = "partial"
    else:
        session_state = "completed"
    return SymbolSignalCoverage(
        symbol=symbol,
        exchange=exchange,
        local_date=local_date,
        session_state=session_state,
        expected_completed_minutes=len(expected),
        observed_completed_minutes=len(observed),
        missing_minutes=len(missing),
        persisted_rows=len(deduplicated),
        outside_regular_rows=outside,
        incomplete_minute_rows=incomplete,
        gaps=_gaps(missing),
    )


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
        intents=json.loads(row["intents_json"]),
        volatility_proxy=row["volatility_proxy"],
        volatility_scale=row["volatility_scale"],
    )


def _execution_evidence(
    fill: ForwardFill,
    decisions: dict[str, ForwardDecision],
    input_cutoffs: dict[str, datetime],
    sidecars: dict[str, sqlite3.Row],
    observations: dict[str, sqlite3.Row],
) -> ExecutionQuoteEvidence:
    decision = decisions.get(fill.decision_id)
    if decision is None:
        raise ValueError("Fill decision unavailable.")
    sidecar = sidecars.get(fill.id)
    quote: ResearchQuote | None = None
    digest: str | None = None
    if sidecar is not None:
        raw = str(sidecar["quote_json"])
        digest = hashlib.sha256(raw.encode()).hexdigest()
        try:
            quote = ResearchQuote.model_validate_json(raw)
        except ValueError:
            evidence: Literal[
                "captured", "legacy_sample_only", "missing", "mismatch"
            ] = "mismatch"
        else:
            evidence = (
                "captured"
                if digest == sidecar["quote_sha256"]
                and quote.symbol == fill.symbol
                and quote.market_at.astimezone(UTC) == fill.market_at.astimezone(UTC)
                and quote.received_at.astimezone(UTC)
                == fill.received_at.astimezone(UTC)
                and quote.received_at.astimezone(UTC)
                >= decision.recorded_at.astimezone(UTC)
                and (
                    decision.expires_at is None
                    or quote.received_at.astimezone(UTC)
                    <= decision.expires_at.astimezone(UTC)
                )
                else "mismatch"
            )
    else:
        sample = observations.get(fill.quote_id)
        if sample is None:
            evidence = "missing"
        else:
            try:
                quote = ResearchQuote.model_validate_json(sample["quote_json"])
            except ValueError:
                evidence = "mismatch"
            else:
                evidence = (
                    "legacy_sample_only" if quote.symbol == fill.symbol else "mismatch"
                )
    return ExecutionQuoteEvidence(
        decision_id=decision.id,
        decision_due_at=decision.due_at,
        decision_recorded_at=decision.recorded_at,
        input_version=decision.input_version,
        input_cutoff_at=input_cutoffs.get(decision.input_version),
        decision_expires_at=decision.expires_at,
        fill_id=fill.id,
        symbol=fill.symbol,
        side=fill.side,
        quantity=fill.quantity,
        fill_market_at=fill.market_at,
        fill_received_at=fill.received_at,
        fill_local_price=str(fill.local_price),
        quote_id=fill.quote_id,
        evidence=evidence,
        execution_quote=quote,
        quote_sha256=digest,
    )


def _fill_on_local_date(fill: ForwardFill, day: date) -> bool:
    instrument = next((item for item in REGISTRY if item.symbol == fill.symbol), None)
    return (
        instrument is not None
        and fill.market_at.astimezone(ZoneInfo(instrument.timezone)).date() == day
    )


def _percentile(values: list[int], quantile: float) -> int | None:
    if not values:
        return None
    return values[max(0, math.ceil(len(values) * quantile) - 1)]


def _latency_values(
    values: list[int], future_count: int, stale_count: int
) -> _SignalLatencyValues:
    ordered = sorted(values)
    return {
        "sample_count": len(ordered),
        "median_milliseconds": _median(ordered),
        "p95_milliseconds": _percentile(ordered, 0.95),
        "maximum_milliseconds": ordered[-1] if ordered else None,
        "over_15_seconds_count": stale_count,
        "future_over_2_seconds_count": future_count,
    }


def _exact_milliseconds(value: timedelta) -> Decimal:
    microseconds = (
        value.days * 24 * 60 * 60 + value.seconds
    ) * 1_000_000 + value.microseconds
    return Decimal(microseconds) / Decimal(1000)


def _median(values: list[int]) -> Decimal | None:
    if not values:
        return None
    middle = len(values) // 2
    if len(values) % 2:
        return Decimal(values[middle])
    return (Decimal(values[middle - 1]) + Decimal(values[middle])) / 2


def _floor_minute(value: datetime) -> datetime:
    return value.astimezone(UTC).replace(second=0, microsecond=0)


def _ceil_minute(value: datetime) -> datetime:
    floor = _floor_minute(value)
    return floor if value.astimezone(UTC) == floor else floor + timedelta(minutes=1)


def _gaps(minutes: list[datetime]) -> list[SignalGap]:
    if not minutes:
        return []
    result: list[SignalGap] = []
    start = previous = minutes[0]
    for minute in minutes[1:]:
        if minute != previous + timedelta(minutes=1):
            result.append(
                SignalGap(
                    start_at=start,
                    end_at=previous + timedelta(minutes=1),
                    minutes=int((previous - start).total_seconds() // 60) + 1,
                )
            )
            start = minute
        previous = minute
    result.append(
        SignalGap(
            start_at=start,
            end_at=previous + timedelta(minutes=1),
            minutes=int((previous - start).total_seconds() // 60) + 1,
        )
    )
    return result
