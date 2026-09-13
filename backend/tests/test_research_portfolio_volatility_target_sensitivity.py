import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest
import jusik.research_portfolio_gross_cap_sensitivity as gross
import jusik.research_portfolio_held_band_cost3_stress as cost3

from jusik.research_portfolio_models import (
    PortfolioCandidate,
    PortfolioConfig,
    PortfolioEquityPoint,
    PortfolioMetrics,
    PortfolioSimulation,
)
from jusik.research_portfolio_volatility_target_sensitivity import (
    ARMS,
    EVALUATION_CAP,
    EquityObservation,
    _config,
    _daily_metrics,
    _execute,
    _load_contract,
    _runtime_hashes,
    COST3_HELPER_SHA256,
    GROSS_HELPER_SHA256,
    _strict_json,
    _verify_observations,
    cap_observations,
    global_drawdown,
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
    assert ARMS == (("control", Decimal("0.10")), ("variant", Decimal("0.15")))
    assert EVALUATION_CAP == 32
    config = _config(PortfolioConfig(), Decimal("0.15"), 3)
    assert config.volatility_target == Decimal("0.15")
    with pytest.raises(ValueError):
        _config(PortfolioConfig(), Decimal("0.20"), 1)


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


def test_global_drawdown_uses_initial_capital_and_running_peak() -> None:
    points = [
        EquityObservation(
            datetime(2024, 1, n, tzinfo=UTC), Decimal(str(nav)), Decimal("0"), {}
        )
        for n, nav in ((1, 100), (2, 90), (3, 110), (4, 88))
    ]
    assert global_drawdown(points, Decimal("100")) == Decimal("20")


def test_cap_observations_reports_exact_boundary_and_epsilon_excess() -> None:
    at = datetime(2024, 1, 2, tzinfo=UTC)
    config = PortfolioConfig(gross_cap=Decimal("0.40"))
    exact = EquityObservation(
        at,
        Decimal("100"),
        Decimal("40"),
        {"NVDA": Decimal("20"), "TQQQ": Decimal("20")},
    )
    epsilon = EquityObservation(
        at,
        Decimal("100"),
        Decimal("39.998"),
        {"NVDA": Decimal("20"), "TQQQ": Decimal("20.002")},
    )
    assert cap_observations([exact], config)["excess"] == {
        "gross": [],
        "symbol": [],
        "leveraged": [],
    }
    excess = cap_observations([epsilon], config)["excess"]
    assert {item["symbol"] for item in excess["symbol"]} == {"TQQQ"}
    assert excess["gross"]
    assert excess["leveraged"]


@pytest.mark.parametrize("field", ["nav", "cash"])
def test_observer_rejects_nonfinite_values(field: str) -> None:
    value = Decimal("NaN")
    observation = EquityObservation(
        datetime(2024, 1, 2, tzinfo=UTC),
        value if field == "nav" else Decimal("100"),
        value if field == "cash" else Decimal("100"),
        {},
    )
    with pytest.raises(ValueError):
        _verify_observations(_sim(), [observation], PortfolioConfig())


@pytest.mark.parametrize(
    "observation",
    [
        EquityObservation(
            datetime(2024, 1, 2, tzinfo=UTC), Decimal("0"), Decimal("0"), {}
        ),
        EquityObservation(
            datetime(2024, 1, 2, tzinfo=UTC), Decimal("100"), Decimal("-1"), {}
        ),
        EquityObservation(
            datetime(2024, 1, 2, tzinfo=UTC),
            Decimal("100"),
            Decimal("101"),
            {"NVDA": Decimal("-1")},
        ),
        EquityObservation(datetime(2024, 1, 2), Decimal("100"), Decimal("100"), {}),
    ],
)
def test_observer_rejects_invalid_values_or_timestamp(
    observation: EquityObservation,
) -> None:
    with pytest.raises(ValueError):
        _verify_observations(_sim(), [observation], PortfolioConfig())


def test_observer_requires_serialized_points_and_allows_same_timestamp() -> None:
    at = datetime(2024, 1, 2, tzinfo=UTC)
    values = {"NVDA": Decimal("20000000")}
    first = EquityObservation(at, Decimal("100000000"), Decimal("80000000"), values)
    second = EquityObservation(at, Decimal("100000000"), Decimal("80000000"), values)
    assert _verify_observations(_sim(), [first, second], PortfolioConfig()) is None
    missing = _sim().model_copy(
        update={
            "equity": [
                _sim()
                .equity[0]
                .model_copy(update={"at": datetime(2024, 1, 3, tzinfo=UTC)})
            ]
        }
    )
    with pytest.raises(ValueError, match="serialized equity"):
        _verify_observations(missing, [first], PortfolioConfig())


def test_observer_rejects_reversed_timestamps() -> None:
    later = EquityObservation(
        datetime(2024, 1, 3, tzinfo=UTC), Decimal("100"), Decimal("100"), {}
    )
    earlier = EquityObservation(
        datetime(2024, 1, 2, tzinfo=UTC), Decimal("100"), Decimal("100"), {}
    )
    with pytest.raises(ValueError, match="chronological"):
        _verify_observations(_sim(), [later, earlier], PortfolioConfig())


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


def test_strict_json_rejects_duplicate_and_nonfinite(tmp_path: Path) -> None:
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"a": 1, "a": 2}', encoding="utf-8")
    with pytest.raises(ValueError):
        _strict_json(duplicate)
    nonfinite = tmp_path / "nonfinite.json"
    nonfinite.write_text('{"a": NaN}', encoding="utf-8")
    with pytest.raises(ValueError):
        _strict_json(nonfinite)


