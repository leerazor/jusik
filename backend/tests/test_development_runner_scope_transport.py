"""Frozen research proposals recover only from verified reviewer transport failure."""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from threading import Barrier
from types import ModuleType
from typing import Any, cast

import pytest
import test_development_runner_backlog as backlog
from test_development_runner_backlog import _fake_blocked_child
from test_development_runner_discovery import _exhausted, _fake_child, _git
from test_development_runner_planning_scope import _fake_planner, _fake_scope
from test_development_runner_review_transport import Clock, _transport_child

from jusik import development_runner as runner
from jusik import development_runner_store as journal
from jusik.development_runner_planning_scope import PendingRoadmapScope


def _pending(
    tmp_path: Path,
) -> tuple[runner.RunnerConfig, journal.RunnerStore, PendingRoadmapScope, Path]:
    fake = tmp_path / "child"
    _fake_planner(fake)
    base, store = _exhausted(tmp_path, fake)
    config = base.model_copy(update={"planning_enabled": True, "daily_launches": None})
    assert runner.run_once(config).reason == "planning_scope_pending"
    pending = store.pending_roadmap_scope()
    assert pending is not None
    return config, store, pending, fake


def _rows(store: journal.RunnerStore, table: str) -> list[dict[str, Any]]:
    assert table in {"roadmap_planning_scopes", "roadmap_scope_attempts", "attempts"}
    with sqlite3.connect(store.db_path) as db:
        db.row_factory = sqlite3.Row
        return [
            dict(row) for row in db.execute(f"SELECT * FROM {table} ORDER BY rowid")
        ]


def _claim(
    store: journal.RunnerStore,
    config: runner.RunnerConfig,
    pending: PendingRoadmapScope,
    review_id: str = "retry",
) -> bool:
    return store.start_roadmap_scope_review(
        pending,
        review_id,
        config.state_dir / review_id,
        journal.utc_now(),
        repo=config.repo,
        daily_launches=config.daily_launches,
        cooldown_seconds=config.cooldown_seconds,
    )


def test_delay_restart_exact_boundary_and_independent_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = Clock(monkeypatch)
    config, store, pending, fake = _pending(tmp_path)
    clock.advance(1)
    before = _rows(store, "roadmap_planning_scopes")[0]
    planner = _rows(store, "attempts")
    _transport_child(fake)
    assert runner.run_once(config).reason == "roadmap_scope_codex_exit"
    wait = _rows(store, "roadmap_planning_scopes")[0]
    failed = _rows(store, "roadmap_scope_attempts")[0]
    assert wait["status"] == "transport_wait"
    assert (wait["retry_kind"], wait["transient_failures"]) == ("capacity", 1)
    assert wait["retry_after"] == (clock.now + timedelta(minutes=5)).isoformat()
    assert failed["status"] == "failed" and failed["reason"] == "transport_capacity"
    for key in ("pending_json", "pending_sha256", "planner_attempt_id", "fingerprint"):
        assert wait[key] == before[key]
    assert _rows(store, "attempts") == planner
    assert store.task(pending.planner_task_id).status == "scope_pending"  # type: ignore[union-attr]
    restarted = journal.RunnerStore(store.db_path)
    _fake_scope(fake)
    clock.advance(299)
    assert restarted.pending_roadmap_scope() is None
    assert not _claim(restarted, config, pending)
    assert restarted.task(pending.proposal.id) is None
    clock.advance(1)
    assert restarted.pending_roadmap_scope() == pending
    assert not restarted.start_roadmap_scope_review(
        pending, "unconfigured", tmp_path / "out", journal.utc_now(), repo=config.repo
    )
    assert runner.run_once(config).reason == "roadmap_scope_approved"
    assert _rows(store, "roadmap_scope_attempts")[0] == failed
    assert len(_rows(store, "roadmap_scope_attempts")) == 2
    assert restarted.task(pending.proposal.id).status == "queued"  # type: ignore[union-attr]
    assert restarted.pending_roadmap_scope() is None
    assert store.launch_count(clock.now.strftime("%Y-%m-%d")) == 3


