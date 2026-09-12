from decimal import Decimal

import pytest

from jusik.research_portfolio_concentration import _sign, _transition


@pytest.mark.parametrize(
    ("value", "expected"),
    [(Decimal("0"), "tie"), (Decimal("-1"), "negative"), (Decimal("1"), "positive")],
)
def test_sign_preserves_zero_and_negative(value: Decimal, expected: str) -> None:
    assert _sign(value) == expected


def test_strict_flip_and_ties_are_distinct() -> None:
    assert _transition(Decimal("-1"), Decimal("1")) == "strict_flip"
    assert _transition(Decimal("1"), Decimal("0")) == "to_tie"
    assert _transition(Decimal("0"), Decimal("-1")) == "from_tie"
    assert _transition(Decimal("0"), Decimal("0")) == "unchanged"


def test_transition_does_not_round_values() -> None:
    assert _transition(Decimal("-0.0000001"), Decimal("0.0000001")) == "strict_flip"
