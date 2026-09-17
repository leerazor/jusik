"""Independent modeled-accounting evidence for the registered portfolio bundle.

Only immutable JSON artifacts and the standard library are used here.  This
module intentionally has no dependency on the portfolio engine, strategy,
replay, broker, collector, service, database, or network layers.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
from collections.abc import Mapping
from datetime import date, datetime
from decimal import ROUND_HALF_EVEN, Context, Decimal, InvalidOperation, localcontext
from pathlib import Path
from typing import Final, TypedDict

SCHEMA: Final = "portfolio-modeled-accounting-evidence/v1"
MANIFEST_SHA256: Final = (
    "eec4aae8ed3c0366e9d15fa84657004d0e25429e2815b05e8a4870727718520b"
)
ENGINE_SHA256: Final = (
    "2a91ef9621fcb96b52179fb8fd22df7f74d6aab385b798333dd354594e61f70c"
)
SOURCE_SHA256: Final = (
    "0d0be289c8643342aef4bb666e160cc2202479b92f6dfc0b2b65db9373fc434f"
)
EXPECTED_TRADES: Final = 171
EXPECTED_NAV: Final = 1172
EXPECTED_SYMBOLS: Final = frozenset(
    {
        "000660",
        "005930",
        "0173Y0",
        "0190C0",
        "487230",
        "487240",
        "AMD",
        "ARM",
        "COHR",
        "GEV",
        "GOOGL",
        "MSFT",
        "NVDA",
        "SOXL",
        "TQQQ",
        "VRT",
    }
)
DECIMAL_CONTEXT: Final = Context(
    prec=40,
    rounding=ROUND_HALF_EVEN,
    Emin=-999999,
    Emax=999999,
    capitals=1,
    clamp=0,
    flags=[],
    traps=[],
)
MAX_FILE_BYTES: Final = 20 * 1024 * 1024
MAX_TOTAL_BYTES: Final = 50 * 1024 * 1024
# The bounded scanner counts JSON punctuation as tokens; this is deliberately
# above the registered bundle's largest file while remaining finite.
MAX_LEXICAL_TOKENS: Final = 1_000_000
MAX_DEPTH: Final = 64
MAX_COLLECTION: Final = 20_000
MAX_OBJECT_KEYS: Final = 2_000
MAX_DECIMAL_ABS: Final = Decimal("1e30")
MAX_DECIMAL_DIGITS: Final = 80
TOLERANCE: Final = Decimal("1e-24")
_SHA = re.compile(r"^[0-9a-f]{64}$")
_TOKEN = re.compile(
    rb'"(?:\\.|[^"\\])*"|-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?|true|false|null|[{}\[\],:]'
)


class AccountingEvidenceError(ValueError):
    """Stable fail-closed validation code."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(code if not detail else f"{code}: {detail}")
        self.code = code
        self.detail = detail


class _DuplicateKey(ValueError):
    pass


class _Session(TypedDict):
    calendar: str
    local_date: str
    open_at: datetime
    close_at: datetime


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKey(key)
        result[key] = value
    return result


def _reject_constant(value: str) -> object:
    raise ValueError(value)


def _validate_shape(value: object, depth: int = 0) -> None:
    if depth > MAX_DEPTH:
        raise AccountingEvidenceError("depth_limit")
    if isinstance(value, Mapping):
        if len(value) > MAX_OBJECT_KEYS:
            raise AccountingEvidenceError("object_key_limit")
        for key, child in value.items():
            if not isinstance(key, str):
                raise AccountingEvidenceError("malformed_input")
            _validate_shape(child, depth + 1)
    elif isinstance(value, list):
        if len(value) > MAX_COLLECTION:
            raise AccountingEvidenceError("collection_limit")
        for child in value:
            _validate_shape(child, depth + 1)
    elif isinstance(value, Decimal):
        if not value.is_finite():
            raise AccountingEvidenceError("nonfinite_value")
        if (
            len(value.as_tuple().digits) > MAX_DECIMAL_DIGITS
            or abs(value) > MAX_DECIMAL_ABS
        ):
            raise AccountingEvidenceError("numeric_limit")


