from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

import jusik.research_portfolio_exposure_cost as module
from jusik.research_entry_attribution import ARMS, COSTS, PERIODS
from jusik.research_portfolio_models import (
    PortfolioCandidate,
    PortfolioEquityPoint,
    PortfolioMetrics,
    PortfolioSimulation,
    PortfolioTrade,
)


def _simulation(
    *,
    points: list[PortfolioEquityPoint] | None = None,
    fee: str = "1",
    transaction_cost: str = "3",
    net_pnl: str = "100",
    trade_count: int = 1,
    initial: str = "100000000",
    turnover_pct: str = "0.0001",
) -> PortfolioSimulation:
    initial_decimal = Decimal(initial)
    trade = PortfolioTrade(
        decided_at=datetime(2024, 1, 1, tzinfo=UTC),
        executed_at=datetime(2024, 1, 1, tzinfo=UTC),
        symbol="AAA",
        side="buy",
        quantity=1,
        local_price=Decimal("100"),
        fx_rate=Decimal("1"),
        notional_krw=Decimal("100"),
        transaction_cost_krw=Decimal(transaction_cost),
        fx_cost_krw=Decimal("2"),
    )
    equity = (
        points
        if points is not None
        else [
            PortfolioEquityPoint(
                at=datetime(2024, 1, 1, tzinfo=UTC),
                equity_krw=initial_decimal,
                cash_krw=initial_decimal,
                drawdown_pct=Decimal("0"),
            ),
            PortfolioEquityPoint(
                at=datetime(2024, 1, 2, tzinfo=UTC),
                equity_krw=initial_decimal + Decimal(net_pnl),
                cash_krw=initial_decimal + Decimal(net_pnl) - Decimal("25"),
                drawdown_pct=Decimal("0"),
            ),
        ]
    )
    return PortfolioSimulation(
        candidate=PortfolioCandidate(
            id="portfolio_inverse_volatility_fx_vix_v1",
            method="inverse_volatility",
            gate="fx_vix",
        ),
        period_start=datetime(2024, 1, 1, tzinfo=UTC).date(),
        period_end=datetime(2024, 1, 2, tzinfo=UTC).date(),
        metrics=PortfolioMetrics(
            initial_equity_krw=initial_decimal,
            final_equity_krw=initial_decimal + Decimal(net_pnl),
            total_return_pct=Decimal("0"),
            max_drawdown_pct=Decimal("0"),
            trade_count=trade_count,
            transaction_cost_krw=Decimal(transaction_cost),
            fx_cost_krw=Decimal("2"),
            turnover_pct=Decimal(turnover_pct),
        ),
        complete=True,
        incomplete_reasons=[],
        drawdown_latched=False,
        drawdown_latched_at=None,
        equity=equity,
        trades=[trade] if trade_count else [],
        weekly_targets=[],
        positions=[],
        contributions_krw={"AAA": Decimal("0")},
        split_cash_in_lieu_krw={},
        overlap_diagnostics={},
        policy="low_turnover_combined",
        policy_events=[],
    )


def _synthetic(
    **kwargs: Any,
) -> tuple[dict[tuple[str, str, int], PortfolioSimulation], list[dict[str, Any]]]:
    simulations: dict[tuple[str, str, int], PortfolioSimulation] = {}
    rows: list[dict[str, Any]] = []
    for period in PERIODS:
        for cost in COSTS:
            for arm in ARMS:
                simulations[(period, arm, cost)] = _simulation(**kwargs)
            rows.append(
                {
                    "period": period,
                    "cost_multiplier": cost,
                    **{
                        f"{prefix}{field}": Decimal(value)
                        for prefix in ("control_", "variant_")
                        for field, value in (
                            ("fee", kwargs.get("fee", "1")),
                            ("slippage", "2"),
                            ("transaction_cost", kwargs.get("transaction_cost", "3")),
                            ("fx_cost", "2"),
                            ("net_pnl", kwargs.get("net_pnl", "100")),
                        )
                    },
                    "control_trade_count": kwargs.get("trade_count", 1),
                    "variant_trade_count": kwargs.get("trade_count", 1),
                }
            )
    return simulations, rows


def _patch_analyze(
    monkeypatch: pytest.MonkeyPatch,
    simulations: dict[tuple[str, str, int], PortfolioSimulation],
    rows: list[dict[str, Any]],
) -> None:
    monkeypatch.setattr(
        module,
        "attribution_analyze",
        lambda _: {"symbol_rows": rows, "source_hashes": {}},
    )
    monkeypatch.setattr(module, "_load_simulations", lambda _: (simulations, {}))


