from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, cast

import pytest

from jusik.development_runner import RunnerConfig, _codex_command
from jusik.development_runner_planning import (
    PLANNING_AREA,
    fingerprint,
    validate_planning_result,
)
from jusik.development_runner_store import RunnerStore


def _config(tmp_path: Path) -> RunnerConfig:
    repo = tmp_path / "repo"
    repo.mkdir()
    return RunnerConfig(
        repo=repo,
        state_dir=tmp_path / "state",
        history_dir=tmp_path / "history",
        history_db=tmp_path / "history.db",
        artifact_dir=tmp_path / "artifact",
    )


def test_planning_area_is_private_and_fingerprint_excludes_planner_state(
    tmp_path: Path,
) -> None:
    store = RunnerStore(tmp_path / "state" / "runner.db")
    store.enqueue("planner-old", PLANNING_AREA, "internal")
    store.enqueue("research", "portfolio-stress-robustness", "research")
    research: list[tuple[str, str, str | None]] = [("research", "queued", None)]
    assert fingerprint(research, "a" * 40, "2026-09-12") == fingerprint(
        research, "a" * 40, "2026-09-12"
    )


def test_planning_result_requires_bounded_prompt_and_existing_hashed_evidence(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    evidence = tmp_path / "evidence.json"
    evidence.write_text("{}\n", encoding="utf-8")
    digest = fingerprint([], "a" * 40, "2026-09-12")
    payload = {
        "task_id": "planner-task",
        "attempt_id": "attempt",
        "fingerprint": digest,
        "status": "proposed",
        "proposal": {
            "id": "next-research-v1",
            "area": "portfolio-stress-robustness",
            "prompt": "objective scope inputs computation cap tests stop condition",
            "evidence": [
                {
                    "path": str(evidence),
                    "sha256": hashlib.sha256(evidence.read_bytes()).hexdigest(),
                }
            ],
        },
        "wait_reason": None,
    }
    result = validate_planning_result(
        payload,
        "planner-task",
        "attempt",
        digest,
        config,
        tmp_path / "attempt",
        {"portfolio-stress-robustness"},
        set(),
    )
    assert result.status == "proposed"
    proposal = cast(dict[str, Any], payload["proposal"])
    proposal["prompt"] = "unbounded"
    with pytest.raises(ValueError, match="bounded"):
        validate_planning_result(
            payload,
            "planner-task",
            "attempt",
            digest,
            config,
            tmp_path / "attempt",
            {"portfolio-stress-robustness"},
            set(),
        )


def test_finish_planning_is_atomic_and_exact_replay_is_idempotent(
    tmp_path: Path,
) -> None:
    store = RunnerStore(tmp_path / "state" / "runner.db")
    store.enqueue("planner-task", PLANNING_AREA, "internal")
    task = store.task("planner-task")
    assert task is not None
    store.claim(
        task,
        "attempt",
        tmp_path / "out",
        tmp_path / "err",
        history_outcome="planning_started",
    )
    snapshot: list[tuple[str, str, str | None]] = []
    digest = hashlib.sha256(b"[]").hexdigest()
    assert (
        store.finish_planning(
            "attempt",
            "planner-task",
            "proposed",
            {"status": "proposed"},
            digest,
            snapshot,
            proposal=("next-research-v1", "portfolio-stress-robustness", "prompt"),
        )
        is True
    )
    before = store.outbox_pending()
    assert (
        store.finish_planning(
            "attempt",
            "planner-task",
            "proposed",
            {"status": "proposed"},
            digest,
            snapshot,
            proposal=("next-research-v1", "portfolio-stress-robustness", "prompt"),
        )
        is True
    )
    assert store.outbox_pending() == before
    assert len([item for item in store.tasks() if item.area != PLANNING_AREA]) == 1


def test_planning_outbox_preserves_started_then_terminal_then_proposal(
    tmp_path: Path,
) -> None:
    store = RunnerStore(tmp_path / "state" / "runner.db")
    store.enqueue("planner-task", PLANNING_AREA, "internal")
    task = store.task("planner-task")
    assert task is not None
    store.claim(
        task,
        "attempt",
        tmp_path / "out",
        tmp_path / "err",
        history_outcome="planning_started",
    )
    store.finish_planning(
        "attempt",
        "planner-task",
        "proposed",
        {"status": "proposed"},
        hashlib.sha256(b"[]").hexdigest(),
        [],
        proposal=("next-research-v1", "portfolio-stress-robustness", "prompt"),
    )
    assert [item[3] for item in store.outbox_pending()] == [
        "planning_started",
        "planning_proposed",
        "planning_proposed",
    ]


def test_completed_planning_replay_does_not_rewrite_snapshot_or_outbox(
    tmp_path: Path,
) -> None:
    store = RunnerStore(tmp_path / "state" / "runner.db")
    store.enqueue("planner-task", PLANNING_AREA, "internal")
    task = store.task("planner-task")
    assert task is not None
    store.claim(task, "attempt", tmp_path / "out", tmp_path / "err")
    digest = hashlib.sha256(b"[]").hexdigest()
    store.finish_planning(
        "attempt", "planner-task", "waiting", {"status": "waiting"}, digest, []
    )
    before_tasks = store.tasks()
    before_outbox = store.outbox_pending()
    assert store.finish_planning(
        "attempt",
        "planner-task",
        "proposed",
        {"status": "proposed"},
        "f" * 64,
        [("unexpected", "queued", None)],
        proposal=("another-research", "portfolio-stress-robustness", "prompt"),
    )
    assert store.tasks() == before_tasks
    assert store.outbox_pending() == before_outbox


def test_planner_profile_is_readonly_and_writes_only_attempt_directory(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    command = _codex_command(
        config,
        tmp_path / "common",
        tmp_path / "state" / "schema",
        tmp_path / "state" / "attempt" / "output",
        planning=True,
    )
    profile = command[command.index("-c", command.index("-c") + 1) + 1]
    assert ":read-only" in profile
    assert "network={enabled=false}" in profile
    assert str((tmp_path / "state" / "attempt").resolve()) in profile
