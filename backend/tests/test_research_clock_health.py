from __future__ import annotations

import asyncio
import json
import threading
import time
import uuid
from collections.abc import Awaitable, Callable, Coroutine
from datetime import UTC, datetime
from decimal import Decimal
from functools import wraps
from pathlib import Path
from typing import cast

import pytest
from fastapi.testclient import TestClient

from jusik.research_app import create_research_app
from jusik.research_clock_health import (
    ClockHealthMonitor,
    ClockProbeError,
    parse_timesync_status,
    probe_clock_health,
    run_timesync_status,
)
from jusik.research_config import PAPER_BASE_URL, ResearchSettings
from jusik.research_forward_models import (
    ForwardClockHealth,
    ForwardConfig,
    ForwardSession,
)
from jusik.research_forward_store import ForwardStore
from jusik.research_models import ResearchInputSnapshot, ResearchRunRequest
from jusik.research_store import ResearchStore


def _async_test[**P](
    function: Callable[P, Coroutine[object, object, None]],
) -> Callable[P, None]:
    @wraps(function)
    def run(*args: P.args, **kwargs: P.kwargs) -> None:
        asyncio.run(function(*args, **kwargs))

    return run


class _UnusedProvider:
    async def collect(self, request: ResearchRunRequest) -> ResearchInputSnapshot:
        raise AssertionError(f"unexpected request: {request}")


def _sample(
    *,
    sampled_at: datetime = datetime(2026, 9, 11, tzinfo=UTC),
    packet_count: int = 3032,
) -> ForwardClockHealth:
    return ForwardClockHealth(
        sample_id="00000000-0000-4000-8000-000000000001",
        sampled_at=sampled_at,
        state="available",
        offset_ms="2906.435",
        delay_ms="251.667",
        jitter_ms="45.675",
        packet_count=packet_count,
        synced=None,
        persisted=False,
        error_code=None,
    )


def _store(tmp_path: Path) -> ForwardStore:
    store = ForwardStore(tmp_path / "forward.db")
    store.activate(
        activated_at=datetime(2026, 9, 10, tzinfo=UTC),
        next_due_at=datetime(2026, 9, 14, tzinfo=UTC),
        source_run_id="source",
        config=ForwardConfig(),
    )
    return store


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("+0s", Decimal("0")),
        ("-2.906435s", Decimal("-2906.435")),
        ("251.667ms", Decimal("251.667")),
        ("45us", Decimal("0.045")),
        ("45µs", Decimal("0.045")),
        ("45ns", Decimal("0.000045")),
    ],
)
def test_parser_preserves_signed_exact_units(raw: str, expected: Decimal) -> None:
    offset, delay, jitter, packet_count = parse_timesync_status(
        f"Offset: {raw}\nDelay: 1ms\nJitter: 2ms\nPacket count: 3032\n"
    )
    assert offset == expected
    assert delay == 1
    assert jitter == 2
    assert packet_count == 3032


@pytest.mark.parametrize(
    "output",
    [
        "Delay: 1ms\n",
        "Offset: NaNs\n",
        "Offset: 1minute\n",
        "Offset: 1ms\nDelay: -1ms\n",
        "Offset: 1ms\nPacket count: nope\n",
        "Offset: 1ms\nOffset: 2ms\n",
    ],
)
def test_parser_rejects_missing_bad_or_ambiguous_values(output: str) -> None:
    with pytest.raises(ClockProbeError, match="parse_error"):
        parse_timesync_status(output)


@_async_test
async def test_probe_maps_failures_without_raw_output() -> None:
    async def missing() -> str:
        raise ClockProbeError("command_missing")

    unknown = await probe_clock_health(
        command=missing, now=lambda: datetime(2026, 9, 11, tzinfo=UTC)
    )
    assert unknown.state == "unknown"
    assert unknown.error_code == "command_missing"
    assert unknown.offset_ms is None
    assert unknown.source_measurement_at is None
    assert unknown.persisted is False


