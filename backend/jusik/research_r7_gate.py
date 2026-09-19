"""Fail-closed entry gate for R7 isolated simulation.

The gate only authorizes a future isolated simulation when the prospective
window, data readiness, OOS result, stress result, and independent review are
all evidenced.  It never authorizes PAPER or live promotion.
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from jusik.research_r7_isolation import R7IsolationWorkspace

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


def _manifest_sha256(workspace: R7IsolationWorkspace) -> str | None:
    if workspace.root.is_symlink() or not workspace.root.is_dir():
        return None
    expected = {
        workspace.market_data,
        workspace.config,
        workspace.database,
        workspace.artifacts,
    }
    if any(path.is_symlink() or not path.is_dir() for path in expected):
        return None
    if workspace.manifest.is_symlink() or not workspace.manifest.is_file():
        return None
    if workspace.root.stat().st_mode & 0o777 != 0o700:
        return None
    if any(path.stat().st_mode & 0o777 != 0o700 for path in expected):
        return None
    if workspace.manifest.stat().st_mode & 0o777 != 0o600:
        return None
    try:
        payload = json.loads(workspace.manifest.read_text(encoding="utf-8"))
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
    return hashlib.sha256(workspace.manifest.read_bytes()).hexdigest()


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
