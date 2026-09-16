from __future__ import annotations

import re
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from jusik.development_runner import RunnerConfig, _bind_scope, init_config, run_once
from jusik.development_runner_roadmap import (
    ROADMAP_SCOPE,
    RoadmapError,
    eligible_areas,
    load_roadmap,
    validate_enqueue,
    validate_roadmap_completion,
)
from jusik.development_runner_store import RunnerStore

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


def test_runner_config_keeps_research_default(tmp_path: Path) -> None:
    config = RunnerConfig(repo=tmp_path)
    assert config.scope == "research"
