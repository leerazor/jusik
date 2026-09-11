from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, time, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from jusik.research_action_collection_models import (
    CollectedAction,
    CollectedActionPayload,
)
from jusik.research_action_collection_store import ActionCollectionStore
from jusik.research_action_review import (
    EvidenceInput,
    ExtractedFacts,
    ReviewInput,
    ReviewManifest,
)
from jusik.research_action_review_store import ActionReviewStore
from jusik.research_app import create_research_app
from jusik.research_config import PAPER_BASE_URL, ResearchSettings
from jusik.research_dividend_overlay import (
    ARTIFACTS,
    ASSUMPTIONS,
    DividendOverlayRepository,
    _canonical,
    _fx_observation,
    _write_artifacts,
    calculate_scenario,
    load_review_coverage,
)
from jusik.research_dividend_overlay_models import (
    DividendCoverage,
    DividendOverlayResult,
)
from jusik.research_external_models import ExternalFeatureSnapshot, ExternalObservation
from jusik.research_models import DailyBar, ResearchInputSnapshot, ResearchRunRequest
from jusik.research_portfolio_models import (
    PortfolioCandidate,
    PortfolioEquityPoint,
    PortfolioInput,
    PortfolioMetrics,
    PortfolioPosition,
    PortfolioSimulation,
    PortfolioTrade,
)
from jusik.research_store import ResearchStore
from jusik.research_universe_data import REGISTRY
from jusik.research_universe_models import (
    CorporateAction,
    DataProvenance,
    OfflineInstrumentSnapshot,
    OfflineResearchSnapshot,
    PriceAdjustmentFactor,
    ResearchInstrument,
)

NOW = datetime(2026, 9, 10, 10, tzinfo=UTC)


class _UnusedProvider:
    async def collect(self, request: ResearchRunRequest) -> ResearchInputSnapshot:
        raise AssertionError(f"Unexpected collection request: {request}")


def _source(observations: tuple[ExternalObservation, ...]) -> PortfolioInput:
    days = [date(2024, 6, 3), date(2024, 6, 10), date(2024, 6, 11), date(2024, 6, 20)]
    bars = [
        DailyBar(
            date=day,
            open=Decimal(100),
            high=Decimal(100),
            low=Decimal(100),
            close=Decimal(100),
            volume=1000,
            adjusted_open=Decimal(100),
            adjusted_high=Decimal(100),
            adjusted_low=Decimal(100),
            adjusted_close=Decimal(100),
        )
        for day in days
    ]
    instrument = ResearchInstrument(
        symbol="NVDA",
        yahoo_symbol="NVDA",
        name="NVIDIA",
        currency="USD",
        exchange="NMS",
        timezone="America/New_York",
    )
    item = OfflineInstrumentSnapshot(
        instrument=instrument,
        bars=bars,
        provenance=DataProvenance(price_volume_source="Yahoo chart"),
        source_url="https://example.com/chart",
    )
    snapshot = OfflineResearchSnapshot(
        captured_at=NOW,
        requested_start=days[0],
        requested_end=days[-1],
        evaluation_start=days[0],
        instruments=[item],
        basis_actions=[
            CorporateAction(date=date(2024, 6, 10), numerator=10, denominator=1)
        ],
        corporate_actions=[
            CorporateAction(date=date(2024, 6, 10), numerator=10, denominator=1)
        ],
        adjustment_factors=[
            PriceAdjustmentFactor(date=day, raw_factor=Decimal(1)) for day in days
        ],
    )
    return PortfolioInput(
        captured_at=NOW,
        stock_snapshot_ids={"NVDA": "snapshot"},
        instruments=[snapshot],
        external=ExternalFeatureSnapshot(observations=observations),
    )


