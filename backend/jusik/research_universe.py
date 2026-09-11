from __future__ import annotations

import argparse
import asyncio
import csv
import fcntl
import hashlib
import io
import json
import signal
import sqlite3
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import FrameType
from zoneinfo import ZoneInfo

import httpx

from jusik.research_config import load_research_settings
from jusik.research_data import (
    DataCollectionError,
    DataInsufficientError,
    KisPaperHistoricalData,
)
from jusik.research_external_data import (
    SOURCE_USAGE,
    ExternalCollectionStopped,
    collect_external_sources,
)
from jusik.research_external_models import (
    ExternalFeatureSnapshot,
    external_evidence_metadata,
)
from jusik.research_external_store import ExternalStore
from jusik.research_history import HistoryRepository
from jusik.research_optimizer import (
    DEFAULT_ARTIFACT_DIR,
    DEFAULT_OPTIMIZER_DB,
    DeviceChoice,
    SourceSnapshot,
    StopRequested,
    _resolve_device,
    optimize_walk_forward_snapshot,
    walk_forward_identity,
)
from jusik.research_optimizer_store import OptimizerStore
from jusik.research_portfolio import (
    PortfolioRunRepository,
    run_from_stores,
)
from jusik.research_risk import ResearchRiskPolicy
from jusik.research_universe_data import (
    FETCH_WARMUP_DAYS,
    REGISTRY,
    YAHOO_BASE_URL,
    CollectedUniverseSnapshot,
    fetch_yahoo_chart,
    normalize_chart,
    rolling_period,
)
from jusik.research_universe_models import ResearchInstrument
from jusik.research_universe_store import UniverseInputStore, UniverseResultStore

DEFAULT_INPUT_DB = Path.home() / ".local/share/jusik/research-universe.db"
DEFAULT_EXTERNAL_DB = Path.home() / ".local/share/jusik/research-external.db"
DEFAULT_REPORT_DIR = Path.home() / ".local/share/jusik/research-universe-reports"
DEFAULT_POLL_SECONDS = 21600
STOCK_REFRESH_SECONDS = 86400


def _safe_error(error: Exception) -> str:
    if isinstance(error, (DataCollectionError, DataInsufficientError)):
        return str(error)
    return f"Universe research failed safely ({type(error).__name__})."


def _load_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise DataCollectionError(f"fixture {path.name}을 읽을 수 없습니다.") from None
    if not isinstance(value, dict):
        raise DataCollectionError(f"fixture {path.name} 형식이 올바르지 않습니다.")
    return value


async def _kis_rows(
    provider: KisPaperHistoricalData,
    token: str,
    instrument: ResearchInstrument,
    requested_start: date,
    requested_end: date,
) -> list[Mapping[str, object]]:
    rows, _market = await provider._series(  # noqa: SLF001
        token,
        instrument.symbol,
        requested_start - timedelta(days=FETCH_WARMUP_DAYS),
        requested_end,
        adjusted=False,
    )
    return [row.model_dump(mode="json") for _, row in sorted(rows.items())]


