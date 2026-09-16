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
            continue
        result = analyze_chronology(
            _observations(case["observations"]),
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
    with pytest.raises(ValueError, match="buy after drawdown latch"):
        analyze_chronology(
            _observations(recovery["observations"]), _trades(recovery["trades"])
        )
    negative = next(
        case for case in payload["cases"] if case["name"] == "zero_and_negative_nav"
    )["negative"]
    with pytest.raises(ValueError, match="NAV must be finite"):
        analyze_chronology(_observations(negative["observations"]))


def test_latch_day_buy_is_allowed_and_duplicate_fills_are_rejected() -> None:
    observations = _observations(
        [
            {"session": "2026-01-02", "nav_krw": "100"},
            {"session": "2026-01-05", "nav_krw": "125"},
            {"session": "2026-01-06", "nav_krw": "100"},
            {
                "session": "2026-01-07",
                "nav_krw": "100",
                "open_available_symbols": ["AAA"],
            },
        ]
    )
    trades = _trades(
        [
            {
                "signal_session": "2026-01-05",
                "fill_session": "2026-01-06",
                "symbol": "AAA",
                "side": "buy",
                "quantity": 1,
            },
            {
                "signal_session": "2026-01-06",
                "fill_session": "2026-01-07",
                "symbol": "AAA",
                "side": "sell",
                "quantity": 1,
            },
        ]
    )
    result = analyze_chronology(observations, trades, initial_cash_krw=Decimal("100"))
    assert result.status == "success"
    assert result.held_quantities_at_latch == {"AAA": 1}
    assert result.liquidation[0].status == "observed"
    duplicate = trades + [
        TradeObservation(date(2026, 1, 5), date(2026, 1, 7), "AAA", "sell", 1)
    ]
    with pytest.raises(ValueError, match="duplicate fill"):
        analyze_chronology(observations, duplicate, initial_cash_krw=Decimal("100"))


def test_non_positive_initial_cash_and_fixed_tolerance() -> None:
    observations = _observations([{"session": "2026-01-02", "nav_krw": "100"}])
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
    pilot = {
        "result": {
            "request": {"initial_cash_krw": "100000000"},
            "metrics": {
                "initial_cash_krw": "100000000",
                "max_drawdown_pct": "20",
                "drawdown_latched": "1",
            },
            "research_grade": "approximate",
            "equity": [
                {"session": "2026-01-02", "nav_krw": "100000000", "drawdown_pct": "0"},
                {"session": "2026-01-05", "nav_krw": "80000000", "drawdown_pct": "20"},
            ],
            "trades": [],
        }
    }
    path = tmp_path / "pilot.json"
    path.write_text(json.dumps(pilot), encoding="utf-8")
    report = diagnose_saved_pilot(path)
    assert report.status == "blocked"
    assert report.input_grade == "approximate"
    assert report.stored_match is True
    assert report.evidence.calendar == "unavailable"
    assert report.evidence.benchmark == "unavailable"
    assert report.evidence.future_observation == "unavailable"
    assert set(report.reasons) == {"calendar", "benchmark", "future_observation"}
