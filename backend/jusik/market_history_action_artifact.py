"""Build a deterministic, offline accounting replay artifact.

The adapter is intentionally small: it validates a JSON replay envelope and
delegates every accounting transition to ``market_history_action_accounting``.
It never reads market data, a database, or a broker and it never changes the
input bytes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Final, Literal, cast

from jusik.market_history_action_accounting import (
    AccountingError,
    AccountingState,
    Action,
    DividendAction,
    Holding,
    SplitAction,
    TransitionResult,
    UnsupportedActionError,
    accrue_dividend,
    action_identity,
    apply_split,
    normalize_action_payload,
    pay_dividend,
)

SCHEMA_VERSION: Final = 1
SEED: Final = 0
MAX_INPUT_BYTES: Final = 1 * 1024 * 1024
MAX_OUTPUT_BYTES: Final = 50 * 1024 * 1024
MAX_SYMBOLS: Final = 4
MAX_UTC_DATES: Final = 40
MAX_STEPS: Final = 80
Currency = Literal["KRW", "USD"]
Phase = Literal["split", "accrual", "payment"]


class ArtifactError(ValueError):
    """A malformed replay envelope or an unsafe artifact path."""


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant {value}")


def _decode_json(raw: bytes) -> object:
    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ArtifactError("input is not valid UTF-8 JSON") from exc


def _canonical_json(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise ArtifactError("input is not canonicalizable JSON") from exc


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ArtifactError(f"{label} must be an object")
    return value


def _list(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise ArtifactError(f"{label} must be an array")
    return value


def _decimal_string(value: object, label: str) -> Decimal:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ArtifactError(f"{label} must be a Decimal string")
    try:
        result = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise ArtifactError(f"{label} must be a Decimal string") from exc
    if not result.is_finite():
        raise ArtifactError(f"{label} must be a finite Decimal string")
    return result


def _currency(value: object, label: str) -> Currency:
    if not isinstance(value, str) or value not in {"KRW", "USD"}:
        raise ArtifactError(f"{label} must be KRW or USD")
    return cast(Currency, value)


def _timestamp(value: object, label: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value:
        try:
            parsed = datetime.fromisoformat(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ArtifactError(f"{label} timestamp is invalid") from exc
    else:
        raise ArtifactError(f"{label} must be an ISO timestamp")
    try:
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ArtifactError(f"{label} timestamp must be timezone-aware")
        return parsed.astimezone(UTC)
    except ArtifactError:
        raise
    except (OverflowError, ValueError) as exc:
        raise ArtifactError(f"{label} timestamp is invalid") from exc


def _action_payload(action: Action) -> dict[str, object]:
    if isinstance(action, SplitAction):
        return {
            "action_id": action.action_id,
            "kind": "split",
            "symbol": action.symbol,
            "effective_at": _timestamp(action.effective_at, "effective_at").isoformat(),
            "ratio": str(action.ratio),
            "currency": action.currency,
            "price_basis": action.price_basis,
            "before_price": (
                None if action.before_price is None else str(action.before_price)
            ),
            "after_price": (
                None if action.after_price is None else str(action.after_price)
            ),
        }
    return {
        "action_id": action.action_id,
        "kind": "dividend",
        "symbol": action.symbol,
        "effective_at": _timestamp(action.effective_at, "effective_at").isoformat(),
        "payment_at": _timestamp(action.payment_at, "payment_at").isoformat(),
        "amount_per_share": str(action.amount_per_share),
        "currency": action.currency,
        "entitled_quantity": (
            None if action.entitled_quantity is None else str(action.entitled_quantity)
        ),
        "entitlement_confirmed": action.entitlement_confirmed,
        "price_basis": action.price_basis,
    }


def _state_json(state: AccountingState) -> dict[str, object]:
    holdings = [
        {
            "symbol": item.symbol,
            "quantity": str(item.quantity),
            "raw_price": str(item.raw_price),
            "total_cost": str(item.total_cost),
            "currency": item.currency,
        }
        for item in state.holdings
    ]
    receivables = [
        {
            "action_id": item.action_id,
            "symbol": item.symbol,
            "entitled_quantity": str(item.entitled_quantity),
            "amount_per_share": str(item.amount_per_share),
            "gross_amount": str(item.gross_amount),
            "currency": item.currency,
            "effective_at": _timestamp(item.effective_at, "effective_at").isoformat(),
            "payment_at": _timestamp(item.payment_at, "payment_at").isoformat(),
        }
        for item in state.receivables
    ]
    records = [
        {
            "action_id": item.action_id,
            "kind": item.kind,
            "phase": item.phase,
            "identity_hash": item.identity_hash,
        }
        for item in state.action_records
    ]
    try:
        nav = str(state.nav)
    except (ArithmeticError, TypeError, ValueError) as exc:
        raise ArtifactError("NAV cannot be computed exactly") from exc
    return {
        "holdings": holdings,
        "cash": str(state.cash),
        "currency": state.currency,
        "price_basis": "raw",
        "receivables": receivables,
        "action_records": records,
        "nav": nav,
        "coverage": state.coverage,
        "accounting_status": state.accounting_status,
    }


def _state_from_payload(payload: Mapping[str, object]) -> AccountingState:
    required = {
        "holdings",
        "cash",
        "currency",
        "price_basis",
        "receivables",
        "action_records",
    }
    if set(payload) != required:
        raise ArtifactError("initial_state fields are incomplete or unsupported")
    if payload["price_basis"] != "raw":
        raise ArtifactError("initial_state price_basis must be raw")
    holdings_data = _list(payload["holdings"], "initial_state.holdings")
    if len(holdings_data) > MAX_SYMBOLS:
        raise ArtifactError("symbol limit exceeded")
    currency = _currency(payload["currency"], "initial_state.currency")
    holdings: list[Holding] = []
    symbols: set[str] = set()
    for index, value in enumerate(holdings_data):
        item = _mapping(value, f"initial_state.holdings[{index}]")
        if set(item) != {"symbol", "quantity", "raw_price", "total_cost", "currency"}:
            raise ArtifactError("holding fields are incomplete or unsupported")
        symbol = item["symbol"]
        if not isinstance(symbol, str) or not symbol:
            raise ArtifactError("holding symbol must be non-empty")
        if symbol in symbols:
            raise ArtifactError("duplicate holding symbol")
        symbols.add(symbol)
        holding_currency = _currency(item["currency"], "holding currency")
        if holding_currency != currency:
            raise ArtifactError("state contains mixed currencies")
        quantity = _decimal_string(item["quantity"], "holding quantity")
        raw_price = _decimal_string(item["raw_price"], "holding raw_price")
        total_cost = _decimal_string(item["total_cost"], "holding total_cost")
        if quantity < 0 or raw_price <= 0 or total_cost < 0:
            raise ArtifactError("holding financial values are outside bounds")
        holdings.append(
            Holding(symbol, quantity, raw_price, total_cost, holding_currency)
        )
    if _list(payload["receivables"], "initial_state.receivables"):
        raise ArtifactError("initial receivables must be empty")
    if _list(payload["action_records"], "initial_state.action_records"):
        raise ArtifactError("initial action_records must be empty")
    cash = _decimal_string(payload["cash"], "initial_state.cash")
    if cash < 0:
        raise ArtifactError("initial cash must be non-negative")
    return AccountingState(holdings=tuple(holdings), cash=cash, currency=currency)


def _require_action_decimal_strings(payload: Mapping[str, object]) -> None:
    fields = {
        "split": ("ratio", "before_price", "after_price"),
        "dividend": ("amount_per_share", "entitled_quantity"),
    }
    kind = payload.get("kind")
    if not isinstance(kind, str) or kind not in fields:
        raise UnsupportedActionError("action kind is unsupported")
    expected = (
        {
            "kind",
            "action_id",
            "symbol",
            "effective_at",
            "ratio",
            "currency",
            "price_basis",
            "before_price",
            "after_price",
        }
        if kind == "split"
        else {
            "kind",
            "action_id",
            "symbol",
            "effective_at",
            "payment_at",
            "amount_per_share",
            "currency",
            "entitled_quantity",
            "entitlement_confirmed",
            "price_basis",
        }
    )
    if set(payload) != expected:
        raise ArtifactError("action fields are incomplete or unsupported")
    for field in fields[cast(Literal["split", "dividend"], kind)]:
        if payload.get(field) is not None:
            _decimal_string(payload[field], f"action.{field}")


def _phase(value: object) -> Phase:
    if not isinstance(value, str) or value not in {"split", "accrual", "payment"}:
        raise ArtifactError("step phase is unsupported")
    return cast(Phase, value)


def _identity(action: Action | None) -> str | None:
    if action is None:
        return None
    try:
        return action_identity(action)
    except AccountingError:
        return None


def _result_json(result: TransitionResult) -> dict[str, object]:
    return {
        "status": result.status,
        "reason": result.reason,
        "identity_hash": result.identity_hash,
        "nav_before": None if result.nav_before is None else str(result.nav_before),
        "nav_after": None if result.nav_after is None else str(result.nav_after),
        "total_cost_before": (
            None if result.total_cost_before is None else str(result.total_cost_before)
        ),
        "total_cost_after": (
            None if result.total_cost_after is None else str(result.total_cost_after)
        ),
        "coverage": result.coverage,
    }


def _failed_result(
    state: AccountingState,
    status: str,
    reason: str,
    identity_hash: str | None = None,
) -> dict[str, object]:
    nav = _state_json(state)["nav"]
    return {
        "status": status,
        "reason": reason,
        "identity_hash": identity_hash,
        "nav_before": nav,
        "nav_after": nav,
        "total_cost_before": None,
        "total_cost_after": None,
        "coverage": "incomplete",
    }


def _step_result(
    state: AccountingState,
    phase: Phase,
    at: datetime | None,
    action_data: object,
) -> tuple[AccountingState, dict[str, object], object]:
    action: Action | None = None
    action_json: object = action_data
    try:
        action_map = _mapping(action_data, "step.action")
        _require_action_decimal_strings(action_map)
        normalized_payload = dict(action_map)
        normalized_payload["effective_at"] = _timestamp(
            action_map.get("effective_at"), "action.effective_at"
        )
        if action_map.get("kind") == "dividend":
            normalized_payload["payment_at"] = _timestamp(
                action_map.get("payment_at"), "action.payment_at"
            )
        action = normalize_action_payload(normalized_payload)
        action_json = _action_payload(action)
        if phase == "split" and not isinstance(action, SplitAction):
            raise ArtifactError("phase and action kind do not match")
        if phase != "split" and not isinstance(action, DividendAction):
            raise ArtifactError("phase and action kind do not match")
        if at is None:
            raise ArtifactError("step timestamp is invalid")
        if phase == "split":
            transition = apply_split(state, cast(SplitAction, action), at=at)
        elif phase == "accrual":
            transition = accrue_dividend(state, cast(DividendAction, action), at=at)
        else:
            transition = pay_dividend(state, cast(DividendAction, action), at=at)
        result = _result_json(transition)
        return transition.state, result, action_json
    except UnsupportedActionError as exc:
        return (
            state,
            _failed_result(state, "unsupported", str(exc), _identity(action)),
            action_json,
        )
    except (AccountingError, ArtifactError, TypeError, ValueError) as exc:
        return (
            state,
            _failed_result(state, "rejected", str(exc), _identity(action)),
            action_json,
        )


def _validate_caps(payload: Mapping[str, object], steps: list[object]) -> None:
    if len(steps) > MAX_STEPS:
        raise ArtifactError("step limit exceeded")
    symbols: set[str] = set()
    initial = _mapping(payload["initial_state"], "initial_state")
    for value in _list(initial["holdings"], "initial_state.holdings"):
        item = _mapping(value, "holding")
        symbol = item.get("symbol")
        if isinstance(symbol, str):
            symbols.add(symbol)
    dates: set[date] = set()
    for value in steps:
        item = _mapping(value, "step")
        action = item.get("action")
        if isinstance(action, Mapping):
            symbol = action.get("symbol")
            if isinstance(symbol, str) and symbol:
                symbols.add(symbol)
            for field in ("effective_at", "payment_at"):
                timestamp = action.get(field)
                try:
                    if isinstance(timestamp, str):
                        dates.add(_timestamp(timestamp, field).date())
                except ArtifactError:
                    pass
        timestamp = item.get("at")
        try:
            if isinstance(timestamp, str):
                dates.add(_timestamp(timestamp, "step.at").date())
        except ArtifactError:
            pass
    if len(symbols) > MAX_SYMBOLS:
        raise ArtifactError("symbol limit exceeded")
    if len(dates) > MAX_UTC_DATES:
        raise ArtifactError("UTC date limit exceeded")


def build_artifact(
    payload: Mapping[str, object], *, input_bytes: bytes | None = None
) -> dict[str, object]:
    """Replay a validated JSON-like envelope and return a serializable artifact."""
    raw = input_bytes if input_bytes is not None else _canonical_json(payload)
    if len(raw) > MAX_INPUT_BYTES:
        raise ArtifactError("input exceeds 1MiB")
    if input_bytes is not None:
        decoded = _decode_json(input_bytes)
        if not isinstance(decoded, Mapping) or _canonical_json(
            decoded
        ) != _canonical_json(payload):
            raise ArtifactError("input bytes do not match replay payload")
    if (
        type(payload.get("schema_version")) is not int
        or type(payload.get("seed")) is not int
        or payload.get("schema_version") != SCHEMA_VERSION
        or payload.get("seed") != SEED
    ):
        raise ArtifactError("schema_version or seed is unsupported")
    if set(payload) != {"schema_version", "seed", "initial_state", "steps"}:
        raise ArtifactError("replay envelope fields are incomplete or unsupported")
    initial = _state_from_payload(_mapping(payload["initial_state"], "initial_state"))
    steps = _list(payload["steps"], "steps")
    _validate_caps(payload, steps)
    current = initial
    transitions: list[dict[str, object]] = []
    previous_at: datetime | None = None
    for index, raw_step in enumerate(steps):
        step = _mapping(raw_step, f"steps[{index}]")
        if set(step) != {"phase", "at", "action"}:
            raise ArtifactError("step fields are incomplete or unsupported")
        before = _state_json(current)
        phase_value = step.get("phase")
        try:
            phase = _phase(phase_value)
        except ArtifactError:
            phase = cast(Phase, str(phase_value))
        at: datetime | None
        try:
            at = _timestamp(step.get("at"), "step.at")
        except ArtifactError:
            at = None
        monotonic_error = (
            at is not None and previous_at is not None and at < previous_at
        )
        if at is not None and not monotonic_error:
            previous_at = at
        if monotonic_error:
            result = _failed_result(
                current, "rejected", "step timestamps are not non-decreasing"
            )
            action_json = (
                step["action"]
                if isinstance(step["action"], Mapping)
                else step["action"]
            )
            after = before
        elif not isinstance(phase_value, str) or phase_value not in {
            "split",
            "accrual",
            "payment",
        }:
            result = _failed_result(current, "rejected", "step phase is unsupported")
            action_json = step["action"]
            after = before
        elif at is None:
            result = _failed_result(current, "rejected", "step timestamp is invalid")
            action_json = step["action"]
            after = before
        else:
            next_state, result, action_json = _step_result(
                current, phase, at, step["action"]
            )
            after = _state_json(next_state)
            current = next_state
        transitions.append(
            {
                "index": index,
                "phase": phase_value,
                "at": None if at is None else at.isoformat(),
                "input_at": step["at"],
                "action": action_json,
                "input_action": step["action"],
                "state_before": before,
                "state_after": after,
                "result": result,
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "seed": SEED,
        "coverage": "incomplete",
        "economic_status": "not-evaluated",
        "input": {
            "action": "read-only-offline-json",
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size_bytes": len(raw),
        },
        "initial_state": _state_json(initial),
        "transitions": transitions,
        "final_state": _state_json(current),
    }


def _check_path_components(path: Path, label: str) -> Path:
    absolute = path if path.is_absolute() else Path.cwd() / path
    current = absolute
    while True:
        if current.is_symlink():
            raise ArtifactError(f"{label} has a symlink path component")
        if current.parent == current:
            break
        current = current.parent
    return absolute


def _read_input(path: Path) -> bytes:
    absolute = _check_path_components(path, "input")
    if absolute.is_symlink() or not absolute.is_file():
        raise ArtifactError("input must be a regular file")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(absolute, flags)
    except OSError as exc:
        raise ArtifactError("input cannot be opened") from exc
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ArtifactError("input cannot be inspected")
        chunks: list[bytes] = []
        remaining = MAX_INPUT_BYTES + 1
        while remaining:
            chunk = os.read(descriptor, remaining)
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        data = b"".join(chunks)
    except OSError as exc:
        raise ArtifactError("input cannot be read") from exc
    finally:
        os.close(descriptor)
    if len(data) > MAX_INPUT_BYTES:
        raise ArtifactError("input exceeds 1MiB")
    return data


def _write_output(path: Path, data: bytes) -> None:
    absolute = _check_path_components(path, "output")
    if absolute.is_symlink() or absolute.exists():
        raise ArtifactError("output already exists")
    if len(data) > MAX_OUTPUT_BYTES:
        raise ArtifactError("output exceeds 50MiB")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(absolute, flags, 0o600)
    except OSError as exc:
        raise ArtifactError("output cannot be created") from exc
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
    except OSError as exc:
        try:
            absolute.unlink()
        except OSError:
            pass
        raise ArtifactError("output cannot be written") from exc


def write_artifact(input_path: Path, output_path: Path) -> None:
    """Read one bounded input and atomically create one new output file."""
    input_absolute = _check_path_components(input_path, "input")
    output_absolute = _check_path_components(output_path, "output")
    if output_absolute.exists() or output_absolute.is_symlink():
        raise ArtifactError("output already exists")
    try:
        if input_absolute.samefile(output_absolute):
            raise ArtifactError("input and output alias")
    except FileNotFoundError:
        pass
    raw = _read_input(input_absolute)
    decoded = _decode_json(raw)
    artifact = build_artifact(_mapping(decoded, "input"), input_bytes=raw)
    data = _canonical_json(artifact)
    _write_output(output_absolute, data)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    try:
        arguments = parser.parse_args(argv)
        write_artifact(arguments.input, arguments.output)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2
    except (ArtifactError, OSError, TypeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ArtifactError",
    "MAX_INPUT_BYTES",
    "MAX_OUTPUT_BYTES",
    "MAX_STEPS",
    "MAX_SYMBOLS",
    "MAX_UTC_DATES",
    "build_artifact",
    "main",
    "write_artifact",
]
