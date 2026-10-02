"""Offline, source-bound preparation of Alpaca SIP daily price evidence."""

from __future__ import annotations

import argparse
import ctypes
import errno
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

EXPECTED_SESSIONS_SHA256 = (
    "c1b8220c3ffd5beb548ced1209b75442c8a4077dbeac032c9d4d0b025a3c514d"
)
WINDOW_START = date(2025, 8, 13)
EVALUATION_START = date(2025, 9, 11)
WINDOW_END = date(2026, 9, 11)
DAY_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
STAMP_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")
NUMBER_PATTERN = re.compile(r"[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\Z")
HASH_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
NEW_YORK = ZoneInfo("America/New_York")


class InputError(ValueError):
    """A local source or contract is malformed; no output is accepted."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    def bad_constant(value: str) -> None:
        raise InputError(f"invalid JSON numeric constant: {value}")

    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            parse_float=Decimal,
            parse_constant=bad_constant,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise InputError("cannot read JSON input") from exc


def require_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise InputError(f"{label} must be an object")
    return value


def require_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise InputError(f"{label} must be an array")
    return value


def day(value: Any) -> date:
    if not isinstance(value, str) or not DAY_PATTERN.fullmatch(value):
        raise InputError("invalid session date")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise InputError("invalid session date") from exc


def session_from_timestamp(value: Any) -> date:
    if not isinstance(value, str) or not STAMP_PATTERN.fullmatch(value):
        raise InputError("daily bar timestamp must be UTC and second-precision")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InputError("invalid daily bar timestamp") from exc
    if stamp.tzinfo is None or stamp.utcoffset() != UTC.utcoffset(stamp):
        raise InputError("daily bar timestamp must be UTC")
    local = stamp.astimezone(NEW_YORK)
    if (local.hour, local.minute, local.second, local.microsecond) != (0, 0, 0, 0):
        raise InputError("daily bar timestamp is not New York midnight")
    if stamp.hour not in (4, 5):
        raise InputError("daily bar timestamp has unexpected UTC hour")
    return local.date()


def positive_price(value: Any) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, Decimal, str)):
        raise InputError("OHLC must be a finite positive decimal")
    if isinstance(value, str) and not NUMBER_PATTERN.fullmatch(value):
        raise InputError("OHLC must be a finite positive decimal")
    try:
        price = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise InputError("OHLC must be a finite positive decimal") from exc
    if not price.is_finite() or price <= 0:
        raise InputError("OHLC must be a finite positive decimal")
    return price


def normalized_bar(
    symbol: str, value: Any, expected: set[date], source: Path, source_hash: str
) -> dict[str, Any]:
    row = require_object(value, "bar")
    session = session_from_timestamp(row.get("t"))
    if session not in expected:
        raise InputError("bar session is outside frozen session calendar")
    prices = {
        name: positive_price(row.get(key))
        for name, key in (("open", "o"), ("high", "h"), ("low", "l"), ("close", "c"))
    }
    if not (
        prices["low"] <= prices["high"]
        and prices["low"] <= prices["open"] <= prices["high"]
        and prices["low"] <= prices["close"] <= prices["high"]
    ):
        raise InputError("OHLC bounds are inconsistent")
    volume = row.get("v")
    if isinstance(volume, bool) or not isinstance(volume, int) or volume < 0:
        raise InputError("volume must be a nonnegative integer")
    return {
        "symbol": symbol,
        "session": session.isoformat(),
        **{name: str(price) for name, price in prices.items()},
        "volume": volume,
        "zero_volume": volume == 0,
        "source_path": str(source.resolve()),
        "source_sha256": source_hash,
        "evidence_only": True,
    }


def expected_sessions(path: Path, expected_hash: str) -> list[date]:
    if expected_hash != EXPECTED_SESSIONS_SHA256 or sha256(path) != expected_hash:
        raise InputError("frozen session file hash mismatch")
    fx = require_list(require_object(read_json(path), "sessions file").get("fx"), "fx")
    sessions = [day(require_object(row, "fx row").get("session")) for row in fx]
    if (
        len(sessions) != 272
        or len(set(sessions)) != 272
        or sessions != sorted(sessions)
        or sessions[0] != WINDOW_START
        or sessions[-1] != WINDOW_END
        or sum(session < EVALUATION_START for session in sessions) != 20
    ):
        raise InputError("frozen session calendar differs from the fixed window")
    return sessions


def source_contract(
    scope_path: Path,
    scope_hash: str,
    assessment_path: Path,
    batch_path: Path,
    single_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    if not HASH_PATTERN.fullmatch(scope_hash) or sha256(scope_path) != scope_hash:
        raise InputError("scope hash mismatch")
    scope = require_object(read_json(scope_path), "scope")
    protected = require_object(scope.get("protected_sha256"), "protected hashes")
    if len(protected) != 8:
        raise InputError("scope must bind eight protected sources")
    for name, value in protected.items():
        if (
            not isinstance(name, str)
            or not isinstance(value, str)
            or not HASH_PATTERN.fullmatch(value)
        ):
            raise InputError("malformed protected hash")
        if sha256(Path(name)) != value:
            raise InputError("protected source hash mismatch")
    for path in (assessment_path, batch_path, single_path):
        if protected.get(str(path.resolve())) != sha256(path):
            raise InputError("source path or hash differs from scope")
    assessment = require_object(read_json(assessment_path), "assessment")
    request = require_object(assessment.get("request"), "request")
    for field, value in {
        "provider": "Alpaca",
        "endpoint": "/v2/stocks/bars",
        "feed": "sip",
        "timeframe": "1Day",
        "start": "2025-08-13",
        "end": "2026-09-12",
        "adjustment": "raw",
        "asof": "-",
    }.items():
        if request.get(field) != value:
            raise InputError("assessment request identity differs from fixed scope")
    if type(request.get("limit")) is not int or request["limit"] != 10000:
        raise InputError("assessment request limit differs from fixed scope")
    raw_files = require_object(assessment.get("raw_files"), "raw files")
    for path in (batch_path, single_path):
        entry = require_object(raw_files.get(path.name), "raw file entry")
        if (
            entry.get("sha256") != sha256(path)
            or entry.get("bytes") != path.stat().st_size
        ):
            raise InputError("assessment raw file binding differs")
    if assessment.get("batch_next_page_token_present") is not False:
        raise InputError("assessment indicates incomplete pagination")
    return (
        scope,
        assessment,
        require_object(read_json(batch_path), "batch"),
        require_object(read_json(single_path), "single"),
    )


def build_evidence(
    scope_path: Path,
    scope_hash: str,
    assessment_path: Path,
    batch_path: Path,
    single_path: Path,
    sessions_path: Path,
    sessions_hash: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    sessions = expected_sessions(sessions_path, sessions_hash)
    scope, assessment, batch, single = source_contract(
        scope_path, scope_hash, assessment_path, batch_path, single_path
    )
    if (
        batch.get("next_page_token") is not None
        or single.get("next_page_token") is not None
    ):
        raise InputError("paginated source response is incomplete")
    if single.get("symbol") != "RAPT":
        raise InputError("single-symbol cross-check is not RAPT")
    batch_bars = require_object(batch.get("bars"), "batch bars")
    single_bars = require_list(single.get("bars"), "RAPT bars")
    if batch_bars.get("RAPT") != single_bars or len(single_bars) != 138:
        raise InputError("RAPT single response differs from batch")
    rows = require_list(assessment.get("rows"), "assessment rows")
    statuses: dict[str, str] = {}
    declared_counts: dict[str, int] = {}
    for raw_row in rows:
        row = require_object(raw_row, "assessment row")
        symbol, status, count = row.get("symbol"), row.get("status"), row.get("bars")
        if not isinstance(symbol, str) or not symbol or symbol in statuses:
            raise InputError("invalid or duplicate assessment symbol")
        if not isinstance(status, str) or status not in {
            "bars_found",
            "zero_bars",
            "hyphen_symbol_unresolved_not_queried_individually",
        }:
            raise InputError("unknown assessment status")
        if status == "bars_found":
            if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
                raise InputError("invalid assessment bar count")
            declared_counts[symbol] = count
        elif count is not None and count != 0:
            raise InputError("unexpected assessment bar count")
        if (
            status == "hyphen_symbol_unresolved_not_queried_individually"
            and "-" not in symbol
        ):
            raise InputError("unqueried symbol classification differs")
        statuses[symbol] = status
    if len(statuses) != 22 or assessment.get("tracked_count") != 22:
        raise InputError("tracked symbol set differs from assessment")
    found = {symbol for symbol, status in statuses.items() if status == "bars_found"}
    zero = {symbol for symbol, status in statuses.items() if status == "zero_bars"}
    unqueried = {
        symbol for symbol, status in statuses.items() if status.startswith("hyphen_")
    }
    if (
        len(found) != 9
        or len(zero) != 7
        or len(unqueried) != 6
        or len(found | zero) != assessment.get("plain_requested_count")
        or set(batch_bars) != found
    ):
        raise InputError("batch, requested, and unqueried sets differ")
    expected_set = set(sessions)
    bars: list[dict[str, Any]] = []
    observed: dict[str, set[date]] = {}
    batch_hash = sha256(batch_path)
    for symbol in sorted(found):
        source_rows = require_list(batch_bars[symbol], "symbol bars")
        if len(source_rows) != declared_counts[symbol]:
            raise InputError("bar count differs from assessment")
        symbol_sessions: set[date] = set()
        for source_row in source_rows:
            bar = normalized_bar(
                symbol, source_row, expected_set, batch_path, batch_hash
            )
            session = day(bar["session"])
            if session in symbol_sessions:
                raise InputError("duplicate symbol and session")
            symbol_sessions.add(session)
            bars.append(bar)
        observed[symbol] = symbol_sessions
    if len(bars) != assessment.get("batch_total_bars") or len(bars) != 1683:
        raise InputError("total bars differ from fixed evidence")
    bars.sort(key=lambda bar: (bar["symbol"], bar["session"]))
    missing_rows: list[dict[str, Any]] = []
    for symbol in sorted(statuses):
        seen = observed.get(symbol, set())
        missing = [session for session in sessions if session not in seen]
        before: list[str] = []
        interior: list[str] = []
        after: list[str] = []
        unanchored: list[str] = []
        if seen:
            first, last = min(seen), max(seen)
            for session in missing:
                (
                    before if session < first else after if session > last else interior
                ).append(session.isoformat())
        else:
            unanchored = [session.isoformat() for session in missing]
        missing_rows.append(
            {
                "symbol": symbol,
                "status": statuses[symbol],
                "observed_bar_count": len(seen),
                "missing_sessions": [session.isoformat() for session in missing],
                "before_first_bar": before,
                "between_first_and_last_bar": interior,
                "after_last_bar": after,
                "unanchored_no_bar_sessions": unanchored,
                "cause_inferred": False,
            }
        )
    inputs = {
        "scope": {"path": str(scope_path.resolve()), "sha256": scope_hash},
        "assessment": {
            "path": str(assessment_path.resolve()),
            "sha256": sha256(assessment_path),
        },
        "batch": {"path": str(batch_path.resolve()), "sha256": batch_hash},
        "single": {"path": str(single_path.resolve()), "sha256": sha256(single_path)},
        "sessions": {"path": str(sessions_path.resolve()), "sha256": sessions_hash},
    }
    normalized = {
        "contract": "alpaca-sip-price-evidence-v1",
        "evidence_only": True,
        "source_request": assessment["request"],
        "bars": bars,
    }
    missing_document = {
        "contract": "alpaca-sip-missing-sessions-v1",
        "evidence_only": True,
        "expected_sessions_sha256": sessions_hash,
        "expected_session_count": len(sessions),
        "per_symbol": missing_rows,
    }
    validation = {
        "contract": "alpaca-sip-price-validation-v1",
        "inputs": inputs,
        "protected_source_count": len(
            require_object(scope["protected_sha256"], "protected")
        ),
        "request_identity_verified": True,
        "pagination_complete": True,
        "rapt_single_matches_batch": True,
        "counts": {
            "tracked_symbols": len(statuses),
            "queried_symbols": len(found | zero),
            "with_bars": len(found),
            "zero_bars": len(zero),
            "not_queried_individually": len(unqueried),
            "bars": len(bars),
            "rapt_bars": len(single_bars),
            "expected_sessions": len(sessions),
            "warmup_sessions": sum(session < EVALUATION_START for session in sessions),
            "zero_volume_bars_retained": sum(bar["zero_volume"] for bar in bars),
        },
        "gates": {
            "security_identity_verified": False,
            "corporate_action_observed_at_verified": False,
            "historical_available_at_verified": False,
            "research_acceptance": False,
            "performance_eligible": False,
        },
        "network_requests": 0,
        "price_gap_cause_inferred": False,
    }
    return normalized, missing_document, validation


def encoded(value: dict[str, Any]) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")


def publish_no_replace(staging: Path, output_dir: Path) -> None:
    """Publish the complete directory atomically without replacing a racer."""
    renameat2 = getattr(ctypes.CDLL(None, use_errno=True), "renameat2", None)
    if renameat2 is None:
        raise InputError("atomic no-replace directory publish is unavailable")
    renameat2.argtypes = (
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    )
    renameat2.restype = ctypes.c_int
    if renameat2(-100, os.fsencode(staging), -100, os.fsencode(output_dir), 1) != 0:
        error = ctypes.get_errno()
        if error == errno.EEXIST:
            raise InputError("output directory already exists")
        raise OSError(error, os.strerror(error), str(output_dir))


def write_fresh_output(output_dir: Path, documents: dict[str, dict[str, Any]]) -> None:
    if output_dir.exists() or output_dir.is_symlink():
        raise InputError("output directory already exists")
    payloads = {name: encoded(document) for name, document in documents.items()}
    payloads["binding.json"] = encoded(
        {
            "contract": "alpaca-sip-price-binding-v1",
            "script_sha256": sha256(Path(__file__)),
            "input_sha256": documents["validation.json"]["inputs"],
            "output_sha256": {
                name: hashlib.sha256(body).hexdigest()
                for name, body in payloads.items()
            },
        }
    )
    if output_dir.exists() or output_dir.is_symlink():
        raise InputError("output directory already exists")
    staging = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}-", dir=output_dir.parent)
    )
    try:
        for name, body in payloads.items():
            with (staging / name).open("xb") as target:
                target.write(body)
        if output_dir.exists() or output_dir.is_symlink():
            raise InputError("output directory already exists")
        publish_no_replace(staging, output_dir)
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "scope",
        "assessment",
        "batch",
        "single",
        "expected-sessions",
        "output-dir",
    ):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--scope-sha256", required=True)
    parser.add_argument("--expected-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        output_dir: Path = args.output_dir
        if output_dir.exists() or output_dir.is_symlink():
            raise InputError("output directory already exists")
        inputs: tuple[Path, ...] = (
            args.scope,
            args.assessment,
            args.batch,
            args.single,
            args.expected_sessions,
        )
        resolved_output = output_dir.resolve()
        if any(
            resolved_output == path.resolve()
            or resolved_output in path.resolve().parents
            for path in inputs
        ):
            raise InputError("output directory could replace an input")
        normalized, missing, validation = build_evidence(
            args.scope,
            args.scope_sha256,
            args.assessment,
            args.batch,
            args.single,
            args.expected_sessions,
            args.expected_sha256,
        )
        write_fresh_output(
            output_dir,
            {
                "normalized-prices.json": normalized,
                "missing-sessions.json": missing,
                "validation.json": validation,
            },
        )
    except (InputError, OSError) as exc:
        print(f"input validation failed: {type(exc).__name__}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
