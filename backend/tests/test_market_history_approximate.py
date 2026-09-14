from __future__ import annotations

import asyncio
import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from jusik.fixture_app import app as fixture_app
from jusik.market_history_approximate import (
    ApproximateProviderError,
    ApproximateUniverseRow,
    JsonApproximateProvider,
    deterministic_pool,
    run_approximate_market_research,
)
from jusik.market_history_models import MarketResearchRequest
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


def test_fixture_approximate_result_is_never_strict_ready() -> None:
    from jusik.market_history_approximate import FixtureApproximateMarketHistorySource

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
