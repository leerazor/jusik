# ruff: noqa: E501
"""Read-only attribution of residual cash in the frozen portfolio run.

This module deliberately consumes saved simulation/observation JSON only.  It
does not import or execute the strategy engine, so running the diagnostic
cannot create a new historical simulation.
"""

from __future__ import annotations

import argparse
import bisect
import hashlib
import importlib.util
import json
import statistics
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

LEVERAGED_SYMBOLS = frozenset({"SOXL", "TQQQ"})
TOLERANCE = Decimal("0.00000001")


def _observation_payload(observation: Any) -> dict[str, Any]:
    return {
        "at": observation.at.isoformat(),
        "nav_krw": observation.nav_krw,
        "cash_krw": observation.cash_krw,
        "position_values_krw": observation.position_values_krw,
    }


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path) -> Any:
    """Load strict JSON and reject duplicate keys/non-finite constants."""

    def reject(value: str) -> Any:
        raise ValueError(f"non-finite JSON constant in {path}: {value}")

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key in {path}: {key}")
            result[key] = value
        return result

    return json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=reject,
        object_pairs_hook=unique,
    )


def covariance_proxy(
    weights: dict[str, Decimal], returns: dict[str, list[Decimal]]
) -> Decimal:
    """Portfolio sigma from aligned weighted returns (population covariance).

    Missing symbols or unequal rows fail closed.  The caller supplies only
    returns known strictly before the decision timestamp.
    """
    if not weights:
        return Decimal(0)
    symbols = list(weights)
    if any(symbol not in returns or not returns[symbol] for symbol in symbols):
        raise ValueError("missing historical return series")
    length = len(returns[symbols[0]])
    if length == 0 or any(len(returns[symbol]) != length for symbol in symbols):
        raise ValueError("returns are not aligned")
    mean = {
        symbol: sum(returns[symbol], Decimal(0)) / Decimal(length) for symbol in symbols
    }
    variance = Decimal(0)
    for index in range(length):
        portfolio_return = sum(
            (
                weights[symbol] * (returns[symbol][index] - mean[symbol])
                for symbol in symbols
            ),
            Decimal(0),
        )
        variance += portfolio_return * portfolio_return
    value = (variance / Decimal(length)).sqrt()
    if not value.is_finite():
        raise ValueError("non-finite covariance proxy")
    return value


def annualized_covariance_proxy(
    weights: dict[str, Decimal], returns: dict[str, list[Decimal]], sessions: int = 252
) -> Decimal:
    """Annualize daily portfolio sigma with the frozen session count."""
    if sessions <= 0:
        raise ValueError("sessions must be positive")
    return covariance_proxy(weights, returns) * Decimal(sessions).sqrt()


def covariance_floor_volatility_scale(
    engine: Any,
    source: Any,
    data: Any,
    weights: dict[str, Decimal],
    at: datetime,
    config: Any,
) -> tuple[Decimal | None, Decimal | None]:
    """Private H1 scale: max(0.9*S, P) on the original causal KRW matrix."""
    if not weights:
        return Decimal(1), Decimal(0)
    global_days = sorted(
        {
            engine._market_time(
                bar.date, item.instrument.timezone, opening=False
            ).date()
            for item in data.values()
            for bar in item.snapshot.instruments[0].bars
            if engine._market_time(bar.date, item.instrument.timezone, opening=False)
            < at
        }
    )[-(config.volatility_window + 1) :]
    if len(global_days) < config.volatility_window + 1:
        return None, None
    matrix: dict[str, list[Decimal]] = {}
    for symbol, weight in weights.items():
        item = data[symbol]
        closes = item.snapshot.instruments[0].bars
        known = [
            engine._market_time(bar.date, item.instrument.timezone, opening=False)
            for bar in closes
        ]
        if len(known) != len(set(known)) or known != sorted(known):
            raise ValueError(f"duplicate or unsorted close timestamps: {symbol}")
        values: list[Decimal] = []
        for day in global_days:
            cutoff = min(datetime.combine(day, datetime.max.time(), UTC), at)
            index = bisect.bisect_right(known, cutoff) - 1
            if index < 0:
                return None, None
            if (
                cutoff - known[index]
            ).total_seconds() > config.external_max_age_days * 86400:
                return None, None
            value = closes[index].adjusted_close
            if item.instrument.currency == "USD":
                fx = engine._fx_rate(source, cutoff, config)
                if fx is None or not fx.is_finite() or fx <= 0:
                    return None, None
                value *= fx
            if not value.is_finite() or value <= 0:
                return None, None
            values.append(value)
        matrix[symbol] = [
            current / previous - 1
            for previous, current in zip(values[:-1], values[1:], strict=True)
        ]
    annual = Decimal(config.volatility_annualization_sessions).sqrt()
    sigmas = {
        symbol: Decimal(str(statistics.pstdev(series))) * annual
        for symbol, series in matrix.items()
    }
    original_s = sum(
        (weights[symbol] * sigmas[symbol] for symbol in weights), Decimal(0)
    )
    portfolio_returns = [
        sum((weights[symbol] * matrix[symbol][i] for symbol in weights), Decimal(0))
        for i in range(config.volatility_window)
    ]
    p = (
        sum(
            (x - sum(portfolio_returns, Decimal(0)) / Decimal(len(portfolio_returns)))
            ** 2
            for x in portfolio_returns
        )
        / Decimal(len(portfolio_returns))
    ).sqrt() * annual
    proxy = max(Decimal("0.9") * original_s, p)
    if not proxy.is_finite():
        return None, None
    return (
        min(Decimal(1), config.volatility_target / proxy) if proxy else Decimal(1),
        proxy,
    )


