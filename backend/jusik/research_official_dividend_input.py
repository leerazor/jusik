"""Freeze reviewed official cash dividends as isolated, retrospective inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import stat
import sys
from contextlib import closing
from datetime import date
from decimal import Decimal, Inexact, localcontext
from pathlib import Path
from typing import Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    ValidationError,
    model_validator,
)

from jusik.approved_universe import (
    ApprovedInstrument,
    ApprovedUniverseSnapshot,
    ApprovedUniverseStore,
)
from jusik.research_action_review import (
    MAX_EVIDENCE_BYTES,
    MAX_MANIFEST_BYTES,
    EvidenceInput,
    ExtractedFacts,
    compare_review,
)

MAX_EVENTS = 100
MAX_JSON_BYTES = 16 * 1024
SHA = r"^[a-f0-9]{64}$"


def _json(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key.")
        result[key] = value
    return result


def _read(path: Path, limit: int) -> bytes:
    if not path.is_absolute() or any(
        part.is_symlink() for part in (path, *path.parents)
    ):
        raise ValueError("Unsafe input path.")
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
        raise ValueError("Input is not a bounded regular file.")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        opened = os.fstat(fd)
        if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (
            before.st_dev,
            before.st_ino,
        ):
            raise ValueError("Input changed while opening.")
        body = bytearray()
        while len(body) <= limit:
            chunk = os.read(fd, limit + 1 - len(body))
            if not chunk:
                break
            body.extend(chunk)
        if len(body) > limit or os.fstat(fd).st_size != len(body):
            raise ValueError("Input changed or exceeded limit.")
        return bytes(body)
    finally:
        os.close(fd)


class Identity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    issuer: str = Field(min_length=1, max_length=200)
    security_type: str = Field(min_length=1, max_length=100)
    share_class: str = Field(min_length=1, max_length=100)
    operator_verified: Literal[True]
    evidence: EvidenceInput

    @model_validator(mode="after")
    def meaningful(self) -> Self:
        if any(
            not value.strip()
            for value in (self.issuer, self.security_type, self.share_class)
        ):
            raise ValueError("Identity strings must be meaningful.")
        return self


class Event(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    market: Literal["KR", "US"]
    exchange: Literal["KRX", "NAS", "NYS", "AMS"]
    symbol: str
    event_id: str = Field(pattern=SHA)
    revision_id: str = Field(pattern=SHA)
    content_sha256: str = Field(pattern=SHA)
    review_id: str = Field(pattern=SHA)
    identity: Identity

    @model_validator(mode="after")
    def normalized(self) -> Self:
        instrument = ApprovedInstrument(
            market=self.market, exchange=self.exchange, symbol=self.symbol
        )
        if instrument.symbol != self.symbol:
            raise ValueError("Symbol must be normalized.")
        return self


class Manifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal[1]
    approved_revision: StrictInt = Field(ge=0)
    events: list[Event] = Field(min_length=1, max_length=MAX_EVENTS)

    @model_validator(mode="after")
    def unique_events(self) -> Self:
        keys = [item.event_id for item in self.events]
        if len(keys) != len(set(keys)):
            raise ValueError("Duplicate event.")
        return self


def _open_db(path: Path) -> sqlite3.Connection:
    if not path.is_absolute() or any(
        part.is_symlink() for part in (path, *path.parents)
    ):
        raise ValueError("Unsafe database path.")
    if not stat.S_ISREG(path.stat().st_mode):
        raise ValueError("Database must exist as a regular file.")
    db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=0.1)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA query_only=ON")
    db.execute("BEGIN")
    return db


def _registry(db: sqlite3.Connection) -> tuple[ApprovedUniverseSnapshot, str]:
    row = db.execute(
        "SELECT revision, updated_at, instruments_json "
        "FROM approved_universe WHERE id=1"
    ).fetchone()
    if row is None or len(str(row["instruments_json"]).encode()) > 128 * 1024:
        raise ValueError("Approved registry missing or oversized.")
    snapshot = ApprovedUniverseStore._snapshot(row)
    if len(snapshot.instruments) > MAX_EVENTS:
        raise ValueError("Approved registry exceeds limit.")
    return snapshot, _sha(_json(snapshot.model_dump(mode="json")))


def _object(raw: str) -> dict[str, object]:
    if len(raw.encode()) > MAX_JSON_BYTES:
        raise ValueError("Stored JSON exceeds limit.")
    value = json.loads(raw, object_pairs_hook=_unique)
    if not isinstance(value, dict):
        raise TypeError("Stored JSON must be an object.")
    return value


def _record(db: sqlite3.Connection, item: Event) -> dict[str, object]:
    row = db.execute(
        """SELECT e.provider, e.symbol, e.kind, e.provider_key, e.vendor_date,
        e.observation_state, e.latest_revision_sequence, e.latest_content_sha256,
        r.id AS revision_id, r.sequence AS revision_sequence, r.content_sha256,
        r.payload_json, r.first_seen_at, v.id AS review_id, v.review_key,
        v.sequence AS review_sequence, v.source_content_sha256, v.evidence_id,
        v.locator, v.extracted_facts_json, v.comparison_status,
        v.compared_fields_json, v.content_sha256 AS review_content_sha256,
        v.reviewed_at, d.sha256 AS evidence_sha256, d.source_url,
        d.publisher, d.captured_at, length(d.body) AS evidence_size
        FROM action_collection_events e
        JOIN action_collection_revisions r ON r.event_id=e.id
            AND r.sequence=e.latest_revision_sequence
        JOIN action_reviews v ON v.id=(SELECT id FROM action_reviews
            WHERE revision_id=r.id ORDER BY sequence DESC LIMIT 1)
        JOIN action_review_evidence d ON d.id=v.evidence_id
        WHERE e.id=? LIMIT 1""",
        (item.event_id,),
    ).fetchone()
    if row is None or any(
        (
            row["provider"] != "Yahoo chart",
            row["kind"] != "dividend",
            row["symbol"] != item.symbol,
            row["revision_id"] != item.revision_id,
            row["content_sha256"] != item.content_sha256,
            row["latest_content_sha256"] != item.content_sha256,
            row["review_id"] != item.review_id,
            row["source_content_sha256"] != item.content_sha256,
            row["revision_sequence"] != row["latest_revision_sequence"],
        )
    ):
        raise ValueError("Event, current revision, or latest review pin mismatch.")
    raw = str(row["payload_json"])
    if _sha(raw.encode()) != item.content_sha256:
        raise ValueError("Stored source payload hash mismatch.")
    payload = _object(raw)
    facts = ExtractedFacts.model_validate(_object(str(row["extracted_facts_json"])))
    if (
        facts.amount is None
        or facts.currency is None
        or facts.ex_dividend_date is None
        or facts.payment_date is None
        or facts.comparable_share_basis is not True
        or facts.payment_date < facts.ex_dividend_date
    ):
        raise ValueError("Required official dividend fact missing or inconsistent.")
    if (
        not isinstance(row["evidence_size"], int)
        or not 0 < row["evidence_size"] <= MAX_EVIDENCE_BYTES
    ):
        raise ValueError("Official evidence missing or oversized.")
    evidence_row = db.execute(
        "SELECT body FROM action_review_evidence WHERE id=? AND length(body)<=?",
        (row["evidence_id"], MAX_EVIDENCE_BYTES),
    ).fetchone()
    if (
        evidence_row is None
        or _sha(bytes(evidence_row["body"])) != row["evidence_sha256"]
        or row["evidence_id"] != row["evidence_sha256"]
    ):
        raise ValueError("Official evidence hash mismatch.")
    evidence = EvidenceInput.model_validate(
        {
            "local_file": "/stored/official-evidence",
            "sha256": row["evidence_sha256"],
            "source_url": row["source_url"],
            "publisher": row["publisher"],
            "locator": row["locator"],
            "captured_at": row["captured_at"],
        }
    )
    review_content = {
        "revision_id": item.revision_id,
        "content_sha256": item.content_sha256,
        "operator_verified": True,
        "evidence": evidence.model_dump(mode="json", exclude={"local_file", "locator"}),
        "locator": evidence.locator,
        "extracted_facts": facts.model_dump(mode="json"),
    }
    review_hash = _sha(_json(review_content))
    if (
        review_hash != row["review_content_sha256"]
        or _sha(_json({"review_key": row["review_key"], "content": review_hash}))
        != item.review_id
    ):
        raise ValueError("Stored review content hash mismatch.")
    comparison, fields = compare_review("dividend", payload, facts)
    stored_fields = json.loads(
        str(row["compared_fields_json"]), object_pairs_hook=_unique
    )
    if comparison != row["comparison_status"] or stored_fields != [
        field.model_dump(mode="json") for field in fields
    ]:
        raise ValueError("Stored comparison mismatch.")
    if any(
        field.status != "matched"
        and (field.field != "amount" or field.status != "mismatched")
        for field in fields
    ):
        raise ValueError("Only vendor amount mismatch is accepted.")
    vendor = payload.get("amount")
    if not isinstance(vendor, str):
        raise TypeError("Vendor amount missing.")
    vendor = ExtractedFacts(amount=vendor).amount
    assert vendor is not None
    if (
        payload.get("currency") != facts.currency
        or payload.get("vendor_date") != facts.ex_dividend_date.isoformat()
    ):
        raise ValueError("Source currency or ex-date mismatch.")
    with localcontext() as context:
        context.prec = 256
        context.traps[Inexact] = True
        delta = format(Decimal(facts.amount) - Decimal(vendor), "f")
    return {
        "instrument": {
            "market": item.market,
            "exchange": item.exchange,
            "symbol": item.symbol,
        },
        "identity": {
            "issuer": item.identity.issuer,
            "security_type": item.identity.security_type,
            "share_class": item.identity.share_class,
            "operator_verified": True,
            "evidence": item.identity.evidence.model_dump(
                mode="json", exclude={"local_file"}
            ),
        },
        "source": {
            "event_id": item.event_id,
            "provider": row["provider"],
            "provider_key": row["provider_key"],
            "revision_id": item.revision_id,
            "revision_sequence": row["revision_sequence"],
            "content_sha256": item.content_sha256,
            "first_seen_at": row["first_seen_at"],
            "vendor_date": row["vendor_date"],
            "observation_state": row["observation_state"],
            "vendor_amount": vendor,
            "currency": payload["currency"],
        },
        "official": {
            "review_id": item.review_id,
            "review_sequence": row["review_sequence"],
            "reviewed_at": row["reviewed_at"],
            "review_status": comparison,
            "evidence": evidence.model_dump(mode="json", exclude={"local_file"}),
            "facts": facts.model_dump(mode="json"),
            "amount": facts.amount,
            "amount_delta_official_minus_vendor": delta,
            "source_conflict_status": "amount_mismatch"
            if comparison == "mismatched"
            else "matched",
        },
    }


def freeze(
    approved_db: Path, action_db: Path, manifest_path: Path, out_dir: Path
) -> Path:
    manifest = Manifest.model_validate(
        json.loads(_read(manifest_path, MAX_MANIFEST_BYTES), object_pairs_hook=_unique)
    )
    with (
        closing(_open_db(approved_db)) as registry_db,
        closing(_open_db(action_db)) as action_connection,
    ):
        snapshot, registry_hash = _registry(registry_db)
        if snapshot.revision != manifest.approved_revision:
            raise ValueError("Approved registry revision changed.")
        approved = {(i.market, i.exchange, i.symbol) for i in snapshot.instruments}
        records: list[dict[str, object]] = []
        seen_dates: set[tuple[str, str, str, date]] = set()
        for item in manifest.events:
            if (item.market, item.exchange, item.symbol) not in approved:
                raise ValueError("Instrument outside approved registry.")
            identity_body = _read(item.identity.evidence.local_file, MAX_EVIDENCE_BYTES)
            if (
                not identity_body
                or _sha(identity_body) != item.identity.evidence.sha256
            ):
                raise ValueError("Identity evidence hash mismatch.")
            record = _record(action_connection, item)
            official = record["official"]
            assert isinstance(official, dict)
            facts = official["facts"]
            assert isinstance(facts, dict)
            key = (
                item.market,
                item.exchange,
                item.symbol,
                date.fromisoformat(str(facts["ex_dividend_date"])),
            )
            if key in seen_dates:
                raise ValueError("Duplicate instrument and ex-date.")
            seen_dates.add(key)
            records.append(record)
        if _registry(registry_db)[1] != registry_hash:
            raise ValueError("Approved registry changed during validation.")
        for item, record in zip(manifest.events, records, strict=True):
            if _record(action_connection, item) != record:
                raise ValueError("Action evidence changed during validation.")
    # Reopen both databases to catch a changed revision or registration after the
    # first read transaction. Cross-database atomicity still requires copied DBs.
    with (
        closing(_open_db(approved_db)) as registry_db,
        closing(_open_db(action_db)) as action_connection,
    ):
        if _registry(registry_db)[1] != registry_hash:
            raise ValueError("Approved registry changed after validation.")
        for item, record in zip(manifest.events, records, strict=True):
            if _record(action_connection, item) != record:
                raise ValueError("Action review changed after validation.")
    records.sort(
        key=lambda record: (
            str(record["instrument"]),
            str(record["source"]),
        )
    )
    artifact = {
        "schema_version": 1,
        "kind": "official_cash_dividend_input",
        "approved_registry": {
            "snapshot": snapshot.model_dump(mode="json"),
            "sha256": registry_hash,
        },
        "events": records,
        "retrospective": True,
        "historical_pit_verified": False,
        "automatic_ledger_application": False,
        "nav_ready": False,
    }
    body = _json(artifact) + b"\n"
    digest = _sha(body)
    if (
        not out_dir.is_absolute()
        or not out_dir.is_dir()
        or any(p.is_symlink() for p in (out_dir, *out_dir.parents))
    ):
        raise ValueError("Output directory must exist and be safe.")
    destination = out_dir / f"official-dividend-input-{digest}.json"
    try:
        fd = os.open(
            destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
        )
    except FileExistsError:
        if _read(destination, len(body)) != body:
            raise ValueError("Existing artifact differs.") from None
        return destination
    with os.fdopen(fd, "wb") as target:
        target.write(body)
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Freeze reviewed official cash dividends"
    )
    parser.add_argument("--approved-db", type=Path, required=True)
    parser.add_argument("--action-db", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        output = freeze(args.approved_db, args.action_db, args.manifest, args.out_dir)
    except (OSError, sqlite3.Error, ValidationError, ValueError, KeyError, TypeError):
        print("official dividend input validation failed", file=sys.stderr)
        return 1
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
