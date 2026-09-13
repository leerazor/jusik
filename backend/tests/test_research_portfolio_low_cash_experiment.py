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
        fee_rate=Decimal(0),
        slippage_rate=Decimal(0),
        fx_spread_rate=Decimal(0),
    )
    off, off_observations = _run_simulation(
        corrected, source, candidate, period, config, False
    )
    on, on_observations = _run_simulation(
        observed, source, candidate, period, config, True
    )
    verify_observer_parity(off, on)
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
    assert metrics["daily_cash_median_krw"] == Decimal("85")
    assert metrics["max_actual_leverage_pct"] == Decimal("20")
    assert metrics["leverage_violations"] == []
