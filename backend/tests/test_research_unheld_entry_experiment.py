from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from jusik.research_experiment_guard import (
    verify_unheld_entry_source,
)
from jusik.research_portfolio_models import (
    PortfolioCandidate,
    PortfolioConfig,
    PortfolioEquityPoint,
    PortfolioMetrics,
    PortfolioPosition,
    PortfolioSimulation,
    PortfolioTrade,
)
from jusik.research_unheld_entry_experiment import (
    _copy_engine,
    _empty_output,
    _entry_count,
    _load_copy,
    entry_metrics,
    invested_percent_by_utc_day,
)


def _trade(symbol: str, side: str, quantity: int, at: datetime) -> PortfolioTrade:
    return PortfolioTrade(
        decided_at=at,
        executed_at=at,
        symbol=symbol,
        side=side,
        quantity=quantity,
        local_price=Decimal("100"),
        fx_rate=Decimal("1"),
        notional_krw=Decimal(quantity * 100),
        transaction_cost_krw=Decimal("0"),
        fx_cost_krw=Decimal("0"),
    )


def _simulation(
    trades: list[PortfolioTrade],
    points: list[PortfolioEquityPoint],
    final_quantity: int = 0,
) -> PortfolioSimulation:
    candidate = PortfolioCandidate(
        id="portfolio_equal_none_v1", method="equal", gate="none"
    )
    metrics = PortfolioMetrics(
        initial_equity_krw=Decimal("1000"),
        final_equity_krw=Decimal("1000"),
        total_return_pct=Decimal("0"),
        max_drawdown_pct=Decimal("0"),
        trade_count=len(trades),
        transaction_cost_krw=Decimal("0"),
        fx_cost_krw=Decimal("0"),
        turnover_pct=Decimal("0"),
    )
    return PortfolioSimulation(
        candidate=candidate,
        period_start=date(2024, 1, 1),
        period_end=date(2024, 1, 3),
        metrics=metrics,
        complete=True,
        incomplete_reasons=[],
        drawdown_latched=False,
        drawdown_latched_at=None,
        equity=points,
        trades=trades,
        weekly_targets=[],
        positions=(
            [
                PortfolioPosition(
                    symbol="AAA",
                    quantity=final_quantity,
                    currency="KRW",
                    local_close=Decimal("100"),
                    fx_rate=Decimal("1"),
                    value_krw=Decimal(final_quantity * 100),
                    weight=Decimal("0"),
                    valued_at=datetime(2024, 1, 3, tzinfo=UTC),
                    fx_observed_on=None,
                )
            ]
            if final_quantity
            else []
        ),
        contributions_krw={},
        split_cash_in_lieu_krw={},
        overlap_diagnostics={},
    )


def _source(*actions: object) -> SimpleNamespace:
    return SimpleNamespace(
        instruments=[
            SimpleNamespace(
                instruments=[SimpleNamespace(symbol="AAA")],
                corporate_actions=list(actions),
            )
        ]
    )


def test_unheld_entry_count_distinguishes_partial_sell_and_reentry() -> None:
    first = datetime(2024, 1, 2, 13, 30, tzinfo=UTC)
    simulation = _simulation(
        [
            _trade("AAA", "buy", 2, first),
            _trade("AAA", "buy", 1, first),
            _trade("AAA", "sell", 3, first),
            _trade("AAA", "buy", 4, first),
        ],
        [],
        final_quantity=4,
    )
    assert _entry_count(simulation, _source()) == 2


def test_unheld_entry_count_applies_split_before_trade() -> None:
    split = SimpleNamespace(date=date(2024, 1, 2), factor=Decimal("2"))
    at = datetime(2024, 1, 2, 13, 30, tzinfo=UTC)
    simulation = _simulation(
        [_trade("AAA", "buy", 1, at), _trade("AAA", "buy", 1, at)], [], 2
    )
    assert _entry_count(simulation, _source(split)) == 1


def test_unheld_entry_count_applies_split_on_no_trade_day_before_sell() -> None:
    split = SimpleNamespace(date=date(2024, 1, 2), factor=Decimal("2"))
    buy = datetime(2024, 1, 1, 13, 30, tzinfo=UTC)
    sell = datetime(2024, 1, 3, 13, 30, tzinfo=UTC)
    simulation = _simulation(
        [_trade("AAA", "buy", 1, buy), _trade("AAA", "sell", 2, sell)],
        [],
        final_quantity=0,
    )
    assert _entry_count(simulation, _source(split)) == 1


