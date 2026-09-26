"""Roadmap planning precedence and independent scope review regressions."""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from test_development_runner_discovery import _exhausted, _fake_child, _git

from jusik import development_runner as runner
from jusik.development_runner_planning_scope import (
    ROADMAP_TASK_SCOPE_GUARD,
    PendingRoadmapScope,
    RoadmapScopeReview,
)
from jusik.development_runner_planning_scope import (
    canonical_json as scope_json,
)
from jusik.development_runner_planning_scope import (
    digest as scope_digest,
)
from jusik.development_runner_store import RunnerStore


def test_legacy_finish_planning_cannot_enqueue_roadmap_proposal(
    tmp_path: Path,
) -> None:
    store = RunnerStore(tmp_path / "state" / "runner.db")
    assert store.enqueue("roadmap-planner", "__planning__", "internal")
    task = store.task("roadmap-planner")
    assert task is not None
    store.claim(task, "attempt", tmp_path / "out", tmp_path / "err")
    with pytest.raises(ValueError, match="independent scope review"):
        store.finish_planning(
            "attempt",
            task.id,
            "proposed",
            {"status": "proposed"},
            hashlib.sha256(b"[]").hexdigest(),
            [],
            proposal=("roadmap-audit-v1", "r1-05", "bounded proposal"),
            scope="investment-roadmap",
        )
    assert store.task("roadmap-audit-v1") is None
    assert store.task("roadmap-planner").status == "running"  # type: ignore[union-attr]


@pytest.mark.parametrize("explicit_research_scope", [False, True])
def test_bound_roadmap_scope_cannot_be_bypassed_by_caller_scope(
    tmp_path: Path, explicit_research_scope: bool
) -> None:
    store = RunnerStore(tmp_path / "state" / "runner.db")
    store.set_meta("scope", "investment-roadmap")
    assert store.enqueue("roadmap-planner", "__planning__", "internal")
    task = store.task("roadmap-planner")
    assert task is not None
    store.claim(task, "attempt", tmp_path / "out", tmp_path / "err")
    args: tuple[
        str, str, str, dict[str, str], str, list[tuple[str, str, str | None]]
    ] = (
        "attempt",
        task.id,
        "proposed",
        {"status": "proposed"},
        hashlib.sha256(b"[]").hexdigest(),
        [],
    )
    with pytest.raises(ValueError, match="independent scope review"):
        if explicit_research_scope:
            store.finish_planning(
                *args, proposal=("audit-v1", "r1-05", "prompt"), scope="research"
            )
        else:
            store.finish_planning(*args, proposal=("audit-v1", "r1-05", "prompt"))
    assert store.task("audit-v1") is None
    assert store.task("roadmap-planner").status == "running"  # type: ignore[union-attr]


def _scope_receipt(pending: PendingRoadmapScope, review_id: str) -> RoadmapScopeReview:
    return RoadmapScopeReview(
        verdict="PASS",
        review_attempt_id=review_id,
        planner_task_id=pending.planner_task_id,
        planner_attempt_id=pending.planner_attempt_id,
        fingerprint=pending.fingerprint,
        baseline_head=pending.baseline_head,
        mandate_digest=pending.mandate_digest,
        roadmap_digest=pending.roadmap_digest,
        area=pending.proposal.area,
        proposal_digest=pending.proposal_digest,
        evidence_digest=pending.evidence_digest,
        work_class="readiness",
        reason="Offline readiness audit has bounded evidence and no activation.",
    )


