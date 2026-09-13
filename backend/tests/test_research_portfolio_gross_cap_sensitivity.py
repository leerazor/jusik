# mypy: ignore-errors
import json
from datetime import UTC, date, datetime
from decimal import Decimal
from types import ModuleType, SimpleNamespace

import pytest

from jusik.research_portfolio_gross_cap_sensitivity import (
    ARMS,
    EVALUATION_CAP,
    EquityObservation,
    _config,
    _daily_metrics,
    _execute,
    _strict_json,
    _verify_observations,
    cap_observations,
    global_drawdown,
)
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
                cash_krw=Decimal("80000000"),
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
    )


def test_contract_constants_and_config() -> None:
    assert ARMS == (("control", Decimal("0.60")), ("variant", Decimal("0.80")))
    assert EVALUATION_CAP == 32
    config = _config(PortfolioConfig(), Decimal("0.80"), 3)
    assert config.gross_cap == Decimal("0.80")
    with pytest.raises(ValueError):
        _config(PortfolioConfig(), Decimal("0.70"), 1)


def test_observer_boundary_drawdown_and_cap_excess() -> None:
    at = datetime(2024, 1, 2, tzinfo=UTC)
    observation = EquityObservation(
        at,
        Decimal("100000000"),
        Decimal("80000000"),
        {"NVDA": Decimal("20000000"), "TQQQ": Decimal("0")},
    )
    simulation = _sim()
    _verify_observations(simulation, [observation], PortfolioConfig())
    assert global_drawdown([observation]) == Decimal("0")
    assert cap_observations([observation], PortfolioConfig())["excess"]["gross"] == []


def test_observer_rejects_negative_nonfinite_and_duplicate_order() -> None:
    at = datetime(2024, 1, 2, tzinfo=UTC)
    bad = EquityObservation(at, Decimal("100000000"), Decimal("100000001"), {})
    with pytest.raises(ValueError):
        _verify_observations(_sim(), [bad], PortfolioConfig())


def test_daily_metrics_uses_arithmetic_ratio_mean_and_initial_turnover() -> None:
    first = EquityObservation(
        datetime(2024, 1, 2, tzinfo=UTC),
        Decimal("100"),
        Decimal("50"),
        {"NVDA": Decimal("50")},
    )
    second = EquityObservation(
        datetime(2024, 1, 3, tzinfo=UTC),
        Decimal("200"),
        Decimal("100"),
        {"NVDA": Decimal("100")},
    )
    simulation = _sim().model_copy(update={"trades": []})
    metrics = _daily_metrics(simulation, [first, second])
    assert Decimal(metrics["daily_mean_cash_pct"]) == Decimal("50")
    assert Decimal(metrics["daily_mean_gross_pct"]) == Decimal("50")
    assert Decimal(metrics["recomputed_turnover_pct_initial"]) == Decimal("0")


def test_strict_json_rejects_duplicate_and_nonfinite(tmp_path) -> None:
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"a": 1, "a": 2}', encoding="utf-8")
    with pytest.raises(ValueError):
        _strict_json(duplicate)
    nonfinite = tmp_path / "nonfinite.json"
    nonfinite.write_text('{"a": NaN}', encoding="utf-8")
    with pytest.raises(ValueError):
        _strict_json(nonfinite)


