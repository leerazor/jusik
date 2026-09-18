"""Read-only performance metrics adapter for the corrected portfolio bundle.

The adapter binds the corrected time-evidence bundle to its independently
verified accounting report before projecting NAV.  It never runs a strategy,
simulation, broker, collector, or network request.  Daily metrics use the
last causally completed NAV in each UTC date; drawdown and Calmar retain every
stored NAV row.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Final

from .market_performance_metrics import (
    CompletenessEvidence,
    CostInclusionEvidence,
    DataSource,
    NAVPoint,
    PerformanceInput,
    PerformanceReport,
    RiskFreeEvidence,
    evaluate_performance,
)
from .market_performance_policy import load_calculation_policy
from .research_portfolio_accounting_evidence import (
    CORRECTED_MANIFEST_SHA256,
    EXPECTED_NAV,
    AccountingEvidenceError,
    verify_accounting_bundle,
)
from .research_portfolio_accounting_evidence import (
    SOURCE_SHA256 as ACCOUNTING_VERIFIER_SOURCE_SHA256,
)

SCHEMA: Final = "portfolio-performance-metrics-envelope/v1"
RESULT_SCHEMA: Final = "market-performance-metrics-result/v1"
BUNDLE_PATH: Final = Path(
    "/home/kwl/.local/share/jusik/portfolio-audit/"
    "portfolio-calendar-2026-krx-holiday-correction/run-v3"
)
ACCOUNTING_REPORT_PATH: Final = Path(
    "/home/kwl/.local/share/jusik/portfolio-audit/"
    "portfolio-calendar-2026-krx-holiday-correction/accounting-report.json"
)
ACCOUNTING_REPORT_SHA256: Final = (
    "2f0378214f622b069aa8d2f679ded7bc96600f5348fe91ed5e69b0f283ba9847"
)
EXPECTED_DAILY_NAV: Final = 614
EXPECTED_TRADE_COUNT: Final = 171
MAX_ARTIFACT_BYTES: Final = 20 * 1024 * 1024
MAX_REPORT_BYTES: Final = 2 * 1024 * 1024
MAX_TOTAL_READ_BYTES: Final = 50 * 1024 * 1024
MAX_DEPTH: Final = 64
MAX_COLLECTION: Final = 20_000
MAX_OBJECT_KEYS: Final = 2_000
MAX_DECIMAL_DIGITS: Final = 80
MAX_DECIMAL_ABS: Final = Decimal("1e30")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ARTIFACTS: Final = frozenset(
    {
        "calendar.json",
        "config.json",
        "input.json",
        "simulation.json",
        "time-evidence.json",
    }
)


class PortfolioPerformanceError(ValueError):
    """Stable fail-closed adapter error."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _shape(value: object, depth: int = 0) -> None:
    if depth > MAX_DEPTH:
        raise PortfolioPerformanceError("depth_limit")
    if isinstance(value, Mapping):
        if len(value) > MAX_OBJECT_KEYS:
            raise PortfolioPerformanceError("object_key_limit")
        for key, child in value.items():
            if not isinstance(key, str):
                raise PortfolioPerformanceError("malformed_input")
            _shape(child, depth + 1)
    elif isinstance(value, list):
        if len(value) > MAX_COLLECTION:
            raise PortfolioPerformanceError("collection_limit")
        for child in value:
            _shape(child, depth + 1)
    elif isinstance(value, Decimal):
        if not value.is_finite() or len(value.as_tuple().digits) > MAX_DECIMAL_DIGITS:
            raise PortfolioPerformanceError("numeric_limit")
        if abs(value) > MAX_DECIMAL_ABS:
            raise PortfolioPerformanceError("numeric_limit")


class _DuplicateKey(ValueError):
    pass


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKey(key)
        result[key] = value
    return result


def _reject_constant(value: str) -> object:
    raise ValueError(value)


def _json(raw: bytes, label: str) -> dict[str, object]:
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_int=Decimal,
            parse_float=Decimal,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError):
        raise PortfolioPerformanceError(f"{label}_malformed") from None
    if not isinstance(value, dict):
        raise PortfolioPerformanceError(f"{label}_malformed")
    _shape(value)
    return value