@pytest.mark.parametrize(
    "code,kind",
    [
        ("model_capacity", "capacity"),
        ("rate_limit", "rate_limit"),
        ("network_error", "network"),
        ("503", "server"),
        ("unauthorized", "auth"),
    ],
)
def test_repeated_failures_and_safe_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, code: str, kind: str
) -> None:
    clock = Clock(monkeypatch)
    config, store, pending, fake = _pending(tmp_path)
    clock.advance(1)
    _transport_child(fake, code=code)
    delays = (21_600, 21_600, 21_600) if kind == "auth" else (300, 900, 3600, 3600)
    for count, delay in enumerate(delays, 1):
        assert runner.run_once(config).reason == "roadmap_scope_codex_exit"
        status = store.roadmap_scope_status()
        assert status is not None
        assert status["retry_kind"] == kind and status["transient_failures"] == count
        assert (
            status["retry_after"] == (clock.now + timedelta(seconds=delay)).isoformat()
        )
        assert set(status) == {
            "status",
            "reason",
            "updated_at",
            "retry_kind",
            "retry_after",
            "transient_failures",
        }
        clock.advance(delay - 1)
        assert journal.RunnerStore(store.db_path).pending_roadmap_scope() is None
        clock.advance(1)
        assert journal.RunnerStore(store.db_path).pending_roadmap_scope() == pending
    assert (
        json.loads(_rows(store, "roadmap_planning_scopes")[0]["pending_json"])[
            "expires_at"
        ]
        == pending.expires_at
    )


def test_expiry_cleans_up_before_later_auth_deadline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = Clock(monkeypatch)
    config, store, pending, fake = _pending(tmp_path)
    clock.advance(23 * 3600)
    _transport_child(fake, code="unauthorized")
    assert runner.run_once(config).reason == "roadmap_scope_codex_exit"
    wait = _rows(store, "roadmap_planning_scopes")[0]
    clock.advance(3600)
    assert clock.now.isoformat() == pending.expires_at
    assert store.pending_roadmap_scope() == pending
    assert runner.run_once(config).reason == "roadmap_scope_stale"
    assert len(_rows(store, "roadmap_scope_attempts")) == 1
    after = _rows(store, "roadmap_planning_scopes")[0]
    assert after["status"] == "stale"
    assert after["pending_json"] == wait["pending_json"]
    assert after["retry_after"] == wait["retry_after"]


def test_future_wait_reaches_fallback_without_duplicate_planner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = Clock(monkeypatch)
    config, store, _, fake = _pending(tmp_path)
    clock.advance(1)
    _transport_child(fake)
    runner.run_once(config)
    planner = _rows(store, "attempts")
    clock.advance(1)
    _fake_child(fake)
    assert runner.run_once(config).reason == "discovery_scope"
    assert _rows(store, "attempts") == planner
    assert len(_rows(store, "roadmap_scope_attempts")) == 1


def test_independent_ready_runs_and_changed_snapshot_makes_scope_stale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = Clock(monkeypatch)
    config, store, _, fake = _pending(tmp_path)
    clock.advance(1)
    _transport_child(fake)
    runner.run_once(config)
    assert store.enqueue("ready", "r1-01", "Independent offline diagnosis")
    clock.advance(1)
    _fake_blocked_child(fake)
    assert runner.run_once(config).task_id == "ready"
    assert len(_rows(store, "roadmap_scope_attempts")) == 1
    clock.advance(300)
    assert runner.run_once(config).reason == "roadmap_scope_stale"
    assert len(_rows(store, "roadmap_scope_attempts")) == 1


