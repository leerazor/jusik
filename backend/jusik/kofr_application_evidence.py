"""Fail-closed contract for applying KOFR source rows to return intervals.

Source evidence and application evidence are deliberately separate.  This
module validates an explicit application manifest but never computes Sharpe or
changes a performance result.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

MAX_BYTES = 2 * 1024 * 1024
SCHEMA = "kofr-risk-free-application/v1"
SOURCE_SCHEMA = "kofr-source-evidence/v1"
SHA_RE = re.compile(r"^[0-9a-f]{64}$")


class KofrApplicationError(ValueError):
    """Stable fail-closed application contract error."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class _DuplicateKey(ValueError):
    pass


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKey(key)
        result[key] = value
    return result


def _load(path: Path) -> dict[str, object]:
    try:
        raw = path.read_bytes()
        if len(raw) > MAX_BYTES:
            raise KofrApplicationError("input_too_large")
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs)
    except KofrApplicationError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, _DuplicateKey):
        raise KofrApplicationError("malformed_json") from None
    if not isinstance(value, dict):
        raise KofrApplicationError("malformed_json")
    return value


def _text(value: object, code: str = "malformed_contract") -> str:
    if not isinstance(value, str) or not value.strip():
        raise KofrApplicationError(code)
    return value


def _sha(value: object) -> str:
    text = _text(value)
    if SHA_RE.fullmatch(text) is None:
        raise KofrApplicationError("invalid_source_hash")
    return text


def _decimal(value: object) -> Decimal:
    try:
        parsed = Decimal(_text(value))
    except (InvalidOperation, KofrApplicationError):
        raise KofrApplicationError("invalid_rate") from None
    if not parsed.is_finite():
        raise KofrApplicationError("invalid_rate")
    return parsed


def _day(value: object) -> date:
    text = _text(value)
    for fmt in ("%Y-%m-%d", "%Y.%m.%d", "%Y%m%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise KofrApplicationError("invalid_date")


def _publication(value: object, timezone: ZoneInfo) -> datetime:
    text = _text(value)
    try:
        local = datetime.strptime(text, "%Y.%m.%d %H:%M:%S").replace(tzinfo=timezone)
    except ValueError:
        raise KofrApplicationError("invalid_publication_time") from None
    return local.astimezone(UTC)


@dataclass(frozen=True)
class ApplicationInterval:
    start: date
    end: date
    source_observed_on: date
    annual_rate: Decimal


@dataclass(frozen=True)
class KofrApplicationReport:
    source_evidence_sha256: str
    timezone: str
    business_dates: tuple[date, ...]
    intervals: tuple[ApplicationInterval, ...]


@dataclass(frozen=True)
class NavDateApplicationReport:
    nav_dates: tuple[date, ...]
    matched_dates: tuple[date, ...]
    missing_dates: tuple[date, ...]


def validate_nav_date_application(
    application: KofrApplicationReport, nav_dates: Iterable[date]
) -> NavDateApplicationReport:
    """Require exact source-date coverage for every NAV date.

    This preflight intentionally has no carry-forward or calendar inference.
    A caller that needs either policy must provide a separate reviewed contract.
    """
    normalized = tuple(nav_dates)
    if any(not isinstance(item, date) for item in normalized):
        raise KofrApplicationError("nav_date_invalid")
    if normalized != tuple(sorted(set(normalized))):
        raise KofrApplicationError("nav_dates_not_ordered")
    source_dates = set(application.business_dates)
    matched = tuple(item for item in normalized if item in source_dates)
    missing = tuple(item for item in normalized if item not in source_dates)
    if missing:
        raise KofrApplicationError("nav_date_application_missing")
    return NavDateApplicationReport(normalized, matched, missing)


def validate_application_contract(
    source_evidence: Path, application: Path
) -> KofrApplicationReport:
    """Validate explicit source-to-interval application provenance."""
    try:
        source_bytes = source_evidence.read_bytes()
    except OSError:
        raise KofrApplicationError("source_unavailable") from None
    if len(source_bytes) > MAX_BYTES:
        raise KofrApplicationError("source_too_large")
    source = _load(source_evidence)
    if source.get("schema") != SOURCE_SCHEMA:
        raise KofrApplicationError("source_schema")
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    manifest = _load(application)
    if manifest.get("schema") != SCHEMA:
        raise KofrApplicationError("application_schema")
    if _sha(manifest.get("source_evidence_sha256")) != source_sha:
        raise KofrApplicationError("source_hash_mismatch")
    timezone_name = _text(manifest.get("timezone"))
    try:
        timezone = ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError):
        raise KofrApplicationError("invalid_timezone") from None
    if timezone_name != "Asia/Seoul":
        raise KofrApplicationError("unsupported_timezone")
    if manifest.get("publication_timestamp_semantics") != "local_wall_time":
        raise KofrApplicationError("publication_semantics_required")
    if manifest.get("coverage_status") != "complete":
        raise KofrApplicationError("business_date_completeness_unverified")
    rows = source.get("rows")
    if not isinstance(rows, list) or not rows:
        raise KofrApplicationError("source_rows_missing")
    row_by_day: dict[date, Decimal] = {}
    published_by_day: dict[date, datetime] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise KofrApplicationError("source_row_malformed")
        observed = _day(row.get("RFR_PUBN_DT"))
        if observed in row_by_day:
            raise KofrApplicationError("source_duplicate_date")
        row_by_day[observed] = _decimal(row.get("RFR_PUBN_MR"))
        published_by_day[observed] = _publication(row.get("PUBN_DTTM"), timezone)
    raw_dates = manifest.get("business_dates")
    if not isinstance(raw_dates, list) or not raw_dates:
        raise KofrApplicationError("business_dates_missing")
    business_dates = tuple(_day(item) for item in raw_dates)
    if business_dates != tuple(sorted(set(business_dates))):
        raise KofrApplicationError("business_dates_not_ordered")
    if set(business_dates) != set(row_by_day):
        raise KofrApplicationError("business_date_manifest_mismatch")
    if any(item not in row_by_day for item in business_dates):
        raise KofrApplicationError("business_date_source_missing")
    raw_intervals = manifest.get("intervals")
    if not isinstance(raw_intervals, list) or not raw_intervals:
        raise KofrApplicationError("intervals_missing")
    intervals: list[ApplicationInterval] = []
    previous_end: date | None = None
    for raw in raw_intervals:
        if not isinstance(raw, dict):
            raise KofrApplicationError("interval_malformed")
        start, end = _day(raw.get("start")), _day(raw.get("end"))
        source_day = _day(raw.get("source_observed_on"))
        if end <= start or (previous_end is not None and start < previous_end):
            raise KofrApplicationError("interval_order")
        if source_day not in row_by_day:
            raise KofrApplicationError("interval_source_missing")
        if _decimal(raw.get("annual_rate")) != row_by_day[source_day]:
            raise KofrApplicationError("interval_rate_mismatch")
        if published_by_day[source_day] >= datetime.combine(start, time.min, UTC):
            raise KofrApplicationError("publication_after_interval_start")
        intervals.append(
            ApplicationInterval(start, end, source_day, row_by_day[source_day])
        )
        previous_end = end
    return KofrApplicationReport(
        source_sha, timezone_name, business_dates, tuple(intervals)
    )


__all__ = [
    "ApplicationInterval",
    "KofrApplicationError",
    "KofrApplicationReport",
    "NavDateApplicationReport",
    "validate_nav_date_application",
    "validate_application_contract",
]
