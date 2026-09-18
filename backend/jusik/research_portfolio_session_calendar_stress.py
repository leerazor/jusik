"""Offline calendar adapter and bounded portfolio calendar stress harness.

This module deliberately loads a copied portfolio engine.  The product research
engine is never imported for mutation and no historical data is fetched.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import statistics
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_FLOOR, Decimal, localcontext
from pathlib import Path
from types import ModuleType
from typing import Any, Literal, cast

from jusik.research_external_models import ExternalFeatureSnapshot, ExternalObservation
from jusik.research_market_calendar import (
    DEFAULT_CALENDAR_PATH,
    MarketCalendar,
    MarketSession,
    load_market_calendar,
)
from jusik.research_models import DailyBar
from jusik.research_portfolio_models import (
    PortfolioCandidate,
    PortfolioConfig,
    PortfolioInput,
)
from jusik.research_universe_models import (
    CorporateAction,
    DataProvenance,
    OfflineInstrumentSnapshot,
    OfflineResearchSnapshot,
    PriceAdjustmentFactor,
    ResearchInstrument,
)

CALENDAR_SHA256 = "ba26619a27e066ca32b1aaaf3b7da2b99f0c6658f731a000c5095c057081c1d8"
ENGINE_PATH = Path(__file__).with_name("research_portfolio_engine.py")


class CalendarStressError(ValueError):
    """A calendar, data-completeness, causality, or accounting gate failed."""


class IncompleteSessionError(CalendarStressError):
    pass


@dataclass(frozen=True)
class SessionEvent:
    at: datetime
    kind: str
    symbol: str
    day: date


PublicationMetadata = Mapping[tuple[str, date], datetime]


def _exchange_for_timezone(timezone_name: str) -> str:
    if timezone_name == "Asia/Seoul":
        return "KRX"
    if timezone_name == "America/New_York":
        return "NYS"
    raise CalendarStressError(f"exchange_unavailable:{timezone_name}")


class CalendarAdapter:
    """Fail-closed view of the committed exchange session artifact."""

    def __init__(
        self,
        path: Path = DEFAULT_CALENDAR_PATH,
        *,
        publication: PublicationMetadata | None = None,
    ) -> None:
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise CalendarStressError("calendar_file_unavailable") from exc
        digest = hashlib.sha256(raw).hexdigest()
        if digest != CALENDAR_SHA256:
            raise CalendarStressError("calendar_hash_mismatch")
        self.path = path
        self.publication = dict(publication or {})
        for key, published in self.publication.items():
            if published.tzinfo is None:
                raise CalendarStressError("bar_publication_timestamp_naive")
            if not isinstance(key, tuple) or len(key) != 2:
                raise CalendarStressError("bar_publication_identity_invalid")
        self.calendar: MarketCalendar = load_market_calendar(path)
        if not self.calendar.available:
            raise CalendarStressError(self.calendar.error or "calendar_unavailable")

    def lookup(self, timezone_name: str, local_date: date) -> MarketSession | None:
        exchange = _exchange_for_timezone(timezone_name)
        result = self.calendar.lookup(exchange, local_date)
        if result.state == "closed":
            return None
        if result.state == "unavailable" or result.session is None:
            raise CalendarStressError(
                f"unknown_session:{exchange}:{local_date.isoformat()}"
            )
        return result.session

    def events(
        self,
        data: dict[str, Any],
        start: date,
        end: date,
        *,
        bar_dates: Callable[[Any], set[date]] | None = None,
        calendar: MarketCalendar | None = None,
    ) -> list[SessionEvent]:
        del calendar
        result: list[SessionEvent] = []
        for symbol, item in data.items():
            bars = item.bars_by_date
            available = set(bars) if bar_dates is None else bar_dates(item)
            for day in sorted(d for d in available if start <= d <= end):
                session = self.lookup(item.instrument.timezone, day)
                if session is None:
                    continue
                result.extend(
                    (
                        SessionEvent(session.open_at, "open", symbol, day),
                        SessionEvent(session.close_at, "close", symbol, day),
                    )
                )
        return sorted(result, key=lambda event: (event.at, event.kind, event.symbol))

    def require_publication(self, data: dict[str, Any]) -> None:
        for item in data.values():
            for bar in item.snapshot.instruments[0].bars:
                published = self.publication.get((item.instrument.symbol, bar.date))
                if published is None:
                    raise CalendarStressError(
                        f"bar_publication_metadata_missing:{item.instrument.symbol}:{bar.date}"
                    )
                if published.tzinfo is None:
                    raise CalendarStressError("bar_publication_timestamp_naive")

    def require_source_publication(self, source: PortfolioInput) -> None:
        for snapshot in source.instruments:
            instrument = snapshot.instruments[0]
            for bar in instrument.bars:
                published = self.publication.get((instrument.symbol, bar.date))
                if published is None:
                    raise CalendarStressError(
                        f"bar_publication_metadata_missing:{instrument.symbol}:{bar.date}"
                    )
                if published.tzinfo is None:
                    raise CalendarStressError("bar_publication_timestamp_naive")

    def require_complete_bars(
        self, data: dict[str, Any], start: date, end: date
    ) -> None:
        """Reject a missing first valid open bar instead of silently skipping it."""
        for symbol, item in data.items():
            bars = item.bars_by_date
            cursor = start
            while cursor <= end:
                session = self.lookup(item.instrument.timezone, cursor)
                if session is not None and cursor not in bars:
                    raise IncompleteSessionError(
                        f"missing_first_valid_open_bar:{symbol}:{cursor.isoformat()}"
                    )
                cursor = date.fromordinal(cursor.toordinal() + 1)

    def known_bars(self, item: Any, at: datetime) -> list[Any]:
        result: list[Any] = []
        for bar in item.snapshot.instruments[0].bars:
            session = self.lookup(item.instrument.timezone, bar.date)
            published = self.publication.get((item.instrument.symbol, bar.date))
            if published is None:
                raise CalendarStressError(
                    f"bar_publication_metadata_missing:{item.instrument.symbol}:{bar.date}"
                )
            if published.tzinfo is None:
                raise CalendarStressError("bar_publication_timestamp_naive")
            if session is not None and max(
                session.close_at, published
            ) <= at.astimezone(UTC):
                result.append(bar)
        return result

    def volatility_cutoff(self, item: Any, at: datetime) -> list[Any]:
        return self.known_bars(item, at)


def fixture_publication_metadata(
    source: PortfolioInput, adapter: CalendarAdapter | None = None
) -> dict[tuple[str, date], datetime]:
    """Build explicit aware publication input for the synthetic fixture only."""
    adapter = adapter or CalendarAdapter()
    result: dict[tuple[str, date], datetime] = {}
    for snapshot in source.instruments:
        instrument = snapshot.instruments[0]
        for bar in instrument.bars:
            session = adapter.lookup(instrument.instrument.timezone, bar.date)
            if session is None:
                result[(instrument.symbol, bar.date)] = datetime.combine(
                    bar.date, time(0), UTC
                )
            else:
                result[(instrument.symbol, bar.date)] = session.close_at
    return result


def load_isolated_engine(audit_dir: Path) -> ModuleType:
    """Copy and import the engine under a private module name."""
    audit_dir.mkdir(parents=True, exist_ok=True)
    if any(audit_dir.iterdir()):
        raise CalendarStressError("audit_directory_not_exclusive")
    copied = audit_dir / "research_portfolio_engine.py"
    shutil.copy2(ENGINE_PATH, copied)
    digest = hashlib.sha256(copied.read_bytes()).hexdigest()
    spec = importlib.util.spec_from_file_location(
        f"portfolio_calendar_engine_{digest[:12]}", copied
    )
    if spec is None or spec.loader is None:
        raise CalendarStressError("isolated_engine_load_failed")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def install_calendar_adapter(engine: ModuleType, adapter: CalendarAdapter) -> None:
    """Patch only the copied module's globals used by simulation."""

    def events(
        data: dict[str, Any],
        start: date,
        end: date,
        *,
        calendar: MarketCalendar | None = None,
    ) -> list[Any]:
        converted = [
            engine.MarketEvent(item.at, item.kind, item.symbol, item.day)
            for item in adapter.events(data, start, end, calendar=calendar)
        ]
        cursor = start
        while cursor <= end:
            if cursor.weekday() == 0:
                converted.append(
                    engine.MarketEvent(
                        datetime.combine(cursor, datetime.min.time(), UTC),
                        "rebalance",
                    )
                )
            cursor = date.fromordinal(cursor.toordinal() + 1)
        return sorted(
            converted,
            key=lambda item: (
                item.at,
                {"rebalance": 0, "open": 1, "close": 2}[item.kind],
                item.symbol or "",
            ),
        )

    def known(item: Any, at: datetime) -> list[Any]:
        return adapter.known_bars(item, at)

    def volatility(*args: Any, **kwargs: Any) -> Any:
        source, data, weights, at, config = args[:5]
        fx_cache = args[5] if len(args) > 5 else kwargs.get("fx_cache")
        if not weights:
            return Decimal(1), Decimal(0)

        def available_at(item: Any, bar: Any, cutoff: datetime) -> bool:
            session = adapter.lookup(item.instrument.timezone, bar.date)
            published = adapter.publication[(item.instrument.symbol, bar.date)]
            return session is not None and max(session.close_at, published) <= cutoff

        def close_at_for(item: Any, bar: Any) -> datetime | None:
            session = adapter.lookup(item.instrument.timezone, bar.date)
            return session.close_at if session is not None else None

        def required_close_at(item: Any, bar: Any) -> datetime:
            close_at = close_at_for(item, bar)
            if close_at is None:
                raise IncompleteSessionError("volatility_session_unavailable")
            return close_at

        global_day_set: set[date] = set()
        for item in data.values():
            for bar in item.snapshot.instruments[0].bars:
                close_at = close_at_for(item, bar)
                if (
                    close_at is not None
                    and close_at < at
                    and available_at(item, bar, at.astimezone(UTC))
                ):
                    global_day_set.add(close_at.date())
        global_days = sorted(global_day_set)[-(config.volatility_window + 1) :]
        if len(global_days) < config.volatility_window + 1:
            return None, None
        proxy = Decimal(0)
        for symbol, weight in weights.items():
            item = data[symbol]
            values: list[Decimal] = []
            for day in global_days:
                cutoff = min(datetime.combine(day, time.max, UTC), at.astimezone(UTC))
                eligible = [
                    bar
                    for bar in item.snapshot.instruments[0].bars
                    if available_at(item, bar, cutoff)
                ]
                if not eligible:
                    return None, None
                eligible.sort(key=lambda bar: required_close_at(item, bar))
                value = eligible[-1].adjusted_close
                if item.instrument.currency == "USD":
                    if fx_cache is not None and cutoff in fx_cache:
                        fx = fx_cache[cutoff]
                    else:
                        fx = engine._fx_rate(source, cutoff, config)
                        if fx_cache is not None:
                            fx_cache[cutoff] = fx
                    if fx is None:
                        return None, None
                    value *= fx
                values.append(value)
            returns = [
                current / previous - Decimal(1)
                for previous, current in zip(values[:-1], values[1:], strict=True)
            ]
            sigma = (
                statistics.pstdev(returns)
                * Decimal(config.volatility_annualization_sessions).sqrt()
            )
            proxy += weight * sigma
        if proxy == 0:
            return Decimal(1), Decimal(0)
        return min(Decimal(1), config.volatility_target / proxy), proxy

    def market_time(day: date, timezone_name: str, *, opening: bool) -> datetime:
        session = adapter.lookup(timezone_name, day)
        if session is None:
            raise IncompleteSessionError(f"closed_session:{timezone_name}:{day}")
        return session.open_at if opening else session.close_at

    setattr(engine, "_events", events)
    setattr(engine, "_known_bars", known)
    # volatility_scale calls _market_time directly, so replace that private
    # clock in the copied module as well.  The source module remains untouched.
    setattr(engine, "_market_time", market_time)
    setattr(engine, "volatility_scale", volatility)

    original_as_of = engine._as_of_external

    def as_of_external(snapshot: Any, series: str, at: datetime) -> list[Any]:
        rows = original_as_of(snapshot, series, at)
        validate_feature_cutoff(rows, at)
        return cast(list[Any], rows)

    setattr(engine, "_as_of_external", as_of_external)


