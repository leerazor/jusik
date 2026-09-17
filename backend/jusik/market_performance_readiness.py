"""Read-only readiness diagnostics for a saved market research run.

The adapter intentionally does not import the research models, strategy,
collector, runner, or performance evaluator.  A saved canonical run is only
eligible for a deterministic evidence check; this module never calculates
performance or promotes an approximate result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Final

from .market_history_models import MarketResearchRun
from .market_performance_policy import (
    PolicyValidationError,
    load_calculation_policy,
    policy_facts,
)

SCHEMA: Final = "market-performance-readiness/v1"
TARGET_SCHEMA: Final = "market-performance-metrics-input/v1"
EVIDENCE_SCHEMA: Final = "r0-us-session-evidence/v1"
CANONICAL_MANIFEST_SHA256: Final = (
    "03ff5a140138277d2161a0896c7c8aefd64abe0545de7cc33ed9270882481205"
)
CANONICAL_RUN_SHA256: Final = (
    "cc9150f8b77a27ffd6b001449c0475933ff744a37011801923f87cbdc5558275"
)
CANONICAL_EVIDENCE_SHA256: Final = (
    "9348e2f3f6d2120e99460e34dd0a20e285bd14daf6c1f45f96df688b7bc1046a"
)
CALENDAR_BYTES_SHA256: Final = (
    "ba26619a27e066ca32b1aaaf3b7da2b99f0c6658f731a000c5095c057081c1d8"
)
CALENDAR_PAYLOAD_SHA256: Final = (
    "e9f86c7e47c8d3cd6ee628e48be12c0379e428f12f9f66f04de52cc272cb122d"
)
CANONICAL_EVIDENCE_PATH: Final = (
    Path(__file__).with_name("data") / "r0_us_session_evidence_v1.json"
)
CANONICAL_AUDIT_ROOT: Final = (
    Path.home() / ".local" / "share" / "jusik" / "portfolio-audit"
)
TRACKED_CALENDAR_PATH: Final = (
    Path(__file__).with_name("data") / "market_sessions_2023_2026.json"
)
MAX_SOURCE_BYTES: Final = 10 * 1024 * 1024
MAX_EVIDENCE_BYTES: Final = 1 * 1024 * 1024
MAX_NAV_POINTS: Final = 5_000
MISSING_CODES: Final = (
    "missing_initial_capital_at",
    "missing_nav_timestamps",
    "missing_session_completeness_evidence",
    "missing_calendar_evidence",
    "missing_cost_inclusion_evidence",
    "missing_risk_free_evidence",
    "missing_calculation_policy",
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_INPUT_SCHEMAS = frozenset(("MarketResearchRun", "market-research-run/v1"))
_SOURCE_NAMES = frozenset(
    ("fixture", "krx", "massive", "yahoo", "alpha_vantage", "fred", "approximate_file")
)
_CAPABILITY_NAMES = frozenset(
    (
        "credentials",
        "entitlement",
        "calendar",
        "membership",
        "bars",
        "actions",
        "fx",
        "policy",
    )
)
_CAPABILITY_STATUSES = frozenset(("ready", "missing", "unsupported", "partial"))
_TOP_FIELDS = frozenset(
    (
        "id",
        "status",
        "request",
        "result",
        "input_hash",
        "created_at",
        "updated_at",
        "error",
        "stage",
        "pilot_run_id",
        "data_contract_hash",
        "final_promotable",
        "final_promotability_reason",
        "schema",
    )
)
_REQUEST_FIELDS = frozenset(
    (
        "market",
        "start_date",
        "end_date",
        "stage",
        "pilot_run_id",
        "initial_cash_krw",
        "fee_rate",
        "slippage_rate",
        "sell_tax_rate",
        "research_grade",
    )
)
_RESULT_FIELDS = frozenset(
    (
        "market",
        "request",
        "readiness",
        "status",
        "completeness",
        "candidate_evidence",
        "trades",
        "equity",
        "limitations",
        "metrics",
        "input_hash",
        "policy_hash",
        "stage",
        "pilot_run_id",
        "data_contract_hash",
        "warmup_sessions",
        "research_grade",
        "pool_contract_hash",
        "provenance",
        "account",
    )
)
_READINESS_FIELDS = frozenset(
    ("market", "checked_at", "capabilities", "ready", "simulated", "research_grade")
)
_CAPABILITY_FIELDS = frozenset(("name", "status", "detail", "missing_ranges"))
_EQUITY_FIELDS = frozenset(
    (
        "session",
        "cash_krw",
        "cash_native",
        "invested_krw",
        "nav_krw",
        "fx_krw_per_usd",
        "drawdown_pct",
    )
)
_PROVENANCE_FIELDS = frozenset(
    (
        "universe_sources",
        "bar_sources",
        "fx_sources",
        "artifact_sources",
        "normalization_version",
        "captured_at",
    )
)
_ACCOUNT_FIELDS = frozenset(
    (
        "account_scope",
        "reporting_currency",
        "native_currency",
        "initial_cash_krw",
        "fx_krw_per_usd",
        "initial_cash_conversion",
    )
)
_CANDIDATE_FIELDS = frozenset(
    (
        "session",
        "symbol",
        "rank",
        "volume",
        "eligible",
        "membership_available_at",
        "bar_available_at",
    )
)
_TRADE_FIELDS = frozenset(
    (
        "session",
        "signal_session",
        "fill_session",
        "symbol",
        "side",
        "quantity",
        "currency",
        "market_open",
        "fill_price",
        "notional",
        "fee",
        "tax",
        "rationale",
    )
)


class ReadinessInputError(ValueError):
    """A safe, stable error for malformed or unsupported source input."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class _DuplicateKey(ValueError):
    pass


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKey
        result[key] = value
    return result


