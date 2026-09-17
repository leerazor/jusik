import copy
import hashlib
import json
from datetime import UTC, datetime, timedelta
from decimal import Context, Decimal, localcontext
from pathlib import Path

import pytest

from jusik.market_performance_metrics import (
    SCHEMA,
    CompletenessEvidence,
    CostInclusionEvidence,
    DataSource,
    NAVPoint,
    PerformanceInput,
    RiskFreeEvidence,
    evaluate_performance,
    evaluate_saved_performance,
)


def _input(
    nav: tuple[str, ...] = ("100", "110", "105"),
    days: tuple[int, ...] = (0, 1, 2),
    *,
    completeness: CompletenessEvidence | None = None,
    costs: CostInclusionEvidence | None = None,
    risk_free: RiskFreeEvidence | None = None,
    grade: str = "fixture",
) -> PerformanceInput:
    return PerformanceInput(
        initial_capital=Decimal("100"),
        nav_points=tuple(
            NAVPoint(
                datetime(2024, 1, 1, tzinfo=UTC) + timedelta(days=day), Decimal(value)
            )
            for value, day in zip(nav, days)
        ),
        data_grade=grade,  # type: ignore[arg-type]
        data_source=DataSource("offline-fixture"),
        completeness=completeness
        or CompletenessEvidence("complete", ("coverage",), ("exchange calendar",)),
        cost_inclusion=costs or CostInclusionEvidence(True, ("NAV statement",)),
        risk_free=risk_free or RiskFreeEvidence(Decimal("0"), ("policy",)),
        calculation_policy="market-performance-metrics/v1",
    )


def _value(report: object, name: str) -> Decimal | None:
    metric = getattr(report, name)
    return metric.value


def _required_value(report: object, name: str) -> Decimal:
    value = _value(report, name)
    assert value is not None
    return value


def test_independent_oracle_for_positive_and_negative_metrics() -> None:
    report = evaluate_performance(_input())
    # Hand-calculated: (105 / 100) - 1 and 5/110 drawdown.
    with localcontext(Context(prec=50)):
        assert _value(report, "total_net_return") == Decimal("0.05")
        assert _value(report, "maximum_drawdown") == Decimal(5) / Decimal(110)
        oracle_cagr = (
            Decimal("1.05").ln() * Decimal(365) / Decimal(2)
        ).exp() - Decimal(1)
        assert abs(_required_value(report, "cagr") - oracle_cagr) < Decimal("1e-44")
        oracle_calmar = oracle_cagr / (Decimal(5) / Decimal(110))
        assert abs(_required_value(report, "calmar") - oracle_calmar) < Decimal("1e-43")


def test_initial_loss_is_included_in_drawdown_and_filter_boundary_is_exact() -> None:
    report = evaluate_performance(_input(nav=("80", "100"), days=(0, 1)))
    assert _value(report, "maximum_drawdown") == Decimal("0.2")
    assert report.hard_filter.value == Decimal(1)
    report = evaluate_performance(_input(nav=("79.99", "100"), days=(0, 1)))
    assert report.hard_filter.value == Decimal(0)


def test_leap_year_and_irregular_holiday_gap_use_actual_utc_calendar_days() -> None:
    report = evaluate_performance(_input(nav=("100", "110", "121"), days=(0, 4, 8)))
    with localcontext(Context(prec=50)):
        oracle_cagr = (
            Decimal("1.21").ln() * Decimal(365) / Decimal(8)
        ).exp() - Decimal(1)
        assert abs(_required_value(report, "cagr") - oracle_cagr) < Decimal("1e-44")
    assert report.total_net_return.availability == "available"


@pytest.mark.parametrize(
    ("nav", "days", "reason"),
    [
        (("100", "100"), (0, 0), "duplicate_timestamp"),
        (("100", "101"), (1, 0), "reversed_timestamp"),
        (("0", "100"), (0, 1), "non_positive_nav"),
        (("100", "NaN"), (0, 1), "non_finite_nav"),
    ],
)
def test_invalid_nav_series_is_unavailable_with_stable_reason(
    nav: tuple[str, ...], days: tuple[int, ...], reason: str
) -> None:
    report = evaluate_performance(_input(nav=nav, days=days))
    assert report.total_net_return.availability == "unavailable"
    assert report.total_net_return.reason == reason
    assert report.hard_filter.availability == "unavailable"


