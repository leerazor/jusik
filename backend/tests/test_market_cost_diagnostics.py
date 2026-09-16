from __future__ import annotations

from datetime import date
from decimal import Decimal, localcontext
from pathlib import Path

import pytest

from jusik.market_cost_diagnostics import (
    FROZEN_PILOT_SHA256,
    CostAssumptions,
    MarketCostDiagnostic,
    diagnose_stored_pilot,
    diagnose_trades,
)

ASSUMPTIONS = CostAssumptions.from_values(
    market="US",
    currency="USD",
    fee_rate="0.00015",
    slippage_rate="0.001",
    sell_tax_rate="0.0018",
)
START = date(2025, 1, 2)
END = date(2025, 1, 10)


def trade(
    *,
    side: str = "buy",
    market: str = "US",
    currency: str = "USD",
    session: str = "2025-01-03",
    signal_session: str | None = "2025-01-02",
    market_open: str = "100",
    quantity: int = 10,
) -> dict[str, object]:
    fill = Decimal(market_open) * (
        Decimal("1.001") if side == "buy" else Decimal("0.999")
    )
    notional = fill * quantity
    fee = notional * Decimal("0.00015")
    tax = notional * Decimal("0.0018") if side == "sell" else Decimal(0)
    return {
        "session": session,
        "signal_session": signal_session,
        "fill_session": session,
        "symbol": "TEST",
        "side": side,
        "quantity": quantity,
        "currency": currency,
        "market_open": market_open,
        "fill_price": str(fill),
        "notional": str(notional),
        "fee": str(fee),
        "tax": str(tax),
    }


SCENARIO_NAMES = (
    "KR buy",
    "KR sell",
    "US buy",
    "US sell",
    "zero",
    "negative",
    "missing",
    "duplicate",
    "rounding",
    "holiday",
    "timezone",
    "partial",
    "cancelled",
    "rejected",
    "missing chronology",
    "stored mismatch",
)


@pytest.mark.parametrize("scenario", SCENARIO_NAMES, ids=SCENARIO_NAMES)
def test_fixed_scenarios(scenario: str) -> None:
    assumptions = ASSUMPTIONS
    rows: list[dict[str, object]] = [trade()]
    if scenario == "KR buy":
        assumptions = CostAssumptions.from_values(
            market="KR",
            currency="KRW",
            fee_rate="0.00015",
            slippage_rate="0.001",
            sell_tax_rate="0.0018",
        )
        rows = [trade(currency="KRW")]
    elif scenario == "KR sell":
        assumptions = CostAssumptions.from_values(
            market="KR",
            currency="KRW",
            fee_rate="0.00015",
            slippage_rate="0.001",
            sell_tax_rate="0.0018",
        )
        rows = [trade(side="sell", currency="KRW")]
    elif scenario == "US sell":
        rows = [trade(side="sell")]
    elif scenario in {"zero", "negative"}:
        rows = [trade(quantity=0 if scenario == "zero" else -1)]
    elif scenario == "missing":
        rows = [trade()]
        del rows[0]["fee"]
    elif scenario == "duplicate":
        rows = [trade(), trade()]
    elif scenario == "rounding":
        rows = [trade(market_open="0.000000000000000001", quantity=1)]
    elif scenario == "holiday":
        rows = [trade(session="2025-01-04")]
    elif scenario == "timezone":
        rows = [trade()]
        rows[0]["executed_at"] = "2025-01-03T09:30:00"
    elif scenario in {"partial", "cancelled", "rejected"}:
        rows = [trade()]
        rows[0]["status"] = scenario
    elif scenario == "missing chronology":
        rows = [trade(signal_session="2025-01-03")]
    elif scenario == "stored mismatch":
        rows = [trade()]
        rows[0]["fee"] = "999"
    result = diagnose_trades(
        rows, assumptions=assumptions, start_date=START, end_date=END
    )
    assert isinstance(result, MarketCostDiagnostic)
    if scenario in {"KR buy", "KR sell", "US buy", "US sell", "rounding", "holiday"}:
        assert result.status == "success"
    elif scenario in {"partial", "cancelled", "rejected"}:
        assert result.status == "blocked"
        assert result.unavailable[1].startswith("stored fill timestamp")
    elif scenario == "stored mismatch":
        assert result.status == "success"
        assert result.stored_match is False
        assert result.mismatches == ("trade[0] stored fee mismatch",)
    else:
        assert result.status == "invalid"


def test_literal_decimal_formula_and_cash_direction() -> None:
    with localcontext() as context:
        context.prec = 6
        result = diagnose_trades([trade(side="sell")], assumptions=ASSUMPTIONS)
    row = result.trades[0]
    assert row.fill_price == Decimal("99.900")
    assert row.notional == Decimal("999.000")
    assert row.fee == Decimal("0.14985000")
    assert row.tax == Decimal("1.7982000")
    assert row.cash_delta == Decimal("997.05195000")


def test_assumptions_reject_malformed_nonfinite_and_currency() -> None:
    for key, value in {
        "fee_rate": "NaN",
        "slippage_rate": "Infinity",
        "sell_tax_rate": "bad",
    }.items():
        values = {"fee_rate": "0", "slippage_rate": "0", "sell_tax_rate": "0"}
        values[key] = value
        with pytest.raises(ValueError):
            CostAssumptions.from_values(market="US", currency="USD", **values)
    with pytest.raises(ValueError):
        CostAssumptions.from_values(
            market="US",
            currency="KRW",
            fee_rate="0",
            slippage_rate="0",
            sell_tax_rate="0",
        )


def test_stored_pilot_hash_and_counts() -> None:
    path = Path(
        "/home/kwl/.local/share/jusik/portfolio-audit/20260915-market-data-live-contract-fixes/us-web-pilot-run.json"
    )
    result = diagnose_stored_pilot(path)
    assert result["status"] == "blocked"
    assert result["input_sha256"] == FROZEN_PILOT_SHA256
    assert result["stored_trade_count"] == 106
    assert result["stored_session_count"] == 252
    assert result["stored_match"] is True
    assert result["statutory_validation"] == "unavailable"