@pytest.mark.parametrize("change", ["head", "evidence", "governance"])
def test_due_retry_preserves_exact_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    clock = Clock(monkeypatch)
    config, store, pending, fake = _pending(tmp_path)
    clock.advance(1)
    _transport_child(fake)
    runner.run_once(config)
    if change == "head":
        (config.repo / "unrelated.txt").write_text("independent committed work\n")
        _git(config.repo, "add", "unrelated.txt")
        _git(config.repo, "commit", "-m", "independent work")
    else:
        Path(pending.proposal.evidence[0].path).write_text("changed\n")
        if change == "governance":
            _git(config.repo, "add", "docs/research-mandate.json")
            _git(config.repo, "commit", "-m", "changed governance")
    clock.advance(300)
    assert not _claim(store, config, pending)
    if change == "head":
        assert runner.run_once(config).reason == "roadmap_scope_stale"
    assert store.task(pending.proposal.id) is None
    assert len(_rows(store, "roadmap_scope_attempts")) == 1


@pytest.mark.parametrize("gate", ["pause", "quota", "cooldown", "cap", "planner"])
def test_due_claim_rechecks_transaction_gates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, gate: str
) -> None:
    clock = Clock(monkeypatch)
    config, store, pending, fake = _pending(tmp_path)
    clock.advance(1)
    _transport_child(fake)
    runner.run_once(config)
    clock.advance(300)
    wait = _rows(store, "roadmap_planning_scopes")
    if gate == "pause":
        store.pause()
    elif gate == "quota":
        config = config.model_copy(update={"daily_launches": 2})
    elif gate == "cooldown":
        config = config.model_copy(update={"cooldown_seconds": 301})
    elif gate == "cap":
        for index in range(8):
            assert store.enqueue(f"independent-{index}", "offline", "fixture")
    else:
        with sqlite3.connect(store.db_path) as db:
            db.execute(
                "UPDATE tasks SET last_attempt_id=NULL WHERE id=?",
                (pending.planner_task_id,),
            )
    assert not _claim(store, config, pending)
    assert _rows(store, "roadmap_planning_scopes") == wait
    assert len(_rows(store, "roadmap_scope_attempts")) == 1
    assert store.launch_count(clock.now.strftime("%Y-%m-%d")) == 2


@pytest.mark.parametrize(
    "field,value",
    [
        ("retry_kind", "timeout"),
        ("transient_failures", 0),
        ("transient_failures", 1.5),
        ("retry_after", "invalid"),
        ("retry_after", "2026-09-26T00:05:00"),
        ("retry_after", "2026-09-26T00:04:59+00:00"),
        ("reason", "failed"),
    ],
)
def test_malformed_metadata_is_never_due(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str, value: object
) -> None:
    clock = Clock(monkeypatch)
    config, store, pending, fake = _pending(tmp_path)
    clock.advance(1)
    _transport_child(fake)
    runner.run_once(config)
    with sqlite3.connect(store.db_path) as db:
        db.execute(f"UPDATE roadmap_planning_scopes SET {field}=?", (value,))
    clock.advance(300)
    assert store.pending_roadmap_scope() is None
    assert not _claim(store, config, pending)
    status = store.roadmap_scope_status()
    assert status is not None
    assert status["retry_kind"] is None and status["retry_after"] is None
    assert status["transient_failures"] == 0
    assert status["reason"] == "transport_metadata_invalid"