def test_unheld_entry_count_reconciles_split_after_last_trade() -> None:
    split = SimpleNamespace(date=date(2024, 1, 2), factor=Decimal("2"))
    buy = datetime(2024, 1, 1, 13, 30, tzinfo=UTC)
    simulation = _simulation([_trade("AAA", "buy", 1, buy)], [], final_quantity=2)
    assert _entry_count(simulation, _source(split)) == 1


def test_unheld_entry_count_fails_visible_on_position_replay_mismatch() -> None:
    at = datetime(2024, 1, 1, 13, 30, tzinfo=UTC)
    simulation = _simulation([_trade("AAA", "buy", 1, at)], [], final_quantity=2)
    with pytest.raises(ValueError, match="cannot reconcile final positions"):
        _entry_count(simulation, _source())


def test_daily_exposure_uses_last_existing_utc_point_and_zero_is_invalid() -> None:
    simulation = _simulation(
        [],
        [
            PortfolioEquityPoint(
                at=datetime(2024, 1, 1, 1, tzinfo=UTC),
                equity_krw=Decimal("100"),
                cash_krw=Decimal("100"),
                drawdown_pct=Decimal("0"),
            ),
            PortfolioEquityPoint(
                at=datetime(2024, 1, 1, 23, tzinfo=UTC),
                equity_krw=Decimal("200"),
                cash_krw=Decimal("50"),
                drawdown_pct=Decimal("0"),
            ),
        ],
    )
    assert invested_percent_by_utc_day(simulation) == {"2024-01-01": Decimal("75")}
    zero = _simulation(
        [],
        [
            PortfolioEquityPoint(
                at=datetime(2024, 1, 1, tzinfo=UTC),
                equity_krw=Decimal("0"),
                cash_krw=Decimal("0"),
                drawdown_pct=Decimal("0"),
            )
        ],
    )
    assert invested_percent_by_utc_day(zero) is None
    assert entry_metrics(zero, _source())["mean_daily_close_invested_percent"] is None


