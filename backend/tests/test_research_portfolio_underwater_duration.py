from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from jusik.research_portfolio_underwater_duration import (
    measure_underwater,
    validate_observation_grid,
)


def points(values: list[str], *, step: int = 1) -> list[dict[str, object]]:
    start = datetime(2024, 1, 1, tzinfo=UTC)
    return [
        {"at": start + timedelta(seconds=index * step), "equity_krw": value}
        for index, value in enumerate(values)
    ]


@pytest.mark.parametrize(
    ("values", "duration", "censored"),
    [
        (["100", "100"], None, False),
        (["100", "90", "100"], "1", False),
        (["100", "90", "90"], "1", True),
        (["100", "90", "110"], "1", False),
        (["100", "90", "110", "100"], "1", True),
    ],
)
def test_episode_fixtures(
    values: list[str], duration: str | None, censored: bool
) -> None:
    result = measure_underwater(points(values), Decimal("100"))
    if duration is not None:
        assert result["longest_episode"]["duration_seconds"] == duration
    else:
        assert result["longest_episode"] is None
    assert result["terminal_unrecovered"] is censored


def test_irregular_interval_and_earliest_tie() -> None:
    result = measure_underwater(
        points(["100", "90", "100", "90", "100"], step=2), Decimal("100")
    )
    assert result["longest_episode"]["start_utc"] == "2024-01-01T00:00:02+00:00"
    assert result["longest_episode"]["duration_seconds"] == "2"


@pytest.mark.parametrize(
    "bad",
    [[], points(["100", "90"])[::-1], points(["100", "NaN"]), points(["100", "-1"])],
)
def test_rejects_invalid_path(bad: list[object]) -> None:
    with pytest.raises((ValueError, TypeError)):
        measure_underwater(bad, Decimal("100"))


def test_grid_requires_identical_timestamps() -> None:
    keys = [
        ("fold_1", arm, cost) for arm in ("control", "variant") for cost in (1, 2, 3)
    ]
    paths = {key: points(["100", "99"]) for key in keys}
    validate_observation_grid(
        {
            **{
                ("fold_1", arm, cost): value
                for (period, arm, cost), value in paths.items()
            },
            **{
                (period, arm, cost): points(["100"])
                for period in [f"fold_{i}" for i in range(2, 8)] + ["continuous"]
                for arm in ("control", "variant")
                for cost in (1, 2, 3)
            },
        }
    )
    changed = dict(paths)
    changed[("fold_1", "variant", 3)] = points(["100", "99"], step=2)
    full = {
        (period, arm, cost): points(["100"])
        for period in [f"fold_{i}" for i in range(2, 8)] + ["continuous"]
        for arm in ("control", "variant")
        for cost in (1, 2, 3)
    }
    full.update(changed)
    with pytest.raises(ValueError, match="timestamps"):
        validate_observation_grid(full)
