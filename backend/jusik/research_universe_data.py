from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import cast
from urllib.parse import quote
from zoneinfo import ZoneInfo

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from jusik.research_data import DataCollectionError, DataInsufficientError
from jusik.research_models import DailyBar
from jusik.research_universe_models import (
    CorporateAction,
    DataProvenance,
    OfflineInstrumentSnapshot,
    OfflineResearchRequest,
    OfflineResearchSnapshot,
    PriceAdjustmentFactor,
    ResearchInstrument,
)

YAHOO_BASE_URL = "https://query1.finance.yahoo.com"
YAHOO_CHART_PATH = "/v8/finance/chart/{symbol}"
FETCH_WARMUP_DAYS = 180
ROLLING_DAYS = 1095

REGISTRY: tuple[ResearchInstrument, ...] = (
    ResearchInstrument(
        symbol="005930",
        yahoo_symbol="005930.KS",
        name="삼성전자",
        currency="KRW",
        exchange="KSC",
        timezone="Asia/Seoul",
    ),
    ResearchInstrument(
        symbol="000660",
        yahoo_symbol="000660.KS",
        name="SK하이닉스",
        currency="KRW",
        exchange="KSC",
        timezone="Asia/Seoul",
    ),
    ResearchInstrument(
        symbol="487230",
        yahoo_symbol="487230.KS",
        name="KODEX 미국AI전력핵심인프라",
        currency="KRW",
        exchange="KSC",
        timezone="Asia/Seoul",
        listed_on=date(2024, 7, 9),
    ),
    ResearchInstrument(
        symbol="487240",
        yahoo_symbol="487240.KS",
        name="KODEX AI전력핵심설비",
        currency="KRW",
        exchange="KSC",
        timezone="Asia/Seoul",
        listed_on=date(2024, 7, 9),
    ),
    ResearchInstrument(
        symbol="0173Y0",
        yahoo_symbol="0173Y0.KS",
        name="KODEX 미국AI광통신네트워크",
        currency="KRW",
        exchange="KSC",
        timezone="Asia/Seoul",
        listed_on=date(2026, 3, 31),
    ),
    ResearchInstrument(
        symbol="0190C0",
        yahoo_symbol="0190C0.KS",
        name="RISE 현대차고정피지컬AI",
        currency="KRW",
        exchange="KSC",
        timezone="Asia/Seoul",
        listed_on=date(2026, 5, 12),
    ),
    ResearchInstrument(
        symbol="SOXL",
        yahoo_symbol="SOXL",
        name="Direxion Daily Semiconductor Bull 3X Shares",
        currency="USD",
        exchange="PCX",
        timezone="America/New_York",
    ),
    ResearchInstrument(
        symbol="NVDA",
        yahoo_symbol="NVDA",
        name="NVIDIA",
        currency="USD",
        exchange="NMS",
        timezone="America/New_York",
    ),
    ResearchInstrument(
        symbol="GOOGL",
        yahoo_symbol="GOOGL",
        name="Alphabet Class A",
        currency="USD",
        exchange="NMS",
        timezone="America/New_York",
    ),
    ResearchInstrument(
        symbol="COHR",
        yahoo_symbol="COHR",
        name="Coherent",
        currency="USD",
        exchange="NYQ",
        timezone="America/New_York",
    ),
    ResearchInstrument(
        symbol="TQQQ",
        yahoo_symbol="TQQQ",
        name="ProShares UltraPro QQQ",
        currency="USD",
        exchange="NGM",
        timezone="America/New_York",
    ),
    ResearchInstrument(
        symbol="MSFT",
        yahoo_symbol="MSFT",
        name="Microsoft",
        currency="USD",
        exchange="NMS",
        timezone="America/New_York",
    ),
    ResearchInstrument(
        symbol="ARM",
        yahoo_symbol="ARM",
        name="Arm Holdings",
        currency="USD",
        exchange="NMS",
        timezone="America/New_York",
        listed_on=date(2023, 9, 14),
    ),
    ResearchInstrument(
        symbol="AMD",
        yahoo_symbol="AMD",
        name="Advanced Micro Devices",
        currency="USD",
        exchange="NMS",
        timezone="America/New_York",
    ),
    ResearchInstrument(
        symbol="GEV",
        yahoo_symbol="GEV",
        name="GE Vernova",
        currency="USD",
        exchange="NYQ",
        timezone="America/New_York",
        listed_on=date(2024, 4, 2),
    ),
    ResearchInstrument(
        symbol="VRT",
        yahoo_symbol="VRT",
        name="Vertiv Holdings",
        currency="USD",
        exchange="NYQ",
        timezone="America/New_York",
    ),
)


