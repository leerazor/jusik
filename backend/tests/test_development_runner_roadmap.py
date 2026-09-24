from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from jusik.development_runner import (
    RunnerConfig,
    _bind_scope,
    _roadmap_waiting_identity,
    _select_task,
    init_config,
    main,
    resume_runner,
    run_once,
    save_config,
    validate_completion,
)
from jusik.development_runner_contract import (
    ENGINEERING_OWNED_PATHS,
    ENGINEERING_SPEC_AREA,
    ENGINEERING_SPEC_ID,
    ENGINEERING_SPEC_PROMPT,
    Blocker,
)
from jusik.development_runner_roadmap import (
    ROADMAP_SCOPE,
    RoadmapError,
    eligible_areas,
    load_roadmap,
    validate_enqueue,
    validate_roadmap_completion,
)
from jusik.development_runner_store import RunnerStore
from jusik.research_mandate_governance import MandateGovernanceError

_ROADMAP_CHECKBOX_RE = re.compile(r"(?m)^(- \[)[ xX](\] \*\*(R\d+-\d{2})\*\*)")


def _fixture_roadmap(content: str) -> str:
    def normalize(match: re.Match[str]) -> str:
        item_id = match.group(3)
        phase = int(item_id[1 : item_id.index("-")])
        return f"{match.group(1)}{'x' if phase == 0 else ' '}{match.group(2)}"

    if _ROADMAP_CHECKBOX_RE.search(content) is None:
        raise AssertionError("roadmap fixture must contain checklist items")
    return _ROADMAP_CHECKBOX_RE.sub(normalize, content)


def _repo(tmp_path: Path, roadmap_content: str | None = None) -> Path:
    repo = tmp_path / "repo"
    docs = repo / "docs"
    docs.mkdir(parents=True)
    code = repo / "backend" / "jusik"
    code.mkdir(parents=True)
    (code / "__init__.py").write_text("\n", encoding="utf-8")
    source = Path(__file__).parents[2] / "docs"
    live_roadmap = (
        roadmap_content
        if roadmap_content is not None
        else (source / "investment-development-roadmap.md").read_text(encoding="utf-8")
    )
    (docs / "investment-development-roadmap.md").write_text(
        _fixture_roadmap(live_roadmap), encoding="utf-8"
    )
    (docs / "research-mandate.json").write_bytes(
        (source / "research-mandate.json").read_bytes()
    )
    for name in (
        "research-mandate.md",
        "market-research-mandate.sha256",
        "market-research.md",
        "continuous-development-session.md",
    ):
        (docs / name).write_bytes((source / name).read_bytes())
    return repo


