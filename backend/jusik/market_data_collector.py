"""Bounded network collection for the approximate market-data workflow.

The collector writes only validated prepared responses.  HTTP is injected so
tests can use deterministic responses, and every raw response is cached by a
content-addressed, secret-free key before it is normalized.
"""

from __future__ import annotations

import asyncio
import csv
import functools
import hashlib
import io
import json
import os
import re
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from pathlib import Path
from typing import Literal, Protocol, cast
from urllib.parse import quote
from zoneinfo import ZoneInfo

import httpx
from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError

from jusik.market_history_approximate import (
    MAX_UNIQUE_SYMBOLS,
    US_EVENT_TIMING_NORMALIZATION_VERSION,
    US_MEMBERSHIP_SEED,
    ApproximateBarRow,
    ApproximateDataset,
    ApproximateEvent,
    ApproximateFXRow,
    ApproximateProviderError,
    ApproximateUniverseRow,
    _event_cutoff_session,
    canonicalize_approximate_events,
    deterministic_pool,
)
from jusik.market_history_models import Market
from jusik.research_market_calendar import MarketCalendar, default_market_calendar

KRX_STK_URL = "https://data-dbg.krx.co.kr/svc/apis/sto/stk_bydd_trd"
KRX_KSQ_URL = "https://data-dbg.krx.co.kr/svc/apis/sto/ksq_bydd_trd"
ALPHA_VANTAGE_URL = "https://www.alphavantage.co/query"
YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart"
FRED_URL = "https://api.stlouisfed.org/fred/series/observations"
MAX_RETRIES = 3
MAX_RETRY_DELAY_SECONDS = 30
DEFAULT_REQUEST_BUDGET = 5_000
MAX_KRX_ROWS_PER_DAY = 10_000
NORMALIZATION_VERSION: str = "approx-v2"
COMPLETION_CONTRACT_VERSION: Literal["collector-completed-v2"] = (
    "collector-completed-v2"
)
CACHE_CONTRACT_VERSION: Literal["collector-cache-v2"] = "collector-cache-v2"


class CollectorError(RuntimeError):
    """A collection cannot produce a trustworthy prepared dataset."""


class CollectorParseError(CollectorError):
    """A provider response is not parseable as the requested payload."""


class CollectorQuotaError(CollectorError):
    """A provider rejected a request because a quota or rate limit was reached."""


class CollectorAuthenticationError(CollectorError):
    """A provider rejected authentication without a retryable response."""


class CollectorPartialError(CollectorError):
    """A bounded collection completed only partially."""


class CollectorNullError(CollectorPartialError):
    """A provider returned an explicit null or empty response envelope."""


class CollectorCoverageError(CollectorPartialError):
    """A valid provider response does not cover the requested range."""


# Keep descriptive compatibility names available to callers that classify the
# response before handling the legacy CollectorError hierarchy.
CollectorNullResponseError = CollectorNullError


class RequestBudgetExceeded(CollectorError):
    """The configured request budget was exhausted."""


def _parse_boundary[**P, T](
    function: Callable[P, T],
) -> Callable[P, T]:
    """Convert parser failures to fixed, provider-body-free exceptions."""

    @functools.wraps(function)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> T:
        try:
            return function(*args, **kwargs)
        except CollectorError as exc:
            if type(exc) is CollectorError:
                raise CollectorParseError(str(exc)) from None
            raise

    return wrapped


def _provider_envelope_error(source: str, body: bytes) -> None:
    """Raise a fixed exception for known provider error envelopes."""

    stripped = body.strip()
    if not stripped or stripped in {b"null", b"NULL"}:
        raise CollectorNullError(f"{source} provider returned a null response")
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return
    if payload is None:
        raise CollectorNullError(f"{source} provider returned a null response")
    if not isinstance(payload, Mapping):
        return

    def text_value(value: object) -> str:
        return value.casefold() if isinstance(value, str) else ""

    def classify_message(message: str, *, default: str) -> None:
        if any(
            marker in message
            for marker in ("quota", "rate limit", "too many", "frequency")
        ):
            raise CollectorQuotaError(f"{source} provider quota was exceeded")
        if any(
            marker in message
            for marker in (
                "invalid api key",
                "invalid apikey",
                "api key is invalid",
                "apikey is invalid",
                "authentication",
                "unauthorized",
                "forbidden",
                "access denied",
            )
        ):
            raise CollectorAuthenticationError(f"{source} authentication was rejected")
        raise CollectorParseError(default)

    if source == "alpha_vantage":
        for key in ("Note", "Information"):
            value = payload.get(key)
            if isinstance(value, str):
                classify_message(
                    text_value(value), default="Alpha Vantage provider error"
                )
        value = payload.get("Error Message")
        if isinstance(value, str):
            classify_message(text_value(value), default="Alpha Vantage provider error")
    elif source == "fred":
        if "error_code" in payload or "error_message" in payload:
            value = payload.get("error_message")
            classify_message(text_value(value), default="FRED provider error")
    elif source == "yahoo":
        chart = payload.get("chart")
        if isinstance(chart, Mapping):
            error = chart.get("error")
            if isinstance(error, Mapping):
                value = error.get("description") or error.get("code")
                classify_message(text_value(value), default="Yahoo provider error")
            if chart.get("result") is None and "result" in chart:
                raise CollectorNullError("Yahoo provider returned a null response")
    elif source == "krx":
        if payload.get("OutBlock_1") is None and "OutBlock_1" in payload:
            raise CollectorNullError("KRX provider returned a null response")
        for key in ("errorCode", "error_code", "resultCode", "result_code"):
            if key in payload:
                code = text_value(payload.get(key))
                if code in {"401", "403"}:
                    raise CollectorAuthenticationError(
                        "KRX authentication was rejected"
                    )
                if code == "429":
                    raise CollectorQuotaError("KRX provider quota was exceeded")
                value = (
                    payload.get("errorMessage")
                    or payload.get("error_message")
                    or payload.get("resultMsg")
                    or payload.get("result_message")
                    or payload.get("message")
                )
                classify_message(text_value(value), default="KRX provider error")


class CollectorSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    krx_auth_key: SecretStr | None = None
    alpha_vantage_api_key: SecretStr | None = None
    fred_api_key: SecretStr | None = None
    request_budget: int = Field(default=DEFAULT_REQUEST_BUDGET, ge=1, le=10_000)
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


