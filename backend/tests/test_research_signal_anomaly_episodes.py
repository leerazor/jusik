from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

import pytest

from jusik.research_signal_anomaly_episodes import (
    EpisodesError,
    _guard_archive,
    _verify_manifest,
    aggregate_rows,
    analyze_archive,
)
from jusik.research_signal_anomaly_episodes import aggregate_rows


def _row(oid: str, symbol: str, minute: str, latency: int) -> dict[str, object]:
    return {
        "observation_id": oid,
        "symbol": symbol,
        "market_at": f"2026-09-11T{minute}:00Z",
        "latency_microseconds": latency,
    }


def test_strict_thresholds_duplicates_and_sets() -> None:
    rows = [
        _row("a", "AAA", "00:00", -2_000_000),
        _row("b", "BBB", "00:00", -2_000_001),
        _row("c", "BBB", "00:00", -2_000_002),
        _row("d", "CCC", "00:00", 15_000_000),
        _row("e", "DDD", "00:00", 15_000_001),
    ]
    result = aggregate_rows(
        rows,
        active_symbols={"2026-09-11T00:00:00Z": {"AAA", "BBB", "CCC", "DDD", "EEE"}},
    )
    minute = result["minutes"]["2026-09-11T00:00:00Z"]
    assert minute["observed_symbol_denominator"] == 4
    assert minute["anomalous_symbols"] == ["BBB", "DDD"]
    assert minute["normal_symbols"] == ["AAA", "CCC"]
    assert minute["missing_symbols"] == ["EEE"]
    assert minute["anomaly_ids"] == ["b", "c", "e"]


def test_episodes_break_on_gaps_and_date_boundaries() -> None:
    rows = [
        _row("a", "AAA", "23:59", -3_000_000),
        _row("b", "BBB", "23:59", -3_000_000),
        {**_row("c", "AAA", "00:00", -3_000_000), "market_at": "2026-09-12T00:00:00Z"},
        {**_row("d", "BBB", "00:00", -3_000_000), "market_at": "2026-09-12T00:00:00Z"},
    ]
    result = aggregate_rows(rows)
    assert result["episodes"] == [["2026-09-11T23:59:00Z"], ["2026-09-12T00:00:00Z"]]


def test_shuffled_rows_are_deterministic() -> None:
    rows = [
        _row("a", "AAA", "00:00", -3_000_000),
        _row("b", "BBB", "00:00", -3_000_000),
    ]
    assert aggregate_rows(rows) == aggregate_rows(reversed(rows))


def test_observed_membership_change_does_not_split_implicit_session() -> None:
    rows = [
        _row("a", "AAA", "00:00", -3_000_000),
        _row("b", "BBB", "00:00", -3_000_000),
        _row("c", "AAA", "00:01", -3_000_000),
        _row("d", "BBB", "00:01", -3_000_000),
        _row("e", "CCC", "00:01", 0),
    ]
    result = aggregate_rows(rows)
    assert result["episodes"] == [["2026-09-11T00:00:00Z", "2026-09-11T00:01:00Z"]]


def test_explicit_session_key_splits_adjacent_minutes() -> None:
    rows = [
        _row("a", "AAA", "00:00", -3_000_000),
        _row("b", "BBB", "00:00", -3_000_000),
        _row("c", "AAA", "00:01", -3_000_000),
        _row("d", "BBB", "00:01", -3_000_000),
    ]
    result = aggregate_rows(
        rows,
        session_keys={
            "2026-09-11T00:00:00Z": "KRX:2026-09-11",
            "2026-09-11T00:01:00Z": "NYS:2026-09-11",
        },
    )
    assert result["episodes"] == [["2026-09-11T00:00:00Z"], ["2026-09-11T00:01:00Z"]]


def test_synchronous_and_asynchronous_seconds_exact_minute() -> None:
    rows = [_row("a", "AAA", "00:00", 0), _row("b", "BBB", "00:00", -2_000_000)]
    result = aggregate_rows(rows)
    assert result["minutes"]["2026-09-11T00:00:00Z"]["anomalous_symbols"] == []
    rows[1]["latency_microseconds"] = -2_000_001
    assert aggregate_rows(rows)["minutes"]["2026-09-11T00:00:00Z"][
        "anomalous_symbols"
    ] == ["BBB"]


def test_missing_minute_grid_break() -> None:
    rows = [
        _row("a", "AAA", "00:00", -3_000_000),
        _row("b", "BBB", "00:00", -3_000_000),
        _row("c", "AAA", "00:02", -3_000_000),
        _row("d", "BBB", "00:02", -3_000_000),
    ]
    active = {f"2026-09-11T00:0{i}:00Z": {"AAA", "BBB"} for i in range(3)}
    result = aggregate_rows(rows, active_symbols=active)
    assert result["minutes"]["2026-09-11T00:01:00Z"]["missing_symbols"] == [
        "AAA",
        "BBB",
    ]
    assert len(result["episodes"]) == 2


