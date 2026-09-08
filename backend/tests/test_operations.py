from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from jusik.operations_models import (
    ProposalDecision,
    Quote,
    ResearchScheduleUpdate,
    SignalProposalCreate,
    StrategyDefinition,
    UniverseUpdate,
)
from jusik.operations_store import FEE_RATE, OperationsStore

KST = ZoneInfo("Asia/Seoul")


def quote(symbol: str, price: str, now: datetime) -> Quote:
    return Quote(
        symbol=symbol,
        price=price,
        ask=price,
        bid=price,
        volume=10,
        accumulated_volume=100,
        market_at=now,
        received_at=now,
    )


def proposal(
    now: datetime,
    *,
    expires: int = 300,
    signal_input_hash: str = "snapshot-a",
) -> SignalProposalCreate:
    return SignalProposalCreate(
        symbol="035420",
        side="buy",
        quantity=10,
        limit_price="1000",
        expires_in_seconds=expires,
        strategy_version="trend_20_v1",
        signal_date=now.astimezone(KST).date() - timedelta(days=1),
        source_run_id=f"run-{signal_input_hash}",
        signal_input_hash=signal_input_hash,
        reason="확정 일봉 조건 충족",
    )


def test_universe_and_schedule_survive_restart(tmp_path: Path) -> None:
    path = tmp_path / "operations.db"
    store = OperationsStore(path)
    assert store.update_universe(UniverseUpdate(symbols=["035420"])) == ["035420"]
    schedule = store.update_schedule(
        ResearchScheduleUpdate(enabled=True, interval_hours=6, lookback_days=365)
    )

    reopened = OperationsStore(path)
    assert reopened.universe() == ["035420"]
    assert reopened.schedule() == schedule


def test_duplicate_and_concurrent_approval_make_one_idempotent_fill(
    tmp_path: Path,
) -> None:
    store = OperationsStore(tmp_path / "operations.db")
    store.activate_paper("trend_20_v1")
    now = datetime.now(UTC)
    created = store.create_proposal(proposal(now))
    assert store.create_proposal(proposal(now)).id == created.id
    decision = ProposalDecision(
        action="approve", expected_version="trend_20_v1", execution_mode="paper"
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                lambda _: store.decide(
                    created.id, decision, quote("035420", "900", now)
                ),
                range(2),
            )
        )

    assert results[0][1] is not None
    assert results[0][1] == results[1][1]
    account = store.paper_account()
    assert len(account.fills) == 1
    assert account.positions == {"035420": 10}
    assert account.cash == Decimal("100000000") - Decimal("9000") * (
        Decimal(1) + FEE_RATE
    )


def test_expired_rejected_stale_and_price_bound_never_fill(tmp_path: Path) -> None:
    store = OperationsStore(tmp_path / "operations.db")
    store.activate_paper("trend_20_v1")
    now = datetime.now(UTC)
    expired = store.create_proposal(proposal(now))
    with pytest.raises(ValueError, match="expired"):
        store.decide(
            expired.id,
            ProposalDecision(action="approve", expected_version="trend_20_v1"),
            quote("035420", "900", now),
            now=now + timedelta(hours=1),
        )
    assert store.get_proposal(expired.id).status == "expired"

    rejected = store.create_proposal(proposal(now, signal_input_hash="snapshot-b"))
    result, fill = store.decide(
        rejected.id,
        ProposalDecision(action="reject", expected_version="trend_20_v1"),
        None,
        now=now,
    )
    assert result.status == "rejected" and fill is None

    stale = store.create_proposal(proposal(now, signal_input_hash="snapshot-c"))
    with pytest.raises(ValueError, match="stale"):
        store.decide(
            stale.id,
            ProposalDecision(action="approve", expected_version="trend_20_v1"),
            quote("035420", "900", now - timedelta(minutes=1)),
            now=now,
        )
    with pytest.raises(ValueError, match="price bound"):
        store.decide(
            stale.id,
            ProposalDecision(action="approve", expected_version="trend_20_v1"),
            quote("035420", "1100", now),
            now=now,
        )
    assert store.paper_account().fills == []


def test_sell_requires_position_and_applies_fee_and_tax(tmp_path: Path) -> None:
    store = OperationsStore(tmp_path / "operations.db")
    store.activate_paper("trend_20_v1")
    now = datetime.now(UTC)
    buy = store.create_proposal(proposal(now))
    store.decide(
        buy.id,
        ProposalDecision(action="approve", expected_version="trend_20_v1"),
        quote("035420", "900", now),
        now=now,
    )
    sell = store.create_proposal(
        SignalProposalCreate(
            symbol="035420",
            side="sell",
            quantity=10,
            limit_price="800",
            strategy_version="trend_20_v1",
            signal_date=now.astimezone(KST).date() - timedelta(days=1),
            reason="확정 일봉 보유 조건 해제",
        )
    )
    _, fill = store.decide(
        sell.id,
        ProposalDecision(action="approve", expected_version="trend_20_v1"),
        quote("035420", "900", now),
        now=now,
    )
    assert fill is not None
    assert fill.tax == Decimal("9000") * Decimal("0.0018")
    assert store.paper_account().positions == {}


def test_invalid_symbols_and_nonfinite_financial_values_are_rejected() -> None:
    with pytest.raises(ValueError):
        UniverseUpdate(symbols=["035420", "035420"])
    with pytest.raises(ValueError):
        SignalProposalCreate(
            symbol="035420",
            side="buy",
            quantity=1,
            limit_price=Decimal("NaN"),
            strategy_version="trend_20_v1",
            signal_date=date.today(),
            reason="invalid",
        )
    with pytest.raises(ValueError):
        Quote(
            symbol="035420",
            price="100",
            volume=1,
            accumulated_volume=1,
            market_at=datetime.now(),
            received_at=datetime.now(UTC),
        )


