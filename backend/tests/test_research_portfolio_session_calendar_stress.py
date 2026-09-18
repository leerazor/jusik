from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from jusik.research_market_calendar import DEFAULT_CALENDAR_PATH
from jusik.research_portfolio_session_calendar_stress import (
    CALENDAR_SHA256,
    CalendarAdapter,
    CalendarStressError,
    IncompleteSessionError,
    assert_next_open,
    fixture_publication_metadata,
    reconcile_decimal_accounting,
    replay_trade_ledger,
    run_simulation_gate,
    run_stress_harness,
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