def _tracked_repo(tmp_path: Path) -> Path:
    repo = _repo(tmp_path)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.invalid"],
        cwd=repo,
        check=True,
    )
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo, check=True)
    (repo / "docs" / "development-runner.md").write_text("runbook\n", encoding="utf-8")
    (repo / "docs" / "roadmap-automation.md").write_text("scope\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "initial"], cwd=repo, check=True)
    return repo


def _make_self_consistent_governance_swap(repo: Path, enabled: bool) -> None:
    mandate = repo / "docs" / "research-mandate.json"
    current = b"true" if enabled is False else b"false"
    raw = mandate.read_bytes().replace(
        b'"dispatch_enabled": ' + current,
        b'"dispatch_enabled": ' + (b"true" if enabled else b"false"),
    )
    mandate.write_bytes(raw)
    full_digest = hashlib.sha256(raw).hexdigest()
    governance = json.loads(raw)["governance"]
    governance_digest = hashlib.sha256(
        json.dumps(
            governance, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()
    marker = repo / "docs" / "research-mandate.md"
    marker.write_text(
        re.sub(
            r"(?<=SHA-256은 `)[0-9a-f]{64}",
            full_digest,
            marker.read_text(encoding="utf-8"),
            count=1,
        ),
        encoding="utf-8",
    )
    hashes = repo / "docs" / "market-research-mandate.sha256"
    lines: list[str] = []
    for line in hashes.read_text(encoding="utf-8").splitlines():
        path = line.split()[0]
        if path == "docs/research-mandate.json":
            lines.append(f"{path} {full_digest}")
        elif path == "docs/research-mandate.json#governance-object":
            lines.append(f"{path} {governance_digest}")
        elif path == "docs/research-mandate.md":
            lines.append(f"{path} {hashlib.sha256(marker.read_bytes()).hexdigest()}")
        else:
            lines.append(line)
    hashes.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_roadmap_areas_are_lowercase_and_gates_are_independent(tmp_path: Path) -> None:
    roadmap = load_roadmap(_repo(tmp_path))
    areas = eligible_areas(roadmap)

    assert roadmap.by_id["r1-01"].complete is False
    assert "r1-01" in areas
    assert "r2-01" in areas
    assert "r3-01" in areas
    assert "r4-01" not in areas
    assert all(area == area.lower() for area in areas)


def test_roadmap_fixture_pins_baseline_when_live_items_are_all_checked(
    tmp_path: Path,
) -> None:
    source = (
        Path(__file__).parents[2] / "docs" / "investment-development-roadmap.md"
    ).read_text(encoding="utf-8")
    all_checked = _ROADMAP_CHECKBOX_RE.sub(
        lambda match: f"{match.group(1)}x{match.group(2)}", source
    )

    roadmap = load_roadmap(_repo(tmp_path, all_checked))

    assert all(item.complete for item in roadmap.items if item.phase == 0)
    assert all(not item.complete for item in roadmap.items if 1 <= item.phase <= 7)


def test_roadmap_enqueue_quarantines_used_area_and_complete_area(
    tmp_path: Path,
) -> None:
    roadmap = load_roadmap(_repo(tmp_path))
    queued = SimpleNamespace(area="r1-01", status="failed")

    with pytest.raises(RoadmapError, match="quarantined"):
        validate_enqueue(roadmap, [queued], "roadmap-r1-01-v2", "R1-01")
    with pytest.raises(RoadmapError, match="complete"):
        validate_enqueue(roadmap, [], "roadmap-r0-01-v1", "r0-01")


def test_completed_partial_slice_can_enqueue_a_distinct_task_id(tmp_path: Path) -> None:
    roadmap = load_roadmap(_repo(tmp_path))
    completed = SimpleNamespace(area="r1-01", status="completed")

    assert (
        validate_enqueue(roadmap, [completed], "roadmap-r1-01-v2", "r1-01") == "r1-01"
    )


def test_planner_ignores_blocked_dependency_and_keeps_independent_phases(
    tmp_path: Path,
) -> None:
    from jusik.development_runner import _planning_task

    repo = _tracked_repo(tmp_path)
    store = RunnerStore(tmp_path / "state" / "runner.db")
    store.set_meta("scope", ROADMAP_SCOPE)
    store.enqueue("blocked", "r9-99", "blocked")
    blocked = store.task("blocked")
    assert blocked is not None
    store.claim(blocked, "blocked-attempt", tmp_path / "out", tmp_path / "err")
    store.finish("blocked-attempt", "blocked", "blocked")
    store.enqueue("roadmap-r1-01-v1", "r1-01", "seed", depends_on="blocked")

    candidate = _planning_task(store, repo, ROADMAP_SCOPE)

    assert candidate is not None
    assert "r2-01" in candidate[0].prompt
    assert "r3-01" in candidate[0].prompt
    assert "r4-01" not in candidate[0].prompt


def test_run_once_quarantines_stale_head_and_dispatches_independent_ready(
    tmp_path: Path,
) -> None:
    repo = _tracked_repo(tmp_path)
    state = tmp_path / "state"
    history = tmp_path / "history"
    store = RunnerStore(state / "runner.db", history)
    store.set_meta("scope", ROADMAP_SCOPE)
    assert store.enqueue("stale", "r0-01", "already complete")
    assert store.enqueue("data", "r1-01", "data unavailable")
    data = store.task("data")
    assert data is not None
    store.claim(data, "data-attempt", tmp_path / "data.out", tmp_path / "data.err")
    store.finish("data-attempt", "data", "blocked")
    assert store.enqueue("dependent", "r2-01", "needs data", depends_on="data")
    assert store.enqueue("independent", "r3-01", "offline fixture")

    evidence = repo / "backend" / "jusik" / "__init__.py"
    digest = hashlib.sha256(evidence.read_bytes()).hexdigest()
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    fake = tmp_path / "fake-child.py"
    fake.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        "from pathlib import Path\n"
        "prompt = sys.stdin.read()\n"
        "fields = {}\n"
        "for line in prompt.splitlines():\n"
        "    if ': ' in line:\n"
        "        key, value = line.split(': ', 1)\n"
        "        fields[key] = value\n"
        "output = Path(sys.argv[sys.argv.index('-o') + 1])\n"
        "payload = {'task_id': fields['Task id'], 'attempt_id': fields['Attempt id'],\n"
        " 'status': 'completed', 'tests_passed': True, 'review_passed': True,\n"
        f" 'integrated_commit': {head!r},\n"
        f" 'evidence': [{{'path': {str(evidence)!r}, 'sha256': {digest!r}}}],\n"
        f" 'handoff_path': {str(evidence)!r},\n"
        " 'blocked_reason': None, 'followup': None}\n"
        "output.write_text(json.dumps(payload), encoding='utf-8')\n",
        encoding="utf-8",
    )
    fake.chmod(0o700)
    config = RunnerConfig(
        repo=repo,
        codex=str(fake),
        state_dir=state,
        history_dir=history,
        history_db=tmp_path / "history.db",
        artifact_dir=tmp_path / "artifact",
        scope=ROADMAP_SCOPE,
        cooldown_seconds=0,
    )

    result = run_once(config)

    assert result.status == "completed" and result.task_id == "independent"
    assert store.task("stale").status == "blocked"  # type: ignore[union-attr]
    assert store.task("stale").blocker["alternative_ready_tasks"] == [  # type: ignore[index,union-attr]
        "independent"
    ]
    assert store.task("data").status == "blocked"  # type: ignore[union-attr]
    assert store.task("dependent").status == "queued"  # type: ignore[union-attr]
    assert store.task("independent").status == "completed"  # type: ignore[union-attr]
    assert store.launch_count(datetime.now(UTC).strftime("%Y-%m-%d")) == 1


def test_wait_states_keep_independent_ready_and_obey_utc_retry_cap(
    tmp_path: Path,
) -> None:
    store = RunnerStore(tmp_path / "state" / "runner.db")
    assert store.enqueue("external", "r1-01", "data")
    assert store.enqueue("dependent", "r2-01", "dependent", depends_on="external")
    assert store.enqueue("human", "r2-02", "approval")
    assert store.enqueue("independent", "r3-01", "offline")
    due = datetime.now(UTC) + timedelta(minutes=10)
    external_blocker = Blocker(
        blocker_reason="source unavailable",
        attempted_actions=["checked cached receipt"],
        dependency="source receipt",
        resume_condition="retry after source deadline",
        retry_policy="bounded",
        next_eligible_retry=due,
        alternative_ready_tasks=["independent"],
    ).model_dump(mode="json")
    human_blocker = Blocker(
        blocker_reason="approval required",
        attempted_actions=[],
        dependency="operator decision",
        resume_condition="authenticated decision",
        retry_policy="manual",
        alternative_ready_tasks=["independent"],
    ).model_dump(mode="json")
    for task_id, status, blocker in (
        ("external", "waiting_external", external_blocker),
        ("human", "waiting_human", human_blocker),
    ):
        task = store.task(task_id)
        assert task is not None
        store.claim(task, f"{task_id}-1", tmp_path / "out", tmp_path / "err")
        store.finish(
            f"{task_id}-1",
            task_id,
            status,
            blocker=blocker,
            next_allowed_at=blocker["next_eligible_retry"],
            automatic_retry=True,
        )
    assert _select_task(
        store, ROADMAP_SCOPE, load_roadmap(_repo(tmp_path))
    ) == store.task("independent")
    assert store.task("dependent").status == "queued"  # type: ignore[union-attr]
    assert store.task("human").canonical_state == "WAITING_HUMAN"  # type: ignore[union-attr]
    assert not store.retry("human")
    assert store.release_due_waiting(due - timedelta(seconds=1)) == []
    assert store.release_due_waiting(due) == ["external"]
    assert store.task("human").status == "waiting_human"  # type: ignore[union-attr]
    for index in (2, 3):
        task = store.task("external")
        assert task is not None
        store.claim(task, f"external-{index}", tmp_path / "out", tmp_path / "err")
        store.finish(
            f"external-{index}",
            "external",
            "waiting_external",
            blocker=external_blocker,
            next_allowed_at=due.isoformat(),
        )
        assert store.release_due_waiting(due) == (["external"] if index == 2 else [])
    assert store.task("external").attempt_count == 3  # type: ignore[union-attr]


def test_wait_completion_requires_utc_blocker_and_manual_human_release(
    tmp_path: Path,
) -> None:
    repo = _tracked_repo(tmp_path)
    config = RunnerConfig(repo=repo, scope=ROADMAP_SCOPE)
    store = RunnerStore(tmp_path / "state" / "runner.db")
    assert store.enqueue("waiting", "r1-01", "wait")
    task = store.task("waiting")
    assert task is not None
    with pytest.raises(ValueError, match="timezone-aware UTC"):
        Blocker(
            blocker_reason="external",
            resume_condition="retry",
            retry_policy="bounded",
            next_eligible_retry=datetime(2026, 1, 1),
        )
    payload = {
        "task_id": "waiting",
        "attempt_id": "attempt",
        "status": "waiting_human",
        "integrated_commit": None,
        "evidence": [],
        "tests_passed": False,
        "review_passed": False,
        "handoff_path": None,
        "blocked_reason": "approval required",
        "followup": None,
        "blocker": Blocker(
            blocker_reason="approval required",
            resume_condition="operator decision",
            retry_policy="manual",
        ).model_dump(mode="json"),
    }
    assert (
        validate_completion(payload, task, "attempt", config).status == "waiting_human"
    )
    payload["blocker"]["retry_policy"] = "event"
    with pytest.raises(ValueError, match="manual release"):
        validate_completion(payload, task, "attempt", config)


def test_legacy_blocked_migration_preserves_attempt_and_unknown_actions(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "state" / "runner.db"
    db_path.parent.mkdir()
    with sqlite3.connect(db_path) as db:
        db.execute(
            "CREATE TABLE tasks (id TEXT PRIMARY KEY, area TEXT NOT NULL, "
            "prompt TEXT NOT NULL, status TEXT NOT NULL, "
            "attempt_count INTEGER NOT NULL, "
            "next_allowed_at TEXT, last_attempt_id TEXT, created_at TEXT NOT NULL, "
            "updated_at TEXT NOT NULL, previous_attempt_id TEXT)"
        )
        db.execute(
            "CREATE TABLE attempts (id TEXT PRIMARY KEY, task_id TEXT NOT NULL, "
            "status TEXT NOT NULL, started_at TEXT NOT NULL, ended_at TEXT, "
            "process_group_id INTEGER, output_path TEXT, stderr_path TEXT, "
            "evidence_json TEXT, failure_code TEXT)"
        )
        db.execute(
            "INSERT INTO tasks VALUES ('legacy','r1-01','old','blocked',1,NULL,"
            "'old-attempt','2020-01-01','2020-01-01',NULL)"
        )
        db.execute(
            "INSERT INTO attempts VALUES ('old-attempt','legacy','blocked',"
            "'2020-01-01','2020-01-01',NULL,NULL,NULL,NULL,'legacy_code')"
        )
    store = RunnerStore(db_path)
    task = store.task("legacy")
    assert task is not None
    assert task.canonical_state == "BLOCKED"
    assert task.blocker is not None
    assert task.blocker["blocker_reason"] == "legacy_unknown"
    assert task.blocker["attempted_actions"] == []
    with sqlite3.connect(db_path) as db:
        assert (
            db.execute("SELECT failure_code FROM attempts").fetchone()[0]
            == "legacy_code"
        )


def test_engineering_spec_is_exact_and_keeps_completion_gates(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _tracked_repo(tmp_path)
    config = RunnerConfig(
        repo=repo,
        state_dir=tmp_path / "state",
        history_dir=tmp_path / "history",
        history_db=tmp_path / "history.db",
        artifact_dir=tmp_path / "artifact",
        scope=ROADMAP_SCOPE,
    )
    config_path = tmp_path / "config.json"
    save_config(config, config_path)
    store = RunnerStore(config.state_dir / "runner.db")
    store.set_meta("scope", ROADMAP_SCOPE)
    assert store.enqueue("data", "r1-01", "data")
    data = store.task("data")
    assert data is not None
    store.claim(data, "data-attempt", tmp_path / "out", tmp_path / "err")
    store.finish("data-attempt", "data", "blocked")
    assert store.enqueue("dependent", "r2-01", "needs data", depends_on="data")
    assert store.enqueue("delayed", "r3-01", "retry later")
    with sqlite3.connect(config.state_dir / "runner.db") as db:
        db.execute(
            "UPDATE tasks SET next_allowed_at=? WHERE id='delayed'",
            ((datetime.now(UTC) + timedelta(hours=1)).isoformat(),),
        )
    assert (
        main(
            [
                "enqueue",
                "--config",
                str(config_path),
                "--kind",
                "engineering",
                "--spec",
                ENGINEERING_SPEC_ID,
            ]
        )
        == 0
    )
    capsys.readouterr()
    task = store.task(ENGINEERING_SPEC_ID)
    assert task is not None
    assert (task.task_kind, task.area, task.prompt) == (
        "engineering",
        ENGINEERING_SPEC_AREA,
        ENGINEERING_SPEC_PROMPT,
    )
    assert "rejected orders" in task.prompt
    assert "Do not call brokerage APIs" in task.prompt
    assert _select_task(store, ROADMAP_SCOPE, load_roadmap(repo)) == task
    assert (
        main(
            [
                "enqueue",
                "--config",
                str(config_path),
                "--kind",
                "engineering",
                "--spec",
                ENGINEERING_SPEC_ID,
                "--area",
                "r1-01",
            ]
        )
        == 2
    )
    capsys.readouterr()
    assert (
        main(
            [
                "enqueue",
                "--config",
                str(config_path),
                "--kind",
                "engineering",
                "--spec",
                ENGINEERING_SPEC_ID,
                "--prompt",
                "changed",
            ]
        )
        == 2
    )
    capsys.readouterr()
    assert main(["status", "--config", str(config_path)]) == 0
    status = json.loads(capsys.readouterr().out)
    engineering = next(item for item in status["tasks"] if item["id"] == task.id)
    dependent = next(item for item in status["tasks"] if item["id"] == "dependent")
    delayed = next(item for item in status["tasks"] if item["id"] == "delayed")
    assert engineering["canonical_state"] == "READY"
    assert engineering["task_kind"] == "engineering"
    assert engineering["investment_status"] is None
    assert dependent["status"] == "queued"
    assert dependent["canonical_state"] == "BLOCKED"
    assert dependent["blocker"]["dependency"] == "data"
    assert dependent["blocker"]["attempted_actions"] == []
    assert delayed["canonical_state"] == "WAITING_EXTERNAL"
    assert delayed["blocker"]["next_eligible_retry"] is not None
    forged = RunnerStore(tmp_path / "forged" / "runner.db")
    assert forged.enqueue(
        "forged-engineering",
        "r1-01",
        ENGINEERING_SPEC_PROMPT,
        task_kind="engineering",
    )
    assert forged.enqueue("safe", "r3-01", "independent")
    assert _select_task(forged, ROADMAP_SCOPE, load_roadmap(repo)).id == "safe"  # type: ignore[union-attr]
    assert forged.task("forged-engineering").status == "blocked"  # type: ignore[union-attr]
    evidence = repo / "backend" / "jusik" / "__init__.py"
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    payload = {
        "task_id": task.id,
        "attempt_id": "attempt",
        "status": "completed",
        "integrated_commit": head,
        "evidence": [
            {
                "path": str(evidence),
                "sha256": hashlib.sha256(evidence.read_bytes()).hexdigest(),
            }
        ],
        "tests_passed": True,
        "review_passed": True,
        "handoff_path": str(evidence),
        "blocked_reason": None,
        "followup": None,
    }
    with pytest.raises(ValueError, match="engineering completion"):
        validate_completion(payload, task, "attempt", config, baseline_head=head)
    payload.update(
        engineering_status="ENGINEERING_COMPLETE", investment_status="NOT_EVALUATED"
    )
    with pytest.raises(ValueError, match="new descendant"):
        validate_completion(payload, task, "attempt", config, baseline_head=head)
    payload["review_passed"] = False
    with pytest.raises(ValueError, match="independent checks"):
        validate_completion(payload, task, "attempt", config, baseline_head=head)
    payload["review_passed"] = True
    fake = tmp_path / "fake-engineering-child.py"
    fake.write_text(
        "#!/usr/bin/env python3\n"
        "import hashlib, json, subprocess, sys\n"
        "from pathlib import Path\n"
        "fields = {}\n"
        "for line in sys.stdin.read().splitlines():\n"
        "    if ': ' in line:\n"
        "        key, value = line.split(': ', 1)\n"
        "        fields[key] = value\n"
        f"payload = {payload!r}\n"
        "payload['attempt_id'] = fields['Attempt id']\n"
        "source = Path('backend/jusik/paper_execution_contract.py')\n"
        "tests = Path('backend/tests/test_paper_execution_contract.py')\n"
        "tests.parent.mkdir(parents=True, exist_ok=True)\n"
        "source.write_text('class ExecutionContract: pass\\n', encoding='utf-8')\n"
        "tests.write_text('def test_offline(): assert True\\n', encoding='utf-8')\n"
        "subprocess.run(['git', 'add', str(source), str(tests)], check=True)\n"
        "subprocess.run(['git', 'commit', '-qm', 'fixture'], check=True)\n"
        "payload['integrated_commit'] = subprocess.check_output(\n"
        "    ['git', 'rev-parse', 'HEAD'], text=True).strip()\n"
        "payload['evidence'] = [\n"
        "    {'path': str(path.resolve()),\n"
        "     'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}\n"
        "    for path in (source, tests)]\n"
        "payload['handoff_path'] = str(source.resolve())\n"
        "Path(sys.argv[sys.argv.index('-o') + 1]).write_text(\n"
        "    json.dumps(payload), encoding='utf-8')\n",
        encoding="utf-8",
    )
    fake.chmod(0o700)
    result = run_once(
        config.model_copy(update={"codex": str(fake), "cooldown_seconds": 0})
    )
    assert result.status == "waiting_external" and result.task_id == ENGINEERING_SPEC_ID
    finished = store.task(ENGINEERING_SPEC_ID)
    assert finished is not None and finished.canonical_state == "WAITING_EXTERNAL"
    assert finished.engineering_status is None
    assert finished.investment_status is None
    assert finished.blocker is not None
    assert finished.blocker["blocker_reason"] == "independent_review_pending"
    assert finished.blocker["retry_policy"] == "none"
    with sqlite3.connect(config.state_dir / "runner.db") as db:
        assert (
            db.execute(
                "SELECT baseline_head FROM attempts WHERE id=?", (result.attempt_id,)
            ).fetchone()[0]
            == head
        )
        evidence_json = db.execute(
            "SELECT evidence_json FROM attempts WHERE id=?", (result.attempt_id,)
        ).fetchone()[0]
    assert json.loads(evidence_json)["integrated_commit"] != head
    receipt = Path(finished.blocker["dependency"])
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text("unverified review\n", encoding="utf-8")
    assert not store.release_event(ENGINEERING_SPEC_ID, receipt)
    assert (
        main(
            [
                "retry",
                "--config",
                str(config_path),
                ENGINEERING_SPEC_ID,
                "--event-evidence",
                str(receipt),
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["retried"] is False
    assert store.task(ENGINEERING_SPEC_ID).status == "waiting_external"  # type: ignore[union-attr]
    unrelated_evidence = json.loads(evidence_json)
    unrelated_evidence["evidence"] = payload["evidence"]
    with pytest.raises(ValueError, match="exact owned paths"):
        validate_completion(
            unrelated_evidence,
            task,
            result.attempt_id or "",
            config,
            baseline_head=head,
        )
    assert store.task("data").status == "blocked"  # type: ignore[union-attr]
    assert store.task("dependent").status == "queued"  # type: ignore[union-attr]


def test_engineering_rejects_unrelated_new_commit(tmp_path: Path) -> None:
    repo = _tracked_repo(tmp_path)
    baseline = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    unrelated = repo / "unrelated.txt"
    unrelated.write_text("unrelated\n", encoding="utf-8")
    subprocess.run(["git", "add", "unrelated.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "unrelated"], cwd=repo, check=True)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    store = RunnerStore(tmp_path / "state" / "runner.db")
    assert store.enqueue(
        ENGINEERING_SPEC_ID,
        ENGINEERING_SPEC_AREA,
        ENGINEERING_SPEC_PROMPT,
        task_kind="engineering",
    )
    task = store.task(ENGINEERING_SPEC_ID)
    assert task is not None
    payload = {
        "task_id": task.id,
        "attempt_id": "attempt",
        "status": "completed",
        "integrated_commit": head,
        "evidence": [
            {
                "path": str(unrelated),
                "sha256": hashlib.sha256(unrelated.read_bytes()).hexdigest(),
            }
        ],
        "tests_passed": True,
        "review_passed": True,
        "handoff_path": str(unrelated),
        "blocked_reason": None,
        "followup": None,
        "engineering_status": "ENGINEERING_COMPLETE",
        "investment_status": "NOT_EVALUATED",
    }
    with pytest.raises(ValueError, match="owned paths"):
        validate_completion(
            payload,
            task,
            "attempt",
            RunnerConfig(repo=repo, scope=ROADMAP_SCOPE),
            baseline_head=baseline,
        )


def test_engineering_rejects_reported_commit_behind_main(tmp_path: Path) -> None:
    repo = _tracked_repo(tmp_path)
    baseline = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    owned = [repo / path for path in sorted(ENGINEERING_OWNED_PATHS)]
    for path in owned:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("offline fixture\n", encoding="utf-8")
    subprocess.run(["git", "add", "backend"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "owned"], cwd=repo, check=True)
    reported = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    (repo / "unrelated.txt").write_text("later\n", encoding="utf-8")
    subprocess.run(["git", "add", "unrelated.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "later"], cwd=repo, check=True)
    store = RunnerStore(tmp_path / "state" / "runner.db")
    assert store.enqueue(
        ENGINEERING_SPEC_ID,
        ENGINEERING_SPEC_AREA,
        ENGINEERING_SPEC_PROMPT,
        task_kind="engineering",
    )
    task = store.task(ENGINEERING_SPEC_ID)
    assert task is not None
    payload = {
        "task_id": task.id,
        "attempt_id": "attempt",
        "status": "completed",
        "integrated_commit": reported,
        "evidence": [
            {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            for path in owned
        ],
        "tests_passed": True,
        "review_passed": True,
        "handoff_path": str(owned[0]),
        "blocked_reason": None,
        "followup": None,
        "engineering_status": "ENGINEERING_COMPLETE",
        "investment_status": "NOT_EVALUATED",
    }
    with pytest.raises(ValueError, match="main HEAD"):
        validate_completion(
            payload,
            task,
            "attempt",
            RunnerConfig(repo=repo, scope=ROADMAP_SCOPE),
            baseline_head=baseline,
        )


def test_engineering_rename_cannot_hide_old_source_path(tmp_path: Path) -> None:
    repo = _tracked_repo(tmp_path)
    old = repo / "backend" / "jusik" / "old_execution.py"
    old.write_text("class Contract: pass\n", encoding="utf-8")
    subprocess.run(["git", "add", str(old.relative_to(repo))], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "old source"], cwd=repo, check=True)
    baseline = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    source = repo / "backend" / "jusik" / "paper_execution_contract.py"
    tests = repo / "backend" / "tests" / "test_paper_execution_contract.py"
    tests.parent.mkdir(parents=True)
    subprocess.run(
        ["git", "mv", str(old.relative_to(repo)), str(source.relative_to(repo))],
        cwd=repo,
        check=True,
    )
    tests.write_text("def test_contract(): assert True\n", encoding="utf-8")
    subprocess.run(["git", "add", str(tests.relative_to(repo))], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "rename"], cwd=repo, check=True)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    store = RunnerStore(tmp_path / "state" / "runner.db")
    assert store.enqueue(
        ENGINEERING_SPEC_ID,
        ENGINEERING_SPEC_AREA,
        ENGINEERING_SPEC_PROMPT,
        task_kind="engineering",
    )
    task = store.task(ENGINEERING_SPEC_ID)
    assert task is not None
    payload = {
        "task_id": task.id,
        "attempt_id": "attempt",
        "status": "completed",
        "integrated_commit": head,
        "evidence": [
            {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            for path in (source, tests)
        ],
        "tests_passed": True,
        "review_passed": True,
        "handoff_path": str(source),
        "blocked_reason": None,
        "followup": None,
        "engineering_status": "ENGINEERING_COMPLETE",
        "investment_status": "NOT_EVALUATED",
    }
    with pytest.raises(ValueError, match="owned paths"):
        validate_completion(
            payload,
            task,
            "attempt",
            RunnerConfig(repo=repo, scope=ROADMAP_SCOPE),
            baseline_head=baseline,
        )


def test_event_wait_releases_only_after_evidence_identity_change(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from jusik.development_runner_contract import Blocker

    artifact = tmp_path / "artifact"
    artifact.mkdir()
    receipt = artifact / "receipt.json"
    receipt.write_text("old\n", encoding="utf-8")
    old_identity = hashlib.sha256(receipt.read_bytes()).hexdigest()
    repo = _tracked_repo(tmp_path)
    store = RunnerStore(tmp_path / "state" / "runner.db")
    store.set_meta("scope", ROADMAP_SCOPE)
    config_path = tmp_path / "config.json"
    save_config(
        RunnerConfig(
            repo=repo,
            state_dir=tmp_path / "state",
            history_dir=tmp_path / "history",
            history_db=tmp_path / "history.db",
            artifact_dir=artifact,
            scope=ROADMAP_SCOPE,
        ),
        config_path,
    )
    assert store.enqueue("external", "r1-01", "wait")
    task = store.task("external")
    assert task is not None
    store.claim(task, "external-attempt", tmp_path / "out", tmp_path / "err")
    blocker = Blocker(
        blocker_reason="source receipt missing",
        dependency=str(receipt.resolve()),
        dependency_identity=old_identity,
        resume_condition="receipt content changes",
        retry_policy="event",
    ).model_dump(mode="json")
    store.finish("external-attempt", "external", "waiting_external", blocker=blocker)
    assert not store.release_event("external", receipt)
    assert (
        main(
            [
                "retry",
                "--config",
                str(config_path),
                "external",
                "--event-evidence",
                str(receipt),
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["retried"] is False
    receipt.write_text("new\n", encoding="utf-8")
    assert (
        main(
            [
                "retry",
                "--config",
                str(config_path),
                "external",
                "--event-evidence",
                str(receipt),
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["retried"] is True
    assert store.task("external").status == "queued"  # type: ignore[union-attr]
    assert not store.release_event("external", receipt)
    assert store.enqueue("human", "r2-01", "approval")
    human = store.task("human")
    assert human is not None
    store.claim(human, "human-attempt", tmp_path / "out", tmp_path / "err")
    store.finish("human-attempt", "human", "waiting_human", blocker=blocker)
    assert not store.release_event("human", receipt)


def test_cli_wait_retry_requires_current_roadmap_fingerprint(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _tracked_repo(tmp_path)
    config = RunnerConfig(
        repo=repo,
        state_dir=tmp_path / "state",
        history_dir=tmp_path / "history",
        history_db=tmp_path / "history.db",
        artifact_dir=tmp_path / "artifact",
        scope=ROADMAP_SCOPE,
    )
    config_path = tmp_path / "config.json"
    save_config(config, config_path)
    store = RunnerStore(config.state_dir / "runner.db", config.history_dir)
    store.set_meta("scope", ROADMAP_SCOPE)
    identity = _roadmap_waiting_identity(store, repo)
    assert identity is not None
    current_id, expected_tasks = identity

    for task_id, attempt_id in (
        ("stale-roadmap-planner", "stale-attempt"),
        (current_id, "current-attempt"),
    ):
        assert store.enqueue(task_id, "__planning__", "internal")
        task = store.task(task_id)
        assert task is not None
        store.claim(
            task,
            attempt_id,
            tmp_path / f"{attempt_id}.out",
            tmp_path / f"{attempt_id}.err",
            history_outcome="planning_started",
        )
        assert store.finish_planning(
            attempt_id,
            task_id,
            "waiting",
            {"status": "waiting"},
            "fingerprint",
            expected_tasks,
            scope=ROADMAP_SCOPE,
        )

    before_tasks = store.tasks()
    with store._connect() as db:
        before_attempts = db.execute("SELECT COUNT(*) FROM attempts").fetchone()[0]
    assert (
        main(
            [
                "retry",
                "--planning-wait",
                "--config",
                str(config_path),
                "stale-roadmap-planner",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out) == {"retried": False}
    assert store.tasks() == before_tasks
    with store._connect() as db:
        assert (
            db.execute("SELECT COUNT(*) FROM attempts").fetchone()[0] == before_attempts
        )

    assert (
        main(["retry", "--planning-wait", "--config", str(config_path), current_id])
        == 0
    )
    assert json.loads(capsys.readouterr().out) == {"retried": True}
    retried = store.task(current_id)
    assert retried is not None
    assert retried.status == "queued"
    with store._connect() as db:
        previous_attempt_id = db.execute(
            "SELECT previous_attempt_id FROM tasks WHERE id=?", (current_id,)
        ).fetchone()["previous_attempt_id"]
    assert previous_attempt_id == "current-attempt"


@pytest.mark.parametrize("missing", [True, False])
def test_untracked_required_runbook_blocks_dispatch(
    tmp_path: Path, missing: bool
) -> None:
    repo = _tracked_repo(tmp_path)
    relative = "docs/roadmap-automation.md"
    subprocess.run(["git", "rm", "--cached", "--", relative], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "untrack runbook"], cwd=repo, check=True)
    if missing:
        (repo / relative).unlink()
    else:
        assert (repo / relative).is_file()
    config = RunnerConfig(
        repo=repo,
        state_dir=tmp_path / "state",
        history_dir=tmp_path / "history",
        history_db=tmp_path / "history.db",
        artifact_dir=tmp_path / "artifact",
        scope=ROADMAP_SCOPE,
        planning_enabled=True,
    )
    RunnerStore(config.state_dir / "runner.db").set_meta("scope", ROADMAP_SCOPE)

    result = run_once(config)

    assert result.status == "blocked"
    assert "roadmap document" in (result.reason or "")
    assert not (tmp_path / "state" / "attempts").exists()


@pytest.mark.parametrize("payload", ["{", "{}"])
@pytest.mark.parametrize("queued", [True, False])
def test_invalid_tracked_mandate_blocks_before_attempt(
    tmp_path: Path, payload: str, queued: bool
) -> None:
    repo = _tracked_repo(tmp_path)
    relative = "docs/research-mandate.json"
    (repo / relative).write_text(payload, encoding="utf-8")
    subprocess.run(["git", "add", "--", relative], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "invalid mandate"], cwd=repo, check=True)
    config = RunnerConfig(
        repo=repo,
        state_dir=tmp_path / "state",
        history_dir=tmp_path / "history",
        history_db=tmp_path / "history.db",
        artifact_dir=tmp_path / "artifact",
        scope=ROADMAP_SCOPE,
        planning_enabled=True,
    )
    store = RunnerStore(config.state_dir / "runner.db")
    store.set_meta("scope", ROADMAP_SCOPE)
    if queued:
        store.enqueue("roadmap-r1-01-v1", "r1-01", "seed")

    result = run_once(config)

    assert result.status == "blocked"
    assert result.reason == "tracked research mandate is missing or malformed"
    assert store.active_attempt() is None
    assert store.get_meta("last_launch_at") is None
    assert not (config.state_dir / "attempts").exists()
    assert all(task.status == "queued" for task in store.tasks())
    assert len(store.tasks()) == int(queued)


def test_slice_completion_is_distinct_from_full_checklist_completion(
    tmp_path: Path,
) -> None:
    roadmap = load_roadmap(_repo(tmp_path))
    task = SimpleNamespace(area="r1-01")
    completion = SimpleNamespace(status="completed", followup=None)

    validate_roadmap_completion(roadmap, task, completion)


def test_investment_init_is_blank_and_binds_dedicated_state(tmp_path: Path) -> None:
    config = init_config(
        tmp_path / "config.json",
        _repo(tmp_path),
        tmp_path / "state",
        tmp_path / "history",
        tmp_path / "history.db",
        tmp_path / "artifact",
        ROADMAP_SCOPE,
    )
    store = RunnerStore(config.state_dir / "runner.db")

    assert config.scope == ROADMAP_SCOPE
    assert store.tasks() == []
    assert store.get_meta("scope") == ROADMAP_SCOPE


def test_investment_scope_rejects_legacy_and_research_state(tmp_path: Path) -> None:
    state = tmp_path / "state"
    legacy = RunnerStore(state / "runner.db")
    assert _bind_scope(legacy, ROADMAP_SCOPE)[0] is False

    research = RunnerStore(tmp_path / "research" / "runner.db")
    research.set_meta("scope", "research")
    assert _bind_scope(research, ROADMAP_SCOPE)[0] is False


def test_missing_or_malformed_roadmap_fails_closed(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / "docs" / "investment-development-roadmap.md").write_text(
        "- [ ] **R1-01** malformed", encoding="utf-8"
    )
    roadmap = load_roadmap(repo)
    assert roadmap.by_id["r1-01"].complete is False
    (repo / "docs" / "investment-development-roadmap.md").write_text(
        "- [ ] **R1-01**\n", encoding="utf-8"
    )
    with pytest.raises(RoadmapError, match="malformed"):
        load_roadmap(repo)


def test_roadmap_resume_rejects_dirty_worktree_and_keeps_paused(
    tmp_path: Path,
) -> None:
    repo = _tracked_repo(tmp_path)
    config = RunnerConfig(
        repo=repo,
        state_dir=tmp_path / "state",
        history_dir=tmp_path / "history",
        history_db=tmp_path / "history.db",
        artifact_dir=tmp_path / "artifact",
        scope=ROADMAP_SCOPE,
    )
    store = RunnerStore(config.state_dir / "runner.db", config.history_dir)
    store.set_meta("scope", ROADMAP_SCOPE)
    store.pause()
    roadmap_path = repo / "docs" / "investment-development-roadmap.md"
    roadmap_path.write_text(
        roadmap_path.read_text(encoding="utf-8") + "\n", encoding="utf-8"
    )

    with pytest.raises(MandateGovernanceError, match="worktree is not ready"):
        resume_runner(config)

    assert store.is_paused()


def test_roadmap_resume_rejects_untracked_required_document_and_keeps_paused(
    tmp_path: Path,
) -> None:
    repo = _tracked_repo(tmp_path)
    config = RunnerConfig(
        repo=repo,
        state_dir=tmp_path / "state",
        history_dir=tmp_path / "history",
        history_db=tmp_path / "history.db",
        artifact_dir=tmp_path / "artifact",
        scope=ROADMAP_SCOPE,
    )
    store = RunnerStore(config.state_dir / "runner.db", config.history_dir)
    store.set_meta("scope", ROADMAP_SCOPE)
    store.pause()
    relative = "docs/roadmap-automation.md"
    subprocess.run(["git", "rm", "--cached", "--", relative], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-qm", "untrack roadmap runbook"], cwd=repo, check=True
    )

    with pytest.raises(
        MandateGovernanceError, match="required roadmap document is not tracked"
    ):
        resume_runner(config)

    assert store.is_paused()


def test_clean_roadmap_resume_releases_pause(tmp_path: Path) -> None:
    repo = _tracked_repo(tmp_path)
    config = RunnerConfig(
        repo=repo,
        state_dir=tmp_path / "state",
        history_dir=tmp_path / "history",
        history_db=tmp_path / "history.db",
        artifact_dir=tmp_path / "artifact",
        scope=ROADMAP_SCOPE,
    )
    store = RunnerStore(config.state_dir / "runner.db", config.history_dir)
    store.set_meta("scope", ROADMAP_SCOPE)
    store.pause()

    resume_runner(config)

    assert not store.is_paused()


def test_runner_config_keeps_research_default(tmp_path: Path) -> None:
    config = RunnerConfig(repo=tmp_path)
    assert config.scope == "research"


def test_disabled_governance_blocks_run_resume_and_cli_without_state_mutation(
    tmp_path: Path,
) -> None:
    repo = _tracked_repo(tmp_path)
    _make_self_consistent_governance_swap(repo, False)
    config = RunnerConfig(
        repo=repo,
        state_dir=tmp_path / "state",
        history_dir=tmp_path / "history",
        history_db=tmp_path / "history.db",
        artifact_dir=tmp_path / "artifact",
        scope=ROADMAP_SCOPE,
        planning_enabled=True,
        cooldown_seconds=0,
    )
    store = RunnerStore(config.state_dir / "runner.db", config.history_dir)
    store.set_meta("scope", ROADMAP_SCOPE)
    store.enqueue("roadmap-r1-01-v1", "r1-01", "seed")
    store.pause()
    before_tasks = store.tasks()
    before_attempt = store.active_attempt()
    before_launches = store.launch_count("2099-01-01")
    config_path = tmp_path / "config.json"
    save_config(config, config_path)

    result = run_once(config)

    assert result.status == "blocked"
    assert result.reason == "investment roadmap governance is disabled"
    assert store.tasks() == before_tasks
    assert store.active_attempt() == before_attempt
    assert store.launch_count("2099-01-01") == before_launches
    assert not (config.state_dir / "attempts").exists()
    with pytest.raises(ValueError, match="disabled"):
        resume_runner(config)
    assert store.is_paused()
    assert main(["resume", "--config", str(config_path)]) == 2
    assert store.is_paused()


def test_dirty_governance_swap_blocks_queued_task_before_claim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from jusik import development_runner

    repo = _tracked_repo(tmp_path)
    config = RunnerConfig(
        repo=repo,
        state_dir=tmp_path / "state",
        history_dir=tmp_path / "history",
        history_db=tmp_path / "history.db",
        artifact_dir=tmp_path / "artifact",
        scope=ROADMAP_SCOPE,
        cooldown_seconds=0,
    )
    store = RunnerStore(config.state_dir / "runner.db", config.history_dir)
    store.set_meta("scope", ROADMAP_SCOPE)
    store.enqueue("roadmap-r1-01-v1", "r1-01", "seed")
    before_tasks = store.tasks()
    original_ready = development_runner._git_ready
    calls = 0

    def swap_after_initial_gate(repo_path: Path) -> tuple[bool, str]:
        nonlocal calls
        calls += 1
        if calls == 2:
            _make_self_consistent_governance_swap(repo_path, False)
        return original_ready(repo_path)

    monkeypatch.setattr(development_runner, "_git_ready", swap_after_initial_gate)

    result = run_once(config)

    assert result.status == "blocked"
    assert result.reason == "investment roadmap worktree is not ready"
    assert store.tasks() == before_tasks
    assert store.active_attempt() is None
    assert store.launch_count("2099-01-01") == 0
    assert not (config.state_dir / "attempts").exists()


def test_dirty_governance_swap_blocks_planner_before_enqueue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from jusik import development_runner

    repo = _tracked_repo(tmp_path)
    config = RunnerConfig(
        repo=repo,
        state_dir=tmp_path / "state",
        history_dir=tmp_path / "history",
        history_db=tmp_path / "history.db",
        artifact_dir=tmp_path / "artifact",
        scope=ROADMAP_SCOPE,
        planning_enabled=True,
        cooldown_seconds=0,
    )
    store = RunnerStore(config.state_dir / "runner.db", config.history_dir)
    store.set_meta("scope", ROADMAP_SCOPE)
    before_tasks = store.tasks()
    original_ready = development_runner._git_ready
    calls = 0

    def swap_after_initial_gate(repo_path: Path) -> tuple[bool, str]:
        nonlocal calls
        calls += 1
        if calls == 2:
            _make_self_consistent_governance_swap(repo_path, False)
        return original_ready(repo_path)

    monkeypatch.setattr(development_runner, "_git_ready", swap_after_initial_gate)

    result = run_once(config)

    assert result.status == "blocked"
    assert result.reason == "investment roadmap worktree is not ready"
    assert store.tasks() == before_tasks
    assert store.active_attempt() is None
    assert store.launch_count("2099-01-01") == 0
    assert not (config.state_dir / "attempts").exists()
