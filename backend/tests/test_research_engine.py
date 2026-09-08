from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from jusik.research_data import DataInsufficientError
from jusik.research_engine import run_backtest
from jusik.research_models import (
    BacktestResult,
    DailyBar,
    MarketEvent,
    ResearchInputSnapshot,
    ResearchRunRequest,
    SymbolSnapshot,
)


def bars(
    start: date,
    count: int,
    *,
    zero_volume_index: int | None = None,
) -> list[DailyBar]:
    result = []
    for index in range(count):
        price = Decimal(100 + index)
        result.append(
            DailyBar(
                date=start + timedelta(days=index),
                open=price,
                high=price,
                low=price,
                close=price,
                volume=0 if index == zero_volume_index else 1000,
                adjusted_open=price,
                adjusted_high=price,
                adjusted_low=price,
                adjusted_close=price,
            )
        )
    return result


def fixture(
    *,
    zero_volume_index: int | None = None,
    events: list[MarketEvent] | None = None,
) -> tuple[ResearchRunRequest, ResearchInputSnapshot]:
    first = date(2024, 10, 1)
    start = first + timedelta(days=65)
    end = first + timedelta(days=69)
    request = ResearchRunRequest(
        start_date=start,
        end_date=end,
        initial_cash="1000",
        fee_rate="0",
        slippage_rate="0",
        sell_tax_rate="0",
        events=events or [],
    )
    snapshots = [
        SymbolSnapshot(
            symbol=symbol,
            market="KOSPI",
            bars=bars(first, 70, zero_volume_index=zero_volume_index),
            source_url="https://example.com/daily",
        )
        for symbol in request.symbols
    ]
    return request, ResearchInputSnapshot(
        captured_at=datetime(2025, 1, 1, tzinfo=UTC),
        requested_start=start,
        requested_end=end,
        symbols=snapshots,
        events=request.events,
    )


def test_request_defaults_symbols_but_allows_independent_ascii_universe() -> None:
    request = ResearchRunRequest(start_date=date(2025, 1, 1), end_date=date(2025, 2, 1))
    assert request.symbols == ["005930", "000660"]
    independent = ResearchRunRequest(
        symbols=["035420"],
        start_date=date(2025, 1, 1),
        end_date=date(2025, 2, 1),
    )
    assert independent.symbols == ["035420"]
    with pytest.raises(ValidationError):
        ResearchRunRequest(
            symbols=["１２３４５６"],
            start_date=date(2025, 1, 1),
            end_date=date(2025, 2, 1),
        )
    with pytest.raises(ValidationError):
        ResearchRunRequest(
            symbols=[f"{index:06d}" for index in range(11)],
            start_date=date(2025, 1, 1),
            end_date=date(2025, 2, 1),
        )


def test_shared_cash_is_deterministic_and_positions_are_not_force_sold() -> None:
    request, snapshot = fixture()

    first = run_backtest(request, snapshot)
    second = run_backtest(request, snapshot)

    assert first == second
    assert [trade.symbol for trade in first.candidate.trades] == ["000660", "005930"]
    assert all(trade.side == "buy" for trade in first.candidate.trades)
    assert all(trade.signal_date < trade.date for trade in first.candidate.trades)
    assert first.candidate.open_positions
    assert first.candidate.metrics.trade_count == 2
    assert all(point.cash >= 0 for point in first.candidate.equity)
    assert first.live_promotion_eligible is False


def test_buy_costs_reconcile_with_shared_cash_and_slippage() -> None:
    request, snapshot = fixture()
    request.fee_rate = Decimal("0.001")
    request.slippage_rate = Decimal("0.01")

    result = run_backtest(request, snapshot).candidate

    spent = sum((trade.notional + trade.fee for trade in result.trades), Decimal())
    expected_slippage = sum(
        (
            (trade.execution_price - trade.market_open) * trade.quantity
            for trade in result.trades
        ),
        Decimal(),
    )
    assert result.equity[0].cash == request.initial_cash - spent
    assert result.metrics.total_fees == sum(
        (trade.fee for trade in result.trades), Decimal()
    )
    assert result.metrics.total_slippage_cost == expected_slippage
    assert result.metrics.total_tax == 0


def test_future_bar_change_does_not_change_earlier_trades_or_equity() -> None:
    request, snapshot = fixture()
    original = run_backtest(request, snapshot).candidate
    revised_symbols = []
    for item in snapshot.symbols:
        changed_bar = item.bars[-1].model_copy(
            update={
                "open": Decimal("10000"),
                "high": Decimal("10000"),
                "low": Decimal("10000"),
                "close": Decimal("10000"),
                "adjusted_open": Decimal("10000"),
                "adjusted_high": Decimal("10000"),
                "adjusted_low": Decimal("10000"),
                "adjusted_close": Decimal("10000"),
            }
        )
        revised_symbols.append(
            item.model_copy(update={"bars": [*item.bars[:-1], changed_bar]})
        )
    revised = snapshot.model_copy(update={"symbols": revised_symbols})

    changed = run_backtest(request, revised).candidate

    assert changed.trades == original.trades
    assert changed.equity[:-1] == original.equity[:-1]


