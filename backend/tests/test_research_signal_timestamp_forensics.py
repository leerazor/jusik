from __future__ import annotations

import csv
import hashlib
import json
import os
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from jusik.research_signal_timestamp_forensics import (
    CODE_RELATIVES,
    ForensicsError,
    analyze_archive,
)

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_SOURCE = ROOT / "jusik"
SESSION_ID = "session"
ACTIVATED_AT = "2026-09-10T00:00:00+00:00"


def _quote(
    symbol: str,
    market_at: str,
    received_at: str,
    *,
    source: str = "KIS H0STCNT0",
) -> str:
    exchange = "KRX" if symbol == "005930" else "NAS"
    currency = "KRW" if symbol == "005930" else "USD"
    return json.dumps(
        {
            "symbol": symbol,
            "exchange": exchange,
            "currency": currency,
            "price": "100",
            "ask": "101",
            "bid": "99",
            "volume": 1,
            "accumulated_volume": 1,
            "market_at": market_at,
            "received_at": received_at,
            "source": source,
            "delay_minutes": 0,
            "realtime_code": None,
        },
        separators=(",", ":"),
    )


def _row(
    number: int,
    symbol: str,
    market_at: str,
    received_at: str,
    *,
    reason: str = "minute_sample",
) -> tuple[str, str, str, str, str, str, str, str]:
    quote = _quote(symbol, market_at, received_at)
    return (
        f"observation-{number}",
        SESSION_ID,
        symbol,
        market_at,
        market_at,
        received_at,
        reason,
        quote,
    )


