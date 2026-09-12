from __future__ import annotations

import hashlib
import os
import signal
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from jusik.research_external_models import ExternalObservation
from jusik.research_portfolio_held_band_cost3_stress import (
    COST3,
    DEADLINE_SECONDS,
    EVALUATION_CAP,
    FULL_EVALUATION_COUNT,
    RATE_3X,
    _arm_deadline,
    _config,
    _disarm_deadline,
    _source_fx,
    _verify_accounting,
    _verify_exact_replay,
    _verify_temporal_accounting,
    preflight,
    run_experiment,
)
from jusik.research_portfolio_models import (
    PortfolioCandidate,
    PortfolioConfig,
    PortfolioEquityPoint,
    PortfolioMetrics,
    PortfolioSimulation,
)


def _simulation() -> PortfolioSimulation:
    candidate = PortfolioCandidate(id="equal", method="equal", gate="none")
    metrics = PortfolioMetrics(
        initial_equity_krw=Decimal("1000000"),
        final_equity_krw=Decimal("1000000"),
        total_return_pct=Decimal("0"),
        max_drawdown_pct=Decimal("0"),
        trade_count=0,
        transaction_cost_krw=Decimal("0"),
        fx_cost_krw=Decimal("0"),
        turnover_pct=Decimal("0"),
    )
    return PortfolioSimulation.model_construct(
        candidate=candidate,
        period_start=date(2024, 1, 1),
        period_end=date(2024, 1, 2),
        metrics=metrics,
        complete=True,
        incomplete_reasons=[],
        drawdown_latched=False,
        drawdown_latched_at=None,
        equity=[
            PortfolioEquityPoint(
                at=datetime(2024, 1, 2, tzinfo=UTC),
                equity_krw=Decimal("1000000"),
                cash_krw=Decimal("1000000"),
                drawdown_pct=Decimal("0"),
            )
        ],
        trades=[],
        weekly_targets=[],
        positions=[],
        contributions_krw={},
        split_cash_in_lieu_krw={},
        overlap_diagnostics={},
        policy="low_turnover_combined",
        policy_events=[],
    )


def test_cost3_rates_and_boundaries() -> None:
    base = PortfolioConfig()
    result = _config(base, "0.04", COST3)
    assert result.fee_rate == RATE_3X
    assert result.slippage_rate == RATE_3X
    assert result.fx_spread_rate == RATE_3X
    with pytest.raises(ValueError):
        _config(base, "0.02", 0)
    with pytest.raises(ValueError):
        _config(base, "0.02", -1)
    with pytest.raises(ValueError):
        _config(base, "0.02", True)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        _config(base.model_copy(update={"fee_rate": Decimal("0")}), "0.02", 3)


def test_exact_replay_delegates_to_full_json_guard(tmp_path: Path) -> None:
    expected = tmp_path / "expected.json"
    expected.write_text('{"a": 1}\n', encoding="utf-8")
    digest = hashlib.sha256(expected.read_bytes()).hexdigest()
    _verify_exact_replay({"a": 1}, expected, digest)
    with pytest.raises(ValueError):
        _verify_exact_replay({"a": 2}, expected, digest)


def test_preflight_uses_stored_artifacts_without_simulate() -> None:
    audit = Path(
        "/home/kwl/.local/share/jusik/portfolio-audit/"
        "portfolio-held-band-interaction-v1-cce0cdf0e5ea43e4a088f2dfe5c2fa74/experiment"
    )
    if not audit.exists():
        pytest.skip("trusted stored artifact audit is unavailable")
    result = preflight(audit)
    assert result["evaluation_count"] == FULL_EVALUATION_COUNT
    assert result["historical_calls"] == 0


def test_run_order_cap_and_deadline_are_declared() -> None:
    assert EVALUATION_CAP == FULL_EVALUATION_COUNT + 16
    assert DEADLINE_SECONDS == 3600


def _fake_contract() -> tuple[PortfolioConfig, dict[str, Any], dict[str, Any]]:
    periods = [
        {"name": name, "start": "2024-01-01", "end": "2024-01-02"}
        for name in [f"fold_{n}" for n in range(1, 8)] + ["continuous"]
    ]
    hashes = {
        f"{period['name']}-control_c{cost}.json": "digest"
        for period in periods
        for cost in (1, 2)
    }
    return (
        PortfolioConfig(),
        {
            "periods": periods,
            "control_hashes": hashes,
            "input_paths": {},
            "source_hashes": {},
            "core_hashes": {},
            "imported_helper_hashes": {},
        },
        {
            "source_run_id": "synthetic",
            "evaluations": [
                {"artifact": name, "sha256": "digest"}
                for period in periods
                for arm in ("control", "variant")
                for cost in (1, 2)
                for name in [f"{period['name']}-{arm}_c{cost}.json"]
            ],
        },
    )


