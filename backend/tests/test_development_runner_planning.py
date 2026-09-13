from __future__ import annotations

import hashlib
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest

from jusik.development_runner import (
    RunnerConfig,
    _codex_command,
    _tracked_research_mandate,
)
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


def test_tracked_research_mandate_preserves_authoritative_fields() -> None:
    import json

    path = Path(__file__).parents[2].joinpath("docs/research-mandate.json")
    raw_content = path.read_text(encoding="utf-8")
    mandate = json.loads(raw_content)
    recorded_at = mandate.pop("recorded_at")
    parsed_recorded_at = datetime.fromisoformat(recorded_at)
    assert parsed_recorded_at.tzinfo == UTC
    assert mandate == {
        "capital_krw": 100000000,
        "maximum_drawdown_fraction": "0.20",
        "drawdown_reference": (
            "running peak of total portfolio marked-to-market NAV, including initial "
            "capital"
        ),
        "research_universe_expansion": [
            "existing instruments",
            "cash",
            "broad-market index ETFs",
            "short-duration bond ETFs",
        ],
        "interim_withdrawals": "none",
        "investment_horizon": "open_ended",
        "historical_lookback_years": 3,
        "leveraged_allocation_fraction": "0.20",
        "turnover_preference": (
            "Infrequent trading; compare net returns, drawdown, trade counts, and "
            "transaction/FX costs side by side before deciding priority. No implicit "
            "weights or adoption decision."
        ),
        "signal_detection": "real-time",
        "live_trading": "deferred",
        "frozen_paper_contract": "unchanged;10% drawdown",
        "user_answers": [
            "기존 종목에 현금·광범위 지수·단기채 ETF 등을 추가해 비교",
            "운용 중 평가액 최고점 대비 20% 하락",
            "중간 인출 없음",
            "현금 비중을 낮춰서 진행. 신규 ETF는 방해된다면 제외. 거래가 너무 잦지 "
            "않도록 거래 횟수도 최적화.",
            "투자기간은 정하지 않고 계속 운용하는 open-ended 방식으로 본다.",
            "우선순위는 정하지 않는다. 실제 순수익·낙폭·거래 횟수·거래/FX 비용을 "
            "나란히 "
            "확인한 뒤 결정한다.",
        ],
        "cash_preference": (
            "Reduce unnecessary idle cash and compare higher investment exposure "
            "within the drawdown and leverage constraints."
        ),
        "short_history_etf_policy": (
            "Exclude newly listed ETFs from primary research when insufficient "
            "history blocks a meaningful comparison."
        ),
    }
    assert _tracked_research_mandate(path.parents[1]) == raw_content


@pytest.mark.parametrize(
    "content",
    ["not json\n", '{"investment_horizon": null}\n'],
    ids=["malformed", "missing-required-fields"],
)
def test_invalid_tracked_research_mandate_fails_closed(
    tmp_path: Path, content: str
) -> None:
    path = tmp_path / "docs" / "research-mandate.json"
    path.parent.mkdir()
    path.write_text(content, encoding="utf-8")
    assert _tracked_research_mandate(tmp_path) is None
    path.unlink()
    path.symlink_to(tmp_path / "other.json")
    assert _tracked_research_mandate(tmp_path) is None


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


