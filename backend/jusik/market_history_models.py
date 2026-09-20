from __future__ import annotations

import hashlib
import json
from base64 import b64decode, b64encode
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    TypeAdapter,
    model_validator,
)

Market = Literal["KR", "US"]
ResearchStage = Literal["pilot", "final", "legacy"]
ResearchGrade = Literal["strict", "approximate"]
InstrumentType = Literal["stock", "etf"]
Currency = Literal["KRW", "USD"]
STAGED_INITIAL_CASH_KRW = Decimal("100000000")
STAGED_FEE_RATE = Decimal("0.00015")
STAGED_SLIPPAGE_RATE = Decimal("0.001")
STAGED_SELL_TAX_RATE = Decimal("0.0018")
SourceName = Literal[
    "fixture",
    "krx",
    "massive",
    "yahoo",
    "alpha_vantage",
    "fred",
    "approximate_file",
]
CapabilityName = Literal[
    "credentials",
    "entitlement",
    "calendar",
    "membership",
    "bars",
    "actions",
    "fx",
    "policy",
]

KR_EXCHANGES = frozenset(("KRX", "KSC", "KOSPI", "KOSDAQ"))
US_EXCHANGES = frozenset(("NAS", "NMS", "NGM", "NYS", "NYQ", "AMS", "PCX"))


class HistoryModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def require_aware_timestamps(self) -> Self:
        for value in self.__dict__.values():
            if isinstance(value, datetime) and (
                value.tzinfo is None or value.utcoffset() is None
            ):
                raise ValueError("timestamps must include a timezone")
        return self


class MarketBar(HistoryModel):
    market: Market
    exchange: str = Field(min_length=1, max_length=12)
    symbol: str = Field(min_length=1, max_length=20)
    session: date
    open: Decimal = Field(gt=0, allow_inf_nan=False)
    high: Decimal = Field(gt=0, allow_inf_nan=False)
    low: Decimal = Field(gt=0, allow_inf_nan=False)
    close: Decimal = Field(gt=0, allow_inf_nan=False)
    volume: Decimal = Field(ge=0, allow_inf_nan=False)
    currency: Currency
    captured_at: datetime
    available_at: datetime
    source: SourceName
    source_hash: str = Field(min_length=64, max_length=64)
    normalization_version: str = Field(min_length=1, max_length=40)
    adjusted: bool = False

    @model_validator(mode="after")
    def validate_bar(self) -> Self:
        if (
            self.low > min(self.open, self.close)
            or self.high < max(self.open, self.close)
            or self.low > self.high
        ):
            raise ValueError("OHLC range is invalid")
        if self.available_at < self.session_start_utc():
            raise ValueError("bar cannot be available before its session")
        expected = "KRW" if self.market == "KR" else "USD"
        if self.currency != expected:
            raise ValueError("market and bar currency do not match")
        return self

    def session_start_utc(self) -> datetime:
        # The source's availability timestamp is the authoritative PIT clock;
        # this lower bound only rejects impossible pre-session timestamps.
        return datetime.combine(self.session, datetime.min.time(), tzinfo=UTC)


class PITMembership(HistoryModel):
    stable_id: str = Field(min_length=1, max_length=80)
    market: Market
    exchange: str = Field(min_length=1, max_length=12)
    symbol: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=120)
    instrument_type: InstrumentType
    currency: Currency
    valid_from: date
    valid_to: date | None = None
    available_at: datetime
    captured_at: datetime
    source: SourceName
    source_hash: str = Field(min_length=64, max_length=64)
    normalization_version: str = Field(min_length=1, max_length=40)

    @model_validator(mode="after")
    def validate_membership(self) -> Self:
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise ValueError("membership validity interval is invalid")
        expected = "KRW" if self.market == "KR" else "USD"
        if self.currency != expected:
            raise ValueError("market and membership currency do not match")
        return self

    def is_valid_on(self, session: date) -> bool:
        return self.valid_from <= session and (
            self.valid_to is None or session <= self.valid_to
        )


