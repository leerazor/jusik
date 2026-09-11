from __future__ import annotations

import argparse
import csv
import fcntl
import hashlib
import io
import json
import os
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from jusik.research_external_store import ExternalStore
from jusik.research_portfolio_engine import (
    candidates,
    cash_metrics,
    policy_diagnostics,
    simulate,
    union_close_dates,
)
from jusik.research_portfolio_models import (
    CandidateEvaluation,
    PortfolioCandidate,
    PortfolioConfig,
    PortfolioInput,
    PortfolioPolicy,
    PortfolioPolicyComparison,
    PortfolioPolicyExperiment,
    PortfolioRunResult,
    PortfolioRunStatus,
)
from jusik.research_universe_data import REGISTRY
from jusik.research_universe_store import UniverseInputStore

DEFAULT_INPUT_DB = Path.home() / ".local/share/jusik/research-universe.db"
DEFAULT_EXTERNAL_DB = Path.home() / ".local/share/jusik/research-external.db"
DEFAULT_REPORT_DIR = Path.home() / ".local/share/jusik/research-universe-reports"
ARTIFACT_NAMES = (
    "result.json",
    "report.md",
    "validation.csv",
    "equity.csv",
    "trades.csv",
    "weekly-targets.csv",
    "policy-comparison.csv",
    "policy-monthly.csv",
    "policy-events.csv",
)
STORED_ARTIFACT_NAMES = (*ARTIFACT_NAMES, "manifest.json")
POLICY_EXPERIMENT_SPEC = {
    "registered_at": "2026-09-09T22:29:27.639617+00:00",
    "reference_run_id": (
        "c719b58bcf3faa697e0d88a25989f88b76df672b19ba257abca35cc3117d0017"
    ),
    "reference_input_hash": (
        "85781ea5025796adb0d4f77c00c13654a795626412c7185cae2b680f470056ae"
    ),
    "candidate": {
        "id": "portfolio_inverse_volatility_fx_vix_v1",
        "method": "inverse_volatility",
        "gate": "fx_vix",
    },
    "policies": [
        "corrected_control",
        "reentry_only",
        "volatility_only",
        "combined",
        "low_turnover_combined",
    ],
    "initial_cash_krw": "100000000",
    "risk": {
        "symbol_cap": "0.20",
        "gross_cap": "0.60",
        "leveraged_cap": "0.20",
        "episode_drawdown_limit": "0.10",
        "lifetime_drawdown_never_reset": True,
    },
    "reentry": {
        "cooldown_days_after_complete_liquidation": 28,
        "weekly_recovery_confirmations": 2,
        "minimum_eligible_assets": 2,
        "requires_existing_gate": True,
        "next_scheduled_rebalance_only": True,
    },
    "volatility": {
        "window_returns": 60,
        "annualization_sessions": 252,
        "annual_risk_proxy_target": "0.10",
        "proxy": "sum(weight * asset_KRW_annualized_population_std)",
        "asof_utc_day_end": True,
        "no_future_fx": True,
        "missing_history": "incomplete",
    },
    "low_turnover": {
        "rebalance_every_weeks": 4,
        "anchor": "first Monday on/after evaluation start",
        "weight_band": "0.02",
        "zero_target_and_risk_exits_exempt": True,
    },
    "execution_correction": (
        "Retire each instruction after first valid opening attempt including sells, "
        "zero quantity and noops; no same-decision sell-to-buy reversal. Preserve "
        "missing valuation deferrals and unopened symbols."
    ),
    "cost_stress_multiplier": 2,
    "selection": (
        "Fixed archived candidate across all five policies; no reselection by reused "
        "evaluation performance. Existing12candidate validation may still run "
        "separately."
    ),
    "evidence": (
        "Retrospective reused historical evaluation, not prospective validation. "
        "No threshold retuning after results."
    ),
    "completion": (
        "Five base+stress comparisons, lifecycle and cadence diagnostics, safe "
        "web+CSV, "
        "meaningful tests and independent review; no broker orders."
    ),
}
POLICIES: tuple[PortfolioPolicy, ...] = (
    "corrected_control",
    "reentry_only",
    "volatility_only",
    "combined",
    "low_turnover_combined",
)


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode()).hexdigest()


