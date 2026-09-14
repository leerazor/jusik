import asyncio
import calendar
import json
import math
import time
from collections.abc import Callable, Coroutine, Mapping
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol, cast
from zoneinfo import ZoneInfo

import httpx

from jusik.investor_analysis import analyze, evaluate_trend
from jusik.investor_models import (
    AnalysisResult,
    Candidate,
    DailyBar,
    DiscoveryResult,
    FundamentalFacts,
    Instrument,
    InstrumentDetail,
    InstrumentType,
    Market,
    QuoteFact,
    TrendFacts,
)
from jusik.kis import BrokerError, KisClient
from jusik.research_market_calendar import default_market_calendar

SOURCE_URL = "https://apiportal.koreainvestment.com/apiservice"
MAX_CANDIDATES = 20
US_EXCHANGES = ("NAS", "NYS", "AMS")


def _decimal(value: object) -> Decimal | None:
    if value in (None, "", "-", "N/A"):
        return None
    try:
        parsed = Decimal(str(value).replace(",", ""))
    except (InvalidOperation, ValueError):
        return None
    return parsed if parsed.is_finite() else None


def _text(value: object) -> str:
    return str(value or "").strip()


def _period_end(value: object) -> date | None:
    text = _text(value).replace(".", "").replace("-", "")
    if len(text) != 6 or not text.isdigit():
        return None
    year, month = int(text[:4]), int(text[4:])
    if month not in range(1, 13):
        return None
    return date(year, month, calendar.monthrange(year, month)[1])


class InvestorProvider(Protocol):
    async def discover(self, market: Market) -> DiscoveryResult: ...

    async def detail(self, instrument: Instrument) -> InstrumentDetail: ...


