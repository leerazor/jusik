from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from jusik.research_portfolio_held_band_experiment import (
    _copy_engine,
    _load_copy,
)
from jusik.research_portfolio_low_cash_experiment import (
    DEV_PERIODS,
    INITIAL_CAPITAL,
    EquityObservation,
    ExperimentRequest,
    _copy_observer_engine,
    _load_source,
    _regular_hashed_file,
    _run_simulation,
    actual_metrics,
    global_drawdown,
    grid,
    verify_accounting,
    verify_observer_parity,
)
from jusik.research_portfolio_models import (
    PortfolioCandidate,
    PortfolioConfig,
    PortfolioEquityPoint,
    PortfolioMetrics,
    PortfolioSimulation,
)


def _simulation(
    *,
    equity: list[PortfolioEquityPoint] | None = None,
) -> PortfolioSimulation:
    points = equity or [
        PortfolioEquityPoint(
            at=datetime(2024, 1, 2, tzinfo=UTC),
            equity_krw=INITIAL_CAPITAL,
            cash_krw=INITIAL_CAPITAL,
            drawdown_pct=Decimal(0),
        )
    ]
    return PortfolioSimulation(
        candidate=PortfolioCandidate(
            id="test", method="inverse_volatility", gate="fx_vix"
        ),
        period_start=date(2024, 1, 1),
        period_end=date(2024, 1, 2),
        metrics=PortfolioMetrics(
            initial_equity_krw=INITIAL_CAPITAL,
            final_equity_krw=points[-1].equity_krw,
            total_return_pct=Decimal(0),
            max_drawdown_pct=Decimal(0),
            trade_count=0,
            transaction_cost_krw=Decimal(0),
            fx_cost_krw=Decimal(0),
            turnover_pct=Decimal(0),
        ),
        complete=True,
        incomplete_reasons=[],
        drawdown_latched=False,
        drawdown_latched_at=None,
        equity=points,
        trades=[],
        weekly_targets=[],
        positions=[],
        contributions_krw={},
        split_cash_in_lieu_krw={},
        overlap_diagnostics={},
        policy="low_turnover_combined",
    )


def test_grid_is_the_fixed_32_case_contract() -> None:
    cases = grid()
    assert len(cases) == 32
    assert cases[0]["id"] == "g060_v010_c4_b002_dd010"
    assert cases[0]["low_turnover_weeks"] == 4
    assert cases[0]["low_turnover_band"] == Decimal("0.02")
    assert cases[0]["drawdown_limit"] == Decimal("0.10")
    assert DEV_PERIODS == (
        ("dev1", "2023-09-13", "2024-09-12"),
        ("dev2", "2024-09-13", "2025-09-12"),
    )


def test_observer_copy_preserves_full_simulation_and_records_actual_values(
    tmp_path: Path,
) -> None:
    from tests.test_research_portfolio import _source

    source = _source()
    engine_path = Path(__file__).parents[1] / "jusik" / "research_portfolio_engine.py"
    _original, variant_path = _copy_engine(engine_path, tmp_path)
    observer_path = _copy_observer_engine(variant_path, tmp_path)
    corrected = _load_copy(variant_path, "low_cash_parity_corrected")
    observed = _load_copy(observer_path, "low_cash_parity_observed")
    period = (
        "fixture",
        source.instruments[0].requested_start.isoformat(),
        source.instruments[0].requested_end.isoformat(),
    )
    candidate = PortfolioCandidate(id="test", method="equal", gate="none")
    config = PortfolioConfig(
        initial_cash_krw=Decimal("1000000"),
        symbol_cap=Decimal("0.60"),
        gross_cap=Decimal("0.60"),
        leveraged_etf_cap=Decimal("0.20"),
        fee_rate=Decimal("0.001"),
        slippage_rate=Decimal("0.001"),
        fx_spread_rate=Decimal("0.001"),
    )
    off, off_observations = _run_simulation(
        corrected, source, candidate, period, config, False
    )
    on, on_observations = _run_simulation(
        observed, source, candidate, period, config, True
    )
    verify_observer_parity(off, on)
    verify_accounting(on, on_observations, config, source)
    assert on.trades
    equity_body = (
        observer_path.read_text().split("    def equity(")[1].split("    grouped:")[0]
    )
    assert equity_body.count("fx_for(symbol, at)") == 1
    assert not off_observations
    assert on_observations
    assert any(
        item.instruments[0].instrument.currency == "USD" for item in source.instruments
    )
    assert all(
        item.at.utcoffset() == UTC.utcoffset(item.at) for item in on_observations
    )
    assert any(item.at.tzinfo is not None for item in on_observations)


