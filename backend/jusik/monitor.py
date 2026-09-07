import asyncio
from contextlib import suppress
from datetime import UTC, datetime, timedelta

from jusik.alert_store import AlertStore
from jusik.fx import FxService
from jusik.market_data import MarketDataService
from jusik.models import MarketIntelligence, MonitorStatus, Portfolio
from jusik.news import NewsService
from jusik.portfolio import PortfolioService
from jusik.signals import with_advice
from jusik.telegram import TelegramNotifier


class DashboardService:
    def __init__(
        self,
        portfolio: PortfolioService,
        fx: FxService,
        market_data: MarketDataService,
        news: NewsService,
        alerts: AlertStore,
        *,
        interval_seconds: int,
        telegram: TelegramNotifier | None = None,
    ) -> None:
        self.portfolio = portfolio
        self.fx = fx
        self.market_data = market_data
        self.news = news
        self.alerts = alerts
        self.interval_seconds = interval_seconds
        self.telegram = telegram
        self._latest_intelligence = MarketIntelligence()
        self._latest_portfolio: Portfolio | None = None
        self._last_checked_at: datetime | None = None
        self._last_success_at: datetime | None = None
        self._next_check_at: datetime | None = None
        self._consecutive_failures = 0
        self._error: str | None = None
        self._lock = asyncio.Lock()
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task

    async def _refresh_news(self) -> None:
        self._latest_intelligence = await self.news.intelligence()

    async def _loop(self) -> None:
        while not self._stop.is_set():
            await asyncio.gather(
                self.snapshot(), self._refresh_news(), return_exceptions=True
            )
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.interval_seconds)
            except TimeoutError:
                continue

    async def snapshot(self) -> Portfolio:
        async with self._lock:
            try:
                base = await self.portfolio.portfolio()
                accounts, rates, total, conversion = await self.fx.convert_accounts(
                    base.accounts
                )
                accounts = await self.market_data.enrich(accounts)
                accounts = [
                    account.model_copy(
                        update={
                            "markets": [
                                market.model_copy(
                                    update={
                                        "holdings": [
                                            with_advice(holding)
                                            for holding in market.holdings
                                        ]
                                    }
                                )
                                for market in account.markets
                            ]
                        }
                    )
                    for account in accounts
                ]
                for account in accounts:
                    for market in account.markets:
                        for holding in market.holdings:
                            alert = self.alerts.record(account.id, holding)
                            if alert is not None and self.telegram is not None:
                                delivery = await self.telegram.send(alert)
                                self.alerts.update_delivery(alert.id, delivery)
                self._last_checked_at = datetime.now(UTC)
                self._last_success_at = self._last_checked_at
                self._next_check_at = self._last_checked_at + timedelta(
                    seconds=self.interval_seconds
                )
                self._consecutive_failures = 0
                self._error = None
                result = base.model_copy(
                    update={
                        "accounts": accounts,
                        "totals": [total] if total else [],
                        "exchange_rates": rates,
                        "alerts": self.alerts.recent(),
                        "intelligence": self._latest_intelligence,
                        "monitor": MonitorStatus(
                            interval_seconds=self.interval_seconds,
                            telegram_configured=self.telegram is not None,
                            last_checked_at=self._last_checked_at,
                            last_success_at=self._last_success_at,
                            next_check_at=self._next_check_at,
                            consecutive_failures=self._consecutive_failures,
                        ),
                        "holding_conversion_completeness": conversion,
                    }
                )
                self._latest_portfolio = result
                return result
            except Exception:
                self._error = "모니터 갱신에 실패했습니다."
                self._consecutive_failures += 1
                self._last_checked_at = datetime.now(UTC)
                self._next_check_at = self._last_checked_at + timedelta(
                    seconds=self.interval_seconds
                )
                if self._latest_portfolio is not None:
                    return self._latest_portfolio.model_copy(
                        update={
                            "intelligence": self._latest_intelligence,
                            "monitor": MonitorStatus(
                                interval_seconds=self.interval_seconds,
                                telegram_configured=self.telegram is not None,
                                last_checked_at=self._last_checked_at,
                                last_success_at=self._last_success_at,
                                next_check_at=self._next_check_at,
                                consecutive_failures=self._consecutive_failures,
                                error=self._error,
                            ),
                        }
                    )
                raise
