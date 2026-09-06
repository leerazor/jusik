import asyncio
import time
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

import httpx
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    ValidationError,
    field_validator,
)

from jusik.config import RegisteredAccount, Settings
from jusik.models import (
    AccountResult,
    AssetSummary,
    AssetSummaryResult,
    Holding,
    MarketResult,
    Portfolio,
    Positive,
    aggregate_net_assets,
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
MARKET_DATA_ERROR = "응답 지연 또는 잔고 데이터 검증 실패. 다시 조회하세요."
ASSET_DATA_ERROR = "계좌 자산 데이터 검증에 실패했습니다. 다시 조회하세요."


class BrokerError(Exception):
    """A sanitized error safe to display without broker response contents."""


class Token(BaseModel):
    access_token: SecretStr
    expires_in: int = Field(gt=60)


class BalanceEnvelope(BaseModel):
    model_config = ConfigDict(extra="ignore")

    rt_cd: str
    output1: list[dict[str, object]]
    ctx_area_fk100: str = ""
    ctx_area_nk100: str = ""
    ctx_area_fk200: str = ""
    ctx_area_nk200: str = ""


class AssetEnvelope(BaseModel):
    model_config = ConfigDict(extra="ignore")

    rt_cd: str
    output1: list[dict[str, object]]
    output2: dict[str, object]


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


class AssetRow(BaseModel):
    model_config = ConfigDict(extra="ignore")

    nass_tot_amt: Decimal | None = Field(default=None, allow_inf_nan=False)
    evlu_amt_smtl: Decimal | None = Field(default=None, allow_inf_nan=False)
    tot_dncl_amt: Decimal | None = Field(default=None, allow_inf_nan=False)
    evlu_pfls_amt_smtl: Decimal | None = Field(default=None, allow_inf_nan=False)
    ovrs_stck_evlu_amt1: Decimal | None = Field(default=None, allow_inf_nan=False)

    @field_validator("*", mode="before")
    @classmethod
    def blank_is_missing(cls, value: object) -> object:
        return None if value == "" else value


class TokenState(BaseModel):
    token: SecretStr
    expires_at: float


def normalize(row: dict[str, object], market: str, currency: str) -> Holding:
    if market == "KRX":
        domestic = DomesticRow.model_validate(row)
        return Holding(
            market=market,
            symbol=domestic.pdno,
            name=domestic.prdt_name,
            currency="KRW",
            quantity=domestic.hldg_qty,
            average_price=domestic.pchs_avg_pric,
            current_price=domestic.prpr,
            cost=domestic.pchs_amt,
            value=domestic.evlu_amt,
            profit=domestic.evlu_pfls_amt,
            return_pct=percentage(domestic.evlu_pfls_amt, domestic.pchs_amt),
        )
    overseas = OverseasRow.model_validate(row)
    if overseas.tr_crcy_cd != currency:
        raise BrokerError("응답 통화가 요청 통화와 다릅니다.")
    return Holding(
        market=market,
        symbol=overseas.ovrs_pdno,
        name=overseas.ovrs_item_name or overseas.ovrs_pdno,
        currency=overseas.tr_crcy_cd,
        quantity=overseas.ovrs_cblc_qty,
        average_price=overseas.pchs_avg_pric,
        current_price=overseas.now_pric2,
        cost=overseas.frcr_pchs_amt1,
        value=overseas.ovrs_stck_evlu_amt,
        profit=overseas.frcr_evlu_pfls_amt,
        return_pct=percentage(overseas.frcr_evlu_pfls_amt, overseas.frcr_pchs_amt1),
    )


class KisClient:
    def __init__(
        self,
        settings: Settings,
        client: httpx.AsyncClient,
        *,
        request_interval_seconds: float = 1.0,
    ) -> None:
        self.settings = settings
        self.client = client
        self._tokens: dict[tuple[str, str], TokenState] = {}
        self._auth_retry_after: dict[tuple[str, str], float] = {}
        self._last_request = 0.0
        self._request_interval_seconds = request_interval_seconds
        self._lock = asyncio.Lock()
        self._cached: Portfolio | None = None
        self._cached_at = 0.0

    async def _authenticate(self, account: RegisteredAccount) -> str:
        credentials = account.credential_key
        state = self._tokens.get(credentials)
        if state is not None and time.monotonic() < state.expires_at:
            return state.token.get_secret_value()
        if time.monotonic() < self._auth_retry_after.get(credentials, 0):
            raise BrokerError("인증 재시도 대기 중입니다. 1분 후 새로고침하세요.")
        self._auth_retry_after[credentials] = time.monotonic() + 60
        response = await self.client.post(
            "/oauth2/tokenP",
            json={
                "grant_type": "client_credentials",
                "appkey": account.app_key.get_secret_value(),
                "appsecret": account.app_secret.get_secret_value(),
            },
        )
        if response.status_code != 200:
            raise BrokerError("KIS 인증에 실패했습니다. 서버 환경 설정을 확인하세요.")
        token = Token.model_validate(response.json())
        self._tokens[credentials] = TokenState(
            token=token.access_token,
            expires_at=time.monotonic() + token.expires_in - 60,
        )
        return token.access_token.get_secret_value()

    async def _get(
        self,
        account: RegisteredAccount,
        token: str,
        path: str,
        tr_id: str,
        params: dict[str, str],
        cont: str = "",
    ) -> httpx.Response:
        await asyncio.sleep(
            max(
                0,
                self._request_interval_seconds
                - (time.monotonic() - self._last_request),
            )
        )
        self._last_request = time.monotonic()
        response = await self.client.get(
            path,
            params=params,
            headers={
                "authorization": f"Bearer {token}",
                "appkey": account.app_key.get_secret_value(),
                "appsecret": account.app_secret.get_secret_value(),
                "tr_id": tr_id,
                "custtype": "P",
                "tr_cont": cont,
            },
        )
        if response.status_code != 200:
            raise BrokerError("KIS 조회에 실패했습니다. 잠시 후 다시 시도하세요.")
        return response

    @staticmethod
    def _accepted_json(response: httpx.Response) -> dict[str, object]:
        data = response.json()
        if not isinstance(data, dict) or data.get("rt_cd") != "0":
            raise BrokerError(
                "KIS가 조회를 거절했습니다. 계좌·서비스 상태를 확인하세요."
            )
        return data

    async def _asset_summary(
        self, account: RegisteredAccount, token: str
    ) -> AssetSummaryResult:
        response = await self._get(
            account,
            token,
            "/uapi/domestic-stock/v1/trading/inquire-account-balance",
            "CTRP6548R",
            {
                "CANO": account.cano.get_secret_value(),
                "ACNT_PRDT_CD": account.acnt_prdt_cd.get_secret_value(),
                "INQR_DVSN_1": "",
                "BSPR_BF_DT_APLY_YN": "",
            },
        )
        envelope = AssetEnvelope.model_validate(self._accepted_json(response))
        row = AssetRow.model_validate(envelope.output2)
        return AssetSummaryResult(
            status="ok",
            summary=AssetSummary(
                net_asset=row.nass_tot_amt,
                total_evaluation=row.evlu_amt_smtl,
                cash=row.tot_dncl_amt,
                profit_loss=row.evlu_pfls_amt_smtl,
                overseas_evaluation=row.ovrs_stck_evlu_amt1,
            ),
            fetched_at=datetime.now(UTC),
        )

    async def _page(
        self,
        account: RegisteredAccount,
        token: str,
        market: str,
        params: dict[str, str],
        cont: str,
    ) -> tuple[BalanceEnvelope, bool]:
        domestic = market == "KRX"
        path = "domestic-stock" if domestic else "overseas-stock"
        response = await self._get(
            account,
            token,
            f"/uapi/{path}/v1/trading/inquire-balance",
            "TTTC8434R" if domestic else "TTTS3012R",
            params,
            cont,
        )
        envelope = BalanceEnvelope.model_validate(self._accepted_json(response))
        return envelope, response.headers.get("tr_cont") in ("M", "F")

    async def _market(
        self,
        account: RegisteredAccount,
        token: str,
        market: str,
        currency: str,
    ) -> MarketResult:
        size = "100" if market == "KRX" else "200"
        params = {
            "CANO": account.cano.get_secret_value(),
            "ACNT_PRDT_CD": account.acnt_prdt_cd.get_secret_value(),
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
            page, more = await self._page(account, token, market, params, cont)
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

    async def _account(self, account: RegisteredAccount) -> AccountResult:
        try:
            token = await self._authenticate(account)
        except BrokerError as exc:
            return self._failed_account(account, str(exc))
        except (httpx.HTTPError, ValidationError, ValueError):
            return self._failed_account(account, "KIS 인증 응답을 확인할 수 없습니다.")

        errors: list[str] = []
        try:
            assets = await self._asset_summary(account, token)
        except BrokerError as exc:
            assets = AssetSummaryResult(status="error", error=str(exc))
            errors.append(str(exc))
        except (httpx.HTTPError, ValidationError, ValueError):
            assets = AssetSummaryResult(status="error", error=ASSET_DATA_ERROR)
            errors.append(ASSET_DATA_ERROR)

        markets = []
        for market, currency in MARKETS:
            try:
                result = await self._market(account, token, market, currency)
            except BrokerError as exc:
                result = MarketResult(market=market, status="error", error=str(exc))
                errors.append(f"{market}: {exc}")
            except (httpx.HTTPError, ValidationError, ValueError):
                result = MarketResult(
                    market=market,
                    status="error",
                    error=MARKET_DATA_ERROR,
                )
                errors.append(f"{market}: {MARKET_DATA_ERROR}")
            markets.append(result)

        successful_parts = (1 if assets.status == "ok" else 0) + sum(
            market.status == "ok" for market in markets
        )
        if not errors:
            status: Literal["ok", "partial", "error"] = "ok"
        elif successful_parts:
            status = "partial"
        else:
            status = "error"
        return AccountResult(
            id=account.id,
            label=account.label,
            status=status,
            asset_summary=assets,
            markets=markets,
            totals=summarize(markets),
            errors=errors,
            fetched_at=datetime.now(UTC),
        )

    @staticmethod
    def _failed_account(account: RegisteredAccount, message: str) -> AccountResult:
        return AccountResult(
            id=account.id,
            label=account.label,
            status="error",
            asset_summary=AssetSummaryResult(status="error", error=message),
            markets=[
                MarketResult(market=market, status="error", error=message)
                for market, _ in MARKETS
            ],
            totals=[],
            errors=[message],
        )

    async def portfolio(self) -> Portfolio:
        async with self._lock:
            if (
                self._cached
                and time.monotonic() - self._cached_at < self.settings.cache_seconds
            ):
                return self._cached

            accounts = [
                await self._account(account)
                for account in self.settings.registered_accounts
            ]
            markets = [market for account in accounts for market in account.markets]
            self._cached = Portfolio(
                fetched_at=datetime.now(UTC),
                accounts=accounts,
                aggregate=aggregate_net_assets(accounts),
                totals=summarize(markets),
            )
            self._cached_at = time.monotonic()
            return self._cached
