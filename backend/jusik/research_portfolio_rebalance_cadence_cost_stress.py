"""Run the bounded corrected-entry cadence and cost stress study.

The first phase replays 24 frozen cadence-4 control simulations.  The second
phase adds exactly 24 cadence-8 simulations.  This module has no
network or broker integration and refuses to resume a partially written run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import time
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, date, datetime
from datetime import time as clock_time
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import jusik.research_portfolio_held_band_experiment as held_band_experiment
from jusik.research_entry_attribution import attribute_simulation
from jusik.research_experiment_guard import verify_control_output, verify_hashes
from jusik.research_portfolio_held_band_experiment import (
    _copy_engine,
    _load_copy,
)
from jusik.research_portfolio_held_band_experiment import (
    _verify_accounting as _held_verify_accounting,
)
from jusik.research_portfolio_held_band_experiment import (
    _verify_runtime_hashes as _held_verify_runtime_hashes,
)
from jusik.research_portfolio_models import (
    PortfolioCandidate,
    PortfolioConfig,
    PortfolioInput,
    PortfolioSimulation,
)

RUN_ID = "portfolio-rebalance-cadence-cost-stress-v1"
PERIOD_NAMES = tuple([f"fold_{n}" for n in range(1, 8)] + ["continuous"])
FULL_COSTS = (1, 2, 3)
VARIANT_COSTS = (1, 2, 3)
FULL_EVALUATION_COUNT = 24
VARIANT_EVALUATION_COUNT = 24
COST3 = 3
EVALUATION_CAP = 48
DEADLINE_SECONDS = 3600
RATE_1X = Decimal("0.001")
RATE_3X = Decimal("0.003")
TOLERANCE_KRW = Decimal("0.000001")
_ACTIVE_DEADLINE: tuple[Any, tuple[float, float]] | None = None
VARIANT_SHA256 = "7d9ccd0d8fef90b11779d4e8c98041eadf8aeac94eb3d289318145504483b442"
HELD_HELPER_SHA256 = "bd33825fd08d55278ea7ed994d73672404a3d30530213f7e6efd2577b9abf29b"
PRIOR_RESULTS_SHA256 = (
    "d6e4895eac42625fe6fd0f3278ee98195bc031c7e651cb3d003b3c9fa4d4e2f1"
)
PRIOR_PREREG_SHA256 = "aeae52d4e1a036b2837f39ce879315b03e98023ac4ba6838e7506e7e602ce3f9"
PRIOR_MANIFEST_SHA256 = (
    "4c5d3eddc7b1f126dd62e5a5a2d718b31d22c0c93ea5295af36fd6aa7e43171f"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_exclusive(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(value, output, ensure_ascii=False, indent=2, default=str)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def _checkpoint(path: Path, value: object) -> None:
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as output:
        json.dump(value, output, ensure_ascii=False, indent=2, default=str)
        output.write("\n")
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, path)


def _arm_deadline(seconds: int) -> tuple[Any, tuple[float, float]]:
    """Install a process timer so a single blocking simulate call is bounded."""
    if not hasattr(signal, "SIGALRM"):
        raise RuntimeError("an interruptible SIGALRM deadline is required")
    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.getitimer(signal.ITIMER_REAL)

    def interrupt(_signum: int, _frame: Any) -> None:
        raise TimeoutError(f"execution deadline exceeded ({seconds}s)")

    signal.signal(signal.SIGALRM, interrupt)
    signal.setitimer(signal.ITIMER_REAL, float(seconds))
    return previous_handler, previous_timer


def _disarm_deadline(previous: tuple[Any, tuple[float, float]]) -> None:
    signal.setitimer(signal.ITIMER_REAL, 0)
    signal.signal(signal.SIGALRM, previous[0])
    if previous[1] != (0.0, 0.0):
        signal.setitimer(signal.ITIMER_REAL, *previous[1])


def _empty_output(path: Path) -> None:
    if path.exists() and (not path.is_dir() or any(path.iterdir())):
        raise ValueError("output must be new or empty; retry/resume is refused")
    path.mkdir(parents=True, exist_ok=True)


def _config(base: PortfolioConfig, band: str, cost: int) -> PortfolioConfig:
    if band not in {"0.02", "0.04"} or isinstance(cost, bool) or cost not in {1, 2, 3}:
        raise ValueError("only bands .02/.04 and cost multipliers 1/2/3 are allowed")
    if any(
        rate != RATE_1X
        for rate in (base.fee_rate, base.slippage_rate, base.fx_spread_rate)
    ):
        raise ValueError("frozen base cost rates must all be 0.001")
    values = base.model_dump()
    values.update(
        low_turnover_band=Decimal(band),
        fee_rate=RATE_1X * cost,
        slippage_rate=RATE_1X * cost,
        fx_spread_rate=RATE_1X * cost,
    )
    result = PortfolioConfig.model_validate(values)
    if (
        result.initial_cash_krw != Decimal("100000000")
        or result.symbol_cap != Decimal("0.20")
        or result.gross_cap != Decimal("0.60")
        or result.leveraged_etf_cap != Decimal("0.20")
        or result.drawdown_limit != Decimal("0.10")
    ):
        raise ValueError("frozen capital or risk configuration changed")
    return result


def _cadence_config(base: PortfolioConfig, weeks: int, cost: int) -> PortfolioConfig:
    """Build the study arm while changing cadence and cost only."""
    if weeks not in {4, 8} or cost not in {1, 2, 3}:
        raise ValueError("only cadence 4/8 and cost multipliers 1/2/3 are allowed")
    if base.low_turnover_weeks != 4 or base.low_turnover_band != Decimal("0.02"):
        raise ValueError("frozen base cadence and corrected-entry band changed")
    values = base.model_dump()
    values.update(
        low_turnover_weeks=weeks,
        low_turnover_band=Decimal("0.02"),
        fee_rate=RATE_1X * cost,
        slippage_rate=RATE_1X * cost,
        fx_spread_rate=RATE_1X * cost,
    )
    result = PortfolioConfig.model_validate(values)
    if result.low_turnover_band != Decimal("0.02"):
        raise ValueError("corrected-entry band must remain 0.02")
    return result


def _periods(prereg: dict[str, Any]) -> list[dict[str, Any]]:
    periods = prereg.get("periods")
    if not isinstance(periods, list) or len(periods) != 8:
        raise ValueError("exactly seven folds plus continuous are required")
    if [item.get("name") for item in periods] != list(PERIOD_NAMES):
        raise ValueError("period ordering is not frozen")
    for item in periods:
        if not isinstance(item.get("start"), str) or not isinstance(
            item.get("end"), str
        ):
            raise ValueError("period dates are missing")
    return periods


def _artifact_key(name: str) -> tuple[str, str, int]:
    stem = name.removesuffix(".json")
    period, arm_cost = stem.split("-", 1) if "-" in stem else ("", "")
    if period not in PERIOD_NAMES or "_c" not in arm_cost:
        raise ValueError(f"unexpected frozen artifact name: {name}")
    arm, cost_text = arm_cost.rsplit("_c", 1)
    if arm not in {"control", "variant"} or cost_text not in {"1", "2", "3"}:
        raise ValueError(f"unexpected frozen artifact name: {name}")
    return period, arm, int(cost_text)


def _control_hashes(prereg: dict[str, Any]) -> dict[str, str]:
    """Normalize the prior preregistration's historical variant-labelled keys."""
    raw = prereg.get("control_hashes")
    if not isinstance(raw, dict) or len(raw) != 16:
        raise ValueError("legacy control hash section is malformed")
    normalized = {
        name.replace("-variant_", "-control_"): digest for name, digest in raw.items()
    }
    expected = {
        f"{period}-control_c{cost}.json"
        for period in PERIOD_NAMES
        for cost in FULL_COSTS
    }
    if set(normalized) != expected:
        raise ValueError("corrected control hashes do not cover all control cells")
    return normalized


