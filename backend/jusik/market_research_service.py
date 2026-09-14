from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from jusik.market_history_models import (
    Market,
    MarketReadiness,
    MarketResearchRequest,
    MarketResearchRun,
)
from jusik.market_history_sources import MarketHistorySource, data_contract_hash
from jusik.market_history_store import MarketHistoryStore
from jusik.market_research_config import load_market_research_settings
from jusik.market_research_strategy import (
    market_research_policy_hash,
    run_market_research,
)
from jusik.research_market_calendar import MarketCalendar, default_market_calendar


class MarketResearchNotFound(LookupError):
    pass


class MarketResearchConflict(ValueError):
    pass


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

    def _pilot_for_final(self, request: MarketResearchRequest) -> MarketResearchRun:
        if request.stage != "final":
            return MarketResearchRun(
                id="legacy-placeholder",
                status="queued",
                request=request,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        assert request.pilot_run_id is not None
        try:
            pilot = self.store.get_run(request.pilot_run_id)
        except KeyError as exc:
            raise MarketResearchNotFound("pilot run not found") from exc
        if (
            pilot.stage != "pilot"
            or pilot.status != "completed"
            or pilot.result is None
            or pilot.result.status != "ready"
            or pilot.result.completeness != "complete"
        ):
            raise MarketResearchConflict(
                "pilot run is not an eligible completed result"
            )
        if pilot.request.market != request.market:
            raise MarketResearchConflict("pilot market does not match final market")
        if pilot.result.policy_hash != self.policy_hash:
            raise MarketResearchConflict("pilot policy does not match current policy")
        for field in ("initial_cash_krw", "fee_rate", "slippage_rate", "sell_tax_rate"):
            if getattr(pilot.request, field) != getattr(request, field):
                raise MarketResearchConflict("pilot execution assumptions do not match")
        if pilot.data_contract_hash is None:
            raise MarketResearchConflict("pilot data contract is unavailable")
        return pilot

    async def create_run(self, request: MarketResearchRequest) -> MarketResearchRun:
        pilot = self._pilot_for_final(request)
        try:
            readiness = self.source.readiness(request.market, datetime.now(UTC))
            snapshot = await self.source.collect(request)
            contract_hash = data_contract_hash(snapshot, readiness)
            snapshot = snapshot.model_copy(update={"data_contract_hash": contract_hash})
            if request.stage == "final" and pilot.data_contract_hash != contract_hash:
                raise MarketResearchConflict("final data contract does not match pilot")
        except (MarketResearchNotFound, MarketResearchConflict):
            raise
        except Exception as exc:
            raise RuntimeError("market research source collection failed") from exc
        run = self.store.create_run(request)
        try:
            for artifact in snapshot.source_artifacts:
                content = artifact.decoded_content
                saved_digest = self.store.save_artifact(
                    content,
                    content_type=artifact.content_type,
                    captured_at=artifact.captured_at,
                )
                if saved_digest != artifact.artifact_id:
                    raise ValueError("saved artifact digest does not match metadata")
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
                data_contract_hash=contract_hash,
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
