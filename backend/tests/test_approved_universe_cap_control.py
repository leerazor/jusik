"""Synthetic, independently calculable cap-control accounting cases."""

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
    RateAssumption,
    RawSession,
    ReferenceInputError,
    SellCostAssumptions,
    SplitEvent,
    run_buy_hold_reference,
    run_cap_control_reference,
)

D = Decimal
PIN = "b" * 64
START = datetime(2026, 1, 1, tzinfo=UTC)


def at(day: int, hour: int = 0) -> datetime:
    return START + timedelta(days=day, hours=hour)


def rate(value: str) -> RateAssumption:
    return RateAssumption(D(value), "explicit synthetic assumption", PIN)


def buy_costs() -> CostAssumptions:
    zero = rate("0")
    return CostAssumptions(zero, zero, zero, zero, zero, zero, zero, zero, zero)


def sell_costs(cost: str = "0.01") -> SellCostAssumptions:
    zero = rate("0")
    return SellCostAssumptions(
        rate(cost), rate(cost), zero, zero, zero, zero, "notional"
    )


def five_assets(*, us_lever: bool = False) -> FrozenReferenceInput:
    instruments = tuple(
        Instrument(
            "US" if us_lever and index == 0 else "KR",
            "NAS" if us_lever and index == 0 else "KRX",
            f"S{index}",
            PIN,
            index == 0,
        )
        for index in range(5)
    )
    sessions = tuple(
        RawSession(
            item,
            at(day),
            at(day, 3),
            D("0.1")
            if item.market == "US" and day < 2
            else D("0.2")
            if item.market == "US"
            else D("200")
            if day == 2 and item.leveraged
            else D("100"),
            D("0.15")
            if item.market == "US" and day == 1
            else D("0.1")
            if item.market == "US" and day == 0
            else D("0.2")
            if item.market == "US"
            else D("150")
            if day == 1 and item.leveraged
            else D("200")
            if day == 2 and item.leveraged
            else D("100"),
            at(day),
            at(day, 3),
        )
        for day in range(3)
        for item in instruments
    )
    return FrozenReferenceInput(
        1,
        PIN,
        instruments,
        instruments,
        "synthetic cap oracle",
        at(0),
        at(2, 4),
        sessions,
        PIN,
        True,
        PIN,
        True,
        (),
        PIN,
        True,
        (FXObservation(at(0), at(0), D("1000")),) if us_lever else (),
        PIN,
        True,
        buy_costs(),
    )


@pytest.mark.parametrize(
    ("cost", "quantity", "gross", "charge", "cash", "nav", "lever"),
    [
        ("0.01", "80161", "16032200", "160322", "15871878", "119839678", "23967800"),
        ("0.02", "80322", "16064400", "321288", "15743112", "119678712", "23935600"),
    ],
)
def test_integer_minimum_and_independent_oracles(
    cost: str,
    quantity: str,
    gross: str,
    charge: str,
    cash: str,
    nav: str,
    lever: str,
) -> None:
    data = five_assets()
    baseline = run_buy_hold_reference(data)
    result = run_cap_control_reference(data, sell_costs(cost))
    assert result.trades == baseline.trades
    assert len(result.sales) == 1
    sale = result.sales[0]
    assert sale.at == at(2) and sale.raw_price == D("200")
    assert sale.quantity == D(quantity)
    assert sale.gross_local == D(gross)
    assert sale.commission_local == D(charge)
    assert sale.proceeds_local == D(cash)
    assert sale.pre_nav_krw == D("120000000")
    assert sale.pre_leveraged_value_krw == D("40000000")
    assert sale.post_nav_krw == D(nav)
    assert sale.post_leveraged_value_krw == D(lever)
    assert result.points[-1].nav_krw == D(nav)
    assert result.points[-1].leveraged_value_krw == D(lever)
    assert result.points[-1].cash_krw == D(cash)
    assert len([p for p in result.points if p.at == at(2)]) == 1
    assert (D(lever) / D(nav)) <= D("0.2")
    one_less = D(quantity) - 1
    assert D("40000000") - one_less * 200 > D("0.2") * (
        D("120000000") - one_less * 200 * D(cost)
    )
    assert result.attempts[0].status == "repaired"
    assert result.leverage_breached
    assert result.status == "reference_only"
    assert result.investment_qualification == "not_evaluated"


def test_new_breach_at_open_waits_for_strictly_later_open() -> None:
    base = five_assets()
    bars = tuple(
        replace(bar, raw_close=D("100"))
        if bar.instrument.leveraged and bar.open_at == at(1)
        else bar
        for bar in base.sessions
    )
    result = run_cap_control_reference(replace(base, sessions=bars), sell_costs())
    assert result.sales == ()
    assert result.attempts[-1].status == "window_end_unfilled"
    assert result.attempts[-1].observed_breach_at == at(2)


def test_simultaneous_other_close_is_in_sale_sizing() -> None:
    base = five_assets()
    other = base.cohort[1]
    bars = tuple(
        replace(bar, close_at=at(2), close_observed_at=at(2), raw_close=D("50"))
        if bar.instrument == other and bar.open_at == at(1)
        else bar
        for bar in base.sessions
        if not (bar.instrument == other and bar.open_at == at(2))
    )
    result = run_cap_control_reference(replace(base, sessions=bars), sell_costs())
    assert result.sales[0].pre_nav_krw == D("110000000")
    assert result.sales[0].pre_leveraged_value_krw == D("40000000")
    assert result.sales[0].quantity == D("90181")
    assert len([p for p in result.points if p.at == at(2)]) == 1