def _fake_planner(
    path: Path, evidence_path: Path | None = None, *, waiting: bool = False
) -> None:
    evidence_source = (
        "Path('docs/research-mandate.json').resolve()"
        if evidence_path is None
        else f"Path({str(evidence_path)!r}).resolve()"
    )
    wait_reason = (
        repr("Need actual data; resume when receipts exist.") if waiting else "None"
    )
    path.write_text(
        "#!/usr/bin/env python3\n"
        "import ast, hashlib, json, sys\n"
        "from pathlib import Path\n"
        "prompt = sys.stdin.read()\n"
        "fields = dict(line.split(': ', 1) for line in prompt.splitlines() "
        "if line.startswith(('Task id: ', 'Attempt id: ', 'Fingerprint: ', "
        "'Allowed areas: ')))\n"
        "area = sorted(ast.literal_eval(fields['Allowed areas']))[0]\n"
        f"evidence = {evidence_source}\n"
        "proposal = {'id': 'roadmap-audit-v1', 'area': area, "
        "'prompt': 'Objective: audit research readiness. Scope: offline contract only. "
        "Inputs: tracked mandate. Computation cap: 10 files. Tests: focused fixtures. "
        "Stop condition: report missing receipts; no investment validation.', "
        "'evidence': [{'path': str(evidence), 'sha256': "
        "hashlib.sha256(evidence.read_bytes()).hexdigest()}]}\n"
        "payload = {'task_id': fields['Task id'], 'attempt_id': fields['Attempt id'], "
        "'fingerprint': fields['Fingerprint'], "
        f"'status': {'waiting' if waiting else 'proposed'!r}, "
        f"'proposal': {'None' if waiting else 'proposal'}, "
        f"'wait_reason': {wait_reason}}}\n"
        "Path(sys.argv[sys.argv.index('-o')+1]).write_text(json.dumps(payload))\n",
        encoding="utf-8",
    )
    path.chmod(0o700)


def _fake_scope(path: Path, verdict: str = "PASS", *, tamper: bool = False) -> None:
    tamper_line = "payload['proposal_digest'] = '0' * 64\n" if tamper else ""
    path.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        "from pathlib import Path\n"
        "prompt = sys.stdin.read()\n"
        "fields = dict(line.split(': ', 1) for line in prompt.splitlines() "
        "if line.startswith(('Review attempt id: ', 'Planner task id: ', "
        "'Planner attempt id: ', 'Fingerprint: ', 'Baseline HEAD: ', "
        "'Mandate digest: ', 'Roadmap digest: ', 'Area: ', "
        "'Proposal digest: ', 'Evidence digest: ')))\n"
        f"verdict = {verdict!r}\n"
        "payload = {'verdict': verdict, "
        "'review_attempt_id': fields['Review attempt id'], "
        "'planner_task_id': fields['Planner task id'], "
        "'planner_attempt_id': fields['Planner attempt id'], "
        "'fingerprint': fields['Fingerprint'], "
        "'baseline_head': fields['Baseline HEAD'], "
        "'mandate_digest': fields['Mandate digest'], "
        "'roadmap_digest': fields['Roadmap digest'], 'area': fields['Area'], "
        "'proposal_digest': fields['Proposal digest'], "
        "'evidence_digest': fields['Evidence digest'], "
        "'work_class': 'readiness' if verdict == 'PASS' else None, "
        "'reason': 'Offline readiness audit has bounded evidence and no activation.'}\n"
        f"{tamper_line}"
        "Path(sys.argv[sys.argv.index('-o')+1]).write_text(json.dumps(payload))\n",
        encoding="utf-8",
    )
    path.chmod(0o700)


def test_eligible_roadmap_planning_precedes_fresh_engineering_discovery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = tmp_path / "unused.py"
    _fake_child(fake)
    base_config, _ = _exhausted(tmp_path, fake)
    config = base_config.model_copy(update={"planning_enabled": True})
    calls: list[str] = []

    def fake_planning(*args: object, **kwargs: object) -> runner.RunResult:
        calls.append("planning")
        return runner.RunResult("completed", reason="planning_selected")

    def fake_discovery(*args: object, **kwargs: object) -> runner.RunResult:
        calls.append("discovery")
        return runner.RunResult("completed", reason="discovery_selected")

    monkeypatch.setattr(runner, "_run_planning", fake_planning)
    monkeypatch.setattr(runner, "_run_engineering_discovery", fake_discovery)
    result = runner.run_once(config)
    assert result.reason == "planning_selected"
    assert calls == ["planning"]


