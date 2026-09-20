"""SEC EDGAR filing evidence collector with immutable raw responses."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator

from jusik.research_action_review import (
    EvidenceInput,
    ExtractedFacts,
    ReviewInput,
    ReviewManifest,
)

SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_MIN_REQUEST_INTERVAL_SECONDS = 0.2
MAX_SEC_REVIEW_EVIDENCE_BYTES = 4 * 1024 * 1024
MAX_SEC_REVIEW_QUEUE_BYTES = 2 * 1024 * 1024


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(UTC)


class SecFiling(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    cik: str = Field(pattern=r"^\d{10}$")
    accession_number: str = Field(pattern=r"^\d{10}-\d{2}-\d{6}$")
    form: str = Field(min_length=1, max_length=20)
    filing_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    acceptance_datetime: datetime | None = None
    primary_document: str | None = None
    source_url: str = Field(min_length=1, max_length=500)
    observed_at: datetime
    raw_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("acceptance_datetime", "observed_at")
    @classmethod
    def timestamps_utc(cls, value: datetime | None) -> datetime | None:
        return _utc(value) if value is not None else None


class SecTicker(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    ticker: str = Field(min_length=1, max_length=20)
    cik: str = Field(pattern=r"^\d{10}$")
    title: str = Field(min_length=1, max_length=300)


class SecFilingCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    cik: str = Field(pattern=r"^\d{10}$")
    accession_number: str = Field(pattern=r"^\d{10}-\d{2}-\d{6}$")
    form: str = Field(min_length=1, max_length=20)
    source_url: str = Field(min_length=1, max_length=500)
    observed_at: datetime
    raw_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_kinds: tuple[str, ...]
    candidate_snippets: tuple[str, ...]

    @field_validator("observed_at")
    @classmethod
    def observed_at_utc(cls, value: datetime) -> datetime:
        return _utc(value)


SEC_REVIEW_QUEUE_REQUIRED_FIELDS: tuple[str, ...] = (
    "manual_classification",
    "event_type",
    "effective_date",
    "amount_or_ratio",
    "share_basis",
    "pit_link",
)


class SecReviewQueueItem(BaseModel):
    """Non-authoritative SEC candidate awaiting action review."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: str = Field(pattern=r"^[A-Z0-9][A-Z0-9.\-/]{0,19}$")
    accession_number: str = Field(pattern=r"^\d{10}-\d{2}-\d{6}$")
    source_url: str = Field(min_length=1, max_length=500)
    raw_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_kinds: tuple[str, ...]
    candidate_snippets: tuple[str, ...]
    status: Literal["unsupported_candidate"] = "unsupported_candidate"
    required_fields: tuple[str, ...] = SEC_REVIEW_QUEUE_REQUIRED_FIELDS
    automatic_ledger_application: Literal[False] = False


class SecReviewQueue(BaseModel):
    """Deterministic queue; it cannot represent an approved action."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    promotion: Literal["forbidden_until_action_review"] = (
        "forbidden_until_action_review"
    )
    source: Literal["sec_edgar_event_near_candidates"] = (
        "sec_edgar_event_near_candidates"
    )
    items: tuple[SecReviewQueueItem, ...] = Field(min_length=1, max_length=100)


class SecReviewQueueSourceVerification(BaseModel):
    """Bounded offline verification of queue-to-raw filing identity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    queue_items: int = Field(ge=1, le=100)
    verified_items: int = Field(ge=0, le=100)
    missing_accessions: tuple[str, ...] = ()
    sha_mismatch_accessions: tuple[str, ...] = ()
    ready: bool


