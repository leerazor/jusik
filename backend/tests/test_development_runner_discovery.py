"""Offline discovery dispatch and durable engineering scope tests."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

import pytest
from test_development_runner_backlog import _config, _fake_blocked_child, _store

from jusik import development_runner as runner
from jusik import development_runner_store as runner_store
from jusik.development_runner_contract import AUTOMATIC_ENGINEERING_BACKLOG
from jusik.development_runner_discovery import (
    DiscoveryProposal,
    DiscoveryResult,
    ScopeReview,
    SourceEvidence,
    digest,
    proposal_digest,
    source_fingerprint,
    spec_from_proposal,
    strict_output_schema,
    validate_proposal,
)
from jusik.development_runner_store import RunnerStore, RunnerTask
from jusik.research_mandate_governance import validate_dispatch_gate


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


def _exhausted(tmp_path: Path, fake: Path) -> tuple[runner.RunnerConfig, RunnerStore]:
    config = _config(tmp_path, fake).model_copy(
        update={"automatic_engineering_discovery": True}
    )
    for module in (
        "paper_execution_contract",
        "research_market_calendar",
        "market_loss_accounting",
    ):
        for relative in (
            f"backend/jusik/{module}.py",
            f"backend/tests/test_{module}.py",
        ):
            path = config.repo / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# offline product fixture\n", encoding="utf-8")
    _git(config.repo, "add", "backend")
    _git(config.repo, "commit", "-m", "offline product fixtures")
    store = _store(config)
    for spec in AUTOMATIC_ENGINEERING_BACKLOG:
        assert store.enqueue(spec.id, spec.area, spec.prompt, task_kind="engineering")
        assert store.quarantine(
            spec.id,
            "blocked",
            {"blocker_reason": "complete", "next_eligible_retry": None},
        )
    return config, store


def _fake_child(path: Path, mode: str = "pass") -> None:
    path.write_text(
        "#!/usr/bin/env python3\n"
        "import hashlib, json, sys\n"
        "from pathlib import Path\n"
        f"mode = {mode!r}\n"
        "prompt = sys.stdin.read()\n"
        "fields = dict(line.split(': ', 1) for line in prompt.splitlines() "
        "if line.startswith(('Planner attempt id: ', 'Baseline HEAD: ', "
        "'Fingerprint: ', 'Proposal digest: ', 'Owned paths: ')))\n"
        "if 'Proposal: ' in prompt:\n"
        "    proposal = json.loads(prompt.split('Proposal: ', 1)[1].splitlines()[0])\n"
        "    verdict = 'REJECT' if mode in ('reject_all', 'repeat') or "
        "(mode == 'reject_first' and "
        "proposal['module'] == 'paper_execution_contract') else 'PASS'\n"
        "    payload = {'verdict': verdict, "
        "'proposal_digest': fields['Proposal digest'], "
        "'planner_attempt_id': fields['Planner attempt id'], "
        "'baseline_head': fields['Baseline HEAD'], "
        "'fingerprint': fields['Fingerprint'], "
        "'owned_paths': json.loads(fields['Owned paths']), "
        "'reason': 'reproduced product gap' if verdict == 'PASS' else "
        "'already completed product gap'}\n"
        "elif mode == 'no_work':\n"
        "    payload = {'status': 'no_work', 'proposal': None, "
        "'inspected_domains': "
        "['paper_execution_contract', 'research_market_calendar'], "
        "'resume_condition': 'source or task state changes', "
        "'alternatives': ['inspect another offline module'], "
        "'planner_attempt_id': fields['Planner attempt id'], "
        "'baseline_head': fields['Baseline HEAD'], "
        "'fingerprint': fields['Fingerprint']}\n"
        "else:\n"
        "    feedback = json.loads(prompt.split('Prior scope rejection feedback: ', 1)"
        "[1].splitlines()[0])\n"
        "    module = ('paper_execution_contract' if mode == 'repeat' "
        "or not feedback else "
        "'research_market_calendar' if len(feedback) == 1 else "
        "'market_loss_accounting')\n"
        "    paths = [f'backend/jusik/{module}.py', "
        "f'backend/tests/test_{module}.py']\n"
        "    evidence = [{'path': name, 'sha256': "
        "hashlib.sha256(Path(name).read_bytes()).hexdigest()} for name in paths]\n"
        "    proposal = {'module': module, "
        "'goal': 'Fix reproducible offline product accounting gap', "
        "'reproduction': 'Run focused test with duplicate records "
        "and observe wrong value', "
        "'gap': 'Current source accepts duplicate records in one offline scenario', "
        "'tests': 'Add focused duplicate-record regression and normal case', "
        "'stop_condition': 'Source fix and regression pass without activation', "
        "'evidence': evidence}\n"
        "    payload = {'status': 'proposal', 'proposal': proposal, "
        "'planner_attempt_id': fields['Planner attempt id'], "
        "'baseline_head': fields['Baseline HEAD'], "
        "'fingerprint': fields['Fingerprint']}\n"
        "Path(sys.argv[sys.argv.index('-o') + 1]).write_text(json.dumps(payload))\n",
        encoding="utf-8",
    )
    path.chmod(0o700)


def _fake_pausing_child(path: Path, db_path: Path) -> None:
    path.write_text(
        "#!/usr/bin/env python3\n"
        "import sqlite3, sys\n"
        "from pathlib import Path\n"
        f"with sqlite3.connect({str(db_path)!r}) as db:\n"
        '    db.execute("INSERT INTO runner_meta(key,value) '
        "VALUES('paused','1') ON CONFLICT(key) DO UPDATE SET value='1'\")\n"
        "Path(sys.argv[sys.argv.index('-o') + 1]).write_text('{}')\n",
        encoding="utf-8",
    )
    path.chmod(0o700)


def _fake_transport_failure(path: Path, error: dict[str, object] | None) -> None:
    event = {"type": "turn.failed", "error": error} if error is not None else None
    path.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        f"event = {event!r}\n"
        "if event is not None:\n"
        "    print(json.dumps(event), flush=True)\n"
        "sys.exit(1)\n",
        encoding="utf-8",
    )
    path.chmod(0o700)


@pytest.mark.parametrize(
    ("error", "kind"),
    [
        ({"message": "model is at capacity"}, "capacity"),
        ({"status_code": 429}, "rate_limit"),
        ({"status": 503}, "server"),
        ({"code": "connection_error"}, "network"),
        ({"message": "unexpected status 401 Unauthorized"}, "auth"),
        ({"message": "unexpected failure"}, None),
    ],
)
def test_only_structured_turn_error_classifies_transport(
    tmp_path: Path,
    error: dict[str, object],
    kind: str | None,
) -> None:
    transcript = tmp_path / "stdout.jsonl"
    transcript.write_text(
        json.dumps({"type": "item.completed", "item": {"text": "status 401"}})
        + "\n"
        + json.dumps({"type": "turn.failed", "error": error})
        + "\n",
        encoding="utf-8",
    )
    assert runner._discovery_transport_kind(transcript) == kind


def test_discovery_transport_retry_survives_restart_without_early_launch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = [datetime.now(UTC)]
    monkeypatch.setattr(runner_store, "utc_now", lambda: clock[0].isoformat())
    fake = tmp_path / "fake-transport.py"
    _fake_transport_failure(fake, {"code": "model_capacity", "message": "busy"})
    config, store = _exhausted(tmp_path, fake)
    first = runner.run_once(config)
    assert first.reason == "discovery_codex_exit"
    mandate = validate_dispatch_gate(config.repo).digest
    fingerprint = source_fingerprint(config.repo, mandate, store.discovery_snapshot())
    cycle = store.discovery_cycle(fingerprint)
    assert cycle is not None and cycle["stage"] == "discover"
    assert cycle["transient_failures"] == 1
    assert cycle["retry_kind"] == "capacity"
    assert datetime.fromisoformat(cycle["retry_after"]) == clock[0] + timedelta(
        minutes=5
    )
    day = datetime.now(UTC).strftime("%Y-%m-%d")
    assert runner.run_once(config).reason == "discovery_retry_scheduled"
    assert RunnerStore(store.db_path).launch_count(day) == 1
    assert not store.start_discovery_attempt(
        fingerprint,
        cycle["baseline_head"],
        mandate,
        store.discovery_snapshot(),
        "early-attempt",
        "discover",
        tmp_path / "early.json",
        datetime.now(UTC).isoformat(),
    )
    clock[0] += timedelta(minutes=5, seconds=1)
    second = runner.run_once(config)
    assert second.reason == "discovery_codex_exit"
    cycle = RunnerStore(store.db_path).discovery_cycle(fingerprint)
    assert cycle is not None and cycle["transient_failures"] == 2
    assert datetime.fromisoformat(cycle["retry_after"]) == clock[0] + timedelta(
        minutes=15
    )
    assert runner.run_once(config).reason == "discovery_retry_scheduled"
    assert store.launch_count(day) == 2
    clock[0] += timedelta(minutes=15, seconds=1)
    _fake_child(fake)
    assert runner.run_once(config).reason == "discovery_scope"
    cycle = store.discovery_cycle(fingerprint)
    assert cycle is not None and cycle["transient_failures"] == 0
    assert cycle["retry_after"] is None and cycle["retry_kind"] is None
    _fake_transport_failure(fake, {"code": "network_error", "message": "disconnected"})
    assert runner.run_once(config).reason == "discovery_codex_exit"
    cycle = store.discovery_cycle(fingerprint)
    assert cycle is not None and cycle["stage"] == "scope"
    assert cycle["proposal_count"] == 1 and cycle["retry_kind"] == "network"
    assert store.discovery_active_proposal(fingerprint) is not None
    assert runner.run_once(config).reason == "discovery_retry_scheduled"
    clock[0] += timedelta(minutes=5, seconds=1)
    _fake_child(fake)
    assert runner.run_once(config).reason == "discovery_approved"
    cycle = store.discovery_cycle(fingerprint)
    assert cycle is not None and cycle["stage"] == "terminal"
    assert cycle["transient_failures"] == 0
    assert cycle["retry_after"] is None and cycle["retry_kind"] is None


def test_discovery_transport_backoff_caps_at_one_hour(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = [datetime.now(UTC)]
    monkeypatch.setattr(runner_store, "utc_now", lambda: clock[0].isoformat())
    fake = tmp_path / "fake-rate-limit.py"
    _fake_transport_failure(fake, {"status_code": 429})
    config, store = _exhausted(tmp_path, fake)
    for count, minutes in enumerate((5, 15, 60, 60), 1):
        assert runner.run_once(config).reason == "discovery_codex_exit"
        status = store.discovery_status()
        assert status is not None and status["transient_failures"] == count
        assert status["retry_kind"] == "rate_limit"
        assert isinstance(status["retry_after"], str)
        assert datetime.fromisoformat(status["retry_after"]) == clock[0] + timedelta(
            minutes=minutes
        )
        clock[0] += timedelta(minutes=minutes, seconds=1)
    assert store.discovery_status()["stage"] == "discover"  # type: ignore[index]


def test_ready_engineering_task_preempts_scheduled_discovery(tmp_path: Path) -> None:
    fake = tmp_path / "fake-capacity.py"
    _fake_transport_failure(fake, {"code": "model_capacity"})
    config, store = _exhausted(tmp_path, fake)
    assert runner.run_once(config).reason == "discovery_codex_exit"
    ready_spec = AUTOMATIC_ENGINEERING_BACKLOG[0]
    with sqlite3.connect(store.db_path) as db:
        db.execute("UPDATE tasks SET status='queued' WHERE id=?", (ready_spec.id,))
    _fake_blocked_child(fake)
    result = runner.run_once(config)
    assert result.task_id == ready_spec.id


def test_terminated_discovery_timeout_schedules_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = tmp_path / "fake-slow.py"
    fake.write_text(
        "#!/usr/bin/env python3\nimport time\ntime.sleep(30)\n", encoding="utf-8"
    )
    fake.chmod(0o700)
    config, store = _exhausted(tmp_path, fake)
    monkeypatch.setattr(runner, "_child_idle_expired", lambda *args: True)
    assert runner.run_once(config).reason == "discovery_timeout"
    status = store.discovery_status()
    assert status is not None and status["retry_kind"] == "timeout"
    assert status["stage"] == "discover"


def test_discovery_401_waits_six_hours_without_reconfiguration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = [datetime.now(UTC)]
    monkeypatch.setattr(runner_store, "utc_now", lambda: clock[0].isoformat())
    fake = tmp_path / "fake-auth.py"
    _fake_transport_failure(fake, {"message": "unexpected status 401 Unauthorized"})
    config, store = _exhausted(tmp_path, fake)
    assert runner.run_once(config).reason == "discovery_codex_exit"
    status = store.discovery_status()
    assert status is not None and status["retry_kind"] == "auth"
    assert status["transient_failures"] == 1
    assert isinstance(status["retry_after"], str)
    assert datetime.fromisoformat(status["retry_after"]) == clock[0] + timedelta(
        hours=6
    )
    day = datetime.now(UTC).strftime("%Y-%m-%d")
    assert runner.run_once(config).reason == "discovery_retry_scheduled"
    assert store.launch_count(day) == 1
    clock[0] += timedelta(hours=6, seconds=1)
    _fake_child(fake)
    assert runner.run_once(config).reason == "discovery_scope"


@pytest.mark.parametrize(
    "error",
    [None, {"message": "401 in command output"}, {"message": "unexpected failure"}],
)
def test_unstructured_or_unknown_failure_keeps_finite_terminal_limit(
    tmp_path: Path,
    error: dict[str, object] | None,
) -> None:
    fake = tmp_path / "fake-unknown.py"
    _fake_transport_failure(fake, error)
    config, store = _exhausted(tmp_path, fake)
    assert runner.run_once(config).reason == "discovery_codex_exit"
    assert runner.run_once(config).reason == "discovery_codex_exit"
    status = store.discovery_status()
    assert status is not None and status["stage"] == "terminal"
    assert status["transient_failures"] == 0
    assert status["retry_after"] is None
    assert (
        runner.run_once(config).reason == "discovery_discovery_infrastructure_exhausted"
    )


def test_exhausted_backlog_dispatches_discovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _config(tmp_path, tmp_path / "unused").model_copy(
        update={"automatic_engineering_discovery": True}
    )
    store = _store(config)
    for spec in AUTOMATIC_ENGINEERING_BACKLOG:
        assert store.enqueue(spec.id, spec.area, spec.prompt, task_kind="engineering")
        assert store.quarantine(
            spec.id,
            "blocked",
            {"blocker_reason": "complete", "next_eligible_retry": None},
        )
    calls: list[str] = []

    def fake_discovery(*args: object, **kwargs: object) -> runner.RunResult:
        calls.append("discovery")
        return runner.RunResult("idle", reason="discovery_dispatched")

    monkeypatch.setattr(
        runner, "_run_engineering_discovery", fake_discovery, raising=False
    )
    result = runner.run_once(config)
    assert result.reason == "discovery_dispatched"
    assert calls == ["discovery"]


def test_structured_schemas_require_every_nested_property() -> None:
    for model in (DiscoveryResult, ScopeReview):
        schema = strict_output_schema(model)

        def inspect(value: object) -> None:
            if isinstance(value, dict):
                properties = value.get("properties")
                if isinstance(properties, dict):
                    assert set(value["required"]) == set(properties)
                    assert value["additionalProperties"] is False
                for child in value.values():
                    inspect(child)
            elif isinstance(value, list):
                for child in value:
                    inspect(child)

        inspect(schema)


def test_completion_schema_guides_blocker_identity_and_retry_deadline() -> None:
    blocker = runner._completion_schema(set(), engineering=True)["properties"][
        "blocker"
    ]["properties"]
    identity = blocker["dependency_identity"]
    deadline = blocker["next_eligible_retry"]
    assert identity["pattern"] == "^(missing|[a-f0-9]{64})$"
    assert all(
        word in identity["description"] for word in ("null", "missing", "SHA-256")
    )
    assert "UTC" in deadline["description"]
    assert "bounded" in deadline["description"]
    assert "null" in deadline["description"]


@pytest.mark.parametrize(
    ("dependency_identity", "retry_policy", "next_eligible_retry"),
    [
        ("attempt offline cache", "manual", None),
        (None, "bounded", None),
        ("0" * 64, "manual", "2026-09-26T00:00:00Z"),
    ],
)
def test_malformed_operational_blocker_remains_fail_closed(
    tmp_path: Path,
    dependency_identity: str | None,
    retry_policy: str,
    next_eligible_retry: str | None,
) -> None:
    config = runner.RunnerConfig(
        repo=tmp_path,
        state_dir=tmp_path / "state",
        history_dir=tmp_path / "history",
        history_db=tmp_path / "history.db",
        artifact_dir=tmp_path / "artifact",
    )
    task = RunnerTask(
        id="offline-task",
        area="__engineering__",
        prompt="offline task",
        status="running",
        attempt_count=1,
        next_allowed_at=None,
        last_attempt_id="attempt",
        depends_on=None,
        task_kind="engineering",
    )
    payload = {
        "task_id": task.id,
        "attempt_id": "attempt",
        "status": "waiting_external",
        "tests_passed": False,
        "review_passed": False,
        "blocked_reason": "dependency_setup",
        "blocker": {
            "blocker_reason": "dependency_setup",
            "attempted_actions": [],
            "dependency": None,
            "dependency_identity": dependency_identity,
            "resume_condition": "owned environment available",
            "retry_policy": retry_policy,
            "next_eligible_retry": next_eligible_retry,
            "alternative_ready_tasks": [],
        },
    }
    with pytest.raises(ValueError, match="completion schema invalid"):
        runner.validate_completion(payload, task, "attempt", config)


def test_dynamic_implementation_receives_existing_dependency_permission(
    tmp_path: Path,
) -> None:
    discovery_child = tmp_path / "fake-discovery.py"
    _fake_child(discovery_child)
    config, _ = _exhausted(tmp_path, discovery_child)
    assert runner.run_once(config).reason == "discovery_scope"
    assert runner.run_once(config).reason == "discovery_approved"
    implementation_child = tmp_path / "fake-implementation.py"
    _fake_blocked_child(implementation_child)
    result = runner.run_once(
        config.model_copy(update={"codex": str(implementation_child)})
    )
    assert result.status == "blocked" and result.attempt_id is not None
    prompt = (
        config.state_dir / "attempts" / result.attempt_id / "prompt.txt"
    ).read_text(encoding="utf-8")
    assert runner.OFFLINE_DEPENDENCY_GUIDANCE in runner.COMMON_PROMPT
    assert runner.OFFLINE_DEPENDENCY_GUIDANCE in prompt


def test_common_guidance_scopes_provider_restriction_to_offline_validation() -> None:
    guidance = runner.OFFLINE_DEPENDENCY_GUIDANCE
    assert (
        "During offline product validation, do not access market-data providers"
        in guidance
    )
    assert "Real brokerage orders remain forbidden for every task." in guidance
    assert guidance in runner.COMMON_PROMPT


def test_no_work_requires_actual_allowlisted_inspection() -> None:
    with pytest.raises(ValueError, match="allowlisted"):
        DiscoveryResult(
            planner_attempt_id="attempt",
            baseline_head="a" * 40,
            fingerprint="b" * 64,
            status="no_work",
            inspected_domains=["untracked", "another untracked"],
            resume_condition="source or task state changes",
            alternatives=["inspect another offline module"],
        )


def test_proposal_scope_pass_registers_once_and_survives_restart(
    tmp_path: Path,
) -> None:
    fake = tmp_path / "fake-discovery.py"
    _fake_child(fake)
    config, store = _exhausted(tmp_path, fake)
    first = runner.run_once(config)
    assert (first.status, first.reason) == ("completed", "discovery_scope")
    assert not [task for task in store.tasks() if task.id.startswith("lab-discovery-")]
    second = runner.run_once(config)
    assert (second.status, second.reason) == ("completed", "discovery_approved")
    assert second.task_id is not None
    assert store.task(second.task_id) is not None
    restarted = RunnerStore(store.db_path, config.history_dir)
    spec = restarted.engineering_spec(second.task_id)
    assert spec is not None
    assert restarted.task(second.task_id).prompt == spec.prompt  # type: ignore[union-attr]
    assert runner._select_task(restarted, config.scope, None).id == second.task_id  # type: ignore[union-attr]
    with sqlite3.connect(store.db_path) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM approved_engineering_specs"
        ).fetchone() == (1,)
    assert restarted.discovery_status() is not None


def test_dynamic_spec_uses_existing_exact_diff_and_independent_review(
    tmp_path: Path,
) -> None:
    fake = tmp_path / "fake-discovery.py"
    _fake_child(fake)
    config, store = _exhausted(tmp_path, fake)
    assert runner.run_once(config).reason == "discovery_scope"
    registered = runner.run_once(config)
    assert registered.task_id is not None
    spec = store.engineering_spec(registered.task_id)
    assert spec is not None
    baseline = _git(config.repo, "rev-parse", "main")
    for relative in spec.owned_paths:
        with (config.repo / relative).open("a", encoding="utf-8") as output:
            output.write("# regression fix\n")
    _git(config.repo, "add", "backend")
    _git(config.repo, "commit", "-m", "offline product fix")
    current = _git(config.repo, "rev-parse", "main")
    task = store.task(spec.id)
    assert task is not None
    store.claim(
        task,
        "implementation",
        tmp_path / "completion.json",
        tmp_path / "stderr.log",
        baseline_head=baseline,
    )
    completion = {
        "task_id": task.id,
        "attempt_id": "implementation",
        "status": "completed",
        "integrated_commit": current,
        "evidence": [
            {
                "path": str(config.repo / relative),
                "sha256": hashlib.sha256(
                    (config.repo / relative).read_bytes()
                ).hexdigest(),
            }
            for relative in sorted(spec.owned_paths)
        ],
        "tests_passed": True,
        "review_passed": False,
        "handoff_path": str(config.repo / sorted(spec.owned_paths)[0]),
    }
    runner.validate_completion(
        completion, task, "implementation", config, baseline_head=baseline
    )
    store.finish(
        "implementation",
        task.id,
        "waiting_external",
        failure_code="independent_review_pending",
        evidence={"review_candidate_version": 1, "completion": completion},
    )
    reviewer = tmp_path / "fake-reviewer.py"
    reviewer.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        "from pathlib import Path\n"
        "prompt = sys.stdin.read()\n"
        "payload = json.loads(prompt.split('fields: ', 1)[1])\n"
        "payload['verdict'] = 'PASS'\n"
        "Path(sys.argv[sys.argv.index('-o') + 1]).write_text(json.dumps(payload))\n",
        encoding="utf-8",
    )
    reviewer.chmod(0o700)
    disabled = config.model_copy(
        update={"codex": str(reviewer), "automatic_engineering_discovery": False}
    )
    result = runner.run_once(disabled)
    assert (result.status, result.task_id) == ("completed", task.id)
    assert store.task(task.id).engineering_status == "ENGINEERING_COMPLETE"  # type: ignore[union-attr]


def test_scope_reject_feedback_leads_to_distinct_candidate(tmp_path: Path) -> None:
    fake = tmp_path / "fake-discovery.py"
    _fake_child(fake, "reject_first")
    config, store = _exhausted(tmp_path, fake)
    assert runner.run_once(config).reason == "discovery_scope"
    assert runner.run_once(config).reason == "discovery_discover"
    assert store.discovery_status()["reason"] == "scope_rejected"  # type: ignore[index]
    assert runner.run_once(config).reason == "discovery_scope"
    final = runner.run_once(config)
    assert final.reason == "discovery_approved"
    assert final.task_id is not None
    assert store.engineering_spec(final.task_id).owned_paths == frozenset(  # type: ignore[union-attr]
        {
            "backend/jusik/research_market_calendar.py",
            "backend/tests/test_research_market_calendar.py",
        }
    )
    with sqlite3.connect(store.db_path) as db:
        statuses = db.execute(
            "SELECT status FROM discovery_proposals ORDER BY rowid"
        ).fetchall()
    assert statuses == [("rejected",), ("approved",)]


def test_no_work_is_terminal_until_fingerprint_changes(tmp_path: Path) -> None:
    fake = tmp_path / "fake-discovery.py"
    _fake_child(fake, "no_work")
    config, store = _exhausted(tmp_path, fake)
    assert runner.run_once(config).reason == "discovery_terminal"
    day = datetime.now(UTC).strftime("%Y-%m-%d")
    launches = store.launch_count(day)
    assert runner.run_once(config).reason == "discovery_no_work"
    assert store.launch_count(day) == launches


def test_three_distinct_scope_rejections_stop_calls(tmp_path: Path) -> None:
    fake = tmp_path / "fake-discovery.py"
    _fake_child(fake, "reject_all")
    config, store = _exhausted(tmp_path, fake)
    outcomes = [runner.run_once(config).reason for _ in range(6)]
    assert outcomes == [
        "discovery_scope",
        "discovery_discover",
        "discovery_scope",
        "discovery_discover",
        "discovery_scope",
        "discovery_terminal",
    ]
    day = datetime.now(UTC).strftime("%Y-%m-%d")
    assert store.launch_count(day) == 6
    assert runner.run_once(config).reason == "discovery_proposal_cap_reached"
    assert store.launch_count(day) == 6
    assert all(not task.id.startswith("lab-discovery-") for task in store.tasks())


def test_duplicate_proposal_never_reaches_scope_again(tmp_path: Path) -> None:
    fake = tmp_path / "fake-discovery.py"
    _fake_child(fake, "repeat")
    config, store = _exhausted(tmp_path, fake)
    assert runner.run_once(config).reason == "discovery_scope"
    assert runner.run_once(config).reason == "discovery_discover"
    assert runner.run_once(config).reason == "discovery_discover"
    assert runner.run_once(config).reason == "discovery_terminal"
    with sqlite3.connect(store.db_path) as db:
        assert db.execute("SELECT COUNT(*) FROM discovery_proposals").fetchone() == (1,)
        assert db.execute(
            "SELECT COUNT(*) FROM approved_engineering_specs"
        ).fetchone() == (0,)


def test_stale_head_and_paused_scope_cannot_enqueue(tmp_path: Path) -> None:
    fake = tmp_path / "fake-discovery.py"
    _fake_child(fake)
    config, store = _exhausted(tmp_path, fake)
    assert runner.run_once(config).reason == "discovery_scope"
    mandate = validate_dispatch_gate(config.repo).digest
    fingerprint = source_fingerprint(config.repo, mandate, store.discovery_snapshot())
    store.pause()
    assert runner.run_once(config).status == "paused"
    store.resume()
    (config.repo / "README.md").write_text("docs-only head change\n", encoding="utf-8")
    _git(config.repo, "add", "README.md")
    _git(config.repo, "commit", "-m", "docs-only change")
    assert (
        source_fingerprint(config.repo, mandate, store.discovery_snapshot())
        == fingerprint
    )
    assert (
        source_fingerprint(config.repo, "0" * 64, store.discovery_snapshot())
        != fingerprint
    )
    assert runner.run_once(config).reason == "discovery_stale_head"
    assert runner.run_once(config).reason == "discovery_stale_head"
    assert not [task for task in store.tasks() if task.id.startswith("lab-discovery-")]


def test_discovery_launch_obeys_quota_and_cooldown(tmp_path: Path) -> None:
    fake = tmp_path / "fake-discovery.py"
    _fake_child(fake)
    config, store = _exhausted(tmp_path, fake)
    assert runner.run_once(config).reason == "discovery_scope"
    day = datetime.now(UTC).strftime("%Y-%m-%d")
    assert store.launch_count(day) == 1
    assert (
        runner.run_once(config.model_copy(update={"daily_launches": 1})).status
        == "quota"
    )
    assert (
        runner.run_once(
            config.model_copy(update={"daily_launches": None, "cooldown_seconds": 3600})
        ).status
        == "cooldown"
    )
    assert store.launch_count(day) == 1
    assert runner.run_once(config).reason == "discovery_approved"


def test_discovery_claim_rechecks_pause_snapshot_and_queue_cap(tmp_path: Path) -> None:
    fake = tmp_path / "fake-discovery.py"
    _fake_child(fake)
    config, store = _exhausted(tmp_path, fake)
    head = _git(config.repo, "rev-parse", "main")
    mandate = "a" * 64
    snapshot = store.discovery_snapshot()
    fingerprint = source_fingerprint(config.repo, mandate, snapshot)

    def claim(items: list[tuple[str, str, str | None]]) -> bool:
        return store.start_discovery_attempt(
            fingerprint,
            head,
            mandate,
            items,
            "attempt",
            "discover",
            tmp_path / "result.json",
            datetime.now(UTC).isoformat(),
        )

    store.pause()
    assert not claim(snapshot)
    store.resume()
    assert store.enqueue("new-ready", "offline", "other")
    assert not claim(snapshot)
    for index in range(7):
        assert store.enqueue(f"ready-{index}", "offline", "other")
    assert not claim(store.discovery_snapshot())
    assert store.discovery_cycle(fingerprint) is None
    with sqlite3.connect(store.db_path) as db:
        assert db.execute("SELECT COUNT(*) FROM discovery_attempts").fetchone() == (0,)


def test_uncertain_orphan_is_quarantined_without_relaunch(tmp_path: Path) -> None:
    fake = tmp_path / "fake-discovery.py"
    _fake_child(fake)
    config, store = _exhausted(tmp_path, fake)
    mandate = validate_dispatch_gate(config.repo).digest
    snapshot = store.discovery_snapshot()
    fingerprint = source_fingerprint(config.repo, mandate, snapshot)
    assert store.start_discovery_attempt(
        fingerprint,
        _git(config.repo, "rev-parse", "main"),
        mandate,
        snapshot,
        "orphan",
        "discover",
        tmp_path / "orphan.json",
        datetime.now(UTC).isoformat(),
    )
    day = datetime.now(UTC).strftime("%Y-%m-%d")
    assert store.launch_count(day) == 1
    assert runner.run_once(config).reason == "discovery orphan identity uncertain"
    cycle = store.discovery_cycle(fingerprint)
    assert cycle is not None and cycle["stage"] == "terminal"
    assert store.launch_count(day) == 1


@pytest.mark.parametrize("failure", ["paused", "child_output_invalid"])
def test_discovery_stopped_child_with_live_group_never_relaunches(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    fake = tmp_path / "fake-stopped.py"
    config, store = _exhausted(tmp_path, fake)
    setup = (
        "import sqlite3\n"
        f"with sqlite3.connect({str(store.db_path)!r}) as db:\n"
        "    db.execute(\"INSERT INTO runner_meta(key,value) VALUES('paused','1') "
        "ON CONFLICT(key) DO UPDATE SET value='1'\")\n"
        if failure == "paused"
        else 'print(\'{"tool":"wait","receiver_thread_ids":[]}\', flush=True)\n'
    )
    fake.write_text(
        "#!/usr/bin/env python3\nimport time\n" + setup + "time.sleep(30)\n",
        encoding="utf-8",
    )
    fake.chmod(0o700)
    monkeypatch.setattr(runner, "_process_group_alive", lambda _group_id: True)
    result = runner.run_once(config)
    assert result.reason == "discovery orphan identity uncertain"
    assert result.status == ("paused" if failure == "paused" else "blocked")
    status = store.discovery_status()
    assert status is not None and status["stage"] == "terminal"
    with sqlite3.connect(store.db_path) as db:
        assert db.execute("SELECT status FROM discovery_attempts").fetchone() == (
            "quarantined",
        )
    store.resume()
    monkeypatch.setattr(runner, "_process_group_alive", lambda _group_id: False)
    day = datetime.now(UTC).strftime("%Y-%m-%d")
    assert runner.run_once(config).reason == "discovery_orphan_identity_uncertain"
    assert store.launch_count(day) == 1


def test_scope_pass_registration_rolls_back_when_queue_fills(tmp_path: Path) -> None:
    fake = tmp_path / "fake-discovery.py"
    _fake_child(fake)
    config, store = _exhausted(tmp_path, fake)
    assert runner.run_once(config).reason == "discovery_scope"
    mandate = validate_dispatch_gate(config.repo).digest
    snapshot = store.discovery_snapshot()
    fingerprint = source_fingerprint(config.repo, mandate, snapshot)
    active = store.discovery_active_proposal(fingerprint)
    assert active is not None
    proposal, planner_attempt_id = active
    head = _git(config.repo, "rev-parse", "main")
    assert store.start_discovery_attempt(
        fingerprint,
        head,
        mandate,
        snapshot,
        "scope-attempt",
        "scope",
        tmp_path / "scope.json",
        datetime.now(UTC).isoformat(),
    )
    for index in range(8):
        assert store.enqueue(f"ready-{index}", "offline", "other")
    review = ScopeReview(
        verdict="PASS",
        proposal_digest=proposal_digest(proposal),
        planner_attempt_id=planner_attempt_id,
        baseline_head=head,
        fingerprint=fingerprint,
        owned_paths=sorted(proposal.owned_paths),
        reason="reproduced product gap",
    )
    assert (
        store.approve_discovery_spec(
            fingerprint,
            "scope-attempt",
            planner_attempt_id,
            proposal,
            review,
            head,
            mandate,
            snapshot,
            "a" * 64,
            config.repo,
        )
        is None
    )
    assert store.task(spec_from_proposal(proposal).id) is None
    with sqlite3.connect(store.db_path) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM approved_engineering_specs"
        ).fetchone() == (0,)
        assert db.execute(
            "SELECT status FROM discovery_attempts WHERE id='scope-attempt'"
        ).fetchone() == ("running",)


def test_pause_during_each_stage_resumes_same_cycle(tmp_path: Path) -> None:
    fake = tmp_path / "fake-discovery.py"
    config, store = _exhausted(tmp_path, fake)
    _fake_pausing_child(fake, store.db_path)
    assert runner.run_once(config).status == "paused"
    status = store.discovery_status()
    assert status is not None and status["stage"] == "discover"
    store.resume()
    _fake_child(fake)
    assert runner.run_once(config).reason == "discovery_scope"
    _fake_pausing_child(fake, store.db_path)
    assert runner.run_once(config).status == "paused"
    status = store.discovery_status()
    assert status is not None and status["stage"] == "scope"
    store.resume()
    _fake_child(fake)
    assert runner.run_once(config).reason == "discovery_approved"


def test_legacy_rows_survive_additive_discovery_schema(tmp_path: Path) -> None:
    path = tmp_path / "state" / "runner.db"
    path.parent.mkdir()
    with sqlite3.connect(path) as db:
        db.executescript(
            "CREATE TABLE tasks (id TEXT PRIMARY KEY,area TEXT NOT NULL,"
            "prompt TEXT NOT NULL,status TEXT NOT NULL,"
            "attempt_count INTEGER NOT NULL DEFAULT 0,next_allowed_at TEXT,"
            "last_attempt_id TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,"
            "previous_attempt_id TEXT,depends_on TEXT);"
            "CREATE TABLE attempts (id TEXT PRIMARY KEY,task_id TEXT NOT NULL,"
            "status TEXT NOT NULL,started_at TEXT NOT NULL,ended_at TEXT,"
            "process_group_id INTEGER,output_path TEXT,stderr_path TEXT,"
            "evidence_json TEXT,failure_code TEXT);"
            "CREATE TABLE review_attempts (id TEXT PRIMARY KEY,"
            "task_id TEXT NOT NULL,implementation_attempt_id TEXT NOT NULL,"
            "status TEXT NOT NULL,started_at TEXT NOT NULL,ended_at TEXT,"
            "process_group_id INTEGER,output_path TEXT NOT NULL,"
            "failure_code TEXT,receipt_json TEXT,context_json TEXT NOT NULL);"
            "CREATE TABLE discovery_cycles (fingerprint TEXT PRIMARY KEY,"
            "stage TEXT NOT NULL,baseline_head TEXT NOT NULL,"
            "mandate_digest TEXT NOT NULL,task_snapshot_json TEXT NOT NULL,"
            "proposal_count INTEGER NOT NULL DEFAULT 0,"
            "infra_failures INTEGER NOT NULL DEFAULT 0,"
            "active_proposal_digest TEXT,active_attempt_id TEXT,"
            "reason TEXT NOT NULL,next_condition TEXT NOT NULL,"
            "updated_at TEXT NOT NULL);"
            "INSERT INTO discovery_cycles "
            "(fingerprint,stage,baseline_head,mandate_digest,"
            "task_snapshot_json,reason,next_condition,updated_at) VALUES "
            "('legacy-cycle','terminal','head','mandate','[]',"
            "'no_work','source changed','before');"
            "INSERT INTO tasks (id,area,prompt,status,created_at,updated_at) "
            "VALUES ('legacy','offline','existing','completed','before','before');"
            "INSERT INTO attempts (id,task_id,status,started_at) "
            "VALUES ('legacy-attempt','legacy','completed','before');"
            "INSERT INTO review_attempts (id,task_id,implementation_attempt_id,"
            "status,started_at,output_path,context_json) VALUES "
            "('legacy-review','legacy','legacy-attempt','completed',"
            "'before','review.json','{}');"
        )
    store = RunnerStore(path)
    assert store.task("legacy") is not None
    legacy_cycle = store.discovery_cycle("legacy-cycle")
    assert legacy_cycle is not None and legacy_cycle["reason"] == "no_work"
    assert legacy_cycle["transient_failures"] == 0
    assert legacy_cycle["retry_after"] is None
    with sqlite3.connect(path) as db:
        assert db.execute(
            "SELECT task_id,status FROM attempts WHERE id='legacy-attempt'"
        ).fetchone() == ("legacy", "completed")
        assert db.execute(
            "SELECT task_id,status FROM review_attempts WHERE id='legacy-review'"
        ).fetchone() == ("legacy", "completed")
        assert db.execute(
            "SELECT COUNT(*) FROM approved_engineering_specs"
        ).fetchone() == (0,)


def test_proposal_evidence_and_registry_tamper_fail_closed(tmp_path: Path) -> None:
    fake = tmp_path / "fake-discovery.py"
    _fake_child(fake)
    config, store = _exhausted(tmp_path, fake)
    module: Literal["paper_execution_contract"] = "paper_execution_contract"
    paths = [
        f"backend/jusik/{module}.py",
        f"backend/tests/test_{module}.py",
    ]
    proposal = DiscoveryProposal(
        module=module,
        goal="Fix reproducible offline product accounting gap",
        reproduction="Run focused duplicate-record fixture and observe wrong value",
        gap="Current source accepts duplicate records in one offline scenario",
        tests="Add focused duplicate-record regression and normal case",
        stop_condition="Source fix and regression pass without activation",
        evidence=[
            SourceEvidence(
                path=name,
                sha256=hashlib.sha256((config.repo / name).read_bytes()).hexdigest(),
            )
            for name in paths
        ],
    )
    validate_proposal(config.repo, proposal)
    spec = spec_from_proposal(proposal)
    assert spec.id.endswith(
        digest(
            {
                "area": spec.area,
                "prompt": spec.prompt,
                "owned_paths": sorted(spec.owned_paths),
            }
        )[:32]
    )
    bad = proposal.model_copy(
        update={
            "evidence": [
                SourceEvidence(path=paths[0], sha256="0" * 64),
                proposal.evidence[1],
            ]
        }
    )
    with pytest.raises(ValueError, match="hash changed"):
        validate_proposal(config.repo, bad)
    assert runner.run_once(config).reason == "discovery_scope"
    approved = runner.run_once(config)
    assert approved.task_id is not None
    with sqlite3.connect(store.db_path) as db:
        original = db.execute(
            "SELECT spec_json,scope_review_json FROM approved_engineering_specs "
            "WHERE task_id=?",
            (approved.task_id,),
        ).fetchone()
        assert original is not None
        db.execute(
            "UPDATE approved_engineering_specs SET spec_json='{}' WHERE task_id=?",
            (approved.task_id,),
        )
    with pytest.raises(ValueError, match="spec changed"):
        store.engineering_spec(approved.task_id)
    review = json.loads(original[1])
    review["verdict"] = "REJECT"
    with sqlite3.connect(store.db_path) as db:
        db.execute(
            "UPDATE approved_engineering_specs SET spec_json=?,scope_review_json=? "
            "WHERE task_id=?",
            (original[0], json.dumps(review), approved.task_id),
        )
    with pytest.raises(ValueError, match="verdict changed"):
        store.engineering_spec(approved.task_id)
