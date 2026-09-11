from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

import jusik.research_app as research_app_module
from jusik.research_app import create_research_app
from jusik.research_boundary_capture import (
    BoundaryCaptureArtifact,
    BoundaryCaptureArtifactContent,
    BoundaryCaptureCount,
    BoundaryCaptureItemStatus,
    BoundaryCaptureStatus,
    BoundaryExecutionQuote,
    BoundaryInputVersion,
    BoundaryLatestObservation,
    BoundaryName,
    BoundaryRawSnapshot,
    BoundaryRiskInput,
    CaptureState,
    _artifact,
    _artifact_bytes,
)
from jusik.research_boundary_evidence import (
    BoundaryEvidenceResult,
    boundary_evidence,
    inspect_boundary_artifact,
)
from jusik.research_config import PAPER_BASE_URL, ResearchSettings
from jusik.research_forward_models import (
    ForwardConfig,
    ForwardDecision,
    ForwardFill,
    ForwardPosition,
    ForwardSession,
)
from jusik.research_models import ResearchInputSnapshot, ResearchRunRequest
from jusik.research_prospective_registration import (
    EVALUATION_END_AT,
    EVALUATION_START_AT,
)
from jusik.research_quote_models import ResearchQuote
from jusik.research_store import ResearchStore

SESSION_ID = "a" * 64
DECISION_ID = "b" * 64
INPUT_ID = "c" * 64
FILL_ID = "d" * 64
ARTIFACT_SHA = "e" * 64


class _Reader:
    def __init__(
        self,
        artifact: BoundaryCaptureArtifact | None,
        *,
        state: CaptureState = "captured_raw",
        corrupt: bool = False,
    ) -> None:
        self.artifact = artifact
        self.state = state
        self.corrupt = corrupt

    def status(self) -> BoundaryCaptureStatus:
        start = BoundaryCaptureItemStatus(
            boundary="start",
            boundary_at=EVALUATION_START_AT,
            state=self.state,
            artifact_sha256=(self.artifact.artifact_sha256 if self.artifact else None),
            issue_count=0,
            download_available=self.artifact is not None
            and self.state.startswith("captured"),
        )
        return BoundaryCaptureStatus(
            checked_at=EVALUATION_START_AT,
            session_id=SESSION_ID,
            running=False,
            last_poll_at=None,
            collector_startup_sha256="f" * 64,
            collector_current_sha256="f" * 64,
            boundaries=[
                start,
                BoundaryCaptureItemStatus(
                    boundary="end",
                    boundary_at=EVALUATION_END_AT,
                    state="scheduled",
                    issue_count=0,
                    download_available=False,
                ),
            ],
            limitations=[],
        )

    def artifact_body(self, boundary: BoundaryName) -> tuple[bytes, str]:
        assert boundary == "start"
        if self.corrupt or self.artifact is None:
            raise ValueError("fixture artifact unavailable")
        body = _artifact_bytes(self.artifact)
        return body, hashlib.sha256(body).hexdigest()


class _UnusedProvider:
    async def collect(self, request: ResearchRunRequest) -> ResearchInputSnapshot:
        raise AssertionError(f"unexpected request: {request}")


def _quote(
    *,
    symbol: str = "NVDA",
    market_at: datetime | None = None,
    received_at: datetime | None = None,
    price: Decimal = Decimal("100"),
    ask: Decimal = Decimal("100"),
) -> ResearchQuote:
    market = market_at or EVALUATION_START_AT
    received = received_at or EVALUATION_START_AT + timedelta(seconds=1)
    return ResearchQuote(
        symbol=symbol,
        exchange="NAS",
        currency="USD",
        price=price,
        ask=ask,
        bid=price,
        volume=1,
        accumulated_volume=1,
        market_at=market,
        received_at=received,
        source="KIS HDFSCNT0",
    )


