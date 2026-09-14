import asyncio
import calendar
import json
import math
import time
from collections.abc import Callable, Coroutine, Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol, cast
from zoneinfo import ZoneInfo

import httpx

from jusik.investor_analysis import analyze, evaluate_trend, quote_status
from jusik.investor_models import (
    AnalysisResult,
    Candidate,
    Currency,
    DailyBar,
    DiscoveryCounts,
    DiscoveryResult,
    FundamentalFacts,
    Instrument,
    InstrumentDetail,
    InstrumentType,
    Market,
    QuoteFact,
    RelativeVolumeFacts,
    TrendFacts,
)
from jusik.kis import BrokerError, KisClient
from jusik.research_market_calendar import (
    MarketCalendar,
    MarketSession,
    default_market_calendar,
)

SOURCE_URL = "https://apiportal.koreainvestment.com/apiservice"
MAX_CANDIDATES = 20
US_EXCHANGES = ("NAS", "NYS", "AMS")
MAX_DISCOVERY_ROWS = 80
MAX_KR_DISCOVERY_ROWS = 60
DISCOVERY_BATCH_SIZE = 4
DISCOVERY_DEADLINE_SECONDS = 20
DISCOVERY_REQUEST_TIMEOUT_SECONDS = 6
DISCOVERY_SOURCE_URL = "https://query1.finance.yahoo.com/v8/finance/chart"
YAHOO_EXCHANGES: dict[str, set[str]] = {
    "NAS": {"NMS", "NGM", "NCM", "NAS"},
    "NYS": {"NYQ", "NYS", "NYSE"},
    "AMS": {"ASE", "AMS", "AMEX", "PCX"},
}


@dataclass(frozen=True)
class _RankedRow:
    instrument: Instrument
    volume: Decimal
    observed_at: datetime
    source: str


@dataclass(frozen=True)
class _CandidateChartResult:
    instrument_type: InstrumentType | None
    relative_volume: RelativeVolumeFacts | None
    reason: str | None = None
    failed: bool = False