def test_one_krw_nav_or_cash_tamper_is_rejected() -> None:
    from tests.test_research_portfolio import _source

    point = PortfolioEquityPoint(
        at=datetime(2024, 1, 2, tzinfo=UTC),
        equity_krw=INITIAL_CAPITAL,
        cash_krw=INITIAL_CAPITAL,
        drawdown_pct=Decimal(0),
    )
    simulation = _simulation(equity=[point])
    observation = EquityObservation(
        at=point.at,
        nav_krw=point.equity_krw,
        cash_krw=point.cash_krw,
        position_values_krw={},
    )
    verify_accounting(simulation, [observation], PortfolioConfig(), _source())
    bad_nav = observation.__class__(
        observation.at,
        observation.nav_krw + Decimal(1),
        observation.cash_krw,
        observation.position_values_krw,
    )
    with pytest.raises(ValueError, match="NAV does not reconcile"):
        verify_accounting(simulation, [bad_nav], PortfolioConfig(), _source())
    bad_cash = observation.__class__(
        observation.at,
        observation.nav_krw,
        observation.cash_krw + Decimal(1),
        observation.position_values_krw,
    )
    with pytest.raises(ValueError, match="NAV does not reconcile"):
        verify_accounting(simulation, [bad_cash], PortfolioConfig(), _source())


def test_source_hash_rejection_and_request_schema_are_strict(tmp_path: Path) -> None:
    source_path = tmp_path / "source.json"
    source_path.write_text("{}\n", encoding="utf-8")
    request = ExperimentRequest(
        source_path=str(source_path),
        source_sha256=hashlib.sha256(source_path.read_bytes()).hexdigest(),
        engine_path=str(source_path),
        engine_sha256=hashlib.sha256(source_path.read_bytes()).hexdigest(),
    )
    with pytest.raises(ValueError, match="source is not a valid"):
        _load_source(request)
    with pytest.raises(ValueError, match="hash mismatch"):
        _regular_hashed_file(source_path, "0" * 64, "source")
    with pytest.raises(ValueError):
        ExperimentRequest.model_validate({**request.model_dump(), "extra": 1})


def test_global_drawdown_includes_initial_capital() -> None:
    observations = [
        EquityObservation(
            datetime(2024, 1, 2, tzinfo=UTC),
            Decimal("99000000"),
            Decimal("99000000"),
            {},
        )
    ]
    assert global_drawdown(observations) == Decimal(1)


def test_split_fx_timezone_duplicate_and_nonfinite_guards(tmp_path: Path) -> None:
    from tests.test_research_portfolio import _instrument_snapshot, _source

    source = _source()
    payload = source.model_dump(mode="json")
    payload["instruments"][0]["instruments"][0]["bars"].append(
        payload["instruments"][0]["instruments"][0]["bars"][0]
    )
    duplicate_body = json.dumps(payload).encode()
    duplicate_path = tmp_path / "duplicate-source.json"
    duplicate_path.write_bytes(duplicate_body)
    duplicate_request = ExperimentRequest(
        source_path=str(duplicate_path),
        source_sha256=hashlib.sha256(duplicate_body).hexdigest(),
        engine_path=str(duplicate_path),
        engine_sha256=hashlib.sha256(duplicate_body).hexdigest(),
    )
    with pytest.raises(ValueError, match="source is not a valid|duplicate price dates"):
        _load_source(duplicate_request)
    with pytest.raises(ValueError, match="non-finite JSON"):
        from jusik.research_portfolio_low_cash_experiment import _strict_json

        _strict_json(b'{"value": NaN}', "fixture")
    valid_path = tmp_path / "valid-source.json"
    valid_body = source.model_dump_json().encode()
    valid_path.write_bytes(valid_body)
    loaded = _load_source(
        ExperimentRequest(
            source_path=str(valid_path),
            source_sha256=hashlib.sha256(valid_body).hexdigest(),
            engine_path=str(duplicate_path),
            engine_sha256=hashlib.sha256(duplicate_body).hexdigest(),
        )
    )
    assert any(
        item.instruments[0].instrument.currency == "USD" for item in loaded.instruments
    )
    split_snapshot = _instrument_snapshot(
        "SPLITUSD", "USD", "America/New_York", split_at=70
    )
    split_source = source.model_copy(
        update={
            "instruments": [split_snapshot],
            "stock_snapshot_ids": {"SPLITUSD": "snapshot"},
        }
    )
    assert split_source.instruments[0].corporate_actions
    assert split_source.instruments[0].instruments[0].instrument.timezone == (
        "America/New_York"
    )


