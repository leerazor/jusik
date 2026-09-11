from __future__ import annotations

import asyncio
import csv
import io
import json
import math
import xml.etree.ElementTree as ET
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from typing import Literal
from urllib.parse import quote
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx

from jusik.research_external_models import ExternalObservation, ExternalSeries
from jusik.research_external_store import ExternalStore

TREASURY_URL = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
    "pages/xml"
)
VIX_URL = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"
YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
GPR_URL = "https://www.matteoiacoviello.com/gpr_files/data_gpr_daily_recent.xls"
EFFR_URL = "https://markets.newyorkfed.org/api/rates/unsecured/effr/search.json"

YAHOO_SERIES: tuple[tuple[ExternalSeries, str], ...] = (
    ("usdkrw", "KRW=X"),
    ("uso", "USO"),
    ("gld", "GLD"),
    ("hyg", "HYG"),
    ("spy", "SPY"),
    ("smh", "SMH"),
)
SOURCE_USAGE: dict[str, Literal["feature", "diagnostic_only", "archive_only"]] = {
    "treasury": "feature",
    "vix": "feature",
    "yahoo_usdkrw": "feature",
    "yahoo_uso": "feature",
    "yahoo_gld": "feature",
    "yahoo_hyg": "feature",
    "yahoo_spy": "diagnostic_only",
    "yahoo_smh": "diagnostic_only",
    "gpr": "archive_only",
    "effr": "archive_only",
}


class ExternalCollectionError(RuntimeError):
    pass


class ExternalCollectionStopped(Exception):
    pass


FetchBytes = Callable[[str, Mapping[str, str | int]], Awaitable[tuple[bytes, str]]]


