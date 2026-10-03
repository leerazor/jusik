"""Synthetic single-target raw-ledger bridge and independent fill arithmetic."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import cast

import pytest

from jusik.approved_universe_buy_hold import (
    CostAssumptions,
    DividendEvent,
    FrozenReferenceInput,
    FXObservation,
    Instrument,
    RateAssumption,
    RawSession,
    ReferenceInputError,
    SplitEvent,
    TargetInstruction,
    run_buy_hold_reference,
    run_target_bridge_reference,
)

D = Decimal
PIN = "c" * 64
START = datetime(2026, 1, 1, tzinfo=UTC)


def at(day: int, hour: int = 0) -> datetime:
    return START + timedelta(days=day, hours=hour)


def rate(value: str) -> RateAssumption:
    return RateAssumption(D(value), "explicit synthetic assumption", PIN)


def costs(*, fx_spread: str = "0") -> CostAssumptions:
    zero = rate("0")
    return CostAssumptions(
        rate("0.01"),
        rate("0.01"),
        zero,
        zero,
        zero,
        zero,
        rate(fx_spread),
        rate("0.25"),
        rate("0.25"),
    )


def fixture(*, market: str = "KR", leveraged: bool = False) -> FrozenReferenceInput:
    instrument = Instrument(
        "US" if market == "US" else "KR",
        "NAS" if market == "US" else "KRX",
        "ONE",
        PIN,
        leveraged,
    )
    bars = tuple(
        RawSession(
            instrument, at(day), at(day, 3), D("100"), D("100"), at(day), at(day, 3)
        )
        for day in range(4)
    )
    return FrozenReferenceInput(
        1,
        PIN,
        (instrument,),
        (instrument,),
        "synthetic single target",
        at(0),
        at(3, 4),
        bars,
        PIN,
        True,
        PIN,
        True,
        (),
        PIN,
        True,
        (FXObservation(at(0), at(0), D("1000")),) if market == "US" else (),
        PIN,
        True,
        costs(fx_spread="0.01" if market == "US" else "0"),
    )


def test_kr_post_cost_target_is_minimum_integer_oracle() -> None:
    data = fixture()
    result = run_target_bridge_reference(
        data, TargetInstruction(data.cohort[0], at(0), D("0.20"))
    )
    assert result.status == "synthetic_reference_only"
    assert result.investment_qualification == "not_evaluated"
    assert result.target_attempt.status == "filled"
    assert result.target_attempt.at == at(1)
    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.at == at(1) and trade.raw_price == 100
    assert trade.quantity == 199600
    assert trade.total_krw == 20159600
    fill = next(point for point in result.points if point.at == at(1))
    assert fill.cash_krw == 79840400
    assert fill.nav_krw == 99800400
    assert fill.positions[0].value_krw == 19960000
    assert fill.positions[0].value_krw / fill.nav_krw <= D("0.20")
    assert D(199601) * 100 > D("0.20") * (D(100000000) - D(199601) * 100 * D("0.01"))
    assert all(point.positions == () for point in result.points if point.at < at(1))
    assert result.dividends == ()


def test_same_time_open_is_ineligible_and_unheld_actions_are_ignored() -> None:
    base = fixture()
    target = base.cohort[0]
    other = Instrument("KR", "KRX", "OTHER", PIN, False)
    other_bars = tuple(
        RawSession(other, at(day), at(day, 3), D("50"), D("50"), at(day), at(day, 3))
        for day in range(4)
    )
    unheld_split = SplitEvent(other, "split-other", at(1), at(0), D("2"), PIN)
    unheld_dividend = DividendEvent(
        other, "div-other", at(2), at(3), at(0), D("5"), D("2"), PIN
    )
    data = replace(
        base,
        registered=(other, target),
        cohort=(other, target),
        sessions=other_bars + base.sessions,
        actions=(unheld_split, unheld_dividend),
    )
    result = run_target_bridge_reference(
        data, TargetInstruction(target, at(1), D("0.20"))
    )
    assert [trade.at for trade in result.trades] == [at(2)]
    assert all(
        position.instrument == target
        for point in result.points
        for position in point.positions
    )
    assert result.dividends == ()
    assert result.points[-1].cash_krw == 79840400


def test_split_before_fill_uses_post_split_raw_price_and_no_prior_entitlement() -> None:
    base = fixture()
    target = base.cohort[0]
    bars = tuple(
        replace(bar, raw_open=D("50"), raw_close=D("50"))
        if bar.open_at >= at(1)
        else bar
        for bar in base.sessions
    )
    split = SplitEvent(target, "pre-buy-split", at(1), at(0), D("2"), PIN)
    before_dividend = DividendEvent(
        target, "pre-buy-ex", at(1), at(2), at(0), D("10"), D("4"), PIN
    )
    after_dividend = DividendEvent(
        target, "post-buy-ex", at(2), at(3), at(1), D("10"), D("4"), PIN
    )
    data = replace(
        base, sessions=bars, actions=(split, before_dividend, after_dividend)
    )
    result = run_target_bridge_reference(
        data, TargetInstruction(target, at(0), D("0.20"))
    )
    assert result.trades[0].raw_price == 50
    assert result.trades[0].quantity == 399201
    assert [entry.action_id for entry in result.dividends] == [
        "post-buy-ex",
        "post-buy-ex",
    ]
    assert [entry.phase for entry in result.dividends] == ["accrual", "payment"]
    assert all(entry.quantity == D("399201") for entry in result.dividends)
    assert result.dividends[0].gross_local == D("3992010")
    assert result.dividends[0].withholding_local == D("399201")
    assert next(
        point for point in result.points if point.at == at(2)
    ).receivables_krw == D("3592809")
    assert result.points[-1].receivables_krw == 0


def test_owned_split_precedes_ex_and_preserves_payment_entitlement() -> None:
    base = fixture()
    target = base.cohort[0]
    bars = tuple(
        replace(bar, raw_open=D("50"), raw_close=D("50"))
        if bar.open_at >= at(2)
        else bar
        for bar in base.sessions
    )
    split = SplitEvent(target, "owned-split", at(2), at(1), D("2"), PIN)
    dividend = DividendEvent(
        target, "owned-div", at(2), at(3), at(1), D("10"), D("4"), PIN
    )
    result = run_target_bridge_reference(
        replace(base, sessions=bars, actions=(split, dividend)),
        TargetInstruction(target, at(0), D("0.20")),
    )
    split_point = next(point for point in result.points if point.at == at(2))
    assert split_point.positions[0].quantity == D("399200")
    assert split_point.positions[0].raw_price == D("50")
    assert split_point.receivables_krw == D("3592800")
    assert [entry.quantity for entry in result.dividends] == [D("399200")] * 2
    assert [entry.withholding_local for entry in result.dividends] == [D("399200")] * 2
    assert result.points[-1].receivables_krw == 0
    assert result.points[-1].cash_krw == D("83433200")


def test_us_effective_cost_and_historically_available_fx() -> None:
    base = fixture(market="US")
    target = base.cohort[0]
    clean = run_target_bridge_reference(
        base, TargetInstruction(target, at(0), D("0.20"))
    )
    poison = FXObservation(at(0), at(4), D("9999"))
    tainted = run_target_bridge_reference(
        replace(base, fx=base.fx + (poison,)),
        TargetInstruction(target, at(0), D("0.20")),
    )
    assert tainted == clean
    trade = clean.trades[0]
    assert trade.quantity == 199
    assert trade.total_krw == D("20299990")
    assert trade.fx_spread_krw == D("200990")
    fill = next(point for point in clean.points if point.at == at(1))
    assert fill.cash_krw == D("79700010")
    assert fill.nav_krw == D("99600010")
    assert fill.cash_usd == 0
    with pytest.raises(ReferenceInputError, match="historically available FX missing"):
        run_target_bridge_reference(
            replace(base, fx=(poison,)),
            TargetInstruction(target, at(0), D("0.20")),
        )


def test_us_spread_changes_integer_target_quantity() -> None:
    base = fixture(market="US")
    bars = tuple(
        replace(bar, raw_open=D("99.8"), raw_close=D("99.8"))
        if bar.open_at == at(1)
        else bar
        for bar in base.sessions
    )
    result = run_target_bridge_reference(
        replace(base, sessions=bars),
        TargetInstruction(base.cohort[0], at(0), D("0.20")),
    )
    assert result.trades[0].quantity == 199
    one_more_value = D(200) * D("99.8") * D(1000)
    effective_cost = D("1.01") * D("1.01") - 1
    assert one_more_value > D("0.20") * (D(100000000) - one_more_value * effective_cost)


def test_explicit_nonfill_reasons() -> None:
    base = fixture()
    target = base.cohort[0]
    zero = run_target_bridge_reference(base, TargetInstruction(target, at(0), D("0")))
    assert zero.target_attempt.status == "zero_target"
    assert zero.trades == () and zero.points[-1].cash_krw == 100000000
    no_later = run_target_bridge_reference(
        base, TargetInstruction(target, at(3), D("0.20"))
    )
    assert no_later.target_attempt.status == "window_end_unfilled"
    assert no_later.target_attempt.at == base.evaluation_end
    assert no_later.trades == ()
    expensive = replace(
        base,
        sessions=tuple(
            replace(bar, raw_open=D("100000000"), raw_close=D("100000000"))
            if bar.open_at == at(1)
            else bar
            for bar in base.sessions
        ),
    )
    one_share = run_target_bridge_reference(
        expensive, TargetInstruction(target, at(0), D("0.20"))
    )
    assert one_share.target_attempt.status == "one_share_unaffordable"
    assert one_share.trades == ()


@pytest.mark.parametrize(
    ("instruction", "message"),
    [
        (
            lambda data: TargetInstruction(
                replace(data.cohort[0], identity_hash="d" * 64), at(0), D("0.20")
            ),
            "registered identity mismatch",
        ),
        (
            lambda data: TargetInstruction(data.cohort[0], at(0), D("0.21")),
            "symbol cap",
        ),
        (
            lambda data: TargetInstruction(data.cohort[0], at(0), D("NaN")),
            "finite Decimal",
        ),
        (
            lambda data: TargetInstruction(data.cohort[0], at(0), D("-0.01")),
            "nonnegative",
        ),
        (
            lambda data: TargetInstruction(data.cohort[0], at(4), D("0.20")),
            "outside evaluation",
        ),
        (
            lambda data: TargetInstruction(
                data.cohort[0], datetime(2026, 1, 1), D("0.20")
            ),
            "timezone",
        ),
    ],
)
def test_invalid_target_fails_closed(instruction: object, message: str) -> None:
    data = fixture()
    with pytest.raises(ReferenceInputError, match=message):
        run_target_bridge_reference(data, instruction(data))  # type: ignore[operator]


def test_existing_initial_allocation_rule_does_not_apply_to_target_only() -> None:
    data = fixture(leveraged=True)
    with pytest.raises(ReferenceInputError, match="initial equal cohort"):
        run_buy_hold_reference(data)
    result = run_target_bridge_reference(
        data, TargetInstruction(data.cohort[0], at(0), D("0.20"))
    )
    assert result.target_attempt.status == "filled"
    assert not result.points[-1].leverage_breach


def test_missing_cost_and_adjusted_execution_price_are_rejected() -> None:
    base = fixture()
    target = TargetInstruction(base.cohort[0], at(0), D("0.20"))
    with pytest.raises(ReferenceInputError, match="buy_tax_kr"):
        run_target_bridge_reference(
            replace(
                base, costs=replace(base.costs, buy_tax_kr=cast(RateAssumption, None))
            ),
            target,
        )
    adjusted = replace(
        base,
        sessions=(replace(base.sessions[0], price_basis="adjusted"),)
        + base.sessions[1:],
    )
    with pytest.raises(ReferenceInputError, match="raw prices"):
        run_target_bridge_reference(adjusted, target)
