import asyncio
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from jusik.fixture_app import app as fixture_app
from jusik.market_history_models import (
    CorporateAction,
    MarketHistorySnapshot,
    MarketResearchRequest,
)
from jusik.market_history_sources import (
    FixtureMarketHistorySource,
    UnavailableMarketHistorySource,
)
from jusik.market_research_strategy import run_market_research
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
