from __future__ import annotations

from datetime import date
from typing import Annotated, Literal, cast

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, ValidationError

from jusik.market_history_models import (
    Market,
    MarketResearchRequest,
    MarketResearchRun,
    anniversary_start,
)
from jusik.market_research_service import (
    MarketResearchConflict,
    MarketResearchNotFound,
    MarketResearchService,
)

router = APIRouter(prefix="/api/research/market", tags=["point-in-time research"])


class MarketResearchCreatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    market: Market
    end_date: date
    start_date: date | None = None
    stage: Literal["pilot", "final"] = "pilot"
    pilot_run_id: str | None = None


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
    request: Request, payload: MarketResearchCreatePayload
) -> MarketResearchRun:
    start_date = payload.start_date or anniversary_start(
        payload.end_date, years=1 if payload.stage == "pilot" else 3
    )
    try:
        validated = MarketResearchRequest(
            market=payload.market,
            start_date=start_date,
            end_date=payload.end_date,
            stage=payload.stage,
            pilot_run_id=payload.pilot_run_id,
        )
    except ValidationError:
        raise HTTPException(
            status_code=422, detail="invalid research request"
        ) from None
    try:
        return await service(request).create_run(validated)
    except MarketResearchNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except MarketResearchConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
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
