from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from jusik.market_history_models import MarketResearchRequest
from jusik.market_history_sources import FixtureMarketHistorySource
from jusik.market_research_strategy import run_market_research
from jusik.market_time_evidence import attach_time_evidence
from jusik.research_market_calendar import default_market_calendar


def test_attach_time_evidence_uses_official_open_and_close() -> None:
    request = MarketResearchRequest(
        market="KR",
        start_date=datetime(2023, 3, 15, tzinfo=UTC).date(),
        end_date=datetime(2024, 3, 15, tzinfo=UTC).date(),
        stage="pilot",
    )
    source = FixtureMarketHistorySource()
    snapshot = asyncio.run(source.collect(request))
    result = run_market_research(
        snapshot,
        request,
        source.readiness("KR", datetime(2024, 3, 15, tzinfo=UTC)),
        default_market_calendar(),
    )
    enriched = attach_time_evidence(result, default_market_calendar())
    assert enriched.initial_capital_at == enriched.equity[0].evaluation_at.replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    assert all(point.evaluation_at is not None for point in enriched.equity)


def test_legacy_result_without_equity_is_preserved() -> None:
    request = MarketResearchRequest(
        market="KR",
        start_date=datetime(2023, 3, 15, tzinfo=UTC).date(),
        end_date=datetime(2024, 3, 15, tzinfo=UTC).date(),
        stage="pilot",
    )
    source = FixtureMarketHistorySource()
    snapshot = asyncio.run(source.collect(request))
    result = run_market_research(
        snapshot,
        request,
        source.readiness("KR", datetime(2024, 3, 15, tzinfo=UTC)),
        default_market_calendar(),
    ).model_copy(update={"equity": (), "initial_capital_at": None})
    assert attach_time_evidence(result, default_market_calendar()) == result
