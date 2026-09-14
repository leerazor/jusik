from __future__ import annotations

import asyncio
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from jusik.fixture_app import app as fixture_app
from jusik.market_history_approximate import (
    ApproximateMarketHistorySource,
    ApproximateProviderError,
    ApproximateUniverseRow,
    FixtureApproximateMarketHistorySource,
    JsonApproximateProvider,
    KRXDateListProvider,
    deterministic_pool,
    run_approximate_market_research,
)
from jusik.market_history_models import MarketResearchRequest
from jusik.market_research_strategy import (
    RESEARCH_MANDATE_JSON_SHA256,
    market_research_policy_for_grade,
    market_research_policy_hash,
)
from jusik.research_market_calendar import default_market_calendar


def test_deterministic_pool_is_bounded_and_seeded() -> None:
    rows = tuple(
        ApproximateUniverseRow(
            session=date(2026, 9, 14),
            symbol=f"S{index:03d}",
            name=f"Sample {index}",
            exchange="KSC",
            currency="KRW",
        )
        for index in range(450)
    )
    first = deterministic_pool(rows, market="KR", pool_end=date(2026, 9, 14))
    second = deterministic_pool(rows, market="KR", pool_end=date(2026, 9, 14))
    assert first.contract_hash == second.contract_hash
    assert first.rows == second.rows
    assert first.unique_symbols == 450
    assert first.sampled_symbols == 100
    assert len({row.symbol for row in first.rows}) == 100


def test_json_provider_rejects_current_period_overflow_and_market_mismatch(
    tmp_path: Path,
) -> None:
    payload = {
        "market": "KR",
        "universe": [
            {
                "session": "2026-09-14",
                "symbol": "S1",
                "name": "Sample",
                "exchange": "KSC",
                "currency": "KRW",
            }
        ],
        "bars": [],
    }
    path = tmp_path / "approx.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    provider = JsonApproximateProvider(path)
    with pytest.raises(ApproximateProviderError):
        asyncio.run(provider.fetch("US", date(2026, 1, 1), date(2026, 9, 14)))
    payload["universe"][0]["session"] = "2026-09-15"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ApproximateProviderError):
        asyncio.run(provider.fetch("KR", date(2026, 1, 1), date(2026, 9, 14)))

    payload["universe"][0]["session"] = "2026-09-14"
    payload["fx"] = [
        {"session": "2026-09-15", "krw_per_usd": "1350", "spread_rate": "0.001"}
    ]
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ApproximateProviderError):
        asyncio.run(provider.fetch("KR", date(2026, 1, 1), date(2026, 9, 14)))


def test_prepared_provider_rejects_untrusted_provenance_and_readiness_is_truthful(
    tmp_path: Path,
) -> None:
    payload = {
        "market": "KR",
        "universe": [
            {
                "session": "2026-09-14",
                "symbol": "S1",
                "name": "Sample",
                "exchange": "KSC",
                "currency": "KRW",
            }
        ],
        "bars": [],
        "simulated": True,
    }
    path = tmp_path / "approx.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    provider = JsonApproximateProvider(path)
    with pytest.raises(ApproximateProviderError):
        asyncio.run(provider.fetch("KR", date(2026, 1, 1), date(2026, 9, 14)))
    readiness = ApproximateMarketHistorySource(provider).readiness(
        "KR", datetime(2026, 9, 14, tzinfo=UTC)
    )
    assert readiness.ready is False
    missing = {item.name for item in readiness.capabilities if item.status == "missing"}
    assert missing >= {"membership", "bars"}


def test_declared_universe_source_is_preserved_in_snapshot(tmp_path: Path) -> None:
    payload = {
        "market": "KR",
        "source": "krx",
        "universe": [
            {
                "session": "2026-09-14",
                "symbol": "S1",
                "name": "Sample",
                "exchange": "KSC",
                "currency": "KRW",
            }
        ],
        "bars": [
            {
                "session": "2026-09-14",
                "symbol": "S1",
                "exchange": "KSC",
                "open": "100",
                "high": "101",
                "low": "99",
                "close": "100",
                "volume": "1000",
                "currency": "KRW",
            }
        ],
    }
    path = tmp_path / "krx.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    request = MarketResearchRequest(
        market="KR",
        start_date=date(2025, 9, 14),
        end_date=date(2026, 9, 14),
        stage="pilot",
        research_grade="approximate",
    )
    snapshot = asyncio.run(
        ApproximateMarketHistorySource(KRXDateListProvider(path)).collect(request)
    )
    assert snapshot.memberships[0].source == "krx"
    assert snapshot.source_artifacts[0].source == "krx"


