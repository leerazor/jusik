"""Alpha Vantage corporate-action evidence collector.

This module stores provider responses as raw evidence and does not apply any
action to prices, holdings, or trading ledgers.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import os
import re
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlencode

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator

ALPHA_VANTAGE_URL = "https://www.alphavantage.co/query"
ALPHA_MIN_REQUEST_INTERVAL = timedelta(seconds=12)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(UTC)


class AlphaAction(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: str = Field(min_length=1, max_length=20)
    kind: str = Field(pattern=r"^(dividend|split)$")
    event_date: date
    payment_date: date | None = None
    amount: str | None = None
    currency: str | None = Field(default=None, max_length=3)
    numerator: int | None = Field(default=None, gt=0)
    denominator: int | None = Field(default=None, gt=0)
    source_url: str = Field(min_length=1, max_length=500)
    observed_at: datetime
    raw_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("observed_at")
    @classmethod
    def observed_at_utc(cls, value: datetime) -> datetime:
        return _utc(value)


def _parse_date(value: object, field: str) -> date:
    if not isinstance(value, str):
        raise ValueError(f"{field}_missing")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field}_invalid") from exc


def _parse_amount(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"\d+(?:\.\d+)?", value):
        raise ValueError("dividend_amount_invalid")
    return value


def _parse_factor(value: object) -> tuple[int, int]:
    if not isinstance(value, str):
        raise ValueError("split_factor_invalid")
    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(?::\s*(\d+(?:\.\d+)?))?", value)
    if match is None:
        raise ValueError("split_factor_invalid")
    try:
        numerator = Decimal(match.group(1))
        denominator = Decimal(match.group(2) or "1")
    except InvalidOperation as exc:
        raise ValueError("split_factor_invalid") from exc
    if numerator <= 0 or denominator <= 0:
        raise ValueError("split_factor_invalid")
    ratio = numerator / denominator
    scaled = ratio.as_integer_ratio()
    return scaled[0], scaled[1]


def _rows(body: bytes) -> list[Mapping[str, object]]:
    try:
        import json

        payload = json.loads(body)
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError("alpha_actions_invalid_json") from exc
    if not isinstance(payload, Mapping):
        raise ValueError("alpha_actions_invalid_root")
    for key in ("Note", "Information", "Error Message"):
        if isinstance(payload.get(key), str):
            raise ValueError("alpha_actions_provider_error")
    data = payload.get("data")
    if not isinstance(data, list):
        raise ValueError("alpha_actions_data_missing")
    if not all(isinstance(item, Mapping) for item in data):
        raise ValueError("alpha_actions_row_invalid")
    return [item for item in data if isinstance(item, Mapping)]


def parse_alpha_actions(
    body: bytes,
    *,
    symbol: str,
    kind: str,
    start: date,
    end: date,
    source_url: str,
    observed_at: datetime,
) -> tuple[AlphaAction, ...]:
    if kind not in {"dividend", "split"}:
        raise ValueError("alpha_action_kind_invalid")
    digest = hashlib.sha256(body).hexdigest()
    public_source_url = source_url.split("&apikey=", 1)[0]
    observed = _utc(observed_at)
    result: list[AlphaAction] = []
    for row in _rows(body):
        if kind == "dividend":
            event_date = _parse_date(row.get("ex_dividend_date"), "ex_dividend_date")
            if not start <= event_date <= end:
                continue
            payment_value = row.get("payment_date")
            payment_date = (
                None
                if payment_value in (None, "None", "")
                else _parse_date(payment_value, "payment_date")
            )
            result.append(
                AlphaAction(
                    symbol=symbol,
                    kind=kind,
                    event_date=event_date,
                    payment_date=payment_date,
                    amount=_parse_amount(row.get("amount")),
                    currency="USD",
                    source_url=public_source_url,
                    observed_at=observed,
                    raw_sha256=digest,
                )
            )
        else:
            event_date = _parse_date(row.get("effective_date"), "effective_date")
            if not start <= event_date <= end:
                continue
            numerator, denominator = _parse_factor(row.get("split_factor"))
            result.append(
                AlphaAction(
                    symbol=symbol,
                    kind=kind,
                    event_date=event_date,
                    numerator=numerator,
                    denominator=denominator,
                    source_url=public_source_url,
                    observed_at=observed,
                    raw_sha256=digest,
                )
            )
    return tuple(sorted(result, key=lambda item: (item.event_date, item.kind)))


def alpha_action_url(*, symbol: str, kind: str, api_key: str) -> str:
    function = "DIVIDENDS" if kind == "dividend" else "SPLITS"
    params = {"function": function, "symbol": symbol, "apikey": api_key}
    return f"{ALPHA_VANTAGE_URL}?{urlencode(params)}"


async def collect_alpha_actions(
    *,
    symbols: Iterable[str],
    start: date,
    end: date,
    output_dir: Path,
    api_key: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> tuple[AlphaAction, ...]:
    key = api_key or os.environ.get("ALPHA_VANTAGE_API_KEY")
    if not key:
        raise ValueError("ALPHA_VANTAGE_API_KEY is required")
    if end < start:
        raise ValueError("end_before_start")
    owns_client = client is None
    http_client = client or httpx.AsyncClient(timeout=30)
    output_dir.mkdir(parents=True, exist_ok=True)
    result: list[AlphaAction] = []
    previous_request_at: datetime | None = None
    try:
        for symbol in symbols:
            for kind in ("dividend", "split"):
                if previous_request_at is not None:
                    wait = ALPHA_MIN_REQUEST_INTERVAL - (
                        datetime.now(UTC) - previous_request_at
                    )
                    if wait.total_seconds() > 0:
                        await asyncio.sleep(wait.total_seconds())
                url = alpha_action_url(symbol=symbol, kind=kind, api_key=key)
                response = await http_client.get(url)
                previous_request_at = datetime.now(UTC)
                response.raise_for_status()
                observed = datetime.now(UTC)
                digest = hashlib.sha256(response.content).hexdigest()
                raw_path = output_dir / (
                    f"alpha-{symbol}-{kind}-{digest}.json"
                )
                if not raw_path.exists():
                    raw_path.write_bytes(response.content)
                result.extend(
                    parse_alpha_actions(
                        response.content,
                        symbol=symbol,
                        kind=kind,
                        start=start,
                        end=end,
                        source_url=url.split("&apikey=", 1)[0],
                        observed_at=observed,
                    )
                )
    finally:
        if owns_client:
            await http_client.aclose()
    return tuple(result)


def _main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Collect Alpha Vantage action evidence"
    )
    parser.add_argument("--symbol", action="append", required=True)
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    actions = asyncio.run(
        collect_alpha_actions(
            symbols=args.symbol,
            start=args.start,
            end=args.end,
            output_dir=args.output_dir,
        )
    )
    print(f"collected_actions={len(actions)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