def _verify_frozen_artifacts(
    prior_audit: Path,
    source: PortfolioInput,
    base: PortfolioConfig,
    prereg: dict[str, Any],
    results: dict[str, Any],
) -> None:
    """Validate every stored result before permitting a future simulate call."""
    rows = results.get("evaluations")
    if not isinstance(rows, list) or len(rows) != 48:
        raise ValueError("frozen result set must contain exactly 48 evaluations")
    by_name: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("artifact"), str):
            raise ValueError("frozen evaluation row is malformed")
        name = row["artifact"]
        if name in by_name:
            raise ValueError(f"duplicate frozen artifact: {name}")
        by_name[name] = row
    expected_names = {
        f"{period}-{arm}_c{cost}.json"
        for period in PERIOD_NAMES
        for arm in ("control", "variant")
        for cost in FULL_COSTS
    }
    if set(by_name) != expected_names:
        raise ValueError(
            "frozen result set does not cover all 48 period/arm/cost cells"
        )
    candidate = {
        "id": "portfolio_inverse_volatility_fx_vix_v1",
        "method": "inverse_volatility",
        "gate": "fx_vix",
    }
    for name in sorted(expected_names):
        period_name, arm, cost = _artifact_key(name)
        path = prior_audit / "simulations" / name
        payload = _load_json(path)
        simulation = PortfolioSimulation.model_validate(payload)
        row = by_name[name]
        if (
            row.get("period") != period_name
            or row.get("arm") != arm
            or row.get("cost_multiplier") != cost
        ):
            raise ValueError(f"frozen metadata disagrees with {name}")
        period = next(item for item in _periods(prereg) if item["name"] == period_name)
        config = _config(base, "0.02" if arm == "control" else "0.04", cost)
        expected_candidate = PortfolioCandidate.model_validate(candidate)
        if (
            simulation.candidate != expected_candidate
            or simulation.policy != "low_turnover_combined"
        ):
            raise ValueError(f"frozen candidate/policy mismatch: {name}")
        if (
            simulation.period_start.isoformat() != period["start"]
            or simulation.period_end.isoformat() != period["end"]
            or simulation.complete is not True
            or simulation.incomplete_reasons
        ):
            raise ValueError(f"frozen period/completeness mismatch: {name}")
        if sha256(path) != row.get("sha256"):
            raise ValueError(f"frozen row hash mismatch: {name}")
        for metric in type(simulation.metrics).model_fields:
            if metric not in row or str(row[metric]) != str(
                getattr(simulation.metrics, metric)
            ):
                raise ValueError(f"frozen metric mismatch: {name} {metric}")
        _verify_accounting(simulation, cost, config, source)
        mutated_equity = [*simulation.equity]
        terminal = mutated_equity[-1]
        mutated_equity[-1] = terminal.model_copy(
            update={"cash_krw": terminal.cash_krw + Decimal(1)}
        )
        mutated = simulation.model_copy(update={"equity": mutated_equity})
        try:
            _verify_accounting(mutated, cost, config, source)
        except ValueError:
            pass
        else:
            raise RuntimeError(f"cash mutation accepted: {name}")


