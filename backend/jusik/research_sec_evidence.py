"""SEC EDGAR filing evidence collector with immutable raw responses."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator

from jusik.research_action_review import (
    ExtractedFacts,
    ReviewInput,
    ReviewManifest,
)

SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_MIN_REQUEST_INTERVAL_SECONDS = 0.2


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
        evidence={
            "local_file": local_file,
            "sha256": candidate.raw_sha256,
            "source_url": candidate.source_url,
            "publisher": "SEC EDGAR",
            "locator": candidate.accession_number,
            "captured_at": candidate.observed_at,
        },
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
    parser.add_argument("--cik", action="append", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    filings = asyncio.run(
        collect_sec_submissions(ciks=args.cik, output_dir=args.output_dir)
    )
    print(f"collected_filings={len(filings)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
