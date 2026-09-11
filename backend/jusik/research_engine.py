import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, time
from decimal import ROUND_FLOOR, ROUND_HALF_EVEN, Decimal, localcontext
from pathlib import Path
from zoneinfo import ZoneInfo

from jusik.operations_models import StrategyDefinition
from jusik.research_data import DataInsufficientError
from jusik.research_models import (
    BASELINE_VERSION,
    CANDIDATE_VERSION,
    AffectedDecision,
    BacktestResult,
    DailyBar,
    DataCoverage,
    EngineSpecification,
    EquityPoint,
    MarketEvent,
    ResearchInputSnapshot,
    ResearchRunRequest,
    StrategyMetrics,
    StrategyResult,
    Trade,
    UnfilledDecision,
    ValidationComparison,
)
from jusik.research_risk import ResearchRiskPolicy, ResearchRiskReport
from jusik.research_strategy import (
    BASELINE_DEFINITION,
    CANDIDATE_DEFINITION,
    target_for_definition,
    target_invested,
)
from jusik.research_universe_models import (
    CorporateActionEffect,
    ExternalStrategyResult,
    OfflineResearchRequest,
    OfflineResearchSnapshot,
)

KST = ZoneInfo("Asia/Seoul")
PERCENT = Decimal("100")
ENGINE_SPECIFICATION = EngineSpecification()
SignalFunction = Callable[[str, tuple[DailyBar, ...]], bool]
SignalRequest = ResearchRunRequest | OfflineResearchRequest
SignalSnapshot = ResearchInputSnapshot | OfflineResearchSnapshot


