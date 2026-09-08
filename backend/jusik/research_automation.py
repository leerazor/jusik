import asyncio
import hashlib
import json
import time
from datetime import date, timedelta
from decimal import ROUND_FLOOR, Decimal
from zoneinfo import ZoneInfo

from jusik.operations_models import (
    Quote,
    SignalProposal,
    SignalProposalCreate,
    StrategyDefinition,
    utc_now,
)
from jusik.operations_store import FEE_RATE, OperationsStore
from jusik.research_ai import PROMPT_VERSION, OpenAiResearchReviewer
from jusik.research_engine import run_definition_backtest
from jusik.research_models import ResearchInputSnapshot, ResearchRunRequest
from jusik.research_store import ResearchStore
from jusik.research_strategy import signal_input_fingerprint, target_for_definition
from jusik.research_worker import ResearchWorker

KST = ZoneInfo("Asia/Seoul")
MIN_AI_FORWARD_SESSIONS = 20


def ai_forward_evaluation_window(
    snapshot: ResearchInputSnapshot, cutoff: date, end_date: date
) -> tuple[date, date] | None:
    future_dates = sorted(
        {
            bar.date
            for symbol in snapshot.symbols
            for bar in symbol.bars
            if cutoff < bar.date <= end_date
        }
    )
    if len(future_dates) < MIN_AI_FORWARD_SESSIONS:
        return None
    return future_dates[0], future_dates[-1]