class CorporateAction(HistoryModel):
    market: Market
    symbol: str = Field(min_length=1, max_length=20)
    session: date
    kind: Literal["split", "delisting", "halt"]
    ratio: Decimal | None = Field(default=None, gt=0, allow_inf_nan=False)
    available_at: datetime
    captured_at: datetime
    source: SourceName
    source_hash: str = Field(min_length=64, max_length=64)


class FXObservation(HistoryModel):
    session: date
    observation_date: date | None = None
    pair: Literal["USDKRW"]
    krw_per_usd: Decimal = Field(gt=0, allow_inf_nan=False)
    spread_rate: Decimal = Field(ge=0, le=Decimal("0.1"), allow_inf_nan=False)
    available_at: datetime
    captured_at: datetime
    source: SourceName
    source_hash: str = Field(min_length=64, max_length=64)


class RawArtifact(HistoryModel):
    artifact_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    content_type: str = Field(min_length=1, max_length=80)
    captured_at: datetime
    source: SourceName
    source_url: HttpUrl | None = None
    raw_content: bytes = Field(default=b"", exclude=True, repr=False)
    raw_content_b64: str = Field(default="", exclude=False, repr=False)

    @model_validator(mode="after")
    def validate_content_hash(self) -> Self:
        content = self.raw_content
        if self.raw_content_b64:
            try:
                decoded = b64decode(self.raw_content_b64, validate=True)
            except ValueError as exc:
                raise ValueError("raw artifact content encoding is invalid") from exc
            if content and decoded != content:
                raise ValueError("raw artifact content representations differ")
            content = decoded
        digest = hashlib.sha256(content).hexdigest()
        if digest != self.artifact_id or digest != self.content_sha256:
            raise ValueError("raw artifact content hash does not match metadata")
        return self

    @property
    def decoded_content(self) -> bytes:
        if self.raw_content_b64:
            return b64decode(self.raw_content_b64, validate=True)
        return self.raw_content

    @classmethod
    def from_bytes(
        cls,
        content: bytes,
        *,
        content_type: str,
        captured_at: datetime,
        source: SourceName,
        source_url: str | None = None,
    ) -> RawArtifact:
        digest = hashlib.sha256(content).hexdigest()
        return cls(
            artifact_id=digest,
            content_sha256=digest,
            content_type=content_type,
            captured_at=captured_at,
            source=source,
            source_url=(
                TypeAdapter(HttpUrl).validate_python(source_url)
                if source_url is not None
                else None
            ),
            raw_content=content,
            raw_content_b64=b64encode(content).decode("ascii"),
        )


