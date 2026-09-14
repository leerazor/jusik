from __future__ import annotations

import builtins
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from jusik.investor_analysis import review_thesis
from jusik.investor_models import AnalysisResult, Thesis, ThesisWrite


class ThesisConflictError(RuntimeError):
    pass


class ThesisNotFoundError(LookupError):
    pass


class InvestorStore:
    """Independent local SQLite store for user research records."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS investor_theses (
                    id TEXT PRIMARY KEY,
                    revision INTEGER NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS investor_thesis_revisions (
                    thesis_id TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (thesis_id, revision),
                    FOREIGN KEY (thesis_id) REFERENCES investor_theses(id)
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=5000")
        return connection

    @staticmethod
    def _load(row: sqlite3.Row) -> Thesis:
        return Thesis.model_validate(json.loads(str(row["payload"])))

    def list(self) -> list[Thesis]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM investor_theses ORDER BY updated_at DESC"
            ).fetchall()
        return [Thesis.model_validate(json.loads(str(row["payload"]))) for row in rows]

    def get(self, thesis_id: str) -> Thesis:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM investor_theses WHERE id = ?", (thesis_id,)
            ).fetchone()
        if row is None:
            raise ThesisNotFoundError(thesis_id)
        return self._load(row)

    def save(
        self,
        thesis_id: str | None,
        request: ThesisWrite,
        evidence: AnalysisResult,
        current_analysis: AnalysisResult | None = None,
    ) -> Thesis:
        now = datetime.now(UTC)
        actual_id = thesis_id or uuid4().hex
        latest = current_analysis or evidence
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM investor_theses WHERE id = ?", (actual_id,)
            ).fetchone()
            if row is not None:
                current = self._load(row)
                if current.revision != request.expected_revision:
                    connection.rollback()
                    raise ThesisConflictError("thesis revision conflict")
                candidate = Thesis(
                    **request.model_dump(exclude={"expected_revision"}),
                    id=actual_id,
                    revision=current.revision + 1,
                    created_at=current.created_at,
                    updated_at=now,
                    evidence=evidence,
                    current_analysis=latest,
                    review=review_thesis(
                        current.model_copy(update={"evidence": latest}), latest
                    ),
                )
                comparable = {
                    "revision",
                    "updated_at",
                    "evidence",
                    "current_analysis",
                    "review",
                }
                if candidate.model_dump(exclude=comparable) == current.model_dump(
                    exclude=comparable
                ):
                    refreshed = current.model_copy(
                        update={
                            "updated_at": now,
                            "current_analysis": latest,
                            "review": review_thesis(
                                current.model_copy(update={"evidence": latest}), latest
                            ),
                        }
                    )
                    refreshed_payload = json.dumps(
                        refreshed.model_dump(mode="json"),
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                    connection.execute(
                        "UPDATE investor_theses SET payload = ?, updated_at = ? "
                        "WHERE id = ?",
                        (refreshed_payload, now.isoformat(), actual_id),
                    )
                    connection.commit()
                    return refreshed
            else:
                if request.expected_revision != 0:
                    connection.rollback()
                    raise ThesisConflictError("new thesis must start at revision zero")
                candidate = Thesis(
                    **request.model_dump(exclude={"expected_revision"}),
                    id=actual_id,
                    revision=1,
                    created_at=now,
                    updated_at=now,
                    evidence=evidence,
                    current_analysis=latest,
                )
            candidate = candidate.model_copy(
                update={"review": review_thesis(candidate, latest)}
            )
            payload = json.dumps(
                candidate.model_dump(mode="json"),
                ensure_ascii=False,
                separators=(",", ":"),
            )
            connection.execute(
                "INSERT OR REPLACE INTO investor_theses VALUES (?, ?, ?, ?, ?)",
                (
                    actual_id,
                    candidate.revision,
                    payload,
                    candidate.created_at.isoformat(),
                    candidate.updated_at.isoformat(),
                ),
            )
            connection.execute(
                "INSERT INTO investor_thesis_revisions VALUES (?, ?, ?, ?)",
                (actual_id, candidate.revision, payload, now.isoformat()),
            )
            connection.commit()
            return candidate

    def revisions(self, thesis_id: str) -> builtins.list[Thesis]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM investor_thesis_revisions "
                "WHERE thesis_id = ? ORDER BY revision",
                (thesis_id,),
            ).fetchall()
        if not rows:
            raise ThesisNotFoundError(thesis_id)
        return [Thesis.model_validate(json.loads(str(row["payload"]))) for row in rows]
