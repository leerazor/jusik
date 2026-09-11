from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from jusik.kis_stream import parse_research_frame, research_subscriptions
from jusik.research_app import create_research_app
from jusik.research_config import PAPER_BASE_URL, ResearchSettings
from jusik.research_external_models import ExternalObservation
from jusik.research_external_store import ExternalStore
from jusik.research_forward import ForwardCoordinator
from jusik.research_forward_models import (
    ForwardConfig,
    ForwardDecision,
    ForwardIntent,
)
from jusik.research_forward_store import ForwardStore
from jusik.research_models import ResearchInputSnapshot, ResearchRunRequest
from jusik.research_portfolio_models import PortfolioCandidate
from jusik.research_portfolio_robustness import (
    ARTIFACTS,
    SPECIFICATION,
    OosEvaluation,
    OosRole,
    PortfolioRobustnessRepository,
    PortfolioRobustnessResult,
    RobustnessFold,
    RobustnessMetric,
    _aggregates,
    _canonical,
    _write,
    fold_boundaries,
)
from jusik.research_quote_models import ResearchFeedStatus, ResearchQuote
from jusik.research_signal_validation import (
    latest_completed_signal_date,
    validate_signal_store,
)
from jusik.research_store import ResearchStore
from jusik.research_universe_data import REGISTRY
from jusik.research_universe_store import UniverseInputStore


class _UnusedProvider:
    async def collect(self, request: ResearchRunRequest) -> ResearchInputSnapshot:
        raise AssertionError(f"Unexpected collection request: {request}")


def _quote(
    market_at: datetime,
    *,
    received_at: datetime | None = None,
    price: str = "100",
) -> ResearchQuote:
    return ResearchQuote(
        symbol="NVDA",
        exchange="NAS",
        currency="USD",
        price=Decimal(price),
        ask=Decimal(price),
        bid=Decimal(price),
        volume=1,
        accumulated_volume=1,
        market_at=market_at,
        received_at=received_at or market_at + timedelta(seconds=1),
        source="KIS HDFSCNT0",
    )


def _fill_setup(
    path: Path,
) -> tuple[ForwardStore, ForwardDecision, ForwardIntent, str]:
    store = ForwardStore(path)
    activated = datetime(2026, 9, 10, 13, 29, tzinfo=UTC)
    session = store.activate(
        activated_at=activated,
        next_due_at=activated + timedelta(minutes=30),
        source_run_id="fixed",
        config=ForwardConfig(),
    )
    input_version = store.save_input_version(
        session.id, activated + timedelta(minutes=20), {"test": True}
    )
    intent = ForwardIntent(
        symbol="NVDA",
        side="buy",
        target_weight=Decimal("0.2"),
        budget_krw=Decimal("20000000"),
        state="pending",
        reason="test",
    )
    decision = store.record_decision(
        session_id=session.id,
        due_at=activated + timedelta(minutes=30),
        recorded_at=activated + timedelta(minutes=29),
        input_version=input_version,
        reason="test",
        expires_at=activated + timedelta(days=7),
        target_weights={"NVDA": Decimal("0.2")},
        intents=[intent],
    )
    return store, decision, intent, session.id


def test_execution_quote_captures_later_same_minute_and_is_idempotent(
    tmp_path: Path,
) -> None:
    database = tmp_path / "forward.db"
    store, decision, intent, session_id = _fill_setup(database)
    first = _quote(datetime(2026, 9, 10, 14, 0, 1, tzinfo=UTC), price="100")
    sample = store.save_observation(session_id, first)
    actual = _quote(datetime(2026, 9, 10, 14, 0, 20, tzinfo=UTC), price="101")
    fill = store.apply_fill(
        decision=decision,
        intent=intent,
        quote=actual,
        quote_id=sample.id,
        fx_rate=Decimal("1300"),
        quantity=1,
        local_fill_price=Decimal("101"),
        transaction_cost_krw=Decimal(0),
        fx_cost_krw=Decimal(0),
    )
    assert fill is not None
    duplicate = store.apply_fill(
        decision=decision,
        intent=intent,
        quote=actual.model_copy(update={"price": Decimal("102")}),
        quote_id="different",
        fx_rate=Decimal("1300"),
        quantity=1,
        local_fill_price=Decimal("102"),
        transaction_cost_krw=Decimal(0),
        fx_cost_krw=Decimal(0),
    )
    assert duplicate == fill
    with sqlite3.connect(database) as connection:
        assert (
            connection.execute(
                "SELECT count(*) FROM forward_execution_quotes"
            ).fetchone()[0]
            == 1
        )
    result = validate_signal_store(
        database,
        local_date=date(2026, 9, 10),
        now=datetime(2026, 9, 11, tzinfo=UTC),
    )
    evidence = result.executions[0]
    assert evidence.evidence == "captured"
    assert evidence.quote_id == sample.id
    assert evidence.execution_quote is not None
    assert evidence.execution_quote.price == Decimal("101")
    assert evidence.input_cutoff_at == datetime(2026, 9, 10, 13, 49, tzinfo=UTC)


