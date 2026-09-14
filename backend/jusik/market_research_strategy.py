from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import date, timedelta
from decimal import ROUND_FLOOR, Decimal
from typing import NamedTuple

from jusik.market_history_models import (
    CandidateEvidence,
    FXObservation,
    MarketBar,
    MarketHistorySnapshot,
    MarketReadiness,
    MarketResearchRequest,
    MarketResearchResult,
    PITMembership,
    ResearchEquityPoint,
    ResearchTrade,
)
from jusik.research_market_calendar import MarketCalendar, MarketSession

PERCENT = Decimal("100")
TWENTY = 20
TARGET_WEIGHT = Decimal("0.05")
DRAWDOWN_LIMIT = Decimal("0.20")


class _PendingBuy(NamedTuple):
    symbol: str
    signal_session: date
    rank: int


def _floor_quantity(value: Decimal) -> int:
    return int(value.to_integral_value(rounding=ROUND_FLOOR))


def _expected_sessions(
    calendar: MarketCalendar, request: MarketResearchRequest
) -> list[MarketSession] | None:
    exchange = "KRX" if request.market == "KR" else "NMS"
    sessions: list[MarketSession] = []
    cursor = request.start_date
    while cursor <= request.end_date:
        lookup = calendar.lookup(exchange, cursor)
        if lookup.state == "unavailable":
            return None
        if lookup.session is not None:
            sessions.append(lookup.session)
        cursor += timedelta(days=1)
    return sessions


def _eligible_memberships(
    memberships: Iterable[PITMembership], session: MarketSession
) -> list[PITMembership]:
    return [
        item
        for item in memberships
        if item.instrument_type == "stock"
        and item.is_valid_on(session.local_date)
        and item.available_at <= session.close_at
    ]


def _rank_candidates(
    memberships: Iterable[PITMembership],
    bars_by_key: dict[tuple[str, date], MarketBar],
    session: MarketSession,
) -> list[CandidateEvidence]:
    rows: list[tuple[PITMembership, MarketBar]] = []
    seen_symbols: set[str] = set()
    for membership in _eligible_memberships(memberships, session):
        if membership.symbol in seen_symbols:
            continue
        bar = bars_by_key.get((membership.symbol, session.local_date))
        if bar is not None and bar.available_at <= session.close_at:
            rows.append((membership, bar))
            seen_symbols.add(membership.symbol)
    rows.sort(key=lambda item: (-item[1].volume, item[0].symbol))
    return [
        CandidateEvidence(
            session=session.local_date,
            symbol=membership.symbol,
            rank=index,
            volume=bar.volume,
            eligible=True,
            membership_available_at=membership.available_at,
            bar_available_at=bar.available_at,
        )
        for index, (membership, bar) in enumerate(rows[:20], start=1)
    ]


def _fx_for(
    observations: dict[date, FXObservation], session: date
) -> FXObservation | None:
    return observations.get(session)


def _valid_coverage(
    snapshot: MarketHistorySnapshot,
    request: MarketResearchRequest,
    sessions: list[MarketSession] | None,
) -> tuple[bool, list[str]]:
    missing: list[str] = []
    if snapshot.completeness != "complete":
        missing.extend(snapshot.missing_ranges or ("snapshot",))
    if not snapshot.actions_complete:
        missing.append("actions")
    if sessions is None or not sessions:
        missing.append("calendar")
        return False, sorted(set(missing))
    expected = {session.local_date for session in sessions}
    memberships = [
        item
        for item in snapshot.memberships
        if item.instrument_type == "stock" and item.valid_from <= request.end_date
    ]
    if not memberships:
        missing.append("membership")
    for membership in memberships:
        required_dates = {
            session.local_date
            for session in sessions
            if membership.is_valid_on(session.local_date)
            and membership.available_at <= session.close_at
        }
        dates = {
            bar.session
            for bar in snapshot.bars
            if bar.symbol == membership.symbol and bar.session in required_dates
        }
        if dates != required_dates:
            missing.append(f"bars:{membership.symbol}")
        if any(
            membership.is_valid_on(session.local_date)
            and membership.available_at > session.close_at
            for session in sessions
        ):
            missing.append(f"membership:{membership.symbol}")
    if request.market == "US":
        fx_dates = {item.session for item in snapshot.fx if item.pair == "USDKRW"}
        if not expected.issubset(fx_dates):
            missing.append("fx")
    return not missing, sorted(set(missing))