def load_collector_settings(env_path: Path | None = None) -> CollectorSettings:
    """Load explicit dotenv values without interpolation or process mutation."""
    file_values: Mapping[str, str | None] = {}
    if env_path is not None:
        if not env_path.is_file():
            raise CollectorError("environment file is unavailable")
        try:
            file_values = dotenv_values(env_path, interpolate=False)
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            raise CollectorError("environment file is invalid") from exc

    def value(standard: str, alias: str) -> str | None:
        for source, name in (
            (os.environ, standard),
            (file_values, standard),
            (os.environ, alias),
            (file_values, alias),
        ):
            candidate = source.get(name)
            if isinstance(candidate, str) and candidate:
                return candidate
        return None

    def secret(standard: str, alias: str) -> SecretStr | None:
        candidate = value(standard, alias)
        return SecretStr(candidate) if candidate else None

    budget = os.environ.get("MARKET_DATA_REQUEST_BUDGET") or file_values.get(
        "MARKET_DATA_REQUEST_BUDGET"
    )
    try:
        parsed_budget = int(budget) if budget else DEFAULT_REQUEST_BUDGET
    except (TypeError, ValueError) as exc:
        raise CollectorError("request budget is invalid") from exc
    try:
        return CollectorSettings(
            krx_auth_key=secret("KRX_AUTH_KEY", "KRX_API_KEY"),
            alpha_vantage_api_key=secret("ALPHA_VANTAGE_API_KEY", "ALPHA_VANTAGE_KEY"),
            fred_api_key=secret("FRED_API_KEY", "FRED_KEY"),
            request_budget=parsed_budget,
        )
    except ValidationError as exc:
        raise CollectorError("collector settings are invalid") from exc


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

    version: Literal["collector-cache-v2"] = CACHE_CONTRACT_VERSION
    entries: tuple[CacheEntry, ...] = ()
    checkpoints: tuple[str, ...] = ()


class CompletedCollection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal["collector-completed-v2"] = COMPLETION_CONTRACT_VERSION
    market: Market
    start: date
    end: date
    sample_size: int = Field(ge=1, le=100)
    output_path: str = Field(min_length=1, max_length=1000)
    output_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    dataset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    completed_at: datetime


