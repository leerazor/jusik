import asyncio
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from jusik.fixture_app import app as fixture_app
from jusik.market_history_models import (
    CorporateAction,
    MarketHistorySnapshot,
    MarketReadiness,
    MarketResearchAccountMetadata,
    MarketResearchProvenance,
    MarketResearchRequest,
    MarketResearchResult,
    RawArtifact,
    anniversary_start,
)
from jusik.market_history_sources import (
    FixtureMarketHistorySource,
    UnavailableMarketHistorySource,
)
from jusik.market_history_store import MarketHistoryStore
from jusik.market_research_api import router as market_research_router
from jusik.market_research_service import (
    MarketResearchConflict,
    MarketResearchNotFound,
    MarketResearchService,
)
from jusik.market_research_strategy import (
    DRAWDOWN_LIMIT,
    MARKET_RESEARCH_POLICY,
    market_research_policy_hash,
    run_market_research,
)
from jusik.research_market_calendar import default_market_calendar


def request(market: str = "KR") -> MarketResearchRequest:
    return MarketResearchRequest(
        market=market,  # type: ignore[arg-type]
        start_date=date(2023, 3, 15),
        end_date=date(2024, 3, 15),
        stage="pilot",
    )


def test_fixture_engine_is_causal_stock_only_and_uses_next_open() -> None:
    source = FixtureMarketHistorySource()
    item = request()
    snapshot = asyncio.run(source.collect(item))
    result = run_market_research(
        snapshot,
        item,
        source.readiness("KR", datetime(2024, 3, 15, tzinfo=UTC)),
        default_market_calendar(),
    )

    assert result.status == "ready"
    assert result.completeness == "complete"
    assert all(
        not evidence.symbol.startswith("ETF") for evidence in result.candidate_evidence
    )
    assert all(trade.fill_session > trade.signal_session for trade in result.trades)
    assert all(trade.side in {"buy", "sell"} for trade in result.trades)
    assert result.metrics["initial_cash_krw"] == item.initial_cash_krw


def test_fixture_full_daily_bars_are_available_at_close() -> None:
    source = FixtureMarketHistorySource()
    snapshot = asyncio.run(source.collect(request()))
    calendar = default_market_calendar()
    for bar in snapshot.bars:
        session = calendar.lookup("KSC", bar.session).session
        assert session is not None
        assert bar.available_at == session.close_at


def test_entry_equal_to_prior_high_is_not_a_breakout() -> None:
    source = FixtureMarketHistorySource()
    item = request()
    snapshot = asyncio.run(source.collect(item))
    sessions = sorted({bar.session for bar in snapshot.bars})
    signal_session = sessions[20]
    prior_closes = [
        bar.close
        for bar in snapshot.bars
        if bar.symbol == "KR-A" and bar.session in sessions[:20]
    ]
    equal_high = max(prior_closes)
    bars = tuple(
        bar.model_copy(update={"close": equal_high})
        if bar.symbol == "KR-A" and bar.session == signal_session
        else bar
        for bar in snapshot.bars
    )
    data = snapshot.model_dump()
    data["bars"] = bars
    result = run_market_research(
        MarketHistorySnapshot(**data),
        item,
        source.readiness("KR", datetime(2024, 3, 15, tzinfo=UTC)),
        default_market_calendar(),
    )
    assert not any(
        trade.symbol == "KR-A" and trade.signal_session == signal_session
        for trade in result.trades
    )


