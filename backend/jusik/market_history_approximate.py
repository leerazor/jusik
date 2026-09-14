"""Bounded, explicitly approximate historical market-data workflow.

This module accepts prepared provider responses and never falls back to the
current candidate universe.  The CLI imports and validates a prepared response
file; network collection is intentionally outside this bounded workflow.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal, Protocol, cast

from pydantic import BaseModel, ConfigDict, Field

from jusik.market_history_models import (
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
    SourceName,
)
from jusik.market_research_strategy import run_market_research
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
    observation_date: date | None = None
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
    bar_source: Literal["krx", "yahoo"] = "yahoo"
    fx_source: Literal["fred"] = "fred"
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
    source_name: Literal["krx", "yahoo"]


class HistoricalFXProvider(Protocol):
    source_name: Literal["fred"]


class JsonApproximateProvider:
    """Read one bounded provider response prepared by the import CLI."""

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

    def cached_dataset(self, market: Market) -> ApproximateDataset | None:
        """Validate the cached envelope before exposing readiness as usable."""
        if not self.available:
            return None
        try:
            dataset = ApproximateDataset.model_validate(
                json.loads(self.path.read_bytes())
            )
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
            return None
        if dataset.market != market or not dataset.universe or not dataset.bars:
            return None
        if market == "US" and not dataset.fx:
            return None
        if not self._valid_provenance(dataset):
            return None
        if (
            self.source_name != "approximate_file"
            and dataset.source != self.source_name
        ):
            return None
        return dataset

    def _valid_provenance(self, dataset: ApproximateDataset) -> bool:
        return (
            dataset.source in {"approximate_file", "krx", "alpha_vantage"}
            and dataset.simulated == self.simulated
            and (
                self.source_name == "approximate_file"
                or dataset.source == self.source_name
            )
        )

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
        if any(row.session > end for row in dataset.fx):
            raise ApproximateProviderError("FX response exceeds requested period")
        if not self._valid_provenance(dataset):
            raise ApproximateProviderError("prepared response provenance is invalid")
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
        cached_dataset = (
            self.provider.cached_dataset(market)
            if isinstance(self.provider, JsonApproximateProvider)
            else None
        )
        has_cached_data = cached_dataset is not None
        has_invalid_file = self.provider.available and not has_cached_data
        if has_cached_data:
            detail = (
                "검증된 준비 파일의 날짜별 표본 자료를 사용합니다. "
                "PIT 검증 자료가 아닙니다."
            )
        elif has_invalid_file:
            detail = (
                "준비 파일은 있지만 시장·provenance·형식 검증에 실패했습니다. "
                "import-file로 검증된 응답을 다시 준비해야 합니다."
            )
        else:
            detail = (
                "준비된 자료 파일이 없습니다. "
                "import-file로 검증된 응답을 준비해야 합니다."
            )
        if market == "KR":
            fx_detail = "KR 시장은 KRW 기준으로 FX 자료가 필요하지 않습니다."
        elif has_cached_data:
            fx_detail = "검증된 준비 파일의 FRED DEXKOUS 환율 관측을 사용합니다."
        elif has_invalid_file:
            fx_detail = (
                "준비 파일의 FX 자료 또는 provenance·형식 검증에 실패했습니다. "
                "import-file로 검증된 응답을 다시 준비해야 합니다."
            )
        else:
            fx_detail = (
                "US 시장의 FX 자료가 없습니다. "
                "준비 파일에 FRED DEXKOUS 관측이 필요합니다."
            )
        names = (
            ("credentials", detail),
            ("entitlement", "historical entitlement is approximate"),
            ("calendar", "내장 거래소 달력을 사용할 수 있습니다."),
            ("membership", detail),
            ("bars", detail),
            ("actions", "dividend and delisting history is excluded or unknown"),
            ("fx", fx_detail),
            ("policy", "approximate sample policy is configured"),
        )
        from jusik.market_history_models import Capability

        capabilities = tuple(
            Capability(
                name=cast(CapabilityName, name),
                status="partial"
                if name in {"entitlement", "actions", "policy"}
                else (
                    "ready"
                    if name == "calendar"
                    or (name == "fx" and market == "KR")
                    or has_cached_data
                    else "missing"
                ),
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
                    source=dataset.bar_source,
                    source_hash=_hash(bar_row.model_dump(mode="json")),
                    normalization_version=dataset.normalization_version,
                )
            )
        fx = tuple(
            FXObservation(
                session=fx_row.session,
                observation_date=fx_row.observation_date,
                pair="USDKRW",
                krw_per_usd=fx_row.krw_per_usd,
                spread_rate=fx_row.spread_rate,
                # Missing source timing is conservatively treated as available
                # only after that session's close; it can never fund that day.
                available_at=fx_row.available_at
                or _session(self.calendar, "NMS", fx_row.session).close_at,
                captured_at=captured,
                source=dataset.fx_source,
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


def run_approximate_market_research(
    snapshot: MarketHistorySnapshot,
    request: MarketResearchRequest,
    readiness: MarketReadiness,
    calendar: MarketCalendar,
    *,
    policy_hash: str | None = None,
) -> MarketResearchResult:
    """Run the same trading core as strict research with approximate coverage."""
    return run_market_research(
        snapshot,
        request,
        readiness,
        calendar,
        policy_hash=policy_hash,
        allow_approximate=True,
    )
