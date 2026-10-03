"""Synthetic KR candidate policy bridge; no actual source acceptance."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Literal

from jusik.approved_universe_buy_hold import (
    INITIAL_KRW,
    LIMIT,
    FrozenReferenceInput,
    HoldQuantityInstruction,
    Instrument,
    KRInstruction,
    KRPolicyDirective,
    KRTargetSequenceReference,
    ReferencePoint,
    SellCostAssumptions,
    TargetInstruction,
    _run_reference_core,
    _sell_rates,
    _time,
)
from jusik.selected_candidate_signals import (
    CandidateMethod,
    FrozenSignalInput,
    SignalPlan,
    plan_selected_candidate,
)

BAND = Fraction(Decimal("0.02"))
GROSS = Fraction(Decimal("0.60"))
EPISODE_EXIT = Fraction(Decimal("0.10"))
_SOURCE_ROOT = Path(__file__).resolve().parents[2]
_SOURCE_PATHS = (
    "backend/jusik/research_portfolio_models.py",
    "backend/jusik/research_portfolio_engine.py",
    "backend/jusik/approved_universe_buy_hold.py",
    "backend/jusik/market_history_action_accounting.py",
    "backend/jusik/selected_candidate_signals.py",
    "backend/jusik/selected_candidate_kr_policy.py",
)


class PolicyInputError(ValueError):
    """Frozen synthetic policy input is unsupported or incomplete."""


class RiskPolicyRequired(PolicyInputError):
    """A completed close reached the episode exit threshold."""

    def __init__(self, point: ReferencePoint, episode_peak_krw: Decimal) -> None:
        self.point = point
        self.episode_peak_krw = episode_peak_krw
        super().__init__(f"risk_policy_required at {point.at.isoformat()}")


@dataclass(frozen=True)
class CandidateDecision:
    at: datetime
    signal: SignalPlan
    hold_quantities: tuple[tuple[Instrument, Decimal], ...]


@dataclass(frozen=True)
class KRCandidatePolicyReference:
    status: Literal["synthetic_reference_only"]
    candidate: CandidateMethod
    decisions: tuple[CandidateDecision, ...]
    ledger: KRTargetSequenceReference
    episode_peak_krw: Decimal
    episode_max_drawdown_fraction: Decimal
    lifetime_peak_krw: Decimal
    investment_qualification: Literal["not_evaluated"] = "not_evaluated"


@dataclass(frozen=True)
class KRRiskEvent:
    at: datetime
    status: Literal[
        "latched",
        "liquidation_completed",
        "all_cash_completed",
        "cooldown",
        "recovery_confirmed",
        "recovery_reset",
        "reentry_ready",
        "reentry_decision",
    ]
    consecutive_confirmations: int = 0
    reason: str | None = None


@dataclass(frozen=True)
class KRCapEvent:
    observed_at: datetime
    at: datetime
    status: Literal["observed", "natural_recovery", "repaired", "repaired_by_target"]
    pre_nav_krw: Decimal
    post_nav_krw: Decimal
    pre_leveraged_value_krw: Decimal
    post_leveraged_value_krw: Decimal


@dataclass(frozen=True)
class KRCandidateRiskReference:
    status: Literal["synthetic_reference_only"]
    candidate: CandidateMethod
    decisions: tuple[CandidateDecision, ...]
    risk_events: tuple[KRRiskEvent, ...]
    cap_events: tuple[KRCapEvent, ...]
    ledger: KRTargetSequenceReference
    episode_peak_krw: Decimal
    episode_max_drawdown_fraction: Decimal
    lifetime_peak_krw: Decimal
    investment_qualification: Literal["not_evaluated"] = "not_evaluated"


def _schedule(start: datetime, end: datetime) -> tuple[datetime, ...]:
    start, end = _time(start, "evaluation start"), _time(end, "evaluation end")
    monday = (start + timedelta(days=(7 - start.weekday()) % 7)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    if monday < start:
        monday += timedelta(days=7)
    dates: list[datetime] = []
    while monday < end:
        dates.append(monday)
        monday += timedelta(days=28)
    if not dates:
        raise PolicyInputError("no scheduled Monday decision in evaluation window")
    return tuple(dates)


def _frozen_config(config_bytes: bytes, signal: FrozenSignalInput) -> None:
    if not isinstance(config_bytes, bytes):
        raise PolicyInputError("frozen config bytes required")
    if hashlib.sha256(config_bytes).hexdigest() != signal.config_sha256:
        raise PolicyInputError("frozen config SHA-256 mismatch")
    try:
        document = json.loads(config_bytes)
        if not isinstance(document, dict):
            raise PolicyInputError("frozen config object required")
        if (
            document["initial_cash_krw"] != "100000000"
            or document["registered_revision"] != 1
            or document["rebalance"]
            != {
                "every_weeks": 4,
                "anchor": "first_Monday_on_or_after_evaluation_start",
                "decision_time": "Monday_00:00_UTC",
                "band_absolute_weight": "0.02",
                "skip_only_if": (
                    "positive_target_and_abs_difference_less_than_band_"
                    "and_no_cap_violation"
                ),
                "zero_targets_and_risk_exits_exempt": True,
            }
            or document["drawdown"]
            != {
                "episode_liquidation_latch": "0.10",
                "episode_peak_resets_on_reentry": True,
                "lifetime_peak_MDD_hard_filter": "0.20",
            }
            or document["reentry"]
            != {
                "cooldown_calendar_days_after_completed_liquidation": 28,
                "weekly_recovery_confirmations": 2,
                "minimum_eligible_assets": 2,
                "execute_on_next_scheduled_rebalance": True,
            }
            or document["timing"]
            != {
                "signal": "official_close_at_or_before_decision",
                "execution": "first_eligible_official_open_strictly_after_decision",
                "FX": (
                    "available_at_at_or_before_each_causal_cutoff_"
                    "no_future_observations"
                ),
            }
        ):
            raise PolicyInputError("frozen KR policy values differ")
        sources = document["semantic_sources_sha256"]
        if not isinstance(sources, dict) or set(sources) != set(_SOURCE_PATHS):
            raise PolicyInputError("fixed semantic source paths differ")
        for source in _SOURCE_PATHS:
            expected = sources[source]
            if (
                not isinstance(expected, str)
                or len(expected) != 64
                or any(char not in "0123456789abcdef" for char in expected)
            ):
                raise PolicyInputError(f"malformed semantic source pin: {source}")
            actual = hashlib.sha256((_SOURCE_ROOT / source).read_bytes()).hexdigest()
            if expected != actual:
                raise PolicyInputError(f"semantic source hash differs: {source}")
    except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError) as exc:
        if isinstance(exc, PolicyInputError):
            raise
        raise PolicyInputError("frozen KR policy config incomplete") from exc


def _bind_inputs(raw: FrozenReferenceInput, signal: FrozenSignalInput) -> None:
    if (
        raw.registration_revision != 1
        or signal.registration_revision != raw.registration_revision
        or signal.registration_hash != raw.registration_hash
        or signal.calendar_hash != raw.official_calendar_hash
        or set(signal.registered) != set(raw.registered)
        or len(signal.registered) != len(raw.registered)
        or set(signal.cohort) != set(raw.cohort)
        or len(signal.cohort) != len(raw.cohort)
        or any(item.market != "KR" for item in raw.cohort)
    ):
        raise PolicyInputError("raw/signal registry identity or calendar mismatch")
    # Adjusted signal prices and raw execution prices retain separate evidence pins.
    if signal.price_source_hash == "" or raw.price_evidence_hash == "":
        raise PolicyInputError("separate signal/raw source pins required")


def _hold_in_band(
    target: Decimal, value: Decimal, nav: Decimal, *, caps_clear: bool
) -> bool:
    return (
        target > 0
        and caps_clear
        and abs(Fraction(target) - Fraction(value) / Fraction(nav)) < BAND
    )


def run_kr_selected_candidate_reference(
    raw_input: FrozenReferenceInput,
    signal_input: FrozenSignalInput,
    config_bytes: bytes,
    candidate: CandidateMethod,
    sell_costs: SellCostAssumptions,
) -> KRCandidatePolicyReference:
    """Run one fixed method over a synthetic, risk-event-free KR interval."""
    _bind_inputs(raw_input, signal_input)
    _frozen_config(config_bytes, signal_input)
    _sell_rates(sell_costs)
    dates = _schedule(raw_input.evaluation_start, raw_input.evaluation_end)
    if _time(signal_input.decided_at, "signal decision") != dates[0]:
        raise PolicyInputError("signal template decision differs from schedule")
    decisions: list[CandidateDecision] = []
    episode_peak = INITIAL_KRW
    episode_max_drawdown = Decimal(0)

    def at_decision(at: datetime, prior: ReferencePoint) -> tuple[KRInstruction, ...]:
        planned = plan_selected_candidate(
            replace(signal_input, decided_at=at), candidate, config_bytes
        )
        if planned.status != "ready" or planned.targets is None:
            raise PolicyInputError(f"signal_incomplete: {planned.reason}")
        positions = {position.instrument: position for position in prior.positions}
        gross = sum((Fraction(p.value_krw) for p in prior.positions), Fraction(0))
        cap_breached = (
            gross > GROSS * Fraction(prior.nav_krw)
            or Fraction(prior.leveraged_value_krw)
            > Fraction(LIMIT) * Fraction(prior.nav_krw)
            or any(
                Fraction(p.value_krw) > Fraction(LIMIT) * Fraction(prior.nav_krw)
                for p in prior.positions
            )
        )
        instructions: list[KRInstruction] = []
        holds: list[tuple[Instrument, Decimal]] = []
        for target in planned.targets:
            position = positions.get(target.instrument)
            quantity = position.quantity if position is not None else Decimal(0)
            value = position.value_krw if position is not None else Decimal(0)
            if _hold_in_band(
                target.weight, value, prior.nav_krw, caps_clear=not cap_breached
            ):
                instructions.append(
                    HoldQuantityInstruction(
                        target.instrument, at, target.weight, quantity
                    )
                )
                holds.append((target.instrument, quantity))
            else:
                instructions.append(
                    TargetInstruction(target.instrument, at, target.weight)
                )
        decisions.append(CandidateDecision(at, planned, tuple(holds)))
        return tuple(instructions)

    def at_close(point: ReferencePoint) -> None:
        nonlocal episode_peak, episode_max_drawdown
        episode_peak = max(episode_peak, point.nav_krw)
        drawdown = (episode_peak - point.nav_krw) / episode_peak
        episode_max_drawdown = max(episode_max_drawdown, drawdown)
        if Fraction(episode_peak - point.nav_krw) >= EPISODE_EXIT * Fraction(
            episode_peak
        ):
            raise RiskPolicyRequired(point, episode_peak)

    result = _run_reference_core(
        raw_input,
        sell_costs=sell_costs,
        kr_decision_times=dates,
        kr_decision_hook=at_decision,
        kr_close_hook=at_close,
    )
    assert isinstance(result, KRTargetSequenceReference)
    return KRCandidatePolicyReference(
        "synthetic_reference_only",
        candidate,
        tuple(decisions),
        result,
        episode_peak,
        episode_max_drawdown,
        max((INITIAL_KRW, *(point.nav_krw for point in result.points))),
    )


def run_kr_selected_candidate_risk_reference(
    raw_input: FrozenReferenceInput,
    signal_input: FrozenSignalInput,
    config_bytes: bytes,
    candidate: CandidateMethod,
    sell_costs: SellCostAssumptions,
) -> KRCandidateRiskReference:
    """Run the fixed KR candidate with synthetic episode exit and reentry."""
    _bind_inputs(raw_input, signal_input)
    _frozen_config(config_bytes, signal_input)
    _sell_rates(sell_costs)
    scheduled = _schedule(raw_input.evaluation_start, raw_input.evaluation_end)
    if _time(signal_input.decided_at, "signal decision") != scheduled[0]:
        raise PolicyInputError("signal template decision differs from schedule")
    cadence = set(scheduled)
    weekly: list[datetime] = []
    monday = scheduled[0]
    while monday < _time(raw_input.evaluation_end, "evaluation end"):
        weekly.append(monday)
        monday += timedelta(days=7)
    ordered = tuple(
        sorted(
            raw_input.cohort,
            key=lambda item: (
                item.market,
                item.exchange,
                item.symbol,
                item.identity_hash,
            ),
        )
    )
    decisions: list[CandidateDecision] = []
    risk_events: list[KRRiskEvent] = []
    cap_events: list[KRCapEvent] = []
    episode_peak = INITIAL_KRW
    episode_max_drawdown = Decimal(0)
    latched = False
    liquidation_completed_at: datetime | None = None
    confirmations = 0
    ready_at: datetime | None = None

    def plan(at: datetime) -> SignalPlan:
        return plan_selected_candidate(
            replace(signal_input, decided_at=at), candidate, config_bytes
        )

    def vector_for(
        at: datetime, prior: ReferencePoint, planned: SignalPlan, *, reentry: bool
    ) -> tuple[KRInstruction, ...]:
        if planned.status != "ready" or planned.targets is None:
            raise PolicyInputError(f"signal_incomplete: {planned.reason}")
        positions = {position.instrument: position for position in prior.positions}
        gross = sum((Fraction(p.value_krw) for p in prior.positions), Fraction(0))
        cap_breached = (
            gross > GROSS * Fraction(prior.nav_krw)
            or Fraction(prior.leveraged_value_krw)
            > Fraction(LIMIT) * Fraction(prior.nav_krw)
            or any(
                Fraction(p.value_krw) > Fraction(LIMIT) * Fraction(prior.nav_krw)
                for p in prior.positions
            )
        )
        instructions: list[KRInstruction] = []
        holds: list[tuple[Instrument, Decimal]] = []
        for target in planned.targets:
            position = positions.get(target.instrument)
            quantity = position.quantity if position is not None else Decimal(0)
            value = position.value_krw if position is not None else Decimal(0)
            if not reentry and _hold_in_band(
                target.weight, value, prior.nav_krw, caps_clear=not cap_breached
            ):
                instructions.append(
                    HoldQuantityInstruction(
                        target.instrument, at, target.weight, quantity
                    )
                )
                holds.append((target.instrument, quantity))
            else:
                instructions.append(
                    TargetInstruction(target.instrument, at, target.weight)
                )
        decisions.append(CandidateDecision(at, planned, tuple(holds)))
        return tuple(instructions)

    def at_event(at: datetime, phase: str, prior: ReferencePoint) -> KRPolicyDirective:
        nonlocal episode_peak, episode_max_drawdown, latched
        nonlocal liquidation_completed_at, confirmations, ready_at
        if phase == "close":
            if latched:
                return KRPolicyDirective()
            episode_peak = max(episode_peak, prior.nav_krw)
            drawdown = (episode_peak - prior.nav_krw) / episode_peak
            episode_max_drawdown = max(episode_max_drawdown, drawdown)
            if Fraction(episode_peak - prior.nav_krw) < EPISODE_EXIT * Fraction(
                episode_peak
            ):
                return KRPolicyDirective()
            latched = True
            confirmations = 0
            ready_at = None
            risk_events.append(KRRiskEvent(at, "latched"))
            if all(position.quantity == 0 for position in prior.positions):
                liquidation_completed_at = at
                risk_events.append(KRRiskEvent(at, "all_cash_completed"))
                return KRPolicyDirective(cancel_pending=True)
            liquidation_completed_at = None
            return KRPolicyDirective(
                tuple(TargetInstruction(item, at, Decimal(0)) for item in ordered),
                cancel_pending=True,
                liquidation=True,
            )
        if at not in cadence and not latched:
            return KRPolicyDirective()
        if latched:
            if liquidation_completed_at is None:
                return KRPolicyDirective()
            if at.date() < liquidation_completed_at.astimezone(UTC).date() + timedelta(
                days=28
            ):
                risk_events.append(KRRiskEvent(at, "cooldown"))
                return KRPolicyDirective()
            planned = plan(at)
            valid = (
                planned.status == "ready"
                and planned.targets is not None
                and sum(target.weight > 0 for target in planned.targets) >= 2
            )
            if not valid:
                confirmations = 0
                ready_at = None
                reason = (
                    planned.reason
                    if planned.status != "ready"
                    else "insufficient_eligible_assets"
                )
                risk_events.append(KRRiskEvent(at, "recovery_reset", reason=reason))
                return KRPolicyDirective()
            confirmations += 1
            risk_events.append(KRRiskEvent(at, "recovery_confirmed", confirmations))
            if confirmations == 2:
                ready_at = at
                risk_events.append(KRRiskEvent(at, "reentry_ready", confirmations))
            if at not in cadence or ready_at is None or at <= ready_at:
                return KRPolicyDirective()
            episode_peak = prior.nav_krw
            latched = False
            liquidation_completed_at = None
            confirmations = 0
            ready_at = None
            risk_events.append(KRRiskEvent(at, "reentry_decision"))
            return KRPolicyDirective(vector_for(at, prior, planned, reentry=True))
        if at not in cadence:
            return KRPolicyDirective()
        return KRPolicyDirective(vector_for(at, prior, plan(at), reentry=False))

    def at_fill(at: datetime, after: ReferencePoint, liquidation: bool) -> None:
        nonlocal liquidation_completed_at
        if liquidation:
            if any(position.quantity != 0 for position in after.positions):
                raise PolicyInputError("risk liquidation incomplete")
            liquidation_completed_at = at
            risk_events.append(KRRiskEvent(at, "liquidation_completed"))

    def at_cap(
        observed_at: datetime,
        at: datetime,
        status: str,
        before: ReferencePoint,
        after: ReferencePoint,
    ) -> None:
        if status not in (
            "observed",
            "natural_recovery",
            "repaired",
            "repaired_by_target",
        ):
            raise PolicyInputError("unsupported cap event")
        cap_events.append(
            KRCapEvent(
                observed_at,
                at,
                status,  # type: ignore[arg-type]
                before.nav_krw,
                after.nav_krw,
                before.leveraged_value_krw,
                after.leveraged_value_krw,
            )
        )

    result = _run_reference_core(
        raw_input,
        sell_costs=sell_costs,
        kr_decision_times=tuple(weekly),
        kr_dynamic_hook=at_event,
        kr_dynamic_fill_hook=at_fill,
        kr_dynamic_cap_hook=at_cap,
    )
    assert isinstance(result, KRTargetSequenceReference)
    if latched and liquidation_completed_at is None:
        raise PolicyInputError("risk liquidation window_end_unfilled")
    return KRCandidateRiskReference(
        "synthetic_reference_only",
        candidate,
        tuple(decisions),
        tuple(risk_events),
        tuple(cap_events),
        result,
        episode_peak,
        episode_max_drawdown,
        max((INITIAL_KRW, *(point.nav_krw for point in result.points))),
    )
