"""Pure synthetic signal planning for the two frozen selected candidates.

The caller attests identity, provenance, and calendar coverage. This module checks
their shape and causal timestamps; it does not authenticate an actual data source.
Adjusted closes never enter the raw-price accounting ledger from here.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from typing import Literal

from jusik.approved_universe_buy_hold import Instrument

ZERO = Decimal(0)
ONE = Decimal(1)
CandidateMethod = Literal["equal", "inverse_volatility"]
Status = Literal["ready", "incomplete"]
EligibilityReason = Literal[
    "eligible", "insufficient_closes", "sma_not_above", "zero_volatility"
]


class SignalInputError(ValueError):
    """The supplied frozen synthetic signal input is inconsistent."""


@dataclass(frozen=True)
class AdjustedClose:
    instrument: Instrument
    official_close_at: datetime
    available_at: datetime
    adjusted_close: Decimal
    revision: int
    basis: str


@dataclass(frozen=True)
class SignalFX:
    effective_at: datetime
    available_at: datetime
    krw_per_usd: Decimal
    revision: int


@dataclass(frozen=True)
class FrozenSignalInput:
    registration_revision: int
    registration_hash: str
    registered: tuple[Instrument, ...]
    cohort: tuple[Instrument, ...]
    config_sha256: str
    price_source_hash: str
    fx_source_hash: str
    calendar_hash: str
    evidence_status: Literal["synthetic_unverified"]
    closes: tuple[AdjustedClose, ...]
    fx: tuple[SignalFX, ...]
    decided_at: datetime


@dataclass(frozen=True)
class Eligibility:
    instrument: Instrument
    reason: EligibilityReason


@dataclass(frozen=True)
class TargetWeight:
    instrument: Instrument
    weight: Decimal


@dataclass(frozen=True)
class SignalPlan:
    status: Status
    reason: str | None
    candidate: CandidateMethod
    decided_at: datetime
    config_sha256: str
    evidence_status: Literal["synthetic_unverified"]
    eligibility: tuple[Eligibility, ...]
    pre_scale: tuple[TargetWeight, ...] | None
    targets: tuple[TargetWeight, ...] | None
    volatility_proxy: Decimal | None
    volatility_scale: Decimal | None
    cash_weight: Decimal | None
    investment_qualification: Literal["not_evaluated"] = "not_evaluated"
    result_scope: Literal["synthetic_reference_only"] = "synthetic_reference_only"


@dataclass(frozen=True)
class _Policy:
    gross: Decimal
    symbol: Decimal
    leveraged: Decimal
    sma: int
    min_closes: int
    vol_returns: int
    target: Decimal
    annual_sessions: int
    fx_max_age_days: int


def _positive_decimal(value: object, label: str) -> Decimal:
    if not isinstance(value, (str, int, Decimal)) or isinstance(value, bool):
        raise SignalInputError(f"{label} must be a positive decimal")
    try:
        result = Decimal(value)
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise SignalInputError(f"{label} must be a positive decimal") from exc
    if not result.is_finite() or result <= ZERO:
        raise SignalInputError(f"{label} must be a positive finite decimal")
    return result


def _positive_int(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise SignalInputError(f"{label} must be a positive integer")
    return value


def _policy(
    config_json: bytes, supplied_hash: str, candidate: str, registration_revision: int
) -> _Policy:
    if hashlib.sha256(config_json).hexdigest() != supplied_hash:
        raise SignalInputError("config SHA-256 mismatch")
    try:
        document = json.loads(config_json)
        if not isinstance(document, dict):
            raise KeyError("document")
        if document["schema"] != "selected_candidate_config_v1":
            raise SignalInputError("unsupported config schema")
        if document["status"] != "hypothesis_only":
            raise SignalInputError("config must remain hypothesis only")
        if document["registered_revision"] != registration_revision:
            raise SignalInputError("registration revision differs from config")
        if (
            document["execution_allowed"] is not False
            or document["results_observed"] is not False
        ):
            raise SignalInputError("execution/result flags must remain blocked")
        if document["unresolved"]["candidate_execution_code_hash"] is not None:
            raise SignalInputError("candidate execution must remain unresolved")
        if document["candidates"] != [
            {"method": "equal", "gate": "none"},
            {"method": "inverse_volatility", "gate": "none"},
        ] or candidate not in ("equal", "inverse_volatility"):
            raise SignalInputError("unsupported candidate or gate")
        if document["policy"] != "low_turnover_combined":
            raise SignalInputError("unsupported policy")
        caps = document["caps"]
        signal = document["signal"]
        scale = document["volatility_scale"]
        if (
            signal["basis"] != "split_adjusted_close_for_signal_only"
            or signal["eligible_when"] != "latest_completed_close > trailing_SMA20"
            or signal["inverse_volatility_estimator"] != "population_standard_deviation"
            or scale["proxy"]
            != "sum(target_weight * asset_KRW_annualized_population_std)"
            or scale["sampling_dates"]
            != "last_61_distinct_UTC_close_dates_across_all_assets_before_decision"
            or scale["asset_close_asof"]
            != "latest_known_adjusted_close_at_or_before_each_UTC_day_end"
            or scale["fx_asof"]
            != "latest_USDKRW_observation_available_at_or_before_each_causal_cutoff"
            or scale["scale"] != "min(1, target/proxy)"
            or scale["missing_history_or_missing_or_stale_FX"] != "incomplete"
        ):
            raise SignalInputError("unsupported signal or volatility contract")
        policy = _Policy(
            gross=_positive_decimal(caps["gross"], "gross cap"),
            symbol=_positive_decimal(caps["symbol"], "symbol cap"),
            leveraged=_positive_decimal(
                caps["leveraged_etf_aggregate"], "leveraged cap"
            ),
            sma=int(signal["eligible_when"].rsplit("SMA", 1)[1]),
            min_closes=_positive_int(
                signal["minimum_completed_closes"], "minimum closes"
            ),
            vol_returns=_positive_int(
                signal["inverse_volatility_returns"], "volatility returns"
            ),
            target=_positive_decimal(scale["target_annualized"], "volatility target"),
            annual_sessions=_positive_int(
                scale["annualization_sessions"], "annual sessions"
            ),
            fx_max_age_days=_positive_int(scale["fx_max_age_calendar_days"], "FX age"),
        )
        if (
            policy.gross != Decimal("0.60")
            or policy.symbol != Decimal("0.20")
            or policy.leveraged != Decimal("0.20")
            or policy.sma != 20
            or policy.min_closes != 61
            or policy.vol_returns != 60
            or _positive_int(scale["return_window"], "proxy return window") != 60
            or policy.target != Decimal("0.10")
            or policy.annual_sessions != 252
            or policy.fx_max_age_days != 7
        ):
            raise SignalInputError("frozen numeric policy changed")
        return policy
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        if isinstance(exc, SignalInputError):
            raise
        raise SignalInputError("incomplete or invalid frozen config") from exc


def _utc(value: datetime, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise SignalInputError(f"{label} must be UTC aware")


def _hash(value: str, label: str) -> None:
    if re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise SignalInputError(f"{label} must be a SHA-256 hex digest")


def _identity_key(item: Instrument) -> tuple[str, str, str, str]:
    return item.market, item.exchange, item.symbol, item.identity_hash


def _validate(data: FrozenSignalInput) -> tuple[Instrument, ...]:
    _positive_int(data.registration_revision, "registration revision")
    for label, value in (
        ("registration hash", data.registration_hash),
        ("config hash", data.config_sha256),
        ("price source hash", data.price_source_hash),
        ("FX source hash", data.fx_source_hash),
        ("calendar hash", data.calendar_hash),
    ):
        _hash(value, label)
    if data.evidence_status != "synthetic_unverified":
        raise SignalInputError("only synthetic unverified evidence is supported")
    _utc(data.decided_at, "decision")
    if not data.registered or not data.cohort:
        raise SignalInputError("registered cohort is empty")
    seen: dict[tuple[str, str, str], Instrument] = {}
    for item in data.registered:
        if (
            item.market not in ("KR", "US")
            or not item.exchange.strip()
            or not item.symbol.strip()
            or not isinstance(item.leveraged, bool)
        ):
            raise SignalInputError("invalid registered identity")
        _hash(item.identity_hash, "identity hash")
        identity_key = item.market, item.exchange, item.symbol
        if identity_key in seen:
            raise SignalInputError("duplicate or conflicting registered identity")
        seen[identity_key] = item
    if len(set(data.cohort)) != len(data.cohort) or any(
        seen.get((item.market, item.exchange, item.symbol)) != item
        for item in data.cohort
    ):
        raise SignalInputError("cohort identity is duplicated or unregistered")
    cohort = tuple(sorted(data.cohort, key=_identity_key))
    close_keys: set[tuple[Instrument, datetime, int]] = set()
    close_dates: dict[tuple[Instrument, date], datetime] = {}
    for close_row in data.closes:
        if close_row.instrument not in cohort:
            raise SignalInputError("close identity is outside cohort")
        _utc(close_row.official_close_at, "official close")
        _utc(close_row.available_at, "close availability")
        if close_row.available_at < close_row.official_close_at:
            raise SignalInputError("close available before official close")
        if close_row.basis != "split_adjusted_close_for_signal_only":
            raise SignalInputError("unsupported signal price basis")
        _positive_decimal(close_row.adjusted_close, "adjusted close")
        _positive_int(close_row.revision, "close revision")
        close_key = (
            close_row.instrument,
            close_row.official_close_at,
            close_row.revision,
        )
        if close_key in close_keys:
            raise SignalInputError("duplicate close revision")
        close_keys.add(close_key)
        date_key = close_row.instrument, close_row.official_close_at.date()
        prior_at = close_dates.get(date_key)
        if prior_at is not None and prior_at != close_row.official_close_at:
            raise SignalInputError("conflicting official closes on one UTC date")
        close_dates[date_key] = close_row.official_close_at
    fx_keys: set[tuple[datetime, int]] = set()
    for fx_row in data.fx:
        _utc(fx_row.effective_at, "FX effective")
        _utc(fx_row.available_at, "FX availability")
        _positive_decimal(fx_row.krw_per_usd, "FX rate")
        _positive_int(fx_row.revision, "FX revision")
        fx_key = fx_row.effective_at, fx_row.revision
        if fx_key in fx_keys:
            raise SignalInputError("duplicate FX revision")
        fx_keys.add(fx_key)
    return cohort


def _asof_closes(
    rows: tuple[AdjustedClose, ...], cutoff: datetime
) -> dict[datetime, AdjustedClose]:
    selected: dict[datetime, AdjustedClose] = {}
    for row in rows:
        if row.available_at > cutoff or row.official_close_at > cutoff:
            continue
        previous = selected.get(row.official_close_at)
        if previous is None or row.revision > previous.revision:
            selected[row.official_close_at] = row
    return selected


def _sigma(values: list[Decimal]) -> Decimal:
    mean = sum(values, ZERO) / Decimal(len(values))
    return (
        sum(((value - mean) ** 2 for value in values), ZERO) / Decimal(len(values))
    ).sqrt()


def _returns(prices: list[Decimal]) -> list[Decimal]:
    return [
        current / previous - ONE
        for previous, current in zip(prices[:-1], prices[1:], strict=True)
    ]


def _capped_weights(
    raw: dict[Instrument, Decimal], cohort: tuple[Instrument, ...], policy: _Policy
) -> dict[Instrument, Decimal]:
    weights = {item: ZERO for item in cohort}
    remaining = {item for item in cohort if raw.get(item, ZERO) > ZERO}
    raw_total = sum(raw.values(), ZERO)
    while remaining:
        room = policy.gross - sum(weights.values(), ZERO)
        if room <= ZERO:
            break
        denominator = sum((raw[item] for item in remaining), ZERO)
        capped = {
            item
            for item in remaining
            if weights[item] + room * raw[item] / denominator >= policy.symbol
        }
        if not capped:
            ordered = sorted(remaining, key=_identity_key)
            for item in ordered[:-1]:
                weights[item] += min(
                    policy.symbol - weights[item],
                    max(ZERO, policy.gross - sum(weights.values(), ZERO)),
                    room * raw[item] / denominator,
                )
            last = ordered[-1]
            weights[last] += min(
                policy.symbol - weights[last],
                max(ZERO, policy.gross - sum(weights.values(), ZERO)),
            )
            break
        for item in sorted(capped, key=_identity_key):
            weights[item] = policy.symbol
        remaining -= capped
    leveraged = sum((weights[item] for item in cohort if item.leveraged), ZERO)
    if leveraged > policy.leveraged:
        factor = policy.leveraged / leveraged
        for item in cohort:
            if item.leveraged:
                weights[item] *= factor
    if raw_total <= ZERO:
        raise SignalInputError("impossible nonpositive raw weight")
    return weights


def _fx_asof(
    rows: tuple[SignalFX, ...], cutoff: datetime, max_age_days: int
) -> Decimal | None:
    eligible = [
        row for row in rows if row.effective_at <= cutoff and row.available_at <= cutoff
    ]
    if not eligible:
        return None
    latest = max(eligible, key=lambda row: (row.effective_at, row.revision))
    if (cutoff.date() - latest.effective_at.date()).days > max_age_days:
        return None
    return latest.krw_per_usd


def plan_selected_candidate(
    data: FrozenSignalInput, candidate: CandidateMethod, config_json: bytes
) -> SignalPlan:
    """Calculate synthetic weights only; an incomplete plan has no targets."""
    cohort = _validate(data)
    policy = _policy(
        config_json, data.config_sha256, candidate, data.registration_revision
    )
    by_asset = {
        item: tuple(row for row in data.closes if row.instrument == item)
        for item in cohort
    }
    eligibility: list[Eligibility] = []
    raw: dict[Instrument, Decimal] = {}
    for item in cohort:
        selected = _asof_closes(by_asset[item], data.decided_at)
        closes = [selected[at].adjusted_close for at in sorted(selected)]
        reason: EligibilityReason
        if len(closes) < policy.min_closes:
            reason = "insufficient_closes"
        elif closes[-1] <= sum(closes[-policy.sma :], ZERO) / Decimal(policy.sma):
            reason = "sma_not_above"
        elif candidate == "inverse_volatility":
            sigma = _sigma(_returns(closes[-(policy.vol_returns + 1) :]))
            if sigma == ZERO:
                reason = "zero_volatility"
            else:
                raw[item] = ONE / sigma
                reason = "eligible"
        else:
            raw[item] = ONE
            reason = "eligible"
        eligibility.append(Eligibility(item, reason))
    if not raw:
        zero = tuple(TargetWeight(item, ZERO) for item in cohort)
        return SignalPlan(
            "ready",
            None,
            candidate,
            data.decided_at,
            data.config_sha256,
            data.evidence_status,
            tuple(eligibility),
            zero,
            zero,
            ZERO,
            ONE,
            ONE,
        )
    weights = _capped_weights(raw, cohort, policy)
    pre_scale = tuple(TargetWeight(item, weights[item]) for item in cohort)
    global_days = sorted(
        {
            row.official_close_at.date()
            for row in data.closes
            if row.official_close_at < data.decided_at
            and row.available_at <= data.decided_at
        }
    )[-(policy.vol_returns + 1) :]

    def incomplete(reason: str) -> SignalPlan:
        return SignalPlan(
            "incomplete",
            reason,
            candidate,
            data.decided_at,
            data.config_sha256,
            data.evidence_status,
            tuple(eligibility),
            None,
            None,
            None,
            None,
            None,
        )

    if len(global_days) < policy.vol_returns + 1:
        return incomplete("insufficient_global_close_dates")
    proxy = ZERO
    for item in cohort:
        weight = weights[item]
        if weight == ZERO:
            continue
        values: list[Decimal] = []
        for day in global_days:
            cutoff = min(datetime.combine(day, time.max, UTC), data.decided_at)
            selected = _asof_closes(by_asset[item], cutoff)
            if not selected:
                return incomplete("missing_historical_close")
            latest = selected[max(selected)].adjusted_close
            if item.market == "US":
                fx = _fx_asof(data.fx, cutoff, policy.fx_max_age_days)
                if fx is None:
                    return incomplete("missing_or_stale_fx")
                latest *= fx
            values.append(latest)
        proxy += (
            weight * _sigma(_returns(values)) * Decimal(policy.annual_sessions).sqrt()
        )
    scale = min(ONE, policy.target / proxy) if proxy > ZERO else ONE
    targets = tuple(TargetWeight(item, weights[item] * scale) for item in cohort)
    cash = ONE - sum((target.weight for target in targets), ZERO)
    if (
        cash < ZERO
        or sum((target.weight for target in targets), ZERO) > policy.gross
        or any(target.weight > policy.symbol for target in targets)
        or sum(
            (target.weight for target in targets if target.instrument.leveraged), ZERO
        )
        > policy.leveraged
    ):
        raise SignalInputError("computed weights violate frozen caps")
    return SignalPlan(
        "ready",
        None,
        candidate,
        data.decided_at,
        data.config_sha256,
        data.evidence_status,
        tuple(eligibility),
        pre_scale,
        targets,
        proxy,
        scale,
        cash,
    )
