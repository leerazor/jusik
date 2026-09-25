"""Finite roadmap engineering backlog with isolated Git and SQLite state."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from test_development_runner_roadmap import _tracked_repo

from jusik.development_runner import RunnerConfig, run_once, validate_completion
from jusik.development_runner_contract import (
    AUTOMATIC_ENGINEERING_BACKLOG,
    ENGINEERING_SPEC_BY_ID,
    ENGINEERING_SPEC_ID,
    ENGINEERING_SPEC_PROMPT,
    Blocker,
    EngineeringSpec,
)
from jusik.development_runner_review import review_schema, validate_receipt
from jusik.development_runner_roadmap import ROADMAP_SCOPE
from jusik.development_runner_store import RunnerStore


def _config(tmp_path: Path, fake: Path, *, enabled: bool = True) -> RunnerConfig:
    return RunnerConfig(
        repo=_tracked_repo(tmp_path),
        codex=str(fake),
        state_dir=tmp_path / "state",
        history_dir=tmp_path / "history",
        history_db=tmp_path / "history.db",
        artifact_dir=tmp_path / "artifacts",
        cooldown_seconds=0,
        planning_enabled=True,
        automatic_engineering_backlog=enabled,
        scope=ROADMAP_SCOPE,
    )


def _store(config: RunnerConfig) -> RunnerStore:
    store = RunnerStore(config.state_dir / "runner.db", config.history_dir)
    store.set_meta("scope", ROADMAP_SCOPE)
    return store


def _fake_blocked_child(path: Path) -> None:
    path.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        "from pathlib import Path\n"
        "prompt = sys.stdin.read()\n"
        "fields = dict(line.split(': ', 1) for line in prompt.splitlines() "
        "if line.startswith(('Task id: ', 'Attempt id: ')))\n"
        "payload = {'task_id': fields['Task id'], "
        "'attempt_id': fields['Attempt id'], 'status': 'blocked', "
        "'blocked_reason': 'offline_fixture_stopped', "
        "'tests_passed': False, 'review_passed': False}\n"
        "Path(sys.argv[sys.argv.index('-o') + 1]).write_text("
        "json.dumps(payload), encoding='utf-8')\n",
        encoding="utf-8",
    )
    path.chmod(0o700)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


def _idle(store: RunnerStore) -> None:
    store.set_meta(
        "idle_status",
        json.dumps(
            {
                "reason": "fixed_engineering_backlog_exhausted",
                "next_check_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            }
        ),
    )


def test_retry_clears_stale_idle_only_after_ready_transition(tmp_path: Path) -> None:
    store = RunnerStore(tmp_path / "state" / "runner.db")
    assert store.enqueue("task", "r1-01", "offline fixture")
    assert store.quarantine(
        "task", "blocked", {"blocker_reason": "fixture", "next_eligible_retry": None}
    )
    _idle(store)
    assert not store.retry("missing")
    assert store.get_meta("idle_status") is not None
    assert store.retry("task")
    assert store.task("task").status == "queued"  # type: ignore[union-attr]
    assert store.get_meta("idle_status") is None


def test_due_wait_release_clears_stale_idle(tmp_path: Path) -> None:
    store = RunnerStore(tmp_path / "state" / "runner.db")
    assert store.enqueue("task", "r1-01", "offline fixture")
    due = datetime.now(UTC) - timedelta(seconds=1)
    blocker = Blocker(
        blocker_reason="fixture",
        resume_condition="UTC deadline",
        retry_policy="bounded",
        next_eligible_retry=due,
    )
    assert store.quarantine("task", "waiting_external", blocker.model_dump(mode="json"))
    _idle(store)
    assert store.release_due_waiting(due - timedelta(seconds=1)) == []
    assert store.get_meta("idle_status") is not None
    assert store.release_due_waiting(datetime.now(UTC)) == ["task"]
    assert store.task("task").status == "queued"  # type: ignore[union-attr]
    assert store.get_meta("idle_status") is None


def test_event_release_clears_stale_idle(tmp_path: Path) -> None:
    store = RunnerStore(tmp_path / "state" / "runner.db")
    assert store.enqueue("task", "r1-01", "offline fixture")
    evidence = tmp_path / "evidence.txt"
    evidence.write_text("before", encoding="utf-8")
    blocker = Blocker(
        blocker_reason="source_wait",
        dependency=str(evidence.resolve()),
        dependency_identity=hashlib.sha256(evidence.read_bytes()).hexdigest(),
        resume_condition="evidence changes",
        retry_policy="event",
    )
    assert store.quarantine("task", "waiting_external", blocker.model_dump(mode="json"))
    _idle(store)
    assert not store.release_event("task", evidence)
    assert store.get_meta("idle_status") is not None
    evidence.write_text("after", encoding="utf-8")
    assert store.release_event("task", evidence)
    assert store.task("task").status == "queued"  # type: ignore[union-attr]
    assert store.get_meta("idle_status") is None


def test_planning_retry_clears_stale_idle(tmp_path: Path) -> None:
    store = RunnerStore(tmp_path / "state" / "runner.db")
    assert store.enqueue("planner", "__planning__", "internal")
    task = store.task("planner")
    assert task is not None
    store.claim(task, "attempt", tmp_path / "output", tmp_path / "stderr")
    store.finish("attempt", "planner", "completed", failure_code="planning_waiting")
    _idle(store)
    assert not store.retry_planning_waiting("planner", [("missing", "queued", None)])
    assert store.get_meta("idle_status") is not None
    assert store.retry_planning_waiting("planner", [])
    assert store.task("planner").status == "queued"  # type: ignore[union-attr]
    assert store.get_meta("idle_status") is None


def test_rebase_clears_stale_idle(tmp_path: Path) -> None:
    store = RunnerStore(tmp_path / "state" / "runner.db")
    assert store.enqueue("task", "r1-01", "offline fixture")
    assert store.quarantine(
        "task", "blocked", {"blocker_reason": "fixture", "next_eligible_retry": None}
    )
    _idle(store)
    assert store.rebase("task", "a" * 40)
    assert store.task("task").status == "queued"  # type: ignore[union-attr]
    assert store.get_meta("idle_status") is None


def test_retry_between_backlog_decision_and_return_cannot_restore_idle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _config(tmp_path, tmp_path / "must-not-run")
    store = _store(config)
    for spec in AUTOMATIC_ENGINEERING_BACKLOG:
        assert store.enqueue(spec.id, spec.area, spec.prompt, task_kind="engineering")
        assert store.quarantine(
            spec.id,
            "blocked",
            {"blocker_reason": "fixture", "next_eligible_retry": None},
        )
    first_id = AUTOMATIC_ENGINEERING_BACKLOG[0].id
    original = RunnerStore.enqueue_next_engineering_spec
    interleaved = False

    def retry_after_decision(
        current: RunnerStore,
    ) -> tuple[EngineeringSpec | None, str]:
        nonlocal interleaved
        result = original(current)
        assert result == (None, "fixed_engineering_backlog_exhausted")
        assert current.retry(first_id)
        interleaved = True
        return result

    monkeypatch.setattr(
        RunnerStore, "enqueue_next_engineering_spec", retry_after_decision
    )
    result = run_once(config)
    assert interleaved
    assert (result.status, result.reason) == (
        "idle",
        "fixed_engineering_backlog_exhausted",
    )
    assert store.task(first_id).status == "queued"  # type: ignore[union-attr]
    assert store.get_meta("idle_status") is None


def test_blocked_legacy_is_preserved_and_new_specs_dispatch_once(
    tmp_path: Path,
) -> None:
    fake = tmp_path / "fake-child.py"
    _fake_blocked_child(fake)
    config = _config(tmp_path, fake)
    store = _store(config)
    assert store.enqueue(
        ENGINEERING_SPEC_ID,
        "__engineering__",
        ENGINEERING_SPEC_PROMPT,
        task_kind="engineering",
    )
    assert store.quarantine(
        ENGINEERING_SPEC_ID,
        "blocked",
        {
            "blocker_reason": "historical_review_unavailable",
            "next_eligible_retry": None,
        },
    )
    original = store.task(ENGINEERING_SPEC_ID)

    first = run_once(config)
    assert (first.status, first.task_id) == (
        "blocked",
        AUTOMATIC_ENGINEERING_BACKLOG[0].id,
    )
    assert store.task(ENGINEERING_SPEC_ID) == original
    assert store.task(AUTOMATIC_ENGINEERING_BACKLOG[0].id).attempt_count == 1  # type: ignore[union-attr]
    assert store.task(AUTOMATIC_ENGINEERING_BACKLOG[1].id) is None

    second = run_once(config)
    assert (second.status, second.task_id) == (
        "blocked",
        AUTOMATIC_ENGINEERING_BACKLOG[1].id,
    )
    assert store.task(AUTOMATIC_ENGINEERING_BACKLOG[0].id).status == "blocked"  # type: ignore[union-attr]
    assert store.task(ENGINEERING_SPEC_ID) == original
    assert store.launch_count(datetime.now(UTC).strftime("%Y-%m-%d")) == 2

    exhausted = run_once(config)
    assert (exhausted.status, exhausted.reason) == (
        "idle",
        "fixed_engineering_backlog_exhausted",
    )
    idle = json.loads(store.get_meta("idle_status") or "{}")
    assert idle["reason"] == exhausted.reason
    assert datetime.fromisoformat(idle["next_check_at"]) > datetime.now(UTC)
    assert run_once(config).status == "idle"
    assert store.launch_count(datetime.now(UTC).strftime("%Y-%m-%d")) == 2


@pytest.mark.parametrize("gate", ["disabled", "paused", "quota", "cooldown"])
def test_backlog_respects_global_gates(tmp_path: Path, gate: str) -> None:
    fake = tmp_path / "must-not-run"
    config = _config(tmp_path, fake, enabled=gate != "disabled")
    if gate == "disabled":
        config = config.model_copy(update={"planning_enabled": False})
    store = _store(config)
    if gate == "paused":
        store.pause()
    elif gate == "quota":
        config = config.model_copy(update={"daily_launches": 1})
        store.record_launch(datetime.now(UTC).isoformat())
    elif gate == "cooldown":
        config = config.model_copy(update={"cooldown_seconds": 3600})
        store.set_meta("last_launch_at", datetime.now(UTC).isoformat())
    result = run_once(config)
    assert (
        result.status
        == {
            "disabled": "idle",
            "paused": "paused",
            "quota": "quota",
            "cooldown": "cooldown",
        }[gate]
    )
    assert all(store.task(spec.id) is None for spec in AUTOMATIC_ENGINEERING_BACKLOG)
    assert store.get_meta("idle_status") is None


def test_full_ready_queue_does_not_create_backlog_task(tmp_path: Path) -> None:
    fake = tmp_path / "must-not-run"
    config = _config(tmp_path, fake)
    store = _store(config)
    for index in range(8):
        assert store.enqueue(
            f"waiting-{index}",
            "r1-01",
            "independent queued dependency",
            depends_on="missing",
            task_kind="investment",
        )
    result = run_once(config)
    assert (result.status, result.reason) == ("idle", "engineering_queue_full")
    idle = json.loads(store.get_meta("idle_status") or "{}")
    assert idle["reason"] == "engineering_queue_full"
    assert datetime.fromisoformat(idle["next_check_at"]) > datetime.now(UTC)
    assert all(store.task(spec.id) is None for spec in AUTOMATIC_ENGINEERING_BACKLOG)


def test_existing_ready_runs_before_fixed_backlog(tmp_path: Path) -> None:
    fake = tmp_path / "fake-child.py"
    _fake_blocked_child(fake)
    config = _config(tmp_path, fake)
    store = _store(config)
    assert store.enqueue("ready", "r1-01", "existing work", task_kind="investment")
    result = run_once(config)
    assert (result.status, result.task_id) == ("blocked", "ready")
    assert all(store.task(spec.id) is None for spec in AUTOMATIC_ENGINEERING_BACKLOG)


@pytest.mark.parametrize("spec", AUTOMATIC_ENGINEERING_BACKLOG, ids=lambda s: s.id)
def test_engineering_runtime_prompt_binds_owned_evidence_to_main(
    tmp_path: Path,
    spec: EngineeringSpec,
) -> None:
    fake = tmp_path / "fake-child.py"
    _fake_blocked_child(fake)
    config = _config(tmp_path, fake)
    store = _store(config)
    assert store.enqueue(spec.id, spec.area, spec.prompt, task_kind="engineering")

    result = run_once(config)

    assert (result.status, result.task_id) == ("blocked", spec.id)
    assert result.attempt_id is not None
    prompt = (
        config.state_dir / "attempts" / result.attempt_id / "prompt.txt"
    ).read_text(encoding="utf-8")
    for owned_path in spec.owned_paths:
        assert str(config.repo.resolve() / owned_path) in prompt
    assert "canonical main" in prompt
    assert "SHA-256" in prompt
    assert "task worktree" in prompt
    assert "audit copies" in prompt
    assert "durable handoff" in prompt
    assert "registered P1 finding" in prompt
    assert "existing owned branch" in prompt
    assert "outside the registered spec" in prompt


def test_invalid_governance_blocks_backlog_before_enqueue(tmp_path: Path) -> None:
    fake = tmp_path / "must-not-run"
    config = _config(tmp_path, fake)
    store = _store(config)
    (config.repo / "docs" / "research-mandate.json").write_text("{}", encoding="utf-8")
    assert run_once(config).status == "blocked"
    assert all(store.task(spec.id) is None for spec in AUTOMATIC_ENGINEERING_BACKLOG)


@pytest.mark.parametrize("spec", AUTOMATIC_ENGINEERING_BACKLOG, ids=lambda s: s.id)
def test_new_spec_requires_exact_commit_evidence_and_review_identity(
    tmp_path: Path, spec: EngineeringSpec
) -> None:
    registered = ENGINEERING_SPEC_BY_ID[spec.id]
    fake = tmp_path / "must-not-run"
    config = _config(tmp_path, fake)
    store = _store(config)
    baseline = _git(config.repo, "rev-parse", "main")
    for name in registered.owned_paths:
        path = config.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("offline fixture\n", encoding="utf-8")
    _git(config.repo, "add", "backend")
    _git(config.repo, "commit", "-m", "offline fixture")
    head = _git(config.repo, "rev-parse", "main")
    assert store.enqueue(
        registered.id, registered.area, registered.prompt, task_kind="engineering"
    )
    task = store.task(registered.id)
    assert task is not None
    evidence = [
        {
            "path": str((config.repo / name).resolve()),
            "sha256": hashlib.sha256((config.repo / name).read_bytes()).hexdigest(),
        }
        for name in sorted(registered.owned_paths)
    ]
    payload = {
        "task_id": registered.id,
        "attempt_id": "implementation",
        "status": "completed",
        "integrated_commit": head,
        "evidence": evidence,
        "tests_passed": True,
        "review_passed": False,
        "handoff_path": evidence[0]["path"],
        "blocked_reason": None,
        "followup": None,
    }
    assert validate_completion(
        payload, task, "implementation", config, baseline_head=baseline
    )
    wrong_hash = json.loads(json.dumps(payload))
    wrong_hash["evidence"][0]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="evidence path or hash"):
        validate_completion(
            wrong_hash, task, "implementation", config, baseline_head=baseline
        )
    wrong_paths = json.loads(json.dumps(payload))
    wrong_paths["evidence"] = wrong_paths["evidence"][:1]
    with pytest.raises(ValueError, match="exact owned paths"):
        validate_completion(
            wrong_paths, task, "implementation", config, baseline_head=baseline
        )
    extra_path = config.repo / "docs" / "development-runner.md"
    extra_evidence = json.loads(json.dumps(payload))
    extra_evidence["evidence"].append(
        {
            "path": str(extra_path),
            "sha256": hashlib.sha256(extra_path.read_bytes()).hexdigest(),
        }
    )
    with pytest.raises(ValueError, match="exact owned paths"):
        validate_completion(
            extra_evidence, task, "implementation", config, baseline_head=baseline
        )
    schema = review_schema(registered.owned_paths)
    assert (
        set(schema["properties"]["owned_file_hashes"]["required"])
        == registered.owned_paths
    )
    context = {
        "task_id": registered.id,
        "implementation_attempt_id": "implementation",
        "review_attempt_id": "review",
        "baseline_head": baseline,
        "main_head": head,
        "owned_file_hashes": {
            name: hashlib.sha256((config.repo / name).read_bytes()).hexdigest()
            for name in registered.owned_paths
        },
    }
    assert validate_receipt(
        context | {"verdict": "PASS"}, context, registered.owned_paths
    )
    with pytest.raises(ValueError, match="owned hashes"):
        validate_receipt(
            context | {"owned_file_hashes": {}, "verdict": "PASS"},
            context,
            registered.owned_paths,
        )
    with pytest.raises(ValueError, match="identity"):
        validate_receipt(
            context | {"main_head": baseline, "verdict": "PASS"},
            context,
            registered.owned_paths,
        )

    reviewer = tmp_path / "fake-reviewer.py"
    reviewer.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        "from pathlib import Path\n"
        "prompt = sys.stdin.read()\n"
        "context = json.loads(prompt.split('fields: ', 1)[1])\n"
        "context['verdict'] = 'PASS'\n"
        "Path(sys.argv[sys.argv.index('-o') + 1]).write_text("
        "json.dumps(context), encoding='utf-8')\n",
        encoding="utf-8",
    )
    reviewer.chmod(0o700)
    store.claim(
        task,
        "implementation",
        tmp_path / "completion",
        tmp_path / "stderr",
        baseline_head=baseline,
    )
    store.finish(
        "implementation",
        task.id,
        "waiting_external",
        failure_code="independent_review_pending",
        evidence={"review_candidate_version": 1, "completion": payload},
    )
    result = run_once(config.model_copy(update={"codex": str(reviewer)}))
    assert (result.status, result.task_id) == ("completed", registered.id)
    assert store.task(registered.id).engineering_status == "ENGINEERING_COMPLETE"  # type: ignore[union-attr]
    with sqlite3.connect(store.db_path) as db:
        saved_context = json.loads(
            db.execute("SELECT context_json FROM review_attempts").fetchone()[0]
        )
    assert set(saved_context["owned_file_hashes"]) == registered.owned_paths
    schema_path = (
        config.state_dir
        / "reviews"
        / saved_context["review_attempt_id"]
        / "receipt.schema.json"
    )
    runtime_schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert (
        set(runtime_schema["properties"]["owned_file_hashes"]["required"])
        == registered.owned_paths
    )
