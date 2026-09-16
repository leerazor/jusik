from decimal import Decimal

import pytest

from jusik.market_loss_accounting import (
    LossTrade,
    PositionLot,
    account_trades,
    fx_decomposition,
    slippage_amount,
)


def _trade(
    side: str,
    quantity: str,
    open_price: str,
    fill_price: str,
    fee: str = "0",
    tax: str = "0",
    session: str = "2026-01-01",
) -> LossTrade:
    return LossTrade(
        symbol="AAA",
        side=side,  # type: ignore[arg-type]
        quantity=Decimal(quantity),
        market_open=Decimal(open_price),
        fill_price=Decimal(fill_price),
        fee=Decimal(fee),
        tax=Decimal(tax),
        session=session,
    )


def test_manual_decimal_accounting_matches_registered_example() -> None:
    report = account_trades(
        [
            _trade("buy", "2", "100", "101", "2.02"),
            _trade("sell", "1", "110", "108.9", "1.089", "0.19602", "2026-01-02"),
        ],
        final_marks={"AAA": Decimal("120")},
        complete_history=True,
        dividends={"AAA": Decimal("0")},
        dividend_evidence_complete=True,
        initial_cash=Decimal("1000"),
    )
    assert report.status == "complete"
    assert report.raw_realized_pnl.value == Decimal("10")
    assert report.raw_unrealized_pnl.value == Decimal("20")
    assert report.fill_realized_pnl.value == Decimal("7.9")
    assert report.fill_unrealized_pnl.value == Decimal("19")
    assert report.slippage.value == Decimal("3.1")
    assert report.fees.value == Decimal("3.109")
    assert report.taxes.value == Decimal("0.19602")
    assert report.raw_net_pnl.value == Decimal("23.59498")
    assert report.fill_net_pnl.value == Decimal("23.59498")
    assert report.cash_balance.value == Decimal("903.59498")


def test_slippage_is_side_aware_and_fill_net_does_not_charge_twice() -> None:
    buy = _trade("buy", "2", "100", "101", "2.02")
    sell = _trade("sell", "1", "110", "108.9", "1.089", "0.19602", "2026-01-02")
    assert slippage_amount(buy) == Decimal("2")
    assert slippage_amount(sell) == Decimal("1.1")
    report = account_trades(
        [buy, sell],
        final_marks={"AAA": Decimal("120")},
        complete_history=True,
        dividends={"AAA": Decimal("0")},
        dividend_evidence_complete=True,
    )
    assert report.raw_net_pnl.value == report.fill_net_pnl.value


@pytest.mark.parametrize(
    ("dividends", "complete", "available", "value"),
    [
        (None, False, False, None),
        ({"AAA": Decimal("0")}, True, True, Decimal("0")),
        ({"AAA": Decimal("1.25")}, True, True, Decimal("1.25")),
        ({"AAA": Decimal("0")}, False, False, None),
    ],
)
def test_dividend_missing_zero_and_nonzero_are_distinct(
    dividends: dict[str, Decimal] | None,
    complete: bool,
    available: bool,
    value: Decimal | None,
) -> None:
    report = account_trades(
        [_trade("buy", "1", "100", "100")],
        final_marks={"AAA": Decimal("100")},
        complete_history=True,
        dividends=dividends,
        dividend_evidence_complete=complete,
    )
    assert report.dividends.available is available
    assert report.dividends.value == value


def test_fx_identity_assigns_cross_term_to_fx() -> None:
    decomposition = fx_decomposition(
        Decimal("100"), Decimal("110"), Decimal("1300"), Decimal("1320")
    )
    assert decomposition.local_effect == Decimal("13000")
    assert decomposition.fx_effect == Decimal("2000")
    assert decomposition.cross_effect == Decimal("200")
    assert decomposition.total_change == Decimal("15200")


def test_unavailable_history_keeps_diagnostic_fifo_value() -> None:
    report = account_trades(
        [_trade("buy", "1", "100", "101")],
        final_marks={"AAA": Decimal("120")},
        initial_cash=Decimal("1000"),
    )
    assert report.status == "blocked"
    assert not report.raw_realized_pnl.available
    assert report.raw_realized_pnl.diagnostic_value == Decimal("0")
    assert "complete trade history" in report.raw_realized_pnl.evidence[0]


def test_partial_fill_fifo_and_cancelled_or_rejected_orders_are_not_invented() -> None:
    report = account_trades(
        [
            _trade("buy", "2", "100", "100.5"),
            _trade("sell", "1", "110", "109.5", session="2026-01-02"),
        ],
        final_marks={"AAA": Decimal("120")},
        complete_history=True,
        dividends={},
        dividend_evidence_complete=True,
    )
    assert report.raw_realized_pnl.value == Decimal("10")
    assert report.raw_unrealized_pnl.value == Decimal("20")
    with pytest.raises(ValueError, match="sell exceeds"):
        account_trades(
            [_trade("sell", "1", "100", "100")],
            final_marks={},
            complete_history=True,
            dividends={},
            dividend_evidence_complete=True,
        )


def test_zero_negative_missing_duplicate_and_rounding_boundaries() -> None:
    with pytest.raises(ValueError, match="quantity"):
        account_trades(
            [_trade("buy", "0", "100", "100")],
            final_marks={},
        )
    with pytest.raises(ValueError, match="prices"):
        account_trades(
            [_trade("buy", "1", "-1", "100")],
            final_marks={},
        )
    with pytest.raises(ValueError, match="costs"):
        account_trades(
            [_trade("buy", "1", "100", "100", fee="-1")],
            final_marks={},
        )
    with pytest.raises(ValueError, match="initial cash"):
        account_trades([], final_marks={}, initial_cash=Decimal("0"))
    with pytest.raises(ValueError, match="chronological"):
        account_trades(
            [
                _trade("buy", "1", "100", "100", session="2026-01-02"),
                _trade("buy", "1", "100", "100", session="2026-01-01"),
            ],
            final_marks={"AAA": Decimal("100")},
        )
    with pytest.raises(ValueError, match="duplicate trade"):
        account_trades(
            [_trade("buy", "1", "100", "100"), _trade("buy", "1", "100", "100")],
            final_marks={"AAA": Decimal("100")},
        )
    missing = account_trades(
        [_trade("buy", "1", "100", "100")],
        final_marks={},
        complete_history=True,
        dividends={},
        dividend_evidence_complete=True,
    )
    assert not missing.raw_unrealized_pnl.available
    assert missing.raw_unrealized_pnl.value is None


def test_initial_position_and_timezone_free_session_are_supported() -> None:
    report = account_trades(
        [_trade("sell", "1", "110", "108.9")],
        final_marks={},
        initial_positions=[PositionLot("AAA", Decimal("1"), Decimal("100"))],
        complete_history=True,
        dividends={},
        dividend_evidence_complete=True,
    )
    assert report.raw_realized_pnl.value == Decimal("10")
    assert report.raw_unrealized_pnl.value == Decimal("0")
