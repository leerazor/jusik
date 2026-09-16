"""Independent chronological drawdown and latch diagnostics.

This module deliberately contains only stdlib code.  It consumes already saved
observations and trades; it never imports a strategy, portfolio engine, broker,
or service module.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field, replace
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path
from typing import Any, Literal

PRECISION = 50
MAX_SESSIONS = 300
LATCH_THRESHOLD = Decimal("0.20")
DRAW_DOWN_TOLERANCE_PP = Decimal("1e-20")

Status = Literal["success", "blocked", "invalid"]
LiquidationStatus = Literal["observed", "not_observed", "mismatch"]


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


def _date(value: object, label: str) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        raise ValueError(f"{label} must be an ISO date")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{label} must be an ISO date") from exc


@dataclass(frozen=True)
class SessionObservation:
    """One observed close; only explicitly supplied sessions are processed."""

    session: date
    nav_krw: Decimal
    open_available_symbols: frozenset[str] | None = None

    @classmethod
    def from_mapping(cls, row: Mapping[str, object]) -> SessionObservation:
        raw_open_symbols = row.get("open_available_symbols")
        return cls(
            session=_date(row.get("session"), "session"),
            nav_krw=_decimal(row.get("nav_krw"), "nav_krw"),
            open_available_symbols=(
                frozenset(str(value) for value in raw_open_symbols)
                if isinstance(raw_open_symbols, list)
                else None
            ),
        )


@dataclass(frozen=True)
class TradeObservation:
    """A saved signal/fill pair used to reconstruct quantity chronology."""

    signal_session: date
    fill_session: date
    symbol: str
    side: Literal["buy", "sell"]
    quantity: int

    @classmethod
    def from_mapping(cls, row: Mapping[str, object]) -> TradeObservation:
        signal = row.get("signal_session", row.get("signal"))
        fill = row.get("fill_session", row.get("session"))
        side = row.get("side")
        symbol = row.get("symbol")
        quantity = row.get("quantity")
        if side not in {"buy", "sell"}:
            raise ValueError("trade side must be buy or sell")
        typed_side: Literal["buy", "sell"] = "buy" if side == "buy" else "sell"
        if not isinstance(symbol, str) or not symbol:
            raise ValueError("trade symbol must be non-empty")
        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
            raise ValueError("trade quantity must be a positive integer")
        return cls(
            signal_session=_date(signal, "signal_session"),
            fill_session=_date(fill, "fill_session"),
            symbol=symbol,
            side=typed_side,
            quantity=quantity,
        )


@dataclass(frozen=True)
class LiquidationObservation:
    symbol: str
    held_quantity: int
    first_available_open: date | None
    filled_quantity: int
    fill_session: date | None
    status: LiquidationStatus


@dataclass(frozen=True)
class ChronologyResult:
    status: Status
    initial_cash_krw: Decimal
    peak_nav_krw: Decimal
    maximum_drawdown_pct: Decimal
    drawdown_by_session: tuple[tuple[date, Decimal], ...]
    latch_session: date | None
    latch_peak_nav_krw: Decimal | None
    held_quantities_at_latch: dict[str, int]
    liquidation: tuple[LiquidationObservation, ...]
    violations: tuple[str, ...] = ()
    blocked_reasons: tuple[str, ...] = ()

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


@dataclass(frozen=True)
class EvidenceState:
    calendar: Literal["ready", "missing", "unavailable"]
    benchmark: Literal["ready", "missing", "unavailable"]
    future_observation: Literal["ready", "missing", "unavailable"]

    @property
    def missing_required(self) -> tuple[str, ...]:
        names = ("calendar", "benchmark", "future_observation")
        return tuple(
            name
            for name, state in zip(
                names,
                (self.calendar, self.benchmark, self.future_observation),
                strict=True,
            )
            if state != "ready"
        )


@dataclass(frozen=True)
class PilotDiagnostic:
    status: Status
    input_grade: str
    chronology: ChronologyResult
    evidence: EvidenceState
    stored_maximum_drawdown_pct: Decimal | None
    stored_latch: bool | None
    stored_match: bool
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "status": self.status,
            "input_grade": self.input_grade,
            "chronology": self.chronology.as_dict(),
            "evidence": asdict(self.evidence),
            "stored_maximum_drawdown_pct": (
                str(self.stored_maximum_drawdown_pct)
                if self.stored_maximum_drawdown_pct is not None
                else None
            ),
            "stored_latch": self.stored_latch,
            "stored_match": self.stored_match,
            "reasons": list(self.reasons),
        }
        return result


def _validate_sessions(
    observations: Sequence[SessionObservation],
    expected_sessions: Sequence[date] | None,
) -> tuple[str, ...]:
    violations: list[str] = []
    dates = [item.session for item in observations]
    if dates != sorted(dates):
        violations.append("equity sessions are not chronological")
    if len(dates) != len(set(dates)):
        violations.append("duplicate equity session")
    if expected_sessions is not None and dates != list(expected_sessions):
        violations.append("equity sessions do not match required calendar")
    return tuple(violations)


def _validate_trades(
    trades: Sequence[TradeObservation], sessions: set[date]
) -> tuple[str, ...]:
    violations: list[str] = []
    keys = [item.fill_session for item in trades]
    if keys != sorted(keys):
        violations.append("trades are not chronological")
    fills: set[tuple[date, str, str]] = set()
    for item in trades:
        if item.signal_session >= item.fill_session:
            violations.append(f"signal must precede fill for {item.symbol}")
        if item.signal_session not in sessions:
            violations.append(f"signal session missing from calendar for {item.symbol}")
        if item.fill_session not in sessions:
            violations.append(f"fill session missing from calendar for {item.symbol}")
        fill_key = (item.fill_session, item.symbol, item.side)
        if fill_key in fills:
            violations.append(f"duplicate fill for {item.symbol}")
        fills.add(fill_key)
    return tuple(violations)


def analyze_chronology(
    observations: Sequence[SessionObservation],
    trades: Sequence[TradeObservation] = (),
    *,
    initial_cash_krw: Decimal = Decimal("100000000"),
    latch_threshold: Decimal = LATCH_THRESHOLD,
    expected_sessions: Sequence[date] | None = None,
) -> ChronologyResult:
    """Calculate DD/latch and reconcile the first post-latch open.

    The threshold comparison is made on NAV directly, without the reporting
    tolerance.  The tolerance applies only when comparing an independently
    recomputed percentage with a stored percentage.
    """

    with localcontext() as context:
        context.prec = PRECISION
        initial = _decimal(initial_cash_krw, "initial_cash_krw")
        threshold = _decimal(latch_threshold, "latch_threshold")
        if initial <= 0:
            raise ValueError("initial_cash_krw must be positive")
        if threshold <= 0 or threshold >= 1:
            raise ValueError("latch_threshold must be between zero and one")

        session_violations = _validate_sessions(observations, expected_sessions)
        session_dates = {item.session for item in observations}
        trade_violations = _validate_trades(trades, session_dates)
        violations = session_violations + trade_violations
        if violations:
            raise ValueError("; ".join(violations))
        if not observations:
            raise ValueError("at least one equity session is required")
        if len(observations) > MAX_SESSIONS:
            raise ValueError(f"at most {MAX_SESSIONS} equity sessions are supported")
        for item in observations:
            if item.nav_krw < 0 or not item.nav_krw.is_finite():
                raise ValueError("NAV must be finite and non-negative")

        peak = initial
        maximum = Decimal(0)
        drawdowns: list[tuple[date, Decimal]] = []
        latch_session: date | None = None
        latch_peak: Decimal | None = None
        for item in observations:
            peak = max(peak, item.nav_krw)
            drawdown = (peak - item.nav_krw) / peak * Decimal(100)
            maximum = max(maximum, drawdown)
            drawdowns.append((item.session, drawdown))
            if latch_session is None and item.nav_krw <= peak * (
                Decimal(1) - threshold
            ):
                latch_session = item.session
                latch_peak = peak

        later_buys = tuple(
            trade.symbol
            for trade in trades
            if latch_session is not None
            and trade.fill_session > latch_session
            and trade.side == "buy"
        )
        if later_buys:
            raise ValueError(
                "buy after drawdown latch: " + ", ".join(sorted(set(later_buys)))
            )

        def ledger(until: date | None = None) -> dict[str, int]:
            held_by_symbol: dict[str, int] = {}
            for trade in trades:
                if until is not None and trade.fill_session > until:
                    break
                current = held_by_symbol.get(trade.symbol, 0)
                if trade.side == "buy":
                    held_by_symbol[trade.symbol] = current + trade.quantity
                elif trade.quantity > current:
                    raise ValueError(f"sell exceeds held quantity for {trade.symbol}")
                elif trade.quantity == current:
                    held_by_symbol.pop(trade.symbol, None)
                else:
                    held_by_symbol[trade.symbol] = current - trade.quantity
            return held_by_symbol

        ledger()
        held = ledger(latch_session) if latch_session is not None else {}

        liquidations: list[LiquidationObservation] = []
        for symbol, quantity in sorted(held.items()):
            available_after = {
                item.session
                for item in observations
                if latch_session is not None
                and item.session > latch_session
                and item.open_available_symbols is not None
                and symbol in item.open_available_symbols
            }
            first_open = min(available_after) if available_after else None
            if first_open is None:
                liquidations.append(
                    LiquidationObservation(
                        symbol, quantity, None, 0, None, "not_observed"
                    )
                )
                continue
            sells = [
                trade
                for trade in trades
                if trade.symbol == symbol
                and trade.side == "sell"
                and trade.fill_session >= first_open
            ]
            first_sell_date = min((trade.fill_session for trade in sells), default=None)
            filled = sum(
                trade.quantity for trade in sells if trade.fill_session == first_open
            )
            liquidation_status: LiquidationStatus = (
                "observed"
                if filled == quantity and first_sell_date == first_open
                else "mismatch"
            )
            liquidations.append(
                LiquidationObservation(
                    symbol,
                    quantity,
                    first_open,
                    filled,
                    first_sell_date,
                    liquidation_status,
                )
            )

        if latch_session is None:
            status: Status = "success"
        elif any(item.status != "observed" for item in liquidations):
            status = "blocked"
        else:
            status = "success"
        return ChronologyResult(
            status=status,
            initial_cash_krw=initial,
            peak_nav_krw=peak,
            maximum_drawdown_pct=maximum,
            drawdown_by_session=tuple(drawdowns),
            latch_session=latch_session,
            latch_peak_nav_krw=latch_peak,
            held_quantities_at_latch=dict(sorted(held.items())),
            liquidation=tuple(liquidations),
        )


def _strict_json(path: Path) -> Any:
    def reject(value: str) -> Any:
        raise ValueError(f"non-finite JSON value in {path}: {value}")

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key in {path}: {key}")
            result[key] = value
        return result

    return json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=reject,
        parse_float=Decimal,
        object_pairs_hook=unique,
    )


def _dataset_open_symbols(path: Path) -> dict[date, frozenset[str]]:
    payload = _strict_json(path)
    if not isinstance(payload, dict) or not isinstance(payload.get("bars"), list):
        raise ValueError("dataset must contain a bars list")
    by_session: dict[date, set[str]] = {}
    seen: set[tuple[date, str]] = set()
    for row in payload["bars"]:
        if not isinstance(row, dict):
            raise ValueError("dataset bar must be an object")
        session = _date(row.get("session"), "bar session")
        symbol = row.get("symbol")
        if not isinstance(symbol, str) or not symbol:
            raise ValueError("bar symbol must be non-empty")
        key = (session, symbol)
        if key in seen:
            raise ValueError(f"duplicate dataset bar for {symbol} on {session}")
        seen.add(key)
        opening = _decimal(row.get("open"), "bar open")
        if opening > 0:
            by_session.setdefault(session, set()).add(symbol)
    return {session: frozenset(symbols) for session, symbols in by_session.items()}


def diagnose_saved_pilot(
    path: Path, dataset_path: Path | None = None
) -> PilotDiagnostic:
    """Diagnose one saved pilot without creating a new run.

    A report cannot be successful when calendar, benchmark, or future evidence
    is absent.  Stored NAV is used for chronology only; this is not a full NAV
    accounting proof.
    """

    payload = _strict_json(path)
    if not isinstance(payload, dict) or not isinstance(payload.get("result"), dict):
        raise ValueError("pilot file must contain a result object")
    result = payload["result"]
    equity_rows = result.get("equity")
    trade_rows = result.get("trades")
    if not isinstance(equity_rows, list) or not isinstance(trade_rows, list):
        raise ValueError("pilot result must contain equity and trades lists")
    observations = [SessionObservation.from_mapping(row) for row in equity_rows]
    trades = [TradeObservation.from_mapping(row) for row in trade_rows]
    request = result.get("request")
    metrics = result.get("metrics")
    if not isinstance(request, dict) or not isinstance(metrics, dict):
        raise ValueError("pilot result must contain request and metrics objects")
    request_initial = _decimal(
        request.get("initial_cash_krw"), "request initial_cash_krw"
    )
    metrics_initial = _decimal(
        metrics.get("initial_cash_krw"), "metrics initial_cash_krw"
    )
    expected_initial = Decimal("100000000")
    if request_initial != metrics_initial or request_initial != expected_initial:
        raise ValueError("pilot initial capital does not match the frozen mandate")
    if dataset_path is not None:
        open_symbols = _dataset_open_symbols(dataset_path)
        observations = [
            replace(
                observation,
                open_available_symbols=open_symbols.get(
                    observation.session, frozenset()
                ),
            )
            for observation in observations
        ]
    chronology = analyze_chronology(
        observations, trades, initial_cash_krw=request_initial
    )
    # This bounded diagnostic has no separately validated calendar, benchmark,
    # or prospective-observation artifact.  Capability flags in the pilot are
    # not evidence of those contracts.
    evidence = EvidenceState(
        calendar="unavailable",
        benchmark="unavailable",
        future_observation="unavailable",
    )
    stored_dd: Decimal | None = None
    stored_latch: bool | None = None
    if isinstance(metrics, dict):
        if metrics.get("max_drawdown_pct") is not None:
            stored_dd = _decimal(metrics["max_drawdown_pct"], "stored max_drawdown_pct")
        if metrics.get("drawdown_latched") is not None:
            stored_latch = bool(int(str(metrics["drawdown_latched"])))
    stored_drawdowns: dict[date, Decimal] = {}
    for row in equity_rows:
        if not isinstance(row, dict):
            raise ValueError("equity row must be an object")
        stored_drawdowns[_date(row.get("session"), "equity session")] = _decimal(
            row.get("drawdown_pct"), "stored drawdown_pct"
        )
    recomputed_drawdowns = dict(chronology.drawdown_by_session)
    session_match = stored_drawdowns.keys() == recomputed_drawdowns.keys() and all(
        compare_percentage_points(
            stored_drawdowns[session], recomputed_drawdowns[session]
        )
        for session in stored_drawdowns
    )
    stored_match = (
        stored_dd is not None
        and compare_percentage_points(stored_dd, chronology.maximum_drawdown_pct)
        and stored_latch == (chronology.latch_session is not None)
        and session_match
    )
    reasons = list(evidence.missing_required)
    if not stored_match:
        reasons.append(
            "stored NAV drawdown or latch does not match independent chronology"
        )
    status: Status = (
        "success" if not reasons and chronology.status == "success" else "blocked"
    )
    return PilotDiagnostic(
        status=status,
        input_grade=str(result.get("research_grade", "unknown")),
        chronology=chronology,
        evidence=evidence,
        stored_maximum_drawdown_pct=stored_dd,
        stored_latch=stored_latch,
        stored_match=stored_match,
        reasons=tuple(reasons),
    )


def compare_percentage_points(expected: Decimal, observed: Decimal) -> bool:
    """Compare DD/MDD values with the fixed 1e-20 percentage-point tolerance."""

    with localcontext() as context:
        context.prec = PRECISION
        return (
            abs(_decimal(expected, "expected") - _decimal(observed, "observed"))
            <= DRAW_DOWN_TOLERANCE_PP
        )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", type=Path, required=True)
    parser.add_argument("--dataset", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = diagnose_saved_pilot(args.pilot, args.dataset)
    output = report.as_dict()
    output["inputs"] = {
        "pilot_sha256": _sha256(args.pilot),
        "dataset_sha256": _sha256(args.dataset) if args.dataset else None,
    }
    output["checks"] = {
        "stored_chronology_match": report.stored_match,
        "no_later_buy_or_latch_release": True,
        "accounting_proof": False,
    }
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


__all__ = [
    "DRAW_DOWN_TOLERANCE_PP",
    "EvidenceState",
    "LATCH_THRESHOLD",
    "MAX_SESSIONS",
    "LiquidationObservation",
    "PRECISION",
    "PilotDiagnostic",
    "SessionObservation",
    "TradeObservation",
    "analyze_chronology",
    "compare_percentage_points",
    "diagnose_saved_pilot",
]


if __name__ == "__main__":
    raise SystemExit(_main())
