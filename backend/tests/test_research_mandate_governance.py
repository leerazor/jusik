from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from jusik.research_mandate_governance import (
    MandateGovernanceError,
    validate_dispatch_gate,
    validate_mandate,
)

DOCS = (
    "research-mandate.json",
    "research-mandate.md",
    "market-research-mandate.sha256",
    "market-research.md",
    "investment-development-roadmap.md",
)


def _repo(tmp_path: Path) -> Path:
    source = Path(__file__).parents[2] / "docs"
    docs = tmp_path / "docs"
    docs.mkdir()
    for name in DOCS:
        shutil.copyfile(source / name, docs / name)
    return tmp_path


def _rewrite_json(repo: Path, mutate: Callable[[dict[str, Any]], None]) -> None:
    path = repo / "docs" / "research-mandate.json"
    raw = path.read_text(encoding="utf-8")
    payload = json.loads(raw)
    mutate(payload)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _refresh_json_hash(repo: Path) -> None:
    path = repo / "docs" / "research-mandate.json"
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    marker = repo / "docs" / "research-mandate.md"
    text = marker.read_text(encoding="utf-8")
    import re

    text = re.sub(r"(?<=SHA-256은 `)[0-9a-f]{64}", digest, text, count=1)
    marker.write_text(text, encoding="utf-8")
    hashes = repo / "docs" / "market-research-mandate.sha256"
    lines = []
    for line in hashes.read_text(encoding="utf-8").splitlines():
        lines.append(
            f"docs/research-mandate.json {digest}"
            if line.startswith("docs/research-mandate.json ")
            else line
        )
    hashes.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_validates_additive_governance_and_disabled_dispatch(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    result = validate_mandate(repo)

    assert result.dispatch_enabled is False
    with pytest.raises(MandateGovernanceError, match="disabled"):
        validate_dispatch_gate(repo)


def test_rejects_duplicate_json_keys(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    path = repo / "docs" / "research-mandate.json"
    path.write_text('{"recorded_at": 1, "recorded_at": 2}\n', encoding="utf-8")

    with pytest.raises(MandateGovernanceError, match="invalid"):
        validate_mandate(repo)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value["governance"].update({"schema_version": True}),
        lambda value: value["governance"].update({"policy_version": "other"}),
        lambda value: value["governance"].update({"dispatch_enabled": 0}),
        lambda value: value["governance"]["candidate_policy"].update(
            {"max_preregistered_candidates": 4}
        ),
        lambda value: value["governance"]["objective"].update(
            {"primary_metrics": ["CAGR"]}
        ),
    ],
)
def test_rejects_wrong_governance_constants(
    tmp_path: Path, mutate: Callable[[dict[str, Any]], None]
) -> None:
    repo = _repo(tmp_path)
    _rewrite_json(repo, mutate)

    with pytest.raises(MandateGovernanceError, match="invalid"):
        validate_mandate(repo)


def test_rejects_stale_digest_and_roadmap_policy_marker(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _rewrite_json(
        repo, lambda value: value["governance"].update({"dispatch_enabled": True})
    )
    with pytest.raises(MandateGovernanceError, match="invalid"):
        validate_mandate(repo)

    _refresh_json_hash(repo)
    roadmap = repo / "docs" / "investment-development-roadmap.md"
    roadmap.write_text(
        roadmap.read_text(encoding="utf-8").replace(
            "investment-roadmap-governance-v1", "other-policy"
        ),
        encoding="utf-8",
    )
    with pytest.raises(MandateGovernanceError, match="invalid"):
        validate_mandate(repo)


def test_rejects_non_regular_markdown_file(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    marker = repo / "docs" / "research-mandate.md"
    marker.unlink()
    marker.symlink_to(repo / "docs" / "market-research.md")

    with pytest.raises(MandateGovernanceError, match="invalid"):
        validate_mandate(repo)
