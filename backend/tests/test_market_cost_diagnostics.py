from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal, localcontext
from pathlib import Path

import pytest

import jusik.market_cost_diagnostics as diagnostics
from jusik.market_cost_diagnostics import (
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
    elif scenario in {"missing", "stored mismatch"}:
        assert result.status == "invalid"
        assert result.stored_match is False
    else:
        assert result.status == "invalid"

    if scenario == "timezone":
        valid = trade()
        valid["executed_at"] = "2025-01-03T05:00:00Z"
        assert diagnose_trades([valid], assumptions=ASSUMPTIONS).status == "success"
        dst_boundary = trade(session="2025-03-10", signal_session="2025-03-07")
        dst_boundary["timestamp"] = "2025-03-10T04:00:00Z"
        assert (
            diagnose_trades([dst_boundary], assumptions=ASSUMPTIONS).status == "success"
        )
        kr_assumptions = CostAssumptions.from_values(
            market="KR",
            currency="KRW",
            fee_rate="0.00015",
            slippage_rate="0.001",
            sell_tax_rate="0.0018",
        )
        kr_boundary = trade(
            currency="KRW", session="2025-01-04", signal_session="2025-01-03"
        )
        kr_boundary["timestamp"] = "2025-01-03T15:00:00Z"
        assert (
            diagnose_trades([kr_boundary], assumptions=kr_assumptions).status
            == "success"
        )
        bad_boundary = trade()
        bad_boundary["timestamp"] = "2025-01-03T04:59:59Z"
        assert (
            diagnose_trades([bad_boundary], assumptions=ASSUMPTIONS).status == "invalid"
        )
        first = trade()
        first["timestamp"] = "2025-01-03T15:00:00Z"
        second = trade()
        second["symbol"] = "SECOND"
        second["timestamp"] = "2025-01-03T14:59:59Z"
        reverse_time = diagnose_trades([first, second], assumptions=ASSUMPTIONS)
        assert reverse_time.status == "invalid"
        assert "trade[1] timestamp chronology decreases" in reverse_time.reasons
        first["executed_at"] = "2025-01-03T15:00:01Z"
        disagreeing_fields = diagnose_trades([first], assumptions=ASSUMPTIONS)
        assert disagreeing_fields.status == "invalid"
        assert "trade[0] timestamp fields disagree" in disagreeing_fields.reasons

    if scenario == "missing chronology":
        reverse = [trade(session="2025-01-04"), trade(session="2025-01-03")]
        assert diagnose_trades(reverse, assumptions=ASSUMPTIONS).status == "invalid"
        fill_mismatch = trade()
        fill_mismatch["fill_session"] = "2025-01-04"
        assert (
            diagnose_trades([fill_mismatch], assumptions=ASSUMPTIONS).status
            == "invalid"
        )


def _literal_trade(*, side: str, currency: str) -> dict[str, object]:
    values = {
        "buy": ("100.1", "1001", "0.15015", "0"),
        "sell": ("99.9", "999", "0.14985", "1.7982"),
    }[side]
    return {
        "session": "2025-01-03",
        "signal_session": "2025-01-02",
        "fill_session": "2025-01-03",
        "symbol": "LITERAL",
        "side": side,
        "quantity": 10,
        "currency": currency,
        "market_open": "100",
        "fill_price": values[0],
        "notional": values[1],
        "fee": values[2],
        "tax": values[3],
    }


def test_literal_decimal_formula_and_roundtrip_cash_direction() -> None:
    expected = {
        "buy": ("100.1", "1001", "0.15015", "0", "1", "-1001.15015"),
        "sell": ("99.9", "999", "0.14985", "1.7982", "1", "997.05195"),
    }
    for market, currency in (("US", "USD"), ("KR", "KRW")):
        assumptions = CostAssumptions.from_values(
            market=market,
            currency=currency,
            fee_rate="0.00015",
            slippage_rate="0.001",
            sell_tax_rate="0.0018",
        )
        result = diagnose_trades(
            [
                _literal_trade(side="buy", currency=currency),
                _literal_trade(side="sell", currency=currency),
            ],
            assumptions=assumptions,
        )
        assert result.status == "success"
        assert result.totals["cash_delta"] == Decimal("-4.09820")
        assert result.totals["slippage"] == Decimal("2")
        for row in result.trades:
            values = expected[row.side]
            assert row.fill_price == Decimal(values[0])
            assert row.notional == Decimal(values[1])
            assert row.fee == Decimal(values[2])
            assert row.tax == Decimal(values[3])
            assert row.slippage_cost == Decimal(values[4])
            assert row.cash_delta == Decimal(values[5])


def _pilot_payload(
    rows: Sequence[Mapping[str, object]], equity: Sequence[Mapping[str, object]]
) -> dict[str, object]:
    return {
        "request": {
            "market": "US",
            "start_date": "2025-01-02",
            "end_date": "2025-01-03",
            "fee_rate": "0.00015",
            "slippage_rate": "0.001",
            "sell_tax_rate": "0.0018",
        },
        "result": {"market": "US", "trades": rows, "equity": equity},
    }


def _write_pilot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    payload: dict[str, object],
    *,
    count: int,
    sessions: int,
) -> Path:
    raw = json.dumps(payload, sort_keys=True).encode()
    path = tmp_path / "synthetic-pilot.json"
    path.write_bytes(raw)
    monkeypatch.setattr(
        diagnostics, "FROZEN_PILOT_SHA256", hashlib.sha256(raw).hexdigest()
    )
    monkeypatch.setattr(diagnostics, "FROZEN_PILOT_TRADE_COUNT", count)
    monkeypatch.setattr(diagnostics, "FROZEN_PILOT_SESSION_COUNT", sessions)
    return path


