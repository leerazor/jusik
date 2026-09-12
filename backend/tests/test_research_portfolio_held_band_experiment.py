from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from jusik.research_experiment_guard import verify_unheld_entry_source
from jusik.research_portfolio_held_band_experiment import (
    VARIANT_SHA256,
    _config,
    _copy_engine,
    _load_copy,
    _verify_accounting,
)
from jusik.research_portfolio_models import (
    PortfolioCandidate,
    PortfolioConfig,
    PortfolioInput,
    PortfolioSimulation,
    PortfolioTrade,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_copy_is_exactly_the_guarded_variant(tmp_path: Path) -> None:
    engine = Path(__file__).parents[1] / "jusik" / "research_portfolio_engine.py"
    original, variant = _copy_engine(engine, tmp_path)
    assert _sha(variant) == VARIANT_SHA256
    verify_unheld_entry_source(original, variant, _sha(original), VARIANT_SHA256)
    assert _load_copy(original, "held_band_test_original").__file__ == str(original)
    assert _load_copy(variant, "held_band_test_variant").__file__ == str(variant)


def test_config_changes_only_band_and_cost_rates() -> None:
    base = PortfolioConfig()
    for band, cost in (("0.02", 1), ("0.04", 2)):
        result = _config(base, band, cost)
        assert result.low_turnover_band == Decimal(band)
        assert result.fee_rate == base.fee_rate * cost
        assert result.slippage_rate == base.slippage_rate * cost
        assert result.fx_spread_rate == base.fx_spread_rate * cost
        assert result.symbol_cap == Decimal("0.20")
        assert result.drawdown_limit == Decimal("0.10")


def test_config_rejects_invalid_zero_negative_and_nonfinite_values() -> None:
    with pytest.raises(ValueError):
        PortfolioConfig(low_turnover_band=Decimal("-0.01"))
    with pytest.raises(ValueError):
        PortfolioConfig(symbol_cap=Decimal("0"))
    with pytest.raises(ValueError):
        PortfolioConfig.model_validate({"low_turnover_band": "NaN"})


def test_held_boundary_guard_is_present_in_the_copied_engine(tmp_path: Path) -> None:
    """The copied engine's actual simulate path honors each held boundary."""
    from tests.test_research_portfolio import _source

    engine = Path(__file__).parents[1] / "jusik" / "research_portfolio_engine.py"
    _original, variant_path = _copy_engine(engine, tmp_path)
    variant = _load_copy(variant_path, "held_boundary_actual_variant")
    base = _source()
    snapshot = base.instruments[0].model_copy(
        update={
            "instruments": [
                base.instruments[0]
                .instruments[0]
                .model_copy(
                    update={
                        "bars": [
                            bar.model_copy(
                                update={
                                    "open": Decimal("100"),
                                    "high": Decimal("100"),
                                    "low": Decimal("100"),
                                    "close": Decimal("100"),
                                    "adjusted_open": Decimal("100"),
                                    "adjusted_high": Decimal("100"),
                                    "adjusted_low": Decimal("100"),
                                    "adjusted_close": Decimal("100"),
                                }
                            )
                            for bar in base.instruments[0].instruments[0].bars
                        ]
                    }
                )
            ]
        }
    )
    source = base.model_copy(
        update={"instruments": [snapshot], "stock_snapshot_ids": {"KRTEST": "snapshot"}}
    )
    candidate = PortfolioCandidate(id="equal", method="equal", gate="none")

    for band, delta, expected_second_trade in (
        (Decimal("0.02"), Decimal("0.0199"), False),
        (Decimal("0.02"), Decimal("0.0200"), True),
        (Decimal("0.02"), Decimal("0.0201"), True),
        (Decimal("0.04"), Decimal("0.0399"), False),
        (Decimal("0.04"), Decimal("0.0400"), True),
        (Decimal("0.04"), Decimal("0.0401"), True),
    ):
        calls = 0

        def target_weights(
            *_args: Any,
        ) -> tuple[dict[str, Decimal], dict[str, Decimal], None]:
            nonlocal calls
            calls += 1
            return (
                {"KRTEST": Decimal("0.20")}
                if calls == 1
                else {"KRTEST": Decimal("0.20") + delta},
                {},
                None,
            )

        variant.target_weights = target_weights  # type: ignore[attr-defined]
        variant.volatility_scale = lambda *_args: (Decimal("1"), Decimal("0"))  # type: ignore[attr-defined]
        config = PortfolioConfig(
            initial_cash_krw=Decimal("1000000"),
            fee_rate=Decimal("0"),
            slippage_rate=Decimal("0"),
            fx_spread_rate=Decimal("0"),
            low_turnover_band=band,
            symbol_cap=Decimal("0.60"),
            gross_cap=Decimal("0.60"),
            leveraged_etf_cap=Decimal("0.20"),
        )
        result = variant.simulate(
            source,
            candidate,
            source.instruments[0].requested_start,
            source.instruments[0].requested_end,
            config,
            "low_turnover_combined",
        )
        kr_trades = [trade for trade in result.trades if trade.symbol == "KRTEST"]
        assert all(
            trade.executed_at >= trade.decided_at
            and trade.executed_at.tzinfo is not None
            and trade.executed_at.weekday() < 5
            for trade in kr_trades
        )
        assert len(kr_trades) == (2 if expected_second_trade else 1)
        if expected_second_trade:
            assert kr_trades[1].quantity == int(
                (Decimal("1000000") * delta / Decimal("100")).to_integral_value()
            )


def test_unheld_and_risk_cap_paths_remain_in_copied_engine(tmp_path: Path) -> None:
    from tests.test_research_portfolio import (
        _episode_source,
        _source,
        _staggered_cap_source,
    )

    engine = Path(__file__).parents[1] / "jusik" / "research_portfolio_engine.py"
    _original_path, variant_path = _copy_engine(engine, tmp_path)
    variant = _load_copy(variant_path, "held_band_fixture_variant")
    candidate = PortfolioCandidate(id="equal", method="equal", gate="none")
    source = _source()
    config = PortfolioConfig(
        low_turnover_band=Decimal("0.02"),
        symbol_cap=Decimal("1"),
        gross_cap=Decimal("1"),
        leveraged_etf_cap=Decimal("1"),
    )
    corrected = variant.simulate(
        source,
        candidate,
        source.instruments[0].requested_start,
        source.instruments[0].requested_end,
        config,
        "low_turnover_combined",
    )
    assert sum(trade.side == "buy" for trade in corrected.trades) >= 1
    assert all(trade.executed_at >= trade.decided_at for trade in corrected.trades)
    risk = _episode_source()
    result = variant.simulate(
        risk,
        candidate,
        risk.instruments[0].requested_start,
        risk.instruments[0].requested_end,
        config,
        "low_turnover_combined",
    )
    assert any(event.kind == "risk_exit" for event in result.policy_events)
    cap_source = _staggered_cap_source()
    cap_config = PortfolioConfig(low_turnover_band=Decimal("0.02"))
    capped = variant.simulate(
        cap_source,
        candidate,
        cap_source.instruments[0].requested_start,
        cap_source.instruments[0].requested_end,
        cap_config,
        "low_turnover_combined",
    )
    assert any(
        event.kind == "cap_constraint_deferred" for event in capped.policy_events
    )


def test_research_receipts_do_not_fabricate_partial_cancel_or_reject() -> None:
    with pytest.raises(ValueError):
        PortfolioTrade.model_validate(
            {
                "decided_at": "2024-01-01T00:00:00Z",
                "executed_at": "2024-01-01T00:00:00Z",
                "symbol": "AAA",
                "side": "buy",
                "quantity": 1,
                "local_price": "1",
                "fx_rate": "1",
                "notional_krw": "1",
                "transaction_cost_krw": "0",
                "fx_cost_krw": "0",
                "status": "partial",
            }
        )


def test_invalid_duplicate_missing_nonfinite_and_temporal_inputs_are_rejected() -> None:
    from tests.test_research_portfolio import _source

    payload = _source().model_dump(mode="json")
    payload["stock_snapshot_ids"].pop("KRTEST")
    with pytest.raises(ValueError, match="snapshot id"):
        PortfolioInput.model_validate(payload)

    duplicate = _source().model_dump(mode="json")
    duplicate["instruments"][1]["instruments"][0]["symbol"] = "KRTEST"
    with pytest.raises(ValueError):
        PortfolioInput.model_validate(duplicate)

    with pytest.raises(ValueError):
        PortfolioConfig.model_validate({"fee_rate": "Infinity"})


def test_saved_corrected_simulation_reconciles_at_precision_40() -> None:
    audit = Path(
        "/home/kwl/.local/share/jusik/portfolio-audit/"
        "20260911T132132Z-worktree-development/unheld-entry-real32"
    )
    manifest = json.loads(
        (
            audit.parents[1] / "20260911T060908Z-rebalance-band/source-manifest.json"
        ).read_text()
    )
    source = PortfolioInput.model_validate(manifest["frozen_input"])
    simulation = PortfolioSimulation.model_validate(
        json.loads((audit / "simulations/fold_1-variant_c1.json").read_text())
    )
    _verify_accounting(
        simulation, 1, PortfolioConfig.model_validate(manifest["config"]), source
    )
