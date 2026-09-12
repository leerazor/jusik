from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

import jusik.research_portfolio_exposure_cost as module
from jusik.research_entry_attribution import ARMS, COSTS, PERIODS
from jusik.research_portfolio_models import PortfolioEquityPoint, PortfolioTrade


def _simulation(
    *, points: list[Any] | None = None, trades: list[Any] | None = None
) -> Any:
    return SimpleNamespace(
        equity=points
        or [
            PortfolioEquityPoint(
                at=datetime(2024, 1, 2, tzinfo=UTC),
                equity_krw=Decimal("100"),
                cash_krw=Decimal("75"),
                drawdown_pct=Decimal("0"),
            ),
            PortfolioEquityPoint(
                at=datetime(2024, 1, 1, tzinfo=UTC),
                equity_krw=Decimal("100"),
                cash_krw=Decimal("80"),
                drawdown_pct=Decimal("0"),
            ),
        ],
        trades=trades or [],
    )


def test_exposure_uses_last_observation_after_utc_sorting() -> None:
    exposure, reason, daily = module._exposure(_simulation())
    assert reason is None
    assert exposure == Decimal("25")
    assert daily["2024-01-01"] == Decimal("20")
    assert daily["2024-01-02"] == Decimal("25")


def test_zero_equity_returns_none_without_interpolation() -> None:
    point = PortfolioEquityPoint(
        at=datetime(2024, 1, 1, tzinfo=UTC),
        equity_krw=Decimal("0"),
        cash_krw=Decimal("0"),
        drawdown_pct=Decimal("0"),
    )
    exposure, reason, daily = module._exposure(_simulation(points=[point]))
    assert exposure is None and daily == {}
    assert reason == "no valid UTC-day equity points or zero equity"


def test_future_decision_and_invalid_bounds_are_rejected() -> None:
    trade = PortfolioTrade(
        decided_at=datetime(2024, 1, 2, tzinfo=UTC),
        executed_at=datetime(2024, 1, 1, tzinfo=UTC),
        symbol="AAA",
        side="buy",
        quantity=1,
        local_price=Decimal("1"),
        fx_rate=Decimal("1"),
        notional_krw=Decimal("1"),
        transaction_cost_krw=Decimal("0"),
        fx_cost_krw=Decimal("0"),
    )
    with pytest.raises(ValueError, match="decided_at"):
        module._exposure(_simulation(trades=[trade]))


def test_arithmetic_cost_formula_and_nonincreasing_positive_cost() -> None:
    row: dict[str, Any] = {
        "period": "fold_1",
        "arm": "control",
        "cost_multiplier": 1,
        "net_pnl_krw": Decimal("100"),
        "transaction_cost_krw": Decimal("3"),
        "fx_cost_krw": Decimal("2"),
    }
    values = []
    for multiplier in module.DIAGNOSTIC_MULTIPLIERS:
        values.append(
            cast(Decimal, row["net_pnl_krw"])
            - (multiplier - 1)
            * (
                cast(Decimal, row["transaction_cost_krw"])
                + cast(Decimal, row["fx_cost_krw"])
            )
        )
    assert values == [Decimal("100"), Decimal("95"), Decimal("90")]


def test_analyze_synthetic_all_rows_no_trades_and_initial_capital(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    simulations: dict[tuple[str, str, int], Any] = {}
    symbol_rows: list[dict[str, Any]] = []
    for period in PERIODS:
        for arm in ARMS:
            for cost in COSTS:
                sim = _simulation()
                sim.metrics = SimpleNamespace(
                    initial_equity_krw=module.INITIAL_CAPITAL_KRW,
                    final_equity_krw=module.INITIAL_CAPITAL_KRW,
                    turnover_pct=Decimal("0"),
                )
                simulations[(period, arm, cost)] = sim
                if arm == "variant":
                    symbol_rows.append(
                        {
                            "period": period,
                            "cost_multiplier": cost,
                            **{
                                f"{prefix}{field}": Decimal("0")
                                for prefix in ("control_", "variant_")
                                for field in (
                                    "fee",
                                    "slippage",
                                    "transaction_cost",
                                    "fx_cost",
                                    "net_pnl",
                                )
                            },
                            "control_trade_count": 0,
                            "variant_trade_count": 0,
                        }
                    )
    monkeypatch.setattr(
        module,
        "attribution_analyze",
        lambda _: {"symbol_rows": symbol_rows, "source_hashes": {}},
    )
    monkeypatch.setattr(module, "_load_simulations", lambda _: (simulations, {}))
    result = module.analyze(tmp_path)
    assert len(result["actual"]) == 32
    assert len(result["comparisons"]) == 16
    assert len(result["arithmetic"]) == 48
    assert all(
        row["trade_count"] == 0 and row["turnover_krw"] == 0 for row in result["actual"]
    )
    assert all(row["net_pnl_krw"] == 0 for row in result["actual"])


def test_analyze_missing_input_and_hash_mismatch_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        module.analyze(tmp_path / "missing")
    (tmp_path / "results.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        module.analyze(tmp_path)