def _bounded_read(path: Path, limit: int, code_prefix: str) -> bytes:
    """Read one regular file with finite bytes and replacement protections."""
    try:
        before = path.lstat()
        if path.is_symlink() or not stat.S_ISREG(before.st_mode):
            raise PortfolioPerformanceError("unsafe_path")
        if before.st_size > limit:
            raise PortfolioPerformanceError(f"{code_prefix}_too_large")
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            opened = os.fstat(descriptor)
            if not stat.S_ISREG(opened.st_mode) or (
                opened.st_dev,
                opened.st_ino,
            ) != (before.st_dev, before.st_ino):
                raise PortfolioPerformanceError("file_replaced")
            raw = bytearray()
            while len(raw) <= limit:
                chunk = os.read(descriptor, min(1024 * 1024, limit + 1 - len(raw)))
                if not chunk:
                    break
                raw.extend(chunk)
            after = os.fstat(descriptor)
        finally:
            os.close(descriptor)
    except PortfolioPerformanceError:
        raise
    except OSError:
        raise PortfolioPerformanceError(f"{code_prefix}_unavailable") from None
    if len(raw) > limit or (before.st_dev, before.st_ino, before.st_size) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
    ):
        raise PortfolioPerformanceError("file_replaced")
    return bytes(raw)


def _text(value: object, code: str = "malformed_input") -> str:
    if not isinstance(value, str) or not value:
        raise PortfolioPerformanceError(code)
    return value


def _sha(value: object, code: str = "malformed_input") -> str:
    text = _text(value, code)
    if _SHA256.fullmatch(text) is None:
        raise PortfolioPerformanceError(code)
    return text


def _decimal(value: object, code: str = "malformed_input") -> Decimal:
    if isinstance(value, bool) or value is None:
        raise PortfolioPerformanceError(code)
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise PortfolioPerformanceError(code) from None
    if not result.is_finite():
        raise PortfolioPerformanceError("nonfinite_value")
    return result


def _mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise PortfolioPerformanceError("malformed_input")
    return value


def _list(value: object) -> list[object]:
    if not isinstance(value, list):
        raise PortfolioPerformanceError("malformed_input")
    return value


def _utc(value: object) -> datetime:
    text = _text(value)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        raise PortfolioPerformanceError("invalid_utc_timestamp") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise PortfolioPerformanceError("invalid_utc_timestamp")
    return parsed.astimezone(UTC)


def _digest(value: object) -> str:
    try:
        raw = json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    except (TypeError, ValueError):
        raise PortfolioPerformanceError("digest_invalid") from None
    return hashlib.sha256(raw).hexdigest()


def _bundle_root(bundle_dir: Path) -> Path:
    try:
        if bundle_dir.is_symlink() or not bundle_dir.is_dir():
            raise PortfolioPerformanceError("unsafe_path")
        return bundle_dir.resolve(strict=True)
    except OSError:
        raise PortfolioPerformanceError("bundle_unavailable") from None


def _read_artifact(
    root: Path, name: str, expected_sha: str
) -> tuple[dict[str, object], int]:
    path = root / name
    raw = _bounded_read(path, MAX_ARTIFACT_BYTES, "artifact")
    if hashlib.sha256(raw).hexdigest() != expected_sha:
        raise PortfolioPerformanceError("artifact_sha_mismatch")
    return _json(raw, name.replace(".", "_")), len(raw)


