from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from jusik.research_market_calendar import DEFAULT_CALENDAR_PATH
from jusik.research_portfolio_models import PortfolioCandidate, PortfolioConfig
from jusik.research_portfolio_session_calendar_stress import (
    CALENDAR_SHA256,
    CalendarAdapter,
    CalendarStressError,
    IncompleteSessionError,
    _normal_session_source,
    assert_next_open,
    fixture_publication_metadata,
    install_calendar_adapter,
    load_isolated_engine,
    reconcile_decimal_accounting,
    replay_trade_ledger,
    run_simulation_gate,
    run_stress_harness,
    synthetic_source,
    validate_feature_cutoff,
)


def test_holiday_early_close_dst_and_krx_offsets() -> None:
    calendar = CalendarAdapter()
    assert calendar.lookup("America/New_York", date(2026, 7, 3)) is None
    early = calendar.lookup("America/New_York", date(2026, 11, 27))
    christmas = calendar.lookup("America/New_York", date(2026, 12, 24))
    assert early is not None and early.close_at == datetime(
        2026, 11, 27, 18, tzinfo=UTC
    )
    assert christmas is not None and christmas.close_at == datetime(
        2026, 12, 24, 18, tzinfo=UTC
    )
    assert early is not None and early.open_at == datetime(
        2026, 11, 27, 14, 30, tzinfo=UTC
    )
    winter = calendar.lookup("America/New_York", date(2026, 12, 23))
    assert (
        winter is not None
        and winter.open_at == datetime(2026, 12, 23, 14, 30, tzinfo=UTC)
        and winter.close_at == datetime(2026, 12, 23, 21, tzinfo=UTC)
    )
    before = calendar.lookup("America/New_York", date(2024, 3, 8))
    after = calendar.lookup("America/New_York", date(2024, 3, 11))
    assert (
        before is not None
        and before.open_at == datetime(2024, 3, 8, 14, 30, tzinfo=UTC)
        and before.close_at == datetime(2024, 3, 8, 21, tzinfo=UTC)
    )
    assert (
        after is not None
        and after.open_at == datetime(2024, 3, 11, 13, 30, tzinfo=UTC)
        and after.close_at == datetime(2024, 3, 11, 20, tzinfo=UTC)
    )
    krx = calendar.lookup("Asia/Seoul", date(2025, 11, 13))
    assert (
        krx is not None
        and krx.open_at == datetime(2025, 11, 13, 1, tzinfo=UTC)
        and krx.close_at == datetime(2025, 11, 13, 7, 30, tzinfo=UTC)
    )


def test_unknown_session_fails_closed() -> None:
    with pytest.raises(CalendarStressError, match="unknown_session"):
        CalendarAdapter().lookup("Asia/Seoul", date(2026, 11, 19))


@pytest.mark.parametrize(
    ("timezone_name", "day", "open_at", "close_at"),
    (
        ("America/New_York", date(2026, 7, 3), None, None),
        (
            "America/New_York",
            date(2026, 11, 27),
            datetime(2026, 11, 27, 14, 30, tzinfo=UTC),
            datetime(2026, 11, 27, 18, tzinfo=UTC),
        ),
        (
            "America/New_York",
            date(2026, 12, 24),
            datetime(2026, 12, 24, 14, 30, tzinfo=UTC),
            datetime(2026, 12, 24, 18, tzinfo=UTC),
        ),
        (
            "America/New_York",
            date(2026, 12, 23),
            datetime(2026, 12, 23, 14, 30, tzinfo=UTC),
            datetime(2026, 12, 23, 21, tzinfo=UTC),
        ),
        (
            "America/New_York",
            date(2024, 3, 8),
            datetime(2024, 3, 8, 14, 30, tzinfo=UTC),
            datetime(2024, 3, 8, 21, tzinfo=UTC),
        ),
        (
            "America/New_York",
            date(2024, 3, 11),
            datetime(2024, 3, 11, 13, 30, tzinfo=UTC),
            datetime(2024, 3, 11, 20, tzinfo=UTC),
        ),
        (
            "Asia/Seoul",
            date(2025, 11, 13),
            datetime(2025, 11, 13, 1, tzinfo=UTC),
            datetime(2025, 11, 13, 7, 30, tzinfo=UTC),
        ),
    ),
)
def test_copied_engine_event_hook_uses_required_session_times(
    tmp_path: Path,
    timezone_name: str,
    day: date,
    open_at: datetime | None,
    close_at: datetime | None,
) -> None:
    engine = load_isolated_engine(tmp_path / "engine")
    adapter = CalendarAdapter()
    install_calendar_adapter(engine, adapter)
    item = type("Item", (), {})()
    item.instrument = type("Instrument", (), {"timezone": timezone_name})()
    item.bars_by_date = {day: object()}
    events = engine._events({"FIXTURE": item}, day, day, calendar=adapter.calendar)
    actual = [(event.kind, event.at) for event in events if event.kind != "rebalance"]
    expected = (
        []
        if open_at is None or close_at is None
        else [("open", open_at), ("close", close_at)]
    )
    assert actual == expected


