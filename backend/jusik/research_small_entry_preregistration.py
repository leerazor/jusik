"""Create and validate the offline small-entry preregistration draft.

This module is deliberately a specification and validator only.  It does not
read the research database, collect market data, run an engine, or submit an
order.  A draft remains a draft even when all currently known decisions are
provided; a separate approval process is required before any future work.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal, NoReturn, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

SPEC_ID = "small-entry-preregistration-draft-v1"
SCHEMA_VERSION = 1
HISTORICAL_DISTRIBUTION_SHA256 = (
    "83f42856e91a34c35f711335dfd9eebebb1a220e902b2f1d767ab74cec1cc5be"
)
ORIGINAL_UNHELD_PREREGISTRATION_SHA256 = (
    "9bf1a850a74a2c95a58f8b6097aa98bff6012a45eb2b887c9e653cf3352f74e7"
)
HASH_PATTERN = r"^[a-f0-9]{64}$"
OLD_SPECIFICATION_SHA256 = ORIGINAL_UNHELD_PREREGISTRATION_SHA256


def _decimal(value: object, label: str, *, positive: bool = False) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a Decimal-compatible number, not bool")
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except (ArithmeticError, TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a Decimal-compatible number") from exc
    if not result.is_finite():
        raise ValueError(f"{label} must be finite")
    if positive and result <= 0:
        raise ValueError(f"{label} must be positive")
    return result


def _positive_decimal(value: object) -> Decimal:
    return _decimal(value, "threshold_krw", positive=True)


def _nonnegative_decimal(value: object, label: str) -> Decimal:
    result = _decimal(value, label)
    if result < 0:
        raise ValueError(f"{label} must not be negative")
    return result


def _aware_utc(value: object, label: str) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError(f"{label} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")
    return value.astimezone(UTC)


class HistoricalProvenance(BaseModel):
    """The two historical artifacts that informed this draft."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, validate_default=True, str_strip_whitespace=True
    )

    entry_amount_distribution_sha256: str = Field(
        default=HISTORICAL_DISTRIBUTION_SHA256, pattern=HASH_PATTERN
    )
    original_unheld_preregistration_sha256: str = Field(
        default=ORIGINAL_UNHELD_PREREGISTRATION_SHA256, pattern=HASH_PATTERN
    )

    @model_validator(mode="after")
    def require_frozen_sources(self) -> Self:
        if self.entry_amount_distribution_sha256 != HISTORICAL_DISTRIBUTION_SHA256:
            raise ValueError("historical distribution hash is not the pinned source")
        if (
            self.original_unheld_preregistration_sha256
            != ORIGINAL_UNHELD_PREREGISTRATION_SHA256
        ):
            raise ValueError("original unheld preregistration hash is not pinned")
        return self


class RiskLimits(BaseModel):
    """User ceilings and the frozen PAPER policy limits."""

    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)

    user_capital_krw: Decimal = Field(default=Decimal("100000000"))
    user_max_loss_pct: Decimal = Field(default=Decimal("20"))
    user_leverage_pct: Decimal = Field(default=Decimal("20"))
    paper_drawdown_pct: Decimal = Field(default=Decimal("10"))
    paper_gross_exposure_pct: Decimal = Field(default=Decimal("60"))
    paper_symbol_exposure_pct: Decimal = Field(default=Decimal("20"))
    paper_leveraged_etf_pct: Decimal = Field(default=Decimal("20"))

    @field_validator(
        "user_capital_krw",
        "user_max_loss_pct",
        "user_leverage_pct",
        "paper_drawdown_pct",
        "paper_gross_exposure_pct",
        "paper_symbol_exposure_pct",
        "paper_leveraged_etf_pct",
        mode="before",
    )
    @classmethod
    def finite_nonnegative(cls, value: object, info: ValidationInfo) -> Decimal:
        return _nonnegative_decimal(value, str(info.field_name))

    @model_validator(mode="after")
    def require_limits(self) -> Self:
        expected = {
            "user_capital_krw": Decimal("100000000"),
            "user_max_loss_pct": Decimal("20"),
            "user_leverage_pct": Decimal("20"),
            "paper_drawdown_pct": Decimal("10"),
            "paper_gross_exposure_pct": Decimal("60"),
            "paper_symbol_exposure_pct": Decimal("20"),
            "paper_leveraged_etf_pct": Decimal("20"),
        }
        for name, value in expected.items():
            if getattr(self, name) != value:
                raise ValueError(f"{name} is not the frozen contract value")
        return self


