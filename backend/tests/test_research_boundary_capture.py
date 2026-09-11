from __future__ import annotations

import asyncio
import fcntl
import hashlib
import os
import sqlite3
import threading
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

import jusik.research_app as research_app_module
from jusik.research_app import create_research_app
from jusik.research_boundary_capture import (
    MAX_CAPTURE_BODY_BYTES,
    BoundaryCaptureMonitor,
    BoundaryCaptureStatus,
    _Budget,
    read_boundary_capture,
)
from jusik.research_config import PAPER_BASE_URL, ResearchSettings
from jusik.research_forward_models import ForwardConfig, ForwardIntent
from jusik.research_forward_store import ForwardStore
from jusik.research_models import ResearchInputSnapshot, ResearchRunRequest
from jusik.research_prospective_registration import (
    EVALUATION_END_AT,
    EVALUATION_START_AT,
    CodeIdentity,
    ProspectiveRegistration,
    ProspectiveRegistrationStatus,
    _evaluation_definition,
)
from jusik.research_quote_models import ResearchQuote
from jusik.research_store import ResearchStore

COLLECTOR_SHA = "a" * 64


class _UnusedProvider:
    async def collect(self, request: ResearchRunRequest) -> ResearchInputSnapshot:
        raise AssertionError(f"unexpected collection request: {request}")


def _fixture(
    tmp_path: Path,
) -> tuple[Path, ForwardStore, ProspectiveRegistrationStatus]:
    database = tmp_path / "forward.db"
    store = ForwardStore(database)
    session = store.activate(
        activated_at=datetime(2026, 9, 11, tzinfo=UTC),
        next_due_at=EVALUATION_START_AT,
        source_run_id="fixed-source",
        config=ForwardConfig(),
    )
    registration = ProspectiveRegistration.model_construct(
        schema_version=1,
        session_id=session.id,
        session_activated_at=session.activated_at,
        config=session.config,
        policy_hash=session.policy_hash,
        source_run_id=session.source_run_id,
        source_manifest_sha256="1" * 64,
        source_result_sha256="2" * 64,
        input_sha256="3" * 64,
        registered_at=datetime(2026, 9, 11, tzinfo=UTC),
        evaluation_start_at=EVALUATION_START_AT,
        evaluation_end_at=EVALUATION_END_AT,
        evaluation_duration_days=56,
        code_identity=CodeIdentity.model_construct(sha256="4" * 64, files={}),
        evaluation=_evaluation_definition(),
        user_loss_tolerance_pct=20,
        policy_defense_drawdown_pct=Decimal("10"),
        paper_only=True,
        automatic_promotion_eligible=False,
        contract_sha256="5" * 64,
    )
    status = ProspectiveRegistrationStatus.model_construct(
        status="observing",
        checked_at=EVALUATION_START_AT,
        reason=None,
        current_session_id=session.id,
        app_start_code_identity_sha256="4" * 64,
        current_disk_code_identity_sha256="4" * 64,
        current_source_manifest_sha256="1" * 64,
        current_source_result_sha256="2" * 64,
        registration=registration,
    )
    return database, store, status


def _monitor(
    database: Path,
    output: Path,
    status: ProspectiveRegistrationStatus,
    *,
    now: datetime,
    collector_sha: str = COLLECTOR_SHA,
) -> BoundaryCaptureMonitor:
    return BoundaryCaptureMonitor(
        forward_db=database,
        output_dir=output,
        registration_status=lambda _: status,
        clock=lambda: now,
        collector_sha=lambda: collector_sha,
    )


def _quote(at: datetime) -> ResearchQuote:
    return ResearchQuote(
        symbol="NVDA",
        exchange="NAS",
        currency="USD",
        price=Decimal("100"),
        ask=Decimal("101"),
        bid=Decimal("99"),
        volume=1,
        accumulated_volume=1,
        market_at=at,
        received_at=at + timedelta(seconds=1),
        source="KIS HDFSCNT0",
    )


def _database_contents(database: Path) -> str:
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        return "\n".join(connection.iterdump())


def test_before_boundary_only_polls_and_creates_no_artifact(tmp_path: Path) -> None:
    database, _store, status = _fixture(tmp_path)
    output = tmp_path / "captures"
    current = EVALUATION_START_AT - timedelta(microseconds=1)
    monitor = _monitor(database, output, status, now=current)
    asyncio.run(monitor.run_once())
    result = monitor.status()
    assert result.last_poll_at == current
    assert [item.state for item in result.boundaries] == ["scheduled", "scheduled"]
    assert not output.exists()