def test_historical_volatility_uses_publication_timed_varying_fx(
    tmp_path: Path,
) -> None:
    from jusik.research_external_models import ExternalFeatureSnapshot

    base = synthetic_source()
    varying_external = ExternalFeatureSnapshot(
        observations=tuple(
            row.model_copy(
                update={
                    "value": Decimal("1300")
                    + Decimal((row.observed_on - date(2023, 10, 2)).days % 3)
                }
            )
            if row.series == "usdkrw"
            else row
            for row in base.external.observations
        )
    )
    varying = base.model_copy(update={"external": varying_external})
    adapter = CalendarAdapter(publication=fixture_publication_metadata(base))
    varying = _normal_session_source(
        varying, adapter, date(2024, 1, 3), date(2024, 3, 15)
    )
    config = PortfolioConfig(
        volatility_window=20,
        initial_cash_krw=Decimal("1000000"),
        symbol_cap=Decimal("1"),
        gross_cap=Decimal("1"),
        leveraged_etf_cap=Decimal("1"),
    )
    at = datetime(2024, 3, 15, 21, tzinfo=UTC)

    engine_constant = load_isolated_engine(tmp_path / "constant")
    data_constant = engine_constant._instrument_data(base)
    install_calendar_adapter(engine_constant, adapter)
    constant_proxy = engine_constant.volatility_scale(
        base, data_constant, {"SYNUSD": Decimal("1")}, at, config, {}
    )[1]

    varying_adapter = CalendarAdapter(publication=fixture_publication_metadata(varying))
    engine_varying = load_isolated_engine(tmp_path / "varying")
    data_varying = engine_varying._instrument_data(varying)
    install_calendar_adapter(engine_varying, varying_adapter)
    varying_proxy = engine_varying.volatility_scale(
        varying, data_varying, {"SYNUSD": Decimal("1")}, at, config, {}
    )[1]
    assert constant_proxy is not None and varying_proxy is not None
    assert constant_proxy != varying_proxy

    delayed_publication = fixture_publication_metadata(varying)
    delayed_publication[("SYNUSD", date(2024, 3, 1))] = datetime(
        2024, 3, 20, tzinfo=UTC
    )
    delayed_adapter = CalendarAdapter(publication=delayed_publication)
    engine_delayed = load_isolated_engine(tmp_path / "delayed")
    data_delayed = engine_delayed._instrument_data(varying)
    install_calendar_adapter(engine_delayed, delayed_adapter)
    delayed_proxy = engine_delayed.volatility_scale(
        varying, data_delayed, {"SYNUSD": Decimal("1")}, at, config, {}
    )[1]
    assert delayed_proxy is not None and delayed_proxy != varying_proxy


def test_missing_first_valid_open_bar_is_incomplete() -> None:
    class Instrument:
        timezone = "America/New_York"

    class Item:
        instrument = Instrument()
        bars_by_date: dict[date, object] = {}

    with pytest.raises(IncompleteSessionError, match="missing_first_valid_open_bar"):
        CalendarAdapter().require_complete_bars(
            {"SPY": Item()}, date(2026, 11, 27), date(2026, 11, 27)
        )