def test_final_day_drawdown_liquidation_is_not_reported_as_performance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = FixtureMarketHistorySource()
    item = request()
    snapshot = asyncio.run(source.collect(item))
    final_session = max(bar.session for bar in snapshot.bars)
    bars = tuple(
        bar.model_copy(update={"close": Decimal("1"), "low": Decimal("1")})
        if bar.symbol in {"KR-B", "KR-C"} and bar.session == final_session
        else bar
        for bar in snapshot.bars
    )
    data = snapshot.model_dump()
    data["bars"] = bars
    monkeypatch.setattr(
        "jusik.market_research_strategy.DRAWDOWN_LIMIT", DRAWDOWN_LIMIT / 10
    )
    result = run_market_research(
        MarketHistorySnapshot(**data),
        item,
        source.readiness("KR", datetime(2024, 3, 15, tzinfo=UTC)),
        default_market_calendar(),
    )
    assert result.status == "insufficient"
    assert result.metrics == {}
    assert any("청산이 체결되지 않아" in item for item in result.limitations)
    assert any("미청산 잔여 보유" in item for item in result.limitations)


def test_fixture_us_keeps_native_cash_and_point_in_time_fx_curve() -> None:
    source = FixtureMarketHistorySource()
    item = request("US")
    snapshot = asyncio.run(source.collect(item))
    result = run_market_research(
        snapshot,
        item,
        source.readiness("US", datetime(2024, 3, 15, tzinfo=UTC)),
        default_market_calendar(),
    )

    assert result.status == "ready"
    assert result.equity
    assert all(point.fx_krw_per_usd > 0 for point in result.equity)
    first_research_session = next(
        observation
        for observation in snapshot.fx
        if observation.session >= item.start_date
    )
    assert (
        result.metrics["initial_fx_krw_per_usd"] == first_research_session.krw_per_usd
    )
    assert all(trade.currency == "USD" for trade in result.trades)


def test_missing_production_capabilities_fail_closed_without_returns() -> None:
    source = UnavailableMarketHistorySource()
    item = request()
    snapshot = asyncio.run(source.collect(item))
    result = run_market_research(
        snapshot,
        item,
        source.readiness("KR", datetime(2024, 3, 15, tzinfo=UTC)),
        default_market_calendar(),
    )

    assert result.status == "insufficient"
    assert result.completeness == "incomplete"
    assert result.metrics == {}
    assert result.trades == ()


def test_fixture_api_exposes_readiness_and_completed_simulated_run() -> None:
    fixture_snapshot = asyncio.run(FixtureMarketHistorySource().collect(request()))
    fixture_artifact = fixture_snapshot.source_artifacts[0]
    with TestClient(fixture_app) as client:
        status_response = client.get("/api/research/market/status?market=KR")
        assert status_response.status_code == 200
        assert status_response.json()[0]["simulated"] is True
        created = client.post(
            "/api/research/market/runs",
            json={
                "market": "KR",
                "start_date": "2023-03-15",
                "end_date": "2024-03-15",
                "stage": "pilot",
            },
        )
        assert created.status_code == 202
        body = created.json()
        assert body["status"] == "completed"
        assert body["final_promotable"] is True
        assert body["final_promotability_reason"] == ""
        assert body["result"]["limitations"]
        provenance = body["result"]["provenance"]
        assert provenance["universe_sources"] == ["fixture"]
        assert provenance["bar_sources"] == ["fixture"]
        assert provenance["fx_sources"] is None
        assert provenance["artifact_sources"] == ["fixture"]
        assert provenance["normalization_version"] == "pit-v1"
        assert provenance["captured_at"]
        account = body["result"]["account"]
        assert account["account_scope"] == "market_specific_independent_simulated"
        assert account["reporting_currency"] == "KRW"
        assert account["native_currency"] == "KRW"
        assert account["initial_cash_krw"] == "100000000"
        assert account["fx_krw_per_usd"] == "1"
        assert account["initial_cash_conversion"] == "identity"
        fetched = client.get(f"/api/research/market/runs/{body['id']}")
        assert fetched.status_code == 200
        assert fetched.json()["input_hash"]
        artifact_response = client.get(
            f"/api/research/market/artifacts/{fixture_artifact.artifact_id}"
        )
        assert artifact_response.status_code == 200
        assert artifact_response.content == fixture_artifact.raw_content


