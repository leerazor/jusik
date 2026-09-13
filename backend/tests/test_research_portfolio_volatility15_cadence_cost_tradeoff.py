from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

import jusik.research_portfolio_volatility15_cadence_cost_tradeoff as runner
from jusik.research_portfolio_models import (
    PortfolioCandidate,
    PortfolioConfig,
    PortfolioEquityPoint,
    PortfolioMetrics,
    PortfolioSimulation,
)


def _sim() -> PortfolioSimulation:
    return PortfolioSimulation.model_construct(
        candidate=PortfolioCandidate(id="equal", method="equal", gate="none"),
        period_start=date(2024, 1, 1),
        period_end=date(2024, 1, 2),
        metrics=PortfolioMetrics(
            initial_equity_krw=Decimal("100000000"),
            final_equity_krw=Decimal("100000000"),
            total_return_pct=Decimal("0"),
            max_drawdown_pct=Decimal("0"),
            trade_count=0,
            transaction_cost_krw=Decimal("0"),
            fx_cost_krw=Decimal("0"),
            turnover_pct=Decimal("0"),
        ),
        complete=True,
        incomplete_reasons=[],
        equity=[
            PortfolioEquityPoint(
                at=datetime(2024, 1, 2, tzinfo=UTC),
                equity_krw=Decimal("100000000"),
                cash_krw=Decimal("100000000"),
                drawdown_pct=Decimal("0"),
            )
        ],
        drawdown_latched=False,
        drawdown_latched_at=None,
        trades=[],
        weekly_targets=[],
        positions=[],
        contributions_krw={},
        split_cash_in_lieu_krw={},
        overlap_diagnostics={},
        policy="low_turnover_combined",
    )


def test_config_is_closed_to_target_cadence_and_cost() -> None:
    base = PortfolioConfig()
    for cadence in (4, 8):
        config = runner._config(base, cadence, 3)
        assert config.volatility_target == Decimal("0.15")
        assert config.low_turnover_weeks == cadence
        assert config.low_turnover_band == Decimal("0.04")
        assert config.fee_rate == Decimal("0.003")
    for cadence, cost in ((0, 1), (5, 1), (4, 2), (4, 0)):
        with pytest.raises(ValueError):
            runner._config(base, cadence, cost)


def test_period_and_order_contract_keeps_controls_first() -> None:
    periods = [
        {"name": name, "start": "2024-01-01", "end": "2024-02-01"}
        for name in runner.PERIOD_NAMES
    ]
    assert [item["name"] for item in runner._periods({"periods": periods})] == list(
        runner.PERIOD_NAMES
    )
    names = [
        f"{period}-{arm}_c{cost}.json"
        for arm, _cadence in runner.ARMS
        for period in runner.PERIOD_NAMES
        for cost in runner.FULL_COSTS
    ]
    assert names[:16] == [
        f"{period}-control_c{cost}.json"
        for period in runner.PERIOD_NAMES
        for cost in runner.FULL_COSTS
    ]
    assert set(names) == runner._expected_names()


def test_prior_variant_mapping_is_explicit_and_exact() -> None:
    mapped = "fold_3-control_c3.json".replace("-control_", "-variant_")
    assert mapped == "fold_3-variant_c3.json"


