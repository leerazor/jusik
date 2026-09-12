from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from jusik.research_future_observation_replay import SyntheticFixture, replay

BASE = {
    "synthetic": True,
    "window_start_at": "2030-01-01T00:00:00Z",
    "window_end_at": "2030-01-02T00:00:00Z",
    "checked_at": "2030-01-02T00:00:00Z",
}


def observation(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "source_id": "s1",
        "observation_id": "o1",
        "raw": '{"price": 1}',
        "received_at": "2030-01-01T01:00:00Z",
        "event_at": "2030-01-01T01:00:00Z",
        "read_started_at": "2030-01-01T00:59:00Z",
        "read_finished_at": "2030-01-01T01:01:00Z",
    }
    value.update(overrides)
    return value


def test_window_boundaries_and_plus_nine() -> None:
    items = [
        observation(observation_id="start", received_at="2030-01-01T00:00:00Z"),
        observation(observation_id="end", received_at="2030-01-02T00:00:00Z"),
        observation(observation_id="korea", received_at="2030-01-01T09:00:00+09:00"),
    ]
    result = replay({**BASE, "observations": items})
    assert [x.classifications for x in result.observations] == [
        ["in_window"],
        ["out_of_window"],
        ["in_window"],
    ]


def test_duplicate_does_not_move_first_receipt_and_keeps_receipts() -> None:
    first = observation(received_at="2029-12-31T23:00:00Z")
    second = observation(received_at="2030-01-01T01:00:00Z")
    result = replay({**BASE, "observations": [first, second]})
    item = result.observations[0]
    assert item.classifications == ["duplicate", "out_of_window"]
    assert [receipt.receipt_index for receipt in item.receipts] == [0, 1]


def test_conflict_preserves_all_versions_and_is_unresolved_with_invalid_clock() -> None:
    result = replay(
        {
            **BASE,
            "observations": [
                observation(raw="a"),
                observation(raw="b", read_finished_at="2030-01-01T00:00:00Z"),
            ],
        }
    )
    item = result.observations[0]
    assert item.classifications == ["unresolved", "clock_invalid", "conflict"]
    assert len(item.raw_versions) == 2
    assert "invalid_or_reversed_clock" in item.exclusion_reasons


def test_late_event_is_not_backdated() -> None:
    result = replay(
        {**BASE, "observations": [observation(event_at="2029-12-31T23:00:00Z")]}
    )
    assert result.observations[0].classifications == [
        "late_arrival",
        "in_window",
    ] or result.observations[0].classifications == ["in_window", "late_arrival"]


def test_boundary_and_truncation() -> None:
    fixture = {
        **BASE,
        "checked_at": "2030-01-01T12:00:00Z",
        "required_boundaries": [{"boundary": "end", "due_at": "2030-01-02T00:00:00Z"}],
        "truncation": {"total_count": 5, "inspected_count": 0},
    }
    result = replay(fixture)
    assert result.boundary_states == {"end": "not_due"}
    assert result.truncation == {
        "total_count": 5,
        "inspected_count": 0,
        "uninspected_count": 5,
        "truncated": True,
    }


def test_invalid_synthetic_and_naive_timestamps_rejected_or_classified() -> None:
    with pytest.raises(ValidationError):
        SyntheticFixture.model_validate({**BASE, "synthetic": False})
    result = replay(
        {**BASE, "observations": [observation(received_at="2030-01-01T01:00:00")]}
    )
    assert result.observations[0].classifications == ["clock_invalid"]


def test_truncation_must_match_inspected_records_and_boundary_contract() -> None:
    with pytest.raises(ValidationError):
        SyntheticFixture.model_validate(
            {
                **BASE,
                "observations": [observation()],
                "truncation": {"total_count": 2, "inspected_count": 0},
            }
        )
    with pytest.raises(ValidationError):
        SyntheticFixture.model_validate(
            {
                **BASE,
                "required_boundaries": [
                    {"boundary": "end", "due_at": "2030-01-01T00:00:00Z"}
                ],
            }
        )


def test_receipt_metadata_and_backwards_clock_are_preserved() -> None:
    result = replay(
        {
            **BASE,
            "observations": [
                observation(evidence_flags=["unavailable"]),
                observation(
                    received_at="2030-01-01T00:30:00Z",
                    evidence_flags=["unverified_provenance"],
                ),
            ],
        }
    )
    item = result.observations[0]
    assert "unresolved" in item.classifications
    assert "unavailable" in item.classifications
    assert item.receipts[1].evidence_flags == ["unverified_provenance"]
    assert item.receipts[1].event_at == "2030-01-01T01:00:00Z"
    reversed_result = replay(
        {
            **BASE,
            "observations": [
                observation(received_at="2030-01-01T02:00:00Z"),
                observation(received_at="2030-01-01T01:00:00Z"),
            ],
        }
    )
    assert "clock_invalid" in reversed_result.observations[0].classifications


