"""Synthetic selected signals through the one KR raw accounting loop."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

import pytest

from jusik.approved_universe_buy_hold import (
    CostAssumptions,
    DividendEvent,
    FrozenReferenceInput,
    HoldQuantityInstruction,
    Instrument,
    RateAssumption,
    RawSession,
    ReferenceInputError,
    SellCostAssumptions,
    TargetInstruction,
    _run_reference_core,
)
from jusik.selected_candidate_kr_policy import (
    PolicyInputError,
    RiskPolicyRequired,
    _hold_in_band,
    _schedule,
    run_kr_selected_candidate_reference,
)
from jusik.selected_candidate_signals import AdjustedClose, FrozenSignalInput

D = Decimal
PIN = "a" * 64
SIGNAL_PRICE_PIN = "b" * 64
RAW_PRICE_PIN = "c" * 64
CALENDAR_PIN = "d" * 64
CONFIG = Path(__file__).parents[2] / "docs/research/selected-candidate-config-v1.json"
CONFIG_BYTES = CONFIG.read_bytes()
CONFIG_HASH = hashlib.sha256(CONFIG_BYTES).hexdigest()
FIRST = datetime(2026, 3, 9, tzinfo=UTC)
SECOND = FIRST + timedelta(days=28)
END = SECOND + timedelta(days=1, hours=4)
AMPS = (".01", ".02", ".04", ".04")


def rate(value: str) -> RateAssumption:
    return RateAssumption(D(value), "explicit synthetic test", PIN)


def costs(buy: str = ".01") -> CostAssumptions:
    zero = rate("0")
    return CostAssumptions(rate(buy), zero, zero, zero, zero, zero, zero, zero, zero)


def sell_costs(sell: str = ".01") -> SellCostAssumptions:
    zero = rate("0")
    return SellCostAssumptions(rate(sell), zero, zero, zero, zero, zero, "notional")


def fixture(
    *,
    high_close: str = "160",
    buy: str = ".01",
    dividend: bool = False,
) -> tuple[FrozenReferenceInput, FrozenSignalInput]:
    items = tuple(Instrument("KR", "KRX", symbol, PIN, False) for symbol in "ABCD")
    day_25 = FIRST + timedelta(days=16)
    opens = (
        FIRST,
        FIRST + timedelta(days=1),
        day_25,
        SECOND,
        SECOND + timedelta(days=1),
    )
    sessions = tuple(
        RawSession(
            item,
            at,
            at + timedelta(hours=3),
            (
                D(high_close)
                if item.symbol == "A"
                else D(50)
                if item.symbol == "D"
                else D(100)
            )
            if at >= day_25
            else D(100),
            (
                D(high_close)
                if item.symbol == "A"
                else D(50)
                if item.symbol == "D"
                else D(100)
            )
            if at >= day_25
            else D(100),
            at,
            at + timedelta(hours=3),
        )
        for at in opens
        for item in items
    )
    actions = (
        (DividendEvent(items[1], "B-cash", day_25, SECOND, day_25, D(1), D(0), PIN),)
        if dividend
        else ()
    )
    raw = FrozenReferenceInput(
        1,
        PIN,
        items,
        items,
        "synthetic policy KR",
        FIRST,
        END,
        sessions,
        CALENDAR_PIN,
        True,
        RAW_PRICE_PIN,
        True,
        actions,
        PIN,
        True,
        (),
        PIN,
        True,
        costs(buy),
    )
    start = datetime(2025, 12, 1, 16, tzinfo=UTC)
    rows: list[AdjustedClose] = []
    for item, amp in zip(items, AMPS, strict=True):
        price = D(100)
        for index in range(126):
            if index:
                sign = D(1) if index % 2 == 0 else D(-1)
                price *= 1 + D(".01") + sign * D(amp)
            at = start + timedelta(days=index)
            rows.append(
                AdjustedClose(
                    item,
                    at,
                    at,
                    price,
                    1,
                    "split_adjusted_close_for_signal_only",
                )
            )
    signal = FrozenSignalInput(
        1,
        PIN,
        items,
        items,
        CONFIG_HASH,
        SIGNAL_PRICE_PIN,
        PIN,
        CALENDAR_PIN,
        "synthetic_unverified",
        tuple(rows),
        (),
        FIRST,
    )
    return raw, signal


def test_two_methods_two_28_day_decisions_and_raw_arithmetic() -> None:
    raw, signal = fixture()
    equal = run_kr_selected_candidate_reference(
        raw, signal, CONFIG_BYTES, "equal", sell_costs()
    )
    inverse = run_kr_selected_candidate_reference(
        raw, signal, CONFIG_BYTES, "inverse_volatility", sell_costs()
    )
    assert [x.at for x in equal.decisions] == [FIRST, SECOND]
    assert [x.at for x in inverse.decisions] == [FIRST, SECOND]
    assert all(x.signal.status == "ready" for x in equal.decisions + inverse.decisions)
    assert all(x.signal.config_sha256 == CONFIG_HASH for x in equal.decisions)
    assert equal.status == inverse.status == "synthetic_reference_only"
    assert (
        equal.investment_qualification
        == inverse.investment_qualification
        == "not_evaluated"
    )
    assert all(batch.open_at > batch.decided_at for batch in equal.ledger.batches)
    assert equal.ledger.batches[0].open_at == FIRST + timedelta(days=1)
    assert equal.ledger.batches[1].open_at == SECOND + timedelta(days=1)
    assert equal.ledger.points[0].positions == ()
    assert all(trade.at > FIRST for trade in equal.ledger.trades)
    equal_weights = tuple(x.weight for x in equal.decisions[0].signal.targets or ())
    inverse_weights = tuple(x.weight for x in inverse.decisions[0].signal.targets or ())
    assert (
        tuple(x.weight for x in equal.decisions[0].signal.pre_scale or ())
        == (D(".15"),) * 4
    )
    assert all(
        abs(actual - expected) < D("1e-22")
        for actual, expected in zip(
            (x.weight for x in inverse.decisions[0].signal.pre_scale or ()),
            (D(".2"), D(".2"), D(".1"), D(".1")),
            strict=True,
        )
    )
    assert sum(equal_weights) < D(".60")
    assert sum(inverse_weights) < D(".60")
    # Independent first-fill arithmetic: Nmin = N0 - 1% of upper exposure.
    for result, weights in ((equal, equal_weights), (inverse, inverse_weights)):
        upper = [Fraction(weight) * 100000000 // 100 for weight in weights]
        n_min = Fraction(100000000) - sum(upper)
        expected = tuple(D(Fraction(weight) * n_min // 100) for weight in weights)
        first = tuple(
            trade.quantity
            for trade in result.ledger.trades
            if trade.at == FIRST + timedelta(days=1)
        )
        assert first == expected
        point = next(
            p
            for p in result.ledger.points
            if p.at == FIRST + timedelta(days=1) and p.phase == "open"
        )
        assert Fraction(point.nav_krw) == Fraction(100000000) - sum(
            Fraction(q) for q in expected
        )
        assert Fraction(point.cash_krw) == Fraction(100000000) - 101 * sum(
            Fraction(q) for q in expected
        )
    assert equal.decisions[1].hold_quantities
    assert equal.ledger.sales
    assert inverse.ledger.sales
    assert equal.ledger.leverage_breached is False
    assert inverse.ledger.leverage_breached is False
    for result in (equal, inverse):
        before = next(
            p
            for p in result.ledger.points
            if p.at == SECOND + timedelta(days=1) and p.phase == "pre_rebalance"
        )
        targets = result.decisions[1].signal.targets
        assert targets is not None
        held = {p.instrument: Fraction(p.quantity) for p in before.positions}
        n0 = Fraction(before.nav_krw)
        wa, wd = Fraction(targets[0].weight), Fraction(targets[3].weight)
        buy_upper = max(0, (wd * n0 - held[raw.cohort[3]] * 50) // 50)
        n_ref = n0 - buy_upper * Fraction(1, 2)
        sale_need = (held[raw.cohort[0]] * 160 - wa * n_ref) / (
            160 - wa * Fraction(8, 5)
        )
        sale_a = -(-sale_need.numerator // sale_need.denominator)
        n_ref -= sale_a * Fraction(8, 5)
        buy_d = max(0, (wd * n_ref - held[raw.cohort[3]] * 50) // 50)
        assert result.ledger.batches[1].sold == ((raw.cohort[0], D(sale_a)),)
        assert result.ledger.batches[1].bought == ((raw.cohort[3], D(buy_d)),)
        after = next(
            p
            for p in result.ledger.points
            if p.at == SECOND + timedelta(days=1) and p.phase == "open"
        )
        assert Fraction(after.nav_krw) == n0 - sale_a * Fraction(
            8, 5
        ) - buy_d * Fraction(1, 2)
        assert Fraction(after.cash_krw) == Fraction(
            before.cash_krw
        ) + sale_a * Fraction(792, 5) - buy_d * Fraction(101, 2)


def test_strict_band_boundary_and_zero_exemption() -> None:
    assert _hold_in_band(D(".15"), D("13.01"), D(100), caps_clear=True)
    assert not _hold_in_band(D(".15"), D(13), D(100), caps_clear=True)
    assert not _hold_in_band(D(0), D(0), D(100), caps_clear=True)
    assert not _hold_in_band(D(".15"), D("13.01"), D(100), caps_clear=False)


def test_held_quantity_survives_other_trade_costs_without_fake_target() -> None:
    raw, signal = fixture()
    result = run_kr_selected_candidate_reference(
        raw, signal, CONFIG_BYTES, "equal", sell_costs(".5")
    )
    held = dict(result.decisions[1].hold_quantities)
    assert held[raw.cohort[1]] == held[raw.cohort[2]] == D(57136)
    final = next(
        point
        for point in result.ledger.points
        if point.at == SECOND + timedelta(days=1) and point.phase == "open"
    )
    positions = {p.instrument: p for p in final.positions}
    assert positions[raw.cohort[1]].quantity == held[raw.cohort[1]]
    assert positions[raw.cohort[2]].quantity == held[raw.cohort[2]]
    target = result.decisions[1].signal.targets
    assert target is not None
    assert Fraction(positions[raw.cohort[1]].value_krw) / Fraction(
        final.nav_krw
    ) > Fraction(target[1].weight)
    assert positions[raw.cohort[1]].value_krw <= D(".20") * final.nav_krw
    assert result.ledger.sales[0].instrument == raw.cohort[0]


def test_held_post_cost_hard_cap_requires_unsupported_repair() -> None:
    raw, _ = fixture(buy="0")
    raw = replace(
        raw,
        sessions=tuple(
            replace(bar, raw_open=D(100), raw_close=D(100)) for bar in raw.sessions
        ),
    )

    def decision(
        at: datetime, prior: object
    ) -> tuple[HoldQuantityInstruction | TargetInstruction, ...]:
        if at == FIRST:
            return tuple(
                TargetInstruction(item, at, D(weight))
                for item, weight in zip(raw.cohort, (".2", ".1", "0", "0"), strict=True)
            )
        positions = {p.instrument: p.quantity for p in prior.positions}  # type: ignore[attr-defined]
        return (
            HoldQuantityInstruction(
                raw.cohort[0], at, D(".2"), positions[raw.cohort[0]]
            ),
            *(TargetInstruction(item, at, D(0)) for item in raw.cohort[1:]),
        )

    with pytest.raises(
        ReferenceInputError, match="held quantity post-cost cap requires repair"
    ):
        _run_reference_core(
            raw,
            sell_costs=sell_costs(".9"),
            kr_decision_times=(FIRST, SECOND),
            kr_decision_hook=decision,
            kr_close_hook=lambda _: None,
        )


def test_zero_exit_ignores_band_and_entitlement_survives_sale() -> None:
    raw, signal = fixture()
    b, d = raw.cohort[1], raw.cohort[3]
    day_25 = FIRST + timedelta(days=16)
    raw = replace(
        raw,
        sessions=tuple(
            replace(bar, raw_open=D(20), raw_close=D(20))
            if bar.instrument == b and bar.open_at >= day_25
            else bar
            for bar in raw.sessions
        ),
        actions=(
            DividendEvent(b, "B-ex", day_25, END, day_25, D(1), D(0), PIN),
            DividendEvent(
                d,
                "D-ex",
                SECOND + timedelta(days=1),
                END,
                SECOND + timedelta(days=1),
                D(1),
                D(0),
                PIN,
            ),
        ),
    )
    signal = replace(
        signal,
        closes=tuple(
            replace(row, adjusted_close=D(1))
            if row.instrument == b and FIRST < row.official_close_at < SECOND
            else row
            for row in signal.closes
        ),
    )
    result = run_kr_selected_candidate_reference(
        raw, signal, CONFIG_BYTES, "equal", sell_costs()
    )
    second_targets = result.decisions[1].signal.targets
    assert second_targets is not None and second_targets[1].weight == 0
    prior = next(
        p for p in result.ledger.points if p.at == SECOND and p.phase == "decision"
    )
    prior_b = next(p for p in prior.positions if p.instrument == b)
    assert prior_b.value_krw / prior.nav_krw < D(".02")
    assert prior.receivables_krw > 0
    assert any(sale.instrument == b for sale in result.ledger.sales)
    entries = [entry for entry in result.ledger.dividends if entry.action_id == "B-ex"]
    assert [entry.phase for entry in entries] == ["accrual", "payment"]
    assert entries[0].quantity == entries[1].quantity == prior_b.quantity
    d_entries = [
        entry for entry in result.ledger.dividends if entry.action_id == "D-ex"
    ]
    before_buy = next(
        p
        for p in result.ledger.points
        if p.at == SECOND + timedelta(days=1) and p.phase == "pre_rebalance"
    )
    original_d = next(p.quantity for p in before_buy.positions if p.instrument == d)
    assert [entry.quantity for entry in d_entries] == [original_d, original_d]
    assert any(
        trade.instrument == d and trade.at == before_buy.at
        for trade in result.ledger.trades
    )
    assert result.ledger.points[-1].receivables_krw == 0


def test_late_adjusted_revision_cannot_poison_past_policy_output() -> None:
    raw, signal = fixture()
    base = run_kr_selected_candidate_reference(
        raw, signal, CONFIG_BYTES, "equal", sell_costs()
    )
    original = next(row for row in signal.closes if row.instrument == raw.cohort[0])
    poison = replace(
        original,
        available_at=END + timedelta(days=1),
        adjusted_close=D("999999"),
        revision=2,
    )
    changed = run_kr_selected_candidate_reference(
        raw,
        replace(signal, closes=signal.closes + (poison,)),
        CONFIG_BYTES,
        "equal",
        sell_costs(),
    )
    assert asdict(changed) == asdict(base)


def test_decision_precedes_same_timestamp_payment_and_open() -> None:
    raw, signal = fixture(dividend=True)
    result = run_kr_selected_candidate_reference(
        raw, signal, CONFIG_BYTES, "equal", sell_costs()
    )
    prior = next(
        point
        for point in result.ledger.points
        if point.at == SECOND and point.phase == "decision"
    )
    after = next(
        point
        for point in result.ledger.points
        if point.at == SECOND and point.phase == "open"
    )
    assert prior.receivables_krw > 0
    assert after.receivables_krw == 0
    assert prior.nav_krw == after.nav_krw
    assert not any(trade.at == SECOND for trade in result.ledger.trades)


def test_risk_at_completed_close_fails_closed_and_lifetime_is_separate() -> None:
    raw, signal = fixture()
    drop = replace(
        raw,
        sessions=tuple(
            replace(bar, raw_open=D(40), raw_close=D(40))
            if bar.open_at == FIRST + timedelta(days=16)
            else bar
            for bar in raw.sessions
        ),
    )
    with pytest.raises(RiskPolicyRequired, match="risk_policy_required") as caught:
        run_kr_selected_candidate_reference(
            drop, signal, CONFIG_BYTES, "equal", sell_costs()
        )
    assert caught.value.point.at == FIRST + timedelta(days=16, hours=3)
    spike = replace(
        raw,
        sessions=tuple(
            replace(bar, raw_open=D(250), raw_close=D(100))
            if bar.open_at == FIRST + timedelta(days=16)
            else bar
            for bar in raw.sessions
        ),
    )
    result = run_kr_selected_candidate_reference(
        spike, signal, CONFIG_BYTES, "equal", sell_costs()
    )
    assert result.ledger.drawdown_breached
    assert result.ledger.max_drawdown_fraction > D(".20")
    assert result.episode_max_drawdown_fraction < D(".10")
    assert result.lifetime_peak_krw > result.episode_peak_krw


def test_binding_incomplete_pending_and_invalid_hold_fail_closed() -> None:
    raw, signal = fixture()
    with pytest.raises(PolicyInputError, match="registry identity"):
        run_kr_selected_candidate_reference(
            raw,
            replace(signal, registration_hash="f" * 64),
            CONFIG_BYTES,
            "equal",
            sell_costs(),
        )
    with pytest.raises(PolicyInputError, match="calendar"):
        run_kr_selected_candidate_reference(
            raw,
            replace(signal, calendar_hash="f" * 64),
            CONFIG_BYTES,
            "equal",
            sell_costs(),
        )
    changed_identity = replace(signal.cohort[0], identity_hash="f" * 64)
    with pytest.raises(PolicyInputError, match="registry identity"):
        run_kr_selected_candidate_reference(
            raw,
            replace(
                signal,
                registered=(changed_identity, *signal.registered[1:]),
                cohort=(changed_identity, *signal.cohort[1:]),
            ),
            CONFIG_BYTES,
            "equal",
            sell_costs(),
        )
    with pytest.raises(PolicyInputError, match="config SHA"):
        run_kr_selected_candidate_reference(
            raw,
            replace(signal, config_sha256="f" * 64),
            CONFIG_BYTES,
            "equal",
            sell_costs(),
        )
    missing = replace(
        signal,
        closes=tuple(
            replace(row, available_at=FIRST)
            if row.official_close_at < FIRST - timedelta(days=40)
            else row
            for row in signal.closes
        ),
    )
    with pytest.raises(PolicyInputError, match="signal_incomplete"):
        run_kr_selected_candidate_reference(
            raw, missing, CONFIG_BYTES, "equal", sell_costs()
        )
    pending = replace(
        raw,
        sessions=tuple(
            bar
            for bar in raw.sessions
            if bar.open_at in (FIRST, SECOND + timedelta(days=1))
        ),
    )
    with pytest.raises(ReferenceInputError, match="overlaps pending"):
        run_kr_selected_candidate_reference(
            pending, signal, CONFIG_BYTES, "equal", sell_costs()
        )

    def malformed(
        at: datetime, point: object
    ) -> tuple[HoldQuantityInstruction | TargetInstruction, ...]:
        return tuple(
            HoldQuantityInstruction(item, at, D(".1"), D("NaN")) for item in raw.cohort
        )

    with pytest.raises(ReferenceInputError, match="finite Decimal"):
        _run_reference_core(
            raw,
            sell_costs=sell_costs(),
            kr_decision_times=(FIRST,),
            kr_decision_hook=malformed,
            kr_close_hook=lambda _: None,
        )


def test_config_rejects_mutated_frozen_schedule() -> None:
    raw, signal = fixture()
    document = json.loads(CONFIG_BYTES)
    document["rebalance"]["every_weeks"] = 2
    altered = json.dumps(document).encode()
    altered_signal = replace(signal, config_sha256=hashlib.sha256(altered).hexdigest())
    with pytest.raises(PolicyInputError, match="frozen KR policy values"):
        run_kr_selected_candidate_reference(
            raw, altered_signal, altered, "equal", sell_costs()
        )
    document = json.loads(CONFIG_BYTES)
    document["semantic_sources_sha256"][
        "backend/jusik/selected_candidate_signals.py"
    ] = "f" * 64
    altered = json.dumps(document).encode()
    with pytest.raises(PolicyInputError, match="semantic source hash differs"):
        run_kr_selected_candidate_reference(
            raw,
            replace(signal, config_sha256=hashlib.sha256(altered).hexdigest()),
            altered,
            "equal",
            sell_costs(),
        )
    assert _schedule(FIRST + timedelta(hours=1), END)[0] == FIRST + timedelta(days=7)
