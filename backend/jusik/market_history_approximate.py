"""Bounded, explicitly approximate historical market-data workflow.

This module accepts prepared provider responses and never falls back to the
current candidate universe.  The CLI imports and validates a prepared response
file; network collection is intentionally outside this bounded workflow.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Literal, Protocol, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
US_MEMBERSHIP_NORMALIZATION_VERSION = "approx-us-r1-membership-v1"
US_EVENT_TIMING_NORMALIZATION_VERSION = "approx-us-r1-event-timing-v1"
US_MEMBERSHIP_POOL_POLICY_VERSION = "approximate-us-membership-pool-v1"
US_EVENT_TIMING_POOL_POLICY_VERSION = "approximate-us-event-timing-pool-v1"
US_MEMBERSHIP_SEED = 20260914
APPROX_LOOKBACK_SESSIONS = 20
APPROX_TARGET_WEIGHT = Decimal("0.05")

CollectionDiagnosticReason = Literal[
    "partial_history",
    "coverage",
    "identity_mismatch",
    "quota",
    "auth",
    "budget",
    "parse",
    "null",
    "observed_delisting",
    "unknown",
    "all_failure",
]


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


class ApproximateEvent(BaseModel):
    """Provider event metadata kept outside snapshot.actions.

    The approximate strategy cannot account for corporate actions.  Keeping
    these facts on the prepared dataset lets the source retain causal rows
    while the wrapper fails closed when the timing is not usable.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: str = Field(min_length=1, max_length=20)
    kind: str = Field(min_length=1, max_length=40)
    occurrence_at: datetime | None = None
    observed_at: datetime | None = None
    invalid_timing: bool = False
    source: SourceName = "yahoo"

    @model_validator(mode="after")
    def require_aware_timestamps(self) -> ApproximateEvent:
        for value in (self.occurrence_at, self.observed_at):
            if value is not None and (
                value.tzinfo is None or value.utcoffset() is None
            ):
                raise ValueError("event timestamps must include a timezone")
        return self

    @property
    def occurred_at(self) -> datetime | None:
        """Compatibility spelling for consumers using the past-tense name."""
        return self.occurrence_at


class CollectionCoverage(BaseModel):
    """Reconciled coverage for one Yahoo request or an aggregate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    expected_sessions: int = Field(ge=0)
    actual_sessions: int = Field(ge=0)
    missing_sessions: int = Field(ge=0)
    retained_sessions: int = Field(ge=0)
    event_excluded_sessions: int = Field(ge=0)

    @model_validator(mode="after")
    def reconcile(self) -> CollectionCoverage:
        if self.expected_sessions != self.actual_sessions + self.missing_sessions:
            raise ValueError("collection coverage expected/actual/missing mismatch")
        if self.actual_sessions != (
            self.retained_sessions + self.event_excluded_sessions
        ):
            raise ValueError("collection coverage actual/retained/excluded mismatch")
        return self


class CollectionSymbolDiagnostic(BaseModel):
    """Bounded, provider-body-free diagnostics for one requested symbol."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: str = Field(min_length=1, max_length=20)
    reasons: tuple[CollectionDiagnosticReason, ...] = ()
    coverage: CollectionCoverage
    request_excluded: bool = False
    occurrence_at: datetime | None = None
    observed_at: datetime | None = None

    @model_validator(mode="after")
    def validate_reasons(self) -> CollectionSymbolDiagnostic:
        if self.occurrence_at is not None and (
            self.occurrence_at.tzinfo is None or self.occurrence_at.utcoffset() is None
        ):
            raise ValueError("diagnostic occurrence timestamp must include a timezone")
        if self.observed_at is not None and (
            self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None
        ):
            raise ValueError("diagnostic observation timestamp must include a timezone")
        if "observed_delisting" in self.reasons and (
            self.occurrence_at is None or self.observed_at is None
        ):
            raise ValueError("observed delisting requires both event timestamps")
        return self


