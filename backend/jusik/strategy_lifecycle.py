"""Offline strategy registry; no investment or execution authority is granted here."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Literal


class StrategyState(StrEnum):
    IDEA = "IDEA"
    RESEARCHING = "RESEARCHING"
    BACKTESTED = "BACKTESTED"
    ROBUSTNESS_TEST = "ROBUSTNESS_TEST"
    PAPER_READY = "PAPER_READY"
    PAPER_TRADING = "PAPER_TRADING"
    REAL_MONEY_CANDIDATE = "REAL_MONEY_CANDIDATE"
    HUMAN_APPROVED = "HUMAN_APPROVED"
    LIVE = "LIVE"
    PAUSED = "PAUSED"
    RETIRED = "RETIRED"


# Target design graph. A legal edge is not necessarily implemented or authorized.
FORWARD_STATES = (
    StrategyState.IDEA,
    StrategyState.RESEARCHING,
    StrategyState.BACKTESTED,
    StrategyState.ROBUSTNESS_TEST,
    StrategyState.PAPER_READY,
    StrategyState.PAPER_TRADING,
    StrategyState.REAL_MONEY_CANDIDATE,
    StrategyState.HUMAN_APPROVED,
    StrategyState.LIVE,
)
LEGAL_TRANSITIONS: dict[StrategyState, frozenset[StrategyState]] = {
    state: frozenset(
        ({FORWARD_STATES[index + 1]} if index + 1 < len(FORWARD_STATES) else set())
        | ({StrategyState.PAUSED} if state != StrategyState.IDEA else set())
        | {StrategyState.RETIRED}
    )
    for index, state in enumerate(FORWARD_STATES)
}
LEGAL_TRANSITIONS[StrategyState.PAUSED] = frozenset(
    {*FORWARD_STATES[1:], StrategyState.RETIRED}
)
LEGAL_TRANSITIONS[StrategyState.RETIRED] = frozenset()

# Only these edges have deterministic guards in this slice. Later edges need
# authoritative evidence adapters, independent review and execution services.
SUPPORTED_TRANSITIONS = frozenset(
    {
        (StrategyState.IDEA, StrategyState.RESEARCHING),
        (StrategyState.RESEARCHING, StrategyState.PAUSED),
        (StrategyState.PAUSED, StrategyState.RESEARCHING),
        (StrategyState.IDEA, StrategyState.RETIRED),
        (StrategyState.RESEARCHING, StrategyState.RETIRED),
        (StrategyState.PAUSED, StrategyState.RETIRED),
    }
)


class RevisionConflict(ValueError):
    """A caller tried to write an obsolete strategy revision."""


@dataclass(frozen=True)
class StrategyRecord:
    strategy_id: str
    version: str
    definition: str
    state: StrategyState
    revision: int
    hypothesis_version: str | None
    hypothesis: str | None
    economic_rationale: str | None
    preregistration_version: str | None
    preregistration_ref: str | None
    resume_state: StrategyState | None
    created_at: str
    updated_at: str
    engineering_status: Literal["NOT_EVALUATED"] = "NOT_EVALUATED"
    investment_status: Literal["NOT_EVALUATED"] = "NOT_EVALUATED"


@dataclass(frozen=True)
class StrategyEvent:
    revision: int
    from_state: StrategyState | None
    to_state: StrategyState
    reason: str
    occurred_at: str


_SCHEMA = """
CREATE TABLE IF NOT EXISTS lifecycle_strategies (
    strategy_id TEXT NOT NULL CHECK(length(trim(strategy_id)) > 0),
    version TEXT NOT NULL CHECK(length(trim(version)) > 0),
    definition TEXT NOT NULL CHECK(length(trim(definition)) > 0),
    state TEXT NOT NULL CHECK(state IN (
        'IDEA','RESEARCHING','BACKTESTED','ROBUSTNESS_TEST','PAPER_READY',
        'PAPER_TRADING','REAL_MONEY_CANDIDATE','HUMAN_APPROVED','LIVE',
        'PAUSED','RETIRED')),
    revision INTEGER NOT NULL CHECK(revision >= 0),
    hypothesis_version TEXT,
    hypothesis TEXT,
    economic_rationale TEXT,
    preregistration_version TEXT,
    preregistration_ref TEXT,
    resume_state TEXT CHECK(resume_state IS NULL OR resume_state IN (
        'RESEARCHING','BACKTESTED','ROBUSTNESS_TEST','PAPER_READY',
        'PAPER_TRADING','REAL_MONEY_CANDIDATE','HUMAN_APPROVED','LIVE')),
    reason TEXT NOT NULL CHECK(length(trim(reason)) > 0),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
        CHECK(created_at GLOB '????-??-??T??:??:??.???Z'),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
        CHECK(updated_at GLOB '????-??-??T??:??:??.???Z'),
    PRIMARY KEY(strategy_id, version)
);
CREATE TABLE IF NOT EXISTS lifecycle_events (
    strategy_id TEXT NOT NULL,
    version TEXT NOT NULL,
    revision INTEGER NOT NULL,
    from_state TEXT,
    to_state TEXT NOT NULL,
    reason TEXT NOT NULL,
    occurred_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
        CHECK(occurred_at GLOB '????-??-??T??:??:??.???Z'),
    PRIMARY KEY(strategy_id, version, revision),
    FOREIGN KEY(strategy_id, version)
        REFERENCES lifecycle_strategies(strategy_id, version)
);
CREATE TRIGGER IF NOT EXISTS lifecycle_insert_guard
BEFORE INSERT ON lifecycle_strategies BEGIN
    SELECT RAISE(ABORT, 'initial state must be IDEA at revision zero')
    WHERE NEW.state != 'IDEA' OR NEW.revision != 0
       OR NEW.resume_state IS NOT NULL
       OR NEW.hypothesis_version IS NOT NULL OR NEW.hypothesis IS NOT NULL
       OR NEW.economic_rationale IS NOT NULL
       OR NEW.preregistration_version IS NOT NULL
       OR NEW.preregistration_ref IS NOT NULL;
