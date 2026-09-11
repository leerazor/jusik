from __future__ import annotations

import statistics
from bisect import bisect_right
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal, localcontext
from typing import Literal
from zoneinfo import ZoneInfo

from jusik.research_external_models import ExternalFeatureSnapshot, ExternalObservation
from jusik.research_models import DailyBar
from jusik.research_portfolio_models import (
    PortfolioCandidate,
    PortfolioConfig,
    PortfolioEquityPoint,
    PortfolioInput,
    PortfolioMetrics,
    PortfolioMonthlyDiagnostics,
    PortfolioPolicy,
    PortfolioPolicyDiagnostics,
    PortfolioPolicyEvent,
    PortfolioPosition,
    PortfolioSimulation,
    PortfolioTarget,
    PortfolioTrade,
)
from jusik.research_universe_models import (
    CorporateAction,
    OfflineResearchSnapshot,
    ResearchInstrument,
)

ZERO = Decimal(0)
ONE = Decimal(1)
LEVERAGED_ETFS = frozenset({"SOXL", "TQQQ"})


@dataclass(frozen=True)
class InstrumentData:
    instrument: ResearchInstrument
    snapshot: OfflineResearchSnapshot
    bars_by_date: dict[date, DailyBar]
    actions_by_date: dict[date, CorporateAction]


@dataclass(frozen=True)
class MarketEvent:
    at: datetime
    kind: Literal["open", "close", "rebalance"]
    symbol: str | None = None
    day: date | None = None


@dataclass(frozen=True)
class _ExecutionCostTerm:
    current_value: Decimal
    sell_loss_fraction: Decimal
    buy_loss_fraction: Decimal


def _conservative_nav_floor(
    total_equity: Decimal,
    cash: Decimal,
    terms: Sequence[_ExecutionCostTerm],
) -> Decimal:
    actionable_value = sum((term.current_value for term in terms), ZERO)
    nonactionable_value = total_equity - cash - actionable_value
    maximum_sell_loss = sum(
        (term.current_value * term.sell_loss_fraction for term in terms), ZERO
    )
    maximum_cash_after_sells = cash + actionable_value - maximum_sell_loss
    maximum_buy_loss_fraction = max(
        (term.buy_loss_fraction for term in terms), default=ZERO
    )
    return nonactionable_value + maximum_cash_after_sells * (
        ONE - maximum_buy_loss_fraction
    )


def candidates() -> tuple[PortfolioCandidate, ...]:
    return tuple(
        PortfolioCandidate(id=f"portfolio_{method}_{gate}_v1", method=method, gate=gate)
        for method in ("equal", "inverse_volatility", "momentum_top4")
        for gate in ("none", "rates", "fx_vix", "stress")
    )


def _market_time(day: date, timezone_name: str, *, opening: bool) -> datetime:
    local_time = time(9, 0) if timezone_name == "Asia/Seoul" else time(9, 30)
    if not opening:
        local_time = time(15, 30) if timezone_name == "Asia/Seoul" else time(16, 0)
    return datetime.combine(day, local_time, ZoneInfo(timezone_name)).astimezone(UTC)


def _instrument_data(source: PortfolioInput) -> dict[str, InstrumentData]:
    result: dict[str, InstrumentData] = {}
    for snapshot in source.instruments:
        item = snapshot.instruments[0]
        result[item.symbol] = InstrumentData(
            instrument=item.instrument,
            snapshot=snapshot,
            bars_by_date={bar.date: bar for bar in item.bars},
            actions_by_date={
                action.date: action for action in snapshot.corporate_actions
            },
        )
    return result


def _as_of_external(
    snapshot: ExternalFeatureSnapshot,
    series: str,
    at: datetime,
) -> list[ExternalObservation]:
    revisions: dict[date, ExternalObservation] = {}
    for item in snapshot.observations:
        if (
            item.series != series
            or item.observed_on > at.date()
            or item.available_at > at
        ):
            continue
        prior = revisions.get(item.observed_on)
        if prior is None or (item.available_at, item.revision) > (
            prior.available_at,
            prior.revision,
        ):
            revisions[item.observed_on] = item
    return [revisions[day] for day in sorted(revisions)]


def _external_window(
    source: PortfolioInput,
    series: str,
    at: datetime,
    config: PortfolioConfig,
    count: int = 21,
) -> list[Decimal] | None:
    rows = _as_of_external(source.external, series, at)
    if len(rows) < count:
        return None
    selected = rows[-count:]
    if (at.date() - selected[-1].observed_on).days > config.external_max_age_days:
        return None
    return [row.value for row in selected]


def _fx_rate(
    source: PortfolioInput, at: datetime, config: PortfolioConfig
) -> Decimal | None:
    values = _external_window(source, "usdkrw", at, config, count=1)
    return values[-1] if values else None


