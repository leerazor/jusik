"""Bounded volatility-target sensitivity runner."""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import jusik.research_portfolio_gross_cap_sensitivity as gross
from jusik.research_experiment_guard import verify_hashes
from jusik.research_portfolio_models import (
    PortfolioCandidate,
    PortfolioConfig,
    PortfolioInput,
)

EquityObservation = gross.EquityObservation
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
_verify_runtime_hashes = gross._verify_runtime_hashes
_coverage = gross._coverage
_daily_metrics = gross._daily_metrics
_scaling_summary = gross._scaling_summary
global_drawdown = gross.global_drawdown
cap_observations = gross.cap_observations
VARIANT_SHA256 = gross.VARIANT_SHA256
MANDATE_SHA256 = gross.MANDATE_SHA256

RUN_ID = "portfolio-volatility-target-cash-sensitivity-v1"
ATTEMPT = "51714e900b9b4cd3b94a4cf0f1aae2f4"
PRIOR_PREREG_SHA256 = "ef2f1187d0c0c1a25e10aad1ec8073bbaa4e28259611e99d87f97c961ac2908e"
PRIOR_MANIFEST_SHA256 = (
    "4d28c36d6ea779cd289eaab09372784ba7568d03d28d2694fc8bd5d10df3ba67"
)
GROSS_HELPER_SHA256 = "f0e699822151b7f54121849ab05c8e37b1c1fff101e1a82ad7ff9bacf3c11cea"
COST3_HELPER_SHA256 = "99786a1dc9da2d4136664f3ce75f9e1a7f3fed1f148f3c1cb4d6515b251675bf"
FULL_COSTS = (1, 3)
ARMS = (("control", Decimal("0.10")), ("variant", Decimal("0.15")))
PERIOD_NAMES = gross.PERIOD_NAMES
EVALUATION_CAP = 32
DEADLINE_SECONDS = 900
INITIAL_CAPITAL = gross.INITIAL_CAPITAL
TOLERANCE_KRW = gross.TOLERANCE_KRW


def _config(base: PortfolioConfig, target: Decimal, cost: int) -> PortfolioConfig:
    if target not in {Decimal("0.10"), Decimal("0.15")} or cost not in FULL_COSTS:
        raise ValueError(
            "only preregistered volatility targets and cost multipliers are allowed"
        )
    values = base.model_dump()
    rate = Decimal("0.001") * cost
    values.update(
        gross_cap=Decimal("0.60"),
        volatility_target=target,
        low_turnover_band=Decimal("0.04"),
        fee_rate=rate,
        slippage_rate=rate,
        fx_spread_rate=rate,
    )
    result = PortfolioConfig.model_validate(values)
    fixed = (
        result.initial_cash_krw == INITIAL_CAPITAL
        and result.symbol_cap == Decimal("0.20")
        and result.gross_cap == Decimal("0.60")
        and result.leveraged_etf_cap == Decimal("0.20")
        and result.drawdown_limit == Decimal("0.10")
        and result.low_turnover_band == Decimal("0.04")
        and result.low_turnover_weeks == 4
        and result.volatility_target == target
    )
    if not fixed:
        raise ValueError("frozen configuration changed")
    return result


def _periods(prereg: dict[str, Any]) -> list[dict[str, Any]]:
    periods = prereg.get("periods")
    if not isinstance(periods, list) or [p.get("name") for p in periods] != list(
        PERIOD_NAMES
    ):
        raise ValueError("periods must be fold_1..fold_7 plus continuous")
    if any(
        not isinstance(p.get("start"), str) or not isinstance(p.get("end"), str)
        for p in periods
    ):
        raise ValueError("period dates are required")
    return periods


def _load_contract(
    prior_audit: Path,
) -> tuple[dict[str, Any], PortfolioInput, PortfolioConfig]:
    prior_audit = prior_audit.resolve()
    prereg_path, manifest_path = (
        prior_audit / "preregistration.json",
        prior_audit / "hash-manifest.json",
    )
    verify_hashes(
        {prereg_path: PRIOR_PREREG_SHA256, manifest_path: PRIOR_MANIFEST_SHA256}
    )
    manifest = _strict_json(manifest_path)
    if not isinstance(manifest, dict):
        raise ValueError("prior hash manifest must be an object")
    for relative, digest in manifest.items():
        path = (prior_audit / relative).resolve()
        if prior_audit not in path.parents or not path.is_file():
            raise ValueError(f"prior manifest path is invalid: {relative}")
        verify_hashes({path: digest})
    prereg = _strict_json(prereg_path)
    paths, hashes = prereg.get("source_paths"), prereg.get("source_hashes")
    if not isinstance(paths, dict) or not isinstance(hashes, dict):
        raise ValueError("frozen source_paths/source_hashes are required")
    verify_hashes({Path(paths[name]): digest for name, digest in hashes.items()})
    source_manifest = _strict_json(Path(paths["source-manifest.json"]))
    results = _strict_json(prior_audit / "results.json")
    expected = {f"{p}-control_c{c}.json" for p in PERIOD_NAMES for c in FULL_COSTS}
    rows = results.get("evaluations")
    controls = {
        row.get("artifact"): row
        for row in rows or []
        if isinstance(row, dict) and row.get("artifact") in expected
    }
    if set(controls) != expected:
        raise ValueError(
            "prior gross audit must provide exactly 16 control evaluations"
        )
    for raw_name, row in controls.items():
        name = cast(str, raw_name)
        verify_hashes({prior_audit / "simulations" / name: row.get("sha256", "")})
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
        "source": source,
        "base_config": base,
        "historical_calls": 0,
        "execution_required": True,
    }


