from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Literal

import pytest
from fastapi.testclient import TestClient

from jusik.research_app import create_research_app
from jusik.research_config import PAPER_BASE_URL, ResearchSettings
from jusik.research_external_models import ExternalFeatureSnapshot, ExternalObservation
from jusik.research_external_store import ExternalStore
from jusik.research_forward import (
    ForwardCoordinator,
    bounded_buy_quantity,
    bounded_sell_quantity,
    deferred_constraints_after_sell,
    first_due_at,
    quote_is_eligible,
    regular_session,
    should_skip_low_turnover,
)
from jusik.research_forward_models import ForwardConfig, ForwardIntent
from jusik.research_forward_store import ForwardStore
from jusik.research_history import HistoryRepository, import_public_history
from jusik.research_models import DailyBar, ResearchInputSnapshot, ResearchRunRequest
from jusik.research_portfolio_models import PortfolioInput
from jusik.research_quote_models import (
    ResearchFeedItem,
    ResearchFeedStatus,
    ResearchProtocolCounter,
    ResearchQuote,
)
from jusik.research_universe_models import (
    CorporateAction,
    DataProvenance,
    OfflineInstrumentSnapshot,
    OfflineResearchSnapshot,
    PriceAdjustmentFactor,
    ResearchInstrument,
)
from jusik.research_universe_store import UniverseInputStore


class NoopProvider:
    async def collect(self, _request: ResearchRunRequest) -> ResearchInputSnapshot:
        raise AssertionError("No collection expected in read-only API test.")


def quote(at: datetime, price: str = "100") -> ResearchQuote:
    return ResearchQuote(
        symbol="NVDA",
        exchange="NAS",
        currency="USD",
        price=price,
        ask=price,
        bid=price,
        volume=1,
        accumulated_volume=1,
        market_at=at,
        received_at=at + timedelta(seconds=1),
        source="KIS HDFSCNT0",
    )


def close_source(captured_at: datetime, *, split: bool = False) -> PortfolioInput:
    bars = [
        DailyBar(
            date=day,
            open=value,
            high=value,
            low=value,
            close=value,
            volume=1,
            adjusted_open=value,
            adjusted_high=value,
            adjusted_low=value,
            adjusted_close=value,
        )
        for day, value in [
            (datetime(2026, 9, 2).date(), Decimal("100")),
            (datetime(2026, 9, 3).date(), Decimal("40")),
        ]
    ]
    instrument = OfflineInstrumentSnapshot(
        instrument=ResearchInstrument(
            symbol="005930",
            yahoo_symbol="005930.KS",
            name="test",
            currency="KRW",
            exchange="KSC",
            timezone="Asia/Seoul",
        ),
        bars=bars,
        provenance=DataProvenance(price_volume_source="Yahoo chart"),
        source_url="https://example.com",
    )
    actions = (
        [
            CorporateAction(
                date=bars[-1].date,
                numerator=Decimal(2),
                denominator=Decimal(1),
            )
        ]
        if split
        else []
    )
    snapshot = OfflineResearchSnapshot(
        captured_at=captured_at,
        requested_start=bars[0].date,
        requested_end=bars[-1].date,
        evaluation_start=bars[0].date,
        instruments=[instrument],
        basis_actions=actions,
        corporate_actions=actions,
        adjustment_factors=[
            PriceAdjustmentFactor(date=bar.date, raw_factor=Decimal(1)) for bar in bars
        ],
    )
    return PortfolioInput(
        captured_at=captured_at,
        stock_snapshot_ids={"005930": "snapshot"},
        instruments=[snapshot],
        external=ExternalFeatureSnapshot(observations=[]),
    )


def multi_close_source(
    captured_at: datetime,
    rows: list[
        tuple[ResearchInstrument, list[tuple[datetime, Decimal]], list[CorporateAction]]
    ],
) -> PortfolioInput:
    snapshots: list[OfflineResearchSnapshot] = []
    ids: dict[str, str] = {}
    for instrument, dated_values, actions in rows:
        bars = [
            DailyBar(
                date=at.date(),
                open=value,
                high=value,
                low=value,
                close=value,
                volume=1,
                adjusted_open=value,
                adjusted_high=value,
                adjusted_low=value,
                adjusted_close=value,
            )
            for at, value in dated_values
        ]
        snapshot = OfflineResearchSnapshot(
            captured_at=captured_at,
            requested_start=bars[0].date,
            requested_end=bars[-1].date,
            evaluation_start=bars[0].date,
            instruments=[
                OfflineInstrumentSnapshot(
                    instrument=instrument,
                    bars=bars,
                    provenance=DataProvenance(price_volume_source="Yahoo chart"),
                    source_url="https://example.com",
                )
            ],
            basis_actions=actions,
            corporate_actions=actions,
            adjustment_factors=[
                PriceAdjustmentFactor(date=bar.date, raw_factor=Decimal(1))
                for bar in bars
            ],
        )
        snapshots.append(snapshot)
        ids[instrument.symbol] = f"snapshot-{instrument.symbol}"
    return PortfolioInput(
        captured_at=captured_at,
        stock_snapshot_ids=ids,
        instruments=snapshots,
        external=ExternalFeatureSnapshot(observations=[]),
    )


def kr_quote(at: datetime, price: str = "100") -> ResearchQuote:
    return quote(at, price).model_copy(
        update={
            "symbol": "005930",
            "exchange": "KRX",
            "currency": "KRW",
            "source": "KIS H0STCNT0",
        }
    )


def inactive_feed() -> ResearchFeedStatus:
    return ResearchFeedStatus(
        state="disabled",
        detail="test",
        configured=False,
        items=[],
    )


def feed_with_phase(
    phase: Literal["queued", "awaiting_ack", "approved", "rejected"],
    *,
    frames: int = 0,
    overdue: bool = False,
) -> ResearchFeedStatus:
    return ResearchFeedStatus(
        state="connecting",
        detail="test feed",
        configured=True,
        items=[
            ResearchFeedItem(
                symbol="NVDA",
                exchange="NAS",
                currency="USD",
                state="pending",
                subscription_phase=phase,
                detail="test item",
                requested_at=datetime(2026, 9, 10, tzinfo=UTC),
                ack_overdue=overdue,
            )
        ],
        protocol_counters=[
            ResearchProtocolCounter(
                tr_id="HDFSCNT0",
                data_frame_count=frames,
                valid_quote_count=0,
                parse_failure_count=frames,
            )
        ],
    )


