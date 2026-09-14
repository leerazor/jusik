from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Iterable
from datetime import date, datetime, timedelta
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
# Maintained alongside docs/market-research-mandate.sha256.  Keeping this
# identifier in the policy hash makes mandate edits invalidate old pilots.
RESEARCH_MANDATE_VERSION = "2026-09-13"
RESEARCH_MANDATE_JSON_SHA256 = (
    "6bf343dc7a6f0405d7044b65a5e1bcb2d26e4f920fe8aa37841aace641f3db16"
)
MARKET_RESEARCH_POLICY: dict[str, object] = {
    "version": 2,
    "mandate_version": RESEARCH_MANDATE_VERSION,
    "mandate_json_sha256": RESEARCH_MANDATE_JSON_SHA256,
    "top_count": 20,
    "lookback_sessions": 20,
    "target_weight": "0.05",
    "drawdown_fraction": "0.20",
    "breakout_comparison": "strict_greater_than_prior_20_high",
    "entry_fill": "next_tradable_open",
    "exit_rule": "two_consecutive_closes_below_sma20",
    "corporate_action_mode": "unsupported_actions_fail_closed",
    "rebalance": "none",
    "execution_assumptions": {
        "initial_cash_krw": "100000000",
        "fee_rate": "0.00015",
        "slippage_rate": "0.001",
        "sell_tax_rate": "0.0018",
    },
    "staged_validation": {
        "stages": ["pilot", "final"],
        "pilot_years": 1,
        "final_years": 3,
        "warmup_sessions": 20,
        "final_requires_completed_pilot": True,
    },
}
APPROXIMATE_MARKET_RESEARCH_POLICY: dict[str, object] = {
    "base_policy_version": MARKET_RESEARCH_POLICY["version"],
    "grade": "approximate",
    "sample_seed": 20260914,
    "max_unique_symbols": 400,
    "max_sample_symbols": 100,
    "missing_data": "skip_nonheld_block_whole_session_mark_held_last_close",
    "provenance": "prepared_historical_response_only",
    "dividend_delisting": "excluded_or_unknown",
}


