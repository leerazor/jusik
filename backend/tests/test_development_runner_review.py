from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
from pathlib import Path

import pytest

from jusik import development_runner as runner
from jusik.development_runner import RunnerConfig, _review_command, run_once
from jusik.development_runner_contract import ENGINEERING_OWNED_PATHS
from jusik.development_runner_review import review_schema, validate_receipt
from jusik.development_runner_store import RunnerStore


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


def _candidate(tmp_path: Path) -> tuple[RunnerConfig, RunnerStore, str, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "Runner Test")
    (repo / "README.md").write_text("baseline\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "baseline")
    baseline = _git(repo, "rev-parse", "main")
    owned = [repo / path for path in sorted(ENGINEERING_OWNED_PATHS)]
    for path in owned:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("offline fixture\n", encoding="utf-8")
    _git(repo, "add", "backend")
    _git(repo, "commit", "-m", "candidate")
    head = _git(repo, "rev-parse", "main")
    config = RunnerConfig(
        repo=repo,
        state_dir=tmp_path / "state",
        history_dir=tmp_path / "history",
        history_db=tmp_path / "history.db",
        artifact_dir=tmp_path / "artifact",
        cooldown_seconds=0,
        planning_enabled=False,
    )
    store = RunnerStore(config.state_dir / "runner.db")
    assert store.enqueue(
        "engineering", "__engineering__", "fixture", task_kind="engineering"
    )
    task = store.task("engineering")
    assert task is not None
    store.claim(
        task,
        "implementation",
        tmp_path / "output",
        tmp_path / "error",
        baseline_head=baseline,
    )
    completion = {
        "task_id": task.id,
        "attempt_id": "implementation",
        "status": "completed",
        "integrated_commit": head,
        "evidence": [
            {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            for path in owned
        ],
        "tests_passed": True,
        "review_passed": False,
        "handoff_path": str(owned[0]),
        "blocked_reason": None,
        "followup": None,
        "recovery_kind": None,
        "blocker": None,
        "engineering_status": None,
        "investment_status": None,
    }
    store.finish(
        "implementation",
        task.id,
        "waiting_external",
        failure_code="independent_review_pending",
        evidence={"review_candidate_version": 1, "completion": completion},
    )
    return config, store, baseline, head


def _fake_reviewer(path: Path, *, verdict: str, wrong_head: bool = False) -> None:
    path.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        "from pathlib import Path\n"
        "prompt = sys.stdin.read()\n"
        "context = json.loads(prompt.split('fields: ', 1)[1])\n"
        + ("context['main_head'] = '0' * 40\n" if wrong_head else "")
        + f"context['verdict'] = {verdict!r}\n"
        "Path(sys.argv[sys.argv.index('-o') + 1]).write_text(\n"
        "    json.dumps(context), encoding='utf-8')\n",
        encoding="utf-8",
    )
    path.chmod(0o700)


def test_review_pass_finalizes_only_matching_candidate(tmp_path: Path) -> None:
    config, store, baseline, head = _candidate(tmp_path)
    fake = tmp_path / "fake-reviewer.py"
    _fake_reviewer(fake, verdict="PASS")

    result = run_once(config.model_copy(update={"codex": str(fake)}))

    assert (result.status, result.task_id, result.attempt_id) == (
        "completed",
        "engineering",
        "implementation",
    )
    task = store.task("engineering")
    assert task is not None
    assert (task.canonical_state, task.engineering_status, task.investment_status) == (
        "DONE",
        "ENGINEERING_COMPLETE",
        "NOT_EVALUATED",
    )
    with sqlite3.connect(store.db_path) as db:
        row = db.execute(
            "SELECT status,receipt_json,context_json FROM review_attempts"
        ).fetchone()
        implementation = db.execute(
            "SELECT status FROM attempts WHERE id='implementation'"
        ).fetchone()
    assert row is not None and row[0] == "completed"
    receipt = json.loads(row[1])
    assert receipt == json.loads(row[2]) | {"verdict": "PASS"}
    assert receipt["baseline_head"] == baseline
    assert receipt["main_head"] == head
    assert implementation == ("completed",)


@pytest.mark.parametrize("verdict,wrong_head", [("FAIL", False), ("PASS", True)])
def test_review_failure_stays_waiting_and_is_not_retried(
    tmp_path: Path, verdict: str, wrong_head: bool
) -> None:
    config, store, _, _ = _candidate(tmp_path)
    fake = tmp_path / "fake-reviewer.py"
    _fake_reviewer(fake, verdict=verdict, wrong_head=wrong_head)

    result = run_once(config.model_copy(update={"codex": str(fake)}))

    assert result.status == "idle"
    task = store.task("engineering")
    assert task is not None
    assert task.canonical_state == "WAITING_EXTERNAL"
    assert task.engineering_status is None
    assert store.review_candidate() is None
    with sqlite3.connect(store.db_path) as db:
        assert db.execute("SELECT COUNT(*) FROM review_attempts").fetchone()[0] == 1
        assert (
            db.execute("SELECT status FROM review_attempts").fetchone()[0] == "failed"
        )


def test_review_restart_recovery_is_bounded(tmp_path: Path) -> None:
    config, store, _, _ = _candidate(tmp_path)
    candidate = store.review_candidate()
    assert candidate is not None
    context = {
        "task_id": "engineering",
        "implementation_attempt_id": "implementation",
        "review_attempt_id": "review-1",
        "baseline_head": candidate.baseline_head,
        "main_head": candidate.completion["integrated_commit"],
        "owned_file_hashes": {
            name: hashlib.sha256((config.repo / name).read_bytes()).hexdigest()
            for name in ENGINEERING_OWNED_PATHS
        },
    }
    assert store.claim_review(
        candidate,
        "review-1",
        tmp_path / "receipt",
        context,
        "2026-01-01T00:00:00+00:00",
    )
    assert store.recover_running_reviews(["review-1"]) == ["review-1"]
    assert store.review_candidate() is not None
    assert store.claim_review(
        candidate,
        "review-2",
        tmp_path / "receipt2",
        context | {"review_attempt_id": "review-2"},
        "2026-01-01T00:00:01+00:00",
    )
    assert store.recover_running_reviews(["review-2"]) == ["review-2"]
    assert store.review_candidate() is None
    assert store.task("engineering").canonical_state == "WAITING_EXTERNAL"  # type: ignore[union-attr]


def test_legacy_wait_does_not_enter_review_path(tmp_path: Path) -> None:
    config, store, _, _ = _candidate(tmp_path)
    candidate = store.review_candidate()
    assert candidate is not None
    with sqlite3.connect(store.db_path) as db:
        db.execute(
            "UPDATE attempts SET evidence_json=? WHERE id='implementation'",
            (json.dumps(candidate.completion),),
        )
    assert store.review_candidate() is None
    fake = tmp_path / "must-not-run"
    assert run_once(config.model_copy(update={"codex": str(fake)})).status == "idle"
    assert not fake.exists()
    assert store.task("engineering").canonical_state == "WAITING_EXTERNAL"  # type: ignore[union-attr]


def test_changed_main_quarantines_candidate_before_dispatch(tmp_path: Path) -> None:
    config, store, _, _ = _candidate(tmp_path)
    (config.repo / "later.txt").write_text("later\n", encoding="utf-8")
    _git(config.repo, "add", "later.txt")
    _git(config.repo, "commit", "-m", "later")
    fake = tmp_path / "must-not-run"

    assert run_once(config.model_copy(update={"codex": str(fake)})).status == "idle"
    assert not fake.exists()
    assert store.review_candidate() is None
    task = store.task("engineering")
    assert task is not None and task.canonical_state == "WAITING_EXTERNAL"
    assert task.blocker is not None
    assert task.blocker["blocker_reason"] == "review_candidate_stale"
    with sqlite3.connect(store.db_path) as db:
        assert db.execute("SELECT COUNT(*) FROM review_attempts").fetchone()[0] == 0


def test_review_idle_timeout_has_two_attempt_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, store, _, _ = _candidate(tmp_path)
    fake = tmp_path / "sleep-reviewer.py"
    fake.write_text(
        "#!/usr/bin/env python3\nimport time\ntime.sleep(60)\n",
        encoding="utf-8",
    )
    fake.chmod(0o700)
    monkeypatch.setattr(
        "jusik.development_runner._child_idle_expired",
        lambda *_args: True,
    )
    configured = config.model_copy(update={"codex": str(fake)})

    assert run_once(configured).status == "idle"
    assert store.review_candidate() is not None
    assert run_once(configured).status == "idle"
    assert store.review_candidate() is None
    assert store.task("engineering").canonical_state == "WAITING_EXTERNAL"  # type: ignore[union-attr]
    with sqlite3.connect(store.db_path) as db:
        rows = db.execute(
            "SELECT status,failure_code FROM review_attempts ORDER BY started_at,id"
        ).fetchall()
    assert rows == [("failed", "idle_timeout"), ("failed", "idle_timeout")]


def test_rejected_review_dispatches_independent_ready_task(tmp_path: Path) -> None:
    config, store, _, _ = _candidate(tmp_path)
    assert store.enqueue("ready", "entry-amount-distribution", "independent")
    fake = tmp_path / "dual-child.py"
    fake.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        "from pathlib import Path\n"
        "prompt = sys.stdin.read()\n"
        "if 'identity fields: ' in prompt:\n"
        "    payload = json.loads(prompt.split('fields: ', 1)[1])\n"
        "    payload['verdict'] = 'FAIL'\n"
        "else:\n"
        "    fields = dict(line.split(': ', 1) for line in prompt.splitlines() "
        "if line.startswith(('Task id: ', 'Attempt id: ')))\n"
        "    payload = {'task_id': fields['Task id'], "
        "'attempt_id': fields['Attempt id'], 'status': 'blocked', "
        "'integrated_commit': None, 'evidence': [], "
        "'tests_passed': False, 'review_passed': False, "
        "'handoff_path': None, 'blocked_reason': 'fixture', "
        "'followup': None, 'recovery_kind': None, 'blocker': None, "
        "'engineering_status': None, 'investment_status': None}\n"
        "Path(sys.argv[sys.argv.index('-o') + 1]).write_text(\n"
        "    json.dumps(payload), encoding='utf-8')\n",
        encoding="utf-8",
    )
    fake.chmod(0o700)

    result = run_once(config.model_copy(update={"codex": str(fake)}))

    assert (result.status, result.task_id) == ("blocked", "ready")
    assert store.task("engineering").canonical_state == "WAITING_EXTERNAL"  # type: ignore[union-attr]
    assert store.task("ready").canonical_state == "BLOCKED"  # type: ignore[union-attr]
    with sqlite3.connect(store.db_path) as db:
        row = db.execute(
            "SELECT failure_code,receipt_json FROM review_attempts"
        ).fetchone()
    assert row is not None and row[0] == "review_rejected"
    assert json.loads(row[1])["verdict"] == "FAIL"