def test_empty_source_provenance_is_explicitly_unknown(tmp_path: Path) -> None:
    source = UnavailableMarketHistorySource()
    run = asyncio.run(
        MarketResearchService(
            source, MarketHistoryStore(tmp_path / "empty.db")
        ).create_run(request())
    )
    assert run.result is not None
    assert run.result.status == "insufficient"
    assert run.result.provenance == MarketResearchProvenance()
    assert run.result.account is not None
    assert run.result.account.native_currency == "KRW"
    assert run.result.account.fx_krw_per_usd == Decimal("1")


def test_us_account_metadata_uses_native_currency_and_initial_fx(
    tmp_path: Path,
) -> None:
    source = FixtureMarketHistorySource()
    run = asyncio.run(
        MarketResearchService(
            source, MarketHistoryStore(tmp_path / "us.db")
        ).create_run(request("US"))
    )
    assert run.result is not None
    assert run.result.account is not None
    assert run.result.account.native_currency == "USD"
    assert run.result.account.reporting_currency == "KRW"
    assert run.result.account.initial_cash_krw == Decimal("100000000")
    assert (
        run.result.account.fx_krw_per_usd
        == run.result.metrics["initial_fx_krw_per_usd"]
    )
    assert run.result.account.initial_cash_conversion == "initial_krw_to_usd"


def test_account_metadata_rejects_market_or_request_contradictions() -> None:
    source = FixtureMarketHistorySource()
    item = request("KR")
    result = run_market_research(
        asyncio.run(source.collect(item)),
        item,
        source.readiness("KR", datetime(2024, 3, 15, tzinfo=UTC)),
        default_market_calendar(),
    )
    payload = result.model_dump()
    payload["account"] = MarketResearchAccountMetadata(
        native_currency="USD",
        initial_cash_krw=item.initial_cash_krw,
        fx_krw_per_usd=Decimal("1300"),
        initial_cash_conversion="initial_krw_to_usd",
    ).model_dump()
    with pytest.raises(ValidationError):
        MarketResearchResult.model_validate(payload)


@pytest.mark.parametrize("kind", ["split", "halt", "delisting"])
def test_unsupported_corporate_actions_fail_closed(kind: str) -> None:
    source = FixtureMarketHistorySource()
    item = request()
    snapshot = asyncio.run(source.collect(item))
    action = CorporateAction(
        market="KR",
        symbol="KR-A",
        session=snapshot.bars[0].session,
        kind=kind,  # type: ignore[arg-type]
        ratio="2" if kind == "split" else None,
        available_at=snapshot.bars[0].available_at,
        captured_at=snapshot.captured_at,
        source="fixture",
        source_hash="a" * 64,
    )
    snapshot_data = snapshot.model_dump()
    snapshot_data["actions"] = (action,)
    with_action = MarketHistorySnapshot(**snapshot_data)
    result = run_market_research(
        with_action,
        item,
        source.readiness("KR", datetime(2024, 3, 15, tzinfo=UTC)),
        default_market_calendar(),
    )
    assert result.status == "insufficient"
    assert result.trades == ()
    assert any(kind in limitation for limitation in result.limitations)


def test_preclose_bar_and_future_fx_are_not_usable() -> None:
    source = FixtureMarketHistorySource()
    kr_item = request()
    kr_snapshot = asyncio.run(source.collect(kr_item))
    kr_data = kr_snapshot.model_dump()
    kr_data["bars"] = tuple(
        bar.model_copy(update={"available_at": bar.session_start_utc()})
        for bar in kr_snapshot.bars
    )
    kr_result = run_market_research(
        MarketHistorySnapshot(**kr_data),
        kr_item,
        source.readiness("KR", datetime(2024, 3, 15, tzinfo=UTC)),
        default_market_calendar(),
    )
    assert kr_result.status == "insufficient"

    us_item = request("US")
    us_snapshot = asyncio.run(source.collect(us_item))
    us_data = us_snapshot.model_dump()
    us_data["fx"] = tuple(
        observation.model_copy(update={"available_at": us_snapshot.captured_at})
        for observation in us_snapshot.fx
    )
    us_result = run_market_research(
        MarketHistorySnapshot(**us_data),
        us_item,
        source.readiness("US", datetime(2024, 3, 15, tzinfo=UTC)),
        default_market_calendar(),
    )
    assert us_result.status == "insufficient"


