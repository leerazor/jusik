from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from jusik.research_app import create_research_app
from jusik.research_config import PAPER_BASE_URL, ResearchSettings
from jusik.research_external_models import ExternalFeatureSnapshot, ExternalObservation
from jusik.research_models import DailyBar, ResearchRunRequest
from jusik.research_portfolio import (
    PortfolioRunRepository,
    run_from_stores,
    run_portfolio_research,
)
from jusik.research_portfolio_engine import (
    _instrument_data,
    _market_time,
    _volatility_scale,
    candidates,
    policy_diagnostics,
    simulate,
    target_weights,
)
from jusik.research_portfolio_models import (
    PortfolioCandidate,
    PortfolioConfig,
    PortfolioEquityPoint,
    PortfolioInput,
    PortfolioMetrics,
    PortfolioRunResult,
    PortfolioRunStatus,
    PortfolioSimulation,
    PortfolioTarget,
    PortfolioTrade,
)
from jusik.research_store import ResearchStore
from jusik.research_universe_models import (
    CorporateAction,
    DataProvenance,
    OfflineInstrumentSnapshot,
    OfflineResearchSnapshot,
    PriceAdjustmentFactor,
    ResearchInstrument,
)


def _business_days(start: date, count: int) -> list[date]:
    days: list[date] = []
    current = start
    while len(days) < count:
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    return days


def _instrument_snapshot(
    symbol: str,
    currency: str,
    timezone_name: str,
    *,
    falling_after: int | None = None,
    split_at: int | None = None,
) -> OfflineResearchSnapshot:
    days = _business_days(date(2023, 10, 2), 110)
    bars = []
    for index, day in enumerate(days):
        if falling_after is not None and index >= falling_after:
            price = Decimal(300 - (index - falling_after) * 12)
        else:
            price = Decimal(100 + index * 2)
        price = max(price, Decimal(5))
        bars.append(
            DailyBar(
                date=day,
                open=price,
                high=price + 1,
                low=price - 1,
                close=price,
                volume=1000 + index,
                adjusted_open=price,
                adjusted_high=price + 1,
                adjusted_low=price - 1,
                adjusted_close=price,
            )
        )
    instrument = ResearchInstrument(
        symbol=symbol,
        yahoo_symbol=symbol,
        name=symbol,
        currency=currency,
        exchange="KSC" if currency == "KRW" else "NMS",
        timezone=timezone_name,
    )
    item = OfflineInstrumentSnapshot(
        instrument=instrument,
        bars=bars,
        provenance=DataProvenance(price_volume_source="Yahoo chart"),
        source_url="https://example.com/chart",
    )
    actions = (
        [
            CorporateAction(
                date=days[split_at],
                numerator=Decimal(3),
                denominator=Decimal(2),
            )
        ]
        if split_at is not None
        else []
    )
    return OfflineResearchSnapshot(
        captured_at=datetime(2024, 3, 4, tzinfo=UTC),
        requested_start=days[65],
        requested_end=days[-1],
        evaluation_start=days[65],
        instruments=[item],
        basis_actions=actions,
        corporate_actions=actions,
        adjustment_factors=[
            PriceAdjustmentFactor(date=bar.date, raw_factor=Decimal(1)) for bar in bars
        ],
    )


def _external(include_fx: bool = True) -> ExternalFeatureSnapshot:
    observations = []
    values = {
        "treasury_2y": Decimal("4.0"),
        "treasury_10y": Decimal("4.2"),
        "vix": Decimal("18"),
        "usdkrw": Decimal("1300"),
        "uso": Decimal("70"),
        "gld": Decimal("180"),
        "hyg": Decimal("75"),
    }
    for offset in range(180):
        day = date(2023, 9, 1) + timedelta(days=offset)
        for series, value in values.items():
            if series == "usdkrw" and not include_fx:
                continue
            observations.append(
                ExternalObservation(
                    series=series,
                    observed_on=day,
                    value=value,
                    available_at=datetime.combine(day, time(), UTC),
                    revision="test",
                )
            )
    return ExternalFeatureSnapshot(observations=observations)


