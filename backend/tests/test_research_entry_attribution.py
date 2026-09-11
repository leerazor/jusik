from datetime import UTC, date, datetime
from decimal import Decimal, getcontext

import pytest

import jusik.research_entry_attribution as attribution_module
from jusik.research_entry_attribution import (
    TOLERANCE,
    _concentration,
    _read_hashed,
    _validate_frozen_metadata,
    analyze,
    attribute_simulation,
    monthly_portfolio,
)
from jusik.research_portfolio_models import (
    PortfolioCandidate,
    PortfolioEquityPoint,
    PortfolioMetrics,
    PortfolioPosition,
    PortfolioSimulation,
    PortfolioTrade,
)

AT = datetime(2024, 1, 15, 13, 30, tzinfo=UTC)


def _trade(
    side: str,
    price: str,
    notional: str,
    tx: str,
    *,
    fx: str = "1",
    fx_cost: str = "0",
) -> PortfolioTrade:
    return PortfolioTrade(
        decided_at=AT,
        executed_at=AT,
        symbol="AAA",
        side=side,
        quantity=1,
        local_price=Decimal(price),
        fx_rate=Decimal(fx),
        notional_krw=Decimal(notional),
        transaction_cost_krw=Decimal(tx),
        fx_cost_krw=Decimal(fx_cost),
    )


def _simulation(
    trades: list[PortfolioTrade],
    contribution: str,
    final: str,
    *,
    position: PortfolioPosition | None = None,
    split: str = "0",
    cost: int = 1,
    points: list[PortfolioEquityPoint] | None = None,
) -> PortfolioSimulation:
    initial = Decimal("1000")
    metrics = PortfolioMetrics(
        initial_equity_krw=initial,
        final_equity_krw=Decimal(final),
        total_return_pct=(Decimal(final) - initial) / initial * 100,
        max_drawdown_pct=Decimal("0"),
        trade_count=len(trades),
        transaction_cost_krw=sum((t.transaction_cost_krw for t in trades), Decimal(0)),
        fx_cost_krw=sum((t.fx_cost_krw for t in trades), Decimal(0)),
        turnover_pct=Decimal("0"),
    )
    equity = points or [
        PortfolioEquityPoint(
            at=datetime(2024, 1, 1, tzinfo=UTC),
            equity_krw=initial,
            cash_krw=initial,
            drawdown_pct=Decimal("0"),
        ),
        PortfolioEquityPoint(
            at=datetime(2024, 1, 31, tzinfo=UTC),
            equity_krw=Decimal(final),
            cash_krw=Decimal(final) - (position.value_krw if position else 0),
            drawdown_pct=Decimal("0"),
        ),
    ]
    return PortfolioSimulation(
        candidate=PortfolioCandidate(
            id="portfolio_inverse_volatility_fx_vix_v1",
            method="inverse_volatility",
            gate="fx_vix",
        ),
        period_start=date(2024, 1, 1),
        period_end=date(2024, 1, 31),
        metrics=metrics,
        complete=True,
        incomplete_reasons=[],
        drawdown_latched=False,
        drawdown_latched_at=None,
        equity=equity,
        trades=trades,
        weekly_targets=[],
        positions=[position] if position else [],
        contributions_krw={"AAA": Decimal(contribution)},
        split_cash_in_lieu_krw={"AAA": Decimal(split)} if split != "0" else {},
        overlap_diagnostics={},
        policy="low_turnover_combined",
        policy_events=[],
    )


def test_buy_and_sell_costs_do_not_double_charge_slippage() -> None:
    buy = _trade("buy", "100.1", "100.1", "0.2001")
    sell = _trade("sell", "99.9", "99.9", "0.1999")
    simulation = _simulation([buy, sell], "-0.4", "999.6")
    result = attribute_simulation(simulation, 1)
    row = result["rows"]["AAA"]
    assert row["fee"] == Decimal("0.2")
    assert row["slippage"] == Decimal("0.2")
    assert row["net_pnl"] == Decimal("-0.4")


def test_remaining_position_and_split_cash_are_accounted_once() -> None:
    buy = _trade("buy", "100.1", "100.1", "0.2001")
    position = PortfolioPosition(
        symbol="AAA",
        quantity=1,
        currency="KRW",
        local_close=Decimal("110"),
        fx_rate=Decimal("1"),
        value_krw=Decimal("110"),
        weight=Decimal("0.1"),
        valued_at=datetime(2024, 1, 31, tzinfo=UTC),
        fx_observed_on=None,
    )
    simulation = _simulation(
        [buy], "19.7999", "1019.7999", position=position, split="10"
    )
    result = attribute_simulation(simulation, 1)
    assert result["rows"]["AAA"]["terminal"] == Decimal("110")
    assert result["rows"]["AAA"]["split_cash_in_lieu"] == Decimal("10")
    assert result["rows"]["AAA"]["net_pnl"] == Decimal("19.7999")


