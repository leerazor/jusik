"""Bind the registered run, session evidence, NAV residuals, and cost ledger.

This is intentionally a no-input adapter.  It is the only reconciliation
entry point allowed to turn the registered calendar and independent modeled
accounting evidence into canonical coverage facts; the generic reconciliation
module keeps its unavailable semantics.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Final

from .market_performance_cost_evidence import (
    CANONICAL_CACHE_DIR,
    CANONICAL_DATASET_PATH,
    CANONICAL_DATASET_SHA256,
    CANONICAL_EVIDENCE_PATH,
    CANONICAL_MANIFEST_PATH,
    CANONICAL_MANIFEST_SHA256,
    CANONICAL_RUN_PATH,
    CostEvidenceError,
    verify_canonical_cost_evidence,
)
from .market_performance_readiness import (
    CALENDAR_BYTES_SHA256,
    CALENDAR_PAYLOAD_SHA256,
    CANONICAL_EVIDENCE_SHA256,
    CANONICAL_PERIOD,
    CANONICAL_RUN_SHA256,
    CANONICAL_SESSION_COUNT,
    EVIDENCE_SCHEMA,
    MAX_SOURCE_BYTES,
    ReadinessInputError,
    verify_canonical_session_evidence,
)
from .research_nav_reconciliation import (
    MAX_INPUT_BYTES,
    ReconciliationError,
    ReconciliationReport,
    reconcile_json_bytes,
)

SCHEMA: Final = "r2-canonical-nav-evidence-connection/v1"
EXPECTED_TRADE_COUNT: Final = 106
MAX_COST_MANIFEST_BYTES: Final = 1 * 1024 * 1024
MAX_COST_DATASET_BYTES: Final = 10 * 1024 * 1024
MAX_COST_EVIDENCE_BYTES: Final = 1 * 1024 * 1024
MAX_COST_CACHE_MANIFEST_BYTES: Final = 2 * 1024 * 1024
MAX_COST_CACHE_RAW_BYTES: Final = 2 * 1024 * 1024
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class CanonicalNavError(ValueError):
    """Stable fail-closed adapter error."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _digest(value: object) -> str:
    try:
        raw = json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    except (TypeError, ValueError):
        raise CanonicalNavError("digest_input_invalid") from None
    return hashlib.sha256(raw).hexdigest()


def _read_canonical_run() -> tuple[bytes, str]:
    if CANONICAL_RUN_PATH.is_symlink():
        raise CanonicalNavError("unsafe_path")
    try:
        with CANONICAL_RUN_PATH.open("rb") as source:
            raw = source.read(min(MAX_INPUT_BYTES, MAX_SOURCE_BYTES) + 1)
    except OSError:
        raise CanonicalNavError("source_unavailable") from None
    if len(raw) > min(MAX_INPUT_BYTES, MAX_SOURCE_BYTES):
        raise CanonicalNavError("source_too_large")
    actual = hashlib.sha256(raw).hexdigest()
    if actual != CANONICAL_RUN_SHA256:
        raise CanonicalNavError("source_sha_mismatch")
    return raw, actual


def _bounded_artifact(path: object, limit: int, too_large_code: str) -> bytes:
    if not isinstance(path, Path):
        raise CanonicalNavError("artifact_path_invalid")
    try:
        with path.open("rb") as source:
            raw = source.read(limit + 1)
    except OSError:
        raise CanonicalNavError("artifact_unavailable") from None
    if len(raw) > limit:
        raise CanonicalNavError(too_large_code)
    return raw