def synthetic_source() -> PortfolioInput:
    """Typed, deterministic fixture with USD FX and a fractional split."""
    start = date(2023, 10, 2)
    days: list[date] = []
    cursor = start
    while len(days) < 150:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor += timedelta(days=1)
    snapshots: list[OfflineResearchSnapshot] = []
    for symbol, currency, timezone_name in (
        ("SYNKRW", "KRW", "Asia/Seoul"),
        ("SYNUSD", "USD", "America/New_York"),
    ):
        bars = [
            DailyBar(
                date=day,
                open=Decimal(100 + i),
                high=Decimal(101 + i),
                low=Decimal(99 + i),
                close=Decimal(100 + i),
                volume=1000 + i,
                adjusted_open=Decimal(100 + i),
                adjusted_high=Decimal(101 + i),
                adjusted_low=Decimal(99 + i),
                adjusted_close=Decimal(100 + i),
            )
            for i, day in enumerate(days)
        ]
        instrument = ResearchInstrument(
            symbol=symbol,
            yahoo_symbol=symbol,
            name=symbol,
            currency=cast(Literal["KRW", "USD"], currency),
            exchange="KSC" if currency == "KRW" else "NMS",
            timezone=cast(Literal["Asia/Seoul", "America/New_York"], timezone_name),
        )
        item = OfflineInstrumentSnapshot(
            instrument=instrument,
            bars=bars,
            provenance=DataProvenance(price_volume_source="Yahoo chart"),
            source_url="https://example.com/synthetic",
        )
        action = CorporateAction(
            date=days[100], numerator=Decimal(3), denominator=Decimal(2)
        )
        snapshots.append(
            OfflineResearchSnapshot(
                captured_at=datetime(2024, 3, 4, tzinfo=UTC),
                requested_start=days[65],
                requested_end=days[-1],
                evaluation_start=days[65],
                instruments=[item],
                basis_actions=[action],
                corporate_actions=[action],
                adjustment_factors=[
                    PriceAdjustmentFactor(date=day, raw_factor=Decimal(1))
                    for day in days
                ],
            )
        )
    observations = tuple(
        ExternalObservation(
            series="usdkrw",
            observed_on=start + timedelta(days=i),
            value=Decimal("1300"),
            available_at=datetime.combine(start + timedelta(days=i), time(), UTC),
            revision="synthetic",
        )
        for i in range(180)
    )
    return PortfolioInput(
        captured_at=datetime(2024, 3, 4, tzinfo=UTC),
        stock_snapshot_ids={"SYNKRW": "synthetic", "SYNUSD": "synthetic"},
        instruments=snapshots,
        external=ExternalFeatureSnapshot(observations=observations),
    )


