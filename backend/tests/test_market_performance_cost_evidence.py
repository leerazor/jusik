from __future__ import annotations

import ast
import copy
import json
import shutil
from decimal import Decimal, localcontext
from pathlib import Path

import pytest

import jusik.market_performance_cost_evidence as evidence

_FORBIDDEN_COMPONENTS = ("strategy", "collector", "replay", "broker")


def _assert_no_forbidden_dependencies(source: str) -> None:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
            assert not any(
                component in name
                for name in names
                for component in _FORBIDDEN_COMPONENTS
            )
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""] + [alias.name for alias in node.names]
            assert not any(
                component in name
                for name in names
                for component in _FORBIDDEN_COMPONENTS
            )
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                assert node.func.id not in {"__import__", "eval", "exec"}
            if isinstance(node.func, ast.Attribute):
                assert node.func.attr not in {"import_module", "__import__"}


def _ledger_seam(
    monkeypatch: pytest.MonkeyPatch,
    run: dict[str, object],
    dataset: dict[str, object],
) -> None:
    def fake_read(
        path: Path,
        expected_sha: str,
        *,
        limit: int = evidence.MAX_SOURCE_BYTES,
        too_large_code: str = "source_too_large",
    ) -> tuple[dict[str, object], bytes]:
        if path == evidence.CANONICAL_RUN_PATH:
            return run, b""
        if path == evidence.CANONICAL_DATASET_PATH:
            return dataset, b""
        return {}, b""

    monkeypatch.setattr(evidence, "_read", fake_read)
    monkeypatch.setattr(evidence, "_verify_manifest", lambda *args: None)
    monkeypatch.setattr(evidence, "_verify_cache", lambda *args: {})
    monkeypatch.setattr(evidence, "_verify_evidence", lambda *args: None)


def _canonical_payloads() -> tuple[dict[str, object], dict[str, object]]:
    return (
        json.loads(evidence.CANONICAL_RUN_PATH.read_text(encoding="utf-8")),
        json.loads(evidence.CANONICAL_DATASET_PATH.read_text(encoding="utf-8")),
    )


def test_canonical_cost_ledger_reconciles_without_strategy_imports() -> None:
    report = evidence.verify_canonical_cost_evidence()
    assert report["status"] == "verified"
    assert report["trade_count"] == 106
    assert report["session_count"] == 252
    assert report["max_residual"] == "0"
    assert report["accounting_digest"] == (
        "6b7ee6f0bdfbe99436a93b55d7d60d3488b2be72175fa9b0977234e522e8a822"
    )


def test_evidence_bytes_and_verifier_source_are_mutually_pinned(
    tmp_path: Path,
) -> None:
    copy = tmp_path / "evidence.json"
    raw = evidence.CANONICAL_EVIDENCE_PATH.read_bytes()
    copy.write_bytes(raw[:-2] + b"x\n")
    with pytest.raises(evidence.CostEvidenceError, match="source_sha_mismatch"):
        evidence.verify_canonical_cost_evidence(evidence_path=copy)


@pytest.mark.parametrize(
    ("limit", "error"),
    [
        (evidence.MAX_MANIFEST_BYTES, "manifest_too_large"),
        (evidence.MAX_DATASET_BYTES, "dataset_too_large"),
        (evidence.MAX_EVIDENCE_BYTES, "evidence_too_large"),
    ],
)
def test_cost_read_replacement_is_bounded_before_hash_and_parse(
    tmp_path: Path, limit: int, error: str
) -> None:
    path = tmp_path / "replacement.json"
    path.write_bytes(b"{}")
    _ = path.stat()
    path.write_bytes(b"x" * (limit + 1))
    with pytest.raises(evidence.CostEvidenceError, match=error):
        evidence._read(
            path,
            "0" * 64,
            limit=limit,
            too_large_code=error,
        )


def test_cost_verifier_bounds_replaced_manifest_before_parse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    replacement = tmp_path / "manifest.json"
    replacement.write_bytes(b"{}")
    _ = replacement.stat()
    replacement.write_bytes(b"x" * (evidence.MAX_MANIFEST_BYTES + 1))
    monkeypatch.setattr(evidence, "CANONICAL_MANIFEST_PATH", replacement)
    with pytest.raises(evidence.CostEvidenceError, match="manifest_too_large"):
        evidence.verify_canonical_cost_evidence(manifest_path=replacement)


