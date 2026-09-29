"""Offline identity checks for strategy evidence receipts."""

import hashlib
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from pathlib import Path
from threading import Event

import pytest

from jusik import strategy_lifecycle_receipt
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


def test_nul_containing_receipt_id_is_valid_in_new_schema(
    stores: tuple[StrategyLifecycleStore, StrategyLifecycleReceiptStore],
) -> None:
    lifecycle, receipts = stores
    receipt_id = "\x00valid\x00id"
    _record(receipts, receipt_id=receipt_id)
    with sqlite3.connect(lifecycle.path) as db:
        db.execute(
            "INSERT INTO lifecycle_evidence_receipts "
            "(receipt_id,strategy_id,version,strategy_revision,evidence_digest) "
            "VALUES (?,?,?,?,?)",
            ("\x00direct", "sample", "v1", 0, DIGEST),
        )
    assert (
        receipts.verify(
            receipt_id,
            "sample",
            "v1",
            expected_revision=0,
            evidence=EVIDENCE,
            evidence_digest=DIGEST,
        ).receipt_id
        == receipt_id
    )


def test_trigger_refresh_rolls_back_if_replacement_fails(
    stores: tuple[StrategyLifecycleStore, StrategyLifecycleReceiptStore],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lifecycle, _ = stores
    with sqlite3.connect(lifecycle.path) as db:
        db.execute("DROP TRIGGER lifecycle_receipt_id_insert_guard")
        db.execute(
            "CREATE TRIGGER lifecycle_receipt_id_insert_guard "
            "BEFORE INSERT ON lifecycle_evidence_receipts BEGIN "
            "SELECT RAISE(ABORT, 'receipt id is required') "
            "WHERE NEW.receipt_id IS NULL OR length(trim(NEW.receipt_id))=0; END"
        )
    monkeypatch.setattr(
        strategy_lifecycle_receipt,
        "_ID_GUARD_TRIGGER_SQL",
        "CREATE TRIGGER lifecycle_receipt_id_insert_guard BROKEN",
    )
    with pytest.raises(sqlite3.OperationalError):
        StrategyLifecycleReceiptStore(lifecycle)
    with sqlite3.connect(lifecycle.path) as db:
        with pytest.raises(sqlite3.IntegrityError, match="receipt id is required"):
            db.execute(
                "INSERT INTO lifecycle_evidence_receipts "
                "(receipt_id,strategy_id,version,strategy_revision,evidence_digest) "
                "VALUES (?,?,?,?,?)",
                (" ", "sample", "v1", 0, DIGEST),
            )


@pytest.mark.parametrize(
    "receipt_id",
    [
        None,
        " ",
        "\t",
        "\n",
        " \t\r\n ",
        "\x1c",
        "\x1d",
        "\x1e",
        "\x1f",
        "\x85",
        "\u00a0",
        "\u1680",
        "\u2000",
        "\u2001",
        "\u2002",
        "\u2003",
        "\u2004",
        "\u2005",
        "\u2006",
        "\u2007",
        "\u2008",
        "\u2009",
        "\u200a",
        "\u2028",
        "\u2029",
        "\u202f",
        "\u205f",
        "\u3000",
        " \u00a0\u2003\t ",
    ],
)
def test_direct_insert_rejects_blank_receipt_id(
    stores: tuple[StrategyLifecycleStore, StrategyLifecycleReceiptStore],
    receipt_id: str | None,
) -> None:
    lifecycle, receipts = stores
    before = lifecycle.get("sample", "v1")
    events = lifecycle.events("sample", "v1")
    with pytest.raises(ValueError, match="receipt id"):
        _record(receipts, receipt_id=receipt_id or "")
    with pytest.raises(ValueError, match="receipt id"):
        receipts.verify(
            receipt_id or "",
            "sample",
            "v1",
            expected_revision=0,
            evidence=EVIDENCE,
            evidence_digest=DIGEST,
        )
    with sqlite3.connect(lifecycle.path) as db:
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO lifecycle_evidence_receipts "
                "(receipt_id,strategy_id,version,strategy_revision,evidence_digest) "
                "VALUES (?,?,?,?,?)",
                (receipt_id, "sample", "v1", 0, DIGEST),
            )
        assert db.execute(
            "SELECT COUNT(*) FROM lifecycle_evidence_receipts"
        ).fetchone() == (0,)
    for valid_id in ("valid-id", "left\u00a0middle\u2003right", "\u2003x"):
        _record(receipts, receipt_id=valid_id)
        assert (
            receipts.verify(
                valid_id,
                "sample",
                "v1",
                expected_revision=0,
                evidence=EVIDENCE,
                evidence_digest=DIGEST,
            ).receipt_id
            == valid_id
        )
    assert lifecycle.get("sample", "v1") == before
    assert lifecycle.events("sample", "v1") == events