def _normal_session_source(
    source: PortfolioInput, adapter: CalendarAdapter, start: date, end: date
) -> PortfolioInput:
    del start, end
    snapshots: list[OfflineResearchSnapshot] = []
    for snapshot in source.instruments:
        instrument = snapshot.instruments[0]
        bars = [
            bar
            for bar in instrument.bars
            if adapter.lookup(instrument.instrument.timezone, bar.date) is not None
        ]
        filtered = instrument.model_copy(update={"bars": bars})
        snapshots.append(snapshot.model_copy(update={"instruments": [filtered]}))
    return source.model_copy(update={"instruments": snapshots})


def validate_feature_cutoff(rows: list[Any], decision_at: datetime) -> None:
    """Require every published feature to be available by its decision."""
    for row in rows:
        published = getattr(row, "published_at", getattr(row, "available_at", None))
        if published is None or published.tzinfo is None:
            raise CalendarStressError("feature_publication_timestamp_missing")
        if published.astimezone(UTC) > decision_at.astimezone(UTC):
            raise CalendarStressError("feature_cutoff_violation")


def simulate_isolated(
    source: Any,
    candidate: Any,
    start: date,
    end: date,
    config: Any,
    policy: Any = "corrected_control",
    *,
    audit_dir: Path,
    adapter: CalendarAdapter | None = None,
) -> Any:
    adapter = adapter or CalendarAdapter()
    engine = load_isolated_engine(audit_dir)
    adapter.require_publication(engine._instrument_data(source))
    source = _normal_session_source(source, adapter, start, end)
    data = engine._instrument_data(source)
    adapter.require_complete_bars(data, start, end)
    install_calendar_adapter(engine, adapter)
    return engine.simulate(source, candidate, start, end, config, policy)


