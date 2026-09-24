"""Lifecycle registry guards use only isolated SQLite files and synthetic text."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from jusik.strategy_lifecycle import (
    FORWARD_STATES,
    LEGAL_TRANSITIONS,
    RevisionConflict,
    StrategyLifecycleStore,
    StrategyState,
)


@pytest.fixture
def store(tmp_path: Path) -> StrategyLifecycleStore:
    return StrategyLifecycleStore(tmp_path / "lifecycle.sqlite3")


def _register(store: StrategyLifecycleStore) -> None:
    record = store.register(
        "sample", "v1", "immutable synthetic definition", reason="idea"
    )
    assert record.state == StrategyState.IDEA


def _start(store: StrategyLifecycleStore) -> None:
    store.transition(
        "sample",
        "v1",
        StrategyState.RESEARCHING,
        expected_revision=0,
        reason="preregister research",
        hypothesis_version="hypothesis-v1",
        hypothesis="synthetic hypothesis",
        economic_rationale="synthetic economic rationale",
        preregistration_version="protocol-v1",
        preregistration_ref="offline-fixture/protocol-v1",
    )


def _sql(store: StrategyLifecycleStore, query: str) -> None:
    with sqlite3.connect(store.path) as db:
        db.execute(query)


def test_registration_research_pause_resume_and_history(
    store: StrategyLifecycleStore,
) -> None:
    _register(store)
    _start(store)
    started = store.get("sample", "v1")
    assert started is not None
    assert started.revision == 1
    assert started.engineering_status == "NOT_EVALUATED"
    assert started.investment_status == "NOT_EVALUATED"
    assert started.preregistration_version == "protocol-v1"
    paused = store.transition(
        "sample", "v1", StrategyState.PAUSED, expected_revision=1, reason="pause"
    )
    assert paused.resume_state == StrategyState.RESEARCHING
    resumed = store.transition(
        "sample", "v1", StrategyState.RESEARCHING, expected_revision=2, reason="resume"
    )
    assert resumed.resume_state is None
    assert resumed.revision == 3
    events = store.events("sample", "v1")
    assert [(event.revision, event.from_state, event.to_state) for event in events] == [
        (0, None, StrategyState.IDEA),
        (1, StrategyState.IDEA, StrategyState.RESEARCHING),
        (2, StrategyState.RESEARCHING, StrategyState.PAUSED),
        (3, StrategyState.PAUSED, StrategyState.RESEARCHING),
    ]
    assert all(event.occurred_at.endswith("Z") for event in events)


def test_full_design_graph_is_distinct_from_supported_policy() -> None:
    assert len(FORWARD_STATES) == 9
    for previous, following in zip(
        FORWARD_STATES[:-1], FORWARD_STATES[1:], strict=True
    ):
        assert following in LEGAL_TRANSITIONS[previous]
    assert StrategyState.PAUSED in LEGAL_TRANSITIONS[StrategyState.LIVE]
    assert StrategyState.RETIRED in LEGAL_TRANSITIONS[StrategyState.PAUSED]
    assert not LEGAL_TRANSITIONS[StrategyState.RETIRED]


@pytest.mark.parametrize("target", FORWARD_STATES[2:])
def test_investment_stages_fail_closed_in_api_and_sql(
    store: StrategyLifecycleStore, target: StrategyState
) -> None:
    _register(store)
    _start(store)
    before = store.get("sample", "v1")
    history = store.events("sample", "v1")
    with pytest.raises(ValueError):
        store.transition(
            "sample", "v1", target, expected_revision=1, reason="fixture says true"
        )
    with pytest.raises(sqlite3.IntegrityError):
        _sql(
            store,
            "UPDATE lifecycle_strategies "
            f"SET state='{target.value}', revision=2, reason='fixture says true' "
            "WHERE strategy_id='sample' AND version='v1'",
        )
    assert store.get("sample", "v1") == before
    assert store.events("sample", "v1") == history


def test_bad_initial_state_and_direct_stage_skip_are_rejected(
    store: StrategyLifecycleStore,
) -> None:
    for state in ("RESEARCHING", "PAPER_READY", "HUMAN_APPROVED", "LIVE", "unknown"):
        with pytest.raises(sqlite3.IntegrityError):
            _sql(
                store,
                "INSERT INTO lifecycle_strategies "
                "(strategy_id,version,definition,state,revision,reason) "
                f"VALUES ('bad','{state}','definition','{state}',0,'fixture')",
            )
    _register(store)
    with pytest.raises(sqlite3.IntegrityError):
        _sql(
            store,
            "UPDATE lifecycle_strategies SET state='PAPER_READY', revision=1, "
            "reason='skip' WHERE strategy_id='sample' AND version='v1'",
        )
    assert store.get("sample", "v1") is not None
    assert len(store.events("sample", "v1")) == 1


def test_research_requires_versioned_declaration_even_for_direct_sql(
    store: StrategyLifecycleStore,
) -> None:
    _register(store)
    with pytest.raises(ValueError, match="preregistration"):
        store.transition(
            "sample",
            "v1",
            StrategyState.RESEARCHING,
            expected_revision=0,
            reason="start",
            hypothesis_version="v1",
            hypothesis="hypothesis",
            economic_rationale="reason",
            preregistration_version=" ",
            preregistration_ref="fixture",
        )
    with pytest.raises(sqlite3.IntegrityError):
        _sql(
            store,
            "UPDATE lifecycle_strategies SET state='RESEARCHING', revision=1, "
            "reason='start', hypothesis_version='v1', hypothesis='hypothesis', "
            "economic_rationale='reason', preregistration_version=' ', "
            "preregistration_ref='fixture' "
            "WHERE strategy_id='sample' AND version='v1'",
        )
    assert len(store.events("sample", "v1")) == 1


def test_revision_conflict_and_failed_transition_leave_no_event(
    store: StrategyLifecycleStore,
) -> None:
    _register(store)
    _start(store)
    before = store.get("sample", "v1")
    history = store.events("sample", "v1")
    with pytest.raises(RevisionConflict):
        store.transition(
            "sample",
            "v1",
            StrategyState.PAUSED,
            expected_revision=0,
            reason="obsolete writer",
        )
    with pytest.raises(sqlite3.IntegrityError):
        _sql(
            store,
            "UPDATE lifecycle_strategies SET state='PAUSED', revision=1, "
            "resume_state='RESEARCHING', reason='bad revision' "
            "WHERE strategy_id='sample' AND version='v1'",
        )
    assert store.get("sample", "v1") == before
    assert store.events("sample", "v1") == history


def test_two_writers_with_same_expected_revision_only_create_one_event(
    store: StrategyLifecycleStore,
) -> None:
    _register(store)

    def retire() -> str:
        try:
            store.transition(
                "sample",
                "v1",
                StrategyState.RETIRED,
                expected_revision=0,
                reason="discard",
            )
        except RevisionConflict:
            return "conflict"
        return "retired"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: retire(), range(2)))
    assert sorted(results) == ["conflict", "retired"]
    assert [event.revision for event in store.events("sample", "v1")] == [0, 1]


def test_pause_requires_safe_resume_and_retirement_is_terminal(
    store: StrategyLifecycleStore,
) -> None:
    _register(store)
    with pytest.raises(ValueError):
        store.transition(
            "sample",
            "v1",
            StrategyState.PAUSED,
            expected_revision=0,
            reason="cannot pause idea",
        )
    _start(store)
    with pytest.raises(sqlite3.IntegrityError):
        _sql(
            store,
            "UPDATE lifecycle_strategies SET state='PAUSED', revision=2, "
            "reason='bad pause' WHERE strategy_id='sample' AND version='v1'",
        )
    store.transition(
        "sample", "v1", StrategyState.PAUSED, expected_revision=1, reason="pause"
    )
    with pytest.raises(sqlite3.IntegrityError):
        _sql(
            store,
            "UPDATE lifecycle_strategies SET state='PAPER_READY', revision=3, "
            "resume_state=NULL, reason='skip' "
            "WHERE strategy_id='sample' AND version='v1'",
        )
    retired = store.transition(
        "sample",
        "v1",
        StrategyState.RETIRED,
        expected_revision=2,
        reason="discard synthetic idea",
    )
    assert retired.revision == 3
    with pytest.raises(ValueError):
        store.transition(
            "sample",
            "v1",
            StrategyState.RESEARCHING,
            expected_revision=3,
            reason="terminal",
        )
    with pytest.raises(sqlite3.IntegrityError):
        _sql(
            store,
            "UPDATE lifecycle_strategies SET state='RESEARCHING', revision=4, "
            "reason='terminal' WHERE strategy_id='sample' AND version='v1'",
        )
    assert len(store.events("sample", "v1")) == 4


def test_definition_identity_and_history_are_immutable(
    store: StrategyLifecycleStore,
) -> None:
    _register(store)
    with pytest.raises(sqlite3.IntegrityError):
        _sql(
            store,
            "UPDATE lifecycle_strategies SET definition='other', state='RETIRED', "
            "revision=1, reason='alter' WHERE strategy_id='sample' AND version='v1'",
        )
    with pytest.raises(sqlite3.IntegrityError):
        _sql(store, "UPDATE lifecycle_events SET reason='rewritten' WHERE revision=0")
    with pytest.raises(sqlite3.IntegrityError):
        _sql(store, "DELETE FROM lifecycle_events WHERE revision=0")
    with pytest.raises(sqlite3.IntegrityError):
        _sql(store, "DELETE FROM lifecycle_strategies WHERE strategy_id='sample'")
    with pytest.raises(sqlite3.IntegrityError):
        _sql(
            store,
            "INSERT OR REPLACE INTO lifecycle_events "
            "(strategy_id,version,revision,from_state,to_state,reason) "
            "VALUES ('sample','v1',0,NULL,'IDEA','idea')",
        )
    assert len(store.events("sample", "v1")) == 1


def test_synthetic_fixture_and_direct_status_edit_cannot_claim_validation(
    store: StrategyLifecycleStore,
) -> None:
    _register(store)
    _start(store)
    with pytest.raises(sqlite3.OperationalError, match="no such column"):
        _sql(
            store,
            "UPDATE lifecycle_strategies SET investment_status='INVESTMENT_VALIDATED' "
            "WHERE strategy_id='sample' AND version='v1'",
        )
    with pytest.raises(sqlite3.OperationalError, match="no such column"):
        _sql(
            store,
            "UPDATE lifecycle_strategies SET engineering_status='ENGINEERING_COMPLETE' "
            "WHERE strategy_id='sample' AND version='v1'",
        )
    record = store.get("sample", "v1")
    assert record is not None
    assert record.engineering_status == "NOT_EVALUATED"
    assert record.investment_status == "NOT_EVALUATED"
