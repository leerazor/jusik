from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from jusik.drawdown_chronology import (
    DRAW_DOWN_TOLERANCE_PP,
    SessionObservation,
    TradeObservation,
    analyze_chronology,
    compare_percentage_points,
    diagnose_saved_pilot,
)

FIXTURE = Path(__file__).parent / "fixtures" / "drawdown_chronology.json"


def _observations(rows: list[dict[str, object]]) -> list[SessionObservation]:
    return [SessionObservation.from_mapping(row) for row in rows]


def _trades(rows: list[dict[str, object]]) -> list[TradeObservation]:
    return [TradeObservation.from_mapping(row) for row in rows]


def test_fixed_drawdown_cases() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert len(payload["cases"]) == 12
    for case in payload["cases"]:
        sessions = case.get("observations", [])
        assert len(sessions) <= 300
        for variant in case.get("invalid_variants", []):
            assert len(variant["observations"]) <= 300
        for variant in (case.get("zero"), case.get("negative")):
            if variant is not None:
                assert len(variant["observations"]) <= 300
        if "expected" not in case:
            if "zero" in case:
                zero = case["zero"]
                zero_result = analyze_chronology(
                    _observations(zero["observations"]),
                    initial_cash_krw=Decimal("100"),
                )
                assert zero_result.maximum_drawdown_pct == Decimal("100")
                assert zero_result.latch_session == date(2026, 1, 5)
            continue
        rows = case["observations"]
        if case["name"] == "fx_only_change":
            rows = [
                {
                    "session": row["session"],
                    "nav_krw": str(Decimal(native) * Decimal(fx)),
                }
                for row, native, fx in zip(
                    rows,
                    case["native_usd"],
                    case["fx_krw_per_usd"],
                    strict=True,
                )
            ]
        result = analyze_chronology(
            _observations(rows),
            _trades(case.get("trades", [])),
            initial_cash_krw=Decimal("100"),
            expected_sessions=[
                date.fromisoformat(value) for value in case.get("expected_sessions", [])
            ]
            or None,
        )
        expected = case["expected"]
        assert result.status == expected["status"], case["name"]
        assert result.peak_nav_krw == Decimal(expected["peak"]), case["name"]
        assert result.maximum_drawdown_pct == Decimal(expected["mdd"]), case["name"]
        if case["name"] == "initial_loss":
            assert result.drawdown_by_session[0][1] == Decimal("1")
        latch = result.latch_session.isoformat() if result.latch_session else None
        assert latch == expected["latch"], case["name"]
        if "first_open" in expected:
            assert result.liquidation[0].first_available_open == date.fromisoformat(
                expected["first_open"]
            )
            assert result.liquidation[0].status == "observed"
        if "liquidation" in expected:
            assert result.liquidation[0].status == expected["liquidation"]


def test_fixed_invalid_cases_reject_chronology() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    invalid_case = next(
        case for case in payload["cases"] if case["name"].startswith("invalid_")
    )
    for variant in invalid_case["invalid_variants"]:
        if "expected_sessions" in variant:
            expected_sessions = [
                date.fromisoformat(value) for value in variant["expected_sessions"]
            ]
        else:
            expected_sessions = None
        with pytest.raises(ValueError):
            analyze_chronology(
                _observations(variant["observations"]),
                expected_sessions=expected_sessions,
            )


def test_reentry_and_negative_nav_are_rejected() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    recovery = next(
        case for case in payload["cases"] if case["name"] == "recovery_cannot_reenter"
    )
    valid = analyze_chronology(
        _observations(recovery["observations"]),
        _trades(recovery["trades"]),
        initial_cash_krw=Decimal("100"),
    )
    assert valid.latch_session == date(2026, 1, 6)
    assert valid.liquidation[0].status == "observed"
    assert valid.drawdown_by_session[-1][0] == date(2026, 1, 7)
    later_buy = dict(recovery["trades"][1])
    later_buy["side"] = "buy"
    with pytest.raises(ValueError, match="buy after drawdown latch"):
        analyze_chronology(
            _observations(recovery["observations"]),
            _trades(recovery["trades"] + [later_buy]),
            initial_cash_krw=Decimal("100"),
        )
    with pytest.raises(ValueError, match="duplicate fill"):
        analyze_chronology(
            _observations(recovery["observations"]),
            _trades(recovery["trades"] + [dict(recovery["trades"][1])]),
            initial_cash_krw=Decimal("100"),
        )
    negative = next(
        case for case in payload["cases"] if case["name"] == "zero_and_negative_nav"
    )["negative"]
    with pytest.raises(ValueError, match="NAV must be finite"):
        analyze_chronology(_observations(negative["observations"]))


def test_late_liquidation_signal_is_a_mismatch() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    case = next(
        case
        for case in payload["cases"]
        if case["name"] == "missing_next_open_then_fill"
    )
    late_sell = dict(case["trades"][1])
    late_sell["signal_session"] = "2026-01-07"
    result = analyze_chronology(
        _observations(case["observations"]),
        _trades([case["trades"][0], late_sell]),
        initial_cash_krw=Decimal("100"),
    )
    assert result.status == "blocked"
    assert result.liquidation[0].signal_session == date(2026, 1, 7)
    assert result.liquidation[0].status == "mismatch"


def test_non_positive_initial_cash_and_fixed_tolerance() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    initial_loss = next(
        case for case in payload["cases"] if case["name"] == "initial_loss"
    )
    observations = _observations(initial_loss["observations"])
    with pytest.raises(ValueError, match="initial_cash_krw"):
        analyze_chronology(observations, initial_cash_krw=Decimal("0"))
    assert compare_percentage_points(
        Decimal("1"), Decimal("1") + DRAW_DOWN_TOLERANCE_PP
    )
    assert not compare_percentage_points(
        Decimal("1"), Decimal("1.000000000000000000011")
    )


def test_saved_approximate_pilot_is_blocked_without_required_evidence(
    tmp_path: Path,
) -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    source = next(
        case for case in fixture["cases"] if case["name"] == "exact_threshold"
    )
    scale = Decimal("1000000")
    expected_drawdowns = ["0", "0", "20"]
    equity = [
        {
            "session": row["session"],
            "nav_krw": str(Decimal(row["nav_krw"]) * scale),
            "drawdown_pct": drawdown,
        }
        for row, drawdown in zip(
            source["observations"][:3], expected_drawdowns, strict=True
        )
    ]
    pilot = {
        "result": {
            "request": {"initial_cash_krw": "100000000"},
            "metrics": {
                "initial_cash_krw": "100000000",
                "max_drawdown_pct": "20",
                "drawdown_latched": "1",
            },
            "research_grade": "approximate",
            "equity": equity,
            "trades": [],
        }
    }
    path = tmp_path / "pilot.json"
    path.write_text(json.dumps(pilot), encoding="utf-8")
    report = diagnose_saved_pilot(path)
    assert report.status == "blocked"
    assert report.input_grade == "approximate"
    assert report.stored_drawdown_match is True
    assert report.stored_final_latch_match is True
    assert report.stored_match is False
    assert report.evidence.calendar == "unavailable"
    assert report.evidence.benchmark == "unavailable"
    assert report.evidence.future_observation == "unavailable"
    assert set(report.reasons) == {
        "calendar",
        "benchmark",
        "future_observation",
        "stored latch date unavailable",
        "stored latch release chronology unavailable",
    }