def install_covariance_floor_adapter(engine: Any) -> None:
    """Install H1 on a private engine module with its six-argument hook."""
    engine.volatility_scale = lambda source, data, weights, at, config, fx_cache=None: (
        covariance_floor_volatility_scale(engine, source, data, weights, at, config)
    )


def _decimal(value: Any, label: str) -> Decimal:
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError(f"{label} is non-finite")
    return result


def _group_targets(simulation: dict[str, Any]) -> dict[str, dict[str, Decimal]]:
    grouped: dict[str, dict[str, Decimal]] = defaultdict(dict)
    for row in simulation.get("weekly_targets", []):
        at = str(row["decided_at"])
        symbol = str(row["symbol"])
        weight = _decimal(row["target_weight"], "target weight")
        if weight < 0:
            raise ValueError("negative target weight")
        grouped[at][symbol] = weight
    return dict(grouped)


def diagnose_simulation(
    simulation: dict[str, Any],
    *,
    gross_cap: Decimal = Decimal("0.95"),
    volatility_target: Decimal = Decimal("0.30"),
) -> dict[str, Any]:
    """Return causal mechanism observations; stages are explicitly non-additive."""
    events = simulation.get("policy_events", [])
    if not isinstance(events, list):
        raise ValueError("policy_events must be a list")
    targets = _group_targets(simulation)
    scales: dict[str, Decimal] = {}
    for event in events:
        if event.get("kind") == "volatility_scale":
            proxy = _decimal(event["value"], "volatility proxy")
            scales[str(event["at"])] = (
                min(Decimal(1), volatility_target / proxy) if proxy else Decimal(1)
            )
    rows: list[dict[str, Any]] = []
    for at in sorted(set(targets) | set(scales)):
        post = sum(targets.get(at, {}).values(), Decimal(0))
        scale = scales.get(at, Decimal(1))
        # This is a recorded-artifact inference only.  When a held-band or
        # cap changed individual targets, post/scale cannot recover pre-vol.
        pre = min(gross_cap, post / scale) if scale else Decimal(0)
        rows.append(
            {
                "decided_at": at,
                "pre_vol_gross": pre,
                "post_vol_gross": post,
                "volatility_scale": scale,
                "unallocated_target": max(Decimal(0), gross_cap - post),
                "recorded_target_gross": post,
                "eligible_count": sum(
                    value > 0 for value in targets.get(at, {}).values()
                ),
                "excluded_reasons": {},
                "pre_vol_source": "inferred_from_saved_target",
            }
        )
    counts = Counter(str(event.get("kind")) for event in events)
    return {
        "stages_are_overlapping_and_not_additive_cash_shares": True,
        "decision_rows": rows,
        "event_counts": dict(sorted(counts.items())),
        "reentry_latches": [
            {
                "at": event.get("at"),
                "kind": event.get("kind"),
                "detail": event.get("detail"),
            }
            for event in events
            if str(event.get("kind", "")).startswith("reentry")
            or event.get("kind") in {"recovery_confirmation", "recovery_reset"}
        ],
        "cap_events": [
            {
                "at": event.get("at"),
                "kind": event.get("kind"),
                "detail": event.get("detail"),
            }
            for event in events
            if event.get("kind") == "cap_constraint_deferred"
        ],
        "gross_cap": gross_cap,
        "volatility_target": volatility_target,
    }