def test_fixture_approximate_result_is_never_strict_ready() -> None:
    request = MarketResearchRequest(
        market="KR",
        start_date=date(2025, 9, 14),
        end_date=date(2026, 9, 14),
        stage="pilot",
        research_grade="approximate",
    )
    source = FixtureApproximateMarketHistorySource()
    readiness = source.readiness("KR", datetime(2026, 9, 14, tzinfo=UTC))
    snapshot = asyncio.run(source.collect(request))
    result = run_approximate_market_research(
        snapshot, request, readiness, default_market_calendar()
    )
    assert snapshot.research_grade == "approximate"
    assert readiness.research_grade == "approximate"
    assert readiness.ready is False
    assert result.research_grade == "approximate"
    assert result.status == "approximate"
    assert result.completeness == "approximate"


def test_approximate_uses_shared_execution_costs_and_next_open_core() -> None:
    request = MarketResearchRequest(
        market="KR",
        start_date=date(2025, 9, 14),
        end_date=date(2026, 9, 14),
        stage="pilot",
        research_grade="approximate",
    )
    source = FixtureApproximateMarketHistorySource()
    readiness = source.readiness("KR", datetime(2026, 9, 14, tzinfo=UTC))
    result = run_approximate_market_research(
        asyncio.run(source.collect(request)),
        request,
        readiness,
        default_market_calendar(),
    )
    assert result.trades
    assert all(trade.fill_session > trade.signal_session for trade in result.trades)
    buys = [trade for trade in result.trades if trade.side == "buy"]
    assert buys
    assert all(trade.fee > 0 for trade in buys)
    assert all(trade.fill_price > trade.market_open for trade in buys)


def test_approximate_policy_tracks_the_maintained_mandate_checksum() -> None:
    checksum_file = Path("docs/market-research-mandate.sha256").read_text()
    assert f"docs/research-mandate.json {RESEARCH_MANDATE_JSON_SHA256}" in checksum_file
    assert market_research_policy_hash() != market_research_policy_hash(
        market_research_policy_for_grade("approximate")
    )


def test_approximate_future_availability_and_fx_are_insufficient() -> None:
    request = MarketResearchRequest(
        market="KR",
        start_date=date(2025, 9, 14),
        end_date=date(2026, 9, 14),
        stage="pilot",
        research_grade="approximate",
    )
    source = FixtureApproximateMarketHistorySource()
    readiness = source.readiness("KR", datetime(2026, 9, 14, tzinfo=UTC))
    snapshot = asyncio.run(source.collect(request))
    future = snapshot.model_copy(
        update={
            "bars": tuple(
                bar.model_copy(
                    update={"available_at": bar.available_at + timedelta(days=1)}
                )
                for bar in snapshot.bars
            )
        }
    )
    result = run_approximate_market_research(
        future, request, readiness, default_market_calendar()
    )
    assert result.status == "insufficient"
    assert result.trades == ()

    preclose = snapshot.model_copy(
        update={
            "bars": tuple(
                bar.model_copy(update={"available_at": bar.session_start_utc()})
                for bar in snapshot.bars
            )
        }
    )
    preclose_result = run_approximate_market_research(
        preclose, request, readiness, default_market_calendar()
    )
    assert preclose_result.status == "insufficient"
    assert preclose_result.trades == ()

    us_request = request.model_copy(update={"market": "US"})
    us_snapshot = asyncio.run(source.collect(us_request))
    us_readiness = source.readiness("US", datetime(2026, 9, 14, tzinfo=UTC))
    future_fx = us_snapshot.model_copy(
        update={
            "fx": tuple(
                observation.model_copy(
                    update={
                        "available_at": observation.available_at + timedelta(days=1)
                    }
                )
                for observation in us_snapshot.fx
            )
        }
    )
    us_result = run_approximate_market_research(
        future_fx, us_request, us_readiness, default_market_calendar()
    )
    assert us_result.status == "insufficient"
    assert us_result.trades == ()


def test_fixture_api_exposes_approximate_grade_without_pit_claim() -> None:
    with TestClient(fixture_app) as client:
        response = client.post(
            "/api/research/market/runs",
            json={
                "market": "KR",
                "end_date": "2026-09-14",
                "stage": "pilot",
                "research_grade": "approximate",
            },
        )
    assert response.status_code == 202
    body = response.json()
    assert body["result"]["research_grade"] == "approximate"
    assert body["result"]["status"] == "approximate"
    assert body["result"]["completeness"] == "approximate"
