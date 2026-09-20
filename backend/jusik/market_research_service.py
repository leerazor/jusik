from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Protocol, cast

from jusik.market_history_approximate import (
    ApproximateMarketHistorySource,
    JsonApproximateProvider,
    run_approximate_market_research,
)
from jusik.market_history_models import (
    STAGED_FEE_RATE,
    STAGED_INITIAL_CASH_KRW,
    STAGED_SELL_TAX_RATE,
    STAGED_SLIPPAGE_RATE,
    Capability,
    CapabilityName,
    Market,
    MarketHistorySnapshot,
    MarketReadiness,
    MarketResearchAccountMetadata,
    MarketResearchProvenance,
    MarketResearchRequest,
    MarketResearchRun,
    ResearchGrade,
    SourceName,
)
from jusik.market_history_sources import MarketHistorySource, data_contract_hash
from jusik.market_history_store import MarketHistoryStore
from jusik.market_research_config import load_market_research_settings
from jusik.market_research_strategy import (
    market_research_policy_for_grade,
    market_research_policy_hash,
    run_market_research,
)
from jusik.market_time_evidence import attach_time_evidence
from jusik.research_market_calendar import MarketCalendar, default_market_calendar


class MarketResearchNotFound(LookupError):
    pass


class MarketResearchConflict(ValueError):
    pass


class ApproximateSource(Protocol):
    def readiness(self, market: Market, checked_at: datetime) -> MarketReadiness: ...

    async def collect(
        self, request: MarketResearchRequest
    ) -> MarketHistorySnapshot: ...


def _provenance_sources(items: Iterable[object]) -> tuple[SourceName, ...] | None:
    sources = {cast(SourceName, getattr(item, "source")) for item in items}
    return tuple(sorted(sources)) or None


def _snapshot_provenance(
    snapshot: MarketHistorySnapshot,
) -> MarketResearchProvenance:
    """Expose only source facts present in the immutable snapshot."""
    has_snapshot_data = bool(
        snapshot.memberships
        or snapshot.bars
        or snapshot.fx
        or snapshot.source_artifacts
    )
    has_normalized_rows = bool(snapshot.memberships or snapshot.bars)
    return MarketResearchProvenance(
        universe_sources=_provenance_sources(snapshot.memberships),
        bar_sources=_provenance_sources(snapshot.bars),
        fx_sources=_provenance_sources(snapshot.fx),
        artifact_sources=_provenance_sources(snapshot.source_artifacts),
        normalization_version=(
            snapshot.normalization_version if has_normalized_rows else None
        ),
        captured_at=snapshot.captured_at if has_snapshot_data else None,
    )


def _account_metadata(
    request: MarketResearchRequest,
    result_metrics: dict[str, Decimal],
) -> MarketResearchAccountMetadata:
    """Build non-identifying account and currency facts from the result request."""
    is_kr = request.market == "KR"
    return MarketResearchAccountMetadata(
        native_currency="KRW" if is_kr else "USD",
        initial_cash_krw=request.initial_cash_krw,
        fx_krw_per_usd=(
            Decimal("1") if is_kr else result_metrics.get("initial_fx_krw_per_usd")
        ),
        initial_cash_conversion="identity" if is_kr else "initial_krw_to_usd",
    )


