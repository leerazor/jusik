"""A bounded, resumable Codex development cycle supervised by systemd."""

from __future__ import annotations

import argparse
import copy
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

from jusik.development_runner_contract import (
    ENGINEERING_OWNED_PATHS,
    ENGINEERING_SPEC_AREA,
    ENGINEERING_SPEC_ID,
    ENGINEERING_SPEC_PROMPT,
    Blocker,
    unknown_blocker,
)
from jusik.development_runner_planning import (
    PLANNING_AREA,
    PLANNING_SCHEMA,
    planner_task_id,
    validate_planning_result,
)
from jusik.development_runner_planning import (
    fingerprint as planning_fingerprint,
)
from jusik.development_runner_roadmap import (
    DEVELOPMENT_DELIVERY_POLICY,
    ROADMAP_SCOPE,
    Roadmap,
    RoadmapError,
    eligible_areas,
    load_roadmap,
    reserved_areas,
    roadmap_fingerprint,
    roadmap_planner_context,
    roadmap_prompt,
    validate_enqueue,
    validate_planner_area,
    validate_roadmap_completion,
)
from jusik.development_runner_store import RunnerStore, RunnerTask
from jusik.research_history import HistoryRepository
from jusik.research_mandate_governance import (
    MandateGovernanceError,
    ValidatedMandate,
    validate_dispatch_gate,
)

DEFAULT_CONFIG = Path.home() / ".config/jusik/development-runner.json"
DEFAULT_STATE = Path.home() / ".local/share/jusik/development-runner"
DEFAULT_HISTORY = Path.home() / ".local/share/jusik/research-history"
DEFAULT_HISTORY_DB = Path.home() / ".local/share/jusik/research-history-journal.db"
DEFAULT_ARTIFACTS = Path.home() / ".local/share/jusik/portfolio-audit"


class RunnerResumeError(RuntimeError):
    """Raised when a private operator hold still suppresses queue mutations."""


ALLOWED_AREAS = {
    "entry-amount-distribution",
    "preregistration-small-entry",
    "future-observation-protocol",
    "paper-signal-evidence",
    "portfolio-stress-robustness",
}
RESEARCH_MANDATE_REQUIRED_FIELDS = frozenset(
    {
        "recorded_at",
        "capital_krw",
        "maximum_drawdown_fraction",
        "drawdown_reference",
        "research_universe_expansion",
        "interim_withdrawals",
        "investment_horizon",
        "historical_lookback_years",
        "leveraged_allocation_fraction",
        "turnover_preference",
        "signal_detection",
        "live_trading",
        "frozen_paper_contract",
        "user_answers",
    }
)
COMMON_PROMPT = (
    "Follow the repository workflow: explore relevant code and AGENTS.md, write a "
    "bounded plan, use at most four active agents including the planner and at most "
    "three workers, assign one Sol or Luna owner per worktree, and have an "
    "independent Sol-based "
    "reviewer inspect the implementation, then have the Sol-based supervisor "
    "integrate it to local main and run checks and "
    "handoff/web publication when applicable. Astra is read-only escalation for one "
    "unresolved critical diagnosis only; it is not an automatic model switch. For an "
    "explicitly complex financial calculation, future-leakage, or design-conflict "
    "issue, the supervisor may choose one initial Astra diagnosis with bounded "
    "evidence; otherwise, after two distinct failed code hypotheses, provide bounded "
    "evidence to Astra. "
    "When "
    "external evidence is missing, use a source alternative or independent task "
    "instead of repeating escalation. Preserve unrelated work and never use real "
    "orders, remote "
    "push, PAPER engine or PAPER database mutation, arbitrary service changes, "
    "or unapproved GPU changes. GPU use is opt-in and on-demand only: for portfolio "
    "stress work use "
    "python -m jusik.research_portfolio_gpu_stress --request PATH --output-dir PATH "
    "--device auto|cpu|cuda with pinned input, seed, bounds, and CPU parity; "
    "never promote approximate stress results."
)
RUNTIME_PROMPT_SUFFIX = (
    "Before removing any merged worktree after integration checks, archive all "
    "needed evidence, its SHA-256 hashes, and the handoff in durable files under "
    "the allowed roots. The completion JSON must reference only files that survive "
    "worktree cleanup. For role routing, read docs/agent-tooling.md and use the "
    "model-only adapter in backend/jusik/agent_routing.py when the actual spawn "
    "tool has no role field; missing agent_type alone is not a halt condition. "
    "On retry, inspect the prior task registry, owned worktree, and artifacts, "
    "then reuse a matching owned branch rather than duplicating, resetting, or "
    "deleting it. Automatic recovery is bounded: use recovery_kind=environment "
    "only with one exact label from dependency_setup, cache_permission, "
    "tool_unavailable, or recovery_kind=implementation only with "
    "one exact blocked label from code_defect, test_defect, lint_defect, "
    "type_defect, actionable_review. These labels cover known in-scope code, "
    "test, lint, type, or actionable review defects only. Missing data, financial "
    "policy choices, SHA or identity mismatch, unknown security issues, permission "
    "expansion, raw Codex exits, interruption, and generic review failure are not "
    "automatic recovery reasons. A retry must freshly pass the configured tests "
    "and independent review; it never bypasses a gate or claims success. Repair an "
    "owned virtual environment or attempt cache only as a routine local fix: run "
    "the owned environment's python --version once before checks and stop the "
    "attempt if setup fails instead of batching past the failed setup. A previous "
    "attempt stop is historical state, not a permanent current block. "
    "Never call collaboration.wait when no receiver agent is present or when the "
    "receiver list is empty: return a finite review-unavailable result with evidence "
    "and stop. A runner child must not call collaboration.spawn_agent: the runner "
    "does not provision receiver agents for that child. A child self-review is not "
    "independent review; do not report review_passed without independent evidence. "
    "Do not leave the task in an unbounded wait state. When reporting a blocked "
    "completion for missing evidence, set followup to null; followup is reserved "
    "for completed results that enqueue a separately validated task."
    f" {DEVELOPMENT_DELIVERY_POLICY}"
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
    idle_timeout_seconds: int = Field(default=900, ge=60, le=5400)
    daily_launches: int | None = Field(default=8, ge=1, le=24)
    cooldown_seconds: int = Field(default=60, ge=0, le=86400)
    planning_enabled: bool = False
    automatic_recovery: bool = False
    scope: Literal["research", "investment-roadmap"] = "research"


def _child_idle_expired(
    stdout_path: Path, stderr_path: Path, started_at: float, timeout_seconds: int
) -> bool:
    """Fail closed when a child produces no observable output for too long."""
    try:
        latest = max(stdout_path.stat().st_mtime, stderr_path.stat().st_mtime)
    except OSError:
        latest = started_at
    return time.time() - max(started_at, latest) >= timeout_seconds


def _empty_receiver_wait_detected(stdout_path: Path) -> bool:
    """Detect a child blocked in collaboration.wait with no receiver agent."""

    try:
        with stdout_path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            handle.seek(max(0, handle.tell() - 131_072))
            tail = handle.read().decode("utf-8", errors="ignore")
    except OSError:
        return False
    return '"tool":"wait"' in tail and '"receiver_thread_ids":[]' in tail


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
    status: Literal["completed", "blocked", "waiting_external", "waiting_human"]
    integrated_commit: str | None = Field(default=None, pattern=r"^[a-f0-9]{7,64}$")
    evidence: list[Evidence] = Field(default_factory=list, max_length=20)
    tests_passed: bool
    review_passed: bool
    handoff_path: str | None = Field(default=None, min_length=1)
    blocked_reason: str | None = Field(default=None, min_length=1, max_length=2000)
    followup: Followup | None = None
    recovery_kind: Literal["environment", "implementation"] | None = None
    blocker: Blocker | None = None
    engineering_status: Literal["ENGINEERING_COMPLETE"] | None = None
    investment_status: Literal["NOT_EVALUATED"] | None = None


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
        "recovery_kind",
        "blocker",
        "engineering_status",
        "investment_status",
    ],
    "properties": {
        "task_id": {"type": "string"},
        "attempt_id": {"type": "string"},
        "status": {
            "type": "string",
            "enum": ["completed", "blocked", "waiting_external", "waiting_human"],
        },
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
        "recovery_kind": {
            "type": ["string", "null"],
            "enum": ["environment", "implementation", None],
        },
        "blocker": {
            "type": ["object", "null"],
            "additionalProperties": False,
            "required": [
                "blocker_reason",
                "attempted_actions",
                "dependency",
                "dependency_identity",
                "resume_condition",
                "retry_policy",
                "next_eligible_retry",
                "alternative_ready_tasks",
            ],
            "properties": {
                "blocker_reason": {"type": "string", "minLength": 1, "maxLength": 2000},
                "attempted_actions": {"type": "array", "items": {"type": "string"}},
                "dependency": {"type": ["string", "null"]},
                "dependency_identity": {"type": ["string", "null"]},
                "resume_condition": {"type": "string", "minLength": 1},
                "retry_policy": {
                    "type": "string",
                    "enum": ["none", "manual", "event", "bounded"],
                },
                "next_eligible_retry": {"type": ["string", "null"]},
                "alternative_ready_tasks": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
        },
        "engineering_status": {
            "type": ["string", "null"],
            "enum": ["ENGINEERING_COMPLETE", None],
        },
        "investment_status": {
            "type": ["string", "null"],
            "enum": ["NOT_EVALUATED", None],
        },
    },
}


