from __future__ import annotations

import json
from pathlib import Path

import pytest

from jusik.research_canonical_time_evidence import (
    CanonicalTimeEvidenceError,
    build_canonical_time_evidence,
    verify_canonical_time_evidence,
)


def test_build_and_verify_frozen_sidecar(tmp_path: Path) -> None:
    output = tmp_path / "sidecar.json"
    built = build_canonical_time_evidence(output_path=output)

    assert built["schema"] == "r0-canonical-time-evidence-sidecar/v1"
    assert built["status"] == "verified"
    assert len(built["time_evidence"]["equity"]) == 252  # type: ignore[index]
    assert verify_canonical_time_evidence(output)["status"] == "verified"


def test_verify_rejects_changed_source_hash(tmp_path: Path) -> None:
    output = tmp_path / "sidecar.json"
    build_canonical_time_evidence(output_path=output)
    payload = json.loads(output.read_text())
    payload["sources"]["replay"]["sha256"] = "0" * 64
    output.write_text(json.dumps(payload))

    with pytest.raises(CanonicalTimeEvidenceError, match="sidecar_source_sha_mismatch"):
        verify_canonical_time_evidence(output)


def test_build_rejects_non_exact_replay(tmp_path: Path) -> None:
    replay = tmp_path / "replay.json"
    source = Path(
        "/home/kwl/.local/share/jusik/portfolio-audit/"
        "canonical-time-evidence-candidate-20260920/replay.json"
    )
    replay_payload = json.loads(source.read_text())
    replay_payload["comparison"]["all"] = False
    replay.write_text(json.dumps(replay_payload))

    with pytest.raises(CanonicalTimeEvidenceError, match="replay_not_exact"):
        build_canonical_time_evidence(
            replay_path=replay, output_path=tmp_path / "out.json"
        )