def test_roadmap_proposal_needs_independent_scope_pass(
    tmp_path: Path,
) -> None:
    fake = tmp_path / "fake-planner.py"
    _fake_planner(fake)
    base_config, store = _exhausted(tmp_path, fake)
    config = base_config.model_copy(update={"planning_enabled": True})
    first = runner.run_once(config)
    assert first.reason == "planning_scope_pending"
    assert store.task("roadmap-audit-v1") is None
    pending = RunnerStore(store.db_path).pending_roadmap_scope()
    assert pending is not None
    _fake_scope(fake)
    second = runner.run_once(config)
    assert second.reason == "roadmap_scope_approved"
    assert second.task_id == "roadmap-audit-v1"
    task = RunnerStore(store.db_path).task("roadmap-audit-v1")
    assert task is not None and task.status == "queued"
    assert task.investment_status is None
    assert task.prompt.startswith(
        ROADMAP_TASK_SCOPE_GUARD.format(work_class="readiness")
    )
    assert RunnerStore(store.db_path).pending_roadmap_scope() is None
    with sqlite3.connect(store.db_path) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM tasks WHERE id='roadmap-audit-v1'"
        ).fetchone() == (1,)
    assert second.attempt_id is not None
    receipt_path = (
        config.state_dir / "roadmap-scope" / second.attempt_id / "result.json"
    )
    receipt = RoadmapScopeReview.model_validate_json(receipt_path.read_text())
    assert not store.approve_roadmap_scope(
        pending,
        second.attempt_id,
        receipt,
        config.repo,
        task.prompt,
        "a" * 64,
    )


def test_approved_roadmap_task_cannot_enqueue_completion_followup(
    tmp_path: Path,
) -> None:
    fake = tmp_path / "fake-child.py"
    _fake_planner(fake)
    base_config, store = _exhausted(tmp_path, fake)
    config = base_config.model_copy(update={"planning_enabled": True})
    assert runner.run_once(config).reason == "planning_scope_pending"
    _fake_scope(fake)
    assert runner.run_once(config).reason == "roadmap_scope_approved"
    assert store.is_approved_roadmap_scope_task("roadmap-audit-v1")
    evidence = config.repo / "docs" / "research-mandate.json"
    digest = hashlib.sha256(evidence.read_bytes()).hexdigest()
    head = _git(config.repo, "rev-parse", "main")
    fake.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        "from pathlib import Path\n"
        "fields = dict(line.split(': ', 1) for line in sys.stdin.read().splitlines() "
        "if line.startswith(('Task id: ', 'Attempt id: ')))\n"
        "payload = {'task_id': fields['Task id'], 'attempt_id': fields['Attempt id'], "
        "'status': 'completed', 'tests_passed': True, 'review_passed': True, "
        f"'integrated_commit': {head!r}, "
        f"'evidence': [{{'path': {str(evidence)!r}, 'sha256': {digest!r}}}], "
        f"'handoff_path': {str(evidence)!r}, "
        "'followup': {'id': 'audit-followup-v1', 'area': 'r1-02', "
        "'prompt': 'Bounded offline data readiness followup.'}}\n"
        "Path(sys.argv[sys.argv.index('-o')+1]).write_text(json.dumps(payload))\n",
        encoding="utf-8",
    )
    fake.chmod(0o700)
    result = runner.run_once(config)
    assert result.reason == "completion_invalid"
    assert store.task("audit-followup-v1") is None
    assert store.enqueue("legacy-roadmap-v1", "r1-01", "legacy offline task")
    assert not store.is_approved_roadmap_scope_task("legacy-roadmap-v1")
    assert runner.run_once(config).status == "completed"
    assert store.task("audit-followup-v1") is not None