def test_synthetic_engine_uses_monday_anchor_for_four_and_eight_weeks(
    tmp_path: Path,
) -> None:
    from tests.test_research_portfolio import _source

    engine_path = Path(__file__).parents[1] / "jusik" / "research_portfolio_engine.py"
    _original, variant_path = runner._copy_engine(engine_path, tmp_path)
    engine = runner._load_copy(variant_path, "cadence_synthetic_engine")
    source = _source()
    candidate = PortfolioCandidate(id="equal", method="equal", gate="none")
    engine.target_weights = lambda *_args: ({"KRTEST": Decimal("0.20")}, {}, None)
    engine.volatility_scale = lambda *_args: (Decimal("1"), Decimal("0"))
    start = date(2024, 1, 8)
    end = date(2024, 3, 29)
    for cadence, expected_rebalances in ((4, 3), (8, 2)):
        config = PortfolioConfig(
            initial_cash_krw=Decimal("1000000"),
            low_turnover_weeks=cadence,
            low_turnover_band=Decimal("0"),
            gross_cap=Decimal("1"),
            symbol_cap=Decimal("1"),
            leveraged_etf_cap=Decimal("1"),
            fee_rate=Decimal("0"),
            slippage_rate=Decimal("0"),
            fx_spread_rate=Decimal("0"),
        )
        result = engine.simulate(
            source, candidate, start, end, config, "low_turnover_combined"
        )
        skips = [
            event for event in result.policy_events if event.kind == "frequency_skip"
        ]
        assert len(result.weekly_targets) // 2 == expected_rebalances
        assert all(event.decided_at.weekday() == 0 for event in result.weekly_targets)
        assert len(skips) == (12 - expected_rebalances)