def _completion_schema(
    allowed_areas: set[str], *, engineering: bool = False
) -> dict[str, Any]:
    schema = copy.deepcopy(COMPLETION_SCHEMA)
    # The Codex JSON-schema contract requires every declared key, including
    # nullable fields, for both investment and engineering completions.
    followup = schema["properties"]["followup"]
    if isinstance(followup, dict) and isinstance(followup.get("properties"), dict):
        area = followup["properties"].get("area")
        if isinstance(area, dict):
            area["enum"] = sorted(allowed_areas)
    return schema


def _planning_schema(allowed_areas: set[str]) -> dict[str, Any]:
    schema = copy.deepcopy(PLANNING_SCHEMA)
    proposal = schema["properties"]["proposal"]
    if isinstance(proposal, dict) and isinstance(proposal.get("properties"), dict):
        area = proposal["properties"].get("area")
        if isinstance(area, dict):
            area["enum"] = sorted(allowed_areas)
    return schema


@dataclass(frozen=True)
class RunResult:
    status: str
    task_id: str | None = None
    attempt_id: str | None = None
    reason: str | None = None


def _secure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    path.chmod(0o700)


def _prepare_artifact_dir(path: Path) -> Path:
    try:
        resolved = path.expanduser().resolve()
    except (OSError, RuntimeError) as exc:
        raise OSError("artifact directory is not usable") from exc
    resolved.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not resolved.is_dir() or not os.access(resolved, os.W_OK):
        raise OSError("artifact directory is not writable")
    return resolved


def _write_private(path: Path, content: bytes) -> None:
    _secure_dir(path.parent)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(content)
    finally:
        path.chmod(0o600)


def _write_exit_diagnostics(
    attempt_dir: Path, returncode: int, completion_path: Path
) -> None:
    payload = {
        "returncode": returncode,
        "signal_number": -returncode if returncode < 0 else None,
        "completion_present": completion_path.exists(),
    }
    _write_private(
        attempt_dir / "exit-diagnostics.json",
        (json.dumps(payload, sort_keys=True) + "\n").encode(),
    )


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
    scope: Literal["research", "investment-roadmap"] = "research",
) -> RunnerConfig:
    state = state.expanduser().resolve()
    if scope == ROADMAP_SCOPE:
        if state == DEFAULT_STATE.resolve():
            raise ValueError("investment roadmap requires a dedicated state directory")
        if (state / "runner.db").exists():
            raise ValueError("investment roadmap state must be a new blank database")
    history_dir = (history or DEFAULT_HISTORY).expanduser().resolve()
    config = RunnerConfig(
        repo=repo.expanduser().resolve(),
        state_dir=state,
        history_dir=history_dir,
        history_db=(history_db or DEFAULT_HISTORY_DB).expanduser().resolve(),
        artifact_dir=(artifact_dir or DEFAULT_ARTIFACTS).expanduser().resolve(),
        scope=scope,
    )
    store = RunnerStore(config.state_dir / "runner.db", config.history_dir)
    existing_scope = store.get_meta("scope")
    if existing_scope is not None and existing_scope != scope:
        raise ValueError("runner state scope mismatch")
    save_config(config, path.expanduser().resolve())
    store.set_meta("scope", scope)
    if scope == "research":
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
    return (path if path.is_absolute() else (repo.resolve() / path)).resolve()


def _codex_workspace_roots(config: RunnerConfig) -> list[Path]:
    candidates = (
        config.repo.parent,
        config.state_dir,
        config.history_dir,
        config.history_dir.parent,
        config.artifact_dir,
    )
    roots: list[Path] = []
    for candidate in candidates:
        resolved = candidate.expanduser().resolve()
        if resolved.is_dir() and os.access(resolved, os.W_OK) and resolved not in roots:
            roots.append(resolved)
    return roots


def _codex_command(
    config: RunnerConfig,
    common: Path,
    schema_path: Path,
    output_path: Path,
    *,
    planning: bool = False,
) -> list[str]:
    if planning:
        profile = (
            'permissions.jusik-planning={extends=":read-only",'
            f'filesystem={{{json.dumps(str(output_path.parent.resolve()))}="write"}},'
            "network={enabled=false}}"
        )
        permission = "jusik-planning"
    else:
        filesystem = f'{json.dumps(str(common))}="write"'
        workspace_roots = ",".join(
            f"{json.dumps(str(root))}=true" for root in _codex_workspace_roots(config)
        )
        profile = (
            "permissions.jusik-development={"
            'extends=":workspace",'
            f"filesystem={{{filesystem}}},"
            f"workspace_roots={{{workspace_roots}}},"
            "network={enabled=true}"
            "}"
        )
        permission = "jusik-development"
    return [
        config.codex,
        "-a",
        "never",
        "exec",
        "--ignore-user-config",
        "-m",
        "gpt-6-sol",
        "-c",
        f'default_permissions="{permission}"',
        "-c",
        profile,
        "-c",
        'model_reasoning_effort="medium"',
        "--json",
        "--output-schema",
        str(schema_path),
        "-o",
        str(output_path),
        "-C",
        str(config.repo),
    ]


def _allowed_path(path: Path, roots: list[Path]) -> bool:
    resolved = path.expanduser().resolve()
    return any(resolved == root or root in resolved.parents for root in roots)


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bind_event_dependency(blocker: Blocker, config: RunnerConfig) -> Blocker:
    if blocker.retry_policy != "event" or blocker.dependency is None:
        return blocker
    path = Path(blocker.dependency)
    roots = [config.repo, config.state_dir, config.history_dir, config.artifact_dir]
    if not path.is_absolute() or not _allowed_path(path, roots) or path.is_symlink():
        return blocker.model_copy(update={"dependency_identity": None})
    if path.exists() and not path.is_file():
        return blocker.model_copy(update={"dependency_identity": None})
    try:
        identity = _hash_file(path) if path.is_file() else "missing"
    except OSError:
        return blocker.model_copy(update={"dependency_identity": None})
    return blocker.model_copy(update={"dependency_identity": identity})