def test_reopen_existing_receipt_table_installs_id_guard(tmp_path: Path) -> None:
    lifecycle = StrategyLifecycleStore(tmp_path / "existing.sqlite3")
    lifecycle.register("sample", "v1", "synthetic definition", reason="idea")
    before = lifecycle.get("sample", "v1")
    events = lifecycle.events("sample", "v1")
    with sqlite3.connect(lifecycle.path) as db:
        db.executescript(
            "CREATE TABLE lifecycle_evidence_receipts ("
            "receipt_id TEXT PRIMARY KEY CHECK(length(trim(receipt_id)) > 0), "
            "strategy_id TEXT NOT NULL, version TEXT NOT NULL, "
            "strategy_revision INTEGER NOT NULL, evidence_digest TEXT NOT NULL);"
            "CREATE TRIGGER lifecycle_receipt_id_insert_guard "
            "BEFORE INSERT ON lifecycle_evidence_receipts BEGIN "
            "SELECT RAISE(ABORT, 'stale permissive receipt guard') "
            "WHERE 0; END;"
        )
        db.execute(
            "INSERT INTO lifecycle_evidence_receipts VALUES (?,?,?,?,?)",
            ("existing", "sample", "v1", 0, DIGEST),
        )
        db.execute(
            "INSERT INTO lifecycle_evidence_receipts VALUES (?,?,?,?,?)",
            ("\u00a0", "sample", "v1", 0, DIGEST),
        )
    StrategyLifecycleReceiptStore(lifecycle)
    reopened = StrategyLifecycleReceiptStore(lifecycle)
    with sqlite3.connect(lifecycle.path) as db:
        for receipt_id in (None, "\t", "\n", "\u00a0", "\u2003", " \u00a0\u2003"):
            with pytest.raises(sqlite3.IntegrityError, match="receipt id is required"):
                db.execute(
                    "INSERT INTO lifecycle_evidence_receipts VALUES (?,?,?,?,?)",
                    (receipt_id, "sample", "v1", 0, DIGEST),
                )
        db.execute(
            "INSERT INTO lifecycle_evidence_receipts VALUES (?,?,?,?,?)",
            ("current", "sample", "v1", 0, DIGEST),
        )
        db.execute(
            "INSERT INTO lifecycle_evidence_receipts VALUES (?,?,?,?,?)",
            ("current\u00a0id", "sample", "v1", 0, DIGEST),
        )
        db.execute(
            "INSERT INTO lifecycle_evidence_receipts VALUES (?,?,?,?,?)",
            ("\x00legacy", "sample", "v1", 0, DIGEST),
        )
        assert db.execute(
            "SELECT receipt_id FROM lifecycle_evidence_receipts "
            "WHERE receipt_id IN ('current', 'existing') ORDER BY receipt_id"
        ).fetchall() == [("current",), ("existing",)]
    for receipt_id in ("existing", "current", "current\u00a0id", "\x00legacy"):
        assert (
            reopened.verify(
                receipt_id,
                "sample",
                "v1",
                expected_revision=0,
                evidence=EVIDENCE,
                evidence_digest=DIGEST,
            ).receipt_id
            == receipt_id
        )
    with pytest.raises(ValueError, match="receipt id"):
        reopened.verify(
            "\u00a0",
            "sample",
            "v1",
            expected_revision=0,
            evidence=EVIDENCE,
            evidence_digest=DIGEST,
        )
    with sqlite3.connect(lifecycle.path) as db:
        assert db.execute(
            "SELECT receipt_id FROM lifecycle_evidence_receipts WHERE receipt_id=?",
            ("\u00a0",),
        ).fetchall() == [("\u00a0",)]
    assert lifecycle.get("sample", "v1") == before
    assert lifecycle.events("sample", "v1") == events


