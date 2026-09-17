from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest

from jusik.market_history_action_accounting import (
    AccountingError,
    AccountingState,
    DividendAction,
    Holding,
    SplitAction,
    accrue_dividend,
    action_identity,
    apply_split,
    legacy_corporate_action_to_action,
    normalize_action_payload,
    pay_dividend,
)
from jusik.market_history_models import CorporateAction, MarketHistorySnapshot

FIXTURE_PATH = Path(__file__).parent / "fixtures/market_history_action_accounting.json"
NOW = datetime(2026, 9, 17, 0, 0, tzinfo=UTC)
EFFECTIVE = datetime(2026, 9, 17, 0, 0, tzinfo=UTC)
FIXTURES = cast(dict[str, object], json.loads(FIXTURE_PATH.read_text(encoding="utf-8")))


def _state(
    *,
    quantity: str = "10",
    price: str = "123.45",
    total_cost: str = "1000",
    currency: str = "KRW",
    cash: str = "0",
) -> AccountingState:
    return AccountingState(
        holdings=(
            Holding(
                symbol="AAA",
                quantity=Decimal(quantity),
                raw_price=Decimal(price),
                total_cost=Decimal(total_cost),
                currency=currency,  # type: ignore[arg-type]
            ),
        ),
        cash=Decimal(cash),
    )


def _scenario(scenario_id: str) -> dict[str, object]:
    scenarios = cast(list[object], FIXTURES["scenarios"])
    for value in scenarios:
        scenario = cast(dict[str, object], value)
        if scenario["id"] == scenario_id:
            return scenario
    raise AssertionError(f"unknown fixture scenario: {scenario_id}")


def _fixture_state(scenario_id: str, key: str = "state") -> AccountingState:
    payload = cast(dict[str, str], _scenario(scenario_id)[key])
    return _state(
        quantity=payload["quantity"],
        price=payload["raw_price"],
        total_cost=payload["total_cost"],
        cash=payload["cash"],
        currency=payload["currency"],
    )


def _fixture_split(scenario_id: str, key: str = "action") -> SplitAction:
    payload = cast(dict[str, object], _scenario(scenario_id)[key])
    return SplitAction(
        action_id=cast(str, payload["action_id"]),
        symbol="AAA",
        effective_at=datetime.fromisoformat(cast(str, payload["effective_at"])),
        ratio=Decimal(cast(str, payload["ratio"])),
        currency=cast(str, payload["currency"]),  # type: ignore[arg-type]
        price_basis=cast(str, payload["price_basis"]),  # type: ignore[arg-type]
        before_price=(
            None
            if payload["before_price"] is None
            else Decimal(cast(str, payload["before_price"]))
        ),
        after_price=(
            None
            if payload["after_price"] is None
            else Decimal(cast(str, payload["after_price"]))
        ),
    )


def _fixture_dividend(scenario_id: str, key: str = "action") -> DividendAction:
    payload = cast(dict[str, object], _scenario(scenario_id)[key])
    entitled = payload["entitled_quantity"]
    return DividendAction(
        action_id=cast(str, payload["action_id"]),
        symbol="AAA",
        effective_at=datetime.fromisoformat(cast(str, payload["effective_at"])),
        payment_at=datetime.fromisoformat(cast(str, payload["payment_at"])),
        amount_per_share=Decimal(cast(str, payload["amount_per_share"])),
        currency=cast(str, payload["currency"]),  # type: ignore[arg-type]
        entitled_quantity=(None if entitled is None else Decimal(cast(str, entitled))),
        entitlement_confirmed=payload["entitlement_confirmed"] is True,
        price_basis=cast(str, payload["price_basis"]),  # type: ignore[arg-type]
    )


def _split(
    *,
    action_id: str = "split-1",
    ratio: str = "2",
    currency: str = "KRW",
    price_basis: str = "raw",
    before_price: Decimal | None = None,
    after_price: Decimal | None = None,
) -> SplitAction:
    if before_price is None and after_price is None and ratio == "2":
        before_price = Decimal("123.45")
        after_price = Decimal("61.725")
    return SplitAction(
        action_id=action_id,
        symbol="AAA",
        effective_at=EFFECTIVE,
        ratio=Decimal(ratio),
        currency=currency,  # type: ignore[arg-type]
        price_basis=price_basis,  # type: ignore[arg-type]
        before_price=before_price,
        after_price=after_price,
    )


