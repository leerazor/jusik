from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from jusik.research_engine import run_signal_backtest
from jusik.research_models import (
    DailyBar,
    ResearchInputSnapshot,
    ResearchRunRequest,
    SymbolSnapshot,
)
from jusik.research_risk import ResearchRiskPolicy, ResearchRiskReport


def _bar(
    trading_date: date,
    price: Decimal,
    *,
    close: Decimal | None = None,
    volume: int = 1000,
) -> DailyBar:
    closing = close if close is not None else price
    high = max(price, closing)
    low = min(price, closing)
    return DailyBar(
        date=trading_date,
        open=price,
        high=high,
        low=low,
        close=closing,
        volume=volume,
        adjusted_open=price,
        adjusted_high=high,
        adjusted_low=low,
        adjusted_close=closing,
    )


def _risk_fixture(
    symbols: list[str],
    comparison: dict[str, list[DailyBar]],
    *,
    fee_rate: str = "0",
    slippage_rate: str = "0",
) -> tuple[ResearchRunRequest, ResearchInputSnapshot]:
    first = date(2025, 1, 1)
    warmup = [_bar(first + timedelta(days=index), Decimal(10)) for index in range(60)]
    all_comparison_dates = sorted(
        {bar.date for bars in comparison.values() for bar in bars}
    )
    request = ResearchRunRequest(
        symbols=symbols,
        start_date=all_comparison_dates[0],
        end_date=all_comparison_dates[-1],
        initial_cash="1000",
        fee_rate=fee_rate,
        slippage_rate=slippage_rate,
        sell_tax_rate="0",
    )
    snapshot = ResearchInputSnapshot(
        captured_at=datetime(2026, 1, 1, tzinfo=UTC),
        requested_start=request.start_date,
        requested_end=request.end_date,
        symbols=[
            SymbolSnapshot(
                symbol=symbol,
                market="KOSPI",
                bars=[*warmup, *comparison[symbol]],
                source_url="https://example.com/daily",
            )
            for symbol in symbols
        ],
        events=[],
    )
    return request, snapshot


def test_risk_policy_rejects_invalid_rates() -> None:
    with pytest.raises(ValueError):
        ResearchRiskPolicy(max_symbol_entry_exposure=Decimal("NaN"))
    with pytest.raises(ValueError):
        ResearchRiskPolicy(max_total_entry_exposure=Decimal("-0.1"))
    with pytest.raises(ValueError):
        ResearchRiskPolicy(peak_close_drawdown_limit=Decimal())
    with pytest.raises(ValueError):
        ResearchRiskPolicy(
            max_symbol_entry_exposure=Decimal("0.7"),
            max_total_entry_exposure=Decimal("0.6"),
        )


def test_entry_budgets_include_costs_and_accumulate_across_buys() -> None:
    start = date(2025, 3, 2)
    symbols = ["000001", "000002", "000003", "000004"]
    comparison = {
        symbol: [_bar(start, Decimal(10)), _bar(start + timedelta(days=1), Decimal(10))]
        for symbol in symbols
    }
    request, snapshot = _risk_fixture(
        symbols, comparison, fee_rate="0.01", slippage_rate="0.01"
    )
    policy = ResearchRiskPolicy()
    report = ResearchRiskReport.start(policy, request.initial_cash)

    result = run_signal_backtest(
        request,
        snapshot,
        strategy_version="risk_budget",
        definition="test",
        signal=lambda _symbol, _bars: True,
        risk_policy=policy,
        risk_report=report,
    )

    buys = [trade for trade in result.trades if trade.side == "buy"]
    assert len(buys) == 4
    assert all(trade.notional + trade.fee <= Decimal(200) for trade in buys)
    assert sum((trade.notional + trade.fee for trade in buys), Decimal()) <= Decimal(
        600
    )
    assert result.equity[0].cash == request.initial_cash - sum(
        (trade.notional + trade.fee for trade in buys), Decimal()
    )