async def collect_all(
    input_store: UniverseInputStore,
    *,
    should_stop: Callable[[], bool],
    fixtures_dir: Path | None = None,
    captured_at: datetime | None = None,
) -> list[CollectedUniverseSnapshot]:
    captured = captured_at or datetime.now(UTC)
    collected: list[CollectedUniverseSnapshot] = []
    yahoo_client: httpx.AsyncClient | None = None
    kis_client: httpx.AsyncClient | None = None
    kis_provider: KisPaperHistoricalData | None = None
    kis_token: str | None = None
    if fixtures_dir is None:
        yahoo_client = httpx.AsyncClient(
            base_url=YAHOO_BASE_URL,
            timeout=20,
            headers={"User-Agent": "jusik-offline-research/1.0"},
        )
    try:
        for instrument in REGISTRY:
            if should_stop():
                raise StopRequested
            local_today = captured.astimezone(ZoneInfo(instrument.timezone)).date()
            requested_start, requested_end = rolling_period(local_today)
            try:
                if fixtures_dir is not None:
                    yahoo_payload = _load_json(
                        fixtures_dir / "charts" / f"{instrument.yahoo_symbol}.json"
                    )
                else:
                    assert yahoo_client is not None
                    yahoo_payload = await fetch_yahoo_chart(
                        yahoo_client, instrument, requested_start, requested_end
                    )
                raw_rows: list[Mapping[str, object]] | None = None
                if instrument.currency == "KRW":
                    if fixtures_dir is not None:
                        kis_payload = _load_json(
                            fixtures_dir / "kis-raw" / f"{instrument.symbol}.json"
                        )
                        value = kis_payload.get("rows")
                        if not isinstance(value, list) or not all(
                            isinstance(row, Mapping) for row in value
                        ):
                            raise DataCollectionError(
                                f"{instrument.symbol} KIS fixture 형식이 "
                                "올바르지 않습니다."
                            )
                        raw_rows = value
                    else:
                        if kis_provider is None:
                            settings = load_research_settings()
                            candidate_client = httpx.AsyncClient(
                                base_url=str(settings.base_url), timeout=20
                            )
                            candidate_provider = KisPaperHistoricalData(
                                settings, candidate_client
                            )
                            try:
                                candidate_token = (
                                    await candidate_provider._authenticate()  # noqa: SLF001
                                )
                            except Exception:
                                await candidate_client.aclose()
                                raise
                            kis_client = candidate_client
                            kis_provider = candidate_provider
                            kis_token = candidate_token
                        assert kis_token is not None
                        raw_rows = await _kis_rows(
                            kis_provider,
                            kis_token,
                            instrument,
                            requested_start,
                            requested_end,
                        )
                result = normalize_chart(
                    instrument,
                    yahoo_payload,
                    captured_at=captured,
                    requested_start=requested_start,
                    requested_end=requested_end,
                    kis_raw_rows=raw_rows,
                )
                input_store.save_success(result)
                collected.append(result)
            except (
                DataCollectionError,
                DataInsufficientError,
                OSError,
                RuntimeError,
                ValueError,
            ) as error:
                input_store.record_failure(instrument.symbol, _safe_error(error))
    finally:
        if yahoo_client is not None:
            await yahoo_client.aclose()
        if kis_client is not None:
            await kis_client.aclose()
    return collected


