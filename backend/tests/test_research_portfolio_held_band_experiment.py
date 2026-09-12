from __future__ import annotations

import hashlib
from decimal import Decimal
from pathlib import Path

import pytest

from jusik.research_experiment_guard import verify_unheld_entry_source
from jusik.research_portfolio_held_band_experiment import (
    VARIANT_SHA256,
    _config,
    _copy_engine,
    _load_copy,
)
from jusik.research_portfolio_models import (
    PortfolioCandidate,
    PortfolioConfig,
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
    """The copied engine contains the strict held-position '< band' guard."""
    engine = Path(__file__).parents[1] / "jusik" / "research_portfolio_engine.py"
    original, variant = _copy_engine(engine, tmp_path)
    original_text = original.read_text()
    variant_text = variant.read_text()
    original_guard = (
        "target_weight > 0\n"
        "                                and abs(actual - target_weight)"
    )
    variant_guard = (
        "target_weight > 0\n"
        "                                and positions[symbol] > 0\n"
        "                                and abs(actual - target_weight)"
    )
    assert original_guard in original_text
    assert variant_guard in variant_text
    assert variant_text.count("positions[symbol] > 0") == 1


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
