"""The runtime priority reaches every dispatched child, including stored tasks."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from test_development_runner import _repo
from test_development_runner_discovery import _exhausted, _fake_child
from test_development_runner_planning_scope import _fake_planner, _fake_scope
from test_development_runner_review import _candidate, _fake_reviewer

from jusik import development_runner as runner
from jusik.development_runner_store import RunnerStore


def _capture_stdin(fake: Path) -> None:
    source = fake.read_text(encoding="utf-8")
    read = "prompt = sys.stdin.read()\n"
    assert source.count(read) == 1
    source = source.replace(
        read,
        read
        + "from pathlib import Path\n"
        + "(Path(sys.argv[sys.argv.index('-o') + 1]).parent / "
        + "'received-prompt.txt').write_text(prompt, encoding='utf-8')\n",
    )
    fake.write_text(source, encoding="utf-8")


def _assert_delivered(directory: Path, *, legacy: bool = False) -> None:
    saved = (directory / "prompt.txt").read_bytes()
    received = (directory / "received-prompt.txt").read_bytes()
    assert saved == received
    prompt = saved.decode("utf-8")
    assert prompt.startswith(runner.FAST_RESULTS_PRIORITY + "\n\n")
    assert prompt.count(runner.FAST_RESULTS_PRIORITY) == 1
    assert "current subscription plan" in prompt
    assert "2026-10-04" in prompt
    assert "exact billing/end time is unknown" in prompt
    assert "No new-spend cap has been set" in prompt
    assert "not payment approval" in prompt
    assert "cost-inclusive net returns" in prompt
    assert "MDD <= 20%" in prompt
    if legacy:
        assert "legacy stored prompt" in prompt
        assert runner.COMMON_PROMPT not in prompt


def test_planning_and_roadmap_scope_dispatch_same_saved_prompt(tmp_path: Path) -> None:
    fake = tmp_path / "planner.py"
    _fake_planner(fake)
    _capture_stdin(fake)
    base, _ = _exhausted(tmp_path, fake)
    config = base.model_copy(update={"planning_enabled": True})
    planned = runner.run_once(config)
    assert planned.reason == "planning_scope_pending"
    assert planned.attempt_id is not None
    _assert_delivered(config.state_dir / "attempts" / planned.attempt_id)

    _fake_scope(fake)
    _capture_stdin(fake)
    scope = runner.run_once(config)
    assert scope.reason == "roadmap_scope_approved"
    assert scope.attempt_id is not None
    _assert_delivered(config.state_dir / "roadmap-scope" / scope.attempt_id)


def test_discovery_and_scope_dispatch_same_saved_prompt(tmp_path: Path) -> None:
    fake = tmp_path / "discovery.py"
    _fake_child(fake)
    _capture_stdin(fake)
    config, _ = _exhausted(tmp_path, fake)
    discovered = runner.run_once(config)
    assert discovered.reason == "discovery_scope"
    assert discovered.attempt_id is not None
    _assert_delivered(config.state_dir / "discovery" / discovered.attempt_id)

    scoped = runner.run_once(config)
    assert scoped.reason == "discovery_approved"
    assert scoped.attempt_id is not None
    _assert_delivered(config.state_dir / "discovery" / scoped.attempt_id)


def test_completion_review_dispatch_same_saved_prompt(tmp_path: Path) -> None:
    config, _, _, _ = _candidate(tmp_path)
    fake = tmp_path / "review.py"
    _fake_reviewer(fake, verdict="PASS")
    _capture_stdin(fake)
    reviewed = runner.run_once(config.model_copy(update={"codex": str(fake)}))
    assert reviewed.status == "completed"
    review_dirs = list((config.state_dir / "reviews").iterdir())
    assert len(review_dirs) == 1
    _assert_delivered(review_dirs[0])


def test_legacy_queued_task_without_seed_guidance_receives_priority(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    fake = tmp_path / "legacy.py"
    fake.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        "from pathlib import Path\n"
        "prompt = sys.stdin.read()\n"
        "fields = dict(line.split(': ', 1) for line in prompt.splitlines() "
        "if line.startswith(('Task id: ', 'Attempt id: ')))\n"
        "payload = {'task_id': fields['Task id'], "
        "'attempt_id': fields['Attempt id'], 'status': 'blocked', "
        "'blocked_reason': 'fixture stop', 'tests_passed': False, "
        "'review_passed': False}\n"
        "Path(sys.argv[sys.argv.index('-o') + 1]).write_text(json.dumps(payload))\n",
        encoding="utf-8",
    )
    fake.chmod(0o700)
    _capture_stdin(fake)
    config = runner.RunnerConfig(
        repo=repo,
        codex=str(fake),
        state_dir=tmp_path / "state",
        history_dir=tmp_path / "history",
        history_db=tmp_path / "history.db",
        artifact_dir=tmp_path / "artifacts",
        planning_enabled=False,
        cooldown_seconds=0,
    )
    store = RunnerStore(config.state_dir / "runner.db", config.history_dir)
    assert store.enqueue("legacy", "entry-amount-distribution", "legacy stored prompt")
    result = runner.run_once(config)
    assert result.status == "blocked" and result.attempt_id is not None
    _assert_delivered(config.state_dir / "attempts" / result.attempt_id, legacy=True)


@pytest.mark.parametrize(
    ("task_id", "expected"),
    [
        ("waiting-human", "waiting_human"),
        ("waiting-external", "waiting_external"),
        ("mismatched-wait", "completion_invalid"),
    ],
)
def test_wait_completion_prompt_contract_and_mismatch_rejection(
    tmp_path: Path, task_id: str, expected: str
) -> None:
    repo = _repo(tmp_path)
    evidence_path = tmp_path / "artifacts" / "existing-source-receipt.json"
    evidence_path.parent.mkdir()
    evidence_path.write_text('{"receipt": "fixture"}\n', encoding="utf-8")
    evidence_sha256 = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
    fake = tmp_path / "waiting.py"
    fake.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        "from pathlib import Path\n"
        "prompt = sys.stdin.read()\n"
        "fields = dict(line.split(': ', 1) for line in prompt.splitlines() "
        "if line.startswith(('Task id: ', 'Attempt id: ')))\n"
        "reason = 'operator decision required'\n"
        "status = 'waiting_external' if fields['Task id'] == 'waiting-external' "
        "else 'waiting_human'\n"
        "retry_policy = 'event' if status == 'waiting_external' else 'manual'\n"
        "dependency = "
        + repr(str(evidence_path.resolve()))
        + " if status == 'waiting_external' else 'operator decision'\n"
        "dependency_identity = "
        + repr(evidence_sha256)
        + " if status == 'waiting_external' else None\n"
        "blocker = {'blocker_reason': "
        "'operator decision required (mismatch)' "
        "if fields['Task id'] == 'mismatched-wait' "
        "else reason, 'attempted_actions': [], 'dependency': dependency, "
        "'dependency_identity': dependency_identity, "
        "'resume_condition': 'authenticated decision', "
        "'retry_policy': retry_policy, 'next_eligible_retry': None, "
        "'alternative_ready_tasks': []}\n"
        "payload = {'task_id': fields['Task id'], 'attempt_id': fields['Attempt id'], "
        "'status': status, 'integrated_commit': None, 'evidence': [], "
        "'tests_passed': False, 'review_passed': False, 'handoff_path': None, "
        "'blocked_reason': reason, 'followup': None, 'recovery_kind': None, "
        "'blocker': blocker, 'engineering_status': None, 'investment_status': None}\n"
        "Path(sys.argv[sys.argv.index('-o') + 1]).write_text(json.dumps(payload))\n",
        encoding="utf-8",
    )
    fake.chmod(0o700)
    _capture_stdin(fake)
    config = runner.RunnerConfig(
        repo=repo,
        codex=str(fake),
        state_dir=tmp_path / "state",
        history_dir=tmp_path / "history",
        history_db=tmp_path / "history.db",
        artifact_dir=tmp_path / "artifacts",
        planning_enabled=False,
        cooldown_seconds=0,
    )
    store = RunnerStore(config.state_dir / "runner.db", config.history_dir)
    assert store.enqueue(task_id, "entry-amount-distribution", "wait")

    result = runner.run_once(config)
    if expected == "completion_invalid":
        assert result.status == "failed" and result.reason == expected
        return

    assert result.status == expected and result.attempt_id is not None
    _assert_delivered(config.state_dir / "attempts" / result.attempt_id)
    prompt_path = config.state_dir / "attempts" / result.attempt_id / "prompt.txt"
    prompt = prompt_path.read_text()
    assert (
        "Return the required completion JSON to the output path supplied by the CLI. "
        "Use the exact task and attempt ids"
    ) in prompt
    assert "waiting_external or waiting_human" in prompt
    assert "exactly the same character-for-character text" in prompt
    assert "copy it verbatim into both fields" in prompt
    assert "dependency must be the canonical absolute path" in prompt
    assert "dependency_identity its current file SHA-256" in prompt
    assert "report the unresolved task as blocked with retry_policy=none" in prompt
    if expected == "waiting_external":
        saved_task = store.task(task_id)
        assert saved_task is not None and saved_task.blocker is not None
        assert saved_task.blocker["dependency"] == str(evidence_path.resolve())
        assert saved_task.blocker["dependency_identity"] == evidence_sha256
