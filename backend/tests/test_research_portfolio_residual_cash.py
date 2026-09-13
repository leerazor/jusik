# ruff: noqa: E501
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from jusik.research_portfolio_low_cash_experiment import (
    EquityObservation,
    global_drawdown,
)
from jusik.research_portfolio_residual_cash import (
    _json,
    annualized_covariance_proxy,
    covariance_proxy,
    diagnose_simulation,
    install_covariance_floor_adapter,
    run_diagnostic,
)


def test_covariance_proxy_handles_negative_correlation_and_zero() -> None:
    weights = {"A": Decimal("0.5"), "B": Decimal("0.5")}
    returns = {
        "A": [Decimal("0.1"), Decimal("-0.1")],
        "B": [Decimal("-0.1"), Decimal("0.1")],
    }
    assert covariance_proxy(weights, returns) == Decimal(0)
    assert covariance_proxy(
        {"A": Decimal(1)}, {"A": [Decimal(0), Decimal(0)]}
    ) == Decimal(0)
    assert annualized_covariance_proxy(
        {"A": Decimal(1)}, {"A": [Decimal(0), Decimal(0)]}
    ) == Decimal(0)


def test_covariance_requires_aligned_finite_history() -> None:
    with pytest.raises(ValueError, match="aligned"):
        covariance_proxy(
            {"A": Decimal(1), "B": Decimal(1)},
            {"A": [Decimal(1)], "B": [Decimal(1), Decimal(2)]},
        )
    with pytest.raises(ValueError, match="missing"):
        covariance_proxy({"A": Decimal(1)}, {})


def test_diagnostic_stages_are_overlapping_and_unallocated_is_target_gap() -> None:
    simulation = {
        "weekly_targets": [
            {
                "decided_at": "2024-01-01T00:00:00Z",
                "symbol": "A",
                "target_weight": "0.45",
            }
        ],
        "policy_events": [
            {
                "at": "2024-01-01T00:00:00Z",
                "kind": "volatility_scale",
                "value": "0.60",
                "detail": "proxy",
            },
            {
                "at": "2024-01-08T00:00:00Z",
                "kind": "reentry_ready",
                "detail": "waiting",
            },
        ],
    }
    result = diagnose_simulation(simulation)
    row = result["decision_rows"][0]
    assert row["pre_vol_gross"] == Decimal("0.9")
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


def test_diagnostic_rejects_missing_saved_inputs(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="simulation artifacts"):
        run_diagnostic(tmp_path / "missing", tmp_path / "out")


def test_covariance_proxy_is_decimal_reference_and_future_poison_changes_result() -> (
    None
):
    weights = {"A": Decimal("0.7"), "B": Decimal("0.3")}
    causal = {
        "A": [Decimal(".01"), Decimal("-.02")],
        "B": [Decimal(".02"), Decimal("-.01")],
    }
    poisoned = {
        "A": causal["A"] + [Decimal("100")],
        "B": causal["B"] + [Decimal("0")],
    }
    assert covariance_proxy(weights, causal) < Decimal(".1")
    assert covariance_proxy(weights, poisoned) != covariance_proxy(weights, causal)


def test_covariance_rejects_nonfinite_and_invalid_annualization() -> None:
    with pytest.raises(ValueError, match="non-finite"):
        covariance_proxy({"A": Decimal(1)}, {"A": [Decimal("NaN")]})
    with pytest.raises(ValueError, match="positive"):
        annualized_covariance_proxy({"A": Decimal(1)}, {"A": [Decimal(0)]}, 0)


def test_adapter_installation_preserves_six_argument_engine_hook() -> None:
    class PrivateEngine:
        volatility_scale = None

    engine = PrivateEngine()
    install_covariance_floor_adapter(engine)
    assert callable(engine.volatility_scale)
    # The sixth cache argument is accepted by the real engine's hook.
    assert engine.volatility_scale.__name__ == "<lambda>"


def test_global_drawdown_uses_initial_peak_and_is_independent_of_latch() -> None:
    points = [
        EquityObservation(
            datetime(2024, 1, 1, tzinfo=UTC), Decimal("110"), Decimal("110"), {}
        ),
        EquityObservation(
            datetime(2024, 1, 2, tzinfo=UTC), Decimal("80"), Decimal("80"), {}
        ),
    ]
    assert global_drawdown(points, Decimal("100")) == Decimal(
        "27.27272727272727272727272727"
    )


def test_target_diagnostic_records_band_as_non_additive_stage() -> None:
    result = diagnose_simulation(
        {
            "weekly_targets": [
                {
                    "decided_at": "2024-01-01T00:00:00Z",
                    "symbol": "A",
                    "target_weight": "0.2",
                }
            ],
            "policy_events": [
                {
                    "at": "2024-01-01T00:00:00Z",
                    "kind": "band_skip",
                    "detail": "held band",
                }
            ],
        }
    )
    assert result["stages_are_overlapping_and_not_additive_cash_shares"]
    assert result["event_counts"]["band_skip"] == 1
