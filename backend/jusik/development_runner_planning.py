"""Bounded automatic planning for an empty development queue."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

PLANNING_AREA = "__planning__"
PLANNER_PREFIX = "planner-"
WAIT_REASON_MAX = 200


class PlanningEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class PlanningProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,100}$")
    area: str
    prompt: str = Field(min_length=1, max_length=2000)
    evidence: list[PlanningEvidence] = Field(min_length=1, max_length=20)


class PlanningResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    task_id: str
    attempt_id: str
    fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    status: Literal["proposed", "waiting"]
    proposal: PlanningProposal | None = None
    wait_reason: str | None = Field(default=None, min_length=1, max_length=200)


def fingerprint(
    tasks: list[tuple[str, str, str | None]], main_head: str, utc_date: str
) -> str:
    value = {
        "tasks": sorted(tasks),
        "main_head": main_head,
        "utc_date": utc_date,
    }
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def validate_planning_result(
    payload: Any,
    task_id: str,
    attempt_id: str,
    expected_fingerprint: str,
    config: Any,
    attempt_dir: Path,
    allowed_areas: set[str],
    reserved_ids: set[str],
) -> PlanningResult:
    try:
        result = PlanningResult.model_validate(payload)
    except ValidationError as exc:
        raise ValueError("planning schema invalid") from exc
    if (result.task_id, result.attempt_id, result.fingerprint) != (
        task_id,
        attempt_id,
        expected_fingerprint,
    ):
        raise ValueError("planning identity mismatch")
    if result.status == "waiting":
        if result.proposal is not None or result.wait_reason is None:
            raise ValueError("waiting result needs a fixed wait reason")
        return result
    proposal = result.proposal
    if proposal is None or result.wait_reason is not None:
        raise ValueError("proposed result needs one proposal")
    if proposal.id.startswith(PLANNER_PREFIX) or proposal.id in reserved_ids:
        raise ValueError("proposal id is reserved")
    if proposal.area not in allowed_areas:
        raise ValueError("proposal area is not allowed")
    required = (
        "objective",
        "scope",
        "inputs",
        "computation cap",
        "tests",
        "stop condition",
    )
    if any(label.lower() not in proposal.prompt.lower() for label in required):
        raise ValueError("proposal prompt is not bounded")
    roots = [
        config.repo,
        config.repo.parent,
        config.state_dir,
        config.history_dir,
        config.artifact_dir,
    ]
    for evidence in proposal.evidence:
        raw_path = Path(evidence.path).expanduser()
        if raw_path.is_symlink():
            raise ValueError("planning evidence path invalid")
        path = raw_path.resolve()
        if attempt_dir.resolve() == path or attempt_dir.resolve() in path.parents:
            raise ValueError("planner cannot cite its own evidence")
        if not any(
            path == root.resolve() or root.resolve() in path.parents for root in roots
        ):
            raise ValueError("planning evidence path invalid")
        if path.is_symlink() or not path.is_file():
            raise ValueError("planning evidence path invalid")
        if hashlib.sha256(path.read_bytes()).hexdigest() != evidence.sha256:
            raise ValueError("planning evidence hash invalid")
    return result


PLANNING_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "task_id",
        "attempt_id",
        "fingerprint",
        "status",
        "proposal",
        "wait_reason",
    ],
    "properties": {
        "task_id": {"type": "string"},
        "attempt_id": {"type": "string"},
        "fingerprint": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
        "status": {"type": "string", "enum": ["proposed", "waiting"]},
        "proposal": {
            "type": ["object", "null"],
            "additionalProperties": False,
            "required": ["id", "area", "prompt", "evidence"],
            "properties": {
                "id": {
                    "type": "string",
                    "pattern": "^[a-z0-9][a-z0-9-]{2,100}$",
                },
                "area": {
                    "type": "string",
                    "enum": sorted(
                        {
                            "entry-amount-distribution",
                            "preregistration-small-entry",
                            "future-observation-protocol",
                            "paper-signal-evidence",
                            "portfolio-stress-robustness",
                        }
                    ),
                },
                "prompt": {"type": "string", "minLength": 1, "maxLength": 2000},
                "evidence": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 20,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["path", "sha256"],
                        "properties": {
                            "path": {"type": "string", "minLength": 1},
                            "sha256": {
                                "type": "string",
                                "pattern": "^[a-f0-9]{64}$",
                            },
                        },
                    },
                },
            },
        },
        "wait_reason": {
            "type": ["string", "null"],
            "minLength": 1,
            "maxLength": WAIT_REASON_MAX,
        },
    },
}


def planner_task_id(fingerprint_value: str) -> str:
    return f"{PLANNER_PREFIX}{fingerprint_value[:24]}"