def test_parsed_second_quote_flows_through_coordinator_to_execution_sidecar(
    tmp_path: Path,
) -> None:
    database = tmp_path / "forward.db"
    store = ForwardStore(database)
    activated = datetime(2026, 9, 10, 13, 30, tzinfo=UTC)
    session = store.activate(
        activated_at=activated,
        next_due_at=activated + timedelta(days=4),
        source_run_id="fixed",
        config=ForwardConfig(),
    )
    external = ExternalStore(tmp_path / "external.db")
    external.save_success(
        "test",
        body=b"fx",
        content_type="application/json",
        observations=[
            ExternalObservation(
                series="usdkrw",
                observed_on=date(2026, 9, 9),
                value=Decimal("1300"),
                available_at=datetime(2026, 9, 10, tzinfo=UTC),
                revision="test",
            )
        ],
        captured_at=datetime(2026, 9, 10, tzinfo=UTC),
    )
    current = datetime(2026, 9, 10, 14, 0, 2, tzinfo=UTC)
    coordinator = ForwardCoordinator(
        store,
        UniverseInputStore(tmp_path / "universe.db"),
        external,
        lambda: ResearchFeedStatus(
            state="disabled", detail="test", configured=False, items=[]
        ),
        now=lambda: current,
    )
    subscriptions = research_subscriptions(REGISTRY)

    def parsed(clock: str, price: str, received_at: datetime) -> ResearchQuote:
        fields = ["0"] * 25
        fields[0] = "NVDA"
        fields[3] = "20260910"
        fields[4] = clock
        fields[10] = price
        fields[14] = price
        fields[15] = price
        fields[18] = "1"
        fields[19] = "1"
        return parse_research_frame(
            f"0|HDFSCNT0|1|{'^'.join(fields)}",
            subscriptions,
            received_at=received_at,
        )[0]

    coordinator.on_quote(parsed("100001", "100", current))
    first_sample = store.observations(session.id, 1)[0]
    input_version = store.save_input_version(
        session.id, current, {"candidate": "fixed"}
    )
    intent = ForwardIntent(
        symbol="NVDA",
        side="buy",
        target_weight=Decimal("0.2"),
        budget_krw=Decimal("20000000"),
        state="pending",
        reason="test",
    )
    store.record_decision(
        session_id=session.id,
        due_at=current,
        recorded_at=current,
        input_version=input_version,
        reason="test",
        expires_at=current + timedelta(days=1),
        target_weights={"NVDA": Decimal("0.2")},
        intents=[intent],
    )
    current = datetime(2026, 9, 10, 14, 0, 21, tzinfo=UTC)
    coordinator.on_quote(parsed("100020", "101", current))
    result = validate_signal_store(
        database,
        local_date=date(2026, 9, 10),
        now=datetime(2026, 9, 11, tzinfo=UTC),
    )
    assert len(result.executions) == 1
    evidence = result.executions[0]
    assert evidence.evidence == "captured"
    assert evidence.quote_id == first_sample.id
    assert evidence.execution_quote is not None
    assert evidence.execution_quote.price == Decimal("101")


def test_fill_on_later_date_resolves_original_decision_and_input(
    tmp_path: Path,
) -> None:
    database = tmp_path / "forward.db"
    store, decision, intent, session_id = _fill_setup(database)
    quote = _quote(datetime(2026, 9, 11, 14, tzinfo=UTC))
    sample = store.save_observation(session_id, quote)
    fill = store.apply_fill(
        decision=decision,
        intent=intent,
        quote=quote,
        quote_id=sample.id,
        fx_rate=Decimal("1300"),
        quantity=1,
        local_fill_price=Decimal("100"),
        transaction_cost_krw=Decimal(0),
        fx_cost_krw=Decimal(0),
    )
    assert fill is not None
    result = validate_signal_store(
        database,
        local_date=date(2026, 9, 11),
        now=datetime(2026, 9, 11, 22, tzinfo=UTC),
    )
    assert result.decisions == []
    assert len(result.executions) == 1
    assert result.executions[0].decision_id == decision.id
    assert result.executions[0].input_cutoff_at == datetime(
        2026, 9, 10, 13, 49, tzinfo=UTC
    )
    assert result.executions[0].evidence == "captured"