class CostScenario(BaseModel):
    """Descriptive historical cost assumptions; never an execution request."""

    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)

    multiplier: Literal[1, 2]
    fee_rate: Decimal
    slippage_rate: Decimal
    fx_spread_rate: Decimal
    description: str

    @field_validator("fee_rate", "slippage_rate", "fx_spread_rate", mode="before")
    @classmethod
    def valid_rate(cls, value: object, info: ValidationInfo) -> Decimal:
        return _nonnegative_decimal(value, str(info.field_name))

    @model_validator(mode="after")
    def frozen_rate(self) -> Self:
        expected = Decimal("0.001") * self.multiplier
        if not (
            self.fee_rate == expected
            and self.slippage_rate == expected
            and self.fx_spread_rate == expected
        ):
            raise ValueError(
                "cost scenario rates must use the pinned 1x/2x assumptions"
            )
        expected_description = (
            "Historical baseline assumptions, 1x; descriptive only."
            if self.multiplier == 1
            else "Historical baseline assumptions, 2x stress; descriptive only."
        )
        if self.description != expected_description:
            raise ValueError("cost scenario description is fixed")
        return self


class ControlDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)

    policy: Literal["low_turnover_combined"] = "low_turnover_combined"
    cadence_weeks: Literal[4] = 4
    low_turnover_band_pct: Decimal = Field(default=Decimal("2"))
    new_entry_floor_krw: None = None
    original_unheld_exemption_context: str = (
        "The historical unheld exemption is context only; it is not a new control."
    )

    @field_validator("low_turnover_band_pct", mode="before")
    @classmethod
    def valid_band(cls, value: object) -> Decimal:
        result = _decimal(value, "low_turnover_band_pct", positive=True)
        if result != Decimal("2"):
            raise ValueError("low-turnover band is fixed at 2 percentage points")
        return result

    @model_validator(mode="after")
    def fixed_context(self) -> Self:
        if self.original_unheld_exemption_context != (
            "The historical unheld exemption is context only; it is not a new control."
        ):
            raise ValueError("historical unheld context is fixed")
        return self


class EvaluationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)

    arms: tuple[
        Literal["control", "small_entry"], Literal["control", "small_entry"]
    ] = (
        "control",
        "small_entry",
    )
    paired_inputs: str = (
        "Use the same input, universe, period, and cost scenario for both arms."
    )
    metrics: tuple[str, ...] = (
        "net_return_pct",
        "max_drawdown_pct",
        "turnover_pct",
        "new_entry_count",
    )
    stop_conditions: tuple[str, ...] = (
        "missing data",
        "duplicate records",
        "future-data leakage",
        "hash mismatch",
        "accounting mismatch",
        "contract violation",
        "drawdown at or above 10 percent",
    )
    automatic_promotion: Literal[False] = False

    @model_validator(mode="after")
    def fixed_protocol(self) -> Self:
        if self.arms != ("control", "small_entry"):
            raise ValueError("evaluation arms are fixed")
        if self.metrics != (
            "net_return_pct",
            "max_drawdown_pct",
            "turnover_pct",
            "new_entry_count",
        ):
            raise ValueError("evaluation metrics are fixed")
        if self.stop_conditions != (
            "missing data",
            "duplicate records",
            "future-data leakage",
            "hash mismatch",
            "accounting mismatch",
            "contract violation",
            "drawdown at or above 10 percent",
        ):
            raise ValueError("evaluation stop conditions are fixed")
        if self.paired_inputs != (
            "Use the same input, universe, period, and cost scenario for both arms."
        ):
            raise ValueError("paired-input protocol is fixed")
        return self


