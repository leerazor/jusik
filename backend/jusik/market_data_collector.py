"""Bounded network collection for the approximate market-data workflow.

The collector writes only validated prepared responses.  HTTP is injected so
tests can use deterministic responses, and every raw response is cached by a
content-addressed, secret-free key before it is normalized.
"""

from __future__ import annotations

import asyncio
import csv
import hashlib
import io
import json
import os
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Literal, Protocol, cast
from urllib.parse import quote
from zoneinfo import ZoneInfo

import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from jusik.market_history_approximate import (
    ApproximateBarRow,
    ApproximateDataset,
    ApproximateFXRow,
    ApproximateProviderError,
    ApproximateUniverseRow,
    deterministic_pool,
)
from jusik.market_history_models import Market
from jusik.research_market_calendar import MarketCalendar, default_market_calendar

KRX_URL = "https://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd"
ALPHA_VANTAGE_URL = "https://www.alphavantage.co/query"
YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart"
FRED_URL = "https://api.stlouisfed.org/fred/series/observations"
MAX_RETRIES = 3
MAX_RETRY_DELAY_SECONDS = 30
DEFAULT_REQUEST_BUDGET = 250


class CollectorError(RuntimeError):
    """A collection cannot produce a trustworthy prepared dataset."""


class CollectorPartialError(CollectorError):
    """A bounded collection completed only partially."""


class RequestBudgetExceeded(CollectorError):
    """The configured request budget was exhausted."""


class CollectorSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    krx_auth_key: SecretStr | None = None
    alpha_vantage_api_key: SecretStr | None = None
    fred_api_key: SecretStr | None = None
    request_budget: int = Field(default=DEFAULT_REQUEST_BUDGET, ge=1, le=1000)
    timeout_seconds: int = Field(default=30, ge=1, le=60)
    max_retries: int = Field(default=MAX_RETRIES, ge=0, le=MAX_RETRIES)

    @property
    def missing_credentials(self) -> tuple[str, ...]:
        missing: list[str] = []
        if self.krx_auth_key is None:
            missing.append("KRX_AUTH_KEY")
        if self.alpha_vantage_api_key is None:
            missing.append("ALPHA_VANTAGE_API_KEY")
        if self.fred_api_key is None:
            missing.append("FRED_API_KEY")
        return tuple(missing)

    def required_missing_credentials(self, market: Market) -> tuple[str, ...]:
        required = (
            ("KRX_AUTH_KEY",)
            if market == "KR"
            else (
                "ALPHA_VANTAGE_API_KEY",
                "FRED_API_KEY",
            )
        )
        return tuple(name for name in required if name in self.missing_credentials)


def load_collector_settings() -> CollectorSettings:
    def secret(name: str) -> SecretStr | None:
        value = os.environ.get(name)
        return SecretStr(value) if value else None

    budget = os.environ.get("MARKET_DATA_REQUEST_BUDGET")
    return CollectorSettings(
        krx_auth_key=secret("KRX_AUTH_KEY"),
        alpha_vantage_api_key=secret("ALPHA_VANTAGE_API_KEY"),
        fred_api_key=secret("FRED_API_KEY"),
        request_budget=int(budget) if budget else DEFAULT_REQUEST_BUDGET,
    )


class CacheEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str = Field(pattern=r"^[0-9a-f]{64}$")
    source: str = Field(min_length=1, max_length=40)
    endpoint: str = Field(min_length=1, max_length=240)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    captured_at: datetime
    status_code: int = Field(ge=200, lt=600)
    byte_count: int = Field(ge=0)


class CacheManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal["collector-cache-v1"] = "collector-cache-v1"
    entries: tuple[CacheEntry, ...] = ()
    checkpoints: tuple[str, ...] = ()


