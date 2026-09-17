from __future__ import annotations

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


def test_verifier_has_no_runtime_strategy_or_broker_imports() -> None:
    source = Path(evidence.__file__).read_text(encoding="utf-8")
    for forbidden in (
        "market_research_strategy",
        "market_data_collector",
        "replay",
        "broker",
    ):
        assert f"import {forbidden}" not in source
