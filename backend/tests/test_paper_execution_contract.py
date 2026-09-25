"""Deterministic fake-broker contract tests; no network or credentials."""

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal, localcontext
from pathlib import Path
from threading import Event

import pytest

import jusik.paper_execution_contract as execution_contract
from jusik.paper_execution_contract import (
    ExecutionLedger,
    Fill,
    OrderIntent,
    OrderSnapshot,
    OrderStatus,
    validate_snapshot,
)


class FakeBroker:
    def __init__(self) -> None:
        self.orders: dict[str, OrderSnapshot] = {}
        self.submit_calls = 0
        self.cancel_calls = 0
        self.fail_after_accept = False
        self.fail_cancel_after_accept = False

    def submit(self, intent: OrderIntent) -> OrderSnapshot:
        self.submit_calls += 1
        existing = self.orders.get(intent.key)
        if existing is not None:
            if existing.intent != intent:
                raise ValueError("idempotency_conflict")
            return existing
        snapshot = OrderSnapshot(intent, "open")
        self.orders[intent.key] = snapshot
        if self.fail_after_accept:
            raise TimeoutError("response_lost")
        return snapshot

    def cancel(self, key: str) -> OrderSnapshot:
        self.cancel_calls += 1
        current = self.orders[key]
        if current.status not in ("open", "partial"):
            return current
        result = OrderSnapshot(current.intent, "cancelled", current.fills)
        self.orders[key] = result
        if self.fail_cancel_after_accept:
            raise TimeoutError("cancel_response_lost")
        return result

    def snapshot(self, key: str) -> OrderSnapshot | None:
        return self.orders.get(key)

    def fill(self, key: str, fill: Fill) -> None:
        current = self.orders[key]
        if current.status not in ("open", "partial"):
            raise ValueError("order_terminal")
        fills = (*current.fills, fill)
        quantity = sum((item.quantity for item in fills), Decimal(0))
        status: OrderStatus = (
            "filled" if quantity == current.intent.quantity else "partial"
        )
        result = OrderSnapshot(current.intent, status, fills)
        validate_snapshot(result)
        self.orders[key] = result

    def reject(self, key: str) -> None:
        current = self.orders[key]
        self.orders[key] = OrderSnapshot(current.intent, "rejected")


def intent(key: str = "k1", quantity: str = "10") -> OrderIntent:
    return OrderIntent(key, "ABC", "buy", Decimal(quantity))


def test_idempotent_submit_and_conflicting_key() -> None:
    broker = FakeBroker()
    ledger = ExecutionLedger(broker)
    first = ledger.submit(intent())
    assert ledger.submit(intent()) == first
    assert broker.submit_calls == 1
    with pytest.raises(ValueError, match="idempotency_conflict"):
        ledger.submit(intent(quantity="11"))
    assert broker.submit_calls == 1


def test_partial_fills_reconcile_and_preserve_execution_ids() -> None:
    broker = FakeBroker()
    ledger = ExecutionLedger(broker)
    ledger.submit(intent())
    broker.fill("k1", Fill("f1", Decimal("3"), Decimal("10.25")))
    first = ledger.reconcile("k1")
    assert (first.status, first.filled_quantity, first.remaining_quantity) == (
        "partial",
        Decimal("3"),
        Decimal("7"),
    )
    broker.fill("k1", Fill("f2", Decimal("7"), Decimal("10.50")))
    assert ledger.reconcile("k1").status == "filled"
    assert ledger.cancel("k1").status == "filled"
    assert broker.cancel_calls == 0


def test_cancel_after_partial_fill_is_idempotent() -> None:
    broker = FakeBroker()
    ledger = ExecutionLedger(broker)
    ledger.submit(intent())
    broker.fill("k1", Fill("f1", Decimal("4"), Decimal("9")))
    ledger.reconcile("k1")
    cancelled = ledger.cancel("k1")
    assert cancelled.status == "cancelled"
    assert cancelled.filled_quantity == Decimal("4")
    assert ledger.cancel("k1") == cancelled
    assert broker.cancel_calls == 1