def test_due_capture_is_raw_observed_canonical_and_idempotent(
    tmp_path: Path,
) -> None:
    database, store, status = _fixture(tmp_path)
    assert status.registration is not None
    store.save_observation(
        status.registration.session_id,
        _quote(EVALUATION_START_AT + timedelta(seconds=1)),
    )
    output = tmp_path / "captures"
    now = EVALUATION_START_AT + timedelta(seconds=5)
    monitor = _monitor(database, output, status, now=now)
    database_before = _database_contents(database)
    asyncio.run(monitor.run_once())
    assert _database_contents(database) == database_before
    target = output / status.registration.session_id / "start.json"
    artifact = read_boundary_capture(
        target,
        registration=status.registration,
        boundary="start",
    )
    assert artifact.read_started_at == now
    assert artifact.raw_observed_at_capture is True
    assert artifact.boundary_asof_reconstructed is False
    assert artifact.accepted_nav is False
    assert artifact.evaluation_inputs_complete is False
    assert artifact.snapshot.latest_observations[0].scope == "latest_at_read_time"
    before = (target.read_bytes(), target.stat().st_mtime_ns)
    asyncio.run(monitor.run_once())
    assert (target.read_bytes(), target.stat().st_mtime_ns) == before
    assert not (target.parent / "end.json").exists()


def test_restart_reuses_start_and_captures_end_when_both_due(
    tmp_path: Path,
) -> None:
    database, _store, status = _fixture(tmp_path)
    assert status.registration is not None
    output = tmp_path / "captures"
    first = _monitor(
        database,
        output,
        status,
        now=EVALUATION_START_AT + timedelta(seconds=1),
    )
    asyncio.run(first.run_once())
    start = output / status.registration.session_id / "start.json"
    original = (start.read_bytes(), start.stat().st_mtime_ns)
    restarted = _monitor(
        database,
        output,
        status,
        now=EVALUATION_END_AT + timedelta(seconds=1),
        collector_sha="b" * 64,
    )
    asyncio.run(restarted.run_once())
    assert (start.read_bytes(), start.stat().st_mtime_ns) == original
    end = start.parent / "end.json"
    assert end.is_file()
    start_artifact = read_boundary_capture(
        start, registration=status.registration, boundary="start"
    )
    end_artifact = read_boundary_capture(
        end, registration=status.registration, boundary="end"
    )
    assert start_artifact.collector_startup_sha256 == COLLECTOR_SHA
    assert end_artifact.collector_startup_sha256 == "b" * 64
    downloaded, downloaded_sha = restarted.artifact_body("start")
    assert downloaded == original[0]
    assert downloaded_sha == hashlib.sha256(original[0]).hexdigest()


def test_clock_rollback_never_publishes_preboundary_artifact(
    tmp_path: Path,
) -> None:
    database, _store, status = _fixture(tmp_path)
    output = tmp_path / "captures"
    clocks = iter(
        [
            EVALUATION_START_AT + timedelta(seconds=1),
            EVALUATION_START_AT - timedelta(microseconds=1),
        ]
    )
    monitor = BoundaryCaptureMonitor(
        forward_db=database,
        output_dir=output,
        registration_status=lambda _: status,
        clock=lambda: next(clocks),
        collector_sha=lambda: COLLECTOR_SHA,
    )
    asyncio.run(monitor.run_once())
    assert not list(output.rglob("*.json"))


def test_nonblocking_lock_precedes_registration_database_read(tmp_path: Path) -> None:
    database, _store, status = _fixture(tmp_path)
    output = tmp_path / "captures"
    output.mkdir()
    lock_path = output / ".start.lock"
    descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    calls = 0

    def registration(_: datetime) -> ProspectiveRegistrationStatus:
        nonlocal calls
        calls += 1
        return status

    monitor = BoundaryCaptureMonitor(
        forward_db=database,
        output_dir=output,
        registration_status=registration,
        clock=lambda: EVALUATION_START_AT,
        collector_sha=lambda: COLLECTOR_SHA,
    )
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(BlockingIOError):
            monitor._capture("start", EVALUATION_START_AT)
    finally:
        os.close(descriptor)
    assert calls == 0


def test_corrupt_existing_capture_is_not_overwritten(tmp_path: Path) -> None:
    database, _store, status = _fixture(tmp_path)
    assert status.registration is not None
    output = tmp_path / "captures"
    monitor = _monitor(database, output, status, now=EVALUATION_START_AT)
    asyncio.run(monitor.run_once())
    target = output / status.registration.session_id / "start.json"
    target.write_bytes(b"corrupt")
    before = (target.read_bytes(), target.stat().st_mtime_ns)
    restarted = _monitor(database, output, status, now=EVALUATION_START_AT)
    asyncio.run(restarted.run_once())
    assert (target.read_bytes(), target.stat().st_mtime_ns) == before
    assert restarted.status().boundaries[0].state == "error"
    assert restarted.status().boundaries[0].error_code == "artifact_invalid"


