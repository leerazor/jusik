import asyncio
import json
import time
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from jusik.models import (
    AccountResult,
    ExchangeRate,
    Holding,
    MarketResult,
    Total,
    percentage,
)

SUPPORTED_CURRENCIES = ("KRW", "USD", "HKD", "CNY", "JPY", "VND")
FX_ERROR = "환율을 확인할 수 없어 원화 환산값을 제공하지 못했습니다."


class RateResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    date: date
    base: str
    quote: str
    rate: Decimal = Field(gt=0, allow_inf_nan=False)


def krw(value: Decimal, rate: Decimal) -> Decimal:
    return (value * rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def convert_holding(holding: Holding, rate: ExchangeRate) -> Holding:
    assert rate.krw_per_unit is not None
    return holding.model_copy(
        update={
            "fx_rate": rate.krw_per_unit,
            "fx_source": rate.source,
            "fx_as_of": rate.as_of,
            "average_price_krw": krw(holding.average_price, rate.krw_per_unit),
            "current_price_krw": krw(holding.current_price, rate.krw_per_unit),
            "cost_krw": krw(holding.cost, rate.krw_per_unit),
            "value_krw": krw(holding.value, rate.krw_per_unit),
            "profit_krw": krw(holding.profit, rate.krw_per_unit),
        }
    )


def has_complete_conversion(holding: Holding) -> bool:
    return holding.fx_rate is not None and all(
        value is not None
        for value in (
            holding.average_price_krw,
            holding.current_price_krw,
            holding.cost_krw,
            holding.value_krw,
            holding.profit_krw,
        )
    )


def converted_total(holdings: list[Holding]) -> Total | None:
    converted = [holding for holding in holdings if holding.value_krw is not None]
    if not converted:
        return None
    cost = sum((holding.cost_krw or Decimal(0) for holding in converted), Decimal(0))
    value = sum((holding.value_krw or Decimal(0) for holding in converted), Decimal(0))
    profit = sum(
        (holding.profit_krw or Decimal(0) for holding in converted), Decimal(0)
    )
    return Total(
        currency="KRW",
        cost=cost,
        value=value,
        profit=profit,
        return_pct=percentage(profit, cost),
        cost_krw=cost,
        value_krw=value,
        profit_krw=profit,
    )


class FxService:
    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        cache_seconds: int = 21_600,
        max_concurrency: int = 3,
    ) -> None:
        self.client = client
        self.cache_seconds = cache_seconds
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._cache: dict[str, ExchangeRate] = {}
        self._cached_at: dict[str, float] = {}

    async def _rate(self, currency: str) -> ExchangeRate:
        now = datetime.now(UTC)
        if currency == "KRW":
            return ExchangeRate(
                currency="KRW",
                status="ok",
                krw_per_unit=Decimal(1),
                source="원화 기준",
                as_of=now.date(),
                fetched_at=now,
            )
        cached = self._cache.get(currency)
        if cached and time.monotonic() - self._cached_at[currency] < self.cache_seconds:
            return cached
        try:
            async with self._semaphore:
                response = await self.client.get(f"/v2/rate/{currency}/KRW")
            response.raise_for_status()
            raw = json.loads(response.text, parse_float=Decimal, parse_int=Decimal)
            parsed = RateResponse.model_validate(raw)
            if parsed.base != currency or parsed.quote != "KRW":
                raise ValueError("Unexpected currency pair")
            if parsed.date > now.date():
                raise ValueError("Future exchange-rate date")
            stale = parsed.date < (now - timedelta(days=5)).date()
            result = ExchangeRate(
                currency=currency,
                status="ok",
                krw_per_unit=parsed.rate,
                as_of=parsed.date,
                fetched_at=now,
                stale=stale,
            )
            self._cache[currency] = result
            self._cached_at[currency] = time.monotonic()
            return result
        except (httpx.HTTPError, json.JSONDecodeError, ValidationError, ValueError):
            if cached is not None:
                return cached.model_copy(update={"stale": True, "error": FX_ERROR})
            return ExchangeRate(
                currency=currency,
                status="error",
                fetched_at=now,
                error=FX_ERROR,
            )

    async def rates(self, currencies: set[str]) -> list[ExchangeRate]:
        requested = [
            currency for currency in SUPPORTED_CURRENCIES if currency in currencies
        ]
        return list(
            await asyncio.gather(*(self._rate(currency) for currency in requested))
        )

    async def convert_accounts(
        self, accounts: list[AccountResult]
    ) -> tuple[
        list[AccountResult],
        list[ExchangeRate],
        Total | None,
        str,
    ]:
        currencies = {
            holding.currency
            for account in accounts
            for market in account.markets
            for holding in market.holdings
            if not has_complete_conversion(holding)
        }
        rates = await self.rates(currencies | {"KRW"})
        values = {
            rate.currency: rate
            for rate in rates
            if rate.status == "ok" and rate.krw_per_unit is not None and not rate.stale
        }
        converted_accounts: list[AccountResult] = []
        all_holdings: list[Holding] = []
        for account in accounts:
            markets: list[MarketResult] = []
            for market in account.markets:
                holdings = [
                    holding
                    if has_complete_conversion(holding)
                    else (
                        convert_holding(holding, values[holding.currency])
                        if holding.currency in values
                        else holding
                    )
                    for holding in market.holdings
                ]
                all_holdings.extend(holdings)
                markets.append(market.model_copy(update={"holdings": holdings}))
            account_holdings = [
                holding for market in markets for holding in market.holdings
            ]
            account_total = (
                converted_total(account_holdings)
                if all(holding.value_krw is not None for holding in account_holdings)
                else None
            )
            converted_accounts.append(
                account.model_copy(
                    update={
                        "markets": markets,
                        "totals": [account_total] if account_total else [],
                    }
                )
            )
        converted_count = sum(holding.value_krw is not None for holding in all_holdings)
        if not all_holdings or converted_count == len(all_holdings):
            completeness = "complete"
        elif converted_count:
            completeness = "partial"
        else:
            completeness = "unavailable"
        total = converted_total(all_holdings) if completeness == "complete" else None
        return converted_accounts, rates, total, completeness
