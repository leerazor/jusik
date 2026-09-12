"""Reproduce coincident signal timestamp anomaly minutes and episodes."""

# The compact aggregate expressions mirror the frozen independent replay schema.
# ruff: noqa: E501

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import sqlite3
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from jusik.research_signal_timestamp_forensics import (
    DATE,
    DB_RELATIVE,
    NOW,
    _load_calendar,
    _parse_observations,
    _fingerprint,
    _validate_archive,
)
from jusik.research_universe_data import REGISTRY

ANOMALIES_RELATIVE = Path("analysis/anomalies.csv")
REPLAY_RELATIVE = Path("independent-replay.json")
ANOMALIES_SHA256 = "bcecc8f53e4b9d665db02c51f5f7d7bedf09b47dbacd96f243f9ee090f7f17bc"
REPLAY_SHA256 = "7715fab67f1b6c5b780ff4d313ae8dc4029ab8302d54ab2f33cf3eac838c10af"
MANIFEST_NAMES = ("manifest.json", "precleanup-manifest.json")
FUTURE_LIMIT_US = -2_000_000
STALE_LIMIT_US = 15_000_000


class EpisodesError(ValueError):
    """Raised when the immutable evidence or its contents are unsafe."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _minute(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    return parsed.replace(second=0, microsecond=0).isoformat().replace("+00:00", "Z")


def _input_paths(archive: Path) -> tuple[Path, Path]:
    return archive / ANOMALIES_RELATIVE, archive / REPLAY_RELATIVE


def _verify_manifest(archive: Path) -> dict[str, str]:
    manifest_path = next(
        (archive / name for name in MANIFEST_NAMES if (archive / name).is_file()), None
    )
    if manifest_path is None or manifest_path.is_symlink():
        raise EpisodesError("manifest_missing")
    try:
        body = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EpisodesError("manifest_unreadable") from exc
    entries = body.get("files", []) if isinstance(body, dict) else body
    if not isinstance(entries, list):
        raise EpisodesError("manifest_entries_required")
    if not entries:
        raise EpisodesError("manifest_empty")
    result: dict[str, str] = {}
    for entry in entries:
        if (
            not isinstance(entry, dict)
            or not isinstance(entry.get("path"), str)
            or not isinstance(entry.get("sha256"), str)
        ):
            raise EpisodesError("manifest_entry_invalid")
        path = Path(entry["path"])
        if not path.is_absolute():
            path = archive / path
        try:
            relative = path.resolve().relative_to(archive).as_posix()
        except ValueError as exc:
            raise EpisodesError("manifest_path_escape") from exc
        if path.is_symlink() or not path.is_file() or _sha256(path) != entry["sha256"]:
            raise EpisodesError(f"manifest_hash_mismatch:{relative}")
        result[relative] = entry["sha256"]
    if len(result) != len(entries):
        raise EpisodesError("manifest_duplicate_path")
    result[manifest_path.name] = _sha256(manifest_path)
    return result


def _guard_archive(
    archive: Path, output: Path, allow_unpinned: bool
) -> tuple[Path, Path, dict[str, str]]:
    if not archive.is_dir():
        raise EpisodesError("archive_root_missing")
    if output.exists() and output.is_symlink():
        raise EpisodesError("output_symlink_rejected")
    archive = archive.resolve()
    output = output.resolve()
    try:
        output.relative_to(archive)
    except ValueError:
        pass
    else:
        raise EpisodesError("output_overlaps_archive")
    try:
        archive.relative_to(output)
    except ValueError:
        pass
    else:
        raise EpisodesError("output_overlaps_archive")
    if output.exists() and output.is_dir():
        input_inodes = {
            (path.stat().st_dev, path.stat().st_ino) for path in _input_paths(archive)
        }
        for candidate in output.rglob("*"):
            if (
                candidate.is_file()
                and (candidate.stat().st_dev, candidate.stat().st_ino) in input_inodes
            ):
                raise EpisodesError("output_hardlink_rejected")
    anomaly_path, replay_path = _input_paths(archive)
    for path, relative in (
        (anomaly_path, ANOMALIES_RELATIVE),
        (replay_path, REPLAY_RELATIVE),
    ):
        if path.is_symlink():
            raise EpisodesError(f"input_symlink_rejected:{relative}")
        if not path.is_file():
            raise EpisodesError(f"input_missing:{relative}")
        try:
            path.resolve().relative_to(archive)
        except ValueError as exc:
            raise EpisodesError(f"input_path_escape:{relative}") from exc
    hashes = {
        ANOMALIES_RELATIVE.as_posix(): _sha256(anomaly_path),
        REPLAY_RELATIVE.as_posix(): _sha256(replay_path),
    }
    hashes.update({f"{key}": value for key, value in _verify_manifest(archive).items()})
    if not allow_unpinned:
        if hashes[ANOMALIES_RELATIVE.as_posix()] != ANOMALIES_SHA256:
            raise EpisodesError("approved_hash_mismatch:analysis/anomalies.csv")
        if hashes[REPLAY_RELATIVE.as_posix()] != REPLAY_SHA256:
            raise EpisodesError("approved_hash_mismatch:independent-replay.json")
    return anomaly_path, replay_path, hashes


def _active_grid(calendar: Any) -> tuple[dict[str, set[str]], dict[str, str]]:
    active: dict[str, set[str]] = defaultdict(set)
    sessions: dict[str, set[str]] = defaultdict(set)
    for instrument in REGISTRY:
        lookup = calendar.lookup(instrument.exchange, DATE)
        if lookup.session is None:
            continue
        current = lookup.session.open_at.replace(second=0, microsecond=0)
        close = lookup.session.close_at
        while current < close:
            minute = current.isoformat().replace("+00:00", "Z")
            active[minute].add(instrument.symbol)
            sessions[minute].add(f"{instrument.exchange}:{DATE.isoformat()}")
            current += timedelta(minutes=1)
    return active, {minute: ",".join(sorted(keys)) for minute, keys in sessions.items()}


def aggregate_rows(
    selected_rows: Iterable[Mapping[str, Any]],
    *,
    active_symbols: Mapping[str, Iterable[str]] | Iterable[str] | None = None,
    session_keys: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Aggregate selected observations deterministically.

    ``selected_rows`` may contain ``latency_microseconds``; anomaly rows are then
    independently selected using strict ``<-2s`` and ``>15s`` comparisons. If
    Row IDs retain multiplicity while symbol membership is deduplicated.
    """
    minutes: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"observed": set(), "anomalous": set(), "ids": []}
    )
    selected = list(selected_rows)
    for row in selected:
        symbol = str(row["symbol"])
        minute = _minute(str(row["market_at"]))
        group = minutes[minute]
        group["observed"].add(symbol)
        raw_latency = row.get("latency_microseconds")
        is_anomaly = False
        if raw_latency is not None:
            latency = int(raw_latency)
            is_anomaly = latency < FUTURE_LIMIT_US or latency > STALE_LIMIT_US
        if is_anomaly:
            group["anomalous"].add(symbol)
            group["ids"].append(str(row["observation_id"]))
    if active_symbols is None:
        active: dict[str, set[str]] = {
            minute: set(group["observed"]) for minute, group in minutes.items()
        }
    elif isinstance(active_symbols, Mapping):
        active = {
            str(key): {str(symbol) for symbol in symbols}
            for key, symbols in active_symbols.items()
        }
    else:
        symbols = {str(symbol) for symbol in active_symbols}
        active = {minute: symbols for minute in minutes}
    all_minutes = sorted(set(minutes) | set(active))
    minute_output: dict[str, dict[str, Any]] = {}
    for minute in all_minutes:
        group = minutes[minute]
        observed = sorted(group["observed"])
        anomalous = sorted(group["anomalous"])
        minute_output[minute] = {
            "observed_symbols": observed,
            "anomalous_symbols": anomalous,
            "normal_symbols": sorted(set(observed) - set(anomalous)),
            "observed_normal_symbols": sorted(set(observed) - set(anomalous)),
            "missing_symbols": sorted(active.get(minute, set()) - set(observed)),
            "anomaly_ids": sorted(group["ids"]),
            "observed_symbol_denominator": len(observed),
            "active_symbol_denominator": len(active.get(minute, set())),
        }
    coincident = {
        minute: item["anomalous_symbols"]
        for minute, item in minute_output.items()
        if len(item["anomalous_symbols"]) >= 2
    }
    pairs: Counter[tuple[str, str]] = Counter()
    for item in coincident.values():
        pairs.update(itertools.combinations(item, 2))
    episodes: list[list[str]] = []
    previous: datetime | None = None
    previous_session: str | None = None
    for minute in sorted(coincident):
        current = datetime.fromisoformat(minute.replace("Z", "+00:00"))
        if (
            previous is None
            or current - previous != timedelta(minutes=1)
            or current.date() != previous.date()
            or (
                session_keys is not None
                and previous_session != session_keys.get(minute)
            )
        ):
            episodes.append([])
        episodes[-1].append(minute)
        previous = current
        previous_session = (
            session_keys.get(minute) if session_keys is not None else None
        )
    return {
        "minutes": minute_output,
        "coincident_minutes": coincident,
        "episodes": episodes,
        "pairwise_counts": [
            {"symbols": list(symbols), "count": count}
            for symbols, count in sorted(pairs.items())
        ],
        "selected_observation_count": len(selected),
        "anomaly_count": sum(
            len(item["anomaly_ids"]) for item in minute_output.values()
        ),
        "coincident_minute_count": len(coincident),
        "episode_count": len(episodes),
        "maximum_anomalous_symbols": max(
            (len(item["anomalous_symbols"]) for item in minute_output.values()),
            default=0,
        ),
    }


