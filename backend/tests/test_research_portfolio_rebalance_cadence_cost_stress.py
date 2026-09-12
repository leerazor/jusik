from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from jusik.research_portfolio_models import PortfolioConfig
from jusik.research_portfolio_rebalance_cadence_cost_stress import (
    EVALUATION_CAP,
    FULL_EVALUATION_COUNT,
    RATE_3X,
    VARIANT_EVALUATION_COUNT,
    _cadence_config,
    preflight,
)


def test_cadence_study_contract() -> None:
    assert FULL_EVALUATION_COUNT == 24
    assert VARIANT_EVALUATION_COUNT == 24
    assert EVALUATION_CAP == 48
    base = PortfolioConfig()
    control = _cadence_config(base, 4, 1)
    variant = _cadence_config(base, 8, 3)
    assert control.low_turnover_weeks == 4
    assert variant.low_turnover_weeks == 8
    assert control.low_turnover_band == Decimal("0.02")
    assert variant.low_turnover_band == Decimal("0.02")
    assert variant.fee_rate == RATE_3X
    assert variant.initial_cash_krw == Decimal("100000000")
    assert variant.leveraged_etf_cap == Decimal("0.20")
    assert variant.drawdown_limit == Decimal("0.10")


@pytest.mark.parametrize("weeks", [0, 3, 9])
def test_cadence_boundary_rejected(weeks: int) -> None:
    with pytest.raises(ValueError):
        _cadence_config(PortfolioConfig(), weeks, 1)


def test_frozen_cost3_inputs_preflight() -> None:
    audit = Path(
        "/home/kwl/.local/share/jusik/portfolio-audit/"
        "portfolio-held-band-cost3-stress-v1-f9aecd54dffc4931a6100ac2de8c8cd3/experiment"
    )
    result = preflight(audit)
    assert result["evaluation_count"] == 24
    assert result["historical_calls"] == 0
