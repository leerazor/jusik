from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal, localcontext
from pathlib import Path
from typing import Literal

from jusik.research_external_store import ExternalStore
from jusik.research_forward_models import (
    ForwardActionLimitations,
    ForwardCalendarExchangeStatus,
    ForwardCalendarStatus,
    ForwardConfig,
    ForwardDecision,
    ForwardIntent,
    ForwardPreview,
    ForwardSession,
    ForwardStatus,
    ForwardWorkerFailure,
)
from jusik.research_forward_store import ForwardStore
from jusik.research_history import HistoryRepository
from jusik.research_market_calendar import (
    CALENDAR_TIMEZONE,
    EXCHANGE_CALENDAR,
    MarketCalendar,
    default_market_calendar,
)
from jusik.research_portfolio_engine import forward_volatility_scale, target_weights
from jusik.research_portfolio_models import (
    PortfolioCandidate,
    PortfolioConfig,
    PortfolioInput,
)
from jusik.research_quote_models import ResearchFeedStatus, ResearchQuote
from jusik.research_universe_data import REGISTRY
from jusik.research_universe_store import UniverseInputStore

DEFAULT_FORWARD_DB = Path.home() / ".local/share/jusik/research-forward.db"
LEVERAGED = frozenset({"SOXL", "TQQQ"})
ZERO = Decimal()
ONE = Decimal(1)


def bounded_buy_quantity(
    *,
    config: ForwardConfig,
    cash: Decimal,
    equity: Decimal,
    holdings: dict[str, Decimal],
    symbol: str,
    mark_unit: Decimal,
    cash_unit: Decimal,
    intent_budget: Decimal,
    target_weight: Decimal,
) -> int:
    """Maximum integer buy keeping cost-adjusted symbol/gross/leveraged caps."""
    if min(cash, equity, mark_unit, cash_unit) <= 0:
        return 0
    loss = cash_unit - mark_unit
    limits = [cash / cash_unit, intent_budget / cash_unit]

    def affected(current: Decimal, cap: Decimal) -> None:
        numerator = cap * equity - current
        denominator = mark_unit + cap * loss
        limits.append(
            ZERO if numerator < 0 or denominator <= 0 else numerator / denominator
        )

    def unaffected(current: Decimal, cap: Decimal) -> None:
        if loss <= 0:
            return
        numerator = cap * equity - current
        limits.append(ZERO if numerator < 0 else numerator / (cap * loss))

    affected(holdings.get(symbol, ZERO), min(target_weight, config.symbol_cap))
    affected(sum(holdings.values(), ZERO), config.gross_cap)
    leveraged_value = sum(
        (value for key, value in holdings.items() if key in LEVERAGED), ZERO
    )
    if symbol in LEVERAGED:
        affected(leveraged_value, config.leveraged_cap)
    else:
        unaffected(leveraged_value, config.leveraged_cap)
    for other, value in holdings.items():
        if other != symbol:
            unaffected(value, config.symbol_cap)
    bound = min(limits)
    return max(0, int(bound.to_integral_value(rounding=ROUND_FLOOR)))


def bounded_sell_quantity(
    *,
    config: ForwardConfig,
    equity: Decimal,
    holdings: dict[str, Decimal],
    held_quantity: int,
    symbol: str,
    mark_unit: Decimal,
    net_cash_unit: Decimal,
    target_weight: Decimal,
) -> int:
    """Minimum cap-corrective sell; zero targets always liquidate the holding."""
    if held_quantity <= 0 or min(equity, mark_unit, net_cash_unit) <= 0:
        return 0
    if target_weight == 0:
        return held_quantity
    loss = mark_unit - net_cash_unit
    lower = ZERO

    def affected(current: Decimal, cap: Decimal) -> None:
        nonlocal lower
        numerator = current - cap * equity
        denominator = mark_unit - cap * loss
        if numerator > 0 and denominator > 0:
            candidate = (numerator / denominator).to_integral_value(
                rounding=ROUND_CEILING
            )
            lower = max(lower, candidate)

    affected(holdings.get(symbol, ZERO), min(target_weight, config.symbol_cap))
    affected(sum(holdings.values(), ZERO), config.gross_cap)
    if symbol in LEVERAGED:
        affected(
            sum((value for key, value in holdings.items() if key in LEVERAGED), ZERO),
            config.leveraged_cap,
        )
    return min(held_quantity, max(0, int(lower)))


def deferred_constraints_after_sell(
    *,
    config: ForwardConfig,
    equity: Decimal,
    holdings: dict[str, Decimal],
    symbol: str,
    quantity: int,
    mark_unit: Decimal,
    net_cash_unit: Decimal,
) -> list[str]:
    """Describe cap breaches that a single-market sell cannot safely repair."""
    if quantity <= 0 or equity <= 0:
        return []
    final_equity = equity - quantity * (mark_unit - net_cash_unit)
    if final_equity <= 0:
        return ["equity"]
    post = dict(holdings)
    post[symbol] = max(ZERO, post.get(symbol, ZERO) - quantity * mark_unit)
    deferred = [
        f"symbol:{key}"
        for key, value in sorted(post.items())
        if key != symbol and value > config.symbol_cap * final_equity
    ]
    if sum(post.values(), ZERO) > config.gross_cap * final_equity:
        deferred.append("gross")
    leveraged = sum((value for key, value in post.items() if key in LEVERAGED), ZERO)
    if leveraged > config.leveraged_cap * final_equity:
        deferred.append("leveraged")
    return deferred


