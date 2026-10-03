"""Offline, synthetic-fixture buy-and-hold accounting reference.

Callers assert complete frozen source coverage. Hash pins identify supplied evidence.
This pure module cannot authenticate a provider or establish historical PIT validity.
"""

from __future__ import annotations

from collections.abc import Callable
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
class HoldQuantityInstruction:
    instrument: Instrument
    decided_at: datetime
    target_weight: Decimal
    quantity: Decimal


KRInstruction = TargetInstruction | HoldQuantityInstruction


@dataclass(frozen=True)
class KRPolicyDirective:
    """One dynamic policy decision in the existing KR raw event loop."""

    vector: tuple[KRInstruction, ...] | None = None
    cancel_pending: bool = False
    liquidation: bool = False


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
class RebalanceBatch:
    decided_at: datetime
    open_at: datetime
    status: Literal["filled", "unchanged", "all_cash", "no_feasible_share"]
    sold: tuple[tuple[Instrument, Decimal], ...]
    bought: tuple[tuple[Instrument, Decimal], ...]


@dataclass(frozen=True)
class KRTargetSequenceReference:
    status: Literal["synthetic_reference_only"]
    trades: tuple[Trade, ...]
    sales: tuple[Sale, ...]
    dividends: tuple[DividendLedgerEntry, ...]
    points: tuple[ReferencePoint, ...]
    batches: tuple[RebalanceBatch, ...]
    max_drawdown_fraction: Decimal
    leverage_breached: bool
    drawdown_breached: bool
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


@dataclass(frozen=True)
class _RebalanceLine:
    weight: Decimal | None
    held: Decimal
    unit_value: Decimal
    unit_buy_cost: Decimal
    unit_sell_proceeds: Decimal
    hold_quantity: Decimal | None = None


