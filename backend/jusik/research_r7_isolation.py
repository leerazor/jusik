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


def _validate_parent_chain(path: Path) -> None:
    """Require an existing, non-symlink parent chain before creating root."""

    parent = path.parent
    if not parent.exists() or not parent.is_dir():
        raise ValueError(f"workspace parent is unavailable: {parent}")
    current = parent
    while True:
        if current.is_symlink():
            raise ValueError(f"workspace parent must not contain a symlink: {current}")
        ancestor = current.parent
        if ancestor == current:
            return
        if not ancestor.exists():
            raise ValueError(f"workspace parent is unavailable: {ancestor}")
        current = ancestor


def _open_directory_chain(path: Path) -> int:
    """Open every directory component without following an ancestor symlink."""
    absolute = Path(os.path.abspath(path))
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    descriptor = os.open(os.sep, flags)
    try:
        for component in absolute.parts[1:]:
            child = os.open(component, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _sha256_path(path: Path) -> str:
    """Hash a regular file or a deterministic tree without following symlinks."""

    digest = hashlib.sha256()
    if path.is_file() and not path.is_symlink():
        digest.update(path.read_bytes())
        return digest.hexdigest()
    if not path.is_dir() or path.is_symlink():
        raise ValueError(f"source path is not a regular file or directory: {path}")
    for child in sorted(path.rglob("*")):
        if child.is_symlink():
            raise ValueError(f"source tree contains a symlink: {child}")
        if child.is_file():
            relative = child.relative_to(path).as_posix().encode("utf-8")
            digest.update(len(relative).to_bytes(8, "big"))
            digest.update(relative)
            body = child.read_bytes()
            digest.update(len(body).to_bytes(8, "big"))
            digest.update(body)
    return digest.hexdigest()


def _write_manifest_at(
    directory_fd: int, name: str, payload: dict[str, object]
) -> None:
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    descriptor = os.open(
        name,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
        0o600,
        dir_fd=directory_fd,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        try:
            os.unlink(name, dir_fd=directory_fd)
        except FileNotFoundError:
            pass
        raise


def create_r7_isolation_workspace(
    root: Path,
    *,
    retrospective_paths: tuple[Path, ...],
    source_identities: dict[str, str],
    source_hashes: dict[Path, str],
) -> R7IsolationWorkspace:
    """Create one empty R7 workspace without touching retrospective paths.

    ``root`` must be new and disjoint from every retrospective path.  The
    manifest stores only relative child names and caller-supplied content
    identities; it never copies or mutates source artifacts.
    """

    if not retrospective_paths:
        raise ValueError("retrospective paths are required")
    if not isinstance(source_identities, dict) or not source_identities:
        raise ValueError("source identities are required")
    if set(source_hashes) != set(retrospective_paths):
        raise ValueError("source hashes must cover every retrospective path")
    if any(
        not isinstance(key, str)
        or not key
        or not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
        for key, value in source_identities.items()
    ):
        raise ValueError("source identities must be lowercase SHA-256 values")
    if any(
        not isinstance(digest, str)
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
        for digest in source_hashes.values()
    ):
        raise ValueError("source hashes must be lowercase SHA-256 values")
    if root.exists() or root.is_symlink():
        raise ValueError("workspace root must be new and not a symlink")
    _validate_parent_chain(root)
    resolved_root = _resolved(root)
    resolved_sources = tuple(
        _resolved(path, require_exists=True) for path in retrospective_paths
    )
    if any(_overlaps(resolved_root, source) for source in resolved_sources):
        raise ValueError("workspace overlaps a retrospective path")
    for path, expected in source_hashes.items():
        if _sha256_path(path) != expected:
            raise ValueError(f"retrospective source hash mismatch: {path}")

    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    parent_fd = _open_directory_chain(root.parent)
    root_fd: int | None = None
    try:
        os.mkdir(root.name, mode=0o700, dir_fd=parent_fd)
        root_fd = os.open(root.name, directory_flags, dir_fd=parent_fd)
        children = {name: root / name for name in CHILDREN}
        for name in CHILDREN:
            os.mkdir(name, mode=0o700, dir_fd=root_fd)
        manifest = root / "workspace.json"
        payload: dict[str, object] = {
            "schema_version": SCHEMA_VERSION,
            "mode": WORKSPACE_MODE,
            "paper_only": True,
            "automatic_promotion_eligible": False,
            "retrospective_write_access": False,
            "source_identities": dict(sorted(source_identities.items())),
            "source_hashes": {
                str(path.resolve(strict=True)): digest
                for path, digest in sorted(
                    source_hashes.items(), key=lambda item: str(item[0])
                )
            },
            "paths": {name: name for name in (*CHILDREN, "workspace.json")},
        }
        _write_manifest_at(root_fd, "workspace.json", payload)
        os.fsync(root_fd)
        return R7IsolationWorkspace(
            root=root,
            market_data=children["market-data"],
            config=children["config"],
            database=children["database"],
            artifacts=children["artifacts"],
            manifest=manifest,
        )
    except BaseException:
        # Remove only entries created through the held directory descriptors.
        if root_fd is not None:
            for name in ("workspace.json", *CHILDREN):
                try:
                    os.unlink(name, dir_fd=root_fd)
                except IsADirectoryError:
                    os.rmdir(name, dir_fd=root_fd)
                except FileNotFoundError:
                    pass
            os.close(root_fd)
            root_fd = None
        try:
            os.rmdir(root.name, dir_fd=parent_fd)
        except FileNotFoundError:
            pass
        raise
    finally:
        if root_fd is not None:
            os.close(root_fd)
        os.close(parent_fd)


def workspace_manifest_sha256(workspace: R7IsolationWorkspace) -> str:
    """Return the manifest identity without changing the workspace."""

    return hashlib.sha256(workspace.manifest.read_bytes()).hexdigest()