def test_missing_next_open_membership_is_insufficient() -> None:
    source = FixtureMarketHistorySource()
    item = request()
    snapshot = asyncio.run(source.collect(item))
    sessions = sorted({bar.session for bar in snapshot.bars})
    data = snapshot.model_dump()
    data["memberships"] = tuple(
        membership.model_copy(update={"valid_to": item.start_date})
        if membership.symbol == "KR-A"
        else membership
        for membership in snapshot.memberships
    )
    result = run_market_research(
        MarketHistorySnapshot(**data),
        item,
        source.readiness("KR", datetime(2024, 3, 15, tzinfo=UTC)),
        default_market_calendar(),
    )
    assert sessions
    assert result.status == "insufficient"
    assert result.trades == ()


def test_snapshot_rejects_cross_market_child() -> None:
    source = FixtureMarketHistorySource()
    snapshot = asyncio.run(source.collect(request()))
    bar = snapshot.bars[0].model_copy(update={"market": "US", "currency": "USD"})
    data = snapshot.model_dump()
    data["bars"] = (bar, *snapshot.bars[1:])
    with pytest.raises(ValidationError):
        MarketHistorySnapshot(**data)


def test_readiness_ready_must_match_capabilities() -> None:
    source = FixtureMarketHistorySource()
    readiness = source.readiness("KR", datetime(2024, 3, 15, tzinfo=UTC))
    data = readiness.model_dump()
    data["ready"] = False
    with pytest.raises(ValidationError):
        MarketReadiness(**data)

    for capabilities in (
        (),
        (*readiness.capabilities[:-1], readiness.capabilities[0]),
    ):
        data["capabilities"] = capabilities
        data["ready"] = True
        with pytest.raises(ValidationError):
            MarketReadiness(**data)


def test_raw_artifact_hash_and_policy_manifest_are_verified() -> None:
    artifact = RawArtifact.from_bytes(
        b"fixture artifact",
        content_type="application/octet-stream",
        captured_at=datetime(2024, 3, 15, tzinfo=UTC),
        source="fixture",
    )
    data = artifact.model_dump()
    data["artifact_id"] = "a" * 64
    data["raw_content"] = artifact.raw_content
    with pytest.raises(ValidationError):
        RawArtifact(**data)
    mismatched = artifact.model_dump()
    mismatched["raw_content"] = b"different bytes"
    with pytest.raises(ValidationError):
        RawArtifact(**mismatched)
    changed_policy = {**MARKET_RESEARCH_POLICY, "top_count": 19}
    assert market_research_policy_hash() != market_research_policy_hash(changed_policy)


def test_service_rejects_mismatched_saved_artifact_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = FixtureMarketHistorySource()
    store = MarketHistoryStore(tmp_path / "pit.db")

    def wrong_digest(*args: object, **kwargs: object) -> str:
        return "f" * 64

    monkeypatch.setattr(store, "save_artifact", wrong_digest)
    service = MarketResearchService(source, store)
    with pytest.raises(RuntimeError):
        asyncio.run(service.create_run(request()))


