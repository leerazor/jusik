from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from decimal import Decimal
from typing import Any, cast

from jusik.research_data import DataInsufficientError
from jusik.research_models import DailyBar, ResearchRunRequest, SymbolSnapshot
from jusik.research_universe_models import (
    OfflineInstrumentSnapshot,
    OfflineResearchRequest,
)

MLP_V2_VARIANT = "cost_aware_v2"
MLP_V2_FORMAT = "jusik_mlp_json_v2"
FEATURE_ORDER = (
    "return_1d",
    "return_5d",
    "return_20d",
    "close_to_sma_5",
    "close_to_sma_20",
    "close_to_sma_60",
    "volume_to_average_20",
    "return_stdev_5",
    "return_stdev_20",
    "average_range_ratio_20",
)


RequestLike = ResearchRunRequest | OfflineResearchRequest
BarsItem = SymbolSnapshot | OfflineInstrumentSnapshot


class MlTrainingStopped(Exception):
    pass


def _int_parameter(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"ML v2 {name} must be an integer.")
    return value


def _sma(bars: Sequence[DailyBar], length: int) -> Decimal:
    return sum((bar.adjusted_close for bar in bars[-length:]), Decimal()) / Decimal(
        length
    )


def _return_stdev(bars: Sequence[DailyBar], length: int) -> float:
    returns = [
        float(bars[index].adjusted_close / bars[index - 1].adjusted_close - 1)
        for index in range(len(bars) - length, len(bars))
    ]
    mean = sum(returns) / len(returns)
    return math.sqrt(sum((value - mean) ** 2 for value in returns) / len(returns))


def features_v2(bars: Sequence[DailyBar]) -> list[float] | None:
    if len(bars) < 61:
        return None
    close = bars[-1].adjusted_close
    volume_average = sum(bar.volume for bar in bars[-20:]) / 20
    average_range_ratio = sum(
        (
            (bar.adjusted_high - bar.adjusted_low) / bar.adjusted_close
            for bar in bars[-20:]
        ),
        Decimal(),
    ) / Decimal(20)
    return [
        float(close / bars[-2].adjusted_close - 1),
        float(close / bars[-6].adjusted_close - 1),
        float(close / bars[-21].adjusted_close - 1),
        float(close / _sma(bars, 5) - 1),
        float(close / _sma(bars, 20) - 1),
        float(close / _sma(bars, 60) - 1),
        bars[-1].volume / volume_average - 1 if volume_average else 0.0,
        _return_stdev(bars, 5),
        _return_stdev(bars, 20),
        float(average_range_ratio),
    ]


def _net_return(
    entry_open: Decimal, exit_open: Decimal, request: RequestLike
) -> Decimal:
    entry_cost = (
        entry_open
        * (Decimal(1) + request.slippage_rate)
        * (Decimal(1) + request.fee_rate)
    )
    exit_proceeds = (
        exit_open
        * (Decimal(1) - request.slippage_rate)
        * (Decimal(1) - request.fee_rate - request.sell_tax_rate)
    )
    return exit_proceeds / entry_cost - Decimal(1)


def training_examples_v2(
    items: Sequence[BarsItem], request: RequestLike, *, horizon: int
) -> tuple[list[list[float]], list[float]]:
    if horizon < 1:
        raise ValueError("ML v2 horizon must be positive.")
    features: list[list[float]] = []
    labels: list[float] = []
    for item in sorted(items, key=lambda value: value.symbol):
        bars = sorted(item.bars, key=lambda bar: bar.date)
        for index in range(60, len(bars) - horizon - 1):
            if bars[index].date < request.start_date:
                continue
            entry = bars[index + 1]
            exit_bar = bars[index + horizon + 1]
            if exit_bar.date > request.end_date:
                continue
            values = features_v2(bars[: index + 1])
            assert values is not None
            features.append(values)
            labels.append(
                float(
                    _net_return(entry.adjusted_open, exit_bar.adjusted_open, request)
                    > 0
                )
            )
    if not features:
        raise DataInsufficientError("ML v2 학습용 시간순 표본이 없습니다.")
    return features, labels


def train_mlp_v2(
    *,
    candidate_id: str,
    parameters: Mapping[str, object],
    items: Sequence[BarsItem],
    training: RequestLike,
    device: str,
    torch: Any,
    optimizer_version: str,
    code_hash: str,
    source_engine_hash: str,
    should_stop: Callable[[], bool],
) -> dict[str, Any]:
    hidden = _int_parameter(parameters["hidden"], "hidden")
    epochs = _int_parameter(parameters["epochs"], "epochs")
    learning_rate = float(str(parameters["learning_rate"]))
    weight_decay = float(str(parameters["weight_decay"]))
    seed = _int_parameter(parameters["seed"], "seed")
    horizon = _int_parameter(parameters["horizon"], "horizon")
    threshold = str(parameters["threshold"])
    x_values, y_values = training_examples_v2(items, training, horizon=horizon)
    feature_count = len(FEATURE_ORDER)
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
    torch.set_num_threads(2)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    x_tensor = torch.tensor(normalized, dtype=torch.float32, device=device)
    y_tensor = torch.tensor(y_values, dtype=torch.float32, device=device).reshape(-1, 1)
    model = torch.nn.Sequential(
        torch.nn.Linear(feature_count, hidden),
        torch.nn.Tanh(),
        torch.nn.Linear(hidden, 1),
    ).to(device)
    optimizer = torch.optim.Adam(
        model.parameters(), learning_rate, weight_decay=weight_decay
    )
    loss_function = torch.nn.BCEWithLogitsLoss()
    for _ in range(epochs):
        if should_stop():
            raise MlTrainingStopped
        optimizer.zero_grad(set_to_none=True)
        loss = loss_function(model(x_tensor), y_tensor)
        if not bool(torch.isfinite(loss).item()):
            raise RuntimeError("ML v2 학습 손실이 유한하지 않습니다.")
        loss.backward()
        optimizer.step()
    layers = [layer for layer in model if isinstance(layer, torch.nn.Linear)]
    return {
        "format": MLP_V2_FORMAT,
        "candidate": {"id": candidate_id, "parameters": dict(parameters)},
        "optimizer_version": optimizer_version,
        "code_hash": code_hash,
        "source_engine_hash": source_engine_hash,
        "seed": seed,
        "device": device,
        "training_end": training.end_date.isoformat(),
        "feature_order": list(FEATURE_ORDER),
        "feature_dimension": feature_count,
        "feature_mean": means,
        "feature_scale": scales,
        "horizon": horizon,
        "threshold": threshold,
        "cost_assumptions": {
            "fee_rate": str(training.fee_rate),
            "slippage_rate": str(training.slippage_rate),
            "sell_tax_rate": str(training.sell_tax_rate),
        },
        "layers": [
            {
                "weight": layer.weight.detach().cpu().tolist(),
                "bias": layer.bias.detach().cpu().tolist(),
            }
            for layer in layers
        ],
    }


