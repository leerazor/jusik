from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from jusik.research_r7_isolation import (
    CHILDREN,
    create_r7_isolation_workspace,
    workspace_manifest_sha256,
)


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def test_workspace_is_new_disjoint_and_paper_only(tmp_path: Path) -> None:
    retrospective = tmp_path / "retrospective"
    retrospective.mkdir()
    source = retrospective / "result.json"
    source.write_bytes(b"historical")
    before = source.read_bytes()

    workspace = create_r7_isolation_workspace(
        tmp_path / "future",
        retrospective_paths=(retrospective, source),
        source_identities={"retrospective": _digest(before)},
    )

    assert tuple(path.name for path in (
        workspace.market_data,
        workspace.config,
        workspace.database,
        workspace.artifacts,
    )) == CHILDREN
    assert all(path.is_dir() for path in (
        workspace.market_data,
        workspace.config,
        workspace.database,
        workspace.artifacts,
    ))
    assert source.read_bytes() == before
    assert workspace_manifest_sha256(workspace) == _digest(
        workspace.manifest.read_bytes()
    )
    payload = workspace.manifest.read_text(encoding="utf-8")
    assert '"paper_only": true' in payload
    assert '"automatic_promotion_eligible": false' in payload
    assert '"retrospective_write_access": false' in payload


def test_workspace_rejects_retrospective_overlap(tmp_path: Path) -> None:
    retrospective = tmp_path / "retrospective"
    retrospective.mkdir()
    root = retrospective / "future"
    with pytest.raises(ValueError, match="overlaps"):
        create_r7_isolation_workspace(
            root,
            retrospective_paths=(retrospective,),
            source_identities={"retrospective": "a" * 64},
        )


def test_workspace_rejects_reuse_symlink_and_bad_identity(tmp_path: Path) -> None:
    retrospective = tmp_path / "retrospective"
    retrospective.mkdir()
    target = tmp_path / "future"
    target.mkdir()
    with pytest.raises(ValueError, match="new"):
        create_r7_isolation_workspace(
            target,
            retrospective_paths=(retrospective,),
            source_identities={"retrospective": "a" * 64},
        )

    link = tmp_path / "link"
    link.symlink_to(retrospective, target_is_directory=True)
    with pytest.raises(ValueError, match="new"):
        create_r7_isolation_workspace(
            link,
            retrospective_paths=(retrospective,),
            source_identities={"retrospective": "a" * 64},
        )

    with pytest.raises(ValueError, match="lowercase SHA-256"):
        create_r7_isolation_workspace(
            tmp_path / "bad",
            retrospective_paths=(retrospective,),
            source_identities={"retrospective": "A" * 64},
        )


def test_workspace_rejects_missing_retrospective_path(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unavailable"):
        create_r7_isolation_workspace(
            tmp_path / "future",
            retrospective_paths=(tmp_path / "missing",),
            source_identities={"retrospective": "a" * 64},
        )
