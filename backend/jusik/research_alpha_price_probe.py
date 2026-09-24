"""Bounded Alpha Vantage daily-price entitlement probe.

The probe records transport and response-shape evidence only.  It never writes
market history and never treats a successful request as proof of complete or
point-in-time coverage.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

import httpx
from dotenv import dotenv_values

ALPHA_VANTAGE_URL = "https://www.alphavantage.co/query"
SYMBOL_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,24}$")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ProbeStatus = Literal["ready", "missing_key", "unavailable", "error"]


@dataclass(frozen=True, slots=True)
class AlphaVantagePriceProbeResult:
    symbol: str
    status: ProbeStatus
    rows: int = 0
    first_date: str | None = None
    last_date: str | None = None
    error: str | None = None


def probe_daily(
    symbol: str,
    api_key: str | None,
    *,
    client: httpx.Client | None = None,
) -> AlphaVantagePriceProbeResult:
    """Fetch Alpha Vantage's bounded daily response without exposing secrets."""

    if not SYMBOL_PATTERN.fullmatch(symbol):
        raise ValueError("symbol is invalid")
    if not api_key:
        return AlphaVantagePriceProbeResult(symbol, "missing_key", error="key_missing")

    params = {
        "function": "TIME_SERIES_DAILY",
        "symbol": symbol,
        "outputsize": "full",
        "apikey": api_key,
    }
    own_client = client is None
    http_client = client or httpx.Client(timeout=20)
    try:
        response = http_client.get(ALPHA_VANTAGE_URL, params=params)
        if response.status_code != 200:
            return AlphaVantagePriceProbeResult(
                symbol, "error", error="alpha_vantage_http_error"
            )
        try:
            payload = response.json()
        except ValueError:
            return AlphaVantagePriceProbeResult(
                symbol, "error", error="alpha_vantage_invalid_json"
            )
        if not isinstance(payload, dict):
            return AlphaVantagePriceProbeResult(
                symbol, "error", error="alpha_vantage_invalid_payload"
            )
        series = payload.get("Time Series (Daily)")
        if not isinstance(series, dict):
            if "Information" in payload:
                return AlphaVantagePriceProbeResult(
                    symbol, "unavailable", error="alpha_vantage_information"
                )
            if "Note" in payload:
                return AlphaVantagePriceProbeResult(
                    symbol, "unavailable", error="alpha_vantage_rate_limited"
                )
            if "Error Message" in payload:
                return AlphaVantagePriceProbeResult(
                    symbol, "error", error="alpha_vantage_provider_error"
                )
            return AlphaVantagePriceProbeResult(
                symbol, "error", error="alpha_vantage_daily_series_missing"
            )
        dates = sorted(
            value
            for value in series
            if isinstance(value, str) and DATE_PATTERN.fullmatch(value)
        )
        if not dates:
            return AlphaVantagePriceProbeResult(
                symbol, "error", error="alpha_vantage_daily_series_empty"
            )
        return AlphaVantagePriceProbeResult(
            symbol,
            "ready",
            rows=len(dates),
            first_date=dates[0],
            last_date=dates[-1],
        )
    except httpx.HTTPError:
        return AlphaVantagePriceProbeResult(
            symbol, "error", error="alpha_vantage_transport_error"
        )
    finally:
        if own_client:
            http_client.close()


def _api_key_from_env(path: Path) -> str | None:
    values = dotenv_values(path)
    for name in ("ALPHA_VANTAGE_API_KEY", "ALPHA_VANTAGE_KEY"):
        value = values.get(name)
        if isinstance(value, str) and value:
            return value
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe Alpha Vantage daily prices")
    parser.add_argument("symbol")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    args = parser.parse_args(argv)
    result = probe_daily(args.symbol, _api_key_from_env(args.env_file))
    print(json.dumps(asdict(result), ensure_ascii=False, sort_keys=True))
    return 0 if result.status == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