def run_simulation_gate(
    source: Any,
    candidate: Any,
    start: date,
    end: date,
    config: Any,
    policy: Any,
    *,
    audit_dir: Path,
    adapter: CalendarAdapter | None = None,
    publication: PublicationMetadata | None = None,
) -> Any:
    """Exercise the real copied ``simulate`` path and exact normal-session control."""
    adapter = adapter or CalendarAdapter(publication=publication)
    adapter.require_source_publication(source)
    source = _normal_session_source(source, adapter, start, end)
    result = simulate_isolated(
        source,
        candidate,
        start,
        end,
        config,
        policy,
        audit_dir=audit_dir / "calendar-engine",
        adapter=adapter,
    )
    (audit_dir / "calendar-engine" / "simulation.json").write_text(
        result.model_dump_json(indent=2), encoding="utf-8"
    )
    pristine = load_isolated_engine(audit_dir / "pristine-engine")
    control = pristine.simulate(source, candidate, start, end, config, policy)
    # For a normal-session fixture, all serialized fields must match exactly.
    if result.model_dump(mode="json") != control.model_dump(mode="json"):
        raise CalendarStressError("normal_session_control_mismatch")
    if not result.trades:
        raise CalendarStressError("simulation_produced_no_trades")
    for trade in result.trades:
        instrument = next(
            item.instruments[0].instrument
            for item in source.instruments
            if item.instruments[0].symbol == trade.symbol
        )
        assert_next_open(
            trade.decided_at,
            trade.executed_at,
            instrument.exchange,
            adapter,
        )
    return result


def assert_next_open(
    decision_at: datetime,
    execution_at: datetime,
    exchange: str,
    adapter: CalendarAdapter,
) -> None:
    if decision_at.tzinfo is None or execution_at.tzinfo is None:
        raise CalendarStressError("timestamps_must_be_aware")
    if decision_at.astimezone(UTC) >= execution_at.astimezone(UTC):
        raise CalendarStressError("next_open_causality_violation")
    expected = adapter.calendar.next_session(exchange, decision_at)
    if expected is None or execution_at.astimezone(UTC) != expected.open_at:
        raise CalendarStressError("next_open_causality_violation")


