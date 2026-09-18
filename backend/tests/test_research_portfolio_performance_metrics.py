from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest

import jusik.research_portfolio_performance_metrics as adapter
from jusik.market_performance_metrics import NAVPoint, PerformanceReport

BUNDLE = adapter.BUNDLE_PATH
ACCOUNTING_REPORT = adapter.ACCOUNTING_REPORT_PATH


def _synthetic_nav() -> dict[str, object]:
    rows = (
        ("2024-01-01T06:30:00Z", "100"),
        ("2024-01-01T20:00:00Z", "110"),
        ("2024-01-02T01:00:00Z", "130"),
        ("2024-01-02T06:30:00Z", "99"),
        ("2024-01-03T06:30:00Z", "121"),
    )
    return {
        "nav": [
            {"evaluation_at": at, "nav_index": index, "nav_krw": nav}
            for index, (at, nav) in enumerate(rows)
        ]
    }


def test_synthetic_projection_uses_last_utc_row_without_forward_fill() -> None:
    projection = adapter.project_nav(_synthetic_nav(), expected_count=5)
    assert len(projection.full) == 5
    assert len(projection.daily) == 3
    assert [point.nav for point in projection.daily] == [
        Decimal("110"),
        Decimal("99"),
        Decimal("121"),
    ]
    assert projection.daily[0].timestamp == datetime(2024, 1, 1, 20, tzinfo=UTC)


def test_synthetic_metrics_preserve_anchor_first_return_and_full_drawdown() -> None:
    projection = adapter.project_nav(_synthetic_nav(), expected_count=5)
    report = adapter.combine_projection_metrics(
        projection,
        initial=Decimal("100"),
        anchor=datetime(2024, 1, 1, tzinfo=UTC),
        policy_id="fixture-policy",
    )
    assert isinstance(report, PerformanceReport)
    assert report.total_net_return.value == Decimal("0.21")
    assert report.maximum_drawdown.value == Decimal(
        "0.23846153846153846153846153846153846153846153846154"
    )
    daily_drawdown = (Decimal(110) - Decimal(99)) / Decimal(110)
    assert report.maximum_drawdown.value != daily_drawdown
    assert report.sharpe.value is None
    assert report.sharpe.reason == "missing_risk_free_evidence"
    assert report.calmar.value is not None


def test_synthetic_recovery_duration_uses_utc_peak_to_recovery_seconds() -> None:
    anchor = datetime(2024, 1, 1, tzinfo=UTC)
    points = (
        NAVPoint(datetime(2024, 1, 1, 1, tzinfo=UTC), Decimal("120")),
        NAVPoint(datetime(2024, 1, 2, tzinfo=UTC), Decimal("90")),
        NAVPoint(datetime(2024, 1, 3, 13, tzinfo=UTC), Decimal("121")),
        NAVPoint(datetime(2024, 1, 4, tzinfo=UTC), Decimal("80")),
        NAVPoint(datetime(2024, 1, 5, tzinfo=UTC), Decimal("122")),
    )
    result = adapter.maximum_mdd_recovery_duration(
        points, initial=Decimal("100"), anchor=anchor
    )
    assert result == {
        "availability": "available",
        "utc_seconds": 216000,
        "iso_duration": "P2DT12H0M0S",
        "reason": None,
    }


def _require_bundle() -> None:
    if not BUNDLE.is_dir() or not ACCOUNTING_REPORT.is_file():
        pytest.skip("corrected audit bundle is not available")


def test_registered_corrected_bundle_has_deterministic_envelope() -> None:
    _require_bundle()
    first = adapter.evaluate_corrected_bundle()
    second = adapter.evaluate_corrected_bundle()
    assert first == second
    assert first["schema"] == adapter.SCHEMA
    projection = first["projection"]
    assert isinstance(projection, dict)
    assert projection["full_nav_count"] == 1172
    assert projection["daily_nav_count"] == 614
    result = first["result"]
    assert isinstance(result, dict)
    metrics = result["metrics"]
    assert isinstance(metrics, dict)
    sharpe = metrics["sharpe"]
    assert isinstance(sharpe, dict)
    assert sharpe["reason"] == "missing_risk_free_evidence"
    secondary = first["secondary_metrics"]
    assert isinstance(secondary, dict)
    assert secondary["trade_count"] == 171
    recovery = secondary["maximum_mdd_recovery_duration"]
    assert isinstance(recovery, dict)
    assert recovery["availability"] == "available"
    for name, reason in (
        ("profit_factor", "missing_realized_trade_pnl"),
        ("max_consecutive_loss", "missing_realized_trade_pnl"),
        ("sortino", "missing_downside_target_policy"),
    ):
        metric = secondary[name]
        assert isinstance(metric, dict)
        assert metric["availability"] == "unavailable"
        assert metric["reason"] == reason
    assert adapter.canonical_envelope_bytes(first) == adapter.canonical_envelope_bytes(
        second
    )


def test_accounting_verifier_is_called_exactly_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _require_bundle()
    calls = 0
    expected = cast(
        dict[str, object], json.loads(ACCOUNTING_REPORT.read_text(encoding="utf-8"))
    )

    def verify_once(
        bundle_dir: Path, *, expected_manifest_sha256: str
    ) -> dict[str, object]:
        nonlocal calls
        calls += 1
        assert bundle_dir == BUNDLE
        assert expected_manifest_sha256 == adapter.CORRECTED_MANIFEST_SHA256
        return expected

    monkeypatch.setattr(adapter, "verify_accounting_bundle", verify_once)
    adapter.evaluate_corrected_bundle()
    assert calls == 1


def test_manifest_tamper_fails_before_accounting_verifier(
    tmp_path: Path,
) -> None:
    _require_bundle()
    copied = tmp_path / "bundle"
    shutil.copytree(BUNDLE, copied)
    manifest = copied / "manifest.json"
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["event_plan_sha256"] = "0" * 64
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(
        adapter.PortfolioPerformanceError, match="manifest_sha_mismatch"
    ):
        adapter.evaluate_corrected_bundle(copied, ACCOUNTING_REPORT)


def test_time_evidence_tamper_fails_artifact_sha_chain(tmp_path: Path) -> None:
    _require_bundle()
    copied = tmp_path / "bundle"
    shutil.copytree(BUNDLE, copied)
    evidence = copied / "time-evidence.json"
    evidence.write_bytes(evidence.read_bytes() + b" ")
    with pytest.raises(
        adapter.PortfolioPerformanceError, match="artifact_sha_mismatch"
    ):
        adapter.evaluate_corrected_bundle(copied, ACCOUNTING_REPORT)


def test_simulation_tamper_fails_before_persisted_trade_count_is_used(
    tmp_path: Path,
) -> None:
    _require_bundle()
    copied = tmp_path / "bundle"
    shutil.copytree(BUNDLE, copied)
    simulation = copied / "simulation.json"
    payload = json.loads(simulation.read_text(encoding="utf-8"))
    payload["metrics"]["trade_count"] = 170
    simulation.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(
        adapter.PortfolioPerformanceError, match="artifact_sha_mismatch"
    ):
        adapter.evaluate_corrected_bundle(copied, ACCOUNTING_REPORT)


def test_accounting_report_tamper_fails_fixed_report_sha(tmp_path: Path) -> None:
    _require_bundle()
    report = tmp_path / "accounting-report.json"
    report.write_bytes(ACCOUNTING_REPORT.read_bytes() + b" ")
    with pytest.raises(
        adapter.PortfolioPerformanceError, match="accounting_report_sha_mismatch"
    ):
        adapter.evaluate_corrected_bundle(BUNDLE, report)