def _artifact_fixture(
    *,
    fills: list[ForwardFill] | None = None,
    quote: ResearchQuote | None = None,
    include_decision: bool = True,
    include_input: bool = True,
    include_execution_quote: bool = True,
    policy_hash: str = "1" * 64,
    session_policy_hash: str | None = None,
    wrong_counts: bool = False,
) -> BoundaryCaptureArtifact:
    config = ForwardConfig()
    session = ForwardSession(
        id=SESSION_ID,
        activated_at=EVALUATION_START_AT - timedelta(days=3),
        next_due_at=EVALUATION_START_AT,
        source_run_id="fixed-source",
        policy_hash=session_policy_hash or policy_hash,
        config=config,
        state="observing",
        cash_krw=Decimal("100000000"),
        lifetime_high_water_krw=Decimal("100000000"),
        episode_high_water_krw=Decimal("100000000"),
    )
    decision = ForwardDecision(
        id=DECISION_ID,
        session_id=SESSION_ID,
        due_at=EVALUATION_START_AT,
        recorded_at=EVALUATION_START_AT - timedelta(minutes=1),
        input_version=INPUT_ID,
        state="completed",
        reason="fixture",
        expires_at=EVALUATION_START_AT + timedelta(days=1),
        target_weights={"NVDA": Decimal("0.1")},
        intents=[],
    )
    source_quote = quote or _quote()
    assert source_quote.ask is not None
    local_price = source_quote.ask * (Decimal(1) + config.slippage_rate)
    with localcontext(Context(prec=28, rounding=ROUND_HALF_EVEN)):
        notional = local_price * 2 * Decimal("1300")
    default_fill = ForwardFill(
        id=FILL_ID,
        session_id=SESSION_ID,
        decision_id=DECISION_ID,
        symbol="NVDA",
        side="buy",
        quantity=2,
        market_at=source_quote.market_at,
        received_at=source_quote.received_at,
        local_price=local_price,
        fx_rate=Decimal("1300"),
        notional_krw=notional,
        transaction_cost_krw=Decimal("260.26"),
        fx_cost_krw=Decimal("260.26"),
        cash_after_krw=Decimal("99739219.48"),
        quote_id="9" * 64,
    )
    actual_fills = fills if fills is not None else [default_fill]
    decisions = [decision] if include_decision else []
    inputs = (
        [
            BoundaryInputVersion(
                id=INPUT_ID,
                cutoff_at=decision.recorded_at,
                recorded_at=decision.recorded_at,
                payload_sha256="2" * 64,
                payload_kind="risk_checkpoint",
                payload=BoundaryRiskInput(
                    checkpoint_at=decision.recorded_at,
                    actually_known_at=decision.recorded_at,
                    equity_krw=Decimal("100000000"),
                    positions_asof={},
                    stock_snapshot_ids={},
                ),
            )
        ]
        if include_input
        else []
    )
    execution_quotes = (
        [
            BoundaryExecutionQuote(
                fill_id=FILL_ID,
                quote=source_quote,
                quote_sha256="3" * 64,
                captured_at=source_quote.received_at,
            )
        ]
        if include_execution_quote
        else []
    )
    positions = [
        ForwardPosition(
            symbol="NVDA",
            currency="USD",
            quantity=2,
            average_cost_krw=Decimal("130390.26"),
            updated_at=source_quote.received_at,
        )
    ]
    observations = [
        BoundaryLatestObservation(
            id="4" * 64,
            persisted_reason="fill",
            quote=source_quote,
        )
    ]
    snapshot = BoundaryRawSnapshot(
        session=session,
        positions=positions,
        decisions=decisions,
        fills=actual_fills,
        execution_quotes=execution_quotes,
        input_versions=inputs,
        corporate_actions=[],
        corporate_action_applications=[],
        checkpoints=[],
        latest_observations=observations,
    )
    table_values = {
        "forward_sessions": 1,
        "forward_positions": len(positions),
        "forward_decisions": len(decisions),
        "forward_fills": len(actual_fills),
        "forward_execution_quotes": len(execution_quotes),
        "forward_input_versions": len(inputs),
        "forward_corporate_action_metadata": 0,
        "forward_corporate_action_applications": 0,
        "forward_checkpoints": 0,
        "latest_forward_observations": len(observations),
    }
    counts = [
        BoundaryCaptureCount(
            table=table,
            total_count=count + (1 if wrong_counts and table == "forward_fills" else 0),
            included_count=count
            + (1 if wrong_counts and table == "forward_fills" else 0),
            omitted_count=0,
        )
        for table, count in table_values.items()
    ]
    return _artifact(
        BoundaryCaptureArtifactContent(
            session_id=SESSION_ID,
            boundary="start",
            boundary_at=EVALUATION_START_AT,
            read_started_at=EVALUATION_START_AT + timedelta(seconds=2),
            read_finished_at=EVALUATION_START_AT + timedelta(seconds=3),
            monotonic_duration_seconds=Decimal("1"),
            capture_lag_seconds=Decimal("2"),
            contract_sha256="5" * 64,
            policy_hash=policy_hash,
            source_run_id="fixed-source",
            collector_startup_sha256="6" * 64,
            collector_capture_sha256="6" * 64,
            snapshot=snapshot,
            counts=counts,
            issues=[],
        )
    )