def _gate_allowed(
    source: PortfolioInput,
    candidate: PortfolioCandidate,
    at: datetime,
    config: PortfolioConfig,
) -> bool | None:
    if candidate.gate == "none":
        return True
    required = {
        "rates": ("treasury_2y", "treasury_10y"),
        "fx_vix": ("usdkrw", "vix"),
        "stress": ("uso", "gld", "hyg"),
    }[candidate.gate]
    windows = {
        series: _external_window(source, series, at, config) for series in required
    }
    if any(values is None for values in windows.values()):
        return None
    if candidate.gate == "rates":
        two = windows["treasury_2y"]
        ten = windows["treasury_10y"]
        assert two is not None and ten is not None
        return ten[-1] - two[-1] >= Decimal("-1") and ten[-1] - ten[0] <= Decimal(
            "0.50"
        )
    if candidate.gate == "fx_vix":
        fx = windows["usdkrw"]
        vix = windows["vix"]
        assert fx is not None and vix is not None
        return fx[-1] / fx[0] - ONE <= Decimal("0.05") and vix[-1] <= Decimal("30")
    uso = windows["uso"]
    gld = windows["gld"]
    hyg = windows["hyg"]
    assert uso is not None and gld is not None and hyg is not None
    return (
        uso[-1] / uso[0] - ONE <= Decimal("0.15")
        and gld[-1] / gld[0] - ONE <= Decimal("0.10")
        and hyg[-1] / hyg[0] - ONE >= Decimal("-0.03")
    )


def _known_bars(data: InstrumentData, at: datetime) -> list[DailyBar]:
    return [
        bar
        for bar in data.snapshot.instruments[0].bars
        if _market_time(bar.date, data.instrument.timezone, opening=False) <= at
    ]


def _returns(bars: list[DailyBar], window: int) -> dict[date, float]:
    selected = bars[-(window + 1) :]
    result: dict[date, float] = {}
    for previous, current in zip(selected[:-1], selected[1:], strict=True):
        prior = float(previous.adjusted_close)
        result[current.date] = float(current.adjusted_close) / prior - 1
    return result


def _correlation(left: dict[date, float], right: dict[date, float]) -> float:
    common = sorted(set(left) & set(right))
    if len(common) < 20:
        return 0.0
    x = [left[day] for day in common]
    y = [right[day] for day in common]
    if statistics.pstdev(x) == 0 or statistics.pstdev(y) == 0:
        return 0.0
    return statistics.correlation(x, y)


def _normalize_weights(
    raw: dict[str, Decimal], config: PortfolioConfig
) -> dict[str, Decimal]:
    positive = {symbol: value for symbol, value in raw.items() if value > 0}
    if not positive:
        return {}
    total = sum(positive.values(), ZERO)
    weights = {
        symbol: min(config.symbol_cap, config.gross_cap * value / total)
        for symbol, value in positive.items()
    }
    uncapped = {symbol for symbol in positive if weights[symbol] < config.symbol_cap}
    while sum(weights.values(), ZERO) < config.gross_cap and uncapped:
        room = config.gross_cap - sum(weights.values(), ZERO)
        raw_total = sum((positive[symbol] for symbol in uncapped), ZERO)
        changed = False
        for symbol in tuple(uncapped):
            addition = room * positive[symbol] / raw_total
            updated = min(config.symbol_cap, weights[symbol] + addition)
            changed = changed or updated > weights[symbol]
            weights[symbol] = updated
            if updated >= config.symbol_cap:
                uncapped.remove(symbol)
        if not changed:
            break
    leveraged = sum((weights.get(symbol, ZERO) for symbol in LEVERAGED_ETFS), ZERO)
    if leveraged > config.leveraged_etf_cap:
        factor = config.leveraged_etf_cap / leveraged
        for symbol in LEVERAGED_ETFS:
            if symbol in weights:
                weights[symbol] *= factor
    return weights


def target_weights(
    source: PortfolioInput,
    candidate: PortfolioCandidate,
    at: datetime,
    config: PortfolioConfig,
) -> tuple[dict[str, Decimal], dict[str, Decimal], str | None]:
    allowed = _gate_allowed(source, candidate, at, config)
    if allowed is None:
        return {}, {}, "external data missing or stale"
    if not allowed:
        return {}, {}, None
    data = _instrument_data(source)
    histories: dict[str, list[DailyBar]] = {}
    volatilities: dict[str, Decimal] = {}
    momentums: dict[str, Decimal] = {}
    return_series: dict[str, dict[date, float]] = {}
    for symbol, item in data.items():
        bars = _known_bars(item, at)
        if len(bars) < max(61, config.signal_window):
            continue
        latest = bars[-1]
        average = (
            sum(
                (bar.adjusted_close for bar in bars[-config.signal_window :]),
                ZERO,
            )
            / config.signal_window
        )
        if latest.adjusted_close <= average:
            continue
        returns = _returns(bars, config.volatility_window)
        values = list(returns.values())
        if len(values) < config.volatility_window or statistics.pstdev(values) == 0:
            if candidate.method != "equal":
                continue
        histories[symbol] = bars
        return_series[symbol] = returns
        if values and statistics.pstdev(values) > 0:
            volatilities[symbol] = Decimal(str(statistics.pstdev(values)))
        if len(bars) >= config.momentum_window + 1:
            momentums[symbol] = (
                bars[-1].adjusted_close
                / bars[-(config.momentum_window + 1)].adjusted_close
                - ONE
            )
    if candidate.method == "equal":
        raw = {symbol: ONE for symbol in histories}
        return _normalize_weights(raw, config), {}, None
    if candidate.method == "inverse_volatility":
        raw = {symbol: ONE / value for symbol, value in volatilities.items()}
        return _normalize_weights(raw, config), {}, None
    selected = sorted(
        (
            symbol
            for symbol in histories
            if symbol in momentums and symbol in volatilities
        ),
        key=lambda symbol: (-momentums[symbol], symbol),
    )[:4]
    diagnostics: dict[str, Decimal] = {}
    raw = {}
    for symbol in selected:
        peers = [
            max(0.0, _correlation(return_series[symbol], return_series[peer]))
            for peer in selected
            if peer != symbol
        ]
        positive_average = sum(peers) / len(peers) if peers else 0.0
        diagnostics[symbol] = Decimal(str(positive_average))
        raw[symbol] = (ONE / volatilities[symbol]) / (ONE + diagnostics[symbol])
    return _normalize_weights(raw, config), diagnostics, None