class _FakeProcess:
    def __init__(self, stdout: bytes = b"", stderr: bytes = b"") -> None:
        self.stdout = asyncio.StreamReader()
        self.stderr = asyncio.StreamReader()
        self.stdout.feed_data(stdout)
        self.stderr.feed_data(stderr)
        self.returncode: int | None = None
        self.killed = False
        self.reaped = False
        self._finished = asyncio.Event()

    def finish(self, return_code: int = 0) -> None:
        self.returncode = return_code
        self.stdout.feed_eof()
        self.stderr.feed_eof()
        self._finished.set()

    def kill(self) -> None:
        self.killed = True
        self.finish(-9)

    async def wait(self) -> int:
        await self._finished.wait()
        self.reaped = True
        return cast(int, self.returncode)


def _factory(
    process: _FakeProcess,
) -> Callable[..., Awaitable[asyncio.subprocess.Process]]:
    async def create(*_args: object, **_kwargs: object) -> asyncio.subprocess.Process:
        return cast(asyncio.subprocess.Process, process)

    return create


@_async_test
async def test_subprocess_timeout_oversize_and_missing_are_bounded_and_reaped() -> None:
    async def slow_start(
        *_args: object, **_kwargs: object
    ) -> asyncio.subprocess.Process:
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    with pytest.raises(ClockProbeError, match="timeout"):
        await run_timesync_status(timeout_seconds=0.001, _process_factory=slow_start)

    timeout_process = _FakeProcess()
    with pytest.raises(ClockProbeError, match="timeout"):
        await run_timesync_status(
            timeout_seconds=0.001, _process_factory=_factory(timeout_process)
        )
    assert timeout_process.killed and timeout_process.reaped

    oversize_process = _FakeProcess(b"x" * 17)
    with pytest.raises(ClockProbeError, match="output_oversize"):
        await run_timesync_status(
            maximum_output_bytes=16, _process_factory=_factory(oversize_process)
        )
    assert oversize_process.killed and oversize_process.reaped

    aggregate_process = _FakeProcess(b"x" * 9, b"y" * 9)
    with pytest.raises(ClockProbeError, match="output_oversize"):
        await run_timesync_status(
            timeout_seconds=1,
            maximum_output_bytes=16,
            _process_factory=_factory(aggregate_process),
        )
    assert aggregate_process.killed and aggregate_process.reaped

    async def missing(*_args: object, **_kwargs: object) -> asyncio.subprocess.Process:
        raise FileNotFoundError

    with pytest.raises(ClockProbeError, match="command_missing"):
        await run_timesync_status(_process_factory=missing)


@_async_test
async def test_subprocess_cancellation_kills_and_reaps() -> None:
    process = _FakeProcess()
    task = asyncio.create_task(run_timesync_status(_process_factory=_factory(process)))
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert process.killed and process.reaped


