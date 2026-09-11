import json
import math
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from jusik.research_data import DataInsufficientError
from jusik.research_models import (
    DailyBar,
    ResearchInputSnapshot,
    ResearchRunRequest,
    SymbolSnapshot,
)
from jusik.research_optimizer import (
    Candidate,
    SourceSnapshot,
    _load_artifact,
    _resumable_candidate_ids,
    _run_candidate,
    candidates,
    content_identity,
    validate_and_split,
)
from jusik.research_optimizer_ml import (
    FEATURE_ORDER,
    features_v2,
    mlp_v2_signal,
    training_examples_v2,
)
from jusik.research_optimizer_store import OptimizerStore


def _bar(day: date, adjusted_open: Decimal, *, volume: int = 1000) -> DailyBar:
    return DailyBar(
        date=day,
        open=adjusted_open,
        high=adjusted_open + Decimal(1),
        low=adjusted_open - Decimal(1),
        close=adjusted_open,
        volume=volume,
        adjusted_open=adjusted_open,
        adjusted_high=adjusted_open + Decimal(1),
        adjusted_low=adjusted_open - Decimal(1),
        adjusted_close=adjusted_open,
    )


def _source(*, sessions: int = 200) -> SourceSnapshot:
    first = date(2025, 1, 1)
    bars = [
        _bar(first + timedelta(days=index), Decimal(100 + index % 13))
        for index in range(60 + sessions)
    ]
    request = ResearchRunRequest(
        symbols=["005930"],
        start_date=bars[60].date,
        end_date=bars[-1].date,
        initial_cash=Decimal("1000000"),
        fee_rate=Decimal("0.001"),
        slippage_rate=Decimal("0.001"),
        sell_tax_rate=Decimal("0.001"),
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
    return SourceSnapshot("ml-v2", request, snapshot)


def _v2_candidate(horizon: int = 1) -> Candidate:
    return next(
        item
        for item in candidates()[86:]
        if item.parameters["horizon"] == horizon
        and item.parameters["threshold"] == "0.55"
    )


def test_v2_features_include_stdev_and_range_with_zero_volume() -> None:
    first = date(2025, 1, 1)
    bars = tuple(
        _bar(first + timedelta(days=index), Decimal(100), volume=0)
        for index in range(61)
    )

    values = features_v2(bars)

    assert values is not None
    assert len(values) == len(FEATURE_ORDER) == 10
    assert values[6] == 0
    assert values[7] == 0
    assert values[8] == 0
    assert values[9] == pytest.approx(0.02)
    assert all(math.isfinite(value) for value in values)


def test_costs_flip_small_positive_label_and_horizon_is_purged() -> None:
    first = date(2025, 1, 1)
    opens = [Decimal(100) for _ in range(67)]
    opens[62] = Decimal("100.1")
    opens[66] = Decimal(101)
    item = SymbolSnapshot(
        symbol="005930",
        market="KOSPI",
        bars=[
            _bar(first + timedelta(days=index), value)
            for index, value in enumerate(opens)
        ],
        source_url="https://example.com/daily",
    )
    request = ResearchRunRequest(
        symbols=["005930"],
        start_date=item.bars[60].date,
        end_date=item.bars[66].date,
        fee_rate=Decimal("0.001"),
        slippage_rate=Decimal("0.001"),
        sell_tax_rate=Decimal("0.001"),
    )
    no_cost = request.model_copy(
        update={
            "fee_rate": Decimal(),
            "slippage_rate": Decimal(),
            "sell_tax_rate": Decimal(),
        }
    )

    assert training_examples_v2([item], request, horizon=1)[1][0] == 0
    assert training_examples_v2([item], no_cost, horizon=1)[1][0] == 1
    assert training_examples_v2([item], no_cost, horizon=5)[1] == [1]
    with pytest.raises(DataInsufficientError):
        training_examples_v2(
            [item],
            no_cost.model_copy(update={"end_date": item.bars[65].date}),
            horizon=5,
        )


def test_v2_labels_are_split_neutral_and_ignore_future_bars() -> None:
    source = _source()
    split = validate_and_split(source)
    item = source.snapshot.symbols[0]
    original = training_examples_v2([item], split.training, horizon=5)
    changed = item.model_copy(
        update={
            "bars": [
                bar.model_copy(
                    update={
                        "open": bar.open / Decimal(10),
                        "high": bar.high / Decimal(10),
                        "low": bar.low / Decimal(10),
                        "close": bar.close / Decimal(10),
                        "adjusted_open": bar.adjusted_open / Decimal(10),
                        "adjusted_high": bar.adjusted_high / Decimal(10),
                        "adjusted_low": bar.adjusted_low / Decimal(10),
                        "adjusted_close": bar.adjusted_close / Decimal(10),
                    }
                )
                if bar.date > split.training.end_date
                else bar
                for bar in item.bars
            ]
        }
    )

    assert training_examples_v2([changed], split.training, horizon=5) == original
    raw_split = item.model_copy(
        update={
            "bars": [
                bar.model_copy(
                    update={
                        "open": bar.open / Decimal(10),
                        "high": bar.high / Decimal(10),
                        "low": bar.low / Decimal(10),
                        "close": bar.close / Decimal(10),
                    }
                )
                if index >= 100
                else bar
                for index, bar in enumerate(item.bars)
            ]
        }
    )
    assert training_examples_v2([raw_split], split.training, horizon=5) == original


def test_v2_torch_model_matches_pure_inference_and_threshold_equality() -> None:
    torch = pytest.importorskip("torch")
    source = _source()
    split = validate_and_split(source)
    candidate = _v2_candidate()
    result, artifact, device, _risk = _run_candidate(
        candidate, source, split, "cpu", lambda: False
    )
    assert artifact is not None and device == "cpu"
    bars = tuple(source.snapshot.symbols[0].bars[:100])
    values = features_v2(bars)
    assert values is not None
    normalized = [
        (value - artifact["feature_mean"][index]) / artifact["feature_scale"][index]
        for index, value in enumerate(values)
    ]
    first, second = artifact["layers"]
    tensor = torch.tensor(normalized, dtype=torch.float32)
    hidden = torch.tanh(
        torch.tensor(first["weight"]) @ tensor + torch.tensor(first["bias"])
    )
    probability = torch.sigmoid(
        torch.tensor(second["weight"])[0] @ hidden + torch.tensor(second["bias"])[0]
    ).item()
    expected = probability >= float(artifact["threshold"])

    assert mlp_v2_signal(artifact)("005930", bars) is expected
    assert result.strategy_version == candidate.id

    boundary = json.loads(json.dumps(artifact))
    boundary["layers"][0]["weight"] = [[0.0] * len(FEATURE_ORDER) for _ in range(16)]
    boundary["layers"][0]["bias"] = [0.0] * 16
    boundary["layers"][1]["weight"] = [[0.0] * 16]
    boundary["layers"][1]["bias"] = [0.0]
    boundary["threshold"] = "0.5"
    assert mlp_v2_signal(boundary)("005930", bars)


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("feature_order", ["wrong"] * 10),
        ("feature_dimension", 9),
        ("horizon", 99),
        ("threshold", "0.99"),
        ("cost_assumptions", {}),
    ],
)
def test_invalid_v2_artifact_is_removed_for_deterministic_resume(
    tmp_path: Path, field: str, invalid: object
) -> None:
    source = _source()
    split = validate_and_split(source)
    candidate = _v2_candidate()
    _result, artifact, _device, _risk = _run_candidate(
        candidate, source, split, "cpu", lambda: False
    )
    assert artifact is not None
    run_id, content_hash = content_identity(source, "cpu")
    artifact["optimizer_run_id"] = run_id
    artifact[field] = invalid
    path = tmp_path / "model-v2.json"
    path.write_text(json.dumps(artifact), encoding="utf-8")
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
        artifact_path=path,
    )

    assert _resumable_candidate_ids(store, run_id, split, [candidate]) == set()
    assert store.completed_candidate_ids(run_id) == set()
    with pytest.raises(RuntimeError, match="artifact"):
        _load_artifact(
            str(path),
            candidate=candidate,
            run_id=run_id,
            training_end=split.training.end_date,
            training=split.training,
        )
