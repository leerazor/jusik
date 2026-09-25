"""Fixed engineering task and structured scheduler blocker contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ENGINEERING_SPEC_ID = "lab-paper-execution-contract-v1"
ENGINEERING_SPEC_AREA = "__engineering__"
ENGINEERING_OWNED_PATHS = frozenset(
    {
        "backend/jusik/paper_execution_contract.py",
        "backend/tests/test_paper_execution_contract.py",
    }
)
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
    "Return a candidate with verified evidence, an integrated commit, "
    "tests_passed=true, review_passed=false, and null engineering/investment "
    "status. A separate reviewer owns the final verdict."
)


@dataclass(frozen=True)
class EngineeringSpec:
    id: str
    area: str
    prompt: str
    owned_paths: frozenset[str]


ENGINEERING_SPECS = (
    EngineeringSpec(
        ENGINEERING_SPEC_ID,
        ENGINEERING_SPEC_AREA,
        ENGINEERING_SPEC_PROMPT,
        ENGINEERING_OWNED_PATHS,
    ),
    EngineeringSpec(
        "lab-strategy-lifecycle-receipt-v1",
        ENGINEERING_SPEC_AREA,
        "Implement only an offline version-bound strategy lifecycle evidence receipt "
        "adapter in backend/jusik/strategy_lifecycle_receipt.py and focused tests "
        "in backend/tests/test_strategy_lifecycle_receipt.py. Bind each receipt "
        "to an existing strategy id, exact version and evidence digest; reject "
        "missing, stale or conflicting identity. Do not change lifecycle transitions "
        "or grant engineering, investment, PAPER or live validation. Use offline "
        "pytest, Ruff and strict mypy. No network, broker, credentials, production "
        "wiring or dependency changes. Return a candidate with exact owned-file "
        "evidence, integrated commit, tests_passed=true, review_passed=false and "
        "null engineering/investment status. A separate reviewer decides PASS.",
        frozenset(
            {
                "backend/jusik/strategy_lifecycle_receipt.py",
                "backend/tests/test_strategy_lifecycle_receipt.py",
            }
        ),
    ),
    EngineeringSpec(
        "lab-paper-execution-restart-journal-v1",
        ENGINEERING_SPEC_AREA,
        "Implement only a durable offline idempotency journal for the existing "
        "paper execution contract in backend/jusik/paper_execution_contract.py "
        "and focused tests in backend/tests/test_paper_execution_contract.py. "
        "Persist intent before any fake-broker submit; on restart never resubmit "
        "an uncertain key. Reconcile partial fills, cancellation and rejection "
        "without duplicate calls. No real broker adapter, network, credentials, "
        "PAPER/live activation, production wiring or dependency changes. Use "
        "offline pytest, Ruff and strict mypy. Return a candidate with exact "
        "owned-file evidence, integrated commit, tests_passed=true, "
        "review_passed=false and null engineering/investment status. A separate "
        "reviewer decides PASS.",
        ENGINEERING_OWNED_PATHS,
    ),
)
ENGINEERING_SPEC_BY_ID = {spec.id: spec for spec in ENGINEERING_SPECS}
AUTOMATIC_ENGINEERING_BACKLOG = ENGINEERING_SPECS[1:]


class Blocker(BaseModel):
    """A bounded reason and explicit condition for releasing one task."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    blocker_reason: str = Field(min_length=1, max_length=2000)
    attempted_actions: list[str] = Field(default_factory=list, max_length=20)
    dependency: str | None = None
    dependency_identity: str | None = Field(
        default=None, pattern=r"^(missing|[a-f0-9]{64})$"
    )
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