def should_skip_low_turnover(
    *,
    config: ForwardConfig,
    holdings: dict[str, Decimal],
    equity: Decimal,
    symbol: str,
    current_weight: Decimal,
    target_weight: Decimal,
) -> bool:
    """Apply the band only when it would not defer a required cap reduction."""
    if (
        target_weight <= 0
        or abs(current_weight - target_weight) >= config.low_turnover_band
    ):
        return False
    cap_reduction = target_weight < current_weight and (
        holdings.get(symbol, ZERO) > config.symbol_cap * equity
        or sum(holdings.values(), ZERO) > config.gross_cap * equity
        or (
            symbol in LEVERAGED
            and sum(
                (value for key, value in holdings.items() if key in LEVERAGED), ZERO
            )
            > config.leveraged_cap * equity
        )
    )
    return not cap_reduction


def first_due_at(activated_at: datetime) -> datetime:
    if activated_at.tzinfo is None:
        raise ValueError("activated_at must include a timezone.")
    current = activated_at.astimezone(UTC).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    days = (7 - current.weekday()) % 7
    result = current + timedelta(days=days)
    if result <= activated_at.astimezone(UTC):
        result += timedelta(days=7)
    return result


def regular_session(
    quote: ResearchQuote, calendar: MarketCalendar | None = None
) -> bool:
    schedule = calendar or default_market_calendar()
    calendar_name = EXCHANGE_CALENDAR.get(quote.exchange)
    if calendar_name is None:
        return False
    local_date = quote.market_at.astimezone(CALENDAR_TIMEZONE[calendar_name]).date()
    lookup = schedule.lookup(quote.exchange, local_date)
    if lookup.session is None:
        return False
    market_at = quote.market_at.astimezone(UTC)
    return lookup.session.open_at <= market_at <= lookup.session.close_at


def quote_is_eligible(
    quote: ResearchQuote,
    decision: ForwardDecision,
    now: datetime,
    calendar: MarketCalendar | None = None,
) -> bool:
    if now.tzinfo is None:
        raise ValueError("now must include a timezone.")
    current = now.astimezone(UTC)
    market = quote.market_at.astimezone(UTC)
    received = quote.received_at.astimezone(UTC)
    recorded = decision.recorded_at.astimezone(UTC)
    return (
        regular_session(quote, calendar)
        and market >= recorded
        and received >= recorded
        and market <= current + timedelta(seconds=2)
        and received <= current + timedelta(seconds=2)
        and current - market <= timedelta(seconds=15)
        and current - received <= timedelta(seconds=15)
        and (
            decision.expires_at is None
            or current <= decision.expires_at.astimezone(UTC)
        )
    )


