from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import exchange_calendars  # type: ignore[import-not-found]

SCHEMA_VERSION = 1
DEFAULT_START = date(2023, 1, 1)
DEFAULT_END = date(2026, 12, 31)
CALENDAR_NAMES = ("XKRX", "XNYS")
SOURCE_URLS = (
    "https://github.com/gerrymanoim/exchange_calendars",
    "https://global.krx.co.kr/contents/GLB/05/0501/0501110000/GLB0501110000.jsp",
    "https://www.nyse.com/markets/hours-calendars",
    "https://www.samsungpop.com/ux/kor/customer/notice/notice/noticeViewContent.do?MenuSeqNo=20302",
    "https://www.samsungpop.com/ux/kor/customer/notice/notice/noticeViewContent.do?MenuSeqNo=21587",
    "https://securities.koreainvestment.com/main/customer/notice/Notice.jsp?cmd=TF04ga000002&num=45644",
    "https://www.moe.go.kr/boardCnts/viewRenew.do?boardID=294&boardSeq=100526&lev=0&m=0204",
)
XKRX_CSAT_OVERRIDES = {
    date(2023, 11, 16): SOURCE_URLS[3],
    date(2024, 11, 14): SOURCE_URLS[4],
    date(2025, 11, 13): SOURCE_URLS[5],
}
XKRX_UNCONFIRMED = {date(2026, 11, 19): SOURCE_URLS[6]}


def _utc_text(value: object) -> str:
    converted = value.to_pydatetime()  # type: ignore[attr-defined]
    if converted.tzinfo is None:
        raise ValueError("Calendar returned a timezone-naive timestamp.")
    return cast(str, converted.astimezone(UTC).isoformat().replace("+00:00", "Z"))


def _entries(name: str, start: date, end: date) -> list[dict[str, str]]:
    calendar = exchange_calendars.get_calendar(
        name,
        start=(start - timedelta(days=10)).isoformat(),
        end=(end + timedelta(days=10)).isoformat(),
    )
    sessions = {
        session.date(): (_utc_text(row["open"]), _utc_text(row["close"]))
        for session, row in calendar.schedule.iterrows()
        if start <= session.date() <= end
    }
    result: list[dict[str, str]] = []
    current = start
    while current <= end:
        times = sessions.get(current)
        if name == "XKRX" and current in XKRX_UNCONFIRMED:
            result.append({"date": current.isoformat(), "state": "unavailable"})
        elif times is None:
            result.append({"date": current.isoformat(), "state": "closed"})
        else:
            opening, closing = times
            if name == "XKRX" and current in XKRX_CSAT_OVERRIDES:
                opening = f"{current.isoformat()}T01:00:00Z"
                closing = f"{current.isoformat()}T07:30:00Z"
            result.append(
                {
                    "date": current.isoformat(),
                    "state": "session",
                    "open_at": opening,
                    "close_at": closing,
                }
            )
        current += timedelta(days=1)
    return result


def _content_hash(calendars: dict[str, list[dict[str, str]]]) -> str:
    canonical = json.dumps(
        calendars, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(canonical).hexdigest()


def build_payload(start: date, end: date) -> dict[str, Any]:
    if end < start:
        raise ValueError("End date must not precede start date.")
    if exchange_calendars.__version__ != "4.12":
        raise RuntimeError("Generate this artifact with exchange_calendars==4.12.")
    calendars = {name: _entries(name, start, end) for name in CALENDAR_NAMES}
    return {
        "schema_version": SCHEMA_VERSION,
        "provider": "exchange_calendars",
        "provider_version": exchange_calendars.__version__,
        "generated_at": datetime.now(UTC)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "coverage": {"start": start.isoformat(), "end": end.isoformat()},
        "source_urls": list(SOURCE_URLS),
        "requirements": ["exchange_calendars==4.12"],
        "verified_overrides": [
            *[
                {
                    "calendar": "XKRX",
                    "date": day.isoformat(),
                    "open_at_local": "10:00:00 Asia/Seoul",
                    "close_at_local": "16:30:00 Asia/Seoul",
                    "reason": "CSAT session opens and closes one hour later",
                    "source_url": source_url,
                }
                for day, source_url in sorted(XKRX_CSAT_OVERRIDES.items())
            ],
            {
                "calendar": "XKRX",
                "date": "2026-11-19",
                "state": "unavailable",
                "reason": "CSAT date confirmed; exchange hours not yet verified",
                "source_url": XKRX_UNCONFIRMED[date(2026, 11, 19)],
            },
        ],
        "calendars_sha256": _content_hash(calendars),
        "calendars": calendars,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate the validated runtime XKRX/XNYS session artifact."
    )
    parser.add_argument("--start", type=date.fromisoformat, default=DEFAULT_START)
    parser.add_argument("--end", type=date.fromisoformat, default=DEFAULT_END)
    parser.add_argument(
        "--output",
        type=Path,
        default=(
            Path(__file__).parents[1]
            / "jusik"
            / "data"
            / "market_sessions_2023_2026.json"
        ),
    )
    args = parser.parse_args()
    payload = build_payload(args.start, args.end)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {args.output}")
    print(f"calendars_sha256={payload['calendars_sha256']}")


if __name__ == "__main__":
    main()