def _source(*, reverse: bool = False, include_fx: bool = True) -> PortfolioInput:
    snapshots = [
        _instrument_snapshot("KRTEST", "KRW", "Asia/Seoul"),
        _instrument_snapshot("USTEST", "USD", "America/New_York"),
    ]
    if reverse:
        snapshots.reverse()
    return PortfolioInput(
        captured_at=datetime(2024, 3, 4, tzinfo=UTC),
        stock_snapshot_ids={
            item.instruments[0].symbol: "snapshot" for item in snapshots
        },
        instruments=snapshots,
        external=_external(include_fx),
    )


def _episode_snapshot(symbol: str) -> OfflineResearchSnapshot:
    days = _business_days(date(2023, 1, 2), 200)
    bars = []
    for index, day in enumerate(days):
        if index < 85:
            price = Decimal(100 + index)
        elif index < 95:
            price = Decimal(185 - (index - 84) * 12)
        else:
            price = Decimal(65 + (index - 95) * 4)
        bars.append(
            DailyBar(
                date=day,
                open=price,
                high=price + 1,
                low=price - 1,
                close=price,
                volume=1000,
                adjusted_open=price,
                adjusted_high=price + 1,
                adjusted_low=price - 1,
                adjusted_close=price,
            )
        )
    instrument = ResearchInstrument(
        symbol=symbol,
        yahoo_symbol=symbol,
        name=symbol,
        currency="KRW",
        exchange="KSC",
        timezone="Asia/Seoul",
    )
    item = OfflineInstrumentSnapshot(
        instrument=instrument,
        bars=bars,
        provenance=DataProvenance(price_volume_source="Yahoo chart"),
        source_url="https://example.com/chart",
    )
    return OfflineResearchSnapshot(
        captured_at=datetime(2024, 1, 1, tzinfo=UTC),
        requested_start=days[65],
        requested_end=days[-1],
        evaluation_start=days[65],
        instruments=[item],
        adjustment_factors=[
            PriceAdjustmentFactor(date=bar.date, raw_factor=Decimal(1)) for bar in bars
        ],
    )


def _episode_source() -> PortfolioInput:
    snapshots = [_episode_snapshot("A"), _episode_snapshot("B")]
    return PortfolioInput(
        captured_at=datetime(2024, 1, 1, tzinfo=UTC),
        stock_snapshot_ids={"A": "a", "B": "b"},
        instruments=snapshots,
        external=_external(),
    )


def _simultaneous_sell_source() -> PortfolioInput:
    snapshots = []
    for symbol in ("A", "B", "SOXL", "TQQQ"):
        snapshot = _instrument_snapshot(symbol, "KRW", "Asia/Seoul")
        bars = []
        for index, bar in enumerate(snapshot.instruments[0].bars):
            multiplier = Decimal(3) if index >= 70 else Decimal(1)
            price = bar.close * multiplier
            bars.append(
                bar.model_copy(
                    update={
                        "open": price,
                        "high": price + 1,
                        "low": price - 1,
                        "close": price,
                        "adjusted_open": price,
                        "adjusted_high": price + 1,
                        "adjusted_low": price - 1,
                        "adjusted_close": price,
                    }
                )
            )
        snapshots.append(
            snapshot.model_copy(
                update={
                    "instruments": [
                        snapshot.instruments[0].model_copy(update={"bars": bars})
                    ]
                }
            )
        )
    return PortfolioInput(
        captured_at=datetime(2024, 3, 4, tzinfo=UTC),
        stock_snapshot_ids={
            snapshot.instruments[0].symbol: "snapshot" for snapshot in snapshots
        },
        instruments=snapshots,
        external=_external(),
    )