def _state(result: BoundaryEvidenceResult, name: str) -> str:
    return next(item.state for item in result.checks if item.name == name)


def _with_decision_times(
    artifact: BoundaryCaptureArtifact,
    *,
    recorded_at: datetime,
    expires_at: datetime,
) -> BoundaryCaptureArtifact:
    decision = artifact.snapshot.decisions[0].model_copy(
        update={"recorded_at": recorded_at, "expires_at": expires_at}
    )
    snapshot = artifact.snapshot.model_copy(update={"decisions": [decision]})
    payload = artifact.model_dump(mode="python", exclude={"artifact_sha256"})
    payload["snapshot"] = snapshot
    return _artifact(BoundaryCaptureArtifactContent.model_validate(payload))


def test_normal_artifact_reproduces_exact_prices_without_approving_nav() -> None:
    artifact = _artifact_fixture()
    first = inspect_boundary_artifact(artifact)
    second = inspect_boundary_artifact(artifact)
    assert first == second
    assert first.state == "inspected"
    assert first.accepted_nav is False
    assert first.evaluation_inputs_complete is False
    assert first.fill_failed_count == 0
    assert first.post_boundary_fill_count == 1
    assert first.fills[0].expected_local_price == first.fills[0].stored_local_price
    assert first.fills[0].expected_notional_krw == first.fills[0].stored_notional_krw
    assert (
        next(
            check.state
            for check in first.fills[0].checks
            if check.name == "boundary_timing_diagnostic"
        )
        == "not_applicable"
    )
    assert first.positions[0].checks[-1].state == "unknown"


def test_fill_symbol_time_amount_and_identity_mismatches_fail_exactly() -> None:
    source = _quote(symbol="MSFT", market_at=EVALUATION_START_AT + timedelta(seconds=2))
    base = _artifact_fixture(include_execution_quote=False).snapshot.fills[0]
    bad_fill = base.model_copy(
        update={
            "notional_krw": base.notional_krw + Decimal("0.0000000001"),
            "market_at": EVALUATION_START_AT,
        }
    )
    artifact = _artifact_fixture(
        fills=[bad_fill],
        quote=source,
        policy_hash="1" * 64,
        session_policy_hash="7" * 64,
        wrong_counts=True,
    )
    result = inspect_boundary_artifact(artifact)
    assert result.fill_failed_count == 1
    states = {item.name: item.state for item in result.fills[0].checks}
    assert states["symbol_consistency"] == "fail"
    assert states["timestamp_consistency"] == "fail"
    assert states["notional_arithmetic"] == "fail"
    assert _state(result, "snapshot_identity") == "fail"
    assert _state(result, "captured_counts") == "fail"


def test_decision_timing_uses_market_time_and_does_not_invent_processing_time() -> None:
    recorded = EVALUATION_START_AT
    expires = recorded + timedelta(seconds=1)
    eligible_quote = _quote(
        market_at=recorded + timedelta(seconds=1),
        received_at=recorded + timedelta(seconds=2),
    )
    eligible = inspect_boundary_artifact(
        _with_decision_times(
            _artifact_fixture(quote=eligible_quote),
            recorded_at=recorded,
            expires_at=expires,
        )
    )
    eligible_states = {item.name: item.state for item in eligible.fills[0].checks}
    assert eligible_states["decision_timing"] == "pass"
    assert eligible_states["decision_expiration"] == "unknown"
    assert eligible.fill_failed_count == 0

    ineligible_quote = _quote(
        market_at=recorded - timedelta(seconds=1),
        received_at=recorded + timedelta(seconds=1),
    )
    ineligible = inspect_boundary_artifact(
        _with_decision_times(
            _artifact_fixture(quote=ineligible_quote),
            recorded_at=recorded,
            expires_at=expires,
        )
    )
    ineligible_states = {item.name: item.state for item in ineligible.fills[0].checks}
    assert ineligible_states["decision_timing"] == "fail"
    assert ineligible_states["decision_expiration"] == "unknown"
    assert ineligible.fill_failed_count == 1


