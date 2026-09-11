from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import time
import uuid
from collections.abc import Callable
from contextlib import closing
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from threading import Lock
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from jusik.research_fx_provenance import FxProvenanceResult
from jusik.research_quote_models import ResearchQuote

APPLICATION_ID = 0x4A525031
SCHEMA_VERSION = 1
MAX_PAYLOAD_BYTES = 256 * 1024
_PROCESS_CLOCK_SEED = os.urandom(32)
_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")

ReceiptFailure = Literal[
    "visibility_read_failed",
    "visibility_clock_invalid",
    "visibility_write_failed",
]
_Hook = Callable[[str], None]


class ReceiptJournalError(RuntimeError):
    pass


class ForeignJournalError(ReceiptJournalError):
    pass


class ReceiptConflictError(ReceiptJournalError):
    pass


class ReceiptIntegrityError(ReceiptJournalError):
    pass


class ReceiptClockError(ReceiptJournalError):
    pass


def _utc(value: datetime, field: str) -> datetime:
    if value.tzinfo is None:
        raise ValueError(f"{field} must be timezone-aware")
    return value.astimezone(UTC)


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class ReceiptPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    scope: Literal["isolated_experiment"] = "isolated_experiment"
    quote: ResearchQuote
    fx: FxProvenanceResult
    production_ledger_linked: Literal[False] = False
    accepted_nav: Literal[False] = False

    @model_validator(mode="after")
    def resolved_currency_pair(self) -> Self:
        if self.quote.currency != self.fx.currency:
            raise ValueError("Quote and FX currencies must match.")
        if self.quote.currency == "KRW":
            if (
                self.fx.state != "identity_conversion"
                or self.fx.rate_krw_per_unit != Decimal(1)
                or self.fx.reason is not None
                or self.fx.age_days is not None
                or self.fx.observation is not None
                or self.fx.archive is not None
            ):
                raise ValueError("KRW requires identity FX provenance.")
            return self
        if (
            self.fx.state != "resolved"
            or self.fx.rate_krw_per_unit is None
            or self.fx.reason is not None
            or self.fx.age_days is None
            or self.fx.observation is None
            or self.fx.archive is None
        ):
            raise ValueError("USD requires resolved FX provenance.")
        observation = self.fx.observation
        archive = self.fx.archive
        expected_age = (self.fx.cutoff_at.date() - observation.observed_on).days
        if (
            self.fx.rate_krw_per_unit != observation.value
            or observation.raw_archive_id != archive.id
            or observation.source != archive.source
            or archive.captured_at > observation.captured_at
            or observation.observed_on > self.fx.cutoff_at.date()
            or observation.available_at > self.fx.cutoff_at
            or observation.captured_at > self.fx.cutoff_at
            or expected_age != self.fx.age_days
            or not 0 <= expected_age <= 7
        ):
            raise ValueError("USD FX provenance is internally inconsistent.")
        return self


class JournalEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    sequence: int = Field(ge=1)
    idempotency_key: str = Field(
        min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
    )
    payload: ReceiptPayload
    payload_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    precommit_observed_at: datetime
    precommit_monotonic_ns: int = Field(ge=0)
    writer_process_clock_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    utc_reversed: bool

    @field_validator("precommit_observed_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        return _utc(value, "precommit_observed_at")


class VisibilityReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-f0-9]{64}$")
    entry_sequence: int = Field(ge=1)
    kind: Literal["initial_visibility", "recovery_visibility"]
    observed_at: datetime
    monotonic_ns: int = Field(ge=0)
    monotonic_elapsed_ns: int | None = Field(default=None, ge=0)
    writer_process_clock_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    entry_payload_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    utc_reversed: bool

    @field_validator("observed_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        return _utc(value, "visibility observed_at")


class JournalRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    entry: JournalEntry
    visibility: VisibilityReceipt | None


class ReceiptWriteResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    state: Literal[
        "created_visible",
        "recovered_visible",
        "reused_visible",
        "entry_committed_receipt_unavailable",
    ]
    entry_committed: Literal[True] = True
    entry: JournalEntry
    visibility: VisibilityReceipt | None
    receipt_error: ReceiptFailure | None = None


class _ClockSample(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    observed_at: datetime
    monotonic_ns: int = Field(ge=0)
    utc_reversed: bool

    @field_validator("observed_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        return _utc(value, "clock sample")


_ENTRY_COLUMNS = (
    "sequence",
    "idempotency_key",
    "payload_json",
    "payload_sha256",
    "precommit_observed_at",
    "precommit_monotonic_ns",
    "writer_process_clock_id",
    "utc_reversed",
)
_RECEIPT_COLUMNS = (
    "id",
    "entry_sequence",
    "kind",
    "observed_at",
    "monotonic_ns",
    "monotonic_elapsed_ns",
    "writer_process_clock_id",
    "entry_payload_sha256",
    "utc_reversed",
)
_CREATE_ENTRIES = """CREATE TABLE entries (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    idempotency_key TEXT NOT NULL UNIQUE,
    payload_json TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    precommit_observed_at TEXT NOT NULL,
    precommit_monotonic_ns INTEGER NOT NULL,
    writer_process_clock_id TEXT NOT NULL,
    utc_reversed INTEGER NOT NULL
)"""
_CREATE_VISIBILITY_RECEIPTS = """CREATE TABLE visibility_receipts (
    id TEXT PRIMARY KEY,
    entry_sequence INTEGER NOT NULL UNIQUE,
    kind TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    monotonic_ns INTEGER NOT NULL,
    monotonic_elapsed_ns INTEGER,
    writer_process_clock_id TEXT NOT NULL,
    entry_payload_sha256 TEXT NOT NULL,
    utc_reversed INTEGER NOT NULL,
    FOREIGN KEY(entry_sequence) REFERENCES entries(sequence)
)"""
_ENTRY_SCHEMA = (
    ("sequence", "INTEGER", 0, None, 1),
    ("idempotency_key", "TEXT", 1, None, 0),
    ("payload_json", "TEXT", 1, None, 0),
    ("payload_sha256", "TEXT", 1, None, 0),
    ("precommit_observed_at", "TEXT", 1, None, 0),
    ("precommit_monotonic_ns", "INTEGER", 1, None, 0),
    ("writer_process_clock_id", "TEXT", 1, None, 0),
    ("utc_reversed", "INTEGER", 1, None, 0),
)
_RECEIPT_SCHEMA = (
    ("id", "TEXT", 0, None, 1),
    ("entry_sequence", "INTEGER", 1, None, 0),
    ("kind", "TEXT", 1, None, 0),
    ("observed_at", "TEXT", 1, None, 0),
    ("monotonic_ns", "INTEGER", 1, None, 0),
    ("monotonic_elapsed_ns", "INTEGER", 0, None, 0),
    ("writer_process_clock_id", "TEXT", 1, None, 0),
    ("entry_payload_sha256", "TEXT", 1, None, 0),
    ("utc_reversed", "INTEGER", 1, None, 0),
)
_ENTRY_SELECT = f"""SELECT
    CASE WHEN typeof(sequence)='integer' THEN sequence END AS sequence,
    CASE WHEN typeof(idempotency_key)='text'
        AND length(CAST(idempotency_key AS BLOB))<=128
        THEN idempotency_key END AS idempotency_key,
    CASE WHEN typeof(payload_json)='text'
        AND length(CAST(payload_json AS BLOB))<={MAX_PAYLOAD_BYTES}
        THEN payload_json END AS payload_json,
    CASE WHEN typeof(payload_sha256)='text'
        AND length(CAST(payload_sha256 AS BLOB))=64
        THEN payload_sha256 END AS payload_sha256,
    CASE WHEN typeof(precommit_observed_at)='text'
        AND length(CAST(precommit_observed_at AS BLOB))<=64
        THEN precommit_observed_at END AS precommit_observed_at,
    CASE WHEN typeof(precommit_monotonic_ns)='integer'
        THEN precommit_monotonic_ns END AS precommit_monotonic_ns,
    CASE WHEN typeof(writer_process_clock_id)='text'
        AND length(CAST(writer_process_clock_id AS BLOB))=32
        THEN writer_process_clock_id END AS writer_process_clock_id,
    CASE WHEN typeof(utc_reversed)='integer'
        THEN utc_reversed END AS utc_reversed
    FROM entries"""
_RECEIPT_SELECT = """SELECT
    CASE WHEN typeof(id)='text' AND length(CAST(id AS BLOB))=64
        THEN id END AS id,
    CASE WHEN typeof(entry_sequence)='integer'
        THEN entry_sequence END AS entry_sequence,
    CASE WHEN typeof(kind)='text' AND length(CAST(kind AS BLOB))<=32
        THEN kind END AS kind,
    CASE WHEN typeof(observed_at)='text'
        AND length(CAST(observed_at AS BLOB))<=64
        THEN observed_at END AS observed_at,
    CASE WHEN typeof(monotonic_ns)='integer'
        THEN monotonic_ns END AS monotonic_ns,
    CASE WHEN monotonic_elapsed_ns IS NULL THEN NULL
        WHEN typeof(monotonic_elapsed_ns)='integer' THEN monotonic_elapsed_ns
        ELSE -1 END AS monotonic_elapsed_ns,
    CASE WHEN typeof(writer_process_clock_id)='text'
        AND length(CAST(writer_process_clock_id AS BLOB))=32
        THEN writer_process_clock_id END AS writer_process_clock_id,
    CASE WHEN typeof(entry_payload_sha256)='text'
        AND length(CAST(entry_payload_sha256 AS BLOB))=64
        THEN entry_payload_sha256 END AS entry_payload_sha256,
    CASE WHEN typeof(utc_reversed)='integer'
        THEN utc_reversed END AS utc_reversed
    FROM visibility_receipts"""


class ReceiptJournal:
    def __init__(
        self,
        path: Path,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        monotonic_ns: Callable[[], int] = time.monotonic_ns,
        _process_clock_id: str | None = None,
        _test_hook: _Hook | None = None,
    ) -> None:
        self.path = path.expanduser().absolute()
        self._clock = clock
        self._monotonic_ns = monotonic_ns
        self._process_clock_id = _process_clock_id or _default_process_clock_id()
        if not _valid_clock_id(self._process_clock_id):
            raise ValueError("Invalid process clock identifier.")
        self._owner_pid = os.getpid()
        self._test_hook = _test_hook
        self._clock_lock = Lock()
        self._last_utc: datetime | None = None
        self._last_monotonic_ns: int | None = None
        self._prepare_database()

    def append(
        self,
        idempotency_key: str,
        quote: ResearchQuote,
        fx: FxProvenanceResult,
    ) -> ReceiptWriteResult:
        self._refresh_process_identity()
        validated_quote = ResearchQuote.model_validate(quote.model_dump(mode="python"))
        validated_fx = FxProvenanceResult.model_validate(fx.model_dump(mode="python"))
        normalized_quote = validated_quote.model_copy(
            update={
                "market_at": _utc(validated_quote.market_at, "quote market_at"),
                "received_at": _utc(validated_quote.received_at, "quote received_at"),
            }
        )
        payload = ReceiptPayload(quote=normalized_quote, fx=validated_fx)
        key = _validate_key(idempotency_key)
        payload_bytes = _canonical(payload.model_dump(mode="json"))
        if len(payload_bytes) > MAX_PAYLOAD_BYTES:
            raise ValueError("Receipt payload exceeds 256 KiB.")
        payload_text = payload_bytes.decode()
        payload_sha256 = _sha256(payload_bytes)
        entry, created = self._commit_entry(key, payload_text, payload_sha256)
        if created:
            self._hook("after_entry_commit")
        try:
            record = self._read_record(key)
        except ReceiptIntegrityError:
            raise
        except ReceiptJournalError:
            return _receipt_unavailable(entry, "visibility_read_failed")
        if record is None:
            return _receipt_unavailable(entry, "visibility_read_failed")
        entry = record.entry
        if record.visibility is not None:
            return ReceiptWriteResult(
                state="reused_visible",
                entry=entry,
                visibility=record.visibility,
            )
        try:
            sample = self._sample_clock()
            elapsed = _elapsed(entry, sample, self._process_clock_id)
        except ReceiptClockError:
            return _receipt_unavailable(entry, "visibility_clock_invalid")
        kind: Literal["initial_visibility", "recovery_visibility"] = (
            "initial_visibility" if created else "recovery_visibility"
        )
        try:
            visibility, inserted = self._commit_visibility(entry, kind, sample, elapsed)
        except ReceiptIntegrityError:
            raise
        except ReceiptJournalError:
            return _receipt_unavailable(entry, "visibility_write_failed")
        state: Literal["created_visible", "recovered_visible", "reused_visible"]
        if not inserted:
            state = "reused_visible"
        elif kind == "initial_visibility":
            state = "created_visible"
        else:
            state = "recovered_visible"
        return ReceiptWriteResult(state=state, entry=entry, visibility=visibility)

    def read(self, idempotency_key: str) -> JournalRecord | None:
        return self._read_record(_validate_key(idempotency_key))

    def _prepare_database(self) -> None:
        if self.path.is_symlink():
            raise ForeignJournalError("Journal path must not be a symbolic link.")
        if self.path.exists():
            self._validate_existing_path()
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.parent / f".{self.path.name}.{uuid.uuid4().hex}.tmp"
        try:
            with closing(sqlite3.connect(temporary, timeout=0.1)) as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(f"PRAGMA application_id={APPLICATION_ID}")
                connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
                connection.executescript(
                    f"{_CREATE_ENTRIES};{_CREATE_VISIBILITY_RECEIPTS};"
                )
                connection.commit()
            _fsync_file(temporary)
            try:
                os.link(temporary, self.path)
            except FileExistsError:
                self._validate_existing_path()
            else:
                _fsync_directory(self.path.parent)
        except (OSError, sqlite3.Error) as exc:
            raise ForeignJournalError("Could not initialize receipt journal.") from exc
        finally:
            temporary.unlink(missing_ok=True)
        self._validate_existing_path()

    def _validate_existing_path(self) -> None:
        if self.path.is_symlink():
            raise ForeignJournalError("Journal path must not be a symbolic link.")
        try:
            with closing(_open_readonly(self.path)) as connection:
                _validate_schema(connection)
        except (OSError, sqlite3.Error, ReceiptIntegrityError) as exc:
            raise ForeignJournalError("Path is not an owned receipt journal.") from exc

    def _write_connection(self) -> sqlite3.Connection:
        connection: sqlite3.Connection | None = None
        try:
            if self.path.is_symlink():
                raise ForeignJournalError("Journal path must not be a symbolic link.")
            uri = self.path.resolve().as_uri() + "?mode=rw"
            connection = sqlite3.connect(uri, uri=True, timeout=0.1)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA busy_timeout=100")
            connection.execute("PRAGMA foreign_keys=ON")
            _validate_schema(connection)
            return connection
        except (OSError, sqlite3.Error, ReceiptIntegrityError) as exc:
            if connection is not None:
                connection.close()
            raise ForeignJournalError("Path is not an owned receipt journal.") from exc

    def _commit_entry(
        self, key: str, payload_text: str, payload_sha256: str
    ) -> tuple[JournalEntry, bool]:
        connection = self._write_connection()
        try:
            connection.execute("BEGIN IMMEDIATE")
            _validate_schema(connection)
            row = connection.execute(
                f"{_ENTRY_SELECT} WHERE idempotency_key=?", (key,)
            ).fetchone()
            if row is not None:
                entry = _entry(row)
                if (
                    entry.payload_sha256 != payload_sha256
                    or _canonical(entry.payload.model_dump(mode="json")).decode()
                    != payload_text
                ):
                    raise ReceiptConflictError(
                        "Idempotency key conflicts with existing payload."
                    )
                connection.commit()
                return entry, False
            sample = self._sample_clock()
            cursor = connection.execute(
                """INSERT INTO entries (
                    idempotency_key, payload_json, payload_sha256,
                    precommit_observed_at, precommit_monotonic_ns,
                    writer_process_clock_id, utc_reversed
                ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    key,
                    payload_text,
                    payload_sha256,
                    sample.observed_at.isoformat(),
                    sample.monotonic_ns,
                    self._process_clock_id,
                    int(sample.utc_reversed),
                ),
            )
            sequence = cursor.lastrowid
            if sequence is None:
                raise ReceiptJournalError("Entry sequence was not assigned.")
            entry = JournalEntry(
                sequence=sequence,
                idempotency_key=key,
                payload=ReceiptPayload.model_validate_json(payload_text),
                payload_sha256=payload_sha256,
                precommit_observed_at=sample.observed_at,
                precommit_monotonic_ns=sample.monotonic_ns,
                writer_process_clock_id=self._process_clock_id,
                utc_reversed=sample.utc_reversed,
            )
            self._hook("before_entry_commit")
            connection.commit()
            return entry, True
        except (ReceiptJournalError, ValueError):
            connection.rollback()
            raise
        except (OSError, sqlite3.Error) as exc:
            connection.rollback()
            raise ReceiptJournalError("Entry write failed.") from exc
        finally:
            connection.close()

    def _read_record(self, key: str) -> JournalRecord | None:
        try:
            with closing(_open_readonly(self.path)) as connection:
                connection.execute("BEGIN")
                _validate_schema(connection)
                row = connection.execute(
                    f"{_ENTRY_SELECT} WHERE idempotency_key=?", (key,)
                ).fetchone()
                if row is None:
                    return None
                entry = _entry(row)
                receipt_row = connection.execute(
                    f"{_RECEIPT_SELECT} WHERE entry_sequence=?",
                    (entry.sequence,),
                ).fetchone()
                visibility = _visibility(receipt_row) if receipt_row else None
                if visibility is not None:
                    _validate_relationship(entry, visibility)
                return JournalRecord(entry=entry, visibility=visibility)
        except ReceiptIntegrityError:
            raise
        except (OSError, sqlite3.Error, ValueError) as exc:
            raise ReceiptJournalError("Journal read failed.") from exc

    def _commit_visibility(
        self,
        entry: JournalEntry,
        kind: Literal["initial_visibility", "recovery_visibility"],
        sample: _ClockSample,
        elapsed: int | None,
    ) -> tuple[VisibilityReceipt, bool]:
        receipt_content = {
            "entry_sequence": entry.sequence,
            "kind": kind,
            "observed_at": sample.observed_at.isoformat(),
            "monotonic_ns": sample.monotonic_ns,
            "monotonic_elapsed_ns": elapsed,
            "writer_process_clock_id": self._process_clock_id,
            "entry_payload_sha256": entry.payload_sha256,
            "utc_reversed": sample.observed_at < entry.precommit_observed_at,
        }
        receipt_id = _sha256(_canonical(receipt_content))
        receipt = VisibilityReceipt(id=receipt_id, **receipt_content)
        connection = self._write_connection()
        try:
            connection.execute("BEGIN IMMEDIATE")
            _validate_schema(connection)
            existing = connection.execute(
                f"{_RECEIPT_SELECT} WHERE entry_sequence=?",
                (entry.sequence,),
            ).fetchone()
            if existing is not None:
                visibility = _visibility(existing)
                _validate_relationship(entry, visibility)
                connection.commit()
                return visibility, False
            connection.execute(
                """INSERT INTO visibility_receipts VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    receipt.id,
                    receipt.entry_sequence,
                    receipt.kind,
                    receipt.observed_at.isoformat(),
                    receipt.monotonic_ns,
                    receipt.monotonic_elapsed_ns,
                    receipt.writer_process_clock_id,
                    receipt.entry_payload_sha256,
                    int(receipt.utc_reversed),
                ),
            )
            self._hook("before_visibility_commit")
            connection.commit()
        except ReceiptJournalError:
            connection.rollback()
            raise
        except (OSError, sqlite3.Error, ValueError) as exc:
            connection.rollback()
            raise ReceiptJournalError("Visibility write failed.") from exc
        finally:
            connection.close()
        self._hook("after_visibility_commit")
        return receipt, True

    def _sample_clock(self) -> _ClockSample:
        with self._clock_lock:
            try:
                observed = _utc(self._clock(), "journal clock")
                monotonic = self._monotonic_ns()
            except (TypeError, ValueError) as exc:
                raise ReceiptClockError("Journal clock sample is invalid.") from exc
            if type(monotonic) is not int or monotonic < 0:
                raise ReceiptClockError("Journal monotonic clock is invalid.")
            if (
                self._last_monotonic_ns is not None
                and monotonic < self._last_monotonic_ns
            ):
                raise ReceiptClockError("Journal monotonic clock moved backward.")
            reversed_utc = self._last_utc is not None and observed < self._last_utc
            self._last_utc = observed
            self._last_monotonic_ns = monotonic
            return _ClockSample(
                observed_at=observed,
                monotonic_ns=monotonic,
                utc_reversed=reversed_utc,
            )

    def _refresh_process_identity(self) -> None:
        current_pid = os.getpid()
        if current_pid == self._owner_pid:
            return
        self._owner_pid = current_pid
        self._process_clock_id = _default_process_clock_id()
        self._clock_lock = Lock()
        self._last_utc = None
        self._last_monotonic_ns = None

    def _hook(self, point: str) -> None:
        if self._test_hook is not None:
            self._test_hook(point)


def _validate_key(value: str) -> str:
    if not isinstance(value, str) or _IDEMPOTENCY_KEY.fullmatch(value) is None:
        raise ValueError("Invalid idempotency key.")
    return value


def _entry(row: sqlite3.Row) -> JournalEntry:
    try:
        payload_text = row["payload_json"]
        if not isinstance(payload_text, str):
            raise ValueError("Entry payload is not text.")
        payload_bytes = payload_text.encode()
        if len(payload_bytes) > MAX_PAYLOAD_BYTES:
            raise ValueError("Entry payload is oversized.")
        payload = ReceiptPayload.model_validate_json(payload_bytes)
        if _canonical(payload.model_dump(mode="json")) != payload_bytes:
            raise ValueError("Entry payload is not canonical.")
        if _sha256(payload_bytes) != row["payload_sha256"]:
            raise ValueError("Entry payload hash mismatch.")
        utc_reversed = _stored_bool(row["utc_reversed"])
        return JournalEntry(
            sequence=row["sequence"],
            idempotency_key=row["idempotency_key"],
            payload=payload,
            payload_sha256=row["payload_sha256"],
            precommit_observed_at=row["precommit_observed_at"],
            precommit_monotonic_ns=row["precommit_monotonic_ns"],
            writer_process_clock_id=row["writer_process_clock_id"],
            utc_reversed=utc_reversed,
        )
    except (KeyError, RecursionError, TypeError, ValueError) as exc:
        raise ReceiptIntegrityError("Stored receipt entry is invalid.") from exc


def _visibility(row: sqlite3.Row) -> VisibilityReceipt:
    try:
        content = {
            "entry_sequence": row["entry_sequence"],
            "kind": row["kind"],
            "observed_at": _utc(
                datetime.fromisoformat(row["observed_at"]), "visibility observed_at"
            ).isoformat(),
            "monotonic_ns": row["monotonic_ns"],
            "monotonic_elapsed_ns": row["monotonic_elapsed_ns"],
            "writer_process_clock_id": row["writer_process_clock_id"],
            "entry_payload_sha256": row["entry_payload_sha256"],
            "utc_reversed": _stored_bool(row["utc_reversed"]),
        }
        expected_id = _sha256(_canonical(content))
        if row["id"] != expected_id:
            raise ValueError("Visibility receipt hash mismatch.")
        return VisibilityReceipt(id=expected_id, **content)
    except (KeyError, TypeError, ValueError) as exc:
        raise ReceiptIntegrityError("Stored visibility receipt is invalid.") from exc


def _stored_bool(value: object) -> bool:
    if value not in (0, 1) or isinstance(value, bool):
        raise ValueError("Stored boolean is invalid.")
    return bool(value)


def _elapsed(
    entry: JournalEntry, sample: _ClockSample, process_clock_id: str
) -> int | None:
    if entry.writer_process_clock_id != process_clock_id:
        return None
    if sample.monotonic_ns < entry.precommit_monotonic_ns:
        raise ReceiptClockError("Journal monotonic interval is invalid.")
    return sample.monotonic_ns - entry.precommit_monotonic_ns


def _validate_relationship(entry: JournalEntry, visibility: VisibilityReceipt) -> None:
    if visibility.entry_sequence != entry.sequence:
        raise ReceiptIntegrityError("Visibility receipt sequence mismatch.")
    if visibility.entry_payload_sha256 != entry.payload_sha256:
        raise ReceiptIntegrityError("Visibility receipt payload mismatch.")
    same_clock = visibility.writer_process_clock_id == entry.writer_process_clock_id
    if same_clock:
        if visibility.monotonic_ns < entry.precommit_monotonic_ns:
            raise ReceiptIntegrityError("Visibility monotonic interval is negative.")
        expected_elapsed = visibility.monotonic_ns - entry.precommit_monotonic_ns
        if visibility.monotonic_elapsed_ns != expected_elapsed:
            raise ReceiptIntegrityError("Visibility monotonic interval mismatch.")
    elif visibility.monotonic_elapsed_ns is not None:
        raise ReceiptIntegrityError("Cross-process monotonic interval is invalid.")
    expected_utc_reversed = visibility.observed_at < entry.precommit_observed_at
    if visibility.utc_reversed != expected_utc_reversed:
        raise ReceiptIntegrityError("Visibility UTC reversal flag mismatch.")


def _receipt_unavailable(
    entry: JournalEntry, reason: ReceiptFailure
) -> ReceiptWriteResult:
    return ReceiptWriteResult(
        state="entry_committed_receipt_unavailable",
        entry=entry,
        visibility=None,
        receipt_error=reason,
    )


def _valid_clock_id(value: str) -> bool:
    return len(value) == 32 and all(
        character in "0123456789abcdef" for character in value
    )


def _default_process_clock_id() -> str:
    process = str(os.getpid()).encode()
    return hashlib.sha256(_PROCESS_CLOCK_SEED + b"\0" + process).hexdigest()[:32]


def _open_readonly(path: Path) -> sqlite3.Connection:
    uri = path.resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True, timeout=0.1)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    connection.execute("PRAGMA busy_timeout=100")
    return connection


def _validate_schema(connection: sqlite3.Connection) -> None:
    application_id = int(connection.execute("PRAGMA application_id").fetchone()[0])
    user_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if application_id != APPLICATION_ID or user_version != SCHEMA_VERSION:
        raise ReceiptIntegrityError("Receipt journal marker mismatch.")
    table_rows = connection.execute(
        """SELECT CASE WHEN length(CAST(name AS BLOB))<=64 THEN name END
        FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'
        LIMIT 4"""
    ).fetchall()
    tables = {str(row[0]) for row in table_rows if row[0] is not None}
    if len(table_rows) != 2 or tables != {"entries", "visibility_receipts"}:
        raise ReceiptIntegrityError("Receipt journal table set mismatch.")
    definitions = {
        str(row[0]): str(row[1])
        for row in connection.execute(
            """SELECT name,
            CASE WHEN length(CAST(sql AS BLOB))<=4096 THEN sql END
            FROM sqlite_master WHERE type='table'
            AND name IN ('entries','visibility_receipts')"""
        ).fetchall()
        if row[0] is not None and row[1] is not None
    }
    if {
        name: _normalized_sql(statement) for name, statement in definitions.items()
    } != {
        "entries": _normalized_sql(_CREATE_ENTRIES),
        "visibility_receipts": _normalized_sql(_CREATE_VISIBILITY_RECEIPTS),
    }:
        raise ReceiptIntegrityError("Receipt journal definition mismatch.")
    extra_objects = int(
        connection.execute(
            """SELECT count(*) FROM sqlite_master WHERE
            type IN ('trigger','view') OR (type='index' AND sql IS NOT NULL)"""
        ).fetchone()[0]
    )
    if extra_objects:
        raise ReceiptIntegrityError("Receipt journal has unexpected objects.")
    for table, expected_columns, expected_schema in (
        ("entries", _ENTRY_COLUMNS, _ENTRY_SCHEMA),
        (
            "visibility_receipts",
            _RECEIPT_COLUMNS,
            _RECEIPT_SCHEMA,
        ),
    ):
        column_rows = connection.execute(
            f"""SELECT
            CASE WHEN length(CAST(name AS BLOB))<=64 THEN name END
                AS name,
            CASE WHEN length(CAST(type AS BLOB))<=32 THEN type END
                AS type,
            "notnull", dflt_value, pk
            FROM pragma_table_info('{table}') LIMIT 10"""
        ).fetchall()
        columns = tuple(str(row[0]) for row in column_rows if row[0] is not None)
        schema = tuple(
            (
                str(row[0]),
                str(row[1]),
                int(row[2]),
                row[3],
                int(row[4]),
            )
            for row in column_rows
            if row[0] is not None and row[1] is not None
        )
        if (
            len(column_rows) != len(expected_columns)
            or columns != expected_columns
            or schema != expected_schema
        ):
            raise ReceiptIntegrityError("Receipt journal schema mismatch.")
    _validate_indexes(connection, "entries", {("u", ("idempotency_key",))})
    _validate_indexes(
        connection,
        "visibility_receipts",
        {("pk", ("id",)), ("u", ("entry_sequence",))},
    )
    entry_foreign_keys = connection.execute(
        "SELECT count(*) FROM pragma_foreign_key_list('entries')"
    ).fetchone()[0]
    receipt_foreign_keys = connection.execute(
        """SELECT "table", "from", "to", on_update, on_delete, match
        FROM pragma_foreign_key_list('visibility_receipts')"""
    ).fetchall()
    if entry_foreign_keys != 0 or [tuple(row) for row in receipt_foreign_keys] != [
        (
            "entries",
            "entry_sequence",
            "sequence",
            "NO ACTION",
            "NO ACTION",
            "NONE",
        )
    ]:
        raise ReceiptIntegrityError("Receipt journal foreign key mismatch.")
    if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise ReceiptIntegrityError("Receipt journal foreign key integrity failed.")


def _validate_indexes(
    connection: sqlite3.Connection,
    table: str,
    expected: set[tuple[str, tuple[str, ...]]],
) -> None:
    rows = connection.execute(
        f"""SELECT
        CASE WHEN length(CAST(name AS BLOB))<=128 THEN name END,
        "unique", origin, partial
        FROM pragma_index_list('{table}') LIMIT 4"""
    ).fetchall()
    actual: set[tuple[str, tuple[str, ...]]] = set()
    for row in rows:
        if row[0] is None or int(row[1]) != 1 or int(row[3]) != 0:
            raise ReceiptIntegrityError("Receipt journal index mismatch.")
        index_rows = connection.execute(
            """SELECT CASE WHEN length(CAST(name AS BLOB))<=64 THEN name END
            FROM pragma_index_info(?) LIMIT 3""",
            (str(row[0]),),
        ).fetchall()
        columns = tuple(
            str(index_row[0]) for index_row in index_rows if index_row[0] is not None
        )
        if len(columns) != len(index_rows):
            raise ReceiptIntegrityError("Receipt journal index mismatch.")
        actual.add((str(row[2]), columns))
    if actual != expected or len(rows) != len(expected):
        raise ReceiptIntegrityError("Receipt journal index mismatch.")


def _normalized_sql(value: str) -> str:
    return " ".join(value.split())


def _fsync_file(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
