"""Independent evidence verifier for the frozen R0 US modeled-cost run.

This module deliberately uses only the standard library.  It reads immutable
JSON artifacts, validates their hash chain, and reconstructs the saved ledger;
it never imports strategy, replay, collector, broker, or service code.
Persisted trades have no unique identifiers; the verifier therefore proves
ordered record count and accounting replacement checks, not identity beyond
the serialized fields.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Mapping
from datetime import date
from decimal import ROUND_HALF_EVEN, Context, Decimal, InvalidOperation, localcontext
from pathlib import Path
from typing import Final

SCHEMA: Final = "r0-us-modeled-cost-evidence/v1"
CANONICAL_MANIFEST_SHA256: Final = (
    "03ff5a140138277d2161a0896c7c8aefd64abe0545de7cc33ed9270882481205"
)
CANONICAL_RUN_SHA256: Final = (
    "cc9150f8b77a27ffd6b001449c0475933ff744a37011801923f87cbdc5558275"
)
CANONICAL_DATASET_SHA256: Final = (
    "e58e69fc19fd89589e5cd5d55a43259f1ad28c9b9f0a87c75dd7617f28906aea"
)
CANONICAL_CACHE_MANIFEST_SHA256: Final = (
    "a806c1ac0058901bbbca007aa91c8f8a3c56bc397c37452025babe82d6260d14"
)
CANONICAL_COMPLETION_SHA256: Final = (
    "16f209fb9ea5ed533e347fd17d85a2f0e37a6e7bfe8cb60df1af8908159a0156"
)
# These are canonicalized hashes: the two registered hash literals are
# replaced with zeroes before hashing this source, avoiding self-reference.
VERIFIER_SOURCE_SHA256: Final = (
    "df05cdd4d9cbbc5620549357d043ff4d0a146c73de03f6decb7ecb676ae5c652"
)
CANONICAL_EVIDENCE_SHA256: Final = (
    "6f53848cefc0935f7112fa2c518606aa6e41485404456910272ef3a9511484d6"
)

CANONICAL_AUDIT_ROOT: Final = (
    Path.home() / ".local" / "share" / "jusik" / "portfolio-audit"
)
CANONICAL_RUN_PATH: Final = (
    CANONICAL_AUDIT_ROOT
    / "20260915-market-data-live-contract-fixes/us-web-pilot-run.json"
)
CANONICAL_DATASET_PATH: Final = (
    CANONICAL_AUDIT_ROOT
    / "20260915-market-data-live-contract-fixes/us-pilot-1y-stable.json"
)
CANONICAL_CACHE_DIR: Final = (
    CANONICAL_AUDIT_ROOT
    / "20260915-market-data-live-contract-fixes/us-pilot-1y-stable-cache"
)
CANONICAL_MANIFEST_PATH: Final = (
    CANONICAL_AUDIT_ROOT
    / "20260915-r0-baseline/r0-baseline-freeze/baseline-manifest.json"
)
CANONICAL_EVIDENCE_PATH: Final = (
    Path(__file__).with_name("data") / "r0_us_cost_inclusion_evidence_v1.json"
)

DECIMAL_CONTEXT: Final = Context(
    prec=28,
    rounding=ROUND_HALF_EVEN,
    Emin=-999999,
    Emax=999999,
    capitals=1,
    clamp=0,
    flags=[],
    traps=[],
)
EXPECTED_TRADE_COUNT: Final = 106
EXPECTED_SESSION_COUNT: Final = 252
EXPECTED_CACHE_ENTRY_COUNT: Final = 84
MAX_SOURCE_BYTES: Final = 12 * 1024 * 1024
MAX_CACHE_BYTES: Final = 2 * 1024 * 1024
MAX_MANIFEST_BYTES: Final = 1 * 1024 * 1024
MAX_DATASET_BYTES: Final = 10 * 1024 * 1024
MAX_EVIDENCE_BYTES: Final = 1 * 1024 * 1024
MAX_CACHE_RAW_BYTES: Final = 2 * 1024 * 1024
MAX_VERIFIER_SOURCE_BYTES: Final = 1 * 1024 * 1024
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_KEY = re.compile(r"^[0-9a-f]{64}$")


class CostEvidenceError(ValueError):
    """Stable fail-closed error code for evidence validation."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class _DuplicateKey(ValueError):
    pass


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKey
        result[key] = value
    return result


