from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DEFAULT_HISTORY_DIR = Path.home() / ".local/share/jusik/research-history"
DEFAULT_HISTORY_DB = Path.home() / ".local/share/jusik/research-history-journal.db"
HEX64 = r"^[a-f0-9]{64}$"


class HistoryCheck(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str = Field(min_length=1, max_length=160)
    result: str = Field(min_length=1, max_length=500)
    evidence_id: str = Field(min_length=1, max_length=160)


class HistoryArtifactReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    artifact_id: str = Field(pattern=HEX64)
    sha256: str = Field(pattern=HEX64)


class HistoryArtifact(HistoryArtifactReference):
    title: str = Field(min_length=1, max_length=160)
    filename: str = Field(pattern=r"^[a-f0-9]{64}\.md$")

    @model_validator(mode="after")
    def identity_matches_filename(self) -> HistoryArtifact:
        if self.filename != f"{self.sha256}.md" or self.artifact_id != self.sha256:
            raise ValueError("History artifacts must use their SHA-256 as identity.")
        return self


class HistoryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str = Field(min_length=1, max_length=160)
    occurred_at: datetime | None
    recorded_at: datetime
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=2000)
    category: Literal["research", "development", "forward", "system"]
    outcome: str = Field(min_length=1, max_length=80)
    run_ids: list[str] = Field(default_factory=list, max_length=20)
    checks: list[HistoryCheck] = Field(default_factory=list, max_length=50)
    artifacts: list[HistoryArtifactReference] = Field(
        default_factory=list, max_length=50
    )
    supersedes: str | None = Field(default=None, max_length=160)

    @field_validator("occurred_at", "recorded_at")
    @classmethod
    def aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("History timestamps must be timezone-aware.")
        return value


class PublicHistorySeed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal[1, "1"]
    artifacts: list[HistoryArtifact]
    entries: list[HistoryEntry]

    @model_validator(mode="after")
    def references_exist(self) -> PublicHistorySeed:
        known = {item.artifact_id: item.sha256 for item in self.artifacts}
        if len(known) != len(self.artifacts):
            raise ValueError("History artifact ids must be unique.")
        for entry in self.entries:
            for reference in entry.artifacts:
                if known.get(reference.artifact_id) != reference.sha256:
                    raise ValueError("History entry references an unknown artifact.")
        if len({entry.id for entry in self.entries}) != len(self.entries):
            raise ValueError("History entry ids must be unique.")
        return self


class HistoryPage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    items: list[HistoryEntry]
    artifacts: list[HistoryArtifact]
    next_cursor: str | None