def test_cost_adjusted_buy_and_sell_bounds_cover_existing_holdings() -> None:
    config = ForwardConfig()
    buy = bounded_buy_quantity(
        config=config,
        cash=Decimal("50000"),
        equity=Decimal("100000"),
        holdings={
            "NVDA": Decimal("19000"),
            "AMD": Decimal("16000"),
            "VRT": Decimal("15000"),
        },
        symbol="NVDA",
        mark_unit=Decimal("100"),
        cash_unit=Decimal("102"),
        intent_budget=Decimal("50000"),
        target_weight=Decimal("0.2"),
    )
    assert buy == 9
    final_equity = Decimal("100000") - buy * Decimal("2")
    assert (Decimal("19000") + buy * Decimal("100")) / final_equity <= Decimal("0.2")

    sell = bounded_sell_quantity(
        config=config,
        equity=Decimal("100000"),
        holdings={
            "NVDA": Decimal("21000"),
            "AMD": Decimal("20000"),
            "VRT": Decimal("19000"),
        },
        held_quantity=210,
        symbol="NVDA",
        mark_unit=Decimal("100"),
        net_cash_unit=Decimal("98"),
        target_weight=Decimal("0.2"),
    )
    assert sell == 11
    assert (
        bounded_sell_quantity(
            config=config,
            equity=Decimal("100000"),
            holdings={"NVDA": Decimal("21000")},
            held_quantity=210,
            symbol="NVDA",
            mark_unit=Decimal("100"),
            net_cash_unit=Decimal("98"),
            target_weight=Decimal(),
        )
        == 210
    )

    deferred = deferred_constraints_after_sell(
        config=config,
        equity=Decimal("100000"),
        holdings={"SOXL": Decimal("20000"), "NVDA": Decimal("20000")},
        symbol="NVDA",
        quantity=101,
        mark_unit=Decimal("100"),
        net_cash_unit=Decimal("98"),
    )
    assert deferred == ["symbol:SOXL", "leveraged"]

    assert not should_skip_low_turnover(
        config=config,
        holdings={"NVDA": Decimal("20500")},
        equity=Decimal("100000"),
        symbol="NVDA",
        current_weight=Decimal("0.205"),
        target_weight=Decimal("0.20"),
    )
    assert should_skip_low_turnover(
        config=config,
        holdings={"NVDA": Decimal("19500")},
        equity=Decimal("100000"),
        symbol="NVDA",
        current_weight=Decimal("0.195"),
        target_weight=Decimal("0.20"),
    )


def test_forward_store_fill_is_atomic_idempotent_and_split_is_deduplicated(
    tmp_path: Path,
) -> None:
    store = ForwardStore(tmp_path / "forward.db")
    activated = datetime(2026, 9, 10, tzinfo=UTC)
    session = store.activate(
        activated_at=activated,
        next_due_at=first_due_at(activated),
        source_run_id="fixed",
        config=ForwardConfig(),
    )
    intent = ForwardIntent(
        symbol="NVDA",
        side="buy",
        target_weight="0.2",
        budget_krw="20000000",
        state="pending",
        reason="test",
    )
    decision = store.record_decision(
        session_id=session.id,
        due_at=session.next_due_at,
        recorded_at=session.next_due_at,
        input_version="a" * 64,
        reason="test",
        expires_at=session.next_due_at + timedelta(days=7),
        target_weights={"NVDA": Decimal("0.2")},
        intents=[intent],
    )
    observed = quote(datetime(2026, 9, 14, 14, 0, tzinfo=UTC))
    fill = store.apply_fill(
        decision=decision,
        intent=intent,
        quote=observed,
        quote_id="q",
        fx_rate=Decimal("1300"),
        quantity=10,
        local_fill_price=Decimal("100.1"),
        transaction_cost_krw=Decimal("1301.3"),
        fx_cost_krw=Decimal("1301.3"),
    )
    assert fill is not None
    duplicate = store.apply_fill(
        decision=decision,
        intent=intent,
        quote=observed,
        quote_id="q2",
        fx_rate=Decimal("1300"),
        quantity=10,
        local_fill_price=Decimal("100.1"),
        transaction_cost_krw=Decimal("1301.3"),
        fx_cost_krw=Decimal("1301.3"),
    )
    assert duplicate == fill
    assert len(store.fills(session.id)) == 1
    assert store.active_session() is not None
    assert store.active_session().cash_krw == fill.cash_after_krw  # type: ignore[union-attr]
    assert store.apply_split(session.id, "NVDA", "split-2", 2, 1, observed.received_at)
    assert not store.apply_split(
        session.id, "NVDA", "split-2", 2, 1, observed.received_at
    )
    assert store.positions(session.id)[0].quantity == 20
    assert store.ledger_asof(session.id, observed.received_at) is None
    with pytest.raises(ValueError, match="fractional"):
        store.apply_split(session.id, "NVDA", "split-2-3", 2, 3, observed.received_at)


def test_quote_requires_post_decision_fresh_regular_session(tmp_path: Path) -> None:
    recorded = datetime(2026, 9, 14, 13, 30, tzinfo=UTC)
    store_decision_at = recorded
    # Build through the validated store model to keep the fixture representative.
    store = ForwardStore(tmp_path / "forward.db")
    session = store.activate(
        activated_at=recorded - timedelta(days=4),
        next_due_at=recorded,
        source_run_id="fixed",
        config=ForwardConfig(),
    )
    decision = store.record_decision(
        session_id=session.id,
        due_at=recorded,
        recorded_at=store_decision_at,
        input_version="b" * 64,
        reason="test",
        expires_at=recorded + timedelta(days=7),
        target_weights={},
        intents=[],
    )
    current = recorded + timedelta(seconds=10)
    assert quote_is_eligible(quote(recorded + timedelta(seconds=1)), decision, current)
    assert not quote_is_eligible(
        quote(recorded - timedelta(seconds=1)), decision, current
    )


