from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field

Money = Annotated[Decimal, Field(allow_inf_nan=False)]
Positive = Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]


class Holding(BaseModel):
    market: str
    symbol: str = Field(min_length=1)
    name: str
    currency: Literal["KRW", "USD", "HKD", "CNY", "JPY", "VND"]
    quantity: Positive
    average_price: Positive
    current_price: Positive
    cost: Positive
    value: Positive
    profit: Money
    return_pct: Money | None


class Total(BaseModel):
    currency: str
    cost: Money
    value: Money
    profit: Money
    return_pct: Money | None


class MarketResult(BaseModel):
    market: str
    status: Literal["ok", "error"]
    holdings: list[Holding] = Field(default_factory=list)
    error: str | None = None
    fetched_at: datetime | None = None


class Portfolio(BaseModel):
    source: Literal["live-account-snapshot"] = "live-account-snapshot"
    fetched_at: datetime
    markets: list[MarketResult]
    totals: list[Total]


def percentage(profit: Decimal, cost: Decimal) -> Decimal | None:
    if cost == 0:
        return None
    return (profit / cost * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def summarize(markets: list[MarketResult]) -> list[Total]:
    groups: dict[str, list[Holding]] = {}
    for market in markets:
        if market.status == "ok":
            for holding in market.holdings:
                groups.setdefault(holding.currency, []).append(holding)
    totals = []
    for currency, holdings in sorted(groups.items()):
        cost = sum((h.cost for h in holdings), Decimal(0))
        value = sum((h.value for h in holdings), Decimal(0))
        profit = sum((h.profit for h in holdings), Decimal(0))
        totals.append(
            Total(
                currency=currency,
                cost=cost,
                value=value,
                profit=profit,
                return_pct=percentage(profit, cost),
            )
        )
    return totals
