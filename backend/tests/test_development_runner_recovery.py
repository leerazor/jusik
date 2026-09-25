from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest
from test_development_runner_review import _candidate, _fake_reviewer, _git

from jusik import development_runner as runner
from jusik.development_runner import RunnerConfig, recover_failed_candidate, run_once
from jusik.development_runner_contract import (
    ENGINEERING_SPEC_AREA,
    ENGINEERING_SPEC_ID,
    ENGINEERING_SPEC_PROMPT,
)
from jusik.development_runner_review import validate_receipt
from jusik.development_runner_store import RunnerStore


def _write_transcript(path: Path, completion_text: str) -> None:
    event = {
        "type": "item.completed",
        "item": {"type": "agent_message", "text": completion_text},
    }
    path.write_text(json.dumps(event) + "\n", encoding="utf-8")


def _recover(
    config: RunnerConfig, store: RunnerStore, *, expected_sha256: str | None = None
) -> str | None:
    source = config.state_dir / "original-completion.json"
    pin = expected_sha256 or hashlib.sha256(source.read_bytes()).hexdigest()
    return recover_failed_candidate(
        config, store, "engineering", "implementation", expected_source_sha256=pin
    )


def _failed_candidate(
    tmp_path: Path,
) -> tuple[RunnerConfig, RunnerStore, dict[str, object]]:
    config, store, _, _ = _candidate(tmp_path)
    candidate = store.review_candidate()
    assert candidate is not None
    original = candidate.completion | {"status": "waiting_external"}
    config.state_dir.mkdir(parents=True, exist_ok=True)
    output = config.state_dir / "original-completion.json"
    output.write_text(json.dumps(original), encoding="utf-8")
    _write_transcript(config.state_dir / "stdout.jsonl", json.dumps(original))
    with sqlite3.connect(store.db_path) as db:
        db.execute(
            "UPDATE attempts SET status='failed',failure_code='completion_invalid',"
            "output_path=?,evidence_json=NULL WHERE id='implementation'",
            (str(output),),
        )
        db.execute("UPDATE tasks SET status='failed' WHERE id='engineering'")
    (config.repo / "later.txt").write_text("runner change\n", encoding="utf-8")
    _git(config.repo, "add", "later.txt")
    _git(config.repo, "commit", "-m", "later runner change")
    store.pause()
    return config, store, original


def _record_failed_output(
    store: RunnerStore, evidence: dict[str, object] | None
) -> None:
    with sqlite3.connect(store.db_path) as db:
        db.execute(
            "UPDATE attempts SET evidence_json=? WHERE id='implementation'",
            (json.dumps(evidence) if evidence is not None else None,),
        )


def _output_evidence(source: Path) -> dict[str, object]:
    return {
        "failed_output_digest_version": 1,
        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
    }


def test_failed_output_digest_is_recorded_with_failure(tmp_path: Path) -> None:
    config, store, _ = _failed_candidate(tmp_path)
    source = config.state_dir / "original-completion.json"
    with sqlite3.connect(store.db_path) as db:
        db.execute(
            "UPDATE attempts SET status='running',failure_code=NULL,evidence_json=NULL "
            "WHERE id='implementation'"
        )
        db.execute("UPDATE tasks SET status='running' WHERE id='engineering'")
    store.finish(
        "implementation",
        "engineering",
        "failed",
        failure_code="completion_invalid",
        evidence=runner._failed_output_evidence(source),
    )
    with sqlite3.connect(store.db_path) as db:
        assert db.execute(
            "SELECT status,failure_code,evidence_json FROM attempts "
            "WHERE id='implementation'"
        ).fetchone() == (
            "failed",
            "completion_invalid",
            json.dumps(_output_evidence(source), sort_keys=True),
        )
        assert (
            db.execute(
                "SELECT value FROM runner_meta "
                "WHERE key='failed_output_digest_min_rowid'"
            ).fetchone()
            == db.execute(
                "SELECT CAST(rowid AS TEXT) FROM attempts WHERE id='implementation'"
            ).fetchone()
        )