END;
CREATE TRIGGER IF NOT EXISTS lifecycle_update_guard
BEFORE UPDATE ON lifecycle_strategies BEGIN
    SELECT RAISE(ABORT, 'strategy identity and definition are immutable')
    WHERE NEW.strategy_id != OLD.strategy_id OR NEW.version != OLD.version
       OR NEW.definition != OLD.definition OR NEW.created_at != OLD.created_at;
    SELECT RAISE(ABORT, 'revision must increment with a state transition')
    WHERE NEW.revision != OLD.revision + 1 OR NEW.state = OLD.state;
    SELECT RAISE(ABORT, 'unsupported lifecycle transition')
    WHERE NOT (
        (OLD.state = 'IDEA' AND NEW.state = 'RESEARCHING') OR
        (OLD.state = 'RESEARCHING' AND NEW.state = 'PAUSED') OR
        (OLD.state = 'PAUSED' AND NEW.state = 'RESEARCHING'
            AND OLD.resume_state = 'RESEARCHING') OR
        (OLD.state IN ('IDEA','RESEARCHING','PAUSED')
            AND NEW.state = 'RETIRED')
    );
    SELECT RAISE(ABORT, 'research preregistration is required')
    WHERE NEW.state = 'RESEARCHING' AND (
        NEW.hypothesis_version IS NULL OR length(trim(NEW.hypothesis_version)) = 0 OR
        NEW.hypothesis IS NULL OR length(trim(NEW.hypothesis)) = 0 OR
        NEW.economic_rationale IS NULL OR length(trim(NEW.economic_rationale)) = 0 OR
        NEW.preregistration_version IS NULL OR
            length(trim(NEW.preregistration_version)) = 0 OR
        NEW.preregistration_ref IS NULL OR
            length(trim(NEW.preregistration_ref)) = 0
    );
    SELECT RAISE(ABORT, 'research declaration is immutable after start')
    WHERE NOT (OLD.state = 'IDEA' AND NEW.state = 'RESEARCHING') AND (
        NEW.hypothesis_version IS NOT OLD.hypothesis_version OR
        NEW.hypothesis IS NOT OLD.hypothesis OR
        NEW.economic_rationale IS NOT OLD.economic_rationale OR
        NEW.preregistration_version IS NOT OLD.preregistration_version OR
        NEW.preregistration_ref IS NOT OLD.preregistration_ref
    );
    SELECT RAISE(ABORT, 'invalid resume state')
    WHERE (NEW.state = 'PAUSED' AND NEW.resume_state IS NOT OLD.state)
       OR (NEW.state != 'PAUSED' AND NEW.resume_state IS NOT NULL);
