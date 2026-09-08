from datetime import UTC, datetime, timedelta
from datetime import date as Date
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
    model_validator,
)

DEFAULT_SYMBOLS = ("005930", "000660")
ENGINE_VERSION = "daily_shared_cash_v1"
BASELINE_VERSION = "trend_20_v1"
CANDIDATE_VERSION = "trend_20_60_v1"

Money = Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
Rate = Annotated[Decimal, Field(ge=0, le=Decimal("0.1"), allow_inf_nan=False)]
Price = Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]


class MarketEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["circuit_breaker", "sidecar"]
    market: Literal["KOSPI", "KOSDAQ"]
    direction: Literal["up", "down"] | None = None
    stage: int | None = Field(default=None, ge=1, le=3)
    occurred_at: datetime
    known_at: datetime
    resumed_at: datetime | None = None
    source_url: HttpUrl

    @field_validator("occurred_at", "known_at", "resumed_at")
    @classmethod
    def require_aware_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("Market event timestamps must include a timezone.")
        return value

    @model_validator(mode="after")
    def validate_timeline(self) -> Self:
        if self.known_at < self.occurred_at:
            raise ValueError("known_at must not precede occurred_at.")
        if self.resumed_at is not None and self.resumed_at < self.occurred_at:
            raise ValueError("resumed_at must not precede occurred_at.")
        if self.kind == "sidecar" and self.stage is not None:
            raise ValueError("Sidecar events do not have circuit-breaker stages.")
        return self


class ResearchRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbols: list[str] = Field(
        default_factory=lambda: list(DEFAULT_SYMBOLS),
        min_length=1,
        max_length=10,
        validate_default=True,
    )
    start_date: Date
    end_date: Date
    initial_cash: Money = Decimal("100000000")
    fee_rate: Rate = Decimal("0.00015")
    slippage_rate: Rate = Decimal("0.001")
    sell_tax_rate: Rate = Decimal("0.0018")
    events: list[MarketEvent] = Field(default_factory=list, max_length=100)

    @field_validator("symbols")
    @classmethod
    def normalize_symbols(cls, symbols: list[str]) -> list[str]:
        normalized: list[str] = []
        for symbol in symbols:
            value = symbol.strip()
            if len(value) != 6 or not value.isascii() or not value.isdigit():
                raise ValueError("Domestic stock symbols must contain 6 digits.")
            if value not in normalized:
                normalized.append(value)
        if not normalized:
            raise ValueError("At least one domestic stock symbol is required.")
        return normalized

    @model_validator(mode="after")
    def validate_period(self) -> Self:
        if self.end_date < self.start_date:
            raise ValueError("end_date must not precede start_date.")
        if self.end_date - self.start_date > timedelta(days=1096):
            raise ValueError("Research periods may not exceed three years.")
        return self


