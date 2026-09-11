from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from jusik.research_external_models import ExternalFeatureSnapshot, ExternalSourceStatus
from jusik.research_universe_models import OfflineResearchSnapshot

PortfolioMethod = Literal["equal", "inverse_volatility", "momentum_top4"]
PortfolioGate = Literal["none", "rates", "fx_vix", "stress"]
PortfolioPolicy = Literal[
    "corrected_control",
    "reentry_only",
    "volatility_only",
    "combined",
    "low_turnover_combined",
]


class PortfolioCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    method: PortfolioMethod
    gate: PortfolioGate


class PortfolioInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    captured_at: datetime
    stock_snapshot_ids: dict[str, str]
    instruments: list[OfflineResearchSnapshot]
    external: ExternalFeatureSnapshot
    external_status: list[ExternalSourceStatus] = Field(default_factory=list)

    @field_validator("captured_at")
    @classmethod
    def require_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("captured_at must include a timezone.")
        return value

    @model_validator(mode="after")
    def validate_instruments(self) -> PortfolioInput:
        symbols = [item.instruments[0].symbol for item in self.instruments]
        if len(symbols) != len(set(symbols)):
            raise ValueError("Portfolio instruments must be unique.")
        if set(symbols) != set(self.stock_snapshot_ids):
            raise ValueError("Every portfolio instrument needs one snapshot id.")
        return self


class PortfolioConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    initial_cash_krw: Decimal = Field(default=Decimal("100000000"), gt=0)
    fee_rate: Decimal = Field(default=Decimal("0.001"), ge=0, lt=1)
    slippage_rate: Decimal = Field(default=Decimal("0.001"), ge=0, lt=1)
    fx_spread_rate: Decimal = Field(default=Decimal("0.001"), ge=0, lt=1)
    symbol_cap: Decimal = Field(default=Decimal("0.20"), gt=0, le=1)
    gross_cap: Decimal = Field(default=Decimal("0.60"), gt=0, le=1)
    leveraged_etf_cap: Decimal = Field(default=Decimal("0.20"), gt=0, le=1)
    drawdown_limit: Decimal = Field(default=Decimal("0.10"), gt=0, lt=1)
    warmup_sessions: int = Field(default=120, ge=2)
    validation_sessions: int = Field(default=40, ge=2)
    signal_window: int = Field(default=20, ge=2)
    volatility_window: int = Field(default=60, ge=2)
    momentum_window: int = Field(default=60, ge=2)
    correlation_window: int = Field(default=60, ge=2)
    external_max_age_days: int = Field(default=7, ge=0)
    reentry_cooldown_days: int = Field(default=28, ge=1)
    recovery_confirmations: int = Field(default=2, ge=1)
    recovery_minimum_assets: int = Field(default=2, ge=1)
    volatility_target: Decimal = Field(default=Decimal("0.10"), gt=0, le=1)
    volatility_annualization_sessions: int = Field(default=252, ge=2)
    low_turnover_weeks: int = Field(default=4, ge=1)
    low_turnover_band: Decimal = Field(default=Decimal("0.02"), ge=0, lt=1)

    @model_validator(mode="after")
    def validate_caps(self) -> PortfolioConfig:
        if self.symbol_cap > self.gross_cap:
            raise ValueError("symbol_cap must not exceed gross_cap.")
        if self.leveraged_etf_cap > self.gross_cap:
            raise ValueError("leveraged_etf_cap must not exceed gross_cap.")
        return self