def test_source_copy_guard_rejects_any_extra_variant_change(tmp_path: Path) -> None:
    engine = Path(__file__).parents[1] / "jusik" / "research_portfolio_engine.py"
    original, variant = _copy_engine(engine, tmp_path)
    verify_unheld_entry_source(original, variant, _sha(original), _sha(variant))
    variant.write_bytes(variant.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        verify_unheld_entry_source(
            original, variant, _sha(original), _sha(variant)[:-1] + "0"
        )


def test_output_directory_refuses_resume(tmp_path: Path) -> None:
    output = tmp_path / "out"
    output.mkdir()
    (output / "existing.json").write_text("{}")
    with pytest.raises(ValueError, match="overwrite/resume"):
        _empty_output(output)


def test_full_engine_fixture_paths_cover_unheld_held_band_zero_cap_and_risk(
    tmp_path: Path,
) -> None:
    """Exercise both copied engines against the repository's portfolio fixtures."""
    from tests.test_research_portfolio import (
        _episode_source,
        _source,
        _staggered_cap_source,
    )

    engine = Path(__file__).parents[1] / "jusik" / "research_portfolio_engine.py"
    original_path, variant_path = _copy_engine(engine, tmp_path)
    original = _load_copy(original_path, "fixture_original_engine")
    variant = _load_copy(variant_path, "fixture_variant_engine")
    candidate = PortfolioCandidate(id="equal", method="equal", gate="none")
    config = PortfolioConfig(
        low_turnover_band=Decimal("0.02"),
        symbol_cap=Decimal("1"),
        gross_cap=Decimal("1"),
        leveraged_etf_cap=Decimal("1"),
    )

    regular = _source()
    control_regular = original.simulate(
        regular,
        candidate,
        regular.instruments[0].requested_start,
        regular.instruments[0].requested_end,
        config,
        "low_turnover_combined",
    )
    variant_regular = variant.simulate(
        regular,
        candidate,
        regular.instruments[0].requested_start,
        regular.instruments[0].requested_end,
        config,
        "low_turnover_combined",
    )
    assert control_regular.complete and variant_regular.complete
    assert control_regular.trades == variant_regular.trades
    assert control_regular.weekly_targets == variant_regular.weekly_targets
    assert control_regular.policy_events == variant_regular.policy_events
    assert any(event.kind == "band_skip" for event in control_regular.policy_events)
    assert entry_metrics(control_regular, regular)["actual_unheld_entry_count"] >= 1
    assert entry_metrics(variant_regular, regular)["actual_unheld_entry_count"] >= 1
    assert all(
        event.value is None or event.value < config.low_turnover_band
        for event in variant_regular.policy_events
        if event.kind == "band_skip"
    )

    risk_source = _episode_source()
    risk_result = variant.simulate(
        risk_source,
        candidate,
        risk_source.instruments[0].requested_start,
        risk_source.instruments[0].requested_end,
        config,
        "low_turnover_combined",
    )
    assert any(event.kind == "risk_exit" for event in risk_result.policy_events)
    assert any(target.target_weight == 0 for target in risk_result.weekly_targets)
    control_risk = original.simulate(
        risk_source,
        candidate,
        risk_source.instruments[0].requested_start,
        risk_source.instruments[0].requested_end,
        config,
        "low_turnover_combined",
    )
    assert control_risk.trades == risk_result.trades
    assert control_risk.weekly_targets == risk_result.weekly_targets
    assert control_risk.policy_events == risk_result.policy_events

    cap_source = _staggered_cap_source()
    cap_config = PortfolioConfig(low_turnover_band=Decimal("0.02"))
    cap_result = original.simulate(
        cap_source,
        candidate,
        cap_source.instruments[0].requested_start,
        cap_source.instruments[0].requested_end,
        cap_config,
        "low_turnover_combined",
    )
    assert any(
        event.kind == "cap_constraint_deferred" for event in cap_result.policy_events
    )
    control_cap = original.simulate(
        cap_source,
        candidate,
        cap_source.instruments[0].requested_start,
        cap_source.instruments[0].requested_end,
        cap_config,
        "low_turnover_combined",
    )
    variant_cap = variant.simulate(
        cap_source,
        candidate,
        cap_source.instruments[0].requested_start,
        cap_source.instruments[0].requested_end,
        cap_config,
        "low_turnover_combined",
    )
    assert control_cap.trades == variant_cap.trades
    assert control_cap.weekly_targets == variant_cap.weekly_targets
    assert control_cap.policy_events == variant_cap.policy_events


def test_full_engine_unheld_entry_and_exact_two_percent_band_boundary(
    tmp_path: Path,
) -> None:
    from tests.test_research_portfolio import _source

    engine = Path(__file__).parents[1] / "jusik" / "research_portfolio_engine.py"
    original_path, variant_path = _copy_engine(engine, tmp_path)
    original = _load_copy(original_path, "boundary_original_engine")
    variant = _load_copy(variant_path, "boundary_variant_engine")
    source = _source()
    candidate = PortfolioCandidate(id="equal", method="equal", gate="none")

    def run(module: object, gross_cap: str) -> PortfolioSimulation:
        config = PortfolioConfig(
            gross_cap=Decimal(gross_cap),
            symbol_cap=Decimal(gross_cap),
            leveraged_etf_cap=Decimal(gross_cap),
            low_turnover_band=Decimal("0.02"),
            fee_rate=Decimal("0"),
            slippage_rate=Decimal("0"),
            fx_spread_rate=Decimal("0"),
        )
        return module.simulate(  # type: ignore[attr-defined]
            source,
            candidate,
            source.instruments[0].requested_start,
            source.instruments[0].requested_end,
            config,
            "low_turnover_combined",
        )

    control_unheld = run(original, "0.02")
    variant_unheld = run(variant, "0.02")
    assert not control_unheld.trades
    assert sum(trade.side == "buy" for trade in variant_unheld.trades) == 2
    assert {
        event.detail
        for event in control_unheld.policy_events
        if event.kind == "band_skip"
    } == {"KRTEST", "USTEST"}
    assert not any(
        event.kind == "band_skip"
        and event.detail in {"KRTEST", "USTEST"}
        and event.value == Decimal("0.01")
        for event in variant_unheld.policy_events
    )

    control_boundary = run(original, "0.04")
    variant_boundary = run(variant, "0.04")
    assert sum(trade.side == "buy" for trade in control_boundary.trades) == 2
    assert [
        (trade.symbol, trade.side, trade.quantity) for trade in control_boundary.trades
    ] == [
        (trade.symbol, trade.side, trade.quantity) for trade in variant_boundary.trades
    ]


def _sha(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()
