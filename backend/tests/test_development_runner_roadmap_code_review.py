"""Fresh roadmap code scopes use the host's independent completion reviewer."""

import json
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest
from test_development_runner_backlog import _fake_blocked_child
from test_development_runner_discovery import _exhausted, _git
from test_development_runner_planning_scope import (
    _fake_planner,
    _fake_scope,
    _scope_receipt,
)
from test_development_runner_review import _fake_reviewer

from jusik import development_runner as runner
from jusik.development_runner_contract import ENGINEERING_SPEC_BY_ID
from jusik.development_runner_planning_scope import (
    PendingRoadmapCodeScope,
    RoadmapCodeScopeReview,
    canonical_input_path,
    code_spec,
    validate_code_contract,
)
from jusik.development_runner_roadmap import (
    RoadmapError,
    load_roadmap,
    validate_enqueue,
)
from jusik.development_runner_store import RunnerStore


def _pending(
    tmp_path: Path,
    area: str = "r2-02",
    *,
    nested_request: bool = False,
    external_input: bool = False,
    evidence_style: str | None = None,
) -> tuple[runner.RunnerConfig, RunnerStore, Path]:
    fake = tmp_path / "fake-planner.py"
    evidence_path = None
    if external_input or evidence_style == "tilde":
        evidence_path = tmp_path / "artifacts/input.txt"
        evidence_path.parent.mkdir()
        evidence_path.write_text("fixed offline input\n")
    if evidence_style in {"relative", "dotdot"}:
        evidence_path = Path("backend/jusik/broker_cost_profiles.py")
    _fake_planner(fake, evidence_path)
    if evidence_style is not None:
        assert evidence_path is not None
        reference = (
            "~/" + os.path.relpath(evidence_path, Path.home())
            if evidence_style == "tilde"
            else "backend/jusik/../jusik/broker_cost_profiles.py"
            if evidence_style == "dotdot"
            else str(evidence_path)
        )
        fake.write_text(fake.read_text().replace("str(evidence)", repr(reference)))
    fake.write_text(
        fake.read_text().replace(
            "area = sorted(ast.literal_eval(fields['Allowed areas']))[0]",
            f"area = {area!r}",
        )
    )
    if nested_request:
        fake.write_text(
            fake.read_text().replace(
                "Objective: audit research readiness.",
                "Delegate implementation to Luna and ask Sol for nested review. "
                "Objective: audit research readiness.",
            )
        )
    config, store = _exhausted(tmp_path, fake)
    for relative in (
        "backend/jusik/broker_cost_profiles.py",
        "backend/tests/test_broker_cost_profiles.py",
    ):
        path = config.repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# offline fixture\n")
    _git(config.repo, "add", "backend")
    _git(config.repo, "commit", "-m", "code pair fixture")
    config = config.model_copy(update={"planning_enabled": True})
    with pytest.MonkeyPatch.context() as patch:
        if evidence_style in {"relative", "dotdot"}:
            patch.chdir(config.repo)
        assert runner.run_once(config).reason == "planning_scope_pending"
    return config, store, fake


def _approve(config: runner.RunnerConfig, store: RunnerStore, fake: Path) -> None:
    _fake_scope(fake)
    script = fake.read_text()
    script = script.replace(
        "Path(sys.argv[sys.argv.index('-o')+1]).write_text(json.dumps(payload))",
        "extra = dict(line.split(': ', 1) for line in prompt.splitlines() "
        "if line.startswith(('Code contract digest: ', 'Owned file hashes: ')))\n"
        "payload.update(schema_version=2, execution_kind='engineering_code', "
        "code_contract_digest=extra['Code contract digest'], "
        "owned_file_hashes=json.loads(extra['Owned file hashes']))\n"
        "Path(sys.argv[sys.argv.index('-o')+1]).write_text(json.dumps(payload))",
    )
    fake.write_text(script)
    result = runner.run_once(config)
    assert result.reason == "roadmap_scope_approved"
    assert store.task("roadmap-audit-v1") is not None
    schema = json.loads(
        (
            config.state_dir / "roadmap-scope" / str(result.attempt_id) / "schema.json"
        ).read_text()
    )
    assert set(schema["required"]) == set(schema["properties"])
    hashes = schema["properties"]["owned_file_hashes"]
    assert hashes["additionalProperties"] is False
    assert len(hashes["required"]) == 2
    review_prompt = (
        config.state_dir / "roadmap-scope" / str(result.attempt_id) / "prompt.txt"
    ).read_text()
    assert "Canonical evidence paths: " in review_prompt