def _verify_chain(
    bundle_dir: Path, accounting_report_path: Path
) -> tuple[
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
    int,
]:
    root = _bundle_root(bundle_dir)
    manifest_raw = _bounded_read(root / "manifest.json", MAX_REPORT_BYTES, "manifest")
    if hashlib.sha256(manifest_raw).hexdigest() != CORRECTED_MANIFEST_SHA256:
        raise PortfolioPerformanceError("manifest_sha_mismatch")
    manifest = _json(manifest_raw, "manifest")
    if (
        manifest.get("schema_version") != Decimal(1)
        or manifest.get("execution_time_policy") != "official"
        or manifest.get("policy_version") != "forward-simulation-time-evidence-v1"
    ):
        raise PortfolioPerformanceError("manifest_identity_mismatch")
    artifacts = _mapping(manifest.get("artifacts"))
    if set(artifacts) != _ARTIFACTS:
        raise PortfolioPerformanceError("manifest_artifact_mismatch")
    input_sha = _sha(_mapping(artifacts["input.json"]).get("sha256"))
    calendar_sha = _sha(_mapping(artifacts["calendar.json"]).get("sha256"))
    calendar_identity = _mapping(manifest.get("calendar"))
    if (
        manifest.get("source_sha256") != input_sha
        or calendar_identity.get("bytes_sha256") != calendar_sha
        or calendar_identity.get("provider") != "exchange_calendars"
        or calendar_identity.get("provider_version") != "4.12"
    ):
        raise PortfolioPerformanceError("manifest_source_identity_mismatch")
    loaded: dict[str, dict[str, object]] = {}
    total = len(manifest_raw)
    for name in sorted(_ARTIFACTS):
        item = _mapping(artifacts.get(name))
        if item.get("path") != name:
            raise PortfolioPerformanceError("manifest_artifact_mismatch")
        expected_sha = _sha(item.get("sha256"))
        size = item.get("size")
        if isinstance(size, bool) or not isinstance(size, (int, Decimal)) or size < 0:
            raise PortfolioPerformanceError("manifest_artifact_mismatch")
        value, size = _read_artifact(root, name, expected_sha)
        if item.get("size") != size:
            raise PortfolioPerformanceError("artifact_size_mismatch")
        total += size
        if total > MAX_TOTAL_READ_BYTES:
            raise PortfolioPerformanceError("bundle_too_large")
        loaded[name] = value
    report_raw = _bounded_read(accounting_report_path, MAX_REPORT_BYTES, "report")
    if total + len(report_raw) > MAX_TOTAL_READ_BYTES:
        raise PortfolioPerformanceError("bundle_too_large")
    if hashlib.sha256(report_raw).hexdigest() != ACCOUNTING_REPORT_SHA256:
        raise PortfolioPerformanceError("accounting_report_sha_mismatch")
    report = _json(report_raw, "accounting_report")
    report_artifacts = _mapping(report.get("artifacts"))
    expected_report_artifacts = {
        **{name: _sha(_mapping(artifacts[name]).get("sha256")) for name in _ARTIFACTS},
        "manifest.json": CORRECTED_MANIFEST_SHA256,
    }
    if expected_report_artifacts != dict(report_artifacts):
        raise PortfolioPerformanceError("accounting_artifact_identity_mismatch")
    if (
        report.get("schema") != "portfolio-modeled-accounting-evidence/v1"
        or report.get("status") != "verified"
        or report.get("grade") != "approximate"
        or report.get("economic_evaluation") != "not-evaluated"
        or report.get("nav_count") != Decimal(EXPECTED_NAV)
        or report.get("consumed_nav_count") != Decimal(EXPECTED_NAV)
        or report.get("max_residual_krw") != "0"
        or report.get("verifier_source_sha256") != ACCOUNTING_VERIFIER_SOURCE_SHA256
    ):
        raise PortfolioPerformanceError("accounting_identity_mismatch")
    simulation = loaded["simulation.json"]
    simulation_metrics = _mapping(simulation.get("metrics"))
    if simulation_metrics.get("trade_count") != Decimal(EXPECTED_TRADE_COUNT):
        raise PortfolioPerformanceError("simulation_trade_count_mismatch")
    return (
        manifest,
        report,
        loaded["time-evidence.json"],
        simulation,
        total + len(report_raw),
    )


@dataclass(frozen=True)
class NAVProjection:
    """Full chronology and deterministic UTC daily last-causal projection."""

    full: tuple[NAVPoint, ...]
    daily: tuple[NAVPoint, ...]


