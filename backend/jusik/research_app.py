import asyncio
import csv
import io
import re
import sqlite3
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

import httpx
from fastapi import FastAPI, HTTPException, Query, Response, status
from fastapi.responses import FileResponse
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
from jusik.research_action_collection import (
    DEFAULT_ACTION_COLLECTION_DB,
    ActionCollector,
)
from jusik.research_action_collection_models import (
    ActionCollectionStatus,
    ActionEventPage,
    ActionRevisionPage,
    ActionSourceStatus,
)
from jusik.research_action_collection_store import ActionCollectionStore
from jusik.research_action_review import ActionReviewPage
from jusik.research_action_review_store import ActionReviewStore
from jusik.research_ai import PROMPT_VERSION, OpenAiResearchReviewer
from jusik.research_automation import ResearchAutomation
from jusik.research_boundary_capture import (
    DEFAULT_BOUNDARY_CAPTURE_DIR,
    BoundaryCaptureMonitor,
    BoundaryCaptureStatus,
)
from jusik.research_boundary_evidence import (
    BoundaryEvidenceResult,
    boundary_evidence,
)
from jusik.research_clock_health import ClockHealthMonitor
from jusik.research_config import ResearchSettings, load_research_settings
from jusik.research_data import HistoricalDataProvider, KisPaperHistoricalData
from jusik.research_dividend_overlay import (
    DEFAULT_DIVIDEND_REPORT_DIR,
    DividendOverlayRepository,
)
from jusik.research_dividend_overlay_models import DividendOverlayResult
from jusik.research_engine import ENGINE_SPECIFICATION, IMPLEMENTATION_HASH
from jusik.research_external_store import ExternalStore
from jusik.research_forward import DEFAULT_FORWARD_DB, ForwardCoordinator
from jusik.research_forward_models import (
    ForwardClockHealth,
    ForwardDecision,
    ForwardEvent,
    ForwardLedger,
    ForwardObservation,
    ForwardStatus,
)
from jusik.research_forward_store import ForwardStore
from jusik.research_history import (
    DEFAULT_HISTORY_DB,
    DEFAULT_HISTORY_DIR,
    HistoryPage,
    HistoryRepository,
)
from jusik.research_models import (
    ResearchRun,
    ResearchRunRequest,
    ResearchRunSummary,
    SymbolMetadata,
)
from jusik.research_portfolio import (
    DEFAULT_EXTERNAL_DB,
    DEFAULT_INPUT_DB,
    DEFAULT_REPORT_DIR,
    PortfolioRunRepository,
)
from jusik.research_portfolio_models import PortfolioRunResult, PortfolioRunStatus
from jusik.research_portfolio_robustness import (
    DEFAULT_VALIDATION_REPORT_DIR,
    PortfolioRobustnessRepository,
    PortfolioRobustnessResult,
)
from jusik.research_prospective_readiness import (
    ProspectiveReadiness,
    prospective_readiness,
)
from jusik.research_prospective_registration import (
    DEFAULT_CODE_ROOT,
    DEFAULT_PROSPECTIVE_DIR,
    ProspectiveRegistrationStatus,
    code_identity,
    prospective_registration_status,
)
from jusik.research_signal_validation import (
    SignalValidationResult,
    latest_completed_signal_date,
    validate_signal_store,
)
from jusik.research_store import ResearchStore
from jusik.research_universe_data import REGISTRY
from jusik.research_universe_store import UniverseInputStore
from jusik.research_worker import ResearchWorker

KST = ZoneInfo("Asia/Seoul")


