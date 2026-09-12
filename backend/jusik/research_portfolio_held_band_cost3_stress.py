"""Prepare and (only with explicit approval) run the held-band cost-3 stress.

The first phase replays the 32 frozen full JSON simulations.  The second phase
adds exactly 16 simulations at a three-times cost rate.  This module has no
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

from jusik.research_entry_attribution import attribute_simulation
from jusik.research_experiment_guard import verify_control_output, verify_hashes
from jusik.research_portfolio_held_band_experiment import (
    _copy_engine,
    _load_copy,
)
from jusik.research_portfolio_held_band_experiment import (
    _verify_accounting as _held_verify_accounting,
)
from jusik.research_portfolio_models import (
    PortfolioCandidate,
    PortfolioConfig,
    PortfolioInput,
    PortfolioSimulation,
)

RUN_ID = "portfolio-held-band-cost3-stress-v1"
PERIOD_NAMES = tuple([f"fold_{n}" for n in range(1, 8)] + ["continuous"])
FULL_COSTS = (1, 2)
COST3 = 3
FULL_EVALUATION_COUNT = 32
COST3_EVALUATION_COUNT = 16
EVALUATION_CAP = 48
DEADLINE_SECONDS = 3600
RATE_1X = Decimal("0.001")
RATE_3X = Decimal("0.003")
TOLERANCE_KRW = Decimal("0.000001")
_ACTIVE_DEADLINE: tuple[Any, tuple[float, float]] | None = None
VARIANT_SHA256 = "7d9ccd0d8fef90b11779d4e8c98041eadf8aeac94eb3d289318145504483b442"
PRIOR_RESULTS_SHA256 = (
    "6c20c79552964182d52e5a9ce8571747ddf97a21a9c7b5c46b2dc827e167479b"
)
PRIOR_PREREG_SHA256 = "fa5065df2ae70d024656209b0a33b755071c1441ecfa3406db99973fda49277e"
PRIOR_MANIFEST_SHA256 = (
    "bba3822f08a648462c8a2634c9402b545c833ad854bcb924fac96adb75d366a2"
)
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
IMPORTED_HASHES = {
    "research_entry_attribution.py": (
        "3013c6ba8ddbd0ec001462272ee9808ee105afcc939fd25360233c69df594f56"
    ),
    "research_unheld_entry_experiment.py": (
        "a31a455ae79dddce3b19248bc85a4068be49d0d7d0f06bea50422818b866f6d8"
    ),
    "research_experiment_guard.py": (
        "5e9a9cb9b25ccbf73becb9a7a6cb10914e8f5ef1ba378a2a687e7a21bc5a2bd0e"
    ),
    "research_external_models.py": (
        "fa83ef9b7c294e5b9a687969ae0cf0c9fe20d9b690cc90ab7ee3175be4918e0a"
    ),
    "research_models.py": (
        "1d518334aadef618b69f350bc2aa52fd16b4dfd52d23ce7fe62d093ea45d7770"
    ),
    "research_universe_models.py": (
        "f5627aac31e19e34a91800a90400e4bc8a130ee93b89f5404240b20eb9cf87c4"
    ),
}


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
    if arm not in {"control", "variant"} or cost_text not in {"1", "2"}:
        raise ValueError(f"unexpected frozen artifact name: {name}")
    return period, arm, int(cost_text)


def _control_hashes(prereg: dict[str, Any]) -> dict[str, str]:
    """Normalize the prior preregistration's historical variant-labelled keys."""
    raw = prereg.get("control_hashes")
    if not isinstance(raw, dict) or len(raw) != 16:
        raise ValueError("exactly 16 corrected control hashes are required")
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
    if not isinstance(rows, list) or len(rows) != FULL_EVALUATION_COUNT:
        raise ValueError("frozen result set must contain exactly 32 evaluations")
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
            "frozen result set does not cover all 32 period/arm/cost cells"
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


def _prior_inputs(
    prior_audit: Path,
) -> tuple[PortfolioInput, PortfolioConfig, dict[str, Any], dict[str, Any]]:
    prior_audit = prior_audit.resolve()
    prereg_path, results_path, manifest_path = (
        prior_audit / "preregistration.json",
        prior_audit / "results.json",
        prior_audit / "hash-manifest.json",
    )
    verify_hashes(
        {
            prereg_path: PRIOR_PREREG_SHA256,
            results_path: PRIOR_RESULTS_SHA256,
            manifest_path: PRIOR_MANIFEST_SHA256,
        }
    )
    prereg = _load_json(prereg_path)
    results = _load_json(results_path)
    if (
        results.get("evaluations") is None
        or len(results["evaluations"]) != FULL_EVALUATION_COUNT
    ):
        raise ValueError("frozen result set must contain exactly 32 evaluations")
    manifest_paths = prereg.get("input_paths")
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
    expected = _control_hashes(prereg)
    for filename, digest in expected.items():
        verify_hashes({prior_audit / "simulations" / filename: digest})
    _verify_frozen_artifacts(prior_audit, source, base, prereg, results)
    return source, base, prereg, results


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