def test_review_command_is_read_only_and_receipt_schema_is_exact(
    tmp_path: Path,
) -> None:
    config = RunnerConfig(repo=tmp_path)
    command = _review_command(config, tmp_path / "schema", tmp_path / "receipt")
    assert command[command.index("--sandbox") + 1] == "read-only"
    assert "--ignore-user-config" in command
    assert any("network={enabled=false}" in item for item in command)
    schema = review_schema()
    assert set(schema["required"]) == set(schema["properties"])
    assert (
        set(schema["properties"]["owned_file_hashes"]["required"])
        == ENGINEERING_OWNED_PATHS
    )
    with pytest.raises(ValueError, match="identity mismatch"):
        validate_receipt(
            {
                "task_id": "wrong",
                "implementation_attempt_id": "implementation",
                "review_attempt_id": "review",
                "baseline_head": "a" * 40,
                "main_head": "b" * 40,
                "owned_file_hashes": {
                    path: "c" * 64 for path in ENGINEERING_OWNED_PATHS
                },
                "verdict": "PASS",
            },
            {
                "task_id": "expected",
                "implementation_attempt_id": "implementation",
                "review_attempt_id": "review",
                "baseline_head": "a" * 40,
                "main_head": "b" * 40,
                "owned_file_hashes": {
                    path: "c" * 64 for path in ENGINEERING_OWNED_PATHS
                },
            },
        )