def _archive(tmp_path: Path, rows: list[tuple[Any, ...]]) -> Path:
    archive = tmp_path / "archive"
    source = archive / "source/jusik"
    (archive / "private").mkdir(parents=True)
    (source / "data").mkdir(parents=True)
    for relative in CODE_RELATIVES:
        relative = relative.relative_to("source/jusik")
        (source / relative).write_bytes((ARCHIVE_SOURCE / relative).read_bytes())

    database = archive / "private/forward-snapshot.db"
    connection = sqlite3.connect(database)
    connection.executescript(
        """
        CREATE TABLE forward_sessions (
            id TEXT PRIMARY KEY, activated_at TEXT NOT NULL
        );
        CREATE TABLE forward_observations (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            minute_key TEXT NOT NULL,
            market_at TEXT NOT NULL,
            received_at TEXT NOT NULL,
            reason TEXT NOT NULL,
            quote_json TEXT NOT NULL
        );
        """
    )
    connection.execute(
        "INSERT INTO forward_sessions VALUES (?, ?)", (SESSION_ID, ACTIVATED_AT)
    )
    connection.executemany(
        "INSERT INTO forward_observations VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows
    )
    connection.commit()
    connection.close()
    wal = archive / "private/forward-snapshot.db-wal"
    wal.write_bytes(b"")

    code_and_calendar = []
    for relative in CODE_RELATIVES:
        path = source / relative.relative_to("source/jusik")
        code_and_calendar.append(
            {
                "path": f"/sanitized/backend/{relative.as_posix()}",
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    provenance = {
        "snapshot_sha256": hashlib.sha256(database.read_bytes()).hexdigest(),
        "snapshot_wal_sha256": hashlib.sha256(wal.read_bytes()).hexdigest(),
        "code_and_calendar": code_and_calendar,
    }
    (archive / "provenance.json").write_text(
        json.dumps(provenance, sort_keys=True) + "\n", encoding="utf-8"
    )
    (archive / "signal-validation.json").write_text(
        json.dumps(
            {
                "local_date": "2026-09-11",
                "latency": {},
                "symbol_latency": [],
                "coverage": [],
                "latency_anomalies": {"total_count": 0},
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return archive


def _default_rows() -> list[tuple[Any, ...]]:
    return [
        _row(1, "005930", "2026-09-11T00:00:00Z", "2026-09-10T23:59:58Z"),
        _row(2, "005930", "2026-09-11T00:01:00Z", "2026-09-11T00:00:57.999999Z"),
        _row(3, "005930", "2026-09-11T00:02:00Z", "2026-09-11T00:02:15Z"),
        _row(4, "005930", "2026-09-11T00:03:00Z", "2026-09-11T00:03:15.000001Z"),
        # Same symbol/minute/reason is retained for latency and deduplicated by
        # coverage.
        _row(5, "005930", "2026-09-11T00:04:01Z", "2026-09-11T00:04:01Z"),
        _row(6, "005930", "2026-09-11T00:04:02Z", "2026-09-11T00:04:02Z"),
        # New York 19:00 on the same local date; KST has already moved to 9/12.
        _row(7, "NVDA", "2026-09-11T19:00:00Z", "2026-09-11T19:00:00Z"),
        # KRX close is exclusive, so this is outside the selected rows.
        _row(8, "005930", "2026-09-11T06:30:00Z", "2026-09-11T06:30:00Z"),
    ]


def test_boundaries_dates_duplicates_and_raw_timestamps(tmp_path: Path) -> None:
    archive = _archive(tmp_path, _default_rows())
    output = tmp_path / "output"
    summary = analyze_archive(archive, output, allow_unpinned=True)

    assert summary["totals"] == {
        "selected_observations": 7,
        "latency_samples": 7,
        "anomalies": 2,
        "future": 1,
        "stale": 1,
    }
    assert summary["by_symbol"]["005930"]["sample_count"] == 6
    coverage = {item["symbol"]: item for item in summary["coverage"]}
    assert coverage["005930"]["persisted_rows"] == 6
    assert coverage["005930"]["observed_completed_minutes"] == 5
    assert summary["by_symbol"]["NVDA"]["sample_count"] == 1
    with (output / "anomalies.csv").open(newline="", encoding="utf-8") as stream:
        anomaly_rows = list(csv.DictReader(stream))
    assert {row["observation_id"] for row in anomaly_rows} == {
        "observation-2",
        "observation-4",
    }
    future = next(row for row in anomaly_rows if row["kind"] == "future")
    assert future["milliseconds"] == "-2000.001"
    assert future["quote_market_at_raw"] == "2026-09-11T00:01:00Z"
    assert future["quote_received_at_raw"] == "2026-09-11T00:00:57.999999Z"
    assert future["db_market_at"] == "2026-09-11T00:01:00Z"
    assert future["db_received_at"] == "2026-09-11T00:00:57.999999Z"


def test_empty_and_more_than_fifty_anomalies_are_not_truncated(tmp_path: Path) -> None:
    empty = _archive(tmp_path / "empty", [])
    empty_summary = analyze_archive(
        empty, tmp_path / "empty-output", allow_unpinned=True
    )
    assert empty_summary["totals"]["latency_samples"] == 0
    assert (tmp_path / "empty-output/anomalies.csv").read_text() == ",".join(
        [
            "observation_id",
            "symbol",
            "exchange",
            "source",
            "reason",
            "kind",
            "milliseconds",
            "market_at",
            "received_at",
            "quote_market_at_raw",
            "quote_received_at_raw",
            "db_market_at",
            "db_received_at",
            "utc_hour",
        ]
    ) + "\n"

    base = datetime(2026, 9, 11, tzinfo=UTC)
    rows = []
    for index in range(1, 62):
        market_at = base + timedelta(minutes=index)
        received_at = market_at - timedelta(seconds=2, microseconds=1)
        rows.append(
            _row(
                index,
                "005930",
                market_at.isoformat().replace("+00:00", "Z"),
                received_at.isoformat().replace("+00:00", "Z"),
            )
        )
    large = _archive(tmp_path / "large", rows)
    summary = analyze_archive(large, tmp_path / "large-output", allow_unpinned=True)
    assert summary["totals"]["anomalies"] == 61
    with (tmp_path / "large-output/anomalies.csv").open(
        newline="", encoding="utf-8"
    ) as stream:
        assert len(list(csv.DictReader(stream))) == 61


def test_replay_is_deterministic_and_preserves_input_hashes(tmp_path: Path) -> None:
    archive = _archive(tmp_path, _default_rows())
    first = tmp_path / "first"
    second = tmp_path / "second"
    analyze_archive(archive, first, allow_unpinned=True)
    analyze_archive(archive, second, allow_unpinned=True)
    for filename in ("anomalies.csv", "summary.json", "input-hashes.json"):
        assert (first / filename).read_bytes() == (second / filename).read_bytes()
    hashes = json.loads((first / "input-hashes.json").read_text())
    assert hashes["before"] == hashes["after"]
    assert (
        hashes["archive_snapshot_sha256"]
        == hashes["files"]["private/forward-snapshot.db"]["sha256"]
    )


def test_tampered_inputs_and_nonempty_wal_are_rejected(tmp_path: Path) -> None:
    for tamper in ("database", "calendar", "wal"):
        archive = _archive(tmp_path / tamper, _default_rows())
        if tamper == "database":
            with (archive / "private/forward-snapshot.db").open("ab") as stream:
                stream.write(b"tampered")
        elif tamper == "calendar":
            with (archive / "source/jusik/data/market_sessions_2023_2026.json").open(
                "ab"
            ) as stream:
                stream.write(b" ")
        else:
            (archive / "private/forward-snapshot.db-wal").write_bytes(b"wal")
        with pytest.raises(ForensicsError):
            analyze_archive(archive, tmp_path / f"output-{tamper}", allow_unpinned=True)


def test_output_may_not_overlap_archive(tmp_path: Path) -> None:
    archive = _archive(tmp_path, [])
    with pytest.raises(ForensicsError, match="output_overlaps_archive"):
        analyze_archive(archive, archive / "results", allow_unpinned=True)


def test_archive_path_is_encoded_as_sqlite_uri(tmp_path: Path) -> None:
    archive = _archive(tmp_path / "archive?# with spaces", _default_rows())
    summary = analyze_archive(archive, tmp_path / "special-output", allow_unpinned=True)
    assert summary["totals"]["latency_samples"] == 7


def test_source_and_output_aliases_are_rejected(tmp_path: Path) -> None:
    source_alias_archive = _archive(tmp_path / "source", [])
    source_file = source_alias_archive / "source/jusik/research_quote_models.py"
    source_file.unlink()
    os.symlink(ARCHIVE_SOURCE / "research_quote_models.py", source_file)
    with pytest.raises(ForensicsError, match="input_symlink_rejected"):
        analyze_archive(
            source_alias_archive, tmp_path / "source-output", allow_unpinned=True
        )

    output_alias_archive = _archive(tmp_path / "output", [])
    output = tmp_path / "output-hardlink"
    output.mkdir()
    os.link(
        output_alias_archive / "private/forward-snapshot.db", output / "summary.json"
    )
    with pytest.raises(ForensicsError, match="output_hardlink_rejected"):
        analyze_archive(output_alias_archive, output, allow_unpinned=True)


def test_forged_self_consistent_archive_is_rejected_before_sqlite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = _archive(tmp_path, _default_rows())
    opened = False

    def spy_connect(*args: Any, **kwargs: Any) -> sqlite3.Connection:
        nonlocal opened
        opened = True
        raise AssertionError("SQLite must not open for an unapproved archive")

    monkeypatch.setattr(sqlite3, "connect", spy_connect)
    with pytest.raises(ForensicsError, match="approved_hash_mismatch"):
        analyze_archive(archive, tmp_path / "forged-output")
    assert not opened
