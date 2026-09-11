"""A bounded, resumable Codex development cycle supervised by systemd."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import signal
import subprocess
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from jusik.development_runner_store import RunnerStore, RunnerTask
from jusik.research_history import HistoryRepository

DEFAULT_CONFIG = Path.home() / ".config/jusik/development-runner.json"
DEFAULT_STATE = Path.home() / ".local/share/jusik/development-runner"
DEFAULT_HISTORY = Path.home() / ".local/share/jusik/research-history"
DEFAULT_HISTORY_DB = Path.home() / ".local/share/jusik/research-history-journal.db"
DEFAULT_ARTIFACTS = Path.home() / ".local/share/jusik/portfolio-audit"
ALLOWED_AREAS = {
    "entry-amount-distribution",
    "preregistration-small-entry",
    "future-observation-protocol",
    "paper-signal-evidence",
    "portfolio-stress-robustness",
}
COMMON_PROMPT = (
    "Follow the repository workflow: explore relevant code and AGENTS.md, write a "
    "bounded plan, assign at most four Luna worktrees, review the implementation, "
    "then Astra merges to local main and runs checks and handoff/web publication "
    "when applicable. Preserve unrelated work and never use real orders, remote "
    "push, PAPER engine or PAPER database mutation, or GPU changes."
)
BACKLOG = (
    (
        "entry-amount-distribution",
        "entry-amount-distribution-v1",
        "Analyze the existing entry amount distribution and produce a small, "
        "auditable report with evidence and stop conditions. Do not implement a "
        "trading constraint in this first task.",
    ),
    (
        "preregistration-small-entry",
        "preregistration-small-entry-v1",
        "Review the preregistered small-entry constraint after the first task. If "
        "its dependency is not verified, record blocked evidence instead of "
        "fabricating completion.",
    ),
    (
        "future-observation-protocol",
        "future-observation-protocol-v1",
        "Design a separate future observation protocol for this research area. Keep "
        "retrospective data separate and define what data is still unavailable.",
    ),
    (
        "paper-signal-evidence",
        "paper-signal-evidence-v1",
        "Collect read-only real-time PAPER signal evidence and its provenance. Do "
        "not submit orders and preserve the paper/live boundary.",
    ),
    (
        "portfolio-stress-robustness",
        "portfolio-stress-robustness-v1",
        "Run a bounded portfolio stress robustness review using existing offline "
        "seams. Report missing future data as blocked and do not alter the trading "
        "engine.",
    ),
)


class RunnerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    repo: Path
    codex: str = "codex"
    state_dir: Path = DEFAULT_STATE
    history_dir: Path = DEFAULT_HISTORY
    history_db: Path = DEFAULT_HISTORY_DB
    artifact_dir: Path = DEFAULT_ARTIFACTS
    timeout_seconds: int = Field(default=5400, ge=60, le=5400)
    daily_launches: int = Field(default=8, ge=1, le=8)
    cooldown_seconds: int = Field(default=60, ge=0, le=86400)


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class Followup(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,100}$")
    area: str
    prompt: str = Field(min_length=1, max_length=2000)


class Completion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    task_id: str
    attempt_id: str
    status: Literal["completed", "blocked"]
    integrated_commit: str | None = Field(default=None, pattern=r"^[a-f0-9]{7,64}$")
    evidence: list[Evidence] = Field(default_factory=list, max_length=20)
    tests_passed: bool
    review_passed: bool
    handoff_path: str | None = Field(default=None, min_length=1)
    blocked_reason: str | None = Field(default=None, min_length=1, max_length=2000)
    followup: Followup | None = None


COMPLETION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "task_id",
        "attempt_id",
        "status",
        "integrated_commit",
        "evidence",
        "tests_passed",
        "review_passed",
        "handoff_path",
        "blocked_reason",
        "followup",
    ],
    "properties": {
        "task_id": {"type": "string"},
        "attempt_id": {"type": "string"},
        "status": {"type": "string", "enum": ["completed", "blocked"]},
        "integrated_commit": {
            "type": ["string", "null"],
            "pattern": "^[a-f0-9]{7,64}$",
        },
        "evidence": {
            "type": "array",
            "maxItems": 20,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["path", "sha256"],
                "properties": {
                    "path": {"type": "string"},
                    "sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
                },
            },
        },
        "tests_passed": {"type": "boolean"},
        "review_passed": {"type": "boolean"},
        "handoff_path": {"type": ["string", "null"]},
        "blocked_reason": {"type": ["string", "null"], "maxLength": 2000},
        "followup": {
            "type": ["object", "null"],
            "additionalProperties": False,
            "required": ["id", "area", "prompt"],
            "properties": {
                "id": {"type": "string", "pattern": "^[a-z0-9][a-z0-9-]{2,100}$"},
                "area": {"type": "string", "enum": sorted(ALLOWED_AREAS)},
                "prompt": {"type": "string", "minLength": 1, "maxLength": 2000},
            },
        },
    },
}


@dataclass(frozen=True)
class RunResult:
    status: str
    task_id: str | None = None
    attempt_id: str | None = None
    reason: str | None = None


def _secure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    path.chmod(0o700)


def _write_private(path: Path, content: bytes) -> None:
    _secure_dir(path.parent)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(content)
    finally:
        path.chmod(0o600)


def load_config(path: Path = DEFAULT_CONFIG) -> RunnerConfig:
    return RunnerConfig.model_validate_json(path.read_text(encoding="utf-8"))


def save_config(config: RunnerConfig, path: Path) -> None:
    _secure_dir(path.parent)
    _write_private(path, (config.model_dump_json(indent=2) + "\n").encode())


def init_config(
    path: Path,
    repo: Path,
    state: Path,
    history: Path | None,
    history_db: Path | None,
    artifact_dir: Path | None = None,
) -> RunnerConfig:
    state = state.expanduser().resolve()
    history_dir = (history or DEFAULT_HISTORY).expanduser().resolve()
    config = RunnerConfig(
        repo=repo.expanduser().resolve(),
        state_dir=state,
        history_dir=history_dir,
        history_db=(history_db or DEFAULT_HISTORY_DB).expanduser().resolve(),
        artifact_dir=(artifact_dir or DEFAULT_ARTIFACTS).expanduser().resolve(),
    )
    save_config(config, path.expanduser().resolve())
    store = RunnerStore(config.state_dir / "runner.db", config.history_dir)
    for area, task_id, prompt in BACKLOG:
        dependency = (
            "entry-amount-distribution-v1"
            if task_id == "preregistration-small-entry-v1"
            else None
        )
        store.enqueue(
            task_id,
            area,
            f"{COMMON_PROMPT}\n\nResearch area: {area}\n\n{prompt}",
            dependency,
        )
    return config


def _git(
    repo: Path, *args: str, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        capture_output=True,
        check=check,
        timeout=30,
    )


def _git_ready(repo: Path) -> tuple[bool, str]:
    branch = _git(repo, "branch", "--show-current").stdout.strip()
    if branch != "main":
        return False, "main branch required"
    status = _git(repo, "status", "--porcelain").stdout.splitlines()
    unsafe = [
        line
        for line in status
        if not (line.startswith("?? ") and Path(line[3:]).name == "HANDOFF.md")
    ]
    return (not unsafe, "tracked worktree is dirty" if unsafe else "")


def _git_common(repo: Path) -> Path:
    common = _git(repo, "rev-parse", "--git-common-dir").stdout.strip()
    path = Path(common)
    return path if path.is_absolute() else (repo / path).resolve()


def _allowed_path(path: Path, roots: list[Path]) -> bool:
    resolved = path.expanduser().resolve()
    return any(resolved == root or root in resolved.parents for root in roots)


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_completion(
    payload: Any, task: RunnerTask, attempt_id: str, config: RunnerConfig
) -> Completion:
    try:
        completion = Completion.model_validate(payload)
    except ValidationError as exc:
        raise ValueError("completion schema invalid") from exc
    if completion.task_id != task.id or completion.attempt_id != attempt_id:
        raise ValueError("completion identity mismatch")
    if completion.status == "blocked":
        if not completion.blocked_reason or completion.followup is not None:
            raise ValueError("blocked completion needs a reason and no followup")
        return completion
    if not completion.tests_passed or not completion.review_passed:
        raise ValueError("independent checks are not reported passed")
    if completion.integrated_commit is None or not completion.evidence:
        raise ValueError("completed result is missing commit or evidence")
    if not re.search(r"^[a-f0-9]{7,64}$", completion.integrated_commit):
        raise ValueError("invalid integrated commit")
    commit = _git(
        config.repo, "cat-file", "-t", completion.integrated_commit, check=False
    )
    if commit.returncode != 0 or commit.stdout.strip() != "commit":
        raise ValueError("integrated commit does not exist")
    ancestor = _git(
        config.repo,
        "merge-base",
        "--is-ancestor",
        completion.integrated_commit,
        "main",
        check=False,
    )
    if ancestor.returncode != 0:
        raise ValueError("integrated commit is not an ancestor of main")
    roots = [
        config.repo,
        config.repo.parent,
        config.state_dir,
        config.history_dir,
        config.artifact_dir,
    ]
    for evidence in completion.evidence:
        path = Path(evidence.path)
        if (
            not _allowed_path(path, roots)
            or not path.is_file()
            or path.is_symlink()
            or _hash_file(path) != evidence.sha256
        ):
            raise ValueError("evidence path or hash invalid")
    if completion.handoff_path is None:
        raise ValueError("completed result is missing handoff")
    handoff = Path(completion.handoff_path)
    if (
        not _allowed_path(handoff, roots)
        or not handoff.is_file()
        or handoff.is_symlink()
    ):
        raise ValueError("handoff path invalid")
    if (
        completion.followup is not None
        and completion.followup.area not in ALLOWED_AREAS
    ):
        raise ValueError("followup area is not allowed")
    return completion


def _next_task(store: RunnerStore) -> RunnerTask | None:
    now = datetime.now(UTC)
    for task in store.tasks():
        if task.status != "queued":
            continue
        if task.depends_on is not None:
            dependency = store.task(task.depends_on)
            if dependency is None or dependency.status not in {"completed", "blocked"}:
                continue
        if task.next_allowed_at and datetime.fromisoformat(task.next_allowed_at) > now:
            continue
        return task
    return None


def _history_flush(store: RunnerStore, config: RunnerConfig) -> None:
    repository = HistoryRepository(config.history_dir, config.history_db)
    for identity, task_id, attempt_id, outcome in store.outbox_pending():
        repository.record(
            identity=identity,
            title="자동 개발 실행기",
            summary="개발 cycle 상태가 기록되었습니다.",
            category="development",
            outcome=outcome,
            run_ids=[task_id, attempt_id],
        )
        store.mark_outbox_delivered(identity)


def _safe_history_flush(store: RunnerStore, config: RunnerConfig) -> None:
    """Best-effort delivery; the durable outbox remains on journal failure."""
    try:
        _history_flush(store, config)
    except Exception:
        return


def _record_control_event(
    store: RunnerStore, config: RunnerConfig, outcome: str
) -> None:
    identity = f"development-runner:control:{outcome}"
    store.add_outbox(identity, "runner-control", "runner-control", outcome)
    _safe_history_flush(store, config)


def _terminate_group(group_id: int | None, force: bool = False) -> None:
    if group_id is None or group_id <= 1 or group_id == os.getpgrp():
        return
    try:
        os.killpg(group_id, signal.SIGKILL if force else signal.SIGTERM)
    except (PermissionError, ProcessLookupError):
        pass


def _stop_process(process: subprocess.Popen[bytes]) -> None:
    """Stop only the process group owned by this live attempt."""
    if process.poll() is not None:
        return
    try:
        group_id = os.getpgid(process.pid)
    except ProcessLookupError:
        return
    if group_id != process.pid or process.poll() is not None:
        return
    _terminate_group(group_id)
    try:
        process.wait(timeout=30)
    except subprocess.TimeoutExpired:
        _terminate_group(group_id, force=True)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            return


def _process_group_alive(group_id: int | None) -> bool:
    """Conservatively detect an orphaned prior child before recovery."""
    if group_id is None or group_id <= 1 or group_id == os.getpgrp():
        return False
    try:
        os.killpg(group_id, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def pause_runner(config: RunnerConfig) -> None:
    store = RunnerStore(config.state_dir / "runner.db", config.history_dir)
    store.pause()
    _record_control_event(store, config, "paused")


def resume_runner(config: RunnerConfig) -> None:
    store = RunnerStore(config.state_dir / "runner.db", config.history_dir)
    store.resume()
    _record_control_event(store, config, "resumed")


def run_once(
    config: RunnerConfig, stop_requested: Callable[[], bool] | None = None
) -> RunResult:
    common = _git_common(config.repo)
    lock_path = common / "development-runner.lock"
    with lock_path.open("a+") as lock:
        lock_path.chmod(0o600)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return RunResult("busy")
        store = RunnerStore(config.state_dir / "runner.db", config.history_dir)
        active = store.active_attempt()
        if active is not None and _process_group_alive(active.process_group_id):
            return RunResult(
                "blocked",
                active.task_id,
                active.id,
                "previous attempt process group is still alive",
            )
        _safe_history_flush(store, config)
        interrupted = store.recover_running()
        if interrupted:
            _safe_history_flush(store, config)
        if store.is_paused():
            return RunResult("paused")
        ready, reason = _git_ready(config.repo)
        if not ready:
            return RunResult("blocked", reason=reason)
        now = datetime.now(UTC)
        if store.launch_count(now.strftime("%Y-%m-%d")) >= config.daily_launches:
            _record_control_event(store, config, "quota")
            return RunResult("quota")
        latest = store.get_meta("last_launch_at")
        if latest and now - datetime.fromisoformat(latest) < timedelta(
            seconds=config.cooldown_seconds
        ):
            return RunResult("cooldown")
        task = _next_task(store)
        if task is None:
            return RunResult("idle")
        attempt_id = uuid.uuid4().hex
        attempt_dir = config.state_dir / "attempts" / attempt_id
        _secure_dir(attempt_dir)
        output_path = attempt_dir / "completion.json"
        stderr_path = attempt_dir / "stderr.log"
        stdout_path = attempt_dir / "stdout.jsonl"
        previous = task.last_attempt_id or "none"
        prompt = (
            f"Task id: {task.id}\nAttempt id: {attempt_id}\n"
            f"Previous attempt id: {previous}\n\n{task.prompt}\n\n"
            "Return the required completion JSON to the output path supplied by "
            "the CLI. Use the exact task and attempt ids, include SHA-256 evidence "
            "paths under the allowed roots, "
            "and report tests_passed, review_passed, integrated_commit, and "
            "handoff_path."
        )
        _write_private(attempt_dir / "prompt.txt", prompt.encode())
        _write_private(stdout_path, b"")
        store.claim(task, attempt_id, output_path, stderr_path, now.isoformat())
        _safe_history_flush(store, config)
        schema_path = attempt_dir / "completion.schema.json"
        _write_private(
            schema_path, (json.dumps(COMPLETION_SCHEMA, sort_keys=True) + "\n").encode()
        )
        command = [
            config.codex,
            "-a",
            "never",
            "exec",
            "-m",
            "gpt-6-astra",
            "-s",
            "workspace-write",
            "--add-dir",
            str(config.repo.parent),
            "--add-dir",
            str(config.state_dir),
            "--add-dir",
            str(config.history_dir),
            "--add-dir",
            str(config.history_dir.parent),
            "--add-dir",
            str(config.artifact_dir),
            "-c",
            "sandbox_workspace_write.network_access=true",
            "--json",
            "--output-schema",
            str(schema_path),
            "-o",
            str(output_path),
            "-C",
            str(config.repo),
        ]
        with (
            stderr_path.open("wb") as stderr,
            stdout_path.open("ab") as stdout,
        ):
            try:
                process = subprocess.Popen(
                    command,
                    cwd=config.repo,
                    stdin=subprocess.PIPE,
                    stdout=stdout,
                    stderr=stderr,
                    start_new_session=True,
                )
            except OSError:
                store.finish(
                    attempt_id, task.id, "failed", failure_code="dispatch_error"
                )
                _safe_history_flush(store, config)
                return RunResult("failed", task.id, attempt_id, "dispatch_error")
            try:
                process_group_id = os.getpgid(process.pid)
            except ProcessLookupError:
                process_group_id = None
            if process_group_id is not None:
                store.set_process_group(attempt_id, process_group_id)
            deadline = time.monotonic() + config.timeout_seconds
            input_payload: bytes | None = prompt.encode()
            while True:
                if store.is_paused() or (
                    stop_requested is not None and stop_requested()
                ):
                    _stop_process(process)
                    store.finish(
                        attempt_id,
                        task.id,
                        "interrupted",
                        failure_code="paused" if store.is_paused() else "signal",
                    )
                    _safe_history_flush(store, config)
                    return RunResult(
                        "paused" if store.is_paused() else "interrupted",
                        task.id,
                        attempt_id,
                    )
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    _stop_process(process)
                    store.finish(attempt_id, task.id, "failed", failure_code="timeout")
                    _safe_history_flush(store, config)
                    return RunResult("failed", task.id, attempt_id, "timeout")
                try:
                    process.communicate(input_payload, timeout=min(1, remaining))
                    input_payload = None
                except subprocess.TimeoutExpired:
                    input_payload = None
                    continue
                break
        if store.is_paused() or (stop_requested is not None and stop_requested()):
            store.finish(
                attempt_id,
                task.id,
                "interrupted",
                failure_code="paused" if store.is_paused() else "signal",
            )
            _safe_history_flush(store, config)
            return RunResult(
                "paused" if store.is_paused() else "interrupted",
                task.id,
                attempt_id,
            )
        if process.returncode != 0:
            store.finish(attempt_id, task.id, "failed", failure_code="codex_exit")
            _safe_history_flush(store, config)
            return RunResult("failed", task.id, attempt_id, "codex_exit")
        try:
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            completion = validate_completion(payload, task, attempt_id, config)
        except (OSError, json.JSONDecodeError, ValueError):
            store.finish(
                attempt_id, task.id, "failed", failure_code="completion_invalid"
            )
            _safe_history_flush(store, config)
            return RunResult("failed", task.id, attempt_id, "completion_invalid")
        post_ready, post_reason = _git_ready(config.repo)
        if not post_ready:
            store.finish(attempt_id, task.id, "failed", failure_code="postcheck_dirty")
            _safe_history_flush(store, config)
            return RunResult("failed", task.id, attempt_id, post_reason)
        if completion.status == "blocked":
            store.finish(
                attempt_id, task.id, "blocked", evidence=completion.model_dump()
            )
            _safe_history_flush(store, config)
            return RunResult("blocked", task.id, attempt_id, completion.blocked_reason)
        store.finish(attempt_id, task.id, "completed", evidence=completion.model_dump())
        if completion.followup is not None:
            pending = [
                item
                for item in store.tasks()
                if item.status not in {"completed", "failed"}
            ]
            if len(pending) < 8:
                store.enqueue(
                    completion.followup.id,
                    completion.followup.area,
                    f"{COMMON_PROMPT}\n\n{completion.followup.prompt}",
                )
        _safe_history_flush(store, config)
        return RunResult("completed", task.id, attempt_id)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    init.add_argument("--repo", type=Path, required=True)
    init.add_argument("--state-dir", type=Path, default=DEFAULT_STATE)
    init.add_argument("--history-dir", type=Path)
    init.add_argument("--history-db", type=Path)
    init.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACTS)
    for name in ("status", "run-once", "pause", "resume"):
        command = sub.add_parser(name)
        command.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    enqueue = sub.add_parser("enqueue")
    enqueue.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    enqueue.add_argument("--id", required=True)
    enqueue.add_argument("--area", required=True, choices=sorted(ALLOWED_AREAS))
    enqueue.add_argument("--prompt", required=True)
    retry = sub.add_parser("retry")
    retry.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    retry.add_argument("task_id")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "init":
        config = init_config(
            args.config,
            args.repo,
            args.state_dir,
            args.history_dir,
            args.history_db,
            args.artifact_dir,
        )
        print(
            json.dumps(
                {"status": "initialized", "tasks": len(BACKLOG)}, ensure_ascii=False
            )
        )
        return 0
    config = load_config(args.config)
    store = RunnerStore(config.state_dir / "runner.db", config.history_dir)
    if args.command == "status":
        print(
            json.dumps(
                {
                    "paused": store.is_paused(),
                    "tasks": [asdict(task) for task in store.tasks()],
                },
                ensure_ascii=False,
            )
        )
        return 0
    if args.command == "enqueue":
        print(
            json.dumps(
                {"enqueued": store.enqueue(args.id, args.area, args.prompt)},
                ensure_ascii=False,
            )
        )
        return 0
    if args.command == "retry":
        print(json.dumps({"retried": store.retry(args.task_id)}, ensure_ascii=False))
        return 0
    if args.command == "pause":
        pause_runner(config)
        print(json.dumps({"status": "paused"}, ensure_ascii=False))
        return 0
    if args.command == "resume":
        resume_runner(config)
        print(json.dumps({"status": "resumed"}, ensure_ascii=False))
        return 0
    stop_event = threading.Event()

    def request_stop(_signum: int, _frame: Any) -> None:
        stop_event.set()

    previous_term = signal.signal(signal.SIGTERM, request_stop)
    previous_int = signal.signal(signal.SIGINT, request_stop)
    try:
        result = run_once(config, stop_event.is_set)
    finally:
        signal.signal(signal.SIGTERM, previous_term)
        signal.signal(signal.SIGINT, previous_int)
    print(json.dumps(asdict(result), ensure_ascii=False))
    return (
        0
        if result.status in {"completed", "idle", "paused", "quota", "cooldown", "busy"}
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
