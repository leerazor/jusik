"""Bounded Nasdaq Data Link SDK probe.

This module deliberately probes entitlement and transport only.  A successful
response is not sufficient evidence for point-in-time membership, delisted
identity, or complete historical coverage, so the result is never promoted to
the canonical market-history source by this module.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from dotenv import dotenv_values

DATASET_PATTERN = re.compile(r"^[A-Za-z0-9_./-]{1,120}$")
SDK_BASE_URL = "https://data.nasdaq.com/api/v3"
ProbeStatus = Literal["ready", "missing_dependency", "missing_key", "error"]


@dataclass(frozen=True, slots=True)
class NasdaqDataLinkProbeResult:
    dataset: str
    status: ProbeStatus
    rows: int = 0
    columns: tuple[str, ...] = ()
    error: str | None = None


def probe_dataset(
    dataset: str,
    api_key: str | None,
    *,
    rows: int = 1,
) -> NasdaqDataLinkProbeResult:
    """Fetch a small dataset sample through the official Python SDK."""

    if not DATASET_PATTERN.fullmatch(dataset):
        raise ValueError("dataset identifier is invalid")
    if rows < 1 or rows > 100:
        raise ValueError("rows must be between 1 and 100")
    if not api_key:
        return NasdaqDataLinkProbeResult(dataset, "missing_key", error="key_missing")

    try:
        sdk = importlib.import_module("nasdaqdatalink")
    except ImportError:
        return NasdaqDataLinkProbeResult(
            dataset, "missing_dependency", error="nasdaq_data_link_sdk_missing"
        )

    config = getattr(sdk, "ApiConfig", None)
    getter = getattr(sdk, "get", None)
    if config is None or not callable(getter):
        return NasdaqDataLinkProbeResult(
            dataset, "error", error="nasdaq_data_link_sdk_invalid"
        )
    config.api_base = SDK_BASE_URL
    config.api_key = api_key
    try:
        frame = getter(dataset, rows=rows)
        columns = tuple(str(value) for value in getattr(frame, "columns", ()))
        return NasdaqDataLinkProbeResult(
            dataset,
            "ready",
            rows=len(frame),
            columns=columns,
        )
    except Exception as exc:  # SDK has provider-specific exception classes.
        # Do not expose provider response bodies or credentials in diagnostics.
        error = "nasdaq_data_link_request_failed"
        if type(exc).__name__ == "DataLinkError":
            error = "nasdaq_data_link_error"
        return NasdaqDataLinkProbeResult(dataset, "error", error=error)


async def probe_dataset_async(
    dataset: str,
    api_key: str | None,
    *,
    rows: int = 1,
) -> NasdaqDataLinkProbeResult:
    """Run the synchronous SDK off the event loop."""

    return await asyncio.to_thread(probe_dataset, dataset, api_key, rows=rows)


def _api_key_from_env(path: Path) -> str | None:
    values = dotenv_values(path)
    value = values.get("NASDAQ_DATA_LINK_API_KEY")
    return value if isinstance(value, str) and value else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe Nasdaq Data Link via SDK")
    parser.add_argument("--dataset", default="FRED/GDP")
    parser.add_argument("--rows", type=int, default=1)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    args = parser.parse_args(argv)
    result = probe_dataset(
        args.dataset,
        _api_key_from_env(args.env_file),
        rows=args.rows,
    )
    print(json.dumps(asdict(result), ensure_ascii=False, sort_keys=True))
    return 0 if result.status == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
