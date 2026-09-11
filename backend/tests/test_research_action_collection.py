import asyncio
import fcntl
import hashlib
import json
import sqlite3
import threading
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from jusik.research_action_collection import (
    MAX_BODY_BYTES,
    ActionCollector,
    CollectionError,
    parse_action_response,
)
from jusik.research_action_collection_models import (
    CollectedAction,
    CollectedActionPayload,
)
from jusik.research_action_collection_store import ActionCollectionStore
from jusik.research_app import create_research_app
from jusik.research_config import PAPER_BASE_URL, ResearchSettings
from jusik.research_models import ResearchInputSnapshot, ResearchRunRequest
from jusik.research_universe_data import REGISTRY
from jusik.research_universe_models import ResearchInstrument

NVDA = next(item for item in REGISTRY if item.symbol == "NVDA")
NOW = datetime(2026, 9, 10, 1, tzinfo=UTC)
START = date(2023, 9, 11)
END = date(2026, 9, 10)


def chart_body(
    *,
    instrument: ResearchInstrument = NVDA,
    events: object | None = None,
    timezone: str | None = None,
) -> bytes:
    result: dict[str, object] = {
        "meta": {
            "symbol": instrument.yahoo_symbol,
            "exchangeName": instrument.exchange,
            "exchangeTimezoneName": timezone or instrument.timezone,
            "currency": instrument.currency,
        }
    }
    if events is not None:
        result["events"] = events
    return json.dumps({"chart": {"result": [result], "error": None}}).encode()


def split(numerator: int = 10) -> CollectedAction:
    return CollectedAction(
        provider_key="1718026200",
        kind="split",
        payload=CollectedActionPayload(
            vendor_date=date(2024, 6, 10),
            numerator=numerator,
            denominator=1,
        ),
    )


def complete(
    store: ActionCollectionStore,
    observed_at: datetime,
    actions: list[CollectedAction],
    *,
    start: date = START,
    end: date = END,
) -> str:
    attempt = store.begin_attempt("NVDA", start, end, observed_at)
    body = chart_body(events={})
    store.complete_success(
        attempt_id=attempt,
        completed_at=observed_at,
        http_status=200,
        request_url="https://query1.finance.yahoo.com/v8/finance/chart/NVDA",
        body=body,
        actions=actions,
    )
    return attempt


def test_parser_validates_metadata_values_and_range() -> None:
    included = int(datetime(2024, 6, 10, 13, 30, tzinfo=UTC).timestamp())
    excluded = int(datetime(2023, 1, 1, tzinfo=UTC).timestamp())
    body = chart_body(
        events={
            "splits": {
                "one": {"date": included, "numerator": 10.0, "denominator": 1.0},
                "old": {"date": excluded, "numerator": 2, "denominator": 1},
            },
            "dividends": {"div": {"date": included, "amount": 0.01}},
        }
    )

    actions = parse_action_response(body, NVDA, START, END)

    assert [(item.kind, item.provider_key) for item in actions] == [
        ("dividend", "div"),
        ("split", "one"),
    ]
    assert actions[0].payload.amount == "0.01"
    assert parse_action_response(chart_body(), NVDA, START, END) == []
    assert parse_action_response(chart_body(events={}), NVDA, START, END) == []

    invalid = [
        chart_body(timezone="UTC"),
        chart_body(events={"dividends": {"x": {"date": included, "amount": 0}}}),
        chart_body(events={"dividends": {"x": {"date": included, "amount": -1}}}),
        chart_body(
            events={
                "splits": {"x": {"date": included, "numerator": 1.5, "denominator": 1}}
            }
        ),
        b'{"chart":{"result":[],"result":[]}}',
    ]
    for raw in invalid:
        with pytest.raises(CollectionError):
            parse_action_response(raw, NVDA, START, END)

    deeply_nested = b"[" * 10_000 + b"0" + b"]" * 10_000
    with pytest.raises(CollectionError, match="response_json_invalid"):
        parse_action_response(deeply_nested, NVDA, START, END)


