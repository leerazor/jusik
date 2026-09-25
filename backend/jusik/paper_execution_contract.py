"""Offline execution contract. No broker transport or trading configuration."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Literal, Protocol

Side = Literal["buy", "sell"]
OrderStatus = Literal["pending", "open", "partial", "filled", "cancelled", "rejected"]


def _exact_sum(values: Iterable[Decimal]) -> Decimal:
    """Sum finite decimals without rounding through the caller's context."""
    parts: list[tuple[int, int]] = []
    for value in values:
        decimal_tuple = value.as_tuple()
        part_exponent = decimal_tuple.exponent
        if not isinstance(part_exponent, int):
            raise ValueError("decimal_nonfinite")
        coefficient = 0
        for digit in decimal_tuple.digits:
            coefficient = coefficient * 10 + digit
        if decimal_tuple.sign:
            coefficient = -coefficient
        parts.append((coefficient, part_exponent))
    if not parts:
        return Decimal(0)
    minimum_exponent = min(part_exponent for _, part_exponent in parts)
    total = sum(
        coefficient * 10 ** (part_exponent - minimum_exponent)
        for coefficient, part_exponent in parts
    )
    return Decimal(
        (
            int(total < 0),
            tuple(int(digit) for digit in str(abs(total))),
            minimum_exponent,
        )
    )


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
        return _exact_sum(fill.quantity for fill in self.fills)

    @property
    def remaining_quantity(self) -> Decimal:
        return _exact_sum(
            (
                self.intent.quantity,
                *(fill.quantity.copy_negate() for fill in self.fills),
            )
        )


class BrokerPort(Protocol):
    """Adapter contract: submit must use intent.key as broker idempotency key."""

    def submit(self, intent: OrderIntent) -> OrderSnapshot: ...

    def cancel(self, key: str) -> OrderSnapshot: ...

    def snapshot(self, key: str) -> OrderSnapshot | None: ...


def validate_snapshot(snapshot: OrderSnapshot) -> None:
    """Validate complete broker state before it enters the local ledger."""
    if snapshot.status not in (
        "pending",
        "open",
        "partial",
        "filled",
        "cancelled",
        "rejected",
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
    """Offline ledger; an optional SQLite journal survives process restarts."""

    def __init__(self, broker: BrokerPort, journal_path: Path | None = None) -> None:
        self._broker = broker
        self._orders: dict[str, OrderSnapshot] = {}
        self._cancel_attempted: set[str] = set()
        self._journal = (
            _OrderJournal(journal_path) if journal_path is not None else None
        )

    def submit(self, intent: OrderIntent) -> OrderSnapshot:
        existing = self._current(intent.key)
        if existing is not None:
            if existing.intent != intent:
                raise ValueError("idempotency_conflict")
            return existing
        pending = OrderSnapshot(intent, "pending")
        if self._journal is not None:
            existing = self._journal.insert_intent(pending)
            if existing is not None:
                if existing.intent != intent:
                    raise ValueError("idempotency_conflict")
                return existing
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
        if key in self._cancel_attempted or (
            self._journal is not None and self._journal.cancel_attempted(key)
        ):
            raise ValueError("cancel_outcome_unknown")
        # A lost response cannot prove the broker did not receive the request.
        if self._journal is not None and not self._journal.mark_cancel_attempted(key):
            raise ValueError("cancel_outcome_unknown")
        self._cancel_attempted.add(key)
        result = self._broker.cancel(key)
        return self._accept(key, result)

    def _required(self, key: str) -> OrderSnapshot:
        current = self._current(key)
        if current is None:
            raise ValueError("order_unknown")
        return current

    def _current(self, key: str) -> OrderSnapshot | None:
        if self._journal is not None:
            return self._journal.get(key)
        return self._orders.get(key)

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
        if current.status in ("filled", "rejected") and result != current:
            raise ValueError("reconciliation_terminal_mismatch")
        if current.status == "cancelled" and result.status not in (
            "cancelled",
            "filled",
        ):
            raise ValueError("reconciliation_terminal_mismatch")
        if current.status != "pending" and result.status == "pending":
            raise ValueError("reconciliation_status_regressed")
        if result.filled_quantity < current.filled_quantity:
            raise ValueError("reconciliation_quantity_regressed")
        if self._journal is not None:
            self._journal.update(result)
        self._orders[key] = result
        return result


class _OrderJournal:
    """Commit call intent before issuing any externally observable fake-broker call."""

    def __init__(self, path: Path) -> None:
        self.path = path
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS paper_orders ("
                "key TEXT PRIMARY KEY, snapshot TEXT NOT NULL, "
                "cancel_attempted INTEGER NOT NULL DEFAULT 0)"
            )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=5)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def get(self, key: str) -> OrderSnapshot | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT snapshot FROM paper_orders WHERE key=?", (key,)
            ).fetchone()
        if row is None:
            return None
        snapshot = _decode_snapshot(row[0])
        if snapshot.intent.key != key:
            raise ValueError("journal_identity_mismatch")
        return snapshot

    def insert_intent(self, pending: OrderSnapshot) -> OrderSnapshot | None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT snapshot FROM paper_orders WHERE key=?", (pending.intent.key,)
            ).fetchone()
            if row is None:
                connection.execute(
                    "INSERT INTO paper_orders (key, snapshot) VALUES (?, ?)",
                    (pending.intent.key, _encode_snapshot(pending)),
                )
        if row is None:
            return None
        snapshot = _decode_snapshot(row[0])
        if snapshot.intent.key != pending.intent.key:
            raise ValueError("journal_identity_mismatch")
        return snapshot

    def cancel_attempted(self, key: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT cancel_attempted FROM paper_orders WHERE key=?", (key,)
            ).fetchone()
        return row is not None and bool(row[0])

    def mark_cancel_attempted(self, key: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE paper_orders SET cancel_attempted=1 "
                "WHERE key=? AND cancel_attempted=0",
                (key,),
            )
        return cursor.rowcount == 1

    def update(self, snapshot: OrderSnapshot) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE paper_orders SET snapshot=? WHERE key=?",
                (_encode_snapshot(snapshot), snapshot.intent.key),
            )
            if cursor.rowcount != 1:
                raise ValueError("order_unknown")


def _encode_snapshot(snapshot: OrderSnapshot) -> str:
    return json.dumps(
        {
            "key": snapshot.intent.key,
            "symbol": snapshot.intent.symbol,
            "side": snapshot.intent.side,
            "quantity": str(snapshot.intent.quantity),
            "status": snapshot.status,
            "fills": [
                [fill.execution_id, str(fill.quantity), str(fill.price)]
                for fill in snapshot.fills
            ],
        }
    )


def _decode_snapshot(value: str) -> OrderSnapshot:
    data = json.loads(value)
    intent = OrderIntent(
        data["key"], data["symbol"], data["side"], Decimal(data["quantity"])
    )
    snapshot = OrderSnapshot(
        intent,
        data["status"],
        tuple(
            Fill(execution_id, Decimal(quantity), Decimal(price))
            for execution_id, quantity, price in data["fills"]
        ),
    )
    validate_snapshot(snapshot)
    return snapshot
