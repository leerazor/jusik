from __future__ import annotations

import hashlib
import json
import subprocess
import threading
import time
import tomllib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from jusik.development_runner import (
    RunnerConfig,
    RunResult,
    _git_common,
    _next_task,
    _prepare_artifact_dir,
    _safe_history_flush,
    init_config,
    pause_runner,
    run_once,
    validate_completion,
)
from jusik.development_runner_planning import PLANNING_AREA
from jusik.development_runner_store import RunnerStore


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "Runner Test")
    (repo / "README.md").write_text("test\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "initial")
    return repo


@pytest.mark.parametrize("mode", [0o750, 0o770])
def test_prepare_artifact_dir_preserves_existing_mode(
    tmp_path: Path, mode: int
) -> None:
    artifact = tmp_path / "existing"
    artifact.mkdir(mode=mode)
    artifact.chmod(mode)

    assert _prepare_artifact_dir(artifact) == artifact.resolve()
    assert artifact.stat().st_mode & 0o777 == mode


def test_prepare_artifact_dir_creates_missing_directory_with_private_mode(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "missing" / "nested"

    assert _prepare_artifact_dir(artifact) == artifact.resolve()
    assert artifact.stat().st_mode & 0o777 == 0o700


def test_interrupted_attempt_is_quarantined_until_explicit_retry(
    tmp_path: Path,
) -> None:
    store = RunnerStore(tmp_path / "state" / "runner.db")
    assert store.enqueue("task-a", "entry-amount-distribution", "prompt")
    task = store.task("task-a")
    assert task is not None
    store.claim(task, "attempt-a", tmp_path / "out", tmp_path / "err")
    assert _next_task(store) is None

    recovered = store.recover_running()
    assert [attempt.id for attempt in recovered] == ["attempt-a"]
    assert store.task("task-a").status == "interrupted"  # type: ignore[union-attr]
    assert [item[3] for item in store.outbox_pending()[:2]] == [
        "started",
        "interrupted",
    ]
    assert store.retry("task-a")
    assert _next_task(store).id == "task-a"  # type: ignore[union-attr]

    task = store.task("task-a")
    assert task is not None
    store.claim(task, "attempt-b", tmp_path / "out-b", tmp_path / "err-b")
    store.finish("attempt-b", "task-a", "failed", failure_code="invalid")
    assert store.task("task-a").status == "failed"  # type: ignore[union-attr]
    assert store.retry("task-a")
    store.add_outbox(
        "development-runner:task-a:attempt-b:failed", "task-a", "attempt-b", "failed"
    )
    assert len(store.outbox_pending()) == 4


def test_persisted_dependency_keeps_small_entry_task_behind_distribution(
    tmp_path: Path,
) -> None:
    store = RunnerStore(tmp_path / "state" / "runner.db")
    store.enqueue("distribution", "entry-amount-distribution", "prompt")
    store.enqueue(
        "small-entry",
        "preregistration-small-entry",
        "prompt",
        depends_on="distribution",
    )
    assert _next_task(store).id == "distribution"  # type: ignore[union-attr]
    distribution = store.task("distribution")
    assert distribution is not None
    store.claim(distribution, "attempt-a", tmp_path / "out", tmp_path / "err")
    store.finish("attempt-a", "distribution", "completed")
    assert _next_task(store).id == "small-entry"  # type: ignore[union-attr]


def test_validate_completion_checks_commit_and_evidence(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    evidence = repo / "evidence.json"
    evidence.write_text('{"ok": true}\n', encoding="utf-8")
    handoff = repo / "HANDOFF.md"
    handoff.write_text("handoff\n", encoding="utf-8")
    config = RunnerConfig(
        repo=repo,
        state_dir=tmp_path / "state",
        history_dir=tmp_path / "history",
        history_db=tmp_path / "history.db",
        artifact_dir=tmp_path / "artifact",
    )
    store = RunnerStore(config.state_dir / "runner.db", config.history_dir)
    store.enqueue("task-a", "entry-amount-distribution", "prompt")
    task = store.task("task-a")
    assert task is not None
    payload: dict[str, Any] = {
        "task_id": task.id,
        "attempt_id": "attempt-a",
        "status": "completed",
        "integrated_commit": _git(repo, "rev-parse", "HEAD"),
        "evidence": [
            {
                "path": str(evidence),
                "sha256": hashlib.sha256(evidence.read_bytes()).hexdigest(),
            }
        ],
        "tests_passed": True,
        "review_passed": True,
        "handoff_path": str(handoff),
        "followup": None,
    }
    assert validate_completion(payload, task, "attempt-a", config).task_id == task.id
    payload["evidence"][0]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="evidence"):
        validate_completion(payload, task, "attempt-a", config)


def test_validate_completion_allows_explicit_blocked_result(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    config = RunnerConfig(
        repo=repo,
        state_dir=tmp_path / "state",
        artifact_dir=tmp_path / "artifact",
    )
    store = RunnerStore(config.state_dir / "runner.db")
    store.enqueue("task-a", "future-observation-protocol", "prompt")
    task = store.task("task-a")
    assert task is not None
    result = validate_completion(
        {
            "task_id": "task-a",
            "attempt_id": "attempt-a",
            "status": "blocked",
            "integrated_commit": None,
            "evidence": [],
            "tests_passed": False,
            "review_passed": False,
            "handoff_path": None,
            "blocked_reason": "Future observation data is unavailable.",
            "followup": None,
        },
        task,
        "attempt-a",
        config,
    )
    assert result.status == "blocked"


def test_git_common_resolves_linked_worktree_to_main_git_directory(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    linked = tmp_path / "linked-worktree"
    _git(repo, "worktree", "add", "--detach", str(linked), "HEAD")
    assert _git_common(linked) == (repo / ".git").resolve()


def test_invalid_repo_does_not_create_child_or_change_task(tmp_path: Path) -> None:
    state = tmp_path / "state"
    history = tmp_path / "history"
    store = RunnerStore(state / "runner.db", history)
    store.enqueue("task-a", "entry-amount-distribution", "stored prompt")
    fake = tmp_path / "must-not-run"
    config = RunnerConfig(
        repo=tmp_path / "not-a-repository",
        codex=str(fake),
        state_dir=state,
        history_dir=history,
        history_db=tmp_path / "history.db",
        artifact_dir=tmp_path / "artifact",
    )

    result = run_once(config)

    assert result.status == "blocked"
    assert result.reason == "invalid repository"
    task = RunnerStore(state / "runner.db", history).task("task-a")
    assert task is not None and task.status == "queued" and task.attempt_count == 0
    assert not fake.exists()
    assert (
        RunnerStore(state / "runner.db", history).launch_count(
            datetime.now(UTC).strftime("%Y-%m-%d")
        )
        == 0
    )


def test_run_once_uses_named_permission_profile_for_stored_task(
    tmp_path: Path,
) -> None:
    repo_parent = tmp_path / 'repo parent "quoted"'
    repo_parent.mkdir()
    repo = _repo(repo_parent)
    state = tmp_path / "state"
    history = tmp_path / "history"
    artifact = tmp_path / 'artifact root "quoted"'
    artifact.mkdir()
    capture = tmp_path / "codex-args.json"
    captured_prompt = tmp_path / "codex-prompt.txt"
    fake = tmp_path / "fake-codex.py"
    fake.write_text(
        f"""#!/usr/bin/env python3
import json, pathlib, sys
pathlib.Path({str(capture)!r}).write_text(json.dumps(sys.argv[1:]), encoding='utf-8')
pathlib.Path({str(captured_prompt)!r}).write_text(sys.stdin.read(), encoding='utf-8')
output = pathlib.Path(sys.argv[sys.argv.index('-o') + 1])
output.write_text(json.dumps({{
    'task_id': 'task-a',
    'attempt_id': output.parent.name,
    'status': 'blocked',
    'integrated_commit': None,
    'evidence': [],
    'tests_passed': False,
    'review_passed': False,
    'handoff_path': None,
    'blocked_reason': 'test block',
    'followup': None,
}}), encoding='utf-8')
""",
        encoding="utf-8",
    )
    fake.chmod(0o700)
    config = RunnerConfig(
        repo=repo,
        codex=str(fake),
        state_dir=state,
        history_dir=history,
        history_db=tmp_path / "history.db",
        artifact_dir=artifact,
        cooldown_seconds=0,
    )
    store = RunnerStore(state / "runner.db", history)
    store.enqueue("task-a", "entry-amount-distribution", "legacy stored prompt")

    assert run_once(config).status == "blocked"
    args = json.loads(capture.read_text(encoding="utf-8"))
    assert "--ignore-user-config" in args
    assert "-s" not in args
    assert "--add-dir" not in args
    assert not any("sandbox_workspace_write" in value for value in args)
    default_value = args[args.index("-c") + 1]
    profile_value = args[args.index("-c", args.index("-c") + 1) + 1]
    settings = tomllib.loads(f"{default_value}\n{profile_value}\n")
    assert settings["default_permissions"] == "jusik-development"
    profile = settings["permissions"]["jusik-development"]
    assert profile["extends"] == ":workspace"
    assert profile["network"] == {"enabled": True}
    assert profile["filesystem"] == {str((repo / ".git").resolve()): "write"}
    roots = profile["workspace_roots"]
    assert roots[str(repo.parent.resolve())] is True
    assert roots[str(state.resolve())] is True
    assert roots[str(history.resolve())] is True
    assert roots[str(history.parent.resolve())] is True
    assert roots[str(artifact.resolve())] is True
    assert "Before removing any merged worktree" in captured_prompt.read_text(
        encoding="utf-8"
    )


def test_run_once_prepares_absent_custom_artifact_before_child_dispatch(
    tmp_path: Path,
) -> None:
    repo_area = tmp_path / "repo-area"
    repo_area.mkdir()
    repo = _repo(repo_area)
    state = repo_area / "state"
    history = repo_area / "history"
    artifact = tmp_path / "artifact-area" / "nested" / "custom"
    capture = tmp_path / "codex-args.json"
    seen = tmp_path / "artifact-seen.json"
    fake = tmp_path / "fake-codex.py"
    fake.write_text(
        f"""#!/usr/bin/env python3
import json, pathlib, sys
artifact = pathlib.Path({str(artifact)!r})
pathlib.Path({str(capture)!r}).write_text(json.dumps(sys.argv[1:]), encoding='utf-8')
pathlib.Path({str(seen)!r}).write_text(
    json.dumps({{'exists': artifact.is_dir()}}), encoding='utf-8'
)
output = pathlib.Path(sys.argv[sys.argv.index('-o') + 1])
output.write_text(json.dumps({{
    'task_id': 'task-a',
    'attempt_id': output.parent.name,
    'status': 'blocked',
    'integrated_commit': None,
    'evidence': [],
    'tests_passed': False,
    'review_passed': False,
    'handoff_path': None,
    'blocked_reason': 'test block',
    'followup': None,
}}), encoding='utf-8')
""",
        encoding="utf-8",
    )
    fake.chmod(0o700)
    config = RunnerConfig(
        repo=repo,
        codex=str(fake),
        state_dir=state,
        history_dir=history,
        history_db=tmp_path / "history.db",
        artifact_dir=artifact,
        cooldown_seconds=0,
    )
    store = RunnerStore(state / "runner.db", history)
    store.enqueue("task-a", "entry-amount-distribution", "prompt")

    assert not artifact.exists()
    assert run_once(config).status == "blocked"
    assert json.loads(seen.read_text(encoding="utf-8")) == {"exists": True}
    args = json.loads(capture.read_text(encoding="utf-8"))
    profile_value = args[args.index("-c", args.index("-c") + 1) + 1]
    profile = tomllib.loads(profile_value)["permissions"]["jusik-development"]
    roots = profile["workspace_roots"]
    assert roots[str(artifact.resolve())] is True
    assert str(artifact.parent.resolve()) not in roots


def test_unusable_artifact_blocks_before_claim_and_quota(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    artifact = tmp_path / "artifact-file"
    artifact.write_text("not a directory\n", encoding="utf-8")
    state = tmp_path / "state"
    history = tmp_path / "history"
    store = RunnerStore(state / "runner.db", history)
    store.enqueue("task-a", "entry-amount-distribution", "prompt")
    config = RunnerConfig(
        repo=repo,
        state_dir=state,
        history_dir=history,
        history_db=tmp_path / "history.db",
        artifact_dir=artifact,
        cooldown_seconds=0,
    )

    result = run_once(config)

    assert result.status == "blocked"
    assert result.reason == "artifact directory unavailable"
    task = store.task("task-a")
    assert task is not None and task.status == "queued" and task.attempt_count == 0
    assert store.launch_count(datetime.now(UTC).strftime("%Y-%m-%d")) == 0


def test_durable_evidence_remains_valid_after_linked_worktree_cleanup(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    linked = tmp_path / "merged-worktree"
    _git(repo, "worktree", "add", "--detach", str(linked), "HEAD")
    durable = tmp_path / "durable-artifacts"
    durable.mkdir()
    evidence = durable / "evidence.json"
    handoff = durable / "HANDOFF.md"
    evidence.write_text('{"survives": true}\n', encoding="utf-8")
    handoff.write_text("handoff\n", encoding="utf-8")
    config = RunnerConfig(
        repo=repo,
        state_dir=tmp_path / "state",
        history_dir=tmp_path / "history",
        history_db=tmp_path / "history.db",
        artifact_dir=durable,
    )
    store = RunnerStore(config.state_dir / "runner.db", config.history_dir)
    store.enqueue("task-a", "entry-amount-distribution", "prompt")
    task = store.task("task-a")
    assert task is not None
    payload = {
        "task_id": task.id,
        "attempt_id": "attempt-a",
        "status": "completed",
        "integrated_commit": _git(repo, "rev-parse", "HEAD"),
        "evidence": [
            {
                "path": str(evidence),
                "sha256": hashlib.sha256(evidence.read_bytes()).hexdigest(),
            }
        ],
        "tests_passed": True,
        "review_passed": True,
        "handoff_path": str(handoff),
        "followup": None,
    }

    _git(repo, "worktree", "remove", str(linked))
    assert validate_completion(payload, task, "attempt-a", config).status == "completed"


def test_run_once_fake_codex_success_preserves_private_result(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    evidence = repo / "evidence.json"
    evidence.write_text("evidence\n", encoding="utf-8")
    _git(repo, "add", "evidence.json")
    _git(repo, "commit", "-m", "add evidence")
    (repo / "HANDOFF.md").write_text("handoff\n", encoding="utf-8")
    fake = tmp_path / "fake-codex.py"
    fake.write_text(
        """#!/usr/bin/env python3
import hashlib, json, pathlib, subprocess, sys, time
time.sleep(2)
output = pathlib.Path(sys.argv[sys.argv.index('-o') + 1])
repo = pathlib.Path(sys.argv[sys.argv.index('-C') + 1])
attempt = output.parent.name
evidence = repo / 'evidence.json'
payload = {
    'task_id': 'entry-amount-distribution-v1',
    'attempt_id': attempt,
    'status': 'completed',
    'integrated_commit': subprocess.check_output(
        ['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True
    ).strip(),
    'evidence': [{'path': str(evidence),
                  'sha256': hashlib.sha256(evidence.read_bytes()).hexdigest()}],
    'tests_passed': True,
    'review_passed': True,
    'handoff_path': str(repo / 'HANDOFF.md'),
    'followup': None,
}
output.write_text(json.dumps(payload), encoding='utf-8')
""",
        encoding="utf-8",
    )
    fake.chmod(0o700)
    config_path = tmp_path / "config.json"
    config = init_config(
        config_path,
        repo,
        tmp_path / "state",
        tmp_path / "history",
        tmp_path / "history.db",
        tmp_path / "artifact",
    )
    config = config.model_copy(update={"codex": str(fake), "cooldown_seconds": 0})
    result = run_once(config)
    assert result.status == "completed"
    assert result.task_id == "entry-amount-distribution-v1"
    assert result.attempt_id is not None
    attempt_dir = config.state_dir / "attempts" / result.attempt_id
    assert (attempt_dir / "stdout.jsonl").stat().st_mode & 0o777 == 0o600
    task = RunnerStore(config.state_dir / "runner.db").task(result.task_id)
    assert task is not None and task.status == "completed"


@pytest.mark.parametrize("daily_launches", [1, 8, 24])
def test_config_accepts_supported_launch_settings(
    tmp_path: Path, daily_launches: int
) -> None:
    config = RunnerConfig(
        repo=tmp_path,
        artifact_dir=tmp_path / "artifact",
        daily_launches=daily_launches,
    )

    assert config.daily_launches == daily_launches


@pytest.mark.parametrize("daily_launches", [0, 25])
def test_config_rejects_unbounded_launch_settings(
    tmp_path: Path, daily_launches: int
) -> None:
    with pytest.raises(ValueError):
        RunnerConfig(
            repo=tmp_path,
            artifact_dir=tmp_path / "artifact",
            daily_launches=daily_launches,
        )


def test_pause_and_utc_launch_count_are_durable(tmp_path: Path) -> None:
    store = RunnerStore(tmp_path / "state" / "runner.db")
    assert not store.is_paused()
    store.pause()
    assert store.is_paused()
    store.resume()
    assert not store.is_paused()
    launched = datetime.now(UTC).isoformat()
    store.record_launch(launched)
    assert store.launch_count(launched[:10]) == 1
    assert store.launch_count("2099-01-01") == 0


def test_timeout_marks_attempt_failed_without_retrying_implicitly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    state = tmp_path / "state"
    history = tmp_path / "history"
    store = RunnerStore(state / "runner.db", history)
    assert store.enqueue("task-a", "entry-amount-distribution", "prompt")
    config = RunnerConfig(
        repo=repo,
        codex="unused",
        state_dir=state,
        history_dir=history,
        history_db=tmp_path / "history.db",
        artifact_dir=tmp_path / "artifact",
        timeout_seconds=60,
        cooldown_seconds=0,
    )

    class TimeoutProcess:
        pid = 100_001
        returncode = None

        def poll(self) -> None:
            return None

        def communicate(self, _prompt: bytes, timeout: int) -> None:
            raise subprocess.TimeoutExpired("fake", timeout)

        def wait(self, timeout: int) -> None:
            return None

    monkeypatch.setattr(
        "jusik.development_runner.subprocess.Popen",
        lambda *args, **kwargs: TimeoutProcess(),
    )
    monkeypatch.setattr(
        "jusik.development_runner._git_common", lambda _repo: repo / ".git"
    )
    monkeypatch.setattr("jusik.development_runner._git_ready", lambda _repo: (True, ""))
    monkeypatch.setattr("jusik.development_runner.os.getpgid", lambda _pid: 100_001)
    monkeypatch.setattr(
        "jusik.development_runner._terminate_group", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        "jusik.development_runner.time.monotonic", iter((0.0, 61.0)).__next__
    )
    result = run_once(config)
    assert result.status == "failed"
    assert result.reason == "timeout"
    task = RunnerStore(state / "runner.db", history).task("task-a")
    assert task is not None and task.status == "failed"
    assert _next_task(RunnerStore(state / "runner.db", history)) is None


def test_live_previous_group_fails_closed_before_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    state = tmp_path / "state"
    history = tmp_path / "history"
    store = RunnerStore(state / "runner.db", history)
    store.enqueue("task-a", "entry-amount-distribution", "prompt")
    task = store.task("task-a")
    assert task is not None
    store.claim(task, "attempt-a", tmp_path / "out", tmp_path / "err")
    store.set_process_group("attempt-a", 7777)
    config = RunnerConfig(
        repo=repo,
        state_dir=state,
        history_dir=history,
        history_db=tmp_path / "history.db",
        artifact_dir=tmp_path / "artifact",
        cooldown_seconds=0,
    )
    monkeypatch.setattr(
        "jusik.development_runner._process_group_alive", lambda _group: True
    )
    result = run_once(config)
    assert result.status == "blocked"
    assert store.task("task-a").status == "running"  # type: ignore[union-attr]


def test_competing_lock_does_not_mutate_alternate_state_db(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    state = tmp_path / "state"
    history = tmp_path / "history"
    store = RunnerStore(state / "runner.db", history)
    store.enqueue("task-a", "entry-amount-distribution", "prompt")
    config = RunnerConfig(
        repo=repo,
        state_dir=state,
        history_dir=history,
        history_db=tmp_path / "history.db",
        artifact_dir=tmp_path / "artifact",
    )
    monkeypatch.setattr(
        "jusik.development_runner.fcntl.flock",
        lambda *_args: (_ for _ in ()).throw(BlockingIOError()),
    )
    result = run_once(config)
    assert result.status == "busy"
    task = RunnerStore(state / "runner.db", history).task("task-a")
    assert task is not None and task.status == "queued" and task.attempt_count == 0


def test_history_outbox_retries_without_duplicate_delivery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = RunnerStore(tmp_path / "state" / "runner.db", tmp_path / "history")
    store.add_outbox("event-a", "task-a", "attempt-a", "completed")
    calls: list[str] = []

    class FailingOnce:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            self.failed = False

        def record(self, **kwargs: object) -> None:
            if not self.failed:
                self.failed = True
                raise OSError("temporary journal failure")
            calls.append(str(kwargs["outcome"]))

    fake = FailingOnce()
    monkeypatch.setattr(
        "jusik.development_runner.HistoryRepository", lambda *_args, **_kwargs: fake
    )
    config = RunnerConfig(
        repo=tmp_path,
        state_dir=tmp_path / "state",
        history_dir=tmp_path / "history",
        history_db=tmp_path / "history.db",
        artifact_dir=tmp_path / "artifact",
    )
    _safe_history_flush(store, config)
    assert store.outbox_pending()
    _safe_history_flush(store, config)
    _safe_history_flush(store, config)
    assert store.outbox_pending() == []
    assert calls == ["completed"]


def test_quota_and_cooldown_gate_real_dispatch(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    now = datetime.now(UTC).isoformat()
    quota_state = tmp_path / "quota-state"
    quota_history = tmp_path / "quota-history"
    quota_store = RunnerStore(quota_state / "runner.db", quota_history)
    quota_store.enqueue("task-a", "entry-amount-distribution", "prompt")
    quota_store.record_launch(now)
    quota_config = RunnerConfig(
        repo=repo,
        state_dir=quota_state,
        history_dir=quota_history,
        history_db=tmp_path / "quota.db",
        artifact_dir=tmp_path / "quota-artifact",
        daily_launches=1,
    )
    assert run_once(quota_config).status == "quota"
    assert quota_store.task("task-a").status == "queued"  # type: ignore[union-attr]

    cooldown_state = tmp_path / "cooldown-state"
    cooldown_history = tmp_path / "cooldown-history"
    cooldown_store = RunnerStore(cooldown_state / "runner.db", cooldown_history)
    cooldown_store.enqueue("task-a", "entry-amount-distribution", "prompt")
    cooldown_store.set_meta("last_launch_at", now)
    cooldown_config = RunnerConfig(
        repo=repo,
        state_dir=cooldown_state,
        history_dir=cooldown_history,
        history_db=tmp_path / "cooldown.db",
        artifact_dir=tmp_path / "cooldown-artifact",
        cooldown_seconds=3600,
    )
    assert run_once(cooldown_config).status == "cooldown"
    assert cooldown_store.task("task-a").status == "queued"  # type: ignore[union-attr]


def test_daily_launch_limit_allows_ninth_dispatch_at_limit_24(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    fake = tmp_path / "fake-codex.py"
    fake.write_text(
        """#!/usr/bin/env python3
import json, pathlib, sys
output = pathlib.Path(sys.argv[sys.argv.index('-o') + 1])
output.write_text(json.dumps({
    'task_id': 'task-a',
    'attempt_id': output.parent.name,
    'status': 'blocked',
    'integrated_commit': None,
    'evidence': [],
    'tests_passed': False,
    'review_passed': False,
    'handoff_path': None,
    'blocked_reason': 'test block',
    'followup': None,
}), encoding='utf-8')
""",
        encoding="utf-8",
    )
    fake.chmod(0o700)
    state = tmp_path / "state"
    history = tmp_path / "history"
    artifact = tmp_path / "artifact"
    store = RunnerStore(state / "runner.db", history)
    store.enqueue("task-a", "entry-amount-distribution", "prompt")
    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    old_launches = [
        (today + timedelta(seconds=index)).isoformat() for index in range(8)
    ]
    for launched_at in old_launches:
        store.record_launch(launched_at)
    config = RunnerConfig(
        repo=repo,
        codex=str(fake),
        state_dir=state,
        history_dir=history,
        history_db=tmp_path / "history.db",
        artifact_dir=artifact,
        daily_launches=24,
        cooldown_seconds=0,
    )

    result = run_once(config)

    assert result.status == "blocked"
    assert store.launch_count(today.strftime("%Y-%m-%d")) == 9
    assert store.task("task-a").attempt_count == 1  # type: ignore[union-attr]
    assert store.launch_count("2099-01-01") == 0


def test_daily_launch_limit_blocks_at_limit_24_without_dispatch(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    fake = tmp_path / "must-not-run"
    state = tmp_path / "state"
    history = tmp_path / "history"
    store = RunnerStore(state / "runner.db", history)
    store.enqueue("task-a", "entry-amount-distribution", "prompt")
    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    old_launches = [
        (today + timedelta(seconds=index)).isoformat() for index in range(24)
    ]
    for launched_at in old_launches:
        store.record_launch(launched_at)
    config = RunnerConfig(
        repo=repo,
        codex=str(fake),
        state_dir=state,
        history_dir=history,
        history_db=tmp_path / "history.db",
        artifact_dir=tmp_path / "artifact",
        daily_launches=24,
        cooldown_seconds=0,
    )

    result = run_once(config)

    assert result.status == "quota"
    task = store.task("task-a")
    assert task is not None and task.status == "queued"
    assert task.attempt_count == 0
    assert store.launch_count(today.strftime("%Y-%m-%d")) == 24
    assert not fake.exists()


def test_empty_queue_planner_proposes_then_dispatches_research_child(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    fake = tmp_path / "fake-codex.py"
    evidence = repo / "README.md"
    evidence_hash = hashlib.sha256(evidence.read_bytes()).hexdigest()
    fake.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        "from pathlib import Path\n"
        "args = sys.argv\n"
        "prompt = sys.stdin.read()\n"
        "output = Path(args[args.index('-o') + 1])\n"
        "fields = {}\n"
        "for line in prompt.splitlines():\n"
        "    if ': ' in line:\n"
        "        key, value = line.split(': ', 1)\n"
        "        fields[key] = value\n"
        "if any('planning.schema.json' in arg for arg in args):\n"
        "    payload = {'task_id': fields['Task id'],\n"
        "      'attempt_id': fields['Attempt id'],\n"
        "      'fingerprint': fields['Fingerprint'], 'status': 'proposed',\n"
        "      'proposal': {'id': 'planned-research-v1',\n"
        "       'area': 'portfolio-stress-robustness',\n"
        "       'prompt': ('Objective: compare costs. Scope: current universe. '\n"
        "         'Inputs: existing evidence. Computation cap: small. '\n"
        "         'Tests: deterministic. Stop condition: stop at cap.'),\n"
        f"       'evidence': [{{'path': {str(evidence)!r},\n"
        f"         'sha256': '{evidence_hash}'}}]}},\n"
        "      'wait_reason': None}\n"
        "else:\n"
        "    payload = {'task_id': fields['Task id'],\n"
        "      'attempt_id': fields['Attempt id'],\n"
        "      'status': 'blocked', 'integrated_commit': None, 'evidence': [],\n"
        "      'tests_passed': False, 'review_passed': False, 'handoff_path': None,\n"
        "      'blocked_reason': 'offline fixture', 'followup': None}\n"
        "output.write_text(json.dumps(payload), encoding='utf-8')\n",
        encoding="utf-8",
    )
    fake.chmod(0o700)
    state = tmp_path / "state"
    history = tmp_path / "history"
    config = RunnerConfig(
        repo=repo,
        codex=str(fake),
        state_dir=state,
        history_dir=history,
        history_db=tmp_path / "history.db",
        artifact_dir=tmp_path / "artifact",
        planning_enabled=True,
        daily_launches=24,
        cooldown_seconds=0,
    )

    planned = run_once(config)
    assert planned.status == "completed"
    store = RunnerStore(state / "runner.db", history)
    research = store.task("planned-research-v1")
    assert research is not None and research.status == "queued"
    assert "Follow the repository workflow" in research.prompt
    assert "never use real orders" in research.prompt
    assert "PAPER engine" in research.prompt
    assert "GPU changes" in research.prompt

    dispatched = run_once(config)
    assert dispatched.status == "blocked"
    assert research.id == dispatched.task_id
    assert store.task(research.id).status == "blocked"  # type: ignore[union-attr]
    assert store.launch_count(datetime.now(UTC).strftime("%Y-%m-%d")) == 2


@pytest.mark.parametrize(
    ("gate", "expected_status"),
    [
        ("paused", "paused"),
        ("quota", "quota"),
        ("cooldown", "cooldown"),
        ("dependency", "idle"),
        ("queue_full", "idle"),
        ("live_pgid", "blocked"),
    ],
)
def test_planner_branch_obeys_all_dispatch_gates_without_claiming(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    gate: str,
    expected_status: str,
) -> None:
    repo = _repo(tmp_path)
    state = tmp_path / "state"
    history = tmp_path / "history"
    store = RunnerStore(state / "runner.db", history)
    if gate == "dependency":
        store.enqueue(
            "blocked-child",
            "portfolio-stress-robustness",
            "prompt",
            depends_on="missing",
        )
    elif gate == "queue_full":
        for index in range(8):
            task_id = f"blocked-{index}"
            store.enqueue(task_id, "portfolio-stress-robustness", "prompt")
            task = store.task(task_id)
            assert task is not None
            store.claim(
                task,
                f"attempt-{index}",
                tmp_path / f"out-{index}",
                tmp_path / f"err-{index}",
            )
            store.finish(f"attempt-{index}", task_id, "blocked")
    elif gate == "live_pgid":
        store.enqueue("planner", "portfolio-stress-robustness", "prompt")
        task = store.task("planner")
        assert task is not None
        store.claim(task, "live-attempt", tmp_path / "out", tmp_path / "err")
        store.set_process_group("live-attempt", 7777)
        monkeypatch.setattr(
            "jusik.development_runner._process_group_alive", lambda _: True
        )
    if gate == "paused":
        store.pause()
    elif gate == "quota":
        store.record_launch(datetime.now(UTC).isoformat())
    elif gate == "cooldown":
        store.set_meta("last_launch_at", datetime.now(UTC).isoformat())

    def no_launch(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("planner gate launched a child")

    monkeypatch.setattr("jusik.development_runner.subprocess.Popen", no_launch)
    monkeypatch.setattr(
        "jusik.development_runner._git_common", lambda path: path / ".git"
    )
    monkeypatch.setattr(
        "jusik.development_runner._git",
        lambda *_args, **_kwargs: type("Result", (), {"stdout": "a" * 40})(),
    )
    monkeypatch.setattr("jusik.development_runner._git_ready", lambda _repo: (True, ""))

    def no_claim(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("planner gate claimed a task")

    monkeypatch.setattr(RunnerStore, "claim", no_claim)
    config = RunnerConfig(
        repo=repo,
        codex="must-not-run",
        state_dir=state,
        history_dir=history,
        history_db=tmp_path / "history.db",
        artifact_dir=tmp_path / "artifact",
        planning_enabled=True,
        daily_launches=1 if gate == "quota" else 24,
        cooldown_seconds=3600 if gate == "cooldown" else 0,
    )
    result = run_once(config)
    assert result.status == expected_status
    if gate != "live_pgid":
        assert not any(task.area == PLANNING_AREA for task in store.tasks())
    assert all(
        task.attempt_count == (1 if gate in {"queue_full", "live_pgid"} else 0)
        for task in store.tasks()
    )


@pytest.mark.parametrize("stale_kind", ["snapshot", "fingerprint"])
def test_stale_planning_cannot_enqueue_and_new_research_remains_next(
    tmp_path: Path, stale_kind: str
) -> None:
    store = RunnerStore(tmp_path / "state" / "runner.db", tmp_path / "history")
    store.enqueue("planner", PLANNING_AREA, "internal")
    task = store.task("planner")
    assert task is not None
    store.claim(task, "attempt", tmp_path / "out", tmp_path / "err")
    expected: list[tuple[str, str, str | None]] = []
    if stale_kind == "snapshot":
        store.enqueue("new-research", "portfolio-stress-robustness", "prompt")
    current = "changed" if stale_kind == "fingerprint" else None
    assert not store.finish_planning(
        "attempt",
        "planner",
        "proposed",
        {"status": "proposed"},
        "f" * 64,
        expected,
        current_fingerprint=current,
        proposal=("must-not-enqueue", "portfolio-stress-robustness", "prompt"),
    )
    assert store.task("must-not-enqueue") is None
    assert store.task("planner").status == "failed"  # type: ignore[union-attr]
    assert store.outbox_pending()[-1][3] == "planning_stale"
    if stale_kind == "fingerprint":
        store.enqueue("new-research", "portfolio-stress-robustness", "prompt")
    assert _next_task(store).id == "new-research"  # type: ignore[union-attr]


@pytest.mark.parametrize("action", ["stop", "pause"])
def test_planner_child_interrupt_during_communicate_has_no_proposal(
    tmp_path: Path, action: str
) -> None:
    repo = _repo(tmp_path)
    fake = tmp_path / "sleep-planner.py"
    fake.write_text(
        "#!/usr/bin/env python3\nimport time\ntime.sleep(30)\n", encoding="utf-8"
    )
    fake.chmod(0o700)
    state = tmp_path / "state"
    history = tmp_path / "history"
    config = RunnerConfig(
        repo=repo,
        codex=str(fake),
        state_dir=state,
        history_dir=history,
        history_db=tmp_path / "history.db",
        artifact_dir=tmp_path / "artifact",
        planning_enabled=True,
        daily_launches=24,
        cooldown_seconds=0,
    )
    store = RunnerStore(state / "runner.db", history)
    stop = threading.Event()
    results: list[RunResult] = []
    worker = threading.Thread(
        target=lambda: results.append(run_once(config, stop.is_set))
    )
    worker.start()
    for _ in range(100):
        active = store.active_attempt()
        if active is not None and active.process_group_id is not None:
            break
        time.sleep(0.02)
    if action == "stop":
        stop.set()
    else:
        pause_runner(config)
    worker.join(timeout=10)
    assert not worker.is_alive()
    assert results[0].status in {"interrupted", "paused"}
    planner = next(task for task in store.tasks() if task.area == PLANNING_AREA)
    assert planner.status == "interrupted"
    assert not any(item[3] == "planning_proposed" for item in store.outbox_pending())


def test_planner_child_timeout_has_no_proposal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    fake = tmp_path / "sleep-planner.py"
    fake.write_text(
        "#!/usr/bin/env python3\nimport time\ntime.sleep(30)\n", encoding="utf-8"
    )
    fake.chmod(0o700)
    state = tmp_path / "state"
    history = tmp_path / "history"
    config = RunnerConfig(
        repo=repo,
        codex=str(fake),
        state_dir=state,
        history_dir=history,
        history_db=tmp_path / "history.db",
        artifact_dir=tmp_path / "artifact",
        planning_enabled=True,
        daily_launches=24,
        cooldown_seconds=0,
    )
    monkeypatch.setattr(
        "jusik.development_runner._git_common", lambda path: path / ".git"
    )
    monkeypatch.setattr(
        "jusik.development_runner._git",
        lambda *_args, **_kwargs: type("Result", (), {"stdout": "a" * 40})(),
    )
    monkeypatch.setattr("jusik.development_runner._git_ready", lambda _repo: (True, ""))

    class TimeoutProcess:
        pid = 100_001
        returncode = None

        def poll(self) -> None:
            return None

        def communicate(self, _prompt: bytes, timeout: int) -> None:
            raise subprocess.TimeoutExpired("fake", timeout)

        def wait(self, timeout: int) -> None:
            return None

    monkeypatch.setattr(
        "jusik.development_runner.subprocess.Popen",
        lambda *args, **kwargs: TimeoutProcess(),
    )
    monkeypatch.setattr("jusik.development_runner.os.getpgid", lambda _pid: 100_001)
    monkeypatch.setattr(
        "jusik.development_runner._terminate_group", lambda *args, **kwargs: None
    )
    ticks = iter([0.0, 1_000_000.0])
    monkeypatch.setattr(
        "jusik.development_runner.time.monotonic",
        lambda: next(ticks, 1_000_000.0),
    )
    result = run_once(config)
    store = RunnerStore(state / "runner.db", history)
    assert result.status == "failed" and result.reason == "timeout"
    planner = next(task for task in store.tasks() if task.area == PLANNING_AREA)
    assert planner.status == "failed"
    assert not any(item[3] == "planning_proposed" for item in store.outbox_pending())


def test_pause_and_stop_callback_interrupt_owned_child(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    fake = tmp_path / "sleep-codex.py"
    fake.write_text(
        "#!/usr/bin/env python3\nimport time\ntime.sleep(30)\n", encoding="utf-8"
    )
    fake.chmod(0o700)
    state = tmp_path / "state"
    history = tmp_path / "history"
    store = RunnerStore(state / "runner.db", history)
    store.enqueue("task-a", "entry-amount-distribution", "prompt")
    config = RunnerConfig(
        repo=repo,
        codex=str(fake),
        state_dir=state,
        history_dir=history,
        history_db=tmp_path / "history.db",
        artifact_dir=tmp_path / "artifact",
        cooldown_seconds=0,
    )
    stop = threading.Event()
    result_box: list[RunResult] = []

    def worker() -> None:
        result_box.append(run_once(config, stop.is_set))

    worker_thread = threading.Thread(target=worker)
    worker_thread.start()
    for _ in range(100):
        active = store.active_attempt()
        if active is not None and active.process_group_id is not None:
            break
        time.sleep(0.02)
    stop.set()
    worker_thread.join(timeout=10)
    assert not worker_thread.is_alive()
    assert result_box[0].status == "interrupted"
    assert store.task("task-a").status == "interrupted"  # type: ignore[union-attr]

    assert store.retry("task-a")
    store.resume()
    paused_box: list[RunResult] = []

    def paused_worker() -> None:
        paused_box.append(run_once(config))

    paused_thread = threading.Thread(target=paused_worker)
    paused_thread.start()
    for _ in range(100):
        active = store.active_attempt()
        if active is not None and active.process_group_id is not None:
            break
        time.sleep(0.02)
    pause_runner(config)
    paused_thread.join(timeout=10)
    assert not paused_thread.is_alive()
    assert paused_box[0].status == "paused"
    assert store.task("task-a").status == "interrupted"  # type: ignore[union-attr]