def test_missing_evidence_does_not_fabricate_zero_or_infinity() -> None:
    cases = (
        _input(costs=CostInclusionEvidence(True, ())),
        _input(completeness=CompletenessEvidence("partial", ("partial",), ())),
        _input(
            completeness=CompletenessEvidence(
                "complete", ("coverage",), ("calendar",), ("2024-01-02",)
            )
        ),
        _input(risk_free=RiskFreeEvidence(Decimal("0"), ())),
    )
    reasons = (
        "missing_cost_inclusion_evidence",
        "missing_completeness_evidence",
        "missing_required_sessions",
        "missing_risk_free_evidence",
    )
    for case, reason in zip(cases, reasons):
        report = evaluate_performance(case)
        assert report.cagr.value is None
        assert report.cagr.reason == reason


def test_zero_volatility_and_zero_drawdown_are_not_fabricated() -> None:
    report = evaluate_performance(_input(nav=("100", "100", "100")))
    assert report.sharpe.value is None
    assert report.sharpe.reason == "zero_variance"
    assert report.maximum_drawdown.value == Decimal(0)
    assert report.calmar.value is None
    assert report.calmar.reason == "zero_drawdown"
    assert report.hard_filter.value == Decimal(1)


def test_grade_and_input_are_preserved_without_mutation() -> None:
    input_value = _input(grade="approximate")
    before = copy.deepcopy(input_value)
    report = evaluate_performance(input_value)
    assert input_value == before
    assert report.data_grade == "approximate"
    assert report.data_grade != "strict"


def _payload() -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "initial_capital": {"value": "100", "unit": "currency"},
        "nav": [
            {"timestamp": "2024-01-01T00:00:00Z", "nav": "100"},
            {"timestamp": "2024-01-02T00:00:00Z", "nav": "105"},
        ],
        "data_grade": "fixture",
        "data_source": "offline-fixture",
        "completeness": {
            "status": "complete",
            "evidence": ["coverage"],
            "calendar_evidence": ["calendar"],
            "missing_sessions": [],
        },
        "cost_inclusion": {"included": True, "evidence": ["NAV statement"]},
        "risk_free": {"annual_rate": "0", "evidence": ["policy"]},
        "sessions_per_year": 252,
        "calculation_policy": "market-performance-metrics/v1",
    }


def _write_envelope(tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "frozen-input.json"
    source.write_text(json.dumps(_payload(), sort_keys=True), encoding="utf-8")
    envelope = tmp_path / "envelope.json"
    envelope.write_text(
        json.dumps(
            {
                "schema": "market-performance-metrics-envelope/v1",
                "source": {
                    "path": source.name,
                    "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                },
            }
        ),
        encoding="utf-8",
    )
    return envelope, source


def test_frozen_adapter_hash_and_output_alias_guards(tmp_path: Path) -> None:
    envelope, source = _write_envelope(tmp_path)
    output = tmp_path / "result.json"
    result = evaluate_saved_performance(envelope, output)
    assert result["data_grade"] == "fixture"
    with pytest.raises(ValueError, match="output path"):
        evaluate_saved_performance(envelope, envelope)
    source.write_text(source.read_text(encoding="utf-8") + " ", encoding="utf-8")
    with pytest.raises(ValueError, match="source_sha_mismatch"):
        evaluate_saved_performance(envelope, output)


def test_frozen_adapter_rejects_malformed_and_unsupported_json(tmp_path: Path) -> None:
    envelope = tmp_path / "envelope.json"
    envelope.write_text('{"schema": "wrong"}', encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported"):
        evaluate_saved_performance(envelope, tmp_path / "result.json")
    envelope.write_bytes(b"not-json")
    with pytest.raises(ValueError, match="invalid JSON"):
        evaluate_saved_performance(envelope, tmp_path / "result.json")