def test_cancelled_order_accepts_late_fill_without_reopening() -> None:
    broker = FakeBroker()
    ledger = ExecutionLedger(broker)
    ledger.submit(intent())
    first_fill = Fill("f1", Decimal("3"), Decimal("9"))
    broker.fill("k1", first_fill)
    ledger.reconcile("k1")
    ledger.cancel("k1")
    late_fill = Fill("f2", Decimal("2"), Decimal("9.25"))
    broker.orders["k1"] = OrderSnapshot(intent(), "cancelled", (first_fill, late_fill))
    reconciled = ledger.reconcile("k1")
    assert reconciled.filled_quantity == Decimal("5")
    assert reconciled.remaining_quantity == Decimal("5")
    assert ledger.cancel("k1") == reconciled
    assert broker.cancel_calls == 1
    broker.orders["k1"] = OrderSnapshot(intent(), "cancelled", (first_fill,))
    with pytest.raises(ValueError, match="reconciliation_fill_mismatch"):
        ledger.reconcile("k1")
    broker.orders["k1"] = OrderSnapshot(intent(), "partial", (first_fill, late_fill))
    with pytest.raises(ValueError, match="reconciliation_terminal_mismatch"):
        ledger.reconcile("k1")


def test_cancelled_order_can_reconcile_to_fully_filled() -> None:
    broker = FakeBroker()
    ledger = ExecutionLedger(broker)
    ledger.submit(intent())
    first_fill = Fill("f1", Decimal("3"), Decimal("9"))
    broker.fill("k1", first_fill)
    ledger.reconcile("k1")
    ledger.cancel("k1")
    late_fill = Fill("f2", Decimal("2"), Decimal("9.25"))
    broker.orders["k1"] = OrderSnapshot(intent(), "cancelled", (first_fill, late_fill))
    ledger.reconcile("k1")
    final_fill = Fill("f3", Decimal("5"), Decimal("9.50"))
    broker.orders["k1"] = OrderSnapshot(
        intent(), "filled", (first_fill, late_fill, final_fill)
    )
    reconciled = ledger.reconcile("k1")
    assert reconciled.status == "filled"
    assert reconciled.filled_quantity == Decimal("10")
    assert reconciled.remaining_quantity == Decimal("0")
    assert ledger.cancel("k1") == reconciled
    assert broker.cancel_calls == 1


def test_lost_cancel_response_does_not_retry_cancel() -> None:
    broker = FakeBroker()
    ledger = ExecutionLedger(broker)
    ledger.submit(intent())
    broker.fail_cancel_after_accept = True
    with pytest.raises(TimeoutError, match="cancel_response_lost"):
        ledger.cancel("k1")
    with pytest.raises(ValueError, match="cancel_outcome_unknown"):
        ledger.cancel("k1")
    assert broker.cancel_calls == 1
    broker.orders["k1"] = OrderSnapshot(intent(), "open")
    assert ledger.reconcile("k1").status == "open"
    with pytest.raises(ValueError, match="cancel_outcome_unknown"):
        ledger.cancel("k1")
    assert broker.cancel_calls == 1
    broker.orders["k1"] = OrderSnapshot(intent(), "cancelled")
    assert ledger.reconcile("k1").status == "cancelled"
    assert ledger.cancel("k1").status == "cancelled"
    assert broker.cancel_calls == 1


def test_open_order_rejects_pending_status_regression() -> None:
    broker = FakeBroker()
    ledger = ExecutionLedger(broker)
    opened = ledger.submit(intent())
    broker.orders["k1"] = OrderSnapshot(intent(), "pending")
    with pytest.raises(ValueError, match="reconciliation_status_regressed"):
        ledger.reconcile("k1")
    assert ledger.submit(intent()) == opened


def test_rejected_order_is_terminal_and_cannot_be_resubmitted() -> None:
    broker = FakeBroker()
    ledger = ExecutionLedger(broker)
    ledger.submit(intent())
    broker.reject("k1")
    rejected = ledger.reconcile("k1")
    assert rejected.status == "rejected"
    assert ledger.submit(intent()) == rejected
    assert ledger.cancel("k1") == rejected
    assert broker.submit_calls == 1


def test_lost_response_does_not_retry_submit_and_reconciles() -> None:
    broker = FakeBroker()
    broker.fail_after_accept = True
    ledger = ExecutionLedger(broker)
    with pytest.raises(TimeoutError, match="response_lost"):
        ledger.submit(intent())
    assert ledger.submit(intent()).status == "pending"
    with pytest.raises(ValueError, match="order_outcome_unknown"):
        ledger.cancel("k1")
    assert ledger.reconcile("k1").status == "open"
    assert broker.submit_calls == 1