def test_orphaned_review_group_escalates_before_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    signals: list[tuple[int, bool]] = []
    monkeypatch.setattr(runner, "_process_group_alive", lambda _group: True)
    monkeypatch.setattr(
        runner,
        "_terminate_group",
        lambda group, force=False: signals.append((group, force)),
    )
    monkeypatch.setattr(runner, "_wait_for_group_exit", lambda *_args: False)

    assert not runner._stop_orphaned_review_group(12345)
    assert signals == [(12345, False), (12345, True)]


def test_multiple_running_reviews_preserve_live_journal_and_block_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, store, _, _ = _candidate(tmp_path)
    candidate = store.review_candidate()
    assert candidate is not None
    assert store.claim_review(
        candidate,
        "review-one",
        tmp_path / "receipt-one",
        {},
        "2026-01-01T00:00:00+00:00",
    )
    store.set_review_process_group("review-one", 1001)
    with sqlite3.connect(store.db_path) as db:
        db.execute(
            "INSERT INTO review_attempts "
            "(id,task_id,implementation_attempt_id,status,started_at,"
            "process_group_id,output_path,context_json) "
            "VALUES(?,?,?,'running',?,?,?,?)",
            (
                "review-two",
                "engineering",
                "implementation",
                "2026-01-01T00:00:01+00:00",
                1002,
                str(tmp_path / "receipt-two"),
                "{}",
            ),
        )
    assert store.enqueue("ready", "entry-amount-distribution", "independent")
    checked: list[int | None] = []

    def stop_group(group_id: int | None) -> bool:
        checked.append(group_id)
        return group_id == 1001

    monkeypatch.setattr(runner, "_stop_orphaned_review_group", stop_group)
    result = run_once(
        config.model_copy(update={"codex": str(tmp_path / "must-not-run")})
    )

    assert result.status == "blocked"
    assert set(checked) == {1001, 1002}
    assert store.task("ready").canonical_state == "READY"  # type: ignore[union-attr]
    with sqlite3.connect(store.db_path) as db:
        rows = db.execute(
            "SELECT id,status FROM review_attempts ORDER BY id"
        ).fetchall()
    assert rows == [("review-one", "interrupted"), ("review-two", "running")]

    monkeypatch.setattr(runner, "_stop_orphaned_review_group", lambda _group: True)
    resumed = run_once(
        config.model_copy(update={"codex": str(tmp_path / "must-not-run")})
    )
    assert (resumed.status, resumed.task_id) == ("failed", "ready")
    with sqlite3.connect(store.db_path) as db:
        rows = db.execute(
            "SELECT id,status FROM review_attempts ORDER BY id"
        ).fetchall()
    assert rows == [("review-one", "interrupted"), ("review-two", "interrupted")]