def _mock_contract(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> list[dict[str, str]]:
    periods = [
        {"name": name, "start": "2024-01-01", "end": "2024-01-02"}
        for name in runner.PERIOD_NAMES
    ]
    prereg = {
        "periods": periods,
        "source_paths": {},
        "source_hashes": {},
        "base_config": PortfolioConfig().model_dump(mode="json"),
    }
    prior = {
        "evaluations": [
            {
                "artifact": f"{p['name']}-variant_c{c}.json",
                "sha256": "b" * 64,
            }
            for p in periods
            for c in runner.FULL_COSTS
        ]
    }
    monkeypatch.setattr(
        runner,
        "_load_contract",
        lambda _path: (prereg, SimpleNamespace(instruments=[]), PortfolioConfig()),
    )
    monkeypatch.setattr(
        runner,
        "_json",
        lambda path: prior if path.name == "results.json" else {"periods": periods},
    )
    monkeypatch.setattr(runner, "verify_hashes", lambda _checks: None)
    monkeypatch.setattr(runner, "_runtime_hashes", lambda *_args: {})
    monkeypatch.setattr(runner, "VARIANT_SHA256", "b" * 64)
    monkeypatch.setattr(runner, "MANDATE_SHA256", "a" * 64)
    monkeypatch.setattr(
        runner,
        "_copy_engine",
        lambda _path, out: (out / "original.py", out / "variant.py"),
    )
    monkeypatch.setattr(
        runner,
        "sha256",
        lambda path: "b" * 64 if path.name == "variant.py" else "a" * 64,
    )
    monkeypatch.setattr(
        runner, "_copy_observer_engine", lambda _path, out: out / "observer.py"
    )
    monkeypatch.setattr(runner, "_load_copy", lambda _path, _name: ModuleType("fake"))
    monkeypatch.setattr(runner.gross, "_coverage", lambda _source: [])
    return periods


def test_mock_execution_calls_32_controls_then_variants_and_replays_prior(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    periods = _mock_contract(monkeypatch, tmp_path)
    calls: list[tuple[str, int, int, bool]] = []
    simulation = _sim()

    def fake_run(
        _engine: ModuleType,
        _source: Any,
        _candidate: PortfolioCandidate,
        period: dict[str, str],
        config: PortfolioConfig,
    ) -> tuple[PortfolioSimulation, list[Any]]:
        calls.append(
            (
                period["name"],
                config.low_turnover_weeks,
                int(config.fee_rate * 1000),
                (tmp_path / "out" / "preregistration.json").exists(),
            )
        )
        return simulation, [
            runner.EquityObservation(
                datetime(2024, 1, 2, tzinfo=UTC),
                Decimal("100000000"),
                Decimal("100000000"),
                {},
            )
        ]

    monkeypatch.setattr(runner, "_run_simulation", fake_run)
    monkeypatch.setattr(runner, "_verify_simulation_contract", lambda *_args: None)
    monkeypatch.setattr(runner, "_verify_observations", lambda *_args: None)
    monkeypatch.setattr(
        runner, "_verify_accounting", lambda *_args: {"residual": Decimal("0")}
    )
    replay: list[str] = []
    monkeypatch.setattr(
        runner,
        "_verify_exact_replay",
        lambda _payload, path, _digest: replay.append(path.name),
    )
    result = runner._execute(
        tmp_path, tmp_path / "engine.py", tmp_path / "out", lambda: 0.0
    )
    assert result["evaluation_count"] == 32
    assert len(calls) == 32 and all(item[3] for item in calls)
    assert [item[1] for item in calls[:16]] == [4] * 16
    assert [item[1] for item in calls[16:]] == [8] * 16
    assert replay == [
        f"{p['name']}-variant_c{c}.json" for p in periods for c in runner.FULL_COSTS
    ]


def test_mock_replay_failure_stops_before_variant_and_records_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _mock_contract(monkeypatch, tmp_path)
    calls = 0

    def fake_run(*_args: Any) -> tuple[PortfolioSimulation, list[Any]]:
        nonlocal calls
        calls += 1
        return _sim(), [
            runner.EquityObservation(
                datetime(2024, 1, 2, tzinfo=UTC),
                Decimal("100000000"),
                Decimal("100000000"),
                {},
            )
        ]

    monkeypatch.setattr(runner, "_run_simulation", fake_run)
    monkeypatch.setattr(runner, "_verify_simulation_contract", lambda *_args: None)
    monkeypatch.setattr(runner, "_verify_observations", lambda *_args: None)
    monkeypatch.setattr(
        runner, "_verify_accounting", lambda *_args: {"residual": Decimal("0")}
    )
    monkeypatch.setattr(
        runner,
        "_verify_exact_replay",
        lambda *_args: (_ for _ in ()).throw(ValueError("replay mismatch")),
    )
    with pytest.raises(ValueError, match="replay mismatch"):
        runner._execute(tmp_path, tmp_path / "engine.py", tmp_path / "out", lambda: 0.0)
    assert calls == 1
    failure = json.loads((tmp_path / "out" / "failure.json").read_text())
    assert len(failure["missing"]) == 32


def test_post_call_hash_mutation_and_deadline_stop_without_retry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _mock_contract(monkeypatch, tmp_path)
    protected = tmp_path / "protected.json"
    protected.write_text("before", encoding="utf-8")
    from jusik.research_experiment_guard import verify_hashes as real_verify_hashes

    monkeypatch.setattr(runner, "verify_hashes", real_verify_hashes)
    protected_expected = hashlib.sha256(b"before").hexdigest()
    monkeypatch.setattr(
        runner, "_runtime_hashes", lambda *_args: {protected: protected_expected}
    )

    def mixed_sha(path: Path) -> str:
        if path == protected or (path.parent.name == "out" and path.exists()):
            return hashlib.sha256(path.read_bytes()).hexdigest()
        return "b" * 64 if path.name == "variant.py" else "a" * 64

    monkeypatch.setattr(runner, "sha256", mixed_sha)
    calls = 0

    def mutate(*_args: Any) -> tuple[PortfolioSimulation, list[Any]]:
        nonlocal calls
        calls += 1
        protected.write_text("after", encoding="utf-8")
        return _sim(), [
            runner.EquityObservation(
                datetime(2024, 1, 2, tzinfo=UTC),
                Decimal("100000000"),
                Decimal("100000000"),
                {},
            )
        ]

    monkeypatch.setattr(runner, "_run_simulation", mutate)
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        runner._execute(tmp_path, tmp_path / "engine.py", tmp_path / "out", lambda: 0.0)
    assert calls == 1
    output = tmp_path / "retry"
    output.mkdir()
    (output / "failure.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="new or empty"):
        runner.run_experiment(
            tmp_path, tmp_path / "engine.py", output, allow_historical_execution=True
        )


def test_deadline_clock_stops_before_first_call_and_records_all_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _mock_contract(monkeypatch, tmp_path)
    calls = 0

    def fake_run(*_args: Any) -> tuple[PortfolioSimulation, list[Any]]:
        nonlocal calls
        calls += 1
        return _sim(), []

    monkeypatch.setattr(runner, "_run_simulation", fake_run)
    with pytest.raises(TimeoutError):
        runner._execute(
            tmp_path,
            tmp_path / "engine.py",
            tmp_path / "out",
            iter((0.0, 1000.0)).__next__,
        )
    assert calls == 0
    failure = json.loads((tmp_path / "out" / "failure.json").read_text())
    assert len(failure["missing"]) == 32


def test_post_call_deadline_stops_after_one_call_without_variant(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _mock_contract(monkeypatch, tmp_path)
    calls = 0

    def fake_run(*_args: Any) -> tuple[PortfolioSimulation, list[Any]]:
        nonlocal calls
        calls += 1
        return _sim(), []

    monkeypatch.setattr(runner, "_run_simulation", fake_run)
    monkeypatch.setattr(runner, "_verify_simulation_contract", lambda *_args: None)
    monkeypatch.setattr(runner, "_verify_observations", lambda *_args: None)
    monkeypatch.setattr(
        runner, "_verify_accounting", lambda *_args: {"residual": Decimal("0")}
    )
    with pytest.raises(TimeoutError, match="after simulation"):
        runner._execute(
            tmp_path,
            tmp_path / "engine.py",
            tmp_path / "out",
            iter((0.0, 0.0, 1000.0)).__next__,
        )
    assert calls == 1


def test_accounting_failure_stops_after_first_control(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _mock_contract(monkeypatch, tmp_path)
    calls = 0

    def fake_run(*_args: Any) -> tuple[PortfolioSimulation, list[Any]]:
        nonlocal calls
        calls += 1
        return _sim(), []

    monkeypatch.setattr(runner, "_run_simulation", fake_run)
    monkeypatch.setattr(runner, "_verify_simulation_contract", lambda *_args: None)
    monkeypatch.setattr(runner, "_verify_observations", lambda *_args: None)
    monkeypatch.setattr(
        runner,
        "_verify_accounting",
        lambda *_args: (_ for _ in ()).throw(ValueError("accounting mismatch")),
    )
    with pytest.raises(ValueError, match="accounting mismatch"):
        runner._execute(tmp_path, tmp_path / "engine.py", tmp_path / "out", lambda: 0.0)
    assert calls == 1


def test_risk_liquidation_runs_even_with_eight_week_cadence(
    tmp_path: Path,
) -> None:
    from jusik.research_portfolio_held_band_experiment import _load_copy
    from tests.test_research_portfolio import _episode_source

    engine_path = Path(__file__).parents[1] / "jusik" / "research_portfolio_engine.py"
    _original, variant_path = runner._copy_engine(engine_path, tmp_path)
    engine = _load_copy(variant_path, "cadence_risk_engine")
    source = _episode_source()
    config = PortfolioConfig(
        initial_cash_krw=Decimal("1000000"),
        low_turnover_weeks=8,
        low_turnover_band=Decimal("0.04"),
        gross_cap=Decimal("1"),
        symbol_cap=Decimal("1"),
        leveraged_etf_cap=Decimal("1"),
        drawdown_limit=Decimal("0.10"),
        fee_rate=Decimal("0"),
        slippage_rate=Decimal("0"),
        fx_spread_rate=Decimal("0"),
    )
    simulation = engine.simulate(
        source,
        PortfolioCandidate(id="equal", method="equal", gate="none"),
        source.instruments[0].requested_start,
        source.instruments[0].requested_end,
        config,
        "low_turnover_combined",
    )
    assert any(event.kind == "risk_exit" for event in simulation.policy_events)