@pytest.mark.parametrize("output", [b'{"invalid": true}', None])
def test_runner_records_failure_time_output_or_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, output: bytes | None
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "Runner Test")
    (repo / "README.md").write_text("baseline\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "baseline")
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
        ENGINEERING_SPEC_ID,
        ENGINEERING_SPEC_AREA,
        ENGINEERING_SPEC_PROMPT,
        task_kind="engineering",
    )
    monkeypatch.setattr(
        runner,
        "_select_task",
        lambda _store, _scope, _roadmap: store.task(ENGINEERING_SPEC_ID),
    )
    fake = tmp_path / "fake-child.py"
    fake.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "from pathlib import Path\n"
        "sys.stdin.read()\n"
        + (
            f"Path(sys.argv[sys.argv.index('-o') + 1]).write_bytes({output!r})\n"
            if output is not None
            else ""
        ),
        encoding="utf-8",
    )
    fake.chmod(0o700)
    result = run_once(config.model_copy(update={"codex": str(fake)}))
    assert (result.status, result.reason) == ("failed", "completion_invalid")
    assert result.attempt_id is not None
    with sqlite3.connect(store.db_path) as db:
        row = db.execute(
            "SELECT status,failure_code,output_path,evidence_json FROM attempts "
            "WHERE id=?",
            (result.attempt_id,),
        ).fetchone()
    assert row is not None
    assert row[:2] == ("failed", "completion_invalid")
    assert json.loads(row[3]) == {
        "failed_output_digest_version": 1,
        "sha256": hashlib.sha256(output).hexdigest() if output is not None else None,
    }
    assert Path(row[2]).exists() is (output is not None)


def test_recorded_digest_accepts_unchanged_source(tmp_path: Path) -> None:
    config, store, _ = _failed_candidate(tmp_path)
    _record_failed_output(
        store, _output_evidence(config.state_dir / "original-completion.json")
    )
    assert _recover(config, store) is not None


def test_recorded_digest_rejects_postfailure_rewrite_with_new_pin(
    tmp_path: Path,
) -> None:
    config, store, _ = _failed_candidate(tmp_path)
    source = config.state_dir / "original-completion.json"
    _record_failed_output(store, _output_evidence(source))
    source.write_bytes(source.read_bytes() + b" ")
    _write_transcript(config.state_dir / "stdout.jsonl", source.read_text())
    assert _recover(config, store) is None


def test_recorded_digest_erased_before_candidate_still_rejects_new_pin(
    tmp_path: Path,
) -> None:
    config, store, _ = _failed_candidate(tmp_path)
    source = config.state_dir / "original-completion.json"
    with sqlite3.connect(store.db_path) as db:
        db.execute(
            "UPDATE attempts SET status='running',failure_code=NULL,evidence_json=NULL "
            "WHERE id='implementation'"
        )
        db.execute("UPDATE tasks SET status='running' WHERE id='engineering'")
    store.finish(
        "implementation",
        "engineering",
        "failed",
        failure_code="completion_invalid",
        evidence=runner._failed_output_evidence(source),
    )
    _record_failed_output(store, None)
    source.write_bytes(source.read_bytes() + b" ")
    _write_transcript(config.state_dir / "stdout.jsonl", source.read_text())
    assert _recover(config, store) is None


@pytest.mark.parametrize("delete_cutoff", [False, True])
def test_older_legacy_failure_respects_activation_provenance(
    tmp_path: Path, delete_cutoff: bool
) -> None:
    config, store, _ = _failed_candidate(tmp_path)
    assert store.enqueue(
        "new-engineering", "__engineering__", "fixture", task_kind="engineering"
    )
    task = store.task("new-engineering")
    assert task is not None
    store.claim(task, "new-attempt", tmp_path / "new-output", tmp_path / "new-error")
    store.finish(
        "new-attempt",
        task.id,
        "failed",
        failure_code="completion_invalid",
        evidence={"failed_output_digest_version": 1, "sha256": None},
    )
    if delete_cutoff:
        with sqlite3.connect(store.db_path) as db:
            db.execute(
                "DELETE FROM runner_meta WHERE key='failed_output_digest_min_rowid'"
            )
    assert (_recover(config, store) is None) is delete_cutoff