def _staggered_cap_source() -> PortfolioInput:
    source = _source()
    snapshots = []
    for snapshot in source.instruments:
        if snapshot.instruments[0].symbol != "KRTEST":
            snapshots.append(snapshot)
            continue
        bars = []
        for index, bar in enumerate(snapshot.instruments[0].bars):
            multiplier = Decimal("1.30") if index >= 70 else Decimal(1)
            price = bar.close * multiplier
            bars.append(
                bar.model_copy(
                    update={
                        "open": price,
                        "high": price + 1,
                        "low": price - 1,
                        "close": price,
                        "adjusted_open": price,
                        "adjusted_high": price + 1,
                        "adjusted_low": price - 1,
                        "adjusted_close": price,
                    }
                )
            )
        snapshots.append(
            snapshot.model_copy(
                update={
                    "instruments": [
                        snapshot.instruments[0].model_copy(update={"bars": bars})
                    ]
                }
            )
        )
    return source.model_copy(update={"instruments": snapshots})


def test_candidates_are_fixed_twelve_and_weights_respect_caps() -> None:
    configured = candidates()
    assert len(configured) == 12
    assert len({item.id for item in configured}) == 12
    source = _source()
    weights, _correlations, reason = target_weights(
        source,
        PortfolioCandidate(id="equal", method="equal", gate="none"),
        datetime(2024, 2, 5, tzinfo=UTC),
        PortfolioConfig(),
    )
    assert reason is None
    assert sum(weights.values()) <= Decimal("0.60")
    assert all(value <= Decimal("0.20") for value in weights.values())


def test_simulation_is_order_independent_and_never_uses_decision_day_open() -> None:
    candidate = PortfolioCandidate(id="equal", method="equal", gate="none")
    config = PortfolioConfig()
    source = _source()
    start = source.instruments[0].requested_start
    end = source.instruments[0].requested_end
    first = simulate(source, candidate, start, end, config)
    reversed_result = simulate(_source(reverse=True), candidate, start, end, config)
    assert first.complete
    assert first.metrics == reversed_result.metrics
    assert [(item.symbol, item.side, item.quantity) for item in first.trades] == [
        (item.symbol, item.side, item.quantity) for item in reversed_result.trades
    ]
    assert first.trades
    assert all(trade.executed_at > trade.decided_at for trade in first.trades)
    assert first.metrics.final_equity_krw >= 0
    assert all(
        (target.actual_weight_after_open is None)
        or target.actual_weight_after_open <= config.symbol_cap
        for target in first.weekly_targets
    )
    executions_by_instruction: dict[tuple[str, datetime], set[datetime]] = {}
    sides_by_instruction: dict[tuple[str, datetime], set[str]] = {}
    for trade in first.trades:
        key = (trade.symbol, trade.decided_at)
        executions_by_instruction.setdefault(key, set()).add(trade.executed_at)
        sides_by_instruction.setdefault(key, set()).add(trade.side)
    assert any("sell" in sides for sides in sides_by_instruction.values())
    assert all(
        len(executions) == 1 for executions in executions_by_instruction.values()
    )
    assert all(len(sides) == 1 for sides in sides_by_instruction.values())


def test_simultaneous_high_cost_sells_preserve_all_allocation_caps() -> None:
    source = _simultaneous_sell_source()
    config = PortfolioConfig(
        fee_rate=Decimal("0.10"),
        slippage_rate=Decimal("0.05"),
        fx_spread_rate=Decimal(0),
    )
    result = simulate(
        source,
        PortfolioCandidate(id="equal", method="equal", gate="none"),
        source.instruments[0].requested_start,
        source.instruments[0].requested_end,
        config,
    )
    sells_by_open: dict[datetime, int] = {}
    for trade in result.trades:
        if trade.side == "sell":
            sells_by_open[trade.executed_at] = (
                sells_by_open.get(trade.executed_at, 0) + 1
            )
    assert max(sells_by_open.values(), default=0) >= 2

    targets_by_decision: dict[datetime, list[PortfolioTarget]] = {}
    for target in result.weekly_targets:
        if target.actual_weight_after_open is not None:
            targets_by_decision.setdefault(target.decided_at, []).append(target)
    for targets in targets_by_decision.values():
        weights = {
            target.symbol: target.actual_weight_after_open
            for target in targets
            if target.actual_weight_after_open is not None
        }
        assert all(weight <= config.symbol_cap for weight in weights.values())
        assert sum(weights.values(), Decimal(0)) <= config.gross_cap
        assert (
            sum(
                (weights.get(symbol, Decimal(0)) for symbol in ("SOXL", "TQQQ")),
                Decimal(0),
            )
            <= config.leveraged_etf_cap
        )