def test_actual_metrics_records_leverage_violations_and_cash_quantiles() -> None:
    simulation = _simulation()
    observations = [
        EquityObservation(
            datetime(2024, 1, 2, tzinfo=UTC),
            Decimal("100"),
            Decimal("80"),
            {"TQQQ": Decimal("20")},
        ),
        EquityObservation(
            datetime(2024, 1, 3, tzinfo=UTC),
            Decimal("100"),
            Decimal("90"),
            {"TQQQ": Decimal("10")},
        ),
    ]
    metrics = actual_metrics(simulation, observations)
    assert metrics["daily_cash_median_krw"] == INITIAL_CAPITAL
    assert metrics["daily_cash_median_pct"] == Decimal("100")
    assert metrics["max_actual_leverage_pct"] == Decimal("20")
    assert metrics["leverage_violations"] == []


@pytest.mark.parametrize(
    "field",
    [
        "final_equity_krw",
        "total_return_pct",
        "transaction_cost_krw",
        "fx_cost_krw",
        "turnover_pct",
        "max_drawdown_pct",
    ],
)
def test_metric_tampering_is_rejected(field: str) -> None:
    from tests.test_research_portfolio import _source

    sim = _simulation()
    delta = Decimal("0.000001") if field == "total_return_pct" else Decimal(1)
    sim = sim.model_copy(
        update={
            "metrics": sim.metrics.model_copy(
                update={field: getattr(sim.metrics, field) + delta}
            )
        }
    )
    observation = EquityObservation(
        sim.equity[0].at, INITIAL_CAPITAL, INITIAL_CAPITAL, {}
    )
    with pytest.raises(ValueError):
        verify_accounting(sim, [observation], PortfolioConfig(), _source())


def test_cash_percentage_selection_overrides_absolute_cash() -> None:
    from jusik.research_portfolio_low_cash_experiment import _eligible

    rows: list[dict[str, object]] = []
    baseline: dict[tuple[str, int], dict[str, object]] = {}
    for period in ("dev1", "dev2"):
        for cost in (1, 2):
            baseline[(period, cost)] = {
                "daily_cash_median_pct": Decimal(80),
                "daily_cash_median_krw": Decimal(80),
                "trade_days": 2,
            }
            rows.append(
                {
                    "candidate_id": "candidate",
                    "period": period,
                    "cost_multiplier": cost,
                    "complete": True,
                    "accounting_valid": True,
                    "global_drawdown_pct": Decimal(0),
                    "max_actual_leverage_pct": Decimal(0),
                    "daily_cash_median_pct": Decimal(50),
                    "daily_cash_median_krw": Decimal(100),
                    "trade_days": 2,
                }
            )
    assert _eligible("candidate", rows, baseline)
    rows[0]["daily_cash_median_pct"] = Decimal(80)
    assert not _eligible("candidate", rows, baseline)


