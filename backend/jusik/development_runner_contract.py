"""Fixed engineering task and structured scheduler blocker contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ENGINEERING_SPEC_ID = "lab-paper-execution-contract-v1"
ENGINEERING_SPEC_AREA = "__engineering__"
ENGINEERING_SPEC_PROMPT = (
    "Implement only an offline deterministic execution interface and fake-broker "
    "contract tests for idempotency, partial fills, cancellations, rejected orders, "
    "retry safety, and reconciliation. Own only "
    "backend/jusik/paper_execution_contract.py and "
    "backend/tests/test_paper_execution_contract.py. Use focused offline pytest, "
    "Ruff, and configured mypy within the runner timeout; no network, GPU, "
    "investment experiment, production wiring, or dependency changes. "
    "Do not call brokerage APIs, load credentials, activate PAPER or live trading, "
    "change research results, or change investment roadmap checkboxes. "
    "Complete only with verified evidence, an integrated commit, independent "
    "review, ENGINEERING_COMPLETE, and NOT_EVALUATED."
)


class Blocker(BaseModel):
    """A bounded reason and explicit condition for releasing one task."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    blocker_reason: str = Field(min_length=1, max_length=2000)
    attempted_actions: list[str] = Field(default_factory=list, max_length=20)
    dependency: str | None = None
    resume_condition: str = Field(min_length=1, max_length=1000)
    retry_policy: Literal["none", "manual", "event", "bounded"]
    next_eligible_retry: datetime | None = None
    alternative_ready_tasks: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("next_eligible_retry")
    @classmethod
    def require_utc(cls, value: datetime | None) -> datetime | None:
        if value is not None and (
            value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value)
        ):
            raise ValueError("next retry must be timezone-aware UTC")
        return value

    @model_validator(mode="after")
    def require_bounded_deadline(self) -> Blocker:
        if (self.retry_policy == "bounded") != (self.next_eligible_retry is not None):
            raise ValueError("bounded retry requires a UTC deadline")
        return self


def unknown_blocker(reason: str, *, dependency: str | None = None) -> Blocker:
    return Blocker(
        blocker_reason=reason,
        attempted_actions=[],
        dependency=dependency,
        resume_condition="unknown",
        retry_policy="manual",
        next_eligible_retry=None,
        alternative_ready_tasks=[],
    )