def test_store_artifact_and_terminal_run_are_immutable(tmp_path: Path) -> None:
    source = FixtureMarketHistorySource()
    item = request()
    snapshot = asyncio.run(source.collect(item))
    store = MarketHistoryStore(tmp_path / "pit.db")
    run = store.create_run(item)
    artifact = snapshot.source_artifacts[0]
    assert artifact.decoded_content == artifact.raw_content
    assert (
        store.save_artifact(
            artifact.decoded_content,
            content_type=artifact.content_type,
            captured_at=artifact.captured_at,
        )
        == artifact.artifact_id
    )
    assert store.get_artifact(artifact.artifact_id)[0] == artifact.decoded_content
    store.save_snapshot(snapshot)
    loaded = store.get_snapshot(snapshot.input_hash)
    assert loaded.source_artifacts[0].decoded_content == artifact.decoded_content
    result = run_market_research(
        snapshot,
        item,
        source.readiness("KR", datetime(2024, 3, 15, tzinfo=UTC)),
        default_market_calendar(),
    )
    store.update_run(
        run.id, status="completed", result=result, input_hash=snapshot.input_hash
    )
    with pytest.raises(ValueError):
        store.update_run(run.id, status="failed", error="overwrite")


def test_snapshot_rejects_duplicate_bars_and_actions() -> None:
    source = FixtureMarketHistorySource()
    item = request()
    snapshot = asyncio.run(source.collect(item))
    duplicate_bar = snapshot.bars[0]
    with pytest.raises(ValidationError):
        snapshot_data = snapshot.model_dump()
        snapshot_data["bars"] = (*snapshot.bars, duplicate_bar)
        MarketHistorySnapshot(**snapshot_data)
    action = CorporateAction(
        market="KR",
        symbol="KR-A",
        session=snapshot.bars[0].session,
        kind="split",
        ratio="2",
        available_at=snapshot.captured_at,
        captured_at=snapshot.captured_at,
        source="fixture",
        source_hash="a" * 64,
    )
    with pytest.raises(ValidationError):
        snapshot_data = snapshot.model_dump()
        snapshot_data["actions"] = (action, action)
        MarketHistorySnapshot(**snapshot_data)


def test_staged_periods_use_calendar_anniversary_and_warmup() -> None:
    assert anniversary_start(date(2024, 2, 29), years=1) == date(2023, 2, 28)
    pilot = MarketResearchRequest(
        market="KR",
        start_date=date(2025, 3, 14),
        end_date=date(2026, 3, 14),
        stage="pilot",
    )
    snapshot = asyncio.run(FixtureMarketHistorySource().collect(pilot))
    result = run_market_research(
        snapshot,
        pilot,
        FixtureMarketHistorySource().readiness("KR", datetime(2026, 3, 14, tzinfo=UTC)),
        default_market_calendar(),
    )
    assert result.status == "ready"
    assert len(result.warmup_sessions) == 20
    assert result.equity
    assert all(point.session >= pilot.start_date for point in result.equity)
    assert all(trade.session >= pilot.start_date for trade in result.trades)


def test_staged_request_rejects_wrong_period_and_reference() -> None:
    with pytest.raises(ValidationError):
        MarketResearchRequest(
            market="KR",
            start_date=date(2025, 1, 1),
            end_date=date(2026, 1, 1),
            stage="pilot",
            pilot_run_id="a" * 8,
        )


def test_new_listing_with_short_history_is_entry_ineligible_not_a_failure() -> None:
    source = FixtureMarketHistorySource()
    item = request()
    snapshot = asyncio.run(source.collect(item))
    listed = snapshot.warmup_sessions[10]
    data = snapshot.model_dump()
    data["memberships"] = tuple(
        membership.model_copy(update={"valid_from": listed})
        if membership.symbol == "KR-A"
        else membership
        for membership in snapshot.memberships
    )
    data["bars"] = tuple(
        bar for bar in snapshot.bars if bar.symbol != "KR-A" or bar.session >= listed
    )
    result = run_market_research(
        MarketHistorySnapshot(**data),
        item,
        source.readiness("KR", datetime(2024, 3, 15, tzinfo=UTC)),
        default_market_calendar(),
    )
    assert result.status == "ready"
    assert not any(
        trade.symbol == "KR-A" and trade.signal_session < listed
        for trade in result.trades
    )