class MarketHistorySnapshot(HistoryModel):
    market: Market
    requested_start: date
    requested_end: date
    captured_at: datetime
    memberships: tuple[PITMembership, ...]
    bars: tuple[MarketBar, ...]
    actions: tuple[CorporateAction, ...]
    actions_complete: bool = False
    fx: tuple[FXObservation, ...] = ()
    source_artifacts: tuple[RawArtifact, ...] = ()
    completeness: Literal["complete", "incomplete"]
    missing_ranges: tuple[str, ...] = ()
    normalization_version: str = "pit-v1"
    # Exactly twenty completed sessions immediately before evaluation.  Kept in
    # the immutable snapshot so the first signal cannot silently borrow future
    # or current-period rows.
    warmup_sessions: tuple[date, ...] = ()
    evaluation_start: date | None = None
    data_contract_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    research_grade: ResearchGrade = "strict"
    pool_contract_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_snapshot(self) -> Self:
        if self.requested_end < self.requested_start:
            raise ValueError("snapshot period is invalid")
        if (
            self.evaluation_start is not None
            and self.evaluation_start != self.requested_start
        ):
            raise ValueError("snapshot evaluation start must equal requested start")
        if len(self.warmup_sessions) > 20:
            raise ValueError("snapshot warmup cannot exceed twenty sessions")
        if len(set(self.warmup_sessions)) != len(self.warmup_sessions):
            raise ValueError("duplicate warmup sessions are not allowed")
        if self.warmup_sessions and max(self.warmup_sessions) >= self.requested_start:
            raise ValueError("warmup must precede evaluation")
        bar_keys = [(bar.symbol, bar.session) for bar in self.bars]
        if len(bar_keys) != len(set(bar_keys)):
            raise ValueError("duplicate bars are not allowed")
        membership_ids = [item.stable_id for item in self.memberships]
        if len(membership_ids) != len(set(membership_ids)):
            raise ValueError("duplicate membership ids are not allowed")
        action_keys = [(item.symbol, item.session, item.kind) for item in self.actions]
        if len(action_keys) != len(set(action_keys)):
            raise ValueError("duplicate corporate actions are not allowed")
        expected_currency = "KRW" if self.market == "KR" else "USD"
        allowed_exchanges = KR_EXCHANGES if self.market == "KR" else US_EXCHANGES
        for item in self.memberships:
            if item.market != self.market:
                raise ValueError("snapshot child market does not match snapshot")
            if item.currency != expected_currency:
                raise ValueError("snapshot child currency does not match market")
            if item.exchange not in allowed_exchanges:
                raise ValueError("snapshot child exchange is not allowed for market")
        for bar_item in self.bars:
            if bar_item.market != self.market:
                raise ValueError("snapshot child market does not match snapshot")
            if bar_item.currency != expected_currency:
                raise ValueError("snapshot child currency does not match market")
            if bar_item.exchange not in allowed_exchanges:
                raise ValueError("snapshot child exchange is not allowed for market")
        if any(item.market != self.market for item in self.actions):
            raise ValueError("snapshot action market does not match snapshot")
        if self.completeness == "complete" and self.missing_ranges:
            raise ValueError("complete snapshot cannot contain missing ranges")
        return self

    @property
    def input_hash(self) -> str:
        payload = self.model_dump(mode="json")
        return hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()
        ).hexdigest()


class Capability(HistoryModel):
    name: CapabilityName
    status: Literal["ready", "missing", "unsupported", "partial"]
    detail: str = Field(min_length=1, max_length=240)
    missing_ranges: tuple[str, ...] = ()


class MarketReadiness(HistoryModel):
    market: Market
    checked_at: datetime
    capabilities: tuple[Capability, ...]
    ready: bool
    simulated: bool = False
    research_grade: ResearchGrade = "strict"

    @model_validator(mode="after")
    def validate_ready_status(self) -> Self:
        required_names = {
            "credentials",
            "entitlement",
            "calendar",
            "membership",
            "bars",
            "actions",
            "fx",
            "policy",
        }
        names = [item.name for item in self.capabilities]
        if len(names) != len(required_names) or set(names) != required_names:
            raise ValueError("readiness must contain each required capability once")
        required_ready = all(item.status == "ready" for item in self.capabilities)
        if self.ready != required_ready:
            raise ValueError("readiness.ready must match capability statuses")
        return self


