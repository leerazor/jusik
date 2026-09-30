"""Bounded, diagnostic-only comparison of ECOS and frozen FRED FX observations."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import sys
from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal

import httpx

Status = Literal["observed", "missing", "error"]
MAX_BASELINE_BYTES = 2_000_000
MAX_RESPONSE_BYTES = 65_536
DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
SHA_PATTERN = re.compile(r"[0-9a-fA-F]{64}\Z")
ECOS_PATH = "StatisticSearch/sample/json/kr/1/10/731Y001/D/{day}/{day}/0000001"
ECOS_ORIGIN = "https://ecos.bok.or.kr/api/"


class InputError(ValueError):
    """Invalid local input; no provider request should be made."""


def _day(value: str) -> date:
    if not DATE_PATTERN.fullmatch(value):
        raise InputError("날짜는 YYYY-MM-DD 형식이어야 합니다")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise InputError("유효하지 않은 날짜입니다") from exc


def _positive_decimal(value: str) -> Decimal:
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("invalid rate") from exc
    if not number.is_finite() or number <= 0:
        raise ValueError("invalid rate")
    return number


def _baseline(body: bytes) -> dict[date, Decimal | None]:
    try:
        rows = csv.reader(
            io.StringIO(body.decode("utf-8-sig"), newline=""), strict=True
        )
        if next(rows, None) != ["observation_date", "DEXKOUS"]:
            raise InputError("FRED CSV 헤더가 올바르지 않습니다")
        observations: dict[date, Decimal | None] = {}
        for row in rows:
            if row == ["", ""]:
                continue
            if len(row) != 2:
                raise InputError("FRED CSV 행이 올바르지 않습니다")
            session = _day(row[0])
            if session in observations:
                raise InputError("FRED CSV에 중복 날짜가 있습니다")
            value = row[1].strip()
            try:
                observations[session] = (
                    None if value in {"", "."} else _positive_decimal(value)
                )
            except ValueError as exc:
                raise InputError("FRED CSV 환율이 올바르지 않습니다") from exc
    except (UnicodeDecodeError, csv.Error) as exc:
        raise InputError("FRED CSV 형식이 올바르지 않습니다") from exc
    if not observations:
        raise InputError("FRED CSV에 관측 행이 없습니다")
    return observations


def _prepare(
    baseline: Path, baseline_sha256: str, dates: list[str], output_dir: Path
) -> tuple[bytes, dict[date, Decimal | None], list[date]]:
    if not SHA_PATTERN.fullmatch(baseline_sha256):
        raise InputError("baseline SHA-256 형식이 올바르지 않습니다")
    if not 1 <= len(dates) <= 10:
        raise InputError("날짜는 1개 이상 10개 이하로 지정해야 합니다")
    sessions = [_day(value) for value in dates]
    if len(set(sessions)) != len(sessions):
        raise InputError("날짜를 중복 지정할 수 없습니다")
    if output_dir.exists() or output_dir.is_symlink():
        raise InputError("출력 디렉터리는 새 경로여야 합니다")
    if not output_dir.parent.is_dir() or output_dir.parent.is_symlink():
        raise InputError("출력 상위 디렉터리는 기존 일반 디렉터리여야 합니다")
    if not baseline.is_file():
        raise InputError("baseline CSV 파일을 찾을 수 없습니다")
    if baseline.stat().st_size > MAX_BASELINE_BYTES:
        raise InputError("baseline CSV가 허용 크기를 넘습니다")
    body = baseline.read_bytes()
    if len(body) > MAX_BASELINE_BYTES:
        raise InputError("baseline CSV가 허용 크기를 넘습니다")
    if hashlib.sha256(body).hexdigest() != baseline_sha256.lower():
        raise InputError("baseline SHA-256이 일치하지 않습니다")
    return body, _baseline(body), sessions


def _fetch(
    client: httpx.Client, session: date, now: Callable[[], datetime]
) -> tuple[Status, Decimal | None, str | None, bytes | None, str]:
    day = session.strftime("%Y%m%d")
    url = ECOS_ORIGIN + ECOS_PATH.format(day=day)
    fetched_at = now().astimezone(UTC).isoformat()
    try:
        with client.stream("GET", url, follow_redirects=False) as response:
            if response.status_code != 200:
                return "error", None, "http_error", None, fetched_at
            body = bytearray()
            for chunk in response.iter_bytes(chunk_size=8192):
                body.extend(chunk)
                if len(body) > MAX_RESPONSE_BYTES:
                    return "error", None, "response_too_large", None, fetched_at
    except httpx.HTTPError:
        return "error", None, "transport_error", None, fetched_at
    raw = bytes(body)
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return "error", None, "invalid_json", None, fetched_at
    if not isinstance(payload, dict):
        return "error", None, "invalid_envelope", None, fetched_at
    envelope = payload.get("StatisticSearch")
    if not isinstance(envelope, dict):
        result = payload.get("RESULT")
        if isinstance(result, dict) and result.get("CODE") == "INFO-200":
            return "missing", None, "provider_no_data", None, fetched_at
        return "error", None, "provider_error", None, fetched_at
    rows = envelope.get("row")
    count = envelope.get("list_total_count")
    if (
        not isinstance(rows, list)
        or len(rows) != 1
        or type(count) not in (int, str)
        or count not in (1, "1")
        or not isinstance(rows[0], dict)
    ):
        return "error", None, "invalid_rows", None, fetched_at
    row = rows[0]
    if (
        row.get("STAT_CODE") != "731Y001"
        or row.get("ITEM_CODE1") != "0000001"
        or row.get("TIME") != day
        or row.get("UNIT_NAME") != "원"
        or not isinstance(row.get("DATA_VALUE"), str)
    ):
        return "error", None, "identity_mismatch", None, fetched_at
    try:
        rate = _positive_decimal(row["DATA_VALUE"])
    except ValueError:
        return "error", None, "invalid_value", None, fetched_at
    return "observed", rate, None, raw, fetched_at


def _write_new(path: Path, body: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(body)


def run_comparison(
    *,
    baseline: Path,
    baseline_sha256: str,
    dates: list[str],
    output_dir: Path,
    client: httpx.Client | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> dict[str, Any]:
    """Validate local inputs before any GET, then create a new diagnostic report."""
    _, fred, sessions = _prepare(baseline, baseline_sha256, dates, output_dir)
    output_dir.mkdir(mode=0o700)
    own_client = client is None
    http_client = client or httpx.Client(
        timeout=httpx.Timeout(10.0),
        follow_redirects=False,
        trust_env=False,
        verify=True,
    )
    rows: list[dict[str, Any]] = []
    try:
        for session in sessions:
            status, ecos, reason, raw, fetched_at = _fetch(http_client, session, now)
            baseline_state = (
                "absent"
                if session not in fred
                else "missing"
                if fred[session] is None
                else "observed"
            )
            baseline_value = fred.get(session)
            delta = (
                ecos - baseline_value if ecos is not None and baseline_value else None
            )
            raw_sha = hashlib.sha256(raw).hexdigest() if raw is not None else None
            raw_file = f"ecos-{session.isoformat()}.json" if raw is not None else None
            if raw is not None and raw_file is not None:
                _write_new(output_dir / raw_file, raw)
            rows.append(
                {
                    "date": session.isoformat(),
                    "fred_status": baseline_state,
                    "fred_krw_per_usd": str(baseline_value) if baseline_value else None,
                    "ecos_status": status,
                    "ecos_krw_per_usd": str(ecos) if ecos else None,
                    "reason": reason,
                    "delta_krw_per_usd": str(delta) if delta is not None else None,
                    "delta_pct_vs_fred": str(delta / baseline_value * 100)
                    if delta is not None and baseline_value
                    else None,
                    "raw_file": raw_file,
                    "raw_sha256": raw_sha,
                    "fetched_at": fetched_at,
                    "publication_at": None,
                    "vintage": None,
                    "point_in_time_verified": False,
                    "eligible_for_performance": False,
                }
            )
    finally:
        if own_client:
            http_client.close()
    report: dict[str, Any] = {
        "schema": "ecos-fx-diagnostic-v1",
        "baseline_source": "FRED DEXKOUS, 뉴욕 정오 매입환율",
        "baseline_sha256": baseline_sha256.lower(),
        "ecos_source": "ECOS 731Y001/D/0000001, 원/달러 매매기준율",
        "comparison_note": (
            "같은 날짜가 같은 고시 시점을 뜻하지 않습니다. "
            "차이는 진단값이며 오류나 성과가 아닙니다."
        ),
        "point_in_time_verified": False,
        "eligible_for_performance": False,
        "rows": rows,
    }
    _write_new(
        output_dir / "comparison.json",
        (
            json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        ).encode(),
    )
    lines = [
        "# ECOS·FRED 원/달러 진단 비교",
        "",
        "FRED DEXKOUS는 뉴욕 정오 매입환율, ECOS는 원/달러 매매기준율입니다.",
        "같은 날짜가 같은 고시 시점을 뜻하지 않습니다.",
        "차이는 진단값이며 오류·투자 성과가 아닙니다.",
        "공표 시각과 vintage는 미확인이고 PIT·성과 사용은 불가합니다.",
        "",
        "| 날짜 | FRED | ECOS | 차이 (원) | 차이 (%) | 상태 |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            (
                "| {date} | {fred_krw_per_usd} | {ecos_krw_per_usd} | "
                "{delta_krw_per_usd} | {delta_pct_vs_fred} | "
                "FRED {fred_status}, ECOS {ecos_status}{reason_suffix} |"
            ).format(
                **{
                    key: value if value is not None else "—"
                    for key, value in row.items()
                },
                reason_suffix=f" ({row['reason']})" if row["reason"] else "",
            )
        )
    _write_new(output_dir / "comparison.md", ("\n".join(lines) + "\n").encode())
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ECOS·FRED 원/달러 진단 비교")
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--baseline-sha256", required=True)
    parser.add_argument("--dates", nargs="+", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        run_comparison(
            baseline=args.baseline,
            baseline_sha256=args.baseline_sha256,
            dates=args.dates,
            output_dir=args.output_dir,
        )
    except (InputError, OSError) as exc:
        print(f"비교 실패: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