def volatility_scale(
    source: PortfolioInput,
    data: dict[str, InstrumentData],
    weights: dict[str, Decimal],
    at: datetime,
    config: PortfolioConfig,
    fx_cache: dict[datetime, Decimal | None] | None = None,
) -> tuple[Decimal | None, Decimal | None]:
    if not weights:
        return ONE, ZERO
    global_days = sorted(
        {
            _market_time(bar.date, item.instrument.timezone, opening=False).date()
            for item in data.values()
            for bar in item.snapshot.instruments[0].bars
            if _market_time(bar.date, item.instrument.timezone, opening=False) < at
        }
    )[-(config.volatility_window + 1) :]
    if len(global_days) < config.volatility_window + 1:
        return None, None
    proxy = ZERO
    for symbol, weight in weights.items():
        item = data[symbol]
        values: list[Decimal] = []
        bars = item.snapshot.instruments[0].bars
        known_closes = [
            _market_time(bar.date, item.instrument.timezone, opening=False)
            for bar in bars
        ]
        for day in global_days:
            cutoff = datetime.combine(day, time.max, UTC)
            causal_cutoff = min(cutoff, at)
            index = bisect_right(known_closes, causal_cutoff) - 1
            if index < 0:
                return None, None
            value = bars[index].adjusted_close
            if item.instrument.currency == "USD":
                if fx_cache is not None and causal_cutoff in fx_cache:
                    fx = fx_cache[causal_cutoff]
                else:
                    fx = _fx_rate(source, causal_cutoff, config)
                    if fx_cache is not None:
                        fx_cache[causal_cutoff] = fx
                if fx is None:
                    return None, None
                value *= fx
            values.append(value)
        returns = [
            current / previous - 1
            for previous, current in zip(values[:-1], values[1:], strict=True)
        ]
        sigma = (
            statistics.pstdev(returns)
            * Decimal(config.volatility_annualization_sessions).sqrt()
        )
        proxy += weight * sigma
    if proxy == 0:
        return ONE, ZERO
    return min(ONE, config.volatility_target / proxy), proxy


def forward_volatility_scale(
    source: PortfolioInput,
    weights: dict[str, Decimal],
    at: datetime,
    config: PortfolioConfig,
) -> tuple[Decimal | None, Decimal | None]:
    """Small causal policy helper shared by backtest and forward PAPER research."""
    return volatility_scale(source, _instrument_data(source), weights, at, config)


# Kept for the historical regression contract and older internal callers.
_volatility_scale = volatility_scale


def _events(
    data: dict[str, InstrumentData], start: date, end: date
) -> list[MarketEvent]:
    events: list[MarketEvent] = []
    cursor = start
    while cursor <= end:
        if cursor.weekday() == 0:
            events.append(
                MarketEvent(datetime.combine(cursor, time(), UTC), "rebalance")
            )
        cursor += timedelta(days=1)
    for symbol, item in data.items():
        for day in item.bars_by_date:
            if start <= day <= end:
                events.extend(
                    (
                        MarketEvent(
                            _market_time(day, item.instrument.timezone, opening=True),
                            "open",
                            symbol,
                            day,
                        ),
                        MarketEvent(
                            _market_time(day, item.instrument.timezone, opening=False),
                            "close",
                            symbol,
                            day,
                        ),
                    )
                )
    return sorted(
        events,
        key=lambda item: (
            item.at,
            {"rebalance": 0, "open": 1, "close": 2}[item.kind],
            item.symbol or "",
        ),
    )