def import_public_history(seed_path: Path, artifacts_dir: Path, target: Path) -> None:
    seed = PublicHistorySeed.model_validate_json(seed_path.read_text(encoding="utf-8"))
    existing_path = target / "seed.json"
    if existing_path.is_file():
        existing = PublicHistorySeed.model_validate_json(
            existing_path.read_text(encoding="utf-8")
        )
        incoming_entries = {item.id: item for item in seed.entries}
        incoming_artifacts = {item.artifact_id: item for item in seed.artifacts}
        if any(incoming_entries.get(item.id) != item for item in existing.entries):
            raise ValueError("Published history entries cannot be removed or changed.")
        if any(
            incoming_artifacts.get(item.artifact_id) != item
            for item in existing.artifacts
        ):
            raise ValueError(
                "Published history artifacts cannot be removed or changed."
            )
    stage = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    (stage / "artifacts").mkdir()
    for artifact in seed.artifacts:
        source = artifacts_dir / artifact.filename
        if (
            source.is_symlink()
            or not source.is_file()
            or source.resolve().parent != artifacts_dir.resolve()
        ):
            raise ValueError("History artifact path is unsafe or missing.")
        content = source.read_bytes()
        if hashlib.sha256(content).hexdigest() != artifact.sha256:
            raise ValueError("History artifact digest mismatch.")
        shutil.copyfile(source, stage / "artifacts" / artifact.filename)
    (stage / "seed.json").write_text(
        seed.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    if target.exists():
        backup = target.with_name(f".{target.name}.old")
        if backup.exists():
            shutil.rmtree(backup)
        os.replace(target, backup)
        os.replace(stage, target)
        shutil.rmtree(backup)
    else:
        os.replace(stage, target)


class HistoryRepository:
    def __init__(
        self, root: Path = DEFAULT_HISTORY_DIR, db_path: Path | None = None
    ) -> None:
        self.root = root
        self.db_path = db_path or (
            DEFAULT_HISTORY_DB
            if root == DEFAULT_HISTORY_DIR
            else root.parent / "research-history-journal.db"
        )
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS history_journal (
                id TEXT PRIMARY KEY, recorded_at TEXT NOT NULL,
                entry_json TEXT NOT NULL, sort_at TEXT)"""
            )
            columns = {
                str(row["name"])
                for row in connection.execute(
                    "PRAGMA table_info(history_journal)"
                ).fetchall()
            }
            if "sort_at" not in columns:
                connection.execute(
                    "ALTER TABLE history_journal ADD COLUMN sort_at TEXT"
                )
            for row in connection.execute(
                "SELECT id, entry_json FROM history_journal WHERE sort_at IS NULL"
            ).fetchall():
                entry = HistoryEntry.model_validate_json(row["entry_json"])
                connection.execute(
                    "UPDATE history_journal SET sort_at=? WHERE id=?",
                    (
                        (entry.occurred_at or entry.recorded_at)
                        .astimezone(UTC)
                        .isoformat(),
                        entry.id,
                    ),
                )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def seed(self) -> PublicHistorySeed:
        try:
            return PublicHistorySeed.model_validate_json(
                (self.root / "seed.json").read_text(encoding="utf-8")
            )
        except OSError:
            return PublicHistorySeed(schema_version=1, artifacts=[], entries=[])

    def append(self, entry: HistoryEntry) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                """INSERT OR IGNORE INTO history_journal
                (id, recorded_at, entry_json, sort_at) VALUES (?, ?, ?, ?)""",
                (
                    entry.id,
                    entry.recorded_at.astimezone(UTC).isoformat(),
                    entry.model_dump_json(),
                    (entry.occurred_at or entry.recorded_at)
                    .astimezone(UTC)
                    .isoformat(),
                ),
            )
        return cursor.rowcount == 1

    def record(
        self,
        *,
        identity: str,
        title: str,
        summary: str,
        category: Literal["research", "development", "forward", "system"],
        outcome: str,
        occurred_at: datetime | None = None,
        run_ids: list[str] | None = None,
    ) -> bool:
        recorded = datetime.now(UTC)
        return self.append(
            HistoryEntry(
                id=identity,
                occurred_at=occurred_at,
                recorded_at=recorded,
                title=title,
                summary=summary,
                category=category,
                outcome=outcome,
                run_ids=run_ids or [],
            )
        )

    def page(self, cursor: str | None = None, limit: int = 50) -> HistoryPage:
        seed = self.seed()
        cursor_key: tuple[str, str] | None = None
        if cursor:
            seed_cursor = next(
                (item for item in seed.entries if item.id == cursor), None
            )
            if seed_cursor is not None:
                cursor_key = (
                    (seed_cursor.occurred_at or seed_cursor.recorded_at)
                    .astimezone(UTC)
                    .isoformat(),
                    seed_cursor.id,
                )
            else:
                with self._connect() as connection:
                    cursor_row = connection.execute(
                        "SELECT sort_at, id FROM history_journal WHERE id=?",
                        (cursor,),
                    ).fetchone()
                if cursor_row is None:
                    return HistoryPage(
                        items=[], artifacts=seed.artifacts, next_cursor=None
                    )
                cursor_key = (str(cursor_row["sort_at"]), str(cursor_row["id"]))
        bounded = min(max(limit, 1), 100)
        with self._connect() as connection:
            if cursor_key is None:
                rows = connection.execute(
                    """SELECT entry_json FROM history_journal
                    ORDER BY sort_at DESC, id DESC LIMIT ?""",
                    (bounded + 1,),
                ).fetchall()
            else:
                rows = connection.execute(
                    """SELECT entry_json FROM history_journal
                    WHERE sort_at<? OR (sort_at=? AND id<?)
                    ORDER BY sort_at DESC, id DESC LIMIT ?""",
                    (cursor_key[0], cursor_key[0], cursor_key[1], bounded + 1),
                ).fetchall()
        combined = [
            *[
                item
                for item in seed.entries
                if cursor_key is None
                or (
                    (item.occurred_at or item.recorded_at).astimezone(UTC).isoformat(),
                    item.id,
                )
                < cursor_key
            ],
            *(HistoryEntry.model_validate_json(row["entry_json"]) for row in rows),
        ]
        combined.sort(
            key=lambda item: (
                (item.occurred_at or item.recorded_at).astimezone(UTC),
                item.id,
            ),
            reverse=True,
        )
        items = combined[:bounded]
        next_cursor = items[-1].id if len(combined) > bounded and items else None
        return HistoryPage(
            items=items, artifacts=seed.artifacts, next_cursor=next_cursor
        )

    def artifact_path(self, artifact_id: str) -> tuple[Path, HistoryArtifact]:
        artifact = next(
            (item for item in self.seed().artifacts if item.artifact_id == artifact_id),
            None,
        )
        if artifact is None:
            raise FileNotFoundError(artifact_id)
        path = self.root / "artifacts" / artifact.filename
        if (
            path.is_symlink()
            or not path.is_file()
            or path.resolve().parent != (self.root / "artifacts").resolve()
        ):
            raise FileNotFoundError(artifact_id)
        if hashlib.sha256(path.read_bytes()).hexdigest() != artifact.sha256:
            raise ValueError("History artifact changed after import.")
        return path, artifact


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import validated public research history"
    )
    parser.add_argument("command", choices=["import"])
    parser.add_argument("--seed", type=Path, required=True)
    parser.add_argument("--artifacts-dir", type=Path, required=True)
    parser.add_argument("--target", type=Path, default=DEFAULT_HISTORY_DIR)
    args = parser.parse_args()
    import_public_history(args.seed, args.artifacts_dir, args.target)


if __name__ == "__main__":
    main()
