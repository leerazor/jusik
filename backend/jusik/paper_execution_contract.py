"""Offline execution contract. No broker transport or trading configuration."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal, Protocol

Side = Literal["buy", "sell"]
OrderStatus = Literal["pending", "open", "partial", "filled", "cancelled", "rejected"]


@dataclass(frozen=True)
class OrderIntent:
    key: str
    symbol: str
    side: Side
    quantity: Decimal

    def __post_init__(self) -> None:
        if not self.key or not self.key.strip():
            raise ValueError("order_identity_invalid")
        if not self.symbol or not self.symbol.strip():
            raise ValueError("order_identity_invalid")
        if self.side not in ("buy", "sell"):
            raise ValueError("order_side_invalid")
        if not self.quantity.is_finite() or self.quantity <= 0:
            raise ValueError("order_quantity_invalid")


@dataclass(frozen=True)
class Fill:
    execution_id: str
    quantity: Decimal
    price: Decimal

    def __post_init__(self) -> None:
        if not self.execution_id or not self.execution_id.strip():
            raise ValueError("execution_id_invalid")
        if not self.quantity.is_finite() or self.quantity <= 0:
            raise ValueError("fill_quantity_invalid")
        if not self.price.is_finite() or self.price <= 0:
            raise ValueError("fill_price_invalid")


@dataclass(frozen=True)
class OrderSnapshot:
    intent: OrderIntent
    status: OrderStatus
    fills: tuple[Fill, ...] = ()

    @property
    def filled_quantity(self) -> Decimal:
        return sum((fill.quantity for fill in self.fills), Decimal(0))

    @property
    def remaining_quantity(self) -> Decimal:
        return self.intent.quantity - self.filled_quantity


class BrokerPort(Protocol):
    """Adapter contract: submit must use intent.key as broker idempotency key."""

    def submit(self, intent: OrderIntent) -> OrderSnapshot: ...

    def cancel(self, key: str) -> OrderSnapshot: ...

    def snapshot(self, key: str) -> OrderSnapshot | None: ...


def validate_snapshot(snapshot: OrderSnapshot) -> None:
    """Validate complete broker state before it enters the local ledger."""
    if snapshot.status not in (
        "pending", "open", "partial", "filled", "cancelled", "rejected"
    ):
        raise ValueError("order_status_invalid")
    ids = [fill.execution_id for fill in snapshot.fills]
    if len(ids) != len(set(ids)) or snapshot.remaining_quantity < 0:
        raise ValueError("order_fills_invalid")
    quantity = snapshot.filled_quantity
    if snapshot.status in ("pending", "open", "rejected") and quantity != 0:
        raise ValueError("order_status_invalid")
    if snapshot.status == "partial" and not 0 < quantity < snapshot.intent.quantity:
        raise ValueError("order_status_invalid")
    if snapshot.status == "filled" and quantity != snapshot.intent.quantity:
        raise ValueError("order_status_invalid")
    if snapshot.status == "cancelled" and quantity == snapshot.intent.quantity:
        raise ValueError("order_status_invalid")


class ExecutionLedger:
    """One process, deterministic ledger; pending means submit outcome is unknown."""

    def __init__(self, broker: BrokerPort) -> None:
        self._broker = broker
        self._orders: dict[str, OrderSnapshot] = {}

    def submit(self, intent: OrderIntent) -> OrderSnapshot:
        existing = self._orders.get(intent.key)
        if existing is not None:
            if existing.intent != intent:
                raise ValueError("idempotency_conflict")
            return existing
        pending = OrderSnapshot(intent, "pending")
        self._orders[intent.key] = pending
        try:
            result = self._broker.submit(intent)
        except Exception:
            # The remote side may have accepted the order. Never submit again.
            raise
        return self._accept(intent.key, result)

    def reconcile(self, key: str) -> OrderSnapshot:
        self._required(key)
        remote = self._broker.snapshot(key)
        if remote is None:
            raise ValueError("broker_order_missing")
        return self._accept(key, remote)

    def cancel(self, key: str) -> OrderSnapshot:
        current = self._required(key)
        if current.status == "pending":
            raise ValueError("order_outcome_unknown")
        if current.status in ("filled", "cancelled", "rejected"):
            return current
        result = self._broker.cancel(key)
        return self._accept(key, result)

    def _required(self, key: str) -> OrderSnapshot:
        try:
            return self._orders[key]
        except KeyError as exc:
            raise ValueError("order_unknown") from exc

    def _accept(self, key: str, result: OrderSnapshot) -> OrderSnapshot:
        current = self._required(key)
        if result.intent != current.intent:
            raise ValueError("reconciliation_identity_mismatch")
        validate_snapshot(result)
        old_fills = {fill.execution_id: fill for fill in current.fills}
        new_fills = {fill.execution_id: fill for fill in result.fills}
        if any(
            new_fills.get(execution_id) != fill
            for execution_id, fill in old_fills.items()
        ):
            raise ValueError("reconciliation_fill_mismatch")
        if current.status in ("filled", "cancelled", "rejected") and result != current:
            raise ValueError("reconciliation_terminal_mismatch")
        if result.filled_quantity < current.filled_quantity:
            raise ValueError("reconciliation_quantity_regressed")
        self._orders[key] = result
        return result
