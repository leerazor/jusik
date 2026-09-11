from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from jusik.research_corporate_actions import register_verified_manifest
from jusik.research_forward_models import ForwardConfig, ForwardIntent
from jusik.research_forward_store import ForwardStore
from jusik.research_quote_models import ResearchQuote

EFFECTIVE_AT = datetime(2024, 6, 10, 13, 30, tzinfo=UTC)
SEC_SOURCE = (
    "https://www.sec.gov/Archives/edgar/data/1045810/"
    "000104581024000144/nvda-20240607.htm"
)


def _quote(at: datetime, price: str) -> ResearchQuote:
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


def _manifest(path: Path, **updates: object) -> Path:
    event: dict[str, object] = {
        "symbol": "NVDA",
        "exchange": "NAS",
        "numerator": 10,
        "denominator": 1,
        "source_url": SEC_SOURCE,
        "evidence_id": "sec-nvda-2024-10-for-1",
        "evidence_sha256": "a" * 64,
        "operator_verified": True,
        "observed_at": "2024-06-05T12:00:00Z",
        "effective_at": "2024-06-10T13:30:00Z",
    }
    event.update(updates)
    path.write_text(
        json.dumps({"schema_version": 1, "events": [event]}), encoding="utf-8"
    )
    return path


def _manifest_event(**updates: object) -> dict[str, object]:
    event: dict[str, object] = {
        "symbol": "NVDA",
        "exchange": "NAS",
        "numerator": 10,
        "denominator": 1,
        "source_url": SEC_SOURCE,
        "evidence_id": "sec-nvda-2024-10-for-1",
        "evidence_sha256": "a" * 64,
        "operator_verified": True,
        "observed_at": "2024-06-05T12:00:00Z",
        "effective_at": "2024-06-10T13:30:00Z",
    }
    event.update(updates)
    return event


def _multi_manifest(path: Path, events: list[dict[str, object]]) -> Path:
    path.write_text(
        json.dumps({"schema_version": 1, "events": events}), encoding="utf-8"
    )
    return path


def _session_with_nvda(store: ForwardStore) -> tuple[str, Decimal]:
    activated = datetime(2024, 6, 3, 13, 30, tzinfo=UTC)
    session = store.activate(
        activated_at=activated,
        next_due_at=activated,
        source_run_id="synthetic-accounting-replay",
        config=ForwardConfig(),
    )
    intent = ForwardIntent(
        symbol="NVDA",
        side="buy",
        target_weight=Decimal("0.2"),
        budget_krw=Decimal("20000000"),
        state="pending",
        reason="synthetic accounting fixture",
    )
    decision = store.record_decision(
        session_id=session.id,
        due_at=activated,
        recorded_at=activated,
        input_version="a" * 64,
        reason="synthetic accounting fixture",
        expires_at=EFFECTIVE_AT,
        target_weights={"NVDA": Decimal("0.2")},
        intents=[intent],
    )
    fill = store.apply_fill(
        decision=decision,
        intent=intent,
        quote=_quote(activated + timedelta(minutes=1), "1000"),
        quote_id="synthetic-pre-split-quote",
        fx_rate=Decimal("1300"),
        quantity=7,
        local_fill_price=Decimal("1000"),
        transaction_cost_krw=Decimal(),
        fx_cost_krw=Decimal(),
    )
    assert fill is not None
    return session.id, fill.cash_after_krw


