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
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path
from typing import Literal

from jusik.market_history_models import MarketResearchResult, ResearchTrade

PRECISION = 50
MAX_SESSIONS = 300
MAX_TRADES = 200

Availability = Literal["available", "unavailable"]
ReportStatus = Literal["complete", "blocked", "invalid"]


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

    delta = trade.fill_price - trade.market_open
    return trade.quantity * (delta if trade.side == "buy" else -delta)


def fx_decomposition(
    initial_native: Decimal,
    final_native: Decimal,
    initial_fx: Decimal,
    final_fx: Decimal,
) -> FXDecomposition:
    """Decompose ``N1*F1 - N0*F0`` including the cross term."""

    if initial_fx <= 0 or final_fx <= 0:
        raise ValueError("FX rates must be positive")
    n_change = final_native - initial_native
    f_change = final_fx - initial_fx
    local = initial_fx * n_change
    fx = initial_native * f_change
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
        if lot.quantity <= 0 or lot.unit_cost <= 0:
            raise ValueError("initial position quantity and cost must be positive")
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
        if trade.quantity <= 0:
            raise ValueError(f"trade {index} quantity must be positive")
        if trade.market_open <= 0 or trade.fill_price <= 0:
            raise ValueError(f"trade {index} prices must be positive")
        if trade.fee < 0 or trade.tax < 0:
            raise ValueError(f"trade {index} costs must be non-negative")
        key = (
            trade.session,
            trade.symbol,
            trade.side,
            trade.quantity,
            trade.market_open,
            trade.fill_price,
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
            cash_delta -= trade.quantity * trade.fill_price + trade.fee
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
) -> LossAccountingReport:
    """Account explicit trades without invoking a strategy or simulation."""

    with localcontext() as context:
        context.prec = PRECISION
        sessions = [trade.session for trade in trades if trade.session]
        if sessions != sorted(sessions):
            raise ValueError("trades are not chronological")
        if initial_cash is not None and initial_cash <= 0:
            raise ValueError("initial cash must be positive")
        if dividends is not None and any(value < 0 for value in dividends.values()):
            raise ValueError("dividends must be non-negative")
        fifo = _fifo(trades, final_marks, initial_positions)
        dividends_value = (
            sum(dividends.values(), Decimal(0)) if dividends else Decimal(0)
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
            _available(dividends_value, "complete dividend evidence supplied")
            if dividends is not None and dividend_evidence_complete
            else _unavailable(
                reason=(
                    "dividend evidence is absent or incomplete; zero is not inferred"
                ),
                resume="provide complete ex-date, quantity, and cash dividend evidence",
            )
        )
        fees = _available(fifo.fees, "stored trade fee values")
        taxes = _available(fifo.taxes, "stored trade tax values")
        slippage = _available(fifo.slippage, "open and fill prices in each trade")
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
                initial_cash + fifo.cash_delta, "initial cash and trade cashflows"
            )
            if initial_cash is not None
            else _unavailable(
                diagnostic=fifo.cash_delta,
                reason="initial cash was not supplied",
                resume="provide the opening cash balance in the same currency",
            )
        )
        net_available = (
            complete_history and dividends is not None and dividend_evidence_complete
        )
        return LossAccountingReport(
            status="complete" if net_available else "blocked",
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
                if net_available
                else _unavailable(
                    diagnostic=raw_net + dividends_value,
                    reason="net PnL depends on unavailable accounting components",
                    resume="resolve history, corporate actions, and dividends first",
                )
            ),
            fill_net_pnl=(
                _available(fill_net + dividends_value, "FIFO fill basis less costs")
                if net_available
                else _unavailable(
                    diagnostic=fill_net + dividends_value,
                    reason="net PnL depends on unavailable accounting components",
                    resume="resolve history, corporate actions, and dividends first",
                )
            ),
            trade_count=len(trades),
        )


def account_result(
    result: MarketResearchResult, *, source_sha256: str | None = None
) -> LossAccountingReport:
    """Diagnose one saved result, preserving its missing-evidence boundaries."""

    if len(result.equity) > MAX_SESSIONS:
        raise ValueError(f"result exceeds {MAX_SESSIONS} sessions")
    if len(result.trades) > MAX_TRADES:
        raise ValueError(f"result exceeds {MAX_TRADES} trades")
    if not result.equity:
        raise ValueError("result has no equity observations")
    trades = tuple(LossTrade.from_research_trade(item) for item in result.trades)
    report = account_trades(trades, final_marks={})
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
        "Economic evaluation remains not-evaluated; this approximate pilot is blocked.",
    )
    return LossAccountingReport(
        status="blocked",
        raw_realized_pnl=_unavailable(
            diagnostic=report.raw_realized_pnl.diagnostic_value,
            reason="saved result has no proof of complete fills and opening positions",
            resume="store a complete ordered fill ledger and opening positions",
        ),
        fill_realized_pnl=report.fill_realized_pnl,
        raw_unrealized_pnl=_unavailable(
            diagnostic=report.raw_unrealized_pnl.diagnostic_value,
            reason=(
                "saved result has no symbol-level final marks and corporate-action "
                "ledger"
            ),
            resume="provide symbol-level final marks and complete corporate actions",
        ),
        fill_unrealized_pnl=report.fill_unrealized_pnl,
        dividends=_unavailable(
            reason="dividend evidence is absent or incomplete; zero is not inferred",
            resume="provide complete dividend evidence",
        ),
        fees=_available(fees, "stored ResearchTrade.fee values"),
        taxes=_available(taxes, "stored ResearchTrade.tax values"),
        slippage=_available(slippage, "stored market_open and fill_price values"),
        fx=_available(
            decomposition.fx_effect + decomposition.cross_effect,
            "first and last saved equity FX observations",
        ),
        cash_balance=_available(last.cash_krw, "last saved equity cash_krw"),
        raw_net_pnl=_unavailable(
            diagnostic=raw_diag - slippage - fees - taxes,
            reason=(
                "net PnL depends on unavailable realized/unrealized/dividend components"
            ),
            resume="resolve opening positions, marks, corporate actions, and dividends",
        ),
        fill_net_pnl=_unavailable(
            diagnostic=(report.fill_realized_pnl.diagnostic_value or Decimal(0))
            - fees
            - taxes,
            reason=(
                "net PnL depends on unavailable realized/unrealized/dividend components"
            ),
            resume="resolve opening positions, marks, corporate actions, and dividends",
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