def _dividend(
    *,
    action_id: str = "dividend-1",
    amount: str = "0.123456789012345678901234567890",
    entitled_quantity: Decimal | None = Decimal("10"),
    confirmed: bool = True,
    currency: str = "KRW",
    price_basis: str = "raw",
    effective_at: datetime = EFFECTIVE,
    payment_at: datetime = datetime(2026, 9, 19, 0, 0, tzinfo=UTC),
) -> DividendAction:
    return DividendAction(
        action_id=action_id,
        symbol="AAA",
        effective_at=effective_at,
        payment_at=payment_at,
        amount_per_share=Decimal(amount),
        currency=currency,  # type: ignore[arg-type]
        entitled_quantity=entitled_quantity,
        entitlement_confirmed=confirmed,
        price_basis=price_basis,  # type: ignore[arg-type]
    )


def test_fixture_inventory_is_fixed_and_seeded() -> None:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    scenarios = fixture["scenarios"]
    assert fixture["seed"] == 0
    assert len(scenarios) == 19
    assert len({item["id"] for item in scenarios}) == 19
    assert [item["id"] for item in scenarios] == [
        "legacy_split_json_hash",
        "raw_two_for_one_split",
        "reverse_fractional_split",
        "dividend_long_decimal_accrual_payment",
        "zero_holding",
        "negative_holding",
        "zero_split_ratio",
        "negative_dividend_amount",
        "missing_entitlement",
        "missing_raw_price",
        "adjusted_price_basis",
        "unknown_price_basis",
        "identical_replay",
        "conflicting_action_id",
        "utc_boundary_holiday_payment",
        "naive_timestamp",
        "empty_incomplete_approximate_snapshot",
        "currency_mismatch",
        "non_terminating_decimal_rejection",
    ]
    for scenario in scenarios:
        assert isinstance(scenario.get("state") or scenario.get("snapshot"), dict)
        if scenario["kind"] != "snapshot":
            action = scenario["action"]
            assert isinstance(action, dict)
            assert action.get("price_basis") in {"raw", "adjusted", "unknown"}


def test_legacy_split_adapter_preserves_input_json_and_hash() -> None:
    legacy = CorporateAction(
        market="KR",
        symbol="AAA",
        session=date(2026, 9, 17),
        kind="split",
        ratio=Decimal("2"),
        available_at=NOW,
        captured_at=NOW,
        source="fixture",
        source_hash="a" * 64,
    )
    original_json = legacy.model_dump_json()
    snapshot = MarketHistorySnapshot(
        market="KR",
        requested_start=date(2026, 9, 17),
        requested_end=date(2026, 9, 17),
        captured_at=NOW,
        memberships=(),
        bars=(),
        actions=(legacy,),
        completeness="incomplete",
        missing_ranges=("bars",),
        research_grade="approximate",
    )
    converted = legacy_corporate_action_to_action(
        legacy,
        effective_at=EFFECTIVE,
        price_basis="raw",
    )
    assert converted.ratio == Decimal("2")
    assert legacy.model_dump_json() == original_json
    assert snapshot.input_hash == (
        "93a9e3994bea1524fb7d5bccc412e46f6359bfde14814aaa2d8aa92185a944a0"
    )
    assert snapshot.actions == (legacy,)


def test_raw_two_for_one_split_preserves_fractional_asset_value_and_cost() -> None:
    state = _fixture_state("raw_two_for_one_split")
    action = _fixture_split("raw_two_for_one_split")
    result = apply_split(state, action, at=action.effective_at)
    assert result.status == "applied"
    assert result.state.holdings[0].quantity == Decimal("20")
    assert result.state.holdings[0].raw_price == Decimal("61.725")
    assert result.state.holdings[0].total_cost == Decimal("1000")
    assert result.nav_before == result.nav_after == Decimal("1234.50")


def test_split_result_nav_includes_all_holdings_cash_and_receivables() -> None:
    state = AccountingState(
        holdings=(
            Holding("AAA", Decimal("10"), Decimal("123.45"), Decimal("1000"), "KRW"),
            Holding("BBB", Decimal("3"), Decimal("50"), Decimal("150"), "KRW"),
        ),
        cash=Decimal("5"),
    )
    dividend = _dividend(action_id="dividend-nav", amount="0.1")
    accrued = accrue_dividend(state, dividend, at=dividend.effective_at)
    assert accrued.status == "applied"
    result = apply_split(
        accrued.state,
        _split(action_id="split-nav"),
        at=EFFECTIVE,
    )
    assert result.status == "applied"
    assert result.nav_before == result.nav_after == Decimal("1390.5")


def test_reverse_fractional_split_preserves_long_decimals() -> None:
    state = _fixture_state("reverse_fractional_split")
    action = _fixture_split("reverse_fractional_split")
    result = apply_split(state, action, at=action.effective_at)
    assert result.status == "applied"
    assert result.state.holdings[0].quantity == Decimal("1.25")
    assert result.state.holdings[0].raw_price == Decimal(
        "246.913578024691357802469135780"
    )
    assert result.nav_before == result.nav_after