def _reject_nonfinite(value: str) -> Decimal:
    raise ValueError(value)


def _parse_json(raw: bytes) -> dict[str, object]:
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_int=Decimal,
            parse_float=Decimal,
            parse_constant=_reject_nonfinite,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError):
        raise ReadinessInputError("malformed_input") from None
    if not isinstance(value, dict):
        raise ReadinessInputError("malformed_input")
    return value


def _required(mapping: Mapping[str, object], key: str) -> object:
    if key not in mapping:
        raise ReadinessInputError("missing_required_field")
    return mapping[key]


def _mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ReadinessInputError("malformed_input")
    return value


def _list(value: object) -> list[object]:
    if not isinstance(value, list):
        raise ReadinessInputError("malformed_input")
    return value


def _string(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReadinessInputError("malformed_input")
    return value


def _decimal(value: object) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise ReadinessInputError("malformed_input")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ReadinessInputError("malformed_input") from None
    if not result.is_finite():
        raise ReadinessInputError("nonfinite_value")
    return result


def _date(value: object) -> date:
    if not isinstance(value, str):
        raise ReadinessInputError("malformed_input")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ReadinessInputError("malformed_input") from None


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise ReadinessInputError("malformed_input")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ReadinessInputError("malformed_input") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ReadinessInputError("malformed_input")
    return parsed.astimezone(UTC)


def _sha256(value: object) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ReadinessInputError("malformed_input")
    return value


def _reject_extra(mapping: Mapping[str, object], allowed: frozenset[str]) -> None:
    if any(key not in allowed for key in mapping):
        raise ReadinessInputError("unsupported_schema")


def _optional_hash(mapping: Mapping[str, object], key: str) -> None:
    if key in mapping and mapping[key] is not None:
        _sha256(mapping[key])


def _optional_string(mapping: Mapping[str, object], key: str) -> None:
    if key in mapping and mapping[key] is not None:
        if not isinstance(mapping[key], str):
            raise ReadinessInputError("malformed_input")


def _bool(value: object) -> bool:
    if not isinstance(value, bool):
        raise ReadinessInputError("malformed_input")
    return value


def _integer(value: object) -> int:
    if isinstance(value, bool):
        raise ReadinessInputError("malformed_input")
    if isinstance(value, Decimal):
        if value != value.to_integral_value():
            raise ReadinessInputError("malformed_input")
        return int(value)
    if isinstance(value, int):
        return value
    raise ReadinessInputError("malformed_input")


def _validate_source_names(value: object) -> None:
    if value is None:
        return
    for item in _list(value):
        if not isinstance(item, str) or item not in _SOURCE_NAMES:
            raise ReadinessInputError("malformed_input")


def _validate_provenance(value: object) -> None:
    if value is None:
        return
    provenance = _mapping(value)
    _reject_extra(provenance, _PROVENANCE_FIELDS)
    for key in ("universe_sources", "bar_sources", "fx_sources", "artifact_sources"):
        if key in provenance:
            _validate_source_names(provenance[key])
    _optional_string(provenance, "normalization_version")
    if "captured_at" in provenance and provenance["captured_at"] is not None:
        _timestamp(provenance["captured_at"])


def _validate_account(value: object) -> None:
    if value is None:
        return
    account = _mapping(value)
    _reject_extra(account, _ACCOUNT_FIELDS)
    if account.get("account_scope") != "market_specific_independent_simulated":
        raise ReadinessInputError("malformed_input")
    if account.get("reporting_currency") != "KRW":
        raise ReadinessInputError("malformed_input")
    if account.get("native_currency") != "USD":
        raise ReadinessInputError("malformed_input")
    if account.get("initial_cash_conversion") != "initial_krw_to_usd":
        raise ReadinessInputError("malformed_input")
    if _decimal(_required(account, "initial_cash_krw")) <= 0:
        raise ReadinessInputError("nonpositive_initial_capital")
    if "fx_krw_per_usd" in account and account["fx_krw_per_usd"] is not None:
        if _decimal(account["fx_krw_per_usd"]) <= 0:
            raise ReadinessInputError("malformed_input")


def _validate_capabilities(readiness: Mapping[str, object]) -> None:
    capabilities = _list(_required(readiness, "capabilities"))
    if len(capabilities) != len(_CAPABILITY_NAMES):
        raise ReadinessInputError("malformed_input")
    seen: set[str] = set()
    statuses: list[str] = []
    for item in capabilities:
        capability = _mapping(item)
        _reject_extra(capability, _CAPABILITY_FIELDS)
        name = _string(_required(capability, "name"))
        if name not in _CAPABILITY_NAMES or name in seen:
            raise ReadinessInputError("malformed_input")
        seen.add(name)
        status = _string(_required(capability, "status"))
        if status not in _CAPABILITY_STATUSES:
            raise ReadinessInputError("malformed_input")
        statuses.append(status)
        _string(_required(capability, "detail"))
        for missing_range in _list(_required(capability, "missing_ranges")):
            _string(missing_range)
    if seen != _CAPABILITY_NAMES or _bool(_required(readiness, "ready")) != all(
        status == "ready" for status in statuses
    ):
        raise ReadinessInputError("malformed_input")


def _validate_equity_shape(result: Mapping[str, object]) -> None:
    for row in _list(_required(result, "equity")):
        item = _mapping(row)
        _reject_extra(item, _EQUITY_FIELDS)
        _date(_required(item, "session"))
        for key in (
            "cash_krw",
            "cash_native",
            "invested_krw",
            "nav_krw",
            "fx_krw_per_usd",
            "drawdown_pct",
        ):
            value = _decimal(_required(item, key))
            if key == "fx_krw_per_usd" and value <= 0:
                raise ReadinessInputError("malformed_input")
            if key != "fx_krw_per_usd" and value < 0:
                raise ReadinessInputError("malformed_input")


def _validate_candidate_shape(result: Mapping[str, object]) -> None:
    for row in _list(_required(result, "candidate_evidence")):
        item = _mapping(row)
        _reject_extra(item, _CANDIDATE_FIELDS)
        _date(_required(item, "session"))
        _string(_required(item, "symbol"))
        rank = _integer(_required(item, "rank"))
        if rank < 1 or rank > 20:
            raise ReadinessInputError("malformed_input")
        if _decimal(_required(item, "volume")) < 0:
            raise ReadinessInputError("malformed_input")
        _bool(_required(item, "eligible"))
        for key in ("membership_available_at", "bar_available_at"):
            if key in item and item[key] is not None:
                _timestamp(item[key])


def _validate_trade_shape(result: Mapping[str, object]) -> None:
    for row in _list(_required(result, "trades")):
        item = _mapping(row)
        _reject_extra(item, _TRADE_FIELDS)
        for key in ("session", "signal_session", "fill_session"):
            _date(_required(item, key))
        _string(_required(item, "symbol"))
        if _required(item, "side") not in {"buy", "sell"}:
            raise ReadinessInputError("malformed_input")
        quantity = _integer(_required(item, "quantity"))
        if quantity <= 0 or _required(item, "currency") != "USD":
            raise ReadinessInputError("malformed_input")
        for key in ("market_open", "fill_price", "notional"):
            if _decimal(_required(item, key)) <= 0:
                raise ReadinessInputError("malformed_input")
        for key in ("fee", "tax"):
            if _decimal(_required(item, key)) < 0:
                raise ReadinessInputError("malformed_input")
        _string(_required(item, "rationale"))


def _validate_result_facts(
    payload: Mapping[str, object], result: Mapping[str, object]
) -> None:
    _optional_hash(payload, "input_hash")
    _optional_hash(payload, "data_contract_hash")
    _bool(_required(payload, "final_promotable"))
    if not isinstance(_required(payload, "final_promotability_reason"), str):
        raise ReadinessInputError("malformed_input")
    _optional_string(payload, "error")
    _optional_string(payload, "pilot_run_id")
    _optional_hash(result, "input_hash")
    _optional_hash(result, "policy_hash")
    _optional_hash(result, "data_contract_hash")
    _optional_hash(result, "pool_contract_hash")
    for key in ("candidate_evidence", "trades", "warmup_sessions"):
        for item in _list(_required(result, key)):
            if key == "warmup_sessions":
                _date(item)
            else:
                _mapping(item)
    for item in _list(_required(result, "limitations")):
        _string(item)
    for key, value in _mapping(_required(result, "metrics")).items():
        _string(key)
        _decimal(value)
    _optional_string(result, "pilot_run_id")
    _validate_provenance(result.get("provenance"))
    _validate_account(result.get("account"))
    _validate_candidate_shape(result)
    _validate_trade_shape(result)


def _validate_strict_model(payload: Mapping[str, object]) -> None:
    try:
        MarketResearchRun.model_validate(payload)
    except (TypeError, ValueError):
        raise ReadinessInputError("malformed_input") from None


def _read_source(path: Path, expected_sha256: str) -> tuple[dict[str, object], str]:
    expected = _sha256(expected_sha256)
    try:
        with path.open("rb") as source:
            raw = source.read(MAX_SOURCE_BYTES + 1)
    except OSError:
        raise ReadinessInputError("source_unavailable") from None
    if len(raw) > MAX_SOURCE_BYTES:
        raise ReadinessInputError("source_too_large")
    actual = hashlib.sha256(raw).hexdigest()
    if actual != expected:
        raise ReadinessInputError("source_sha_mismatch")
    return _parse_json(raw), actual


def _canonical_digest(value: object) -> str:
    try:
        raw = json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    except (TypeError, ValueError):
        raise ReadinessInputError("malformed_input") from None
    return hashlib.sha256(raw).hexdigest()


def _read_evidence(path: Path) -> tuple[dict[str, object], str]:
    try:
        with path.open("rb") as source:
            raw = source.read(MAX_EVIDENCE_BYTES + 1)
    except OSError:
        raise ReadinessInputError("evidence_unavailable") from None
    if len(raw) > MAX_EVIDENCE_BYTES:
        raise ReadinessInputError("evidence_too_large")
    actual = hashlib.sha256(raw).hexdigest()
    if actual != CANONICAL_EVIDENCE_SHA256:
        raise ReadinessInputError("evidence_sha_mismatch")
    try:
        evidence = _parse_json(raw)
    except ReadinessInputError:
        raise ReadinessInputError("evidence_malformed") from None
    return evidence, actual


def _read_manifest(
    path: Path,
    run_path: Path,
    expected_run_sha256: str,
    expected_period: tuple[str, str],
) -> str:
    try:
        raw = path.read_bytes()
    except OSError:
        raise ReadinessInputError("manifest_unavailable") from None
    actual = hashlib.sha256(raw).hexdigest()
    if actual != CANONICAL_MANIFEST_SHA256:
        raise ReadinessInputError("manifest_sha_mismatch")
    try:
        manifest = _parse_json(raw)
    except ReadinessInputError:
        raise ReadinessInputError("manifest_malformed") from None
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, Mapping):
        raise ReadinessInputError("manifest_chain_mismatch")
    run_artifact = artifacts.get("run")
    if not isinstance(run_artifact, Mapping):
        raise ReadinessInputError("manifest_chain_mismatch")
    linked_path = run_artifact.get("path")
    if not isinstance(linked_path, str) or Path(linked_path).resolve() != (
        run_path.resolve()
    ):
        raise ReadinessInputError("manifest_run_path_mismatch")
    if run_artifact.get("sha256") != expected_run_sha256:
        raise ReadinessInputError("manifest_run_sha_mismatch")
    run_fact = manifest.get("run")
    if not isinstance(run_fact, Mapping):
        raise ReadinessInputError("manifest_chain_mismatch")
    period = run_fact.get("period")
    request = run_fact.get("request")
    if period != {"start": expected_period[0], "end": expected_period[1]}:
        raise ReadinessInputError("manifest_period_mismatch")
    if not isinstance(request, Mapping):
        raise ReadinessInputError("manifest_request_mismatch")
    if (
        request.get("start_date") != expected_period[0]
        or request.get("end_date") != expected_period[1]
    ):
        raise ReadinessInputError("manifest_request_mismatch")
    return actual


