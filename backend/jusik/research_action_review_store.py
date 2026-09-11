from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from jusik.research_action_review import (
    MAX_EVIDENCE_BYTES,
    ActionReview,
    ActionReviewPage,
    ComparedField,
    PublicEvidence,
    RawReviewEvidence,
    ReviewInput,
    ReviewManifest,
    compare_review,
)

MAX_TOTAL_EVIDENCE_BYTES = 16 * 1024 * 1024


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value: object) -> str:
    return hashlib.sha256(_json(value).encode()).hexdigest()


class ActionReviewStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS action_review_evidence (
                    id TEXT PRIMARY KEY, sha256 TEXT NOT NULL UNIQUE,
                    source_url TEXT NOT NULL, publisher TEXT NOT NULL,
                    captured_at TEXT NOT NULL, body BLOB NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS action_reviews (
                    id TEXT PRIMARY KEY, review_key TEXT NOT NULL UNIQUE,
                    revision_id TEXT NOT NULL, sequence INTEGER NOT NULL,
                    source_content_sha256 TEXT NOT NULL,
                    evidence_id TEXT NOT NULL, locator TEXT NOT NULL,
                    extracted_facts_json TEXT NOT NULL,
                    comparison_status TEXT NOT NULL,
                    compared_fields_json TEXT NOT NULL,
                    content_sha256 TEXT NOT NULL,
                    reviewed_at TEXT NOT NULL, imported_at TEXT NOT NULL,
                    UNIQUE(revision_id, sequence),
                    FOREIGN KEY(revision_id)
                        REFERENCES action_collection_revisions(id),
                    FOREIGN KEY(evidence_id) REFERENCES action_review_evidence(id)
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=0.1)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=100")
        return connection

    def import_manifest(
        self, manifest: ReviewManifest, imported_at: datetime
    ) -> dict[str, int]:
        current = imported_at.astimezone(UTC)
        prepared: list[tuple[ReviewInput, bytes]] = []
        bodies: dict[str, bytes] = {}
        total_bytes = 0
        for review in manifest.reviews:
            if review.evidence.captured_at > current:
                raise ValueError("Evidence capture timestamp is in the future.")
            evidence_path = review.evidence.local_file
            if not evidence_path.is_file():
                raise ValueError("Evidence file is not a regular file.")
            with evidence_path.open("rb") as source:
                body = source.read(MAX_EVIDENCE_BYTES + 1)
            if len(body) > MAX_EVIDENCE_BYTES:
                raise ValueError("Evidence file is too large.")
            if hashlib.sha256(body).hexdigest() != review.evidence.sha256:
                raise ValueError("Evidence file hash mismatch.")
            if review.evidence.sha256 not in bodies:
                total_bytes += len(body)
                if total_bytes > MAX_TOTAL_EVIDENCE_BYTES:
                    raise ValueError("Review evidence batch is too large.")
                bodies[review.evidence.sha256] = body
            prepared.append((review, bodies[review.evidence.sha256]))

        inserted = 0
        idempotent = 0
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            for review, body in prepared:
                revision = connection.execute(
                    """SELECT r.*, e.symbol, e.kind, e.provider_key,
                        e.latest_revision_sequence
                    FROM action_collection_revisions r
                    JOIN action_collection_events e ON e.id=r.event_id
                    WHERE r.id=?""",
                    (review.revision_id,),
                ).fetchone()
                if revision is None:
                    raise ValueError("Unknown action revision.")
                if revision["content_sha256"] != review.content_sha256:
                    raise ValueError("Action revision content hash mismatch.")
                source_payload = json.loads(revision["payload_json"])
                status, compared_fields = compare_review(
                    revision["kind"], source_payload, review.extracted_facts
                )
                content = {
                    "revision_id": review.revision_id,
                    "content_sha256": review.content_sha256,
                    "operator_verified": review.operator_verified,
                    "evidence": review.evidence.model_dump(
                        mode="json", exclude={"local_file", "locator"}
                    ),
                    "locator": review.evidence.locator,
                    "extracted_facts": review.extracted_facts.model_dump(mode="json"),
                }
                review_content_sha = _hash(content)
                existing = connection.execute(
                    "SELECT content_sha256 FROM action_reviews WHERE review_key=?",
                    (review.review_key,),
                ).fetchone()
                if existing is not None:
                    if existing["content_sha256"] != review_content_sha:
                        raise ValueError("Review key conflicts with existing content.")
                    idempotent += 1
                    continue
                evidence_id = review.evidence.sha256
                existing_evidence = connection.execute(
                    "SELECT * FROM action_review_evidence WHERE id=?", (evidence_id,)
                ).fetchone()
                if existing_evidence is None:
                    connection.execute(
                        """INSERT INTO action_review_evidence
                        (id, sha256, source_url, publisher, captured_at, body,
                         created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (
                            evidence_id,
                            review.evidence.sha256,
                            review.evidence.source_url,
                            review.evidence.publisher,
                            review.evidence.captured_at.isoformat(),
                            body,
                            current.isoformat(),
                        ),
                    )
                elif any(
                    existing_evidence[key] != value
                    for key, value in {
                        "source_url": review.evidence.source_url,
                        "publisher": review.evidence.publisher,
                        "captured_at": review.evidence.captured_at.isoformat(),
                    }.items()
                ):
                    raise ValueError(
                        "Evidence metadata conflicts with existing content."
                    )
                sequence = (
                    int(
                        connection.execute(
                            """SELECT COALESCE(MAX(sequence), 0) FROM action_reviews
                        WHERE revision_id=?""",
                            (review.revision_id,),
                        ).fetchone()[0]
                    )
                    + 1
                )
                review_id = _hash(
                    {"review_key": review.review_key, "content": review_content_sha}
                )
                connection.execute(
                    """INSERT INTO action_reviews VALUES
                    (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        review_id,
                        review.review_key,
                        review.revision_id,
                        sequence,
                        review.content_sha256,
                        evidence_id,
                        review.evidence.locator,
                        review.extracted_facts.model_dump_json(),
                        status,
                        _json(
                            [item.model_dump(mode="json") for item in compared_fields]
                        ),
                        review_content_sha,
                        current.isoformat(),
                        current.isoformat(),
                    ),
                )
                inserted += 1
        return {"inserted": inserted, "idempotent": idempotent}

    def review_page(
        self, cursor: str | None, limit: int, event_id: str | None = None
    ) -> ActionReviewPage:
        bounded = min(max(limit, 1), 100)
        with self._connect() as connection:
            clauses: list[str] = []
            parameters: list[object] = []
            if event_id is not None:
                clauses.append("r.event_id=?")
                parameters.append(event_id)
            if cursor is not None:
                boundary = connection.execute(
                    "SELECT imported_at, id FROM action_reviews WHERE id=?", (cursor,)
                ).fetchone()
                if boundary is None:
                    raise ValueError("Unknown action review cursor.")
                clauses.append("(v.imported_at<? OR (v.imported_at=? AND v.id<?))")
                parameters.extend(
                    [boundary["imported_at"], boundary["imported_at"], boundary["id"]]
                )
            where = " WHERE " + " AND ".join(clauses) if clauses else ""
            rows = connection.execute(
                """SELECT v.*, r.event_id, r.payload_json, e.symbol, e.kind,
                    e.latest_revision_sequence, r.sequence AS source_revision_sequence,
                    d.source_url, d.publisher, d.captured_at, d.sha256
                FROM action_reviews v
                JOIN action_collection_revisions r ON r.id=v.revision_id
                JOIN action_collection_events e ON e.id=r.event_id
                JOIN action_review_evidence d ON d.id=v.evidence_id"""
                + where
                + " ORDER BY v.imported_at DESC, v.id DESC LIMIT ?",
                (*parameters, bounded + 1),
            ).fetchall()
            counts = connection.execute(
                """SELECT
                    (SELECT COUNT(DISTINCT revision_id) FROM action_reviews),
                    (SELECT COUNT(*) FROM action_collection_events),
                    (SELECT COUNT(*) FROM action_collection_events e
                     WHERE NOT EXISTS (
                        SELECT 1 FROM action_reviews v
                        JOIN action_collection_revisions r ON r.id=v.revision_id
                        WHERE r.event_id=e.id
                          AND r.sequence=e.latest_revision_sequence))"""
            ).fetchone()
        items = [self._review(row) for row in rows[:bounded]]
        return ActionReviewPage(
            items=items,
            next_cursor=items[-1].id if len(rows) > bounded and items else None,
            reviewed_revision_count=counts[0],
            current_revision_count=counts[1],
            unreviewed_current_revision_count=counts[2],
        )

    @staticmethod
    def _review(row: sqlite3.Row) -> ActionReview:
        current = row["source_revision_sequence"] == row["latest_revision_sequence"]
        compared_fields = [
            ComparedField.model_validate(item)
            for item in json.loads(row["compared_fields_json"])
        ]
        compared_fields = [
            item.model_copy(update={"source_value": None})
            if item.field == "comparable_share_basis"
            else item
            for item in compared_fields
        ]
        return ActionReview(
            id=row["id"],
            review_key=row["review_key"],
            revision_id=row["revision_id"],
            event_id=row["event_id"],
            sequence=row["sequence"],
            symbol=row["symbol"],
            kind=row["kind"],
            source_content_sha256=row["source_content_sha256"],
            source_payload=json.loads(row["payload_json"]),
            extracted_facts=json.loads(row["extracted_facts_json"]),
            comparison_status=row["comparison_status"],
            compared_fields=compared_fields,
            evidence=PublicEvidence(
                id=row["evidence_id"],
                sha256=row["sha256"],
                source_url=row["source_url"],
                publisher=row["publisher"],
                locator=row["locator"],
                captured_at=row["captured_at"],
            ),
            reviewed_at=row["reviewed_at"],
            imported_at=row["imported_at"],
            current_revision=current,
            needs_review=not current,
        )

    def raw_evidence(self, evidence_id: str) -> RawReviewEvidence:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id, sha256, body FROM action_review_evidence WHERE id=?",
                (evidence_id,),
            ).fetchone()
        if row is None:
            raise KeyError(evidence_id)
        body = bytes(row["body"])
        if hashlib.sha256(body).hexdigest() != row["sha256"]:
            raise ValueError("Stored review evidence hash mismatch.")
        return RawReviewEvidence(id=row["id"], sha256=row["sha256"], body=body)