def test_restart_keeps_uncertain_submit_and_reconciles(tmp_path: Path) -> None:
    broker = FakeBroker()
    broker.fail_after_accept = True
    path = tmp_path / "orders.sqlite3"
    with pytest.raises(TimeoutError):
        ExecutionLedger(broker, path).submit(intent())
    restarted = ExecutionLedger(broker, path)
    assert restarted.submit(intent()).status == "pending"
    with pytest.raises(ValueError, match="idempotency_conflict"):
        restarted.submit(intent(quantity="11"))
    assert broker.submit_calls == 1
    assert restarted.reconcile("k1").status == "open"
    assert ExecutionLedger(broker, path).submit(intent()).status == "open"
    assert broker.submit_calls == 1


def test_restart_keeps_intent_when_submit_did_not_complete(tmp_path: Path) -> None:
    class FailingBroker(FakeBroker):
        def submit(self, intent: OrderIntent) -> OrderSnapshot:
            raise RuntimeError("submit_unavailable")

    broker = FailingBroker()
    path = tmp_path / "orders.sqlite3"
    with pytest.raises(RuntimeError, match="submit_unavailable"):
        ExecutionLedger(broker, path).submit(intent())
    restarted = ExecutionLedger(broker, path)
    assert restarted.submit(intent()).status == "pending"
    with pytest.raises(ValueError, match="broker_order_missing"):
        restarted.reconcile("k1")


def test_restart_reconciles_partial_cancel_and_late_fill(tmp_path: Path) -> None:
    broker = FakeBroker()
    path = tmp_path / "orders.sqlite3"
    ExecutionLedger(broker, path).submit(intent())
    first = Fill("f1", Decimal("3"), Decimal("9"))
    broker.fill("k1", first)
    assert ExecutionLedger(broker, path).reconcile("k1").status == "partial"
    restarted = ExecutionLedger(broker, path)
    assert restarted.submit(intent()).filled_quantity == Decimal("3")
    assert restarted.cancel("k1").status == "cancelled"
    second = Fill("f2", Decimal("2"), Decimal("9.25"))
    broker.orders["k1"] = OrderSnapshot(intent(), "cancelled", (first, second))
    final = ExecutionLedger(broker, path).reconcile("k1")
    assert final.filled_quantity == Decimal("5")
    assert ExecutionLedger(broker, path).cancel("k1") == final
    assert (broker.submit_calls, broker.cancel_calls) == (1, 1)


