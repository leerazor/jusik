"""Run the pre-registered low-cash, low-turnover portfolio experiment offline.

The request contains only immutable paths and their SHA-256 digests.  The
experiment copies the corrected-entry engine into the fresh audit directory,
and instruments that copy's nested ``equity`` function for actual NAV, cash,
and leveraged-position observations.  It never changes the product engine.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from types import ModuleType
from typing import Final, cast

from pydantic import BaseModel, ConfigDict, ValidationError

from jusik.research_experiment_guard import verify_hashes
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

RUN_ID: Final = "portfolio-low-cash-low-turnover-v1"
INITIAL_CAPITAL: Final = Decimal("100000000")
BASE_RATE: Final = Decimal("0.001")
LEVERAGED_CAP: Final = Decimal("0.20")
LEVERAGED_SYMBOLS: Final = frozenset({"SOXL", "TQQQ"})
LEVERAGE_TOLERANCE_PP: Final = Decimal("0.00000001")
GRID_RUN_COUNT: Final = 128
FINAL_RUN_CAP: Final = 12
OBSERVER_PARITY_COUNT: Final = 2

DEV_PERIODS: Final = (
    ("dev1", "2023-09-13", "2024-09-12"),
    ("dev2", "2024-09-13", "2025-09-12"),
)
HELDOUT_PERIODS: Final = (
    ("final", "2025-09-13", "2026-09-11"),
    ("continuous", "2023-09-13", "2026-09-11"),
)
PROFILE_GRID: Final = (
    (Decimal("0.60"), Decimal("0.10")),
    (Decimal("0.80"), Decimal("0.20")),
    (Decimal("0.95"), Decimal("0.20")),
    (Decimal("0.95"), Decimal("0.30")),
)
CADENCE_GRID: Final = (4, 8)
BAND_GRID: Final = (Decimal("0.02"), Decimal("0.04"))
DRAWDOWN_GRID: Final = (Decimal("0.10"), Decimal("0.20"))


class ExperimentRequest(BaseModel):
    """The deliberately closed request contract for a run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_path: str
    source_sha256: str
    engine_path: str
    engine_sha256: str


@dataclass(frozen=True)
class EquityObservation:
    at: datetime
    nav_krw: Decimal
    cash_krw: Decimal
    position_values_krw: dict[str, Decimal]

    @property
    def leverage_value_krw(self) -> Decimal:
        return sum(
            (
                value
                for symbol, value in self.position_values_krw.items()
                if symbol in LEVERAGED_SYMBOLS
            ),
            Decimal(0),
        )


