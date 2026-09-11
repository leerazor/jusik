from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import sys
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from jusik.research_fx_provenance import (
    FxArchiveProvenance,
    FxObservationProvenance,
    FxProvenanceResult,
)
from jusik.research_quote_models import ResearchQuote
from jusik.research_receipt_journal import (
    MAX_PAYLOAD_BYTES,
    ForeignJournalError,
    ReceiptConflictError,
    ReceiptIntegrityError,
    ReceiptJournal,
    ReceiptJournalError,
)

NOW = datetime(2026, 9, 11, 6, tzinfo=UTC)
PROCESS_ID = "a" * 32
BODY = b'{"chart":"fixture"}'
SOURCE = "yahoo_usdkrw"
ARCHIVE_ID = hashlib.sha256(SOURCE.encode() + b"\0" + BODY).hexdigest()


def quote(currency: str = "USD", price: str = "100") -> ResearchQuote:
    exchange = "NAS" if currency == "USD" else "KRX"
    symbol = "NVDA" if currency == "USD" else "005930"
    source = "KIS HDFSCNT0" if currency == "USD" else "KIS H0STCNT0"
    return ResearchQuote(
        symbol=symbol,
        exchange=exchange,
        currency=currency,
        price=price,
        ask=price,
        bid=price,
        volume=1,
        accumulated_volume=1,
        market_at=NOW - timedelta(seconds=2),
        received_at=NOW - timedelta(seconds=1),
        source=source,
    )


def usd_fx() -> FxProvenanceResult:
    captured = NOW - timedelta(hours=1)
    observation = FxObservationProvenance(
        value="1355.4100341796875",
        observed_on=date(2026, 9, 10),
        available_at=captured,
        revision="bootstrap-current",
        source=SOURCE,
        raw_archive_id=ARCHIVE_ID,
        captured_at=captured,
    )
    archive = FxArchiveProvenance(
        id=ARCHIVE_ID,
        source=SOURCE,
        captured_at=captured,
        content_type="application/json",
        body_bytes=len(BODY),
        body_sha256=hashlib.sha256(BODY).hexdigest(),
    )
    return FxProvenanceResult(
        currency="USD",
        cutoff_at=NOW,
        read_started_at=NOW,
        read_finished_at=NOW,
        state="resolved",
        rate_krw_per_unit=observation.value,
        age_days=1,
        candidate_count=1,
        observation=observation,
        archive=archive,
        limitations=["fixture provenance; not linked to production"],
    )


def krw_fx() -> FxProvenanceResult:
    return FxProvenanceResult(
        currency="KRW",
        cutoff_at=NOW,
        read_started_at=NOW,
        read_finished_at=NOW,
        state="identity_conversion",
        rate_krw_per_unit=1,
        candidate_count=0,
        limitations=["identity conversion"],
    )


def journal(
    path: Path,
    *,
    clock: Callable[[], datetime] = lambda: NOW,
    monotonic_ns: Callable[[], int] = lambda: 100,
    process_clock_id: str = PROCESS_ID,
    hook: Callable[[str], None] | None = None,
) -> ReceiptJournal:
    return ReceiptJournal(
        path,
        clock=clock,
        monotonic_ns=monotonic_ns,
        _process_clock_id=process_clock_id,
        _test_hook=hook,
    )