def test_shared_journal_cannot_overwrite_newer_fills(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    broker = FakeBroker()
    path = tmp_path / "orders.sqlite3"
    first = ExecutionLedger(broker, path)
    second = ExecutionLedger(broker, path)
    first.submit(intent())
    fill3 = Fill("f1", Decimal("3"), Decimal("9"))
    fill2 = Fill("f2", Decimal("2"), Decimal("9.25"))
    stale = OrderSnapshot(intent(), "partial", (fill3,))
    latest = OrderSnapshot(intent(), "partial", (fill3, fill2))
    broker.orders["k1"] = stale
    first.reconcile("k1")

    validating_stale = Event()
    resume_stale = Event()
    original_validate = execution_contract.validate_snapshot

    def pause_stale_validation(snapshot: OrderSnapshot) -> None:
        original_validate(snapshot)
        if snapshot is stale:
            validating_stale.set()
            if not resume_stale.wait(timeout=5):
                raise AssertionError("stale_reconciliation_not_released")

    monkeypatch.setattr(execution_contract, "validate_snapshot", pause_stale_validation)
    with ThreadPoolExecutor(max_workers=2) as pool:
        stale_future = pool.submit(first.reconcile, "k1")
        assert validating_stale.wait(timeout=5)
        broker.orders["k1"] = latest
        latest_future = pool.submit(second.reconcile, "k1")
        try:
            # The old two-transaction path can commit while validation is paused.
            latest_future.result(timeout=2)
        except TimeoutError:
            # The atomic path waits for the first ledger's writer lock.
            pass
        finally:
            resume_stale.set()
        assert stale_future.result(timeout=5) == stale
        assert latest_future.result(timeout=5) == latest

    restarted = ExecutionLedger(broker, path)
    assert restarted.submit(intent()) == latest
    broker.orders["k1"] = stale
    with pytest.raises(ValueError, match="reconciliation_fill_mismatch"):
        restarted.reconcile("k1")
    assert restarted._orders == {}
    assert ExecutionLedger(broker, path).submit(intent()) == latest


def test_restart_does_not_retry_uncertain_cancel_or_rejection(tmp_path: Path) -> None:
    broker = FakeBroker()
    path = tmp_path / "orders.sqlite3"
    ExecutionLedger(broker, path).submit(intent())
    broker.fail_cancel_after_accept = True
    with pytest.raises(TimeoutError):
        ExecutionLedger(broker, path).cancel("k1")
    restarted = ExecutionLedger(broker, path)
    with pytest.raises(ValueError, match="cancel_outcome_unknown"):
        restarted.cancel("k1")
    broker.orders["k1"] = OrderSnapshot(intent(), "open")
    restarted.reconcile("k1")
    with pytest.raises(ValueError, match="cancel_outcome_unknown"):
        ExecutionLedger(broker, path).cancel("k1")
    assert broker.cancel_calls == 1
    broker.reject("k1")
    assert ExecutionLedger(broker, path).reconcile("k1").status == "rejected"
    final = ExecutionLedger(broker, path)
    assert final.submit(intent()).status == "rejected"
    assert final.cancel("k1").status == "rejected"
    assert (broker.submit_calls, broker.cancel_calls) == (1, 1)


def test_missing_or_divergent_broker_state_fails_closed() -> None:
    broker = FakeBroker()
    ledger = ExecutionLedger(broker)
    ledger.submit(intent())
    broker.orders.pop("k1")
    with pytest.raises(ValueError, match="broker_order_missing"):
        ledger.reconcile("k1")
    broker.orders["k1"] = OrderSnapshot(intent(quantity="11"), "open")
    with pytest.raises(ValueError, match="reconciliation_identity_mismatch"):
        ledger.reconcile("k1")


def test_missing_order_after_lost_response_remains_pending() -> None:
    broker = FakeBroker()
    broker.fail_after_accept = True
    ledger = ExecutionLedger(broker)
    with pytest.raises(TimeoutError):
        ledger.submit(intent())
    broker.orders.pop("k1")
    with pytest.raises(ValueError, match="broker_order_missing"):
        ledger.reconcile("k1")
    assert ledger.submit(intent()).status == "pending"
    assert broker.submit_calls == 1


def test_cancel_response_cannot_erase_a_recorded_fill() -> None:
    broker = FakeBroker()
    ledger = ExecutionLedger(broker)
    ledger.submit(intent())
    broker.fill("k1", Fill("f1", Decimal("2"), Decimal("10")))
    ledger.reconcile("k1")
    broker.orders["k1"] = OrderSnapshot(intent(), "open")
    with pytest.raises(ValueError, match="reconciliation_fill_mismatch"):
        ledger.cancel("k1")


def test_duplicate_overfill_and_regressed_fills_fail_closed() -> None:
    broker = FakeBroker()
    ledger = ExecutionLedger(broker)
    ledger.submit(intent())
    fill = Fill("f1", Decimal("3"), Decimal("10"))
    broker.orders["k1"] = OrderSnapshot(intent(), "partial", (fill, fill))
    with pytest.raises(ValueError, match="order_fills_invalid"):
        ledger.reconcile("k1")
    broker.orders["k1"] = OrderSnapshot(intent(), "partial", (fill,))
    ledger.reconcile("k1")
    broker.orders["k1"] = OrderSnapshot(intent(), "open")
    with pytest.raises(ValueError, match="reconciliation_fill_mismatch"):
        ledger.reconcile("k1")
    broker.orders["k1"] = OrderSnapshot(
        intent(), "partial", (Fill("f1", Decimal("11"), Decimal("10")),)
    )
    with pytest.raises(ValueError, match="order_fills_invalid"):
        ledger.reconcile("k1")


def test_overfill_is_rejected_with_low_decimal_precision() -> None:
    snapshot = OrderSnapshot(
        intent(),
        "filled",
        (
            Fill("f1", Decimal("10"), Decimal("1")),
            Fill("f2", Decimal("0.1"), Decimal("1")),
        ),
    )
    with localcontext() as context:
        context.prec = 2
        assert snapshot.filled_quantity == Decimal("10.1")
        assert snapshot.remaining_quantity == Decimal("-0.1")
        with pytest.raises(ValueError, match="order_fills_invalid"):
            validate_snapshot(snapshot)


@pytest.mark.parametrize("quantity", ["0", "-1", "NaN", "Infinity"])
def test_invalid_order_quantities(quantity: str) -> None:
    with pytest.raises(ValueError, match="order_quantity_invalid"):
        intent(quantity=quantity)