def _code_hash() -> str:
    digest = hashlib.sha256()
    root = Path(__file__).parent
    for name in (
        "research_portfolio.py",
        "research_portfolio_engine.py",
        "research_portfolio_models.py",
    ):
        digest.update(name.encode())
        digest.update((root / name).read_bytes())
    return digest.hexdigest()


def load_portfolio_input(
    input_store: UniverseInputStore, external_store: ExternalStore
) -> PortfolioInput:
    ids: dict[str, str] = {}
    snapshots = []
    for instrument in REGISTRY:
        latest = input_store.load_latest(instrument.symbol)
        if latest is None:
            continue
        snapshot_id, _request, snapshot = latest
        ids[instrument.symbol] = snapshot_id
        snapshots.append(snapshot)
    missing = [item.symbol for item in REGISTRY if item.symbol not in ids]
    if missing:
        raise ValueError(f"Universe snapshots are missing: {', '.join(missing)}")
    return PortfolioInput(
        captured_at=max(snapshot.captured_at for snapshot in snapshots),
        stock_snapshot_ids=ids,
        instruments=snapshots,
        external=external_store.snapshot(),
        external_status=external_store.statuses(),
    )


class PortfolioRunRepository:
    def __init__(self, report_dir: Path) -> None:
        self.report_dir = report_dir
        self.runs_dir = report_dir / "portfolio-runs"

    def run_dir(self, run_id: str) -> Path:
        if len(run_id) != 64 or any(
            character not in "0123456789abcdef" for character in run_id
        ):
            raise ValueError("Invalid portfolio run id.")
        return self.runs_dir / run_id

    def read(self, run_id: str) -> PortfolioRunResult:
        run_dir = self.run_dir(run_id)
        resolved = run_dir.resolve()
        if resolved.parent != self.runs_dir.resolve() or run_dir.is_symlink():
            raise ValueError("Invalid portfolio run path.")
        path = resolved / "result.json"
        if path.is_symlink():
            raise ValueError("Invalid portfolio result path.")
        return PortfolioRunResult.model_validate_json(path.read_text(encoding="utf-8"))

    def latest(self) -> PortfolioRunResult | None:
        pointer = self.report_dir / "portfolio-latest.json"
        try:
            payload = json.loads(pointer.read_text(encoding="utf-8"))
            return self.read(str(payload["run_id"]))
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def status(self) -> PortfolioRunStatus:
        path = self.report_dir / "portfolio-status.json"
        try:
            return PortfolioRunStatus.model_validate_json(
                path.read_text(encoding="utf-8")
            )
        except (OSError, ValueError):
            return PortfolioRunStatus(status="idle")

    def save_status(self, status: PortfolioRunStatus) -> None:
        _atomic_write(
            self.report_dir / "portfolio-status.json",
            status.model_dump_json() + "\n",
        )

    def artifact_path(self, run_id: str, name: str) -> Path:
        if name not in ARTIFACT_NAMES:
            raise ValueError("Unknown portfolio artifact.")
        run_dir = self.run_dir(run_id)
        resolved_run_dir = run_dir.resolve()
        if resolved_run_dir.parent != self.runs_dir.resolve() or run_dir.is_symlink():
            raise ValueError("Invalid portfolio run path.")
        path = resolved_run_dir / name
        if not path.is_file() or path.is_symlink():
            raise FileNotFoundError(name)
        return path

    def record_failure(self, run_id: str, error: Exception) -> None:
        self.report_dir.mkdir(parents=True, exist_ok=True)
        failures = self.report_dir / "portfolio-failures"
        failures.mkdir(parents=True, exist_ok=True)
        payload = {
            "run_id": run_id,
            "failed_at": datetime.now(UTC).isoformat(),
            "error_type": type(error).__name__,
            "message": "Portfolio research failed safely.",
        }
        _atomic_write(failures / f"{run_id}.json", _canonical_json(payload) + "\n")


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, path)