def universe_status(
    input_store: UniverseInputStore,
    result_store: UniverseResultStore,
    external_store: ExternalStore | None = None,
) -> dict[str, object]:
    collections = input_store.statuses()
    optimizations = result_store.statuses()
    instruments: list[dict[str, object]] = []
    evidence = external_evidence_metadata()
    for instrument in REGISTRY:
        collection = collections.get(instrument.symbol, {})
        optimization = optimizations.get(instrument.symbol, {})
        optimization_is_current = bool(collection.get("snapshot_id")) and (
            optimization.get("snapshot_id") == collection.get("snapshot_id")
        )
        batch = (
            result_store.batch_details(str(optimization["batch_id"]))
            if optimization_is_current and optimization.get("batch_id")
            else None
        )
        folds = batch["folds"] if batch else []
        summary = batch.get("summary") if batch else None
        macro_validation = (
            _macro_validation_status(result_store.path, str(batch["id"]))
            if batch is not None
            else {"eligible": 0, "ineligible": 0, "reasons": {}}
        )
        oos_missing_dates = 0
        for fold in folds:
            raw_risk = fold.get("winner_risk_json")
            if not raw_risk:
                continue
            risk = json.loads(raw_risk)
            diagnostics = risk.get("external_diagnostics", {})
            if isinstance(diagnostics, dict):
                oos_missing_dates += int(diagnostics.get("missing_date_count", 0))
        current_optimizer_status = (
            str(batch["status"])
            if batch is not None
            else str(optimization.get("status", "pending"))
        )
        instruments.append(
            {
                "symbol": instrument.symbol,
                "name": instrument.name,
                "currency": instrument.currency,
                "exchange": instrument.exchange,
                "timezone": instrument.timezone,
                "listed_on": instrument.listed_on.isoformat()
                if instrument.listed_on
                else None,
                "collection_status": collection.get("status", "pending"),
                "freshness": collection.get("updated_at"),
                "last_success_at": collection.get("last_success_at"),
                "collection_error": collection.get("error"),
                "requested_range": [
                    collection.get("requested_start"),
                    collection.get("requested_end"),
                ],
                "actual_range": [
                    collection.get("actual_start"),
                    collection.get("actual_end"),
                ],
                "evaluation_start": collection.get("evaluation_start"),
                "warmup_bars": collection.get("warmup_bars", 0),
                "evaluation_bars": collection.get("evaluation_bars", 0),
                "optimizer_status": (
                    current_optimizer_status
                    if optimization_is_current
                    else "pending_refresh"
                    if collection.get("snapshot_id")
                    else "pending"
                ),
                "optimizer_error": (
                    batch.get("error")
                    if batch is not None
                    else optimization.get("error")
                )
                if optimization_is_current
                else None,
                "batch_id": optimization.get("batch_id")
                if optimization_is_current
                else None,
                "previous_result": {
                    "snapshot_id": optimization.get("snapshot_id"),
                    "batch_id": optimization.get("batch_id"),
                    "status": optimization.get("status"),
                }
                if optimization and not optimization_is_current
                else None,
                "folds": len(folds),
                "completed_folds": sum(fold["status"] == "completed" for fold in folds),
                "candidate_evaluations": sum(
                    int(fold["candidate_count"]) for fold in folds
                ),
                "passed_folds": summary.get("passed_folds", 0) if summary else 0,
                "mean_oos_return_pct": summary.get("mean_oos_return_pct")
                if summary
                else None,
                "worst_oos_return_pct": summary.get("worst_oos_return_pct")
                if summary
                else None,
                "max_oos_drawdown_pct": summary.get("max_oos_drawdown_pct")
                if summary
                else None,
                "tail": batch.get("tail") if batch else None,
                "research_comparison_met": summary.get("research_comparison_met")
                if summary
                else False,
                "macro_validation": macro_validation,
                "external_oos_missing_dates": oos_missing_dates,
                **evidence,
                "cost_assumptions": {
                    "initial_cash": "100000000"
                    if instrument.currency == "KRW"
                    else "100000",
                    "fee_rate": "0.001",
                    "slippage_rate": "0.001",
                    "sell_tax_rate": "0",
                    "experimental": True,
                },
            }
        )
    external = (
        [
            item.model_dump(mode="json")
            for item in external_store.statuses(usages=SOURCE_USAGE)
        ]
        if external_store is not None
        else []
    )
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        **evidence,
        "automatic_trading_eligible": False,
        "currency_aggregation": "disabled",
        "price_return_only": True,
        "external_sources": external,
        "external_bootstrap_policy": (
            "과거 archive를 현재 시점에 복원하고 보수적인 익일 UTC 공개시각을 "
            "가정한 근사치이며 완전한 vintage 자료가 아닙니다."
        ),
        "unused_external_series": ["spy", "smh", "gpr", "effr"],
        "instruments": instruments,
    }