def recompute_causal_stages(
    source_path: Path, engine_path: Path, simulation: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    """Recompute trend/gate and pre/post-volatility stages without simulating."""
    source = _json(source_path)
    spec = importlib.util.spec_from_file_location("residual_cash_engine", engine_path)
    if spec is None or spec.loader is None:
        raise ValueError("cannot load frozen engine")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    from jusik.research_portfolio_models import (
        PortfolioCandidate,
        PortfolioConfig,
        PortfolioInput,
    )

    parsed = PortfolioInput.model_validate(source)
    config = PortfolioConfig(
        initial_cash_krw=Decimal("100000000"),
        gross_cap=Decimal("0.95"),
        volatility_target=Decimal("0.30"),
        low_turnover_weeks=8,
        low_turnover_band=Decimal("0.02"),
        drawdown_limit=Decimal("0.10"),
        symbol_cap=Decimal("0.20"),
        leveraged_etf_cap=Decimal("0.20"),
    )
    candidate = PortfolioCandidate(
        id="diagnostic", method="inverse_volatility", gate="fx_vix"
    )
    dates = sorted(
        {str(row["decided_at"]) for row in simulation.get("weekly_targets", [])}
    )
    output: dict[str, dict[str, Any]] = {}
    for value in dates:
        at = datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
        weights, _, blocked = module.target_weights(parsed, candidate, at, config)
        scale, proxy = module.volatility_scale(
            parsed, module._instrument_data(parsed), weights, at, config
        )
        if scale is None:
            raise ValueError(f"missing causal volatility data at {value}")
        data = module._instrument_data(parsed)
        excluded: dict[str, list[str]] = {}
        gate_allowed = module._gate_allowed(parsed, candidate, at, config)
        for symbol, item in data.items():
            reasons: list[str] = []
            bars = module._known_bars(item, at)
            if len(bars) < max(61, config.signal_window):
                reasons.append("insufficient_history")
            elif (
                bars[-1].adjusted_close
                <= sum(
                    (bar.adjusted_close for bar in bars[-config.signal_window :]),
                    Decimal(0),
                )
                / config.signal_window
            ):
                reasons.append("trend_gate")
            if gate_allowed is not True:
                reasons.append(
                    "external_gate_blocked"
                    if gate_allowed is False
                    else "external_gate_missing"
                )
            if symbol not in weights and not reasons:
                reasons.append("zero_or_invalid_volatility")
            if reasons:
                excluded[symbol] = reasons
        output[value] = {
            "pre_vol_gross": sum(weights.values(), Decimal(0)),
            "post_vol_gross": sum(weights.values(), Decimal(0)) * scale,
            "volatility_scale": scale,
            "volatility_proxy": proxy,
            "eligible_count": len(weights),
            "excluded_reasons": excluded,
            "blocked_reason": blocked,
            "eligible_symbols": sorted(weights),
        }
    return output


def run_diagnostic(prior_audit: Path, output_dir: Path) -> dict[str, Any]:
    """Read saved dev1/dev2 simulation and observation artifacts into audit JSON."""
    if output_dir.exists():
        raise ValueError("diagnostic output must be a new directory")
    simulation_dir = prior_audit / "experiment" / "simulations"
    observation_dir = prior_audit / "experiment" / "observations"
    files = sorted(simulation_dir.glob("g095_v030_c8_b002_dd010-dev*-c1.json"))
    if len(files) != 2:
        raise ValueError("expected exactly two saved dev simulation artifacts")
    output_dir.mkdir(parents=True)
    entries: list[dict[str, Any]] = []
    request = _json(prior_audit / "experiment" / "request.json")
    source_path, engine_path = (
        Path(request["source_path"]),
        Path(request["engine_path"]),
    )
    if (
        sha256(source_path) != request["source_sha256"]
        or sha256(engine_path) != request["engine_sha256"]
    ):
        raise ValueError("frozen source or engine hash mismatch")
    for path in files:
        simulation = _json(path)
        period = path.name.split("-")[1]
        observation = observation_dir / path.name
        if not observation.is_file():
            raise ValueError(f"missing saved observation: {observation}")
        entries.append(
            {
                "period": period,
                "simulation_path": str(path),
                "simulation_sha256": sha256(path),
                "observation_path": str(observation),
                "observation_sha256": sha256(observation),
                "diagnostic": diagnose_simulation(simulation),
                "causal_stages": recompute_causal_stages(
                    source_path, engine_path, simulation
                ),
            }
        )
    result = {
        "run_id": "portfolio-residual-cash-risk-proxy-v1",
        "read_only": True,
        "historical_simulations_executed": 0,
        "prior_audit": str(prior_audit),
        "entries": entries,
        "provenance": {
            "prior_audit_sha256": sha256(prior_audit / "experiment" / "results.json"),
            "module_sha256": sha256(Path(__file__)),
        },
    }
    (output_dir / "diagnostic.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prior-audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run_diagnostic(args.prior_audit, args.output)


if __name__ == "__main__":
    main()
