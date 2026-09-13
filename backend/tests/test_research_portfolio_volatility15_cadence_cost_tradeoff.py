from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

import jusik.research_portfolio_volatility15_cadence_cost_tradeoff as runner
from jusik.research_portfolio_models import PortfolioCandidate, PortfolioConfig


def test_config_is_closed_to_target_cadence_and_cost() -> None:
    base = PortfolioConfig()
    for cadence in (4, 8):
        config = runner._config(base, cadence, 3)
        assert config.volatility_target == Decimal("0.15")
        assert config.low_turnover_weeks == cadence
        assert config.low_turnover_band == Decimal("0.04")
        assert config.fee_rate == Decimal("0.003")
    for cadence, cost in ((0, 1), (5, 1), (4, 2), (4, 0)):
        with pytest.raises(ValueError):
            runner._config(base, cadence, cost)


def test_period_and_order_contract_keeps_controls_first() -> None:
    periods = [
        {"name": name, "start": "2024-01-01", "end": "2024-02-01"}
        for name in runner.PERIOD_NAMES
    ]
    assert [item["name"] for item in runner._periods({"periods": periods})] == list(
        runner.PERIOD_NAMES
    )
    names = [
        f"{period}-{arm}_c{cost}.json"
        for arm, _cadence in runner.ARMS
        for period in runner.PERIOD_NAMES
        for cost in runner.FULL_COSTS
    ]
    assert names[:16] == [
        f"{period}-control_c{cost}.json"
        for period in runner.PERIOD_NAMES
        for cost in runner.FULL_COSTS
    ]
    assert set(names) == runner._expected_names()


def test_prior_variant_mapping_is_explicit_and_exact() -> None:
    prior = next(
        Path("/home/kwl/.local/share/jusik/portfolio-audit").glob(
            "portfolio-volatility-target-cash-sensitivity-v1-*/experiment"
        )
    )
    prereg, _source, _base = runner._load_contract(prior)
    assert runner._periods(prereg)
    mapped = "fold_3-control_c3.json".replace("-control_", "-variant_")
    assert mapped == "fold_3-variant_c3.json"


def test_synthetic_engine_uses_monday_anchor_for_four_and_eight_weeks(
    tmp_path: Path,
) -> None:
    from tests.test_research_portfolio import _source

    engine_path = Path(__file__).parents[1] / "jusik" / "research_portfolio_engine.py"
    _original, variant_path = runner._copy_engine(engine_path, tmp_path)
    engine = runner._load_copy(variant_path, "cadence_synthetic_engine")
    source = _source()
    candidate = PortfolioCandidate(id="equal", method="equal", gate="none")
    engine.target_weights = lambda *_args: ({"KRTEST": Decimal("0.20")}, {}, None)
    engine.volatility_scale = lambda *_args: (Decimal("1"), Decimal("0"))
    start = date(2024, 1, 8)
    end = date(2024, 3, 29)
    for cadence, expected_rebalances in ((4, 3), (8, 2)):
        config = PortfolioConfig(
            initial_cash_krw=Decimal("1000000"),
            low_turnover_weeks=cadence,
            low_turnover_band=Decimal("0"),
            gross_cap=Decimal("1"),
            symbol_cap=Decimal("1"),
            leveraged_etf_cap=Decimal("1"),
            fee_rate=Decimal("0"),
            slippage_rate=Decimal("0"),
            fx_spread_rate=Decimal("0"),
        )
        result = engine.simulate(
            source, candidate, start, end, config, "low_turnover_combined"
        )
        skips = [
            event
            for event in result.policy_events
            if event.kind == "frequency_skip"
        ]
        assert len(result.weekly_targets) // 2 == expected_rebalances
        assert all(event.decided_at.weekday() == 0 for event in result.weekly_targets)
        assert len(skips) == (12 - expected_rebalances)
