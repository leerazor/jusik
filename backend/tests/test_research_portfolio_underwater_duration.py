from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

import jusik.research_portfolio_underwater_duration as underwater
from jusik.research_portfolio_models import (
    PortfolioCandidate,
    PortfolioEquityPoint,
    PortfolioMetrics,
    PortfolioSimulation,
)
from jusik.research_portfolio_underwater_duration import (
    _simulation_row,
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


def test_irregular_microseconds_and_initial_capital_peak_mdd() -> None:
    start = datetime(2024, 1, 1, tzinfo=UTC)
    result = measure_underwater(
        [
            {"at": start, "equity_krw": "80"},
            {"at": start + timedelta(seconds=1, microseconds=2), "equity_krw": "90"},
        ],
        Decimal("100"),
    )
    assert result["mdd"] == "0.2"
    assert result["drawdowns"][0]["drawdown"] == "0.2"
    assert result["longest_episode"]["duration_seconds"] == "1.000002"


@pytest.mark.parametrize(
    "bad",
    [[], points(["100", "90"])[::-1], points(["100", "NaN"]), points(["100", "-1"])],
)
def test_rejects_invalid_path(bad: list[object]) -> None:
    with pytest.raises((ValueError, TypeError)):
        measure_underwater(bad, Decimal("100"))


@pytest.mark.parametrize(
    "bad",
    [
        [{"at": datetime(2024, 1, 1), "equity_krw": "100"}],
        [
            {"at": datetime(2024, 1, 1, tzinfo=UTC), "equity_krw": "100"},
            {
                "at": datetime(2024, 1, 1, tzinfo=timezone(timedelta(hours=9))),
                "equity_krw": "99",
            },
        ],
        [{"at": datetime(2024, 1, 1, tzinfo=UTC)}],
        [{"at": datetime(2024, 1, 1, tzinfo=UTC), "equity_krw": "Infinity"}],
    ],
)
def test_rejects_naive_duplicate_missing_and_nonfinite(bad: list[object]) -> None:
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


def test_grid_rejects_missing_path() -> None:
    paths = {
        (period, arm, cost): points(["100"])
        for period in [f"fold_{i}" for i in range(1, 8)] + ["continuous"]
        for arm in ("control", "variant")
        for cost in (1, 2, 3)
    }
    del paths[("fold_1", "variant", 3)]
    with pytest.raises(ValueError, match="missing"):
        validate_observation_grid(paths)


def _simulation(*, variant: bool = False, saved_mdd: str = "10") -> PortfolioSimulation:
    values = ["100000000", "90000000", "101000000" if variant else "100000000"]
    at = datetime(2024, 1, 1, tzinfo=UTC)
    equity = [
        PortfolioEquityPoint(
            at=at + timedelta(days=index),
            equity_krw=Decimal(value),
            cash_krw=Decimal(value),
            drawdown_pct=Decimal("10" if index == 1 else "0"),
        )
        for index, value in enumerate(values)
    ]
    return PortfolioSimulation(
        candidate=PortfolioCandidate(id="fixture", method="equal", gate="none"),
        period_start=date(2024, 1, 1),
        period_end=date(2024, 1, 3),
        metrics=PortfolioMetrics(
            initial_equity_krw=Decimal("100000000"),
            final_equity_krw=Decimal(values[-1]),
            total_return_pct=Decimal("1" if variant else "0"),
            max_drawdown_pct=Decimal(saved_mdd),
            trade_count=0,
            transaction_cost_krw=Decimal("2" if variant else "1"),
            fx_cost_krw=Decimal("3" if variant else "1"),
            turnover_pct=Decimal("4" if variant else "2"),
        ),
        complete=True,
        incomplete_reasons=[],
        drawdown_latched=False,
        drawdown_latched_at=None,
        equity=equity,
        trades=[],
        weekly_targets=[],
        positions=[],
        contributions_krw={},
        split_cash_in_lieu_krw={},
        overlap_diagnostics={},
    )


def test_saved_mdd_and_per_point_mismatch_rejected() -> None:
    with pytest.raises(ValueError, match="saved MDD"):
        _simulation_row("fold_1", "control", 1, _simulation(saved_mdd="11"))
    sim = _simulation()
    bad = sim.model_copy(
        update={
            "equity": [
                sim.equity[0],
                sim.equity[1].model_copy(update={"drawdown_pct": Decimal("11")}),
                sim.equity[2],
            ]
        }
    )
    with pytest.raises(ValueError, match="saved point"):
        _simulation_row("fold_1", "control", 1, bad)


def test_synthetic_full48_analyze_has_24_pairs_and_separate_groups(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    periods = [f"fold_{i}" for i in range(1, 8)] + ["continuous"]
    simulations = {
        (period, arm, cost): _simulation(variant=arm == "variant")
        for period in periods
        for arm in ("control", "variant")
        for cost in (1, 2, 3)
    }
    monkeypatch.setattr(underwater, "load_frozen", lambda _path: simulations)
    report = underwater.analyze(tmp_path / "input", tmp_path / "output")
    assert len(report["paths"]) == 48
    assert len(report["variant_control"]) == 24
    assert len(report["variant_control_groups"]["folds"]) == 21
    assert len(report["variant_control_groups"]["continuous"]) == 3
    assert report["group_summaries"]["folds"]["joint_mdd_improved_duration_longer"] == 0
