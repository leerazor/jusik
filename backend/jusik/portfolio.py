from jusik.kis import KisClient
from jusik.kiwoom import KiwoomClient
from jusik.models import Portfolio, aggregate_net_assets, summarize


def available_account_id(preferred: str, existing: set[str]) -> str:
    if preferred not in existing:
        return preferred
    suffix = 2
    while f"{preferred}-{suffix}" in existing:
        suffix += 1
    return f"{preferred}-{suffix}"


class PortfolioService:
    def __init__(self, kis: KisClient, kiwoom: KiwoomClient | None = None) -> None:
        self.kis = kis
        self.kiwoom = kiwoom

    async def portfolio(self) -> Portfolio:
        kis_portfolio = await self.kis.portfolio()
        if self.kiwoom is None:
            return kis_portfolio

        kiwoom_account = await self.kiwoom.account()
        accounts = [*kis_portfolio.accounts, kiwoom_account]
        markets = [market for account in accounts for market in account.markets]
        fetched_at = max(
            kis_portfolio.fetched_at,
            kiwoom_account.fetched_at or kis_portfolio.fetched_at,
        )
        return Portfolio(
            fetched_at=fetched_at,
            accounts=accounts,
            aggregate=aggregate_net_assets(accounts),
            totals=summarize(markets),
        )
