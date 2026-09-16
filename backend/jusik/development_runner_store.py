"""Durable private queue and attempt journal for the development runner."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


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


@dataclass(frozen=True)
class RunnerAttempt:
    id: str
    task_id: str
    status: str
    process_group_id: int | None
    output_path: str | None


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
                    failure_code TEXT
                );
                CREATE TABLE IF NOT EXISTS history_outbox (
                    id TEXT PRIMARY KEY, task_id TEXT NOT NULL,
                    attempt_id TEXT NOT NULL, outcome TEXT NOT NULL,
                    delivered_at TEXT
                );
                CREATE TABLE IF NOT EXISTS launch_log (
                    launched_at TEXT PRIMARY KEY
                );
                """
            )
            columns = {
                str(row["name"])
                for row in db.execute("PRAGMA table_info(tasks)").fetchall()
            }
            if "depends_on" not in columns:
                db.execute("ALTER TABLE tasks ADD COLUMN depends_on TEXT")

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
        self, task_id: str, area: str, prompt: str, depends_on: str | None = None
    ) -> bool:
        now = utc_now()
        with self._connect() as db:
            cur = db.execute(
                "INSERT OR IGNORE INTO tasks "
                "(id,area,prompt,status,created_at,updated_at) "
                "VALUES(?,?,?,'queued',?,?)",
                (task_id, area, prompt, now, now),
            )
            if cur.rowcount == 1 and depends_on is not None:
                db.execute(
                    "UPDATE tasks SET depends_on=? WHERE id=?", (depends_on, task_id)
                )
        return cur.rowcount == 1

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
        )

    def active_attempt(self) -> RunnerAttempt | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM attempts WHERE status='running' "
                "ORDER BY started_at LIMIT 1"
            ).fetchone()
        return self._attempt(row) if row else None

    @staticmethod
    def _attempt(row: sqlite3.Row) -> RunnerAttempt:
        return RunnerAttempt(
            id=str(row["id"]),
            task_id=str(row["task_id"]),
            status=str(row["status"]),
            process_group_id=row["process_group_id"],
            output_path=row["output_path"],
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
            db.execute(
                "INSERT INTO attempts "
                "(id,task_id,status,started_at,output_path,stderr_path) "
                "VALUES(?,?, 'running',?,?,?)",
                (attempt_id, task.id, now, str(output_path), str(stderr_path)),
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
        return RunnerAttempt(attempt_id, task.id, "running", None, str(output_path))

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
    ) -> None:
        now = utc_now()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            task = db.execute(
                "SELECT status,attempt_count,last_attempt_id,previous_attempt_id "
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
                "previous_attempt_id=? WHERE id=?",
                (task_status, now, retry_at, previous_attempt, task_id),
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
                current_fingerprint is not None and current_fingerprint != fingerprint
            ) or hashlib.sha256(expected.encode()).hexdigest() != hashlib.sha256(
                actual.encode()
            ).hexdigest():
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

    def retry(self, task_id: str) -> bool:
        now = utc_now()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT last_attempt_id FROM tasks WHERE id=?", (task_id,)
            ).fetchone()
            cur = db.execute(
                "UPDATE tasks SET status='queued',next_allowed_at=NULL, "
                "previous_attempt_id=?,updated_at=? "
                "WHERE id=? AND status IN "
                "('failed','retryable','interrupted','blocked')",
                (None if row is None else row["last_attempt_id"], now, task_id),
            )
            db.commit()
        return cur.rowcount == 1

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