class AtomicResponseCache:
    """Content-addressed raw cache with atomic files and a resumable manifest."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.raw_root = root / "raw"
        self.manifest_path = root / "manifest.json"

    def _read_manifest(self) -> CacheManifest:
        if not self.manifest_path.is_file():
            return CacheManifest()
        try:
            return CacheManifest.model_validate(
                json.loads(self.manifest_path.read_bytes())
            )
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise CollectorError("collector cache manifest is invalid") from exc

    def _atomic_write(self, path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=path.parent, prefix=".tmp-", delete=False
            ) as handle:
                temporary = handle.name
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if temporary is not None and Path(temporary).exists():
                Path(temporary).unlink()

    def put(
        self,
        *,
        source: str,
        endpoint: str,
        request_key: str,
        body: bytes,
        status_code: int,
        captured_at: datetime,
        checkpoint: str | None = None,
    ) -> CacheEntry:
        digest = hashlib.sha256(body).hexdigest()
        key = hashlib.sha256(request_key.encode()).hexdigest()
        entry = CacheEntry(
            key=key,
            source=source,
            endpoint=endpoint,
            content_sha256=digest,
            captured_at=captured_at,
            status_code=status_code,
            byte_count=len(body),
        )
        self._atomic_write(self.raw_root / f"{key}.bin", body)
        manifest = self._read_manifest()
        entries = tuple(item for item in manifest.entries if item.key != key) + (entry,)
        checkpoints = (
            tuple(sorted(set(manifest.checkpoints) | {checkpoint}))
            if checkpoint is not None
            else manifest.checkpoints
        )
        updated = CacheManifest(entries=entries, checkpoints=checkpoints)
        self._atomic_write(
            self.manifest_path,
            updated.model_dump_json(indent=2).encode(),
        )
        return entry

    def get(self, request_key: str) -> tuple[CacheEntry, bytes] | None:
        key = hashlib.sha256(request_key.encode()).hexdigest()
        manifest = self._read_manifest()
        entry = next((item for item in manifest.entries if item.key == key), None)
        if entry is None:
            return None
        try:
            body = (self.raw_root / f"{key}.bin").read_bytes()
        except OSError as exc:
            raise CollectorError("collector cache raw response is missing") from exc
        if hashlib.sha256(body).hexdigest() != entry.content_sha256:
            raise CollectorError("collector cache raw response hash mismatch")
        return entry, body

    def checkpointed(self, checkpoint: str) -> bool:
        return checkpoint in self._read_manifest().checkpoints

    def status(self) -> dict[str, object]:
        manifest = self._read_manifest()
        return {
            "cache_dir": str(self.root),
            "entries": len(manifest.entries),
            "checkpoints": list(manifest.checkpoints),
        }


class HttpClient(Protocol):
    async def request(
        self, method: str, url: str, **kwargs: object
    ) -> httpx.Response: ...


@dataclass
class HttpFetcher:
    client: HttpClient
    cache: AtomicResponseCache
    settings: CollectorSettings
    resume: bool = True
    requests_used: int = 0

    async def get(
        self,
        *,
        source: str,
        url: str,
        params: Mapping[str, str | int],
        headers: Mapping[str, str] | None = None,
        checkpoint: str | None = None,
    ) -> bytes:
        cache_params = {
            key: value
            for key, value in params.items()
            if key.lower() not in {"auth_key", "api_key", "apikey"}
        }
        request_key = json.dumps(
            {
                "source": source,
                "url": url,
                "params": dict(sorted(cache_params.items())),
            },
            sort_keys=True,
        )
        cached = self.cache.get(request_key) if self.resume else None
        if cached is not None:
            return cached[1]
        if self.requests_used >= self.settings.request_budget:
            raise RequestBudgetExceeded("collector request budget exhausted")
        self.requests_used += 1
        request_headers = {"User-Agent": "jusik-market-data-collector/1.0"}
        if headers:
            request_headers.update(headers)
        for attempt in range(self.settings.max_retries + 1):
            try:
                response = await self.client.request(
                    "GET",
                    url,
                    params=params,
                    headers=request_headers,
                    timeout=self.settings.timeout_seconds,
                )
            except (httpx.HTTPError, TimeoutError) as exc:
                if attempt >= self.settings.max_retries:
                    raise CollectorError(f"{source} request failed") from exc
                await asyncio.sleep(min(2**attempt, MAX_RETRY_DELAY_SECONDS))
                continue
            if response.status_code == 429 or response.status_code >= 500:
                if attempt >= self.settings.max_retries:
                    raise CollectorError(f"{source} request returned HTTP error")
                retry_after = response.headers.get("Retry-After")
                try:
                    delay = max(
                        0.0,
                        min(
                            float(retry_after or 2**attempt),
                            MAX_RETRY_DELAY_SECONDS,
                        ),
                    )
                except ValueError:
                    delay = float(min(2**attempt, MAX_RETRY_DELAY_SECONDS))
                await asyncio.sleep(delay)
                continue
            if response.status_code < 200 or response.status_code >= 300:
                raise CollectorError(f"{source} request returned HTTP error")
            body = response.content
            self.cache.put(
                source=source,
                endpoint=url,
                request_key=request_key,
                body=body,
                status_code=response.status_code,
                captured_at=datetime.now(UTC),
                checkpoint=checkpoint,
            )
            return body
        raise CollectorError(f"{source} request failed")


def _decimal(value: object, field: str, *, nonnegative: bool = False) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise CollectorError(f"{field} is not numeric")
    try:
        result = Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, ValueError) as exc:
        raise CollectorError(f"{field} is not numeric") from exc
    if (
        not result.is_finite()
        or (nonnegative and result < 0)
        or (result <= 0 and not nonnegative)
    ):
        raise CollectorError(f"{field} is not valid")
    return result


def _date(value: object, field: str) -> date:
    try:
        text = str(value).replace("/", "-").replace(".", "-")
        if len(text) == 8 and text.isdigit():
            text = f"{text[:4]}-{text[4:6]}-{text[6:]}"
        return date.fromisoformat(text)
    except ValueError as exc:
        raise CollectorError(f"{field} date is invalid") from exc


def _rows(payload: object) -> list[Mapping[str, object]]:
    raw_rows: object
    if isinstance(payload, list):
        raw_rows = payload
    elif isinstance(payload, dict):
        raw_rows = []
        for key in ("OutBlock_1", "output", "data", "rows", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                raw_rows = value
                break
    else:
        raise CollectorError("provider response must contain rows")
    if not isinstance(raw_rows, list) or not raw_rows:
        raise CollectorError("provider response contains no rows")
    return [
        cast(Mapping[str, object], row) for row in raw_rows if isinstance(row, dict)
    ]


def _field(row: Mapping[str, object], *names: str) -> object | None:
    for name in names:
        if name in row and row[name] not in (None, ""):
            return row[name]
    return None


def parse_krx_daily_response(
    body: bytes,
    *,
    checkpoint: date,
    market_board: Literal["STK", "KSQ"] = "STK",
    available_at: datetime | None = None,
) -> tuple[ApproximateUniverseRow, ...]:
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CollectorError("KRX response is not valid JSON") from exc
    rows = _rows(payload)
    normalized: list[ApproximateUniverseRow] = []
    seen: dict[tuple[date, str], tuple[str, str]] = {}
    for row in rows:
        raw_session = _field(
            row,
            "basDd",
            "BAS_DD",
            "TRD_DD",
            "session",
            "stck_bsop_date",
            "date",
        )
        session = _date(raw_session, "KRX") if raw_session is not None else checkpoint
        symbol = str(
            _field(row, "ISU_SRT_CD", "isu_srt_cd", "symbol", "stck_shrn_iscd") or ""
        ).strip()
        name = str(
            _field(row, "ISU_ABBRV", "isu_abbrv", "name", "bstp_kor_isnm") or ""
        ).strip()
        security_type = str(
            _field(row, "SECUGRP_NM", "ISU_TYP", "instrument_type") or ""
        ).upper()
        if "ETF" in security_type or "ETN" in security_type:
            continue
        if not symbol or not name:
            raise CollectorError("KRX response row lacks identity")
        exchange_raw = str(
            _field(row, "MKT_NM", "mktNm", "market", "exchange") or ""
        ).upper()
        exchange = (
            "KOSDAQ"
            if "KOSDAQ" in exchange_raw or exchange_raw in {"KSQ", "KQ"}
            else ("KOSDAQ" if market_board == "KSQ" else "KOSPI")
        )
        identity = (name, exchange)
        previous = seen.get((session, symbol))
        if previous is not None:
            detail = "conflicting " if previous != identity else "duplicate "
            raise CollectorError(f"KRX response contains {detail}rows")
        seen[(session, symbol)] = identity
        volume = _field(row, "ACC_TRDVOL", "acml_vol", "volume")
        if volume is not None:
            _decimal(volume, "KRX volume", nonnegative=True)
        row_available_at = available_at or datetime.combine(
            session, time(18), tzinfo=UTC
        )
        normalized.append(
            ApproximateUniverseRow(
                session=session,
                symbol=symbol,
                name=name,
                exchange=exchange,
                currency="KRW",
                available_at=row_available_at,
            )
        )
    if not normalized:
        raise CollectorError("KRX response contains no valid stock rows")
    return tuple(normalized)


def parse_alpha_vantage_listing_status(
    body: bytes, *, as_of: date, available_at: datetime | None = None
) -> tuple[ApproximateUniverseRow, ...]:
    try:
        text = body.decode("utf-8-sig")
        rows = list(csv.DictReader(io.StringIO(text)))
    except (UnicodeDecodeError, csv.Error) as exc:
        raise CollectorError("Alpha Vantage response is not valid CSV") from exc
    if not rows:
        raise CollectorError("Alpha Vantage response contains no listings")
    observed_at = available_at or datetime.combine(as_of, time(18), tzinfo=UTC)
    result: list[ApproximateUniverseRow] = []
    seen: set[str] = set()
    for row in rows:
        symbol = (row.get("symbol") or "").strip()
        asset_type = (row.get("assetType") or row.get("asset_type") or "").strip()
        status = (row.get("status") or "").strip().lower()
        if (
            not symbol
            or asset_type.lower() not in {"stock", "common stock", "common_stock"}
            or status not in {"active", "delisted"}
        ):
            continue
        ipo = row.get("ipoDate") or row.get("ipo_date")
        delisted = row.get("delistingDate") or row.get("delisting_date")
        if ipo and ipo not in {"null", "None"} and _date(ipo, "ipo") > as_of:
            continue
        if (
            delisted
            and delisted not in {"null", "None"}
            and _date(delisted, "delisting") < as_of
        ):
            continue
        if symbol in seen:
            raise CollectorError("Alpha Vantage response contains duplicate symbols")
        seen.add(symbol)
        exchange = (row.get("exchange") or "NYS").strip().upper()
        exchange = {"NYSE": "NYS", "NASDAQ": "NAS", "NYSE ARCA": "AMS"}.get(
            exchange, exchange
        )
        if exchange not in {"NAS", "NYS", "AMS"}:
            continue
        result.append(
            ApproximateUniverseRow(
                session=as_of,
                symbol=symbol,
                name=(row.get("name") or symbol).strip(),
                exchange=exchange,
                currency="USD",
                available_at=observed_at,
            )
        )
    if not result:
        raise CollectorError("Alpha Vantage response contains no eligible stocks")
    return tuple(result)


@dataclass(frozen=True)
class YahooChart:
    bars: tuple[ApproximateBarRow, ...]
    events: tuple[str, ...]


def parse_yahoo_chart(
    body: bytes,
    *,
    symbol: str,
    exchange: str,
    currency: Literal["KRW", "USD"],
    start: date,
    end: date,
    available_at: datetime | None = None,
) -> YahooChart:
    try:
        payload = json.loads(body)
        result = payload["chart"]["result"][0]
        meta = result["meta"]
        timestamps = result.get("timestamp")
        quote = result["indicators"]["quote"][0]
    except (
        KeyError,
        IndexError,
        TypeError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as exc:
        raise CollectorError("Yahoo chart response is malformed") from exc
    if not isinstance(meta, Mapping) or not isinstance(quote, Mapping):
        raise CollectorError("Yahoo chart response is malformed")
    expected_symbol = str(meta.get("symbol", ""))
    expected_currency = str(meta.get("currency", ""))
    instrument_type = str(meta.get("instrumentType", ""))
    venue = str(meta.get("exchangeName", "")).upper()
    venue_aliases = {
        "KSC": {"KSC", "KOSPI", "KOE"},
        "KOSPI": {"KSC", "KOSPI", "KOE"},
        "KOSDAQ": {"KOE", "KOSDAQ"},
        "NAS": {"NAS", "NMS", "NGM"},
        "NMS": {"NAS", "NMS", "NGM"},
        "NYS": {"NYS", "NYQ"},
        "NYQ": {"NYS", "NYQ"},
        "AMS": {"AMS", "PCX"},
        "PCX": {"AMS", "PCX"},
    }
    if (
        expected_symbol != symbol
        or expected_currency != currency
        or instrument_type != "EQUITY"
        or venue not in venue_aliases.get(exchange, {exchange})
    ):
        raise CollectorError("Yahoo chart identity does not match requested stock")
    if not isinstance(timestamps, list):
        raise CollectorError("Yahoo chart timestamps are missing")
    fields = ("open", "high", "low", "close", "volume")
    arrays: dict[str, list[object]] = {}
    for field in fields:
        values = quote.get(field)
        if not isinstance(values, list) or len(values) != len(timestamps):
            raise CollectorError("Yahoo chart arrays have inconsistent lengths")
        arrays[field] = values
    indicators = result.get("indicators")
    if not isinstance(indicators, Mapping):
        raise CollectorError("Yahoo chart indicators are malformed")
    adjusted = indicators.get("adjclose")
    if adjusted is not None:
        if not isinstance(adjusted, list) or not adjusted:
            raise CollectorError("Yahoo adjusted close is malformed")
        if not isinstance(adjusted[0], Mapping):
            raise CollectorError("Yahoo adjusted close is malformed")
        adjusted_values = adjusted[0].get("adjclose")
        if not isinstance(adjusted_values, list) or len(adjusted_values) != len(
            timestamps
        ):
            raise CollectorError("Yahoo chart arrays have inconsistent lengths")
    timezone_name = str(meta.get("exchangeTimezoneName", "UTC"))
    try:
        timezone = ZoneInfo(timezone_name)
    except Exception as exc:
        raise CollectorError("Yahoo chart timezone is invalid") from exc
    bars: list[ApproximateBarRow] = []
    seen_sessions: set[date] = set()
    for index, raw_timestamp in enumerate(timestamps):
        if isinstance(raw_timestamp, bool) or not isinstance(
            raw_timestamp, (int, float)
        ):
            raise CollectorError("Yahoo chart timestamp is invalid")
        try:
            session = (
                datetime.fromtimestamp(raw_timestamp, UTC).astimezone(timezone).date()
            )
        except (OverflowError, OSError, ValueError) as exc:
            raise CollectorError("Yahoo chart timestamp is invalid") from exc
        if session < start or session > end:
            continue
        if session in seen_sessions:
            raise CollectorError("Yahoo chart contains duplicate sessions")
        seen_sessions.add(session)
        values = {field: arrays[field][index] for field in fields}
        if any(value is None for value in values.values()):
            raise CollectorError("Yahoo chart contains incomplete OHLCV")
        bars.append(
            ApproximateBarRow(
                session=session,
                symbol=symbol,
                exchange=exchange,
                open=_decimal(values["open"], "Yahoo open"),
                high=_decimal(values["high"], "Yahoo high"),
                low=_decimal(values["low"], "Yahoo low"),
                close=_decimal(values["close"], "Yahoo close"),
                volume=_decimal(values["volume"], "Yahoo volume", nonnegative=True),
                currency=currency,
                available_at=available_at
                or datetime.combine(session, time(18), tzinfo=UTC),
            )
        )
    if not bars:
        raise CollectorError("Yahoo chart contains no requested sessions")
    raw_events = result.get("events") or {}
    if not isinstance(raw_events, Mapping):
        raise CollectorError("Yahoo chart events are malformed")
    events = tuple(
        str(kind)
        for kind, values in raw_events.items()
        if isinstance(values, dict) and values
    )
    return YahooChart(bars=tuple(bars), events=events)


def parse_fred_observations(
    body: bytes, *, start: date, end: date, available_at: datetime | None = None
) -> tuple[ApproximateFXRow, ...]:
    try:
        payload = json.loads(body)
        raw_rows = payload["observations"]
    except (KeyError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CollectorError("FRED response is malformed") from exc
    if not isinstance(raw_rows, list):
        raise CollectorError("FRED observations are missing")
    result: list[ApproximateFXRow] = []
    for row in raw_rows:
        if not isinstance(row, dict) or row.get("value") in (None, "", "."):
            continue
        session = _date(row.get("date"), "FRED")
        if start <= session <= end:
            row_available_at = available_at or datetime.combine(
                session + timedelta(days=1), time(), UTC
            )
            result.append(
                ApproximateFXRow(
                    session=session,
                    krw_per_usd=_decimal(row["value"], "FRED FX"),
                    spread_rate=Decimal("0"),
                    available_at=row_available_at,
                )
            )
    if not result:
        raise CollectorError("FRED response contains no requested observations")
    if len({item.session for item in result}) != len(result):
        raise CollectorError("FRED response contains duplicate observations")
    return tuple(result)


class CollectorTransport(Protocol):
    async def krx(self, market_board: str, start: date, end: date) -> bytes: ...

    async def alpha_listing(self, as_of: date) -> bytes: ...

    async def yahoo(self, symbol: str, start: date, end: date) -> bytes: ...

    async def fred(self, start: date, end: date) -> bytes: ...


class NetworkCollectorTransport:
    def __init__(self, fetcher: HttpFetcher, settings: CollectorSettings) -> None:
        self.fetcher = fetcher
        self.settings = settings

    async def krx(self, market_board: str, start: date, end: date) -> bytes:
        key = self.settings.krx_auth_key
        if key is None:
            raise CollectorError("KRX_AUTH_KEY is not configured")
        return await self.fetcher.get(
            source="krx",
            url=KRX_URL,
            params={
                "bld": "dbms/MDC/STAT/standard/MDCSTAT01501",
                "mktId": market_board,
                "strtDd": start.strftime("%Y%m%d"),
                "endDd": end.strftime("%Y%m%d"),
                "share": 1,
                "money": 1,
                "csvxls_isNo": "false",
                "AUTH_KEY": key.get_secret_value(),
            },
            checkpoint=f"krx:{market_board}:{start}:{end}",
        )

    async def alpha_listing(self, as_of: date) -> bytes:
        key = self.settings.alpha_vantage_api_key
        if key is None:
            raise CollectorError("ALPHA_VANTAGE_API_KEY is not configured")
        return await self.fetcher.get(
            source="alpha_vantage",
            url=ALPHA_VANTAGE_URL,
            params={
                "function": "LISTING_STATUS",
                "date": as_of.isoformat(),
                "apikey": key.get_secret_value(),
            },
            checkpoint=f"alpha_vantage:{as_of}",
        )

    async def yahoo(self, symbol: str, start: date, end: date) -> bytes:
        return await self.fetcher.get(
            source="yahoo",
            url=f"{YAHOO_URL}/{quote(symbol, safe='.-')}",
            params={
                "period1": int(datetime.combine(start, time(), UTC).timestamp()),
                "period2": int(
                    datetime.combine(end + timedelta(days=1), time(), UTC).timestamp()
                ),
                "interval": "1d",
                "events": "div,splits",
                "includeAdjustedClose": "true",
            },
            checkpoint=f"yahoo:{symbol}:{start}:{end}",
        )

    async def fred(self, start: date, end: date) -> bytes:
        key = self.settings.fred_api_key
        if key is None:
            raise CollectorError("FRED_API_KEY is not configured")
        return await self.fetcher.get(
            source="fred",
            url=FRED_URL,
            params={
                "series_id": "DEXKOUS",
                "api_key": key.get_secret_value(),
                "file_type": "json",
                "observation_start": start.isoformat(),
                "observation_end": end.isoformat(),
            },
            checkpoint=f"fred:{start}:{end}",
        )


def _historical_sessions(
    calendar: MarketCalendar, exchange: str, start: date, end: date
) -> tuple[date, ...]:
    sessions: list[date] = []
    cursor = start
    while cursor <= end:
        if calendar.lookup(exchange, cursor).session is not None:
            sessions.append(cursor)
        cursor += timedelta(days=1)
    return tuple(sessions)


def _warmup_start(calendar: MarketCalendar, exchange: str, start: date) -> date:
    sessions: list[date] = []
    cursor = start - timedelta(days=80)
    while cursor < start:
        if calendar.lookup(exchange, cursor).session is not None:
            sessions.append(cursor)
        cursor += timedelta(days=1)
    if len(sessions) < 20:
        raise CollectorError("calendar does not provide twenty warmup sessions")
    return sessions[-20]


def _listing_checkpoints(sessions: tuple[date, ...]) -> tuple[date, ...]:
    """Return the first available historical session for each calendar year."""
    result: list[date] = []
    seen_years: set[int] = set()
    for session in sessions:
        if session.year not in seen_years:
            result.append(session)
            seen_years.add(session.year)
    return tuple(result)


@dataclass(frozen=True)
class CollectionOutput:
    dataset: ApproximateDataset
    limitations: tuple[str, ...]
    excluded_symbols: tuple[str, ...]


class FreeMarketDataCollector:
    """Collect one bounded approximate dataset without changing the current pool."""

    def __init__(
        self,
        transport: CollectorTransport,
        *,
        calendar: MarketCalendar | None = None,
    ) -> None:
        self.transport = transport
        self.calendar = calendar or default_market_calendar()

    async def collect(
        self,
        *,
        market: Market,
        start: date,
        end: date,
        sample_size: int = 100,
    ) -> CollectionOutput:
        if start > end:
            raise CollectorError("collection start is after end")
        if not 1 <= sample_size <= 100:
            raise CollectorError("sample_size must be between 1 and 100")
        exchange = "KSC" if market == "KR" else "NMS"
        warmup_start = _warmup_start(self.calendar, exchange, start)
        sessions = _historical_sessions(self.calendar, exchange, warmup_start, end)
        if len(sessions) < 21:
            raise CollectorError("requested range lacks warmup and evaluation sessions")
        checkpoint = sessions[0]
        if market == "KR":
            krx_rows: list[ApproximateUniverseRow] = []
            boards: tuple[Literal["STK", "KSQ"], ...] = ("STK", "KSQ")
            for board in boards:
                krx_rows.extend(
                    parse_krx_daily_response(
                        await self.transport.krx(board, warmup_start, end),
                        checkpoint=checkpoint,
                        market_board=board,
                    )
                )
            raw_rows: tuple[ApproximateUniverseRow, ...] = tuple(krx_rows)
            source: Literal["krx", "alpha_vantage"] = "krx"
        else:
            raw_rows = parse_alpha_vantage_listing_status(
                await self.transport.alpha_listing(checkpoint), as_of=checkpoint
            )
            for listing_checkpoint in _listing_checkpoints(sessions)[1:]:
                parse_alpha_vantage_listing_status(
                    await self.transport.alpha_listing(listing_checkpoint),
                    as_of=listing_checkpoint,
                )
            source = "alpha_vantage"
        first_day_rows = tuple(row for row in raw_rows if row.session == checkpoint)
        pool = deterministic_pool(first_day_rows, market=market, pool_end=end)
        symbols = tuple(sorted({row.symbol for row in pool.rows}))[:sample_size]
        if not symbols:
            raise CollectorError("historical eligible universe is empty")
        available_at = datetime.combine(checkpoint, time(18), tzinfo=UTC)
        universe = tuple(
            ApproximateUniverseRow(
                session=session,
                symbol=row.symbol,
                name=row.name,
                exchange=row.exchange,
                instrument_type=row.instrument_type,
                currency=row.currency,
                available_at=(
                    row.available_at
                    if row.available_at is not None and row.available_at <= available_at
                    else available_at
                ),
            )
            for session in sessions
            for row in pool.rows
            if row.symbol in symbols
        )
        bars: list[ApproximateBarRow] = []
        excluded: list[str] = []
        for symbol in symbols:
            row = next(item for item in pool.rows if item.symbol == symbol)
            try:
                chart = parse_yahoo_chart(
                    await self.transport.yahoo(symbol, warmup_start, end),
                    symbol=symbol,
                    exchange=row.exchange,
                    currency="KRW" if market == "KR" else "USD",
                    start=warmup_start,
                    end=end,
                )
            except CollectorError:
                excluded.append(symbol)
                continue
            if chart.events:
                excluded.append(symbol)
                continue
            for chart_bar in chart.bars:
                lookup = self.calendar.lookup(row.exchange, chart_bar.session)
                if lookup.session is None:
                    raise CollectorError(
                        f"calendar session unavailable: {chart_bar.session}"
                    )
                bars.append(
                    chart_bar.model_copy(
                        update={
                            "available_at": lookup.session.close_at
                            + timedelta(minutes=1)
                        }
                    )
                )
        if not bars:
            raise CollectorPartialError("no sampled symbol has a valid Yahoo history")
        fx: tuple[ApproximateFXRow, ...] = ()
        limitations: list[str] = []
        if market == "US":
            fx = parse_fred_observations(
                await self.transport.fred(warmup_start, end),
                start=warmup_start,
                end=end,
            )
            fx = tuple(
                item.model_copy(
                    update={
                        "available_at": datetime.combine(
                            item.session + timedelta(days=1), time(), UTC
                        )
                    }
                )
                for item in fx
            )
            limitations.append(
                "Alpha Vantage annual membership checkpoints are validated, "
                "while the initial checkpoint fixes the sampled pool."
            )
        if excluded:
            limitations.append(
                "Yahoo symbols with missing OHLCV or unresolved corporate actions "
                "were excluded."
            )
        return CollectionOutput(
            dataset=ApproximateDataset(
                market=market,
                universe=tuple(
                    item for item in universe if item.symbol not in excluded
                ),
                bars=tuple(item for item in bars if item.symbol not in excluded),
                fx=fx,
                source=source,
                bar_source="yahoo",
                fx_source="fred",
                simulated=False,
            ),
            limitations=tuple(limitations),
            excluded_symbols=tuple(sorted(excluded)),
        )


async def collect_market_data(
    *,
    market: Market,
    start: date,
    end: date,
    output: Path,
    cache_dir: Path,
    settings: CollectorSettings,
    sample_size: int = 100,
    resume: bool = True,
    client: httpx.AsyncClient | None = None,
) -> CollectionOutput:
    owns_client = client is None
    http_client = client or httpx.AsyncClient()
    try:
        fetcher = HttpFetcher(
            cast(HttpClient, http_client),
            AtomicResponseCache(cache_dir),
            settings,
            resume=resume,
        )
        output_result = await FreeMarketDataCollector(
            NetworkCollectorTransport(fetcher, settings)
        ).collect(market=market, start=start, end=end, sample_size=sample_size)
        content = output_result.dataset.model_dump_json(indent=2).encode()
        temporary: str | None = None
        output.parent.mkdir(parents=True, exist_ok=True)
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=output.parent, prefix=".tmp-", delete=False
            ) as handle:
                temporary = handle.name
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, output)
        finally:
            if temporary is not None and Path(temporary).exists():
                Path(temporary).unlink()
        return output_result
    finally:
        if owns_client:
            await http_client.aclose()


__all__ = [
    "ALPHA_VANTAGE_URL",
    "AtomicResponseCache",
    "ApproximateProviderError",
    "CollectorError",
    "CollectorPartialError",
    "CollectorSettings",
    "FreeMarketDataCollector",
    "NetworkCollectorTransport",
    "RequestBudgetExceeded",
    "collect_market_data",
    "load_collector_settings",
    "parse_alpha_vantage_listing_status",
    "parse_fred_observations",
    "parse_krx_daily_response",
    "parse_yahoo_chart",
]