def test_observed_normal_vs_missing() -> None:
    result = aggregate_rows(
        [_row("a", "AAA", "00:00", 0)],
        active_symbols={
            "2026-09-11T00:00:00Z": {"AAA", "BBB"},
            "2026-09-11T00:01:00Z": {"AAA", "BBB"},
        },
    )
    assert result["minutes"]["2026-09-11T00:00:00Z"]["normal_symbols"] == ["AAA"]
    assert result["minutes"]["2026-09-11T00:01:00Z"]["missing_symbols"] == [
        "AAA",
        "BBB",
    ]


def test_kst_date_boundary() -> None:
    rows = [
        _row("a", "AAA", "14:59", -3_000_000),
        _row("b", "BBB", "14:59", -3_000_000),
        {**_row("c", "AAA", "00:00", -3_000_000), "market_at": "2026-09-11T15:00:00Z"},
        {**_row("d", "BBB", "00:00", -3_000_000), "market_at": "2026-09-11T15:00:00Z"},
    ]
    result = aggregate_rows(
        rows,
        session_keys={
            "2026-09-11T14:59:00Z": "KRX:2026-09-11",
            "2026-09-11T15:00:00Z": "KRX:2026-09-12",
        },
    )
    assert len(result["episodes"]) == 2


def test_empty_input() -> None:
    assert aggregate_rows([])["episode_count"] == 0


def test_same_id_duplicate_retention() -> None:
    rows = [
        _row("same", "AAA", "00:00", -3_000_000),
        _row("same", "AAA", "00:00", -3_000_001),
        _row("b", "BBB", "00:00", -3_000_000),
    ]
    result = aggregate_rows(rows)
    minute = result["minutes"]["2026-09-11T00:00:00Z"]
    assert minute["anomaly_ids"] == ["b", "same", "same"]
    assert minute["anomalous_symbols"] == ["AAA", "BBB"]


def test_frozen_archive_replay(tmp_path: Path) -> None:
    timestamp = Path(
        "/home/kwl/.local/share/jusik/portfolio-audit/paper-signal-timestamp-forensics-v1-a77ec18fbf634b3694afa8da08ef11c6"
    )
    evidence = Path(
        "/home/kwl/.local/share/jusik/portfolio-audit/paper-signal-evidence-v1-722bb6f1d10a42318b502092d64dac39"
    )
    if not (timestamp.exists() and evidence.exists()):
        pytest.skip("frozen archives unavailable")
    first = analyze_archive(timestamp, tmp_path / "one", evidence_root=evidence)
    second = analyze_archive(timestamp, tmp_path / "two", evidence_root=evidence)
    assert (
        first["anomaly_count"],
        first["coincident_minute_count"],
        first["maximum_anomalous_symbols"],
        first["episode_count"],
    ) == (249, 68, 5, 65)
    with (timestamp / "analysis/anomalies.csv").open(
        newline="", encoding="utf-8"
    ) as stream:
        assert sum(1 for _ in csv.DictReader(stream)) == 249
    assert (tmp_path / "one/summary.json").read_bytes() == (
        tmp_path / "two/summary.json"
    ).read_bytes()
    assert first["input_hashes"] == second["input_hashes"]


def test_archive_manifest_tamper(tmp_path: Path) -> None:
    item = tmp_path / "item"
    item.write_text("ok", encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps([{"path": str(item), "sha256": hashlib.sha256(b"ok").hexdigest()}]),
        encoding="utf-8",
    )
    assert _verify_manifest(tmp_path)["manifest.json"]
    item.write_text("tampered", encoding="utf-8")
    with pytest.raises(EpisodesError, match="manifest_hash_mismatch"):
        _verify_manifest(tmp_path)


def test_output_hardlink_to_timestamp_input_rejected(tmp_path: Path) -> None:
    (tmp_path / "analysis").mkdir()
    (tmp_path / "analysis/anomalies.csv").write_text("x", encoding="utf-8")
    (tmp_path / "independent-replay.json").write_text("{}", encoding="utf-8")
    manifest = [
        {
            "path": str(tmp_path / "analysis/anomalies.csv"),
            "sha256": hashlib.sha256(b"x").hexdigest(),
        }
    ]
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    out = tmp_path.parent / f"{tmp_path.name}-out"
    out.mkdir()
    (out / "alias").hardlink_to(tmp_path / "analysis/anomalies.csv")
    with pytest.raises(EpisodesError, match="output_hardlink_rejected"):
        _guard_archive(tmp_path, out, True)
