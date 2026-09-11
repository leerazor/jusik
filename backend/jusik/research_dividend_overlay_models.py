from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class _AwareModel(BaseModel):
    @field_validator(
        "created_at", "ex_open_at", "payment_boundary_at", "at", check_fields=False
    )
    @classmethod
    def require_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Dividend overlay timestamps must include a timezone.")
        return value


class DividendCoverage(_AwareModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str
    revision_id: str
    symbol: str
    vendor_date: date
    status: Literal["eligible", "excluded"]
    reason: str | None
    review_id: str | None = None
    evidence_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    evidence_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    ex_dividend_date: date | None = None
    payment_date: date | None = None
    amount: Decimal | None = Field(default=None, allow_inf_nan=False)
    currency: Literal["KRW", "USD"] | None = None


class DividendEntitlement(_AwareModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    scenario: Literal["heldout", "equal_baseline"]
    event_id: str
    revision_id: str
    symbol: str
    ex_open_at: datetime
    payment_boundary_at: datetime
    entitled_quantity: int = Field(ge=0)
    amount_per_share: Decimal = Field(gt=0, allow_inf_nan=False)
    currency: Literal["KRW", "USD"]
    gross_native: Decimal = Field(ge=0, allow_inf_nan=False)


class DividendLedgerPoint(_AwareModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    scenario: Literal["heldout", "equal_baseline"]
    event_id: str
    symbol: str
    kind: Literal["accrual", "payment"]
    at: datetime
    currency: Literal["KRW", "USD"]
    amount_native: Decimal = Field(ge=0, allow_inf_nan=False)
    receivable_after_native: Decimal = Field(ge=0, allow_inf_nan=False)
    cash_after_native: Decimal = Field(ge=0, allow_inf_nan=False)


class DividendEquityPoint(_AwareModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    scenario: Literal["heldout", "equal_baseline"]
    at: datetime
    baseline_equity_krw: Decimal = Field(ge=0, allow_inf_nan=False)
    dividend_contribution_krw: Decimal | None = Field(allow_inf_nan=False)
    equity_with_known_dividends_krw: Decimal | None = Field(allow_inf_nan=False)
    fx_rate: Decimal | None = Field(allow_inf_nan=False)
    fx_observed_on: date | None = None
    fx_available_at: datetime | None = None
    fx_revision: str | None = None
    receivable_native: dict[str, Decimal]
    cash_native: dict[str, Decimal]
    reason: str | None

    @model_validator(mode="after")
    def validate_native_balances(self) -> DividendEquityPoint:
        expected = {"KRW", "USD"}
        if set(self.receivable_native) != expected or set(self.cash_native) != expected:
            raise ValueError("Native balances must contain KRW and USD.")
        values = (*self.receivable_native.values(), *self.cash_native.values())
        if any(not value.is_finite() or value < 0 for value in values):
            raise ValueError("Native balances must be finite and non-negative.")
        return self


class DividendComparison(_AwareModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    scenario: Literal["heldout", "equal_baseline", "cash_baseline"]
    baseline_return_pct: Decimal = Field(allow_inf_nan=False)
    known_dividend_krw: Decimal | None = Field(allow_inf_nan=False)
    return_with_known_dividends_pct: Decimal | None = Field(allow_inf_nan=False)
    increase_percentage_points: Decimal | None = Field(allow_inf_nan=False)


class PositionReconciliation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    scenario: Literal["heldout", "equal_baseline"]
    expected_quantities: dict[str, int]
    replayed_quantities: dict[str, int]
    matches: bool
    quantities_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def validate_quantities(self) -> PositionReconciliation:
        if any(quantity < 0 for quantity in self.expected_quantities.values()):
            raise ValueError("Expected quantities cannot be negative.")
        if any(quantity < 0 for quantity in self.replayed_quantities.values()):
            raise ValueError("Replayed quantities cannot be negative.")
        return self


class DividendOverlayResult(_AwareModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_run_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    created_at: datetime
    source_manifest_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_result_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    review_snapshot_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    calendar_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    code_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    calculation_complete: bool
    calculation_reasons: list[str]
    coverage_complete: Literal[False] = False
    current_dividend_revision_count: int = Field(ge=0)
    eligible_dividend_count: int = Field(ge=0)
    excluded_dividend_count: int = Field(ge=0)
    in_period_eligible_count: int = Field(ge=0)
    in_period_excluded_count: int = Field(ge=0)
    coverage: list[DividendCoverage]
    entitlements: list[DividendEntitlement]
    ledger: list[DividendLedgerPoint]
    equity: list[DividendEquityPoint]
    position_reconciliations: list[PositionReconciliation]
    comparisons: list[DividendComparison]
    assumptions: list[str]
    retrospective: Literal[True] = True
    prospective_validation_eligible: Literal[False] = False
    automatic_ledger_application: Literal[False] = False
    artifacts: list[str]