def test_synthetic_run_orders_32_full_before_16_cost3(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    base, prereg, results = _fake_contract()
    calls: list[Decimal] = []

    def simulate(*_args: object) -> PortfolioSimulation:
        config = _args[4]
        assert isinstance(config, PortfolioConfig)
        calls.append(config.fee_rate)
        return _simulation()

    def copy_engine(_engine: Path, output: Path) -> tuple[Path, Path]:
        original, variant = output / "original.py", output / "variant.py"
        original.write_text("original", encoding="utf-8")
        variant.write_text("variant", encoding="utf-8")
        return original, variant

    source = _source_for_test()
    monkeypatch.setattr(
        "jusik.research_portfolio_held_band_cost3_stress._prior_inputs",
        lambda _path: (source, base, prereg, results),
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_held_band_cost3_stress._copy_engine", copy_engine
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_held_band_cost3_stress._load_copy",
        lambda _path, _name: SimpleNamespace(simulate=simulate),
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_held_band_cost3_stress.sha256",
        lambda path: (
            "7d9ccd0d8fef90b11779d4e8c98041eadf8aeac94eb3d289318145504483b442"
            if path.name == "variant.py"
            else "digest"
        ),
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_held_band_cost3_stress._verify_accounting",
        lambda *_args: {"residual": Decimal(0)},
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_held_band_cost3_stress._held_verify_runtime_hashes",
        lambda *_args: None,
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_held_band_cost3_stress._verify_exact_replay",
        lambda *_args: None,
    )
    result = run_experiment(
        tmp_path / "prior",
        tmp_path / "engine.py",
        tmp_path / "output",
        allow_historical_execution=True,
    )
    assert result["evaluation_count"] == 48
    assert len(calls) == 48
    assert all(rate in {Decimal("0.001"), Decimal("0.002")} for rate in calls[:32])
    assert all(rate == RATE_3X for rate in calls[32:])


def _source_for_test() -> Any:
    from tests.test_research_portfolio import _source

    return _source()


def test_replay_failure_stops_before_cost3_and_preserves_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    base, prereg, results = _fake_contract()
    calls = 0

    def simulate(*_args: object) -> PortfolioSimulation:
        nonlocal calls
        calls += 1
        return _simulation()

    original = tmp_path / "original.py"
    variant = tmp_path / "variant.py"
    original.write_text("original", encoding="utf-8")
    variant.write_text("variant", encoding="utf-8")
    monkeypatch.setattr(
        "jusik.research_portfolio_held_band_cost3_stress._prior_inputs",
        lambda _path: (_source_for_test(), base, prereg, results),
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_held_band_cost3_stress._copy_engine",
        lambda _engine, _output: (original, variant),
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_held_band_cost3_stress._load_copy",
        lambda _path, _name: SimpleNamespace(simulate=simulate),
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_held_band_cost3_stress.sha256",
        lambda path: (
            "7d9ccd0d8fef90b11779d4e8c98041eadf8aeac94eb3d289318145504483b442"
            if path.name == "variant.py"
            else "digest"
        ),
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_held_band_cost3_stress._verify_accounting",
        lambda *_args: {"residual": Decimal(0)},
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_held_band_cost3_stress._held_verify_runtime_hashes",
        lambda *_args: None,
    )
    replay_count = 0

    def fail_replay(*_args: object) -> None:
        nonlocal replay_count
        replay_count += 1
        if replay_count == 3:
            raise ValueError("synthetic replay mismatch")

    monkeypatch.setattr(
        "jusik.research_portfolio_held_band_cost3_stress._verify_exact_replay",
        fail_replay,
    )
    with pytest.raises(ValueError, match="synthetic replay mismatch"):
        run_experiment(
            tmp_path / "prior",
            tmp_path / "engine.py",
            tmp_path / "failure-output",
            allow_historical_execution=True,
        )
    assert calls == 3
    failure = __import__("json").loads(
        (tmp_path / "failure-output" / "failure.json").read_text()
    )
    assert len(failure["ledger"]["ledger"]) == 3


def test_incomplete_simulation_stops_before_the_next_call(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    base, prereg, results = _fake_contract()
    calls = 0

    def incomplete_call(*_args: object) -> PortfolioSimulation:
        nonlocal calls
        calls += 1
        return _simulation().model_copy(
            update={"complete": False, "incomplete_reasons": ["synthetic"]}
        )

    monkeypatch.setattr(
        "jusik.research_portfolio_held_band_cost3_stress._prior_inputs",
        lambda _path: (_source_for_test(), base, prereg, results),
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_held_band_cost3_stress._verify_runtime_hashes",
        lambda *_args: None,
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_held_band_cost3_stress._copy_engine",
        lambda _engine, output: (output / "original.py", output / "variant.py"),
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_held_band_cost3_stress._load_copy",
        lambda *_args: SimpleNamespace(simulate=lambda *_args: _simulation()),
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_held_band_cost3_stress._run_call",
        incomplete_call,
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_held_band_cost3_stress.sha256",
        lambda path: (
            "7d9ccd0d8fef90b11779d4e8c98041eadf8aeac94eb3d289318145504483b442"
            if path.name == "variant.py"
            else "digest"
        ),
    )
    with pytest.raises(RuntimeError, match="incomplete simulation"):
        run_experiment(
            tmp_path / "prior",
            tmp_path / "engine.py",
            tmp_path / "incomplete-output",
            allow_historical_execution=True,
        )
    assert calls == 1


def test_without_explicit_approval_never_calls_simulate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    base, prereg, results = _fake_contract()
    calls = 0

    def simulate(*_args: object) -> PortfolioSimulation:
        nonlocal calls
        calls += 1
        return _simulation()

    monkeypatch.setattr(
        "jusik.research_portfolio_held_band_cost3_stress._prior_inputs",
        lambda _path: (_source_for_test(), base, prereg, results),
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_held_band_cost3_stress._copy_engine",
        lambda *_args: (_args[1] / "original.py", _args[1] / "variant.py"),
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_held_band_cost3_stress._verify_runtime_hashes",
        lambda *_args: None,
    )
    with pytest.raises(PermissionError):
        run_experiment(tmp_path / "prior", tmp_path / "engine.py", tmp_path / "output")
    assert calls == 0
    assert (tmp_path / "output" / "failure.json").exists()


def test_existing_output_refusal_preserves_successful_ledger(
    tmp_path: Path,
) -> None:
    output = tmp_path / "existing-output"
    output.mkdir()
    ledger = output / "ledger.json"
    results = output / "results.json"
    ledger.write_text('{"status": "saved"}\n', encoding="utf-8")
    results.write_text('{"status": "complete"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="new or empty"):
        run_experiment(tmp_path / "prior", tmp_path / "engine.py", output)
    assert not (output / "failure.json").exists()
    assert ledger.read_text(encoding="utf-8") == '{"status": "saved"}\n'
    assert results.read_text(encoding="utf-8") == '{"status": "complete"}\n'


def test_process_deadline_interrupts_in_flight_work() -> None:
    previous = _arm_deadline(3600)
    try:
        with pytest.raises(TimeoutError):
            os.kill(os.getpid(), signal.SIGALRM)
            signal.pause()
    finally:
        _disarm_deadline(previous)


def test_terminal_cash_plus_one_is_rejected() -> None:
    source = _source_for_test()
    config = PortfolioConfig(initial_cash_krw=Decimal("1000000"))
    simulation = _simulation()
    _verify_temporal_accounting(simulation, config, source)
    bad = simulation.model_copy(
        update={
            "equity": [
                simulation.equity[0].model_copy(update={"cash_krw": Decimal("1000001")})
            ]
        }
    )
    with pytest.raises(ValueError, match="ending cash"):
        _verify_temporal_accounting(bad, config, source)


def test_runtime_accounting_gate_rejects_cash_mutation_even_if_held_checker_passes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _source_for_test()
    config = PortfolioConfig(initial_cash_krw=Decimal("1000000"))
    simulation = _simulation()
    bad = simulation.model_copy(
        update={
            "equity": [
                simulation.equity[0].model_copy(
                    update={"cash_krw": Decimal("1000001")}
                )
            ]
        }
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_held_band_cost3_stress._held_verify_accounting",
        lambda *_args: None,
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_held_band_cost3_stress.attribute_simulation",
        lambda *_args: {"residual": Decimal(0)},
    )
    with pytest.raises(ValueError, match="ending cash"):
        _verify_accounting(bad, 1, config, source)


def test_source_fx_is_point_in_time_and_freshness_checked() -> None:
    source = _source_for_test()
    observed = date(2024, 2, 5)
    at = datetime(2024, 2, 5, 12, tzinfo=UTC)
    newer = ExternalObservation(
        series="usdkrw",
        observed_on=observed,
        value=Decimal("1400"),
        available_at=datetime(2024, 2, 5, 11, tzinfo=UTC),
        revision="later",
    )
    future = ExternalObservation(
        series="usdkrw",
        observed_on=observed,
        value=Decimal("9999"),
        available_at=at + timedelta(minutes=1),
        revision="future",
    )
    checked = source.model_copy(
        update={
            "external": source.external.model_copy(
                update={"observations": (*source.external.observations, newer, future)}
            )
        }
    )
    assert _source_fx(checked, at, PortfolioConfig()) == Decimal("1400")
    assert (
        _source_fx(checked, datetime(2024, 12, 1, tzinfo=UTC), PortfolioConfig())
        is None
    )
