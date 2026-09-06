from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Response
from pydantic import ValidationError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from jusik.config import Settings
from jusik.kis import BrokerError, KisClient
from jusik.models import Portfolio


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        settings = Settings()
    except ValidationError:
        raise RuntimeError(
            "Invalid backend settings. Check .env.prod locally."
        ) from None
    async with httpx.AsyncClient(
        base_url=settings.kis_base_url,
        timeout=12,
        follow_redirects=False,
        trust_env=False,
    ) as client:
        app.state.kis = KisClient(settings, client)
        yield


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
        broker: KisClient = app.state.kis
        return await broker.portfolio()
    except BrokerError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from None
