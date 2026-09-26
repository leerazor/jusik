"""Implementation review transport recovery with isolated Git, clocks and children."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta, tzinfo
from pathlib import Path
from threading import Barrier
from types import ModuleType
from typing import Any, Self, cast

import pytest
from test_development_runner_backlog import _fake_blocked_child
from test_development_runner_recovery import _failed_candidate, _recover
from test_development_runner_review import _candidate, _fake_reviewer, _git
from test_development_runner_roadmap_code_review import (
    _approve,
    _implementation,
    _pending,
)

from jusik import development_runner as runner
from jusik import development_runner_store as journal


class Clock:
    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.now = datetime(2026, 9, 26, 0, 0, tzinfo=UTC)
        clock = self

        class FrozenDateTime(datetime):
            @classmethod
            def now(cls, tz: tzinfo | None = None) -> Self:
                return cls.fromtimestamp(clock.now.timestamp(), tz)

        monkeypatch.setattr(runner, "datetime", FrozenDateTime)
        monkeypatch.setattr(journal, "utc_now", lambda: clock.now.isoformat())

    def advance(self, seconds: int) -> None:
        self.now += timedelta(seconds=seconds)


def _transport_child(path: Path, *, code: str = "model_capacity") -> None:
    event = {"type": "turn.failed", "error": {"code": code}}
    path.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "sys.stdin.read()\n"
        f"print({json.dumps(event)!r})\n"
        "sys.exit(1)\n",
        encoding="utf-8",
    )
    path.chmod(0o700)


def _reviews(store: journal.RunnerStore) -> list[dict[str, Any]]:
    with sqlite3.connect(store.db_path) as db:
        db.row_factory = sqlite3.Row
        return [
            dict(row)
            for row in db.execute("SELECT * FROM review_attempts ORDER BY rowid")
        ]


def test_transport_failure_survives_restart_and_requires_due_independent_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = Clock(monkeypatch)
    config, store, _, product = _candidate(tmp_path)
    fake = tmp_path / "reviewer"
    _transport_child(fake)
    config = config.model_copy(update={"codex": str(fake)})
    assert runner.run_once(config).status == "idle"
    failed = _reviews(store)[0]
    stdout_path = Path(failed["output_path"]).parent / "stdout.jsonl"
    original_stdout = stdout_path.read_bytes()
    assert failed["failure_code"] == "review_transport_capacity"
    assert failed["retry_kind"] == "capacity"
    assert failed["transient_failures"] == 1
    assert failed["retry_after"] == (clock.now + timedelta(minutes=5)).isoformat()
    restarted = journal.RunnerStore(store.db_path)
    _fake_reviewer(fake, verdict="PASS")
    clock.advance(299)
    assert runner.run_once(config).status == "idle"
    assert len(_reviews(store)) == 1
    assert restarted.review_candidate() is None
    clock.advance(1)
    assert runner.run_once(config).status == "completed"
    rows = _reviews(store)
    assert len(rows) == 2 and rows[0] == failed
    assert stdout_path.read_bytes() == original_stdout
    receipt = json.loads(rows[1]["receipt_json"])
    assert receipt == json.loads(rows[1]["context_json"]) | {"verdict": "PASS"}
    assert receipt["product_commit"] == product
    assert receipt["main_head"] == product
    task = restarted.task("engineering")
    assert task is not None
    assert (task.canonical_state, task.engineering_status, task.investment_status) == (
        "DONE",
        "ENGINEERING_COMPLETE",
        "NOT_EVALUATED",
    )


def test_transport_anchor_allows_only_unrelated_committed_progress(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = Clock(monkeypatch)
    config, store, _, product = _candidate(tmp_path)
    fake = tmp_path / "reviewer"
    _transport_child(fake)
    config = config.model_copy(update={"codex": str(fake)})
    assert runner.run_once(config).status == "idle"
    (config.repo / "unrelated.txt").write_text("independent READY result\n")
    _git(config.repo, "add", "unrelated.txt")
    _git(config.repo, "commit", "-m", "independent work")
    head = _git(config.repo, "rev-parse", "main")
    _fake_reviewer(fake, verdict="PASS")
    clock.advance(300)
    assert runner.run_once(config).status == "completed"
    receipt = json.loads(_reviews(store)[-1]["receipt_json"])
    assert receipt["product_commit"] == product and receipt["main_head"] == head


@pytest.mark.parametrize(
    "code,kind",
    [
        ("model_capacity", "capacity"),
        ("rate_limit", "rate_limit"),
        ("network_error", "network"),
        ("503", "server"),
    ],
)
def test_repeated_transport_failures_back_off_without_spending_semantic_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, code: str, kind: str
) -> None:
    clock = Clock(monkeypatch)
    config, store, _, _ = _candidate(tmp_path)
    fake = tmp_path / "reviewer"
    _transport_child(fake, code=code)
    config = config.model_copy(update={"codex": str(fake), "daily_launches": None})
    for count, seconds in enumerate((300, 900, 3600, 3600), 1):
        assert runner.run_once(config).status == "idle"
        row = _reviews(store)[-1]
        assert row["retry_kind"] == kind and row["transient_failures"] == count
        assert (
            row["retry_after"] == (clock.now + timedelta(seconds=seconds)).isoformat()
        )
        clock.advance(seconds - 1)
        assert journal.RunnerStore(store.db_path).review_candidate() is None
        clock.advance(1)
        assert journal.RunnerStore(store.db_path).review_candidate() is not None
    assert store.launch_count(clock.now.strftime("%Y-%m-%d")) == 4
    _fake_reviewer(fake, verdict="PASS")
    assert runner.run_once(config).status == "completed"


def test_auth_waits_six_hours_without_changing_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = Clock(monkeypatch)
    config, store, _, _ = _candidate(tmp_path)
    fake = tmp_path / "reviewer"
    _transport_child(fake, code="unauthorized")
    config = config.model_copy(update={"codex": str(fake)})
    original = config.model_dump()
    assert runner.run_once(config).status == "idle"
    row = _reviews(store)[0]
    assert row["retry_kind"] == "auth"
    assert row["retry_after"] == (clock.now + timedelta(hours=6)).isoformat()
    clock.advance(21_599)
    assert runner.run_once(config).status == "idle"
    assert len(_reviews(store)) == 1 and config.model_dump() == original
    clock.advance(1)
    _fake_reviewer(fake, verdict="PASS")
    assert runner.run_once(config).status == "completed"


def test_waiting_transport_dispatches_independent_ready_then_reviews_same_product(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = Clock(monkeypatch)
    config, store, _, product = _candidate(tmp_path)
    fake = tmp_path / "child"
    _transport_child(fake)
    config = config.model_copy(update={"codex": str(fake)})
    assert runner.run_once(config).status == "idle"
    assert store.enqueue("ready", "entry-amount-distribution", "independent")
    _fake_blocked_child(fake)
    script = (
        fake.read_text()
        .replace("import json, sys", "import json, sys, subprocess")
        .replace(
            "prompt = sys.stdin.read()",
            "prompt = sys.stdin.read()\n"
            "Path('independent.txt').write_text('independent product\\n')\n"
            "subprocess.run(['git', 'add', 'independent.txt'], check=True)\n"
            "subprocess.run(['git', 'commit', '-m', 'independent product'], "
            "check=True)",
        )
    )
    fake.write_text(script)
    clock.advance(1)
    result = runner.run_once(config)
    assert (result.status, result.task_id) == ("blocked", "ready")
    assert len(_reviews(store)) == 1
    head = _git(config.repo, "rev-parse", "main")
    assert head != product
    clock.advance(299)
    _fake_reviewer(fake, verdict="PASS")
    assert runner.run_once(config).status == "completed"
    receipt = json.loads(_reviews(store)[-1]["receipt_json"])
    assert receipt["product_commit"] == product and receipt["main_head"] == head


def test_roadmap_code_transport_wait_allows_empty_queue_engineering_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = Clock(monkeypatch)
    config, store, fake = _pending(tmp_path)
    clock.advance(1)
    _approve(config, store, fake)
    clock.advance(1)
    _implementation(fake)
    assert runner.run_once(config).reason == "independent_review_pending"
    config = config.model_copy(
        update={
            "planning_enabled": False,
            "automatic_engineering_discovery": False,
        }
    )
    clock.advance(1)
    _transport_child(fake)
    runner.run_once(config)
    assert len(_reviews(store)) == 1
    # The fixture has exhausted the finite backlog. Make one never-attempted slot
    # available in this isolated DB, so the empty queue can exercise real fallback.
    with sqlite3.connect(store.db_path) as db:
        db.execute("DELETE FROM tasks WHERE id='lab-strategy-lifecycle-receipt-v1'")
    _fake_blocked_child(fake)
    clock.advance(1)
    result = runner.run_once(config)
    assert result.task_id == "lab-strategy-lifecycle-receipt-v1"
    assert result.status == "blocked" and len(_reviews(store)) == 1
    clock.advance(299)
    _fake_reviewer(fake, verdict="PASS")
    assert runner.run_once(config).status == "completed"
    task = store.task("roadmap-audit-v1")
    assert task is not None and task.engineering_status == "ENGINEERING_COMPLETE"
    assert task.investment_status == "NOT_EVALUATED"


@pytest.mark.parametrize(
    "mode", ["text", "stderr", "oversize", "unknown", "success", "invalid", "rejected"]
)
def test_only_terminated_structured_nonzero_transport_failure_opts_in(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    clock = Clock(monkeypatch)
    config, store, _, _ = _candidate(tmp_path)
    fake = tmp_path / "reviewer"
    if mode == "rejected":
        _fake_reviewer(fake, verdict="FAIL")
    elif mode == "invalid":
        _fake_reviewer(fake, verdict="PASS", wrong_head=True)
    else:
        event = json.dumps({"type": "turn.failed", "error": {"code": "model_capacity"}})
        content = {
            "text": json.dumps({"type": "item.completed", "item": {"text": event}}),
            "unknown": json.dumps(
                {"type": "turn.failed", "error": {"code": "unknown"}}
            ),
            "oversize": "x" * 1_048_577 + "\n" + event,
        }.get(mode, event)
        fake.write_text(
            "#!/usr/bin/env python3\nimport sys\nsys.stdin.read()\n"
            f"stream = sys.{'stderr' if mode == 'stderr' else 'stdout'}\n"
            f"print({content!r}, file=stream)\n"
            f"sys.exit({0 if mode == 'success' else 1})\n"
        )
        fake.chmod(0o700)
    config = config.model_copy(update={"codex": str(fake)})
    assert runner.run_once(config).status == "idle"
    row = _reviews(store)[0]
    assert row["retry_kind"] is None and row["retry_after"] is None
    assert row["transient_failures"] == 0
    clock.advance(86_400)
    assert store.review_candidate() is None
    assert runner.run_once(config).status == "idle"
    assert len(_reviews(store)) == 1


def test_nonzero_child_with_live_group_remains_quarantined(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    Clock(monkeypatch)
    config, store, _, _ = _candidate(tmp_path)
    fake = tmp_path / "reviewer"
    _transport_child(fake)
    monkeypatch.setattr(runner, "_process_group_alive", lambda _pid: True)
    assert (
        runner.run_once(config.model_copy(update={"codex": str(fake)})).status == "idle"
    )
    row = _reviews(store)[0]
    assert row["status"] == "quarantined" and row["retry_kind"] is None
    assert store.review_candidate() is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("retry_kind", None),
        ("retry_kind", "timeout"),
        ("retry_after", None),
        ("retry_after", "invalid"),
        ("retry_after", "2026-09-26T00:05:00"),
        ("retry_after", "2026-09-26T09:05:00+09:00"),
        ("retry_after", "2026-09-26T00:04:59+00:00"),
        ("transient_failures", 0),
        ("transient_failures", 7),
        ("failure_code", "codex_exit"),
    ],
)
def test_malformed_transport_metadata_blocks_selection_and_atomic_claim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str, value: object
) -> None:
    clock = Clock(monkeypatch)
    config, store, _, _ = _candidate(tmp_path)
    fake = tmp_path / "reviewer"
    _transport_child(fake)
    runner.run_once(config.model_copy(update={"codex": str(fake)}))
    clock.advance(300)
    candidate = store.review_candidate()
    assert candidate is not None
    context = runner._review_context(candidate, "retry", config)
    with sqlite3.connect(store.db_path) as db:
        db.execute(f"UPDATE review_attempts SET {field}=?", (value,))
    assert store.review_candidate() is None
    assert not store.claim_review(
        candidate, "retry", tmp_path / "receipt", context, clock.now.isoformat()
    )
    assert len(_reviews(store)) == 1


def test_due_claim_race_is_atomic_with_equal_timestamps_and_descending_ids(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = Clock(monkeypatch)
    config, store, _, _ = _candidate(tmp_path)
    fake = tmp_path / "reviewer"
    _transport_child(fake)
    runner.run_once(config.model_copy(update={"codex": str(fake)}))
    clock.advance(300)
    candidate = store.review_candidate()
    assert candidate is not None
    context = runner._review_context(candidate, "zzzz", config)
    barrier = Barrier(2)
    stores = [journal.RunnerStore(store.db_path), journal.RunnerStore(store.db_path)]

    def claim(index: int) -> bool:
        review_id = ("zzzz", "aaaa")[index]
        barrier.wait()
        return stores[index].claim_review(
            candidate,
            review_id,
            tmp_path / review_id,
            context | {"review_attempt_id": review_id},
            clock.now.isoformat(),
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(claim, range(2))) == [False, True]
    assert len(_reviews(store)) == 2
    assert store.review_candidate() is None
    assert not store.claim_review(
        candidate, "0000", tmp_path / "again", context, clock.now.isoformat()
    )


def test_claim_rechecks_due_time_instead_of_trusting_selection_or_launch_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = Clock(monkeypatch)
    config, store, _, _ = _candidate(tmp_path)
    fake = tmp_path / "reviewer"
    _transport_child(fake)
    runner.run_once(config.model_copy(update={"codex": str(fake)}))
    clock.advance(300)
    candidate = store.review_candidate()
    assert candidate is not None
    context = runner._review_context(candidate, "retry", config)
    scheduled = clock.now.isoformat()
    clock.advance(-1)
    assert not store.claim_review(
        candidate,
        "retry",
        tmp_path / "receipt",
        context,
        scheduled,
    )
    assert len(_reviews(store)) == 1


def test_transport_retries_preserve_two_nontransport_attempt_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = Clock(monkeypatch)
    config, store, _, _ = _candidate(tmp_path)
    fake = tmp_path / "reviewer"
    _transport_child(fake)
    runner.run_once(config.model_copy(update={"codex": str(fake)}))
    clock.advance(300)
    for review_id in ("z-restarted", "a-restarted"):
        candidate = store.review_candidate()
        assert candidate is not None
        context = runner._review_context(candidate, review_id, config)
        assert store.claim_review(
            candidate, review_id, tmp_path / review_id, context, clock.now.isoformat()
        )
        assert store.recover_running_reviews([review_id]) == [review_id]
        clock.advance(1)
    assert store.review_candidate() is None
    assert len(_reviews(store)) == 3


def test_running_retry_blocks_claim_when_prior_failure_sorts_after_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = Clock(monkeypatch)
    config, store, _, _ = _candidate(tmp_path)
    fake = tmp_path / "reviewer"
    _transport_child(fake)
    runner.run_once(config.model_copy(update={"codex": str(fake)}))
    failed = _reviews(store)[0]
    clock.advance(300)
    candidate = store.review_candidate()
    assert candidate is not None
    context = runner._review_context(candidate, "!earlier-id", config)
    assert store.claim_review(
        candidate, "!earlier-id", tmp_path / "receipt", context, clock.now.isoformat()
    )
    # Model identical wall-clock timestamps independently of random UUID ordering.
    with sqlite3.connect(store.db_path) as db:
        db.execute(
            "UPDATE review_attempts SET started_at=? WHERE id='!earlier-id'",
            (failed["started_at"],),
        )
        assert (
            db.execute(
                "SELECT id FROM review_attempts "
                "ORDER BY started_at DESC,id DESC LIMIT 1"
            ).fetchone()[0]
            == failed["id"]
        )
    other = journal.RunnerStore(store.db_path)
    assert other.review_candidate() is None
    assert not other.claim_review(
        candidate, "!another", tmp_path / "another", context, clock.now.isoformat()
    )
    assert len(_reviews(store)) == 2


@pytest.mark.parametrize("gate", ["pause", "quota", "cooldown"])
def test_due_transport_launch_obeys_pause_quota_and_cooldown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, gate: str
) -> None:
    clock = Clock(monkeypatch)
    config, store, _, _ = _candidate(tmp_path)
    fake = tmp_path / "reviewer"
    _transport_child(fake)
    config = config.model_copy(update={"codex": str(fake)})
    runner.run_once(config)
    clock.advance(300)
    candidate = store.review_candidate()
    assert candidate is not None
    context = runner._review_context(candidate, "retry", config)
    if gate == "pause":
        store.pause()
        assert not store.claim_review(
            candidate, "retry", tmp_path / "receipt", context, clock.now.isoformat()
        )
    elif gate == "quota":
        config = config.model_copy(update={"daily_launches": 1})
    else:
        config = config.model_copy(update={"cooldown_seconds": 3600})
    assert runner.run_once(config).status == ("paused" if gate == "pause" else gate)
    assert len(_reviews(store)) == 1


@pytest.mark.parametrize(
    "mutation",
    [
        "owned",
        "evidence",
        "product",
        "baseline",
        "anchor",
        "earlier_anchor",
        "head_during_review",
    ],
)
def test_transport_anchor_and_current_review_identity_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    clock = Clock(monkeypatch)
    config, store, _, _ = _candidate(tmp_path)
    fake = tmp_path / "reviewer"
    _transport_child(fake)
    config = config.model_copy(update={"codex": str(fake)})
    runner.run_once(config)
    clock.advance(300)
    if mutation == "earlier_anchor":
        runner.run_once(config)
        clock.advance(900)
    candidate = store.review_candidate()
    assert candidate is not None
    if mutation == "owned":
        owned = Path(candidate.completion["evidence"][0]["path"])
        owned.write_text("changed owned product\n")
        _git(config.repo, "add", "backend")
        _git(config.repo, "commit", "-m", "owned product changed")
    elif mutation in {"evidence", "product", "baseline"}:
        with sqlite3.connect(store.db_path) as db:
            if mutation == "baseline":
                db.execute("UPDATE attempts SET baseline_head=?", ("0" * 40,))
            else:
                completion = json.loads(json.dumps(candidate.completion))
                if mutation == "evidence":
                    completion["evidence"][0]["sha256"] = "0" * 64
                else:
                    completion["integrated_commit"] = candidate.baseline_head
                db.execute(
                    "UPDATE attempts SET evidence_json=?",
                    (
                        json.dumps(
                            {"review_candidate_version": 1, "completion": completion}
                        ),
                    ),
                )
    elif mutation in {"anchor", "earlier_anchor"}:
        row = _reviews(store)[0]
        context = json.loads(row["context_json"])
        context["owned_file_hashes"] = {
            name: "0" * 64 for name in context["owned_file_hashes"]
        }
        with sqlite3.connect(store.db_path) as db:
            db.execute(
                "UPDATE review_attempts SET context_json=? WHERE id=?",
                (json.dumps(context), row["id"]),
            )
    _fake_reviewer(fake, verdict="PASS")
    if mutation == "head_during_review":
        script = (
            fake.read_text()
            .replace("import json, sys", "import json, sys, subprocess")
            .replace(
                "prompt = sys.stdin.read()",
                "prompt = sys.stdin.read()\n"
                "Path('later.txt').write_text('later\\n')\n"
                "subprocess.run(['git', 'add', 'later.txt'], check=True)\n"
                "subprocess.run(['git', 'commit', '-m', 'later'], check=True)",
            )
        )
        fake.write_text(script)
    assert runner.run_once(config).status == "idle"
    task = store.task("engineering")
    assert task is not None and task.engineering_status is None
    assert all(row["status"] != "completed" for row in _reviews(store))


def test_caller_cannot_supply_transport_anchor_without_store_opt_in(
    tmp_path: Path,
) -> None:
    config, store, _, _ = _candidate(tmp_path)
    candidate = store.review_candidate()
    assert candidate is not None
    forged = replace(
        candidate, transport_anchor={"identity": {}, "main_head": "0" * 40}
    )
    with pytest.raises(ValueError, match="anchor changed"):
        runner._review_context(forged, "forged", config)
    assert not store.claim_review(
        forged, "forged", tmp_path / "receipt", {}, datetime.now(UTC).isoformat()
    )


@pytest.mark.parametrize("divergence", ["product", "previous_review"])
def test_transport_retry_requires_product_and_every_previous_review_ancestry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, divergence: str
) -> None:
    clock = Clock(monkeypatch)
    config, store, baseline, product = _candidate(tmp_path)
    fake = tmp_path / "reviewer"
    _transport_child(fake)
    config = config.model_copy(update={"codex": str(fake)})
    runner.run_once(config)
    clock.advance(300)
    if divergence == "previous_review":
        (config.repo / "unrelated.txt").write_text("unrelated\n")
        _git(config.repo, "add", "unrelated.txt")
        _git(config.repo, "commit", "-m", "unrelated")
        runner.run_once(config)
        clock.advance(900)
    previous = _git(config.repo, "rev-parse", "main")
    tree = _git(config.repo, "rev-parse", "main^{tree}")
    # Only the isolated fixture ref changes; keep its exact tree and owned blobs.
    alternate = _git(
        config.repo,
        "commit-tree",
        tree,
        "-p",
        baseline if divergence == "product" else product,
        "-m",
        "alternate lineage",
    )
    _git(config.repo, "update-ref", "refs/heads/main", alternate, previous)
    _fake_reviewer(fake, verdict="PASS")
    assert runner.run_once(config).status == "idle"
    assert all(row["status"] == "failed" for row in _reviews(store))
    task = store.task("engineering")
    assert task is not None and task.engineering_status is None


def test_caller_cannot_remove_transport_anchor_from_finalization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = Clock(monkeypatch)
    config, store, _, _ = _candidate(tmp_path)
    fake = tmp_path / "reviewer"
    _transport_child(fake)
    runner.run_once(config.model_copy(update={"codex": str(fake)}))
    clock.advance(300)
    candidate = store.review_candidate()
    assert candidate is not None and candidate.transport_anchor is not None
    context = runner._review_context(candidate, "retry", config)
    assert store.claim_review(
        candidate, "retry", tmp_path / "receipt", context, clock.now.isoformat()
    )
    assert not store.finish_review(
        replace(candidate, transport_anchor=None),
        "retry",
        status="completed",
        receipt=context | {"verdict": "PASS"},
        repo=config.repo,
    )
    assert store.finish_review(
        candidate,
        "retry",
        status="completed",
        receipt=context | {"verdict": "PASS"},
        repo=config.repo,
    )


def test_recovery_product_remains_bound_across_transport_and_later_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = Clock(monkeypatch)
    config, store, _ = _failed_candidate(tmp_path)
    assert _recover(config, store) is not None
    store.resume()
    fake = tmp_path / "reviewer"
    _transport_child(fake)
    config = config.model_copy(update={"codex": str(fake)})
    assert runner.run_once(config).status == "idle"
    (config.repo / "another.txt").write_text("unrelated\n")
    _git(config.repo, "add", "another.txt")
    _git(config.repo, "commit", "-m", "unrelated")
    clock.advance(300)
    _fake_reviewer(fake, verdict="PASS")
    assert runner.run_once(config).status == "completed"


@pytest.mark.parametrize("history", ["linear", "sibling_rewind", "changed_identity"])
def test_transport_anchor_retains_prior_nontransport_review_ancestry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, history: str
) -> None:
    clock = Clock(monkeypatch)
    config, store, _ = _failed_candidate(tmp_path)
    assert _recover(config, store) is not None
    store.resume()
    candidate = store.review_candidate()
    assert candidate is not None
    prior_head = _git(config.repo, "rev-parse", "main")
    context = runner._review_context(candidate, "prior-timeout", config)
    assert store.claim_review(
        candidate,
        "prior-timeout",
        tmp_path / "prior-receipt",
        context,
        clock.now.isoformat(),
    )
    assert store.finish_review(
        candidate,
        "prior-timeout",
        status="failed",
        failure_code="timeout",
    )
    # Legacy-only selection still permits a bounded recovery review.
    legacy_candidate = store.review_candidate()
    assert legacy_candidate is not None and legacy_candidate.transport_anchor is None
    clock.advance(1)
    tree = _git(config.repo, "rev-parse", "main^{tree}")
    current_head = _git(
        config.repo,
        "commit-tree",
        tree,
        "-p",
        candidate.completion["integrated_commit"]
        if history == "sibling_rewind"
        else prior_head,
        "-m",
        "next review context",
    )
    _git(config.repo, "update-ref", "refs/heads/main", current_head, prior_head)
    fake = tmp_path / "reviewer"
    _transport_child(fake)
    config = config.model_copy(update={"codex": str(fake)})
    assert runner.run_once(config).status == "idle"
    assert _reviews(store)[-1]["failure_code"] == "review_transport_capacity"
    clock.advance(300)
    if history == "changed_identity":
        context["owned_file_hashes"] = {
            name: "0" * 64 for name in context["owned_file_hashes"]
        }
        with sqlite3.connect(store.db_path) as db:
            db.execute(
                "UPDATE review_attempts SET context_json=? WHERE id='prior-timeout'",
                (json.dumps(context),),
            )
    anchored = store.review_candidate()
    if history == "changed_identity":
        assert anchored is None
    else:
        assert anchored is not None and anchored.transport_anchor is not None
        assert anchored.transport_anchor["review_heads"] == [prior_head, current_head]
        assert anchored.transport_anchor["first_review_id"] == "prior-timeout"
    _fake_reviewer(fake, verdict="PASS")
    result = runner.run_once(config)
    assert result.status == ("completed" if history == "linear" else "idle")
    task = store.task("engineering")
    assert task is not None
    if history != "linear":
        assert len(_reviews(store)) == 2 and task.engineering_status is None
        if history == "sibling_rewind":
            assert task.blocker is not None
            assert task.blocker["blocker_reason"] == "review_candidate_stale"
    else:
        assert len(_reviews(store)) == 3
        assert task.engineering_status == "ENGINEERING_COMPLETE"


@pytest.mark.parametrize("failure_code", ["timeout", "codex_exit"])
def test_legacy_failure_cannot_enable_historical_product_review(
    tmp_path: Path, failure_code: str
) -> None:
    config, store, _, _ = _candidate(tmp_path)
    candidate = store.review_candidate()
    assert candidate is not None
    context = runner._review_context(candidate, "legacy", config)
    assert store.claim_review(
        candidate,
        "legacy",
        tmp_path / "receipt",
        context,
        datetime.now(UTC).isoformat(),
    )
    assert store.finish_review(
        candidate, "legacy", status="failed", failure_code=failure_code
    )
    (config.repo / "unrelated.txt").write_text("unrelated\n")
    _git(config.repo, "add", "unrelated.txt")
    _git(config.repo, "commit", "-m", "unrelated")
    fake = tmp_path / "reviewer"
    _fake_reviewer(fake, verdict="PASS")
    assert (
        runner.run_once(config.model_copy(update={"codex": str(fake)})).status == "idle"
    )
    assert len(_reviews(store)) == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("main_head", []),
        ("main_head", "invalid"),
        ("product_commit", "invalid"),
        ("owned_file_hashes", []),
        ("owned_file_hashes", {"file": "invalid"}),
        ("_transport_candidate", None),
    ],
)
def test_malformed_anchor_cannot_launch_or_block_other_ready_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str, value: object
) -> None:
    clock = Clock(monkeypatch)
    config, store, _, _ = _candidate(tmp_path)
    fake = tmp_path / "reviewer"
    _transport_child(fake)
    runner.run_once(config.model_copy(update={"codex": str(fake)}))
    row = _reviews(store)[0]
    context = json.loads(row["context_json"])
    context[field] = value
    with sqlite3.connect(store.db_path) as db:
        db.execute("UPDATE review_attempts SET context_json=?", (json.dumps(context),))
    clock.advance(300)
    assert store.review_candidate() is None
    assert store.enqueue("ready", "entry-amount-distribution", "independent")
    _fake_blocked_child(fake)
    result = runner.run_once(config.model_copy(update={"codex": str(fake)}))
    assert result.task_id == "ready" and result.status == "blocked"
    assert len(_reviews(store)) == 1


@pytest.mark.parametrize("mutation", ["head", "owned", "evidence"])
def test_final_transport_pass_transaction_rechecks_current_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    clock = Clock(monkeypatch)
    config, store, _, _ = _candidate(tmp_path)
    if mutation == "evidence":
        extra = config.artifact_dir / "report.txt"
        extra.parent.mkdir()
        extra.write_text("frozen evidence\n")
        with sqlite3.connect(store.db_path) as db:
            envelope = json.loads(
                db.execute("SELECT evidence_json FROM attempts").fetchone()[0]
            )
            envelope["completion"]["evidence"].append(
                {
                    "path": str(extra),
                    "sha256": hashlib.sha256(extra.read_bytes()).hexdigest(),
                }
            )
            db.execute("UPDATE attempts SET evidence_json=?", (json.dumps(envelope),))
    fake = tmp_path / "reviewer"
    _transport_child(fake)
    runner.run_once(config.model_copy(update={"codex": str(fake)}))
    clock.advance(300)
    candidate = store.review_candidate()
    assert candidate is not None
    context = runner._review_context(candidate, "retry", config)
    assert store.claim_review(
        candidate, "retry", tmp_path / "receipt", context, clock.now.isoformat()
    )
    if mutation == "head":
        (config.repo / "later.txt").write_text("late commit\n")
        _git(config.repo, "add", "later.txt")
        _git(config.repo, "commit", "-m", "late commit")
    elif mutation == "owned":
        Path(candidate.completion["evidence"][0]["path"]).write_text("late mutation\n")
    else:
        extra.write_text("late evidence mutation\n")
    with pytest.raises(ValueError, match="changed"):
        store.finish_review(
            candidate,
            "retry",
            status="completed",
            receipt=context | {"verdict": "PASS"},
            repo=config.repo,
        )
    task = store.task("engineering")
    assert task is not None and task.engineering_status is None


def _legacy_store_type(monkeypatch: pytest.MonkeyPatch) -> type[journal.RunnerStore]:
    """Execute the actual frozen pre-change reader, not a reimplementation."""
    repo = Path(__file__).resolve().parents[2]
    source = subprocess.run(
        [
            "git",
            "show",
            "d30c809e2d8a501b5b174421b850a95f5f317f5a:backend/jusik/development_runner_store.py",
        ],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    module = ModuleType("_frozen_review_store")
    monkeypatch.setitem(sys.modules, module.__name__, module)
    exec(compile(source, "frozen-development-runner-store.py", "exec"), module.__dict__)
    return cast(type[journal.RunnerStore], module.RunnerStore)


def test_actual_old_reader_defers_new_rows_before_after_due_and_interrupted_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = Clock(monkeypatch)
    config, store, _, _ = _candidate(tmp_path)
    fake = tmp_path / "reviewer"
    _transport_child(fake)
    runner.run_once(config.model_copy(update={"codex": str(fake)}))
    failed = _reviews(store)[0]
    legacy_type = _legacy_store_type(monkeypatch)
    assert store.enqueue("ready", "entry-amount-distribution", "independent")
    for stage in ("before_due", "after_due", "interrupted_retry"):
        if stage == "after_due":
            clock.advance(300)
        if stage == "interrupted_retry":
            candidate = store.review_candidate()
            assert candidate is not None
            context = runner._review_context(candidate, "interrupted", config)
            assert store.claim_review(
                candidate,
                "interrupted",
                tmp_path / "receipt",
                context,
                clock.now.isoformat(),
            )
        copied = tmp_path / stage / "runner.db"
        copied.parent.mkdir()
        with (
            sqlite3.connect(store.db_path) as source,
            sqlite3.connect(copied) as destination,
        ):
            source.backup(destination)
        old = legacy_type(copied)
        if stage == "interrupted_retry":
            assert old.recover_running_reviews(["interrupted"]) == ["interrupted"]
        assert old.review_candidate() is None
        ready = runner._select_task(old, "research", None)
        assert ready is not None and ready.id == "ready"
        assert _reviews(old)[0] == failed
        upgraded = journal.RunnerStore(copied)
        assert (upgraded.review_candidate() is not None) == (stage != "before_due")
        assert _reviews(upgraded)[0] == failed
        with sqlite3.connect(copied) as db:
            assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_additive_schema_preserves_actual_legacy_rows_and_repeated_initialization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    legacy_type = _legacy_store_type(monkeypatch)
    old = legacy_type(tmp_path / "legacy" / "runner.db")
    assert old.enqueue("legacy", "__engineering__", "fixture", task_kind="engineering")
    with sqlite3.connect(old.db_path) as db:
        db.execute(
            "INSERT INTO attempts(id,task_id,status,started_at) "
            "VALUES('implementation','legacy','waiting_external',"
            "'2026-01-01T00:00:00+00:00')"
        )
        db.execute(
            "INSERT INTO review_attempts(id,task_id,implementation_attempt_id,"
            "status,started_at,output_path,failure_code,context_json) "
            "VALUES('legacy-review','legacy','implementation','failed',"
            "'2026-01-01T00:00:00+00:00','preserved','codex_exit','{}')"
        )
        old_columns = [
            row[1] for row in db.execute("PRAGMA table_info(review_attempts)")
        ]
        previous = db.execute("SELECT * FROM review_attempts").fetchall()
    for _ in range(3):
        journal.RunnerStore(old.db_path)
        with sqlite3.connect(old.db_path) as db:
            assert (
                db.execute(
                    f"SELECT {','.join(old_columns)} FROM review_attempts"
                ).fetchall()
                == previous
            )
            assert db.execute(
                "SELECT retry_kind,retry_after,transient_failures FROM review_attempts"
            ).fetchall() == [(None, None, 0)]
            assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
