from decimal import Decimal
import json
from pathlib import Path

import pytest

from jusik.research_portfolio_residual_cash import (
    _json,
    covariance_proxy,
    diagnose_simulation,
    run_diagnostic,
)


def test_covariance_proxy_handles_negative_correlation_and_zero() -> None:
    weights = {"A": Decimal("0.5"), "B": Decimal("0.5")}
    returns = {"A": [Decimal("0.1"), Decimal("-0.1")],
               "B": [Decimal("-0.1"), Decimal("0.1")]}
    assert covariance_proxy(weights, returns) == Decimal(0)
    assert covariance_proxy({"A": Decimal(1)}, {"A": [Decimal(0), Decimal(0)]}) == Decimal(0)


def test_covariance_requires_aligned_finite_history() -> None:
    with pytest.raises(ValueError, match="aligned"):
        covariance_proxy({"A": Decimal(1), "B": Decimal(1)},
                         {"A": [Decimal(1)], "B": [Decimal(1), Decimal(2)]})
    with pytest.raises(ValueError, match="missing"):
        covariance_proxy({"A": Decimal(1)}, {})


def test_diagnostic_stages_are_overlapping_and_unallocated_is_target_gap() -> None:
    simulation = {
        "weekly_targets": [{"decided_at": "2024-01-01T00:00:00Z", "symbol": "A",
                             "target_weight": "0.45"}],
        "policy_events": [{"at": "2024-01-01T00:00:00Z", "kind": "volatility_scale",
                            "value": "0.60", "detail": "proxy"},
                           {"at": "2024-01-08T00:00:00Z", "kind": "reentry_ready",
                            "detail": "waiting"}],
    }
    result = diagnose_simulation(simulation)
    row = result["decision_rows"][0]
    assert row["pre_vol_gross"] == Decimal("0.75")
    assert row["post_vol_gross"] == Decimal("0.45")
    assert row["unallocated_target"] == Decimal("0.50")
    assert result["stages_are_overlapping_and_not_additive_cash_shares"] is True


def test_strict_json_rejects_duplicate_and_nonfinite(tmp_path: Path) -> None:
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"a": 1, "a": 2}', encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        _json(duplicate)
    nonfinite = tmp_path / "nonfinite.json"
    nonfinite.write_text('{"a": NaN}', encoding="utf-8")
    with pytest.raises(ValueError, match="non-finite"):
        _json(nonfinite)


def test_run_diagnostic_reads_saved_paths_without_simulation(tmp_path: Path) -> None:
    prior = tmp_path / "prior" / "experiment"
    (prior / "simulations").mkdir(parents=True)
    (prior / "observations").mkdir()
    payload = {"weekly_targets": [], "policy_events": []}
    simulation = prior / "simulations" / "g095_v030_c8_b002_dd010-dev1-c1.json"
    simulation.write_text(json.dumps(payload), encoding="utf-8")
    simulation2 = prior / "simulations" / "g095_v030_c8_b002_dd010-dev2-c1.json"
    simulation2.write_text(json.dumps(payload), encoding="utf-8")
    for path in (simulation, simulation2):
        (prior / "observations" / path.name).write_text("[]", encoding="utf-8")
    results = prior / "results.json"
    results.write_text("{}", encoding="utf-8")
    output = tmp_path / "out"
    result = run_diagnostic(prior.parent, output)
    assert result["historical_simulations_executed"] == 0
    assert (output / "diagnostic.json").is_file()