def _implementation(fake: Path, *, self_review: bool = False) -> None:
    fake.write_text(
        "#!/usr/bin/env python3\n"
        "import hashlib, json, subprocess, sys\n"
        "from pathlib import Path\n"
        "prompt = sys.stdin.read()\n"
        "fields = dict(line.split(': ', 1) for line in prompt.splitlines() "
        "if line.startswith(('Task id: ', 'Attempt id: ')))\n"
        "paths = [Path('backend/jusik/broker_cost_profiles.py'), "
        "Path('backend/tests/test_broker_cost_profiles.py')]\n"
        "for path in paths: path.write_text(path.read_text() + '# fixed gap\\n')\n"
        "subprocess.run(['git', 'add', 'backend'], check=True, capture_output=True)\n"
        "subprocess.run(['git', 'commit', '-m', 'product correction'], "
        "check=True, capture_output=True)\n"
        "head = subprocess.check_output(['git', 'rev-parse', 'main'], "
        "text=True).strip()\n"
        "payload = {'task_id': fields['Task id'], 'attempt_id': fields['Attempt id'], "
        "'status': 'completed', 'tests_passed': True, "
        f"'review_passed': {self_review!r}, "
        "'integrated_commit': head, 'handoff_path': str(paths[0].resolve()), "
        "'evidence': [{'path': str(p.resolve()), 'sha256': "
        "hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths]}\n"
        "Path(sys.argv[sys.argv.index('-o')+1]).write_text(json.dumps(payload))\n"
    )
    fake.chmod(0o700)


@pytest.mark.parametrize("area", ["r2-01", "r2-02"])
def test_fresh_roadmap_code_proposal_freezes_engineering_authority(
    tmp_path: Path,
    area: str,
) -> None:
    _, store, _ = _pending(tmp_path, area=area)
    pending = store.pending_roadmap_scope()
    assert isinstance(pending, PendingRoadmapCodeScope)
    assert pending.execution_kind == "engineering_code"
    assert store.task("roadmap-audit-v1") is None


def test_execution_contract_overrides_nested_roles_in_task_prose(
    tmp_path: Path,
) -> None:
    config, store, fake = _pending(tmp_path, nested_request=True)
    _approve(config, store, fake)
    task = store.task("roadmap-audit-v1")
    assert task is not None
    assert "Objective: audit research readiness." in task.prompt
    assert "overrides any delegation" in task.prompt
    assert task.prompt.endswith("owns independent review and final completion.")
    assert "review_passed=false and followup=null" in task.prompt
    assert runner.COMMON_PROMPT not in task.prompt


def test_code_delivery_requires_separate_host_review_and_survives_restart(
    tmp_path: Path,
) -> None:
    config, store, fake = _pending(tmp_path)
    original_roadmap = load_roadmap(config.repo).digest
    _approve(config, store, fake)
    task = store.task("roadmap-audit-v1")
    assert task is not None and task.task_kind == "engineering" and task.area == "r2-02"
    assert task.engineering_status is None and task.investment_status is None
    assert "single implementer" in task.prompt
    _implementation(fake)
    candidate = runner.run_once(config)
    assert candidate.reason == "independent_review_pending"
    restarted = RunnerStore(store.db_path)
    assert restarted.review_candidate() is not None
    assert restarted.engineering_spec(task.id) == store.engineering_spec(task.id)
    _fake_reviewer(fake, verdict="PASS")
    assert runner.run_once(config).status == "completed"
    done = restarted.task(task.id)
    assert done is not None
    assert (done.canonical_state, done.engineering_status, done.investment_status) == (
        "DONE",
        "ENGINEERING_COMPLETE",
        "NOT_EVALUATED",
    )
    assert load_roadmap(config.repo).digest == original_roadmap


def test_code_child_self_review_cannot_complete(tmp_path: Path) -> None:
    config, store, fake = _pending(tmp_path)
    _approve(config, store, fake)
    _implementation(fake, self_review=True)
    assert runner.run_once(config).reason == "completion_invalid"
    assert store.review_candidate() is None


def test_v1_scope_response_cannot_authorize_code(tmp_path: Path) -> None:
    config, store, fake = _pending(tmp_path)
    _fake_scope(fake)
    assert runner.run_once(config).reason == "roadmap_scope_invalid"
    assert store.task("roadmap-audit-v1") is None