def _simulate(
    source: PortfolioInput,
    candidate: PortfolioCandidate,
    start: date,
    end: date,
    config: PortfolioConfig,
    policy: PortfolioPolicy,
) -> PortfolioSimulation:
    data = _instrument_data(source)
    cash = config.initial_cash_krw
    positions: dict[str, int] = defaultdict(int)
    latest_local: dict[str, Decimal] = {}
    pending: dict[str, tuple[datetime, Decimal]] = {}
    trades: list[PortfolioTrade] = []
    targets: list[PortfolioTarget] = []
    equity_points: list[PortfolioEquityPoint] = []
    incomplete: set[str] = set()
    contributions: dict[str, Decimal] = defaultdict(lambda: ZERO)
    split_cash: dict[str, Decimal] = defaultdict(lambda: ZERO)
    overlap: dict[str, Decimal] = {}
    high_water = config.initial_cash_krw
    max_drawdown = ZERO
    turnover = ZERO
    latched = False
    latched_at: datetime | None = None
    episode_high_water = config.initial_cash_krw
    liquidation_completed_at: datetime | None = None
    recovery_count = 0
    reentry_ready = False
    policy_events: list[PortfolioPolicyEvent] = []
    fx_cache: dict[datetime, Decimal | None] = {}
    uses_reentry = policy in {
        "reentry_only",
        "combined",
        "low_turnover_combined",
    }
    uses_volatility = policy in {
        "volatility_only",
        "combined",
        "low_turnover_combined",
    }
    uses_low_turnover = policy == "low_turnover_combined"
    first_monday = start + timedelta(days=(7 - start.weekday()) % 7)

    def local_value(symbol: str, price: Decimal, fx: Decimal) -> Decimal:
        return Decimal(positions[symbol]) * price * fx

    def fx_for(symbol: str, at: datetime) -> Decimal | None:
        if data[symbol].instrument.currency == "KRW":
            return ONE
        if at not in fx_cache:
            fx_cache[at] = _fx_rate(source, at, config)
        value = fx_cache[at]
        if value is None:
            incomplete.add(f"{at.isoformat()}: USD/KRW missing or stale")
        return value

    def equity(
        at: datetime, open_prices: dict[str, Decimal] | None = None
    ) -> Decimal | None:
        total = cash
        for symbol, quantity in positions.items():
            if quantity <= 0:
                continue
            price = (open_prices or {}).get(symbol, latest_local.get(symbol))
            fx = fx_for(symbol, at)
            if price is None or fx is None:
                incomplete.add(
                    f"{at.isoformat()}: held position cannot be valued: {symbol}"
                )
                return None
            total += Decimal(quantity) * price * fx
        return total

    grouped: dict[datetime, list[MarketEvent]] = defaultdict(list)
    for event in _events(data, start, end):
        grouped[event.at].append(event)
    for at in sorted(grouped):
        group = grouped[at]
        if any(event.kind == "rebalance" for event in group):
            weeks_from_anchor = (at.date() - first_monday).days // 7
            cadence_due = not uses_low_turnover or (
                weeks_from_anchor % config.low_turnover_weeks == 0
            )
            weights: dict[str, Decimal] | None = None
            correlations: dict[str, Decimal] = {}
            reason: str | None = None
            if latched and uses_reentry and liquidation_completed_at is not None:
                cooldown_complete = at.date() >= (
                    liquidation_completed_at.date()
                    + timedelta(days=config.reentry_cooldown_days)
                )
                if cooldown_complete:
                    recovery_weights, correlations, reason = target_weights(
                        source, candidate, at, config
                    )
                    recovered = (
                        reason is None
                        and sum(value > 0 for value in recovery_weights.values())
                        >= config.recovery_minimum_assets
                    )
                    if reason is not None:
                        incomplete.add(f"{at.isoformat()}: {reason}")
                    if recovered:
                        if reentry_ready and cadence_due:
                            weights = recovery_weights
                            latched = False
                            liquidation_completed_at = None
                            reentry_ready = False
                            recovery_count = 0
                            current_nav = equity(at)
                            if current_nav is not None:
                                episode_high_water = current_nav
                            policy_events.append(
                                PortfolioPolicyEvent(
                                    at=at,
                                    kind="reentry",
                                    detail="next scheduled rebalance after recovery",
                                )
                            )
                        elif not reentry_ready:
                            recovery_count += 1
                            policy_events.append(
                                PortfolioPolicyEvent(
                                    at=at,
                                    kind="recovery_confirmation",
                                    detail=f"confirmation {recovery_count}",
                                    value=Decimal(recovery_count),
                                )
                            )
                            if recovery_count >= config.recovery_confirmations:
                                reentry_ready = True
                                policy_events.append(
                                    PortfolioPolicyEvent(
                                        at=at,
                                        kind="reentry_ready",
                                        detail="waiting for next scheduled rebalance",
                                    )
                                )
                    elif recovery_count or reentry_ready:
                        recovery_count = 0
                        reentry_ready = False
                        policy_events.append(
                            PortfolioPolicyEvent(
                                at=at,
                                kind="recovery_reset",
                                detail=reason or "fewer than two eligible assets",
                            )
                        )
            elif not latched:
                if cadence_due:
                    weights, correlations, reason = target_weights(
                        source, candidate, at, config
                    )
                elif uses_low_turnover:
                    policy_events.append(
                        PortfolioPolicyEvent(
                            at=at,
                            kind="frequency_skip",
                            detail="four-week cadence",
                        )
                    )
            if weights is not None:
                overlap.update(correlations)
                if reason:
                    incomplete.add(f"{at.isoformat()}: {reason}")
                    weights = {}
                if uses_volatility and weights:
                    scale, proxy = volatility_scale(
                        source, data, weights, at, config, fx_cache
                    )
                    if scale is None:
                        incomplete.add(
                            f"{at.isoformat()}: volatility history or FX missing"
                        )
                        weights = {}
                    elif scale < ONE:
                        weights = {
                            symbol: value * scale for symbol, value in weights.items()
                        }
                        policy_events.append(
                            PortfolioPolicyEvent(
                                at=at,
                                kind="volatility_scale",
                                detail="conservative weighted volatility proxy",
                                value=proxy,
                            )
                        )
                if uses_low_turnover and weights:
                    current_nav = equity(at)
                    actual_weights: dict[str, Decimal] = {}
                    if current_nav is not None and current_nav > 0:
                        for symbol in data:
                            price = latest_local.get(symbol)
                            fx = fx_for(symbol, at)
                            if price is not None and fx is not None:
                                actual_weights[symbol] = (
                                    local_value(symbol, price, fx) / current_nav
                                )
                    gross = sum(actual_weights.values(), ZERO)
                    leveraged = sum(
                        (actual_weights.get(item, ZERO) for item in LEVERAGED_ETFS),
                        ZERO,
                    )
                    caps_violated = (
                        gross > config.gross_cap
                        or leveraged > config.leveraged_etf_cap
                        or any(
                            value > config.symbol_cap
                            for value in actual_weights.values()
                        )
                    )
                    if not caps_violated:
                        for symbol, target_weight in tuple(weights.items()):
                            actual = actual_weights.get(symbol, ZERO)
                            if (
                                target_weight > 0
                                and abs(actual - target_weight)
                                < config.low_turnover_band
                            ):
                                weights[symbol] = actual
                                policy_events.append(
                                    PortfolioPolicyEvent(
                                        at=at,
                                        kind="band_skip",
                                        detail=symbol,
                                        value=abs(actual - target_weight),
                                    )
                                )
                for symbol in data:
                    weight = weights.get(symbol, ZERO)
                    pending[symbol] = (at, weight)
                    targets.append(
                        PortfolioTarget(
                            decided_at=at,
                            symbol=symbol,
                            target_weight=weight,
                        )
                    )

        opens = [event for event in group if event.kind == "open"]
        if opens:
            open_prices = {
                event.symbol: data[event.symbol].bars_by_date[event.day].open
                for event in opens
                if event.symbol is not None and event.day is not None
            }
            for event in opens:
                assert event.symbol is not None and event.day is not None
                action = data[event.symbol].actions_by_date.get(event.day)
                if action is not None and positions[event.symbol] > 0:
                    exact = Decimal(positions[event.symbol]) * action.factor
                    whole = int(exact.to_integral_value(rounding=ROUND_FLOOR))
                    fraction = exact - whole
                    fx = fx_for(event.symbol, at)
                    if fx is not None:
                        cash_in_lieu = fraction * open_prices[event.symbol] * fx
                        cash += cash_in_lieu
                        contributions[event.symbol] += cash_in_lieu
                        split_cash[event.symbol] += cash_in_lieu
                    positions[event.symbol] = whole
            total_equity = equity(at, open_prices)
            if total_equity is None:
                continue
            current: dict[str, Decimal] = {}
            actionable: dict[str, tuple[datetime, Decimal]] = {}
            for event in opens:
                assert event.symbol is not None
                instruction = pending.get(event.symbol)
                if instruction is None or instruction[0] >= at:
                    continue
                fx = fx_for(event.symbol, at)
                if fx is None:
                    continue
                actionable[event.symbol] = instruction
                current[event.symbol] = local_value(
                    event.symbol, open_prices[event.symbol], fx
                )
            held_values: dict[str, Decimal] = {}
            for symbol, quantity in positions.items():
                if quantity <= 0:
                    continue
                price = open_prices.get(symbol, latest_local.get(symbol))
                fx = fx_for(symbol, at)
                assert price is not None and fx is not None
                held_values[symbol] = Decimal(quantity) * price * fx
            cost_terms: list[_ExecutionCostTerm] = []
            for symbol in actionable:
                fx_multiplier = (
                    ONE + config.fx_spread_rate
                    if data[symbol].instrument.currency == "USD"
                    else ONE
                )
                sell_fx_multiplier = (
                    ONE - config.fx_spread_rate
                    if data[symbol].instrument.currency == "USD"
                    else ONE
                )
                sell_loss_fraction = ONE - (
                    (ONE - config.slippage_rate)
                    * (ONE - config.fee_rate)
                    * sell_fx_multiplier
                )
                buy_multiplier = (
                    (ONE + config.slippage_rate)
                    * (ONE + config.fee_rate)
                    * fx_multiplier
                )
                cost_terms.append(
                    _ExecutionCostTerm(
                        current_value=current[symbol],
                        sell_loss_fraction=sell_loss_fraction,
                        buy_loss_fraction=ONE - ONE / buy_multiplier,
                    )
                )
            pretrade_desired = {
                symbol: min(instruction[1], config.symbol_cap) * total_equity
                for symbol, instruction in actionable.items()
            }
            pretrade_gross = sum(held_values.values(), ZERO)
            pretrade_leveraged = sum(
                (held_values.get(symbol, ZERO) for symbol in LEVERAGED_ETFS),
                ZERO,
            )
            all_noop = all(
                current[symbol] == pretrade_desired[symbol] for symbol in actionable
            )
            no_cap_violation = (
                pretrade_gross <= config.gross_cap * total_equity
                and pretrade_leveraged <= config.leveraged_etf_cap * total_equity
                and all(
                    value <= config.symbol_cap * total_equity
                    for value in current.values()
                )
            )
            common_floor = (
                total_equity
                if all_noop and no_cap_violation
                else _conservative_nav_floor(
                    total_equity,
                    cash,
                    cost_terms,
                )
            )
            if common_floor <= 0:
                raise ValueError("Trading-cost NAV floor must be positive.")
            nonactionable_values = {
                symbol: value
                for symbol, value in held_values.items()
                if symbol not in actionable
            }
            nonactionable_gross = sum(nonactionable_values.values(), ZERO)
            nonactionable_leveraged = sum(
                (nonactionable_values.get(symbol, ZERO) for symbol in LEVERAGED_ETFS),
                ZERO,
            )
            deferred_constraints = []
            if nonactionable_gross > config.gross_cap * common_floor:
                deferred_constraints.append("gross")
            if nonactionable_leveraged > config.leveraged_etf_cap * common_floor:
                deferred_constraints.append("leveraged")
            deferred_constraints.extend(
                f"symbol={symbol}"
                for symbol, value in sorted(nonactionable_values.items())
                if value > config.symbol_cap * common_floor
            )
            if deferred_constraints:
                policy_events.append(
                    PortfolioPolicyEvent(
                        at=at,
                        kind="cap_constraint_deferred",
                        detail=(
                            "non-opening holdings exceed conservative budget: "
                            + ", ".join(deferred_constraints)
                        ),
                    )
                )
            desired = {
                symbol: min(instruction[1], config.symbol_cap) * common_floor
                for symbol, instruction in actionable.items()
            }
            target_total = sum(desired.values(), ZERO)
            target_gross_room = max(
                ZERO,
                config.gross_cap * common_floor - nonactionable_gross,
            )
            target_gross_scale = (
                min(ONE, target_gross_room / target_total) if target_total else ZERO
            )
            desired = {
                symbol: value * target_gross_scale for symbol, value in desired.items()
            }
            target_leveraged = sum(
                (desired.get(symbol, ZERO) for symbol in LEVERAGED_ETFS), ZERO
            )
            target_leveraged_room = max(
                ZERO,
                config.leveraged_etf_cap * common_floor - nonactionable_leveraged,
            )
            target_leveraged_scale = (
                min(ONE, target_leveraged_room / target_leveraged)
                if target_leveraged
                else ZERO
            )
            for symbol in LEVERAGED_ETFS & desired.keys():
                desired[symbol] *= target_leveraged_scale
            directions = {
                symbol: (
                    "sell"
                    if current[symbol] > desired[symbol]
                    else "buy"
                    if current[symbol] < desired[symbol]
                    else "noop"
                )
                for symbol in actionable
            }
            for symbol in sorted(actionable):
                if directions[symbol] != "sell" or positions[symbol] == 0:
                    continue
                fx = fx_for(symbol, at)
                assert fx is not None
                local_open = open_prices[symbol]
                execution = local_open * (ONE - config.slippage_rate)
                per_unit_value = local_open * fx
                sell_quantity = min(
                    positions[symbol],
                    int(
                        (
                            (current[symbol] - desired[symbol]) / per_unit_value
                        ).to_integral_value(rounding=ROUND_CEILING)
                    ),
                )
                if sell_quantity <= 0:
                    continue
                local_notional = Decimal(sell_quantity) * execution
                fee_local = local_notional * config.fee_rate
                gross_krw = (local_notional - fee_local) * fx
                fx_cost = (
                    gross_krw * config.fx_spread_rate
                    if data[symbol].instrument.currency == "USD"
                    else ZERO
                )
                proceeds = gross_krw - fx_cost
                cash += proceeds
                positions[symbol] -= sell_quantity
                cost = (
                    fee_local * fx
                    + Decimal(sell_quantity) * local_open * config.slippage_rate * fx
                )
                contributions[symbol] += proceeds
                turnover += local_notional * fx
                trades.append(
                    PortfolioTrade(
                        decided_at=actionable[symbol][0],
                        executed_at=at,
                        symbol=symbol,
                        side="sell",
                        quantity=sell_quantity,
                        local_price=execution,
                        fx_rate=fx,
                        notional_krw=local_notional * fx,
                        transaction_cost_krw=cost,
                        fx_cost_krw=fx_cost,
                    )
                )
            total_equity = equity(at, open_prices)
            if total_equity is None:
                continue
            requests: dict[str, tuple[int, Decimal, Decimal, Decimal]] = {}
            needs: dict[str, Decimal] = {}
            for symbol in sorted(actionable):
                if directions[symbol] != "buy":
                    continue
                fx = fx_for(symbol, at)
                if fx is None:
                    continue
                now_value = local_value(symbol, open_prices[symbol], fx)
                needs[symbol] = max(ZERO, desired[symbol] - now_value)
            held_value = total_equity - cash
            gross_room = max(ZERO, config.gross_cap * common_floor - held_value)
            need_total = sum(needs.values(), ZERO)
            gross_scale = min(ONE, gross_room / need_total) if need_total else ZERO
            leveraged_value = ZERO
            for symbol in LEVERAGED_ETFS:
                price = open_prices.get(symbol, latest_local.get(symbol))
                if positions[symbol] <= 0 or price is None or symbol not in data:
                    continue
                fx = fx_for(symbol, at)
                if fx is not None:
                    leveraged_value += local_value(symbol, price, fx)
            leveraged_need = sum(
                (needs.get(symbol, ZERO) for symbol in LEVERAGED_ETFS), ZERO
            )
            leveraged_room = max(
                ZERO,
                config.leveraged_etf_cap * common_floor - leveraged_value,
            )
            leveraged_scale = (
                min(ONE, leveraged_room / leveraged_need) if leveraged_need else ZERO
            )
            for symbol in sorted(actionable):
                if directions[symbol] != "buy":
                    continue
                fx = fx_for(symbol, at)
                if fx is None:
                    continue
                need = needs.get(symbol, ZERO) * gross_scale
                if symbol in LEVERAGED_ETFS:
                    need *= leveraged_scale
                execution = open_prices[symbol] * (ONE + config.slippage_rate)
                local_unit = execution * (ONE + config.fee_rate)
                krw_unit = local_unit * fx
                if data[symbol].instrument.currency == "USD":
                    krw_unit *= ONE + config.fx_spread_rate
                quantity = int(
                    (need / krw_unit).to_integral_value(rounding=ROUND_FLOOR)
                )
                if quantity > 0:
                    requests[symbol] = (quantity, execution, fx, krw_unit)
            requested_cash = sum(
                (Decimal(q) * unit for q, _p, _f, unit in requests.values()), ZERO
            )
            scale = min(ONE, cash / requested_cash) if requested_cash > 0 else ZERO
            for symbol in sorted(requests):
                requested, execution, fx, krw_unit = requests[symbol]
                quantity = int(
                    (Decimal(requested) * scale).to_integral_value(rounding=ROUND_FLOOR)
                )
                if quantity <= 0:
                    continue
                local_notional = Decimal(quantity) * execution
                fee_local = local_notional * config.fee_rate
                base_krw = (local_notional + fee_local) * fx
                fx_cost = (
                    base_krw * config.fx_spread_rate
                    if data[symbol].instrument.currency == "USD"
                    else ZERO
                )
                spent = base_krw + fx_cost
                if spent > cash:
                    continue
                cash -= spent
                positions[symbol] += quantity
                cost = (
                    fee_local * fx
                    + Decimal(quantity)
                    * open_prices[symbol]
                    * config.slippage_rate
                    * fx
                )
                contributions[symbol] -= spent
                turnover += local_notional * fx
                trades.append(
                    PortfolioTrade(
                        decided_at=actionable[symbol][0],
                        executed_at=at,
                        symbol=symbol,
                        side="buy",
                        quantity=quantity,
                        local_price=execution,
                        fx_rate=fx,
                        notional_krw=local_notional * fx,
                        transaction_cost_krw=cost,
                        fx_cost_krw=fx_cost,
                    )
                )
            post_trade_equity = equity(at, open_prices)
            if post_trade_equity is not None:
                for symbol, instruction in actionable.items():
                    fx = fx_for(symbol, at)
                    if fx is None:
                        continue
                    actual = (
                        local_value(symbol, open_prices[symbol], fx) / post_trade_equity
                        if post_trade_equity
                        else ZERO
                    )
                    for index in range(len(targets) - 1, -1, -1):
                        stored_target = targets[index]
                        if (
                            stored_target.symbol == symbol
                            and stored_target.decided_at == instruction[0]
                        ):
                            targets[index] = stored_target.model_copy(
                                update={"actual_weight_after_open": actual}
                            )
                            break
            for symbol in actionable:
                pending.pop(symbol, None)
            if (
                latched
                and liquidation_completed_at is None
                and not any(quantity > 0 for quantity in positions.values())
            ):
                liquidation_completed_at = at
                policy_events.append(
                    PortfolioPolicyEvent(
                        at=at,
                        kind="liquidation_complete",
                        detail="all positions closed",
                    )
                )

        closes = [event for event in group if event.kind == "close"]
        for event in closes:
            assert event.symbol is not None and event.day is not None
            latest_local[event.symbol] = (
                data[event.symbol].bars_by_date[event.day].close
            )
        if closes:
            value = equity(at)
            if value is not None:
                high_water = max(high_water, value)
                if not latched:
                    episode_high_water = max(episode_high_water, value)
                drawdown = (
                    (high_water - value) / high_water * 100 if high_water else ZERO
                )
                max_drawdown = max(max_drawdown, drawdown)
                equity_points.append(
                    PortfolioEquityPoint(
                        at=at, equity_krw=value, cash_krw=cash, drawdown_pct=drawdown
                    )
                )
                episode_drawdown = (
                    (episode_high_water - value) / episode_high_water * 100
                    if episode_high_water
                    else ZERO
                )
                if not latched and episode_drawdown >= config.drawdown_limit * 100:
                    latched = True
                    latched_at = at
                    liquidation_completed_at = None
                    recovery_count = 0
                    reentry_ready = False
                    policy_events.append(
                        PortfolioPolicyEvent(
                            at=at,
                            kind="risk_exit",
                            detail="episode drawdown limit reached",
                            value=episode_drawdown,
                        )
                    )
                    for symbol in data:
                        pending[symbol] = (at, ZERO)
                        targets.append(
                            PortfolioTarget(
                                decided_at=at,
                                symbol=symbol,
                                target_weight=ZERO,
                            )
                        )

    final_at = max(grouped, default=datetime.combine(end, time(), UTC))
    final_equity = equity(final_at)
    if final_equity is None:
        final_equity = cash
    final_positions: list[PortfolioPosition] = []
    for symbol in sorted(data):
        quantity = positions[symbol]
        if quantity <= 0:
            continue
        price = latest_local.get(symbol)
        fx = fx_for(symbol, final_at)
        if price is None or fx is None:
            continue
        value = Decimal(quantity) * price * fx
        contributions[symbol] += value
        fx_rows = _as_of_external(source.external, "usdkrw", final_at)
        final_positions.append(
            PortfolioPosition(
                symbol=symbol,
                quantity=quantity,
                currency=data[symbol].instrument.currency,
                local_close=price,
                fx_rate=fx,
                value_krw=value,
                weight=value / final_equity if final_equity else ZERO,
                valued_at=final_at,
                fx_observed_on=(
                    fx_rows[-1].observed_on
                    if data[symbol].instrument.currency == "USD" and fx_rows
                    else None
                ),
            )
        )
    transaction_cost = sum((trade.transaction_cost_krw for trade in trades), ZERO)
    fx_cost = sum((trade.fx_cost_krw for trade in trades), ZERO)
    metrics = PortfolioMetrics(
        initial_equity_krw=config.initial_cash_krw,
        final_equity_krw=final_equity,
        total_return_pct=(final_equity / config.initial_cash_krw - ONE) * 100,
        max_drawdown_pct=max_drawdown,
        trade_count=len(trades),
        transaction_cost_krw=transaction_cost,
        fx_cost_krw=fx_cost,
        turnover_pct=turnover / config.initial_cash_krw * 100,
    )
    return PortfolioSimulation(
        candidate=candidate,
        period_start=start,
        period_end=end,
        metrics=metrics,
        complete=not incomplete,
        incomplete_reasons=sorted(incomplete),
        drawdown_latched=latched,
        drawdown_latched_at=latched_at,
        equity=equity_points,
        trades=trades,
        weekly_targets=targets,
        positions=final_positions,
        contributions_krw=dict(sorted(contributions.items())),
        split_cash_in_lieu_krw=dict(sorted(split_cash.items())),
        overlap_diagnostics=dict(sorted(overlap.items())),
        policy=policy,
        policy_events=policy_events,
    )


