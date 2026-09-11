from __future__ import annotations

import hashlib
import subprocess
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest

from jusik.development_runner import (
    RunnerConfig,
    _next_task,
    _safe_history_flush,
    init_config,
    pause_runner,
    run_once,
    validate_completion,
)
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
    assert store.outbox_pending()[0][3] == "interrupted"
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
    assert validate_completion(payload, task, "attempt-a", config).task_id == task.id
    payload["evidence"][0]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="evidence"):
        validate_completion(payload, task, "attempt-a", config)


def test_validate_completion_allows_explicit_blocked_result(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    config = RunnerConfig(repo=repo, state_dir=tmp_path / "state")
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


def test_config_rejects_unbounded_launch_settings(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        RunnerConfig(repo=tmp_path, daily_launches=9)


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
        cooldown_seconds=3600,
    )
    assert run_once(cooldown_config).status == "cooldown"
    assert cooldown_store.task("task-a").status == "queued"  # type: ignore[union-attr]


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
        cooldown_seconds=0,
    )
    stop = threading.Event()
    result_box: list[object] = []

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
    assert result_box[0].status == "interrupted"  # type: ignore[union-attr]
    assert store.task("task-a").status == "interrupted"  # type: ignore[union-attr]

    assert store.retry("task-a")
    store.resume()
    paused_box: list[object] = []

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
    assert paused_box[0].status == "paused"  # type: ignore[union-attr]
    assert store.task("task-a").status == "interrupted"  # type: ignore[union-attr]
