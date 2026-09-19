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
    for item in halts:
        if start <= item.halt_date <= end:
            items.append(
                PublicEvidenceItem(
                    source="nasdaq_trader",
                    instrument_ref=item.symbol,
                    event_kind="trading_halt",
                    event_date=item.halt_date,
                    observed_at=item.observed_at,
                    source_url=item.source_url,
                    raw_sha256=item.raw_sha256,
                )
            )
    for item in filings:
        filing_date = date.fromisoformat(item.filing_date)
        if start <= filing_date <= end:
            items.append(
                PublicEvidenceItem(
                    source="sec_edgar",
                    instrument_ref=(
                        filing_symbols.get(item.cik, item.cik)
                        if filing_symbols is not None
                        else item.cik
                    ),
                    event_kind=item.form,
                    event_date=filing_date,
                    observed_at=item.acceptance_datetime or item.observed_at,
                    source_url=item.source_url,
                    raw_sha256=item.raw_sha256,
                )
            )
    for item in actions:
        if start <= item.event_date <= end:
            items.append(
                PublicEvidenceItem(
                    source="alpha_vantage",
                    instrument_ref=item.symbol,
                    event_kind=item.kind,
                    event_date=item.event_date,
                    observed_at=item.observed_at,
                    source_url=item.source_url,
                    raw_sha256=item.raw_sha256,
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
    for item in ordered:
        counts[item.source] = counts.get(item.source, 0) + 1
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


def write_catalog(catalog: PublicEvidenceCatalog, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(catalog.model_dump_json(indent=2) + "\n", encoding="utf-8")