def simulate(
    source: PortfolioInput,
    candidate: PortfolioCandidate,
    start: date,
    end: date,
    config: PortfolioConfig,
    policy: PortfolioPolicy = "corrected_control",
) -> PortfolioSimulation:
    with localcontext() as context:
        context.prec = 40
        return _simulate(source, candidate, start, end, config, policy)


def cash_metrics(config: PortfolioConfig) -> PortfolioMetrics:
    return PortfolioMetrics(
        initial_equity_krw=config.initial_cash_krw,
        final_equity_krw=config.initial_cash_krw,
        total_return_pct=ZERO,
        max_drawdown_pct=ZERO,
        trade_count=0,
        transaction_cost_krw=ZERO,
        fx_cost_krw=ZERO,
        turnover_pct=ZERO,
    )


def policy_diagnostics(
    simulation: PortfolioSimulation,
) -> PortfolioPolicyDiagnostics:
    day_end: dict[date, PortfolioEquityPoint] = {}
    for point in simulation.equity:
        day_end[point.at.date()] = point
    invested_days = sum(point.equity_krw > point.cash_krw for point in day_end.values())
    invested_pct = (
        Decimal(invested_days) / Decimal(len(day_end)) * 100 if day_end else ZERO
    )
    cursor = simulation.period_start.replace(day=1)
    final_month = simulation.period_end.replace(day=1)
    monthly: list[PortfolioMonthlyDiagnostics] = []
    while cursor <= final_month:
        month = cursor.strftime("%Y-%m")
        trades = [
            trade
            for trade in simulation.trades
            if trade.executed_at.strftime("%Y-%m") == month
        ]
        points = [
            point for day, point in day_end.items() if day.strftime("%Y-%m") == month
        ]
        average_nav = (
            sum((point.equity_krw for point in points), ZERO) / Decimal(len(points))
            if points
            else simulation.metrics.initial_equity_krw
        )
        turnover = (
            sum((trade.notional_krw for trade in trades), ZERO) / average_nav * 100
            if average_nav
            else ZERO
        )
        active = bool(trades) or any(
            point.equity_krw > point.cash_krw for point in points
        )
        monthly.append(
            PortfolioMonthlyDiagnostics(
                month=month,
                trade_count=len(trades),
                turnover_pct=turnover,
                active=active,
            )
        )
        cursor = (
            date(cursor.year + 1, 1, 1)
            if cursor.month == 12
            else date(cursor.year, cursor.month + 1, 1)
        )
    active_counts = [item.trade_count for item in monthly if item.active]
    events = simulation.policy_events
    return PortfolioPolicyDiagnostics(
        trading_utc_days=len({trade.executed_at.date() for trade in simulation.trades}),
        invested_days_pct=invested_pct,
        monthly=monthly,
        active_month_trade_average=(
            Decimal(sum(active_counts)) / Decimal(len(active_counts))
            if active_counts
            else ZERO
        ),
        active_month_trade_maximum=max(active_counts, default=0),
        reentry_count=sum(event.kind == "reentry" for event in events),
        exit_count=sum(event.kind == "risk_exit" for event in events),
        frequency_skip_count=sum(event.kind == "frequency_skip" for event in events),
        band_skip_count=sum(event.kind == "band_skip" for event in events),
        volatility_scale_event_count=sum(
            event.kind == "volatility_scale" for event in events
        ),
    )


def union_close_dates(source: PortfolioInput) -> list[date]:
    return sorted(
        {
            bar.date
            for snapshot in source.instruments
            for bar in snapshot.instruments[0].bars
            if snapshot.requested_start <= bar.date <= snapshot.requested_end
        }
    )
