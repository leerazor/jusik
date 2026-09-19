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


def _tree_digest(path: Path) -> str:
    digest = hashlib.sha256()
    for child in sorted(path.rglob("*")):
        if child.is_file():
            relative = child.relative_to(path).as_posix().encode("utf-8")
            digest.update(len(relative).to_bytes(8, "big"))
            digest.update(relative)
            body = child.read_bytes()
            digest.update(len(body).to_bytes(8, "big"))
            digest.update(body)
    return digest.hexdigest()


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
        source_hashes={
            retrospective: _tree_digest(retrospective),
            source: _digest(before),
        },
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
            source_hashes={retrospective: "a" * 64},
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
            source_hashes={retrospective: "a" * 64},
        )

    link = tmp_path / "link"
    link.symlink_to(retrospective, target_is_directory=True)
    with pytest.raises(ValueError, match="new"):
        create_r7_isolation_workspace(
            link,
            retrospective_paths=(retrospective,),
            source_identities={"retrospective": "a" * 64},
            source_hashes={retrospective: "a" * 64},
        )

    with pytest.raises(ValueError, match="lowercase SHA-256"):
        create_r7_isolation_workspace(
            tmp_path / "bad",
            retrospective_paths=(retrospective,),
            source_identities={"retrospective": "A" * 64},
            source_hashes={retrospective: "a" * 64},
        )


def test_workspace_rejects_missing_retrospective_path(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unavailable"):
        create_r7_isolation_workspace(
            tmp_path / "future",
            retrospective_paths=(tmp_path / "missing",),
            source_identities={"retrospective": "a" * 64},
            source_hashes={tmp_path / "missing": "a" * 64},
        )


def test_workspace_validates_source_hashes_permissions_and_parent_symlinks(
    tmp_path: Path,
) -> None:
    retrospective = tmp_path / "retrospective"
    retrospective.mkdir()
    source = retrospective / "source.json"
    source.write_bytes(b"source")

    with pytest.raises(ValueError, match="hash mismatch"):
        create_r7_isolation_workspace(
            tmp_path / "bad-hash",
            retrospective_paths=(source,),
            source_identities={"source": "a" * 64},
            source_hashes={source: "b" * 64},
        )

    workspace = create_r7_isolation_workspace(
        tmp_path / "private",
        retrospective_paths=(source,),
        source_identities={"source": _digest(b"source")},
        source_hashes={source: _digest(b"source")},
    )
    assert workspace.root.stat().st_mode & 0o777 == 0o700
    assert all(path.stat().st_mode & 0o777 == 0o700 for path in (
        workspace.market_data,
        workspace.config,
        workspace.database,
        workspace.artifacts,
    ))

    parent = tmp_path / "parent"
    parent.mkdir()
    link = tmp_path / "parent-link"
    link.symlink_to(parent, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        create_r7_isolation_workspace(
            link / "future",
            retrospective_paths=(source,),
            source_identities={"source": _digest(b"source")},
            source_hashes={source: _digest(b"source")},
        )