def test_nonopening_symbol_cap_is_deferred_until_its_next_open() -> None:
    source = _staggered_cap_source()
    result = simulate(
        source,
        PortfolioCandidate(id="equal", method="equal", gate="none"),
        source.instruments[0].requested_start,
        source.instruments[0].requested_end,
        PortfolioConfig(),
    )
    deferred = [
        event
        for event in result.policy_events
        if event.kind == "cap_constraint_deferred"
        and "symbol=KRTEST" in event.detail
        and event.at.hour in {13, 14}
    ]
    assert deferred
    us_open_deferral, next_kr_trade = next(
        (event, trade)
        for event in deferred
        for trade in result.trades
        if trade.symbol == "KRTEST"
        and trade.side == "sell"
        and trade.decided_at < event.at < trade.executed_at
    )
    assert not any(
        trade.symbol == "KRTEST" and trade.executed_at == us_open_deferral.at
        for trade in result.trades
    )
    assert (
        next_kr_trade.executed_at.date()
        == (us_open_deferral.at + timedelta(days=1)).date()
    )
    corrected_target = next(
        target
        for target in result.weekly_targets
        if target.symbol == "KRTEST" and target.decided_at == next_kr_trade.decided_at
    )
    assert corrected_target.actual_weight_after_open is not None
    assert corrected_target.actual_weight_after_open <= PortfolioConfig().symbol_cap


def test_missing_fx_marks_result_incomplete_without_creating_usd_cash() -> None:
    source = _source(include_fx=False)
    result = simulate(
        source,
        PortfolioCandidate(id="equal", method="equal", gate="none"),
        source.instruments[0].requested_start,
        source.instruments[0].requested_end,
        PortfolioConfig(),
    )
    assert not result.complete
    assert any("USD/KRW" in reason for reason in result.incomplete_reasons)
    assert all(trade.symbol != "USTEST" for trade in result.trades)


def test_us_market_open_tracks_dst_without_future_timezone_leak() -> None:
    assert _market_time(date(2024, 3, 8), "America/New_York", opening=True).hour == 14
    assert _market_time(date(2024, 3, 11), "America/New_York", opening=True).hour == 13


def test_target_uses_only_known_closes_and_ipo_enters_after_sixty_one_bars() -> None:
    long = _instrument_snapshot("LONG", "KRW", "Asia/Seoul")
    ipo = _instrument_snapshot("IPO", "KRW", "Asia/Seoul").model_copy(
        update={
            "instruments": [
                _instrument_snapshot("IPO", "KRW", "Asia/Seoul")
                .instruments[0]
                .model_copy(
                    update={
                        "bars": _instrument_snapshot("IPO", "KRW", "Asia/Seoul")
                        .instruments[0]
                        .bars[40:]
                    }
                )
            ],
            "adjustment_factors": _instrument_snapshot(
                "IPO", "KRW", "Asia/Seoul"
            ).adjustment_factors[40:],
        }
    )
    source = PortfolioInput(
        captured_at=datetime(2024, 3, 4, tzinfo=UTC),
        stock_snapshot_ids={"LONG": "long", "IPO": "ipo"},
        instruments=[long, ipo],
        external=_external(),
    )
    ipo_bars = ipo.instruments[0].bars
    before, _, _ = target_weights(
        source,
        PortfolioCandidate(id="equal", method="equal", gate="none"),
        _market_time(ipo_bars[59].date, "Asia/Seoul", opening=False),
        PortfolioConfig(),
    )
    after, _, _ = target_weights(
        source,
        PortfolioCandidate(id="equal", method="equal", gate="none"),
        _market_time(ipo_bars[60].date, "Asia/Seoul", opening=False),
        PortfolioConfig(),
    )
    assert "IPO" not in before
    assert "IPO" in after


