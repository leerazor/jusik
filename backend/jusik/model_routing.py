"""Resolve explicit configured model/effort choices; never optimize by price."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

DEFAULT_POLICY = Path(__file__).resolve().parents[2] / ".codex/model-routing.json"
Identifier = Annotated[str, Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$")]


class ModelRoutingError(ValueError):
    """Safe routing failure without raw configuration values."""


class Variant(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    model: Identifier
    effort: Literal["low", "medium", "high", "xhigh", "max", "ultra"]
    aa_slug: Identifier
    host_supported: bool
    diagnostic_only: bool = False


class Profile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    role: Identifier
    selected: Identifier


class Policy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    schema_version: Literal[1]
    variants: dict[Identifier, Variant]
    profiles: dict[Identifier, Profile]

    @model_validator(mode="after")
    def valid_profiles(self) -> Self:
        pairs = [(v.model, v.effort) for v in self.variants.values()]
        if len(set(pairs)) != len(pairs):
            raise ValueError("duplicate model/effort pair")
        for name, profile in self.profiles.items():
            variant = self.variants.get(profile.selected)
            if variant is None or not variant.host_supported:
                raise ValueError("unsupported configured variant")
            if variant.diagnostic_only and (
                profile.role != "escalate" or name != "role.escalate"
            ):
                raise ValueError("diagnostic variant requires escalation role")
        return self


def resolve(profile: str, policy_path: Path | None = None) -> tuple[Variant, str, str]:
    """Return configured variant, logical role, and exact policy input hash."""
    try:
        raw = (policy_path if policy_path is not None else DEFAULT_POLICY).read_bytes()
        policy = Policy.model_validate_json(raw)
        selected = policy.profiles[profile]
        return (
            policy.variants[selected.selected],
            selected.role,
            hashlib.sha256(raw).hexdigest(),
        )
    except (OSError, ValueError, KeyError) as exc:
        raise ModelRoutingError("routing policy or profile unavailable") from exc


def check_spawn(profile: str, policy_path: Path | None, spawn_args: Path) -> None:
    variant, role, _ = resolve(profile, policy_path)
    try:
        args = json.loads(spawn_args.read_text())
        if not isinstance(args, dict) or (
            args.get("model") != variant.model
            or args.get("reasoning_effort") != variant.effort
            or args.get("fork_turns") != "none"
            or args.get("agent_type") not in {role, "default"}
        ):
            raise ValueError("spawn mismatch")
    except (OSError, ValueError, TypeError) as exc:
        raise ModelRoutingError("spawn model, effort, role or fork mismatch") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["resolve", "check"])
    parser.add_argument("--policy", type=Path)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--spawn-args", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "check":
            if args.spawn_args is None:
                raise ModelRoutingError("check requires spawn args")
            check_spawn(args.profile, args.policy, args.spawn_args)
        variant, role, digest = resolve(args.profile, args.policy)
    except ModelRoutingError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "model": variant.model,
                "reasoning_effort": variant.effort,
                "role": role,
                "profile": args.profile,
                "policy_sha256": digest,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
