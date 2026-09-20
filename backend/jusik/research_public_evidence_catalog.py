"""Fail-closed catalog joining public evidence from independent providers."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import date, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from jusik.research_alpha_actions import AlphaAction
from jusik.research_public_evidence import NasdaqHalt
from jusik.research_sec_evidence import SecFiling


class PublicEvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source: Literal["alpha_vantage", "nasdaq_trader", "sec_edgar"]
    instrument_ref: str = Field(min_length=1, max_length=40)
    event_kind: str = Field(min_length=1, max_length=40)
    event_date: date
    observed_at: datetime
    source_url: str = Field(min_length=1, max_length=500)
    raw_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("observed_at")
    @classmethod
    def observed_at_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("observed_at_must_be_timezone_aware")
        return value


class PublicEvidenceCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    requested_symbols: tuple[str, ...]
    requested_start: date
    requested_end: date
    coverage: Literal["incomplete"] = "incomplete"
    unresolved_symbols: tuple[str, ...] = ()
    items: tuple[PublicEvidenceItem, ...]
    source_counts: dict[str, int]
    observed_item_count: int = Field(ge=0)
    catalog_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


PUBLIC_EVIDENCE_SOURCES = ("alpha_vantage", "nasdaq_trader", "sec_edgar")


class SymbolEvidenceCoverage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_counts: dict[str, int]
    missing_sources: tuple[str, ...]


class PublicEvidenceSymbolCoverage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    catalog_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    requested_symbols: tuple[str, ...]
    requested_start: date
    requested_end: date
    unresolved_symbols: tuple[str, ...]
    coverage: Literal["incomplete"] = "incomplete"
    economic_acceptance: Literal[False] = False
    pit_proof: Literal[False] = False
    symbols: dict[str, SymbolEvidenceCoverage]


def public_evidence_catalog_sha256(catalog: PublicEvidenceCatalog) -> str:
    """Return the canonical digest over catalog content excluding its digest."""
    payload = catalog.model_dump(mode="json", exclude={"catalog_sha256"})
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def verify_public_evidence_catalog(catalog: PublicEvidenceCatalog) -> None:
    """Reject tampered or internally inconsistent public evidence catalogs."""
    if public_evidence_catalog_sha256(catalog) != catalog.catalog_sha256:
        raise ValueError("catalog_sha_mismatch")
    if catalog.observed_item_count != len(catalog.items):
        raise ValueError("catalog_item_count_mismatch")
    counts: dict[str, int] = {}
    for item in catalog.items:
        counts[item.source] = counts.get(item.source, 0) + 1
    if dict(sorted(counts.items())) != dict(sorted(catalog.source_counts.items())):
        raise ValueError("catalog_source_count_mismatch")


def _require_requested_symbol(symbol: str, requested: tuple[str, ...]) -> None:
    if symbol not in requested:
        raise ValueError("evidence_symbol_not_requested")


def build_public_evidence_catalog(
    *,
    symbols: tuple[str, ...],
    start: date,
    end: date,
    halts: tuple[NasdaqHalt, ...] = (),
    filings: tuple[SecFiling, ...] = (),
    actions: tuple[AlphaAction, ...] = (),
    filing_symbols: Mapping[str, str] | None = None,
    unresolved_symbols: tuple[str, ...] = (),
) -> PublicEvidenceCatalog:
    if end < start:
        raise ValueError("end_before_start")
    requested = tuple(sorted(set(symbols)))
    unresolved = tuple(sorted(set(unresolved_symbols)))
    if any(symbol not in requested for symbol in unresolved):
        raise ValueError("unresolved_symbol_not_requested")
    items: list[PublicEvidenceItem] = []
    for halt in halts:
        _require_requested_symbol(halt.symbol, requested)
        if start <= halt.halt_date <= end:
            items.append(
                PublicEvidenceItem(
                    source="nasdaq_trader",
                    instrument_ref=halt.symbol,
                    event_kind="trading_halt",
                    event_date=halt.halt_date,
                    observed_at=halt.observed_at,
                    source_url=halt.source_url,
                    raw_sha256=halt.raw_sha256,
                )
            )
    for filing in filings:
        filing_symbol = (
            filing_symbols.get(filing.cik, filing.cik)
            if filing_symbols is not None
            else filing.cik
        )
        _require_requested_symbol(filing_symbol, requested)
        filing_date = date.fromisoformat(filing.filing_date)
        if start <= filing_date <= end:
            items.append(
                PublicEvidenceItem(
                    source="sec_edgar",
                    instrument_ref=filing_symbol,
                    event_kind=filing.form,
                    event_date=filing_date,
                    observed_at=filing.acceptance_datetime or filing.observed_at,
                    source_url=filing.source_url,
                    raw_sha256=filing.raw_sha256,
                )
            )
    for action in actions:
        _require_requested_symbol(action.symbol, requested)
        if start <= action.event_date <= end:
            items.append(
                PublicEvidenceItem(
                    source="alpha_vantage",
                    instrument_ref=action.symbol,
                    event_kind=action.kind,
                    event_date=action.event_date,
                    observed_at=action.observed_at,
                    source_url=action.source_url,
                    raw_sha256=action.raw_sha256,
                )
            )
    unique = {
        (
            item.source,
            item.instrument_ref,
            item.event_kind,
            item.event_date,
            item.raw_sha256,
        ): item
        for item in items
    }
    ordered = tuple(
        sorted(
            unique.values(),
            key=lambda item: (
                item.event_date,
                item.source,
                item.instrument_ref,
                item.event_kind,
                item.raw_sha256,
            ),
        )
    )
    counts: dict[str, int] = {}
    for evidence_item in ordered:
        counts[evidence_item.source] = counts.get(evidence_item.source, 0) + 1
    provisional = {
        "schema_version": 1,
        "requested_symbols": requested,
        "requested_start": start.isoformat(),
        "requested_end": end.isoformat(),
        "coverage": "incomplete",
        "unresolved_symbols": unresolved,
        "items": [item.model_dump(mode="json") for item in ordered],
        "source_counts": dict(sorted(counts.items())),
        "observed_item_count": len(ordered),
    }
    digest = hashlib.sha256(
        json.dumps(provisional, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return PublicEvidenceCatalog(
        **provisional,
        catalog_sha256=digest,
    )


def build_public_evidence_symbol_coverage(
    catalog: PublicEvidenceCatalog,
) -> PublicEvidenceSymbolCoverage:
    """Summarize observed source rows per requested symbol without promotion."""
    verify_public_evidence_catalog(catalog)
    requested = tuple(catalog.requested_symbols)
    if requested != tuple(sorted(set(requested))):
        raise ValueError("catalog_requested_symbols_not_canonical")
    counts = {
        symbol: {source: 0 for source in PUBLIC_EVIDENCE_SOURCES}
        for symbol in requested
    }
    for item in catalog.items:
        if item.instrument_ref not in counts:
            raise ValueError("catalog_item_symbol_not_requested")
        if item.source not in PUBLIC_EVIDENCE_SOURCES:
            raise ValueError("catalog_item_source_not_supported")
        counts[item.instrument_ref][item.source] += 1
    symbols = {
        symbol: SymbolEvidenceCoverage(
            source_counts=counts[symbol],
            missing_sources=tuple(
                source
                for source in PUBLIC_EVIDENCE_SOURCES
                if counts[symbol][source] == 0
            ),
        )
        for symbol in requested
    }
    return PublicEvidenceSymbolCoverage(
        catalog_sha256=catalog.catalog_sha256,
        requested_symbols=requested,
        requested_start=catalog.requested_start,
        requested_end=catalog.requested_end,
        unresolved_symbols=catalog.unresolved_symbols,
        symbols=symbols,
    )


def write_catalog(catalog: PublicEvidenceCatalog, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(catalog.model_dump_json(indent=2) + "\n", encoding="utf-8")


def write_symbol_coverage(
    report: PublicEvidenceSymbolCoverage, path: Path
) -> None:
    """Write a deterministic symbol coverage report without changing its status."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
