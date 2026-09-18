import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

import jusik.research_portfolio_symbol_cap_episodes as module

FIXED_ARCHIVE = Path(
    "/home/kwl/.local/share/jusik/portfolio-audit/"
    "portfolio-volatility15-cadence-cost-tradeoff-v1-527025c895ad4d54a9559469434162a8/"
    "experiment"
)


def _evaluation() -> dict[str, Any]:
    return {
        "period": "fold_1",
        "arm": "control",
        "cost_multiplier": 1,
        "metrics": {"final_equity_krw": "100000001", "transaction_cost_krw": "2"},
        "global_drawdown_pct": "1",
        "daily_metrics": {"recomputed_cost_krw": "2"},
    }


def _cell(
    tmp_path: Path, rows: list[dict[str, Any]]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    archive = tmp_path / "archive"
    path = archive / "observations"
    path.mkdir(parents=True)
    artifact = "fold_1-control_c1.json"
    (path / artifact).write_text(json.dumps(rows), encoding="utf-8")
    return module._read_cell(archive, artifact, _evaluation())


def test_read_cell_preserves_order_repeats_and_contiguous_episodes(
    tmp_path: Path,
) -> None:
    rows = [
        {
            "at": "2024-01-01T00:00:00+00:00",
            "nav_krw": "100",
            "position_values_krw": {"AAA": "20"},
        },
        {
            "at": "2024-01-01T00:00:00+00:00",
            "nav_krw": "100",
            "position_values_krw": {"AAA": "21"},
        },
        {
            "at": "2024-01-01T00:01:00+00:00",
            "nav_krw": "100",
            "position_values_krw": {"AAA": "19"},
        },
        {
            "at": "2024-01-01T00:02:00+00:00",
            "nav_krw": "100",
            "position_values_krw": {"AAA": "22", "BBB": "21"},
        },
    ]
    cell, records = _cell(tmp_path, rows)
    assert [record["observation_index"] for record in records] == [1, 3, 3]
    assert [record["at"] for record in records] == [
        "2024-01-01T00:00:00+00:00",
        "2024-01-01T00:02:00+00:00",
        "2024-01-01T00:02:00+00:00",
    ]
    assert cell["breach_observation_count"] == 3
    assert cell["episode_count"] == 3
    assert [episode["symbol"] for episode in cell["episodes"]] == [
        "AAA",
        "AAA",
        "BBB",
    ]
    assert cell["episodes"][0]["observation_indices"] == [1]
    assert cell["episodes"][1]["observation_indices"] == [3]


def test_cap_boundary_is_not_a_breach(tmp_path: Path) -> None:
    cell, records = _cell(
        tmp_path,
        [
            {
                "at": "2024-01-01T00:00:00+00:00",
                "nav_krw": "100",
                "position_values_krw": {"AAA": "20", "BBB": "20.0000000001"},
            }
        ],
    )
    assert cell["breach_observation_count"] == 1
    assert [record["symbol"] for record in records] == ["BBB"]
    assert Decimal(records[0]["excess_weight"]) > 0


@pytest.mark.skipif(
    not FIXED_ARCHIVE.is_dir(), reason="fixed offline archive is unavailable"
)
def test_fixed_archive_reconstructs_expected_episode_count() -> None:
    result = module.analyze(FIXED_ARCHIVE, Path(__file__).parents[2])
    assert result["cell_count"] == module.EXPECTED_CELLS
    assert result["breach_observation_count"] == module.EXPECTED_BREACH_OBSERVATIONS
    assert result["episode_count"] == module.EXPECTED_EPISODES == 13


@pytest.mark.parametrize(
    "rows",
    [
        [],
        [{"at": "2024-01-01T00:00:00", "nav_krw": "100", "position_values_krw": {}}],
        [
            {
                "at": "2024-01-01T00:00:00+00:00",
                "nav_krw": "0",
                "position_values_krw": {},
            }
        ],
    ],
)
def test_invalid_observation_rows_fail_closed(
    tmp_path: Path, rows: list[dict[str, Any]]
) -> None:
    with pytest.raises(module.EpisodesError):
        _cell(tmp_path, rows)