def _bound_cost_chain() -> None:
    """Bound every file the legacy cost verifier can reach before its call."""

    _bounded_artifact(
        CANONICAL_MANIFEST_PATH,
        MAX_COST_MANIFEST_BYTES,
        "manifest_too_large",
    )
    _bounded_artifact(
        CANONICAL_DATASET_PATH,
        MAX_COST_DATASET_BYTES,
        "dataset_too_large",
    )
    _bounded_artifact(
        CANONICAL_EVIDENCE_PATH,
        MAX_COST_EVIDENCE_BYTES,
        "evidence_too_large",
    )
    _bounded_artifact(
        CANONICAL_CACHE_DIR / "manifest.json",
        MAX_COST_CACHE_MANIFEST_BYTES,
        "cache_manifest_too_large",
    )
    _bounded_artifact(
        CANONICAL_CACHE_DIR / "completed.json",
        MAX_COST_CACHE_MANIFEST_BYTES,
        "cache_completion_too_large",
    )
    try:
        raw_paths = list((CANONICAL_CACHE_DIR / "raw").glob("*.bin"))
    except OSError:
        raise CanonicalNavError("cache_raw_unavailable") from None
    if len(raw_paths) > 84:
        raise CanonicalNavError("cache_raw_count_mismatch")
    for path in raw_paths:
        _bounded_artifact(path, MAX_COST_CACHE_RAW_BYTES, "cache_raw_too_large")


