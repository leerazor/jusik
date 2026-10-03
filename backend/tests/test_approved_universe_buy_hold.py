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
    run_buy_hold_reference,
)

PIN = "a" * 64
START = datetime(2026, 1, 1, tzinfo=UTC)
D = Decimal


def time(day: int, hour: int = 0) -> datetime:
    return START + timedelta(days=day, hours=hour)


def assumption(rate: str, label: str) -> RateAssumption:
    return RateAssumption(D(rate), label, PIN)


def costs() -> CostAssumptions:
    return CostAssumptions(
        assumption("0.01", "KR commission synthetic assumption"),
        assumption("0.01", "US commission synthetic assumption"),
        assumption("0", "KR slippage synthetic zero"),
        assumption("0", "US slippage synthetic zero"),
        assumption("0", "KR buy tax synthetic zero"),
        assumption("0", "US buy tax synthetic zero"),
        assumption("0.01", "FX spread synthetic assumption"),
        assumption("0", "KR withholding synthetic zero"),
        assumption("0.25", "US withholding synthetic assumption"),
    )


def fixture() -> FrozenReferenceInput:
    kr = tuple(
        Instrument("KR", "KRX", name, PIN, name == "L") for name in ("A", "L", "C")
    )
    us = tuple(Instrument("US", "NAS", name, PIN, False) for name in ("U", "V"))
    cohort = kr + us
    sessions: list[RawSession] = []
    for day in (0, 1):
        for item in cohort:
            opening = time(day, 4 if item.market == "US" else 0)
            closing = time(day, 10 if item.market == "US" else 3)
            price = D("100") if item.market == "US" else D("10000")
            closing_price = D("20000") if day == 1 and item.symbol == "L" else price
            if day == 1 and item.symbol == "A":
                price = D("5000")
                closing_price = price
            sessions.append(
                RawSession(
                    item, opening, closing, price, closing_price, opening, closing
                )
            )
    return FrozenReferenceInput(
        1,
        PIN,
        cohort,
        cohort,
        "synthetic five-name common cohort",
        time(0),
        time(2, 1),
        tuple(sessions),
        PIN,
        True,
        PIN,
        True,
        (
            SplitEvent(kr[0], "split-A", time(1), time(0), D("2"), PIN),
            DividendEvent(
                us[0], "div-U", time(1, 4), time(2), time(0), D("1"), D("0.5"), PIN
            ),
        ),
        PIN,
        True,
        (
            FXObservation(time(0), time(0), D("1000")),
            FXObservation(time(1), time(1), D("1000")),
            FXObservation(time(2), time(2), D("1000")),
        ),
        PIN,
        True,
        costs(),
    )


def test_independent_kr_us_accounting_oracle() -> None:
    result = run_buy_hold_reference(fixture())
    assert result.status == "reference_only"
    assert len(result.trades) == 5
    assert all(
        t.quantity == D("1980") and t.total_krw == D("19998000")
        for t in result.trades[:3]
    )
    assert all(
        t.quantity == D("196") and t.total_krw == D("19993960")
        for t in result.trades[3:]
    )
    assert [t.fx_spread_krw for t in result.trades[3:]] == [D("197960"), D("197960")]
    assert len(result.dividends) == 2
    assert [
        (x.phase, x.gross_local, x.taxable_local, x.withholding_local, x.net_local)
        for x in result.dividends
    ] == [
        ("accrual", D("196"), D("98"), D("24.50"), D("171.50")),
        ("payment", D("196"), D("98"), D("24.50"), D("171.50")),
    ]
    accrual = next(
        p for p in result.points if p.phase == "dividend_ex" and p.at == time(1, 4)
    )
    payment = next(p for p in result.points if p.phase == "dividend_payment")
    assert accrual.receivables_usd == D("171.50")
    assert payment.receivables_usd == 0
    assert payment.cash_usd == D("171.50")
    assert payment.cash_krw == D("18080")
    assert payment.nav_krw == D("118589580")
    assert result.points[-1].nav_krw == D("118589580")
    assert next(
        x for x in payment.positions if x.instrument.symbol == "A"
    ).quantity == D("3960")
    assert next(
        x for x in payment.positions if x.instrument.symbol == "U"
    ).quantity == D("196")
    assert result.leverage_breached
    assert any(
        p.leverage_breach and p.leveraged_fraction > D("0.20") for p in result.points
    )
    assert result.investment_qualification == "not_evaluated"