@pytest.mark.parametrize("change", ["head", "evidence"])
def test_stale_head_or_evidence_cannot_reach_scope_approval(
    tmp_path: Path,
    change: str,
) -> None:
    fake = tmp_path / "fake-planner.py"
    evidence = tmp_path / "artifacts" / "readiness.txt"
    evidence.parent.mkdir(parents=True)
    evidence.write_text("initial offline evidence", encoding="utf-8")
    _fake_planner(fake, evidence)
    base_config, store = _exhausted(tmp_path, fake)
    config = base_config.model_copy(update={"planning_enabled": True})
    assert runner.run_once(config).reason == "planning_scope_pending"
    if change == "head":
        (config.repo / "README.md").write_text("head changed\n", encoding="utf-8")
        _git(config.repo, "add", "README.md")
        _git(config.repo, "commit", "-m", "test head change")
    else:
        evidence.write_text("changed offline evidence", encoding="utf-8")
    _fake_scope(fake)
    assert runner.run_once(config).reason == "roadmap_scope_stale"
    assert store.task("roadmap-audit-v1") is None
    assert store.pending_roadmap_scope() is None


def test_scope_quota_pause_and_receipt_mismatch_never_enqueue(tmp_path: Path) -> None:
    fake = tmp_path / "fake-planner.py"
    _fake_planner(fake)
    base_config, store = _exhausted(tmp_path, fake)
    config = base_config.model_copy(update={"planning_enabled": True})
    assert runner.run_once(config).reason == "planning_scope_pending"
    assert (
        runner.run_once(config.model_copy(update={"daily_launches": 1})).status
        == "quota"
    )
    assert (
        runner.run_once(config.model_copy(update={"cooldown_seconds": 3600})).status
        == "cooldown"
    )
    store.pause()
    assert runner.run_once(config).status == "paused"
    assert store.task("roadmap-audit-v1") is None
    store.resume()
    _fake_scope(fake, tamper=True)
    assert runner.run_once(config).reason == "roadmap_scope_invalid"
    assert store.task("roadmap-audit-v1") is None


@pytest.mark.parametrize(
    ("verdict", "reason"),
    [
        ("REJECT", "roadmap_scope_reject"),
        ("WAIT", "roadmap_scope_wait"),
        ("ERROR", "roadmap_scope_invalid"),
    ],
)
def test_scope_nonpass_terminal_allows_engineering_fallback(
    tmp_path: Path,
    verdict: str,
    reason: str,
) -> None:
    fake = tmp_path / "fake-planner.py"
    _fake_planner(fake)
    base_config, store = _exhausted(tmp_path, fake)
    config = base_config.model_copy(update={"planning_enabled": True})
    assert runner.run_once(config).reason == "planning_scope_pending"
    _fake_scope(fake, verdict)
    assert runner.run_once(config).reason == reason
    assert store.task("roadmap-audit-v1") is None
    assert store.pending_roadmap_scope() is None
    _fake_child(fake)
    assert runner.run_once(config).reason == "discovery_scope"
    assert store.task("roadmap-audit-v1") is None


def test_data_unready_planner_waits_then_engineering_continues(tmp_path: Path) -> None:
    fake = tmp_path / "fake-waiting.py"
    _fake_planner(fake, waiting=True)
    base_config, store = _exhausted(tmp_path, fake)
    config = base_config.model_copy(update={"planning_enabled": True})
    first = runner.run_once(config)
    assert first.status == "completed"
    assert store.pending_roadmap_scope() is None
    assert store.task("roadmap-audit-v1") is None
    _fake_child(fake)
    assert runner.run_once(config).reason == "discovery_scope"


