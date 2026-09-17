"""Pure Decimal performance metrics for a frozen, cost-inclusive NAV series.

This module deliberately has no market-data, strategy, broker, or service
dependency.  A caller must provide evidence that the NAV already includes the
stated costs and that the observed valuations are complete for the declared
calendar.  Irregular dates (including holidays) are therefore accepted, but
missing sessions are never inferred from the dates alone.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import (
    ROUND_HALF_EVEN,
    Context,
    Decimal,
    DivisionByZero,
    InvalidOperation,
    Overflow,
    localcontext,
)
from pathlib import Path
from typing import Literal, cast

from .market_performance_policy import load_calculation_policy

PRECISION = 50
DECIMAL_CONTEXT = Context(
    prec=PRECISION,
    rounding=ROUND_HALF_EVEN,
    Emin=-999999,
    Emax=999999,
    capitals=1,
    clamp=0,
    flags=[],
    traps=[InvalidOperation, DivisionByZero, Overflow],
)
SESSIONS_PER_YEAR = 252
SCHEMA = "market-performance-metrics-input/v1"
ENVELOPE_SCHEMA = "market-performance-metrics-envelope/v1"
RESULT_SCHEMA = "market-performance-metrics-result/v1"
MAX_NAV_POINTS = 5_000
MAX_SOURCE_BYTES = 10 * 1024 * 1024
_SHA256 = re.compile(r"^[0-9a-f]{64}$")

Grade = Literal["strict", "approximate", "fixture"]
Availability = Literal["available", "unavailable"]
_GRADES = frozenset(("strict", "approximate", "fixture"))

# These are part of the consumer-facing contract.  Do not replace them with
# exception text: an unavailable value must be stable and machine-readable.
REASONS = (
    "initial_capital_non_positive",
    "non_finite_initial_capital",
    "invalid_sessions_per_year",
    "unsupported_grade",
    "missing_data_source",
    "missing_calculation_policy",
    "missing_initial_capital_at",
    "first_nav_before_anchor",
    "missing_cost_inclusion_evidence",
    "missing_completeness_evidence",
    "missing_required_sessions",
    "missing_risk_free_evidence",
    "non_finite_risk_free_rate",
    "invalid_risk_free_rate",
    "non_finite_nav",
    "non_positive_nav",
    "duplicate_timestamp",
    "reversed_timestamp",
    "invalid_utc_timestamp",
    "period_non_positive",
    "insufficient_returns",
    "too_many_nav_points",
    "zero_variance",
    "zero_drawdown",
    "malformed_json",
    "unsupported_contract",
    "source_sha_mismatch",
    "output_overwrite",
)
Reason = Literal[
    "initial_capital_non_positive",
    "non_finite_initial_capital",
    "invalid_sessions_per_year",
    "unsupported_grade",
    "missing_data_source",
    "missing_calculation_policy",
    "missing_initial_capital_at",
    "first_nav_before_anchor",
    "missing_cost_inclusion_evidence",
    "missing_completeness_evidence",
    "missing_required_sessions",
    "missing_risk_free_evidence",
    "non_finite_risk_free_rate",
    "invalid_risk_free_rate",
    "non_finite_nav",
    "non_positive_nav",
    "duplicate_timestamp",
    "reversed_timestamp",
    "invalid_utc_timestamp",
    "period_non_positive",
    "insufficient_returns",
    "too_many_nav_points",
    "zero_variance",
    "zero_drawdown",
    "malformed_json",
    "unsupported_contract",
    "source_sha_mismatch",
    "output_overwrite",
]


def _decimal(value: object, label: str) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float):
        raise ValueError(f"{label} must be a finite decimal")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{label} must be a finite decimal") from exc
    if not result.is_finite():
        raise ValueError(f"{label} must be a finite decimal")
    return result


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _sha256(value: object, label: str) -> str:
    result = _string(value, label)
    if not _SHA256.fullmatch(result):
        raise ValueError(f"{label} must be a lowercase SHA-256")
    return result


def _list(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    return value


def _evidence(value: object, label: str) -> tuple[str, ...]:
    if isinstance(value, str):
        return (_string(value, label),)
    return tuple(_string(item, label) for item in _list(value, label))


class _DuplicateKey(ValueError):
    pass


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKey(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _parse_json(body: bytes, label: str) -> dict[str, object]:
    try:
        parsed = json.loads(
            body.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_int=Decimal,
            parse_float=Decimal,
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        RecursionError,
        _DuplicateKey,
    ) as exc:
        raise ValueError(f"{label} is invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{label} is invalid JSON: must contain an object")
    return parsed


def _parse_utc(value: object, label: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be an offset-aware UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{label} must be an offset-aware UTC timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{label} must be an offset-aware UTC timestamp")
    return parsed.astimezone(UTC)


@dataclass(frozen=True)
class NAVPoint:
    """One UTC valuation point.  The input ordering is meaningful and checked."""

    timestamp: datetime
    nav: Decimal


@dataclass(frozen=True)
class DataSource:
    identity: str


@dataclass(frozen=True)
class CompletenessEvidence:
    status: Literal["complete", "partial", "unknown"]
    evidence: tuple[str, ...]
    calendar_evidence: tuple[str, ...]
    missing_sessions: tuple[str, ...] = ()
    # Explicitly listed holiday gaps are informational; they are not inferred
    # to be complete without calendar_evidence.
    allowed_gaps: tuple[str, ...] = ()


@dataclass(frozen=True)
class CostInclusionEvidence:
    included: bool
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class RiskFreeEvidence:
    annual_rate: Decimal
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class PerformanceInput:
    initial_capital: Decimal
    initial_capital_at: datetime
    nav_points: tuple[NAVPoint, ...]
    data_grade: Grade
    data_source: DataSource
    completeness: CompletenessEvidence
    cost_inclusion: CostInclusionEvidence
    risk_free: RiskFreeEvidence
    calculation_policy: str
    sessions_per_year: int = SESSIONS_PER_YEAR

    @classmethod
    def from_mapping(cls, value: object) -> PerformanceInput:
        if not isinstance(value, Mapping):
            raise ValueError("performance input must be an object")
        if value.get("schema") != SCHEMA:
            raise ValueError("performance input schema is unsupported")
        capital = value.get("initial_capital")
        capital_map = capital if isinstance(capital, Mapping) else None
        if capital_map is None or capital_map.get("unit") != "currency":
            raise ValueError("initial_capital must be a currency object")
        initial_capital = _decimal(capital_map.get("value"), "initial_capital.value")
        initial_capital_at = _parse_utc(
            value.get("initial_capital_at"), "initial_capital_at"
        )
        nav_points: list[NAVPoint] = []
        raw_nav = value.get("nav", value.get("nav_points"))
        for index, item in enumerate(_list(raw_nav, "nav")):
            if not isinstance(item, Mapping):
                raise ValueError(f"nav {index} must be an object")
            nav_points.append(
                NAVPoint(
                    _parse_utc(
                        item.get("timestamp", item.get("at")),
                        f"nav {index}.timestamp",
                    ),
                    _decimal(item.get("nav"), f"nav {index}.nav"),
                )
            )
        raw_source = value.get("data_source", value.get("source"))
        if isinstance(raw_source, Mapping):
            raw_source = raw_source.get("identity")
        source = _string(raw_source, "data_source")
        grade = value.get("data_grade", value.get("research_grade"))
        if grade not in _GRADES:
            raise ValueError("data_grade is unsupported")
        raw_complete = value.get("completeness")
        complete_map = raw_complete if isinstance(raw_complete, Mapping) else None
        if complete_map is None:
            raise ValueError("completeness must be an object")
        evidence = _evidence(complete_map.get("evidence"), "completeness.evidence")
        calendar = _evidence(
            complete_map.get("calendar_evidence"), "completeness.calendar_evidence"
        )
        missing = tuple(
            _string(item, "completeness.missing_sessions")
            for item in _list(
                complete_map.get("missing_sessions", []),
                "completeness.missing_sessions",
            )
        )
        allowed = tuple(
            _string(item, "completeness.allowed_gaps")
            for item in _list(
                complete_map.get("allowed_gaps", []), "completeness.allowed_gaps"
            )
        )
        status = complete_map.get("status")
        if status not in {"complete", "partial", "unknown"}:
            raise ValueError("completeness.status is unsupported")
        raw_cost = value.get("cost_inclusion", value.get("costs"))
        cost_map = raw_cost if isinstance(raw_cost, Mapping) else None
        if cost_map is None:
            raise ValueError("cost_inclusion must be an object")
        cost_evidence = _evidence(cost_map.get("evidence"), "cost_inclusion.evidence")
        included = cost_map.get("included")
        if not isinstance(included, bool):
            raise ValueError("cost_inclusion.included must be boolean")
        raw_rf = value.get("risk_free")
        if raw_rf is None and "risk_free_annual_rate" in value:
            raw_rf = {
                "annual_rate": value.get("risk_free_annual_rate"),
                "evidence": value.get("risk_free_evidence"),
            }
        rf_map = raw_rf if isinstance(raw_rf, Mapping) else None
        if rf_map is None:
            raise ValueError("risk_free must be an object")
        rf_evidence = _evidence(rf_map.get("evidence"), "risk_free.evidence")
        raw_sessions_per_year = value.get("sessions_per_year", SESSIONS_PER_YEAR)
        if isinstance(raw_sessions_per_year, Decimal):
            if raw_sessions_per_year != raw_sessions_per_year.to_integral_value():
                raise ValueError("sessions_per_year must be an integer")
            sessions_per_year = int(raw_sessions_per_year)
        elif isinstance(raw_sessions_per_year, int) and not isinstance(
            raw_sessions_per_year, bool
        ):
            sessions_per_year = raw_sessions_per_year
        else:
            raise ValueError("sessions_per_year must be an integer")
        return cls(
            initial_capital=initial_capital,
            initial_capital_at=initial_capital_at,
            nav_points=tuple(nav_points),
            data_grade=cast(Grade, grade),
            data_source=DataSource(source),
            completeness=CompletenessEvidence(
                cast(Literal["complete", "partial", "unknown"], status),
                evidence,
                calendar,
                missing,
                allowed,
            ),
            cost_inclusion=CostInclusionEvidence(included, cost_evidence),
            risk_free=RiskFreeEvidence(
                _decimal(rf_map.get("annual_rate"), "risk_free.annual_rate"),
                rf_evidence,
            ),
            calculation_policy=_string(
                value.get("calculation_policy"), "calculation_policy"
            ),
            sessions_per_year=sessions_per_year,
        )


@dataclass(frozen=True)
class MetricResult:
    availability: Availability
    value: Decimal | None = None
    reason: Reason | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "availability": self.availability,
            "value": None if self.value is None else str(self.value),
            "reason": self.reason,
        }


@dataclass(frozen=True)
class HardFilterResult:
    availability: Availability
    passed: bool | None = None
    reason: Reason | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "availability": self.availability,
            "passed": self.passed,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class PerformanceReport:
    data_grade: Grade
    data_source: str
    initial_capital_at: datetime
    calculation_policy: str
    total_net_return: MetricResult
    cagr: MetricResult
    maximum_drawdown: MetricResult
    sharpe: MetricResult
    calmar: MetricResult
    hard_filter: HardFilterResult

    def as_dict(self) -> dict[str, object]:
        return {
            "schema": RESULT_SCHEMA,
            "data_grade": self.data_grade,
            "data_source": self.data_source,
            "initial_capital_at": self.initial_capital_at.isoformat(),
            "calculation_policy": self.calculation_policy,
            "metrics": {
                "total_net_return": self.total_net_return.as_dict(),
                "cagr": self.cagr.as_dict(),
                "maximum_drawdown": self.maximum_drawdown.as_dict(),
                "sharpe": self.sharpe.as_dict(),
                "calmar": self.calmar.as_dict(),
            },
            "hard_filter": self.hard_filter.as_dict(),
            "contract": {
                "costs_included_in_nav": True,
                "research_grade_preserved": True,
                "economic_promotion": False,
            },
        }


def _unavailable(input_value: PerformanceInput, reason: Reason) -> PerformanceReport:
    metric = MetricResult("unavailable", reason=reason)
    return PerformanceReport(
        input_value.data_grade,
        input_value.data_source.identity,
        input_value.initial_capital_at,
        input_value.calculation_policy,
        metric,
        metric,
        metric,
        metric,
        metric,
        HardFilterResult("unavailable", reason=reason),
    )


def _validate_input(input_value: PerformanceInput) -> Reason | None:
    if not input_value.initial_capital.is_finite():
        return "non_finite_initial_capital"
    if input_value.initial_capital <= 0:
        return "initial_capital_non_positive"
    if input_value.sessions_per_year != SESSIONS_PER_YEAR:
        return "invalid_sessions_per_year"
    if input_value.data_grade not in _GRADES:
        return "unsupported_grade"
    if not input_value.data_source.identity.strip():
        return "missing_data_source"
    if not input_value.calculation_policy.strip():
        return "missing_calculation_policy"
    anchor = input_value.initial_capital_at
    if anchor.tzinfo is None or anchor.utcoffset() is None:
        return "invalid_utc_timestamp"
    if (
        not input_value.cost_inclusion.included
        or not input_value.cost_inclusion.evidence
        or any(not item.strip() for item in input_value.cost_inclusion.evidence)
    ):
        return "missing_cost_inclusion_evidence"
    if input_value.completeness.missing_sessions:
        return "missing_required_sessions"
    if (
        input_value.completeness.status != "complete"
        or not input_value.completeness.evidence
        or not input_value.completeness.calendar_evidence
        or any(not item.strip() for item in input_value.completeness.evidence)
        or any(not item.strip() for item in input_value.completeness.calendar_evidence)
    ):
        return "missing_completeness_evidence"
    previous: datetime | None = None
    for point in input_value.nav_points:
        if not point.nav.is_finite():
            return "non_finite_nav"
        if point.nav <= 0:
            return "non_positive_nav"
        timestamp = point.timestamp
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            return "invalid_utc_timestamp"
        if previous is not None:
            current_utc = timestamp.astimezone(UTC)
            if current_utc == previous:
                return "duplicate_timestamp"
            if current_utc < previous:
                return "reversed_timestamp"
            previous = current_utc
        else:
            previous = timestamp.astimezone(UTC)
    if not input_value.nav_points:
        return "period_non_positive"
    first_timestamp = input_value.nav_points[0].timestamp.astimezone(UTC)
    if first_timestamp < anchor.astimezone(UTC):
        return "first_nav_before_anchor"
    final_timestamp = input_value.nav_points[-1].timestamp.astimezone(UTC)
    if final_timestamp.date() <= anchor.astimezone(UTC).date():
        return "period_non_positive"
    if len(input_value.nav_points) > MAX_NAV_POINTS:
        return "too_many_nav_points"
    return None


def _validate_sharpe_input(input_value: PerformanceInput) -> Reason | None:
    if not input_value.risk_free.evidence or any(
        not item.strip() for item in input_value.risk_free.evidence
    ):
        return "missing_risk_free_evidence"
    annual = input_value.risk_free.annual_rate
    if not annual.is_finite():
        return "non_finite_risk_free_rate"
    if annual <= Decimal("-1"):
        return "invalid_risk_free_rate"
    if len(input_value.nav_points) < 2:
        return "insufficient_returns"
    return None


def _power(base: Decimal, exponent: Decimal) -> Decimal:
    if base <= 0:
        raise ValueError("power base must be positive")
    return (base.ln() * exponent).exp()


def evaluate_performance(input_value: PerformanceInput) -> PerformanceReport:
    """Evaluate one frozen input without changing or sorting its NAV points."""

    reason = _validate_input(input_value)
    if reason is not None:
        return _unavailable(input_value, reason)
    with localcontext(DECIMAL_CONTEXT):
        final = input_value.nav_points[-1]
        elapsed_days = Decimal(
            (
                final.timestamp.astimezone(UTC).date()
                - input_value.initial_capital_at.astimezone(UTC).date()
            ).days
        )
        if elapsed_days <= 0:
            return _unavailable(input_value, "period_non_positive")
        total = final.nav / input_value.initial_capital - Decimal(1)
        cagr = _power(
            final.nav / input_value.initial_capital, Decimal(365) / elapsed_days
        ) - Decimal(1)

        peak = input_value.initial_capital
        maximum_drawdown = Decimal(0)
        for point in input_value.nav_points:
            if point.nav > peak:
                peak = point.nav
            drawdown = (peak - point.nav) / peak
            if drawdown > maximum_drawdown:
                maximum_drawdown = drawdown

        sharpe_reason = _validate_sharpe_input(input_value)
        if sharpe_reason is not None:
            sharpe = MetricResult("unavailable", reason=sharpe_reason)
        else:
            returns = [
                input_value.nav_points[0].nav / input_value.initial_capital - Decimal(1)
            ]
            returns.extend(
                current.nav / previous.nav - Decimal(1)
                for previous, current in zip(
                    input_value.nav_points, input_value.nav_points[1:]
                )
            )
            daily_rf = _power(
                Decimal(1) + input_value.risk_free.annual_rate,
                Decimal(1) / Decimal(input_value.sessions_per_year),
            ) - Decimal(1)
            excess = [item - daily_rf for item in returns]
            mean = sum(excess, Decimal(0)) / Decimal(len(excess))
            variance = sum((item - mean) ** 2 for item in excess) / Decimal(
                len(excess) - 1
            )
            if variance == 0:
                sharpe = MetricResult("unavailable", reason="zero_variance")
            else:
                sharpe = MetricResult(
                    "available",
                    mean
                    / variance.sqrt()
                    * Decimal(input_value.sessions_per_year).sqrt(),
                )
        mdd = MetricResult("available", maximum_drawdown)
        calmar = (
            MetricResult("unavailable", reason="zero_drawdown")
            if maximum_drawdown == 0
            else MetricResult("available", cagr / maximum_drawdown)
        )
        hard_filter = HardFilterResult(
            "available", passed=maximum_drawdown <= Decimal("0.20")
        )
        return PerformanceReport(
            input_value.data_grade,
            input_value.data_source.identity,
            input_value.initial_capital_at,
            input_value.calculation_policy,
            MetricResult("available", total),
            MetricResult("available", cagr),
            mdd,
            sharpe,
            calmar,
            hard_filter,
        )


@dataclass(frozen=True)
class FrozenSource:
    path: Path
    sha256: str


@dataclass(frozen=True)
class PerformanceEnvelope:
    source: FrozenSource

    @classmethod
    def from_mapping(
        cls, value: object, *, base_dir: Path = Path(".")
    ) -> PerformanceEnvelope:
        if not isinstance(value, Mapping) or value.get("schema") != ENVELOPE_SCHEMA:
            raise ValueError("performance envelope schema is unsupported")
        raw = value.get("source")
        if not isinstance(raw, Mapping):
            raise ValueError("performance envelope.source must be an object")
        path = Path(_string(raw.get("path"), "source.path"))
        if not path.is_absolute():
            path = base_dir / path
        return cls(FrozenSource(path, _sha256(raw.get("sha256"), "source.sha256")))


def _paths_alias(first: Path, second: Path) -> bool:
    if first.resolve() == second.resolve():
        return True
    if not first.exists() or not second.exists():
        return False
    try:
        return first.samefile(second)
    except OSError:
        return False


def _load_source(source: FrozenSource) -> tuple[PerformanceInput, str]:
    try:
        body = source.path.read_bytes()
    except OSError as exc:
        raise ValueError("performance source is unavailable") from exc
    if len(body) > MAX_SOURCE_BYTES:
        raise ValueError("performance source exceeds bounded input size")
    actual = hashlib.sha256(body).hexdigest()
    if actual != source.sha256:
        raise ValueError("source_sha_mismatch: source SHA-256 mismatch")
    payload = _parse_json(body, f"performance source {source.path}")
    return PerformanceInput.from_mapping(payload), actual


def load_performance_envelope(path: Path) -> PerformanceEnvelope:
    try:
        body = path.read_bytes()
    except OSError as exc:
        raise ValueError("performance envelope is unavailable") from exc
    return PerformanceEnvelope.from_mapping(
        _parse_json(body, str(path)), base_dir=path.parent
    )


def evaluate_saved_performance(
    envelope_path: Path, output_path: Path
) -> dict[str, object]:
    load_calculation_policy()
    envelope = load_performance_envelope(envelope_path)
    if _paths_alias(output_path, envelope_path) or _paths_alias(
        output_path, envelope.source.path
    ):
        raise ValueError("output path must not overwrite an input")
    input_value, source_sha256 = _load_source(envelope.source)
    result = evaluate_performance(input_value).as_dict()
    result["source"] = {"path": str(envelope.source.path), "sha256": source_sha256}
    payload = (
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    temporary_path: Path | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{output_path.name}.", suffix=".tmp", dir=output_path.parent
        )
        temporary_path = Path(temporary_name)
        with os.fdopen(descriptor, "wb") as temporary:
            temporary.write(payload)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, output_path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass
    return result


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    evaluate_saved_performance(args.input, args.output)
    return 0


__all__ = [
    "Availability",
    "CompletenessEvidence",
    "CostInclusionEvidence",
    "DataSource",
    "FrozenSource",
    "HardFilterResult",
    "MetricResult",
    "NAVPoint",
    "PerformanceEnvelope",
    "PerformanceInput",
    "PerformanceReport",
    "REASONS",
    "RiskFreeEvidence",
    "evaluate_performance",
    "evaluate_saved_performance",
    "load_performance_envelope",
]


if __name__ == "__main__":
    raise SystemExit(_main())
