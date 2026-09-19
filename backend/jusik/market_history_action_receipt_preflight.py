"""Audit fixed action-collection receipts and review provenance offline.

The preflight is deliberately a read-only provenance check.  It does not
collect data, create an accounting state, or replay an empty artifact.  A
receipt is the raw body saved on an action collection attempt; a review
database is linked to the collection database by its natural action key and
payload hash, never by a revision id alone.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Final, Literal, cast

from pydantic import ValidationError

from jusik.market_history_action_artifact import (
    SCHEMA_VERSION as ARTIFACT_SCHEMA_VERSION,
)
from jusik.market_history_action_artifact import (
    ArtifactError,
    _check_path_components,
)
from jusik.research_action_collection import CollectionError, parse_action_response
from jusik.research_action_collection_models import CollectedAction
from jusik.research_action_review import EvidenceInput, ExtractedFacts, compare_review
from jusik.research_universe_data import REGISTRY

SCHEMA_VERSION: Final = 1
MAX_DATABASE_BYTES: Final = 8 * 1024 * 1024
MAX_ATTEMPTS: Final = 256
MAX_EVENTS: Final = 128
MAX_REVISIONS: Final = 256
MAX_EVIDENCE: Final = 16
MAX_REVIEWS: Final = 128
MAX_BODY_BYTES: Final = 4 * 1024 * 1024
MAX_OUTPUT_BYTES: Final = 50 * 1024 * 1024
PROVIDER: Final = "Yahoo chart"
ARTIFACT_REQUIRED_FIELDS: Final = (
    "schema_version",
    "seed",
    "initial_state",
    "steps",
)
ARTIFACT_MISSING_FIELDS: Final = (
    "initial_state",
    "steps",
    "effective_utc_boundary",
    "price_inputs",
    "entitlement_inputs",
)
COLLECTION_DB_SHA256: Final = (
    "838715af71cc1f16c1367779a7a010db1ab99a613cd6f605a7757c854a6594ae"
)
REVIEW_DB_SHA256: Final = (
    "873c644d8fff74c9dd3c34880e30d054a2811e480214abfb904a56df94139a06"
)
EXPECTED_SIZES: Final = {
    COLLECTION_DB_SHA256: 835584,
    REVIEW_DB_SHA256: 1966080,
}
EXPECTED_ROWS: Final = {
    COLLECTION_DB_SHA256: {
        "action_collection_attempts": 128,
        "action_collection_source_status": 16,
        "action_collection_events": 12,
        "action_collection_revisions": 14,
    },
    REVIEW_DB_SHA256: {
        "action_collection_attempts": 32,
        "action_collection_source_status": 16,
        "action_collection_events": 109,
        "action_collection_revisions": 109,
        "action_review_evidence": 3,
        "action_reviews": 6,
    },
}

CollectionTable = Literal[
    "action_collection_attempts",
    "action_collection_source_status",
    "action_collection_events",
    "action_collection_revisions",
]
ReviewTable = CollectionTable | Literal["action_review_evidence", "action_reviews"]

TABLE_COLUMNS: Final[dict[str, tuple[str, ...]]] = {
    "action_collection_attempts": (
        "id",
        "symbol",
        "requested_start",
        "requested_end",
        "started_at",
        "completed_at",
        "state",
        "http_status",
        "request_url",
        "body_sha256",
        "body",
        "error_code",
        "next_due_at",
    ),
    "action_collection_source_status": (
        "symbol",
        "yahoo_symbol",
        "state",
        "last_attempt_at",
        "last_success_at",
        "next_due_at",
        "error_code",
        "requested_start",
        "requested_end",
        "latest_attempt_id",
    ),
    "action_collection_events": (
        "id",
        "provider",
        "symbol",
        "kind",
        "provider_key",
        "vendor_date",
        "first_seen_at",
        "last_seen_at",
        "observation_state",
        "latest_revision_sequence",
        "latest_content_sha256",
    ),
    "action_collection_revisions": (
        "id",
        "event_id",
        "sequence",
        "content_sha256",
        "first_seen_at",
        "attempt_id",
        "payload_json",
    ),
    "action_review_evidence": (
        "id",
        "sha256",
        "source_url",
        "publisher",
        "captured_at",
        "body",
        "created_at",
    ),
    "action_reviews": (
        "id",
        "review_key",
        "revision_id",
        "sequence",
        "source_content_sha256",
        "evidence_id",
        "locator",
        "extracted_facts_json",
        "comparison_status",
        "compared_fields_json",
        "content_sha256",
        "reviewed_at",
        "imported_at",
    ),
}


class PreflightError(ValueError):
    """The fixed provenance input is malformed or changed."""


def _reject_constant(value: str) -> None:
    raise ValueError(f"JSON constant is unsupported: {value}")


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _json(raw: bytes | str, label: str) -> object:
    try:
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        return json.loads(
            text,
            object_pairs_hook=_unique_pairs,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise PreflightError(f"{label} is not strict JSON") from exc


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise PreflightError("value is not canonical JSON") from exc


def _hash_object(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _sha256_file(path: Path) -> tuple[str, int]:
    try:
        stat_result = path.stat()
    except OSError as exc:
        raise PreflightError("database is unavailable") from exc
    if not path.is_file() or path.is_symlink():
        raise PreflightError("database must be a regular file")
    if stat_result.st_nlink != 1:
        raise PreflightError("database hardlink alias is rejected")
    if stat_result.st_size > MAX_DATABASE_BYTES:
        raise PreflightError("database exceeds the byte cap")
    digest = hashlib.sha256()
    try:
        with path.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
    except OSError as exc:
        raise PreflightError("database cannot be read") from exc
    return digest.hexdigest(), stat_result.st_size


def _check_path(path: Path) -> Path:
    absolute = path.absolute()
    current = absolute
    while current.parent != current:
        if current.is_symlink():
            raise PreflightError("database path contains a symlink")
        current = current.parent
    for suffix in ("-wal", "-shm", "-journal"):
        if absolute.with_name(absolute.name + suffix).exists():
            raise PreflightError("database sidecar is present")
    return absolute


def _connect(path: Path) -> sqlite3.Connection:
    # immutable prevents SQLite from creating a journal/WAL sidecar while this
    # audit is running.  The file was hashed and sidecars were checked first.
    uri = f"file:{path}?mode=ro&immutable=1"
    try:
        connection = sqlite3.connect(uri, uri=True, timeout=0.1)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        return connection
    except sqlite3.Error as exc:
        raise PreflightError("database cannot be opened read-only") from exc


def _read_snapshot(
    path: Path,
    *,
    tables: set[str],
    caps: Mapping[str, int],
    expected_sha256: str | None,
) -> tuple[dict[str, list[dict[str, object]]], dict[str, object]]:
    absolute = _check_path(path)
    before_sha, before_size = _sha256_file(absolute)
    if expected_sha256 is not None and before_sha != expected_sha256:
        raise PreflightError("database SHA-256 does not match the fixed manifest")
    connection = _connect(absolute)
    try:
        names = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        if names != tables:
            raise PreflightError("database table allowlist mismatch")
        result: dict[str, list[dict[str, object]]] = {}
        counts: dict[str, int] = {}
        for table in sorted(tables):
            actual_columns = tuple(
                str(row[1])
                for row in connection.execute(f'PRAGMA table_info("{table}")')
            )
            if actual_columns != TABLE_COLUMNS[table]:
                raise PreflightError(f"{table} column contract mismatch")
            rows = connection.execute(f'SELECT * FROM "{table}"').fetchall()
            cap = caps[table]
            if len(rows) > cap:
                raise PreflightError(f"{table} row cap exceeded")
            result[table] = [dict(row) for row in rows]
            counts[table] = len(rows)
    except sqlite3.Error as exc:
        raise PreflightError("database query failed") from exc
    finally:
        connection.close()
    after_sha, after_size = _sha256_file(absolute)
    if (before_sha, before_size) != (after_sha, after_size):
        raise PreflightError("database changed during read")
    return result, {
        "path": str(absolute),
        "sha256": before_sha,
        "size_bytes": before_size,
        "tables": {
            key: {"rows": counts[key], "columns": list(TABLE_COLUMNS[key])}
            for key in sorted(counts)
        },
    }


def _sha(value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise PreflightError("invalid SHA-256 identity")
    return value


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise PreflightError(f"{label} must be a non-empty string")
    return value


def _utc(value: object, label: str) -> datetime:
    if not isinstance(value, str):
        raise PreflightError(f"{label} must be an ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("timestamp is naive")
        return parsed.astimezone(UTC)
    except (TypeError, ValueError, OverflowError) as exc:
        raise PreflightError(f"{label} must be timezone-aware UTC") from exc


def _date(value: object, label: str) -> date:
    if not isinstance(value, str):
        raise PreflightError(f"{label} must be an ISO date")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise PreflightError(f"{label} must be an ISO date") from exc


def _payload(raw: object, label: str) -> dict[str, object]:
    if not isinstance(raw, str):
        raise PreflightError(f"{label} must be JSON text")
    value = _json(raw, label)
    if not isinstance(value, dict):
        raise PreflightError(f"{label} must be an object")
    expected = {"vendor_date", "numerator", "denominator", "amount", "currency"}
    if set(value) != expected:
        raise PreflightError(f"{label} fields are incomplete")
    _date(value["vendor_date"], f"{label}.vendor_date")
    for field in ("numerator", "denominator"):
        item = value[field]
        if item is not None and (type(item) is not int or item <= 0):
            raise PreflightError(f"{label}.{field} is invalid")
    amount = value["amount"]
    currency = value["currency"]
    if amount is not None and (not isinstance(amount, str) or not amount):
        raise PreflightError(f"{label}.amount is invalid")
    if currency is not None and currency not in {"KRW", "USD"}:
        raise PreflightError(f"{label}.currency is invalid")
    return value


def _event_key(row: Mapping[str, object]) -> tuple[str, str, str, str]:
    return (
        _text(row["provider"], "event.provider"),
        _text(row["symbol"], "event.symbol"),
        _text(row["kind"], "event.kind"),
        _text(row["provider_key"], "event.provider_key"),
    )


def _check_attempts(rows: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    attempts: dict[str, dict[str, object]] = {}
    for row in rows:
        identifier = _sha(row["id"])
        if identifier in attempts:
            raise PreflightError("duplicate collection attempt id")
        symbol = _text(row["symbol"], "attempt.symbol")
        state = row["state"]
        if state not in {"pending", "success", "failure", "interrupted"}:
            raise PreflightError("attempt state is unsupported")
        requested_start = _date(row["requested_start"], "attempt.requested_start")
        requested_end = _date(row["requested_end"], "attempt.requested_end")
        if requested_start > requested_end:
            raise PreflightError("attempt requested date range is reversed")
        started_at = _utc(row["started_at"], "attempt.started_at")
        completed_at = row["completed_at"]
        if completed_at is None and state in {"success", "failure", "interrupted"}:
            raise PreflightError("completed attempt has no completion timestamp")
        if completed_at is not None:
            completed_at_utc = _utc(completed_at, "attempt.completed_at")
            if started_at > completed_at_utc:
                raise PreflightError("attempt timestamps are reversed")
        body = row["body"]
        if body is not None and not isinstance(body, bytes):
            raise PreflightError("attempt body must be bytes")
        if isinstance(body, bytes):
            if len(body) > MAX_BODY_BYTES:
                raise PreflightError("attempt body exceeds byte cap")
            body_sha = _sha(row["body_sha256"])
            if hashlib.sha256(body).hexdigest() != body_sha:
                raise PreflightError("attempt raw body hash mismatch")
            # Successful response bodies are strict JSON. Failure receipts may
            # intentionally contain provider text such as a rate-limit body.
            if row["state"] == "success":
                _json(body, "attempt.body")
        elif row["body_sha256"] is not None:
            raise PreflightError("attempt body SHA exists without raw body")
        if row["state"] == "success" and body is None:
            raise PreflightError("successful attempt has no raw body")
        attempts[identifier] = {**row, "symbol": symbol}
    return attempts


def _check_collection(
    rows: dict[str, list[dict[str, object]]],
) -> tuple[
    dict[tuple[str, str, str, str], dict[str, object]],
    dict[str, dict[str, object]],
    dict[str, object],
]:
    attempts = _check_attempts(rows["action_collection_attempts"])
    registry = {item.symbol: item for item in REGISTRY}
    events: dict[str, dict[str, object]] = {}
    natural: dict[tuple[str, str, str, str], dict[str, object]] = {}
    for row in rows["action_collection_events"]:
        event_id = _sha(row["id"])
        key = _event_key(row)
        if event_id in events or key in natural:
            raise PreflightError("duplicate event identity")
        if row["provider"] != PROVIDER or row["kind"] not in {"split", "dividend"}:
            raise PreflightError("unsupported event provider or kind")
        expected_id = _hash_object(
            {
                "provider": key[0],
                "symbol": key[1],
                "kind": key[2],
                "provider_key": key[3],
            }
        )
        if event_id != expected_id:
            raise PreflightError("event identity hash mismatch")
        _date(row["vendor_date"], "event.vendor_date")
        first_seen_at = _utc(row["first_seen_at"], "event.first_seen_at")
        last_seen_at = _utc(row["last_seen_at"], "event.last_seen_at")
        if first_seen_at > last_seen_at:
            raise PreflightError("event observation timestamps are reversed")
        _sha(row["latest_content_sha256"])
        natural[key] = {**row, "id": event_id, "key": key}
        events[event_id] = natural[key]
    revisions_by_event: dict[tuple[str, int], dict[str, object]] = {}
    revisions_by_id: dict[str, dict[str, object]] = {}
    parsed_attempts: dict[str, list[CollectedAction]] = {}
    for row in rows["action_collection_revisions"]:
        revision_id = _sha(row["id"])
        event_id = _sha(row["event_id"])
        sequence = row["sequence"]
        if type(sequence) is not int or sequence <= 0:
            raise PreflightError("revision sequence is invalid")
        event = events.get(event_id)
        if event is None:
            raise PreflightError("revision references unknown event")
        pair = (event_id, sequence)
        if pair in revisions_by_event:
            raise PreflightError("duplicate revision identity")
        expected_id = _hash_object({"event": event_id, "sequence": sequence})
        if revision_id != expected_id:
            raise PreflightError("revision identity hash mismatch")
        payload = _payload(row["payload_json"], "revision.payload_json")
        payload_bytes = cast(str, row["payload_json"]).encode("utf-8")
        content_sha = _sha(row["content_sha256"])
        if hashlib.sha256(payload_bytes).hexdigest() != content_sha:
            raise PreflightError("revision payload hash mismatch")
        if (
            content_sha != event["latest_content_sha256"]
            and sequence == event["latest_revision_sequence"]
        ):
            raise PreflightError("event latest payload pointer mismatch")
        if payload["vendor_date"] != event["vendor_date"]:
            raise PreflightError("event and revision vendor dates differ")
        attempt_id = _sha(row["attempt_id"])
        attempt = attempts.get(attempt_id)
        if attempt is None or attempt["state"] != "success":
            raise PreflightError("revision references non-success attempt")
        if attempt["symbol"] != event["symbol"]:
            raise PreflightError("revision and attempt symbols differ")
        instrument = registry.get(cast(str, attempt["symbol"]))
        if instrument is None:
            raise PreflightError("attempt symbol is outside the registry")
        if attempt_id not in parsed_attempts:
            try:
                parsed_attempts[attempt_id] = parse_action_response(
                    cast(bytes, attempt["body"]),
                    instrument,
                    date.fromisoformat(cast(str, attempt["requested_start"])),
                    date.fromisoformat(cast(str, attempt["requested_end"])),
                )
            except (CollectionError, ValueError, TypeError) as exc:
                raise PreflightError("attempt receipt cannot be parsed") from exc
        matches = [
            action
            for action in parsed_attempts[attempt_id]
            if action.kind == event["kind"]
            and action.provider_key == event["provider_key"]
        ]
        if (
            len(matches) != 1
            or matches[0].payload.model_dump_json() != row["payload_json"]
        ):
            raise PreflightError("revision payload does not match parsed receipt")
        revision_first_seen_at = _utc(row["first_seen_at"], "revision.first_seen_at")
        if revision_first_seen_at < _utc(attempt["started_at"], "attempt.started_at"):
            raise PreflightError("revision was observed before attempt start")
        if row["first_seen_at"] != attempt["completed_at"]:
            raise PreflightError("revision and attempt completion times differ")
        revision = {
            **row,
            "id": revision_id,
            "event": event,
            "payload": payload,
            "receipt_body_sha256": attempt["body_sha256"],
            "receipt_completed_at": attempt["completed_at"],
        }
        revisions_by_event[pair] = revision
        revisions_by_id[revision_id] = revision
        revision_list = event.get("revisions")
        if revision_list is None:
            revision_list = []
            event["revisions"] = revision_list
        if not isinstance(revision_list, list):
            raise PreflightError("event revisions are malformed")
        revision_list.append(revision)
    for event in events.values():
        latest = event["latest_revision_sequence"]
        if type(latest) is not int or latest <= 0:
            raise PreflightError("event latest revision pointer is invalid")
        latest_revision = revisions_by_event.get((cast(str, event["id"]), latest))
        if latest_revision is None:
            raise PreflightError("event latest revision is missing")
        if latest_revision["content_sha256"] != event["latest_content_sha256"]:
            raise PreflightError("event latest content pointer is stale")
    summary: dict[str, object] = {
        "attempts": len(attempts),
        "events": len(events),
        "revisions": len(revisions_by_event),
    }
    return natural, revisions_by_id, summary


def _evidence(rows: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for row in rows:
        identifier = _sha(row["id"])
        sha = _sha(row["sha256"])
        if identifier != sha or identifier in result:
            raise PreflightError("review evidence identity mismatch")
        body = row["body"]
        if not isinstance(body, bytes) or len(body) > MAX_BODY_BYTES:
            raise PreflightError("review evidence body is invalid")
        if hashlib.sha256(body).hexdigest() != sha:
            raise PreflightError("review evidence hash mismatch")
        _utc(row["captured_at"], "evidence.captured_at")
        _utc(row["created_at"], "evidence.created_at")
        _text(row["source_url"], "evidence.source_url")
        _text(row["publisher"], "evidence.publisher")
        result[identifier] = row
    return result


def _review_content_hash(
    row: Mapping[str, object], facts: ExtractedFacts, evidence: Mapping[str, object]
) -> str:
    evidence_model = EvidenceInput(
        local_file=Path("."),
        sha256=cast(str, evidence["sha256"]),
        source_url=cast(str, evidence["source_url"]),
        publisher=cast(str, evidence["publisher"]),
        locator=cast(str, row["locator"]),
        captured_at=cast(str, evidence["captured_at"]),
    )
    content = {
        "revision_id": row["revision_id"],
        "content_sha256": row["source_content_sha256"],
        "operator_verified": True,
        "evidence": evidence_model.model_dump(
            mode="json", exclude={"local_file", "locator"}
        ),
        "locator": row["locator"],
        "extracted_facts": facts.model_dump(mode="json"),
    }
    return _hash_object(content)


def _review_representation(
    fields_raw: Sequence[object],
    expected_fields: list[dict[str, object]],
    *,
    kind: str,
) -> tuple[str, str | None]:
    """Accept the canonical array or the one explicitly versioned legacy form."""
    if fields_raw == expected_fields:
        return "canonical-v1", None
    if kind != "dividend":
        raise PreflightError("review comparison is not reproducible")
    legacy_fields = [dict(item) for item in expected_fields]
    share_basis = next(
        (
            item
            for item in legacy_fields
            if item.get("field") == "comparable_share_basis"
        ),
        None,
    )
    if share_basis is None:
        raise PreflightError("review comparison is not reproducible")
    if (
        share_basis.get("evidence_value") != "true"
        or share_basis.get("status") != "matched"
    ):
        raise PreflightError("review comparison is not reproducible")
    share_basis["source_value"] = "true"
    if fields_raw != legacy_fields:
        raise PreflightError("review comparison is not reproducible")
    return "legacy-v1", "comparable_share_basis.source_value:true-to-null"


def _output_path(path: Path) -> Path:
    try:
        return _check_path_components(path, "output")
    except ArtifactError as exc:
        raise PreflightError(str(exc)) from exc


def _check_reviews(
    rows: dict[str, list[dict[str, object]]],
    review_revisions: dict[str, dict[str, object]],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    evidence = _evidence(rows["action_review_evidence"])
    seen_keys: set[str] = set()
    seen_revision_sequence: set[tuple[str, int]] = set()
    records: list[dict[str, object]] = []
    counts: Counter[str] = Counter()
    for row in rows["action_reviews"]:
        review_id = _sha(row["id"])
        review_key = _text(row["review_key"], "review.review_key")
        if review_key in seen_keys:
            raise PreflightError("duplicate review key")
        seen_keys.add(review_key)
        revision_id = _sha(row["revision_id"])
        sequence = row["sequence"]
        if type(sequence) is not int or sequence <= 0:
            raise PreflightError("review sequence is invalid")
        pair = (revision_id, sequence)
        if pair in seen_revision_sequence:
            raise PreflightError("duplicate review revision sequence")
        seen_revision_sequence.add(pair)
        source_sha = _sha(row["source_content_sha256"])
        review_content_sha = _sha(row["content_sha256"])
        evidence_id = _sha(row["evidence_id"])
        evidence_row = evidence.get(evidence_id)
        if evidence_row is None:
            raise PreflightError("review references unknown evidence")
        revision = review_revisions.get(revision_id)
        facts_raw = _json(cast(str, row["extracted_facts_json"]), "review facts")
        fields_text = cast(str, row["compared_fields_json"])
        fields_raw = _json(fields_text, "review fields")
        fields_sha256 = hashlib.sha256(fields_text.encode("utf-8")).hexdigest()
        if not isinstance(facts_raw, dict) or not isinstance(fields_raw, list):
            raise PreflightError("review JSON shape is invalid")
        try:
            facts = ExtractedFacts.model_validate(facts_raw)
        except ValidationError as exc:
            raise PreflightError("review facts are invalid") from exc
        if revision is None:
            raise PreflightError("review references unknown revision")
        if source_sha != revision["content_sha256"]:
            raise PreflightError("review source payload hash mismatch")
        event = cast(dict[str, object], revision["event"])
        key = cast(tuple[str, str, str, str], event["key"])
        status, compared = compare_review(
            cast(Literal["split", "dividend"], key[2]),
            cast(dict[str, object], revision["payload"]),
            facts,
        )
        expected_fields = [item.model_dump(mode="json") for item in compared]
        if _review_content_hash(row, facts, evidence_row) != review_content_sha:
            raise PreflightError("review content hash mismatch")
        expected_id = _hash_object(
            {"review_key": review_key, "content": row["content_sha256"]}
        )
        if review_id != expected_id:
            raise PreflightError("review identity hash mismatch")
        if row["comparison_status"] != status:
            raise PreflightError("review comparison is not reproducible")
        normalization_version, legacy_adapter = _review_representation(
            fields_raw, expected_fields, kind=key[2]
        )
        _utc(row["reviewed_at"], "review.reviewed_at")
        _utc(row["imported_at"], "review.imported_at")
        synthetic = review_key.startswith("synthetic-")
        category = "synthetic_excluded" if synthetic else str(status)
        counts[category] += 1
        records.append(
            {
                "review_key": review_key,
                "review_id": review_id,
                "event_id": event["id"],
                "revision_id": revision_id,
                "revision_sequence": revision["sequence"],
                "revision_first_seen_at": revision["first_seen_at"],
                "revision_payload_sha256": revision["content_sha256"],
                "natural_key": list(key),
                "payload_sha256": source_sha,
                "provider": key[0],
                "attempt_id": revision["attempt_id"],
                "receipt_body_sha256": revision["receipt_body_sha256"],
                "receipt_completed_at": revision["receipt_completed_at"],
                "evidence_id": evidence_id,
                "evidence_sha256": evidence_row["sha256"],
                "evidence_captured_at": evidence_row["captured_at"],
                "comparison_status": status,
                "compared_fields": {
                    "raw_json": fields_text,
                    "raw_sha256": fields_sha256,
                    "canonical": expected_fields,
                    "canonical_sha256": _hash_object(expected_fields),
                    "normalization_version": normalization_version,
                    "legacy_adapter": legacy_adapter,
                },
                "reviewed_at": row["reviewed_at"],
                "imported_at": row["imported_at"],
                "synthetic": synthetic,
                "eligibility": "excluded" if synthetic else "blocked",
                "blocked_reasons": [
                    "missing_effective_utc_boundary",
                    "missing_price_inputs",
                    "missing_entitlement_inputs",
                    "coverage_incomplete",
                ],
            }
        )
    records.sort(key=lambda item: cast(str, item["review_key"]))
    return records, {"reviews": len(records), "counts": dict(sorted(counts.items()))}


def _build_preflight(
    collection_db: Path,
    review_db: Path,
    *,
    expected_collection_sha256: str,
    expected_review_sha256: str,
) -> dict[str, object]:
    """Build a deterministic read-only receipt provenance report."""
    collection_rows, collection_input = _read_snapshot(
        collection_db,
        tables=set(TABLE_COLUMNS) - {"action_review_evidence", "action_reviews"},
        caps={
            "action_collection_attempts": MAX_ATTEMPTS,
            "action_collection_source_status": MAX_EVENTS,
            "action_collection_events": MAX_EVENTS,
            "action_collection_revisions": MAX_REVISIONS,
        },
        expected_sha256=expected_collection_sha256,
    )
    review_rows, review_input = _read_snapshot(
        review_db,
        tables=set(TABLE_COLUMNS),
        caps={
            "action_collection_attempts": MAX_ATTEMPTS,
            "action_collection_source_status": MAX_EVENTS,
            "action_collection_events": MAX_EVENTS,
            "action_collection_revisions": MAX_REVISIONS,
            "action_review_evidence": MAX_EVIDENCE,
            "action_reviews": MAX_REVIEWS,
        },
        expected_sha256=expected_review_sha256,
    )
    for expected_sha, input_meta in (
        (expected_collection_sha256, collection_input),
        (expected_review_sha256, review_input),
    ):
        if expected_sha in EXPECTED_SIZES:
            if input_meta["size_bytes"] != EXPECTED_SIZES[expected_sha]:
                raise PreflightError("fixed input size differs from manifest")
            expected_rows = EXPECTED_ROWS[expected_sha]
            actual_tables = cast(dict[str, dict[str, object]], input_meta["tables"])
            if any(
                actual_tables[name]["rows"] != count
                for name, count in expected_rows.items()
            ):
                raise PreflightError("fixed input row count differs from manifest")
    collection_natural, _collection_revisions, collection_counts = _check_collection(
        collection_rows
    )
    review_natural, review_revisions, review_counts = _check_collection(review_rows)
    if not set(collection_natural).issubset(review_natural):
        raise PreflightError("collection action natural key is absent from review DB")
    for key in collection_natural:
        if (
            collection_natural[key]["latest_content_sha256"]
            != review_natural[key]["latest_content_sha256"]
        ):
            raise PreflightError("collection and review payload hashes differ")
    reviews, review_summary = _check_reviews(review_rows, review_revisions)
    official_matched = sum(
        1
        for item in reviews
        if item["synthetic"] is False and item["comparison_status"] == "matched"
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "seed": 0,
        "mode": "offline-read-only",
        "coverage": "incomplete",
        "economic_status": "not-evaluated",
        "prospective_validation_eligible": False,
        "automatic_ledger_application": False,
        "artifact_replay": None,
        "artifact_linkage": {
            "schema_version": ARTIFACT_SCHEMA_VERSION,
            "linked": False,
            "required_input_fields": list(ARTIFACT_REQUIRED_FIELDS),
            "missing_fields": list(ARTIFACT_MISSING_FIELDS),
            "reason": (
                "receipt review does not provide a complete accounting replay envelope"
            ),
        },
        "inputs": {"collection": collection_input, "review": review_input},
        "collection": collection_counts,
        "review_collection": review_counts,
        "review": review_summary,
        "official_matched_count": official_matched,
        "records": reviews,
        "limitations": [
            "receipt_is_collection_attempt_body",
            "synthetic_reviews_excluded",
            "missing_effective_utc_boundary",
            "missing_price_inputs",
            "missing_entitlement_inputs",
            "coverage_incomplete",
            "pit_and_economic_acceptance_deferred",
        ],
    }


def write_preflight(
    collection_db: Path,
    review_db: Path,
    output: Path,
) -> None:
    data = _canonical(
        _build_preflight(
            collection_db,
            review_db,
            expected_collection_sha256=COLLECTION_DB_SHA256,
            expected_review_sha256=REVIEW_DB_SHA256,
        )
    )
    if len(data) > MAX_OUTPUT_BYTES:
        raise PreflightError("output exceeds 50MiB")
    output = _output_path(output)
    if output.exists() or output.is_symlink():
        raise PreflightError("output already exists")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(output, flags, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
    except OSError as exc:
        raise PreflightError("output cannot be created") from exc


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collection-db", type=Path, required=True)
    parser.add_argument("--review-db", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    try:
        args = parser.parse_args(argv)
        write_preflight(
            args.collection_db,
            args.review_db,
            args.output,
        )
    except (PreflightError, OSError, TypeError, ValueError, sqlite3.Error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


def build_preflight(collection_db: Path, review_db: Path) -> dict[str, object]:
    """Build a report for the two immutable databases in the fixed manifest."""
    return _build_preflight(
        collection_db,
        review_db,
        expected_collection_sha256=COLLECTION_DB_SHA256,
        expected_review_sha256=REVIEW_DB_SHA256,
    )


__all__ = [
    "COLLECTION_DB_SHA256",
    "MAX_OUTPUT_BYTES",
    "PreflightError",
    "REVIEW_DB_SHA256",
    "build_preflight",
    "main",
    "write_preflight",
]


if __name__ == "__main__":
    raise SystemExit(main())
