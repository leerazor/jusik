"""Bounded read-only review receipt contract for engineering candidates."""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from jusik.development_runner_contract import ENGINEERING_OWNED_PATHS


class ReviewReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    task_id: str
    implementation_attempt_id: str
    review_attempt_id: str
    baseline_head: str = Field(pattern=r"^[a-f0-9]{40,64}$")
    main_head: str = Field(pattern=r"^[a-f0-9]{40,64}$")
    owned_file_hashes: dict[str, str]
    product_commit: str | None = Field(default=None, pattern=r"^[a-f0-9]{40,64}$")
    verdict: Literal["PASS", "FAIL"]


def review_schema(
    owned_paths: frozenset[str] = ENGINEERING_OWNED_PATHS,
    *,
    recovery: bool = False,
) -> dict[str, Any]:
    hashes = {
        path: {"type": "string", "pattern": "^[a-f0-9]{64}$"}
        for path in sorted(owned_paths)
    }
    properties: dict[str, Any] = {
        "task_id": {"type": "string"},
        "implementation_attempt_id": {"type": "string"},
        "review_attempt_id": {"type": "string"},
        "baseline_head": {"type": "string", "pattern": "^[a-f0-9]{40,64}$"},
        "main_head": {"type": "string", "pattern": "^[a-f0-9]{40,64}$"},
        "owned_file_hashes": {
            "type": "object",
            "additionalProperties": False,
            "required": sorted(hashes),
            "properties": hashes,
        },
        "verdict": {"type": "string", "enum": ["PASS", "FAIL"]},
    }
    if recovery:
        properties["product_commit"] = {
            "type": "string",
            "pattern": "^[a-f0-9]{40,64}$",
        }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(properties),
        "properties": properties,
    }


def validate_receipt(
    payload: Any,
    expected: dict[str, Any],
    owned_paths: frozenset[str] = ENGINEERING_OWNED_PATHS,
) -> ReviewReceipt:
    if not isinstance(payload, dict) or ("product_commit" in payload) != (
        "product_commit" in expected
    ):
        raise ValueError("review receipt identity mismatch")
    try:
        receipt = ReviewReceipt.model_validate(payload)
    except ValidationError as exc:
        raise ValueError("review receipt schema invalid") from exc
    if set(receipt.owned_file_hashes) != owned_paths or any(
        len(value) != 64 or any(char not in "0123456789abcdef" for char in value)
        for value in receipt.owned_file_hashes.values()
    ):
        raise ValueError("review receipt owned hashes invalid")
    if {
        key: value
        for key, value in receipt.model_dump(exclude_none=True).items()
        if key != "verdict"
    } != expected:
        raise ValueError("review receipt identity mismatch")
    return receipt


def review_prompt(context: dict[str, Any]) -> str:
    return (
        "Review the integrated engineering candidate independently. "
        "Read only the repository and named owned files. Do not edit files, "
        "run orders, use network, change configuration, or spawn agents. "
        "Check correctness, regression risk, and the supplied identity. "
        "Return PASS only if no material finding remains; otherwise FAIL. "
        "Return only the required JSON with these exact identity fields: "
        + json.dumps(context, sort_keys=True)
    )