def test_rejected_or_expired_signal_is_not_reoffered_until_input_changes(
    tmp_path: Path,
) -> None:
    store = OperationsStore(tmp_path / "operations.db")
    store.activate_paper("trend_20_v1")
    now = datetime.now(UTC)
    unchanged = proposal(now, signal_input_hash="unchanged")
    created = store.create_proposal(unchanged)
    rejected, _ = store.decide(
        created.id,
        ProposalDecision(action="reject", expected_version="trend_20_v1"),
        None,
        now=now,
    )

    repeated = store.create_proposal(unchanged)
    changed = store.create_proposal(proposal(now, signal_input_hash="new-snapshot"))

    assert repeated.id == rejected.id
    assert repeated.status == "rejected"
    assert changed.id != rejected.id
    assert changed.status == "pending"


def test_reversed_signal_expires_pending_proposal_and_blocks_approval(
    tmp_path: Path,
) -> None:
    store = OperationsStore(tmp_path / "operations.db")
    store.activate_paper("trend_20_v1")
    now = datetime.now(UTC)
    created = store.create_proposal(proposal(now, signal_input_hash="old-input"))

    count = store.expire_incompatible_proposals(
        symbol="035420",
        strategy_version="trend_20_v1",
        valid_side=None,
        signal_date=created.signal_date + timedelta(days=1),
        signal_input_hash="new-input",
    )

    assert count == 1
    assert store.get_proposal(created.id).status == "expired"
    with pytest.raises(ValueError, match="expired"):
        store.decide(
            created.id,
            ProposalDecision(action="approve", expected_version="trend_20_v1"),
            quote("035420", "900", now),
            now=now,
        )


def test_ai_strategy_requires_completed_passing_later_period_evaluation(
    tmp_path: Path,
) -> None:
    store = OperationsStore(tmp_path / "operations.db")
    definitions = [
        StrategyDefinition(
            version=f"ai_trend_{status}",
            name="AI 제안 · 미검증",
            fast_window=fast,
            slow_window=45,
            definition="제한된 추세 후보",
        )
        for status, fast in (("pending", 13), ("failed", 14), ("passed", 15))
    ]
    for definition in definitions:
        store.save_ai_suggestion(
            definition,
            "후속 관측 대기",
            proposed_after_date=date(2026, 9, 8),
            provenance={
                "source_run_id": "source-run",
                "created_on_kst": "2026-09-08",
            },
        )
    with pytest.raises(ValueError, match="passing later-period"):
        store.activate_paper(definitions[0].version)

    validation = {
        "run_id": "later-run",
        "return_pct": Decimal("1"),
        "drawdown_pct": Decimal("2"),
        "reason": "후속 기간 평가",
        "evaluation_start": date(2026, 9, 9),
        "evaluation_end": date(2026, 10, 9),
        "input_hash": "later-input",
        "implementation_hash": "engine-code",
    }
    with pytest.raises(ValueError, match="after its immutable proposal cutoff"):
        store.record_version_validation(
            **{
                **validation,
                "evaluation_start": date(2026, 9, 8),
            },
            version=definitions[0].version,
            passed=True,
        )
    store.record_version_validation(
        **validation, version=definitions[1].version, passed=False
    )
    with pytest.raises(ValueError, match="passing later-period"):
        store.activate_paper(definitions[1].version)

    store.record_version_validation(
        **validation, version=definitions[2].version, passed=True
    )
    active = store.activate_paper(definitions[2].version)
    assert active.active_for_paper is True
    assert active.evaluation_start == date(2026, 9, 9)
    assert active.provenance["source_run_id"] == "source-run"


def test_ai_budget_reservation_is_atomic_and_failed_calls_keep_reservation(
    tmp_path: Path,
) -> None:
    store = OperationsStore(tmp_path / "operations.db")
    request = {"model": "test-model", "input": "public summary"}
    first = store.reserve_ai_run(
        model="test-model",
        prompt_version="v1",
        request=request,
        daily_budget=300,
        conservative_input_tokens=100,
        desired_output_tokens=500,
    )
    assert first is not None
    assert first.max_output_tokens == 200
    assert first.reserved_tokens == 300
    assert (
        store.reserve_ai_run(
            model="test-model",
            prompt_version="v1",
            request=request,
            daily_budget=300,
            conservative_input_tokens=1,
        )
        is None
    )

    store.complete_ai_run(
        first.id,
        input_tokens=0,
        output_tokens=0,
        analysis=None,
        error="validated failure",
    )
    status = store.ai_status(
        enabled=True,
        configured=True,
        model="test-model",
        daily_token_budget=300,
        prompt_version="v1",
    )
    assert status.used_tokens_today == 300
    assert status.last_error == "validated failure"


def test_successful_ai_call_reconciles_reservation_to_reported_usage(
    tmp_path: Path,
) -> None:
    store = OperationsStore(tmp_path / "operations.db")
    reservation = store.reserve_ai_run(
        model="test-model",
        prompt_version="v1",
        request={"input": "public summary"},
        daily_budget=300,
        conservative_input_tokens=100,
    )
    assert reservation is not None
    store.complete_ai_run(
        reservation.id,
        input_tokens=40,
        output_tokens=10,
        analysis="validated",
        error=None,
    )

    status = store.ai_status(
        enabled=True,
        configured=True,
        model="test-model",
        daily_token_budget=300,
        prompt_version="v1",
    )
    second = store.reserve_ai_run(
        model="test-model",
        prompt_version="v1",
        request={"input": "next public summary"},
        daily_budget=300,
        conservative_input_tokens=100,
    )

    assert status.used_tokens_today == 50
    assert second is not None
    assert second.max_output_tokens == 150