def _mapping(value: object, code: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise CanonicalNavError(code)
    return value


def _require_sha(value: object, expected: str, code: str) -> str:
    if value != expected:
        raise CanonicalNavError(code)
    return expected


def _require_digest(value: object, code: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise CanonicalNavError(code)
    return value


def _bind_facts(
    report: ReconciliationReport,
    source_sha256: str,
    session_facts: Mapping[str, object],
    cost_facts: Mapping[str, object],
) -> dict[str, object]:
    """Fail closed when independently verified facts do not identify one run."""

    _require_sha(source_sha256, CANONICAL_RUN_SHA256, "run_identity_mismatch")
    _require_sha(
        session_facts.get("run_sha256"),
        CANONICAL_RUN_SHA256,
        "run_identity_mismatch",
    )
    _require_sha(
        session_facts.get("manifest_sha256"),
        CANONICAL_MANIFEST_SHA256,
        "manifest_identity_mismatch",
    )
    _require_sha(
        session_facts.get("evidence_sha256"),
        CANONICAL_EVIDENCE_SHA256,
        "evidence_identity_mismatch",
    )
    if session_facts.get("schema") != EVIDENCE_SCHEMA:
        raise CanonicalNavError("evidence_schema_mismatch")
    _require_sha(
        session_facts.get("calendar_bytes_sha256"),
        CALENDAR_BYTES_SHA256,
        "calendar_identity_mismatch",
    )
    _require_sha(
        session_facts.get("calendar_payload_sha256"),
        CALENDAR_PAYLOAD_SHA256,
        "calendar_identity_mismatch",
    )
    if session_facts.get("period") != {
        "start_date": CANONICAL_PERIOD[0],
        "end_date": CANONICAL_PERIOD[1],
    }:
        raise CanonicalNavError("period_mismatch")

    observed = session_facts.get("observed_sessions")
    expected = session_facts.get("expected_sessions")
    if (
        not isinstance(observed, list)
        or not isinstance(expected, list)
        or len(observed) != CANONICAL_SESSION_COUNT
        or observed != expected
        or session_facts.get("observed_count") != CANONICAL_SESSION_COUNT
        or session_facts.get("expected_count") != CANONICAL_SESSION_COUNT
    ):
        raise CanonicalNavError("session_identity_mismatch")
    if list(observed) != [row.session.isoformat() for row in report.rows]:
        raise CanonicalNavError("reconciliation_session_mismatch")
    if report.ordered is not True or len(report.rows) != CANONICAL_SESSION_COUNT:
        raise CanonicalNavError("reconciliation_coverage_mismatch")

    if cost_facts.get("status") != "verified":
        raise CanonicalNavError("cost_evidence_unverified")
    if cost_facts.get("trade_count") != EXPECTED_TRADE_COUNT:
        raise CanonicalNavError("trade_count_mismatch")
    if cost_facts.get("session_count") != CANONICAL_SESSION_COUNT:
        raise CanonicalNavError("cost_session_count_mismatch")
    artifacts = _mapping(cost_facts.get("artifacts"), "cost_artifacts_missing")
    _require_sha(artifacts.get("run"), CANONICAL_RUN_SHA256, "cost_run_mismatch")
    _require_sha(
        artifacts.get("manifest"), CANONICAL_MANIFEST_SHA256, "cost_manifest_mismatch"
    )
    _require_sha(
        artifacts.get("dataset"), CANONICAL_DATASET_SHA256, "dataset_identity_mismatch"
    )
    accounting_digest = cost_facts.get("accounting_digest")
    accounting_digest = _require_digest(accounting_digest, "accounting_digest_missing")

    residual = report.residual_artifact(source_sha256=source_sha256)
    projection_digest = _digest(
        {
            "source_run_sha256": source_sha256,
            "sessions": list(observed),
            "residuals": residual["residuals"],
        }
    )
    return {
        "schema": SCHEMA,
        "status": report.status,
        "residual": residual,
        "canonical": {
            "coverage": {
                "calendar": {
                    "availability": "verified",
                    "source": "canonical_session_evidence",
                    "session_count": CANONICAL_SESSION_COUNT,
                    "period": {
                        "start_date": CANONICAL_PERIOD[0],
                        "end_date": CANONICAL_PERIOD[1],
                    },
                },
                "independent_modeled_accounting": {
                    "availability": "verified",
                    "source": "canonical_cost_evidence",
                    "trade_count": EXPECTED_TRADE_COUNT,
                    "session_count": CANONICAL_SESSION_COUNT,
                },
                "nav": {
                    "availability": "verified",
                    "source": "residual.residuals",
                    "currency": "KRW",
                    "session_count": CANONICAL_SESSION_COUNT,
                },
            },
            "provenance": {
                "run_sha256": source_sha256,
                "manifest_sha256": session_facts["manifest_sha256"],
                "dataset_sha256": CANONICAL_DATASET_SHA256,
                "session_evidence_sha256": session_facts["evidence_sha256"],
                "calendar_bytes_sha256": session_facts["calendar_bytes_sha256"],
                "calendar_payload_sha256": session_facts["calendar_payload_sha256"],
                "period": {
                    "start_date": CANONICAL_PERIOD[0],
                    "end_date": CANONICAL_PERIOD[1],
                },
                "sessions": list(observed),
            },
        },
        "projection": {
            "source": "residual.residuals",
            "digest": projection_digest,
            "session_count": CANONICAL_SESSION_COUNT,
        },
        "accounting": {
            "source": "canonical_cost_evidence",
            "digest": accounting_digest,
            "trade_count": EXPECTED_TRADE_COUNT,
            "session_count": CANONICAL_SESSION_COUNT,
        },
    }


def reconcile_canonical_nav() -> dict[str, object]:
    """Read and bind the fixed canonical run without caller-provided inputs."""

    raw, source_sha256 = _read_canonical_run()
    try:
        report = reconcile_json_bytes(raw, expected_sha256=source_sha256)
    except ReconciliationError as exc:
        raise CanonicalNavError("reconciliation_invalid") from exc
    try:
        session_facts = verify_canonical_session_evidence()
    except ReadinessInputError as exc:
        raise CanonicalNavError(exc.code) from None
    _bound_cost_chain()
    try:
        cost_facts = verify_canonical_cost_evidence()
    except CostEvidenceError as exc:
        raise CanonicalNavError(exc.code) from None
    return _bind_facts(report, source_sha256, session_facts, cost_facts)


def render_report(report: Mapping[str, object]) -> str:
    return json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(description=__doc__)


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    del args
    try:
        report = reconcile_canonical_nav()
    except CanonicalNavError as exc:
        print(render_report({"error": {"code": exc.code}}))
        return 2
    print(render_report(report))
    return 0 if report["status"] == "passed" else 1


__all__ = [
    "CANONICAL_RUN_PATH",
    "CanonicalNavError",
    "SCHEMA",
    "main",
    "parser",
    "reconcile_canonical_nav",
    "render_report",
]


if __name__ == "__main__":
    sys.exit(main())
