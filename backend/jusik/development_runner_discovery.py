"""Bounded, offline engineering discovery contracts and source identity."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from jusik.development_runner_contract import ENGINEERING_SPEC_AREA, EngineeringSpec

DISCOVERY_MODULES = (
    "paper_execution_contract",
    "strategy_lifecycle_receipt",
    "research_future_observation_replay",
    "research_market_calendar",
    "market_performance_metrics",
    "research_portfolio_performance_metrics",
    "market_history_action_accounting",
    "market_loss_accounting",
)
MAX_PROPOSALS = 3
MAX_INFRA_FAILURES = 2
_SHA256 = re.compile(r"[a-f0-9]{64}\Z")


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def strict_output_schema(model: type[BaseModel]) -> dict[str, object]:
    """Codex structured output requires every object property to be required."""
    schema: dict[str, object] = model.model_json_schema()

    def normalize(value: object) -> None:
        if isinstance(value, dict):
            value.pop("default", None)
            value.pop("title", None)
            properties = value.get("properties")
            if isinstance(properties, dict):
                value["required"] = list(properties)
                value["additionalProperties"] = False
            for child in value.values():
                normalize(child)
        elif isinstance(value, list):
            for child in value:
                normalize(child)

    normalize(schema)
    return schema


class SourceEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    path: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class DiscoveryProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    module: Literal[
        "paper_execution_contract",
        "strategy_lifecycle_receipt",
        "research_future_observation_replay",
        "research_market_calendar",
        "market_performance_metrics",
        "research_portfolio_performance_metrics",
        "market_history_action_accounting",
        "market_loss_accounting",
    ]
    goal: str = Field(min_length=20, max_length=400)
    reproduction: str = Field(min_length=20, max_length=600)
    gap: str = Field(min_length=20, max_length=500)
    tests: str = Field(min_length=20, max_length=500)
    stop_condition: str = Field(min_length=20, max_length=400)
    evidence: list[SourceEvidence] = Field(min_length=2, max_length=8)

    @field_validator("goal", "reproduction", "gap", "tests", "stop_condition")
    @classmethod
    def require_substantive_text(cls, value: str) -> str:
        if len(value.strip()) < 20:
            raise ValueError("proposal text is not substantive")
        return value

    @property
    def owned_paths(self) -> frozenset[str]:
        return frozenset(
            {
                f"backend/jusik/{self.module}.py",
                f"backend/tests/test_{self.module}.py",
            }
        )


class DiscoveryResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    planner_attempt_id: str
    baseline_head: str = Field(pattern=r"^[a-f0-9]{40}$")
    fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    status: Literal["proposal", "no_work"]
    proposal: DiscoveryProposal | None = None
    inspected_domains: list[str] = Field(default_factory=list, max_length=8)
    resume_condition: str | None = Field(default=None, max_length=500)
    alternatives: list[str] = Field(default_factory=list, max_length=4)

    @field_validator("inspected_domains")
    @classmethod
    def require_allowlisted_domains(cls, value: list[str]) -> list[str]:
        if not set(value).issubset(DISCOVERY_MODULES):
            raise ValueError("inspected domains must be allowlisted")
        return value

    @model_validator(mode="after")
    def check_status(self) -> DiscoveryResult:
        if self.status == "proposal" and self.proposal is None:
            raise ValueError("discovery proposal required")
        if self.status == "no_work" and (
            self.proposal is not None
            or len(self.inspected_domains) < 2
            or len(set(self.inspected_domains)) < 2
            or not self.resume_condition
            or len(self.resume_condition.strip()) < 12
            or not self.alternatives
            or any(len(item.strip()) < 12 for item in self.alternatives)
        ):
            raise ValueError("no_work needs inspected domains and resume alternatives")
        return self


class ScopeReview(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    verdict: Literal["PASS", "REJECT"]
    proposal_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    planner_attempt_id: str
    baseline_head: str = Field(pattern=r"^[a-f0-9]{40}$")
    fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    owned_paths: list[str] = Field(min_length=2, max_length=2)
    reason: str = Field(min_length=5, max_length=500)


def _git(repo: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, timeout=30
    ).stdout


def source_fingerprint(
    repo: Path, mandate_digest: str, tasks: list[tuple[str, str, str | None]]
) -> str:
    paths = sorted(
        path.decode()
        for path in _git(repo, "ls-files", "-z", "--", "backend/jusik", "backend/tests")
        .rstrip(b"\0")
        .split(b"\0")
        if path
    )
    files: list[tuple[str, str]] = []
    for path in paths:
        source = repo / path
        if source.is_symlink() or not source.is_file():
            raise ValueError("source tree contains a non-regular tracked path")
        files.append((path, hashlib.sha256(source.read_bytes()).hexdigest()))
    return digest({"files": files, "mandate": mandate_digest, "tasks": tasks})


def validate_proposal(repo: Path, proposal: DiscoveryProposal) -> None:
    if len({item.path for item in proposal.evidence}) != len(proposal.evidence):
        raise ValueError("duplicate source evidence")
    if not proposal.owned_paths.issubset({item.path for item in proposal.evidence}):
        raise ValueError("owned source and test evidence required")
    for item in proposal.evidence:
        path = item.path
        if (
            not path.startswith(("backend/jusik/", "backend/tests/"))
            or not path.endswith(".py")
            or Path(path).is_absolute()
            or ".." in Path(path).parts
        ):
            raise ValueError("source evidence path outside offline backend")
        source = repo / path
        if not source.is_file() or source.is_symlink():
            raise ValueError("source evidence missing or symlinked")
        current = hashlib.sha256(source.read_bytes()).hexdigest()
        if not _SHA256.fullmatch(item.sha256) or current != item.sha256:
            raise ValueError("source evidence hash changed")
        if hashlib.sha256(_git(repo, "show", f"main:{path}")).hexdigest() != current:
            raise ValueError("source evidence is not canonical main")


def proposal_digest(proposal: DiscoveryProposal) -> str:
    return digest(proposal.model_dump(mode="json"))


def spec_from_proposal(proposal: DiscoveryProposal) -> EngineeringSpec:
    owned = ", ".join(sorted(proposal.owned_paths))
    prompt = (
        f"Fix the reproduced offline product gap. Goal: {proposal.goal}\n"
        f"Reproduction: {proposal.reproduction}\nGap: {proposal.gap}\n"
        "Baseline source evidence: "
        f"{canonical_json([item.model_dump() for item in proposal.evidence])}\n"
        f"Own exactly {owned}. Tests: {proposal.tests}\n"
        f"Stop condition: {proposal.stop_condition}\n"
        "Change both owned files with a real source fix and focused regression test. "
        "Use offline pytest, Ruff check, Ruff format --check, and strict mypy. "
        "Do not change investment gates or criteria, strategy activation, PAPER/live "
        "activation, credentials, configuration, dependencies, network, services, "
        "orders, runner policy, or other paths. Fixture results are not investment "
        "validation. Return a candidate with current main integrated commit, exact "
        "owned-file SHA-256 evidence, tests_passed=true, review_passed=false, and "
        "null engineering/investment status. Independent review decides PASS."
    )
    spec_content = {
        "area": ENGINEERING_SPEC_AREA,
        "prompt": prompt,
        "owned_paths": sorted(proposal.owned_paths),
    }
    return EngineeringSpec(
        id=f"lab-discovery-{digest(spec_content)[:32]}",
        area=ENGINEERING_SPEC_AREA,
        prompt=prompt,
        owned_paths=proposal.owned_paths,
    )


def validate_scope_review(
    review: ScopeReview,
    proposal: DiscoveryProposal,
    attempt_id: str,
    baseline_head: str,
    fingerprint: str,
) -> None:
    if (
        review.proposal_digest != proposal_digest(proposal)
        or review.planner_attempt_id != attempt_id
        or review.baseline_head != baseline_head
        or review.fingerprint != fingerprint
        or review.owned_paths != sorted(proposal.owned_paths)
    ):
        raise ValueError("scope review identity mismatch")
