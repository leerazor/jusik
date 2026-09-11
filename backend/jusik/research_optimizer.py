from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import math
import os
import signal as process_signal
import sqlite3
import sys
import time
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import FrameType
from typing import Any, Literal, cast

from pydantic import ValidationError

from jusik.research_data import DataInsufficientError
from jusik.research_engine import (
    IMPLEMENTATION_HASH,
    SignalFunction,
    run_signal_backtest,
)
from jusik.research_external_features import (
    ExternalSignalDiagnostics,
    MacroGate,
    control_candidate_parameters,
    macro_candidate_parameters,
    macro_signal,
    validation_coverage,
)
from jusik.research_external_models import (
    ExternalFeatureSnapshot,
    external_evidence_metadata,
)
from jusik.research_models import (
    BASELINE_VERSION,
    DailyBar,
    ResearchInputSnapshot,
    ResearchRunRequest,
    StrategyResult,
    SymbolSnapshot,
)
from jusik.research_optimizer_ml import (
    MLP_V2_FORMAT,
    MLP_V2_VARIANT,
    MlTrainingStopped,
    mlp_v2_signal,
    train_mlp_v2,
    validate_mlp_v2_artifact,
)
from jusik.research_optimizer_store import OptimizerStore
from jusik.research_risk import ResearchRiskPolicy, ResearchRiskReport
from jusik.research_strategy import target_invested
from jusik.research_universe_models import (
    OfflineInstrumentSnapshot,
    OfflineResearchRequest,
    OfflineResearchSnapshot,
)

DEFAULT_RESEARCH_DB = Path.home() / ".local/share/jusik/research.db"
DEFAULT_OPTIMIZER_DB = Path.home() / ".local/share/jusik/research-optimizer.db"
DEFAULT_ARTIFACT_DIR = Path.home() / ".local/share/jusik/optimizer-artifacts"
MIN_SPLIT = (120, 40, 40)
WALK_FORWARD_MIN_SESSIONS = 240
WALK_FORWARD_STEP = 40
SEED = 20260909
POLL_SECONDS = 60
OPTIMIZER_VERSION = "offline_optimizer_v1"
DeviceChoice = Literal["auto", "cpu", "cuda"]
ValidationMode = Literal["single", "walk-forward"]
OptimizerRequest = ResearchRunRequest | OfflineResearchRequest
OptimizerSnapshot = ResearchInputSnapshot | OfflineResearchSnapshot


@dataclass(frozen=True)
class Candidate:
    id: str
    family: str
    parameters: dict[str, object]


@dataclass(frozen=True)
class SourceSnapshot:
    run_id: str
    request: OptimizerRequest
    snapshot: OptimizerSnapshot
    external: ExternalFeatureSnapshot | None = None


@dataclass(frozen=True)
class Split:
    training: OptimizerRequest
    validation: OptimizerRequest
    final: OptimizerRequest

    def as_json(self) -> dict[str, object]:
        return {
            "training": [
                self.training.start_date.isoformat(),
                self.training.end_date.isoformat(),
            ],
            "validation": [
                self.validation.start_date.isoformat(),
                self.validation.end_date.isoformat(),
            ],
            "final": [
                self.final.start_date.isoformat(),
                self.final.end_date.isoformat(),
            ],
            "evidence_limitation": (
                "날짜가 겹치는 후속 스냅샷의 최종 구간은 독립적인 전진 검증이 아닙니다."
            ),
        }


@dataclass(frozen=True)
class WalkForwardFold:
    index: int
    split: Split

    def date_ranges(self) -> dict[str, tuple[str, str]]:
        return {
            "training": (
                self.split.training.start_date.isoformat(),
                self.split.training.end_date.isoformat(),
            ),
            "validation": (
                self.split.validation.start_date.isoformat(),
                self.split.validation.end_date.isoformat(),
            ),
            "oos": (
                self.split.final.start_date.isoformat(),
                self.split.final.end_date.isoformat(),
            ),
        }

    def as_json(self) -> dict[str, object]:
        return {"fold_index": self.index, **self.date_ranges()}


class StopRequested(Exception):
    pass


