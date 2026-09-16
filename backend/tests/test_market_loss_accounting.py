import hashlib
import json
from datetime import date
from decimal import ROUND_DOWN, Context, Decimal, getcontext, localcontext
from pathlib import Path
from typing import cast

import pytest

from jusik.market_history_models import (
    MarketReadiness,
    MarketResearchRequest,
    MarketResearchResult,
    ResearchEquityPoint,
    ResearchTrade,
)
from jusik.market_loss_accounting import (
    LossTrade,
    PositionLot,
    account_result,
    account_trades,
    diagnose_saved_pilot,
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
    currency: str = "KRW",
) -> LossTrade:
    return LossTrade(
        symbol="AAA",
        side=side,  # type: ignore[arg-type]
        quantity=Decimal(quantity),
        market_open=Decimal(open_price),
        fill_price=Decimal(fill_price),
        fee=Decimal(fee),
        tax=Decimal(tax),
        currency=currency,  # type: ignore[arg-type]
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
    serialised = report.as_dict()
    fees_payload = cast(dict[str, object], serialised["fees"])
    cash_payload = cast(dict[str, object], serialised["cash_balance"])
    assert fees_payload["currency"] == "KRW"
    assert fees_payload["unit"] == "currency"
    assert cash_payload["currency"] == "KRW"


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


def test_missing_final_mark_blocks_net_pnl_even_with_complete_history() -> None:
    report = account_trades(
        [_trade("buy", "1", "100", "100")],
        final_marks={},
        complete_history=True,
        dividends={},
        dividend_evidence_complete=True,
    )
    assert report.status == "blocked"
    assert not report.raw_unrealized_pnl.available
    assert not report.raw_net_pnl.available


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
    assert decomposition.native_currency is None
    assert decomposition.local_currency == "KRW"
    assert decomposition.rate_unit == "KRW_per_USD"


def test_decimal_operations_ignore_caller_precision_rounding_and_traps() -> None:
    trade = _trade("buy", "3", "100", "100.123456789")
    with localcontext(Context(prec=4, rounding=ROUND_DOWN, traps=[])):
        assert slippage_amount(trade) == Decimal("0.370370367")
        assert fx_decomposition(
            Decimal("100.123456789"),
            Decimal("100.123456790"),
            Decimal("1300.123456789"),
            Decimal("1300.123456790"),
        ).total_change == Decimal("0.000001400246913579")
    assert getcontext().prec == 28


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
    with pytest.raises(ValueError, match="final marks"):
        account_trades([], final_marks={"AAA": Decimal("0")})
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


def test_currency_side_and_iso_session_validation_is_explicit() -> None:
    with pytest.raises(ValueError, match="side"):
        account_trades([_trade("hold", "1", "100", "100")], final_marks={})
    with pytest.raises(ValueError, match="ISO date"):
        account_trades(
            [_trade("buy", "1", "100", "100", session="2026/01/01")],
            final_marks={},
        )
    with pytest.raises(ValueError, match="mixed"):
        account_trades(
            [
                _trade("buy", "1", "100", "100", currency="KRW"),
                _trade("buy", "1", "100", "100", currency="USD"),
            ],
            final_marks={},
        )


def test_buy_tax_and_complete_dividend_are_in_cash() -> None:
    report = account_trades(
        [_trade("buy", "1", "100", "100", tax="2")],
        final_marks={"AAA": Decimal("100")},
        complete_history=True,
        dividends={"AAA": Decimal("3")},
        dividend_evidence_complete=True,
        initial_cash=Decimal("1000"),
    )
    assert report.cash_balance.value == Decimal("901")


def test_cash_is_unavailable_when_dividend_evidence_is_incomplete() -> None:
    report = account_trades(
        [_trade("buy", "1", "100", "100")],
        final_marks={"AAA": Decimal("100")},
        initial_cash=Decimal("1000"),
        dividends={"AAA": Decimal("3")},
    )
    assert not report.cash_balance.available
    assert report.cash_balance.diagnostic_value == Decimal("900")


def test_initial_position_with_iso_session_is_supported() -> None:
    report = account_trades(
        [_trade("sell", "1", "110", "108.9", session="2026-01-02")],
        final_marks={},
        initial_positions=[PositionLot("AAA", Decimal("1"), Decimal("100"))],
        complete_history=True,
        dividends={},
        dividend_evidence_complete=True,
    )
    assert report.raw_realized_pnl.value == Decimal("10")
    assert report.raw_unrealized_pnl.value == Decimal("0")


def test_duplicate_key_includes_costs_and_currency() -> None:
    report = account_trades(
        [
            _trade("buy", "1", "100", "100", fee="1"),
            _trade("buy", "1", "100", "100", fee="2"),
        ],
        final_marks={"AAA": Decimal("100")},
    )
    assert report.trade_count == 2


def test_empty_input_does_not_infer_currency_and_saved_units_are_structured() -> None:
    empty = account_trades([], final_marks={})
    assert empty.fees.currency is None
    assert empty.fees.unit == "currency"
    saved = account_result(_saved_result((_equity(date(2026, 1, 1)),)))
    assert saved.fees.currency == "USD"
    assert saved.slippage.currency == "USD"
    assert saved.fx.currency == "KRW"
    assert saved.cash_balance.currency == "KRW"
    fx_payload = cast(dict[str, object], saved.as_dict()["fx"])
    assert fx_payload["unit"] == "currency"


def test_cli_rejects_order_or_timestamp_metadata(tmp_path: Path) -> None:
    path = tmp_path / "unsupported.json"
    payload = {"result": {}, "order_status": "rejected"}
    body = json.dumps(payload).encode()
    path.write_bytes(body)
    with pytest.raises(ValueError, match="unsupported order or timestamp"):
        diagnose_saved_pilot(path, expected_sha256=hashlib.sha256(body).hexdigest())


def _equity(session: date) -> ResearchEquityPoint:
    return ResearchEquityPoint(
        session=session,
        cash_krw=Decimal("1000"),
        cash_native=Decimal("1"),
        invested_krw=Decimal("0"),
        nav_krw=Decimal("1000"),
        fx_krw_per_usd=Decimal("1000"),
        drawdown_pct=Decimal("0"),
    )


def _saved_result(
    equity: tuple[ResearchEquityPoint, ...],
    trades: tuple[ResearchTrade, ...] = (),
) -> MarketResearchResult:
    return MarketResearchResult.model_construct(
        market="US",
        request=cast(MarketResearchRequest, object()),
        readiness=cast(MarketReadiness, object()),
        status="approximate",
        completeness="approximate",
        equity=equity,
        trades=trades,
        research_grade="strict",
    )


def test_saved_equity_is_unique_chronological_and_contains_fill_sessions() -> None:
    with pytest.raises(ValueError, match="unique and chronological"):
        account_result(
            _saved_result((_equity(date(2026, 1, 2)), _equity(date(2026, 1, 2))))
        )
    trade = ResearchTrade(
        session=date(2026, 1, 1),
        signal_session=date(2026, 1, 1),
        fill_session=date(2026, 1, 3),
        symbol="AAA",
        side="buy",
        quantity=1,
        currency="USD",
        market_open=Decimal("100"),
        fill_price=Decimal("100"),
        notional=Decimal("100"),
        fee=Decimal("0"),
        tax=Decimal("0"),
        rationale="fixture",
    )
    with pytest.raises(ValueError, match="absent from equity"):
        account_result(_saved_result((_equity(date(2026, 1, 1)),), (trade,)))
