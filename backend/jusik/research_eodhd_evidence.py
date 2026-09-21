"""Offline EODHD corporate-action evidence with an explicit SEC boundary.

The adapter parses already captured bytes.  It never calls a provider, infers
publication or PIT availability, or applies a corporate action to a ledger.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from jusik.research_sec_evidence import (
    SEC_SUBMISSIONS_URL,
    filing_document_url,
    parse_sec_filing_candidate,
    parse_sec_submissions,
)

EodhdEndpoint = Literal["div", "splits"]
_SYMBOL = re.compile(r"^[A-Z][A-Z0-9.\-/]{0,19}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_RATIO = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*/\s*([0-9]+(?:\.[0-9]+)?)\s*$")


def _utc(value: datetime, *, field: str) -> datetime:
    if value.tzinfo is None:
        raise ValueError(f"{field}_must_be_timezone_aware")
    return value.astimezone(UTC)


def _date(value: object, field: str) -> date:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field}_invalid")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field}_invalid") from exc


def _nullable_date(value: object, field: str) -> date | None:
    if value is None:
        return None
    return _date(value, field)


def _decimal(value: object, field: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise ValueError(f"{field}_invalid")
    try:
        parsed = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field}_invalid") from exc
    if not parsed.is_finite() or parsed <= 0:
        raise ValueError(f"{field}_invalid")
    return parsed


class EodhdRequest(BaseModel):
    """One bounded US EODHD action request."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: str = Field(pattern=r"^[A-Z][A-Z0-9.\-/]{0,19}$")
    exchange: Literal["US"] = "US"
    endpoint: EodhdEndpoint
    start: date
    end: date

    @field_validator("symbol")
    @classmethod
    def symbol_is_uppercase(cls, value: str) -> str:
        if _SYMBOL.fullmatch(value) is None or value != value.upper():
            raise ValueError("symbol_must_be_uppercase_us_ticker")
        return value

    @model_validator(mode="after")
    def period_is_ordered(self) -> EodhdRequest:
        if self.end < self.start:
            raise ValueError("end_before_start")
        return self


class EodhdDividendEvidence(BaseModel):
    """One EODHD dividend row; ``ex_date`` is the provider's ``date``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_key: str = Field(min_length=1, max_length=100)
    symbol: str = Field(pattern=r"^[A-Z][A-Z0-9.\-/]{0,19}$")
    ex_date: date
    declaration_date: date | None = None
    record_date: date | None = None
    payment_date: date | None = None
    value: Decimal
    unadjusted_value: Decimal
    currency: str = Field(min_length=1, max_length=12)
    missing_fields: tuple[str, ...] = ()

    @field_validator("value", "unadjusted_value")
    @classmethod
    def positive_amount(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value <= 0:
            raise ValueError("dividend_amount_invalid")
        return value


class EodhdSplitEvidence(BaseModel):
    """One EODHD split row represented as an exact positive rational."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_key: str = Field(min_length=1, max_length=100)
    symbol: str = Field(pattern=r"^[A-Z][A-Z0-9.\-/]{0,19}$")
    event_date: date
    numerator: int = Field(gt=0)
    denominator: int = Field(gt=0)