def _prior_inputs(
    prior_audit: Path,
) -> tuple[PortfolioInput, PortfolioConfig, dict[str, Any], dict[str, Any]]:
    prior_audit = prior_audit.resolve()
    prereg_path, results_path, manifest_path = (
        prior_audit / "preregistration.json",
        prior_audit / "results.json",
        prior_audit / "hash-manifest.json",
    )
    prior_manifest = _load_json(manifest_path)
    if not isinstance(prior_manifest, dict):
        raise ValueError("prior hash manifest is malformed")
    verify_hashes(
        {
            prereg_path: PRIOR_PREREG_SHA256,
            results_path: PRIOR_RESULTS_SHA256,
            manifest_path: PRIOR_MANIFEST_SHA256,
        }
    )
    for relative, digest in prior_manifest.items():
        path = (prior_audit / relative).resolve()
        if prior_audit not in path.parents or not path.is_file():
            raise ValueError(f"prior manifest path is invalid: {relative}")
        verify_hashes({path: digest})
    prereg = _load_json(prereg_path)
    results = _load_json(results_path)
    if results.get("evaluations") is None or len(results["evaluations"]) != 48:
        raise ValueError("frozen result set must contain exactly 48 evaluations")
    manifest_paths = prereg.get("input_paths") or prereg.get("source_paths")
    if not isinstance(manifest_paths, dict) or not isinstance(
        manifest_paths.get("source-manifest.json"), str
    ):
        raise ValueError("frozen source path is missing")
    frozen_dir = Path(manifest_paths["source-manifest.json"]).resolve().parent
    source_hashes = prereg.get("source_hashes")
    if not isinstance(source_hashes, dict):
        raise ValueError("frozen source hashes are missing")
    verify_hashes({frozen_dir / name: digest for name, digest in source_hashes.items()})
    manifest = _load_json(frozen_dir / "source-manifest.json")
    source = PortfolioInput.model_validate(manifest["frozen_input"])
    base = PortfolioConfig.model_validate(prereg["base_config"])
    _periods(prereg)
    _verify_frozen_artifacts(prior_audit, source, base, prereg, results)
    return source, base, prereg, results


def _verify_prior_inputs_unchanged(
    prior_audit: Path,
    source: PortfolioInput,
    base: PortfolioConfig,
    prereg: dict[str, Any],
    results: dict[str, Any],
) -> None:
    current = _prior_inputs(prior_audit)
    if current != (source, base, prereg, results):
        raise ValueError("frozen inputs changed during execution")


def _source_maps(
    source: PortfolioInput,
) -> tuple[
    dict[str, dict[datetime, Decimal]],
    dict[str, dict[date, Any]],
    dict[str, Any],
]:
    opens: dict[str, dict[datetime, Decimal]] = {}
    bars: dict[str, dict[date, Any]] = {}
    snapshots: dict[str, Any] = {}
    for snapshot in source.instruments:
        item = snapshot.instruments[0]
        zone = ZoneInfo(item.instrument.timezone)
        opening = (
            clock_time(9)
            if item.instrument.timezone == "Asia/Seoul"
            else clock_time(9, 30)
        )
        opens[item.symbol] = {
            datetime.combine(bar.date, opening, zone).astimezone(UTC): bar.open
            for bar in item.bars
        }
        bars[item.symbol] = {bar.date: bar for bar in item.bars}
        snapshots[item.symbol] = snapshot
    return opens, bars, snapshots


def _source_fx(
    source: PortfolioInput, at: datetime, config: PortfolioConfig
) -> Decimal | None:
    rows = [
        item
        for item in source.external.observations
        if item.series == "usdkrw"
        and item.observed_on <= at.date()
        and item.available_at <= at
    ]
    if not rows:
        return None
    latest = max(
        rows, key=lambda item: (item.observed_on, item.available_at, item.revision)
    )
    if (at.date() - latest.observed_on).days > config.external_max_age_days:
        return None
    return latest.value


