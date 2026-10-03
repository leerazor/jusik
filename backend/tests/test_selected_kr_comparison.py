"""Same-input synthetic comparison, frozen before any raw arm executes."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest
from test_selected_candidate_kr_risk_policy import (
    CONFIG,
    at,
    fixture,
    rate,
    sell_costs,
)

import jusik.selected_kr_comparison as comparison
from jusik.approved_universe_buy_hold import RawSession
from jusik.market_performance_metrics import (
    CompletenessEvidence,
    RiskFreeEvidence,
)
from jusik.selected_kr_comparison import (
    ComparisonInputError,
    freeze_kr_comparison_manifest,
    run_kr_comparison,
)

D = Decimal
DATES = tuple(at(day).date() for day in (0, 1, 2, 3, 11, 57, 64))
COMPLETE = CompletenessEvidence(
    "complete",
    ("declared synthetic fixture dates",),
    ("explicit UTC fixture calendar",),
)
EVIDENCE = ("synthetic commission and dividend accounting",)
SCENARIO = "explicit synthetic one-percent KR sale cost"


def _run(
    *,
    dividend: bool = True,
    dates: tuple[date, ...] = DATES,
    risk_free: RiskFreeEvidence | None = None,
) -> comparison.KRComparisonResult:
    raw, signal = fixture(dividend=dividend)
    manifest = freeze_kr_comparison_manifest(
        raw,
        signal,
        CONFIG,
        sell_costs(),
        cost_scenario=SCENARIO,
        cost_evidence=EVIDENCE,
        evaluation_dates=dates,
        completeness=COMPLETE,
        risk_free=risk_free,
    )
    return run_kr_comparison(
        raw,
        signal,
        CONFIG,
        sell_costs(),
        manifest=manifest,
        cost_scenario=SCENARIO,
        cost_evidence=EVIDENCE,
        evaluation_dates=dates,
        completeness=COMPLETE,
        risk_free=risk_free,
    )


def test_four_arms_same_fixture_hand_accounting_and_no_ranking() -> None:
    result = _run()
    assert result.schema == "selected-kr-comparison-result/v1"
    assert result.scope == "synthetic_only"
    assert result.investment_qualification == "not_evaluated"
    assert [arm.name for arm in result.arms] == [
        "buy_hold",
        "cap_control",
        "equal_none",
        "inverse_volatility_none",
    ]
    assert not hasattr(result, "winner")
    assert result.manifest.raw_input_sha256 != result.manifest.signal_input_sha256
    assert result.manifest.raw_price_evidence_hash != (
        result.manifest.adjusted_signal_price_source_hash
    )
    hold, cap, equal, inverse = result.arms
    assert hold.ledger.points[-1].nav_krw == D("100950000")
    assert cap.ledger.points[-1].nav_krw == D("100950000")
    assert hold.metrics.total_net_return.value == D(".0095")
    assert hold.metrics.maximum_drawdown.value == D(".25")
    assert hold.metrics.hard_filter.passed is False
    for arm in (equal, inverse):
        assert arm.ledger.ledger.points[-1].nav_krw == D("90080000")
        assert arm.metrics.total_net_return.value == D("-.0992")
        assert arm.metrics.maximum_drawdown.value == D(".10")
        assert arm.metrics.hard_filter.passed is True
        assert arm.metrics.sharpe.reason == "missing_risk_free_evidence"
        assert arm.metrics.cagr.availability == "available"
        assert arm.metrics.calmar.availability == "available"
        assert len(arm.ledger.ledger.sales) == 2
        assert sum(s.commission_local for s in arm.ledger.ledger.sales) == D(300000)
        accrual, payment = arm.ledger.ledger.dividends
        assert (accrual.net_local, payment.net_local) == (D(380000), D(380000))
        assert accrual.at < payment.at
        assert arm.ledger.ledger.points[-1].receivables_krw == 0
        assert arm.ledger.ledger.points[-1].cash_krw == D("54048000")
        assert len(arm.daily_nav) == len(DATES)


def test_first_baseline_fill_may_precede_monday_decision_next_fill() -> None:
    raw, signal = fixture(dividend=True)
    same_instant = tuple(
        RawSession(item, at(0), at(0, 3), D(100), D(100), at(0), at(0, 3))
        for item in raw.cohort
    )
    raw = replace(raw, sessions=same_instant + raw.sessions)
    manifest = freeze_kr_comparison_manifest(
        raw,
        signal,
        CONFIG,
        sell_costs(),
        cost_scenario=SCENARIO,
        cost_evidence=EVIDENCE,
        evaluation_dates=DATES,
        completeness=COMPLETE,
        risk_free=None,
    )
    result = run_kr_comparison(
        raw,
        signal,
        CONFIG,
        sell_costs(),
        manifest=manifest,
        cost_scenario=SCENARIO,
        cost_evidence=EVIDENCE,
        evaluation_dates=DATES,
        completeness=COMPLETE,
        risk_free=None,
    )
    assert result.arms[0].first_fill_at == at(0)
    assert result.arms[1].first_fill_at == at(0)
    for arm in result.arms[2:]:
        assert arm.first_decision_at == at(0)
        assert arm.first_fill_at == at(1)


def test_buy_sale_costs_and_dividend_payment_enter_nav_once() -> None:
    raw, signal = fixture(dividend=True)
    raw = replace(raw, costs=replace(raw.costs, commission_kr=rate(".01")))
    manifest = freeze_kr_comparison_manifest(
        raw,
        signal,
        CONFIG,
        sell_costs(),
        cost_scenario=SCENARIO,
        cost_evidence=EVIDENCE,
        evaluation_dates=DATES,
        completeness=COMPLETE,
        risk_free=None,
    )
    result = run_kr_comparison(
        raw,
        signal,
        CONFIG,
        sell_costs(),
        manifest=manifest,
        cost_scenario=SCENARIO,
        cost_evidence=EVIDENCE,
        evaluation_dates=DATES,
        completeness=COMPLETE,
        risk_free=None,
    )
    hold = result.arms[0]
    # Two 495049-share buys cost 1% each; dividend net is 2*495049 - .1*495049.
    assert hold.ledger.points[-1].nav_krw == (D(100000000) - D(990098) + D("940593.10"))
    for arm in result.arms[2:]:
        ledger = arm.ledger.ledger
        # Initial buys, a 25 KRW decline on 398400 shares, retained ex-right,
        # sale fees, then reentry buy fees. Payment clears a receivable, not NAV.
        assert ledger.points[-1].nav_krw == (
            D(100000000) - D(398400) - D(9960000) + D(378480) - D(298800) - D(357448)
        )
        assert ledger.dividends[0].net_local == D(378480)
        assert ledger.dividends[1].net_local == D(378480)
        assert ledger.points[-1].receivables_krw == 0


@pytest.mark.parametrize(
    "change",
    (
        "raw_price",
        "signal_price",
        "cost",
        "scenario",
        "dates",
        "config",
        "calendar",
        "registry",
        "completeness",
        "risk_free",
        "manifest",
    ),
)
def test_frozen_manifest_rejects_change_before_arms(
    monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    raw, signal = fixture()
    costs = sell_costs()
    config = CONFIG
    scenario = SCENARIO
    dates = DATES
    complete = COMPLETE
    risk_free = None
    manifest = freeze_kr_comparison_manifest(
        raw,
        signal,
        config,
        costs,
        cost_scenario=scenario,
        cost_evidence=EVIDENCE,
        evaluation_dates=dates,
        completeness=complete,
        risk_free=risk_free,
    )
    if change == "raw_price":
        raw = replace(
            raw,
            sessions=(replace(raw.sessions[0], raw_open=D(101)),) + raw.sessions[1:],
        )
    elif change == "signal_price":
        signal = replace(
            signal,
            closes=(replace(signal.closes[0], adjusted_close=D(101)),)
            + signal.closes[1:],
        )
    elif change == "cost":
        costs = sell_costs(".02")
    elif change == "scenario":
        scenario = "changed scenario"
    elif change == "dates":
        dates = DATES[:-2] + (at(58).date(), DATES[-1])
    elif change == "config":
        config += b" "
        signal = replace(signal, config_sha256=hashlib.sha256(config).hexdigest())
    elif change == "calendar":
        raw = replace(raw, official_calendar_hash="e" * 64)
        signal = replace(signal, calendar_hash="e" * 64)
    elif change == "registry":
        raw = replace(raw, registration_hash="e" * 64)
        signal = replace(signal, registration_hash="e" * 64)
    elif change == "completeness":
        complete = replace(complete, evidence=("changed coverage",))
    elif change == "risk_free":
        risk_free = RiskFreeEvidence(D(".01"), ("synthetic rate",))
    else:
        manifest = replace(manifest, adapter_sha256="0" * 64)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("raw arm executed before manifest rejection")

    monkeypatch.setattr(comparison, "run_buy_hold_reference", forbidden)
    monkeypatch.setattr(comparison, "run_cap_control_reference", forbidden)
    monkeypatch.setattr(
        comparison, "run_kr_selected_candidate_risk_reference", forbidden
    )
    with pytest.raises(ValueError):
        run_kr_comparison(
            raw,
            signal,
            config,
            costs,
            manifest=manifest,
            cost_scenario=scenario,
            cost_evidence=EVIDENCE,
            evaluation_dates=dates,
            completeness=complete,
            risk_free=risk_free,
        )


def test_common_date_projection_and_missing_date_fail() -> None:
    result = _run()
    equal = result.arms[2]
    assert equal.daily_nav[3].nav == D("90080000")
    assert equal.daily_nav[4].nav == D("90080000")
    assert [point.timestamp.date() for point in equal.daily_nav] == list(DATES)
    with pytest.raises(
        ComparisonInputError, match="missing common UTC evaluation date"
    ):
        _run(dates=DATES[:-2] + (at(58).date(), DATES[-1]))


def test_intraday_drawdown_survives_same_day_close_recovery() -> None:
    raw, signal = fixture(
        dividend=True,
        closes={2: ("100", "100")},
        opens={
            2: ("75", "75"),
            3: ("100", "100"),
            29: ("100", "100"),
            57: ("100", "100"),
        },
    )
    manifest = freeze_kr_comparison_manifest(
        raw,
        signal,
        CONFIG,
        sell_costs(),
        cost_scenario=SCENARIO,
        cost_evidence=EVIDENCE,
        evaluation_dates=DATES,
        completeness=COMPLETE,
        risk_free=None,
    )
    result = run_kr_comparison(
        raw,
        signal,
        CONFIG,
        sell_costs(),
        manifest=manifest,
        cost_scenario=SCENARIO,
        cost_evidence=EVIDENCE,
        evaluation_dates=DATES,
        completeness=COMPLETE,
        risk_free=None,
    )
    hold = result.arms[0]
    assert hold.daily_nav[2].nav == D("100000000")
    assert hold.metrics.maximum_drawdown.value == D(".25")
    assert hold.metrics.hard_filter.passed is False
    assert hold.metrics.total_net_return.value == D(".0095")


def test_incomplete_or_oversized_chronology_is_explicit_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw, signal = fixture()
    with pytest.raises(ComparisonInputError, match="completeness"):
        freeze_kr_comparison_manifest(
            raw,
            signal,
            CONFIG,
            sell_costs(),
            cost_scenario=SCENARIO,
            cost_evidence=EVIDENCE,
            evaluation_dates=DATES,
            completeness=replace(COMPLETE, status="partial"),
            risk_free=None,
        )
    result = _run()
    point = result.arms[0].ledger.points[0]
    with pytest.raises(ComparisonInputError, match="too_many_nav_points"):
        comparison._metrics((point,) * 5001, result.manifest, "buy_hold")


def test_explicit_risk_free_enables_sharpe_only_with_evidence() -> None:
    result = _run(risk_free=RiskFreeEvidence(D(".02"), ("synthetic annual rate",)))
    assert all(
        arm.metrics.sharpe.reason != "missing_risk_free_evidence" for arm in result.arms
    )
    assert result.arms[0].metrics.maximum_drawdown.value == D(".25")
