"""Offline, synthetic-fixture buy-and-hold accounting reference.

Callers assert complete frozen source coverage. Hash pins identify supplied evidence.
This pure module cannot authenticate a provider or establish historical PIT validity.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import ROUND_FLOOR, Decimal
from typing import Literal

from jusik.market_history_action_accounting import (
    AccountingState,
    DividendAction,
    Holding,
    SplitAction,
    accrue_dividend,
    apply_split,
    pay_dividend,
)

Market = Literal["KR", "US"]
Currency = Literal["KRW", "USD"]
INITIAL_KRW = Decimal(100000000)
LIMIT = Decimal("0.20")


class ReferenceInputError(ValueError):
    """Incomplete or inconsistent frozen reference input."""


@dataclass(frozen=True)
class Instrument:
    market: Market
    exchange: str
    symbol: str
    identity_hash: str
    leveraged: bool


@dataclass(frozen=True)
class RawSession:
    instrument: Instrument
    open_at: datetime
    close_at: datetime
    raw_open: Decimal
    raw_close: Decimal
    open_observed_at: datetime
    close_observed_at: datetime
    price_basis: Literal["raw", "adjusted", "unknown"] = "raw"


@dataclass(frozen=True)
class FXObservation:
    effective_at: datetime
    available_at: datetime
    krw_per_usd: Decimal


@dataclass(frozen=True)
class RateAssumption:
    rate: Decimal
    label: str
    evidence_hash: str


@dataclass(frozen=True)
class CostAssumptions:
    commission_kr: RateAssumption
    commission_us: RateAssumption
    slippage_kr: RateAssumption
    slippage_us: RateAssumption
    buy_tax_kr: RateAssumption
    buy_tax_us: RateAssumption
    fx_spread: RateAssumption
    withholding_kr: RateAssumption
    withholding_us: RateAssumption


@dataclass(frozen=True)
class SplitEvent:
    instrument: Instrument
    action_id: str
    effective_at: datetime
    observed_at: datetime
    ratio: Decimal
    evidence_hash: str


@dataclass(frozen=True)
class DividendEvent:
    instrument: Instrument
    action_id: str
    ex_at: datetime
    payment_at: datetime
    observed_at: datetime
    gross_per_share: Decimal
    taxable_per_share: Decimal
    evidence_hash: str


@dataclass(frozen=True)
class FrozenReferenceInput:
    registration_revision: int
    registration_hash: str
    registered: tuple[Instrument, ...]
    cohort: tuple[Instrument, ...]
    cohort_label: str
    evaluation_start: datetime
    evaluation_end: datetime
    sessions: tuple[RawSession, ...]
    official_calendar_hash: str
    official_calendar_complete: bool
    price_evidence_hash: str
    price_coverage_complete: bool
    actions: tuple[SplitEvent | DividendEvent, ...]
    action_evidence_hash: str
    action_coverage_complete: bool
    fx: tuple[FXObservation, ...]
    fx_evidence_hash: str
    fx_coverage_complete: bool
    costs: CostAssumptions


@dataclass(frozen=True)
class Trade:
    at: datetime
    instrument: Instrument
    quantity: Decimal
    raw_price: Decimal
    notional_local: Decimal
    commission_local: Decimal
    slippage_local: Decimal
    buy_tax_local: Decimal
    fx_spread_krw: Decimal
    total_krw: Decimal


@dataclass(frozen=True)
class DividendLedgerEntry:
    action_id: str
    instrument: Instrument
    at: datetime
    phase: Literal["accrual", "payment"]
    quantity: Decimal
    gross_local: Decimal
    taxable_local: Decimal
    withholding_local: Decimal
    net_local: Decimal


@dataclass(frozen=True)
class Position:
    instrument: Instrument
    quantity: Decimal
    raw_price: Decimal
    value_krw: Decimal


@dataclass(frozen=True)
class ReferencePoint:
    at: datetime
    phase: str
    cash_krw: Decimal
    cash_usd: Decimal
    positions: tuple[Position, ...]
    receivables_krw: Decimal
    receivables_usd: Decimal
    nav_krw: Decimal
    leveraged_value_krw: Decimal
    leveraged_fraction: Decimal
    leverage_breach: bool
    drawdown_fraction: Decimal
    drawdown_breach: bool


@dataclass(frozen=True)
class BuyHoldReference:
    status: Literal["reference_only"]
    trades: tuple[Trade, ...]
    dividends: tuple[DividendLedgerEntry, ...]
    points: tuple[ReferencePoint, ...]
    max_drawdown_fraction: Decimal
    leverage_breached: bool
    drawdown_breached: bool
    investment_qualification: Literal["not_evaluated"] = "not_evaluated"


def _decimal(value: Decimal, label: str, *, positive: bool = False) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ReferenceInputError(f"{label} must be finite Decimal")
    if value <= 0 if positive else value < 0:
        raise ReferenceInputError(
            f"{label} must be {'positive' if positive else 'nonnegative'}"
        )
    return value


def _time(value: datetime, label: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ReferenceInputError(f"{label} must have timezone")
    return value.astimezone(UTC)


def _hash(value: str, label: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(c not in "0123456789abcdef" for c in value)
    ):
        raise ReferenceInputError(f"{label} must be lowercase SHA-256 pin")


def _instrument(value: Instrument) -> None:
    if not isinstance(value, Instrument):
        raise ReferenceInputError("instrument is invalid")
    if (
        (value.market == "KR" and value.exchange != "KRX")
        or (value.market == "US" and value.exchange not in {"NAS", "NYS", "AMS"})
        or value.market not in {"KR", "US"}
        or not value.symbol
    ):
        raise ReferenceInputError("instrument market/exchange/symbol invalid")
    if type(value.leveraged) is not bool:
        raise ReferenceInputError("leveraged taxonomy must be explicit bool")
    _hash(value.identity_hash, "instrument identity")


def _rates(costs: CostAssumptions) -> None:
    if not isinstance(costs, CostAssumptions):
        raise ReferenceInputError("complete costs required")
    for name in costs.__dataclass_fields__:
        item = getattr(costs, name)
        if not isinstance(item, RateAssumption) or not item.label.strip():
            raise ReferenceInputError(f"{name} needs explicit labelled assumption")
        _decimal(item.rate, name)
        if item.rate >= 1:
            raise ReferenceInputError(f"{name} rate must be below one")
        _hash(item.evidence_hash, name)


def _validate(data: FrozenReferenceInput) -> None:
    if type(data.registration_revision) is not int or data.registration_revision < 1:
        raise ReferenceInputError("registration revision required")
    for name in (
        "registration_hash",
        "official_calendar_hash",
        "price_evidence_hash",
        "action_evidence_hash",
        "fx_evidence_hash",
    ):
        _hash(getattr(data, name), name)
    for name in (
        "official_calendar_complete",
        "price_coverage_complete",
        "action_coverage_complete",
        "fx_coverage_complete",
    ):
        if getattr(data, name) is not True:
            raise ReferenceInputError(f"{name} must be explicitly true")
    if not data.cohort_label.strip():
        raise ReferenceInputError("cohort label required")
    start = _time(data.evaluation_start, "evaluation start")
    end = _time(data.evaluation_end, "evaluation end")
    if start >= end:
        raise ReferenceInputError("evaluation interval invalid")
    if not data.registered or not data.cohort:
        raise ReferenceInputError("registered list and cohort required")
    for item in data.registered + data.cohort:
        _instrument(item)
    keys = [(x.market, x.exchange, x.symbol) for x in data.registered]
    if len(keys) != len(set(keys)) or len(data.cohort) != len(set(data.cohort)):
        raise ReferenceInputError("duplicate registered/cohort identity")
    if not set(data.cohort).issubset(set(data.registered)):
        raise ReferenceInputError("cohort must be registered identity subset")
    if Decimal(sum(item.leveraged for item in data.cohort)) / len(data.cohort) > LIMIT:
        raise ReferenceInputError(
            "initial equal cohort allocation exceeds leverage cap"
        )
    _rates(data.costs)
    seen: set[tuple[Instrument, datetime]] = set()
    for bar in data.sessions:
        op = _time(bar.open_at, "official open")
        cl = _time(bar.close_at, "official close")
        if bar.instrument not in data.cohort or not start <= op < cl <= end:
            raise ReferenceInputError("session outside cohort/evaluation")
        if (bar.instrument, op) in seen:
            raise ReferenceInputError("duplicate official session")
        seen.add((bar.instrument, op))
        if bar.price_basis != "raw":
            raise ReferenceInputError("execution and marks require raw prices")
        _decimal(bar.raw_open, "raw open", positive=True)
        _decimal(bar.raw_close, "raw close", positive=True)
        if (
            _time(bar.open_observed_at, "open observation") > op
            or _time(bar.close_observed_at, "close observation") > cl
        ):
            raise ReferenceInputError("future price observation")
    for item in data.cohort:
        bars = sorted(
            (b for b in data.sessions if b.instrument == item), key=lambda b: b.open_at
        )
        if not bars:
            raise ReferenceInputError("missing cohort sessions")
        if any(a.close_at >= b.open_at for a, b in zip(bars, bars[1:])):
            raise ReferenceInputError("overlapping official sessions")
    fx_times: set[datetime] = set()
    for fx in data.fx:
        at = _time(fx.available_at, "FX availability")
        effective = _time(fx.effective_at, "FX effective time")
        if effective > at:
            raise ReferenceInputError("FX observation precedes effective time")
        if at in fx_times:
            raise ReferenceInputError("duplicate FX observation")
        fx_times.add(at)
        _decimal(fx.krw_per_usd, "KRW/USD", positive=True)
    action_ids: set[str] = set()
    for action in data.actions:
        if (
            action.instrument not in data.cohort
            or not action.action_id
            or action.action_id in action_ids
        ):
            raise ReferenceInputError("action identity duplicate or outside cohort")
        action_ids.add(action.action_id)
        _hash(action.evidence_hash, "action evidence")
        at = _time(
            action.effective_at if isinstance(action, SplitEvent) else action.ex_at,
            "action effective time",
        )
        if (
            not start <= at <= end
            or _time(action.observed_at, "action observation") > at
        ):
            raise ReferenceInputError("future or out-of-window action")
        if not any(
            bar.instrument == action.instrument and bar.open_at == at
            for bar in data.sessions
        ):
            raise ReferenceInputError("split/ex must use official instrument open")
        if isinstance(action, SplitEvent):
            _decimal(action.ratio, "split ratio", positive=True)
        else:
            if _time(action.payment_at, "dividend payment") < at:
                raise ReferenceInputError("payment before ex date")
            _decimal(action.gross_per_share, "gross dividend", positive=True)
            _decimal(action.taxable_per_share, "taxable dividend")
            if action.taxable_per_share > action.gross_per_share:
                raise ReferenceInputError("taxable dividend exceeds gross")


def run_buy_hold_reference(data: FrozenReferenceInput) -> BuyHoldReference:
    """Apply frozen offline events; reject any missing or inconsistent fact."""
    _validate(data)
    n = Decimal(len(data.cohort))
    budgets = {item: INITIAL_KRW / n for item in data.cohort}
    states: dict[Instrument, AccountingState] = {}
    krw_cash = INITIAL_KRW
    trades: list[Trade] = []
    dividends: list[DividendLedgerEntry] = []
    points: list[ReferencePoint] = []
    receivable_tax: dict[str, Decimal] = {}
    peak = INITIAL_KRW

    def fx_at(at: datetime) -> Decimal:
        past = [
            item
            for item in data.fx
            if item.effective_at <= at and item.available_at <= at
        ]
        if not past:
            raise ReferenceInputError("historically available FX missing")
        return max(past, key=lambda x: (x.effective_at, x.available_at)).krw_per_usd

    def point(at: datetime, phase: str) -> None:
        nonlocal peak
        usd_needed = any(item.market == "US" for item in states)
        rate = fx_at(at) if usd_needed else Decimal(1)
        positions: list[Position] = []
        kr_rec = Decimal(0)
        us_rec = Decimal(0)
        kr_cash_local = Decimal(0)
        us_cash = Decimal(0)
        leverage = Decimal(0)
        for instrument, state in states.items():
            conversion = rate if instrument.market == "US" else Decimal(1)
            holding = state.holdings[0]
            value = holding.quantity * holding.raw_price * conversion
            positions.append(
                Position(instrument, holding.quantity, holding.raw_price, value)
            )
            if instrument.leveraged:
                leverage += value
            if instrument.market == "US":
                us_cash += state.cash
            else:
                kr_cash_local += state.cash
            for receipt in state.receivables:
                net = receipt.gross_amount - receivable_tax[receipt.action_id]
                if instrument.market == "US":
                    us_rec += net
                else:
                    kr_rec += net
        total_krw_cash = krw_cash + kr_cash_local
        nav = (
            total_krw_cash
            + kr_rec
            + (us_cash + us_rec) * rate
            + sum((x.value_krw for x in positions), Decimal(0))
        )
        if nav <= 0:
            raise ReferenceInputError("NAV nonpositive")
        peak = max(peak, nav)
        fraction = leverage / nav
        drawdown = (peak - nav) / peak
        points.append(
            ReferencePoint(
                at,
                phase,
                total_krw_cash,
                us_cash,
                tuple(
                    sorted(
                        positions,
                        key=lambda x: (
                            x.instrument.market,
                            x.instrument.exchange,
                            x.instrument.symbol,
                        ),
                    )
                ),
                kr_rec,
                us_rec,
                nav,
                leverage,
                fraction,
                fraction > LIMIT,
                drawdown,
                drawdown > LIMIT,
            )
        )

    events: list[tuple[datetime, int, str, object]] = []
    for action in data.actions:
        if isinstance(action, SplitEvent):
            events.append((action.effective_at, 0, action.action_id, action))
        else:
            events.append((action.ex_at, 1, action.action_id, action))
            if action.payment_at <= data.evaluation_end:
                events.append((action.payment_at, 2, action.action_id, action))
    for bar in data.sessions:
        events.extend(
            (
                (bar.open_at, 3, bar.instrument.symbol, bar),
                (bar.close_at, 4, bar.instrument.symbol, bar),
            )
        )
    events.sort(key=lambda x: (x[0], x[1], x[2]))
    point(data.evaluation_start, "initial")
    timestamp_phase = ""
    phase_names = ("split", "dividend_ex", "dividend_payment", "open", "close")
    for index, (at, phase_order, _, obj) in enumerate(events):
        if index == 0 or events[index - 1][0] != at:
            timestamp_phase = phase_names[phase_order]
        if isinstance(obj, SplitEvent):
            state = states.get(obj.instrument)
            if state is not None:
                previous = state.holdings[0]
                result = apply_split(
                    state,
                    SplitAction(
                        obj.action_id,
                        obj.instrument.symbol,
                        obj.effective_at,
                        obj.ratio,
                        "USD" if obj.instrument.market == "US" else "KRW",
                        "raw",
                        previous.raw_price,
                        previous.raw_price / obj.ratio,
                    ),
                    at=at,
                )
                if result.status != "applied":
                    raise ReferenceInputError(f"split rejected: {result.reason}")
                if (
                    result.state.holdings[0].quantity
                    != result.state.holdings[0].quantity.to_integral_value()
                ):
                    raise ReferenceInputError(
                        "fractional split requires cash-in-lieu rule"
                    )
                states[obj.instrument] = result.state
        elif isinstance(obj, DividendEvent):
            state = states.get(obj.instrument)
            if phase_order == 1:
                if state is not None:
                    qty = state.holdings[0].quantity
                    taxable = qty * obj.taxable_per_share
                    tax_rate = (
                        data.costs.withholding_us.rate
                        if obj.instrument.market == "US"
                        else data.costs.withholding_kr.rate
                    )
                    tax = taxable * tax_rate
                    engine_action = DividendAction(
                        obj.action_id,
                        obj.instrument.symbol,
                        obj.ex_at,
                        obj.payment_at,
                        obj.gross_per_share,
                        "USD" if obj.instrument.market == "US" else "KRW",
                        qty,
                        True,
                        "raw",
                    )
                    result = accrue_dividend(state, engine_action, at=at)
                    if result.status != "applied":
                        raise ReferenceInputError(
                            f"dividend accrual rejected: {result.reason}"
                        )
                    states[obj.instrument] = result.state
                    receivable_tax[obj.action_id] = tax
                    gross = qty * obj.gross_per_share
                    dividends.append(
                        DividendLedgerEntry(
                            obj.action_id,
                            obj.instrument,
                            at,
                            "accrual",
                            qty,
                            gross,
                            taxable,
                            tax,
                            gross - tax,
                        )
                    )
            else:
                if obj.action_id in receivable_tax:
                    assert state is not None
                    receipt = next(
                        x for x in state.receivables if x.action_id == obj.action_id
                    )
                    engine_action = DividendAction(
                        obj.action_id,
                        obj.instrument.symbol,
                        obj.ex_at,
                        obj.payment_at,
                        obj.gross_per_share,
                        "USD" if obj.instrument.market == "US" else "KRW",
                        receipt.entitled_quantity,
                        True,
                        "raw",
                    )
                    result = pay_dividend(state, engine_action, at=at)
                    if result.status != "applied":
                        raise ReferenceInputError(
                            f"dividend payment rejected: {result.reason}"
                        )
                    tax = receivable_tax.pop(obj.action_id)
                    states[obj.instrument] = replace(
                        result.state, cash=result.state.cash - tax
                    )
                    gross = receipt.gross_amount
                    taxable = receipt.entitled_quantity * obj.taxable_per_share
                    dividends.append(
                        DividendLedgerEntry(
                            obj.action_id,
                            obj.instrument,
                            at,
                            "payment",
                            receipt.entitled_quantity,
                            gross,
                            taxable,
                            tax,
                            gross - tax,
                        )
                    )
        elif isinstance(obj, RawSession):
            if phase_order == 3:
                if obj.instrument not in states:
                    market = obj.instrument.market
                    rate = fx_at(at) if market == "US" else Decimal(1)
                    commission = (
                        data.costs.commission_us.rate
                        if market == "US"
                        else data.costs.commission_kr.rate
                    )
                    slippage = (
                        data.costs.slippage_us.rate
                        if market == "US"
                        else data.costs.slippage_kr.rate
                    )
                    buy_tax = (
                        data.costs.buy_tax_us.rate
                        if market == "US"
                        else data.costs.buy_tax_kr.rate
                    )
                    spread = data.costs.fx_spread.rate if market == "US" else Decimal(0)
                    unit_cost = (
                        obj.raw_open
                        * (1 + commission + slippage + buy_tax)
                        * rate
                        * (1 + spread)
                    )
                    quantity = (budgets[obj.instrument] / unit_cost).to_integral_value(
                        rounding=ROUND_FLOOR
                    )
                    if quantity < 1:
                        raise ReferenceInputError(
                            "per-instrument budget cannot buy one share"
                        )
                    local_notional = quantity * obj.raw_open
                    local_cost = local_notional * (1 + commission + slippage + buy_tax)
                    krw_cost = local_cost * rate * (1 + spread)
                    krw_cash -= krw_cost
                    if krw_cash < 0:
                        raise ReferenceInputError(
                            "initial committed budgets exceed capital"
                        )
                    currency: Currency = "USD" if market == "US" else "KRW"
                    states[obj.instrument] = AccountingState(
                        holdings=(
                            Holding(
                                obj.instrument.symbol,
                                quantity,
                                obj.raw_open,
                                local_cost,
                                currency,
                            ),
                        ),
                        currency=currency,
                    )
                    trades.append(
                        Trade(
                            at,
                            obj.instrument,
                            quantity,
                            obj.raw_open,
                            local_notional,
                            local_notional * commission,
                            local_notional * slippage,
                            local_notional * buy_tax,
                            local_cost * rate * spread,
                            krw_cost,
                        )
                    )
                else:
                    state = states[obj.instrument]
                    states[obj.instrument] = replace(
                        state,
                        holdings=(replace(state.holdings[0], raw_price=obj.raw_open),),
                    )
            else:
                state = states[obj.instrument]
                states[obj.instrument] = replace(
                    state,
                    holdings=(replace(state.holdings[0], raw_price=obj.raw_close),),
                )
        if index + 1 == len(events) or events[index + 1][0] != at:
            point(at, timestamp_phase)
    if len(trades) != len(data.cohort):
        raise ReferenceInputError("not every cohort instrument was purchased")
    point(data.evaluation_end, "evaluation_end")
    return BuyHoldReference(
        "reference_only",
        tuple(trades),
        tuple(dividends),
        tuple(points),
        max(x.drawdown_fraction for x in points),
        any(x.leverage_breach for x in points),
        any(x.drawdown_breach for x in points),
    )