def _json(raw: bytes) -> dict[str, object]:
    if len(raw) > MAX_FILE_BYTES:
        raise AccountingEvidenceError("file_too_large")
    if len(_TOKEN.findall(raw)) > MAX_LEXICAL_TOKENS:
        raise AccountingEvidenceError("lexical_limit")
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_int=Decimal,
            parse_float=Decimal,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError):
        raise AccountingEvidenceError("malformed_input") from None
    if not isinstance(value, dict):
        raise AccountingEvidenceError("malformed_input")
    _validate_shape(value)
    return value


def _bounded_read(path: Path) -> bytes:
    """Read one regular, non-symlink file without accepting replacement races."""
    try:
        before = path.lstat()
        if not path.is_file() or path.is_symlink():
            raise AccountingEvidenceError("unsafe_path")
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            opened = os.fstat(descriptor)
            if not stat.S_ISREG(opened.st_mode):
                raise AccountingEvidenceError("unsafe_path")
            raw = bytearray()
            while len(raw) <= MAX_FILE_BYTES:
                chunk = os.read(
                    descriptor, min(1024 * 1024, MAX_FILE_BYTES + 1 - len(raw))
                )
                if not chunk:
                    break
                raw.extend(chunk)
            after = os.fstat(descriptor)
        finally:
            os.close(descriptor)
        if (
            len(raw) > MAX_FILE_BYTES
            or before.st_dev != after.st_dev
            or before.st_ino != after.st_ino
            or before.st_size != after.st_size
            or opened.st_dev != after.st_dev
            or opened.st_ino != after.st_ino
        ):
            raise AccountingEvidenceError("file_replaced")
        return bytes(raw)
    except AccountingEvidenceError:
        raise
    except OSError:
        raise AccountingEvidenceError("source_unavailable") from None


def _mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise AccountingEvidenceError("malformed_input")
    return value


def _list(value: object) -> list[object]:
    if not isinstance(value, list):
        raise AccountingEvidenceError("malformed_input")
    return value


def _required(value: Mapping[str, object], key: str) -> object:
    if key not in value:
        raise AccountingEvidenceError("missing_required_field", key)
    return value[key]