def _mock_contract(monkeypatch, tmp_path):
    periods = [
        {"name": name, "start": "2024-01-01", "end": "2024-01-02"}
        for name in [f"fold_{i}" for i in range(1, 8)] + ["continuous"]
    ]
    prereg = {
        "periods": periods,
        "source_paths": {"source-manifest.json": str(tmp_path / "source.json")},
        "source_hashes": {},
        "base_config": PortfolioConfig().model_dump(mode="json"),
    }
    monkeypatch.setattr(
        "jusik.research_portfolio_gross_cap_sensitivity._json",
        lambda path: (
            {
                "evaluations": [
                    {"artifact": f"{p['name']}-variant_c{c}.json", "sha256": "b" * 64}
                    for p in periods
                    for c in (1, 3)
                ]
            }
            if path.name == "results.json"
            else {"periods": periods}
        ),
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_gross_cap_sensitivity._load_contract",
        lambda _path: (prereg, SimpleNamespace(instruments=[]), PortfolioConfig()),
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_gross_cap_sensitivity.load_frozen", lambda _path: {}
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_gross_cap_sensitivity._coverage", lambda _source: []
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_gross_cap_sensitivity._verify_runtime_hashes",
        lambda _path: None,
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_gross_cap_sensitivity.verify_hashes",
        lambda _checks: None,
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_gross_cap_sensitivity.VARIANT_SHA256", "b" * 64
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_gross_cap_sensitivity.MANDATE_SHA256", "a" * 64
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_gross_cap_sensitivity._copy_engine",
        lambda _path, out: (out / "original.py", out / "variant.py"),
    )

    def fake_sha(path):
        return "b" * 64 if path.name == "variant.py" else "a" * 64

    monkeypatch.setattr(
        "jusik.research_portfolio_gross_cap_sensitivity.sha256", fake_sha
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_gross_cap_sensitivity._copy_observer_engine",
        lambda _path, out: out / "observer.py",
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_gross_cap_sensitivity._load_copy",
        lambda _path, _name: ModuleType("fake"),
    )
    return periods


def test_mock_orchestration_prereg_then_controls_then_variants(
    monkeypatch, tmp_path
) -> None:
    periods = _mock_contract(monkeypatch, tmp_path)
    calls = []
    simulation = _sim().model_copy(
        update={
            "equity": [
                PortfolioEquityPoint(
                    at=datetime(2024, 1, 2, tzinfo=UTC),
                    equity_krw=Decimal("100000000"),
                    cash_krw=Decimal("100000000"),
                    drawdown_pct=Decimal("0"),
                )
            ]
        }
    )
    observation = EquityObservation(
        datetime(2024, 1, 2, tzinfo=UTC), Decimal("100000000"), Decimal("100000000"), {}
    )

    def fake_run(_engine, _source, _candidate, period, config):
        calls.append(
            (
                period["name"],
                config.gross_cap,
                config.fee_rate,
                (tmp_path / "output" / "preregistration.json").exists(),
            )
        )
        return simulation, [observation]

    monkeypatch.setattr(
        "jusik.research_portfolio_gross_cap_sensitivity._run_simulation", fake_run
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_gross_cap_sensitivity._verify_simulation_contract",
        lambda *_args: None,
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_gross_cap_sensitivity._verify_accounting",
        lambda *_args: {"residual": Decimal("0")},
    )
    replay_paths = []
    monkeypatch.setattr(
        "jusik.research_portfolio_gross_cap_sensitivity._verify_exact_replay",
        lambda _payload, path, _digest: replay_paths.append(path.name),
    )
    results = {
        "evaluations": [
            {
                "artifact": f"{p['name']}-variant_c{c}.json",
                "sha256": "b" * 64,
                "cost_multiplier": c,
            }
            for p in periods
            for c in (1, 3)
        ]
    }
    monkeypatch.setattr(
        "jusik.research_portfolio_gross_cap_sensitivity._json",
        lambda path: results if path.name == "results.json" else {"periods": periods},
    )
    output = tmp_path / "output"
    result = _execute(tmp_path, tmp_path / "engine.py", output, lambda: 0.0)
    assert result["evaluation_count"] == 32
    assert len(calls) == 32 and all(item[3] for item in calls)
    assert len(result["evaluations"]) == 32
    assert calls[:16] and all(cap == Decimal("0.60") for _, cap, _, _ in calls[:16])
    assert all(cap == Decimal("0.80") for _, cap, _, _ in calls[16:])
    assert replay_paths == [
        f"{p['name']}-variant_c{c}.json" for p in periods for c in (1, 3)
    ]


