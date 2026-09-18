"""Offline consistency checks for stored research NAV components.

This module deliberately checks only the relationship already present in a
stored result: ``nav_krw = cash_krw + invested_krw``.  It does not infer a
calendar, quantities, prices, cash flows, benchmark, or future observations.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Final, Literal

MAX_INPUT_BYTES: Final = 20 * 1024 * 1024
MAX_EQUITY_ROWS: Final = 300
MAX_DECIMAL_DIGITS: Final = 1_000
MAX_DECIMAL_EXPONENT: Final = 10_000
TOLERANCE_KRW: Final = Decimal("1")
TASK_SLUG: Final = "r2-nav-components-7284"
_DATE_PATTERN: Final = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
_SHA_PATTERN: Final = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED_COMPONENTS: Final = ("cash_krw", "invested_krw", "nav_krw")


class ReconciliationError(ValueError):
    """Raised when a stored run does not satisfy the input contract."""


@dataclass(frozen=True)
class ResidualRow:
    session: date
    cash_krw: Decimal
    invested_krw: Decimal
    nav_krw: Decimal
    residual_krw: Decimal
    passed: bool

    def as_artifact(self) -> dict[str, object]:
        return {
            "session": self.session.isoformat(),
            "cash_krw": str(self.cash_krw),
            "invested_krw": str(self.invested_krw),
            "nav_krw": str(self.nav_krw),
            "residual_krw": str(self.residual_krw),
            "passed": self.passed,
        }


@dataclass(frozen=True)
class ReconciliationReport:
    rows: tuple[ResidualRow, ...]
    max_absolute_residual_krw: Decimal
    failed_sessions: tuple[date, ...]
    ordered: bool = True
    calendar_completeness: Literal["unavailable"] = "unavailable"
    economic_evaluation: Literal["not-evaluated"] = "not-evaluated"
    independent_accounting: Literal["unavailable"] = "unavailable"
    benchmark_evaluation: Literal["blocked"] = "blocked"
    future_evaluation: Literal["blocked"] = "blocked"
    full_r2_05_checkbox: Literal["untouched"] = "untouched"

    @property
    def status(self) -> Literal["passed", "failed"]:
        return "passed" if not self.failed_sessions else "failed"

    def residual_artifact(self, *, source_sha256: str) -> dict[str, object]:
        _validate_sha(source_sha256)
        return {
            "schema_version": 1,
            "task_slug": TASK_SLUG,
            "source_sha256": source_sha256,
            "status": self.status,
            "tolerance_krw": str(TOLERANCE_KRW),
            "rows": len(self.rows),
            "unique_sessions": len(self.rows),
            "ordered": self.ordered,
            "max_absolute_residual_krw": str(self.max_absolute_residual_krw),
            "failed_sessions": [item.isoformat() for item in self.failed_sessions],
            "residuals": [item.as_artifact() for item in self.rows],
        }

    def coverage_artifact(self, *, source_sha256: str) -> dict[str, object]:
        _validate_sha(source_sha256)
        first = self.rows[0].session.isoformat() if self.rows else None
        last = self.rows[-1].session.isoformat() if self.rows else None
        return {
            "schema_version": 1,
            "task_slug": TASK_SLUG,
            "source_sha256": source_sha256,
            "observed_sessions": len(self.rows),
            "unique_sessions": len(self.rows),
            "first_session": first,
            "last_session": last,
            "ordered": self.ordered,
            "calendar_completeness": self.calendar_completeness,
            "independent_accounting": self.independent_accounting,
            "economic_evaluation": self.economic_evaluation,
            "benchmark_evaluation": self.benchmark_evaluation,
            "future_evaluation": self.future_evaluation,
            "full_r2_05_checkbox": self.full_r2_05_checkbox,
            "note": (
                "Observed sessions are the stored market sessions; no calendar "
                "completeness is claimed."
            ),
        }


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ReconciliationError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _validate_sha(value: str) -> None:
    if not _SHA_PATTERN.fullmatch(value):
        raise ReconciliationError(
            "expected SHA-256 must be 64 lowercase hex characters"
        )


def _finite_exponent(value: Decimal, *, field: str) -> int:
    exponent = value.as_tuple().exponent
    if not isinstance(exponent, int):
        raise ReconciliationError(f"{field} must have a finite decimal exponent")
    return exponent


def _parse_decimal(value: object, *, field: str) -> Decimal:
    if value is None or isinstance(value, bool):
        raise ReconciliationError(f"{field} must be a finite non-negative number")
    if isinstance(value, Decimal):
        parsed = value
    elif isinstance(value, str):
        if not value.strip():
            raise ReconciliationError(f"{field} must be a finite non-negative number")
        try:
            parsed = Decimal(value)
        except (ValueError, ArithmeticError) as exc:
            raise ReconciliationError(f"{field} is not numeric") from exc
    elif isinstance(value, int):
        parsed = Decimal(value)
    else:
        raise ReconciliationError(
            f"{field} must be a Decimal-compatible string or number"
        )
    if not parsed.is_finite() or parsed < 0:
        raise ReconciliationError(f"{field} must be a finite non-negative number")
    tup = parsed.as_tuple()
    exponent = _finite_exponent(parsed, field=field)
    if len(tup.digits) > MAX_DECIMAL_DIGITS or abs(exponent) > MAX_DECIMAL_EXPONENT:
        raise ReconciliationError(f"{field} exceeds decimal bounds")
    return parsed


def _parse_session(value: object, *, row_number: int) -> date:
    if not isinstance(value, str) or _DATE_PATTERN.fullmatch(value) is None:
        raise ReconciliationError(f"equity[{row_number}].session must be YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ReconciliationError(
            f"equity[{row_number}].session is not a valid date"
        ) from exc


def _exact_residual(nav: Decimal, cash: Decimal, invested: Decimal) -> Decimal:
    values = (nav, cash, invested)
    max_adjusted = max(item.adjusted() for item in values)
    min_exponent = min(_finite_exponent(item, field="component") for item in values)
    precision = max(1, max_adjusted - min_exponent + 3)
    with localcontext() as context:
        context.prec = precision
        return nav - cash - invested


def _equity_from_payload(payload: object) -> list[object]:
    if not isinstance(payload, dict):
        raise ReconciliationError("run payload must be a JSON object")
    result = payload.get("result")
    if not isinstance(result, dict):
        raise ReconciliationError("run payload must contain an object result")
    equity = result.get("equity")
    if not isinstance(equity, list) or not equity:
        raise ReconciliationError("result.equity must be a non-empty array")
    if len(equity) > MAX_EQUITY_ROWS:
        raise ReconciliationError(f"result.equity exceeds {MAX_EQUITY_ROWS} rows")
    return equity


def reconcile_run_payload(
    payload: object, *, source_sha256: str
) -> ReconciliationReport:
    """Validate and reconcile a decoded stored run payload."""
    _validate_sha(source_sha256)
    equity = _equity_from_payload(payload)
    rows: list[ResidualRow] = []
    previous: date | None = None
    for index, raw_row in enumerate(equity):
        if not isinstance(raw_row, dict):
            raise ReconciliationError(f"equity[{index}] must be an object")
        session = _parse_session(raw_row.get("session"), row_number=index)
        if previous is not None and session <= previous:
            relation = "duplicate" if session == previous else "reverse chronological"
            raise ReconciliationError(
                f"equity[{index}] has {relation} session {session}"
            )
        previous = session
        values = {
            field: _parse_decimal(raw_row.get(field), field=f"equity[{index}].{field}")
            for field in _REQUIRED_COMPONENTS
        }
        residual = _exact_residual(
            values["nav_krw"], values["cash_krw"], values["invested_krw"]
        )
        passed = residual.copy_abs() <= TOLERANCE_KRW
        rows.append(
            ResidualRow(
                session=session,
                residual_krw=residual,
                passed=passed,
                **values,
            )
        )
    max_residual = max(
        (item.residual_krw.copy_abs() for item in rows), default=Decimal(0)
    )
    failed = tuple(item.session for item in rows if not item.passed)
    return ReconciliationReport(
        rows=tuple(rows),
        max_absolute_residual_krw=max_residual,
        failed_sessions=failed,
    )


def reconcile_json_bytes(raw: bytes, *, expected_sha256: str) -> ReconciliationReport:
    """Decode bounded JSON bytes and reconcile them against a pinned SHA."""
    if len(raw) > MAX_INPUT_BYTES:
        raise ReconciliationError(f"input exceeds {MAX_INPUT_BYTES} bytes")
    actual = hashlib.sha256(raw).hexdigest()
    _validate_sha(expected_sha256)
    if actual != expected_sha256:
        raise ReconciliationError("input SHA-256 does not match the pinned run SHA")
    try:
        payload = json.loads(
            raw,
            object_pairs_hook=_reject_duplicate_keys,
            parse_int=Decimal,
            parse_float=Decimal,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ReconciliationError("input is not valid JSON") from exc
    return reconcile_run_payload(payload, source_sha256=actual)


def _paths_alias(first: Path, second: Path) -> bool:
    if first.resolve() == second.resolve():
        return True
    if not first.exists() or not second.exists():
        return False
    try:
        return os.path.samefile(first, second)
    except OSError:
        return False


def _validate_artifact_paths(
    source: Path, residual_output: Path, coverage_output: Path
) -> None:
    paths = (
        ("residual output", residual_output),
        ("coverage output", coverage_output),
    )
    for label, output in paths:
        if _paths_alias(source, output):
            raise ReconciliationError(f"{label} must not overwrite the source run")
    if _paths_alias(residual_output, coverage_output):
        raise ReconciliationError("artifact outputs must be separate files")


def _write_artifact(path: Path, artifact: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(
        description="Offline stored NAV component consistency check"
    )
    command.add_argument("--input", type=Path, required=True)
    command.add_argument(
        "--expected-sha256",
        "--run-sha256",
        "--source-sha256",
        dest="expected_sha256",
        required=True,
        help="pinned SHA-256 of the input run",
    )
    command.add_argument(
        "--residual-output",
        "--output",
        dest="residual_output",
        type=Path,
        required=True,
    )
    command.add_argument("--coverage-output", type=Path, required=True)
    return command


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        source = args.input.resolve()
        _validate_artifact_paths(source, args.residual_output, args.coverage_output)
        raw = source.read_bytes()
        actual_sha = hashlib.sha256(raw).hexdigest()
        report = reconcile_json_bytes(raw, expected_sha256=args.expected_sha256)
        _write_artifact(
            args.residual_output,
            report.residual_artifact(source_sha256=actual_sha),
        )
        _write_artifact(
            args.coverage_output,
            report.coverage_artifact(source_sha256=actual_sha),
        )
    except (OSError, ReconciliationError) as exc:
        print(f"reconciliation rejected: {exc}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            report.residual_artifact(source_sha256=actual_sha), ensure_ascii=False
        )
    )
    return 0 if report.status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