def _finite_numbers(values: object, expected: int) -> bool:
    return (
        isinstance(values, list)
        and len(values) == expected
        and all(
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(float(value))
            for value in values
        )
    )


def validate_mlp_v2_artifact(
    value: object,
    *,
    candidate_id: str,
    parameters: Mapping[str, object],
    run_id: str,
    training: RequestLike,
    optimizer_version: str,
    code_hash: str,
    source_engine_hash: str,
) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("format") != MLP_V2_FORMAT:
        raise ValueError
    identity = value.get("candidate")
    expected_costs = {
        "fee_rate": str(training.fee_rate),
        "slippage_rate": str(training.slippage_rate),
        "sell_tax_rate": str(training.sell_tax_rate),
    }
    if (
        not isinstance(identity, dict)
        or identity.get("id") != candidate_id
        or identity.get("parameters") != dict(parameters)
        or value.get("optimizer_run_id") != run_id
        or value.get("optimizer_version") != optimizer_version
        or value.get("code_hash") != code_hash
        or value.get("source_engine_hash") != source_engine_hash
        or value.get("seed") != parameters.get("seed")
        or value.get("device") not in {"cpu", "cuda"}
        or value.get("training_end") != training.end_date.isoformat()
        or value.get("feature_order") != list(FEATURE_ORDER)
        or value.get("feature_dimension") != len(FEATURE_ORDER)
        or value.get("horizon") != parameters.get("horizon")
        or value.get("threshold") != parameters.get("threshold")
        or value.get("cost_assumptions") != expected_costs
    ):
        raise ValueError
    means = value.get("feature_mean")
    scales = value.get("feature_scale")
    layers = value.get("layers")
    hidden = parameters.get("hidden")
    if (
        not isinstance(hidden, int)
        or not _finite_numbers(means, len(FEATURE_ORDER))
        or not _finite_numbers(scales, len(FEATURE_ORDER))
        or not isinstance(layers, list)
        or len(layers) != 2
        or not all(isinstance(layer, dict) for layer in layers)
    ):
        raise ValueError
    assert isinstance(scales, list)
    if any(float(scale) <= 0 for scale in scales):
        raise ValueError
    first, second = cast(list[dict[str, object]], layers)
    first_weights = first.get("weight")
    second_weights = second.get("weight")
    if (
        not isinstance(first_weights, list)
        or len(first_weights) != hidden
        or any(not _finite_numbers(row, len(FEATURE_ORDER)) for row in first_weights)
        or not _finite_numbers(first.get("bias"), hidden)
        or not isinstance(second_weights, list)
        or len(second_weights) != 1
        or not _finite_numbers(second_weights[0], hidden)
        or not _finite_numbers(second.get("bias"), 1)
    ):
        raise ValueError
    return value


def mlp_v2_signal(
    artifact: Mapping[str, object],
) -> Callable[[str, tuple[DailyBar, ...]], bool]:
    means = [
        float(str(value)) for value in cast(list[object], artifact["feature_mean"])
    ]
    scales = [
        float(str(value)) for value in cast(list[object], artifact["feature_scale"])
    ]
    layers = cast(list[dict[str, Any]], artifact["layers"])
    first, second = layers
    hidden_weights = [[float(value) for value in row] for row in first["weight"]]
    hidden_bias = [float(value) for value in first["bias"]]
    output_weights = [float(value) for value in second["weight"][0]]
    output_bias = float(second["bias"][0])
    threshold = float(str(artifact["threshold"]))

    def predict(_symbol: str, bars: tuple[DailyBar, ...]) -> bool:
        values = features_v2(bars)
        if values is None:
            return False
        normalized = [
            (value - means[index]) / scales[index] for index, value in enumerate(values)
        ]
        hidden_values = [
            math.tanh(
                sum(
                    weight * feature
                    for weight, feature in zip(row, normalized, strict=True)
                )
                + hidden_bias[index]
            )
            for index, row in enumerate(hidden_weights)
        ]
        logit = (
            sum(
                weight * hidden
                for weight, hidden in zip(output_weights, hidden_values, strict=True)
            )
            + output_bias
        )
        probability = (
            1 / (1 + math.exp(-logit))
            if logit >= 0
            else math.exp(logit) / (1 + math.exp(logit))
        )
        return probability >= threshold

    return predict
