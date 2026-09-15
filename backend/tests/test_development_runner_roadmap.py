from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from jusik.development_runner import RunnerConfig, _bind_scope, init_config
from jusik.development_runner_roadmap import (
    ROADMAP_SCOPE,
    RoadmapError,
    eligible_areas,
    load_roadmap,
    validate_enqueue,
    validate_roadmap_completion,
)
from jusik.development_runner_store import RunnerStore


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    docs = repo / "docs"
    docs.mkdir(parents=True)
    source = Path(__file__).parents[2] / "docs"
    (docs / "investment-development-roadmap.md").write_bytes(
        (source / "investment-development-roadmap.md").read_bytes()
    )
    (docs / "research-mandate.json").write_bytes(
        (source / "research-mandate.json").read_bytes()
    )
    return repo


def test_roadmap_areas_are_lowercase_and_gates_are_independent(tmp_path: Path) -> None:
    roadmap = load_roadmap(_repo(tmp_path))
    areas = eligible_areas(roadmap)

    assert "r1-01" in areas
    assert "r2-01" in areas
    assert "r3-01" in areas
    assert "r4-01" not in areas
    assert all(area == area.lower() for area in areas)


def test_roadmap_enqueue_quarantines_used_area_and_complete_area(
    tmp_path: Path,
) -> None:
    roadmap = load_roadmap(_repo(tmp_path))
    queued = SimpleNamespace(area="r1-01", status="failed")

    with pytest.raises(RoadmapError, match="quarantined"):
        validate_enqueue(roadmap, [queued], "roadmap-r1-01-v2", "R1-01")
    with pytest.raises(RoadmapError, match="complete"):
        validate_enqueue(roadmap, [], "roadmap-r0-01-v1", "r0-01")


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