def project_nav(value: object, *, expected_count: int = EXPECTED_NAV) -> NAVProjection:
    """Project serialized NAV rows without filling holidays or changing values."""
    rows = _list(_mapping(value).get("nav"))
    if len(rows) != expected_count:
        raise PortfolioPerformanceError("nav_count_mismatch")
    full: list[NAVPoint] = []
    last_by_day: dict[date, NAVPoint] = {}
    previous: datetime | None = None
    for index, raw in enumerate(rows):
        item = _mapping(raw)
        if item.get("nav_index") != Decimal(index):
            raise PortfolioPerformanceError("nav_order_mismatch")
        at = _utc(item.get("evaluation_at"))
        nav = _decimal(item.get("nav_krw"), "invalid_nav")
        if nav <= 0:
            raise PortfolioPerformanceError("non_positive_nav")
        if previous is not None and at <= previous:
            raise PortfolioPerformanceError("nav_order_mismatch")
        point = NAVPoint(at, nav)
        full.append(point)
        last_by_day[at.date()] = point
        previous = at
    daily = tuple(last_by_day[key] for key in sorted(last_by_day))
    if not daily:
        raise PortfolioPerformanceError("nav_empty")
    return NAVProjection(tuple(full), daily)


def _performance_input(
    points: Sequence[NAVPoint], initial: Decimal, anchor: datetime, policy_id: str
) -> PerformanceInput:
    return PerformanceInput(
        initial_capital=initial,
        initial_capital_at=anchor,
        nav_points=tuple(points),
        data_grade="approximate",
        data_source=DataSource("corrected-portfolio-time-evidence-bundle"),
        completeness=CompletenessEvidence(
            "complete",
            ("independent modeled accounting",),
            ("corrected exchange calendar",),
        ),
        cost_inclusion=CostInclusionEvidence(
            True, ("independent modeled accounting report",)
        ),
        # KOFR evidence is intentionally absent; evaluator returns a stable
        # unavailable reason for Sharpe while other metrics remain available.
        risk_free=RiskFreeEvidence(Decimal(0), ()),
        calculation_policy=policy_id,
    )


def combine_projection_metrics(
    projection: NAVProjection, *, initial: Decimal, anchor: datetime, policy_id: str
) -> PerformanceReport:
    """Use daily rows for return/CAGR/Sharpe and all rows for MDD/Calmar."""
    daily = evaluate_performance(
        _performance_input(projection.daily, initial, anchor, policy_id)
    )
    full = evaluate_performance(
        _performance_input(projection.full, initial, anchor, policy_id)
    )
    return PerformanceReport(
        data_grade=daily.data_grade,
        data_source=daily.data_source,
        initial_capital_at=anchor,
        calculation_policy=policy_id,
        total_net_return=daily.total_net_return,
        cagr=daily.cagr,
        maximum_drawdown=full.maximum_drawdown,
        sharpe=daily.sharpe,
        calmar=full.calmar,
        hard_filter=full.hard_filter,
    )


def _iso_duration(seconds: int) -> str:
    duration = timedelta(seconds=seconds)
    days = duration.days
    remainder = duration.seconds
    hours, remainder = divmod(remainder, 60 * 60)
    minutes, secs = divmod(remainder, 60)
    if days:
        return f"P{days}DT{hours}H{minutes}M{secs}S"
    return f"PT{hours}H{minutes}M{secs}S"


def maximum_mdd_recovery_duration(
    points: Sequence[NAVPoint], *, initial: Decimal, anchor: datetime
) -> dict[str, object]:
    """Return the longest completed peak-to-recovery duration in UTC seconds."""
    if not points:
        return {
            "availability": "unavailable",
            "utc_seconds": None,
            "iso_duration": None,
            "reason": "missing_nav_chronology",
        }
    peak = initial
    peak_at = anchor.astimezone(UTC)
    underwater = False
    maximum = 0
    for point in points:
        at = point.timestamp.astimezone(UTC)
        if point.nav < peak:
            underwater = True
            continue
        if underwater:
            elapsed = at - peak_at
            if elapsed.days < 0 or elapsed.microseconds:
                return {
                    "availability": "unavailable",
                    "utc_seconds": None,
                    "iso_duration": None,
                    "reason": "invalid_recovery_timestamp",
                }
            maximum = max(maximum, elapsed.days * 86_400 + elapsed.seconds)
            underwater = False
        if point.nav >= peak:
            peak = point.nav
            peak_at = at
    if maximum == 0 and underwater:
        return {
            "availability": "unavailable",
            "utc_seconds": None,
            "iso_duration": None,
            "reason": "mdd_not_recovered",
        }
    return {
        "availability": "available",
        "utc_seconds": maximum,
        "iso_duration": _iso_duration(maximum),
        "reason": None,
    }