def test_decimal_literals_keep_revision_precision_and_reject_expansion(
    tmp_path: Path,
) -> None:
    event_date = int(datetime(2024, 6, 10, 13, 30, tzinfo=UTC).timestamp())

    def response(amount: str) -> bytes:
        body = chart_body(
            events={"dividends": {"div": {"date": event_date, "amount": "__AMOUNT__"}}}
        )
        return body.replace(b'"__AMOUNT__"', amount.encode())

    store = ActionCollectionStore(tmp_path / "actions.db")
    store.ensure_sources(REGISTRY, NOW)
    first = parse_action_response(response("0.123456789012345678901"), NVDA, START, END)
    second = parse_action_response(
        response("0.123456789012345678902"), NVDA, START, END
    )
    assert first[0].payload.amount == "0.123456789012345678901"
    assert second[0].payload.amount == "0.123456789012345678902"
    complete(store, NOW, first)
    complete(store, NOW + timedelta(hours=25), second)
    assert [item.sequence for item in store.revision_page(None, 50).items] == [2, 1]

    with pytest.raises(CollectionError, match="dividend_amount_invalid"):
        parse_action_response(response('"1e100000"'), NVDA, START, END)


def test_store_tracks_identical_revision_reversion_and_missing(tmp_path: Path) -> None:
    store = ActionCollectionStore(tmp_path / "actions.db")
    store.ensure_sources(REGISTRY, NOW)

    first_attempt = complete(store, NOW, [split(10)])
    complete(store, NOW + timedelta(hours=25), [split(10)])
    complete(store, NOW + timedelta(hours=50), [split(20)])
    complete(store, NOW + timedelta(hours=75), [split(10)])

    event = store.event_page(None, 50).items[0]
    revisions = list(reversed(store.revision_page(None, 50).items))
    assert event.first_seen_at == NOW
    assert event.last_seen_at == NOW + timedelta(hours=75)
    assert event.latest_revision_sequence == 3
    assert [item.sequence for item in revisions] == [1, 2, 3]
    assert revisions[0].attempt_id == first_attempt
    assert all(item.symbol == "NVDA" and item.kind == "split" for item in revisions)

    complete(store, NOW + timedelta(hours=100), [])
    assert store.event_page(None, 50).items[0].observation_state == (
        "not_seen_in_latest_response"
    )
    complete(
        store,
        NOW + timedelta(hours=125),
        [],
        start=date(2025, 1, 1),
        end=END,
    )
    assert store.event_page(None, 50).items[0].observation_state == (
        "not_seen_in_latest_response"
    )