def _decimal(value: object, field: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ExternalCollectionError(f"{field} 값이 숫자가 아닙니다.")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ExternalCollectionError(f"{field} 값이 숫자가 아닙니다.") from None
    if not result.is_finite():
        raise ExternalCollectionError(f"{field} 값이 유한하지 않습니다.")
    return result


def _next_utc_day(day: date, *, extra_days: int = 1) -> datetime:
    return datetime.combine(day + timedelta(days=extra_days), time(), UTC)


def parse_treasury_xml(body: bytes, *, revision: str) -> list[ExternalObservation]:
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        raise ExternalCollectionError(
            "Treasury XML 형식이 올바르지 않습니다."
        ) from None
    result: list[ExternalObservation] = []
    for entry in root.iter():
        if entry.tag.rsplit("}", 1)[-1] != "properties":
            continue
        fields = {child.tag.rsplit("}", 1)[-1]: child.text for child in entry}
        raw_day = fields.get("NEW_DATE")
        if raw_day is None:
            continue
        try:
            observed_on = datetime.fromisoformat(raw_day.replace("Z", "+00:00")).date()
        except ValueError:
            raise ExternalCollectionError(
                "Treasury 날짜 형식이 올바르지 않습니다."
            ) from None
        for series, key in (("treasury_2y", "BC_2YEAR"), ("treasury_10y", "BC_10YEAR")):
            raw_value = fields.get(key)
            if raw_value in (None, ""):
                continue
            result.append(
                ExternalObservation(
                    series=series,
                    observed_on=observed_on,
                    value=_decimal(raw_value, key),
                    available_at=_next_utc_day(observed_on),
                    revision=revision,
                )
            )
    if not result:
        raise ExternalCollectionError("Treasury 수익률 관측값이 없습니다.")
    return result


def parse_vix_csv(body: bytes, *, revision: str) -> list[ExternalObservation]:
    try:
        text = body.decode("utf-8-sig")
        rows = list(csv.DictReader(io.StringIO(text)))
    except UnicodeDecodeError:
        raise ExternalCollectionError("VIX CSV 인코딩이 올바르지 않습니다.") from None
    result: list[ExternalObservation] = []
    for row in rows:
        raw_day = row.get("DATE") or row.get("Date")
        raw_close = row.get("CLOSE") or row.get("Close")
        if not raw_day or raw_close in (None, ""):
            continue
        try:
            observed_on = datetime.strptime(raw_day.strip(), "%m/%d/%Y").date()
        except ValueError:
            try:
                observed_on = date.fromisoformat(raw_day.strip())
            except ValueError:
                raise ExternalCollectionError(
                    "VIX 날짜 형식이 올바르지 않습니다."
                ) from None
        result.append(
            ExternalObservation(
                series="vix",
                observed_on=observed_on,
                value=_decimal(raw_close, "VIX close"),
                available_at=_next_utc_day(observed_on),
                revision=revision,
            )
        )
    if not result:
        raise ExternalCollectionError("VIX 관측값이 없습니다.")
    return result


def parse_yahoo_chart(
    body: bytes,
    *,
    series: ExternalSeries,
    expected_symbol: str,
    revision: str,
) -> list[ExternalObservation]:
    try:
        payload = json.loads(body)
        chart = payload["chart"]
        if chart.get("error") is not None:
            raise ExternalCollectionError("Yahoo chart가 오류를 반환했습니다.")
        results = chart["result"]
        if not isinstance(results, list) or len(results) != 1:
            raise ExternalCollectionError("Yahoo chart 결과 개수가 올바르지 않습니다.")
        item = results[0]
        metadata = item["meta"]
        timestamps = item["timestamp"]
        quote_rows = item["indicators"]["quote"]
        if metadata.get("symbol") != expected_symbol:
            raise ExternalCollectionError("Yahoo symbol metadata가 요청과 다릅니다.")
        timezone_name = metadata["exchangeTimezoneName"]
        timezone = ZoneInfo(timezone_name)
        if (
            not isinstance(timestamps, list)
            or not isinstance(quote_rows, list)
            or len(quote_rows) != 1
        ):
            raise ExternalCollectionError("Yahoo chart 배열 형식이 올바르지 않습니다.")
        closes = quote_rows[0]["close"]
        if not isinstance(closes, list) or len(closes) != len(timestamps):
            raise ExternalCollectionError("Yahoo timestamp와 close 길이가 다릅니다.")
    except ExternalCollectionError:
        raise
    except (
        KeyError,
        TypeError,
        ValueError,
        ZoneInfoNotFoundError,
        json.JSONDecodeError,
    ):
        raise ExternalCollectionError("Yahoo chart 형식이 올바르지 않습니다.") from None
    result: list[ExternalObservation] = []
    seen: set[date] = set()
    for raw_timestamp, raw_close in zip(timestamps, closes, strict=True):
        if raw_close is None:
            continue
        if (
            isinstance(raw_timestamp, bool)
            or not isinstance(raw_timestamp, (int, float))
            or not math.isfinite(raw_timestamp)
        ):
            raise ExternalCollectionError("Yahoo timestamp가 유효하지 않습니다.")
        try:
            observed_on = (
                datetime.fromtimestamp(raw_timestamp, UTC).astimezone(timezone).date()
            )
        except (OverflowError, OSError, ValueError):
            raise ExternalCollectionError(
                "Yahoo timestamp 범위가 유효하지 않습니다."
            ) from None
        if observed_on in seen:
            raise ExternalCollectionError("Yahoo 일별 날짜가 중복되었습니다.")
        seen.add(observed_on)
        close = _decimal(raw_close, "Yahoo close")
        if close <= 0:
            raise ExternalCollectionError("Yahoo close가 양수가 아닙니다.")
        result.append(
            ExternalObservation(
                series=series,
                observed_on=observed_on,
                value=close,
                # Daily chart timestamps are session markers, not publication times.
                available_at=_next_utc_day(observed_on, extra_days=2),
                revision=revision,
            )
        )
    if not result:
        raise ExternalCollectionError("Yahoo close 관측값이 없습니다.")
    return result


def validate_gpr_archive(body: bytes) -> list[ExternalObservation]:
    if not body.startswith(b"\xd0\xcf\x11\xe0"):
        raise ExternalCollectionError("GPR XLS 원문 형식이 올바르지 않습니다.")
    return []


def validate_effr_archive(
    body: bytes,
    *,
    required_start: date | None = None,
    required_end: date | None = None,
) -> list[ExternalObservation]:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise ExternalCollectionError("EFFR JSON 형식이 올바르지 않습니다.") from None
    if not isinstance(payload, dict) or not isinstance(payload.get("refRates"), list):
        raise ExternalCollectionError("EFFR JSON 형식이 올바르지 않습니다.")
    rows = payload["refRates"]
    dates: list[date] = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("effectiveDate"), str):
            raise ExternalCollectionError("EFFR JSON 관측 형식이 올바르지 않습니다.")
        try:
            dates.append(date.fromisoformat(row["effectiveDate"][:10]))
        except ValueError:
            raise ExternalCollectionError(
                "EFFR JSON 날짜 형식이 올바르지 않습니다."
            ) from None
    if (
        required_start is not None
        and required_end is not None
        and (
            not dates
            or (min(dates) - required_start).days > 7
            or (required_end - max(dates)).days > 7
        )
    ):
        raise ExternalCollectionError("EFFR archive 요청 범위를 확인할 수 없습니다.")
    return []


def _within_range(
    observations: list[ExternalObservation], start: date, end: date
) -> list[ExternalObservation]:
    selected = [item for item in observations if start <= item.observed_on <= end]
    if not selected:
        raise ExternalCollectionError("요청 기간 외부 관측값이 없습니다.")
    return selected


