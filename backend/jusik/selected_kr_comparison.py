"""Frozen, synthetic-only comparison of four existing KR raw-ledger references."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal

from jusik.approved_universe_buy_hold import (
    INITIAL_KRW,
    BuyHoldReference,
    CapControlReference,
    FrozenReferenceInput,
    ReferencePoint,
    SellCostAssumptions,
    Trade,
    _sell_rates,
    _validate,
    run_buy_hold_reference,
    run_cap_control_reference,
)
from jusik.market_performance_metrics import (
    MAX_NAV_POINTS,
    CompletenessEvidence,
    CostInclusionEvidence,
    DataSource,
    NAVPoint,
    PerformanceInput,
    PerformanceReport,
    RiskFreeEvidence,
    evaluate_performance,
)
from jusik.selected_candidate_kr_policy import (
    KRCandidateRiskReference,
    _bind_inputs,
    _frozen_config,
    run_kr_selected_candidate_risk_reference,
)
from jusik.selected_candidate_signals import FrozenSignalInput

SCHEMA = "selected-kr-comparison-manifest/v1"
RESULT_SCHEMA = "selected-kr-comparison-result/v1"
_ROOT = Path(__file__).resolve().parents[2]


class ComparisonInputError(ValueError):
    """A frozen fixture or its comparison contract is inconsistent."""


@dataclass(frozen=True)
class KRComparisonManifest:
    schema: Literal["selected-kr-comparison-manifest/v1"]
    raw_input_sha256: str
    signal_input_sha256: str
    config_sha256: str
    sell_costs_sha256: str
    adapter_sha256: str
    metrics_sha256: str
    registration_revision: int
    registration_hash: str
    cohort_label: str
    cohort_identity_sha256: str
    evaluation_start: datetime
    evaluation_end: datetime
    initial_capital_krw: Decimal
    currency: Literal["KRW"]
    raw_price_evidence_hash: str
    adjusted_signal_price_source_hash: str
    action_evidence_hash: str
    fx_evidence_hash: str
    calendar_hash: str
    cost_scenario: str
    cost_evidence: tuple[str, ...]
    evaluation_dates: tuple[date, ...]
    completeness: CompletenessEvidence
    risk_free: RiskFreeEvidence | None


@dataclass(frozen=True)
class KRComparisonArm:
    name: Literal["buy_hold", "cap_control", "equal_none", "inverse_volatility_none"]
    ledger: BuyHoldReference | CapControlReference | KRCandidateRiskReference
    metrics: PerformanceReport
    daily_nav: tuple[NAVPoint, ...]
    first_decision_at: datetime | None
    first_fill_at: datetime | None


@dataclass(frozen=True)
class KRComparisonResult:
    schema: Literal["selected-kr-comparison-result/v1"]
    scope: Literal["synthetic_only"]
    investment_qualification: Literal["not_evaluated"]
    manifest: KRComparisonManifest
    arms: tuple[KRComparisonArm, KRComparisonArm, KRComparisonArm, KRComparisonArm]


def _json_value(value: object) -> object:
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ComparisonInputError("non-finite frozen input")
        return str(value)
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ComparisonInputError("naive frozen timestamp")
        return value.astimezone(UTC).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError(f"unsupported frozen value: {type(value).__name__}")


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            default=_json_value,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _source_sha(path: str) -> str:
    return hashlib.sha256((_ROOT / path).read_bytes()).hexdigest()


def _validate_dates(dates: tuple[date, ...], start: datetime, end: datetime) -> None:
    if (
        not dates
        or any(type(day) is not date for day in dates)
        or len(dates) > MAX_NAV_POINTS
        or tuple(sorted(set(dates))) != dates
        or dates[0] != start.astimezone(UTC).date()
        or dates[-1] != end.astimezone(UTC).date()
    ):
        raise ComparisonInputError(
            "common UTC evaluation dates are incomplete or unordered"
        )


def freeze_kr_comparison_manifest(
    raw: FrozenReferenceInput,
    signal: FrozenSignalInput,
    config_bytes: bytes,
    sell_costs: SellCostAssumptions,
    *,
    cost_scenario: str,
    cost_evidence: tuple[str, ...],
    evaluation_dates: tuple[date, ...],
    completeness: CompletenessEvidence,
    risk_free: RiskFreeEvidence | None,
) -> KRComparisonManifest:
    """Bind every supplied fixture and comparison assumption before any arm runs."""
    _validate(raw)
    _bind_inputs(raw, signal)
    _frozen_config(config_bytes, signal)
    _sell_rates(sell_costs)
    if any(item.market != "KR" for item in raw.cohort):
        raise ComparisonInputError("KR-only comparison required")
    if (
        not cost_scenario.strip()
        or not cost_evidence
        or any(not item.strip() for item in cost_evidence)
    ):
        raise ComparisonInputError("explicit cost scenario and evidence required")
    if (
        completeness.status != "complete"
        or not completeness.evidence
        or not completeness.calendar_evidence
        or completeness.missing_sessions
        or any(
            not item.strip()
            for item in completeness.evidence + completeness.calendar_evidence
        )
    ):
        raise ComparisonInputError(
            "fixture completeness and calendar evidence required"
        )
    _validate_dates(evaluation_dates, raw.evaluation_start, raw.evaluation_end)
    if risk_free is not None and (
        not risk_free.annual_rate.is_finite()
        or risk_free.annual_rate <= Decimal(-1)
        or not risk_free.evidence
        or any(not item.strip() for item in risk_free.evidence)
    ):
        raise ComparisonInputError("risk-free rate requires valid evidence")
    return KRComparisonManifest(
        "selected-kr-comparison-manifest/v1",
        _digest(asdict(raw)),
        _digest(asdict(signal)),
        hashlib.sha256(config_bytes).hexdigest(),
        _digest(asdict(sell_costs)),
        _source_sha("backend/jusik/selected_kr_comparison.py"),
        _source_sha("backend/jusik/market_performance_metrics.py"),
        raw.registration_revision,
        raw.registration_hash,
        raw.cohort_label,
        _digest([asdict(item) for item in raw.cohort]),
        raw.evaluation_start.astimezone(UTC),
        raw.evaluation_end.astimezone(UTC),
        INITIAL_KRW,
        "KRW",
        raw.price_evidence_hash,
        signal.price_source_hash,
        raw.action_evidence_hash,
        raw.fx_evidence_hash,
        raw.official_calendar_hash,
        cost_scenario,
        cost_evidence,
        evaluation_dates,
        completeness,
        risk_free,
    )


def _metrics(
    points: tuple[ReferencePoint, ...],
    manifest: KRComparisonManifest,
    name: str,
) -> tuple[PerformanceReport, tuple[NAVPoint, ...]]:
    if len(points) > MAX_NAV_POINTS:
        raise ComparisonInputError("too_many_nav_points")
    full = tuple(NAVPoint(item.at, item.nav_krw) for item in points)
    last_by_day: dict[date, NAVPoint] = {}
    for point in full:
        day = point.timestamp.astimezone(UTC).date()
        if day in manifest.evaluation_dates:
            last_by_day[day] = point
    if set(last_by_day) != set(manifest.evaluation_dates):
        raise ComparisonInputError("missing common UTC evaluation date")
    daily = tuple(last_by_day[day] for day in manifest.evaluation_dates)
    if len(daily) > MAX_NAV_POINTS:
        raise ComparisonInputError("too_many_nav_points")

    def performance_input(
        series: tuple[NAVPoint, ...], *, ordered_equal: bool
    ) -> PerformanceInput:
        return PerformanceInput(
            initial_capital=manifest.initial_capital_krw,
            initial_capital_at=manifest.evaluation_start,
            nav_points=series,
            data_grade="fixture",
            data_source=DataSource(f"synthetic-KR-{name}"),
            completeness=manifest.completeness,
            cost_inclusion=CostInclusionEvidence(True, manifest.cost_evidence),
            risk_free=manifest.risk_free,
            calculation_policy="market-performance-metrics/v1",
            allow_ordered_equal_timestamps=ordered_equal,
        )

    projected = evaluate_performance(performance_input(daily, ordered_equal=False))
    chronology = evaluate_performance(performance_input(full, ordered_equal=True))
    if (
        projected.total_net_return.availability != "available"
        or chronology.maximum_drawdown.availability != "available"
        or projected.cagr.value != chronology.cagr.value
    ):
        raise ComparisonInputError("metric projection or chronology unavailable")
    return (
        PerformanceReport(
            projected.data_grade,
            projected.data_source,
            projected.initial_capital_at,
            projected.calculation_policy,
            projected.total_net_return,
            projected.cagr,
            chronology.maximum_drawdown,
            projected.sharpe,
            chronology.calmar,
            chronology.hard_filter,
        ),
        daily,
    )


def _first_fill(trades: tuple[Trade, ...]) -> datetime | None:
    return min((item.at for item in trades), default=None)


def run_kr_comparison(
    raw: FrozenReferenceInput,
    signal: FrozenSignalInput,
    config_bytes: bytes,
    sell_costs: SellCostAssumptions,
    *,
    manifest: KRComparisonManifest,
    cost_scenario: str,
    cost_evidence: tuple[str, ...],
    evaluation_dates: tuple[date, ...],
    completeness: CompletenessEvidence,
    risk_free: RiskFreeEvidence | None,
) -> KRComparisonResult:
    """Reject changed inputs before executing each existing raw ledger exactly once."""
    if not isinstance(manifest, KRComparisonManifest) or manifest.schema != SCHEMA:
        raise ComparisonInputError("frozen comparison manifest required")
    expected = freeze_kr_comparison_manifest(
        raw,
        signal,
        config_bytes,
        sell_costs,
        cost_scenario=cost_scenario,
        cost_evidence=cost_evidence,
        evaluation_dates=evaluation_dates,
        completeness=completeness,
        risk_free=risk_free,
    )
    if manifest != expected:
        raise ComparisonInputError("frozen comparison manifest mismatch")

    hold = run_buy_hold_reference(raw)
    cap = run_cap_control_reference(raw, sell_costs)
    equal = run_kr_selected_candidate_risk_reference(
        raw, signal, config_bytes, "equal", sell_costs
    )
    inverse = run_kr_selected_candidate_risk_reference(
        raw, signal, config_bytes, "inverse_volatility", sell_costs
    )
    hold_metrics, hold_daily = _metrics(hold.points, manifest, "buy_hold")
    cap_metrics, cap_daily = _metrics(cap.points, manifest, "cap_control")
    equal_metrics, equal_daily = _metrics(equal.ledger.points, manifest, "equal_none")
    inverse_metrics, inverse_daily = _metrics(
        inverse.ledger.points, manifest, "inverse_volatility_none"
    )
    return KRComparisonResult(
        "selected-kr-comparison-result/v1",
        "synthetic_only",
        "not_evaluated",
        manifest,
        (
            KRComparisonArm(
                "buy_hold",
                hold,
                hold_metrics,
                hold_daily,
                None,
                _first_fill(hold.trades),
            ),
            KRComparisonArm(
                "cap_control",
                cap,
                cap_metrics,
                cap_daily,
                None,
                _first_fill(cap.trades),
            ),
            KRComparisonArm(
                "equal_none",
                equal,
                equal_metrics,
                equal_daily,
                equal.decisions[0].at if equal.decisions else None,
                _first_fill(equal.ledger.trades),
            ),
            KRComparisonArm(
                "inverse_volatility_none",
                inverse,
                inverse_metrics,
                inverse_daily,
                inverse.decisions[0].at if inverse.decisions else None,
                _first_fill(inverse.ledger.trades),
            ),
        ),
    )
