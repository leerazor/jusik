from __future__ import annotations

import argparse
import csv
import hashlib
import inspect
import io
import json
import os
import statistics
import sys
from datetime import UTC, date, datetime, time
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field, field_validator

from jusik.research_external_models import ExternalFeatureSnapshot
from jusik.research_models import DailyBar
from jusik.research_portfolio import DEFAULT_REPORT_DIR
from jusik.research_portfolio_engine import candidates, simulate, union_close_dates
from jusik.research_portfolio_models import (
    PortfolioCandidate,
    PortfolioConfig,
    PortfolioInput,
    PortfolioMetrics,
    PortfolioRunResult,
    PortfolioSimulation,
)
from jusik.research_universe_models import OfflineResearchSnapshot

OosRole = Literal[
    "selected_base",
    "selected_cost_2x",
    "equal_baseline",
    "fixed_base",
    "fixed_cost_2x",
    "signal_window_15",
    "signal_window_25",
    "volatility_window_45",
    "volatility_window_75",
]

SOURCE_RUN_ID = "c94690f0ee13f01b1810ac0368e84fdcaeb1c1bbe7f396985d04dd3634b5ead0"
SOURCE_MANIFEST_SHA256 = (
    "1a2934466efa12c09d08e7792b1a5e4b7c0c880d2aaabab9b25919bd0ec5c825"
)
SOURCE_RESULT_SHA256 = (
    "db7ff9f5108e9112a495e2c47f8abf21cde8870f375139930e44ec01056ee8ca"
)
DEFAULT_VALIDATION_REPORT_DIR = (
    Path.home() / ".local/share/jusik/research-validation-reports"
)
ARTIFACTS = (
    "result.json",
    "folds.csv",
    "validation.csv",
    "sensitivity.csv",
    "report.md",
)
SPECIFICATION = {
    "warmup_union_dates": 120,
    "selection_union_dates": 80,
    "oos_union_dates": 80,
    "step_union_dates": 80,
    "policy": "low_turnover_combined",
    "validation_candidates": 12,
    "fixed_candidate": "portfolio_inverse_volatility_fx_vix_v1",
    "cost_multiplier": 2,
    "sensitivity": {
        "signal_window": [15, 25],
        "volatility_window": [45, 75],
        "one_factor_at_a_time": True,
    },
    "maximum_simulations_per_fold": 21,
    "independent_fold_initialization": True,
}