def test_mock_replay_or_accounting_failure_stops_before_variant(
    monkeypatch, tmp_path
) -> None:
    periods = _mock_contract(monkeypatch, tmp_path)
    simulation = _sim()
    observation = EquityObservation(
        datetime(2024, 1, 2, tzinfo=UTC),
        Decimal("100000000"),
        Decimal("80000000"),
        {"NVDA": Decimal("20000000")},
    )
    calls = []
    monkeypatch.setattr(
        "jusik.research_portfolio_gross_cap_sensitivity._run_simulation",
        lambda *_args: calls.append(1) or (simulation, [observation]),
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_gross_cap_sensitivity._verify_simulation_contract",
        lambda *_args: None,
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_gross_cap_sensitivity._verify_accounting",
        lambda *_args: {"residual": Decimal("0")},
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_gross_cap_sensitivity._json",
        lambda path: (
            {
                "evaluations": [
                    {"artifact": f"{p['name']}-variant_c{c}.json", "sha256": "b" * 64}
                    for p in periods
                    for c in (1, 3)
                ]
            }
            if path.name == "results.json"
            else {"periods": periods}
        ),
    )
    replay_calls = []
    monkeypatch.setattr(
        "jusik.research_portfolio_gross_cap_sensitivity._verify_exact_replay",
        lambda *_args: (
            replay_calls.append(1),
            (_ for _ in ()).throw(ValueError("mismatch")),
        )[1],
    )
    with pytest.raises(ValueError, match="mismatch"):
        _execute(tmp_path, tmp_path / "engine.py", tmp_path / "out", lambda: 0.0)
    assert len(calls) == 1
    assert replay_calls == [1]


def test_nonempty_output_refuses_retry_without_calls(tmp_path) -> None:
    output = tmp_path / "output"
    output.mkdir()
    (output / "failure.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError):
        from jusik.research_portfolio_gross_cap_sensitivity import run_experiment

        run_experiment(tmp_path, tmp_path / "engine.py", output)


def test_deadline_stops_before_first_simulation_and_records_all_missing(
    monkeypatch, tmp_path
) -> None:
    _mock_contract(monkeypatch, tmp_path)
    calls = []
    monkeypatch.setattr(
        "jusik.research_portfolio_gross_cap_sensitivity._run_simulation",
        lambda *_args: calls.append(1),
    )
    with pytest.raises(TimeoutError):
        _execute(
            tmp_path,
            tmp_path / "engine.py",
            tmp_path / "out",
            iter((0.0, 1000.0)).__next__,
        )
    assert calls == []
    failure = json.loads((tmp_path / "out" / "failure.json").read_text())
    assert len(failure["missing"]) == 32


def test_accounting_failure_stops_after_first_simulation(monkeypatch, tmp_path) -> None:
    periods = _mock_contract(monkeypatch, tmp_path)
    simulation = _sim()
    observation = EquityObservation(
        datetime(2024, 1, 2, tzinfo=UTC),
        Decimal("100000000"),
        Decimal("80000000"),
        {"NVDA": Decimal("20000000")},
    )
    calls = []
    monkeypatch.setattr(
        "jusik.research_portfolio_gross_cap_sensitivity._run_simulation",
        lambda *_args: calls.append(1) or (simulation, [observation]),
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_gross_cap_sensitivity._verify_simulation_contract",
        lambda *_args: None,
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_gross_cap_sensitivity._verify_accounting",
        lambda *_args: (_ for _ in ()).throw(ValueError("accounting mismatch")),
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_gross_cap_sensitivity._json",
        lambda path: (
            {
                "evaluations": [
                    {"artifact": f"{p['name']}-variant_c{c}.json", "sha256": "b" * 64}
                    for p in periods
                    for c in (1, 3)
                ]
            }
            if path.name == "results.json"
            else {"periods": periods}
        ),
    )
    with pytest.raises(ValueError, match="accounting"):
        _execute(tmp_path, tmp_path / "engine.py", tmp_path / "out", lambda: 0.0)
    assert len(calls) == 1


def test_input_load_failure_preserves_failure_json_before_calls(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(
        "jusik.research_portfolio_gross_cap_sensitivity._load_contract",
        lambda _path: (_ for _ in ()).throw(ValueError("malformed prereg")),
    )
    with pytest.raises(ValueError, match="malformed prereg"):
        _execute(tmp_path, tmp_path / "engine.py", tmp_path / "out", lambda: 0.0)
    failure = tmp_path / "out" / "failure.json"
    assert failure.exists()
    assert "malformed prereg" in failure.read_text()