class KisRawRow(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    stck_bsop_date: str = Field(pattern=r"^[0-9]{8}$")
    stck_oprc: Decimal = Field(gt=0, allow_inf_nan=False)
    stck_hgpr: Decimal = Field(gt=0, allow_inf_nan=False)
    stck_lwpr: Decimal = Field(gt=0, allow_inf_nan=False)
    stck_clpr: Decimal = Field(gt=0, allow_inf_nan=False)
    acml_vol: int = Field(ge=0)

    @property
    def trading_date(self) -> date:
        return datetime.strptime(self.stck_bsop_date, "%Y%m%d").date()


@dataclass(frozen=True)
class CollectedUniverseSnapshot:
    request: OfflineResearchRequest
    snapshot: OfflineResearchSnapshot
    raw_payload: dict[str, object]
    content_hash: str


def rolling_period(local_today: date) -> tuple[date, date]:
    end = local_today - timedelta(days=1)
    return end - timedelta(days=ROLLING_DAYS), end


def yahoo_request_parameters(
    instrument: ResearchInstrument, requested_start: date, requested_end: date
) -> tuple[str, dict[str, str | int]]:
    fetch_start = requested_start - timedelta(days=FETCH_WARMUP_DAYS)
    timezone = ZoneInfo(instrument.timezone)
    period1 = int(
        datetime.combine(fetch_start, datetime.min.time(), timezone).timestamp()
    )
    period2 = int(
        datetime.combine(
            requested_end + timedelta(days=2), datetime.min.time(), timezone
        ).timestamp()
    )
    path = YAHOO_CHART_PATH.format(symbol=quote(instrument.yahoo_symbol, safe=""))
    return path, {
        "period1": period1,
        "period2": period2,
        "interval": "1d",
        "events": "div,splits",
        "includeAdjustedClose": "true",
    }


async def fetch_yahoo_chart(
    client: httpx.AsyncClient,
    instrument: ResearchInstrument,
    requested_start: date,
    requested_end: date,
) -> dict[str, object]:
    path, parameters = yahoo_request_parameters(
        instrument, requested_start, requested_end
    )
    try:
        response = await client.get(path, params=parameters)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError):
        raise DataCollectionError(
            f"{instrument.symbol} Yahoo chart 수집에 실패했습니다."
        ) from None
    if not isinstance(payload, dict):
        raise DataCollectionError(
            f"{instrument.symbol} Yahoo chart 응답 형식이 올바르지 않습니다."
        )
    return payload


def _finite_decimal(value: object, field: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (Decimal, int, float, str)):
        raise DataInsufficientError(f"Yahoo {field} 값이 없거나 숫자가 아닙니다.")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise DataInsufficientError(
            f"Yahoo {field} 값이 없거나 숫자가 아닙니다."
        ) from None
    if not result.is_finite() or result <= 0:
        raise DataInsufficientError(f"Yahoo {field} 값이 유효하지 않습니다.")
    return result


def _local_date(timestamp: object, timezone: ZoneInfo, field: str) -> date:
    if (
        isinstance(timestamp, bool)
        or not isinstance(timestamp, (int, float))
        or not math.isfinite(float(timestamp))
    ):
        raise DataInsufficientError(f"Yahoo {field}가 올바르지 않습니다.")
    try:
        return datetime.fromtimestamp(timestamp, timezone).date()
    except (OverflowError, OSError, ValueError):
        raise DataInsufficientError(f"Yahoo {field}가 올바르지 않습니다.") from None


def _chart_result(payload: Mapping[str, object]) -> Mapping[str, object]:
    chart = payload.get("chart")
    if not isinstance(chart, Mapping) or chart.get("error") is not None:
        raise DataInsufficientError("Yahoo chart 응답에 오류가 있습니다.")
    result = chart.get("result")
    if (
        not isinstance(result, list)
        or len(result) != 1
        or not isinstance(result[0], Mapping)
    ):
        raise DataInsufficientError("Yahoo chart 결과 형식이 올바르지 않습니다.")
    return result[0]


def _corporate_actions(
    result: Mapping[str, object], timezone: ZoneInfo
) -> list[CorporateAction]:
    events = result.get("events", {})
    if not isinstance(events, Mapping):
        raise DataInsufficientError("Yahoo corporate action 형식이 올바르지 않습니다.")
    splits = events.get("splits", {})
    if not isinstance(splits, Mapping):
        raise DataInsufficientError("Yahoo split 형식이 올바르지 않습니다.")
    actions: list[CorporateAction] = []
    for event in splits.values():
        if not isinstance(event, Mapping):
            raise DataInsufficientError("Yahoo split 항목이 올바르지 않습니다.")
        try:
            actions.append(
                CorporateAction(
                    date=_local_date(event.get("date"), timezone, "split 날짜"),
                    numerator=_finite_decimal(
                        event.get("numerator"), "split numerator"
                    ),
                    denominator=_finite_decimal(
                        event.get("denominator"), "split denominator"
                    ),
                )
            )
        except ValidationError:
            raise DataInsufficientError(
                "Yahoo split 비율이 올바르지 않습니다."
            ) from None
    return sorted(actions, key=lambda action: action.date)