@pytest.mark.parametrize(
    "tampered", [None, {"failed_output_digest_version": 1, "sha256": "0" * 64}]
)
def test_recorded_digest_reviewer_rejects_marker_tampering(
    tmp_path: Path, tampered: dict[str, object] | None
) -> None:
    config, store, _ = _failed_candidate(tmp_path)
    source = config.state_dir / "original-completion.json"
    _record_failed_output(store, _output_evidence(source))
    assert _recover(config, store)
    _record_failed_output(store, tampered)
    store.resume()
    fake = tmp_path / "must-not-run"
    assert run_once(config.model_copy(update={"codex": str(fake)})).status == "idle"
    assert store.task("engineering").engineering_status is None  # type: ignore[union-attr]
    assert not fake.exists()


@pytest.mark.parametrize(
    "tampered", [None, {"failed_output_digest_version": 1, "sha256": "0" * 64}]
)
def test_recorded_digest_final_review_cas_rejects_marker_tampering(
    tmp_path: Path, tampered: dict[str, object] | None
) -> None:
    config, store, _ = _failed_candidate(tmp_path)
    source = config.state_dir / "original-completion.json"
    _record_failed_output(store, _output_evidence(source))
    assert _recover(config, store)
    candidate = store.review_candidate()
    assert candidate is not None
    context = {"review": "fixture"}
    review_id = "review"
    assert store.claim_review(
        candidate, review_id, source, context, "2026-01-01T00:00:00+00:00"
    )
    _record_failed_output(store, tampered)
    assert not store.finish_review(
        candidate,
        review_id,
        status="completed",
        receipt=context | {"verdict": "PASS"},
    )
    assert store.task("engineering").engineering_status is None  # type: ignore[union-attr]


def test_recorded_digest_reviewer_rejects_marker_erasure_during_review(
    tmp_path: Path,
) -> None:
    config, store, _ = _failed_candidate(tmp_path)
    source = config.state_dir / "original-completion.json"
    _record_failed_output(store, _output_evidence(source))
    assert _recover(config, store)
    store.resume()
    fake = tmp_path / "fake-reviewer.py"
    fake.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sqlite3, sys\n"
        "from pathlib import Path\n"
        "context = json.loads(sys.stdin.read().split('fields: ', 1)[1])\n"
        f"with sqlite3.connect({str(store.db_path)!r}) as db:\n"
        '    db.execute("UPDATE attempts SET evidence_json=NULL '
        "WHERE id='implementation'\")\n"
        "context['verdict'] = 'PASS'\n"
        "Path(sys.argv[sys.argv.index('-o') + 1]).write_text(json.dumps(context))\n",
        encoding="utf-8",
    )
    fake.chmod(0o700)
    assert run_once(config.model_copy(update={"codex": str(fake)})).status == "idle"
    assert store.task("engineering").engineering_status is None  # type: ignore[union-attr]
    with sqlite3.connect(store.db_path) as db:
        assert db.execute("SELECT failure_code FROM review_attempts").fetchone() == (
            "receipt_invalid",
        )


@pytest.mark.parametrize(
    "evidence",
    [
        {"failed_output_digest_version": 1, "sha256": None},
        {"failed_output_digest_version": 1},
        {"failed_output_digest_version": 2, "sha256": "a" * 64},
        {"failed_output_digest_version": 1, "sha256": "invalid"},
    ],
)
def test_recorded_digest_rejects_unavailable_or_malformed(
    tmp_path: Path, evidence: dict[str, object]
) -> None:
    config, store, _ = _failed_candidate(tmp_path)
    _record_failed_output(store, evidence)
    assert _recover(config, store) is None


