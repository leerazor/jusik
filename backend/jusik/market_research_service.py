from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from jusik.market_history_models import (
    STAGED_FEE_RATE,
    STAGED_INITIAL_CASH_KRW,
    STAGED_SELL_TAX_RATE,
    STAGED_SLIPPAGE_RATE,
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

    @staticmethod
    def _fixed_assumptions_match(request: MarketResearchRequest) -> bool:
        return all(
            getattr(request, field) == expected
            for field, expected in (
                ("initial_cash_krw", STAGED_INITIAL_CASH_KRW),
                ("fee_rate", STAGED_FEE_RATE),
                ("slippage_rate", STAGED_SLIPPAGE_RATE),
                ("sell_tax_rate", STAGED_SELL_TAX_RATE),
            )
        )

    def pilot_promotability(
        self,
        pilot: MarketResearchRun,
        *,
        expected_market: Market | None = None,
    ) -> tuple[bool, str]:
        """Return the server-owned predicate used before a final run."""
        if pilot.stage != "pilot":
            return False, "파일럿 단계가 아닙니다."
        if expected_market is not None and pilot.request.market != expected_market:
            return False, "파일럿 시장이 일치하지 않습니다."
        if pilot.status != "completed" or pilot.result is None:
            return False, "완료된 파일럿 결과가 없습니다."
        if pilot.result.status != "ready" or pilot.result.completeness != "complete":
            return False, "파일럿 자료가 완전하게 확인되지 않았습니다."
        if not self._fixed_assumptions_match(pilot.request):
            return (
                False,
                "현재 실행 가정과 일치하지 않아 최종 단계에서 참조할 수 없습니다.",
            )
        if pilot.result.policy_hash != self.policy_hash:
            return False, "현재 연구 정책과 일치하지 않습니다."
        if (
            pilot.data_contract_hash is None
            or pilot.result.data_contract_hash is None
            or pilot.data_contract_hash != pilot.result.data_contract_hash
        ):
            return False, "파일럿 자료 계약을 확인할 수 없습니다."
        try:
            current_readiness = self.source.readiness(
                pilot.request.market, datetime.now(UTC)
            )
        except Exception:
            return False, "현재 자료 공급원 상태를 확인할 수 없습니다."
        if current_readiness.simulated != pilot.result.readiness.simulated:
            return (
                False,
                "현재 자료 공급원 조건이 파일럿과 달라 "
                "최종 단계에서 참조할 수 없습니다.",
            )
        return True, ""

    def annotate_run(self, run: MarketResearchRun) -> MarketResearchRun:
        if run.stage != "pilot":
            return run.model_copy(
                update={
                    "final_promotable": False,
                    "final_promotability_reason": "파일럿 단계가 아닙니다.",
                }
            )
        promotable, reason = self.pilot_promotability(run)
        return run.model_copy(
            update={
                "final_promotable": promotable,
                "final_promotability_reason": reason,
            }
        )

    def _pilot_for_final(self, request: MarketResearchRequest) -> MarketResearchRun:
        if request.stage == "legacy":
            raise MarketResearchConflict(
                "new research runs require pilot or final stage"
            )
        if not self._fixed_assumptions_match(request):
            raise MarketResearchConflict(
                "execution assumptions are fixed by the mandate"
            )
        if request.stage != "final":
            return MarketResearchRun(
                id="pilot-placeholder",
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
        promotable, reason = self.pilot_promotability(
            pilot, expected_market=request.market
        )
        if not promotable:
            raise MarketResearchConflict(reason)
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
        return self.annotate_run(self.store.get_run(run.id))


def production_market_research_service(path: Path) -> MarketResearchService:
    from jusik.market_history_sources import UnavailableMarketHistorySource

    configured = load_market_research_settings()
    return MarketResearchService(
        UnavailableMarketHistorySource(configured), MarketHistoryStore(path)
    )
