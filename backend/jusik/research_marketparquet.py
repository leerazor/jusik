"""Bounded MarketParquet manifest and symbol probe.

This is evidence collection only.  It never writes canonical history or treats
the provider's split-adjusted, dividend-excluded bars as complete PIT evidence.
"""

from __future__ import annotations

import argparse
import io
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Literal

import httpx
from dotenv import dotenv_values

BASE_URL = "https://marketparquet.com/api/v1"
SYMBOL_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,24}$")
ProbeStatus = Literal[
    "ready", "missing_key", "missing_dependency", "unavailable", "error"
]


@dataclass(frozen=True, slots=True)
class SymbolCoverage:
    rows: int = 0
    first_date: str | None = None
    last_date: str | None = None


@dataclass(frozen=True, slots=True)
class MarketParquetProbeResult:
    status: ProbeStatus
    start: str
    end: str
    symbols: tuple[str, ...]
    files: int = 0
    rows: dict[str, int] = field(default_factory=dict)
    first_date: dict[str, str | None] = field(default_factory=dict)
    last_date: dict[str, str | None] = field(default_factory=dict)
    manifest_bytes: int | None = None
    error: str | None = None


def probe_symbols(
    start: str,
    end: str,
    symbols: tuple[str, ...],
    api_key: str | None,
    *,
    max_files: int = 30,
    client: httpx.Client | None = None,
) -> MarketParquetProbeResult:
    """Inspect at most ``max_files`` daily files from an authenticated manifest."""

    _validate_date(start, "start")
    _validate_date(end, "end")
    if start > end:
        raise ValueError("start must not be after end")
    if not symbols or any(not SYMBOL_PATTERN.fullmatch(item) for item in symbols):
        raise ValueError("symbols are invalid")
    if max_files < 1 or max_files > 400:
        raise ValueError("max_files must be between 1 and 400")
    normalized = tuple(dict.fromkeys(symbols))
    if not api_key:
        return MarketParquetProbeResult(
            "missing_key", start, end, normalized, error="key_missing"
        )
    try:
        import pyarrow.parquet as parquet  # type: ignore[import-untyped]
    except ImportError:
        return MarketParquetProbeResult(
            "missing_dependency", start, end, normalized, error="pyarrow_missing"
        )
    own_client = client is None
    http_client = client or httpx.Client(timeout=30)
    try:
        response = http_client.get(
            f"{BASE_URL}/manifest/stock_daily",
            params={"start": start, "end": end},
            headers={"Authorization": f"Bearer {api_key}"},
        )
        if response.status_code in {401, 403}:
            return MarketParquetProbeResult(
                "unavailable", start, end, normalized, error="manifest_not_entitled"
            )
        if response.status_code != 200:
            return MarketParquetProbeResult(
                "error", start, end, normalized, error="manifest_http_error"
            )
        try:
            payload = response.json()
        except ValueError:
            return MarketParquetProbeResult(
                "error", start, end, normalized, error="manifest_invalid_json"
            )
        files = payload.get("files") if isinstance(payload, dict) else None
        if not isinstance(files, list):
            return MarketParquetProbeResult(
                "error", start, end, normalized, error="manifest_files_missing"
            )
        rows = {symbol: 0 for symbol in normalized}
        first: dict[str, str | None] = {symbol: None for symbol in normalized}
        last: dict[str, str | None] = {symbol: None for symbol in normalized}
        inspected = 0
        for item in files[:max_files]:
            if not isinstance(item, dict) or not isinstance(
                item.get("download_url"), str
            ):
                continue
            daily = http_client.get(item["download_url"], timeout=60)
            if daily.status_code != 200:
                continue
            table = parquet.read_table(io.BytesIO(daily.content))
            names = set(table.column_names)
            date_column = (
                "date"
                if "date" in names
                else "timestamp"
                if "timestamp" in names
                else None
            )
            if "symbol" not in names or date_column is None:
                continue
            for row in table.select([date_column, "symbol"]).to_pylist():
                symbol = row.get("symbol")
                if symbol not in rows:
                    continue
                value = str(row[date_column])[:10]
                rows[symbol] += 1
                current_first = first[symbol]
                current_last = last[symbol]
                first[symbol] = (
                    value if current_first is None else min(current_first, value)
                )
                last[symbol] = (
                    value if current_last is None else max(current_last, value)
                )
            inspected += 1
        return MarketParquetProbeResult(
            "ready" if any(rows.values()) else "unavailable",
            start,
            end,
            normalized,
            files=inspected,
            rows=rows,
            first_date=first,
            last_date=last,
            manifest_bytes=len(response.content),
            error=None if any(rows.values()) else "symbols_not_observed_in_sample",
        )
    except httpx.HTTPError:
        return MarketParquetProbeResult(
            "error", start, end, normalized, error="transport_error"
        )
    finally:
        if own_client:
            http_client.close()


def _validate_date(value: str, label: str) -> None:
    try:
        if date.fromisoformat(value).isoformat() != value:
            raise ValueError
    except ValueError as exc:
        raise ValueError(f"{label} must be an ISO date") from exc


def _api_key_from_env(path: Path) -> str | None:
    value = dotenv_values(path).get("MARKETPARQUET_API_KEY")
    return value if isinstance(value, str) and value else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe MarketParquet symbol coverage")
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--symbol", action="append", required=True)
    parser.add_argument("--max-files", type=int, default=30)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    args = parser.parse_args(argv)
    result = probe_symbols(
        args.start,
        args.end,
        tuple(args.symbol),
        _api_key_from_env(args.env_file),
        max_files=args.max_files,
    )
    print(json.dumps(asdict(result), ensure_ascii=False, sort_keys=True))
    return 0 if result.status == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