def test_cost_verifier_bounds_replaced_dataset_before_parse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    replacement = tmp_path / "dataset.json"
    replacement.write_bytes(b"{}")
    _ = replacement.stat()
    replacement.write_bytes(b"x" * (evidence.MAX_DATASET_BYTES + 1))
    monkeypatch.setattr(evidence, "CANONICAL_DATASET_PATH", replacement)
    monkeypatch.setattr(evidence, "_verify_manifest", lambda *args: None)
    monkeypatch.setattr(evidence, "_verify_cache", lambda *args: {})
    with pytest.raises(evidence.CostEvidenceError, match="dataset_too_large"):
        evidence.verify_canonical_cost_evidence(dataset_path=replacement)


def test_cost_verifier_bounds_replaced_evidence_before_parse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    replacement = tmp_path / "evidence.json"
    replacement.write_bytes(b"{}")
    _ = replacement.stat()
    replacement.write_bytes(b"x" * (evidence.MAX_EVIDENCE_BYTES + 1))
    monkeypatch.setattr(evidence, "CANONICAL_EVIDENCE_PATH", replacement)
    with pytest.raises(evidence.CostEvidenceError, match="evidence_too_large"):
        evidence.verify_canonical_cost_evidence(evidence_path=replacement)


def test_cost_verifier_reports_absent_verifier_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing_source = tmp_path / "missing-verifier.py"
    monkeypatch.setattr(evidence, "__file__", str(missing_source))
    with pytest.raises(evidence.CostEvidenceError, match="verifier_unavailable"):
        evidence._canonical_source_hash()


def test_canonical_artifact_paths_reject_symlinked_run(tmp_path: Path) -> None:
    link = tmp_path / "run.json"
    link.symlink_to(evidence.CANONICAL_RUN_PATH)
    with pytest.raises(evidence.CostEvidenceError, match="unsafe_path"):
        evidence.verify_canonical_cost_evidence(run_path=link)


@pytest.mark.parametrize(
    ("argument", "canonical"),
    [
        ("run_path", evidence.CANONICAL_RUN_PATH),
        ("dataset_path", evidence.CANONICAL_DATASET_PATH),
        ("manifest_path", evidence.CANONICAL_MANIFEST_PATH),
        ("cache_dir", evidence.CANONICAL_CACHE_DIR),
    ],
)
def test_same_bytes_copies_cannot_bypass_registered_paths(
    tmp_path: Path, argument: str, canonical: Path
) -> None:
    copy_path = tmp_path / canonical.name
    if canonical.is_dir():
        copy_path.mkdir()
    else:
        copy_path.write_bytes(canonical.read_bytes())
    with pytest.raises(evidence.CostEvidenceError, match="unsafe_path"):
        evidence.verify_canonical_cost_evidence(**{argument: copy_path})


def test_pure_ledger_guards_reach_fee_and_mark_reconciliation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = json.loads(evidence.CANONICAL_RUN_PATH.read_text(encoding="utf-8"))
    dataset = json.loads(evidence.CANONICAL_DATASET_PATH.read_text(encoding="utf-8"))
    run["result"]["trades"][0]["fee"] = "0"

    def fake_read(
        path: Path,
        expected_sha: str,
        *,
        limit: int = evidence.MAX_SOURCE_BYTES,
        too_large_code: str = "source_too_large",
    ):
        if path == evidence.CANONICAL_RUN_PATH:
            return run, b""
        if path == evidence.CANONICAL_DATASET_PATH:
            return dataset, b""
        return {}, b""

    monkeypatch.setattr(evidence, "_read", fake_read)
    monkeypatch.setattr(evidence, "_verify_manifest", lambda *args: None)
    monkeypatch.setattr(evidence, "_verify_cache", lambda *args: {})
    monkeypatch.setattr(evidence, "_verify_evidence", lambda *args: None)
    with pytest.raises(
        evidence.CostEvidenceError, match="trade_recomputation_mismatch"
    ):
        evidence.verify_canonical_cost_evidence()

    run = copy.deepcopy(run)
    run["result"]["trades"][0]["fee"] = "0.54049946193716521838790"
    run["result"]["equity"][0]["nav_krw"] = "1"

    def replacement_read(
        path: Path,
        expected_sha: str,
        *,
        limit: int = evidence.MAX_SOURCE_BYTES,
        too_large_code: str = "source_too_large",
    ) -> tuple[dict[str, object], bytes]:
        return (
            run if path == evidence.CANONICAL_RUN_PATH else dataset,
            b"",
        )

    monkeypatch.setattr(evidence, "_read", replacement_read)
    with pytest.raises(evidence.CostEvidenceError, match="nav_reconciliation_mismatch"):
        evidence.verify_canonical_cost_evidence()

    dataset = json.loads(evidence.CANONICAL_DATASET_PATH.read_text(encoding="utf-8"))
    dataset["fx"][0]["spread_rate"] = "0.01"
    monkeypatch.setattr(evidence, "_read", replacement_read)
    with pytest.raises(evidence.CostEvidenceError, match="nav_reconciliation_mismatch"):
        evidence.verify_canonical_cost_evidence()