def test_calendar_annualization_and_empty_months() -> None:
    from jusik.research_portfolio_models import PortfolioTrade

    sim = _simulation().model_copy(update={"period_end": date(2024, 2, 29)})
    sim = sim.model_copy(
        update={
            "trades": [
                PortfolioTrade(
                    decided_at=sim.equity[0].at,
                    executed_at=sim.equity[0].at,
                    symbol="KRTEST",
                    side="buy",
                    quantity=1,
                    local_price=Decimal(100),
                    fx_rate=Decimal(1),
                    notional_krw=Decimal(100),
                    transaction_cost_krw=Decimal(0),
                    fx_cost_krw=Decimal(0),
                )
            ]
        }
    )
    result = actual_metrics(sim, [])
    expected = Decimal(100) / INITIAL_CAPITAL * Decimal("365.25") / 60 * 100
    assert result["annual_notional_turnover_pct"] == expected
    assert result["trade_days_by_month"] == {"2024-01": 1, "2024-02": 0}


@pytest.mark.parametrize(
    "terminal_failure",
    ["risk", "accounting", "incomplete", "parity", "parity_accounting"],
)
def test_orchestration_actual_short_engine_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, terminal_failure: str
) -> None:
    import jusik.research_portfolio_low_cash_experiment as experiment
    from tests.test_research_portfolio import _source

    source = _source()
    source_path = tmp_path / "input.json"
    source_path.write_text(source.model_dump_json())
    engine_path = Path(__file__).parents[1] / "jusik" / "research_portfolio_engine.py"
    request = ExperimentRequest(
        source_path=str(source_path),
        source_sha256=experiment.sha256(source_path),
        engine_path=str(engine_path),
        engine_sha256=experiment.sha256(engine_path),
    )
    request_path = tmp_path / "request.json"
    request_path.write_text(request.model_dump_json())
    periods = tuple((name, "2024-01-01", "2024-01-03") for name in ("dev1", "dev2"))
    monkeypatch.setattr(experiment, "DEV_PERIODS", periods)
    monkeypatch.setattr(
        experiment,
        "HELDOUT_PERIODS",
        tuple((name, "2024-01-01", "2024-01-03") for name in ("final", "continuous")),
    )
    profiles = grid()[:3]
    monkeypatch.setattr(experiment, "grid", lambda: profiles)
    original_row = experiment._candidate_row
    calls: list[str] = []
    original_run = experiment._run_simulation
    output = tmp_path / "output"

    def run_checked(
        *args: object,
    ) -> tuple[PortfolioSimulation, list[EquityObservation]]:
        # Assert freezes exist before the first execution in each phase.
        assert (output / "preregistration.json").exists()
        if len(calls) < 2:
            assert args[5] is (len(calls) == 1)
            assert not (output / "observer-parity.json").exists()
            assert not (output / "simulations").exists()
        else:
            assert (output / "observer-parity.json").exists()
        period = args[3]
        assert isinstance(period, tuple)
        if period[0] in {"final", "continuous"}:
            assert (output / "finalist-freeze.json").exists()
        calls.append(str(period[0]))
        sim, observations = original_run(*args)  # type: ignore[arg-type]
        if terminal_failure == "parity" and len(calls) == 2:
            sim = sim.model_copy(
                update={"overlap_diagnostics": {"tampered": Decimal(1)}}
            )
        elif terminal_failure == "parity_accounting" and len(calls) == 2:
            observations[-1] = EquityObservation(
                observations[-1].at,
                observations[-1].nav_krw + 1,
                observations[-1].cash_krw,
                observations[-1].position_values_krw,
            )
        if period[0] == "final" and sim.candidate.id != profiles[0]["id"]:
            if terminal_failure == "accounting":
                sim = sim.model_copy(
                    update={
                        "metrics": sim.metrics.model_copy(
                            update={
                                "final_equity_krw": sim.metrics.final_equity_krw + 1
                            }
                        )
                    }
                )
            elif terminal_failure == "incomplete":
                sim = sim.model_copy(
                    update={
                        "complete": False,
                        "incomplete_reasons": ["fixture missing FX"],
                    }
                )
        return sim, observations

    def controlled_row(*args: object) -> dict[str, object]:
        row = original_row(*args)  # type: ignore[arg-type]
        # Inject only selection/risk metrics; simulation and accounting remain real.
        row["daily_cash_median_pct"] = Decimal(
            90 if row["candidate_id"] == profiles[0]["id"] else 80
        )
        if (
            terminal_failure == "risk"
            and row["period"] == "continuous"
            and row["candidate_id"] != profiles[0]["id"]
        ):
            row["global_drawdown_pct"] = Decimal(20)
        if (
            terminal_failure == "risk"
            and row["period"] == "final"
            and row["candidate_id"] == profiles[2]["id"]
        ):
            row["max_actual_leverage_pct"] = Decimal("20.00000002")
        return row

    monkeypatch.setattr(experiment, "_run_simulation", run_checked)
    monkeypatch.setattr(experiment, "_candidate_row", controlled_row)
    if terminal_failure in {"parity", "parity_accounting"}:
        with pytest.raises(ValueError, match="observer changed|NAV does not reconcile"):
            experiment.run(request_path, output)
        assert calls == ["dev1", "dev1"]
        assert not (output / "simulations").exists()
        assert not (output / "finalist-freeze.json").exists()
        assert not (output / "observer-parity.json").exists()
        assert not (output / "results.json").exists()
        failure = json.loads((output / "failure.json").read_text())
        assert failure["ledger"] == []
        return
    result = experiment.run(request_path, output)
    assert len(calls) == 12 + 12 + 2
    assert (
        calls
        == ["dev1", "dev1"]
        + ["dev1", "dev1", "dev2", "dev2"] * 3
        + ["final", "final", "continuous", "continuous"] * 3
    )
    assert result["finalist_ids"] == sorted(
        [str(profiles[1]["id"]), str(profiles[2]["id"])]
    )
    assert result["validated_finalist_ids"] == []
    assert result["negative_result"] is True
    report = (output / "report.md").read_text()
    assert report.startswith("# 저현금")
    assert "continuous" in report and "dev2" in report
    if terminal_failure == "risk":
        assert "global DD >=20%" in report
        assert "actual leverage >20%" in report
    else:
        assert "incomplete/accounting invalid" in report
    with pytest.raises(ValueError, match="must be new"):
        experiment.run(request_path, output)


