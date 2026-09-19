"""SEC EDGAR filing evidence collector with immutable raw responses."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator

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


def _main(argv: Iterable[str] | None = None) -> int:
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