def test_success_is_atomic_and_raw_hash_is_verified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ActionCollectionStore(tmp_path / "actions.db")
    store.ensure_sources(REGISTRY, NOW)
    attempt = store.begin_attempt("NVDA", START, END, NOW)
    original = store._store_action
    calls = 0

    def fail_second(*args: object, **kwargs: object) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("synthetic rollback")
        original(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(store, "_store_action", fail_second)
    second = split().model_copy(update={"provider_key": "second"})
    with pytest.raises(RuntimeError, match="synthetic rollback"):
        store.complete_success(
            attempt_id=attempt,
            completed_at=NOW,
            http_status=200,
            request_url="https://query1.finance.yahoo.com/test",
            body=b"raw",
            actions=[split(), second],
        )
    assert store.event_page(None, 50).items == []
    with sqlite3.connect(store.path) as connection:
        row = connection.execute(
            "SELECT state, body FROM action_collection_attempts WHERE id=?", (attempt,)
        ).fetchone()
    assert row == ("pending", None)

    monkeypatch.setattr(store, "_store_action", original)
    attempt = complete(store, NOW + timedelta(hours=1), [split()])
    raw = store.raw_attempt(attempt)
    assert hashlib.sha256(raw.body).hexdigest() == raw.body_sha256
    with sqlite3.connect(store.path) as connection:
        connection.execute(
            "UPDATE action_collection_attempts SET body=? WHERE id=?",
            (b"changed", attempt),
        )
    with pytest.raises(ValueError, match="hash mismatch"):
        store.raw_attempt(attempt)


def test_failure_keeps_last_success_and_marks_raw_availability(tmp_path: Path) -> None:
    store = ActionCollectionStore(tmp_path / "actions.db")
    store.ensure_sources(REGISTRY, NOW)
    complete(store, NOW, [split()])
    attempt = store.begin_attempt("NVDA", START, END, NOW + timedelta(hours=25))
    store.complete_failure(
        attempt_id=attempt,
        completed_at=NOW + timedelta(hours=25),
        error_code="http_429",
        http_status=429,
        request_url="https://query1.finance.yahoo.com/test",
        body=b'{"error":"rate limited"}',
    )
    nvda = next(
        item for item in store.status(REGISTRY, NOW).sources if item.symbol == "NVDA"
    )
    assert nvda.last_success_at == NOW
    assert nvda.error_code == "http_429"
    assert nvda.latest_attempt_raw_available is True
    assert store.event_page(None, 50).items[0].observation_state == "observed"


def test_cycle_lock_does_not_recover_active_attempt(tmp_path: Path) -> None:
    async def scenario() -> None:
        store = ActionCollectionStore(tmp_path / "actions.db")
        store.ensure_sources(REGISTRY, NOW)
        pending = store.begin_attempt("NVDA", START, END, NOW)
        lock_path = store.path.with_suffix(store.path.suffix + ".lock")
        with lock_path.open("a+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            async with httpx.AsyncClient(
                base_url="https://query1.finance.yahoo.com",
                transport=httpx.MockTransport(lambda _request: httpx.Response(500)),
            ) as client:
                collector = ActionCollector(store, client, now=lambda: NOW)
                assert await collector.run_once() is False
        with sqlite3.connect(store.path) as connection:
            state = connection.execute(
                "SELECT state FROM action_collection_attempts WHERE id=?", (pending,)
            ).fetchone()
        assert state == ("pending",)

    asyncio.run(scenario())


def test_cancel_waits_for_begin_write_and_records_interruption(tmp_path: Path) -> None:
    class DelayedStore(ActionCollectionStore):
        def __init__(self, path: Path) -> None:
            super().__init__(path)
            self.entered = threading.Event()
            self.release = threading.Event()

        def begin_attempt(self, *args: object, **kwargs: object) -> str:
            self.entered.set()
            self.release.wait(timeout=2)
            return super().begin_attempt(*args, **kwargs)  # type: ignore[arg-type]

    async def scenario() -> None:
        store = DelayedStore(tmp_path / "actions.db")
        store.ensure_sources(REGISTRY, NOW)
        async with httpx.AsyncClient(
            base_url="https://query1.finance.yahoo.com",
            transport=httpx.MockTransport(lambda _request: httpx.Response(500)),
        ) as client:
            collector = ActionCollector(store, client, now=lambda: NOW)
            task = asyncio.create_task(collector._collect(NVDA))
            assert await asyncio.to_thread(store.entered.wait, 1)
            task.cancel()
            await asyncio.sleep(0)
            assert not task.done()
            store.release.set()
            with pytest.raises(asyncio.CancelledError):
                await task
        with sqlite3.connect(store.path) as connection:
            states = connection.execute(
                "SELECT state FROM action_collection_attempts"
            ).fetchall()
        assert states == [("interrupted",)]

    asyncio.run(scenario())


def test_cancel_wins_over_database_error_and_releases_lock(tmp_path: Path) -> None:
    class FailingStore(ActionCollectionStore):
        def __init__(self, path: Path) -> None:
            super().__init__(path)
            self.entered = threading.Event()
            self.release = threading.Event()

        def ensure_sources(self, *args: object, **kwargs: object) -> None:
            self.entered.set()
            self.release.wait(timeout=2)
            raise sqlite3.OperationalError("synthetic locked database")

    async def scenario() -> None:
        store = FailingStore(tmp_path / "actions.db")
        async with httpx.AsyncClient(
            base_url="https://query1.finance.yahoo.com",
            transport=httpx.MockTransport(lambda _request: httpx.Response(500)),
        ) as client:
            collector = ActionCollector(store, client, now=lambda: NOW)
            task = asyncio.create_task(collector.run_once())
            assert await asyncio.to_thread(store.entered.wait, 1)
            task.cancel()
            await asyncio.sleep(0)
            lock_path = store.path.with_suffix(store.path.suffix + ".lock")
            with lock_path.open("a+") as contender:
                with pytest.raises(BlockingIOError):
                    fcntl.flock(contender, fcntl.LOCK_EX | fcntl.LOCK_NB)
            store.release.set()
            with pytest.raises(asyncio.CancelledError):
                await task
            with lock_path.open("a+") as contender:
                fcntl.flock(contender, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(contender, fcntl.LOCK_UN)

    asyncio.run(scenario())


def test_competing_cycle_cannot_recover_first_collectors_attempt(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        store = ActionCollectionStore(tmp_path / "actions.db")
        store.ensure_sources(REGISTRY, NOW)
        with sqlite3.connect(store.path) as connection:
            connection.execute(
                """UPDATE action_collection_source_status
                SET next_due_at=? WHERE symbol!='NVDA'""",
                ((NOW + timedelta(days=1)).isoformat(),),
            )
        entered = asyncio.Event()
        release = asyncio.Event()

        async def handler(_request: httpx.Request) -> httpx.Response:
            entered.set()
            await release.wait()
            return httpx.Response(200, content=chart_body(events={}))

        first_client = httpx.AsyncClient(
            base_url="https://query1.finance.yahoo.com",
            transport=httpx.MockTransport(handler),
        )
        second_client = httpx.AsyncClient(
            base_url="https://query1.finance.yahoo.com",
            transport=httpx.MockTransport(lambda _request: httpx.Response(500)),
        )
        first = ActionCollector(store, first_client, now=lambda: NOW)
        second = ActionCollector(store, second_client, now=lambda: NOW)
        first_task = asyncio.create_task(first.run_once())
        await entered.wait()
        assert await second.run_once() is False
        with sqlite3.connect(store.path) as connection:
            assert connection.execute(
                "SELECT state FROM action_collection_attempts"
            ).fetchall() == [("pending",)]
        release.set()
        assert await first_task is True
        with sqlite3.connect(store.path) as connection:
            assert connection.execute(
                "SELECT state FROM action_collection_attempts"
            ).fetchall() == [("success",)]
        await first.stop()
        await second.stop()

    asyncio.run(scenario())


def test_cancel_waits_for_success_commit(tmp_path: Path) -> None:
    class DelayedStore(ActionCollectionStore):
        def __init__(self, path: Path) -> None:
            super().__init__(path)
            self.entered = threading.Event()
            self.release = threading.Event()

        def complete_success(self, *args: object, **kwargs: object) -> None:
            self.entered.set()
            self.release.wait(timeout=2)
            super().complete_success(*args, **kwargs)  # type: ignore[arg-type]

    async def scenario() -> None:
        store = DelayedStore(tmp_path / "actions.db")
        store.ensure_sources(REGISTRY, NOW)
        async with httpx.AsyncClient(
            base_url="https://query1.finance.yahoo.com",
            transport=httpx.MockTransport(
                lambda _request: httpx.Response(200, content=chart_body(events={}))
            ),
        ) as client:
            collector = ActionCollector(store, client, now=lambda: NOW)
            task = asyncio.create_task(collector._collect(NVDA))
            assert await asyncio.to_thread(store.entered.wait, 1)
            task.cancel()
            await asyncio.sleep(0)
            assert not task.done()
            store.release.set()
            with pytest.raises(asyncio.CancelledError):
                await task
        with sqlite3.connect(store.path) as connection:
            assert connection.execute(
                "SELECT state FROM action_collection_attempts"
            ).fetchall() == [("success",)]

    asyncio.run(scenario())


def test_timeout_has_no_fake_raw_body(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def scenario() -> None:
        store = ActionCollectionStore(tmp_path / "actions.db")
        store.ensure_sources(REGISTRY, NOW)

        async def handler(_request: httpx.Request) -> httpx.Response:
            await asyncio.sleep(0.05)
            return httpx.Response(200, content=chart_body(events={}))

        monkeypatch.setattr(
            "jusik.research_action_collection.TOTAL_TIMEOUT_SECONDS", 0.001
        )
        async with httpx.AsyncClient(
            base_url="https://query1.finance.yahoo.com",
            transport=httpx.MockTransport(handler),
        ) as client:
            await ActionCollector(store, client, now=lambda: NOW)._collect(NVDA)
        nvda = next(
            item
            for item in store.status(REGISTRY, NOW).sources
            if item.symbol == "NVDA"
        )
        assert nvda.error_code == "request_timeout"
        assert nvda.latest_attempt_raw_available is False

    asyncio.run(scenario())


def test_oversized_integer_is_completed_as_bounded_parse_failure(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        store = ActionCollectionStore(tmp_path / "actions.db")
        store.ensure_sources(REGISTRY, NOW)
        raw = chart_body(events={}).replace(
            b'"events": {}', b'"events": {}, "x": ' + b"1" * 5000
        )
        async with httpx.AsyncClient(
            base_url="https://query1.finance.yahoo.com",
            transport=httpx.MockTransport(
                lambda _request: httpx.Response(200, content=raw)
            ),
        ) as client:
            await ActionCollector(store, client, now=lambda: NOW)._collect(NVDA)
        nvda = next(
            item
            for item in store.status(REGISTRY, NOW).sources
            if item.symbol == "NVDA"
        )
        assert nvda.state == "error"
        assert nvda.error_code == "numeric_literal_too_large"
        assert nvda.latest_attempt_raw_available is True
        assert nvda.next_due_at == NOW + timedelta(hours=1)
        due = store.due_symbols(NOW + timedelta(minutes=59))
        assert "NVDA" not in due
        assert len(due) == len(REGISTRY) - 1

    asyncio.run(scenario())


def test_oversize_response_is_not_claimed_as_preserved_raw(tmp_path: Path) -> None:
    async def scenario() -> None:
        store = ActionCollectionStore(tmp_path / "actions.db")
        store.ensure_sources(REGISTRY, NOW)
        async with httpx.AsyncClient(
            base_url="https://query1.finance.yahoo.com",
            transport=httpx.MockTransport(
                lambda _request: httpx.Response(
                    200, content=b"x" * (MAX_BODY_BYTES + 1)
                )
            ),
        ) as client:
            collector = ActionCollector(store, client, now=lambda: NOW)
            await collector._collect(NVDA)
        nvda = next(
            item
            for item in store.status(REGISTRY, NOW).sources
            if item.symbol == "NVDA"
        )
        assert nvda.error_code == "response_body_too_large"
        assert nvda.latest_attempt_raw_available is False
        assert nvda.latest_attempt_id is not None
        with pytest.raises(KeyError):
            store.raw_attempt(nvda.latest_attempt_id)

    asyncio.run(scenario())


def test_action_api_paginates_and_checks_raw_hash(tmp_path: Path) -> None:
    class UnusedProvider:
        async def collect(self, request: ResearchRunRequest) -> ResearchInputSnapshot:
            raise AssertionError(f"Unexpected historical collection: {request}")

    action_db = tmp_path / "actions.db"
    store = ActionCollectionStore(action_db)
    store.ensure_sources(REGISTRY, NOW)
    raw_attempt = complete(store, NOW, [split()])
    complete(
        store,
        NOW + timedelta(hours=25),
        [split(), split().model_copy(update={"provider_key": "second"})],
    )
    app = create_research_app(
        settings=ResearchSettings(
            app_key="test-key",
            app_secret="test-secret",
            base_url=PAPER_BASE_URL,
            db_path=tmp_path / "research.db",
        ),
        provider=UnusedProvider(),
        forward_db_path=tmp_path / "forward.db",
        universe_db_path=tmp_path / "universe.db",
        external_db_path=tmp_path / "external.db",
        history_dir=tmp_path / "history",
        history_db_path=tmp_path / "history.db",
        action_collection_db_path=action_db,
        action_collection_enabled=False,
    )
    with TestClient(app) as client:
        status = client.get("/api/research/actions/status")
        assert status.status_code == 200
        assert len(status.json()["sources"]) == len(REGISTRY)
        assert status.json()["automatic_ledger_application"] is False

        first = client.get("/api/research/actions/events?limit=1")
        assert first.status_code == 200
        assert len(first.json()["items"]) == 1
        assert first.json()["next_cursor"] is not None
        second = client.get(
            "/api/research/actions/events",
            params={"limit": 1, "cursor": first.json()["next_cursor"]},
        )
        assert second.status_code == 200
        assert second.json()["items"][0]["id"] != first.json()["items"][0]["id"]

        revisions = client.get("/api/research/actions/revisions?limit=1")
        assert revisions.status_code == 200
        assert revisions.json()["items"][0]["symbol"] == "NVDA"
        assert revisions.json()["items"][0]["provider_key"]
        assert (
            client.get("/api/research/actions/events?cursor=../secret").status_code
            == 400
        )
        raw = client.get(f"/api/research/actions/raw/{raw_attempt}")
        assert raw.status_code == 200
        assert raw.headers["content-type"] == "application/octet-stream"
        assert raw.headers["content-disposition"].endswith(f'{raw_attempt}.body"')
        assert (
            hashlib.sha256(raw.content).hexdigest() == raw.headers["x-content-sha256"]
        )
        assert client.get("/api/research/actions/raw/..%2Fsecret").status_code == 404

        with sqlite3.connect(action_db) as connection:
            connection.execute(
                "UPDATE action_collection_attempts SET body=? WHERE id=?",
                (b"tampered", raw_attempt),
            )
        assert client.get(f"/api/research/actions/raw/{raw_attempt}").status_code == 404