def _macro_validation_status(path: Path, batch_id: str) -> dict[str, object]:
    with sqlite3.connect(path) as connection:
        rows = connection.execute(
            """
            SELECT c.eligible, c.validation_result_json
            FROM optimizer_candidates AS c
            JOIN optimizer_batch_folds AS f
              ON f.optimizer_run_id=c.optimizer_run_id
            WHERE f.batch_id=? AND c.family='external_macro'
            """,
            (batch_id,),
        ).fetchall()
    eligible = sum(int(row[0] == 1) for row in rows)
    reasons: dict[str, int] = {}
    for row in rows:
        if row[0] == 1 or not row[1]:
            continue
        payload = json.loads(row[1])
        reason = str(payload.get("ineligible_reason", "검증 부적격 사유 없음"))
        reasons[reason] = reasons.get(reason, 0) + 1
    return {
        "eligible": eligible,
        "ineligible": len(rows) - eligible,
        "reasons": dict(sorted(reasons.items())),
    }


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def write_reports(report_dir: Path, status: dict[str, object]) -> None:
    items = status["instruments"]
    assert isinstance(items, list)
    overview = [
        "# 3년 종목별 전략 연구",
        "",
        "이 보고서는 자동매매 준비 판정이 아닌 과거 가격 손익 연구입니다. ",
        "배당·분배금, 환전, 개인별 세금은 제외하며 KRW와 USD 성과를 합산하지 않습니다.",
        "외부 변수 과거값은 현재 archive를 보수적인 공개시각으로 복원한 근사치입니다.",
        (
            "`evidence_class=reconstructed_historical_exploration`, "
            "`point_in_time_verified=false`, "
            "`prospective_validation_eligible=false`입니다. "
            "`research_comparison_met`는 원시점·전진 검증 또는 자동매매 승격을 "
            "뜻하지 않습니다."
        ),
        "",
        (
            "| 종목 | 통화 | 수집 | 평가 일봉 | fold | 통과 | 평균 OOS | "
            "최악 OOS | 최대 낙폭 |"
        ),
        "|---|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    for raw_item in items:
        assert isinstance(raw_item, dict)
        item = raw_item
        row = {
            key: item.get(key)
            for key in (
                "symbol",
                "name",
                "currency",
                "collection_status",
                "optimizer_status",
                "evaluation_bars",
                "folds",
                "completed_folds",
                "candidate_evaluations",
                "passed_folds",
                "mean_oos_return_pct",
                "worst_oos_return_pct",
                "max_oos_drawdown_pct",
                "research_comparison_met",
                "macro_validation",
                "external_oos_missing_dates",
                "evidence_class",
                "point_in_time_verified",
                "prospective_validation_eligible",
                "collection_error",
                "optimizer_error",
            )
        }
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)
        _atomic_write(report_dir / f"{item['symbol']}.csv", output.getvalue())
        markdown = (
            f"# {item['symbol']} {item['name']}\n\n"
            f"- 통화/거래소: {item['currency']} / {item['exchange']}\n"
            f"- 요청 범위: {item['requested_range']}\n"
            f"- 실제 범위: {item['actual_range']}\n"
            f"- 준비/평가 일봉: {item['warmup_bars']} / {item['evaluation_bars']}\n"
            f"- 수집/최적화 상태: {item['collection_status']} / "
            f"{item['optimizer_status']}\n"
            f"- 완료 fold/후보 평가: {item['completed_folds']} / "
            f"{item['candidate_evaluations']}\n"
            f"- 평균·최악 OOS 수익률: {item['mean_oos_return_pct']} / "
            f"{item['worst_oos_return_pct']}\n"
            f"- 최대 OOS 낙폭: {item['max_oos_drawdown_pct']}\n\n"
            f"- macro 검증 상태: {item['macro_validation']}\n"
            f"- 외부 변수 OOS 누락 날짜: {item['external_oos_missing_dates']}\n\n"
            f"- 증거 분류: {item['evidence_class']}\n"
            f"- 원시점 자료 검증: {item['point_in_time_verified']}\n"
            f"- 전진 검증 승격 가능: {item['prospective_validation_eligible']}\n\n"
            "배당·분배금, 환전, 개인별 세금을 제외한 종목별 가격 손익 연구입니다. "
            "고정 수수료·슬리피지 가정은 실제 거래 조건이 아니며 "
            "자동매매에 사용하지 않습니다.\n"
        )
        _atomic_write(report_dir / f"{item['symbol']}.md", markdown)
        overview.append(
            f"| {item['symbol']} | {item['currency']} | {item['collection_status']} | "
            f"{item['evaluation_bars']} | {item['completed_folds']} | "
            f"{item['passed_folds']} | "
            f"{item['mean_oos_return_pct']} | {item['worst_oos_return_pct']} | "
            f"{item['max_oos_drawdown_pct']} |"
        )
    _atomic_write(report_dir / "universe.md", "\n".join(overview) + "\n")
    external_rows = status.get("external_sources", [])
    lines = [
        "# 외부 변수 수집 상태",
        "",
        (
            "`evidence_class=reconstructed_historical_exploration`, "
            "`point_in_time_verified=false`, "
            "`prospective_validation_eligible=false`입니다. 현재 archive로 재구성한 "
            "과거 비교이므로 `research_comparison_met`도 원시점·전진 검증이나 "
            "자동매매 승격 근거가 아닙니다."
        ),
        "",
        "| 출처 | 용도 | 상태 | 범위 | 관측 | 원문 | 오류 |",
        "|---|---|---|---|---:|---:|---|",
    ]
    if isinstance(external_rows, list):
        for raw in external_rows:
            if not isinstance(raw, dict):
                continue
            lines.append(
                f"| {raw.get('source')} | {raw.get('usage')} | {raw.get('status')} | "
                f"{raw.get('coverage_start')}~{raw.get('coverage_end')} | "
                f"{raw.get('observation_count')} | {raw.get('raw_archive_count')} | "
                f"{raw.get('error') or ''} |"
            )
    lines.extend(
        [
            "",
            "GPR과 EFFR는 원문만 보관하며 현재 후보 신호에는 사용하지 않습니다. ",
            "SPY와 SMH도 진단용으로만 수집합니다. 누락값은 0으로 채우지 않습니다.",
        ]
    )
    _atomic_write(report_dir / "external.md", "\n".join(lines) + "\n")