def _mock_contract(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> list[dict[str, str]]:
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
        "jusik.research_portfolio_volatility_target_sensitivity._json",
        lambda path: (
            {
                "evaluations": [
                    {"artifact": f"{p['name']}-control_c{c}.json", "sha256": "b" * 64}
                    for p in periods
                    for c in (1, 3)
                ]
            }
            if path.name == "results.json"
            else {"periods": periods}
        ),
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_volatility_target_sensitivity._load_contract",
        lambda _path: (prereg, SimpleNamespace(instruments=[]), PortfolioConfig()),
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_volatility_target_sensitivity._coverage",
        lambda _source: [],
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_volatility_target_sensitivity._verify_runtime_hashes",
        lambda _path: None,
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_volatility_target_sensitivity.verify_hashes",
        lambda _checks: None,
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_volatility_target_sensitivity.VARIANT_SHA256",
        "b" * 64,
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_volatility_target_sensitivity.MANDATE_SHA256",
        "a" * 64,
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_volatility_target_sensitivity._copy_engine",
        lambda _path, out: (out / "original.py", out / "variant.py"),
    )

    def fake_sha(path: Path) -> str:
        return "b" * 64 if path.name == "variant.py" else "a" * 64

    monkeypatch.setattr(
        "jusik.research_portfolio_volatility_target_sensitivity.sha256", fake_sha
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_volatility_target_sensitivity._copy_observer_engine",
        lambda _path, out: out / "observer.py",
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_volatility_target_sensitivity._load_copy",
        lambda _path, _name: ModuleType("fake"),
    )
    return periods