def test_precision_and_residual_boundary() -> None:
    simulation = _simulation([], "0", "1000")
    assert attribute_simulation(simulation, 1)["residual"] == Decimal("0")
    assert TOLERANCE == Decimal("0.000001")


def test_cost_two_with_fx_cost_is_signed_and_precision_independent() -> None:
    buy = _trade("buy", "100.2", "100.2", "0.4004", fx="1", fx_cost="0.4")
    simulation = _simulation([buy], "-100.8004", "899.1996", cost=2)
    simulation = simulation.model_copy(
        update={
            "metrics": simulation.metrics.model_copy(
                update={"fx_cost_krw": Decimal("0.4")}
            )
        }
    )
    result = attribute_simulation(simulation, 2)
    assert result["rows"]["AAA"]["net_pnl"] == Decimal("-100.8004")


def test_residual_above_tolerance_is_rejected() -> None:
    simulation = _simulation([], "0", "1000.000002")
    with pytest.raises(ValueError, match="sum PnL"):
        attribute_simulation(simulation, 1)


def test_residual_exactly_at_tolerance_is_accepted() -> None:
    simulation = _simulation([], "0", "1000.000001")
    assert attribute_simulation(simulation, 1)["residual"] == Decimal("-0.000001")


def test_duplicate_trade_and_position_are_rejected() -> None:
    buy = _trade("buy", "100.1", "100.1", "0.2001")
    with pytest.raises(ValueError, match="duplicate trade"):
        attribute_simulation(_simulation([buy, buy], "0", "1000"), 1)
    position = PortfolioPosition(
        symbol="AAA",
        quantity=1,
        currency="KRW",
        local_close=Decimal("100"),
        fx_rate=Decimal("1"),
        value_krw=Decimal("100"),
        weight=Decimal("0.1"),
        valued_at=datetime(2024, 1, 31, tzinfo=UTC),
        fx_observed_on=None,
    )
    duplicate = _simulation([], "0", "1000", position=position).model_copy(
        update={"positions": [position, position]}
    )
    with pytest.raises(ValueError, match="duplicate position"):
        attribute_simulation(duplicate, 1)


def test_incomplete_simulation_metadata_is_rejected() -> None:
    simulation = _simulation([], "0", "1000")
    row = {
        "artifact": "fold_1-b2_c1.json",
        "period": "fold_1",
        "arm": "control",
        "cost_multiplier": 1,
        "start": "2024-01-01",
        "end": "2024-01-31",
        "complete": True,
        **simulation.metrics.model_dump(mode="json"),
    }
    prereg = {
        "periods": [{"name": "fold_1", "start": "2024-01-01", "end": "2024-01-31"}],
        "candidate": simulation.candidate.model_dump(mode="json"),
        "policy": simulation.policy,
    }
    incomplete = simulation.model_copy(update={"complete": False})
    with pytest.raises(ValueError, match="incomplete"):
        _validate_frozen_metadata(incomplete, row, prereg)
    with pytest.raises(ValueError, match="period metadata"):
        _validate_frozen_metadata(simulation, {**row, "start": "2024-01-02"}, prereg)
    with pytest.raises(ValueError, match="evaluation is incomplete"):
        _validate_frozen_metadata(simulation, {**row, "complete": False}, prereg)


def test_hash_loader_rejects_missing_file_and_core_hash_mismatch(
    tmp_path, monkeypatch
) -> None:
    with pytest.raises(FileNotFoundError):
        _read_hashed(tmp_path / "missing.json", "0" * 64, "missing")
    results = {"specification_sha256": "", "evaluations": []}
    prereg = {
        "evaluation_count": 32,
        "core_hashes": {"research_portfolio_models.py": "0" * 64},
    }
    import hashlib
    import json

    prereg_bytes = (json.dumps(prereg) + "\n").encode()
    prereg_hash = hashlib.sha256(prereg_bytes).hexdigest()
    results["specification_sha256"] = prereg_hash
    results_bytes = (json.dumps(results) + "\n").encode()
    results_hash = hashlib.sha256(results_bytes).hexdigest()
    (tmp_path / "preregistration.json").write_bytes(prereg_bytes)
    (tmp_path / "results.json").write_bytes(results_bytes)
    monkeypatch.setattr(attribution_module, "PREREGISTRATION_SHA256", prereg_hash)
    monkeypatch.setattr(attribution_module, "RESULTS_SHA256", results_hash)
    monkeypatch.setattr(
        attribution_module, "CORE_FILES", ("research_portfolio_models.py",)
    )
    with pytest.raises(ValueError, match="current source differs"):
        analyze(tmp_path)


