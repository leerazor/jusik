from __future__ import annotations

# ruff: noqa: E501
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