def test_staged_api_rejects_client_execution_override_and_legacy_create() -> None:
    with TestClient(fixture_app) as client:
        override = client.post(
            "/api/research/market/runs",
            json={
                "market": "KR",
                "end_date": "2026-09-14",
                "stage": "pilot",
                "initial_cash_krw": "1",
            },
        )
        assert override.status_code == 422
        legacy = client.post(
            "/api/research/market/runs",
            json={
                "market": "KR",
                "start_date": "2023-03-15",
                "end_date": "2024-03-15",
                "stage": "legacy",
            },
        )
        assert legacy.status_code == 422


def test_service_rejects_direct_staged_execution_override(tmp_path: Path) -> None:
    source = FixtureMarketHistorySource()
    store = MarketHistoryStore(tmp_path / "staged-direct-override.db")
    service = MarketResearchService(source, store)
    with pytest.raises(MarketResearchConflict):
        asyncio.run(
            service.create_run(request().model_copy(update={"fee_rate": Decimal("0")}))
        )
    with pytest.raises(MarketResearchConflict):
        asyncio.run(
            service.create_run(request().model_copy(update={"stage": "legacy"}))
        )
    with pytest.raises(ValidationError):
        MarketResearchRequest(
            market="KR",
            start_date=date(2023, 1, 1),
            end_date=date(2026, 1, 1),
            stage="final",
        )


def test_store_reads_historical_staged_custom_assumptions_but_final_rejects(
    tmp_path: Path,
) -> None:
    import json
    import sqlite3

    path = tmp_path / "historical-staged.db"
    store = MarketHistoryStore(path)
    source = FixtureMarketHistorySource()
    readiness = source.readiness("KR", datetime(2026, 9, 14, tzinfo=UTC))
    request_payload = {
        "market": "KR",
        "start_date": "2025-09-14",
        "end_date": "2026-09-14",
        "stage": "pilot",
        "pilot_run_id": None,
        "initial_cash_krw": "100000000",
        "fee_rate": "0.002",
        "slippage_rate": "0.001",
        "sell_tax_rate": "0.0018",
    }
    result_payload = {
        "market": "KR",
        "request": request_payload,
        "readiness": readiness.model_dump(mode="json"),
        "status": "ready",
        "completeness": "complete",
        "candidate_evidence": [
            {
                "session": "2026-09-11",
                "symbol": "KR-A",
                "rank": 1,
                "volume": "10",
                "eligible": True,
                "membership_available_at": None,
                "bar_available_at": None,
            }
        ],
        "trades": [
            {
                "session": "2026-09-11",
                "signal_session": "2026-09-10",
                "fill_session": "2026-09-11",
                "symbol": "KR-A",
                "side": "buy",
                "quantity": 1,
                "currency": "KRW",
                "market_open": "10",
                "fill_price": "10",
                "notional": "10",
                "fee": "0",
                "tax": "0",
                "rationale": "historical compatibility",
            }
        ],
        "equity": [
            {
                "session": "2026-09-11",
                "cash_krw": "100",
                "cash_native": "100",
                "invested_krw": "0",
                "nav_krw": "100",
                "fx_krw_per_usd": "1",
                "drawdown_pct": "0",
            }
        ],
        "limitations": ["historical compatibility"],
        "metrics": {"sample": "1.25"},
        "input_hash": "a" * 64,
        "policy_hash": market_research_policy_hash(),
        "stage": "pilot",
        "pilot_run_id": None,
        "data_contract_hash": "b" * 64,
        "warmup_sessions": ["2026-09-10"],
    }
    with sqlite3.connect(path) as connection:
        connection.execute(
            "INSERT INTO pit_runs (id,status,request_json,result_json,input_hash,error,"
            "created_at,updated_at,stage,pilot_run_id,data_contract_hash) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                "historical-pilot",
                "completed",
                json.dumps(request_payload),
                json.dumps(result_payload),
                "a" * 64,
                None,
                "2026-09-14T00:00:00+00:00",
                "2026-09-14T00:00:00+00:00",
                "pilot",
                None,
                "b" * 64,
            ),
        )
    loaded = store.get_run("historical-pilot")
    assert loaded.request.fee_rate == Decimal("0.002")
    assert loaded.result is not None
    assert isinstance(loaded.result.candidate_evidence, tuple)
    assert isinstance(loaded.result.trades, tuple)
    assert isinstance(loaded.result.equity, tuple)
    assert isinstance(loaded.result.limitations, tuple)
    assert isinstance(loaded.result.metrics["sample"], Decimal)
    assert isinstance(loaded.result.warmup_sessions, tuple)
    assert loaded.result.provenance is None
    assert loaded.result.account is None
    assert loaded.result.warmup_sessions == (date(2026, 9, 10),)
    assert store.list_runs()[0].id == "historical-pilot"
    annotated = MarketResearchService(source, store).annotate_run(loaded)
    assert annotated.final_promotable is False
    assert annotated.final_promotability_reason
    api_app = FastAPI()
    api_app.include_router(market_research_router)
    api_app.state.market_research_service = MarketResearchService(source, store)
    with TestClient(api_app) as client:
        response = client.get("/api/research/market/runs/historical-pilot")
    assert response.status_code == 200
    assert response.json()["final_promotable"] is False
    assert response.json()["result"]["warmup_sessions"] == ["2026-09-10"]
    final = MarketResearchRequest(
        market="KR",
        start_date=date(2023, 9, 14),
        end_date=date(2026, 9, 14),
        stage="final",
        pilot_run_id=loaded.id,
    )
    with pytest.raises(MarketResearchConflict):
        asyncio.run(MarketResearchService(source, store).create_run(final))