def test_future_fx_poison_is_ignored_and_missing_prior_fx_rejected() -> None:
    base = fixture()
    poison = FXObservation(time(0), time(3), D("9999"))
    clean = run_buy_hold_reference(base)
    tainted = run_buy_hold_reference(replace(base, fx=base.fx + (poison,)))
    assert tainted.points == clean.points
    assert tainted.trades == clean.trades
    with pytest.raises(ReferenceInputError, match="historically available FX missing"):
        run_buy_hold_reference(replace(base, fx=(poison,)))


def test_ex_at_first_buy_does_not_create_entitlement() -> None:
    base = fixture()
    later = cast(DividendEvent, base.actions[1])
    early = replace(later, ex_at=time(0, 4), payment_at=time(2))
    result = run_buy_hold_reference(replace(base, actions=(base.actions[0], early)))
    assert result.dividends == ()
    assert result.points[-1].cash_usd == 0


def test_fractional_split_requires_explicit_cash_in_lieu_rule() -> None:
    base = fixture()
    split = cast(SplitEvent, base.actions[0])
    with pytest.raises(ReferenceInputError, match="fractional split"):
        run_buy_hold_reference(
            replace(base, actions=(replace(split, ratio=D("0.125")), base.actions[1]))
        )


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (
            lambda x: replace(x, official_calendar_complete=False),
            "official_calendar_complete",
        ),
        (
            lambda x: replace(x, price_coverage_complete=False),
            "price_coverage_complete",
        ),
        (
            lambda x: replace(x, action_coverage_complete=False),
            "action_coverage_complete",
        ),
        (lambda x: replace(x, fx_coverage_complete=False), "fx_coverage_complete"),
        (
            lambda x: replace(
                x, costs=replace(x.costs, buy_tax_us=cast(RateAssumption, None))
            ),
            "buy_tax_us",
        ),
        (lambda x: replace(x, cohort=x.cohort + (x.cohort[0],)), "duplicate"),
        (
            lambda x: replace(x, registered=x.registered[:-1]),
            "registered identity subset",
        ),
        (
            lambda x: replace(
                x, sessions=tuple(b for b in x.sessions if b.instrument.symbol != "V")
            ),
            "missing cohort sessions",
        ),
        (
            lambda x: replace(
                x,
                sessions=(replace(x.sessions[0], price_basis="adjusted"),)
                + x.sessions[1:],
            ),
            "raw prices",
        ),
        (
            lambda x: replace(
                x,
                sessions=(replace(x.sessions[0], raw_open=D("NaN")),) + x.sessions[1:],
            ),
            "finite Decimal",
        ),
        (
            lambda x: replace(
                x,
                sessions=(replace(x.sessions[0], open_observed_at=time(0, 1)),)
                + x.sessions[1:],
            ),
            "future price",
        ),
        (
            lambda x: replace(x, actions=x.actions + (x.actions[0],)),
            "action identity duplicate",
        ),
        (
            lambda x: replace(
                x,
                actions=(replace(cast(DividendEvent, x.actions[1]), ex_at=time(1, 5)),),
            ),
            "official instrument open",
        ),
        (
            lambda x: replace(
                x,
                actions=(
                    replace(
                        cast(DividendEvent, x.actions[1]), taxable_per_share=D("2")
                    ),
                ),
            ),
            "taxable dividend exceeds gross",
        ),
    ],
)
def test_incomplete_or_inconsistent_fixture_rejected(
    change: object, message: str
) -> None:
    adjusted = change(fixture())  # type: ignore[operator]
    with pytest.raises(ReferenceInputError, match=message):
        run_buy_hold_reference(adjusted)


def test_initial_infeasible_leverage_cohort_rejected() -> None:
    base = fixture()
    with pytest.raises(ReferenceInputError, match="initial equal cohort"):
        run_buy_hold_reference(replace(base, cohort=(base.cohort[1], base.cohort[0])))


def test_same_time_split_precedes_ex_and_end_fx_revalues_nav() -> None:
    base = fixture()
    kr_dividend = DividendEvent(
        base.cohort[0],
        "kr-post-split",
        time(1),
        time(2),
        time(0),
        D("100"),
        D("60"),
        PIN,
    )
    changed = replace(
        base,
        actions=base.actions + (kr_dividend,),
        fx=base.fx + (FXObservation(time(2, 1), time(2, 1), D("1100")),),
    )
    result = run_buy_hold_reference(changed)
    kr_accrual = next(
        x
        for x in result.dividends
        if x.action_id == "kr-post-split" and x.phase == "accrual"
    )
    assert kr_accrual.quantity == D("3960")
    assert kr_accrual.gross_local == D("396000")
    prior = next(
        x for x in result.points if x.phase == "dividend_payment" and x.at == time(2)
    )
    final = result.points[-1]
    assert final.at == time(2, 1) and final.phase == "evaluation_end"
    assert final.nav_krw - prior.nav_krw == D("3937150")
    assert final.nav_krw == D("122922730")