def _ceil_fraction(value: Fraction) -> int:
    return -(-value.numerator // value.denominator)


def _policy_cap_sell_quantity(
    nav: Decimal,
    gross: Decimal,
    leverage: Decimal,
    owned_value: Decimal,
    unit_price: Decimal,
    sell_cost: Decimal,
    owned_quantity: Decimal,
    *,
    leveraged: bool,
) -> Decimal:
    """Minimum bounded integer sale for all three post-cost hard caps."""
    n, g, lev = Fraction(nav), Fraction(gross), Fraction(leverage)
    own, price, cost = Fraction(owned_value), Fraction(unit_price), Fraction(sell_cost)
    limits = (
        (own - Fraction(LIMIT) * n, Fraction(LIMIT)),
        (g - Fraction(Decimal("0.60")) * n, Fraction(Decimal("0.60"))),
        (lev - Fraction(LIMIT) * n, Fraction(LIMIT))
        if leveraged
        else (Fraction(0), Fraction(LIMIT)),
    )
    needed = max(
        (
            _ceil_fraction(excess / (price * (1 - limit * cost)))
            for excess, limit in limits
            if excess > 0
        ),
        default=0,
    )
    return Decimal(min(needed, int(owned_quantity)))


def _size_kr_rebalance(
    nav: Decimal, cash: Decimal, lines: tuple[_RebalanceLine, ...]
) -> tuple[tuple[Decimal, ...], tuple[Decimal, ...]]:
    """Bounded conservative simultaneous sells, then proportional shared-cash buys."""
    _decimal(nav, "rebalance NAV", positive=True)
    _decimal(cash, "rebalance cash")
    n, k = Fraction(nav), Fraction(cash)
    values: list[Fraction] = []
    buy_costs: list[Fraction] = []
    proceeds: list[Fraction] = []
    weights: list[Fraction | None] = []
    held: list[int] = []
    upper: list[int] = []
    for line in lines:
        h = _decimal(line.held, "rebalance held quantity")
        v = Fraction(_decimal(line.unit_value, "rebalance unit value", positive=True))
        c = Fraction(_decimal(line.unit_buy_cost, "rebalance buy cost", positive=True))
        p = Fraction(_decimal(line.unit_sell_proceeds, "rebalance sell proceeds"))
        if h != h.to_integral_value() or c < v or p > v:
            raise ReferenceInputError("rebalance sizing line invalid")
        if line.hold_quantity is not None:
            if line.weight is not None:
                raise ReferenceInputError("hold quantity cannot carry sizing weight")
            held_at_decision = _decimal(line.hold_quantity, "hold quantity")
            if held_at_decision != held_at_decision.to_integral_value():
                raise ReferenceInputError("hold quantity must be integral")
            w: Fraction | None = None
        else:
            if line.weight is None:
                raise ReferenceInputError("rebalance target weight required")
            w = Fraction(_decimal(line.weight, "rebalance target weight"))
            if w > Fraction(LIMIT):
                raise ReferenceInputError("rebalance target weight exceeds cap")
        values.append(v)
        buy_costs.append(c)
        proceeds.append(p)
        weights.append(w)
        held.append(int(h))
        upper.append(0 if w is None else max(0, (w * n - int(h) * v) // v))
    n_base = n - sum(
        (upper[i] * (buy_costs[i] - values[i]) for i in range(len(lines))),
        Fraction(0),
    )
    if n_base <= 0:
        raise ReferenceInputError("rebalance conservative NAV nonpositive")
    sold = [0] * len(lines)
    # Each pass increases at least one integer sale. Stop after a size-based
    # logarithmic budget and fail closed instead of walking a huge position.
    max_passes = max(64, 8 * max((h.bit_length() for h in held), default=0))
    for _ in range(max_passes):
        n_ref = n_base - sum(
            (sold[i] * (values[i] - proceeds[i]) for i in range(len(lines))),
            Fraction(0),
        )
        if n_ref <= 0:
            raise ReferenceInputError("rebalance conservative NAV nonpositive")
        changed = False
        for i in range(len(lines)):
            if weights[i] is None:
                continue
            weight = weights[i]
            assert weight is not None
            exposure = (held[i] - sold[i]) * values[i]
            if exposure <= weight * n_ref:
                continue
            denominator = values[i] - weight * (values[i] - proceeds[i])
            if denominator <= 0:
                raise ReferenceInputError("rebalance sale denominator invalid")
            need = _ceil_fraction((exposure - weight * n_ref) / denominator)
            if need <= 0 or sold[i] + need > held[i]:
                raise ReferenceInputError("rebalance sale cannot satisfy target")
            sold[i] += need
            n_ref -= need * (values[i] - proceeds[i])
            if n_ref <= 0:
                raise ReferenceInputError("rebalance conservative NAV nonpositive")
            changed = True
        if not changed:
            break
    else:
        raise ReferenceInputError("rebalance sale sizing did not converge")
    bought: list[int] = []
    for i, weight in enumerate(weights):
        bought.append(
            0
            if sold[i] or weight is None
            else max(0, (weight * n_ref - held[i] * values[i]) // values[i])
        )
    funding = k + sum((sold[i] * proceeds[i] for i in range(len(lines))), Fraction(0))
    spend = sum((bought[i] * buy_costs[i] for i in range(len(lines))), Fraction(0))
    if spend > funding:
        ratio = funding / spend
        bought = [int(quantity * ratio) for quantity in bought]
        if not any(bought) and any(
            upper[i] > 0 and not sold[i] and buy_costs[i] <= funding
            for i in range(len(lines))
        ):
            raise ReferenceInputError("proportional buys erased feasible share")
    return tuple(Decimal(x) for x in sold), tuple(Decimal(x) for x in bought)


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


def _validate_kr_decisions(
    data: FrozenReferenceInput,
    decisions: tuple[tuple[TargetInstruction, ...], ...],
) -> tuple[tuple[tuple[TargetInstruction, ...], datetime], ...]:
    if data.registration_revision != 1 or any(
        item.market != "KR" for item in data.cohort
    ):
        raise ReferenceInputError("KR revision-one cohort required")
    if not isinstance(decisions, tuple) or not decisions:
        raise ReferenceInputError("nonempty finite KR decision sequence required")
    scheduled: list[tuple[tuple[TargetInstruction, ...], datetime]] = []
    previous_decision: datetime | None = None
    previous_open: datetime | None = None
    for vector in decisions:
        ordered, _ = _validate_multi_targets(data, vector)
        decision = _time(ordered[0].decided_at, "target decision")
        if previous_decision is not None and decision <= previous_decision:
            raise ReferenceInputError("KR decisions must increase strictly")
        if previous_open is not None and decision <= previous_open:
            raise ReferenceInputError("KR decision overlaps pending batch")
        opens = {
            min(
                (
                    _time(bar.open_at, "official open")
                    for bar in data.sessions
                    if bar.instrument == item.instrument and bar.open_at > decision
                ),
                default=None,
            )
            for item in ordered
        }
        if None in opens or len(opens) != 1:
            raise ReferenceInputError("KR batch first official opens missing or differ")
        open_at = next(iter(opens))
        assert open_at is not None
        scheduled.append((ordered, open_at))
        previous_decision, previous_open = decision, open_at
    return tuple(scheduled)


def _validate_kr_hook_vector(
    data: FrozenReferenceInput,
    vector: tuple[KRInstruction, ...],
    decision: datetime,
    prior: ReferencePoint,
) -> tuple[tuple[KRInstruction, ...], datetime]:
    if not isinstance(vector, tuple) or len(vector) != len(data.cohort):
        raise ReferenceInputError("KR hook requires every cohort identity once")
    quantities = {
        position.instrument: position.quantity for position in prior.positions
    }
    seen: set[Instrument] = set()
    gross = Fraction(0)
    leveraged = Fraction(0)
    for item in vector:
        if not isinstance(item, (TargetInstruction, HoldQuantityInstruction)):
            raise ReferenceInputError("invalid KR hook instruction")
        _instrument(item.instrument)
        if (
            item.instrument not in data.cohort
            or item.instrument in seen
            or _time(item.decided_at, "hook decision") != decision
        ):
            raise ReferenceInputError("KR hook identity or decision mismatch")
        seen.add(item.instrument)
        weight = _decimal(item.target_weight, "hook target weight")
        if weight > LIMIT:
            raise ReferenceInputError("KR hook target exceeds symbol cap")
        gross += Fraction(weight)
        if item.instrument.leveraged:
            leveraged += Fraction(weight)
        if isinstance(item, HoldQuantityInstruction):
            held = _decimal(item.quantity, "hold quantity")
            if (
                weight == 0
                or held != held.to_integral_value()
                or held != quantities.get(item.instrument, Decimal(0))
            ):
                raise ReferenceInputError("malformed hold quantity instruction")
    if (
        seen != set(data.cohort)
        or gross > Fraction(Decimal("0.60"))
        or leveraged > Fraction(LIMIT)
    ):
        raise ReferenceInputError("KR hook cohort or target caps invalid")
    ordered = tuple(
        sorted(
            vector,
            key=lambda item: (
                item.instrument.market,
                item.instrument.exchange,
                item.instrument.symbol,
                item.instrument.identity_hash,
            ),
        )
    )
    first_opens: set[datetime] = set()
    for item in ordered:
        future = [
            _time(bar.open_at, "official open")
            for bar in data.sessions
            if bar.instrument == item.instrument and bar.open_at > decision
        ]
        if not future:
            raise ReferenceInputError("KR hook missing next official open")
        first_opens.add(min(future))
    if len(first_opens) != 1:
        raise ReferenceInputError("KR hook first official opens differ")
    return ordered, next(iter(first_opens))


def _run_reference_core(
    data: FrozenReferenceInput,
    sell_costs: SellCostAssumptions | None = None,
    target: TargetInstruction | None = None,
    batch_targets: tuple[TargetInstruction, ...] | None = None,
    kr_decisions: tuple[tuple[TargetInstruction, ...], ...] | None = None,
    kr_decision_times: tuple[datetime, ...] | None = None,
    kr_decision_hook: Callable[[datetime, ReferencePoint], tuple[KRInstruction, ...]]
    | None = None,
    kr_close_hook: Callable[[ReferencePoint], None] | None = None,
    kr_dynamic_hook: Callable[[datetime, str, ReferencePoint], KRPolicyDirective]
    | None = None,
    kr_dynamic_fill_hook: Callable[[datetime, ReferencePoint, bool], None]
    | None = None,
    kr_dynamic_cap_hook: Callable[
        [datetime, datetime, str, ReferencePoint, ReferencePoint], None
    ]
    | None = None,
) -> (
    BuyHoldReference
    | CapControlReference
    | TargetBridgeReference
    | MultiTargetReference
    | KRTargetSequenceReference
):
    """Apply frozen offline events; reject any missing or inconsistent fact."""
    risk_mode = kr_dynamic_hook is not None
    policy_mode = kr_decision_hook is not None or risk_mode
    if (
        kr_decisions is None
        and not policy_mode
        and sum(x is not None for x in (sell_costs, target, batch_targets)) > 1
    ):
        raise ReferenceInputError("reference modes cannot be combined")
    if kr_decisions is not None and (target is not None or batch_targets is not None):
        raise ReferenceInputError("reference modes cannot be combined")
    if policy_mode:
        if (
            kr_decisions is not None
            or target is not None
            or batch_targets is not None
            or sell_costs is None
            or kr_decision_times is None
            or (kr_close_hook is None and not risk_mode)
            or (risk_mode and kr_decision_hook is not None)
            or (risk_mode != (kr_dynamic_fill_hook is not None))
            or (risk_mode != (kr_dynamic_cap_hook is not None))
            or not kr_decision_times
        ):
            raise ReferenceInputError("incomplete KR policy hook")
    elif (
        kr_decision_times is not None
        or kr_close_hook is not None
        or kr_dynamic_fill_hook is not None
        or kr_dynamic_cap_hook is not None
    ):
        raise ReferenceInputError("KR policy hook missing")
    _validate(
        data,
        enforce_initial_allocation=(
            target is None
            and batch_targets is None
            and kr_decisions is None
            and not policy_mode
        ),
    )
    if target is not None:
        _validate_target(data, target)
    ordered_batch: tuple[TargetInstruction, ...] = ()
    batch_open_at: datetime | None = None
    if batch_targets is not None:
        ordered_batch, batch_open_at = _validate_multi_targets(data, batch_targets)
    scheduled: list[tuple[tuple[KRInstruction, ...], datetime]] = list(
        _validate_kr_decisions(data, kr_decisions) if kr_decisions is not None else ()
    )
    if policy_mode:
        assert kr_decision_times is not None
        normalized = tuple(_time(at, "KR policy decision") for at in kr_decision_times)
        if (
            any(
                not data.evaluation_start <= at < data.evaluation_end
                for at in normalized
            )
            or any(a >= b for a, b in zip(normalized, normalized[1:]))
            or data.registration_revision != 1
            or any(item.market != "KR" for item in data.cohort)
        ):
            raise ReferenceInputError("KR policy schedule or cohort invalid")
        kr_decision_times = normalized
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
    sequence_index = 0
    sequence_batches: list[RebalanceBatch] = []
    policy_cap_pending: datetime | None = None
    risk_pending = False

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
        if sell_costs is None or kr_decisions is not None or policy_mode:
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
        prior = states.get(bar.instrument)
        if prior is None:
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
        else:
            holding = prior.holdings[0]
            states[bar.instrument] = replace(
                prior,
                holdings=(
                    replace(
                        holding,
                        quantity=holding.quantity + quantity,
                        raw_price=bar.raw_open,
                        total_cost=holding.total_cost + local_cost,
                    ),
                ),
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

    def execute_kr_batch(
        at: datetime, opened: list[RawSession], vector: tuple[KRInstruction, ...]
    ) -> None:
        nonlocal krw_cash
        assert sell_costs is not None
        bars = {bar.instrument: bar for bar in opened}
        if set(bars) != set(data.cohort):
            raise ReferenceInputError("KR sequence requires all cohort open marks")
        before = point(at, "pre_rebalance")
        ordered_bars = tuple(bars[item.instrument] for item in vector)
        terms = tuple(buy_terms(bar, at) for bar in ordered_bars)
        sell_rates = (
            sell_costs.commission_kr.rate,
            sell_costs.slippage_kr.rate,
            sell_costs.notional_tax_kr.rate,
        )
        sell_rate_exact = sum((Fraction(rate) for rate in sell_rates), Fraction(0))
        lines: list[_RebalanceLine] = []
        for item, bar, term in zip(vector, ordered_bars, terms, strict=True):
            held_state = states.get(item.instrument)
            held = (
                held_state.holdings[0].quantity
                if held_state is not None
                else Decimal(0)
            )
            if held != held.to_integral_value():
                raise ReferenceInputError("fractional holding cannot be rebalanced")
            exact_buy = (
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
            if Fraction(term.unit_cost) != exact_buy:
                raise ReferenceInputError("KR rebalance buy unit arithmetic rounded")
            proceeds = bar.raw_open * (1 - sum(sell_rates, Decimal(0)))
            if Fraction(proceeds) != Fraction(bar.raw_open) * (1 - sell_rate_exact):
                raise ReferenceInputError("KR rebalance sell unit arithmetic rounded")
            lines.append(
                _RebalanceLine(
                    item.target_weight if isinstance(item, TargetInstruction) else None,
                    held,
                    bar.raw_open,
                    term.unit_cost,
                    proceeds,
                    item.quantity
                    if isinstance(item, HoldQuantityInstruction)
                    else None,
                )
            )
        sizes = _size_kr_rebalance(before.nav_krw, before.cash_krw, tuple(lines))
        sold, bought = sizes
        expected_proceeds = sum(
            (
                Fraction(q) * Fraction(line.unit_sell_proceeds)
                for q, line in zip(sold, lines, strict=True)
            ),
            Fraction(0),
        )
        expected_spend = sum(
            (
                Fraction(q) * Fraction(line.unit_buy_cost)
                for q, line in zip(bought, lines, strict=True)
            ),
            Fraction(0),
        )
        if expected_spend > Fraction(before.cash_krw) + expected_proceeds:
            raise ReferenceInputError("KR rebalance shared cash insufficient")
        sale_count, trade_count = len(sales), len(trades)
        for item, bar, quantity in zip(vector, ordered_bars, sold, strict=True):
            if not quantity:
                continue
            state = states[item.instrument]
            current = point(at, "open", record=False)
            gross = quantity * bar.raw_open
            proceeds = gross * (1 - sum(sell_rates, Decimal(0)))
            if Fraction(proceeds) != Fraction(quantity) * Fraction(
                next(
                    line.unit_sell_proceeds
                    for line, target_item in zip(lines, vector, strict=True)
                    if target_item.instrument == item.instrument
                )
            ):
                raise ReferenceInputError("KR rebalance sale arithmetic rounded")
            states[item.instrument] = _sell_state(state, quantity, proceeds)
            after_sale = point(at, "open", record=False)
            if Fraction(after_sale.nav_krw) != Fraction(current.nav_krw) - (
                Fraction(gross) - Fraction(proceeds)
            ):
                raise ReferenceInputError("KR rebalance sale NAV mismatch")
            sales.append(
                Sale(
                    at,
                    item.instrument,
                    quantity,
                    bar.raw_open,
                    gross,
                    gross * sell_rates[0],
                    gross * sell_rates[1],
                    gross * sell_rates[2],
                    proceeds,
                    current.nav_krw,
                    current.leveraged_value_krw,
                    after_sale.nav_krw,
                    after_sale.leveraged_value_krw,
                )
            )
        before_sweep = point(at, "open", record=False)
        for instrument, state in tuple(states.items()):
            if state.cash:
                krw_cash += state.cash
                states[instrument] = replace(state, cash=Decimal(0))
        swept = point(at, "open", record=False)
        if (
            swept.nav_krw != before_sweep.nav_krw
            or swept.cash_krw != before_sweep.cash_krw
        ):
            raise ReferenceInputError("KR native cash sweep changed NAV")
        for bar, quantity, term in zip(ordered_bars, bought, terms, strict=True):
            if quantity:
                buy_at_open(bar, at, quantity, term)
        actual_proceeds = sum(
            (Fraction(sale.proceeds_local) for sale in sales[sale_count:]),
            Fraction(0),
        )
        actual_spend = sum(
            (Fraction(trade.total_krw) for trade in trades[trade_count:]),
            Fraction(0),
        )
        if actual_proceeds != expected_proceeds or actual_spend != expected_spend:
            raise ReferenceInputError("KR rebalance trade arithmetic rounded")
        after = point(at, "open", record=False)
        expected_cash = Fraction(before.cash_krw) + expected_proceeds - expected_spend
        expected_nav = (
            Fraction(before.nav_krw)
            - sum(
                (
                    Fraction(q)
                    * (Fraction(line.unit_value) - Fraction(line.unit_sell_proceeds))
                    for q, line in zip(sold, lines, strict=True)
                ),
                Fraction(0),
            )
            - sum(
                (
                    Fraction(q)
                    * (Fraction(line.unit_buy_cost) - Fraction(line.unit_value))
                    for q, line in zip(bought, lines, strict=True)
                ),
                Fraction(0),
            )
        )
        if (
            Fraction(after.cash_krw) != expected_cash
            or Fraction(after.nav_krw) != expected_nav
        ):
            raise ReferenceInputError("KR rebalance cash/NAV mismatch")
        positions = {position.instrument: position for position in after.positions}
        gross_exact = Fraction(0)
        leverage_exact = Fraction(0)
        for item, line, sale_qty, buy_qty in zip(
            vector, lines, sold, bought, strict=True
        ):
            expected_value = (
                Fraction(line.held) - Fraction(sale_qty) + Fraction(buy_qty)
            ) * Fraction(line.unit_value)
            actual_value = (
                Fraction(positions[item.instrument].value_krw)
                if item.instrument in positions
                else Fraction(0)
            )
            if actual_value != expected_value:
                raise ReferenceInputError("KR rebalance post-cost target mismatch")
            if isinstance(item, HoldQuantityInstruction):
                if actual_value > Fraction(LIMIT) * expected_nav:
                    raise ReferenceInputError(
                        "held quantity post-cost cap requires repair"
                    )
            elif actual_value > Fraction(item.target_weight) * expected_nav:
                raise ReferenceInputError("KR rebalance post-cost target mismatch")
            gross_exact += actual_value
            if item.instrument.leveraged:
                leverage_exact += actual_value
        if (
            expected_cash < 0
            or gross_exact > Fraction(Decimal("0.60")) * expected_nav
            or leverage_exact > Fraction(LIMIT) * expected_nav
        ):
            if any(isinstance(item, HoldQuantityInstruction) for item in vector):
                raise ReferenceInputError("held quantity post-cost cap requires repair")
            raise ReferenceInputError("KR rebalance post-cost cap exceeded")
        status: Literal["filled", "unchanged", "all_cash", "no_feasible_share"]
        if any(sold) or any(bought):
            status = "filled"
        elif all(
            isinstance(item, TargetInstruction) and item.target_weight == 0
            for item in vector
        ):
            status = "all_cash"
        elif any(
            line.weight is not None
            and Fraction(line.held) * Fraction(line.unit_value)
            < Fraction(line.weight) * expected_nav
            for line, item in zip(lines, vector, strict=True)
        ):
            status = "no_feasible_share"
        else:
            status = "unchanged"
        sequence_batches.append(
            RebalanceBatch(
                vector[0].decided_at,
                at,
                status,
                tuple(
                    (item.instrument, q)
                    for item, q in zip(vector, sold, strict=True)
                    if q
                ),
                tuple(
                    (item.instrument, q)
                    for item, q in zip(vector, bought, strict=True)
                    if q
                ),
            )
        )

    def policy_breached(value: ReferencePoint) -> bool:
        nav = Fraction(value.nav_krw)
        gross = sum((Fraction(p.value_krw) for p in value.positions), Fraction(0))
        return (
            gross > Fraction(Decimal("0.60")) * nav
            or Fraction(value.leveraged_value_krw) > Fraction(LIMIT) * nav
            or any(
                Fraction(p.value_krw) > Fraction(LIMIT) * nav for p in value.positions
            )
        )

    def accept_policy_directive(
        at: datetime, prior: ReferencePoint, directive: KRPolicyDirective
    ) -> None:
        nonlocal risk_pending
        if not isinstance(directive, KRPolicyDirective):
            raise ReferenceInputError("KR dynamic policy directive invalid")
        if directive.cancel_pending:
            del scheduled[sequence_index:]
            risk_pending = False
        if directive.vector is None:
            if directive.liquidation:
                raise ReferenceInputError("KR liquidation vector missing")
            return
        if sequence_index != len(scheduled):
            raise ReferenceInputError("KR policy decision overlaps pending batch")
        scheduled.append(_validate_kr_hook_vector(data, directive.vector, at, prior))
        risk_pending = directive.liquidation

    def repair_policy_cap(at: datetime, opened: list[RawSession]) -> None:
        nonlocal krw_cash
        assert sell_costs is not None
        if {bar.instrument for bar in opened if bar.instrument in data.cohort} != set(
            data.cohort
        ):
            return
        bars = {bar.instrument: bar for bar in opened}
        point(at, "pre_cap_repair")
        cost = sum(
            (
                sell_costs.commission_kr.rate,
                sell_costs.slippage_kr.rate,
                sell_costs.notional_tax_kr.rate,
            ),
            Decimal(0),
        )
        for instrument in sorted(
            data.cohort,
            key=lambda item: (
                item.market,
                item.exchange,
                item.symbol,
                item.identity_hash,
            ),
        ):
            state = states.get(instrument)
            if state is None or state.holdings[0].quantity == 0:
                continue
            before = point(at, "open", record=False)
            if not policy_breached(before):
                break
            price = bars[instrument].raw_open
            n = Fraction(before.nav_krw)
            p = Fraction(price)
            gross = sum(
                (position.value_krw for position in before.positions), Decimal(0)
            )
            position = next(x for x in before.positions if x.instrument == instrument)
            quantity = _policy_cap_sell_quantity(
                before.nav_krw,
                gross,
                before.leveraged_value_krw,
                position.value_krw,
                price,
                cost,
                state.holdings[0].quantity,
                leveraged=instrument.leveraged,
            )
            if quantity == 0:
                continue
            gross_sale = quantity * price
            proceeds = gross_sale * (1 - cost)
            if Fraction(proceeds) != Fraction(quantity) * p * (1 - Fraction(cost)):
                raise ReferenceInputError("KR cap repair sale arithmetic rounded")
            states[instrument] = _sell_state(state, quantity, proceeds)
            after = point(at, "open", record=False)
            if Fraction(after.nav_krw) != n - Fraction(gross_sale) * Fraction(cost):
                raise ReferenceInputError("KR cap repair NAV mismatch")
            sales.append(
                Sale(
                    at,
                    instrument,
                    quantity,
                    price,
                    gross_sale,
                    gross_sale * sell_costs.commission_kr.rate,
                    gross_sale * sell_costs.slippage_kr.rate,
                    gross_sale * sell_costs.notional_tax_kr.rate,
                    proceeds,
                    before.nav_krw,
                    before.leveraged_value_krw,
                    after.nav_krw,
                    after.leveraged_value_krw,
                )
            )
        before_sweep = point(at, "open", record=False)
        for instrument, state in tuple(states.items()):
            if state.cash:
                krw_cash += state.cash
                states[instrument] = replace(state, cash=Decimal(0))
        after_sweep = point(at, "open", record=False)
        if (
            before_sweep.nav_krw != after_sweep.nav_krw
            or before_sweep.cash_krw != after_sweep.cash_krw
        ):
            raise ReferenceInputError("KR cap repair cash sweep changed NAV")
        if policy_breached(after_sweep):
            raise ReferenceInputError("KR policy cap repair unresolved")

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
    if kr_decision_times is not None:
        events.extend((at, -1, "policy_decision", at) for at in kr_decision_times)
    events.sort(key=lambda x: (x[0], x[1], x[2]))
    settle_pending(point(data.evaluation_start, "initial"))
    timestamp_phase = ""
    phase_names = ("split", "dividend_ex", "dividend_payment", "open", "close")
    opens_at: list[RawSession] = []
    target_open: RawSession | None = None
    for index, (at, phase_order, _, obj) in enumerate(events):
        if index == 0 or events[index - 1][0] != at:
            timestamp_phase = (
                "decision" if phase_order == -1 else phase_names[phase_order]
            )
            opens_at = []
            target_open = None
        elif policy_mode and phase_order >= 0:
            timestamp_phase = phase_names[phase_order]
        if phase_order == -1:
            prior = point(at, "decision")
            if risk_mode:
                assert kr_dynamic_hook is not None
                accept_policy_directive(
                    at, prior, kr_dynamic_hook(at, "decision", prior)
                )
            else:
                if kr_decision_hook is None or sequence_index != len(scheduled):
                    raise ReferenceInputError(
                        "KR policy decision overlaps pending batch"
                    )
                vector = kr_decision_hook(at, prior)
                scheduled.append(_validate_kr_hook_vector(data, vector, at, prior))
        elif isinstance(obj, SplitEvent):
            state = states.get(obj.instrument)
            if state is not None and state.holdings[0].quantity > 0:
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
                    if (
                        target is None
                        and batch_targets is None
                        and kr_decisions is None
                        and not policy_mode
                    ):
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
        if (
            (kr_decisions is not None or policy_mode)
            and not risk_mode
            and sequence_index < len(scheduled)
            and at == scheduled[sequence_index][1]
            and phase_order == 3
            and (index + 1 == len(events) or events[index + 1][:2] != (at, 3))
        ):
            execute_kr_batch(at, opens_at, scheduled[sequence_index][0])
            sequence_index += 1
        if index + 1 == len(events) or events[index + 1][0] != at:
            recorded_close: ReferencePoint | None = None
            policy_traded = False
            if risk_mode:
                pre_policy = point(at, timestamp_phase, record=False)
                if timestamp_phase == "close":
                    recorded_close = point(at, "close")
                    assert kr_dynamic_hook is not None
                    accept_policy_directive(
                        at,
                        recorded_close,
                        kr_dynamic_hook(at, "close", recorded_close),
                    )
                if policy_cap_pending is not None and not policy_breached(pre_policy):
                    assert kr_dynamic_cap_hook is not None
                    kr_dynamic_cap_hook(
                        policy_cap_pending,
                        at,
                        "natural_recovery",
                        pre_policy,
                        pre_policy,
                    )
                    policy_cap_pending = None
                if (
                    sequence_index < len(scheduled)
                    and at == scheduled[sequence_index][1]
                ):
                    vector = scheduled[sequence_index][0]
                    if (
                        policy_cap_pending is not None
                        and policy_cap_pending < at
                        and not risk_pending
                    ):
                        vector = tuple(
                            TargetInstruction(
                                item.instrument, item.decided_at, item.target_weight
                            )
                            if isinstance(item, HoldQuantityInstruction)
                            else item
                            for item in vector
                        )
                    cap_batch_since = (
                        policy_cap_pending
                        if policy_cap_pending is not None
                        and policy_cap_pending < at
                        and not risk_pending
                        else None
                    )
                    execute_kr_batch(
                        at,
                        [bar for bar in opens_at if bar.instrument in data.cohort],
                        vector,
                    )
                    policy_traded = True
                    sequence_index += 1
                    assert kr_dynamic_fill_hook is not None
                    after_batch = point(at, "open", record=False)
                    if cap_batch_since is not None and not policy_breached(after_batch):
                        assert kr_dynamic_cap_hook is not None
                        kr_dynamic_cap_hook(
                            cap_batch_since,
                            at,
                            "repaired_by_target",
                            pre_policy,
                            after_batch,
                        )
                        policy_cap_pending = None
                    kr_dynamic_fill_hook(at, after_batch, risk_pending)
                    risk_pending = False
                elif (
                    policy_cap_pending is not None
                    and policy_cap_pending < at
                    and not risk_pending
                    and policy_breached(pre_policy)
                    and {
                        bar.instrument
                        for bar in opens_at
                        if bar.instrument in data.cohort
                    }
                    == set(data.cohort)
                ):
                    repair_policy_cap(at, opens_at)
                    policy_traded = True
                    assert kr_dynamic_cap_hook is not None
                    after_repair = point(at, "open", record=False)
                    kr_dynamic_cap_hook(
                        policy_cap_pending,
                        at,
                        "repaired",
                        pre_policy,
                        after_repair,
                    )
                    policy_cap_pending = None
            if (
                sell_costs is not None
                and kr_decisions is None
                and not policy_mode
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
            evaluated = (
                point(at, timestamp_phase)
                if recorded_close is None or policy_traded
                else recorded_close
            )
            settle_pending(evaluated)
            if risk_mode:
                if policy_breached(evaluated):
                    if policy_cap_pending is None:
                        policy_cap_pending = at
                        assert kr_dynamic_cap_hook is not None
                        kr_dynamic_cap_hook(at, at, "observed", evaluated, evaluated)
                else:
                    if policy_cap_pending is not None:
                        assert kr_dynamic_cap_hook is not None
                        kr_dynamic_cap_hook(
                            policy_cap_pending,
                            at,
                            "natural_recovery",
                            evaluated,
                            evaluated,
                        )
                    policy_cap_pending = None
            if kr_close_hook is not None and timestamp_phase == "close":
                kr_close_hook(evaluated)
    if (
        target is None
        and batch_targets is None
        and kr_decisions is None
        and not policy_mode
        and len(trades) != len(data.cohort)
    ):
        raise ReferenceInputError("not every cohort instrument was purchased")
    if batch_open_at is not None and not batch_executed:
        raise ReferenceInputError("batch first official open not executed")
    if (kr_decisions is not None or policy_mode) and sequence_index != len(scheduled):
        raise ReferenceInputError("KR decision batch not executed")
    if (
        policy_mode
        and not risk_mode
        and kr_decision_times is not None
        and len(scheduled) != len(kr_decision_times)
    ):
        raise ReferenceInputError("KR policy decision missing")
    end_point = point(data.evaluation_end, "evaluation_end")
    settle_pending(end_point)
    if risk_mode:
        if policy_cap_pending is not None and not policy_breached(end_point):
            assert kr_dynamic_cap_hook is not None
            kr_dynamic_cap_hook(
                policy_cap_pending,
                data.evaluation_end,
                "natural_recovery",
                end_point,
                end_point,
            )
            policy_cap_pending = None
        if policy_cap_pending is not None:
            raise ReferenceInputError("KR policy cap repair window_end_unfilled")
    if (
        sell_costs is not None
        and kr_decisions is None
        and not policy_mode
        and pending_since is not None
    ):
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
    if kr_decisions is not None or policy_mode:
        return KRTargetSequenceReference(
            "synthetic_reference_only",
            tuple(trades),
            tuple(sales),
            tuple(dividends),
            tuple(points),
            tuple(sequence_batches),
            common[4],
            common[5],
            common[6],
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


def run_kr_target_sequence_reference(
    data: FrozenReferenceInput,
    decisions: tuple[tuple[TargetInstruction, ...], ...],
    sell_costs: SellCostAssumptions,
) -> KRTargetSequenceReference:
    """Execute explicit synthetic KR target vectors in the shared raw event loop."""
    _sell_rates(sell_costs)
    result = _run_reference_core(data, sell_costs=sell_costs, kr_decisions=decisions)
    assert isinstance(result, KRTargetSequenceReference)
    return result