Observer = Callable[[datetime, Decimal, Decimal, dict[str, Decimal]], None]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_exclusive(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, default=str)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def _write_bytes_exclusive(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def _empty_output(path: Path) -> None:
    if path.is_symlink() or path.exists():
        raise ValueError("output directory must be new and not a symlink")
    path.mkdir(parents=True)


def _strict_json(body: bytes, label: str) -> object:
    def reject_constant(value: str) -> object:
        raise ValueError(f"non-finite JSON constant is forbidden in {label}: {value}")

    def reject_duplicate(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key in {label}: {key}")
            result[key] = value
        return result

    try:
        return json.loads(
            body.decode("utf-8"),
            parse_constant=reject_constant,
            object_pairs_hook=reject_duplicate,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid JSON: {label}") from error


def _digest(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")
    return value


def load_request(path: Path) -> ExperimentRequest:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"request is not a regular file: {path}")
    raw = _strict_json(path.read_bytes(), str(path))
    if not isinstance(raw, dict):
        raise ValueError("request must be an object")
    try:
        request = ExperimentRequest.model_validate(raw)
    except ValidationError as error:
        raise ValueError(
            "request schema is exactly source/engine path and hash"
        ) from error
    _digest(request.source_sha256, "source_sha256")
    _digest(request.engine_sha256, "engine_sha256")
    if not request.source_path or not request.engine_path:
        raise ValueError("source_path and engine_path must not be empty")
    return request


def _regular_hashed_file(path: Path, expected: str, label: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{label} is not a regular file: {path}")
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != expected:
        raise ValueError(f"{label} hash mismatch: {path}")
    return body


def _load_source(request: ExperimentRequest) -> PortfolioInput:
    path = Path(request.source_path)
    body = _regular_hashed_file(path, request.source_sha256, "source")
    raw = _strict_json(body, str(path))
    try:
        source = PortfolioInput.model_validate(raw)
    except (ValidationError, ValueError) as error:
        raise ValueError("source is not a valid PortfolioInput JSON") from error
    for snapshot in source.instruments:
        bars = [bar.date for bar in snapshot.instruments[0].bars]
        if len(bars) != len(set(bars)):
            raise ValueError("source contains duplicate price dates")
    for observation in source.external.observations:
        if observation.available_at.tzinfo is None:
            raise ValueError("source contains a naive external timestamp")
        if not observation.value.is_finite():
            raise ValueError("source contains a non-finite external value")
    return source


def _profile_id(
    gross: Decimal,
    volatility_target: Decimal,
    cadence: int,
    band: Decimal,
    drawdown: Decimal,
) -> str:
    return (
        f"g{gross * 100:03.0f}_v{volatility_target * 100:03.0f}_"
        f"c{cadence}_b{band * 100:03.0f}_dd{drawdown * 100:03.0f}"
    )


def grid() -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "id": _profile_id(gross, target, cadence, band, drawdown),
            "gross_cap": gross,
            "volatility_target": target,
            "low_turnover_weeks": cadence,
            "low_turnover_band": band,
            "drawdown_limit": drawdown,
        }
        for gross, target in PROFILE_GRID
        for cadence in CADENCE_GRID
        for band in BAND_GRID
        for drawdown in DRAWDOWN_GRID
    )


def _config(profile: dict[str, object], cost: int) -> PortfolioConfig:
    if cost not in {1, 2}:
        raise ValueError("cost multiplier must be 1 or 2")
    config = PortfolioConfig(
        initial_cash_krw=INITIAL_CAPITAL,
        fee_rate=BASE_RATE * cost,
        slippage_rate=BASE_RATE * cost,
        fx_spread_rate=BASE_RATE * cost,
        gross_cap=cast(Decimal, profile["gross_cap"]),
        volatility_target=cast(Decimal, profile["volatility_target"]),
        low_turnover_weeks=cast(int, profile["low_turnover_weeks"]),
        low_turnover_band=cast(Decimal, profile["low_turnover_band"]),
        drawdown_limit=cast(Decimal, profile["drawdown_limit"]),
        symbol_cap=Decimal("0.20"),
        leveraged_etf_cap=LEVERAGED_CAP,
    )
    if (
        config.symbol_cap != Decimal("0.20")
        or config.leveraged_etf_cap != LEVERAGED_CAP
    ):
        raise ValueError("frozen symbol or leveraged ETF cap changed")
    return config


def _copy_observer_engine(variant_path: Path, output: Path) -> Path:
    observer_path = output / "observer_engine.py"
    body = variant_path.read_bytes()
    marker = b'LEVERAGED_ETFS = frozenset({"SOXL", "TQQQ"})\n'
    anchor = b"        return total\n"
    if body.count(marker) != 1 or body.count(anchor) != 1:
        raise ValueError("engine observer anchors are not unique")
    injected = marker + b"_EQUITY_OBSERVER = None\n"
    body = body.replace(marker, injected, 1)
    callback = (
        b"        if _EQUITY_OBSERVER is not None:\n"
        b"            _EQUITY_OBSERVER(\n"
        b"                at,\n"
        b"                total,\n"
        b"                cash,\n"
        b"                {\n"
        b"                    symbol: Decimal(quantity) * (open_prices or {}).get(\n"
        b"                        symbol, latest_local.get(symbol)\n"
        b"                    ) * fx_for(symbol, at)\n"
        b"                    for symbol, quantity in positions.items()\n"
        b"                    if quantity > 0\n"
        b"                },\n"
        b"            )\n"
        b"        return total\n"
    )
    body = body.replace(anchor, callback, 1)
    _write_bytes_exclusive(observer_path, body)
    return observer_path


def _observe(
    at: datetime,
    nav: Decimal,
    cash: Decimal,
    position_values: dict[str, Decimal],
    output: list[EquityObservation],
) -> None:
    output.append(
        EquityObservation(
            at=at,
            nav_krw=nav,
            cash_krw=cash,
            position_values_krw=dict(sorted(position_values.items())),
        )
    )


def _run_simulation(
    engine: ModuleType,
    source: PortfolioInput,
    candidate: PortfolioCandidate,
    period: tuple[str, str, str],
    config: PortfolioConfig,
    observer: bool,
) -> tuple[PortfolioSimulation, list[EquityObservation]]:
    observations: list[EquityObservation] = []
    if observer:
        if not hasattr(engine, "_EQUITY_OBSERVER"):
            raise RuntimeError("observer engine is not instrumented")
        setattr(
            engine,
            "_EQUITY_OBSERVER",
            lambda at, nav, cash, values: _observe(at, nav, cash, values, observations),
        )
    try:
        simulation = engine.simulate(
            source,
            candidate,
            date.fromisoformat(period[1]),
            date.fromisoformat(period[2]),
            config,
            "low_turnover_combined",
        )
    finally:
        if observer:
            setattr(engine, "_EQUITY_OBSERVER", None)
    return simulation, observations


def _same_simulation(left: PortfolioSimulation, right: PortfolioSimulation) -> bool:
    return left.model_dump(mode="json") == right.model_dump(mode="json")


def verify_observer_parity(off: PortfolioSimulation, on: PortfolioSimulation) -> None:
    if not _same_simulation(off, on):
        raise ValueError("observer changed PortfolioSimulation output")


def _verify_observations(
    simulation: PortfolioSimulation,
    observations: Sequence[EquityObservation],
    config: PortfolioConfig,
) -> None:
    if not observations:
        raise ValueError("simulation produced no equity observations")
    previous: datetime | None = None
    for observation in observations:
        if observation.at.tzinfo is None or observation.at.utcoffset() != UTC.utcoffset(
            observation.at
        ):
            raise ValueError("observer timestamps must be aware UTC")
        if previous is not None and observation.at < previous:
            raise ValueError("observer timestamps are not chronological")
        if not observation.nav_krw.is_finite() or not observation.cash_krw.is_finite():
            raise ValueError("observer NAV/cash must be finite")
        if observation.nav_krw < 0 or observation.cash_krw < 0:
            raise ValueError("observer NAV/cash must be non-negative")
        position_total = sum(observation.position_values_krw.values(), Decimal(0))
        if any(
            not value.is_finite() or value < 0
            for value in observation.position_values_krw.values()
        ):
            raise ValueError("observer position values must be finite and non-negative")
        if observation.nav_krw != observation.cash_krw + position_total:
            raise ValueError("observer NAV does not reconcile to cash and positions")
        previous = observation.at
    if simulation.metrics.initial_equity_krw != config.initial_cash_krw:
        raise ValueError("simulation initial capital mismatch")
    observed_by_time = {point.at: point for point in observations}
    for point in simulation.equity:
        observed = observed_by_time.get(point.at)
        if (
            observed is None
            or observed.nav_krw != point.equity_krw
            or observed.cash_krw != point.cash_krw
        ):
            raise ValueError("observer does not match serialized equity points")


def global_drawdown(
    observations: Sequence[EquityObservation], initial: Decimal = INITIAL_CAPITAL
) -> Decimal:
    """Global peak-to-trough DD over all observer calls, including initial capital."""

    peak = initial
    maximum = Decimal(0)
    for observation in observations:
        if observation.nav_krw < 0 or not observation.nav_krw.is_finite():
            raise ValueError("NAV must be finite and non-negative")
        peak = max(peak, observation.nav_krw)
        maximum = max(
            maximum, (peak - observation.nav_krw) / peak * 100 if peak else Decimal(0)
        )
    return maximum


def _quantile(values: Sequence[Decimal], fraction: Decimal) -> Decimal:
    if not values:
        return Decimal(0)
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def actual_metrics(
    simulation: PortfolioSimulation, observations: Sequence[EquityObservation]
) -> dict[str, object]:
    daily: dict[date, EquityObservation] = {}
    for observation in observations:
        daily[observation.at.date()] = observation
    daily_values = list(daily.values())
    cash_values = [observation.cash_krw for observation in daily_values]
    leverage_values = [
        observation.leverage_value_krw / observation.nav_krw * 100
        for observation in observations
        if observation.nav_krw
    ]
    violations = [
        {
            "at": observation.at.isoformat(),
            "leverage_pct": str(
                observation.leverage_value_krw / observation.nav_krw * 100
            ),
        }
        for observation in observations
        if observation.nav_krw
        and observation.leverage_value_krw / observation.nav_krw * 100
        > LEVERAGED_CAP * 100 + LEVERAGE_TOLERANCE_PP
    ]
    by_month: dict[str, set[date]] = defaultdict(set)
    for trade in simulation.trades:
        by_month[trade.executed_at.strftime("%Y-%m")].add(trade.executed_at.date())
    amounts = [trade.notional_krw for trade in simulation.trades]
    daily_nav = [observation.nav_krw for observation in daily_values]
    mean_nav = (
        sum(daily_nav, Decimal(0)) / Decimal(len(daily_nav))
        if daily_nav
        else Decimal(0)
    )
    annual_turnover = (
        sum(amounts, Decimal(0))
        / mean_nav
        * Decimal("365.25")
        / Decimal(len(daily_nav))
        * 100
        if mean_nav and daily_nav
        else Decimal(0)
    )
    cost_pct = (
        (simulation.metrics.transaction_cost_krw + simulation.metrics.fx_cost_krw)
        / simulation.metrics.initial_equity_krw
        * 100
    )
    return {
        "daily_cash_median_krw": _quantile(cash_values, Decimal("0.5")),
        "daily_cash_p90_krw": _quantile(cash_values, Decimal("0.9")),
        "global_drawdown_pct": global_drawdown(
            observations, simulation.metrics.initial_equity_krw
        ),
        "max_actual_leverage_pct": max(leverage_values, default=Decimal(0)),
        "leverage_violations": violations,
        "trade_days": len({trade.executed_at.date() for trade in simulation.trades}),
        "trade_days_by_month": {
            month: len(days) for month, days in sorted(by_month.items())
        },
        "annual_notional_turnover_pct": annual_turnover,
        "trade_amount_quantiles_krw": {
            key: _quantile(amounts, fraction)
            for key, fraction in (
                ("p0", Decimal(0)),
                ("p25", Decimal(".25")),
                ("p50", Decimal(".5")),
                ("p75", Decimal(".75")),
                ("p90", Decimal(".9")),
                ("p100", Decimal(1)),
            )
        },
        "net_price_return_pct": simulation.metrics.total_return_pct,
        "transaction_cost_krw": simulation.metrics.transaction_cost_krw,
        "fx_cost_krw": simulation.metrics.fx_cost_krw,
        "total_cost_krw": simulation.metrics.transaction_cost_krw
        + simulation.metrics.fx_cost_krw,
        "cost_pct_of_initial": cost_pct,
    }


def verify_accounting(
    simulation: PortfolioSimulation,
    observations: Sequence[EquityObservation],
    config: PortfolioConfig,
    source: PortfolioInput,
) -> None:
    """Apply the existing Decimal trade reconciliation plus observer checks."""

    _held_verify_accounting(
        simulation, 1 if config.fee_rate == BASE_RATE else 2, config, source
    )
    _verify_observations(simulation, observations, config)


def _observation_payload(observation: EquityObservation) -> dict[str, object]:
    return {
        "at": observation.at.isoformat(),
        "nav_krw": observation.nav_krw,
        "cash_krw": observation.cash_krw,
        "position_values_krw": observation.position_values_krw,
        "leverage_value_krw": observation.leverage_value_krw,
    }


def _mean_decimal(values: Sequence[Decimal]) -> Decimal:
    return sum(values, Decimal(0)) / Decimal(len(values)) if values else Decimal(0)


def _candidate_row(
    profile: dict[str, object],
    period: tuple[str, str, str],
    cost: int,
    simulation: PortfolioSimulation,
    observations: Sequence[EquityObservation],
    accounting_valid: bool,
) -> dict[str, object]:
    metrics = actual_metrics(simulation, observations)
    return {
        "candidate_id": profile["id"],
        "period": period[0],
        "start": period[1],
        "end": period[2],
        "cost_multiplier": cost,
        "gross_cap": profile["gross_cap"],
        "volatility_target": profile["volatility_target"],
        "cadence_weeks": profile["low_turnover_weeks"],
        "band": profile["low_turnover_band"],
        "drawdown_limit": profile["drawdown_limit"],
        "complete": simulation.complete,
        "accounting_valid": accounting_valid,
        "net_return_pct": simulation.metrics.total_return_pct,
        "engine_episode_drawdown_pct": simulation.metrics.max_drawdown_pct,
        "trade_count": simulation.metrics.trade_count,
        **metrics,
    }


def _as_float_free(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: _as_float_free(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_as_float_free(item) for item in value]
    return value


def _eligible(
    profile_id: str,
    rows: Sequence[dict[str, object]],
    baseline: dict[tuple[str, int], dict[str, object]],
) -> bool:
    candidate_rows = [row for row in rows if row["candidate_id"] == profile_id]
    if len(candidate_rows) != 4 or any(
        not row["complete"] or not row["accounting_valid"] for row in candidate_rows
    ):
        return False
    for row in candidate_rows:
        if cast(Decimal, row["global_drawdown_pct"]) >= Decimal("20"):
            return False
        if (
            cast(Decimal, row["max_actual_leverage_pct"])
            > Decimal("20") + LEVERAGE_TOLERANCE_PP
        ):
            return False
        key = (cast(str, row["period"]), cast(int, row["cost_multiplier"]))
        base = baseline[key]
        if cast(Decimal, row["daily_cash_median_krw"]) >= cast(
            Decimal, base["daily_cash_median_krw"]
        ):
            return False
        if cast(int, row["trade_days"]) > cast(int, base["trade_days"]):
            return False
    return True


def _freeze_grid() -> dict[str, object]:
    return {
        "grid_count": len(grid()),
        "profiles": [_as_float_free(profile) for profile in grid()],
        "dev_periods": DEV_PERIODS,
        "heldout_periods": HELDOUT_PERIODS,
        "cost_multipliers": (1, 2),
        "candidate": {"method": "inverse_volatility", "gate": "fx_vix"},
        "policy": "low_turnover_combined",
        "initial_capital_krw": str(INITIAL_CAPITAL),
        "symbol_cap": "0.20",
        "leveraged_etf_cap": str(LEVERAGED_CAP),
        "development_simulations": GRID_RUN_COUNT,
        "heldout_simulation_cap": FINAL_RUN_CAP,
        "observer_parity_runs": OBSERVER_PARITY_COUNT,
        "eligibility": {
            "global_drawdown_pct": "<20 including initial capital",
            "actual_leverage_pct": "<=20 + 0.00000001 pp",
            "daily_cash_median": "strictly lower than baseline per dev/cost",
            "trade_days": "<= baseline per dev/cost",
        },
        "retrospective_reused_data": True,
        "dividends_and_taxes_included": False,
        "global_drawdown_is_not_engine_episode_drawdown": True,
    }


def run(request_path: Path, output_dir: Path) -> dict[str, object]:
    _empty_output(output_dir)
    ledger: list[dict[str, object]] = []
    try:
        request = load_request(request_path)
        source = _load_source(request)
        engine_path = Path(request.engine_path)
        _regular_hashed_file(engine_path, request.engine_sha256, "engine")
        _write_exclusive(
            output_dir / "request.json",
            _strict_json(request_path.read_bytes(), str(request_path)),
        )
        _write_exclusive(
            output_dir / "preregistration.json",
            {
                "run_id": RUN_ID,
                "request_sha256": sha256(request_path),
                "source_sha256": request.source_sha256,
                "engine_sha256": request.engine_sha256,
                **_freeze_grid(),
            },
        )

        original_path, variant_path = _copy_engine(engine_path, output_dir)
        if sha256(original_path) != request.engine_sha256:
            raise ValueError("copied original engine hash mismatch")
        observer_path = _copy_observer_engine(variant_path, output_dir)
        corrected = _load_copy(variant_path, "low_cash_corrected_engine")
        observed_engine = _load_copy(observer_path, "low_cash_observer_engine")
        candidate_template = PortfolioCandidate(
            id="placeholder", method="inverse_volatility", gate="fx_vix"
        )
        rows: list[dict[str, object]] = []
        for profile in grid():
            candidate = candidate_template.model_copy(
                update={"id": cast(str, profile["id"])}
            )
            for period in DEV_PERIODS:
                for cost in (1, 2):
                    ledger.append(
                        {
                            "phase": "development",
                            "candidate_id": profile["id"],
                            "period": period[0],
                            "cost": cost,
                            "status": "started",
                        }
                    )
                    simulation, observations = _run_simulation(
                        corrected,
                        source,
                        candidate,
                        period,
                        _config(profile, cost),
                        True,
                    )
                    verify_accounting(
                        simulation, observations, _config(profile, cost), source
                    )
                    if not simulation.complete or simulation.incomplete_reasons:
                        raise RuntimeError(
                            "incomplete development simulation: "
                            f"{profile['id']} {period[0]} c{cost}"
                        )
                    artifact_name = f"{profile['id']}-{period[0]}-c{cost}"
                    _write_exclusive(
                        output_dir / "simulations" / f"{artifact_name}.json",
                        simulation.model_dump(mode="json"),
                    )
                    _write_exclusive(
                        output_dir / "observations" / f"{artifact_name}.json",
                        [
                            _observation_payload(observation)
                            for observation in observations
                        ],
                    )
                    row = _candidate_row(
                        profile, period, cost, simulation, observations, True
                    )
                    rows.append(row)
                    ledger[-1].update({"status": "saved", "artifact": artifact_name})

        baseline_id = cast(str, grid()[0]["id"])
        baseline = {
            (cast(str, row["period"]), cast(int, row["cost_multiplier"])): row
            for row in rows
            if row["candidate_id"] == baseline_id
        }
        eligible_ids = [
            cast(str, profile["id"])
            for profile in grid()
            if cast(str, profile["id"]) != baseline_id
            and _eligible(cast(str, profile["id"]), rows, baseline)
        ]
        ranking = sorted(
            (
                (
                    candidate_id,
                    _mean_decimal(
                        [
                            cast(Decimal, row["net_return_pct"])
                            for row in rows
                            if row["candidate_id"] == candidate_id
                        ]
                    ),
                )
                for candidate_id in eligible_ids
            ),
            key=lambda item: (-item[1], item[0]),
        )
        finalist_ids = [candidate_id for candidate_id, _score in ranking[:2]]
        _write_exclusive(
            output_dir / "finalist-freeze.json",
            {
                "run_id": RUN_ID,
                "baseline_id": baseline_id,
                "eligible_ids": eligible_ids,
                "finalist_ids": finalist_ids,
                "ranking_mean_dev_net_return_pct": [
                    {"candidate_id": candidate_id, "mean_net_return_pct": score}
                    for candidate_id, score in ranking
                ],
            },
        )

        final_ids = [baseline_id, *finalist_ids]
        profiles = {cast(str, profile["id"]): profile for profile in grid()}
        heldout_rows: list[dict[str, object]] = []
        for candidate_id in final_ids:
            profile = profiles[candidate_id]
            candidate = candidate_template.model_copy(update={"id": candidate_id})
            for period in HELDOUT_PERIODS:
                for cost in (1, 2):
                    simulation, observations = _run_simulation(
                        observed_engine,
                        source,
                        candidate,
                        period,
                        _config(profile, cost),
                        True,
                    )
                    verify_accounting(
                        simulation, observations, _config(profile, cost), source
                    )
                    if not simulation.complete or simulation.incomplete_reasons:
                        raise RuntimeError(
                            "incomplete heldout simulation: "
                            f"{candidate_id} {period[0]} c{cost}"
                        )
                    artifact_name = f"{candidate_id}-{period[0]}-c{cost}"
                    _write_exclusive(
                        output_dir / "simulations" / f"{artifact_name}.json",
                        simulation.model_dump(mode="json"),
                    )
                    _write_exclusive(
                        output_dir / "observations" / f"{artifact_name}.json",
                        [
                            _observation_payload(observation)
                            for observation in observations
                        ],
                    )
                    heldout_rows.append(
                        _candidate_row(
                            profile, period, cost, simulation, observations, True
                        )
                    )

        parity_period = DEV_PERIODS[0]
        baseline_profile = profiles[baseline_id]
        baseline_candidate = candidate_template.model_copy(update={"id": baseline_id})
        off, _off_observations = _run_simulation(
            corrected,
            source,
            baseline_candidate,
            parity_period,
            _config(baseline_profile, 1),
            False,
        )
        on, on_observations = _run_simulation(
            observed_engine,
            source,
            baseline_candidate,
            parity_period,
            _config(baseline_profile, 1),
            True,
        )
        verify_observer_parity(off, on)
        verify_accounting(on, on_observations, _config(baseline_profile, 1), source)
        parity = {
            "period": parity_period[0],
            "cost_multiplier": 1,
            "equal": True,
            "off_sha256": hashlib.sha256(
                json.dumps(off.model_dump(mode="json"), sort_keys=True).encode()
            ).hexdigest(),
            "on_sha256": hashlib.sha256(
                json.dumps(on.model_dump(mode="json"), sort_keys=True).encode()
            ).hexdigest(),
        }
        _write_exclusive(output_dir / "observer-parity.json", parity)
        verify_hashes(
            {
                Path(request.source_path): request.source_sha256,
                Path(request.engine_path): request.engine_sha256,
            }
        )
        all_rows = [*rows, *heldout_rows]
        result: dict[str, object] = {
            "run_id": RUN_ID,
            "development": rows,
            "heldout": heldout_rows,
            "evaluations": all_rows,
            "baseline_id": baseline_id,
            "eligible_ids": eligible_ids,
            "finalist_ids": finalist_ids,
            "negative_result": not bool(finalist_ids),
            "no_heldout_retuning": True,
            "development_simulation_count": len(rows),
            "heldout_simulation_count": len(heldout_rows),
            "observer_parity_runs": OBSERVER_PARITY_COUNT,
            "total_simulation_count": len(rows)
            + len(heldout_rows)
            + OBSERVER_PARITY_COUNT,
        }
        _write_exclusive(output_dir / "results.json", _as_float_free(result))
        fields = [
            "candidate_id",
            "period",
            "cost_multiplier",
            "complete",
            "accounting_valid",
            "net_return_pct",
            "daily_cash_median_krw",
            "daily_cash_p90_krw",
            "global_drawdown_pct",
            "max_actual_leverage_pct",
            "trade_days",
            "annual_notional_turnover_pct",
            "net_price_return_pct",
            "transaction_cost_krw",
            "fx_cost_krw",
        ]
        with (output_dir / "results.csv").open(
            "x", newline="", encoding="utf-8"
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for row in all_rows:
                writer.writerow(
                    {field: _as_float_free(row.get(field)) for field in fields}
                )
        report = [
            "# Low-cash low-turnover portfolio experiment",
            "",
            "This is retrospective reused data; dividends and taxes are excluded. "
            "Global DD uses every observer NAV and includes initial capital; it "
            "is not engine episode DD.",
            "",
            f"Development simulations: {len(rows)}/{GRID_RUN_COUNT}",
            f"Heldout simulations: {len(heldout_rows)}/{len(final_ids) * 4}",
            "Finalists frozen before heldout: "
            f"{', '.join(finalist_ids) if finalist_ids else 'none (negative result)'}",
            "",
            "No automatic promotion, PAPER activation, or future-performance "
            "guarantee is implied.",
        ]
        _write_exclusive(output_dir / "report.md", "\n".join(report) + "\n")
        verify_hashes(
            {
                Path(request.source_path): request.source_sha256,
                Path(request.engine_path): request.engine_sha256,
            }
        )
        _write_exclusive(
            output_dir / "hash-manifest.json",
            {
                "source_sha256": sha256(Path(request.source_path)),
                "engine_sha256": sha256(Path(request.engine_path)),
                "runner_sha256": sha256(Path(__file__)),
            },
        )
        return result
    except BaseException as error:
        if not (output_dir / "failure.json").exists():
            _write_exclusive(
                output_dir / "failure.json",
                {"run_id": RUN_ID, "error": repr(error), "ledger": ledger},
            )
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    result = run(args.request, args.output_dir)
    print(
        json.dumps(
            {
                "run_id": RUN_ID,
                "development_simulation_count": result["development_simulation_count"],
                "heldout_simulation_count": result["heldout_simulation_count"],
                "finalist_ids": result["finalist_ids"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
