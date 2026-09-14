from urllib.parse import urlparse

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response

from jusik.investor_analysis import analyze, review_thesis
from jusik.investor_data import InvestorProvider
from jusik.investor_models import (
    DiscoveryResult,
    Instrument,
    InstrumentDetail,
    Market,
    Thesis,
    ThesisWrite,
)
from jusik.investor_store import InvestorStore, ThesisConflictError, ThesisNotFoundError

router = APIRouter(prefix="/api/investor", tags=["investor"])


def _services(request: Request) -> tuple[InvestorProvider, InvestorStore]:
    provider = getattr(request.app.state, "investor_provider", None)
    store = getattr(request.app.state, "investor_store", None)
    if provider is None or store is None:
        raise HTTPException(
            status_code=503, detail="투자자 조회 기능을 사용할 수 없습니다."
        )
    return provider, store


def _origin_allowed(origin: str | None) -> bool:
    if not origin:
        return True
    parsed = urlparse(origin)
    return parsed.scheme in {"http", "https"} and parsed.hostname in {
        "127.0.0.1",
        "localhost",
    }


def _identity_matches(left: Instrument, right: Instrument) -> bool:
    return (
        left.market == right.market
        and left.exchange == right.exchange
        and left.symbol == right.symbol
        and left.currency == right.currency
    )


def _canonical_payload(payload: ThesisWrite, detail: Instrument) -> ThesisWrite:
    if not _identity_matches(payload.instrument, detail):
        raise HTTPException(
            status_code=409,
            detail="종목 시장·거래소·코드·통화가 조회 결과와 다릅니다.",
        )
    if (
        payload.instrument.name != detail.name
        or payload.instrument.instrument_type != detail.instrument_type
    ):
        raise HTTPException(
            status_code=409,
            detail="종목 이름·유형이 최신 조회 결과와 다릅니다. 다시 조회하세요.",
        )
    return payload.model_copy(update={"instrument": detail})


@router.get("/candidates", response_model=DiscoveryResult)
async def candidates(
    market: Market, request: Request, response: Response
) -> DiscoveryResult:
    response.headers["Cache-Control"] = "no-store"
    provider, _ = _services(request)
    try:
        return await provider.discover(market)
    except Exception:
        raise HTTPException(
            status_code=502, detail="후보 자료를 확인할 수 없습니다."
        ) from None


@router.get("/instrument", response_model=InstrumentDetail)
async def instrument(
    market: Market,
    request: Request,
    symbol: str = Query(min_length=1, max_length=16, pattern=r"^[A-Za-z0-9.-]+$"),
    exchange: str | None = Query(
        default=None, max_length=12, pattern=r"^[A-Za-z0-9.-]+$"
    ),
) -> InstrumentDetail:
    provider, _ = _services(request)
    chosen_exchange = exchange or ("KRX" if market == "KR" else "NAS")
    try:
        return await provider.detail(
            Instrument(
                market=market,
                exchange=chosen_exchange,
                symbol=symbol,
                currency="KRW" if market == "KR" else "USD",
                name=symbol,
            )
        )
    except Exception:
        raise HTTPException(
            status_code=502, detail="상세 자료를 확인할 수 없습니다."
        ) from None


@router.get("/theses", response_model=list[Thesis])
async def thesis_list(request: Request) -> list[Thesis]:
    _, store = _services(request)
    return store.list()


@router.get("/theses/{thesis_id}", response_model=Thesis)
async def thesis_detail(thesis_id: str, request: Request) -> Thesis:
    provider, store = _services(request)
    try:
        stored = store.get(thesis_id)
        detail = await provider.detail(stored.instrument)
        if not _identity_matches(detail.instrument, stored.instrument):
            raise HTTPException(
                status_code=409,
                detail="최신 조회 결과의 종목 식별자가 저장 기록과 다릅니다.",
            )
        current_analysis = analyze(
            detail.instrument,
            detail.analysis.quote,
            detail.analysis.fundamentals,
            detail.analysis.trend,
            assumptions=stored.valuation,
            entry_kind=stored.entry_kind,
            now=detail.analysis.analyzed_at,
        )
        return stored.model_copy(
            update={
                "current_analysis": current_analysis,
                "review": review_thesis(stored, current_analysis),
            }
        )
    except ThesisNotFoundError:
        raise HTTPException(
            status_code=404, detail="저장된 thesis를 찾을 수 없습니다."
        ) from None
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=502, detail="최신 투자 자료를 확인할 수 없습니다."
        ) from None


@router.put("/theses", response_model=Thesis, status_code=200)
async def thesis_create_or_update(
    payload: ThesisWrite,
    request: Request,
    origin: str | None = Header(default=None),
) -> Thesis:
    if not _origin_allowed(origin):
        raise HTTPException(
            status_code=403,
            detail="허용된 로컬 브라우저 경계에서만 저장할 수 있습니다.",
        )
    provider, store = _services(request)
    try:
        detail = await provider.detail(payload.instrument)
        canonical = _canonical_payload(payload, detail.instrument)
        current_analysis = analyze(
            detail.instrument,
            detail.analysis.quote,
            detail.analysis.fundamentals,
            detail.analysis.trend,
            assumptions=canonical.valuation,
            entry_kind=canonical.entry_kind,
            now=detail.analysis.analyzed_at,
        )
        return store.save(
            None, canonical, detail.analysis, current_analysis=current_analysis
        )
    except ThesisConflictError:
        raise HTTPException(
            status_code=409, detail="thesis revision conflict"
        ) from None


@router.put("/theses/{thesis_id}", response_model=Thesis)
async def thesis_update(
    thesis_id: str,
    payload: ThesisWrite,
    request: Request,
    origin: str | None = Header(default=None),
) -> Thesis:
    if not _origin_allowed(origin):
        raise HTTPException(
            status_code=403,
            detail="허용된 로컬 브라우저 경계에서만 저장할 수 있습니다.",
        )
    provider, store = _services(request)
    try:
        current = store.get(thesis_id)
        if not _identity_matches(payload.instrument, current.instrument):
            raise HTTPException(
                status_code=409,
                detail="저장된 종목 식별자는 변경할 수 없습니다.",
            )
        detail = await provider.detail(current.instrument)
        if not _identity_matches(detail.instrument, current.instrument):
            raise HTTPException(
                status_code=409,
                detail="최신 조회 결과의 종목 식별자가 저장 기록과 다릅니다.",
            )
        canonical = _canonical_payload(payload, detail.instrument)
        current_analysis = analyze(
            detail.instrument,
            detail.analysis.quote,
            detail.analysis.fundamentals,
            detail.analysis.trend,
            assumptions=canonical.valuation,
            entry_kind=canonical.entry_kind,
            now=detail.analysis.analyzed_at,
        )
        return store.save(
            thesis_id,
            canonical,
            detail.analysis,
            current_analysis=current_analysis,
        )
    except ThesisConflictError:
        raise HTTPException(
            status_code=409, detail="thesis revision conflict"
        ) from None
    except ThesisNotFoundError:
        raise HTTPException(
            status_code=404, detail="저장된 thesis를 찾을 수 없습니다."
        ) from None
