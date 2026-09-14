import asyncio
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from jusik.fixture_app import app as fixture_app
from jusik.market_history_models import (
    CorporateAction,
    MarketHistorySnapshot,
    MarketReadiness,
    MarketResearchRequest,
    RawArtifact,
)
from jusik.market_history_sources import (
    FixtureMarketHistorySource,
    UnavailableMarketHistorySource,
)
from jusik.market_history_store import MarketHistoryStore
from jusik.market_research_service import MarketResearchService
from jusik.market_research_strategy import (
    MARKET_RESEARCH_POLICY,
    market_research_policy_hash,
    run_market_research,
)
from jusik.research_market_calendar import default_market_calendar


def request(market: str = "KR") -> MarketResearchRequest:
    return MarketResearchRequest(
        market=market,  # type: ignore[arg-type]
        start_date=date(2024, 1, 15),
        end_date=date(2024, 3, 15),
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
                "start_date": "2024-01-15",
                "end_date": "2024-03-15",
            },
        )
        assert created.status_code == 202
        body = created.json()
        assert body["status"] == "completed"
        assert body["result"]["limitations"]
        fetched = client.get(f"/api/research/market/runs/{body['id']}")
        assert fetched.status_code == 200
        assert fetched.json()["input_hash"]
        artifact_response = client.get(
            f"/api/research/market/artifacts/{fixture_artifact.artifact_id}"
        )
        assert artifact_response.status_code == 200
        assert artifact_response.content == fixture_artifact.raw_content


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
