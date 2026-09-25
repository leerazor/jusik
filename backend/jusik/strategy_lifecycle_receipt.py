"""Offline evidence receipts bound to an existing strategy version and revision.

Receipts record identity only. They do not authorize lifecycle transitions or
evaluate engineering, investment, PAPER, or live readiness.
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass

from jusik.strategy_lifecycle import RevisionConflict, StrategyLifecycleStore

_DIGEST = re.compile(r"[a-f0-9]{64}\Z")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS lifecycle_evidence_receipts (
    receipt_id TEXT PRIMARY KEY CHECK(length(trim(receipt_id)) > 0),
    strategy_id TEXT NOT NULL,
    version TEXT NOT NULL,
    strategy_revision INTEGER NOT NULL CHECK(strategy_revision >= 0),
    evidence_digest TEXT NOT NULL CHECK(
        length(evidence_digest) = 64 AND evidence_digest NOT GLOB '*[^a-f0-9]*'
    ),
    FOREIGN KEY(strategy_id, version)
        REFERENCES lifecycle_strategies(strategy_id, version)
);
CREATE TRIGGER IF NOT EXISTS lifecycle_receipt_insert_guard
BEFORE INSERT ON lifecycle_evidence_receipts BEGIN
    SELECT RAISE(ABORT, 'receipt must match current strategy revision')
    WHERE NOT EXISTS (
        SELECT 1 FROM lifecycle_strategies s
        WHERE s.strategy_id = NEW.strategy_id
          AND s.version = NEW.version
          AND s.revision = NEW.strategy_revision
    );
END;
CREATE TRIGGER IF NOT EXISTS lifecycle_receipt_no_update
BEFORE UPDATE ON lifecycle_evidence_receipts BEGIN
    SELECT RAISE(ABORT, 'evidence receipt is immutable');
END;
CREATE TRIGGER IF NOT EXISTS lifecycle_receipt_no_delete
BEFORE DELETE ON lifecycle_evidence_receipts BEGIN
    SELECT RAISE(ABORT, 'evidence receipt is immutable');
END;
"""


@dataclass(frozen=True)
class StrategyEvidenceReceipt:
    receipt_id: str
    strategy_id: str
    version: str
    strategy_revision: int
    evidence_digest: str


class StrategyLifecycleReceiptStore:
    """Persist evidence identity in the offline lifecycle registry database."""

    def __init__(self, lifecycle: StrategyLifecycleStore) -> None:
        self.lifecycle = lifecycle
        with closing(self._connect()) as db:
            if (
                db.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' "
                    "AND name='lifecycle_strategies'"
                ).fetchone()
                is None
            ):
                raise ValueError("lifecycle registry is missing")
            db.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.lifecycle.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db

    @staticmethod
    def _receipt(row: sqlite3.Row) -> StrategyEvidenceReceipt:
        return StrategyEvidenceReceipt(
            receipt_id=str(row["receipt_id"]),
            strategy_id=str(row["strategy_id"]),
            version=str(row["version"]),
            strategy_revision=int(row["strategy_revision"]),
            evidence_digest=str(row["evidence_digest"]),
        )

    def record(
        self,
        receipt_id: str,
        strategy_id: str,
        version: str,
        *,
        expected_revision: int,
        evidence: bytes,
        evidence_digest: str,
    ) -> StrategyEvidenceReceipt:
        """Record an exact digest after checking current strategy identity."""
        if not receipt_id.strip():
            raise ValueError("receipt id is required")
        if not _DIGEST.fullmatch(evidence_digest):
            raise ValueError("invalid evidence digest")
        if hashlib.sha256(evidence).hexdigest() != evidence_digest:
            raise ValueError("evidence digest mismatch")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            current = self.lifecycle._get_required(db, strategy_id, version)
            if current.revision != expected_revision:
                raise RevisionConflict("strategy revision changed")
            candidate = StrategyEvidenceReceipt(
                receipt_id, strategy_id, version, expected_revision, evidence_digest
            )
            row = db.execute(
                "SELECT * FROM lifecycle_evidence_receipts WHERE receipt_id=?",
                (receipt_id,),
            ).fetchone()
            if row is not None:
                if self._receipt(row) != candidate:
                    raise ValueError("conflicting evidence receipt identity")
                return candidate
            db.execute(
                "INSERT INTO lifecycle_evidence_receipts "
                "(receipt_id,strategy_id,version,strategy_revision,evidence_digest) "
                "VALUES (?,?,?,?,?)",
                (
                    receipt_id,
                    strategy_id,
                    version,
                    expected_revision,
                    evidence_digest,
                ),
            )
            return candidate

    def verify(
        self,
        receipt_id: str,
        strategy_id: str,
        version: str,
        *,
        expected_revision: int,
        evidence: bytes,
        evidence_digest: str,
    ) -> StrategyEvidenceReceipt:
        """Require the stored receipt and the current registry revision to agree."""
        if not _DIGEST.fullmatch(evidence_digest):
            raise ValueError("invalid evidence digest")
        if hashlib.sha256(evidence).hexdigest() != evidence_digest:
            raise ValueError("evidence digest mismatch")
        with closing(self._connect()) as db:
            db.execute("BEGIN")
            current = self.lifecycle._get_required(db, strategy_id, version)
            if current.revision != expected_revision:
                raise RevisionConflict("strategy revision changed")
            row = db.execute(
                "SELECT * FROM lifecycle_evidence_receipts WHERE receipt_id=?",
                (receipt_id,),
            ).fetchone()
        if row is None:
            raise KeyError(receipt_id)
        receipt = self._receipt(row)
        if receipt != StrategyEvidenceReceipt(
            receipt_id, strategy_id, version, expected_revision, evidence_digest
        ):
            raise ValueError("conflicting evidence receipt identity")
        return receipt