def test_cutoff_and_next_open_are_strict() -> None:
    calendar = CalendarAdapter()
    session = calendar.lookup("America/New_York", date(2026, 11, 27))
    assert session is not None
    from tests.test_research_portfolio import _source

    source = _source()
    publication = fixture_publication_metadata(source, calendar)
    calendar = CalendarAdapter(publication=publication)
    item = type("Item", (), {})()
    item.snapshot = source.instruments[1]
    item.instrument = source.instruments[1].instruments[0].instrument
    cutoff_session = calendar.lookup("America/New_York", date(2024, 1, 3))
    assert cutoff_session is not None
    before_close = calendar.known_bars(
        item, cutoff_session.close_at.replace(hour=20, minute=59)
    )
    at_close = calendar.known_bars(item, cutoff_session.close_at)
    assert len(at_close) > len(before_close) >= 0
    assert_next_open(
        session.close_at,
        datetime(2026, 11, 30, 14, 30, tzinfo=UTC),
        "NYS",
        calendar,
    )
    with pytest.raises(CalendarStressError, match="causality"):
        assert_next_open(session.close_at, session.close_at, "NYS", calendar)
    assert_next_open(
        session.open_at,
        datetime(2026, 11, 30, 14, 30, tzinfo=UTC),
        "NYS",
        calendar,
    )
    with pytest.raises(CalendarStressError, match="causality"):
        assert_next_open(
            datetime(2026, 11, 18, 21, tzinfo=UTC),
            datetime(2026, 11, 20, 14, 30, tzinfo=UTC),
            "NYS",
            calendar,
        )


def test_copied_simulate_has_trades_and_exact_normal_control(tmp_path: Path) -> None:
    from jusik.research_portfolio_models import PortfolioCandidate, PortfolioConfig
    from tests.test_research_portfolio import _source

    source = _source()
    snapshot = source.instruments[1].model_copy(
        update={"requested_start": date(2024, 1, 3), "requested_end": date(2024, 1, 12)}
    )
    source = source.model_copy(update={"instruments": [snapshot]})
    config = PortfolioConfig(
        signal_window=2,
        volatility_window=2,
        momentum_window=2,
        initial_cash_krw=Decimal("1000000"),
        symbol_cap=Decimal("1"),
        gross_cap=Decimal("1"),
        leveraged_etf_cap=Decimal("1"),
    )
    result = run_simulation_gate(
        source,
        PortfolioCandidate(id="equal", method="equal", gate="none"),
        date(2024, 1, 3),
        date(2024, 1, 12),
        config,
        "corrected_control",
        audit_dir=tmp_path,
        adapter=CalendarAdapter(publication=fixture_publication_metadata(source)),
    )
    assert result.trades
    assert result.complete


def test_feature_future_publication_and_failure_evidence(tmp_path: Path) -> None:
    with pytest.raises(CalendarStressError, match="feature_cutoff"):
        validate_feature_cutoff(
            [type("Feature", (), {"published_at": datetime(2026, 1, 2, tzinfo=UTC)})()],
            datetime(2026, 1, 1, tzinfo=UTC),
        )
    bad_calendar = tmp_path / "calendar.json"
    bad_calendar.write_bytes(DEFAULT_CALENDAR_PATH.read_bytes() + b"tamper")
    with pytest.raises(CalendarStressError, match="hash"):
        run_stress_harness(tmp_path / "failed", calendar_path=bad_calendar)
    assert (tmp_path / "failed" / "failure.json").exists()
    assert (tmp_path / "failed" / "hash-manifest.json").exists()


def test_bar_publication_is_explicit_and_historical_cutoff_is_causal() -> None:
    from tests.test_research_portfolio import _source

    source = _source()
    item = type("Item", (), {})()
    item.snapshot = source.instruments[1]
    item.instrument = source.instruments[1].instruments[0].instrument
    with pytest.raises(CalendarStressError, match="publication_metadata_missing"):
        CalendarAdapter().known_bars(item, datetime(2024, 1, 3, 20, tzinfo=UTC))
    with pytest.raises(CalendarStressError, match="publication_timestamp_naive"):
        CalendarAdapter(
            publication={("USTEST", date(2024, 1, 3)): datetime(2024, 1, 3)}
        )

    adapter = CalendarAdapter(publication=fixture_publication_metadata(source))
    close = adapter.lookup("America/New_York", date(2024, 1, 3))
    assert close is not None
    before = adapter.known_bars(
        item, close.close_at.replace(hour=close.close_at.hour - 1, minute=59)
    )
    at_close = adapter.known_bars(item, close.close_at)
    assert len(at_close) == len(before) + 1

    delayed_publication = fixture_publication_metadata(source)
    delayed_publication[("USTEST", date(2024, 1, 3))] = datetime(2024, 1, 4, tzinfo=UTC)
    delayed = CalendarAdapter(publication=delayed_publication)
    assert len(delayed.known_bars(item, close.close_at)) == len(before)