def test_missing_and_invalid_referenced_input_persist_as_issues(
    tmp_path: Path,
) -> None:
    database, store, status = _fixture(tmp_path)
    assert status.registration is not None
    input_id = store.save_input_version(
        status.registration.session_id, EVALUATION_START_AT, {}
    )
    deeply_nested = "[" * 20_000 + "0" + "]" * 20_000
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE forward_input_versions SET payload_json=? WHERE id=?",
            (deeply_nested, input_id),
        )
    store.record_decision(
        session_id=status.registration.session_id,
        due_at=EVALUATION_START_AT,
        recorded_at=EVALUATION_START_AT,
        input_version=input_id,
        reason="fixture",
        expires_at=EVALUATION_START_AT + timedelta(days=1),
        target_weights={},
        intents=[
            ForwardIntent(
                symbol="NVDA",
                side="buy",
                target_weight=Decimal("0.1"),
                budget_krw=Decimal("1000"),
                state="pending",
                reason="fixture",
            )
        ],
    )
    output = tmp_path / "captures"
    monitor = _monitor(database, output, status, now=EVALUATION_START_AT)
    asyncio.run(monitor.run_once())
    artifact = read_boundary_capture(
        output / status.registration.session_id / "start.json",
        registration=status.registration,
        boundary="start",
    )
    assert artifact.issues
    assert {issue.code for issue in artifact.issues} >= {
        "invalid_payload",
        "missing_reference",
    }
    assert monitor.status().boundaries[0].state == "captured_with_issues"


def test_oversize_row_and_total_budget_are_omitted_not_retried(
    tmp_path: Path,
) -> None:
    database, store, status = _fixture(tmp_path)
    assert status.registration is not None
    input_id = "6" * 64
    decision = store.record_decision(
        session_id=status.registration.session_id,
        due_at=EVALUATION_START_AT,
        recorded_at=EVALUATION_START_AT,
        input_version=input_id,
        reason="fixture",
        expires_at=None,
        target_weights={},
        intents=[],
    )
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE forward_decisions SET reason=? WHERE id=?",
            ("x" * (256 * 1024 + 1), decision.id),
        )
    output = tmp_path / "captures"
    monitor = _monitor(database, output, status, now=EVALUATION_START_AT)
    asyncio.run(monitor.run_once())
    artifact = read_boundary_capture(
        output / status.registration.session_id / "start.json",
        registration=status.registration,
        boundary="start",
    )
    assert any(issue.code == "row_oversize" for issue in artifact.issues)
    budget = _Budget()
    assert budget.reserve(MAX_CAPTURE_BODY_BYTES)
    assert not budget.reserve(1)


def test_oversize_capture_key_cannot_alias_literal_none_key(tmp_path: Path) -> None:
    database, _store, status = _fixture(tmp_path)
    assert status.registration is not None
    with sqlite3.connect(database) as connection:
        connection.executemany(
            "INSERT INTO forward_positions VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    status.registration.session_id,
                    symbol,
                    "USD",
                    1,
                    "100",
                    EVALUATION_START_AT.isoformat(),
                )
                for symbol in ("x" * 257, "None")
            ],
        )
    output = tmp_path / "captures"
    monitor = _monitor(database, output, status, now=EVALUATION_START_AT)
    asyncio.run(monitor.run_once())
    artifact = read_boundary_capture(
        output / status.registration.session_id / "start.json",
        registration=status.registration,
        boundary="start",
    )
    positions = artifact.snapshot.positions
    position_count = next(
        item for item in artifact.counts if item.table == "forward_positions"
    )
    position_issue = next(
        item
        for item in artifact.issues
        if item.table == "forward_positions" and item.code == "row_oversize"
    )
    assert [position.symbol for position in positions] == ["None"]
    assert (position_count.total_count, position_count.included_count) == (2, 1)
    assert position_count.omitted_count == 1
    assert position_issue.count == 1
    assert position_issue.references == ["capture_key_over_256_bytes"]


def test_cancel_waits_for_running_thread_before_finishing(tmp_path: Path) -> None:
    database, _store, status = _fixture(tmp_path)
    monitor = _monitor(
        database,
        tmp_path / "captures",
        status,
        now=EVALUATION_START_AT,
    )
    entered = threading.Event()
    release = threading.Event()

    def delayed(_boundary: str, _at: datetime) -> bool:
        entered.set()
        release.wait(timeout=5)
        return False

    monitor._capture = delayed  # type: ignore[assignment]

    async def exercise() -> None:
        task = asyncio.create_task(monitor.run_once())
        assert await asyncio.to_thread(entered.wait, 2)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(exercise())