class MarketResearchRequest(HistoryModel):
    market: Market
    start_date: date
    end_date: date
    stage: ResearchStage = "legacy"
    pilot_run_id: str | None = Field(default=None, min_length=8, max_length=64)
    initial_cash_krw: Decimal = Field(default=STAGED_INITIAL_CASH_KRW, gt=0)
    fee_rate: Decimal = Field(default=STAGED_FEE_RATE, ge=0, le=Decimal("0.1"))
    slippage_rate: Decimal = Field(
        default=STAGED_SLIPPAGE_RATE, ge=0, le=Decimal("0.1")
    )
    sell_tax_rate: Decimal = Field(
        default=STAGED_SELL_TAX_RATE, ge=0, le=Decimal("0.1")
    )
    research_grade: ResearchGrade = "strict"

    @model_validator(mode="after")
    def validate_period(self) -> Self:
        if self.end_date < self.start_date:
            raise ValueError("end_date must not precede start_date")
        if (self.end_date - self.start_date).days > 1096:
            raise ValueError("research period may not exceed three years")
        if self.stage == "pilot":
            if self.pilot_run_id is not None:
                raise ValueError("pilot cannot reference another run")
            expected = anniversary_start(self.end_date, years=1)
            if self.start_date != expected:
                raise ValueError(
                    "pilot start must be exactly one calendar year before end"
                )
        elif self.stage == "final":
            if self.pilot_run_id is None:
                raise ValueError("final requires pilot_run_id")
            expected = anniversary_start(self.end_date, years=3)
            if self.start_date != expected:
                raise ValueError(
                    "final start must be exactly three calendar years before end"
                )
        elif self.pilot_run_id is not None:
            raise ValueError("legacy request cannot reference a pilot")
        if self.stage in {"pilot", "final"} and (
            self.initial_cash_krw != STAGED_INITIAL_CASH_KRW
            or self.fee_rate != STAGED_FEE_RATE
            or self.slippage_rate != STAGED_SLIPPAGE_RATE
            or self.sell_tax_rate != STAGED_SELL_TAX_RATE
        ):
            raise ValueError("staged execution assumptions are fixed by the mandate")
        return self


class CandidateEvidence(HistoryModel):
    session: date
    symbol: str
    rank: int = Field(ge=1, le=20)
    volume: Decimal = Field(ge=0, allow_inf_nan=False)
    eligible: bool
    membership_available_at: datetime | None = None
    bar_available_at: datetime | None = None


class ResearchTrade(HistoryModel):
    session: date
    signal_session: date
    fill_session: date
    symbol: str
    side: Literal["buy", "sell"]
    quantity: int = Field(gt=0)
    currency: Currency
    market_open: Decimal = Field(gt=0, allow_inf_nan=False)
    fill_price: Decimal = Field(gt=0, allow_inf_nan=False)
    notional: Decimal = Field(gt=0, allow_inf_nan=False)
    fee: Decimal = Field(ge=0, allow_inf_nan=False)
    tax: Decimal = Field(ge=0, allow_inf_nan=False)
    rationale: str = Field(min_length=1, max_length=240)


class ResearchEquityPoint(HistoryModel):
    session: date
    # Optional on legacy artifacts. New strategy runs populate the exact
    # causal evaluation instant; readiness keeps the legacy omission blocked.
    evaluation_at: datetime | None = None
    cash_krw: Decimal = Field(ge=0, allow_inf_nan=False)
    cash_native: Decimal = Field(ge=0, allow_inf_nan=False)
    invested_krw: Decimal = Field(ge=0, allow_inf_nan=False)
    nav_krw: Decimal = Field(ge=0, allow_inf_nan=False)
    fx_krw_per_usd: Decimal = Field(gt=0, allow_inf_nan=False)
    drawdown_pct: Decimal = Field(ge=0, allow_inf_nan=False)


class MarketResearchProvenance(HistoryModel):
    """Optional source facts copied from the immutable research snapshot."""

    universe_sources: tuple[SourceName, ...] | None = None
    bar_sources: tuple[SourceName, ...] | None = None
    fx_sources: tuple[SourceName, ...] | None = None
    artifact_sources: tuple[SourceName, ...] | None = None
    normalization_version: str | None = Field(default=None, min_length=1, max_length=40)
    captured_at: datetime | None = None


class MarketResearchAccountMetadata(HistoryModel):
    """Optional market-scoped account and currency facts for a result."""

    account_scope: Literal["market_specific_independent_simulated"] = (
        "market_specific_independent_simulated"
    )
    reporting_currency: Literal["KRW"] = "KRW"
    native_currency: Currency
    initial_cash_krw: Decimal = Field(gt=0, allow_inf_nan=False)
    fx_krw_per_usd: Decimal | None = Field(default=None, gt=0, allow_inf_nan=False)
    initial_cash_conversion: Literal["identity", "initial_krw_to_usd"]


