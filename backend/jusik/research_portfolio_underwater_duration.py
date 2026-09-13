"""Measure portfolio underwater episodes from frozen equity paths."""
# ruff: noqa: E501

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path
from typing import Any

from jusik.research_portfolio_cost_path_attribution import (
    ARMS,
    PERIODS,
    TOLERANCE,
    load_frozen,
)
from jusik.research_portfolio_models import PortfolioEquityPoint, PortfolioSimulation

INITIAL_CAPITAL = Decimal("100000000")
MDD_TOLERANCE = Decimal("0.000000000000000001")


def _decimal(value: Any) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("equity values must be finite decimals") from exc
    if not result.is_finite():
        raise ValueError("equity values must be finite")
    return result


def _point(value: Any) -> tuple[datetime, Decimal]:
    at_value: Any
    equity_value: Any
    if isinstance(value, PortfolioEquityPoint):
        at_value, equity_value = value.at, value.equity_krw
    elif isinstance(value, Mapping):
        at_value, equity_value = value.get("at"), value.get("equity_krw")
    else:
        raise TypeError("equity points must be PortfolioEquityPoint or mappings")
    at, equity = at_value, equity_value
    if not isinstance(at, datetime) or at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("equity timestamps must be timezone-aware")
    if isinstance(equity, bool):
        raise ValueError("equity values must be finite")
    amount = _decimal(equity)
    if amount < 0:
        raise ValueError("equity values must be non-negative")
    return at.astimezone(UTC), amount


def _validated_points(points: Iterable[Any]) -> list[tuple[datetime, Decimal]]:
    values = [_point(point) for point in points]
    if not values:
        raise ValueError("equity path must contain at least one point")
    for previous, current in zip(values, values[1:]):
        if current[0] <= previous[0]:
            raise ValueError("equity timestamps must be strictly increasing and unique")
    return values


def measure_underwater(
    points: Iterable[Any], initial_capital: Decimal = INITIAL_CAPITAL
) -> dict[str, Any]:
    """Return Decimal drawdowns and the longest peak-to-recovery episode."""
    with localcontext() as context:
        context.prec = 50
        capital = _decimal(initial_capital)
        if capital <= 0:
            raise ValueError("initial capital must be positive")
        values = _validated_points(points)
        peak = capital
        peak_at = values[0][0]
        max_drawdown = Decimal(0)
        episodes: list[dict[str, Any]] = []
        open_start: tuple[datetime, Decimal, datetime] | None = None
        drawdowns: list[dict[str, str]] = []
        for at, equity in values:
            if equity > peak:
                peak, peak_at = equity, at
            drawdown = max(Decimal(0), (peak - equity) / peak)
            max_drawdown = max(max_drawdown, drawdown)
            drawdowns.append({"at": at.isoformat(), "drawdown": format(drawdown, "f")})
            if equity < peak and open_start is None:
                open_start = (at, peak, peak_at)
            elif equity >= peak and open_start is not None:
                start, episode_peak, episode_peak_at = open_start
                episodes.append(
                    {
                        "start": start,
                        "end": at,
                        "duration_seconds": _seconds(at - start),
                        "right_censored": False,
                        "peak_krw": episode_peak,
                        "peak_at": episode_peak_at,
                    }
                )
                open_start = None
        terminal_unrecovered = open_start is not None
        if open_start is not None:
            start, episode_peak, episode_peak_at = open_start
            end = values[-1][0]
            episodes.append(
                {
                    "start": start,
                    "end": end,
                    "duration_seconds": _seconds(end - start),
                    "right_censored": True,
                    "peak_krw": episode_peak,
                    "peak_at": episode_peak_at,
                }
            )
        longest = min(
            episodes,
            key=lambda item: (-Decimal(item["duration_seconds"]), item["start"]),
            default=None,
        )
        result: dict[str, Any] = {
            "mdd": format(max_drawdown, "f"),
            "drawdowns": drawdowns,
            "episode_count": len(episodes),
            "terminal_unrecovered": terminal_unrecovered,
            "longest_episode": None,
        }
        if longest is not None:
            result["longest_episode"] = {
                "start_utc": longest["start"].isoformat(),
                "end_utc": longest["end"].isoformat(),
                "duration_seconds": longest["duration_seconds"],
                "right_censored": longest["right_censored"],
            }
        return result


def _seconds(delta: Any) -> str:
    """Serialize elapsed seconds without losing sub-second precision."""
    return format(
        Decimal(
            delta.days * 86400 * 1_000_000
            + delta.seconds * 1_000_000
            + delta.microseconds
        )
        / Decimal(1_000_000),
        "f",
    )


underwater_duration = measure_underwater


def validate_observation_grid(
    paths: Mapping[tuple[str, str, int], Sequence[Any]],
) -> None:
    """Require identical timestamps for the six paths in each period."""
    for period in PERIODS:
        keys = [(period, arm, cost) for arm in ARMS for cost in (1, 2, 3)]
        if any(key not in paths for key in keys):
            raise ValueError(f"missing observation path for {period}")
        grids = [tuple(at for at, _ in _validated_points(paths[key])) for key in keys]
        if any(grid != grids[0] for grid in grids[1:]):
            raise ValueError(f"observation timestamps differ within {period}")


