"""Audit frozen portfolio exposure and execution-cost trade-offs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from collections.abc import Mapping
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Any

from jusik.research_entry_attribution import (
    ARMS,
    COSTS,
    PERIODS,
    PREREGISTRATION_SHA256,
    RESULTS_SHA256,
    _read_hashed,
)
from jusik.research_entry_attribution import (
    analyze as attribution_analyze,
)
from jusik.research_portfolio_models import PortfolioSimulation
from jusik.research_unheld_entry_experiment import invested_percent_by_utc_day

PRECISION = 50
INITIAL_CAPITAL_KRW = Decimal("100000000")
DIAGNOSTIC_MULTIPLIERS = (1, 2, 3)
TOLERANCE = Decimal("0.000001")


def _decimal(value: Any, label: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except Exception as exc:
        raise ValueError(f"{label} is not a decimal") from exc
    if not result.is_finite():
        raise ValueError(f"{label} is non-finite")
    return result


def _close(actual: Decimal, expected: Decimal, label: str) -> None:
    if abs(actual - expected) > TOLERANCE:
        raise ValueError(f"{label} residual {actual - expected} exceeds tolerance")


def _exclusive(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, dict):
        return {str(k): _json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(v) for v in value]
    return value


def _load_simulations(
    input_dir: Path,
) -> tuple[dict[tuple[str, str, int], PortfolioSimulation], dict[str, str]]:
    _, results = _read_hashed(
        input_dir / "results.json", RESULTS_SHA256, "results.json"
    )
    _, prereg = _read_hashed(
        input_dir / "preregistration.json",
        PREREGISTRATION_SHA256,
        "preregistration.json",
    )
    evaluations = results.get("evaluations")
    if not isinstance(evaluations, list) or len(evaluations) != 32:
        raise ValueError("frozen results must contain exactly 32 evaluations")
    expected: dict[str, str] = {}
    for row in evaluations:
        if not isinstance(row, dict) or not isinstance(row.get("artifact"), str):
            raise ValueError("frozen artifact metadata is invalid")
        digest = row.get("sha256")
        if not isinstance(digest, str) or row["artifact"] in expected:
            raise ValueError("frozen artifact hash is missing or duplicated")
        expected[row["artifact"]] = digest
    simulations: dict[tuple[str, str, int], PortfolioSimulation] = {}
    for name, digest in sorted(expected.items()):
        body, payload = _read_hashed(input_dir / "simulations" / name, digest, name)
        if hashlib.sha256(body).hexdigest() != digest:
            raise ValueError(f"simulation hash mismatch: {name}")
        sim = PortfolioSimulation.model_validate(payload)
        parts = name.removesuffix(".json").split("-")
        if len(parts) != 2 or parts[0] not in PERIODS or "_c" not in parts[1]:
            raise ValueError(f"unexpected simulation artifact: {name}")
        arm_name, cost_text = parts[1].rsplit("_c", 1)
        if arm_name not in ("b2", "variant") or int(cost_text) not in COSTS:
            raise ValueError(f"unexpected simulation artifact: {name}")
        key = (parts[0], "control" if arm_name == "b2" else "variant", int(cost_text))
        simulations[key] = sim
    expected_keys = {(p, a, c) for p in PERIODS for a in ARMS for c in COSTS}
    if set(simulations) != expected_keys:
        raise ValueError("frozen simulation set is not exactly 32 artifacts")
    if prereg.get("evaluation_count") != 32:
        raise ValueError("frozen preregistration evaluation count mismatch")
    return simulations, expected


def _exposure(
    sim: PortfolioSimulation,
) -> tuple[Decimal | None, str | None, dict[str, Decimal]]:
    for point in sim.equity:
        if point.at.tzinfo is None:
            raise ValueError("equity timestamps must be timezone aware")
        if point.cash_krw > point.equity_krw:
            raise ValueError("cash cannot exceed equity")
    points = sorted(enumerate(sim.equity), key=lambda item: (item[1].at, item[0]))
    for trade in sim.trades:
        if trade.decided_at.tzinfo is None or trade.executed_at.tzinfo is None:
            raise ValueError("trade timestamps must be timezone aware")
        if trade.decided_at > trade.executed_at:
            raise ValueError("trade decided_at cannot be after executed_at")
    if not points or any(point.equity_krw <= 0 for _, point in points):
        return None, "no valid UTC-day equity points or zero equity", {}
    sorted_equity = [point for _, point in points]
    sorted_sim = sim.model_copy(update={"equity": sorted_equity})
    daily = invested_percent_by_utc_day(sorted_sim)
    if daily is None:
        return None, "no valid UTC-day equity points or zero equity", {}
    last = _decimal(daily[sorted(daily)[-1]], "last daily exposure")
    if last < 0 or last > 100:
        raise ValueError("invested percent is outside 0..100")
    return (
        last,
        None,
        {day: _decimal(value, "daily exposure") for day, value in daily.items()},
    )


def _artifact_row(
    attribution: Mapping[str, Any], period: str, arm: str, cost: int
) -> dict[str, Any]:
    rows = [
        row
        for row in attribution["symbol_rows"]
        if row["period"] == period and row["cost_multiplier"] == cost
    ]
    prefix = "control_" if arm == "control" else "variant_"
    values = {
        field: Decimal(0)
        for field in ("fee", "slippage", "transaction_cost", "fx_cost", "net_pnl")
    }
    trade_count = 0
    for row in rows:
        values["fee"] += _decimal(row[f"{prefix}fee"], "fee")
        values["slippage"] += _decimal(row[f"{prefix}slippage"], "slippage")
        values["transaction_cost"] += _decimal(
            row[f"{prefix}transaction_cost"], "transaction cost"
        )
        values["fx_cost"] += _decimal(row[f"{prefix}fx_cost"], "FX cost")
        values["net_pnl"] += _decimal(row[f"{prefix}net_pnl"], "net PnL")
        trade_count += int(row[f"{prefix}trade_count"])
    _close(
        values["fee"] + values["slippage"],
        values["transaction_cost"],
        f"{period} {arm} cost reconciliation",
    )
    return values | {"trade_count": trade_count}


def analyze(input_dir: Path) -> dict[str, Any]:
    """Analyze the fixed simulations with deterministic Decimal arithmetic."""
    with localcontext() as context:
        context.prec = PRECISION
        attribution = attribution_analyze(input_dir)
        simulations, simulation_hashes = _load_simulations(input_dir)
        actual: list[dict[str, Any]] = []
        daily: list[dict[str, Any]] = []
        for period in PERIODS:
            for arm in ARMS:
                for cost in COSTS:
                    sim = simulations[(period, arm, cost)]
                    _close(
                        sim.metrics.initial_equity_krw,
                        INITIAL_CAPITAL_KRW,
                        f"{period} {arm} initial capital",
                    )
                    exposure, reason, daily_values = _exposure(sim)
                    costs = _artifact_row(attribution, period, arm, cost)
                    turnover = sum(
                        (
                            abs(_decimal(trade.notional_krw, "notional"))
                            for trade in sim.trades
                        ),
                        Decimal(0),
                    )
                    if costs["trade_count"] != len(sim.trades):
                        raise ValueError(f"{period} {arm} trade count invalid")
                    _close(
                        turnover / INITIAL_CAPITAL_KRW * 100,
                        sim.metrics.turnover_pct,
                        f"{period} {arm} turnover",
                    )
                    _close(
                        costs["transaction_cost"],
                        sum(
                            (trade.transaction_cost_krw for trade in sim.trades),
                            Decimal(0),
                        ),
                        f"{period} {arm} transaction cost",
                    )
                    _close(
                        costs["fx_cost"],
                        sum((trade.fx_cost_krw for trade in sim.trades), Decimal(0)),
                        f"{period} {arm} FX cost",
                    )
                    _close(
                        costs["net_pnl"],
                        sim.metrics.final_equity_krw - sim.metrics.initial_equity_krw,
                        f"{period} {arm} net PnL",
                    )
                    actual.append(
                        {
                            "period": period,
                            "arm": arm,
                            "cost_multiplier": cost,
                            "last_daily_invested_percent": exposure,
                            "daily_invested_percent": daily_values,
                            "invested_percent_reason": reason,
                            "trade_count": costs["trade_count"],
                            "turnover_krw": turnover,
                            "turnover_percent": turnover / INITIAL_CAPITAL_KRW * 100,
                            "fee_krw": costs["fee"],
                            "slippage_krw": costs["slippage"],
                            "transaction_cost_krw": costs["transaction_cost"],
                            "fx_cost_krw": costs["fx_cost"],
                            "net_pnl_krw": costs["net_pnl"],
                        }
                    )
                    daily.extend(
                        {
                            "period": period,
                            "arm": arm,
                            "cost_multiplier": cost,
                            "utc_day": day,
                            "invested_percent": value,
                        }
                        for day, value in sorted(daily_values.items())
                    )
        comparisons: list[dict[str, Any]] = []
        for period in PERIODS:
            for arm in ARMS:
                one = next(
                    row
                    for row in actual
                    if row["period"] == period
                    and row["arm"] == arm
                    and row["cost_multiplier"] == 1
                )
                two = next(
                    row
                    for row in actual
                    if row["period"] == period
                    and row["arm"] == arm
                    and row["cost_multiplier"] == 2
                )
                comparisons.append(
                    {
                        "period": period,
                        "arm": arm,
                        **{
                            f"delta_{key}": two[key] - one[key]
                            for key in (
                                "trade_count",
                                "turnover_krw",
                                "turnover_percent",
                                "fee_krw",
                                "slippage_krw",
                                "transaction_cost_krw",
                                "fx_cost_krw",
                                "net_pnl_krw",
                            )
                        },
                    }
                )
        arithmetic: list[dict[str, Any]] = []
        for row in actual:
            if row["cost_multiplier"] != 1:
                continue
            for multiplier in DIAGNOSTIC_MULTIPLIERS:
                extra = (multiplier - 1) * (
                    row["transaction_cost_krw"] + row["fx_cost_krw"]
                )
                arithmetic.append(
                    {
                        "period": row["period"],
                        "arm": row["arm"],
                        "baseline_cost_multiplier": 1,
                        "diagnostic_multiplier": multiplier,
                        "baseline_net_pnl_krw": row["net_pnl_krw"],
                        "transaction_cost_krw": row["transaction_cost_krw"],
                        "fx_cost_krw": row["fx_cost_krw"],
                        "diagnostic_net_pnl_krw": row["net_pnl_krw"] - extra,
                    }
                )
        return {
            "input": {
                "input_dir": str(input_dir.resolve()),
                "results_sha256": RESULTS_SHA256,
                "preregistration_sha256": PREREGISTRATION_SHA256,
                "source_hashes": attribution["source_hashes"],
                "simulation_hashes": simulation_hashes,
                "analysis_source_hashes": {
                    "research_portfolio_exposure_cost.py": hashlib.sha256(
                        Path(__file__).read_bytes()
                    ).hexdigest(),
                    "research_entry_attribution.py": hashlib.sha256(
                        Path(__file__)
                        .with_name("research_entry_attribution.py")
                        .read_bytes()
                    ).hexdigest(),
                    "research_unheld_entry_experiment.py": hashlib.sha256(
                        Path(__file__)
                        .with_name("research_unheld_entry_experiment.py")
                        .read_bytes()
                    ).hexdigest(),
                },
                "initial_capital_krw": INITIAL_CAPITAL_KRW,
                "diagnostic_multipliers": DIAGNOSTIC_MULTIPLIERS,
            },
            "actual": actual,
            "daily": daily,
            "comparisons": comparisons,
            "arithmetic": arithmetic,
        }


def write_outputs(result: dict[str, Any], output_dir: Path) -> None:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("output directory must be new or empty; overwrite is refused")
    output_dir.mkdir(parents=True, exist_ok=True)
    assumptions = {
        "input": result["input"],
        "initial_capital_krw": INITIAL_CAPITAL_KRW,
        "diagnostic_multipliers": DIAGNOSTIC_MULTIPLIERS,
        "formula": "baseline_net_pnl - (multiplier - 1) * (transaction_cost + fx_cost)",
        "turnover_definition": (
            "sum of absolute execution notional in KRW for buys and sells"
        ),
        "paper_limit_percent": Decimal("10"),
        "selection_or_policy_activation": False,
        "future_validation": False,
        "hypothetical_mdd_or_feasibility_claims": False,
    }
    for name, value in (
        ("diagnostics.json", result),
        ("assumptionsmanifest.json", assumptions),
    ):
        _exclusive(
            output_dir / name,
            (
                json.dumps(_json_value(value), ensure_ascii=False, indent=2) + "\n"
            ).encode(),
        )
    for name, rows in (
        ("actual.csv", result["actual"]),
        ("daily.csv", result["daily"]),
        ("comparisons.csv", result["comparisons"]),
        ("arithmetic.csv", result["arithmetic"]),
    ):
        fields = sorted({key for row in rows for key in row})
        with (output_dir / name).open("x", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                writer.writerow({key: _json_value(row.get(key)) for key in fields})
    report = [
        "# 포트폴리오 노출·비용 절충 진단",
        "",
        (
            f"실제 체결 진단 {len(result['actual'])}행, "
            f"비용 2배 비교 {len(result['comparisons'])}행, "
            f"고정 1배 산술 진단 {len(result['arithmetic'])}행입니다."
        ),
        "",
        (
            "고정된 과거 시뮬레이션을 재사용했습니다. PAPER 10% 제한은 유지했으며 "
            "정책 활성화, 파라미터 탐색과 미래 검증은 수행하지 않았습니다."
        ),
        "",
        (
            "산술 진단은 각 기간·arm의 실제 1배 체결을 기준으로 거래비용과 FX 비용을 "
            "추가 차감한 계산이며, 비용 변경에 따라 현금·체결이 달라질 수 있는 "
            "실제 2배 결과와 동일시하지 않습니다."
        ),
    ]
    report.extend(
        [
            "",
            "## 실제 체결 요약",
            "",
            (
                "| period | arm | cost | last UTC-day exposure % | trades | "
                "turnover KRW | transaction cost KRW | FX cost KRW | net PnL KRW |"
            ),
            "|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in result["actual"]:
        report.append(
            "| {period} | {arm} | {cost_multiplier} | {last_daily_invested_percent} | "
            "{trade_count} | {turnover_krw} | {transaction_cost_krw} | "
            "{fx_cost_krw} | {net_pnl_krw} |".format(**_json_value(row))
        )
    report.extend(
        [
            "",
            "## 고정 체결 산술 진단",
            "",
            (
                "| period | arm | diagnostic multiplier | baseline net PnL KRW | "
                "diagnostic net PnL KRW |"
            ),
            "|---|---|---:|---:|---:|",
        ]
    )
    for row in result["arithmetic"]:
        report.append(
            "| {period} | {arm} | {diagnostic_multiplier} | "
            "{baseline_net_pnl_krw} | {diagnostic_net_pnl_krw} |".format(
                **_json_value(row)
            )
        )
    _exclusive(output_dir / "report.md", ("\n".join(report) + "\n").encode())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    write_outputs(analyze(args.input_dir), args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