def canonical_hash(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def snapshot_hash(snapshot: ResearchInputSnapshot | OfflineResearchSnapshot) -> str:
    return canonical_hash(snapshot.model_dump(mode="json"))


def implementation_hash() -> str:
    digest = hashlib.sha256()
    for path in sorted(
        [
            Path(__file__),
            Path(__file__).with_name("research_risk.py"),
            Path(__file__).with_name("research_strategy.py"),
            Path(__file__).with_name("research_universe_models.py"),
        ]
    ):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


IMPLEMENTATION_HASH = implementation_hash()


def parameters_hash(request: ResearchRunRequest) -> str:
    return canonical_hash(
        {
            "specification": ENGINE_SPECIFICATION.model_dump(mode="json"),
            "implementation_hash": IMPLEMENTATION_HASH,
            "request": request.model_dump(mode="json", exclude={"events"}),
        }
    )


@dataclass
class _PortfolioState:
    cash: Decimal
    positions: dict[str, int] = field(default_factory=dict)
    pending: dict[str, bool] = field(default_factory=dict)
    signal_dates: dict[str, date] = field(default_factory=dict)
    last_close: dict[str, Decimal] = field(default_factory=dict)
    trades: list[Trade] = field(default_factory=list)
    equity: list[EquityPoint] = field(default_factory=list)
    affected: list[AffectedDecision] = field(default_factory=list)
    unfilled: list[UnfilledDecision] = field(default_factory=list)
    consumed_events: set[int] = field(default_factory=set)
    fees: Decimal = Decimal()
    tax: Decimal = Decimal()
    slippage: Decimal = Decimal()
    risk_latched: bool = False
    corporate_action_effects: list[CorporateActionEffect] = field(default_factory=list)


def _event_time(event: MarketEvent, field_name: str) -> datetime | None:
    value = getattr(event, field_name)
    return value.astimezone(KST) if value is not None else None


def _open_time(trading_date: date) -> datetime:
    return datetime.combine(trading_date, time(9), tzinfo=KST)


def _validate_execution_window(
    events: list[MarketEvent], trading_date: date, market: str
) -> None:
    fill_at = _open_time(trading_date)
    for event in events:
        if event.kind != "circuit_breaker" or event.market != market:
            continue
        occurred_at = _event_time(event, "occurred_at")
        resumed_at = _event_time(event, "resumed_at")
        assert occurred_at is not None
        if occurred_at <= fill_at and (resumed_at is None or resumed_at > fill_at):
            raise DataInsufficientError(
                "출처가 있는 서킷브레이커 중단 구간이 가정한 시가 체결과 "
                "겹쳐 일봉만으로 체결을 복원할 수 없습니다."
            )


def _defer_event(
    state: _PortfolioState,
    events: list[MarketEvent],
    trading_date: date,
    market: str,
) -> tuple[int, MarketEvent] | None:
    fill_at = _open_time(trading_date)
    for index, event in enumerate(events):
        if index in state.consumed_events:
            continue
        if event.market != market:
            continue
        occurred_at = _event_time(event, "occurred_at")
        known_at = _event_time(event, "known_at")
        assert occurred_at is not None and known_at is not None
        if occurred_at <= fill_at and known_at <= fill_at:
            return index, event
    return None


def _portfolio_equity(
    state: _PortfolioState,
    bars_today: dict[str, DailyBar],
    *,
    use_open: bool,
) -> Decimal:
    value = state.cash
    for symbol, quantity in state.positions.items():
        bar = bars_today.get(symbol)
        price = (
            bar.open
            if use_open and bar is not None
            else bar.close
            if bar is not None
            else state.last_close.get(symbol)
        )
        if price is not None:
            value += Decimal(quantity) * price
    return value


def _position_exposures(
    state: _PortfolioState,
    bars_today: dict[str, DailyBar],
    *,
    use_open: bool,
) -> dict[str, Decimal]:
    exposures: dict[str, Decimal] = {}
    for symbol, quantity in state.positions.items():
        bar = bars_today.get(symbol)
        price = (
            bar.open
            if use_open and bar is not None
            else bar.close
            if bar is not None
            else state.last_close.get(symbol)
        )
        if price is not None:
            exposures[symbol] = Decimal(quantity) * price
    return exposures


def _execute_sell(
    state: _PortfolioState,
    request: SignalRequest,
    trading_date: date,
    symbol: str,
    bar: DailyBar,
    signal_date: date,
    rationale: str | None = None,
) -> None:
    quantity = state.positions.get(symbol, 0)
    if quantity <= 0:
        return
    execution_price = bar.open * (Decimal(1) - request.slippage_rate)
    notional = execution_price * quantity
    fee = notional * request.fee_rate
    tax = notional * request.sell_tax_rate
    state.cash += notional - fee - tax
    state.positions.pop(symbol, None)
    state.fees += fee
    state.tax += tax
    state.slippage += (bar.open - execution_price) * quantity
    state.trades.append(
        Trade(
            date=trading_date,
            signal_date=signal_date,
            symbol=symbol,
            side="sell",
            quantity=quantity,
            market_open=bar.open,
            execution_price=execution_price,
            notional=notional,
            fee=fee,
            tax=tax,
            rationale=rationale
            or "신호일 종가에서 전략의 추세 조건이 더 이상 성립하지 않았습니다.",
        )
    )


def _execute_buy(
    state: _PortfolioState,
    request: SignalRequest,
    trading_date: date,
    symbol: str,
    bar: DailyBar,
    position_cap: Decimal,
    signal_date: date,
    risk_budget: Decimal | None = None,
) -> None:
    execution_price = bar.open * (Decimal(1) + request.slippage_rate)
    unit_cash = execution_price * (Decimal(1) + request.fee_rate)
    budget = min(state.cash, position_cap)
    if risk_budget is not None:
        budget = min(budget, risk_budget)
    quantity = int((budget / unit_cash).to_integral_value(rounding=ROUND_FLOOR))
    if quantity <= 0:
        reason = "가용 현금이 1주 매수 비용보다 적습니다."
        if risk_budget is not None and risk_budget < unit_cash:
            reason = "연구용 진입 위험 한도 안에서 1주를 매수할 수 없습니다."
        state.unfilled.append(
            UnfilledDecision(
                date=trading_date,
                symbol=symbol,
                side="buy",
                reason=reason,
            )
        )
        return
    notional = execution_price * quantity
    fee = notional * request.fee_rate
    state.cash -= notional + fee
    state.positions[symbol] = quantity
    state.fees += fee
    state.slippage += (execution_price - bar.open) * quantity
    state.trades.append(
        Trade(
            date=trading_date,
            signal_date=signal_date,
            symbol=symbol,
            side="buy",
            quantity=quantity,
            market_open=bar.open,
            execution_price=execution_price,
            notional=notional,
            fee=fee,
            tax=Decimal(),
            rationale="신호일 종가에서 전략의 추세 조건이 성립했습니다.",
        )
    )


def _metrics(state: _PortfolioState, initial_cash: Decimal) -> StrategyMetrics:
    final_equity = state.equity[-1].equity if state.equity else initial_cash
    peak = initial_cash
    max_drawdown = Decimal()
    for point in state.equity:
        peak = max(peak, point.equity)
        if peak:
            max_drawdown = max(max_drawdown, (peak - point.equity) / peak * PERCENT)
    return StrategyMetrics(
        initial_cash=initial_cash,
        final_equity=final_equity,
        total_return_pct=(final_equity - initial_cash) / initial_cash * PERCENT
        if initial_cash
        else Decimal(),
        max_drawdown_pct=max_drawdown,
        trade_count=len(state.trades),
        total_fees=state.fees,
        total_tax=state.tax,
        total_slippage_cost=state.slippage,
    )


def _run_strategy(
    request: SignalRequest,
    snapshot: SignalSnapshot,
    version: str,
    definition: str,
    strategy_definition: StrategyDefinition | None = None,
    signal: SignalFunction | None = None,
    defer_events: bool | None = None,
    risk_policy: ResearchRiskPolicy | None = None,
    risk_report: ResearchRiskReport | None = None,
) -> StrategyResult:
    if risk_report is not None and risk_policy is None:
        raise ValueError("risk_report requires risk_policy.")
    if risk_report is not None and risk_report.policy != risk_policy:
        raise ValueError("risk_report policy does not match risk_policy.")
    if risk_policy is not None and risk_report is None:
        risk_report = ResearchRiskReport.start(risk_policy, request.initial_cash)
    series = {
        item.symbol: sorted(item.bars, key=lambda bar: bar.date)
        for item in snapshot.symbols
    }
    indexes = {
        symbol: {bar.date: index for index, bar in enumerate(bars)}
        for symbol, bars in series.items()
    }
    trading_dates = sorted(
        {
            bar.date
            for bars in series.values()
            for bar in bars
            if request.start_date <= bar.date <= request.end_date
        }
    )
    if not trading_dates:
        raise DataInsufficientError("비교 기간에 거래일이 없습니다.")
    state = _PortfolioState(cash=request.initial_cash)
    external_snapshot = (
        snapshot if isinstance(snapshot, OfflineResearchSnapshot) else None
    )
    actions_by_date = (
        {action.date: action for action in external_snapshot.corporate_actions}
        if external_snapshot is not None
        else {}
    )
    for symbol, bars in series.items():
        prior = [
            index for index, bar in enumerate(bars) if bar.date < request.start_date
        ]
        if len(prior) < ENGINE_SPECIFICATION.warmup_bars:
            raise DataInsufficientError(f"{symbol}의 준비 일봉이 60개보다 적습니다.")
        desired = (
            signal(symbol, tuple(bars[: prior[-1] + 1]))
            if signal is not None
            else target_for_definition(strategy_definition, bars, prior[-1])
            if strategy_definition is not None
            else target_invested(version, bars, prior[-1])
        )
        if desired:
            state.pending[symbol] = True
            state.signal_dates[symbol] = series[symbol][prior[-1]].date

    for trading_date in trading_dates:
        bars_today = {
            symbol: bars[indexes[symbol][trading_date]]
            for symbol, bars in series.items()
            if trading_date in indexes[symbol]
        }
        action = actions_by_date.get(trading_date)
        if action is not None:
            assert external_snapshot is not None
            symbol = external_snapshot.instruments[0].symbol
            bar = bars_today.get(symbol)
            if bar is None:
                raise DataInsufficientError(
                    "기업행동일의 원주가 시가를 확인할 수 없습니다."
                )
            quantity_before = state.positions.get(symbol, 0)
            exact_quantity = Decimal(quantity_before) * action.factor
            quantity_after = int(exact_quantity.to_integral_value(rounding=ROUND_FLOOR))
            fractional_quantity = exact_quantity - Decimal(quantity_after)
            cash_in_lieu = fractional_quantity * bar.open
            if quantity_before:
                state.cash += cash_in_lieu
                if quantity_after:
                    state.positions[symbol] = quantity_after
                else:
                    state.positions.pop(symbol, None)
            if symbol in state.last_close:
                state.last_close[symbol] /= action.factor
            state.corporate_action_effects.append(
                CorporateActionEffect(
                    date=trading_date,
                    symbol=symbol,
                    factor=action.factor,
                    quantity_before=quantity_before,
                    quantity_after=quantity_after,
                    fractional_quantity=fractional_quantity,
                    cash_in_lieu=cash_in_lieu,
                )
            )
        if risk_report is not None:
            risk_report.observe_exposure(
                trading_date,
                "open",
                _portfolio_equity(state, bars_today, use_open=True),
                _position_exposures(state, bars_today, use_open=True),
            )
        for symbol in sorted(state.pending):
            if state.pending[symbol] or symbol not in state.positions:
                continue
            bar = bars_today.get(symbol)
            if bar is None:
                continue
            market = next(
                item.market for item in snapshot.symbols if item.symbol == symbol
            )
            _validate_execution_window(snapshot.events, trading_date, market)
            if bar.volume == 0:
                state.unfilled.append(
                    UnfilledDecision(
                        date=trading_date,
                        symbol=symbol,
                        side="sell",
                        reason=(
                            "해당 일봉의 거래량이 0이어서 체결을 가정하지 않았습니다."
                        ),
                    )
                )
                continue
            _execute_sell(
                state,
                request,
                trading_date,
                symbol,
                bar,
                state.signal_dates[symbol],
                (
                    "종가 기준 낙폭 한도에 도달해 연구용 위험 정책이 청산을 "
                    "요청했습니다."
                    if state.risk_latched
                    else None
                ),
            )
            state.pending.pop(symbol, None)
            state.signal_dates.pop(symbol, None)

        open_equity = _portfolio_equity(state, bars_today, use_open=True)
        position_cap = open_equity / Decimal(len(series))
        opening_exposures = _position_exposures(state, bars_today, use_open=True)
        opening_position_exposure = sum(opening_exposures.values(), Decimal())
        cash_before_buys = state.cash
        for symbol in sorted(state.pending):
            if not state.pending[symbol] or symbol in state.positions:
                continue
            bar = bars_today.get(symbol)
            if bar is None:
                continue
            market = next(
                item.market for item in snapshot.symbols if item.symbol == symbol
            )
            _validate_execution_window(snapshot.events, trading_date, market)
            if bar.volume == 0:
                state.unfilled.append(
                    UnfilledDecision(
                        date=trading_date,
                        symbol=symbol,
                        side="buy",
                        reason=(
                            "해당 일봉의 거래량이 0이어서 체결을 가정하지 않았습니다."
                        ),
                    )
                )
                continue
            should_defer_events = defer_events
            if should_defer_events is None:
                should_defer_events = version == CANDIDATE_VERSION or signal is not None
            if should_defer_events:
                deferred = _defer_event(state, snapshot.events, trading_date, market)
                if deferred is not None:
                    event_index, event = deferred
                    state.consumed_events.add(event_index)
                    state.affected.append(
                        AffectedDecision(
                            date=trading_date,
                            symbol=symbol,
                            event_kind=event.kind,
                            action="entry_deferred",
                            reason=(
                                "출처가 있고 시가 전에 알려진 시장 이벤트 뒤 "
                                "첫 신규 진입을 "
                                "일봉 연구 정책에 따라 한 거래일 미뤘습니다."
                            ),
                            source_url=str(event.source_url),
                        )
                    )
                    continue
            risk_budget: Decimal | None = None
            if risk_policy is not None:
                same_open_cash_debit = cash_before_buys - state.cash
                total_capacity = max(
                    Decimal(),
                    open_equity * risk_policy.max_total_entry_exposure
                    - opening_position_exposure
                    - same_open_cash_debit,
                )
                symbol_capacity = max(
                    Decimal(),
                    open_equity * risk_policy.max_symbol_entry_exposure
                    - opening_exposures.get(symbol, Decimal()),
                )
                risk_budget = min(total_capacity, symbol_capacity)
            _execute_buy(
                state,
                request,
                trading_date,
                symbol,
                bar,
                position_cap,
                state.signal_dates[symbol],
                risk_budget,
            )
            if symbol in state.positions:
                state.pending.pop(symbol, None)
                state.signal_dates.pop(symbol, None)

        for symbol, bar in bars_today.items():
            state.last_close[symbol] = bar.close
        close_equity = _portfolio_equity(state, bars_today, use_open=False)
        state.equity.append(
            EquityPoint(date=trading_date, equity=close_equity, cash=state.cash)
        )
        if risk_report is not None:
            risk_report.observe_exposure(
                trading_date,
                "close",
                close_equity,
                _position_exposures(state, bars_today, use_open=False),
            )
            if risk_report.observe_close(trading_date, close_equity):
                state.risk_latched = True
                for symbol in [
                    pending_symbol
                    for pending_symbol, desired in state.pending.items()
                    if desired
                ]:
                    state.pending.pop(symbol, None)
                    state.signal_dates.pop(symbol, None)
                for symbol in state.positions:
                    state.pending[symbol] = False
                    state.signal_dates[symbol] = trading_date
        if state.risk_latched:
            continue
        for symbol, bar in bars_today.items():
            desired = (
                signal(
                    symbol,
                    tuple(series[symbol][: indexes[symbol][bar.date] + 1]),
                )
                if signal is not None
                else target_for_definition(
                    strategy_definition,
                    series[symbol],
                    indexes[symbol][bar.date],
                )
                if strategy_definition is not None
                else target_invested(version, series[symbol], indexes[symbol][bar.date])
            )
            held = symbol in state.positions
            if desired != held:
                state.pending[symbol] = desired
                state.signal_dates[symbol] = trading_date
            else:
                state.pending.pop(symbol, None)
                state.signal_dates.pop(symbol, None)

    if risk_report is not None:
        risk_report.finish(state.positions)
    result = StrategyResult(
        strategy_version=version,
        definition=definition,
        metrics=_metrics(state, request.initial_cash),
        trades=state.trades,
        equity=state.equity,
        affected_decisions=state.affected,
        unfilled_decisions=state.unfilled,
        open_positions=state.positions,
    )
    if isinstance(snapshot, OfflineResearchSnapshot):
        return ExternalStrategyResult(
            **result.model_dump(),
            currency=snapshot.instruments[0].instrument.currency,
            price_basis=snapshot.price_basis,
            dividend_policy=snapshot.dividend_policy,
            corporate_action_effects=state.corporate_action_effects,
        )
    return result


def _run_backtest(
    request: ResearchRunRequest, snapshot: ResearchInputSnapshot
) -> BacktestResult:
    if (
        snapshot.requested_start != request.start_date
        or snapshot.requested_end != request.end_date
    ):
        raise DataInsufficientError("입력 스냅샷과 요청 기간이 다릅니다.")
    requested_symbols = sorted(request.symbols)
    snapshot_symbols = sorted(item.symbol for item in snapshot.symbols)
    if requested_symbols != snapshot_symbols:
        raise DataInsufficientError("입력 스냅샷과 요청 종목이 다릅니다.")
    if snapshot.events and any(item.market == "UNKNOWN" for item in snapshot.symbols):
        raise DataInsufficientError(
            "시장 소속을 확인할 수 없는 종목이 있어 입력한 시장 이벤트를 "
            "적용할 수 없습니다."
        )
    all_dates = {
        bar.date
        for item in snapshot.symbols
        for bar in item.bars
        if request.start_date <= bar.date <= request.end_date
    }
    coverage = []
    for item in snapshot.symbols:
        comparison_dates = {
            bar.date
            for bar in item.bars
            if request.start_date <= bar.date <= request.end_date
        }
        warmup = sum(bar.date < request.start_date for bar in item.bars)
        if not comparison_dates or warmup < ENGINE_SPECIFICATION.warmup_bars:
            raise DataInsufficientError(
                f"{item.symbol}의 과거 데이터 범위가 부족합니다."
            )
        coverage.append(
            DataCoverage(
                symbol=item.symbol,
                first_date=min(comparison_dates),
                last_date=max(comparison_dates),
                bars=len(comparison_dates),
                warmup_bars=warmup,
                missing_vs_union_dates=len(all_dates - comparison_dates),
            )
        )
    input_digest = snapshot_hash(snapshot)
    baseline = _run_strategy(request, snapshot, BASELINE_VERSION, BASELINE_DEFINITION)
    candidate = _run_strategy(
        request, snapshot, CANDIDATE_VERSION, CANDIDATE_DEFINITION
    )
    validation: ValidationComparison | None = None
    sorted_dates = sorted(all_dates)
    if len(sorted_dates) >= 40:
        split_index = max(20, int(len(sorted_dates) * 0.7))
        if split_index < len(sorted_dates):
            testing_start = sorted_dates[split_index]
            training_end = sorted_dates[split_index - 1]
            train_request = request.model_copy(update={"end_date": training_end})
            test_request = request.model_copy(update={"start_date": testing_start})
            # Both slices start with the same configured capital. Bars before each
            # slice are warm-up input only and never carry positions or equity.
            baseline_train = _run_strategy(
                train_request, snapshot, BASELINE_VERSION, BASELINE_DEFINITION
            )
            candidate_train = _run_strategy(
                train_request, snapshot, CANDIDATE_VERSION, CANDIDATE_DEFINITION
            )
            baseline_test = _run_strategy(
                test_request, snapshot, BASELINE_VERSION, BASELINE_DEFINITION
            )
            candidate_test = _run_strategy(
                test_request, snapshot, CANDIDATE_VERSION, CANDIDATE_DEFINITION
            )
            passed = (
                candidate_test.metrics.total_return_pct
                >= baseline_test.metrics.total_return_pct
                and candidate_test.metrics.max_drawdown_pct
                <= baseline_test.metrics.max_drawdown_pct
            )
            validation = ValidationComparison(
                training_start=request.start_date,
                training_end=training_end,
                testing_start=testing_start,
                testing_end=request.end_date,
                testing_initial_cash=request.initial_cash,
                training_baseline=baseline_train.metrics,
                training_candidate=candidate_train.metrics,
                baseline=baseline_test.metrics,
                candidate=candidate_test.metrics,
                recommended_version=CANDIDATE_VERSION if passed else BASELINE_VERSION,
                candidate_passed=passed,
                reason=(
                    "해당 실행의 후반 시간순 구간에서 기준 전략 이상의 수익률과 "
                    "이하의 최대 낙폭을 모두 충족했습니다."
                    if passed
                    else (
                        "해당 실행의 후반 시간순 구간에서 수익률과 최대 낙폭 합격 "
                        "조건을 모두 충족하지 못했습니다."
                    )
                ),
            )
    return BacktestResult(
        baseline=baseline,
        candidate=candidate,
        coverage=coverage,
        limitations=[
            (
                "일봉 종가로 신호를 계산하고 다음 거래 가능 시가 체결을 "
                "가정합니다. 장중 호가와 부분 체결은 반영하지 않습니다."
            ),
            (
                "원주가로 체결을 계산합니다. 배당과 총수익률은 지원하지 "
                "않으며 수정 비율이 변한 이력은 검증 불충분으로 처리합니다."
            ),
            (
                "사이드카를 전체 주식 거래중단으로 취급하지 않습니다. "
                "출처가 있고 알려진 이벤트는 후보 전략의 다음 신규 진입만 "
                "한 번 미룹니다."
            ),
            (
                "이벤트를 입력하지 않으면 서킷브레이커·사이드카 이력 범위는 "
                "확인 불가입니다. 일봉으로 장중 시장조치를 완전히 검증할 수 "
                "없습니다."
            ),
            (
                "시장 이벤트는 종목의 KOSPI·KOSDAQ 소속이 확인된 경우에만 "
                "같은 시장에 적용합니다."
            ),
            (
                "종료 시점 보유분은 강제 매도하지 않으며 마지막 확인 종가로 "
                "평가한 미실현 손익을 최종 평가액에 포함합니다."
            ),
            (
                "공식 KRX 거래일 달력이 없어 모든 종목에서 동시에 빠진 거래일은 "
                "검증하지 못했습니다. 표시된 누락일은 종목 간 차이만 뜻합니다."
            ),
            "결과는 연구 전용이며 실전 전략 승격이나 주문에 사용할 수 없습니다.",
        ],
        event_coverage="provided_partial" if snapshot.events else "unavailable",
        input_hash=input_digest,
        parameters_hash=parameters_hash(request),
        specification=ENGINE_SPECIFICATION,
        implementation_hash=IMPLEMENTATION_HASH,
        validation=validation,
    )


def run_backtest(
    request: ResearchRunRequest, snapshot: ResearchInputSnapshot
) -> BacktestResult:
    with localcontext() as context:
        context.prec = ENGINE_SPECIFICATION.decimal_precision
        context.rounding = ROUND_HALF_EVEN
        return _run_backtest(request, snapshot)


def run_definition_backtest(
    request: ResearchRunRequest,
    snapshot: ResearchInputSnapshot,
    definition: StrategyDefinition,
) -> StrategyResult:
    with localcontext() as context:
        context.prec = ENGINE_SPECIFICATION.decimal_precision
        context.rounding = ROUND_HALF_EVEN
        return _run_strategy(
            request,
            snapshot,
            definition.version,
            definition.definition,
            definition,
        )


def run_signal_backtest(
    request: SignalRequest,
    snapshot: SignalSnapshot,
    *,
    strategy_version: str,
    definition: str,
    signal: SignalFunction,
    defer_events: bool = True,
    risk_policy: ResearchRiskPolicy | None = None,
    risk_report: ResearchRiskReport | None = None,
) -> StrategyResult:
    """Run a causal close-bar signal through the shared Decimal execution engine."""
    if (
        request.start_date < snapshot.requested_start
        or request.end_date > snapshot.requested_end
    ):
        raise DataInsufficientError("입력 스냅샷과 요청 기간이 다릅니다.")
    if sorted(request.symbols) != sorted(item.symbol for item in snapshot.symbols):
        raise DataInsufficientError("입력 스냅샷과 요청 종목이 다릅니다.")
    with localcontext() as context:
        context.prec = ENGINE_SPECIFICATION.decimal_precision
        context.rounding = ROUND_HALF_EVEN
        return _run_strategy(
            request,
            snapshot,
            strategy_version,
            definition,
            signal=signal,
            defer_events=defer_events,
            risk_policy=risk_policy,
            risk_report=risk_report,
        )
