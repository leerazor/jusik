from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time
from decimal import Decimal
from typing import Literal
from zoneinfo import ZoneInfo

from jusik.research_engine import SignalFunction
from jusik.research_external_models import (
    ExternalFeatureSnapshot,
    ExternalObservation,
    ExternalSeries,
)
from jusik.research_models import BASELINE_VERSION, DailyBar
from jusik.research_strategy import target_invested

MacroGate = Literal["rates", "fx_vix", "stress"]
CONTROL_PARAMETERS: tuple[tuple[str, object], ...] = (
    ("variant", "unfiltered_trend_20_control"),
)


@dataclass(frozen=True)
class MacroGateConfig:
    required_series: tuple[ExternalSeries, ...]
    parameters: tuple[tuple[str, object], ...]

    def candidate_parameters(self, gate: MacroGate) -> dict[str, object]:
        return {"variant": gate, **dict(self.parameters)}


GATE_CONFIGS: dict[MacroGate, MacroGateConfig] = {
    "rates": MacroGateConfig(
        required_series=("treasury_2y", "treasury_10y"),
        parameters=(
            ("observation_lookback", 20),
            ("max_age_days", 7),
            ("minimum_spread_pp", "-1"),
            ("maximum_10y_change_pp", "0.50"),
        ),
    ),
    "fx_vix": MacroGateConfig(
        required_series=("usdkrw", "vix"),
        parameters=(
            ("observation_lookback", 20),
            ("max_age_days", 7),
            ("maximum_usdkrw_return", "0.05"),
            ("maximum_vix", "30"),
        ),
    ),
    "stress": MacroGateConfig(
        required_series=("uso", "gld", "hyg"),
        parameters=(
            ("observation_lookback", 20),
            ("max_age_days", 7),
            ("maximum_uso_return", "0.15"),
            ("maximum_gld_return", "0.10"),
            ("minimum_hyg_return", "-0.03"),
        ),
    ),
}


def macro_candidate_parameters(gate: MacroGate) -> dict[str, object]:
    return GATE_CONFIGS[gate].candidate_parameters(gate)


def control_candidate_parameters() -> dict[str, object]:
    return dict(CONTROL_PARAMETERS)


def _integer_parameter(value: object, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"Invalid macro gate integer parameter: {name}")
    return value


@dataclass
class ExternalSignalDiagnostics:
    decision_dates: set[date] = field(default_factory=set)
    missing_dates: set[date] = field(default_factory=set)
    missing_reasons: dict[str, int] = field(default_factory=dict)

    def record(self, day: date, reason: str | None) -> None:
        self.decision_dates.add(day)
        if reason is None:
            return
        if day in self.missing_dates:
            return
        self.missing_dates.add(day)
        self.missing_reasons[reason] = self.missing_reasons.get(reason, 0) + 1

    def as_json(self) -> dict[str, object]:
        return {
            "decision_date_count": len(self.decision_dates),
            "missing_date_count": len(self.missing_dates),
            "missing_reasons": dict(sorted(self.missing_reasons.items())),
            "complete": not self.missing_dates,
        }


def decision_cutoff(day: date, timezone_name: str) -> datetime:
    if timezone_name not in {"Asia/Seoul", "America/New_York"}:
        raise ValueError("Unsupported research exchange timezone.")
    hour, minute = (15, 30) if timezone_name == "Asia/Seoul" else (16, 0)
    return datetime.combine(
        day, time(hour, minute), ZoneInfo(timezone_name)
    ).astimezone(UTC)


def _as_of_observations(
    snapshot: ExternalFeatureSnapshot,
    series: ExternalSeries,
    day: date,
    cutoff: datetime,
) -> list[ExternalObservation]:
    revisions: dict[date, ExternalObservation] = {}
    for item in snapshot.observations:
        if (
            item.series != series
            or item.observed_on > day
            or item.available_at > cutoff
        ):
            continue
        prior = revisions.get(item.observed_on)
        if prior is None or (item.available_at, item.revision) > (
            prior.available_at,
            prior.revision,
        ):
            revisions[item.observed_on] = item
    return [revisions[key] for key in sorted(revisions)]


