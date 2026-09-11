from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal

from jusik.research_external_models import (
    ExternalFeatureSnapshot,
    ExternalObservation,
    ExternalSourceStatus,
)


class ExternalStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS external_raw_archives (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    captured_at TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    body BLOB NOT NULL
                );
                CREATE TABLE IF NOT EXISTS external_observations (
                    series TEXT NOT NULL,
                    observed_on TEXT NOT NULL,
                    value TEXT NOT NULL,
                    available_at TEXT NOT NULL,
                    revision TEXT NOT NULL,
                    source TEXT NOT NULL,
                    raw_archive_id TEXT NOT NULL,
                    captured_at TEXT NOT NULL,
                    PRIMARY KEY (series, observed_on, revision),
                    FOREIGN KEY (raw_archive_id) REFERENCES external_raw_archives(id)
                );
                CREATE TABLE IF NOT EXISTS external_source_status (
                    source TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    last_attempt_at TEXT NOT NULL,
                    last_success_at TEXT,
                    coverage_start TEXT,
                    coverage_end TEXT,
                    observation_count INTEGER NOT NULL DEFAULT 0,
                    error TEXT
                );
                CREATE TABLE IF NOT EXISTS external_snapshot_bindings (
                    stock_snapshot_id TEXT PRIMARY KEY,
                    external_hash TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def save_success(
        self,
        source: str,
        *,
        body: bytes,
        content_type: str,
        observations: list[ExternalObservation],
        captured_at: datetime,
        archive_coverage: tuple[date, date] | None = None,
    ) -> int:
        if captured_at.tzinfo is None:
            raise ValueError("captured_at must include a timezone.")
        captured = captured_at.astimezone(UTC)
        archive_id = hashlib.sha256(source.encode() + b"\0" + body).hexdigest()
        inserted = 0
        with self._connect() as connection:
            prior_status = connection.execute(
                "SELECT last_success_at FROM external_source_status WHERE source=?",
                (source,),
            ).fetchone()
            is_bootstrap = (
                prior_status is None or prior_status["last_success_at"] is None
            )
            connection.execute(
                """
                INSERT OR IGNORE INTO external_raw_archives (
                    id, source, captured_at, content_type, body
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (archive_id, source, captured.isoformat(), content_type, body),
            )
            for item in observations:
                latest = connection.execute(
                    """
                    SELECT value FROM external_observations
                    WHERE series=? AND observed_on=?
                    ORDER BY available_at DESC, revision DESC LIMIT 1
                    """,
                    (item.series, item.observed_on.isoformat()),
                ).fetchone()
                if latest is not None and Decimal(str(latest["value"])) == item.value:
                    continue
                if latest is None:
                    proposed = item.available_at.astimezone(UTC)
                    available_at = proposed if is_bootstrap else max(proposed, captured)
                    revision = item.revision
                else:
                    available_at = max(item.available_at.astimezone(UTC), captured)
                    revision = (
                        "revision-"
                        + hashlib.sha256(
                            (
                                f"{item.series}|{item.observed_on.isoformat()}|"
                                f"{item.value}|{captured.isoformat()}"
                            ).encode()
                        ).hexdigest()[:16]
                    )
                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO external_observations (
                        series, observed_on, value, available_at, revision,
                        source, raw_archive_id, captured_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item.series,
                        item.observed_on.isoformat(),
                        str(item.value),
                        available_at.isoformat(),
                        revision,
                        source,
                        archive_id,
                        captured.isoformat(),
                    ),
                )
                inserted += cursor.rowcount
            aggregate = connection.execute(
                """
                SELECT MIN(observed_on) AS first_date, MAX(observed_on) AS last_date,
                       COUNT(*) AS observation_count
                FROM external_observations WHERE source=?
                """,
                (source,),
            ).fetchone()
            connection.execute(
                """
                INSERT INTO external_source_status (
                    source, status, last_attempt_at, last_success_at,
                    coverage_start, coverage_end, observation_count, error
                ) VALUES (?, 'success', ?, ?, ?, ?, ?, NULL)
                ON CONFLICT(source) DO UPDATE SET
                    status='success', last_attempt_at=excluded.last_attempt_at,
                    last_success_at=excluded.last_success_at,
                    coverage_start=excluded.coverage_start,
                    coverage_end=excluded.coverage_end,
                    observation_count=excluded.observation_count, error=NULL
                """,
                (
                    source,
                    captured.isoformat(),
                    captured.isoformat(),
                    aggregate["first_date"]
                    or (
                        archive_coverage[0].isoformat()
                        if archive_coverage is not None
                        else None
                    ),
                    aggregate["last_date"]
                    or (
                        archive_coverage[1].isoformat()
                        if archive_coverage is not None
                        else None
                    ),
                    aggregate["observation_count"],
                ),
            )
        return inserted

    def record_failure(
        self, source: str, message: str, *, attempted_at: datetime
    ) -> None:
        if attempted_at.tzinfo is None:
            raise ValueError("attempted_at must include a timezone.")
        attempted = attempted_at.astimezone(UTC).isoformat()
        with self._connect() as connection:
            previous = connection.execute(
                "SELECT * FROM external_source_status WHERE source=?", (source,)
            ).fetchone()
            status = "stale" if previous and previous["last_success_at"] else "error"
            connection.execute(
                """
                INSERT INTO external_source_status (
                    source, status, last_attempt_at, last_success_at,
                    coverage_start, coverage_end, observation_count, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source) DO UPDATE SET
                    status=excluded.status,
                    last_attempt_at=excluded.last_attempt_at,
                    error=excluded.error
                """,
                (
                    source,
                    status,
                    attempted,
                    previous["last_success_at"] if previous else None,
                    previous["coverage_start"] if previous else None,
                    previous["coverage_end"] if previous else None,
                    previous["observation_count"] if previous else 0,
                    message,
                ),
            )

    def snapshot(self) -> ExternalFeatureSnapshot:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT series, observed_on, value, available_at, revision
                FROM external_observations
                ORDER BY series, observed_on, available_at, revision
                """
            ).fetchall()
        return ExternalFeatureSnapshot(
            observations=[
                ExternalObservation(
                    series=row["series"],
                    observed_on=row["observed_on"],
                    value=row["value"],
                    available_at=row["available_at"],
                    revision=row["revision"],
                )
                for row in rows
            ]
        )

    def snapshot_asof(self, cutoff_at: datetime) -> ExternalFeatureSnapshot:
        """Return revisions that were actually available by a UTC cutoff."""
        if cutoff_at.tzinfo is None:
            raise ValueError("cutoff_at must include a timezone.")
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT series, observed_on, value, available_at, revision
                FROM external_observations
                WHERE available_at<=? AND captured_at<=?
                ORDER BY series, observed_on, available_at, revision""",
                (
                    cutoff_at.astimezone(UTC).isoformat(),
                    cutoff_at.astimezone(UTC).isoformat(),
                ),
            ).fetchall()
        return ExternalFeatureSnapshot(
            observations=tuple(
                ExternalObservation(
                    series=row["series"],
                    observed_on=row["observed_on"],
                    value=row["value"],
                    available_at=row["available_at"],
                    revision=row["revision"],
                )
                for row in rows
            )
        )

    def bind_snapshot(
        self, stock_snapshot_id: str, snapshot: ExternalFeatureSnapshot
    ) -> ExternalFeatureSnapshot:
        payload = json.dumps(
            snapshot.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO external_snapshot_bindings (
                    stock_snapshot_id, external_hash, payload_json
                ) VALUES (?, ?, ?)
                """,
                (stock_snapshot_id, snapshot.semantic_hash(), payload),
            )
            row = connection.execute(
                """
                SELECT payload_json FROM external_snapshot_bindings
                WHERE stock_snapshot_id=?
                """,
                (stock_snapshot_id,),
            ).fetchone()
        assert row is not None
        return ExternalFeatureSnapshot.model_validate_json(row["payload_json"])

    def load_bound_snapshot(
        self, stock_snapshot_id: str
    ) -> ExternalFeatureSnapshot | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT payload_json FROM external_snapshot_bindings
                WHERE stock_snapshot_id=?
                """,
                (stock_snapshot_id,),
            ).fetchone()
        return (
            ExternalFeatureSnapshot.model_validate_json(row["payload_json"])
            if row is not None
            else None
        )

    def statuses(
        self,
        *,
        now: datetime | None = None,
        usages: Mapping[str, Literal["feature", "diagnostic_only", "archive_only"]]
        | None = None,
    ) -> list[ExternalSourceStatus]:
        current = (now or datetime.now(UTC)).astimezone(UTC)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT status.*, COUNT(raw.id) AS raw_archive_count,
                       COALESCE(SUM(LENGTH(raw.body)), 0) AS raw_bytes
                FROM external_source_status AS status
                LEFT JOIN external_raw_archives AS raw ON raw.source=status.source
                GROUP BY status.source ORDER BY status.source
                """
            ).fetchall()
        result = [
            ExternalSourceStatus(
                source=row["source"],
                status=row["status"],
                last_attempt_at=row["last_attempt_at"],
                last_success_at=row["last_success_at"],
                coverage_start=row["coverage_start"],
                coverage_end=row["coverage_end"],
                observation_count=row["observation_count"],
                raw_archive_count=row["raw_archive_count"],
                raw_bytes=row["raw_bytes"],
                age_hours=(
                    Decimal(
                        str(
                            max(
                                0.0,
                                (
                                    current
                                    - datetime.fromisoformat(row["last_success_at"])
                                ).total_seconds()
                                / 3600,
                            )
                        )
                    )
                    if row["last_success_at"]
                    else None
                ),
                error=row["error"],
                usage=(usages or {}).get(row["source"], "archive_only"),
            )
            for row in rows
        ]
        seen = {item.source for item in result}
        if usages is not None:
            result.extend(
                ExternalSourceStatus(source=source, status="pending", usage=usage)
                for source, usage in usages.items()
                if source not in seen
            )
        return sorted(result, key=lambda item: item.source)