def test_conflict_also_keeps_duplicate_fact_and_future_receipt_is_not_due() -> None:
    result = replay(
        {
            **BASE,
            "observations": [
                observation(raw="a"),
                observation(raw="a", received_at="2030-01-01T01:30:00Z"),
                observation(raw="b", received_at="2030-01-03T00:00:00Z"),
            ],
        }
    )
    item = result.observations[0]
    assert "conflict" not in item.classifications
    assert "duplicate" in item.classifications
    assert "not_due" in item.classifications
    assert len(item.receipts) == 3


def test_duplicate_and_conflict_are_both_facts_when_all_receipts_are_known() -> None:
    result = replay(
        {
            **BASE,
            "observations": [
                observation(raw="a"),
                observation(raw="a", received_at="2030-01-01T01:30:00Z"),
                observation(raw="b", received_at="2030-01-01T02:00:00Z"),
            ],
        }
    )
    item = result.observations[0]
    assert item.classifications[:3] == ["unresolved", "conflict", "duplicate"]
    assert item.evidence_counts["available_receipts"] == 3


def test_result_flags_are_always_synthetic_and_not_accepted() -> None:
    result = replay({**BASE})
    assert result.synthetic is True
    assert result.registered is False
    assert result.accepted_nav is False
    assert result.evaluation_inputs_complete is False
    assert result.checked_at == datetime(2030, 1, 2, tzinfo=UTC)


@pytest.mark.parametrize(
    ("checked_at", "state"),
    [("2030-01-01T00:00:00Z", "not_due"), ("2030-01-02T00:00:00Z", "missing")],
)
def test_boundary_before_and_at_due(checked_at: str, state: str) -> None:
    result = replay(
        {
            **BASE,
            "checked_at": checked_at,
            "required_boundaries": [
                {"boundary": "end", "due_at": BASE["window_end_at"]}
            ],
        }
    )
    assert result.boundary_states["end"] == state
    before = replay(
        {
            **BASE,
            "checked_at": "2029-12-31T23:00:00Z",
            "required_boundaries": [
                {"boundary": "start", "due_at": BASE["window_start_at"]}
            ],
        }
    )
    assert before.boundary_states["start"] == "not_due"


def test_missing_synthetic_and_utc_overflow_rejected() -> None:
    with pytest.raises(ValidationError):
        SyntheticFixture.model_validate(
            {k: v for k, v in BASE.items() if k != "synthetic"}
        )
    result = replay(
        {**BASE, "observations": [observation(received_at="9999-12-31T23:00:00-23:00")]}
    )
    assert result.observations[0].classifications == ["clock_invalid"]


@pytest.mark.parametrize("value", [None, False, "true", 1])
def test_cli_rejects_non_literal_synthetic(tmp_path: Path, value: object) -> None:
    fixture = tmp_path / "fixture.json"
    fixture.write_text(json.dumps({**BASE, "synthetic": value}), encoding="utf-8")
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "jusik.research_future_observation_replay",
            "--fixture",
            str(fixture),
            "--output",
            str(tmp_path / "out.json"),
        ],
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])},
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0


def test_cli_is_deterministic_and_refuses_malformed_oversize_and_alias(
    tmp_path: Path,
) -> None:
    fixture = tmp_path / "fixture.json"
    fixture.write_text(json.dumps(BASE), encoding="utf-8")
    output = tmp_path / "out.json"
    command = [
        sys.executable,
        "-m",
        "jusik.research_future_observation_replay",
        "--fixture",
        str(fixture),
        "--output",
        str(output),
    ]
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}
    first = subprocess.run(command, env=env, capture_output=True)
    assert first.returncode == 0
    payload = output.read_bytes()
    distinct = tmp_path / "distinct.json"
    assert subprocess.run([*command[:-1], str(distinct)], env=env).returncode == 0
    assert distinct.read_bytes() == payload
    second = subprocess.run(command, env=env, capture_output=True)
    assert second.returncode != 0 and output.read_bytes() == payload
    malformed = tmp_path / "malformed.json"
    malformed.write_text("{", encoding="utf-8")
    malformed_command = [
        sys.executable,
        "-m",
        "jusik.research_future_observation_replay",
        "--fixture",
        str(malformed),
        "--output",
        str(tmp_path / "bad.json"),
    ]
    assert subprocess.run(malformed_command, env=env).returncode != 0
    alias = tmp_path / "alias.json"
    alias.hardlink_to(fixture)
    alias_proc = subprocess.run(
        [*command[:-1], str(alias)], env=env, capture_output=True, text=True
    )
    assert alias_proc.returncode != 0 and (
        "alias" in alias_proc.stderr or "differ" in alias_proc.stderr
    )
    large = tmp_path / "large.json"
    large.write_bytes(b"{" + b"x" * (4 * 1024 * 1024) + b"}")
    large_command = [
        sys.executable,
        "-m",
        "jusik.research_future_observation_replay",
        "--fixture",
        str(large),
        "--output",
        str(tmp_path / "large-out.json"),
    ]
    assert subprocess.run(large_command, env=env).returncode != 0