def test_drawdown_latch_exits_and_never_reenters() -> None:
    snapshot = _instrument_snapshot("FALL", "KRW", "Asia/Seoul", falling_after=75)
    source = PortfolioInput(
        captured_at=datetime(2024, 3, 4, tzinfo=UTC),
        stock_snapshot_ids={"FALL": "fall"},
        instruments=[snapshot],
        external=_external(),
    )
    result = simulate(
        source,
        PortfolioCandidate(id="equal", method="equal", gate="none"),
        snapshot.requested_start,
        snapshot.requested_end,
        PortfolioConfig(),
    )
    assert result.drawdown_latched
    latch_at = result.weekly_targets[-1].decided_at
    assert result.weekly_targets[-1].target_weight == 0
    assert not any(
        trade.side == "buy" and trade.decided_at >= latch_at for trade in result.trades
    )


def test_split_fraction_is_settled_to_krw_cash() -> None:
    snapshot = _instrument_snapshot("SPLIT", "KRW", "Asia/Seoul", split_at=80)
    source = PortfolioInput(
        captured_at=datetime(2024, 3, 4, tzinfo=UTC),
        stock_snapshot_ids={"SPLIT": "split"},
        instruments=[snapshot],
        external=_external(),
    )
    result = simulate(
        source,
        PortfolioCandidate(id="equal", method="equal", gate="none"),
        snapshot.requested_start,
        snapshot.requested_end,
        PortfolioConfig(
            initial_cash_krw=Decimal("100001"),
            fee_rate=Decimal(0),
            slippage_rate=Decimal(0),
            fx_spread_rate=Decimal(0),
            symbol_cap=Decimal(1),
            gross_cap=Decimal(1),
            leveraged_etf_cap=Decimal(1),
        ),
    )
    assert result.split_cash_in_lieu_krw.get("SPLIT", Decimal(0)) > 0


def test_reentry_waits_for_liquidation_cooldown_and_confirmations() -> None:
    source = _episode_source()
    start = source.instruments[0].requested_start
    end = source.instruments[0].requested_end
    result = simulate(
        source,
        PortfolioCandidate(id="equal", method="equal", gate="none"),
        start,
        end,
        PortfolioConfig(),
        policy="reentry_only",
    )
    events = result.policy_events
    liquidation = next(item for item in events if item.kind == "liquidation_complete")
    confirmations = [item for item in events if item.kind == "recovery_confirmation"]
    reentry = next(item for item in events if item.kind == "reentry")
    assert len(confirmations) == 2
    assert confirmations[0].at.date() >= liquidation.at.date() + timedelta(days=28)
    assert confirmations[1].at < reentry.at
    assert sum(item.kind == "risk_exit" for item in events) == 1
    assert result.metrics.max_drawdown_pct > Decimal(10)
    assert not result.drawdown_latched


def test_low_turnover_cadence_and_band_do_not_delay_risk_exit() -> None:
    source = _episode_source()
    result = simulate(
        source,
        PortfolioCandidate(id="equal", method="equal", gate="none"),
        source.instruments[0].requested_start,
        source.instruments[0].requested_end,
        PortfolioConfig(),
        policy="low_turnover_combined",
    )
    events = result.policy_events
    risk_exit = next(item for item in events if item.kind == "risk_exit")
    assert risk_exit.at.weekday() != 0
    assert any(item.kind == "frequency_skip" for item in events)
    assert any(item.kind == "reentry" for item in events)

    regular = _source()
    band_result = simulate(
        regular,
        PortfolioCandidate(id="equal", method="equal", gate="none"),
        regular.instruments[0].requested_start,
        regular.instruments[0].requested_end,
        PortfolioConfig(
            symbol_cap=Decimal(1),
            gross_cap=Decimal(1),
            leveraged_etf_cap=Decimal(1),
        ),
        policy="low_turnover_combined",
    )
    assert any(item.kind == "band_skip" for item in band_result.policy_events)