def test_decimal_reconciliation_and_harness(tmp_path: Path) -> None:
    residual = reconcile_decimal_accounting(
        initial_cash=Decimal("1000000"),
        final_cash=Decimal("1200000"),
        terminal_value=Decimal("220000"),
        proceeds=Decimal("500000"),
        spending=Decimal("300000"),
        split_cash=Decimal("100"),
        fees=Decimal("19.5"),
        fx_cost=Decimal("80.5"),
    )
    assert abs(residual) <= Decimal("0.000001")
    result = run_stress_harness(tmp_path)
    assert result["calendar_sha256"] == CALENDAR_SHA256
    assert (tmp_path / "hash-manifest.json").exists()
    assert DEFAULT_CALENDAR_PATH.exists()


def test_independent_split_ledger_paths(tmp_path: Path) -> None:
    from jusik.research_external_models import ExternalFeatureSnapshot
    from jusik.research_universe_models import CorporateAction

    base = synthetic_source()
    varying_external = ExternalFeatureSnapshot(
        observations=tuple(
            row.model_copy(
                update={
                    "value": Decimal("1300")
                    + Decimal((row.observed_on - date(2023, 10, 2)).days % 3)
                }
            )
            if row.series == "usdkrw"
            else row
            for row in base.external.observations
        )
    )
    source = base.model_copy(update={"external": varying_external})
    adapter = CalendarAdapter(publication=fixture_publication_metadata(source))
    source = _normal_session_source(
        source, adapter, date(2024, 1, 3), date(2024, 3, 15)
    )
    config = PortfolioConfig(
        initial_cash_krw=Decimal("1000000"),
        signal_window=20,
        volatility_window=20,
        momentum_window=20,
        warmup_sessions=20,
        validation_sessions=20,
        symbol_cap=Decimal("1"),
        gross_cap=Decimal("1"),
        leveraged_etf_cap=Decimal("1"),
    )
    candidate = PortfolioCandidate(id="equal", method="equal", gate="none")
    simulation = run_simulation_gate(
        source,
        candidate,
        date(2024, 1, 3),
        date(2024, 3, 15),
        config,
        "corrected_control",
        audit_dir=tmp_path / "base",
        adapter=adapter,
    )
    assert replay_trade_ledger(source, simulation, config, adapter=adapter) == 0
    consumed_fx = {
        trade.fx_rate for trade in simulation.trades if trade.symbol == "SYNUSD"
    } | {
        position.fx_rate
        for position in simulation.positions
        if position.symbol == "SYNUSD"
    }
    assert len(consumed_fx) > 1
    action_day = next(
        action.date
        for snapshot in source.instruments
        for action in snapshot.corporate_actions
        if snapshot.instruments[0].symbol == "SYNKRW"
    )
    assert simulation.split_cash_in_lieu_krw["SYNKRW"] > 0
    assert any(
        trade.symbol == "SYNKRW"
        and trade.side == "sell"
        and trade.executed_at.date() > action_day
        for trade in simulation.trades
    )
    assert not any(
        trade.symbol == "SYNKRW" and trade.executed_at.date() == action_day
        for trade in simulation.trades
    )
    action_bar = next(
        bar
        for snapshot in source.instruments
        if snapshot.instruments[0].symbol == "SYNKRW"
        for bar in snapshot.instruments[0].bars
        if bar.date == action_day
    )
    presplit_quantity = sum(
        trade.quantity if trade.side == "buy" else -trade.quantity
        for trade in simulation.trades
        if trade.symbol == "SYNKRW" and trade.executed_at.date() < action_day
    )
    post_split_exact = Decimal(presplit_quantity) * Decimal("1.5")
    post_split_quantity = int(post_split_exact)
    expected_fractional_cash = (
        post_split_exact - post_split_quantity
    ) * action_bar.open
    assert simulation.split_cash_in_lieu_krw["SYNKRW"] == expected_fractional_cash
    expected_terminal_quantity = post_split_quantity + sum(
        trade.quantity if trade.side == "buy" else -trade.quantity
        for trade in simulation.trades
        if trade.symbol == "SYNKRW" and trade.executed_at.date() > action_day
    )
    terminal_position = next(
        position for position in simulation.positions if position.symbol == "SYNKRW"
    )
    assert terminal_position.quantity == expected_terminal_quantity
    assert all(position.local_close > 0 for position in simulation.positions)

    after_period = CorporateAction(
        date=date(2024, 4, 1), numerator=Decimal("3"), denominator=Decimal("2")
    )
    snapshots = [
        snapshot.model_copy(
            update={"corporate_actions": [*snapshot.corporate_actions, after_period]}
        )
        if snapshot.instruments[0].symbol == "SYNKRW"
        else snapshot
        for snapshot in source.instruments
    ]
    after_source = source.model_copy(update={"instruments": snapshots})
    after_simulation = run_simulation_gate(
        after_source,
        candidate,
        date(2024, 1, 3),
        date(2024, 3, 15),
        config,
        "corrected_control",
        audit_dir=tmp_path / "after-period",
        adapter=adapter,
    )
    assert after_simulation.split_cash_in_lieu_krw == simulation.split_cash_in_lieu_krw
    assert (
        replay_trade_ledger(after_source, after_simulation, config, adapter=adapter)
        == 0
    )