def preflight(prior_audit: Path) -> dict[str, Any]:
    """Run the stored-input checks without creating output or calling simulate."""
    source, base, prereg, results = _prior_inputs(prior_audit)
    return {
        "source": source,
        "base_config": base,
        "preregistration": prereg,
        "results": results,
        "evaluation_count": FULL_EVALUATION_COUNT,
        "cash_mutation_rejection_checks": FULL_EVALUATION_COUNT,
        "historical_calls": 0,
    }


def _close(actual: Decimal, expected: Decimal, label: str) -> None:
    if abs(actual - expected) > TOLERANCE_KRW:
        raise ValueError(f"{label} residual {actual - expected} exceeds tolerance")


def _verify_temporal_accounting(
    sim: PortfolioSimulation, config: PortfolioConfig, source: PortfolioInput
) -> None:
    """Verify raw opens, split quantity/cash, terminal marks and final NAV."""
    opens, bars, snapshots = _source_maps(source)
    currencies = {
        symbol: item.instrument.currency
        for symbol, item in (
            (s.instruments[0].symbol, s.instruments[0]) for s in source.instruments
        )
    }
    quantities: defaultdict[str, int] = defaultdict(int)
    cash = config.initial_cash_krw
    split_cash: defaultdict[str, Decimal] = defaultdict(Decimal)
    actions: dict[str, dict[date, Any]] = {
        symbol: {action.date: action for action in snapshot.corporate_actions}
        for symbol, snapshot in snapshots.items()
    }
    trade_by_day: defaultdict[date, list[Any]] = defaultdict(list)
    for trade in sim.trades:
        if trade.executed_at.tzinfo is None or trade.decided_at.tzinfo is None:
            raise ValueError("trade timestamps must be timezone aware")
        if (
            trade.executed_at <= trade.decided_at
            or trade.executed_at.utcoffset() != UTC.utcoffset(None)
        ):
            raise ValueError("execution must be strictly after decision in UTC")
        available = [
            moment for moment in opens[trade.symbol] if moment > trade.decided_at
        ]
        if not available or min(available) != trade.executed_at:
            raise ValueError(f"trade is not next valid open: {trade.symbol}")
        raw = opens[trade.symbol][trade.executed_at]
        sign = Decimal(1) if trade.side == "buy" else Decimal(-1)
        if currencies[trade.symbol] == "USD":
            expected_fx_rate = _source_fx(source, trade.executed_at, config)
            if expected_fx_rate is None or trade.fx_rate != expected_fx_rate:
                raise ValueError(
                    f"FX rate does not match source observation: {trade.symbol}"
                )
        elif trade.fx_rate != Decimal(1):
            raise ValueError(f"KRW trade has non-unit FX rate: {trade.symbol}")
        expected_price = raw * (Decimal(1) + sign * config.slippage_rate)
        if trade.local_price != expected_price:
            raise ValueError(f"execution price does not match raw open: {trade.symbol}")
        fee = trade.notional_krw * config.fee_rate
        slippage = Decimal(trade.quantity) * raw * config.slippage_rate * trade.fx_rate
        expected_fx = (
            (trade.notional_krw + sign * fee) * config.fx_spread_rate
            if currencies[trade.symbol] == "USD"
            else Decimal(0)
        )
        _close(
            trade.notional_krw,
            Decimal(trade.quantity) * trade.local_price * trade.fx_rate,
            "notional",
        )
        _close(trade.transaction_cost_krw, fee + slippage, "transaction cost")
        _close(trade.fx_cost_krw, expected_fx, "FX cost")
        trade_by_day[trade.executed_at.date()].append(trade)
    event_days = set(trade_by_day)
    event_days.update(
        day
        for by_date in actions.values()
        for day in by_date
        if sim.period_start <= day <= sim.period_end
    )
    for day in sorted(event_days):
        for symbol, by_date in actions.items():
            action = by_date.get(day)
            if action is None or quantities[symbol] <= 0:
                continue
            open_moment = min(
                moment for moment in opens[symbol] if moment.date() == day
            )
            exact = Decimal(quantities[symbol]) * action.factor
            whole = int(exact)
            cash_in_lieu = (exact - whole) * opens[symbol][open_moment]
            if currencies[symbol] == "USD":
                fx = _source_fx(source, open_moment, config)
                if fx is None:
                    raise ValueError(f"missing split FX source observation: {symbol}")
                cash_in_lieu *= fx
            cash += cash_in_lieu
            split_cash[symbol] += cash_in_lieu
            quantities[symbol] = whole
        for trade in sorted(trade_by_day[day], key=lambda item: item.executed_at):
            if trade.side == "sell" and trade.quantity > quantities[trade.symbol]:
                raise ValueError("trade sells more quantity than held")
            fee = trade.notional_krw * config.fee_rate
            cash -= (
                Decimal(1) if trade.side == "buy" else Decimal(-1)
            ) * trade.notional_krw
            cash -= fee + trade.fx_cost_krw
            quantities[trade.symbol] += (
                trade.quantity if trade.side == "buy" else -trade.quantity
            )
    for symbol, amount in sim.split_cash_in_lieu_krw.items():
        _close(amount, split_cash[symbol], f"split cash {symbol}")
    terminal_quantities = {
        position.symbol: position.quantity for position in sim.positions
    }
    if {
        symbol: quantity for symbol, quantity in quantities.items() if quantity > 0
    } != terminal_quantities:
        raise ValueError("terminal quantity does not reconcile to trades and splits")
    final_at = sim.equity[-1].at
    terminal = Decimal(0)
    for position in sim.positions:
        if position.valued_at != final_at:
            raise ValueError(
                "terminal mark timestamp does not match final equity point"
            )
        candidates = [day for day in bars[position.symbol] if day <= sim.period_end]
        if not candidates:
            raise ValueError("terminal mark has no source close")
        bar = bars[position.symbol][max(candidates)]
        if position.local_close != bar.close:
            raise ValueError(
                f"terminal local mark does not match source close: {position.symbol}"
            )
        terminal_fx = (
            _source_fx(source, final_at, config)
            if position.currency == "USD"
            else Decimal(1)
        )
        if terminal_fx is None or position.fx_rate != terminal_fx:
            raise ValueError(
                f"terminal FX rate does not match source: {position.symbol}"
            )
        _close(
            position.value_krw,
            Decimal(position.quantity) * position.local_close * terminal_fx,
            "terminal position value",
        )
        terminal += position.value_krw
    _close(cash, sim.equity[-1].cash_krw, "ending cash")
    _close(cash + terminal, sim.metrics.final_equity_krw, "final NAV")