def test_volatility_scale_is_causal_and_handles_zero_or_missing_fx() -> None:
    source = _source()
    at = datetime(2024, 2, 5, tzinfo=UTC)
    weights = {"USTEST": Decimal("0.20")}
    base = _volatility_scale(
        source, _instrument_data(source), weights, at, PortfolioConfig()
    )
    future_fx = ExternalObservation(
        series="usdkrw",
        observed_on=at.date(),
        value=Decimal("9999"),
        available_at=at + timedelta(days=1),
        revision="future",
    )
    with_future = source.model_copy(
        update={
            "external": source.external.model_copy(
                update={"observations": [*source.external.observations, future_fx]}
            )
        }
    )
    assert (
        _volatility_scale(
            with_future,
            _instrument_data(with_future),
            weights,
            at,
            PortfolioConfig(),
        )
        == base
    )

    missing = _source(include_fx=False)
    assert _volatility_scale(
        missing,
        _instrument_data(missing),
        weights,
        at,
        PortfolioConfig(),
    ) == (None, None)

    kr_snapshot = _instrument_snapshot("FLAT", "KRW", "Asia/Seoul")
    flat_bars = [
        bar.model_copy(
            update={
                "open": Decimal(100),
                "high": Decimal(101),
                "low": Decimal(99),
                "close": Decimal(100),
                "adjusted_open": Decimal(100),
                "adjusted_high": Decimal(101),
                "adjusted_low": Decimal(99),
                "adjusted_close": Decimal(100),
            }
        )
        for bar in kr_snapshot.instruments[0].bars
    ]
    flat_snapshot = kr_snapshot.model_copy(
        update={
            "instruments": [
                kr_snapshot.instruments[0].model_copy(update={"bars": flat_bars})
            ]
        }
    )
    flat_source = PortfolioInput(
        captured_at=source.captured_at,
        stock_snapshot_ids={"FLAT": "flat"},
        instruments=[flat_snapshot],
        external=_external(),
    )
    assert _volatility_scale(
        flat_source,
        _instrument_data(flat_source),
        {"FLAT": Decimal("0.20")},
        at,
        PortfolioConfig(),
    ) == (Decimal(1), Decimal(0))


def test_monthly_policy_diagnostics_use_observed_utc_day_end_nav() -> None:
    candidate = PortfolioCandidate(id="equal", method="equal", gate="none")
    metrics = PortfolioMetrics(
        initial_equity_krw=Decimal(1000),
        final_equity_krw=Decimal(1000),
        total_return_pct=Decimal(0),
        max_drawdown_pct=Decimal(0),
        trade_count=1,
        transaction_cost_krw=Decimal(0),
        fx_cost_krw=Decimal(0),
        turnover_pct=Decimal(10),
    )
    trade = PortfolioTrade(
        decided_at=datetime(2024, 1, 29, tzinfo=UTC),
        executed_at=datetime(2024, 1, 30, tzinfo=UTC),
        symbol="A",
        side="buy",
        quantity=1,
        local_price=Decimal(100),
        fx_rate=Decimal(1),
        notional_krw=Decimal(100),
        transaction_cost_krw=Decimal(0),
        fx_cost_krw=Decimal(0),
    )
    simulation = PortfolioSimulation(
        candidate=candidate,
        period_start=date(2024, 1, 30),
        period_end=date(2024, 3, 1),
        metrics=metrics,
        complete=True,
        incomplete_reasons=[],
        drawdown_latched=False,
        drawdown_latched_at=None,
        equity=[
            PortfolioEquityPoint(
                at=datetime(2024, 1, 30, 20, tzinfo=UTC),
                equity_krw=Decimal(1000),
                cash_krw=Decimal(900),
                drawdown_pct=Decimal(0),
            ),
            PortfolioEquityPoint(
                at=datetime(2024, 2, 1, 20, tzinfo=UTC),
                equity_krw=Decimal(1000),
                cash_krw=Decimal(900),
                drawdown_pct=Decimal(0),
            ),
            PortfolioEquityPoint(
                at=datetime(2024, 3, 1, 20, tzinfo=UTC),
                equity_krw=Decimal(1000),
                cash_krw=Decimal(1000),
                drawdown_pct=Decimal(0),
            ),
        ],
        trades=[trade],
        weekly_targets=[],
        positions=[],
        contributions_krw={},
        split_cash_in_lieu_krw={},
        overlap_diagnostics={},
    )
    diagnostics = policy_diagnostics(simulation)
    assert diagnostics.trading_utc_days == 1
    assert diagnostics.invested_days_pct == Decimal(2) / Decimal(3) * 100
    assert [item.trade_count for item in diagnostics.monthly] == [1, 0, 0]
    assert [item.active for item in diagnostics.monthly] == [True, True, False]
    assert diagnostics.monthly[0].turnover_pct == Decimal(10)
    assert diagnostics.active_month_trade_average == Decimal("0.5")
    assert diagnostics.active_month_trade_maximum == 1