def _markdown(result: PortfolioRunResult) -> str:
    heldout = result.heldout
    lines = [
        "# 통합 포트폴리오 연구",
        "",
        f"- 실행 ID: `{result.run_id}`",
        f"- 선택 정책: `{result.selected_candidate.id}`",
        f"- 검증: {result.validation_start}–{result.validation_end}",
        f"- 연속 보유평가: {result.heldout_start}–{result.heldout_end}",
        f"- 보유평가 수익률: {heldout.metrics.total_return_pct:.4f}%",
        f"- 최대 낙폭: {heldout.metrics.max_drawdown_pct:.4f}%",
        f"- 최종 평가액: {heldout.metrics.final_equity_krw:.0f} KRW",
        f"- 거래: {heldout.metrics.trade_count}건",
        f"- 거래비용: {heldout.metrics.transaction_cost_krw:.0f} KRW",
        f"- 환전비용: {heldout.metrics.fx_cost_krw:.0f} KRW",
        f"- 손실 제한 작동: {heldout.drawdown_latched_at or '없음'}",
        (
            "- 동일 비중 추세 기준 수익률: "
            f"{result.equal_baseline.metrics.total_return_pct:.4f}%"
        ),
        "",
        "## 검증 후보",
        "",
        "|후보|순수익률|최대 낙폭|회전율|완전성|",
        "|---|---:|---:|---:|---|",
    ]
    lines.extend(
        f"|{item.candidate.id}|{item.metrics.total_return_pct:.4f}%|"
        f"{item.metrics.max_drawdown_pct:.4f}%|{item.metrics.turnover_pct:.2f}%|"
        f"{'완전' if item.complete else '불완전'}|"
        for item in result.validation
    )
    lines.extend(
        [
            "",
            "## 외부 자료 수집 상태",
            "",
            *[
                (
                    f"- {item.source}: {item.status}, 최근 성공 "
                    f"{item.last_success_at or '없음'}"
                )
                for item in result.external_status
            ],
            "",
            "## 해석 경계",
            "",
            *[f"- {item}" for item in result.limitations],
        ]
    )
    if result.policy_experiment is not None:
        experiment = result.policy_experiment
        lines.extend(
            [
                "",
                "## 사전 고정 정책 비교",
                "",
                (
                    f"고정 후보 `{experiment.fixed_candidate.id}`를 보유평가 구간에서 "
                    "다섯 정책에 똑같이 적용했습니다. 결과로 정책을 고르거나 "
                    "임계값을 다시 맞추지 않았습니다."
                ),
                "",
                "|정책|수익률|최대 낙폭|비용 2배 수익률|거래|투자일|재진입|",
                "|---|---:|---:|---:|---:|---:|---:|",
                *[
                    (
                        f"|{comparison.policy}|"
                        f"{comparison.base.metrics.total_return_pct:.4f}%|"
                        f"{comparison.base.metrics.max_drawdown_pct:.4f}%|"
                        f"{comparison.cost_stress.metrics.total_return_pct:.4f}%|"
                        f"{comparison.base.metrics.trade_count}|"
                        f"{comparison.diagnostics.invested_days_pct:.2f}%|"
                        f"{comparison.diagnostics.reentry_count}|"
                    )
                    for comparison in experiment.comparisons
                ],
                "",
                *[f"- {item}" for item in experiment.limitations],
            ]
        )
    lines.extend(["", "이 결과는 자동매매에 사용할 수 없습니다."])
    return "\n".join(lines) + "\n"