class CollectionDiagnostics(BaseModel):
    """Serializable US collection diagnostics, independent of strategy inputs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal["us-collection-diagnostics-v1"] = "us-collection-diagnostics-v1"
    requested_start: date
    requested_end: date
    warmup_start: date
    coverage: CollectionCoverage
    symbols: tuple[CollectionSymbolDiagnostic, ...] = ()
    reason_counts: dict[CollectionDiagnosticReason, int] = Field(default_factory=dict)
    request_excluded_symbols: tuple[str, ...] = ()
    request_excluded_symbol_count: int = Field(default=0, ge=0)
    all_failed: bool = False

    @model_validator(mode="after")
    def validate_diagnostics(self) -> CollectionDiagnostics:
        if self.requested_end < self.requested_start:
            raise ValueError("diagnostic requested period is invalid")
        if self.warmup_start > self.requested_start:
            raise ValueError("diagnostic warmup must not follow requested start")
        symbols = tuple(sorted(self.symbols, key=lambda item: item.symbol))
        if symbols != self.symbols:
            raise ValueError("diagnostic symbols must be sorted")
        if len({item.symbol for item in symbols}) != len(symbols):
            raise ValueError("diagnostic symbols must be unique")
        excluded_symbols = tuple(sorted(self.request_excluded_symbols))
        if excluded_symbols != self.request_excluded_symbols:
            raise ValueError("diagnostic request exclusions must be sorted")
        if len(set(excluded_symbols)) != len(excluded_symbols):
            raise ValueError("diagnostic request exclusions must be unique")
        expected_excluded = tuple(
            item.symbol for item in symbols if item.request_excluded
        )
        if excluded_symbols != expected_excluded:
            raise ValueError("diagnostic request exclusions do not match symbols")
        if self.request_excluded_symbol_count != len(excluded_symbols):
            raise ValueError(
                "diagnostic request exclusion count does not match symbols"
            )
        aggregate = _aggregate_coverage(item.coverage for item in symbols)
        if aggregate != self.coverage:
            raise ValueError("diagnostic aggregate coverage does not match symbols")
        if (
            self.all_failed
            and symbols
            and not all(item.coverage.actual_sessions == 0 for item in symbols)
        ):
            raise ValueError("all-failure diagnostics cannot retain actual sessions")
        if self.all_failed and symbols:
            if not all(item.request_excluded for item in symbols):
                raise ValueError(
                    "all-failure diagnostics must exclude every requested symbol"
                )
            if excluded_symbols != tuple(item.symbol for item in symbols):
                raise ValueError(
                    "all-failure diagnostics must list every requested exclusion"
                )
            if any("all_failure" not in item.reasons for item in symbols):
                raise ValueError(
                    "all-failure diagnostics require an all_failure reason per symbol"
                )
        expected_counts: dict[CollectionDiagnosticReason, int] = {}
        for item in symbols:
            if len(item.reasons) != len(set(item.reasons)):
                raise ValueError("diagnostic reasons must be unique")
            for reason in item.reasons:
                expected_counts[reason] = expected_counts.get(reason, 0) + 1
        if not self.all_failed and expected_counts.get("all_failure", 0):
            raise ValueError("non-failure diagnostics cannot contain all_failure")
        if (
            self.all_failed
            and symbols
            and expected_counts.get("all_failure") != len(symbols)
        ):
            raise ValueError(
                "all-failure diagnostics require an aggregate all_failure reason"
            )
        if any(value < 0 for value in self.reason_counts.values()):
            raise ValueError("diagnostic reason counts must be non-negative")
        if self.reason_counts != expected_counts:
            raise ValueError("diagnostic reason counts do not match symbols")
        return self


def _aggregate_coverage(
    coverages: Iterable[CollectionCoverage],
) -> CollectionCoverage:
    values = tuple(coverages)
    return CollectionCoverage(
        expected_sessions=sum(item.expected_sessions for item in values),
        actual_sessions=sum(item.actual_sessions for item in values),
        missing_sessions=sum(item.missing_sessions for item in values),
        retained_sessions=sum(item.retained_sessions for item in values),
        event_excluded_sessions=sum(item.event_excluded_sessions for item in values),
    )


class ApproximateDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    market: Market
    universe: tuple[ApproximateUniverseRow, ...]
    bars: tuple[ApproximateBarRow, ...]
    fx: tuple[ApproximateFXRow, ...] = ()
    events: tuple[ApproximateEvent, ...] = ()
    source: SourceName = "approximate_file"
    bar_source: Literal["krx", "yahoo"] = "yahoo"
    fx_source: Literal["fred"] = "fred"
    simulated: bool = False
    normalization_version: str = Field(default="approx-v2", min_length=1, max_length=40)
    collection_diagnostics: CollectionDiagnostics | None = Field(
        default=None, exclude_if=lambda value: value is None
    )


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


def _us_contract_hash(*, policy_version: str, normalization_version: str) -> str:
    return _hash(
        {
            "version": policy_version,
            "normalization_version": normalization_version,
            "seed": US_MEMBERSHIP_SEED,
            "per_session_sample_size": MAX_SAMPLE_SYMBOLS,
            "cumulative_unique_admissions": MAX_UNIQUE_SYMBOLS,
            "admission": "initial-seeded-retain-incumbents-fill-vacancies",
            "availability": "checkpoint-close-fallback-monotonic",
            "gaps": "failed-checkpoint-unknown-until-recovery",
            "event_timing": "occurrence-and-observation-required-before-cutoff",
        }
    )


def us_membership_contract_hash() -> str:
    """Return the stable R1-01 policy hash for causal US membership."""
    return _hash(
        {
            "version": US_MEMBERSHIP_POOL_POLICY_VERSION,
            "normalization_version": US_MEMBERSHIP_NORMALIZATION_VERSION,
            "seed": US_MEMBERSHIP_SEED,
            "per_session_sample_size": MAX_SAMPLE_SYMBOLS,
            "cumulative_unique_admissions": MAX_UNIQUE_SYMBOLS,
            "admission": "initial-seeded-retain-incumbents-fill-vacancies",
            "availability": "checkpoint-close-fallback-monotonic",
            "gaps": "failed-checkpoint-unknown-until-recovery",
        }
    )


def us_event_timing_contract_hash() -> str:
    """Return the policy hash for causal US event timing selections."""
    return _us_contract_hash(
        policy_version=US_EVENT_TIMING_POOL_POLICY_VERSION,
        normalization_version=US_EVENT_TIMING_NORMALIZATION_VERSION,
    )


def legacy_us_membership_contract_hash() -> str:
    """Return the R1-01 hash so legacy prepared artifacts remain identifiable."""
    return us_membership_contract_hash()


def _validate_us_membership_rows(
    rows: tuple[ApproximateUniverseRow, ...],
    *,
    market: Market,
) -> None:
    """Validate collector-produced causal selections without resampling them."""
    expected_currency = "KRW" if market == "KR" else "USD"
    symbols_by_session: dict[date, set[str]] = {}
    all_symbols: set[str] = set()
    for row in rows:
        if row.currency != expected_currency:
            raise ApproximateProviderError("US membership currency is invalid")
        session_symbols = symbols_by_session.setdefault(row.session, set())
        if row.symbol in session_symbols:
            raise ApproximateProviderError(
                "US membership contains duplicate symbols on a session"
            )
        session_symbols.add(row.symbol)
        all_symbols.add(row.symbol)
    if any(
        len(symbols) > MAX_SAMPLE_SYMBOLS
        for symbols in symbols_by_session.values()
    ):
        raise ApproximateProviderError("US membership exceeds the per-session bound")
    if len(all_symbols) > MAX_UNIQUE_SYMBOLS:
        raise ApproximateProviderError(
            "US membership exceeds the cumulative admission bound"
        )


def canonicalize_approximate_events(
    events: tuple[ApproximateEvent, ...],
) -> tuple[tuple[ApproximateEvent, ...], frozenset[str]]:
    """Dedupe equivalent event records and identify contradictory timings."""
    ordered = sorted(
        events,
        key=lambda event: (
            event.symbol,
            event.kind,
            event.occurrence_at or datetime.min.replace(tzinfo=UTC),
            event.observed_at or datetime.min.replace(tzinfo=UTC),
            event.invalid_timing,
            event.source,
        ),
    )
    deduped: list[ApproximateEvent] = []
    seen: set[tuple[object, ...]] = set()
    timings: dict[tuple[str, str, datetime | None], set[datetime | None]] = {}
    contradictory: set[str] = set()
    for event in ordered:
        identity = (
            event.symbol,
            event.kind,
            event.occurrence_at,
            event.observed_at,
            event.invalid_timing,
            event.source,
        )
        if identity not in seen:
            seen.add(identity)
            deduped.append(event)
        timing_key = (event.symbol, event.kind, event.occurrence_at)
        timings.setdefault(timing_key, set()).add(event.observed_at)
    for (symbol, _kind, _occurrence), observations in timings.items():
        if len(observations) > 1:
            contradictory.add(symbol)
    return tuple(deduped), frozenset(contradictory)


def _event_cutoff_session(
    calendar: MarketCalendar,
    effective_at: datetime,
    *,
    start: date,
    end: date,
) -> tuple[date | None, bool]:
    """Map an event instant to a daily-bar boundary without guessing intraday."""
    cursor = start
    while cursor <= end:
        lookup = calendar.lookup("NMS", cursor)
        if lookup.session is not None:
            session = lookup.session
            if effective_at <= session.open_at:
                return session.local_date, False
            if effective_at < session.close_at:
                return None, True
        cursor += timedelta(days=1)
    return None, False


def _last_session_close(
    calendar: MarketCalendar, *, start: date, end: date
) -> datetime | None:
    cursor = end
    while cursor >= start:
        lookup = calendar.lookup("NMS", cursor)
        if lookup.session is not None:
            return lookup.session.close_at
        cursor -= timedelta(days=1)
    return None


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

    async def collect(
        self,
        request: MarketResearchRequest,
        *,
        captured_at: datetime | None = None,
    ) -> MarketHistorySnapshot:
        if request.research_grade != "approximate":
            raise ApproximateProviderError(
                "approximate source requires approximate request"
            )
        response = await self.provider.fetch(
            request.market, request.start_date, request.end_date
        )
        dataset = response.dataset
        is_causal_us = request.market == "US" and dataset.normalization_version in {
            US_MEMBERSHIP_NORMALIZATION_VERSION,
            US_EVENT_TIMING_NORMALIZATION_VERSION,
        }
        pool = (
            deterministic_pool(
                dataset.universe, market=request.market, pool_end=request.end_date
            )
            if not is_causal_us
            else None
        )
        if is_causal_us:
            _validate_us_membership_rows(dataset.universe, market=request.market)
            selected_rows = dataset.universe
            contract_hash = (
                legacy_us_membership_contract_hash()
                if dataset.normalization_version == US_MEMBERSHIP_NORMALIZATION_VERSION
                else us_event_timing_contract_hash()
            )
        else:
            assert pool is not None
            selected_rows = pool.rows
            contract_hash = pool.contract_hash
        event_timing_enabled = (
            request.market == "US"
            and dataset.normalization_version == US_EVENT_TIMING_NORMALIZATION_VERSION
        )
        normalized_events: tuple[ApproximateEvent, ...]
        if event_timing_enabled:
            normalized_events, _ = canonicalize_approximate_events(dataset.events)
        else:
            normalized_events = ()
        final_session_close = _last_session_close(
            self.calendar, start=request.start_date, end=request.end_date
        )
        visible_events = tuple(
            event
            for event in normalized_events
            if final_session_close is None
            or event.observed_at is None
            or event.observed_at.astimezone(UTC) <= final_session_close
        )
        _, visible_contradictory_event_symbols = canonicalize_approximate_events(
            visible_events
        )
        event_cutoffs: dict[str, date] = {}
        ambiguous_event_symbols: set[str] = set()
        if event_timing_enabled:
            for event in normalized_events:
                if (
                    event.invalid_timing
                    or event.occurrence_at is None
                    or event.observed_at is None
                ):
                    continue
                effective_at = max(
                    event.occurrence_at.astimezone(UTC),
                    event.observed_at.astimezone(UTC),
                )
                cutoff, ambiguous = _event_cutoff_session(
                    self.calendar,
                    effective_at,
                    start=request.start_date,
                    end=request.end_date,
                )
                if ambiguous:
                    ambiguous_event_symbols.add(event.symbol)
                    continue
                if cutoff is None:
                    continue
                previous = event_cutoffs.get(event.symbol)
                if previous is None or cutoff < previous:
                    event_cutoffs[event.symbol] = cutoff
            selected_rows = tuple(
                row
                for row in selected_rows
                if row.session < event_cutoffs.get(row.symbol, date.max)
            )
        if captured_at is None:
            captured = datetime.now(UTC)
        elif captured_at.tzinfo is None or captured_at.utcoffset() != timedelta(0):
            raise ApproximateProviderError("captured_at must be an aware UTC timestamp")
        else:
            captured = captured_at.astimezone(UTC)
        memberships: list[PITMembership] = []
        for row in selected_rows:
            market_session = _session(self.calendar, row.exchange, row.session)
            membership_available_at = row.available_at or market_session.close_at
            if is_causal_us:
                if (
                    membership_available_at.tzinfo is None
                    or membership_available_at.utcoffset() is None
                ):
                    raise ApproximateProviderError(
                        "US membership availability must be timezone-aware"
                    )
                membership_available_at = membership_available_at.astimezone(UTC)
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
                    available_at=membership_available_at,
                    captured_at=captured,
                    source=dataset.source,
                    source_hash=_hash(row.model_dump(mode="json")),
                    normalization_version=dataset.normalization_version,
                )
            )
        bars: list[MarketBar] = []
        selected_symbols = {row.symbol for row in selected_rows}
        for bar_row in dataset.bars:
            if bar_row.symbol not in selected_symbols:
                continue
            if event_timing_enabled and bar_row.session >= event_cutoffs.get(
                bar_row.symbol, date.max
            ):
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
        unknown_event_symbols = sorted(
            {
                event.symbol
                for event in visible_events
                if event_timing_enabled
                and (
                    event.occurrence_at is None
                    or event.invalid_timing
                    or (
                        event.occurrence_at.astimezone(UTC).date() <= request.end_date
                        and event.observed_at is None
                    )
                    or (
                        event.symbol in visible_contradictory_event_symbols
                        and (
                            event.occurrence_at is None
                            or event.occurrence_at.astimezone(UTC).date()
                            <= request.end_date
                        )
                    )
                    or event.symbol in ambiguous_event_symbols
                )
            }
        )
        event_missing_ranges = tuple(
            f"us_event_timing:unknown:{symbol}" for symbol in unknown_event_symbols
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
            missing_ranges=(
                "corporate_actions:dividends_excluded",
                *event_missing_ranges,
            ),
            normalization_version=dataset.normalization_version,
            evaluation_start=request.start_date,
            research_grade="approximate",
            pool_contract_hash=contract_hash,
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
    unknown_event_ranges = tuple(
        item
        for item in snapshot.missing_ranges
        if item.startswith("us_event_timing:unknown:")
    )
    if unknown_event_ranges:
        return MarketResearchResult(
            market=request.market,
            request=request,
            readiness=readiness,
            status="insufficient",
            completeness="incomplete",
            limitations=(
                "미국 기업행동의 발생 또는 관측 시각이 확인되지 않아 "
                "계산하지 않습니다.",
                "불확실한 사건: "
                + ", ".join(
                    item.removeprefix("us_event_timing:unknown:")
                    for item in unknown_event_ranges
                ),
            ),
            input_hash=snapshot.input_hash,
            policy_hash=policy_hash,
            stage=request.stage,
            pilot_run_id=request.pilot_run_id,
            data_contract_hash=snapshot.data_contract_hash,
            warmup_sessions=snapshot.warmup_sessions,
            research_grade=request.research_grade,
            pool_contract_hash=snapshot.pool_contract_hash,
        )
    return run_market_research(
        snapshot,
        request,
        readiness,
        calendar,
        policy_hash=policy_hash,
        allow_approximate=True,
    )