def _verify_accounting(
    sim: PortfolioSimulation, cost: int, config: PortfolioConfig, source: PortfolioInput
) -> dict[str, Any]:
    if cost not in {1, 2, 3}:
        raise ValueError("unsupported cost multiplier")
    _held_verify_accounting(sim, cost, config, source)
    accounting = attribute_simulation(sim, cost)
    _verify_temporal_accounting(sim, config, source)
    return accounting


def _verify_runtime_hashes(engine_source: Path) -> None:
    """Reuse the held runner's immutable import checks and pin its helper."""
    _held_verify_runtime_hashes(engine_source)
    helper = Path(str(held_band_experiment.__file__))
    verify_hashes({helper: HELD_HELPER_SHA256})


def _verify_exact_replay(
    payload: dict[str, Any], expected: Path, expected_sha: str
) -> None:
    """Require byte-independent full JSON equality through the shared guard."""
    verify_control_output(payload, expected, expected_sha)


def _exposure(sim: PortfolioSimulation) -> dict[str, str]:
    sampled = [
        (point.equity_krw - point.cash_krw) / point.equity_krw * 100
        for point in sim.equity
        if point.equity_krw > 0
    ]
    final_gross = sum((position.value_krw for position in sim.positions), Decimal(0))
    final_leveraged = sum(
        (
            position.value_krw
            for position in sim.positions
            if position.symbol in {"TQQQ", "UPRO", "SOXL"}
        ),
        Decimal(0),
    )
    denominator = sim.metrics.final_equity_krw
    return {
        "sampled_gross_exposure_pct": str(max(sampled, default=Decimal(0))),
        "final_gross_exposure_pct": str(
            final_gross / denominator * 100 if denominator else Decimal(0)
        ),
        "final_leveraged_exposure_pct": str(
            final_leveraged / denominator * 100 if denominator else Decimal(0)
        ),
        "scope": (
            "sampled equity points; final is terminal mark and is not claimed "
            "to be the maximum"
        ),
    }


def _reentry_summary(sim: PortfolioSimulation) -> dict[str, Any]:
    episodes: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for event in sorted(sim.policy_events, key=lambda item: item.at):
        if event.kind == "risk_exit":
            if current is not None:
                current["status"] = "censored"
                episodes.append(current)
            current = {"exit_utc": event.at.isoformat(), "status": "open"}
        elif current is not None and event.kind == "reentry_ready":
            current["ready_utc"] = event.at.isoformat()
        elif current is not None and event.kind == "recovery_reset":
            current["status"] = "reset"
            episodes.append(current)
            current = None
        elif current is not None and event.kind == "reentry":
            current["reentry_utc"] = event.at.isoformat()
            current["status"] = "reentered"
            episodes.append(current)
            current = None
    if current is not None:
        current["status"] = "censored"
        episodes.append(current)
    ready = [event for event in sim.policy_events if event.kind == "reentry_ready"]
    reentries = [event for event in sim.policy_events if event.kind == "reentry"]
    delays = [
        str(
            (next_event.at - event.at).total_seconds()
        )
        if (next_event := next(
            (candidate for candidate in reentries if candidate.at >= event.at), None
        ))
        else None
        for event in ready
    ]
    return {
        "ready_utc": [event.at.isoformat() for event in ready],
        "reentry_utc": [event.at.isoformat() for event in reentries],
        "delay_seconds": delays,
        "episodes": episodes,
        "never_ready_count": sum(
            episode.get("status") == "censored" and "ready_utc" not in episode
            for episode in episodes
        ),
    }