def test_concurrent_due_claim_and_interrupted_transaction_have_no_pending_gap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = Clock(monkeypatch)
    config, store, pending, fake = _pending(tmp_path)
    clock.advance(1)
    _transport_child(fake)
    runner.run_once(config)
    clock.advance(300)
    before = _rows(store, "roadmap_planning_scopes")
    with sqlite3.connect(store.db_path) as db:
        db.execute(
            "CREATE TRIGGER fail_launch BEFORE INSERT ON launch_log BEGIN "
            "SELECT RAISE(ABORT,'interrupted transaction'); END"
        )
    with pytest.raises(sqlite3.IntegrityError, match="interrupted transaction"):
        _claim(store, config, pending)
    assert _rows(store, "roadmap_planning_scopes") == before
    assert len(_rows(store, "roadmap_scope_attempts")) == 1
    with sqlite3.connect(store.db_path) as db:
        db.execute("DROP TRIGGER fail_launch")
        db.execute(
            "CREATE TRIGGER reject_gap BEFORE UPDATE ON roadmap_planning_scopes "
            "WHEN NEW.status='pending' AND NEW.active_review_id IS NULL BEGIN "
            "SELECT RAISE(ABORT,'pending gap'); END"
        )
    stores = [journal.RunnerStore(store.db_path), journal.RunnerStore(store.db_path)]
    barrier = Barrier(2)

    def claim(index: int) -> bool:
        barrier.wait()
        return _claim(stores[index], config, pending, f"retry-{index}")

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(claim, (0, 1))) == [False, True]
    assert len(store.running_roadmap_scope_reviews()) == 1
    assert store.launch_count(clock.now.strftime("%Y-%m-%d")) == 3


