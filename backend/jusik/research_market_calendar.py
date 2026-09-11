from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Literal, cast
from zoneinfo import ZoneInfo

CalendarCode = Literal["XKRX", "XNYS"]
CalendarEntryState = Literal["session", "closed", "unavailable"]
CalendarPhase = Literal[
    "pre_open", "regular_session", "post_close", "closed", "unavailable"
]
EXCHANGE_CALENDAR: dict[str, CalendarCode] = {
    "KRX": "XKRX",
    "KSC": "XKRX",
    "NAS": "XNYS",
    "NMS": "XNYS",
    "NGM": "XNYS",
    "NYS": "XNYS",
    "NYQ": "XNYS",
    "AMS": "XNYS",
    "PCX": "XNYS",
}
CALENDAR_TIMEZONE: dict[CalendarCode, ZoneInfo] = {
    "XKRX": ZoneInfo("Asia/Seoul"),
    "XNYS": ZoneInfo("America/New_York"),
}
DEFAULT_CALENDAR_PATH = (
    Path(__file__).with_name("data") / "market_sessions_2023_2026.json"
)
UTC_TEXT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$")


class MarketCalendarError(ValueError):
    pass


@dataclass(frozen=True)
class MarketSession:
    calendar: CalendarCode
    local_date: date
    open_at: datetime
    close_at: datetime


@dataclass(frozen=True)
class CalendarLookup:
    calendar: CalendarCode | None
    local_date: date
    state: CalendarEntryState
    session: MarketSession | None = None
    reason: str | None = None


@dataclass(frozen=True)
class CalendarClock:
    calendar: CalendarCode
    phase: CalendarPhase
    local_date: date
    open_at: datetime | None
    close_at: datetime | None
    next_session: MarketSession | None


@dataclass(frozen=True)
class _Day:
    state: CalendarEntryState
    session: MarketSession | None