def _window(
    snapshot: ExternalFeatureSnapshot,
    series: ExternalSeries,
    day: date,
    timezone_name: str,
    observation_lookback: int,
    max_age_days: int,
) -> tuple[list[Decimal] | None, str | None]:
    items = _as_of_observations(
        snapshot, series, day, decision_cutoff(day, timezone_name)
    )
    if len(items) < observation_lookback + 1:
        return None, f"{series}:관측값부족"
    selected = items[-(observation_lookback + 1) :]
    if (day - selected[-1].observed_on).days > max_age_days:
        return None, f"{series}:7일초과"
    return [item.value for item in selected], None


def evaluate_gate(
    gate: MacroGate,
    snapshot: ExternalFeatureSnapshot | None,
    day: date,
    timezone_name: str,
) -> tuple[bool | None, str | None]:
    if snapshot is None:
        return None, "외부변수스냅샷없음"
    config = GATE_CONFIGS[gate]
    parameters = config.candidate_parameters(gate)
    observation_lookback = _integer_parameter(
        parameters["observation_lookback"], "observation_lookback"
    )
    max_age_days = _integer_parameter(parameters["max_age_days"], "max_age_days")
    windows: dict[ExternalSeries, list[Decimal]] = {}
    for series in config.required_series:
        values, reason = _window(
            snapshot,
            series,
            day,
            timezone_name,
            observation_lookback,
            max_age_days,
        )
        if values is None:
            return None, reason
        windows[series] = values
    if gate == "rates":
        two_year = windows["treasury_2y"][-1]
        ten_year = windows["treasury_10y"]
        return (
            ten_year[-1] - two_year >= Decimal(str(parameters["minimum_spread_pp"]))
            and ten_year[-1] - ten_year[0]
            <= Decimal(str(parameters["maximum_10y_change_pp"]))
        ), None
    if gate == "fx_vix":
        fx = windows["usdkrw"]
        return (
            fx[-1] / fx[0] - 1 <= Decimal(str(parameters["maximum_usdkrw_return"]))
            and windows["vix"][-1] <= Decimal(str(parameters["maximum_vix"]))
        ), None
    uso = windows["uso"]
    gld = windows["gld"]
    hyg = windows["hyg"]
    return (
        uso[-1] / uso[0] - 1 <= Decimal(str(parameters["maximum_uso_return"]))
        and gld[-1] / gld[0] - 1 <= Decimal(str(parameters["maximum_gld_return"]))
        and hyg[-1] / hyg[0] - 1 >= Decimal(str(parameters["minimum_hyg_return"]))
    ), None


def macro_signal(
    gate: MacroGate,
    snapshot: ExternalFeatureSnapshot | None,
    timezone_name: str,
    diagnostics: ExternalSignalDiagnostics,
) -> SignalFunction:
    def signal(_symbol: str, bars: tuple[DailyBar, ...]) -> bool:
        day = bars[-1].date
        allowed, reason = evaluate_gate(gate, snapshot, day, timezone_name)
        diagnostics.record(day, reason)
        if allowed is not True:
            return False
        return target_invested(BASELINE_VERSION, list(bars), len(bars) - 1)

    return signal


def validation_coverage(
    gate: MacroGate,
    snapshot: ExternalFeatureSnapshot | None,
    decision_dates: Sequence[date],
    timezone_name: str,
) -> tuple[bool, dict[str, object]]:
    missing: dict[str, int] = defaultdict(int)
    missing_dates: set[date] = set()
    for day in decision_dates:
        _value, reason = evaluate_gate(gate, snapshot, day, timezone_name)
        if reason is not None:
            missing[reason] += 1
            missing_dates.add(day)
    result: dict[str, object] = {
        "decision_date_count": len(set(decision_dates)),
        "missing_date_count": len(missing_dates),
        "missing_reasons": dict(sorted(missing.items())),
        "complete": not missing_dates,
    }
    return not missing_dates, result
