"""Offline, synthetic-fixture buy-and-hold accounting reference.

Callers assert complete frozen source coverage. Hash pins identify supplied evidence.
This pure module cannot authenticate a provider or establish historical PIT validity.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from fractions import Fraction
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


@dataclass(frozen=True)
class SellCostAssumptions:
    commission_kr: RateAssumption
    commission_us: RateAssumption
    slippage_kr: RateAssumption
    slippage_us: RateAssumption
    notional_tax_kr: RateAssumption
    notional_tax_us: RateAssumption
    tax_basis: Literal["notional"]


@dataclass(frozen=True)
class Sale:
    at: datetime
    instrument: Instrument
    quantity: Decimal
    raw_price: Decimal
    gross_local: Decimal
    commission_local: Decimal
    slippage_local: Decimal
    notional_tax_local: Decimal
    proceeds_local: Decimal
    pre_nav_krw: Decimal
    pre_leveraged_value_krw: Decimal
    post_nav_krw: Decimal
    post_leveraged_value_krw: Decimal


@dataclass(frozen=True)
class CapControlAttempt:
    observed_breach_at: datetime
    at: datetime
    status: Literal[
        "repaired", "partial_unresolved", "natural_recovery", "window_end_unfilled"
    ]
    pre_nav_krw: Decimal | None
    pre_leveraged_value_krw: Decimal | None
    post_nav_krw: Decimal | None
    post_leveraged_value_krw: Decimal | None


@dataclass(frozen=True)
class CapControlReference:
    status: Literal["reference_only"]
    trades: tuple[Trade, ...]
    dividends: tuple[DividendLedgerEntry, ...]
    points: tuple[ReferencePoint, ...]
    max_drawdown_fraction: Decimal
    leverage_breached: bool
    drawdown_breached: bool
    sales: tuple[Sale, ...]
    attempts: tuple[CapControlAttempt, ...]
    investment_qualification: Literal["not_evaluated"] = "not_evaluated"


@dataclass(frozen=True)
class TargetInstruction:
    instrument: Instrument
    decided_at: datetime
    target_weight: Decimal


@dataclass(frozen=True)
class TargetAttempt:
    at: datetime
    status: Literal[
        "filled", "zero_target", "one_share_unaffordable", "window_end_unfilled"
    ]


@dataclass(frozen=True)
class TargetBridgeReference:
    status: Literal["synthetic_reference_only"]
    trades: tuple[Trade, ...]
    dividends: tuple[DividendLedgerEntry, ...]
    points: tuple[ReferencePoint, ...]
    max_drawdown_fraction: Decimal
    leverage_breached: bool
    drawdown_breached: bool
    target_attempt: TargetAttempt
    investment_qualification: Literal["not_evaluated"] = "not_evaluated"


@dataclass(frozen=True)
class MultiTargetAttempt:
    instrument: Instrument
    at: datetime
    status: Literal["filled", "zero_target", "one_share_not_feasible"]
    target_weight: Decimal
    quantity: Decimal
    achieved_weight: Decimal
    shortfall_weight: Decimal


@dataclass(frozen=True)
class MultiTargetReference:
    status: Literal["synthetic_reference_only"]
    execution_status: Literal["filled", "no_feasible_share", "all_cash"]
    trades: tuple[Trade, ...]
    dividends: tuple[DividendLedgerEntry, ...]
    points: tuple[ReferencePoint, ...]
    max_drawdown_fraction: Decimal
    leverage_breached: bool
    drawdown_breached: bool
    target_attempts: tuple[MultiTargetAttempt, ...]
    investment_qualification: Literal["not_evaluated"] = "not_evaluated"


@dataclass(frozen=True)
class _BuyTerms:
    rate: Decimal
    commission: Decimal
    slippage: Decimal
    buy_tax: Decimal
    spread: Decimal
    unit_cost: Decimal


@dataclass(frozen=True)
class _BatchSizingLine:
    weight: Decimal
    unit_value: Decimal
    unit_cost: Decimal


def _size_initial_target_batch(
    nav: Decimal, cash: Decimal, lines: tuple[_BatchSizingLine, ...]
) -> tuple[Decimal, ...]:
    """Conservative simultaneous quantities; never redistribute residual cash."""
    _decimal(nav, "batch NAV", positive=True)
    _decimal(cash, "batch cash")
    upper: list[int] = []
    for line in lines:
        weight = _decimal(line.weight, "batch target weight")
        value = _decimal(line.unit_value, "batch unit value", positive=True)
        cost = _decimal(line.unit_cost, "batch unit cost", positive=True)
        if weight > LIMIT or cost < value:
            raise ReferenceInputError("batch sizing line violates target/cost bounds")
        upper.append(Fraction(weight) * Fraction(nav) // Fraction(value))
    nav_min = Fraction(nav) - sum(
        (
            quantity * (Fraction(line.unit_cost) - Fraction(line.unit_value))
            for quantity, line in zip(upper, lines, strict=True)
        ),
        Fraction(0),
    )
    if nav_min <= 0:
        raise ReferenceInputError("batch conservative NAV nonpositive")
    quantities = tuple(
        Fraction(line.weight) * nav_min // Fraction(line.unit_value) for line in lines
    )
    if any(q < 0 or q > upper[index] for index, q in enumerate(quantities)):
        raise ReferenceInputError("batch sizing arithmetic invalid")
    if sum(
        (
            q * Fraction(line.unit_cost)
            for q, line in zip(quantities, lines, strict=True)
        ),
        Fraction(0),
    ) > Fraction(cash):
        raise ReferenceInputError("shared_cash_insufficient")
    return tuple(Decimal(quantity) for quantity in quantities)


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


def _sell_rates(costs: SellCostAssumptions) -> None:
    if not isinstance(costs, SellCostAssumptions):
        raise ReferenceInputError("complete sell costs required")
    if costs.tax_basis != "notional":
        raise ReferenceInputError("unsupported sell tax basis")
    for name in (
        "commission_kr",
        "commission_us",
        "slippage_kr",
        "slippage_us",
        "notional_tax_kr",
        "notional_tax_us",
    ):
        item = getattr(costs, name)
        if (
            not isinstance(item, RateAssumption)
            or not isinstance(item.label, str)
            or not item.label.strip()
        ):
            raise ReferenceInputError(f"{name} needs explicit labelled assumption")
        _decimal(item.rate, name)
        if item.rate >= 1:
            raise ReferenceInputError(f"{name} rate must be below one")
        _hash(item.evidence_hash, name)
    for suffix in ("kr", "us"):
        total = sum(
            (
                getattr(costs, f"{kind}_{suffix}").rate
                for kind in ("commission", "slippage", "notional_tax")
            ),
            Decimal(0),
        )
        if total >= 1:
            raise ReferenceInputError(f"combined sell cost {suffix} must be below one")


def _sell_state(
    state: AccountingState, quantity: Decimal, proceeds: Decimal
) -> AccountingState:
    """Pure native-currency sale; existing dividend entitlements stay untouched."""
    holding = state.holdings[0]
    if (
        quantity <= 0
        or quantity > holding.quantity
        or quantity != quantity.to_integral_value()
    ):
        raise ReferenceInputError("invalid sale quantity")
    if not proceeds.is_finite() or proceeds < 0:
        raise ReferenceInputError("invalid sale proceeds")
    remaining = holding.quantity - quantity
    basis = holding.total_cost * remaining / holding.quantity
    return replace(
        state,
        holdings=(replace(holding, quantity=remaining, total_cost=basis),),
        cash=state.cash + proceeds,
    )


def _validate(
    data: FrozenReferenceInput, *, enforce_initial_allocation: bool = True
) -> None:
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
    if (
        enforce_initial_allocation
        and Decimal(sum(item.leveraged for item in data.cohort)) / len(data.cohort)
        > LIMIT
    ):
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


def _validate_target(data: FrozenReferenceInput, target: TargetInstruction) -> None:
    if not isinstance(target, TargetInstruction):
        raise ReferenceInputError("target instruction required")
    _instrument(target.instrument)
    if target.instrument not in data.cohort or target.instrument not in data.registered:
        raise ReferenceInputError("target registered identity mismatch")
    decided_at = _time(target.decided_at, "target decision")
    if not data.evaluation_start <= decided_at < data.evaluation_end:
        raise ReferenceInputError("target decision outside evaluation interval")
    weight = _decimal(target.target_weight, "target weight")
    if weight > LIMIT:
        raise ReferenceInputError("target weight exceeds symbol cap")


def _validate_multi_targets(
    data: FrozenReferenceInput, targets: tuple[TargetInstruction, ...]
) -> tuple[tuple[TargetInstruction, ...], datetime | None]:
    if not isinstance(targets, tuple) or len(targets) != len(data.cohort):
        raise ReferenceInputError("batch requires every cohort identity once")
    for target in targets:
        _validate_target(data, target)
    identities = [target.instrument for target in targets]
    if len(set(identities)) != len(identities) or set(identities) != set(data.cohort):
        raise ReferenceInputError("batch requires every cohort identity once")
    decisions = {_time(target.decided_at, "target decision") for target in targets}
    if len(decisions) != 1:
        raise ReferenceInputError("batch targets need one decision time")
    weights = sum((Fraction(target.target_weight) for target in targets), Fraction(0))
    leveraged = sum(
        (
            Fraction(target.target_weight)
            for target in targets
            if target.instrument.leveraged
        ),
        Fraction(0),
    )
    if weights > Fraction(Decimal("0.60")) or leveraged > Fraction(LIMIT):
        raise ReferenceInputError("batch gross or leveraged cap exceeded")
    ordered = tuple(
        sorted(
            targets,
            key=lambda target: (
                target.instrument.market,
                target.instrument.exchange,
                target.instrument.symbol,
                target.instrument.identity_hash,
            ),
        )
    )
    if weights == 0:
        return ordered, None
    if len({target.instrument.market for target in ordered}) != 1:
        raise ReferenceInputError("batch requires one currency")
    decision = next(iter(decisions))
    first_opens: set[datetime] = set()
    for target in ordered:
        future = [
            _time(bar.open_at, "official open")
            for bar in data.sessions
            if bar.instrument == target.instrument
            and _time(bar.open_at, "official open") > decision
        ]
        if not future:
            raise ReferenceInputError("batch missing next official open")
        first_opens.add(min(future))
    if len(first_opens) != 1:
        raise ReferenceInputError("batch first official opens differ")
    return ordered, next(iter(first_opens))


def _run_reference_core(
    data: FrozenReferenceInput,
    sell_costs: SellCostAssumptions | None = None,
    target: TargetInstruction | None = None,
    batch_targets: tuple[TargetInstruction, ...] | None = None,
) -> (
    BuyHoldReference
    | CapControlReference
    | TargetBridgeReference
    | MultiTargetReference
):
    """Apply frozen offline events; reject any missing or inconsistent fact."""
    if sum(x is not None for x in (sell_costs, target, batch_targets)) > 1:
        raise ReferenceInputError("reference modes cannot be combined")
    _validate(data, enforce_initial_allocation=target is None and batch_targets is None)
    if target is not None:
        _validate_target(data, target)
    ordered_batch: tuple[TargetInstruction, ...] = ()
    batch_open_at: datetime | None = None
    if batch_targets is not None:
        ordered_batch, batch_open_at = _validate_multi_targets(data, batch_targets)
    n = Decimal(len(data.cohort))
    budgets = {item: INITIAL_KRW / n for item in data.cohort}
    states: dict[Instrument, AccountingState] = {}
    krw_cash = INITIAL_KRW
    trades: list[Trade] = []
    dividends: list[DividendLedgerEntry] = []
    points: list[ReferencePoint] = []
    receivable_tax: dict[str, Decimal] = {}
    peak = INITIAL_KRW
    sales: list[Sale] = []
    attempts: list[CapControlAttempt] = []
    pending_since: datetime | None = None
    target_attempt: TargetAttempt | None = (
        TargetAttempt(target.decided_at, "zero_target")
        if target is not None and target.target_weight == 0
        else None
    )
    batch_attempts: list[MultiTargetAttempt] = []
    batch_executed = False

    def fx_at(at: datetime) -> Decimal:
        past = [
            item
            for item in data.fx
            if item.effective_at <= at and item.available_at <= at
        ]
        if not past:
            raise ReferenceInputError("historically available FX missing")
        return max(past, key=lambda x: (x.effective_at, x.available_at)).krw_per_usd

    def point(at: datetime, phase: str, *, record: bool = True) -> ReferencePoint:
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
        evaluated_peak = max(peak, nav)
        fraction = leverage / nav
        drawdown = (evaluated_peak - nav) / evaluated_peak
        result = ReferencePoint(
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
        if record:
            peak = evaluated_peak
            points.append(result)
        return result

    def settle_pending(evaluated: ReferencePoint) -> None:
        nonlocal pending_since
        if sell_costs is None:
            return
        if not evaluated.leverage_breach and pending_since is not None:
            attempts.append(
                CapControlAttempt(
                    pending_since,
                    evaluated.at,
                    "natural_recovery",
                    evaluated.nav_krw,
                    evaluated.leveraged_value_krw,
                    evaluated.nav_krw,
                    evaluated.leveraged_value_krw,
                )
            )
            pending_since = None
        elif evaluated.leverage_breach and pending_since is None:
            pending_since = evaluated.at

    def buy_terms(bar: RawSession, at: datetime) -> _BuyTerms:
        market = bar.instrument.market
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
            data.costs.buy_tax_us.rate if market == "US" else data.costs.buy_tax_kr.rate
        )
        spread = data.costs.fx_spread.rate if market == "US" else Decimal(0)
        unit_cost = (
            bar.raw_open * (1 + commission + slippage + buy_tax) * rate * (1 + spread)
        )
        return _BuyTerms(rate, commission, slippage, buy_tax, spread, unit_cost)

    def buy_at_open(
        bar: RawSession, at: datetime, quantity: Decimal, terms: _BuyTerms
    ) -> None:
        nonlocal krw_cash
        local_notional = quantity * bar.raw_open
        local_cost = local_notional * (
            1 + terms.commission + terms.slippage + terms.buy_tax
        )
        krw_cost = local_cost * terms.rate * (1 + terms.spread)
        krw_cash -= krw_cost
        if krw_cash < 0:
            raise ReferenceInputError("initial committed budgets exceed capital")
        currency: Currency = "USD" if bar.instrument.market == "US" else "KRW"
        states[bar.instrument] = AccountingState(
            holdings=(
                Holding(
                    bar.instrument.symbol,
                    quantity,
                    bar.raw_open,
                    local_cost,
                    currency,
                ),
            ),
            currency=currency,
        )
        trades.append(
            Trade(
                at,
                bar.instrument,
                quantity,
                bar.raw_open,
                local_notional,
                local_notional * terms.commission,
                local_notional * terms.slippage,
                local_notional * terms.buy_tax,
                local_cost * terms.rate * terms.spread,
                krw_cost,
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
    settle_pending(point(data.evaluation_start, "initial"))
    timestamp_phase = ""
    phase_names = ("split", "dividend_ex", "dividend_payment", "open", "close")
    opens_at: list[RawSession] = []
    target_open: RawSession | None = None
    for index, (at, phase_order, _, obj) in enumerate(events):
        if index == 0 or events[index - 1][0] != at:
            timestamp_phase = phase_names[phase_order]
            opens_at = []
            target_open = None
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
                if state is not None and state.holdings[0].quantity > 0:
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
                opens_at.append(obj)
                if (
                    target is not None
                    and target_attempt is None
                    and obj.instrument == target.instrument
                    and at > target.decided_at
                ):
                    target_open = obj
                if obj.instrument not in states:
                    if target is None and batch_targets is None:
                        terms = buy_terms(obj, at)
                        quantity = (
                            budgets[obj.instrument] / terms.unit_cost
                        ).to_integral_value(rounding=ROUND_FLOOR)
                        if quantity < 1:
                            raise ReferenceInputError(
                                "per-instrument budget cannot buy one share"
                            )
                        buy_at_open(obj, at, quantity, terms)
                else:
                    state = states[obj.instrument]
                    states[obj.instrument] = replace(
                        state,
                        holdings=(replace(state.holdings[0], raw_price=obj.raw_open),),
                    )
            else:
                state = states.get(obj.instrument)
                if state is not None:
                    states[obj.instrument] = replace(
                        state,
                        holdings=(replace(state.holdings[0], raw_price=obj.raw_close),),
                    )
        if (
            target is not None
            and target_open is not None
            and phase_order == 3
            and (index + 1 == len(events) or events[index + 1][:2] != (at, 3))
        ):
            before = point(at, "open", record=False)
            terms = buy_terms(target_open, at)
            effective_cost = (1 + terms.commission + terms.slippage + terms.buy_tax) * (
                1 + terms.spread
            ) - 1
            unit_value = target_open.raw_open * terms.rate
            denominator = unit_value * (1 + target.target_weight * effective_cost)
            if not denominator.is_finite() or denominator <= 0:
                raise ReferenceInputError("target sizing denominator invalid")
            desired = (
                target.target_weight * before.nav_krw / denominator
            ).to_integral_value(rounding=ROUND_FLOOR)
            affordable = (krw_cash / terms.unit_cost).to_integral_value(
                rounding=ROUND_FLOOR
            )
            quantity = min(desired, affordable)
            if quantity < 1:
                target_attempt = TargetAttempt(at, "one_share_unaffordable")
            else:
                buy_at_open(target_open, at, quantity, terms)
                after = point(at, "open", record=False)
                position = next(
                    x for x in after.positions if x.instrument == target.instrument
                )
                if (
                    position.value_krw / after.nav_krw > target.target_weight
                    or after.leveraged_fraction > LIMIT
                    or after.cash_krw < 0
                ):
                    raise ReferenceInputError("target purchase exceeds post-cost cap")
                target_attempt = TargetAttempt(at, "filled")
            target_open = None
        if (
            batch_open_at is not None
            and not batch_executed
            and at == batch_open_at
            and phase_order == 3
            and (index + 1 == len(events) or events[index + 1][:2] != (at, 3))
        ):
            bars = {bar.instrument: bar for bar in opens_at}
            if any(target_item.instrument not in bars for target_item in ordered_batch):
                raise ReferenceInputError("batch open mark missing")
            before = point(at, "open", record=False)
            if (
                before.positions
                or before.receivables_krw
                or before.receivables_usd
                or before.cash_usd
            ):
                raise ReferenceInputError("batch requires unheld initial capital")
            ordered_bars = tuple(
                bars[target_item.instrument] for target_item in ordered_batch
            )
            batch_terms = tuple(buy_terms(bar, at) for bar in ordered_bars)
            lines = tuple(
                _BatchSizingLine(
                    target_item.target_weight,
                    bar.raw_open * term.rate,
                    term.unit_cost,
                )
                for target_item, bar, term in zip(
                    ordered_batch, ordered_bars, batch_terms, strict=True
                )
            )
            for bar, term, line in zip(ordered_bars, batch_terms, lines, strict=True):
                _decimal(line.unit_value, "batch unit value", positive=True)
                _decimal(line.unit_cost, "batch unit cost", positive=True)
                exact_value = Fraction(bar.raw_open) * Fraction(term.rate)
                exact_cost = (
                    Fraction(bar.raw_open)
                    * (
                        1
                        + Fraction(term.commission)
                        + Fraction(term.slippage)
                        + Fraction(term.buy_tax)
                    )
                    * Fraction(term.rate)
                    * (1 + Fraction(term.spread))
                )
                if (
                    Fraction(line.unit_value) != exact_value
                    or Fraction(line.unit_cost) != exact_cost
                ):
                    raise ReferenceInputError("batch unit arithmetic rounded")
            quantities = _size_initial_target_batch(before.nav_krw, krw_cash, lines)
            exact_spend = sum(
                (
                    Fraction(quantity) * Fraction(line.unit_cost)
                    for quantity, line in zip(quantities, lines, strict=True)
                ),
                Fraction(0),
            )
            actual_spend = sum(
                (
                    (quantity * bar.raw_open)
                    * (1 + term.commission + term.slippage + term.buy_tax)
                    * term.rate
                    * (1 + term.spread)
                    for quantity, bar, term in zip(
                        quantities, ordered_bars, batch_terms, strict=True
                    )
                ),
                Decimal(0),
            )
            if not actual_spend.is_finite() or actual_spend > krw_cash:
                raise ReferenceInputError("shared_cash_insufficient")
            if Fraction(actual_spend) != exact_spend:
                raise ReferenceInputError("batch purchase arithmetic rounded")
            for quantity, bar, term in zip(
                quantities, ordered_bars, batch_terms, strict=True
            ):
                if quantity > 0:
                    buy_at_open(bar, at, quantity, term)
            expected_trade_costs = tuple(
                Fraction(quantity) * Fraction(line.unit_cost)
                for quantity, line in zip(quantities, lines, strict=True)
                if quantity > 0
            )
            if len(trades) != len(expected_trade_costs) or any(
                Fraction(trade.total_krw) != expected
                for trade, expected in zip(trades, expected_trade_costs, strict=True)
            ):
                raise ReferenceInputError("batch purchase arithmetic rounded")
            after = point(at, "open", record=False)
            if Fraction(krw_cash) != Fraction(before.cash_krw) - exact_spend:
                raise ReferenceInputError("batch purchase arithmetic rounded")
            exact_values = {
                target_item.instrument: Fraction(quantity) * Fraction(line.unit_value)
                for target_item, quantity, line in zip(
                    ordered_batch, quantities, lines, strict=True
                )
            }
            nav_exact = Fraction(krw_cash) + sum(exact_values.values(), Fraction(0))
            positions = {position.instrument: position for position in after.positions}
            if Fraction(after.nav_krw) != nav_exact or any(
                Fraction(position.value_krw) != exact_values[position.instrument]
                for position in after.positions
            ):
                raise ReferenceInputError("batch mark arithmetic rounded")
            if after.nav_krw > before.nav_krw:
                raise ReferenceInputError("batch purchase NAV arithmetic invalid")
            gross_exact = sum(
                (Fraction(position.value_krw) for position in after.positions),
                Fraction(0),
            )
            leveraged_exact = sum(
                (
                    Fraction(position.value_krw)
                    for position in after.positions
                    if position.instrument.leveraged
                ),
                Fraction(0),
            )
            if (
                gross_exact > Fraction(Decimal("0.60")) * nav_exact
                or leveraged_exact > Fraction(LIMIT) * nav_exact
                or krw_cash < 0
            ):
                raise ReferenceInputError("batch purchase exceeds post-cost caps")
            for target_item, quantity in zip(ordered_batch, quantities, strict=True):
                batch_position = positions.get(target_item.instrument)
                achieved = (
                    batch_position.value_krw / after.nav_krw
                    if batch_position is not None
                    else Decimal(0)
                )
                if (
                    batch_position is not None
                    and Fraction(batch_position.value_krw)
                    > Fraction(target_item.target_weight) * nav_exact
                ) or achieved > target_item.target_weight:
                    raise ReferenceInputError("batch purchase exceeds post-cost target")
                batch_attempts.append(
                    MultiTargetAttempt(
                        target_item.instrument,
                        at,
                        "zero_target"
                        if target_item.target_weight == 0
                        else ("filled" if quantity > 0 else "one_share_not_feasible"),
                        target_item.target_weight,
                        quantity,
                        achieved,
                        target_item.target_weight - achieved,
                    )
                )
            batch_executed = True
        if index + 1 == len(events) or events[index + 1][0] != at:
            if (
                sell_costs is not None
                and pending_since is not None
                and pending_since < at
            ):
                eligible = sorted(
                    (
                        bar
                        for bar in opens_at
                        if bar.instrument.leveraged
                        and bar.instrument in states
                        and states[bar.instrument].holdings[0].quantity > 0
                    ),
                    key=lambda bar: (
                        bar.instrument.market,
                        bar.instrument.exchange,
                        bar.instrument.symbol,
                        bar.instrument.identity_hash,
                    ),
                )
                if eligible:
                    before = point(at, timestamp_phase, record=False)
                    if not before.leverage_breach:
                        attempts.append(
                            CapControlAttempt(
                                pending_since,
                                at,
                                "natural_recovery",
                                before.nav_krw,
                                before.leveraged_value_krw,
                                before.nav_krw,
                                before.leveraged_value_krw,
                            )
                        )
                        pending_since = None
                    else:
                        for bar in eligible:
                            current = point(at, timestamp_phase, record=False)
                            if not current.leverage_breach:
                                break
                            instrument = bar.instrument
                            state = states[instrument]
                            holding = state.holdings[0]
                            suffix = "us" if instrument.market == "US" else "kr"
                            commission = getattr(
                                sell_costs, f"commission_{suffix}"
                            ).rate
                            slippage = getattr(sell_costs, f"slippage_{suffix}").rate
                            tax = getattr(sell_costs, f"notional_tax_{suffix}").rate
                            cost = commission + slippage + tax
                            fx = fx_at(at) if instrument.market == "US" else Decimal(1)
                            unit = bar.raw_open * fx
                            denominator = unit * (1 - LIMIT * cost)
                            if not denominator.is_finite() or denominator <= 0:
                                raise ReferenceInputError(
                                    "invalid sale sizing denominator"
                                )
                            needed = (
                                (current.leveraged_value_krw - LIMIT * current.nav_krw)
                                / denominator
                            ).to_integral_value(rounding=ROUND_CEILING)
                            quantity = min(needed, holding.quantity)
                            if (
                                quantity <= 0
                                or quantity != quantity.to_integral_value()
                            ):
                                raise ReferenceInputError(
                                    "invalid sale sizing quantity"
                                )
                            gross = quantity * bar.raw_open
                            proceeds = gross * (1 - cost)
                            if (
                                not gross.is_finite()
                                or not proceeds.is_finite()
                                or proceeds < 0
                            ):
                                raise ReferenceInputError("invalid sale arithmetic")
                            states[instrument] = _sell_state(state, quantity, proceeds)
                            after = point(at, timestamp_phase, record=False)
                            expected_nav = current.nav_krw - gross * fx * cost
                            expected_leverage = current.leveraged_value_krw - gross * fx
                            if (
                                after.nav_krw != expected_nav
                                or after.leveraged_value_krw != expected_leverage
                            ):
                                raise ReferenceInputError("sale accounting mismatch")
                            if quantity < holding.quantity and after.leverage_breach:
                                raise ReferenceInputError(
                                    "sale sizing did not repair cap"
                                )
                            one_less_exposure = (
                                current.leveraged_value_krw - (quantity - 1) * unit
                            )
                            one_less_nav = (
                                current.nav_krw - (quantity - 1) * unit * cost
                            )
                            if one_less_exposure <= LIMIT * one_less_nav:
                                raise ReferenceInputError(
                                    "sale quantity is not minimum"
                                )
                            sales.append(
                                Sale(
                                    at,
                                    instrument,
                                    quantity,
                                    bar.raw_open,
                                    gross,
                                    gross * commission,
                                    gross * slippage,
                                    gross * tax,
                                    proceeds,
                                    current.nav_krw,
                                    current.leveraged_value_krw,
                                    after.nav_krw,
                                    after.leveraged_value_krw,
                                )
                            )
                        after = point(at, timestamp_phase, record=False)
                        attempt_status: Literal[
                            "repaired",
                            "partial_unresolved",
                            "natural_recovery",
                            "window_end_unfilled",
                        ] = (
                            "partial_unresolved"
                            if after.leverage_breach
                            else "repaired"
                        )
                        attempts.append(
                            CapControlAttempt(
                                pending_since,
                                at,
                                attempt_status,
                                before.nav_krw,
                                before.leveraged_value_krw,
                                after.nav_krw,
                                after.leveraged_value_krw,
                            )
                        )
                        if not after.leverage_breach:
                            pending_since = None
            settle_pending(point(at, timestamp_phase))
    if target is None and batch_targets is None and len(trades) != len(data.cohort):
        raise ReferenceInputError("not every cohort instrument was purchased")
    if batch_open_at is not None and not batch_executed:
        raise ReferenceInputError("batch first official open not executed")
    settle_pending(point(data.evaluation_end, "evaluation_end"))
    if sell_costs is not None and pending_since is not None:
        last = points[-1]
        attempts.append(
            CapControlAttempt(
                pending_since,
                data.evaluation_end,
                "window_end_unfilled",
                last.nav_krw,
                last.leveraged_value_krw,
                last.nav_krw,
                last.leveraged_value_krw,
            )
        )
    result_status: Literal["reference_only"] = "reference_only"
    common = (
        result_status,
        tuple(trades),
        tuple(dividends),
        tuple(points),
        max(x.drawdown_fraction for x in points),
        any(x.leverage_breach for x in points),
        any(x.drawdown_breach for x in points),
    )
    if batch_targets is not None:
        if batch_open_at is None:
            batch_attempts = [
                MultiTargetAttempt(
                    target_item.instrument,
                    target_item.decided_at,
                    "zero_target",
                    Decimal(0),
                    Decimal(0),
                    Decimal(0),
                    Decimal(0),
                )
                for target_item in ordered_batch
            ]
        return MultiTargetReference(
            "synthetic_reference_only",
            "all_cash"
            if batch_open_at is None
            else ("filled" if trades else "no_feasible_share"),
            tuple(trades),
            tuple(dividends),
            tuple(points),
            common[4],
            common[5],
            common[6],
            tuple(batch_attempts),
        )
    if target is not None:
        if target_attempt is None:
            target_attempt = TargetAttempt(data.evaluation_end, "window_end_unfilled")
        return TargetBridgeReference(
            "synthetic_reference_only",
            tuple(trades),
            tuple(dividends),
            tuple(points),
            common[4],
            common[5],
            common[6],
            target_attempt,
        )
    if sell_costs is None:
        return BuyHoldReference(*common)
    return CapControlReference(*common, tuple(sales), tuple(attempts))


def run_buy_hold_reference(data: FrozenReferenceInput) -> BuyHoldReference:
    """Apply frozen offline events; reject any missing or inconsistent fact."""
    result = _run_reference_core(data)
    assert isinstance(result, BuyHoldReference)
    return result


def run_cap_control_reference(
    data: FrozenReferenceInput, sell_costs: SellCostAssumptions
) -> CapControlReference:
    """Evaluate synthetic cap repair at later official opens."""
    _sell_rates(sell_costs)
    result = _run_reference_core(data, sell_costs)
    assert isinstance(result, CapControlReference)
    return result


def run_target_bridge_reference(
    data: FrozenReferenceInput, target: TargetInstruction
) -> TargetBridgeReference:
    """Inject one synthetic initial target into the shared raw accounting core."""
    result = _run_reference_core(data, target=target)
    assert isinstance(result, TargetBridgeReference)
    return result


def run_multi_target_reference(
    data: FrozenReferenceInput, targets: tuple[TargetInstruction, ...]
) -> MultiTargetReference:
    """Buy one synthetic all-cohort target vector at one shared next open."""
    result = _run_reference_core(data, batch_targets=targets)
    assert isinstance(result, MultiTargetReference)
    return result
