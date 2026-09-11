from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import ROUND_HALF_EVEN, Context, Decimal, DecimalException, localcontext
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

from jusik.research_boundary_capture import (
    BoundaryCaptureArtifact,
    BoundaryCaptureStatus,
    BoundaryExecutionQuote,
    BoundaryInputVersion,
    BoundaryName,
)
from jusik.research_forward_models import ForwardDecision, ForwardFill
from jusik.research_portfolio_models import PortfolioInput

MAX_DETAILS = 50
CheckState = Literal["pass", "fail", "unknown", "not_applicable"]
EvidenceState = Literal["not_due", "missing", "unavailable", "inspected"]


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("boundary evidence timestamps must be timezone-aware")
    return value.astimezone(UTC)


class EvidenceCheck(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    state: CheckState
    detail: str


class FillEvidenceDetail(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    fill_id: str
    symbol: str
    side: Literal["buy", "sell"]
    received_at: datetime
    after_boundary: bool
    stored_local_price: Decimal
    expected_local_price: Decimal | None
    stored_notional_krw: Decimal
    expected_notional_krw: Decimal | None
    checks: list[EvidenceCheck]

    @field_validator("received_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        return _utc(value)


class PositionEvidenceDetail(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: str
    currency: Literal["KRW", "USD"]
    quantity: int = Field(ge=0)
    checks: list[EvidenceCheck]


class BoundaryEvidenceResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    boundary: BoundaryName
    boundary_at: datetime
    state: EvidenceState
    reason: (
        Literal[
            "boundary_not_due",
            "capture_missing",
            "capture_unavailable",
        ]
        | None
    ) = None
    artifact_sha256: str | None = None
    session_id: str | None = None
    checks: list[EvidenceCheck]
    fill_total_count: int = Field(ge=0)
    fill_detail_count: int = Field(ge=0, le=MAX_DETAILS)
    fill_omitted_count: int = Field(ge=0)
    fill_failed_count: int = Field(ge=0)
    fill_unknown_count: int = Field(ge=0)
    post_boundary_fill_count: int = Field(ge=0)
    fills: list[FillEvidenceDetail] = Field(max_length=MAX_DETAILS)
    position_total_count: int = Field(ge=0)
    position_detail_count: int = Field(ge=0, le=MAX_DETAILS)
    position_omitted_count: int = Field(ge=0)
    positions: list[PositionEvidenceDetail] = Field(max_length=MAX_DETAILS)
    accepted_nav: Literal[False] = False
    evaluation_inputs_complete: Literal[False] = False
    limitations: list[str]

    @field_validator("boundary_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        return _utc(value)


class BoundaryArtifactReader(Protocol):
    def status(self) -> BoundaryCaptureStatus: ...

    def artifact_body(self, boundary: BoundaryName) -> tuple[bytes, str]: ...


def _check(name: str, state: CheckState, detail: str) -> EvidenceCheck:
    return EvidenceCheck(name=name, state=state, detail=detail)


def _bounded(values: tuple[Decimal, ...]) -> bool:
    for value in values:
        digits = value.as_tuple().digits
        exponent = value.as_tuple().exponent
        if not isinstance(exponent, int) or len(digits) > 100 or abs(exponent) > 1_000:
            return False
    return True


def _expected_fill_price(
    fill: ForwardFill,
    quote_price: Decimal,
    ask: Decimal | None,
    bid: Decimal | None,
    slippage: Decimal,
) -> Decimal | None:
    values = tuple(
        value for value in (quote_price, ask, bid, slippage) if value is not None
    )
    if not _bounded(values):
        return None
    try:
        with localcontext(Context(prec=40, rounding=ROUND_HALF_EVEN)):
            if fill.side == "buy":
                return (ask if ask is not None else quote_price) * (
                    Decimal(1) + slippage
                )
            return (bid if bid is not None else quote_price) * (Decimal(1) - slippage)
    except DecimalException:
        return None


def _expected_notional(fill: ForwardFill) -> Decimal | None:
    values = (fill.local_price, fill.fx_rate)
    if not _bounded(values):
        return None
    try:
        with localcontext(Context(prec=28, rounding=ROUND_HALF_EVEN)):
            return fill.local_price * fill.quantity * fill.fx_rate
    except DecimalException:
        return None


def _fill_detail(
    artifact: BoundaryCaptureArtifact,
    fill: ForwardFill,
    decisions: dict[str, ForwardDecision],
    decision_duplicates: set[str],
    inputs: dict[str, BoundaryInputVersion],
    input_duplicates: set[str],
    quotes_by_fill: dict[str, BoundaryExecutionQuote],
    quote_duplicates: set[str],
) -> FillEvidenceDetail:
    checks: list[EvidenceCheck] = []
    checks.append(
        _check(
            "session_identity",
            "pass" if fill.session_id == artifact.session_id else "fail",
            "체결 session이 원시 기록 session과 일치합니다."
            if fill.session_id == artifact.session_id
            else "체결 session이 원시 기록 session과 다릅니다.",
        )
    )
    decision = decisions.get(fill.decision_id)
    if fill.decision_id in decision_duplicates:
        checks.append(
            _check("decision_reference", "fail", "같은 판단 ID가 중복됩니다.")
        )
    elif decision is None:
        checks.append(
            _check("decision_reference", "unknown", "참조한 판단이 없습니다.")
        )
    elif decision.session_id != artifact.session_id:
        checks.append(
            _check("decision_reference", "fail", "참조한 판단의 session이 다릅니다.")
        )
    else:
        checks.append(
            _check("decision_reference", "pass", "참조한 판단이 한 건 있습니다.")
        )

    if decision is None:
        checks.extend(
            [
                _check(
                    "input_reference",
                    "unknown",
                    "판단이 없어 입력을 연결할 수 없습니다.",
                ),
                _check(
                    "input_timing",
                    "unknown",
                    "판단이 없어 입력 시각을 비교할 수 없습니다.",
                ),
            ]
        )
    elif decision.input_version in input_duplicates:
        checks.extend(
            [
                _check("input_reference", "fail", "같은 입력 ID가 중복됩니다."),
                _check(
                    "input_timing",
                    "unknown",
                    "입력이 중복되어 시각을 비교할 수 없습니다.",
                ),
            ]
        )
    elif decision.input_version not in inputs:
        checks.extend(
            [
                _check("input_reference", "unknown", "판단이 참조한 입력이 없습니다."),
                _check(
                    "input_timing",
                    "unknown",
                    "입력이 없어 시각을 비교할 수 없습니다.",
                ),
            ]
        )
    else:
        input_version = inputs[decision.input_version]
        timing_ok = (
            input_version.cutoff_at <= decision.recorded_at
            and input_version.recorded_at <= decision.recorded_at
        )
        checks.extend(
            [
                _check(
                    "input_reference", "pass", "판단이 참조한 입력이 한 건 있습니다."
                ),
                _check(
                    "input_timing",
                    "pass" if timing_ok else "fail",
                    "입력 cutoff·기록 시각이 판단 기록보다 늦지 않습니다."
                    if timing_ok
                    else "입력 cutoff·기록 시각이 판단 기록보다 늦습니다.",
                ),
            ]
        )

    quote = quotes_by_fill.get(fill.id)
    expected_price: Decimal | None = None
    if fill.id in quote_duplicates:
        checks.append(
            _check("execution_quote_reference", "fail", "같은 체결 시세가 중복됩니다.")
        )
    elif quote is None:
        checks.extend(
            [
                _check(
                    "execution_quote_reference", "unknown", "실제 사용 시세가 없습니다."
                ),
                _check(
                    "symbol_consistency",
                    "unknown",
                    "시세가 없어 종목을 비교할 수 없습니다.",
                ),
                _check(
                    "timestamp_consistency",
                    "unknown",
                    "시세가 없어 시각을 비교할 수 없습니다.",
                ),
                _check(
                    "execution_price",
                    "unknown",
                    "시세가 없어 체결가를 재현할 수 없습니다.",
                ),
                _check(
                    "execution_currency",
                    "unknown",
                    "체결에는 별도 통화 필드가 없습니다.",
                ),
            ]
        )
    else:
        execution_quote = quote
        symbol_matches = execution_quote.quote.symbol == fill.symbol
        time_matches = (
            execution_quote.quote.market_at == fill.market_at
            and execution_quote.quote.received_at == fill.received_at
            and execution_quote.captured_at >= fill.received_at
        )
        checks.extend(
            [
                _check(
                    "execution_quote_reference",
                    "pass",
                    "실제 사용 시세가 한 건 있습니다.",
                ),
                _check(
                    "symbol_consistency",
                    "pass" if symbol_matches else "fail",
                    "체결과 시세 종목이 일치합니다."
                    if symbol_matches
                    else "체결과 시세 종목이 다릅니다.",
                ),
                _check(
                    "timestamp_consistency",
                    "pass" if time_matches else "fail",
                    "시장·수신·보존 시각의 순서가 일치합니다."
                    if time_matches
                    else "시장·수신·보존 시각에 모순이 있습니다.",
                ),
                _check(
                    "execution_currency",
                    "unknown",
                    (
                        f"사용 시세 통화는 {execution_quote.quote.currency}이지만 "
                        "체결에는 독립 통화 필드가 없습니다."
                    ),
                ),
            ]
        )
        expected_price = _expected_fill_price(
            fill,
            execution_quote.quote.price,
            execution_quote.quote.ask,
            execution_quote.quote.bid,
            artifact.snapshot.session.config.slippage_rate,
        )
        checks.append(
            _check(
                "execution_price",
                "unknown"
                if expected_price is None
                else "pass"
                if expected_price == fill.local_price
                else "fail",
                "producer의 precision 40 체결가와 정확히 일치합니다."
                if expected_price is not None and expected_price == fill.local_price
                else "체결가 산술을 안전하게 재현할 수 없습니다."
                if expected_price is None
                else "producer의 precision 40 체결가와 다릅니다.",
            )
        )
        checks.append(
            _check(
                "execution_quote_hash",
                "unknown",
                "시세 원문 JSON이 artifact에 없어 저장된 SHA를 다시 계산하지 않습니다.",
            )
        )

    expected_notional = _expected_notional(fill)
    checks.append(
        _check(
            "notional_arithmetic",
            "unknown"
            if expected_notional is None
            else "pass"
            if expected_notional == fill.notional_krw
            else "fail",
            "저장 경로의 precision 28 원화 거래대금과 정확히 일치합니다."
            if expected_notional is not None and expected_notional == fill.notional_krw
            else "원화 거래대금 산술을 안전하게 재현할 수 없습니다."
            if expected_notional is None
            else "저장 경로의 precision 28 원화 거래대금과 다릅니다.",
        )
    )
    costs_valid = fill.transaction_cost_krw.is_finite() and fill.fx_cost_krw.is_finite()
    checks.append(
        _check(
            "cost_range",
            "pass" if costs_valid else "fail",
            "비용이 유한한 비음수 값입니다. 전체 비용 산식 검증은 아닙니다."
            if costs_valid
            else "비용 값이 유한하지 않습니다.",
        )
    )
    if decision is None:
        checks.extend(
            [
                _check(
                    "decision_timing",
                    "unknown",
                    "판단이 없어 시장·수신 시각을 비교할 수 없습니다.",
                ),
                _check(
                    "decision_expiration",
                    "unknown",
                    "판단이 없어 만료 시각을 비교할 수 없습니다.",
                ),
            ]
        )
    else:
        timing_ok = (
            fill.market_at >= decision.recorded_at
            and fill.received_at >= decision.recorded_at
        )
        checks.extend(
            [
                _check(
                    "decision_timing",
                    "pass" if timing_ok else "fail",
                    "시장·수신 시각이 판단 기록보다 늦거나 같습니다."
                    if timing_ok
                    else "시장 또는 수신 시각이 판단 기록보다 이릅니다.",
                ),
                _check(
                    "decision_expiration",
                    "not_applicable" if decision.expires_at is None else "unknown",
                    "만료 없는 판단입니다."
                    if decision.expires_at is None
                    else (
                        "producer 처리 시각이 artifact에 없어 만료 여부를 "
                        "재판정하지 않습니다."
                    ),
                ),
            ]
        )
    after_boundary = fill.received_at > artifact.boundary_at
    checks.append(
        _check(
            "boundary_timing_diagnostic",
            "not_applicable",
            "경계 뒤 체결이며 원시 관측에는 정상적으로 포함될 수 있습니다."
            if after_boundary
            else "경계 이전 또는 같은 시각 체결입니다. 운영 장애 판정 항목이 아닙니다.",
        )
    )
    return FillEvidenceDetail(
        fill_id=fill.id,
        symbol=fill.symbol,
        side=fill.side,
        received_at=fill.received_at,
        after_boundary=after_boundary,
        stored_local_price=fill.local_price,
        expected_local_price=expected_price,
        stored_notional_krw=fill.notional_krw,
        expected_notional_krw=expected_notional,
        checks=checks,
    )


def _duplicates(values: list[str]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates


def _count_consistency(artifact: BoundaryCaptureArtifact) -> EvidenceCheck:
    snapshot = artifact.snapshot
    actual = {
        "forward_sessions": 1,
        "forward_positions": len(snapshot.positions),
        "forward_decisions": len(snapshot.decisions),
        "forward_fills": len(snapshot.fills),
        "forward_execution_quotes": len(snapshot.execution_quotes),
        "forward_input_versions": len(snapshot.input_versions),
        "forward_corporate_action_metadata": len(snapshot.corporate_actions),
        "forward_corporate_action_applications": len(
            snapshot.corporate_action_applications
        ),
        "forward_checkpoints": len(snapshot.checkpoints),
        "latest_forward_observations": len(snapshot.latest_observations),
    }
    counts: dict[str, int] = {}
    duplicate_tables: set[str] = set()
    for item in artifact.counts:
        if item.table in counts:
            duplicate_tables.add(item.table)
        counts[item.table] = item.included_count
    consistent = not duplicate_tables and counts == actual
    return _check(
        "captured_counts",
        "pass" if consistent else "fail",
        "표별 포함 건수가 실제 snapshot 목록과 일치합니다."
        if consistent
        else "표별 포함 건수와 실제 snapshot 목록이 다릅니다.",
    )


def inspect_boundary_artifact(
    artifact: BoundaryCaptureArtifact,
) -> BoundaryEvidenceResult:
    snapshot = artifact.snapshot
    decision_duplicates = _duplicates([item.id for item in snapshot.decisions])
    fill_duplicates = _duplicates([item.id for item in snapshot.fills])
    input_duplicates = _duplicates([item.id for item in snapshot.input_versions])
    quote_duplicates = _duplicates([item.fill_id for item in snapshot.execution_quotes])
    other_duplicates = set().union(
        _duplicates([item.symbol for item in snapshot.positions]),
        _duplicates([item.id for item in snapshot.latest_observations]),
        _duplicates([item.quote.symbol for item in snapshot.latest_observations]),
        _duplicates([item.id for item in snapshot.corporate_actions]),
        _duplicates(
            [item.action_id for item in snapshot.corporate_action_applications]
        ),
        _duplicates([item.id for item in snapshot.checkpoints]),
    )
    decisions = {item.id: item for item in snapshot.decisions}
    inputs = {item.id: item for item in snapshot.input_versions}
    quotes_by_fill = {item.fill_id: item for item in snapshot.execution_quotes}
    all_fill_details = [
        _fill_detail(
            artifact,
            fill,
            decisions,
            decision_duplicates,
            inputs,
            input_duplicates,
            quotes_by_fill,
            quote_duplicates,
        )
        for fill in sorted(snapshot.fills, key=lambda item: (item.received_at, item.id))
    ]
    failed = sum(
        any(check.state == "fail" for check in item.checks) for item in all_fill_details
    )
    unknown = sum(
        any(check.state == "unknown" for check in item.checks)
        for item in all_fill_details
    )
    positions: list[PositionEvidenceDetail] = []
    observations = {item.quote.symbol: item for item in snapshot.latest_observations}
    portfolio_inputs = [
        item.payload
        for item in snapshot.input_versions
        if item.payload_kind == "portfolio" and isinstance(item.payload, PortfolioInput)
    ]
    historical_symbols = {
        instrument.instruments[0].instrument.symbol
        for value in portfolio_inputs
        for instrument in value.instruments
    }
    fx_observations = [
        observation
        for value in portfolio_inputs
        for observation in value.external.observations
        if observation.series == "usdkrw"
    ]
    eligible_fx = [
        item
        for item in fx_observations
        if item.available_at.astimezone(UTC) <= artifact.boundary_at
        and item.observed_on <= artifact.boundary_at.date()
    ]
    for position in sorted(snapshot.positions, key=lambda item: item.symbol):
        quote = observations.get(position.symbol)
        quote_state: CheckState = (
            "unknown"
            if quote is None
            else "fail"
            if quote.quote.currency != position.currency
            or quote.quote.received_at > artifact.read_finished_at
            else "pass"
        )
        position_checks = [
            _check(
                "latest_price_candidate",
                quote_state,
                "읽기 시점 최신 시세 후보가 있습니다. 경계 시점 가격은 아닙니다."
                if quote_state == "pass"
                else "최신 시세 후보의 통화·수신 시각에 모순이 있습니다."
                if quote_state == "fail"
                else "이 종목의 최신 시세 후보가 없습니다.",
            ),
            _check(
                "latest_price_boundary_timing",
                "pass"
                if quote is not None and quote.quote.received_at <= artifact.boundary_at
                else "unknown",
                (
                    "경계까지 수신된 최신 시세 후보가 있습니다. 경계 평가 선택 "
                    "증명은 아닙니다."
                )
                if quote is not None and quote.quote.received_at <= artifact.boundary_at
                else (
                    "최신 시세가 없거나 경계 뒤 수신되어 경계 가격 후보를 "
                    "확인할 수 없습니다."
                ),
            ),
            _check(
                "historical_price_candidate",
                "pass" if position.symbol in historical_symbols else "unknown",
                "참조 입력에 이 종목의 과거 가격 자료가 있습니다."
                if position.symbol in historical_symbols
                else "참조 입력에서 과거 가격 자료를 확인할 수 없습니다.",
            ),
            _check(
                "fx_candidate_availability",
                "not_applicable"
                if position.currency == "KRW"
                else "pass"
                if eligible_fx
                else "unknown",
                "원화 종목에는 USD/KRW 후보가 필요하지 않습니다."
                if position.currency == "KRW"
                else "경계까지 이용 가능한 USD/KRW 후보가 있습니다."
                if eligible_fx
                else "경계까지 이용 가능한 USD/KRW 후보를 확인할 수 없습니다.",
            ),
            _check(
                "point_in_time_selection",
                "unknown",
                (
                    "어떤 가격·환율을 경계 평가에 선택할지는 이 원시 기록만으로 "
                    "증명되지 않습니다."
                ),
            ),
        ]
        positions.append(
            PositionEvidenceDetail(
                symbol=position.symbol,
                currency=position.currency,
                quantity=position.quantity,
                checks=position_checks,
            )
        )
    checks = [
        _check(
            "artifact_integrity",
            "pass",
            (
                "canonical schema·내용 SHA·계약·session·경계를 검증했습니다. "
                "출처 진위 증명은 아닙니다."
            ),
        ),
        _check(
            "snapshot_identity",
            "pass"
            if snapshot.session.id == artifact.session_id
            and snapshot.session.policy_hash == artifact.policy_hash
            and snapshot.session.source_run_id == artifact.source_run_id
            else "fail",
            "snapshot session·정책·source가 artifact 표제와 일치합니다."
            if snapshot.session.id == artifact.session_id
            and snapshot.session.policy_hash == artifact.policy_hash
            and snapshot.session.source_run_id == artifact.source_run_id
            else "snapshot session·정책·source와 artifact 표제가 다릅니다.",
        ),
        _check(
            "capture_completeness",
            "unknown"
            if artifact.issues or any(item.omitted_count for item in artifact.counts)
            else "pass",
            (
                f"수집 issue {len(artifact.issues)}종류가 있어 생략된 자료가 "
                "있을 수 있습니다."
            )
            if artifact.issues
            else "표별 생략 건수가 있어 원시 자료가 불완전할 수 있습니다."
            if any(item.omitted_count for item in artifact.counts)
            else "원시 수집기가 기록한 생략 issue가 없습니다.",
        ),
        _count_consistency(artifact),
        _check(
            "duplicate_identifiers",
            "fail"
            if decision_duplicates
            or fill_duplicates
            or input_duplicates
            or quote_duplicates
            or other_duplicates
            else "pass",
            "원시 기록의 식별자 또는 종목 map 키가 중복됩니다."
            if decision_duplicates
            or fill_duplicates
            or input_duplicates
            or quote_duplicates
            or other_duplicates
            else "원시 기록의 식별자와 종목 map 키 중복이 없습니다.",
        ),
        _check(
            "input_payload_hash",
            "unknown",
            (
                "입력 원문 JSON이 없어 저장된 입력 SHA를 model 재직렬화로 "
                "검증하지 않습니다."
            ),
        ),
        _check(
            "detail_limit",
            "unknown" if len(all_fill_details) > MAX_DETAILS else "not_applicable",
            f"체결 상세 {len(all_fill_details) - MAX_DETAILS}건을 표시하지 않습니다."
            if len(all_fill_details) > MAX_DETAILS
            else "체결 상세가 표시 한도 안에 있습니다.",
        ),
        _check(
            "ledger_commit_timing",
            "unknown",
            "원장 commit 시각은 artifact에 별도 기록되지 않았습니다.",
        ),
        _check(
            "corporate_action_completeness",
            "unknown",
            "기업행동 원장의 전체 완결성은 이 부분 검사로 증명되지 않습니다.",
        ),
        _check(
            "valuation_policy",
            "unknown",
            "경계 가격·환율 선택과 NAV 계산은 수행하지 않았습니다.",
        ),
    ]
    return BoundaryEvidenceResult(
        boundary=artifact.boundary,
        boundary_at=artifact.boundary_at,
        state="inspected",
        artifact_sha256=artifact.artifact_sha256,
        session_id=artifact.session_id,
        checks=checks,
        fill_total_count=len(all_fill_details),
        fill_detail_count=min(len(all_fill_details), MAX_DETAILS),
        fill_omitted_count=max(0, len(all_fill_details) - MAX_DETAILS),
        fill_failed_count=failed,
        fill_unknown_count=unknown,
        post_boundary_fill_count=sum(item.after_boundary for item in all_fill_details),
        fills=all_fill_details[:MAX_DETAILS],
        position_total_count=len(positions),
        position_detail_count=min(len(positions), MAX_DETAILS),
        position_omitted_count=max(0, len(positions) - MAX_DETAILS),
        positions=positions[:MAX_DETAILS],
        limitations=_limitations(),
    )


def boundary_evidence(
    monitor: BoundaryArtifactReader,
    boundary: BoundaryName,
    *,
    now: datetime,
) -> BoundaryEvidenceResult:
    checked_at = _utc(now)
    status = monitor.status()
    item = next(value for value in status.boundaries if value.boundary == boundary)
    empty = dict(
        boundary=boundary,
        boundary_at=item.boundary_at,
        checks=[],
        fill_total_count=0,
        fill_detail_count=0,
        fill_omitted_count=0,
        fill_failed_count=0,
        fill_unknown_count=0,
        post_boundary_fill_count=0,
        fills=[],
        position_total_count=0,
        position_detail_count=0,
        position_omitted_count=0,
        positions=[],
        limitations=_limitations(),
    )
    if checked_at < item.boundary_at:
        return BoundaryEvidenceResult(
            **empty, state="not_due", reason="boundary_not_due"
        )
    if item.state in {"scheduled", "collecting"}:
        return BoundaryEvidenceResult(
            **empty, state="missing", reason="capture_missing"
        )
    if not item.download_available:
        return BoundaryEvidenceResult(
            **empty, state="unavailable", reason="capture_unavailable"
        )
    try:
        raw, body_sha256 = monitor.artifact_body(boundary)
        if hashlib.sha256(raw).hexdigest() != body_sha256:
            raise ValueError("capture body hash is invalid")
        artifact = BoundaryCaptureArtifact.model_validate_json(raw)
    except (OSError, ValueError):
        return BoundaryEvidenceResult(
            **empty, state="unavailable", reason="capture_unavailable"
        )
    return inspect_boundary_artifact(artifact)


def _limitations() -> list[str]:
    return [
        (
            "이 검사는 원시 artifact 안의 확인 가능한 모순만 찾으며 전체 통과 "
            "판정을 만들지 않습니다."
        ),
        (
            "경계 가격·환율 선택, 원장 commit 시각, 기업행동 완결성과 NAV는 "
            "검증하지 않습니다."
        ),
        (
            "체결 환율은 별도 외부 원문 출처가 없어 판단 입력의 환율과 달라도 "
            "실패로 판정하지 않습니다."
        ),
        (
            "accepted_nav와 evaluation_inputs_complete는 항상 false이며 수익률을 "
            "계산하지 않습니다."
        ),
    ]
