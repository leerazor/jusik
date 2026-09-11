from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from jusik.research_quote_models import ResearchFeedStatus, ResearchQuote

ForwardState = Literal[
    "observing",
    "waiting_cadence",
    "decision_recorded",
    "awaiting_quotes",
    "completed",
    "partially_completed",
    "expired",
    "inputs_blocked",
    "risk_liquidation",
    "cooldown",
    "recovery_wait",
    "reentry_ready",
]


class ForwardConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    initial_cash_krw: Decimal = Field(default=Decimal("100000000"), gt=0)
    candidate_id: Literal["portfolio_inverse_volatility_fx_vix_v1"] = (
        "portfolio_inverse_volatility_fx_vix_v1"
    )
    method: Literal["inverse_volatility"] = "inverse_volatility"
    gate: Literal["fx_vix"] = "fx_vix"
    policy: Literal["low_turnover_combined"] = "low_turnover_combined"
    fee_rate: Decimal = Field(default=Decimal("0.001"), ge=0, lt=1)
    slippage_rate: Decimal = Field(default=Decimal("0.001"), ge=0, lt=1)
    fx_spread_rate: Decimal = Field(default=Decimal("0.001"), ge=0, lt=1)
    symbol_cap: Decimal = Field(default=Decimal("0.20"), gt=0, le=1)
    gross_cap: Decimal = Field(default=Decimal("0.60"), gt=0, le=1)
    leveraged_cap: Decimal = Field(default=Decimal("0.20"), gt=0, le=1)
    drawdown_limit: Decimal = Field(default=Decimal("0.10"), gt=0, lt=1)
    cadence_days: Literal[28] = 28
    normal_intent_expiry_days: Literal[7] = 7
    restart_catchup_minutes: Literal[15] = 15
    quote_fresh_seconds: Literal[15] = 15
    future_tolerance_seconds: Literal[2] = 2
    reentry_cooldown_days: Literal[28] = 28
    recovery_confirmations: Literal[2] = 2
    low_turnover_band: Decimal = Decimal("0.02")


class ForwardSession(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-f0-9]{64}$")
    activated_at: datetime
    next_due_at: datetime
    source_run_id: str
    policy_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    config: ForwardConfig
    state: ForwardState
    cash_krw: Decimal = Field(ge=0)
    lifetime_high_water_krw: Decimal = Field(gt=0)
    episode_high_water_krw: Decimal = Field(gt=0)
    liquidation_completed_at: datetime | None = None
    next_recovery_check_at: datetime | None = None
    recovery_confirmations: int = Field(default=0, ge=0)

    @field_validator("activated_at", "next_due_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Forward session timestamps must be timezone-aware.")
        return value


class ForwardObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-f0-9]{64}$")
    quote: ResearchQuote
    persisted_reason: Literal["minute_sample", "decision", "fill", "alert"]


class ForwardPosition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: str
    currency: Literal["KRW", "USD"]
    quantity: int = Field(ge=0)
    average_cost_krw: Decimal = Field(ge=0)
    updated_at: datetime


class ForwardIntent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: str
    side: Literal["buy", "sell"]
    target_weight: Decimal = Field(ge=0, le=1)
    budget_krw: Decimal = Field(ge=0)
    state: Literal["pending", "filled", "consumed", "expired", "blocked"]
    reason: str


class ForwardDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-f0-9]{64}$")
    session_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    due_at: datetime
    recorded_at: datetime
    input_version: str = Field(pattern=r"^[a-f0-9]{64}$")
    state: ForwardState
    reason: str
    expires_at: datetime | None
    target_weights: dict[str, Decimal]
    intents: list[ForwardIntent]
    volatility_proxy: Decimal | None = None
    volatility_scale: Decimal | None = None


class ForwardFill(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-f0-9]{64}$")
    session_id: str
    decision_id: str
    symbol: str
    side: Literal["buy", "sell"]
    quantity: int = Field(gt=0)
    market_at: datetime
    received_at: datetime
    local_price: Decimal = Field(gt=0)
    fx_rate: Decimal = Field(gt=0)
    notional_krw: Decimal = Field(gt=0)
    transaction_cost_krw: Decimal = Field(ge=0)
    fx_cost_krw: Decimal = Field(ge=0)
    cash_after_krw: Decimal = Field(ge=0)
    quote_id: str
    model: Literal["hypothetical_integer_full_fill"] = "hypothetical_integer_full_fill"


class ForwardLedger(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    session: ForwardSession
    cash_krw: Decimal = Field(ge=0)
    positions: list[ForwardPosition]
    fills: list[ForwardFill]
    valuated_equity_krw: Decimal | None
    valuation_at: datetime | None
    fx_proxy_observed_on: date | None
    limitations: list[str]


class ForwardEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-f0-9]{64}$")
    session_id: str
    occurred_at: datetime
    kind: Literal[
        "session_activated",
        "feed_state_changed",
        "decision_recorded",
        "fill_recorded",
        "intent_consumed",
        "intent_expired",
        "missed_restart",
        "missed_data",
        "risk_alert",
        "risk_exit",
        "liquidation_complete",
        "recovery_confirmation",
        "reentry_ready",
        "corporate_action_registered",
        "corporate_action",
        "corporate_action_blocked",
        "cap_constraint_deferred",
        "close_checkpoint",
        "worker_failure",
        "calendar_unavailable",
        "clock_sample",
    ]
    detail: str
    reference_id: str | None = None