def test_same_timestamp_states_and_sub_krw_rounding() -> None:
    from tests.test_research_portfolio import _source

    sim = _simulation()
    at = sim.equity[0].at
    before = EquityObservation(at, INITIAL_CAPITAL, INITIAL_CAPITAL, {})
    after = EquityObservation(
        at,
        INITIAL_CAPITAL,
        INITIAL_CAPITAL - 1,
        {"KRTEST": Decimal("1.000000000000000000000000000001")},
    )
    verify_accounting(sim, [before, after], PortfolioConfig(), _source())
    bad_point = sim.equity[0].model_copy(update={"cash_krw": INITIAL_CAPITAL - 2})
    with pytest.raises(ValueError, match="serialized equity"):
        verify_accounting(
            sim.model_copy(update={"equity": [bad_point]}),
            [before, after],
            PortfolioConfig(),
            _source(),
        )


def test_cash_sampling_uses_utc_last_serialized_point() -> None:
    from datetime import timedelta, timezone

    points = [
        PortfolioEquityPoint(
            at=datetime(2024, 1, 3, 1, tzinfo=timezone(timedelta(hours=9))),
            equity_krw=Decimal(200),
            cash_krw=Decimal(120),
            drawdown_pct=Decimal(0),
        ),
        PortfolioEquityPoint(
            at=datetime(2024, 1, 2, 23, tzinfo=UTC),
            equity_krw=Decimal(400),
            cash_krw=Decimal(160),
            drawdown_pct=Decimal(0),
        ),
    ]
    result = actual_metrics(
        _simulation(equity=points),
        [
            EquityObservation(
                datetime(2024, 1, 3, tzinfo=UTC), Decimal(100), Decimal(100), {}
            )
        ],
    )
    assert result["daily_cash_median_pct"] == Decimal(40)
    assert result["daily_cash_median_krw"] == Decimal(160)