def _simulation(period_end: date = date(2024, 6, 20)) -> PortfolioSimulation:
    candidate = PortfolioCandidate(id="test", method="equal", gate="none")
    metrics = PortfolioMetrics(
        initial_equity_krw=Decimal(1000),
        final_equity_krw=Decimal(1000),
        total_return_pct=Decimal(0),
        max_drawdown_pct=Decimal(0),
        trade_count=2,
        transaction_cost_krw=Decimal(0),
        fx_cost_krw=Decimal(0),
        turnover_pct=Decimal(0),
    )
    trades = [
        PortfolioTrade(
            decided_at=datetime(2024, 6, 2, tzinfo=UTC),
            executed_at=datetime(2024, 6, 3, 13, 30, tzinfo=UTC),
            symbol="NVDA",
            side="buy",
            quantity=3,
            local_price=Decimal(100),
            fx_rate=Decimal(1),
            notional_krw=Decimal(300),
            transaction_cost_krw=Decimal(0),
            fx_cost_krw=Decimal(0),
        ),
        PortfolioTrade(
            decided_at=datetime(2024, 6, 9, tzinfo=UTC),
            executed_at=datetime(2024, 6, 10, 13, 30, tzinfo=UTC),
            symbol="NVDA",
            side="sell",
            quantity=5,
            local_price=Decimal(10),
            fx_rate=Decimal(1),
            notional_krw=Decimal(50),
            transaction_cost_krw=Decimal(0),
            fx_cost_krw=Decimal(0),
        ),
    ]
    final_at = datetime.combine(period_end, time(20), UTC)
    return PortfolioSimulation(
        candidate=candidate,
        period_start=date(2024, 6, 3),
        period_end=period_end,
        metrics=metrics,
        complete=True,
        incomplete_reasons=[],
        drawdown_latched=False,
        drawdown_latched_at=None,
        equity=[
            PortfolioEquityPoint(
                at=datetime(2024, 6, 3, 20, tzinfo=UTC),
                equity_krw=Decimal(1000),
                cash_krw=Decimal(700),
                drawdown_pct=Decimal(0),
            ),
            PortfolioEquityPoint(
                at=final_at,
                equity_krw=Decimal(1000),
                cash_krw=Decimal(750),
                drawdown_pct=Decimal(0),
            ),
        ],
        trades=trades,
        weekly_targets=[],
        positions=[
            PortfolioPosition(
                symbol="NVDA",
                quantity=25,
                currency="USD",
                local_close=Decimal(10),
                fx_rate=Decimal(1),
                value_krw=Decimal(250),
                weight=Decimal("0.25"),
                valued_at=final_at,
                fx_observed_on=period_end,
            )
        ],
        contributions_krw={},
        split_cash_in_lieu_krw={},
        overlap_diagnostics={},
    )


def _eligible(payment: date = date(2024, 6, 28)) -> DividendCoverage:
    return DividendCoverage(
        event_id="event",
        revision_id="revision",
        symbol="NVDA",
        vendor_date=date(2024, 6, 11),
        status="eligible",
        reason=None,
        review_id="review",
        ex_dividend_date=date(2024, 6, 11),
        payment_date=payment,
        amount=Decimal("0.01"),
        currency="USD",
    )


def _stored_overlay(report_dir: Path) -> DividendOverlayResult:
    identity: dict[str, object] = {
        "source_run_id": "1" * 64,
        "source_manifest_sha256": "2" * 64,
        "source_result_sha256": "3" * 64,
        "review_snapshot_sha256": "4" * 64,
        "calendar_sha256": "5" * 64,
        "code_sha256": "6" * 64,
        "assumptions": ASSUMPTIONS,
    }
    run_id = hashlib.sha256(_canonical(identity).encode()).hexdigest()
    result = DividendOverlayResult(
        run_id=run_id,
        created_at=NOW,
        calculation_complete=True,
        calculation_reasons=[],
        current_dividend_revision_count=0,
        eligible_dividend_count=0,
        excluded_dividend_count=0,
        in_period_eligible_count=0,
        in_period_excluded_count=0,
        coverage=[],
        entitlements=[],
        ledger=[],
        equity=[],
        position_reconciliations=[],
        comparisons=[],
        artifacts=list(ARTIFACTS),
        **identity,
    )
    _write_artifacts(
        report_dir,
        report_dir / "dividend-overlay-runs" / run_id,
        result,
        identity,
    )
    return result


