from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

import pytest

import jusik.market_performance_cost_evidence as evidence


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
        path: Path, expected_sha: str, *, limit: int = evidence.MAX_SOURCE_BYTES
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
    monkeypatch.setattr(
        evidence,
        "_read",
        lambda path, expected_sha, *, limit=evidence.MAX_SOURCE_BYTES: (
            run if path == evidence.CANONICAL_RUN_PATH else dataset,
            b"",
        ),
    )
    with pytest.raises(evidence.CostEvidenceError, match="nav_reconciliation_mismatch"):
        evidence.verify_canonical_cost_evidence()

    dataset = json.loads(evidence.CANONICAL_DATASET_PATH.read_text(encoding="utf-8"))
    dataset["fx"][0]["spread_rate"] = "0.01"
    monkeypatch.setattr(
        evidence,
        "_read",
        lambda path, expected_sha, *, limit=evidence.MAX_SOURCE_BYTES: (
            run if path == evidence.CANONICAL_RUN_PATH else dataset,
            b"",
        ),
    )
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


def test_verifier_has_no_runtime_strategy_or_broker_imports() -> None:
    source = Path(evidence.__file__).read_text(encoding="utf-8")
    for forbidden in (
        "market_research_strategy",
        "market_data_collector",
        "replay",
        "broker",
    ):
        assert f"import {forbidden}" not in source