def test_config_rejects_invalid_cash_and_caps() -> None:
    with pytest.raises(ValidationError):
        PortfolioConfig(initial_cash_krw=Decimal(0))
    with pytest.raises(ValidationError):
        PortfolioConfig(symbol_cap=Decimal("0.8"), gross_cap=Decimal("0.6"))


def test_run_is_immutable_idempotent_and_failed_attempt_keeps_latest(
    tmp_path: Path,
) -> None:
    config = PortfolioConfig(warmup_sessions=5, validation_sessions=5)
    source = _source()
    first = run_portfolio_research(source, tmp_path, config)
    second = run_portfolio_research(source, tmp_path, config)
    repository = PortfolioRunRepository(tmp_path)
    assert second == first
    assert repository.latest() == first
    assert (repository.run_dir(first.run_id) / "manifest.json").is_file()
    assert first.policy_experiment is not None
    assert len(first.policy_experiment.comparisons) == 5
    for name in (
        "policy-comparison.csv",
        "policy-monthly.csv",
        "policy-events.csv",
    ):
        assert repository.artifact_path(first.run_id, name).is_file()
    with pytest.raises(ValueError):
        repository.artifact_path(first.run_id, "manifest.json")
    repository.record_failure("f" * 64, RuntimeError("secret detail"))
    assert repository.latest() == first
    with pytest.raises(ValueError):
        repository.artifact_path("../escape", "result.json")
    with pytest.raises(ValueError):
        repository.artifact_path(first.run_id, "../../etc/passwd")


def test_old_portfolio_result_without_policy_fields_still_parses(
    tmp_path: Path,
) -> None:
    result = run_portfolio_research(
        _source(),
        tmp_path,
        PortfolioConfig(warmup_sessions=5, validation_sessions=5),
    )
    payload = result.model_dump(mode="json")
    payload.pop("policy_experiment")
    for field in (
        "reentry_cooldown_days",
        "recovery_confirmations",
        "recovery_minimum_assets",
        "volatility_target",
        "volatility_annualization_sessions",
        "low_turnover_weeks",
        "low_turnover_band",
    ):
        payload["config"].pop(field)
    for name in ("heldout", "equal_baseline", "cost_stress"):
        payload[name].pop("policy")
        payload[name].pop("policy_events")
    parsed = PortfolioRunResult.model_validate(payload)
    assert parsed.policy_experiment is None
    assert parsed.heldout.policy == "corrected_control"