def _validate_metadata(
    result: Mapping[str, object], instrument: ResearchInstrument
) -> ZoneInfo:
    meta = result.get("meta")
    if not isinstance(meta, Mapping):
        raise DataInsufficientError("Yahoo chart metadata가 없습니다.")
    expected = {
        "symbol": instrument.yahoo_symbol,
        "currency": instrument.currency,
        "exchangeName": instrument.exchange,
        "exchangeTimezoneName": instrument.timezone,
    }
    if any(meta.get(key) != value for key, value in expected.items()):
        raise DataInsufficientError(
            f"{instrument.symbol} Yahoo symbol/currency/exchange/timezone이 다릅니다."
        )
    return ZoneInfo(instrument.timezone)


def _yahoo_rows(
    result: Mapping[str, object], timezone: ZoneInfo
) -> list[tuple[date, object, object, object, object, object]]:
    timestamps = result.get("timestamp")
    indicators = result.get("indicators")
    if not isinstance(timestamps, list) or not isinstance(indicators, Mapping):
        raise DataInsufficientError("Yahoo chart 시계열 형식이 올바르지 않습니다.")
    quotes = indicators.get("quote")
    if (
        not isinstance(quotes, list)
        or len(quotes) != 1
        or not isinstance(quotes[0], Mapping)
    ):
        raise DataInsufficientError("Yahoo quote 시계열 형식이 올바르지 않습니다.")
    quote_row = quotes[0]
    columns = [
        quote_row.get(name) for name in ("open", "high", "low", "close", "volume")
    ]
    if any(
        not isinstance(column, list) or len(column) != len(timestamps)
        for column in columns
    ):
        raise DataInsufficientError("Yahoo quote 배열 길이가 서로 다릅니다.")
    open_column, high_column, low_column, close_column, volume_column = (
        cast(list[object], column) for column in columns
    )
    rows: list[tuple[date, object, object, object, object, object]] = []
    for index, timestamp in enumerate(timestamps):
        rows.append(
            (
                _local_date(timestamp, timezone, "timestamp"),
                open_column[index],
                high_column[index],
                low_column[index],
                close_column[index],
                volume_column[index],
            )
        )
    dates = [row[0] for row in rows]
    if len(dates) != len(set(dates)):
        raise DataInsufficientError("Yahoo chart의 현지 거래일이 중복되었습니다.")
    return rows


def _factor_for_date(day: date, actions: Sequence[CorporateAction]) -> Decimal:
    factor = Decimal(1)
    for action in actions:
        if action.date > day:
            factor *= action.factor
    return factor


def _make_bar(
    day: date,
    values: tuple[object, object, object, object, object],
    factor: Decimal,
    *,
    raw_primary: bool,
) -> DailyBar:
    open_value = _finite_decimal(values[0], "open")
    high = _finite_decimal(values[1], "high")
    low = _finite_decimal(values[2], "low")
    close = _finite_decimal(values[3], "close")
    volume_value = values[4]
    if isinstance(volume_value, bool) or not isinstance(volume_value, (int, float)):
        raise DataInsufficientError("Yahoo/KIS volume 값이 올바르지 않습니다.")
    if (
        not math.isfinite(float(volume_value))
        or int(volume_value) != volume_value
        or volume_value < 0
    ):
        raise DataInsufficientError("Yahoo/KIS volume 값이 올바르지 않습니다.")
    raw_multiplier = Decimal(1) if raw_primary else factor
    adjusted_divisor = factor if raw_primary else Decimal(1)
    try:
        return DailyBar(
            date=day,
            open=open_value * raw_multiplier,
            high=high * raw_multiplier,
            low=low * raw_multiplier,
            close=close * raw_multiplier,
            volume=int(volume_value),
            adjusted_open=open_value / adjusted_divisor,
            adjusted_high=high / adjusted_divisor,
            adjusted_low=low / adjusted_divisor,
            adjusted_close=close / adjusted_divisor,
        )
    except ValidationError:
        raise DataInsufficientError(
            f"{day.isoformat()} 일봉 OHLC를 검증할 수 없습니다."
        ) from None


