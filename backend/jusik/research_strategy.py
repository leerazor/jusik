import hashlib
import json
from decimal import Decimal

from jusik.operations_models import StrategyDefinition
from jusik.research_models import (
    BASELINE_VERSION,
    CANDIDATE_VERSION,
    DailyBar,
)

BASELINE_DEFINITION = (
    "수정 종가가 20거래일 단순이동평균보다 높을 때 보유합니다. "
    "장 마감 후 신호를 계산하고 다음 거래 가능 시가에 체결합니다."
)
CANDIDATE_DEFINITION = (
    "수정 종가가 20거래일 단순이동평균보다 높고 20거래일 평균이 "
    "60거래일 평균보다 높을 때 보유합니다. 장 마감 후 신호를 계산하고 "
    "다음 거래 가능 시가에 체결합니다."
)
SIGNAL_FINGERPRINT_VERSION = "closed_bar_signal_v1"


def simple_moving_average(
    bars: list[DailyBar], index: int, length: int
) -> Decimal | None:
    if index + 1 < length:
        return None
    values = [bar.adjusted_close for bar in bars[index - length + 1 : index + 1]]
    return sum(values, Decimal()) / Decimal(length)


def target_invested(version: str, bars: list[DailyBar], index: int) -> bool:
    sma20 = simple_moving_average(bars, index, 20)
    if sma20 is None:
        return False
    if version == BASELINE_VERSION:
        return bars[index].adjusted_close > sma20
    if version == CANDIDATE_VERSION:
        sma60 = simple_moving_average(bars, index, 60)
        return sma60 is not None and bars[index].adjusted_close > sma20 > sma60
    raise ValueError(f"Unknown strategy version: {version}")


def target_for_definition(
    definition: StrategyDefinition, bars: list[DailyBar], index: int
) -> bool:
    fast = simple_moving_average(bars, index, definition.fast_window)
    if fast is None or bars[index].adjusted_close <= fast:
        return False
    if definition.slow_window is not None:
        slow = simple_moving_average(bars, index, definition.slow_window)
        if slow is None or fast <= slow:
            return False
    if definition.min_volume_ratio is not None:
        start = index - definition.fast_window + 1
        if start < 0:
            return False
        window = bars[start : index + 1]
        average = Decimal(sum(item.volume for item in window)) / Decimal(len(window))
        if (
            average <= 0
            or Decimal(bars[index].volume) / average < definition.min_volume_ratio
        ):
            return False
    return True


def signal_input_fingerprint(
    definition: StrategyDefinition, bars: list[DailyBar], index: int
) -> str:
    window = max(definition.fast_window, definition.slow_window or 0)
    selected = bars[max(0, index - window + 1) : index + 1]
    payload = {
        "fingerprint_version": SIGNAL_FINGERPRINT_VERSION,
        "strategy": {
            "version": definition.version,
            "fast_window": definition.fast_window,
            "slow_window": definition.slow_window,
            "min_volume_ratio": (
                str(definition.min_volume_ratio)
                if definition.min_volume_ratio is not None
                else None
            ),
        },
        "bars": [
            {
                "date": bar.date.isoformat(),
                "adjusted_close": str(bar.adjusted_close),
                **(
                    {"volume": bar.volume}
                    if definition.min_volume_ratio is not None
                    else {}
                ),
            }
            for bar in selected
        ],
    }
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(encoded).hexdigest()