def _csv_artifacts(result: PortfolioRunResult) -> dict[str, str]:
    outputs: dict[str, str] = {}
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(
        (
            "candidate_id",
            "method",
            "gate",
            "return_pct",
            "max_drawdown_pct",
            "turnover_pct",
            "complete",
        )
    )
    for evaluation in result.validation:
        writer.writerow(
            (
                evaluation.candidate.id,
                evaluation.candidate.method,
                evaluation.candidate.gate,
                evaluation.metrics.total_return_pct,
                evaluation.metrics.max_drawdown_pct,
                evaluation.metrics.turnover_pct,
                evaluation.complete,
            )
        )
    outputs["validation.csv"] = stream.getvalue()
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(("at", "equity_krw", "cash_krw", "drawdown_pct"))
    for point in result.heldout.equity:
        writer.writerow(
            (point.at.isoformat(), point.equity_krw, point.cash_krw, point.drawdown_pct)
        )
    outputs["equity.csv"] = stream.getvalue()
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(
        (
            "decided_at",
            "executed_at",
            "symbol",
            "side",
            "quantity",
            "local_price",
            "fx_rate",
            "notional_krw",
            "transaction_cost_krw",
            "fx_cost_krw",
        )
    )
    for trade in result.heldout.trades:
        writer.writerow(
            (
                trade.decided_at.isoformat(),
                trade.executed_at.isoformat(),
                trade.symbol,
                trade.side,
                trade.quantity,
                trade.local_price,
                trade.fx_rate,
                trade.notional_krw,
                trade.transaction_cost_krw,
                trade.fx_cost_krw,
            )
        )
    outputs["trades.csv"] = stream.getvalue()
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(
        ("decided_at", "symbol", "target_weight", "actual_weight_after_open")
    )
    for target in result.heldout.weekly_targets:
        writer.writerow(
            (
                target.decided_at.isoformat(),
                target.symbol,
                target.target_weight,
                target.actual_weight_after_open or "",
            )
        )
    outputs["weekly-targets.csv"] = stream.getvalue()
    if result.policy_experiment is not None:
        stream = io.StringIO()
        writer = csv.writer(stream)
        writer.writerow(
            (
                "policy",
                "return_pct",
                "max_drawdown_pct",
                "stress_return_pct",
                "stress_max_drawdown_pct",
                "trade_count",
                "turnover_pct",
                "trading_utc_days",
                "invested_days_pct",
                "active_month_trade_average",
                "active_month_trade_maximum",
                "exit_count",
                "reentry_count",
                "frequency_skip_count",
                "band_skip_count",
                "volatility_scale_event_count",
            )
        )
        for comparison in result.policy_experiment.comparisons:
            diagnostics = comparison.diagnostics
            writer.writerow(
                (
                    comparison.policy,
                    comparison.base.metrics.total_return_pct,
                    comparison.base.metrics.max_drawdown_pct,
                    comparison.cost_stress.metrics.total_return_pct,
                    comparison.cost_stress.metrics.max_drawdown_pct,
                    comparison.base.metrics.trade_count,
                    comparison.base.metrics.turnover_pct,
                    diagnostics.trading_utc_days,
                    diagnostics.invested_days_pct,
                    diagnostics.active_month_trade_average,
                    diagnostics.active_month_trade_maximum,
                    diagnostics.exit_count,
                    diagnostics.reentry_count,
                    diagnostics.frequency_skip_count,
                    diagnostics.band_skip_count,
                    diagnostics.volatility_scale_event_count,
                )
            )
        outputs["policy-comparison.csv"] = stream.getvalue()
        stream = io.StringIO()
        writer = csv.writer(stream)
        writer.writerow(("policy", "month", "trade_count", "turnover_pct", "active"))
        for comparison in result.policy_experiment.comparisons:
            for monthly in comparison.diagnostics.monthly:
                writer.writerow(
                    (
                        comparison.policy,
                        monthly.month,
                        monthly.trade_count,
                        monthly.turnover_pct,
                        monthly.active,
                    )
                )
        outputs["policy-monthly.csv"] = stream.getvalue()
        stream = io.StringIO()
        writer = csv.writer(stream)
        writer.writerow(("policy", "cost_scenario", "at", "kind", "detail", "value"))
        for comparison in result.policy_experiment.comparisons:
            for scenario, simulation in (
                ("base", comparison.base),
                ("2x", comparison.cost_stress),
            ):
                for event in simulation.policy_events:
                    writer.writerow(
                        (
                            comparison.policy,
                            scenario,
                            event.at.isoformat(),
                            event.kind,
                            event.detail,
                            event.value if event.value is not None else "",
                        )
                    )
        outputs["policy-events.csv"] = stream.getvalue()
    return outputs


