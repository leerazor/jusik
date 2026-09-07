import asyncio
import time
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal
from zoneinfo import ZoneInfo

import httpx
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    ValidationError,
    field_validator,
)

from jusik.kis import BrokerError
from jusik.kiwoom_config import KiwoomSettings
from jusik.models import (
    AccountResult,
    AssetSummary,
    AssetSummaryResult,
    Holding,
    MarketResult,
    Money,
    Positive,
    percentage,
    summarize,
)

KIWOOM_MARKETS = ("KRX", "US")
KIWOOM_ACCOUNT_ERROR = "키움 계좌를 확인할 수 없습니다. 계좌 설정을 확인하세요."
KIWOOM_AUTH_ERROR = "키움 인증에 실패했습니다. 서버 환경 설정을 확인하세요."
KIWOOM_TERMINAL_ERROR = (
    "키움 지정단말기 인증에 실패했습니다. 키움 REST API 설정을 확인하세요."
)
KIWOOM_DATA_ERROR = "키움 잔고 데이터 검증에 실패했습니다. 다시 조회하세요."
KIWOOM_QUERY_ERROR = "키움 조회에 실패했습니다. 잠시 후 다시 시도하세요."
KST = ZoneInfo("Asia/Seoul")


class TokenResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    return_code: int
    token: SecretStr
    token_type: str
    expires_dt: str = Field(pattern=r"^\d{14}$")


class AccountResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    return_code: int
    acctNo: str = Field(pattern=r"^\d{10}$")


class DomesticEnvelope(BaseModel):
    model_config = ConfigDict(extra="ignore")

    return_code: int
    tot_pur_amt: Money
    tot_evlt_amt: Money
    tot_evlt_pl: Money
    prsm_dpst_aset_amt: Money
    tot_loan_amt: Positive | None = None
    acnt_evlt_remn_indv_tot: list[dict[str, object]]

    @field_validator("tot_loan_amt", mode="before")
    @classmethod
    def blank_debt_is_missing(cls, value: object) -> object:
        return None if value == "" else value


class DomesticRow(BaseModel):
    model_config = ConfigDict(extra="ignore")

    stk_cd: str = Field(min_length=2)
    stk_nm: str = Field(min_length=1)
    rmnd_qty: Positive
    pur_pric: Positive
    cur_prc: Money
    pur_amt: Positive
    evlt_amt: Positive
    evltv_prft: Money
    crd_tp: str
    crd_loan_dt: str


class CashResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    return_code: int
    entr: Money


class ForeignCashRow(BaseModel):
    model_config = ConfigDict(extra="ignore")

    crnc_code: str
    fc_entra: Money
    fc_ch_uncla: Positive
    fc_etc_loana: Positive


class ForeignCashEnvelope(BaseModel):
    model_config = ConfigDict(extra="ignore")

    return_code: int
    krw_entra: Money
    ch_uncla: Positive
    etc_loana: Positive
    result_list: list[ForeignCashRow]


class CurrencyValuationRow(BaseModel):
    model_config = ConfigDict(extra="ignore")

    crnc_code: str
    fx_entr: Money
    evlt_amt: Money
    crnc_rt: Positive
    chg_entr: Money
    chg_evlt_amt: Money


class CurrencyValuationEnvelope(BaseModel):
    model_config = ConfigDict(extra="ignore")

    return_code: int
    won_entr: Money
    aset_evlt_amt: Money
    result_list: list[CurrencyValuationRow]


class OverseasEnvelope(BaseModel):
    model_config = ConfigDict(extra="ignore")

    return_code: int
    result_list: list[dict[str, object]]


class OverseasRow(BaseModel):
    model_config = ConfigDict(extra="ignore")

    crnc_code: Literal["USD"]
    stk_cd: str = Field(min_length=1)
    frgn_stk_nm: str = Field(min_length=1)
    poss_qty: Positive
    frgn_stk_book_uv: Positive
    now_pric: Money
    frgn_stk_book_amt: Positive
    evlt_amt: Positive
    pl_amt: Money


