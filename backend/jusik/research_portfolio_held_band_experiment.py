"""Run the bounded corrected-entry held-band comparison.

The runner is deliberately isolated from the product engine.  It copies the
engine, applies the single guarded held-position change, and imports both
copies under private module names.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import os
import sys
from datetime import date
from decimal import Decimal, localcontext
from importlib.machinery import ModuleSpec
from pathlib import Path
from types import ModuleType
from typing import Any

from jusik.research_entry_attribution import FEE_RATE, attribute_simulation
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
from jusik.research_unheld_entry_experiment import entry_metrics

RUN_ID = "portfolio-held-band-interaction-v1"
VARIANT_SHA256 = "7d9ccd0d8fef90b11779d4e8c98041eadf8aeac94eb3d289318145504483b442"
CORE_NAMES = (
    "research_portfolio_engine.py",
    "research_portfolio_models.py",
    "research_external_features.py",
    "research_risk.py",
)
PERIOD_NAMES = tuple([f"fold_{n}" for n in range(1, 8)] + ["continuous"])
SOURCE_HASHES = {
    "source-manifest.json": (
        "1a2934466efa12c09d08e7792b1a5e4b7c0c880d2aaabab9b25919bd0ec5c825"
    ),
    "source-result.json": (
        "db7ff9f5108e9112a495e2c47f8abf21cde8870f375139930e44ec01056ee8ca"
    ),
    "robustness-control.json": (
        "a6881452b4a87512761e6d3ddf467188f1795811c313be6237584ddc054bd3ef"
    ),
}
CORE_HASHES = {
    "research_portfolio_engine.py": (
        "8790405075a22548f7490c8d4cced8845d3067cba647568a2169a908fe339ed2"
    ),
    "research_portfolio_models.py": (
        "e1fda47a0dc4cb37e4186b778d902cd293e6e2ec1fbd1be2b367bb967c865024"
    ),
    "research_external_features.py": (
        "d44346d43ebc00f18381058ad649e944bb022e6a3868d2f38a8c5edbec49e572"
    ),
    "research_risk.py": (
        "8e79dfa98defec7c9f28fcb8d035e5662903f229f3d6b80997b98b3773f88fcc"
    ),
}
CORRECTED_PREREGISTRATION_SHA256 = (
    "9bf1a850a74a2c95a58f8b6097aa98bff6012a45eb2b887c9e653cf3352f74e7"
)
CORRECTED_RESULTS_SHA256 = (
    "5c2de5987dd099de64736e1d5ebe9a14e25a43f089bc4a1dc60d924a645e7cc4"
)
IMPORTED_HASHES = {
    "research_entry_attribution.py": (
        "3013c6ba8ddbd0ec001462272ee9808ee105afcc939fd25360233c69df594f56"
    ),
    "research_unheld_entry_experiment.py": (
        "a31a455ae79dddce3b19248bc85a4068be49d0d7d0f06bea50422818b866f6d8"
    ),
    "research_experiment_guard.py": (
        "5e9a9cb9b25ccbf73bec9b7a6cb10914e8f5ef1ba378a2a687e7a21bc5a2bd0e"
    ),
    "research_external_models.py": (
        "fa83ef9b7c294e5b9a687969ae0cf0c9fe20d9b690cc90ab7ee3175be4918e0a"
    ),
    "research_universe_models.py": (
        "f5627aac31e19e34a91800a90400e4bc8a130ee93b89f5404240b20eb9cf87c4"
    ),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_exclusive(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, default=str)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def _empty_output(path: Path) -> None:
    if path.exists() and (not path.is_dir() or any(path.iterdir())):
        raise ValueError(
            "output directory must be new or empty; overwrite/resume is refused"
        )
    path.mkdir(parents=True, exist_ok=True)


def _checkpoint(path: Path, value: object) -> None:
    """Persist an execution ledger checkpoint before starting a simulation."""
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, default=str)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_copy(path: Path, name: str) -> ModuleType:
    spec: ModuleSpec | None = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load engine copy: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _copy_engine(engine_source: Path, output: Path) -> tuple[Path, Path]:
    original = output / "original_engine.py"
    variant = output / "variant_engine.py"
    body = engine_source.read_bytes()
    anchor = b"                                and positions[symbol] > 0\n"
    condition = (
        b"                                target_weight > 0\n"
        b"                                and abs(actual - target_weight)"
    )
    if body.count(condition) != 1 or body.count(anchor) != 0:
        raise ValueError("engine source does not have one unique band condition")
    _write_bytes_exclusive(original, body)
    variant_body = body.replace(
        condition,
        b"                                target_weight > 0\n"
        + anchor
        + b"                                and abs(actual - target_weight)",
        1,
    )
    _write_bytes_exclusive(variant, variant_body)
    return original, variant


def _write_bytes_exclusive(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def _config(base: PortfolioConfig, band: str, cost: int) -> PortfolioConfig:
    if band not in {"0.02", "0.04"} or isinstance(cost, bool) or cost not in {1, 2}:
        raise ValueError("only bands .02/.04 and cost multipliers 1/2 are allowed")
    values = base.model_dump()
    values.update(
        low_turnover_band=Decimal(band),
        fee_rate=base.fee_rate * cost,
        slippage_rate=base.slippage_rate * cost,
        fx_spread_rate=base.fx_spread_rate * cost,
    )
    config = PortfolioConfig.model_validate(values)
    if config.symbol_cap != Decimal("0.20") or config.drawdown_limit != Decimal("0.10"):
        raise ValueError("frozen cap or drawdown configuration changed")
    return config


def _periods(result: dict[str, Any], control: dict[str, Any]) -> list[dict[str, Any]]:
    folds = control.get("folds")
    if not isinstance(folds, list) or len(folds) != 7:
        raise ValueError("exactly seven frozen folds are required")
    periods = [
        {"name": f"fold_{x['fold']}", "start": x["oos_start"], "end": x["oos_end"]}
        for x in folds
    ]
    periods.append(
        {
            "name": "continuous",
            "start": result["heldout_start"],
            "end": result["heldout_end"],
        }
    )
    if [x["name"] for x in periods] != list(PERIOD_NAMES):
        raise ValueError("period set is not the approved seven folds plus continuous")
    return periods


def _row(
    period: dict[str, str],
    arm: str,
    cost: int,
    sim: PortfolioSimulation,
    engine: ModuleType,
    source: PortfolioInput,
    artifact: Path,
) -> dict[str, object]:
    payload = sim.model_dump(mode="json")
    diagnostics = engine.policy_diagnostics(sim).model_dump(mode="json")
    skips = sum(event.kind == "band_skip" for event in sim.policy_events)
    return {
        "period": period["name"],
        "start": period["start"],
        "end": period["end"],
        "arm": arm,
        "cost_multiplier": cost,
        "complete": sim.complete,
        **payload["metrics"],
        "actual_unheld_entry_count": entry_metrics(sim, source)[
            "actual_unheld_entry_count"
        ],
        "band_skip_count": skips,
        "diagnostics": diagnostics,
        "artifact": artifact.name,
        "sha256": sha256(artifact),
        "accounting": {
            key: str(value)
            for key, value in attribute_simulation(sim, cost).items()
            if key in {"residual", "total_net_pnl"}
        },
    }


def _delta(left: object, right: object) -> Decimal:
    with localcontext() as context:
        context.prec = 40
        return Decimal(str(left)) - Decimal(str(right))


def _verify_accounting(
    sim: PortfolioSimulation,
    cost: int,
    config: PortfolioConfig,
    source: PortfolioInput,
) -> None:
    for value in (
        sim.metrics.initial_equity_krw,
        sim.metrics.final_equity_krw,
        sim.metrics.turnover_pct,
        *(trade.notional_krw for trade in sim.trades),
    ):
        if not value.is_finite():
            raise ValueError("non-finite financial value")
    if sim.metrics.trade_count != len(sim.trades):
        raise ValueError("trade_count does not equal serialized trades")
    notional = sum((trade.notional_krw for trade in sim.trades), Decimal(0))
    expected_turnover = notional / config.initial_cash_krw * 100
    if sim.metrics.turnover_pct != expected_turnover:
        raise ValueError("turnover does not reconcile to trade notionals")
    fee_rate = FEE_RATE * cost
    spread = config.fx_spread_rate
    currencies = {
        item.instruments[0].symbol: item.instruments[0].instrument.currency
        for item in source.instruments
    }
    for trade in sim.trades:
        if currencies[trade.symbol] == "KRW":
            if trade.fx_cost_krw != Decimal("0"):
                raise ValueError("KRW trade has nonzero FX cost")
            continue
        base = trade.notional_krw * (Decimal("1") + fee_rate)
        gross = trade.notional_krw * (Decimal("1") - fee_rate)
        expected = (base if trade.side == "buy" else gross) * spread
        if abs(trade.fx_cost_krw - expected) > Decimal("0.000001"):
            raise ValueError("FX cost does not reconcile independently")


def run_experiment(
    prior_audit: Path, engine_source: Path, output_dir: Path
) -> dict[str, Any]:
    _empty_output(output_dir)
    ledger: list[dict[str, object]] = []
    try:
        source_dir = prior_audit / "simulations"
        frozen_dir = prior_audit.parents[1] / "20260911T060908Z-rebalance-band"
        verify_hashes(
            {frozen_dir / name: digest for name, digest in SOURCE_HASHES.items()}
        )
        if (
            sha256(prior_audit / "preregistration.json")
            != CORRECTED_PREREGISTRATION_SHA256
        ):
            raise ValueError("corrected preregistration hash mismatch")
        if sha256(prior_audit / "results.json") != CORRECTED_RESULTS_SHA256:
            raise ValueError("corrected results hash mismatch")
        manifest = _load_json(frozen_dir / "source-manifest.json")
        source_result = _load_json(frozen_dir / "source-result.json")
        robustness = _load_json(frozen_dir / "robustness-control.json")
        verify_hashes(
            {
                engine_source.parent / name: digest
                for name, digest in CORE_HASHES.items()
            }
        )
        verify_hashes(
            {
                engine_source.parent / name: digest
                for name, digest in IMPORTED_HASHES.items()
            }
        )
        source = PortfolioInput.model_validate(manifest["frozen_input"])
        base = PortfolioConfig.model_validate(manifest["config"])
        control = _load_json(prior_audit / "preregistration.json")
        control_result = _load_json(prior_audit / "results.json")
        expected_controls = {
            (row["period"], row["cost_multiplier"]): row["sha256"]
            for row in control_result["evaluations"]
            if row["arm"] == "variant"
        }
        if len(expected_controls) != 16:
            raise ValueError("corrected results must pin exactly 16 control artifacts")
        verify_hashes(
            {
                source_dir / f"{period}-variant_c{cost}.json": digest
                for (period, cost), digest in expected_controls.items()
            }
        )
        periods = control.get("periods") or _periods(source_result, robustness)
        if len(periods) != 8 or len({item["name"] for item in periods}) != 8:
            raise ValueError("invalid frozen periods")
        candidate = PortfolioCandidate(
            id="portfolio_inverse_volatility_fx_vix_v1",
            method="inverse_volatility",
            gate="fx_vix",
        )
        frozen_configs = {
            f"{band}-c{cost}": _config(base, band, cost).model_dump(mode="json")
            for band in ("0.02", "0.04")
            for cost in (1, 2)
        }
        original_path, variant_path = _copy_engine(engine_source, output_dir)
        original_hash, variant_hash = sha256(original_path), sha256(variant_path)
        if variant_hash != VARIANT_SHA256:
            raise ValueError(f"variant SHA-256 mismatch: {variant_hash}")
        verify_unheld_entry_source(
            original_path, variant_path, original_hash, variant_hash
        )
        # Both arms use the same corrected-entry variant engine.  Only the
        # validated low-turnover band differs between them.
        variant = _load_copy(variant_path, "held_band_variant_engine")
        (output_dir / "simulations").mkdir()
        _write_exclusive(
            output_dir / "preregistration.json",
            {
                "run_id": RUN_ID,
                "variant_engine_sha256": variant_hash,
                "bands": ["0.02", "0.04"],
                "periods": periods,
                "cost_multipliers": [1, 2],
                "source_run_id": source_result.get("run_id"),
                "retrospective_reused_history": True,
                "point_in_time_verified": False,
                "automatic_trading_eligible": False,
                "base_config": base.model_dump(mode="json"),
                "validated_configs": frozen_configs,
                "source_hashes": SOURCE_HASHES,
                "core_hashes": CORE_HASHES,
                "imported_helper_hashes": IMPORTED_HASHES,
                "control_hashes": expected_controls,
            },
        )
        rows: list[dict[str, object]] = []
        pairs: list[dict[str, object]] = []
        for arm, band in (("control", "0.02"), ("variant", "0.04")):
            if arm == "variant" and len(rows) != 16:
                raise RuntimeError("all 16 corrected control simulations are required")
            for period in periods:
                for cost in (1, 2):
                    ledger.append(
                        {
                            "period": period["name"],
                            "arm": arm,
                            "cost": cost,
                            "status": "started",
                        }
                    )
                    _checkpoint(
                        output_dir / "ledger.json", {"run_id": RUN_ID, "ledger": ledger}
                    )
                    sim = variant.simulate(
                        source,
                        candidate,
                        date.fromisoformat(period["start"]),
                        date.fromisoformat(period["end"]),
                        _config(base, band, cost),
                        "low_turnover_combined",
                    )
                    artifact = (
                        output_dir
                        / "simulations"
                        / f"{period['name']}-{arm}_c{cost}.json"
                    )
                    payload = sim.model_dump(mode="json")
                    _write_exclusive(artifact, payload)
                    _verify_accounting(sim, cost, _config(base, band, cost), source)
                    ledger[-1].update(
                        {
                            "status": "saved",
                            "artifact": str(artifact),
                            "sha256": sha256(artifact),
                            "complete": sim.complete,
                        }
                    )
                    _checkpoint(
                        output_dir / "ledger.json", {"run_id": RUN_ID, "ledger": ledger}
                    )
                    if not sim.complete:
                        raise RuntimeError(
                            f"incomplete simulation: {period['name']} {arm} cost {cost}"
                        )
                    if arm == "control":
                        expected = source_dir / f"{period['name']}-variant_c{cost}.json"
                        expected_sha = expected_controls[(period["name"], cost)]
                        verify_control_output(payload, expected, expected_sha)
                    rows.append(_row(period, arm, cost, sim, variant, source, artifact))
            if arm == "control":
                verify_hashes(
                    {
                        engine_source.parent / name: digest
                        for name, digest in CORE_HASHES.items()
                    }
                    | {
                        engine_source.parent / name: digest
                        for name, digest in IMPORTED_HASHES.items()
                    }
                )
        for period in periods:
            for cost in (1, 2):
                c = next(
                    x
                    for x in rows
                    if x["period"] == period["name"]
                    and x["arm"] == "control"
                    and x["cost_multiplier"] == cost
                )
                v = next(
                    x
                    for x in rows
                    if x["period"] == period["name"]
                    and x["arm"] == "variant"
                    and x["cost_multiplier"] == cost
                )
                pairs.append(
                    {
                        "period": period["name"],
                        "cost_multiplier": cost,
                        "deltas": {
                            key: str(_delta(v[key], c[key]))
                            for key in (
                                "total_return_pct",
                                "max_drawdown_pct",
                                "turnover_pct",
                                "transaction_cost_krw",
                                "fx_cost_krw",
                                "trade_count",
                            )
                        },
                    }
                )
        results = {
            "run_id": RUN_ID,
            "evaluations": rows,
            "pairs": pairs,
            "all_complete": len(rows) == 32,
            "full_control_comparisons": 16,
            "automatic_promotion": False,
            "retrospective_reused_history": True,
        }
        _write_exclusive(output_dir / "results.json", results)
        with (output_dir / "results.csv").open(
            "x", newline="", encoding="utf-8"
        ) as handle:
            fields = [
                "period",
                "arm",
                "cost_multiplier",
                "complete",
                "total_return_pct",
                "max_drawdown_pct",
                "trade_count",
                "turnover_pct",
                "transaction_cost_krw",
                "fx_cost_krw",
                "actual_unheld_entry_count",
                "band_skip_count",
                "artifact",
                "sha256",
            ]
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows({key: row.get(key) for key in fields} for row in rows)
        return results
    except BaseException as error:
        _write_exclusive(
            output_dir / "failure.json",
            {"run_id": RUN_ID, "error": repr(error), "ledger": ledger},
        )
        raise
    finally:
        if not (output_dir / "ledger.json").exists():
            _write_exclusive(
                output_dir / "ledger.json", {"run_id": RUN_ID, "ledger": ledger}
            )
        manifest = {
            str(path.relative_to(output_dir)): sha256(path)
            for path in output_dir.rglob("*")
            if path.is_file() and path.name != "hash-manifest.json"
        }
        _write_exclusive(output_dir / "hash-manifest.json", manifest)


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
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