def test_dividend_accrual_then_payment_uses_frozen_entitlement() -> None:
    state = _fixture_state("dividend_long_decimal_accrual_payment")
    action = _fixture_dividend("dividend_long_decimal_accrual_payment")
    accrued = accrue_dividend(state, action, at=action.effective_at)
    assert accrued.status == "applied"
    assert accrued.state.cash == Decimal("1.00")
    assert accrued.state.receivables[0].gross_amount == Decimal(
        "1.234567890123456789012345678900"
    )
    assert accrued.state.nav == Decimal("1236.734567890123456789012345678900")
    changed_input = _fixture_state(
        "dividend_long_decimal_accrual_payment", key="changed_state"
    )
    changed = AccountingState(
        holdings=changed_input.holdings,
        cash=changed_input.cash,
        receivables=accrued.state.receivables,
        action_records=accrued.state.action_records,
    )
    paid = pay_dividend(changed, action, at=action.payment_at)
    assert paid.status == "applied"
    assert paid.state.cash == Decimal("2.234567890123456789012345678900")
    assert paid.state.receivables == ()
    assert paid.state.nav == changed.nav
    assert paid.state.nav == Decimal("101.234567890123456789012345678900")


def test_zero_holding_split_is_an_exact_no_value_transition() -> None:
    state = _fixture_state("zero_holding")
    action = _fixture_split("zero_holding")
    result = apply_split(state, action, at=action.effective_at)
    assert result.status == "applied"
    assert result.state.holdings[0].quantity == Decimal("0")
    assert result.nav_before == result.nav_after == Decimal("0")


def test_negative_holding_is_rejected_atomically() -> None:
    state = _fixture_state("negative_holding")
    action = _fixture_split("negative_holding")
    result = apply_split(state, action, at=action.effective_at)
    assert result.status == "rejected"
    assert result.state == state


def test_zero_split_ratio_is_rejected_atomically() -> None:
    state = _fixture_state("zero_split_ratio")
    action = _fixture_split("zero_split_ratio")
    result = apply_split(state, action, at=action.effective_at)
    assert result.status == "rejected"
    assert result.state == state


def test_negative_dividend_amount_is_rejected_atomically() -> None:
    state = _fixture_state("negative_dividend_amount")
    action = _fixture_dividend("negative_dividend_amount")
    result = accrue_dividend(state, action, at=action.effective_at)
    assert result.status == "rejected"
    assert result.state == state


def test_missing_entitlement_is_insufficient_and_atomic() -> None:
    state = _fixture_state("missing_entitlement")
    action = _fixture_dividend("missing_entitlement")
    result = accrue_dividend(state, action, at=action.effective_at)
    assert result.status == "insufficient"
    assert "missing" in (result.reason or "")
    assert result.state == state


def test_missing_raw_price_marks_are_insufficient_and_atomic() -> None:
    state = _fixture_state("missing_raw_price")
    action = _fixture_split("missing_raw_price")
    result = apply_split(state, action, at=action.effective_at)
    assert result.status == "insufficient"
    assert result.state == state


def test_adjusted_price_basis_is_unsupported() -> None:
    state = _fixture_state("adjusted_price_basis")
    action = _fixture_dividend("adjusted_price_basis")
    result = accrue_dividend(state, action, at=action.effective_at)
    assert result.status == "unsupported"
    assert "unsupported" in (result.reason or "")
    assert result.state == state
    replay = accrue_dividend(state, action, at=action.effective_at)
    assert replay.status == "unsupported"
    assert replay.state == state


def test_unknown_price_basis_is_unsupported() -> None:
    state = _fixture_state("unknown_price_basis")
    action = _fixture_split("unknown_price_basis")
    result = apply_split(state, action, at=action.effective_at)
    assert result.status == "unsupported"
    assert "unsupported" in (result.reason or "")
    assert result.state == state


def test_identical_action_replay_does_not_change_state() -> None:
    state = _fixture_state("identical_replay")
    action = _fixture_dividend("identical_replay")
    first = accrue_dividend(state, action, at=action.effective_at)
    accrual_replay = accrue_dividend(first.state, action, at=action.effective_at)
    assert accrual_replay.status == "replayed"
    paid = pay_dividend(first.state, action, at=action.payment_at)
    payment_replay = pay_dividend(paid.state, action, at=action.payment_at)
    assert payment_replay.status == "replayed"
    assert payment_replay.state == paid.state


def test_action_id_conflict_includes_price_and_currency_semantics() -> None:
    state = _fixture_state("conflicting_action_id")
    original = _fixture_split("conflicting_action_id")
    conflicting_action = _fixture_split("conflicting_action_id", "conflicting_action")
    first = apply_split(state, original, at=original.effective_at)
    conflicting = apply_split(first.state, conflicting_action, at=original.effective_at)
    assert conflicting.status == "rejected"
    assert conflicting.reason == "action_id_conflict"
    assert conflicting.state == first.state
    assert action_identity(original) != action_identity(conflicting_action)


