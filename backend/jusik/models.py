from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field, PlainSerializer


def fixed_decimal(value: Decimal) -> str:
    return format(value, "f")


Money = Annotated[
    Decimal,
    Field(allow_inf_nan=False),
    PlainSerializer(fixed_decimal, return_type=str, when_used="json"),
]
Positive = Annotated[
    Decimal,
    Field(ge=0, allow_inf_nan=False),
    PlainSerializer(fixed_decimal, return_type=str, when_used="json"),
]


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
    fx_rate: Money | None = None
    fx_source: str | None = None
    fx_as_of: date | None = None
    average_price_krw: Money | None = None
    current_price_krw: Money | None = None
    cost_krw: Money | None = None
    value_krw: Money | None = None
    profit_krw: Money | None = None
    fundamentals: "Fundamentals" = Field(default_factory=lambda: Fundamentals())
    advice: "InvestmentAdvice" = Field(default_factory=lambda: InvestmentAdvice())
    price_fetched_at: datetime | None = None


class Total(BaseModel):
    currency: str
    cost: Money
    value: Money
    profit: Money
    return_pct: Money | None
    cost_krw: Money | None = None
    value_krw: Money | None = None
    profit_krw: Money | None = None


class Fundamentals(BaseModel):
    status: Literal["ok", "unavailable", "error"] = "unavailable"
    per: Money | None = None
    pbr: Money | None = None
    eps: Money | None = None
    bps: Money | None = None
    instrument_type: str | None = None
    source: str | None = None
    source_url: str | None = None
    fetched_at: datetime | None = None
    error: str | None = None


class InvestmentAdvice(BaseModel):
    signal: Literal["buy_review", "hold", "sell_review", "insufficient"] = (
        "insufficient"
    )
    label: str = "판단 보류"
    reasons: list[str] = Field(default_factory=list)
    rule_version: str = "v1"


class ExchangeRate(BaseModel):
    currency: Literal["KRW", "USD", "HKD", "CNY", "JPY", "VND"]
    krw_per_unit: Money | None = None
    status: Literal["ok", "error"]
    source: str = "Frankfurter 일별 기준환율"
    source_url: str = "https://frankfurter.dev/"
    as_of: date | None = None
    fetched_at: datetime
    stale: bool = False
    error: str | None = None


class Alert(BaseModel):
    id: int
    account_id: str
    market: str
    symbol: str
    name: str
    signal: Literal["buy_review", "sell_review"]
    title: str
    message: str
    created_at: datetime
    delivery: Literal["in_app", "telegram_sent", "telegram_failed", "telegram_unknown"]


class NewsItem(BaseModel):
    id: str
    category: Literal[
        "korea_rate",
        "us_rate",
        "geopolitics",
        "truth_social",
        "truth_social_post",
    ]
    title: str
    url: str
    source: str
    published_at: datetime | None = None
    assessment: str
    original_url: str | None = None
    excerpt: str | None = None


class SourceStatus(BaseModel):
    id: str
    label: str
    status: Literal["ok", "error"]
    source_url: str
    fetched_at: datetime | None = None
    stale: bool = False
    error: str | None = None


class MarketIntelligence(BaseModel):
    korea_base_rate: Money | None = None
    korea_rate_as_of: date | None = None
    us_target_rate: str | None = None
    us_rate_as_of: date | None = None
    news: list[NewsItem] = Field(default_factory=list)
    sources: list[SourceStatus] = Field(default_factory=list)
    fetched_at: datetime | None = None


class MonitorStatus(BaseModel):
    enabled: bool = True
    interval_seconds: int = 300
    telegram_configured: bool = False
    last_checked_at: datetime | None = None
    last_success_at: datetime | None = None
    next_check_at: datetime | None = None
    consecutive_failures: int = Field(default=0, ge=0)
    error: str | None = None


class AssetSummary(BaseModel):
    currency: Literal["KRW"] = "KRW"
    net_asset: Money | None = None
    total_evaluation: Money | None = None
    cash: Money | None = None
    profit_loss: Money | None = None
    overseas_evaluation: Money | None = None
    estimated_deposit_assets: Money | None = None
    debt: Money | None = None
    scope: Literal["account", "domestic", "estimated_account"] = "account"
    basis: str = "증권사 제공 원화 순자산"
    exchange_rates: dict[str, Money] = Field(default_factory=dict)
    asset_source: str = "증권사 계좌 API"


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
    exchange_rates: list[ExchangeRate] = Field(default_factory=list)
    alerts: list[Alert] = Field(default_factory=list)
    intelligence: MarketIntelligence = Field(default_factory=MarketIntelligence)
    monitor: MonitorStatus = Field(default_factory=MonitorStatus)
    holding_conversion_completeness: Literal["complete", "partial", "unavailable"] = (
        "complete"
    )


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
        and account.asset_summary.summary.scope != "domestic"
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
