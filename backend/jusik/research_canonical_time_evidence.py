"""Build and verify a read-only time-evidence sidecar for the frozen R0 run.

The sidecar deliberately does not rewrite the historical run.  Its timestamps
are derived from the tracked XNYS calendar and are therefore calendar-derived
execution anchors, not an assertion about an observed broker event.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections.abc import Mapping
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Final, cast

from .market_performance_readiness import (
    CALENDAR_BYTES_SHA256,
    CANONICAL_MANIFEST_SHA256,
    CANONICAL_PERIOD,
    CANONICAL_RUN_SHA256,
    TRACKED_CALENDAR_PATH,
)
from .research_market_calendar import MarketCalendar

SCHEMA: Final = "r0-canonical-time-evidence-sidecar/v1"
MAX_SOURCE_BYTES: Final = 25 * 1024 * 1024
SHA256 = re.compile(r"^[0-9a-f]{64}$")
AUDIT_ROOT = Path.home() / ".local" / "share" / "jusik" / "portfolio-audit"
DEFAULT_CANONICAL_RUN = (
    AUDIT_ROOT / "20260915-market-data-live-contract-fixes" / "us-web-pilot-run.json"
)
DEFAULT_CANONICAL_MANIFEST = (
    AUDIT_ROOT
    / "20260915-r0-baseline"
    / "r0-baseline-freeze"
    / "baseline-manifest.json"
)
DEFAULT_CANDIDATE = (
    AUDIT_ROOT
    / "canonical-time-evidence-candidate-20260920"
    / "candidate-run-with-time-evidence.json"
)
DEFAULT_REPLAY = (
    AUDIT_ROOT / "canonical-time-evidence-candidate-20260920" / "replay.json"
)
DEFAULT_TIME_EVIDENCE = (
    AUDIT_ROOT
    / "canonical-time-evidence-candidate-20260920"
    / "time-evidence-result.json"
)
DEFAULT_OUTPUT = (
    AUDIT_ROOT
    / "canonical-time-evidence-candidate-20260920"
    / "canonical-time-evidence-sidecar.json"
)
DEFAULT_ATTACHMENT_MANIFEST = (
    AUDIT_ROOT
    / "canonical-time-evidence-candidate-20260920"
    / "attachment-manifest.json"
)
ATTACHMENT_MANIFEST_SHA256: Final = (
    "59ba9f4c719681286bb487555336194a08bdbe35c7054d021227ea4387f69fe8"
)


class CanonicalTimeEvidenceError(ValueError):
    """Stable fail-closed error for invalid or mismatched evidence."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _read(path: Path, label: str) -> tuple[bytes, str]:
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise CanonicalTimeEvidenceError(f"{label}_unsafe_path")
    try:
        size = path.stat().st_size
        if size > MAX_SOURCE_BYTES:
            raise CanonicalTimeEvidenceError(f"{label}_too_large")
        body = path.read_bytes()
    except OSError as exc:
        raise CanonicalTimeEvidenceError(f"{label}_unavailable") from exc
    if len(body) != size:
        raise CanonicalTimeEvidenceError(f"{label}_changed_while_reading")
    return body, hashlib.sha256(body).hexdigest()


def _json(body: bytes, label: str) -> dict[str, object]:
    try:
        value = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CanonicalTimeEvidenceError(f"{label}_invalid_json") from exc
    if not isinstance(value, dict):
        raise CanonicalTimeEvidenceError(f"{label}_invalid_root")
    return cast(dict[str, object], value)