def test_planner_wait_is_idempotent_per_day_and_reconsiders_changed_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from jusik import development_runner

    repo = tmp_path / "repo"
    repo.mkdir()
    mandate_path = repo / "docs" / "research-mandate.json"
    mandate_path.parent.mkdir()
    mandate_path.write_text(
        Path(__file__)
        .parents[2]
        .joinpath("docs/research-mandate.json")
        .read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    store = RunnerStore(tmp_path / "state" / "runner.db", tmp_path / "history")
    store.enqueue("research", "portfolio-stress-robustness", "prompt")
    fake = tmp_path / "wait.py"
    captured_prompt = tmp_path / "captured-prompt.txt"
    fake.write_text(
        "#!/usr/bin/env python3\n"
        "import json, pathlib, sys\n"
        "prompt = sys.stdin.read()\n"
        f"pathlib.Path({str(captured_prompt)!r}).write_text(prompt, encoding='utf-8')\n"
        "fields = dict(line.split(': ', 1) for line in prompt.splitlines()\n"
        "               if ': ' in line)\n"
        "pathlib.Path(sys.argv[sys.argv.index('-o') + 1]).write_text(json.dumps({\n"
        "'task_id': fields['Task id'], 'attempt_id': fields['Attempt id'],\n"
        "'fingerprint': fields['Fingerprint'], 'status': 'waiting',\n"
        "'proposal': None, 'wait_reason': 'Need input; resume when available.'\n"
        "}), encoding='utf-8')\n",
        encoding="utf-8",
    )
    fake.chmod(0o700)
    config = RunnerConfig(
        repo=repo,
        codex=str(fake),
        state_dir=tmp_path / "state",
        history_dir=tmp_path / "history",
        history_db=tmp_path / "history.db",
        artifact_dir=tmp_path / "artifact",
        planning_enabled=True,
        daily_launches=24,
        cooldown_seconds=0,
    )

    # _planning_task owns the date boundary; freeze only this module's clock.
    class Clock:
        value = "2026-09-12"
        calls = 0

        @classmethod
        def now(cls, _tz: object) -> Any:
            from datetime import datetime

            cls.calls += 1
            return datetime.fromisoformat(f"{cls.value}T12:00:{cls.calls:02d}+00:00")

        @staticmethod
        def fromisoformat(value: str) -> Any:
            from datetime import datetime

            return datetime.fromisoformat(value)

    monkeypatch.setattr(development_runner, "datetime", Clock)
    # A real git repository is not needed for this queue-identity test.
    monkeypatch.setattr(
        development_runner,
        "_git",
        lambda *_args, **_kwargs: type("Result", (), {"stdout": "a" * 40})(),
    )
    monkeypatch.setattr(development_runner, "_git_common", lambda _repo: tmp_path)
    monkeypatch.setattr(development_runner, "_git_ready", lambda _repo: (True, ""))
    research = store.task("research")
    assert research is not None
    store.claim(research, "attempt-1", tmp_path / "out", tmp_path / "err")
    store.finish("attempt-1", "research", "failed")

    assert development_runner.run_once(config).status == "completed"
    prompt_text = captured_prompt.read_text(encoding="utf-8")
    assert "docs/research-mandate.json" in prompt_text
    assert '"historical_lookback_years": 3' in prompt_text
    assert '"investment_horizon": "open_ended"' in prompt_text
    assert "supersedes all older mandate text" in prompt_text
    assert "100m KRW" not in prompt_text
    assert development_runner.run_once(config).status == "idle"
    assert len([t for t in store.tasks() if t.area == PLANNING_AREA]) == 1

    Clock.value = "2026-09-13"
    assert development_runner.run_once(config).status == "completed"
    assert len([t for t in store.tasks() if t.area == PLANNING_AREA]) == 2

    # A non-planning attempt identity is part of the next fingerprint.
    research = store.task("research")
    assert research is not None
    assert store.retry(research.id)
    research = store.task(research.id)
    assert research is not None
    store.claim(research, "attempt-2", tmp_path / "out-2", tmp_path / "err-2")
    store.finish("attempt-2", research.id, "failed")
    assert development_runner.run_once(config).status == "completed"
    assert len([t for t in store.tasks() if t.area == PLANNING_AREA]) == 3

    # Main HEAD changes independently of planner-only records.
    monkeypatch.setattr(
        development_runner,
        "_git",
        lambda *_args, **_kwargs: type("Result", (), {"stdout": "b" * 40})(),
    )
    assert development_runner.run_once(config).status == "completed"
    assert len([t for t in store.tasks() if t.area == PLANNING_AREA]) == 4


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload, evidence, attempt: payload["proposal"].update(
            {"id": "planner-forbidden"}
        ),
        lambda payload, evidence, attempt: payload["proposal"].update(
            {"area": "not-allowed"}
        ),
        lambda payload, evidence, attempt: payload["proposal"]["evidence"].clear(),
        lambda payload, evidence, attempt: payload["proposal"]["evidence"][0].update(
            {"sha256": "0" * 64}
        ),
        lambda payload, evidence, attempt: payload["proposal"]["evidence"][0].update(
            {"path": str(evidence.parents[2] / "outside.json")}
        ),
        lambda payload, evidence, attempt: (
            (evidence.parent / "link.json").symlink_to(evidence),
            payload["proposal"]["evidence"][0].update(
                {"path": str(evidence.parent / "link.json")}
            ),
        )[-1],
        lambda payload, evidence, attempt: payload["proposal"]["evidence"][0].update(
            {"path": str(attempt / "self.json")}
        ),
    ],
    ids=[
        "reserved-id",
        "invalid-area",
        "empty-evidence",
        "bad-hash",
        "outside",
        "symlink",
        "own-attempt",
    ],
)
def test_planning_result_rejects_invalid_evidence_and_identity_fields(
    tmp_path: Path, mutate: Any
) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    config = _config(allowed)
    evidence = config.repo / "evidence.json"
    evidence.write_text("evidence\n", encoding="utf-8")
    outside = tmp_path / "outside.json"
    outside.write_bytes(evidence.read_bytes())
    assert config.repo.parent not in outside.parents
    attempt = tmp_path / "attempt"
    attempt.mkdir()
    digest = fingerprint([], "a" * 40, "2026-09-12")
    payload: dict[str, Any] = {
        "task_id": "planner-task",
        "attempt_id": "attempt",
        "fingerprint": digest,
        "status": "proposed",
        "wait_reason": None,
        "proposal": {
            "id": "next-research-v1",
            "area": "portfolio-stress-robustness",
            "prompt": (
                "Objective: o Scope: s Inputs: i Computation cap: c Tests: t "
                "Stop condition: x"
            ),
            "evidence": [
                {
                    "path": str(evidence),
                    "sha256": hashlib.sha256(evidence.read_bytes()).hexdigest(),
                }
            ],
        },
    }
    mutate(payload, evidence, attempt)
    with pytest.raises(ValueError):
        validate_planning_result(
            payload,
            "planner-task",
            "attempt",
            digest,
            config,
            attempt,
            {"portfolio-stress-robustness"},
            set(),
        )