async def _http_fetch(
    client: httpx.AsyncClient,
    url: str,
    parameters: Mapping[str, str | int],
) -> tuple[bytes, str]:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = await client.get(url, params=parameters)
            response.raise_for_status()
            return response.content, response.headers.get(
                "content-type", "application/octet-stream"
            )
        except httpx.HTTPError as error:
            last_error = error
            if attempt < 2:
                await asyncio.sleep(0.2 * (attempt + 1))
    assert last_error is not None
    raise ExternalCollectionError("외부 자료 HTTP 수집에 실패했습니다.") from None


async def collect_external_sources(
    store: ExternalStore,
    *,
    start: date,
    end: date,
    captured_at: datetime,
    should_stop: Callable[[], bool] = lambda: False,
    fetch_bytes: FetchBytes | None = None,
) -> dict[str, str]:
    if captured_at.tzinfo is None:
        raise ValueError("captured_at must include a timezone.")
    client: httpx.AsyncClient | None = None
    fetch: FetchBytes
    if fetch_bytes is None:
        client = httpx.AsyncClient(
            timeout=20, headers={"User-Agent": "jusik-offline-research/1.0"}
        )

        async def fetch(url: str, params: Mapping[str, str | int]) -> tuple[bytes, str]:
            assert client is not None
            return await _http_fetch(client, url, params)

    else:
        fetch = fetch_bytes
    outcomes: dict[str, str] = {}

    async def save(
        source: str,
        url: str,
        params: Mapping[str, str | int],
        parser: Callable[[bytes], list[ExternalObservation]],
        archive_coverage: tuple[date, date] | None = None,
    ) -> None:
        if should_stop():
            raise ExternalCollectionStopped
        try:
            body, content_type = await fetch(url, params)
            observations = parser(body)
            store.save_success(
                source,
                body=body,
                content_type=content_type,
                observations=observations,
                captured_at=captured_at,
                archive_coverage=archive_coverage,
            )
            outcomes[source] = "success"
        except ExternalCollectionStopped:
            raise
        except (ExternalCollectionError, ValueError, OSError) as error:
            store.record_failure(source, str(error), attempted_at=captured_at)
            outcomes[source] = "error"

    revision = "bootstrap-current"
    try:
        try:
            treasury_bodies: list[bytes] = []
            treasury_observations: list[ExternalObservation] = []
            content_type = "application/xml"
            for year in range(start.year, end.year + 1):
                if should_stop():
                    raise ExternalCollectionStopped
                body, content_type = await fetch(
                    TREASURY_URL,
                    {
                        "data": "daily_treasury_yield_curve",
                        "field_tdr_date_value": year,
                    },
                )
                treasury_bodies.append(body)
                treasury_observations.extend(
                    parse_treasury_xml(body, revision=f"{revision}-{year}")
                )
            treasury_observations = [
                item
                for item in treasury_observations
                if start <= item.observed_on <= end
            ]
            if not treasury_observations:
                raise ExternalCollectionError("Treasury 요청 기간 관측값이 없습니다.")
            store.save_success(
                "treasury",
                body=b"\n<!-- year boundary -->\n".join(treasury_bodies),
                content_type=content_type,
                observations=treasury_observations,
                captured_at=captured_at,
            )
            outcomes["treasury"] = "success"
        except ExternalCollectionStopped:
            raise
        except (ExternalCollectionError, ValueError, OSError) as error:
            store.record_failure("treasury", str(error), attempted_at=captured_at)
            outcomes["treasury"] = "error"

        def vix_parser(body: bytes) -> list[ExternalObservation]:
            return _within_range(parse_vix_csv(body, revision=revision), start, end)

        await save("vix", VIX_URL, {}, vix_parser)
        period1 = int(datetime.combine(start, time(), UTC).timestamp())
        period2 = int(
            datetime.combine(end + timedelta(days=2), time(), UTC).timestamp()
        )
        for series, symbol in YAHOO_SERIES:

            def yahoo_parser(
                body: bytes,
                *,
                selected_series: ExternalSeries = series,
                selected_symbol: str = symbol,
            ) -> list[ExternalObservation]:
                return _within_range(
                    parse_yahoo_chart(
                        body,
                        series=selected_series,
                        expected_symbol=selected_symbol,
                        revision=revision,
                    ),
                    start,
                    end,
                )

            await save(
                f"yahoo_{series}",
                YAHOO_URL.format(symbol=quote(symbol, safe="")),
                {
                    "period1": period1,
                    "period2": period2,
                    "interval": "1d",
                    "events": "splits",
                    "includeAdjustedClose": "false",
                },
                yahoo_parser,
            )
        await save(
            "gpr",
            GPR_URL,
            {},
            validate_gpr_archive,
        )

        def effr_parser(body: bytes) -> list[ExternalObservation]:
            return validate_effr_archive(body, required_start=start, required_end=end)

        await save(
            "effr",
            EFFR_URL,
            {
                "startDate": start.isoformat(),
                "endDate": end.isoformat(),
                "type": "rate",
            },
            effr_parser,
            (start, end),
        )
    finally:
        if client is not None:
            await client.aclose()
    return outcomes