def test_scope_approval_queue_cap_and_transaction_rollback(tmp_path: Path) -> None:
    fake = tmp_path / "fake-planner.py"
    _fake_planner(fake)
    base_config, store = _exhausted(tmp_path, fake)
    config = base_config.model_copy(update={"planning_enabled": True})
    assert runner.run_once(config).reason == "planning_scope_pending"
    pending = store.pending_roadmap_scope()
    assert pending is not None
    review_id = "scope-review"
    assert store.start_roadmap_scope_review(
        pending, review_id, tmp_path / "scope.json", datetime.now(UTC).isoformat()
    )
    receipt = _scope_receipt(pending, review_id)
    prompt = (
        ROADMAP_TASK_SCOPE_GUARD.format(work_class="readiness")
        + f"\n\n{runner.COMMON_PROMPT}\n\n{pending.proposal.prompt}"
    )
    with sqlite3.connect(store.db_path) as db:
        db.execute(
            "CREATE TRIGGER reject_roadmap BEFORE INSERT ON tasks "
            "WHEN NEW.id='roadmap-audit-v1' BEGIN "
            "SELECT RAISE(ABORT,'test rollback'); END"
        )
    with pytest.raises(sqlite3.IntegrityError):
        store.approve_roadmap_scope(
            pending, review_id, receipt, config.repo, prompt, "a" * 64
        )
    assert store.task("roadmap-audit-v1") is None
    assert store.pending_roadmap_scope() is not None
    with sqlite3.connect(store.db_path) as db:
        assert db.execute(
            "SELECT status FROM roadmap_scope_attempts WHERE id=?", (review_id,)
        ).fetchone() == ("running",)
        db.execute("DROP TRIGGER reject_roadmap")
    for index in range(8):
        assert store.enqueue(f"other-{index}", "offline", "independent")
    assert not store.approve_roadmap_scope(
        pending, review_id, receipt, config.repo, prompt, "a" * 64
    )
    assert store.task("roadmap-audit-v1") is None
    assert store.finish_roadmap_scope_review(pending, review_id, "stale")


def test_pending_scope_expires_without_new_reviewer_launch(tmp_path: Path) -> None:
    fake = tmp_path / "fake-planner.py"
    _fake_planner(fake)
    base_config, store = _exhausted(tmp_path, fake)
    config = base_config.model_copy(update={"planning_enabled": True})
    assert runner.run_once(config).reason == "planning_scope_pending"
    pending = store.pending_roadmap_scope()
    assert pending is not None
    expired = pending.model_copy(
        update={"expires_at": (datetime.now(UTC) - timedelta(seconds=1)).isoformat()}
    )
    value = expired.model_dump(mode="json")
    with sqlite3.connect(store.db_path) as db:
        db.execute(
            "UPDATE roadmap_planning_scopes SET pending_json=?,pending_sha256=? "
            "WHERE planner_task_id=?",
            (scope_json(value), scope_digest(value), pending.planner_task_id),
        )
    day = datetime.now(UTC).strftime("%Y-%m-%d")
    assert runner.run_once(config).reason == "roadmap_scope_stale"
    assert store.launch_count(day) == 1
    assert store.task("roadmap-audit-v1") is None


def test_uncertain_scope_orphan_blocks_subsequent_cycles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = tmp_path / "fake-planner.py"
    _fake_planner(fake)
    base_config, store = _exhausted(tmp_path, fake)
    config = base_config.model_copy(update={"planning_enabled": True})
    assert runner.run_once(config).reason == "planning_scope_pending"
    pending = store.pending_roadmap_scope()
    assert pending is not None
    assert store.start_roadmap_scope_review(
        pending, "orphan-review", tmp_path / "scope.json", datetime.now(UTC).isoformat()
    )
    monkeypatch.setattr(runner, "_stop_orphaned_review_group", lambda _: False)
    before = store.launch_count(datetime.now(UTC).strftime("%Y-%m-%d"))
    assert runner.run_once(config).reason == "roadmap scope orphan uncertain"
    assert RunnerStore(store.db_path).roadmap_scope_orphan_hold()
    assert runner.run_once(config).reason == "roadmap scope orphan uncertain"
    assert store.launch_count(datetime.now(UTC).strftime("%Y-%m-%d")) == before
    assert store.task("roadmap-audit-v1") is None