def _nonfinite(value: str) -> Decimal:
    raise ValueError(value)


def _json(raw: bytes, *, limit: int) -> dict[str, object]:
    if len(raw) > limit:
        raise CostEvidenceError("source_too_large")
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_int=Decimal,
            parse_float=Decimal,
            parse_constant=_nonfinite,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError):
        raise CostEvidenceError("malformed_input") from None
    if not isinstance(value, dict):
        raise CostEvidenceError("malformed_input")
    return value


def _mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise CostEvidenceError("malformed_input")
    return value


def _list(value: object) -> list[object]:
    if not isinstance(value, list):
        raise CostEvidenceError("malformed_input")
    return value


def _required(value: Mapping[str, object], key: str) -> object:
    if key not in value:
        raise CostEvidenceError("missing_required_field")
    return value[key]


def _text(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CostEvidenceError("malformed_input")
    return value


def _decimal(value: object) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise CostEvidenceError("malformed_input")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise CostEvidenceError("malformed_input") from None
    if not result.is_finite():
        raise CostEvidenceError("nonfinite_value")
    return result


def _integer(value: object) -> int:
    result = _decimal(value)
    if result != result.to_integral_value():
        raise CostEvidenceError("malformed_input")
    return int(result)


def _sha(value: object) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise CostEvidenceError("malformed_input")
    return value


def _date(value: object) -> str:
    if not isinstance(value, str):
        raise CostEvidenceError("malformed_input")
    try:
        date.fromisoformat(value)
    except ValueError:
        raise CostEvidenceError("malformed_input") from None
    return value


def _bounded_bytes(
    path: Path,
    limit: int,
    too_large_code: str,
    *,
    unavailable_code: str = "source_unavailable",
) -> bytes:
    try:
        with path.open("rb") as source:
            raw = source.read(limit + 1)
    except OSError:
        raise CostEvidenceError(unavailable_code) from None
    if len(raw) > limit:
        raise CostEvidenceError(too_large_code)
    return raw


def _read(
    path: Path,
    expected_sha: str,
    *,
    limit: int = MAX_SOURCE_BYTES,
    too_large_code: str = "source_too_large",
) -> tuple[dict[str, object], bytes]:
    raw = _bounded_bytes(path, limit, too_large_code)
    if hashlib.sha256(raw).hexdigest() != expected_sha:
        raise CostEvidenceError("source_sha_mismatch")
    return _json(raw, limit=limit), raw


def _digest(value: object) -> str:
    try:
        raw = json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    except (TypeError, ValueError):
        raise CostEvidenceError("malformed_input") from None
    return hashlib.sha256(raw).hexdigest()


def _canonical_source_hash() -> str:
    raw = _bounded_bytes(
        Path(__file__),
        MAX_VERIFIER_SOURCE_BYTES,
        "verifier_too_large",
        unavailable_code="verifier_unavailable",
    )
    text = raw.decode("utf-8")
    for literal in (VERIFIER_SOURCE_SHA256, CANONICAL_EVIDENCE_SHA256):
        text = text.replace(literal, "0" * 64)
    return hashlib.sha256(text.encode()).hexdigest()


def _safe_expected(path: Path, expected: Path) -> None:
    try:
        if path.resolve() != expected.resolve() or path.is_symlink():
            raise CostEvidenceError("unsafe_path")
    except OSError:
        raise CostEvidenceError("source_unavailable") from None


def _verify_manifest(
    manifest_path: Path, run_path: Path, dataset_path: Path, cache_dir: Path
) -> None:
    _safe_expected(manifest_path, CANONICAL_MANIFEST_PATH)
    manifest, _ = _read(
        manifest_path,
        CANONICAL_MANIFEST_SHA256,
        limit=MAX_MANIFEST_BYTES,
        too_large_code="manifest_too_large",
    )
    artifacts = _mapping(_required(manifest, "artifacts"))
    expected = {
        "dataset": (dataset_path, CANONICAL_DATASET_SHA256),
        "run": (run_path, CANONICAL_RUN_SHA256),
        "cache_manifest": (
            cache_dir / "manifest.json",
            CANONICAL_CACHE_MANIFEST_SHA256,
        ),
        "collection_completion": (
            cache_dir / "completed.json",
            CANONICAL_COMPLETION_SHA256,
        ),
    }
    for name, (path, sha) in expected.items():
        item = _mapping(_required(artifacts, name))
        linked = item.get("path")
        canonical = {
            "dataset": CANONICAL_DATASET_PATH,
            "run": CANONICAL_RUN_PATH,
            "cache_manifest": CANONICAL_CACHE_DIR / "manifest.json",
            "collection_completion": CANONICAL_CACHE_DIR / "completed.json",
        }[name]
        if item.get("sha256") != sha or linked != str(canonical):
            raise CostEvidenceError("manifest_chain_mismatch")
    run_fact = _mapping(_required(manifest, "run"))
    if run_fact.get("period") != {"start": "2025-09-11", "end": "2026-09-11"}:
        raise CostEvidenceError("manifest_period_mismatch")


def _verify_cache(cache_dir: Path) -> dict[str, object]:
    manifest_path = cache_dir / "manifest.json"
    completion_path = cache_dir / "completed.json"
    _safe_expected(manifest_path, CANONICAL_CACHE_DIR / "manifest.json")
    _safe_expected(completion_path, CANONICAL_CACHE_DIR / "completed.json")
    manifest, _ = _read(
        manifest_path,
        CANONICAL_CACHE_MANIFEST_SHA256,
        limit=MAX_CACHE_BYTES,
        too_large_code="cache_manifest_too_large",
    )
    if manifest.get("version") != "collector-cache-v2":
        raise CostEvidenceError("cache_schema_mismatch")
    entries = _list(_required(manifest, "entries"))
    if len(entries) != EXPECTED_CACHE_ENTRY_COUNT:
        raise CostEvidenceError("cache_entry_count_mismatch")
    seen: set[str] = set()
    raw_total = 0
    raw_digests: list[dict[str, object]] = []
    for raw_entry in entries:
        entry = _mapping(raw_entry)
        key = _text(_required(entry, "key"))
        content_sha = _sha(_required(entry, "content_sha256"))
        if not _KEY.fullmatch(key) or key in seen:
            raise CostEvidenceError("cache_duplicate_or_invalid_key")
        seen.add(key)
        size = _integer(_required(entry, "byte_count"))
        if size <= 0 or _integer(_required(entry, "status_code")) != 200:
            raise CostEvidenceError("cache_entry_mismatch")
        raw_path = cache_dir / "raw" / f"{key}.bin"
        try:
            if (
                raw_path.resolve().parent != (cache_dir / "raw").resolve()
                or raw_path.is_symlink()
            ):
                raise CostEvidenceError("unsafe_path")
            if size > MAX_CACHE_RAW_BYTES:
                raise CostEvidenceError("cache_raw_too_large")
            raw = _bounded_bytes(
                raw_path,
                MAX_CACHE_RAW_BYTES,
                "cache_raw_too_large",
                unavailable_code="cache_raw_unavailable",
            )
        except OSError:
            raise CostEvidenceError("cache_raw_unavailable") from None
        if len(raw) != size or hashlib.sha256(raw).hexdigest() != content_sha:
            raise CostEvidenceError("cache_raw_mismatch")
        raw_total += size
        raw_digests.append({"key": key, "sha256": content_sha, "byte_count": size})
    completion, _ = _read(
        completion_path,
        CANONICAL_COMPLETION_SHA256,
        limit=MAX_CACHE_BYTES,
        too_large_code="cache_completion_too_large",
    )
    if (
        completion.get("version") != "collector-completed-v2"
        or completion.get("dataset_sha256") != CANONICAL_DATASET_SHA256
    ):
        raise CostEvidenceError("completion_mismatch")
    if completion.get("output_path") != str(CANONICAL_DATASET_PATH):
        raise CostEvidenceError("completion_path_mismatch")
    return {
        "entry_count": len(entries),
        "raw_total_bytes": raw_total,
        "raw_digest": _digest(raw_digests),
    }


def _validate_dataset(
    dataset: Mapping[str, object],
) -> tuple[
    dict[tuple[str, str], Mapping[str, object]], dict[str, Mapping[str, object]]
]:
    if dataset.get("market") != "US" or dataset.get("simulated") is not False:
        raise CostEvidenceError("dataset_mismatch")
    bars = _list(_required(dataset, "bars"))
    fx_rows = _list(_required(dataset, "fx"))
    if len(bars) != 10476 or len(fx_rows) != 271:
        raise CostEvidenceError("dataset_count_mismatch")
    bar_map: dict[tuple[str, str], Mapping[str, object]] = {}
    for row in bars:
        item = _mapping(row)
        session = _date(_required(item, "session"))
        symbol = _text(_required(item, "symbol"))
        key = (session, symbol)
        if key in bar_map:
            raise CostEvidenceError("dataset_duplicate_bar")
        for name in ("open", "close"):
            if _decimal(_required(item, name)) <= 0:
                raise CostEvidenceError("dataset_invalid_bar")
        bar_map[key] = item
    fx_map: dict[str, Mapping[str, object]] = {}
    for row in fx_rows:
        item = _mapping(row)
        session = _date(_required(item, "session"))
        if (
            session in fx_map
            or _decimal(_required(item, "krw_per_usd")) <= 0
            or _decimal(_required(item, "spread_rate")) < 0
        ):
            raise CostEvidenceError("dataset_invalid_fx")
        fx_map[session] = item
    return bar_map, fx_map


def _verify_evidence(
    evidence_path: Path,
    sessions: list[dict[str, object]],
    summary: Mapping[str, object],
) -> None:
    if evidence_path.is_symlink():
        raise CostEvidenceError("unsafe_path")
    evidence, raw = _read(
        evidence_path,
        CANONICAL_EVIDENCE_SHA256,
        limit=MAX_EVIDENCE_BYTES,
        too_large_code="evidence_too_large",
    )
    if (
        evidence.get("schema") != SCHEMA
        or evidence.get("verifier_source_sha256") != VERIFIER_SOURCE_SHA256
    ):
        raise CostEvidenceError("evidence_schema_mismatch")
    if _canonical_source_hash() != VERIFIER_SOURCE_SHA256:
        raise CostEvidenceError("verifier_sha_mismatch")
    context = _mapping(_required(evidence, "decimal_context"))
    if context != {
        "prec": 28,
        "rounding": "ROUND_HALF_EVEN",
        "Emin": -999999,
        "Emax": 999999,
    }:
        raise CostEvidenceError("decimal_context_mismatch")
    if (
        evidence.get("trade_count") != EXPECTED_TRADE_COUNT
        or evidence.get("session_count") != EXPECTED_SESSION_COUNT
    ):
        raise CostEvidenceError("evidence_count_mismatch")
    if evidence.get("max_residual") != "0" or evidence.get("final_holdings") != {}:
        raise CostEvidenceError("evidence_accounting_mismatch")
    stored = _list(_required(evidence, "sessions"))
    if stored != sessions:
        raise CostEvidenceError("session_digest_mismatch")
    if evidence.get("accounting_digest") != _digest(sessions):
        raise CostEvidenceError("accounting_digest_mismatch")
    artifacts = _mapping(_required(evidence, "artifacts"))
    expected = {
        "manifest": CANONICAL_MANIFEST_SHA256,
        "run": CANONICAL_RUN_SHA256,
        "dataset": CANONICAL_DATASET_SHA256,
        "cache_manifest": CANONICAL_CACHE_MANIFEST_SHA256,
        "completion": CANONICAL_COMPLETION_SHA256,
    }
    if any(artifacts.get(key) != value for key, value in expected.items()):
        raise CostEvidenceError("evidence_artifact_mismatch")


def verify_canonical_cost_evidence(
    run_path: Path = CANONICAL_RUN_PATH,
    dataset_path: Path = CANONICAL_DATASET_PATH,
    cache_dir: Path = CANONICAL_CACHE_DIR,
    manifest_path: Path = CANONICAL_MANIFEST_PATH,
    evidence_path: Path = CANONICAL_EVIDENCE_PATH,
) -> dict[str, object]:
    """Verify the registered artifact chain and reconstruct the native ledger."""
    _safe_expected(run_path, CANONICAL_RUN_PATH)
    _safe_expected(dataset_path, CANONICAL_DATASET_PATH)
    _safe_expected(cache_dir, CANONICAL_CACHE_DIR)
    _verify_manifest(manifest_path, run_path, dataset_path, cache_dir)
    cache_facts = _verify_cache(cache_dir)
    run, _ = _read(run_path, CANONICAL_RUN_SHA256, too_large_code="run_too_large")
    dataset, _ = _read(
        dataset_path,
        CANONICAL_DATASET_SHA256,
        limit=MAX_DATASET_BYTES,
        too_large_code="dataset_too_large",
    )
    bar_map, fx_map = _validate_dataset(dataset)
    request = _mapping(_required(run, "request"))
    result = _mapping(_required(run, "result"))
    trades = _list(_required(result, "trades"))
    equity = _list(_required(result, "equity"))
    if len(trades) != EXPECTED_TRADE_COUNT or len(equity) != EXPECTED_SESSION_COUNT:
        raise CostEvidenceError("run_count_mismatch")
    if request.get("market") != "US" or request.get("research_grade") != "approximate":
        raise CostEvidenceError("run_mismatch")
    fee_rate = _decimal(_required(request, "fee_rate"))
    slip_rate = _decimal(_required(request, "slippage_rate"))
    tax_rate = _decimal(_required(request, "sell_tax_rate"))
    first_session = _date(_required(_mapping(equity[0]), "session"))
    first_fx = fx_map.get(first_session)
    if first_fx is None:
        raise CostEvidenceError("missing_initial_fx")
    with localcontext(DECIMAL_CONTEXT):
        cash = _decimal(_required(request, "initial_cash_krw")) / (
            _decimal(_required(first_fx, "krw_per_usd"))
            * (Decimal(1) + _decimal(_required(first_fx, "spread_rate")))
        )
        holdings: dict[str, int] = {}
        grouped: dict[str, list[Mapping[str, object]]] = {}
        previous_session = ""
        for raw_trade in trades:
            trade = _mapping(raw_trade)
            session = _date(_required(trade, "session"))
            if session < previous_session:
                raise CostEvidenceError("trade_order_mismatch")
            previous_session = session
            grouped.setdefault(session, []).append(trade)
        sessions: list[dict[str, object]] = []
        previous_equity = ""
        for raw_equity in equity:
            point = _mapping(raw_equity)
            session = _date(_required(point, "session"))
            if session <= previous_equity:
                raise CostEvidenceError("session_order_mismatch")
            previous_equity = session
            fx_row = fx_map.get(session)
            if fx_row is None:
                raise CostEvidenceError("missing_fx")
            seen_buy = False
            session_trade_count = 0
            for trade in grouped.get(session, []):
                side = _required(trade, "side")
                if side not in {"buy", "sell"}:
                    raise CostEvidenceError("invalid_side")
                if side == "buy":
                    seen_buy = True
                elif seen_buy:
                    raise CostEvidenceError("trade_side_order_mismatch")
                symbol = _text(_required(trade, "symbol"))
                quantity = _integer(_required(trade, "quantity"))
                if (
                    quantity <= 0
                    or _required(trade, "currency") != "USD"
                    or _required(trade, "fill_session") != session
                ):
                    raise CostEvidenceError("invalid_trade")
                bar = bar_map.get((session, symbol))
                if bar is None:
                    raise CostEvidenceError("missing_trade_bar")
                market_open = _decimal(_required(bar, "open"))
                stored_open = _decimal(_required(trade, "market_open"))
                fill = market_open * (
                    Decimal(1) - slip_rate if side == "sell" else Decimal(1) + slip_rate
                )
                notional = fill * quantity
                fee = notional * fee_rate
                tax = notional * tax_rate if side == "sell" else Decimal(0)
                if (
                    stored_open != market_open
                    or _decimal(_required(trade, "fill_price")) != fill
                    or _decimal(_required(trade, "notional")) != notional
                    or _decimal(_required(trade, "fee")) != fee
                    or _decimal(_required(trade, "tax")) != tax
                ):
                    raise CostEvidenceError("trade_recomputation_mismatch")
                current = holdings.get(symbol, 0)
                if side == "sell":
                    if current < quantity:
                        raise CostEvidenceError("oversell")
                    holdings[symbol] = current - quantity
                    cash += notional - fee - tax
                else:
                    holdings[symbol] = current + quantity
                    cash -= notional + fee
                session_trade_count += 1
            holdings = {key: value for key, value in holdings.items() if value}
            invested_native = sum(
                (
                    (
                        _decimal(_required(bar_map[(session, symbol)], "close"))
                        * quantity
                    )
                    for symbol, quantity in holdings.items()
                ),
                Decimal(0),
            )
            fx = _decimal(_required(fx_row, "krw_per_usd"))
            cash_krw = cash * fx
            invested_krw = invested_native * fx
            nav = (cash + invested_native) * fx
            values = {
                "cash_native": cash,
                "cash_krw": cash_krw,
                "invested_krw": invested_krw,
                "nav_krw": nav,
            }
            for name, calculated in values.items():
                if _decimal(_required(point, name)) != calculated:
                    raise CostEvidenceError("nav_reconciliation_mismatch")
            sessions.append(
                {
                    "session": session,
                    "trade_count": session_trade_count,
                    "cash_native": str(cash),
                    "cash_krw": str(cash_krw),
                    "invested_krw": str(invested_krw),
                    "nav_krw": str(nav),
                    "fx_krw_per_usd": str(fx),
                    "holdings": {key: value for key, value in sorted(holdings.items())},
                }
            )
        if holdings:
            raise CostEvidenceError("final_holdings_nonzero")
    summary: dict[str, object] = {
        "trade_count": len(trades),
        "session_count": len(equity),
        "accounting_digest": _digest(sessions),
        "max_residual": "0",
        "final_holdings": {},
        "cache": cache_facts,
    }
    _verify_evidence(evidence_path, sessions, summary)
    return {
        "schema": SCHEMA,
        "status": "verified",
        "grade": "approximate",
        "trade_count": EXPECTED_TRADE_COUNT,
        "session_count": EXPECTED_SESSION_COUNT,
        "max_residual": "0",
        "accounting_digest": summary["accounting_digest"],
        "artifacts": {
            "manifest": CANONICAL_MANIFEST_SHA256,
            "run": CANONICAL_RUN_SHA256,
            "dataset": CANONICAL_DATASET_SHA256,
            "cache_manifest": CANONICAL_CACHE_MANIFEST_SHA256,
            "completion": CANONICAL_COMPLETION_SHA256,
        },
    }


# Short names are useful to callers while keeping the canonical entry point explicit.
verify_cost_evidence = verify_canonical_cost_evidence
reconcile_canonical_run = verify_canonical_cost_evidence


def render_report(report: Mapping[str, object]) -> str:
    return json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, default=str)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--canonical", action="store_true")
    args = parser.parse_args(argv)
    if not args.canonical:
        print(render_report({"error": "canonical flag required"}))
        return 2
    try:
        print(render_report(verify_canonical_cost_evidence()))
    except CostEvidenceError as exc:
        print(render_report({"error": {"code": exc.code}}))
        return 1
    return 0


__all__ = [
    "CANONICAL_EVIDENCE_PATH",
    "CANONICAL_RUN_PATH",
    "CostEvidenceError",
    "SCHEMA",
    "verify_canonical_cost_evidence",
    "verify_cost_evidence",
    "reconcile_canonical_run",
    "render_report",
    "main",
]


if __name__ == "__main__":
    sys.exit(main())