def test_simultaneous_opposite_closes_do_not_create_drawdown() -> None:
    left = Instrument("KR", "KRX", "LEFT", PIN, False)
    right = Instrument("KR", "KRX", "RIGHT", PIN, False)
    base = fixture()
    sessions = tuple(
        RawSession(
            item, time(day), time(day, 3), D("10000"), close, time(day), time(day, 3)
        )
        for day in (0, 1)
        for item, close in (
            (left, D("5000") if day == 1 else D("10000")),
            (right, D("15000") if day == 1 else D("10000")),
        )
    )
    data = replace(
        base,
        registered=(left, right),
        cohort=(left, right),
        sessions=sessions,
        actions=(),
        fx=(),
        evaluation_end=time(1, 4),
        costs=replace(base.costs, commission_kr=assumption("0", "zero KR commission")),
    )
    result = run_buy_hold_reference(data)
    assert len([p for p in result.points if p.at == time(1, 3)]) == 1
    assert all(p.nav_krw == D("100000000") for p in result.points)
    assert result.max_drawdown_fraction == 0
    assert not result.drawdown_breached
    real_loss = replace(
        data,
        sessions=tuple(
            replace(bar, raw_close=D("10000"))
            if bar.instrument == right and bar.open_at == time(1)
            else bar
            for bar in data.sessions
        ),
    )
    losing_result = run_buy_hold_reference(real_loss)
    assert losing_result.max_drawdown_fraction == D("0.25")
    assert losing_result.drawdown_breached


def test_simultaneous_ex_and_open_do_not_create_peak_or_drawdown() -> None:
    item = Instrument("KR", "KRX", "DIV", PIN, False)
    base = fixture()
    dividend = DividendEvent(
        item, "div", time(1), time(2), time(0), D("3000"), D("0"), PIN
    )
    data = replace(
        base,
        registered=(item,),
        cohort=(item,),
        sessions=(
            RawSession(
                item, time(0), time(0, 3), D("10000"), D("10000"), time(0), time(0, 3)
            ),
            RawSession(
                item, time(1), time(1, 3), D("7000"), D("7000"), time(1), time(1, 3)
            ),
        ),
        actions=(dividend,),
        fx=(),
        evaluation_end=time(2, 1),
        costs=replace(base.costs, commission_kr=assumption("0", "zero KR commission")),
    )
    result = run_buy_hold_reference(data)
    assert len([p for p in result.points if p.at == time(1)]) == 1
    assert [(x.phase, x.net_local) for x in result.dividends] == [
        ("accrual", D("30000000")),
        ("payment", D("30000000")),
    ]
    assert all(p.nav_krw == D("100000000") for p in result.points)
    assert result.max_drawdown_fraction == 0
    assert not result.drawdown_breached


def test_fx_prefers_latest_effective_then_latest_available_revision() -> None:
    item = Instrument("US", "NAS", "FX", PIN, False)
    base = fixture()
    sessions = tuple(
        RawSession(
            item, time(day), time(day, 3), D("100"), D("100"), time(day), time(day, 3)
        )
        for day in (0, 1, 2)
    )
    data = replace(
        base,
        registered=(item,),
        cohort=(item,),
        sessions=sessions,
        actions=(),
        evaluation_end=time(2, 4),
        fx=(
            FXObservation(time(0), time(0), D("1000")),
            FXObservation(time(1), time(1), D("1100")),
            FXObservation(time(0), time(2), D("900")),
            FXObservation(time(1), time(2, 1), D("1200")),
        ),
        costs=replace(
            base.costs,
            commission_us=assumption("0", "zero US commission"),
            fx_spread=assumption("0", "zero FX spread"),
        ),
    )
    result = run_buy_hold_reference(data)
    assert next(p for p in result.points if p.at == time(2)).nav_krw == D("110000000")
    assert next(p for p in result.points if p.at == time(2, 3)).nav_krw == D(
        "120000000"
    )
    assert result.points[-1].nav_krw == D("120000000")