class ResearchAutomation:
    def __init__(
        self,
        research_store: ResearchStore,
        operations_store: OperationsStore,
        reviewer: OpenAiResearchReviewer,
    ) -> None:
        self.research_store = research_store
        self.operations_store = operations_store
        self.reviewer = reviewer
        self.worker: ResearchWorker | None = None
        self._task: asyncio.Task[None] | None = None
        self._signal_cache: dict[str, tuple[float, str, bool, date, str, str]] = {}

    def attach_worker(self, worker: ResearchWorker) -> None:
        self.worker = worker

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._schedule_loop())

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    def enqueue_scheduled(self) -> str:
        if self.worker is None:
            raise RuntimeError("Research worker is unavailable.")
        if self.worker.queue_full:
            raise RuntimeError("Research queue is full.")
        schedule = self.operations_store.schedule()
        if schedule.last_run_id is not None:
            try:
                previous = self.research_store.get(schedule.last_run_id)
            except KeyError:
                previous = None
            if previous is not None and previous.status in {
                "queued",
                "collecting",
                "running",
            }:
                raise RuntimeError("A scheduled research run is already active.")
        today = utc_now().astimezone(KST).date()
        end = today - timedelta(days=1)
        request = ResearchRunRequest(
            symbols=self.operations_store.universe(),
            start_date=end - timedelta(days=schedule.lookback_days),
            end_date=end,
        )
        identity = json.dumps(
            {
                "next_run_at": schedule.next_run_at.isoformat(),
                "request": request.model_dump(mode="json"),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        run_id = "scheduled_" + hashlib.sha256(identity).hexdigest()[:32]
        run = self.research_store.create(request, run_id=run_id, if_exists=True)
        self.worker.enqueue(run.id)
        self.operations_store.mark_schedule_started(run.id, utc_now())
        return run.id

    async def _schedule_loop(self) -> None:
        while True:
            now = utc_now()
            if self.operations_store.schedule_due(now):
                try:
                    self.enqueue_scheduled()
                except Exception:
                    self.operations_store.mark_schedule_error(
                        "정기 연구를 대기열에 등록하지 못했습니다.", now
                    )
            await asyncio.sleep(30)

    async def on_completed(self, run_id: str) -> None:
        run = self.research_store.get(run_id)
        if (
            run.result is None
            or run.result.validation is None
            or run.input_snapshot is None
        ):
            return
        validation = run.result.validation
        baseline_definition = next(
            item.definition
            for item in self.operations_store.versions()
            if item.definition.version == "trend_20_v1"
        )
        evaluated: list[tuple[str, Decimal, Decimal, bool]] = []
        for record in self.operations_store.versions():
            if (
                record.source == "openai_suggestion"
                and record.proposed_after_date is None
            ):
                self.operations_store.mark_version_pending(
                    record.definition.version,
                    "이전 형식의 AI 제안은 생성 기준일이 없어 평가할 수 없습니다.",
                )
                continue
            if (
                record.source == "openai_suggestion"
                and record.evaluation_run_id is not None
            ):
                continue
            evaluation_start = validation.testing_start
            evaluation_end = validation.testing_end
            baseline_metrics = validation.baseline
            if record.proposed_after_date is not None:
                evaluation_window = ai_forward_evaluation_window(
                    run.input_snapshot,
                    record.proposed_after_date,
                    run.request.end_date,
                )
                if evaluation_window is None:
                    observed = len(
                        {
                            bar.date
                            for symbol in run.input_snapshot.symbols
                            for bar in symbol.bars
                            if record.proposed_after_date
                            < bar.date
                            <= run.request.end_date
                        }
                    )
                    self.operations_store.mark_version_pending(
                        record.definition.version,
                        (
                            f"제안 생성 기준일 {record.proposed_after_date} 뒤의 "
                            f"새 거래일이 {observed}/{MIN_AI_FORWARD_SESSIONS}개라 "
                            "평가를 기다립니다."
                        ),
                    )
                    continue
                evaluation_start, evaluation_end = evaluation_window
                candidate_request = run.request.model_copy(
                    update={
                        "start_date": evaluation_start,
                        "end_date": evaluation_end,
                    }
                )
                baseline_result = await asyncio.to_thread(
                    run_definition_backtest,
                    candidate_request,
                    run.input_snapshot,
                    baseline_definition,
                )
                baseline_metrics = baseline_result.metrics
            else:
                candidate_request = run.request.model_copy(
                    update={
                        "start_date": evaluation_start,
                        "end_date": evaluation_end,
                    }
                )
            result = await asyncio.to_thread(
                run_definition_backtest,
                candidate_request,
                run.input_snapshot,
                record.definition,
            )
            passed = (
                result.metrics.total_return_pct >= baseline_metrics.total_return_pct
                and result.metrics.max_drawdown_pct <= baseline_metrics.max_drawdown_pct
            )
            reason = (
                "동일 초기자금의 시간순 평가 구간에서 기준 수익률 이상과 "
                "최대 낙폭 이하를 충족했습니다."
                if passed
                else (
                    "시간순 평가 구간의 기준 수익률과 최대 낙폭 조건을 "
                    "모두 충족하지 못했습니다."
                )
            )
            self.operations_store.record_version_validation(
                run_id=run_id,
                version=record.definition.version,
                return_pct=result.metrics.total_return_pct,
                drawdown_pct=result.metrics.max_drawdown_pct,
                passed=passed,
                reason=reason,
                evaluation_start=evaluation_start,
                evaluation_end=evaluation_end,
                input_hash=run.result.input_hash,
                implementation_hash=run.result.implementation_hash or "legacy_unknown",
            )
            evaluated.append(
                (
                    record.definition.version,
                    result.metrics.total_return_pct,
                    result.metrics.max_drawdown_pct,
                    passed,
                )
            )
        eligible = [item for item in evaluated if item[3]]
        if eligible:
            best = max(eligible, key=lambda item: (item[1], -item[2], item[0]))
            self.operations_store.recommend(
                best[0],
                (
                    "이번 시간순 평가 구간의 합격 전략 중 수익률이 가장 높았습니다. "
                    "paper 반영은 별도 선택이 필요합니다."
                ),
                run_id,
            )
        if (
            not self.reviewer.configured
            or self.reviewer.settings.openai_daily_token_budget <= 0
        ):
            return
        ai_request = self.reviewer.build_request(
            run_id=run_id,
            deterministic_summary=validation.model_dump_json(),
        )
        reservation = self.operations_store.reserve_ai_run(
            model=self.reviewer.settings.openai_model,
            prompt_version=PROMPT_VERSION,
            request=ai_request,
            daily_budget=self.reviewer.settings.openai_daily_token_budget,
            conservative_input_tokens=self.reviewer.conservative_input_tokens(
                ai_request
            ),
        )
        if reservation is None:
            return
        ai_request["max_output_tokens"] = reservation.max_output_tokens
        ai_result = await self.reviewer.analyze(ai_request)
        analysis = ai_result.suggestion.summary if ai_result.suggestion else None
        self.operations_store.complete_ai_run(
            reservation.id,
            input_tokens=ai_result.input_tokens,
            output_tokens=ai_result.output_tokens,
            analysis=analysis,
            error=ai_result.error,
        )
        suggestion = ai_result.suggestion
        if suggestion is None or suggestion.suggested_fast_window is None:
            return
        slow = suggestion.suggested_slow_window
        if slow is not None and slow <= suggestion.suggested_fast_window:
            return
        version = (
            f"ai_trend_{suggestion.suggested_fast_window}_"
            f"{slow or 0}_"
            f"{str(suggestion.suggested_min_volume_ratio or 0).replace('.', '_')}"
        )[:48]
        definition = StrategyDefinition(
            version=version,
            name="AI 제안 · 미검증",
            fast_window=suggestion.suggested_fast_window,
            slow_window=slow,
            min_volume_ratio=suggestion.suggested_min_volume_ratio,
            definition=suggestion.summary,
        )
        created_on_kst = utc_now().astimezone(KST).date()
        self.operations_store.save_ai_suggestion(
            definition,
            "OpenAI가 제한 범위 안에서 제안했으며 아직 백테스트하지 않았습니다.",
            proposed_after_date=max(validation.testing_end, created_on_kst),
            provenance={
                "source_run_id": run_id,
                "source_input_hash": run.result.input_hash,
                "source_implementation_hash": (
                    run.result.implementation_hash or "legacy_unknown"
                ),
                "feedback_end_date": validation.testing_end.isoformat(),
                "created_on_kst": created_on_kst.isoformat(),
                "prompt_version": PROMPT_VERSION,
                "model": self.reviewer.settings.openai_model or "unknown",
            },
        )

    def on_quote(self, quote: Quote) -> None:
        active = next(
            (
                item
                for item in self.operations_store.versions()
                if item.active_for_paper
            ),
            None,
        )
        if active is None:
            return
        definition = active.definition
        cached = self._signal_cache.get(quote.symbol)
        if (
            cached is not None
            and time.monotonic() - cached[0] < 1
            and cached[1] == definition.version
        ):
            desired = cached[2]
            signal_date = cached[3]
            source_run_id = cached[4]
            signal_input_hash = cached[5]
        else:
            runs = self.research_store.list(limit=20)
            latest = next(
                (
                    self.research_store.get(item.id)
                    for item in runs
                    if item.status == "completed"
                    and quote.symbol in item.request.symbols
                ),
                None,
            )
            if latest is None or latest.input_snapshot is None:
                return
            symbol_input = next(
                item
                for item in latest.input_snapshot.symbols
                if item.symbol == quote.symbol
            )
            completed_before = utc_now().astimezone(KST).date()
            bars = [bar for bar in symbol_input.bars if bar.date < completed_before]
            if not bars or (completed_before - bars[-1].date).days > 7:
                return
            signal_date = bars[-1].date
            desired = target_for_definition(definition, bars, len(bars) - 1)
            source_run_id = latest.id
            signal_input_hash = signal_input_fingerprint(
                definition, bars, len(bars) - 1
            )
            self._signal_cache[quote.symbol] = (
                time.monotonic(),
                definition.version,
                desired,
                signal_date,
                source_run_id,
                signal_input_hash,
            )
        account = self.operations_store.paper_account()
        held = account.positions.get(quote.symbol, 0)
        valid_side = (
            "buy"
            if desired and held <= 0
            else "sell"
            if not desired and held > 0
            else None
        )
        self.operations_store.expire_incompatible_proposals(
            symbol=quote.symbol,
            strategy_version=definition.version,
            valid_side=valid_side,
            signal_date=signal_date,
            signal_input_hash=signal_input_hash,
        )
        if desired == (held > 0):
            return
        if desired:
            price = quote.ask or quote.price
            budget = account.cash / Decimal(
                max(1, len(self.operations_store.universe()))
            )
            side = "buy"
            limit_price = price * Decimal("1.005")
            unit_cash = limit_price * (Decimal(1) + FEE_RATE)
            quantity = int((budget / unit_cash).to_integral_value(rounding=ROUND_FLOOR))
            if quantity <= 0:
                return
            reason = (
                f"{signal_date} 확정 일봉에서 {definition.name} "
                "진입 조건이 성립했습니다."
            )
        else:
            quantity = held
            side = "sell"
            price = quote.bid or quote.price
            limit_price = price * Decimal("0.995")
            reason = (
                f"{signal_date} 확정 일봉에서 {definition.name} "
                "보유 조건이 해제됐습니다."
            )
        self.operations_store.create_proposal(
            SignalProposalCreate(
                symbol=quote.symbol,
                side=side,
                quantity=quantity,
                limit_price=limit_price,
                strategy_version=definition.version,
                signal_date=signal_date,
                source_run_id=source_run_id,
                signal_input_hash=signal_input_hash,
                reason=reason,
            )
        )

    def proposal_is_current(self, proposal: SignalProposal) -> bool:
        active = next(
            (
                item
                for item in self.operations_store.versions()
                if item.active_for_paper
            ),
            None,
        )
        if active is None or active.definition.version != proposal.strategy_version:
            return False
        latest = next(
            (
                self.research_store.get(item.id)
                for item in self.research_store.list(limit=20)
                if item.status == "completed"
                and proposal.symbol in item.request.symbols
            ),
            None,
        )
        if latest is None or latest.input_snapshot is None:
            return False
        symbol_input = next(
            item
            for item in latest.input_snapshot.symbols
            if item.symbol == proposal.symbol
        )
        today = utc_now().astimezone(KST).date()
        bars = [bar for bar in symbol_input.bars if bar.date < today]
        if not bars or (today - bars[-1].date).days > 7:
            return False
        desired = target_for_definition(active.definition, bars, len(bars) - 1)
        current_input_hash = signal_input_fingerprint(
            active.definition, bars, len(bars) - 1
        )
        held = self.operations_store.paper_account().positions.get(proposal.symbol, 0)
        expected_side = (
            "buy"
            if desired and held <= 0
            else "sell"
            if not desired and held > 0
            else None
        )
        return (
            expected_side == proposal.side
            and proposal.signal_date == bars[-1].date
            and proposal.signal_input_hash == current_input_hash
        )