class PortfolioTarget(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    decided_at: datetime
    symbol: str
    target_weight: Decimal
    actual_weight_after_open: Decimal | None = None


class PortfolioTrade(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    decided_at: datetime
    executed_at: datetime
    symbol: str
    side: Literal["buy", "sell"]
    quantity: int = Field(gt=0)
    local_price: Decimal = Field(gt=0)
    fx_rate: Decimal = Field(gt=0)
    notional_krw: Decimal = Field(gt=0)
    transaction_cost_krw: Decimal = Field(ge=0)
    fx_cost_krw: Decimal = Field(ge=0)


class PortfolioPosition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: str
    quantity: int = Field(ge=0)
    currency: Literal["KRW", "USD"]
    local_close: Decimal = Field(gt=0)
    fx_rate: Decimal = Field(gt=0)
    value_krw: Decimal = Field(ge=0)
    weight: Decimal = Field(ge=0)
    valued_at: datetime
    fx_observed_on: date | None


class PortfolioEquityPoint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    at: datetime
    equity_krw: Decimal = Field(ge=0)
    cash_krw: Decimal = Field(ge=0)
    drawdown_pct: Decimal = Field(ge=0)


class PortfolioPolicyEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    at: datetime
    kind: Literal[
        "risk_exit",
        "liquidation_complete",
        "recovery_confirmation",
        "recovery_reset",
        "reentry_ready",
        "reentry",
        "volatility_scale",
        "frequency_skip",
        "band_skip",
        "cap_constraint_deferred",
    ]
    detail: str
    value: Decimal | None = None


class PortfolioMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    initial_equity_krw: Decimal = Field(ge=0)
    final_equity_krw: Decimal = Field(ge=0)
    total_return_pct: Decimal
    max_drawdown_pct: Decimal = Field(ge=0)
    trade_count: int = Field(ge=0)
    transaction_cost_krw: Decimal = Field(ge=0)
    fx_cost_krw: Decimal = Field(ge=0)
    turnover_pct: Decimal = Field(ge=0)


class CandidateEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate: PortfolioCandidate
    metrics: PortfolioMetrics
    complete: bool
    incomplete_reasons: list[str]


class PortfolioSimulation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate: PortfolioCandidate
    period_start: date
    period_end: date
    metrics: PortfolioMetrics
    complete: bool
    incomplete_reasons: list[str]
    drawdown_latched: bool
    drawdown_latched_at: datetime | None
    equity: list[PortfolioEquityPoint]
    trades: list[PortfolioTrade]
    weekly_targets: list[PortfolioTarget]
    positions: list[PortfolioPosition]
    contributions_krw: dict[str, Decimal]
    split_cash_in_lieu_krw: dict[str, Decimal]
    overlap_diagnostics: dict[str, Decimal]
    policy: PortfolioPolicy = "corrected_control"
    policy_events: list[PortfolioPolicyEvent] = Field(default_factory=list)


class PortfolioMonthlyDiagnostics(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    trade_count: int = Field(ge=0)
    turnover_pct: Decimal = Field(ge=0)
    active: bool


class PortfolioPolicyDiagnostics(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    trading_utc_days: int = Field(ge=0)
    invested_days_pct: Decimal = Field(ge=0, le=100)
    monthly: list[PortfolioMonthlyDiagnostics]
    active_month_trade_average: Decimal = Field(ge=0)
    active_month_trade_maximum: int = Field(ge=0)
    reentry_count: int = Field(ge=0)
    exit_count: int = Field(ge=0)
    frequency_skip_count: int = Field(ge=0)
    band_skip_count: int = Field(ge=0)
    volatility_scale_event_count: int = Field(ge=0)


class PortfolioPolicyComparison(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    policy: PortfolioPolicy
    base: PortfolioSimulation
    cost_stress: PortfolioSimulation
    diagnostics: PortfolioPolicyDiagnostics


class PortfolioPolicyExperiment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    registered_at: datetime
    reference_run_id: str
    reference_input_hash: str
    fixed_candidate: PortfolioCandidate
    specification_hash: str
    evidence: Literal["retrospective_reused_historical_evaluation"] = (
        "retrospective_reused_historical_evaluation"
    )
    corrected_validation_candidate: PortfolioCandidate
    corrected_selection_changed: bool
    comparisons: list[PortfolioPolicyComparison]
    limitations: list[str]

    @model_validator(mode="after")
    def validate_comparisons(self) -> PortfolioPolicyExperiment:
        expected = {
            "corrected_control",
            "reentry_only",
            "volatility_only",
            "combined",
            "low_turnover_combined",
        }
        policies = [item.policy for item in self.comparisons]
        if len(policies) != len(expected) or set(policies) != expected:
            raise ValueError("Policy experiment must contain each fixed policy once.")
        for comparison in self.comparisons:
            if (
                comparison.base.policy != comparison.policy
                or comparison.cost_stress.policy != comparison.policy
            ):
                raise ValueError("Policy simulations must match their comparison.")
            if (
                comparison.base.candidate != self.fixed_candidate
                or comparison.cost_stress.candidate != self.fixed_candidate
            ):
                raise ValueError("Policy simulations must use the fixed candidate.")
        return self


class PortfolioRunResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    created_at: datetime
    status: Literal["completed"] = "completed"
    input_hash: str
    code_hash: str
    requested_start: date
    harmonized_end: date
    preparation_end: date
    validation_start: date
    validation_end: date
    heldout_start: date
    heldout_end: date
    selected_candidate: PortfolioCandidate
    validation: list[CandidateEvaluation]
    heldout: PortfolioSimulation
    cash_baseline: PortfolioMetrics
    equal_baseline: PortfolioSimulation
    cost_stress: PortfolioSimulation
    config: PortfolioConfig
    external_status: list[ExternalSourceStatus]
    evidence_class: Literal["reconstructed_historical_exploration"] = (
        "reconstructed_historical_exploration"
    )
    point_in_time_verified: Literal[False] = False
    prospective_validation_eligible: Literal[False] = False
    automatic_trading_eligible: Literal[False] = False
    limitations: list[str]
    artifacts: list[str]
    policy_experiment: PortfolioPolicyExperiment | None = None


class PortfolioRunStatus(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["idle", "running", "success", "error"]
    last_attempt_at: datetime | None = None
    last_success_at: datetime | None = None
    latest_run_id: str | None = None
    error_code: str | None = None
    latest_stale: bool = False
    external_status: list[ExternalSourceStatus] = Field(default_factory=list)