class ForwardCoordinator:
    """Fixed-policy PAPER observer. This class has no brokerage execution dependency."""

    def __init__(
        self,
        store: ForwardStore,
        universe_store: UniverseInputStore,
        external_store: ExternalStore,
        feed_status: Callable[[], ResearchFeedStatus],
        *,
        source_run_id: str = (
            "fa0907ecfe86b19836881e5a78a874925fc611978ffe31064eacc82a0a46f687"
        ),
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        history: HistoryRepository | None = None,
        market_calendar: MarketCalendar | None = None,
    ) -> None:
        self.store = store
        self.universe_store = universe_store
        self.external_store = external_store
        self._feed_status = feed_status
        self._now = now
        self._source_run_id = source_run_id
        self._history = history
        self._calendar = market_calendar or default_market_calendar()
        self._task: asyncio.Task[None] | None = None
        self._last_feed_state: str | None = None
        self._last_feed_items: dict[str, str] = {}
        self._worker_failures: dict[str, ForwardWorkerFailure] = {}

    def ensure_session(self) -> ForwardSession:
        existing = self.store.active_session()
        if existing:
            return existing
        activated = self._now().astimezone(UTC)
        session = self.store.activate(
            activated_at=activated,
            next_due_at=first_due_at(activated),
            source_run_id=self._source_run_id,
            config=ForwardConfig(),
        )
        if self._history is not None:
            self._history.record(
                identity=f"forward-session-{session.id}",
                title="전진 PAPER 관찰 세션 활성화",
                summary="과거 보유 없이 1억원 현금의 별도 PAPER 원장을 시작했습니다.",
                category="forward",
                outcome="activated",
                occurred_at=session.activated_at,
                run_ids=[session.source_run_id],
            )
        return session

    def enabled(self) -> bool:
        return self.store.active_session() is not None

    def start(self) -> None:
        self.ensure_session()
        if self._task is None:
            self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        await asyncio.gather(self._task, return_exceptions=True)
        self._task = None

    async def _loop(self) -> None:
        while True:
            try:
                await asyncio.to_thread(self.tick)
            except Exception:
                # Durable blockers are recorded inside tick; the observer remains alive.
                pass
            await asyncio.sleep(5)

    def on_quote(self, quote: ResearchQuote) -> None:
        try:
            self._on_quote(quote)
        except Exception:
            self._record_worker_failure("quote", quote.received_at)
        else:
            self._worker_failures.pop("quote", None)

    def _on_quote(self, quote: ResearchQuote) -> None:
        session = self.ensure_session()
        current = self._now().astimezone(UTC)
        if not self._process_registered_actions(session, current):
            return
        if not self.store.quote_is_post_split(
            session.id, quote.symbol, quote.market_at
        ):
            return
        observation = self.store.save_observation(session.id, quote)
        self._maybe_intraday_alert(session, quote)
        now = current
        for decision in self.store.pending_decisions(session.id):
            intent = next(
                (
                    item
                    for item in decision.intents
                    if item.symbol == quote.symbol and item.state == "pending"
                ),
                None,
            )
            if intent is None:
                continue
            if not quote_is_eligible(quote, decision, now, self._calendar):
                self._record_quote_calendar_block(session, quote)
                continue
            if intent.side == "buy" and any(
                item.side == "sell" and item.state == "pending"
                for item in decision.intents
            ):
                continue
            self._paper_fill(session, decision, intent, quote, observation.id)

    def tick(self, now: datetime | None = None) -> None:
        current = (now or self._now()).astimezone(UTC)
        try:
            self._tick(current)
        except Exception:
            self._record_worker_failure("tick", current)
        else:
            self._worker_failures.pop("tick", None)

    def _tick(self, current: datetime) -> None:
        session = self.ensure_session()
        if not self._process_registered_actions(session, current):
            return
        feed = self._feed_status()
        if feed.state != self._last_feed_state:
            self.store.record_event(
                session.id,
                current,
                "feed_state_changed",
                f"연구 시세 상태: {feed.state}",
                f"{current.isoformat()}:{feed.state}",
            )
            self._last_feed_state = feed.state
            if self._history is not None:
                self._history.record(
                    identity=f"forward-feed-{session.id}-{current.isoformat()}",
                    title="전진 관찰 시세 상태 변경",
                    summary=(
                        "단일 KIS 읽기 전용 스트림 상태가 "
                        f"{feed.state}(으)로 변경되었습니다."
                    ),
                    category="forward",
                    outcome=feed.state,
                    occurred_at=current,
                )
        if self._history is not None:
            for item in feed.items:
                signature = f"{item.state}:{item.subscription_phase}:{item.ack_overdue}"
                if self._last_feed_items.get(item.symbol) == signature:
                    continue
                self._history.record(
                    identity=(
                        f"forward-feed-{session.id}-{item.symbol}-{current.isoformat()}"
                    ),
                    title=f"{item.symbol} 연구 시세 상태 변경",
                    summary=(
                        "읽기 전용 구독 상태가 "
                        f"{item.subscription_phase}/{item.state}"
                        f"(으)로 변경되었습니다"
                        + ("(ACK 확인 지연)." if item.ack_overdue else ".")
                    ),
                    category="forward",
                    outcome=item.state,
                    occurred_at=current,
                )
                self._last_feed_items[item.symbol] = signature
        self._maybe_daily_checkpoints(session, current)
        self._expire_intents(session, current)
        session = self.ensure_session()
        if session.liquidation_completed_at is not None:
            if not self._recovery_step(session, current):
                return
            session = self.ensure_session()
        if current < session.next_due_at:
            return
        delay = current - session.next_due_at
        due = session.next_due_at
        next_due = due + timedelta(days=session.config.cadence_days)
        if delay > timedelta(minutes=session.config.restart_catchup_minutes):
            self.store.record_event(
                session.id,
                current,
                "missed_restart",
                "재시작 허용 15분을 지나 과거 결정을 만들지 않았습니다.",
                due.isoformat(),
            )
            self.store.advance_due(session.id, next_due, "waiting_cadence")
            return
        try:
            source = self._load_input(due)
        except ValueError:
            self.store.record_event(
                session.id,
                current,
                "missed_data",
                "마감시각 이전 입력이 완전하지 않아 결정을 만들지 않았습니다.",
                due.isoformat(),
            )
            self.store.advance_due(session.id, next_due, "inputs_blocked")
            return
        held_symbols = {
            item.symbol
            for item in self.store.positions(session.id)
            if item.quantity > 0
        }
        action = self._unresolved_corporate_action(session, source, held_symbols, due)
        if action is not None:
            self.store.record_event(
                session.id,
                current,
                "corporate_action_blocked",
                "보유 중 발생한 분할을 원장에 안전하게 반영하기 전까지 "
                f"정기 결정을 차단했습니다: {action}",
                f"action:{action}",
            )
            self.store.advance_due(session.id, next_due, "inputs_blocked")
            return
        payload = source.model_dump(mode="json")
        input_version = self.store.save_input_version(session.id, due, payload)
        weights, blocked, proxy, scale = self._targets(source, due, session.config)
        try:
            intents = self._intents(session, weights)
        except ValueError:
            self.store.record_event(
                session.id,
                current,
                "missed_data",
                "보유 종목의 동시 평가 시세 또는 FX가 없어 결정을 만들지 않았습니다.",
                due.isoformat(),
            )
            self.store.advance_due(session.id, next_due, "inputs_blocked")
            return
        decision = self.store.record_decision(
            session_id=session.id,
            due_at=due,
            recorded_at=current,
            input_version=input_version,
            reason=blocked or "fixed low_turnover_combined scheduled decision",
            expires_at=current
            + timedelta(days=session.config.normal_intent_expiry_days),
            target_weights=weights,
            intents=intents,
            volatility_proxy=proxy,
            volatility_scale=scale,
        )
        if session.recovery_confirmations >= session.config.recovery_confirmations:
            self.store.begin_reentry_episode(session.id, session.cash_krw)
        self.store.advance_due(
            session.id,
            next_due,
            "awaiting_quotes" if intents else "waiting_cadence",
        )
        if self._history is not None:
            self._history.record(
                identity=f"forward-decision-{decision.id}",
                title="전진 PAPER 정기 결정 기록",
                summary="고정 정책과 마감 이전 입력으로 가상 체결 지시를 기록했습니다.",
                category="forward",
                outcome=decision.state,
                occurred_at=decision.recorded_at,
                run_ids=[session.source_run_id],
            )

    def _recovery_step(self, session: ForwardSession, current: datetime) -> bool:
        if session.recovery_confirmations >= session.config.recovery_confirmations:
            return True
        next_check = session.next_recovery_check_at
        if next_check is None or current < next_check:
            return False
        try:
            source = self._load_input(next_check)
            weights, blocked, _proxy, _scale = self._targets(
                source, next_check, session.config
            )
        except ValueError:
            weights, blocked = {}, "recovery input missing"
        passed = (
            blocked is None
            and len([value for value in weights.values() if value > 0]) >= 2
        )
        confirmations = session.recovery_confirmations + 1 if passed else 0
        following = next_check + timedelta(days=7)
        state = (
            "reentry_ready"
            if confirmations >= session.config.recovery_confirmations
            else "recovery_wait"
        )
        self.store.set_recovery(
            session.id,
            confirmations=confirmations,
            next_check_at=None if state == "reentry_ready" else following,
            state=state,
        )
        if state == "reentry_ready":
            next_due = session.next_due_at
            while next_due <= current:
                next_due += timedelta(days=session.config.cadence_days)
            self.store.advance_due(session.id, next_due, state)
        self.store.record_event(
            session.id,
            current,
            "recovery_confirmation",
            (
                "주간 회복 확인 "
                f"{confirmations}/{session.config.recovery_confirmations}"
                if passed
                else "주간 회복 조건 미충족으로 연속 확인을 0으로 초기화했습니다."
            ),
            next_check.isoformat(),
        )
        return state == "reentry_ready"

    def preview(self, asof: datetime | None = None) -> ForwardPreview:
        current = (asof or self._now()).astimezone(UTC)
        try:
            source = self._load_input(current)
            weights, blocked, _proxy, _scale = self._targets(
                source, current, self.ensure_session().config
            )
            payload = source.model_dump(mode="json")
            version = hashlib.sha256(
                json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
        except ValueError as exc:
            weights, blocked, version = {}, str(exc), None
        return ForwardPreview(
            computed_at=self._now().astimezone(UTC),
            asof=current,
            target_weights=weights,
            blocked_reason=blocked,
            input_version=version,
        )

    def status(self) -> ForwardStatus:
        session = self.ensure_session()
        decisions = self.store.decisions(session.id, 1)
        preview = self.preview()
        calendar_status = self._calendar_status()
        corporate_actions = self.store.corporate_actions(session.id, self._now())
        corporate_action_block = next(
            (
                "검증된 분할의 원장 적용이 차단되었습니다: "
                f"{action.symbol}:{action.blocked_reason}"
                for action in corporate_actions
                if action.state == "blocked"
            ),
            None,
        )
        calendar_block = (
            "고정 거래소 달력을 확인할 수 없어 관련 평가와 가상 체결을 차단합니다."
            if not calendar_status.available
            or any(item.phase == "unavailable" for item in calendar_status.exchanges)
            else None
        )
        return ForwardStatus(
            session=session,
            feed=self._feed_status(),
            preview=preview,
            latest_decision=decisions[0] if decisions else None,
            blocked_reason=(
                preview.blocked_reason
                or calendar_block
                or corporate_action_block
                or (
                    "전진 관찰 워커 내부 오류가 기록되었습니다."
                    if self._worker_failures
                    else None
                )
            ),
            worker_failures=list(self._worker_failures.values()),
            calendar=calendar_status,
            action_limitations=ForwardActionLimitations(),
            corporate_actions=corporate_actions,
        )

    def _process_registered_actions(
        self, session: ForwardSession, current: datetime
    ) -> bool:
        actions = self.store.apply_due_corporate_actions(session.id, current)
        blocked = [
            action
            for action in actions
            if action.effective_at <= current and action.state == "blocked"
        ]
        if not blocked:
            return True
        action = blocked[0]
        self.store.record_event(
            session.id,
            current,
            "corporate_action_blocked",
            "검증된 분할을 원장에 적용할 수 없어 PAPER 처리를 차단했습니다: "
            f"{action.symbol}:{action.blocked_reason}",
            f"registered:{action.id}:{action.blocked_reason}",
        )
        return False

    def _calendar_status(self) -> ForwardCalendarStatus:
        current = self._now().astimezone(UTC)
        exchanges: list[ForwardCalendarExchangeStatus] = []
        for exchange in ("KRX", "NYS"):
            clock = self._calendar.clock(exchange, current)
            exchanges.append(
                ForwardCalendarExchangeStatus(
                    calendar=clock.calendar,
                    phase=clock.phase,
                    local_date=clock.local_date,
                    open_at=clock.open_at,
                    close_at=clock.close_at,
                    next_session_open_at=(
                        clock.next_session.open_at if clock.next_session else None
                    ),
                    next_session_close_at=(
                        clock.next_session.close_at if clock.next_session else None
                    ),
                )
            )
        return ForwardCalendarStatus(
            available=self._calendar.available,
            provider_version=self._calendar.provider_version,
            artifact_sha256=self._calendar.artifact_sha256,
            calendars_sha256=self._calendar.calendars_sha256,
            generated_at=self._calendar.generated_at,
            coverage_start=self._calendar.coverage_start,
            coverage_end=self._calendar.coverage_end,
            error_code=self._calendar.error,
            exchanges=exchanges,
        )

    def _record_quote_calendar_block(
        self, session: ForwardSession, quote: ResearchQuote
    ) -> None:
        calendar_name = EXCHANGE_CALENDAR.get(quote.exchange)
        if calendar_name is None:
            self._record_calendar_problem(
                session,
                quote.received_at,
                quote.exchange,
                quote.market_at.date(),
                "exchange_not_mapped",
                "가상 체결",
            )
            return
        local_date = quote.market_at.astimezone(CALENDAR_TIMEZONE[calendar_name]).date()
        lookup = self._calendar.lookup(quote.exchange, local_date)
        if lookup.state == "unavailable":
            self._record_calendar_problem(
                session,
                quote.received_at,
                quote.exchange,
                local_date,
                lookup.reason or "calendar_date_unavailable",
                "가상 체결",
            )

    def _record_calendar_problem(
        self,
        session: ForwardSession,
        occurred_at: datetime,
        exchange: str,
        local_date: date,
        reason: str,
        context: str,
    ) -> None:
        calendar_name = EXCHANGE_CALENDAR.get(exchange, exchange)
        reference = f"calendar:{context}:{calendar_name}:{local_date}:{reason}"
        self.store.record_event(
            session.id,
            occurred_at,
            "calendar_unavailable",
            f"{context}에 필요한 {calendar_name} {local_date} 거래 일정을 "
            f"확인할 수 없어 차단했습니다: {reason}",
            reference,
        )

    def _record_worker_failure(
        self, channel: Literal["tick", "quote"], occurred_at: datetime
    ) -> None:
        failure = ForwardWorkerFailure(
            channel=channel,
            occurred_at=occurred_at.astimezone(UTC),
        )
        self._worker_failures[channel] = failure
        try:
            session = self.store.active_session()
            if session is not None:
                self.store.record_event(
                    session.id,
                    failure.occurred_at,
                    "worker_failure",
                    f"{channel} 워커 내부 오류가 발생했습니다. "
                    "비밀값은 기록하지 않았습니다.",
                    f"{channel}:{failure.occurred_at.isoformat()}",
                )
        except Exception:
            pass

    def _load_input(self, cutoff: datetime) -> PortfolioInput:
        ids: dict[str, str] = {}
        snapshots = []
        for instrument in REGISTRY:
            loaded = self.universe_store.load_asof(instrument.symbol, cutoff)
            if loaded is None:
                raise ValueError(f"{instrument.symbol} cutoff snapshot missing")
            identity, _request, snapshot = loaded
            ids[instrument.symbol] = identity
            snapshots.append(snapshot)
        return PortfolioInput(
            captured_at=max(item.captured_at for item in snapshots),
            stock_snapshot_ids=ids,
            instruments=snapshots,
            external=self.external_store.snapshot_asof(cutoff),
            external_status=[],
        )

    @staticmethod
    def _targets(
        source: PortfolioInput, at: datetime, config: ForwardConfig
    ) -> tuple[dict[str, Decimal], str | None, Decimal | None, Decimal | None]:
        portfolio_config = PortfolioConfig(
            initial_cash_krw=config.initial_cash_krw,
            fee_rate=config.fee_rate,
            slippage_rate=config.slippage_rate,
            fx_spread_rate=config.fx_spread_rate,
            symbol_cap=config.symbol_cap,
            gross_cap=config.gross_cap,
            leveraged_etf_cap=config.leveraged_cap,
            drawdown_limit=config.drawdown_limit,
        )
        candidate = PortfolioCandidate(
            id=config.candidate_id, method=config.method, gate=config.gate
        )
        weights, _diagnostics, blocked = target_weights(
            source, candidate, at, portfolio_config
        )
        if blocked or not weights:
            return weights, blocked, None, None
        scale, proxy = forward_volatility_scale(source, weights, at, portfolio_config)
        if scale is None:
            return {}, "60-return KRW volatility input missing", proxy, scale
        return (
            {symbol: weight * scale for symbol, weight in weights.items()},
            None,
            proxy,
            scale,
        )

    def _intents(
        self, session: ForwardSession, weights: dict[str, Decimal]
    ) -> list[ForwardIntent]:
        positions = {item.symbol: item for item in self.store.positions(session.id)}
        latest = self.store.latest_quotes(session.id)
        current_values: dict[str, Decimal] = {}
        for symbol, position in positions.items():
            observation = latest.get(symbol)
            if observation is None or not self.store.quote_is_post_split(
                session.id, symbol, observation.quote.market_at
            ):
                raise ValueError("Held position valuation quote missing.")
            fx = self._fx_rate(
                observation.quote.received_at, observation.quote.currency
            )
            if fx is None:
                raise ValueError("Held position FX proxy missing.")
            current_values[symbol] = position.quantity * observation.quote.price * fx
        nav = session.cash_krw + sum(current_values.values(), ZERO)
        if nav <= 0:
            return []
        intents: list[ForwardIntent] = []
        for symbol in sorted(set(weights) | set(positions)):
            target_weight = min(weights.get(symbol, ZERO), session.config.symbol_cap)
            current_weight = current_values.get(symbol, ZERO) / nav
            if should_skip_low_turnover(
                config=session.config,
                holdings=current_values,
                equity=nav,
                symbol=symbol,
                current_weight=current_weight,
                target_weight=target_weight,
            ):
                continue
            side = "buy" if target_weight > current_weight else "sell"
            budget = abs(target_weight - current_weight) * nav
            if budget <= 0:
                continue
            intents.append(
                ForwardIntent(
                    symbol=symbol,
                    side=side,
                    target_weight=target_weight,
                    budget_krw=budget,
                    state="pending",
                    reason=(
                        "fixed target direction computed before any same-decision fill"
                    ),
                )
            )
        return intents

    def _paper_fill(
        self,
        session: ForwardSession,
        decision: ForwardDecision,
        intent: ForwardIntent,
        quote: ResearchQuote,
        quote_id: str,
    ) -> None:
        fx = self._fx_rate(quote.received_at, quote.currency)
        if fx is None:
            self.store.record_event(
                session.id,
                quote.received_at,
                "missed_data",
                "USD/KRW 대용치가 없거나 7일을 초과해 가상 체결을 차단했습니다.",
                f"fx:{intent.symbol}:{quote.received_at.date().isoformat()}",
            )
            return
        current_session = self.store.active_session()
        if current_session is None or current_session.id != session.id:
            return
        session = current_session
        config = session.config
        positions = {item.symbol: item for item in self.store.positions(session.id)}
        held_symbols = {
            symbol for symbol, position in positions.items() if position.quantity > 0
        }
        if held_symbols:
            try:
                action_source = self._load_input(quote.received_at)
            except ValueError:
                self.store.record_event(
                    session.id,
                    quote.received_at,
                    "missed_data",
                    "보유 종목의 분할 여부를 확인할 입력이 없어 가상 체결을 "
                    "차단했습니다.",
                    f"action-input:{intent.symbol}:{quote.received_at.date()}",
                )
                return
            action = self._unresolved_corporate_action(
                session, action_source, held_symbols, quote.received_at
            )
            if action is not None:
                self.store.record_event(
                    session.id,
                    quote.received_at,
                    "corporate_action_blocked",
                    "보유 중 발생한 분할을 원장에 안전하게 반영하기 전까지 "
                    f"가상 체결을 차단했습니다: {action}",
                    f"action:{action}",
                )
                return
        latest = self.store.latest_quotes(session.id)
        holdings: dict[str, Decimal] = {}
        for symbol, position in positions.items():
            observed = latest.get(symbol)
            if observed is None or not self.store.quote_is_post_split(
                session.id, symbol, observed.quote.market_at
            ):
                return
            position_fx = self._fx_rate(quote.received_at, observed.quote.currency)
            if position_fx is None:
                return
            holdings[symbol] = position.quantity * observed.quote.price * position_fx
        equity = session.cash_krw + sum(holdings.values(), ZERO)
        with localcontext() as context:
            context.prec = 40
            if intent.side == "buy":
                fill_price = (quote.ask or quote.price) * (ONE + config.slippage_rate)
            else:
                fill_price = (quote.bid or quote.price) * (ONE - config.slippage_rate)
            unit_notional = fill_price * fx
            unit_fee = unit_notional * config.fee_rate
            unit_fx = (
                fill_price
                * fx
                * (config.fx_spread_rate if quote.currency == "USD" else ZERO)
            )
            unit_cash = unit_notional + unit_fee + unit_fx
            if intent.side == "buy":
                quantity = bounded_buy_quantity(
                    config=config,
                    cash=session.cash_krw,
                    equity=equity,
                    holdings=holdings,
                    symbol=intent.symbol,
                    mark_unit=quote.price * fx,
                    cash_unit=unit_cash,
                    intent_budget=intent.budget_krw,
                    target_weight=intent.target_weight,
                )
            else:
                target_position = positions.get(intent.symbol)
                if target_position is None:
                    self.store.consume_intent(
                        decision, intent.symbol, "보유 수량이 없어 지시를 소비했습니다."
                    )
                    return
                quantity = bounded_sell_quantity(
                    config=config,
                    equity=equity,
                    holdings=holdings,
                    held_quantity=target_position.quantity,
                    symbol=intent.symbol,
                    mark_unit=quote.price * fx,
                    net_cash_unit=unit_notional - unit_fee - unit_fx,
                    target_weight=intent.target_weight,
                )
            if quantity <= 0:
                self.store.consume_intent(
                    decision, intent.symbol, "정수 수량이 0이라 지시를 소비했습니다."
                )
                return
            notional = unit_notional * quantity
            fee = notional * config.fee_rate
            fx_cost = (
                fill_price
                * fx
                * quantity
                * (config.fx_spread_rate if quote.currency == "USD" else ZERO)
            )
        self.store.save_observation(session.id, quote, "fill")
        fill = self.store.apply_fill(
            decision=decision,
            intent=intent,
            quote=quote,
            quote_id=quote_id,
            fx_rate=fx,
            quantity=quantity,
            local_fill_price=fill_price,
            transaction_cost_krw=fee,
            fx_cost_krw=fx_cost,
        )
        if fill is not None and intent.side == "sell":
            deferred = deferred_constraints_after_sell(
                config=config,
                equity=equity,
                holdings=holdings,
                symbol=intent.symbol,
                quantity=quantity,
                mark_unit=quote.price * fx,
                net_cash_unit=unit_notional - unit_fee - unit_fx,
            )
            if deferred:
                self.store.record_event(
                    session.id,
                    fill.received_at,
                    "cap_constraint_deferred",
                    "매도 비용과 비동시 시장 때문에 다른 보유의 한도 초과를 "
                    "즉시 복구할 수 없습니다: " + ", ".join(deferred),
                    fill.id,
                )
        if fill is not None and self._history is not None:
            self._history.record(
                identity=f"forward-fill-{fill.id}",
                title="전진 PAPER 가상 체결 기록",
                summary=(
                    f"{fill.symbol} {fill.side} {fill.quantity}주를 "
                    "시세 기반 가정으로 기록했습니다."
                ),
                category="forward",
                outcome="paper_fill",
                occurred_at=fill.received_at,
                run_ids=[session.source_run_id],
            )
        if (
            fill is not None
            and intent.side == "sell"
            and decision.expires_at is None
            and all(
                position.quantity == 0 for position in self.store.positions(session.id)
            )
        ):
            self.store.complete_liquidation(session.id, fill.received_at)

    def _maybe_daily_checkpoints(
        self, session: ForwardSession, actually_known_at: datetime
    ) -> None:
        if not self._calendar.available:
            self._record_calendar_problem(
                session,
                actually_known_at,
                "KRX",
                actually_known_at.date(),
                self._calendar.error or "calendar_file_unavailable",
                "종가 checkpoint",
            )
            return
        try:
            source = self._load_input(actually_known_at)
        except ValueError:
            return
        instruments = {
            item.instruments[0].instrument.symbol: item for item in source.instruments
        }
        checkpoint_values: set[datetime] = set()
        for snapshot in source.instruments:
            instrument = snapshot.instruments[0].instrument
            calendar_name = EXCHANGE_CALENDAR.get(instrument.exchange)
            if calendar_name is None:
                self._record_calendar_problem(
                    session,
                    actually_known_at,
                    instrument.exchange,
                    actually_known_at.date(),
                    "exchange_not_mapped",
                    "종가 checkpoint",
                )
                continue
            zone = CALENDAR_TIMEZONE[calendar_name]
            activated_date = session.activated_at.astimezone(zone).date()
            known_date = actually_known_at.astimezone(zone).date()
            for bar in snapshot.instruments[0].bars:
                if bar.date < activated_date or bar.date > known_date:
                    continue
                lookup = self._calendar.lookup(instrument.exchange, bar.date)
                if lookup.session is None:
                    reason = (
                        lookup.reason
                        if lookup.state == "unavailable"
                        else "daily_bar_on_closed_date"
                    )
                    self._record_calendar_problem(
                        session,
                        actually_known_at,
                        instrument.exchange,
                        bar.date,
                        reason or "calendar_date_unavailable",
                        "종가 checkpoint",
                    )
                    continue
                close_at = lookup.session.close_at
                if session.activated_at < close_at < actually_known_at:
                    checkpoint_values.add(close_at)
        checkpoints = sorted(checkpoint_values)
        for checkpoint_at in checkpoints:
            replayed = self.store.ledger_asof(session.id, checkpoint_at)
            if replayed is None:
                self.store.record_event(
                    session.id,
                    actually_known_at,
                    "corporate_action_blocked",
                    "분할 metadata가 완전하지 않아 종가 원장 재생을 차단했습니다.",
                    checkpoint_at.isoformat(),
                )
                return
            cash, quantities = replayed
            action = self._unresolved_corporate_action(
                session,
                source,
                {symbol for symbol, quantity in quantities.items() if quantity > 0},
                checkpoint_at,
            )
            if action is not None:
                self.store.record_event(
                    session.id,
                    actually_known_at,
                    "corporate_action_blocked",
                    "보유 중 발생한 분할을 원장에 안전하게 반영하기 전까지 "
                    f"종가 평가를 차단했습니다: {action}",
                    f"action:{action}",
                )
                continue
            values: dict[str, Decimal] = {}
            valuation_blocked = False
            for symbol, quantity in quantities.items():
                if quantity == 0:
                    continue
                held_snapshot = instruments.get(symbol)
                if held_snapshot is None:
                    valuation_blocked = True
                    break
                instrument = held_snapshot.instruments[0].instrument
                calendar_name = EXCHANGE_CALENDAR.get(instrument.exchange)
                if calendar_name is None:
                    valuation_blocked = True
                    self._record_calendar_problem(
                        session,
                        actually_known_at,
                        instrument.exchange,
                        checkpoint_at.date(),
                        "exchange_not_mapped",
                        "보유 종가 평가",
                    )
                    break
                completed = self._calendar.latest_completed_session(
                    instrument.exchange, checkpoint_at
                )
                if completed is None:
                    valuation_blocked = True
                    self._record_calendar_problem(
                        session,
                        actually_known_at,
                        instrument.exchange,
                        checkpoint_at.astimezone(
                            CALENDAR_TIMEZONE[calendar_name]
                        ).date(),
                        "latest_completed_session_unavailable",
                        "보유 종가 평가",
                    )
                    break
                known = None
                activation_local_date = session.activated_at.astimezone(
                    CALENDAR_TIMEZONE[calendar_name]
                ).date()
                for bar in held_snapshot.instruments[0].bars:
                    if bar.date < activation_local_date:
                        continue
                    if bar.date > completed.local_date:
                        break
                    lookup = self._calendar.lookup(instrument.exchange, bar.date)
                    if lookup.session is None:
                        valuation_blocked = True
                        reason = (
                            lookup.reason
                            if lookup.state == "unavailable"
                            else "daily_bar_on_closed_date"
                        )
                        self._record_calendar_problem(
                            session,
                            actually_known_at,
                            instrument.exchange,
                            bar.date,
                            reason or "calendar_date_unavailable",
                            "보유 종가 평가",
                        )
                        break
                    if bar.date == completed.local_date:
                        known = bar
                if valuation_blocked or known is None:
                    valuation_blocked = True
                    break
                fx = self._fx_rate(checkpoint_at, instrument.currency)
                if fx is None:
                    valuation_blocked = True
                    break
                values[symbol] = quantity * known.close * fx
            if valuation_blocked or (
                any(quantity > 0 for quantity in quantities.values()) and not values
            ):
                self.store.record_event(
                    session.id,
                    actually_known_at,
                    "missed_data",
                    "확정 종가 또는 당시 이용 가능했던 FX가 없어 "
                    "checkpoint를 차단했습니다.",
                    checkpoint_at.isoformat(),
                )
                continue
            equity = cash + sum(values.values(), ZERO)
            inserted = self.store.record_checkpoint(
                session.id,
                checkpoint_at,
                actually_known_at,
                equity,
                cash,
                values,
                update_episode=session.liquidation_completed_at is None,
            )
            evaluated_reference = f"checkpoint:{checkpoint_at.isoformat()}"
            if not inserted and self.store.event_exists(
                session.id, "close_checkpoint", evaluated_reference
            ):
                continue
            current = self.store.active_session()
            if current is None or not values:
                self.store.record_event(
                    session.id,
                    actually_known_at,
                    "close_checkpoint",
                    "확정 종가와 당시 PAPER 원장을 평가했습니다.",
                    evaluated_reference,
                )
                continue
            drawdown = ONE - equity / current.episode_high_water_krw
            if drawdown < current.config.drawdown_limit:
                self.store.record_event(
                    session.id,
                    actually_known_at,
                    "close_checkpoint",
                    "확정 종가와 당시 PAPER 원장을 평가했습니다.",
                    evaluated_reference,
                )
                continue
            if any(
                decision.expires_at is None
                for decision in self.store.pending_decisions(session.id)
            ):
                self.store.record_event(
                    session.id,
                    actually_known_at,
                    "close_checkpoint",
                    "기존 종가 위험 청산 지시가 있어 중복 생성을 막았습니다.",
                    evaluated_reference,
                )
                continue
            current_positions = [
                position
                for position in self.store.positions(session.id)
                if position.quantity > 0
            ]
            if not current_positions:
                self.store.record_event(
                    session.id,
                    actually_known_at,
                    "close_checkpoint",
                    "현재 보유가 없어 과거 원장으로 주문을 소급 생성하지 않았습니다.",
                    evaluated_reference,
                )
                continue
            payload: dict[str, object] = {
                "checkpoint_at": checkpoint_at.isoformat(),
                "actually_known_at": actually_known_at.isoformat(),
                "equity_krw": str(equity),
                "positions_asof": {key: str(value) for key, value in values.items()},
                "stock_snapshot_ids": source.stock_snapshot_ids,
            }
            version = self.store.save_input_version(
                session.id, actually_known_at, payload
            )
            self.store.block_pending_buys(session.id)
            intents = [
                ForwardIntent(
                    symbol=position.symbol,
                    side="sell",
                    target_weight=ZERO,
                    budget_krw=values.get(position.symbol, ZERO),
                    state="pending",
                    reason="confirmed daily-close drawdown liquidation",
                )
                for position in current_positions
            ]
            decision = self.store.record_decision(
                session_id=session.id,
                due_at=checkpoint_at,
                recorded_at=actually_known_at,
                input_version=version,
                reason="confirmed close episode drawdown risk liquidation",
                expires_at=None,
                target_weights={},
                intents=intents,
            )
            self.store.set_state(session.id, "risk_liquidation")
            self.store.record_event(
                session.id,
                actually_known_at,
                "risk_exit",
                "새로 확인한 확정 일봉과 당시 원장으로 10% 낙폭을 확인했습니다.",
                decision.id,
            )
            self.store.record_event(
                session.id,
                actually_known_at,
                "close_checkpoint",
                "확정 종가 위험 평가와 가상 청산 결정을 연결했습니다.",
                evaluated_reference,
            )

    def _maybe_intraday_alert(
        self, session: ForwardSession, quote: ResearchQuote
    ) -> None:
        positions = {item.symbol: item for item in self.store.positions(session.id)}
        if not any(item.quantity > 0 for item in positions.values()):
            return
        latest = self.store.latest_quotes(session.id)
        values: dict[str, Decimal] = {}
        for symbol, position in positions.items():
            if position.quantity == 0:
                continue
            observed = latest.get(symbol)
            if observed is None or not self.store.quote_is_post_split(
                session.id, symbol, observed.quote.market_at
            ):
                return
            fx = self._fx_rate(quote.received_at, observed.quote.currency)
            if fx is None:
                return
            values[symbol] = position.quantity * observed.quote.price * fx
        equity = session.cash_krw + sum(values.values(), ZERO)
        if (
            ONE - equity / session.lifetime_high_water_krw
            < session.config.drawdown_limit
        ):
            return
        minute = quote.received_at.astimezone(UTC).replace(second=0, microsecond=0)
        self.store.save_observation(session.id, quote, "alert")
        self.store.record_event(
            session.id,
            quote.received_at,
            "risk_alert",
            "장중 원장 추정 낙폭 경보입니다. 자동 종가 청산 판단을 대신하지 않습니다.",
            minute.isoformat(),
        )

    def _fx_rate(self, at: datetime, currency: str) -> Decimal | None:
        if currency == "KRW":
            return ONE
        snapshot = self.external_store.snapshot_asof(at)
        known = [
            item
            for item in snapshot.observations
            if item.series == "usdkrw" and item.available_at <= at
        ]
        if not known:
            return None
        latest = max(known, key=lambda item: (item.observed_on, item.available_at))
        if (at.astimezone(UTC).date() - latest.observed_on).days > 7:
            return None
        return latest.value

    def _unresolved_corporate_action(
        self,
        session: ForwardSession,
        source: PortfolioInput,
        symbols: set[str],
        cutoff: datetime,
    ) -> str | None:
        for snapshot in source.instruments:
            instrument = snapshot.instruments[0].instrument
            if instrument.symbol not in symbols:
                continue
            calendar_name = EXCHANGE_CALENDAR.get(instrument.exchange)
            for action in snapshot.corporate_actions:
                if calendar_name is None:
                    return f"{instrument.symbol}:{action.date}:exchange_not_mapped"
                action_local_cutoff = cutoff.astimezone(
                    CALENDAR_TIMEZONE[calendar_name]
                ).date()
                activated_local = session.activated_at.astimezone(
                    CALENDAR_TIMEZONE[calendar_name]
                ).date()
                if action.date > action_local_cutoff or action.date < activated_local:
                    continue
                lookup = self._calendar.lookup(instrument.exchange, action.date)
                if lookup.session is None:
                    reason = (
                        lookup.reason
                        if lookup.state == "unavailable"
                        else "split_on_closed_date"
                    )
                    return f"{instrument.symbol}:{action.date}:{reason}"
                effective = lookup.session.open_at
                if session.activated_at < effective <= cutoff.astimezone(UTC):
                    numerator = int(action.numerator)
                    denominator = int(action.denominator)
                    exact_integers = (
                        action.numerator == numerator
                        and action.denominator == denominator
                    )
                    if (
                        exact_integers
                        and denominator > 0
                        and numerator > denominator
                        and numerator % denominator == 0
                        and self.store.split_is_applied(
                            session.id,
                            instrument.symbol,
                            effective,
                            numerator // denominator,
                        )
                    ):
                        continue
                    return (
                        f"{instrument.symbol}:{action.date.isoformat()}:"
                        f"{action.numerator}/{action.denominator}"
                    )
        return None

    def _expire_intents(self, session: ForwardSession, now: datetime) -> None:
        for decision in self.store.pending_decisions(session.id):
            if decision.expires_at is None or now <= decision.expires_at:
                continue
            for intent in decision.intents:
                if intent.state == "pending":
                    self.store.consume_intent(
                        decision,
                        intent.symbol,
                        "7일 만료로 미체결 지시를 소비했습니다.",
                    )
            self.store.record_event(
                session.id,
                now,
                "intent_expired",
                "정상 지시가 7일 동안 유효 시세를 만나지 못했습니다.",
                decision.id,
            )