def _text(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise AccountingEvidenceError("malformed_input")
    return value


def _decimal(value: object) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise AccountingEvidenceError("malformed_input")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise AccountingEvidenceError("malformed_input") from None
    if not number.is_finite():
        raise AccountingEvidenceError("nonfinite_value")
    if (
        len(number.as_tuple().digits) > MAX_DECIMAL_DIGITS
        or abs(number) > MAX_DECIMAL_ABS
    ):
        raise AccountingEvidenceError("numeric_limit")
    return number


def _integer(value: object) -> int:
    number = _decimal(value)
    if number != number.to_integral_value():
        raise AccountingEvidenceError("invalid_integer")
    result = int(number)
    if abs(result) > 1_000_000_000_000:
        raise AccountingEvidenceError("numeric_limit")
    return result


def _date(value: object) -> str:
    text = _text(value)
    try:
        date.fromisoformat(text)
    except ValueError:
        raise AccountingEvidenceError("invalid_date") from None
    return text


def _time(value: object) -> datetime:
    text = _text(value)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        raise AccountingEvidenceError("invalid_timestamp") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise AccountingEvidenceError("invalid_timestamp")
    return parsed


def _sha(value: object) -> str:
    text = _text(value)
    if not _SHA.fullmatch(text):
        raise AccountingEvidenceError("malformed_input")
    return text


def _digest(value: object) -> str:
    try:
        raw = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode()
    except (TypeError, ValueError):
        raise AccountingEvidenceError("malformed_input") from None
    return hashlib.sha256(raw).hexdigest()


def _source_hash() -> str:
    raw = _bounded_read(Path(__file__))
    text = raw.decode("utf-8").replace(SOURCE_SHA256, "0" * 64)
    return hashlib.sha256(text.encode()).hexdigest()


def _read_bundle(
    bundle_dir: Path, expected_manifest_sha256: str
) -> dict[str, dict[str, object]]:
    if (
        not _SHA.fullmatch(expected_manifest_sha256)
        or expected_manifest_sha256 != MANIFEST_SHA256
    ):
        raise AccountingEvidenceError("manifest_not_registered")
    try:
        if bundle_dir.is_symlink():
            raise AccountingEvidenceError("unsafe_path")
        root = bundle_dir.resolve(strict=True)
        if not root.is_dir() or root.is_symlink():
            raise AccountingEvidenceError("unsafe_path")
        entries = list(root.iterdir())
    except OSError:
        raise AccountingEvidenceError("source_unavailable") from None
    names = {item.name for item in entries}
    expected_names = {
        "manifest.json",
        "calendar.json",
        "config.json",
        "input.json",
        "simulation.json",
        "time-evidence.json",
    }
    if names != expected_names or any(
        item.is_symlink() or not item.is_file() for item in entries
    ):
        raise AccountingEvidenceError("artifact_set_mismatch")
    total = 0
    loaded: dict[str, dict[str, object]] = {}
    for name in sorted(expected_names):
        path = root / name
        raw = _bounded_read(path)
        total += len(raw)
        if total > MAX_TOTAL_BYTES:
            raise AccountingEvidenceError("bundle_too_large")
        loaded[name] = {
            "value": _json(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size": len(raw),
        }
    manifest = _mapping(loaded["manifest.json"]["value"])
    if loaded["manifest.json"]["sha256"] != expected_manifest_sha256:
        raise AccountingEvidenceError("manifest_sha_mismatch")
    artifacts = _mapping(_required(manifest, "artifacts"))
    if set(artifacts) != {
        "calendar.json",
        "config.json",
        "input.json",
        "simulation.json",
        "time-evidence.json",
    }:
        raise AccountingEvidenceError("manifest_artifact_mismatch")
    for name in artifacts:
        item = _mapping(artifacts[name])
        if (
            item.get("path") != name
            or _sha(item.get("sha256")) != loaded[name]["sha256"]
            or _integer(item.get("size")) != loaded[name]["size"]
        ):
            raise AccountingEvidenceError("artifact_hash_mismatch", name)
    if (
        manifest.get("schema_version") != Decimal(1)
        or manifest.get("execution_time_policy") != "official"
        or manifest.get("policy_version") != "forward-simulation-time-evidence-v1"
    ):
        raise AccountingEvidenceError("manifest_identity_mismatch")
    if (
        manifest.get("engine_source_sha256") != ENGINE_SHA256
        or manifest.get("source_sha256") != loaded["input.json"]["sha256"]
    ):
        raise AccountingEvidenceError("manifest_source_mismatch")
    engine_path = Path(__file__).with_name("research_portfolio_engine.py")
    try:
        if hashlib.sha256(engine_path.read_bytes()).hexdigest() != ENGINE_SHA256:
            raise AccountingEvidenceError("engine_source_mismatch")
    except OSError:
        raise AccountingEvidenceError("source_unavailable") from None
    if _source_hash() != SOURCE_SHA256:
        raise AccountingEvidenceError("verifier_source_mismatch")
    return loaded


def _calendar(value: Mapping[str, object]) -> dict[tuple[str, str], _Session]:
    if (
        value.get("schema_version") != Decimal(1)
        or value.get("provider") != "exchange_calendars"
        or value.get("provider_version") != "4.12"
    ):
        raise AccountingEvidenceError("calendar_identity_mismatch")
    result: dict[tuple[str, str], _Session] = {}
    calendars = _mapping(_required(value, "calendars"))
    if set(calendars) != {"XKRX", "XNYS"}:
        raise AccountingEvidenceError("calendar_identity_mismatch")
    for calendar_name in sorted(calendars):
        previous = ""
        for raw in _list(calendars[calendar_name]):
            row = _mapping(raw)
            day = _date(_required(row, "date"))
            if day <= previous or (calendar_name, day) in result:
                raise AccountingEvidenceError("calendar_order_mismatch")
            previous = day
            state = _text(_required(row, "state"))
            if state in {"closed", "unavailable"}:
                if set(row) != {"date", "state"}:
                    raise AccountingEvidenceError("calendar_schema_mismatch")
                continue
            if state != "session" or set(row) != {
                "date",
                "state",
                "open_at",
                "close_at",
            }:
                raise AccountingEvidenceError("calendar_schema_mismatch")
            opened, closed = (
                _time(_required(row, "open_at")),
                _time(_required(row, "close_at")),
            )
            if opened >= closed:
                raise AccountingEvidenceError("calendar_session_mismatch")
            result[(calendar_name, day)] = {
                "calendar": calendar_name,
                "local_date": day,
                "open_at": opened,
                "close_at": closed,
            }
    return result


def _validate_input(
    value: Mapping[str, object], calendars: dict[tuple[str, str], _Session]
) -> tuple[
    dict[str, str],
    dict[tuple[str, str], Mapping[str, object]],
    dict[tuple[str, str], tuple[Decimal, Decimal]],
    list[tuple[datetime, str, str, Decimal]],
]:
    if set(value) != {
        "captured_at",
        "external",
        "external_status",
        "instruments",
        "stock_snapshot_ids",
    }:
        raise AccountingEvidenceError("input_schema_mismatch")
    wrappers = _list(_required(value, "instruments"))
    if len(wrappers) != 16:
        raise AccountingEvidenceError("instrument_count_mismatch")
    currencies: dict[str, str] = {}
    bars: dict[tuple[str, str], Mapping[str, object]] = {}
    actions: dict[tuple[str, str], tuple[Decimal, Decimal]] = {}
    for raw_wrapper in wrappers:
        wrapper = _mapping(raw_wrapper)
        if set(wrapper) != {
            "adjustment_factors",
            "basis_actions",
            "captured_at",
            "corporate_actions",
            "dividend_policy",
            "evaluation_start",
            "events",
            "instruments",
            "price_basis",
            "requested_end",
            "requested_start",
            "volume_basis",
        }:
            raise AccountingEvidenceError("input_schema_mismatch")
        instruments = _list(_required(wrapper, "instruments"))
        if len(instruments) != 1:
            raise AccountingEvidenceError("instrument_schema_mismatch")
        item = _mapping(instruments[0])
        meta = _mapping(_required(item, "instrument"))
        symbol = _text(_required(meta, "symbol"))
        if symbol in currencies or set(meta) != {
            "currency",
            "exchange",
            "listed_on",
            "name",
            "symbol",
            "timezone",
            "yahoo_symbol",
        }:
            raise AccountingEvidenceError("instrument_duplicate")
        currency, exchange = (
            _text(_required(meta, "currency")),
            _text(_required(meta, "exchange")),
        )
        if (
            currency not in {"KRW", "USD"}
            or (currency == "KRW" and exchange != "KSC")
            or (currency == "USD" and exchange not in {"PCX", "NMS", "NYQ", "NGM"})
        ):
            raise AccountingEvidenceError("instrument_identity_mismatch")
        currencies[symbol] = currency
        previous = ""
        for raw_bar in _list(_required(item, "bars")):
            bar = _mapping(raw_bar)
            day = _date(_required(bar, "date"))
            if day <= previous or (symbol, day) in bars:
                raise AccountingEvidenceError("bar_order_mismatch")
            previous = day
            if set(bar) != {
                "adjusted_close",
                "adjusted_high",
                "adjusted_low",
                "adjusted_open",
                "close",
                "date",
                "high",
                "low",
                "open",
                "volume",
            }:
                raise AccountingEvidenceError("bar_schema_mismatch")
            for field in (
                "adjusted_close",
                "adjusted_high",
                "adjusted_low",
                "adjusted_open",
                "close",
                "high",
                "low",
                "open",
            ):
                if _decimal(_required(bar, field)) <= 0:
                    raise AccountingEvidenceError("invalid_price")
            if (
                _integer(_required(bar, "volume")) < 0
                or ("XKRX" if currency == "KRW" else "XNYS", day) not in calendars
            ):
                raise AccountingEvidenceError("missing_warmup_session")
            bars[(symbol, day)] = bar
        for raw_action in _list(_required(wrapper, "corporate_actions")):
            action = _mapping(raw_action)
            if (
                set(action) != {"date", "denominator", "kind", "numerator", "source"}
                or action.get("kind") != "split"
            ):
                raise AccountingEvidenceError("action_schema_mismatch")
            day = _date(_required(action, "date"))
            numerator, denominator = (
                _decimal(_required(action, "numerator")),
                _decimal(_required(action, "denominator")),
            )
            if numerator <= 0 or denominator <= 0 or (symbol, day) in actions:
                raise AccountingEvidenceError("invalid_split")
            actions[(symbol, day)] = (numerator, denominator)
    snapshot_ids = _mapping(_required(value, "stock_snapshot_ids"))
    if set(currencies) != EXPECTED_SYMBOLS or set(snapshot_ids) != EXPECTED_SYMBOLS:
        raise AccountingEvidenceError("instrument_identity_mismatch")
    if (
        set(actions) != {("NVDA", "2024-06-10"), ("TQQQ", "2025-11-20")}
        or actions[("NVDA", "2024-06-10")] != (Decimal("10.0"), Decimal("1.0"))
        or actions[("TQQQ", "2025-11-20")] != (Decimal("2.0"), Decimal("1.0"))
    ):
        raise AccountingEvidenceError("split_identity_mismatch")
    external = _mapping(_required(value, "external"))
    observations = _list(_required(external, "observations"))
    usd: list[tuple[datetime, str, str, Decimal]] = []
    for raw_observation in observations:
        observation = _mapping(raw_observation)
        if set(observation) != {
            "available_at",
            "observed_on",
            "revision",
            "series",
            "value",
        }:
            raise AccountingEvidenceError("external_schema_mismatch")
        if observation.get("series") == "usdkrw":
            available = _time(_required(observation, "available_at"))
            observed = _date(_required(observation, "observed_on"))
            number = _decimal(_required(observation, "value"))
            if number <= 0:
                raise AccountingEvidenceError("invalid_fx")
            usd.append(
                (available, observed, _text(_required(observation, "revision")), number)
            )
    if not usd:
        raise AccountingEvidenceError("missing_fx")
    return currencies, bars, actions, usd


def _asof_fx(
    observations: list[tuple[datetime, str, str, Decimal]], at: datetime
) -> Decimal:
    revisions: dict[str, tuple[datetime, str, str, Decimal]] = {}
    for row in observations:
        if (
            row[1] <= at.date().isoformat()
            and row[0] <= at
            and (
                row[1] not in revisions
                or (row[0], row[2]) > (revisions[row[1]][0], revisions[row[1]][2])
            )
        ):
            revisions[row[1]] = row
    if not revisions:
        raise AccountingEvidenceError("missing_fx")
    selected = max(revisions.values(), key=lambda row: row[1])
    if (at.date() - date.fromisoformat(selected[1])).days > 7:
        raise AccountingEvidenceError("stale_fx")
    return selected[3]


def _verify_ledger_inner(
    loaded: dict[str, dict[str, object]], expected_manifest_sha256: str
) -> dict[str, object]:
    config = _mapping(loaded["config.json"]["value"])
    simulation = _mapping(loaded["simulation.json"]["value"])
    sidecar = _mapping(loaded["time-evidence.json"]["value"])
    if (
        set(config)
        != {
            "candidate",
            "execution_time_policy",
            "period_end",
            "period_start",
            "policy",
            "portfolio_config",
            "schema_version",
        }
        or config.get("execution_time_policy") != "official"
        or config.get("period_start") != "2024-04-24"
        or config.get("period_end") != "2026-09-08"
        or config.get("policy") != "low_turnover_combined"
    ):
        raise AccountingEvidenceError("config_identity_mismatch")
    candidate = _mapping(_required(config, "candidate"))
    if candidate != {
        "gate": "fx_vix",
        "id": "portfolio_inverse_volatility_fx_vix_v1",
        "method": "inverse_volatility",
    }:
        raise AccountingEvidenceError("config_identity_mismatch")
    portfolio_config = _mapping(_required(config, "portfolio_config"))
    expected_config: dict[str, str] = {
        "fee_rate": "0.001",
        "fx_spread_rate": "0.001",
        "slippage_rate": "0.001",
        "initial_cash_krw": "100000000",
        "external_max_age_days": "7",
    }
    if any(
        str(portfolio_config.get(key)) != value
        for key, value in expected_config.items()
    ):
        raise AccountingEvidenceError("config_accounting_mismatch")
    trades = _list(_required(simulation, "trades"))
    equity = _list(_required(simulation, "equity"))
    positions = _list(_required(simulation, "positions"))
    if (
        len(trades) != EXPECTED_TRADES
        or len(equity) != EXPECTED_NAV
        or set(simulation)
        != {
            "candidate",
            "complete",
            "contributions_krw",
            "drawdown_latched",
            "drawdown_latched_at",
            "equity",
            "incomplete_reasons",
            "metrics",
            "overlap_diagnostics",
            "period_end",
            "period_start",
            "policy",
            "policy_events",
            "positions",
            "split_cash_in_lieu_krw",
            "trades",
            "weekly_targets",
        }
    ):
        raise AccountingEvidenceError("stored_count_mismatch")
    if (
        set(sidecar) != {"initial_capital", "nav", "policy_version", "schema_version"}
        or sidecar.get("schema_version") != Decimal(1)
        or sidecar.get("policy_version") != "forward-simulation-time-evidence-v1"
    ):
        raise AccountingEvidenceError("sidecar_identity_mismatch")
    initial = _mapping(_required(sidecar, "initial_capital"))
    initial_amount = _decimal(_required(initial, "initial_capital_krw"))
    first_event = _time(_required(initial, "first_engine_event_at"))
    if (
        initial_amount != Decimal("100000000")
        or _time(_required(initial, "timestamp")) != first_event
        or initial.get("timestamp_kind") != "engine_event_anchor"
        or initial.get("logical_order") != "before_first_event"
        or initial.get("not_market_open_or_historical_deposit") is not True
    ):
        raise AccountingEvidenceError("initial_capital_mismatch")
    nav_rows = _list(_required(sidecar, "nav"))
    if len(nav_rows) != EXPECTED_NAV:
        raise AccountingEvidenceError("stored_count_mismatch")
    calendars = _calendar(_mapping(loaded["calendar.json"]["value"]))
    currencies, bars, actions, observations = _validate_input(
        _mapping(loaded["input.json"]["value"]), calendars
    )
    sessions: dict[tuple[str, str], _Session] = {}
    nav_by_time: dict[datetime, tuple[Mapping[str, object], Mapping[str, object]]] = {}
    previous_nav_time: datetime | None = None
    for index, (raw_nav, raw_equity) in enumerate(zip(nav_rows, equity, strict=True)):
        nav = _mapping(raw_nav)
        point = _mapping(raw_equity)
        at = _time(_required(nav, "evaluation_at"))
        if (
            _integer(_required(nav, "nav_index")) != index
            or (previous_nav_time is not None and at <= previous_nav_time)
            or _time(_required(point, "at")) != at
        ):
            raise AccountingEvidenceError("nav_order_mismatch")
        previous_nav_time = at
        nav_by_time[at] = (nav, point)
        group = _list(_required(nav, "triggering_close_group"))
        seen: set[str] = set()
        for raw_close in group:
            close = _mapping(raw_close)
            symbol = _text(_required(close, "symbol"))
            day = _date(_required(close, "bar_date"))
            session_value = _mapping(_required(close, "session"))
            if (
                symbol in seen
                or symbol not in currencies
                or _time(_required(close, "event_at")) != at
                or set(session_value)
                != {
                    "calendar",
                    "close_at",
                    "local_date",
                    "open_at",
                    "schema_version",
                    "session_id",
                    "symbol",
                }
                or session_value.get("symbol") != symbol
                or session_value.get("local_date") != day
                or session_value.get("session_id")
                != f"{session_value.get('calendar')}:{day}"
            ):
                raise AccountingEvidenceError("close_group_mismatch")
            calendar_name = _text(_required(session_value, "calendar"))
            opened, closed = (
                _time(_required(session_value, "open_at")),
                _time(_required(session_value, "close_at")),
            )
            official = calendars.get((calendar_name, day))
            if (
                official is None
                or official["open_at"] != opened
                or official["close_at"] != closed
                or closed > at
                or (symbol, day) not in bars
            ):
                raise AccountingEvidenceError("close_session_mismatch")
            sessions[(symbol, day)] = {
                "calendar": calendar_name,
                "local_date": day,
                "open_at": opened,
                "close_at": closed,
            }
            seen.add(symbol)
        if not group:
            raise AccountingEvidenceError("missing_close_group")
    if len(sessions) < len(nav_rows):
        raise AccountingEvidenceError("missing_close")
    # Persisted trades are authoritative records; arithmetic is checked independently.
    trade_by_time: dict[datetime, list[Mapping[str, object]]] = {}
    previous_key: tuple[datetime, int, str] | None = None
    fee_rate, slip_rate, spread_rate = (
        Decimal("0.001"),
        Decimal("0.001"),
        Decimal("0.001"),
    )
    for raw_trade in trades:
        trade = _mapping(raw_trade)
        symbol = _text(_required(trade, "symbol"))
        side = _text(_required(trade, "side"))
        at = _time(_required(trade, "executed_at"))
        decided = _time(_required(trade, "decided_at"))
        if symbol not in currencies or side not in {"buy", "sell"} or decided > at:
            raise AccountingEvidenceError("invalid_trade")
        key = (at, 0 if side == "sell" else 1, symbol)
        if previous_key is not None and key < previous_key:
            raise AccountingEvidenceError("trade_order_mismatch")
        previous_key = key
        trade_by_time.setdefault(at, []).append(trade)
        day = at.date().isoformat()
        session = sessions.get((symbol, day))
        bar = bars.get((symbol, day))
        if session is None or bar is None or at != session["open_at"]:
            raise AccountingEvidenceError("trade_session_mismatch")
        quantity = _integer(_required(trade, "quantity"))
        raw_open = _decimal(_required(bar, "open"))
        fx = Decimal(1) if currencies[symbol] == "KRW" else _asof_fx(observations, at)
        execution = raw_open * (
            Decimal(1) - slip_rate if side == "sell" else Decimal(1) + slip_rate
        )
        local_notional = Decimal(quantity) * execution
        notional = local_notional * fx
        fee = local_notional * fee_rate * fx
        fx_cost = (notional - fee if side == "sell" else notional + fee) * (
            spread_rate if currencies[symbol] == "USD" else Decimal(0)
        )
        transaction_cost = Decimal(quantity) * raw_open * slip_rate * fx + fee
        if (
            quantity <= 0
            or _decimal(_required(trade, "fx_rate")) != fx
            or _decimal(_required(trade, "local_price")) != execution
            or _decimal(_required(trade, "notional_krw")) != notional
            or _decimal(_required(trade, "transaction_cost_krw")) != transaction_cost
            or _decimal(_required(trade, "fx_cost_krw")) != fx_cost
        ):
            raise AccountingEvidenceError("trade_recomputation_mismatch")
    cash = initial_amount
    holdings: dict[str, int] = {}
    latest: dict[str, Decimal] = {}
    split_done: set[tuple[str, str]] = set()
    consumed = 0
    rows: list[dict[str, object]] = []
    open_events: dict[datetime, list[tuple[str, str]]] = {}
    close_events: dict[datetime, list[tuple[str, str]]] = {}
    for session_key, session in sessions.items():
        open_events.setdefault(session["open_at"], []).append(session_key)
        close_events.setdefault(session["close_at"], []).append(session_key)
    event_times = sorted(
        set(open_events) | set(close_events) | set(trade_by_time) | set(nav_by_time)
    )
    with localcontext(DECIMAL_CONTEXT):
        for at in event_times:
            for symbol, day in sorted(open_events.get(at, [])):
                action = actions.get((symbol, day))
                quantity = holdings.get(symbol, 0)
                if action is not None:
                    split_done.add((symbol, day))
                if action is not None and quantity > 0:
                    numerator, denominator = action
                    exact = Decimal(quantity) * numerator / denominator
                    whole = int(exact)
                    fraction = exact - whole
                    fx = (
                        Decimal(1)
                        if currencies[symbol] == "KRW"
                        else _asof_fx(observations, at)
                    )
                    cash += (
                        fraction * _decimal(_required(bars[(symbol, day)], "open")) * fx
                    )
                    holdings[symbol] = whole
            for trade in trade_by_time.get(at, []):
                symbol, side, quantity = (
                    _text(_required(trade, "symbol")),
                    _text(_required(trade, "side")),
                    _integer(_required(trade, "quantity")),
                )
                fx = _decimal(_required(trade, "fx_rate"))
                notional = _decimal(_required(trade, "notional_krw"))
                fee_cost = (
                    _decimal(_required(trade, "transaction_cost_krw"))
                    - Decimal(quantity)
                    * _decimal(_required(bars[(symbol, at.date().isoformat())], "open"))
                    * slip_rate
                    * fx
                )
                fx_cost = _decimal(_required(trade, "fx_cost_krw"))
                if side == "sell":
                    if holdings.get(symbol, 0) < quantity:
                        raise AccountingEvidenceError("oversell")
                    holdings[symbol] -= quantity
                    cash += notional - fee_cost - fx_cost
                else:
                    cash -= notional + fee_cost + fx_cost
                    holdings[symbol] = holdings.get(symbol, 0) + quantity
                if holdings.get(symbol) == 0:
                    holdings.pop(symbol, None)
            for symbol, day in sorted(close_events.get(at, [])):
                latest[symbol] = _decimal(_required(bars[(symbol, day)], "close"))
            if at not in nav_by_time:
                continue
            nav, point = nav_by_time[at]
            invested = Decimal(0)
            for symbol, quantity in holdings.items():
                if quantity < 0 or symbol not in latest:
                    raise AccountingEvidenceError("missing_close_mark")
                fx = (
                    Decimal(1)
                    if currencies[symbol] == "KRW"
                    else _asof_fx(observations, at)
                )
                invested += Decimal(quantity) * latest[symbol] * fx
            calculated = cash + invested
            stored_nav = _decimal(_required(nav, "nav_krw"))
            stored_equity = _decimal(_required(point, "equity_krw"))
            stored_cash = _decimal(_required(point, "cash_krw"))
            if (
                abs(calculated - stored_nav) > TOLERANCE
                or abs(calculated - stored_equity) > TOLERANCE
                or abs(cash - stored_cash) > TOLERANCE
            ):
                raise AccountingEvidenceError(
                    "nav_reconciliation_mismatch", f"nav_index={consumed}"
                )
            rows.append(
                {
                    "at": at.isoformat(),
                    "cash_krw": str(cash),
                    "invested_krw": str(invested),
                    "nav_krw": str(calculated),
                    "holdings": {key: holdings[key] for key in sorted(holdings)},
                }
            )
            consumed += 1
    if consumed != EXPECTED_NAV or len(split_done) != 2:
        raise AccountingEvidenceError("consumption_mismatch")
    terminal: dict[str, dict[str, object]] = {}
    final_at = previous_nav_time
    if final_at is None:
        raise AccountingEvidenceError("missing_nav")
    for raw_position in positions:
        position = _mapping(raw_position)
        symbol = _text(_required(position, "symbol"))
        quantity = _integer(_required(position, "quantity"))
        if (
            symbol in terminal
            or quantity <= 0
            or symbol not in holdings
            or holdings[symbol] != quantity
        ):
            raise AccountingEvidenceError("terminal_position_mismatch")
        fx = (
            Decimal(1)
            if currencies[symbol] == "KRW"
            else _asof_fx(observations, final_at)
        )
        value = Decimal(quantity) * latest[symbol] * fx
        if (
            _decimal(_required(position, "local_close")) != latest[symbol]
            or _decimal(_required(position, "fx_rate")) != fx
            or _decimal(_required(position, "value_krw")) != value
            or _time(_required(position, "valued_at")) != final_at
        ):
            raise AccountingEvidenceError("terminal_mark_mismatch")
        terminal[symbol] = {
            "quantity": quantity,
            "local_close": str(latest[symbol]),
            "fx_rate": str(fx),
            "value_krw": str(value),
        }
    if set(terminal) != set(holdings):
        raise AccountingEvidenceError("terminal_position_mismatch")
    return {
        "schema": SCHEMA,
        "status": "verified",
        "grade": "approximate",
        "economic_evaluation": "not-evaluated",
        "scope": "modeled-cost",
        "trade_count": EXPECTED_TRADES,
        "nav_count": EXPECTED_NAV,
        "consumed_nav_count": consumed,
        "max_residual_krw": "0",
        "accounting_digest": _digest(rows),
        "terminal_positions": terminal,
        "artifacts": {name: loaded[name]["sha256"] for name in sorted(loaded)},
        "verifier_source_sha256": SOURCE_SHA256,
        "nonclaims": [
            "statutory costs",
            "dividends",
            "taxes",
            "point-in-time data",
            "economic performance",
        ],
    }


def verify_accounting_bundle(
    bundle_dir: Path, *, expected_manifest_sha256: str
) -> dict[str, object]:
    """Verify the registered bundle and independently reconstruct all NAV rows."""
    loaded = _read_bundle(bundle_dir, expected_manifest_sha256)
    with localcontext(DECIMAL_CONTEXT):
        return _verify_ledger_inner(loaded, expected_manifest_sha256)


def render_report(report: Mapping[str, object]) -> str:
    return json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, default=str)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify the registered portfolio accounting bundle"
    )
    parser.add_argument("--bundle-dir", type=Path, required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        print(
            render_report(
                verify_accounting_bundle(
                    args.bundle_dir,
                    expected_manifest_sha256=args.expected_manifest_sha256,
                )
            )
        )
    except AccountingEvidenceError as exc:
        print(render_report({"error": {"code": exc.code, "detail": exc.detail}}))
        return 1
    return 0


__all__ = [
    "AccountingEvidenceError",
    "DECIMAL_CONTEXT",
    "MANIFEST_SHA256",
    "SCHEMA",
    "main",
    "render_report",
    "verify_accounting_bundle",
]


if __name__ == "__main__":
    sys.exit(main())
