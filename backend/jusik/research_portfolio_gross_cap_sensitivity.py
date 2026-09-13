"""Bounded, preregistered gross-cap sensitivity runner.

This module prepares a two-arm (.60/.80) observer experiment.  Historical
simulation is deliberately disabled unless the caller supplies the explicit
execution flag; the normal preregistration path performs no simulation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import time
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from types import ModuleType
from typing import Any

from jusik.research_portfolio_cost_path_attribution import load_frozen
from jusik.research_portfolio_held_band_cost3_stress import (
    _copy_engine,
    _load_copy,
    _run_call,
    _verify_accounting,
    _verify_exact_replay,
    _verify_runtime_hashes,
)
from jusik.research_portfolio_models import PortfolioCandidate, PortfolioConfig, PortfolioInput, PortfolioSimulation

RUN_ID = "portfolio-gross-cap-cash-sensitivity-v1"
FULL_COSTS = (1, 3)
ARMS = (("control", Decimal("0.60")), ("variant", Decimal("0.80")))
PERIOD_NAMES = tuple([f"fold_{i}" for i in range(1, 8)] + ["continuous"])
EVALUATION_CAP = 32
DEADLINE_SECONDS = 900
INITIAL_CAPITAL = Decimal("100000000")
TOLERANCE_KRW = Decimal("0.000001")
LEVERAGED_SYMBOLS = frozenset({"SOXL", "TQQQ"})
_ACTIVE_DEADLINE: tuple[Any, tuple[float, float]] | None = None


@dataclass(frozen=True)
class EquityObservation:
    at: datetime
    nav_krw: Decimal
    cash_krw: Decimal
    position_values_krw: dict[str, Decimal]

    @property
    def gross_krw(self) -> Decimal:
        return sum(self.position_values_krw.values(), Decimal(0))

    @property
    def leveraged_krw(self) -> Decimal:
        return sum((v for s, v in self.position_values_krw.items() if s in LEVERAGED_SYMBOLS), Decimal(0))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_exclusive(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(value, out, ensure_ascii=False, indent=2, default=str)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def _checkpoint(path: Path, value: object) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _arm_deadline(seconds: int) -> tuple[Any, tuple[float, float]]:
    if not hasattr(signal, "SIGALRM"):
        raise RuntimeError("SIGALRM is required for the exact CPU deadline")
    previous = signal.getsignal(signal.SIGALRM), signal.getitimer(signal.ITIMER_REAL)
    def interrupt(_signum: int, _frame: Any) -> None:
        raise TimeoutError(f"execution deadline exceeded ({seconds}s)")
    signal.signal(signal.SIGALRM, interrupt)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    return previous


def _disarm_deadline(previous: tuple[Any, tuple[float, float]]) -> None:
    signal.setitimer(signal.ITIMER_REAL, 0)
    signal.signal(signal.SIGALRM, previous[0])
    if previous[1] != (0.0, 0.0):
        signal.setitimer(signal.ITIMER_REAL, *previous[1])


def _periods(prereg: dict[str, Any]) -> list[dict[str, Any]]:
    periods = prereg.get("periods")
    if not isinstance(periods, list) or [p.get("name") for p in periods] != list(PERIOD_NAMES):
        raise ValueError("periods must be fold_1..fold_7 plus continuous")
    if any(not isinstance(p.get("start"), str) or not isinstance(p.get("end"), str) for p in periods):
        raise ValueError("period dates are required")
    return periods


def _config(base: PortfolioConfig, gross_cap: Decimal, cost: int) -> PortfolioConfig:
    if gross_cap not in {Decimal("0.60"), Decimal("0.80")} or cost not in {1, 3}:
        raise ValueError("only preregistered gross caps and cost multipliers are allowed")
    values = base.model_dump()
    rate = Decimal("0.001") * cost
    values.update(gross_cap=gross_cap, fee_rate=rate, slippage_rate=rate, fx_spread_rate=rate)
    result = PortfolioConfig.model_validate(values)
    if (result.initial_cash_krw != INITIAL_CAPITAL or result.symbol_cap != Decimal("0.20") or
            result.leveraged_etf_cap != Decimal("0.20") or result.drawdown_limit != Decimal("0.10") or
            result.low_turnover_band != Decimal("0.04") or result.low_turnover_weeks != 4 or
            result.volatility_target != Decimal("0.10")):
        raise ValueError("frozen configuration changed")
    return result


def _copy_observer_engine(variant_path: Path, output: Path) -> Path:
    """Copy the engine and inject a pure valuation observer."""
    body = variant_path.read_bytes()
    marker = b'LEVERAGED_ETFS = frozenset({"SOXL", "TQQQ"})\n'
    start, value, anchor = b"        total = cash\n", b"            total += Decimal(quantity) * price * fx\n", b"        return total\n"
    if any(body.count(x) != 1 for x in (marker, start, value, anchor)):
        raise ValueError("observer anchors are not unique")
    body = body.replace(marker, marker + b"_EQUITY_OBSERVER = None\n_SCALING_OBSERVER = None\n", 1)
    body = body.replace(start, start + b"        position_values = {}\n", 1)
    body = body.replace(value, b"            position_value = Decimal(quantity) * price * fx\n            total += position_value\n            position_values[symbol] = position_value\n", 1)
    target_scale = b"            desired = {\n                symbol: value * target_gross_scale for symbol, value in desired.items()\n            }\n"
    if body.count(target_scale) != 1:
        raise ValueError("target scaling anchor is not unique")
    body = body.replace(target_scale, target_scale + b"            if _SCALING_OBSERVER is not None:\n                _SCALING_OBSERVER(at, \"target_gross\", target_gross_scale)\n", 1)
    gross_scale = b"            gross_scale = min(ONE, gross_room / need_total) if need_total else ZERO\n"
    if body.count(gross_scale) != 1:
        raise ValueError("execution scaling anchor is not unique")
    body = body.replace(gross_scale, gross_scale + b"            if _SCALING_OBSERVER is not None:\n                _SCALING_OBSERVER(at, \"opening_gross\", gross_scale)\n", 1)
    callback = (b"        if _EQUITY_OBSERVER is not None:\n"
                b"            _EQUITY_OBSERVER(at, total, cash, dict(position_values))\n"
                b"        return total\n")
    path = output / "observer_engine.py"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as out:
        out.write(body.replace(anchor, callback, 1))
    return path


def _observe(at: datetime, nav: Decimal, cash: Decimal, values: dict[str, Decimal], out: list[EquityObservation]) -> None:
    out.append(EquityObservation(at, nav, cash, dict(sorted(values.items()))))


def _run_simulation(engine: ModuleType, source: PortfolioInput, candidate: PortfolioCandidate,
                    period: dict[str, Any], config: PortfolioConfig) -> tuple[PortfolioSimulation, list[EquityObservation]]:
    observations: list[EquityObservation] = []
    if not hasattr(engine, "_EQUITY_OBSERVER"):
        raise RuntimeError("observer engine is not instrumented")
    scaling: list[tuple[datetime, str, Decimal]] = []
    setattr(engine, "_EQUITY_OBSERVER", lambda at, nav, cash, values: _observe(at, nav, cash, values, observations))
    setattr(engine, "_SCALING_OBSERVER", lambda at, kind, scale: scaling.append((at, kind, scale)))
    try:
        simulation = _run_call(engine.simulate, source, candidate, period, config)
    finally:
        setattr(engine, "_EQUITY_OBSERVER", None)
        setattr(engine, "_SCALING_OBSERVER", None)
    setattr(engine, "_last_scaling_events", scaling)
    return simulation, observations


def _verify_observations(simulation: PortfolioSimulation, observations: Sequence[EquityObservation], config: PortfolioConfig) -> None:
    if not observations:
        raise ValueError("simulation produced no observations")
    previous: datetime | None = None
    for item in observations:
        if item.at.tzinfo is None or item.at.utcoffset() != UTC.utcoffset(item.at) or (previous and item.at < previous):
            raise ValueError("observer timestamps must be chronological aware UTC")
        if not item.nav_krw.is_finite() or not item.cash_krw.is_finite() or item.nav_krw < 0 or item.cash_krw < 0:
            raise ValueError("observer values must be finite and non-negative")
        if any(not v.is_finite() or v < 0 for v in item.position_values_krw.values()):
            raise ValueError("position values must be finite and non-negative")
        if abs(item.nav_krw - item.cash_krw - item.gross_krw) > TOLERANCE_KRW:
            raise ValueError("observer NAV does not reconcile")
        previous = item.at
    if simulation.metrics.initial_equity_krw != config.initial_cash_krw:
        raise ValueError("initial capital mismatch")
    for point in simulation.equity:
        if not any(o.at == point.at and abs(o.nav_krw - point.equity_krw) <= TOLERANCE_KRW and abs(o.cash_krw - point.cash_krw) <= TOLERANCE_KRW for o in observations):
            raise ValueError("observer does not match serialized equity")


def global_drawdown(observations: Sequence[EquityObservation], initial: Decimal = INITIAL_CAPITAL) -> Decimal:
    peak, maximum = initial, Decimal(0)
    for item in observations:
        if not item.nav_krw.is_finite() or item.nav_krw < 0:
            raise ValueError("NAV must be finite and non-negative")
        peak = max(peak, item.nav_krw)
        maximum = max(maximum, (peak - item.nav_krw) / peak * 100 if peak else Decimal(0))
    return maximum


def cap_observations(observations: Sequence[EquityObservation], config: PortfolioConfig) -> dict[str, Any]:
    """Summarize actual cap excess and sizing scaling observations."""
    excess: dict[str, list[dict[str, str]]] = {"gross": [], "symbol": [], "leveraged": []}
    scaling: defaultdict[str, int] = defaultdict(int)
    for item in observations:
        if item.nav_krw <= 0:
            continue
        gross = item.gross_krw / item.nav_krw
        lev = item.leveraged_krw / item.nav_krw
        if gross > config.gross_cap:
            excess["gross"].append({"at": item.at.isoformat(), "excess": str(gross - config.gross_cap)})
        if lev > config.leveraged_etf_cap:
            excess["leveraged"].append({"at": item.at.isoformat(), "excess": str(lev - config.leveraged_etf_cap)})
        for symbol, value in item.position_values_krw.items():
            amount = value / item.nav_krw
            if amount > config.symbol_cap:
                excess["symbol"].append({"at": item.at.isoformat(), "symbol": symbol, "excess": str(amount - config.symbol_cap)})
    return {"excess": excess, "scaling": dict(scaling), "scaling_denominator": "recorded sizing calls; decision frequency is not inferred"}


def _scaling_summary(engine: ModuleType) -> dict[str, Any]:
    events = getattr(engine, "_last_scaling_events", [])
    counts: defaultdict[str, int] = defaultdict(int)
    for _at, kind, scale in events:
        counts[kind] += 1
        counts[f"{kind}_scale_lt_one"] += int(scale < 1)
    return {"counts": dict(counts), "denominator": "opening execution sizing and pre-observer target sizing calls", "events": [{"at": at.isoformat(), "kind": kind, "scale": str(scale)} for at, kind, scale in events]}


def preflight(prior_audit: Path) -> dict[str, Any]:
    prior_audit = prior_audit.resolve()
    prereg_path = prior_audit / "preregistration.json"
    prereg = _json(prereg_path)
    periods = _periods(prereg)
    manifest_path = Path(prereg["input_paths"]["source-manifest.json"])
    manifest = _json(manifest_path)
    source = PortfolioInput.model_validate(manifest["frozen_input"])
    base = PortfolioConfig.model_validate(prereg["base_config"])
    frozen = load_frozen(prior_audit)
    return {"run_id": RUN_ID, "periods": periods, "frozen_count": len(frozen), "source": source,
            "base_config": base, "historical_calls": 0, "execution_required": True}


def run_experiment(prior_audit: Path, engine_source: Path, output_dir: Path, *, allow_historical_execution: bool = False,
                   clock: Callable[[], float] = time.monotonic) -> dict[str, Any]:
    if output_dir.exists() and (not output_dir.is_dir() or any(output_dir.iterdir())):
        raise ValueError("output must be new or empty; retry/resume is refused")
    if not allow_historical_execution:
        preflight(prior_audit)
        raise PermissionError("historical simulation requires explicit allow_historical_execution")
    return _execute(prior_audit, engine_source, output_dir, clock)


def _execute(prior_audit: Path, engine_source: Path, output_dir: Path,
             clock: Callable[[], float]) -> dict[str, Any]:
    global _ACTIVE_DEADLINE
    started = clock()
    previous = _arm_deadline(DEADLINE_SECONDS)
    _ACTIVE_DEADLINE = previous
    output_dir.mkdir(parents=True, exist_ok=True)
    ledger: list[dict[str, Any]] = []
    _checkpoint(output_dir / "ledger.json", {"run_id": RUN_ID, "evaluation_cap": EVALUATION_CAP, "ledger": ledger})
    try:
        prior_audit = prior_audit.resolve()
        prereg = _json(prior_audit / "preregistration.json")
        periods = _periods(prereg)
        source_manifest = Path(prereg["input_paths"]["source-manifest.json"])
        source = PortfolioInput.model_validate(_json(source_manifest)["frozen_input"])
        base = PortfolioConfig.model_validate(prereg["base_config"])
        load_frozen(prior_audit)
        original, variant_path = _copy_engine(engine_source, output_dir)
        _verify_runtime_hashes(engine_source)
        observer_path = _copy_observer_engine(variant_path, output_dir)
        engine = _load_copy(observer_path, "gross_cap_observer_engine")
        candidate = PortfolioCandidate(id="portfolio_inverse_volatility_fx_vix_v1", method="inverse_volatility", gate="fx_vix")
        (output_dir / "simulations").mkdir()
        (output_dir / "observations").mkdir()
        rows: list[dict[str, Any]] = []
        simulations: dict[tuple[str, str, int], PortfolioSimulation] = {}
        for arm, gross in ARMS:
            for period in periods:
                for cost in FULL_COSTS:
                    if len(ledger) >= EVALUATION_CAP or clock() - started >= DEADLINE_SECONDS:
                        raise TimeoutError("evaluation cap or deadline exceeded")
                    name = f"{period['name']}-{arm}_c{cost}.json"
                    ledger.append({"index": len(ledger), "period": period["name"], "arm": arm, "cost": cost, "status": "reserved"})
                    _checkpoint(output_dir / "ledger.json", {"run_id": RUN_ID, "evaluation_cap": EVALUATION_CAP, "ledger": ledger})
                    config = _config(base, gross, cost)
                    simulation, observations = _run_simulation(engine, source, candidate, period, config)
                    if not simulation.complete or simulation.incomplete_reasons:
                        raise RuntimeError(f"incomplete simulation: {name}")
                    _verify_observations(simulation, observations, config)
                    accounting = _verify_accounting(simulation, cost, config, source)
                    artifact = output_dir / "simulations" / name
                    payload = simulation.model_dump(mode="json")
                    _write_exclusive(artifact, payload)
                    _write_exclusive(output_dir / "observations" / name, [{"at": o.at.isoformat(), "nav_krw": str(o.nav_krw), "cash_krw": str(o.cash_krw), "position_values_krw": {k: str(v) for k, v in o.position_values_krw.items()}} for o in observations])
                    if arm == "control":
                        expected = next((x for x in _json(prior_audit / "results.json").get("evaluations", []) if x.get("artifact") == name), None)
                        if expected is None:
                            # Legacy prereg labels variant outputs as controls.
                            expected = next(x for x in _json(prior_audit / "results.json")["evaluations"] if x.get("artifact") == name.replace("-control_", "-variant_"))
                        _verify_exact_replay(payload, prior_audit / "simulations" / name.replace("-control_", "-variant_") if not (prior_audit / "simulations" / name).exists() else prior_audit / "simulations" / name, expected["sha256"])
                    simulations[(period["name"], arm, cost)] = simulation
                    row = {"artifact": name, "period": period["name"], "arm": arm, "cost_multiplier": cost, "gross_cap": str(gross), "metrics": simulation.metrics.model_dump(mode="json"), "accounting_residual": str(accounting["residual"]), "global_drawdown_pct": str(global_drawdown(observations, INITIAL_CAPITAL)), "cap_observations": cap_observations(observations, config), "scaling": _scaling_summary(engine), "sha256": sha256(artifact)}
                    rows.append(row)
                    ledger[-1].update({"status": "saved", "artifact": name, "sha256": sha256(artifact)})
                    _checkpoint(output_dir / "ledger.json", {"run_id": RUN_ID, "evaluation_cap": EVALUATION_CAP, "ledger": ledger})
        result = {"run_id": RUN_ID, "evaluation_count": len(rows), "evaluation_cap": EVALUATION_CAP, "evaluations": rows, "all_complete": len(rows) == EVALUATION_CAP, "automatic_promotion": False, "coverage": "requested 3 years; each instrument's actual frozen coverage is reported in source-coverage.json", "limitations": ["historical PIT and dividend receipt timing are not independently verified", "receipt and early-close handling are unsupported", "scaling denominator is engine sizing-call frequency; decision frequency is not inferred"]}
        _write_exclusive(output_dir / "results.json", result)
        manifest = {str(p.relative_to(output_dir)): sha256(p) for p in output_dir.rglob("*") if p.is_file() and p.name != "hash-manifest.json"}
        _write_exclusive(output_dir / "hash-manifest.json", manifest)
        return result
    except BaseException as error:
        if output_dir.is_dir() and not (output_dir / "failure.json").exists():
            _write_exclusive(output_dir / "failure.json", {"run_id": RUN_ID, "error": repr(error), "ledger": _json(output_dir / "ledger.json") if (output_dir / "ledger.json").exists() else {}})
        raise
    finally:
        _disarm_deadline(previous)
        _ACTIVE_DEADLINE = None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prior-audit", type=Path, required=True)
    parser.add_argument("--engine-source", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--allow-historical-execution", action="store_true")
    args = parser.parse_args(argv)
    result = run_experiment(**vars(args))
    print(json.dumps(result, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