def validate_completion(
    payload: Any,
    task: RunnerTask,
    attempt_id: str,
    config: RunnerConfig,
    *,
    allowed_areas: set[str] | None = None,
    baseline_head: str | None = None,
) -> Completion:
    try:
        completion = Completion.model_validate(payload)
    except ValidationError as exc:
        raise ValueError("completion schema invalid") from exc
    if completion.task_id != task.id or completion.attempt_id != attempt_id:
        raise ValueError("completion identity mismatch")
    if completion.status != "completed":
        if not completion.blocked_reason or completion.followup is not None:
            raise ValueError("blocked completion needs a reason and no followup")
        if (
            completion.engineering_status is not None
            or completion.investment_status is not None
        ):
            raise ValueError("unfinished task cannot claim completion outcome")
        if completion.status != "blocked" and completion.recovery_kind is not None:
            raise ValueError("waiting completion cannot request recovery")
        if (
            completion.status in {"waiting_external", "waiting_human"}
            and completion.blocker is None
        ):
            raise ValueError("waiting completion needs a structured blocker")
        if completion.status == "waiting_human" and (
            completion.blocker is None
            or completion.blocker.retry_policy != "manual"
            or completion.blocker.next_eligible_retry is not None
        ):
            raise ValueError("human wait requires manual release")
        return completion
    if completion.recovery_kind is not None:
        raise ValueError("completed result cannot request recovery")
    if task.task_kind == "engineering" and (
        completion.engineering_status != "ENGINEERING_COMPLETE"
        or completion.investment_status != "NOT_EVALUATED"
        or completion.followup is not None
    ):
        raise ValueError("engineering completion has invalid outcome")
    if task.task_kind != "engineering" and (
        completion.engineering_status is not None
        or completion.investment_status is not None
    ):
        raise ValueError("investment completion cannot claim engineering outcome")
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
    if task.task_kind == "engineering":
        current_main = _git(config.repo, "rev-parse", "main").stdout.strip()
        if completion.integrated_commit != current_main:
            raise ValueError("engineering commit must be current main HEAD")
        if baseline_head is None or completion.integrated_commit == baseline_head:
            raise ValueError("engineering commit must be a new descendant")
        descendant = _git(
            config.repo,
            "merge-base",
            "--is-ancestor",
            baseline_head,
            completion.integrated_commit,
            check=False,
        )
        if descendant.returncode != 0:
            raise ValueError("engineering commit must be a new descendant")
        changed = _git(
            config.repo,
            "diff",
            "--no-renames",
            "--name-only",
            baseline_head,
            completion.integrated_commit,
        )
        if set(changed.stdout.splitlines()) != ENGINEERING_OWNED_PATHS:
            raise ValueError("engineering commit must change exact owned paths")
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
    if task.task_kind == "engineering" and not ENGINEERING_OWNED_PATHS.issubset(
        {
            str(Path(evidence.path).resolve().relative_to(config.repo.resolve()))
            for evidence in completion.evidence
            if config.repo.resolve() in Path(evidence.path).resolve().parents
        }
    ):
        raise ValueError("engineering evidence needs exact owned paths")
    if completion.handoff_path is None:
        raise ValueError("completed result is missing handoff")
    handoff = Path(completion.handoff_path)
    if (
        not _allowed_path(handoff, roots)
        or not handoff.is_file()
        or handoff.is_symlink()
    ):
        raise ValueError("handoff path invalid")
    if allowed_areas is None and config.scope == ROADMAP_SCOPE:
        try:
            allowed_areas = set(load_roadmap(config.repo).by_id)
        except RoadmapError as exc:
            raise ValueError("tracked investment roadmap is unavailable") from exc
    followup_areas = ALLOWED_AREAS if allowed_areas is None else allowed_areas
    if (
        completion.followup is not None
        and completion.followup.area not in followup_areas
    ):
        raise ValueError("followup area is not allowed")
    return completion


def _bind_scope(store: RunnerStore, scope: str) -> tuple[bool, str]:
    existing = store.get_meta("scope")
    if existing is None:
        if scope != "research":
            return False, "investment roadmap cannot use an unbound legacy state"
        store.set_meta("scope", "research")
        return True, ""
    if existing != scope:
        return False, "runner state scope mismatch"
    return True, ""


def _next_task(
    store: RunnerStore,
    scope: Literal["research", "investment-roadmap"] = "research",
    *,
    exclude: set[str] | None = None,
) -> RunnerTask | None:
    now = datetime.now(UTC)
    for task in store.tasks():
        if (
            task.status != "queued"
            or task.area == PLANNING_AREA
            or (exclude is not None and task.id in exclude)
        ):
            continue
        if task.depends_on is not None:
            dependency = store.task(task.depends_on)
            accepted = (
                {"completed"} if scope == ROADMAP_SCOPE else {"completed", "blocked"}
            )
            if dependency is None or dependency.status not in accepted:
                continue
        if task.next_allowed_at:
            try:
                due = datetime.fromisoformat(task.next_allowed_at)
            except ValueError:
                return task
            if due.tzinfo is None or due.utcoffset() != timedelta(0):
                return task
            if due > now:
                continue
        return task
    return None


def _select_task(
    store: RunnerStore,
    scope: Literal["research", "investment-roadmap"],
    roadmap: Roadmap | None,
) -> RunnerTask | None:
    """Quarantine invalid task contracts without stopping independent work."""
    while (task := _next_task(store, scope)) is not None:
        reason: str | None = None
        if task.next_allowed_at:
            try:
                due = datetime.fromisoformat(task.next_allowed_at)
                if due.tzinfo is None or due.utcoffset() != timedelta(0):
                    reason = "retry timestamp is not UTC"
            except ValueError:
                reason = "retry timestamp is invalid"
        if reason is None and task.task_kind == "engineering":
            if (
                scope != ROADMAP_SCOPE
                or task.id != ENGINEERING_SPEC_ID
                or task.area != ENGINEERING_SPEC_AREA
                or task.prompt != ENGINEERING_SPEC_PROMPT
                or task.depends_on is not None
            ):
                reason = "engineering task does not match registered spec"
        elif reason is None and task.task_kind not in {"research", "investment"}:
            reason = "task kind is not registered"
        elif reason is None and roadmap is not None and task.task_kind != "engineering":
            item = roadmap.by_id.get(task.area.lower())
            if item is None:
                reason = "queued roadmap area is not tracked"
            elif item.complete:
                reason = "queued roadmap area is already complete"
        if reason is None:
            return task
        blocker = unknown_blocker(reason, dependency=task.depends_on)
        alternative = _next_task(store, scope, exclude={task.id})
        if alternative is not None and (
            roadmap is None
            or (
                alternative.task_kind == "engineering"
                and alternative.id == ENGINEERING_SPEC_ID
                and alternative.area == ENGINEERING_SPEC_AREA
                and alternative.prompt == ENGINEERING_SPEC_PROMPT
            )
            or (
                alternative.area.lower() in roadmap.by_id
                and not roadmap.by_id[alternative.area.lower()].complete
            )
        ):
            blocker = blocker.model_copy(
                update={"alternative_ready_tasks": [alternative.id]}
            )
        if not store.quarantine(task.id, "blocked", blocker.model_dump(mode="json")):
            return None
    return None


def _research_snapshot(store: RunnerStore) -> list[tuple[str, str, str | None]]:
    return sorted(
        (task.id, task.status, task.last_attempt_id)
        for task in store.tasks()
        if task.area != PLANNING_AREA
    )


def _roadmap_waiting_identity(
    store: RunnerStore, repo: Path
) -> tuple[str, list[tuple[str, str, str | None]]] | None:
    """Return the current roadmap planner ID and snapshot without enqueueing."""
    documents_ready, _ = _roadmap_documents_ready(repo)
    if not documents_ready:
        return None
    try:
        mandate = _roadmap_dispatch_gate(repo)
        roadmap = load_roadmap(repo)
        tasks = _research_snapshot(store)
        code_tree_sha = _git(repo, "rev-parse", "main:backend/jusik").stdout.strip()
    except (
        MandateGovernanceError,
        RoadmapError,
        OSError,
        subprocess.CalledProcessError,
    ):
        return None
    digest = roadmap_fingerprint(tasks, roadmap, mandate.digest, code_tree_sha)
    return planner_task_id(digest), tasks


def _tracked_research_mandate(
    repo: Path, expected_digest: str | None = None
) -> str | None:
    """Read the current tracked mandate for planner context."""
    path = repo / "docs" / "research-mandate.json"
    if not path.is_file() or path.is_symlink():
        return None
    try:
        raw = path.read_bytes()
        if (
            expected_digest is not None
            and hashlib.sha256(raw).hexdigest() != expected_digest
        ):
            return None
        content = raw.decode("utf-8")
        mandate = json.loads(content)
        if not isinstance(
            mandate, dict
        ) or not RESEARCH_MANDATE_REQUIRED_FIELDS.issubset(mandate):
            return None
        return content
    except (OSError, UnicodeError):
        return None
    except json.JSONDecodeError:
        return None


def _tracked_continuous_session_policy(repo: Path) -> str | None:
    """Read the tracked operator policy for a bounded continuous session."""
    path = repo / "docs" / "continuous-development-session.md"
    if not path.is_file() or path.is_symlink() or not os.access(path, os.R_OK):
        return None
    relative = str(path.relative_to(repo))
    tracked = _git(repo, "ls-files", "--error-unmatch", relative, check=False)
    if getattr(tracked, "returncode", 1) != 0 or tracked.stdout.strip() != str(
        relative
    ):
        return None
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None
    required = ("started_at:", "deadline_at:", "status:", "Stop conditions")
    return content if all(marker in content for marker in required) else None