def test_ledger_rejects_independent_output_corruptions(tmp_path: Path) -> None:
    from jusik.research_portfolio_models import PortfolioCandidate, PortfolioConfig
    from tests.test_research_portfolio import _source

    source = _source()
    config = PortfolioConfig(
        signal_window=2,
        volatility_window=2,
        momentum_window=2,
        initial_cash_krw=Decimal("1000000"),
        symbol_cap=Decimal("1"),
        gross_cap=Decimal("1"),
        leveraged_etf_cap=Decimal("1"),
    )
    adapter = CalendarAdapter(publication=fixture_publication_metadata(source))
    simulation = run_simulation_gate(
        source,
        PortfolioCandidate(id="equal", method="equal", gate="none"),
        date(2024, 1, 3),
        date(2024, 1, 12),
        config,
        "corrected_control",
        audit_dir=tmp_path / "simulation",
        adapter=adapter,
    )
    assert replay_trade_ledger(source, simulation, config, adapter=adapter) == 0

    last = simulation.equity[-1]
    corrupted_point = last.model_copy(update={"cash_krw": last.cash_krw + Decimal("1")})
    corrupted = simulation.model_copy(
        update={"equity": [*simulation.equity[:-1], corrupted_point]}
    )
    with pytest.raises(CalendarStressError, match="equity_cash"):
        replay_trade_ledger(source, corrupted, config, adapter=adapter)

    assert simulation.positions
    corrupted_position = simulation.positions[0].model_copy(
        update={
            "local_close": simulation.positions[0].local_close + Decimal("1"),
            "fx_rate": simulation.positions[0].fx_rate - Decimal("1"),
        }
    )
    corrupted = simulation.model_copy(
        update={"positions": [corrupted_position, *simulation.positions[1:]]}
    )
    with pytest.raises(CalendarStressError, match="terminal_price"):
        replay_trade_ledger(source, corrupted, config, adapter=adapter)

    with pytest.raises(CalendarStressError, match="position_symbols"):
        replay_trade_ledger(
            source,
            simulation.model_copy(update={"positions": []}),
            config,
            adapter=adapter,
        )

    metrics = simulation.metrics.model_copy(
        update={"transaction_cost_krw": simulation.metrics.transaction_cost_krw + 1}
    )
    with pytest.raises(CalendarStressError, match="metrics_cost"):
        replay_trade_ledger(
            source,
            simulation.model_copy(update={"metrics": metrics}),
            config,
            adapter=adapter,
        )

    contributions = dict(simulation.contributions_krw)
    first_symbol = next(iter(contributions))
    contributions[first_symbol] += 1
    with pytest.raises(CalendarStressError, match="contribution"):
        replay_trade_ledger(
            source,
            simulation.model_copy(update={"contributions_krw": contributions}),
            config,
            adapter=adapter,
        )