def test_calendar_blocks_holiday_and_after_early_close_quotes(tmp_path: Path) -> None:
    recorded = datetime(2026, 7, 3, 14, 30, tzinfo=UTC)
    store = ForwardStore(tmp_path / "forward.db")
    session = store.activate(
        activated_at=recorded - timedelta(days=1),
        next_due_at=recorded,
        source_run_id="fixed",
        config=ForwardConfig(),
    )
    decision = store.record_decision(
        session_id=session.id,
        due_at=recorded,
        recorded_at=recorded,
        input_version="8" * 64,
        reason="calendar boundary",
        expires_at=recorded + timedelta(days=7),
        target_weights={},
        intents=[],
    )
    holiday = quote(recorded + timedelta(seconds=1))
    assert not quote_is_eligible(holiday, decision, recorded + timedelta(seconds=5))

    early_close = datetime(2026, 11, 27, 18, tzinfo=UTC)
    boundary_decision = decision.model_copy(
        update={
            "recorded_at": early_close - timedelta(seconds=10),
            "expires_at": early_close + timedelta(days=1),
        }
    )
    assert regular_session(quote(early_close))
    assert not quote_is_eligible(
        quote(early_close + timedelta(seconds=1)),
        boundary_decision,
        early_close + timedelta(seconds=3),
    )


def test_unknown_calendar_quote_is_blocked_and_event_is_deduplicated(
    tmp_path: Path,
) -> None:
    at = datetime(2026, 11, 19, 1, tzinfo=UTC)
    store = ForwardStore(tmp_path / "forward.db")
    session = store.activate(
        activated_at=at - timedelta(days=1),
        next_due_at=at + timedelta(days=7),
        source_run_id="fixed",
        config=ForwardConfig(),
    )
    intent = ForwardIntent(
        symbol="005930",
        side="buy",
        target_weight=Decimal("0.2"),
        budget_krw=Decimal("20000000"),
        state="pending",
        reason="unknown calendar",
    )
    store.record_decision(
        session_id=session.id,
        due_at=at - timedelta(minutes=1),
        recorded_at=at - timedelta(minutes=1),
        input_version="9" * 64,
        reason="unknown calendar",
        expires_at=at + timedelta(days=7),
        target_weights={"005930": Decimal("0.2")},
        intents=[intent],
    )
    current = at + timedelta(seconds=2)
    coordinator = ForwardCoordinator(
        store,
        UniverseInputStore(tmp_path / "universe.db"),
        ExternalStore(tmp_path / "external.db"),
        inactive_feed,
        now=lambda: current,
    )
    observed = kr_quote(at)
    coordinator.on_quote(observed)
    coordinator.on_quote(observed)
    assert not store.fills(session.id)
    blocked = [
        event
        for event in store.events(session.id)
        if event.kind == "calendar_unavailable"
    ]
    assert len(blocked) == 1
    assert "XKRX" in blocked[0].detail


def test_checkpoint_never_uses_partial_nav_when_calendar_is_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    activated = datetime(2026, 11, 17, tzinfo=UTC)
    known_at = datetime(2026, 11, 20, tzinfo=UTC)
    store = ForwardStore(tmp_path / "forward.db")
    session = store.activate(
        activated_at=activated,
        next_due_at=known_at + timedelta(days=7),
        source_run_id="fixed",
        config=ForwardConfig(),
    )
    instruments = [
        ResearchInstrument(
            symbol="005930",
            yahoo_symbol="005930.KS",
            name="KR",
            currency="KRW",
            exchange="KSC",
            timezone="Asia/Seoul",
        ),
        ResearchInstrument(
            symbol="NVDA",
            yahoo_symbol="NVDA",
            name="US",
            currency="USD",
            exchange="NMS",
            timezone="America/New_York",
        ),
    ]
    intents = [
        ForwardIntent(
            symbol=instrument.symbol,
            side="buy",
            target_weight=Decimal("0.2"),
            budget_krw=Decimal("20000"),
            state="pending",
            reason="seed",
        )
        for instrument in instruments
    ]
    decision = store.record_decision(
        session_id=session.id,
        due_at=activated,
        recorded_at=activated,
        input_version="a" * 64,
        reason="seed",
        expires_at=activated + timedelta(days=7),
        target_weights={item.symbol: Decimal("0.2") for item in instruments},
        intents=intents,
    )
    for intent, observed in zip(
        intents,
        [
            kr_quote(datetime(2026, 11, 18, 1, tzinfo=UTC)),
            quote(datetime(2026, 11, 18, 15, tzinfo=UTC)),
        ],
        strict=True,
    ):
        assert store.apply_fill(
            decision=decision,
            intent=intent,
            quote=observed,
            quote_id=f"seed-{intent.symbol}",
            fx_rate=Decimal(1),
            quantity=100,
            local_fill_price=Decimal("100"),
            transaction_cost_krw=Decimal(),
            fx_cost_krw=Decimal(),
        )
    source = multi_close_source(
        known_at,
        [
            (
                instruments[0],
                [
                    (datetime(2026, 11, 18), Decimal("100")),
                    (datetime(2026, 11, 19), Decimal("100")),
                ],
                [],
            ),
            (
                instruments[1],
                [
                    (datetime(2026, 11, 18), Decimal("100")),
                    (datetime(2026, 11, 19), Decimal("100")),
                ],
                [],
            ),
        ],
    )
    coordinator = ForwardCoordinator(
        store,
        UniverseInputStore(tmp_path / "universe.db"),
        ExternalStore(tmp_path / "external.db"),
        inactive_feed,
        now=lambda: known_at,
    )
    monkeypatch.setattr(coordinator, "_load_input", lambda _cutoff: source)
    monkeypatch.setattr(coordinator, "_fx_rate", lambda _at, _currency: Decimal(1))
    coordinator._maybe_daily_checkpoints(session, known_at)
    first_unknown_count = len(
        [
            event
            for event in store.events(session.id, 500)
            if event.kind == "calendar_unavailable"
        ]
    )
    coordinator._maybe_daily_checkpoints(session, known_at)

    events = store.events(session.id, 500)
    unknown = [event for event in events if event.kind == "calendar_unavailable"]
    assert len(unknown) == first_unknown_count
    assert len(unknown) >= 2
    assert any("2026-11-19" in event.detail for event in unknown)
    us_close = datetime(2026, 11, 19, 21, tzinfo=UTC).isoformat()
    assert not any(
        event.kind == "close_checkpoint"
        and event.reference_id == f"checkpoint:{us_close}"
        for event in events
    )


