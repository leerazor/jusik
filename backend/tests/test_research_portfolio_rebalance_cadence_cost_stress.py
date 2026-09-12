from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from jusik.research_portfolio_engine import simulate
from jusik.research_portfolio_models import PortfolioCandidate, PortfolioConfig
from jusik.research_portfolio_rebalance_cadence_cost_stress import (
    EVALUATION_CAP,
    FULL_EVALUATION_COUNT,
    RATE_3X,
    VARIANT_EVALUATION_COUNT,
    _cadence_config,
    _empty_output,
    _evaluation_plan,
    _reentry_summary,
    _verify_exact_replay,
    preflight,
)


def test_cadence_study_contract() -> None:
    assert FULL_EVALUATION_COUNT == 24
    assert VARIANT_EVALUATION_COUNT == 24
    assert EVALUATION_CAP == 48
    base = PortfolioConfig()
    control = _cadence_config(base, 4, 1)
    variant = _cadence_config(base, 8, 3)
    assert control.low_turnover_weeks == 4
    assert variant.low_turnover_weeks == 8
    assert control.low_turnover_band == Decimal("0.02")
    assert variant.low_turnover_band == Decimal("0.02")
    assert variant.fee_rate == RATE_3X
    assert variant.initial_cash_krw == Decimal("100000000")
    assert variant.leveraged_etf_cap == Decimal("0.20")
    assert variant.drawdown_limit == Decimal("0.10")


def test_runner_plan_is_24_control_then_24_variant() -> None:
    periods = [{"name": f"fold_{i}"} for i in range(1, 8)] + [
        {"name": "continuous"}
    ]
    plan = _evaluation_plan(periods)
    assert len(plan) == 48
    assert all(item[0] == "control" for item in plan[:24])
    assert all(item[0] == "variant" for item in plan[24:])
    assert [item[1] for item in plan[:3]] == [1, 2, 3]


@pytest.mark.parametrize("weeks", [4, 8])
def test_copied_engine_keeps_risk_weekly_and_changes_only_reentry_cadence(
    weeks: int,
) -> None:
    from tests.test_research_portfolio import _episode_source

    source = _episode_source()
    config = _cadence_config(PortfolioConfig(), weeks, 1)
    result = simulate(
        source,
        PortfolioCandidate(id="equal", method="equal", gate="none"),
        source.instruments[0].requested_start,
        source.instruments[0].requested_end,
        config,
        policy="low_turnover_combined",
    )
    events = result.policy_events
    risk = next(event for event in events if event.kind == "risk_exit")
    liquidation = next(
        event for event in events if event.kind == "liquidation_complete"
    )
    confirmations = [
        event for event in events if event.kind == "recovery_confirmation"
    ]
    assert risk.at.weekday() != 0
    assert confirmations[0].at.date() >= liquidation.at.date() + timedelta(days=28)
    assert len(confirmations) == 2
    assert any(event.kind == "reentry" for event in events)


def test_control_json_mismatch_stops(tmp_path: Path) -> None:
    expected = tmp_path / "expected.json"
    expected.write_text('{"value": 1}\n', encoding="utf-8")
    with pytest.raises(ValueError):
        _verify_exact_replay({"value": 2}, expected, "0" * 64)


@pytest.mark.parametrize("weeks", [0, 3, 9])
def test_cadence_boundary_rejected(weeks: int) -> None:
    with pytest.raises(ValueError):
        _cadence_config(PortfolioConfig(), weeks, 1)


def test_frozen_cost3_inputs_preflight() -> None:
    audit = Path(
        "/home/kwl/.local/share/jusik/portfolio-audit/"
        "portfolio-held-band-cost3-stress-v1-f9aecd54dffc4931a6100ac2de8c8cd3/experiment"
    )
    result = preflight(audit)
    assert result["evaluation_count"] == 24
    assert result["historical_calls"] == 0


def test_reentry_ready_delay_and_censored_episode_are_preserved() -> None:
    start = datetime(2025, 1, 6, tzinfo=UTC)
    events = [
        SimpleNamespace(kind="risk_exit", at=start),
        SimpleNamespace(kind="reentry_ready", at=start + timedelta(days=35)),
        SimpleNamespace(kind="recovery_reset", at=start + timedelta(days=60)),
        SimpleNamespace(kind="reentry_ready", at=start + timedelta(days=90)),
        SimpleNamespace(kind="reentry", at=start + timedelta(days=97)),
    ]
    result = _reentry_summary(
        SimpleNamespace(
            policy_events=events, period_end=start.date() + timedelta(days=100)
        )
    )
    assert result["ready_utc"] == [
        (start + timedelta(days=35)).isoformat(),
        (start + timedelta(days=90)).isoformat(),
    ]
    assert result["delay_seconds"] == [None, "604800.0"]
    assert result["reentry_utc"] == [(start + timedelta(days=97)).isoformat()]
    assert result["never_ready_count"] == 0
    assert [item["status"] for item in result["waits"]] == ["reset", "completed"]


def test_existing_output_refuses_resume(tmp_path: Path) -> None:
    output = tmp_path / "existing"
    output.mkdir()
    (output / "ledger.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="retry/resume"):
        _empty_output(output)


def test_never_ready_risk_episode_is_censored() -> None:
    start = datetime(2025, 1, 6, tzinfo=UTC)
    result = _reentry_summary(
        SimpleNamespace(
            policy_events=[SimpleNamespace(kind="risk_exit", at=start)],
            period_end=start.date() + timedelta(days=10),
        )
    )
    assert result["never_ready_count"] == 1
    assert result["risk_episodes"][0]["status"] == "censored"