class TokenState(BaseModel):
    token: SecretStr
    expires_at: datetime


class DomesticData(BaseModel):
    holdings: list[Holding]
    total_evaluation: Money
    profit_loss: Money
    estimated_deposit_assets: Money
    debt: Positive | None


class OverseasAssets(BaseModel):
    cash_krw: Money
    evaluation_krw: Money
    debt_krw: Money
    rates: dict[str, Decimal]


def _domestic_symbol(value: str) -> str:
    symbol = value.strip()
    if len(symbol) > 1 and symbol[0] in {"A", "J", "Q"}:
        symbol = symbol[1:]
    if not symbol:
        raise ValueError("Domestic symbol must not be blank.")
    return symbol


def _domestic_holding(rows: list[DomesticRow], symbol: str) -> Holding:
    quantity = sum((row.rmnd_qty for row in rows), Decimal(0))
    cost = sum((row.pur_amt for row in rows), Decimal(0))
    value = sum((row.evlt_amt for row in rows), Decimal(0))
    profit = sum((row.evltv_prft for row in rows), Decimal(0))
    current_value = sum((abs(row.cur_prc) * row.rmnd_qty for row in rows), Decimal(0))
    if quantity <= 0:
        raise ValueError("Domestic holding quantity must be positive.")
    return Holding(
        market="KRX",
        symbol=symbol,
        name=rows[0].stk_nm,
        currency="KRW",
        quantity=quantity,
        average_price=cost / quantity,
        current_price=current_value / quantity,
        cost=cost,
        value=value,
        profit=profit,
        return_pct=percentage(profit, cost),
    )