def test_missing_references_and_detail_limit_are_unknown_not_pass() -> None:
    base = _artifact_fixture(
        include_decision=False, include_input=False
    ).snapshot.fills[0]
    fills = [
        base.model_copy(update={"id": f"{number:064x}"}) for number in range(1, 52)
    ]
    result = inspect_boundary_artifact(
        _artifact_fixture(
            fills=fills,
            include_decision=False,
            include_input=False,
            include_execution_quote=False,
        )
    )
    assert result.fill_total_count == 51
    assert result.fill_detail_count == 50
    assert result.fill_omitted_count == 1
    assert result.fill_unknown_count == 51
    assert _state(result, "detail_limit") == "unknown"


def test_duplicate_map_keys_fail_without_hiding_the_second_row() -> None:
    source = _artifact_fixture()
    decision = source.snapshot.decisions[0]
    snapshot = source.snapshot.model_copy(update={"decisions": [decision, decision]})
    counts = [
        item.model_copy(update={"total_count": 2, "included_count": 2})
        if item.table == "forward_decisions"
        else item
        for item in source.counts
    ]
    payload = source.model_dump(mode="python", exclude={"artifact_sha256"})
    payload.update({"snapshot": snapshot, "counts": counts})
    artifact = _artifact(BoundaryCaptureArtifactContent.model_validate(payload))
    result = inspect_boundary_artifact(artifact)
    assert _state(result, "duplicate_identifiers") == "fail"
    assert result.fills[0].checks[1].state == "fail"


def test_long_decimal_notional_uses_store_precision_28() -> None:
    price = Decimal("0.123456789012345678901234567891")
    fx = Decimal("1355.4100341796875")
    quote = _quote(price=price, ask=price)
    base = _artifact_fixture(quote=quote).snapshot.fills[0]
    with localcontext(Context(prec=28, rounding=ROUND_HALF_EVEN)):
        notional = base.local_price * base.quantity * fx
    fill = base.model_copy(update={"fx_rate": fx, "notional_krw": notional})
    result = inspect_boundary_artifact(_artifact_fixture(quote=quote, fills=[fill]))
    assert (
        next(
            check.state
            for check in result.fills[0].checks
            if check.name == "notional_arithmetic"
        )
        == "pass"
    )


def test_boundary_availability_distinguishes_not_due_missing_and_corrupt() -> None:
    artifact = _artifact_fixture()
    not_due = boundary_evidence(
        _Reader(None, state="scheduled"),
        "start",
        now=EVALUATION_START_AT - timedelta(microseconds=1),
    )
    missing = boundary_evidence(
        _Reader(None, state="scheduled"), "start", now=EVALUATION_START_AT
    )
    corrupt = boundary_evidence(
        _Reader(artifact, corrupt=True), "start", now=EVALUATION_START_AT
    )
    assert (not_due.state, missing.state, corrupt.state) == (
        "not_due",
        "missing",
        "unavailable",
    )


def test_api_returns_typed_boundary_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    expected = inspect_boundary_artifact(_artifact_fixture())
    monkeypatch.setattr(
        research_app_module, "boundary_evidence", lambda *_, **__: expected
    )
    settings = ResearchSettings(
        app_key=SecretStr("key"),
        app_secret=SecretStr("secret"),
        base_url=PAPER_BASE_URL,
        db_path=tmp_path / "research.db",
    )
    app = create_research_app(
        settings=settings,
        store=ResearchStore(tmp_path / "research.db"),
        provider=_UnusedProvider(),
        forward_db_path=tmp_path / "forward.db",
        boundary_capture_dir=tmp_path / "captures",
        action_collection_enabled=False,
    )
    with TestClient(app) as client:
        response = client.get(
            "/api/research/validation/prospective/boundary-evidence/start"
        )
        invalid = client.get(
            "/api/research/validation/prospective/boundary-evidence/other"
        )
    assert response.status_code == 200
    assert response.json()["accepted_nav"] is False
    assert invalid.status_code == 422
