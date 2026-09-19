from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from jusik.research_prospective_readiness import (
    ProspectiveBoundaryReadiness,
    ProspectiveExecutionEvidenceReadiness,
    ProspectiveReadiness,
)
from jusik.research_r7_gate import R7GateResult, R7ReviewEvidence, evaluate_r7_gate
from jusik.research_r7_isolation import create_r7_isolation_workspace


def _prospective(*, complete: bool = False) -> ProspectiveReadiness:
    return ProspectiveReadiness.model_construct(
        checked_at=datetime(2026, 11, 10, tzinfo=UTC),
        registration_status="window_elapsed",
        session_id="a" * 64,
        evaluation_start_at=datetime(2026, 9, 14, tzinfo=UTC),
        evaluation_end_at=datetime(2026, 11, 9, tzinfo=UTC),
        collector_implemented=False,
        start_boundary=ProspectiveBoundaryReadiness(
            boundary="start",
            boundary_at=datetime(2026, 9, 14, tzinfo=UTC),
            state="unverified_candidate",
        ),
        end_boundary=ProspectiveBoundaryReadiness(
            boundary="end",
            boundary_at=datetime(2026, 11, 9, tzinfo=UTC),
            state="unverified_candidate",
        ),
        execution_evidence=ProspectiveExecutionEvidenceReadiness(
            state="linked_integrity",
            total_fill_count=1,
            inspected_fill_count=1,
            uninspected_fill_count=0,
            captured_count=1,
            missing_count=0,
            mismatch_count=0,
            truncated=False,
        ),
        evaluation_inputs_complete=complete,
        limitations=[],
    )


def _workspace(tmp_path: Path):
    source = tmp_path / "source.txt"
    source.write_bytes(b"source")
    import hashlib

    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    return create_r7_isolation_workspace(
        tmp_path / "future",
        retrospective_paths=(source,),
        source_identities={"source": digest},
        source_hashes={source: digest},
    )


def test_gate_blocks_without_all_evidence_and_never_promotes(tmp_path: Path) -> None:
    result = evaluate_r7_gate(
        prospective=_prospective(),
        workspace=None,
        evidence=R7ReviewEvidence(),
    )
    assert result.state == "blocked"
    assert result.simulation_allowed is False
    assert result.paper_decision_required is True
    assert result.automatic_promotion_eligible is False
    assert "prospective_inputs_incomplete" in result.reasons
    assert "isolated_workspace_manifest_unavailable" in result.reasons


def test_gate_is_ready_only_after_every_gate_and_keeps_paper_manual(
    tmp_path: Path,
) -> None:
    digest = "b" * 64
    result = evaluate_r7_gate(
        prospective=_prospective(complete=True),
        workspace=_workspace(tmp_path),
        evidence=R7ReviewEvidence(
            oos_artifact_sha256=digest,
            oos_passed=True,
            stress_artifact_sha256=digest,
            stress_passed=True,
            independent_review_sha256=digest,
            independent_review_passed=True,
        ),
    )
    assert result.state == "ready"
    assert result.simulation_allowed is True
    assert result.paper_decision_required is True
    assert result.automatic_promotion_eligible is False
    assert result.workspace_manifest_sha256 is not None


def test_gate_evidence_and_result_invariants_cannot_be_bypassed() -> None:
    with pytest.raises(ValueError, match="OOS evidence"):
        R7ReviewEvidence(oos_passed=True)
    with pytest.raises(ValueError, match="cannot allow simulation"):
        R7GateResult(state="blocked", simulation_allowed=True, reasons=())