def _canonical_hash(value: object) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def _code_hash() -> str:
    digest = hashlib.sha256()
    for name in (
        "research_engine.py",
        "research_external_data.py",
        "research_external_features.py",
        "research_external_models.py",
        "research_external_store.py",
        "research_optimizer.py",
        "research_optimizer_ml.py",
        "research_optimizer_store.py",
        "research_risk.py",
        "research_strategy.py",
        "research_universe.py",
        "research_universe_data.py",
        "research_universe_models.py",
        "research_universe_store.py",
    ):
        path = Path(__file__).with_name(name)
        digest.update(name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def candidates() -> list[Candidate]:
    result: list[Candidate] = []
    for fast in (5, 10, 20):
        for slow in (None, 20, 40, 60):
            if slow is not None and fast >= slow:
                continue
            for volume_ratio in (None, "0.8", "1.0", "1.2"):
                parameters: dict[str, object] = {
                    "fast": fast,
                    "slow": slow,
                    "volume_ratio": volume_ratio,
                }
                result.append(_candidate("ma_volume", parameters))
    for lookback in (5, 10, 20):
        for threshold in ("0", "0.02", "0.05"):
            result.append(
                _candidate("momentum", {"lookback": lookback, "threshold": threshold})
            )
    for lookback in (10, 20, 40):
        result.append(_candidate("breakout", {"lookback": lookback}))
    for window in (5, 10, 20):
        for discount in ("0.02", "0.05", "0.10"):
            result.append(
                _candidate("mean_reversion", {"window": window, "discount": discount})
            )
    for hidden, epochs, learning_rate in (
        (8, 24, "0.01"),
        (16, 32, "0.005"),
        (24, 40, "0.003"),
    ):
        result.append(
            _candidate(
                "mlp",
                {
                    "hidden": hidden,
                    "epochs": epochs,
                    "learning_rate": learning_rate,
                    "seed": SEED,
                },
            )
        )
    for window in (7, 14, 21):
        for threshold in ("30", "40", "45"):
            result.append(
                _candidate(
                    "rsi_pullback",
                    {
                        "window": window,
                        "threshold": threshold,
                        "trend_window": 60,
                    },
                )
            )
    for window in (10, 14, 20):
        for max_ratio in ("0.03", "0.05", "0.08"):
            result.append(
                _candidate(
                    "atr_trend",
                    {
                        "window": window,
                        "max_ratio": max_ratio,
                        "trend_window": 20,
                    },
                )
            )
    for horizon, threshold in ((1, "0.55"), (5, "0.55"), (5, "0.60")):
        result.append(
            _candidate(
                "mlp",
                {
                    "variant": MLP_V2_VARIANT,
                    "horizon": horizon,
                    "threshold": threshold,
                    "hidden": 16,
                    "epochs": 32,
                    "learning_rate": "0.005",
                    "weight_decay": "0.01",
                    "seed": SEED,
                },
            )
        )
    result.append(
        _candidate(
            "external_control",
            control_candidate_parameters(),
        )
    )
    external_gates: tuple[MacroGate, ...] = ("rates", "fx_vix", "stress")
    for gate in external_gates:
        result.append(
            _candidate(
                "external_macro",
                macro_candidate_parameters(gate),
            )
        )
    return result


def _candidate(family: str, parameters: dict[str, object]) -> Candidate:
    suffix = _canonical_hash({"family": family, "parameters": parameters})[:12]
    return Candidate(f"{family}-{suffix}", family, parameters)


def _library_versions() -> dict[str, str]:
    versions = {"python": sys.version.split()[0]}
    try:
        import torch

        versions["torch"] = str(torch.__version__)
        versions["cuda"] = str(torch.version.cuda)
    except ImportError:
        versions["torch"] = "unavailable"
        versions["cuda"] = "unavailable"
    return versions


def optimizer_config(
    device_choice: DeviceChoice = "auto",
    validation_mode: ValidationMode = "single",
    risk_policy: ResearchRiskPolicy | None = None,
) -> dict[str, object]:
    return {
        "version": OPTIMIZER_VERSION,
        "seed": SEED,
        "minimum_split_sessions": MIN_SPLIT,
        "device_choice": device_choice,
        "validation_mode": validation_mode,
        "risk_policy": risk_policy.as_json() if risk_policy else None,
        "candidates": [
            {"id": item.id, "family": item.family, "parameters": item.parameters}
            for item in candidates()
        ],
    }


def _source_content_hash(source: SourceSnapshot) -> str:
    snapshot = source.snapshot.model_dump(mode="json", exclude={"captured_at"})
    payload: dict[str, object] = {
        "request": source.request.model_dump(mode="json"),
        "snapshot": snapshot,
    }
    if source.external is not None:
        payload["external"] = source.external.semantic_payload()
    return _canonical_hash(payload)


def content_identity(
    source: SourceSnapshot, device_choice: DeviceChoice = "auto"
) -> tuple[str, str]:
    content_hash = _source_content_hash(source)
    run_id = _canonical_hash(
        {
            "content_hash": content_hash,
            "code_hash": _code_hash(),
            "libraries": _library_versions(),
            "config": optimizer_config(device_choice),
        }
    )
    return run_id, content_hash


def walk_forward_identity(
    source: SourceSnapshot,
    device_choice: DeviceChoice,
    risk_policy: ResearchRiskPolicy,
) -> tuple[str, str]:
    content_hash = _source_content_hash(source)
    batch_id = _canonical_hash(
        {
            "content_hash": content_hash,
            "code_hash": _code_hash(),
            "libraries": _library_versions(),
            "config": optimizer_config(device_choice, "walk-forward", risk_policy),
        }
    )
    return batch_id, content_hash


def read_source_snapshots(
    path: Path, on_invalid: Callable[[str], None] | None = None
) -> Iterator[SourceSnapshot]:
    uri = f"file:{path.resolve()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT id, request_json, input_json FROM research_runs
            WHERE status='completed' AND input_json IS NOT NULL
            ORDER BY created_at, id
            """
        ).fetchall()
    for row in rows:
        try:
            yield SourceSnapshot(
                run_id=str(row["id"]),
                request=ResearchRunRequest.model_validate_json(row["request_json"]),
                snapshot=ResearchInputSnapshot.model_validate_json(row["input_json"]),
            )
        except (ValidationError, ValueError, TypeError):
            if on_invalid is not None:
                on_invalid(str(row["id"]))
            continue


def _validated_dates(source: SourceSnapshot) -> list[date]:
    request = source.request
    snapshot = source.snapshot
    if snapshot.captured_at.tzinfo is None:
        raise DataInsufficientError("입력 스냅샷 수집 시각에 시간대가 없습니다.")
    if isinstance(snapshot, OfflineResearchSnapshot):
        if not isinstance(request, OfflineResearchRequest):
            raise DataInsufficientError("외부 입력 요청과 스냅샷 형식이 다릅니다.")
        if (
            snapshot.evaluation_start != request.start_date
            or snapshot.requested_end != request.end_date
            or snapshot.requested_start > snapshot.evaluation_start
        ):
            raise DataInsufficientError("외부 입력의 요청·평가 기간이 다릅니다.")
        if snapshot.instruments[0].instrument != request.instrument:
            raise DataInsufficientError("외부 입력 종목 metadata가 요청과 다릅니다.")
    elif (
        snapshot.requested_start != request.start_date
        or snapshot.requested_end != request.end_date
    ):
        raise DataInsufficientError("입력 스냅샷과 연구 요청 기간이 다릅니다.")
    if snapshot.events != request.events:
        raise DataInsufficientError("입력 스냅샷과 연구 요청의 시장 이벤트가 다릅니다.")
    symbols = [item.symbol for item in snapshot.symbols]
    if len(symbols) != len(set(symbols)) or sorted(symbols) != sorted(request.symbols):
        raise DataInsufficientError("입력 스냅샷의 종목이 누락되거나 중복되었습니다.")
    comparison_dates: set[date] | None = None
    for item in snapshot.symbols:
        dates = [bar.date for bar in item.bars]
        if len(dates) != len(set(dates)):
            raise DataInsufficientError(f"{item.symbol}의 일봉 날짜가 중복되었습니다.")
        warmup = sum(bar_date < request.start_date for bar_date in dates)
        if warmup < 60:
            raise DataInsufficientError(
                f"{item.symbol}의 준비 일봉이 60개보다 적습니다."
            )
        if isinstance(snapshot, OfflineResearchSnapshot):
            actions = snapshot.basis_actions
            factors = {
                entry.date: entry.raw_factor for entry in snapshot.adjustment_factors
            }
            for bar in item.bars:
                expected = Decimal(1)
                for action in actions:
                    if action.date > bar.date:
                        expected *= action.factor
                if factors.get(bar.date) != expected:
                    raise DataInsufficientError(
                        f"{item.symbol}의 기업행동 조정계수를 검증할 수 없습니다."
                    )
        else:
            ratios = [bar.adjusted_close / bar.close for bar in item.bars]
            if not ratios or max(ratios) - min(ratios) > Decimal("0.0001"):
                raise DataInsufficientError(
                    f"{item.symbol}의 원주가와 수정주가 비율을 검증할 수 없습니다."
                )
        selected = {
            bar_date
            for bar_date in dates
            if request.start_date <= bar_date <= request.end_date
        }
        if comparison_dates is None:
            comparison_dates = selected
        elif selected != comparison_dates:
            raise DataInsufficientError("종목별 비교 기간 일봉 날짜가 서로 다릅니다.")
    return sorted(comparison_dates or set())


def validate_and_split(source: SourceSnapshot) -> Split:
    request = source.request
    dates = _validated_dates(source)
    required = sum(MIN_SPLIT)
    if len(dates) < required:
        raise DataInsufficientError(
            f"시간순 60/20/20 검증에는 거래일 {required}개가 필요합니다."
        )
    train_size = max(MIN_SPLIT[0], int(len(dates) * 0.6))
    validation_size = max(MIN_SPLIT[1], int(len(dates) * 0.2))
    if len(dates) - train_size - validation_size < MIN_SPLIT[2]:
        validation_size = len(dates) - train_size - MIN_SPLIT[2]
    return Split(
        training=request.model_copy(update={"end_date": dates[train_size - 1]}),
        validation=request.model_copy(
            update={
                "start_date": dates[train_size],
                "end_date": dates[train_size + validation_size - 1],
            }
        ),
        final=request.model_copy(
            update={"start_date": dates[train_size + validation_size]}
        ),
    )


def walk_forward_folds(
    source: SourceSnapshot,
) -> tuple[list[WalkForwardFold], dict[str, object]]:
    dates = _validated_dates(source)
    if len(dates) < WALK_FORWARD_MIN_SESSIONS:
        raise DataInsufficientError(
            "확장형 walk-forward 검증에는 거래일 240개가 필요합니다."
        )
    request = source.request
    folds: list[WalkForwardFold] = []
    train_size = MIN_SPLIT[0]
    while train_size + MIN_SPLIT[1] + MIN_SPLIT[2] <= len(dates):
        validation_start = train_size
        oos_start = validation_start + MIN_SPLIT[1]
        oos_end = oos_start + MIN_SPLIT[2]
        folds.append(
            WalkForwardFold(
                index=len(folds),
                split=Split(
                    training=request.model_copy(
                        update={"end_date": dates[train_size - 1]}
                    ),
                    validation=request.model_copy(
                        update={
                            "start_date": dates[validation_start],
                            "end_date": dates[oos_start - 1],
                        }
                    ),
                    final=request.model_copy(
                        update={
                            "start_date": dates[oos_start],
                            "end_date": dates[oos_end - 1],
                        }
                    ),
                ),
            )
        )
        train_size += WALK_FORWARD_STEP
    used = MIN_SPLIT[0] + len(folds) * WALK_FORWARD_STEP + MIN_SPLIT[1]
    tail_dates = dates[used:]
    tail: dict[str, object] = {
        "count": len(tail_dates),
        "first_date": tail_dates[0].isoformat() if tail_dates else None,
        "last_date": tail_dates[-1].isoformat() if tail_dates else None,
    }
    return folds, tail


def _sma(bars: Sequence[DailyBar], length: int) -> Decimal | None:
    if len(bars) < length:
        return None
    return sum((bar.adjusted_close for bar in bars[-length:]), Decimal()) / Decimal(
        length
    )


def _int_parameter(value: object, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"Invalid integer candidate parameter: {name}")
    return value


def _wilder_rsi(bars: Sequence[DailyBar], window: int) -> Decimal | None:
    if len(bars) < window + 1:
        return None
    changes = [
        current.adjusted_close - previous.adjusted_close
        for previous, current in zip(bars[:-1], bars[1:], strict=True)
    ]
    gains = [max(change, Decimal()) for change in changes[:window]]
    losses = [max(-change, Decimal()) for change in changes[:window]]
    average_gain = sum(gains, Decimal()) / Decimal(window)
    average_loss = sum(losses, Decimal()) / Decimal(window)
    for change in changes[window:]:
        gain = max(change, Decimal())
        loss = max(-change, Decimal())
        average_gain = (average_gain * Decimal(window - 1) + gain) / Decimal(window)
        average_loss = (average_loss * Decimal(window - 1) + loss) / Decimal(window)
    if average_gain == 0 and average_loss == 0:
        return Decimal(50)
    if average_loss == 0:
        return Decimal(100)
    if average_gain == 0:
        return Decimal()
    relative_strength = average_gain / average_loss
    return Decimal(100) - Decimal(100) / (Decimal(1) + relative_strength)


def _wilder_atr(bars: Sequence[DailyBar], window: int) -> Decimal | None:
    if len(bars) < window + 1:
        return None
    true_ranges = [
        max(
            current.adjusted_high - current.adjusted_low,
            abs(current.adjusted_high - previous.adjusted_close),
            abs(current.adjusted_low - previous.adjusted_close),
        )
        for previous, current in zip(bars[:-1], bars[1:], strict=True)
    ]
    average = sum(true_ranges[:window], Decimal()) / Decimal(window)
    for true_range in true_ranges[window:]:
        average = (average * Decimal(window - 1) + true_range) / Decimal(window)
    return average


def rule_signal(candidate: Candidate) -> SignalFunction:
    parameters = candidate.parameters
    if candidate.family == "ma_volume":
        fast = _int_parameter(parameters["fast"], "fast")
        slow_value = parameters["slow"]
        slow = _int_parameter(slow_value, "slow") if slow_value is not None else None
        ratio_value = parameters["volume_ratio"]
        minimum_ratio = Decimal(str(ratio_value)) if ratio_value is not None else None

        def ma_volume(_symbol: str, bars: tuple[DailyBar, ...]) -> bool:
            fast_average = _sma(bars, fast)
            if fast_average is None or bars[-1].adjusted_close <= fast_average:
                return False
            if slow is not None:
                slow_average = _sma(bars, slow)
                if slow_average is None or fast_average <= slow_average:
                    return False
            if minimum_ratio is not None:
                window = bars[-fast:]
                average_volume = Decimal(sum(bar.volume for bar in window)) / Decimal(
                    len(window)
                )
                if average_volume <= 0:
                    return False
                return Decimal(bars[-1].volume) / average_volume >= minimum_ratio
            return True

        return ma_volume
    if candidate.family == "momentum":
        lookback = _int_parameter(parameters["lookback"], "lookback")
        threshold = Decimal(str(parameters["threshold"]))

        def momentum(_symbol: str, bars: tuple[DailyBar, ...]) -> bool:
            if len(bars) <= lookback:
                return False
            change = bars[-1].adjusted_close / bars[-lookback - 1].adjusted_close - 1
            return bool(change > threshold)

        return momentum
    if candidate.family == "breakout":
        lookback = _int_parameter(parameters["lookback"], "lookback")

        def breakout(_symbol: str, bars: tuple[DailyBar, ...]) -> bool:
            if len(bars) <= lookback:
                return False
            previous_high = max(bar.adjusted_high for bar in bars[-lookback - 1 : -1])
            return bars[-1].adjusted_close > previous_high

        return breakout
    if candidate.family == "mean_reversion":
        window = _int_parameter(parameters["window"], "window")
        discount = Decimal(str(parameters["discount"]))

        def mean_reversion(_symbol: str, bars: tuple[DailyBar, ...]) -> bool:
            average = _sma(bars, window)
            return average is not None and bars[-1].adjusted_close < average * (
                1 - discount
            )

        return mean_reversion
    if candidate.family == "rsi_pullback":
        window = _int_parameter(parameters["window"], "window")
        threshold = Decimal(str(parameters["threshold"]))
        trend_window = _int_parameter(parameters["trend_window"], "trend_window")

        def rsi_pullback(_symbol: str, bars: tuple[DailyBar, ...]) -> bool:
            trend = _sma(bars, trend_window)
            rsi = _wilder_rsi(bars, window)
            return bool(
                trend is not None
                and rsi is not None
                and bars[-1].adjusted_close > trend
                and rsi <= threshold
            )

        return rsi_pullback
    if candidate.family == "atr_trend":
        window = _int_parameter(parameters["window"], "window")
        max_ratio = Decimal(str(parameters["max_ratio"]))
        trend_window = _int_parameter(parameters["trend_window"], "trend_window")

        def atr_trend(_symbol: str, bars: tuple[DailyBar, ...]) -> bool:
            trend = _sma(bars, trend_window)
            atr = _wilder_atr(bars, window)
            return bool(
                trend is not None
                and atr is not None
                and bars[-1].adjusted_close > trend
                and atr / bars[-1].adjusted_close <= max_ratio
            )

        return atr_trend
    raise ValueError(f"Unsupported rule family: {candidate.family}")


def _features(bars: Sequence[DailyBar]) -> list[float] | None:
    if len(bars) < 61:
        return None
    close = bars[-1].adjusted_close
    average5 = _sma(bars, 5)
    average20 = _sma(bars, 20)
    average60 = _sma(bars, 60)
    assert average5 is not None and average20 is not None and average60 is not None
    volume_average = sum(bar.volume for bar in bars[-20:]) / 20
    return [
        float(close / bars[-2].adjusted_close - 1),
        float(close / bars[-6].adjusted_close - 1),
        float(close / bars[-21].adjusted_close - 1),
        float(close / average5 - 1),
        float(close / average20 - 1),
        float(close / average60 - 1),
        bars[-1].volume / volume_average - 1 if volume_average else 0.0,
    ]


def _snapshot_items(
    snapshot: OptimizerSnapshot,
) -> Sequence[SymbolSnapshot | OfflineInstrumentSnapshot]:
    return cast(
        Sequence[SymbolSnapshot | OfflineInstrumentSnapshot],
        snapshot.instruments
        if isinstance(snapshot, OfflineResearchSnapshot)
        else snapshot.symbols,
    )


def training_examples(
    snapshot: OptimizerSnapshot, request: OptimizerRequest
) -> tuple[list[list[float]], list[float]]:
    features: list[list[float]] = []
    labels: list[float] = []
    for item in sorted(_snapshot_items(snapshot), key=lambda value: value.symbol):
        bars = sorted(item.bars, key=lambda bar: bar.date)
        for index in range(60, len(bars) - 2):
            signal_date = bars[index].date
            if signal_date < request.start_date:
                continue
            # Both execution opens used by the label must stay inside training.
            if bars[index + 2].date > request.end_date:
                continue
            values = _features(bars[: index + 1])
            assert values is not None
            features.append(values)
            first_open = (
                bars[index + 1].adjusted_open
                if isinstance(snapshot, OfflineResearchSnapshot)
                else bars[index + 1].open
            )
            second_open = (
                bars[index + 2].adjusted_open
                if isinstance(snapshot, OfflineResearchSnapshot)
                else bars[index + 2].open
            )
            labels.append(float(second_open > first_open))
    if not features:
        raise DataInsufficientError("ML 학습용 시간순 표본이 없습니다.")
    return features, labels


def _resolve_device(device_choice: DeviceChoice) -> tuple[str, Any]:
    try:
        import torch
    except ImportError:
        raise RuntimeError(
            "ML 탐색에는 별도 optimizer PyTorch 의존성이 필요합니다."
        ) from None
    if device_choice == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("요청한 CUDA 장치를 사용할 수 없습니다.")
    device = (
        "cuda"
        if device_choice == "cuda"
        or (device_choice == "auto" and torch.cuda.is_available())
        else "cpu"
    )
    return device, torch


def train_mlp(
    candidate: Candidate,
    snapshot: OptimizerSnapshot,
    training: OptimizerRequest,
    device_choice: DeviceChoice,
    should_stop: Callable[[], bool] = lambda: False,
) -> tuple[dict[str, Any], str]:
    device, torch = _resolve_device(device_choice)
    torch.set_num_threads(2)
    torch.manual_seed(SEED)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(SEED)
    x_values, y_values = training_examples(snapshot, training)
    feature_count = len(x_values[0])
    means = [
        sum(row[index] for row in x_values) / len(x_values)
        for index in range(feature_count)
    ]
    deviations = [
        math.sqrt(
            sum((row[index] - means[index]) ** 2 for row in x_values) / len(x_values)
        )
        for index in range(feature_count)
    ]
    scales = [value if value > 1e-12 else 1.0 for value in deviations]
    normalized = [
        [(value - means[index]) / scales[index] for index, value in enumerate(row)]
        for row in x_values
    ]
    x_tensor = torch.tensor(normalized, dtype=torch.float32, device=device)
    y_tensor = torch.tensor(y_values, dtype=torch.float32, device=device).reshape(-1, 1)
    hidden = _int_parameter(candidate.parameters["hidden"], "hidden")
    model = torch.nn.Sequential(
        torch.nn.Linear(feature_count, hidden),
        torch.nn.Tanh(),
        torch.nn.Linear(hidden, 1),
    ).to(device)
    optimizer = torch.optim.Adam(
        model.parameters(), lr=float(str(candidate.parameters["learning_rate"]))
    )
    loss_function = torch.nn.BCEWithLogitsLoss()
    for _ in range(_int_parameter(candidate.parameters["epochs"], "epochs")):
        if should_stop():
            raise StopRequested
        optimizer.zero_grad(set_to_none=True)
        loss = loss_function(model(x_tensor), y_tensor)
        if not bool(torch.isfinite(loss).item()):
            raise RuntimeError("ML 학습 손실이 유한하지 않습니다.")
        loss.backward()
        optimizer.step()
    layers = [layer for layer in model if isinstance(layer, torch.nn.Linear)]
    artifact: dict[str, Any] = {
        "format": "jusik_mlp_json_v1",
        "candidate": {
            "id": candidate.id,
            "parameters": candidate.parameters,
        },
        "optimizer_version": OPTIMIZER_VERSION,
        "code_hash": _code_hash(),
        "source_engine_hash": IMPLEMENTATION_HASH,
        "torch_version": str(torch.__version__),
        "seed": SEED,
        "device": device,
        "training_end": training.end_date.isoformat(),
        "feature_mean": means,
        "feature_scale": scales,
        "layers": [
            {
                "weight": layer.weight.detach().cpu().tolist(),
                "bias": layer.bias.detach().cpu().tolist(),
            }
            for layer in layers
        ],
    }
    return artifact, device


def mlp_signal(artifact: dict[str, Any]) -> SignalFunction:
    means = [float(value) for value in artifact["feature_mean"]]
    scales = [float(value) for value in artifact["feature_scale"]]
    first, second = artifact["layers"]
    hidden_weights = [[float(value) for value in row] for row in first["weight"]]
    hidden_bias = [float(value) for value in first["bias"]]
    output_weights = [float(value) for value in second["weight"][0]]
    output_bias = float(second["bias"][0])

    def predict(_symbol: str, bars: tuple[DailyBar, ...]) -> bool:
        values = _features(bars)
        if values is None:
            return False
        normalized = [
            (value - means[index]) / scales[index] for index, value in enumerate(values)
        ]
        hidden = [
            math.tanh(
                sum(
                    weight * value
                    for weight, value in zip(row, normalized, strict=True)
                )
                + hidden_bias[index]
            )
            for index, row in enumerate(hidden_weights)
        ]
        logit = (
            sum(
                weight * value
                for weight, value in zip(output_weights, hidden, strict=True)
            )
            + output_bias
        )
        return logit > 0

    return predict


def _is_mlp_v2(candidate: Candidate) -> bool:
    return candidate.family == "mlp" and (
        candidate.parameters.get("variant") == MLP_V2_VARIANT
    )


def _mlp_signal_for_artifact(artifact: dict[str, Any]) -> SignalFunction:
    return (
        mlp_v2_signal(artifact)
        if artifact.get("format") == MLP_V2_FORMAT
        else mlp_signal(artifact)
    )


def _baseline_signal(_symbol: str, bars: tuple[DailyBar, ...]) -> bool:
    return target_invested(BASELINE_VERSION, list(bars), len(bars) - 1)


def _external_gate(candidate: Candidate) -> MacroGate | None:
    if candidate.family == "external_control":
        if candidate.parameters != control_candidate_parameters():
            raise ValueError("Invalid external control candidate parameters.")
        return None
    if candidate.family != "external_macro":
        return None
    variant = candidate.parameters.get("variant")
    if variant not in {"rates", "fx_vix", "stress"}:
        raise ValueError("Invalid external macro candidate variant.")
    gate = cast(MacroGate, variant)
    if candidate.parameters != macro_candidate_parameters(gate):
        raise ValueError("Invalid external macro candidate parameters.")
    return gate


def _source_timezone(source: SourceSnapshot) -> str:
    if isinstance(source.request, OfflineResearchRequest):
        return source.request.instrument.timezone
    return "Asia/Seoul"


def _candidate_signal(
    candidate: Candidate,
    source: SourceSnapshot,
    diagnostics: ExternalSignalDiagnostics | None = None,
) -> SignalFunction:
    if candidate.family == "external_control":
        _external_gate(candidate)
        return _baseline_signal
    gate = _external_gate(candidate)
    if gate is not None:
        if diagnostics is None:
            raise ValueError("External macro diagnostics are required.")
        return macro_signal(
            gate,
            source.external,
            _source_timezone(source),
            diagnostics,
        )
    return rule_signal(candidate)


def _decision_dates(source: SourceSnapshot, request: OptimizerRequest) -> list[date]:
    items = _snapshot_items(source.snapshot)
    if not items:
        return []
    dates = sorted(bar.date for bar in items[0].bars)
    prior = [day for day in dates if day < request.start_date]
    selected = [day for day in dates if request.start_date <= day <= request.end_date]
    return ([prior[-1]] if prior else []) + selected


def _external_validation(
    candidate: Candidate,
    source: SourceSnapshot,
    request: OptimizerRequest,
) -> tuple[bool, dict[str, object] | None]:
    gate = _external_gate(candidate)
    if gate is None:
        return True, None
    return validation_coverage(
        gate,
        source.external,
        _decision_dates(source, request),
        _source_timezone(source),
    )


def _run_candidate(
    candidate: Candidate,
    source: SourceSnapshot,
    split: Split,
    device_choice: DeviceChoice,
    should_stop: Callable[[], bool],
    risk_policy: ResearchRiskPolicy | None = None,
    external_diagnostics: ExternalSignalDiagnostics | None = None,
) -> tuple[
    StrategyResult,
    dict[str, Any] | None,
    str,
    ResearchRiskReport | None,
]:
    artifact: dict[str, Any] | None = None
    device = "cpu"
    if _is_mlp_v2(candidate):
        device, torch = _resolve_device(device_choice)
        try:
            artifact = train_mlp_v2(
                candidate_id=candidate.id,
                parameters=candidate.parameters,
                items=_snapshot_items(source.snapshot),
                training=split.training,
                device=device,
                torch=torch,
                optimizer_version=OPTIMIZER_VERSION,
                code_hash=_code_hash(),
                source_engine_hash=IMPLEMENTATION_HASH,
                should_stop=should_stop,
            )
        except MlTrainingStopped:
            raise StopRequested from None
        selected_signal = mlp_v2_signal(artifact)
    elif candidate.family == "mlp":
        artifact, device = train_mlp(
            candidate,
            source.snapshot,
            split.training,
            device_choice,
            should_stop,
        )
        selected_signal = mlp_signal(artifact)
    else:
        selected_signal = _candidate_signal(candidate, source, external_diagnostics)
    risk_report = (
        ResearchRiskReport.start(risk_policy, split.validation.initial_cash)
        if risk_policy is not None
        else None
    )
    result = run_signal_backtest(
        split.validation,
        source.snapshot,
        strategy_version=candidate.id,
        definition=json.dumps(candidate.parameters, sort_keys=True),
        signal=selected_signal,
        risk_policy=risk_policy,
        risk_report=risk_report,
    )
    return result, artifact, device, risk_report


def _write_artifact(
    directory: Path, run_id: str, candidate_id: str, artifact: dict[str, Any]
) -> Path:
    target_dir = directory / run_id
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{candidate_id}.json"
    temporary = target.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(artifact, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    os.chmod(temporary, 0o600)
    temporary.replace(target)
    return target


def _load_artifact(
    path: str,
    *,
    candidate: Candidate,
    run_id: str,
    training_end: date,
    training: OptimizerRequest | None = None,
) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        if _is_mlp_v2(candidate):
            if training is None:
                raise ValueError
            return validate_mlp_v2_artifact(
                value,
                candidate_id=candidate.id,
                parameters=candidate.parameters,
                run_id=run_id,
                training=training,
                optimizer_version=OPTIMIZER_VERSION,
                code_hash=_code_hash(),
                source_engine_hash=IMPLEMENTATION_HASH,
            )
        if not isinstance(value, dict) or value.get("format") != "jusik_mlp_json_v1":
            raise ValueError
        identity = value["candidate"]
        if not isinstance(identity, dict):
            raise ValueError
        if (
            identity.get("id") != candidate.id
            or identity.get("parameters") != candidate.parameters
        ):
            raise ValueError
        if (
            value.get("optimizer_run_id") != run_id
            or value.get("optimizer_version") != OPTIMIZER_VERSION
            or value.get("code_hash") != _code_hash()
            or value.get("source_engine_hash") != IMPLEMENTATION_HASH
            or value.get("seed") != SEED
            or value.get("training_end") != training_end.isoformat()
            or value.get("device") not in {"cpu", "cuda"}
        ):
            raise ValueError
        means = value["feature_mean"]
        scales = value["feature_scale"]
        layers = value["layers"]
        if (
            not isinstance(means, list)
            or not isinstance(scales, list)
            or len(means) != 7
            or len(scales) != 7
            or not isinstance(layers, list)
            or len(layers) != 2
        ):
            raise ValueError
        numeric_means = [float(item) for item in means]
        numeric_scales = [float(item) for item in scales]
        first_weight = layers[0]["weight"]
        first_bias = layers[0]["bias"]
        second_weight = layers[1]["weight"]
        second_bias = layers[1]["bias"]
        hidden = _int_parameter(candidate.parameters["hidden"], "hidden")
        if (
            not all(math.isfinite(item) for item in numeric_means)
            or not all(math.isfinite(item) and item > 0 for item in numeric_scales)
            or len(first_weight) != hidden
            or len(first_bias) != hidden
            or any(len(row) != 7 for row in first_weight)
            or len(second_weight) != 1
            or len(second_weight[0]) != hidden
            or len(second_bias) != 1
        ):
            raise ValueError
        tensors = [*first_bias, *second_weight[0], *second_bias]
        tensors.extend(item for row in first_weight for item in row)
        if not all(math.isfinite(float(item)) for item in tensors):
            raise ValueError
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError, IndexError):
        raise RuntimeError(
            "저장된 ML 모델 artifact 형식이 올바르지 않습니다."
        ) from None
    return value


def _resumable_candidate_ids(
    store: OptimizerStore,
    run_id: str,
    split: Split,
    configured_candidates: Sequence[Candidate],
) -> set[str]:
    completed = store.completed_candidate_ids(run_id)
    for candidate in configured_candidates:
        if candidate.family != "mlp" or candidate.id not in completed:
            continue
        artifact_path = store.candidate_artifact_path(run_id, candidate.id)
        try:
            if artifact_path is None:
                raise RuntimeError("저장된 ML 모델 artifact 형식이 올바르지 않습니다.")
            _load_artifact(
                artifact_path,
                candidate=candidate,
                run_id=run_id,
                training_end=split.training.end_date,
                training=split.training,
            )
        except RuntimeError:
            store.delete_candidate(run_id, candidate.id)
            completed.remove(candidate.id)
    return completed


def _selected_winner_id(
    frozen_winner_id: str | None, winner_row: sqlite3.Row | None
) -> str:
    if frozen_winner_id is not None:
        return frozen_winner_id
    if winner_row is None:
        raise DataInsufficientError("거래가 발생한 유효 후보가 없습니다.")
    return str(winner_row["candidate_id"])


def optimize_snapshot(
    source: SourceSnapshot,
    store: OptimizerStore,
    artifact_dir: Path,
    device_choice: DeviceChoice,
    should_stop: Callable[[], bool] = lambda: False,
) -> bool:
    run_id, content_hash = content_identity(source, device_choice)
    if not store.begin(run_id, source.run_id, content_hash):
        return False
    try:
        split = validate_and_split(source)
        configured_candidates = candidates()
        completed = _resumable_candidate_ids(
            store, run_id, split, configured_candidates
        )
        resolved_device, _torch = _resolve_device(device_choice)
        for candidate in configured_candidates:
            if should_stop() or store.stop_requested():
                raise StopRequested
            if candidate.id in completed:
                continue
            coverage_ok, coverage = _external_validation(
                candidate, source, split.validation
            )
            if not coverage_ok:
                store.save_candidate(
                    run_id,
                    candidate.id,
                    candidate.family,
                    candidate.parameters,
                    score=None,
                    eligible=False,
                    validation_result={
                        "ineligible_reason": "검증 구간 외부 변수 자료가 불완전합니다.",
                        "external_diagnostics": coverage,
                    },
                    artifact_path=None,
                )
                store.heartbeat(run_id, device=resolved_device)
                continue
            diagnostics = (
                ExternalSignalDiagnostics()
                if candidate.family == "external_macro"
                else None
            )
            result, artifact, device, _risk_report = _run_candidate(
                candidate,
                source,
                split,
                device_choice,
                should_stop,
                external_diagnostics=diagnostics,
            )
            resolved_device = device if candidate.family == "mlp" else resolved_device
            artifact_path = (
                _write_artifact(
                    artifact_dir,
                    run_id,
                    candidate.id,
                    {**artifact, "optimizer_run_id": run_id},
                )
                if artifact is not None
                else None
            )
            score = result.metrics.total_return_pct - result.metrics.max_drawdown_pct
            eligible = result.metrics.trade_count > 0
            store.save_candidate(
                run_id,
                candidate.id,
                candidate.family,
                candidate.parameters,
                score=str(score) if eligible else None,
                eligible=eligible,
                validation_result=(
                    {
                        "strategy_result": result.model_dump(mode="json"),
                        "external_diagnostics": diagnostics.as_json(),
                    }
                    if diagnostics is not None
                    else result.model_dump(mode="json")
                ),
                artifact_path=artifact_path,
            )
            store.heartbeat(run_id, device=resolved_device)
            time.sleep(0)
        frozen_winner_id = store.frozen_winner_id(run_id)
        winner_row = store.best_candidate(run_id)
        winner_id = _selected_winner_id(frozen_winner_id, winner_row)
        winner = next(item for item in configured_candidates if item.id == winner_id)
        if winner.family == "mlp":
            stored_artifact_path = store.candidate_artifact_path(run_id, winner.id)
            if not stored_artifact_path:
                raise RuntimeError("선정된 ML 후보의 artifact가 없습니다.")
            selected_signal = _mlp_signal_for_artifact(
                _load_artifact(
                    stored_artifact_path,
                    candidate=winner,
                    run_id=run_id,
                    training_end=split.training.end_date,
                    training=split.training,
                )
            )
        else:
            selected_signal = _candidate_signal(
                winner,
                source,
                ExternalSignalDiagnostics()
                if winner.family == "external_macro"
                else None,
            )
        store.freeze_winner(
            run_id,
            device=resolved_device,
            split=split.as_json(),
            winner_id=winner.id,
        )
        if should_stop() or store.stop_requested():
            raise StopRequested
        # The winner is frozen before either strategy sees the untouched final slice.
        baseline_final = run_signal_backtest(
            split.final,
            source.snapshot,
            strategy_version=BASELINE_VERSION,
            definition="20-day adjusted-close trend baseline",
            signal=_baseline_signal,
            defer_events=False,
        )
        winner_final = run_signal_backtest(
            split.final,
            source.snapshot,
            strategy_version=winner.id,
            definition=json.dumps(winner.parameters, sort_keys=True),
            signal=selected_signal,
        )
        store.complete(
            run_id,
            device=resolved_device,
            split=split.as_json(),
            winner_id=winner.id,
            baseline_final=baseline_final.model_dump(mode="json"),
            winner_final=winner_final.model_dump(mode="json"),
        )
        return True
    except StopRequested:
        store.fail(run_id, "중지 요청으로 탐색을 안전하게 종료했습니다.", stopped=True)
        raise
    except DataInsufficientError as error:
        store.fail(run_id, str(error), insufficient=True)
        return True
    except (RuntimeError, ValueError, OSError, sqlite3.Error) as error:
        store.fail(run_id, _safe_error(error))
        return True


def _walk_fold_id(batch_id: str, fold: WalkForwardFold) -> str:
    return _canonical_hash(
        {"batch_id": batch_id, "fold_index": fold.index, **fold.date_ranges()}
    )


def _strategy_signal(
    candidate: Candidate,
    source: SourceSnapshot,
    store: OptimizerStore,
    run_id: str,
    training: OptimizerRequest,
    diagnostics: ExternalSignalDiagnostics | None = None,
) -> SignalFunction:
    if candidate.family != "mlp":
        return _candidate_signal(candidate, source, diagnostics)
    artifact_path = store.candidate_artifact_path(run_id, candidate.id)
    if artifact_path is None:
        raise RuntimeError("선정된 ML 후보의 artifact가 없습니다.")
    return _mlp_signal_for_artifact(
        _load_artifact(
            artifact_path,
            candidate=candidate,
            run_id=run_id,
            training_end=training.end_date,
            training=training,
        )
    )


def _optimize_walk_fold(
    source: SourceSnapshot,
    store: OptimizerStore,
    artifact_dir: Path,
    device_choice: DeviceChoice,
    batch_id: str,
    content_hash: str,
    fold: WalkForwardFold,
    risk_policy: ResearchRiskPolicy,
    should_stop: Callable[[], bool],
) -> None:
    run_id = _walk_fold_id(batch_id, fold)
    store.register_fold(batch_id, fold.index, run_id, fold.date_ranges())
    if store.fold_completed(batch_id, fold.index):
        return
    fold_content_hash = _canonical_hash(
        {"content_hash": content_hash, **fold.date_ranges()}
    )
    if not store.begin(run_id, source.run_id, fold_content_hash):
        if store.fold_completed(batch_id, fold.index):
            return
        raise RuntimeError("Walk-forward fold state is inconsistent.")
    store.start_fold(batch_id, fold.index)
    split = fold.split
    configured_candidates = candidates()
    try:
        completed = _resumable_candidate_ids(
            store, run_id, split, configured_candidates
        )
        resolved_device, _torch = _resolve_device(device_choice)
        for candidate in configured_candidates:
            if should_stop() or store.stop_requested():
                raise StopRequested
            if candidate.id in completed:
                continue
            coverage_ok, coverage = _external_validation(
                candidate, source, split.validation
            )
            if not coverage_ok:
                store.save_candidate(
                    run_id,
                    candidate.id,
                    candidate.family,
                    candidate.parameters,
                    score=None,
                    eligible=False,
                    validation_result={
                        "ineligible_reason": "검증 구간 외부 변수 자료가 불완전합니다.",
                        "external_diagnostics": coverage,
                    },
                    artifact_path=None,
                )
                store.heartbeat(run_id, device=resolved_device)
                continue
            diagnostics = (
                ExternalSignalDiagnostics()
                if candidate.family == "external_macro"
                else None
            )
            result, artifact, device, risk_report = _run_candidate(
                candidate,
                source,
                split,
                device_choice,
                should_stop,
                risk_policy,
                diagnostics,
            )
            assert risk_report is not None
            resolved_device = device if candidate.family == "mlp" else resolved_device
            artifact_path = (
                _write_artifact(
                    artifact_dir,
                    run_id,
                    candidate.id,
                    {**artifact, "optimizer_run_id": run_id},
                )
                if artifact is not None
                else None
            )
            score = result.metrics.total_return_pct - result.metrics.max_drawdown_pct
            eligible = result.metrics.trade_count > 0
            store.save_candidate(
                run_id,
                candidate.id,
                candidate.family,
                candidate.parameters,
                score=str(score) if eligible else None,
                eligible=eligible,
                validation_result={
                    "strategy_result": result.model_dump(mode="json"),
                    "risk_report": risk_report.as_json(),
                    **(
                        {"external_diagnostics": diagnostics.as_json()}
                        if diagnostics is not None
                        else {}
                    ),
                },
                artifact_path=artifact_path,
            )
            store.heartbeat(run_id, device=resolved_device)
            time.sleep(0)
        frozen_winner_id = store.frozen_winner_id(run_id)
        winner_row = store.best_candidate(run_id)
        winner_id = _selected_winner_id(frozen_winner_id, winner_row)
        winner = next(
            candidate
            for candidate in configured_candidates
            if candidate.id == winner_id
        )
        winner_diagnostics = (
            ExternalSignalDiagnostics() if winner.family == "external_macro" else None
        )
        selected_signal = _strategy_signal(
            winner,
            source,
            store,
            run_id,
            split.training,
            winner_diagnostics,
        )
        store.freeze_winner(
            run_id,
            device=resolved_device,
            split=fold.as_json(),
            winner_id=winner.id,
        )
        if should_stop() or store.stop_requested():
            raise StopRequested
        baseline_risk = ResearchRiskReport.start(risk_policy, split.final.initial_cash)
        baseline_oos = run_signal_backtest(
            split.final,
            source.snapshot,
            strategy_version=BASELINE_VERSION,
            definition="20-day adjusted-close trend baseline",
            signal=_baseline_signal,
            defer_events=False,
            risk_policy=risk_policy,
            risk_report=baseline_risk,
        )
        winner_risk = ResearchRiskReport.start(risk_policy, split.final.initial_cash)
        winner_oos = run_signal_backtest(
            split.final,
            source.snapshot,
            strategy_version=winner.id,
            definition=json.dumps(winner.parameters, sort_keys=True),
            signal=selected_signal,
            risk_policy=risk_policy,
            risk_report=winner_risk,
        )
        passed = (
            winner_oos.metrics.trade_count > 0
            and winner_oos.metrics.total_return_pct
            >= baseline_oos.metrics.total_return_pct
            and winner_oos.metrics.max_drawdown_pct
            <= baseline_oos.metrics.max_drawdown_pct
            and winner_oos.metrics.max_drawdown_pct
            <= risk_policy.peak_close_drawdown_limit * Decimal(100)
            and (winner_diagnostics is None or not winner_diagnostics.missing_dates)
        )
        store.complete_walk_fold(
            batch_id,
            fold.index,
            run_id,
            device=resolved_device,
            split=fold.as_json(),
            winner_id=winner.id,
            baseline_final=baseline_oos.model_dump(mode="json"),
            winner_final=winner_oos.model_dump(mode="json"),
            passed=passed,
            baseline_risk=baseline_risk.as_json(),
            winner_risk={
                **winner_risk.as_json(),
                **(
                    {"external_diagnostics": winner_diagnostics.as_json()}
                    if winner_diagnostics is not None
                    else {}
                ),
            },
        )
    except StopRequested:
        store.fail(
            run_id, "중지 요청으로 fold 탐색을 안전하게 종료했습니다.", stopped=True
        )
        store.fail_fold(batch_id, fold.index, stopped=True)
        raise
    except DataInsufficientError as error:
        store.fail(run_id, str(error), insufficient=True)
        store.fail_fold(batch_id, fold.index, insufficient=True)
        raise
    except (RuntimeError, ValueError, OSError, sqlite3.Error) as error:
        store.fail(run_id, _safe_error(error))
        store.fail_fold(batch_id, fold.index)
        raise


def _walk_summary(
    rows: Sequence[sqlite3.Row], *, external_attached: bool = False
) -> dict[str, object]:
    winner_returns: list[Decimal] = []
    winner_drawdowns: list[Decimal] = []
    excess_returns: list[Decimal] = []
    passed_folds = 0
    winning_folds = 0
    for row in rows:
        baseline = json.loads(row["baseline_final_json"])["metrics"]
        winner = json.loads(row["winner_final_json"])["metrics"]
        baseline_return = Decimal(str(baseline["total_return_pct"]))
        winner_return = Decimal(str(winner["total_return_pct"]))
        winner_returns.append(winner_return)
        winner_drawdowns.append(Decimal(str(winner["max_drawdown_pct"])))
        excess_returns.append(winner_return - baseline_return)
        passed_folds += int(row["passed"] == 1)
        winning_folds += int(winner_return > baseline_return)
    count = Decimal(len(rows))
    result: dict[str, object] = {
        "fold_count": len(rows),
        "passed_folds": passed_folds,
        "winning_folds": winning_folds,
        "mean_oos_return_pct": str(sum(winner_returns, Decimal()) / count),
        "worst_oos_return_pct": str(min(winner_returns)),
        "max_oos_drawdown_pct": str(max(winner_drawdowns)),
        "mean_excess_return_pct": str(sum(excess_returns, Decimal()) / count),
        "research_comparison_met": len(rows) >= 2 and passed_folds == len(rows),
        "automatic_trading_eligible": False,
    }
    if external_attached:
        result.update(external_evidence_metadata())
    return result


def optimize_walk_forward_snapshot(
    source: SourceSnapshot,
    store: OptimizerStore,
    artifact_dir: Path,
    device_choice: DeviceChoice,
    should_stop: Callable[[], bool] = lambda: False,
) -> bool:
    risk_policy = ResearchRiskPolicy()
    batch_id, content_hash = walk_forward_identity(source, device_choice, risk_policy)
    try:
        folds, tail = walk_forward_folds(source)
    except DataInsufficientError as error:
        if store.begin_batch(
            batch_id,
            source.run_id,
            content_hash,
            validation_mode="walk-forward",
            risk=risk_policy.as_json(),
            fold_count=0,
            tail={"count": 0, "first_date": None, "last_date": None},
        ):
            store.fail_batch(batch_id, str(error), insufficient=True)
        return True
    if not store.begin_batch(
        batch_id,
        source.run_id,
        content_hash,
        validation_mode="walk-forward",
        risk=risk_policy.as_json(),
        fold_count=len(folds),
        tail=tail,
    ):
        return False
    try:
        for fold in folds:
            store.register_fold(
                batch_id,
                fold.index,
                _walk_fold_id(batch_id, fold),
                fold.date_ranges(),
            )
        for fold in folds:
            if should_stop() or store.stop_requested():
                raise StopRequested
            _optimize_walk_fold(
                source,
                store,
                artifact_dir,
                device_choice,
                batch_id,
                content_hash,
                fold,
                risk_policy,
                should_stop,
            )
        rows = store.batch_fold_results(batch_id)
        if len(rows) != len(folds) or any(row["status"] != "completed" for row in rows):
            raise RuntimeError("Walk-forward folds did not complete.")
        store.complete_batch(
            batch_id,
            _walk_summary(rows, external_attached=source.external is not None),
        )
        return True
    except StopRequested:
        store.fail_batch(
            batch_id, "중지 요청으로 walk-forward 탐색을 종료했습니다.", stopped=True
        )
        raise
    except DataInsufficientError as error:
        store.fail_batch(batch_id, str(error), insufficient=True)
        return True
    except (RuntimeError, ValueError, OSError, sqlite3.Error) as error:
        store.fail_batch(batch_id, _safe_error(error))
        return True


def _safe_error(error: Exception) -> str:
    if isinstance(error, RuntimeError) and str(error) in {
        "ML 탐색에는 별도 optimizer PyTorch 의존성이 필요합니다.",
        "요청한 CUDA 장치를 사용할 수 없습니다.",
        "ML 학습 손실이 유한하지 않습니다.",
        "저장된 ML 모델 artifact 형식이 올바르지 않습니다.",
        "선정된 ML 후보의 artifact가 없습니다.",
    }:
        return str(error)
    return f"Optimizer failed safely ({type(error).__name__})."


def run_daemon(
    research_db: Path,
    optimizer_db: Path,
    artifact_dir: Path,
    *,
    device: DeviceChoice,
    once: bool,
    poll_seconds: int = POLL_SECONDS,
    validation_mode: ValidationMode = "single",
) -> int:
    store = OptimizerStore(optimizer_db)
    lock_path = optimizer_db.with_suffix(".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("optimizer is already running", file=sys.stderr)
            return 2
        _resolve_device(device)
        store.clear_stop()
        store.daemon_heartbeat(True)
        interrupted = False

        def request_stop(_signum: int, _frame: FrameType | None) -> None:
            nonlocal interrupted
            interrupted = True

        previous_term = process_signal.signal(process_signal.SIGTERM, request_stop)
        previous_int = process_signal.signal(process_signal.SIGINT, request_stop)
        try:
            while True:
                store.daemon_heartbeat(True)
                if interrupted or store.stop_requested():
                    return 0
                processed = False

                def record_invalid_source(source_run_id: str) -> None:
                    invalid_id = _canonical_hash(
                        {
                            "invalid_source_run_id": source_run_id,
                            "optimizer_version": OPTIMIZER_VERSION,
                        }
                    )
                    store.record_invalid_source(invalid_id, source_run_id)

                for source in read_source_snapshots(
                    research_db, on_invalid=record_invalid_source
                ):
                    if interrupted or store.stop_requested():
                        return 0
                    try:
                        optimizer = (
                            optimize_walk_forward_snapshot
                            if validation_mode == "walk-forward"
                            else optimize_snapshot
                        )
                        processed = (
                            optimizer(
                                source,
                                store,
                                artifact_dir,
                                device,
                                lambda: interrupted,
                            )
                            or processed
                        )
                    except StopRequested:
                        return 0
                if once:
                    return 0
                waited = 0
                while waited < poll_seconds:
                    if interrupted or store.stop_requested():
                        return 0
                    time.sleep(1)
                    waited += 1
                    store.daemon_heartbeat(True)
                if processed:
                    time.sleep(0)
        finally:
            store.daemon_heartbeat(False)
            process_signal.signal(process_signal.SIGTERM, previous_term)
            process_signal.signal(process_signal.SIGINT, previous_int)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Offline strategy optimizer")
    parser.add_argument("--research-db", type=Path, default=DEFAULT_RESEARCH_DB)
    parser.add_argument("--optimizer-db", type=Path, default=DEFAULT_OPTIMIZER_DB)
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run")
    run.add_argument("--once", action="store_true")
    run.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    run.add_argument(
        "--validation-mode",
        choices=("walk-forward", "single"),
        default="walk-forward",
    )
    subparsers.add_parser("status")
    subparsers.add_parser("stop")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    store = OptimizerStore(arguments.optimizer_db)
    if arguments.command == "status":
        print(json.dumps(store.status(), ensure_ascii=False, sort_keys=True))
        return 0
    if arguments.command == "stop":
        store.request_stop()
        print("stop requested")
        return 0
    try:
        return run_daemon(
            arguments.research_db,
            arguments.optimizer_db,
            arguments.artifact_dir,
            device=arguments.device,
            once=arguments.once,
            validation_mode=arguments.validation_mode,
        )
    except sqlite3.Error:
        print("research database is unavailable or invalid", file=sys.stderr)
        return 1
    except DataInsufficientError:
        print("a stored research snapshot is invalid", file=sys.stderr)
        return 1
    except RuntimeError as error:
        print(_safe_error(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