def test_price_gap_is_reported_as_exposure_drift() -> None:
    start = date(2025, 3, 2)
    request, snapshot = _risk_fixture(
        ["000001"],
        {
            "000001": [
                _bar(start, Decimal(10)),
                _bar(start + timedelta(days=1), Decimal(50)),
            ]
        },
    )
    policy = ResearchRiskPolicy()
    report = ResearchRiskReport.start(policy, request.initial_cash)

    run_signal_backtest(
        request,
        snapshot,
        strategy_version="risk_gap",
        definition="test",
        signal=lambda _symbol, _bars: True,
        risk_policy=policy,
        risk_report=report,
    )

    assert report.max_symbol_exposure_pct > Decimal(20)
    assert any(breach.scope == "000001" for breach in report.exposure_breaches)


def test_drawdown_equality_latches_through_missing_and_zero_volume_days() -> None:
    start = date(2025, 3, 2)
    clock = [_bar(start + timedelta(days=index), Decimal(10)) for index in range(4)]
    held = [
        _bar(start, Decimal(10), close=Decimal(5)),
        _bar(start + timedelta(days=2), Decimal(5), volume=0),
        _bar(start + timedelta(days=3), Decimal(5)),
    ]
    request, snapshot = _risk_fixture(
        ["000001", "000002"], {"000001": held, "000002": clock}
    )
    policy = ResearchRiskPolicy()
    report = ResearchRiskReport.start(policy, request.initial_cash)

    result = run_signal_backtest(
        request,
        snapshot,
        strategy_version="risk_latch",
        definition="test",
        signal=lambda symbol, _bars: symbol == "000001",
        risk_policy=policy,
        risk_report=report,
    )

    assert report.trigger_date == start
    assert report.trigger_drawdown_pct == Decimal(10)
    assert [trade.side for trade in result.trades] == ["buy", "sell"]
    assert result.trades[-1].date == start + timedelta(days=3)
    assert result.trades[-1].signal_date == start
    assert any(
        item.date == start + timedelta(days=2) for item in result.unfilled_decisions
    )
    assert result.open_positions == {}
    assert report.remaining_positions == {}


def test_risk_policy_without_report_still_latches_drawdown() -> None:
    start = date(2025, 3, 2)
    clock = [_bar(start + timedelta(days=index), Decimal(10)) for index in range(2)]
    falling = [
        _bar(start, Decimal(10), close=Decimal(5)),
        _bar(start + timedelta(days=1), Decimal(5)),
    ]
    request, snapshot = _risk_fixture(
        ["000001", "000002"], {"000001": falling, "000002": clock}
    )

    result = run_signal_backtest(
        request,
        snapshot,
        strategy_version="risk_implicit_report",
        definition="test",
        signal=lambda symbol, _bars: symbol == "000001",
        risk_policy=ResearchRiskPolicy(),
    )

    assert [trade.side for trade in result.trades] == ["buy", "sell"]
    assert result.trades[-1].date == start + timedelta(days=1)
    assert result.trades[-1].signal_date == start
    assert result.open_positions == {}


def test_explicit_no_risk_arguments_preserve_strategy_json() -> None:
    start = date(2025, 3, 2)
    request, snapshot = _risk_fixture(
        ["000001"],
        {
            "000001": [
                _bar(start, Decimal(10)),
                _bar(start + timedelta(days=1), Decimal(11)),
            ]
        },
    )

    def signal(_symbol: str, _bars: tuple[DailyBar, ...]) -> bool:
        return True

    implicit = run_signal_backtest(
        request,
        snapshot,
        strategy_version="no_risk",
        definition="test",
        signal=signal,
    )
    explicit = run_signal_backtest(
        request,
        snapshot,
        strategy_version="no_risk",
        definition="test",
        signal=signal,
        risk_policy=None,
        risk_report=None,
    )

    assert explicit.model_dump_json() == implicit.model_dump_json()
