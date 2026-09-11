import fcntl
import hashlib
import json
import sqlite3
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

import jusik.research_optimizer as optimizer_module
from jusik.operations_models import StrategyDefinition
from jusik.research_data import DataInsufficientError
from jusik.research_engine import run_definition_backtest, run_signal_backtest
from jusik.research_external_models import ExternalFeatureSnapshot
from jusik.research_models import (
    DailyBar,
    ResearchInputSnapshot,
    ResearchRunRequest,
    SymbolSnapshot,
)
from jusik.research_optimizer import (
    Candidate,
    SourceSnapshot,
    StopRequested,
    _load_artifact,
    _resumable_candidate_ids,
    _wilder_atr,
    _wilder_rsi,
    candidates,
    content_identity,
    mlp_signal,
    optimize_snapshot,
    optimize_walk_forward_snapshot,
    rule_signal,
    run_daemon,
    train_mlp,
    training_examples,
    validate_and_split,
    walk_forward_folds,
)
from jusik.research_optimizer_store import OptimizerStore
from jusik.research_risk import ResearchRiskPolicy

LEGACY_CANDIDATES_HASH = (
    "c4355002a5c610ed00863744a0e943fcacfcd93aa38b60312d23dd9597c90bc8"
)
ORIGINAL_86_CANDIDATES_HASH = (
    "5b907bc9abe4dcb5e77db8ae3b83b5953e6ebeeb87605c6094010d30c2b6094a"
)


def _source(*, sessions: int = 200) -> SourceSnapshot:
    first = date(2025, 1, 1)
    start = first + timedelta(days=60)
    bars = []
    for index in range(60 + sessions):
        price = Decimal(100 + index % 17)
        bars.append(
            DailyBar(
                date=first + timedelta(days=index),
                open=price,
                high=price + 1,
                low=price - 1,
                close=price,
                volume=1000 + index % 11,
                adjusted_open=price,
                adjusted_high=price + 1,
                adjusted_low=price - 1,
                adjusted_close=price,
            )
        )
    request = ResearchRunRequest(
        symbols=["005930"],
        start_date=start,
        end_date=bars[-1].date,
        initial_cash="1000000",
        fee_rate="0",
        slippage_rate="0",
        sell_tax_rate="0",
    )
    snapshot = ResearchInputSnapshot(
        captured_at=datetime(2026, 1, 1, tzinfo=UTC),
        requested_start=request.start_date,
        requested_end=request.end_date,
        symbols=[
            SymbolSnapshot(
                symbol="005930",
                market="KOSPI",
                bars=bars,
                source_url="https://example.com/daily",
            )
        ],
        events=[],
    )
    return SourceSnapshot("source", request, snapshot)


def _indicator_bars(
    closes: list[int | Decimal],
    *,
    highs: list[int | Decimal] | None = None,
    lows: list[int | Decimal] | None = None,
) -> list[DailyBar]:
    first = date(2025, 1, 1)
    result = []
    for index, value in enumerate(closes):
        close = Decimal(value)
        high = Decimal(highs[index]) if highs is not None else close
        low = Decimal(lows[index]) if lows is not None else close
        result.append(
            DailyBar(
                date=first + timedelta(days=index),
                open=close,
                high=high,
                low=low,
                close=close,
                volume=1000,
                adjusted_open=close,
                adjusted_high=high,
                adjusted_low=low,
                adjusted_close=close,
            )
        )
    return result


def _new_family_execution_source() -> SourceSnapshot:
    prices = [100] * 50 + [190] * 9 + [183, 176, 169, 162, 163, 164, 165]
    prices.extend([50, 50, 50, 50])
    bars = _indicator_bars(prices)
    start = bars[66].date
    request = ResearchRunRequest(
        symbols=["005930"],
        start_date=start,
        end_date=bars[-1].date,
        initial_cash="1000000",
        fee_rate="0",
        slippage_rate="0",
        sell_tax_rate="0",
    )
    snapshot = ResearchInputSnapshot(
        captured_at=datetime(2026, 1, 1, tzinfo=UTC),
        requested_start=request.start_date,
        requested_end=request.end_date,
        symbols=[
            SymbolSnapshot(
                symbol="005930",
                market="KOSPI",
                bars=bars,
                source_url="https://example.com/daily",
            )
        ],
        events=[],
    )
    return SourceSnapshot("new-family", request, snapshot)