class RobustnessMetric(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    total_return_pct: Decimal = Field(allow_inf_nan=False)
    max_drawdown_pct: Decimal = Field(ge=0, allow_inf_nan=False)
    trade_count: int = Field(ge=0)
    turnover_pct: Decimal = Field(ge=0, allow_inf_nan=False)
    transaction_cost_krw: Decimal = Field(ge=0, allow_inf_nan=False)
    fx_cost_krw: Decimal = Field(ge=0, allow_inf_nan=False)


class ValidationEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    fold: int = Field(gt=0)
    candidate: PortfolioCandidate
    complete: bool
    incomplete_reasons: list[str]
    metrics: RobustnessMetric


class OosEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    fold: int = Field(gt=0)
    role: OosRole
    candidate: PortfolioCandidate
    config_changes: dict[str, int]
    complete: bool
    incomplete_reasons: list[str]
    metrics: RobustnessMetric


class RobustnessFold(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    fold: int = Field(gt=0)
    selection_start: date
    selection_end: date
    oos_start: date
    oos_end: date
    status: Literal["completed", "failed"]
    failure_reason: str | None
    selected_candidate: PortfolioCandidate | None
    selected_before_oos: bool
    validation: list[ValidationEvaluation]
    oos: list[OosEvaluation]


class AggregateResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    role: str
    fold_count: int = Field(ge=0)
    median_return_pct: Decimal | None = Field(allow_inf_nan=False)
    worst_return_pct: Decimal | None = Field(allow_inf_nan=False)
    benchmark_beat_count: int = Field(ge=0)
    benchmark_beat_fraction: Decimal | None = Field(allow_inf_nan=False)
    zero_trade_fold_count: int = Field(ge=0)
    median_cost_drag_percentage_points: Decimal | None = Field(allow_inf_nan=False)


class PortfolioRobustnessResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_run_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    created_at: datetime
    source_manifest_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_result_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    code_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    specification_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    calculation_complete: bool
    fold_count: int = Field(ge=0)
    failed_fold_count: int = Field(ge=0)
    simulation_evaluation_count: int = Field(ge=0, le=147)
    union_date_count: int = Field(ge=0)
    unused_tail_start: date | None
    unused_tail_end: date | None
    unused_tail_count: int = Field(ge=0)
    folds: list[RobustnessFold]
    aggregates: list[AggregateResult]
    retrospective_reused_history: Literal[True] = True
    prospective_validation_eligible: Literal[False] = False
    automatic_promotion_eligible: Literal[False] = False
    limitations: list[str]
    artifacts: list[str]

    @field_validator("created_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("created_at must be timezone-aware.")
        return value.astimezone(UTC)


def _canonical(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _read(path: Path, maximum: int = 32 * 1024 * 1024) -> bytes:
    with path.open("rb") as source:
        body = source.read(maximum + 1)
    if len(body) > maximum:
        raise ValueError("Portfolio robustness source artifact too large.")
    return body


def _code_hash() -> str:
    digest = hashlib.sha256()
    for module in (
        sys.modules[__name__],
        sys.modules[PortfolioInput.__module__],
        sys.modules[simulate.__module__],
        sys.modules[ExternalFeatureSnapshot.__module__],
        sys.modules[DailyBar.__module__],
        sys.modules[OfflineResearchSnapshot.__module__],
    ):
        digest.update(inspect.getsource(module).encode())
    return digest.hexdigest()


def _metric(metrics: PortfolioMetrics) -> RobustnessMetric:
    return RobustnessMetric(
        total_return_pct=metrics.total_return_pct,
        max_drawdown_pct=metrics.max_drawdown_pct,
        trade_count=metrics.trade_count,
        turnover_pct=metrics.turnover_pct,
        transaction_cost_krw=metrics.transaction_cost_krw,
        fx_cost_krw=metrics.fx_cost_krw,
    )


def _truncate_source(source: PortfolioInput, end: date) -> PortfolioInput:
    snapshots = []
    for snapshot in source.instruments:
        instrument = snapshot.instruments[0]
        bars = [bar for bar in instrument.bars if bar.date <= end]
        dates = {bar.date for bar in bars}
        snapshots.append(
            snapshot.model_copy(
                update={
                    "requested_end": min(snapshot.requested_end, end),
                    "instruments": [instrument.model_copy(update={"bars": bars})],
                    "basis_actions": [
                        item for item in snapshot.basis_actions if item.date <= end
                    ],
                    "corporate_actions": [
                        item for item in snapshot.corporate_actions if item.date <= end
                    ],
                    "adjustment_factors": [
                        item
                        for item in snapshot.adjustment_factors
                        if item.date in dates
                    ],
                }
            )
        )
    external_cutoff = datetime.combine(end, time.max, UTC)
    external = source.external.model_copy(
        update={
            "observations": tuple(
                item
                for item in source.external.observations
                if item.available_at.astimezone(UTC) <= external_cutoff
                and item.observed_on <= end
            )
        }
    )
    return source.model_copy(update={"instruments": snapshots, "external": external})


def _stressed(config: PortfolioConfig) -> PortfolioConfig:
    return config.model_copy(
        update={
            "fee_rate": config.fee_rate * 2,
            "slippage_rate": config.slippage_rate * 2,
            "fx_spread_rate": config.fx_spread_rate * 2,
        }
    )


def fold_boundaries(
    dates: list[date],
) -> tuple[list[tuple[int, date, date, date, date]], list[date]]:
    folds: list[tuple[int, date, date, date, date]] = []
    cursor = cast(int, SPECIFICATION["warmup_union_dates"])
    width = cast(int, SPECIFICATION["selection_union_dates"])
    oos_width = cast(int, SPECIFICATION["oos_union_dates"])
    step = cast(int, SPECIFICATION["step_union_dates"])
    fold_number = 1
    consumed_end = cursor
    while cursor + width + oos_width <= len(dates):
        folds.append(
            (
                fold_number,
                dates[cursor],
                dates[cursor + width - 1],
                dates[cursor + width],
                dates[cursor + width + oos_width - 1],
            )
        )
        consumed_end = cursor + width + oos_width
        fold_number += 1
        cursor += step
    return folds, dates[consumed_end:]


def run_portfolio_robustness(
    source_run_id: str,
    source_report_dir: Path,
    report_dir: Path,
    *,
    created_at: datetime | None = None,
) -> PortfolioRobustnessResult:
    if source_run_id != SOURCE_RUN_ID:
        raise ValueError("Robustness source run is not the fixed baseline.")
    source_dir = source_report_dir / "portfolio-runs" / source_run_id
    manifest_raw = _read(source_dir / "manifest.json")
    result_raw = _read(source_dir / "result.json")
    if (
        _sha(manifest_raw) != SOURCE_MANIFEST_SHA256
        or _sha(result_raw) != SOURCE_RESULT_SHA256
    ):
        raise ValueError("Fixed portfolio source hash mismatch.")
    manifest = json.loads(manifest_raw)
    original = PortfolioRunResult.model_validate_json(result_raw)
    source = PortfolioInput.model_validate(manifest["frozen_input"])
    if original.run_id != source_run_id or manifest.get("run_id") != source_run_id:
        raise ValueError("Fixed portfolio source identity mismatch.")
    config = original.config
    _validate_fixed_config(config)
    dates = [day for day in union_close_dates(source) if day <= original.harmonized_end]
    folds_spec, tail = fold_boundaries(dates)
    code_hash = _code_hash()
    specification_hash = _sha(_canonical(SPECIFICATION).encode())
    identity: dict[str, object] = {
        "source_run_id": source_run_id,
        "source_manifest_sha256": _sha(manifest_raw),
        "source_result_sha256": _sha(result_raw),
        "code_sha256": code_hash,
        "specification": SPECIFICATION,
        "specification_sha256": specification_hash,
    }
    run_id = _sha(_canonical(identity).encode())
    output_dir = report_dir / "portfolio-robustness-runs" / run_id
    if output_dir.exists():
        return _read_existing(output_dir, identity)
    fixed = PortfolioCandidate(
        id="portfolio_inverse_volatility_fx_vix_v1",
        method="inverse_volatility",
        gate="fx_vix",
    )
    equal = PortfolioCandidate(
        id="portfolio_equal_none_v1", method="equal", gate="none"
    )
    cache: dict[str, PortfolioSimulation] = {}
    evaluations = 0

    def evaluate(
        input_source: PortfolioInput,
        candidate: PortfolioCandidate,
        start: date,
        end: date,
        configured: PortfolioConfig,
    ) -> PortfolioSimulation:
        nonlocal evaluations
        key = _canonical(
            {
                "source_end": max(
                    bar.date
                    for item in input_source.instruments
                    for bar in item.instruments[0].bars
                ),
                "candidate": candidate.model_dump(mode="json"),
                "start": start,
                "end": end,
                "config": configured.model_dump(mode="json"),
            }
        )
        if key not in cache:
            cache[key] = simulate(
                input_source, candidate, start, end, configured, "low_turnover_combined"
            )
        evaluations += 1
        if evaluations > 147:
            raise ValueError("Robustness simulation budget exceeded.")
        return cache[key]

    folds: list[RobustnessFold] = []
    for number, selection_start, selection_end, oos_start, oos_end in folds_spec:
        selection_source = _truncate_source(source, selection_end)
        validation = []
        simulations: list[tuple[PortfolioCandidate, PortfolioSimulation]] = []
        for candidate in candidates():
            simulation = evaluate(
                selection_source, candidate, selection_start, selection_end, config
            )
            simulations.append((candidate, simulation))
            validation.append(
                ValidationEvaluation(
                    fold=number,
                    candidate=candidate,
                    complete=simulation.complete,
                    incomplete_reasons=simulation.incomplete_reasons,
                    metrics=_metric(simulation.metrics),
                )
            )
        complete = [
            (candidate, simulation)
            for candidate, simulation in simulations
            if simulation.complete
        ]
        if not complete:
            folds.append(
                RobustnessFold(
                    fold=number,
                    selection_start=selection_start,
                    selection_end=selection_end,
                    oos_start=oos_start,
                    oos_end=oos_end,
                    status="failed",
                    failure_reason="no_complete_validation_candidate",
                    selected_candidate=None,
                    selected_before_oos=True,
                    validation=validation,
                    oos=[],
                )
            )
            continue
        winner = sorted(
            complete,
            key=lambda row: (
                -row[1].metrics.total_return_pct,
                row[1].metrics.max_drawdown_pct,
                row[1].metrics.turnover_pct,
                row[0].id,
            ),
        )[0][0]
        scenarios: list[
            tuple[OosRole, PortfolioCandidate, PortfolioConfig, dict[str, int]]
        ] = [
            ("selected_base", winner, config, {}),
            ("selected_cost_2x", winner, _stressed(config), {}),
            ("equal_baseline", equal, config, {}),
            ("fixed_base", fixed, config, {}),
            ("fixed_cost_2x", fixed, _stressed(config), {}),
            (
                "signal_window_15",
                fixed,
                config.model_copy(update={"signal_window": 15}),
                {"signal_window": 15},
            ),
            (
                "signal_window_25",
                fixed,
                config.model_copy(update={"signal_window": 25}),
                {"signal_window": 25},
            ),
            (
                "volatility_window_45",
                fixed,
                config.model_copy(update={"volatility_window": 45}),
                {"volatility_window": 45},
            ),
            (
                "volatility_window_75",
                fixed,
                config.model_copy(update={"volatility_window": 75}),
                {"volatility_window": 75},
            ),
        ]
        oos = []
        for role, candidate, configured, changes in scenarios:
            simulation = evaluate(source, candidate, oos_start, oos_end, configured)
            oos.append(
                OosEvaluation(
                    fold=number,
                    role=role,
                    candidate=candidate,
                    config_changes=changes,
                    complete=simulation.complete,
                    incomplete_reasons=simulation.incomplete_reasons,
                    metrics=_metric(simulation.metrics),
                )
            )
        incomplete_roles = [item.role for item in oos if not item.complete]
        incomplete_reasons = sorted(
            {
                reason
                for item in oos
                if not item.complete
                for reason in item.incomplete_reasons
            }
        )
        fold_complete = not incomplete_roles
        folds.append(
            RobustnessFold(
                fold=number,
                selection_start=selection_start,
                selection_end=selection_end,
                oos_start=oos_start,
                oos_end=oos_end,
                status="completed" if fold_complete else "failed",
                failure_reason=(
                    None
                    if fold_complete
                    else "oos_incomplete:"
                    + ",".join(incomplete_reasons or incomplete_roles)
                ),
                selected_candidate=winner,
                selected_before_oos=True,
                validation=validation,
                oos=oos,
            )
        )
    aggregates = _aggregates(folds)
    result = PortfolioRobustnessResult(
        run_id=run_id,
        source_run_id=source_run_id,
        created_at=(created_at or datetime.now(UTC)).astimezone(UTC),
        source_manifest_sha256=_sha(manifest_raw),
        source_result_sha256=_sha(result_raw),
        code_sha256=code_hash,
        specification_sha256=specification_hash,
        calculation_complete=all(
            fold.status == "completed" and all(item.complete for item in fold.oos)
            for fold in folds
        ),
        fold_count=len(folds),
        failed_fold_count=sum(fold.status == "failed" for fold in folds),
        simulation_evaluation_count=evaluations,
        union_date_count=len(dates),
        unused_tail_start=tail[0] if tail else None,
        unused_tail_end=tail[-1] if tail else None,
        unused_tail_count=len(tail),
        folds=folds,
        aggregates=aggregates,
        limitations=[
            "각 fold는 현금 1억원에서 독립 시작하며 수익률을 복리 연결하지 않습니다.",
            "반복 사용한 과거 자료의 후향 검증이며 새로운 깨끗한 holdout이 아닙니다.",
            "원본 universe의 생존편향·배당·상장 시점과 자료 한계를 그대로 유지합니다.",
            "민감도 결과로 후보나 파라미터를 다시 선택하지 않습니다.",
        ],
        artifacts=list(ARTIFACTS),
    )
    _write(report_dir, output_dir, result, identity)
    return result


def _validate_fixed_config(config: PortfolioConfig) -> None:
    expected = {
        "initial_cash_krw": Decimal("100000000"),
        "symbol_cap": Decimal("0.20"),
        "gross_cap": Decimal("0.60"),
        "leveraged_etf_cap": Decimal("0.20"),
        "drawdown_limit": Decimal("0.10"),
        "low_turnover_weeks": 4,
        "signal_window": 20,
        "volatility_window": 60,
    }
    for name, value in expected.items():
        if getattr(config, name) != value:
            raise ValueError(f"Fixed portfolio config mismatch: {name}")


def _aggregates(folds: list[RobustnessFold]) -> list[AggregateResult]:
    result = []
    aggregate_roles: tuple[OosRole, OosRole] = ("selected_base", "fixed_base")
    for role in aggregate_roles:
        stress_role: OosRole = (
            "selected_cost_2x" if role == "selected_base" else "fixed_cost_2x"
        )
        comparable: list[tuple[OosEvaluation, OosEvaluation, OosEvaluation]] = []
        for fold in folds:
            by_role = {item.role: item for item in fold.oos}
            row = by_role.get(role)
            equal_row = by_role.get("equal_baseline")
            stress_row = by_role.get(stress_role)
            if (
                fold.status == "completed"
                and row is not None
                and equal_row is not None
                and stress_row is not None
                and row.complete
                and equal_row.complete
                and stress_row.complete
            ):
                comparable.append((row, equal_row, stress_row))
        rows = [row for row, _equal, _stress in comparable]
        returns = [item.metrics.total_return_pct for item in rows]
        beat = sum(
            item.metrics.total_return_pct > equal.metrics.total_return_pct
            for item, equal, _stress in comparable
        )
        drags = [
            item.metrics.total_return_pct - stress.metrics.total_return_pct
            for item, _equal, stress in comparable
        ]
        with localcontext() as context:
            context.prec = 40
            fraction = Decimal(beat) / Decimal(len(rows)) if rows else None
        result.append(
            AggregateResult(
                role=role,
                fold_count=len(rows),
                median_return_pct=statistics.median(returns) if returns else None,
                worst_return_pct=min(returns) if returns else None,
                benchmark_beat_count=beat,
                benchmark_beat_fraction=fraction,
                zero_trade_fold_count=sum(
                    item.metrics.trade_count == 0 for item in rows
                ),
                median_cost_drag_percentage_points=statistics.median(drags)
                if drags
                else None,
            )
        )
    return result


def _csv(rows: list[dict[str, object]]) -> str:
    if not rows:
        return ""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def _write(
    report_dir: Path,
    output_dir: Path,
    result: PortfolioRobustnessResult,
    identity: dict[str, object],
) -> None:
    temporary = output_dir.with_name(f".{output_dir.name}.{os.getpid()}.tmp")
    temporary.mkdir(parents=True, exist_ok=False)
    try:
        validation = [
            item.model_dump(mode="json")
            | {
                "candidate": item.candidate.id,
                "incomplete_reasons": "|".join(item.incomplete_reasons),
            }
            for fold in result.folds
            for item in fold.validation
        ]
        oos = [item for fold in result.folds for item in fold.oos]
        folds_rows = [
            {
                "fold": fold.fold,
                "selection_start": fold.selection_start,
                "selection_end": fold.selection_end,
                "oos_start": fold.oos_start,
                "oos_end": fold.oos_end,
                "status": fold.status,
                "selected_candidate": fold.selected_candidate.id
                if fold.selected_candidate
                else "",
                **{
                    f"{item.role}_{field}": getattr(item.metrics, field)
                    for item in fold.oos
                    if item.role
                    in {
                        "selected_base",
                        "selected_cost_2x",
                        "equal_baseline",
                        "fixed_base",
                        "fixed_cost_2x",
                    }
                    for field in (
                        "total_return_pct",
                        "max_drawdown_pct",
                        "trade_count",
                        "turnover_pct",
                    )
                },
            }
            for fold in result.folds
        ]
        sensitivity = [
            item.model_dump(mode="json")
            | {
                "candidate": item.candidate.id,
                "config_changes": _canonical(item.config_changes),
                "incomplete_reasons": "|".join(item.incomplete_reasons),
            }
            for item in oos
            if item.role.startswith(("signal_", "volatility_"))
        ]
        contents = {
            "result.json": result.model_dump_json(indent=2) + "\n",
            "folds.csv": _csv(folds_rows),
            "validation.csv": _csv(validation),
            "sensitivity.csv": _csv(sensitivity),
            "report.md": (
                "# 포트폴리오 rolling robustness\n\n"
                f"- 완전 fold: {result.fold_count - result.failed_fold_count}/"
                f"{result.fold_count}\n"
                f"- 논리 simulation 평가: {result.simulation_evaluation_count}\n"
                f"- 미사용 tail: {result.unused_tail_start}–"
                f"{result.unused_tail_end} ({result.unused_tail_count}일)\n\n"
                "각 fold는 독립 초기화했으며 결과를 복리 연결하지 않습니다. "
                "반복 사용한 과거 자료의 후향 검증이고 자동 승격에 사용하지 "
                "않습니다.\n"
            ),
        }
        hashes = {}
        for name, content in contents.items():
            raw = content.encode()
            (temporary / name).write_bytes(raw)
            hashes[name] = _sha(raw)
        (temporary / "manifest.json").write_text(
            _canonical(identity | {"run_id": result.run_id, "artifacts": hashes})
            + "\n",
            encoding="utf-8",
        )
        output_dir.parent.mkdir(parents=True, exist_ok=True)
        os.replace(temporary, output_dir)
        pointer = report_dir / "portfolio-robustness-latest.json"
        pointer_temp = pointer.with_suffix(".tmp")
        pointer_temp.write_text(
            _canonical({"run_id": result.run_id}) + "\n", encoding="utf-8"
        )
        os.replace(pointer_temp, pointer)
    except Exception:
        if temporary.exists():
            for child in temporary.iterdir():
                child.unlink()
            temporary.rmdir()
        raise


def _read_existing(
    output_dir: Path, identity: dict[str, object] | None = None
) -> PortfolioRobustnessResult:
    manifest = json.loads(_read(output_dir / "manifest.json", 1024 * 1024))
    expected = {
        "source_run_id",
        "source_manifest_sha256",
        "source_result_sha256",
        "code_sha256",
        "specification",
        "specification_sha256",
        "run_id",
        "artifacts",
    }
    if (
        not isinstance(manifest, dict)
        or set(manifest) != expected
        or manifest.get("run_id") != output_dir.name
    ):
        raise ValueError("Invalid robustness manifest.")
    stored_identity = {key: manifest[key] for key in expected - {"run_id", "artifacts"}}
    if _sha(_canonical(stored_identity).encode()) != output_dir.name:
        raise ValueError("Robustness identity hash mismatch.")
    if identity is not None and stored_identity != identity:
        raise ValueError("Robustness identity mismatch.")
    hashes = manifest.get("artifacts")
    if not isinstance(hashes, dict) or set(hashes) != set(ARTIFACTS):
        raise ValueError("Invalid robustness artifact index.")
    for name, digest in hashes.items():
        if not isinstance(digest, str) or _sha(_read(output_dir / name)) != digest:
            raise ValueError("Robustness artifact hash mismatch.")
    result = PortfolioRobustnessResult.model_validate_json(
        _read(output_dir / "result.json")
    )
    if result.run_id != output_dir.name:
        raise ValueError("Robustness result identity mismatch.")
    result_identity = {
        "source_run_id": result.source_run_id,
        "source_manifest_sha256": result.source_manifest_sha256,
        "source_result_sha256": result.source_result_sha256,
        "code_sha256": result.code_sha256,
        "specification": manifest["specification"],
        "specification_sha256": result.specification_sha256,
    }
    if result_identity != stored_identity:
        raise ValueError("Robustness result identity mismatch.")
    return result


class PortfolioRobustnessRepository:
    def __init__(self, report_dir: Path = DEFAULT_VALIDATION_REPORT_DIR) -> None:
        self.report_dir = report_dir

    def latest(self) -> PortfolioRobustnessResult | None:
        pointer = self.report_dir / "portfolio-robustness-latest.json"
        if not pointer.is_file():
            return None
        run_id = json.loads(_read(pointer, 1024))["run_id"]
        if (
            not isinstance(run_id, str)
            or len(run_id) != 64
            or any(character not in "0123456789abcdef" for character in run_id)
        ):
            raise ValueError("Invalid robustness pointer.")
        return _read_existing(self.report_dir / "portfolio-robustness-runs" / run_id)

    def artifact(self, run_id: str, name: str) -> Path:
        if (
            len(run_id) != 64
            or any(character not in "0123456789abcdef" for character in run_id)
            or name not in (*ARTIFACTS, "manifest.json")
        ):
            raise ValueError("Invalid robustness artifact.")
        output_dir = self.report_dir / "portfolio-robustness-runs" / run_id
        _read_existing(output_dir)
        return output_dir / name


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build fixed portfolio robustness evidence"
    )
    parser.add_argument("--source-run-id", default=SOURCE_RUN_ID)
    parser.add_argument("--source-report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument(
        "--report-dir", type=Path, default=DEFAULT_VALIDATION_REPORT_DIR
    )
    arguments = parser.parse_args()
    try:
        result = run_portfolio_robustness(
            arguments.source_run_id, arguments.source_report_dir, arguments.report_dir
        )
    except (OSError, ValueError):
        print("portfolio robustness failed", file=sys.stderr)
        return 1
    print(
        _canonical(
            {
                "run_id": result.run_id,
                "fold_count": result.fold_count,
                "calculation_complete": result.calculation_complete,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
