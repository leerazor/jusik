"""Inventory-only SEC ETF filing coverage reports."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from jusik.research_sec_etf_identity import SecEtfIdentity
from jusik.research_sec_evidence import SecFiling


class SecEtfCoverageReport(BaseModel):
    """A filing inventory, deliberately not a completeness or PIT assertion."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    symbol: str
    cik: str
    requested_start: date
    requested_end: date
    inventory_status: Literal["inventory_only"] = "inventory_only"
    target_filing_count: int = Field(ge=0)
    forms: dict[str, int]
    first_filing_date: date | None
    last_filing_date: date | None
    source_raw_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    identity_raw_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


def build_sec_etf_coverage_report(
    identity: SecEtfIdentity,
    filings: Iterable[SecFiling],
    *,
    start: date,
    end: date,
    source_raw_sha256: str,
) -> SecEtfCoverageReport:
    """Count filings in a bounded period without inferring missing coverage."""
    if end < start:
        raise ValueError("end_before_start")
    if len(source_raw_sha256) != 64 or any(
        character not in "0123456789abcdef" for character in source_raw_sha256
    ):
        raise ValueError("source_raw_sha256_invalid")
    selected: list[SecFiling] = []
    for filing in filings:
        if filing.cik != identity.cik:
            raise ValueError("sec_etf_filing_cik_mismatch")
        filing_date = date.fromisoformat(filing.filing_date)
        if start <= filing_date <= end:
            selected.append(filing)
    counts = Counter(filing.form for filing in selected)
    dates = [date.fromisoformat(filing.filing_date) for filing in selected]
    return SecEtfCoverageReport(
        symbol=identity.symbol,
        cik=identity.cik,
        requested_start=start,
        requested_end=end,
        target_filing_count=len(selected),
        forms=dict(sorted(counts.items())),
        first_filing_date=min(dates) if dates else None,
        last_filing_date=max(dates) if dates else None,
        source_raw_sha256=source_raw_sha256,
        identity_raw_sha256=identity.raw_sha256,
    )


def build_sec_etf_coverage_reports(
    identities: Iterable[SecEtfIdentity],
    filings_by_cik: Mapping[str, Iterable[SecFiling]],
    *,
    start: date,
    end: date,
    source_hashes_by_cik: Mapping[str, str],
) -> tuple[SecEtfCoverageReport, ...]:
    """Build deterministic reports for each supplied identity."""
    reports = [
        build_sec_etf_coverage_report(
            identity,
            filings_by_cik.get(identity.cik, ()),
            start=start,
            end=end,
            source_raw_sha256=source_hashes_by_cik.get(identity.cik, ""),
        )
        for identity in identities
    ]
    return tuple(sorted(reports, key=lambda report: report.symbol))


__all__ = [
    "SecEtfCoverageReport",
    "build_sec_etf_coverage_report",
    "build_sec_etf_coverage_reports",
]
