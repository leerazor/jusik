"""Offline calendar adapter and bounded portfolio calendar stress harness.

This module deliberately loads a copied portfolio engine.  The product research
engine is never imported for mutation and no historical data is fetched.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
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


def _exchange_for_timezone(timezone_name: str) -> str:
    if timezone_name == "Asia/Seoul":
        return "KRX"
    if timezone_name == "America/New_York":
        return "NYS"
    raise CalendarStressError(f"exchange_unavailable:{timezone_name}")


class CalendarAdapter:
    """Fail-closed view of the committed exchange session artifact."""

    def __init__(self, path: Path = DEFAULT_CALENDAR_PATH) -> None:
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise CalendarStressError("calendar_file_unavailable") from exc
        digest = hashlib.sha256(raw).hexdigest()
        if digest != CALENDAR_SHA256:
            raise CalendarStressError("calendar_hash_mismatch")
        self.path = path
        self.publication: dict[tuple[str, date], datetime] = {}
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
    ) -> list[SessionEvent]:
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
            published = self.publication.get(
                (item.instrument.symbol, bar.date),
                session.close_at if session else at,
            )
            if session is not None and max(
                session.close_at, published
            ) <= at.astimezone(UTC):
                result.append(bar)
        return result

    def volatility_cutoff(self, item: Any, at: datetime) -> list[Any]:
        return self.known_bars(item, at)


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

    def events(data: dict[str, Any], start: date, end: date) -> list[Any]:
        converted = [
            engine.MarketEvent(item.at, item.kind, item.symbol, item.day)
            for item in adapter.events(data, start, end)
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

    original_volatility = engine.volatility_scale

    def volatility(*args: Any, **kwargs: Any) -> Any:
        source, data, weights, at, config = args[:5]
        filtered: dict[str, Any] = {}
        for symbol, item in data.items():
            bars = adapter.known_bars(item, at)
            snapshot = item.snapshot.model_copy(
                update={
                    "instruments": [
                        item.snapshot.instruments[0].model_copy(update={"bars": bars})
                    ]
                }
            )
            filtered[symbol] = replace(
                item, snapshot=snapshot, bars_by_date={b.date: b for b in bars}
            )
        return original_volatility(
            source, filtered, weights, at, config, kwargs.get("fx_cache")
        )

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
    snapshots: list[OfflineResearchSnapshot] = []
    for snapshot in source.instruments:
        instrument = snapshot.instruments[0]
        bars = [
            bar
            for bar in instrument.bars
            if not (start <= bar.date <= end)
            or adapter.lookup(instrument.instrument.timezone, bar.date) is not None
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
) -> Any:
    """Exercise the real copied ``simulate`` path and exact normal-session control."""
    adapter = adapter or CalendarAdapter()
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
    expected = (
        initial_cash
        + proceeds
        - spending
        + split_cash
        - fees
        - fx_cost
        + terminal_value
    )
    return final_cash + terminal_value - expected


def replay_trade_ledger(
    source: PortfolioInput, simulation: Any, config: PortfolioConfig
) -> Decimal:
    """Recompute trade execution fields from raw opens and independent FX rows."""
    instruments = {
        item.instruments[0].symbol: item.instruments[0] for item in source.instruments
    }
    observations = sorted(
        source.external.observations, key=lambda row: row.available_at
    )
    residual = Decimal(0)
    for trade in simulation.trades:
        item = instruments[trade.symbol]
        bar = next(
            (
                bar
                for bar in item.bars
                if bar.date == trade.executed_at.astimezone(UTC).date()
            ),
            None,
        )
        if bar is None:
            raise CalendarStressError(f"ledger_missing_raw_open:{trade.symbol}")
        fx = Decimal(1)
        if item.instrument.currency == "USD":
            rows = [
                row
                for row in observations
                if row.series == "usdkrw" and row.available_at <= trade.executed_at
            ]
            if not rows:
                raise CalendarStressError("ledger_missing_fx")
            fx = rows[-1].value
        multiplier = (
            Decimal(1) - config.slippage_rate
            if trade.side == "sell"
            else Decimal(1) + config.slippage_rate
        )
        expected_price = bar.open * multiplier
        expected_notional = Decimal(trade.quantity) * expected_price * fx
        residual += abs(trade.local_price - expected_price)
        residual += abs(trade.notional_krw - expected_notional)
        if item.instrument.currency == "USD" and trade.fx_cost_krw <= 0:
            raise CalendarStressError("ledger_fx_cost_missing")
    if residual > Decimal("0.000001"):
        raise CalendarStressError(f"ledger_residual:{residual}")
    return residual


def run_stress_harness(
    output_dir: Path, *, calendar_path: Path = DEFAULT_CALENDAR_PATH
) -> dict[str, Any]:
    """Run deterministic gates and persist evidence before returning."""
    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.iterdir()):
        raise CalendarStressError("output_directory_not_exclusive")
    try:
        adapter = CalendarAdapter(calendar_path)
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
            session = adapter.lookup(timezone_name, day)
            checks[name] = (
                "closed"
                if session is None
                else f"{session.open_at.isoformat()}->{session.close_at.isoformat()}"
            )
        holiday_events = adapter.events(
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
        source = _normal_session_source(
            source, adapter, date(2024, 1, 3), date(2024, 3, 15)
        )
        (output_dir / "fixture.json").write_text(
            source.model_dump_json(indent=2), encoding="utf-8"
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
        replay_trade_ledger(source, simulation, config)
        (output_dir / "simulation.json").write_text(
            simulation.model_dump_json(indent=2), encoding="utf-8"
        )
        validate_feature_cutoff(
            [type("Feature", (), {"published_at": datetime(2024, 1, 2, tzinfo=UTC)})()],
            datetime(2024, 1, 3, tzinfo=UTC),
        )
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
        if abs(residual) > Decimal("0.000001"):
            raise CalendarStressError(f"accounting_residual:{residual}")
        result = {
            "calendar_sha256": CALENDAR_SHA256,
            "checks": checks,
            "accounting_residual_krw": str(residual),
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
        manifest: dict[str, Any] = {"files": files}
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
            failure_manifest["calendar_input"] = hashlib.sha256(
                calendar_path.read_bytes()
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
