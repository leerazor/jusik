"""Fail-closed loader for the versioned market-performance policy artifact."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Final

POLICY_SCHEMA: Final = "market-performance-calculation-policy/v1"
POLICY_ID: Final = "market-performance-calculation-policy-v1"
POLICY_PATH: Final = (
    Path(__file__).with_name("data") / "market_performance_calculation_policy_v1.json"
)
EVALUATOR_PATH: Final = Path(__file__).with_name("market_performance_metrics.py")
MAX_POLICY_BYTES: Final = 64 * 1024

# This is deliberately pinned after the artifact is finalized.  It is not
# recomputed from disk, so replacing the artifact cannot silently change the
# policy consumed by a caller.
POLICY_SHA256: Final = (
    "87385ecb15bdc9d0425b9cfcf97c46174e2e8d9e6de970780654aab81e5bd4a9"
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class PolicyValidationError(ValueError):
    """Stable, non-sensitive error raised for policy integrity failures."""

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


def _reject_float(value: str) -> object:
    raise ValueError(value)


def _reject_constant(value: str) -> object:
    raise ValueError(value)


def _parse_policy(body: bytes) -> dict[str, object]:
    try:
        parsed = json.loads(
            body.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError):
        raise PolicyValidationError("policy_malformed") from None
    if not isinstance(parsed, dict):
        raise PolicyValidationError("policy_malformed")
    return parsed


def _require_keys(value: Mapping[str, object], expected: frozenset[str]) -> None:
    if set(value) != expected:
        raise PolicyValidationError("policy_unsupported_schema")


def _string(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise PolicyValidationError("policy_malformed")
    return value


def _sha(value: object) -> str:
    result = _string(value)
    if _SHA256.fullmatch(result) is None:
        raise PolicyValidationError("policy_malformed")
    return result


def _bool(value: object) -> bool:
    if not isinstance(value, bool):
        raise PolicyValidationError("policy_malformed")
    return value


def _int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise PolicyValidationError("policy_malformed")
    return value


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise PolicyValidationError("policy_malformed")
    return tuple(value)


def _validate_policy(policy: dict[str, object]) -> None:
    _require_keys(
        policy,
        frozenset(
            {
                "schema",
                "id",
                "scope",
                "contracts",
                "implementation",
                "parameters",
                "rules",
                "availability",
                "semantics",
            }
        ),
    )
    if policy["schema"] != POLICY_SCHEMA or policy["id"] != POLICY_ID:
        raise PolicyValidationError("policy_unsupported_schema")

    scope = policy["scope"]
    if not isinstance(scope, Mapping):
        raise PolicyValidationError("policy_malformed")
    _require_keys(scope, frozenset({"application", "historical_application_proven"}))
    if scope["application"] != "forward-only" or _bool(
        scope["historical_application_proven"]
    ):
        raise PolicyValidationError("policy_scope_invalid")

    contracts = policy["contracts"]
    if not isinstance(contracts, Mapping):
        raise PolicyValidationError("policy_malformed")
    _require_keys(
        contracts,
        frozenset(
            {
                "costs_included_in_nav",
                "data_grade_preserved",
                "economic_promotion",
                "historical_recalculation",
            }
        ),
    )
    for key in contracts:
        _bool(contracts[key])
    if (
        contracts["costs_included_in_nav"] is not True
        or contracts["data_grade_preserved"] is not True
    ):
        raise PolicyValidationError("policy_contract_invalid")
    if (
        contracts["economic_promotion"] is not False
        or contracts["historical_recalculation"] is not False
    ):
        raise PolicyValidationError("policy_contract_invalid")

    implementation = policy["implementation"]
    if not isinstance(implementation, Mapping):
        raise PolicyValidationError("policy_malformed")
    _require_keys(
        implementation,
        frozenset({"evaluator_module", "evaluator_source_sha256", "decimal_context"}),
    )
    if (
        _string(implementation["evaluator_module"])
        != "jusik.market_performance_metrics"
    ):
        raise PolicyValidationError("policy_implementation_invalid")
    evaluator_sha = _sha(implementation["evaluator_source_sha256"])
    context = implementation["decimal_context"]
    if not isinstance(context, Mapping):
        raise PolicyValidationError("policy_malformed")
    _require_keys(
        context,
        frozenset(
            {"prec", "rounding", "Emin", "Emax", "capitals", "clamp", "flags", "traps"}
        ),
    )
    if _int(context["prec"]) != 50 or context["rounding"] != "ROUND_HALF_EVEN":
        raise PolicyValidationError("policy_context_invalid")
    if _int(context["Emin"]) != -999999 or _int(context["Emax"]) != 999999:
        raise PolicyValidationError("policy_context_invalid")
    if _int(context["capitals"]) != 1 or _int(context["clamp"]) != 0:
        raise PolicyValidationError("policy_context_invalid")
    if _strings(context["flags"]) != () or _strings(context["traps"]) != (
        "InvalidOperation",
        "DivisionByZero",
        "Overflow",
    ):
        raise PolicyValidationError("policy_context_invalid")
    if evaluator_sha == "0" * 64:
        raise PolicyValidationError("policy_malformed")

    parameters = policy["parameters"]
    if not isinstance(parameters, Mapping):
        raise PolicyValidationError("policy_malformed")
    _require_keys(
        parameters, frozenset({"days_per_year", "sessions_per_year", "mdd_hard_limit"})
    )
    if (
        _int(parameters["days_per_year"]) != 365
        or _int(parameters["sessions_per_year"]) != 252
    ):
        raise PolicyValidationError("policy_parameters_invalid")
    if parameters["mdd_hard_limit"] != "0.20":
        raise PolicyValidationError("policy_parameters_invalid")

    for name in ("rules", "availability", "semantics"):
        value = policy[name]
        if not isinstance(value, Mapping) or not value:
            raise PolicyValidationError("policy_malformed")
        if any(
            not isinstance(key, str) or not isinstance(item, str) or not item
            for key, item in value.items()
        ):
            raise PolicyValidationError("policy_malformed")


def canonical_policy_bytes(policy: Mapping[str, object]) -> bytes:
    """Serialize a validated policy using its one canonical byte encoding."""

    return (
        json.dumps(
            policy, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        + b"\n"
    )


def load_calculation_policy() -> dict[str, object]:
    """Load and verify the only policy artifact accepted by this package."""

    try:
        body = POLICY_PATH.read_bytes()
    except OSError:
        raise PolicyValidationError("policy_unavailable") from None
    if len(body) > MAX_POLICY_BYTES:
        raise PolicyValidationError("policy_too_large")
    if hashlib.sha256(body).hexdigest() != POLICY_SHA256:
        raise PolicyValidationError("policy_sha_mismatch")
    policy = _parse_policy(body)
    _validate_policy(policy)
    if canonical_policy_bytes(policy) != body:
        raise PolicyValidationError("policy_noncanonical")
    implementation = policy["implementation"]
    assert isinstance(implementation, Mapping)
    try:
        evaluator_body = EVALUATOR_PATH.read_bytes()
    except OSError:
        raise PolicyValidationError("evaluator_unavailable") from None
    actual_evaluator_sha = hashlib.sha256(evaluator_body).hexdigest()
    if actual_evaluator_sha != implementation["evaluator_source_sha256"]:
        raise PolicyValidationError("evaluator_source_sha_mismatch")
    return policy


load_policy = load_calculation_policy


def policy_facts(policy: Mapping[str, object]) -> dict[str, object]:
    implementation = policy["implementation"]
    scope = policy["scope"]
    assert isinstance(implementation, Mapping)
    assert isinstance(scope, Mapping)
    return {
        "id": policy["id"],
        "artifact_sha256": POLICY_SHA256,
        "evaluator_source_sha256": implementation["evaluator_source_sha256"],
        "scope": scope["application"],
        "historical_application_proven": scope["historical_application_proven"],
    }


__all__ = [
    "EVALUATOR_PATH",
    "MAX_POLICY_BYTES",
    "POLICY_ID",
    "POLICY_PATH",
    "POLICY_SCHEMA",
    "POLICY_SHA256",
    "PolicyValidationError",
    "canonical_policy_bytes",
    "load_calculation_policy",
    "load_policy",
    "policy_facts",
]