class SecReviewPriorityItem(BaseModel):
    """One item from the bounded operator-review priority catalog."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: str = Field(pattern=r"^[A-Z0-9][A-Z0-9.\-/]{0,19}$")
    accession_number: str = Field(pattern=r"^\d{10}-\d{2}-\d{6}$")
    source_url: str = Field(min_length=1, max_length=500)
    raw_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_kinds: tuple[str, ...]
    candidate_snippets: tuple[str, ...]
    required_fields: tuple[str, ...] = SEC_REVIEW_QUEUE_REQUIRED_FIELDS
    status: Literal["unsupported_candidate"] = "unsupported_candidate"
    automatic_ledger_application: Literal[False] = False


class SecReviewPriorityPacket(BaseModel):
    """Priority catalog that is a subset of the full SEC review queue."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    items: tuple[SecReviewPriorityItem, ...] = Field(min_length=1, max_length=100)
    automatic_ledger_application: Literal[False] = False
    operator_review_required: Literal[True] = True
    schema_version: Literal[1] = 1
    status: Literal["unsupported_candidate"] = "unsupported_candidate"


class SecActionReviewFormItem(BaseModel):
    """One operator-supplied action review row; never an approved ledger event."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: str = Field(pattern=r"^[A-Z0-9][A-Z0-9.\-/]{0,19}$")
    accession_number: str = Field(pattern=r"^\d{10}-\d{2}-\d{6}$")
    review_key: str = Field(pattern=r"^sec:\d{10}-\d{2}-\d{6}:(split|dividend)$")
    source_url: str = Field(min_length=1, max_length=500)
    raw_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    required_fields: tuple[str, ...] = SEC_REVIEW_QUEUE_REQUIRED_FIELDS
    operator_verified: bool = False
    automatic_ledger_application: Literal[False] = False
    revision_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    content_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    manual_classification: str | None = Field(
        default=None, min_length=1, max_length=200
    )
    event_type: Literal["split", "dividend"] | None = None
    pit_link: str | None = Field(default=None, min_length=1, max_length=2000)
    extracted_facts: ExtractedFacts = ExtractedFacts()


class SecActionReviewForm(BaseModel):
    """Batch operator form that must pass validation before a ReviewManifest."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    status: Literal["operator_input_required"] = "operator_input_required"
    items: tuple[SecActionReviewFormItem, ...] = Field(min_length=1, max_length=100)