async def _run_cycle(
    input_store: UniverseInputStore,
    optimizer_store: OptimizerStore,
    result_store: UniverseResultStore,
    artifact_dir: Path,
    report_dir: Path,
    device: DeviceChoice,
    should_stop: Callable[[], bool],
    fixtures_dir: Path | None,
    external_store: ExternalStore | None = None,
    refresh_stocks: bool = True,
) -> bool:
    captured = datetime.now(UTC)
    if external_store is not None:
        external_end = captured.date() - timedelta(days=1)
        external_start = external_end - timedelta(days=1095 + FETCH_WARMUP_DAYS)
        try:
            await collect_external_sources(
                external_store,
                start=external_start,
                end=external_end,
                captured_at=captured,
                should_stop=should_stop,
            )
        except ExternalCollectionStopped:
            raise StopRequested from None
    collected = (
        await collect_all(
            input_store,
            should_stop=should_stop,
            fixtures_dir=fixtures_dir,
            captured_at=captured,
        )
        if refresh_stocks
        else []
    )
    collected_by_symbol = {item.request.instrument.symbol: item for item in collected}
    prior_states = result_store.statuses()
    latest_external = (
        external_store.snapshot()
        if external_store is not None
        else ExternalFeatureSnapshot(observations=[])
    )
    if external_store is not None:
        history = HistoryRepository(
            report_dir.parent / "research-history",
            report_dir.parent / "research-history-journal.db",
        )
        try:
            portfolio = run_from_stores(
                input_store.path, external_store.path, report_dir
            )
            history.record(
                identity=f"portfolio-run-{portfolio.run_id}-completed",
                title="통합 포트폴리오 연구 완료",
                summary="고정 검증·보유평가 결과와 공개 산출물을 저장했습니다.",
                category="research",
                outcome="completed",
                occurred_at=captured,
                run_ids=[portfolio.run_id],
            )
        except Exception as portfolio_error:
            failure_id = hashlib.sha256(
                f"{captured.isoformat()}|{type(portfolio_error).__name__}".encode()
            ).hexdigest()
            PortfolioRunRepository(report_dir).record_failure(
                failure_id, portfolio_error
            )
            history.record(
                identity=f"portfolio-run-{failure_id}-failed",
                title="통합 포트폴리오 연구 실패",
                summary="실패 상태를 기록하고 마지막 성공 결과는 보존했습니다.",
                category="research",
                outcome="failed",
                occurred_at=captured,
            )
    for instrument in REGISTRY:
        if instrument.symbol in collected_by_symbol:
            continue
        latest = input_store.load_latest(instrument.symbol)
        if latest is None:
            continue
        snapshot_id, request, snapshot = latest
        prior = prior_states.get(instrument.symbol)
        prior_external = (
            external_store.load_bound_snapshot(str(prior["batch_id"]))
            if external_store is not None and prior and prior.get("batch_id")
            else None
        )
        external_changed = external_store is not None and (
            prior_external is None
            or prior_external.semantic_hash() != latest_external.semantic_hash()
        )
        resumable = (
            prior is None
            or prior.get("snapshot_id") != snapshot_id
            or prior.get("status") in {"running", "stopped", "failed"}
            or external_changed
        )
        if resumable:
            collected.append(
                CollectedUniverseSnapshot(
                    request=request,
                    snapshot=snapshot,
                    raw_payload={},
                    content_hash=snapshot_id,
                )
            )
    processed = False
    policy = ResearchRiskPolicy()
    for item in collected:
        if should_stop() or optimizer_store.stop_requested():
            raise StopRequested
        symbol = item.request.instrument.symbol
        prior = prior_states.get(symbol)
        bound_external = (
            external_store.load_bound_snapshot(str(prior["batch_id"]))
            if external_store is not None
            and prior
            and prior.get("snapshot_id") == item.content_hash
            and prior.get("batch_id")
            and prior.get("status") in {"running", "stopped", "failed"}
            else None
        )
        source = SourceSnapshot(
            run_id=f"universe:{symbol}:{item.content_hash}",
            request=item.request,
            snapshot=item.snapshot,
            external=bound_external or latest_external,
        )
        batch_id, _ = walk_forward_identity(source, device, policy)
        assert source.external is not None
        if external_store is not None:
            source = source.__class__(
                run_id=source.run_id,
                request=source.request,
                snapshot=source.snapshot,
                external=external_store.bind_snapshot(batch_id, source.external),
            )
        result_store.update(
            symbol, item.content_hash, batch_id=batch_id, status="running"
        )
        try:
            processed = (
                optimize_walk_forward_snapshot(
                    source,
                    optimizer_store,
                    artifact_dir,
                    device,
                    should_stop,
                )
                or processed
            )
        except StopRequested:
            batch = result_store.batch_details(batch_id)
            result_store.update(
                symbol,
                item.content_hash,
                batch_id=batch_id,
                status=str(batch["status"]) if batch else "stopped",
                error=str(batch["error"]) if batch and batch.get("error") else None,
            )
            write_reports(
                report_dir,
                universe_status(input_store, result_store, external_store),
            )
            raise
        batch = result_store.batch_details(batch_id)
        status = str(batch["status"]) if batch else "failed"
        error = str(batch["error"]) if batch and batch.get("error") else None
        result_store.update(
            symbol,
            item.content_hash,
            batch_id=batch_id,
            status=status,
            error=error,
        )
    write_reports(
        report_dir,
        universe_status(input_store, result_store, external_store),
    )
    return processed


