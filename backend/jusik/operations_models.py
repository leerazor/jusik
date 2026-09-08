from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from jusik.research_models import DEFAULT_SYMBOLS

Symbol = Annotated[str, Field(pattern=r"^[0-9]{6}$")]
PositiveMoney = Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
NonNegativeMoney = Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]


class UniverseUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbols: list[Symbol] = Field(min_length=1, max_length=10)

    @field_validator("symbols")
    @classmethod
    def unique_symbols(cls, symbols: list[str]) -> list[str]:
        result: list[str] = []
        for symbol in symbols:
            if symbol not in result:
                result.append(symbol)
        if len(result) != len(symbols):
            raise ValueError("Duplicate symbols are not allowed.")
        return result


class ResearchScheduleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool
    interval_hours: int = Field(ge=1, le=168)
    lookback_days: int = Field(ge=120, le=1096)


class ResearchSchedule(ResearchScheduleUpdate):
    next_run_at: datetime
    last_started_at: datetime | None = None
    last_run_id: str | None = None
    last_error: str | None = None


class StrategyDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str = Field(pattern=r"^[a-z0-9_]{3,48}$")
    name: str = Field(min_length=1, max_length=80)
    fast_window: int = Field(ge=5, le=120)
    slow_window: int | None = Field(default=None, ge=10, le=240)
    min_volume_ratio: Decimal | None = Field(
        default=None, ge=Decimal("0.5"), le=Decimal("3"), allow_inf_nan=False
    )
    definition: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_windows(self) -> Self:
        if self.slow_window is not None and self.fast_window >= self.slow_window:
            raise ValueError("slow_window must exceed fast_window.")
        return self


class StrategyVersionRecord(BaseModel):
    definition: StrategyDefinition
    created_at: datetime
    source: Literal["built_in", "openai_suggestion"]
    recommended: bool
    active_for_paper: bool
    reason: str
    last_run_id: str | None = None
    out_of_sample_return_pct: Decimal | None = None
    out_of_sample_max_drawdown_pct: Decimal | None = None
    passed: bool | None = None
    proposed_after_date: date | None = None
    provenance: dict[str, str] = Field(default_factory=dict)
    evaluation_start: date | None = None
    evaluation_end: date | None = None
    evaluation_run_id: str | None = None
    evaluation_input_hash: str | None = None
    evaluation_implementation_hash: str | None = None


class AiReservation(BaseModel):
    id: str
    max_output_tokens: int = Field(ge=1)
    reserved_tokens: int = Field(ge=1)


class ActivateStrategyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    mode: Literal["paper"] = "paper"


class StreamToggle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool


class AiStatus(BaseModel):
    enabled: bool
    configured: bool
    model: str | None
    daily_token_budget: int
    used_tokens_today: int
    last_run_at: datetime | None
    last_error: str | None
    last_analysis: str | None
    prompt_version: str


class Quote(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: Symbol
    price: PositiveMoney
    ask: PositiveMoney | None = None
    bid: PositiveMoney | None = None
    volume: int = Field(ge=0)
    accumulated_volume: int = Field(ge=0)
    market_at: datetime
    received_at: datetime
    source: Literal["KIS H0STCNT0"] = "KIS H0STCNT0"

    @field_validator("market_at", "received_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Quote timestamps must be timezone-aware.")
        return value


class StreamStatus(BaseModel):
    state: Literal["disabled", "connecting", "connected", "stale", "error"]
    detail: str
    configured: bool
    symbols: list[str]
    connected_at: datetime | None = None
    last_message_at: datetime | None = None
    reconnect_count: int = 0


class SignalProposalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: Symbol
    side: Literal["buy", "sell"]
    quantity: int = Field(gt=0, le=1_000_000)
    limit_price: PositiveMoney
    expires_in_seconds: int = Field(default=300, ge=15, le=3600)
    strategy_version: str
    signal_date: date
    source_run_id: str = "manual"
    signal_input_hash: str = "manual"
    reason: str = Field(min_length=1, max_length=1000)


class SignalProposal(BaseModel):
    id: str
    symbol: str
    side: Literal["buy", "sell"]
    quantity: int
    limit_price: PositiveMoney
    expires_at: datetime
    strategy_version: str
    signal_date: date
    source_run_id: str
    signal_input_hash: str
    reason: str
    status: Literal["pending", "approved", "rejected", "expired", "filled"]
    created_at: datetime
    decided_at: datetime | None = None
    decision_reason: str | None = None


class ProposalDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["approve", "reject"]
    reason: str | None = Field(default=None, max_length=500)
    expected_version: str
    execution_mode: Literal["paper"] = "paper"


class PaperFill(BaseModel):
    id: str
    proposal_id: str
    symbol: str
    side: Literal["buy", "sell"]
    quantity: int
    price: PositiveMoney
    notional: PositiveMoney
    fee: NonNegativeMoney
    tax: NonNegativeMoney
    filled_at: datetime
    execution: Literal["app_simulated"] = "app_simulated"


class PaperAccount(BaseModel):
    cash: NonNegativeMoney
    positions: dict[str, int]
    fills: list[PaperFill]
    updated_at: datetime


class ProposalDecisionResult(BaseModel):
    proposal: SignalProposal
    fill: PaperFill | None


class OperationsStatus(BaseModel):
    universe: list[str]
    schedule: ResearchSchedule
    versions: list[StrategyVersionRecord]
    stream: StreamStatus
    quotes: list[Quote]
    proposals: list[SignalProposal]
    paper_account: PaperAccount
    ai: AiStatus
    execution_mode: Literal["paper_only"] = "paper_only"
    warnings: list[str]


DEFAULT_UNIVERSE = list(DEFAULT_SYMBOLS)


def utc_now() -> datetime:
    return datetime.now(UTC)


def next_schedule_time(interval_hours: int, *, now: datetime | None = None) -> datetime:
    return (now or utc_now()) + timedelta(hours=interval_hours)