def test_time_split_uses_prior_bars_only_as_warmup_and_resets_test_capital() -> None:
    first = date(2024, 1, 1)
    request = ResearchRunRequest(
        symbols=["035420"],
        start_date=first + timedelta(days=65),
        end_date=first + timedelta(days=129),
        initial_cash="1234567",
        fee_rate="0.001",
        slippage_rate="0.001",
        sell_tax_rate="0.0018",
    )
    snapshot = ResearchInputSnapshot(
        captured_at=datetime(2025, 1, 1, tzinfo=UTC),
        requested_start=request.start_date,
        requested_end=request.end_date,
        symbols=[
            SymbolSnapshot(
                symbol="035420",
                market="KOSPI",
                bars=bars(first, 130),
                source_url="https://example.com/daily",
            )
        ],
        events=[],
    )

    validation = run_backtest(request, snapshot).validation

    assert validation is not None
    assert validation.training_end < validation.testing_start
    assert validation.testing_initial_cash == request.initial_cash
    assert validation.baseline.initial_cash == request.initial_cash
    assert validation.candidate.initial_cash == request.initial_cash


def test_common_missing_bar_is_explicitly_unverified_without_inventing_calendar() -> (
    None
):
    request, snapshot = fixture()
    missing_date = request.start_date + timedelta(days=1)
    changed = snapshot.model_copy(
        update={
            "symbols": [
                item.model_copy(
                    update={
                        "bars": [bar for bar in item.bars if bar.date != missing_date]
                    }
                )
                for item in snapshot.symbols
            ]
        }
    )

    result = run_backtest(request, changed)

    assert result.coverage_status == "common_sessions_unverified"
    assert all(item.missing_expected_sessions is None for item in result.coverage)
    assert all(item.missing_vs_union_dates == 0 for item in result.coverage)


def test_result_records_fixed_specification_and_loaded_implementation() -> None:
    request, snapshot = fixture()

    result = run_backtest(request, snapshot)

    assert result.specification is not None
    assert result.specification.signal_windows == (20, 60)
    assert result.specification.warmup_bars == 60
    assert result.specification.decimal_precision == 40
    assert result.implementation_hash is not None
    assert len(result.implementation_hash) == 64


def test_legacy_result_remains_readable_but_has_no_replay_identity() -> None:
    request, snapshot = fixture()
    payload = run_backtest(request, snapshot).model_dump(mode="json")
    payload.pop("specification")
    payload.pop("implementation_hash")
    payload.pop("coverage_status")
    for item in payload["coverage"]:
        item["missing_comparison_dates"] = item.pop("missing_vs_union_dates")
        item.pop("missing_expected_sessions")

    legacy = BacktestResult.model_validate(payload)

    assert legacy.implementation_hash is None
    assert legacy.specification is None
    assert legacy.coverage[0].missing_vs_union_dates == 0


def test_zero_volume_defers_fill_without_losing_signal() -> None:
    request, snapshot = fixture(zero_volume_index=65)

    result = run_backtest(request, snapshot).candidate

    assert len(result.unfilled_decisions) == 2
    assert result.unfilled_decisions[0].date == request.start_date
    assert all(trade.date > request.start_date for trade in result.trades)
    assert all(trade.signal_date < trade.date for trade in result.trades)


def test_afternoon_event_does_not_retroactively_block_morning_fill() -> None:
    request, snapshot = fixture()
    occurred = datetime.combine(
        request.start_date, datetime.min.time(), tzinfo=UTC
    ).replace(hour=6)
    event = MarketEvent(
        kind="sidecar",
        market="KOSPI",
        direction="down",
        occurred_at=occurred,
        known_at=occurred,
        resumed_at=occurred + timedelta(minutes=5),
        source_url="https://example.com/event",
    )
    request.events = [event]
    snapshot = snapshot.model_copy(update={"events": [event]})

    result = run_backtest(request, snapshot).candidate

    assert result.trades[0].date == request.start_date
    assert result.affected_decisions == []


def test_unresolved_matching_circuit_breaker_makes_execution_insufficient() -> None:
    request, snapshot = fixture()
    open_utc = datetime.combine(request.start_date, datetime.min.time(), tzinfo=UTC)
    event = MarketEvent(
        kind="circuit_breaker",
        market="KOSPI",
        direction="down",
        stage=1,
        occurred_at=open_utc - timedelta(minutes=1),
        known_at=open_utc - timedelta(minutes=1),
        source_url="https://example.com/event",
    )
    request.events = [event]
    snapshot = snapshot.model_copy(update={"events": [event]})

    with pytest.raises(DataInsufficientError, match="서킷브레이커"):
        run_backtest(request, snapshot)


def test_market_event_only_applies_to_the_matching_listing_board() -> None:
    request, snapshot = fixture()
    open_utc = datetime.combine(request.start_date, datetime.min.time(), tzinfo=UTC)
    event = MarketEvent(
        kind="circuit_breaker",
        market="KOSDAQ",
        direction="down",
        stage=1,
        occurred_at=open_utc - timedelta(minutes=1),
        known_at=open_utc - timedelta(minutes=1),
        source_url="https://example.com/event",
    )
    request.events = [event]
    snapshot = snapshot.model_copy(update={"events": [event]})

    result = run_backtest(request, snapshot)

    assert result.candidate.metrics.trade_count == 2
    assert result.event_coverage == "provided_partial"
