# ruff: noqa: E501
"""Bounded, preregistered volatility-15% cadence/cost trade-off runner.

This runner is deliberately closed: the volatility target and all risk limits
are frozen, and only four versus eight week Monday-anchored cadence is varied.
Historical execution requires the explicit flag and always writes a fresh
audit directory.  The first 16 calls replay the prior volatility-15% results
as controls; only then are the 16 eight-week variants evaluated.
"""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import jusik.research_portfolio_gross_cap_sensitivity as gross
import jusik.research_portfolio_held_band_cost3_stress as cost3
from jusik.research_experiment_guard import verify_hashes
from jusik.research_portfolio_models import (
    PortfolioCandidate,
    PortfolioConfig,
    PortfolioInput,
)

RUN_ID = "portfolio-volatility15-cadence-cost-tradeoff-v1"
ATTEMPT = "527025c895ad4d54a9559469434162a8"
PRIOR_PREREG_SHA256 = "24d2d9ebfc5b1fd0083999d96065d9222a046a7ba3cfe7524b920de0c90ec0d8"
PRIOR_MANIFEST_SHA256 = "332ddf7728a8e92e720a92541fb0b3d778fd9130b61a9abdc5ed612b43ce78a2"
PRIOR_RESULTS_SHA256 = "1487e612d747cb960d20065ac3a6ce780d07136f40d80af67600c14682d1ff91"
VARIANT_SHA256 = gross.VARIANT_SHA256
MANDATE_SHA256 = gross.MANDATE_SHA256
GROSS_HELPER_SHA256 = "f0e699822151b7f54121849ab05c8e37b1c1fff101e1a82ad7ff9bacf3c11cea"
COST3_HELPER_SHA256 = "99786a1dc9da2d4136664f3ce75f9e1a7f3fed1f148f3c1cb4d6515b251675bf8"
PRIOR_VARIANT = {"control": "variant"}
PERIOD_NAMES = gross.PERIOD_NAMES
FULL_COSTS = (1, 3)
ARMS = (("control", 4), ("variant", 8))
EVALUATION_CAP = 32
DEADLINE_SECONDS = 900
INITIAL_CAPITAL = gross.INITIAL_CAPITAL

sha256 = gross.sha256
_strict_json = gross._strict_json
_json = gross._json
_write_exclusive = gross._write_exclusive
_checkpoint = gross._checkpoint
_arm_deadline = gross._arm_deadline
_disarm_deadline = gross._disarm_deadline
_copy_engine = gross._copy_engine
_copy_observer_engine = gross._copy_observer_engine
_load_copy = gross._load_copy
_run_simulation = gross._run_simulation
_verify_observations = gross._verify_observations
_verify_simulation_contract = gross._verify_simulation_contract
_verify_accounting = gross._verify_accounting
_verify_exact_replay = gross._verify_exact_replay
_daily_metrics = gross._daily_metrics
_scaling_summary = gross._scaling_summary
global_drawdown = gross.global_drawdown
cap_observations = gross.cap_observations


def _config(base: PortfolioConfig, cadence: int, cost: int) -> PortfolioConfig:
    if isinstance(cadence, bool) or cadence not in {4, 8}:
        raise ValueError("cadence must be one of the preregistered values 4 or 8")
    if isinstance(cost, bool) or cost not in FULL_COSTS:
        raise ValueError("cost multiplier must be one of the preregistered values 1 or 3")
    values = base.model_dump()
    rate = Decimal("0.001") * cost
    values.update(
        volatility_target=Decimal("0.15"),
        gross_cap=Decimal("0.60"),
        low_turnover_band=Decimal("0.04"),
        low_turnover_weeks=cadence,
        fee_rate=rate,
        slippage_rate=rate,
        fx_spread_rate=rate,
    )
    result = PortfolioConfig.model_validate(values)
    if (
        result.initial_cash_krw != INITIAL_CAPITAL
        or result.volatility_target != Decimal("0.15")
        or result.gross_cap != Decimal("0.60")
        or result.symbol_cap != Decimal("0.20")
        or result.leveraged_etf_cap != Decimal("0.20")
        or result.drawdown_limit != Decimal("0.10")
        or result.low_turnover_band != Decimal("0.04")
        or result.low_turnover_weeks != cadence
    ):
        raise ValueError("frozen configuration changed")
    return result


def _periods(prereg: dict[str, Any]) -> list[dict[str, Any]]:
    periods = prereg.get("periods")
    if not isinstance(periods, list) or [p.get("name") for p in periods] != list(PERIOD_NAMES):
        raise ValueError("periods must be fold_1..fold_7 plus continuous")
    if any(not isinstance(p.get("start"), str) or not isinstance(p.get("end"), str) for p in periods):
        raise ValueError("period dates are required")
    return periods


