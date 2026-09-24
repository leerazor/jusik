"""Bounded queue rules for the tracked investment development roadmap."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROADMAP_SCOPE = "investment-roadmap"
ROADMAP_PATH = Path("docs/investment-development-roadmap.md")
ROADMAP_SEED_AREA = "r1-01"
ROADMAP_SEED_TASK_ID = "roadmap-r1-01-v1"
ROADMAP_PENDING_LIMIT = 8
DEVELOPMENT_DELIVERY_POLICY = (
    "Delivery policy: an agent-invented unit-regression fixture count or ordinary "
    "focused-test call count is not a scientific experiment cap and must not "
    "permanently block a technical slice. The current supervisor authorizes a "
    "prospective replacement using focused files plus runtime and artifact budgets; "
    "retain historical violations without retroactive approval. Keep user limits, "
    "research sample/period/assumptions/seed/experiment counts, financial data, and "
    "compute budgets strict. Honor current tracked docs over stale agent-generated "
    "task test-count limits. Distinguish technical-slice completion from full "
    "financial or data acceptance. Do not bypass identity, hash, review, or other "
    "completion gates. Routine repair of the owned environment or cache needs no "
    "fresh user permission."
)

_CHECKLIST_RE = re.compile(r"^- \[([ xX])\] \*\*(R[0-9]+-[0-9]{2})\*\*\s+(.+)$")
_ID_RE = re.compile(r"^r[0-9]+-[0-9]{2}$")


class RoadmapError(ValueError):
    """The tracked roadmap cannot safely define a queue."""


@dataclass(frozen=True)
class ChecklistItem:
    id: str
    phase: int
    complete: bool
    text: str


@dataclass(frozen=True)
class Roadmap:
    path: Path
    content: str
    items: tuple[ChecklistItem, ...]

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()

    @property
    def by_id(self) -> dict[str, ChecklistItem]:
        return {item.id: item for item in self.items}


def load_roadmap(repo: Path) -> Roadmap:
    path = repo / ROADMAP_PATH
    if not path.is_file() or path.is_symlink():
        raise RoadmapError("tracked investment roadmap is missing")
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RoadmapError("tracked investment roadmap is unreadable") from exc
    items: list[ChecklistItem] = []
    seen: set[str] = set()
    for line in content.splitlines():
        if "**R" not in line:
            continue
        match = _CHECKLIST_RE.match(line)
        if match is None:
            raise RoadmapError("tracked investment roadmap checklist is malformed")
        raw_id = match.group(2)
        item_id = raw_id.lower()
        if not _ID_RE.fullmatch(item_id) or item_id in seen:
            raise RoadmapError("tracked investment roadmap checklist has invalid IDs")
        seen.add(item_id)
        items.append(
            ChecklistItem(
                id=item_id,
                phase=int(item_id[1 : item_id.index("-")]),
                complete=match.group(1).lower() == "x",
                text=match.group(3).strip(),
            )
        )
    if not items or not any(item.id == "r1-01" for item in items):
        raise RoadmapError("tracked investment roadmap has no usable checklist")
    return Roadmap(path.resolve(), content, tuple(items))


def roadmap_fingerprint(
    tasks: list[tuple[str, str, str | None]],
    roadmap: Roadmap,
    mandate_digest: str,
    code_tree_sha: str,
) -> str:
    value = {
        "scope": ROADMAP_SCOPE,
        "tasks": sorted(tasks),
        "roadmap_sha256": roadmap.digest,
        "mandate_digest": mandate_digest,
        "code_tree_sha256": code_tree_sha,
    }
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _phase_prerequisites(phase: int) -> tuple[int, ...]:
    if phase in {1, 2, 3}:
        return (0,)
    if phase == 4:
        return (1, 2)
    if phase == 5:
        return (4,)
    if phase == 6:
        return (4, 1)
    if phase == 7:
        return (5,)
    return ()


def _phase_complete(roadmap: Roadmap, phase: int) -> bool:
    items = [item for item in roadmap.items if item.phase == phase]
    return bool(items) and all(item.complete for item in items)


def eligible_areas(roadmap: Roadmap) -> set[str]:
    """Return unchecked areas whose coarse phase gates are complete."""
    return {
        item.id
        for item in roadmap.items
        if not item.complete
        and all(
            _phase_complete(roadmap, prerequisite)
            for prerequisite in _phase_prerequisites(item.phase)
        )
    }


def pending_task_count(tasks: Iterable[Any]) -> int:
    """Count live queue entries; quarantined terminal history is excluded."""
    return sum(getattr(task, "status", None) in {"queued", "running"} for task in tasks)


def reserved_areas(tasks: Iterable[Any]) -> set[str]:
    """Areas unavailable to a new slice until an explicit retry."""
    quarantined = {
        "queued",
        "running",
        "failed",
        "blocked",
        "interrupted",
        "waiting_external",
        "waiting_human",
    }
    return {
        str(task.area).lower()
        for task in tasks
        if getattr(task, "status", None) in quarantined
    }


def _task_by_area(tasks: Iterable[Any], area: str) -> list[Any]:
    return [
        task
        for task in tasks
        if getattr(task, "area", "").lower() == area
        and getattr(task, "status", None)
        in {
            "queued",
            "running",
            "failed",
            "blocked",
            "interrupted",
            "waiting_external",
            "waiting_human",
        }
    ]


def validate_enqueue(
    roadmap: Roadmap,
    tasks: Iterable[Any],
    task_id: str,
    area: str,
    *,
    pending_limit: int = ROADMAP_PENDING_LIMIT,
) -> str:
    canonical = area.lower()
    if not _ID_RE.fullmatch(canonical) or canonical not in roadmap.by_id:
        raise RoadmapError("roadmap area is not a tracked checklist ID")
    if roadmap.by_id[canonical].complete:
        raise RoadmapError("roadmap checklist is already complete")
    if canonical not in eligible_areas(roadmap):
        raise RoadmapError("roadmap area prerequisites are incomplete")
    if pending_task_count(tasks) >= pending_limit:
        raise RoadmapError("roadmap queue is full")
    if _task_by_area(tasks, canonical):
        raise RoadmapError(
            "roadmap area is already queued or quarantined; retry it explicitly"
        )
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,100}", task_id):
        raise RoadmapError("roadmap task ID is invalid")
    return canonical


def validate_task_dependency(task: Any, tasks: Iterable[Any]) -> None:
    dependency = getattr(task, "depends_on", None)
    if dependency is None:
        return
    match = next((item for item in tasks if item.id == dependency), None)
    if match is None or match.status != "completed":
        raise RoadmapError("roadmap dependency is not completed")


def roadmap_prompt(area: str, item: ChecklistItem, mandate: str | None) -> str:
    mandate_text = mandate or (
        "MANDATE STATUS: tracked docs/research-mandate.json is missing or unreadable."
    )
    return (
        "Scope: investment-roadmap. Work on exactly one bounded checklist slice.\n"
        f"Checklist area: {area}\nChecklist text: {item.text}\n"
        "The tracked Markdown checkbox is authoritative for the full checklist; a "
        "bounded slice may complete while that checkbox remains unchecked. Update "
        "only this checklist item when its full conditions are actually complete. A "
        "slice completion never marks the whole phase complete. Missing benchmark, "
        "future observation data, or another required input must be reported as "
        "blocked and must never be presented as success.\n"
        "Required boundaries: use worktree Luna/review/local-main integrated checks, "
        "evidence, handoff, and cleanup. Do not activate PAPER or live trading, "
        "change an operating ledger, submit orders, push a remote, change services "
        "or configuration, or create a new task tracker/schema.\n"
        f"{DEVELOPMENT_DELIVERY_POLICY}\n"
        f"Current tracked mandate:\n{mandate_text}"
    )


def roadmap_planner_context(
    roadmap: Roadmap, tasks: list[tuple[str, str, str | None]], eligible: set[str]
) -> str:
    return (
        "Scope: investment-roadmap. Select at most one eligible unchecked checklist "
        "slice. R1/R2/R3 independently require completed R0; R4 requires completed "
        "R1 and R2 but does not require R3; R5 and R6 require R4; R6 also records "
        "R1; R7 requires R5 and its task must state any required Korean-data or "
        "approval gate (R7-04 requires a separate decision; R7-05 forbids real "
        "orders). A failed, blocked, or interrupted area stays quarantined "
        "until the same task ID is explicitly retried.\n"
        f"Eligible areas: {sorted(eligible)}\n"
        f"Roadmap SHA-256: {roadmap.digest}\n"
        f"Research snapshot: {json.dumps(tasks, sort_keys=True)}\n"
        f"{DEVELOPMENT_DELIVERY_POLICY}\n"
        "Do not activate PAPER/live trading, alter operating ledgers/services, push "
        "remotely, or claim success when benchmark/future data is missing. Return "
        "one bounded proposal or a waiting result."
    )


def validate_roadmap_completion(
    roadmap: Roadmap,
    task: Any,
    completion: Any,
) -> None:
    area = str(getattr(task, "area", "")).lower()
    item = roadmap.by_id.get(area)
    if item is None:
        raise RoadmapError("completion area is not a tracked checklist ID")
    followup = getattr(completion, "followup", None)
    if followup is not None:
        followup_area = str(followup.area).lower()
        if followup_area not in eligible_areas(roadmap):
            raise RoadmapError("roadmap followup area is not eligible")


def validate_planner_area(roadmap: Roadmap, area: str, tasks: Iterable[Any]) -> str:
    canonical = area.lower()
    if canonical not in eligible_areas(roadmap):
        raise RoadmapError("planner proposed an ineligible roadmap area")
    if _task_by_area(tasks, canonical):
        raise RoadmapError("planner proposed an already used roadmap area")
    return canonical