def _simulation_row(
    period: str, arm: str, cost: int, simulation: PortfolioSimulation
) -> dict[str, Any]:
    metric = simulation.metrics
    points = _validated_points(simulation.equity)
    if (
        points[0][0].date() < simulation.period_start
        or points[-1][0].date() > simulation.period_end
    ):
        raise ValueError(f"equity point outside period: {period}-{arm}_c{cost}")
    if abs(points[-1][1] - metric.final_equity_krw) > TOLERANCE:
        raise ValueError(f"final equity mismatch: {period}-{arm}_c{cost}")
    underwater = measure_underwater(simulation.equity, metric.initial_equity_krw)
    saved_mdd = metric.max_drawdown_pct / Decimal("100")
    if abs(Decimal(underwater["mdd"]) - saved_mdd) > MDD_TOLERANCE:
        raise ValueError(f"saved MDD mismatch: {period}-{arm}_c{cost}")
    for point, drawdown in zip(simulation.equity, underwater["drawdowns"], strict=True):
        if (
            abs(Decimal(drawdown["drawdown"]) - point.drawdown_pct / Decimal("100"))
            > MDD_TOLERANCE
        ):
            raise ValueError(f"saved point drawdown mismatch: {period}-{arm}_c{cost}")
    episode = underwater["longest_episode"]
    return {
        "period": period,
        "arm": arm,
        "cost_multiplier": cost,
        "net_pnl_krw": format(metric.final_equity_krw - metric.initial_equity_krw, "f"),
        "mdd": underwater["mdd"],
        "transaction_cost_krw": format(metric.transaction_cost_krw, "f"),
        "fx_cost_krw": format(metric.fx_cost_krw, "f"),
        "turnover_pct": format(metric.turnover_pct, "f"),
        "longest_episode": episode,
        "terminal_unrecovered": underwater["terminal_unrecovered"],
    }


