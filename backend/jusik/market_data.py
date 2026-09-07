import time
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

import httpx
from pydantic import ValidationError

from jusik.config import RegisteredAccount
from jusik.kis import BrokerError, KisClient
from jusik.models import AccountResult, Fundamentals, Holding, MarketResult
from jusik.signals import with_advice

EXCHANGE_CODES = {
    "NASD": "NAS",
    "NYSE": "NYS",
    "AMEX": "AMS",
    "SEHK": "HKS",
    "TKSE": "TSE",
    "SHAA": "SHS",
    "SZAA": "SZS",
    "HASE": "HNX",
    "VNSE": "HSX",
}
US_EXCHANGES = ("NAS", "NYS", "AMS")
FUNDAMENTAL_ERROR = "기업가치 지표를 확인할 수 없습니다."


def optional_decimal(value: object) -> Decimal | None:
    if value in (None, "", "-"):
        return None
    try:
        parsed = Decimal(str(value).replace(",", ""))
    except (InvalidOperation, ValueError):
        return None
    return parsed if parsed.is_finite() else None


def optional_fundamental_decimal(value: object) -> Decimal | None:
    parsed = optional_decimal(value)
    return parsed if parsed != 0 else None


class MarketDataService:
    def __init__(self, kis: KisClient) -> None:
        self.kis = kis
        self._cache: dict[tuple[str, str], tuple[Fundamentals, float]] = {}

    async def _overseas_quote(
        self,
        account: RegisteredAccount,
        token: str,
        holding: Holding,
        exchanges: list[str],
    ) -> dict[str, object]:
        for exchange in exchanges:
            try:
                response = await self.kis._get(
                    account,
                    token,
                    "/uapi/overseas-price/v1/quotations/price-detail",
                    "HHDFS76200200",
                    {"AUTH": "", "EXCD": exchange, "SYMB": holding.symbol},
                )
                data = self.kis._accepted_json(response)
            except (BrokerError, httpx.HTTPError):
                continue
            output = data.get("output")
            if not isinstance(output, dict):
                continue
            returned_symbol = str(output.get("rsym") or "").strip().upper()
            returned_currency = str(output.get("curr") or "").strip().upper()
            last_price = optional_decimal(output.get("last"))
            expected_symbol = f"D{exchange}{holding.symbol}".upper()
            if (
                returned_symbol == expected_symbol
                and returned_currency == holding.currency
                and last_price is not None
                and last_price > 0
            ):
                return output
        raise ValueError("No quote matched the holding identity")

    async def _holding(
        self, account: RegisteredAccount, token: str, holding: Holding
    ) -> Fundamentals:
        cache_market = "US" if holding.market in {"US", "NASD"} else holding.market
        key = (cache_market, holding.symbol)
        cached = self._cache.get(key)
        if cached is not None:
            cached_value, cached_at = cached
            ttl = 86_400 if cached_value.status == "ok" else 300
            if time.monotonic() - cached_at < ttl:
                return cached_value
        now = datetime.now(UTC)
        try:
            if holding.market == "KRX":
                response = await self.kis._get(
                    account,
                    token,
                    "/uapi/domestic-stock/v1/quotations/inquire-price",
                    "FHKST01010100",
                    {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": holding.symbol},
                )
                data = self.kis._accepted_json(response)
                output = data.get("output")
                if not isinstance(output, dict):
                    raise ValueError("Missing output")
                instrument_parts = [
                    str(output.get(field) or "").strip()
                    for field in ("rprs_mrkt_kor_name", "bstp")
                ]
                instrument_type = (
                    " · ".join(part for part in instrument_parts if part) or None
                )
                result = Fundamentals(
                    status="ok",
                    per=optional_decimal(output.get("per")),
                    pbr=optional_decimal(output.get("pbr")),
                    eps=optional_decimal(output.get("eps")),
                    bps=optional_decimal(output.get("bps")),
                    instrument_type=instrument_type,
                    source="한국투자증권 KIS 현재가",
                    source_url="https://apiportal.koreainvestment.com/apiservice",
                    fetched_at=now,
                )
            else:
                exchange = EXCHANGE_CODES.get(holding.market)
                if holding.market in {"US", "NASD"}:
                    exchanges = list(US_EXCHANGES)
                elif exchange is not None:
                    exchanges = [exchange]
                else:
                    raise ValueError("Unknown exchange")
                output = await self._overseas_quote(account, token, holding, exchanges)
                result = Fundamentals(
                    status="ok",
                    per=optional_fundamental_decimal(output.get("perx")),
                    pbr=optional_fundamental_decimal(output.get("pbrx")),
                    eps=optional_fundamental_decimal(output.get("epsx")),
                    bps=optional_fundamental_decimal(output.get("bpsx")),
                    instrument_type=str(output.get("etyp_nm") or "").strip() or None,
                    source="한국투자증권 KIS 해외주식 현재가상세",
                    source_url="https://apiportal.koreainvestment.com/apiservice",
                    fetched_at=now,
                )
            if all(
                value is None
                for value in (result.per, result.pbr, result.eps, result.bps)
            ):
                result = result.model_copy(
                    update={"status": "unavailable", "error": FUNDAMENTAL_ERROR}
                )
        except (BrokerError, httpx.HTTPError, ValidationError, ValueError):
            result = Fundamentals(
                status="error", fetched_at=now, error=FUNDAMENTAL_ERROR
            )
        self._cache[key] = (result, time.monotonic())
        return result

    async def enrich(self, accounts: list[AccountResult]) -> list[AccountResult]:
        account = self.kis.settings.registered_accounts[0]
        try:
            token = await self.kis._authenticate(account)
        except (BrokerError, httpx.HTTPError, ValidationError, ValueError):
            token = None
        result: list[AccountResult] = []
        for broker_account in accounts:
            markets: list[MarketResult] = []
            for market in broker_account.markets:
                holdings: list[Holding] = []
                for holding in market.holdings:
                    holding = holding.model_copy(
                        update={"price_fetched_at": market.fetched_at}
                    )
                    fundamentals = (
                        await self._holding(account, token, holding)
                        if token is not None
                        else Fundamentals(status="error", error=FUNDAMENTAL_ERROR)
                    )
                    holdings.append(
                        with_advice(
                            holding.model_copy(update={"fundamentals": fundamentals})
                        )
                    )
                markets.append(market.model_copy(update={"holdings": holdings}))
            result.append(broker_account.model_copy(update={"markets": markets}))
        return result