def _roadmap_dispatch_gate(
    repo: Path, expected_digest: str | None = None
) -> ValidatedMandate:
    ready, _ = _git_ready(repo)
    if not ready:
        raise MandateGovernanceError("investment roadmap worktree is not ready")
    current = validate_dispatch_gate(repo)
    if expected_digest is not None and current.digest != expected_digest:
        raise MandateGovernanceError("mandate governance changed")
    return current


def _roadmap_documents_ready(repo: Path) -> tuple[bool, str]:
    required = (
        Path("docs/investment-development-roadmap.md"),
        Path("docs/research-mandate.json"),
        Path("docs/development-runner.md"),
        Path("docs/roadmap-automation.md"),
        Path("docs/continuous-development-session.md"),
    )
    for relative in required:
        path = repo / relative
        if not path.is_file() or path.is_symlink() or not os.access(path, os.R_OK):
            return False, f"required roadmap document is missing: {relative}"
        tracked = _git(repo, "ls-files", "--error-unmatch", str(relative), check=False)
        if getattr(tracked, "returncode", 1) != 0 or tracked.stdout.strip() != str(
            relative
        ):
            return False, f"required roadmap document is not tracked: {relative}"
    if _tracked_research_mandate(repo) is None:
        return False, "tracked research mandate is missing or malformed"
    if _tracked_continuous_session_policy(repo) is None:
        return False, (
            "tracked continuous development session policy is missing or malformed"
        )
    return True, ""


def _planning_task(
    store: RunnerStore,
    repo: Path,
    scope: Literal["research", "investment-roadmap"] = "research",
    mandate_digest: str | None = None,
) -> tuple[RunnerTask, str, list[tuple[str, str, str | None]]] | None:
    if scope == ROADMAP_SCOPE:
        documents_ready, _ = _roadmap_documents_ready(repo)
        if not documents_ready:
            return None
        try:
            roadmap = load_roadmap(repo)
        except RoadmapError:
            return None
        if mandate_digest is None:
            mandate_digest = _roadmap_dispatch_gate(repo).digest
        tasks = _research_snapshot(store)
        if any(status == "running" for _, status, _ in tasks):
            return None
        if _next_task(store, ROADMAP_SCOPE) is not None:
            return None
        if sum(status in {"queued", "running"} for _, status, _ in tasks) >= 8:
            return None
        eligible = eligible_areas(roadmap) - reserved_areas(
            task for task in store.tasks() if task.area != PLANNING_AREA
        )
        if not eligible:
            return None
        code_tree_sha = _git(repo, "rev-parse", "main:backend/jusik").stdout.strip()
        digest = roadmap_fingerprint(
            tasks, roadmap, mandate_digest or "", code_tree_sha
        )
        existing = store.task(planner_task_id(digest))
        if existing is not None:
            ready = not existing.next_allowed_at or (
                datetime.fromisoformat(existing.next_allowed_at) <= datetime.now(UTC)
            )
            return (
                (existing, digest, tasks)
                if existing.status == "queued" and ready
                else None
            )
        task_id = planner_task_id(digest)
        if mandate_digest is not None:
            _roadmap_dispatch_gate(repo, mandate_digest)
        store.enqueue(
            task_id,
            PLANNING_AREA,
            roadmap_planner_context(roadmap, tasks, eligible),
        )
        task = store.task(task_id)
        return (task, digest, tasks) if task is not None else None
    tasks = _research_snapshot(store)
    if any(status in {"queued", "running"} for _, status, _ in tasks):
        return None
    if (
        sum(
            status not in {"completed", "failed", "waiting_external", "waiting_human"}
            for _, status, _ in tasks
        )
        >= 8
    ):
        return None
    head = _git(repo, "rev-parse", "main").stdout.strip()
    day = datetime.now(UTC).date().isoformat()
    digest = planning_fingerprint(tasks, head, day)
    existing = store.task(planner_task_id(digest))
    if existing is not None:
        ready = not existing.next_allowed_at or (
            datetime.fromisoformat(existing.next_allowed_at) <= datetime.now(UTC)
        )
        return (
            (existing, digest, tasks) if existing.status == "queued" and ready else None
        )
    task_id = planner_task_id(digest)
    store.enqueue(
        task_id,
        PLANNING_AREA,
        "Plan exactly one useful bounded portfolio research job. Read the current "
        "tracked mandate at docs/research-mandate.json before making any proposal; "
        "that document is authoritative and replaces any mandate details in this "
        "task prompt. If it is missing or unreadable, return waiting with a clear "
        "resume condition. Keep PAPER10% unchanged. "
        "For GPU stress research, consult docs/research-gpu-role.md and "
        "docs/research-portfolio-gpu-stress.md and use only the on-demand "
        "research_portfolio_gpu_stress CLI when measured beneficial, with fixed "
        "inputs, seed, bounds, and CPU parity; never promote approximate results. "
        f"{DEVELOPMENT_DELIVERY_POLICY} "
        "Return planning JSON.",
    )
    task = store.task(task_id)
    return (task, digest, tasks) if task is not None else None


AUTO_RETRY_BACKOFF_SECONDS = (60, 120)
AUTO_RETRYABLE_PLANNING_FAILURES = frozenset(
    {"planning_output_invalid", "planning_schema_invalid", "planning_length_invalid"}
)
ENVIRONMENT_RECOVERY_LABELS = frozenset(
    {"dependency_setup", "cache_permission", "tool_unavailable"}
)
IMPLEMENTATION_RECOVERY_LABELS = frozenset(
    {
        "code_defect",
        "test_defect",
        "lint_defect",
        "type_defect",
        "actionable_review",
    }
)


def _planner_feedback(store: RunnerStore, task_id: str) -> str | None:
    code = store.last_failure_code(task_id)
    return code if code in AUTO_RETRYABLE_PLANNING_FAILURES else None


def _planning_failure_code(error: BaseException) -> str:
    if isinstance(error, (OSError, json.JSONDecodeError)):
        return "planning_output_invalid"
    message = str(error)
    if message == "planning schema invalid":
        return "planning_schema_invalid"
    if message == "proposal prompt is not bounded":
        return "planning_length_invalid"
    if message == "planning identity mismatch":
        return "planning_identity_invalid"
    if "planning evidence" in message:
        return "planning_evidence_invalid"
    return "planning_invalid"


def _attempt_environment(attempt_dir: Path) -> dict[str, str]:
    cache_root = attempt_dir / "cache"
    _secure_dir(cache_root)
    environment = os.environ.copy()
    for name in (
        "XDG_CACHE_HOME",
        "UV_CACHE_DIR",
        "PIP_CACHE_DIR",
        "RUFF_CACHE_DIR",
        "MYPY_CACHE_DIR",
    ):
        path = cache_root / name.lower()
        _secure_dir(path)
        environment[name] = str(path)
    return environment


def _automatic_retry_requested(
    config: RunnerConfig,
    *,
    eligible: bool,
) -> bool:
    return config.automatic_recovery and eligible