def _kis_rows(
    rows: Sequence[Mapping[str, object]],
) -> list[tuple[date, object, object, object, object, object]]:
    parsed: list[KisRawRow] = []
    try:
        parsed = [KisRawRow.model_validate(row) for row in rows]
    except ValidationError:
        raise DataInsufficientError("KIS raw 일봉 응답을 검증할 수 없습니다.") from None
    dates = [row.trading_date for row in parsed]
    if len(dates) != len(set(dates)):
        raise DataInsufficientError("KIS raw 일봉 날짜가 중복되었습니다.")
    return [
        (
            row.trading_date,
            row.stck_oprc,
            row.stck_hgpr,
            row.stck_lwpr,
            row.stck_clpr,
            row.acml_vol,
        )
        for row in sorted(parsed, key=lambda value: value.trading_date)
    ]


def normalize_chart(
    instrument: ResearchInstrument,
    yahoo_payload: Mapping[str, object],
    *,
    captured_at: datetime,
    requested_start: date,
    requested_end: date,
    kis_raw_rows: Sequence[Mapping[str, object]] | None = None,
) -> CollectedUniverseSnapshot:
    if captured_at.tzinfo is None:
        raise ValueError("captured_at must include a timezone.")
    result = _chart_result(yahoo_payload)
    timezone = _validate_metadata(result, instrument)
    local_today = captured_at.astimezone(timezone).date()
    actions = _corporate_actions(result, timezone)
    yahoo_rows = _yahoo_rows(result, timezone)
    if instrument.currency == "KRW":
        if kis_raw_rows is None:
            raise DataInsufficientError(
                f"{instrument.symbol}은 검증된 KIS raw 일봉이 필요합니다."
            )
        rows = _kis_rows(kis_raw_rows)
        raw_primary = True
        provenance = DataProvenance(
            price_volume_source="KIS paper daily chart",
        )
        source_url = "https://openapivts.koreainvestment.com:29443"
    else:
        if kis_raw_rows is not None:
            raise ValueError("KIS raw rows are only valid for KRW instruments.")
        rows = yahoo_rows
        raw_primary = False
        provenance = DataProvenance(price_volume_source="Yahoo chart")
        source_url = YAHOO_BASE_URL + YAHOO_CHART_PATH.format(
            symbol=quote(instrument.yahoo_symbol, safe="")
        )
    eligible_rows = [
        row
        for row in rows
        if row[0] <= requested_end
        and row[0] < local_today
        and (instrument.listed_on is None or row[0] >= instrument.listed_on)
    ]
    bars: list[DailyBar] = []
    factors: list[PriceAdjustmentFactor] = []
    for row in eligible_rows:
        factor = _factor_for_date(row[0], actions)
        bars.append(_make_bar(row[0], row[1:], factor, raw_primary=raw_primary))
        factors.append(PriceAdjustmentFactor(date=row[0], raw_factor=factor))
    if not bars:
        raise DataInsufficientError(f"{instrument.symbol}의 완료 일봉이 없습니다.")
    bar_dates = {bar.date for bar in bars}
    missing_action_dates = [
        action.date
        for action in actions
        if bars[0].date <= action.date <= bars[-1].date and action.date not in bar_dates
    ]
    if missing_action_dates:
        raise DataInsufficientError(
            f"{instrument.symbol} 기업행동일의 일봉이 누락되었습니다."
        )
    relevant_actions = [action for action in actions if action.date in bar_dates]
    evaluation_start = max(requested_start, bars[min(60, len(bars) - 1)].date)
    initial_cash = (
        Decimal("100000000") if instrument.currency == "KRW" else Decimal("100000")
    )
    request = OfflineResearchRequest(
        instrument=instrument,
        start_date=evaluation_start,
        end_date=requested_end,
        initial_cash=initial_cash,
    )
    snapshot = OfflineResearchSnapshot(
        captured_at=captured_at.astimezone(UTC),
        requested_start=requested_start,
        requested_end=requested_end,
        evaluation_start=evaluation_start,
        instruments=[
            OfflineInstrumentSnapshot(
                instrument=instrument,
                bars=bars,
                provenance=provenance,
                source_url=source_url,
            )
        ],
        basis_actions=actions,
        corporate_actions=relevant_actions,
        adjustment_factors=factors,
    )
    raw_payload: dict[str, object] = {
        "yahoo": dict(yahoo_payload),
        "kis_raw": list(kis_raw_rows) if kis_raw_rows is not None else None,
    }
    content_hash = hashlib.sha256(
        json.dumps(
            {
                "request": request.model_dump(mode="json"),
                "snapshot": snapshot.model_dump(mode="json", exclude={"captured_at"}),
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    return CollectedUniverseSnapshot(request, snapshot, raw_payload, content_hash)