def test_split_precedes_trade_and_payment_after_horizon_stays_receivable() -> None:
    source = _source(
        (
            ExternalObservation(
                series="usdkrw",
                observed_on=date(2024, 6, 19),
                value=Decimal(1300),
                available_at=datetime(2024, 6, 20, tzinfo=UTC),
                revision="r1",
            ),
        )
    )
    entitlements, ledger, equity, reconciliation, reasons = calculate_scenario(
        "heldout", _simulation(), source, [_eligible()]
    )
    assert reasons == []
    assert entitlements[0].entitled_quantity == 25
    assert entitlements[0].gross_native == Decimal("0.25")
    assert [point.kind for point in ledger] == ["accrual"]
    assert equity[-1].receivable_native == {"KRW": Decimal(0), "USD": Decimal("0.25")}
    assert equity[-1].cash_native == {"KRW": Decimal(0), "USD": Decimal(0)}
    assert reconciliation.matches
    assert reconciliation.replayed_quantities == {"NVDA": 25}


def test_native_ledger_preserves_long_decimal_through_payment() -> None:
    amount = Decimal("0.123456789012345678901234567891")
    source = _source(
        (
            ExternalObservation(
                series="usdkrw",
                observed_on=date(2024, 6, 19),
                value=Decimal(1300),
                available_at=datetime(2024, 6, 20, tzinfo=UTC),
                revision="r1",
            ),
        )
    )
    event = _eligible(payment=date(2024, 6, 12)).model_copy(update={"amount": amount})
    entitlements, ledger, _equity, _reconciliation, reasons = calculate_scenario(
        "heldout", _simulation(), source, [event]
    )
    expected = Decimal("3.086419725308641972530864197275")
    assert reasons == []
    assert entitlements[0].gross_native == expected
    assert ledger[-1].receivable_after_native == Decimal(0)
    assert ledger[-1].cash_after_native == expected


def test_fx_uses_utc_boundary_latest_revision_and_seven_day_limit() -> None:
    at = datetime(2024, 6, 20, 9, tzinfo=timezone(timedelta(hours=9)))
    observations = (
        ExternalObservation(
            series="usdkrw",
            observed_on=date(2024, 6, 13),
            value=Decimal(1290),
            available_at=datetime(2024, 6, 19, tzinfo=UTC),
            revision="a",
        ),
        ExternalObservation(
            series="usdkrw",
            observed_on=date(2024, 6, 13),
            value=Decimal(1300),
            available_at=datetime(2024, 6, 20, tzinfo=UTC),
            revision="b",
        ),
        ExternalObservation(
            series="usdkrw",
            observed_on=date(2024, 6, 20),
            value=Decimal(1400),
            available_at=datetime(2024, 6, 20, 1, tzinfo=UTC),
            revision="future",
        ),
        ExternalObservation(
            series="usdkrw",
            observed_on=date(2024, 6, 12),
            value=Decimal(1200),
            available_at=datetime(2024, 6, 19, tzinfo=UTC),
            revision="stale",
        ),
    )
    selected = _fx_observation(_source(observations), at)
    assert selected is not None
    assert selected.value == Decimal(1300)
    assert selected.revision == "b"


def test_conflicting_split_and_duplicate_trade_fail_reconciliation() -> None:
    source = _source(())
    snapshot = source.instruments[0]
    conflicting = snapshot.model_copy(
        update={
            "basis_actions": [
                CorporateAction(date=date(2024, 6, 10), numerator=2, denominator=1)
            ]
        }
    )
    source = source.model_copy(update={"instruments": [conflicting]})
    simulation = _simulation().model_copy(
        update={"trades": [*_simulation().trades, _simulation().trades[1]]}
    )
    _entitlements, _ledger, _equity, reconciliation, reasons = calculate_scenario(
        "heldout", simulation, source, [_eligible()]
    )
    assert "duplicate_source_trade" in reasons
    assert "unsupported_or_unresolved_split:NVDA:2024-06-10" in reasons
    assert "negative_quantity:NVDA" in reasons
    assert "final_position_reconciliation_failed" in reasons
    assert not reconciliation.matches