def test_cached_a_after_b_moves_latest_pointer_back_to_a(tmp_path: Path) -> None:
    config = PortfolioConfig(warmup_sessions=5, validation_sessions=5)
    source_a = _source()
    source_b = source_a.model_copy(
        update={
            "stock_snapshot_ids": {
                **source_a.stock_snapshot_ids,
                "KRTEST": "changed-snapshot",
            }
        }
    )
    first_a = run_portfolio_research(source_a, tmp_path, config)
    result_b = run_portfolio_research(source_b, tmp_path, config)
    assert result_b.run_id != first_a.run_id
    cached_a = run_portfolio_research(source_a, tmp_path, config)
    assert cached_a == first_a
    assert PortfolioRunRepository(tmp_path).latest() == first_a


def test_failed_store_run_marks_latest_stale_without_replacing_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report_dir = tmp_path / "reports"
    source = _source()
    completed = run_portfolio_research(
        source,
        report_dir,
        PortfolioConfig(warmup_sessions=5, validation_sessions=5),
    )
    repository = PortfolioRunRepository(report_dir)
    repository.save_status(
        PortfolioRunStatus(
            status="success",
            last_attempt_at=completed.created_at,
            last_success_at=completed.created_at,
            latest_run_id=completed.run_id,
        )
    )
    monkeypatch.setattr(
        "jusik.research_portfolio.load_portfolio_input",
        lambda _input, _external: source,
    )

    def fail_run(*_args: object, **_kwargs: object) -> object:
        raise ValueError("forced failure")

    monkeypatch.setattr("jusik.research_portfolio.run_portfolio_research", fail_run)
    with pytest.raises(ValueError, match="forced failure"):
        run_from_stores(tmp_path / "input.db", tmp_path / "external.db", report_dir)

    assert repository.latest() == completed
    status = repository.status()
    assert status.status == "error"
    assert status.latest_stale
    assert status.latest_run_id == completed.run_id
    assert status.error_code == "ValueError"


class _UnusedProvider:
    async def collect(self, _request: ResearchRunRequest) -> object:
        raise AssertionError("not used")


def test_portfolio_api_serves_allowlisted_artifacts_only(tmp_path: Path) -> None:
    result = run_portfolio_research(
        _source(),
        tmp_path / "reports",
        PortfolioConfig(warmup_sessions=5, validation_sessions=5),
    )
    repository = PortfolioRunRepository(tmp_path / "reports")
    repository.save_status(
        PortfolioRunStatus(
            status="error",
            last_attempt_at=datetime(2024, 3, 5, tzinfo=UTC),
            last_success_at=result.created_at,
            latest_run_id=result.run_id,
            error_code="ValueError",
            latest_stale=True,
        )
    )
    settings = ResearchSettings(
        app_key="key",
        app_secret="secret",
        base_url=PAPER_BASE_URL,
        db_path=tmp_path / "research.db",
    )
    app = create_research_app(
        action_collection_enabled=False,
        settings=settings,
        store=ResearchStore(tmp_path / "research.db"),
        provider=_UnusedProvider(),  # type: ignore[arg-type]
        portfolio_report_dir=tmp_path / "reports",
    )
    with TestClient(app) as client:
        latest = client.get("/api/research/portfolio/latest")
        assert latest.status_code == 200
        assert latest.json()["run_id"] == result.run_id
        current_status = client.get("/api/research/portfolio/status")
        assert current_status.status_code == 200
        assert current_status.json()["latest_stale"] is True
        assert current_status.json()["latest_run_id"] == result.run_id
        artifact = client.get(
            f"/api/research/portfolio/runs/{result.run_id}/artifacts/report.md"
        )
        assert artifact.status_code == 200
        assert artifact.headers["x-content-type-options"] == "nosniff"
        policy_artifact = client.get(
            f"/api/research/portfolio/runs/{result.run_id}/artifacts/"
            "policy-comparison.csv"
        )
        assert policy_artifact.status_code == 200
        assert "low_turnover_combined" in policy_artifact.text
        rejected = client.get(
            f"/api/research/portfolio/runs/{result.run_id}/artifacts/secret.env"
        )
        assert rejected.status_code == 404