def test_stored_pilot_contract_uses_small_synthetic_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _write_pilot(
        tmp_path,
        monkeypatch,
        _pilot_payload(
            [trade()], [{"session": "2025-01-02"}, {"session": "2025-01-03"}]
        ),
        count=1,
        sessions=2,
    )
    result = diagnose_stored_pilot(path)
    assert result["status"] == "blocked"
    assert result["diagnostic_status"] == "success"
    assert result["stored_trade_count"] == 1
    assert result["stored_session_count"] == 2
    assert result["stored_match"] is True
    assert result["statutory_validation"] == "unavailable"


def test_stored_pilot_mismatch_is_invalid_at_top_level(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = trade()
    row["fee"] = "999"
    path = _write_pilot(
        tmp_path,
        monkeypatch,
        _pilot_payload([row], [{"session": "2025-01-02"}, {"session": "2025-01-03"}]),
        count=1,
        sessions=2,
    )
    result = diagnose_stored_pilot(path)
    assert result["status"] == "invalid"
    assert result["diagnostic_status"] == "invalid"
    assert result["stored_match"] is False
    mismatches = result["mismatches"]
    assert isinstance(mismatches, list)
    assert "trade[0] stored fee mismatch" in mismatches


def test_synthetic_pilot_rejects_equity_and_fill_boundaries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for bad_equity in (
        [{"session": "2025-01-03"}, {"session": "2025-01-02"}],
        [{"session": "2025-01-02"}, {"session": "2025-01-02"}],
    ):
        path = _write_pilot(
            tmp_path,
            monkeypatch,
            _pilot_payload([trade()], bad_equity),
            count=1,
            sessions=2,
        )
        with pytest.raises(ValueError, match="equity"):
            diagnose_stored_pilot(path)
    row = trade()
    row["fill_session"] = "2025-01-04"
    path = _write_pilot(
        tmp_path,
        monkeypatch,
        _pilot_payload([row], [{"session": "2025-01-02"}, {"session": "2025-01-03"}]),
        count=1,
        sessions=2,
    )
    with pytest.raises(ValueError, match="fill session"):
        diagnose_stored_pilot(path)


def test_ambient_decimal_precision_does_not_change_results() -> None:
    with localcontext() as context:
        context.prec = 6
        result = diagnose_trades(
            [_literal_trade(side="sell", currency="USD")], assumptions=ASSUMPTIONS
        )
    row = result.trades[0]
    assert row.fill_price == Decimal("99.9")
    assert row.notional == Decimal("999")
    assert row.fee == Decimal("0.14985")
    assert row.tax == Decimal("1.7982")
    assert row.cash_delta == Decimal("997.05195")


def test_cli_preserves_pilot_for_aliases_and_writes_distinct_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pilot = _write_pilot(
        tmp_path,
        monkeypatch,
        _pilot_payload(
            [trade()], [{"session": "2025-01-02"}, {"session": "2025-01-03"}]
        ),
        count=1,
        sessions=2,
    )
    source_bytes = pilot.read_bytes()

    assert diagnostics.main(["--pilot", str(pilot), "--output", str(pilot)]) == 2
    assert pilot.read_bytes() == source_bytes

    symlink = tmp_path / "pilot-symlink.json"
    symlink.symlink_to(pilot)
    assert diagnostics.main(["--pilot", str(pilot), "--output", str(symlink)]) == 2
    assert pilot.read_bytes() == source_bytes

    hardlink = tmp_path / "pilot-hardlink.json"
    os.link(pilot, hardlink)
    assert diagnostics.main(["--pilot", str(pilot), "--output", str(hardlink)]) == 2
    assert pilot.read_bytes() == source_bytes

    output = tmp_path / "diagnostic.json"
    assert diagnostics.main(["--pilot", str(pilot), "--output", str(output)]) == 0
    assert json.loads(output.read_text())["status"] == "blocked"
    assert pilot.read_bytes() == source_bytes
