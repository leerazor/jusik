from __future__ import annotations

from datetime import UTC, datetime

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
    assert "same_source_and_id_have_different_raw_hashes" in item.exclusion_reasons


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
        "required_boundaries": [
            {"boundary": "end", "due_at": "2030-01-02T00:00:00Z", "evidence_id": "e"}
        ],
        "truncation": {"total_count": 5, "inspected_count": 2},
    }
    result = replay(fixture)
    assert result.boundary_states == {"end": "not_due"}
    assert result.truncation == {
        "total_count": 5,
        "inspected_count": 2,
        "uninspected_count": 3,
        "truncated": True,
    }


def test_invalid_synthetic_and_naive_timestamps_rejected_or_classified() -> None:
    with pytest.raises(ValidationError):
        SyntheticFixture.model_validate({**BASE, "synthetic": False})
    result = replay(
        {**BASE, "observations": [observation(received_at="2030-01-01T01:00:00")]}
    )
    assert result.observations[0].classifications == ["clock_invalid"]


def test_result_flags_are_always_synthetic_and_not_accepted() -> None:
    result = replay({**BASE})
    assert result.synthetic is True
    assert result.registered is False
    assert result.accepted_nav is False
    assert result.evaluation_inputs_complete is False
    assert result.checked_at == datetime(2030, 1, 2, tzinfo=UTC)