class KisInvestorProvider:
    """Bounded, read-only investor data access over the existing KIS client."""

    def __init__(self, kis: KisClient, *, cache_seconds: int = 60) -> None:
        self.kis = kis
        self.cache_seconds = cache_seconds
        self._cache: dict[tuple[str, str], tuple[object, float]] = {}
        self._inflight: dict[tuple[str, str], asyncio.Task[object]] = {}
        self._inflight_lock = asyncio.Lock()

    async def _cached(
        self, key: tuple[str, str], loader: Callable[[], Coroutine[Any, Any, object]]
    ) -> object:
        now = time.monotonic()
        cached = self._cache.get(key)
        if cached and now - cached[1] < self.cache_seconds:
            return cached[0]
        async with self._inflight_lock:
            task = self._inflight.get(key)
            if task is None:
                task = asyncio.create_task(loader())
                self._inflight[key] = task
        try:
            result = await task
            self._cache[key] = (result, time.monotonic())
            return result
        finally:
            async with self._inflight_lock:
                if self._inflight.get(key) is task:
                    del self._inflight[key]

    async def _request(
        self, path: str, tr_id: str, params: dict[str, str]
    ) -> dict[str, object]:
        accounts = self.kis.settings.registered_accounts
        if not accounts:
            raise BrokerError("투자자 데이터 조회 계정이 설정되지 않았습니다.")
        account = accounts[0]
        token = await self.kis._authenticate(account)
        response = await self.kis._get(account, token, path, tr_id, params)
        return self.kis._accepted_json(response)

    @staticmethod
    def _instrument(
        market: Market, exchange: str, symbol: str, output: Mapping[str, object]
    ) -> Instrument:
        name = _text(
            output.get("prdt_name")
            or output.get("hts_kor_isnm")
            or output.get("name")
            or symbol
        )
        etyp = _text(output.get("etyp_nm") or output.get("etf_yn"))
        instrument_type = "etf" if etyp and "ETF" in etyp.upper() else "unknown"
        return Instrument(
            market=market,
            exchange="KRX" if market == "KR" else exchange,
            symbol=symbol,
            currency="KRW" if market == "KR" else "USD",
            name=name,
            instrument_type=instrument_type,
        )

    async def discover(self, market: Market) -> DiscoveryResult:
        now = datetime.now(UTC)
        key = ("discover", market)

        async def load() -> DiscoveryResult:
            errors: list[str] = []
            rows: list[Mapping[str, object]] = []
            try:
                if market == "KR":
                    data = await self._request(
                        "/uapi/domestic-stock/v1/quotations/volume-rank",
                        "FHPST01710000",
                        {
                            "FID_COND_MRKT_DIV_CODE": "J",
                            "FID_COND_SCR_DIV_CODE": "20171",
                            "FID_INPUT_ISCD": "0000",
                            "FID_DIV_CLS_CODE": "0",
                            "FID_BLNG_CLS_CODE": "0",
                            "FID_TRGT_CLS_CODE": "111111111",
                            "FID_TRGT_EXLS_CLS_CODE": "0000000000",
                            "FID_INPUT_PRICE_1": "",
                            "FID_INPUT_PRICE_2": "",
                            "FID_VOL_CNT": "",
                            "FID_INPUT_DATE_1": "",
                        },
                    )
                    output = data.get("output")
                    rows = output if isinstance(output, list) else []
                    exchange = "KRX"
                else:
                    for exchange in US_EXCHANGES:
                        data = await self._request(
                            "/uapi/overseas-stock/v1/ranking/trade-vol",
                            "HHDFS76310010",
                            {
                                "EXCD": exchange,
                                "NDAY": "0",
                                "VOL_RANG": "0",
                                "KEYB": "",
                                "AUTH": "",
                                "PRC1": "",
                                "PRC2": "",
                            },
                        )
                        output = data.get("output2")
                        if isinstance(output, list):
                            rows.extend(
                                row for row in output if isinstance(row, Mapping)
                            )
                    exchange = "US"
            except (BrokerError, httpx.HTTPError, ValueError):
                errors.append("후보 순위 자료를 확인할 수 없습니다.")
                exchange = "KRX" if market == "KR" else "US"
            candidates: list[Candidate] = []
            seen: set[str] = set()
            for row in rows:
                symbol = _text(
                    row.get("mksc_shrn_iscd")
                    or row.get("stck_shrn_iscd")
                    or row.get("symb")
                    or row.get("rsym")
                )
                if market == "US" and symbol.startswith("D") and len(symbol) > 5:
                    symbol = symbol[5:]
                if not symbol or symbol in seen or len(candidates) >= MAX_CANDIDATES:
                    continue
                seen.add(symbol)
                item_exchange = _text(row.get("excd") or exchange)
                candidates.append(
                    Candidate(
                        instrument=self._instrument(market, item_exchange, symbol, row),
                        rank=len(candidates) + 1,
                        reason=(
                            "거래량 순위 후보입니다. 저평가나 품질을 증명하지 않습니다."
                        ),
                        source="KIS 거래량 순위",
                        observed_at=now,
                    )
                )
            return DiscoveryResult(
                market=market,
                candidates=candidates,
                coverage="KIS 첫 순위 페이지의 후보만 확인했습니다.",
                truncated=len(rows) > MAX_CANDIDATES,
                partial=bool(errors),
                errors=errors,
                fetched_at=now,
            )

        result = await self._cached(key, load)
        assert isinstance(result, DiscoveryResult)
        return result

    async def detail(self, instrument: Instrument) -> InstrumentDetail:
        key = (
            "detail",
            f"{instrument.market}:{instrument.exchange}:{instrument.symbol}",
        )

        async def load() -> InstrumentDetail:
            now = datetime.now(UTC)
            limitations: list[str] = [
                "조회 시각과 거래소의 실제 시세 시각은 다를 수 있습니다.",
                "현재 자료만 사용하며 과거 시점의 정보 가용성을 주장하지 않습니다.",
            ]
            try:
                resolved_instrument = instrument
                if instrument.market == "KR":
                    quote_data = await self._request(
                        "/uapi/domestic-stock/v1/quotations/inquire-price",
                        "FHKST01010100",
                        {
                            "FID_COND_MRKT_DIV_CODE": "J",
                            "FID_INPUT_ISCD": instrument.symbol,
                        },
                    )
                    output = quote_data.get("output")
                    if not isinstance(output, Mapping):
                        raise ValueError("quote identity unavailable")
                    if _text(output.get("stck_shrn_iscd")) != instrument.symbol:
                        raise ValueError("quote identity mismatch")
                    price = _decimal(output.get("stck_prpr"))
                    quote = QuoteFact(
                        price=price,
                        currency="KRW",
                        fetched_at=now,
                        source="KIS 국내 현재가",
                        source_url=SOURCE_URL,
                        unavailable_reason=None if price else "현재가가 없습니다.",
                    )
                    fundamentals = FundamentalFacts(
                        eps=_decimal(output.get("eps")),
                        per=_decimal(output.get("per")),
                        pbr=_decimal(output.get("pbr")),
                        source="KIS 국내 현재가",
                        source_url=SOURCE_URL,
                        fetched_at=now,
                    )
                    fundamentals = await self._kr_financials(
                        instrument.symbol, fundamentals
                    )
                else:
                    exchange = (
                        instrument.exchange
                        if instrument.exchange in US_EXCHANGES
                        else "NAS"
                    )
                    output = None
                    for exchange_code in (
                        exchange,
                        *[item for item in US_EXCHANGES if item != exchange],
                    ):
                        data = await self._request(
                            "/uapi/overseas-price/v1/quotations/price-detail",
                            "HHDFS76200200",
                            {
                                "AUTH": "",
                                "EXCD": exchange_code,
                                "SYMB": instrument.symbol,
                            },
                        )
                        candidate = data.get("output")
                        if (
                            isinstance(candidate, Mapping)
                            and _text(candidate.get("rsym")).upper()
                            == f"D{exchange_code}{instrument.symbol}".upper()
                            and _text(candidate.get("curr")).upper() == "USD"
                        ):
                            output = candidate
                            exchange = exchange_code
                            break
                    if output is None:
                        raise ValueError("quote identity unavailable")
                    quote = QuoteFact(
                        price=_decimal(output.get("last")),
                        currency="USD",
                        fetched_at=now,
                        source="KIS 해외 현재가상세",
                        source_url=SOURCE_URL,
                        unavailable_reason=None
                        if _decimal(output.get("last"))
                        else "현재가가 없습니다.",
                    )
                    fundamentals = FundamentalFacts(
                        eps=_decimal(output.get("epsx")),
                        per=_decimal(output.get("perx")),
                        pbr=_decimal(output.get("pbrx")),
                        source="KIS 해외 현재가상세",
                        source_url=SOURCE_URL,
                        fetched_at=now,
                    )
                    resolved_instrument = resolved_instrument.model_copy(
                        update={
                            "exchange": exchange,
                            "instrument_type": "etf"
                            if "ETF" in _text(output.get("etyp_nm")).upper()
                            else resolved_instrument.instrument_type,
                        }
                    )
                trend, provider_type = await self._yahoo_trend(resolved_instrument)
                if resolved_instrument.instrument_type == "unknown" and provider_type:
                    resolved_instrument = resolved_instrument.model_copy(
                        update={"instrument_type": provider_type}
                    )
                analysis = _detail_analysis(
                    resolved_instrument, quote, fundamentals, trend, now
                )
                return InstrumentDetail(
                    instrument=resolved_instrument,
                    analysis=analysis,
                    limitations=limitations,
                )
            except (BrokerError, httpx.HTTPError, ValueError):
                quote = QuoteFact(
                    currency=resolved_instrument.currency,
                    fetched_at=now,
                    source="KIS",
                    source_url=SOURCE_URL,
                    unavailable_reason="현재가·식별 정보를 확인할 수 없습니다.",
                )
                return InstrumentDetail(
                    instrument=resolved_instrument,
                    analysis=_detail_analysis(
                        resolved_instrument,
                        quote,
                        FundamentalFacts(
                            unavailable_reasons=["재무 자료를 확인할 수 없습니다."]
                        ),
                        TrendFacts(
                            unavailable_reasons=[
                                "신뢰할 수 있는 조정 일봉 자료를 확인하지 못했습니다."
                            ]
                        ),
                        now,
                    ),
                    limitations=limitations + ["세부 조회 실패로 분석을 보류했습니다."],
                )

        result = await self._cached(key, load)
        assert isinstance(result, InstrumentDetail)
        return result

    async def _kr_financials(
        self, symbol: str, base: FundamentalFacts
    ) -> FundamentalFacts:
        """Read the first current KIS fiscal rows without inventing missing values."""
        try:
            ratio_data = await self._request(
                "/uapi/domestic-stock/v1/finance/financial-ratio",
                "FHKST66430300",
                {
                    "FID_DIV_CLS_CODE": "0",
                    "fid_cond_mrkt_div_code": "J",
                    "fid_input_iscd": symbol,
                },
            )
            growth_data = await self._request(
                "/uapi/domestic-stock/v1/finance/growth-ratio",
                "FHKST66430800",
                {
                    "fid_input_iscd": symbol,
                    "fid_div_cls_code": "0",
                    "fid_cond_mrkt_div_code": "J",
                },
            )
            ratio_rows = ratio_data.get("output")
            growth_rows = growth_data.get("output")
            ratio = (
                ratio_rows[0]
                if isinstance(ratio_rows, list)
                and ratio_rows
                and isinstance(ratio_rows[0], Mapping)
                else {}
            )
            growth = (
                growth_rows[0]
                if isinstance(growth_rows, list)
                and growth_rows
                and isinstance(growth_rows[0], Mapping)
                else {}
            )
            period = _text(ratio.get("stac_yymm") or growth.get("stac_yymm")) or None
            ratio_period_end = _period_end(ratio.get("stac_yymm"))
            growth_period_end = _period_end(growth.get("stac_yymm"))
            ratio_eps = _decimal(ratio.get("eps"))
            return base.model_copy(
                update={
                    "growth": _decimal(growth.get("grs") or ratio.get("grs")),
                    "roe": _decimal(ratio.get("roe_val")),
                    "debt_ratio": _decimal(ratio.get("lblt_rate")),
                    "eps": ratio_eps if ratio_eps is not None else base.eps,
                    "period_end": ratio_period_end or growth_period_end,
                    "growth_period_end": growth_period_end,
                    "roe_period_end": ratio_period_end,
                    "debt_period_end": ratio_period_end,
                    "eps_period": period if ratio_eps is not None else base.eps_period,
                    "source": (
                        "KIS financial-ratio (EPS·ROE·부채) + growth-ratio (성장)"
                    ),
                    "unavailable_reasons": []
                    if ratio or growth
                    else ["재무비율 응답이 비어 있습니다."],
                }
            )
        except (BrokerError, httpx.HTTPError, ValueError):
            return base.model_copy(
                update={"unavailable_reasons": ["국내 재무비율을 확인할 수 없습니다."]}
            )

    async def _yahoo_trend(
        self, instrument: Instrument
    ) -> tuple[TrendFacts, InstrumentType | None]:
        suffixes = (".KS", ".KQ") if instrument.market == "KR" else ("",)
        calendar = default_market_calendar()
        now = datetime.now(UTC)
        expected = calendar.latest_completed_session(instrument.exchange, now)
        if expected is None:
            return (
                TrendFacts(
                    source="Yahoo chart",
                    unavailable_reasons=[
                        "거래소 달력에서 최신 완료 거래일을 확인하지 못했습니다."
                    ],
                ),
                None,
            )
        verified_type: InstrumentType | None = None
        try:
            async with httpx.AsyncClient(
                timeout=10,
                follow_redirects=False,
                trust_env=False,
                headers={"User-Agent": "jusik-investor/1.0"},
            ) as client:
                for suffix in suffixes:
                    ticker = f"{instrument.symbol}{suffix}"
                    response = await client.get(
                        f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}",
                        params={
                            "range": "6mo",
                            "interval": "1d",
                            "events": "div,splits",
                            "includeAdjustedClose": "true",
                        },
                    )
                    if response.status_code >= 400:
                        continue
                    payload = response.json()
                    chart = payload.get("chart")
                    results = (
                        chart.get("result") if isinstance(chart, Mapping) else None
                    )
                    result = (
                        results[0] if isinstance(results, list) and results else None
                    )
                    if not isinstance(result, Mapping):
                        continue
                    meta = result.get("meta")
                    if not isinstance(meta, Mapping):
                        continue
                    if _text(meta.get("symbol")).upper() != ticker.upper():
                        continue
                    provider_type = _text(meta.get("instrumentType")).upper()
                    if provider_type not in {"EQUITY", "ETF"}:
                        continue
                    verified_type = "etf" if provider_type == "ETF" else "stock"
                    if (
                        instrument.instrument_type == "stock"
                        and provider_type != "EQUITY"
                    ):
                        continue
                    if instrument.instrument_type == "etf" and provider_type != "ETF":
                        continue
                    timestamps = result.get("timestamp")
                    indicators = result.get("indicators")
                    quote = (
                        indicators.get("quote")
                        if isinstance(indicators, Mapping)
                        else None
                    )
                    adj = (
                        indicators.get("adjclose")
                        if isinstance(indicators, Mapping)
                        else None
                    )
                    raw = quote[0] if isinstance(quote, list) and quote else None
                    adjusted = (
                        adj[0].get("adjclose")
                        if isinstance(adj, list) and adj and isinstance(adj[0], Mapping)
                        else None
                    )
                    closes = raw.get("close") if isinstance(raw, Mapping) else None
                    volumes = raw.get("volume") if isinstance(raw, Mapping) else None
                    if not all(
                        isinstance(item, list)
                        for item in (timestamps, closes, volumes, adjusted)
                    ):
                        continue
                    timestamps = cast(list[object], timestamps)
                    closes = cast(list[object], closes)
                    volumes = cast(list[object], volumes)
                    adjusted = cast(list[object], adjusted)
                    if (
                        not len(
                            {len(timestamps), len(closes), len(volumes), len(adjusted)}
                        )
                        == 1
                    ):
                        continue
                    timezone = ZoneInfo(
                        "Asia/Seoul"
                        if instrument.market == "KR"
                        else "America/New_York"
                    )
                    today_local = now.astimezone(timezone).date()
                    bars: list[DailyBar] = []
                    for stamp, close, adj_close, volume in zip(
                        timestamps, closes, adjusted, volumes, strict=True
                    ):
                        if any(
                            isinstance(item, bool)
                            or not isinstance(item, (int, float))
                            or not math.isfinite(float(item))
                            for item in (stamp, close, adj_close, volume)
                        ):
                            bars = []
                            break
                        session = (
                            datetime.fromtimestamp(float(cast(int | float, stamp)), UTC)
                            .astimezone(timezone)
                            .date()
                        )
                        if session > today_local:
                            bars = []
                            break
                        if session == today_local and (
                            expected.local_date != today_local
                            or expected.close_at > now
                        ):
                            continue
                        parsed_close = _decimal(adj_close)
                        parsed_volume = _decimal(volume)
                        if (
                            parsed_close is None
                            or parsed_volume is None
                            or parsed_close <= 0
                            or parsed_volume < 0
                        ):
                            bars = []
                            break
                        bars.append(
                            DailyBar(
                                session=session,
                                close=parsed_close,
                                volume=parsed_volume,
                                adjusted=True,
                            )
                        )
                    if not bars:
                        continue
                    trend = evaluate_trend(
                        bars,
                        today=expected.local_date,
                        expected_latest_session=expected.local_date,
                        source=f"Yahoo chart ({ticker})",
                    )
                    if trend.unavailable_reasons:
                        continue
                    trend = trend.model_copy(
                        update={
                            "source_url": f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
                        }
                    )
                    return trend, verified_type
            raise ValueError("validated chart bars unavailable")
        except (httpx.HTTPError, json.JSONDecodeError, TypeError, ValueError):
            return (
                TrendFacts(
                    source="Yahoo chart",
                    unavailable_reasons=[
                        "신뢰할 수 있는 조정 일봉 자료를 확인하지 못했습니다."
                    ],
                ),
                verified_type,
            )


def _detail_analysis(
    instrument: Instrument,
    quote: QuoteFact,
    fundamentals: FundamentalFacts,
    trend: TrendFacts,
    now: datetime,
) -> AnalysisResult:
    return analyze(instrument, quote, fundamentals, trend, now=now)


class InMemoryInvestorProvider:
    def __init__(
        self, details: list[InstrumentDetail], candidates: dict[Market, DiscoveryResult]
    ) -> None:
        self.details = {
            (item.instrument.market, item.instrument.symbol): item for item in details
        }
        self.candidates = candidates

    async def discover(self, market: Market) -> DiscoveryResult:
        return self.candidates[market]

    async def detail(self, instrument: Instrument) -> InstrumentDetail:
        return self.details[(instrument.market, instrument.symbol)]