def test_mock_orchestration_prereg_then_controls_then_variants(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    periods = _mock_contract(monkeypatch, tmp_path)
    calls: list[tuple[str, Decimal, Decimal, bool]] = []
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

    def fake_run(
        _engine: ModuleType,
        _source: Any,
        _candidate: PortfolioCandidate,
        period: dict[str, str],
        config: PortfolioConfig,
    ) -> tuple[PortfolioSimulation, list[EquityObservation]]:
        calls.append(
            (
                period["name"],
                config.volatility_target,
                config.fee_rate,
                (tmp_path / "output" / "preregistration.json").exists(),
            )
        )
        return simulation, [observation]

    monkeypatch.setattr(
        "jusik.research_portfolio_volatility_target_sensitivity._run_simulation",
        fake_run,
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_volatility_target_sensitivity._verify_simulation_contract",
        lambda *_args: None,
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_volatility_target_sensitivity._verify_accounting",
        lambda *_args: {"residual": Decimal("0")},
    )
    replay_paths: list[str] = []
    monkeypatch.setattr(
        "jusik.research_portfolio_volatility_target_sensitivity._verify_exact_replay",
        lambda _payload, path, _digest: replay_paths.append(path.name),
    )
    results = {
        "evaluations": [
            {
                "artifact": f"{p['name']}-control_c{c}.json",
                "sha256": "b" * 64,
                "cost_multiplier": c,
            }
            for p in periods
            for c in (1, 3)
        ]
    }
    monkeypatch.setattr(
        "jusik.research_portfolio_volatility_target_sensitivity._json",
        lambda path: results if path.name == "results.json" else {"periods": periods},
    )
    output = tmp_path / "output"
    result = _execute(tmp_path, tmp_path / "engine.py", output, lambda: 0.0)
    assert result["evaluation_count"] == 32
    assert len(calls) == 32 and all(item[3] for item in calls)
    assert len(result["evaluations"]) == 32
    assert calls[:16] and all(cap == Decimal("0.10") for _, cap, _, _ in calls[:16])
    assert all(cap == Decimal("0.15") for _, cap, _, _ in calls[16:])
    assert replay_paths == [
        f"{p['name']}-control_c{c}.json" for p in periods for c in (1, 3)
    ]


def test_mock_replay_or_accounting_failure_stops_before_variant(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    periods = _mock_contract(monkeypatch, tmp_path)
    simulation = _sim()
    observation = EquityObservation(
        datetime(2024, 1, 2, tzinfo=UTC),
        Decimal("100000000"),
        Decimal("80000000"),
        {"NVDA": Decimal("20000000")},
    )
    calls: list[int] = []

    def fake_run(*_args: Any) -> tuple[PortfolioSimulation, list[EquityObservation]]:
        calls.append(1)
        return simulation, [observation]

    monkeypatch.setattr(
        "jusik.research_portfolio_volatility_target_sensitivity._run_simulation",
        fake_run,
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_volatility_target_sensitivity._verify_simulation_contract",
        lambda *_args: None,
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_volatility_target_sensitivity._verify_accounting",
        lambda *_args: {"residual": Decimal("0")},
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_volatility_target_sensitivity._json",
        lambda path: (
            {
                "evaluations": [
                    {"artifact": f"{p['name']}-control_c{c}.json", "sha256": "b" * 64}
                    for p in periods
                    for c in (1, 3)
                ]
            }
            if path.name == "results.json"
            else {"periods": periods}
        ),
    )
    replay_calls = []

    def fail_replay(*_args: Any) -> None:
        replay_calls.append(1)
        raise ValueError("mismatch")

    monkeypatch.setattr(
        "jusik.research_portfolio_volatility_target_sensitivity._verify_exact_replay",
        fail_replay,
    )
    with pytest.raises(ValueError, match="mismatch"):
        _execute(tmp_path, tmp_path / "engine.py", tmp_path / "out", lambda: 0.0)
    assert len(calls) == 1
    assert replay_calls == [1]


def test_nonempty_output_refuses_retry_without_calls(tmp_path: Path) -> None:
    output = tmp_path / "output"
    output.mkdir()
    (output / "failure.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError):
        from jusik.research_portfolio_volatility_target_sensitivity import (
            run_experiment,
        )

        run_experiment(tmp_path, tmp_path / "engine.py", output)


def test_deadline_stops_before_first_simulation_and_records_all_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _mock_contract(monkeypatch, tmp_path)
    calls: list[int] = []
    monkeypatch.setattr(
        "jusik.research_portfolio_volatility_target_sensitivity._run_simulation",
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


def test_accounting_failure_stops_after_first_simulation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    periods = _mock_contract(monkeypatch, tmp_path)
    simulation = _sim()
    observation = EquityObservation(
        datetime(2024, 1, 2, tzinfo=UTC),
        Decimal("100000000"),
        Decimal("80000000"),
        {"NVDA": Decimal("20000000")},
    )
    calls: list[int] = []

    def fake_run(*_args: Any) -> tuple[PortfolioSimulation, list[EquityObservation]]:
        calls.append(1)
        return simulation, [observation]

    monkeypatch.setattr(
        "jusik.research_portfolio_volatility_target_sensitivity._run_simulation",
        fake_run,
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_volatility_target_sensitivity._verify_simulation_contract",
        lambda *_args: None,
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_volatility_target_sensitivity._verify_accounting",
        lambda *_args: (_ for _ in ()).throw(ValueError("accounting mismatch")),
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_volatility_target_sensitivity._json",
        lambda path: (
            {
                "evaluations": [
                    {"artifact": f"{p['name']}-control_c{c}.json", "sha256": "b" * 64}
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
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "jusik.research_portfolio_volatility_target_sensitivity._load_contract",
        lambda _path: (_ for _ in ()).throw(ValueError("malformed prereg")),
    )
    with pytest.raises(ValueError, match="malformed prereg"):
        _execute(tmp_path, tmp_path / "engine.py", tmp_path / "out", lambda: 0.0)
    failure = tmp_path / "out" / "failure.json"
    assert failure.exists()
    assert "malformed prereg" in failure.read_text()


def test_load_contract_rejects_corrupt_pinned_preregistration(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    prereg = tmp_path / "preregistration.json"
    manifest = tmp_path / "hash-manifest.json"
    prereg.write_text("{}", encoding="utf-8")
    manifest.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        "jusik.research_portfolio_volatility_target_sensitivity.PRIOR_PREREG_SHA256",
        "f" * 64,
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_volatility_target_sensitivity.PRIOR_MANIFEST_SHA256",
        sha256(manifest),
    )
    with pytest.raises(ValueError, match="hash mismatch"):
        _load_contract(tmp_path)


def test_load_contract_rejects_missing_manifest_artifact(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    prereg = tmp_path / "preregistration.json"
    manifest = tmp_path / "hash-manifest.json"
    prereg.write_text("{}", encoding="utf-8")
    manifest.write_text('{"missing.json":"' + "a" * 64 + '"}', encoding="utf-8")
    monkeypatch.setattr(
        "jusik.research_portfolio_volatility_target_sensitivity.PRIOR_PREREG_SHA256",
        sha256(prereg),
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_volatility_target_sensitivity.PRIOR_MANIFEST_SHA256",
        sha256(manifest),
    )
    monkeypatch.setattr(
        "jusik.research_portfolio_volatility_target_sensitivity.verify_hashes",
        lambda _checks: None,
    )
    with pytest.raises(ValueError, match="manifest path is invalid"):
        _load_contract(tmp_path)


def test_runtime_hashes_contains_both_pinned_helpers(tmp_path: Path) -> None:
    files = [tmp_path / name for name in ("engine.py", "original.py", "variant.py", "observer.py", "mandate.json", "results.json")]
    for path in files:
        path.write_text("{}", encoding="utf-8")
    checks = _runtime_hashes(
        tmp_path,
        {"source_paths": {}, "source_hashes": {}},
        files[0], files[1], files[2], files[3], files[4],
    )
    assert checks[Path(gross.__file__)] == GROSS_HELPER_SHA256
    assert checks[Path(cost3.__file__)] == COST3_HELPER_SHA256


def test_zero_nav_observation_is_valid_and_drawdown_is_initial_inclusive() -> None:
    zero = EquityObservation(
        datetime(2024, 1, 2, tzinfo=UTC), Decimal("0"), Decimal("0"), {}
    )
    simulation = _sim().model_copy(update={"equity": []})
    assert _verify_observations(simulation, [zero], PortfolioConfig()) is None
    assert global_drawdown([zero]) == Decimal("100")
