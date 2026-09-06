import asyncio
import time
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError

from jusik.config import Settings
from jusik.models import (
    Holding,
    MarketResult,
    Portfolio,
    Positive,
    percentage,
    summarize,
)

MARKETS = (
    ("KRX", "KRW"),
    ("NASD", "USD"),
    ("SEHK", "HKD"),
    ("SHAA", "CNY"),
    ("SZAA", "CNY"),
    ("TKSE", "JPY"),
    ("HASE", "VND"),
    ("VNSE", "VND"),
)


class BrokerError(Exception):
    """A sanitized error safe to display without broker response contents."""


class Token(BaseModel):
    access_token: SecretStr
    expires_in: int = Field(gt=60)


class Envelope(BaseModel):
    rt_cd: str
    output1: list[dict[str, object]]
    ctx_area_fk100: str = ""
    ctx_area_nk100: str = ""
    ctx_area_fk200: str = ""
    ctx_area_nk200: str = ""


class DomesticRow(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pdno: str = Field(min_length=1)
    prdt_name: str
    hldg_qty: Positive
    pchs_avg_pric: Positive
    prpr: Positive
    pchs_amt: Positive
    evlu_amt: Positive
    evlu_pfls_amt: Decimal = Field(allow_inf_nan=False)


class OverseasRow(BaseModel):
    model_config = ConfigDict(extra="ignore")
    ovrs_pdno: str = Field(min_length=1)
    ovrs_item_name: str = ""
    ovrs_cblc_qty: Positive
    pchs_avg_pric: Positive
    now_pric2: Positive
    frcr_pchs_amt1: Positive
    ovrs_stck_evlu_amt: Positive
    frcr_evlu_pfls_amt: Decimal = Field(allow_inf_nan=False)
    tr_crcy_cd: Literal["USD", "HKD", "CNY", "JPY", "VND"]


def normalize(row: dict[str, object], market: str, currency: str) -> Holding:
    if market == "KRX":
        d = DomesticRow.model_validate(row)
        return Holding(
            market=market,
            symbol=d.pdno,
            name=d.prdt_name,
            currency="KRW",
            quantity=d.hldg_qty,
            average_price=d.pchs_avg_pric,
            current_price=d.prpr,
            cost=d.pchs_amt,
            value=d.evlu_amt,
            profit=d.evlu_pfls_amt,
            return_pct=percentage(d.evlu_pfls_amt, d.pchs_amt),
        )
    o = OverseasRow.model_validate(row)
    if o.tr_crcy_cd != currency:
        raise BrokerError("응답 통화가 요청 통화와 다릅니다.")
    return Holding(
        market=market,
        symbol=o.ovrs_pdno,
        name=o.ovrs_item_name or o.ovrs_pdno,
        currency=o.tr_crcy_cd,
        quantity=o.ovrs_cblc_qty,
        average_price=o.pchs_avg_pric,
        current_price=o.now_pric2,
        cost=o.frcr_pchs_amt1,
        value=o.ovrs_stck_evlu_amt,
        profit=o.frcr_evlu_pfls_amt,
        return_pct=percentage(o.frcr_evlu_pfls_amt, o.frcr_pchs_amt1),
    )


class KisClient:
    def __init__(self, settings: Settings, client: httpx.AsyncClient) -> None:
        self.settings = settings
        self.client = client
        self._token = ""
        self._expires = 0.0
        self._last_request = 0.0
        self._auth_retry_after = 0.0
        self._lock = asyncio.Lock()
        self._cached: Portfolio | None = None
        self._cached_at = 0.0

    async def _authenticate(self) -> None:
        if self._token and time.monotonic() < self._expires:
            return
        if time.monotonic() < self._auth_retry_after:
            raise BrokerError("인증 재시도 대기 중입니다. 1분 후 새로고침하세요.")
        self._auth_retry_after = time.monotonic() + 60
        response = await self.client.post(
            "/oauth2/tokenP",
            json={
                "grant_type": "client_credentials",
                "appkey": self.settings.kis_app_key.get_secret_value(),
                "appsecret": self.settings.kis_app_secret.get_secret_value(),
            },
        )
        if response.status_code != 200:
            raise BrokerError("KIS 인증에 실패했습니다. 서버 환경 설정을 확인하세요.")
        token = Token.model_validate(response.json())
        self._token = token.access_token.get_secret_value()
        self._expires = time.monotonic() + token.expires_in - 60

    async def _page(
        self, market: str, params: dict[str, str], cont: str
    ) -> tuple[Envelope, bool]:
        await asyncio.sleep(max(0, 1.0 - (time.monotonic() - self._last_request)))
        domestic = market == "KRX"
        path = "domestic-stock" if domestic else "overseas-stock"
        self._last_request = time.monotonic()
        response = await self.client.get(
            f"/uapi/{path}/v1/trading/inquire-balance",
            params=params,
            headers={
                "authorization": f"Bearer {self._token}",
                "appkey": self.settings.kis_app_key.get_secret_value(),
                "appsecret": self.settings.kis_app_secret.get_secret_value(),
                "tr_id": "TTTC8434R" if domestic else "TTTS3012R",
                "custtype": "P",
                "tr_cont": cont,
            },
        )
        if response.status_code != 200:
            raise BrokerError("KIS 조회에 실패했습니다. 잠시 후 다시 시도하세요.")
        data = response.json()
        if not isinstance(data, dict) or data.get("rt_cd") != "0":
            raise BrokerError(
                "KIS가 조회를 거절했습니다. 계좌·서비스 상태를 확인하세요."
            )
        return Envelope.model_validate(data), response.headers.get("tr_cont") in (
            "M",
            "F",
        )

    async def _market(self, market: str, currency: str) -> MarketResult:
        size = "100" if market == "KRX" else "200"
        params = {
            "CANO": self.settings.kis_cano.get_secret_value(),
            "ACNT_PRDT_CD": self.settings.kis_acnt_prdt_cd.get_secret_value(),
            f"CTX_AREA_FK{size}": "",
            f"CTX_AREA_NK{size}": "",
        }
        if market == "KRX":
            params.update(
                AFHR_FLPR_YN="N",
                OFL_YN="",
                INQR_DVSN="02",
                UNPR_DVSN="01",
                FUND_STTL_ICLD_YN="N",
                FNCG_AMT_AUTO_RDPT_YN="N",
                PRCS_DVSN="00",
            )
        else:
            params.update(OVRS_EXCG_CD=market, TR_CRCY_CD=currency)
        holdings: dict[str, Holding] = {}
        cursors: set[tuple[str, str]] = set()
        cont = ""
        for _ in range(100):
            page, more = await self._page(market, params, cont)
            for row in page.output1:
                holding = normalize(row, market, currency)
                if holding.quantity == 0:
                    continue
                previous = holdings.get(holding.symbol)
                if previous is not None and previous != holding:
                    raise BrokerError(
                        "중복 종목의 잔고가 일치하지 않아 재조회가 필요합니다."
                    )
                holdings[holding.symbol] = holding
            if not more:
                return MarketResult(
                    market=market,
                    status="ok",
                    holdings=list(holdings.values()),
                    fetched_at=datetime.now(UTC),
                )
            cursor = (
                getattr(page, f"ctx_area_fk{size}").strip(),
                getattr(page, f"ctx_area_nk{size}").strip(),
            )
            if not any(cursor) or cursor in cursors:
                raise BrokerError("연속 조회가 완료되지 않았습니다. 다시 조회하세요.")
            cursors.add(cursor)
            params[f"CTX_AREA_FK{size}"], params[f"CTX_AREA_NK{size}"] = cursor
            cont = "N"
        raise BrokerError("연속 조회 한도를 초과했습니다.")

    async def portfolio(self) -> Portfolio:
        async with self._lock:
            if (
                self._cached
                and time.monotonic() - self._cached_at < self.settings.cache_seconds
            ):
                return self._cached
            try:
                await self._authenticate()
            except (httpx.HTTPError, ValidationError, ValueError) as exc:
                raise BrokerError("KIS 인증 응답을 확인할 수 없습니다.") from exc
            markets = []
            for market, currency in MARKETS:
                try:
                    result = await self._market(market, currency)
                except BrokerError as exc:
                    result = MarketResult(market=market, status="error", error=str(exc))
                except (httpx.HTTPError, ValidationError, ValueError):
                    result = MarketResult(
                        market=market,
                        status="error",
                        error="응답 지연 또는 잔고 데이터 검증 실패. 다시 조회하세요.",
                    )
                markets.append(result)
            self._cached = Portfolio(
                fetched_at=datetime.now(UTC), markets=markets, totals=summarize(markets)
            )
            self._cached_at = time.monotonic()
            return self._cached
