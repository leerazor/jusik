"""Synthetic risk path through the real selected planner and one raw ledger."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

import pytest

import jusik.selected_candidate_kr_policy as policy_module
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
    _policy_cap_sell_quantity,
)
from jusik.selected_candidate_kr_policy import (
    KRCandidateRiskReference,
    PolicyInputError,
    run_kr_selected_candidate_risk_reference,
)
from jusik.selected_candidate_signals import (
    AdjustedClose,
    CandidateMethod,
    FrozenSignalInput,
    SignalPlan,
    plan_selected_candidate,
)

D = Decimal
PIN = "a" * 64
RAW_PIN = "b" * 64
SIGNAL_PIN = "c" * 64
CALENDAR_PIN = "d" * 64
CONFIG = (
    Path(__file__).parents[2] / "docs/research/selected-candidate-config-v1.json"
).read_bytes()
CONFIG_SHA = hashlib.sha256(CONFIG).hexdigest()
FIRST = datetime(2026, 3, 9, tzinfo=UTC)


def at(days: int, hours: int = 0) -> datetime:
    return FIRST + timedelta(days=days, hours=hours)


def rate(value: str) -> RateAssumption:
    return RateAssumption(D(value), "explicit synthetic test", PIN)


def sell_costs(value: str = ".01") -> SellCostAssumptions:
    zero = rate("0")
    return SellCostAssumptions(rate(value), zero, zero, zero, zero, zero, "notional")


def fixture(
    *,
    closes: dict[int, tuple[str, str]] | None = None,
    opens: dict[int, tuple[str, str]] | None = None,
    leveraged: bool = False,
    dividend: bool = False,
    end_day: int = 64,
) -> tuple[FrozenReferenceInput, FrozenSignalInput]:
    items = (
        Instrument("KR", "KRX", "A", PIN, leveraged),
        Instrument("KR", "KRX", "B", PIN, False),
    )
    close_prices = {2: ("75", "75")} if closes is None else closes
    open_prices = {3: ("75", "75"), 57: ("100", "100")} if opens is None else opens
    days = sorted(
        day for day in {1, 2, 3, 57, *close_prices, *open_prices} if day < end_day
    )
    bars = tuple(
        RawSession(
            item,
            at(day),
            at(day, 3),
            D(open_prices.get(day, ("100", "100"))[index]),
            D(close_prices.get(day, open_prices.get(day, ("100", "100")))[index]),
            at(day),
            at(day, 3),
        )
        for day in days
        for index, item in enumerate(items)
    )
    actions = (
        (DividendEvent(items[0], "div-A", at(3), at(11), at(3), D(2), D(1), PIN),)
        if dividend
        else ()
    )
    zero = rate("0")
    costs = CostAssumptions(zero, zero, zero, zero, zero, zero, zero, rate(".1"), zero)
    raw = FrozenReferenceInput(
        1,
        PIN,
        items,
        items,
        "synthetic risk cohort",
        FIRST,
        at(end_day),
        bars,
        CALENDAR_PIN,
        True,
        RAW_PIN,
        True,
        actions,
        PIN,
        True,
        (),
        PIN,
        True,
        costs,
    )
    rows: list[AdjustedClose] = []
    history_start = FIRST - timedelta(days=100)
    for item in items:
        price = D(100)
        for index in range(190):
            if index:
                price *= D("1.002") + (D(".001") if index % 2 else D("-.001"))
            moment = history_start + timedelta(days=index)
            rows.append(
                AdjustedClose(
                    item,
                    moment,
                    moment,
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
        CONFIG_SHA,
        SIGNAL_PIN,
        PIN,
        CALENDAR_PIN,
        "synthetic_unverified",
        tuple(rows),
        (),
        FIRST,
    )
    return raw, signal


def run(
    raw: FrozenReferenceInput,
    signal: FrozenSignalInput,
    method: CandidateMethod = "equal",
    *,
    sale_cost: str = ".01",
) -> KRCandidateRiskReference:
    return run_kr_selected_candidate_risk_reference(
        raw, signal, CONFIG, method, sell_costs(sale_cost)
    )


@pytest.mark.parametrize("method", ("equal", "inverse_volatility"))
def test_full_risk_liquidation_cooldown_recovery_and_later_reentry(
    method: CandidateMethod,
) -> None:
    raw, signal = fixture(dividend=True)
    result = run(raw, signal, method)
    assert result.status == "synthetic_reference_only"
    assert result.investment_qualification == "not_evaluated"
    assert [
        event.status
        for event in result.risk_events
        if event.status
        in {"latched", "liquidation_completed", "reentry_ready", "reentry_decision"}
    ] == ["latched", "liquidation_completed", "reentry_ready", "reentry_decision"]
    assert [
        (event.at, event.status)
        for event in result.risk_events
        if event.status
        in {"latched", "liquidation_completed", "reentry_ready", "reentry_decision"}
    ] == [
        (at(2, 3), "latched"),
        (at(3), "liquidation_completed"),
        (at(42), "reentry_ready"),
        (at(56), "reentry_decision"),
    ]
    assert [decision.at for decision in result.decisions] == [FIRST, at(56)]
    assert [(batch.decided_at, batch.open_at) for batch in result.ledger.batches] == [
        (FIRST, at(1)),
        (at(2, 3), at(3)),
        (at(56), at(57)),
    ]
    assert [sale.quantity for sale in result.ledger.sales] == [D(200000)] * 2
    liquidation = next(
        p for p in result.ledger.points if p.at == at(3) and p.phase == "open"
    )
    assert all(position.quantity == 0 for position in liquidation.positions)
    assert liquidation.receivables_krw == D(380000)
    assert liquidation.cash_krw == D(89700000)
    assert liquidation.nav_krw == D(90080000)
    payment = next(x for x in result.ledger.dividends if x.phase == "payment")
    assert payment.quantity == D(200000)
    assert payment.net_local == D(380000)
    assert result.episode_peak_krw == D(90080000)
    assert result.lifetime_peak_krw == D(100000000)
    assert result.episode_max_drawdown_fraction == D(".10")
    assert result.ledger.max_drawdown_fraction == D(".10")


def test_exact_threshold_and_strict_later_common_open() -> None:
    raw, signal = fixture(dividend=False)
    result = run(raw, signal)
    trigger = next(
        p for p in result.ledger.points if p.at == at(2, 3) and p.phase == "close"
    )
    assert trigger.nav_krw == D(90000000)
    assert trigger.drawdown_fraction == D(".10")
    assert all(sale.at > trigger.at for sale in result.ledger.sales)
    assert all(sale.at == at(3) for sale in result.ledger.sales)


def test_split_before_queued_liquidation_preserves_native_basis_and_quantity() -> None:
    raw, signal = fixture(opens={3: ("37.5", "75"), 57: ("100", "100")})
    raw = replace(
        raw,
        actions=(SplitEvent(raw.cohort[0], "split-A", at(3), at(3), D(2), PIN),),
    )
    result = run(raw, signal)
    sales = result.ledger.sales[:2]
    assert [
        (sale.instrument.symbol, sale.quantity, sale.raw_price) for sale in sales
    ] == [
        ("A", D(400000), D("37.5")),
        ("B", D(200000), D(75)),
    ]
    assert sum(sale.proceeds_local for sale in sales) == D(29700000)
    point = next(p for p in result.ledger.points if p.at == at(3) and p.phase == "open")
    assert point.cash_krw == D(89700000)
    assert all(position.quantity == 0 for position in point.positions)


def test_cap_repair_minimal_integer_and_natural_recovery() -> None:
    raw, signal = fixture(
        leveraged=True,
        closes={2: ("150", "100"), 3: ("100", "100"), 4: ("150", "100")},
        opens={
            3: ("100", "100"),
            4: ("100", "100"),
            5: ("150", "100"),
            57: ("100", "100"),
        },
        end_day=13,
    )
    result = run(raw, signal)
    assert [
        (event.observed_at, event.at, event.status) for event in result.cap_events
    ] == [
        (at(2, 3), at(2, 3), "observed"),
        (at(2, 3), at(3), "natural_recovery"),
        (at(4, 3), at(4, 3), "observed"),
        (at(4, 3), at(5), "repaired"),
    ]
    assert len(result.ledger.sales) == 1
    sale = result.ledger.sales[0]
    assert sale.at == at(5) and sale.instrument.symbol == "A"
    before = next(
        p for p in result.ledger.points if p.at == at(5) and p.phase == "pre_cap_repair"
    )
    n, leverage = Fraction(before.nav_krw), Fraction(before.leveraged_value_krw)
    unit, cost = Fraction(150), Fraction(1, 100)
    q = (leverage - n / 5) / (unit * (1 - cost / 5))
    expected = -(-q.numerator // q.denominator)
    assert sale.quantity == expected
    assert leverage - (expected - 1) * unit > (n - (expected - 1) * unit * cost) / 5
    assert sale.post_leveraged_value_krw <= sale.post_nav_krw / 5


@pytest.mark.parametrize(
    ("nav", "gross", "leverage", "owned", "price", "cost", "held", "leveraged"),
    (
        ("1000", "700", "250", "400", "100", ".01", "4", True),
        ("1000", "700", "100", "300", "100", ".05", "3", False),
        ("1000", "500", "300", "300", "50", ".02", "6", True),
        ("1000", "650", "250", "250", "50", ".10", "5", True),
    ),
)
def test_small_exhaustive_post_cost_cap_sale_oracle(
    nav: str,
    gross: str,
    leverage: str,
    owned: str,
    price: str,
    cost: str,
    held: str,
    leveraged: bool,
) -> None:
    n, g, lev, own = map(Fraction, (nav, gross, leverage, owned))
    p, c = Fraction(price), Fraction(cost)
    feasible = [
        q
        for q in range(int(held) + 1)
        if own - q * p <= (n - q * p * c) / 5
        and g - q * p <= (n - q * p * c) * Fraction(3, 5)
        and lev - (q * p if leveraged else 0) <= (n - q * p * c) / 5
    ]
    assert feasible
    actual = _policy_cap_sell_quantity(
        D(nav),
        D(gross),
        D(leverage),
        D(owned),
        D(price),
        D(cost),
        D(held),
        leveraged=leveraged,
    )
    assert actual == min(feasible)


def test_missing_liquidation_open_fails_closed() -> None:
    raw, signal = fixture(end_day=10)
    raw = replace(
        raw, sessions=tuple(bar for bar in raw.sessions if bar.open_at != at(3))
    )
    with pytest.raises(ReferenceInputError, match="next official open"):
        run(raw, signal)


def test_second_confirmation_on_cadence_waits_next_four_week_decision() -> None:
    raw, signal = fixture(
        closes={19: ("75", "75")},
        opens={20: ("75", "75"), 85: ("100", "100")},
        end_day=90,
    )
    result = run(raw, signal)
    important = [
        (event.at, event.status)
        for event in result.risk_events
        if event.status
        in ("liquidation_completed", "reentry_ready", "reentry_decision")
    ]
    assert important == [
        (at(20), "liquidation_completed"),
        (at(56), "reentry_ready"),
        (at(84), "reentry_decision"),
    ]
    assert result.ledger.batches[-1].open_at == at(85)


def test_cooldown_monday_before_and_on_utc_date_plus_28() -> None:
    raw, signal = fixture(
        closes={6: ("75", "75")},
        opens={7: ("75", "75"), 57: ("100", "100")},
    )
    result = run(raw, signal)
    assert any(
        event.at == at(28) and event.status == "cooldown"
        for event in result.risk_events
    )
    assert [
        (event.at, event.consecutive_confirmations)
        for event in result.risk_events
        if event.status == "recovery_confirmed"
    ][:2] == [(at(35), 1), (at(42), 2)]
    assert result.ledger.batches[-1].open_at == at(57)


def test_one_asset_recovery_resets_streak_before_next_two_confirmations() -> None:
    raw, signal = fixture()
    revised = tuple(
        replace(row, adjusted_close=D(1))
        if row.instrument.symbol == "B" and row.official_close_at == at(35)
        else row
        for row in signal.closes
    )
    result = run(raw, replace(signal, closes=revised))
    at_35 = [event for event in result.risk_events if event.at == at(35)]
    assert [(event.status, event.consecutive_confirmations) for event in at_35] == [
        ("recovery_reset", 0)
    ]
    assert next(
        event.at for event in result.risk_events if event.status == "reentry_ready"
    ) == at(49)
    assert result.ledger.batches[-1].open_at == at(57)


def test_incomplete_recovery_resets_ready_and_does_not_become_cash_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw, signal = fixture()

    def incomplete_on_confirmation(
        data: FrozenSignalInput, candidate: CandidateMethod, config_json: bytes
    ) -> SignalPlan:
        planned = plan_selected_candidate(data, candidate, config_json)
        if data.decided_at == at(42):
            return replace(
                planned, status="incomplete", targets=None, reason="test_gap"
            )
        return planned

    monkeypatch.setattr(
        policy_module, "plan_selected_candidate", incomplete_on_confirmation
    )
    result = run(raw, signal)
    assert any(
        event.at == at(42)
        and event.status == "recovery_reset"
        and event.reason == "test_gap"
        for event in result.risk_events
    )
    assert next(
        event.at for event in result.risk_events if event.status == "reentry_ready"
    ) == at(56)
    assert all(batch.decided_at != at(56) for batch in result.ledger.batches)


def test_completed_close_cancels_pending_normal_vector_before_open() -> None:
    raw, signal = fixture(
        closes={27: ("75", "75")},
        opens={30: ("75", "75")},
        end_day=40,
    )
    raw = replace(
        raw,
        sessions=tuple(
            replace(bar, close_at=at(29, 3), close_observed_at=at(29, 3))
            if bar.open_at == at(27)
            else bar
            for bar in raw.sessions
        ),
    )
    result = run(raw, signal)
    assert [batch.decided_at for batch in result.ledger.batches] == [FIRST, at(29, 3)]
    assert result.ledger.batches[-1].open_at == at(30)
    assert all(
        position.quantity == 0 for position in result.ledger.points[-1].positions
    )


def test_monday_close_and_open_same_instant_excludes_that_open() -> None:
    raw, signal = fixture(
        closes={27: ("75", "75")},
        opens={28: ("75", "75"), 29: ("75", "75")},
        end_day=35,
    )
    raw = replace(
        raw,
        sessions=tuple(
            replace(bar, close_at=at(28), close_observed_at=at(28))
            if bar.open_at == at(27) and bar.instrument.symbol == "A"
            else bar
            for bar in raw.sessions
            if not (bar.open_at == at(28) and bar.instrument.symbol == "A")
        ),
    )
    result = run(raw, signal)
    assert any(
        event.at == at(28) and event.status == "latched" for event in result.risk_events
    )
    assert result.ledger.batches[-1].open_at == at(29)
    assert all(sale.at > at(28) for sale in result.ledger.sales)


def test_prior_cap_breach_uses_single_scheduled_vector_not_extra_repair() -> None:
    raw, signal = fixture(
        leveraged=True,
        closes={2: ("150", "100")},
        opens={29: ("150", "100")},
        end_day=32,
    )
    raw = replace(
        raw, sessions=tuple(bar for bar in raw.sessions if bar.open_at != at(3))
    )
    result = run(raw, signal)
    assert len(result.ledger.batches) == 2
    assert result.ledger.batches[1].open_at == at(29)
    assert len(result.ledger.sales) == 1
    assert result.ledger.sales[0].at == at(29)
    assert result.cap_events[-1].status == "repaired_by_target"
    assert not any(
        p.at == at(29) and p.phase == "pre_cap_repair" for p in result.ledger.points
    )
    final = result.ledger.points[-1]
    assert final.leveraged_value_krw <= final.nav_krw / 5


def test_new_open_gap_breach_waits_next_common_open() -> None:
    raw, signal = fixture(
        leveraged=True,
        closes={},
        opens={3: ("150", "100"), 4: ("150", "100")},
        end_day=10,
    )
    result = run(raw, signal)
    assert all(sale.at != at(3) for sale in result.ledger.sales)
    assert result.ledger.sales[0].at == at(4)
    assert any(p.at == at(3) and p.leverage_breach for p in result.ledger.points)


def test_risk_exit_takes_priority_over_prior_cap_repair() -> None:
    raw, signal = fixture(
        leveraged=True,
        closes={2: ("125", "25")},
        opens={3: ("125", "25")},
        end_day=10,
    )
    result = run(raw, signal)
    assert result.ledger.batches[-1].decided_at == at(2, 3)
    assert result.ledger.batches[-1].sold == (
        (raw.cohort[0], D(200000)),
        (raw.cohort[1], D(200000)),
    )
    assert len(result.ledger.sales) == 2
    assert not any(p.phase == "pre_cap_repair" for p in result.ledger.points)
    assert result.ledger.leverage_breached is True


def test_lifetime_drawdown_history_survives_episode_reset() -> None:
    raw, signal = fixture(
        closes={2: ("75", "75"), 57: ("20", "20")},
        opens={3: ("75", "75"), 57: ("100", "100"), 58: ("20", "20")},
    )
    result = run(raw, signal)
    assert (
        len([event for event in result.risk_events if event.status == "latched"]) == 2
    )
    assert result.ledger.drawdown_breached is True
    assert result.ledger.max_drawdown_fraction > D(".20")
    assert result.lifetime_peak_krw == D(100000000)


def test_cap_without_later_common_open_fails_closed() -> None:
    raw, signal = fixture(leveraged=True, closes={2: ("150", "100")}, end_day=10)
    raw = replace(
        raw, sessions=tuple(bar for bar in raw.sessions if bar.open_at != at(3))
    )
    with pytest.raises(ReferenceInputError, match="cap repair window_end_unfilled"):
        run(raw, signal)


def test_registry_calendar_config_pins_and_future_revision() -> None:
    raw, signal = fixture()
    with pytest.raises(PolicyInputError, match="identity or calendar"):
        run(raw, replace(signal, registration_hash="e" * 64))
    with pytest.raises(PolicyInputError, match="identity or calendar"):
        run(raw, replace(signal, calendar_hash="e" * 64))
    with pytest.raises(PolicyInputError, match="config SHA-256"):
        run(raw, replace(signal, config_sha256="e" * 64))
    original = run(raw, signal)
    poison = replace(
        signal.closes[-1],
        adjusted_close=D(999999),
        revision=2,
        available_at=at(100),
    )
    assert run(raw, replace(signal, closes=signal.closes + (poison,))) == original