def test_final_requires_completed_matching_pilot_and_collects_own_period(
    tmp_path: Path,
) -> None:
    store = MarketHistoryStore(tmp_path / "staged.db")
    service = MarketResearchService(FixtureMarketHistorySource(), store)
    pilot_request = MarketResearchRequest(
        market="KR",
        start_date=date(2025, 9, 14),
        end_date=date(2026, 9, 14),
        stage="pilot",
    )
    pilot = asyncio.run(service.create_run(pilot_request))
    assert pilot.status == "completed"
    final_request = MarketResearchRequest(
        market="KR",
        start_date=date(2023, 9, 14),
        end_date=date(2026, 9, 14),
        stage="final",
        pilot_run_id=pilot.id,
    )
    final = asyncio.run(service.create_run(final_request))
    assert final.status == "completed"
    assert final.stage == "final"
    assert service.annotate_run(pilot).final_promotable is True
    assert final.input_hash != pilot.input_hash
    with pytest.raises(MarketResearchNotFound):
        asyncio.run(
            service.create_run(
                final_request.model_copy(update={"pilot_run_id": "missing"})
            )
        )


def test_old_pit_runs_migrate_to_legacy_without_rewriting_request(
    tmp_path: Path,
) -> None:
    import sqlite3

    path = tmp_path / "old.db"
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE pit_runs (id TEXT PRIMARY KEY, status TEXT NOT NULL, "
            "request_json TEXT NOT NULL, result_json TEXT, input_hash TEXT, "
            "error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
        )
        old_request = request().model_dump_json()
        connection.execute(
            "INSERT INTO pit_runs VALUES (?, 'queued', ?, NULL, NULL, NULL, ?, ?)",
            (
                "legacy123",
                old_request,
                "2024-01-01T00:00:00+00:00",
                "2024-01-01T00:00:00+00:00",
            ),
        )
    store = MarketHistoryStore(path)
    loaded = store.get_run("legacy123")
    assert loaded.stage == "legacy"
    assert loaded.request.model_dump_json() == old_request