def test_execution_quote_failure_rolls_back_fill_cash_and_position(
    tmp_path: Path,
) -> None:
    database = tmp_path / "forward.db"
    store, decision, intent, session_id = _fill_setup(database)
    before = store.active_session()
    with sqlite3.connect(database) as connection:
        connection.execute(
            """CREATE TRIGGER reject_execution_quote BEFORE INSERT
            ON forward_execution_quotes BEGIN SELECT RAISE(ABORT, 'test'); END"""
        )
    with pytest.raises(sqlite3.IntegrityError):
        store.apply_fill(
            decision=decision,
            intent=intent,
            quote=_quote(datetime(2026, 9, 10, 14, tzinfo=UTC)),
            quote_id="sample",
            fx_rate=Decimal("1300"),
            quantity=1,
            local_fill_price=Decimal("100"),
            transaction_cost_krw=Decimal(0),
            fx_cost_krw=Decimal(0),
        )
    assert store.fills(session_id) == []
    assert store.positions(session_id) == []
    assert store.active_session() == before


def test_signal_boundaries_use_raw_latency_and_completed_minutes(
    tmp_path: Path,
) -> None:
    database = tmp_path / "forward.db"
    store = ForwardStore(database)
    session = store.activate(
        activated_at=datetime(2026, 9, 10, 13, 29, 33, tzinfo=UTC),
        next_due_at=datetime(2026, 9, 14, tzinfo=UTC),
        source_run_id="fixed",
        config=ForwardConfig(),
    )
    market = datetime(2026, 9, 10, 13, 30, 3, tzinfo=UTC)
    store.save_observation(
        session.id,
        _quote(market, received_at=market - timedelta(seconds=2)),
    )
    store.save_observation(
        session.id,
        _quote(
            market + timedelta(microseconds=1),
            received_at=market - timedelta(seconds=2),
        ),
        reason="fill",
    )
    second = market + timedelta(minutes=1)
    store.save_observation(
        session.id,
        _quote(second, received_at=second + timedelta(seconds=15)),
    )
    third = market + timedelta(minutes=2)
    store.save_observation(
        session.id,
        _quote(third, received_at=third + timedelta(seconds=15, microseconds=1)),
    )
    outside = datetime(2026, 9, 10, 13, 29, 50, tzinfo=UTC)
    store.save_observation(
        session.id,
        _quote(outside, received_at=outside + timedelta(minutes=1)),
    )
    result = validate_signal_store(
        database,
        local_date=date(2026, 9, 10),
        now=datetime(2026, 9, 10, 13, 33, 30, tzinfo=UTC),
    )
    nvda = next(item for item in result.coverage if item.symbol == "NVDA")
    assert nvda.expected_completed_minutes == 3
    assert nvda.observed_completed_minutes == 3
    assert nvda.persisted_rows == 5
    assert nvda.outside_regular_rows == 1
    assert result.latency.sample_count == 4
    assert result.latency.future_over_2_seconds_count == 1
    assert result.latency.over_15_seconds_count == 1
    assert result.latency.median_milliseconds == Decimal("6500")
    assert sum(item.sample_count for item in result.symbol_latency) == 4
    assert sum(item.future_over_2_seconds_count for item in result.symbol_latency) == 1
    assert sum(item.over_15_seconds_count for item in result.symbol_latency) == 1
    nvda_latency = next(item for item in result.symbol_latency if item.symbol == "NVDA")
    assert nvda_latency.sample_count == 4
    empty_latency = next(
        item for item in result.symbol_latency if item.symbol == "SOXL"
    )
    assert empty_latency.sample_count == 0
    assert empty_latency.median_milliseconds is None
    assert empty_latency.p95_milliseconds is None
    assert empty_latency.maximum_milliseconds is None
    assert result.latency_anomalies.total_count == 2
    assert result.latency_anomalies.truncated is False
    assert [item.kind for item in result.latency_anomalies.items] == [
        "stale",
        "future",
    ]
    assert [item.milliseconds for item in result.latency_anomalies.items] == [
        Decimal("15000.001"),
        Decimal("-2000.001"),
    ]