class SecReferenceMetadata(BaseModel):
    """Identity metadata for an explicitly bound SEC filing.

    These fields describe the reference source only; they do not verify or
    replace the EODHD action facts.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_key: str = Field(min_length=1, max_length=100)
    accession_number: str = Field(pattern=r"^\d{10}-\d{2}-\d{6}$")
    cik: str = Field(pattern=r"^\d{10}$")
    form: str = Field(min_length=1, max_length=20)
    raw_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    submissions_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    retrieved_at: datetime
    submissions_retrieved_at: datetime
    accepted_at: datetime | None
    source_url: str = Field(min_length=1, max_length=500)
    submissions_source_url: str = Field(min_length=1, max_length=500)

    @field_validator("retrieved_at", "submissions_retrieved_at", "accepted_at")
    @classmethod
    def timestamps_utc(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _utc(value, field="sec_timestamp")


class EodhdEvidence(BaseModel):
    """Immutable parser output with all promotion/evaluation gates closed."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    request: EodhdRequest
    raw_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    retrieved_at: datetime
    dividends: tuple[EodhdDividendEvidence, ...] = ()
    splits: tuple[EodhdSplitEvidence, ...] = ()
    missing_fields: tuple[str, ...] = ()
    evidence_status: Literal["complete", "blocked"] = "complete"
    pit_evaluation: Literal["not-evaluated"] = "not-evaluated"
    coverage: Literal["not-evaluated"] = "not-evaluated"
    economic_evaluation: Literal["not-evaluated"] = "not-evaluated"
    automatic_ledger_application: Literal[False] = False
    sec_reference: SecReferenceMetadata | None = None

    @field_validator("retrieved_at")
    @classmethod
    def retrieved_at_utc(cls, value: datetime) -> datetime:
        return _utc(value, field="retrieved_at")

    @model_validator(mode="after")
    def status_matches_missing_fields(self) -> EodhdEvidence:
        expected = "blocked" if self.missing_fields else "complete"
        if self.evidence_status != expected:
            raise ValueError("evidence_status_mismatch")
        return self

    @property
    def blocked(self) -> bool:
        return self.evidence_status == "blocked"

    @property
    def response_sha256(self) -> str:
        return self.raw_sha256

    @property
    def source_sha256(self) -> str:
        return self.raw_sha256

    @property
    def coverage_status(self) -> Literal["not-evaluated"]:
        return self.coverage

    @property
    def pit_status(self) -> Literal["not-evaluated"]:
        return self.pit_evaluation

    @property
    def economic_status(self) -> Literal["not-evaluated"]:
        return self.economic_evaluation


def _object_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("eodhd_duplicate_json_key")
        result[key] = value
    return result


def _payload_rows(raw: bytes) -> list[Mapping[str, object]]:
    try:
        payload = json.loads(raw, object_pairs_hook=_object_pairs, parse_float=Decimal)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError("eodhd_invalid_json") from exc
    if not isinstance(payload, list):
        raise ValueError("eodhd_invalid_root")
    if not all(isinstance(row, Mapping) for row in payload):
        raise ValueError("eodhd_row_invalid")
    return list(payload)


def _ratio(value: object) -> tuple[int, int]:
    if not isinstance(value, str):
        raise ValueError("split_ratio_invalid")
    match = _RATIO.fullmatch(value)
    if match is None:
        raise ValueError("split_ratio_invalid")
    try:
        numerator = Decimal(match.group(1))
        denominator = Decimal(match.group(2))
    except InvalidOperation as exc:
        raise ValueError("split_ratio_invalid") from exc
    if not numerator.is_finite() or not denominator.is_finite():
        raise ValueError("split_ratio_invalid")
    if numerator <= 0 or denominator <= 0:
        raise ValueError("split_ratio_invalid")
    ratio = Fraction(*numerator.as_integer_ratio()) / Fraction(
        *denominator.as_integer_ratio()
    )
    return ratio.numerator, ratio.denominator


def _event_key(request: EodhdRequest, event_date: date) -> str:
    return f"{request.symbol}:{request.endpoint}:{event_date.isoformat()}"