def _row(
    period: dict[str, Any],
    arm: str,
    cost: int,
    sim: PortfolioSimulation,
    accounting: dict[str, Any],
    artifact: Path,
) -> dict[str, Any]:
    metrics = sim.metrics.model_dump(mode="json")
    return {
        "period": period["name"],
        "start": period["start"],
        "end": period["end"],
        "arm": arm,
        "cost_multiplier": cost,
        "complete": sim.complete,
        **metrics,
        "band_skip_count": sum(
            event.kind == "band_skip" for event in sim.policy_events
        ),
        "leverage": _exposure(sim),
        "reentry": _reentry_summary(sim),
        "final_cash_krw": str(sim.equity[-1].cash_krw),
        "final_quantities": {
            position.symbol: position.quantity for position in sim.positions
        },
        "accounting_residual": str(accounting["residual"]),
        "net_pnl_krw": str(
            sim.metrics.final_equity_krw - sim.metrics.initial_equity_krw
        ),
        "artifact": artifact.name,
        "sha256": sha256(artifact),
    }


def _quantities(sim: PortfolioSimulation) -> dict[str, int]:
    return {position.symbol: position.quantity for position in sim.positions}


def _cost3_summary(pairs: list[dict[str, Any]]) -> dict[str, Any]:
    fold_pairs = [
        pair
        for pair in pairs
        if pair["cost_multiplier"] == COST3 and pair["period"] != "continuous"
    ]
    returns = [Decimal(pair["deltas"]["total_return_pct"]) for pair in fold_pairs]

    def median(values: list[Decimal]) -> Decimal:
        ordered_values = sorted(values)
        middle = len(ordered_values) // 2
        return (
            ordered_values[middle]
            if len(ordered_values) % 2
            else (ordered_values[middle - 1] + ordered_values[middle]) / 2
        )

    return {
        "fold_return_delta_median_pp": str(median(returns)),
        "fold_mdd_delta_median_pp": str(
            median([Decimal(pair["deltas"]["max_drawdown_pct"]) for pair in fold_pairs])
        ),
        "fold_turnover_delta_median_pp": str(
            median([Decimal(pair["deltas"]["turnover_pct"]) for pair in fold_pairs])
        ),
        "positive_fold_count": sum(value > 0 for value in returns),
        "negative_fold_count": sum(value < 0 for value in returns),
        "zero_fold_count": sum(value == 0 for value in returns),
        "scope": "seven independent folds; continuous is reported separately",
    }


def _delta(left: object, right: object) -> Decimal:
    with localcontext() as context:
        context.prec = 50
        return Decimal(str(left)) - Decimal(str(right))


def _run_call(
    simulate: Callable[..., PortfolioSimulation],
    source: PortfolioInput,
    candidate: PortfolioCandidate,
    period: dict[str, Any],
    config: PortfolioConfig,
) -> PortfolioSimulation:
    return simulate(
        source,
        candidate,
        date.fromisoformat(period["start"]),
        date.fromisoformat(period["end"]),
        config,
        "low_turnover_combined",
    )


def _verify_simulation_contract(
    sim: PortfolioSimulation,
    period: dict[str, Any],
    candidate: PortfolioCandidate,
    config: PortfolioConfig,
) -> None:
    if not sim.complete or sim.incomplete_reasons:
        raise RuntimeError(f"incomplete simulation: {period['name']}")
    if sim.period_start != date.fromisoformat(
        period["start"]
    ) or sim.period_end != date.fromisoformat(period["end"]):
        raise RuntimeError(f"simulation period mismatch: {period['name']}")
    if sim.candidate != candidate:
        raise RuntimeError(f"simulation candidate mismatch: {period['name']}")
    if sim.policy != "low_turnover_combined":
        raise RuntimeError(f"simulation policy mismatch: {period['name']}")
    if sim.metrics.initial_equity_krw != config.initial_cash_krw:
        raise RuntimeError(f"simulation initial equity mismatch: {period['name']}")