def test_latency_anomaly_list_is_bounded_and_deterministically_sorted(
    tmp_path: Path,
) -> None:
    database = tmp_path / "forward.db"
    store = ForwardStore(database)
    session = store.activate(
        activated_at=datetime(2026, 9, 10, 13, 29, tzinfo=UTC),
        next_due_at=datetime(2026, 9, 14, tzinfo=UTC),
        source_run_id="fixed",
        config=ForwardConfig(),
    )
    first = datetime(2026, 9, 10, 13, 30, tzinfo=UTC)
    for offset in range(51):
        market_at = first + timedelta(minutes=offset)
        store.save_observation(
            session.id,
            _quote(
                market_at,
                received_at=market_at + timedelta(seconds=16, microseconds=offset),
            ),
        )
    result = validate_signal_store(
        database,
        local_date=date(2026, 9, 10),
        now=datetime(2026, 9, 10, 15, tzinfo=UTC),
    )
    anomalies = result.latency_anomalies
    assert anomalies.total_count == 51
    assert anomalies.limit == 50
    assert anomalies.truncated is True
    assert len(anomalies.items) == 50
    assert [item.market_at for item in anomalies.items] == sorted(
        (item.market_at for item in anomalies.items), reverse=True
    )
    assert anomalies.items[0].market_at == first + timedelta(minutes=50)
    assert anomalies.items[-1].market_at == first + timedelta(minutes=1)


def test_latest_completed_signal_date_uses_market_closes_and_skips_weekend() -> None:
    assert latest_completed_signal_date(datetime(2026, 9, 10, 21, tzinfo=UTC)) == date(
        2026, 9, 10
    )
    assert latest_completed_signal_date(datetime(2026, 9, 10, 18, tzinfo=UTC)) == date(
        2026, 9, 9
    )
    assert latest_completed_signal_date(datetime(2026, 9, 13, 12, tzinfo=UTC)) == date(
        2026, 9, 11
    )


def test_signal_date_bound_uses_supported_exchange_local_dates(tmp_path: Path) -> None:
    database = tmp_path / "forward.db"
    store = ForwardStore(database)
    store.activate(
        activated_at=datetime(2026, 9, 10, 13, 29, tzinfo=UTC),
        next_due_at=datetime(2026, 9, 14, tzinfo=UTC),
        source_run_id="fixed",
        config=ForwardConfig(),
    )
    result = validate_signal_store(
        database,
        local_date=date(2026, 9, 11),
        now=datetime(2026, 9, 10, 22, tzinfo=UTC),
    )
    assert result.local_date == date(2026, 9, 11)
    with pytest.raises(ValueError, match="latest seven local dates"):
        validate_signal_store(
            database,
            local_date=date(2026, 9, 12),
            now=datetime(2026, 9, 10, 22, tzinfo=UTC),
        )


def test_legacy_fill_is_reported_as_sample_only_without_backfill(
    tmp_path: Path,
) -> None:
    database = tmp_path / "forward.db"
    store, decision, intent, session_id = _fill_setup(database)
    quote = _quote(datetime(2026, 9, 10, 14, tzinfo=UTC))
    sample = store.save_observation(session_id, quote)
    fill = store.apply_fill(
        decision=decision,
        intent=intent,
        quote=quote,
        quote_id=sample.id,
        fx_rate=Decimal("1300"),
        quantity=1,
        local_fill_price=Decimal("100"),
        transaction_cost_krw=Decimal(0),
        fx_cost_krw=Decimal(0),
    )
    assert fill is not None
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE forward_execution_quotes SET quote_sha256 = ? WHERE fill_id = ?",
            ("0" * 64, fill.id),
        )
    mismatched = validate_signal_store(
        database,
        local_date=date(2026, 9, 10),
        now=datetime(2026, 9, 11, tzinfo=UTC),
    )
    assert mismatched.executions[0].evidence == "mismatch"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "DELETE FROM forward_execution_quotes WHERE fill_id = ?", (fill.id,)
        )
    result = validate_signal_store(
        database,
        local_date=date(2026, 9, 10),
        now=datetime(2026, 9, 11, tzinfo=UTC),
    )
    assert result.executions[0].evidence == "legacy_sample_only"
    with sqlite3.connect(database) as connection:
        assert (
            connection.execute(
                "SELECT count(*) FROM forward_execution_quotes"
            ).fetchone()[0]
            == 0
        )


def test_fold_boundaries_leave_only_unconsumed_tail() -> None:
    days = [date(2024, 1, 1) + timedelta(days=index) for index in range(774)]
    folds, tail = fold_boundaries(days)
    assert len(folds) == 7
    assert folds[0][1:] == (days[120], days[199], days[200], days[279])
    assert folds[-1][1:] == (days[600], days[679], days[680], days[759])
    assert tail == days[760:]
    assert len(tail) == 14