def run_market_research(
    snapshot: MarketHistorySnapshot,
    request: MarketResearchRequest,
    readiness: MarketReadiness,
    calendar: MarketCalendar,
    *,
    implementation_hash: str | None = None,
) -> MarketResearchResult:
    sessions = _expected_sessions(calendar, request)
    complete, missing = _valid_coverage(snapshot, request, sessions)
    if not readiness.ready:
        complete = False
        missing.append("readiness")
    if not complete or sessions is None:
        return MarketResearchResult(
            market=request.market,
            request=request,
            readiness=readiness,
            status="insufficient",
            completeness="incomplete",
            limitations=(
                "필수 PIT membership·일봉·기업행동·환율 자료가 모두 확인될 때까지 "
                "계산하지 않습니다.",
                "이 결과는 capability readiness만 보여 주며 수익률을 만들지 않습니다.",
            ),
            metrics={},
            implementation_hash=implementation_hash,
        ).model_copy(update={"input_hash": snapshot.input_hash})

    bars_by_key = {(bar.symbol, bar.session): bar for bar in snapshot.bars}
    fx_by_date = {item.session: item for item in snapshot.fx}
    evidence: list[CandidateEvidence] = []
    trades: list[ResearchTrade] = []
    equity: list[ResearchEquityPoint] = []
    positions: dict[str, int] = {}
    first_fx = _fx_for(fx_by_date, sessions[0].local_date)
    if request.market == "US":
        if first_fx is None:
            raise ValueError("US research requires an initial FX observation")
        cash_native = request.initial_cash_krw / (
            first_fx.krw_per_usd * (1 + first_fx.spread_rate)
        )
        initial_fx = first_fx.krw_per_usd
    else:
        cash_native = request.initial_cash_krw
        initial_fx = Decimal(1)
    pending_buys: list[_PendingBuy] = []
    pending_sells: dict[str, date] = {}
    below_sma: dict[str, int] = defaultdict(int)
    peak_nav = request.initial_cash_krw
    drawdown_latched = False

    for index, session in enumerate(sessions):
        fx_observation = _fx_for(fx_by_date, session.local_date)
        if request.market == "US":
            if fx_observation is None:
                raise ValueError("US research requires an FX observation per session")
            fx = fx_observation.krw_per_usd
        else:
            fx = Decimal(1)
        # Fill all decisions made at the prior close at this session's open.
        for symbol, signal_session in sorted(pending_sells.items()):
            quantity = positions.pop(symbol, 0)
            if quantity <= 0:
                continue
            bar = bars_by_key[(symbol, session.local_date)]
            fill_price = bar.open * (1 - request.slippage_rate)
            notional = fill_price * quantity
            fee = notional * request.fee_rate
            tax = notional * request.sell_tax_rate
            cash_native += notional - fee - tax
            trades.append(
                ResearchTrade(
                    session=session.local_date,
                    signal_session=signal_session,
                    fill_session=session.local_date,
                    symbol=symbol,
                    side="sell",
                    quantity=quantity,
                    currency="KRW" if request.market == "KR" else "USD",
                    market_open=bar.open,
                    fill_price=fill_price,
                    notional=notional,
                    fee=fee,
                    tax=tax,
                    rationale=(
                        "연속 2회 SMA20 하회 또는 낙폭 제한 발동 후 "
                        "다음 거래일 시가 청산"
                    ),
                )
            )
        pending_sells.clear()
        if not drawdown_latched:
            for pending in sorted(
                pending_buys, key=lambda item: (item.rank, item.symbol)
            ):
                if pending.symbol in positions or len(positions) >= 20:
                    continue
                bar = bars_by_key[(pending.symbol, session.local_date)]
                nav_native = cash_native + sum(
                    bars_by_key[(held, session.local_date)].close * quantity
                    for held, quantity in positions.items()
                )
                target = nav_native * TARGET_WEIGHT
                fill_price = bar.open * (1 + request.slippage_rate)
                quantity = _floor_quantity(target / fill_price)
                notional = fill_price * quantity
                fee = notional * request.fee_rate
                if quantity <= 0 or notional + fee > cash_native:
                    continue
                cash_native -= notional + fee
                positions[pending.symbol] = quantity
                trades.append(
                    ResearchTrade(
                        session=session.local_date,
                        signal_session=pending.signal_session,
                        fill_session=session.local_date,
                        symbol=pending.symbol,
                        side="buy",
                        quantity=quantity,
                        currency="KRW" if request.market == "KR" else "USD",
                        market_open=bar.open,
                        fill_price=fill_price,
                        notional=notional,
                        fee=fee,
                        tax=Decimal(0),
                        rationale=(
                            "거래량 상위 20 및 종가 breakout·거래량 조건 충족 후 "
                            "다음 거래일 시가 진입"
                        ),
                    )
                )
        pending_buys.clear()

        candidates = _rank_candidates(snapshot.memberships, bars_by_key, session)
        evidence.extend(candidates)
        for symbol in list(positions):
            bar = bars_by_key[(symbol, session.local_date)]
            sma_window = [
                bars_by_key[(symbol, prior_session.local_date)]
                for prior_session in sessions[max(0, index - TWENTY + 1) : index + 1]
            ]
            if len(sma_window) == TWENTY:
                sma = sum((item.close for item in sma_window), Decimal()) / TWENTY
                below_sma[symbol] = below_sma[symbol] + 1 if bar.close < sma else 0
                if below_sma[symbol] >= 2 and index + 1 < len(sessions):
                    pending_sells[symbol] = session.local_date
        for candidate in candidates:
            if candidate.rank > 20 or candidate.symbol in positions:
                continue
            prior = [
                bars_by_key[(candidate.symbol, prior_session.local_date)]
                for prior_session in sessions[max(0, index - TWENTY) : index]
            ]
            current = bars_by_key[(candidate.symbol, session.local_date)]
            if (
                len(prior) == TWENTY
                and current.close >= max(item.close for item in prior)
                and current.volume
                > sum((item.volume for item in prior), Decimal()) / TWENTY
                and index + 1 < len(sessions)
                and not drawdown_latched
            ):
                pending_buys.append(
                    _PendingBuy(candidate.symbol, session.local_date, candidate.rank)
                )

        invested_native = sum(
            bars_by_key[(symbol, session.local_date)].close * quantity
            for symbol, quantity in positions.items()
        )
        nav_krw = (cash_native + invested_native) * fx
        peak_nav = max(peak_nav, nav_krw)
        drawdown = (peak_nav - nav_krw) / peak_nav if peak_nav else Decimal(0)
        if drawdown >= DRAWDOWN_LIMIT and not drawdown_latched:
            drawdown_latched = True
            pending_buys.clear()
            pending_sells.update({symbol: session.local_date for symbol in positions})
        equity.append(
            ResearchEquityPoint(
                session=session.local_date,
                cash_krw=cash_native * fx,
                cash_native=cash_native,
                invested_krw=invested_native * fx,
                nav_krw=nav_krw,
                fx_krw_per_usd=fx,
                drawdown_pct=drawdown * PERCENT,
            )
        )

    final = equity[-1].nav_krw if equity else request.initial_cash_krw
    metrics = {
        "initial_cash_krw": request.initial_cash_krw,
        "final_nav_krw": final,
        "return_pct": (final / request.initial_cash_krw - 1) * PERCENT,
        "max_drawdown_pct": max(
            (item.drawdown_pct for item in equity), default=Decimal(0)
        ),
        "trade_count": Decimal(len(trades)),
        "drawdown_latched": Decimal(1 if drawdown_latched else 0),
        "initial_fx_krw_per_usd": initial_fx,
    }
    return MarketResearchResult(
        market=request.market,
        request=request,
        readiness=readiness,
        status="ready",
        completeness="complete",
        candidate_evidence=tuple(evidence),
        trades=tuple(trades),
        equity=tuple(equity),
        limitations=(
            "합성 자료는 인과 흐름 확인용이며 실제 수익률이나 주문 결과가 아닙니다."
            if readiness.simulated
            else "모의 연구 결과이며 실주문과 연결되지 않습니다.",
            "낙폭 제한은 감지된 뒤 다음 거래일 시가에 청산하며 gap으로 20%를 "
            "초과할 수 있습니다.",
        ),
        metrics=metrics,
        input_hash=snapshot.input_hash,
        implementation_hash=implementation_hash,
    )