class SecActionReviewFormValidation(BaseModel):
    """Fail-closed form readiness; readiness is not action approval."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    form_items: int = Field(ge=1, le=100)
    source_verified_items: int = Field(ge=0, le=100)
    missing_fields: dict[str, tuple[str, ...]] = {}
    reference_missing_accessions: tuple[str, ...] = ()
    reference_unexpected_accessions: tuple[str, ...] = ()
    source_missing_accessions: tuple[str, ...] = ()
    source_sha_mismatch_accessions: tuple[str, ...] = ()
    ready: bool
    automatic_ledger_application: Literal[False] = False


def build_sec_review_queue(
    candidates: Iterable[SecFilingCandidate],
    *,
    filing_symbols: Mapping[str, str],
) -> SecReviewQueue:
    """Bind SEC candidates to tickers without inferring action facts."""
    items: list[SecReviewQueueItem] = []
    seen_accessions: set[str] = set()
    for candidate in candidates:
        symbol = filing_symbols.get(candidate.cik)
        if symbol is None:
            raise ValueError("sec_review_queue_symbol_missing")
        symbol = symbol.upper()
        if candidate.accession_number in seen_accessions:
            raise ValueError("sec_review_queue_duplicate_accession")
        seen_accessions.add(candidate.accession_number)
        items.append(
            SecReviewQueueItem(
                symbol=symbol,
                accession_number=candidate.accession_number,
                source_url=candidate.source_url,
                raw_sha256=candidate.raw_sha256,
                candidate_kinds=tuple(candidate.candidate_kinds),
                candidate_snippets=tuple(candidate.candidate_snippets),
            )
        )
    if not items:
        raise ValueError("sec_review_queue_empty")
    return SecReviewQueue(
        items=tuple(
            sorted(items, key=lambda item: (item.symbol, item.accession_number))
        )
    )


def verify_sec_review_queue_sources(
    queue: SecReviewQueue,
    *,
    candidate_dir: Path,
    max_source_bytes: int = 10 * 1024 * 1024,
) -> SecReviewQueueSourceVerification:
    """Verify every queue item has a bounded, hash-matching local raw filing.

    This function is read-only and deliberately does not approve a candidate or
    enable ledger application.  A queue is not source-ready when any accession
    is absent or its stored bytes do not match the queue hash.
    """
    if max_source_bytes < 1:
        raise ValueError("sec_review_source_size_limit_invalid")
    if candidate_dir.is_symlink() or not candidate_dir.is_dir():
        raise ValueError("sec_review_source_dir_missing")
    missing: list[str] = []
    mismatched: list[str] = []
    verified = 0
    for item in queue.items:
        matches = sorted(
            candidate_dir.glob(f"sec-filing-{item.accession_number}-*.html")
        )
        valid_hash = False
        for path in matches:
            if path.is_symlink() or not path.is_file():
                continue
            try:
                if path.stat().st_size > max_source_bytes:
                    continue
                body = path.read_bytes()
            except OSError:
                continue
            if (
                len(body) <= max_source_bytes
                and hashlib.sha256(body).hexdigest() == item.raw_sha256
            ):
                valid_hash = True
                break
        if valid_hash:
            verified += 1
        elif matches:
            mismatched.append(item.accession_number)
        else:
            missing.append(item.accession_number)
    return SecReviewQueueSourceVerification(
        queue_items=len(queue.items),
        verified_items=verified,
        missing_accessions=tuple(missing),
        sha_mismatch_accessions=tuple(mismatched),
        ready=verified == len(queue.items),
    )


def load_sec_action_review_form(path: Path) -> SecActionReviewForm:
    """Load a bounded batch form without treating it as an approved manifest."""
    try:
        body = path.read_bytes()
    except OSError as exc:
        raise ValueError("sec_action_review_form_unavailable") from exc
    if len(body) > MAX_SEC_REVIEW_QUEUE_BYTES:
        raise ValueError("sec_action_review_form_too_large")
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("sec_action_review_form_invalid") from exc
    try:
        return SecActionReviewForm.model_validate(payload)
    except ValueError as exc:
        raise ValueError("sec_action_review_form_invalid") from exc


def validate_sec_action_review_form(
    form: SecActionReviewForm,
    *,
    candidate_dir: Path,
    reference_queue: SecReviewQueue,
    max_source_bytes: int = MAX_SEC_REVIEW_EVIDENCE_BYTES,
) -> SecActionReviewFormValidation:
    """Validate a filled batch form and its raw files, without approving actions."""
    if max_source_bytes < 1:
        raise ValueError("sec_action_review_source_size_limit_invalid")
    if candidate_dir.is_symlink() or not candidate_dir.is_dir():
        raise ValueError("sec_action_review_source_dir_missing")
    missing: dict[str, tuple[str, ...]] = {}
    source_missing: list[str] = []
    source_mismatch: list[str] = []
    source_verified = 0
    reference_items = {
        item.accession_number: item for item in reference_queue.items
    }
    form_accessions = {item.accession_number for item in form.items}
    reference_missing = tuple(sorted(set(reference_items) - form_accessions))
    reference_unexpected = tuple(sorted(form_accessions - set(reference_items)))
    seen_accessions: set[str] = set()
    seen_review_keys: set[str] = set()
    for item in form.items:
        key = item.review_key
        missing_fields: list[str] = []
        kind = key.rsplit(":", 1)[-1]
        if item.accession_number in seen_accessions:
            missing_fields.append("duplicate_accession_number")
        seen_accessions.add(item.accession_number)
        reference = reference_items.get(item.accession_number)
        if reference is None:
            missing_fields.append("reference_queue_item")
        else:
            if item.symbol != reference.symbol:
                missing_fields.append("symbol_reference")
            if item.source_url != reference.source_url:
                missing_fields.append("source_url_reference")
            if item.raw_sha256 != reference.raw_sha256:
                missing_fields.append("raw_sha256_reference")
            if item.required_fields != reference.required_fields:
                missing_fields.append("required_fields_reference")
        try:
            EvidenceInput(
                local_file=Path("."),
                sha256=item.raw_sha256,
                source_url=item.source_url,
                publisher="SEC",
                locator=item.accession_number,
                captured_at=datetime(1970, 1, 1, tzinfo=UTC),
            )
        except ValueError:
            missing_fields.append("source_url_format")
        if key in seen_review_keys:
            missing_fields.append("duplicate_review_key")
        seen_review_keys.add(key)
        if item.review_key != f"sec:{item.accession_number}:{kind}":
            missing_fields.append("review_key_identity")
        if item.event_type != kind:
            missing_fields.append("event_type")
        if not item.operator_verified:
            missing_fields.append("operator_verified")
        if item.revision_id is None:
            missing_fields.append("revision_id")
        if item.content_sha256 is None:
            missing_fields.append("content_sha256")
        if item.manual_classification is None:
            missing_fields.append("manual_classification")
        if item.pit_link is None:
            missing_fields.append("pit_link")
        facts = item.extracted_facts
        if kind == "dividend":
            required_facts: tuple[tuple[str, object], ...] = (
                ("amount", facts.amount),
                ("currency", facts.currency),
                ("ex_dividend_date", facts.ex_dividend_date),
                ("comparable_share_basis", facts.comparable_share_basis),
            )
        else:
            required_facts = (
                ("numerator", facts.numerator),
                ("denominator", facts.denominator),
                ("legal_effective_date", facts.legal_effective_date),
                ("comparable_share_basis", facts.comparable_share_basis),
            )
        missing_fields.extend(name for name, value in required_facts if value is None)
        matches = sorted(
            candidate_dir.glob(f"sec-filing-{item.accession_number}-*.html")
        )
        valid_hash = False
        for path in matches:
            if path.is_symlink() or not path.is_file():
                continue
            try:
                if path.stat().st_size > max_source_bytes:
                    continue
                body = path.read_bytes()
            except OSError:
                continue
            if (
                len(body) <= max_source_bytes
                and hashlib.sha256(body).hexdigest() == item.raw_sha256
            ):
                valid_hash = True
                break
        if valid_hash:
            source_verified += 1
        elif matches:
            source_mismatch.append(item.accession_number)
        else:
            source_missing.append(item.accession_number)
        if missing_fields:
            missing[key] = tuple(sorted(set(missing_fields)))
    ready = (
        source_verified == len(form.items)
        and not reference_missing
        and not reference_unexpected
        and not source_missing
        and not source_mismatch
        and not missing
    )
    return SecActionReviewFormValidation(
        form_items=len(form.items),
        source_verified_items=source_verified,
        missing_fields=missing,
        reference_missing_accessions=reference_missing,
        reference_unexpected_accessions=reference_unexpected,
        source_missing_accessions=tuple(source_missing),
        source_sha_mismatch_accessions=tuple(source_mismatch),
        ready=ready,
    )


def load_sec_review_queue(path: Path) -> SecReviewQueue:
    """Load a bounded queue file for offline source verification."""
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ValueError("sec_review_queue_unavailable") from exc
    if len(raw) > MAX_SEC_REVIEW_QUEUE_BYTES:
        raise ValueError("sec_review_queue_too_large")
    try:
        return SecReviewQueue.model_validate_json(raw)
    except ValueError as exc:
        raise ValueError("sec_review_queue_invalid") from exc


def load_sec_review_reference_queue(path: Path) -> SecReviewQueue:
    """Load either the full queue or the bounded priority catalog as a queue."""
    try:
        body = path.read_bytes()
    except OSError as exc:
        raise ValueError("sec_review_reference_unavailable") from exc
    if len(body) > MAX_SEC_REVIEW_QUEUE_BYTES:
        raise ValueError("sec_review_reference_too_large")
    try:
        payload = json.loads(body)
        try:
            return SecReviewQueue.model_validate(payload)
        except ValueError:
            packet = SecReviewPriorityPacket.model_validate(payload)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError("sec_review_reference_invalid") from exc
    return SecReviewQueue(
        items=tuple(
            SecReviewQueueItem(
                symbol=item.symbol,
                accession_number=item.accession_number,
                source_url=item.source_url,
                raw_sha256=item.raw_sha256,
                candidate_kinds=item.candidate_kinds,
                candidate_snippets=item.candidate_snippets,
                required_fields=item.required_fields,
            )
            for item in packet.items
        )
    )


_FILING_CANDIDATE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("dividend", re.compile(r"\bdividend(?:s|ed)?\b", re.I)),
    ("split", re.compile(r"\b(?:stock|reverse)\s+split\b", re.I)),
    ("merger", re.compile(r"\bmerger|acquisition|business combination\b", re.I)),
    ("delisting", re.compile(r"\bdelist(?:ed|ing)?\b", re.I)),
    ("suspension", re.compile(r"\bsuspend(?:ed|sion)?\b", re.I)),
)


def filing_document_url(filing: SecFiling) -> str:
    if not filing.primary_document:
        raise ValueError("sec_filing_primary_document_missing")
    accession = filing.accession_number.replace("-", "")
    return (
        f"https://www.sec.gov/Archives/edgar/data/{int(filing.cik)}/"
        f"{accession}/{filing.primary_document}"
    )


def parse_sec_filing_candidate(
    body: bytes, *, filing: SecFiling, observed_at: datetime, source_url: str
) -> SecFilingCandidate:
    try:
        text = body.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError("sec_filing_invalid_utf8") from exc
    matches = [
        (kind, match)
        for kind, pattern in _FILING_CANDIDATE_PATTERNS
        if (match := pattern.search(text)) is not None
    ]
    snippets = tuple(
        " ".join(text[max(0, match.start() - 100) : match.end() + 140].split())
        for _, match in matches[:3]
    )
    return SecFilingCandidate(
        cik=filing.cik,
        accession_number=filing.accession_number,
        form=filing.form,
        source_url=source_url,
        observed_at=observed_at,
        raw_sha256=hashlib.sha256(body).hexdigest(),
        candidate_kinds=tuple(kind for kind, _ in matches),
        candidate_snippets=snippets,
    )


def build_sec_action_review_input(
    candidate: SecFilingCandidate,
    *,
    local_file: Path,
    extracted_facts: ExtractedFacts,
    operator_verified: bool,
    revision_id: str,
    content_sha256: str,
) -> ReviewInput:
    """Build a manually verified action-review input; never infer facts."""
    if not operator_verified:
        raise ValueError("sec_candidate_operator_verification_required")
    if not re.fullmatch(r"[0-9a-f]{64}", revision_id):
        raise ValueError("sec_candidate_collection_revision_invalid")
    if not re.fullmatch(r"[0-9a-f]{64}", content_sha256):
        raise ValueError("sec_candidate_collection_content_hash_invalid")
    try:
        if local_file.is_symlink() or not local_file.is_file():
            raise ValueError("sec_candidate_evidence_file_missing")
        if local_file.stat().st_size > MAX_SEC_REVIEW_EVIDENCE_BYTES:
            raise ValueError("sec_candidate_evidence_file_too_large")
        with local_file.open("rb") as source:
            body = source.read(MAX_SEC_REVIEW_EVIDENCE_BYTES + 1)
    except OSError as exc:
        raise ValueError("sec_candidate_evidence_file_unavailable") from exc
    if len(body) > MAX_SEC_REVIEW_EVIDENCE_BYTES:
        raise ValueError("sec_candidate_evidence_file_too_large")
    if hashlib.sha256(body).hexdigest() != candidate.raw_sha256:
        raise ValueError("sec_candidate_evidence_hash_mismatch")
    kinds = tuple(
        kind for kind in candidate.candidate_kinds if kind in {"split", "dividend"}
    )
    if len(kinds) != 1 or len(candidate.candidate_kinds) != 1:
        raise ValueError("sec_candidate_action_kind_unresolved")
    kind = kinds[0]
    return ReviewInput(
        review_key=f"sec:{candidate.accession_number}:{kind}",
        revision_id=revision_id,
        content_sha256=content_sha256,
        operator_verified=True,
        evidence=EvidenceInput(
            local_file=local_file,
            sha256=candidate.raw_sha256,
            source_url=candidate.source_url,
            publisher="SEC EDGAR",
            locator=candidate.accession_number,
            captured_at=candidate.observed_at,
        ),
        extracted_facts=extracted_facts,
    )


def build_sec_review_manifest(
    candidates: Iterable[SecFilingCandidate],
    *,
    local_files: Mapping[str, Path],
    extracted_facts: Mapping[str, ExtractedFacts],
    revision_ids: Mapping[str, str],
    content_hashes: Mapping[str, str],
    operator_verified: bool,
) -> ReviewManifest:
    """Create a review manifest only from complete, manually supplied facts."""
    reviews: list[ReviewInput] = []
    for candidate in candidates:
        accession = candidate.accession_number
        if (
            accession not in local_files
            or accession not in extracted_facts
            or accession not in revision_ids
            or accession not in content_hashes
        ):
            raise ValueError("sec_candidate_review_facts_missing")
        reviews.append(
            build_sec_action_review_input(
                candidate,
                local_file=local_files[accession],
                extracted_facts=extracted_facts[accession],
                operator_verified=operator_verified,
                revision_id=revision_ids[accession],
                content_sha256=content_hashes[accession],
            )
        )
    if not reviews:
        raise ValueError("sec_candidate_review_manifest_empty")
    return ReviewManifest(schema_version=1, reviews=reviews)


def parse_sec_ticker_map(
    body: bytes, *, symbols: Iterable[str] | None = None
) -> tuple[SecTicker, ...]:
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("sec_ticker_map_invalid_json") from exc
    if not isinstance(payload, Mapping):
        raise ValueError("sec_ticker_map_invalid_root")
    wanted = {item.upper() for item in symbols} if symbols is not None else None
    result: list[SecTicker] = []
    for value in payload.values():
        if not isinstance(value, Mapping):
            continue
        ticker = value.get("ticker")
        cik_value = value.get("cik_str")
        title = value.get("title")
        if not isinstance(ticker, str) or not isinstance(title, str):
            continue
        ticker = ticker.upper()
        if wanted is not None and ticker not in wanted:
            continue
        try:
            cik = str(cik_value).zfill(10)
        except (TypeError, ValueError):
            continue
        if len(cik) != 10 or not cik.isdigit():
            continue
        result.append(SecTicker(ticker=ticker, cik=cik, title=title))
    return tuple(sorted(result, key=lambda item: item.ticker))


def _string_at(values: object, index: int) -> str | None:
    if not isinstance(values, list) or index >= len(values):
        return None
    value = values[index]
    return value if isinstance(value, str) and value else None


def _parse_acceptance(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        if normalized.isdigit() and len(normalized) == 14:
            eastern = datetime.strptime(normalized, "%Y%m%d%H%M%S").replace(
                tzinfo=ZoneInfo("America/New_York")
            )
            return eastern.astimezone(UTC)
        return _utc(datetime.fromisoformat(normalized))
    except ValueError:
        return None


def parse_sec_submissions(
    body: bytes, *, observed_at: datetime, source_url: str
) -> tuple[SecFiling, ...]:
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("sec_submissions_invalid_json") from exc
    if not isinstance(payload, Mapping):
        raise ValueError("sec_submissions_invalid_root")
    cik_value = payload.get("cik")
    cik = str(cik_value).zfill(10) if isinstance(cik_value, (str, int)) else ""
    recent = payload.get("filings")
    recent = recent.get("recent") if isinstance(recent, Mapping) else None
    if not cik or not isinstance(recent, Mapping):
        raise ValueError("sec_submissions_recent_missing")
    forms = recent.get("form")
    accessions = recent.get("accessionNumber")
    filing_dates = recent.get("filingDate")
    acceptance = recent.get("acceptanceDateTime")
    documents = recent.get("primaryDocument")
    if not all(isinstance(item, list) for item in (forms, accessions, filing_dates)):
        raise ValueError("sec_submissions_columns_missing")
    assert isinstance(forms, list)
    assert isinstance(accessions, list)
    assert isinstance(filing_dates, list)
    count = min(len(forms), len(accessions), len(filing_dates))
    observed = _utc(observed_at)
    digest = hashlib.sha256(body).hexdigest()
    result: list[SecFiling] = []
    for index in range(count):
        form = _string_at(forms, index)
        accession_number = _string_at(accessions, index)
        filing_date = _string_at(filing_dates, index)
        if form is None or accession_number is None or filing_date is None:
            continue
        if not revalidate_accession(accession_number):
            continue
        result.append(
            SecFiling(
                cik=cik,
                accession_number=accession_number,
                form=form,
                filing_date=filing_date,
                acceptance_datetime=_parse_acceptance(_string_at(acceptance, index)),
                primary_document=_string_at(documents, index),
                source_url=source_url,
                observed_at=observed,
                raw_sha256=digest,
            )
        )
    return tuple(result)


def revalidate_accession(value: str) -> bool:
    parts = value.split("-")
    return (
        len(parts) == 3
        and len(parts[0]) == 10
        and len(parts[1]) == 2
        and len(parts[2]) == 6
        and all(part.isdigit() for part in parts)
    )


async def collect_sec_submissions(
    *,
    ciks: Iterable[str],
    output_dir: Path,
    user_agent: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> tuple[SecFiling, ...]:
    agent = user_agent or os.environ.get("SEC_USER_AGENT")
    if not agent:
        raise ValueError("SEC_USER_AGENT is required")
    owns_client = client is None
    http_client = client or httpx.AsyncClient(timeout=30)
    output_dir.mkdir(parents=True, exist_ok=True)
    result: list[SecFiling] = []
    try:
        for index, raw_cik in enumerate(ciks):
            cik = str(raw_cik).zfill(10)
            if not cik.isdigit() or len(cik) != 10:
                raise ValueError("cik_invalid")
            if index:
                await asyncio.sleep(SEC_MIN_REQUEST_INTERVAL_SECONDS)
            url = SEC_SUBMISSIONS_URL.format(cik=cik)
            response = await http_client.get(
                url,
                headers={"User-Agent": agent, "Accept": "application/json"},
            )
            response.raise_for_status()
            observed = datetime.now(UTC)
            digest = hashlib.sha256(response.content).hexdigest()
            raw_path = output_dir / f"sec-submissions-{cik}-{digest}.json"
            if not raw_path.exists():
                raw_path.write_bytes(response.content)
            result.extend(
                parse_sec_submissions(
                    response.content, observed_at=observed, source_url=url
                )
            )
    finally:
        if owns_client:
            await http_client.aclose()
    return tuple(result)


async def collect_sec_ticker_map(
    *,
    output_dir: Path,
    symbols: Iterable[str] | None = None,
    user_agent: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> tuple[SecTicker, ...]:
    agent = user_agent or os.environ.get("SEC_USER_AGENT")
    if not agent:
        raise ValueError("SEC_USER_AGENT is required")
    owns_client = client is None
    http_client = client or httpx.AsyncClient(timeout=30)
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        response = await http_client.get(
            SEC_TICKER_MAP_URL,
            headers={"User-Agent": agent, "Accept": "application/json"},
        )
        response.raise_for_status()
        digest = hashlib.sha256(response.content).hexdigest()
        raw_path = output_dir / f"sec-company-tickers-{digest}.json"
        if not raw_path.exists():
            raw_path.write_bytes(response.content)
        return parse_sec_ticker_map(response.content, symbols=symbols)
    finally:
        if owns_client:
            await http_client.aclose()


async def collect_sec_filing_candidates(
    *,
    filings: Iterable[SecFiling],
    output_dir: Path,
    max_documents: int = 20,
    user_agent: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> tuple[SecFilingCandidate, ...]:
    """Fetch a bounded set of primary documents as non-authoritative candidates."""
    if max_documents < 1:
        raise ValueError("max_documents_must_be_positive")
    agent = user_agent or os.environ.get("SEC_USER_AGENT")
    if not agent:
        raise ValueError("SEC_USER_AGENT is required")
    owns_client = client is None
    http_client = client or httpx.AsyncClient(timeout=30)
    output_dir.mkdir(parents=True, exist_ok=True)
    result: list[SecFilingCandidate] = []
    try:
        eligible = (
            filing
            for filing in filings
            if filing.primary_document and filing.form in {"8-K", "8-K/A"}
        )
        for index, filing in enumerate(eligible):
            if index >= max_documents:
                break
            if index:
                await asyncio.sleep(SEC_MIN_REQUEST_INTERVAL_SECONDS)
            source_url = filing_document_url(filing)
            response = await http_client.get(
                source_url,
                headers={"User-Agent": agent, "Accept": "text/html"},
            )
            response.raise_for_status()
            observed = datetime.now(UTC)
            digest = hashlib.sha256(response.content).hexdigest()
            raw_path = (
                output_dir / f"sec-filing-{filing.accession_number}-{digest}.html"
            )
            if not raw_path.exists():
                raw_path.write_bytes(response.content)
            result.append(
                parse_sec_filing_candidate(
                    response.content,
                    filing=filing,
                    observed_at=observed,
                    source_url=source_url,
                )
            )
    finally:
        if owns_client:
            await http_client.aclose()
    return tuple(result)


def _main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect SEC filing evidence")
    parser.add_argument("--cik", action="append")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--verify-queue", type=Path)
    parser.add_argument("--candidate-dir", type=Path)
    parser.add_argument("--validate-review-form", type=Path)
    parser.add_argument("--review-candidate-dir", type=Path)
    parser.add_argument("--review-reference-queue", type=Path)
    args = parser.parse_args(argv)
    if args.validate_review_form is not None:
        if (
            args.cik
            or args.output_dir is not None
            or args.verify_queue is not None
            or args.candidate_dir is not None
            or args.review_candidate_dir is None
            or args.review_reference_queue is None
        ):
            parser.error(
                "--validate-review-form requires --review-candidate-dir and "
                "--review-reference-queue and cannot "
                "be combined with collection or queue verification arguments"
            )
        try:
            form_report = validate_sec_action_review_form(
                load_sec_action_review_form(args.validate_review_form),
                candidate_dir=args.review_candidate_dir,
                reference_queue=load_sec_review_reference_queue(
                    args.review_reference_queue
                ),
            )
        except (OSError, ValueError):
            print("SEC action review form validation failed", file=sys.stderr)
            return 1
        print(json.dumps(form_report.model_dump(mode="json"), sort_keys=True))
        return 0 if form_report.ready else 2
    if args.verify_queue is not None:
        if args.cik or args.output_dir is not None or args.candidate_dir is None:
            parser.error(
                "--verify-queue requires --candidate-dir and cannot be combined "
                "with collection arguments"
            )
        try:
            queue = load_sec_review_queue(args.verify_queue)
            report = verify_sec_review_queue_sources(
                queue, candidate_dir=args.candidate_dir
            )
        except (OSError, ValueError):
            print("SEC review queue verification failed", file=sys.stderr)
            return 1
        print(json.dumps(report.model_dump(mode="json"), sort_keys=True))
        return 0 if report.ready else 2
    if not args.cik or args.output_dir is None or args.candidate_dir is not None:
        parser.error("collection requires --cik and --output-dir")
    filings = asyncio.run(
        collect_sec_submissions(ciks=args.cik, output_dir=args.output_dir)
    )
    print(f"collected_filings={len(filings)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