def _read_tracked_calendar(path: Path | None = None) -> dict[str, object]:
    calendar_path = path or TRACKED_CALENDAR_PATH
    try:
        raw = calendar_path.read_bytes()
    except OSError:
        raise ReadinessInputError("calendar_unavailable") from None
    if hashlib.sha256(raw).hexdigest() != CALENDAR_BYTES_SHA256:
        raise ReadinessInputError("calendar_sha_mismatch")
    try:
        payload = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError):
        raise ReadinessInputError("calendar_malformed") from None
    if not isinstance(payload, dict):
        raise ReadinessInputError("calendar_malformed")
    if (
        payload.get("provider") != "exchange_calendars"
        or payload.get("provider_version") != "4.12"
    ):
        raise ReadinessInputError("calendar_metadata_mismatch")
    calendars = payload.get("calendars")
    if not isinstance(calendars, dict) or set(calendars) != {"XKRX", "XNYS"}:
        raise ReadinessInputError("calendar_malformed")
    payload_hash = hashlib.sha256(
        json.dumps(
            calendars, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()
    if payload.get("calendars_sha256") != CALENDAR_PAYLOAD_SHA256:
        raise ReadinessInputError("calendar_payload_hash_mismatch")
    if payload_hash != CALENDAR_PAYLOAD_SHA256:
        raise ReadinessInputError("calendar_payload_hash_mismatch")
    return payload


def _validate_session_evidence(
    evidence_path: Path,
    run_path: Path,
    payload: Mapping[str, object],
    request: Mapping[str, object],
    result: Mapping[str, object],
    source_sha256: str,
    manifest_path: Path | None = None,
    calendar_path: Path | None = None,
) -> dict[str, object]:
    evidence, evidence_sha256 = _read_evidence(evidence_path)
    expected_top = {
        "schema",
        "manifest",
        "run_sha256",
        "calendar",
        "request",
        "sessions",
        "limitations",
    }
    if set(evidence) != expected_top or evidence.get("schema") != EVIDENCE_SCHEMA:
        raise ReadinessInputError("evidence_schema_mismatch")
    manifest_identity = evidence.get("manifest")
    if not isinstance(manifest_identity, Mapping):
        raise ReadinessInputError("evidence_schema_mismatch")
    if set(manifest_identity) != {
        "path",
        "sha256",
        "run_path",
        "run_sha256",
        "request_period",
    }:
        raise ReadinessInputError("evidence_schema_mismatch")
    manifest_relative_path = manifest_identity.get("path")
    if (
        not isinstance(manifest_relative_path, str)
        or Path(manifest_relative_path).is_absolute()
    ):
        raise ReadinessInputError("evidence_manifest_mismatch")
    if evidence.get("run_sha256") != source_sha256:
        raise ReadinessInputError("evidence_run_mismatch")
    if manifest_identity.get("sha256") != CANONICAL_MANIFEST_SHA256:
        raise ReadinessInputError("evidence_manifest_mismatch")
    if manifest_identity.get("run_sha256") != source_sha256:
        raise ReadinessInputError("evidence_manifest_run_mismatch")
    if manifest_identity.get("run_path") != (
        "20260915-market-data-live-contract-fixes/us-web-pilot-run.json"
    ):
        raise ReadinessInputError("evidence_manifest_mismatch")
    if manifest_identity.get("request_period") != {
        "start_date": "2025-09-11",
        "end_date": "2026-09-11",
    }:
        raise ReadinessInputError("evidence_manifest_mismatch")
    resolved_manifest_path = manifest_path or (
        CANONICAL_AUDIT_ROOT / manifest_relative_path
    )
    manifest_sha256 = _read_manifest(
        resolved_manifest_path,
        run_path,
        source_sha256,
        ("2025-09-11", "2026-09-11"),
    )
    calendar = evidence.get("calendar")
    if not isinstance(calendar, Mapping):
        raise ReadinessInputError("evidence_schema_mismatch")
    if set(calendar) != {
        "path",
        "bytes_sha256",
        "payload_sha256",
        "provider",
        "provider_version",
        "calendar",
        "market",
        "timezone",
    }:
        raise ReadinessInputError("evidence_schema_mismatch")
    if calendar != {
        "path": "backend/jusik/data/market_sessions_2023_2026.json",
        "bytes_sha256": CALENDAR_BYTES_SHA256,
        "payload_sha256": CALENDAR_PAYLOAD_SHA256,
        "provider": "exchange_calendars",
        "provider_version": "4.12",
        "calendar": "XNYS",
        "market": "US",
        "timezone": "America/New_York",
    }:
        raise ReadinessInputError("evidence_calendar_mismatch")
    evidence_request = evidence.get("request")
    if evidence_request != {
        "start_date": "2025-09-11",
        "end_date": "2026-09-11",
        "inclusive": True,
        "date_semantics": (
            "XNYS local session dates in America/New_York; not UTC timestamps"
        ),
    }:
        raise ReadinessInputError("evidence_request_mismatch")
    if request.get("market") != "US" or request.get("start_date") != "2025-09-11":
        raise ReadinessInputError("evidence_request_mismatch")
    if request.get("end_date") != "2026-09-11":
        raise ReadinessInputError("evidence_request_mismatch")
    limitations = evidence.get("limitations")
    if (
        not isinstance(limitations, list)
        or not limitations
        or not all(isinstance(item, str) and item for item in limitations)
    ):
        raise ReadinessInputError("evidence_schema_mismatch")

    calendar_payload = _read_tracked_calendar(calendar_path)
    calendars = calendar_payload["calendars"]
    if not isinstance(calendars, Mapping) or not isinstance(calendars["XNYS"], list):
        raise ReadinessInputError("calendar_malformed")
    expected_sessions: list[str] = []
    unavailable: list[str] = []
    for row in calendars["XNYS"]:
        if not isinstance(row, Mapping):
            raise ReadinessInputError("calendar_malformed")
        value = row.get("date")
        state = row.get("state")
        if not isinstance(value, str) or not isinstance(state, str):
            raise ReadinessInputError("calendar_malformed")
        try:
            local_date = date.fromisoformat(value)
        except ValueError:
            raise ReadinessInputError("calendar_malformed") from None
        if date(2025, 9, 11) <= local_date <= date(2026, 9, 11):
            if state == "session":
                expected_sessions.append(value)
            elif state == "unavailable":
                unavailable.append(value)
            elif state != "closed":
                raise ReadinessInputError("calendar_malformed")
    observed_sessions = [
        _string(_required(_mapping(row), "session"))
        for row in _list(_required(result, "equity"))
    ]
    try:
        observed_dates = [date.fromisoformat(value) for value in observed_sessions]
    except ValueError:
        raise ReadinessInputError("evidence_run_mismatch") from None
    duplicates = sorted(
        {value for value in observed_sessions if observed_sessions.count(value) > 1}
    )
    missing = sorted(set(expected_sessions) - set(observed_sessions))
    extra = sorted(set(observed_sessions) - set(expected_sessions))
    sessions = evidence.get("sessions")
    if not isinstance(sessions, Mapping):
        raise ReadinessInputError("evidence_schema_mismatch")
    if set(sessions) != {
        "digest_encoding",
        "expected",
        "observed",
        "missing",
        "extra",
        "duplicates",
        "unavailable",
    }:
        raise ReadinessInputError("evidence_schema_mismatch")
    if sessions.get("digest_encoding") != (
        "UTF-8 JSON array of ISO-8601 dates with sorted keys and compact separators"
    ):
        raise ReadinessInputError("evidence_schema_mismatch")
    for name, values in (
        ("expected", expected_sessions),
        ("observed", observed_sessions),
    ):
        item = sessions.get(name)
        if not isinstance(item, Mapping) or set(item) != {
            "count",
            "sha256",
            "first",
            "last",
        }:
            raise ReadinessInputError("evidence_schema_mismatch")
        if (
            item.get("count") != len(values)
            or item.get("sha256") != _canonical_digest(values)
            or item.get("first") != (values[0] if values else None)
            or item.get("last") != (values[-1] if values else None)
        ):
            raise ReadinessInputError("session_evidence_mismatch")
    if (
        sessions.get("missing") != missing
        or sessions.get("extra") != extra
        or sessions.get("duplicates") != duplicates
        or sessions.get("unavailable") != unavailable
        or observed_dates != [date.fromisoformat(value) for value in expected_sessions]
    ):
        raise ReadinessInputError("session_evidence_mismatch")
    return {
        "sha256": evidence_sha256,
        "manifest_sha256": manifest_sha256,
        "run_sha256": source_sha256,
        "calendar_bytes_sha256": CALENDAR_BYTES_SHA256,
        "calendar_payload_sha256": CALENDAR_PAYLOAD_SHA256,
        "expected_count": len(expected_sessions),
        "observed_count": len(observed_sessions),
        "expected_sessions": expected_sessions,
        "observed_sessions": observed_sessions,
        "missing": missing,
        "extra": extra,
        "duplicates": duplicates,
        "unavailable": unavailable,
    }


def _validate_run(
    payload: Mapping[str, object],
) -> tuple[Mapping[str, object], Mapping[str, object], Mapping[str, object]]:
    _reject_extra(payload, _TOP_FIELDS)
    schema = payload.get("schema")
    if schema is not None and schema not in _ALLOWED_INPUT_SCHEMAS:
        raise ReadinessInputError("unsupported_schema")
    for key in (
        "id",
        "status",
        "request",
        "result",
        "input_hash",
        "created_at",
        "updated_at",
        "error",
        "stage",
        "pilot_run_id",
        "data_contract_hash",
        "final_promotable",
        "final_promotability_reason",
    ):
        _required(payload, key)
    request = _mapping(_required(payload, "request"))
    result = _mapping(_required(payload, "result"))
    _reject_extra(request, _REQUEST_FIELDS)
    _reject_extra(result, _RESULT_FIELDS)
    for key in (
        "market",
        "start_date",
        "end_date",
        "stage",
        "pilot_run_id",
        "initial_cash_krw",
        "fee_rate",
        "slippage_rate",
        "sell_tax_rate",
        "research_grade",
    ):
        _required(request, key)
    for key in (
        "market",
        "request",
        "readiness",
        "status",
        "completeness",
        "equity",
        "stage",
        "pilot_run_id",
        "research_grade",
    ):
        _required(result, key)
    result_request = _mapping(_required(result, "request"))
    if dict(result_request) != dict(request):
        raise ReadinessInputError("request_result_mismatch")
    readiness = _mapping(_required(result, "readiness"))
    _reject_extra(readiness, _READINESS_FIELDS)
    for key in (
        "market",
        "checked_at",
        "capabilities",
        "ready",
        "simulated",
        "research_grade",
    ):
        _required(readiness, key)
    _validate_capabilities(readiness)
    _timestamp(_required(payload, "created_at"))
    _timestamp(_required(payload, "updated_at"))
    _timestamp(_required(readiness, "checked_at"))
    _validate_result_facts(payload, result)
    _validate_equity_shape(result)
    _validate_strict_model(payload)
    return request, result, readiness


def _validate_canonical_values(
    payload: Mapping[str, object],
    request: Mapping[str, object],
    result: Mapping[str, object],
    readiness: Mapping[str, object],
) -> None:
    if payload.get("status") != "completed" or payload.get("stage") != "pilot":
        raise ReadinessInputError("unsupported_run")
    if request.get("market") != "US" or request.get("stage") != "pilot":
        raise ReadinessInputError("unsupported_run")
    if result.get("market") != "US" or result.get("stage") != "pilot":
        raise ReadinessInputError("unsupported_run")
    if result.get("status") != "approximate":
        raise ReadinessInputError("unsupported_run")
    if result.get("completeness") != "approximate":
        raise ReadinessInputError("unsupported_run")
    if (
        request.get("research_grade") != "approximate"
        or result.get("research_grade") != "approximate"
        or readiness.get("research_grade") != "approximate"
    ):
        raise ReadinessInputError("unsupported_run")
    if readiness.get("market") != "US":
        raise ReadinessInputError("unsupported_run")
    if not isinstance(readiness.get("simulated"), bool):
        raise ReadinessInputError("malformed_input")
    initial_cash = _decimal(_required(request, "initial_cash_krw"))
    if initial_cash <= 0:
        raise ReadinessInputError("nonpositive_initial_capital")
    for key in ("fee_rate", "slippage_rate", "sell_tax_rate"):
        rate = _decimal(_required(request, key))
        if rate < 0 or rate > 1:
            raise ReadinessInputError("malformed_input")
    start = _date(_required(request, "start_date"))
    end = _date(_required(request, "end_date"))
    if end < start:
        raise ReadinessInputError("malformed_input")
    equity = _list(_required(result, "equity"))
    if len(equity) > MAX_NAV_POINTS:
        raise ReadinessInputError("too_many_nav_points")
    previous: date | None = None
    for row in equity:
        item = _mapping(row)
        session = _date(_required(item, "session"))
        nav = _decimal(_required(item, "nav_krw"))
        if nav <= 0:
            raise ReadinessInputError("nonpositive_nav")
        if session < start or session > end:
            raise ReadinessInputError("session_out_of_period")
        if previous is not None:
            if session == previous:
                raise ReadinessInputError("duplicate_session")
            if session < previous:
                raise ReadinessInputError("reverse_session_order")
        previous = session


def _source_facts(
    payload: Mapping[str, object],
    request: Mapping[str, object],
    result: Mapping[str, object],
    readiness: Mapping[str, object],
    source_sha256: str,
) -> dict[str, object]:
    provenance = result.get("provenance")
    return {
        "sha256": source_sha256,
        "run_id": _string(_required(payload, "id")),
        "market": "US",
        "stage": "pilot",
        "research_grade": "approximate",
        "simulated": readiness.get("simulated"),
        "source": provenance,
        "input_hash": result.get("input_hash"),
        "data_contract_hash": result.get("data_contract_hash"),
        "pool_contract_hash": result.get("pool_contract_hash"),
        "policy_hash": result.get("policy_hash"),
        "request_period": {
            "start_date": request.get("start_date"),
            "end_date": request.get("end_date"),
        },
    }


def diagnose_run(
    path: Path,
    expected_sha256: str,
    *,
    canonical: bool = False,
    evidence_path: Path | None = None,
    manifest_path: Path | None = None,
    calendar_path: Path | None = None,
) -> dict[str, object]:
    """Inspect a saved run using its caller-provided identity hash.

    The default report is generic and cannot claim that the registered
    artifact was accepted.  Use :func:`diagnose_canonical_run` for that gate.
    """

    if canonical and expected_sha256 != CANONICAL_RUN_SHA256:
        raise ReadinessInputError("canonical_sha_required")
    if evidence_path is not None and not canonical:
        raise ReadinessInputError("canonical_evidence_requires_canonical")

    payload, source_sha256 = _read_source(path, expected_sha256)
    request, result, readiness = _validate_run(payload)
    _validate_canonical_values(payload, request, result, readiness)
    evidence: dict[str, object] | None = None
    calculation_policy: dict[str, object] | None = None
    if canonical and evidence_path is not None:
        evidence = _validate_session_evidence(
            evidence_path,
            path,
            payload,
            request,
            result,
            source_sha256,
            manifest_path,
            calendar_path,
        )
        try:
            calculation_policy = policy_facts(load_calculation_policy())
        except PolicyValidationError as exc:
            raise ReadinessInputError(exc.code) from None
    missing = list(MISSING_CODES)
    if evidence is not None:
        missing = [
            code
            for code in missing
            if code
            not in {
                "missing_calendar_evidence",
                "missing_session_completeness_evidence",
                "missing_calculation_policy",
            }
        ]
    return {
        "schema": SCHEMA,
        "target": TARGET_SCHEMA,
        "status": "blocked",
        "ready_for_metrics": False,
        "economic_evaluation": "not-evaluated",
        "canonical": canonical,
        "missing": missing,
        "source": _source_facts(payload, request, result, readiness, source_sha256),
        **({"session_evidence": evidence} if evidence is not None else {}),
        **(
            {"calculation_policy": calculation_policy}
            if calculation_policy is not None
            else {}
        ),
        "cost_assumptions": {
            "fee_rate": str(_decimal(_required(request, "fee_rate"))),
            "slippage_rate": str(_decimal(_required(request, "slippage_rate"))),
            "sell_tax_rate": str(_decimal(_required(request, "sell_tax_rate"))),
            "pointer": "request",
            "pointers": {
                "fee_rate": "request.fee_rate",
                "slippage_rate": "request.slippage_rate",
                "sell_tax_rate": "request.sell_tax_rate",
            },
            "nav_cost_inclusion": "unproven",
        },
    }


def diagnose_canonical_run(
    path: Path,
    evidence_path: Path = CANONICAL_EVIDENCE_PATH,
    manifest_path: Path | None = None,
    calendar_path: Path | None = None,
) -> dict[str, object]:
    """Accept only the registered frozen run identity as canonical input."""

    return diagnose_run(
        path,
        CANONICAL_RUN_SHA256,
        canonical=True,
        evidence_path=evidence_path,
        manifest_path=manifest_path,
        calendar_path=calendar_path,
    )


def _json_default(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"unsupported output value: {type(value).__name__}")


def render_report(report: Mapping[str, object]) -> str:
    return json.dumps(
        report,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    )


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--run", type=Path, required=True)
    command.add_argument("--expected-sha256", required=True)
    command.add_argument(
        "--canonical",
        action="store_true",
        help="require the registered canonical artifact SHA-256",
    )
    command.add_argument(
        "--canonical-evidence",
        type=Path,
        help="verify the registered canonical session evidence JSON",
    )
    return command


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.canonical:
            report = diagnose_canonical_run(
                args.run, args.canonical_evidence or CANONICAL_EVIDENCE_PATH
            )
        else:
            report = diagnose_run(
                args.run,
                args.expected_sha256,
                evidence_path=args.canonical_evidence,
            )
    except ReadinessInputError as exc:
        print(render_report({"error": {"code": exc.code}}))
        return 2
    print(render_report(report))
    return 0


load_market_research_run = diagnose_run

__all__ = [
    "MAX_NAV_POINTS",
    "MAX_SOURCE_BYTES",
    "MISSING_CODES",
    "SCHEMA",
    "TARGET_SCHEMA",
    "EVIDENCE_SCHEMA",
    "ReadinessInputError",
    "CANONICAL_MANIFEST_SHA256",
    "CANONICAL_RUN_SHA256",
    "CANONICAL_EVIDENCE_SHA256",
    "CANONICAL_EVIDENCE_PATH",
    "CALENDAR_BYTES_SHA256",
    "CALENDAR_PAYLOAD_SHA256",
    "diagnose_run",
    "diagnose_canonical_run",
    "load_market_research_run",
    "main",
    "render_report",
]


if __name__ == "__main__":
    sys.exit(main())