class DailyBar(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    date: Date
    open: Price
    high: Price
    low: Price
    close: Price
    volume: Annotated[int, Field(ge=0)]
    adjusted_open: Price
    adjusted_high: Price
    adjusted_low: Price
    adjusted_close: Price

    @model_validator(mode="after")
    def validate_ohlc(self) -> Self:
        if self.low > min(self.open, self.close) or self.high < max(
            self.open, self.close
        ):
            raise ValueError("Open and close must be within the daily range.")
        if self.low > self.high:
            raise ValueError("Daily low must not exceed daily high.")
        if self.adjusted_low > min(self.adjusted_open, self.adjusted_close):
            raise ValueError("Adjusted open and close must be within the daily range.")
        if self.adjusted_high < max(self.adjusted_open, self.adjusted_close):
            raise ValueError("Adjusted open and close must be within the daily range.")
        if self.adjusted_low > self.adjusted_high:
            raise ValueError("Adjusted daily low must not exceed daily high.")
        return self


class SymbolSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: str
    market: Literal["KOSPI", "KOSDAQ", "UNKNOWN"]
    bars: list[DailyBar]
    source: Literal["KIS paper daily chart"] = "KIS paper daily chart"
    source_url: str


class SymbolMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: Annotated[str, Field(pattern=r"^[0-9]{6}$")]
    name: str = Field(min_length=1, max_length=80)
    updated_at: datetime

    @field_validator("name")
    @classmethod
    def valid_display_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or not normalized.isprintable():
            raise ValueError("Symbol name must be printable.")
        return normalized

    @field_validator("updated_at")
    @classmethod
    def aware_updated_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Symbol metadata timestamp must include a timezone.")
        return value


class ResearchInputSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    captured_at: datetime
    requested_start: Date
    requested_end: Date
    symbols: list[SymbolSnapshot]
    events: list[MarketEvent]


class DataCoverage(BaseModel):
    symbol: str
    first_date: Date
    last_date: Date
    bars: int
    warmup_bars: int
    missing_vs_union_dates: int = Field(
        validation_alias=AliasChoices(
            "missing_vs_union_dates", "missing_comparison_dates"
        )
    )
    missing_expected_sessions: int | None = None


class EngineSpecification(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    engine_version: Literal["daily_shared_cash_v1"] = "daily_shared_cash_v1"
    baseline_version: Literal["trend_20_v1"] = "trend_20_v1"
    candidate_version: Literal["trend_20_60_v1"] = "trend_20_60_v1"
    signal_price: Literal["adjusted_close"] = "adjusted_close"
    signal_windows: tuple[int, int] = (20, 60)
    warmup_bars: Literal[60] = 60
    signal_timing: Literal["close_then_next_available_open"] = (
        "close_then_next_available_open"
    )
    execution_price: Literal["raw_open_with_symmetric_slippage"] = (
        "raw_open_with_symmetric_slippage"
    )
    cash_model: Literal["shared_long_only"] = "shared_long_only"
    allocation: Literal["inverse_universe_equal_cap"] = "inverse_universe_equal_cap"
    order_priority: Literal["sells_then_symbol_sorted_buys"] = (
        "sells_then_symbol_sorted_buys"
    )
    quantity_rounding: Literal["integer_floor"] = "integer_floor"
    decimal_precision: Literal[40] = 40
    decimal_rounding: Literal["ROUND_HALF_EVEN"] = "ROUND_HALF_EVEN"
    final_valuation: Literal["raw_close_without_forced_liquidation"] = (
        "raw_close_without_forced_liquidation"
    )
    event_policy: Literal["matching_board_known_event_defer_once"] = (
        "matching_board_known_event_defer_once"
    )


class Trade(BaseModel):
    date: Date
    signal_date: Date
    symbol: str
    side: Literal["buy", "sell"]
    quantity: int = Field(gt=0)
    market_open: Money
    execution_price: Money
    notional: Money
    fee: Money
    tax: Money
    rationale: str


class EquityPoint(BaseModel):
    date: Date
    equity: Money
    cash: Money


class AffectedDecision(BaseModel):
    date: Date
    symbol: str
    event_kind: Literal["circuit_breaker", "sidecar"]
    action: Literal["entry_deferred"]
    reason: str
    source_url: str


class UnfilledDecision(BaseModel):
    date: Date
    symbol: str
    side: Literal["buy", "sell"]
    reason: str


class StrategyMetrics(BaseModel):
    initial_cash: Money
    final_equity: Money
    total_return_pct: Decimal = Field(allow_inf_nan=False)
    max_drawdown_pct: Decimal = Field(ge=0, allow_inf_nan=False)
    trade_count: int = Field(ge=0)
    total_fees: Money
    total_tax: Money
    total_slippage_cost: Money


class StrategyResult(BaseModel):
    strategy_version: str
    definition: str
    metrics: StrategyMetrics
    trades: list[Trade]
    equity: list[EquityPoint]
    affected_decisions: list[AffectedDecision]
    unfilled_decisions: list[UnfilledDecision]
    open_positions: dict[str, int]


class ValidationComparison(BaseModel):
    training_start: Date
    training_end: Date
    testing_start: Date
    testing_end: Date
    testing_initial_cash: Money
    training_baseline: StrategyMetrics
    training_candidate: StrategyMetrics
    baseline: StrategyMetrics
    candidate: StrategyMetrics
    recommended_version: str
    candidate_passed: bool
    reason: str


class BacktestResult(BaseModel):
    engine_version: Literal["daily_shared_cash_v1"] = "daily_shared_cash_v1"
    baseline: StrategyResult
    candidate: StrategyResult
    coverage: list[DataCoverage]
    coverage_status: Literal["common_sessions_unverified"] = (
        "common_sessions_unverified"
    )
    limitations: list[str]
    event_coverage: Literal["provided_partial", "unavailable"]
    input_hash: str
    parameters_hash: str
    specification: EngineSpecification | None = None
    implementation_hash: str | None = None
    live_promotion_eligible: Literal[False] = False
    validation: ValidationComparison | None = None


RunStatus = Literal[
    "queued", "collecting", "running", "completed", "insufficient", "failed"
]


class ResearchRun(BaseModel):
    id: str
    status: RunStatus
    request: ResearchRunRequest
    created_at: datetime
    updated_at: datetime
    replay_of: str | None = None
    input_hash: str | None = None
    input_snapshot: ResearchInputSnapshot | None = None
    result: BacktestResult | None = None
    error: str | None = None


class ResearchRunSummary(BaseModel):
    id: str
    status: RunStatus
    request: ResearchRunRequest
    created_at: datetime
    updated_at: datetime
    replay_of: str | None = None
    input_hash: str | None = None
    result: BacktestResult | None = None


def utc_now() -> datetime:
    return datetime.now(UTC)