@pytest.mark.parametrize("change", ["head", "source", "phase", "mandate", "spec"])
def test_changed_code_authority_blocks_dispatch(tmp_path: Path, change: str) -> None:
    config, store, fake = _pending(tmp_path)
    _approve(config, store, fake)
    if change == "spec":
        with sqlite3.connect(store.db_path) as db:
            db.execute(
                "UPDATE approved_roadmap_code_specs SET spec_sha256=?", ("0" * 64,)
            )
    else:
        relative = {
            "head": "README.md",
            "source": "backend/jusik/broker_cost_profiles.py",
            "phase": "docs/investment-development-roadmap.md",
            "mandate": "docs/research-mandate.json",
        }[change]
        path = config.repo / relative
        path.write_text(path.read_text() + "\n" if path.exists() else "new head\n")
        _git(config.repo, "add", relative)
        _git(config.repo, "commit", "-m", "changed input")
    runner.run_once(config)
    task = store.task("roadmap-audit-v1")
    assert task is not None and task.attempt_count == 0
    assert task.engineering_status is None


@pytest.mark.parametrize("state", ["blocked", "waiting_external"])
def test_blocked_or_waiting_code_task_does_not_stall_independent_ready(
    tmp_path: Path, state: str
) -> None:
    config, store, fake = _pending(tmp_path)
    _approve(config, store, fake)
    assert store.quarantine(
        "roadmap-audit-v1",
        state,
        {"blocker_reason": "fixture", "next_eligible_retry": None},
    )
    spec = ENGINEERING_SPEC_BY_ID["lab-paper-execution-contract-v1"]
    assert store.enqueue(spec.id, spec.area, spec.prompt, task_kind="engineering")
    _fake_blocked_child(fake)
    result = runner.run_once(config)
    assert result.task_id == spec.id and result.status == "blocked"


def test_scope_registration_rolls_back_spec_and_task_together(tmp_path: Path) -> None:
    config, store, _ = _pending(tmp_path)
    pending = store.pending_roadmap_scope()
    assert isinstance(pending, PendingRoadmapCodeScope)
    review_id = "review-rollback"
    review = RoadmapCodeScopeReview.model_validate(
        _scope_receipt(pending, review_id).model_dump()
        | {
            "schema_version": 2,
            "execution_kind": "engineering_code",
            "owned_file_hashes": pending.owned_file_hashes,
            "code_contract_digest": pending.code_contract_digest,
        }
    )
    assert store.start_roadmap_scope_review(
        pending, review_id, tmp_path / "output", datetime.now(UTC).isoformat()
    )
    with sqlite3.connect(store.db_path) as db:
        db.execute(
            "CREATE TRIGGER fail_spec BEFORE INSERT ON approved_roadmap_code_specs "
            "BEGIN SELECT RAISE(ABORT,'rollback'); END"
        )
    with pytest.raises(sqlite3.IntegrityError):
        store.approve_roadmap_scope(
            pending, review_id, review, config.repo, code_spec(pending).prompt, "a" * 64
        )
    assert store.task(pending.proposal.id) is None
    assert store.pending_roadmap_scope() == pending
    assert RunnerStore(store.db_path).roadmap_code_scope(pending.proposal.id) is None


@pytest.mark.parametrize("mutation", ["pair", "hash"])
def test_code_contract_rejects_pair_and_hash_mutation(
    tmp_path: Path, mutation: str
) -> None:
    _, store, _ = _pending(tmp_path)
    pending = store.pending_roadmap_scope()
    assert isinstance(pending, PendingRoadmapCodeScope)
    hashes = dict(pending.owned_file_hashes)
    if mutation == "pair":
        hashes["../outside.py"] = hashes.pop(next(iter(hashes)))
    else:
        hashes[next(iter(hashes))] = "0" * 64
    with pytest.raises(ValueError):
        validate_code_contract(pending.model_copy(update={"owned_file_hashes": hashes}))


def test_review_rejection_is_bounded_and_never_promotes(tmp_path: Path) -> None:
    config, store, fake = _pending(tmp_path)
    _approve(config, store, fake)
    _implementation(fake)
    assert runner.run_once(config).reason == "independent_review_pending"
    config = config.model_copy(
        update={
            "planning_enabled": False,
            "automatic_engineering_backlog": False,
            "automatic_engineering_discovery": False,
        }
    )
    _fake_reviewer(fake, verdict="FAIL")
    runner.run_once(config)
    runner.run_once(config)
    before = store.launch_count(datetime.now(UTC).strftime("%Y-%m-%d"))
    runner.run_once(config)
    assert store.launch_count(datetime.now(UTC).strftime("%Y-%m-%d")) == before
    task = store.task("roadmap-audit-v1")
    assert task is not None and task.canonical_state == "WAITING_EXTERNAL"
    assert task.engineering_status is None


