"""Fail-closed entry gate for R7 isolated simulation.

The gate only authorizes a future isolated simulation when the prospective
window, data readiness, OOS result, stress result, and independent review are
all evidenced.  It never authorizes PAPER or live promotion.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from jusik.research_r7_isolation import CHILDREN, R7IsolationWorkspace, _sha256_path

if TYPE_CHECKING:
    from jusik.research_prospective_readiness import ProspectiveReadiness

HASH_PATTERN = r"^[a-f0-9]{64}$"


class R7ReviewEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    oos_artifact_sha256: str | None = Field(default=None, pattern=HASH_PATTERN)
    oos_passed: bool = False
    stress_artifact_sha256: str | None = Field(default=None, pattern=HASH_PATTERN)
    stress_passed: bool = False
    independent_review_sha256: str | None = Field(
        default=None, pattern=HASH_PATTERN
    )
    independent_review_passed: bool = False

    @model_validator(mode="after")
    def require_hash_for_passed_evidence(self) -> R7ReviewEvidence:
        if self.oos_passed and self.oos_artifact_sha256 is None:
            raise ValueError("passed OOS evidence requires an artifact hash")
        if self.stress_passed and self.stress_artifact_sha256 is None:
            raise ValueError("passed stress evidence requires an artifact hash")
        if self.independent_review_passed and self.independent_review_sha256 is None:
            raise ValueError("passed review evidence requires an artifact hash")
        return self


class R7GateResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    state: Literal["blocked", "ready"]
    simulation_allowed: bool = False
    paper_decision_required: Literal[True] = True
    automatic_promotion_eligible: Literal[False] = False
    reasons: tuple[str, ...]
    workspace_manifest_sha256: str | None = Field(
        default=None, pattern=HASH_PATTERN
    )

    @model_validator(mode="after")
    def preserve_gate_invariants(self) -> R7GateResult:
        if self.state == "blocked" and self.simulation_allowed:
            raise ValueError("blocked R7 gate cannot allow simulation")
        if self.state == "ready" and (
            not self.simulation_allowed or self.reasons
        ):
            raise ValueError("ready R7 gate requires simulation and no reasons")
        return self


def _open_directory_chain(path: Path) -> int:
    """Open a directory path without following any component symlink."""
    absolute = Path(os.path.abspath(path))
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    descriptor = os.open(os.sep, flags)
    try:
        for component in absolute.parts[1:]:
            child = os.open(component, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _manifest_sha256(workspace: R7IsolationWorkspace) -> str | None:
    root_path = Path(os.path.abspath(workspace.root))
    expected_workspace_paths = {
        "market_data": root_path / "market-data",
        "config": root_path / "config",
        "database": root_path / "database",
        "artifacts": root_path / "artifacts",
        "manifest": root_path / "workspace.json",
    }
    actual_workspace_paths = {
        "market_data": Path(os.path.abspath(workspace.market_data)),
        "config": Path(os.path.abspath(workspace.config)),
        "database": Path(os.path.abspath(workspace.database)),
        "artifacts": Path(os.path.abspath(workspace.artifacts)),
        "manifest": Path(os.path.abspath(workspace.manifest)),
    }
    if actual_workspace_paths != expected_workspace_paths:
        return None
    root_fd: int | None = None
    child_fds: list[int] = []
    manifest_fd: int | None = None
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    try:
        root_fd = _open_directory_chain(root_path)
        root_stat = os.fstat(root_fd)
        if not stat.S_ISDIR(root_stat.st_mode) or root_stat.st_mode & 0o777 != 0o700:
            return None
        for name in CHILDREN:
            descriptor = os.open(name, directory_flags, dir_fd=root_fd)
            child_fds.append(descriptor)
            child_stat = os.fstat(descriptor)
            if (
                not stat.S_ISDIR(child_stat.st_mode)
                or child_stat.st_mode & 0o777 != 0o700
            ):
                return None
        manifest_fd = os.open(
            "workspace.json",
            os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=root_fd,
        )
        manifest_stat = os.fstat(manifest_fd)
        if (
            not stat.S_ISREG(manifest_stat.st_mode)
            or manifest_stat.st_mode & 0o777 != 0o600
        ):
            return None
        chunks: list[bytes] = []
        while chunk := os.read(manifest_fd, 1024 * 1024):
            chunks.append(chunk)
        manifest_bytes = b"".join(chunks)
    except OSError:
        return None
    finally:
        if manifest_fd is not None:
            os.close(manifest_fd)
        for descriptor in child_fds:
            os.close(descriptor)
        if root_fd is not None:
            os.close(root_fd)
    try:
        payload = json.loads(manifest_bytes.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("schema_version") != 1 or payload.get("mode") != "r7_isolated":
        return None
    if (
        payload.get("paper_only") is not True
        or payload.get("automatic_promotion_eligible") is not False
        or payload.get("retrospective_write_access") is not False
    ):
        return None
    expected_paths = {
        **{
            name: name
            for name in ("market-data", "config", "database", "artifacts")
        },
        "workspace.json": "workspace.json",
    }
    if payload.get("paths") != expected_paths:
        return None
    identities = payload.get("source_identities")
    if not isinstance(identities, dict) or not identities:
        return None
    if any(
        not isinstance(key, str)
        or not key
        or not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
        for key, value in identities.items()
    ):
        return None
    source_hashes = payload.get("source_hashes")
    if not isinstance(source_hashes, dict) or not source_hashes:
        return None
    if set(source_hashes.values()) != set(identities.values()):
        return None
    for path, expected in source_hashes.items():
        if (
            not isinstance(path, str)
            or not os.path.isabs(path)
            or not isinstance(expected, str)
            or len(expected) != 64
            or any(character not in "0123456789abcdef" for character in expected)
        ):
            return None
        try:
            if _sha256_path(Path(path)) != expected:
                return None
        except (OSError, ValueError):
            return None
    return hashlib.sha256(manifest_bytes).hexdigest()


def evaluate_r7_gate(
    *,
    prospective: ProspectiveReadiness,
    workspace: R7IsolationWorkspace | None,
    evidence: R7ReviewEvidence,
) -> R7GateResult:
    """Return a non-promoting R7 decision from already-collected evidence."""

    reasons: list[str] = []
    manifest_sha = None if workspace is None else _manifest_sha256(workspace)
    if manifest_sha is None:
        reasons.append("isolated_workspace_manifest_unavailable")
    if prospective.registration_status != "window_elapsed":
        reasons.append("prospective_window_not_elapsed")
    if prospective.evaluation_inputs_complete is not True:
        reasons.append("prospective_inputs_incomplete")
    if prospective.start_boundary.state != "unverified_candidate":
        reasons.append("prospective_start_boundary_unverified")
    if prospective.end_boundary.state != "unverified_candidate":
        reasons.append("prospective_end_boundary_unverified")
    if prospective.execution_evidence.state != "linked_integrity":
        reasons.append("prospective_execution_evidence_incomplete")
    if not evidence.oos_passed or evidence.oos_artifact_sha256 is None:
        reasons.append("untouched_oos_not_passed")
    if not evidence.stress_passed or evidence.stress_artifact_sha256 is None:
        reasons.append("stress_review_not_passed")
    if (
        not evidence.independent_review_passed
        or evidence.independent_review_sha256 is None
    ):
        reasons.append("independent_review_not_passed")
    ready = not reasons
    return R7GateResult(
        state="ready" if ready else "blocked",
        simulation_allowed=ready,
        reasons=tuple(reasons),
        workspace_manifest_sha256=manifest_sha,
    )