def test_status_model_exposes_worker_poll_state() -> None:
    status = BoundaryCaptureStatus.model_validate(
        {
            "checked_at": EVALUATION_START_AT.isoformat(),
            "session_id": None,
            "collector_implemented": True,
            "running": False,
            "last_poll_at": None,
            "collector_startup_sha256": COLLECTOR_SHA,
            "collector_current_sha256": None,
            "boundaries": [
                {
                    "boundary": boundary,
                    "boundary_at": at.isoformat(),
                    "state": "scheduled",
                    "issue_count": 0,
                    "download_available": False,
                }
                for boundary, at in (
                    ("start", EVALUATION_START_AT),
                    ("end", EVALUATION_END_AT),
                )
            ],
            "limitations": [],
        }
    )
    assert status.running is False
    assert status.last_poll_at is None


def test_started_monitor_crosses_boundary_and_captures_automatically(
    tmp_path: Path,
) -> None:
    database, _store, status = _fixture(tmp_path)
    output = tmp_path / "captures"
    current = [EVALUATION_START_AT - timedelta(seconds=1)]

    async def advance(_: float) -> None:
        current[0] = EVALUATION_START_AT
        await asyncio.sleep(0)

    monitor = BoundaryCaptureMonitor(
        forward_db=database,
        output_dir=output,
        registration_status=lambda _: status,
        clock=lambda: current[0],
        sleep=advance,
        collector_sha=lambda: COLLECTOR_SHA,
    )

    async def exercise() -> None:
        monitor.start()
        assert status.current_session_id is not None
        target = output / status.current_session_id / "start.json"
        try:
            for _ in range(200):
                await asyncio.sleep(0.01)
                if target.is_file():
                    break
            running = monitor.status()
            assert running.running is True
            assert running.last_poll_at == EVALUATION_START_AT
            assert target.is_file()
        finally:
            await monitor.stop()
        assert monitor.status().running is False

    asyncio.run(exercise())


def test_database_failure_retries_and_collector_change_blocks_new_capture(
    tmp_path: Path,
) -> None:
    database, _store, status = _fixture(tmp_path)
    output = tmp_path / "captures"
    monitor = _monitor(database, output, status, now=EVALUATION_START_AT)
    capture = monitor._capture
    calls = 0

    def fail_once(boundary: str, at: datetime) -> bool:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise sqlite3.OperationalError("fixture busy")
        return capture(boundary, at)  # type: ignore[arg-type]

    monitor._capture = fail_once  # type: ignore[assignment]
    asyncio.run(monitor.run_once())
    assert monitor.status().boundaries[0].error_code == "database_unavailable"
    asyncio.run(monitor.run_once())
    assert monitor.status().boundaries[0].state == "captured_raw"

    changed = _monitor(
        database,
        tmp_path / "changed",
        status,
        now=EVALUATION_START_AT,
    )
    changed._collector_sha = lambda: "b" * 64
    asyncio.run(changed.run_once())
    changed_status = changed.status().boundaries[0]
    assert changed_status.state == "error"
    assert changed_status.error_code == "collector_identity_changed"
    assert not list((tmp_path / "changed").rglob("*.json"))


def test_api_status_and_hash_download_use_fixed_boundary_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database, _store, status = _fixture(tmp_path)
    assert status.registration is not None
    output = tmp_path / "captures"
    monitor = _monitor(database, output, status, now=EVALUATION_START_AT)
    asyncio.run(monitor.run_once())
    monkeypatch.setattr(
        research_app_module, "prospective_registration_status", lambda **_: status
    )
    monkeypatch.setattr(
        research_app_module,
        "collector_code_sha256",
        lambda: COLLECTOR_SHA,
        raising=False,
    )
    settings = ResearchSettings(
        app_key=SecretStr("key"),
        app_secret=SecretStr("secret"),
        base_url=PAPER_BASE_URL,
        db_path=tmp_path / "research.db",
    )
    app = create_research_app(
        settings=settings,
        store=ResearchStore(tmp_path / "research.db"),
        provider=_UnusedProvider(),
        forward_db_path=database,
        boundary_capture_dir=output,
        action_collection_enabled=False,
    )
    app_monitor_sha = COLLECTOR_SHA
    with TestClient(app) as client:
        app.state.boundary_capture._startup_sha = app_monitor_sha
        app.state.boundary_capture._collector_sha = lambda: app_monitor_sha
        response = client.get("/api/research/validation/prospective/boundary-captures")
        assert response.status_code == 200
        assert response.json()["running"] is False
        download = client.get(
            "/api/research/validation/prospective/boundary-captures/start"
        )
        invalid = client.get(
            "/api/research/validation/prospective/boundary-captures/other"
        )
    assert download.status_code == 200
    assert download.headers["content-type"] == "application/octet-stream"
    assert (
        download.headers["x-content-sha256"]
        == hashlib.sha256(download.content).hexdigest()
    )
    assert invalid.status_code == 422
