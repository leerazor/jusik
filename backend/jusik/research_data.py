import asyncio
import time
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError

from jusik.research_config import PAPER_BASE_URL, ResearchSettings
from jusik.research_models import (
    DailyBar,
    EngineSpecification,
    ResearchInputSnapshot,
    ResearchRunRequest,
    SymbolSnapshot,
)

DAILY_PATH = "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
DAILY_TR_ID = "FHKST03010100"
WARMUP_CALENDAR_DAYS = 180
MIN_WARMUP_BARS = EngineSpecification().warmup_bars


class DataInsufficientError(Exception):
    """Historical input cannot support a valid comparison."""


class HistoricalDataProvider(Protocol):
    async def collect(self, request: ResearchRunRequest) -> ResearchInputSnapshot: ...


class _Token(BaseModel):
    access_token: SecretStr
    expires_in: int = Field(gt=60)


class _DailyRow(BaseModel):
    model_config = ConfigDict(extra="ignore")

    stck_bsop_date: str = Field(pattern=r"^[0-9]{8}$")
    stck_oprc: Decimal = Field(gt=0, allow_inf_nan=False)
    stck_hgpr: Decimal = Field(gt=0, allow_inf_nan=False)
    stck_lwpr: Decimal = Field(gt=0, allow_inf_nan=False)
    stck_clpr: Decimal = Field(gt=0, allow_inf_nan=False)
    acml_vol: int = Field(ge=0)

    @property
    def trading_date(self) -> date:
        return datetime.strptime(self.stck_bsop_date, "%Y%m%d").date()


def extract_symbol_name(metadata: object, requested_symbol: str) -> str | None:
    if not isinstance(metadata, dict):
        return None
    reported_symbol = metadata.get("stck_shrn_iscd")
    if reported_symbol is not None and (
        not isinstance(reported_symbol, str)
        or reported_symbol.strip() != requested_symbol
    ):
        return None
    value = metadata.get("hts_kor_isnm")
    if not isinstance(value, str):
        return None
    name = value.strip()
    if not name or len(name) > 80 or not name.isprintable():
        return None
    return name


