"""Reproduce the prespecified unheld-entry portfolio experiment.

The experiment is intentionally self contained: it copies and hash-checks the
engine, imports those copies under unique names, and writes new artifacts only
to an explicitly empty output directory.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import os
import sys
from collections import defaultdict
from datetime import UTC, date, datetime
from decimal import ROUND_FLOOR, Decimal, localcontext
from importlib.machinery import ModuleSpec
from pathlib import Path
from statistics import median
from types import ModuleType
from typing import Any, cast

from jusik.research_experiment_guard import (
    verify_control_output,
    verify_hashes,
    verify_unheld_entry_source,
)
from jusik.research_portfolio_models import (
    PortfolioCandidate,
    PortfolioConfig,
    PortfolioInput,
    PortfolioSimulation,
)

RUN_ID = "unheld-entry-band-experiment-v1"
PRESPECIFICATION_SHA256 = (
    "9e5159061a0d53e84bf2ad32ab1fc6b16e00497be557f51417cc9b8d63b56dd3"
)
CORE_NAMES = (
    "research_portfolio_engine.py",
    "research_portfolio_models.py",
    "research_external_features.py",
    "research_risk.py",
)
SIMULATION_NAMES = tuple(
    [f"fold_{fold}-b2_c{cost}.json" for fold in range(1, 8) for cost in (1, 2)]
    + [f"continuous-b2_c{cost}.json" for cost in (1, 2)]
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_exclusive(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(body)
            output.flush()
            os.fsync(output.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def _write_json(path: Path, value: object) -> None:
    _write_exclusive(
        path,
        (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
    )


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _empty_output(path: Path) -> None:
    if path.exists():
        if not path.is_dir() or any(path.iterdir()):
            raise ValueError(
                "output directory must be new or empty; overwrite/resume is refused"
            )
    else:
        path.mkdir(parents=True)


def _load_copy(path: Path, name: str) -> ModuleType:
    module_spec: ModuleSpec | None = importlib.util.spec_from_file_location(name, path)
    if module_spec is None or module_spec.loader is None:
        raise ImportError(f"cannot load engine copy: {path}")
    module = importlib.util.module_from_spec(module_spec)
    sys.modules[name] = module
    module_spec.loader.exec_module(module)
    return module


def _copy_engine(engine_source: Path, output: Path) -> tuple[Path, Path]:
    original = output / "original_engine.py"
    variant = output / "variant_engine.py"
    source = engine_source.read_bytes()
    _write_exclusive(original, source)
    anchor = b"                                and positions[symbol] > 0\n"
    condition = (
        b"                                target_weight > 0\n"
        b"                                and abs(actual - target_weight)"
    )
    if source.count(condition) != 1 or source.count(anchor) != 0:
        raise ValueError(
            "engine source does not have the expected unique band condition"
        )
    variant_body = source.replace(
        condition,
        b"                                target_weight > 0\n"
        + anchor
        + b"                                and abs(actual - target_weight)",
        1,
    )
    _write_exclusive(variant, variant_body)
    return original, variant


def _verify_prior(
    prior: Path, engine_source: Path
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, str],
    dict[str, str],
]:
    names = ("source-manifest.json", "source-result.json", "robustness-control.json")
    manifest, result, control = (_load_json(prior / name) for name in names)
    if sha256(prior / "prespecified.json") != PRESPECIFICATION_SHA256:
        raise ValueError("prior prespecified specification hash is not approved")
    specification = _load_json(prior / "prespecified.json")
    expected_source_hashes = specification.get("source_hashes")
    if not isinstance(expected_source_hashes, dict):
        raise ValueError("prior prespecified source hashes are missing")
    verify_hashes(
        {prior / name: digest for name, digest in expected_source_hashes.items()}
    )
    expected_core = specification.get("core_hashes", {})
    for name in CORE_NAMES:
        if sha256(engine_source.parent / name) != expected_core.get(name):
            raise ValueError(f"core source does not match prior frozen hash: {name}")
    if result.get("run_id") != manifest.get("run_id") or control.get(
        "source_run_id"
    ) != result.get("run_id"):
        raise ValueError("prior run identity mismatch")
    if manifest.get("input_hash") != result.get("input_hash"):
        raise ValueError("prior input hash mismatch")
    if (
        control.get("calculation_complete") is not True
        or control.get("fold_count") != 7
    ):
        raise ValueError("prior control is not a complete seven-fold audit")
    control_hashes: dict[str, str] = {}
    specification_controls = specification.get("control_hashes", {})
    for name in SIMULATION_NAMES:
        path = prior / "simulations" / name
        if not path.is_file():
            raise ValueError(f"required prior control output is missing: {name}")
        expected_name = name.replace("-b2_", "-w4_")
        expected_hash = specification_controls.get(expected_name)
        if not isinstance(expected_hash, str) or sha256(path) != expected_hash:
            raise ValueError(f"prior control output hash mismatch: {name}")
        control_hashes[name] = expected_hash
    return (
        manifest,
        result,
        control,
        {str(k): str(v) for k, v in expected_source_hashes.items()},
        control_hashes,
    )


def _periods(result: dict[str, Any], control: dict[str, Any]) -> list[dict[str, Any]]:
    periods = [
        {
            "name": f"fold_{item['fold']}",
            "start": item["oos_start"],
            "end": item["oos_end"],
            "fold": item["fold"],
        }
        for item in control["folds"]
    ]
    periods.append(
        {
            "name": "continuous",
            "start": result["heldout_start"],
            "end": result["heldout_end"],
            "fold": None,
        }
    )
    if (
        len(periods) != 8
        or periods[-1]["start"] != "2024-04-24"
        or periods[-1]["end"] != "2026-09-08"
    ):
        raise ValueError(
            "evaluation periods differ from approved 7-fold plus continuous plan"
        )
    return periods


def _config(base: PortfolioConfig, cost: int) -> PortfolioConfig:
    return PortfolioConfig.model_validate(
        {
            **base.model_dump(),
            "low_turnover_band": Decimal("0.02"),
            "fee_rate": base.fee_rate * cost,
            "slippage_rate": base.slippage_rate * cost,
            "fx_spread_rate": base.fx_spread_rate * cost,
        }
    )


def _entry_count(simulation: PortfolioSimulation, source: PortfolioInput) -> int:
    """Count buys whose pre-trade quantity was zero, applying splits first."""
    actions: dict[str, list[tuple[date, Decimal]]] = defaultdict(list)
    for snapshot in source.instruments:
        item = snapshot.instruments[0]
        for action in snapshot.corporate_actions:
            if simulation.period_start <= action.date <= simulation.period_end:
                actions[item.symbol].append((action.date, action.factor))
        actions[item.symbol].sort()
    positions: defaultdict[str, int] = defaultdict(int)
    action_indexes: defaultdict[str, int] = defaultdict(int)
    count = 0

    def apply_actions_through(day: date) -> None:
        for symbol, symbol_actions in actions.items():
            index = action_indexes[symbol]
            while index < len(symbol_actions) and symbol_actions[index][0] <= day:
                _action_day, factor = symbol_actions[index]
                positions[symbol] = int(
                    (Decimal(positions[symbol]) * factor).to_integral_value(
                        rounding=ROUND_FLOOR
                    )
                )
                index += 1
            action_indexes[symbol] = index

    ordered_trades = sorted(
        enumerate(simulation.trades),
        key=lambda item: (item[1].executed_at, item[0]),
    )
    for _index, trade in ordered_trades:
        apply_actions_through(trade.executed_at.date())
        if trade.side == "buy":
            if positions[trade.symbol] == 0:
                count += 1
            positions[trade.symbol] += trade.quantity
        else:
            positions[trade.symbol] = max(0, positions[trade.symbol] - trade.quantity)
    apply_actions_through(simulation.period_end)
    expected = {
        position.symbol: position.quantity
        for position in simulation.positions
        if position.quantity > 0
    }
    actual = {
        symbol: quantity for symbol, quantity in positions.items() if quantity > 0
    }
    if actual != expected:
        raise ValueError(
            "unheld-entry replay cannot reconcile final positions: "
            f"tracked={actual}, simulation={expected}"
        )
    return count


def invested_percent_by_utc_day(
    simulation: PortfolioSimulation,
) -> dict[str, Decimal] | None:
    """Return last-existing-point daily exposure, without interpolation."""
    daily: dict[date, Any] = {}
    for point in simulation.equity:
        daily[point.at.astimezone(UTC).date()] = point
    if not daily:
        return None
    result: dict[str, Decimal] = {}
    for day, point in sorted(daily.items()):
        if point.equity_krw <= 0:
            return None
        result[day.isoformat()] = (
            (point.equity_krw - point.cash_krw) / point.equity_krw * 100
        )
    return result


def entry_metrics(
    simulation: PortfolioSimulation, source: PortfolioInput
) -> dict[str, object]:
    exposure = invested_percent_by_utc_day(simulation)
    if exposure is None:
        return {
            "actual_unheld_entry_count": _entry_count(simulation, source),
            "mean_daily_close_invested_percent": None,
            "invested_percent_reason": "no valid UTC-day equity points or zero equity",
        }
    with localcontext() as context:
        context.prec = 40
        mean = sum(exposure.values(), Decimal(0)) / Decimal(len(exposure))
    return {
        "actual_unheld_entry_count": _entry_count(simulation, source),
        "mean_daily_close_invested_percent": str(mean),
        "invested_percent_by_utc_day": {
            key: str(value) for key, value in exposure.items()
        },
    }


def _delta(left: object, right: object) -> Decimal:
    with localcontext() as context:
        context.prec = 40
        return Decimal(str(left)) - Decimal(str(right))


def _pair_state(complete: bool, return_delta: Decimal, mdd_delta: Decimal) -> str:
    if not complete:
        return "incomplete"
    if return_delta == 0 and mdd_delta == 0:
        return "unchanged"
    if return_delta >= 0 and mdd_delta <= 0:
        return "pareto_improved"
    if return_delta <= 0 and mdd_delta >= 0:
        return "dominated"
    return "tradeoff"


def _verify_frozen(
    *,
    engine_source: Path,
    original_path: Path,
    variant_path: Path,
    original_engine: ModuleType,
    variant_engine: ModuleType,
    control_paths: dict[str, Path],
    control_hashes: dict[str, str],
    core_hashes: dict[str, str],
    source_hashes: dict[str, str],
    prior_audit: Path,
    runner_hash: str,
    helper_hash: str,
    original_hash: str,
    variant_hash: str,
) -> None:
    if Path(str(original_engine.__file__)).resolve() != original_path.resolve():
        raise RuntimeError("control engine was not loaded from its frozen copy")
    if Path(str(variant_engine.__file__)).resolve() != variant_path.resolve():
        raise RuntimeError("variant engine was not loaded from its frozen copy")
    checks: dict[Path, str] = {
        engine_source: core_hashes["research_portfolio_engine.py"],
        original_path: original_hash,
        variant_path: variant_hash,
        Path(__file__): runner_hash,
        Path(__file__).with_name("research_experiment_guard.py"): helper_hash,
    }
    checks.update(
        {engine_source.parent / name: digest for name, digest in core_hashes.items()}
    )
    checks.update(
        {prior_audit / name: digest for name, digest in source_hashes.items()}
    )
    checks.update({path: control_hashes[name] for name, path in control_paths.items()})
    verify_hashes(checks)


def run_experiment(
    prior_audit: Path, engine_source: Path, output_dir: Path
) -> dict[str, Any]:
    _empty_output(output_dir)
    manifest, prior_result, control, source_hashes, control_hashes = _verify_prior(
        prior_audit, engine_source
    )
    source = PortfolioInput.model_validate(manifest["frozen_input"])
    base = PortfolioConfig.model_validate(manifest["config"])
    candidate = PortfolioCandidate(
        id="portfolio_inverse_volatility_fx_vix_v1",
        method="inverse_volatility",
        gate="fx_vix",
    )
    periods = _periods(prior_result, control)
    original_path, variant_path = _copy_engine(engine_source, output_dir)
    original_sha, variant_sha = sha256(original_path), sha256(variant_path)
    verify_unheld_entry_source(original_path, variant_path, original_sha, variant_sha)
    original_engine = _load_copy(original_path, "jusik_unheld_entry_original_engine")
    variant_engine = _load_copy(variant_path, "jusik_unheld_entry_variant_engine")
    core_hashes = {name: sha256(engine_source.parent / name) for name in CORE_NAMES}
    control_paths = {
        name: prior_audit / "simulations" / name for name in SIMULATION_NAMES
    }
    runner_hash = sha256(Path(__file__))
    helper_hash = sha256(Path(__file__).with_name("research_experiment_guard.py"))
    specification = {
        "frozen_at": datetime.now(UTC).isoformat(),
        "run_id": RUN_ID,
        "prior_audit": str(prior_audit),
        "prior_source_hashes": source_hashes,
        "engine_source": str(engine_source),
        "engine_original_sha256": original_sha,
        "engine_variant_sha256": variant_sha,
        "runner_sha256": runner_hash,
        "helper_sha256": helper_hash,
        "core_hashes": core_hashes,
        "control_hashes": control_hashes,
        "candidate": candidate.model_dump(mode="json"),
        "policy": "low_turnover_combined",
        "periods": periods,
        "cost_multipliers": [1, 2],
        "control_count": 16,
        "variant_count": 16,
        "evaluation_count": 32,
        "variant_rule": (
            "add positions[symbol] > 0 to the positive-target low-turnover "
            "band skip condition"
        ),
        "criteria": {
            "continuous_return_delta_gt": "0",
            "continuous_mdd_delta_lte": "0",
            "median_fold_return_delta_gt": "0",
            "worst_fold_mdd_variant_lte_control": True,
        },
        "retrospective_reused_history": True,
        "point_in_time_verified": False,
        "prospective_validation_eligible": False,
        "automatic_trading_eligible": False,
        "paper_trading": False,
        "limitations": [
            "후향 재사용 자료이며 신규 미래 검증이 아닙니다.",
            "fold는 독립 현금 시작이며 복리 연결하지 않습니다.",
            "진입·노출 지표는 설명용이며 새 승자 기준이 아닙니다.",
        ],
    }
    _write_json(output_dir / "preregistration.json", specification)
    (output_dir / "simulations").mkdir()
    rows: list[dict[str, object]] = []
    control_verified = 0
    for period in periods:
        for cost in (1, 2):
            config = _config(base, cost)
            control_path = (
                prior_audit / "simulations" / f"{period['name']}-b2_c{cost}.json"
            )
            result = original_engine.simulate(
                source,
                candidate,
                date.fromisoformat(period["start"]),
                date.fromisoformat(period["end"]),
                config,
                "low_turnover_combined",
            )
            payload = result.model_dump(mode="json")
            if not result.complete:
                raise RuntimeError(
                    f"control simulation incomplete: {period['name']} cost {cost}"
                )
            verify_control_output(
                payload, control_path, control_hashes[control_path.name]
            )
            control_verified += 1
            artifact = output_dir / "simulations" / f"{period['name']}-b2_c{cost}.json"
            _write_json(artifact, payload)
            diagnostics = original_engine.policy_diagnostics(result)
            rows.append(
                {
                    "period": period["name"],
                    "start": period["start"],
                    "end": period["end"],
                    "arm": "control",
                    "cost_multiplier": cost,
                    "complete": result.complete,
                    **payload["metrics"],
                    **entry_metrics(result, source),
                    "diagnostics": diagnostics.model_dump(mode="json"),
                    "artifact": artifact.name,
                    "sha256": sha256(artifact),
                }
            )
    _verify_frozen(
        engine_source=engine_source,
        original_path=original_path,
        variant_path=variant_path,
        original_engine=original_engine,
        variant_engine=variant_engine,
        control_paths=control_paths,
        control_hashes=control_hashes,
        core_hashes=core_hashes,
        source_hashes=source_hashes,
        prior_audit=prior_audit,
        runner_hash=runner_hash,
        helper_hash=helper_hash,
        original_hash=original_sha,
        variant_hash=variant_sha,
    )
    if control_verified != 16:
        raise RuntimeError("control count mismatch; variant execution is refused")
    for period in periods:
        for cost in (1, 2):
            config = _config(base, cost)
            result = variant_engine.simulate(
                source,
                candidate,
                date.fromisoformat(period["start"]),
                date.fromisoformat(period["end"]),
                config,
                "low_turnover_combined",
            )
            if not result.complete:
                raise RuntimeError(
                    f"variant simulation incomplete: {period['name']} cost {cost}"
                )
            payload = result.model_dump(mode="json")
            artifact = (
                output_dir / "simulations" / f"{period['name']}-variant_c{cost}.json"
            )
            _write_json(artifact, payload)
            diagnostics = variant_engine.policy_diagnostics(result)
            rows.append(
                {
                    "period": period["name"],
                    "start": period["start"],
                    "end": period["end"],
                    "arm": "variant",
                    "cost_multiplier": cost,
                    "complete": result.complete,
                    **payload["metrics"],
                    **entry_metrics(result, source),
                    "diagnostics": diagnostics.model_dump(mode="json"),
                    "artifact": artifact.name,
                    "sha256": sha256(artifact),
                }
            )
    _verify_frozen(
        engine_source=engine_source,
        original_path=original_path,
        variant_path=variant_path,
        original_engine=original_engine,
        variant_engine=variant_engine,
        control_paths=control_paths,
        control_hashes=control_hashes,
        core_hashes=core_hashes,
        source_hashes=source_hashes,
        prior_audit=prior_audit,
        runner_hash=runner_hash,
        helper_hash=helper_hash,
        original_hash=original_sha,
        variant_hash=variant_sha,
    )
    pairs: list[dict[str, object]] = []
    for period in periods:
        for cost in (1, 2):
            control_row = next(
                row
                for row in rows
                if row["period"] == period["name"]
                and row["arm"] == "control"
                and row["cost_multiplier"] == cost
            )
            variant_row = next(
                row
                for row in rows
                if row["period"] == period["name"]
                and row["arm"] == "variant"
                and row["cost_multiplier"] == cost
            )
            return_delta = _delta(
                variant_row["total_return_pct"], control_row["total_return_pct"]
            )
            mdd_delta = _delta(
                variant_row["max_drawdown_pct"], control_row["max_drawdown_pct"]
            )
            pairs.append(
                {
                    "period": period["name"],
                    "cost_multiplier": cost,
                    "complete": True,
                    "delta": {
                        key: str(_delta(variant_row[key], control_row[key]))
                        for key in (
                            "total_return_pct",
                            "max_drawdown_pct",
                            "turnover_pct",
                            "transaction_cost_krw",
                            "fx_cost_krw",
                            "trade_count",
                        )
                    },
                    "state": _pair_state(True, return_delta, mdd_delta),
                }
            )
    aggregates: list[dict[str, object]] = []
    for cost in (1, 2):
        fold = [
            item
            for item in pairs
            if item["cost_multiplier"] == cost and item["period"] != "continuous"
        ]
        returns = [
            Decimal(str(cast(dict[str, Any], item["delta"])["total_return_pct"]))
            for item in fold
        ]
        continuous = next(
            item
            for item in pairs
            if item["cost_multiplier"] == cost and item["period"] == "continuous"
        )
        control_mdds = [
            Decimal(str(row["max_drawdown_pct"]))
            for row in rows
            if row["arm"] == "control"
            and row["cost_multiplier"] == cost
            and row["period"] != "continuous"
        ]
        variant_mdds = [
            Decimal(str(row["max_drawdown_pct"]))
            for row in rows
            if row["arm"] == "variant"
            and row["cost_multiplier"] == cost
            and row["period"] != "continuous"
        ]
        delta = cast(dict[str, Any], continuous["delta"])
        qualifies = (
            Decimal(str(delta["total_return_pct"])) > 0
            and Decimal(str(delta["max_drawdown_pct"])) <= 0
            and median(returns) > 0
            and max(variant_mdds) <= max(control_mdds)
        )
        aggregates.append(
            {
                "cost_multiplier": cost,
                "median_fold_return_delta_pp": str(median(returns)),
                "worst_fold_mdd_pct": {
                    "control": str(max(control_mdds)),
                    "variant": str(max(variant_mdds)),
                },
                "continuous_delta": delta,
                "qualifies": qualifies,
            }
        )
    results = {
        "completed_at": datetime.now(UTC).isoformat(),
        "specification_sha256": sha256(output_dir / "preregistration.json"),
        "evaluations": rows,
        "pairs": pairs,
        "aggregates": aggregates,
        "all_complete": len(rows) == 32,
        "full_control_comparisons": control_verified,
        "followup_interest": len(rows) == 32
        and all(item["qualifies"] for item in aggregates),
        "automatic_promotion": False,
        "retrospective_reused_history": True,
    }
    _write_json(output_dir / "results.json", results)
    _write_json(output_dir / "comparisons.json", pairs)
    with (output_dir / "comparisons.csv").open(
        "x", newline="", encoding="utf-8"
    ) as handle:
        fields = [
            "period",
            "cost_multiplier",
            "complete",
            "state",
            "total_return_pct_delta",
            "max_drawdown_pct_delta",
            "trade_count_delta",
            "turnover_pct_delta",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for pair in pairs:
            delta = cast(dict[str, Any], pair["delta"])
            writer.writerow(
                {
                    "period": pair["period"],
                    "cost_multiplier": pair["cost_multiplier"],
                    "complete": pair["complete"],
                    "state": pair["state"],
                    "total_return_pct_delta": delta["total_return_pct"],
                    "max_drawdown_pct_delta": delta["max_drawdown_pct"],
                    "trade_count_delta": delta["trade_count"],
                    "turnover_pct_delta": delta["turnover_pct"],
                }
            )
    report = [
        "# 미보유 진입 밴드 실험",
        "",
        (
            "사전 고정한 2%p 밴드 대조군과 미보유 양수 목표의 밴드 억제를 "
            "제외한 변형군을 비교했습니다."
        ),
        "",
        f"- 대조군 비교: {control_verified}/16",
        f"- 전체 실행: {len(rows)}/32",
        f"- 사전 기준 충족: {'예' if results['followup_interest'] else '아니오'}",
        "- 자료 성격: 후향 재사용 자료; 자동 주문·PAPER 반영 없음",
        "",
        "## 판정",
        "",
    ]
    for aggregate in aggregates:
        aggregate_delta = cast(dict[str, Any], aggregate["continuous_delta"])
        report.append(
            f"- 비용 {aggregate['cost_multiplier']}배: "
            f"연속 수익률 차이 {aggregate_delta['total_return_pct']}%p, "
            f"MDD 차이 {aggregate_delta['max_drawdown_pct']}%p, "
            f"판정 {'충족' if aggregate['qualifies'] else '미충족'}"
        )
    _write_exclusive(output_dir / "report.md", ("\n".join(report) + "\n").encode())
    with (output_dir / "results.csv").open("x", newline="", encoding="utf-8") as handle:
        fields = [
            "period",
            "arm",
            "cost_multiplier",
            "complete",
            "total_return_pct",
            "max_drawdown_pct",
            "trade_count",
            "transaction_cost_krw",
            "fx_cost_krw",
            "turnover_pct",
            "actual_unheld_entry_count",
            "mean_daily_close_invested_percent",
            "artifact",
            "sha256",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fields})
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prior-audit", type=Path, required=True)
    parser.add_argument("--engine-source", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    result = run_experiment(args.prior_audit, args.engine_source, args.output_dir)
    print(
        json.dumps(
            {
                "all_complete": result["all_complete"],
                "full_control_comparisons": result["full_control_comparisons"],
                "followup_interest": result["followup_interest"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