def _read_anomalies(path: Path) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8") as stream:
            return [dict(row) for row in csv.DictReader(stream)]
    except (OSError, csv.Error) as exc:
        raise EpisodesError("anomalies_csv_unreadable") from exc


def analyze_archive(
    archive_root: Path,
    output_dir: Path,
    *,
    evidence_root: Path | None = None,
    allow_unpinned: bool = False,
) -> dict[str, Any]:
    """Analyze the pinned timestamp-forensics archive without opening its DB."""
    anomaly_path, replay_path, before = _guard_archive(
        archive_root, output_dir, allow_unpinned
    )
    evidence = (evidence_root or archive_root).resolve()
    try:
        evidence_inputs, evidence_before, _, _ = _validate_archive(
            evidence, output_dir.resolve(), allow_unpinned=allow_unpinned
        )
        before.update(
            {
                f"evidence:{key}": value["sha256"]
                for key, value in evidence_before.items()
            }
        )
        evidence_manifest = _verify_manifest(evidence)
        before.update(
            {f"evidence:{key}": value for key, value in evidence_manifest.items()}
        )
        calendar = _load_calendar(
            evidence / "source/jusik/data/market_sessions_2023_2026.json"
        )
        active_grid, session_keys = _active_grid(calendar)
        db_path = evidence / DB_RELATIVE
        connection = sqlite3.connect(
            f"{db_path.as_uri()}?mode=ro&immutable=1", uri=True, timeout=0.1
        )
        connection.row_factory = sqlite3.Row
        try:
            session = connection.execute(
                "SELECT id, activated_at FROM forward_sessions ORDER BY activated_at DESC, id DESC LIMIT 1"
            ).fetchone()
            if session is None:
                raise EpisodesError("forward_session_missing")
            actual, _ = _parse_observations(
                connection, str(session["id"]), DATE, NOW, calendar
            )
        finally:
            connection.close()
    except (OSError, sqlite3.Error, ValueError) as exc:
        if isinstance(exc, EpisodesError):
            raise
        raise EpisodesError("snapshot_read_failed") from exc
    try:
        replay = json.loads(replay_path.read_text(encoding="utf-8"))
        anomaly_rows = _read_anomalies(anomaly_path)
    except (OSError, json.JSONDecodeError) as exc:
        raise EpisodesError("replay_json_unreadable") from exc
    if not isinstance(replay, dict) or not isinstance(
        replay.get("selected_rows"), list
    ):
        raise EpisodesError("replay_selected_rows_required")
    selected_rows = replay["selected_rows"]
    actual_rows = [
        {
            "observation_id": row.observation_id,
            "symbol": row.symbol,
            "market_at": row.market_at.isoformat().replace("+00:00", "Z"),
            "latency_microseconds": int(row.milliseconds * 1000),
        }
        for row in actual
    ]

    def identity(row: Mapping[str, Any]) -> tuple[str, str, str, int]:
        return (
            str(row["observation_id"]),
            str(row["symbol"]),
            str(row["market_at"]),
            int(str(row["latency_microseconds"])),
        )

    if Counter(identity(row) for row in selected_rows) != Counter(
        identity(row) for row in actual_rows
    ):
        raise EpisodesError("anomaly_reconciliation_failed")
    expected_anomaly_ids = sorted(str(row["observation_id"]) for row in anomaly_rows)
    actual_anomaly_ids = sorted(
        str(row["observation_id"])
        for row in actual_rows
        if int(str(row["latency_microseconds"])) < FUTURE_LIMIT_US
        or int(str(row["latency_microseconds"])) > STALE_LIMIT_US
    )
    if expected_anomaly_ids != actual_anomaly_ids:
        raise EpisodesError("anomaly_reconciliation_failed")
    result = aggregate_rows(
        actual_rows, active_symbols=active_grid, session_keys=session_keys
    )
    after = {
        ANOMALIES_RELATIVE.as_posix(): _sha256(anomaly_path),
        REPLAY_RELATIVE.as_posix(): _sha256(replay_path),
    }
    after.update(
        {key: value for key, value in _verify_manifest(archive_root.resolve()).items()}
    )
    evidence_after = _fingerprint(evidence_inputs)
    if evidence_before != evidence_after:
        raise EpisodesError("input_changed_during_analysis")
    after.update(
        {f"evidence:{key}": value["sha256"] for key, value in evidence_after.items()}
    )
    after.update(
        {f"evidence:{key}": value for key, value in _verify_manifest(evidence).items()}
    )
    if before != after:
        raise EpisodesError("input_changed_during_analysis")
    result["input_hashes"] = {"before": before, "after": after}
    output = output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output / "summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-root", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = analyze_archive(
            args.archive_root, args.output_dir, evidence_root=args.evidence_root
        )
    except (EpisodesError, OSError) as exc:
        print(f"error: {exc}")
        return 2
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "selected_observation_count",
                    "anomaly_count",
                    "coincident_minute_count",
                    "episode_count",
                )
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