def test_new_candidates_append_after_unchanged_legacy_sequence() -> None:
    configured = candidates()
    legacy_payload = [
        {"id": item.id, "family": item.family, "parameters": item.parameters}
        for item in configured[:68]
    ]
    legacy_hash = hashlib.sha256(
        json.dumps(legacy_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

    assert legacy_hash == LEGACY_CANDIDATES_HASH
    original_payload = [
        {"id": item.id, "family": item.family, "parameters": item.parameters}
        for item in configured[:86]
    ]
    assert (
        hashlib.sha256(
            json.dumps(original_payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        == ORIGINAL_86_CANDIDATES_HASH
    )
    assert [item.id for item in configured[68:86]] == [
        "rsi_pullback-073c605c00bd",
        "rsi_pullback-54eb3be6a663",
        "rsi_pullback-27506a239d77",
        "rsi_pullback-a1331c97a9cf",
        "rsi_pullback-73ccaae16759",
        "rsi_pullback-da2362e4fe99",
        "rsi_pullback-072d1fe92c43",
        "rsi_pullback-347e86c1cf22",
        "rsi_pullback-1054113e709e",
        "atr_trend-9f2acf871168",
        "atr_trend-e1fb79eeaaca",
        "atr_trend-106700d3f351",
        "atr_trend-3087cbea3738",
        "atr_trend-d3dd537c6314",
        "atr_trend-e89219f8ce4d",
        "atr_trend-c4f10e502e20",
        "atr_trend-b3e55dc249fb",
        "atr_trend-f74bfac26308",
    ]
    assert [item.parameters for item in configured[68:77]] == [
        {"window": window, "threshold": threshold, "trend_window": 60}
        for window in (7, 14, 21)
        for threshold in ("30", "40", "45")
    ]
    assert [item.parameters for item in configured[77:86]] == [
        {"window": window, "max_ratio": ratio, "trend_window": 20}
        for window in (10, 14, 20)
        for ratio in ("0.03", "0.05", "0.08")
    ]
    assert [(item.id, item.parameters) for item in configured[86:89]] == [
        (
            "mlp-ff33c870b288",
            {
                "variant": "cost_aware_v2",
                "horizon": 1,
                "threshold": "0.55",
                "hidden": 16,
                "epochs": 32,
                "learning_rate": "0.005",
                "weight_decay": "0.01",
                "seed": 20260909,
            },
        ),
        (
            "mlp-cdb7698fad65",
            {
                "variant": "cost_aware_v2",
                "horizon": 5,
                "threshold": "0.55",
                "hidden": 16,
                "epochs": 32,
                "learning_rate": "0.005",
                "weight_decay": "0.01",
                "seed": 20260909,
            },
        ),
        (
            "mlp-139c2c1f129c",
            {
                "variant": "cost_aware_v2",
                "horizon": 5,
                "threshold": "0.60",
                "hidden": 16,
                "epochs": 32,
                "learning_rate": "0.005",
                "weight_decay": "0.01",
                "seed": 20260909,
            },
        ),
    ]
    assert [(item.id, item.family, item.parameters) for item in configured[89:]] == [
        (
            "external_control-ffdca988e7b2",
            "external_control",
            {"variant": "unfiltered_trend_20_control"},
        ),
        (
            "external_macro-99b37f5c50d3",
            "external_macro",
            {
                "variant": "rates",
                "observation_lookback": 20,
                "max_age_days": 7,
                "minimum_spread_pp": "-1",
                "maximum_10y_change_pp": "0.50",
            },
        ),
        (
            "external_macro-db4b45d06841",
            "external_macro",
            {
                "variant": "fx_vix",
                "observation_lookback": 20,
                "max_age_days": 7,
                "maximum_usdkrw_return": "0.05",
                "maximum_vix": "30",
            },
        ),
        (
            "external_macro-9f3662e2b087",
            "external_macro",
            {
                "variant": "stress",
                "observation_lookback": 20,
                "max_age_days": 7,
                "maximum_uso_return": "0.15",
                "maximum_gld_return": "0.10",
                "minimum_hyg_return": "-0.03",
            },
        ),
    ]


def test_wilder_rsi_initializes_once_then_recurs() -> None:
    initial = _indicator_bars([10, 11, 10, 12])
    updated = _indicator_bars([10, 11, 10, 12, 11])

    assert _wilder_rsi(initial, 3) == Decimal(75)
    assert _wilder_rsi(updated, 3) == Decimal(600) / Decimal(11)
    assert _wilder_rsi(updated, 3) != Decimal(50)
    assert _wilder_rsi(_indicator_bars([10, 10, 10, 10]), 3) == Decimal(50)
    assert _wilder_rsi(_indicator_bars([10, 11, 12, 13]), 3) == Decimal(100)
    assert _wilder_rsi(_indicator_bars([13, 12, 11, 10]), 3) == Decimal()
    assert _wilder_rsi(_indicator_bars([10, 11, 10]), 3) is None


def test_wilder_atr_handles_gaps_and_recurs() -> None:
    initial = _indicator_bars(
        [10, 11, 8, 8],
        highs=[10, 12, 9, 9],
        lows=[10, 11, 8, 7],
    )
    updated = _indicator_bars(
        [10, 11, 8, 8, 12],
        highs=[10, 12, 9, 9, 13],
        lows=[10, 11, 8, 7, 12],
    )

    assert _wilder_atr(initial, 3) == Decimal(7) / Decimal(3)
    assert _wilder_atr(updated, 3) == Decimal(29) / Decimal(9)
    assert _wilder_atr(updated, 3) != Decimal(10) / Decimal(3)
    assert _wilder_atr(_indicator_bars([10, 11, 8]), 3) is None


def test_new_indicators_use_adjusted_scale_without_mutating_input() -> None:
    bars = _indicator_bars([1] * 55 + [10, 11, 10, 12, 11])
    before = [bar.model_dump() for bar in bars]
    rsi = _wilder_rsi(bars, 3)
    atr = _wilder_atr(bars, 3)
    assert rsi is not None and atr is not None
    scaled = [
        bar.model_copy(
            update={
                "adjusted_open": bar.adjusted_open * 10,
                "adjusted_high": bar.adjusted_high * 10,
                "adjusted_low": bar.adjusted_low * 10,
                "adjusted_close": bar.adjusted_close * 10,
            }
        )
        for bar in bars
    ]
    rsi_candidate = Candidate(
        "rsi-equality",
        "rsi_pullback",
        {"window": 3, "threshold": str(rsi), "trend_window": 60},
    )
    atr_candidate = Candidate(
        "atr-equality",
        "atr_trend",
        {
            "window": 3,
            "max_ratio": str(atr / bars[-1].adjusted_close),
            "trend_window": 20,
        },
    )

    assert rule_signal(rsi_candidate)("005930", tuple(bars))
    assert rule_signal(atr_candidate)("005930", tuple(bars))
    assert _wilder_rsi(scaled, 3) == rsi
    assert _wilder_atr(scaled, 3) == atr * 10
    assert rule_signal(rsi_candidate)("005930", tuple(scaled))
    assert rule_signal(atr_candidate)("005930", tuple(scaled))
    assert [bar.model_dump() for bar in bars] == before


@pytest.mark.parametrize(
    "candidate",
    [
        Candidate(
            "rsi-execution",
            "rsi_pullback",
            {"window": 7, "threshold": "45", "trend_window": 60},
        ),
        Candidate(
            "atr-execution",
            "atr_trend",
            {"window": 10, "max_ratio": "0.08", "trend_window": 20},
        ),
    ],
)
def test_new_family_enters_and_exits_at_next_open(candidate: Candidate) -> None:
    source = _new_family_execution_source()

    result = run_signal_backtest(
        source.request,
        source.snapshot,
        strategy_version=candidate.id,
        definition="test",
        signal=rule_signal(candidate),
    )

    assert [trade.side for trade in result.trades] == ["buy", "sell"]
    assert [trade.date for trade in result.trades] == [
        source.request.start_date,
        source.request.start_date + timedelta(days=1),
    ]
    assert [trade.signal_date for trade in result.trades] == [
        source.request.start_date - timedelta(days=1),
        source.request.start_date,
    ]


@pytest.mark.parametrize(
    "candidate",
    [
        Candidate(
            "rsi-future",
            "rsi_pullback",
            {"window": 7, "threshold": "45", "trend_window": 60},
        ),
        Candidate(
            "atr-future",
            "atr_trend",
            {"window": 10, "max_ratio": "0.08", "trend_window": 20},
        ),
    ],
)
def test_new_family_signal_ignores_bars_after_prefix(candidate: Candidate) -> None:
    bars = _new_family_execution_source().snapshot.symbols[0].bars
    prefix = tuple(bars[:66])
    changed_future = bars[-1].model_copy(
        update={
            "adjusted_open": Decimal(9999),
            "adjusted_high": Decimal(9999),
            "adjusted_low": Decimal(9999),
            "adjusted_close": Decimal(9999),
        }
    )
    changed = [*bars[:-1], changed_future]

    selected = rule_signal(candidate)
    assert selected("005930", prefix)
    assert selected("005930", tuple(changed[:66]))


def test_signal_callback_matches_definition_and_cannot_see_future_bars() -> None:
    source = _source()
    split = validate_and_split(source)
    observed: list[date] = []

    def causal(_symbol: str, bars: tuple[DailyBar, ...]) -> bool:
        observed.append(bars[-1].date)
        window = bars[-5:]
        average = sum((bar.adjusted_close for bar in window), Decimal()) / len(window)
        return bars[-1].adjusted_close > average

    callback_result = run_signal_backtest(
        split.validation,
        source.snapshot,
        strategy_version="test_signal",
        definition="test",
        signal=causal,
        defer_events=False,
    )
    definition_result = run_definition_backtest(
        split.validation,
        source.snapshot,
        StrategyDefinition(
            version="test_definition",
            name="test",
            fast_window=5,
            definition="test",
        ),
    )

    assert callback_result.metrics == definition_result.metrics
    assert callback_result.trades == definition_result.trades
    assert observed
    assert max(observed) <= split.validation.end_date


def test_split_and_ml_labels_purge_future_training_opens() -> None:
    source = _source()
    split = validate_and_split(source)
    original = training_examples(source.snapshot, split.training)
    item = source.snapshot.symbols[0]
    changed_bars = [
        bar.model_copy(
            update={
                "open": Decimal("999"),
                "high": Decimal("999"),
                "low": Decimal("999"),
                "close": Decimal("999"),
            }
        )
        if bar.date > split.training.end_date
        else bar
        for bar in item.bars
    ]
    changed = source.snapshot.model_copy(
        update={"symbols": [item.model_copy(update={"bars": changed_bars})]}
    )

    assert training_examples(changed, split.training) == original
    assert split.training.end_date < split.validation.start_date
    assert split.validation.end_date < split.final.start_date


@pytest.mark.parametrize(
    ("sessions", "fold_count", "tail_count"),
    [(240, 2, 0), (244, 2, 4), (280, 3, 0)],
)
def test_walk_forward_uses_expanding_full_folds_and_explicit_tail(
    sessions: int, fold_count: int, tail_count: int
) -> None:
    source = _source(sessions=sessions)

    folds, tail = walk_forward_folds(source)

    assert len(folds) == fold_count
    assert tail["count"] == tail_count
    assert folds[0].split.training.start_date == source.request.start_date
    assert folds[0].split.validation.start_date == (
        folds[0].split.training.end_date + timedelta(days=1)
    )
    assert folds[0].split.final.start_date == (
        folds[0].split.validation.end_date + timedelta(days=1)
    )
    assert all(
        fold.split.training.start_date == source.request.start_date for fold in folds
    )
    assert all(
        current.split.training.end_date < following.split.training.end_date
        for current, following in zip(folds[:-1], folds[1:], strict=True)
    )


def test_walk_forward_rejects_239_sessions() -> None:
    with pytest.raises(DataInsufficientError, match="240"):
        walk_forward_folds(_source(sessions=239))


def test_same_fold_training_and_validation_ignore_oos_changes() -> None:
    source = _source(sessions=240)
    fold = walk_forward_folds(source)[0][0]
    item = source.snapshot.symbols[0]
    changed_bars = [
        bar.model_copy(
            update={
                "open": Decimal(999),
                "high": Decimal(999),
                "low": Decimal(999),
                "close": Decimal(999),
                "adjusted_open": Decimal(999),
                "adjusted_high": Decimal(999),
                "adjusted_low": Decimal(999),
                "adjusted_close": Decimal(999),
            }
        )
        if fold.split.final.start_date <= bar.date <= fold.split.final.end_date
        else bar
        for bar in item.bars
    ]
    changed = SourceSnapshot(
        "changed",
        source.request,
        source.snapshot.model_copy(
            update={"symbols": [item.model_copy(update={"bars": changed_bars})]}
        ),
    )
    candidate = Candidate(
        "mlp-fold",
        "mlp",
        {"hidden": 4, "epochs": 2, "learning_rate": "0.01", "seed": 20260909},
    )

    original_artifact, _ = train_mlp(
        candidate, source.snapshot, fold.split.training, "cpu"
    )
    changed_artifact, _ = train_mlp(
        candidate, changed.snapshot, fold.split.training, "cpu"
    )
    original_validation = run_signal_backtest(
        fold.split.validation,
        source.snapshot,
        strategy_version=candidate.id,
        definition="test",
        signal=mlp_signal(original_artifact),
        risk_policy=ResearchRiskPolicy(),
    )
    changed_validation = run_signal_backtest(
        fold.split.validation,
        changed.snapshot,
        strategy_version=candidate.id,
        definition="test",
        signal=mlp_signal(changed_artifact),
        risk_policy=ResearchRiskPolicy(),
    )

    assert original_artifact["layers"] == changed_artifact["layers"]
    assert original_artifact["feature_mean"] == changed_artifact["feature_mean"]
    assert original_validation == changed_validation


def test_walk_forward_persists_isolated_fold_results_and_resumes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selected = Candidate(
        "momentum-fold",
        "momentum",
        {"lookback": 5, "threshold": "0"},
    )
    mlp = Candidate(
        "mlp-fold-artifact",
        "mlp",
        {"hidden": 4, "epochs": 2, "learning_rate": "0.01", "seed": 20260909},
    )
    monkeypatch.setattr(optimizer_module, "candidates", lambda: [selected, mlp])
    source = _source(sessions=240)
    store = OptimizerStore(tmp_path / "optimizer.db")

    assert optimize_walk_forward_snapshot(source, store, tmp_path / "artifacts", "cpu")
    status = store.status()

    assert status["status"] == "completed"
    assert status["validation_mode"] == "walk-forward"
    assert status["fold_progress"] == {"completed": 2, "total": 2}
    assert status["candidate_count"] == 4
    assert status["tail"]["count"] == 0
    assert status["summary"]["fold_count"] == 2
    assert status["summary"]["automatic_trading_eligible"] is False
    assert all(fold["winner_oos"]["trade_count"] > 0 for fold in status["folds"])
    assert all(
        fold["winner_risk"]["policy"] == ResearchRiskPolicy().as_json()
        for fold in status["folds"]
    )
    assert all(
        store.frozen_winner_id(row["optimizer_run_id"]) is not None
        for row in store.batch_fold_results(status["batch_id"])
    )
    artifacts = sorted((tmp_path / "artifacts").glob("*/*.json"))
    assert len(artifacts) == 2
    artifact_payloads = [
        json.loads(path.read_text(encoding="utf-8")) for path in artifacts
    ]
    assert len({payload["optimizer_run_id"] for payload in artifact_payloads}) == 2
    assert len({payload["training_end"] for payload in artifact_payloads}) == 2
    candidate_count = status["candidate_count"]
    assert not optimize_walk_forward_snapshot(
        source, store, tmp_path / "artifacts", "cpu"
    )
    assert store.status()["candidate_count"] == candidate_count


def test_missing_external_validation_marks_only_macro_candidate_ineligible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    control = Candidate(
        "external-control-test",
        "external_control",
        {"variant": "unfiltered_trend_20_control"},
    )
    macro = Candidate(
        "external-macro-test",
        "external_macro",
        {
            "variant": "rates",
            "observation_lookback": 20,
            "max_age_days": 7,
            "minimum_spread_pp": "-1",
            "maximum_10y_change_pp": "0.50",
        },
    )
    monkeypatch.setattr(optimizer_module, "candidates", lambda: [control, macro])
    raw_source = _source(sessions=240)
    source = SourceSnapshot(
        raw_source.run_id,
        raw_source.request,
        raw_source.snapshot,
        ExternalFeatureSnapshot(observations=()),
    )
    store = OptimizerStore(tmp_path / "optimizer.db")

    assert optimize_walk_forward_snapshot(source, store, tmp_path / "artifacts", "cpu")
    status = store.status()
    assert status["candidate_count"] == 4
    assert status["summary"]["evidence_class"] == (
        "reconstructed_historical_exploration"
    )
    assert status["summary"]["point_in_time_verified"] is False
    assert status["summary"]["prospective_validation_eligible"] is False
    assert all(fold["winner_id"] == control.id for fold in status["folds"])
    with sqlite3.connect(store.path) as connection:
        rows = connection.execute(
            """
            SELECT candidate_id, eligible, validation_result_json
            FROM optimizer_candidates ORDER BY optimizer_run_id, candidate_id
            """
        ).fetchall()
    macro_rows = [row for row in rows if row[0] == macro.id]
    assert len(macro_rows) == 2
    assert all(row[1] == 0 for row in macro_rows)
    assert all(
        json.loads(row[2])["external_diagnostics"]["missing_date_count"] == 41
        for row in macro_rows
    )


def test_walk_forward_resumes_at_fold_boundary_with_frozen_winner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selected = Candidate(
        "momentum-resume",
        "momentum",
        {"lookback": 5, "threshold": "0"},
    )
    monkeypatch.setattr(optimizer_module, "candidates", lambda: [selected])
    source = _source(sessions=240)
    store = OptimizerStore(tmp_path / "optimizer.db")

    def stop_after_first_fold() -> bool:
        with sqlite3.connect(store.path) as connection:
            completed = connection.execute(
                """
                SELECT COUNT(*) FROM optimizer_batch_folds
                WHERE status='completed'
                """
            ).fetchone()[0]
        return bool(completed)

    with pytest.raises(StopRequested):
        optimize_walk_forward_snapshot(
            source,
            store,
            tmp_path / "artifacts",
            "cpu",
            should_stop=stop_after_first_fold,
        )
    stopped = store.status()
    assert stopped["status"] == "stopped"
    assert stopped["fold_progress"] == {"completed": 1, "total": 2}
    first_row = store.batch_fold_results(stopped["batch_id"])[0]
    first_winner = store.frozen_winner_id(first_row["optimizer_run_id"])

    assert optimize_walk_forward_snapshot(source, store, tmp_path / "artifacts", "cpu")
    resumed = store.status()
    assert resumed["status"] == "completed"
    assert resumed["candidate_count"] == 2
    assert store.frozen_winner_id(first_row["optimizer_run_id"]) == first_winner


def test_status_uses_fold_heartbeat_and_newer_single_run(tmp_path: Path) -> None:
    store = OptimizerStore(tmp_path / "optimizer.db")
    policy = ResearchRiskPolicy()
    assert store.begin_batch(
        "batch",
        "source",
        "walk-content",
        validation_mode="walk-forward",
        risk=policy.as_json(),
        fold_count=1,
        tail={"count": 0, "first": None, "last": None},
    )
    store.register_fold(
        "batch",
        0,
        "fold-run",
        {
            "training": ("2025-01-01", "2025-04-30"),
            "validation": ("2025-05-01", "2025-06-09"),
            "oos": ("2025-06-10", "2025-07-19"),
        },
    )
    store.start_fold("batch", 0)
    assert store.begin("fold-run", "source", "fold-content")
    store.save_candidate(
        "fold-run",
        "candidate",
        "momentum",
        {"lookback": 5, "threshold": "0"},
        score="1",
        eligible=True,
        validation_result={"metrics": {}},
        artifact_path=None,
    )
    old = (datetime.now(UTC) - timedelta(minutes=10)).isoformat()
    recent = datetime.now(UTC).isoformat()
    with sqlite3.connect(store.path) as connection:
        connection.execute(
            "UPDATE optimizer_batches SET heartbeat_at=? WHERE id='batch'", (old,)
        )
        connection.execute(
            """
            UPDATE optimizer_runs SET heartbeat_at=?, device='cuda'
            WHERE id='fold-run'
            """,
            (recent,),
        )

    batch_status = store.status(stale_after=timedelta(minutes=3))
    assert batch_status["batch_id"] == "batch"
    assert batch_status["status"] == "running"
    assert batch_status["folds"][0]["candidate_count"] == 1
    assert batch_status["folds"][0]["device"] == "cuda"

    assert store.begin("single-run", "source", "single-content")
    future = (datetime.now(UTC) + timedelta(seconds=1)).isoformat()
    with sqlite3.connect(store.path) as connection:
        connection.execute(
            "UPDATE optimizer_runs SET heartbeat_at=? WHERE id='single-run'", (future,)
        )

    single_status = store.status(stale_after=timedelta(minutes=3))
    assert single_status["id"] == "single-run"
    assert "batch_id" not in single_status


def test_fold_heartbeat_refreshes_batch_and_running_daemon(tmp_path: Path) -> None:
    store = OptimizerStore(tmp_path / "optimizer.db")
    assert store.begin_batch(
        "batch",
        "source",
        "walk-content",
        validation_mode="walk-forward",
        risk=ResearchRiskPolicy().as_json(),
        fold_count=1,
        tail={"count": 0, "first": None, "last": None},
    )
    store.register_fold(
        "batch",
        0,
        "fold-run",
        {
            "training": ("2025-01-01", "2025-04-30"),
            "validation": ("2025-05-01", "2025-06-09"),
            "oos": ("2025-06-10", "2025-07-19"),
        },
    )
    assert store.begin("fold-run", "source", "fold-content")
    store.daemon_heartbeat(True)
    old = (datetime.now(UTC) - timedelta(minutes=10)).isoformat()
    with sqlite3.connect(store.path) as connection:
        connection.execute("UPDATE optimizer_batches SET heartbeat_at=?", (old,))
        connection.execute("UPDATE optimizer_batch_folds SET updated_at=?", (old,))
        connection.execute(
            "UPDATE optimizer_control SET updated_at=? WHERE key='daemon'", (old,)
        )

    store.heartbeat("fold-run", device="cuda")

    with sqlite3.connect(store.path) as connection:
        batch_heartbeat = connection.execute(
            "SELECT heartbeat_at FROM optimizer_batches WHERE id='batch'"
        ).fetchone()[0]
        fold_heartbeat = connection.execute(
            "SELECT updated_at FROM optimizer_batch_folds WHERE batch_id='batch'"
        ).fetchone()[0]
        daemon_heartbeat = connection.execute(
            "SELECT updated_at FROM optimizer_control WHERE key='daemon'"
        ).fetchone()[0]
    assert batch_heartbeat > old
    assert fold_heartbeat > old
    assert daemon_heartbeat > old


def test_snapshot_validation_rejects_duplicate_missing_and_adjustment_change() -> None:
    source = _source()
    item = source.snapshot.symbols[0]
    duplicate = source.snapshot.model_copy(
        update={
            "symbols": [item.model_copy(update={"bars": [*item.bars, item.bars[-1]]})]
        }
    )
    with pytest.raises(DataInsufficientError, match="중복"):
        validate_and_split(SourceSnapshot("duplicate", source.request, duplicate))

    missing = source.snapshot.model_copy(update={"symbols": []})
    with pytest.raises(DataInsufficientError, match="누락"):
        validate_and_split(SourceSnapshot("missing", source.request, missing))

    changed_bar = item.bars[-1].model_copy(update={"adjusted_close": Decimal("200")})
    changed = source.snapshot.model_copy(
        update={
            "symbols": [
                item.model_copy(update={"bars": [*item.bars[:-1], changed_bar]})
            ]
        }
    )
    with pytest.raises(DataInsufficientError, match="비율"):
        validate_and_split(SourceSnapshot("adjustment", source.request, changed))


@pytest.mark.parametrize("device", ["cpu", "cuda"])
def test_real_mlp_training_smoke(device: str) -> None:
    torch = pytest.importorskip("torch")
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA is unavailable")
    source = _source()
    split = validate_and_split(source)
    candidate = Candidate(
        "mlp-smoke",
        "mlp",
        {"hidden": 4, "epochs": 2, "learning_rate": "0.01", "seed": 20260909},
    )

    artifact, actual_device = train_mlp(
        candidate, source.snapshot, split.training, device
    )
    prediction = mlp_signal(artifact)(
        "005930", tuple(source.snapshot.symbols[0].bars[:80])
    )

    assert actual_device == device
    assert artifact["source_engine_hash"]
    assert artifact["seed"] == 20260909
    assert isinstance(prediction, bool)


def test_store_deduplicates_content_and_resumes_candidates(tmp_path: Path) -> None:
    store = OptimizerStore(tmp_path / "optimizer.db")
    source = _source()
    first_id, first_content = content_identity(source, "cpu")
    recaptured = source.snapshot.model_copy(
        update={"captured_at": datetime(2026, 1, 2, tzinfo=UTC)}
    )
    second_id, second_content = content_identity(
        SourceSnapshot("other", source.request, recaptured), "cpu"
    )

    assert (first_id, first_content) == (second_id, second_content)
    assert store.begin(first_id, source.run_id, first_content)
    store.save_candidate(
        first_id,
        "candidate",
        "momentum",
        {"lookback": 5},
        score="1.0000000000000000001",
        eligible=True,
        validation_result={"complete": True},
        artifact_path=None,
    )
    store.fail(first_id, "interrupted", stopped=True)
    assert store.begin(first_id, source.run_id, first_content)
    assert store.completed_candidate_ids(first_id) == {"candidate"}


def test_stop_is_cooperative_and_lock_is_exclusive(tmp_path: Path) -> None:
    store = OptimizerStore(tmp_path / "optimizer.db")
    with pytest.raises(StopRequested):
        optimize_snapshot(
            _source(),
            store,
            tmp_path / "artifacts",
            "cpu",
            should_stop=lambda: True,
        )
    assert store.status()["status"] == "stopped"

    lock_path = tmp_path / "optimizer.lock"
    with lock_path.open("a+") as first, lock_path.open("a+") as second:
        fcntl.flock(first, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(BlockingIOError):
            fcntl.flock(second, fcntl.LOCK_EX | fcntl.LOCK_NB)


def test_status_exposes_failed_final_comparison(tmp_path: Path) -> None:
    store = OptimizerStore(tmp_path / "optimizer.db")
    source = _source()
    run_id, content_hash = content_identity(source, "cpu")
    assert store.begin(run_id, source.run_id, content_hash)
    metrics = {
        "initial_cash": "1",
        "final_equity": "1",
        "total_return_pct": "2",
        "max_drawdown_pct": "3",
        "trade_count": 1,
        "total_fees": "0",
        "total_tax": "0",
        "total_slippage_cost": "0",
    }
    baseline = {"metrics": metrics}
    worse_drawdown = json.loads(json.dumps(baseline))
    worse_drawdown["metrics"]["total_return_pct"] = "4"
    worse_drawdown["metrics"]["max_drawdown_pct"] = "5"
    store.complete(
        run_id,
        device="cpu",
        split={},
        winner_id="winner",
        baseline_final=baseline,
        winner_final=worse_drawdown,
    )

    assert store.status()["latest_completed"]["winner_passed_final"] is False


def test_daemon_records_malformed_source_and_continues(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _source()
    research_db = tmp_path / "research.db"
    with sqlite3.connect(research_db) as connection:
        connection.execute(
            """
            CREATE TABLE research_runs (
                id TEXT, status TEXT, request_json TEXT, input_json TEXT,
                created_at TEXT
            )
            """
        )
        connection.executemany(
            "INSERT INTO research_runs VALUES (?, 'completed', ?, ?, ?)",
            [
                ("bad", "{}", "{}", "2026-01-01"),
                (
                    "good",
                    source.request.model_dump_json(),
                    source.snapshot.model_dump_json(),
                    "2026-01-02",
                ),
            ],
        )
    seen: list[str] = []

    def fake_optimize(
        selected: SourceSnapshot,
        _store: OptimizerStore,
        _artifact_dir: Path,
        _device: str,
        _should_stop: object,
    ) -> bool:
        seen.append(selected.run_id)
        return True

    monkeypatch.setattr(optimizer_module, "optimize_snapshot", fake_optimize)
    monkeypatch.setattr(
        optimizer_module, "_resolve_device", lambda _device: ("cpu", object())
    )

    assert (
        run_daemon(
            research_db,
            tmp_path / "optimizer.db",
            tmp_path / "artifacts",
            device="cpu",
            once=True,
        )
        == 0
    )
    assert seen == ["good"]
    assert OptimizerStore(tmp_path / "optimizer.db").status()["run_counts"] == {
        "insufficient": 1
    }


def test_explicit_unavailable_cuda_exits_nonzero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def unavailable(_device: str) -> tuple[str, object]:
        raise RuntimeError("요청한 CUDA 장치를 사용할 수 없습니다.")

    monkeypatch.setattr(optimizer_module, "_resolve_device", unavailable)

    result = optimizer_module.main(
        [
            "--research-db",
            str(tmp_path / "research.db"),
            "--optimizer-db",
            str(tmp_path / "optimizer.db"),
            "run",
            "--once",
            "--device",
            "cuda",
        ]
    )

    assert result == 1
    assert "CUDA" in capsys.readouterr().err


@pytest.mark.parametrize("failure", ["missing", "corrupt"])
def test_invalid_completed_mlp_artifact_is_retrained(
    tmp_path: Path, failure: str
) -> None:
    source = _source()
    split = validate_and_split(source)
    candidate = Candidate(
        "mlp-resume",
        "mlp",
        {"hidden": 4, "epochs": 2, "learning_rate": "0.01", "seed": 20260909},
    )
    artifact, _device = train_mlp(candidate, source.snapshot, split.training, "cpu")
    run_id, content_hash = content_identity(source, "cpu")
    artifact["optimizer_run_id"] = run_id
    artifact_path = tmp_path / "model.json"
    artifact_path.write_text(json.dumps(artifact), encoding="utf-8")
    store = OptimizerStore(tmp_path / "optimizer.db")
    assert store.begin(run_id, source.run_id, content_hash)
    store.save_candidate(
        run_id,
        candidate.id,
        candidate.family,
        candidate.parameters,
        score="1",
        eligible=True,
        validation_result={"complete": True},
        artifact_path=artifact_path,
    )
    if failure == "missing":
        artifact_path.unlink()
    else:
        artifact_path.write_text("{}", encoding="utf-8")

    assert _resumable_candidate_ids(store, run_id, split, [candidate]) == set()
    assert store.completed_candidate_ids(run_id) == set()
    with pytest.raises(RuntimeError, match="artifact"):
        _load_artifact(
            str(artifact_path),
            candidate=candidate,
            run_id=run_id,
            training_end=split.training.end_date,
        )