def test_ambient_decimal_context_does_not_change_canonical_result() -> None:
    from decimal import getcontext

    before = getcontext().prec
    getcontext().prec = 6
    try:
        assert evidence.verify_canonical_cost_evidence()["max_residual"] == "0"
    finally:
        getcontext().prec = before


def test_cache_raw_size_and_hash_are_checked_after_path_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_copy = tmp_path / "cache"
    shutil.copytree(evidence.CANONICAL_CACHE_DIR, cache_copy)
    raw_file = next((cache_copy / "raw").iterdir())
    raw_file.write_bytes(raw_file.read_bytes() + b"tamper")
    monkeypatch.setattr(evidence, "CANONICAL_CACHE_DIR", cache_copy)
    with pytest.raises(evidence.CostEvidenceError, match="cache_raw_mismatch"):
        evidence._verify_cache(cache_copy)


def test_cache_raw_replacement_cannot_escape_bound(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_copy = tmp_path / "cache"
    shutil.copytree(evidence.CANONICAL_CACHE_DIR, cache_copy)
    raw_file = next((cache_copy / "raw").iterdir())
    raw_file.write_bytes(b"x" * (evidence.MAX_CACHE_RAW_BYTES + 1))
    monkeypatch.setattr(evidence, "CANONICAL_CACHE_DIR", cache_copy)
    with pytest.raises(evidence.CostEvidenceError, match="cache_raw_too_large"):
        evidence._verify_cache(cache_copy)


def test_cache_raw_absence_is_reported_by_production_consumer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_copy = tmp_path / "cache"
    shutil.copytree(evidence.CANONICAL_CACHE_DIR, cache_copy)
    raw_file = next((cache_copy / "raw").iterdir())
    raw_file.unlink()
    monkeypatch.setattr(evidence, "CANONICAL_CACHE_DIR", cache_copy)
    with pytest.raises(evidence.CostEvidenceError, match="cache_raw_unavailable"):
        evidence._verify_cache(cache_copy)


@pytest.mark.parametrize(
    ("mutation", "error"),
    [
        ("trade_order", "trade_order_mismatch"),
        ("trade_side_order", "trade_side_order_mismatch"),
    ],
)
def test_serialized_trade_order_guards_reach_ledger(
    monkeypatch: pytest.MonkeyPatch, mutation: str, error: str
) -> None:
    run, dataset = _canonical_payloads()
    trades = run["result"]["trades"]
    assert isinstance(trades, list)
    if mutation == "trade_order":
        trades[0], trades[1] = trades[1], trades[0]
    else:
        same_session = [
            index
            for index, item in enumerate(trades)
            if item["session"] == "2025-10-23"
        ]
        trades[same_session[0]], trades[same_session[1]] = (
            trades[same_session[1]],
            trades[same_session[0]],
        )
    _ledger_seam(monkeypatch, run, dataset)
    with pytest.raises(evidence.CostEvidenceError, match=error):
        evidence.verify_canonical_cost_evidence()


def test_oversell_guard_reaches_position_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run, dataset = _canonical_payloads()
    trades = run["result"]["trades"]
    assert isinstance(trades, list)
    trade = next(item for item in trades if item["side"] == "sell")
    trade["quantity"] = 10_000
    with localcontext() as context:
        context.prec = 28
        bar = next(
            item
            for item in dataset["bars"]
            if item["session"] == trade["session"] and item["symbol"] == trade["symbol"]
        )
        fill = Decimal(bar["open"]) * (
            Decimal(1) - Decimal(run["request"]["slippage_rate"])
        )
        notional = fill * trade["quantity"]
        trade["fill_price"] = str(fill)
        trade["notional"] = str(notional)
        trade["fee"] = str(notional * Decimal(run["request"]["fee_rate"]))
        trade["tax"] = str(notional * Decimal(run["request"]["sell_tax_rate"]))
    _ledger_seam(monkeypatch, run, dataset)
    with pytest.raises(evidence.CostEvidenceError, match="oversell"):
        evidence.verify_canonical_cost_evidence()


def test_final_open_holding_guard_reaches_terminal_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run, dataset = _canonical_payloads()
    trades = run["result"]["trades"]
    assert isinstance(trades, list)
    trade = trades[-1]
    assert trade["side"] == "sell"
    original_tax = Decimal(trade["tax"])
    original_notional = Decimal(trade["notional"])
    original_fee = Decimal(trade["fee"])
    with localcontext() as context:
        context.prec = 28
        trade["side"] = "buy"
        fill = Decimal(trade["market_open"]) * (
            Decimal(1) + Decimal(run["request"]["slippage_rate"])
        )
        notional = fill * trade["quantity"]
        fee = notional * Decimal(run["request"]["fee_rate"])
        trade["fill_price"] = str(fill)
        trade["notional"] = str(notional)
        trade["fee"] = str(fee)
        trade["tax"] = "0"
        final_point = run["result"]["equity"][-1]
        cash_before = (
            Decimal(final_point["cash_native"])
            - original_notional
            + original_fee
            + original_tax
        )
        cash = cash_before - notional - fee
        pre_quantity = sum(
            item["quantity"] if item["side"] == "buy" else -item["quantity"]
            for item in trades[:-1]
            if item["symbol"] == trade["symbol"]
        )
        for point in run["result"]["equity"]:
            if point["session"] < trade["session"]:
                continue
            fx = Decimal(point["fx_krw_per_usd"])
            close = next(
                item
                for item in dataset["bars"]
                if item["session"] == point["session"]
                and item["symbol"] == trade["symbol"]
            )["close"]
            invested_native = Decimal(close) * (pre_quantity + trade["quantity"])
            point["cash_native"] = str(cash)
            point["cash_krw"] = str(cash * fx)
            point["invested_krw"] = str(invested_native * fx)
            point["nav_krw"] = str((cash + invested_native) * fx)
    _ledger_seam(monkeypatch, run, dataset)
    with pytest.raises(evidence.CostEvidenceError, match="final_holdings_nonzero"):
        evidence.verify_canonical_cost_evidence()


def test_active_close_mark_mutation_reaches_nav_reconciliation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run, dataset = _canonical_payloads()
    bar = next(
        item
        for item in dataset["bars"]
        if item["session"] == "2025-10-10" and item["symbol"] == "VTGN"
    )
    bar["close"] = str(Decimal(bar["close"]) + Decimal("1"))
    _ledger_seam(monkeypatch, run, dataset)
    with pytest.raises(evidence.CostEvidenceError, match="nav_reconciliation_mismatch"):
        evidence.verify_canonical_cost_evidence()


@pytest.mark.parametrize("mutation", ["tax_zero", "tax_double", "fee_double"])
def test_sell_tax_omission_and_double_charge_residual_are_rejected(
    monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    run, dataset = _canonical_payloads()
    trade = next(item for item in run["result"]["trades"] if item["side"] == "sell")
    if mutation == "tax_zero":
        trade["tax"] = "0"
    elif mutation == "tax_double":
        trade["tax"] = str(Decimal(trade["tax"]) * 2)
    else:
        trade["fee"] = str(Decimal(trade["fee"]) * 2)
    _ledger_seam(monkeypatch, run, dataset)
    with pytest.raises(
        evidence.CostEvidenceError, match="trade_recomputation_mismatch"
    ):
        evidence.verify_canonical_cost_evidence()


def test_duplicate_trade_row_cannot_replace_identity_silently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run, dataset = _canonical_payloads()
    trades = run["result"]["trades"]
    assert isinstance(trades, list)
    trades.append(copy.deepcopy(trades[-1]))
    _ledger_seam(monkeypatch, run, dataset)
    with pytest.raises(evidence.CostEvidenceError, match="run_count_mismatch"):
        evidence.verify_canonical_cost_evidence()


def test_verifier_has_no_runtime_strategy_or_broker_imports() -> None:
    source = Path(evidence.__file__).read_text(encoding="utf-8")
    _assert_no_forbidden_dependencies(source)


@pytest.mark.parametrize(
    "source",
    [
        "from . import strategy",
        "from .market_research_strategy import run",
        "from package import market_data_collector as collector",
        "import importlib\nimportlib.import_module('broker.execution')",
        "__import__('replay.engine')",
    ],
)
def test_dependency_detector_rejects_import_bypass_snippets(source: str) -> None:
    with pytest.raises(AssertionError):
        _assert_no_forbidden_dependencies(source)