def _mapping(value: object, code: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise CanonicalTimeEvidenceError(code)
    return value


def _digest(value: object, code: str) -> str:
    if not isinstance(value, str) or SHA256.fullmatch(value) is None:
        raise CanonicalTimeEvidenceError(code)
    return value


def _identity(
    result: Mapping[str, object], top: Mapping[str, object]
) -> dict[str, object]:
    request = _mapping(
        result.get("request", top.get("request")), "identity_request_invalid"
    )
    period = {
        "start_date": request.get("start_date"),
        "end_date": request.get("end_date"),
    }
    return {
        "market": result.get("market", request.get("market", top.get("market"))),
        "period": period,
        "stage": result.get("stage", top.get("stage")),
        "research_grade": result.get(
            "research_grade", request.get("research_grade", top.get("research_grade"))
        ),
        "pilot_run_id": result.get("pilot_run_id", top.get("pilot_run_id")),
        "data_contract_hash": result.get(
            "data_contract_hash", top.get("data_contract_hash")
        ),
        "policy_hash": result.get("policy_hash"),
        "pool_contract_hash": result.get("pool_contract_hash"),
        "warmup_sessions": result.get("warmup_sessions", []),
    }


def _equity(value: object, label: str) -> list[dict[str, object]]:
    if not isinstance(value, list) or not value:
        raise CanonicalTimeEvidenceError(f"{label}_missing")
    rows: list[dict[str, object]] = []
    previous_session: str | None = None
    previous_at: datetime | None = None
    for raw in value:
        row = _mapping(raw, f"{label}_row_invalid")
        session = row.get("session")
        nav = row.get("nav_krw")
        at = row.get("evaluation_at")
        if (
            not isinstance(session, str)
            or not isinstance(nav, str)
            or not isinstance(at, str)
        ):
            raise CanonicalTimeEvidenceError(f"{label}_timestamp_missing")
        try:
            date.fromisoformat(session)
        except ValueError as exc:
            raise CanonicalTimeEvidenceError(f"{label}_session_invalid") from exc
        try:
            parsed = datetime.fromisoformat(at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise CanonicalTimeEvidenceError(f"{label}_timestamp_invalid") from exc
        if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
            raise CanonicalTimeEvidenceError(f"{label}_timestamp_not_utc")
        if previous_session is not None and session <= previous_session:
            raise CanonicalTimeEvidenceError(f"{label}_session_order_invalid")
        if previous_at is not None and parsed <= previous_at:
            raise CanonicalTimeEvidenceError(f"{label}_timestamp_order_invalid")
        previous_session, previous_at = session, parsed
        rows.append({"session": session, "nav_krw": nav, "evaluation_at": at})
    return rows


def _canonical_rows(value: object, label: str) -> list[tuple[str, str]]:
    if not isinstance(value, list) or not value:
        raise CanonicalTimeEvidenceError(f"{label}_missing")
    rows: list[tuple[str, str]] = []
    previous: str | None = None
    for raw in value:
        row = _mapping(raw, f"{label}_row_invalid")
        session, nav = row.get("session"), row.get("nav_krw")
        if not isinstance(session, str) or not isinstance(nav, str):
            raise CanonicalTimeEvidenceError(f"{label}_row_invalid")
        if previous is not None and session <= previous:
            raise CanonicalTimeEvidenceError(f"{label}_session_order_invalid")
        previous = session
        rows.append((session, nav))
    return rows


def _assert_identity(*identities: Mapping[str, object]) -> dict[str, object]:
    first = dict(identities[0])
    for other in identities[1:]:
        if dict(other) != first:
            raise CanonicalTimeEvidenceError("identity_mismatch")
    if first.get("market") != "US" or first.get("period") != {
        "start_date": CANONICAL_PERIOD[0],
        "end_date": CANONICAL_PERIOD[1],
    }:
        raise CanonicalTimeEvidenceError("period_or_market_mismatch")
    if first.get("stage") != "pilot" or first.get("research_grade") != "approximate":
        raise CanonicalTimeEvidenceError("stage_or_grade_mismatch")
    return first


def _build(
    canonical_run_path: Path,
    canonical_manifest_path: Path,
    candidate_run_path: Path,
    replay_path: Path,
    time_evidence_path: Path,
    calendar_path: Path,
    attachment_manifest_path: Path,
    output_path: Path,
) -> dict[str, object]:
    paths = {
        "canonical_run": canonical_run_path,
        "canonical_manifest": canonical_manifest_path,
        "candidate_run": candidate_run_path,
        "replay": replay_path,
        "time_evidence": time_evidence_path,
        "calendar": calendar_path,
        "attachment_manifest": attachment_manifest_path,
    }
    raw: dict[str, bytes] = {}
    hashes: dict[str, str] = {}
    for label, path in paths.items():
        raw[label], hashes[label] = _read(path, label)
    if canonical_run_path.resolve() != DEFAULT_CANONICAL_RUN.resolve():
        raise CanonicalTimeEvidenceError("canonical_run_path_not_pinned")
    if canonical_manifest_path.resolve() != DEFAULT_CANONICAL_MANIFEST.resolve():
        raise CanonicalTimeEvidenceError("canonical_manifest_path_not_pinned")
    if hashes["canonical_run"] != CANONICAL_RUN_SHA256:
        raise CanonicalTimeEvidenceError("canonical_run_sha_mismatch")
    if hashes["canonical_manifest"] != CANONICAL_MANIFEST_SHA256:
        raise CanonicalTimeEvidenceError("canonical_manifest_sha_mismatch")
    if calendar_path.resolve() != TRACKED_CALENDAR_PATH.resolve():
        raise CanonicalTimeEvidenceError("calendar_path_not_tracked")
    if hashes["calendar"] != CALENDAR_BYTES_SHA256:
        raise CanonicalTimeEvidenceError("calendar_sha_mismatch")
    if hashes["attachment_manifest"] != ATTACHMENT_MANIFEST_SHA256:
        raise CanonicalTimeEvidenceError("attachment_manifest_sha_mismatch")
    manifest = _json(raw["canonical_manifest"], "canonical_manifest")
    artifacts = _mapping(manifest.get("artifacts"), "manifest_artifacts_invalid")
    run_artifact = _mapping(artifacts.get("run"), "manifest_run_invalid")
    if (
        run_artifact.get("sha256") != CANONICAL_RUN_SHA256
        or Path(str(run_artifact.get("path", ""))).resolve()
        != canonical_run_path.resolve()
    ):
        raise CanonicalTimeEvidenceError("manifest_run_identity_mismatch")
    # Validate every frozen manifest edge, not just the run we project.  This
    # prevents a valid run from being paired with a changed dataset/cache.
    for name, raw_artifact in artifacts.items():
        artifact = _mapping(raw_artifact, "manifest_artifact_invalid")
        artifact_path = Path(str(artifact.get("path", "")))
        expected = _digest(artifact.get("sha256"), "manifest_artifact_hash_invalid")
        _, actual = _read(artifact_path, f"manifest_{name}")
        if actual != expected:
            raise CanonicalTimeEvidenceError("manifest_artifact_sha_mismatch")
    canonical = _json(raw["canonical_run"], "canonical_run")
    candidate = _json(raw["candidate_run"], "candidate_run")
    replay = _json(raw["replay"], "replay")
    evidence = _json(raw["time_evidence"], "time_evidence")
    attachment = _json(raw["attachment_manifest"], "attachment_manifest")
    if attachment.get("schema") != "market-time-evidence-attachment/v1":
        raise CanonicalTimeEvidenceError("attachment_manifest_schema_invalid")
    expected_attachment = {
        "canonical_run_sha256": hashes["canonical_run"],
        "candidate_run_sha256": hashes["candidate_run"],
        "replay_sha256": hashes["replay"],
        "time_evidence_result_sha256": hashes["time_evidence"],
    }
    for key, expected in expected_attachment.items():
        if attachment.get(key) != expected:
            raise CanonicalTimeEvidenceError("attachment_manifest_identity_mismatch")
    comparison = _mapping(replay.get("comparison"), "replay_comparison_missing")
    if comparison.get("all") is not True:
        raise CanonicalTimeEvidenceError("replay_not_exact")
    candidate_result = _mapping(candidate.get("result"), "candidate_result_invalid")
    replay_result = _mapping(replay.get("result"), "replay_result_invalid")
    evidence_identity = _identity(evidence, evidence)
    identity = _assert_identity(
        _identity(
            _mapping(canonical.get("result"), "canonical_result_invalid"), canonical
        ),
        _identity(candidate_result, candidate),
        _identity(replay_result, replay),
        evidence_identity,
    )
    canonical_rows = _canonical_rows(
        _mapping(canonical.get("result"), "canonical_result_invalid").get("equity"),
        "canonical_equity",
    )
    candidate_rows = _canonical_rows(candidate_result.get("equity"), "candidate_equity")
    replay_rows = _canonical_rows(replay_result.get("equity"), "replay_equity")
    if candidate_rows != canonical_rows or replay_rows != canonical_rows:
        raise CanonicalTimeEvidenceError("replay_equity_mismatch")
    evidence_rows = _equity(evidence.get("equity"), "time_evidence_equity")
    if [(r["session"], r["nav_krw"]) for r in evidence_rows] != canonical_rows:
        raise CanonicalTimeEvidenceError("canonical_equity_mismatch")
    calendar = MarketCalendar.from_bytes(raw["calendar"])
    if not calendar.available or calendar.artifact_sha256 != hashes["calendar"]:
        raise CanonicalTimeEvidenceError("calendar_invalid")
    for row in evidence_rows:
        try:
            session_date = date.fromisoformat(cast(str, row["session"]))
        except ValueError as exc:
            raise CanonicalTimeEvidenceError("time_evidence_session_invalid") from exc
        lookup = calendar.lookup("NMS", session_date)
        if (
            lookup.state != "session"
            or lookup.session is None
            or lookup.session.close_at.astimezone(UTC)
            .isoformat()
            .replace("+00:00", "Z")
            != row["evaluation_at"]
        ):
            raise CanonicalTimeEvidenceError("calendar_timestamp_mismatch")
    initial = evidence.get("initial_capital_at")
    try:
        first_date = date.fromisoformat(cast(str, evidence_rows[0]["session"]))
    except ValueError as exc:
        raise CanonicalTimeEvidenceError("time_evidence_session_invalid") from exc
    first_lookup = calendar.lookup("NMS", first_date)
    expected_initial = (
        first_lookup.session.open_at.astimezone(UTC).isoformat().replace("+00:00", "Z")
        if first_lookup.session
        else None
    )
    if initial != expected_initial:
        raise CanonicalTimeEvidenceError("initial_anchor_mismatch")
    return {
        "schema": SCHEMA,
        "status": "verified",
        "built_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "identity": identity,
        "sources": {
            label: {"path": str(path), "sha256": hashes[label]}
            for label, path in paths.items()
        },
        "time_evidence": {"initial_capital_at": initial, "equity": evidence_rows},
        "limitations": [
            "calendar_derived_timestamps",
            "initial_open_is_engine_ordering_anchor",
            "not_historical_observation_or_pit_proof",
        ],
    }


def build_canonical_time_evidence(
    canonical_run_path: Path = DEFAULT_CANONICAL_RUN,
    canonical_manifest_path: Path = DEFAULT_CANONICAL_MANIFEST,
    candidate_run_path: Path = DEFAULT_CANDIDATE,
    replay_path: Path = DEFAULT_REPLAY,
    time_evidence_path: Path = DEFAULT_TIME_EVIDENCE,
    calendar_path: Path = TRACKED_CALENDAR_PATH,
    output_path: Path = DEFAULT_OUTPUT,
    attachment_manifest_path: Path = DEFAULT_ATTACHMENT_MANIFEST,
) -> dict[str, object]:
    """Validate inputs, then atomically write a new sidecar."""
    result = _build(
        *(
            Path(p)
            for p in (
                canonical_run_path,
                canonical_manifest_path,
                candidate_run_path,
                replay_path,
                time_evidence_path,
                calendar_path,
                attachment_manifest_path,
                output_path,
            )
        )
    )
    output_path = Path(output_path)
    if output_path.is_symlink() or not output_path.is_absolute():
        raise CanonicalTimeEvidenceError("output_unsafe_path")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()
    fd, tmp = tempfile.mkstemp(prefix=f".{output_path.name}.", dir=output_path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, output_path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return result


def verify_canonical_time_evidence(
    sidecar_path: Path = DEFAULT_OUTPUT,
) -> dict[str, object]:
    """Rehash every source and re-run all semantic checks without writing."""
    body, _ = _read(Path(sidecar_path), "sidecar")
    sidecar = _json(body, "sidecar")
    if sidecar.get("schema") != SCHEMA or sidecar.get("status") != "verified":
        raise CanonicalTimeEvidenceError("sidecar_schema_invalid")
    sources = _mapping(sidecar.get("sources"), "sidecar_sources_invalid")
    required = {
        "canonical_run",
        "canonical_manifest",
        "candidate_run",
        "replay",
        "time_evidence",
        "calendar",
        "attachment_manifest",
    }
    if set(sources) != required:
        raise CanonicalTimeEvidenceError("sidecar_sources_incomplete")
    source_paths: dict[str, Path] = {}
    for label in required:
        source = _mapping(sources.get(label), "sidecar_source_invalid")
        path = Path(str(source.get("path", "")))
        expected = _digest(source.get("sha256"), "sidecar_source_hash_invalid")
        _, actual = _read(path, label)
        if actual != expected:
            raise CanonicalTimeEvidenceError("sidecar_source_sha_mismatch")
        source_paths[label] = path
    result = _build(
        source_paths["canonical_run"],
        source_paths["canonical_manifest"],
        source_paths["candidate_run"],
        source_paths["replay"],
        source_paths["time_evidence"],
        source_paths["calendar"],
        source_paths["attachment_manifest"],
        Path("/tmp/canonical-time-evidence-verify-output.json"),
    )
    if result["identity"] != sidecar.get("identity") or result[
        "time_evidence"
    ] != sidecar.get("time_evidence"):
        raise CanonicalTimeEvidenceError("sidecar_content_mismatch")
    return sidecar


__all__ = [
    "CanonicalTimeEvidenceError",
    "build_canonical_time_evidence",
    "verify_canonical_time_evidence",
]