class KisPaperHistoricalData:
    def __init__(
        self,
        settings: ResearchSettings,
        client: httpx.AsyncClient,
        *,
        request_interval_seconds: float = 1.0,
        on_symbol_metadata: Callable[[str, str], object] | None = None,
    ) -> None:
        self.settings = settings
        self.client = client
        self._request_interval_seconds = request_interval_seconds
        self._on_symbol_metadata = on_symbol_metadata
        self._last_request = 0.0
        self._token: SecretStr | None = None
        self._token_expires_at = 0.0
        self._lock = asyncio.Lock()

    async def _authenticate(self) -> str:
        if self._token is not None and time.monotonic() < self._token_expires_at:
            return self._token.get_secret_value()
        response = await self.client.post(
            "/oauth2/tokenP",
            json={
                "grant_type": "client_credentials",
                "appkey": self.settings.app_key.get_secret_value(),
                "appsecret": self.settings.app_secret.get_secret_value(),
            },
        )
        if response.status_code != 200:
            raise DataInsufficientError("KIS 모의투자 인증에 실패했습니다.")
        try:
            token = _Token.model_validate(response.json())
        except (ValidationError, ValueError):
            raise DataInsufficientError(
                "KIS 모의투자 인증 응답을 검증할 수 없습니다."
            ) from None
        self._token = token.access_token
        self._token_expires_at = time.monotonic() + token.expires_in - 60
        self._last_request = time.monotonic()
        return token.access_token.get_secret_value()

    async def _request_page(
        self,
        token: str,
        symbol: str,
        start: date,
        end: date,
        *,
        adjusted: bool,
    ) -> tuple[list[_DailyRow], str | None]:
        await asyncio.sleep(
            max(
                0,
                self._request_interval_seconds
                - (time.monotonic() - self._last_request),
            )
        )
        self._last_request = time.monotonic()
        response = await self.client.get(
            DAILY_PATH,
            params={
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": symbol,
                "FID_INPUT_DATE_1": start.strftime("%Y%m%d"),
                "FID_INPUT_DATE_2": end.strftime("%Y%m%d"),
                "FID_PERIOD_DIV_CODE": "D",
                "FID_ORG_ADJ_PRC": "0" if adjusted else "1",
            },
            headers={
                "authorization": f"Bearer {token}",
                "appkey": self.settings.app_key.get_secret_value(),
                "appsecret": self.settings.app_secret.get_secret_value(),
                "tr_id": DAILY_TR_ID,
                "custtype": "P",
            },
        )
        if response.status_code != 200:
            raise DataInsufficientError("KIS 모의투자 일봉 조회에 실패했습니다.")
        try:
            payload = response.json()
            if not isinstance(payload, dict) or payload.get("rt_cd") != "0":
                raise ValueError
            output = payload.get("output2")
            if not isinstance(output, list):
                raise ValueError
            metadata = payload.get("output1")
            market = None
            if isinstance(metadata, dict):
                name = extract_symbol_name(metadata, symbol)
                if name is not None and self._on_symbol_metadata is not None:
                    try:
                        self._on_symbol_metadata(symbol, name)
                    except Exception:
                        # Display metadata must never fail validated price collection.
                        pass
                value = metadata.get("rprs_mrkt_kor_name")
                if isinstance(value, str):
                    market = value.strip()
            return [_DailyRow.model_validate(row) for row in output], market
        except (ValidationError, ValueError, TypeError):
            raise DataInsufficientError(
                "KIS 모의투자 일봉 응답을 검증할 수 없습니다."
            ) from None

    async def _series(
        self,
        token: str,
        symbol: str,
        start: date,
        end: date,
        *,
        adjusted: bool,
    ) -> tuple[dict[date, _DailyRow], str | None]:
        rows: dict[date, _DailyRow] = {}
        reported_market: str | None = None
        page_end = end
        seen_ends: set[date] = set()
        for _ in range(20):
            page, market = await self._request_page(
                token, symbol, start, page_end, adjusted=adjusted
            )
            if market:
                if reported_market is not None and market != reported_market:
                    raise DataInsufficientError(
                        f"{symbol}의 시장 소속 정보가 서로 다릅니다."
                    )
                reported_market = market
            if not page:
                break
            earliest = min(row.trading_date for row in page)
            for row in page:
                if not start <= row.trading_date <= end:
                    continue
                previous = rows.get(row.trading_date)
                if previous is not None and previous != row:
                    raise DataInsufficientError(
                        f"{symbol}의 같은 날짜 일봉이 서로 다릅니다."
                    )
                rows[row.trading_date] = row
            if earliest <= start:
                break
            next_end = earliest - timedelta(days=1)
            if next_end >= page_end or next_end in seen_ends:
                raise DataInsufficientError(
                    f"{symbol}의 일봉 연속 조회가 진행되지 않았습니다."
                )
            seen_ends.add(next_end)
            page_end = next_end
        else:
            raise DataInsufficientError(
                f"{symbol}의 일봉 연속 조회 한도를 초과했습니다."
            )
        return rows, reported_market

    async def _symbol(
        self, token: str, symbol: str, start: date, end: date
    ) -> SymbolSnapshot:
        raw, raw_market = await self._series(token, symbol, start, end, adjusted=False)
        adjusted, adjusted_market = await self._series(
            token, symbol, start, end, adjusted=True
        )
        if not raw or raw.keys() != adjusted.keys():
            raise DataInsufficientError(
                f"{symbol}의 원주가와 수정주가 날짜 범위가 다릅니다."
            )
        bars: list[DailyBar] = []
        ratios: list[Decimal] = []
        try:
            for trading_date in sorted(raw):
                source = raw[trading_date]
                revised = adjusted[trading_date]
                bars.append(
                    DailyBar(
                        date=trading_date,
                        open=source.stck_oprc,
                        high=source.stck_hgpr,
                        low=source.stck_lwpr,
                        close=source.stck_clpr,
                        volume=source.acml_vol,
                        adjusted_open=revised.stck_oprc,
                        adjusted_high=revised.stck_hgpr,
                        adjusted_low=revised.stck_lwpr,
                        adjusted_close=revised.stck_clpr,
                    )
                )
                ratios.append(revised.stck_clpr / source.stck_clpr)
        except ValidationError:
            raise DataInsufficientError(
                f"{symbol}의 KIS 모의투자 일봉 응답을 검증할 수 없습니다."
            ) from None
        if max(ratios) - min(ratios) > Decimal("0.0001"):
            raise DataInsufficientError(
                f"{symbol}의 입력 기간에 기업행동으로 추정되는 "
                "수정 비율 변화가 있습니다."
            )
        if raw_market and adjusted_market and raw_market != adjusted_market:
            raise DataInsufficientError(
                f"{symbol}의 원주가와 수정주가 시장 소속 정보가 다릅니다."
            )
        market_name = raw_market or adjusted_market or ""
        normalized_market = market_name.upper()
        if symbol in {"005930", "000660"}:
            market = "KOSPI"
        elif "코스닥" in normalized_market or "KOSDAQ" in normalized_market:
            market = "KOSDAQ"
        elif "코스피" in normalized_market or "KOSPI" in normalized_market:
            market = "KOSPI"
        else:
            market = "UNKNOWN"
        return SymbolSnapshot(
            symbol=symbol,
            market=market,
            bars=bars,
            source_url=f"{PAPER_BASE_URL}{DAILY_PATH}",
        )

    async def collect(self, request: ResearchRunRequest) -> ResearchInputSnapshot:
        async with self._lock:
            token = await self._authenticate()
            input_start = request.start_date - timedelta(days=WARMUP_CALENDAR_DAYS)
            symbols = [
                await self._symbol(token, symbol, input_start, request.end_date)
                for symbol in request.symbols
            ]
        for snapshot in symbols:
            warmup = sum(bar.date < request.start_date for bar in snapshot.bars)
            comparison = sum(
                request.start_date <= bar.date <= request.end_date
                for bar in snapshot.bars
            )
            if warmup < MIN_WARMUP_BARS:
                raise DataInsufficientError(
                    f"{snapshot.symbol}의 준비 일봉은 {warmup}개입니다. "
                    "60개가 필요합니다."
                )
            if comparison == 0:
                raise DataInsufficientError(
                    f"{snapshot.symbol}의 비교 기간 일봉이 없습니다."
                )
        return ResearchInputSnapshot(
            captured_at=datetime.now(UTC),
            requested_start=request.start_date,
            requested_end=request.end_date,
            symbols=symbols,
            events=request.events,
        )
