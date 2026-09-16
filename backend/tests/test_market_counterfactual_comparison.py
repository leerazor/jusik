import hashlib
import json
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from decimal import ROUND_DOWN, Context, localcontext
from pathlib import Path

import pytest

from jusik.market_counterfactual_comparison import (
    MAX_SCENARIOS,
    ComparisonEnvelope,
    compare_prepared_reports,
    compare_saved_reports,
    load_comparison_envelope,
)

COMPONENTS = (
    "raw_realized_pnl",
    "fill_realized_pnl",
    "raw_unrealized_pnl",
    "fill_unrealized_pnl",
    "dividends",
    "fees",
    "taxes",
    "slippage",
    "fx",
    "cash_balance",
    "raw_net_pnl",
    "fill_net_pnl",
)


def _object(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return value


def _array(value: object) -> list[object]:
    assert isinstance(value, list)
    return value


def _report(*, unavailable: tuple[str, ...] = ()) -> dict[str, object]:
    result: dict[str, object] = {"status": "complete"}
    for name in COMPONENTS:
        is_unavailable = name in unavailable
        result[name] = {
            "availability": "unavailable" if is_unavailable else "available",
            "value": None if is_unavailable else "100",
            "evidence": [f"{name}-evidence"],
            "resume_inputs": [f"{name}-resume"] if is_unavailable else [],
            "diagnostic_value": "77" if is_unavailable else None,
            "currency": "KRW" if name in {"fx", "cash_balance"} else "USD",
            "unit": "currency",
        }
    return result


def _write_report(
    path: Path, report: dict[str, object], assumptions: Mapping[str, object]
) -> str:
    metadata = {
        "market": "US",
        "period": {"start": "2026-01-02", "end": "2026-01-02"},
        "sessions": ["2026-01-02"],
        "currency": "USD",
        "initial_capital": {
            "value": "1000",
            "currency": "USD",
            "unit": "currency",
        },
        "research_grade": "fixture",
        "data_contract": "data-contract-v1",
        "policy_contract": "policy-v1",
        "fixed_assumptions": {
            "cost": "fixed",
            "dividend": "fixed",
            "fx": "fixed",
        },
        "assumptions": assumptions,
    }
    prepared = {
        "schema": "prepared-loss-accounting-report/v1",
        "metadata": metadata,
        "report": report,
    }
    body = json.dumps(prepared, sort_keys=True).encode()
    path.write_bytes(body)
    return hashlib.sha256(body).hexdigest()


def _envelope(
    tmp_path: Path, *, unavailable: tuple[str, ...] = ()
) -> dict[str, object]:
    baseline_path = tmp_path / "baseline.json"
    scenario_path = tmp_path / "scenario.json"
    assumptions = {
        "cost": {"fees": "1"},
        "dividend": {"evidence": "complete"},
        "fx": {"source": "prepared"},
    }
    baseline_hash = _write_report(baseline_path, _report(), assumptions)
    scenario = _report(unavailable=unavailable)
    if not unavailable:
        fees = scenario["fees"]
        assert isinstance(fees, dict)
        fees["value"] = "120"
    scenario_assumptions = {
        **assumptions,
        "cost": {"fees": "2"},
    }
    scenario_hash = _write_report(scenario_path, scenario, scenario_assumptions)
    return {
        "schema": "market-counterfactual-comparison/v1",
        "market": "US",
        "period": {"start": "2026-01-02", "end": "2026-01-02"},
        "sessions": ["2026-01-02"],
        "currency": "USD",
        "initial_capital": {"value": "1000", "currency": "USD", "unit": "currency"},
        "research_grade": "fixture",
        "data_contract": "data-contract-v1",
        "policy_contract": "policy-v1",
        "fixed_assumptions": {"cost": "fixed", "dividend": "fixed", "fx": "fixed"},
        "baseline": {
            "id": "baseline",
            "source": {"path": baseline_path.name, "sha256": baseline_hash},
            "assumptions": assumptions,
        },
        "scenarios": [
            {
                "id": "cost-change",
                "source": {"path": scenario_path.name, "sha256": scenario_hash},
                "change": {"kind": "cost", "description": "fee change"},
                "assumptions": scenario_assumptions,
            }
        ],
    }


@contextmanager
def _low_precision() -> Iterator[None]:
    with localcontext(Context(prec=3, rounding=ROUND_DOWN)):
        yield


def test_compare_uses_independent_decimal_and_returns_component_delta(
    tmp_path: Path,
) -> None:
    envelope_path = tmp_path / "envelope.json"
    envelope_path.write_text(json.dumps(_envelope(tmp_path)), encoding="utf-8")
    with _low_precision():
        result = compare_saved_reports(envelope_path, tmp_path / "result.json")
    comparison = _object(_array(result["comparisons"])[0])
    deltas = _object(comparison["deltas"])
    fees = _object(deltas["fees"])
    assert fees["value"] == "20"
    assert fees["availability"] == "available"
    assert _object(result["contract"])["aggregates"] is False


def test_unavailable_values_keep_diagnostic_out_of_delta(tmp_path: Path) -> None:
    envelope = ComparisonEnvelope.from_mapping(
        _envelope(tmp_path, unavailable=("dividends", "fx")), base_dir=tmp_path
    )
    result = compare_prepared_reports(envelope)
    comparison = _object(_array(result["comparisons"])[0])
    delta = _object(_object(comparison["deltas"])["dividends"])
    assert delta["availability"] == "unavailable"
    assert delta["value"] is None
    assert delta["resume_inputs"] == ["dividends-resume"]
    report = _object(comparison["report"])
    assert _object(report["dividends"])["diagnostic_value"] == "77"
    assert result["status"] == "blocked"


def test_available_missing_currency_is_unavailable_and_output_cannot_overwrite(
    tmp_path: Path,
) -> None:
    envelope_data = _envelope(tmp_path)
    scenario = _array(envelope_data["scenarios"])[0]
    assert isinstance(scenario, dict)
    scenario_path = tmp_path / "scenario.json"
    prepared = json.loads(scenario_path.read_text(encoding="utf-8"))
    prepared["report"]["fees"]["currency"] = None
    scenario_path.write_text(json.dumps(prepared, sort_keys=True), encoding="utf-8")
    scenario_source = _object(scenario["source"])
    scenario_source["sha256"] = hashlib.sha256(scenario_path.read_bytes()).hexdigest()
    envelope_path = tmp_path / "envelope.json"
    envelope_path.write_text(json.dumps(envelope_data), encoding="utf-8")
    with pytest.raises(ValueError, match="must not overwrite"):
        compare_saved_reports(envelope_path, envelope_path)
    result = compare_saved_reports(envelope_path, tmp_path / "result.json")
    comparison = _object(_array(result["comparisons"])[0])
    fees = _object(_object(comparison["deltas"])["fees"])
    assert fees["availability"] == "unavailable"
    assert fees["value"] is None


@pytest.mark.parametrize("component", ["dividends", "fx"])
def test_available_dividend_or_fx_requires_evidence(
    tmp_path: Path, component: str
) -> None:
    envelope_data = _envelope(tmp_path)
    baseline = tmp_path / "baseline.json"
    prepared = json.loads(baseline.read_text(encoding="utf-8"))
    prepared["report"][component]["evidence"] = []
    baseline.write_text(json.dumps(prepared, sort_keys=True), encoding="utf-8")
    baseline_source = _object(_object(envelope_data["baseline"])["source"])
    baseline_source["sha256"] = hashlib.sha256(baseline.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="requires evidence"):
        compare_prepared_reports(
            ComparisonEnvelope.from_mapping(envelope_data, base_dir=tmp_path)
        )


def test_cost_and_fx_deltas_remain_separate_and_are_not_added(
    tmp_path: Path,
) -> None:
    envelope_data = _envelope(tmp_path)
    baseline_path = tmp_path / "baseline.json"
    cost_path = tmp_path / "scenario.json"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    cost = json.loads(cost_path.read_text(encoding="utf-8"))
    baseline["report"]["fill_net_pnl"]["value"] = "180"
    cost["report"]["fill_net_pnl"]["value"] = "200"
    baseline_path.write_text(json.dumps(baseline, sort_keys=True), encoding="utf-8")
    cost_path.write_text(json.dumps(cost, sort_keys=True), encoding="utf-8")
    baseline_source = _object(_object(envelope_data["baseline"])["source"])
    baseline_source["sha256"] = hashlib.sha256(baseline_path.read_bytes()).hexdigest()
    scenarios = _array(envelope_data["scenarios"])
    cost_scenario = _object(scenarios[0])
    cost_scenario_source = _object(cost_scenario["source"])
    cost_scenario_source["sha256"] = hashlib.sha256(cost_path.read_bytes()).hexdigest()
    fx_path = tmp_path / "fx.json"
    fx = json.loads(baseline_path.read_text(encoding="utf-8"))
    fx["report"]["fill_net_pnl"]["value"] = "270"
    fx_assumptions = {
        "cost": {"fees": "1"},
        "dividend": {"evidence": "complete"},
        "fx": {"source": "changed"},
    }
    fx["metadata"]["assumptions"] = fx_assumptions
    fx_path.write_text(json.dumps(fx, sort_keys=True), encoding="utf-8")
    scenarios.append(
        {
            "id": "fx-change",
            "source": {
                "path": fx_path.name,
                "sha256": hashlib.sha256(fx_path.read_bytes()).hexdigest(),
            },
            "change": {"kind": "fx", "description": "rate change"},
            "assumptions": fx_assumptions,
        }
    )
    envelope = ComparisonEnvelope.from_mapping(envelope_data, base_dir=tmp_path)
    result = compare_prepared_reports(envelope)
    comparisons = _array(result["comparisons"])
    first = _object(comparisons[0])
    second = _object(comparisons[1])
    assert _object(_object(first["deltas"])["fill_net_pnl"])["value"] == "20"
    assert _object(_object(second["deltas"])["fill_net_pnl"])["value"] == "90"
    assert "total_delta" not in result
    assert "aggregate" not in result


def test_zero_negative_and_high_precision_values_are_decimal_safe(
    tmp_path: Path,
) -> None:
    envelope_data = _envelope(tmp_path)
    baseline_path = tmp_path / "baseline.json"
    scenario_path = tmp_path / "scenario.json"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
    baseline["report"]["fees"]["value"] = "0"
    scenario["report"]["fees"]["value"] = "-0.0000000000000000001"
    baseline_path.write_text(json.dumps(baseline, sort_keys=True), encoding="utf-8")
    scenario_path.write_text(json.dumps(scenario, sort_keys=True), encoding="utf-8")
    _object(_object(envelope_data["baseline"])["source"])["sha256"] = hashlib.sha256(
        baseline_path.read_bytes()
    ).hexdigest()
    scenario_source = _object(_object(_array(envelope_data["scenarios"])[0])["source"])
    scenario_source["sha256"] = hashlib.sha256(scenario_path.read_bytes()).hexdigest()
    result = compare_prepared_reports(
        ComparisonEnvelope.from_mapping(envelope_data, base_dir=tmp_path)
    )
    delta = _object(
        _object(_object(_array(result["comparisons"])[0])["deltas"])["fees"]
    )
    assert delta["value"] == "-1E-19"


def test_explicit_weekend_session_is_preserved_and_timezone_is_not_a_date(
    tmp_path: Path,
) -> None:
    envelope_data = _envelope(tmp_path)
    envelope_data["period"] = {"start": "2026-01-03", "end": "2026-01-03"}
    envelope_data["sessions"] = ["2026-01-03"]
    for path in (tmp_path / "baseline.json", tmp_path / "scenario.json"):
        prepared = json.loads(path.read_text(encoding="utf-8"))
        prepared["metadata"]["period"] = {
            "start": "2026-01-03",
            "end": "2026-01-03",
        }
        prepared["metadata"]["sessions"] = ["2026-01-03"]
        path.write_text(json.dumps(prepared, sort_keys=True), encoding="utf-8")
    baseline = _object(envelope_data["baseline"])
    _object(baseline["source"])["sha256"] = hashlib.sha256(
        (tmp_path / "baseline.json").read_bytes()
    ).hexdigest()
    scenario = _object(_array(envelope_data["scenarios"])[0])
    _object(scenario["source"])["sha256"] = hashlib.sha256(
        (tmp_path / "scenario.json").read_bytes()
    ).hexdigest()
    envelope = ComparisonEnvelope.from_mapping(envelope_data, base_dir=tmp_path)
    assert envelope.sessions == ("2026-01-03",)
    envelope_data["sessions"] = ["2026-01-03T00:00:00+09:00"]
    with pytest.raises(ValueError, match="ISO date"):
        ComparisonEnvelope.from_mapping(envelope_data, base_dir=tmp_path)


def test_partial_cancelled_and_rejected_status_metadata_is_preserved(
    tmp_path: Path,
) -> None:
    envelope_data = _envelope(tmp_path)
    scenario_path = tmp_path / "scenario.json"
    prepared = json.loads(scenario_path.read_text(encoding="utf-8"))
    prepared["report"]["order_statuses"] = ["partial", "cancelled", "rejected"]
    scenario_path.write_text(json.dumps(prepared, sort_keys=True), encoding="utf-8")
    scenario_source = _object(_object(_array(envelope_data["scenarios"])[0])["source"])
    scenario_source["sha256"] = hashlib.sha256(scenario_path.read_bytes()).hexdigest()
    result = compare_prepared_reports(
        ComparisonEnvelope.from_mapping(envelope_data, base_dir=tmp_path)
    )
    report = _object(_object(_array(result["comparisons"])[0])["report"])
    assert report["order_statuses"] == ["partial", "cancelled", "rejected"]


@pytest.mark.parametrize(
    "field",
    [
        "market",
        "currency",
        "period",
        "sessions",
        "initial_capital",
        "research_grade",
        "data_contract",
        "policy_contract",
        "fixed_assumptions",
    ],
)
def test_report_metadata_must_match_envelope(tmp_path: Path, field: str) -> None:
    envelope = _envelope(tmp_path)
    report_path = tmp_path / "baseline.json"
    report = _report()
    baseline = envelope["baseline"]
    assert isinstance(baseline, dict)
    base_assumptions = baseline["assumptions"]
    assert isinstance(base_assumptions, dict)
    report_hash = _write_report(report_path, report, base_assumptions)
    prepared = json.loads(report_path.read_text(encoding="utf-8"))
    if field == "period":
        prepared["metadata"][field] = {
            "start": "2026-01-01",
            "end": "2026-01-02",
        }
    elif field == "sessions":
        prepared["metadata"][field] = ["2026-01-01"]
    elif field == "initial_capital":
        prepared["metadata"][field] = {
            "value": "1001",
            "currency": "USD",
            "unit": "currency",
        }
    elif field == "fixed_assumptions":
        prepared["metadata"][field] = {
            "cost": "other",
            "dividend": "fixed",
            "fx": "fixed",
        }
    else:
        prepared["metadata"][field] = "wrong"
    report_path.write_text(json.dumps(prepared, sort_keys=True), encoding="utf-8")
    report_hash = hashlib.sha256(report_path.read_bytes()).hexdigest()
    cast_baseline = envelope["baseline"]
    assert isinstance(cast_baseline, dict)
    cast_source = cast_baseline["source"]
    assert isinstance(cast_source, dict)
    cast_source["sha256"] = report_hash
    envelope_path = tmp_path / "metadata.json"
    envelope_path.write_text(json.dumps(envelope), encoding="utf-8")
    expected_message = (
        "sessions do not match envelope"
        if field == "sessions"
        else ("does not match envelope")
    )
    with pytest.raises(ValueError, match=expected_message):
        compare_saved_reports(envelope_path, tmp_path / "result.json")


def test_duplicate_ids_sessions_and_assumptions_are_rejected(tmp_path: Path) -> None:
    envelope = _envelope(tmp_path)
    envelope["sessions"] = ["2026-01-02", "2026-01-02"]
    with pytest.raises(ValueError, match="sessions must be unique"):
        ComparisonEnvelope.from_mapping(envelope, base_dir=tmp_path)
    envelope = _envelope(tmp_path)
    scenario = _array(envelope["scenarios"])[0]
    assert isinstance(scenario, dict)
    scenario["id"] = "baseline"
    with pytest.raises(ValueError, match="scenario IDs"):
        ComparisonEnvelope.from_mapping(envelope, base_dir=tmp_path)
    envelope = _envelope(tmp_path)
    scenario = _array(envelope["scenarios"])[0]
    assert isinstance(scenario, dict)
    scenario["assumptions"] = {
        "cost": {"fees": "2"},
        "dividend": {"evidence": "changed"},
        "fx": {"source": "prepared"},
    }
    with pytest.raises(ValueError, match="exactly one"):
        ComparisonEnvelope.from_mapping(envelope, base_dir=tmp_path)


def test_duplicate_json_key_is_rejected_before_report_validation(
    tmp_path: Path,
) -> None:
    envelope = _envelope(tmp_path)
    path = tmp_path / "duplicate.json"
    path.write_text('{"schema":"market-counterfactual-comparison/v1", "schema":"x"}')
    with pytest.raises(ValueError, match="invalid JSON"):
        load_comparison_envelope(path)
    source = tmp_path / "duplicate-report.json"
    body = b'{"status":"complete", "status":"blocked"}'
    source.write_bytes(body)
    baseline = envelope["baseline"]
    assert isinstance(baseline, dict)
    source_spec = baseline["source"]
    assert isinstance(source_spec, dict)
    source_spec["path"] = source.name
    source_spec["sha256"] = hashlib.sha256(body).hexdigest()
    with pytest.raises(ValueError, match="invalid JSON"):
        compare_prepared_reports(
            ComparisonEnvelope.from_mapping(envelope, base_dir=tmp_path)
        )


def test_hash_is_checked_before_parsing_and_scenario_limit_is_bounded(
    tmp_path: Path,
) -> None:
    envelope = _envelope(tmp_path)
    baseline = envelope["baseline"]
    assert isinstance(baseline, dict)
    source = baseline["source"]
    assert isinstance(source, dict)
    source["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="hash mismatch"):
        compare_prepared_reports(
            ComparisonEnvelope.from_mapping(envelope, base_dir=tmp_path)
        )
    scenarios = envelope["scenarios"]
    assert isinstance(scenarios, list)
    scenarios.extend(scenarios.copy() * MAX_SCENARIOS)
    with pytest.raises(ValueError, match="1 to"):
        ComparisonEnvelope.from_mapping(envelope, base_dir=tmp_path)


def test_all_reports_and_original_evidence_are_preserved(tmp_path: Path) -> None:
    envelope_path = tmp_path / "envelope.json"
    envelope_path.write_text(json.dumps(_envelope(tmp_path)), encoding="utf-8")
    result = compare_saved_reports(envelope_path, tmp_path / "result.json")
    comparison = _object(_array(result["comparisons"])[0])
    report = _object(comparison["report"])
    assert _object(report["raw_realized_pnl"])["evidence"] == [
        "raw_realized_pnl-evidence"
    ]
    assert _object(comparison["change"])["kind"] == "cost"
    assert _object(result["fixed_assumptions"])["fx"] == "fixed"