def test_failed_candidate_recovery_requires_independent_pass(tmp_path: Path) -> None:
    config, store, original = _failed_candidate(tmp_path)
    source = config.state_dir / "original-completion.json"
    source_hash = source.read_bytes()
    recovery_id = _recover(config, store)
    assert recovery_id is not None and recovery_id != "implementation"
    assert _recover(config, store) is None
    assert source.read_bytes() == source_hash
    assert json.loads(source.read_text(encoding="utf-8")) == original
    task = store.task("engineering")
    assert task is not None and task.canonical_state == "WAITING_EXTERNAL"
    assert task.engineering_status is None
    with sqlite3.connect(store.db_path) as db:
        assert db.execute(
            "SELECT status,failure_code FROM attempts WHERE id='implementation'"
        ).fetchone() == ("failed", "completion_invalid")
        assert db.execute(
            "SELECT status FROM attempts WHERE id=?", (recovery_id,)
        ).fetchone() == ("waiting_external",)
    store.resume()
    fake = tmp_path / "fake-reviewer.py"
    _fake_reviewer(fake, verdict="PASS")
    result = run_once(config.model_copy(update={"codex": str(fake)}))
    assert (result.status, result.attempt_id) == ("completed", recovery_id)
    task = store.task("engineering")
    assert task is not None
    assert (task.canonical_state, task.engineering_status, task.investment_status) == (
        "DONE",
        "ENGINEERING_COMPLETE",
        "NOT_EVALUATED",
    )
    with sqlite3.connect(store.db_path) as db:
        assert db.execute(
            "SELECT status,failure_code FROM attempts WHERE id='implementation'"
        ).fetchone() == ("failed", "completion_invalid")
        receipt = db.execute("SELECT receipt_json FROM review_attempts").fetchone()
        assert receipt is not None
        receipt_payload = json.loads(receipt[0])
        assert receipt_payload["product_commit"] == original["integrated_commit"]
        context = {
            key: value for key, value in receipt_payload.items() if key != "verdict"
        }
        with pytest.raises(ValueError, match="identity mismatch"):
            validate_receipt(
                {
                    key: value
                    for key, value in receipt_payload.items()
                    if key != "product_commit"
                },
                context,
            )


def test_existing_legacy_recovery_envelope_remains_reviewable(tmp_path: Path) -> None:
    config, store, _ = _failed_candidate(tmp_path)
    recovery_id = _recover(config, store)
    assert recovery_id is not None
    with sqlite3.connect(store.db_path) as db:
        row = db.execute(
            "SELECT evidence_json FROM attempts WHERE id=?", (recovery_id,)
        ).fetchone()
        assert row is not None
        envelope = json.loads(row[0])
        envelope["recovery"].pop("source_evidence_identity")
        db.execute(
            "UPDATE attempts SET evidence_json=? WHERE id=?",
            (json.dumps(envelope), recovery_id),
        )
    store.resume()
    fake = tmp_path / "fake-reviewer.py"
    _fake_reviewer(fake, verdict="PASS")
    assert (
        run_once(config.model_copy(update={"codex": str(fake)})).status == "completed"
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "tests",
        "review",
        "commit",
        "wrong_diff",
        "evidence",
        "handoff",
        "blocked_reason",
        "owned_changed",
        "original_changed",
    ],
)
def test_failed_candidate_recovery_rejects_invalid_source(
    tmp_path: Path, mutation: str
) -> None:
    config, store, original = _failed_candidate(tmp_path)
    if mutation == "tests":
        original["tests_passed"] = False
    elif mutation == "review":
        original["review_passed"] = True
    elif mutation == "commit":
        original["integrated_commit"] = "0" * 40
    elif mutation == "wrong_diff":
        original["integrated_commit"] = _git(config.repo, "rev-parse", "main")
    elif mutation == "evidence":
        original["evidence"] = []
    elif mutation == "handoff":
        original["handoff_path"] = None
    elif mutation == "blocked_reason":
        original["blocked_reason"] = "actual wait"
    elif mutation == "owned_changed":
        owned = Path(original["evidence"][0]["path"])  # type: ignore[index]
        owned.write_text("changed\n", encoding="utf-8")
    elif mutation == "original_changed":
        original["status"] = "blocked"
    if mutation != "owned_changed":
        source_text = json.dumps(original)
        (config.state_dir / "original-completion.json").write_text(
            source_text, encoding="utf-8"
        )
        _write_transcript(config.state_dir / "stdout.jsonl", source_text)
    assert _recover(config, store) is None
    assert store.task("engineering").canonical_state == "FAILED"  # type: ignore[union-attr]


