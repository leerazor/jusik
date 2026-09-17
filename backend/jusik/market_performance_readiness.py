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

SCHEMA: Final = "market-performance-readiness/v1"
TARGET_SCHEMA: Final = "market-performance-metrics-input/v1"
CANONICAL_RUN_SHA256: Final = (
    "cc9150f8b77a27ffd6b001449c0475933ff744a37011801923f87cbdc5558275"
)
MAX_SOURCE_BYTES: Final = 10 * 1024 * 1024
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
    path: Path, expected_sha256: str, *, canonical: bool = False
) -> dict[str, object]:
    """Inspect a saved run using its caller-provided identity hash.

    The default report is generic and cannot claim that the registered
    artifact was accepted.  Use :func:`diagnose_canonical_run` for that gate.
    """

    if canonical and expected_sha256 != CANONICAL_RUN_SHA256:
        raise ReadinessInputError("canonical_sha_required")

    payload, source_sha256 = _read_source(path, expected_sha256)
    request, result, readiness = _validate_run(payload)
    _validate_canonical_values(payload, request, result, readiness)
    return {
        "schema": SCHEMA,
        "target": TARGET_SCHEMA,
        "status": "blocked",
        "ready_for_metrics": False,
        "economic_evaluation": "not-evaluated",
        "canonical": canonical,
        "missing": list(MISSING_CODES),
        "source": _source_facts(payload, request, result, readiness, source_sha256),
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


def diagnose_canonical_run(path: Path) -> dict[str, object]:
    """Accept only the registered frozen run identity as canonical input."""

    return diagnose_run(path, CANONICAL_RUN_SHA256, canonical=True)


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
    return command


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        report = diagnose_run(args.run, args.expected_sha256, canonical=args.canonical)
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
    "ReadinessInputError",
    "CANONICAL_RUN_SHA256",
    "diagnose_run",
    "diagnose_canonical_run",
    "load_market_research_run",
    "main",
    "render_report",
]


if __name__ == "__main__":
    sys.exit(main())
