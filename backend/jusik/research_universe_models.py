from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from jusik.research_models import (
    DailyBar,
    MarketEvent,
    Money,
    Rate,
    StrategyResult,
)

Currency = Literal["KRW", "USD"]
Exchange = Literal["KSC", "PCX", "NMS", "NGM", "NYQ"]


class ResearchInstrument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: str = Field(min_length=1, max_length=12)
    yahoo_symbol: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=100)
    currency: Currency
    exchange: Exchange
    timezone: Literal["Asia/Seoul", "America/New_York"]
    listed_on: date | None = None


class OfflineResearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    instrument: ResearchInstrument
    start_date: date
    end_date: date
    initial_cash: Money
    fee_rate: Rate = Decimal("0.001")
    slippage_rate: Rate = Decimal("0.001")
    sell_tax_rate: Rate = Decimal()
    events: list[MarketEvent] = Field(default_factory=list, max_length=0)

    @property
    def symbols(self) -> list[str]:
        return [self.instrument.symbol]

    @model_validator(mode="after")
    def validate_period(self) -> Self:
        if self.end_date < self.start_date:
            raise ValueError("end_date must not precede start_date.")
        if self.end_date - self.start_date > timedelta(days=1096):
            raise ValueError("Research periods may not exceed three years.")
        return self


class CorporateAction(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    date: date
    kind: Literal["split"] = "split"
    numerator: Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
    denominator: Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
    source: Literal["Yahoo chart"] = "Yahoo chart"

    @property
    def factor(self) -> Decimal:
        return self.numerator / self.denominator


class PriceAdjustmentFactor(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    date: date
    raw_factor: Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]


class DataProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    price_volume_source: Literal["Yahoo chart", "KIS paper daily chart"]
    corporate_action_source: Literal["Yahoo chart"] = "Yahoo chart"


class OfflineInstrumentSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    instrument: ResearchInstrument
    bars: list[DailyBar]
    provenance: DataProvenance
    source_url: str

    @property
    def symbol(self) -> str:
        return self.instrument.symbol

    @property
    def market(self) -> Literal["UNKNOWN"]:
        return "UNKNOWN"


class OfflineResearchSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    captured_at: datetime
    requested_start: date
    requested_end: date
    evaluation_start: date
    instruments: list[OfflineInstrumentSnapshot] = Field(min_length=1, max_length=1)
    basis_actions: list[CorporateAction] = Field(default_factory=list)
    corporate_actions: list[CorporateAction] = Field(default_factory=list)
    adjustment_factors: list[PriceAdjustmentFactor]
    price_basis: Literal[
        "reconstructed_contemporary_raw_ohlc_and_split_adjusted_signal_ohlc"
    ] = "reconstructed_contemporary_raw_ohlc_and_split_adjusted_signal_ohlc"
    volume_basis: Literal["provider_reported_unadjusted"] = (
        "provider_reported_unadjusted"
    )
    dividend_policy: Literal["excluded_price_return"] = "excluded_price_return"
    events: list[MarketEvent] = Field(default_factory=list, max_length=0)

    @property
    def symbols(self) -> list[OfflineInstrumentSnapshot]:
        return self.instruments

    @field_validator("captured_at")
    @classmethod
    def captured_at_is_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("captured_at must include a timezone.")
        return value

    @model_validator(mode="after")
    def validate_contents(self) -> Self:
        item = self.instruments[0]
        dates = [bar.date for bar in item.bars]
        if dates != sorted(dates) or len(dates) != len(set(dates)):
            raise ValueError("Offline daily bars must have unique sorted dates.")
        if not dates:
            raise ValueError("Offline snapshot must contain daily bars.")
        if self.evaluation_start < self.requested_start:
            raise ValueError("evaluation_start must not precede requested_start.")
        factors = {entry.date: entry.raw_factor for entry in self.adjustment_factors}
        if set(factors) != set(dates):
            raise ValueError("Every offline daily bar needs one adjustment factor.")
        basis_action_dates = {action.date for action in self.basis_actions}
        if len(basis_action_dates) != len(self.basis_actions):
            raise ValueError("Corporate action dates must be unique.")
        action_dates = {action.date for action in self.corporate_actions}
        if len(action_dates) != len(self.corporate_actions):
            raise ValueError("Execution corporate action dates must be unique.")
        if not action_dates.issubset(set(dates)):
            raise ValueError(
                "Corporate actions require a daily bar on the action date."
            )
        if not action_dates.issubset(basis_action_dates):
            raise ValueError("Execution actions must be present in basis actions.")
        actions_inside_bar_range = {
            action.date
            for action in self.basis_actions
            if dates[0] <= action.date <= dates[-1]
        }
        if action_dates != actions_inside_bar_range:
            raise ValueError(
                "Every corporate action inside the daily-bar range must be executed."
            )
        for bar in item.bars:
            factor = factors[bar.date]
            pairs = (
                (bar.open, bar.adjusted_open),
                (bar.high, bar.adjusted_high),
                (bar.low, bar.adjusted_low),
                (bar.close, bar.adjusted_close),
            )
            if any(
                abs(raw / adjusted - factor) > Decimal("0.000001")
                for raw, adjusted in pairs
            ):
                raise ValueError("Offline raw prices do not match adjustment factors.")
        return self


class CorporateActionEffect(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    date: date
    symbol: str
    factor: Decimal
    quantity_before: int = Field(ge=0)
    quantity_after: int = Field(ge=0)
    fractional_quantity: Decimal = Field(ge=0)
    cash_in_lieu: Money
    assumption: Literal["fraction_settled_at_action_date_raw_open"] = (
        "fraction_settled_at_action_date_raw_open"
    )


class ExternalStrategyResult(StrategyResult):
    model_config = ConfigDict(extra="forbid")

    currency: Currency
    price_basis: str
    dividend_policy: Literal["excluded_price_return"]
    corporate_action_effects: list[CorporateActionEffect]
