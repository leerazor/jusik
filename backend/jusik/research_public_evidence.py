"""Free public evidence collectors for US corporate actions and trading halts.

The collectors preserve provider publication/receipt time and raw response
hashes.  They are evidence inputs only; they never mutate trading state.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import re
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator

NASDAQ_RSS_URL = "https://www.nasdaqtrader.com/rss.aspx"
NASDAQ_MIN_REQUEST_INTERVAL = timedelta(seconds=60)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(UTC)


class NasdaqHalt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: str = Field(min_length=1, max_length=20)
    halt_date: date
    title: str = Field(min_length=1, max_length=500)
    description: str = Field(min_length=1, max_length=4000)
    source_url: str = Field(min_length=1, max_length=500)
    observed_at: datetime
    raw_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    market: str | None = Field(default=None, max_length=20)
    reason_code: str | None = Field(default=None, max_length=20)

    @field_validator("observed_at")
    @classmethod
    def observed_at_utc(cls, value: datetime) -> datetime:
        return _utc(value)


_SYMBOL_RE = re.compile(r"\b(?:Security|Issue)\s+([A-Z0-9][A-Z0-9.\-/]{0,19})\b", re.I)
_DATE_RE = re.compile(r"\b(\d{2}/\d{2}/\d{4})\b")
_CODE_RE = re.compile(r"\b(?:halt code|reason code)\s*[:=-]?\s*([A-Z0-9]{1,8})\b", re.I)
_HTML_SYMBOL_RE = re.compile(
    r"Issue\s+Symbol.*?</th>\s*<th[^>]*>.*?</th>.*?</tr>\s*<tr>\s*"
    r"<td[^>]*>\s*([A-Z0-9][A-Z0-9.\-/]{0,19})\s*</td>",
    re.I | re.S,
)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].casefold()


def _item_text(item: ET.Element, name: str) -> str:
    for child in item:
        if _local_name(child.tag) == name:
            return " ".join("".join(child.itertext()).split())
    return ""


def _item_raw(item: ET.Element, name: str) -> str:
    for child in item:
        if _local_name(child.tag) == name:
            if child.text and not list(child):
                return child.text
            return ET.tostring(child, encoding="unicode")
    return ""


def parse_nasdaq_halt_rss(
    body: bytes,
    *,
    halt_date: date,
    source_url: str,
    observed_at: datetime,
) -> tuple[NasdaqHalt, ...]:
    """Parse a Nasdaq halt RSS response without trusting display text as identity."""
    try:
        root = ET.fromstring(body)
    except (ET.ParseError, UnicodeDecodeError) as exc:
        raise ValueError("nasdaq_rss_invalid_xml") from exc
    observed = _utc(observed_at)
    digest = hashlib.sha256(body).hexdigest()
    items: list[NasdaqHalt] = []
    for item in root.iter():
        if _local_name(item.tag) != "item":
            continue
        title = _item_text(item, "title")
        description = _item_text(item, "description")
        raw_description = _item_raw(item, "description")
        text = f"{title} {description}"
        html_match = _HTML_SYMBOL_RE.search(raw_description)
        match = html_match or _SYMBOL_RE.search(text)
        if match is None:
            continue
        parsed_date = _DATE_RE.search(text)
        reason_match = _CODE_RE.search(text)
        event_date = (
            datetime.strptime(parsed_date.group(1), "%m/%d/%Y").date()
            if parsed_date is not None
            else halt_date
        )
        items.append(
            NasdaqHalt(
                symbol=match.group(1).upper(),
                halt_date=event_date,
                title=title or "Nasdaq trading halt",
                description=description or title,
                source_url=source_url,
                observed_at=observed,
                raw_sha256=digest,
                reason_code=(
                    reason_match.group(1).upper()
                    if reason_match is not None
                    else None
                ),
            )
        )
    return tuple(sorted(items, key=lambda value: (value.halt_date, value.symbol)))


def nasdaq_halt_url(*, halt_date: date, resumedate: date | None = None) -> str:
    params = {"feed": "tradehalts", "haltdate": halt_date.strftime("%m%d%Y")}
    if resumedate is not None:
        params["resumedate"] = resumedate.strftime("%m%d%Y")
    return f"{NASDAQ_RSS_URL}?{urlencode(params)}"


async def collect_nasdaq_halts(
    *,
    start: date,
    end: date,
    output_dir: Path,
    client: httpx.AsyncClient | None = None,
) -> tuple[NasdaqHalt, ...]:
    """Collect one raw RSS response per day and write immutable evidence files."""
    if end < start:
        raise ValueError("end_before_start")
    owns_client = client is None
    http_client = client or httpx.AsyncClient(timeout=30)
    output_dir.mkdir(parents=True, exist_ok=True)
    results: list[NasdaqHalt] = []
    previous_request_at: datetime | None = None
    try:
        current = start
        while current <= end:
            if previous_request_at is not None:
                wait = NASDAQ_MIN_REQUEST_INTERVAL - (
                    datetime.now(UTC) - previous_request_at
                )
                if wait.total_seconds() > 0:
                    await asyncio.sleep(wait.total_seconds())
            url = nasdaq_halt_url(halt_date=current)
            response = await http_client.get(
                url, headers={"Accept": "application/rss+xml, application/xml"}
            )
            previous_request_at = datetime.now(UTC)
            response.raise_for_status()
            observed = datetime.now(UTC)
            digest = hashlib.sha256(response.content).hexdigest()
            raw_path = output_dir / (
                f"nasdaq-tradehalts-{current.isoformat()}-{digest}.xml"
            )
            if not raw_path.exists():
                raw_path.write_bytes(response.content)
            results.extend(
                parse_nasdaq_halt_rss(
                    response.content,
                    halt_date=current,
                    source_url=url,
                    observed_at=observed,
                )
            )
            current += timedelta(days=1)
    finally:
        if owns_client:
            await http_client.aclose()
    return tuple(results)


def _main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect Nasdaq public halt evidence")
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    items = asyncio.run(
        collect_nasdaq_halts(
            start=args.start, end=args.end, output_dir=args.output_dir
        )
    )
    print(f"collected_halts={len(items)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