END;
CREATE TRIGGER IF NOT EXISTS lifecycle_no_delete
BEFORE DELETE ON lifecycle_strategies BEGIN
    SELECT RAISE(ABORT, 'strategy history cannot be deleted');
END;
CREATE TRIGGER IF NOT EXISTS lifecycle_event_insert_guard
BEFORE INSERT ON lifecycle_events BEGIN
    SELECT RAISE(ABORT, 'event must match current strategy revision')
    WHERE NOT EXISTS (
        SELECT 1 FROM lifecycle_strategies s
        WHERE s.strategy_id = NEW.strategy_id AND s.version = NEW.version
          AND s.revision = NEW.revision AND s.state = NEW.to_state
          AND s.reason = NEW.reason
    ) OR EXISTS (
        SELECT 1 FROM lifecycle_events e
        WHERE e.strategy_id = NEW.strategy_id AND e.version = NEW.version
          AND e.revision = NEW.revision
    );
END;
CREATE TRIGGER IF NOT EXISTS lifecycle_event_no_update
BEFORE UPDATE ON lifecycle_events BEGIN
    SELECT RAISE(ABORT, 'event history is append only');
END;
CREATE TRIGGER IF NOT EXISTS lifecycle_event_no_delete
BEFORE DELETE ON lifecycle_events BEGIN
    SELECT RAISE(ABORT, 'event history is append only');
END;
CREATE TRIGGER IF NOT EXISTS lifecycle_register_event
AFTER INSERT ON lifecycle_strategies BEGIN
    INSERT INTO lifecycle_events
        (strategy_id,version,revision,from_state,to_state,reason)
    VALUES (NEW.strategy_id,NEW.version,NEW.revision,NULL,NEW.state,NEW.reason);
END;
CREATE TRIGGER IF NOT EXISTS lifecycle_transition_event
AFTER UPDATE ON lifecycle_strategies BEGIN
    INSERT INTO lifecycle_events
        (strategy_id,version,revision,from_state,to_state,reason)
    VALUES (NEW.strategy_id,NEW.version,NEW.revision,OLD.state,NEW.state,NEW.reason);
