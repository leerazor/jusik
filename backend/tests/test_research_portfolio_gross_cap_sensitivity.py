from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from jusik.research_portfolio_gross_cap_sensitivity import (
    ARMS,
    EVALUATION_CAP,
    EquityObservation,
    _config,
    _verify_observations,
    cap_observations,
    global_drawdown,
)
from jusik.research_portfolio_models import (
    PortfolioCandidate,
    PortfolioConfig,
    PortfolioEquityPoint,
    PortfolioSimulation,
)


def _sim() -> PortfolioSimulation:
    return PortfolioSimulation.model_construct(
        candidate=PortfolioCandidate(id="equal", method="equal", gate="none"),
        period_start=date(2024, 1, 1),
        period_end=date(2024, 1, 2),
        metrics=type("M", (), {"initial_equity_krw": Decimal("100000000")})(),
        complete=True,
        incomplete_reasons=[],
        equity=[
            PortfolioEquityPoint(
                at=datetime(2024, 1, 2, tzinfo=UTC),
                equity_krw=Decimal("100000000"),
                cash_krw=Decimal("80000000"),
                drawdown_pct=Decimal("0"),
            )
        ],
        drawdown_latched=False,
        drawdown_latched_at=None,
        trades=[],
        weekly_targets=[],
        positions=[],
        contributions_krw={},
        split_cash_in_lieu_krw={},
        overlap_diagnostics={},
    )


def test_contract_constants_and_config() -> None:
    assert ARMS == (("control", Decimal("0.60")), ("variant", Decimal("0.80")))
    assert EVALUATION_CAP == 32
    config = _config(PortfolioConfig(), Decimal("0.80"), 3)
    assert config.gross_cap == Decimal("0.80")
    with pytest.raises(ValueError):
        _config(PortfolioConfig(), Decimal("0.70"), 1)


def test_observer_boundary_drawdown_and_cap_excess() -> None:
    at = datetime(2024, 1, 2, tzinfo=UTC)
    observation = EquityObservation(
        at,
        Decimal("100000000"),
        Decimal("80000000"),
        {"NVDA": Decimal("20000000"), "TQQQ": Decimal("0")},
    )
    simulation = _sim()
    _verify_observations(simulation, [observation], PortfolioConfig())
    assert global_drawdown([observation]) == Decimal("0")
    assert cap_observations([observation], PortfolioConfig())["excess"]["gross"] == []


def test_observer_rejects_negative_nonfinite_and_duplicate_order() -> None:
    at = datetime(2024, 1, 2, tzinfo=UTC)
    bad = EquityObservation(at, Decimal("100000000"), Decimal("100000001"), {})
    with pytest.raises(ValueError):
        _verify_observations(_sim(), [bad], PortfolioConfig())
