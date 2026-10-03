"""Synthetic, causal checks for selected-candidate target planning."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal, cast

import pytest

from jusik.approved_universe_buy_hold import Instrument
from jusik.selected_candidate_signals import (
    AdjustedClose,
    FrozenSignalInput,
    SignalFX,
    SignalInputError,
    plan_selected_candidate,
)

CONFIG = Path(__file__).parents[2] / "docs/research/selected-candidate-config-v1.json"
CONFIG_BYTES = CONFIG.read_bytes()
CONFIG_HASH = hashlib.sha256(CONFIG_BYTES).hexdigest()
HASH = "a" * 64
START = datetime(2020, 1, 1, 16, tzinfo=UTC)
BASIS = "split_adjusted_close_for_signal_only"


def asset(
    symbol: str, *, market: Literal["KR", "US"] = "KR", leveraged: bool = False
) -> Instrument:
    return Instrument(
        market,
        "XKRX" if market == "KR" else "XNYS",
        symbol,
        hashlib.sha256(f"{market}:{symbol}".encode()).hexdigest(),
        leveraged,
    )


def closes(
    item: Instrument, amplitude: str = "0.001", count: int = 61
) -> tuple[AdjustedClose, ...]:
    price = Decimal(100)
    result = []
    for offset in range(count):
        if offset:
            direction = ONE if offset % 2 == 0 else -ONE
            price *= ONE + Decimal("0.01") + direction * Decimal(amplitude)
        at = START + timedelta(days=offset)
        result.append(AdjustedClose(item, at, at, price, 1, BASIS))
    return tuple(result)


ONE = Decimal(1)


def fixture(
    *items: Instrument, rows: tuple[AdjustedClose, ...] | None = None
) -> FrozenSignalInput:
    if rows is None:
        rows = tuple(row for item in items for row in closes(item))
    return FrozenSignalInput(
        1,
        HASH,
        items,
        items,
        CONFIG_HASH,
        HASH,
        HASH,
        HASH,
        "synthetic_unverified",
        rows,
        (),
        START + timedelta(days=61),
    )


def weights(result: object, field: str = "targets") -> tuple[Decimal, ...]:
    values = getattr(result, field)
    assert values is not None
    return tuple(value.weight for value in values)


def test_four_asset_independent_weight_oracle_and_scale() -> None:
    items = tuple(asset(letter) for letter in "ABCD")
    rows = tuple(
        row
        for item, amplitude in zip(
            items, ("0.001", "0.002", "0.004", "0.004"), strict=True
        )
        for row in closes(item, amplitude)
    )
    data = fixture(*items, rows=rows)
    equal = plan_selected_candidate(data, "equal", CONFIG_BYTES)
    inverse = plan_selected_candidate(data, "inverse_volatility", CONFIG_BYTES)
    assert equal.status == inverse.status == "ready"
    assert weights(equal, "pre_scale") == (Decimal("0.15"),) * 4
    for actual, expected in zip(
        weights(inverse, "pre_scale"),
        (Decimal("0.20"), Decimal("0.20"), Decimal("0.10"), Decimal("0.10")),
        strict=True,
    ):
        assert abs(actual - expected) < Decimal("1e-22")
    # Independent arithmetic: population sigma of alternating ±a returns is a.
    annualizer = Decimal(252).sqrt()
    assert equal.volatility_proxy is not None
    assert inverse.volatility_proxy is not None
    assert abs(equal.volatility_proxy - Decimal("0.00165") * annualizer) < Decimal(
        "1e-20"
    )
    assert abs(inverse.volatility_proxy - Decimal("0.0014") * annualizer) < Decimal(
        "1e-20"
    )
    assert equal.volatility_scale == inverse.volatility_scale == ONE
    assert equal.cash_weight == inverse.cash_weight == Decimal("0.40")
    assert equal.investment_qualification == "not_evaluated"


def test_volatility_scale_reduces_final_targets_and_preserves_cash() -> None:
    items = (asset("A"), asset("B"))
    rows = closes(items[0], "0.03") + closes(items[1], "0.06")
    result = plan_selected_candidate(fixture(*items, rows=rows), "equal", CONFIG_BYTES)
    assert result.status == "ready"
    assert weights(result, "pre_scale") == (Decimal("0.20"),) * 2
    assert result.volatility_proxy is not None and result.volatility_proxy > Decimal(
        "0.10"
    )
    assert result.volatility_scale == Decimal("0.10") / result.volatility_proxy
    assert weights(result) == tuple(
        Decimal("0.20") * result.volatility_scale for _ in items
    )
    assert result.cash_weight == ONE - sum(weights(result))


def test_registered_leveraged_classification_and_single_asset_cap() -> None:
    items = (asset("A", leveraged=True), asset("B", leveraged=True), asset("C"))
    result = plan_selected_candidate(fixture(*items), "equal", CONFIG_BYTES)
    assert weights(result, "pre_scale") == (
        Decimal("0.10"),
        Decimal("0.10"),
        Decimal("0.20"),
    )
    solo = plan_selected_candidate(fixture(items[0]), "equal", CONFIG_BYTES)
    assert weights(solo) == (Decimal("0.20"),)
    assert solo.cash_weight == Decimal("0.80")


def test_many_equal_assets_keep_exact_gross_cap_and_stable_identity_order() -> None:
    items = tuple(asset(letter) for letter in "ABCDEFG")
    data = fixture(*items)
    forward = plan_selected_candidate(data, "equal", CONFIG_BYTES)
    reversed_data = replace(
        data, registered=items[::-1], cohort=items[::-1], closes=data.closes[::-1]
    )
    assert plan_selected_candidate(reversed_data, "equal", CONFIG_BYTES) == forward
    assert sum(weights(forward, "pre_scale")) == Decimal("0.60")
    assert forward.cash_weight == Decimal("0.40")


def test_zero_volatility_inverse_excludes_but_equal_accepts() -> None:
    item = asset("A")
    price = Decimal(100)
    rows = []
    for offset in range(61):
        if offset:
            price *= Decimal("1.01")
        at = START + timedelta(days=offset)
        rows.append(AdjustedClose(item, at, at, price, 1, BASIS))
    data = fixture(item, rows=tuple(rows))
    equal = plan_selected_candidate(data, "equal", CONFIG_BYTES)
    inverse = plan_selected_candidate(data, "inverse_volatility", CONFIG_BYTES)
    assert equal.eligibility[0].reason == "eligible"
    assert inverse.eligibility[0].reason == "zero_volatility"
    assert weights(inverse) == (Decimal(0),)
    assert inverse.cash_weight == ONE and inverse.volatility_proxy == Decimal(0)


def test_insufficient_signal_history_is_valid_all_cash() -> None:
    item = asset("A")
    result = plan_selected_candidate(
        fixture(item, rows=closes(item, count=60)), "equal", CONFIG_BYTES
    )
    assert result.status == "ready"
    assert result.eligibility[0].reason == "insufficient_closes"
    assert weights(result) == (Decimal(0),)
    assert result.cash_weight == ONE


def test_sma_requires_strictly_above_trailing_average() -> None:
    item = asset("A")
    rows = tuple(replace(row, adjusted_close=Decimal(100)) for row in closes(item))
    result = plan_selected_candidate(fixture(item, rows=rows), "equal", CONFIG_BYTES)
    assert result.eligibility[0].reason == "sma_not_above"
    assert weights(result) == (Decimal(0),)


def test_incomplete_proxy_has_no_targets() -> None:
    item = asset("A")
    original = fixture(item)
    # One close is known at decision but belongs to the decision UTC date, so
    # it can establish 61 signal closes but cannot become a proxy sample date.
    rows = closes(item, count=60)
    at = original.decided_at
    rows += (AdjustedClose(item, at, at, rows[-1].adjusted_close * 2, 1, BASIS),)
    result = plan_selected_candidate(
        replace(original, closes=rows), "equal", CONFIG_BYTES
    )
    assert result.status == "incomplete"
    assert result.reason == "insufficient_global_close_dates"
    assert (
        result.targets is None
        and result.pre_scale is None
        and result.cash_weight is None
    )


def test_future_close_and_late_revision_do_not_poison_decision() -> None:
    item = asset("A")
    base = fixture(item)
    original = plan_selected_candidate(base, "equal", CONFIG_BYTES)
    future = AdjustedClose(
        item,
        base.decided_at + timedelta(days=1),
        base.decided_at + timedelta(days=1),
        Decimal("999999"),
        1,
        BASIS,
    )
    late = replace(
        base.closes[-1],
        available_at=base.decided_at + timedelta(seconds=1),
        adjusted_close=Decimal("0.01"),
        revision=2,
    )
    poisoned = plan_selected_candidate(
        replace(base, closes=base.closes + (future, late)), "equal", CONFIG_BYTES
    )
    assert poisoned == original


def test_same_time_close_is_signal_eligible_but_not_global_proxy_date() -> None:
    item = asset("A")
    rows = closes(item, count=60)
    at = START + timedelta(days=60)
    simultaneous = AdjustedClose(item, at, at, rows[-1].adjusted_close * 2, 1, BASIS)
    data = replace(fixture(item), closes=rows + (simultaneous,), decided_at=at)
    result = plan_selected_candidate(data, "equal", CONFIG_BYTES)
    assert result.eligibility[0].reason == "eligible"
    assert result.status == "incomplete"
    delayed = replace(simultaneous, available_at=at + timedelta(seconds=1))
    delayed_result = plan_selected_candidate(
        replace(data, closes=rows + (delayed,)), "equal", CONFIG_BYTES
    )
    assert delayed_result.eligibility[0].reason == "insufficient_closes"
    assert delayed_result.status == "ready"


def test_historical_revision_is_not_backdated_to_earlier_proxy_cutoff() -> None:
    item = asset("A")
    other = asset("B")
    sparse = tuple(
        row for index, row in enumerate(closes(item, count=121)) if index % 2 == 0
    )
    base = replace(
        fixture(item, other, rows=sparse + closes(other, count=121)),
        decided_at=START + timedelta(days=121),
    )
    at = sparse[40].official_close_at
    revised = replace(
        sparse[40],
        revision=2,
        adjusted_close=Decimal("9999"),
        available_at=at + timedelta(days=1),
    )
    result = plan_selected_candidate(
        replace(base, closes=base.closes + (revised,)), "equal", CONFIG_BYTES
    )
    assert result.status == "ready"
    # A revision available after its close date changes the next gap day's
    # proxy sample, but cannot replace the earlier day-end sample.
    assert (
        result.volatility_proxy
        != plan_selected_candidate(base, "equal", CONFIG_BYTES).volatility_proxy
    )
    cutoff = at + timedelta(hours=1)
    early = replace(base, decided_at=cutoff, closes=base.closes + (revised,))
    control = replace(base, decided_at=cutoff)
    assert plan_selected_candidate(
        early, "equal", CONFIG_BYTES
    ) == plan_selected_candidate(control, "equal", CONFIG_BYTES)


def test_us_fx_causal_staleness_and_market_gap() -> None:
    kr = asset("K")
    us = asset("U", market="US")
    # US closes are every other day; global KR dates carry its last prior close.
    rows = closes(kr) + tuple(
        row for index, row in enumerate(closes(us, count=121)) if index % 2 == 0
    )
    fx = tuple(
        SignalFX(
            START + timedelta(days=day), START + timedelta(days=day), Decimal(1300), 1
        )
        for day in range(121)
    )
    data = replace(
        fixture(kr, us, rows=rows), decided_at=START + timedelta(days=121), fx=fx
    )
    result = plan_selected_candidate(data, "equal", CONFIG_BYTES)
    assert result.status == "ready"
    assert result.volatility_proxy is not None
    future_fx = SignalFX(
        data.decided_at + timedelta(days=1),
        data.decided_at + timedelta(days=1),
        Decimal(1),
        1,
    )
    assert (
        plan_selected_candidate(
            replace(data, fx=fx + (future_fx,)), "equal", CONFIG_BYTES
        )
        == result
    )
    stale = plan_selected_candidate(replace(data, fx=fx[:1]), "equal", CONFIG_BYTES)
    assert stale.status == "incomplete" and stale.reason == "missing_or_stale_fx"
    assert stale.targets is None
    assert (
        plan_selected_candidate(
            replace(data, cohort=(kr,), closes=closes(kr), fx=()), "equal", CONFIG_BYTES
        ).status
        == "ready"
    )


def test_identity_order_duplicate_and_same_symbol_other_market() -> None:
    kr = asset("SAME")
    us = asset("SAME", market="US")
    rows = closes(kr) + closes(us)
    fx = tuple(
        SignalFX(
            START + timedelta(days=day), START + timedelta(days=day), Decimal(1300), 1
        )
        for day in range(61)
    )
    data = replace(fixture(us, kr, rows=rows), fx=fx)
    first = plan_selected_candidate(data, "equal", CONFIG_BYTES)
    second = plan_selected_candidate(
        replace(
            data,
            registered=(kr, us),
            cohort=(kr, us),
            closes=tuple(reversed(rows)),
            fx=tuple(reversed(fx)),
        ),
        "equal",
        CONFIG_BYTES,
    )
    assert first == second
    assert tuple(target.instrument for target in first.targets or ()) == (kr, us)
    with pytest.raises(SignalInputError, match="duplicate or conflicting"):
        plan_selected_candidate(
            replace(data, registered=(kr, kr)), "equal", CONFIG_BYTES
        )
    with pytest.raises(SignalInputError, match="cohort identity"):
        plan_selected_candidate(
            replace(data, cohort=(replace(kr, identity_hash=HASH),)),
            "equal",
            CONFIG_BYTES,
        )


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"basis": "raw"}, "basis"),
        ({"adjusted_close": Decimal("NaN")}, "positive finite"),
        ({"adjusted_close": Decimal("-1")}, "positive finite"),
        ({"revision": 0}, "positive integer"),
    ],
)
def test_invalid_close_fails_closed(change: dict[str, object], message: str) -> None:
    item = asset("A")
    data = fixture(item)
    with pytest.raises(SignalInputError, match=message):
        plan_selected_candidate(
            replace(
                data,
                closes=(replace(data.closes[0], **cast(Any, change)),)
                + data.closes[1:],
            ),
            "equal",
            CONFIG_BYTES,
        )


def test_duplicate_revision_and_hash_or_config_mismatch_fail_closed() -> None:
    item = asset("A")
    data = fixture(item)
    with pytest.raises(SignalInputError, match="duplicate close revision"):
        plan_selected_candidate(
            replace(data, closes=data.closes + (data.closes[0],)), "equal", CONFIG_BYTES
        )
    conflicting_time = replace(
        data.closes[0],
        official_close_at=data.closes[0].official_close_at + timedelta(hours=1),
        available_at=data.closes[0].available_at + timedelta(hours=1),
    )
    with pytest.raises(SignalInputError, match="conflicting official closes"):
        plan_selected_candidate(
            replace(data, closes=data.closes + (conflicting_time,)),
            "equal",
            CONFIG_BYTES,
        )
    with pytest.raises(SignalInputError, match="config SHA-256 mismatch"):
        plan_selected_candidate(
            replace(data, config_sha256="b" * 64), "equal", CONFIG_BYTES
        )
    changed_config = json.loads(CONFIG_BYTES)
    changed_config["caps"]["gross"] = "0.61"
    changed_bytes = json.dumps(changed_config).encode()
    with pytest.raises(SignalInputError, match="frozen numeric policy"):
        plan_selected_candidate(
            replace(data, config_sha256=hashlib.sha256(changed_bytes).hexdigest()),
            "equal",
            changed_bytes,
        )
    with pytest.raises(SignalInputError, match="SHA-256"):
        plan_selected_candidate(
            replace(data, calendar_hash="unknown"), "equal", CONFIG_BYTES
        )
    with pytest.raises(SignalInputError, match="registration revision"):
        plan_selected_candidate(
            replace(data, registration_revision=2), "equal", CONFIG_BYTES
        )
    with pytest.raises(SignalInputError, match="unsupported candidate"):
        plan_selected_candidate(data, "momentum_top4", CONFIG_BYTES)  # type: ignore[arg-type]


def test_fx_revision_and_missing_history_fail_closed() -> None:
    us = asset("U", market="US")
    fx = tuple(
        SignalFX(
            START + timedelta(days=day), START + timedelta(days=day), Decimal(1300), 1
        )
        for day in range(61)
    )
    data = replace(fixture(us), fx=fx)
    with pytest.raises(SignalInputError, match="duplicate FX revision"):
        plan_selected_candidate(replace(data, fx=fx + (fx[0],)), "equal", CONFIG_BYTES)
    missing = plan_selected_candidate(replace(data, fx=fx[1:]), "equal", CONFIG_BYTES)
    assert missing.status == "incomplete" and missing.reason == "missing_or_stale_fx"


def test_fx_revision_is_available_only_from_its_publication_cutoff() -> None:
    us = asset("U", market="US")
    fx = tuple(
        SignalFX(
            START + timedelta(days=day), START + timedelta(days=day), Decimal(1300), 1
        )
        for day in range(0, 61, 7)
    )
    data = replace(fixture(us), fx=fx)
    original = plan_selected_candidate(data, "equal", CONFIG_BYTES)
    revised = replace(
        fx[6],
        available_at=fx[6].effective_at + timedelta(days=1),
        krw_per_usd=Decimal(1400),
        revision=2,
    )
    changed = plan_selected_candidate(
        replace(data, fx=fx + (revised,)), "equal", CONFIG_BYTES
    )
    assert (
        changed.status == "ready"
        and changed.volatility_proxy != original.volatility_proxy
    )
    unpublished = replace(revised, available_at=data.decided_at + timedelta(seconds=1))
    assert (
        plan_selected_candidate(
            replace(data, fx=fx + (unpublished,)), "equal", CONFIG_BYTES
        )
        == original
    )