def test_split_before_queued_sale_and_ex_entitlement_survives_trim() -> None:
    base = five_assets()
    lever = base.cohort[0]
    split = SplitEvent(lever, "split", at(2), at(1), D("2"), PIN)
    dividend = DividendEvent(lever, "div", at(2), at(2, 3), at(1), D("10"), D("0"), PIN)
    bars = tuple(
        replace(bar, raw_open=D("100"), raw_close=D("100"))
        if bar.instrument == lever and bar.open_at == at(2)
        else bar
        for bar in base.sessions
    )
    result = run_cap_control_reference(
        replace(base, sessions=bars, actions=(split, dividend)), sell_costs()
    )
    sale = result.sales[0]
    assert sale.raw_price == D("100")
    assert sale.pre_leveraged_value_krw == D("40000000")
    assert result.dividends[0].quantity == D("400000")
    assert result.dividends[1].quantity == D("400000")
    assert result.dividends[0].net_local == D("4000000")
    assert next(p for p in result.points if p.at == at(2)).receivables_krw == D(
        "4000000"
    )
    assert result.points[-1].cash_krw >= D("4000000")


def test_us_sale_keeps_native_cash_and_ignores_future_fx_revision() -> None:
    base = five_assets(us_lever=True)
    poison = FXObservation(at(0), at(3), D("9999"))
    clean = run_cap_control_reference(base, sell_costs())
    tainted = run_cap_control_reference(
        replace(base, fx=base.fx + (poison,)), sell_costs()
    )
    assert tainted == clean
    sale = clean.sales[0]
    assert sale.quantity == D("80161")
    assert sale.proceeds_local == D("15871.878")
    assert clean.points[-1].cash_usd == sale.proceeds_local
    assert clean.points[-1].cash_krw == 0


def test_closed_market_and_last_breach_remain_unfilled() -> None:
    base = five_assets()
    no_last_open = replace(
        base,
        sessions=tuple(
            bar
            for bar in base.sessions
            if not (bar.instrument.leveraged and bar.open_at == at(2))
        ),
    )
    result = run_cap_control_reference(no_last_open, sell_costs())
    assert result.sales == ()
    assert result.attempts[-1].status == "window_end_unfilled"
    assert result.leverage_breached


def test_natural_recovery_and_partial_repair_are_distinct() -> None:
    base = five_assets()
    lever = base.cohort[0]
    recovered = replace(
        base,
        sessions=tuple(
            replace(bar, raw_open=D("100"), raw_close=D("100"))
            if bar.instrument == lever and bar.open_at == at(2)
            else bar
            for bar in base.sessions
        ),
    )
    natural = run_cap_control_reference(recovered, sell_costs())
    assert natural.sales == ()
    assert natural.attempts[0].status == "natural_recovery"
    assert natural.leverage_breached

    extra = tuple(Instrument("KR", "KRX", f"X{i}", PIN, i in (0, 1)) for i in range(10))
    bars = tuple(
        RawSession(
            item,
            at(day),
            at(day, 3),
            D("100"),
            D("300") if day == 1 and item.leveraged else D("100"),
            at(day),
            at(day, 3),
        )
        for day in (0, 1)
        for item in extra
    ) + (RawSession(extra[0], at(2), at(2, 3), D("100"), D("100"), at(2), at(2, 3)),)
    data = replace(
        base, registered=extra, cohort=extra, sessions=bars, evaluation_end=at(2, 4)
    )
    partial = run_cap_control_reference(data, sell_costs())
    assert partial.sales[0].quantity == D("100000")
    assert partial.attempts[0].status == "partial_unresolved"
    assert partial.attempts[-1].status == "window_end_unfilled"
    assert partial.points[-1].leverage_breach

    second_open = RawSession(
        extra[1], at(2), at(2, 3), D("300"), D("300"), at(2), at(2, 3)
    )
    both = run_cap_control_reference(
        replace(data, sessions=(second_open,) + bars), sell_costs()
    )
    assert [sale.instrument.symbol for sale in both.sales] == ["X0", "X1"]
    assert both.attempts[0].status == "repaired"
    assert not both.points[-1].leverage_breach


@pytest.mark.parametrize(
    "change",
    [
        lambda x: replace(x, notional_tax_kr=None),
        lambda x: replace(x, notional_tax_kr=rate("NaN")),
        lambda x: replace(x, notional_tax_kr=rate("-0.01")),
        lambda x: replace(x, notional_tax_kr=RateAssumption(D("0"), "", PIN)),
        lambda x: replace(x, tax_basis="actual_etf_tax"),
        lambda x: replace(x, commission_kr=rate("0.5"), slippage_kr=rate("0.5")),
    ],
)
def test_unsupported_or_missing_sell_cost_fails(change: object) -> None:
    with pytest.raises(ReferenceInputError):
        run_cap_control_reference(five_assets(), change(sell_costs()))  # type: ignore[operator]