def test_checkpoint_becomes_eligible_only_after_actual_early_close(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    close_at = datetime(2026, 11, 27, 18, tzinfo=UTC)
    store = ForwardStore(tmp_path / "forward.db")
    session = store.activate(
        activated_at=datetime(2026, 11, 26, tzinfo=UTC),
        next_due_at=close_at + timedelta(days=7),
        source_run_id="fixed",
        config=ForwardConfig(),
    )
    instrument = ResearchInstrument(
        symbol="NVDA",
        yahoo_symbol="NVDA",
        name="US",
        currency="USD",
        exchange="NMS",
        timezone="America/New_York",
    )
    source = multi_close_source(
        close_at + timedelta(seconds=1),
        [(instrument, [(datetime(2026, 11, 27), Decimal("100"))], [])],
    )
    coordinator = ForwardCoordinator(
        store,
        UniverseInputStore(tmp_path / "universe.db"),
        ExternalStore(tmp_path / "external.db"),
        inactive_feed,
        now=lambda: close_at,
    )
    monkeypatch.setattr(coordinator, "_load_input", lambda _cutoff: source)

    coordinator._maybe_daily_checkpoints(session, close_at)
    assert not any(
        event.kind == "close_checkpoint" for event in store.events(session.id)
    )
    coordinator._maybe_daily_checkpoints(session, close_at + timedelta(seconds=1))
    assert any(
        event.kind == "close_checkpoint"
        and event.reference_id == f"checkpoint:{close_at.isoformat()}"
        for event in store.events(session.id)
    )


def test_checkpoint_requires_each_holding_latest_completed_session_bar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    activated = datetime(2026, 11, 18, tzinfo=UTC)
    checkpoint = datetime(2026, 11, 20, 21, tzinfo=UTC)
    store = ForwardStore(tmp_path / "forward.db")
    session = store.activate(
        activated_at=activated,
        next_due_at=checkpoint + timedelta(days=7),
        source_run_id="fixed",
        config=ForwardConfig(),
    )
    instruments = [
        ResearchInstrument(
            symbol=symbol,
            yahoo_symbol=symbol,
            name=symbol,
            currency="USD",
            exchange="NMS",
            timezone="America/New_York",
        )
        for symbol in ("NVDA", "MSFT")
    ]
    intents = [
        ForwardIntent(
            symbol=item.symbol,
            side="buy",
            target_weight=Decimal("0.2"),
            budget_krw=Decimal("20000000"),
            state="pending",
            reason="seed",
        )
        for item in instruments
    ]
    decision = store.record_decision(
        session_id=session.id,
        due_at=activated,
        recorded_at=activated,
        input_version="d" * 64,
        reason="seed",
        expires_at=activated + timedelta(days=7),
        target_weights={item.symbol: Decimal("0.2") for item in instruments},
        intents=intents,
    )
    fill_at = datetime(2026, 11, 19, 15, tzinfo=UTC)
    for intent in intents:
        observed = quote(fill_at).model_copy(update={"symbol": intent.symbol})
        assert store.apply_fill(
            decision=decision,
            intent=intent,
            quote=observed,
            quote_id=f"seed-{intent.symbol}",
            fx_rate=Decimal(1),
            quantity=200_000,
            local_fill_price=Decimal("100"),
            transaction_cost_krw=Decimal(),
            fx_cost_krw=Decimal(),
        )
    missing_source = multi_close_source(
        checkpoint + timedelta(seconds=1),
        [
            (instruments[0], [(datetime(2026, 11, 19), Decimal("100"))], []),
            (
                instruments[1],
                [
                    (datetime(2026, 11, 19), Decimal("100")),
                    (datetime(2026, 11, 20), Decimal("1")),
                ],
                [],
            ),
        ],
    )
    source = [missing_source]
    coordinator = ForwardCoordinator(
        store,
        UniverseInputStore(tmp_path / "universe.db"),
        ExternalStore(tmp_path / "external.db"),
        inactive_feed,
        now=lambda: checkpoint + timedelta(seconds=1),
    )
    monkeypatch.setattr(coordinator, "_load_input", lambda _cutoff: source[0])
    monkeypatch.setattr(coordinator, "_fx_rate", lambda _at, _currency: Decimal(1))
    coordinator._maybe_daily_checkpoints(session, checkpoint + timedelta(seconds=1))
    events = store.events(session.id, 500)
    reference = f"checkpoint:{checkpoint.isoformat()}"
    assert not any(
        event.kind == "close_checkpoint" and event.reference_id == reference
        for event in events
    )
    assert not any(event.kind == "risk_exit" for event in events)

    source[0] = multi_close_source(
        checkpoint + timedelta(seconds=2),
        [
            (
                item,
                [
                    (datetime(2026, 11, 19), Decimal("100")),
                    (datetime(2026, 11, 20), Decimal("100")),
                ],
                [],
            )
            for item in instruments
        ],
    )
    coordinator._maybe_daily_checkpoints(session, checkpoint + timedelta(seconds=2))
    assert any(
        event.kind == "close_checkpoint" and event.reference_id == reference
        for event in store.events(session.id, 500)
    )
    assert not any(event.kind == "risk_exit" for event in store.events(session.id))


def test_split_block_begins_at_actual_delayed_krx_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    activated = datetime(2025, 11, 12, tzinfo=UTC)
    store = ForwardStore(tmp_path / "forward.db")
    session = store.activate(
        activated_at=activated,
        next_due_at=activated + timedelta(days=7),
        source_run_id="fixed",
        config=ForwardConfig(),
    )
    seed_intent = ForwardIntent(
        symbol="005930",
        side="buy",
        target_weight=Decimal("0.2"),
        budget_krw=Decimal("20000"),
        state="pending",
        reason="seed",
    )
    seed = store.record_decision(
        session_id=session.id,
        due_at=activated,
        recorded_at=activated,
        input_version="b" * 64,
        reason="seed",
        expires_at=activated + timedelta(days=7),
        target_weights={"005930": Decimal("0.2")},
        intents=[seed_intent],
    )
    seed_quote = kr_quote(datetime(2025, 11, 12, 1, tzinfo=UTC))
    assert store.apply_fill(
        decision=seed,
        intent=seed_intent,
        quote=seed_quote,
        quote_id="seed",
        fx_rate=Decimal(1),
        quantity=100,
        local_fill_price=Decimal("100"),
        transaction_cost_krw=Decimal(),
        fx_cost_krw=Decimal(),
    )
    sell_intent = seed_intent.model_copy(
        update={"side": "sell", "target_weight": Decimal(), "state": "pending"}
    )
    sell = store.record_decision(
        session_id=session.id,
        due_at=datetime(2025, 11, 13, tzinfo=UTC),
        recorded_at=datetime(2025, 11, 13, tzinfo=UTC),
        input_version="c" * 64,
        reason="split",
        expires_at=datetime(2025, 11, 20, tzinfo=UTC),
        target_weights={},
        intents=[sell_intent],
    )
    instrument = ResearchInstrument(
        symbol="005930",
        yahoo_symbol="005930.KS",
        name="KR",
        currency="KRW",
        exchange="KSC",
        timezone="Asia/Seoul",
    )
    action = CorporateAction(
        date=datetime(2025, 11, 13).date(), numerator=2, denominator=1
    )
    source = multi_close_source(
        datetime(2025, 11, 13, 8, tzinfo=UTC),
        [
            (
                instrument,
                [
                    (datetime(2025, 11, 12), Decimal("100")),
                    (datetime(2025, 11, 13), Decimal("50")),
                ],
                [action],
            )
        ],
    )
    clock = [datetime(2025, 11, 13, 0, 30, 2, tzinfo=UTC)]
    coordinator = ForwardCoordinator(
        store,
        UniverseInputStore(tmp_path / "universe.db"),
        ExternalStore(tmp_path / "external.db"),
        inactive_feed,
        now=lambda: clock[0],
    )
    monkeypatch.setattr(coordinator, "_load_input", lambda _cutoff: source)
    monkeypatch.setattr(coordinator, "_fx_rate", lambda _at, _currency: Decimal(1))

    coordinator.on_quote(kr_quote(datetime(2025, 11, 13, 0, 30, tzinfo=UTC)))
    assert len(store.fills(session.id)) == 1
    assert not any(
        event.kind == "corporate_action_blocked" for event in store.events(session.id)
    )

    clock[0] = datetime(2025, 11, 13, 1, 0, 2, tzinfo=UTC)
    coordinator.on_quote(kr_quote(datetime(2025, 11, 13, 1, tzinfo=UTC), "50"))
    assert len(store.fills(session.id)) == 1
    assert any(
        event.kind == "corporate_action_blocked" for event in store.events(session.id)
    )
    pending = next(item for item in store.decisions(session.id) if item.id == sell.id)
    assert pending.intents[0].state == "pending"


def test_history_import_is_digest_allowlisted_and_preserves_journal(
    tmp_path: Path,
) -> None:
    public = tmp_path / "public"
    artifacts = tmp_path / "source"
    artifacts.mkdir()
    body = b"# verified\n"
    digest = hashlib.sha256(body).hexdigest()
    (artifacts / f"{digest}.md").write_bytes(body)
    seed = {
        "schema_version": 1,
        "artifacts": [
            {
                "artifact_id": digest,
                "sha256": digest,
                "title": "proof",
                "filename": f"{digest}.md",
            }
        ],
        "entries": [],
    }
    seed_path = tmp_path / "seed.json"
    seed_path.write_text(json.dumps(seed), encoding="utf-8")
    journal = tmp_path / "journal.db"
    repository = HistoryRepository(public, journal)
    assert repository.record(
        identity="event",
        title="event",
        summary="kept",
        category="system",
        outcome="recorded",
    )
    import_public_history(seed_path, artifacts, public)
    import_public_history(seed_path, artifacts, public)
    assert HistoryRepository(public, journal).page().items[0].id == "event"
    path, _artifact = repository.artifact_path(digest)
    assert path.read_bytes() == body
    with pytest.raises(FileNotFoundError):
        repository.artifact_path("../private.db")


def test_history_keyset_pagination_reaches_large_journal(tmp_path: Path) -> None:
    repository = HistoryRepository(tmp_path / "public", tmp_path / "journal.db")
    base = datetime(2026, 9, 10, tzinfo=UTC)
    for index in range(120):
        assert repository.record(
            identity=f"event-{index:03d}",
            title=f"event {index}",
            summary="bounded",
            category="system",
            outcome="recorded",
            occurred_at=base + timedelta(seconds=index),
        )
    seen: list[str] = []
    cursor = None
    while True:
        page = repository.page(cursor, 25)
        seen.extend(item.id for item in page.items)
        if page.next_cursor is None:
            break
        cursor = page.next_cursor
    assert len(seen) == len(set(seen)) == 120
    assert seen[0] == "event-119"
    assert seen[-1] == "event-000"


def test_feed_history_tracks_phase_and_overdue_without_counter_churn(
    tmp_path: Path,
) -> None:
    current = datetime(2026, 9, 10, tzinfo=UTC)
    feeds = [feed_with_phase("awaiting_ack")]
    history = HistoryRepository(tmp_path / "history", tmp_path / "history.db")
    coordinator = ForwardCoordinator(
        ForwardStore(tmp_path / "forward.db"),
        UniverseInputStore(tmp_path / "universe.db"),
        ExternalStore(tmp_path / "external.db"),
        lambda: feeds[0],
        now=lambda: current,
        history=history,
    )
    coordinator.ensure_session()
    coordinator.tick(current)
    first = [item for item in history.page(limit=100).items if "NVDA" in item.title]
    assert len(first) == 1

    feeds[0] = feed_with_phase("awaiting_ack", frames=7)
    coordinator.tick(current + timedelta(seconds=1))
    unchanged = [item for item in history.page(limit=100).items if "NVDA" in item.title]
    assert len(unchanged) == 1

    feeds[0] = feed_with_phase("awaiting_ack", frames=7, overdue=True)
    coordinator.tick(current + timedelta(seconds=2))
    overdue = [item for item in history.page(limit=100).items if "NVDA" in item.title]
    assert len(overdue) == 2

    feeds[0] = feed_with_phase("approved", frames=7)
    coordinator.tick(current + timedelta(seconds=3))
    approved = [item for item in history.page(limit=100).items if "NVDA" in item.title]
    assert len(approved) == 3


def test_ledger_asof_excludes_later_fill_and_cooldown_uses_strict_28_days(
    tmp_path: Path,
) -> None:
    store = ForwardStore(tmp_path / "forward.db")
    activated = datetime(2026, 9, 7, tzinfo=UTC)
    session = store.activate(
        activated_at=activated,
        next_due_at=activated + timedelta(days=7),
        source_run_id="fixed",
        config=ForwardConfig(),
    )
    first_intent = ForwardIntent(
        symbol="NVDA",
        side="buy",
        target_weight="0.2",
        budget_krw="1000000",
        state="pending",
        reason="first",
    )
    first = store.record_decision(
        session_id=session.id,
        due_at=activated + timedelta(days=1),
        recorded_at=activated + timedelta(days=1),
        input_version="c" * 64,
        reason="first",
        expires_at=activated + timedelta(days=8),
        target_weights={"NVDA": Decimal("0.2")},
        intents=[first_intent],
    )
    first_quote = quote(activated + timedelta(days=1, hours=14))
    assert (
        store.apply_fill(
            decision=first,
            intent=first_intent,
            quote=first_quote,
            quote_id="first",
            fx_rate=Decimal("1"),
            quantity=10,
            local_fill_price=Decimal("100"),
            transaction_cost_krw=Decimal("1"),
            fx_cost_krw=Decimal(),
        )
        is not None
    )
    second_intent = first_intent.model_copy(update={"symbol": "AMD"})
    second = store.record_decision(
        session_id=session.id,
        due_at=activated + timedelta(days=2),
        recorded_at=activated + timedelta(days=2),
        input_version="d" * 64,
        reason="second",
        expires_at=activated + timedelta(days=9),
        target_weights={"AMD": Decimal("0.2")},
        intents=[second_intent],
    )
    second_quote = first_quote.model_copy(
        update={
            "symbol": "AMD",
            "market_at": activated + timedelta(days=2, hours=14),
            "received_at": activated + timedelta(days=2, hours=14, seconds=1),
        }
    )
    assert (
        store.apply_fill(
            decision=second,
            intent=second_intent,
            quote=second_quote,
            quote_id="second",
            fx_rate=Decimal("1"),
            quantity=10,
            local_fill_price=Decimal("100"),
            transaction_cost_krw=Decimal("1"),
            fx_cost_krw=Decimal(),
        )
        is not None
    )
    replayed = store.ledger_asof(session.id, activated + timedelta(days=1, hours=20))
    assert replayed == (Decimal("99998999"), {"NVDA": 10})

    liquidation = datetime(2026, 10, 5, 14, 30, tzinfo=UTC)  # Monday
    store.complete_liquidation(session.id, liquidation)
    active = store.active_session()
    assert active is not None
    assert active.next_recovery_check_at == datetime(2026, 11, 9, tzinfo=UTC)
    assert active.next_recovery_check_at >= liquidation + timedelta(days=28)


def test_confirmed_close_risk_is_reconciled_once_and_quote_only_is_alert(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ForwardStore(tmp_path / "forward.db")
    activated = datetime(2026, 9, 1, tzinfo=UTC)
    session = store.activate(
        activated_at=activated,
        next_due_at=datetime(2026, 9, 7, tzinfo=UTC),
        source_run_id="fixed",
        config=ForwardConfig(),
    )
    buy_intent = ForwardIntent(
        symbol="005930",
        side="buy",
        target_weight=Decimal("0.2"),
        budget_krw=Decimal("20000000"),
        state="pending",
        reason="seed",
    )
    buy = store.record_decision(
        session_id=session.id,
        due_at=activated + timedelta(minutes=1),
        recorded_at=activated + timedelta(minutes=1),
        input_version="1" * 64,
        reason="seed",
        expires_at=activated + timedelta(days=7),
        target_weights={"005930": Decimal("0.2")},
        intents=[buy_intent],
    )
    opening = kr_quote(activated + timedelta(hours=1))
    assert store.apply_fill(
        decision=buy,
        intent=buy_intent,
        quote=opening,
        quote_id="opening",
        fx_rate=Decimal(1),
        quantity=200_000,
        local_fill_price=Decimal("100"),
        transaction_cost_krw=Decimal(),
        fx_cost_krw=Decimal(),
    )
    pending_intent = ForwardIntent(
        symbol="AMD",
        side="buy",
        target_weight=Decimal("0.1"),
        budget_krw=Decimal("10000000"),
        state="pending",
        reason="must be blocked by close risk",
    )
    pending = store.record_decision(
        session_id=session.id,
        due_at=activated + timedelta(minutes=2),
        recorded_at=activated + timedelta(minutes=2),
        input_version="2" * 64,
        reason="pending",
        expires_at=activated + timedelta(days=7),
        target_weights={"AMD": Decimal("0.1")},
        intents=[pending_intent],
    )
    known_at = datetime(2026, 9, 4, tzinfo=UTC)
    clock = [datetime(2026, 9, 3, 7, 0, 2, tzinfo=UTC)]
    coordinator = ForwardCoordinator(
        store,
        UniverseInputStore(tmp_path / "universe.db"),
        ExternalStore(tmp_path / "external.db"),
        inactive_feed,
        now=lambda: clock[0],
    )
    source = close_source(known_at)
    monkeypatch.setattr(coordinator, "_load_input", lambda _cutoff: source)

    coordinator.on_quote(kr_quote(datetime(2026, 9, 3, 7, 0, tzinfo=UTC), "40"))
    assert any(event.kind == "risk_alert" for event in store.events(session.id))
    assert not any(event.kind == "risk_exit" for event in store.events(session.id))

    low_close = datetime(2026, 9, 3, 6, 30, tzinfo=UTC)
    assert store.record_checkpoint(
        session.id,
        low_close,
        known_at,
        Decimal("88000000"),
        Decimal("80000000"),
        {"005930": Decimal("8000000")},
        update_episode=True,
    )
    clock[0] = known_at
    coordinator.tick(known_at)
    events = store.events(session.id)
    assert len([event for event in events if event.kind == "risk_exit"]) == 1
    pending_after = next(
        item for item in store.decisions(session.id) if item.id == pending.id
    )
    assert pending_after.intents[0].state == "blocked"

    sale_time = datetime(2026, 9, 4, 1, tzinfo=UTC)
    clock[0] = sale_time + timedelta(seconds=2)
    coordinator.on_quote(kr_quote(sale_time, "40"))
    coordinator.on_quote(kr_quote(sale_time, "40"))
    assert len(store.fills(session.id)) == 2
    assert all(position.quantity == 0 for position in store.positions(session.id))
    assert store.active_session() is not None
    assert store.active_session().state == "cooldown"  # type: ignore[union-attr]

    restarted = ForwardCoordinator(
        store,
        UniverseInputStore(tmp_path / "universe.db"),
        ExternalStore(tmp_path / "external.db"),
        inactive_feed,
        now=lambda: clock[0],
    )
    monkeypatch.setattr(restarted, "_load_input", lambda _cutoff: source)
    restarted.tick(clock[0])
    assert (
        len([event for event in store.events(session.id) if event.kind == "risk_exit"])
        == 1
    )
    assert len(store.fills(session.id)) == 2


def test_known_split_blocks_checkpoint_and_fill_without_false_drawdown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ForwardStore(tmp_path / "forward.db")
    activated = datetime(2026, 9, 1, tzinfo=UTC)
    session = store.activate(
        activated_at=activated,
        next_due_at=datetime(2026, 9, 7, tzinfo=UTC),
        source_run_id="fixed",
        config=ForwardConfig(),
    )
    intent = ForwardIntent(
        symbol="005930",
        side="buy",
        target_weight=Decimal("0.2"),
        budget_krw=Decimal("20000000"),
        state="pending",
        reason="seed",
    )
    decision = store.record_decision(
        session_id=session.id,
        due_at=activated + timedelta(minutes=1),
        recorded_at=activated + timedelta(minutes=1),
        input_version="3" * 64,
        reason="seed",
        expires_at=activated + timedelta(days=7),
        target_weights={"005930": Decimal("0.2")},
        intents=[intent],
    )
    opening = kr_quote(activated + timedelta(hours=1))
    assert store.apply_fill(
        decision=decision,
        intent=intent,
        quote=opening,
        quote_id="opening",
        fx_rate=Decimal(1),
        quantity=200_000,
        local_fill_price=Decimal("100"),
        transaction_cost_krw=Decimal(),
        fx_cost_krw=Decimal(),
    )
    sell_intent = intent.model_copy(
        update={"side": "sell", "target_weight": Decimal(), "state": "pending"}
    )
    sell = store.record_decision(
        session_id=session.id,
        due_at=activated + timedelta(minutes=2),
        recorded_at=activated + timedelta(minutes=2),
        input_version="4" * 64,
        reason="test split block",
        expires_at=activated + timedelta(days=7),
        target_weights={},
        intents=[sell_intent],
    )
    known_at = datetime(2026, 9, 4, tzinfo=UTC)
    clock = [known_at]
    coordinator = ForwardCoordinator(
        store,
        UniverseInputStore(tmp_path / "universe.db"),
        ExternalStore(tmp_path / "external.db"),
        inactive_feed,
        now=lambda: clock[0],
    )
    source = close_source(known_at, split=True)
    monkeypatch.setattr(coordinator, "_load_input", lambda _cutoff: source)

    sale_time = datetime(2026, 9, 3, 1, tzinfo=UTC)
    clock[0] = sale_time + timedelta(seconds=2)
    coordinator.on_quote(kr_quote(sale_time, "40"))
    assert len(store.fills(session.id)) == 1
    sell_after = next(
        item for item in store.decisions(session.id) if item.id == sell.id
    )
    assert sell_after.intents[0].state == "pending"

    clock[0] = known_at
    coordinator.tick(known_at)
    assert not any(event.kind == "risk_exit" for event in store.events(session.id))
    assert any(
        event.kind == "corporate_action_blocked" for event in store.events(session.id)
    )


def test_stale_daily_fx_blocks_hypothetical_fill(tmp_path: Path) -> None:
    store = ForwardStore(tmp_path / "forward.db")
    external = ExternalStore(tmp_path / "external.db")
    observed = datetime(2026, 9, 1, tzinfo=UTC)
    external.save_success(
        "yahoo_usdkrw",
        body=b"fx",
        content_type="text/csv",
        observations=[
            ExternalObservation(
                series="usdkrw",
                observed_on=observed.date(),
                value=Decimal("1300"),
                available_at=observed,
                revision="test",
            )
        ],
        captured_at=observed,
    )
    current = datetime(2026, 9, 9, 14, 0, 2, tzinfo=UTC)
    session = store.activate(
        activated_at=observed,
        next_due_at=current + timedelta(days=1),
        source_run_id="fixed",
        config=ForwardConfig(),
    )
    intent = ForwardIntent(
        symbol="NVDA",
        side="buy",
        target_weight=Decimal("0.2"),
        budget_krw=Decimal("20000000"),
        state="pending",
        reason="stale FX test",
    )
    decision = store.record_decision(
        session_id=session.id,
        due_at=current - timedelta(minutes=1),
        recorded_at=current - timedelta(minutes=1),
        input_version="5" * 64,
        reason="stale FX test",
        expires_at=current + timedelta(days=7),
        target_weights={"NVDA": Decimal("0.2")},
        intents=[intent],
    )
    coordinator = ForwardCoordinator(
        store,
        UniverseInputStore(tmp_path / "universe.db"),
        external,
        inactive_feed,
        now=lambda: current,
    )
    assert coordinator._fx_rate(observed + timedelta(days=7), "USD") == Decimal("1300")
    assert coordinator._fx_rate(observed + timedelta(days=8), "USD") is None
    coordinator.on_quote(quote(current - timedelta(seconds=2)))
    assert not store.fills(session.id)
    assert any(
        event.kind == "missed_data" and "7일" in event.detail
        for event in store.events(session.id)
    )
    pending_after = next(
        item for item in store.decisions(session.id) if item.id == decision.id
    )
    assert pending_after.intents[0].state == "pending"


def test_sell_records_other_holding_cost_breach(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ForwardStore(tmp_path / "forward.db")
    activated = datetime(2026, 9, 1, tzinfo=UTC)
    session = store.activate(
        activated_at=activated,
        next_due_at=activated + timedelta(days=7),
        source_run_id="fixed",
        config=ForwardConfig(initial_cash_krw=Decimal("100000")),
    )
    seed_intents = [
        ForwardIntent(
            symbol=symbol,
            side="buy",
            target_weight=Decimal("0.2"),
            budget_krw=Decimal("20000"),
            state="pending",
            reason="seed",
        )
        for symbol in ("NVDA", "SOXL")
    ]
    seed = store.record_decision(
        session_id=session.id,
        due_at=activated + timedelta(minutes=1),
        recorded_at=activated + timedelta(minutes=1),
        input_version="6" * 64,
        reason="seed",
        expires_at=activated + timedelta(days=7),
        target_weights={symbol: Decimal("0.2") for symbol in ("NVDA", "SOXL")},
        intents=seed_intents,
    )
    at = datetime(2026, 9, 1, 14, tzinfo=UTC)
    for intent in seed_intents:
        observed = quote(at).model_copy(update={"symbol": intent.symbol})
        assert store.apply_fill(
            decision=seed,
            intent=intent,
            quote=observed,
            quote_id=f"seed-{intent.symbol}",
            fx_rate=Decimal(1),
            quantity=200,
            local_fill_price=Decimal("100"),
            transaction_cost_krw=Decimal(),
            fx_cost_krw=Decimal(),
        )
        store.save_observation(session.id, observed)
    sell_intent = ForwardIntent(
        symbol="NVDA",
        side="sell",
        target_weight=Decimal("0.1"),
        budget_krw=Decimal("10000"),
        state="pending",
        reason="reduce",
    )
    sell = store.record_decision(
        session_id=session.id,
        due_at=activated + timedelta(minutes=2),
        recorded_at=activated + timedelta(minutes=2),
        input_version="7" * 64,
        reason="reduce",
        expires_at=activated + timedelta(days=7),
        target_weights={"NVDA": Decimal("0.1"), "SOXL": Decimal("0.2")},
        intents=[sell_intent],
    )
    coordinator = ForwardCoordinator(
        store,
        UniverseInputStore(tmp_path / "universe.db"),
        ExternalStore(tmp_path / "external.db"),
        inactive_feed,
        now=lambda: at + timedelta(seconds=2),
    )
    monkeypatch.setattr(coordinator, "_fx_rate", lambda _at, _currency: Decimal(1))
    monkeypatch.setattr(coordinator, "_load_input", lambda _cutoff: close_source(at))
    sell_quote = quote(at)
    store.save_observation(session.id, sell_quote)
    coordinator._paper_fill(session, sell, sell_intent, sell_quote, "sell")

    deferred = [
        event
        for event in store.events(session.id)
        if event.kind == "cap_constraint_deferred"
    ]
    assert len(deferred) == 1
    assert "symbol:SOXL" in deferred[0].detail
    assert "leveraged" in deferred[0].detail


def test_worker_failure_is_sanitized_in_status_and_clears_on_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ForwardStore(tmp_path / "forward.db")
    current = datetime(2026, 9, 10, tzinfo=UTC)
    coordinator = ForwardCoordinator(
        store,
        UniverseInputStore(tmp_path / "universe.db"),
        ExternalStore(tmp_path / "external.db"),
        inactive_feed,
        now=lambda: current,
    )
    coordinator.ensure_session()
    original = coordinator._on_quote

    def fail(_quote: ResearchQuote) -> None:
        raise RuntimeError("secret-reflection-must-not-persist")

    monkeypatch.setattr(coordinator, "_on_quote", fail)
    coordinator.on_quote(quote(current))
    status = coordinator.status()
    assert [(item.channel, item.code) for item in status.worker_failures] == [
        ("quote", "internal_error")
    ]
    failure = next(
        event
        for event in store.events(status.session.id)
        if event.kind == "worker_failure"
    )
    assert "secret-reflection" not in failure.detail

    monkeypatch.setattr(coordinator, "_on_quote", original)
    coordinator.on_quote(quote(current))
    assert coordinator.status().worker_failures == []


def test_forward_and_history_read_apis_are_isolated_and_no_store(
    tmp_path: Path,
) -> None:
    history_root = tmp_path / "history"
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    body = b"# public proof\n"
    digest = hashlib.sha256(body).hexdigest()
    (artifacts / f"{digest}.md").write_bytes(body)
    seed = tmp_path / "seed.json"
    seed.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "artifacts": [
                    {
                        "artifact_id": digest,
                        "sha256": digest,
                        "title": "proof",
                        "filename": f"{digest}.md",
                    }
                ],
                "entries": [],
            }
        ),
        encoding="utf-8",
    )
    import_public_history(seed, artifacts, history_root)
    settings = ResearchSettings(
        app_key="key",
        app_secret="secret",
        base_url=PAPER_BASE_URL,
        db_path=tmp_path / "research.db",
    )
    app = create_research_app(
        action_collection_enabled=False,
        settings=settings,
        provider=NoopProvider(),
        portfolio_report_dir=tmp_path / "reports",
        forward_db_path=tmp_path / "forward.db",
        universe_db_path=tmp_path / "universe.db",
        external_db_path=tmp_path / "external.db",
        history_dir=history_root,
        history_db_path=tmp_path / "history-journal.db",
    )
    with TestClient(app) as client:
        response = client.get("/api/research/forward/status")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert response.json()["broker_orders_enabled"] is False
        assert response.json()["calendar"]["provider_version"] == "4.12"
        assert len(response.json()["calendar"]["artifact_sha256"]) == 64
        assert response.json()["action_limitations"]["dividends"] == (
            "excluded_cash_dividends"
        )
        history = client.get("/api/research/history?limit=1")
        assert history.status_code == 200
        assert history.headers["cache-control"] == "no-store"
        download = client.get(f"/api/research/history/artifacts/{digest}")
        assert download.status_code == 200
        assert download.content == body
        assert (
            client.get("/api/research/history/artifacts/private.db").status_code == 404
        )
        (history_root / "artifacts" / f"{digest}.md").write_text("changed")
        assert (
            client.get(f"/api/research/history/artifacts/{digest}").status_code == 404
        )