def run_experiment(
    prior_audit: Path,
    engine_source: Path,
    output_dir: Path,
    *,
    allow_historical_execution: bool = False,
    clock: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    if output_dir.exists() and (not output_dir.is_dir() or any(output_dir.iterdir())):
        raise ValueError("output must be new or empty; retry/resume is refused")
    if not allow_historical_execution:
        preflight(prior_audit)
        raise PermissionError(
            "historical simulation requires explicit allow_historical_execution"
        )
    return _execute(prior_audit, engine_source, output_dir, clock)


def _execute(
    prior_audit: Path, engine_source: Path, output_dir: Path, clock: Callable[[], float]
) -> dict[str, Any]:
    started, previous = clock(), None
    ledger: list[dict[str, Any]] = []
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        previous = _arm_deadline(DEADLINE_SECONDS)
        _checkpoint(
            output_dir / "ledger.json",
            {"run_id": RUN_ID, "evaluation_cap": EVALUATION_CAP, "ledger": ledger},
        )
        prereg, source, base = _load_contract(prior_audit)
        periods = _periods(prereg)
        original, variant = _copy_engine(engine_source, output_dir)
        if (
            sha256(original) != sha256(engine_source)
            or sha256(variant) == sha256(original)
            or sha256(variant) != VARIANT_SHA256
        ):
            raise ValueError(
                "engine copy hashes are invalid or variant engine is not pinned"
            )
        _verify_runtime_hashes(engine_source)
        observer = _copy_observer_engine(variant, output_dir)
        engine = _load_copy(observer, "volatility_target_observer_engine")
        mandate_path = Path(__file__).parents[2] / "docs/research-mandate.json"
        if sha256(mandate_path) != MANDATE_SHA256:
            raise ValueError("mandate hash is not pinned")
        candidate = PortfolioCandidate(
            id="portfolio_inverse_volatility_fx_vix_v1",
            method="inverse_volatility",
            gate="fx_vix",
        )
        (output_dir / "simulations").mkdir()
        (output_dir / "observations").mkdir()
        _write_exclusive(output_dir / "source-coverage.json", _coverage(source))
        _write_exclusive(
            output_dir / "preregistration.json",
            {
                "run_id": RUN_ID,
                "attempt": ATTEMPT,
                "volatility_targets": ["0.10", "0.15"],
                "cost_multipliers": [1, 3],
                "evaluation_count": EVALUATION_CAP,
                "periods": periods,
                "source_paths": prereg["source_paths"],
                "source_hashes": prereg["source_hashes"],
                "core_hashes": prereg.get("core_hashes", {}),
                "imported_helper_hashes": prereg.get("imported_helper_hashes", {}),
                "base_config": base.model_dump(mode="json"),
                "validated_configs": {
                    f"{target}-c{cost}": _config(base, target, cost).model_dump(
                        mode="json"
                    )
                    for _, target in ARMS
                    for cost in FULL_COSTS
                },
                "deadline_seconds": DEADLINE_SECONDS,
                "execution_order": [
                    f"{p['name']}-{arm}_c{cost}.json"
                    for arm, _ in ARMS
                    for p in periods
                    for cost in FULL_COSTS
                ],
                "metric_definitions": {
                    "mdd": "initial-capital-inclusive observer NAV running peak",
                    "daily": "last UTC valuation per day arithmetic mean",
                    "scaling": "positive-demand target/opening sizing calls",
                },
                "runner_sha256": sha256(Path(__file__)),
                "reused_helper_hashes": {
                    "research_portfolio_gross_cap_sensitivity.py": GROSS_HELPER_SHA256,
                    "research_portfolio_held_band_cost3_stress.py": COST3_HELPER_SHA256,
                },
                "historical_calls": 0,
                "mandate": _strict_json(mandate_path),
                "mandate_sha256": MANDATE_SHA256,
                "prior_control_expected_sha256": {
                    r["artifact"]: r["sha256"]
                    for r in _json(prior_audit / "results.json")["evaluations"]
                    if "-control_" in r.get("artifact", "")
                    and r.get("cost_multiplier") in FULL_COSTS
                },
                "engine_source_sha256": sha256(engine_source),
                "original_engine_sha256": sha256(original),
                "variant_engine_sha256": sha256(variant),
                "observer_engine_sha256": sha256(observer),
            },
        )
        rows, simulations = [], {}
        for arm, target in ARMS:
            for period in periods:
                for cost in FULL_COSTS:
                    if (
                        len(ledger) >= EVALUATION_CAP
                        or clock() - started >= DEADLINE_SECONDS
                    ):
                        raise TimeoutError("evaluation cap or deadline exceeded")
                    name = f"{period['name']}-{arm}_c{cost}.json"
                    ledger.append(
                        {
                            "index": len(ledger),
                            "period": period["name"],
                            "arm": arm,
                            "cost": cost,
                            "status": "reserved",
                        }
                    )
                    _checkpoint(
                        output_dir / "ledger.json",
                        {
                            "run_id": RUN_ID,
                            "evaluation_cap": EVALUATION_CAP,
                            "ledger": ledger,
                        },
                    )
                    config = _config(base, target, cost)
                    sim, observations = _run_simulation(
                        engine, source, candidate, period, config
                    )
                    _verify_simulation_contract(sim, period, candidate, config)
                    _verify_observations(sim, observations, config)
                    accounting = _verify_accounting(sim, cost, config, source)
                    artifact = output_dir / "simulations" / name
                    payload = sim.model_dump(mode="json")
                    _write_exclusive(artifact, payload)
                    _write_exclusive(
                        output_dir / "observations" / name,
                        [
                            {
                                "at": o.at.isoformat(),
                                "nav_krw": str(o.nav_krw),
                                "cash_krw": str(o.cash_krw),
                                "position_values_krw": {
                                    k: str(v) for k, v in o.position_values_krw.items()
                                },
                            }
                            for o in observations
                        ],
                    )
                    if arm == "control":
                        prior = next(
                            r
                            for r in _json(prior_audit / "results.json")["evaluations"]
                            if r.get("artifact") == name
                        )
                        _verify_exact_replay(
                            payload, prior_audit / "simulations" / name, prior["sha256"]
                        )
                    simulations[(period["name"], arm, cost)] = sim
                    rows.append(
                        {
                            "artifact": name,
                            "period": period["name"],
                            "arm": arm,
                            "cost_multiplier": cost,
                            "gross_cap": str(config.gross_cap),
                            "volatility_target": str(target),
                            "metrics": sim.metrics.model_dump(mode="json"),
                            "accounting_residual": str(accounting["residual"]),
                            "global_drawdown_pct": str(global_drawdown(observations)),
                            "daily_metrics": _daily_metrics(sim, observations),
                            "cap_observations": cap_observations(observations, config),
                            "scaling": _scaling_summary(engine),
                            "sha256": sha256(artifact),
                        }
                    )
                    ledger[-1].update(
                        {
                            "status": "saved",
                            "artifact": name,
                            "sha256": sha256(artifact),
                        }
                    )
                    _checkpoint(
                        output_dir / "ledger.json",
                        {
                            "run_id": RUN_ID,
                            "evaluation_cap": EVALUATION_CAP,
                            "ledger": ledger,
                        },
                    )
        pairs = [
            {
                "period": p["name"],
                "cost_multiplier": c,
                "delta": {
                    k: str(
                        getattr(simulations[(p["name"], "variant", c)].metrics, k)
                        - getattr(simulations[(p["name"], "control", c)].metrics, k)
                    )
                    for k in (
                        "total_return_pct",
                        "max_drawdown_pct",
                        "turnover_pct",
                        "transaction_cost_krw",
                        "trade_count",
                    )
                },
            }
            for p in periods
            for c in FULL_COSTS
        ]
        result = {
            "run_id": RUN_ID,
            "evaluation_count": len(rows),
            "evaluation_cap": EVALUATION_CAP,
            "evaluations": rows,
            "pairs": pairs,
            "fold_pairs": [x for x in pairs if x["period"] != "continuous"],
            "continuous_pairs": [x for x in pairs if x["period"] == "continuous"],
            "all_complete": len(rows) == EVALUATION_CAP,
            "automatic_promotion": False,
            "coverage": (
                "requested 3 years; each instrument's actual frozen coverage is "
                "reported in source-coverage.json"
            ),
            "limitations": [
                "historical PIT and dividend receipt timing are not independently "
                "verified",
                "receipt and early-close handling are unsupported",
                "scaling denominator is engine sizing-call frequency; decision "
                "frequency is not inferred",
            ],
        }
        _write_exclusive(output_dir / "results.json", result)
        _write_exclusive(
            output_dir / "hash-manifest.json",
            {
                str(p.relative_to(output_dir)): sha256(p)
                for p in output_dir.rglob("*")
                if p.is_file() and p.name != "hash-manifest.json"
            },
        )
        return result
    except BaseException as error:
        if output_dir.is_dir() and not (output_dir / "failure.json").exists():
            expected = {
                f"{p}-{a}_c{c}.json"
                for a, _ in ARMS
                for p in PERIOD_NAMES
                for c in FULL_COSTS
            }
            completed = {
                cast(str, x.get("artifact"))
                for x in ledger
                if x.get("status") == "saved" and isinstance(x.get("artifact"), str)
            }
            _write_exclusive(
                output_dir / "failure.json",
                {
                    "run_id": RUN_ID,
                    "error": repr(error),
                    "completed": sorted(completed),
                    "missing": sorted(expected - completed),
                    "restart_requires": [
                        "new empty output directory",
                        "same frozen source hashes",
                        "control replay and accounting pass",
                    ],
                },
            )
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
