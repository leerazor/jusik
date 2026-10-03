"""Read-only collection metadata for the registered research universe.

These observations do not establish instrument identity or comparison eligibility.
"""

from __future__ import annotations

import re
import sqlite3
from contextlib import closing
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from jusik.approved_universe import ApprovedInstrument, ApprovedUniverseSnapshot

SourceStatus = Literal["available", "unavailable"]
PriceStatus = Literal["missing", "success", "stale", "error", "unavailable"]


class PriceReadiness(BaseModel):
    status: PriceStatus
    identity_status: Literal["not_checked"] = "not_checked"
    requested_start: date | None = None
    requested_end: date | None = None
    actual_start: date | None = None
    actual_end: date | None = None
    evaluation_start: date | None = None
    warmup_bars: int | None = Field(default=None, ge=0)
    evaluation_bars: int | None = Field(default=None, ge=0)
    captured_at: datetime | None = None
    history_warning: bool | None = None


class DividendReadiness(BaseModel):
    status: SourceStatus
    identity_status: Literal["not_checked"] = "not_checked"
    observed_event_count: int | None = None
    reviewed_current_event_count: int | None = None


class FxReadiness(BaseModel):
    status: SourceStatus
    observed_date_count: int | None = None
    first_observed_on: date | None = None
    last_observed_on: date | None = None


class InstrumentReadiness(BaseModel):
    instrument: ApprovedInstrument
    price: PriceReadiness
    dividend: DividendReadiness


class ApprovedUniverseReadiness(BaseModel):
    revision: int
    updated_at: datetime | None
    generated_at: datetime
    comparison_status: Literal["not_performed"] = "not_performed"
    price_source_status: SourceStatus
    dividend_source_status: SourceStatus
    fx: FxReadiness
    instruments: list[InstrumentReadiness]


