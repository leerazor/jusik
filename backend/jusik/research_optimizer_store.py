from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, cast


def utc_now() -> datetime:
    return datetime.now(UTC)


class OptimizerStore:
    """Persistent state for the offline optimizer, separate from paper research."""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS optimizer_runs (
                    id TEXT PRIMARY KEY,
                    source_run_id TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    status TEXT NOT NULL,
                    device TEXT,
                    split_json TEXT,
                    winner_id TEXT,
                    baseline_final_json TEXT,
                    winner_final_json TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    heartbeat_at TEXT,
                    finished_at TEXT
                );
                CREATE TABLE IF NOT EXISTS optimizer_candidates (
                    optimizer_run_id TEXT NOT NULL,
                    candidate_id TEXT NOT NULL,
                    family TEXT NOT NULL,
                    parameters_json TEXT NOT NULL,
                    score TEXT,
                    eligible INTEGER NOT NULL,
                    validation_result_json TEXT,
                    artifact_path TEXT,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (optimizer_run_id, candidate_id),
                    FOREIGN KEY (optimizer_run_id) REFERENCES optimizer_runs(id)
                );
                CREATE TABLE IF NOT EXISTS optimizer_control (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS optimizer_batches (
                    id TEXT PRIMARY KEY,
                    source_run_id TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    validation_mode TEXT NOT NULL,
                    risk_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    fold_count INTEGER NOT NULL,
                    tail_json TEXT NOT NULL,
                    summary_json TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    heartbeat_at TEXT NOT NULL,
                    finished_at TEXT
                );
                CREATE TABLE IF NOT EXISTS optimizer_batch_folds (
                    batch_id TEXT NOT NULL,
                    fold_index INTEGER NOT NULL,
                    optimizer_run_id TEXT NOT NULL UNIQUE,
                    training_start TEXT NOT NULL,
                    training_end TEXT NOT NULL,
                    validation_start TEXT NOT NULL,
                    validation_end TEXT NOT NULL,
                    oos_start TEXT NOT NULL,
                    oos_end TEXT NOT NULL,
                    status TEXT NOT NULL,
                    passed INTEGER,
                    baseline_risk_json TEXT,
                    winner_risk_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (batch_id, fold_index),
                    FOREIGN KEY (batch_id) REFERENCES optimizer_batches(id),
                    FOREIGN KEY (optimizer_run_id) REFERENCES optimizer_runs(id)
                );
                """
            )

    def begin_batch(
        self,
        batch_id: str,
        source_run_id: str,
        content_hash: str,
        *,
        validation_mode: str,
        risk: dict[str, str],
        fold_count: int,
        tail: dict[str, object],
    ) -> bool:
        now = utc_now().isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO optimizer_batches (
                    id, source_run_id, content_hash, validation_mode, risk_json,
                    status, fold_count, tail_json, created_at, heartbeat_at
                ) VALUES (?, ?, ?, ?, ?, 'running', ?, ?, ?, ?)
                """,
                (
                    batch_id,
                    source_run_id,
                    content_hash,
                    validation_mode,
                    json.dumps(risk, sort_keys=True, separators=(",", ":")),
                    fold_count,
                    json.dumps(tail, sort_keys=True, separators=(",", ":")),
                    now,
                    now,
                ),
            )
            if cursor.rowcount == 1:
                return True
            row = connection.execute(
                "SELECT status FROM optimizer_batches WHERE id=?", (batch_id,)
            ).fetchone()
            if row is None or row["status"] in {"completed", "insufficient"}:
                return False
            connection.execute(
                """
                UPDATE optimizer_batches SET status='running', error=NULL,
                    heartbeat_at=?, finished_at=NULL WHERE id=?
                """,
                (now, batch_id),
            )
            return True

    def register_fold(
        self,
        batch_id: str,
        fold_index: int,
        run_id: str,
        split: dict[str, tuple[str, str]],
    ) -> None:
        now = utc_now().isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO optimizer_batch_folds (
                    batch_id, fold_index, optimizer_run_id,
                    training_start, training_end, validation_start,
                    validation_end, oos_start, oos_end, status,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'queued', ?, ?)
                """,
                (
                    batch_id,
                    fold_index,
                    run_id,
                    *split["training"],
                    *split["validation"],
                    *split["oos"],
                    now,
                    now,
                ),
            )

    def fold_completed(self, batch_id: str, fold_index: int) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT status FROM optimizer_batch_folds
                WHERE batch_id=? AND fold_index=?
                """,
                (batch_id, fold_index),
            ).fetchone()
        return row is not None and row["status"] == "completed"

    def start_fold(self, batch_id: str, fold_index: int) -> None:
        now = utc_now().isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE optimizer_batch_folds SET status='running', updated_at=?
                WHERE batch_id=? AND fold_index=? AND status!='completed'
                """,
                (now, batch_id, fold_index),
            )

    def fail_fold(
        self,
        batch_id: str,
        fold_index: int,
        *,
        stopped: bool = False,
        insufficient: bool = False,
    ) -> None:
        now = utc_now().isoformat()
        status = "stopped" if stopped else "insufficient" if insufficient else "failed"
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE optimizer_batch_folds SET status=?, updated_at=?
                WHERE batch_id=? AND fold_index=?
                """,
                (status, now, batch_id, fold_index),
            )

    def frozen_winner_id(self, run_id: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT winner_id FROM optimizer_runs WHERE id=?", (run_id,)
            ).fetchone()
        return str(row["winner_id"]) if row and row["winner_id"] else None

    def complete_fold(
        self,
        batch_id: str,
        fold_index: int,
        *,
        passed: bool,
        baseline_risk: dict[str, object],
        winner_risk: dict[str, object],
    ) -> None:
        now = utc_now().isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE optimizer_batch_folds SET status='completed', passed=?,
                    baseline_risk_json=?, winner_risk_json=?, updated_at=?
                WHERE batch_id=? AND fold_index=?
                """,
                (
                    int(passed),
                    json.dumps(baseline_risk, sort_keys=True),
                    json.dumps(winner_risk, sort_keys=True),
                    now,
                    batch_id,
                    fold_index,
                ),
            )
            connection.execute(
                "UPDATE optimizer_batches SET heartbeat_at=? WHERE id=?",
                (now, batch_id),
            )

    def complete_walk_fold(
        self,
        batch_id: str,
        fold_index: int,
        run_id: str,
        *,
        device: str,
        split: dict[str, object],
        winner_id: str,
        baseline_final: dict[str, Any],
        winner_final: dict[str, Any],
        passed: bool,
        baseline_risk: dict[str, object],
        winner_risk: dict[str, object],
    ) -> None:
        now = utc_now().isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE optimizer_runs SET status='completed', device=?,
                    split_json=?, winner_id=?, baseline_final_json=?,
                    winner_final_json=?, error=NULL, heartbeat_at=?, finished_at=?
                WHERE id=?
                """,
                (
                    device,
                    json.dumps(split, sort_keys=True, separators=(",", ":")),
                    winner_id,
                    json.dumps(baseline_final, ensure_ascii=False, sort_keys=True),
                    json.dumps(winner_final, ensure_ascii=False, sort_keys=True),
                    now,
                    now,
                    run_id,
                ),
            )
            connection.execute(
                """
                UPDATE optimizer_batch_folds SET status='completed', passed=?,
                    baseline_risk_json=?, winner_risk_json=?, updated_at=?
                WHERE batch_id=? AND fold_index=?
                """,
                (
                    int(passed),
                    json.dumps(baseline_risk, sort_keys=True),
                    json.dumps(winner_risk, sort_keys=True),
                    now,
                    batch_id,
                    fold_index,
                ),
            )
            connection.execute(
                "UPDATE optimizer_batches SET heartbeat_at=? WHERE id=?",
                (now, batch_id),
            )

    def complete_batch(self, batch_id: str, summary: dict[str, object]) -> None:
        now = utc_now().isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE optimizer_batches SET status='completed', summary_json=?,
                    error=NULL, heartbeat_at=?, finished_at=? WHERE id=?
                """,
                (json.dumps(summary, sort_keys=True), now, now, batch_id),
            )

    def fail_batch(
        self,
        batch_id: str,
        message: str,
        *,
        stopped: bool = False,
        insufficient: bool = False,
    ) -> None:
        now = utc_now().isoformat()
        status = "stopped" if stopped else "insufficient" if insufficient else "failed"
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE optimizer_batches SET status=?, error=?, heartbeat_at=?,
                    finished_at=? WHERE id=?
                """,
                (status, message, now, now, batch_id),
            )

    def batch_fold_results(self, batch_id: str) -> list[sqlite3.Row]:
        with self._connect() as connection:
            return cast(
                list[sqlite3.Row],
                connection.execute(
                    """
                    SELECT f.*, r.winner_id, r.device, r.baseline_final_json,
                        r.winner_final_json
                    FROM optimizer_batch_folds f
                    LEFT JOIN optimizer_runs r ON r.id=f.optimizer_run_id
                    WHERE f.batch_id=? ORDER BY f.fold_index
                    """,
                    (batch_id,),
                ).fetchall(),
            )

    def begin(self, run_id: str, source_run_id: str, content_hash: str) -> bool:
        now = utc_now().isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO optimizer_runs (
                    id, source_run_id, content_hash, status, created_at,
                    started_at, heartbeat_at
                ) VALUES (?, ?, ?, 'running', ?, ?, ?)
                """,
                (run_id, source_run_id, content_hash, now, now, now),
            )
            if cursor.rowcount == 1:
                return True
            row = connection.execute(
                "SELECT status FROM optimizer_runs WHERE id = ?", (run_id,)
            ).fetchone()
            if row is None or row["status"] in {"completed", "insufficient"}:
                return False
            connection.execute(
                """
                UPDATE optimizer_runs SET status='running', error=NULL,
                    started_at=?, heartbeat_at=?, finished_at=NULL
                WHERE id=?
                """,
                (now, now, run_id),
            )
            return True

    def heartbeat(self, run_id: str, *, device: str | None = None) -> None:
        now = utc_now().isoformat()
        fields = "heartbeat_at=?"
        values: list[object] = [now]
        if device is not None:
            fields += ", device=?"
            values.append(device)
        values.append(run_id)
        with self._connect() as connection:
            connection.execute(
                f"UPDATE optimizer_runs SET {fields} WHERE id=?",  # noqa: S608
                values,
            )
            connection.execute(
                """
                UPDATE optimizer_batch_folds SET updated_at=?
                WHERE optimizer_run_id=?
                """,
                (now, run_id),
            )
            connection.execute(
                """
                UPDATE optimizer_batches SET heartbeat_at=?
                WHERE id IN (
                    SELECT batch_id FROM optimizer_batch_folds
                    WHERE optimizer_run_id=?
                )
                """,
                (now, run_id),
            )
            connection.execute(
                """
                UPDATE optimizer_control SET updated_at=?
                WHERE key='daemon' AND value='running'
                """,
                (now,),
            )

    def save_candidate(
        self,
        run_id: str,
        candidate_id: str,
        family: str,
        parameters: dict[str, object],
        *,
        score: str | None,
        eligible: bool,
        validation_result: dict[str, Any] | None,
        artifact_path: Path | None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO optimizer_candidates (
                    optimizer_run_id, candidate_id, family, parameters_json,
                    score, eligible, validation_result_json, artifact_path,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(optimizer_run_id, candidate_id) DO UPDATE SET
                    score=excluded.score,
                    eligible=excluded.eligible,
                    validation_result_json=excluded.validation_result_json,
                    artifact_path=excluded.artifact_path,
                    created_at=excluded.created_at
                """,
                (
                    run_id,
                    candidate_id,
                    family,
                    json.dumps(parameters, sort_keys=True, separators=(",", ":")),
                    score,
                    int(eligible),
                    json.dumps(
                        validation_result,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    if validation_result is not None
                    else None,
                    str(artifact_path) if artifact_path is not None else None,
                    utc_now().isoformat(),
                ),
            )

    def completed_candidate_ids(self, run_id: str) -> set[str]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT candidate_id FROM optimizer_candidates
                WHERE optimizer_run_id=? AND validation_result_json IS NOT NULL
                """,
                (run_id,),
            ).fetchall()
        return {str(row["candidate_id"]) for row in rows}

    def candidate_artifact_path(self, run_id: str, candidate_id: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT artifact_path FROM optimizer_candidates
                WHERE optimizer_run_id=? AND candidate_id=?
                """,
                (run_id, candidate_id),
            ).fetchone()
        return str(row["artifact_path"]) if row and row["artifact_path"] else None

    def delete_candidate(self, run_id: str, candidate_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                DELETE FROM optimizer_candidates
                WHERE optimizer_run_id=? AND candidate_id=?
                """,
                (run_id, candidate_id),
            )

    def record_invalid_source(self, run_id: str, source_run_id: str) -> None:
        now = utc_now().isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO optimizer_runs (
                    id, source_run_id, content_hash, status, error,
                    created_at, heartbeat_at, finished_at
                ) VALUES (?, ?, 'invalid', 'insufficient', ?, ?, ?, ?)
                """,
                (
                    run_id,
                    source_run_id,
                    "저장된 완료 연구의 입력 스냅샷을 검증할 수 없습니다.",
                    now,
                    now,
                    now,
                ),
            )

    def best_candidate(self, run_id: str) -> sqlite3.Row | None:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM optimizer_candidates
                WHERE optimizer_run_id=? AND eligible=1
                """,
                (run_id,),
            ).fetchall()
        if not rows:
            return None
        return cast(
            sqlite3.Row,
            sorted(
                rows,
                key=lambda row: (
                    -Decimal(str(row["score"])),
                    str(row["candidate_id"]),
                ),
            )[0],
        )

    def freeze_winner(
        self,
        run_id: str,
        *,
        device: str,
        split: dict[str, object],
        winner_id: str,
    ) -> None:
        now = utc_now().isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE optimizer_runs SET status='final_testing', device=?,
                    split_json=?, winner_id=?, heartbeat_at=? WHERE id=?
                """,
                (
                    device,
                    json.dumps(split, sort_keys=True, separators=(",", ":")),
                    winner_id,
                    now,
                    run_id,
                ),
            )

    def complete(
        self,
        run_id: str,
        *,
        device: str,
        split: dict[str, object],
        winner_id: str,
        baseline_final: dict[str, Any],
        winner_final: dict[str, Any],
    ) -> None:
        now = utc_now().isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE optimizer_runs SET status='completed', device=?,
                    split_json=?, winner_id=?, baseline_final_json=?,
                    winner_final_json=?, error=NULL, heartbeat_at=?, finished_at=?
                WHERE id=?
                """,
                (
                    device,
                    json.dumps(split, sort_keys=True, separators=(",", ":")),
                    winner_id,
                    json.dumps(baseline_final, ensure_ascii=False, sort_keys=True),
                    json.dumps(winner_final, ensure_ascii=False, sort_keys=True),
                    now,
                    now,
                    run_id,
                ),
            )

    def fail(
        self,
        run_id: str,
        message: str,
        *,
        stopped: bool = False,
        insufficient: bool = False,
    ) -> None:
        now = utc_now().isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE optimizer_runs SET status=?, error=?, heartbeat_at=?,
                    finished_at=? WHERE id=?
                """,
                (
                    "stopped"
                    if stopped
                    else "insufficient"
                    if insufficient
                    else "failed",
                    message,
                    now,
                    now,
                    run_id,
                ),
            )

    def daemon_heartbeat(self, running: bool) -> None:
        now = utc_now().isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO optimizer_control (key, value, updated_at)
                VALUES ('daemon', ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value=excluded.value, updated_at=excluded.updated_at
                """,
                ("running" if running else "stopped", now),
            )

    def request_stop(self) -> None:
        now = utc_now().isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO optimizer_control (key, value, updated_at)
                VALUES ('stop_requested', '1', ?)
                ON CONFLICT(key) DO UPDATE SET value='1', updated_at=excluded.updated_at
                """,
                (now,),
            )

    def clear_stop(self) -> None:
        now = utc_now().isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO optimizer_control (key, value, updated_at)
                VALUES ('stop_requested', '0', ?)
                ON CONFLICT(key) DO UPDATE SET value='0', updated_at=excluded.updated_at
                """,
                (now,),
            )

    def stop_requested(self) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM optimizer_control WHERE key='stop_requested'"
            ).fetchone()
        return row is not None and row["value"] == "1"

    def status(self, stale_after: timedelta = timedelta(minutes=3)) -> dict[str, Any]:
        with self._connect() as connection:
            batch = connection.execute(
                """
                SELECT b.*,
                    MAX(
                        b.heartbeat_at,
                        COALESCE(
                            (
                                SELECT MAX(r.heartbeat_at)
                                FROM optimizer_batch_folds f
                                JOIN optimizer_runs r ON r.id=f.optimizer_run_id
                                WHERE f.batch_id=b.id
                            ),
                            b.heartbeat_at
                        )
                    ) AS activity_at
                FROM optimizer_batches b
                ORDER BY activity_at DESC LIMIT 1
                """
            ).fetchone()
            row = connection.execute(
                """
                SELECT r.*,
                    MAX(
                        r.created_at,
                        COALESCE(r.heartbeat_at, r.created_at),
                        COALESCE(r.finished_at, r.created_at)
                    ) AS activity_at
                FROM optimizer_runs r
                WHERE NOT EXISTS (
                    SELECT 1 FROM optimizer_batch_folds f
                    WHERE f.optimizer_run_id=r.id
                )
                ORDER BY activity_at DESC LIMIT 1
                """
            ).fetchone()
            completed = connection.execute(
                """
                SELECT * FROM optimizer_runs WHERE status='completed'
                ORDER BY finished_at DESC LIMIT 1
                """
            ).fetchone()
            run_counts = {
                str(item["status"]): int(item["count"])
                for item in connection.execute(
                    """
                    SELECT status, COUNT(*) AS count FROM optimizer_runs
                    GROUP BY status
                    """
                ).fetchall()
            }
            daemon = connection.execute(
                "SELECT value, updated_at FROM optimizer_control WHERE key='daemon'"
            ).fetchone()
        daemon_status = "stopped"
        if daemon is not None and daemon["value"] == "running":
            heartbeat = datetime.fromisoformat(daemon["updated_at"])
            daemon_status = (
                "stale" if utc_now() - heartbeat > stale_after else "running"
            )
        show_batch = batch is not None and (
            row is None or str(batch["activity_at"]) >= str(row["activity_at"])
        )
        if show_batch:
            assert batch is not None
            batch_result = dict(batch)
            if batch_result["status"] == "running":
                heartbeat = datetime.fromisoformat(batch_result["activity_at"])
                if utc_now() - heartbeat > stale_after:
                    batch_result["status"] = "stale"
            fold_rows = self.batch_fold_results(str(batch["id"]))
            folds: list[dict[str, object]] = []
            candidate_count = 0
            with self._connect() as connection:
                for fold in fold_rows:
                    fold_candidate_count = int(
                        connection.execute(
                            """
                            SELECT COUNT(*) FROM optimizer_candidates
                            WHERE optimizer_run_id=?
                            """,
                            (fold["optimizer_run_id"],),
                        ).fetchone()[0]
                    )
                    candidate_count += fold_candidate_count
                    item: dict[str, object] = {
                        "fold_index": fold["fold_index"],
                        "status": fold["status"],
                        "candidate_count": fold_candidate_count,
                        "device": fold["device"],
                        "training": [fold["training_start"], fold["training_end"]],
                        "validation": [
                            fold["validation_start"],
                            fold["validation_end"],
                        ],
                        "oos": [fold["oos_start"], fold["oos_end"]],
                        "winner_id": fold["winner_id"],
                        "passed": bool(fold["passed"])
                        if fold["passed"] is not None
                        else None,
                    }
                    if fold["baseline_final_json"] and fold["winner_final_json"]:
                        baseline = json.loads(fold["baseline_final_json"])["metrics"]
                        winner = json.loads(fold["winner_final_json"])["metrics"]
                        item["baseline_oos"] = {
                            "total_return_pct": baseline["total_return_pct"],
                            "max_drawdown_pct": baseline["max_drawdown_pct"],
                            "trade_count": baseline["trade_count"],
                        }
                        item["winner_oos"] = {
                            "total_return_pct": winner["total_return_pct"],
                            "max_drawdown_pct": winner["max_drawdown_pct"],
                            "trade_count": winner["trade_count"],
                        }
                        item["baseline_risk"] = json.loads(fold["baseline_risk_json"])
                        item["winner_risk"] = json.loads(fold["winner_risk_json"])
                    folds.append(item)
            return {
                "status": batch_result["status"],
                "validation_mode": batch_result["validation_mode"],
                "batch_id": batch_result["id"],
                "source_run_id": batch_result["source_run_id"],
                "risk_policy": json.loads(batch_result["risk_json"]),
                "fold_progress": {
                    "completed": sum(item["status"] == "completed" for item in folds),
                    "total": batch_result["fold_count"],
                },
                "tail": json.loads(batch_result["tail_json"]),
                "summary": json.loads(batch_result["summary_json"])
                if batch_result["summary_json"]
                else None,
                "error": batch_result["error"],
                "candidate_count": candidate_count,
                "folds": folds,
                "daemon_status": daemon_status,
            }
        if row is None:
            return {"status": "idle", "candidate_count": 0}
        result = dict(row)
        if result["status"] == "running" and result["heartbeat_at"]:
            heartbeat = datetime.fromisoformat(result["heartbeat_at"])
            if utc_now() - heartbeat > stale_after:
                result["status"] = "stale"
        for field in ("baseline_final_json", "winner_final_json"):
            payload = result.pop(field, None)
            if payload:
                parsed = json.loads(payload)
                metrics = parsed.get("metrics", {})
                result[field.removesuffix("_json")] = {
                    "total_return_pct": metrics.get("total_return_pct"),
                    "max_drawdown_pct": metrics.get("max_drawdown_pct"),
                    "trade_count": metrics.get("trade_count"),
                }
        with self._connect() as connection:
            result["candidate_count"] = connection.execute(
                """
                SELECT COUNT(*) FROM optimizer_candidates
                WHERE optimizer_run_id=?
                """,
                (result["id"],),
            ).fetchone()[0]
        result["daemon_status"] = daemon_status
        result["run_counts"] = run_counts
        if completed is not None:
            baseline = json.loads(completed["baseline_final_json"])["metrics"]
            winner = json.loads(completed["winner_final_json"])["metrics"]
            result["latest_completed"] = {
                "id": completed["id"],
                "source_run_id": completed["source_run_id"],
                "winner_id": completed["winner_id"],
                "device": completed["device"],
                "baseline_final": {
                    "total_return_pct": baseline["total_return_pct"],
                    "max_drawdown_pct": baseline["max_drawdown_pct"],
                    "trade_count": baseline["trade_count"],
                },
                "winner_final": {
                    "total_return_pct": winner["total_return_pct"],
                    "max_drawdown_pct": winner["max_drawdown_pct"],
                    "trade_count": winner["trade_count"],
                },
                "winner_passed_final": (
                    Decimal(str(winner["total_return_pct"]))
                    >= Decimal(str(baseline["total_return_pct"]))
                    and Decimal(str(winner["max_drawdown_pct"]))
                    <= Decimal(str(baseline["max_drawdown_pct"]))
                ),
            }
        return result