def parse_eodhd_response(
    raw: bytes,
    request: EodhdRequest,
    retrieved_at: datetime,
) -> EodhdEvidence:
    """Parse one captured response and reject any invalid/out-of-range row."""
    if not isinstance(raw, bytes):
        raise TypeError("raw_response_must_be_bytes")
    retrieved = _utc(retrieved_at, field="retrieved_at")
    rows = _payload_rows(raw)
    digest = hashlib.sha256(raw).hexdigest()
    missing: set[str] = set()
    if request.endpoint == "div":
        events: list[EodhdDividendEvidence] = []
        seen: set[date] = set()
        allowed = {
            "date",
            "declarationDate",
            "recordDate",
            "paymentDate",
            "period",
            "value",
            "unadjustedValue",
            "currency",
        }
        for row in rows:
            if set(row) - allowed:
                raise ValueError("dividend_schema_invalid")
            event_date = _date(row.get("date"), "date")
            if not request.start <= event_date <= request.end:
                raise ValueError("eodhd_row_out_of_period")
            if event_date in seen:
                raise ValueError("eodhd_duplicate_event")
            seen.add(event_date)
            row_missing: set[str] = set()
            auxiliary: dict[str, date | None] = {}
            for wire_name, field_name in (
                ("declarationDate", "declaration_date"),
                ("recordDate", "record_date"),
                ("paymentDate", "payment_date"),
            ):
                if wire_name not in row or row[wire_name] is None:
                    missing.add(wire_name)
                    row_missing.add(wire_name)
                    auxiliary[field_name] = None
                else:
                    auxiliary[field_name] = _nullable_date(row[wire_name], wire_name)
            value = _decimal(row.get("value"), "value")
            unadjusted = _decimal(row.get("unadjustedValue"), "unadjustedValue")
            currency = row.get("currency")
            if not isinstance(currency, str) or not currency:
                raise ValueError("currency_invalid")
            event_missing = tuple(
                name
                for name in ("declarationDate", "recordDate", "paymentDate")
                if name in row_missing
            )
            events.append(
                EodhdDividendEvidence(
                    event_key=_event_key(request, event_date),
                    symbol=request.symbol,
                    ex_date=event_date,
                    declaration_date=auxiliary["declaration_date"],
                    record_date=auxiliary["record_date"],
                    payment_date=auxiliary["payment_date"],
                    value=value,
                    unadjusted_value=unadjusted,
                    currency=currency,
                    missing_fields=event_missing,
                )
            )
        return EodhdEvidence(
            request=request,
            raw_sha256=digest,
            retrieved_at=retrieved,
            dividends=tuple(events),
            missing_fields=tuple(sorted(missing)),
            evidence_status="blocked" if missing else "complete",
        )

    events_split: list[EodhdSplitEvidence] = []
    seen_split: set[date] = set()
    allowed_split = {"date", "split"}
    for row in rows:
        if set(row) - allowed_split:
            raise ValueError("split_schema_invalid")
        event_date = _date(row.get("date"), "date")
        if not request.start <= event_date <= request.end:
            raise ValueError("eodhd_row_out_of_period")
        if event_date in seen_split:
            raise ValueError("eodhd_duplicate_event")
        seen_split.add(event_date)
        numerator, denominator = _ratio(row.get("split"))
        events_split.append(
            EodhdSplitEvidence(
                event_key=_event_key(request, event_date),
                symbol=request.symbol,
                event_date=event_date,
                numerator=numerator,
                denominator=denominator,
            )
        )
    return EodhdEvidence(
        request=request,
        raw_sha256=digest,
        retrieved_at=retrieved,
        splits=tuple(events_split),
    )


def _validate_submission_columns(raw: bytes) -> None:
    """Reject malformed SEC column arrays before the legacy parser's min()."""
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("sec_submissions_invalid") from exc
    recent = (
        payload.get("filings", {}).get("recent")
        if isinstance(payload, Mapping)
        else None
    )
    if not isinstance(recent, Mapping):
        raise ValueError("sec_submissions_invalid")
    columns = [recent.get(name) for name in ("form", "accessionNumber", "filingDate")]
    if not all(isinstance(column, list) for column in columns):
        raise ValueError("sec_submissions_invalid")
    lengths = {len(column) for column in columns if isinstance(column, list)}
    if len(lengths) != 1:
        raise ValueError("sec_submissions_columns_mismatch")


def _raw_accession_count(raw: bytes, expected_accession: str) -> int:
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("sec_submissions_invalid") from exc
    recent = (
        payload.get("filings", {}).get("recent")
        if isinstance(payload, Mapping)
        else None
    )
    accessions = recent.get("accessionNumber") if isinstance(recent, Mapping) else None
    if not isinstance(accessions, list):
        raise ValueError("sec_submissions_invalid")
    return sum(item == expected_accession for item in accessions)


