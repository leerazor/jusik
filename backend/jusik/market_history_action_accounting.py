"""Pure, research-only corporate-action accounting for market history inputs.

This module deliberately sits beside the shared market-history models.  It does
not change their JSON contract and does not invoke a collector, strategy,
portfolio engine, ledger, service, or broker.  All transitions are immutable
and labelled ``not-evaluated``; the calculations are accounting invariants,
not economic results.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import (
    Context,
    Decimal,
    DivisionByZero,
    Inexact,
    InvalidOperation,
    Overflow,
    Rounded,
    Underflow,
    localcontext,
)
from typing import Literal, cast

from jusik.market_history_models import CorporateAction

PRECISION = 128
DECIMAL_CONTEXT = Context(prec=PRECISION)
for _signal in (
    Inexact,
    Rounded,
    Overflow,
    Underflow,
    InvalidOperation,
    DivisionByZero,
):
    DECIMAL_CONTEXT.traps[_signal] = True

Currency = Literal["KRW", "USD"]
PriceBasis = Literal["raw", "adjusted", "unknown"]
AccountingStatus = Literal["not-evaluated"]
TransitionStatus = Literal[
    "applied", "replayed", "insufficient", "unsupported", "rejected"
]


class AccountingError(ValueError):
    """A rejected input that must leave the prior state untouched."""


class UnsupportedActionError(AccountingError):
    """The action kind or price basis has no supported accounting rule."""


class InsufficientActionError(AccountingError):
    """Required rights, marks, or prior accrual facts are unavailable."""


class ActionConflictError(AccountingError):
    """An action ID was reused with different accounting semantics."""


def _decimal(value: object, label: str) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float):
        raise AccountingError(f"{label} must be a finite Decimal")
    try:
        result = (
            Decimal(value)
            if isinstance(value, (Decimal, int, str))
            else Decimal(str(value))
        )
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise AccountingError(f"{label} must be a finite Decimal") from exc
    if not result.is_finite():
        raise AccountingError(f"{label} must be a finite Decimal")
    return result


def _aware_utc(value: object, label: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise AccountingError(f"{label} must be timezone-aware")
    return value.astimezone(UTC)


def _decimal_text(value: Decimal) -> str:
    if value == 0:
        return "0"
    sign, digits, raw_exponent = value.as_tuple()
    exponent = cast(int, raw_exponent)
    significant = list(digits)
    while significant and significant[-1] == 0:
        significant.pop()
        exponent += 1
    coefficient = "".join(str(digit) for digit in significant)
    return f"{'-' if sign else ''}{coefficient}e{exponent}"


def _currency(value: object, label: str) -> Currency:
    if value not in {"KRW", "USD"}:
        raise AccountingError(f"{label} must be KRW or USD")
    return cast(Currency, value)


def _strict_bool(value: object, label: str) -> bool:
    if type(value) is not bool:
        raise AccountingError(f"{label} must be a bool")
    return value


def _price_basis(value: object) -> PriceBasis:
    if value not in {"raw", "adjusted", "unknown"}:
        raise AccountingError("price_basis is unsupported")
    return cast(PriceBasis, value)


@dataclass(frozen=True)
class Holding:
    """One symbol's raw quantity, raw mark, and total cost basis."""

    symbol: str
    quantity: Decimal
    raw_price: Decimal
    total_cost: Decimal
    currency: Currency


@dataclass(frozen=True)
class DividendReceivable:
    """Frozen entitlement facts created by accrual and consumed by payment."""

    action_id: str
    symbol: str
    entitled_quantity: Decimal
    amount_per_share: Decimal
    gross_amount: Decimal
    currency: Currency
    effective_at: datetime
    payment_at: datetime


@dataclass(frozen=True)
class ActionRecord:
    action_id: str
    kind: Literal["split", "dividend"]
    phase: Literal["split", "accrual", "payment"]
    identity_hash: str


