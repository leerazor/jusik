"""Fail-closed workspace contract for the R7 isolated evaluation.

This module only prepares an empty, newly-created workspace.  It does not run a
strategy, collect data, activate PAPER, or write to the retrospective source.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

SCHEMA_VERSION = 1
WORKSPACE_MODE = "r7_isolated"
CHILDREN = ("market-data", "config", "database", "artifacts")


@dataclass(frozen=True)
class R7IsolationWorkspace:
    """Paths belonging exclusively to one future R7 evaluation."""

    root: Path
    market_data: Path
    config: Path
    database: Path
    artifacts: Path
    manifest: Path


def _resolved(path: Path, *, require_exists: bool = False) -> Path:
    if path.is_symlink():
        raise ValueError(f"workspace path must not be a symlink: {path}")
    if require_exists and not path.exists():
        raise ValueError(f"retrospective path is unavailable: {path}")
    return path.resolve(strict=False)


def _overlaps(left: Path, right: Path) -> bool:
    return left == right or left in right.parents or right in left.parents


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_manifest(path: Path, payload: dict[str, object]) -> None:
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
        0o600,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def create_r7_isolation_workspace(
    root: Path,
    *,
    retrospective_paths: tuple[Path, ...],
    source_identities: dict[str, str],
) -> R7IsolationWorkspace:
    """Create one empty R7 workspace without touching retrospective paths.

    ``root`` must be new and disjoint from every retrospective path.  The
    manifest stores only relative child names and caller-supplied content
    identities; it never copies or mutates source artifacts.
    """

    if not isinstance(source_identities, dict) or not source_identities:
        raise ValueError("source identities are required")
    if any(
        not isinstance(key, str)
        or not key
        or not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
        for key, value in source_identities.items()
    ):
        raise ValueError("source identities must be lowercase SHA-256 values")
    if root.exists() or root.is_symlink():
        raise ValueError("workspace root must be new and not a symlink")
    resolved_root = _resolved(root)
    resolved_sources = tuple(
        _resolved(path, require_exists=True) for path in retrospective_paths
    )
    if any(_overlaps(resolved_root, source) for source in resolved_sources):
        raise ValueError("workspace overlaps a retrospective path")

    root.mkdir(parents=True, exist_ok=False)
    try:
        children = {name: root / name for name in CHILDREN}
        for child in children.values():
            child.mkdir()
        manifest = root / "workspace.json"
        payload: dict[str, object] = {
            "schema_version": SCHEMA_VERSION,
            "mode": WORKSPACE_MODE,
            "paper_only": True,
            "automatic_promotion_eligible": False,
            "retrospective_write_access": False,
            "source_identities": dict(sorted(source_identities.items())),
            "paths": {name: name for name in (*CHILDREN, "workspace.json")},
        }
        _write_manifest(manifest, payload)
        _fsync_directory(root)
        return R7IsolationWorkspace(
            root=root,
            market_data=children["market-data"],
            config=children["config"],
            database=children["database"],
            artifacts=children["artifacts"],
            manifest=manifest,
        )
    except BaseException:
        # This is a newly-created, private workspace.  Remove only its known
        # empty/manifest children so a failed setup cannot be reused silently.
        for path in (root / "workspace.json", *(root / name for name in CHILDREN)):
            if path.is_file() or path.is_symlink():
                path.unlink(missing_ok=True)
            elif path.is_dir():
                path.rmdir()
        root.rmdir()
        raise


def workspace_manifest_sha256(workspace: R7IsolationWorkspace) -> str:
    """Return the manifest identity without changing the workspace."""

    return hashlib.sha256(workspace.manifest.read_bytes()).hexdigest()
