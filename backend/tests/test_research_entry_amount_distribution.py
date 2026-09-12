from datetime import UTC, date, datetime
from decimal import Decimal, localcontext
from types import SimpleNamespace

import pytest

from jusik import research_entry_amount_distribution as analyze


def trade(day: date, side: str, quantity: int, amount: str) -> SimpleNamespace:
    at = datetime(day.year, day.month, day.day, tzinfo=UTC)
    return SimpleNamespace(
        executed_at=at,
        side=side,
        symbol="X",
        quantity=quantity,
        local_price=str(Decimal(amount) / quantity),
        fx_rate="1",
        notional_krw=amount,
    )


def simulation(trades: list[SimpleNamespace], final_quantity: int) -> SimpleNamespace:
    return SimpleNamespace(
        period_start=date(2024, 1, 1),
        period_end=date(2024, 1, 5),
        trades=trades,
        positions=[SimpleNamespace(symbol="X", quantity=final_quantity)],
    )


def test_nearest_rank_and_empty_semantics() -> None:
    values = [Decimal(1), Decimal(2), Decimal(3), Decimal(4)]
    assert analyze.nearest_rank(values, 25) == Decimal(1)
    assert analyze.nearest_rank(values, 50) == Decimal(2)
    empty = analyze.summarize([])
    assert empty["count"] == 0
    assert empty["sum_krw"] == "0"
    assert empty["min_krw"] is None
    assert empty["p90_krw"] is None


def test_bucket_boundaries_and_sum_reconciliation() -> None:
    values = [
        Decimal("9999.99"),
        Decimal(10000),
        Decimal("99999.99"),
        Decimal(100000),
        Decimal("999999.99"),
        Decimal(1000000),
        Decimal("9999999.99"),
        Decimal(10000000),
    ]
    result = analyze.summarize(values)
    assert result["buckets"] == {
        "<10000": 1,
        "[10000,100000)": 2,
        "[100000,1000000)": 2,
        "[1000000,10000000)": 2,
        ">=10000000": 1,
    }
    assert sum(result["buckets"].values()) == result["count"]
    with localcontext() as context:
        context.prec = 60
        assert sum(Decimal(v) for v in result["bucket_sums_krw"].values()) == Decimal(
            result["sum_krw"]
        )


@pytest.mark.parametrize("values", [[Decimal(0)], [Decimal(-1)], [Decimal("NaN")]])
def test_invalid_amounts_are_refused(values: list[Decimal]) -> None:
    with pytest.raises(ValueError):
        analyze.summarize(values)


def test_split_reentry_and_oversell_replay() -> None:
    actions = {"X": [(date(2024, 1, 2), Decimal(2))]}
    events, meta = analyze.replay(
        simulation(
            [
                trade(date(2024, 1, 1), "buy", 1, "100"),
                trade(date(2024, 1, 3), "sell", 2, "200"),
                trade(date(2024, 1, 4), "buy", 3, "300"),
            ],
            3,
        ),
        actions,
        "synthetic.json",
    )
    assert [event["classification"] for event in events] == ["new_entry", "new_entry"]
    assert meta["final_positions"] == {"X": 3}
    with pytest.raises(ValueError, match="oversell"):
        analyze.replay(
            simulation([trade(date(2024, 1, 1), "sell", 1, "100")], 0),
            {},
            "oversell.json",
        )