class ForwardPreview(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    computed_at: datetime
    asof: datetime
    is_decision: Literal[False] = False
    target_weights: dict[str, Decimal]
    blocked_reason: str | None
    input_version: str | None


class ForwardWorkerFailure(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    channel: Literal["tick", "quote"]
    code: Literal["internal_error"] = "internal_error"
    occurred_at: datetime


class ForwardClockHealth(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    sample_id: str = Field(
        pattern=(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-"
            r"[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
        )
    )
    sampled_at: datetime
    source_measurement_at: None = None
    state: Literal["available", "unknown"]
    offset_ms: Decimal | None = Field(default=None, allow_inf_nan=False)
    delay_ms: Decimal | None = Field(default=None, ge=0, allow_inf_nan=False)
    jitter_ms: Decimal | None = Field(default=None, ge=0, allow_inf_nan=False)
    packet_count: int | None = Field(default=None, ge=0)
    synced: bool | None = None
    persisted: bool
    error_code: (
        Literal[
            "command_missing",
            "command_failed",
            "timeout",
            "output_oversize",
            "parse_error",
            "probe_failed",
            "persistence_failed",
        ]
        | None
    ) = None

    @field_validator("sampled_at")
    @classmethod
    def clock_sample_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Clock sample timestamp must be timezone-aware.")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def clock_sample_consistent(self) -> ForwardClockHealth:
        measurements = (self.offset_ms, self.delay_ms, self.jitter_ms)
        if self.state == "available":
            if self.offset_ms is None or self.error_code not in (
                None,
                "persistence_failed",
            ):
                raise ValueError("Available clock sample is inconsistent.")
        elif (
            any(value is not None for value in measurements) or self.error_code is None
        ):
            raise ValueError("Unknown clock sample is inconsistent.")
        return self


class ForwardCalendarExchangeStatus(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    calendar: Literal["XKRX", "XNYS"]
    phase: Literal["pre_open", "regular_session", "post_close", "closed", "unavailable"]
    local_date: date
    open_at: datetime | None
    close_at: datetime | None
    next_session_open_at: datetime | None
    next_session_close_at: datetime | None


class ForwardCalendarStatus(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    available: bool
    provider: Literal["exchange_calendars"] = "exchange_calendars"
    provider_version: str
    artifact_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    calendars_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    generated_at: datetime
    coverage_start: date
    coverage_end: date
    error_code: str | None
    exchanges: list[ForwardCalendarExchangeStatus]


class ForwardActionLimitations(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    dividends: Literal["excluded_cash_dividends"] = "excluded_cash_dividends"
    splits: Literal["verified_integer_forward_splits_only"] = (
        "verified_integer_forward_splits_only"
    )
    historical_calendar: Literal["not_converted"] = "not_converted"


class ForwardCorporateAction(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-f0-9]{64}$")
    session_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    symbol: str
    exchange: Literal["KRX", "NAS", "NYS", "AMS"]
    numerator: int = Field(gt=1)
    denominator: Literal[1] = 1
    factor: int = Field(gt=1)
    source_url: str = Field(pattern=r"^https://")
    evidence_id: str = Field(min_length=1, max_length=200)
    evidence_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    operator_verified: Literal[True] = True
    observed_at: datetime
    effective_at: datetime
    registered_at: datetime
    applied_at: datetime | None = None
    before_quantity: int | None = Field(default=None, ge=0)
    after_quantity: int | None = Field(default=None, ge=0)
    state: Literal["registered", "applied", "blocked"]
    blocked_reason: str | None = None

    @field_validator("observed_at", "effective_at", "registered_at", "applied_at")
    @classmethod
    def corporate_action_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("Corporate action timestamps must be timezone-aware.")
        return value


class ForwardStatus(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    session: ForwardSession
    feed: ResearchFeedStatus
    preview: ForwardPreview
    latest_decision: ForwardDecision | None
    blocked_reason: str | None
    worker_failures: list[ForwardWorkerFailure] = Field(default_factory=list)
    latest_clock_health: ForwardClockHealth | None = None
    calendar: ForwardCalendarStatus
    action_limitations: ForwardActionLimitations = Field(
        default_factory=ForwardActionLimitations
    )
    corporate_actions: list[ForwardCorporateAction] = Field(default_factory=list)
    paper_only: Literal[True] = True
    broker_orders_enabled: Literal[False] = False
    worker_interval_seconds: Literal[5] = 5


class ForwardPage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    items: list[ForwardObservation | ForwardDecision | ForwardFill | ForwardEvent]
    next_cursor: str | None
