import asyncio
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from jusik.operations_models import ProposalDecision, Quote
from jusik.operations_store import OperationsStore
from jusik.research_ai import OpenAiResearchReviewer
from jusik.research_automation import ResearchAutomation, ai_forward_evaluation_window
from jusik.research_config import PAPER_BASE_URL, ResearchSettings
from jusik.research_engine import run_backtest, snapshot_hash
from jusik.research_models import (
    DailyBar,
    ResearchInputSnapshot,
    ResearchRunRequest,
    SymbolSnapshot,
)
from jusik.research_store import ResearchStore

KST = ZoneInfo("Asia/Seoul")


def snapshot(first: date, count: int) -> ResearchInputSnapshot:
    bars = []
    for index in range(count):
        price = Decimal(100 + index)
        bars.append(
            DailyBar(
                date=first + timedelta(days=index),
                open=price,
                high=price,
                low=price,
                close=price,
                volume=100,
                adjusted_open=price,
                adjusted_high=price,
                adjusted_low=price,
                adjusted_close=price,
            )
        )
    return ResearchInputSnapshot(
        captured_at=datetime(2026, 9, 8, tzinfo=UTC),
        requested_start=first,
        requested_end=first + timedelta(days=count - 1),
        symbols=[
            SymbolSnapshot(
                symbol="005930",
                market="KOSPI",
                bars=bars,
                source_url="https://example.com/daily",
            )
        ],
        events=[],
    )


def test_ai_forward_window_excludes_cutoff_and_requires_twenty_later_dates() -> None:
    cutoff = date(2026, 9, 8)
    only_nineteen = snapshot(cutoff - timedelta(days=10), 30)
    twenty = snapshot(cutoff - timedelta(days=10), 31)

    assert (
        ai_forward_evaluation_window(only_nineteen, cutoff, only_nineteen.requested_end)
        is None
    )
    assert ai_forward_evaluation_window(twenty, cutoff, twenty.requested_end) == (
        cutoff + timedelta(days=1),
        cutoff + timedelta(days=20),
    )


def signal_snapshot(
    request: ResearchRunRequest,
    *,
    captured_at: datetime,
    change_last_bar: bool = False,
) -> ResearchInputSnapshot:
    first = request.end_date - timedelta(days=69)
    rows = []
    for index in range(70):
        price = Decimal(100 + index)
        if change_last_bar and index == 69:
            price += 1
        rows.append(
            DailyBar(
                date=first + timedelta(days=index),
                open=price,
                high=price,
                low=price,
                close=price,
                volume=100,
                adjusted_open=price,
                adjusted_high=price,
                adjusted_low=price,
                adjusted_close=price,
            )
        )
    return ResearchInputSnapshot(
        captured_at=captured_at,
        requested_start=request.start_date,
        requested_end=request.end_date,
        symbols=[
            SymbolSnapshot(
                symbol="005930",
                market="KOSPI",
                bars=rows,
                source_url="https://example.com/daily",
            )
        ],
        events=[],
    )


def complete_signal_run(
    store: ResearchStore,
    request: ResearchRunRequest,
    input_snapshot: ResearchInputSnapshot,
) -> str:
    run = store.create(request, snapshot=input_snapshot)
    store.save_snapshot(run.id, input_snapshot, snapshot_hash(input_snapshot))
    store.complete(run.id, run_backtest(request, input_snapshot))
    return run.id


def signal_quote() -> Quote:
    now = datetime.now(UTC)
    return Quote(
        symbol="005930",
        price="200",
        ask="200",
        bid="200",
        volume=1,
        accumulated_volume=1,
        market_at=now,
        received_at=now,
    )


def signal_automation(
    path: Path,
) -> tuple[ResearchStore, OperationsStore, ResearchAutomation, httpx.AsyncClient]:
    research_store = ResearchStore(path)
    operations_store = OperationsStore(path)
    operations_store.activate_paper("trend_20_v1")
    client = httpx.AsyncClient()
    reviewer = OpenAiResearchReviewer(
        ResearchSettings(
            app_key="key",
            app_secret="secret",
            base_url=PAPER_BASE_URL,
        ),
        client,
    )
    return (
        research_store,
        operations_store,
        ResearchAutomation(research_store, operations_store, reviewer),
        client,
    )


def test_same_signal_bars_from_new_capture_and_run_preserve_claim(
    tmp_path: Path,
) -> None:
    research_store, operations_store, automation, client = signal_automation(
        tmp_path / "research.db"
    )
    today = datetime.now(UTC).astimezone(KST).date()
    request = ResearchRunRequest(
        symbols=["005930"],
        start_date=today - timedelta(days=10),
        end_date=today - timedelta(days=1),
    )
    first_snapshot = signal_snapshot(
        request, captured_at=datetime.now(UTC) - timedelta(minutes=1)
    )
    first_run = complete_signal_run(research_store, request, first_snapshot)
    automation.on_quote(signal_quote())
    first = operations_store.proposals()[0]
    assert first.source_run_id == first_run
    assert first.status == "pending"

    second_snapshot = signal_snapshot(request, captured_at=datetime.now(UTC))
    second_run = complete_signal_run(research_store, request, second_snapshot)
    refreshed = ResearchAutomation(
        research_store, operations_store, automation.reviewer
    )
    refreshed.on_quote(signal_quote())

    assert second_run != first_run
    assert refreshed.proposal_is_current(first) is True
    assert [(item.id, item.status) for item in operations_store.proposals()] == [
        (first.id, "pending")
    ]

    operations_store.decide(
        first.id,
        ProposalDecision(action="reject", expected_version="trend_20_v1"),
        None,
    )
    third_snapshot = signal_snapshot(
        request, captured_at=datetime.now(UTC) + timedelta(seconds=1)
    )
    complete_signal_run(research_store, request, third_snapshot)
    ResearchAutomation(research_store, operations_store, automation.reviewer).on_quote(
        signal_quote()
    )
    proposals = operations_store.proposals()
    assert len(proposals) == 1
    assert proposals[0].status == "rejected"
    asyncio.run(client.aclose())


def test_changed_signal_bar_expires_old_pending_and_creates_new_claim(
    tmp_path: Path,
) -> None:
    research_store, operations_store, automation, client = signal_automation(
        tmp_path / "research.db"
    )
    today = datetime.now(UTC).astimezone(KST).date()
    request = ResearchRunRequest(
        symbols=["005930"],
        start_date=today - timedelta(days=10),
        end_date=today - timedelta(days=1),
    )
    complete_signal_run(
        research_store,
        request,
        signal_snapshot(request, captured_at=datetime.now(UTC)),
    )
    automation.on_quote(signal_quote())
    first = operations_store.proposals()[0]

    complete_signal_run(
        research_store,
        request,
        signal_snapshot(
            request,
            captured_at=datetime.now(UTC) + timedelta(seconds=1),
            change_last_bar=True,
        ),
    )
    refreshed = ResearchAutomation(
        research_store, operations_store, automation.reviewer
    )
    assert refreshed.proposal_is_current(first) is False
    refreshed.on_quote(signal_quote())
    proposals = operations_store.proposals()

    assert len(proposals) == 2
    assert {item.status for item in proposals} == {"expired", "pending"}
    assert len({item.signal_input_hash for item in proposals}) == 2
    asyncio.run(client.aclose())
