from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Response
from pydantic import ValidationError
from pydantic_settings import SettingsError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from jusik.alert_store import AlertStore
from jusik.config import Settings
from jusik.fx import FxService
from jusik.kis import BrokerError, KisClient
from jusik.kiwoom import KiwoomClient
from jusik.kiwoom_config import load_kiwoom_settings
from jusik.market_data import MarketDataService
from jusik.models import Portfolio
from jusik.monitor import DashboardService
from jusik.news import NewsService
from jusik.portfolio import PortfolioService, available_account_id
from jusik.telegram import TelegramNotifier


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        settings = Settings()
        kiwoom_settings = load_kiwoom_settings()
    except (SettingsError, ValidationError):
        raise RuntimeError(
            "Invalid backend settings. Check local environment files."
        ) from None
    async with AsyncExitStack() as stack:
        kis_http = await stack.enter_async_context(
            httpx.AsyncClient(
                base_url=settings.kis_base_url,
                timeout=12,
                follow_redirects=False,
                trust_env=False,
            )
        )
        kis = KisClient(settings, kis_http)
        kiwoom = None
        if kiwoom_settings is not None:
            kiwoom_http = await stack.enter_async_context(
                httpx.AsyncClient(
                    base_url=kiwoom_settings.base_url,
                    timeout=12,
                    follow_redirects=False,
                    trust_env=False,
                )
            )
            account_id = available_account_id(
                "kiwoom", {account.id for account in settings.registered_accounts}
            )
            kiwoom = KiwoomClient(kiwoom_settings, kiwoom_http, account_id=account_id)
        app.state.portfolio = PortfolioService(kis, kiwoom)
        public_http = await stack.enter_async_context(
            httpx.AsyncClient(timeout=10, follow_redirects=False, trust_env=False)
        )
        fx_http = await stack.enter_async_context(
            httpx.AsyncClient(
                base_url="https://api.frankfurter.dev",
                timeout=10,
                follow_redirects=False,
                trust_env=False,
            )
        )
        telegram = None
        if settings.telegram_enabled:
            assert settings.telegram_bot_token is not None
            assert settings.telegram_chat_id is not None
            telegram_http = await stack.enter_async_context(
                httpx.AsyncClient(
                    base_url="https://api.telegram.org",
                    timeout=8,
                    follow_redirects=False,
                    trust_env=False,
                )
            )
            telegram = TelegramNotifier(
                telegram_http,
                settings.telegram_bot_token,
                settings.telegram_chat_id,
            )
        dashboard = DashboardService(
            app.state.portfolio,
            FxService(fx_http),
            MarketDataService(kis),
            NewsService(public_http),
            AlertStore(settings.alert_db_path),
            interval_seconds=settings.monitor_interval_seconds,
            telegram=telegram,
        )
        app.state.dashboard = dashboard
        dashboard.start()
        try:
            yield
        finally:
            await dashboard.stop()


app = FastAPI(title="Jusik read-only portfolio", lifespan=lifespan)
app.add_middleware(
    TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"]
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/portfolio", response_model=Portfolio)
async def portfolio(response: Response) -> Portfolio:
    response.headers["Cache-Control"] = "no-store"
    try:
        service: DashboardService = app.state.dashboard
        return await service.snapshot()
    except BrokerError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from None
