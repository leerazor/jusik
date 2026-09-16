"""Independent Decimal diagnostics for the stored market-cost pilot.

The module deliberately uses only the standard library.  It reads saved trade
rows and recomputes execution costs without importing a strategy, shared model,
portfolio engine, broker, database, or service.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path
from typing import Literal

PRECISION = 28
MAX_ARTIFACT_BYTES = 20 * 1024 * 1024
MAX_SESSIONS = 300
MAX_TRADES = 200
FROZEN_PILOT_SHA256 = "cc9150f8b77a27ffd6b001449c0475933ff744a37011801923f87cbdc5558275"
FROZEN_PILOT_TRADE_COUNT = 106
FROZEN_PILOT_SESSION_COUNT = 252

Market = Literal["KR", "US"]
Side = Literal["buy", "sell"]
DiagnosticStatus = Literal["success", "blocked", "invalid"]


def _decimal(value: object, label: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise ValueError(f"{label} must be a finite decimal")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{label} must be a finite decimal") from exc
    if not result.is_finite():
        raise ValueError(f"{label} must be a finite decimal")
    return result


def _date(value: object, label: str) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        raise ValueError(f"{label} must be an ISO date")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{label} must be an ISO date") from exc


def _aware_timestamp(value: object, label: str) -> None:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be an aware ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{label} must be an aware ISO timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{label} must be an aware ISO timestamp")


@dataclass(frozen=True)
class CostAssumptions:
    market: str
    currency: str
    fee_rate: Decimal
    slippage_rate: Decimal
    sell_tax_rate: Decimal

    @classmethod
    def from_values(
        cls,
        *,
        market: object,
        currency: object,
        fee_rate: object,
        slippage_rate: object,
        sell_tax_rate: object,
    ) -> CostAssumptions:
        rates = {
            "fee_rate": _decimal(fee_rate, "fee_rate"),
            "slippage_rate": _decimal(slippage_rate, "slippage_rate"),
            "sell_tax_rate": _decimal(sell_tax_rate, "sell_tax_rate"),
        }
        if not isinstance(market, str) or market not in {"KR", "US"}:
            raise ValueError("market must be KR or US")
        if not isinstance(currency, str):
            raise ValueError("currency must be KRW or USD")
        expected_currency = "KRW" if market == "KR" else "USD"
        if currency != expected_currency:
            raise ValueError("market and currency do not match")
        for name, rate in rates.items():
            if rate < 0 or rate > 1:
                raise ValueError(f"{name} must be between zero and one")
        if rates["slippage_rate"] >= 1:
            raise ValueError("slippage_rate must be below one")
        return cls(market, currency, **rates)


@dataclass(frozen=True)
class TradeCost:
    index: int
    session: date
    symbol: str
    side: Side
    quantity: int
    market_open: Decimal
    fill_price: Decimal
    notional: Decimal
    fee: Decimal
    tax: Decimal
    slippage_cost: Decimal
    cash_delta: Decimal
    stored_match: bool


@dataclass(frozen=True)
class MarketCostDiagnostic:
    status: DiagnosticStatus
    assumptions: CostAssumptions
    trades: tuple[TradeCost, ...]
    trade_count: int
    session_count: int | None
    totals: dict[str, Decimal]
    stored_match: bool
    mismatches: tuple[str, ...]
    reasons: tuple[str, ...]
    unavailable: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        def encode(value: object) -> object:
            if isinstance(value, Decimal):
                return str(value)
            if isinstance(value, date):
                return value.isoformat()
            if isinstance(value, tuple):
                return [encode(item) for item in value]
            if isinstance(value, dict):
                return {str(key): encode(item) for key, item in value.items()}
            return value

        return encode(asdict(self))  # type: ignore[return-value]


def _stored_decimal(
    row: Mapping[str, object], key: str, expected: Decimal, index: int
) -> tuple[bool, str | None]:
    if key not in row:
        return False, f"trade[{index}] missing stored {key}"
    try:
        actual = _decimal(row[key], f"trade[{index}].{key}")
    except ValueError as exc:
        return False, str(exc)
    if actual != expected:
        return False, f"trade[{index}] stored {key} mismatch"
    return True, None


def diagnose_trades(
    rows: Sequence[Mapping[str, object]],
    *,
    assumptions: CostAssumptions,
    start_date: date | None = None,
    end_date: date | None = None,
    session_count: int | None = None,
) -> MarketCostDiagnostic:
    """Recompute costs for saved rows using an isolated Decimal context."""

    reasons: list[str] = []
    mismatches: list[str] = []
    parsed: list[tuple[int, date, str, Side, int, Decimal, Decimal, bool]] = []
    seen: set[tuple[date, str, str, int]] = set()
    unsupported = False
    with localcontext() as context:
        context.prec = PRECISION
        for index, row in enumerate(rows):
            try:
                session = _date(row.get("session"), f"trade[{index}].session")
                if start_date is not None and session < start_date:
                    raise ValueError(f"trade[{index}] is before request start")
                if end_date is not None and session > end_date:
                    raise ValueError(f"trade[{index}] is after request end")
                symbol = row.get("symbol")
                if not isinstance(symbol, str) or not symbol:
                    raise ValueError(f"trade[{index}].symbol must be non-empty")
                side_value = row.get("side")
                if side_value not in {"buy", "sell"}:
                    raise ValueError(f"trade[{index}].side must be buy or sell")
                side: Side = "buy" if side_value == "buy" else "sell"
                quantity_value = row.get("quantity")
                if (
                    isinstance(quantity_value, bool)
                    or not isinstance(quantity_value, int)
                    or quantity_value <= 0
                ):
                    raise ValueError(
                        f"trade[{index}].quantity must be positive integer"
                    )
                quantity = quantity_value
                market_open = _decimal(
                    row.get("market_open"), f"trade[{index}].market_open"
                )
                if market_open <= 0:
                    raise ValueError(f"trade[{index}].market_open must be positive")
                row_currency = row.get("currency")
                if row_currency != assumptions.currency:
                    raise ValueError(f"trade[{index}] currency does not match market")
                signal = row.get("signal_session")
                if (
                    signal is not None
                    and _date(signal, f"trade[{index}].signal_session") >= session
                ):
                    raise ValueError(f"trade[{index}] signal must precede fill")
                fill_session = row.get("fill_session")
                if (
                    fill_session is not None
                    and _date(fill_session, f"trade[{index}].fill_session") != session
                ):
                    raise ValueError(f"trade[{index}] session/fill chronology mismatch")
                row_status = row.get("status")
                if row_status in {"partial", "cancelled", "canceled", "rejected"}:
                    unsupported = True
                    reasons.append(
                        f"trade[{index}] {row_status} status is unavailable "
                        "in stored data"
                    )
                    continue
                if row_status not in {None, "filled", "executed"}:
                    raise ValueError(f"trade[{index}] has unsupported status")
                for timestamp_key in ("executed_at", "timestamp"):
                    if timestamp_key in row and row[timestamp_key] is not None:
                        _aware_timestamp(
                            row[timestamp_key], f"trade[{index}].{timestamp_key}"
                        )
                duplicate_key = (session, symbol, side, quantity)
                if duplicate_key in seen:
                    raise ValueError(f"trade[{index}] duplicate trade")
                seen.add(duplicate_key)
                fill_price = market_open * (
                    1 + assumptions.slippage_rate
                    if side == "buy"
                    else 1 - assumptions.slippage_rate
                )
                notional = fill_price * quantity
                fee = notional * assumptions.fee_rate
                tax = (
                    notional * assumptions.sell_tax_rate
                    if side == "sell"
                    else Decimal(0)
                )
                slippage_cost = (
                    fill_price - market_open
                    if side == "buy"
                    else market_open - fill_price
                ) * quantity
                cash_delta = (
                    -(notional + fee) if side == "buy" else notional - fee - tax
                )
                row_match = True
                for key, expected in (
                    ("fill_price", fill_price),
                    ("notional", notional),
                    ("fee", fee),
                    ("tax", tax),
                ):
                    matches, mismatch = _stored_decimal(row, key, expected, index)
                    row_match = row_match and matches
                    if mismatch is not None:
                        mismatches.append(mismatch)
                parsed.append(
                    (
                        index,
                        session,
                        symbol,
                        side,
                        quantity,
                        market_open,
                        fill_price,
                        row_match,
                    )
                )
            except ValueError as exc:
                reasons.append(str(exc))

        calculated: list[TradeCost] = []
        totals = {
            "buy_fee": Decimal(0),
            "sell_fee": Decimal(0),
            "sell_tax": Decimal(0),
            "slippage": Decimal(0),
            "cash_delta": Decimal(0),
        }
        for (
            index,
            session,
            symbol,
            side,
            quantity,
            market_open,
            fill_price,
            match,
        ) in parsed:
            notional = fill_price * quantity
            fee = notional * assumptions.fee_rate
            tax = notional * assumptions.sell_tax_rate if side == "sell" else Decimal(0)
            slippage_cost = (
                fill_price - market_open if side == "buy" else market_open - fill_price
            ) * quantity
            cash_delta = -(notional + fee) if side == "buy" else notional - fee - tax
            calculated.append(
                TradeCost(
                    index,
                    session,
                    symbol,
                    side,
                    quantity,
                    market_open,
                    fill_price,
                    notional,
                    fee,
                    tax,
                    slippage_cost,
                    cash_delta,
                    match,
                )
            )
            totals["buy_fee" if side == "buy" else "sell_fee"] += fee
            totals["sell_tax"] += tax
            totals["slippage"] += slippage_cost
            totals["cash_delta"] += cash_delta
    stored_match = not mismatches and not reasons and len(calculated) == len(rows)
    if mismatches:
        reasons.append(
            "stored execution values do not match independent Decimal results"
        )
    malformed_stored = any(
        "missing stored" in mismatch or "must be a finite decimal" in mismatch
        for mismatch in mismatches
    )
    structural_reasons = tuple(
        reason
        for reason in reasons
        if reason != "stored execution values do not match independent Decimal results"
    )
    status: DiagnosticStatus
    if unsupported:
        status = "blocked"
    elif structural_reasons or malformed_stored:
        status = "invalid"
    else:
        status = "success"
    return MarketCostDiagnostic(
        status,
        assumptions,
        tuple(calculated),
        len(rows),
        session_count,
        totals,
        stored_match,
        tuple(mismatches),
        tuple(reasons),
        (
            "exchange holiday calendar validation is unavailable; "
            "supplied dates are explicit sessions",
            "stored fill timestamp and order/partial-fill identity are unavailable",
            "statutory tax types, jurisdiction, effective period, and "
            "official rates are unavailable",
        ),
    )


def _read_json(path: Path) -> tuple[bytes, object, str]:
    size = path.stat().st_size
    if size > MAX_ARTIFACT_BYTES:
        raise ValueError("input artifact exceeds 20 MiB cap")
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("input is not valid JSON") from exc
    return raw, payload, digest


def diagnose_stored_pilot(path: Path) -> dict[str, object]:
    """Diagnose exactly the frozen US pilot run, without executing research."""

    _, payload, digest = _read_json(path)
    if digest != FROZEN_PILOT_SHA256:
        raise ValueError("stored pilot SHA-256 does not match frozen manifest")
    if not isinstance(payload, dict):
        raise ValueError("stored pilot must be a JSON object")
    request = payload.get("request")
    result = payload.get("result")
    if not isinstance(request, dict) or not isinstance(result, dict):
        raise ValueError("stored pilot request and result are required")
    if request.get("market") != "US" or result.get("market") != "US":
        raise ValueError("stored pilot must be the frozen US run")
    start = _date(request.get("start_date"), "request.start_date")
    end = _date(request.get("end_date"), "request.end_date")
    if start > end:
        raise ValueError("request start_date must not be after end_date")
    assumptions = CostAssumptions.from_values(
        market="US",
        currency="USD",
        fee_rate=request.get("fee_rate"),
        slippage_rate=request.get("slippage_rate"),
        sell_tax_rate=request.get("sell_tax_rate"),
    )
    trades = result.get("trades")
    equity = result.get("equity")
    if not isinstance(trades, list) or not isinstance(equity, list):
        raise ValueError("stored pilot trades and equity arrays are required")
    if len(trades) > MAX_TRADES or len(equity) > MAX_SESSIONS:
        raise ValueError("stored pilot exceeds diagnostic bounds")
    rows = [row for row in trades if isinstance(row, dict)]
    if len(rows) != len(trades):
        raise ValueError("stored pilot trade rows must be objects")
    sessions: list[date] = []
    for index, row in enumerate(equity):
        if not isinstance(row, dict):
            raise ValueError(f"equity[{index}] must be an object")
        sessions.append(_date(row.get("session"), f"equity[{index}].session"))
    if len(set(sessions)) != len(sessions):
        raise ValueError("stored pilot equity has duplicate sessions")
    if len(trades) != FROZEN_PILOT_TRADE_COUNT:
        raise ValueError("stored pilot trade count does not match frozen run")
    if len(equity) != FROZEN_PILOT_SESSION_COUNT:
        raise ValueError("stored pilot session count does not match frozen run")
    diagnostic = diagnose_trades(
        rows,
        assumptions=assumptions,
        start_date=start,
        end_date=end,
        session_count=len(equity),
    )
    output = diagnostic.as_dict()
    output.update(
        {
            "status": "blocked",
            "diagnostic_status": diagnostic.status,
            "input_sha256": digest,
            "source": str(path),
            "market": "US",
            "currency": "USD",
            "stored_trade_count": len(trades),
            "stored_session_count": len(equity),
            "economic_evaluation": "not-evaluated",
            "statutory_validation": "unavailable",
        }
    )
    return output


def _write_output(path: Path, payload: Mapping[str, object]) -> None:
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode()
    if len(encoded) > MAX_ARTIFACT_BYTES:
        raise ValueError("output artifact exceeds 20 MiB cap")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded + b"\n")


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(
        description="Bounded independent Decimal market-cost diagnostic"
    )
    command.add_argument("--pilot", type=Path, required=True)
    command.add_argument("--output", type=Path, required=True)
    return command


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        result = diagnose_stored_pilot(args.pilot)
        _write_output(args.output, result)
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "invalid", "reason": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