class SmallEntryPreregistrationDraft(BaseModel):
    """Immutable, always-draft contract for a possible future evaluation."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, validate_default=True, str_strip_whitespace=True
    )

    schema_version: Literal[1] = 1
    spec_id: Literal["small-entry-preregistration-draft-v1"] = (
        "small-entry-preregistration-draft-v1"
    )
    status: Literal["draft"] = "draft"
    runtime_activation_allowed: Literal[False] = False
    reused_data: Literal[True] = True
    historical_context_only: Literal[True] = True
    prospective_validation_eligible: Literal[False] = False
    historical_small_entry_preregistration_found: Literal[False] = False

    threshold_krw: Decimal | None = None
    approval_time: datetime | None = None
    future_period_start: datetime | None = None
    future_period_end: datetime | None = None
    threshold_rule: Literal["planned_notional_krw < threshold_krw"] = (
        "planned_notional_krw < threshold_krw"
    )

    provenance: HistoricalProvenance = Field(default_factory=HistoricalProvenance)
    control: ControlDefinition = Field(default_factory=ControlDefinition)
    cost_scenarios: tuple[CostScenario, CostScenario] = (
        CostScenario(
            multiplier=1,
            fee_rate=Decimal("0.001"),
            slippage_rate=Decimal("0.001"),
            fx_spread_rate=Decimal("0.001"),
            description="Historical baseline assumptions, 1x; descriptive only.",
        ),
        CostScenario(
            multiplier=2,
            fee_rate=Decimal("0.002"),
            slippage_rate=Decimal("0.002"),
            fx_spread_rate=Decimal("0.002"),
            description="Historical baseline assumptions, 2x stress; descriptive only.",
        ),
    )
    risk_limits: RiskLimits = Field(default_factory=RiskLimits)
    evaluation: EvaluationPlan = Field(default_factory=EvaluationPlan)
    accounting: tuple[str, ...] = (
        "new_entry: pre-buy position quantity is zero",
        "additional_buy: pre-buy position quantity is positive",
        "unknown: pre-buy position quantity is missing or negative",
        "planned notional is quantity times local price times FX in KRW before "
        "the decision and excludes fees",
        "historical filled notional includes embedded slippage; fees and FX costs "
        "are separate and never double-counted",
    )

    @field_validator("threshold_krw", mode="before")
    @classmethod
    def valid_threshold(cls, value: object) -> Decimal | None:
        if value is None:
            return None
        return _positive_decimal(value)

    @field_validator(
        "approval_time", "future_period_start", "future_period_end", mode="before"
    )
    @classmethod
    def valid_time(cls, value: object, info: ValidationInfo) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value)
            except ValueError as exc:
                raise ValueError(f"{info.field_name} must be an ISO datetime") from exc
        elif isinstance(value, (bool, int, float, Decimal)):
            raise ValueError(f"{info.field_name} must be an ISO datetime")
        return _aware_utc(value, str(info.field_name))

    @model_validator(mode="after")
    def valid_period(self) -> Self:
        if (
            self.approval_time is not None
            and self.future_period_start is not None
            and self.approval_time >= self.future_period_start
        ):
            raise ValueError("approval_time must precede future_period_start")
        if (
            self.future_period_start is not None
            and self.future_period_end is not None
            and self.future_period_start >= self.future_period_end
        ):
            raise ValueError("future_period_start must precede future_period_end")
        if len(self.cost_scenarios) != 2 or tuple(
            item.multiplier for item in self.cost_scenarios
        ) != (1, 2):
            raise ValueError("cost scenarios must contain 1x and 2x in order")
        if self.threshold_rule != "planned_notional_krw < threshold_krw":
            raise ValueError("threshold comparison rule is fixed")
        if self.accounting != (
            "new_entry: pre-buy position quantity is zero",
            "additional_buy: pre-buy position quantity is positive",
            "unknown: pre-buy position quantity is missing or negative",
            "planned notional is quantity times local price times FX in KRW before "
            "the decision and excludes fees",
            "historical filled notional includes embedded slippage; fees and FX costs "
            "are separate and never double-counted",
        ):
            raise ValueError("accounting definitions are fixed")
        return self


def _normalise(value: object) -> object:
    if isinstance(value, BaseModel):
        return _normalise(value.model_dump(mode="python"))
    if isinstance(value, Decimal):
        # Decimal scale is presentation detail: 1, 1.0, and 1E+0 have one
        # canonical representation while values remain exact.  Avoid
        # normalize(), whose ambient context can round long values.
        text = format(value, "f")
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        return "0" if text in ("", "-0") else text
    if isinstance(value, datetime):
        return _aware_utc(value, "canonical datetime").isoformat()
    if isinstance(value, Mapping):
        return {str(key): _normalise(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalise(item) for item in value]
    return value


def canonical_json(value: object, *, exclude_self: bool = True) -> bytes:
    """Return stable sorted compact UTF-8 JSON bytes.

    ``exclude_self`` removes conventional self-hash keys when a caller passes
    a dictionary that contains a digest alongside the content.
    """

    normalised = _normalise(value)
    if exclude_self and isinstance(normalised, dict):
        for key in ("sha256", "draft_sha256", "content_sha256", "specification_sha256"):
            normalised.pop(key, None)
    return json.dumps(
        normalised,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_bytes(draft: SmallEntryPreregistrationDraft) -> bytes:
    return canonical_json(_validated_draft(draft))


def _validated_draft(
    draft: SmallEntryPreregistrationDraft,
) -> SmallEntryPreregistrationDraft:
    """Revalidate instances, including objects made with ``model_construct``."""

    return SmallEntryPreregistrationDraft.model_validate(
        draft.model_dump(mode="python")
    )


def draft_sha256(draft: SmallEntryPreregistrationDraft) -> str:
    digest = hashlib.sha256(canonical_bytes(draft)).hexdigest()
    if digest == OLD_SPECIFICATION_SHA256:
        raise ValueError("new draft identity unexpectedly matches the old identity")
    return digest


def classify_entry(
    pre_buy_position: int | Decimal | None,
) -> Literal["new_entry", "additional_buy", "unknown"]:
    """Classify a buy using the position immediately before the buy."""

    if pre_buy_position is None:
        return "unknown"
    if isinstance(pre_buy_position, bool):
        return "unknown"
    try:
        position = _decimal(pre_buy_position, "pre_buy_position")
    except ValueError:
        return "unknown"
    if position < 0:
        return "unknown"
    if position == 0:
        return "new_entry"
    return "additional_buy"


def missing_decisions(draft: SmallEntryPreregistrationDraft) -> dict[str, object]:
    draft = _validated_draft(draft)
    fields = (
        ("threshold_krw", draft.threshold_krw, "a positive finite KRW threshold"),
        ("approval_time", draft.approval_time, "a timezone-aware approval time"),
        (
            "future_period_start",
            draft.future_period_start,
            "a timezone-aware future evaluation start",
        ),
        (
            "future_period_end",
            draft.future_period_end,
            "a timezone-aware future evaluation end",
        ),
    )
    decisions = [
        {"field": name, "reason": reason}
        for name, value, reason in fields
        if value is None
    ]
    return {
        "spec_id": SPEC_ID,
        "status": "draft",
        "runtime_activation_allowed": False,
        "missing": [item["field"] for item in decisions],
        "decisions": decisions,
    }


def _empty_output(path: Path) -> None:
    if path.exists():
        if not path.is_dir() or any(path.iterdir()):
            raise ValueError(
                "output directory must be new or empty; overwrite is refused"
            )
    else:
        path.mkdir(parents=True)


def _write_exclusive(path: Path, body: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(body)
            output.flush()
            os.fsync(output.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def _load_draft(path: Path | None) -> SmallEntryPreregistrationDraft:
    if path is None:
        return SmallEntryPreregistrationDraft()
    try:
        payload = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_float=Decimal,
            parse_constant=_reject_json_constant,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("input must be UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("input JSON root must be an object")
    return SmallEntryPreregistrationDraft.model_validate(payload)


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> NoReturn:
    raise ValueError(f"non-finite JSON constant is not allowed: {value}")


def write_draft(draft: SmallEntryPreregistrationDraft, output_dir: Path) -> str:
    """Write the three immutable draft artifacts into a new/empty directory."""

    draft = _validated_draft(draft)
    _empty_output(output_dir)
    body = canonical_bytes(draft)
    digest = draft_sha256(draft)
    missing = canonical_json(missing_decisions(draft), exclude_self=False)
    _write_exclusive(output_dir / "draft.json", body)
    _write_exclusive(output_dir / "draft.sha256", (digest + "\n").encode("ascii"))
    _write_exclusive(output_dir / "missing-decisions.json", missing)
    return digest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=None, help="optional draft JSON")
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        draft = _load_draft(args.input)
        write_draft(draft, args.output_dir)
    except (OSError, TypeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
