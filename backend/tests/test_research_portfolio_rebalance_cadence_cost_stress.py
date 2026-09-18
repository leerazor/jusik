from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from jusik.research_portfolio_held_band_experiment import _copy_engine, _load_copy
from jusik.research_portfolio_models import (
    PortfolioCandidate,
    PortfolioConfig,
    PortfolioMetrics,
    PortfolioPolicyEvent,
    PortfolioSimulation,
)
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
    run_experiment,
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
    periods = [{"name": f"fold_{i}"} for i in range(1, 8)] + [{"name": "continuous"}]
    plan = _evaluation_plan(periods)
    assert len(plan) == 48
    assert all(item[0] == "control" for item in plan[:24])
    assert all(item[0] == "variant" for item in plan[24:])
    assert [item[1] for item in plan[:3]] == [1, 2, 3]


@pytest.mark.parametrize("weeks", [4, 8])
@pytest.mark.parametrize("holiday", [False, True])
def test_copied_engine_keeps_risk_weekly_and_changes_only_reentry_cadence(
    weeks: int,
    holiday: bool,
    tmp_path: Path,
) -> None:
    from tests.test_research_portfolio import _episode_source

    source = _episode_source()
    if holiday:
        snapshots = []
        for snapshot in source.instruments:
            instrument = snapshot.instruments[0]
            snapshots.append(
                snapshot.model_copy(
                    update={
                        "instruments": [
                            instrument.model_copy(update={"bars": instrument.bars[1:]})
                        ]
                    }
                )
            )
        source = source.model_copy(update={"instruments": snapshots})
    config = _cadence_config(PortfolioConfig(), weeks, 1)
    engine = Path(__file__).parents[1] / "jusik" / "research_portfolio_engine.py"
    _original, variant_path = _copy_engine(engine, tmp_path)
    variant = _load_copy(variant_path, "cadence_test_variant")
    result = variant.simulate(
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
    confirmations = [event for event in events if event.kind == "recovery_confirmation"]
    assert risk.at.weekday() != 0
    assert confirmations[0].at.date() >= liquidation.at.date() + timedelta(days=28)
    assert len(confirmations) == 2
    assert (confirmations[1].at - confirmations[0].at).days >= 7
    reentry = next(event for event in events if event.kind == "reentry")
    assert reentry.at.tzinfo == UTC
    assert reentry.at.hour == 0
    assert reentry.at.weekday() == 0


def test_control_json_mismatch_stops(tmp_path: Path) -> None:
    expected = tmp_path / "expected.json"
    expected.write_text('{"value": 1}\n', encoding="utf-8")
    with pytest.raises(ValueError):
        _verify_exact_replay(
            {"value": 2},
            expected,
            hashlib.sha256(expected.read_bytes()).hexdigest(),
        )


def _synthetic_contract() -> tuple[
    Any, PortfolioConfig, dict[str, Any], dict[str, Any]
]:
    from tests.test_research_portfolio import _source

    periods = [
        {"name": name, "start": "2024-01-01", "end": "2024-01-02"}
        for name in [f"fold_{n}" for n in range(1, 8)] + ["continuous"]
    ]
    artifacts = [
        {"artifact": f"{period['name']}-{arm}_c{cost}.json", "sha256": "digest"}
        for period in periods
        for arm in ("control", "variant")
        for cost in (1, 2, 3)
    ]
    return (
        _source(),
        PortfolioConfig(),
        {
            "periods": periods,
            "source_paths": {},
            "source_hashes": {},
            "core_hashes": {},
            "imported_helper_hashes": {},
        },
        {"source_run_id": "synthetic", "evaluations": artifacts},
    )


def _synthetic_simulation(
    policy_events: list[PortfolioPolicyEvent], period_end: date
) -> PortfolioSimulation:
    return PortfolioSimulation(
        candidate=PortfolioCandidate(id="synthetic", method="equal", gate="none"),
        period_start=period_end,
        period_end=period_end,
        metrics=PortfolioMetrics(
            initial_equity_krw=Decimal("1"),
            final_equity_krw=Decimal("1"),
            total_return_pct=Decimal("0"),
            max_drawdown_pct=Decimal("0"),
            trade_count=0,
            transaction_cost_krw=Decimal("0"),
            fx_cost_krw=Decimal("0"),
            turnover_pct=Decimal("0"),
        ),
        complete=True,
        incomplete_reasons=[],
        drawdown_latched=False,
        drawdown_latched_at=None,
        equity=[],
        trades=[],
        weekly_targets=[],
        positions=[],
        contributions_krw={},
        split_cash_in_lieu_krw={},
        overlap_diagnostics={},
        policy="low_turnover_combined",
        policy_events=policy_events,
    )


@pytest.mark.parametrize("fail_at", [None, 24])
def test_run_experiment_executes_control_24_then_variant_24(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fail_at: int | None
) -> None:
    from tests.test_research_portfolio_held_band_cost3_stress import _runner_simulation

    source, base, prereg, results = _synthetic_contract()
    calls: list[int] = []
    replays: list[int] = []

    def simulate(*args: object) -> Any:
        config = args[4]
        assert isinstance(config, PortfolioConfig)
        calls.append(config.low_turnover_weeks)
        return _runner_simulation()

    module = "jusik.research_portfolio_rebalance_cadence_cost_stress"
    monkeypatch.setattr(
        module + "._prior_inputs", lambda _path: (source, base, prereg, results)
    )
    monkeypatch.setattr(module + "._verify_prior_inputs_unchanged", lambda *args: None)
    monkeypatch.setattr(module + "._verify_runtime_hashes", lambda *args: None)
    monkeypatch.setattr(
        module + "._verify_accounting", lambda *args: {"residual": Decimal(0)}
    )

    def replay(*_args: object) -> None:
        replays.append(len(calls))
        if fail_at == len(replays):
            raise ValueError("synthetic control mismatch")

    monkeypatch.setattr(module + "._verify_exact_replay", replay)
    monkeypatch.setattr(
        module + "._copy_engine",
        lambda _engine, output: (output / "o.py", output / "v.py"),
    )
    monkeypatch.setattr(
        module + ".sha256",
        lambda _path: (
            "7d9ccd0d8fef90b11779d4e8c98041eadf8aeac94eb3d289318145504483b442"
        ),
    )
    monkeypatch.setattr(
        module + "._load_copy", lambda *_args: SimpleNamespace(simulate=simulate)
    )
    if fail_at is None:
        result = run_experiment(
            tmp_path / "prior",
            tmp_path / "engine.py",
            tmp_path / "out",
            allow_historical_execution=True,
        )
        assert result["evaluation_count"] == 48
        assert calls == [4] * 24 + [8] * 24
    else:
        with pytest.raises(ValueError, match="synthetic control mismatch"):
            run_experiment(
                tmp_path / "prior",
                tmp_path / "engine.py",
                tmp_path / "out",
                allow_historical_execution=True,
            )
        assert calls == [4] * 24
        assert (tmp_path / "out" / "failure.json").exists()


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
        PortfolioPolicyEvent(kind="risk_exit", at=start, detail="synthetic"),
        PortfolioPolicyEvent(
            kind="reentry_ready", at=start + timedelta(days=35), detail="synthetic"
        ),
        PortfolioPolicyEvent(
            kind="recovery_reset", at=start + timedelta(days=60), detail="synthetic"
        ),
        PortfolioPolicyEvent(
            kind="reentry_ready", at=start + timedelta(days=90), detail="synthetic"
        ),
        PortfolioPolicyEvent(
            kind="reentry", at=start + timedelta(days=97), detail="synthetic"
        ),
    ]
    result = _reentry_summary(
        _synthetic_simulation(events, start.date() + timedelta(days=100))
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
        _synthetic_simulation(
            [PortfolioPolicyEvent(kind="risk_exit", at=start, detail="synthetic")],
            start.date() + timedelta(days=10),
        )
    )
    assert result["never_ready_count"] == 1
    assert result["risk_episodes"][0]["status"] == "censored"
