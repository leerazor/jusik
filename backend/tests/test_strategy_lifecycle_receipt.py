"""Offline identity checks for strategy evidence receipts."""

import hashlib
import sqlite3
from pathlib import Path

import pytest

from jusik.strategy_lifecycle import (
    RevisionConflict,
    StrategyLifecycleStore,
    StrategyState,
)
from jusik.strategy_lifecycle_receipt import StrategyLifecycleReceiptStore

EVIDENCE = b"synthetic evidence v1"
DIGEST = hashlib.sha256(EVIDENCE).hexdigest()


@pytest.fixture
def stores(
    tmp_path: Path,
) -> tuple[StrategyLifecycleStore, StrategyLifecycleReceiptStore]:
    lifecycle = StrategyLifecycleStore(tmp_path / "strategy.sqlite3")
    lifecycle.register("sample", "v1", "synthetic definition", reason="idea")
    lifecycle.register("sample", "v2", "other synthetic definition", reason="idea")
    return lifecycle, StrategyLifecycleReceiptStore(lifecycle)


def _record(
    receipts: StrategyLifecycleReceiptStore,
    *,
    receipt_id: str = "receipt-1",
    strategy_id: str = "sample",
    version: str = "v1",
    expected_revision: int = 0,
    evidence: bytes = EVIDENCE,
    evidence_digest: str = DIGEST,
) -> None:
    receipts.record(
        receipt_id,
        strategy_id,
        version,
        expected_revision=expected_revision,
        evidence=evidence,
        evidence_digest=evidence_digest,
    )


def test_exact_identity_is_durable_and_does_not_advance_lifecycle(
    stores: tuple[StrategyLifecycleStore, StrategyLifecycleReceiptStore],
) -> None:
    lifecycle, receipts = stores
    before = lifecycle.get("sample", "v1")
    events = lifecycle.events("sample", "v1")
    _record(receipts)
    reopened = StrategyLifecycleReceiptStore(lifecycle)
    receipt = reopened.verify(
        "receipt-1",
        "sample",
        "v1",
        expected_revision=0,
        evidence=EVIDENCE,
        evidence_digest=DIGEST,
    )
    assert receipt.strategy_id == "sample"
    assert receipt.version == "v1"
    assert receipt.evidence_digest == DIGEST
    _record(reopened)
    assert lifecycle.get("sample", "v1") == before
    assert lifecycle.events("sample", "v1") == events
    assert before is not None
    assert before.state == StrategyState.IDEA
    assert before.engineering_status == "NOT_EVALUATED"
    assert before.investment_status == "NOT_EVALUATED"


def test_missing_and_wrong_version_are_rejected(
    stores: tuple[StrategyLifecycleStore, StrategyLifecycleReceiptStore],
) -> None:
    _, receipts = stores
    with pytest.raises(KeyError):
        _record(receipts, strategy_id="absent")
    with pytest.raises(KeyError):
        _record(receipts, version="v3")
    _record(receipts)
    with pytest.raises(KeyError):
        receipts.verify(
            "absent",
            "sample",
            "v1",
            expected_revision=0,
            evidence=EVIDENCE,
            evidence_digest=DIGEST,
        )
    with pytest.raises(ValueError, match="conflicting"):
        receipts.verify(
            "receipt-1",
            "sample",
            "v2",
            expected_revision=0,
            evidence=EVIDENCE,
            evidence_digest=DIGEST,
        )


def test_digest_and_receipt_identity_must_match(
    stores: tuple[StrategyLifecycleStore, StrategyLifecycleReceiptStore],
) -> None:
    _, receipts = stores
    with pytest.raises(ValueError, match="digest mismatch"):
        _record(receipts, evidence=b"changed")
    with pytest.raises(ValueError, match="invalid evidence digest"):
        _record(receipts, evidence_digest="not-a-sha256")
    _record(receipts)
    with pytest.raises(ValueError, match="conflicting"):
        _record(receipts, version="v2")
    other = b"different evidence"
    other_digest = hashlib.sha256(other).hexdigest()
    with pytest.raises(ValueError, match="conflicting"):
        _record(receipts, evidence=other, evidence_digest=other_digest)
    with pytest.raises(ValueError, match="digest mismatch"):
        receipts.verify(
            "receipt-1",
            "sample",
            "v1",
            expected_revision=0,
            evidence=other,
            evidence_digest=DIGEST,
        )


def test_stale_revision_and_immutable_storage(
    stores: tuple[StrategyLifecycleStore, StrategyLifecycleReceiptStore],
) -> None:
    lifecycle, receipts = stores
    _record(receipts)
    lifecycle.transition(
        "sample",
        "v1",
        StrategyState.RETIRED,
        expected_revision=0,
        reason="discard synthetic idea",
    )
    with pytest.raises(RevisionConflict):
        _record(receipts)
    with pytest.raises(RevisionConflict):
        receipts.verify(
            "receipt-1",
            "sample",
            "v1",
            expected_revision=0,
            evidence=EVIDENCE,
            evidence_digest=DIGEST,
        )
    with sqlite3.connect(lifecycle.path) as db:
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "UPDATE lifecycle_evidence_receipts SET version='v2' "
                "WHERE receipt_id='receipt-1'"
            )
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "DELETE FROM lifecycle_evidence_receipts WHERE receipt_id='receipt-1'"
            )


def test_missing_or_blank_receipt_identity_is_rejected(
    stores: tuple[StrategyLifecycleStore, StrategyLifecycleReceiptStore],
) -> None:
    _, receipts = stores
    with pytest.raises(ValueError, match="receipt id"):
        _record(receipts, receipt_id=" ")
    with pytest.raises(KeyError):
        receipts.verify(
            "missing",
            "sample",
            "v1",
            expected_revision=0,
            evidence=EVIDENCE,
            evidence_digest=DIGEST,
        )
