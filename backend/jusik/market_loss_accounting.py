"""Independent Decimal loss-accounting diagnostics for saved market results.

The module consumes already saved ``MarketResearchResult`` JSON or explicit
trade observations.  It never imports a strategy, collector, simulation,
replay, broker, or service module.  FIFO values are labelled diagnostic until
the caller proves complete history, initial positions, and corporate actions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict, deque
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import date
from decimal import ROUND_HALF_EVEN, Context, Decimal, InvalidOperation, localcontext
from pathlib import Path
from typing import Literal

from jusik.market_history_models import MarketResearchResult, ResearchTrade

PRECISION = 50
MAX_SESSIONS = 300
MAX_TRADES = 200
DECIMAL_CONTEXT = Context(prec=PRECISION, rounding=ROUND_HALF_EVEN)

Availability = Literal["available", "unavailable"]
ReportStatus = Literal["complete", "blocked", "invalid"]
Currency = Literal["KRW", "USD"]
_CURRENCIES = frozenset(("KRW", "USD"))
_SIDES = frozenset(("buy", "sell"))


def _decimal(value: object, label: str) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a finite decimal")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{label} must be a finite decimal") from exc
    if not result.is_finite():
        raise ValueError(f"{label} must be a finite decimal")
    return result


def _iso_session(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be an ISO date")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{label} must be an ISO date") from exc
    if parsed.isoformat() != value:
        raise ValueError(f"{label} must be an ISO date")
    return value


def _normalise_trade(
    trade: LossTrade, index: int, expected_currency: Currency | None
) -> LossTrade:
    if not isinstance(trade, LossTrade):
        raise ValueError(f"trade {index} is invalid")
    if not isinstance(trade.symbol, str) or not trade.symbol:
        raise ValueError(f"trade {index} symbol must be non-empty")
    if trade.side not in _SIDES:
        raise ValueError(f"trade {index} side must be buy or sell")
    if trade.currency not in _CURRENCIES:
        raise ValueError(f"trade {index} currency must be KRW or USD")
    if expected_currency is not None and trade.currency != expected_currency:
        raise ValueError(f"trade {index} currency does not match market")
    quantity = _decimal(trade.quantity, f"trade {index} quantity")
    market_open = _decimal(trade.market_open, f"trade {index} market open")
    fill_price = _decimal(trade.fill_price, f"trade {index} fill price")
    fee = _decimal(trade.fee, f"trade {index} fee")
    tax = _decimal(trade.tax, f"trade {index} tax")
    if quantity <= 0:
        raise ValueError(f"trade {index} quantity must be positive")
    if market_open <= 0 or fill_price <= 0:
        raise ValueError(f"trade {index} prices must be positive")
    if fee < 0 or tax < 0:
        raise ValueError(f"trade {index} costs must be non-negative")
    return LossTrade(
        symbol=trade.symbol,
        side=trade.side,
        quantity=quantity,
        market_open=market_open,
        fill_price=fill_price,
        fee=fee,
        tax=tax,
        currency=trade.currency,
        session=_iso_session(trade.session, f"trade {index} session"),
    )


def _normalise_position(lot: PositionLot, index: int) -> PositionLot:
    if not isinstance(lot, PositionLot):
        raise ValueError(f"initial position {index} is invalid")
    if not isinstance(lot.symbol, str) or not lot.symbol:
        raise ValueError(f"initial position {index} symbol must be non-empty")
    if lot.currency not in _CURRENCIES:
        raise ValueError(f"initial position {index} currency must be KRW or USD")
    quantity = _decimal(lot.quantity, f"initial position {index} quantity")
    unit_cost = _decimal(lot.unit_cost, f"initial position {index} cost")
    fill_unit_cost = (
        None
        if lot.fill_unit_cost is None
        else _decimal(lot.fill_unit_cost, f"initial position {index} fill cost")
    )
    if (
        quantity <= 0
        or unit_cost <= 0
        or (fill_unit_cost is not None and fill_unit_cost <= 0)
    ):
        raise ValueError("initial position quantity and cost must be positive")
    return PositionLot(
        symbol=lot.symbol,
        quantity=quantity,
        unit_cost=unit_cost,
        currency=lot.currency,
        fill_unit_cost=fill_unit_cost,
    )


@dataclass(frozen=True)
class AccountingComponent:
    """One accounting item with explicit evidence and resume requirements."""

    availability: Availability
    value: Decimal | None
    evidence: tuple[str, ...] = ()
    resume_inputs: tuple[str, ...] = ()
    diagnostic_value: Decimal | None = None

    @property
    def available(self) -> bool:
        return self.availability == "available"


@dataclass(frozen=True)
class LossTrade:
    """A small, currency-local trade record for deterministic FIFO checks."""

    symbol: str
    side: Literal["buy", "sell"]
    quantity: Decimal
    market_open: Decimal
    fill_price: Decimal
    fee: Decimal = Decimal(0)
    tax: Decimal = Decimal(0)
    currency: Literal["KRW", "USD"] = "KRW"
    session: str = ""

    @classmethod
    def from_research_trade(cls, trade: ResearchTrade) -> LossTrade:
        with localcontext(DECIMAL_CONTEXT):
            expected = trade.fill_price * trade.quantity
            if trade.notional != expected:
                raise ValueError(f"{trade.symbol} notional does not match fill price")
            return cls(
                symbol=trade.symbol,
                side=trade.side,
                quantity=Decimal(trade.quantity),
                market_open=trade.market_open,
                fill_price=trade.fill_price,
                fee=trade.fee,
                tax=trade.tax,
                currency=trade.currency,
                session=trade.fill_session.isoformat(),
            )


@dataclass(frozen=True)
class PositionLot:
    symbol: str
    quantity: Decimal
    unit_cost: Decimal
    currency: Literal["KRW", "USD"] = "KRW"
    fill_unit_cost: Decimal | None = None


@dataclass(frozen=True)
class FXDecomposition:
    native_change: Decimal
    local_effect: Decimal
    fx_effect: Decimal
    cross_effect: Decimal
    total_change: Decimal


@dataclass(frozen=True)
class LossAccountingReport:
    status: ReportStatus
    raw_realized_pnl: AccountingComponent
    fill_realized_pnl: AccountingComponent
    raw_unrealized_pnl: AccountingComponent
    fill_unrealized_pnl: AccountingComponent
    dividends: AccountingComponent
    fees: AccountingComponent
    taxes: AccountingComponent
    slippage: AccountingComponent
    fx: AccountingComponent
    cash_balance: AccountingComponent
    raw_net_pnl: AccountingComponent
    fill_net_pnl: AccountingComponent
    violations: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    trade_count: int = 0
    session_count: int = 0
    source_sha256: str | None = None

    def as_dict(self) -> dict[str, object]:
        def encode(value: object) -> object:
            if isinstance(value, Decimal):
                return str(value)
            if isinstance(value, tuple):
                return [encode(item) for item in value]
            if isinstance(value, dict):
                return {str(key): encode(item) for key, item in value.items()}
            return value

        return encode(asdict(self))  # type: ignore[return-value]


@dataclass(frozen=True)
class _FIFOResult:
    raw_realized: Decimal
    fill_realized: Decimal
    raw_unrealized: Decimal
    fill_unrealized: Decimal
    slippage: Decimal
    fees: Decimal
    taxes: Decimal
    cash_delta: Decimal
    remaining: tuple[PositionLot, ...]
    missing_marks: tuple[str, ...]


def slippage_amount(trade: LossTrade) -> Decimal:
    """Return positive execution cost; the sign is side-aware."""

    with localcontext(DECIMAL_CONTEXT):
        normalised = _normalise_trade(trade, 0, None)
        delta = normalised.fill_price - normalised.market_open
        return normalised.quantity * (delta if normalised.side == "buy" else -delta)


def fx_decomposition(
    initial_native: Decimal,
    final_native: Decimal,
    initial_fx: Decimal,
    final_fx: Decimal,
) -> FXDecomposition:
    """Decompose ``N1*F1 - N0*F0`` including the cross term."""

    with localcontext(DECIMAL_CONTEXT):
        initial_native_value = _decimal(initial_native, "initial native value")
        final_native_value = _decimal(final_native, "final native value")
        initial_fx_value = _decimal(initial_fx, "initial FX rate")
        final_fx_value = _decimal(final_fx, "final FX rate")
        if initial_fx_value <= 0 or final_fx_value <= 0:
            raise ValueError("FX rates must be positive")
        n_change = final_native_value - initial_native_value
        f_change = final_fx_value - initial_fx_value
        local = initial_fx_value * n_change
        fx = initial_native_value * f_change
        cross = n_change * f_change
        return FXDecomposition(
            native_change=n_change,
            local_effect=local,
            fx_effect=fx,
            cross_effect=cross,
            total_change=local + fx + cross,
        )


def _fifo(
    trades: Sequence[LossTrade],
    final_marks: Mapping[str, Decimal],
    initial_positions: Sequence[PositionLot],
) -> _FIFOResult:
    lots: dict[tuple[str, str], deque[PositionLot]] = defaultdict(deque)
    for lot in initial_positions:
        lots[(lot.symbol, lot.currency)].append(
            PositionLot(
                symbol=lot.symbol,
                quantity=lot.quantity,
                unit_cost=lot.unit_cost,
                currency=lot.currency,
                fill_unit_cost=lot.fill_unit_cost or lot.unit_cost,
            )
        )
    raw_realized = Decimal(0)
    fill_realized = Decimal(0)
    slippage = Decimal(0)
    fees = Decimal(0)
    taxes = Decimal(0)
    cash_delta = Decimal(0)
    seen: set[tuple[object, ...]] = set()
    for index, trade in enumerate(trades):
        key = (
            trade.session,
            trade.symbol,
            trade.side,
            trade.quantity,
            trade.market_open,
            trade.fill_price,
            trade.fee,
            trade.tax,
            trade.currency,
        )
        if key in seen:
            raise ValueError(f"duplicate trade: {trade.symbol} {trade.session}")
        seen.add(key)
        bucket = lots[(trade.symbol, trade.currency)]
        quantity = trade.quantity
        if trade.side == "buy":
            bucket.append(
                PositionLot(
                    symbol=trade.symbol,
                    quantity=quantity,
                    unit_cost=trade.market_open,
                    currency=trade.currency,
                    fill_unit_cost=trade.fill_price,
                )
            )
            cash_delta -= trade.quantity * trade.fill_price + trade.fee + trade.tax
        else:
            while quantity:
                if not bucket:
                    raise ValueError(f"sell exceeds FIFO position: {trade.symbol}")
                lot = bucket[0]
                consumed = min(quantity, lot.quantity)
                raw_realized += consumed * (trade.market_open - lot.unit_cost)
                fill_realized += consumed * (
                    trade.fill_price - (lot.fill_unit_cost or lot.unit_cost)
                )
                if consumed == lot.quantity:
                    bucket.popleft()
                else:
                    bucket[0] = PositionLot(
                        symbol=lot.symbol,
                        quantity=lot.quantity - consumed,
                        unit_cost=lot.unit_cost,
                        currency=lot.currency,
                        fill_unit_cost=lot.fill_unit_cost,
                    )
                quantity -= consumed
            cash_delta += trade.quantity * trade.fill_price - trade.fee - trade.tax
        slippage += slippage_amount(trade)
        fees += trade.fee
        taxes += trade.tax
    raw_unrealized = Decimal(0)
    fill_unrealized = Decimal(0)
    remaining: list[PositionLot] = []
    missing_marks: set[str] = set()
    for bucket in lots.values():
        for lot in bucket:
            remaining.append(lot)
            if lot.symbol not in final_marks:
                missing_marks.add(lot.symbol)
                continue
            mark = _decimal(final_marks[lot.symbol], f"final mark {lot.symbol}")
            if mark <= 0:
                raise ValueError(f"final mark {lot.symbol} must be positive")
            raw_unrealized += lot.quantity * (mark - lot.unit_cost)
            fill_unrealized += lot.quantity * (
                mark - (lot.fill_unit_cost or lot.unit_cost)
            )
    return _FIFOResult(
        raw_realized=raw_realized,
        fill_realized=fill_realized,
        raw_unrealized=raw_unrealized,
        fill_unrealized=fill_unrealized,
        slippage=slippage,
        fees=fees,
        taxes=taxes,
        cash_delta=cash_delta,
        remaining=tuple(remaining),
        missing_marks=tuple(sorted(missing_marks)),
    )


def _available(value: Decimal, evidence: str) -> AccountingComponent:
    return AccountingComponent("available", value, (evidence,))


def _unavailable(
    *, diagnostic: Decimal | None = None, reason: str, resume: str
) -> AccountingComponent:
    return AccountingComponent("unavailable", None, (reason,), (resume,), diagnostic)


def account_trades(
    trades: Sequence[LossTrade],
    *,
    final_marks: Mapping[str, Decimal],
    initial_positions: Sequence[PositionLot] = (),
    complete_history: bool = False,
    dividends: Mapping[str, Decimal] | None = None,
    dividend_evidence_complete: bool = False,
    initial_cash: Decimal | None = None,
    expected_currency: Currency | None = None,
) -> LossAccountingReport:
    """Account explicit trades without invoking a strategy or simulation."""

    with localcontext(DECIMAL_CONTEXT):
        if expected_currency is not None and expected_currency not in _CURRENCIES:
            raise ValueError("expected currency must be KRW or USD")
        normalised_trades = tuple(
            _normalise_trade(trade, index, expected_currency)
            for index, trade in enumerate(trades)
        )
        normalised_positions = tuple(
            _normalise_position(lot, index)
            for index, lot in enumerate(initial_positions)
        )
        currencies = {trade.currency for trade in normalised_trades} | {
            lot.currency for lot in normalised_positions
        }
        if len(currencies) > 1:
            raise ValueError("mixed KRW/USD accounting is unsupported")
        if (
            expected_currency is not None
            and currencies
            and currencies != {expected_currency}
        ):
            raise ValueError("trade and position currencies do not match market")
        currency_label = next(iter(currencies), expected_currency or "unspecified")
        marks = {
            symbol: _decimal(value, f"final mark {symbol}")
            for symbol, value in final_marks.items()
        }
        if any(not isinstance(symbol, str) or not symbol for symbol in marks):
            raise ValueError("final mark symbol must be non-empty")
        if any(value <= 0 for value in marks.values()):
            raise ValueError("final marks must be positive")
        normalised_dividends = (
            {
                symbol: _decimal(value, f"dividend {symbol}")
                for symbol, value in dividends.items()
            }
            if dividends is not None
            else None
        )
        if normalised_dividends is not None and any(
            not isinstance(symbol, str) or not symbol for symbol in normalised_dividends
        ):
            raise ValueError("dividend symbol must be non-empty")
        sessions = [trade.session for trade in normalised_trades]
        if sessions != sorted(sessions):
            raise ValueError("trades are not chronological")
        initial_cash_value = (
            None if initial_cash is None else _decimal(initial_cash, "initial cash")
        )
        if initial_cash_value is not None and initial_cash_value <= 0:
            raise ValueError("initial cash must be positive")
        if normalised_dividends is not None and any(
            value < 0 for value in normalised_dividends.values()
        ):
            raise ValueError("dividends must be non-negative")
        fifo = _fifo(normalised_trades, marks, normalised_positions)
        dividends_value = (
            sum(normalised_dividends.values(), Decimal(0))
            if normalised_dividends
            else Decimal(0)
        )
        raw_realized = (
            _available(fifo.raw_realized, "FIFO open-price basis")
            if complete_history
            else _unavailable(
                diagnostic=fifo.raw_realized,
                reason="complete trade history and initial positions are unproven",
                resume="provide a complete, ordered fill ledger and opening positions",
            )
        )
        fill_realized = (
            _available(fifo.fill_realized, "FIFO fill-price basis")
            if complete_history
            else _unavailable(
                diagnostic=fifo.fill_realized,
                reason="complete trade history and initial positions are unproven",
                resume="provide a complete, ordered fill ledger and opening positions",
            )
        )
        raw_unrealized = (
            _available(fifo.raw_unrealized, "remaining FIFO lots and final marks")
            if complete_history and not fifo.missing_marks
            else _unavailable(
                diagnostic=fifo.raw_unrealized,
                reason=(
                    "final marks are missing"
                    if fifo.missing_marks
                    else "corporate-action quantity preservation is unproven"
                ),
                resume=(
                    "provide symbol-level final marks"
                    if fifo.missing_marks
                    else (
                        "provide opening positions and complete split/delisting records"
                    )
                ),
            )
        )
        fill_unrealized = (
            _available(fifo.fill_unrealized, "remaining FIFO lots and final marks")
            if complete_history and not fifo.missing_marks
            else _unavailable(
                diagnostic=fifo.fill_unrealized,
                reason=(
                    "final marks are missing"
                    if fifo.missing_marks
                    else "corporate-action quantity preservation is unproven"
                ),
                resume=(
                    "provide symbol-level final marks"
                    if fifo.missing_marks
                    else (
                        "provide opening positions and complete split/delisting records"
                    )
                ),
            )
        )
        dividend_component = (
            _available(
                dividends_value,
                f"complete dividend evidence supplied in {currency_label}",
            )
            if normalised_dividends is not None and dividend_evidence_complete
            else _unavailable(
                reason=(
                    "dividend evidence is absent or incomplete; zero is not inferred"
                ),
                resume="provide complete ex-date, quantity, and cash dividend evidence",
            )
        )
        fees = _available(fifo.fees, f"stored trade fee values in {currency_label}")
        taxes = _available(fifo.taxes, f"stored trade tax values in {currency_label}")
        slippage = _available(
            fifo.slippage,
            f"open and fill prices in each {currency_label} trade",
        )
        raw_net = (
            fifo.raw_realized
            + fifo.raw_unrealized
            - fifo.slippage
            - fifo.fees
            - fifo.taxes
        )
        fill_net = fifo.fill_realized + fifo.fill_unrealized - fifo.fees - fifo.taxes
        cash = (
            _available(
                initial_cash_value + fifo.cash_delta + dividends_value,
                f"initial cash and trade cashflows in {currency_label}, "
                "plus complete dividends",
            )
            if initial_cash_value is not None
            and normalised_dividends is not None
            and dividend_evidence_complete
            else _unavailable(
                diagnostic=(
                    None
                    if initial_cash_value is None
                    else initial_cash_value + fifo.cash_delta
                ),
                reason=(
                    "initial cash was not supplied"
                    if initial_cash_value is None
                    else "cash depends on complete dividend evidence"
                ),
                resume=(
                    "provide the opening cash balance in the same currency"
                    if initial_cash_value is None
                    else "provide complete dividend cashflow evidence"
                ),
            )
        )
        raw_net_available = (
            raw_realized.available
            and raw_unrealized.available
            and dividend_component.available
            and fees.available
            and taxes.available
            and slippage.available
        )
        fill_net_available = (
            fill_realized.available
            and fill_unrealized.available
            and dividend_component.available
            and fees.available
            and taxes.available
        )
        return LossAccountingReport(
            status=(
                "complete" if raw_net_available and fill_net_available else "blocked"
            ),
            raw_realized_pnl=raw_realized,
            fill_realized_pnl=fill_realized,
            raw_unrealized_pnl=raw_unrealized,
            fill_unrealized_pnl=fill_unrealized,
            dividends=dividend_component,
            fees=fees,
            taxes=taxes,
            slippage=slippage,
            fx=_unavailable(
                diagnostic=Decimal(0),
                reason="no FX observations supplied",
                resume="provide opening and closing native values and FX rates",
            ),
            cash_balance=cash,
            raw_net_pnl=(
                _available(raw_net + dividends_value, "FIFO price basis less costs")
                if raw_net_available
                else _unavailable(
                    diagnostic=raw_net + dividends_value,
                    reason="net PnL depends on unavailable accounting components",
                    resume="resolve history, corporate actions, and dividends first",
                )
            ),
            fill_net_pnl=(
                _available(fill_net + dividends_value, "FIFO fill basis less costs")
                if fill_net_available
                else _unavailable(
                    diagnostic=fill_net + dividends_value,
                    reason="net PnL depends on unavailable accounting components",
                    resume="resolve history, corporate actions, and dividends first",
                )
            ),
            trade_count=len(normalised_trades),
        )


def account_result(
    result: MarketResearchResult, *, source_sha256: str | None = None
) -> LossAccountingReport:
    """Diagnose one saved result, preserving its missing-evidence boundaries."""

    with localcontext(DECIMAL_CONTEXT):
        if len(result.equity) > MAX_SESSIONS:
            raise ValueError(f"result exceeds {MAX_SESSIONS} sessions")
        if len(result.trades) > MAX_TRADES:
            raise ValueError(f"result exceeds {MAX_TRADES} trades")
        if not result.equity:
            raise ValueError("result has no equity observations")
        equity_sessions = [point.session for point in result.equity]
        if any(not isinstance(session, date) for session in equity_sessions):
            raise ValueError("equity sessions must be ISO dates")
        if equity_sessions != sorted(set(equity_sessions)):
            raise ValueError("equity sessions must be unique and chronological")
        fill_sessions = {trade.fill_session for trade in result.trades}
        missing_fill_sessions = fill_sessions - set(equity_sessions)
        if missing_fill_sessions:
            raise ValueError("trade fill session is absent from equity observations")
        expected_currency: Currency = "KRW" if result.market == "KR" else "USD"
        trades = tuple(LossTrade.from_research_trade(item) for item in result.trades)
        report = account_trades(
            trades, final_marks={}, expected_currency=expected_currency
        )
        fees = sum((item.fee for item in result.trades), Decimal(0))
        taxes = sum((item.tax for item in result.trades), Decimal(0))
        slippage = sum((slippage_amount(item) for item in trades), Decimal(0))
        first, last = result.equity[0], result.equity[-1]
        initial_native = first.cash_native + first.invested_krw / first.fx_krw_per_usd
        final_native = last.cash_native + last.invested_krw / last.fx_krw_per_usd
        decomposition = fx_decomposition(
            initial_native, final_native, first.fx_krw_per_usd, last.fx_krw_per_usd
        )
        raw_diag = report.raw_realized_pnl.diagnostic_value or Decimal(0)
        limitations = tuple(result.limitations) + (
            "FIFO is diagnostic only: opening positions, corporate actions, and "
            "complete fills are not proven.",
            "Economic evaluation remains not-evaluated; this approximate pilot is "
            "blocked.",
            "Observed cash is the saved KRW cash_krw value; native cash and FX are "
            "separate.",
        )
        return LossAccountingReport(
            status="blocked",
            raw_realized_pnl=_unavailable(
                diagnostic=report.raw_realized_pnl.diagnostic_value,
                reason=(
                    "saved result has no proof of complete fills and opening positions"
                ),
                resume="store a complete ordered fill ledger and opening positions",
            ),
            fill_realized_pnl=report.fill_realized_pnl,
            raw_unrealized_pnl=_unavailable(
                diagnostic=report.raw_unrealized_pnl.diagnostic_value,
                reason=(
                    "saved result has no symbol-level final marks and corporate-action "
                    "ledger"
                ),
                resume=(
                    "provide symbol-level final marks and complete corporate actions"
                ),
            ),
            fill_unrealized_pnl=report.fill_unrealized_pnl,
            dividends=_unavailable(
                reason=(
                    "dividend evidence is absent or incomplete; zero is not inferred"
                ),
                resume="provide complete dividend evidence",
            ),
            fees=_available(
                fees,
                f"stored ResearchTrade.fee values in native {expected_currency}",
            ),
            taxes=_available(
                taxes,
                f"stored ResearchTrade.tax values in native {expected_currency}",
            ),
            slippage=_available(
                slippage,
                "stored market_open and fill_price values in "
                f"native {expected_currency}",
            ),
            fx=_available(
                decomposition.fx_effect + decomposition.cross_effect,
                "first and last saved equity FX observations",
            ),
            cash_balance=_available(
                last.cash_krw,
                "last saved equity cash_krw observation in KRW",
            ),
            raw_net_pnl=_unavailable(
                diagnostic=raw_diag - slippage - fees - taxes,
                reason=(
                    "net PnL depends on unavailable realized/unrealized/dividend "
                    "components"
                ),
                resume=(
                    "resolve opening positions, marks, corporate actions, and dividends"
                ),
            ),
            fill_net_pnl=_unavailable(
                diagnostic=(report.fill_realized_pnl.diagnostic_value or Decimal(0))
                - fees
                - taxes,
                reason=(
                    "net PnL depends on unavailable realized/unrealized/dividend "
                    "components"
                ),
                resume=(
                    "resolve opening positions, marks, corporate actions, and dividends"
                ),
            ),
            limitations=limitations,
            trade_count=len(result.trades),
            session_count=len(result.equity),
            source_sha256=source_sha256,
        )


def diagnose_saved_pilot(path: Path, *, expected_sha256: str) -> LossAccountingReport:
    """Hash-check and diagnose exactly one already saved pilot result."""

    body = path.read_bytes()
    actual = hashlib.sha256(body).hexdigest()
    if actual != expected_sha256:
        raise ValueError(f"pilot hash mismatch: {actual} != {expected_sha256}")
    payload = json.loads(body.decode("utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("result"), dict):
        raise ValueError("pilot JSON must contain a result object")
    allowed_keys = {
        "created_at",
        "data_contract_hash",
        "error",
        "final_promotability_reason",
        "final_promotable",
        "id",
        "input_hash",
        "pilot_run_id",
        "request",
        "result",
        "stage",
        "status",
        "updated_at",
    }
    unsupported = set(payload) - allowed_keys
    if unsupported:
        raise ValueError("pilot JSON contains unsupported order or timestamp metadata")
    result = MarketResearchResult.model_validate(payload["result"])
    return account_result(result, source_sha256=actual)


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = diagnose_saved_pilot(args.pilot, expected_sha256=args.expected_sha256)
    args.output.write_text(
        json.dumps(report.as_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