def test_aggregates_exclude_incomplete_comparable_oos_rows() -> None:
    candidate = PortfolioCandidate(id="equal", method="equal", gate="none")

    def evaluation(role: OosRole) -> OosEvaluation:
        return OosEvaluation(
            fold=1,
            role=role,
            candidate=candidate,
            config_changes={},
            complete=False,
            incomplete_reasons=["missing_fx"],
            metrics=RobustnessMetric(
                total_return_pct=Decimal("100"),
                max_drawdown_pct=Decimal(0),
                trade_count=0,
                turnover_pct=Decimal(0),
                transaction_cost_krw=Decimal(0),
                fx_cost_krw=Decimal(0),
            ),
        )

    fold = RobustnessFold(
        fold=1,
        selection_start=date(2025, 1, 1),
        selection_end=date(2025, 4, 1),
        oos_start=date(2025, 4, 2),
        oos_end=date(2025, 7, 1),
        status="completed",
        failure_reason=None,
        selected_candidate=candidate,
        selected_before_oos=True,
        validation=[],
        oos=[
            evaluation("selected_base"),
            evaluation("selected_cost_2x"),
            evaluation("equal_baseline"),
            evaluation("fixed_base"),
            evaluation("fixed_cost_2x"),
        ],
    )
    aggregates = _aggregates([fold])
    assert all(item.fold_count == 0 for item in aggregates)
    assert all(item.median_return_pct is None for item in aggregates)
    assert all(item.benchmark_beat_count == 0 for item in aggregates)


def _robustness_fixture(report_dir: Path) -> PortfolioRobustnessResult:
    specification_sha = hashlib.sha256(_canonical(SPECIFICATION).encode()).hexdigest()
    identity: dict[str, object] = {
        "source_run_id": "1" * 64,
        "source_manifest_sha256": "2" * 64,
        "source_result_sha256": "3" * 64,
        "code_sha256": "4" * 64,
        "specification": SPECIFICATION,
        "specification_sha256": specification_sha,
    }
    run_id = hashlib.sha256(_canonical(identity).encode()).hexdigest()
    result = PortfolioRobustnessResult(
        run_id=run_id,
        source_run_id="1" * 64,
        created_at=datetime(2026, 9, 11, tzinfo=UTC),
        source_manifest_sha256="2" * 64,
        source_result_sha256="3" * 64,
        code_sha256="4" * 64,
        specification_sha256=specification_sha,
        calculation_complete=True,
        fold_count=0,
        failed_fold_count=0,
        simulation_evaluation_count=0,
        union_date_count=0,
        unused_tail_start=None,
        unused_tail_end=None,
        unused_tail_count=0,
        folds=[],
        aggregates=[],
        limitations=[],
        artifacts=list(ARTIFACTS),
    )
    _write(
        report_dir,
        report_dir / "portfolio-robustness-runs" / run_id,
        result,
        identity,
    )
    return result


def test_robustness_repository_and_validation_api_are_bounded(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    expected = _robustness_fixture(reports)
    repository = PortfolioRobustnessRepository(reports)
    assert repository.latest() == expected
    with pytest.raises(ValueError):
        repository.artifact(expected.run_id, "../result.json")
    manifest_path = (
        reports / "portfolio-robustness-runs" / expected.run_id / "manifest.json"
    )
    original = manifest_path.read_text(encoding="utf-8")
    manifest = json.loads(original)
    manifest["code_sha256"] = "9" * 64
    manifest_path.write_text(_canonical(manifest) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="identity hash mismatch"):
        repository.latest()
    manifest_path.write_text(original, encoding="utf-8")

    forward_db = tmp_path / "forward.db"
    store = ForwardStore(forward_db)
    session = store.activate(
        activated_at=datetime(2026, 9, 10, 13, 29, tzinfo=UTC),
        next_due_at=datetime(2026, 9, 14, tzinfo=UTC),
        source_run_id="fixed",
        config=ForwardConfig(),
    )
    store.save_observation(
        session.id, _quote(datetime(2026, 9, 10, 13, 30, tzinfo=UTC))
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
        action_collection_enabled=False,
        forward_db_path=forward_db,
        validation_report_dir=reports,
    )
    with TestClient(app) as client:
        signal = client.get("/api/research/validation/signal?local_date=2026-09-10")
        assert signal.status_code == 200
        robustness = client.get("/api/research/validation/portfolio/latest")
        assert robustness.status_code == 200
        assert robustness.json()["run_id"] == expected.run_id
        blocked = client.get(
            f"/api/research/validation/portfolio/runs/{expected.run_id}/artifacts/unknown"
        )
        assert blocked.status_code == 404