def analyze(input_dir: Path, output_dir: Path) -> dict[str, Any]:
    """Analyze the pinned 48 paths once; no simulation or external collection."""
    with localcontext() as context:
        context.prec = 50
        simulations = load_frozen(input_dir)
        validate_observation_grid({key: sim.equity for key, sim in simulations.items()})
        paths = [
            _simulation_row(period, arm, cost, simulations[(period, arm, cost)])
            for period in PERIODS
            for arm in ARMS
            for cost in (1, 2, 3)
        ]
        index = {
            (row["period"], row["arm"], row["cost_multiplier"]): row for row in paths
        }
        variants = []
        for period in PERIODS:
            for cost in (1, 2, 3):
                control, variant = (
                    index[(period, "control", cost)],
                    index[(period, "variant", cost)],
                )
                variants.append(
                    {
                        "period": period,
                        "cost_multiplier": cost,
                        "control": {
                            "net_pnl_krw": control["net_pnl_krw"],
                            "mdd": control["mdd"],
                            "transaction_cost_krw": control["transaction_cost_krw"],
                            "fx_cost_krw": control["fx_cost_krw"],
                            "turnover_pct": control["turnover_pct"],
                            "longest_episode": control["longest_episode"],
                            "terminal_unrecovered": control["terminal_unrecovered"],
                        },
                        "variant": {
                            "net_pnl_krw": variant["net_pnl_krw"],
                            "mdd": variant["mdd"],
                            "transaction_cost_krw": variant["transaction_cost_krw"],
                            "fx_cost_krw": variant["fx_cost_krw"],
                            "turnover_pct": variant["turnover_pct"],
                            "longest_episode": variant["longest_episode"],
                            "terminal_unrecovered": variant["terminal_unrecovered"],
                        },
                        "variant_minus_control_net_pnl_krw": format(
                            Decimal(variant["net_pnl_krw"])
                            - Decimal(control["net_pnl_krw"]),
                            "f",
                        ),
                        "variant_minus_control_mdd": format(
                            Decimal(variant["mdd"]) - Decimal(control["mdd"]), "f"
                        ),
                        "variant_minus_control_duration_seconds": format(
                            Decimal(
                                (variant["longest_episode"] or {}).get(
                                    "duration_seconds", "0"
                                )
                            )
                            - Decimal(
                                (control["longest_episode"] or {}).get(
                                    "duration_seconds", "0"
                                )
                            ),
                            "f",
                        ),
                        "variant_minus_control_transaction_cost_krw": format(
                            Decimal(variant["transaction_cost_krw"])
                            - Decimal(control["transaction_cost_krw"]),
                            "f",
                        ),
                        "variant_minus_control_fx_cost_krw": format(
                            Decimal(variant["fx_cost_krw"])
                            - Decimal(control["fx_cost_krw"]),
                            "f",
                        ),
                        "variant_minus_control_turnover_pct": format(
                            Decimal(variant["turnover_pct"])
                            - Decimal(control["turnover_pct"]),
                            "f",
                        ),
                    }
                )
        report: dict[str, Any] = {
            "run_id": "portfolio-held-band-underwater-duration-v1",
            "simulation_count": 48,
            "paths": paths,
            "variant_control": variants,
            "variant_control_groups": {
                "folds": [row for row in variants if _is_fold(row)],
                "continuous": [
                    row for row in variants if row["period"] == "continuous"
                ],
            },
            "groups": {
                "folds": {
                    "period_count": 7,
                    "path_count": 42,
                    "variant_control_count": 21,
                },
                "continuous": {
                    "period_count": 1,
                    "path_count": 6,
                    "variant_control_count": 3,
                },
            },
            "group_summaries": {
                "folds": _summarize_group([row for row in variants if _is_fold(row)]),
                "continuous": _summarize_group(
                    [row for row in variants if row["period"] == "continuous"]
                ),
            },
            "claims": [
                "descriptive MDD and underwater duration only; no policy promotion",
                "initial capital 100000000 KRW; user loss limit 20%; leveraged ETF cap 20%; frozen drawdown limit 10%; PAPER limit 10%",
                "live execution is deferred; no real-time risk control or loss guarantee",
                "no recovery is inferred between observations",
            ],
        }
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (output_dir / "report.md").write_text(
            _render_markdown(report), encoding="utf-8"
        )
        return report


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 보유 밴드 underwater 기간 분석 v1",
        "",
        "고정 48개 경로와 24개 같은 기간·비용 variant-control 비교의 기술 통계입니다.",
        "",
        "| period | arm | cost | net PnL (KRW) | MDD | start UTC | end UTC | seconds | censored | terminal unrecovered | transaction (KRW) | FX (KRW) | turnover % |",
        "|---|---|---:|---:|---:|---|---|---:|---|---|---:|---:|---:|",
    ]
    for row in report["paths"]:
        episode = row["longest_episode"] or {}
        lines.append(
            f"| {row['period']} | {row['arm']} | {row['cost_multiplier']} | {row['net_pnl_krw']} | {row['mdd']} | {episode.get('start_utc', '')} | {episode.get('end_utc', '')} | {episode.get('duration_seconds', '0')} | {episode.get('right_censored', False)} | {row['terminal_unrecovered']} | {row['transaction_cost_krw']} | {row['fx_cost_krw']} | {row['turnover_pct']} |"
        )
    lines.extend(
        [
            "",
            "## variant-control folds 21개",
            "",
            "| period | cost | Δnet PnL | ΔMDD | Δduration seconds | Δtransaction KRW | ΔFX KRW | Δturnover pp |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in report["variant_control_groups"]["folds"]:
        lines.append(
            f"| {row['period']} | {row['cost_multiplier']} | {row['variant_minus_control_net_pnl_krw']} | {row['variant_minus_control_mdd']} | {row['variant_minus_control_duration_seconds']} | {row['variant_minus_control_transaction_cost_krw']} | {row['variant_minus_control_fx_cost_krw']} | {row['variant_minus_control_turnover_pct']} |"
        )
    lines.extend(
        [
            "",
            "## variant-control continuous 3개",
            "",
            "| period | cost | Δnet PnL | ΔMDD | Δduration seconds | Δtransaction KRW | ΔFX KRW | Δturnover pp |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in report["variant_control_groups"]["continuous"]:
        lines.append(
            f"| {row['period']} | {row['cost_multiplier']} | {row['variant_minus_control_net_pnl_krw']} | {row['variant_minus_control_mdd']} | {row['variant_minus_control_duration_seconds']} | {row['variant_minus_control_transaction_cost_krw']} | {row['variant_minus_control_fx_cost_krw']} | {row['variant_minus_control_turnover_pct']} |"
        )
    lines.extend(
        [
            "",
            f"동시 MDD 개선·underwater 기간 증가 사례: folds {report['group_summaries']['folds']['joint_mdd_improved_duration_longer']}/21, continuous {report['group_summaries']['continuous']['joint_mdd_improved_duration_longer']}/3.",
            "MDD 개선과 underwater 기간 증가는 기술 통계로만 보고하며 정책 승격을 하지 않습니다.",
            "",
        ]
    )
    return "\n".join(lines)


def _summarize_group(rows: Sequence[dict[str, Any]]) -> dict[str, int]:
    mdd = sum(Decimal(row["variant_minus_control_mdd"]) < 0 for row in rows)
    duration = sum(
        Decimal(row["variant_minus_control_duration_seconds"]) > 0 for row in rows
    )
    joint = sum(
        Decimal(row["variant_minus_control_mdd"]) < 0
        and Decimal(row["variant_minus_control_duration_seconds"]) > 0
        for row in rows
    )
    return {
        "comparison_count": len(rows),
        "mdd_improved": mdd,
        "duration_longer": duration,
        "joint_mdd_improved_duration_longer": joint,
    }


def _is_fold(row: Mapping[str, Any]) -> bool:
    period = row.get("period")
    return isinstance(period, str) and period.startswith("fold_")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    analyze(args.input_dir, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