class AtomicResponseCache:
    """Content-addressed raw cache with atomic files and a resumable manifest."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.raw_root = root / "raw"
        self.manifest_path = root / "manifest.json"
        self.completed_path = root / "completed.json"

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

    def write_completed(
        self,
        *,
        market: Market,
        start: date,
        end: date,
        sample_size: int,
        output: Path,
        content: bytes,
    ) -> CompletedCollection:
        digest = hashlib.sha256(content).hexdigest()
        marker = CompletedCollection(
            market=market,
            start=start,
            end=end,
            sample_size=sample_size,
            output_path=str(output.resolve()),
            output_sha256=digest,
            dataset_sha256=digest,
            completed_at=datetime.now(UTC),
        )
        self._atomic_write(
            self.completed_path, marker.model_dump_json(indent=2).encode()
        )
        return marker

    def read_completed(self) -> CompletedCollection | None:
        if not self.completed_path.is_file():
            return None
        try:
            return CompletedCollection.model_validate(
                json.loads(self.completed_path.read_bytes())
            )
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
            return None

    def raw_entries_valid(self) -> bool:
        manifest = self._read_manifest()
        for entry in manifest.entries:
            try:
                body = (self.raw_root / f"{entry.key}.bin").read_bytes()
            except OSError:
                return False
            if hashlib.sha256(body).hexdigest() != entry.content_sha256:
                return False
        return True

    def status(self) -> dict[str, object]:
        manifest = self._read_manifest()
        return {
            "cache_dir": str(self.root),
            "entries": len(manifest.entries),
            "checkpoints": list(manifest.checkpoints),
            "completed": self.read_completed() is not None,
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
        method: Literal["GET", "POST"] = "GET",
        data: Mapping[str, str | int] | None = None,
        validator: Callable[[bytes], object] | None = None,
    ) -> bytes:
        def cache_safe(values: Mapping[str, str | int]) -> dict[str, str | int]:
            return {
                key: value
                for key, value in values.items()
                if key.lower() not in {"auth_key", "api_key", "apikey"}
            }

        cache_params = cache_safe(params)
        cache_data = cache_safe(data or {})
        request_key = json.dumps(
            {
                "source": source,
                "url": url,
                "method": method,
                "params": dict(sorted(cache_params.items())),
                "data": dict(sorted(cache_data.items())),
            },
            sort_keys=True,
        )
        cached = self.cache.get(request_key) if self.resume else None
        if cached is not None:
            if validator is not None:
                try:
                    validator(cached[1])
                except CollectorError:
                    raise
                except Exception:
                    raise CollectorParseError(
                        f"{source} response validation failed"
                    ) from None
            return cached[1]
        if self.requests_used >= self.settings.request_budget:
            raise RequestBudgetExceeded("collector request budget exhausted")
        request_headers = {"User-Agent": "jusik-market-data-collector/1.0"}
        if headers:
            request_headers.update(headers)
        for attempt in range(self.settings.max_retries + 1):
            if self.requests_used >= self.settings.request_budget:
                raise RequestBudgetExceeded("collector request budget exhausted")
            self.requests_used += 1
            try:
                request_kwargs: dict[str, object] = {
                    "headers": request_headers,
                    "timeout": self.settings.timeout_seconds,
                }
                if method == "POST":
                    request_kwargs["data"] = data or {}
                else:
                    request_kwargs["params"] = params
                response = await self.client.request(
                    method,
                    url,
                    **request_kwargs,
                )
            except (httpx.HTTPError, TimeoutError) as exc:
                if attempt >= self.settings.max_retries:
                    raise CollectorError(f"{source} request failed") from exc
                await asyncio.sleep(min(2**attempt, MAX_RETRY_DELAY_SECONDS))
                continue
            if response.status_code in {401, 403}:
                raise CollectorAuthenticationError(
                    f"{source} authentication was rejected"
                )
            if response.status_code == 429 or response.status_code >= 500:
                if attempt >= self.settings.max_retries:
                    if response.status_code == 429:
                        raise CollectorQuotaError(
                            f"{source} provider quota was exceeded"
                        )
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
            if validator is not None:
                try:
                    validator(body)
                except CollectorError:
                    raise
                except Exception:
                    raise CollectorParseError(
                        f"{source} response validation failed"
                    ) from None
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


def _krx_rows(payload: object) -> list[Mapping[str, object]]:
    if not isinstance(payload, dict) or "OutBlock_1" not in payload:
        raise CollectorError("KRX response envelope is missing")
    raw_rows = payload["OutBlock_1"]
    if not isinstance(raw_rows, list) or any(
        not isinstance(row, Mapping) for row in raw_rows
    ):
        raise CollectorError("KRX response rows are malformed")
    return _rows(payload)


def _field(row: Mapping[str, object], *names: str) -> object | None:
    for name in names:
        if name in row and row[name] not in (None, ""):
            return row[name]
    return None


@dataclass(frozen=True)
class KRXDailyResponse:
    universe: tuple[ApproximateUniverseRow, ...]
    bars: tuple[ApproximateBarRow, ...]
    listed_shares: dict[str, Decimal | None]


@_parse_boundary
def parse_krx_daily_trade_response(
    body: bytes,
    *,
    checkpoint: date,
    market_board: Literal["STK", "KSQ"] = "STK",
    available_at: datetime | None = None,
) -> KRXDailyResponse:
    _provider_envelope_error("krx", body)
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CollectorError("KRX response is not valid JSON") from exc
    if isinstance(payload, dict):
        response_date = _field(payload, "basDd", "BAS_DD", "trdDd", "TRD_DD")
        if response_date is not None and _date(response_date, "KRX") != checkpoint:
            raise CollectorError("KRX response date does not match request")
        response_board = _field(payload, "mktNm", "MKT_NM", "market", "mktId")
        if response_board is not None:
            expected_board = "KOSDAQ" if market_board == "KSQ" else "KOSPI"
            board_text = str(response_board).strip().upper()
            accepted_boards = {
                "KOSPI": {"KOSPI", "STK", "KSC"},
                "KOSDAQ": {"KOSDAQ", "KSQ", "KQ"},
            }
            if board_text not in accepted_boards[expected_board]:
                raise CollectorError("KRX response board does not match request")
    rows = _krx_rows(payload)
    if len(rows) > MAX_KRX_ROWS_PER_DAY:
        raise CollectorError("KRX daily response exceeds the row bound")
    normalized: list[ApproximateUniverseRow] = []
    bars: list[ApproximateBarRow] = []
    listed_shares: dict[str, Decimal | None] = {}
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
        if session != checkpoint:
            raise CollectorError("KRX response date does not match request")
        symbol = str(
            _field(
                row,
                "ISU_SRT_CD",
                "ISU_CD",
                "isu_srt_cd",
                "symbol",
                "stck_shrn_iscd",
            )
            or ""
        ).strip()
        name = str(
            _field(
                row,
                "ISU_ABBRV",
                "ISU_NM",
                "isu_abbrv",
                "name",
                "bstp_kor_isnm",
            )
            or ""
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
        if exchange_raw:
            expected_board = "KOSDAQ" if market_board == "KSQ" else "KOSPI"
            board_aliases = {
                "KOSPI": {"KOSPI", "STK", "KSC"},
                "KOSDAQ": {"KOSDAQ", "KSQ", "KQ"},
            }
            if exchange_raw not in board_aliases[expected_board]:
                raise CollectorError("KRX response board does not match request")
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
        listed_shares_value = _field(row, "LIST_SHRS", "list_shrs", "listed_shares")
        listed_shares[symbol] = (
            _decimal(listed_shares_value, "KRX listed shares", nonnegative=True)
            if listed_shares_value is not None
            else None
        )
        price_fields = (
            _field(row, "TDD_OPNPRC", "opnprc", "open"),
            _field(row, "TDD_HGPRC", "hgprc", "high"),
            _field(row, "TDD_LWPRC", "lwprc", "low"),
            _field(row, "TDD_CLSPRC", "clsprc", "close"),
            _field(row, "ACC_TRDVOL", "acml_vol", "volume"),
        )
        # KRX uses '-' for an untraded price. Preserve membership but do not
        # invent a daily bar for that symbol.
        if all(
            value is not None and str(value).strip() not in {"", "-"}
            for value in price_fields
        ):
            assert all(value is not None for value in price_fields)
            bars.append(
                ApproximateBarRow(
                    session=session,
                    symbol=symbol,
                    exchange=exchange,
                    open=_decimal(price_fields[0], "KRX open"),
                    high=_decimal(price_fields[1], "KRX high"),
                    low=_decimal(price_fields[2], "KRX low"),
                    close=_decimal(price_fields[3], "KRX close"),
                    volume=_decimal(price_fields[4], "KRX volume", nonnegative=True),
                    currency="KRW",
                    available_at=row_available_at,
                )
            )
    if not normalized:
        raise CollectorError("KRX response contains no valid stock rows")
    return KRXDailyResponse(
        universe=tuple(normalized), bars=tuple(bars), listed_shares=listed_shares
    )


@_parse_boundary
def parse_krx_daily_response(
    body: bytes,
    *,
    checkpoint: date,
    market_board: Literal["STK", "KSQ"] = "STK",
    available_at: datetime | None = None,
) -> tuple[ApproximateUniverseRow, ...]:
    """Compatibility wrapper returning the normalized membership rows."""
    return parse_krx_daily_trade_response(
        body,
        checkpoint=checkpoint,
        market_board=market_board,
        available_at=available_at,
    ).universe


@dataclass(frozen=True)
class AlphaListingParseResult:
    rows: tuple[ApproximateUniverseRow, ...]
    input_rows: int
    accepted: int
    excluded: tuple[tuple[str, int], ...]


class _AlphaProductType(StrEnum):
    ORDINARY = "ordinary"
    ETF = "etf"
    WARRANT = "warrant"
    OTHER = "other"
    UNKNOWN = "unknown"


_ALPHA_ASSET_TYPE_MAP: dict[str, _AlphaProductType] = {
    "stock": _AlphaProductType.ORDINARY,
    "common stock": _AlphaProductType.ORDINARY,
    "common_stock": _AlphaProductType.ORDINARY,
    "etf": _AlphaProductType.ETF,
    "warrant": _AlphaProductType.WARRANT,
    "warrants": _AlphaProductType.WARRANT,
    "right": _AlphaProductType.OTHER,
    "rights": _AlphaProductType.OTHER,
    "unit": _AlphaProductType.OTHER,
    "units": _AlphaProductType.OTHER,
    "preferred": _AlphaProductType.OTHER,
    "preferred stock": _AlphaProductType.OTHER,
    "preferred shares": _AlphaProductType.OTHER,
    "etn": _AlphaProductType.OTHER,
    "etns": _AlphaProductType.OTHER,
    "adr": _AlphaProductType.OTHER,
    "ads": _AlphaProductType.OTHER,
    "depositary receipt": _AlphaProductType.OTHER,
    "depositary receipts": _AlphaProductType.OTHER,
    "fund": _AlphaProductType.OTHER,
    "bond": _AlphaProductType.OTHER,
    "note": _AlphaProductType.OTHER,
    "trust": _AlphaProductType.OTHER,
}

_ALPHA_NAME_PRODUCT_PATTERNS: tuple[tuple[_AlphaProductType, re.Pattern[str]], ...] = (
    (_AlphaProductType.ETF, re.compile(r"\betfs?\b")),
    (_AlphaProductType.WARRANT, re.compile(r"\bwarrants?\b")),
    (
        _AlphaProductType.OTHER,
        re.compile(
            r"\bunits?(?:\s*[,;:.]?\s*$|\s*(?:[,;:]\s*)?(?:each|consisting\s+of)\b)"
        ),
    ),
    (
        _AlphaProductType.OTHER,
        re.compile(
            r"\brights?(?:\s*[,;:.]?\s*$|\s*(?:[,;:]\s*)?(?:each|consisting\s+of)\b)"
        ),
    ),
    (_AlphaProductType.OTHER, re.compile(r"\betns?\b")),
    (
        _AlphaProductType.OTHER,
        re.compile(r"\bpreferred[-\s]+(?:stock|shares?)\b"),
    ),
    (_AlphaProductType.OTHER, re.compile(r"\b(?:adr|ads)\b")),
    (_AlphaProductType.OTHER, re.compile(r"\bdepositary\s+receipts?\b")),
)


def _classify_alpha_product(
    asset_type: str, *, symbol: str = "", name: str = ""
) -> _AlphaProductType:
    """Classify one listing from independent, conservative product evidence."""
    evidence: set[_AlphaProductType] = set()
    mapped = _ALPHA_ASSET_TYPE_MAP.get(asset_type.strip().casefold())
    if mapped is not None:
        evidence.add(mapped)
    if re.search(r"(?:-ws|\.ws|-wt|\.wt)$", symbol.strip(), re.IGNORECASE):
        evidence.add(_AlphaProductType.WARRANT)
    normalized_name = name.strip().casefold()
    for product_type, pattern in _ALPHA_NAME_PRODUCT_PATTERNS:
        if pattern.search(normalized_name):
            evidence.add(product_type)

    nonordinary = evidence - {_AlphaProductType.ORDINARY}
    if len(nonordinary) == 1:
        return next(iter(nonordinary))
    if len(nonordinary) > 1:
        return _AlphaProductType.UNKNOWN
    return _AlphaProductType.ORDINARY if evidence else _AlphaProductType.UNKNOWN


_ALPHA_EXCHANGE_MAP = {
    "NYSE": "NYS",
    "NASDAQ": "NAS",
    "NASDAQ CAPITAL MARKET": "NAS",
    "NASDAQ GLOBAL MARKET": "NAS",
    "NASDAQ GLOBAL SELECT MARKET": "NAS",
    "NCM": "NAS",
    "NGM": "NAS",
    "NMS": "NAS",
    "NYSE ARCA": "AMS",
    "NYSEARCA": "AMS",
}


def _normalize_alpha_exchange(exchange: str) -> str:
    """Normalize Alpha exchange labels without using product information."""
    normalized = exchange.strip().upper()
    return _ALPHA_EXCHANGE_MAP.get(normalized, normalized)


_ALPHA_HEADERS = frozenset(
    {"symbol", "name", "exchange", "assetType", "ipoDate", "delistingDate", "status"}
)


@_parse_boundary
def parse_alpha_vantage_listing_status_detailed(
    body: bytes, *, as_of: date, available_at: datetime | None = None
) -> AlphaListingParseResult:
    _provider_envelope_error("alpha_vantage", body)
    try:
        text = body.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text), strict=True)
        headers = reader.fieldnames
        if (
            headers is None
            or set(headers) != _ALPHA_HEADERS
            or len(headers) != len(_ALPHA_HEADERS)
        ):
            raise CollectorError("Alpha Vantage CSV header is invalid")
        rows = list(reader)
    except CollectorError:
        raise
    except (UnicodeDecodeError, csv.Error) as exc:
        raise CollectorError("Alpha Vantage response is not valid CSV") from exc
    if not rows:
        raise CollectorError("Alpha Vantage response contains no listings")
    observed_at = available_at or datetime.combine(as_of, time(18), tzinfo=UTC)
    result: list[ApproximateUniverseRow] = []
    seen: set[str] = set()
    exclusion_counts: dict[str, int] = {}

    def exclude(reason: str) -> None:
        exclusion_counts[reason] = exclusion_counts.get(reason, 0) + 1

    for row in rows:
        if None in row or any(value is None for value in row.values()):
            exclude("schema")
            continue
        symbol = (row.get("symbol") or "").strip()
        name = (row.get("name") or "").strip()
        exchange_raw = (row.get("exchange") or "").strip().upper()
        asset_type = (row.get("assetType") or "").strip().casefold()
        status = (row.get("status") or "").strip().casefold()
        if (
            not symbol
            or len(symbol) > 20
            or any(not (char.isalnum() or char in ".-_^") for char in symbol)
        ):
            exclude("symbol")
            continue
        if not name or len(name) > 120:
            exclude("name")
            continue
        exchange = _normalize_alpha_exchange(exchange_raw)
        if exchange not in {"NAS", "NYS", "AMS"}:
            exclude("exchange")
            continue
        product_type = _classify_alpha_product(asset_type, symbol=symbol, name=name)
        if product_type is not _AlphaProductType.ORDINARY:
            exclude("security_type")
            continue
        if status not in {"active", "delisted"}:
            exclude("status")
            continue
        try:
            ipo_raw = row.get("ipoDate") or ""
            delisted_raw = row.get("delistingDate") or ""
            ipo = (
                None
                if ipo_raw.casefold() in {"null", "none"}
                else (_date(ipo_raw, "ipo") if ipo_raw else None)
            )
            delisted = (
                None
                if delisted_raw.casefold() in {"null", "none"}
                else (_date(delisted_raw, "delisting") if delisted_raw else None)
            )
        except CollectorError:
            exclude("date")
            continue
        if (ipo is not None and ipo > as_of) or (
            delisted is not None and delisted < as_of
        ):
            exclude("date")
            continue
        if symbol in seen:
            exclude("duplicate")
            continue
        seen.add(symbol)
        result.append(
            ApproximateUniverseRow(
                session=as_of,
                symbol=symbol,
                name=name,
                exchange=exchange,
                currency="USD",
                available_at=observed_at,
            )
        )
    if not result:
        raise CollectorError("Alpha Vantage response contains no eligible stocks")
    return AlphaListingParseResult(
        rows=tuple(result),
        input_rows=len(rows),
        accepted=len(result),
        excluded=tuple(sorted(exclusion_counts.items())),
    )


@_parse_boundary
def parse_alpha_vantage_listing_status(
    body: bytes, *, as_of: date, available_at: datetime | None = None
) -> tuple[ApproximateUniverseRow, ...]:
    return parse_alpha_vantage_listing_status_detailed(
        body, as_of=as_of, available_at=available_at
    ).rows


@dataclass(frozen=True)
class YahooChart:
    bars: tuple[ApproximateBarRow, ...]
    events: tuple[str, ...]
    event_rows: tuple[ApproximateEvent, ...] = ()


def _event_datetime(value: object, field: str) -> datetime | None:
    """Parse an event timestamp without inventing an intraday boundary."""
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        raise CollectorError(f"Yahoo {field} timestamp is invalid")
    if isinstance(value, (int, float, Decimal)):
        try:
            result = datetime.fromtimestamp(float(value), UTC)
        except (OverflowError, OSError, ValueError) as exc:
            raise CollectorError(f"Yahoo {field} timestamp is invalid") from exc
        return result
    if not isinstance(value, str):
        raise CollectorError(f"Yahoo {field} timestamp is invalid")
    text = value.strip()
    if not text:
        return None
    if re.fullmatch(r"\d+(?:\.\d+)?", text):
        try:
            return datetime.fromtimestamp(float(text), UTC)
        except (OverflowError, OSError, ValueError) as exc:
            raise CollectorError(f"Yahoo {field} timestamp is invalid") from exc
    # A date-only provider value has no safe intraday ordering.  Preserve the
    # event as unknown rather than treating midnight as its occurrence time.
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        try:
            date.fromisoformat(text)
        except ValueError as exc:
            raise CollectorError(f"Yahoo {field} timestamp is invalid") from exc
        return None
    try:
        result = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CollectorError(f"Yahoo {field} timestamp is invalid") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise CollectorError(f"Yahoo {field} timestamp must include a timezone")
    return result.astimezone(UTC)


@_parse_boundary
def parse_yahoo_chart(
    body: bytes,
    *,
    symbol: str,
    exchange: str | None,
    currency: Literal["KRW", "USD"] | None,
    start: date,
    end: date,
    available_at: datetime | None = None,
    observed_at: datetime | None = None,
) -> YahooChart:
    _provider_envelope_error("yahoo", body)
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
        "NAS": {"NAS", "NMS", "NGM", "NCM"},
        "NMS": {"NAS", "NMS", "NGM", "NCM"},
        "NYS": {"NYS", "NYQ"},
        "NYQ": {"NYS", "NYQ"},
        "AMS": {"AMS", "PCX"},
        "PCX": {"AMS", "PCX"},
    }
    if (
        expected_symbol != symbol
        or (currency is not None and expected_currency != currency)
        or instrument_type != "EQUITY"
        or not venue
        or (
            exchange is not None
            and venue not in venue_aliases.get(exchange, {exchange})
        )
    ):
        raise CollectorError("Yahoo chart identity does not match requested stock")
    if expected_currency not in {"KRW", "USD"}:
        raise CollectorError("Yahoo chart currency is invalid")
    normalized_exchange = exchange or venue
    normalized_currency = cast(Literal["KRW", "USD"], expected_currency)
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
                exchange=normalized_exchange,
                open=_decimal(values["open"], "Yahoo open"),
                high=_decimal(values["high"], "Yahoo high"),
                low=_decimal(values["low"], "Yahoo low"),
                close=_decimal(values["close"], "Yahoo close"),
                volume=_decimal(values["volume"], "Yahoo volume", nonnegative=True),
                currency=normalized_currency,
                available_at=available_at
                or datetime.combine(session, time(18), tzinfo=UTC),
            )
        )
    if not bars:
        raise CollectorCoverageError("Yahoo chart contains no requested sessions")
    raw_events = result.get("events") or {}
    if not isinstance(raw_events, Mapping):
        raise CollectorError("Yahoo chart events are malformed")
    # ``available_at`` timestamps the returned bars.  It is deliberately not
    # reused as an event observation timestamp: only the explicit event field
    # or ``observed_at`` supplied by the provider is authoritative.
    supplied_observed_at = observed_at
    if supplied_observed_at is not None:
        if (
            supplied_observed_at.tzinfo is None
            or supplied_observed_at.utcoffset() is None
        ):
            raise CollectorError("Yahoo event observation must include a timezone")
        supplied_observed_at = supplied_observed_at.astimezone(UTC)
    events = tuple(
        sorted(
            str(kind)
            for kind, values in raw_events.items()
            if isinstance(values, dict) and values
        )
    )
    event_rows: list[ApproximateEvent] = []
    event_time_fields = {
        "occurrence_at",
        "occurrenceAt",
        "timestamp",
        "date",
        "observed_at",
        "observedAt",
    }
    for kind, raw_values in raw_events.items():
        if not isinstance(raw_values, Mapping) or not raw_values:
            if raw_values not in ({}, None):
                raise CollectorError("Yahoo chart events are malformed")
            continue
        entries: list[tuple[object | None, Mapping[str, object]]]
        if event_time_fields.intersection(raw_values):
            entries = [(None, cast(Mapping[str, object], raw_values))]
        else:
            entries = [
                (key, cast(Mapping[str, object], value))
                for key, value in raw_values.items()
                if isinstance(value, Mapping)
            ]
            if len(entries) != len(raw_values):
                raise CollectorError("Yahoo chart events are malformed")
        for event_key_value, values in entries:
            occurrence_value = next(
                (
                    values.get(name)
                    for name in (
                        "occurrence_at",
                        "occurrenceAt",
                        "timestamp",
                        "date",
                    )
                    if values.get(name) not in (None, "")
                ),
                None,
            )
            invalid_timing = False
            try:
                occurrence_at = _event_datetime(occurrence_value, "event")
            except CollectorError:
                occurrence_at = None
                invalid_timing = True
            if occurrence_value in (None, "") and (
                isinstance(event_key_value, (int, float))
                or (
                    isinstance(event_key_value, str)
                    and re.fullmatch(r"\d+(?:\.\d+)?", event_key_value) is not None
                )
            ):
                try:
                    occurrence_at = _event_datetime(event_key_value, "event")
                except CollectorError:
                    occurrence_at = None
                    invalid_timing = True
            event_observed_value = next(
                (
                    values.get(name)
                    for name in ("observed_at", "observedAt")
                    if values.get(name) not in (None, "")
                ),
                None,
            )
            try:
                event_observed_at = _event_datetime(event_observed_value, "observation")
            except CollectorError:
                event_observed_at = None
                invalid_timing = True
            if event_observed_at is None:
                event_observed_at = supplied_observed_at
            event_rows.append(
                ApproximateEvent(
                    symbol=symbol,
                    kind=str(kind),
                    occurrence_at=occurrence_at,
                    observed_at=event_observed_at,
                    invalid_timing=invalid_timing,
                    source="yahoo",
                )
            )
    normalized_event_rows, _ = canonicalize_approximate_events(tuple(event_rows))
    return YahooChart(bars=tuple(bars), events=events, event_rows=normalized_event_rows)


@_parse_boundary
def parse_fred_observations(
    body: bytes, *, start: date, end: date, available_at: datetime | None = None
) -> tuple[ApproximateFXRow, ...]:
    _provider_envelope_error("fred", body)
    try:
        payload = json.loads(body)
        raw_rows = payload["observations"]
    except (KeyError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CollectorError("FRED response is malformed") from exc
    if not isinstance(raw_rows, list):
        raise CollectorError("FRED observations are missing")
    if not raw_rows:
        raise CollectorNullError("FRED provider returned an empty observation set")
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
        raise CollectorCoverageError("FRED response contains no requested observations")
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
        normalized_board = {
            "STK": "STK",
            "KOSPI": "STK",
            "KSQ": "KSQ",
            "KOSDAQ": "KSQ",
        }.get(market_board.upper())
        endpoint = (
            KRX_STK_URL
            if normalized_board == "STK"
            else KRX_KSQ_URL
            if normalized_board == "KSQ"
            else None
        )
        if endpoint is None:
            raise CollectorError("KRX market board is invalid")

        def validate(body: bytes) -> None:
            _provider_envelope_error("krx", body)
            try:
                payload = json.loads(body)
            except (UnicodeDecodeError, json.JSONDecodeError):
                payload = None
            if isinstance(payload, dict) and payload.get("OutBlock_1") == []:
                return
            parse_krx_daily_trade_response(
                body,
                checkpoint=start,
                market_board=cast(Literal["STK", "KSQ"], normalized_board),
            )

        return await self.fetcher.get(
            source="krx",
            url=endpoint,
            params={"basDd": start.strftime("%Y%m%d")},
            headers={
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "ko-KR,ko;q=0.9",
                "AUTH_KEY": key.get_secret_value(),
            },
            checkpoint=f"krx:daily:{normalized_board}:{start}",
            validator=validate,
        )

    async def alpha_listing(self, as_of: date) -> bytes:
        key = self.settings.alpha_vantage_api_key
        if key is None:
            raise CollectorError("ALPHA_VANTAGE_API_KEY is not configured")

        def validate(body: bytes) -> None:
            _provider_envelope_error("alpha_vantage", body)
            parse_alpha_vantage_listing_status_detailed(body, as_of=as_of)

        return await self.fetcher.get(
            source="alpha_vantage",
            url=ALPHA_VANTAGE_URL,
            params={
                "function": "LISTING_STATUS",
                "date": as_of.isoformat(),
                "apikey": key.get_secret_value(),
            },
            checkpoint=f"alpha_vantage:{as_of}",
            validator=validate,
        )

    async def yahoo(self, symbol: str, start: date, end: date) -> bytes:
        def validate(body: bytes) -> None:
            _provider_envelope_error("yahoo", body)
            parse_yahoo_chart(
                body,
                symbol=symbol,
                exchange=None,
                currency=None,
                start=start,
                end=end,
            )

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
            validator=validate,
        )

    async def fred(self, start: date, end: date) -> bytes:
        key = self.settings.fred_api_key
        if key is None:
            raise CollectorError("FRED_API_KEY is not configured")

        def validate(body: bytes) -> None:
            _provider_envelope_error("fred", body)
            parse_fred_observations(body, start=start, end=end)

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
            validator=validate,
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


def estimate_network_requests(
    *, market: Market, start: date, end: date, sample_size: int = 100
) -> int:
    """Estimate uncached calls before starting a potentially large collection."""
    if not 1 <= sample_size <= 100:
        raise CollectorError("sample_size must be between 1 and 100")
    calendar = default_market_calendar()
    exchange = "KSC" if market == "KR" else "NMS"
    warmup_start = _warmup_start(calendar, exchange, start)
    sessions = _historical_sessions(calendar, exchange, warmup_start, end)
    if market == "KR":
        # Two boards each require one date-specific daily trade response.
        return len(sessions) * 2
    checkpoint_count = len(_listing_checkpoints(sessions))
    return (
        checkpoint_count
        + min(MAX_UNIQUE_SYMBOLS, sample_size * checkpoint_count)
        + 1
    )


def completed_collection_is_valid(
    cache: AtomicResponseCache,
    *,
    market: Market,
    start: date,
    end: date,
    sample_size: int,
    output: Path,
) -> bool:
    marker = cache.read_completed()
    if marker is None or not cache.raw_entries_valid():
        return False
    if (
        marker.market != market
        or marker.start != start
        or marker.end != end
        or marker.sample_size != sample_size
        or marker.output_path != str(output.resolve())
    ):
        return False
    try:
        content = output.read_bytes()
        ApproximateDataset.model_validate_json(content)
    except (OSError, ValueError):
        return False
    digest = hashlib.sha256(content).hexdigest()
    return digest == marker.output_sha256 == marker.dataset_sha256


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
        alpha_limitations: list[str] = []
        us_symbol_details: dict[str, ApproximateUniverseRow] = {}
        if market == "KR":
            krx_rows: list[ApproximateUniverseRow] = []
            krx_bars: list[ApproximateBarRow] = []
            krx_listed_shares: dict[date, dict[str, Decimal | None]] = {}
            krx_symbols: dict[date, set[str]] = {}
            krx_bar_symbols: dict[date, set[str]] = {}
            boards: tuple[Literal["STK", "KSQ"], ...] = ("STK", "KSQ")
            for session in sessions:
                for board in boards:
                    lookup = self.calendar.lookup(
                        "KSC" if board == "STK" else "KOSDAQ", session
                    )
                    if lookup.session is None:
                        raise CollectorError(f"calendar session unavailable: {session}")
                    daily_body = await self.transport.krx(board, session, session)
                    try:
                        daily = parse_krx_daily_trade_response(
                            daily_body,
                            checkpoint=session,
                            market_board=board,
                            # KRX EOD is modeled as complete at the official close;
                            # next-open fills remain the first executable decision.
                            available_at=lookup.session.close_at,
                        )
                    except CollectorError:
                        # A valid empty day is a halt/no-trade observation. Other
                        # malformed responses remain fatal to preserve coverage.
                        try:
                            empty_payload = json.loads(daily_body)
                        except (UnicodeDecodeError, json.JSONDecodeError):
                            raise
                        empty_rows = (
                            empty_payload.get("OutBlock_1")
                            if isinstance(empty_payload, dict)
                            else None
                        )
                        if empty_rows != []:
                            raise
                        daily = KRXDailyResponse(universe=(), bars=(), listed_shares={})
                    krx_rows.extend(daily.universe)
                    krx_bars.extend(daily.bars)
                    krx_listed_shares.setdefault(session, {}).update(
                        daily.listed_shares
                    )
                    krx_symbols.setdefault(session, set()).update(
                        row.symbol for row in daily.universe
                    )
                    krx_bar_symbols.setdefault(session, set()).update(
                        row.symbol for row in daily.bars
                    )
            raw_rows: tuple[ApproximateUniverseRow, ...] = tuple(krx_rows)
            source: Literal["krx", "alpha_vantage"] = "krx"
        else:
            checkpoint_rows: dict[date, tuple[ApproximateUniverseRow, ...] | None] = {}
            checkpoint_selected: dict[date, tuple[str, ...]] = {}
            admitted_symbols: set[str] = set()
            us_current_symbols: tuple[str, ...] = ()
            symbol_details = us_symbol_details
            listing_checkpoints = _listing_checkpoints(sessions)
            for checkpoint_index, listing_checkpoint in enumerate(listing_checkpoints):
                lookup = self.calendar.lookup("NMS", listing_checkpoint)
                if lookup.session is None:
                    raise CollectorError(
                        f"calendar session unavailable: {listing_checkpoint}"
                    )
                try:
                    listing = parse_alpha_vantage_listing_status_detailed(
                        await self.transport.alpha_listing(listing_checkpoint),
                        as_of=listing_checkpoint,
                        available_at=lookup.session.close_at,
                    )
                except CollectorError:
                    if checkpoint_index == 0:
                        raise
                    checkpoint_rows[listing_checkpoint] = None
                    alpha_limitations.append(
                        "Alpha Vantage membership checkpoint unavailable: "
                        f"{listing_checkpoint}; current_selected=0; "
                        f"cumulative_admitted={len(admitted_symbols)}"
                    )
                    continue
                checkpoint_rows[listing_checkpoint] = listing.rows
                eligible = {row.symbol for row in listing.rows}
                for row in listing.rows:
                    symbol_details.setdefault(row.symbol, row)
                seeded = sorted(
                    eligible,
                    key=lambda symbol: hashlib.sha256(
                        f"{US_MEMBERSHIP_SEED}:US:{symbol}".encode()
                    ).hexdigest(),
                )
                if checkpoint_index == 0:
                    us_current_symbols = tuple(seeded[:sample_size])
                    admitted_symbols.update(us_current_symbols)
                else:
                    retained = [
                        symbol for symbol in us_current_symbols if symbol in eligible
                    ]
                    retained_set = set(retained)
                    for symbol in seeded:
                        if len(retained) >= sample_size:
                            break
                        if symbol in retained_set:
                            continue
                        if symbol not in admitted_symbols:
                            if len(admitted_symbols) >= MAX_UNIQUE_SYMBOLS:
                                continue
                            admitted_symbols.add(symbol)
                        retained.append(symbol)
                        retained_set.add(symbol)
                    us_current_symbols = tuple(retained)
                checkpoint_selected[listing_checkpoint] = us_current_symbols
                alpha_limitations.append(
                    self._alpha_checkpoint_summary(
                        listing_checkpoint,
                        listing,
                        selected=len(us_current_symbols),
                        cumulative_admitted=len(admitted_symbols),
                    )
                )
            if not admitted_symbols:
                raise CollectorError("historical eligible universe is empty")
            symbols = tuple(sorted(admitted_symbols))
            if not symbols:
                raise CollectorError("historical eligible universe is empty")
            # Expand each successful checkpoint selection through its known
            # interval. A failed checkpoint starts an unknown interval; no
            # membership rows are emitted until the next successful checkpoint.
            universe_rows: list[ApproximateUniverseRow] = []
            last_available: dict[str, datetime] = {}

            def exchange_close(session: date) -> datetime:
                lookup = self.calendar.lookup("NMS", session)
                if lookup.session is None:
                    raise CollectorError(f"calendar session unavailable: {session}")
                return lookup.session.close_at

            effective_starts: dict[date, date] = {}
            for listing_checkpoint in listing_checkpoints:
                checkpoint_listing = checkpoint_rows.get(listing_checkpoint)
                if checkpoint_listing is None:
                    continue
                checkpoint_close = exchange_close(listing_checkpoint)
                known_at = max(
                    (
                        row.available_at or checkpoint_close
                        for row in checkpoint_listing
                    ),
                    default=checkpoint_close,
                )
                effective_start = next(
                    (
                        session
                        for session in sessions
                        if session >= listing_checkpoint
                        and exchange_close(session) >= known_at
                    ),
                    None,
                )
                if effective_start is not None:
                    effective_starts[listing_checkpoint] = effective_start
            for checkpoint_index, listing_checkpoint in enumerate(listing_checkpoints):
                selected = checkpoint_selected.get(listing_checkpoint)
                effective_start = effective_starts.get(listing_checkpoint)
                if selected is None or effective_start is None:
                    continue
                next_checkpoint = None
                if checkpoint_index + 1 < len(listing_checkpoints):
                    next_checkpoint = listing_checkpoints[checkpoint_index + 1]
                    next_effective = effective_starts.get(next_checkpoint)
                    if next_effective is not None:
                        next_checkpoint = next_effective
                    elif checkpoint_rows.get(next_checkpoint) is not None:
                        # The successful observation is after the requested
                        # range. Keep the prior state through the range; the
                        # transition cannot be applied yet.
                        next_checkpoint = None
                period_sessions = tuple(
                    session
                    for session in sessions
                    if session >= effective_start
                    and (next_checkpoint is None or session < next_checkpoint)
                )
                details_by_symbol = {
                    row.symbol: row
                    for row in checkpoint_rows[listing_checkpoint] or ()
                }
                for session in period_sessions:
                    for symbol in selected:
                        detail = details_by_symbol.get(symbol) or symbol_details[symbol]
                        available_at = detail.available_at
                        if available_at is None:
                            available_at = exchange_close(listing_checkpoint)
                        previous_available = last_available.get(symbol)
                        if previous_available is not None:
                            available_at = max(available_at, previous_available)
                        last_available[symbol] = available_at
                        universe_rows.append(
                            detail.model_copy(
                                update={
                                    "session": session,
                                    "available_at": available_at,
                                }
                            )
                        )
            raw_rows = tuple(universe_rows)
            selected_symbols = set(symbols)
            source = "alpha_vantage"
            normalization_version = US_EVENT_TIMING_NORMALIZATION_VERSION
        if market == "KR":
            first_day_rows = tuple(row for row in raw_rows if row.session == checkpoint)
            pool = deterministic_pool(first_day_rows, market=market, pool_end=end)
            symbols = tuple(sorted({row.symbol for row in pool.rows}))[:sample_size]
            if not symbols:
                raise CollectorError("historical eligible universe is empty")
            selected_symbols = set(symbols)
            normalization_version = NORMALIZATION_VERSION
        event_dates: dict[str, date] = {}
        event_reasons: dict[str, str] = {}
        us_events: list[ApproximateEvent] = []
        us_event_cutoffs: dict[str, date] = {}
        if market == "KR":
            universe = tuple(row for row in raw_rows if row.symbol in selected_symbols)
            previous_details: dict[str, Decimal] = {}
            previous_symbols: set[str] | None = None
            missing_sessions: dict[str, date] = {}
            for session in sessions:
                current_symbols = krx_symbols.get(session, set()) & selected_symbols
                current_bar_symbols = (
                    krx_bar_symbols.get(session, set()) & selected_symbols
                )
                if previous_symbols is not None:
                    for symbol in previous_symbols - current_symbols:
                        event_dates.setdefault(symbol, session)
                        event_reasons.setdefault(symbol, "halt or delisting")
                        missing_sessions.setdefault(symbol, session)
                for symbol in current_symbols - current_bar_symbols:
                    event_dates.setdefault(symbol, session)
                    event_reasons.setdefault(symbol, "halt or missing trade bar")
                for symbol in current_symbols:
                    listed_shares = krx_listed_shares.get(session, {}).get(symbol)
                    if listed_shares is None:
                        event_dates.setdefault(symbol, session)
                        event_reasons.setdefault(symbol, "missing listed share count")
                        continue
                    prior = previous_details.get(symbol)
                    if prior is not None and prior != listed_shares:
                        event_dates.setdefault(symbol, session)
                        event_reasons.setdefault(symbol, "listed share count changed")
                    previous_details[symbol] = listed_shares
                previous_symbols = current_symbols
            for symbol, event_date in missing_sessions.items():
                if any(
                    symbol in (krx_symbols.get(session, set()) & selected_symbols)
                    for session in sessions
                    if session > event_date
                ):
                    event_reasons[symbol] = "halt or missing trade bar"
                else:
                    event_reasons[symbol] = "delisting"
        else:
            universe = raw_rows
        bars: list[ApproximateBarRow] = []
        excluded: list[str] = []
        if market == "KR":
            bars = [bar for bar in krx_bars if bar.symbol in selected_symbols]
        else:
            candidate_rows = raw_rows
            for symbol in symbols:
                candidate_row = next(
                    (
                        item
                        for item in candidate_rows
                        if item.symbol == symbol
                    ),
                    us_symbol_details.get(symbol),
                )
                if candidate_row is None:
                    raise CollectorError(
                        f"admitted symbol details unavailable: {symbol}"
                    )
                row = candidate_row
                try:
                    chart = parse_yahoo_chart(
                        await self.transport.yahoo(symbol, warmup_start, end),
                        symbol=symbol,
                        exchange=row.exchange,
                        currency="USD",
                        start=warmup_start,
                        end=end,
                    )
                except CollectorError:
                    excluded.append(symbol)
                    continue
                us_events.extend(chart.event_rows)
                for chart_bar in chart.bars:
                    lookup = self.calendar.lookup(row.exchange, chart_bar.session)
                    if lookup.session is None:
                        raise CollectorError(
                            f"calendar session unavailable: {chart_bar.session}"
                        )
                    bars.append(
                        chart_bar.model_copy(
                            update={"available_at": lookup.session.close_at}
                        )
                    )
            for event in us_events:
                if event.occurrence_at is None or event.observed_at is None:
                    continue
                effective_at = max(
                    event.occurrence_at.astimezone(UTC),
                    event.observed_at.astimezone(UTC),
                )
                cutoff, ambiguous = _event_cutoff_session(
                    self.calendar,
                    effective_at,
                    start=start,
                    end=end,
                )
                if ambiguous or cutoff is None:
                    continue
                event_prior = us_event_cutoffs.get(event.symbol)
                if event_prior is None or cutoff < event_prior:
                    us_event_cutoffs[event.symbol] = cutoff
            normalized_us_events, _ = canonicalize_approximate_events(tuple(us_events))
            us_events = list(normalized_us_events)
        if not bars:
            raise CollectorPartialError("no sampled symbol has a valid history")
        fx: tuple[ApproximateFXRow, ...] = ()
        limitations: list[str] = []
        if market == "US":
            limitations.extend(alpha_limitations)
        if market == "US":
            fred_start = warmup_start - timedelta(days=7)
            fx = parse_fred_observations(
                await self.transport.fred(fred_start, end),
                start=fred_start,
                end=end,
            )
            fx_by_session: list[ApproximateFXRow] = []
            for session in sessions:
                lookup = self.calendar.lookup("NMS", session)
                if lookup.session is None:
                    raise CollectorError(f"calendar session unavailable: {session}")
                usable = [
                    item
                    for item in fx
                    if item.session <= session
                    and item.available_at is not None
                    and item.available_at <= lookup.session.open_at
                ]
                if not usable:
                    if session >= start:
                        raise CollectorError(
                            f"FRED FX observation unavailable before {session} open"
                        )
                    continue
                observation = max(usable, key=lambda item: item.session)
                fx_by_session.append(
                    observation.model_copy(
                        update={
                            "session": session,
                            "observation_date": observation.session,
                        }
                    )
                )
            fx = tuple(fx_by_session)
            limitations.append(
                "Alpha Vantage annual membership checkpoints use causal selections: "
                "eligible incumbents are retained and vacancies use then-eligible "
                "seeded candidates. Failed checkpoints create unknown intervals."
            )
            limitations.append(
                "US session FX uses the latest prior FRED observation available "
                "before each session open; observation date and availability are "
                "preserved."
            )
        if excluded:
            limitations.append(
                "Yahoo symbols with missing OHLCV or unresolved corporate actions "
                "were excluded."
            )
        if event_dates:
            limitations.append(
                "KRX symbols are excluded from the first affected session onward "
                "when a halt, delisting, missing listed-share data, or share-count "
                "change is detected: "
                + "; ".join(
                    f"{symbol} ({event_reasons[symbol]})"
                    for symbol in sorted(event_dates)
                )
            )

        def before_event(row: ApproximateUniverseRow | ApproximateBarRow) -> bool:
            event_date = event_dates.get(row.symbol)
            if event_date is not None and row.session >= event_date:
                return False
            us_event_date = us_event_cutoffs.get(row.symbol)
            return us_event_date is None or row.session < us_event_date

        return CollectionOutput(
            dataset=ApproximateDataset(
                market=market,
                universe=tuple(
                    item
                    for item in universe
                    if item.symbol not in excluded and before_event(item)
                ),
                bars=tuple(
                    item
                    for item in bars
                    if item.symbol not in excluded and before_event(item)
                ),
                fx=fx,
                events=tuple(us_events),
                source=source,
                bar_source="krx" if market == "KR" else "yahoo",
                fx_source="fred",
                simulated=False,
                normalization_version=normalization_version,
            ),
            limitations=tuple(limitations),
            excluded_symbols=tuple(sorted(excluded)),
        )

    @staticmethod
    def _alpha_checkpoint_summary(
        checkpoint: date,
        result: AlphaListingParseResult,
        *,
        selected: int | None = None,
        cumulative_admitted: int | None = None,
    ) -> str:
        excluded = (
            ", ".join(f"{reason}={count}" for reason, count in result.excluded)
            or "none"
        )
        return (
            "Alpha Vantage listing checkpoint "
            f"{checkpoint}: input={result.input_rows}, accepted={result.accepted}, "
            f"excluded=({excluded})"
            + (
                f", current_selected={selected}, "
                f"cumulative_admitted={cumulative_admitted}"
                if selected is not None and cumulative_admitted is not None
                else ""
            )
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
        estimated = estimate_network_requests(
            market=market, start=start, end=end, sample_size=sample_size
        )
        # Generic entries cannot prove they are exact, hash-verified requests
        # for this run. A full estimate is conservative in resume mode but
        # prevents unrelated cache data from hiding a partial collection.
        if settings.request_budget < estimated:
            raise RequestBudgetExceeded(
                "collector request budget is below the estimated call count"
            )
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
        ApproximateDataset.model_validate_json(content)
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
        AtomicResponseCache(cache_dir).write_completed(
            market=market,
            start=start,
            end=end,
            sample_size=sample_size,
            output=output,
            content=content,
        )
        return output_result
    finally:
        if owns_client:
            await http_client.aclose()


__all__ = [
    "ALPHA_VANTAGE_URL",
    "AtomicResponseCache",
    "ApproximateProviderError",
    "CACHE_CONTRACT_VERSION",
    "COMPLETION_CONTRACT_VERSION",
    "CollectorAuthenticationError",
    "CollectorCoverageError",
    "CollectorError",
    "CollectorNullError",
    "CollectorNullResponseError",
    "CollectorParseError",
    "CollectorPartialError",
    "CollectorQuotaError",
    "CompletedCollection",
    "CollectorSettings",
    "FreeMarketDataCollector",
    "KRXDailyResponse",
    "KRX_KSQ_URL",
    "KRX_STK_URL",
    "MAX_KRX_ROWS_PER_DAY",
    "NetworkCollectorTransport",
    "NORMALIZATION_VERSION",
    "RequestBudgetExceeded",
    "parse_alpha_vantage_listing_status_detailed",
    "collect_market_data",
    "completed_collection_is_valid",
    "estimate_network_requests",
    "load_collector_settings",
    "parse_alpha_vantage_listing_status",
    "parse_fred_observations",
    "parse_krx_daily_response",
    "parse_krx_daily_trade_response",
    "parse_yahoo_chart",
]