@dataclass(frozen=True)
class AccountingState:
    """Immutable state used by the pure transitions in this module."""

    holdings: tuple[Holding, ...] = ()
    cash: Decimal = Decimal(0)
    receivables: tuple[DividendReceivable, ...] = ()
    action_records: tuple[ActionRecord, ...] = ()
    currency: Currency | None = None
    coverage: Literal["incomplete"] = "incomplete"
    accounting_status: AccountingStatus = "not-evaluated"

    @property
    def nav(self) -> Decimal:
        with localcontext(DECIMAL_CONTEXT):
            holding_value = sum(
                (holding.quantity * holding.raw_price for holding in self.holdings),
                Decimal(0),
            )
            receivable_value = sum(
                (item.gross_amount for item in self.receivables), Decimal(0)
            )
            return self.cash + holding_value + receivable_value


@dataclass(frozen=True)
class SplitAction:
    action_id: str
    symbol: str
    effective_at: datetime
    ratio: Decimal
    currency: Currency
    price_basis: PriceBasis = "unknown"
    before_price: Decimal | None = None
    after_price: Decimal | None = None


@dataclass(frozen=True)
class DividendAction:
    action_id: str
    symbol: str
    effective_at: datetime
    payment_at: datetime
    amount_per_share: Decimal
    currency: Currency
    entitled_quantity: Decimal | None
    entitlement_confirmed: bool
    price_basis: PriceBasis = "unknown"


Action = SplitAction | DividendAction


@dataclass(frozen=True)
class NormalizedAction:
    action: Action
    identity_hash: str
    canonical_payload: str


@dataclass(frozen=True)
class TransitionResult:
    state: AccountingState
    status: TransitionStatus
    reason: str | None = None
    identity_hash: str | None = None
    nav_before: Decimal | None = None
    nav_after: Decimal | None = None
    total_cost_before: Decimal | None = None
    total_cost_after: Decimal | None = None
    coverage: Literal["incomplete"] = "incomplete"


def _raw_payload(action: Action) -> dict[str, object]:
    if isinstance(action, SplitAction):
        payload: dict[str, object] = {
            "kind": "split",
            "symbol": action.symbol,
            "effective_at": _aware_utc(action.effective_at, "effective_at").isoformat(),
            "ratio": _decimal_text(_decimal(action.ratio, "ratio")),
            "currency": action.currency,
            "price_basis": action.price_basis,
            "before_price": (
                None
                if action.before_price is None
                else _decimal_text(_decimal(action.before_price, "before_price"))
            ),
            "after_price": (
                None
                if action.after_price is None
                else _decimal_text(_decimal(action.after_price, "after_price"))
            ),
        }
    else:
        payload = {
            "kind": "dividend",
            "symbol": action.symbol,
            "effective_at": _aware_utc(action.effective_at, "effective_at").isoformat(),
            "payment_at": _aware_utc(action.payment_at, "payment_at").isoformat(),
            "amount_per_share": _decimal_text(
                _decimal(action.amount_per_share, "amount_per_share")
            ),
            "currency": action.currency,
            "entitled_quantity": (
                None
                if action.entitled_quantity is None
                else _decimal_text(
                    _decimal(action.entitled_quantity, "entitled_quantity")
                )
            ),
            "entitlement_confirmed": action.entitlement_confirmed,
            "price_basis": action.price_basis,
        }
    return payload


def normalize_action(action: Action) -> NormalizedAction:
    """Canonicalize an action; its hash includes all accounting semantics."""

    if not isinstance(action, (SplitAction, DividendAction)):
        raise AccountingError("action is unsupported")
    payload = _raw_payload(action)
    if not isinstance(action.action_id, str) or not action.action_id:
        raise AccountingError("action_id must be non-empty")
    if not isinstance(action.symbol, str) or not action.symbol:
        raise AccountingError("symbol must be non-empty")
    if action.price_basis != "raw":
        raise UnsupportedActionError("adjusted or unknown price basis is unsupported")
    if isinstance(action, SplitAction):
        ratio = _decimal(action.ratio, "ratio")
        if ratio <= 0:
            raise AccountingError("split ratio must be positive")
    else:
        _strict_bool(action.entitlement_confirmed, "entitlement_confirmed")
        amount = _decimal(action.amount_per_share, "amount_per_share")
        if amount <= 0:
            raise AccountingError("dividend amount must be positive")
        if action.payment_at < action.effective_at:
            raise AccountingError("payment boundary precedes effective boundary")
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return NormalizedAction(
        action=action,
        identity_hash=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        canonical_payload=canonical,
    )


def _identity_or_none(action: Action) -> str | None:
    try:
        return normalize_action(action).identity_hash
    except AccountingError:
        return None


