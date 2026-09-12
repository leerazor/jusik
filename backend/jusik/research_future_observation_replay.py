"""Offline, synthetic replay classifier for the future-observation protocol.

This module deliberately has no collector, database, runtime, or order dependencies.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _utc(value: str | datetime, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{field} timestamp is invalid") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} timestamp must be timezone-aware")
    return parsed.astimezone(UTC)


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str = Field(min_length=1)
    observation_id: str = Field(min_length=1)
    raw: str
    received_at: str | datetime
    event_at: str | datetime
    read_started_at: str | datetime
    read_finished_at: str | datetime
    evidence_flags: frozenset[str] = frozenset()

    @field_validator("evidence_flags", mode="before")
    @classmethod
    def known_flags(cls, value: object) -> object:
        values = set(cast(list[str], value or []))
        unknown = values - {"unavailable", "unverified_provenance"}
        if unknown:
            raise ValueError(f"unknown evidence flags: {sorted(unknown)}")
        return values

    @field_validator("raw")
    @classmethod
    def utf8_encodable(cls, value: str) -> str:
        value.encode("utf-8")
        return value


class BoundaryRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    boundary: Literal["start", "end"]
    due_at: str | datetime
    evidence_id: str = Field(min_length=1)


class Truncation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    total_count: int = Field(ge=0)
    inspected_count: int = Field(ge=0)

    @model_validator(mode="after")
    def inspected_not_above_total(self) -> Truncation:
        if self.inspected_count > self.total_count:
            raise ValueError("inspected_count cannot exceed total_count")
        return self

    @property
    def uninspected_count(self) -> int:
        return self.total_count - self.inspected_count


class SyntheticFixture(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    synthetic: Literal[True]
    window_start_at: str | datetime
    window_end_at: str | datetime
    checked_at: str | datetime
    observations: list[Observation] = Field(default_factory=list)
    required_boundaries: list[BoundaryRequirement] = Field(default_factory=list)
    truncation: Truncation | None = None

    @field_validator("synthetic", mode="before")
    @classmethod
    def require_literal_true(cls, value: object) -> object:
        if value is not True:
            raise ValueError("fixture must set synthetic to literal true")
        return value


Classification = Literal[
    "in_window",
    "out_of_window",
    "late_arrival",
    "duplicate",
    "conflict",
    "not_due",
    "missing",
    "clock_invalid",
    "unavailable",
    "unverified_provenance",
    "unresolved",
]


class ReceiptResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    receipt_index: int = Field(ge=0)
    received_at: str | None
    raw: str
    raw_sha256: str


class ObservationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str
    observation_id: str
    raw_versions: list[str]
    receipts: list[ReceiptResult]
    classifications: list[Classification]
    exclusion_reasons: list[str]
    evidence_counts: dict[str, int]


class ReplayResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    synthetic: Literal[True] = True
    registered: Literal[False] = False
    accepted_nav: Literal[False] = False
    evaluation_inputs_complete: Literal[False] = False
    window_start_at: datetime
    window_end_at: datetime
    checked_at: datetime
    observations: list[ObservationResult]
    boundary_states: dict[str, str]
    truncation: dict[str, int | bool] | None
    counts: dict[str, int]


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def replay(fixture: SyntheticFixture | dict[str, object]) -> ReplayResult:
    """Classify a synthetic fixture while preserving input receipt order."""
    parsed = (
        fixture
        if isinstance(fixture, SyntheticFixture)
        else SyntheticFixture.model_validate(fixture)
    )
    start = _utc(parsed.window_start_at, "window_start_at")
    end = _utc(parsed.window_end_at, "window_end_at")
    checked = _utc(parsed.checked_at, "checked_at")
    if end <= start:
        raise ValueError("window_end_at must be after window_start_at")

    groups: dict[tuple[str, str], list[tuple[int, Observation, str]]] = {}
    for index, item in enumerate(parsed.observations):
        digest = _hash(item.raw)
        groups.setdefault((item.source_id, item.observation_id), []).append(
            (index, item, digest)
        )
    results: list[ObservationResult] = []
    for (source_id, observation_id), entries in groups.items():
        hashes = list(dict.fromkeys(digest for _, _, digest in entries))
        receipts: list[ReceiptResult] = []
        reasons: list[str] = []
        classes: list[Classification] = []
        invalid = False
        for index, item, digest in entries:
            try:
                received = _utc(item.received_at, "received_at")
                _utc(item.event_at, "event_at")
                read_started = _utc(item.read_started_at, "read_started_at")
                read_finished = _utc(item.read_finished_at, "read_finished_at")
                if read_finished < read_started:
                    raise ValueError("clock_invalid")
                received_text = received.isoformat()
            except (TypeError, ValueError, OverflowError):
                invalid = True
                received_text = str(item.received_at)
            receipts.append(
                ReceiptResult(
                    receipt_index=index,
                    received_at=received_text,
                    raw=item.raw,
                    raw_sha256=digest,
                )
            )
        if invalid:
            classes.append("clock_invalid")
            reasons.append("invalid_or_reversed_clock")
        if len(hashes) > 1:
            classes.append("conflict")
            reasons.append("same_source_and_id_have_different_raw_hashes")
        elif len(entries) > 1:
            classes.append("duplicate")
            reasons.append("repeated_identical_raw_receipt")
        first = entries[0][1]
        flags = first.evidence_flags
        for flag in ("unavailable", "unverified_provenance"):
            if flag in flags:
                classes.append(flag)  # type: ignore[arg-type]
                reasons.append(flag)
        try:
            first_received = _utc(first.received_at, "received_at")
            if not invalid:
                if first_received > checked:
                    classes.append("not_due")
                    reasons.append("receipt_is_after_checked_at")
                elif start <= first_received < end:
                    classes.append("in_window")
                else:
                    classes.append("out_of_window")
                if _utc(first.event_at, "event_at") < start and first_received >= start:
                    classes.append("late_arrival")
                    reasons.append("event_precedes_window_but_receipt_is_in_window")
        except (TypeError, ValueError, OverflowError):
            pass
        if len(classes) > 1 and (invalid or len(hashes) > 1):
            classes.insert(0, "unresolved")
            reasons.append("independent_error_candidates_have_no_precedence")
        if not classes:
            classes = ["unresolved"]
        results.append(
            ObservationResult(
                source_id=source_id,
                observation_id=observation_id,
                raw_versions=hashes,
                receipts=receipts,
                classifications=classes,
                exclusion_reasons=reasons,
                evidence_counts={
                    "receipts": len(receipts),
                    "raw_versions": len(hashes),
                },
            )
        )

    boundary_states: dict[str, str] = {}
    for boundary in parsed.required_boundaries:
        due = _utc(boundary.due_at, "boundary due_at")
        state = "not_due" if checked < due else "missing"
        boundary_states[boundary.boundary] = state
    truncation = None
    if parsed.truncation is not None:
        truncation = {
            "total_count": parsed.truncation.total_count,
            "inspected_count": parsed.truncation.inspected_count,
            "uninspected_count": parsed.truncation.uninspected_count,
            "truncated": parsed.truncation.total_count
            > parsed.truncation.inspected_count,
        }
    counts: dict[str, int] = {
        "logical_observations": len(results),
        "receipts": len(parsed.observations),
        "in_window": 0,
        "out_of_window": 0,
    }
    for result in results:
        for classification in result.classifications:
            counts[classification] = counts.get(classification, 0) + 1
    return ReplayResult(
        window_start_at=start,
        window_end_at=end,
        checked_at=checked,
        observations=results,
        boundary_states=boundary_states,
        truncation=truncation,
        counts=counts,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Replay a synthetic future-observation fixture"
    )
    parser.add_argument("--fixture", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = args.output / "replay.json" if args.output.is_dir() else args.output
    if args.fixture.resolve() == output.resolve():
        raise SystemExit("--output must differ from --fixture")
    if args.fixture.stat().st_size > 4 * 1024 * 1024:
        raise SystemExit("fixture exceeds 4 MiB limit")
    result = replay(json.loads(args.fixture.read_text(encoding="utf-8")))
    payload = (
        json.dumps(
            result.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, indent=2
        )
        + "\n"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output.open("x", encoding="utf-8") as handle:
            handle.write(payload)
    except FileExistsError as exc:
        raise SystemExit("refusing to overwrite existing output") from exc


if __name__ == "__main__":
    main()