def test_recovery_reviewer_rejects_stale_original(tmp_path: Path) -> None:
    config, store, _ = _failed_candidate(tmp_path)
    assert _recover(config, store)
    store.resume()
    source = config.state_dir / "original-completion.json"
    source.write_bytes(source.read_bytes() + b" ")
    fake = tmp_path / "must-not-run"
    assert run_once(config.model_copy(update={"codex": str(fake)})).status == "idle"
    assert store.task("engineering").engineering_status is None  # type: ignore[union-attr]
    assert not fake.exists()


def test_recovery_rejects_wrong_operator_pin(tmp_path: Path) -> None:
    config, store, _ = _failed_candidate(tmp_path)
    assert _recover(config, store, expected_sha256="0" * 64) is None
    assert store.task("engineering").canonical_state == "FAILED"  # type: ignore[union-attr]


def test_recovery_rejects_transcript_mismatch(tmp_path: Path) -> None:
    config, store, _ = _failed_candidate(tmp_path)
    _write_transcript(config.state_dir / "stdout.jsonl", "other")
    assert _recover(config, store) is None
    assert store.task("engineering").canonical_state == "FAILED"  # type: ignore[union-attr]


def test_recovery_rejects_substitution_between_parse_and_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, store, _ = _failed_candidate(tmp_path)
    source = config.state_dir / "original-completion.json"
    original_read = runner._recovery_output

    def substitute(path: Path, current: RunnerConfig) -> bytes:
        data = original_read(path, current)
        if path == source:
            source.write_bytes(data + b" ")
        return data

    monkeypatch.setattr(runner, "_recovery_output", substitute)
    assert _recover(config, store) is None
    assert store.task("engineering").canonical_state == "FAILED"  # type: ignore[union-attr]


def test_recovery_reviewer_rejects_stale_transcript(tmp_path: Path) -> None:
    config, store, _ = _failed_candidate(tmp_path)
    assert _recover(config, store)
    store.resume()
    transcript = config.state_dir / "stdout.jsonl"
    transcript.write_bytes(transcript.read_bytes() + b" ")
    fake = tmp_path / "must-not-run"
    assert run_once(config.model_copy(update={"codex": str(fake)})).status == "idle"
    assert store.task("engineering").engineering_status is None  # type: ignore[union-attr]
    assert not fake.exists()


def test_recovery_reviewer_rejects_corrected_payload_mismatch(tmp_path: Path) -> None:
    config, store, _ = _failed_candidate(tmp_path)
    recovery_id = _recover(config, store)
    assert recovery_id is not None
    store.resume()
    with sqlite3.connect(store.db_path) as db:
        row = db.execute(
            "SELECT evidence_json FROM attempts WHERE id=?", (recovery_id,)
        ).fetchone()
        assert row is not None
        envelope = json.loads(row[0])
        envelope["completion"]["blocked_reason"] = "changed"
        db.execute(
            "UPDATE attempts SET evidence_json=? WHERE id=?",
            (json.dumps(envelope), recovery_id),
        )
    fake = tmp_path / "must-not-run"
    assert run_once(config.model_copy(update={"codex": str(fake)})).status == "idle"
    assert store.task("engineering").engineering_status is None  # type: ignore[union-attr]
    assert not fake.exists()


