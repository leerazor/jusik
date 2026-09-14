from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Market = Literal["KR", "US"]
Currency = Literal["KRW", "USD"]
InstrumentType = Literal["stock", "etf", "unknown"]
EntryKind = Literal["value", "trend"]
ThesisState = Literal["watch", "holding", "closed"]
ThesisHealth = Literal["intact", "broken", "unknown"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Instrument(StrictModel):
    market: Market
    exchange: str = Field(min_length=1, max_length=12)
    symbol: str = Field(min_length=1, max_length=16)
    currency: Currency
    name: str = Field(min_length=1, max_length=120)
    instrument_type: InstrumentType = "unknown"

    @field_validator("exchange", "symbol")
    @classmethod
    def safe_code(cls, value: str) -> str:
        if not value.replace("-", "").replace(".", "").isalnum():
            raise ValueError("코드는 영문·숫자와 제한된 기호만 사용할 수 있습니다.")
        return value.upper()

    @model_validator(mode="after")
    def currency_matches_market(self) -> "Instrument":
        expected = "KRW" if self.market == "KR" else "USD"
        if self.currency != expected:
            raise ValueError("시장과 통화가 일치하지 않습니다.")
        return self


class Candidate(StrictModel):
    instrument: Instrument
    rank: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=240)
    source: str = Field(min_length=1, max_length=120)
    observed_at: datetime


class DiscoveryResult(StrictModel):
    market: Market
    candidates: list[Candidate]
    coverage: str = Field(min_length=1, max_length=240)
    truncated: bool
    partial: bool = False
    errors: list[str] = Field(default_factory=list, max_length=10)
    fetched_at: datetime


class QuoteFact(StrictModel):
    price: Decimal | None = Field(default=None, allow_inf_nan=False)
    currency: Currency
    as_of: datetime | None = None
    fetched_at: datetime
    source: str
    unavailable_reason: str | None = Field(default=None, max_length=240)

    @field_validator("price")
    @classmethod
    def positive_price(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and value <= 0:
            raise ValueError("가격은 양수여야 합니다.")
        return value


class FundamentalFacts(StrictModel):
    eps: Decimal | None = Field(default=None, allow_inf_nan=False)
    eps_period: str | None = Field(default=None, max_length=32)
    per: Decimal | None = Field(default=None, allow_inf_nan=False)
    pbr: Decimal | None = Field(default=None, allow_inf_nan=False)
    growth: Decimal | None = Field(default=None, allow_inf_nan=False)
    roe: Decimal | None = Field(default=None, allow_inf_nan=False)
    debt_ratio: Decimal | None = Field(default=None, allow_inf_nan=False)
    period_end: date | None = None
    source: str | None = None
    fetched_at: datetime | None = None
    unavailable_reasons: list[str] = Field(default_factory=list, max_length=12)


class DailyBar(StrictModel):
    session: date
    close: Decimal = Field(gt=0, allow_inf_nan=False)
    volume: Decimal = Field(ge=0, allow_inf_nan=False)
    adjusted: bool


class TrendFacts(StrictModel):
    breakout_observed: bool | None = None
    deterioration_observed: bool | None = None
    latest_completed_session: date | None = None
    rule_version: str = "breakout20_sma20_v1"
    source: str | None = None
    unavailable_reasons: list[str] = Field(default_factory=list, max_length=12)


class AnalysisResult(StrictModel):
    instrument: Instrument
    quote: QuoteFact
    fundamentals: FundamentalFacts
    trend: TrendFacts
    entry_kind: EntryKind
    value_entry_status: Literal["review", "unassessed", "exit_review"]
    trend_entry_status: Literal["review", "unassessed", "exit_review"]
    assumed_value_lower: Decimal | None = Field(default=None, allow_inf_nan=False)
    assumed_value_upper: Decimal | None = Field(default=None, allow_inf_nan=False)
    assumed_safety_price: Decimal | None = Field(default=None, allow_inf_nan=False)
    reasons: list[str] = Field(default_factory=list, max_length=30)
    rule_version: str = "investor_analysis_v1"
    analyzed_at: datetime


class ThesisReview(StrictModel):
    decision: Literal["hold_review", "exit_review", "deferred", "closed"]
    reasons: list[str] = Field(default_factory=list, max_length=12)
    review_overdue: bool


class ValuationAssumptions(StrictModel):
    normalized_eps: Decimal | None = Field(default=None, gt=0, allow_inf_nan=False)
    eps_period: str | None = Field(default=None, max_length=32)
    target_pe_lower: Decimal | None = Field(default=None, gt=0, allow_inf_nan=False)
    target_pe_upper: Decimal | None = Field(default=None, gt=0, allow_inf_nan=False)
    margin_of_safety: Decimal | None = Field(
        default=None, ge=0, lt=1, allow_inf_nan=False
    )
    rationale: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def ordered_range(self) -> "ValuationAssumptions":
        if self.target_pe_lower is not None and self.target_pe_upper is not None:
            if self.target_pe_lower > self.target_pe_upper:
                raise ValueError("목표 PER 범위가 올바르지 않습니다.")
        if (self.normalized_eps is None) != (self.eps_period is None):
            raise ValueError("정규화 EPS와 EPS 기간을 함께 입력하세요.")
        complete = all(
            value is not None
            for value in (
                self.normalized_eps,
                self.target_pe_lower,
                self.target_pe_upper,
                self.margin_of_safety,
            )
        )
        if complete and not self.rationale:
            raise ValueError("완전한 가치 가정에는 근거를 작성해야 합니다.")
        return self


class ThesisWrite(StrictModel):
    instrument: Instrument
    state: ThesisState
    entry_kind: EntryKind
    why: str = Field(min_length=1, max_length=2000)
    source_references: list[str] = Field(default_factory=list, max_length=12)
    invalidation_criteria: str = Field(min_length=1, max_length=1000)
    next_review: date
    health: ThesisHealth
    risk_price: Decimal | None = Field(default=None, gt=0, allow_inf_nan=False)
    valuation: ValuationAssumptions | None = None
    expected_revision: int = Field(ge=0)


class Thesis(StrictModel):
    instrument: Instrument
    state: ThesisState
    entry_kind: EntryKind
    why: str = Field(min_length=1, max_length=2000)
    source_references: list[str] = Field(default_factory=list, max_length=12)
    invalidation_criteria: str = Field(min_length=1, max_length=1000)
    next_review: date
    health: ThesisHealth
    risk_price: Decimal | None = Field(default=None, gt=0, allow_inf_nan=False)
    valuation: ValuationAssumptions | None = None
    id: str
    revision: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime
    evidence: AnalysisResult
    review: ThesisReview = Field(
        default_factory=lambda: ThesisReview(
            decision="deferred", reasons=[], review_overdue=False
        )
    )


class InstrumentDetail(StrictModel):
    instrument: Instrument
    analysis: AnalysisResult
    limitations: list[str] = Field(default_factory=list, max_length=20)