def preflight(prior_audit: Path) -> dict[str, Any]:
    """Run the stored-input checks without creating output or calling simulate."""
    source, base, prereg, results = _prior_inputs(prior_audit)
    return {
        "source": source,
        "base_config": base,
        "preregistration": prereg,
        "results": results,
        "evaluation_count": FULL_EVALUATION_COUNT,
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
                # Split cash uses the same FX observation as the engine's open.
                fx = next(
                    (
                        trade.fx_rate
                        for trade in trade_by_day[day]
                        if trade.symbol == symbol
                    ),
                    Decimal(1),
                )
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
        expected_fx = position.fx_rate
        _close(
            position.value_krw,
            Decimal(position.quantity) * position.local_close * expected_fx,
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
        "final_cash_krw": str(sim.equity[-1].cash_krw),
        "final_quantities": {
            position.symbol: position.quantity for position in sim.positions
        },
        "accounting_residual": str(accounting["residual"]),
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
    ordered = sorted(returns)
    median = (
        ordered[len(ordered) // 2]
        if len(ordered) % 2
        else (ordered[len(ordered) // 2 - 1] + ordered[len(ordered) // 2]) / 2
    )
    return {
        "fold_return_delta_median_pp": str(median),
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


def _run_experiment_inner(
    prior_audit: Path,
    engine_source: Path,
    output_dir: Path,
    *,
    allow_historical_execution: bool = False,
    clock: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    """Run only after explicit approval; all preflight is read-only."""
    _empty_output(output_dir)
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
    variant = _load_copy(variant_path, "held_band_cost3_variant_engine")
    deadline = clock() + DEADLINE_SECONDS
    global _ACTIVE_DEADLINE
    _ACTIVE_DEADLINE = _arm_deadline(DEADLINE_SECONDS)
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
            "bands": ["0.02", "0.04"],
            "cost_multipliers": [1, 2, 3],
            "periods": periods,
            "evaluation_count": EVALUATION_CAP,
            "full_replay_count": FULL_EVALUATION_COUNT,
            "cost3_count": COST3_EVALUATION_COUNT,
            "cost3_rates": {
                "fee": str(RATE_3X),
                "slippage": str(RATE_3X),
                "fx_spread": str(RATE_3X),
            },
            "source_run_id": prior_results.get("source_run_id"),
            "point_in_time_verified": False,
            "automatic_trading_eligible": False,
        },
    )
    rows: list[dict[str, Any]] = []
    simulations: dict[tuple[str, str, int], PortfolioSimulation] = {}
    for phase, costs in (("full", FULL_COSTS), ("cost3", (COST3,))):
        for arm, band in (("control", "0.02"), ("variant", "0.04")):
            for period in periods:
                for cost in costs:
                    if len(ledger) >= EVALUATION_CAP:
                        raise RuntimeError("evaluation cap exceeded")
                    if clock() >= deadline:
                        raise TimeoutError(
                            "execution deadline exceeded before simulation"
                        )
                    ledger.append(
                        {
                            "index": len(ledger),
                            "phase": phase,
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
                    config = _config(base, band, cost)
                    sim = _run_call(variant.simulate, source, candidate, period, config)
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
                    if phase == "full":
                        expected_name = f"{period['name']}-{arm}_c{cost}.json"
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
    if len(rows) != EVALUATION_CAP:
        raise RuntimeError("runner did not produce exactly 48 evaluations")
    for row in rows:
        if row["cost_multiplier"] != COST3:
            continue
        period, arm = row["period"], row["arm"]
        c1 = simulations[(period, arm, 1)]
        row["fixed_cost3_net_pnl_krw"] = str(
            c1.metrics.final_equity_krw
            - c1.metrics.initial_equity_krw
            - Decimal(2) * (c1.metrics.transaction_cost_krw + c1.metrics.fx_cost_krw)
        )
        row["actual_minus_fixed_cost3_krw"] = str(
            (
                simulations[(period, arm, COST3)].metrics.final_equity_krw
                - simulations[(period, arm, COST3)].metrics.initial_equity_krw
            )
            - Decimal(row["fixed_cost3_net_pnl_krw"])
        )
        c1_row = next(
            item
            for item in rows
            if item["period"] == period
            and item["arm"] == arm
            and item["cost_multiplier"] == 1
        )
        row["cash_delta_vs_c1_krw"] = str(
            Decimal(row["final_cash_krw"]) - Decimal(c1_row["final_cash_krw"])
        )
    pairs: list[dict[str, Any]] = []
    for period in periods:
        for cost in (*FULL_COSTS, COST3):
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
        "cost3_count": COST3_EVALUATION_COUNT,
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
