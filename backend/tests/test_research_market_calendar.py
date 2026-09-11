from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from jusik.research_market_calendar import (
    DEFAULT_CALENDAR_PATH,
    MarketCalendar,
    MarketCalendarError,
    load_market_calendar,
)


def _payload() -> dict[str, Any]:
    return json.loads(DEFAULT_CALENDAR_PATH.read_text(encoding="utf-8"))


def _encoded(payload: dict[str, Any]) -> bytes:
    calendars = payload["calendars"]
    payload["calendars_sha256"] = hashlib.sha256(
        json.dumps(
            calendars, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()
    return json.dumps(payload, ensure_ascii=False).encode()


def test_committed_calendar_has_holidays_early_closes_dst_and_krx_offsets() -> None:
    calendar = load_market_calendar()
    assert calendar.available
    assert calendar.provider_version == "4.12"
    assert calendar.lookup("NYS", datetime(2026, 7, 3).date()).state == "closed"

    thanksgiving = calendar.lookup("NYS", datetime(2026, 11, 27).date()).session
    christmas = calendar.lookup("NYS", datetime(2026, 12, 24).date()).session
    assert thanksgiving is not None and thanksgiving.close_at.hour == 18
    assert christmas is not None and christmas.close_at.hour == 18

    before_dst = calendar.lookup("NAS", datetime(2024, 3, 8).date()).session
    after_dst = calendar.lookup("NAS", datetime(2024, 3, 11).date()).session
    assert before_dst is not None and before_dst.open_at.hour == 14
    assert after_dst is not None and after_dst.open_at.hour == 13

    first_krx = calendar.lookup("KRX", datetime(2023, 1, 2).date()).session
    csat = calendar.lookup("KRX", datetime(2025, 11, 13).date()).session
    assert first_krx is not None and first_krx.open_at.hour == 1
    assert first_krx.close_at.hour == 6
    assert csat is not None and (csat.open_at.hour, csat.close_at.hour) == (1, 7)
    assert calendar.lookup("KRX", datetime(2026, 11, 19).date()).state == "unavailable"


def test_session_boundaries_are_inclusive_and_next_session_stops_at_unknown() -> None:
    calendar = load_market_calendar()
    opening = datetime(2026, 11, 27, 14, 30, tzinfo=UTC)
    closing = datetime(2026, 11, 27, 18, 0, tzinfo=UTC)
    assert calendar.clock("NYS", opening).phase == "regular_session"
    assert calendar.clock("NYS", closing).phase == "regular_session"
    assert calendar.clock("NYS", opening.replace(minute=29)).phase == "pre_open"
    assert calendar.clock("NYS", closing.replace(minute=1)).phase == "post_close"
    assert calendar.clock("NYS", datetime(2026, 7, 3, 16, tzinfo=UTC)).phase == "closed"
    assert calendar.next_session("KRX", datetime(2026, 11, 18, 9, tzinfo=UTC)) is None
    assert calendar.latest_completed_session("NYS", closing) is not None
    assert (
        calendar.latest_completed_session("KRX", datetime(2026, 11, 19, 2, tzinfo=UTC))
        is None
    )


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (
            lambda value: value["calendars"]["XNYS"].pop(10),
            "calendar_dates_incomplete",
        ),
        (
            lambda value: value["calendars"]["XNYS"].__setitem__(
                10, dict(value["calendars"]["XNYS"][9])
            ),
            "calendar_dates_unordered_or_duplicate",
        ),
        (
            lambda value: value["calendars"]["XNYS"][10].__setitem__(
                "open_at", "2023-01-11T09:30:00"
            ),
            "calendar_open_at_invalid",
        ),
        (
            lambda value: value["calendars"]["XNYS"][10].__setitem__(
                "open_at", "2023-01-11T25:30:00Z"
            ),
            "calendar_open_at_invalid",
        ),
        (
            lambda value: value["calendars"]["XNYS"][10].update(
                {"open_at": "2023-01-11T15:00:00Z", "close_at": "2023-01-11T14:00:00Z"}
            ),
            "calendar_session_order_invalid",
        ),
        (
            lambda value: value["calendars"]["XNYS"][10].update(
                {"open_at": "2023-01-11T15:00:00Z", "close_at": "2023-01-11T21:00:00Z"}
            ),
            "calendar_session_time_invalid",
        ),
    ],
)
def test_corrupt_or_incomplete_calendars_fail_closed(mutate: Any, code: str) -> None:
    payload = _payload()
    mutate(payload)
    with pytest.raises(MarketCalendarError, match=code):
        MarketCalendar.from_bytes(_encoded(payload))


def test_missing_or_out_of_range_calendar_is_unavailable(tmp_path: Path) -> None:
    calendar = load_market_calendar(tmp_path / "missing.json")
    assert not calendar.available
    assert calendar.lookup("KRX", datetime(2026, 9, 10).date()).state == "unavailable"

    committed = load_market_calendar()
    assert committed.lookup("NYS", datetime(2027, 1, 1).date()).state == "unavailable"


def test_invalid_metadata_datetime_fails_closed_without_raw_error(
    tmp_path: Path,
) -> None:
    payload = _payload()
    payload["generated_at"] = "2026-99-10T00:00:00Z"
    path = tmp_path / "invalid.json"
    path.write_bytes(_encoded(payload))
    calendar = load_market_calendar(path)
    assert not calendar.available
    assert calendar.error == "calendar_generated_at_invalid"