class KiwoomClient:
    def __init__(
        self,
        settings: KiwoomSettings,
        client: httpx.AsyncClient,
        *,
        account_id: str = "kiwoom",
        request_interval_seconds: float = 1.0,
    ) -> None:
        self.settings = settings
        self.client = client
        self.account_id = account_id
        self._request_interval_seconds = request_interval_seconds
        self._last_request = 0.0
        self._request_lock = asyncio.Lock()
        self._account_lock = asyncio.Lock()
        self._token: TokenState | None = None
        self._auth_retry_after = 0.0
        self._cached: AccountResult | None = None
        self._cached_at = 0.0

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    async def _post(
        self,
        path: str,
        api_id: str,
        body: dict[str, str],
        *,
        token: str | None = None,
        continuation: tuple[str, str] | None = None,
    ) -> httpx.Response:
        headers = {"api-id": api_id}
        if token is not None:
            headers["authorization"] = f"Bearer {token}"
        if continuation is not None:
            headers["cont-yn"], headers["next-key"] = continuation
        async with self._request_lock:
            await asyncio.sleep(
                max(
                    0,
                    self._request_interval_seconds
                    - (time.monotonic() - self._last_request),
                )
            )
            self._last_request = time.monotonic()
            response = await self.client.post(path, json=body, headers=headers)
        if response.status_code != 200:
            raise BrokerError(KIWOOM_QUERY_ERROR)
        return response

    @staticmethod
    def _accepted_json(response: httpx.Response) -> dict[str, object]:
        data = response.json()
        if not isinstance(data, dict):
            raise BrokerError(KIWOOM_DATA_ERROR)
        code = data.get("return_code")
        if not isinstance(code, int) or isinstance(code, bool) or code != 0:
            raise BrokerError(KIWOOM_QUERY_ERROR)
        return data

    async def _authenticate(self) -> str:
        now = self._now()
        if (
            self._token is not None
            and now + timedelta(seconds=60) < self._token.expires_at
        ):
            return self._token.token.get_secret_value()
        if time.monotonic() < self._auth_retry_after:
            raise BrokerError("인증 재시도 대기 중입니다. 1분 후 새로고침하세요.")
        self._auth_retry_after = time.monotonic() + 60
        response = await self._post(
            "/oauth2/token",
            "au10001",
            {
                "grant_type": "client_credentials",
                "appkey": self.settings.app_key.get_secret_value(),
                "secretkey": self.settings.app_secret.get_secret_value(),
            },
        )
        data = response.json()
        if not isinstance(data, dict):
            raise BrokerError(KIWOOM_AUTH_ERROR)
        code = data.get("return_code")
        if not isinstance(code, int) or isinstance(code, bool) or code != 0:
            message = data.get("return_msg")
            if isinstance(message, str) and "8050" in message:
                raise BrokerError(KIWOOM_TERMINAL_ERROR)
            raise BrokerError(KIWOOM_AUTH_ERROR)
        try:
            token = TokenResponse.model_validate(data)
            expires_at = (
                datetime.strptime(token.expires_dt, "%Y%m%d%H%M%S")
                .replace(tzinfo=KST)
                .astimezone(UTC)
            )
        except (ValidationError, ValueError) as exc:
            raise BrokerError(KIWOOM_AUTH_ERROR) from exc
        if token.token_type.lower() != "bearer":
            raise BrokerError(KIWOOM_AUTH_ERROR)
        if expires_at <= now + timedelta(seconds=60):
            raise BrokerError(KIWOOM_AUTH_ERROR)
        self._token = TokenState(token=token.token, expires_at=expires_at)
        self._auth_retry_after = 0.0
        return token.token.get_secret_value()

    async def _pages(
        self, path: str, api_id: str, body: dict[str, str], token: str
    ) -> list[dict[str, object]]:
        pages: list[dict[str, object]] = []
        continuation: tuple[str, str] | None = None
        cursors: set[str] = set()
        for _ in range(100):
            response = await self._post(
                path,
                api_id,
                body,
                token=token,
                continuation=continuation,
            )
            pages.append(self._accepted_json(response))
            if response.headers.get("cont-yn", "N").upper() != "Y":
                return pages
            next_key = response.headers.get("next-key", "").strip()
            if not next_key or next_key in cursors:
                raise BrokerError("연속 조회가 완료되지 않았습니다. 다시 조회하세요.")
            cursors.add(next_key)
            continuation = ("Y", next_key)
        raise BrokerError("연속 조회 한도를 초과했습니다.")

    async def _verify_account(self, token: str) -> None:
        response = await self._post("/api/dostk/acnt", "ka00001", {}, token=token)
        account = AccountResponse.model_validate(self._accepted_json(response))
        configured_account = self.settings.account_number
        if configured_account is not None and account.acctNo != configured_account:
            raise BrokerError(KIWOOM_ACCOUNT_ERROR)

    async def _domestic(self, token: str) -> DomesticData:
        raw_pages = await self._pages(
            "/api/dostk/acnt",
            "kt00018",
            {"qry_tp": "1", "dmst_stex_tp": "KRX"},
            token,
        )
        pages = [DomesticEnvelope.model_validate(page) for page in raw_pages]
        totals = {
            (
                page.tot_pur_amt,
                page.tot_evlt_amt,
                page.tot_evlt_pl,
                page.prsm_dpst_aset_amt,
                page.tot_loan_amt,
            )
            for page in pages
        }
        if len(totals) != 1:
            raise BrokerError("연속 조회의 계좌 합계가 일치하지 않습니다.")

        lots: dict[tuple[object, ...], DomesticRow] = {}
        for page in pages:
            for raw_row in page.acnt_evlt_remn_indv_tot:
                row = DomesticRow.model_validate(raw_row)
                if row.rmnd_qty == 0:
                    continue
                symbol = _domestic_symbol(row.stk_cd)
                identity = (
                    symbol,
                    row.crd_tp,
                    row.crd_loan_dt,
                    row.pur_pric,
                    row.rmnd_qty,
                    row.pur_amt,
                )
                previous = lots.get(identity)
                if previous is not None and previous != row:
                    raise BrokerError(
                        "중복 국내 잔고가 일치하지 않아 재조회가 필요합니다."
                    )
                lots[identity] = row

        grouped: dict[str, list[DomesticRow]] = {}
        for row in lots.values():
            grouped.setdefault(_domestic_symbol(row.stk_cd), []).append(row)
        holdings = [
            _domestic_holding(rows, symbol) for symbol, rows in sorted(grouped.items())
        ]
        first = pages[0]
        return DomesticData(
            holdings=holdings,
            total_evaluation=first.tot_evlt_amt,
            profit_loss=first.tot_evlt_pl,
            estimated_deposit_assets=first.prsm_dpst_aset_amt,
            debt=first.tot_loan_amt,
        )

    async def _cash(self, token: str) -> Decimal:
        response = await self._post(
            "/api/dostk/acnt", "kt00001", {"qry_tp": "2"}, token=token
        )
        return CashResponse.model_validate(self._accepted_json(response)).entr

    async def _us(self, token: str) -> list[Holding]:
        holdings: dict[str, Holding] = {}
        pages = await self._pages("/api/us/acnt", "ust21070", {}, token)
        for page in pages:
            envelope = OverseasEnvelope.model_validate(page)
            for raw_row in envelope.result_list:
                row = OverseasRow.model_validate(raw_row)
                if row.poss_qty == 0:
                    continue
                symbol = row.stk_cd.strip()
                name = row.frgn_stk_nm.strip() or symbol
                holding = Holding(
                    market="US",
                    symbol=symbol,
                    name=name,
                    currency="USD",
                    quantity=row.poss_qty,
                    average_price=row.frgn_stk_book_uv,
                    current_price=abs(row.now_pric),
                    cost=row.frgn_stk_book_amt,
                    value=row.evlt_amt,
                    profit=row.pl_amt,
                    return_pct=percentage(row.pl_amt, row.frgn_stk_book_amt),
                )
                previous = holdings.get(holding.symbol)
                if previous is not None and previous != holding:
                    raise BrokerError(
                        "중복 미국 잔고가 일치하지 않아 재조회가 필요합니다."
                    )
                holdings[holding.symbol] = holding
        return list(holdings.values())

    async def _overseas_assets(self, token: str) -> OverseasAssets:
        cash_pages = [
            ForeignCashEnvelope.model_validate(page)
            for page in await self._pages("/api/us/acnt", "ust21110", {}, token)
        ]
        valuation_pages = [
            CurrencyValuationEnvelope.model_validate(page)
            for page in await self._pages(
                "/api/us/acnt",
                "ust21120",
                {"cmsn_incl_tp": "1", "exrt_tp": "0"},
                token,
            )
        ]
        cash_totals = {
            (page.krw_entra, page.ch_uncla, page.etc_loana) for page in cash_pages
        }
        valuation_totals = {
            (page.won_entr, page.aset_evlt_amt) for page in valuation_pages
        }
        if len(cash_totals) != 1 or len(valuation_totals) != 1:
            raise BrokerError("키움 해외 자산 연속 조회 합계가 일치하지 않습니다.")
        cash_page = cash_pages[0]
        valuation = valuation_pages[0]
        valuation_by_currency: dict[str, CurrencyValuationRow] = {}
        for valuation_page in valuation_pages:
            for valuation_row in valuation_page.result_list:
                previous_valuation = valuation_by_currency.get(valuation_row.crnc_code)
                if (
                    previous_valuation is not None
                    and previous_valuation != valuation_row
                ):
                    raise BrokerError(
                        "키움 통화별 평가금이 중복되어 일치하지 않습니다."
                    )
                valuation_by_currency[valuation_row.crnc_code] = valuation_row
        cash_by_currency: dict[str, ForeignCashRow] = {}
        for current_cash_page in cash_pages:
            for cash_row in current_cash_page.result_list:
                previous_cash = cash_by_currency.get(cash_row.crnc_code)
                if previous_cash is not None and previous_cash != cash_row:
                    raise BrokerError(
                        "키움 통화별 예수금이 중복되어 일치하지 않습니다."
                    )
                cash_by_currency[cash_row.crnc_code] = cash_row
        rates = {
            row.crnc_code: row.crnc_rt
            for row in valuation_by_currency.values()
            if row.crnc_rt > 0
        }
        foreign_cash = sum(
            (row.chg_entr for row in valuation_by_currency.values()), Decimal(0)
        )
        foreign_evaluation = sum(
            (row.chg_evlt_amt for row in valuation_by_currency.values()), Decimal(0)
        )
        converted_assets = valuation.won_entr + foreign_cash + foreign_evaluation
        if converted_assets != valuation.aset_evlt_amt:
            raise BrokerError("키움 해외 원화추정자산의 구성금액이 일치하지 않습니다.")
        foreign_debt = Decimal(0)
        for cash_row in cash_by_currency.values():
            rate = rates.get(cash_row.crnc_code)
            if rate is None and (
                cash_row.fc_ch_uncla != 0 or cash_row.fc_etc_loana != 0
            ):
                raise BrokerError("키움 외화 부채 환율을 확인할 수 없습니다.")
            if rate is not None:
                foreign_debt += (cash_row.fc_ch_uncla + cash_row.fc_etc_loana) * rate
        return OverseasAssets(
            cash_krw=valuation.won_entr + foreign_cash,
            evaluation_krw=foreign_evaluation,
            debt_krw=cash_page.ch_uncla + cash_page.etc_loana + foreign_debt,
            rates=rates,
        )

    async def _fetch_account(self) -> AccountResult:
        try:
            token = await self._authenticate()
            await self._verify_account(token)
        except BrokerError as exc:
            return self._failed_account(str(exc))
        except (httpx.HTTPError, ValidationError, ValueError):
            return self._failed_account(KIWOOM_ACCOUNT_ERROR)

        errors: list[str] = []
        domestic: DomesticData | None = None
        cash: Decimal | None = None
        overseas_assets: OverseasAssets | None = None
        try:
            domestic = await self._domestic(token)
            domestic_market = MarketResult(
                market="KRX",
                status="ok",
                holdings=domestic.holdings,
                fetched_at=self._now(),
            )
        except BrokerError as exc:
            domestic_market = MarketResult(market="KRX", status="error", error=str(exc))
            errors.append(f"KRX: {exc}")
        except (httpx.HTTPError, ValidationError, ValueError):
            domestic_market = MarketResult(
                market="KRX", status="error", error=KIWOOM_DATA_ERROR
            )
            errors.append(f"KRX: {KIWOOM_DATA_ERROR}")

        try:
            cash = await self._cash(token)
        except BrokerError as exc:
            errors.append(f"예수금: {exc}")
        except (httpx.HTTPError, ValidationError, ValueError):
            errors.append(f"예수금: {KIWOOM_DATA_ERROR}")

        try:
            us_holdings = await self._us(token)
            us_market = MarketResult(
                market="US", status="ok", holdings=us_holdings, fetched_at=self._now()
            )
        except BrokerError as exc:
            us_market = MarketResult(market="US", status="error", error=str(exc))
            errors.append(f"US: {exc}")
        except (httpx.HTTPError, ValidationError, ValueError):
            us_market = MarketResult(
                market="US", status="error", error=KIWOOM_DATA_ERROR
            )
            errors.append(f"US: {KIWOOM_DATA_ERROR}")

        try:
            overseas_assets = await self._overseas_assets(token)
        except BrokerError as exc:
            errors.append(f"해외 자산: {exc}")
        except (httpx.HTTPError, ValidationError, ValueError):
            errors.append(f"해외 자산: {KIWOOM_DATA_ERROR}")
        if overseas_assets is not None:
            errors = [error for error in errors if not error.startswith("예수금:")]

        if overseas_assets is not None:
            converted_us = []
            for holding in us_market.holdings:
                rate = overseas_assets.rates.get(holding.currency)
                if rate is None:
                    converted_us.append(holding)
                    continue
                converted_us.append(
                    holding.model_copy(
                        update={
                            "fx_rate": rate,
                            "fx_source": "키움 계좌 기준환율",
                            "average_price_krw": (
                                holding.average_price * rate
                            ).quantize(Decimal("1"), rounding=ROUND_HALF_UP),
                            "current_price_krw": (
                                holding.current_price * rate
                            ).quantize(Decimal("1"), rounding=ROUND_HALF_UP),
                            "cost_krw": (holding.cost * rate).quantize(
                                Decimal("1"), rounding=ROUND_HALF_UP
                            ),
                            "value_krw": (holding.value * rate).quantize(
                                Decimal("1"), rounding=ROUND_HALF_UP
                            ),
                            "profit_krw": (holding.profit * rate).quantize(
                                Decimal("1"), rounding=ROUND_HALF_UP
                            ),
                        }
                    )
                )
            us_market = us_market.model_copy(update={"holdings": converted_us})

        net_asset = None
        debt = None
        overseas_evaluation = None
        if (
            domestic is not None
            and domestic.debt is not None
            and overseas_assets is not None
        ):
            debt = domestic.debt + overseas_assets.debt_krw
            overseas_evaluation = overseas_assets.evaluation_krw
            net_asset = (
                domestic.total_evaluation
                + overseas_assets.cash_krw
                + overseas_assets.evaluation_krw
                - debt
            )

        summary = AssetSummary(
            net_asset=net_asset,
            total_evaluation=(domestic.total_evaluation if domestic else None),
            cash=(overseas_assets.cash_krw if overseas_assets is not None else cash),
            profit_loss=(domestic.profit_loss if domestic else None),
            overseas_evaluation=overseas_evaluation,
            estimated_deposit_assets=(
                domestic.estimated_deposit_assets if domestic else None
            ),
            debt=debt,
            scope="estimated_account" if net_asset is not None else "domestic",
            basis=(
                "국내주식 평가 + 원화·외화 예수금 + 해외주식 원화평가 - 총부채"
                if net_asset is not None
                else "키움 국내 추정예탁자산"
            ),
            exchange_rates=(overseas_assets.rates if overseas_assets else {}),
            asset_source="키움증권 계좌 원화평가 API",
        )
        asset_errors = [error for error in errors if not error.startswith("US:")]
        assets = AssetSummaryResult(
            status="error" if asset_errors else "ok",
            summary=summary,
            error=asset_errors[0] if asset_errors else None,
            fetched_at=self._now(),
        )
        markets = [domestic_market, us_market]
        successful_parts = (
            (1 if domestic is not None else 0)
            + (1 if cash is not None else 0)
            + (1 if us_market.status == "ok" else 0)
            + (1 if overseas_assets is not None else 0)
        )
        if not errors:
            status: Literal["ok", "partial", "error"] = "ok"
        elif successful_parts:
            status = "partial"
        else:
            status = "error"
        return AccountResult(
            id=self.account_id,
            label="키움증권 계좌",
            broker="kiwoom",
            status=status,
            asset_summary=assets,
            markets=markets,
            totals=summarize(markets),
            errors=errors,
            fetched_at=self._now(),
        )

    def _failed_account(self, message: str) -> AccountResult:
        return AccountResult(
            id=self.account_id,
            label="키움증권 계좌",
            broker="kiwoom",
            status="error",
            asset_summary=AssetSummaryResult(status="error", error=message),
            markets=[
                MarketResult(market=market, status="error", error=message)
                for market in KIWOOM_MARKETS
            ],
            totals=[],
            errors=[message],
        )

    async def account(self) -> AccountResult:
        async with self._account_lock:
            if (
                self._cached is not None
                and time.monotonic() - self._cached_at < self.settings.cache_seconds
            ):
                return self._cached
            self._cached = await self._fetch_account()
            self._cached_at = time.monotonic()
            return self._cached