class MarketResearchService:
    def __init__(
        self,
        source: MarketHistorySource,
        store: MarketHistoryStore,
        *,
        calendar: MarketCalendar | None = None,
        approximate_source: ApproximateSource | None = None,
    ) -> None:
        self.source = source
        self.store = store
        self.calendar = calendar or default_market_calendar()
        self.approximate_source = approximate_source
        self.policy_hash = market_research_policy_hash()

    def _policy_hash_for_grade(self, grade: ResearchGrade) -> str:
        return market_research_policy_hash(market_research_policy_for_grade(grade))

    def _source_for_grade(self, grade: ResearchGrade) -> MarketHistorySource:
        if grade == "approximate":
            if self.approximate_source is None:
                raise MarketResearchConflict("approximate source is not configured")
            return self.approximate_source
        return self.source

    def readiness(
        self, market: Market, grade: ResearchGrade = "strict"
    ) -> MarketReadiness:
        try:
            source = self._source_for_grade(grade)
        except MarketResearchConflict:
            names: tuple[CapabilityName, ...] = (
                "credentials",
                "entitlement",
                "calendar",
                "membership",
                "bars",
                "actions",
                "fx",
                "policy",
            )
            return MarketReadiness(
                market=market,
                checked_at=datetime.now(UTC),
                capabilities=tuple(
                    Capability(
                        name=name,
                        status="missing",
                        detail="approximate source is not configured",
                    )
                    for name in names
                ),
                ready=False,
                research_grade=grade,
            )
        return source.readiness(market, datetime.now(UTC))

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
        expected_grade: ResearchGrade | None = None,
    ) -> tuple[bool, str]:
        """Return the server-owned predicate used before a final run."""
        if pilot.stage != "pilot":
            return False, "파일럿 단계가 아닙니다."
        if expected_market is not None and pilot.request.market != expected_market:
            return False, "파일럿 시장이 일치하지 않습니다."
        if (
            expected_grade is not None
            and pilot.request.research_grade != expected_grade
        ):
            return False, "파일럿 자료 등급이 일치하지 않습니다."
        if pilot.status != "completed" or pilot.result is None:
            return False, "완료된 파일럿 결과가 없습니다."
        expected_status = (
            ("ready", "complete")
            if pilot.request.research_grade == "strict"
            else ("approximate", "approximate")
        )
        if (
            pilot.result.status != expected_status[0]
            or pilot.result.completeness != expected_status[1]
        ):
            return False, "파일럿 자료가 완전하게 확인되지 않았습니다."
        if pilot.result.research_grade != pilot.request.research_grade:
            return False, "파일럿 자료 등급이 일치하지 않습니다."
        if not self._fixed_assumptions_match(pilot.request):
            return (
                False,
                "현재 실행 가정과 일치하지 않아 최종 단계에서 참조할 수 없습니다.",
            )
        if pilot.result.policy_hash != self._policy_hash_for_grade(
            pilot.request.research_grade
        ):
            return False, "현재 연구 정책과 일치하지 않습니다."
        if (
            pilot.data_contract_hash is None
            or pilot.result.data_contract_hash is None
            or pilot.data_contract_hash != pilot.result.data_contract_hash
        ):
            return False, "파일럿 자료 계약을 확인할 수 없습니다."
        try:
            current_readiness = self._source_for_grade(
                pilot.request.research_grade
            ).readiness(pilot.request.market, datetime.now(UTC))
        except Exception:
            return False, "현재 자료 공급원 상태를 확인할 수 없습니다."
        if current_readiness.simulated != pilot.result.readiness.simulated:
            return (
                False,
                "현재 자료 공급원 조건이 파일럿과 달라 "
                "최종 단계에서 참조할 수 없습니다.",
            )
        if current_readiness.research_grade != pilot.request.research_grade:
            return (
                False,
                "현재 자료 등급이 파일럿과 달라 최종 단계에서 참조할 수 없습니다.",
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
            pilot,
            expected_market=request.market,
            expected_grade=request.research_grade,
        )
        if not promotable:
            raise MarketResearchConflict(reason)
        return pilot

    async def create_run(self, request: MarketResearchRequest) -> MarketResearchRun:
        pilot = self._pilot_for_final(request)
        try:
            source = self._source_for_grade(request.research_grade)
            readiness = source.readiness(request.market, datetime.now(UTC))
            snapshot = await source.collect(request)
            if (
                readiness.research_grade != request.research_grade
                or snapshot.research_grade != request.research_grade
            ):
                raise MarketResearchConflict(
                    "research grade does not match configured source"
                )
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
            if request.research_grade == "approximate":
                result = run_approximate_market_research(
                    snapshot,
                    request,
                    readiness,
                    self.calendar,
                    policy_hash=self._policy_hash_for_grade(request.research_grade),
                )
            else:
                result = run_market_research(
                    snapshot,
                    request,
                    readiness,
                    self.calendar,
                    policy_hash=self._policy_hash_for_grade(request.research_grade),
                )
            result = attach_time_evidence(result, self.calendar)
            result = result.model_copy(
                update={
                    "provenance": _snapshot_provenance(snapshot),
                    "account": _account_metadata(request, result.metrics),
                }
            )
            self.store.update_run(
                run.id,
                status=(
                    "completed"
                    if result.status in {"ready", "approximate"}
                    else "insufficient"
                ),
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
    approximate_source = ApproximateMarketHistorySource(
        JsonApproximateProvider(configured.approximate_data_path)
    )
    return MarketResearchService(
        UnavailableMarketHistorySource(configured),
        MarketHistoryStore(path),
        approximate_source=approximate_source,
    )