@_async_test
async def test_monitor_persists_each_sample_even_with_same_packet_count(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    samples = iter(
        [
            _sample(),
            _sample(sampled_at=datetime(2026, 9, 11, 0, 1, tzinfo=UTC)),
        ]
    )

    async def probe() -> ForwardClockHealth:
        return next(samples).model_copy(update={"sample_id": str(uuid.uuid4())})

    monitor = ClockHealthMonitor(store, probe=probe)
    first = await monitor.run_once()
    second = await monitor.run_once()
    session = store.active_session()
    assert session is not None
    events = [item for item in store.events(session.id) if item.kind == "clock_sample"]
    assert len(events) == 2
    assert first.sample_id != second.sample_id
    assert all(json.loads(item.detail)["persisted"] is True for item in events)
    assert {item.reference_id for item in events} == {first.sample_id, second.sample_id}


@_async_test
async def test_monitor_waits_for_database_thread_when_cancelled(tmp_path: Path) -> None:
    store = _store(tmp_path)
    started = threading.Event()
    release = threading.Event()
    delayed_store = _DelayedStore(store, started, release)

    async def probe() -> ForwardClockHealth:
        return _sample()

    monitor = ClockHealthMonitor(delayed_store, probe=probe)
    task = asyncio.create_task(monitor.run_once())
    assert await asyncio.to_thread(started.wait, 1)
    task.cancel()
    await asyncio.sleep(0)
    assert not task.done()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    session = store.active_session()
    assert session is not None
    assert len([e for e in store.events(session.id) if e.kind == "clock_sample"]) == 1


@_async_test
async def test_monitor_uses_monotonic_interval_despite_wall_clock_reversal(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    monotonic_values = iter([10.0, 11.25])
    sleep_calls: list[float] = []

    async def probe() -> ForwardClockHealth:
        return _sample(sampled_at=datetime(2026, 9, 10, 23, 59, tzinfo=UTC))

    async def sleep(delay: float) -> None:
        sleep_calls.append(delay)
        raise asyncio.CancelledError

    monitor = ClockHealthMonitor(
        store, probe=probe, monotonic=lambda: next(monotonic_values), sleep=sleep
    )
    with pytest.raises(asyncio.CancelledError):
        await monitor._loop()
    assert sleep_calls == [58.75]


class _DelayedStore:
    def __init__(
        self, store: ForwardStore, started: threading.Event, release: threading.Event
    ) -> None:
        self.store = store
        self.started = started
        self.release = release

    def active_session(self) -> ForwardSession | None:
        return self.store.active_session()

    def record_event(
        self,
        session_id: str,
        occurred_at: datetime,
        kind: str,
        detail: str,
        reference_id: str | None,
    ) -> None:
        self.started.set()
        self.release.wait(timeout=1)
        self.store.record_event(session_id, occurred_at, kind, detail, reference_id)


class _FailingStore:
    def __init__(self, store: ForwardStore) -> None:
        self.store = store

    def active_session(self) -> ForwardSession | None:
        return self.store.active_session()

    def record_event(self, *_args: object, **_kwargs: object) -> None:
        raise OSError("private database failure")


@_async_test
async def test_persistence_failure_only_changes_clock_status(tmp_path: Path) -> None:
    async def probe() -> ForwardClockHealth:
        return _sample()

    monitor = ClockHealthMonitor(_FailingStore(_store(tmp_path)), probe=probe)
    result = await monitor.run_once()
    assert result.state == "available"
    assert result.persisted is False
    assert result.error_code == "persistence_failed"


def test_app_can_disable_probe_and_exposes_nullable_clock_status(
    tmp_path: Path,
) -> None:
    calls = 0

    async def probe() -> ForwardClockHealth:
        nonlocal calls
        calls += 1
        return _sample()

    settings = ResearchSettings(
        app_key="key",
        app_secret="secret",
        base_url=PAPER_BASE_URL,
        db_path=tmp_path / "research.db",
    )
    app = create_research_app(
        settings=settings,
        store=ResearchStore(tmp_path / "research.db"),
        provider=_UnusedProvider(),
        forward_db_path=tmp_path / "forward.db",
        universe_db_path=tmp_path / "universe.db",
        external_db_path=tmp_path / "external.db",
        history_dir=tmp_path / "history",
        history_db_path=tmp_path / "history.db",
        action_collection_db_path=tmp_path / "actions.db",
        action_collection_enabled=False,
        run_clock_health_background=False,
        clock_health_probe=probe,
    )
    with TestClient(app) as client:
        response = client.get("/api/research/forward/status")
    assert response.status_code == 200
    assert response.json()["latest_clock_health"] is None
    assert response.json()["worker_interval_seconds"] == 5
    assert calls == 0


def test_app_starts_immediate_probe_and_stops_cleanly(tmp_path: Path) -> None:
    calls = 0

    async def probe() -> ForwardClockHealth:
        nonlocal calls
        calls += 1
        return _sample()

    settings = ResearchSettings(
        app_key="key",
        app_secret="secret",
        base_url=PAPER_BASE_URL,
        db_path=tmp_path / "research.db",
    )
    app = create_research_app(
        settings=settings,
        store=ResearchStore(tmp_path / "research.db"),
        provider=_UnusedProvider(),
        forward_db_path=tmp_path / "forward.db",
        universe_db_path=tmp_path / "universe.db",
        external_db_path=tmp_path / "external.db",
        history_dir=tmp_path / "history",
        history_db_path=tmp_path / "history.db",
        action_collection_db_path=tmp_path / "actions.db",
        action_collection_enabled=False,
        run_clock_health_background=True,
        clock_health_probe=probe,
    )
    with TestClient(app) as client:
        body: dict[str, object] = {}
        for _ in range(100):
            body = client.get("/api/research/forward/status").json()
            if body["latest_clock_health"] is not None:
                break
            time.sleep(0.01)
    latest = cast(dict[str, object], body["latest_clock_health"])
    assert latest["persisted"] is True
    assert latest["packet_count"] == 3032
    assert calls == 1