def evaluate_corrected_bundle(
    bundle_dir: Path = BUNDLE_PATH,
    accounting_report_path: Path = ACCOUNTING_REPORT_PATH,
) -> dict[str, object]:
    """Verify and evaluate the registered corrected bundle exactly once."""
    manifest, accounting, time_evidence, simulation, bytes_read = _verify_chain(
        bundle_dir, accounting_report_path
    )
    try:
        verified = verify_accounting_bundle(
            bundle_dir, expected_manifest_sha256=CORRECTED_MANIFEST_SHA256
        )
    except AccountingEvidenceError as exc:
        raise PortfolioPerformanceError(f"accounting_{exc.code}") from None
    if verified != accounting:
        raise PortfolioPerformanceError("accounting_report_mismatch")
    initial_map = _mapping(time_evidence.get("initial_capital"))
    initial = _decimal(initial_map.get("initial_capital_krw"), "initial_capital")
    anchor = _utc(initial_map.get("timestamp"))
    policy = load_calculation_policy()
    policy_id = _text(policy.get("id"), "policy_identity_mismatch")
    projection = project_nav(time_evidence)
    if len(projection.daily) != EXPECTED_DAILY_NAV:
        raise PortfolioPerformanceError("daily_nav_count_mismatch")
    result = combine_projection_metrics(
        projection, initial=initial, anchor=anchor, policy_id=policy_id
    )
    output = result.as_dict()
    output["schema"] = RESULT_SCHEMA
    simulation_metrics = _mapping(simulation["metrics"])
    secondary_metrics = {
        "trade_count": int(_decimal(simulation_metrics["trade_count"])),
        "maximum_mdd_recovery_duration": maximum_mdd_recovery_duration(
            projection.full, initial=initial, anchor=anchor
        ),
        "profit_factor": {
            "availability": "unavailable",
            "value": None,
            "reason": "missing_realized_trade_pnl",
        },
        "max_consecutive_loss": {
            "availability": "unavailable",
            "value": None,
            "reason": "missing_realized_trade_pnl",
        },
        "sortino": {
            "availability": "unavailable",
            "value": None,
            "reason": "missing_downside_target_policy",
        },
    }
    return {
        "schema": SCHEMA,
        "status": "verified",
        "source": {
            "manifest_sha256": CORRECTED_MANIFEST_SHA256,
            "accounting_report_sha256": ACCOUNTING_REPORT_SHA256,
            "artifacts": _mapping(manifest["artifacts"]),
        },
        "accounting": {
            "schema": accounting["schema"],
            "status": accounting["status"],
            "grade": accounting["grade"],
            "trade_count": accounting["trade_count"],
            "nav_count": accounting["nav_count"],
            "max_residual_krw": accounting["max_residual_krw"],
            "digest": accounting["accounting_digest"],
        },
        "projection": {
            "sampling": "utc_date_last_causal_nav",
            "full_nav_count": len(projection.full),
            "daily_nav_count": len(projection.daily),
            "full_digest": _digest(
                [
                    {"at": point.timestamp.isoformat(), "nav": str(point.nav)}
                    for point in projection.full
                ]
            ),
            "daily_digest": _digest(
                [
                    {"at": point.timestamp.isoformat(), "nav": str(point.nav)}
                    for point in projection.daily
                ]
            ),
        },
        "secondary_metrics": secondary_metrics,
        "bytes_read": bytes_read,
        "result": output,
    }


def canonical_envelope_bytes(envelope: Mapping[str, object]) -> bytes:
    """Return the deterministic v1 envelope encoding."""
    if envelope.get("schema") != SCHEMA:
        raise PortfolioPerformanceError("unsupported_envelope")
    return (
        json.dumps(
            envelope,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode()
        + b"\n"
    )


__all__ = [
    "ACCOUNTING_REPORT_PATH",
    "ACCOUNTING_REPORT_SHA256",
    "BUNDLE_PATH",
    "CORRECTED_MANIFEST_SHA256",
    "EXPECTED_DAILY_NAV",
    "NAVProjection",
    "PortfolioPerformanceError",
    "SCHEMA",
    "canonical_envelope_bytes",
    "combine_projection_metrics",
    "evaluate_corrected_bundle",
    "maximum_mdd_recovery_duration",
    "project_nav",
]
