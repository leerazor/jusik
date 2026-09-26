"""Identity-bound, read-only scope review for roadmap planner proposals."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from jusik.development_runner_planning import PlanningProposal, PlanningResult

ROADMAP_TASK_SCOPE_GUARD = (
    "Approved roadmap scope is {work_class} diagnosis only. Preserve all roadmap "
    "phase gates, MDD 20%, PAPER 10%, and maximum three candidates. Do not start a "
    "new financial or strategy experiment, reuse an untouched holdout for tuning, "
    "claim synthetic data as investment evidence, place actual orders, or activate "
    "PAPER/LIVE. Scope PASS permits this task to be queued only; it is not an "
    "implementation review or investment validation. Set completion.followup "
    "to null; a later proposal requires a new planner and independent scope "
    "review. If actual inputs for a computation are absent, report a bounded "
    "blocker and stop."
)


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


class PendingRoadmapScope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    planner_task_id: str
    planner_attempt_id: str
    fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    baseline_head: str = Field(pattern=r"^[a-f0-9]{40}$")
    mandate_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    roadmap_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    expires_at: str
    snapshot: list[tuple[str, str, str | None]]
    result: PlanningResult
    proposal_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    evidence_digest: str = Field(pattern=r"^[a-f0-9]{64}$")

    @field_validator("expires_at")
    @classmethod
    def utc_expiration(cls, value: str) -> str:
        try:
            expires_at = datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("roadmap scope expiry invalid") from exc
        if expires_at.utcoffset() != timedelta(0):
            raise ValueError("roadmap scope expiry must be UTC")
        return value

    @property
    def proposal(self) -> PlanningProposal:
        proposal = self.result.proposal
        if proposal is None:
            raise ValueError("roadmap scope has no proposal")
        if digest(proposal.model_dump(mode="json")) != self.proposal_digest:
            raise ValueError("roadmap proposal changed")
        if digest([item.model_dump(mode="json") for item in proposal.evidence]) != (
            self.evidence_digest
        ):
            raise ValueError("roadmap evidence changed")
        return proposal


class RoadmapScopeReview(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    verdict: Literal["PASS", "REJECT", "WAIT"]
    review_attempt_id: str
    planner_task_id: str
    planner_attempt_id: str
    fingerprint: str
    baseline_head: str
    mandate_digest: str
    roadmap_digest: str
    area: str
    proposal_digest: str
    evidence_digest: str
    work_class: Literal["readiness", "data", "accounting", "offline_contract"] | None
    reason: str = Field(min_length=20, max_length=500)


def validate_scope_review(
    review: RoadmapScopeReview, pending: PendingRoadmapScope, review_attempt_id: str
) -> None:
    proposal = pending.proposal
    if (
        review.review_attempt_id,
        review.planner_task_id,
        review.planner_attempt_id,
        review.fingerprint,
        review.baseline_head,
        review.mandate_digest,
        review.roadmap_digest,
        review.area,
        review.proposal_digest,
        review.evidence_digest,
    ) != (
        review_attempt_id,
        pending.planner_task_id,
        pending.planner_attempt_id,
        pending.fingerprint,
        pending.baseline_head,
        pending.mandate_digest,
        pending.roadmap_digest,
        proposal.area,
        pending.proposal_digest,
        pending.evidence_digest,
    ):
        raise ValueError("roadmap scope receipt identity mismatch")
