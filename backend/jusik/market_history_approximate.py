"""Bounded, explicitly approximate historical market-data workflow.

This module accepts prepared provider responses and never falls back to the
current candidate universe.  Network backfills belong in a separate bounded
CLI job; the web application only reads a prepared response file.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Literal, Protocol, TypedDict, cast

from pydantic import BaseModel, ConfigDict, Field

from jusik.market_history_models import (
    CandidateEvidence,
    CapabilityName,
    Currency,
    FXObservation,
    Market,
    MarketBar,
    MarketHistorySnapshot,
    MarketReadiness,
    MarketResearchRequest,
    MarketResearchResult,
    PITMembership,
    ResearchEquityPoint,
    ResearchTrade,
    SourceName,
)
from jusik.research_market_calendar import (
    MarketCalendar,
    MarketSession,
    default_market_calendar,
)

MAX_SAMPLE_SYMBOLS = 100
MAX_UNIQUE_SYMBOLS = 400
APPROX_LOOKBACK_SESSIONS = 20
APPROX_TARGET_WEIGHT = Decimal("0.05")


class ApproximateProviderError(RuntimeError):
    """A prepared response is unavailable or violates the bounded contract."""


class ApproximateUniverseRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session: date
    symbol: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=120)
    exchange: str = Field(min_length=1, max_length=12)
    instrument_type: Literal["stock", "etf"] = "stock"
    currency: Currency
    available_at: datetime | None = None


class ApproximateBarRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session: date
    symbol: str = Field(min_length=1, max_length=20)
    exchange: str = Field(min_length=1, max_length=12)
    open: Decimal = Field(gt=0)
    high: Decimal = Field(gt=0)
    low: Decimal = Field(gt=0)
    close: Decimal = Field(gt=0)
    volume: Decimal = Field(ge=0)
    currency: Currency
    available_at: datetime | None = None


class ApproximateFXRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session: date
    krw_per_usd: Decimal = Field(gt=0)
    spread_rate: Decimal = Field(ge=0, le=Decimal("0.1"))
    available_at: datetime | None = None


class ApproximateDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    market: Market
    universe: tuple[ApproximateUniverseRow, ...]
    bars: tuple[ApproximateBarRow, ...]
    fx: tuple[ApproximateFXRow, ...] = ()
    source: SourceName = "approximate_file"
    simulated: bool = False
    normalization_version: str = Field(default="approx-v1", min_length=1, max_length=40)


@dataclass(frozen=True)
class ApproximateProviderResponse:
    dataset: ApproximateDataset
    raw_content: bytes


class HistoricalDateUniverseProvider(Protocol):
    source_name: SourceName
    simulated: bool

    @property
    def available(self) -> bool: ...

    async def fetch(
        self, market: Market, start: date, end: date
    ) -> ApproximateProviderResponse: ...


class HistoricalBarProvider(Protocol):
    source_name: Literal["yahoo"]


class HistoricalFXProvider(Protocol):
    source_name: Literal["fred"]


class JsonApproximateProvider:
    """Read one bounded provider response prepared by the backfill CLI."""

    def __init__(
        self,
        path: Path,
        *,
        source_name: SourceName = "approximate_file",
        simulated: bool = False,
    ) -> None:
        self.path = path
        self.source_name = source_name
        self.simulated = simulated

    @property
    def available(self) -> bool:
        return self.path.is_file()

    async def fetch(
        self, market: Market, start: date, end: date
    ) -> ApproximateProviderResponse:
        if not self.available:
            raise ApproximateProviderError(
                f"prepared approximate response is unavailable for {market}"
            )
        try:
            raw = self.path.read_bytes()
            dataset = ApproximateDataset.model_validate(json.loads(raw))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise ApproximateProviderError(
                "prepared approximate response is invalid"
            ) from exc
        if dataset.market != market:
            raise ApproximateProviderError(
                "prepared response market does not match request"
            )
        if any(row.session > end for row in dataset.universe):
            raise ApproximateProviderError("universe response exceeds requested period")
        if any(row.session > end for row in dataset.bars):
            raise ApproximateProviderError("bar response exceeds requested period")
        return ApproximateProviderResponse(dataset=dataset, raw_content=raw)


class KRXDateListProvider(JsonApproximateProvider):
    """Prepared KRX/public date-list response; no key means unavailable."""

    def __init__(self, path: Path) -> None:
        super().__init__(path, source_name="krx")


class AlphaVantageListingStatusProvider(JsonApproximateProvider):
    """Prepared LISTING_STATUS(date=...) response from Alpha Vantage."""

    def __init__(self, path: Path) -> None:
        super().__init__(path, source_name="alpha_vantage")


def _hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode()
    ).hexdigest()


@dataclass(frozen=True)
class ApproximatePool:
    rows: tuple[ApproximateUniverseRow, ...]
    contract_hash: str
    unique_symbols: int
    sampled_symbols: int


def deterministic_pool(
    rows: tuple[ApproximateUniverseRow, ...],
    *,
    market: Market,
    pool_end: date,
    seed: int = 20260914,
) -> ApproximatePool:
    """Select at most 100 stable symbols from at most 400 unique candidates."""
    if not rows:
        raise ApproximateProviderError("historical universe is empty")
    if any(row.currency != ("KRW" if market == "KR" else "USD") for row in rows):
        raise ApproximateProviderError("historical universe currency is invalid")
    unique = sorted({row.symbol for row in rows})
    bounded = sorted(
        unique,
        key=lambda symbol: hashlib.sha256(
            f"{seed}:{market}:{symbol}".encode()
        ).hexdigest(),
    )[:MAX_UNIQUE_SYMBOLS]
    sampled = bounded[:MAX_SAMPLE_SYMBOLS]
    sampled_set = set(sampled)
    selected = tuple(row for row in rows if row.symbol in sampled_set)
    contract_hash = _hash(
        {
            "version": "approximate-pool-v1",
            "market": market,
            "pool_end": pool_end.isoformat(),
            "seed": seed,
            "source_unique_symbols": len(unique),
            "bounded_unique_symbols": len(bounded),
            "sampled_symbols": sampled,
        }
    )
    return ApproximatePool(
        rows=selected,
        contract_hash=contract_hash,
        unique_symbols=len(unique),
        sampled_symbols=len(sampled),
    )


def _session(calendar: MarketCalendar, exchange: str, session: date) -> MarketSession:
    lookup = calendar.lookup(exchange, session)
    if lookup.session is None:
        raise ApproximateProviderError(f"calendar session unavailable: {session}")
    return lookup.session


class ApproximateMarketHistorySource:
    """Prepared-file source that emits a clearly approximate snapshot."""

    def __init__(
        self,
        provider: HistoricalDateUniverseProvider,
        *,
        calendar: MarketCalendar | None = None,
    ) -> None:
        self.provider = provider
        self.calendar = calendar or default_market_calendar()

    def readiness(self, market: Market, checked_at: datetime) -> MarketReadiness:
        detail = (
            "준비된 날짜별 표본 자료를 사용합니다. PIT 검증 자료가 아닙니다."
            if self.provider.available
            else (
                "KRX/Alpha Vantage 키 또는 무료 근사 자료 캐시가 없어 "
                "CLI 백필이 필요합니다."
            )
        )
        names = (
            ("credentials", "provider response file is prepared"),
            ("entitlement", "historical entitlement is approximate"),
            ("calendar", "bundled exchange calendar is available"),
            ("membership", detail),
            ("bars", detail),
            ("actions", "dividend and delisting history is excluded or unknown"),
            ("fx", "FRED DEXKOUS observations are required for US"),
            ("policy", "approximate sample policy is configured"),
        )
        from jusik.market_history_models import Capability

        capabilities = tuple(
            Capability(
                name=cast(CapabilityName, name),
                status="partial"
                if name in {"entitlement", "actions", "policy"}
                else ("ready" if self.provider.available else "missing"),
                detail=value,
            )
            for name, value in names
        )
        return MarketReadiness(
            market=market,
            checked_at=checked_at,
            capabilities=capabilities,
            ready=False,
            simulated=self.provider.simulated,
            research_grade="approximate",
        )

    async def collect(self, request: MarketResearchRequest) -> MarketHistorySnapshot:
        if request.research_grade != "approximate":
            raise ApproximateProviderError(
                "approximate source requires approximate request"
            )
        response = await self.provider.fetch(
            request.market, request.start_date, request.end_date
        )
        dataset = response.dataset
        if dataset.source != self.provider.source_name:
            dataset = dataset.model_copy(update={"source": self.provider.source_name})
        pool = deterministic_pool(
            dataset.universe, market=request.market, pool_end=request.end_date
        )
        captured = datetime.now(UTC)
        memberships: list[PITMembership] = []
        for row in pool.rows:
            market_session = _session(self.calendar, row.exchange, row.session)
            memberships.append(
                PITMembership(
                    stable_id=f"approx:{row.session}:{row.symbol}",
                    market=request.market,
                    exchange=row.exchange,
                    symbol=row.symbol,
                    name=row.name,
                    instrument_type=row.instrument_type,
                    currency=row.currency,
                    valid_from=row.session,
                    valid_to=row.session,
                    available_at=row.available_at or market_session.close_at,
                    captured_at=captured,
                    source=dataset.source,
                    source_hash=_hash(row.model_dump(mode="json")),
                    normalization_version=dataset.normalization_version,
                )
            )
        bars: list[MarketBar] = []
        selected_symbols = {row.symbol for row in pool.rows}
        for bar_row in dataset.bars:
            if bar_row.symbol not in selected_symbols:
                continue
            market_session = _session(self.calendar, bar_row.exchange, bar_row.session)
            bars.append(
                MarketBar(
                    market=request.market,
                    exchange=bar_row.exchange,
                    symbol=bar_row.symbol,
                    session=bar_row.session,
                    open=bar_row.open,
                    high=bar_row.high,
                    low=bar_row.low,
                    close=bar_row.close,
                    volume=bar_row.volume,
                    currency=bar_row.currency,
                    captured_at=captured,
                    available_at=bar_row.available_at or market_session.close_at,
                    source="yahoo"
                    if dataset.source == "alpha_vantage"
                    else dataset.source,
                    source_hash=_hash(bar_row.model_dump(mode="json")),
                    normalization_version=dataset.normalization_version,
                )
            )
        fx = tuple(
            FXObservation(
                session=fx_row.session,
                pair="USDKRW",
                krw_per_usd=fx_row.krw_per_usd,
                spread_rate=fx_row.spread_rate,
                available_at=fx_row.available_at or captured,
                captured_at=captured,
                source="fred",
                source_hash=_hash(fx_row.model_dump(mode="json")),
            )
            for fx_row in dataset.fx
        )
        from jusik.market_history_models import RawArtifact

        artifact = RawArtifact.from_bytes(
            response.raw_content,
            content_type="application/json",
            captured_at=captured,
            source=dataset.source,
        )
        return MarketHistorySnapshot(
            market=request.market,
            requested_start=request.start_date,
            requested_end=request.end_date,
            captured_at=captured,
            memberships=tuple(memberships),
            bars=tuple(bars),
            actions=(),
            actions_complete=False,
            fx=fx,
            source_artifacts=(artifact,),
            completeness="incomplete",
            missing_ranges=("corporate_actions:dividends_excluded",),
            normalization_version=dataset.normalization_version,
            evaluation_start=request.start_date,
            research_grade="approximate",
            pool_contract_hash=pool.contract_hash,
        )


class FixtureApproximateMarketHistorySource:
    """Deterministic simulated approximate source for the isolated fixture app."""

    available = True
    simulated = True

    def __init__(self) -> None:
        from jusik.market_history_sources import FixtureMarketHistorySource

        self.fixture = FixtureMarketHistorySource()

    def readiness(self, market: Market, checked_at: datetime) -> MarketReadiness:
        readiness = self.fixture.readiness(market, checked_at)

        capabilities = tuple(
            capability.model_copy(
                update={
                    "status": "partial"
                    if capability.name == "policy"
                    else capability.status,
                    "detail": (
                        "합성 표본으로 계산하며 strict PIT 검증 결과가 아닙니다."
                        if capability.name == "policy"
                        else capability.detail
                    ),
                }
            )
            for capability in readiness.capabilities
        )
        return readiness.model_copy(
            update={
                "capabilities": capabilities,
                "ready": False,
                "research_grade": "approximate",
            }
        )

    async def collect(self, request: MarketResearchRequest) -> MarketHistorySnapshot:
        strict_request = request.model_copy(update={"research_grade": "strict"})
        snapshot = await self.fixture.collect(strict_request)
        symbols = sorted(
            item.symbol
            for item in snapshot.memberships
            if item.instrument_type == "stock"
        )
        pool_hash = _hash(
            {
                "version": "fixture-approximate-pool-v1",
                "market": request.market,
                "pool_end": request.end_date.isoformat(),
                "symbols": symbols,
            }
        )
        return snapshot.model_copy(
            update={
                "research_grade": "approximate",
                "pool_contract_hash": pool_hash,
                "missing_ranges": (
                    *snapshot.missing_ranges,
                    "corporate_actions:dividends_excluded",
                ),
                "completeness": "incomplete",
            }
        )


def _days(
    calendar: MarketCalendar, market: Market, start: date, end: date
) -> list[date]:
    exchange = "KSC" if market == "KR" else "NMS"
    output: list[date] = []
    cursor = start
    while cursor <= end:
        if calendar.lookup(exchange, cursor).session is not None:
            output.append(cursor)
        cursor += timedelta(days=1)
    return output


class _ApproximateResultBase(TypedDict):
    market: Market
    request: MarketResearchRequest
    readiness: MarketReadiness
    input_hash: str | None
    policy_hash: str | None
    stage: Literal["pilot", "final", "legacy"]
    pilot_run_id: str | None
    data_contract_hash: str | None
    warmup_sessions: tuple[date, ...]
    research_grade: Literal["approximate"]
    pool_contract_hash: str | None


def run_approximate_market_research(
    snapshot: MarketHistorySnapshot,
    request: MarketResearchRequest,
    readiness: MarketReadiness,
    calendar: MarketCalendar,
    *,
    policy_hash: str | None = None,
) -> MarketResearchResult:
    """Run the bounded sample strategy without claiming strict PIT validity."""
    base: _ApproximateResultBase = {
        "market": request.market,
        "request": request,
        "readiness": readiness,
        "input_hash": snapshot.input_hash,
        "policy_hash": policy_hash,
        "stage": request.stage,
        "pilot_run_id": request.pilot_run_id,
        "data_contract_hash": snapshot.data_contract_hash,
        "warmup_sessions": (),
        "research_grade": "approximate",
        "pool_contract_hash": snapshot.pool_contract_hash,
    }
    if (
        request.research_grade != "approximate"
        or snapshot.research_grade != "approximate"
        or readiness.research_grade != "approximate"
    ):
        return MarketResearchResult(
            **base,
            status="insufficient",
            completeness="incomplete",
            limitations=("근사 연구 자료 계약이 일치하지 않아 계산하지 않습니다.",),
            metrics={},
        )
    sessions = _days(calendar, request.market, request.start_date, request.end_date)
    bars = {(item.symbol, item.session): item for item in snapshot.bars}
    fx = {item.session: item for item in snapshot.fx}
    evidence: list[CandidateEvidence] = []
    trades: list[ResearchTrade] = []
    equity: list[ResearchEquityPoint] = []
    limitations = [
        "무료 근사 자료의 날짜별 표본이며 strict PIT 검증 결과가 아닙니다.",
        "배당·상장폐지 자료가 제외되거나 불완전해 보유 청산을 추정하지 않습니다.",
    ]
    blockers: list[str] = []
    positions: dict[str, int] = {}
    first_fx = fx.get(sessions[0]) if sessions and request.market == "US" else None
    if request.market == "US" and first_fx is None:
        blockers.append("fx:initial funding")
    if request.market == "KR":
        cash = request.initial_cash_krw
    elif first_fx is not None:
        cash = request.initial_cash_krw / (
            first_fx.krw_per_usd * (1 + first_fx.spread_rate)
        )
    else:
        cash = Decimal(0)
    marks: dict[str, Decimal] = {}
    pending: list[tuple[str, date, int]] = []
    missing_bars = 0
    for index, session in enumerate(sessions):
        current_fx = fx.get(session) if request.market == "US" else None
        if request.market == "US" and current_fx is None:
            blockers.append(f"fx:{session}")
            continue
        for symbol, signal_session, rank in pending:
            fill = bars.get((symbol, session))
            if fill is None:
                limitations.append(
                    f"다음 시가 자료 없음으로 진입을 건너뜀: {symbol} {session}"
                )
                continue
            quantity = max(1, int((cash * APPROX_TARGET_WEIGHT) / fill.open))
            notional = fill.open * quantity
            if notional > cash:
                continue
            cash -= notional
            positions[symbol] = quantity
            marks[symbol] = fill.close
            trades.append(
                ResearchTrade(
                    session=session,
                    signal_session=signal_session,
                    fill_session=session,
                    symbol=symbol,
                    side="buy",
                    quantity=quantity,
                    currency="KRW" if request.market == "KR" else "USD",
                    market_open=fill.open,
                    fill_price=fill.open,
                    notional=notional,
                    fee=Decimal(0),
                    tax=Decimal(0),
                    rationale="근사 표본의 거래량 상위 20·breakout 조건 다음 시가 진입",
                )
            )
        pending.clear()
        ranked = sorted(
            (
                row
                for row in snapshot.memberships
                if row.is_valid_on(session)
                and row.instrument_type == "stock"
                and (row.symbol, session) in bars
            ),
            key=lambda row: (-bars[(row.symbol, session)].volume, row.symbol),
        )[:20]
        if not ranked:
            blockers.append(f"historical sample missing:{session}")
            continue
        for rank, membership in enumerate(ranked, start=1):
            bar = bars[(membership.symbol, session)]
            evidence.append(
                CandidateEvidence(
                    session=session,
                    symbol=membership.symbol,
                    rank=rank,
                    volume=bar.volume,
                    eligible=True,
                    membership_available_at=membership.available_at,
                    bar_available_at=bar.available_at,
                )
            )
            prior = [
                bars.get((membership.symbol, prior_session))
                for prior_session in sessions[
                    max(0, index - APPROX_LOOKBACK_SESSIONS) : index
                ]
            ]
            if (
                len(prior) == APPROX_LOOKBACK_SESSIONS
                and all(item is not None for item in prior)
                and index + 1 < len(sessions)
                and bar.close > max(item.close for item in prior if item is not None)
                and bar.volume
                > sum((item.volume for item in prior if item is not None), Decimal())
                / APPROX_LOOKBACK_SESSIONS
                and membership.symbol not in positions
            ):
                pending.append((membership.symbol, session, rank))
        for symbol in positions:
            mark = bars.get((symbol, session))
            if mark is None:
                missing_bars += 1
                limitations.append(
                    f"보유 종목 일봉 누락, 마지막 가격으로만 표시: {symbol} {session}"
                )
            else:
                marks[symbol] = mark.close
        invested = sum(
            (marks[symbol] * quantity for symbol, quantity in positions.items()),
            Decimal(),
        )
        rate = current_fx.krw_per_usd if current_fx else Decimal(1)
        nav_native = cash + invested
        nav = nav_native * rate if request.market == "US" else nav_native
        equity.append(
            ResearchEquityPoint(
                session=session,
                cash_krw=cash * rate if request.market == "US" else cash,
                cash_native=cash,
                invested_krw=invested * rate if request.market == "US" else invested,
                nav_krw=nav,
                fx_krw_per_usd=rate,
                drawdown_pct=Decimal(0),
            )
        )
    if not sessions:
        blockers.append("calendar coverage unavailable")
    if blockers:
        limitations.extend(sorted(set(blockers)))
        return MarketResearchResult(
            **base,
            status="insufficient",
            completeness="incomplete",
            candidate_evidence=tuple(evidence),
            trades=tuple(trades),
            equity=tuple(equity),
            limitations=tuple(limitations),
            metrics={},
        )
    final_nav = equity[-1].nav_krw if equity else request.initial_cash_krw
    return MarketResearchResult(
        **base,
        status="approximate",
        completeness="approximate",
        candidate_evidence=tuple(evidence),
        trades=tuple(trades),
        equity=tuple(equity),
        limitations=tuple(limitations),
        metrics={
            "coverage_sessions": Decimal(len(equity)),
            "sampled_candidate_count": Decimal(len({item.symbol for item in evidence})),
            "missing_held_bars": Decimal(missing_bars),
            "final_nav_krw": final_nav,
        },
    )