def test_analyze_positive_cost_formula_uses_production_outputs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    simulations, rows = _synthetic()
    _patch_analyze(monkeypatch, simulations, rows)
    result = module.analyze(tmp_path)
    values = [
        r["diagnostic_net_pnl_krw"]
        for r in result["arithmetic"]
        if r["period"] == "fold_1" and r["arm"] == "control"
    ]
    assert values == [Decimal("100"), Decimal("95"), Decimal("90")]
    assert values == sorted(values, reverse=True)
    assert result["actual"][0]["turnover_krw"] == Decimal("100")


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("fee", "2", "cost reconciliation"),
        ("net_pnl", "101", "net PnL"),
        ("trade_count", 2, "trade count"),
        ("turnover_pct", "0", "turnover"),
        ("initial", "1", "initial capital"),
    ],
)
def test_analyze_rejects_accounting_and_bounds_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, field: str, value: Any, match: str
) -> None:
    if field == "net_pnl":
        simulations, rows = _synthetic()
        for row in rows:
            row["control_net_pnl"] = Decimal(str(value))
            row["variant_net_pnl"] = Decimal(str(value))
    else:
        simulations, rows = _synthetic(**{field: value})
    _patch_analyze(monkeypatch, simulations, rows)
    with pytest.raises(ValueError, match=match):
        module.analyze(tmp_path)


def test_exposure_uses_sorted_utc_last_observation_and_boundary() -> None:
    points = [
        PortfolioEquityPoint(
            at=datetime(2024, 1, 1, 22, tzinfo=UTC),
            equity_krw=Decimal("100"),
            cash_krw=Decimal("75"),
            drawdown_pct=Decimal("0"),
        ),
        PortfolioEquityPoint(
            at=datetime(2024, 1, 1, 1, tzinfo=UTC),
            equity_krw=Decimal("100"),
            cash_krw=Decimal("80"),
            drawdown_pct=Decimal("0"),
        ),
    ]
    exposure, reason, daily = module._exposure(_simulation(points=points))
    assert (exposure, reason, daily) == (
        Decimal("25"),
        None,
        {"2024-01-01": Decimal("25")},
    )
    boundary = [
        points[0].model_copy(
            update={"at": datetime.fromisoformat("2024-01-02T00:00:00+09:00")}
        ),
        points[1].model_copy(update={"at": datetime(2024, 1, 1, 15, tzinfo=UTC)}),
        points[0].model_copy(update={"at": datetime(2024, 1, 2, 9, tzinfo=UTC)}),
    ]
    assert module._exposure(_simulation(points=boundary))[2] == {
        "2024-01-01": Decimal("20"),
        "2024-01-02": Decimal("25"),
    }


def test_zero_equity_returns_none_with_explicit_reason() -> None:
    point = PortfolioEquityPoint(
        at=datetime(2024, 1, 1, tzinfo=UTC),
        equity_krw=Decimal("0"),
        cash_krw=Decimal("0"),
        drawdown_pct=Decimal("0"),
    )
    assert module._exposure(_simulation(points=[point])) == (
        None,
        "no valid UTC-day equity points or zero equity",
        {},
    )


def test_no_trades_analyze_produces_zero_costs_and_pnl(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    simulations, rows = _synthetic(
        trade_count=0, net_pnl="0", transaction_cost="0", fee="0", turnover_pct="0"
    )
    for row in rows:
        for prefix in ("control_", "variant_"):
            row[f"{prefix}slippage"] = Decimal("0")
            row[f"{prefix}fx_cost"] = Decimal("0")
    for key, simulation in simulations.items():
        metrics = simulation.metrics.model_copy(update={"fx_cost_krw": Decimal("0")})
        equity = [
            point.model_copy(update={"cash_krw": point.equity_krw})
            for point in simulation.equity
        ]
        simulations[key] = simulation.model_copy(
            update={"metrics": metrics, "equity": equity}
        )
    _patch_analyze(monkeypatch, simulations, rows)
    result = module.analyze(tmp_path)
    assert len(result["actual"]) == 32
    assert all(
        row[field] == 0
        for row in result["actual"]
        for field in (
            "trade_count",
            "turnover_krw",
            "turnover_percent",
            "fee_krw",
            "slippage_krw",
            "transaction_cost_krw",
            "fx_cost_krw",
            "net_pnl_krw",
        )
    )
    assert all(row["invested_percent"] == 0 for row in result["daily"])
    assert all(row["diagnostic_net_pnl_krw"] == 0 for row in result["arithmetic"])


def test_empty_equity_and_write_outputs_are_safe(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    empty = _simulation(points=[])
    assert module._exposure(empty) == (
        None,
        "no valid UTC-day equity points or zero equity",
        {},
    )
    simulations, rows = _synthetic()
    _patch_analyze(monkeypatch, simulations, rows)
    first, second = (
        module.analyze(tmp_path / "input"),
        module.analyze(tmp_path / "input"),
    )
    module.write_outputs(first, tmp_path / "a")
    module.write_outputs(second, tmp_path / "b")
    names = (
        "diagnostics.json",
        "assumptionsmanifest.json",
        "actual.csv",
        "daily.csv",
        "comparisons.csv",
        "arithmetic.csv",
        "report.md",
    )
    assert all(
        (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()
        for name in names
    )
    with pytest.raises(ValueError, match="overwrite"):
        module.write_outputs(first, tmp_path / "a")


def test_missing_input_and_hash_mismatch_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        module.analyze(tmp_path / "missing")
    (tmp_path / "results.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        module.analyze(tmp_path)