def _connect_read_only(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(
        f"{path.resolve().as_uri()}?mode=ro", uri=True, timeout=0.1
    )
    connection.row_factory = sqlite3.Row
    return connection


def _price_rows(
    path: Path, symbols: list[str]
) -> tuple[SourceStatus, dict[str, dict[str, Any]]]:
    try:
        with closing(_connect_read_only(path)) as connection:
            if not symbols:
                connection.execute(
                    "SELECT 1 FROM universe_collection_state LIMIT 1"
                ).fetchone()
                return "available", {}
            placeholders = ",".join("?" for _ in symbols)
            rows = connection.execute(
                f"""SELECT c.instrument_id, c.status, c.last_success_at,
                    s.requested_start, s.requested_end, s.actual_start,
                    s.actual_end, s.evaluation_start, s.warmup_bars,
                    s.evaluation_bars
                FROM universe_collection_state c
                LEFT JOIN universe_snapshots s ON s.id=c.snapshot_id
                WHERE c.instrument_id IN ({placeholders})""",
                symbols,
            ).fetchall()
        return "available", {str(row["instrument_id"]): dict(row) for row in rows}
    except (OSError, sqlite3.Error, ValueError, TypeError):
        return "unavailable", {}


def _dividend_counts(
    path: Path, symbols: list[str]
) -> tuple[SourceStatus, dict[str, tuple[int, int]]]:
    try:
        with closing(_connect_read_only(path)) as connection:
            if not symbols:
                connection.execute(
                    "SELECT 1 FROM action_collection_events LIMIT 1"
                ).fetchone()
                return "available", {}
            placeholders = ",".join("?" for _ in symbols)
            rows = connection.execute(
                f"""SELECT e.symbol, COUNT(*) AS observed_count,
                    SUM(CASE WHEN EXISTS (
                        SELECT 1 FROM action_reviews v
                        JOIN action_collection_revisions r ON r.id=v.revision_id
                        WHERE r.event_id=e.id
                          AND r.sequence=e.latest_revision_sequence
                    ) THEN 1 ELSE 0 END) AS reviewed_count
                FROM action_collection_events e
                WHERE e.kind='dividend' AND e.symbol IN ({placeholders})
                GROUP BY e.symbol""",
                symbols,
            ).fetchall()
        return "available", {
            str(row["symbol"]): (int(row["observed_count"]), int(row["reviewed_count"]))
            for row in rows
        }
    except (OSError, sqlite3.Error):
        return "unavailable", {}


def _fx_status(path: Path) -> FxReadiness:
    try:
        with closing(_connect_read_only(path)) as connection:
            rows = connection.execute(
                """SELECT DISTINCT observed_on FROM external_observations
                WHERE series='usdkrw' ORDER BY observed_on LIMIT 10001"""
            ).fetchall()
        if len(rows) > 10000:
            return FxReadiness(status="unavailable")
        dates = []
        for row in rows:
            value = row["observed_on"]
            if not isinstance(value, str) or not re.fullmatch(
                r"\d{4}-\d{2}-\d{2}", value
            ):
                return FxReadiness(status="unavailable")
            dates.append(date.fromisoformat(value))
        return FxReadiness(
            status="available",
            observed_date_count=len(dates),
            first_observed_on=min(dates) if dates else None,
            last_observed_on=max(dates) if dates else None,
        )
    except (OSError, sqlite3.Error, ValueError, TypeError):
        return FxReadiness(status="unavailable")


def _price_readiness(row: dict[str, Any]) -> PriceReadiness:
    status = row.get("status")
    if status not in ("success", "stale", "error"):
        return PriceReadiness(status="unavailable")
    requested_start = row.get("requested_start")
    actual_start = row.get("actual_start")
    evaluation_start = row.get("evaluation_start")
    history_warning = (
        actual_start > requested_start or evaluation_start > requested_start
        if isinstance(requested_start, str)
        and isinstance(actual_start, str)
        and isinstance(evaluation_start, str)
        else None
    )
    try:
        captured_at = row.get("last_success_at")
        if isinstance(captured_at, str):
            parsed = datetime.fromisoformat(captured_at)
            captured_at = parsed if parsed.tzinfo is not None else None
        return PriceReadiness(
            status=status,
            requested_start=requested_start,
            requested_end=row.get("requested_end"),
            actual_start=actual_start,
            actual_end=row.get("actual_end"),
            evaluation_start=evaluation_start,
            warmup_bars=row.get("warmup_bars"),
            evaluation_bars=row.get("evaluation_bars"),
            captured_at=captured_at,
            history_warning=history_warning,
        )
    except (ValueError, TypeError):
        return PriceReadiness(status="unavailable")


def build_approved_universe_readiness(
    snapshot: ApprovedUniverseSnapshot,
    *,
    universe_db_path: Path,
    action_db_path: Path,
    external_db_path: Path,
) -> ApprovedUniverseReadiness:
    """Read each source independently; no cross-database atomic snapshot is implied."""
    symbols = sorted({item.symbol for item in snapshot.instruments})
    price_source_status, prices = _price_rows(universe_db_path, symbols)
    dividend_source_status, dividends = _dividend_counts(action_db_path, symbols)
    fx = _fx_status(external_db_path)
    instruments: list[InstrumentReadiness] = []
    for item in snapshot.instruments:
        row = prices.get(item.symbol)
        if price_source_status == "unavailable":
            price = PriceReadiness(status="unavailable")
        elif row is None:
            price = PriceReadiness(status="missing")
        else:
            price = _price_readiness(row)
        counts = dividends.get(item.symbol, (0, 0))
        dividend = (
            DividendReadiness(
                status="available",
                observed_event_count=counts[0],
                reviewed_current_event_count=counts[1],
            )
            if dividend_source_status == "available"
            else DividendReadiness(status="unavailable")
        )
        instruments.append(
            InstrumentReadiness(instrument=item, price=price, dividend=dividend)
        )
    return ApprovedUniverseReadiness(
        revision=snapshot.revision,
        updated_at=snapshot.updated_at,
        generated_at=datetime.now(UTC),
        price_source_status=price_source_status,
        dividend_source_status=dividend_source_status,
        fx=fx,
        instruments=instruments,
    )