def test_phase_change_after_candidate_prevents_completion(tmp_path: Path) -> None:
    config, store, fake = _pending(tmp_path)
    _approve(config, store, fake)
    _implementation(fake)
    assert runner.run_once(config).reason == "independent_review_pending"
    path = config.repo / "docs/investment-development-roadmap.md"
    path.write_text(path.read_text().replace("- [x] **R0-", "- [ ] **R0-", 1))
    _git(config.repo, "add", "docs")
    _git(config.repo, "commit", "-m", "phase now unmet")
    _fake_reviewer(fake, verdict="PASS")
    runner.run_once(
        config.model_copy(
            update={
                "planning_enabled": False,
                "automatic_engineering_backlog": False,
                "automatic_engineering_discovery": False,
            }
        )
    )
    task = store.task("roadmap-audit-v1")
    assert task is not None and task.engineering_status is None


def test_legacy_scope_and_rows_survive_additive_registry_initialization(
    tmp_path: Path,
) -> None:
    config, store, fake = _pending(tmp_path, area="r1-01")
    _fake_scope(fake)
    assert runner.run_once(config).reason == "roadmap_scope_approved"
    tables = ("tasks", "attempts", "roadmap_planning_scopes", "roadmap_scope_attempts")
    with sqlite3.connect(store.db_path) as db:
        before = {
            table: db.execute(f"SELECT * FROM {table}").fetchall() for table in tables
        }
        db.execute("DROP TABLE approved_roadmap_code_specs")
    RunnerStore(store.db_path)
    restarted = RunnerStore(store.db_path)
    with sqlite3.connect(store.db_path) as db:
        after = {
            table: db.execute(f"SELECT * FROM {table}").fetchall() for table in tables
        }
    assert after == before
    assert restarted.engineering_spec("roadmap-audit-v1") is None
    legacy = restarted.task("roadmap-audit-v1")
    assert legacy is not None and legacy.task_kind == "research"


@pytest.mark.parametrize("mutation", ["receipt", "review_attempt", "symlink"])
def test_approved_provenance_and_paths_fail_closed(
    tmp_path: Path, mutation: str
) -> None:
    config, store, fake = _pending(tmp_path)
    _approve(config, store, fake)
    if mutation == "symlink":
        path = config.repo / "backend/jusik/broker_cost_profiles.py"
        outside = tmp_path / "outside.py"
        outside.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(outside)
        with pytest.raises(ValueError):
            store.validate_roadmap_code_task(
                "roadmap-audit-v1", config.repo, before_dispatch=True
            )
    else:
        with sqlite3.connect(store.db_path) as db:
            if mutation == "receipt":
                raw = db.execute(
                    "SELECT receipt_json FROM roadmap_planning_scopes"
                ).fetchone()[0]
                receipt = json.loads(raw)
                receipt["reason"] = (
                    "Altered approval explanation is not the original receipt."
                )
                db.execute(
                    "UPDATE roadmap_planning_scopes SET receipt_json=?",
                    (json.dumps(receipt),),
                )
            else:
                db.execute("UPDATE roadmap_scope_attempts SET status='failed'")
        with pytest.raises(ValueError):
            store.engineering_spec("roadmap-audit-v1")


@pytest.mark.parametrize("state", ["queued", "running", "blocked"])
def test_roadmap_code_task_preserves_area_reservation(
    tmp_path: Path, state: str
) -> None:
    config, store, fake = _pending(tmp_path)
    _approve(config, store, fake)
    task = store.task("roadmap-audit-v1")
    assert task is not None
    if state != "queued":
        store.claim(task, "implementation", tmp_path / "out", tmp_path / "err")
        if state == "blocked":
            store.finish("implementation", task.id, "blocked")
    with pytest.raises(RoadmapError):
        validate_enqueue(
            load_roadmap(config.repo), store.tasks(), "duplicate-v1", "r2-02"
        )


def test_roadmap_code_task_counts_toward_roadmap_queue_cap(tmp_path: Path) -> None:
    config, store, fake = _pending(tmp_path)
    _approve(config, store, fake)
    for index in range(7):
        assert store.enqueue(f"other-{index}", "offline", "fixture")
    with pytest.raises(RoadmapError, match="queue"):
        validate_enqueue(load_roadmap(config.repo), store.tasks(), "new-v1", "r1-01")