def test_payment_accepts_explicit_utc_holiday_boundary() -> None:
    kst = timezone(timedelta(hours=9))
    state = _fixture_state("utc_boundary_holiday_payment")
    action = _fixture_dividend("utc_boundary_holiday_payment")
    accrued = accrue_dividend(state, action, at=action.effective_at)
    before = pay_dividend(
        accrued.state,
        action,
        at=datetime(2026, 9, 19, 8, 59, tzinfo=kst),
    )
    assert before.status == "rejected"
    assert before.state == accrued.state
    paid = pay_dividend(accrued.state, action, at=action.payment_at)
    assert paid.status == "applied"


def test_naive_timestamp_is_rejected_atomically() -> None:
    state = _fixture_state("naive_timestamp")
    action = _fixture_dividend("naive_timestamp")
    result = accrue_dividend(state, action, at=action.effective_at)
    assert result.status == "rejected"
    assert "timezone" in (result.reason or "")
    assert result.state == state


def test_empty_incomplete_approximate_snapshot_remains_empty() -> None:
    snapshot = MarketHistorySnapshot(
        market="KR",
        requested_start=date(2026, 1, 1),
        requested_end=date(2026, 1, 2),
        captured_at=NOW,
        memberships=(),
        bars=(),
        actions=(),
        completeness="incomplete",
        missing_ranges=("actions",),
        research_grade="approximate",
    )
    assert snapshot.actions == ()
    assert snapshot.completeness == "incomplete"
    assert snapshot.research_grade == "approximate"


def test_currency_mismatch_is_rejected_atomically() -> None:
    state = _fixture_state("currency_mismatch")
    action = _fixture_split("currency_mismatch")
    result = apply_split(state, action, at=action.effective_at)
    assert result.status == "rejected"
    assert "currencies" in (result.reason or "")
    assert result.state == state


def test_non_terminating_decimal_is_rejected_without_rounding() -> None:
    state = _fixture_state("non_terminating_decimal_rejection")
    action = _fixture_split("non_terminating_decimal_rejection")
    result = apply_split(state, action, at=action.effective_at)
    assert result.status == "rejected"
    assert result.reason == "decimal_operation_rejected"
    assert result.state == state


def test_payment_rejects_changed_frozen_receivable_atomically() -> None:
    state = _state()
    action = _dividend(action_id="dividend-frozen", amount="0.1")
    accrued = accrue_dividend(state, action, at=action.effective_at)
    assert accrued.status == "applied"
    original = accrued.state.receivables[0]
    tampered = replace(
        accrued.state,
        receivables=(
            replace(
                original,
                entitled_quantity=Decimal("11"),
                gross_amount=Decimal("1.1"),
            ),
        ),
    )
    result = pay_dividend(tampered, action, at=action.payment_at)
    assert result.status == "rejected"
    assert result.reason == "payment semantics conflict with accrued entitlement"
    assert result.state == tampered


def test_direct_dataclass_entitlement_confirmation_requires_bool() -> None:
    state = _state()
    action = replace(
        _dividend(action_id="dividend-bool"),
        entitlement_confirmed=cast(bool, "yes"),
    )
    result = accrue_dividend(state, action, at=action.effective_at)
    assert result.status == "rejected"
    assert result.reason == "entitlement_confirmed must be a bool"
    assert result.state == state


def test_payload_entitlement_confirmation_requires_bool() -> None:
    with pytest.raises(AccountingError, match="entitlement_confirmed must be a bool"):
        normalize_action_payload(
            {
                "kind": "dividend",
                "action_id": "dividend-payload-bool",
                "symbol": "AAA",
                "effective_at": EFFECTIVE,
                "payment_at": datetime(2026, 9, 19, 0, 0, tzinfo=UTC),
                "amount_per_share": "0.1",
                "currency": "KRW",
                "entitled_quantity": "10",
                "entitlement_confirmed": 1,
                "price_basis": "raw",
            }
        )


def test_split_without_holding_is_insufficient_and_atomic() -> None:
    state = _state()
    action = replace(_split(action_id="split-missing-holding"), symbol="MISSING")
    result = apply_split(state, action, at=action.effective_at)
    assert result.status == "insufficient"
    assert result.state == state


def test_duplicate_holding_symbols_are_rejected_atomically() -> None:
    state = _state()
    duplicate = replace(state, holdings=state.holdings + state.holdings)
    result = apply_split(duplicate, _split(action_id="split-duplicate"), at=EFFECTIVE)
    assert result.status == "rejected"
    assert result.reason == "duplicate holding symbol"
    assert result.state == duplicate