def _load_contract(prior_audit: Path) -> tuple[dict[str, Any], PortfolioInput, PortfolioConfig]:
    prior_audit = prior_audit.resolve()
    prereg_path = prior_audit / "preregistration.json"
    manifest_path = prior_audit / "hash-manifest.json"
    results_path = prior_audit / "results.json"
    verify_hashes({prereg_path: PRIOR_PREREG_SHA256, manifest_path: PRIOR_MANIFEST_SHA256, results_path: PRIOR_RESULTS_SHA256})
    manifest = _strict_json(manifest_path)
    if not isinstance(manifest, dict):
        raise ValueError("prior hash manifest must be an object")
    for relative, digest in manifest.items():
        path = (prior_audit / relative).resolve()
        if prior_audit not in path.parents or not path.is_file():
            raise ValueError(f"invalid prior manifest path: {relative}")
        verify_hashes({path: digest})
    prereg = _strict_json(prereg_path)
    if not isinstance(prereg, dict):
        raise ValueError("prior preregistration must be an object")
    paths, hashes = prereg.get("source_paths"), prereg.get("source_hashes")
    if not isinstance(paths, dict) or not isinstance(hashes, dict):
        raise ValueError("frozen source_paths/source_hashes are required")
    verify_hashes({Path(paths[name]): digest for name, digest in hashes.items()})
    source_manifest = _strict_json(Path(paths["source-manifest.json"]))
    results = _strict_json(results_path)
    rows = results.get("evaluations") if isinstance(results, dict) else None
    expected = {f"{p}-variant_c{c}.json" for p in PERIOD_NAMES for c in FULL_COSTS}
    prior_rows = {
        row.get("artifact"): row for row in rows or []
        if isinstance(row, dict) and row.get("artifact") in expected
    }
    if set(prior_rows) != expected:
        raise ValueError("prior volatility audit must provide exactly 16 variant controls")
    for name, row in prior_rows.items():
        verify_hashes({prior_audit / "simulations" / cast(str, name): row.get("sha256", "")})
    return (
        prereg,
        PortfolioInput.model_validate(source_manifest["frozen_input"]),
        PortfolioConfig.model_validate(prereg["base_config"]),
    )


def preflight(prior_audit: Path) -> dict[str, Any]:
    prereg, source, base = _load_contract(prior_audit)
    return {
        "run_id": RUN_ID,
        "periods": _periods(prereg),
        "frozen_count": 16,
        "cadences": [4, 8],
        "source": source,
        "base_config": base,
        "historical_calls": 0,
        "execution_required": True,
    }


def _runtime_hashes(prior_audit: Path, prereg: dict[str, Any], engine_source: Path, original: Path, variant: Path, observer: Path, mandate: Path) -> dict[Path, str]:
    checks: dict[Path, str] = {
        prior_audit / "preregistration.json": PRIOR_PREREG_SHA256,
        prior_audit / "hash-manifest.json": PRIOR_MANIFEST_SHA256,
        prior_audit / "results.json": PRIOR_RESULTS_SHA256,
        engine_source: sha256(engine_source),
        original: sha256(original),
        variant: VARIANT_SHA256,
        observer: sha256(observer),
        Path(__file__): sha256(Path(__file__)),
        mandate: MANDATE_SHA256,
        Path(gross.__file__): GROSS_HELPER_SHA256,
        Path(cost3.__file__): COST3_HELPER_SHA256,
    }
    for name, digest in prereg["source_hashes"].items():
        checks[Path(prereg["source_paths"][name])] = digest
    source_root = Path(__file__).parent
    for name, digest in {**prereg.get("core_hashes", {}), **prereg.get("imported_helper_hashes", {})}.items():
        candidate = source_root / name
        if candidate.is_file():
            checks[candidate] = digest
    return checks


def _expected_names() -> set[str]:
    return {f"{period}-{arm}_c{cost}.json" for arm, _cadence in ARMS for period in PERIOD_NAMES for cost in FULL_COSTS}


def run_experiment(prior_audit: Path, engine_source: Path, output_dir: Path, *, allow_historical_execution: bool = False, clock: Callable[[], float] = time.monotonic) -> dict[str, Any]:
    if output_dir.exists() and (not output_dir.is_dir() or any(output_dir.iterdir())):
        raise ValueError("output must be new or empty; retry/resume is refused")
    if not allow_historical_execution:
        preflight(prior_audit)
        raise PermissionError("historical simulation requires explicit allow_historical_execution")
    return _execute(prior_audit, engine_source, output_dir, clock)