def _run_planning(
    config: RunnerConfig,
    common: Path,
    store: RunnerStore,
    candidate: tuple[RunnerTask, str, list[tuple[str, str, str | None]]],
    stop_requested: Callable[[], bool] | None,
    started_at: datetime,
    *,
    allowed_areas: set[str] | None = None,
    context: str | None = None,
    fingerprint_factory: Callable[[list[tuple[str, str, str | None]], str, str], str]
    | None = None,
    mandate_digest: str | None = None,
) -> RunResult:
    task, digest, snapshot = candidate
    if config.scope == ROADMAP_SCOPE:
        try:
            _roadmap_dispatch_gate(config.repo, mandate_digest)
        except MandateGovernanceError as exc:
            return RunResult("blocked", task.id, reason=str(exc))
    attempt_id = uuid.uuid4().hex
    main_head = _git(config.repo, "rev-parse", "main").stdout.strip()
    mandate = _tracked_research_mandate(
        config.repo,
        mandate_digest if config.scope == ROADMAP_SCOPE else None,
    )
    if config.scope == ROADMAP_SCOPE and mandate is None:
        return RunResult("blocked", task.id, reason="mandate governance changed")
    mandate_context = (
        "Current tracked mandate (docs/research-mandate.json) supersedes all older "
        "mandate text in this queued task and prompt:\n"
        f"{mandate}"
        if mandate is not None
        else "MANDATE STATUS: docs/research-mandate.json is missing or unreadable. "
        "Return status waiting and state that planning resumes after the tracked "
        "mandate is restored. Do not infer or propose research from an older prompt."
    )
    evidence_roots = (
        config.repo,
        config.repo.parent,
        config.state_dir,
        config.history_dir,
        config.artifact_dir,
    )
    planning_areas = ALLOWED_AREAS if allowed_areas is None else allowed_areas
    scope_context = "" if context is None else f"{context}\n"
    feedback = _planner_feedback(store, task.id)
    feedback_context = (
        f"Previous planner failure label: {feedback}. Correct that bounded output "
        "and preserve all identity, evidence, and repository gates.\n"
        if feedback is not None
        else ""
    )
    prompt = (
        f"Task id: {task.id}\nAttempt id: {attempt_id}\nFingerprint: {digest}\n\n"
        f"{task.prompt}\nResearch snapshot: {json.dumps(snapshot, sort_keys=True)}\n"
        f"Current main HEAD: {main_head}\nAllowed areas: {sorted(planning_areas)}\n"
        f"{scope_context}"
        f"{feedback_context}"
        f"{mandate_context}\n"
        f"Permitted evidence roots: "
        f"{[str(path.resolve()) for path in evidence_roots]}\n"
        "Return planning JSON only. The proposal prompt MUST contain six concise "
        "labelled sections in this order: Objective, Scope, Inputs, Computation cap, "
        "Tests, Stop condition. Keep it under 1600 characters (hard maximum 2000); "
        "put all six labels and short substantive values first, then omit detail. "
        "Refer to evidence instead of repeating long context. Do not modify repo, "
        "database, config, remote, orders, or create subagents. Use private bounded "
        "wait_reason with missing input and resume condition when waiting. Cite "
        "existing permitted evidence only; never cite this attempt's files. GPU stress "
        "must remain on-demand, fixed-input/seed/bounds with CPU parity and no "
        "promotion of approximate results."
    )
    if config.scope == ROADMAP_SCOPE:
        try:
            _roadmap_dispatch_gate(config.repo, mandate_digest)
        except MandateGovernanceError as exc:
            return RunResult("blocked", task.id, reason=str(exc))
    attempt_dir = config.state_dir / "attempts" / attempt_id
    _secure_dir(attempt_dir)
    output_path = attempt_dir / "planning.json"
    stderr_path = attempt_dir / "stderr.log"
    stdout_path = attempt_dir / "stdout.jsonl"
    _write_private(attempt_dir / "prompt.txt", prompt.encode())
    _write_private(stdout_path, b"")
    try:
        if config.scope == ROADMAP_SCOPE:
            _roadmap_dispatch_gate(config.repo, mandate_digest)
        store.claim(
            task,
            attempt_id,
            output_path,
            stderr_path,
            started_at.isoformat(),
            history_outcome="planning_started",
        )
        _safe_history_flush(store, config)
    except MandateGovernanceError as exc:
        for path in attempt_dir.iterdir():
            path.unlink()
        attempt_dir.rmdir()
        return RunResult("blocked", task.id, reason=str(exc))
    except ValueError:
        return RunResult("idle")
    schema_path = attempt_dir / "planning.schema.json"
    _write_private(
        schema_path,
        (json.dumps(_planning_schema(planning_areas), sort_keys=True) + "\n").encode(),
    )
    command = _codex_command(config, common, schema_path, output_path, planning=True)
    with stderr_path.open("wb") as stderr, stdout_path.open("ab") as stdout:
        try:
            process = subprocess.Popen(
                command,
                cwd=config.repo,
                stdin=subprocess.PIPE,
                stdout=stdout,
                stderr=stderr,
                start_new_session=True,
                env=_attempt_environment(attempt_dir),
            )
        except OSError:
            store.finish(attempt_id, task.id, "failed", failure_code="dispatch_error")
            return RunResult("failed", task.id, attempt_id, "dispatch_error")
        try:
            group_id = os.getpgid(process.pid)
        except ProcessLookupError:
            group_id = None
        if group_id is not None:
            store.set_process_group(attempt_id, group_id)
        deadline = time.monotonic() + config.timeout_seconds
        child_started_at = time.time()
        data: bytes | None = prompt.encode()
        while True:
            if store.is_paused() or (stop_requested is not None and stop_requested()):
                _stop_process(process)
                store.finish(
                    attempt_id,
                    task.id,
                    "interrupted",
                    failure_code="paused" if store.is_paused() else "signal",
                )
                return RunResult(
                    "paused" if store.is_paused() else "interrupted",
                    task.id,
                    attempt_id,
                )
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                _stop_process(process)
                store.finish(attempt_id, task.id, "failed", failure_code="timeout")
                return RunResult("failed", task.id, attempt_id, "timeout")
            if _child_idle_expired(
                stdout_path,
                stderr_path,
                child_started_at,
                config.idle_timeout_seconds,
            ):
                _stop_process(process)
                store.finish(attempt_id, task.id, "failed", failure_code="idle_timeout")
                return RunResult("failed", task.id, attempt_id, "idle_timeout")
            try:
                process.communicate(data, timeout=min(1, remaining))
                data = None
            except subprocess.TimeoutExpired:
                data = None
                continue
            break
    if process.returncode != 0:
        store.finish(attempt_id, task.id, "failed", failure_code="codex_exit")
        return RunResult("failed", task.id, attempt_id, "codex_exit")
    if store.is_paused() or (stop_requested is not None and stop_requested()):
        store.finish(
            attempt_id,
            task.id,
            "interrupted",
            failure_code="paused" if store.is_paused() else "signal",
        )
        return RunResult(
            "paused" if store.is_paused() else "interrupted", task.id, attempt_id
        )
    try:
        payload = json.loads(output_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        failure_code = "planning_output_invalid"
        store.finish(
            attempt_id,
            task.id,
            "failed",
            failure_code=failure_code,
            automatic_retry=_automatic_retry_requested(config, eligible=True),
        )
        return RunResult("failed", task.id, attempt_id, failure_code)
    try:
        if store.is_paused() or (stop_requested is not None and stop_requested()):
            store.finish(
                attempt_id,
                task.id,
                "interrupted",
                failure_code="paused" if store.is_paused() else "signal",
            )
            return RunResult(
                "paused" if store.is_paused() else "interrupted", task.id, attempt_id
            )
        result = validate_planning_result(
            payload,
            task.id,
            attempt_id,
            digest,
            config,
            attempt_dir,
            planning_areas,
            {item.id for item in store.tasks()},
        )
        if mandate is None and result.proposal is not None:
            result = result.model_copy(
                update={
                    "status": "waiting",
                    "proposal": None,
                    "wait_reason": (
                        "Tracked docs/research-mandate.json is missing or unreadable; "
                        "planning resumes after it is restored."
                    ),
                }
            )
        ready, reason = _git_ready(config.repo)
        if not ready:
            raise ValueError(reason)
        current_head = _git(config.repo, "rev-parse", "main").stdout.strip()
        current_digest = (
            planning_fingerprint(snapshot, current_head, started_at.date().isoformat())
            if fingerprint_factory is None
            else fingerprint_factory(
                snapshot, current_head, started_at.date().isoformat()
            )
        )
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        failure_code = _planning_failure_code(exc)
        if isinstance(exc, OSError):
            failure_code = "planning_evidence_invalid"
        store.finish(
            attempt_id,
            task.id,
            "failed",
            failure_code=failure_code,
            automatic_retry=_automatic_retry_requested(
                config, eligible=failure_code in AUTO_RETRYABLE_PLANNING_FAILURES
            ),
        )
        return RunResult("failed", task.id, attempt_id, failure_code)
    proposal = (
        None
        if result.proposal is None
        else (
            result.proposal.id,
            result.proposal.area,
            f"{COMMON_PROMPT}\n\n{result.proposal.prompt}",
        )
    )
    if proposal is not None and allowed_areas is not None:
        try:
            roadmap = load_roadmap(config.repo)
            validate_planner_area(roadmap, proposal[1], store.tasks())
        except RoadmapError:
            store.finish(attempt_id, task.id, "failed", failure_code="planning_invalid")
            return RunResult("failed", task.id, attempt_id, "planning_invalid")
    if store.is_paused() or (stop_requested is not None and stop_requested()):
        store.finish(
            attempt_id,
            task.id,
            "interrupted",
            failure_code="paused" if store.is_paused() else "signal",
        )
        return RunResult(
            "paused" if store.is_paused() else "interrupted", task.id, attempt_id
        )
    try:
        if config.scope == ROADMAP_SCOPE:
            current_mandate = validate_dispatch_gate(config.repo)
            if mandate_digest != current_mandate.digest:
                raise MandateGovernanceError("mandate governance changed")
        committed = store.finish_planning(
            attempt_id,
            task.id,
            result.status,
            result.model_dump(),
            digest,
            snapshot,
            current_digest,
            proposal,
            scope=config.scope,
            proposal_head_matches=current_head == main_head,
        )
    except MandateGovernanceError as exc:
        store.finish(attempt_id, task.id, "blocked", failure_code="mandate_stale")
        return RunResult("blocked", task.id, attempt_id, str(exc))
    except RuntimeError:
        store.finish(
            attempt_id,
            task.id,
            "interrupted",
            failure_code="paused" if store.is_paused() else "signal",
        )
        return RunResult(
            "paused" if store.is_paused() else "interrupted", task.id, attempt_id
        )
    except ValueError:
        store.finish(attempt_id, task.id, "failed", failure_code="planning_invalid")
        return RunResult("failed", task.id, attempt_id, "planning_invalid")
    _safe_history_flush(store, config)
    return RunResult(
        "completed" if committed else "blocked",
        task.id,
        attempt_id,
        None if committed else "planning_stale",
    )


def _history_flush(store: RunnerStore, config: RunnerConfig) -> None:
    repository = HistoryRepository(config.history_dir, config.history_db)
    for identity, task_id, attempt_id, outcome in store.outbox_pending():
        planning = outcome.startswith("planning_") or outcome == "planning_started"
        title = "자동 연구 계획기" if planning else "자동 개발 실행기"
        summary = (
            "연구 계획 상태가 기록되었습니다."
            if planning
            else "개발 cycle 상태가 기록되었습니다."
        )
        repository.record(
            identity=identity,
            title=title,
            summary=summary,
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
    if config.scope == ROADMAP_SCOPE:
        validate_dispatch_gate(config.repo)
        documents_ready, documents_reason = _roadmap_documents_ready(config.repo)
        if not documents_ready:
            raise MandateGovernanceError(documents_reason)
        _roadmap_dispatch_gate(config.repo)
    store = RunnerStore(config.state_dir / "runner.db", config.history_dir)
    hold_triggers = store.operator_hold_triggers()
    if hold_triggers:
        raise RunnerResumeError(
            "operator hold triggers remain: " + ", ".join(hold_triggers)
        )
    store.resume()
    _record_control_event(store, config, "resumed")


def run_once(
    config: RunnerConfig, stop_requested: Callable[[], bool] | None = None
) -> RunResult:
    governance: ValidatedMandate | None = None
    try:
        common = _git_common(config.repo)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return RunResult("blocked", reason="invalid repository")
    if config.scope == ROADMAP_SCOPE:
        documents_ready, documents_reason = _roadmap_documents_ready(config.repo)
        if not documents_ready:
            return RunResult("blocked", reason=documents_reason)
        try:
            governance = validate_dispatch_gate(config.repo)
        except MandateGovernanceError as exc:
            return RunResult("blocked", reason=str(exc))
    lock_path = common / "development-runner.lock"
    with lock_path.open("a+") as lock:
        lock_path.chmod(0o600)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return RunResult("busy")
        store = RunnerStore(config.state_dir / "runner.db", config.history_dir)
        scope_ready, scope_reason = _bind_scope(store, config.scope)
        if not scope_ready:
            return RunResult("blocked", reason=scope_reason)
        hold_triggers = store.operator_hold_triggers()
        if hold_triggers:
            return RunResult(
                "blocked",
                reason="operator hold triggers remain: " + ", ".join(hold_triggers),
            )
        roadmap = None
        session_policy = None
        if config.scope == ROADMAP_SCOPE:
            documents_ready, documents_reason = _roadmap_documents_ready(config.repo)
            if not documents_ready:
                return RunResult("blocked", reason=documents_reason)
            try:
                roadmap = load_roadmap(config.repo)
                session_policy = _tracked_continuous_session_policy(config.repo)
            except RoadmapError as exc:
                return RunResult("blocked", reason=str(exc))
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
        if (
            config.daily_launches is not None
            and store.launch_count(now.strftime("%Y-%m-%d")) >= config.daily_launches
        ):
            _record_control_event(store, config, "quota")
            return RunResult("quota")
        latest = store.get_meta("last_launch_at")
        if latest and now - datetime.fromisoformat(latest) < timedelta(
            seconds=config.cooldown_seconds
        ):
            return RunResult("cooldown")
        store.release_due_waiting(now)
        task = _select_task(store, config.scope, roadmap)
        if task is None:
            if not config.planning_enabled:
                return RunResult("idle")
            if config.scope == ROADMAP_SCOPE:
                if governance is None:
                    return RunResult(
                        "blocked", reason="mandate governance is unavailable"
                    )
                try:
                    current_governance = validate_dispatch_gate(config.repo)
                except MandateGovernanceError as exc:
                    return RunResult("blocked", reason=str(exc))
                if current_governance.digest != governance.digest:
                    return RunResult("blocked", reason="mandate governance changed")
                try:
                    candidate = _planning_task(
                        store, config.repo, config.scope, governance.digest
                    )
                except MandateGovernanceError as exc:
                    return RunResult("blocked", reason=str(exc))
            else:
                candidate = _planning_task(store, config.repo, config.scope)
            if candidate is None:
                return RunResult("idle")
            try:
                _prepare_artifact_dir(config.artifact_dir)
            except OSError:
                return RunResult(
                    "blocked", candidate[0].id, reason="artifact directory unavailable"
                )
            planning_kwargs: dict[str, Any] = {}
            if config.scope == ROADMAP_SCOPE and roadmap is not None:
                eligible = eligible_areas(roadmap) - reserved_areas(
                    item for item in store.tasks() if item.area != PLANNING_AREA
                )
                planning_kwargs = {
                    "allowed_areas": eligible,
                    "context": (
                        roadmap_planner_context(roadmap, candidate[2], eligible)
                        + "\n\nOperator session policy:\n"
                        + (session_policy or "")
                    ),
                    "fingerprint_factory": lambda tasks, _head, _day: (
                        roadmap_fingerprint(
                            tasks,
                            load_roadmap(config.repo),
                            governance.digest if governance is not None else "",
                            _git(
                                config.repo, "rev-parse", "main:backend/jusik"
                            ).stdout.strip(),
                        )
                    ),
                }
            result = _run_planning(
                config,
                common,
                store,
                candidate,
                stop_requested,
                now,
                mandate_digest=(governance.digest if governance is not None else None),
                **planning_kwargs,
            )
            _safe_history_flush(store, config)
            return result
        roadmap_prompt_text = ""
        if roadmap is not None and task.task_kind != "engineering":
            try:
                if governance is None:
                    return RunResult(
                        "blocked", task.id, reason="mandate governance is unavailable"
                    )
                _roadmap_dispatch_gate(config.repo, governance.digest)
                mandate_snapshot = _tracked_research_mandate(
                    config.repo, governance.digest
                )
                if mandate_snapshot is None:
                    return RunResult(
                        "blocked", task.id, reason="mandate governance changed"
                    )
                if task.area.lower() not in roadmap.by_id:
                    raise RoadmapError("queued roadmap area is not tracked")
                if roadmap.by_id[task.area.lower()].complete:
                    raise RoadmapError("queued roadmap area is already complete")
                roadmap_prompt_text = roadmap_prompt(
                    task.area.lower(),
                    roadmap.by_id[task.area.lower()],
                    mandate_snapshot,
                )
                roadmap_prompt_text += "\n\nOperator session policy:\n" + (
                    session_policy or ""
                )
            except (MandateGovernanceError, RoadmapError) as exc:
                return RunResult("blocked", task.id, reason=str(exc))
        try:
            if config.scope == ROADMAP_SCOPE:
                if governance is None:
                    return RunResult(
                        "blocked", task.id, reason="mandate governance is unavailable"
                    )
                current_governance = validate_dispatch_gate(config.repo)
                if current_governance.digest != governance.digest:
                    return RunResult(
                        "blocked", task.id, reason="mandate governance changed"
                    )
            _prepare_artifact_dir(config.artifact_dir)
        except OSError:
            return RunResult(
                "blocked", task.id, reason="artifact directory unavailable"
            )
        attempt_id = uuid.uuid4().hex
        previous = task.last_attempt_id or "none"
        prompt = (
            f"Task id: {task.id}\nAttempt id: {attempt_id}\n"
            f"Previous attempt id: {previous}\n\n{task.prompt}\n"
            f"{roadmap_prompt_text}\n\n"
            "Return the required completion JSON to the output path supplied by "
            "the CLI. Use the exact task and attempt ids, include SHA-256 evidence "
            "paths under the allowed roots, "
            "and report tests_passed, review_passed, integrated_commit, and "
            f"handoff_path.\n\n{RUNTIME_PROMPT_SUFFIX}"
        )
        if roadmap is not None:
            try:
                _roadmap_dispatch_gate(
                    config.repo, governance.digest if governance else None
                )
            except MandateGovernanceError as exc:
                return RunResult("blocked", task.id, reason=str(exc))
        baseline_head = (
            _git(config.repo, "rev-parse", "main").stdout.strip()
            if task.task_kind == "engineering"
            else None
        )
        attempt_dir = config.state_dir / "attempts" / attempt_id
        _secure_dir(attempt_dir)
        output_path = attempt_dir / "completion.json"
        stderr_path = attempt_dir / "stderr.log"
        stdout_path = attempt_dir / "stdout.jsonl"
        _write_private(attempt_dir / "prompt.txt", prompt.encode())
        _write_private(stdout_path, b"")
        try:
            if roadmap is not None:
                _roadmap_dispatch_gate(
                    config.repo, governance.digest if governance else None
                )
            store.claim(
                task,
                attempt_id,
                output_path,
                stderr_path,
                now.isoformat(),
                baseline_head=baseline_head,
            )
        except MandateGovernanceError as exc:
            for path in attempt_dir.iterdir():
                path.unlink()
            attempt_dir.rmdir()
            return RunResult("blocked", task.id, reason=str(exc))
        _safe_history_flush(store, config)
        schema_path = attempt_dir / "completion.schema.json"
        _write_private(
            schema_path,
            (
                json.dumps(
                    _completion_schema(
                        set(roadmap.by_id) if roadmap is not None else ALLOWED_AREAS,
                        engineering=task.task_kind == "engineering",
                    ),
                    sort_keys=True,
                )
                + "\n"
            ).encode(),
        )
        command = _codex_command(config, common, schema_path, output_path)
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
                    env=_attempt_environment(attempt_dir),
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
            child_started_at = time.time()
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
                if _child_idle_expired(
                    stdout_path,
                    stderr_path,
                    child_started_at,
                    config.idle_timeout_seconds,
                ):
                    _stop_process(process)
                    store.finish(
                        attempt_id, task.id, "failed", failure_code="idle_timeout"
                    )
                    _safe_history_flush(store, config)
                    return RunResult("failed", task.id, attempt_id, "idle_timeout")
                if _empty_receiver_wait_detected(stdout_path):
                    _stop_process(process)
                    store.finish(
                        attempt_id,
                        task.id,
                        "failed",
                        failure_code="empty_review_dispatch",
                    )
                    _safe_history_flush(store, config)
                    return RunResult(
                        "failed", task.id, attempt_id, "empty_review_dispatch"
                    )
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
            try:
                _write_exit_diagnostics(attempt_dir, process.returncode, output_path)
            except OSError:
                pass
            _safe_history_flush(store, config)
            return RunResult("failed", task.id, attempt_id, "codex_exit")
        try:
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            completion = validate_completion(
                payload,
                task,
                attempt_id,
                config,
                allowed_areas=set(roadmap.by_id) if roadmap is not None else None,
                baseline_head=baseline_head,
            )
            if roadmap is not None and task.task_kind != "engineering":
                validate_roadmap_completion(load_roadmap(config.repo), task, completion)
        except (OSError, json.JSONDecodeError, RoadmapError, ValueError):
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
        if completion.status != "completed":
            blocker = completion.blocker or unknown_blocker(
                completion.blocked_reason or "unknown", dependency=task.depends_on
            )
            if blocker.blocker_reason != completion.blocked_reason:
                store.finish(
                    attempt_id, task.id, "failed", failure_code="completion_invalid"
                )
                _safe_history_flush(store, config)
                return RunResult("failed", task.id, attempt_id, "completion_invalid")
            blocker = _bind_event_dependency(blocker, config)
            if (
                completion.status == "waiting_external"
                and blocker.retry_policy == "bounded"
                and task.attempt_count >= 2
            ):
                blocker = blocker.model_copy(
                    update={
                        "retry_policy": "manual",
                        "next_eligible_retry": None,
                        "resume_condition": "bounded retry exhausted; explicit review",
                    }
                )
            recovery_eligible = completion.status == "blocked" and (
                (
                    completion.recovery_kind == "environment"
                    and completion.blocked_reason in ENVIRONMENT_RECOVERY_LABELS
                )
                or (
                    completion.recovery_kind == "implementation"
                    and completion.blocked_reason in IMPLEMENTATION_RECOVERY_LABELS
                )
            )
            store.finish(
                attempt_id,
                task.id,
                completion.status,
                evidence=completion.model_dump(mode="json"),
                automatic_retry=_automatic_retry_requested(
                    config, eligible=recovery_eligible
                ),
                blocker=blocker.model_dump(mode="json"),
                next_allowed_at=(
                    blocker.next_eligible_retry.isoformat()
                    if blocker.next_eligible_retry is not None
                    else None
                ),
            )
            _safe_history_flush(store, config)
            return RunResult(
                completion.status, task.id, attempt_id, completion.blocked_reason
            )
        if task.task_kind == "engineering":
            # A child completion is a candidate. Only a separate reviewer attempt
            # may eventually finalize this task; generic event retry cannot do so.
            receipt_path = (
                config.state_dir / "review-receipts" / f"{task.id}-{attempt_id}.json"
            ).resolve()
            alternative = _next_task(store, config.scope)
            blocker = _bind_event_dependency(
                Blocker(
                    blocker_reason="independent_review_pending",
                    attempted_actions=[
                        "validated new commit and exact owned file evidence"
                    ],
                    dependency=str(receipt_path),
                    dependency_identity="missing",
                    resume_condition=(
                        "separate read-only reviewer PASS receipt bound to this task, "
                        "attempt, and integrated commit"
                    ),
                    retry_policy="none",
                    alternative_ready_tasks=[alternative.id] if alternative else [],
                ),
                config,
            )
            store.finish(
                attempt_id,
                task.id,
                "waiting_external",
                failure_code="independent_review_pending",
                evidence=completion.model_dump(mode="json"),
                blocker=blocker.model_dump(mode="json"),
            )
            _safe_history_flush(store, config)
            return RunResult(
                "waiting_external", task.id, attempt_id, "independent_review_pending"
            )
        store.finish(
            attempt_id,
            task.id,
            "completed",
            evidence=completion.model_dump(mode="json"),
        )
        if completion.followup is not None:
            if config.scope == ROADMAP_SCOPE:
                if governance is None:
                    _safe_history_flush(store, config)
                    return RunResult(
                        "blocked",
                        task.id,
                        attempt_id,
                        "mandate governance is unavailable",
                    )
                try:
                    _roadmap_dispatch_gate(config.repo, governance.digest)
                except MandateGovernanceError as exc:
                    _safe_history_flush(store, config)
                    return RunResult("blocked", task.id, attempt_id, str(exc))
            pending = [
                item
                for item in store.tasks()
                if item.area != PLANNING_AREA
                if (
                    item.status in {"queued", "running"}
                    if roadmap is not None
                    else item.status not in {"completed", "failed"}
                )
            ]
            if len(pending) < 8:
                if roadmap is None:
                    store.enqueue(
                        completion.followup.id,
                        completion.followup.area,
                        f"{COMMON_PROMPT}\n\n{completion.followup.prompt}",
                    )
                else:
                    try:
                        current_roadmap = load_roadmap(config.repo)
                        area = validate_enqueue(
                            current_roadmap,
                            store.tasks(),
                            completion.followup.id,
                            completion.followup.area,
                        )
                    except RoadmapError:
                        area = None
                    if area is not None:
                        mandate_snapshot = _tracked_research_mandate(
                            config.repo, governance.digest if governance else None
                        )
                        if mandate_snapshot is None:
                            _safe_history_flush(store, config)
                            return RunResult(
                                "blocked",
                                task.id,
                                attempt_id,
                                "mandate governance changed",
                            )
                        followup_prompt = roadmap_prompt(
                            area,
                            current_roadmap.by_id[area],
                            mandate_snapshot,
                        )
                        try:
                            _roadmap_dispatch_gate(
                                config.repo, governance.digest if governance else None
                            )
                        except MandateGovernanceError as exc:
                            _safe_history_flush(store, config)
                            return RunResult("blocked", task.id, attempt_id, str(exc))
                        store.enqueue(
                            completion.followup.id,
                            area,
                            f"{COMMON_PROMPT}\n\n{followup_prompt}\n\n"
                            f"{completion.followup.prompt}",
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
    init.add_argument(
        "--scope", choices=["research", ROADMAP_SCOPE], default="research"
    )
    for name in ("status", "run-once", "pause", "resume"):
        command = sub.add_parser(name)
        command.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    enqueue = sub.add_parser("enqueue")
    enqueue.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    enqueue.add_argument("--id")
    enqueue.add_argument("--area")
    enqueue.add_argument("--prompt")
    enqueue.add_argument(
        "--kind", choices=["existing", "engineering"], default="existing"
    )
    enqueue.add_argument("--spec")
    retry = sub.add_parser("retry")
    retry.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    retry.add_argument(
        "--planning-wait",
        action="store_true",
        help="retry a completed investment-roadmap planner waiting result",
    )
    retry.add_argument("task_id")
    retry.add_argument("--event-evidence", type=Path)
    rebase = sub.add_parser("rebase")
    rebase.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    rebase.add_argument("task_id")
    rebase.add_argument("--base-commit", required=True)
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
            args.scope,
        )
        print(
            json.dumps(
                {
                    "status": "initialized",
                    "scope": config.scope,
                    "tasks": len(BACKLOG) if config.scope == "research" else 0,
                },
                ensure_ascii=False,
            )
        )
        return 0
    config = load_config(args.config)
    if args.command == "resume" and config.scope == ROADMAP_SCOPE:
        try:
            validate_dispatch_gate(config.repo)
        except MandateGovernanceError as exc:
            print(json.dumps({"status": "blocked", "reason": str(exc)}))
            return 2
    store = RunnerStore(config.state_dir / "runner.db", config.history_dir)
    scope_ready, scope_reason = _bind_scope(store, config.scope)
    if not scope_ready:
        print(json.dumps({"status": "blocked", "reason": scope_reason}))
        return 2
    if args.command == "status":
        snapshot = store.tasks()
        by_id = {task.id: task for task in snapshot}
        tasks = []
        for task in snapshot:
            view = {**asdict(task), "canonical_state": task.canonical_state}
            if task.status == "queued" and task.depends_on is not None:
                dependency = by_id.get(task.depends_on)
                accepted = (
                    {"completed"}
                    if config.scope == ROADMAP_SCOPE
                    else {"completed", "blocked"}
                )
                if dependency is None or dependency.status not in accepted:
                    view["canonical_state"] = "BLOCKED"
                    view["blocker"] = Blocker(
                        blocker_reason="dependency not complete",
                        attempted_actions=[],
                        dependency=task.depends_on,
                        resume_condition="dependency reaches accepted state",
                        retry_policy="event",
                        alternative_ready_tasks=[],
                    ).model_dump(mode="json")
            if task.status == "queued" and task.next_allowed_at is not None:
                try:
                    due = datetime.fromisoformat(task.next_allowed_at)
                    valid = due.tzinfo is not None and due.utcoffset() == timedelta(0)
                except ValueError:
                    valid = False
                if not valid:
                    view["canonical_state"] = "BLOCKED"
                    view["blocker"] = unknown_blocker(
                        "retry timestamp is invalid"
                    ).model_dump(mode="json")
                elif due > datetime.now(UTC) and view["canonical_state"] == "READY":
                    view["canonical_state"] = "WAITING_EXTERNAL"
                    if view["blocker"] is None:
                        view["blocker"] = Blocker(
                            blocker_reason="legacy_unknown",
                            attempted_actions=[],
                            dependency=None,
                            resume_condition="UTC retry deadline",
                            retry_policy="bounded",
                            next_eligible_retry=due,
                            alternative_ready_tasks=[],
                        ).model_dump(mode="json")
            tasks.append(view)
        print(
            json.dumps(
                {
                    "paused": store.is_paused(),
                    "tasks": tasks,
                },
                ensure_ascii=False,
            )
        )
        return 0
    if args.command == "enqueue":
        if args.kind == "engineering":
            if (
                config.scope != ROADMAP_SCOPE
                or args.spec != ENGINEERING_SPEC_ID
                or any(value is not None for value in (args.id, args.area, args.prompt))
            ):
                print(
                    json.dumps(
                        {
                            "enqueued": False,
                            "reason": "engineering spec is not registered",
                        }
                    )
                )
                return 2
            print(
                json.dumps(
                    {
                        "enqueued": store.enqueue(
                            ENGINEERING_SPEC_ID,
                            ENGINEERING_SPEC_AREA,
                            ENGINEERING_SPEC_PROMPT,
                            task_kind="engineering",
                        )
                    }
                )
            )
            return 0
        if args.spec is not None or not all(
            value is not None for value in (args.id, args.area, args.prompt)
        ):
            print(
                json.dumps(
                    {"enqueued": False, "reason": "id, area, and prompt are required"}
                )
            )
            return 2
        if config.scope == ROADMAP_SCOPE:
            try:
                roadmap = load_roadmap(config.repo)
                area = validate_enqueue(roadmap, store.tasks(), args.id, args.area)
            except RoadmapError as exc:
                print(json.dumps({"enqueued": False, "reason": str(exc)}))
                return 2
        else:
            area = args.area
            if area not in ALLOWED_AREAS:
                print(json.dumps({"enqueued": False, "reason": "area is not allowed"}))
                return 2
        print(
            json.dumps(
                {
                    "enqueued": store.enqueue(
                        args.id,
                        area,
                        args.prompt,
                        task_kind="investment"
                        if config.scope == ROADMAP_SCOPE
                        else "research",
                    )
                },
                ensure_ascii=False,
            )
        )
        return 0
    if args.command == "retry":
        if args.event_evidence is not None:
            evidence_path = args.event_evidence
            roots = [
                config.repo,
                config.state_dir,
                config.history_dir,
                config.artifact_dir,
            ]
            retried = (
                not args.planning_wait
                and _allowed_path(evidence_path, roots)
                and store.release_event(args.task_id, evidence_path)
            )
        elif args.planning_wait:
            identity = (
                _roadmap_waiting_identity(store, config.repo)
                if config.scope == ROADMAP_SCOPE
                else None
            )
            retried = (
                identity is not None
                and identity[0] == args.task_id
                and store.retry_planning_waiting(args.task_id, identity[1])
            )
        else:
            retried = store.retry(args.task_id)
        print(json.dumps({"retried": retried}, ensure_ascii=False))
        return 0
    if args.command == "rebase":
        current = _git(config.repo, "rev-parse", "main").stdout.strip()
        if current != args.base_commit:
            print(
                json.dumps(
                    {
                        "rebased": False,
                        "reason": "base commit does not match current main",
                        "current_main": current,
                    },
                    ensure_ascii=False,
                )
            )
            return 2
        print(
            json.dumps(
                {
                    "rebased": store.rebase(args.task_id, current),
                    "base_commit": current,
                },
                ensure_ascii=False,
            )
        )
        return 0
    if args.command == "pause":
        pause_runner(config)
        print(json.dumps({"status": "paused"}, ensure_ascii=False))
        return 0
    if args.command == "resume":
        try:
            resume_runner(config)
        except (MandateGovernanceError, RunnerResumeError) as exc:
            print(json.dumps({"status": "blocked", "reason": str(exc)}))
            return 2
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
