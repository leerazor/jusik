from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


def _validated_rate(value: Decimal, name: str) -> Decimal:
    if not value.is_finite() or value <= 0 or value > 1:
        raise ValueError(f"{name} must be finite and between zero and one.")
    return value


@dataclass(frozen=True)
class ResearchRiskPolicy:
    max_symbol_entry_exposure: Decimal = Decimal("0.20")
    max_total_entry_exposure: Decimal = Decimal("0.60")
    peak_close_drawdown_limit: Decimal = Decimal("0.10")

    def __post_init__(self) -> None:
        symbol = _validated_rate(
            self.max_symbol_entry_exposure, "max_symbol_entry_exposure"
        )
        total = _validated_rate(
            self.max_total_entry_exposure, "max_total_entry_exposure"
        )
        _validated_rate(self.peak_close_drawdown_limit, "peak_close_drawdown_limit")
        if symbol > total:
            raise ValueError(
                "max_symbol_entry_exposure must not exceed total exposure."
            )

    def as_json(self) -> dict[str, str]:
        return {
            "max_symbol_entry_exposure": str(self.max_symbol_entry_exposure),
            "max_total_entry_exposure": str(self.max_total_entry_exposure),
            "peak_close_drawdown_limit": str(self.peak_close_drawdown_limit),
        }


@dataclass(frozen=True)
class ExposureBreach:
    date: date
    stage: str
    scope: str
    observed_pct: Decimal
    limit_pct: Decimal

    def as_json(self) -> dict[str, str]:
        return {
            "date": self.date.isoformat(),
            "stage": self.stage,
            "scope": self.scope,
            "observed_pct": str(self.observed_pct),
            "limit_pct": str(self.limit_pct),
        }


@dataclass
class ResearchRiskReport:
    policy: ResearchRiskPolicy
    peak_close_equity: Decimal
    trigger_date: date | None = None
    trigger_drawdown_pct: Decimal | None = None
    max_total_exposure_pct: Decimal = Decimal()
    max_symbol_exposure_pct: Decimal = Decimal()
    exposure_breaches: list[ExposureBreach] = field(default_factory=list)
    remaining_positions: dict[str, int] = field(default_factory=dict)

    @classmethod
    def start(
        cls, policy: ResearchRiskPolicy, initial_cash: Decimal
    ) -> ResearchRiskReport:
        if not initial_cash.is_finite() or initial_cash < 0:
            raise ValueError("initial_cash must be finite and non-negative.")
        return cls(policy=policy, peak_close_equity=initial_cash)

    def observe_exposure(
        self,
        trading_date: date,
        stage: str,
        equity: Decimal,
        exposures: dict[str, Decimal],
    ) -> None:
        if equity <= 0:
            return
        total_pct = sum(exposures.values(), Decimal()) / equity * Decimal(100)
        symbol_pct = max(exposures.values(), default=Decimal()) / equity * Decimal(100)
        self.max_total_exposure_pct = max(self.max_total_exposure_pct, total_pct)
        self.max_symbol_exposure_pct = max(self.max_symbol_exposure_pct, symbol_pct)
        total_limit = self.policy.max_total_entry_exposure * Decimal(100)
        symbol_limit = self.policy.max_symbol_entry_exposure * Decimal(100)
        if total_pct > total_limit:
            self.exposure_breaches.append(
                ExposureBreach(trading_date, stage, "total", total_pct, total_limit)
            )
        for symbol, exposure in sorted(exposures.items()):
            observed = exposure / equity * Decimal(100)
            if observed > symbol_limit:
                self.exposure_breaches.append(
                    ExposureBreach(trading_date, stage, symbol, observed, symbol_limit)
                )

    def observe_close(self, trading_date: date, equity: Decimal) -> bool:
        self.peak_close_equity = max(self.peak_close_equity, equity)
        if self.trigger_date is not None or self.peak_close_equity <= 0:
            return False
        drawdown = (self.peak_close_equity - equity) / self.peak_close_equity
        if drawdown >= self.policy.peak_close_drawdown_limit:
            self.trigger_date = trading_date
            self.trigger_drawdown_pct = drawdown * Decimal(100)
            return True
        return False

    def finish(self, positions: dict[str, int]) -> None:
        self.remaining_positions = dict(sorted(positions.items()))

    def as_json(self) -> dict[str, object]:
        return {
            "policy": self.policy.as_json(),
            "trigger_date": self.trigger_date.isoformat()
            if self.trigger_date
            else None,
            "trigger_drawdown_pct": (
                str(self.trigger_drawdown_pct)
                if self.trigger_drawdown_pct is not None
                else None
            ),
            "peak_close_equity": str(self.peak_close_equity),
            "max_total_exposure_pct": str(self.max_total_exposure_pct),
            "max_symbol_exposure_pct": str(self.max_symbol_exposure_pct),
            "exposure_breaches": [
                breach.as_json() for breach in self.exposure_breaches
            ],
            "remaining_positions": self.remaining_positions,
        }
