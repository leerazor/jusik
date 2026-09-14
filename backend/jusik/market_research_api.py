from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, HTTPException, Query, Request, Response, status

from jusik.market_history_models import (
    Market,
    MarketResearchRequest,
    MarketResearchRun,
)
from jusik.market_research_service import MarketResearchService

router = APIRouter(prefix="/api/research/market", tags=["point-in-time research"])


def service(request: Request) -> MarketResearchService:
    configured = getattr(request.app.state, "market_research_service", None)
    if not isinstance(configured, MarketResearchService):
        raise HTTPException(status_code=503, detail="market research unavailable")
    return configured


@router.get("/status")
@router.get("/readiness")
async def market_status(
    request: Request,
    market: Annotated[str | None, Query(pattern="^(KR|US)$")] = None,
) -> object:
    configured = service(request)
    markets = [market] if market else ["KR", "US"]
    return [configured.readiness(cast("Market", item)) for item in markets]


@router.post(
    "/runs", response_model=MarketResearchRun, status_code=status.HTTP_202_ACCEPTED
)
async def create_market_run(
    request: Request, payload: MarketResearchRequest
) -> MarketResearchRun:
    try:
        return await service(request).create_run(payload)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from None


@router.get("/runs", response_model=list[MarketResearchRun])
async def list_market_runs(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[MarketResearchRun]:
    return service(request).store.list_runs(limit)


@router.get("/runs/{run_id}", response_model=MarketResearchRun)
async def get_market_run(request: Request, run_id: str) -> MarketResearchRun:
    try:
        return service(request).store.get_run(run_id)
    except KeyError:
        raise HTTPException(
            status_code=404, detail="market research run not found"
        ) from None


@router.get("/artifacts/{artifact_id}")
async def get_market_artifact(request: Request, artifact_id: str) -> Response:
    try:
        content, content_type = service(request).store.get_artifact(artifact_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="artifact not found") from None
    return Response(content=content, media_type=content_type)
