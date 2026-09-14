from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from jusik.market_history_models import (
    Market,
    MarketReadiness,
    MarketResearchRequest,
    MarketResearchRun,
)
from jusik.market_history_sources import MarketHistorySource
from jusik.market_history_store import MarketHistoryStore
from jusik.market_research_config import load_market_research_settings
from jusik.market_research_strategy import (
    market_research_policy_hash,
    run_market_research,
)
from jusik.research_market_calendar import MarketCalendar, default_market_calendar


class MarketResearchService:
    def __init__(
        self,
        source: MarketHistorySource,
        store: MarketHistoryStore,
        *,
        calendar: MarketCalendar | None = None,
    ) -> None:
        self.source = source
        self.store = store
        self.calendar = calendar or default_market_calendar()
        self.policy_hash = market_research_policy_hash()

    def readiness(self, market: Market) -> MarketReadiness:
        return self.source.readiness(market, datetime.now(UTC))

    async def create_run(self, request: MarketResearchRequest) -> MarketResearchRun:
        run = self.store.create_run(request)
        try:
            readiness = self.source.readiness(request.market, datetime.now(UTC))
            snapshot = await self.source.collect(request)
            for artifact in snapshot.source_artifacts:
                if artifact.raw_content:
                    saved_digest = self.store.save_artifact(
                        artifact.raw_content,
                        content_type=artifact.content_type,
                        captured_at=artifact.captured_at,
                    )
                    if saved_digest != artifact.artifact_id:
                        raise ValueError(
                            "saved artifact digest does not match metadata"
                        )
            snapshot_hash = self.store.save_snapshot(snapshot)
            result = run_market_research(
                snapshot,
                request,
                readiness,
                self.calendar,
                policy_hash=self.policy_hash,
            )
            self.store.update_run(
                run.id,
                status="completed" if result.status == "ready" else "insufficient",
                result=result,
                input_hash=snapshot_hash,
            )
        except Exception as exc:
            self.store.update_run(
                run.id,
                status="failed",
                error="PIT 자료 수집 또는 검증에 실패했습니다.",
            )
            raise RuntimeError("market research run failed") from exc
        return self.store.get_run(run.id)


def production_market_research_service(path: Path) -> MarketResearchService:
    from jusik.market_history_sources import UnavailableMarketHistorySource

    configured = load_market_research_settings()
    return MarketResearchService(
        UnavailableMarketHistorySource(configured), MarketHistoryStore(path)
    )