def bind_sec_reference(
    evidence: EodhdEvidence,
    *,
    filing_body: bytes,
    submissions_body: bytes,
    expected_raw_sha256: str,
    expected_submissions_sha256: str,
    expected_accession_number: str,
    expected_cik: str,
    event_key: str,
    retrieved_at: datetime,
    submissions_retrieved_at: datetime,
    submissions_source_url: str,
    filing_source_url: str,
) -> EodhdEvidence:
    """Bind one explicitly selected SEC filing by exact identity.

    The SEC submission response and filing body are both parsed through the
    existing SEC evidence module.  No symbol/date or action-fact association is
    inferred from filing text.
    """
    if evidence.evidence_status != "complete":
        raise ValueError("eodhd_evidence_blocked")
    if _SHA256.fullmatch(expected_raw_sha256) is None:
        raise ValueError("sec_expected_raw_sha256_invalid")
    if _SHA256.fullmatch(expected_submissions_sha256) is None:
        raise ValueError("sec_expected_submissions_sha256_invalid")
    if not isinstance(filing_body, bytes) or not isinstance(submissions_body, bytes):
        raise TypeError("sec_raw_response_must_be_bytes")
    event_keys = [event.event_key for event in evidence.dividends]
    event_keys.extend(event.event_key for event in evidence.splits)
    if event_key not in set(event_keys):
        raise ValueError("sec_event_key_not_found")
    filing_digest = hashlib.sha256(filing_body).hexdigest()
    if filing_digest != expected_raw_sha256:
        raise ValueError("sec_raw_sha256_mismatch")
    submissions_digest = hashlib.sha256(submissions_body).hexdigest()
    if submissions_digest != expected_submissions_sha256:
        raise ValueError("sec_submissions_sha256_mismatch")
    observed = _utc(retrieved_at, field="retrieved_at")
    submissions_observed = _utc(
        submissions_retrieved_at, field="submissions_retrieved_at"
    )
    _validate_submission_columns(submissions_body)
    if _raw_accession_count(submissions_body, expected_accession_number) != 1:
        raise ValueError("sec_accession_not_unique")
    try:
        filings = parse_sec_submissions(
            submissions_body,
            observed_at=submissions_observed,
            source_url=submissions_source_url,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("sec_submissions_invalid") from exc
    matches = [
        filing
        for filing in filings
        if filing.accession_number == expected_accession_number
    ]
    if len(matches) != 1:
        raise ValueError("sec_accession_not_unique")
    filing = matches[0]
    if filing.cik != expected_cik:
        raise ValueError("sec_cik_mismatch")
    if submissions_source_url != SEC_SUBMISSIONS_URL.format(cik=expected_cik):
        raise ValueError("sec_submissions_source_mismatch")
    try:
        expected_filing_url = filing_document_url(filing)
    except ValueError as exc:
        raise ValueError("sec_filing_source_mismatch") from exc
    if filing_source_url != expected_filing_url:
        raise ValueError("sec_filing_source_mismatch")
    if filing.acceptance_datetime is not None and (
        filing.acceptance_datetime > observed
        or filing.acceptance_datetime > submissions_observed
    ):
        raise ValueError("sec_accepted_after_observed")
    candidate = parse_sec_filing_candidate(
        filing_body,
        filing=filing,
        observed_at=observed,
        source_url=filing_source_url,
    )
    if candidate.raw_sha256 != expected_raw_sha256:
        raise ValueError("sec_raw_sha256_mismatch")
    return evidence.model_copy(
        update={
            "sec_reference": SecReferenceMetadata(
                event_key=event_key,
                accession_number=filing.accession_number,
                cik=filing.cik,
                form=filing.form,
                raw_sha256=candidate.raw_sha256,
                submissions_sha256=filing.raw_sha256,
                retrieved_at=observed,
                submissions_retrieved_at=submissions_observed,
                accepted_at=filing.acceptance_datetime,
                source_url=filing_source_url,
                submissions_source_url=submissions_source_url,
            )
        }
    )


__all__ = [
    "EodhdDividendEvidence",
    "EodhdEndpoint",
    "EodhdEvidence",
    "EodhdRequest",
    "EodhdSplitEvidence",
    "SecReferenceMetadata",
    "bind_sec_reference",
    "parse_eodhd_response",
]