def market_research_policy_hash(
    policy: dict[str, object] | None = None,
) -> str:
    canonical = json.dumps(
        policy if policy is not None else MARKET_RESEARCH_POLICY,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(canonical).hexdigest()


def market_research_policy_for_grade(grade: str) -> dict[str, object]:
    if grade == "approximate":
        return {**MARKET_RESEARCH_POLICY, **APPROXIMATE_MARKET_RESEARCH_POLICY}
    return MARKET_RESEARCH_POLICY


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


def _expected_warmup_sessions(
    calendar: MarketCalendar, request: MarketResearchRequest
) -> list[MarketSession] | None:
    exchange = "KRX" if request.market == "KR" else "NMS"
    sessions: list[MarketSession] = []
    # Sixty calendar days covers twenty sessions for the supported calendars;
    # keeping this bounded also makes calendar coverage failures explicit.
    cursor = request.start_date - timedelta(days=60)
    while cursor < request.start_date:
        lookup = calendar.lookup(exchange, cursor)
        if lookup.state == "unavailable":
            return None
        if lookup.session is not None:
            sessions.append(lookup.session)
        cursor += timedelta(days=1)
    return sessions[-TWENTY:]


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
    decision_cutoff: datetime,
) -> list[CandidateEvidence]:
    rows: list[tuple[PITMembership, MarketBar]] = []
    seen_symbols: set[str] = set()
    for membership in _eligible_memberships(memberships, session):
        if membership.symbol in seen_symbols:
            continue
        bar = bars_by_key.get((membership.symbol, session.local_date))
        if bar is not None and bar.available_at <= decision_cutoff:
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
    *,
    evaluation_start_index: int = 0,
    approximate: bool = False,
) -> tuple[bool, list[str]]:
    missing: list[str] = []
    if snapshot.completeness != "complete" and not approximate:
        missing.extend(snapshot.missing_ranges or ("snapshot",))
    if not snapshot.actions_complete and not approximate:
        missing.append("actions")
    if sessions is None or not sessions:
        missing.append("calendar")
        return False, sorted(set(missing))
    memberships = [
        item
        for item in snapshot.memberships
        if item.instrument_type == "stock" and item.valid_from <= request.end_date
    ]
    if not memberships:
        missing.append("membership")
    bars_by_key = {(bar.symbol, bar.session): bar for bar in snapshot.bars}
    for index, session in enumerate(sessions):
        next_session = sessions[index + 1] if index + 1 < len(sessions) else None
        decision_cutoff = next_session.open_at if next_session else session.close_at
        usable_bars = 0
        for membership in memberships:
            valid_now = membership.is_valid_on(session.local_date)
            if not valid_now:
                continue
            if membership.available_at > session.close_at:
                missing.append(f"membership:{membership.symbol}")
                continue
            bar = bars_by_key.get((membership.symbol, session.local_date))
            if approximate:
                if bar is None:
                    continue
                if bar.available_at < session.close_at:
                    missing.append(f"bar-before-close:{membership.symbol}")
                elif bar.available_at > decision_cutoff:
                    missing.append(f"bar-after-decision:{membership.symbol}")
                else:
                    usable_bars += 1
                continue
            if bar is None:
                missing.append(f"bars:{membership.symbol}")
            elif bar.available_at < session.close_at:
                missing.append(f"bar-before-close:{membership.symbol}")
            elif bar.available_at > decision_cutoff:
                missing.append(f"bar-after-decision:{membership.symbol}")
            if next_session is not None and not membership.is_valid_on(
                next_session.local_date
            ):
                missing.append(f"executable-membership:{membership.symbol}")
            elif (
                next_session is not None
                and (
                    membership.symbol,
                    next_session.local_date,
                )
                not in bars_by_key
            ):
                missing.append(f"fill-bar:{membership.symbol}")
        if approximate and usable_bars == 0:
            missing.append(f"bars:{session.local_date}")
    if request.market == "US":
        fx_by_date = {
            item.session: item for item in snapshot.fx if item.pair == "USDKRW"
        }
        for index, session in enumerate(sessions):
            observation = fx_by_date.get(session.local_date)
            if observation is None or observation.available_at > session.close_at:
                missing.append(f"fx:{session.local_date}")
            if index == evaluation_start_index and (
                observation is None or observation.available_at > session.open_at
            ):
                missing.append("initial-fx")
    return not missing, sorted(set(missing))