def run_portfolio_research(
    source: PortfolioInput,
    report_dir: Path,
    config: PortfolioConfig | None = None,
) -> PortfolioRunResult:
    configured = config or PortfolioConfig()
    source_payload = source.model_dump(mode="json")
    input_hash = _hash(
        {
            "stock_snapshot_ids": source.stock_snapshot_ids,
            "instruments": [
                item.model_dump(mode="json") for item in source.instruments
            ],
            "external": source.external.semantic_payload(),
        }
    )
    code_hash = _code_hash()
    run_id = _hash(
        {
            "input_hash": input_hash,
            "config": configured.model_dump(mode="json"),
            "code_hash": code_hash,
        }
    )
    repository = PortfolioRunRepository(report_dir)
    run_dir = repository.run_dir(run_id)
    if run_dir.is_dir():
        result = repository.read(run_id)
        _atomic_write(
            report_dir / "portfolio-latest.json",
            _canonical_json({"run_id": result.run_id}) + "\n",
        )
        return result
    dates = union_close_dates(source)
    required = configured.warmup_sessions + configured.validation_sessions + 1
    if len(dates) < required:
        raise ValueError(
            f"Portfolio research needs at least {required} union sessions."
        )
    preparation_end = dates[configured.warmup_sessions - 1]
    validation_start = dates[configured.warmup_sessions]
    validation_end = dates[
        configured.warmup_sessions + configured.validation_sessions - 1
    ]
    heldout_start = dates[configured.warmup_sessions + configured.validation_sessions]
    heldout_end = min(snapshot.requested_end for snapshot in source.instruments)
    requested_start = min(snapshot.requested_start for snapshot in source.instruments)
    if heldout_start > heldout_end:
        raise ValueError("No held-out portfolio period remains after validation.")
    evaluations = []
    for candidate in candidates():
        simulation = simulate(
            source, candidate, validation_start, validation_end, configured
        )
        evaluations.append(
            CandidateEvaluation(
                candidate=candidate,
                metrics=simulation.metrics,
                complete=simulation.complete,
                incomplete_reasons=simulation.incomplete_reasons,
            )
        )
    eligible = [item for item in evaluations if item.complete]
    if not eligible:
        raise ValueError("All portfolio candidates have incomplete validation inputs.")
    selected = sorted(
        eligible,
        key=lambda item: (
            -item.metrics.total_return_pct,
            item.metrics.max_drawdown_pct,
            item.metrics.turnover_pct,
            item.candidate.id,
        ),
    )[0].candidate
    heldout = simulate(source, selected, heldout_start, heldout_end, configured)
    equal_baseline = simulate(
        source,
        PortfolioCandidate(id="portfolio_equal_none_v1", method="equal", gate="none"),
        heldout_start,
        heldout_end,
        configured,
    )
    stressed_config = configured.model_copy(
        update={
            "fee_rate": configured.fee_rate * 2,
            "slippage_rate": configured.slippage_rate * 2,
            "fx_spread_rate": configured.fx_spread_rate * 2,
        }
    )
    stressed = simulate(source, selected, heldout_start, heldout_end, stressed_config)
    fixed_candidate = PortfolioCandidate.model_validate(
        POLICY_EXPERIMENT_SPEC["candidate"]
    )
    policy_comparisons = []
    for policy in POLICIES:
        base = simulate(
            source,
            fixed_candidate,
            heldout_start,
            heldout_end,
            configured,
            policy,
        )
        cost_stress = simulate(
            source,
            fixed_candidate,
            heldout_start,
            heldout_end,
            stressed_config,
            policy,
        )
        policy_comparisons.append(
            PortfolioPolicyComparison(
                policy=policy,
                base=base,
                cost_stress=cost_stress,
                diagnostics=policy_diagnostics(base),
            )
        )
    policy_experiment = PortfolioPolicyExperiment(
        registered_at=datetime.fromisoformat(
            str(POLICY_EXPERIMENT_SPEC["registered_at"])
        ),
        reference_run_id=str(POLICY_EXPERIMENT_SPEC["reference_run_id"]),
        reference_input_hash=str(POLICY_EXPERIMENT_SPEC["reference_input_hash"]),
        fixed_candidate=fixed_candidate,
        specification_hash=_hash(POLICY_EXPERIMENT_SPEC),
        corrected_validation_candidate=selected,
        corrected_selection_changed=selected.id != fixed_candidate.id,
        comparisons=policy_comparisons,
        limitations=[
            (
                "사전 고정 뒤 같은 과거 보유평가 구간을 재사용한 후향 비교이며 "
                "독립적인 미래검증이 아닙니다."
            ),
            "일봉 시가·종가만 사용해 장중 체결 가능성이나 호가를 검증하지 않습니다.",
            (
                "재진입 때 episode 고점을 다시 잡지만 lifetime 고점과 낙폭은 "
                "초기화하지 않으며 lifetime 10% 이내를 보장하지 않습니다."
            ),
            (
                "변동성 배율은 종목별 원화 표준편차의 가중합인 보수적 proxy이며 "
                "공분산 포트폴리오 변동성 목표가 아닙니다."
            ),
            "어떤 비교 행도 자동으로 선택하거나 실제 주문에 사용하지 않습니다.",
        ],
    )
    incomplete_results = [
        item
        for item in (
            heldout,
            equal_baseline,
            stressed,
            *(
                simulation
                for comparison in policy_comparisons
                for simulation in (comparison.base, comparison.cost_stress)
            ),
        )
        if not item.complete
    ]
    if incomplete_results:
        reasons = sorted(
            {
                reason
                for item in incomplete_results
                for reason in item.incomplete_reasons
            }
        )
        raise ValueError(
            "Held-out portfolio inputs are incomplete: " + "; ".join(reasons[:5])
        )
    result = PortfolioRunResult(
        run_id=run_id,
        created_at=datetime.now(UTC),
        input_hash=input_hash,
        code_hash=code_hash,
        requested_start=requested_start,
        harmonized_end=heldout_end,
        preparation_end=preparation_end,
        validation_start=validation_start,
        validation_end=validation_end,
        heldout_start=heldout_start,
        heldout_end=heldout_end,
        selected_candidate=selected,
        validation=evaluations,
        heldout=heldout,
        cash_baseline=cash_metrics(configured),
        equal_baseline=equal_baseline,
        cost_stress=stressed,
        config=configured,
        external_status=source.external_status,
        limitations=[
            (
                "현재 archive로 재구성한 과거 탐색이며 당시 시점 데이터임이 "
                "검증되지 않았습니다."
            ),
            (
                "같은 과거 구간에서 후보를 비교한 뒤 보유평가했으므로 "
                "독립적인 미래 성과가 아닙니다."
            ),
            (
                "배당과 세금은 제외하고 가격수익률, 수수료, 슬리피지, "
                "환전 스프레드만 반영했습니다."
            ),
            (
                "종목별 20%, 총투자 60%, SOXL·TQQQ 합산 20%, "
                "고점 대비 10% 손실 제한을 고정했습니다."
            ),
            "실제 주문이나 증권사 거래 API를 호출하지 않습니다.",
        ],
        artifacts=list(ARTIFACT_NAMES),
        policy_experiment=policy_experiment,
    )
    temporary = repository.runs_dir / f".{run_id}.{os.getpid()}.tmp"
    temporary.mkdir(parents=True, exist_ok=False)
    try:
        (temporary / "result.json").write_text(
            result.model_dump_json(indent=2), encoding="utf-8"
        )
        (temporary / "report.md").write_text(_markdown(result), encoding="utf-8")
        for name, content in _csv_artifacts(result).items():
            (temporary / name).write_text(content, encoding="utf-8")
        manifest = {
            "run_id": run_id,
            "input_hash": input_hash,
            "code_hash": code_hash,
            "config": configured.model_dump(mode="json"),
            "selection": selected.model_dump(mode="json"),
            "policy_experiment_specification": POLICY_EXPERIMENT_SPEC,
            "policy_experiment_specification_hash": _hash(POLICY_EXPERIMENT_SPEC),
            "frozen_input": source_payload,
            "artifacts": list(STORED_ARTIFACT_NAMES),
        }
        (temporary / "manifest.json").write_text(
            _canonical_json(manifest) + "\n", encoding="utf-8"
        )
        repository.runs_dir.mkdir(parents=True, exist_ok=True)
        os.replace(temporary, run_dir)
        _atomic_write(
            report_dir / "portfolio-latest.json",
            _canonical_json({"run_id": run_id}) + "\n",
        )
    except Exception as error:
        repository.record_failure(run_id, error)
        raise
    return result