def test_latest_review_only_and_missing_required_fact_are_excluded(
    tmp_path: Path,
) -> None:
    database = tmp_path / "actions.db"
    collection = ActionCollectionStore(database)
    collection.ensure_sources(REGISTRY, NOW)
    attempt = collection.begin_attempt(
        "NVDA", date(2023, 9, 11), date(2026, 9, 10), NOW
    )
    collection.complete_success(
        attempt_id=attempt,
        completed_at=NOW,
        http_status=200,
        request_url="https://query1.finance.yahoo.com/test",
        body=b"{}",
        actions=[
            CollectedAction(
                provider_key="dividend",
                kind="dividend",
                payload=CollectedActionPayload(
                    vendor_date=date(2024, 6, 11), amount="0.01", currency="USD"
                ),
            )
        ],
    )
    revision = collection.revision_page(None, 10).items[0]
    document = tmp_path / "official.body"
    document.write_bytes(b"official")
    evidence = EvidenceInput(
        local_file=document,
        sha256=hashlib.sha256(b"official").hexdigest(),
        source_url="https://issuer.example/dividend",
        publisher="Issuer",
        locator="table",
        captured_at=NOW - timedelta(minutes=1),
    )
    store = ActionReviewStore(database)
    common = dict(
        revision_id=revision.id,
        content_sha256=revision.content_sha256,
        operator_verified=True,
        evidence=evidence,
    )
    matched = ReviewInput(
        review_key="matched",
        extracted_facts=ExtractedFacts(
            amount="0.01",
            currency="USD",
            comparable_share_basis=True,
            ex_dividend_date=date(2024, 6, 11),
            payment_date=date(2024, 6, 28),
        ),
        **common,
    )
    store.import_manifest(ReviewManifest(schema_version=1, reviews=[matched]), NOW)
    missing = ReviewInput(
        review_key="missing",
        extracted_facts=matched.extracted_facts.model_copy(
            update={"payment_date": None}
        ),
        **common,
    )
    store.import_manifest(
        ReviewManifest(schema_version=1, reviews=[missing]), NOW + timedelta(seconds=1)
    )
    coverage, snapshot_hash = load_review_coverage(database)
    assert snapshot_hash
    assert coverage[0].status == "excluded"
    assert coverage[0].reason == "required_official_fact_missing"


def test_repository_and_api_verify_artifact_hashes_and_allowlist(
    tmp_path: Path,
) -> None:
    reports = tmp_path / "reports"
    result = _stored_overlay(reports)
    repository = DividendOverlayRepository(reports)
    assert repository.latest() == result
    assert repository.artifact(result.run_id, "ledger.csv").name == "ledger.csv"
    with pytest.raises(ValueError):
        repository.artifact(result.run_id, "../result.json")

    manifest_path = reports / "dividend-overlay-runs" / result.run_id / "manifest.json"
    original_manifest = manifest_path.read_text(encoding="utf-8")
    manifest = json.loads(original_manifest)
    manifest["code_sha256"] = "9" * 64
    manifest_path.write_text(_canonical(manifest) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="identity hash mismatch"):
        repository.latest()
    manifest_path.write_text(original_manifest, encoding="utf-8")

    settings = ResearchSettings(
        app_key="key",
        app_secret="secret",
        base_url=PAPER_BASE_URL,
        db_path=tmp_path / "research.db",
    )
    app = create_research_app(
        settings=settings,
        store=ResearchStore(tmp_path / "research.db"),
        provider=_UnusedProvider(),
        action_collection_enabled=False,
        dividend_report_dir=reports,
    )
    with TestClient(app) as client:
        response = client.get("/api/research/portfolio/dividends/latest")
        assert response.status_code == 200
        assert response.json()["run_id"] == result.run_id
        artifact = client.get(
            f"/api/research/portfolio/dividends/runs/{result.run_id}/artifacts/ledger.csv"
        )
        assert artifact.status_code == 200
        assert artifact.headers["x-content-type-options"] == "nosniff"

    artifact_path = reports / "dividend-overlay-runs" / result.run_id / "ledger.csv"
    artifact_path.write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="artifact mismatch"):
        repository.latest()
