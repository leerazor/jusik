"""Read-only audit of synthetic future-observation revision links."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .research_future_observation_replay import ReplayResult, SyntheticFixture, replay

MAX_BYTES = 4 * 1024 * 1024
MAX_ITEMS = 10_000


class RevisionLink(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str
    observation_id: str
    raw_sha256: str
    parent_sha256: str
    effective_at: str


class RevisionDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    synthetic: Literal[True]
    revision_links: list[RevisionLink] = Field(default_factory=list)

    @field_validator("synthetic", mode="before")
    @classmethod
    def require_literal_true(cls, value: object) -> object:
        if value is not True:
            raise ValueError("revision document must set synthetic to literal true")
        return value


class RevisionDiagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    link_index: int | None = None
    source_id: str | None = None
    observation_id: str | None = None
    raw_sha256: str | None = None
    parent_sha256: str | None = None
    detail: str | None = None


class _DiagnosticFields(TypedDict, total=False):
    link_index: int | None
    source_id: str | None
    observation_id: str | None
    raw_sha256: str | None
    parent_sha256: str | None


class RevisionAuditResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    synthetic: Literal[True] = True
    registered: Literal[False] = False
    accepted_nav: Literal[False] = False
    evaluation_inputs_complete: Literal[False] = False
    selection_policy: Literal["unresolved"] = "unresolved"
    temporal_policy: Literal["unresolved"] = "unresolved"
    replay: ReplayResult
    revision_links: list[RevisionLink]
    diagnostics: list[RevisionDiagnostic]
    counts: dict[str, int]


def _time_diagnostic(value: str) -> bool:
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.utcoffset() is None:
            return True
        parsed.astimezone(UTC)
        return False
    except (TypeError, ValueError, OverflowError):
        return True


def audit(
    receipt_fixture: SyntheticFixture | dict[str, object],
    revision_document: RevisionDocument | dict[str, object],
) -> RevisionAuditResult:
    """Audit links without changing fixture, receipts, or declarations."""
    fixture = (
        receipt_fixture
        if isinstance(receipt_fixture, SyntheticFixture)
        else SyntheticFixture.model_validate(receipt_fixture)
    )
    document = (
        revision_document
        if isinstance(revision_document, RevisionDocument)
        else RevisionDocument.model_validate(revision_document)
    )
    if len(fixture.observations) > MAX_ITEMS:
        raise ValueError("fixture exceeds 10000 observations")
    if len(document.revision_links) > MAX_ITEMS:
        raise ValueError("revision-links exceeds 10000 links")
    replay_result = replay(fixture)
    observations: set[tuple[str, str, str]] = set()
    hashes_by_pair: dict[tuple[str, str], set[str]] = {}
    all_hashes: dict[str, set[tuple[str, str]]] = {}
    for result in replay_result.observations:
        for receipt in result.receipts:
            digest = receipt.raw_sha256
            identity = (result.source_id, result.observation_id, digest)
            observations.add(identity)
            hashes_by_pair.setdefault(identity[:2], set()).add(digest)
            all_hashes.setdefault(digest, set()).add(identity[:2])

    diagnostics: list[RevisionDiagnostic] = []
    declarations: list[RevisionLink] = []
    child_parents: dict[tuple[str, str, str], set[str]] = {}
    seen_declarations: set[tuple[str, str, str, str, str]] = set()
    for index, link in enumerate(document.revision_links):
        declarations.append(link)
        child = (link.source_id, link.observation_id, link.raw_sha256)
        child_parents.setdefault(child, set()).add(link.parent_sha256)
        base: _DiagnosticFields = {
            "link_index": index,
            "source_id": link.source_id,
            "observation_id": link.observation_id,
            "raw_sha256": link.raw_sha256,
            "parent_sha256": link.parent_sha256,
        }
        if link.raw_sha256 not in hashes_by_pair.get(child[:2], set()):
            diagnostics.append(RevisionDiagnostic(code="hash_mismatch", **base))
            for source_id, observation_id in sorted(
                all_hashes.get(link.raw_sha256, set())
            ):
                if source_id != link.source_id:
                    diagnostics.append(
                        RevisionDiagnostic(
                            code="cross_source_child", detail=source_id, **base
                        )
                    )
                if observation_id != link.observation_id:
                    diagnostics.append(
                        RevisionDiagnostic(
                            code="cross_observation_child",
                            detail=observation_id,
                            **base,
                        )
                    )
        parent = (link.source_id, link.observation_id, link.parent_sha256)
        if parent not in observations:
            diagnostics.append(RevisionDiagnostic(code="missing_parent", **base))
            locations = sorted(all_hashes.get(link.parent_sha256, set()))
            if len(locations) > 1:
                diagnostics.append(
                    RevisionDiagnostic(
                        code="ambiguous_parent",
                        detail=str(locations),
                        **base,
                    )
                )
            for source_id, observation_id in locations:
                if source_id != link.source_id:
                    diagnostics.append(
                        RevisionDiagnostic(
                            code="cross_source_parent", detail=source_id, **base
                        )
                    )
                if observation_id != link.observation_id:
                    diagnostics.append(
                        RevisionDiagnostic(
                            code="cross_observation_parent",
                            detail=observation_id,
                            **base,
                        )
                    )
            if len(link.parent_sha256) != 64 or any(
                c not in "0123456789abcdefABCDEF" for c in link.parent_sha256
            ):
                diagnostics.append(
                    RevisionDiagnostic(
                        code="hash_mismatch", detail="parent_sha256", **base
                    )
                )
        if link.parent_sha256 == link.raw_sha256:
            diagnostics.append(RevisionDiagnostic(code="self_link", **base))
        declaration_key = (
            link.source_id,
            link.observation_id,
            link.raw_sha256,
            link.parent_sha256,
            link.effective_at,
        )
        if declaration_key in seen_declarations:
            diagnostics.append(RevisionDiagnostic(code="duplicate_link", **base))
        seen_declarations.add(declaration_key)
        if _time_diagnostic(link.effective_at):
            diagnostics.append(
                RevisionDiagnostic(
                    code="effective_at_invalid", detail=link.effective_at, **base
                )
            )

    for child, parents in child_parents.items():
        if len(parents) > 1:
            diagnostics.append(
                RevisionDiagnostic(
                    code="ambiguous_parent",
                    source_id=child[0],
                    observation_id=child[1],
                    raw_sha256=child[2],
                    detail=str(sorted(parents)),
                )
            )
    # Mark every member of every directed cycle, iteratively, without recursion.
    edges: dict[tuple[str, str, str], list[tuple[str, str, str]]] = {
        child: [
            (child[0], child[1], parent)
            for parent in sorted(parents)
            if (child[0], child[1], parent) in observations and child in observations
        ]
        for child, parents in child_parents.items()
        if child in observations
    }
    nodes = set(edges)
    nodes.update(neighbor for neighbors in edges.values() for neighbor in neighbors)
    reverse: dict[tuple[str, str, str], list[tuple[str, str, str]]] = {
        node: [] for node in nodes
    }
    for node, neighbors in edges.items():
        for neighbor in neighbors:
            reverse[neighbor].append(node)
    finish: list[tuple[str, str, str]] = []
    visited: set[tuple[str, str, str]] = set()
    for start in sorted(nodes):
        if start in visited:
            continue
        visited.add(start)
        stack: list[tuple[tuple[str, str, str], int]] = [(start, 0)]
        while stack:
            node, offset = stack[-1]
            neighbors = edges.get(node, [])
            if offset == len(neighbors):
                finish.append(node)
                stack.pop()
                continue
            neighbor = neighbors[offset]
            stack[-1] = (node, offset + 1)
            if neighbor not in visited:
                visited.add(neighbor)
                stack.append((neighbor, 0))
    cycles: set[tuple[str, str, str]] = set()
    visited.clear()
    for start in reversed(finish):
        if start in visited:
            continue
        component: set[tuple[str, str, str]] = set()
        stack_nodes: list[tuple[str, str, str]] = [start]
        visited.add(start)
        while stack_nodes:
            node = stack_nodes.pop()
            component.add(node)
            for neighbor in reverse.get(node, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    stack_nodes.append(neighbor)
        if len(component) > 1 or any(node in edges.get(node, []) for node in component):
            cycles.update(component)
    for child in sorted(cycles):
        diagnostics.append(
            RevisionDiagnostic(
                code="cycle_member",
                source_id=child[0],
                observation_id=child[1],
                raw_sha256=child[2],
            )
        )

    diagnostics.sort(
        key=lambda item: (
            item.link_index is None,
            item.link_index or -1,
            item.code,
            item.source_id or "",
            item.observation_id or "",
            item.raw_sha256 or "",
        )
    )
    counts: dict[str, int] = {
        "revision_links": len(declarations),
        "diagnostics": len(diagnostics),
    }
    for diagnostic in diagnostics:
        counts[diagnostic.code] = counts.get(diagnostic.code, 0) + 1
    return RevisionAuditResult(
        replay=replay_result,
        revision_links=declarations,
        diagnostics=diagnostics,
        counts=counts,
    )


def _read_json(path: Path, label: str, limit: int) -> object:
    with path.open("rb") as handle:
        data = handle.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f"{label} exceeds 4 MiB limit")
    return json.loads(data.decode("utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit synthetic revision links")
    parser.add_argument("--fixture", required=True, type=Path)
    parser.add_argument("--revision-links", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    inputs = [args.fixture, args.revision_links]
    try:
        output = (
            args.output / "revision-audit.json" if args.output.is_dir() else args.output
        )
        output_stat = output.stat() if output.exists() else None
        for path in inputs:
            if path.stat().st_ino == (output_stat.st_ino if output_stat else -1):
                raise ValueError("--output aliases an input")
        fixture_data = _read_json(args.fixture, "fixture", MAX_BYTES)
        links_data = _read_json(args.revision_links, "revision-links", MAX_BYTES)
        if not isinstance(fixture_data, dict) or not isinstance(links_data, dict):
            raise ValueError("JSON inputs must be objects")
        if len(fixture_data.get("observations", [])) > MAX_ITEMS:
            raise ValueError("fixture exceeds 10000 observations")
        if len(links_data.get("revision_links", [])) > MAX_ITEMS:
            raise ValueError("revision-links exceeds 10000 links")
        result = audit(fixture_data, links_data)
        payload = (
            json.dumps(
                result.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
            + "\n"
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x", encoding="utf-8") as handle:
            handle.write(payload)
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        TypeError,
        ValueError,
    ) as exc:
        raise SystemExit(f"invalid audit input: {exc}") from exc


if __name__ == "__main__":
    main()