def _legacy_action_id(
    action: CorporateAction, effective_at: datetime, price_basis: PriceBasis
) -> str:
    payload = {
        "kind": action.kind,
        "market": action.market,
        "symbol": action.symbol,
        "session": action.session.isoformat(),
        "effective_at": _aware_utc(effective_at, "effective_at").isoformat(),
        "currency": "KRW" if action.market == "KR" else "USD",
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def legacy_corporate_action_to_action(
    action: CorporateAction,
    *,
    effective_at: datetime,
    price_basis: PriceBasis,
    action_id: str | None = None,
    before_price: Decimal | None = None,
    after_price: Decimal | None = None,
) -> SplitAction:
    """Convert a legacy split while leaving ``CorporateAction`` unchanged.

    Without a supplied ID, the event key is market/symbol/session/kind/effective
    boundary.  A later payload revision therefore reaches the same ID and is
    rejected as a semantic conflict instead of silently becoming a new event.
    """

    if action.kind != "split":
        raise UnsupportedActionError(f"legacy action kind {action.kind} is unsupported")
    if action.ratio is None:
        raise InsufficientActionError("legacy split ratio is missing")
    if price_basis != "raw":
        raise UnsupportedActionError("adjusted or unknown price basis is unsupported")
    effective = _aware_utc(effective_at, "effective_at")
    currency: Currency = "KRW" if action.market == "KR" else "USD"
    return SplitAction(
        action_id=action_id or _legacy_action_id(action, effective, price_basis),
        symbol=action.symbol,
        effective_at=effective,
        ratio=_decimal(action.ratio, "ratio"),
        currency=currency,
        price_basis="raw",
        before_price=before_price,
        after_price=after_price,
    )


def _existing_record(
    state: AccountingState,
    normalized: NormalizedAction,
    phase: Literal["split", "accrual", "payment"],
) -> TransitionResult | None:
    action = normalized.action
    for record in state.action_records:
        if record.action_id != action.action_id:
            continue
        if record.identity_hash != normalized.identity_hash:
            return TransitionResult(
                state, "rejected", "action_id_conflict", normalized.identity_hash
            )
        if record.phase == phase:
            return TransitionResult(
                state, "replayed", "identical_replay", normalized.identity_hash
            )
    return None


def _validate_holding(holding: Holding) -> None:
    if not holding.symbol:
        raise AccountingError("holding symbol must be non-empty")
    _currency(holding.currency, "holding currency")
    quantity = _decimal(holding.quantity, "holding quantity")
    raw_price = _decimal(holding.raw_price, "holding raw price")
    total_cost = _decimal(holding.total_cost, "holding total cost")
    if quantity < 0:
        raise AccountingError("holding quantity must be non-negative")
    if raw_price <= 0:
        raise AccountingError("holding raw price must be positive")
    if total_cost < 0:
        raise AccountingError("holding total cost must be non-negative")


def _validate_state(state: AccountingState) -> None:
    if not isinstance(state, AccountingState):
        raise AccountingError("state is invalid")
    cash = _decimal(state.cash, "cash")
    if cash < 0:
        raise AccountingError("cash must be non-negative")
    currencies: set[Currency] = set()
    symbols: set[str] = set()
    for holding in state.holdings:
        _validate_holding(holding)
        currencies.add(holding.currency)
        if holding.symbol in symbols:
            raise AccountingError("duplicate holding symbol")
        symbols.add(holding.symbol)
    for receivable in state.receivables:
        if receivable.action_id == "":
            raise AccountingError("receivable action_id must be non-empty")
        _aware_utc(receivable.effective_at, "receivable effective_at")
        _aware_utc(receivable.payment_at, "receivable payment_at")
        if receivable.payment_at < receivable.effective_at:
            raise AccountingError("receivable payment precedes effective boundary")
        _currency(receivable.currency, "receivable currency")
        entitled_quantity = _decimal(
            receivable.entitled_quantity, "receivable entitled quantity"
        )
        amount_per_share = _decimal(
            receivable.amount_per_share, "receivable amount per share"
        )
        gross_amount = _decimal(receivable.gross_amount, "receivable gross amount")
        if gross_amount < 0 or entitled_quantity < 0 or amount_per_share <= 0:
            raise AccountingError("receivable values must be non-negative")
        currencies.add(receivable.currency)
        with localcontext(DECIMAL_CONTEXT):
            if gross_amount != entitled_quantity * amount_per_share:
                raise AccountingError("receivable amount does not match entitlement")
    if len(currencies) > 1:
        raise AccountingError("mixed KRW/USD accounting is unsupported")
    if state.currency is not None:
        _currency(state.currency, "state currency")
        if currencies and currencies != {state.currency}:
            raise AccountingError("state currency does not match accounting values")
    record_keys: set[tuple[str, str]] = set()
    record_hashes: dict[str, str] = {}
    for record in state.action_records:
        if (
            not record.action_id
            or len(record.identity_hash) != 64
            or any(
                character not in "0123456789abcdef"
                for character in record.identity_hash
            )
        ):
            raise AccountingError("action record is invalid")
        if record.phase not in {"split", "accrual", "payment"}:
            raise AccountingError("action record phase is invalid")
        if record.phase == "split" and record.kind != "split":
            raise AccountingError("action record kind is invalid")
        if record.phase in {"accrual", "payment"} and record.kind != "dividend":
            raise AccountingError("action record kind is invalid")
        key = (record.action_id, record.phase)
        if key in record_keys:
            raise AccountingError("duplicate action record")
        record_keys.add(key)
        prior_hash = record_hashes.setdefault(record.action_id, record.identity_hash)
        if prior_hash != record.identity_hash:
            raise AccountingError("conflicting action records")
    receivable_ids = {item.action_id for item in state.receivables}
    if len(receivable_ids) != len(state.receivables):
        raise AccountingError("duplicate dividend receivable")
    for action_id in receivable_ids:
        if (action_id, "accrual") not in record_keys:
            raise AccountingError("receivable has no accrual record")


def _reject(
    state: AccountingState,
    reason: str,
    identity_hash: str | None = None,
    *,
    status: TransitionStatus = "rejected",
) -> TransitionResult:
    return TransitionResult(state, status, reason, identity_hash)


def apply_split(
    state: AccountingState,
    action: SplitAction,
    *,
    at: datetime,
) -> TransitionResult:
    """Apply a raw split, preserving quantity*price NAV and total cost exactly."""

    try:
        _validate_state(state)
        normalized = normalize_action(action)
        replay = _existing_record(state, normalized, "split")
        if replay is not None:
            return replay
        holding_index = next(
            (
                index
                for index, item in enumerate(state.holdings)
                if item.symbol == action.symbol
            ),
            None,
        )
        if holding_index is None:
            raise InsufficientActionError("split holding is unavailable")
        boundary = _aware_utc(at, "split boundary")
        effective = _aware_utc(action.effective_at, "effective_at")
        if boundary < effective:
            raise AccountingError("split boundary precedes effective boundary")
        if action.before_price is None or action.after_price is None:
            raise InsufficientActionError("raw split marks are required")
        holding = state.holdings[holding_index]
        if holding.currency != action.currency:
            raise AccountingError("action and holding currencies differ")
        with localcontext(DECIMAL_CONTEXT):
            ratio = _decimal(action.ratio, "ratio")
            quantity_before = holding.quantity
            price_before = holding.raw_price
            total_cost_before = holding.total_cost
            quantity_after = quantity_before * ratio
            price_after = price_before / ratio
            if _decimal(action.before_price, "before_price") != price_before:
                raise AccountingError("before raw price does not match holding")
            if _decimal(action.after_price, "after_price") != price_after:
                raise AccountingError("after raw price does not match split")
            holding_nav_before = quantity_before * price_before
            holding_nav_after = quantity_after * price_after
            if holding_nav_after != holding_nav_before:
                raise AccountingError("split NAV is not preserved")
            updated = replace(holding, quantity=quantity_after, raw_price=price_after)
            holdings = (
                state.holdings[:holding_index]
                + (updated,)
                + state.holdings[holding_index + 1 :]
            )
            next_state = replace(
                state,
                holdings=holdings,
                action_records=state.action_records
                + (
                    ActionRecord(
                        action.action_id, "split", "split", normalized.identity_hash
                    ),
                ),
            )
            return TransitionResult(
                next_state,
                "applied",
                identity_hash=normalized.identity_hash,
                nav_before=state.nav,
                nav_after=next_state.nav,
                total_cost_before=total_cost_before,
                total_cost_after=updated.total_cost,
            )
    except UnsupportedActionError as exc:
        return _reject(
            state,
            str(exc),
            _identity_or_none(action),
            status="unsupported",
        )
    except InsufficientActionError as exc:
        return _reject(
            state,
            str(exc),
            _identity_or_none(action),
            status="insufficient",
        )
    except AccountingError as exc:
        return _reject(state, str(exc), _identity_or_none(action))
    except (ArithmeticError, TypeError, ValueError):
        return _reject(state, "decimal_operation_rejected", None)


def accrue_dividend(
    state: AccountingState,
    action: DividendAction,
    *,
    at: datetime,
) -> TransitionResult:
    """Accrue a confirmed entitlement without changing cash."""

    try:
        _validate_state(state)
        normalized = normalize_action(action)
        replay = _existing_record(state, normalized, "accrual")
        if replay is not None:
            return replay
        boundary = _aware_utc(at, "accrual boundary")
        effective = _aware_utc(action.effective_at, "effective_at")
        if boundary < effective:
            raise AccountingError("accrual boundary precedes effective boundary")
        if not action.entitlement_confirmed or action.entitled_quantity is None:
            raise InsufficientActionError(
                "dividend entitlement is unconfirmed or missing"
            )
        holding = next(
            (item for item in state.holdings if item.symbol == action.symbol), None
        )
        if holding is None:
            raise InsufficientActionError("dividend holding is unavailable")
        if holding.currency != action.currency:
            raise AccountingError("action and holding currencies differ")
        with localcontext(DECIMAL_CONTEXT):
            entitlement = _decimal(action.entitled_quantity, "entitled_quantity")
            amount = _decimal(action.amount_per_share, "amount_per_share")
            if entitlement < 0:
                raise AccountingError("entitled quantity must be non-negative")
            if entitlement != holding.quantity:
                raise InsufficientActionError(
                    "entitled quantity does not match holding"
                )
            gross = entitlement * amount
            receivable = DividendReceivable(
                action_id=action.action_id,
                symbol=action.symbol,
                entitled_quantity=entitlement,
                amount_per_share=amount,
                gross_amount=gross,
                currency=action.currency,
                effective_at=_aware_utc(action.effective_at, "effective_at"),
                payment_at=_aware_utc(action.payment_at, "payment_at"),
            )
            next_state = replace(
                state,
                receivables=state.receivables + (receivable,),
                action_records=state.action_records
                + (
                    ActionRecord(
                        action.action_id,
                        "dividend",
                        "accrual",
                        normalized.identity_hash,
                    ),
                ),
            )
            return TransitionResult(
                next_state, "applied", identity_hash=normalized.identity_hash
            )
    except UnsupportedActionError as exc:
        return _reject(
            state,
            str(exc),
            _identity_or_none(action),
            status="unsupported",
        )
    except InsufficientActionError as exc:
        return _reject(
            state,
            str(exc),
            _identity_or_none(action),
            status="insufficient",
        )
    except AccountingError as exc:
        return _reject(state, str(exc), _identity_or_none(action))
    except (ArithmeticError, TypeError, ValueError):
        return _reject(state, "decimal_operation_rejected")


def pay_dividend(
    state: AccountingState,
    action: DividendAction,
    *,
    at: datetime,
) -> TransitionResult:
    """Move the frozen accrued amount to cash at an explicit UTC boundary."""

    try:
        _validate_state(state)
        normalized = normalize_action(action)
        replay = _existing_record(state, normalized, "payment")
        if replay is not None:
            return replay
        boundary = _aware_utc(at, "payment boundary")
        payment_index = next(
            (
                index
                for index, item in enumerate(state.receivables)
                if item.action_id == action.action_id
            ),
            None,
        )
        if payment_index is None:
            raise InsufficientActionError("dividend entitlement has not been accrued")
        receivable = state.receivables[payment_index]
        if boundary < receivable.payment_at:
            raise AccountingError("payment boundary precedes payment date")
        with localcontext(DECIMAL_CONTEXT):
            action_entitlement = (
                None
                if action.entitled_quantity is None
                else _decimal(action.entitled_quantity, "entitled_quantity")
            )
            action_amount = _decimal(action.amount_per_share, "amount_per_share")
            semantics_match = (
                receivable.symbol == action.symbol
                and receivable.currency == action.currency
                and action.entitlement_confirmed is True
                and receivable.effective_at.astimezone(UTC)
                == action.effective_at.astimezone(UTC)
                and receivable.payment_at.astimezone(UTC)
                == action.payment_at.astimezone(UTC)
                and action_entitlement is not None
                and receivable.entitled_quantity == action_entitlement
                and receivable.amount_per_share == action_amount
                and receivable.gross_amount == action_entitlement * action_amount
            )
        if not semantics_match:
            raise ActionConflictError(
                "payment semantics conflict with accrued entitlement"
            )
        with localcontext(DECIMAL_CONTEXT):
            next_state = replace(
                state,
                cash=state.cash + receivable.gross_amount,
                receivables=state.receivables[:payment_index]
                + state.receivables[payment_index + 1 :],
                action_records=state.action_records
                + (
                    ActionRecord(
                        action.action_id,
                        "dividend",
                        "payment",
                        normalized.identity_hash,
                    ),
                ),
            )
            return TransitionResult(
                next_state, "applied", identity_hash=normalized.identity_hash
            )
    except UnsupportedActionError as exc:
        return _reject(
            state,
            str(exc),
            _identity_or_none(action),
            status="unsupported",
        )
    except InsufficientActionError as exc:
        return _reject(
            state,
            str(exc),
            _identity_or_none(action),
            status="insufficient",
        )
    except AccountingError as exc:
        return _reject(state, str(exc), _identity_or_none(action))
    except (ArithmeticError, TypeError, ValueError):
        return _reject(state, "decimal_operation_rejected")


def normalize_action_payload(payload: Mapping[str, object]) -> Action:
    """Normalize an explicit JSON-like split or dividend payload."""

    kind = payload.get("kind")
    action_id = payload.get("action_id")
    symbol = payload.get("symbol")
    currency = _currency(payload.get("currency"), "currency")
    price_basis = _price_basis(payload.get("price_basis"))
    if not isinstance(action_id, str) or not action_id:
        raise AccountingError("action_id must be non-empty")
    if not isinstance(symbol, str) or not symbol:
        raise AccountingError("symbol must be non-empty")
    if kind == "split":
        effective = _aware_utc(payload.get("effective_at"), "effective_at")
        return SplitAction(
            action_id=action_id,
            symbol=symbol,
            effective_at=effective,
            ratio=_decimal(payload.get("ratio"), "ratio"),
            currency=currency,
            price_basis=price_basis,
            before_price=(
                None
                if payload.get("before_price") is None
                else _decimal(payload["before_price"], "before_price")
            ),
            after_price=(
                None
                if payload.get("after_price") is None
                else _decimal(payload["after_price"], "after_price")
            ),
        )
    if kind == "dividend":
        return DividendAction(
            action_id=action_id,
            symbol=symbol,
            effective_at=_aware_utc(payload.get("effective_at"), "effective_at"),
            payment_at=_aware_utc(payload.get("payment_at"), "payment_at"),
            amount_per_share=_decimal(
                payload.get("amount_per_share"), "amount_per_share"
            ),
            currency=currency,
            entitled_quantity=(
                None
                if payload.get("entitled_quantity") is None
                else _decimal(payload["entitled_quantity"], "entitled_quantity")
            ),
            entitlement_confirmed=_strict_bool(
                payload.get("entitlement_confirmed"), "entitlement_confirmed"
            ),
            price_basis=price_basis,
        )
    raise UnsupportedActionError("action kind is unsupported")


def action_identity(action: Action) -> str:
    """Return the normalized identity hash used for replay/conflict checks."""

    return normalize_action(action).identity_hash


__all__ = [
    "AccountingError",
    "AccountingState",
    "ActionConflictError",
    "ActionRecord",
    "DividendAction",
    "DividendReceivable",
    "Holding",
    "InsufficientActionError",
    "NormalizedAction",
    "SplitAction",
    "TransitionResult",
    "UnsupportedActionError",
    "action_identity",
    "accrue_dividend",
    "apply_split",
    "legacy_corporate_action_to_action",
    "normalize_action",
    "normalize_action_payload",
    "pay_dividend",
]