END;
"""


class StrategyLifecycleStore:
    """Private registry; triggers cannot stop same-user DDL or file edits."""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db:
            db.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA recursive_triggers=ON")
        return db

    def register(
        self, strategy_id: str, version: str, definition: str, *, reason: str
    ) -> StrategyRecord:
        with closing(self._connect()) as db, db:
            db.execute(
                "INSERT INTO lifecycle_strategies "
                "(strategy_id,version,definition,state,revision,reason) "
                "VALUES (?,?,?,'IDEA',0,?)",
                (strategy_id, version, definition, reason),
            )
            return self._get_required(db, strategy_id, version)

    def get(self, strategy_id: str, version: str) -> StrategyRecord | None:
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT * FROM lifecycle_strategies WHERE strategy_id=? AND version=?",
                (strategy_id, version),
            ).fetchone()
        return self._record(row) if row is not None else None

    def events(self, strategy_id: str, version: str) -> list[StrategyEvent]:
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT * FROM lifecycle_events WHERE strategy_id=? AND version=? "
                "ORDER BY revision",
                (strategy_id, version),
            ).fetchall()
        return [
            StrategyEvent(
                revision=int(row["revision"]),
                from_state=(
                    StrategyState(row["from_state"])
                    if row["from_state"] is not None
                    else None
                ),
                to_state=StrategyState(row["to_state"]),
                reason=str(row["reason"]),
                occurred_at=str(row["occurred_at"]),
            )
            for row in rows
        ]

    def transition(
        self,
        strategy_id: str,
        version: str,
        target: StrategyState,
        *,
        expected_revision: int,
        reason: str,
        hypothesis_version: str | None = None,
        hypothesis: str | None = None,
        economic_rationale: str | None = None,
        preregistration_version: str | None = None,
        preregistration_ref: str | None = None,
    ) -> StrategyRecord:
        if not reason.strip():
            raise ValueError("transition reason is required")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            current = self._get_required(db, strategy_id, version)
            if current.revision != expected_revision:
                raise RevisionConflict("strategy revision changed")
            if target not in LEGAL_TRANSITIONS[current.state]:
                raise ValueError("illegal lifecycle transition")
            if (current.state, target) not in SUPPORTED_TRANSITIONS:
                raise ValueError("lifecycle transition needs authoritative services")
            declaration = (
                hypothesis_version,
                hypothesis,
                economic_rationale,
                preregistration_version,
                preregistration_ref,
            )
            if (
                current.state == StrategyState.IDEA
                and target == StrategyState.RESEARCHING
            ):
                if any(value is None or not value.strip() for value in declaration):
                    raise ValueError("versioned research preregistration is required")
            elif any(value is not None for value in declaration):
                raise ValueError("research declaration is only accepted at start")
            resume_state = (
                current.state.value if target == StrategyState.PAUSED else None
            )
            cursor = db.execute(
                "UPDATE lifecycle_strategies SET state=?, revision=revision+1, "
                "hypothesis_version=COALESCE(?,hypothesis_version), "
                "hypothesis=COALESCE(?,hypothesis), "
                "economic_rationale=COALESCE(?,economic_rationale), "
                "preregistration_version=COALESCE(?,preregistration_version), "
                "preregistration_ref=COALESCE(?,preregistration_ref), "
                "resume_state=?, reason=?, "
                "updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') "
                "WHERE strategy_id=? AND version=? AND revision=?",
                (
                    target.value,
                    *declaration,
                    resume_state,
                    reason,
                    strategy_id,
                    version,
                    expected_revision,
                ),
            )
            if cursor.rowcount != 1:
                raise RevisionConflict("strategy revision changed")
            return self._get_required(db, strategy_id, version)

    @staticmethod
    def _record(row: sqlite3.Row) -> StrategyRecord:
        resume_state = row["resume_state"]
        return StrategyRecord(
            strategy_id=str(row["strategy_id"]),
            version=str(row["version"]),
            definition=str(row["definition"]),
            state=StrategyState(row["state"]),
            revision=int(row["revision"]),
            hypothesis_version=row["hypothesis_version"],
            hypothesis=row["hypothesis"],
            economic_rationale=row["economic_rationale"],
            preregistration_version=row["preregistration_version"],
            preregistration_ref=row["preregistration_ref"],
            resume_state=StrategyState(resume_state) if resume_state else None,
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    def _get_required(
        self, db: sqlite3.Connection, strategy_id: str, version: str
    ) -> StrategyRecord:
        row = db.execute(
            "SELECT * FROM lifecycle_strategies WHERE strategy_id=? AND version=?",
            (strategy_id, version),
        ).fetchone()
        if row is None:
            raise KeyError((strategy_id, version))
        return self._record(row)