def test_utc_offset_and_same_instant_tie_keep_original_last_point() -> None:
    points = [
        PortfolioEquityPoint(
            at=datetime(2024, 1, 2, tzinfo=UTC),
            equity_krw=Decimal("1000"),
            cash_krw=Decimal("1000"),
            drawdown_pct=Decimal("0"),
        ),
        PortfolioEquityPoint(
            at=datetime.fromisoformat("2024-01-31T23:00:00+01:00"),
            equity_krw=Decimal("1001"),
            cash_krw=Decimal("1001"),
            drawdown_pct=Decimal("0"),
        ),
        PortfolioEquityPoint(
            at=datetime.fromisoformat("2024-02-01T00:00:00+02:00"),
            equity_krw=Decimal("1002"),
            cash_krw=Decimal("1002"),
            drawdown_pct=Decimal("0"),
        ),
        PortfolioEquityPoint(
            at=datetime(2024, 2, 28, tzinfo=UTC),
            equity_krw=Decimal("1003"),
            cash_krw=Decimal("1003"),
            drawdown_pct=Decimal("0"),
        ),
    ]
    simulation = _simulation([], "0", "1003", points=points).model_copy(
        update={"period_end": date(2024, 2, 29)}
    )
    rows = monthly_portfolio(simulation, {})
    assert rows[0]["equity"] == Decimal("1002")
    previous_precision = getcontext().prec
    try:
        getcontext().prec = 6
        assert monthly_portfolio(simulation, {}) == rows
    finally:
        getcontext().prec = previous_precision


def test_monthly_portfolio_keeps_no_trade_month_and_rejects_gap() -> None:
    points = [
        PortfolioEquityPoint(
            at=datetime(2024, 1, 2, 1, tzinfo=UTC),
            equity_krw=Decimal("1000"),
            cash_krw=Decimal("1000"),
            drawdown_pct=Decimal("0"),
        ),
        PortfolioEquityPoint(
            at=datetime(2024, 2, 29, 20, tzinfo=UTC),
            equity_krw=Decimal("1000"),
            cash_krw=Decimal("1000"),
            drawdown_pct=Decimal("0"),
        ),
        PortfolioEquityPoint(
            at=datetime(2024, 3, 29, 20, tzinfo=UTC),
            equity_krw=Decimal("1010"),
            cash_krw=Decimal("1010"),
            drawdown_pct=Decimal("0"),
        ),
    ]
    simulation = _simulation([], "0", "1010", points=points)
    simulation = simulation.model_copy(update={"period_end": date(2024, 3, 31)})
    rows = monthly_portfolio(simulation, {})
    assert [row["month"] for row in rows] == ["2024-01", "2024-02", "2024-03"]
    assert rows[1]["pnl"] == Decimal("0")
    missing = simulation.model_copy(update={"equity": [points[0], points[-1]]})
    with pytest.raises(ValueError, match="missing UTC month"):
        monthly_portfolio(missing, {})


def test_concentration_uses_positive_and_negative_denominators_with_ties() -> None:
    rows = [
        {"symbol": "ZZZ", "delta_net_pnl": Decimal("10")},
        {"symbol": "AAA", "delta_net_pnl": Decimal("10")},
        {"symbol": "BBB", "delta_net_pnl": Decimal("-5")},
        {"symbol": "CCC", "delta_net_pnl": Decimal("-5")},
    ]
    concentration = _concentration(rows)
    assert concentration["positive"]["symbol"] == "AAA"
    assert concentration["positive"]["percent"] == Decimal("50")
    assert concentration["negative"]["symbol"] == "BBB"
    assert concentration["negative"]["value"] == Decimal("-5")
    assert concentration["negative"]["percent"] == Decimal("50")
    assert _concentration([{"symbol": "AAA", "delta_net_pnl": Decimal("0")}]) == {
        "positive": None,
        "negative": None,
    }