def test_append_is_canonical_idempotent_and_preserves_original_times(
    tmp_path: Path,
) -> None:
    clocks = iter([NOW, NOW + timedelta(seconds=1)])
    monotonic = iter([100, 125])
    store = ReceiptJournal(
        tmp_path / "journal.db",
        clock=lambda: next(clocks),
        monotonic_ns=lambda: next(monotonic),
        _process_clock_id=PROCESS_ID,
    )
    created = store.append("decision:1", quote(), usd_fx())
    assert created.state == "created_visible"
    assert created.entry.sequence == 1
    assert created.entry.payload.scope == "isolated_experiment"
    assert created.entry.payload.production_ledger_linked is False
    assert created.entry.payload.accepted_nav is False
    assert created.visibility is not None
    assert created.visibility.kind == "initial_visibility"
    assert created.visibility.monotonic_elapsed_ns == 25

    retried = store.append("decision:1", quote(), usd_fx())
    assert retried.state == "reused_visible"
    assert retried.entry == created.entry
    assert retried.visibility == created.visibility
    with sqlite3.connect(store.path) as connection:
        assert connection.execute("SELECT count(*) FROM entries").fetchone()[0] == 1
        assert (
            connection.execute("SELECT count(*) FROM visibility_receipts").fetchone()[0]
            == 1
        )
        payload, digest = connection.execute(
            "SELECT payload_json, payload_sha256 FROM entries"
        ).fetchone()
    assert (
        json.dumps(
            json.loads(payload),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        == payload
    )
    assert hashlib.sha256(payload.encode()).hexdigest() == digest


def test_krw_identity_is_accepted_but_currency_or_unresolved_fx_is_rejected(
    tmp_path: Path,
) -> None:
    store = journal(tmp_path / "journal.db")
    result = store.append("krw:1", quote("KRW"), krw_fx())
    assert result.state == "created_visible"
    with pytest.raises(ValidationError, match="currencies"):
        store.append("bad:currency", quote("USD"), krw_fx())
    unavailable = usd_fx().model_copy(
        update={
            "state": "unavailable",
            "reason": "no_candidate",
            "rate_krw_per_unit": None,
            "age_days": None,
            "observation": None,
            "archive": None,
        }
    )
    with pytest.raises(ValidationError, match="resolved FX"):
        store.append("bad:unresolved", quote(), unavailable)
    assert store.read("bad:currency") is None
    assert store.read("bad:unresolved") is None


def test_same_key_conflict_and_oversize_payload_do_not_write(tmp_path: Path) -> None:
    store = journal(tmp_path / "journal.db")
    original = store.append("same-key", quote(price="100"), usd_fx())
    with pytest.raises(ReceiptConflictError):
        store.append("same-key", quote(price="101"), usd_fx())
    stored = store.read("same-key")
    assert stored is not None
    assert stored.entry == original.entry

    large_fx = usd_fx().model_copy(
        update={"limitations": ["x" * (MAX_PAYLOAD_BYTES + 1)]}
    )
    with pytest.raises(ValueError, match="256 KiB"):
        store.append("too-large", quote(), large_fx)
    assert store.read("too-large") is None


def test_entry_rollback_and_receipt_failure_have_distinct_outcomes(
    tmp_path: Path,
) -> None:
    def rollback_hook(point: str) -> None:
        if point == "before_entry_commit":
            raise ReceiptJournalError("synthetic rollback")

    rolled_back = journal(tmp_path / "rollback.db", hook=rollback_hook)
    with pytest.raises(ReceiptJournalError, match="synthetic"):
        rolled_back.append("rollback", quote(), usd_fx())
    assert rolled_back.read("rollback") is None

    def receipt_hook(point: str) -> None:
        if point == "before_visibility_commit":
            raise ReceiptJournalError("synthetic receipt failure")

    failed = journal(tmp_path / "receipt.db", hook=receipt_hook)
    result = failed.append("receipt-failure", quote(), usd_fx())
    assert result.state == "entry_committed_receipt_unavailable"
    assert result.entry_committed is True
    assert result.receipt_error == "visibility_write_failed"
    assert result.visibility is None
    record = failed.read("receipt-failure")
    assert record is not None
    assert record.visibility is None

    recovered = journal(failed.path).append("receipt-failure", quote(), usd_fx())
    assert recovered.state == "recovered_visible"
    assert recovered.visibility is not None
    assert recovered.visibility.kind == "recovery_visibility"


@pytest.mark.parametrize(
    ("point", "expected_entry", "expected_receipt"),
    [
        ("before_entry_commit", False, False),
        ("after_entry_commit", True, False),
        ("after_visibility_commit", True, True),
    ],
)
def test_real_process_exit_boundaries_are_recoverable(
    tmp_path: Path,
    point: str,
    expected_entry: bool,
    expected_receipt: bool,
) -> None:
    database = tmp_path / f"{point}.db"
    journal(database)
    fixture = tmp_path / f"{point}.json"
    fixture.write_text(
        json.dumps(
            {
                "quote": quote().model_dump(mode="json"),
                "fx": usd_fx().model_dump(mode="json"),
            }
        )
    )
    script = """
import json, os, sys
from pathlib import Path
from jusik.research_fx_provenance import FxProvenanceResult
from jusik.research_quote_models import ResearchQuote
from jusik.research_receipt_journal import ReceiptJournal
data = json.loads(Path(sys.argv[2]).read_text())
point = sys.argv[3]
def hook(current):
    if current == point:
        os._exit(73)
ReceiptJournal(Path(sys.argv[1]), _test_hook=hook).append(
    "crash-key",
    ResearchQuote.model_validate(data["quote"]),
    FxProvenanceResult.model_validate(data["fx"]),
)
"""
    completed = subprocess.run(
        [sys.executable, "-c", script, str(database), str(fixture), point],
        check=False,
        timeout=10,
    )
    assert completed.returncode == 73
    store = journal(database)
    record = store.read("crash-key")
    assert (record is not None) is expected_entry
    assert (record is not None and record.visibility is not None) is expected_receipt
    retried = store.append("crash-key", quote(), usd_fx())
    if point == "before_entry_commit":
        assert retried.state == "created_visible"
    elif point == "after_entry_commit":
        assert retried.state == "recovered_visible"
        assert retried.visibility is not None
        assert retried.visibility.kind == "recovery_visibility"
    else:
        assert retried.state == "reused_visible"


def test_concurrent_same_key_is_single_entry_and_conflict_is_rejected(
    tmp_path: Path,
) -> None:
    database = tmp_path / "journal.db"
    journal(database)

    def write(price: str) -> str:
        return (
            journal(database).append("concurrent", quote(price=price), usd_fx()).state
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        states = list(executor.map(write, ["100", "100"]))
    assert set(states) <= {
        "created_visible",
        "recovered_visible",
        "reused_visible",
    }
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT count(*) FROM entries").fetchone()[0] == 1
        assert (
            connection.execute("SELECT count(*) FROM visibility_receipts").fetchone()[0]
            == 1
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(write, price) for price in ("100", "101")]
    assert (
        sum(isinstance(item.exception(), ReceiptConflictError) for item in futures) == 1
    )


def test_clock_reversal_is_visible_and_invalid_monotonic_stops_receipt(
    tmp_path: Path,
) -> None:
    clocks = iter([NOW, NOW - timedelta(seconds=1)])
    monotonic = iter([100, 101])
    reversed_store = ReceiptJournal(
        tmp_path / "reverse.db",
        clock=lambda: next(clocks),
        monotonic_ns=lambda: next(monotonic),
        _process_clock_id=PROCESS_ID,
    )
    reversed_result = reversed_store.append("reverse", quote(), usd_fx())
    assert reversed_result.visibility is not None
    assert reversed_result.visibility.utc_reversed is True

    monotonic = iter([100, 99])
    invalid_store = ReceiptJournal(
        tmp_path / "invalid.db",
        clock=lambda: NOW,
        monotonic_ns=lambda: next(monotonic),
        _process_clock_id=PROCESS_ID,
    )
    invalid = invalid_store.append("invalid", quote(), usd_fx())
    assert invalid.state == "entry_committed_receipt_unavailable"
    assert invalid.receipt_error == "visibility_clock_invalid"
    invalid_record = invalid_store.read("invalid")
    assert invalid_record is not None
    assert invalid_record.visibility is None

    negative = ReceiptJournal(
        tmp_path / "negative.db",
        clock=lambda: NOW,
        monotonic_ns=lambda: -1,
        _process_clock_id=PROCESS_ID,
    )
    with pytest.raises(ReceiptJournalError, match="monotonic"):
        negative.append("negative", quote(), usd_fx())
    assert negative.read("negative") is None


def test_inherited_journal_uses_a_new_process_clock_identity_in_subprocess(
    tmp_path: Path,
) -> None:
    database = tmp_path / "fork.db"
    fixture = tmp_path / "fork.json"
    fixture.write_text(
        json.dumps(
            {
                "quote": quote().model_dump(mode="json"),
                "fx": usd_fx().model_dump(mode="json"),
            }
        )
    )
    script = """
import json, os, sys
from pathlib import Path
from jusik.research_fx_provenance import FxProvenanceResult
from jusik.research_quote_models import ResearchQuote
from jusik.research_receipt_journal import ReceiptJournal
data = json.loads(Path(sys.argv[2]).read_text())
store = ReceiptJournal(Path(sys.argv[1]))
parent = store.append(
    "parent", ResearchQuote.model_validate(data["quote"]),
    FxProvenanceResult.model_validate(data["fx"]),
)
child_pid = os.fork()
if child_pid == 0:
    try:
        store.append(
            "child", ResearchQuote.model_validate(data["quote"]),
            FxProvenanceResult.model_validate(data["fx"]),
        )
    except BaseException:
        os._exit(74)
    os._exit(0)
_, status = os.waitpid(child_pid, 0)
if os.waitstatus_to_exitcode(status) != 0:
    raise SystemExit(75)
child = store.read("child")
if child is None:
    raise SystemExit(76)
if child.entry.writer_process_clock_id == parent.entry.writer_process_clock_id:
    raise SystemExit(76)
"""
    completed = subprocess.run(
        [sys.executable, "-c", script, str(database), str(fixture)],
        check=False,
        timeout=10,
    )
    assert completed.returncode == 0
    store = ReceiptJournal(database)
    parent = store.read("parent")
    child = store.read("child")
    assert parent is not None
    assert child is not None
    assert child.entry.writer_process_clock_id != parent.entry.writer_process_clock_id


def test_entry_and_receipt_tampering_fail_without_normalizing_rows(
    tmp_path: Path,
) -> None:
    database = tmp_path / "journal.db"
    store = journal(database)
    result = store.append("tamper-entry", quote(), usd_fx())
    assert result.visibility is not None
    with sqlite3.connect(database) as connection:
        connection.execute(
            "DELETE FROM visibility_receipts WHERE entry_sequence=?",
            (result.entry.sequence,),
        )
        connection.execute(
            "UPDATE entries SET payload_sha256=? WHERE sequence=?",
            ("0" * 64, result.entry.sequence),
        )
    with pytest.raises(ReceiptIntegrityError):
        store.read("tamper-entry")
    with pytest.raises(ReceiptIntegrityError):
        store.append("tamper-entry", quote(), usd_fx())
    with sqlite3.connect(database) as connection:
        assert (
            connection.execute("SELECT count(*) FROM visibility_receipts").fetchone()[0]
            == 0
        )

    clean = store.append("tamper-receipt", quote(), usd_fx())
    assert clean.visibility is not None
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE visibility_receipts SET id=? WHERE entry_sequence=?",
            ("f" * 64, clean.entry.sequence),
        )
    with pytest.raises(ReceiptIntegrityError):
        store.read("tamper-receipt")
    with pytest.raises(ReceiptIntegrityError):
        store.append("tamper-receipt", quote(), usd_fx())


@pytest.mark.parametrize(
    ("column", "value", "message"),
    [
        ("precommit_monotonic_ns", 1000, "monotonic"),
        ("writer_process_clock_id", "b" * 32, "Cross-process"),
        (
            "precommit_observed_at",
            (NOW + timedelta(seconds=1)).isoformat(),
            "UTC reversal",
        ),
    ],
)
def test_entry_and_visibility_clock_relationship_tampering_is_rejected(
    tmp_path: Path, column: str, value: object, message: str
) -> None:
    database = tmp_path / "journal.db"
    store = journal(database)
    result = store.append("clock-link", quote(), usd_fx())
    assert result.visibility is not None
    with sqlite3.connect(database) as connection:
        connection.execute(
            f"UPDATE entries SET {column}=? WHERE sequence=?",
            (value, result.entry.sequence),
        )
    with pytest.raises(ReceiptIntegrityError, match=message):
        store.read("clock-link")
    with pytest.raises(ReceiptIntegrityError, match=message):
        store.append("clock-link", quote(), usd_fx())


def test_orphaned_visibility_sequence_is_rejected(tmp_path: Path) -> None:
    database = tmp_path / "journal.db"
    store = journal(database)
    result = store.append("sequence-link", quote(), usd_fx())
    assert result.visibility is not None
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute(
            "UPDATE visibility_receipts SET entry_sequence=999 WHERE entry_sequence=?",
            (result.entry.sequence,),
        )
    with pytest.raises(ReceiptIntegrityError, match="foreign key integrity"):
        store.read("sequence-link")


def test_altered_schema_is_rejected_without_further_mutation(tmp_path: Path) -> None:
    database = tmp_path / "altered.db"
    store = journal(database)
    created = store.append("existing", quote(), usd_fx())
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.executescript(
            """
            ALTER TABLE entries RENAME TO old_entries;
            CREATE TABLE entries AS SELECT * FROM old_entries;
            DROP TABLE old_entries;
            """
        )
    with sqlite3.connect(database) as connection:
        schema_before = "\n".join(connection.iterdump())
        rows_before = connection.execute("SELECT * FROM entries").fetchall()
    bytes_before = database.read_bytes()
    stat_before = database.stat()
    with pytest.raises(ForeignJournalError):
        ReceiptJournal(database)
    assert database.read_bytes() == bytes_before
    stat_after = database.stat()
    assert stat_after.st_size == stat_before.st_size
    assert stat_after.st_mtime_ns == stat_before.st_mtime_ns
    with sqlite3.connect(database) as connection:
        assert "\n".join(connection.iterdump()) == schema_before
        assert connection.execute("SELECT * FROM entries").fetchall() == rows_before
        assert rows_before[0][0] == created.entry.sequence


@pytest.mark.parametrize("kind", ["empty", "sqlite", "symlink"])
def test_foreign_paths_are_rejected_without_mutation(tmp_path: Path, kind: str) -> None:
    path = tmp_path / f"foreign-{kind}.db"
    if kind == "empty":
        path.write_bytes(b"")
    elif kind == "sqlite":
        with sqlite3.connect(path) as connection:
            connection.execute("CREATE TABLE unrelated (value TEXT)")
    else:
        target = tmp_path / "target"
        target.write_bytes(b"foreign")
        path.symlink_to(target)
    target = path.resolve() if path.is_symlink() else path
    before = target.read_bytes()
    before_stat = target.stat()
    with pytest.raises(ForeignJournalError):
        ReceiptJournal(path)
    assert target.read_bytes() == before
    after_stat = target.stat()
    assert after_stat.st_size == before_stat.st_size
    assert after_stat.st_mtime_ns == before_stat.st_mtime_ns


def test_invalid_key_is_rejected_before_writing(tmp_path: Path) -> None:
    store = journal(tmp_path / "journal.db")
    for key in ("", "has space", "x" * 129):
        with pytest.raises(ValueError, match="idempotency"):
            store.append(key, quote(), usd_fx())
    with sqlite3.connect(store.path) as connection:
        assert connection.execute("SELECT count(*) FROM entries").fetchone()[0] == 0


def test_missing_owned_database_is_not_recreated_during_append(tmp_path: Path) -> None:
    store = journal(tmp_path / "journal.db")
    store.path.unlink()
    with pytest.raises(ForeignJournalError):
        store.append("missing", quote(), usd_fx())
    assert not store.path.exists()
