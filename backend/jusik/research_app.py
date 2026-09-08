import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
from fastapi import FastAPI, HTTPException, Response, status
from starlette.middleware.trustedhost import TrustedHostMiddleware

from jusik.kis_stream import KisReadOnlyStream
from jusik.operations_models import (
    ActivateStrategyRequest,
    OperationsStatus,
    ProposalDecision,
    ProposalDecisionResult,
    ResearchSchedule,
    ResearchScheduleUpdate,
    StrategyVersionRecord,
    StreamStatus,
    StreamToggle,
    UniverseUpdate,
)
from jusik.operations_store import OperationsStore
from jusik.research_ai import PROMPT_VERSION, OpenAiResearchReviewer
from jusik.research_automation import ResearchAutomation
from jusik.research_config import ResearchSettings, load_research_settings
from jusik.research_data import HistoricalDataProvider, KisPaperHistoricalData
from jusik.research_engine import ENGINE_SPECIFICATION, IMPLEMENTATION_HASH
from jusik.research_models import (
    ResearchRun,
    ResearchRunRequest,
    ResearchRunSummary,
    SymbolMetadata,
)
from jusik.research_store import ResearchStore
from jusik.research_worker import ResearchWorker

KST = ZoneInfo("Asia/Seoul")


def create_research_app(
    *,
    settings: ResearchSettings | None = None,
    store: ResearchStore | None = None,
    provider: HistoricalDataProvider | None = None,
    operations_store: OperationsStore | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configured = settings or load_research_settings()
        run_store = store or ResearchStore(configured.db_path)
        operation_store = operations_store or OperationsStore(run_store.path)
        client = httpx.AsyncClient(
            base_url=configured.base_url,
            timeout=15,
            follow_redirects=False,
            trust_env=False,
        )
        data_provider = provider
        if data_provider is None:
            data_provider = KisPaperHistoricalData(
                configured,
                client,
                on_symbol_metadata=run_store.upsert_symbol_metadata,
            )
        reviewer = OpenAiResearchReviewer(configured, client)
        automation = ResearchAutomation(run_store, operation_store, reviewer)
        worker = ResearchWorker(run_store, data_provider, automation.on_completed)
        automation.attach_worker(worker)
        stream = KisReadOnlyStream(
            configured,
            client,
            operation_store.universe,
            operation_store.stream_enabled,
            automation.on_quote,
        )
        app.state.research_store = run_store
        app.state.research_worker = worker
        app.state.operations_store = operation_store
        app.state.automation = automation
        app.state.stream = stream
        app.state.settings = configured
        worker.start()
        automation.start()
        stream.start()
        try:
            yield
        finally:
            await stream.stop()
            await automation.stop()
            await worker.stop()
            await client.aclose()

    research_app = FastAPI(title="Jusik paper research", lifespan=lifespan)
    research_app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["127.0.0.1", "localhost", "testserver"],
    )

    @research_app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "mode": "paper-research"}

    @research_app.get("/api/operations", response_model=OperationsStatus)
    async def operations(response: Response) -> OperationsStatus:
        response.headers["Cache-Control"] = "no-store"
        operation_store: OperationsStore = research_app.state.operations_store
        stream: KisReadOnlyStream = research_app.state.stream
        configured: ResearchSettings = research_app.state.settings
        stream_status = stream.status()
        warnings = [
            (
                "실시간 시세는 확정 일봉 전략의 가격 조건과 승인 직전 "
                "재검증에만 사용합니다."
            ),
            (
                "모든 체결은 앱 내부 paper 원장에만 기록되며 증권사 주문 "
                "API를 호출하지 않습니다."
            ),
        ]
        if stream_status.state != "connected":
            warnings.append(
                "실시간 시세가 연결되지 않아 paper 체결 승인을 처리할 수 없습니다."
            )
        return OperationsStatus(
            universe=operation_store.universe(),
            schedule=operation_store.schedule(),
            versions=operation_store.versions(),
            stream=stream_status,
            quotes=stream.quotes(),
            proposals=operation_store.proposals(),
            paper_account=operation_store.paper_account(),
            ai=operation_store.ai_status(
                enabled=bool(
                    configured.openai_api_key
                    and configured.openai_model
                    and configured.openai_daily_token_budget > 0
                ),
                configured=bool(configured.openai_api_key and configured.openai_model),
                model=configured.openai_model,
                daily_token_budget=configured.openai_daily_token_budget,
                prompt_version=PROMPT_VERSION,
            ),
            warnings=warnings,
        )

    @research_app.put("/api/operations/universe", response_model=list[str])
    async def update_universe(update: UniverseUpdate) -> list[str]:
        operation_store: OperationsStore = research_app.state.operations_store
        stream: KisReadOnlyStream = research_app.state.stream
        result = operation_store.update_universe(update)
        if operation_store.stream_enabled():
            await stream.restart()
        return result

    @research_app.put("/api/operations/schedule", response_model=ResearchSchedule)
    async def update_schedule(update: ResearchScheduleUpdate) -> ResearchSchedule:
        operation_store: OperationsStore = research_app.state.operations_store
        return operation_store.update_schedule(update)

    @research_app.post("/api/operations/schedule/run", status_code=202)
    async def run_scheduled_now() -> dict[str, str]:
        automation: ResearchAutomation = research_app.state.automation
        try:
            return {"run_id": automation.enqueue_scheduled()}
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from None

    @research_app.put("/api/operations/stream", response_model=StreamStatus)
    async def update_stream(update: StreamToggle) -> StreamStatus:
        operation_store: OperationsStore = research_app.state.operations_store
        stream: KisReadOnlyStream = research_app.state.stream
        operation_store.update_stream_enabled(update.enabled)
        await stream.restart()
        return stream.status()

    @research_app.post(
        "/api/operations/strategies/activate", response_model=StrategyVersionRecord
    )
    async def activate_strategy(
        request: ActivateStrategyRequest,
    ) -> StrategyVersionRecord:
        operation_store: OperationsStore = research_app.state.operations_store
        try:
            return operation_store.activate_paper(request.version)
        except KeyError:
            raise HTTPException(status_code=404, detail="Strategy not found.") from None
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from None

    @research_app.post(
        "/api/operations/proposals/{proposal_id}/decision",
        response_model=ProposalDecisionResult,
    )
    async def decide_proposal(
        proposal_id: str, decision: ProposalDecision
    ) -> ProposalDecisionResult:
        operation_store: OperationsStore = research_app.state.operations_store
        stream: KisReadOnlyStream = research_app.state.stream
        if decision.action == "approve":
            if stream.status().state != "connected":
                raise HTTPException(
                    status_code=409,
                    detail="A fresh connected quote stream is required for approval.",
                )
            active = next(
                (item for item in operation_store.versions() if item.active_for_paper),
                None,
            )
            if active is None or active.definition.version != decision.expected_version:
                raise HTTPException(
                    status_code=409,
                    detail="The active paper strategy does not match the proposal.",
                )
            try:
                proposed = operation_store.get_proposal(proposal_id)
            except KeyError:
                raise HTTPException(
                    status_code=404, detail="Proposal not found."
                ) from None
            automation: ResearchAutomation = research_app.state.automation
            if not await asyncio.to_thread(automation.proposal_is_current, proposed):
                try:
                    operation_store.expire_proposal(
                        proposal_id,
                        "승인 직전 최신 확정 일봉 또는 입력 스냅샷이 달라졌습니다.",
                    )
                except ValueError:
                    pass
                raise HTTPException(
                    status_code=409,
                    detail="The proposal signal is no longer current.",
                )
        try:
            proposal, fill = operation_store.decide(
                proposal_id,
                decision,
                stream.quote(operation_store.get_proposal(proposal_id).symbol),
            )
            return ProposalDecisionResult(proposal=proposal, fill=fill)
        except KeyError:
            raise HTTPException(status_code=404, detail="Proposal not found.") from None
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from None

    @research_app.post(
        "/api/research/runs",
        response_model=ResearchRun,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def create_run(
        request: ResearchRunRequest, response: Response
    ) -> ResearchRun:
        if request.end_date >= datetime.now(KST).date():
            raise HTTPException(
                status_code=422,
                detail="end_date must be a completed past KST date.",
            )
        run_store: ResearchStore = research_app.state.research_store
        worker: ResearchWorker = research_app.state.research_worker
        if worker.queue_full:
            raise HTTPException(
                status_code=429,
                detail="Research queue is full. Try again after a run finishes.",
            )
        run = run_store.create(request)
        worker.enqueue(run.id)
        response.headers["Cache-Control"] = "no-store"
        return run

    @research_app.get("/api/research/runs", response_model=list[ResearchRunSummary])
    async def list_runs(response: Response) -> list[ResearchRunSummary]:
        response.headers["Cache-Control"] = "no-store"
        run_store: ResearchStore = research_app.state.research_store
        return run_store.list()

    @research_app.get(
        "/api/research/symbol-metadata", response_model=list[SymbolMetadata]
    )
    async def list_symbol_metadata(response: Response) -> list[SymbolMetadata]:
        response.headers["Cache-Control"] = "no-store"
        run_store: ResearchStore = research_app.state.research_store
        return run_store.list_symbol_metadata()

    @research_app.get("/api/research/runs/{run_id}", response_model=ResearchRun)
    async def get_run(run_id: str, response: Response) -> ResearchRun:
        response.headers["Cache-Control"] = "no-store"
        run_store: ResearchStore = research_app.state.research_store
        try:
            return run_store.get(run_id)
        except KeyError:
            raise HTTPException(
                status_code=404, detail="Research run not found."
            ) from None

    @research_app.post(
        "/api/research/runs/{run_id}/replay",
        response_model=ResearchRun,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def replay_run(run_id: str, response: Response) -> ResearchRun:
        run_store: ResearchStore = research_app.state.research_store
        worker: ResearchWorker = research_app.state.research_worker
        if worker.queue_full:
            raise HTTPException(
                status_code=429,
                detail="Research queue is full. Try again after a run finishes.",
            )
        try:
            original = run_store.get(run_id)
        except KeyError:
            raise HTTPException(
                status_code=404, detail="Research run not found."
            ) from None
        if original.input_snapshot is None:
            raise HTTPException(
                status_code=409,
                detail="Research run has no immutable input snapshot to replay.",
            )
        if (
            original.result is None
            or original.result.implementation_hash != IMPLEMENTATION_HASH
            or original.result.specification != ENGINE_SPECIFICATION
        ):
            raise HTTPException(
                status_code=409,
                detail=(
                    "The saved run does not match the loaded engine implementation; "
                    "its input cannot be replayed as the same version."
                ),
            )
        replay = run_store.create(
            original.request,
            replay_of=original.id,
            snapshot=original.input_snapshot,
        )
        worker.enqueue(replay.id)
        response.headers["Cache-Control"] = "no-store"
        return replay

    return research_app


app = create_research_app()