def test_reviewer_environment_does_not_inherit_unlisted_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("JUSIK_REVIEW_SECRET_MARKER", "marker")
    monkeypatch.setenv("PATH", "/usr/bin:/bin")

    environment = runner._review_environment(tmp_path)

    assert environment["PATH"] == "/usr/bin:/bin"
    assert "JUSIK_REVIEW_SECRET_MARKER" not in environment
    assert environment["XDG_CACHE_HOME"].startswith(str(tmp_path))


def test_fake_reviewer_process_cannot_read_unlisted_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, store, _, _ = _candidate(tmp_path)
    monkeypatch.setenv("JUSIK_REVIEW_SECRET_MARKER", "marker")
    fake = tmp_path / "environment-reviewer.py"
    _fake_reviewer(fake, verdict="PASS")
    original = fake.read_text(encoding="utf-8")
    fake.write_text(
        original.replace(
            "import json, sys\n",
            "import json, os, sys\n"
            "if os.environ.get('JUSIK_REVIEW_SECRET_MARKER'): sys.exit(8)\n",
        ),
        encoding="utf-8",
    )

    result = run_once(config.model_copy(update={"codex": str(fake)}))

    assert result.status == "completed"
    assert store.task("engineering").canonical_state == "DONE"  # type: ignore[union-attr]