def run_daemon(
    input_db: Path,
    external_db: Path,
    optimizer_db: Path,
    artifact_dir: Path,
    report_dir: Path,
    *,
    device: DeviceChoice,
    once: bool,
    poll_seconds: int = DEFAULT_POLL_SECONDS,
    fixtures_dir: Path | None = None,
) -> int:
    input_store = UniverseInputStore(input_db)
    external_store = ExternalStore(external_db)
    optimizer_store = OptimizerStore(optimizer_db)
    result_store = UniverseResultStore(optimizer_db)
    lock_path = optimizer_db.with_suffix(".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("optimizer is already running", file=sys.stderr)
            return 2
        _resolve_device(device)
        optimizer_store.clear_stop()
        optimizer_store.daemon_heartbeat(True)
        interrupted = False

        def request_stop(_signum: int, _frame: FrameType | None) -> None:
            nonlocal interrupted
            interrupted = True

        previous_term = signal.signal(signal.SIGTERM, request_stop)
        previous_int = signal.signal(signal.SIGINT, request_stop)
        try:
            last_stock_refresh: datetime | None = None
            while True:
                if interrupted or optimizer_store.stop_requested():
                    return 0
                try:
                    refresh_stocks = (
                        once
                        or last_stock_refresh is None
                        or datetime.now(UTC) - last_stock_refresh
                        >= timedelta(seconds=STOCK_REFRESH_SECONDS)
                    )
                    asyncio.run(
                        _run_cycle(
                            input_store,
                            optimizer_store,
                            result_store,
                            artifact_dir,
                            report_dir,
                            device,
                            lambda: interrupted,
                            fixtures_dir,
                            external_store,
                            refresh_stocks=refresh_stocks,
                        )
                    )
                    if refresh_stocks:
                        last_stock_refresh = datetime.now(UTC)
                except StopRequested:
                    return 0
                if once:
                    return 0
                waited = 0
                while waited < poll_seconds:
                    if interrupted or optimizer_store.stop_requested():
                        return 0
                    time.sleep(1)
                    waited += 1
                    optimizer_store.daemon_heartbeat(True)
        finally:
            optimizer_store.daemon_heartbeat(False)
            signal.signal(signal.SIGTERM, previous_term)
            signal.signal(signal.SIGINT, previous_int)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Three-year offline universe research")
    parser.add_argument("--input-db", type=Path, default=DEFAULT_INPUT_DB)
    parser.add_argument("--external-db", type=Path, default=DEFAULT_EXTERNAL_DB)
    parser.add_argument("--optimizer-db", type=Path, default=DEFAULT_OPTIMIZER_DB)
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run")
    run.add_argument("--once", action="store_true")
    run.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    run.add_argument("--poll-seconds", type=int, default=DEFAULT_POLL_SECONDS)
    run.add_argument("--fixtures-dir", type=Path)
    subparsers.add_parser("status")
    subparsers.add_parser("collect-external")
    subparsers.add_parser("stop")
    subparsers.add_parser("report")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    input_store = UniverseInputStore(arguments.input_db)
    external_store = ExternalStore(arguments.external_db)
    optimizer_store = OptimizerStore(arguments.optimizer_db)
    result_store = UniverseResultStore(arguments.optimizer_db)
    if arguments.command == "status":
        print(
            json.dumps(
                universe_status(input_store, result_store, external_store),
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    if arguments.command == "collect-external":
        captured = datetime.now(UTC)
        end = captured.date() - timedelta(days=1)
        start = end - timedelta(days=1095 + FETCH_WARMUP_DAYS)
        try:
            outcomes = asyncio.run(
                collect_external_sources(
                    external_store,
                    start=start,
                    end=end,
                    captured_at=captured,
                )
            )
        except ExternalCollectionStopped:
            return 0
        print(json.dumps(outcomes, ensure_ascii=False, sort_keys=True))
        return int(any(value != "success" for value in outcomes.values()))
    if arguments.command == "stop":
        optimizer_store.request_stop()
        print("stop requested")
        return 0
    if arguments.command == "report":
        write_reports(
            arguments.report_dir,
            universe_status(input_store, result_store, external_store),
        )
        return 0
    try:
        return run_daemon(
            arguments.input_db,
            arguments.external_db,
            arguments.optimizer_db,
            arguments.artifact_dir,
            arguments.report_dir,
            device=arguments.device,
            once=arguments.once,
            poll_seconds=arguments.poll_seconds,
            fixtures_dir=arguments.fixtures_dir,
        )
    except (sqlite3.Error, DataCollectionError, DataInsufficientError):
        print("universe research storage or input is invalid", file=sys.stderr)
        return 1
    except RuntimeError as error:
        print(_safe_error(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
