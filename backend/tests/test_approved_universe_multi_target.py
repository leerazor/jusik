"""One synthetic same-open target batch and independent integer feasibility checks."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from jusik.approved_universe_buy_hold import (
    CostAssumptions,
    DividendEvent,
    FrozenReferenceInput,
    FXObservation,
    Instrument,
    Market,
    RateAssumption,
    RawSession,
    ReferenceInputError,
    SplitEvent,
    TargetInstruction,
    _BatchSizingLine,
    _size_initial_target_batch,
    run_multi_target_reference,
)

D = Decimal
PIN = "d" * 64
START = datetime(2026, 1, 1, tzinfo=UTC)


def at(day: int, hour: int = 0) -> datetime:
    return START + timedelta(days=day, hours=hour)


def rate(value: str) -> RateAssumption:
    return RateAssumption(D(value), "explicit synthetic assumption", PIN)


def costs(
    *, kr_commission: str = "0.10", us_commission: str = "0", spread: str = "0.10"
) -> CostAssumptions:
    zero = rate("0")
    return CostAssumptions(
        rate(kr_commission),
        rate(us_commission),
        zero,
        zero,
        zero,
        zero,
        rate(spread),
        rate("0.25"),
        rate("0.25"),
    )


def fixture(
    *,
    markets: tuple[Market, ...] = ("KR", "KR"),
    open_hours: tuple[int, ...] = (0, 0),
    leveraged: tuple[bool, ...] = (False, False),
) -> FrozenReferenceInput:
    assert len(markets) == len(open_hours) == len(leveraged)
    items = tuple(
        Instrument(
            market, "KRX" if market == "KR" else "NAS", chr(65 + index), PIN, lev
        )
        for index, (market, lev) in enumerate(zip(markets, leveraged, strict=True))
    )
    sessions = tuple(
        RawSession(
            item,
            at(day, open_hours[index]),
            at(day, open_hours[index] + 3),
            D(100 if index == 0 else 50),
            D(100 if index == 0 else 50),
            at(day, open_hours[index]),
            at(day, open_hours[index] + 3),
        )
        for day in range(4)
        for index, item in enumerate(items)
    )
    return FrozenReferenceInput(
        1,
        PIN,
        items,
        items,
        "synthetic same-open batch",
        at(0),
        at(4),
        sessions,
        PIN,
        True,
        PIN,
        True,
        (),
        PIN,
        True,
        (FXObservation(at(0), at(0), D(1000)),),
        PIN,
        True,
        costs(),
    )


def targets(
    data: FrozenReferenceInput, *weights: str, decided_at: datetime | None = None
) -> tuple[TargetInstruction, ...]:
    return tuple(
        TargetInstruction(item, at(0) if decided_at is None else decided_at, D(weight))
        for item, weight in zip(data.cohort, weights, strict=True)
    )


def test_small_exhaustive_integer_feasibility_oracle() -> None:
    lines = (
        _BatchSizingLine(D("0.20"), D(100), D(110)),
        _BatchSizingLine(D("0.20"), D(50), D(55)),
    )
    result = _size_initial_target_batch(D(1000), D(1000), lines)
    assert result == (D(1), D(3))  # u=(2,4), Nmin=960.
    cash = D(1000) - result[0] * 110 - result[1] * 55
    nav = D(1000) - result[0] * 10 - result[1] * 5
    assert cash == 725 and nav == 975
    feasible = {
        (first, second)
        for first in range(3)
        for second in range(5)
        if first * 110 + second * 55 <= 1000
        and first * 100 <= D("0.20") * (1000 - first * 10 - second * 5)
        and second * 50 <= D("0.20") * (1000 - first * 10 - second * 5)
    }
    assert (1, 3) in feasible
    assert all(first <= 1 and second <= 3 for first, second in feasible)
    with pytest.raises(ReferenceInputError, match="shared_cash_insufficient"):
        _size_initial_target_batch(D(1000), D(274), lines)
    with pytest.raises(ReferenceInputError, match="conservative NAV nonpositive"):
        _size_initial_target_batch(
            D(1000),
            D(1000),
            (
                _BatchSizingLine(D("0.20"), D(100), D(370)),
                _BatchSizingLine(D("0.20"), D(50), D(185)),
            ),
        )


def test_kr_atomic_batch_conservative_quantities_and_permutation() -> None:
    data = fixture()
    requested = targets(data, "0.20", "0.20")
    result = run_multi_target_reference(data, requested)
    permuted = run_multi_target_reference(
        replace(data, sessions=tuple(reversed(data.sessions))),
        tuple(reversed(requested)),
    )
    assert result == permuted
    assert result.status == "synthetic_reference_only"
    assert result.execution_status == "filled"
    assert result.investment_qualification == "not_evaluated"
    assert [
        (trade.instrument.symbol, trade.at, trade.quantity) for trade in result.trades
    ] == [("A", at(1), D(192000)), ("B", at(1), D(384000))]
    assert [trade.total_krw for trade in result.trades] == [D(21120000)] * 2
    fill = next(point for point in result.points if point.at == at(1))
    assert fill.cash_krw == D(57760000)
    assert fill.nav_krw == D(96160000)
    assert fill.cash_usd == 0
    assert sum(position.value_krw for position in fill.positions) == D(38400000)
    assert all(
        position.value_krw / fill.nav_krw <= D("0.20") for position in fill.positions
    )
    assert all(
        attempt.status == "filled" and attempt.shortfall_weight > 0
        for attempt in result.target_attempts
    )
    assert all(point.positions == () for point in result.points if point.at < at(1))


def test_us_batch_fx_spread_uses_shared_krw_cash_without_implicit_usd() -> None:
    data = fixture(markets=("US", "US"))
    result = run_multi_target_reference(data, targets(data, "0.20", "0.20"))
    assert [trade.quantity for trade in result.trades] == [D(192), D(384)]
    assert [trade.fx_spread_krw for trade in result.trades] == [D(1920000)] * 2
    fill = next(point for point in result.points if point.at == at(1))
    assert fill.cash_krw == D(57760000)
    assert fill.cash_usd == 0
    assert fill.nav_krw == D(96160000)
    assert all(
        attempt.achieved_weight <= D("0.20") for attempt in result.target_attempts
    )
    poison = FXObservation(at(0), at(5), D(9999))
    assert (
        run_multi_target_reference(
            replace(data, fx=data.fx + (poison,)), targets(data, "0.20", "0.20")
        )
        == result
    )


def test_three_targets_preserve_gross_and_registered_leverage_caps() -> None:
    data = fixture(
        markets=("KR", "KR", "KR"),
        open_hours=(0, 0, 0),
        leveraged=(True, False, False),
    )
    result = run_multi_target_reference(data, targets(data, "0.20", "0.20", "0.20"))
    assert [trade.quantity for trade in result.trades] == [
        D(188000),
        D(376000),
        D(376000),
    ]
    fill = next(point for point in result.points if point.at == at(1))
    assert fill.nav_krw == D(94360000)
    assert (
        sum(position.value_krw for position in fill.positions)
        <= D("0.60") * fill.nav_krw
    )
    assert fill.leveraged_value_krw <= D("0.20") * fill.nav_krw
    assert all(
        attempt.achieved_weight <= attempt.target_weight
        for attempt in result.target_attempts
    )


def test_zero_and_one_share_not_feasible_are_explicit() -> None:
    data = fixture()
    all_cash = run_multi_target_reference(data, targets(data, "0", "0"))
    assert all_cash.execution_status == "all_cash" and all_cash.trades == ()
    assert all(attempt.status == "zero_target" for attempt in all_cash.target_attempts)
    assert all_cash.points[-1].cash_krw == D(100000000)
    expensive = replace(
        data,
        sessions=tuple(
            replace(bar, raw_open=D(100000000), raw_close=D(100000000))
            if bar.instrument == data.cohort[0] and bar.open_at == at(1)
            else bar
            for bar in data.sessions
        ),
    )
    result = run_multi_target_reference(expensive, targets(expensive, "0.20", "0.20"))
    assert [attempt.status for attempt in result.target_attempts] == [
        "one_share_not_feasible",
        "filled",
    ]
    assert result.target_attempts[0].quantity == 0
    assert result.target_attempts[0].shortfall_weight == D("0.20")
    all_expensive = replace(
        data,
        sessions=tuple(
            replace(bar, raw_open=D(100000000), raw_close=D(100000000))
            if bar.open_at == at(1)
            else bar
            for bar in data.sessions
        ),
    )
    none_filled = run_multi_target_reference(
        all_expensive, targets(all_expensive, "0.20", "0.20")
    )
    assert none_filled.execution_status == "no_feasible_share"
    assert none_filled.trades == ()
    one_zero = run_multi_target_reference(data, targets(data, "0", "0.20"))
    assert [attempt.status for attempt in one_zero.target_attempts] == [
        "zero_target",
        "filled",
    ]


def test_split_ex_before_buy_has_zero_entitlement_then_later_payment() -> None:
    data = fixture()
    first = data.cohort[0]
    split = SplitEvent(first, "pre-split", at(1), at(0), D(2), PIN)
    early = DividendEvent(first, "pre-ex", at(1), at(2), at(0), D(1), D(1), PIN)
    later = DividendEvent(first, "post-ex", at(2), at(3), at(1), D(1), D(1), PIN)
    sessions = tuple(
        replace(bar, raw_open=D(50), raw_close=D(50))
        if bar.instrument == first and bar.open_at >= at(1)
        else bar
        for bar in data.sessions
    )
    result = run_multi_target_reference(
        replace(data, sessions=sessions, actions=(split, early, later)),
        targets(data, "0.20", "0.20"),
    )
    assert result.trades[0].raw_price == 50
    assert result.trades[0].quantity == D(384000)
    assert [
        (entry.action_id, entry.phase, entry.quantity) for entry in result.dividends
    ] == [("post-ex", "accrual", D(384000)), ("post-ex", "payment", D(384000))]
    ex_point = next(point for point in result.points if point.at == at(2))
    assert ex_point.receivables_krw == D(288000)
    assert result.points[-1].receivables_krw == 0
    assert result.points[-1].cash_krw == D(58048000)


def test_batch_rejects_mixed_or_staggered_or_missing_first_open() -> None:
    mixed = fixture(markets=("KR", "US"), open_hours=(0, 4))
    with pytest.raises(ReferenceInputError, match="one currency"):
        run_multi_target_reference(mixed, targets(mixed, "0.20", "0.20"))
    assert (
        run_multi_target_reference(mixed, targets(mixed, "0", "0")).execution_status
        == "all_cash"
    )
    staggered = fixture(open_hours=(0, 1))
    with pytest.raises(ReferenceInputError, match="first official opens differ"):
        run_multi_target_reference(staggered, targets(staggered, "0.20", "0.20"))
    with pytest.raises(ReferenceInputError, match="first official opens differ"):
        run_multi_target_reference(staggered, targets(staggered, "0.20", "0"))
    data = fixture()
    with pytest.raises(ReferenceInputError, match="missing next official open"):
        run_multi_target_reference(
            data, targets(data, "0.20", "0.20", decided_at=at(3))
        )


def test_batch_full_identity_decision_and_cap_validation() -> None:
    data = fixture()
    requested = targets(data, "0.20", "0.20")
    bad_cases = (
        ((requested[0],), "every cohort identity"),
        ((requested[0], requested[0]), "every cohort identity"),
        (
            (
                replace(
                    requested[0],
                    instrument=replace(data.cohort[0], identity_hash="e" * 64),
                ),
                requested[1],
            ),
            "registered identity mismatch",
        ),
        (
            (requested[0], replace(requested[1], decided_at=at(0, 1))),
            "one decision time",
        ),
        ((replace(requested[0], target_weight=D("0.21")), requested[1]), "symbol cap"),
        (
            (replace(requested[0], target_weight=D("NaN")), requested[1]),
            "finite Decimal",
        ),
    )
    for candidate, reason in bad_cases:
        with pytest.raises(ReferenceInputError, match=reason):
            run_multi_target_reference(data, candidate)
    leveraged = fixture(leveraged=(True, True))
    with pytest.raises(ReferenceInputError, match="leveraged cap"):
        run_multi_target_reference(leveraged, targets(leveraged, "0.20", "0.20"))
    with pytest.raises(ReferenceInputError, match="leveraged cap"):
        run_multi_target_reference(
            leveraged,
            targets(
                leveraged,
                "0.10000000000000000000000000001",
                "0.10000000000000000000000000001",
            ),
        )
    four = fixture(
        markets=("KR", "KR", "KR", "KR"),
        open_hours=(0, 0, 0, 0),
        leveraged=(False,) * 4,
    )
    with pytest.raises(ReferenceInputError, match="gross"):
        run_multi_target_reference(four, targets(four, "0.20", "0.20", "0.20", "0.20"))
    with pytest.raises(ReferenceInputError, match="gross"):
        run_multi_target_reference(
            four,
            targets(four, *("0.15000000000000000000000000001",) * 4),
        )


def test_high_cost_batch_rejects_nonpositive_conservative_nav() -> None:
    data = fixture()
    high = replace(
        data.costs,
        commission_kr=rate("0.90"),
        slippage_kr=rate("0.90"),
        buy_tax_kr=rate("0.90"),
    )
    with pytest.raises(ReferenceInputError, match="conservative NAV nonpositive"):
        run_multi_target_reference(
            replace(data, costs=high), targets(data, "0.20", "0.20")
        )


def test_batch_requires_explicit_cost_evidence_and_available_us_fx() -> None:
    data = fixture()
    unlabeled = replace(data.costs, commission_kr=RateAssumption(D("0.10"), "", PIN))
    with pytest.raises(ReferenceInputError, match="explicit labelled assumption"):
        run_multi_target_reference(
            replace(data, costs=unlabeled), targets(data, "0.20", "0.20")
        )
    us = fixture(markets=("US", "US"))
    with pytest.raises(ReferenceInputError, match="historically available FX missing"):
        run_multi_target_reference(replace(us, fx=()), targets(us, "0.20", "0.20"))


def test_rounded_unit_arithmetic_fails_closed_before_any_fill() -> None:
    data = fixture()
    precise = D("1.1234567890123456789012345678")
    sessions = tuple(
        replace(bar, raw_open=precise, raw_close=precise)
        if bar.instrument == data.cohort[0] and bar.open_at == at(1)
        else bar
        for bar in data.sessions
    )
    with pytest.raises(ReferenceInputError, match="batch unit arithmetic rounded"):
        run_multi_target_reference(
            replace(data, sessions=sessions), targets(data, "0.20", "0.20")
        )