@pytest.mark.parametrize("foreign_keys", [False, True])
@pytest.mark.parametrize(
    ("strategy_id", "version", "revision"),
    [
        ("absent", "v1", 1),
        ("sample", "v3", 1),
        ("sample", "V1", 1),
        ("sample", "v1", 0),
        ("sample", "v1", 2),
    ],
)
def test_direct_insert_requires_current_strategy_identity_and_revision(
    stores: tuple[StrategyLifecycleStore, StrategyLifecycleReceiptStore],
    foreign_keys: bool,
    strategy_id: str,
    version: str,
    revision: int,
) -> None:
    lifecycle, _ = stores
    lifecycle.transition(
        "sample",
        "v1",
        StrategyState.RETIRED,
        expected_revision=0,
        reason="discard synthetic idea",
    )
    before = lifecycle.get("sample", "v1")
    events = lifecycle.events("sample", "v1")
    with sqlite3.connect(lifecycle.path) as db:
        db.execute(f"PRAGMA foreign_keys={'ON' if foreign_keys else 'OFF'}")
        with pytest.raises(sqlite3.IntegrityError, match="current strategy revision"):
            db.execute(
                "INSERT INTO lifecycle_evidence_receipts "
                "(receipt_id,strategy_id,version,strategy_revision,evidence_digest) "
                "VALUES (?,?,?,?,?)",
                ("direct", strategy_id, version, revision, DIGEST),
            )
        assert db.execute(
            "SELECT COUNT(*) FROM lifecycle_evidence_receipts"
        ).fetchone() == (0,)
    assert lifecycle.get("sample", "v1") == before
    assert lifecycle.events("sample", "v1") == events


@pytest.mark.parametrize("foreign_keys", [False, True])
def test_direct_current_insert_and_legacy_receipt_survive_transition(
    stores: tuple[StrategyLifecycleStore, StrategyLifecycleReceiptStore],
    foreign_keys: bool,
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
    before = lifecycle.get("sample", "v1")
    events = lifecycle.events("sample", "v1")
    with sqlite3.connect(lifecycle.path) as db:
        db.execute(f"PRAGMA foreign_keys={'ON' if foreign_keys else 'OFF'}")
        db.execute(
            "INSERT INTO lifecycle_evidence_receipts "
            "(receipt_id,strategy_id,version,strategy_revision,evidence_digest) "
            "VALUES (?,?,?,?,?)",
            ("current", "sample", "v1", 1, DIGEST),
        )
        assert db.execute(
            "SELECT receipt_id,strategy_revision FROM lifecycle_evidence_receipts "
            "ORDER BY receipt_id"
        ).fetchall() == [("current", 1), ("receipt-1", 0)]
    assert (
        receipts.verify(
            "current",
            "sample",
            "v1",
            expected_revision=1,
            evidence=EVIDENCE,
            evidence_digest=DIGEST,
        ).strategy_revision
        == 1
    )
    with pytest.raises(RevisionConflict):
        receipts.verify(
            "receipt-1",
            "sample",
            "v1",
            expected_revision=0,
            evidence=EVIDENCE,
            evidence_digest=DIGEST,
        )
    assert lifecycle.get("sample", "v1") == before
    assert lifecycle.events("sample", "v1") == events


def test_record_and_verify_after_revision_change(
    stores: tuple[StrategyLifecycleStore, StrategyLifecycleReceiptStore],
) -> None:
    lifecycle, receipts = stores
    lifecycle.transition(
        "sample",
        "v1",
        StrategyState.RETIRED,
        expected_revision=0,
        reason="discard synthetic idea",
    )
    with pytest.raises(RevisionConflict):
        _record(receipts)
    _record(receipts, expected_revision=1)
    assert (
        receipts.verify(
            "receipt-1",
            "sample",
            "v1",
            expected_revision=1,
            evidence=EVIDENCE,
            evidence_digest=DIGEST,
        ).strategy_revision
        == 1
    )


def test_record_waiting_for_transition_detects_revision_conflict(
    stores: tuple[StrategyLifecycleStore, StrategyLifecycleReceiptStore],
) -> None:
    lifecycle, receipts = stores
    started = Event()

    def record_after_writer_starts() -> None:
        started.set()
        _record(receipts)

    with sqlite3.connect(lifecycle.path, timeout=10) as writer:
        writer.execute("BEGIN IMMEDIATE")
        writer.execute(
            "UPDATE lifecycle_strategies SET state='RETIRED', revision=1, "
            "reason='discard synthetic idea' "
            "WHERE strategy_id='sample' AND version='v1'"
        )
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(record_after_writer_starts)
            assert started.wait(timeout=5)
            try:
                with pytest.raises(FutureTimeoutError):
                    pending.result(timeout=0.05)
            finally:
                writer.commit()
            with pytest.raises(RevisionConflict):
                pending.result(timeout=10)
    assert lifecycle.get("sample", "v1") is not None
    assert [event.revision for event in lifecycle.events("sample", "v1")] == [0, 1]
    with sqlite3.connect(lifecycle.path) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM lifecycle_evidence_receipts"
        ).fetchone() == (0,)