def test_recovery_reviewer_rejects_stale_source_row(tmp_path: Path) -> None:
    config, store, _ = _failed_candidate(tmp_path)
    assert _recover(config, store)
    store.resume()
    with sqlite3.connect(store.db_path) as db:
        db.execute(
            "UPDATE attempts SET failure_code='changed' WHERE id='implementation'"
        )
    fake = tmp_path / "must-not-run"

    assert run_once(config.model_copy(update={"codex": str(fake)})).status == "idle"
    assert store.task("engineering").engineering_status is None  # type: ignore[union-attr]
    assert not fake.exists()


def test_recovery_reviewer_rejects_later_owned_commit(tmp_path: Path) -> None:
    config, store, original = _failed_candidate(tmp_path)
    assert _recover(config, store)
    store.resume()
    owned = Path(original["evidence"][0]["path"])  # type: ignore[index]
    owned.write_text("later version\n", encoding="utf-8")
    _git(config.repo, "add", "backend")
    _git(config.repo, "commit", "-m", "later owned change")
    fake = tmp_path / "must-not-run"

    assert run_once(config.model_copy(update={"codex": str(fake)})).status == "idle"
    assert store.task("engineering").engineering_status is None  # type: ignore[union-attr]
    assert not fake.exists()


def test_recovery_reviewer_fail_leaves_task_waiting(tmp_path: Path) -> None:
    config, store, _ = _failed_candidate(tmp_path)
    recovery_id = _recover(config, store)
    assert recovery_id is not None
    store.resume()
    fake = tmp_path / "fake-reviewer.py"
    _fake_reviewer(fake, verdict="FAIL")

    assert run_once(config.model_copy(update={"codex": str(fake)})).status == "idle"
    task = store.task("engineering")
    assert task is not None
    assert task.canonical_state == "WAITING_EXTERNAL"
    assert task.engineering_status is None
    with sqlite3.connect(store.db_path) as db:
        assert db.execute(
            "SELECT status FROM attempts WHERE id=?", (recovery_id,)
        ).fetchone() == ("waiting_external",)


def test_recovery_rejects_source_change_during_review(tmp_path: Path) -> None:
    config, store, _ = _failed_candidate(tmp_path)
    assert _recover(config, store)
    store.resume()
    source = config.state_dir / "original-completion.json"
    fake = tmp_path / "fake-reviewer.py"
    fake.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        "from pathlib import Path\n"
        "context = json.loads(sys.stdin.read().split('fields: ', 1)[1])\n"
        f"source = Path({str(source)!r})\n"
        "source.write_bytes(source.read_bytes() + b' ')\n"
        "context['verdict'] = 'PASS'\n"
        "Path(sys.argv[sys.argv.index('-o') + 1]).write_text(json.dumps(context))\n",
        encoding="utf-8",
    )
    fake.chmod(0o700)

    assert run_once(config.model_copy(update={"codex": str(fake)})).status == "idle"
    assert store.task("engineering").engineering_status is None  # type: ignore[union-attr]
    with sqlite3.connect(store.db_path) as db:
        assert db.execute("SELECT failure_code FROM review_attempts").fetchone() == (
            "receipt_invalid",
        )


def test_recovery_cli_requires_paused_runner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    config, store, _ = _failed_candidate(tmp_path)
    store.resume()
    monkeypatch.setattr(runner, "load_config", lambda _path: config)
    args = [
        "recover-failed-candidate",
        "--config",
        str(tmp_path / "config.json"),
        "engineering",
        "--attempt-id",
        "implementation",
        "--expected-source-sha256",
        hashlib.sha256(
            (config.state_dir / "original-completion.json").read_bytes()
        ).hexdigest(),
    ]
    assert runner.main(args) == 2
    assert json.loads(capsys.readouterr().out)["recovery_attempt_id"] is None
    store.pause()
    assert runner.main(args) == 0
    assert json.loads(capsys.readouterr().out)["recovery_attempt_id"]