def run_from_stores(
    input_db: Path, external_db: Path, report_dir: Path
) -> PortfolioRunResult:
    report_dir.mkdir(parents=True, exist_ok=True)
    repository = PortfolioRunRepository(report_dir)
    lock_path = report_dir / "portfolio.lock"
    with lock_path.open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Portfolio research is already running.") from None
        attempted_at = datetime.now(UTC)
        previous = repository.status()
        external_store = ExternalStore(external_db)
        repository.save_status(
            PortfolioRunStatus(
                status="running",
                last_attempt_at=attempted_at,
                last_success_at=previous.last_success_at,
                latest_run_id=previous.latest_run_id,
                latest_stale=previous.latest_stale,
                external_status=external_store.statuses(),
            )
        )
        try:
            source = load_portfolio_input(UniverseInputStore(input_db), external_store)
            result = run_portfolio_research(source, report_dir)
        except Exception as error:
            failure_id = _hash(
                {
                    "attempted_at": attempted_at.isoformat(),
                    "error_type": type(error).__name__,
                }
            )
            repository.record_failure(failure_id, error)
            latest = repository.latest()
            repository.save_status(
                PortfolioRunStatus(
                    status="error",
                    last_attempt_at=attempted_at,
                    last_success_at=previous.last_success_at,
                    latest_run_id=latest.run_id if latest else previous.latest_run_id,
                    error_code=type(error).__name__,
                    latest_stale=latest is not None,
                    external_status=external_store.statuses(),
                )
            )
            raise
        repository.save_status(
            PortfolioRunStatus(
                status="success",
                last_attempt_at=attempted_at,
                last_success_at=datetime.now(UTC),
                latest_run_id=result.run_id,
                latest_stale=False,
                external_status=external_store.statuses(),
            )
        )
        return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Combined multi-market portfolio research"
    )
    parser.add_argument("--input-db", type=Path, default=DEFAULT_INPUT_DB)
    parser.add_argument("--external-db", type=Path, default=DEFAULT_EXTERNAL_DB)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("run")
    commands.add_parser("status")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    if arguments.command == "status":
        current = PortfolioRunRepository(arguments.report_dir).status()
        print(_canonical_json(current.model_dump(mode="json")))
        return 0
    try:
        result = run_from_stores(
            arguments.input_db, arguments.external_db, arguments.report_dir
        )
    except (OSError, ValueError, RuntimeError) as error:
        print(str(error))
        return 1
    print(result.model_dump_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