def _execute(prior_audit: Path, engine_source: Path, output_dir: Path, clock: Callable[[], float]) -> dict[str, Any]:
    started = clock()
    previous: tuple[Any, tuple[float, float]] | None = None
    ledger: list[dict[str, Any]] = []
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        previous = _arm_deadline(DEADLINE_SECONDS)
        _checkpoint(output_dir / "ledger.json", {"run_id": RUN_ID, "evaluation_cap": EVALUATION_CAP, "ledger": ledger})
        prior_audit = prior_audit.resolve()
        prereg, source, base = _load_contract(prior_audit)
        periods = _periods(prereg)
        original, variant = _copy_engine(engine_source, output_dir)
        if sha256(original) != sha256(engine_source) or sha256(variant) != VARIANT_SHA256 or sha256(variant) == sha256(original):
            raise ValueError("engine copies are not the pinned corrected-entry pair")
        observer = _copy_observer_engine(variant, output_dir)
        engine = _load_copy(observer, "volatility15_cadence_observer_engine")
        mandate = Path(__file__).parents[2] / "docs/research-mandate.json"
        if sha256(mandate) != MANDATE_SHA256:
            raise ValueError("mandate hash is not pinned")
        candidate = PortfolioCandidate(id="portfolio_inverse_volatility_fx_vix_v1", method="inverse_volatility", gate="fx_vix")
        (output_dir / "simulations").mkdir()
        (output_dir / "observations").mkdir()
        _write_exclusive(output_dir / "source-coverage.json", gross._coverage(source))
        _write_exclusive(output_dir / "preregistration.json", {"run_id": RUN_ID, "attempt": ATTEMPT, "registered_at": datetime.now(UTC).isoformat(), "volatility_target": "0.15", "cadences_weeks": [4, 8], "cost_multipliers": [1, 3], "evaluation_count": EVALUATION_CAP, "execution_order": [f"{p['name']}-{a}_c{c}.json" for a, _ in ARMS for p in periods for c in FULL_COSTS], "anchor": "first Monday on or after each evaluation period start; weeks are anchor-relative modulo cadence", "source_paths": prereg["source_paths"], "source_hashes": prereg["source_hashes"], "core_hashes": prereg.get("core_hashes", {}), "imported_helper_hashes": prereg.get("imported_helper_hashes", {}), "retry_count": 0, "gpu": 0, "deadline_seconds": DEADLINE_SECONDS, "base_config": base.model_dump(mode="json")})
        runtime_hashes = _runtime_hashes(prior_audit, prereg, engine_source, original, variant, observer, mandate)
        verify_hashes(runtime_hashes)
        rows: list[dict[str, Any]] = []
        simulations: dict[tuple[str, str, int], Any] = {}
        prior_results = _json(prior_audit / "results.json")
        for arm, cadence in ARMS:
            for period in periods:
                for cost in FULL_COSTS:
                    if len(ledger) >= EVALUATION_CAP or clock() - started >= DEADLINE_SECONDS:
                        raise TimeoutError("evaluation cap or deadline exceeded")
                    verify_hashes(runtime_hashes)
                    name = f"{period['name']}-{arm}_c{cost}.json"
                    ledger.append({"index": len(ledger), "period": period["name"], "arm": arm, "cadence_weeks": cadence, "cost": cost, "status": "reserved"})
                    _checkpoint(output_dir / "ledger.json", {"run_id": RUN_ID, "evaluation_cap": EVALUATION_CAP, "ledger": ledger})
                    config = _config(base, cadence, cost)
                    simulation, observations = _run_simulation(engine, source, candidate, period, config)
                    verify_hashes(runtime_hashes)
                    _verify_simulation_contract(simulation, period, candidate, config)
                    _verify_observations(simulation, observations, config)
                    accounting = _verify_accounting(simulation, cost, config, source)
                    artifact = output_dir / "simulations" / name
                    payload = simulation.model_dump(mode="json")
                    _write_exclusive(artifact, payload)
                    _write_exclusive(output_dir / "observations" / name, [{"at": o.at.isoformat(), "nav_krw": str(o.nav_krw), "cash_krw": str(o.cash_krw), "position_values_krw": {k: str(v) for k, v in o.position_values_krw.items()}} for o in observations])
                    if arm == "control":
                        prior_name = name.replace("-control_", "-variant_")
                        prior = next(row for row in prior_results["evaluations"] if row.get("artifact") == prior_name)
                        _verify_exact_replay(payload, prior_audit / "simulations" / prior_name, prior["sha256"])
                    simulations[(period["name"], arm, cost)] = simulation
                    rows.append({"artifact": name, "period": period["name"], "arm": arm, "cadence_weeks": cadence, "cost_multiplier": cost, "volatility_target": "0.15", "metrics": simulation.metrics.model_dump(mode="json"), "accounting_residual": str(accounting["residual"]), "global_drawdown_pct": str(global_drawdown(observations)), "daily_metrics": _daily_metrics(simulation, observations), "cap_observations": cap_observations(observations, config), "scaling": _scaling_summary(engine), "sha256": sha256(artifact)})
                    ledger[-1].update({"status": "saved", "artifact": name, "sha256": sha256(artifact)})
                    _checkpoint(output_dir / "ledger.json", {"run_id": RUN_ID, "evaluation_cap": EVALUATION_CAP, "ledger": ledger})
        verify_hashes(runtime_hashes)
        pairs: list[dict[str, Any]] = []
        for period in periods:
            for cost in FULL_COSTS:
                control = next(r for r in rows if r["period"] == period["name"] and r["arm"] == "control" and r["cost_multiplier"] == cost)
                variant = next(r for r in rows if r["period"] == period["name"] and r["arm"] == "variant" and r["cost_multiplier"] == cost)
                cm, vm = control["metrics"], variant["metrics"]
                cd, vd = control["daily_metrics"], variant["daily_metrics"]
                cc, vc = control["cap_observations"], variant["cap_observations"]
                pairs.append({"period": period["name"], "cost_multiplier": cost, "delta": {"daily_mean_cash_krw": str(Decimal(vd["daily_mean_cash_krw"]) - Decimal(cd["daily_mean_cash_krw"])), "daily_mean_cash_pct": str(Decimal(vd["daily_mean_cash_pct"]) - Decimal(cd["daily_mean_cash_pct"])), "total_return_pct": str(Decimal(vm["total_return_pct"]) - Decimal(cm["total_return_pct"])), "turnover_pct": str(Decimal(vm["turnover_pct"]) - Decimal(cm["turnover_pct"])), "trade_count": vm["trade_count"] - cm["trade_count"], "transaction_cost_krw": str(Decimal(vm["transaction_cost_krw"]) - Decimal(cm["transaction_cost_krw"])), "fx_cost_krw": str(Decimal(vm["fx_cost_krw"]) - Decimal(cm["fx_cost_krw"])), "total_cost_krw": str(Decimal(vm["transaction_cost_krw"]) + Decimal(vm["fx_cost_krw"]) - Decimal(cm["transaction_cost_krw"]) - Decimal(cm["fx_cost_krw"])), "observer_mdd_pct": str(Decimal(variant["global_drawdown_pct"]) - Decimal(control["global_drawdown_pct"])), "gross_cap_exceed_count": len(vc["excess"]["gross"]) - len(cc["excess"]["gross"]), "symbol_cap_exceed_count": len(vc["excess"]["symbol"]) - len(cc["excess"]["symbol"]), "leveraged_cap_exceed_count": len(vc["excess"]["leveraged"]) - len(cc["excess"]["leveraged"])}})
        result = {"run_id": RUN_ID, "attempt": ATTEMPT, "evaluation_count": len(rows), "evaluation_cap": EVALUATION_CAP, "evaluations": rows, "pairs": pairs, "fold_pairs": [p for p in pairs if p["period"] != "continuous"], "continuous_pairs": [p for p in pairs if p["period"] == "continuous"], "all_complete": len(rows) == EVALUATION_CAP, "automatic_promotion": False, "execution_order": [f"{p['name']}-{a}_c{c}.json" for a, _ in ARMS for p in periods for c in FULL_COSTS], "constraints": {"volatility_target": "0.15", "cadences_weeks": [4, 8], "cost_multipliers": [1, 3], "deadline_seconds": DEADLINE_SECONDS, "gpu": 0, "retries": 0}, "limitations": ["historical PIT and dividend receipt timing are not independently verified", "receipt, early-close, partial, cancel, and reject handling are unsupported", "folds remain separate; continuous is reported separately"]}
        _write_exclusive(output_dir / "results.json", result)
        _write_exclusive(output_dir / "hash-manifest.json", {str(path.relative_to(output_dir)): sha256(path) for path in output_dir.rglob("*") if path.is_file() and path.name != "hash-manifest.json"})
        return result
    except BaseException as error:
        if previous is not None:
            _disarm_deadline(previous)
            previous = None
        if output_dir.is_dir() and not (output_dir / "failure.json").exists():
            completed = {cast(str, item.get("artifact")) for item in ledger if item.get("status") == "saved" and isinstance(item.get("artifact"), str)}
            _write_exclusive(output_dir / "failure.json", {"run_id": RUN_ID, "attempt": ATTEMPT, "error": repr(error), "completed": sorted(completed), "missing": sorted(_expected_names() - completed), "restart_requires": ["explicit new attempt approval", "new empty output directory", "same frozen source/helper/model/preregistration hashes", "control replay and accounting pass"]})
        raise
    finally:
        if previous is not None:
            _disarm_deadline(previous)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prior-audit", type=Path, required=True)
    parser.add_argument("--engine-source", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--allow-historical-execution", action="store_true")
    print(json.dumps(run_experiment(**vars(parser.parse_args(argv))), default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