@dataclass
class _DiscoveryProgress:
    stock_candidates: list[Candidate] = field(default_factory=list)
    etf_candidates: list[Candidate] = field(default_factory=list)
    counts: DiscoveryCounts = field(default_factory=DiscoveryCounts)
    source_rows: int = 0
    valid_rows: int = 0
    inspected: int = 0


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
        self._inflight_waiters: dict[tuple[str, str], int] = {}
        self._inflight_lock = asyncio.Lock()
        self._candidate_semaphore = asyncio.Semaphore(4)

    async def _cached(
        self,
        key: tuple[str, str],
        loader: Callable[[], Coroutine[Any, Any, object]],
        *,
        cache_seconds: int | None = None,
    ) -> object:
        now = time.monotonic()
        ttl = self.cache_seconds if cache_seconds is None else cache_seconds
        cached = self._cache.get(key)
        if cached and now - cached[1] < ttl:
            return cached[0]
        async with self._inflight_lock:
            task = self._inflight.get(key)
            if task is None:
                task = asyncio.create_task(loader())
                self._inflight[key] = task
                self._inflight_waiters[key] = 0
            self._inflight_waiters[key] += 1
        try:
            result = await asyncio.shield(task)
            self._cache[key] = (result, time.monotonic())
            return result
        finally:
            drain = False
            async with self._inflight_lock:
                waiters = self._inflight_waiters.get(key, 1) - 1
                if waiters <= 0:
                    self._inflight_waiters.pop(key, None)
                    drain = self._inflight.get(key) is task and not task.done()
                else:
                    self._inflight_waiters[key] = waiters
                if self._inflight.get(key) is task and waiters <= 0:
                    del self._inflight[key]
            if drain:
                task.cancel()
                asyncio.create_task(self._drain_task(task))

    @staticmethod
    async def _drain_task(task: asyncio.Task[object]) -> None:
        try:
            await task
        except BaseException:
            # Cancellation and loader failures are already delivered to the
            # waiting callers; this prevents an orphaned task warning.
            pass

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
        instrument_type: InstrumentType = (
            "etf" if etyp and "ETF" in etyp.upper() else "unknown"
        )
        return Instrument(
            market=market,
            exchange="KRX" if market == "KR" else exchange,
            symbol=symbol,
            currency="KRW" if market == "KR" else "USD",
            name=name,
            instrument_type=instrument_type,
        )

    async def discover(self, market: Market) -> DiscoveryResult:
        key = ("discover", market)

        async def load() -> DiscoveryResult:
            return await self._discover(market)

        result = await self._cached(key, load)
        assert isinstance(result, DiscoveryResult)
        return result

    async def _discover(self, market: Market) -> DiscoveryResult:
        now = datetime.now(UTC)
        errors: list[str] = []
        progress = _DiscoveryProgress()
        try:
            async with asyncio.timeout(DISCOVERY_DEADLINE_SECONDS):
                rows, source_rows, rank_errors = await self._rank_rows(market, now)
                errors.extend(rank_errors)
                progress.source_rows = source_rows
                progress.valid_rows = len(rows)
                return await self._classify_rows(
                    market, rows, source_rows, errors, now, progress=progress
                )
        except TimeoutError:
            errors.append("후보 분류 시간이 제한을 넘어 수집된 자료만 표시합니다.")
            progress.counts = progress.counts.model_copy(
                update={"failed": progress.counts.failed + 1}
            )
            return self._discovery_result(market, progress, errors, now, truncated=True)

    async def _rank_rows(
        self, market: Market, observed_at: datetime
    ) -> tuple[list[_RankedRow], int, list[str]]:
        raw_rows: list[tuple[str, Mapping[str, object], datetime]] = []
        errors: list[str] = []

        async def request_rows(
            label: str,
            path: str,
            tr_id: str,
            params: dict[str, str],
            output_key: str,
            exchange: str,
            limit: int,
        ) -> None:
            try:
                data = await asyncio.wait_for(
                    self._request(path, tr_id, params),
                    timeout=DISCOVERY_REQUEST_TIMEOUT_SECONDS,
                )
            except (BrokerError, httpx.HTTPError, TimeoutError, ValueError):
                errors.append(f"{label} 거래량 순위를 확인하지 못했습니다.")
                return
            output = data.get(output_key)
            if not isinstance(output, list):
                return
            source_observed_at = datetime.now(UTC)
            for row in output[:limit]:
                if isinstance(row, Mapping):
                    raw_rows.append((exchange, row, source_observed_at))

        if market == "KR":
            base_params = {
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_COND_SCR_DIV_CODE": "20171",
                "FID_INPUT_ISCD": "0000",
                "FID_BLNG_CLS_CODE": "0",
                "FID_TRGT_CLS_CODE": "111111111",
                "FID_INPUT_PRICE_1": "",
                "FID_INPUT_PRICE_2": "",
                "FID_VOL_CNT": "",
                "FID_INPUT_DATE_1": "",
            }
            await request_rows(
                "한국 전체",
                "/uapi/domestic-stock/v1/quotations/volume-rank",
                "FHPST01710000",
                {
                    **base_params,
                    "FID_DIV_CLS_CODE": "0",
                    "FID_TRGT_EXLS_CLS_CODE": "0000000000",
                },
                "output",
                "KRX",
                30,
            )
            await request_rows(
                "한국 주식",
                "/uapi/domestic-stock/v1/quotations/volume-rank",
                "FHPST01710000",
                {
                    **base_params,
                    "FID_DIV_CLS_CODE": "1",
                    "FID_TRGT_EXLS_CLS_CODE": "0000001100",
                },
                "output",
                "KRX",
                30,
            )
        else:
            for exchange in US_EXCHANGES:
                await request_rows(
                    f"미국 {exchange}",
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
                    "output2",
                    exchange,
                    100,
                )

        ranked: dict[tuple[str, str, str], _RankedRow] = {}
        for requested_exchange, row, row_observed_at in raw_rows:
            parsed = self._parse_rank_row(
                market, requested_exchange, row, row_observed_at
            )
            if parsed is None:
                continue
            key = (
                parsed.instrument.market,
                parsed.instrument.exchange,
                parsed.instrument.symbol,
            )
            previous = ranked.get(key)
            if previous is None or parsed.volume > previous.volume:
                ranked[key] = parsed
        rows = sorted(
            ranked.values(),
            key=lambda item: (
                -item.volume,
                item.instrument.exchange,
                item.instrument.symbol,
            ),
        )
        return rows, len(raw_rows), errors

    @staticmethod
    def _parse_rank_row(
        market: Market,
        requested_exchange: str,
        row: Mapping[str, object],
        observed_at: datetime,
    ) -> _RankedRow | None:
        row_exchange = _text(row.get("excd"))
        if row_exchange and row_exchange.upper() != requested_exchange.upper():
            return None
        symbols: list[str] = []
        if market == "KR":
            for key in ("mksc_shrn_iscd", "stck_shrn_iscd"):
                value = _text(row.get(key))
                if value:
                    symbols.append(value.upper())
        else:
            plain = _text(row.get("symb"))
            if plain:
                symbols.append(plain.upper())
            qualified = _text(row.get("rsym"))
            if qualified:
                prefix = f"D{requested_exchange}".upper()
                if not qualified.upper().startswith(prefix):
                    return None
                symbol = qualified[len(prefix) :].upper()
                if symbol:
                    symbols.append(symbol)
        if not symbols or len(set(symbols)) != 1:
            return None
        symbol = symbols[0]
        if not symbol.replace("-", "").replace(".", "").isalnum():
            return None
        volume = _decimal(row.get("acml_vol" if market == "KR" else "tvol"))
        if volume is None or volume < 0 or volume != volume.to_integral_value():
            return None
        return _RankedRow(
            instrument=Instrument(
                market=market,
                exchange="KRX" if market == "KR" else requested_exchange,
                symbol=symbol,
                currency="KRW" if market == "KR" else "USD",
                name=_text(
                    row.get("prdt_name")
                    or row.get("hts_kor_isnm")
                    or row.get("name")
                    or symbol
                ),
            ),
            volume=volume,
            observed_at=observed_at,
            source="KIS 거래량 순위",
        )

    async def _classify_rows(
        self,
        market: Market,
        rows: list[_RankedRow],
        source_rows: int,
        errors: list[str],
        observed_at: datetime,
        *,
        progress: _DiscoveryProgress | None = None,
    ) -> DiscoveryResult:
        progress = progress or _DiscoveryProgress()
        progress.source_rows = source_rows
        progress.valid_rows = len(rows)
        progress.counts = progress.counts.model_copy(
            update={"source_rows": source_rows, "valid_rows": len(rows)}
        )
        max_rows = MAX_KR_DISCOVERY_ROWS if market == "KR" else MAX_DISCOVERY_ROWS
        async with httpx.AsyncClient(
            timeout=5,
            follow_redirects=False,
            trust_env=False,
            headers={"User-Agent": "jusik-investor/1.0"},
        ) as client:
            for start in range(0, min(len(rows), max_rows), DISCOVERY_BATCH_SIZE):
                if (
                    len(progress.stock_candidates) >= MAX_CANDIDATES
                    and len(progress.etf_candidates) >= MAX_CANDIDATES
                ):
                    break
                batch = rows[start : start + DISCOVERY_BATCH_SIZE]
                tasks = [
                    asyncio.create_task(
                        self._candidate_chart(client, row.instrument, observed_at)
                    )
                    for row in batch
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                progress.inspected += len(batch)
                for row, result in zip(batch, results, strict=True):
                    if isinstance(result, BaseException):
                        progress.counts.failed += 1
                        if len(errors) < 10:
                            errors.append(
                                "일부 종목의 분류·상대거래량을 확인하지 못했습니다."
                            )
                        continue
                    if result.instrument_type is None:
                        if result.failed:
                            progress.counts.failed += 1
                        else:
                            progress.counts.unknown += 1
                        if result.reason and len(errors) < 10 and result.failed:
                            errors.append(result.reason)
                        continue
                    instrument = row.instrument.model_copy(
                        update={"instrument_type": result.instrument_type}
                    )
                    reason = (
                        "KIS 누적 거래량 순위와 Yahoo 상대거래량을 함께 표시합니다."
                    )
                    if result.relative_volume is not None:
                        if result.relative_volume.ratio is None:
                            reason += (
                                " 상대거래량을 확인할 수 없습니다: "
                                f"{result.relative_volume.unavailable_reason}"
                            )
                        else:
                            reason += (
                                " 상대거래량은 직전 완료 20거래일 평균 대비입니다."
                            )
                    candidate = Candidate(
                        instrument=instrument,
                        rank=1,
                        reason=reason,
                        source=row.source,
                        observed_at=row.observed_at,
                        ranking_volume=row.volume,
                        classification_source="Yahoo chart metadata",
                        classification_observed_at=(
                            result.relative_volume.fetched_at
                            if result.relative_volume is not None
                            else observed_at
                        ),
                        relative_volume=result.relative_volume,
                    )
                    if result.instrument_type == "stock":
                        if len(progress.stock_candidates) < MAX_CANDIDATES:
                            progress.stock_candidates.append(
                                candidate.model_copy(
                                    update={"rank": len(progress.stock_candidates) + 1}
                                )
                            )
                    elif len(progress.etf_candidates) < MAX_CANDIDATES:
                        progress.etf_candidates.append(
                            candidate.model_copy(
                                update={"rank": len(progress.etf_candidates) + 1}
                            )
                        )
        progress.counts = progress.counts.model_copy(
            update={
                "inspected": progress.inspected,
                "stocks": len(progress.stock_candidates),
                "etfs": len(progress.etf_candidates),
                "unscanned": max(0, len(rows) - progress.inspected),
            }
        )
        return self._discovery_result(market, progress, errors, observed_at)

    @staticmethod
    def _discovery_result(
        market: Market,
        progress: _DiscoveryProgress,
        errors: list[str],
        observed_at: datetime,
        *,
        truncated: bool = False,
    ) -> DiscoveryResult:
        max_rows = MAX_KR_DISCOVERY_ROWS if market == "KR" else MAX_DISCOVERY_ROWS
        counts = progress.counts.model_copy(
            update={
                "source_rows": progress.source_rows,
                "valid_rows": progress.valid_rows,
                "inspected": progress.inspected,
                "stocks": len(progress.stock_candidates),
                "etfs": len(progress.etf_candidates),
                "unscanned": max(0, progress.valid_rows - progress.inspected),
            }
        )
        return DiscoveryResult(
            market=market,
            candidates=progress.stock_candidates,
            etf_candidates=progress.etf_candidates,
            coverage=(
                "KIS 첫 페이지에서 확인한 거래량 후보를 수치로 정렬했습니다. "
                "전체 시장 순위나 저평가를 보장하지 않습니다."
            ),
            truncated=truncated
            or progress.source_rows > max_rows
            or counts.unscanned > 0,
            partial=bool(errors) or counts.failed > 0 or counts.unknown > 0,
            errors=errors[:10],
            fetched_at=observed_at,
            counts=counts,
        )

    async def _candidate_chart(
        self,
        client: httpx.AsyncClient,
        instrument: Instrument,
        fetched_at: datetime,
    ) -> _CandidateChartResult:
        key = (
            "candidate-chart",
            f"{instrument.market}:{instrument.exchange}:{instrument.symbol}",
        )

        async def load() -> _CandidateChartResult:
            async with self._candidate_semaphore:
                return await self._fetch_candidate_chart(client, instrument, fetched_at)

        result = await self._cached(key, load, cache_seconds=300)
        assert isinstance(result, _CandidateChartResult)
        return result

    async def _fetch_candidate_chart(
        self,
        client: httpx.AsyncClient,
        instrument: Instrument,
        fetched_at: datetime,
    ) -> _CandidateChartResult:
        suffixes = (".KS", ".KQ") if instrument.market == "KR" else ("",)
        for suffix in suffixes:
            ticker = f"{instrument.symbol}{suffix}"
            try:
                response = await client.get(
                    f"{DISCOVERY_SOURCE_URL}/{ticker}",
                    params={
                        "range": "3mo",
                        "interval": "1d",
                        "events": "div,splits",
                        "includeAdjustedClose": "true",
                    },
                )
                if response.status_code >= 400:
                    continue
                payload = response.json()
                result = self._chart_result(payload)
                if result is None:
                    continue
                meta = result.get("meta")
                if not isinstance(meta, Mapping) or not self._valid_chart_identity(
                    instrument, ticker, meta
                ):
                    continue
                provider_type = _text(meta.get("instrumentType")).upper()
                if provider_type not in {"EQUITY", "ETF"}:
                    # A Korean symbol can have a valid Yahoo listing on the
                    # other board (for example, a mutual-fund record on .KS
                    # and an equity record on .KQ). Keep trying the bounded
                    # suffix list before declaring its type unknown.
                    continue
                instrument_type: InstrumentType = (
                    "etf" if provider_type == "ETF" else "stock"
                )
                chart_fetched_at = datetime.now(UTC)
                relative = self._relative_volume(
                    instrument, result, meta, chart_fetched_at, ticker
                )
                return _CandidateChartResult(
                    instrument_type=instrument_type,
                    relative_volume=relative,
                )
            except (httpx.HTTPError, json.JSONDecodeError, TypeError, ValueError):
                continue
        return _CandidateChartResult(
            instrument_type=None,
            relative_volume=None,
            reason="Yahoo 종목 분류 자료를 확인하지 못해 후보에서 제외했습니다.",
            failed=True,
        )

    @staticmethod
    def _chart_result(payload: object) -> Mapping[str, object] | None:
        if not isinstance(payload, Mapping):
            return None
        chart = payload.get("chart")
        if not isinstance(chart, Mapping):
            return None
        results = chart.get("result")
        result = results[0] if isinstance(results, list) and results else None
        return result if isinstance(result, Mapping) else None

    @staticmethod
    def _valid_chart_identity(
        instrument: Instrument, ticker: str, meta: Mapping[str, object]
    ) -> bool:
        if _text(meta.get("symbol")).upper() != ticker.upper():
            return False
        expected_currency = "KRW" if instrument.market == "KR" else "USD"
        if _text(meta.get("currency")).upper() != expected_currency:
            return False
        expected_timezone = (
            "Asia/Seoul" if instrument.market == "KR" else "America/New_York"
        )
        if _text(meta.get("exchangeTimezoneName")) != expected_timezone:
            return False
        venue = _text(meta.get("exchangeName")).upper()
        if instrument.market == "KR":
            suffix = ticker.rsplit(".", maxsplit=1)[-1].upper()
            allowed_venues = {
                "KS": {"KSC", "KOSPI"},
                "KQ": {"KOE", "KOSDAQ"},
            }.get(suffix, set())
            return venue in allowed_venues
        return venue in YAHOO_EXCHANGES.get(instrument.exchange, set())

    def _relative_volume(
        self,
        instrument: Instrument,
        result: Mapping[str, object],
        meta: Mapping[str, object],
        fetched_at: datetime,
        ticker: str,
    ) -> RelativeVolumeFacts:
        source_url = f"{DISCOVERY_SOURCE_URL}/{ticker}"
        unavailable = self._unavailable_relative(
            source_url, fetched_at, "상대거래량 자료를 확인할 수 없습니다."
        )
        market_volume = _decimal(meta.get("regularMarketVolume"))
        market_time_value = meta.get("regularMarketTime")
        if (
            market_volume is None
            or market_volume < 0
            or market_volume != market_volume.to_integral_value()
            or not isinstance(market_time_value, (int, float))
            or isinstance(market_time_value, bool)
            or not math.isfinite(float(market_time_value))
        ):
            return unavailable.model_copy(
                update={
                    "unavailable_reason": (
                        "현재 거래량 또는 기준 시각이 유효하지 않습니다."
                    )
                }
            )
        market_time = datetime.fromtimestamp(float(market_time_value), UTC)
        quote = QuoteFact(
            price=None,
            currency="KRW" if instrument.market == "KR" else "USD",
            as_of=market_time,
            fetched_at=fetched_at,
            source=f"Yahoo chart ({ticker}) 거래량",
            source_url=source_url,
        )
        status = self._volume_quote_status(instrument, quote, fetched_at)
        if status != "usable":
            return unavailable.model_copy(
                update={
                    "unavailable_reason": (
                        "현재 거래량 기준 시각이 최신 거래 세션과 맞지 않습니다."
                    )
                }
            )
        calendar_obj = default_market_calendar()
        latest = calendar_obj.latest_completed_session(instrument.exchange, fetched_at)
        if latest is None:
            return unavailable.model_copy(
                update={"unavailable_reason": "거래소 달력 범위 밖입니다."}
            )
        timezone = ZoneInfo(
            "Asia/Seoul" if instrument.market == "KR" else "America/New_York"
        )
        current_lookup = calendar_obj.lookup(
            instrument.exchange, fetched_at.astimezone(timezone).date()
        )
        if (
            current_lookup.session is not None
            and current_lookup.session.open_at
            <= fetched_at
            < current_lookup.session.close_at
            and market_time.astimezone(timezone).date()
            == current_lookup.session.local_date
        ):
            numerator_session = current_lookup.session.local_date
        else:
            numerator_session = latest.local_date
        prior_sessions = self._prior_sessions(
            calendar_obj, instrument.exchange, numerator_session
        )
        if prior_sessions is None:
            return unavailable.model_copy(
                update={
                    "unavailable_reason": (
                        "직전 20거래일 달력 범위를 확인할 수 없습니다."
                    )
                }
            )
        volumes = self._chart_volumes(result, instrument, fetched_at)
        if volumes is None:
            return unavailable.model_copy(
                update={"unavailable_reason": "일봉 거래량 배열이 유효하지 않습니다."}
            )
        split_reason = self._split_in_comparison_window(
            result, instrument, prior_sessions, numerator_session
        )
        if split_reason:
            return unavailable.model_copy(update={"unavailable_reason": split_reason})
        prior_volumes: list[Decimal] = []
        for session in prior_sessions:
            volume = volumes.get(session.local_date)
            if volume is None:
                return unavailable.model_copy(
                    update={
                        "unavailable_reason": (
                            "직전 20거래일 거래량이 모두 제공되지 않았습니다."
                        )
                    }
                )
            prior_volumes.append(volume)
        average = sum(prior_volumes, Decimal(0)) / Decimal(20)
        if average == 0:
            return unavailable.model_copy(
                update={"unavailable_reason": "직전 20거래일 평균 거래량이 0입니다."}
            )
        return RelativeVolumeFacts(
            numerator=market_volume,
            average20=average,
            ratio=market_volume / average,
            sample_count=20,
            sample_start=prior_sessions[-1].local_date,
            sample_end=prior_sessions[0].local_date,
            source=f"Yahoo chart ({ticker}) 거래량",
            source_url=source_url,
            as_of=market_time,
            fetched_at=fetched_at,
        )

    @staticmethod
    def _unavailable_relative(
        source_url: str, fetched_at: datetime, reason: str
    ) -> RelativeVolumeFacts:
        return RelativeVolumeFacts(
            source="Yahoo chart 거래량",
            source_url=source_url,
            fetched_at=fetched_at,
            unavailable_reason=reason,
        )

    @staticmethod
    def _volume_quote_status(
        instrument: Instrument, quote: QuoteFact, now: datetime
    ) -> str:
        status = quote_status(instrument, quote, now)
        if status != "stale" or quote.as_of is None:
            return status
        calendar_obj = default_market_calendar()
        latest = calendar_obj.latest_completed_session(instrument.exchange, now)
        if latest is None:
            return status
        if (
            latest.local_date
            == quote.as_of.astimezone(
                ZoneInfo(
                    "Asia/Seoul" if instrument.market == "KR" else "America/New_York"
                )
            ).date()
            and latest.close_at < quote.as_of <= latest.close_at + timedelta(seconds=60)
            and now - quote.fetched_at <= timedelta(minutes=15)
        ):
            return "usable"
        return status

    @staticmethod
    def _prior_sessions(
        calendar_obj: MarketCalendar, exchange: str, anchor: date
    ) -> list[MarketSession] | None:
        coverage_start = calendar_obj.coverage_start
        current = anchor - timedelta(days=1)
        sessions: list[MarketSession] = []
        while current >= coverage_start and len(sessions) < 20:
            lookup = calendar_obj.lookup(exchange, current)
            if lookup.state == "unavailable":
                return None
            if lookup.session is not None:
                sessions.append(lookup.session)
            current -= timedelta(days=1)
        return sessions if len(sessions) == 20 else None

    @staticmethod
    def _chart_volumes(
        result: Mapping[str, object], instrument: Instrument, now: datetime
    ) -> dict[date, Decimal] | None:
        timestamps: object = result.get("timestamp")
        indicators = result.get("indicators")
        quote_block = (
            indicators.get("quote") if isinstance(indicators, Mapping) else None
        )
        raw = quote_block[0] if isinstance(quote_block, list) and quote_block else None
        values = raw.get("volume") if isinstance(raw, Mapping) else None
        if not isinstance(timestamps, list) or not isinstance(values, list):
            return None
        if len(timestamps) != len(values):
            return None
        timezone = ZoneInfo(
            "Asia/Seoul" if instrument.market == "KR" else "America/New_York"
        )
        calendar_obj = default_market_calendar()
        parsed: dict[date, Decimal] = {}
        previous: date | None = None
        for stamp, value in zip(timestamps, values, strict=True):
            if (
                isinstance(stamp, bool)
                or not isinstance(stamp, (int, float))
                or not math.isfinite(float(stamp))
            ):
                return None
            volume = _decimal(value)
            if (
                volume is None
                or volume < 0
                or isinstance(value, bool)
                or (
                    previous is not None
                    and previous
                    >= datetime.fromtimestamp(float(stamp), UTC)
                    .astimezone(timezone)
                    .date()
                )
            ):
                return None
            session = (
                datetime.fromtimestamp(float(stamp), UTC).astimezone(timezone).date()
            )
            lookup = calendar_obj.lookup(instrument.exchange, session)
            if lookup.state == "unavailable" or lookup.session is None:
                return None
            if lookup.session.open_at > now:
                return None
            if session in parsed:
                return None
            parsed[session] = volume
            previous = session
        return parsed

    @staticmethod
    def _split_in_comparison_window(
        result: Mapping[str, object],
        instrument: Instrument,
        sessions: list[MarketSession],
        numerator_session: date | None = None,
    ) -> str | None:
        events = result.get("events")
        if events is None:
            return None
        if not isinstance(events, Mapping):
            return "기업행사 자료 형식이 유효하지 않습니다."
        splits = events.get("splits")
        if splits is None:
            return None
        if not isinstance(splits, Mapping):
            return "분할 자료 형식이 유효하지 않습니다."
        timezone = ZoneInfo(
            "Asia/Seoul" if instrument.market == "KR" else "America/New_York"
        )
        comparison_dates = {session.local_date for session in sessions}
        if numerator_session is not None:
            comparison_dates.add(numerator_session)
        for item in splits.values():
            if not isinstance(item, Mapping):
                return "분할 자료 형식이 유효하지 않습니다."
            stamp = item.get("date") or item.get("timestamp")
            if (
                isinstance(stamp, bool)
                or not isinstance(stamp, (int, float))
                or not math.isfinite(float(stamp))
            ):
                return "분할 기준 시각이 유효하지 않습니다."
            split_date = (
                datetime.fromtimestamp(float(stamp), UTC).astimezone(timezone).date()
            )
            if split_date in comparison_dates:
                return "분자 및 직전 20거래일 비교 구간에 분할 자료가 있어 보류합니다."
        return None

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
                trend, provider_type, yahoo_quote = await self._yahoo_trend(
                    resolved_instrument
                )
                if yahoo_quote is not None:
                    quote = yahoo_quote
                if resolved_instrument.instrument_type == "unknown" and provider_type:
                    resolved_instrument = resolved_instrument.model_copy(
                        update={"instrument_type": provider_type}
                    )
                analysis_now = datetime.now(UTC)
                analysis = _detail_analysis(
                    resolved_instrument, quote, fundamentals, trend, analysis_now
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
    ) -> tuple[TrendFacts, InstrumentType | None, QuoteFact | None]:
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
                None,
            )
        verified_type: InstrumentType | None = None
        verified_quote: QuoteFact | None = None
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
                    expected_currency: Currency = (
                        "KRW" if instrument.market == "KR" else "USD"
                    )
                    if _text(meta.get("currency")).upper() != expected_currency:
                        continue
                    expected_timezone = (
                        "Asia/Seoul"
                        if instrument.market == "KR"
                        else "America/New_York"
                    )
                    if _text(meta.get("exchangeTimezoneName")) != expected_timezone:
                        continue
                    exchange_name = _text(meta.get("exchangeName")).upper()
                    allowed_exchange_names = (
                        {"KSC", "KOE", "KOSPI", "KOSDAQ", "KRX"}
                        if instrument.market == "KR"
                        else YAHOO_EXCHANGES.get(instrument.exchange, set())
                    )
                    if exchange_name not in allowed_exchange_names:
                        continue
                    if (
                        instrument.instrument_type == "stock"
                        and provider_type != "EQUITY"
                    ):
                        continue
                    if instrument.instrument_type == "etf" and provider_type != "ETF":
                        continue
                    verified_type = "etf" if provider_type == "ETF" else "stock"
                    market_price = _decimal(meta.get("regularMarketPrice"))
                    market_time = meta.get("regularMarketTime")
                    if (
                        market_price is not None
                        and isinstance(market_time, (int, float))
                        and not isinstance(market_time, bool)
                        and math.isfinite(float(market_time))
                    ):
                        verified_quote = QuoteFact(
                            price=market_price,
                            currency=expected_currency,
                            as_of=datetime.fromtimestamp(float(market_time), UTC),
                            fetched_at=now,
                            source=f"Yahoo chart ({ticker}) 시장가",
                            source_url=f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}",
                        )
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
                    return trend, verified_type, verified_quote
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
                verified_quote,
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