def reconcile_decimal_accounting(
    *,
    initial_cash: Decimal,
    final_cash: Decimal,
    terminal_value: Decimal,
    proceeds: Decimal,
    spending: Decimal,
    split_cash: Decimal,
    fees: Decimal,
    fx_cost: Decimal,
) -> Decimal:
    """Independent cash-flow identity; returns residual in KRW."""
    expected_cash = initial_cash + proceeds - spending + split_cash - fees - fx_cost
    # terminal_value is deliberately accepted for callers that also report a
    # terminal NAV; the cash-flow identity is checked before terminal marking.
    del terminal_value
    return final_cash - expected_cash


def _replay_trade_ledger(
    source: PortfolioInput,
    simulation: Any,
    config: PortfolioConfig,
    adapter: CalendarAdapter,
) -> Decimal:
    """Reconstruct the complete simulation ledger from raw fixture inputs."""
    if not simulation.complete:
        raise CalendarStressError("ledger_simulation_incomplete")
    symbols = [snapshot.instruments[0].symbol for snapshot in source.instruments]
    instruments = {
        snapshot.instruments[0].symbol: snapshot.instruments[0]
        for snapshot in source.instruments
    }
    bars = {
        symbol: {bar.date: bar for bar in item.bars}
        for symbol, item in instruments.items()
    }
    actions = {
        snapshot.instruments[0].symbol: {
            action.date: action for action in snapshot.corporate_actions
        }
        for snapshot in source.instruments
    }
    if any(
        len(snapshot.corporate_actions)
        != len({action.date for action in snapshot.corporate_actions})
        for snapshot in source.instruments
    ):
        raise CalendarStressError("ledger_duplicate_corporate_action")
    events: dict[datetime, list[SessionEvent]] = {}
    for symbol, item in instruments.items():
        for day, bar in bars[symbol].items():
            if not simulation.period_start <= day <= simulation.period_end:
                continue
            session = adapter.lookup(item.instrument.timezone, day)
            if session is None:
                continue
            events.setdefault(session.open_at, []).append(
                SessionEvent(session.open_at, "open", symbol, day)
            )
            events.setdefault(session.close_at, []).append(
                SessionEvent(session.close_at, "close", symbol, day)
            )
            del bar
    if not events:
        raise CalendarStressError("ledger_missing_session_events")

    observations = list(source.external.observations)

    def fx_row(at: datetime) -> Any | None:
        by_day: dict[date, Any] = {}
        for row in observations:
            if (
                row.series == "usdkrw"
                and row.observed_on <= at.astimezone(UTC).date()
                and row.available_at.astimezone(UTC) <= at.astimezone(UTC)
            ):
                prior = by_day.get(row.observed_on)
                if prior is None or (row.available_at, row.revision) > (
                    prior.available_at,
                    prior.revision,
                ):
                    by_day[row.observed_on] = row
        return by_day[max(by_day)] if by_day else None

    def fx_at(at: datetime, currency: str) -> Decimal:
        if currency == "KRW":
            return Decimal(1)
        row = fx_row(at)
        if row is None:
            raise CalendarStressError("ledger_missing_fx")
        return row.value

    def require_close(actual: Decimal, expected: Decimal, label: str) -> Decimal:
        difference = abs(actual - expected)
        if difference > Decimal("0.000001"):
            raise CalendarStressError(f"ledger_{label}:{difference}")
        return difference

    def require_exact(actual: Decimal, expected: Decimal, label: str) -> None:
        if actual != expected:
            raise CalendarStressError(f"ledger_{label}")

    trades = list(simulation.trades)
    ordered_trades = sorted(
        trades,
        key=lambda row: (
            row.executed_at,
            0 if row.side == "sell" else 1,
            row.symbol,
        ),
    )
    if trades != ordered_trades:
        raise CalendarStressError("ledger_trade_order")
    trade_by_at: dict[datetime, list[Any]] = {}
    for trade in trades:
        if trade.symbol not in instruments:
            raise CalendarStressError("ledger_unknown_trade_symbol")
        if trade.decided_at.tzinfo is None or trade.executed_at.tzinfo is None:
            raise CalendarStressError("ledger_trade_timestamp_naive")
        if not trade.decided_at < trade.executed_at:
            raise CalendarStressError("ledger_decision_causality")
        if (
            not simulation.period_start
            <= trade.executed_at.astimezone(UTC).date()
            <= simulation.period_end
        ):
            raise CalendarStressError("ledger_trade_outside_period")
        matched = [
            event
            for event in events.get(trade.executed_at.astimezone(UTC), [])
            if event.kind == "open" and event.symbol == trade.symbol
        ]
        if len(matched) != 1:
            raise CalendarStressError("ledger_trade_not_at_session_open")
        assert_next_open(
            trade.decided_at,
            trade.executed_at,
            instruments[trade.symbol].instrument.exchange,
            adapter,
        )
        trade_by_at.setdefault(trade.executed_at.astimezone(UTC), []).append(trade)

    quantities = {symbol: 0 for symbol in symbols}
    cash = config.initial_cash_krw
    split_cash = {symbol: Decimal(0) for symbol in symbols}
    contributions: dict[str, Decimal] = {}
    processed_actions: set[tuple[str, date]] = set()
    latest_close: dict[str, tuple[date, Decimal]] = {}
    expected_points: list[tuple[datetime, Decimal, Decimal]] = []
    residual = Decimal(0)

    def add_contribution(symbol: str, amount: Decimal) -> None:
        contributions[symbol] = contributions.get(symbol, Decimal(0)) + amount

    for at in sorted(events):
        group = events[at]
        opens = sorted(
            (event for event in group if event.kind == "open"),
            key=lambda event: event.symbol,
        )
        for event in opens:
            action = actions[event.symbol].get(event.day)
            if action is not None and quantities[event.symbol] > 0:
                exact = Decimal(quantities[event.symbol]) * action.factor
                whole = int(exact.to_integral_value(rounding=ROUND_FLOOR))
                fraction = exact - whole
                if fraction:
                    value = (
                        fraction
                        * bars[event.symbol][event.day].open
                        * fx_at(at, instruments[event.symbol].instrument.currency)
                    )
                    cash += value
                    split_cash[event.symbol] += value
                    add_contribution(event.symbol, value)
                quantities[event.symbol] = whole
                processed_actions.add((event.symbol, event.day))
        for trade in trade_by_at.get(at, []):
            raw_bar = bars[trade.symbol].get(trade.executed_at.astimezone(UTC).date())
            if raw_bar is None:
                raise CalendarStressError(f"ledger_missing_raw_open:{trade.symbol}")
            item = instruments[trade.symbol]
            fx = fx_at(at, item.instrument.currency)
            multiplier = (
                Decimal(1) - config.slippage_rate
                if trade.side == "sell"
                else Decimal(1) + config.slippage_rate
            )
            expected_price = raw_bar.open * multiplier
            local_notional = Decimal(trade.quantity) * expected_price
            expected_notional = local_notional * fx
            fee_local = local_notional * config.fee_rate
            base = (
                (local_notional + fee_local) * fx
                if trade.side == "buy"
                else (local_notional - fee_local) * fx
            )
            expected_fx_cost = (
                base * config.fx_spread_rate
                if item.instrument.currency == "USD"
                else Decimal(0)
            )
            expected_cost = (
                fee_local * fx
                + Decimal(trade.quantity) * raw_bar.open * config.slippage_rate * fx
            )
            require_exact(trade.local_price, expected_price, "trade_price")
            residual += require_close(
                trade.notional_krw, expected_notional, "trade_notional"
            )
            require_exact(trade.fx_rate, fx, "trade_fx")
            residual += require_close(
                trade.transaction_cost_krw, expected_cost, "trade_cost"
            )
            residual += require_close(
                trade.fx_cost_krw, expected_fx_cost, "trade_fx_cost"
            )
            if trade.side == "buy":
                cash -= base + expected_fx_cost
                quantities[trade.symbol] += trade.quantity
                add_contribution(trade.symbol, -(base + expected_fx_cost))
            else:
                if trade.quantity > quantities[trade.symbol]:
                    raise CalendarStressError("ledger_sell_exceeds_position")
                cash += base - expected_fx_cost
                quantities[trade.symbol] -= trade.quantity
                add_contribution(trade.symbol, base - expected_fx_cost)

        closes = sorted(
            (event for event in group if event.kind == "close"),
            key=lambda event: event.symbol,
        )
        for event in closes:
            latest_close[event.symbol] = (
                event.day,
                bars[event.symbol][event.day].close,
            )
        if closes:
            equity = cash
            for symbol, quantity in quantities.items():
                if quantity <= 0:
                    continue
                latest = latest_close.get(symbol)
                if latest is None:
                    raise CalendarStressError("ledger_missing_close_mark")
                equity += (
                    Decimal(quantity)
                    * latest[1]
                    * fx_at(at, instruments[symbol].instrument.currency)
                )
            expected_points.append((at, cash, equity))

    output_points = list(simulation.equity)
    if len(output_points) != len(expected_points):
        raise CalendarStressError("ledger_equity_point_count")
    for point, (at, expected_cash, expected_equity) in zip(
        output_points, expected_points, strict=True
    ):
        if point.at.astimezone(UTC) != at:
            raise CalendarStressError("ledger_equity_timestamp")
        residual += require_close(point.cash_krw, expected_cash, "equity_cash")
        residual += require_close(point.equity_krw, expected_equity, "equity_value")

    final_at = max(events)
    terminal = Decimal(0)
    expected_positions: dict[
        str, tuple[int, Decimal, Decimal, Decimal, date | None]
    ] = {}
    for symbol, quantity in quantities.items():
        if quantity <= 0:
            continue
        latest = latest_close.get(symbol)
        if latest is None:
            raise CalendarStressError("ledger_missing_terminal_price")
        fx = fx_at(final_at, instruments[symbol].instrument.currency)
        value = Decimal(quantity) * latest[1] * fx
        fx_observation = fx_row(final_at)
        fx_observed = (
            fx_observation.observed_on
            if instruments[symbol].instrument.currency == "USD"
            and fx_observation is not None
            else None
        )
        expected_positions[symbol] = (quantity, latest[1], fx, value, fx_observed)
        terminal += value
        add_contribution(symbol, value)
    output_positions = list(simulation.positions)
    if len({position.symbol for position in output_positions}) != len(output_positions):
        raise CalendarStressError("ledger_duplicate_position")
    if any(position.quantity <= 0 for position in output_positions):
        raise CalendarStressError("ledger_nonpositive_position")
    if set(position.symbol for position in output_positions) != set(expected_positions):
        raise CalendarStressError("ledger_position_symbols")
    for position in output_positions:
        quantity, local_close, fx, value, fx_observed = expected_positions[
            position.symbol
        ]
        if (
            position.quantity != quantity
            or position.valued_at.astimezone(UTC) != final_at
        ):
            raise CalendarStressError("ledger_terminal_position")
        require_exact(position.local_close, local_close, "terminal_price")
        require_exact(position.fx_rate, fx, "terminal_fx")
        residual += require_close(position.value_krw, value, "terminal_value")
        residual += require_close(
            position.weight,
            value / simulation.metrics.final_equity_krw,
            "terminal_weight",
        )
        if position.fx_observed_on != fx_observed:
            raise CalendarStressError("ledger_terminal_fx_observed_on")
    residual += require_close(
        cash + terminal, simulation.metrics.final_equity_krw, "final_equity"
    )
    residual += require_close(
        simulation.equity[-1].equity_krw,
        simulation.metrics.final_equity_krw,
        "terminal_equity",
    )
    residual += require_close(simulation.equity[-1].cash_krw, cash, "terminal_cash")

    for symbol in set(split_cash) | set(simulation.split_cash_in_lieu_krw):
        residual += require_close(
            simulation.split_cash_in_lieu_krw.get(symbol, Decimal(0)),
            split_cash.get(symbol, Decimal(0)),
            "split_cash",
        )
    if set(simulation.contributions_krw) != set(contributions):
        raise CalendarStressError("ledger_contribution_symbols")
    for symbol, expected in contributions.items():
        residual += require_close(
            simulation.contributions_krw[symbol], expected, "contribution"
        )
    transaction_cost = sum((trade.transaction_cost_krw for trade in trades), Decimal(0))
    fx_cost = sum((trade.fx_cost_krw for trade in trades), Decimal(0))
    turnover = sum((trade.notional_krw for trade in trades), Decimal(0))
    residual += require_close(
        simulation.metrics.transaction_cost_krw, transaction_cost, "metrics_cost"
    )
    residual += require_close(
        simulation.metrics.fx_cost_krw, fx_cost, "metrics_fx_cost"
    )
    residual += require_close(
        simulation.metrics.turnover_pct,
        turnover / config.initial_cash_krw * 100,
        "metrics_turnover",
    )
    if simulation.metrics.trade_count != len(trades):
        raise CalendarStressError("ledger_trade_count")
    if residual > Decimal("0.000001"):
        raise CalendarStressError(f"ledger_residual:{residual}")
    return residual


