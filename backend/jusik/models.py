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


class AssetSummary(BaseModel):
    currency: Literal["KRW"] = "KRW"
    net_asset: Money | None = None
    total_evaluation: Money | None = None
    cash: Money | None = None
    profit_loss: Money | None = None
    overseas_evaluation: Money | None = None
    estimated_deposit_assets: Money | None = None
    scope: Literal["account", "domestic"] = "account"


class AssetSummaryResult(BaseModel):
    status: Literal["ok", "error"]
    summary: AssetSummary | None = None
    error: str | None = None
    fetched_at: datetime | None = None


class MarketResult(BaseModel):
    market: str
    status: Literal["ok", "error"]
    holdings: list[Holding] = Field(default_factory=list)
    error: str | None = None
    fetched_at: datetime | None = None


class AccountResult(BaseModel):
    id: str
    label: str
    broker: Literal["kis", "kiwoom"] = "kis"
    status: Literal["ok", "partial", "error"]
    asset_summary: AssetSummaryResult
    markets: list[MarketResult]
    totals: list[Total]
    errors: list[str] = Field(default_factory=list)
    fetched_at: datetime | None = None


class AggregateSummary(BaseModel):
    currency: Literal["KRW"] = "KRW"
    net_asset: Money | None
    completeness: Literal["complete", "partial", "unavailable"]
    included_accounts: int = Field(ge=0)
    registered_accounts: int = Field(ge=1)


class Portfolio(BaseModel):
    source: Literal["live-registered-accounts-snapshot"] = (
        "live-registered-accounts-snapshot"
    )
    fetched_at: datetime
    accounts: list[AccountResult] = Field(min_length=1)
    aggregate: AggregateSummary
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


def aggregate_net_assets(accounts: list[AccountResult]) -> AggregateSummary:
    values = [
        account.asset_summary.summary.net_asset
        for account in accounts
        if account.asset_summary.status == "ok"
        and account.asset_summary.summary is not None
        and account.asset_summary.summary.net_asset is not None
    ]
    included = len(values)
    total = len(accounts)
    if included == 0:
        completeness: Literal["complete", "partial", "unavailable"] = "unavailable"
        net_asset = None
    elif included == total:
        completeness = "complete"
        net_asset = sum(values, Decimal(0))
    else:
        completeness = "partial"
        net_asset = sum(values, Decimal(0))
    return AggregateSummary(
        net_asset=net_asset,
        completeness=completeness,
        included_accounts=included,
        registered_accounts=total,
    )