def create_research_app(
    *,
    settings: ResearchSettings | None = None,
    store: ResearchStore | None = None,
    provider: HistoricalDataProvider | None = None,
    operations_store: OperationsStore | None = None,
    portfolio_report_dir: Path = DEFAULT_REPORT_DIR,
    dividend_report_dir: Path = DEFAULT_DIVIDEND_REPORT_DIR,
    validation_report_dir: Path = DEFAULT_VALIDATION_REPORT_DIR,
    prospective_dir: Path = DEFAULT_PROSPECTIVE_DIR,
    prospective_source_report_dir: Path = DEFAULT_REPORT_DIR,
    prospective_code_root: Path = DEFAULT_CODE_ROOT,
    forward_db_path: Path | None = None,
    universe_db_path: Path = DEFAULT_INPUT_DB,
    external_db_path: Path = DEFAULT_EXTERNAL_DB,
    history_dir: Path | None = None,
    history_db_path: Path | None = None,
    action_collection_db_path: Path | None = None,
    action_collection_enabled: bool = True,
    action_collection_client: httpx.AsyncClient | None = None,
    run_clock_health_background: bool = False,
    clock_health_probe: Callable[[], Awaitable[ForwardClockHealth]] | None = None,
    boundary_capture_dir: Path = DEFAULT_BOUNDARY_CAPTURE_DIR,
    run_boundary_capture_background: bool = False,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configured = settings or load_research_settings()
        run_store = store or ResearchStore(configured.db_path)
        resolved_forward_db = forward_db_path or run_store.path.with_name(
            DEFAULT_FORWARD_DB.name
        )
        resolved_history_dir = (
            history_dir or run_store.path.parent / DEFAULT_HISTORY_DIR.name
        )
        resolved_history_db = history_db_path or run_store.path.with_name(
            DEFAULT_HISTORY_DB.name
        )
        resolved_action_collection_db = (
            action_collection_db_path
            or run_store.path.with_name(DEFAULT_ACTION_COLLECTION_DB.name)
        )
        history_repository = HistoryRepository(
            resolved_history_dir, resolved_history_db
        )
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

        async def record_run_history(run_id: str, outcome: str) -> None:
            history_repository.record(
                identity=f"research-run-{run_id}-{outcome}",
                title="단일 연구 실행 종료",
                summary=f"저장된 연구 실행이 {outcome} 상태로 종료되었습니다.",
                category="research",
                outcome=outcome,
                occurred_at=datetime.now(UTC),
                run_ids=[run_id],
            )

        worker = ResearchWorker(
            run_store,
            data_provider,
            automation.on_completed,
            record_run_history,
        )
        automation.attach_worker(worker)
        forward_store = ForwardStore(resolved_forward_db)
        forward: ForwardCoordinator
        stream = KisReadOnlyStream(
            configured,
            client,
            operation_store.universe,
            operation_store.stream_enabled,
            automation.on_quote,
            research_instruments=lambda: REGISTRY,
            forward_enabled=lambda: forward.enabled(),
            on_research_quote=lambda quote: forward.on_quote(quote),
        )
        forward = ForwardCoordinator(
            forward_store,
            UniverseInputStore(universe_db_path),
            ExternalStore(external_db_path),
            stream.research_status,
            history=history_repository,
        )
        if clock_health_probe is None:
            clock_health = ClockHealthMonitor(forward_store)
        else:
            clock_health = ClockHealthMonitor(forward_store, probe=clock_health_probe)
        action_store: ActionCollectionStore | None = None
        action_collector: ActionCollector | None = None
        action_review_store: ActionReviewStore | None = None
        action_client = action_collection_client
        action_collection_error: str | None = (
            "collection_disabled" if not action_collection_enabled else None
        )
        try:
            action_store = ActionCollectionStore(resolved_action_collection_db)
            if action_collection_enabled:
                if action_client is None:
                    action_client = httpx.AsyncClient(
                        base_url="https://query1.finance.yahoo.com",
                        timeout=httpx.Timeout(30),
                        headers={"User-Agent": "jusik-offline-research/1.0"},
                        follow_redirects=False,
                        trust_env=False,
                    )
                action_collector = ActionCollector(action_store, action_client)
                action_collector.start()
        except Exception:
            action_collection_error = "collector_startup_failed"
        try:
            action_review_store = ActionReviewStore(resolved_action_collection_db)
        except Exception:
            pass
        app.state.research_store = run_store
        app.state.research_worker = worker
        app.state.operations_store = operation_store
        app.state.automation = automation
        app.state.stream = stream
        app.state.forward = forward
        app.state.forward_store = forward_store
        app.state.clock_health = clock_health
        app.state.history_repository = history_repository
        app.state.action_collection_store = action_store
        app.state.action_collector = action_collector
        app.state.action_review_store = action_review_store
        app.state.action_collection_error = action_collection_error
        try:
            app.state.prospective_app_start_code_identity_sha256 = code_identity(
                prospective_code_root
            ).sha256
        except (OSError, ValueError):
            app.state.prospective_app_start_code_identity_sha256 = None
        boundary_capture = BoundaryCaptureMonitor(
            forward_db=forward_store.path,
            output_dir=boundary_capture_dir,
            registration_status=lambda checked_at: prospective_registration_status(
                forward_db=forward_store.path,
                source_report_dir=prospective_source_report_dir,
                output_dir=prospective_dir,
                code_root=prospective_code_root,
                app_start_code_identity_sha256=(
                    app.state.prospective_app_start_code_identity_sha256
                ),
                now=checked_at,
            ),
        )
        app.state.boundary_capture = boundary_capture
        app.state.settings = configured
        worker.start()
        automation.start()
        stream.start()
        forward.start()
        if run_clock_health_background:
            clock_health.start()
        if run_boundary_capture_background:
            boundary_capture.start()
        try:
            yield
        finally:
            await boundary_capture.stop()
            await clock_health.stop()
            if action_collector is not None:
                await action_collector.stop()
            elif action_client is not None:
                await action_client.aclose()
            await forward.stop()
            await stream.stop()
            await automation.stop()
            await worker.stop()
            await client.aclose()

    research_app = FastAPI(title="Jusik paper research", lifespan=lifespan)
    research_app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["127.0.0.1", "localhost", "testserver"],
    )
    portfolio_repository = PortfolioRunRepository(portfolio_report_dir)
    dividend_repository = DividendOverlayRepository(dividend_report_dir)
    robustness_repository = PortfolioRobustnessRepository(validation_report_dir)

    def forward_components() -> tuple[ForwardCoordinator, ForwardStore]:
        return research_app.state.forward, research_app.state.forward_store

    @research_app.get(
        "/api/research/actions/status", response_model=ActionCollectionStatus
    )
    async def action_collection_status(response: Response) -> ActionCollectionStatus:
        response.headers["Cache-Control"] = "no-store"
        collector: ActionCollector | None = research_app.state.action_collector
        current = datetime.now(UTC)
        store: ActionCollectionStore | None = research_app.state.action_collection_store
        try:
            if collector is not None:
                return await collector.status()
            if store is not None:
                return await asyncio.to_thread(
                    store.status,
                    REGISTRY,
                    current,
                    collector_state="idle",
                    error_code=research_app.state.action_collection_error,
                )
        except (OSError, sqlite3.Error, ValueError):
            pass
        return ActionCollectionStatus(
            collector_state="error",
            error_code=research_app.state.action_collection_error,
            generated_at=current,
            sources=[
                ActionSourceStatus(
                    symbol=item.symbol,
                    yahoo_symbol=item.yahoo_symbol,
                    state="never",
                    next_due_at=current,
                    stale=True,
                )
                for item in REGISTRY
            ],
        )

    @research_app.get("/api/research/actions/events", response_model=ActionEventPage)
    async def action_collection_events(
        response: Response,
        cursor: str | None = Query(default=None, max_length=64),
        limit: int = Query(default=50, ge=1, le=100),
    ) -> ActionEventPage:
        response.headers["Cache-Control"] = "no-store"
        if cursor is not None and re.fullmatch(r"[a-f0-9]{64}", cursor) is None:
            raise HTTPException(status_code=400, detail="Invalid cursor.")
        store: ActionCollectionStore | None = research_app.state.action_collection_store
        if store is None:
            raise HTTPException(
                status_code=503, detail="Action collection unavailable."
            )
        try:
            return await asyncio.to_thread(store.event_page, cursor, limit)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid cursor.") from None
        except sqlite3.Error:
            raise HTTPException(
                status_code=503, detail="Action collection unavailable."
            ) from None

    @research_app.get(
        "/api/research/actions/revisions", response_model=ActionRevisionPage
    )
    async def action_collection_revisions(
        response: Response,
        cursor: str | None = Query(default=None, max_length=64),
        limit: int = Query(default=50, ge=1, le=100),
    ) -> ActionRevisionPage:
        response.headers["Cache-Control"] = "no-store"
        if cursor is not None and re.fullmatch(r"[a-f0-9]{64}", cursor) is None:
            raise HTTPException(status_code=400, detail="Invalid cursor.")
        store: ActionCollectionStore | None = research_app.state.action_collection_store
        if store is None:
            raise HTTPException(
                status_code=503, detail="Action collection unavailable."
            )
        try:
            return await asyncio.to_thread(store.revision_page, cursor, limit)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid cursor.") from None
        except sqlite3.Error:
            raise HTTPException(
                status_code=503, detail="Action collection unavailable."
            ) from None

    @research_app.get("/api/research/actions/raw/{attempt_id}")
    async def action_collection_raw(attempt_id: str) -> Response:
        if re.fullmatch(r"[a-f0-9]{64}", attempt_id) is None:
            raise HTTPException(status_code=404, detail="Raw attempt not found.")
        store: ActionCollectionStore | None = research_app.state.action_collection_store
        if store is None:
            raise HTTPException(
                status_code=503, detail="Action collection unavailable."
            )
        try:
            attempt = await asyncio.to_thread(store.raw_attempt, attempt_id)
        except (KeyError, ValueError):
            raise HTTPException(
                status_code=404, detail="Raw attempt not found."
            ) from None
        except sqlite3.Error:
            raise HTTPException(
                status_code=503, detail="Action collection unavailable."
            ) from None
        return Response(
            content=attempt.body,
            media_type="application/octet-stream",
            headers={
                "Cache-Control": "private, no-store",
                "Content-Disposition": (
                    f'attachment; filename="action-attempt-{attempt.id}.body"'
                ),
                "X-Content-Type-Options": "nosniff",
                "X-Content-SHA256": attempt.body_sha256,
            },
        )

    @research_app.get("/api/research/actions/reviews", response_model=ActionReviewPage)
    async def action_reviews(
        response: Response,
        cursor: str | None = Query(default=None, max_length=64),
        event_id: str | None = Query(default=None, max_length=64),
        limit: int = Query(default=50, ge=1, le=100),
    ) -> ActionReviewPage:
        response.headers["Cache-Control"] = "no-store"
        if cursor is not None and re.fullmatch(r"[a-f0-9]{64}", cursor) is None:
            raise HTTPException(status_code=400, detail="Invalid cursor.")
        if event_id is not None and re.fullmatch(r"[a-f0-9]{64}", event_id) is None:
            raise HTTPException(status_code=400, detail="Invalid event ID.")
        store: ActionReviewStore | None = research_app.state.action_review_store
        if store is None:
            raise HTTPException(status_code=503, detail="Action reviews unavailable.")
        try:
            return await asyncio.to_thread(store.review_page, cursor, limit, event_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid cursor.") from None
        except sqlite3.Error:
            raise HTTPException(
                status_code=503, detail="Action reviews unavailable."
            ) from None

    @research_app.get("/api/research/actions/evidence/{evidence_id}")
    async def action_review_evidence(evidence_id: str) -> Response:
        if re.fullmatch(r"[a-f0-9]{64}", evidence_id) is None:
            raise HTTPException(status_code=404, detail="Review evidence not found.")
        store: ActionReviewStore | None = research_app.state.action_review_store
        if store is None:
            raise HTTPException(status_code=503, detail="Action reviews unavailable.")
        try:
            evidence = await asyncio.to_thread(store.raw_evidence, evidence_id)
        except (KeyError, ValueError):
            raise HTTPException(
                status_code=404, detail="Review evidence not found."
            ) from None
        except sqlite3.Error:
            raise HTTPException(
                status_code=503, detail="Action reviews unavailable."
            ) from None
        return Response(
            content=evidence.body,
            media_type="application/octet-stream",
            headers={
                "Cache-Control": "private, no-store",
                "Content-Disposition": (
                    f'attachment; filename="action-evidence-{evidence.id}.body"'
                ),
                "X-Content-Type-Options": "nosniff",
                "X-Content-SHA256": evidence.sha256,
            },
        )

    @research_app.get("/api/research/forward/status", response_model=ForwardStatus)
    async def forward_status(response: Response) -> ForwardStatus:
        response.headers["Cache-Control"] = "no-store"
        coordinator, _store = forward_components()
        status_result = coordinator.status()
        clock_health: ClockHealthMonitor = research_app.state.clock_health
        return status_result.model_copy(
            update={"latest_clock_health": clock_health.latest}
        )

    @research_app.get(
        "/api/research/forward/observations",
        response_model=list[ForwardObservation],
    )
    async def forward_observations(
        response: Response, limit: int = Query(default=200, ge=1, le=1000)
    ) -> list[ForwardObservation]:
        response.headers["Cache-Control"] = "no-store"
        coordinator, store = forward_components()
        return store.observations(coordinator.ensure_session().id, limit)

    @research_app.get(
        "/api/research/forward/decisions", response_model=list[ForwardDecision]
    )
    async def forward_decisions(
        response: Response, limit: int = Query(default=100, ge=1, le=500)
    ) -> list[ForwardDecision]:
        response.headers["Cache-Control"] = "no-store"
        coordinator, store = forward_components()
        return store.decisions(coordinator.ensure_session().id, limit)

    @research_app.get("/api/research/forward/ledger", response_model=ForwardLedger)
    async def forward_ledger(response: Response) -> ForwardLedger:
        response.headers["Cache-Control"] = "no-store"
        coordinator, store = forward_components()
        return store.ledger(coordinator.ensure_session().id)

    @research_app.get("/api/research/forward/events", response_model=list[ForwardEvent])
    async def forward_events(
        response: Response, limit: int = Query(default=200, ge=1, le=500)
    ) -> list[ForwardEvent]:
        response.headers["Cache-Control"] = "no-store"
        coordinator, store = forward_components()
        return store.events(coordinator.ensure_session().id, limit)

    @research_app.get("/api/research/forward/export/{name}")
    async def forward_export(name: str) -> Response:
        allowed = {
            "observations.csv",
            "decisions.csv",
            "fills.csv",
            "events.csv",
            "equity.csv",
        }
        if name not in allowed:
            raise HTTPException(status_code=404, detail="Forward export not found.")
        coordinator, store = forward_components()
        session_id = coordinator.ensure_session().id
        output = io.StringIO()
        writer = csv.writer(output)
        if name == "observations.csv":
            writer.writerow(
                [
                    "id",
                    "symbol",
                    "market_at",
                    "received_at",
                    "price",
                    "source",
                    "reason",
                ]
            )
            for observation in store.observations(session_id, 1000):
                writer.writerow(
                    [
                        observation.id,
                        observation.quote.symbol,
                        observation.quote.market_at.isoformat(),
                        observation.quote.received_at.isoformat(),
                        observation.quote.price,
                        observation.quote.source,
                        observation.persisted_reason,
                    ]
                )
        elif name == "decisions.csv":
            writer.writerow(
                ["id", "due_at", "recorded_at", "state", "input_version", "reason"]
            )
            for decision in store.decisions(session_id, 500):
                writer.writerow(
                    [
                        decision.id,
                        decision.due_at.isoformat(),
                        decision.recorded_at.isoformat(),
                        decision.state,
                        decision.input_version,
                        decision.reason,
                    ]
                )
        elif name == "fills.csv":
            writer.writerow(
                [
                    "id",
                    "decision_id",
                    "symbol",
                    "side",
                    "quantity",
                    "market_at",
                    "local_price",
                    "fx_rate",
                    "notional_krw",
                    "cash_after_krw",
                ]
            )
            for fill in store.fills(session_id, 500):
                writer.writerow(
                    [
                        fill.id,
                        fill.decision_id,
                        fill.symbol,
                        fill.side,
                        fill.quantity,
                        fill.market_at.isoformat(),
                        fill.local_price,
                        fill.fx_rate,
                        fill.notional_krw,
                        fill.cash_after_krw,
                    ]
                )
        elif name == "events.csv":
            writer.writerow(["id", "occurred_at", "kind", "detail", "reference_id"])
            for event in store.events(session_id, 500):
                writer.writerow(
                    [
                        event.id,
                        event.occurred_at.isoformat(),
                        event.kind,
                        event.detail,
                        event.reference_id or "",
                    ]
                )
        else:
            writer.writerow(["notice"])
            writer.writerow(["No close checkpoint has been recorded since activation."])
        return Response(
            content=output.getvalue(),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{name}"',
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )

    @research_app.get("/api/research/history", response_model=HistoryPage)
    async def research_history(
        response: Response,
        cursor: str | None = Query(default=None, max_length=160),
        limit: int = Query(default=50, ge=1, le=100),
    ) -> HistoryPage:
        response.headers["Cache-Control"] = "no-store"
        repository: HistoryRepository = research_app.state.history_repository
        return repository.page(cursor, limit)

    @research_app.get("/api/research/history/artifacts/{artifact_id}")
    async def history_artifact(artifact_id: str) -> FileResponse:
        try:
            repository: HistoryRepository = research_app.state.history_repository
            path, artifact = repository.artifact_path(artifact_id)
        except (OSError, ValueError):
            raise HTTPException(
                status_code=404, detail="History artifact not found."
            ) from None
        return FileResponse(
            path,
            filename=artifact.filename,
            media_type="text/markdown",
            headers={
                "Cache-Control": "public, max-age=31536000, immutable",
                "X-Content-Type-Options": "nosniff",
            },
        )

    @research_app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "mode": "paper-research"}

    @research_app.get(
        "/api/research/portfolio/latest",
        response_model=PortfolioRunResult,
    )
    async def latest_portfolio(response: Response) -> PortfolioRunResult:
        response.headers["Cache-Control"] = "no-store"
        latest = portfolio_repository.latest()
        if latest is None:
            raise HTTPException(status_code=404, detail="Portfolio result not found.")
        return latest

    @research_app.get(
        "/api/research/portfolio/dividends/latest",
        response_model=DividendOverlayResult,
    )
    async def latest_dividend_overlay(response: Response) -> DividendOverlayResult:
        response.headers["Cache-Control"] = "no-store"
        try:
            latest = dividend_repository.latest()
        except (OSError, ValueError, KeyError):
            raise HTTPException(
                status_code=503, detail="Dividend overlay unavailable."
            ) from None
        if latest is None:
            raise HTTPException(status_code=404, detail="Dividend overlay not found.")
        return latest

    @research_app.get(
        "/api/research/validation/signal",
        response_model=SignalValidationResult,
    )
    async def signal_validation(
        response: Response,
        local_date: date | None = Query(default=None),
    ) -> SignalValidationResult:
        response.headers["Cache-Control"] = "no-store"
        _forward, forward_store = forward_components()
        current = datetime.now(UTC)
        try:
            current_feed = research_app.state.stream.research_status()
        except Exception:
            current_feed = None
        try:
            selected_date = local_date or latest_completed_signal_date(current)
            return await asyncio.to_thread(
                validate_signal_store,
                forward_store.path,
                local_date=selected_date,
                now=current,
                current_feed=current_feed,
            )
        except (OSError, sqlite3.Error, ValueError):
            raise HTTPException(
                status_code=503, detail="Signal validation unavailable."
            ) from None

    @research_app.get(
        "/api/research/validation/prospective",
        response_model=ProspectiveRegistrationStatus,
    )
    async def prospective_validation_status(
        response: Response,
    ) -> ProspectiveRegistrationStatus:
        response.headers["Cache-Control"] = "no-store"
        _forward, forward_store = forward_components()
        return await asyncio.to_thread(
            prospective_registration_status,
            forward_db=forward_store.path,
            source_report_dir=prospective_source_report_dir,
            output_dir=prospective_dir,
            code_root=prospective_code_root,
            app_start_code_identity_sha256=(
                research_app.state.prospective_app_start_code_identity_sha256
            ),
        )

    @research_app.get(
        "/api/research/validation/prospective/readiness",
        response_model=ProspectiveReadiness,
    )
    async def prospective_validation_readiness(
        response: Response,
    ) -> ProspectiveReadiness:
        response.headers["Cache-Control"] = "no-store"
        _forward, forward_store = forward_components()

        def read() -> ProspectiveReadiness:
            checked_at = datetime.now(UTC)
            registration = prospective_registration_status(
                forward_db=forward_store.path,
                source_report_dir=prospective_source_report_dir,
                output_dir=prospective_dir,
                code_root=prospective_code_root,
                app_start_code_identity_sha256=(
                    research_app.state.prospective_app_start_code_identity_sha256
                ),
                now=checked_at,
            )
            return prospective_readiness(
                forward_db=forward_store.path,
                registration_status=registration,
                now=checked_at,
            )

        try:
            return await asyncio.to_thread(read)
        except (OSError, sqlite3.Error, ValueError):
            raise HTTPException(
                status_code=503, detail="Prospective readiness unavailable."
            ) from None

    @research_app.get(
        "/api/research/validation/prospective/boundary-captures",
        response_model=BoundaryCaptureStatus,
    )
    async def prospective_boundary_capture_status(
        response: Response,
    ) -> BoundaryCaptureStatus:
        response.headers["Cache-Control"] = "no-store"
        monitor: BoundaryCaptureMonitor = research_app.state.boundary_capture
        return await asyncio.to_thread(monitor.status)

    @research_app.get(
        "/api/research/validation/prospective/boundary-captures/{boundary}"
    )
    async def prospective_boundary_capture_artifact(
        boundary: Literal["start", "end"],
    ) -> Response:
        monitor: BoundaryCaptureMonitor = research_app.state.boundary_capture
        try:
            body, body_sha256 = await asyncio.to_thread(monitor.artifact_body, boundary)
        except (OSError, sqlite3.Error, ValueError):
            raise HTTPException(
                status_code=404, detail="Boundary capture not found."
            ) from None
        return Response(
            content=body,
            media_type="application/octet-stream",
            headers={
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "X-Content-SHA256": body_sha256,
                "Content-Disposition": (
                    f'attachment; filename="prospective-{boundary}-raw.json"'
                ),
            },
        )

    @research_app.get(
        "/api/research/validation/prospective/boundary-evidence/{boundary}",
        response_model=BoundaryEvidenceResult,
    )
    async def prospective_boundary_evidence(
        boundary: Literal["start", "end"], response: Response
    ) -> BoundaryEvidenceResult:
        response.headers["Cache-Control"] = "no-store"
        monitor: BoundaryCaptureMonitor = research_app.state.boundary_capture
        try:
            return await asyncio.to_thread(
                boundary_evidence,
                monitor,
                boundary,
                now=datetime.now(UTC),
            )
        except (OSError, ValueError):
            raise HTTPException(
                status_code=503, detail="Boundary evidence unavailable."
            ) from None

    @research_app.get(
        "/api/research/validation/portfolio/latest",
        response_model=PortfolioRobustnessResult,
    )
    async def latest_portfolio_robustness(
        response: Response,
    ) -> PortfolioRobustnessResult:
        response.headers["Cache-Control"] = "no-store"
        try:
            latest = robustness_repository.latest()
        except (OSError, ValueError, KeyError):
            raise HTTPException(
                status_code=503, detail="Portfolio robustness unavailable."
            ) from None
        if latest is None:
            raise HTTPException(
                status_code=404, detail="Portfolio robustness not found."
            )
        return latest

    @research_app.get(
        "/api/research/validation/portfolio/runs/{run_id}/artifacts/{name}"
    )
    async def portfolio_robustness_artifact(run_id: str, name: str) -> FileResponse:
        try:
            path = robustness_repository.artifact(run_id, name)
        except (OSError, ValueError, KeyError):
            raise HTTPException(status_code=404, detail="Artifact not found.") from None
        return FileResponse(
            path,
            filename=name,
            media_type="application/octet-stream",
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )

    @research_app.get(
        "/api/research/portfolio/dividends/runs/{run_id}/artifacts/{name}"
    )
    async def dividend_overlay_artifact(run_id: str, name: str) -> FileResponse:
        try:
            path = dividend_repository.artifact(run_id, name)
        except (OSError, ValueError, KeyError):
            raise HTTPException(status_code=404, detail="Artifact not found.") from None
        return FileResponse(
            path,
            filename=name,
            media_type="application/octet-stream",
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )

    @research_app.get(
        "/api/research/portfolio/status",
        response_model=PortfolioRunStatus,
    )
    async def portfolio_status(response: Response) -> PortfolioRunStatus:
        response.headers["Cache-Control"] = "no-store"
        return portfolio_repository.status()

    @research_app.get(
        "/api/research/portfolio/runs/{run_id}",
        response_model=PortfolioRunResult,
    )
    async def portfolio_run(run_id: str, response: Response) -> PortfolioRunResult:
        response.headers["Cache-Control"] = "no-store"
        try:
            return portfolio_repository.read(run_id)
        except (OSError, ValueError):
            raise HTTPException(
                status_code=404, detail="Portfolio result not found."
            ) from None

    @research_app.get("/api/research/portfolio/runs/{run_id}/artifacts/{name}")
    async def portfolio_artifact(run_id: str, name: str) -> FileResponse:
        try:
            path = portfolio_repository.artifact_path(run_id, name)
        except (OSError, ValueError):
            raise HTTPException(status_code=404, detail="Artifact not found.") from None
        media_type = "text/markdown" if path.suffix == ".md" else None
        return FileResponse(
            path,
            filename=name,
            media_type=media_type,
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )

    @research_app.get("/api/research/reports/{name}")
    async def legacy_research_report(name: str) -> FileResponse:
        allowed = {
            "external-research.md",
            "external-comparison.md",
            "model-improvement.md",
            "portfolio-next-research.md",
        }
        if name not in allowed:
            raise HTTPException(status_code=404, detail="Report not found.")
        path = portfolio_report_dir / name
        if (
            not path.is_file()
            or path.is_symlink()
            or path.resolve().parent != portfolio_report_dir.resolve()
        ):
            raise HTTPException(status_code=404, detail="Report not found.")
        return FileResponse(
            path,
            filename=name,
            media_type="text/markdown",
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )

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


app = create_research_app(
    run_clock_health_background=True,
    run_boundary_capture_background=True,
)