def replay_trade_ledger(
    source: PortfolioInput,
    simulation: Any,
    config: PortfolioConfig,
    *,
    adapter: CalendarAdapter | None = None,
) -> Decimal:
    with localcontext() as context:
        context.prec = 40
        return _replay_trade_ledger(
            source, simulation, config, adapter or CalendarAdapter()
        )


def run_stress_harness(
    output_dir: Path, *, calendar_path: Path = DEFAULT_CALENDAR_PATH
) -> dict[str, Any]:
    """Run deterministic gates and persist evidence before returning."""
    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.iterdir()):
        raise CalendarStressError("output_directory_not_exclusive")
    try:
        base_adapter = CalendarAdapter(calendar_path)
        checks: dict[str, str] = {}
        for name, timezone_name, day in (
            ("nyse_holiday", "America/New_York", date(2026, 7, 3)),
            ("early_close", "America/New_York", date(2026, 11, 27)),
            ("christmas_early_close", "America/New_York", date(2026, 12, 24)),
            ("winter_close", "America/New_York", date(2026, 12, 23)),
            ("dst_before", "America/New_York", date(2024, 3, 8)),
            ("dst_after", "America/New_York", date(2024, 3, 11)),
            ("krx_offset", "Asia/Seoul", date(2025, 11, 13)),
        ):
            session = base_adapter.lookup(timezone_name, day)
            checks[name] = (
                "closed"
                if session is None
                else f"{session.open_at.isoformat()}->{session.close_at.isoformat()}"
            )
        holiday_events = base_adapter.events(
            {
                "holiday": type(
                    "Item",
                    (),
                    {
                        "instrument": type("I", (), {"timezone": "America/New_York"})(),
                        "bars_by_date": {date(2026, 7, 3): object()},
                    },
                )()
            },
            date(2026, 7, 3),
            date(2026, 7, 3),
        )
        if holiday_events:
            raise CalendarStressError("closed_holiday_event_created")
        source = synthetic_source()
        publication = fixture_publication_metadata(source, base_adapter)
        adapter = CalendarAdapter(calendar_path, publication=publication)
        source = _normal_session_source(
            source, adapter, date(2024, 1, 3), date(2024, 3, 15)
        )
        (output_dir / "fixture.json").write_text(
            source.model_dump_json(indent=2), encoding="utf-8"
        )
        (output_dir / "publication.json").write_text(
            json.dumps(
                {
                    f"{symbol}:{day.isoformat()}": published.isoformat()
                    for (symbol, day), published in sorted(publication.items())
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
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
        simulation = run_simulation_gate(
            source,
            PortfolioCandidate(id="equal", method="equal", gate="none"),
            date(2024, 1, 3),
            date(2024, 3, 15),
            config,
            "corrected_control",
            audit_dir=output_dir / "simulation",
            adapter=adapter,
        )
        if not simulation.trades:
            raise CalendarStressError("simulation_produced_no_trades")
        if simulation.metrics.fx_cost_krw <= 0:
            raise CalendarStressError("synthetic_fx_cost_missing")
        if not any(value > 0 for value in simulation.split_cash_in_lieu_krw.values()):
            raise CalendarStressError("synthetic_fractional_split_missing")
        residual = replay_trade_ledger(source, simulation, config, adapter=adapter)
        (output_dir / "simulation.json").write_text(
            simulation.model_dump_json(indent=2), encoding="utf-8"
        )
        validate_feature_cutoff(
            [type("Feature", (), {"published_at": datetime(2024, 1, 2, tzinfo=UTC)})()],
            datetime(2024, 1, 3, tzinfo=UTC),
        )
        if abs(residual) > Decimal("0.000001"):
            raise CalendarStressError(f"accounting_residual:{residual}")
        result = {
            "calendar_sha256": CALENDAR_SHA256,
            "checks": checks,
            "accounting_residual_krw": str(residual),
            "fixture_sha256": hashlib.sha256(
                (output_dir / "fixture.json").read_bytes()
            ).hexdigest(),
            "publication_sha256": hashlib.sha256(
                (output_dir / "publication.json").read_bytes()
            ).hexdigest(),
        }
        results_path = output_dir / "results.json"
        results_path.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        files = {}
        for path in sorted(output_dir.rglob("*")):
            if path.is_file() and path.name != "hash-manifest.json":
                files[str(path.relative_to(output_dir))] = hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
        manifest: dict[str, Any] = {
            "files": files,
            "calendar_input_sha256": hashlib.sha256(
                calendar_path.read_bytes()
            ).hexdigest(),
            "source_sha256": result["fixture_sha256"],
            "fixture_sha256": result["fixture_sha256"],
            "publication_sha256": result["publication_sha256"],
            "results_sha256": hashlib.sha256(results_path.read_bytes()).hexdigest(),
            "engine_sha256": files.get(
                "simulation/calendar-engine/research_portfolio_engine.py"
            ),
        }
        (output_dir / "hash-manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return result
    except Exception as exc:
        failure = {"status": "failed", "error": str(exc)}
        failure_path = output_dir / "failure.json"
        failure_path.write_text(
            json.dumps(failure, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        failure_manifest: dict[str, Any] = {
            "files": {
                str(path.relative_to(output_dir)): hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
                for path in output_dir.rglob("*")
                if path.is_file() and path.name != "hash-manifest.json"
            }
        }
        if calendar_path.exists():
            failure_manifest["calendar_input_sha256"] = hashlib.sha256(
                calendar_path.read_bytes()
            ).hexdigest()
        for name in ("fixture.json", "results.json"):
            path = output_dir / name
            if path.exists():
                failure_manifest[f"{name.removesuffix('.json')}_sha256"] = (
                    hashlib.sha256(path.read_bytes()).hexdigest()
                )
        failure_manifest["failure_sha256"] = hashlib.sha256(
            failure_path.read_bytes()
        ).hexdigest()
        (output_dir / "hash-manifest.json").write_text(
            json.dumps(failure_manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        raise


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    run_stress_harness(parser.parse_args().output)
