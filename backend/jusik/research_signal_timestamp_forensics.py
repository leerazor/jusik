"""Read-only forensic report for persisted PAPER signal timestamps.

The command in this module deliberately reads only an audit archive.  It never
opens the archive's provenance ``source_path`` and it never opens a database
without SQLite's immutable URI flag.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import inspect
import json
import sqlite3
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import jusik.research_universe_data as research_universe_data
from jusik.research_market_calendar import MarketCalendar
from jusik.research_quote_models import ResearchQuote
from jusik.research_signal_validation import (
    _exact_milliseconds,
    _latency_values,
    _symbol_coverage,
)
from jusik.research_universe_data import REGISTRY

DATE = date(2026, 9, 11)
NOW = datetime(2026, 9, 12, 0, 51, 19, 514182, tzinfo=UTC)
DB_RELATIVE = Path("private/forward-snapshot.db")
WAL_RELATIVE = Path("private/forward-snapshot.db-wal")
PROVENANCE_RELATIVE = Path("provenance.json")
REFERENCE_RELATIVE = Path("signal-validation.json")
CODE_RELATIVES = (
    Path("source/jusik/research_signal_validation.py"),
    Path("source/jusik/research_quote_models.py"),
    Path("source/jusik/data/market_sessions_2023_2026.json"),
    Path("source/jusik/research_universe_data.py"),
    Path("source/jusik/research_market_calendar.py"),
)
APPROVED_SNAPSHOT_SHA256 = (
    "7c901a51b7bcf2b2f192760a4b29cdcbf7a4b4ef177db69ca9c5f9146b168c15"
)
APPROVED_WAL_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
APPROVED_PROVENANCE_SHA256 = (
    "b1d1fe25ab6020858c0be9b0f376b56c14306dcd83fe557c326f59716a2b2f93"
)
APPROVED_REFERENCE_SHA256 = (
    "ff01a83263a661302897998468d05363c1916c18839332c0547a37bb268d676e"
)
APPROVED_CODE_SHA256 = {
    "source/jusik/research_signal_validation.py": (
        "3e92f379f715caab2dbd3efd4fa7efc6f00865fe8259ce3706afc9ad04897a1b"
    ),
    "source/jusik/research_quote_models.py": (
        "b082553dadcc87f6a4df473ebeb746071a0d9ed90bce2fc07e25972ed4bf5b61"
    ),
    "source/jusik/data/market_sessions_2023_2026.json": (
        "ba26619a27e066ca32b1aaaf3b7da2b99f0c6658f731a000c5095c057081c1d8"
    ),
    "source/jusik/research_universe_data.py": (
        "9093c4c4c5cb504b9f8526f944b7b85d349cb506a0b1cc54e52283a26ba0d882"
    ),
    "source/jusik/research_market_calendar.py": (
        "edca750738bf69bb58b27ee15a0985a3434707ba1daad06719c26a4d17a54d9a"
    ),
}
CSV_FIELDS = (
    "observation_id",
    "symbol",
    "exchange",
    "source",
    "reason",
    "kind",
    "milliseconds",
    "market_at",
    "received_at",
    "quote_market_at_raw",
    "quote_received_at_raw",
    "db_market_at",
    "db_received_at",
    "utc_hour",
)


class ForensicsError(ValueError):
    """Raised when an archive is incomplete, changed, or unsafe to inspect."""


@dataclass(frozen=True)
class _Input:
    relative: Path
    path: Path


@dataclass(frozen=True)
class _Observation:
    observation_id: str
    symbol: str
    exchange: str
    source: str
    reason: str
    quote_market_at_raw: str
    quote_received_at_raw: str
    db_market_at: str | None
    db_received_at: str | None
    market_at: datetime
    received_at: datetime
    milliseconds: Decimal
    rounded_milliseconds: int
    kind: str | None

    @property
    def utc_hour(self) -> str:
        return (
            self.market_at.astimezone(UTC)
            .replace(minute=0, second=0, microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _fingerprint(inputs: Iterable[_Input]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in inputs:
        try:
            if item.path.is_symlink():
                raise ForensicsError(f"input_symlink_rejected:{item.relative}")
            stat = item.path.stat()
            digest = _sha256(item.path)
        except ForensicsError:
            raise
        except OSError as exc:
            raise ForensicsError(f"input_unreadable:{item.relative}") from exc
        result[item.relative.as_posix()] = {
            "sha256": digest,
            "size": stat.st_size,
        }
    return result


def _read_json(path: Path, relative: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ForensicsError(f"json_unreadable:{relative}") from exc
    if not isinstance(value, dict):
        raise ForensicsError(f"json_object_required:{relative}")
    return value


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _decimal(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def _stats(values: list[int], future: int, stale: int) -> dict[str, Any]:
    return {
        **_latency_values(values, future, stale),
        "median_milliseconds": _decimal(
            _latency_values(values, future, stale)["median_milliseconds"]
        ),
    }


def _stats_from_observations(rows: list[_Observation]) -> dict[str, Any]:
    values = [row.rounded_milliseconds for row in rows]
    return _stats(
        values,
        sum(row.kind == "future" for row in rows),
        sum(row.kind == "stale" for row in rows),
    )


def _instrument_map() -> dict[str, Any]:
    return {item.symbol: item for item in REGISTRY}


def _inputs(archive: Path) -> list[_Input]:
    relatives = [
        DB_RELATIVE,
        WAL_RELATIVE,
        PROVENANCE_RELATIVE,
        REFERENCE_RELATIVE,
        *CODE_RELATIVES,
    ]
    return [_Input(relative, archive / relative) for relative in relatives]


def _guard_output(output: Path, inputs: list[_Input], archive: Path) -> None:
    if output.exists() and output.is_symlink():
        raise ForensicsError("output_symlink_rejected")
    if output.exists() and not output.is_dir():
        raise ForensicsError("output_not_directory")
    input_inodes = {
        (item.path.stat().st_dev, item.path.stat().st_ino) for item in inputs
    }
    if not output.exists():
        return
    for path in output.rglob("*"):
        if path.is_symlink():
            raise ForensicsError("output_symlink_rejected")
        if path.is_file() and (path.stat().st_dev, path.stat().st_ino) in input_inodes:
            raise ForensicsError("output_hardlink_rejected")
        try:
            path.resolve().relative_to(archive)
        except ValueError:
            continue
        raise ForensicsError("output_alias_rejected")


def _validate_archive(
    archive: Path, output: Path, *, allow_unpinned: bool
) -> tuple[list[_Input], dict[str, dict[str, Any]], dict[str, Any], dict[str, Any]]:
    if not archive.is_dir():
        raise ForensicsError("archive_root_missing")
    archive = archive.resolve()
    output = output.resolve()
    try:
        output.relative_to(archive)
    except ValueError:
        pass
    else:
        raise ForensicsError("output_overlaps_archive")
    try:
        archive.relative_to(output)
    except ValueError:
        pass
    else:
        raise ForensicsError("output_overlaps_archive")
    inputs = _inputs(archive)
    for item in inputs:
        if item.path.is_symlink():
            raise ForensicsError(f"input_symlink_rejected:{item.relative}")
        if not item.path.is_file():
            raise ForensicsError(f"input_missing:{item.relative}")
        try:
            item.path.resolve().relative_to(archive)
        except ValueError as exc:
            raise ForensicsError(f"input_path_escape:{item.relative}") from exc
    _guard_output(output, inputs, archive)
    before = _fingerprint(inputs)
    if before[WAL_RELATIVE.as_posix()]["size"] != 0:
        raise ForensicsError("nonempty_wal_rejected")
    provenance = _read_json(archive / PROVENANCE_RELATIVE, "provenance.json")
    reference = _read_json(archive / REFERENCE_RELATIVE, "signal-validation.json")
    if not allow_unpinned:
        pinned = {
            DB_RELATIVE.as_posix(): APPROVED_SNAPSHOT_SHA256,
            WAL_RELATIVE.as_posix(): APPROVED_WAL_SHA256,
            PROVENANCE_RELATIVE.as_posix(): APPROVED_PROVENANCE_SHA256,
            REFERENCE_RELATIVE.as_posix(): APPROVED_REFERENCE_SHA256,
            **APPROVED_CODE_SHA256,
        }
        for pinned_relative, pinned_hash in pinned.items():
            if before[pinned_relative]["sha256"] != pinned_hash:
                raise ForensicsError(f"approved_hash_mismatch:{pinned_relative}")
    if provenance.get("snapshot_sha256") != before[DB_RELATIVE.as_posix()]["sha256"]:
        raise ForensicsError("snapshot_hash_mismatch")
    if (
        provenance.get("snapshot_wal_sha256")
        != before[WAL_RELATIVE.as_posix()]["sha256"]
    ):
        raise ForensicsError("snapshot_wal_hash_mismatch")
    expected_code: dict[str, str] = {}
    for item in provenance.get("code_and_calendar", []):
        if not isinstance(item, dict) or "path" not in item or "sha256" not in item:
            continue
        path_parts = Path(str(item["path"])).parts
        jusik_indices = [
            index for index, part in enumerate(path_parts) if part == "jusik"
        ]
        if not jusik_indices:
            continue
        jusik_index = jusik_indices[-1]
        expected_code["/".join(path_parts[jusik_index:])] = str(item["sha256"])
    for code_relative in CODE_RELATIVES:
        key = code_relative.as_posix()
        code_hash = expected_code.get(key) or APPROVED_CODE_SHA256.get(key)
        if code_hash != before[code_relative.as_posix()]["sha256"]:
            raise ForensicsError(f"code_hash_mismatch:{key}")
    if not allow_unpinned:
        imported = {
            Path("source/jusik/research_signal_validation.py"): Path(
                inspect.getfile(_latency_values)
            ),
            Path("source/jusik/research_quote_models.py"): Path(
                inspect.getfile(ResearchQuote)
            ),
            Path("source/jusik/research_universe_data.py"): Path(
                inspect.getfile(research_universe_data)
            ),
            Path("source/jusik/research_market_calendar.py"): Path(
                inspect.getfile(MarketCalendar)
            ),
            Path("source/jusik/data/market_sessions_2023_2026.json"): Path(
                inspect.getfile(MarketCalendar)
            ).parent
            / "data/market_sessions_2023_2026.json",
        }
        for imported_relative, imported_path in imported.items():
            if (
                _sha256(imported_path)
                != APPROVED_CODE_SHA256[imported_relative.as_posix()]
            ):
                raise ForensicsError(f"imported_code_hash_mismatch:{imported_relative}")
    return inputs, before, provenance, reference


def _load_calendar(path: Path) -> MarketCalendar:
    try:
        calendar = MarketCalendar.from_bytes(path.read_bytes())
    except (OSError, ValueError) as exc:
        raise ForensicsError("calendar_invalid") from exc
    if not calendar.available:
        raise ForensicsError("calendar_unavailable")
    return calendar


def _raw_value(payload: str, key: str) -> str:
    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ForensicsError("quote_json_invalid") from exc
    value = decoded.get(key) if isinstance(decoded, dict) else None
    if not isinstance(value, str):
        raise ForensicsError(f"quote_{key}_missing")
    return value


def _parse_observations(
    connection: sqlite3.Connection,
    session_id: str,
    local_date: date,
    now: datetime,
    calendar: MarketCalendar,
) -> tuple[list[_Observation], list[tuple[str, ResearchQuote]]]:
    range_start = datetime.combine(
        local_date - timedelta(days=1), datetime.min.time(), UTC
    )
    range_end = datetime.combine(
        local_date + timedelta(days=2), datetime.min.time(), UTC
    )
    rows = connection.execute(
        """SELECT id, symbol, reason, market_at, received_at, quote_json
        FROM forward_observations
        WHERE session_id=? AND market_at>=? AND market_at<?
        ORDER BY market_at, received_at, id""",
        (session_id, range_start.isoformat(), range_end.isoformat()),
    ).fetchall()
    instruments = _instrument_map()
    selected: list[_Observation] = []
    coverage_rows: list[tuple[str, ResearchQuote]] = []
    for row in rows:
        try:
            quote = ResearchQuote.model_validate_json(row["quote_json"])
        except ValueError as exc:
            raise ForensicsError("quote_model_invalid") from exc
        instrument = instruments.get(quote.symbol)
        if instrument is None:
            continue
        market_at = quote.market_at.astimezone(UTC)
        if market_at.astimezone(ZoneInfo(instrument.timezone)).date() != local_date:
            continue
        coverage_rows.append((str(row["reason"]), quote))
        lookup = calendar.lookup(instrument.exchange, local_date)
        if (
            lookup.session is None
            or not lookup.session.open_at <= market_at < lookup.session.close_at
        ):
            continue
        received_at = quote.received_at.astimezone(UTC)
        delta = received_at - market_at
        kind = (
            "future"
            if delta < -timedelta(seconds=2)
            else "stale"
            if delta > timedelta(seconds=15)
            else None
        )
        selected.append(
            _Observation(
                observation_id=str(row["id"]),
                symbol=quote.symbol,
                exchange=instrument.exchange,
                source=quote.source,
                reason=str(row["reason"]),
                quote_market_at_raw=_raw_value(row["quote_json"], "market_at"),
                quote_received_at_raw=_raw_value(row["quote_json"], "received_at"),
                db_market_at=str(row["market_at"])
                if row["market_at"] is not None
                else None,
                db_received_at=str(row["received_at"])
                if row["received_at"] is not None
                else None,
                market_at=market_at,
                received_at=received_at,
                milliseconds=_exact_milliseconds(delta),
                rounded_milliseconds=round(delta.total_seconds() * 1000),
                kind=kind,
            )
        )
    return selected, coverage_rows


def _coverage(
    rows: list[tuple[str, ResearchQuote]],
    activated_at: datetime,
    now: datetime,
    calendar: MarketCalendar,
    local_date: date,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for instrument in REGISTRY:
        item = _symbol_coverage(
            instrument.symbol,
            instrument.exchange,
            instrument.timezone,
            local_date,
            now,
            activated_at,
            [
                (reason, quote)
                for reason, quote in rows
                if quote.symbol == instrument.symbol
            ],
            calendar,
        )
        result.append(item.model_dump(mode="json"))
    return result


def _group_stats(rows: list[_Observation], key: str) -> dict[str, Any]:
    groups: dict[str, list[_Observation]] = defaultdict(list)
    for row in rows:
        groups[str(getattr(row, key))].append(row)
    return {group: _stats_from_observations(groups[group]) for group in sorted(groups)}


def _comparison(
    reference: dict[str, Any], rows: list[_Observation], coverage: list[dict[str, Any]]
) -> dict[str, Any]:
    baseline_latency = reference.get("latency", {})
    current_latency = _stats_from_observations(rows)
    baseline_by_symbol = {
        str(item["symbol"]): item for item in reference.get("symbol_latency", [])
    }
    current_by_symbol = _group_stats(rows, "symbol")
    baseline_coverage = {
        str(item["symbol"]): item for item in reference.get("coverage", [])
    }
    coverage_match: dict[str, Any] = {}
    for item in coverage:
        symbol = str(item["symbol"])
        expected = baseline_coverage.get(symbol, {})
        fields = (
            "expected_completed_minutes",
            "observed_completed_minutes",
            "missing_minutes",
            "persisted_rows",
            "outside_regular_rows",
            "incomplete_minute_rows",
        )
        coverage_match[symbol] = {
            field: {"forensic": item.get(field), "reference": expected.get(field)}
            for field in fields
        }
    return {
        "reference_local_date": reference.get("local_date"),
        "reference_latency": baseline_latency,
        "forensic_latency": current_latency,
        "reference_symbol_latency": baseline_by_symbol,
        "forensic_symbol_latency": current_by_symbol,
        "coverage_counts": coverage_match,
        "reference_anomaly_total": reference.get("latency_anomalies", {}).get(
            "total_count"
        ),
        "forensic_anomaly_total": sum(row.kind is not None for row in rows),
    }


def analyze_archive(
    archive_root: Path, output_dir: Path, *, allow_unpinned: bool = False
) -> dict[str, Any]:
    """Analyze ``archive_root`` and write deterministic CSV/JSON outputs."""
    archive = archive_root.resolve()
    if output_dir.is_symlink():
        raise ForensicsError("output_symlink_rejected")
    output = output_dir.resolve()
    inputs, before, provenance, reference = _validate_archive(
        archive, output, allow_unpinned=allow_unpinned
    )
    db_path = archive / DB_RELATIVE
    calendar = _load_calendar(archive / CODE_RELATIVES[2])
    try:
        connection = sqlite3.connect(
            f"file:{db_path}?mode=ro&immutable=1", uri=True, timeout=0.1
        )
    except sqlite3.Error as exc:
        raise ForensicsError("snapshot_open_failed") from exc
    connection.row_factory = sqlite3.Row
    try:
        session = connection.execute(
            "SELECT id, activated_at FROM forward_sessions "
            "ORDER BY activated_at DESC, id DESC LIMIT 1"
        ).fetchone()
        if session is None:
            raise ForensicsError("forward_session_missing")
        session_id = str(session["id"])
        activated_at = datetime.fromisoformat(str(session["activated_at"])).astimezone(
            UTC
        )
        rows, coverage_rows = _parse_observations(
            connection, session_id, DATE, NOW, calendar
        )
    finally:
        connection.close()
    coverage = _coverage(coverage_rows, activated_at, NOW, calendar, DATE)
    rows.sort(
        key=lambda row: (row.market_at, row.received_at, row.symbol, row.observation_id)
    )
    output.mkdir(parents=True, exist_ok=True)
    csv_path = output / "anomalies.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            if row.kind is None:
                continue
            writer.writerow(
                {
                    "observation_id": row.observation_id,
                    "symbol": row.symbol,
                    "exchange": row.exchange,
                    "source": row.source,
                    "reason": row.reason,
                    "kind": row.kind,
                    "milliseconds": str(row.milliseconds),
                    "market_at": _iso(row.market_at),
                    "received_at": _iso(row.received_at),
                    "quote_market_at_raw": row.quote_market_at_raw,
                    "quote_received_at_raw": row.quote_received_at_raw,
                    "db_market_at": row.db_market_at or "",
                    "db_received_at": row.db_received_at or "",
                    "utc_hour": row.utc_hour,
                }
            )
    summary = {
        "date": DATE.isoformat(),
        "now": _iso(NOW),
        "session_id": session_id,
        "activated_at": _iso(activated_at),
        "selection": {
            "sql_utc_range": [
                datetime.combine(
                    DATE - timedelta(days=1), datetime.min.time(), UTC
                ).isoformat(),
                datetime.combine(
                    DATE + timedelta(days=2), datetime.min.time(), UTC
                ).isoformat(),
            ],
            "market_date_timezone": "instrument registry timezone",
            "regular_session_bounds": "[calendar open, calendar close)",
            "latency_rows_are_deduplicated": False,
        },
        "totals": {
            "selected_observations": len(rows),
            "latency_samples": len(rows),
            "anomalies": sum(row.kind is not None for row in rows),
            "future": sum(row.kind == "future" for row in rows),
            "stale": sum(row.kind == "stale" for row in rows),
        },
        "latency": _stats_from_observations(rows),
        "by_symbol": _group_stats(rows, "symbol"),
        "by_source": _group_stats(rows, "source"),
        "by_observation_reason": _group_stats(rows, "reason"),
        "by_anomaly_kind": {
            kind: _stats_from_observations([row for row in rows if row.kind == kind])
            for kind in ("future", "stale")
        },
        "by_utc_hour": _group_stats(rows, "utc_hour"),
        "coverage": coverage,
        "baseline_comparison": _comparison(reference, rows, coverage),
        "limitations": [
            (
                "Latency is the difference between provider market_at and host "
                "received_at; host clock uncertainty is not resolved."
            ),
            (
                "Anomalies describe timestamp relationships only; this report "
                "makes no causal claim and applies no correction."
            ),
            (
                "Coverage counts use unique symbol/minute rows from the validator; "
                "latency statistics retain every selected observation row."
            ),
        ],
    }
    (output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    after = _fingerprint(inputs)
    if before != after:
        raise ForensicsError("input_changed_during_analysis")
    input_hashes = {
        "before": before,
        "after": after,
        "files": {
            relative: {"sha256": data["sha256"], "size": data["size"]}
            for relative, data in sorted(after.items())
        },
        "archive_snapshot_sha256": after[DB_RELATIVE.as_posix()]["sha256"],
        "archive_wal_sha256": after[WAL_RELATIVE.as_posix()]["sha256"],
        "provenance_snapshot_sha256": provenance.get("snapshot_sha256"),
        "reference_sha256": after[REFERENCE_RELATIVE.as_posix()]["sha256"],
    }
    (output / "input-hashes.json").write_text(
        json.dumps(input_hashes, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        summary = analyze_archive(args.archive_root, args.output_dir)
    except (ForensicsError, OSError, sqlite3.Error) as exc:
        print(f"error: {exc}")
        return 2
    print(json.dumps(summary["totals"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
