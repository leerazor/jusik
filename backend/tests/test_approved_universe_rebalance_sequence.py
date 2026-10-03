"""Finite synthetic KR target sequence through the shared raw accounting loop."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from fractions import Fraction

import pytest

from jusik.approved_universe_buy_hold import (
    CostAssumptions,
    DividendEvent,
    FrozenReferenceInput,
    Instrument,
    RateAssumption,
    RawSession,
    ReferenceInputError,
    SellCostAssumptions,
    SplitEvent,
    TargetInstruction,
    _RebalanceLine,
    _size_kr_rebalance,
    run_kr_target_sequence_reference,
)

D = Decimal
PIN = "e" * 64
START = datetime(2026, 1, 1, tzinfo=UTC)


def at(day: int, hour: int = 0) -> datetime:
    return START + timedelta(days=day, hours=hour)


def rate(value: str) -> RateAssumption:
    return RateAssumption(D(value), "explicit synthetic cost", PIN)


def costs(buy: str = "0") -> CostAssumptions:
    zero = rate("0")
    return CostAssumptions(
        rate(buy), zero, zero, zero, zero, zero, zero, rate("0.25"), zero
    )


def sell_costs(sell: str = "0") -> SellCostAssumptions:
    zero = rate("0")
    return SellCostAssumptions(rate(sell), zero, zero, zero, zero, zero, "notional")


def fixture(*, actions: bool = False) -> FrozenReferenceInput:
    items = tuple(
        Instrument("KR", "KRX", symbol, PIN, symbol == "A")
        for symbol in ("A", "B", "C")
    )
    bars = tuple(
        RawSession(
            item,
            at(day),
            at(day, 3),
            D(
                50
                if day >= 2 and item.symbol == "A"
                else 100
                if item.symbol == "A"
                else 50
            ),
            D(
                50
                if day >= 2 and item.symbol == "A"
                else 100
                if item.symbol == "A"
                else 50
            ),
            at(day),
            at(day, 3),
        )
        for day in range(4)
        for item in items
    )
    events = (
        (
            SplitEvent(items[0], "split-A", at(2), at(2), D(2), PIN),
            DividendEvent(items[0], "div-A", at(2), at(3), at(2), D(2), D(1), PIN),
            DividendEvent(items[2], "div-C", at(2), at(3), at(2), D(1), D(0), PIN),
        )
        if actions
        else ()
    )
    return FrozenReferenceInput(
        1,
        PIN,
        items,
        items,
        "synthetic KR sequence",
        at(0),
        at(3, 4),
        bars,
        PIN,
        True,
        PIN,
        True,
        events,
        PIN,
        True,
        (),
        PIN,
        True,
        costs(),
    )


def vector(
    data: FrozenReferenceInput, day: int, *weights: str
) -> tuple[TargetInstruction, ...]:
    decision = at(0) if day == 0 else at(day, 4)
    return tuple(
        TargetInstruction(item, decision, D(weight))
        for item, weight in zip(data.cohort, weights, strict=True)
    )


def test_small_integer_oracle_and_proportional_cash_boundary() -> None:
    lines = (
        _RebalanceLine(D(".2"), D(4), D(100), D(110), D(90)),
        _RebalanceLine(D(".2"), D(4), D(50), D(55), D(45)),
        _RebalanceLine(D(".2"), D(0), D(50), D(55), D(45)),
    )
    sold, bought = _size_kr_rebalance(D(1000), D(400), lines)
    assert sold == (D(3), D(1), D(0))
    assert bought == (D(0), D(0), D(3))
    nav = D(1000) - D(3) * 10 - D(1) * 5 - D(3) * 5
    cash = D(400) + D(3) * 90 + D(1) * 45 - D(3) * 55
    assert (nav, cash) == (D(950), D(550))
    feasible = {
        (sa, sb, bc)
        for sa in range(5)
        for sb in range(5)
        for bc in range(5)
        if 55 * bc <= 400 + 90 * sa + 45 * sb
        and 100 * (4 - sa) <= Fraction(1, 5) * (1000 - 10 * sa - 5 * sb - 5 * bc)
        and 50 * (4 - sb) <= Fraction(1, 5) * (1000 - 10 * sa - 5 * sb - 5 * bc)
        and 50 * bc <= Fraction(1, 5) * (1000 - 10 * sa - 5 * sb - 5 * bc)
    }
    assert (3, 1, 3) in feasible
    assert all(sa >= 3 and sb >= 1 for sa, sb, _ in feasible)
    with pytest.raises(
        ReferenceInputError, match="proportional buys erased feasible share"
    ):
        _size_kr_rebalance(
            D(1000),
            D(110),
            (
                _RebalanceLine(D(".2"), D(0), D(100), D(110), D(90)),
                _RebalanceLine(D(".2"), D(0), D(100), D(110), D(90)),
            ),
        )
    assert _size_kr_rebalance(D(1000), D(0), lines)[1] == (D(0), D(0), D(3))
    with pytest.raises(ReferenceInputError, match="conservative NAV nonpositive"):
        _size_kr_rebalance(
            D(1000),
            D(1000),
            tuple(
                _RebalanceLine(D(".2"), D(0), D(100), D(1000), D(90)) for _ in range(3)
            ),
        )


def test_three_decisions_preserve_rights_cash_and_permutation() -> None:
    data = fixture(actions=True)
    decisions = (
        vector(data, 0, ".1", ".1", "0"),
        vector(data, 1, ".05", ".15", ".1"),
        vector(data, 2, "0", "0", "0"),
    )
    result = run_kr_target_sequence_reference(data, decisions, sell_costs())
    permuted = run_kr_target_sequence_reference(
        replace(
            data,
            cohort=data.cohort[::-1],
            registered=data.registered[::-1],
            sessions=data.sessions[::-1],
            actions=data.actions[::-1],
        ),
        tuple(tuple(reversed(v)) for v in decisions),
        sell_costs(),
    )
    assert result == permuted
    assert result.status == "synthetic_reference_only"
    assert result.investment_qualification == "not_evaluated"
    assert [(batch.open_at, batch.status) for batch in result.batches] == [
        (at(1), "filled"),
        (at(2), "filled"),
        (at(3), "filled"),
    ]
    assert [(t.instrument.symbol, t.quantity) for t in result.trades[:2]] == [
        ("A", D(100000)),
        ("B", D(200000)),
    ]
    assert [x for x in result.dividends if x.action_id == "div-C"] == []
    accrual, payment = [x for x in result.dividends if x.action_id == "div-A"]
    assert accrual.quantity == payment.quantity == D(200000)
    assert accrual.net_local == payment.net_local == D(350000)
    assert result.sales[0].instrument.symbol == "A"
    assert result.sales[0].quantity > 0
    assert any(t.instrument.symbol == "B" and t.at == at(2) for t in result.trades)
    assert any(t.instrument.symbol == "C" and t.at == at(2) for t in result.trades)
    final = result.points[-1]
    assert final.cash_krw == final.nav_krw == D(100350000)
    assert final.receivables_krw == 0
    assert all(position.quantity == 0 for position in final.positions)
    assert all(batch.open_at > batch.decided_at for batch in result.batches)


def test_buy_and_sell_costs_reconcile_shared_cash_and_existing_holding() -> None:
    data = replace(fixture(), costs=costs(".1"))
    result = run_kr_target_sequence_reference(
        data,
        (vector(data, 0, ".1", ".1", "0"), vector(data, 1, "0", ".1", ".1")),
        sell_costs(".1"),
    )
    assert [(sale.instrument.symbol, sale.quantity) for sale in result.sales] == [
        ("A", D(98000)),
        ("B", D(12690)),
    ]
    assert result.batches[1].bought == ((data.cohort[2], D(183310)),)
    assert result.points[-1].nav_krw == D(91670000)
    assert result.points[-1].cash_krw == D(73339000)
    assert all(not point.leverage_breach for point in result.points)


def test_zero_target_unchanged_and_last_breach_history() -> None:
    data = fixture()
    data = replace(
        data,
        sessions=tuple(
            replace(bar, raw_open=D(100), raw_close=D(100))
            if bar.instrument.symbol == "A" and bar.open_at >= at(2)
            else bar
            for bar in data.sessions
        ),
    )
    decisions = (
        vector(data, 0, ".2", "0", "0"),
        vector(data, 1, ".2", "0", "0"),
        vector(data, 2, "0", "0", "0"),
    )
    result = run_kr_target_sequence_reference(data, decisions, sell_costs(".1"))
    assert result.batches[1].status == "unchanged"
    assert result.batches[2].sold[0][0].symbol == "A"
    assert result.points[-1].positions[0].quantity == 0
    assert result.points[-1].cash_krw == result.points[-1].nav_krw
    assert result.max_drawdown_fraction > 0


def test_open_gap_breach_stays_visible_after_same_batch_repair() -> None:
    data = fixture()
    data = replace(
        data,
        sessions=tuple(
            replace(bar, raw_open=D(200), raw_close=D(200))
            if bar.instrument.symbol == "A" and bar.open_at >= at(2)
            else bar
            for bar in data.sessions
        ),
    )
    result = run_kr_target_sequence_reference(
        data,
        (vector(data, 0, ".2", "0", "0"), vector(data, 1, ".2", "0", "0")),
        sell_costs(),
    )
    opening = next(
        point
        for point in result.points
        if point.at == at(2) and point.phase == "pre_rebalance"
    )
    repaired = next(
        point for point in result.points if point.at == at(2) and point.phase == "open"
    )
    assert opening.leverage_breach
    assert not repaired.leverage_breach
    assert result.leverage_breached
    assert result.batches[1].sold[0][1] > 0


def test_all_cash_and_fractional_split_fail_closed() -> None:
    data = fixture()
    empty = run_kr_target_sequence_reference(
        data, (vector(data, 0, "0", "0", "0"),), sell_costs()
    )
    assert empty.batches[0].status == "all_cash"
    assert empty.trades == ()
    assert empty.sales == ()
    assert empty.points[-1].nav_krw == D(100000000)
    fractional = replace(
        data,
        sessions=tuple(
            replace(bar, raw_open=D(80), raw_close=D(80))
            if bar.instrument.symbol == "A" and bar.open_at >= at(2)
            else bar
            for bar in data.sessions
        ),
        actions=(
            SplitEvent(data.cohort[0], "fractional", at(2), at(2), D("1.25"), PIN),
        ),
    )
    with pytest.raises(ReferenceInputError, match="fractional split"):
        run_kr_target_sequence_reference(
            fractional,
            (
                vector(fractional, 0, ".199999", "0", "0"),
                vector(fractional, 1, "0", "0", "0"),
            ),
            sell_costs(),
        )


def test_sold_out_state_ignores_later_split_and_can_buy_again() -> None:
    data = fixture()
    data = replace(
        data,
        sessions=tuple(
            replace(bar, raw_open=D(100), raw_close=D(100))
            if bar.instrument.symbol == "A" and bar.open_at == at(2)
            else bar
            for bar in data.sessions
        ),
        actions=(SplitEvent(data.cohort[0], "after-sale", at(3), at(3), D(2), PIN),),
    )
    result = run_kr_target_sequence_reference(
        data,
        (
            vector(data, 0, ".1", "0", "0"),
            vector(data, 1, "0", "0", "0"),
            vector(data, 2, ".1", "0", "0"),
        ),
        sell_costs(),
    )
    assert [(trade.at, trade.quantity, trade.raw_price) for trade in result.trades] == [
        (at(1), D(100000), D(100)),
        (at(3), D(200000), D(50)),
    ]
    assert result.sales[0].quantity == D(100000)
    assert result.points[-1].nav_krw == D(100000000)


def test_wrong_identity_clock_market_and_costs_fail_closed() -> None:
    data = fixture()
    first = vector(data, 0, ".1", ".1", "0")
    second = vector(data, 1, ".1", ".1", "0")
    for bad in (
        (first, first),
        (first, tuple(replace(x, decided_at=at(1)) for x in second)),
        (first, (second[0], second[0], second[2])),
    ):
        with pytest.raises(ReferenceInputError):
            run_kr_target_sequence_reference(data, bad, sell_costs())
    bad_identity = replace(data.cohort[0], identity_hash="f" * 64)
    with pytest.raises(ReferenceInputError, match="identity"):
        run_kr_target_sequence_reference(
            data,
            ((replace(first[0], instrument=bad_identity), *first[1:]),),
            sell_costs(),
        )
    us = replace(data.cohort[0], market="US", exchange="NAS")
    mixed = replace(
        data,
        registered=(us, *data.registered[1:]),
        cohort=(us, *data.cohort[1:]),
        sessions=tuple(
            replace(b, instrument=us) if b.instrument == data.cohort[0] else b
            for b in data.sessions
        ),
    )
    with pytest.raises(ReferenceInputError, match="KR revision-one"):
        run_kr_target_sequence_reference(
            mixed, (vector(mixed, 0, ".1", ".1", "0"),), sell_costs()
        )
    staggered = replace(
        data,
        sessions=tuple(
            replace(
                b,
                open_at=b.open_at + timedelta(hours=1),
                open_observed_at=b.open_observed_at + timedelta(hours=1),
            )
            if b.instrument == data.cohort[2]
            else b
            for b in data.sessions
        ),
    )
    with pytest.raises(ReferenceInputError, match="first official opens differ"):
        run_kr_target_sequence_reference(
            staggered, (vector(staggered, 0, ".1", ".1", "0"),), sell_costs()
        )
    with pytest.raises(ReferenceInputError, match="sell costs"):
        run_kr_target_sequence_reference(data, (first,), None)  # type: ignore[arg-type]
    late = tuple(replace(item, decided_at=at(3, 3)) for item in first)
    with pytest.raises(ReferenceInputError, match="next official open"):
        run_kr_target_sequence_reference(data, (late,), sell_costs())
    with pytest.raises(ReferenceInputError, match="revision-one"):
        run_kr_target_sequence_reference(
            replace(data, registration_revision=2), (first,), sell_costs()
        )