def _run_experiment_inner(
    prior_audit: Path,
    engine_source: Path,
    output_dir: Path,
    *,
    allow_historical_execution: bool = False,
    clock: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    """Run only after explicit approval; all preflight is read-only."""
    global _ACTIVE_DEADLINE
    deadline = clock() + DEADLINE_SECONDS
    _ACTIVE_DEADLINE = _arm_deadline(DEADLINE_SECONDS)
    _empty_output(output_dir)
    _write_exclusive(
        output_dir / ".run-lock",
        {"run_id": RUN_ID, "status": "active", "pid": os.getpid()},
    )
    ledger: list[dict[str, Any]] = []
    _checkpoint(
        output_dir / "ledger.json",
        {
            "run_id": RUN_ID,
            "cap": EVALUATION_CAP,
            "deadline_seconds": DEADLINE_SECONDS,
            "ledger": ledger,
        },
    )
    _verify_runtime_hashes(engine_source)
    source, base, prereg, prior_results = _prior_inputs(prior_audit)
    periods = _periods(prereg)
    candidate = PortfolioCandidate(
        id="portfolio_inverse_volatility_fx_vix_v1",
        method="inverse_volatility",
        gate="fx_vix",
    )
    if not allow_historical_execution:
        raise PermissionError(
            "historical simulation requires explicit allow_historical_execution"
        )
    original_path, variant_path = _copy_engine(engine_source, output_dir)
    if sha256(variant_path) != VARIANT_SHA256:
        raise ValueError("guarded variant hash mismatch")
    variant = _load_copy(variant_path, "rebalance_cadence_variant_engine")
    _checkpoint(
        output_dir / "ledger.json",
        {
            "run_id": RUN_ID,
            "cap": EVALUATION_CAP,
            "deadline_seconds": DEADLINE_SECONDS,
            "ledger": ledger,
        },
    )
    (output_dir / "simulations").mkdir()
    _write_exclusive(
        output_dir / "preregistration.json",
        {
            "run_id": RUN_ID,
            "corrected_entry_band": "0.02",
            "cadences_weeks": [4, 8],
            "cost_multipliers": [1, 2, 3],
            "periods": periods,
            "evaluation_count": EVALUATION_CAP,
            "full_replay_count": FULL_EVALUATION_COUNT,
            "cash_mutation_rejection_checks": 48,
            "source_run_id": prior_results.get("source_run_id"),
            "point_in_time_verified": False,
            "automatic_trading_eligible": False,
            "source_paths": prereg["input_paths"],
            "source_hashes": prereg["source_hashes"],
            "core_hashes": prereg["core_hashes"],
            "imported_helper_hashes": prereg["imported_helper_hashes"],
            "held_helper_sha256": HELD_HELPER_SHA256,
            "base_config": base.model_dump(mode="json"),
            "validated_configs": {
                f"{weeks}w-c{cost}": _cadence_config(
                    base, weeks, cost
                ).model_dump(mode="json")
                for weeks in (4, 8) for cost in (1, 2, 3)
            },
            "runner_sha256": sha256(Path(__file__)),
        },
    )
    rows: list[dict[str, Any]] = []
    simulations: dict[tuple[str, str, int], PortfolioSimulation] = {}
    for arm, weeks in (("control", 4), ("variant", 8)):
        for period in periods:
            for cost in FULL_COSTS:
                    if len(ledger) >= EVALUATION_CAP:
                        raise RuntimeError("evaluation cap exceeded")
                    if clock() >= deadline:
                        raise TimeoutError(
                            "execution deadline exceeded before simulation"
                        )
                    ledger.append(
                        {
                            "index": len(ledger),
                            "phase": "control" if arm == "control" else "variant",
                            "period": period["name"],
                            "arm": arm,
                            "cost": cost,
                            "status": "reserved",
                            "deadline_seconds": DEADLINE_SECONDS,
                        }
                    )
                    _checkpoint(
                        output_dir / "ledger.json",
                        {
                            "run_id": RUN_ID,
                            "cap": EVALUATION_CAP,
                            "deadline_seconds": DEADLINE_SECONDS,
                            "ledger": ledger,
                        },
                    )
                    config = _cadence_config(base, weeks, cost)
                    sim = _run_call(variant.simulate, source, candidate, period, config)
                    _verify_simulation_contract(sim, period, candidate, config)
                    if clock() >= deadline:
                        raise TimeoutError(
                            "execution deadline exceeded after simulation"
                        )
                    artifact = (
                        output_dir
                        / "simulations"
                        / f"{period['name']}-{arm}_c{cost}.json"
                    )
                    payload = sim.model_dump(mode="json")
                    _write_exclusive(artifact, payload)
                    accounting = _verify_accounting(sim, cost, config, source)
                    if arm == "control":
                        expected_name = f"{period['name']}-control_c{cost}.json"
                        expected_path = prior_audit / "simulations" / expected_name
                        expected_hash = next(
                            item["sha256"]
                            for item in prior_results["evaluations"]
                            if item["artifact"] == expected_name
                        )
                        _verify_exact_replay(payload, expected_path, expected_hash)
                    simulations[(period["name"], arm, cost)] = sim
                    rows.append(_row(period, arm, cost, sim, accounting, artifact))
                    ledger[-1].update(
                        {
                            "status": "saved",
                            "artifact": artifact.name,
                            "sha256": sha256(artifact),
                        }
                    )
                    _checkpoint(
                        output_dir / "ledger.json",
                        {
                            "run_id": RUN_ID,
                            "cap": EVALUATION_CAP,
                            "deadline_seconds": DEADLINE_SECONDS,
                            "ledger": ledger,
                        },
                    )
        _verify_runtime_hashes(engine_source)
        _verify_prior_inputs_unchanged(prior_audit, source, base, prereg, prior_results)
    if len(rows) != EVALUATION_CAP:
        raise RuntimeError("runner did not produce exactly 48 evaluations")
    pairs: list[dict[str, Any]] = []
    for period in periods:
        for cost in FULL_COSTS:
            control = simulations[(period["name"], "control", cost)]
            variant_sim = simulations[(period["name"], "variant", cost)]
            control_qty, variant_qty = _quantities(control), _quantities(variant_sim)
            symbols = sorted(set(control_qty) | set(variant_qty))
            pairs.append(
                {
                    "period": period["name"],
                    "cost_multiplier": cost,
                    "deltas": {
                        "total_return_pct": str(
                            _delta(
                                variant_sim.metrics.total_return_pct,
                                control.metrics.total_return_pct,
                            )
                        ),
                        "max_drawdown_pct": str(
                            _delta(
                                variant_sim.metrics.max_drawdown_pct,
                                control.metrics.max_drawdown_pct,
                            )
                        ),
                        "trade_count": variant_sim.metrics.trade_count
                        - control.metrics.trade_count,
                        "turnover_pct": str(
                            _delta(
                                variant_sim.metrics.turnover_pct,
                                control.metrics.turnover_pct,
                            )
                        ),
                        "transaction_cost_krw": str(
                            variant_sim.metrics.transaction_cost_krw
                            - control.metrics.transaction_cost_krw
                        ),
                        "fx_cost_krw": str(
                            variant_sim.metrics.fx_cost_krw
                            - control.metrics.fx_cost_krw
                        ),
                        "final_cash_krw": str(
                            variant_sim.equity[-1].cash_krw
                            - control.equity[-1].cash_krw
                        ),
                        "net_pnl_krw": str(
                            (
                                variant_sim.metrics.final_equity_krw
                                - variant_sim.metrics.initial_equity_krw
                            )
                            - (
                                control.metrics.final_equity_krw
                                - control.metrics.initial_equity_krw
                            )
                        ),
                    },
                    "quantity_effect": {
                        symbol: variant_qty.get(symbol, 0) - control_qty.get(symbol, 0)
                        for symbol in symbols
                    },
                }
            )
    result = {
        "run_id": RUN_ID,
        "evaluations": rows,
        "pairs": pairs,
        "summary": _cost3_summary(pairs),
        "all_complete": True,
        "full_replay_count": FULL_EVALUATION_COUNT,
        "variant_count": VARIANT_EVALUATION_COUNT,
        "evaluation_count": len(rows),
        "evaluation_cap": EVALUATION_CAP,
        "deadline_seconds": DEADLINE_SECONDS,
        "automatic_promotion": False,
        "retrospective_reused_history": True,
    }
    _write_exclusive(output_dir / "results.json", result)
    manifest = {
        str(path.relative_to(output_dir)): sha256(path)
        for path in output_dir.rglob("*")
        if path.is_file() and path.name != "hash-manifest.json"
    }
    _write_exclusive(output_dir / "hash-manifest.json", manifest)
    _disarm_deadline(_ACTIVE_DEADLINE)
    _ACTIVE_DEADLINE = None
    return result


def run_experiment(
    prior_audit: Path,
    engine_source: Path,
    output_dir: Path,
    *,
    allow_historical_execution: bool = False,
    clock: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    """Run the bounded experiment and preserve a failure record on every abort."""
    # Refuse an existing run before entering the failure writer.  This keeps a
    # successful ledger/results pair immutable when a caller accidentally reruns.
    if output_dir.exists() and (not output_dir.is_dir() or any(output_dir.iterdir())):
        raise ValueError("output must be new or empty; retry/resume is refused")
    try:
        return _run_experiment_inner(
            prior_audit,
            engine_source,
            output_dir,
            allow_historical_execution=allow_historical_execution,
            clock=clock,
        )
    except BaseException as error:
        global _ACTIVE_DEADLINE
        if _ACTIVE_DEADLINE is not None:
            _disarm_deadline(_ACTIVE_DEADLINE)
            _ACTIVE_DEADLINE = None
        if (
            output_dir.is_dir()
            and (output_dir / "ledger.json").exists()
            and not (output_dir / "failure.json").exists()
        ):
            ledger: object = {}
            if (output_dir / "ledger.json").exists():
                ledger = _load_json(output_dir / "ledger.json")
            _write_exclusive(
                output_dir / "failure.json",
                {"run_id": RUN_ID, "error": repr(error), "ledger": ledger},
            )
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prior-audit", type=Path, required=True)
    parser.add_argument("--engine-source", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--allow-historical-execution", action="store_true")
    args = parser.parse_args(argv)
    result = run_experiment(
        args.prior_audit,
        args.engine_source,
        args.output_dir,
        allow_historical_execution=args.allow_historical_execution,
    )
    print(
        json.dumps(
            {
                "run_id": RUN_ID,
                "evaluation_count": result["evaluation_count"],
                "all_complete": result["all_complete"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