def test_verified_nvda_split_applies_once_and_replays_by_effective_time(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "forward.db"
    store = ForwardStore(db_path)
    session_id, cash_before = _session_with_nvda(store)
    registered = register_verified_manifest(
        db_path=db_path,
        session_id=session_id,
        manifest_path=_manifest(tmp_path / "manifest.json"),
        clock=lambda: datetime(2024, 6, 6, 12, tzinfo=UTC),
    )
    assert registered[0].state == "registered"

    assert store.ledger_asof(session_id, EFFECTIVE_AT - timedelta(seconds=1)) == (
        cash_before,
        {"NVDA": 7},
    )
    applied = store.apply_due_corporate_actions(session_id, EFFECTIVE_AT)
    assert applied[0].state == "applied"
    assert applied[0].before_quantity == 7
    assert applied[0].after_quantity == 70
    position = store.positions(session_id)[0]
    assert position.quantity == 70
    assert position.average_cost_krw == Decimal("130000")
    assert position.average_cost_krw * position.quantity == Decimal("9100000")
    assert store.active_session() is not None
    assert store.active_session().cash_krw == cash_before  # type: ignore[union-attr]
    assert store.ledger_asof(session_id, EFFECTIVE_AT) == (
        cash_before,
        {"NVDA": 70},
    )

    reopened = ForwardStore(db_path)
    duplicate = reopened.apply_due_corporate_actions(
        session_id, EFFECTIVE_AT + timedelta(minutes=1)
    )
    assert duplicate[0].state == "applied"
    assert reopened.positions(session_id)[0].quantity == 70


def test_split_registration_rejects_late_invalid_conflicting_and_wrong_exchange(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "forward.db"
    store = ForwardStore(db_path)
    session_id, _cash = _session_with_nvda(store)
    manifest_path = _manifest(tmp_path / "manifest.json")

    with pytest.raises(ValueError, match="timely"):
        register_verified_manifest(
            db_path=db_path,
            session_id=session_id,
            manifest_path=manifest_path,
            clock=lambda: EFFECTIVE_AT + timedelta(seconds=1),
        )
    for name, update in [
        ("reverse", {"numerator": 1, "denominator": 10}),
        ("fractional", {"numerator": 3, "denominator": 2}),
        ("noop", {"numerator": 1, "denominator": 1}),
        ("exchange", {"exchange": "NYQ"}),
    ]:
        with pytest.raises(ValueError):
            register_verified_manifest(
                db_path=db_path,
                session_id=session_id,
                manifest_path=_manifest(tmp_path / f"{name}.json", **update),
                clock=lambda: datetime(2024, 6, 6, 12, tzinfo=UTC),
            )

    register_verified_manifest(
        db_path=db_path,
        session_id=session_id,
        manifest_path=manifest_path,
        clock=lambda: datetime(2024, 6, 6, 12, tzinfo=UTC),
    )
    with pytest.raises(ValueError, match="conflicts"):
        register_verified_manifest(
            db_path=db_path,
            session_id=session_id,
            manifest_path=_manifest(
                tmp_path / "conflict.json", evidence_sha256="b" * 64
            ),
            clock=lambda: datetime(2024, 6, 6, 13, tzinfo=UTC),
        )


def test_zero_holding_split_is_processed_and_stale_quote_cannot_fill(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "forward.db"
    store = ForwardStore(db_path)
    activated = datetime(2024, 6, 3, 13, 30, tzinfo=UTC)
    session = store.activate(
        activated_at=activated,
        next_due_at=activated,
        source_run_id="synthetic-zero-holding-replay",
        config=ForwardConfig(),
    )
    register_verified_manifest(
        db_path=db_path,
        session_id=session.id,
        manifest_path=_manifest(tmp_path / "manifest.json"),
        clock=lambda: datetime(2024, 6, 6, 12, tzinfo=UTC),
    )
    action = store.apply_due_corporate_actions(session.id, EFFECTIVE_AT)[0]
    assert (action.before_quantity, action.after_quantity) == (0, 0)
    assert store.ledger_asof(session.id, EFFECTIVE_AT) == (
        session.config.initial_cash_krw,
        {"NVDA": 0},
    )

    intent = ForwardIntent(
        symbol="NVDA",
        side="buy",
        target_weight=Decimal("0.2"),
        budget_krw=Decimal("20000000"),
        state="pending",
        reason="synthetic stale quote fixture",
    )
    decision = store.record_decision(
        session_id=session.id,
        due_at=EFFECTIVE_AT + timedelta(minutes=1),
        recorded_at=EFFECTIVE_AT + timedelta(minutes=1),
        input_version="b" * 64,
        reason="synthetic stale quote fixture",
        expires_at=EFFECTIVE_AT + timedelta(days=1),
        target_weights={"NVDA": Decimal("0.2")},
        intents=[intent],
    )
    stale = _quote(EFFECTIVE_AT - timedelta(seconds=1), "100")
    assert (
        store.apply_fill(
            decision=decision,
            intent=intent,
            quote=stale.model_copy(
                update={"received_at": EFFECTIVE_AT + timedelta(minutes=2)}
            ),
            quote_id="synthetic-stale-quote",
            fx_rate=Decimal("1300"),
            quantity=1,
            local_fill_price=Decimal("100"),
            transaction_cost_krw=Decimal(),
            fx_cost_krw=Decimal(),
        )
        is None
    )
    fresh = _quote(EFFECTIVE_AT + timedelta(minutes=2), "100")
    assert (
        store.apply_fill(
            decision=decision,
            intent=intent,
            quote=fresh,
            quote_id="synthetic-fresh-quote",
            fx_rate=Decimal("1300"),
            quantity=1,
            local_fill_price=Decimal("100"),
            transaction_cost_krw=Decimal(),
            fx_cost_krw=Decimal(),
        )
        is not None
    )


def test_due_split_blocks_without_mutating_after_later_checkpoint(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "forward.db"
    store = ForwardStore(db_path)
    session_id, _cash = _session_with_nvda(store)
    checkpoint_at = EFFECTIVE_AT + timedelta(hours=7)
    assert store.record_checkpoint(
        session_id,
        checkpoint_at,
        checkpoint_at + timedelta(minutes=1),
        Decimal("100000000"),
        Decimal("90900000"),
        {"NVDA": Decimal("9100000")},
        update_episode=False,
    )
    register_verified_manifest(
        db_path=db_path,
        session_id=session_id,
        manifest_path=_manifest(tmp_path / "manifest.json"),
        clock=lambda: datetime(2024, 6, 6, 12, tzinfo=UTC),
    )

    action = store.apply_due_corporate_actions(session_id, checkpoint_at)[0]
    assert action.state == "blocked"
    assert action.blocked_reason == "checkpoint_at_or_after_effective_at"
    position = store.positions(session_id)[0]
    assert position.quantity == 7
    assert position.average_cost_krw == Decimal("1300000")


def test_repeating_average_cost_preserves_basis_below_one_cent(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "forward.db"
    store = ForwardStore(db_path)
    session_id, _cash = _session_with_nvda(store)
    register_verified_manifest(
        db_path=db_path,
        session_id=session_id,
        manifest_path=_manifest(
            tmp_path / "manifest.json", numerator=3, evidence_id="synthetic-3-for-1"
        ),
        clock=lambda: datetime(2024, 6, 6, 12, tzinfo=UTC),
    )
    store.apply_due_corporate_actions(session_id, EFFECTIVE_AT)
    position = store.positions(session_id)[0]
    assert position.quantity == 21
    basis_drift = abs(
        position.average_cost_krw * position.quantity - Decimal("9100000")
    )
    assert basis_drift < Decimal("0.01")


def test_manifest_registration_is_atomic_for_validation_and_database_conflicts(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "forward.db"
    store = ForwardStore(db_path)
    session_id, _cash = _session_with_nvda(store)
    registered_at = datetime(2024, 6, 6, 12, tzinfo=UTC)

    invalid_manifest = _multi_manifest(
        tmp_path / "invalid.json",
        [
            _manifest_event(),
            _manifest_event(
                symbol="MSFT",
                exchange="NYS",
                evidence_id="invalid-msft-exchange",
            ),
        ],
    )
    with pytest.raises(ValueError, match="symbol_exchange"):
        register_verified_manifest(
            db_path=db_path,
            session_id=session_id,
            manifest_path=invalid_manifest,
            clock=lambda: registered_at,
        )
    assert store.corporate_actions(session_id) == []
    assert not any(
        event.kind == "corporate_action_registered"
        for event in store.events(session_id)
    )

    register_verified_manifest(
        db_path=db_path,
        session_id=session_id,
        manifest_path=_manifest(tmp_path / "existing.json"),
        clock=lambda: registered_at,
    )
    before_actions = store.corporate_actions(session_id)
    before_audits = [
        event
        for event in store.events(session_id)
        if event.kind == "corporate_action_registered"
    ]
    conflict_manifest = _multi_manifest(
        tmp_path / "conflict-batch.json",
        [
            _manifest_event(
                symbol="MSFT",
                evidence_id="msft-new-event",
                evidence_sha256="c" * 64,
            ),
            _manifest_event(evidence_sha256="b" * 64),
        ],
    )
    with pytest.raises(ValueError, match="conflicts"):
        register_verified_manifest(
            db_path=db_path,
            session_id=session_id,
            manifest_path=conflict_manifest,
            clock=lambda: registered_at,
        )
    assert store.corporate_actions(session_id) == before_actions
    assert [
        event
        for event in store.events(session_id)
        if event.kind == "corporate_action_registered"
    ] == before_audits


def test_unapplied_split_blocks_later_split_for_same_symbol(tmp_path: Path) -> None:
    db_path = tmp_path / "forward.db"
    store = ForwardStore(db_path)
    session_id, cash = _session_with_nvda(store)
    checkpoint_at = datetime(2024, 6, 11, 20, tzinfo=UTC)
    assert store.record_checkpoint(
        session_id,
        checkpoint_at,
        checkpoint_at + timedelta(minutes=1),
        Decimal("100000000"),
        cash,
        {"NVDA": Decimal("9100000")},
        update_episode=False,
    )
    register_verified_manifest(
        db_path=db_path,
        session_id=session_id,
        manifest_path=_multi_manifest(
            tmp_path / "two-splits.json",
            [
                _manifest_event(),
                _manifest_event(
                    numerator=2,
                    evidence_id="synthetic-later-2-for-1",
                    evidence_sha256="d" * 64,
                    effective_at="2024-06-20T13:30:00Z",
                ),
            ],
        ),
        clock=lambda: datetime(2024, 6, 6, 12, tzinfo=UTC),
    )

    actions = store.apply_due_corporate_actions(
        session_id, datetime(2024, 6, 20, 13, 30, tzinfo=UTC)
    )
    assert [action.blocked_reason for action in actions] == [
        "checkpoint_at_or_after_effective_at",
        "prior_split_unapplied",
    ]
    position = store.positions(session_id)[0]
    assert position.quantity == 7
    assert position.average_cost_krw == Decimal("1300000")
    assert store.active_session() is not None
    assert store.active_session().cash_krw == cash  # type: ignore[union-attr]