def test_completion_transaction_rechecks_roadmap_gate(tmp_path: Path) -> None:
    config, store, fake = _pending(tmp_path)
    _approve(config, store, fake)
    _implementation(fake)
    assert runner.run_once(config).reason == "independent_review_pending"
    candidate = store.review_candidate()
    assert candidate is not None
    context = runner._review_context(candidate, "final-review", config)
    assert store.claim_review(
        candidate,
        "final-review",
        tmp_path / "receipt",
        context,
        datetime.now(UTC).isoformat(),
    )
    path = config.repo / "docs/investment-development-roadmap.md"
    path.write_text(path.read_text().replace("- [x] **R0-", "- [ ] **R0-", 1))
    with pytest.raises(ValueError):
        store.finish_review(
            candidate,
            "final-review",
            status="completed",
            receipt=context | {"verdict": "PASS"},
            repo=config.repo,
        )
    task = store.task(candidate.task.id)
    assert task is not None and task.engineering_status is None


def test_changed_nonowned_input_blocks_completion_review(tmp_path: Path) -> None:
    config, store, fake = _pending(tmp_path, external_input=True)
    _approve(config, store, fake)
    _implementation(fake)
    assert runner.run_once(config).reason == "independent_review_pending"
    (tmp_path / "artifacts/input.txt").write_text("changed input\n")
    _fake_reviewer(fake, verdict="PASS")
    runner.run_once(
        config.model_copy(
            update={
                "planning_enabled": False,
                "automatic_engineering_backlog": False,
                "automatic_engineering_discovery": False,
            }
        )
    )
    task = store.task("roadmap-audit-v1")
    assert task is not None and task.engineering_status is None
    assert store.review_candidate() is None


def test_deleted_code_registry_never_falls_back_to_legacy_paper_spec(
    tmp_path: Path,
) -> None:
    config, store, fake = _pending(tmp_path)
    _approve(config, store, fake)
    with sqlite3.connect(store.db_path) as db:
        db.execute("DELETE FROM approved_roadmap_code_specs")
    assert runner._engineering_spec(store, "roadmap-audit-v1") is None
    with pytest.raises(ValueError, match="provenance missing"):
        store.validate_roadmap_code_task(
            "roadmap-audit-v1", config.repo, before_dispatch=True
        )


@pytest.mark.parametrize("style", ["tilde", "relative", "dotdot"])
def test_approved_evidence_paths_survive_restart_and_cwd_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, style: str
) -> None:
    config, store, fake = _pending(tmp_path, evidence_style=style)
    original = store.pending_roadmap_scope()
    assert isinstance(original, PendingRoadmapCodeScope)
    other_cwd = tmp_path / "other-cwd"
    other_cwd.mkdir()
    monkeypatch.chdir(other_cwd)
    decoy = other_cwd / "backend/jusik/broker_cost_profiles.py"
    decoy.parent.mkdir(parents=True)
    decoy.write_text("unapproved same relative path\n")
    _approve(config, store, fake)
    restarted = RunnerStore(store.db_path)
    frozen = restarted.roadmap_code_scope("roadmap-audit-v1")
    assert frozen is not None
    assert frozen.result == original.result
    assert frozen.proposal_digest == original.proposal_digest
    assert frozen.evidence_digest == original.evidence_digest
    _implementation(fake)
    assert runner.run_once(config).reason == "independent_review_pending"
    _fake_reviewer(fake, verdict="PASS")
    assert runner.run_once(config).status == "completed"
    task = restarted.task("roadmap-audit-v1")
    assert task is not None and task.engineering_status == "ENGINEERING_COMPLETE"


def test_evidence_freeze_rejects_symlink_ancestor_before_resolution(
    tmp_path: Path,
) -> None:
    target = tmp_path / "actual"
    target.mkdir()
    (target / "input.txt").write_text("fixed input\n")
    alias = tmp_path / "alias"
    alias.symlink_to(target, target_is_directory=True)
    for raw in (alias / "input.txt", alias / ".." / "actual/input.txt"):
        with pytest.raises(ValueError, match="symlink"):
            canonical_input_path(raw)


def test_frozen_nonowned_evidence_rejects_symlink_and_mapping_tamper(
    tmp_path: Path,
) -> None:
    config, store, fake = _pending(tmp_path, evidence_style="tilde")
    _approve(config, store, fake)
    pending = store.roadmap_code_scope("roadmap-audit-v1")
    assert pending is not None
    original = Path(next(iter(pending.canonical_evidence_paths.values())))
    replacement = tmp_path / "replacement.txt"
    replacement.write_bytes(original.read_bytes())
    mapping = {key: str(replacement) for key in pending.canonical_evidence_paths}
    with pytest.raises(ValueError, match="contract changed"):
        validate_code_contract(
            pending.model_copy(update={"canonical_evidence_paths": mapping})
        )
    original.unlink()
    original.symlink_to(replacement)
    with pytest.raises(ValueError, match="symlink"):
        store.validate_roadmap_code_task(
            "roadmap-audit-v1", config.repo, before_dispatch=True
        )