def test_finish_planning_trigger_failure_rolls_back_and_retry_is_single_commit(
    tmp_path: Path,
) -> None:
    store = RunnerStore(tmp_path / "state" / "runner.db", tmp_path / "history")
    store.enqueue("planner-task", PLANNING_AREA, "internal")
    task = store.task("planner-task")
    assert task is not None
    store.claim(task, "attempt", tmp_path / "out", tmp_path / "err")
    digest = hashlib.sha256(b"[]").hexdigest()
    with sqlite3.connect(store.db_path) as db:
        db.execute(
            "CREATE TRIGGER fail_planning_history BEFORE INSERT ON history_outbox "
            "WHEN NEW.outcome LIKE 'planning_%' AND NEW.outcome != 'planning_started' "
            "BEGIN SELECT RAISE(ABORT, 'injected'); END"
        )
    with pytest.raises(sqlite3.IntegrityError, match="injected"):
        store.finish_planning(
            "attempt",
            "planner-task",
            "proposed",
            {"status": "proposed"},
            digest,
            [],
            proposal=("research-v1", "portfolio-stress-robustness", "prompt"),
        )
    assert store.task("planner-task").status == "running"  # type: ignore[union-attr]
    assert store.task("research-v1") is None
    assert [item[3] for item in store.outbox_pending()] == ["started"]
    with sqlite3.connect(store.db_path) as db:
        db.execute("DROP TRIGGER fail_planning_history")
    assert store.finish_planning(
        "attempt",
        "planner-task",
        "proposed",
        {"status": "proposed"},
        digest,
        [],
        proposal=("research-v1", "portfolio-stress-robustness", "prompt"),
    )
    assert store.task("research-v1") is not None
    assert store.task("planner-task").status == "completed"  # type: ignore[union-attr]
