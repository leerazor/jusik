"""Durable private queue and attempt journal for the development runner."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from jusik.development_runner_contract import (
    AUTOMATIC_ENGINEERING_BACKLOG,
    Blocker,
    EngineeringSpec,
    unknown_blocker,
)
from jusik.development_runner_roadmap import ROADMAP_PENDING_LIMIT


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


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
                "SELECT tasks.*,attempts.output_path,attempts.baseline_head "
                "FROM tasks JOIN attempts ON attempts.id=tasks.last_attempt_id "
                "WHERE tasks.id=? AND attempts.id=? "
                "AND tasks.task_kind='engineering' AND tasks.status='failed' "
                "AND attempts.status='failed' "
                "AND attempts.failure_code='completion_invalid' "
                "AND attempts.evidence_json IS NULL",
                (task_id, attempt_id),
            ).fetchone()
        if (
            row is None
            or not isinstance(row["output_path"], str)
            or not isinstance(row["baseline_head"], str)
        ):
            return None
        return FailedCandidateSource(
            self._task(row), attempt_id, row["output_path"], row["baseline_head"]
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
                "attempts.output_path,attempts.baseline_head,attempts.evidence_json "
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
                or row["evidence_json"] is not None
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
                "SELECT status,failure_code,output_path,baseline_head,evidence_json "
                "FROM attempts WHERE id=? AND task_id=?",
                (recovery["source_attempt_id"], candidate.task.id),
            ).fetchone()
        return bool(
            row is not None
            and row["status"] == "failed"
            and row["failure_code"] == "completion_invalid"
            and row["output_path"] == recovery["source_output_path"]
            and row["baseline_head"] == candidate.baseline_head
            and row["evidence_json"] is None
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
                        != {
                            "source_attempt_id",
                            "source_output_path",
                            "source_sha256",
                            "recovery_sha256",
                        }
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
                        "evidence_json FROM attempts WHERE id=? AND task_id=?",
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
                        or source["evidence_json"] is not None
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
                "SELECT status,attempt_count,last_attempt_id,"
                "previous_attempt_id,depends_on "
                "FROM tasks WHERE id=?",
                (task_id,),
            ).fetchone()
            attempt = db.execute(
                "SELECT status FROM attempts WHERE id=? AND task_id=?",
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
        """Finish planner and enqueue proposal in one locked transaction."""
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
                if scope == "investment-roadmap":
                    pending = db.execute(
                        "SELECT COUNT(*) AS count FROM tasks "
                        "WHERE area != '__planning__' "
                        "AND status IN ('queued','running')"
                    ).fetchone()
                else:
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
