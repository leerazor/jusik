"""Fail-closed validation for the tracked investment-roadmap mandate."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MANDATE_JSON = Path("docs/research-mandate.json")
MANDATE_MARKDOWN = Path("docs/research-mandate.md")
MANDATE_HASHES = Path("docs/market-research-mandate.sha256")
ROADMAP_MARKDOWN = Path("docs/investment-development-roadmap.md")
LEGACY_MANDATE_JSON_SHA256 = (
    "f097fde7874063314e21f8be884b19d2e8cea3e1272c47e5991300c546548a7d"
)
LEGACY_EXECUTION_HASH_KEY = "docs/research-mandate.json#legacy-execution-identity"
GOVERNANCE_PROJECTION_HASH_KEY = "docs/research-mandate.json#governance-object"

GOVERNANCE_SCHEMA_VERSION = 1
GOVERNANCE_POLICY_VERSION = "investment-roadmap-governance-v1"
SUPPORTED_SCHEMA_VERSION = GOVERNANCE_SCHEMA_VERSION
SUPPORTED_POLICY_VERSION = GOVERNANCE_POLICY_VERSION
ROADMAP_POLICY_VERSION = GOVERNANCE_POLICY_VERSION
PRIMARY_METRICS = ("CAGR", "MDD", "Sharpe", "Calmar")
DIAGNOSTIC_METRICS = (
    "net_return",
    "trade_count",
    "turnover",
    "transaction_cost",
    "fx_cost",
    "coverage",
    "missing_data",
    "stress",
)
MAX_PREREGISTERED_CANDIDATES = 3
MAXIMUM_DRAWDOWN_FRACTION = "0.20"
PAPER_CONTRACT = "unchanged;10% drawdown"
PREREGISTRATION_BUDGET = (
    "bounded compute, data, and artifact budgets fixed before execution"
)
PREREGISTRATION_PERIOD = (
    "bounded IS, separate validation, chronological walk-forward, and one "
    "untouched OOS period fixed before execution"
)
PREREGISTRATION_REQUIRED_RETURN = (
    "candidate-specific required return fixed before execution; failure blocks "
    "stress and PAPER"
)

_HASH_LINE_RE = re.compile(r"^(?P<path>\S+)\s+(?P<digest>[0-9a-f]{64})$")
_MANDATE_MARKER_RE = re.compile(
    r"research-mandate\.json.*?SHA-256은\s+`?(?P<digest>[0-9a-f]{64})"
)
_ROADMAP_POLICY_RE = re.compile(
    r"^\s*-\s+canonical\s+policy_version:\s+`?(?P<version>[A-Za-z0-9._-]+)`?\s*$",
    re.MULTILINE,
)


class MandateGovernanceError(ValueError):
    """A tracked governance document cannot safely authorize dispatch."""


@dataclass(frozen=True)
class ValidatedMandate:
    """Validated mandate metadata without exposing document contents."""

    digest: str
    schema_version: int
    policy_version: str
    dispatch_enabled: bool


def _invalid() -> MandateGovernanceError:
    return MandateGovernanceError("investment roadmap governance is invalid")


def _read_regular_file(repo: Path, relative: Path) -> bytes:
    """Read one tracked file through no-follow directory and file descriptors."""
    parts = relative.parts
    if relative.is_absolute() or not parts or ".." in parts:
        raise _invalid()
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
    directory_flags = flags | os.O_DIRECTORY
    directory_fd: int | None = None
    file_fd: int | None = None
    try:
        directory_fd = os.open(repo, directory_flags)
        for component in parts[:-1]:
            next_fd = os.open(component, directory_flags, dir_fd=directory_fd)
            os.close(directory_fd)
            directory_fd = next_fd
        file_fd = os.open(parts[-1], flags, dir_fd=directory_fd)
        if not stat.S_ISREG(os.fstat(file_fd).st_mode):
            raise _invalid()
        chunks: list[bytes] = []
        while True:
            chunk = os.read(file_fd, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks)
    except (OSError, ValueError) as exc:
        if isinstance(exc, MandateGovernanceError):
            raise
        raise _invalid() from exc
    finally:
        if file_fd is not None:
            os.close(file_fd)
        if directory_fd is not None:
            os.close(directory_fd)


def _strict_object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _invalid()
        result[key] = value
    return result


def _json_object(raw: bytes) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_strict_object_pairs)
    except (UnicodeError, json.JSONDecodeError, MandateGovernanceError) as exc:
        raise _invalid() from exc
    if not isinstance(value, dict):
        raise _invalid()
    return value


def _legacy_execution_projection(raw: bytes) -> bytes:
    """Project the exact frozen document before the additive governance member."""
    marker = b',\n  "governance":'
    start = raw.find(marker)
    if start < 0 or start != raw.rfind(marker):
        raise _invalid()
    projection = raw[:start] + b"\n}\n"
    projected = _json_object(projection)
    if "governance" in projected:
        raise _invalid()
    return projection


def _governance_projection(governance: Mapping[str, Any]) -> bytes:
    return json.dumps(
        governance,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _strict_bool(value: Any) -> bool:
    if type(value) is not bool:
        raise _invalid()
    return value


def _strict_int(value: Any) -> int:
    if type(value) is not int:
        raise _invalid()
    return value


def _strict_string(value: Any) -> str:
    if type(value) is not str:
        raise _invalid()
    return value


def _validate_governance(value: Any) -> ValidatedMandate:
    if not isinstance(value, dict):
        raise _invalid()
    schema_version = _strict_int(value.get("schema_version"))
    policy_version = _strict_string(value.get("policy_version"))
    if schema_version != GOVERNANCE_SCHEMA_VERSION:
        raise _invalid()
    if policy_version != GOVERNANCE_POLICY_VERSION:
        raise _invalid()
    dispatch_enabled = _strict_bool(value.get("dispatch_enabled"))

    objective = value.get("objective")
    if not isinstance(objective, dict):
        raise _invalid()
    if objective.get("kind") != "balanced":
        raise _invalid()
    if objective.get("cost_adjusted") is not True:
        raise _invalid()
    if objective.get("primary_metrics") != list(PRIMARY_METRICS):
        raise _invalid()
    diagnostics = objective.get("diagnostic_metrics")
    if diagnostics != list(DIAGNOSTIC_METRICS):
        raise _invalid()
    hard_filters = objective.get("hard_filters")
    if (
        not isinstance(hard_filters, dict)
        or hard_filters.get("MDD") != MAXIMUM_DRAWDOWN_FRACTION
    ):
        raise _invalid()

    candidates = value.get("candidate_policy")
    if not isinstance(candidates, dict):
        raise _invalid()
    if (
        _strict_int(candidates.get("max_preregistered_candidates"))
        != MAX_PREREGISTERED_CANDIDATES
    ):
        raise _invalid()
    for key in ("weighted_aggregate", "automatic_winner", "automatic_promotion"):
        if _strict_bool(candidates.get(key)) is not False:
            raise _invalid()
    if _strict_bool(candidates.get("retune_same_holdout")) is not False:
        raise _invalid()

    data_policy = value.get("data_policy")
    if not isinstance(data_policy, dict):
        raise _invalid()
    if (
        _strict_bool(data_policy.get("free_cache_audit_before_bounded_gaps"))
        is not True
    ):
        raise _invalid()

    sequence = value.get("validation_sequence")
    if sequence != [
        "bounded_is",
        "separate_validation",
        "chronological_walk_forward",
        "one_time_untouched_oos_go_no_go",
        "stress",
        "isolated_simulation",
        "paper_review",
        "separate_live_approval",
    ]:
        raise _invalid()

    preregistration = value.get("preregistration")
    if not isinstance(preregistration, dict):
        raise _invalid()
    if preregistration != {
        "budget": PREREGISTRATION_BUDGET,
        "period": PREREGISTRATION_PERIOD,
        "required_return": PREREGISTRATION_REQUIRED_RETURN,
    }:
        raise _invalid()
    promotion = value.get("promotion")
    if not isinstance(promotion, dict):
        raise _invalid()
    if promotion.get("paper_contract") != PAPER_CONTRACT:
        raise _invalid()
    if promotion.get("live_approval") != "separate_explicit_approval":
        raise _invalid()
    return ValidatedMandate("", schema_version, policy_version, dispatch_enabled)


def _manifest(repo: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    try:
        lines = _read_regular_file(repo, MANDATE_HASHES).decode("utf-8").splitlines()
    except UnicodeError as exc:
        raise _invalid() from exc
    for line in lines:
        if not line:
            continue
        match = _HASH_LINE_RE.fullmatch(line)
        if match is None or match.group("path") in entries:
            raise _invalid()
        entries[match.group("path")] = match.group("digest")
    if not entries:
        raise _invalid()
    return entries


def _document_digest(repo: Path, relative: Path, entries: Mapping[str, str]) -> None:
    key = relative.as_posix()
    expected = entries.get(key)
    if expected is None:
        raise _invalid()
    if hashlib.sha256(_read_regular_file(repo, relative)).hexdigest() != expected:
        raise _invalid()


def validate_mandate(repo: Path) -> ValidatedMandate:
    """Validate all tracked governance inputs and return only safe metadata."""
    raw = _read_regular_file(repo, MANDATE_JSON)
    mandate = _json_object(raw)
    governance = _validate_governance(mandate.get("governance"))

    entries = _manifest(repo)
    full_digest = hashlib.sha256(raw).hexdigest()
    if entries.get(MANDATE_JSON.as_posix()) != full_digest:
        raise _invalid()
    legacy_digest = hashlib.sha256(_legacy_execution_projection(raw)).hexdigest()
    if (
        entries.get(LEGACY_EXECUTION_HASH_KEY) != legacy_digest
        or legacy_digest != LEGACY_MANDATE_JSON_SHA256
    ):
        raise _invalid()
    governance_digest = hashlib.sha256(
        _governance_projection(mandate["governance"])
    ).hexdigest()
    if entries.get(GOVERNANCE_PROJECTION_HASH_KEY) != governance_digest:
        raise _invalid()

    try:
        markdown = _read_regular_file(repo, MANDATE_MARKDOWN).decode("utf-8")
    except UnicodeError as exc:
        raise _invalid() from exc
    markers = _MANDATE_MARKER_RE.findall(markdown)
    if len(markers) != 1 or markers[0] != full_digest:
        raise _invalid()
    _document_digest(repo, MANDATE_MARKDOWN, entries)
    _document_digest(repo, Path("docs/market-research.md"), entries)

    try:
        roadmap = _read_regular_file(repo, ROADMAP_MARKDOWN).decode("utf-8")
    except UnicodeError as exc:
        raise _invalid() from exc
    policy_markers = _ROADMAP_POLICY_RE.findall(roadmap)
    if len(policy_markers) != 1 or policy_markers[0] != governance.policy_version:
        raise _invalid()
    return ValidatedMandate(
        full_digest,
        governance.schema_version,
        governance.policy_version,
        governance.dispatch_enabled,
    )


def validate_dispatch_gate(repo: Path) -> ValidatedMandate:
    """Validate governance and require explicit roadmap dispatch enablement."""
    result = validate_mandate(repo)
    if not result.dispatch_enabled:
        raise MandateGovernanceError("investment roadmap governance is disabled")
    return result


# Descriptive aliases keep the validator easy to discover for callers and tests.
load_validated_mandate = validate_mandate
require_dispatch_enabled = validate_dispatch_gate