def test_transport_finish_is_atomic_and_active_scope_cannot_be_terminalized(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = Clock(monkeypatch)
    config, store, pending, _ = _pending(tmp_path)
    clock.advance(1)
    assert _claim(store, config, pending)
    assert not store.terminalize_roadmap_scope(pending, "stale_input")
    parent = _rows(store, "roadmap_planning_scopes")
    attempts = _rows(store, "roadmap_scope_attempts")
    with sqlite3.connect(store.db_path) as db:
        db.execute(
            "CREATE TRIGGER interrupt_finish BEFORE UPDATE ON roadmap_planning_scopes "
            "WHEN NEW.status='transport_wait' BEGIN "
            "SELECT RAISE(ABORT,'interrupted finish'); END"
        )
    with pytest.raises(sqlite3.IntegrityError, match="interrupted finish"):
        store.finish_roadmap_scope_review(
            pending, "retry", "failed", retry_kind="server"
        )
    assert _rows(store, "roadmap_planning_scopes") == parent
    assert _rows(store, "roadmap_scope_attempts") == attempts
    with sqlite3.connect(store.db_path) as db:
        db.execute("DROP TRIGGER interrupt_finish")
    assert store.finish_roadmap_scope_review(
        pending, "retry", "failed", retry_kind="server"
    )
    assert not store.finish_roadmap_scope_review(
        pending, "retry", "failed", retry_kind="server"
    )
    assert _rows(store, "roadmap_planning_scopes")[0]["transient_failures"] == 1


@pytest.mark.parametrize(
    "kind",
    [
        "unknown",
        "text",
        "oversized",
        "timeout",
        "orphan",
        "forged_success",
        "REJECT",
        "WAIT",
        "invalid",
    ],
)
def test_nontransport_failure_never_opts_in(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    clock = Clock(monkeypatch)
    config, store, _, fake = _pending(tmp_path)
    clock.advance(1)
    if kind in {"REJECT", "WAIT", "invalid"}:
        _fake_scope(
            fake,
            verdict=kind if kind != "invalid" else "PASS",
            tamper=kind == "invalid",
        )
    else:
        _transport_child(
            fake, code="unknown" if kind == "unknown" else "model_capacity"
        )
        if kind in {"text", "oversized", "timeout"}:
            expression = {
                "text": "print('model_capacity')",
                "oversized": "print('x' * 1048577)",
                "timeout": "import time; time.sleep(10)",
            }[kind]
            fake.write_text(
                "#!/usr/bin/env python3\nimport sys\nsys.stdin.read()\n"
                + expression
                + "\nsys.exit(1)\n"
            )
        if kind == "timeout":
            config = config.model_copy(update={"timeout_seconds": 1})
        if kind == "orphan":
            monkeypatch.setattr(runner, "_process_group_alive", lambda _: True)
        if kind == "forged_success":
            fake.write_text(fake.read_text().replace("sys.exit(1)", "sys.exit(0)"))
    runner.run_once(config)
    row = _rows(store, "roadmap_planning_scopes")[0]
    assert row["status"] not in {"pending", "transport_wait"}
    assert row["retry_kind"] is None and row["transient_failures"] == 0


def _frozen_module(monkeypatch: pytest.MonkeyPatch, filename: str) -> ModuleType:
    source = subprocess.run(
        [
            "git",
            "show",
            "3130718812e75402e4ed8bc5eee1470a18351ccb:backend/jusik/" + filename,
        ],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    module = ModuleType("_frozen_scope_" + filename.removesuffix(".py"))
    monkeypatch.setitem(sys.modules, module.__name__, module)
    exec(compile(source, "frozen-scope-store.py", "exec"), module.__dict__)
    return module


def _old_store(monkeypatch: pytest.MonkeyPatch) -> type[journal.RunnerStore]:
    module = _frozen_module(monkeypatch, "development_runner_store.py")
    return cast(type[journal.RunnerStore], module.RunnerStore)


def test_actual_previous_store_quarantines_wait_and_interrupted_due_claim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = Clock(monkeypatch)
    config, store, pending, fake = _pending(tmp_path)
    clock.advance(1)
    _transport_child(fake)
    runner.run_once(config)
    old_type = _old_store(monkeypatch)
    failed = _rows(store, "roadmap_scope_attempts")[0]
    for stage in ("before", "due", "claimed"):
        if stage == "due":
            clock.advance(300)
        if stage == "claimed":
            assert _claim(store, config, pending)
        copied = tmp_path / stage / "runner.db"
        copied.parent.mkdir()
        with sqlite3.connect(store.db_path) as source, sqlite3.connect(copied) as dest:
            source.backup(dest)
        old = old_type(copied)
        if stage == "claimed":
            assert len(old.running_roadmap_scope_reviews()) == 1
            old.quarantine_roadmap_scope_review("retry", uncertain=False)
        assert old.pending_roadmap_scope() is None
        upgraded = journal.RunnerStore(copied)
        assert (upgraded.pending_roadmap_scope() is not None) == (stage == "due")
        assert _rows(upgraded, "roadmap_scope_attempts")[0] == failed
        with sqlite3.connect(copied) as db:
            assert db.execute("PRAGMA integrity_check").fetchone() == ("ok",)


def test_additive_migration_preserves_every_legacy_column_and_terminal_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = Clock(monkeypatch)
    old_type = _old_store(monkeypatch)
    old_runner = _frozen_module(monkeypatch, "development_runner.py")
    monkeypatch.setattr(old_runner, "datetime", getattr(runner, "datetime"))
    monkeypatch.setattr(backlog, "RunnerStore", old_type)
    monkeypatch.setattr(runner, "RunnerStore", old_type)
    monkeypatch.setattr(
        runner, "_run_roadmap_scope_review", old_runner._run_roadmap_scope_review
    )
    config, store, _, fake = _pending(tmp_path)
    clock.advance(1)
    _transport_child(fake)
    assert runner.run_once(config).reason == "roadmap_scope_codex_exit"
    assert _rows(store, "roadmap_planning_scopes")[0]["status"] == "failed"
    with sqlite3.connect(store.db_path) as db:
        tables = [
            row[0]
            for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name!='sqlite_sequence'"
            )
        ]
        columns = {
            table: [row[1] for row in db.execute(f"PRAGMA table_info({table})")]
            for table in tables
        }
        before = {
            table: db.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()
            for table in tables
        }
    for _ in range(3):
        upgraded = journal.RunnerStore(store.db_path)
        assert upgraded.pending_roadmap_scope() is None
        with sqlite3.connect(store.db_path) as db:
            for table in tables:
                assert (
                    db.execute(
                        f"SELECT {','.join(columns[table])} FROM {table} ORDER BY rowid"
                    ).fetchall()
                    == before[table]
                )
            assert db.execute(
                "SELECT retry_kind,retry_after,transient_failures "
                "FROM roadmap_planning_scopes"
            ).fetchall() == [(None, None, 0)]
            assert db.execute("PRAGMA integrity_check").fetchone() == ("ok",)
