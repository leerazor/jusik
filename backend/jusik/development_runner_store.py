"""Durable private queue and attempt journal for the development runner."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from jusik.development_runner_contract import (
    AUTOMATIC_ENGINEERING_BACKLOG,
    ENGINEERING_SPEC_BY_ID,
    Blocker,
    EngineeringSpec,
    unknown_blocker,
)
from jusik.development_runner_discovery import (
    MAX_INFRA_FAILURES,
    MAX_PROPOSALS,
    DiscoveryProposal,
    ScopeReview,
    canonical_json,
    digest,
    proposal_digest,
    source_fingerprint,
    spec_from_proposal,
    validate_proposal,
    validate_scope_review,
)
from jusik.development_runner_planning_scope import (
    ROADMAP_TASK_SCOPE_GUARD,
    PendingRoadmapScope,
    RoadmapScopeReview,
)
from jusik.development_runner_planning_scope import (
    canonical_json as scope_json,
)
from jusik.development_runner_planning_scope import (
    digest as scope_digest,
)
from jusik.development_runner_planning_scope import (
    validate_scope_review as validate_roadmap_scope_review,
)
from jusik.development_runner_roadmap import (
    ROADMAP_PENDING_LIMIT,
    load_roadmap,
    roadmap_fingerprint,
    validate_enqueue,
)
from jusik.research_mandate_governance import validate_dispatch_gate


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def failed_output_digest_matches(
    evidence_json: str | None, sha256: str, *, allow_legacy: bool = False
) -> bool:
    """Legacy SQL NULL has no historical digest; new records must match exactly."""
    if evidence_json is None:
        return allow_legacy
    try:
        evidence = json.loads(evidence_json)
    except (TypeError, ValueError):
        return False
    return (
        isinstance(evidence, dict)
        and set(evidence) == {"failed_output_digest_version", "sha256"}
        and type(evidence["failed_output_digest_version"]) is int
        and evidence["failed_output_digest_version"] == 1
        and isinstance(evidence["sha256"], str)
        and re.fullmatch(r"[a-f0-9]{64}", evidence["sha256"]) is not None
        and evidence["sha256"] == sha256
    )


def _legacy_failed_output_allowed(db: sqlite3.Connection, attempt_rowid: int) -> bool:
    cutoff = db.execute(
        "SELECT value FROM runner_meta WHERE key='failed_output_digest_min_rowid'"
    ).fetchone()
    if cutoff is None:
        marker = db.execute(
            "SELECT 1 FROM attempts WHERE failure_code='completion_invalid' "
            "AND evidence_json IS NOT NULL LIMIT 1"
        ).fetchone()
        return marker is None
    try:
        first_new_rowid = int(cutoff["value"])
    except (TypeError, ValueError):
        return False
    return first_new_rowid > 0 and attempt_rowid < first_new_rowid


def failed_output_evidence_identity(evidence_json: str | None) -> str:
    return (
        "legacy-null"
        if evidence_json is None
        else hashlib.sha256(evidence_json.encode()).hexdigest()
    )


def recovery_evidence_matches(
    evidence_json: str | None, recovery: dict[str, str]
) -> bool:
    identity = recovery.get("source_evidence_identity")
    if identity is None:
        # Existing legacy candidates predate identity pins.
        return evidence_json is None
    return failed_output_evidence_identity(evidence_json) == identity


@dataclass(frozen=True)
class RunnerTask:
    id: str
    area: str
    prompt: str
    status: str
    attempt_count: int
    next_allowed_at: str | None
    last_attempt_id: str | None
    depends_on: str | None
    task_kind: str = "research"
    blocker: dict[str, Any] | None = None
    engineering_status: str | None = None
    investment_status: str | None = None

    @property
    def canonical_state(self) -> str:
        return {
            "queued": "READY",
            "running": "RUNNING",
            "scope_pending": "RUNNING",
            "blocked": "BLOCKED",
            "waiting_external": "WAITING_EXTERNAL",
            "waiting_human": "WAITING_HUMAN",
            "completed": "DONE",
            "failed": "FAILED",
            "interrupted": "FAILED",
            "retryable": "FAILED",
        }.get(self.status, "FAILED")


@dataclass(frozen=True)
class RunnerAttempt:
    id: str
    task_id: str
    status: str
    process_group_id: int | None
    output_path: str | None
    baseline_head: str | None = None


@dataclass(frozen=True)
class ReviewCandidate:
    task: RunnerTask
    implementation_attempt_id: str
    baseline_head: str
    completion: dict[str, Any]
    recovery: dict[str, str] | None = None


@dataclass(frozen=True)
class FailedCandidateSource:
    task: RunnerTask
    attempt_id: str
    output_path: str
    baseline_head: str
    output_evidence: str | None = None
    legacy_output_allowed: bool = False


@dataclass(frozen=True)
class ReviewAttempt:
    id: str
    task_id: str
    process_group_id: int | None
    process_id: int | None
    process_starttime: int | None


class RunnerStore:
    """SQLite state whose schema is private to one runner installation."""

    def __init__(self, db_path: Path, history_root: Path | None = None) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.chmod(0o700)
        self.history_root = history_root or self.db_path.parent / "history"
        self.history_root.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS runner_meta (
                    key TEXT PRIMARY KEY, value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY, area TEXT NOT NULL, prompt TEXT NOT NULL,
                    status TEXT NOT NULL, attempt_count INTEGER NOT NULL DEFAULT 0,
                    next_allowed_at TEXT, last_attempt_id TEXT,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    previous_attempt_id TEXT, depends_on TEXT
                );
                CREATE TABLE IF NOT EXISTS attempts (
                    id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(id),
                    status TEXT NOT NULL, started_at TEXT NOT NULL,
                    ended_at TEXT, process_group_id INTEGER,
                    output_path TEXT, stderr_path TEXT, evidence_json TEXT,
                    failure_code TEXT, baseline_head TEXT
                );
                CREATE TABLE IF NOT EXISTS history_outbox (
                    id TEXT PRIMARY KEY, task_id TEXT NOT NULL,
                    attempt_id TEXT NOT NULL, outcome TEXT NOT NULL,
                    delivered_at TEXT
                );
                CREATE TABLE IF NOT EXISTS launch_log (
                    launched_at TEXT PRIMARY KEY
                );
                CREATE TABLE IF NOT EXISTS review_attempts (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL REFERENCES tasks(id),
                    implementation_attempt_id TEXT NOT NULL REFERENCES attempts(id),
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    process_group_id INTEGER,
                    process_id INTEGER,
                    process_starttime INTEGER,
                    output_path TEXT NOT NULL,
                    failure_code TEXT,
                    receipt_json TEXT,
                    context_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS discovery_cycles (
                    fingerprint TEXT PRIMARY KEY,
                    stage TEXT NOT NULL,
                    baseline_head TEXT NOT NULL,
                    mandate_digest TEXT NOT NULL,
                    task_snapshot_json TEXT NOT NULL,
                    proposal_count INTEGER NOT NULL DEFAULT 0,
                    infra_failures INTEGER NOT NULL DEFAULT 0,
                    transient_failures INTEGER NOT NULL DEFAULT 0,
                    retry_after TEXT,
                    retry_kind TEXT CHECK(retry_kind IN
                        ('capacity','rate_limit','network','server','auth','timeout')),
                    active_proposal_digest TEXT,
                    active_attempt_id TEXT,
                    reason TEXT NOT NULL,
                    next_condition TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS discovery_attempts (
                    id TEXT PRIMARY KEY,
                    fingerprint TEXT NOT NULL REFERENCES discovery_cycles(fingerprint),
                    stage TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    baseline_head TEXT NOT NULL,
                    process_group_id INTEGER,
                    process_id INTEGER,
                    process_starttime INTEGER,
                    output_path TEXT NOT NULL,
                    response_sha256 TEXT,
                    reason TEXT
                );
                CREATE TABLE IF NOT EXISTS discovery_proposals (
                    fingerprint TEXT NOT NULL REFERENCES discovery_cycles(fingerprint),
                    proposal_digest TEXT NOT NULL,
                    planner_attempt_id TEXT NOT NULL UNIQUE,
                    proposal_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    feedback TEXT,
                    PRIMARY KEY(fingerprint,proposal_digest)
                );
                CREATE TABLE IF NOT EXISTS approved_engineering_specs (
                    task_id TEXT PRIMARY KEY REFERENCES tasks(id),
                    spec_json TEXT NOT NULL,
                    spec_sha256 TEXT NOT NULL,
                    proposal_digest TEXT NOT NULL UNIQUE,
                    fingerprint TEXT NOT NULL,
                    scope_attempt_id TEXT NOT NULL UNIQUE,
                    scope_review_json TEXT NOT NULL,
                    approved_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS roadmap_planning_scopes (
                    planner_task_id TEXT PRIMARY KEY REFERENCES tasks(id),
                    planner_attempt_id TEXT NOT NULL UNIQUE REFERENCES attempts(id),
                    fingerprint TEXT NOT NULL UNIQUE,
                    pending_json TEXT NOT NULL,
                    pending_sha256 TEXT NOT NULL,
                    status TEXT NOT NULL,
                    active_review_id TEXT,
                    receipt_json TEXT,
                    reason TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS roadmap_scope_attempts (
                    id TEXT PRIMARY KEY,
                    planner_task_id TEXT NOT NULL
                        REFERENCES roadmap_planning_scopes(planner_task_id),
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    process_group_id INTEGER,
                    process_id INTEGER,
                    process_starttime INTEGER,
                    output_path TEXT NOT NULL,
                    response_sha256 TEXT,
                    reason TEXT
                );
                """
            )
            columns = {
                str(row["name"])
                for row in db.execute("PRAGMA table_info(tasks)").fetchall()
            }
            if "depends_on" not in columns:
                db.execute("ALTER TABLE tasks ADD COLUMN depends_on TEXT")
            if "task_kind" not in columns:
                db.execute(
                    "ALTER TABLE tasks ADD COLUMN task_kind TEXT NOT NULL "
                    "DEFAULT 'research'"
                )
            if "blocker_json" not in columns:
                db.execute("ALTER TABLE tasks ADD COLUMN blocker_json TEXT")
            if "engineering_status" not in columns:
                db.execute("ALTER TABLE tasks ADD COLUMN engineering_status TEXT")
            if "investment_status" not in columns:
                db.execute("ALTER TABLE tasks ADD COLUMN investment_status TEXT")
            attempt_columns = {
                str(row["name"])
                for row in db.execute("PRAGMA table_info(attempts)").fetchall()
            }
            if "baseline_head" not in attempt_columns:
                db.execute("ALTER TABLE attempts ADD COLUMN baseline_head TEXT")
            review_columns = {
                str(row["name"])
                for row in db.execute("PRAGMA table_info(review_attempts)").fetchall()
            }
            if "process_id" not in review_columns:
                db.execute("ALTER TABLE review_attempts ADD COLUMN process_id INTEGER")
            if "process_starttime" not in review_columns:
                db.execute(
                    "ALTER TABLE review_attempts ADD COLUMN process_starttime INTEGER"
                )
            cycle_columns = {
                str(row["name"])
                for row in db.execute("PRAGMA table_info(discovery_cycles)").fetchall()
            }
            if "transient_failures" not in cycle_columns:
                db.execute(
                    "ALTER TABLE discovery_cycles ADD COLUMN transient_failures "
                    "INTEGER NOT NULL DEFAULT 0"
                )
            if "retry_after" not in cycle_columns:
                db.execute("ALTER TABLE discovery_cycles ADD COLUMN retry_after TEXT")
            if "retry_kind" not in cycle_columns:
                db.execute(
                    "ALTER TABLE discovery_cycles ADD COLUMN retry_kind TEXT "
                    "CHECK(retry_kind IN ('capacity','rate_limit','network',"
                    "'server','auth','timeout'))"
                )
            legacy_blocker = unknown_blocker("legacy_unknown").model_dump(mode="json")
            db.execute(
                "UPDATE tasks SET blocker_json=? WHERE blocker_json IS NULL "
                "AND status IN ('blocked','waiting_external','waiting_human')",
                (json.dumps(legacy_blocker, sort_keys=True),),
            )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.db_path, timeout=2, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=2000")
        return db

    def set_meta(self, key: str, value: str) -> None:
        with self._connect() as db:
            db.execute(
                "INSERT INTO runner_meta(key,value) VALUES(?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )

    def get_meta(self, key: str) -> str | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT value FROM runner_meta WHERE key=?", (key,)
            ).fetchone()
        return None if row is None else str(row["value"])

    def enqueue(
        self,
        task_id: str,
        area: str,
        prompt: str,
        depends_on: str | None = None,
        task_kind: str = "research",
    ) -> bool:
        now = utc_now()
        with self._connect() as db:
            cur = db.execute(
                "INSERT OR IGNORE INTO tasks "
                "(id,area,prompt,status,created_at,updated_at,task_kind) "
                "VALUES(?,?,?,'queued',?,?,?)",
                (task_id, area, prompt, now, now, task_kind),
            )
            if cur.rowcount == 1 and depends_on is not None:
                db.execute(
                    "UPDATE tasks SET depends_on=? WHERE id=?", (depends_on, task_id)
                )
            if cur.rowcount == 1:
                db.execute("DELETE FROM runner_meta WHERE key='idle_status'")
        return cur.rowcount == 1

    def enqueue_next_engineering_spec(self) -> tuple[EngineeringSpec | None, str]:
        """Create one fixed task or record the idle decision atomically."""
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            paused = db.execute(
                "SELECT value FROM runner_meta WHERE key='paused'"
            ).fetchone()
            if paused is not None and paused["value"] == "1":
                db.rollback()
                return None, "paused"
            idle_reason = "fixed_engineering_backlog_exhausted"
            for spec in AUTOMATIC_ENGINEERING_BACKLOG:
                existing = db.execute(
                    "SELECT 1 FROM tasks WHERE id=?", (spec.id,)
                ).fetchone()
                if existing is not None:
                    continue
                pending = db.execute(
                    "SELECT COUNT(*) FROM tasks WHERE area != '__planning__' "
                    "AND status IN ('queued','running')"
                ).fetchone()
                if int(pending[0]) >= ROADMAP_PENDING_LIMIT:
                    idle_reason = "engineering_queue_full"
                    break
                now = utc_now()
                db.execute(
                    "INSERT INTO tasks "
                    "(id,area,prompt,status,created_at,updated_at,task_kind) "
                    "VALUES(?,?,?,'queued',?,?,'engineering')",
                    (spec.id, spec.area, spec.prompt, now, now),
                )
                db.execute("DELETE FROM runner_meta WHERE key='idle_status'")
                db.commit()
                return spec, "enqueued"
            next_check_at = datetime.now(UTC).replace(
                minute=0, second=0, microsecond=0
            ) + timedelta(hours=1)
            db.execute(
                "INSERT INTO runner_meta(key,value) VALUES('idle_status',?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (
                    json.dumps(
                        {
                            "reason": idle_reason,
                            "next_check_at": next_check_at.isoformat(),
                        },
                        sort_keys=True,
                    ),
                ),
            )
            db.commit()
        return None, idle_reason

    @staticmethod
    def _discovery_snapshot(db: sqlite3.Connection) -> list[list[str | None]]:
        rows = db.execute(
            "SELECT id,status,last_attempt_id FROM tasks WHERE area!='__planning__' "
            "ORDER BY id"
        ).fetchall()
        return [
            [str(row["id"]), str(row["status"]), row["last_attempt_id"]] for row in rows
        ]

    def discovery_snapshot(self) -> list[tuple[str, str, str | None]]:
        with self._connect() as db:
            snapshot = self._discovery_snapshot(db)
        return [(str(row[0]), str(row[1]), row[2]) for row in snapshot]

    def discovery_cycle(self, fingerprint: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM discovery_cycles WHERE fingerprint=?", (fingerprint,)
            ).fetchone()
        return dict(row) if row is not None else None

    def discovery_status(self) -> dict[str, str | int | None] | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT stage,reason,next_condition,proposal_count,updated_at,"
                "transient_failures,retry_after,retry_kind "
                "FROM discovery_cycles ORDER BY updated_at DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return None
        status: dict[str, str | int | None] = dict(row)
        if status["stage"] == "terminal":
            status["next_condition"] = "source, test, mandate, or task state changes"
        return status

    def discovery_retry_pending(self, fingerprint: str) -> bool:
        with self._connect() as db:
            row = db.execute(
                "SELECT retry_after FROM discovery_cycles WHERE fingerprint=?",
                (fingerprint,),
            ).fetchone()
        if row is None or row["retry_after"] is None:
            return False
        return self._retry_not_due(row["retry_after"], utc_now())

    def terminalize_discovery_cycle(self, fingerprint: str, reason: str) -> bool:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            changed = db.execute(
                "UPDATE discovery_cycles SET stage='terminal',reason=?,"
                "retry_after=NULL,retry_kind=NULL,next_condition=?,updated_at=? "
                "WHERE fingerprint=? "
                "AND stage!='terminal' AND active_attempt_id IS NULL",
                (
                    reason,
                    "source, test, mandate, or task state changes",
                    utc_now(),
                    fingerprint,
                ),
            ).rowcount
            db.commit()
        return changed == 1

    def discovery_feedback(self, fingerprint: str) -> list[str]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT feedback FROM discovery_proposals WHERE fingerprint=? "
                "AND status='rejected' ORDER BY rowid",
                (fingerprint,),
            ).fetchall()
        return [str(row["feedback"]) for row in rows if row["feedback"]]

    def discovery_active_proposal(
        self, fingerprint: str
    ) -> tuple[DiscoveryProposal, str] | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT p.proposal_json,p.planner_attempt_id,p.proposal_digest "
                "FROM discovery_cycles c JOIN discovery_proposals p "
                "ON p.fingerprint=c.fingerprint "
                "AND p.proposal_digest=c.active_proposal_digest "
                "WHERE c.fingerprint=? AND c.stage='scope' AND p.status='pending'",
                (fingerprint,),
            ).fetchone()
        if row is None:
            return None
        proposal = DiscoveryProposal.model_validate_json(str(row["proposal_json"]))
        if proposal_digest(proposal) != row["proposal_digest"]:
            raise ValueError("stored discovery proposal changed")
        return proposal, str(row["planner_attempt_id"])

    def start_discovery_attempt(
        self,
        fingerprint: str,
        baseline_head: str,
        mandate_digest: str,
        snapshot: list[tuple[str, str, str | None]],
        attempt_id: str,
        stage: str,
        output_path: Path,
        launched_at: str,
    ) -> bool:
        if stage not in {"discover", "scope"}:
            raise ValueError("invalid discovery stage")
        now = utc_now()
        expected = canonical_json(snapshot)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            paused = db.execute(
                "SELECT value FROM runner_meta WHERE key='paused'"
            ).fetchone()
            current = canonical_json(self._discovery_snapshot(db))
            pending = db.execute(
                "SELECT COUNT(*) FROM tasks WHERE area!='__planning__' "
                "AND status IN ('queued','running')"
            ).fetchone()
            if (
                (paused is not None and paused["value"] == "1")
                or current != expected
                or int(pending[0]) >= ROADMAP_PENDING_LIMIT
            ):
                db.rollback()
                return False
            row = db.execute(
                "SELECT * FROM discovery_cycles WHERE fingerprint=?", (fingerprint,)
            ).fetchone()
            if row is None:
                if stage != "discover":
                    db.rollback()
                    return False
                db.execute(
                    "INSERT INTO discovery_cycles "
                    "(fingerprint,stage,baseline_head,mandate_digest,task_snapshot_json,"
                    "reason,next_condition,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                    (
                        fingerprint,
                        stage,
                        baseline_head,
                        mandate_digest,
                        expected,
                        "started",
                        "discovery result",
                        now,
                    ),
                )
            elif (
                row["stage"] != stage
                or row["baseline_head"] != baseline_head
                or row["mandate_digest"] != mandate_digest
                or row["task_snapshot_json"] != expected
                or row["active_attempt_id"] is not None
                or int(row["infra_failures"]) >= MAX_INFRA_FAILURES
                or self._retry_not_due(row["retry_after"], now)
            ):
                db.rollback()
                return False
            db.execute(
                "INSERT INTO discovery_attempts "
                "(id,fingerprint,stage,status,started_at,baseline_head,output_path) "
                "VALUES(?,?,?,'running',?,?,?)",
                (attempt_id, fingerprint, stage, now, baseline_head, str(output_path)),
            )
            db.execute(
                "UPDATE discovery_cycles SET active_attempt_id=?,reason=?,"
                "retry_after=NULL,retry_kind=NULL,next_condition=?,updated_at=? "
                "WHERE fingerprint=?",
                (
                    attempt_id,
                    stage + "_running",
                    "current attempt completes",
                    now,
                    fingerprint,
                ),
            )
            db.execute("INSERT INTO launch_log(launched_at) VALUES(?)", (launched_at,))
            db.execute(
                "INSERT INTO runner_meta(key,value) VALUES('last_launch_at',?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (launched_at,),
            )
            db.commit()
        return True

    @staticmethod
    def _retry_not_due(deadline_value: object, now_value: str) -> bool:
        if deadline_value is None:
            return False
        try:
            deadline = datetime.fromisoformat(str(deadline_value))
            now = datetime.fromisoformat(now_value)
            return deadline.utcoffset() != timedelta(0) or now < deadline
        except ValueError:
            return True

    def set_discovery_process_identity(
        self, attempt_id: str, group_id: int, process_id: int, starttime: int
    ) -> None:
        with self._connect() as db:
            db.execute(
                "UPDATE discovery_attempts SET process_group_id=?,process_id=?,"
                "process_starttime=? WHERE id=? AND status='running'",
                (group_id, process_id, starttime, attempt_id),
            )

    def running_discovery_attempts(self) -> list[ReviewAttempt]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT id,process_group_id,process_id,process_starttime "
                "FROM discovery_attempts WHERE status='running'"
            ).fetchall()
        return [
            ReviewAttempt(
                str(row["id"]),
                "__discovery__",
                row["process_group_id"],
                row["process_id"],
                row["process_starttime"],
            )
            for row in rows
        ]

    def finish_discovery_attempt(
        self,
        fingerprint: str,
        attempt_id: str,
        *,
        outcome: str,
        reason: str,
        output_sha256: str | None = None,
        proposal: DiscoveryProposal | None = None,
        no_work_condition: str | None = None,
        transient_kind: str | None = None,
    ) -> str:
        if transient_kind is not None and transient_kind not in {
            "capacity",
            "rate_limit",
            "network",
            "server",
            "auth",
            "timeout",
        }:
            raise ValueError("invalid discovery retry kind")
        if (outcome == "transient") != (transient_kind is not None):
            raise ValueError("transient outcome needs retry kind")
        now = utc_now()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            cycle = db.execute(
                "SELECT * FROM discovery_cycles WHERE fingerprint=?", (fingerprint,)
            ).fetchone()
            attempt = db.execute(
                "SELECT * FROM discovery_attempts WHERE id=? AND fingerprint=?",
                (attempt_id, fingerprint),
            ).fetchone()
            if (
                cycle is None
                or attempt is None
                or attempt["status"] != "running"
                or cycle["active_attempt_id"] != attempt_id
                or cycle["stage"] != attempt["stage"]
            ):
                db.rollback()
                return "stale"
            stage = str(cycle["stage"])
            count = int(cycle["proposal_count"])
            failures = int(cycle["infra_failures"])
            transient_failures = int(cycle["transient_failures"])
            retry_after: str | None = None
            retry_kind: str | None = None
            active_digest = cycle["active_proposal_digest"]
            if outcome == "proposal":
                if stage != "discover" or proposal is None or count >= MAX_PROPOSALS:
                    db.rollback()
                    return "stale"
                identity = proposal_digest(proposal)
                existing = db.execute(
                    "SELECT 1 FROM discovery_proposals WHERE fingerprint=? "
                    "AND proposal_digest=?",
                    (fingerprint, identity),
                ).fetchone()
                if existing is not None:
                    outcome = "failed"
                    reason = "duplicate_proposal"
                else:
                    db.execute(
                        "INSERT INTO discovery_proposals "
                        "(fingerprint,proposal_digest,planner_attempt_id,"
                        "proposal_json,status) "
                        "VALUES(?,?,?,?,'pending')",
                        (
                            fingerprint,
                            identity,
                            attempt_id,
                            canonical_json(proposal.model_dump(mode="json")),
                        ),
                    )
                    count += 1
                    active_digest = identity
                    stage = "scope"
                    reason = "proposal_pending_scope"
            if outcome == "no_work":
                stage = "terminal"
                reason = "no_work"
            elif outcome == "stale":
                stage = "terminal"
            elif outcome == "interrupted":
                reason = "paused"
            elif outcome == "rejected":
                if stage != "scope" or active_digest is None:
                    db.rollback()
                    return "stale"
                db.execute(
                    "UPDATE discovery_proposals SET status='rejected',feedback=? "
                    "WHERE fingerprint=? AND proposal_digest=? AND status='pending'",
                    (reason, fingerprint, active_digest),
                )
                active_digest = None
                stage = "terminal" if count >= MAX_PROPOSALS else "discover"
                reason = (
                    "proposal_cap_reached" if stage == "terminal" else "scope_rejected"
                )
            elif outcome == "failed":
                failures += 1
                if failures >= MAX_INFRA_FAILURES:
                    stage = "terminal"
                    reason = "discovery_infrastructure_exhausted"
            elif outcome == "transient" and transient_kind is not None:
                transient_failures += 1
                seconds = (
                    21_600
                    if transient_kind == "auth"
                    else (300, 900, 3_600)[min(transient_failures - 1, 2)]
                )
                retry_after = (
                    datetime.fromisoformat(now) + timedelta(seconds=seconds)
                ).isoformat()
                retry_kind = transient_kind
                reason = "discovery_transient_" + transient_kind
            if outcome in {"proposal", "no_work", "rejected"}:
                transient_failures = 0
            next_condition = (
                no_work_condition
                if outcome == "no_work" and no_work_condition
                else "source, test, mandate, or non-discovery task state changes"
                if stage == "terminal"
                else "runner resumed"
                if outcome == "interrupted"
                else f"retry after {retry_after}"
                if outcome == "transient"
                else "next bounded discovery cycle"
            )
            db.execute(
                "UPDATE discovery_attempts SET status=?,ended_at=?,response_sha256=?,"
                "reason=? WHERE id=?",
                (outcome, now, output_sha256, reason, attempt_id),
            )
            db.execute(
                "UPDATE discovery_cycles SET stage=?,proposal_count=?,infra_failures=?,"
                "transient_failures=?,retry_after=?,retry_kind=?,"
                "active_proposal_digest=?,active_attempt_id=NULL,reason=?,"
                "next_condition=?,updated_at=? WHERE fingerprint=?",
                (
                    stage,
                    count,
                    failures,
                    transient_failures,
                    retry_after,
                    retry_kind,
                    active_digest,
                    reason,
                    next_condition,
                    now,
                    fingerprint,
                ),
            )
            db.commit()
        return stage

    def quarantine_discovery_attempt(self, attempt_id: str, reason: str) -> None:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT fingerprint FROM discovery_attempts WHERE id=? "
                "AND status='running'",
                (attempt_id,),
            ).fetchone()
            if row is not None:
                now = utc_now()
                db.execute(
                    "UPDATE discovery_attempts SET status='quarantined',ended_at=?,"
                    "reason=? WHERE id=?",
                    (now, reason, attempt_id),
                )
                if reason == "orphan_recovered":
                    db.execute(
                        "UPDATE discovery_cycles SET active_attempt_id=NULL,"
                        "infra_failures=infra_failures+1,"
                        "stage=CASE WHEN infra_failures+1>=? THEN 'terminal' "
                        "ELSE stage END,reason=?,next_condition=?,updated_at=? "
                        "WHERE fingerprint=? AND active_attempt_id=?",
                        (
                            MAX_INFRA_FAILURES,
                            reason,
                            "next bounded discovery cycle",
                            now,
                            row["fingerprint"],
                            attempt_id,
                        ),
                    )
                else:
                    db.execute(
                        "UPDATE discovery_cycles SET stage='terminal',"
                        "active_attempt_id=NULL,reason=?,next_condition=?,"
                        "updated_at=? WHERE fingerprint=? AND active_attempt_id=?",
                        (
                            reason,
                            "operator verifies orphan before changed input "
                            "resumes discovery",
                            now,
                            row["fingerprint"],
                            attempt_id,
                        ),
                    )
            db.commit()

    def approve_discovery_spec(
        self,
        fingerprint: str,
        attempt_id: str,
        planner_attempt_id: str,
        proposal: DiscoveryProposal,
        review: ScopeReview,
        baseline_head: str,
        mandate_digest: str,
        snapshot: list[tuple[str, str, str | None]],
        output_sha256: str,
        repo: Path,
    ) -> EngineeringSpec | None:
        if review.verdict != "PASS":
            raise ValueError("scope PASS required")
        validate_scope_review(
            review, proposal, planner_attempt_id, baseline_head, fingerprint
        )
        spec = spec_from_proposal(proposal)
        spec_data = {
            "id": spec.id,
            "area": spec.area,
            "prompt": spec.prompt,
            "owned_paths": sorted(spec.owned_paths),
        }
        spec_json = canonical_json(spec_data)
        now = utc_now()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            cycle = db.execute(
                "SELECT * FROM discovery_cycles WHERE fingerprint=?", (fingerprint,)
            ).fetchone()
            attempt = db.execute(
                "SELECT status,stage FROM discovery_attempts WHERE id=? "
                "AND fingerprint=?",
                (attempt_id, fingerprint),
            ).fetchone()
            pending = db.execute(
                "SELECT COUNT(*) FROM tasks WHERE area!='__planning__' "
                "AND status IN ('queued','running')"
            ).fetchone()
            paused = db.execute(
                "SELECT value FROM runner_meta WHERE key='paused'"
            ).fetchone()
            active = db.execute(
                "SELECT proposal_json,planner_attempt_id,status FROM "
                "discovery_proposals WHERE fingerprint=? AND proposal_digest=?",
                (fingerprint, proposal_digest(proposal)),
            ).fetchone()
            current_head = subprocess.run(
                ["git", "rev-parse", "main"],
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            ).stdout.strip()
            current_fingerprint = source_fingerprint(repo, mandate_digest, snapshot)
            validate_proposal(repo, proposal)
            if (
                cycle is None
                or attempt is None
                or attempt["status"] != "running"
                or attempt["stage"] != "scope"
                or cycle["stage"] != "scope"
                or cycle["active_attempt_id"] != attempt_id
                or cycle["active_proposal_digest"] != proposal_digest(proposal)
                or cycle["baseline_head"] != baseline_head
                or cycle["mandate_digest"] != mandate_digest
                or current_head != baseline_head
                or current_fingerprint != fingerprint
                or cycle["task_snapshot_json"] != canonical_json(snapshot)
                or canonical_json(self._discovery_snapshot(db))
                != canonical_json(snapshot)
                or int(pending[0]) >= ROADMAP_PENDING_LIMIT
                or (paused is not None and paused["value"] == "1")
                or active is None
                or active["status"] != "pending"
                or active["planner_attempt_id"] != planner_attempt_id
                or active["proposal_json"]
                != canonical_json(proposal.model_dump(mode="json"))
                or db.execute("SELECT 1 FROM tasks WHERE id=?", (spec.id,)).fetchone()
                is not None
            ):
                db.rollback()
                return None
            db.execute(
                "INSERT INTO tasks(id,area,prompt,status,created_at,"
                "updated_at,task_kind) "
                "VALUES(?,?,?,'queued',?,?,'engineering')",
                (spec.id, spec.area, spec.prompt, now, now),
            )
            db.execute(
                "INSERT INTO approved_engineering_specs "
                "(task_id,spec_json,spec_sha256,proposal_digest,"
                "fingerprint,scope_attempt_id,scope_review_json,approved_at) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (
                    spec.id,
                    spec_json,
                    digest(spec_data),
                    proposal_digest(proposal),
                    fingerprint,
                    attempt_id,
                    canonical_json(review.model_dump(mode="json")),
                    now,
                ),
            )
            db.execute(
                "UPDATE discovery_proposals SET status='approved' WHERE "
                "fingerprint=? AND proposal_digest=?",
                (fingerprint, proposal_digest(proposal)),
            )
            db.execute(
                "UPDATE discovery_attempts SET status='approved',ended_at=?,"
                "response_sha256=?,reason='scope_pass' WHERE id=?",
                (now, output_sha256, attempt_id),
            )
            db.execute(
                "UPDATE discovery_cycles SET stage='terminal',active_attempt_id=NULL,"
                "transient_failures=0,retry_after=NULL,retry_kind=NULL,"
                "reason='approved',next_condition='new source or task state',"
                "updated_at=? WHERE fingerprint=?",
                (now, fingerprint),
            )
            db.execute("DELETE FROM runner_meta WHERE key='idle_status'")
            db.commit()
        return spec

    def engineering_spec(self, task_id: str) -> EngineeringSpec | None:
        static = ENGINEERING_SPEC_BY_ID.get(task_id)
        if static is not None:
            return static
        with self._connect() as db:
            row = db.execute(
                "SELECT spec_json,spec_sha256,proposal_digest,fingerprint,"
                "scope_attempt_id,scope_review_json "
                "FROM approved_engineering_specs WHERE task_id=?",
                (task_id,),
            ).fetchone()
            proposal_row = (
                db.execute(
                    "SELECT proposal_json,status,planner_attempt_id "
                    "FROM discovery_proposals WHERE "
                    "fingerprint=? AND proposal_digest=?",
                    (row["fingerprint"], row["proposal_digest"]),
                ).fetchone()
                if row is not None
                else None
            )
            cycle_row = (
                db.execute(
                    "SELECT baseline_head FROM discovery_cycles WHERE fingerprint=?",
                    (row["fingerprint"],),
                ).fetchone()
                if row is not None
                else None
            )
            attempt_row = (
                db.execute(
                    "SELECT status FROM discovery_attempts WHERE id=?",
                    (row["scope_attempt_id"],),
                ).fetchone()
                if row is not None
                else None
            )
        if row is None:
            return None
        if (
            proposal_row is None
            or proposal_row["status"] != "approved"
            or cycle_row is None
            or attempt_row is None
            or attempt_row["status"] != "approved"
        ):
            raise ValueError("approved discovery proposal missing")
        proposal = DiscoveryProposal.model_validate_json(
            str(proposal_row["proposal_json"])
        )
        review = ScopeReview.model_validate_json(str(row["scope_review_json"]))
        if review.verdict != "PASS":
            raise ValueError("approved discovery scope verdict changed")
        validate_scope_review(
            review,
            proposal,
            str(proposal_row["planner_attempt_id"]),
            str(cycle_row["baseline_head"]),
            str(row["fingerprint"]),
        )
        expected = spec_from_proposal(proposal)
        data = {
            "id": expected.id,
            "area": expected.area,
            "prompt": expected.prompt,
            "owned_paths": sorted(expected.owned_paths),
        }
        if (
            proposal_digest(proposal) != row["proposal_digest"]
            or row["spec_json"] != canonical_json(data)
            or row["spec_sha256"] != digest(data)
            or expected.id != task_id
        ):
            raise ValueError("approved discovery spec changed")
        return expected

    def task(self, task_id: str) -> RunnerTask | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        return self._task(row) if row else None

    def tasks(self) -> list[RunnerTask]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM tasks ORDER BY created_at,id").fetchall()
        return [self._task(row) for row in rows]

    @staticmethod
    def _task(row: sqlite3.Row) -> RunnerTask:
        return RunnerTask(
            id=str(row["id"]),
            area=str(row["area"]),
            prompt=str(row["prompt"]),
            status=str(row["status"]),
            attempt_count=int(row["attempt_count"]),
            next_allowed_at=row["next_allowed_at"],
            last_attempt_id=row["last_attempt_id"],
            depends_on=row["depends_on"],
            task_kind=str(row["task_kind"]),
            blocker=(
                json.loads(str(row["blocker_json"]))
                if row["blocker_json"] is not None
                else None
            ),
            engineering_status=row["engineering_status"],
            investment_status=row["investment_status"],
        )

    def quarantine(self, task_id: str, status: str, blocker: dict[str, Any]) -> bool:
        if status not in {"blocked", "waiting_external", "waiting_human"}:
            raise ValueError("invalid quarantine state")
        with self._connect() as db:
            cur = db.execute(
                "UPDATE tasks SET status=?,blocker_json=?,updated_at=?,"
                "next_allowed_at=? WHERE id=? AND status='queued'",
                (
                    status,
                    json.dumps(blocker, sort_keys=True),
                    utc_now(),
                    blocker["next_eligible_retry"],
                    task_id,
                ),
            )
        return cur.rowcount == 1

    def release_due_waiting(self, now: datetime | None = None) -> list[str]:
        """Release only bounded external waits whose verified UTC deadline passed."""
        current = now or datetime.now(UTC)
        if current.tzinfo is None or current.utcoffset() != timedelta(0):
            raise ValueError("current time must be timezone-aware UTC")
        released: list[str] = []
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute(
                "SELECT id,last_attempt_id,blocker_json,next_allowed_at FROM tasks "
                "WHERE status='waiting_external' AND attempt_count <= 2 "
                "AND next_allowed_at IS NOT NULL"
            ).fetchall()
            for row in rows:
                try:
                    blocker = Blocker.model_validate_json(str(row["blocker_json"]))
                except (ValueError, TypeError):
                    continue
                due = blocker.next_eligible_retry
                try:
                    scheduled = datetime.fromisoformat(str(row["next_allowed_at"]))
                except ValueError:
                    continue
                if (
                    blocker.retry_policy != "bounded"
                    or due is None
                    or due > current
                    or scheduled != due
                ):
                    continue
                db.execute(
                    "UPDATE tasks SET status='queued',next_allowed_at=NULL,"
                    "previous_attempt_id=last_attempt_id,updated_at=? "
                    "WHERE id=? AND status='waiting_external'",
                    (current.isoformat(), row["id"]),
                )
                released.append(str(row["id"]))
            if released:
                db.execute("DELETE FROM runner_meta WHERE key='idle_status'")
            db.commit()
        return released

    def release_event(self, task_id: str, evidence_path: Path) -> bool:
        """Release a data wait on changed evidence; engineering review stays pending."""
        if not evidence_path.is_file() or evidence_path.is_symlink():
            return False
        resolved = evidence_path.resolve()
        try:
            current_identity = hashlib.sha256(resolved.read_bytes()).hexdigest()
        except OSError:
            return False
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT status,task_kind,blocker_json,last_attempt_id "
                "FROM tasks WHERE id=?",
                (task_id,),
            ).fetchone()
            if (
                row is None
                or row["status"] != "waiting_external"
                or row["task_kind"] == "engineering"
            ):
                db.rollback()
                return False
            try:
                blocker = Blocker.model_validate_json(str(row["blocker_json"]))
            except (ValueError, TypeError):
                db.rollback()
                return False
            if (
                blocker.retry_policy != "event"
                or blocker.blocker_reason == "independent_review_pending"
                or blocker.dependency != str(resolved)
                or blocker.dependency_identity is None
                or blocker.dependency_identity == current_identity
            ):
                db.rollback()
                return False
            db.execute(
                "UPDATE tasks SET status='queued',next_allowed_at=NULL,"
                "blocker_json=NULL,previous_attempt_id=last_attempt_id,updated_at=? "
                "WHERE id=? AND status='waiting_external'",
                (utc_now(), task_id),
            )
            db.execute("DELETE FROM runner_meta WHERE key='idle_status'")
            db.commit()
        return True

    def active_attempt(self) -> RunnerAttempt | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM attempts WHERE status='running' "
                "ORDER BY started_at LIMIT 1"
            ).fetchone()
        return self._attempt(row) if row else None

    def running_reviews(self) -> list[ReviewAttempt]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT id,task_id,process_group_id,process_id,process_starttime "
                "FROM review_attempts "
                "WHERE status='running' ORDER BY started_at,id"
            ).fetchall()
        return [
            ReviewAttempt(
                str(row["id"]),
                str(row["task_id"]),
                row["process_group_id"],
                row["process_id"],
                row["process_starttime"],
            )
            for row in rows
        ]

    @staticmethod
    def _matches_candidate(raw: Any, candidate: ReviewCandidate) -> bool:
        try:
            envelope = json.loads(str(raw))
        except (TypeError, ValueError):
            return False
        return (
            isinstance(envelope, dict)
            and envelope.get("review_candidate_version")
            == (2 if candidate.recovery is not None else 1)
            and envelope.get("completion") == candidate.completion
            and envelope.get("recovery") == candidate.recovery
        )

    def failed_candidate_source(
        self, task_id: str, attempt_id: str
    ) -> FailedCandidateSource | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT tasks.*,attempts.output_path,attempts.baseline_head,"
                "attempts.evidence_json,attempts.rowid AS attempt_rowid "
                "FROM tasks JOIN attempts ON attempts.id=tasks.last_attempt_id "
                "WHERE tasks.id=? AND attempts.id=? "
                "AND tasks.task_kind='engineering' AND tasks.status='failed' "
                "AND attempts.status='failed' "
                "AND attempts.failure_code='completion_invalid'",
                (task_id, attempt_id),
            ).fetchone()
            legacy_allowed = row is not None and _legacy_failed_output_allowed(
                db, int(row["attempt_rowid"])
            )
        if (
            row is None
            or not isinstance(row["output_path"], str)
            or not isinstance(row["baseline_head"], str)
        ):
            return None
        return FailedCandidateSource(
            self._task(row),
            attempt_id,
            row["output_path"],
            row["baseline_head"],
            row["evidence_json"],
            legacy_allowed,
        )

    def create_recovery_candidate(
        self,
        source: FailedCandidateSource,
        recovery_id: str,
        output_path: Path,
        completion: dict[str, Any],
        recovery: dict[str, str],
    ) -> bool:
        now = utc_now()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            paused = db.execute(
                "SELECT value FROM runner_meta WHERE key='paused'"
            ).fetchone()
            row = db.execute(
                "SELECT tasks.status,tasks.last_attempt_id,tasks.attempt_count,"
                "attempts.status AS attempt_status,attempts.failure_code,"
                "attempts.output_path,attempts.baseline_head,attempts.evidence_json,"
                "attempts.rowid AS attempt_rowid "
                "FROM tasks JOIN attempts ON attempts.id=tasks.last_attempt_id "
                "WHERE tasks.id=? AND tasks.task_kind='engineering'",
                (source.task.id,),
            ).fetchone()
            if (
                paused is None
                or paused["value"] != "1"
                or row is None
                or row["status"] != "failed"
                or row["last_attempt_id"] != source.attempt_id
                or row["attempt_status"] != "failed"
                or row["failure_code"] != "completion_invalid"
                or row["output_path"] != source.output_path
                or row["baseline_head"] != source.baseline_head
                or row["evidence_json"] != source.output_evidence
                or _legacy_failed_output_allowed(db, int(row["attempt_rowid"]))
                != source.legacy_output_allowed
                or not failed_output_digest_matches(
                    row["evidence_json"],
                    recovery["source_sha256"],
                    allow_legacy=_legacy_failed_output_allowed(
                        db, int(row["attempt_rowid"])
                    ),
                )
                or not recovery_evidence_matches(row["evidence_json"], recovery)
            ):
                db.rollback()
                return False
            try:
                source_path = Path(source.output_path)
                source_intact = (
                    not source_path.is_symlink()
                    and source_path.stat().st_size <= 65_536
                    and hashlib.sha256(source_path.read_bytes()).hexdigest()
                    == recovery["source_sha256"]
                    and not (source_path.parent / "stdout.jsonl").is_symlink()
                    and (source_path.parent / "stdout.jsonl").stat().st_size
                    <= 8_388_608
                    and hashlib.sha256(
                        (source_path.parent / "stdout.jsonl").read_bytes()
                    ).hexdigest()
                    == recovery["source_transcript_sha256"]
                )
            except OSError:
                source_intact = False
            if not source_intact:
                db.rollback()
                return False
            envelope = {
                "review_candidate_version": 2,
                "completion": completion,
                "recovery": recovery,
            }
            db.execute(
                "INSERT INTO attempts "
                "(id,task_id,status,started_at,ended_at,output_path,"
                "evidence_json,failure_code,baseline_head) "
                "VALUES(?,?,'waiting_external',?,?,?,?,?,?)",
                (
                    recovery_id,
                    source.task.id,
                    now,
                    now,
                    str(output_path),
                    json.dumps(envelope, sort_keys=True),
                    "independent_review_pending",
                    source.baseline_head,
                ),
            )
            blocker = unknown_blocker("independent_review_pending")
            updated = db.execute(
                "UPDATE tasks SET status='waiting_external',last_attempt_id=?,"
                "previous_attempt_id=?,attempt_count=?,blocker_json=?,"
                "updated_at=? WHERE id=? AND status='failed' AND last_attempt_id=?",
                (
                    recovery_id,
                    source.attempt_id,
                    int(row["attempt_count"]) + 1,
                    json.dumps(blocker.model_dump(mode="json"), sort_keys=True),
                    now,
                    source.task.id,
                    source.attempt_id,
                ),
            )
            if updated.rowcount != 1:
                db.rollback()
                return False
            db.commit()
        return True

    def recovery_source_matches(self, candidate: ReviewCandidate) -> bool:
        recovery = candidate.recovery
        if recovery is None:
            return False
        with self._connect() as db:
            row = db.execute(
                "SELECT status,failure_code,output_path,baseline_head,evidence_json,"
                "rowid AS attempt_rowid "
                "FROM attempts WHERE id=? AND task_id=?",
                (recovery["source_attempt_id"], candidate.task.id),
            ).fetchone()
            legacy_allowed = row is not None and _legacy_failed_output_allowed(
                db, int(row["attempt_rowid"])
            )
        return bool(
            row is not None
            and row["status"] == "failed"
            and row["failure_code"] == "completion_invalid"
            and row["output_path"] == recovery["source_output_path"]
            and row["baseline_head"] == candidate.baseline_head
            and failed_output_digest_matches(
                row["evidence_json"],
                recovery["source_sha256"],
                allow_legacy=legacy_allowed,
            )
            and recovery_evidence_matches(row["evidence_json"], recovery)
        )

    def recover_running_reviews(self, attempt_ids: list[str]) -> list[str]:
        """Interrupt only reviewers whose process groups have stopped."""
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            recovered: list[str] = []
            for review_id in attempt_ids:
                changed = db.execute(
                    "UPDATE review_attempts SET status='interrupted',ended_at=?,"
                    "failure_code='runner_restart' WHERE id=? AND status='running'",
                    (utc_now(), review_id),
                )
                if changed.rowcount == 1:
                    recovered.append(review_id)
            db.commit()
        return recovered

    def quarantine_reviews(self, attempt_ids: list[str]) -> list[str]:
        """Exclude uncertain reviewer processes without claiming they exited."""
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            quarantined: list[str] = []
            blocker = unknown_blocker("review_process_needs_manual_reconciliation")
            for review_id in attempt_ids:
                row = db.execute(
                    "SELECT task_id,implementation_attempt_id "
                    "FROM review_attempts WHERE id=? AND status='running'",
                    (review_id,),
                ).fetchone()
                if row is None:
                    continue
                db.execute(
                    "UPDATE review_attempts SET status='quarantined',"
                    "failure_code='review_process_needs_manual_reconciliation' "
                    "WHERE id=? AND status='running'",
                    (review_id,),
                )
                db.execute(
                    "UPDATE tasks SET blocker_json=?,updated_at=? "
                    "WHERE id=? AND status='waiting_external' "
                    "AND last_attempt_id=?",
                    (
                        json.dumps(blocker.model_dump(mode="json"), sort_keys=True),
                        utc_now(),
                        row["task_id"],
                        row["implementation_attempt_id"],
                    ),
                )
                quarantined.append(review_id)
            db.commit()
        return quarantined

    def review_candidate(self) -> ReviewCandidate | None:
        """Only new, validated candidate envelopes can enter this path."""
        with self._connect() as db:
            rows = db.execute(
                "SELECT tasks.*,attempts.evidence_json,attempts.baseline_head "
                "FROM tasks JOIN attempts ON attempts.id=tasks.last_attempt_id "
                "WHERE tasks.task_kind='engineering' "
                "AND tasks.status='waiting_external' "
                "AND attempts.status='waiting_external' "
                "AND attempts.failure_code='independent_review_pending' "
                "ORDER BY tasks.created_at,tasks.id"
            ).fetchall()
            for row in rows:
                try:
                    envelope = json.loads(str(row["evidence_json"]))
                except (TypeError, ValueError):
                    continue
                if (
                    not isinstance(envelope, dict)
                    or envelope.get("review_candidate_version") not in {1, 2}
                    or not isinstance(envelope.get("completion"), dict)
                    or not isinstance(row["baseline_head"], str)
                ):
                    continue
                recovery = envelope.get("recovery")
                if envelope["review_candidate_version"] == 2:
                    if (
                        not isinstance(recovery, dict)
                        or set(recovery)
                        not in (
                            {
                                "source_attempt_id",
                                "source_output_path",
                                "source_sha256",
                                "source_transcript_sha256",
                                "recovery_sha256",
                            },
                            {
                                "source_attempt_id",
                                "source_output_path",
                                "source_sha256",
                                "source_transcript_sha256",
                                "recovery_sha256",
                                "source_evidence_identity",
                            },
                        )
                        or not all(
                            isinstance(value, str) for value in recovery.values()
                        )
                    ):
                        continue
                elif recovery is not None:
                    continue
                latest = db.execute(
                    "SELECT status,failure_code FROM review_attempts "
                    "WHERE implementation_attempt_id=? "
                    "ORDER BY started_at DESC,id DESC LIMIT 1",
                    (row["last_attempt_id"],),
                ).fetchone()
                count = db.execute(
                    "SELECT COUNT(*) FROM review_attempts "
                    "WHERE implementation_attempt_id=?",
                    (row["last_attempt_id"],),
                ).fetchone()[0]
                if count >= 2 or (
                    latest is not None
                    and (
                        latest["status"] not in {"failed", "interrupted"}
                        or latest["failure_code"]
                        not in {"timeout", "idle_timeout", "runner_restart"}
                    )
                ):
                    continue
                return ReviewCandidate(
                    self._task(row),
                    str(row["last_attempt_id"]),
                    str(row["baseline_head"]),
                    envelope["completion"],
                    recovery,
                )
        return None

    def claim_review(
        self,
        candidate: ReviewCandidate,
        review_id: str,
        output_path: Path,
        context: dict[str, Any],
        launched_at: str,
    ) -> bool:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT tasks.status,tasks.last_attempt_id,attempts.status "
                "AS attempt_status,attempts.evidence_json FROM tasks "
                "JOIN attempts ON attempts.id=tasks.last_attempt_id "
                "WHERE tasks.id=?",
                (candidate.task.id,),
            ).fetchone()
            if (
                row is None
                or row["status"] != "waiting_external"
                or row["last_attempt_id"] != candidate.implementation_attempt_id
                or row["attempt_status"] != "waiting_external"
                or not self._matches_candidate(row["evidence_json"], candidate)
            ):
                db.rollback()
                return False
            previous = db.execute(
                "SELECT status,failure_code FROM review_attempts "
                "WHERE implementation_attempt_id=? "
                "ORDER BY started_at DESC,id DESC LIMIT 1",
                (candidate.implementation_attempt_id,),
            ).fetchone()
            count = db.execute(
                "SELECT COUNT(*) FROM review_attempts "
                "WHERE implementation_attempt_id=?",
                (candidate.implementation_attempt_id,),
            ).fetchone()[0]
            if count >= 2 or (
                previous is not None
                and (
                    previous["status"] not in {"failed", "interrupted"}
                    or previous["failure_code"]
                    not in {"timeout", "idle_timeout", "runner_restart"}
                )
            ):
                db.rollback()
                return False
            db.execute(
                "INSERT INTO review_attempts "
                "(id,task_id,implementation_attempt_id,status,started_at,"
                "output_path,context_json) VALUES(?,?,?,'running',?,?,?)",
                (
                    review_id,
                    candidate.task.id,
                    candidate.implementation_attempt_id,
                    utc_now(),
                    str(output_path),
                    json.dumps(context, sort_keys=True),
                ),
            )
            db.execute("INSERT INTO launch_log(launched_at) VALUES(?)", (launched_at,))
            db.execute("DELETE FROM runner_meta WHERE key='idle_status'")
            db.execute(
                "INSERT INTO runner_meta(key,value) VALUES('last_launch_at',?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (launched_at,),
            )
            db.commit()
        return True

    def mark_review_candidate_stale(self, candidate: ReviewCandidate) -> bool:
        """Quarantine failed preflight without consuming a reviewer launch."""
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT status,last_attempt_id FROM tasks WHERE id=?",
                (candidate.task.id,),
            ).fetchone()
            if (
                row is None
                or row["status"] != "waiting_external"
                or row["last_attempt_id"] != candidate.implementation_attempt_id
            ):
                db.rollback()
                return False
            blocker = unknown_blocker("review_candidate_stale")
            db.execute(
                "UPDATE attempts SET failure_code='review_candidate_stale' "
                "WHERE id=? AND status='waiting_external'",
                (candidate.implementation_attempt_id,),
            )
            db.execute(
                "UPDATE tasks SET blocker_json=?,updated_at=? WHERE id=?",
                (
                    json.dumps(blocker.model_dump(mode="json"), sort_keys=True),
                    utc_now(),
                    candidate.task.id,
                ),
            )
            db.commit()
        return True

    def set_review_process_identity(
        self, review_id: str, group_id: int, process_id: int, starttime: int
    ) -> None:
        if group_id <= 1 or group_id != process_id or starttime <= 0:
            raise ValueError("invalid reviewer process identity")
        with self._connect() as db:
            db.execute(
                "UPDATE review_attempts SET process_group_id=?,process_id=?,"
                "process_starttime=? "
                "WHERE id=? AND status='running'",
                (group_id, process_id, starttime, review_id),
            )

    def finish_review(
        self,
        candidate: ReviewCandidate,
        review_id: str,
        *,
        status: str,
        failure_code: str | None = None,
        receipt: dict[str, Any] | None = None,
    ) -> bool:
        if status not in {"completed", "failed", "interrupted"}:
            raise ValueError("invalid review status")
        if status == "completed" and receipt is None:
            raise ValueError("completed review requires receipt")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT review_attempts.status,review_attempts.context_json,"
                "tasks.status AS task_status,tasks.last_attempt_id,"
                "attempts.status AS implementation_status,attempts.evidence_json,"
                "attempts.baseline_head,attempts.output_path AS implementation_output "
                "FROM review_attempts JOIN tasks ON tasks.id=review_attempts.task_id "
                "JOIN attempts ON "
                "attempts.id=review_attempts.implementation_attempt_id "
                "WHERE review_attempts.id=? AND review_attempts.task_id=? "
                "AND review_attempts.implementation_attempt_id=?",
                (review_id, candidate.task.id, candidate.implementation_attempt_id),
            ).fetchone()
            if (
                row is None
                or row["status"] != "running"
                or row["task_status"] != "waiting_external"
                or row["last_attempt_id"] != candidate.implementation_attempt_id
                or row["implementation_status"] != "waiting_external"
                or row["baseline_head"] != candidate.baseline_head
                or not self._matches_candidate(row["evidence_json"], candidate)
            ):
                db.rollback()
                return False
            if status == "completed":
                if candidate.recovery is not None:
                    source = db.execute(
                        "SELECT status,failure_code,output_path,baseline_head,"
                        "evidence_json,rowid AS attempt_rowid FROM attempts "
                        "WHERE id=? AND task_id=?",
                        (
                            candidate.recovery["source_attempt_id"],
                            candidate.task.id,
                        ),
                    ).fetchone()
                    try:
                        source_path = Path(candidate.recovery["source_output_path"])
                        candidate_path = Path(str(row["implementation_output"]))
                        expected_candidate_path = (
                            self.db_path.parent
                            / "recoveries"
                            / candidate.implementation_attempt_id
                            / "completion.json"
                        )
                        intact = (
                            candidate_path == expected_candidate_path
                            and not source_path.is_symlink()
                            and not candidate_path.is_symlink()
                            and source_path.stat().st_size <= 65_536
                            and candidate_path.stat().st_size <= 65_536
                            and hashlib.sha256(source_path.read_bytes()).hexdigest()
                            == candidate.recovery["source_sha256"]
                            and not (source_path.parent / "stdout.jsonl").is_symlink()
                            and (source_path.parent / "stdout.jsonl").stat().st_size
                            <= 8_388_608
                            and hashlib.sha256(
                                (source_path.parent / "stdout.jsonl").read_bytes()
                            ).hexdigest()
                            == candidate.recovery["source_transcript_sha256"]
                            and hashlib.sha256(candidate_path.read_bytes()).hexdigest()
                            == candidate.recovery["recovery_sha256"]
                        )
                    except OSError:
                        intact = False
                    if (
                        source is None
                        or source["status"] != "failed"
                        or source["failure_code"] != "completion_invalid"
                        or source["output_path"] != str(source_path)
                        or source["baseline_head"] != candidate.baseline_head
                        or not failed_output_digest_matches(
                            source["evidence_json"],
                            candidate.recovery["source_sha256"],
                            allow_legacy=_legacy_failed_output_allowed(
                                db, int(source["attempt_rowid"])
                            ),
                        )
                        or not recovery_evidence_matches(
                            source["evidence_json"], candidate.recovery
                        )
                        or not intact
                    ):
                        db.rollback()
                        return False
                try:
                    expected_receipt = json.loads(str(row["context_json"])) | {
                        "verdict": "PASS"
                    }
                except (TypeError, ValueError):
                    db.rollback()
                    return False
                if receipt != expected_receipt:
                    db.rollback()
                    return False
            db.execute(
                "UPDATE review_attempts SET status=?,ended_at=?,failure_code=?,"
                "receipt_json=? WHERE id=?",
                (
                    status,
                    utc_now(),
                    failure_code,
                    json.dumps(receipt, sort_keys=True) if receipt else None,
                    review_id,
                ),
            )
            if status == "completed":
                db.execute(
                    "UPDATE attempts SET status='completed',failure_code=NULL "
                    "WHERE id=? AND status='waiting_external'",
                    (candidate.implementation_attempt_id,),
                )
                db.execute(
                    "UPDATE tasks SET status='completed',blocker_json=NULL,"
                    "engineering_status='ENGINEERING_COMPLETE',"
                    "investment_status='NOT_EVALUATED',updated_at=? "
                    "WHERE id=? AND status='waiting_external'",
                    (utc_now(), candidate.task.id),
                )
                db.execute(
                    "INSERT OR IGNORE INTO history_outbox "
                    "(id,task_id,attempt_id,outcome) VALUES(?,?,?,'completed')",
                    (
                        f"development-runner:{candidate.task.id}:"
                        f"{candidate.implementation_attempt_id}:completed",
                        candidate.task.id,
                        candidate.implementation_attempt_id,
                    ),
                )
            db.commit()
        return True

    @staticmethod
    def _attempt(row: sqlite3.Row) -> RunnerAttempt:
        return RunnerAttempt(
            id=str(row["id"]),
            task_id=str(row["task_id"]),
            status=str(row["status"]),
            process_group_id=row["process_group_id"],
            output_path=row["output_path"],
            baseline_head=row["baseline_head"],
        )

    def recover_running(self) -> list[RunnerAttempt]:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute(
                "SELECT * FROM attempts WHERE status='running'"
            ).fetchall()
            now = utc_now()
            for row in rows:
                db.execute(
                    "UPDATE attempts SET status='interrupted',ended_at=?, "
                    "failure_code=? WHERE id=?",
                    (now, "runner_restart", row["id"]),
                )
                db.execute(
                    "UPDATE tasks SET status='interrupted',updated_at=? "
                    "WHERE id=? AND status='running'",
                    (now, row["task_id"]),
                )
                identity = (
                    f"development-runner:{row['task_id']}:{row['id']}:interrupted"
                )
                db.execute(
                    "INSERT OR IGNORE INTO history_outbox "
                    "(id,task_id,attempt_id,outcome) VALUES(?,?,?,?)",
                    (identity, row["task_id"], row["id"], "interrupted"),
                )
            db.commit()
        return [self._attempt(row) for row in rows]

    def claim(
        self,
        task: RunnerTask,
        attempt_id: str,
        output_path: Path,
        stderr_path: Path,
        launched_at: str | None = None,
        history_outcome: str = "started",
        baseline_head: str | None = None,
    ) -> RunnerAttempt:
        now = utc_now()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT status,attempt_count FROM tasks WHERE id=?", (task.id,)
            ).fetchone()
            if row is None or row["status"] != "queued":
                db.rollback()
                raise ValueError("task is not claimable")
            db.execute(
                "UPDATE tasks SET status='running',attempt_count=attempt_count+1, "
                "last_attempt_id=?,updated_at=? WHERE id=?",
                (attempt_id, now, task.id),
            )
            db.execute("DELETE FROM runner_meta WHERE key='idle_status'")
            db.execute(
                "INSERT INTO attempts "
                "(id,task_id,status,started_at,output_path,stderr_path,baseline_head) "
                "VALUES(?,?, 'running',?,?,?,?)",
                (
                    attempt_id,
                    task.id,
                    now,
                    str(output_path),
                    str(stderr_path),
                    baseline_head,
                ),
            )
            if launched_at is not None:
                db.execute(
                    "INSERT INTO launch_log(launched_at) VALUES(?)", (launched_at,)
                )
                db.execute(
                    "INSERT INTO runner_meta(key,value) VALUES('last_launch_at',?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (launched_at,),
                )
            identity = f"development-runner:{task.id}:{attempt_id}:{history_outcome}"
            db.execute(
                "INSERT OR IGNORE INTO history_outbox "
                "(id,task_id,attempt_id,outcome) VALUES(?,?,?,?)",
                (identity, task.id, attempt_id, history_outcome),
            )
            db.commit()
        return RunnerAttempt(
            attempt_id, task.id, "running", None, str(output_path), baseline_head
        )

    def set_process_group(self, attempt_id: str, process_group_id: int) -> None:
        with self._connect() as db:
            db.execute(
                "UPDATE attempts SET process_group_id=? WHERE id=?",
                (process_group_id, attempt_id),
            )

    def finish(
        self,
        attempt_id: str,
        task_id: str,
        status: str,
        *,
        failure_code: str | None = None,
        evidence: dict[str, Any] | None = None,
        next_allowed_at: str | None = None,
        automatic_retry: bool = False,
        blocker: dict[str, Any] | None = None,
    ) -> None:
        now = utc_now()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            task = db.execute(
                "SELECT status,attempt_count,last_attempt_id,task_kind,"
                "previous_attempt_id,depends_on "
                "FROM tasks WHERE id=?",
                (task_id,),
            ).fetchone()
            attempt = db.execute(
                "SELECT status,rowid AS attempt_rowid FROM attempts "
                "WHERE id=? AND task_id=?",
                (attempt_id, task_id),
            ).fetchone()
            if (
                attempt is None
                or attempt["status"] != "running"
                or task is None
                or task["status"] != "running"
                or task["last_attempt_id"] != attempt_id
            ):
                db.rollback()
                return
            db.execute(
                "UPDATE attempts SET status=?,ended_at=?,failure_code=?, "
                "evidence_json=? WHERE id=?",
                (
                    status,
                    now,
                    failure_code,
                    json.dumps(evidence, sort_keys=True) if evidence else None,
                    attempt_id,
                ),
            )
            if (
                task["task_kind"] == "engineering"
                and status == "failed"
                and failure_code == "completion_invalid"
                and isinstance(evidence, dict)
                and evidence.get("failed_output_digest_version") == 1
            ):
                db.execute(
                    "INSERT OR IGNORE INTO runner_meta(key,value) "
                    "VALUES('failed_output_digest_min_rowid',?)",
                    (str(attempt["attempt_rowid"]),),
                )
            task_status = "completed" if status == "completed" else status
            if blocker is None and status in {
                "blocked",
                "waiting_external",
                "waiting_human",
            }:
                known_reason = (
                    evidence.get("blocked_reason") if evidence is not None else None
                )
                blocker = unknown_blocker(
                    failure_code or known_reason or "unknown",
                    dependency=task["depends_on"],
                ).model_dump(mode="json")
            retry_at = next_allowed_at
            retry_attempt = None
            previous_attempt = None if task is None else task["previous_attempt_id"]
            if (
                automatic_retry
                and status in {"failed", "blocked"}
                and task is not None
                and task["last_attempt_id"] == attempt_id
                and 1 <= int(task["attempt_count"]) <= 2
            ):
                retry_at = (
                    datetime.now(UTC)
                    + timedelta(seconds=(60, 120)[int(task["attempt_count"]) - 1])
                ).isoformat()
                task_status = "queued"
                retry_attempt = attempt_id
                previous_attempt = attempt_id
            db.execute(
                "UPDATE tasks SET status=?,updated_at=?,next_allowed_at=?,"
                "previous_attempt_id=?,blocker_json=?,"
                "engineering_status=?,investment_status=? WHERE id=?",
                (
                    task_status,
                    now,
                    retry_at,
                    previous_attempt,
                    json.dumps(
                        {
                            **blocker,
                            "retry_policy": "bounded"
                            if retry_attempt
                            else blocker["retry_policy"],
                            "resume_condition": (
                                "bounded recovery deadline"
                                if retry_attempt
                                else blocker["resume_condition"]
                            ),
                            "next_eligible_retry": retry_at,
                        },
                        sort_keys=True,
                    )
                    if blocker is not None
                    else None,
                    (
                        evidence.get("engineering_status")
                        if status == "completed" and evidence is not None
                        else None
                    ),
                    (
                        evidence.get("investment_status")
                        if status == "completed" and evidence is not None
                        else None
                    ),
                    task_id,
                ),
            )
            identity = f"development-runner:{task_id}:{attempt_id}:{status}"
            db.execute(
                "INSERT OR IGNORE INTO history_outbox "
                "(id,task_id,attempt_id,outcome) VALUES(?,?,?,?)",
                (identity, task_id, attempt_id, status),
            )
            if retry_attempt is not None:
                db.execute(
                    "INSERT OR IGNORE INTO history_outbox "
                    "(id,task_id,attempt_id,outcome) VALUES(?,?,?,?)",
                    (
                        f"development-runner:{task_id}:{attempt_id}:automatic_retry",
                        task_id,
                        attempt_id,
                        "automatic_retry",
                    ),
                )
            db.commit()

    def last_failure_code(self, task_id: str) -> str | None:
        """Return the latest bounded failure label for planner feedback."""
        with self._connect() as db:
            row = db.execute(
                "SELECT failure_code FROM attempts "
                "WHERE task_id=? AND failure_code IS NOT NULL "
                "ORDER BY ended_at DESC, started_at DESC LIMIT 1",
                (task_id,),
            ).fetchone()
        return None if row is None else str(row["failure_code"])

    def stage_roadmap_planning(self, pending: PendingRoadmapScope) -> bool:
        """Freeze a validated roadmap proposal without creating a product task."""
        proposal = pending.proposal
        if (
            pending.result.status != "proposed"
            or pending.result.task_id != pending.planner_task_id
            or pending.result.attempt_id != pending.planner_attempt_id
            or pending.result.fingerprint != pending.fingerprint
        ):
            raise ValueError("roadmap proposal identity invalid")
        value = scope_json(pending.model_dump(mode="json"))
        now = utc_now()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            task = db.execute(
                "SELECT status,last_attempt_id FROM tasks "
                "WHERE id=? AND area='__planning__'",
                (pending.planner_task_id,),
            ).fetchone()
            attempt = db.execute(
                "SELECT status FROM attempts WHERE id=? AND task_id=?",
                (pending.planner_attempt_id, pending.planner_task_id),
            ).fetchone()
            paused = db.execute(
                "SELECT value FROM runner_meta WHERE key='paused'"
            ).fetchone()
            actual = scope_json(self._discovery_snapshot(db))
            count = db.execute(
                "SELECT COUNT(*) FROM tasks WHERE area!='__planning__' "
                "AND status IN ('queued','running')"
            ).fetchone()
            if (
                task is None
                or task["status"] != "running"
                or task["last_attempt_id"] != pending.planner_attempt_id
                or attempt is None
                or attempt["status"] != "running"
                or paused is not None
                and paused["value"] == "1"
                or actual != scope_json(pending.snapshot)
                or int(count[0]) >= ROADMAP_PENDING_LIMIT
                or db.execute(
                    "SELECT 1 FROM tasks WHERE id=?", (proposal.id,)
                ).fetchone()
                is not None
            ):
                db.rollback()
                return False
            db.execute(
                "INSERT INTO roadmap_planning_scopes "
                "(planner_task_id,planner_attempt_id,fingerprint,pending_json,"
                "pending_sha256,status,reason,updated_at) "
                "VALUES(?,?,?,?,?,'pending','awaiting_scope',?)",
                (
                    pending.planner_task_id,
                    pending.planner_attempt_id,
                    pending.fingerprint,
                    value,
                    hashlib.sha256(value.encode()).hexdigest(),
                    now,
                ),
            )
            db.execute(
                "UPDATE attempts SET status='scope_pending',evidence_json=?,"
                "failure_code='planning_scope_pending' WHERE id=?",
                (pending.result.model_dump_json(), pending.planner_attempt_id),
            )
            db.execute(
                "UPDATE tasks SET status='scope_pending',updated_at=? WHERE id=?",
                (now, pending.planner_task_id),
            )
            db.execute("DELETE FROM runner_meta WHERE key='idle_status'")
            db.commit()
        return True

    def pending_roadmap_scope(self) -> PendingRoadmapScope | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT pending_json,pending_sha256 FROM roadmap_planning_scopes "
                "WHERE status='pending' ORDER BY updated_at LIMIT 1"
            ).fetchone()
        if row is None:
            return None
        raw = str(row["pending_json"])
        if hashlib.sha256(raw.encode()).hexdigest() != row["pending_sha256"]:
            raise ValueError("stored roadmap scope changed")
        pending = PendingRoadmapScope.model_validate_json(raw)
        pending.proposal
        return pending

    def roadmap_scope_status(self) -> dict[str, str] | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT status,reason,updated_at FROM roadmap_planning_scopes "
                "ORDER BY updated_at DESC LIMIT 1"
            ).fetchone()
        return dict(row) if row is not None else None

    def terminalize_roadmap_scope(
        self, pending: PendingRoadmapScope, reason: str
    ) -> bool:
        now = utc_now()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            changed = db.execute(
                "UPDATE roadmap_planning_scopes SET status='stale',reason=?,"
                "updated_at=? WHERE planner_task_id=? AND status='pending' "
                "AND active_review_id IS NULL",
                (reason, now, pending.planner_task_id),
            ).rowcount
            if changed == 1:
                db.execute(
                    "UPDATE attempts SET status='failed',ended_at=?,failure_code=? "
                    "WHERE id=? AND status='scope_pending'",
                    (now, "planning_scope_" + reason, pending.planner_attempt_id),
                )
                db.execute(
                    "UPDATE tasks SET status='failed',updated_at=? WHERE id=? "
                    "AND status='scope_pending'",
                    (now, pending.planner_task_id),
                )
            db.commit()
        return changed == 1

    def start_roadmap_scope_review(
        self,
        pending: PendingRoadmapScope,
        review_id: str,
        output_path: Path,
        launched_at: str,
    ) -> bool:
        now = utc_now()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT status,active_review_id,pending_json "
                "FROM roadmap_planning_scopes "
                "WHERE planner_task_id=?",
                (pending.planner_task_id,),
            ).fetchone()
            paused = db.execute(
                "SELECT value FROM runner_meta WHERE key='paused'"
            ).fetchone()
            count = db.execute(
                "SELECT COUNT(*) FROM tasks WHERE area!='__planning__' "
                "AND status IN ('queued','running')"
            ).fetchone()
            if (
                row is None
                or row["status"] != "pending"
                or row["active_review_id"] is not None
                or row["pending_json"] != scope_json(pending.model_dump(mode="json"))
                or paused is not None
                and paused["value"] == "1"
                or scope_json(self._discovery_snapshot(db))
                != scope_json(pending.snapshot)
                or int(count[0]) >= ROADMAP_PENDING_LIMIT
                or datetime.fromisoformat(pending.expires_at) <= datetime.now(UTC)
            ):
                db.rollback()
                return False
            db.execute(
                "INSERT INTO roadmap_scope_attempts "
                "(id,planner_task_id,status,started_at,output_path) "
                "VALUES(?,?,'running',?,?)",
                (review_id, pending.planner_task_id, now, str(output_path)),
            )
            db.execute(
                "UPDATE roadmap_planning_scopes SET active_review_id=?,"
                "reason='scope_running',updated_at=? WHERE planner_task_id=?",
                (review_id, now, pending.planner_task_id),
            )
            db.execute("INSERT INTO launch_log(launched_at) VALUES(?)", (launched_at,))
            db.execute(
                "INSERT INTO runner_meta(key,value) VALUES('last_launch_at',?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (launched_at,),
            )
            db.commit()
        return True

    def set_roadmap_scope_process_identity(
        self, review_id: str, group_id: int, process_id: int, starttime: int
    ) -> None:
        with self._connect() as db:
            db.execute(
                "UPDATE roadmap_scope_attempts SET process_group_id=?,process_id=?,"
                "process_starttime=? WHERE id=? AND status='running'",
                (group_id, process_id, starttime, review_id),
            )

    def running_roadmap_scope_reviews(self) -> list[ReviewAttempt]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT id,process_group_id,process_id,process_starttime "
                "FROM roadmap_scope_attempts WHERE status='running'"
            ).fetchall()
        return [
            ReviewAttempt(
                str(row["id"]),
                "__planning__",
                row["process_group_id"],
                row["process_id"],
                row["process_starttime"],
            )
            for row in rows
        ]

    def roadmap_scope_orphan_hold(self) -> bool:
        with self._connect() as db:
            row = db.execute(
                "SELECT 1 FROM roadmap_scope_attempts WHERE status='quarantined' "
                "AND reason='orphan_uncertain' LIMIT 1"
            ).fetchone()
        return row is not None

    def quarantine_roadmap_scope_review(
        self, review_id: str, *, uncertain: bool = True
    ) -> None:
        now = utc_now()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT planner_task_id FROM roadmap_scope_attempts "
                "WHERE id=? AND status='running'",
                (review_id,),
            ).fetchone()
            if row is not None:
                task_id = str(row["planner_task_id"])
                pending = db.execute(
                    "SELECT planner_attempt_id FROM roadmap_planning_scopes "
                    "WHERE planner_task_id=? AND active_review_id=?",
                    (task_id, review_id),
                ).fetchone()
                db.execute(
                    "UPDATE roadmap_scope_attempts SET status='quarantined',"
                    "ended_at=?,reason=? WHERE id=?",
                    (
                        now,
                        "orphan_uncertain" if uncertain else "orphan_recovered",
                        review_id,
                    ),
                )
                if pending is not None:
                    db.execute(
                        "UPDATE roadmap_planning_scopes SET status='quarantined',"
                        "active_review_id=NULL,reason='orphan_uncertain',"
                        "updated_at=? WHERE planner_task_id=?",
                        (now, task_id),
                    )
                    db.execute(
                        "UPDATE attempts SET status='failed',ended_at=?,"
                        "failure_code='planning_scope_orphan_uncertain' WHERE id=? "
                        "AND status='scope_pending'",
                        (now, pending["planner_attempt_id"]),
                    )
                    db.execute(
                        "UPDATE tasks SET status='failed',updated_at=? WHERE id=? "
                        "AND status='scope_pending'",
                        (now, task_id),
                    )
            db.commit()

    def finish_roadmap_scope_review(
        self,
        pending: PendingRoadmapScope,
        review_id: str,
        outcome: str,
        response_sha256: str | None = None,
    ) -> bool:
        if outcome not in {
            "rejected",
            "waiting",
            "failed",
            "stale",
            "interrupted",
            "quarantined",
        }:
            raise ValueError("invalid roadmap scope outcome")
        now = utc_now()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT status,active_review_id FROM roadmap_planning_scopes "
                "WHERE planner_task_id=?",
                (pending.planner_task_id,),
            ).fetchone()
            attempt = db.execute(
                "SELECT status FROM roadmap_scope_attempts "
                "WHERE id=? AND planner_task_id=?",
                (review_id, pending.planner_task_id),
            ).fetchone()
            if (
                row is None
                or row["status"] != "pending"
                or row["active_review_id"] != review_id
                or attempt is None
                or attempt["status"] != "running"
            ):
                db.rollback()
                return False
            db.execute(
                "UPDATE roadmap_scope_attempts SET status=?,ended_at=?,"
                "response_sha256=?,reason=? WHERE id=?",
                (outcome, now, response_sha256, outcome, review_id),
            )
            if outcome == "interrupted":
                db.execute(
                    "UPDATE roadmap_planning_scopes SET active_review_id=NULL,"
                    "reason='paused',updated_at=? WHERE planner_task_id=?",
                    (now, pending.planner_task_id),
                )
            else:
                db.execute(
                    "UPDATE roadmap_planning_scopes SET status=?,active_review_id=NULL,"
                    "reason=?,updated_at=? WHERE planner_task_id=?",
                    (outcome, outcome, now, pending.planner_task_id),
                )
                db.execute(
                    "UPDATE attempts SET status='failed',ended_at=?,failure_code=? "
                    "WHERE id=? AND status='scope_pending'",
                    (now, "planning_scope_" + outcome, pending.planner_attempt_id),
                )
                db.execute(
                    "UPDATE tasks SET status='failed',updated_at=? WHERE id=? "
                    "AND status='scope_pending'",
                    (now, pending.planner_task_id),
                )
            db.commit()
        return True

    def approve_roadmap_scope(
        self,
        pending: PendingRoadmapScope,
        review_id: str,
        review: RoadmapScopeReview,
        repo: Path,
        prompt: str,
        response_sha256: str,
    ) -> bool:
        validate_roadmap_scope_review(review, pending, review_id)
        if review.verdict != "PASS" or review.work_class is None:
            raise ValueError("scope PASS with bounded work class required")
        proposal = pending.proposal
        if not prompt.startswith(
            ROADMAP_TASK_SCOPE_GUARD.format(work_class=review.work_class)
        ) or not prompt.endswith(proposal.prompt):
            raise ValueError("roadmap prompt changed")
        now = utc_now()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM roadmap_planning_scopes WHERE planner_task_id=?",
                (pending.planner_task_id,),
            ).fetchone()
            attempt = db.execute(
                "SELECT status FROM roadmap_scope_attempts "
                "WHERE id=? AND planner_task_id=?",
                (review_id, pending.planner_task_id),
            ).fetchone()
            planner = db.execute(
                "SELECT status,last_attempt_id FROM tasks WHERE id=?",
                (pending.planner_task_id,),
            ).fetchone()
            planner_attempt = db.execute(
                "SELECT status FROM attempts WHERE id=? AND task_id=?",
                (pending.planner_attempt_id, pending.planner_task_id),
            ).fetchone()
            paused = db.execute(
                "SELECT value FROM runner_meta WHERE key='paused'"
            ).fetchone()
            snapshot = self._discovery_snapshot(db)
            if (
                row is None
                or row["status"] != "pending"
                or row["active_review_id"] != review_id
                or row["pending_json"] != scope_json(pending.model_dump(mode="json"))
                or row["pending_sha256"]
                != scope_digest(pending.model_dump(mode="json"))
                or attempt is None
                or attempt["status"] != "running"
                or planner is None
                or planner["status"] != "scope_pending"
                or planner["last_attempt_id"] != pending.planner_attempt_id
                or planner_attempt is None
                or planner_attempt["status"] != "scope_pending"
                or paused is not None
                and paused["value"] == "1"
                or scope_json(snapshot) != scope_json(pending.snapshot)
                or datetime.fromisoformat(pending.expires_at) <= datetime.now(UTC)
            ):
                db.rollback()
                return False
            current_head = subprocess.run(
                ["git", "rev-parse", "main"],
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            ).stdout.strip()
            code_tree = subprocess.run(
                ["git", "rev-parse", "main:backend/jusik"],
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            ).stdout.strip()
            roadmap = load_roadmap(repo)
            mandate = validate_dispatch_gate(repo)
            if (
                current_head != pending.baseline_head
                or mandate.digest != pending.mandate_digest
                or roadmap.digest != pending.roadmap_digest
                or roadmap_fingerprint(
                    [(str(item[0]), str(item[1]), item[2]) for item in snapshot],
                    roadmap,
                    mandate.digest,
                    code_tree,
                )
                != pending.fingerprint
            ):
                db.rollback()
                return False
            for item in proposal.evidence:
                raw = Path(item.path).expanduser()
                path = raw.resolve()
                if raw.is_symlink() or path.is_symlink() or not path.is_file():
                    db.rollback()
                    return False
                if hashlib.sha256(path.read_bytes()).hexdigest() != item.sha256:
                    db.rollback()
                    return False
            tasks = [
                self._task(item)
                for item in db.execute("SELECT * FROM tasks ORDER BY created_at,id")
            ]
            validate_enqueue(roadmap, tasks, proposal.id, proposal.area)
            db.execute(
                "INSERT INTO tasks(id,area,prompt,status,created_at,updated_at) "
                "VALUES(?,?,?,'queued',?,?)",
                (proposal.id, proposal.area, prompt, now, now),
            )
            db.execute(
                "UPDATE roadmap_scope_attempts SET status='approved',ended_at=?,"
                "response_sha256=?,reason='scope_pass' WHERE id=?",
                (now, response_sha256, review_id),
            )
            db.execute(
                "UPDATE roadmap_planning_scopes SET status='approved',"
                "active_review_id=NULL,receipt_json=?,reason='approved',"
                "updated_at=? WHERE planner_task_id=?",
                (review.model_dump_json(), now, pending.planner_task_id),
            )
            db.execute(
                "UPDATE attempts SET status='completed',ended_at=?,"
                "failure_code='planning_proposed' WHERE id=?",
                (now, pending.planner_attempt_id),
            )
            db.execute(
                "UPDATE tasks SET status='completed',updated_at=? WHERE id=?",
                (now, pending.planner_task_id),
            )
            db.execute("DELETE FROM runner_meta WHERE key='idle_status'")
            db.commit()
        return True

    def finish_planning(
        self,
        attempt_id: str,
        task_id: str,
        status: str,
        evidence: dict[str, Any],
        fingerprint: str,
        expected_tasks: list[tuple[str, str, str | None]],
        current_fingerprint: str | None = None,
        proposal: tuple[str, str, str] | None = None,
        scope: str = "research",
        proposal_head_matches: bool = True,
    ) -> bool:
        """Finish generic planning; roadmap proposals require independent scope PASS."""
        if scope == "investment-roadmap" and proposal is not None:
            raise ValueError("roadmap proposal requires independent scope review")
        now = utc_now()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute(
                "SELECT status FROM attempts WHERE id=? AND task_id=?",
                (attempt_id, task_id),
            ).fetchone()
            if prior is not None and prior["status"] == "completed":
                db.rollback()
                return True
            if prior is None or prior["status"] != "running":
                db.rollback()
                raise ValueError("planning attempt is not running")
            task = db.execute(
                "SELECT status,last_attempt_id FROM tasks WHERE id=?",
                (task_id,),
            ).fetchone()
            if (
                task is None
                or task["status"] != "running"
                or task["last_attempt_id"] != attempt_id
            ):
                db.rollback()
                raise ValueError("planning task is not current")
            paused = db.execute(
                "SELECT value FROM runner_meta WHERE key='paused'"
            ).fetchone()
            if paused is not None and paused["value"] == "1":
                db.rollback()
                raise RuntimeError("planning interrupted")
            snapshot = db.execute(
                "SELECT id,status,last_attempt_id FROM tasks "
                "WHERE area != '__planning__' ORDER BY id"
            ).fetchall()
            actual = json.dumps(
                [
                    (str(r["id"]), str(r["status"]), r["last_attempt_id"])
                    for r in snapshot
                ],
                sort_keys=True,
            )
            expected = json.dumps(sorted(expected_tasks), sort_keys=True)
            if (
                (current_fingerprint is not None and current_fingerprint != fingerprint)
                or (proposal is not None and not proposal_head_matches)
                or hashlib.sha256(expected.encode()).hexdigest()
                != hashlib.sha256(actual.encode()).hexdigest()
            ):
                db.execute(
                    "UPDATE attempts SET status='failed',ended_at=?,failure_code=? WHERE id=?",  # noqa: E501
                    (now, "planning_stale", attempt_id),
                )
                db.execute(
                    "UPDATE tasks SET status='failed',updated_at=? WHERE id=?",
                    (now, task_id),
                )
                db.execute(
                    "INSERT OR IGNORE INTO history_outbox(id,task_id,attempt_id,outcome) VALUES(?,?,?,?)",  # noqa: E501
                    (
                        f"development-runner:{task_id}:{attempt_id}:planning_stale",
                        task_id,
                        attempt_id,
                        "planning_stale",
                    ),
                )
                db.commit()
                return False
            if proposal is not None:
                pending = db.execute(
                    "SELECT COUNT(*) AS count FROM tasks "
                    "WHERE area != '__planning__' "
                    "AND status NOT IN ('completed','failed')"
                ).fetchone()
                if int(pending["count"]) >= 8:
                    db.rollback()
                    raise ValueError("research queue is full")
                proposal_id, area, prompt = proposal
                db.execute(
                    "INSERT INTO tasks(id,area,prompt,status,created_at,updated_at) "
                    "VALUES(?,?,?,'queued',?,?)",
                    (proposal_id, area, prompt, now, now),
                )
            db.execute(
                "UPDATE attempts SET status='completed',ended_at=?,evidence_json=?,"
                "failure_code=? WHERE id=?",
                (
                    now,
                    json.dumps(evidence, sort_keys=True),
                    f"planning_{status}",
                    attempt_id,
                ),
            )
            db.execute(
                "UPDATE tasks SET status='completed',updated_at=? WHERE id=?",
                (now, task_id),
            )
            outcome = f"planning_{status}"
            db.execute(
                "INSERT OR IGNORE INTO history_outbox(id,task_id,attempt_id,outcome) "
                "VALUES(?,?,?,?)",
                (
                    f"development-runner:{task_id}:{attempt_id}:{outcome}",
                    task_id,
                    attempt_id,
                    outcome,
                ),
            )
            if proposal is not None:
                db.execute(
                    "INSERT OR IGNORE INTO history_outbox "
                    "(id,task_id,attempt_id,outcome) "
                    "VALUES(?,?,?,?)",
                    (
                        f"development-runner:{task_id}:{attempt_id}:proposal",
                        proposal[0],
                        attempt_id,
                        "planning_proposed",
                    ),
                )
            db.commit()
        return True

    def pause(self) -> None:
        self.set_meta("paused", "1")

    def resume(self) -> None:
        self.set_meta("paused", "0")

    def is_paused(self) -> bool:
        return self.get_meta("paused") == "1"

    def operator_hold_triggers(self) -> tuple[str, ...]:
        """Return legacy triggers that can silently suppress queue work."""
        names = {
            "operator_hold_no_new_tasks",
            "operator_hold_no_requeue",
        }
        with self._connect() as db:
            rows = db.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger' "
                "AND name IN (?, ?) ORDER BY name",
                tuple(sorted(names)),
            ).fetchall()
        return tuple(str(row["name"]) for row in rows)

    def retry(self, task_id: str) -> bool:
        now = utc_now()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT last_attempt_id FROM tasks WHERE id=?", (task_id,)
            ).fetchone()
            cur = db.execute(
                "UPDATE tasks SET status='queued',next_allowed_at=NULL, "
                "blocker_json=NULL, "
                "previous_attempt_id=?,updated_at=? "
                "WHERE id=? AND status IN "
                "('failed','retryable','interrupted','blocked')",
                (None if row is None else row["last_attempt_id"], now, task_id),
            )
            if cur.rowcount == 1:
                db.execute("DELETE FROM runner_meta WHERE key='idle_status'")
            db.commit()
        return cur.rowcount == 1

    def retry_planning_waiting(
        self,
        task_id: str,
        expected_tasks: list[tuple[str, str, str | None]],
    ) -> bool:
        """Retry only a completed planner whose latest result was waiting."""
        now = utc_now()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT tasks.last_attempt_id, attempts.failure_code "
                "FROM tasks JOIN attempts ON attempts.id=tasks.last_attempt_id "
                "WHERE tasks.id=? AND tasks.area='__planning__' "
                "AND tasks.status='completed' AND attempts.status='completed'",
                (task_id,),
            ).fetchone()
            if row is None or row["failure_code"] != "planning_waiting":
                db.rollback()
                return False
            snapshot = db.execute(
                "SELECT id,status,last_attempt_id FROM tasks "
                "WHERE area != '__planning__' ORDER BY id"
            ).fetchall()
            actual_tasks = [
                (str(item["id"]), str(item["status"]), item["last_attempt_id"])
                for item in snapshot
            ]
            if actual_tasks != sorted(expected_tasks):
                db.rollback()
                return False
            db.execute(
                "UPDATE tasks SET status='queued',next_allowed_at=NULL,"
                "previous_attempt_id=?,updated_at=? WHERE id=?",
                (row["last_attempt_id"], now, task_id),
            )
            db.execute("DELETE FROM runner_meta WHERE key='idle_status'")
            db.commit()
        return True

    def rebase(self, task_id: str, baseline: str) -> bool:
        """Queue a quarantined task with an explicit current-main baseline."""
        now = utc_now()
        marker = (
            "\n\nFresh rebase baseline (operator-verified current main): "
            f"{baseline}. This baseline supersedes stale prior identity values "
            "for this retry only.\n"
        )
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT status,prompt,last_attempt_id FROM tasks WHERE id=?",
                (task_id,),
            ).fetchone()
            if row is None or row["status"] not in {
                "failed",
                "retryable",
                "interrupted",
                "blocked",
            }:
                db.rollback()
                return False
            prompt = str(row["prompt"])
            if marker not in prompt:
                prompt += marker
            db.execute(
                "UPDATE tasks SET status='queued',prompt=?,next_allowed_at=NULL,"
                "blocker_json=NULL,"
                "previous_attempt_id=?,updated_at=? WHERE id=?",
                (prompt, row["last_attempt_id"], now, task_id),
            )
            db.execute("DELETE FROM runner_meta WHERE key='idle_status'")
            db.commit()
        return True

    def record_launch(self, launched_at: str) -> None:
        with self._connect() as db:
            db.execute("INSERT INTO launch_log(launched_at) VALUES(?)", (launched_at,))

    def launch_count(self, day_prefix: str) -> int:
        with self._connect() as db:
            row = db.execute(
                "SELECT COUNT(*) AS count FROM launch_log WHERE launched_at LIKE ?",
                (day_prefix + "%",),
            ).fetchone()
        return int(row["count"])

    def outbox_pending(self) -> list[tuple[str, str, str, str]]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT id,task_id,attempt_id,outcome FROM history_outbox "
                "WHERE delivered_at IS NULL ORDER BY rowid"
            ).fetchall()
        return [
            (str(r["id"]), str(r["task_id"]), str(r["attempt_id"]), str(r["outcome"]))
            for r in rows
        ]

    def add_outbox(
        self, identity: str, task_id: str, attempt_id: str, outcome: str
    ) -> None:
        with self._connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO history_outbox "
                "(id,task_id,attempt_id,outcome) VALUES(?,?,?,?)",
                (identity, task_id, attempt_id, outcome),
            )

    def mark_outbox_delivered(self, identity: str) -> None:
        with self._connect() as db:
            db.execute(
                "UPDATE history_outbox SET delivered_at=? WHERE id=?",
                (utc_now(), identity),
            )