class MarketCalendar:
    def __init__(
        self,
        *,
        provider: str,
        provider_version: str,
        generated_at: datetime,
        coverage_start: date,
        coverage_end: date,
        calendars_sha256: str,
        artifact_sha256: str,
        days: dict[CalendarCode, dict[date, _Day]],
        error: str | None = None,
    ) -> None:
        self.provider = provider
        self.provider_version = provider_version
        self.generated_at = generated_at
        self.coverage_start = coverage_start
        self.coverage_end = coverage_end
        self.calendars_sha256 = calendars_sha256
        self.artifact_sha256 = artifact_sha256
        self._days = days
        self.error = error

    @property
    def available(self) -> bool:
        return self.error is None

    @classmethod
    def unavailable(cls, reason: str) -> MarketCalendar:
        epoch = datetime(1970, 1, 1, tzinfo=UTC)
        return cls(
            provider="exchange_calendars",
            provider_version="unavailable",
            generated_at=epoch,
            coverage_start=date(1970, 1, 1),
            coverage_end=date(1970, 1, 1),
            calendars_sha256="0" * 64,
            artifact_sha256="0" * 64,
            days={"XKRX": {}, "XNYS": {}},
            error=reason,
        )

    @classmethod
    def from_bytes(cls, raw: bytes) -> MarketCalendar:
        artifact_sha = hashlib.sha256(raw).hexdigest()
        try:
            payload = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MarketCalendarError("calendar_json_invalid") from exc
        return cls._from_payload(payload, artifact_sha)

    @classmethod
    def _from_payload(cls, payload: object, artifact_sha: str) -> MarketCalendar:
        if not isinstance(payload, dict):
            raise MarketCalendarError("calendar_root_invalid")
        required = {
            "schema_version",
            "provider",
            "provider_version",
            "generated_at",
            "coverage",
            "source_urls",
            "requirements",
            "verified_overrides",
            "calendars_sha256",
            "calendars",
        }
        if set(payload) != required:
            raise MarketCalendarError("calendar_fields_invalid")
        if payload["schema_version"] != 1:
            raise MarketCalendarError("calendar_schema_unsupported")
        if payload["provider"] != "exchange_calendars":
            raise MarketCalendarError("calendar_provider_invalid")
        if payload["provider_version"] != "4.12":
            raise MarketCalendarError("calendar_version_invalid")
        if payload["requirements"] != ["exchange_calendars==4.12"]:
            raise MarketCalendarError("calendar_requirements_invalid")
        generated_at = _parse_utc(payload["generated_at"], "generated_at")
        coverage = payload["coverage"]
        if not isinstance(coverage, dict) or set(coverage) != {"start", "end"}:
            raise MarketCalendarError("calendar_coverage_invalid")
        try:
            start = date.fromisoformat(cast(str, coverage["start"]))
            end = date.fromisoformat(cast(str, coverage["end"]))
        except (TypeError, ValueError) as exc:
            raise MarketCalendarError("calendar_coverage_invalid") from exc
        if end < start:
            raise MarketCalendarError("calendar_coverage_invalid")
        urls = payload["source_urls"]
        if (
            not isinstance(urls, list)
            or not urls
            or not all(
                isinstance(url, str) and url.startswith("https://") for url in urls
            )
        ):
            raise MarketCalendarError("calendar_sources_invalid")
        if not isinstance(payload["verified_overrides"], list):
            raise MarketCalendarError("calendar_overrides_invalid")
        calendars = payload["calendars"]
        if not isinstance(calendars, dict) or set(calendars) != {"XKRX", "XNYS"}:
            raise MarketCalendarError("calendar_sets_invalid")
        content_hash = hashlib.sha256(
            json.dumps(
                calendars, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode()
        ).hexdigest()
        claimed_hash = payload["calendars_sha256"]
        if claimed_hash != content_hash:
            raise MarketCalendarError("calendar_hash_mismatch")
        expected_length = (end - start).days + 1
        parsed: dict[CalendarCode, dict[date, _Day]] = {}
        for name in ("XKRX", "XNYS"):
            rows = calendars[name]
            if not isinstance(rows, list) or len(rows) != expected_length:
                raise MarketCalendarError("calendar_dates_incomplete")
            parsed_days: dict[date, _Day] = {}
            for index, row in enumerate(rows):
                expected = start + timedelta(days=index)
                parsed_day, day = _parse_day(name, row)
                if parsed_day != expected or parsed_day in parsed_days:
                    raise MarketCalendarError("calendar_dates_unordered_or_duplicate")
                parsed_days[parsed_day] = day
            parsed[name] = parsed_days
        return cls(
            provider=cast(str, payload["provider"]),
            provider_version=cast(str, payload["provider_version"]),
            generated_at=generated_at,
            coverage_start=start,
            coverage_end=end,
            calendars_sha256=content_hash,
            artifact_sha256=artifact_sha,
            days=parsed,
        )

    def lookup(self, exchange: str, local_date: date) -> CalendarLookup:
        calendar = EXCHANGE_CALENDAR.get(exchange)
        if calendar is None:
            return CalendarLookup(
                calendar=None,
                local_date=local_date,
                state="unavailable",
                reason="exchange_not_mapped",
            )
        if not self.available:
            return CalendarLookup(
                calendar=calendar,
                local_date=local_date,
                state="unavailable",
                reason=self.error,
            )
        day = self._days[calendar].get(local_date)
        if day is None:
            return CalendarLookup(
                calendar=calendar,
                local_date=local_date,
                state="unavailable",
                reason="date_out_of_coverage",
            )
        return CalendarLookup(
            calendar=calendar,
            local_date=local_date,
            state=day.state,
            session=day.session,
            reason=(
                "calendar_date_unconfirmed" if day.state == "unavailable" else None
            ),
        )

    def clock(self, exchange: str, at: datetime) -> CalendarClock:
        if at.tzinfo is None:
            raise ValueError("at must include a timezone")
        calendar = EXCHANGE_CALENDAR.get(exchange)
        if calendar is None:
            calendar = "XKRX" if exchange == "XKRX" else "XNYS"
            return CalendarClock(calendar, "unavailable", at.date(), None, None, None)
        local_date = at.astimezone(CALENDAR_TIMEZONE[calendar]).date()
        lookup = self.lookup(exchange, local_date)
        if lookup.state == "unavailable":
            phase: CalendarPhase = "unavailable"
        elif lookup.state == "closed":
            phase = "closed"
        else:
            assert lookup.session is not None
            current = at.astimezone(UTC)
            if current < lookup.session.open_at:
                phase = "pre_open"
            elif current <= lookup.session.close_at:
                phase = "regular_session"
            else:
                phase = "post_close"
        return CalendarClock(
            calendar=calendar,
            phase=phase,
            local_date=local_date,
            open_at=lookup.session.open_at if lookup.session else None,
            close_at=lookup.session.close_at if lookup.session else None,
            next_session=self.next_session(exchange, at),
        )

    def next_session(self, exchange: str, after: datetime) -> MarketSession | None:
        if after.tzinfo is None:
            raise ValueError("after must include a timezone")
        calendar = EXCHANGE_CALENDAR.get(exchange)
        if calendar is None or not self.available:
            return None
        current = after.astimezone(CALENDAR_TIMEZONE[calendar]).date()
        while current <= self.coverage_end:
            lookup = self.lookup(exchange, current)
            if lookup.state == "unavailable":
                return None
            if lookup.session is not None and lookup.session.open_at > after.astimezone(
                UTC
            ):
                return lookup.session
            current += timedelta(days=1)
        return None

    def latest_completed_session(
        self, exchange: str, at: datetime
    ) -> MarketSession | None:
        if at.tzinfo is None:
            raise ValueError("at must include a timezone")
        calendar = EXCHANGE_CALENDAR.get(exchange)
        if calendar is None or not self.available:
            return None
        current = at.astimezone(CALENDAR_TIMEZONE[calendar]).date()
        while current >= self.coverage_start:
            lookup = self.lookup(exchange, current)
            if lookup.state == "unavailable":
                return None
            if lookup.session is not None and lookup.session.close_at <= at.astimezone(
                UTC
            ):
                return lookup.session
            current -= timedelta(days=1)
        return None


def _parse_utc(value: object, field: str) -> datetime:
    if not isinstance(value, str) or UTC_TEXT.fullmatch(value) is None:
        raise MarketCalendarError(f"calendar_{field}_invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MarketCalendarError(f"calendar_{field}_invalid") from exc
    if parsed.tzinfo != UTC:
        raise MarketCalendarError(f"calendar_{field}_invalid")
    return parsed


def _parse_day(calendar: CalendarCode, row: object) -> tuple[date, _Day]:
    if not isinstance(row, dict) or "date" not in row or "state" not in row:
        raise MarketCalendarError("calendar_day_invalid")
    try:
        local_date = date.fromisoformat(cast(str, row["date"]))
    except (TypeError, ValueError) as exc:
        raise MarketCalendarError("calendar_day_invalid") from exc
    state = row["state"]
    if state in {"closed", "unavailable"}:
        if set(row) != {"date", "state"}:
            raise MarketCalendarError("calendar_closed_day_invalid")
        return local_date, _Day(cast(CalendarEntryState, state), None)
    if state != "session" or set(row) != {"date", "state", "open_at", "close_at"}:
        raise MarketCalendarError("calendar_session_invalid")
    opening = _parse_utc(row["open_at"], "open_at")
    closing = _parse_utc(row["close_at"], "close_at")
    if opening >= closing:
        raise MarketCalendarError("calendar_session_order_invalid")
    zone = CALENDAR_TIMEZONE[calendar]
    if (
        opening.astimezone(zone).date() != local_date
        or closing.astimezone(zone).date() != local_date
    ):
        raise MarketCalendarError("calendar_session_date_invalid")
    open_time = opening.astimezone(zone).time().replace(tzinfo=None)
    close_time = closing.astimezone(zone).time().replace(tzinfo=None)
    valid = (
        calendar == "XNYS"
        and open_time == time(9, 30)
        and close_time in {time(13), time(16)}
    ) or (
        calendar == "XKRX"
        and (open_time, close_time)
        in {(time(9), time(15, 30)), (time(10), time(15, 30)), (time(10), time(16, 30))}
    )
    if not valid:
        raise MarketCalendarError("calendar_session_time_invalid")
    return local_date, _Day(
        "session", MarketSession(calendar, local_date, opening, closing)
    )


def load_market_calendar(path: Path = DEFAULT_CALENDAR_PATH) -> MarketCalendar:
    try:
        return MarketCalendar.from_bytes(path.read_bytes())
    except (OSError, MarketCalendarError) as exc:
        code = (
            str(exc)
            if isinstance(exc, MarketCalendarError)
            else "calendar_file_unavailable"
        )
        return MarketCalendar.unavailable(code)


@lru_cache(maxsize=1)
def default_market_calendar() -> MarketCalendar:
    return load_market_calendar()