def run_market_research(
    snapshot: MarketHistorySnapshot,
    request: MarketResearchRequest,
    readiness: MarketReadiness,
    calendar: MarketCalendar,
    *,
    policy_hash: str | None = None,
    allow_approximate: bool = False,
) -> MarketResearchResult:
    approximate = allow_approximate and request.research_grade == "approximate"
    if (
        (request.research_grade != "strict" and not approximate)
        or snapshot.research_grade != request.research_grade
        or readiness.research_grade != request.research_grade
    ):
        return MarketResearchResult(
            market=request.market,
            request=request,
            readiness=readiness,
            status="insufficient",
            completeness="incomplete",
            limitations=("근사 자료는 strict PIT 전략에서 계산하지 않습니다.",),
            metrics={},
            input_hash=snapshot.input_hash,
            policy_hash=policy_hash,
            stage=request.stage,
            pilot_run_id=request.pilot_run_id,
            data_contract_hash=snapshot.data_contract_hash,
            warmup_sessions=(),
            research_grade=request.research_grade,
            pool_contract_hash=snapshot.pool_contract_hash,
        )
    if snapshot.market != request.market or readiness.market != request.market:
        return MarketResearchResult(
            market=request.market,
            request=request,
            readiness=readiness,
            status="insufficient",
            completeness="incomplete",
            limitations=("시장 식별자가 일치하지 않아 계산하지 않습니다.",),
            metrics={},
            input_hash=snapshot.input_hash,
            policy_hash=policy_hash,
            stage=request.stage,
            pilot_run_id=request.pilot_run_id,
            data_contract_hash=snapshot.data_contract_hash,
            warmup_sessions=(),
            research_grade=request.research_grade,
            pool_contract_hash=snapshot.pool_contract_hash,
        )
    sessions = _expected_sessions(calendar, request)
    expected_warmup = _expected_warmup_sessions(calendar, request)
    warmup = list(snapshot.warmup_sessions)
    warmup_missing: list[str] = []
    if request.stage in {"pilot", "final"} and (
        expected_warmup is None
        or len(warmup) != TWENTY
        or [item.local_date for item in expected_warmup] != warmup
    ):
        warmup = []
        warmup_missing.append("warmup:exactly20_completed_sessions")
    warmup_objects = [
        item for item in expected_warmup or [] if item.local_date in warmup
    ]
    all_sessions = warmup_objects + (sessions or [])
    complete, missing = _valid_coverage(
        snapshot,
        request,
        all_sessions,
        evaluation_start_index=len(warmup_objects),
        approximate=approximate,
    )
    missing.extend(warmup_missing)
    unsupported_actions = sorted({item.kind for item in snapshot.actions})
    if unsupported_actions:
        complete = False
        missing.extend(
            f"unsupported corporate action:{kind}" for kind in unsupported_actions
        )
    if not readiness.ready and not approximate:
        complete = False
        missing.append("readiness")
    if not complete or sessions is None:
        action_limitations = (
            (
                "지원하지 않는 기업행동이 있어 전체 연구를 보류합니다: "
                + ", ".join(unsupported_actions),
            )
            if unsupported_actions
            else ()
        )
        return MarketResearchResult(
            market=request.market,
            request=request,
            readiness=readiness,
            status="insufficient",
            completeness="incomplete",
            limitations=(
                "필수 PIT membership·일봉·기업행동·환율 자료가 모두 확인될 때까지 "
                "계산하지 않습니다.",
                *action_limitations,
                "이 결과는 capability readiness만 보여 주며 수익률을 만들지 않습니다.",
            ),
            metrics={},
            policy_hash=policy_hash,
            stage=request.stage,
            pilot_run_id=request.pilot_run_id,
            data_contract_hash=snapshot.data_contract_hash,
            warmup_sessions=tuple(warmup),
            research_grade=request.research_grade,
            pool_contract_hash=snapshot.pool_contract_hash,
        ).model_copy(update={"input_hash": snapshot.input_hash})

    bars_by_key = {(bar.symbol, bar.session): bar for bar in snapshot.bars}
    fx_by_date = {item.session: item for item in snapshot.fx}
    evidence: list[CandidateEvidence] = []
    trades: list[ResearchTrade] = []
    equity: list[ResearchEquityPoint] = []
    positions: dict[str, int] = {}
    if not sessions:
        raise ValueError("research requires at least one evaluation session")
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
    unsettled_sells: set[str] = set()
    below_sma: dict[str, int] = defaultdict(int)
    last_close: dict[str, Decimal] = {}
    last_mark_session: dict[str, date] = {}
    missing_held_bars = 0
    expected_candidate_bars = 0
    usable_candidate_bars = 0
    excluded_nonheld_bars = 0
    limitations: list[str] = []
    peak_nav = request.initial_cash_krw
    drawdown_latched = False

    for index, session in enumerate(all_sessions):
        is_evaluation = index >= len(warmup_objects)
        fx_observation = _fx_for(fx_by_date, session.local_date)
        if request.market == "US":
            if fx_observation is None:
                raise ValueError("US research requires an FX observation per session")
            fx = fx_observation.krw_per_usd
        else:
            fx = Decimal(1)
        # Fill all decisions made at the prior close at this session's open.
        for symbol, signal_session in sorted(pending_sells.items()):
            quantity = positions.get(symbol, 0)
            if quantity <= 0:
                continue
            bar = bars_by_key.get((symbol, session.local_date))
            if bar is None:
                if approximate:
                    unsettled_sells.add(symbol)
                    continue
                raise ValueError(f"missing exit bar: {symbol} {session.local_date}")
            positions.pop(symbol, None)
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
                bar = bars_by_key.get((pending.symbol, session.local_date))
                if bar is None:
                    if approximate:
                        continue
                    raise ValueError(
                        f"missing entry bar: {pending.symbol} {session.local_date}"
                    )
                signal_object = next(
                    item
                    for item in all_sessions
                    if item.local_date == pending.signal_session
                )
                signal_membership = next(
                    (
                        item
                        for item in snapshot.memberships
                        if item.symbol == pending.symbol
                        and item.instrument_type == "stock"
                        and item.is_valid_on(pending.signal_session)
                        and item.available_at <= signal_object.close_at
                    ),
                    None,
                )
                fill_day_memberships = tuple(
                    item
                    for item in snapshot.memberships
                    if item.symbol == pending.symbol
                    and item.instrument_type == "stock"
                    and item.valid_from == session.local_date
                )
                preopen_membership = next(
                    (
                        item
                        for item in fill_day_memberships
                        if item.available_at <= session.open_at
                        and item.is_valid_on(session.local_date)
                    ),
                    None,
                )
                has_preopen_fill_membership = any(
                    item.available_at <= session.open_at
                    for item in fill_day_memberships
                )
                membership = (
                    preopen_membership
                    if preopen_membership is not None
                    else (
                        None
                        if has_preopen_fill_membership
                        else (
                            signal_membership
                            if signal_membership is not None
                            and (
                                signal_membership.is_valid_on(session.local_date)
                                or (
                                    signal_membership.valid_from
                                    == signal_membership.valid_to
                                    == pending.signal_session
                                )
                            )
                            else None
                        )
                    )
                )
                if membership is None:
                    if approximate:
                        excluded_nonheld_bars += 1
                        limitations.append(
                            "진입일 membership 불충분으로 매수를 건너뜀: "
                            f"{pending.symbol}"
                        )
                        continue
                    raise ValueError(
                        "invalid entry membership: "
                        f"{pending.symbol} {session.local_date}"
                    )
                nav_native = cash_native + sum(
                    last_close.get(held, Decimal(0)) * quantity
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
                last_mark_session[pending.symbol] = session.local_date
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

        if not is_evaluation:
            continue

        decision_cutoff = (
            all_sessions[index + 1].open_at
            if index + 1 < len(all_sessions)
            else session.close_at
        )
        candidates = _rank_candidates(
            snapshot.memberships, bars_by_key, session, decision_cutoff
        )
        evidence.extend(candidates)
        if approximate:
            seen_symbols: set[str] = set()
            for membership in _eligible_memberships(snapshot.memberships, session):
                if membership.symbol in seen_symbols:
                    continue
                seen_symbols.add(membership.symbol)
                expected_candidate_bars += 1
                candidate_bar = bars_by_key.get((membership.symbol, session.local_date))
                if (
                    candidate_bar is not None
                    and candidate_bar.available_at >= session.close_at
                    and candidate_bar.available_at <= decision_cutoff
                ):
                    usable_candidate_bars += 1
                elif membership.symbol not in positions:
                    excluded_nonheld_bars += 1
        for symbol in list(positions):
            bar = bars_by_key.get((symbol, session.local_date))
            if bar is None:
                if approximate:
                    missing_held_bars += 1
                    held_from = last_mark_session.get(symbol)
                    age = 0
                    if held_from is not None:
                        age = sum(
                            item.local_date > held_from
                            for item in all_sessions[: index + 1]
                        )
                    limitations.append(
                        f"보유 종목 {symbol}은 {age}세션 전 마지막 가격으로 "
                        "평가합니다(추정값)."
                    )
                    continue
                raise ValueError(f"missing signal bar: {symbol} {session.local_date}")
            sma_window = [
                bars_by_key.get((symbol, prior_session.local_date))
                for prior_session in all_sessions[
                    max(0, index - TWENTY + 1) : index + 1
                ]
            ]
            sma_bars = [item for item in sma_window if item is not None]
            if len(sma_bars) == TWENTY:
                sma = sum((item.close for item in sma_bars), Decimal()) / TWENTY
                below_sma[symbol] = below_sma[symbol] + 1 if bar.close < sma else 0
                if below_sma[symbol] >= 2 and index + 1 < len(all_sessions):
                    pending_sells[symbol] = session.local_date
        for candidate in candidates:
            if candidate.rank > 20 or candidate.symbol in positions:
                continue
            membership = next(
                (
                    item
                    for item in snapshot.memberships
                    if item.symbol == candidate.symbol
                    and item.instrument_type == "stock"
                    and item.is_valid_on(session.local_date)
                ),
                None,
            )
            if membership is None:
                continue
            prior = [
                bars_by_key[(candidate.symbol, prior_session.local_date)]
                for prior_session in all_sessions[max(0, index - TWENTY) : index]
                if (approximate or membership.is_valid_on(prior_session.local_date))
                and (candidate.symbol, prior_session.local_date) in bars_by_key
            ]
            current = bars_by_key[(candidate.symbol, session.local_date)]
            if (
                len(prior) == TWENTY
                and current.close > max(item.close for item in prior)
                and current.volume
                > sum((item.volume for item in prior), Decimal()) / TWENTY
                and index + 1 < len(all_sessions)
                and not drawdown_latched
            ):
                pending_buys.append(
                    _PendingBuy(candidate.symbol, session.local_date, candidate.rank)
                )

        for symbol in positions:
            mark = bars_by_key.get((symbol, session.local_date))
            if mark is not None:
                last_close[symbol] = mark.close
                last_mark_session[symbol] = session.local_date
        invested_native = sum(
            last_close.get(symbol, Decimal(0)) * quantity
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
    if approximate:
        metrics.update(
            {
                "coverage_sessions": Decimal(len(equity)),
                "expected_candidate_bars": Decimal(expected_candidate_bars),
                "usable_candidate_bars": Decimal(usable_candidate_bars),
                "excluded_nonheld_bars": Decimal(excluded_nonheld_bars),
                "missing_held_bars": Decimal(missing_held_bars),
            }
        )
    unsettled = tuple(sorted(set(pending_sells) | unsettled_sells))
    if unsettled:
        return MarketResearchResult(
            market=request.market,
            request=request,
            readiness=readiness,
            status="insufficient",
            completeness="incomplete",
            candidate_evidence=tuple(evidence),
            trades=tuple(trades),
            equity=tuple(equity),
            limitations=(
                "마지막 거래일 이후 다음 거래일 시가 청산이 체결되지 않아 "
                "성과를 공개하지 않습니다.",
                "미청산 잔여 보유: " + ", ".join(unsettled),
                *limitations,
            ),
            metrics=(
                {
                    key: metrics[key]
                    for key in (
                        "coverage_sessions",
                        "expected_candidate_bars",
                        "usable_candidate_bars",
                        "excluded_nonheld_bars",
                        "missing_held_bars",
                    )
                    if key in metrics
                }
                if approximate
                else {}
            ),
            input_hash=snapshot.input_hash,
            policy_hash=policy_hash,
            stage=request.stage,
            pilot_run_id=request.pilot_run_id,
            data_contract_hash=snapshot.data_contract_hash,
            warmup_sessions=tuple(warmup),
            research_grade=request.research_grade,
            pool_contract_hash=snapshot.pool_contract_hash,
        )
    return MarketResearchResult(
        market=request.market,
        request=request,
        readiness=readiness,
        status="approximate" if approximate else "ready",
        completeness="approximate" if approximate else "complete",
        candidate_evidence=tuple(evidence),
        trades=tuple(trades),
        equity=tuple(equity),
        limitations=(
            "무료 근사 자료는 날짜별 표본·누락·생존편향 한계가 있어 "
            "실제 수익률이 아닙니다."
            if approximate
            else (
                "합성 자료는 인과 흐름 확인용이며 실제 수익률이나 주문 결과가 아닙니다."
                if readiness.simulated
                else "모의 연구 결과이며 실주문과 연결되지 않습니다."
            ),
            "낙폭 제한은 감지된 뒤 다음 거래일 시가에 청산하며 gap으로 20%를 "
            "초과할 수 있습니다.",
            *limitations,
        ),
        metrics=metrics,
        input_hash=snapshot.input_hash,
        policy_hash=policy_hash,
        stage=request.stage,
        pilot_run_id=request.pilot_run_id,
        data_contract_hash=snapshot.data_contract_hash,
        warmup_sessions=tuple(warmup),
        research_grade=request.research_grade,
        pool_contract_hash=snapshot.pool_contract_hash,
    )