class MarketResearchResult(HistoryModel):
    market: Market
    request: MarketResearchRequest
    readiness: MarketReadiness
    status: Literal["ready", "insufficient", "approximate"]
    completeness: Literal["complete", "incomplete", "approximate"]
    candidate_evidence: tuple[CandidateEvidence, ...] = ()
    trades: tuple[ResearchTrade, ...] = ()
    equity: tuple[ResearchEquityPoint, ...] = ()
    # The engine anchor is deliberately not interpreted as a historical
    # deposit. It is present only when the run records its causal time plan.
    initial_capital_at: datetime | None = None
    limitations: tuple[str, ...] = ()
    metrics: dict[str, Decimal] = Field(default_factory=dict)
    input_hash: str | None = None
    policy_hash: str | None = None
    stage: ResearchStage = "legacy"
    pilot_run_id: str | None = None
    data_contract_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    warmup_sessions: tuple[date, ...] = ()
    research_grade: ResearchGrade = "strict"
    pool_contract_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    provenance: MarketResearchProvenance | None = None
    account: MarketResearchAccountMetadata | None = None

    @model_validator(mode="after")
    def validate_time_evidence(self) -> Self:
        timestamps = tuple(item.evaluation_at for item in self.equity)
        has_any = self.initial_capital_at is not None or any(
            value is not None for value in timestamps
        )
        if not has_any:
            return self
        if self.initial_capital_at is None or any(
            value is None for value in timestamps
        ):
            raise ValueError(
                "time evidence must include initial and every NAV timestamp"
            )
        ordered = tuple(value for value in timestamps if value is not None)
        if ordered != tuple(sorted(ordered)) or len(set(ordered)) != len(ordered):
            raise ValueError("NAV evaluation timestamps must be strictly increasing")
        if ordered and self.initial_capital_at >= ordered[0]:
            raise ValueError("initial capital anchor must precede the first NAV")
        return self

    @model_validator(mode="after")
    def validate_grade_consistency(self) -> Self:
        if (
            self.research_grade != self.request.research_grade
            or self.research_grade != self.readiness.research_grade
        ):
            raise ValueError("research grade must match request and readiness")
        if self.account is not None:
            expected_native = "KRW" if self.market == "KR" else "USD"
            if self.account.native_currency != expected_native:
                raise ValueError("account native currency does not match market")
            if self.account.initial_cash_krw != self.request.initial_cash_krw:
                raise ValueError("account initial cash does not match request")
            expected_conversion = (
                "identity" if self.market == "KR" else "initial_krw_to_usd"
            )
            if self.account.initial_cash_conversion != expected_conversion:
                raise ValueError("account cash conversion does not match market")
            if self.market == "KR" and self.account.fx_krw_per_usd not in (
                None,
                Decimal("1"),
            ):
                raise ValueError("KR account FX quote must be identity")
        return self


class MarketResearchRun(HistoryModel):
    id: str = Field(min_length=8, max_length=64)
    status: Literal["queued", "running", "completed", "insufficient", "failed"]
    request: MarketResearchRequest
    result: MarketResearchResult | None = None
    input_hash: str | None = None
    created_at: datetime
    updated_at: datetime
    error: str | None = None
    stage: ResearchStage = "legacy"
    pilot_run_id: str | None = None
    data_contract_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    final_promotable: bool = False
    final_promotability_reason: str = "최종 단계 참조 조건을 확인하지 않았습니다."


def anniversary_start(end_date: date, *, years: int) -> date:
    """Return the calendar anniversary, mapping Feb 29 to Feb 28."""
    if years < 0:
        raise ValueError("years must be non-negative")
    try:
        return end_date.replace(year=end_date.year - years)
    except ValueError:
        return end_date.replace(year=end_date.year - years, day=28)
