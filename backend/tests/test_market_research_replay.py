from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from jusik.market_research_replay import (
    CATALOGUE_FILE,
    REPLAY_FILE,
    ReplayError,
    _parse_checkpoint,
    replay_manifest,
)

MANIFEST = Path(
    "/home/kwl/.local/share/jusik/portfolio-audit/20260915-r0-baseline/"
    "r0-baseline-freeze/baseline-manifest.json"
)


@pytest.mark.parametrize(
    "value",
    ["2026-09-15T01:10:31", "2026-09-15T10:10:31+09:00", "not-a-time"],
)
def test_checkpoint_requires_aware_utc(value: str) -> None:
    with pytest.raises(ReplayError):
        _parse_checkpoint(value)


def test_checkpoint_normalizes_utc() -> None:
    assert _parse_checkpoint("2026-09-15T10:10:31+00:00").isoformat() == (
        "2026-09-15T10:10:31+00:00"
    )


@pytest.mark.skipif(not MANIFEST.is_file(), reason="frozen audit input is unavailable")
def test_frozen_replay_writes_result_and_refuses_overwrite(tmp_path: Path) -> None:
    import asyncio

    output_dir = tmp_path / "replay"
    catalogue = asyncio.run(
        replay_manifest(
            MANIFEST,
            _parse_checkpoint("2026-09-15T01:10:31Z"),
            output_dir,
        )
    )
    assert catalogue["comparison"] == {
        "all": True,
        "candidate_evidence": True,
        "completeness": True,
        "data_contract_hash": True,
        "equity": True,
        "limitations": True,
        "market": True,
        "metrics": True,
        "pilot_run_id": True,
        "policy_hash": True,
        "pool_contract_hash": True,
        "provenance": True,
        "account": True,
        "readiness": True,
        "request": True,
        "research_grade": True,
        "status": True,
        "stage": True,
        "trades": True,
        "warmup_sessions": True,
    }
    assert (output_dir / REPLAY_FILE).is_file()
    assert (output_dir / CATALOGUE_FILE).is_file()
    with pytest.raises(ReplayError, match="overwrite"):
        asyncio.run(
            replay_manifest(
                MANIFEST,
                _parse_checkpoint("2026-09-15T01:10:31Z"),
                output_dir,
            )
        )


@pytest.mark.skipif(not MANIFEST.is_file(), reason="frozen audit input is unavailable")
@pytest.mark.parametrize(
    "kind",
    ["invalidhash", "wronggrade", "policy", "data", "pool", "request"],
)
def test_manifest_guards_fail_before_strategy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    import asyncio

    payload = json.loads(MANIFEST.read_bytes())
    if kind == "invalidhash":
        payload["artifacts"]["dataset"]["sha256"] = "0" * 64
    elif kind == "wronggrade":
        payload["run"]["request"]["research_grade"] = "strict"
    elif kind == "policy":
        payload["run"]["result"]["policy_hash"] = "0" * 64
    elif kind == "data":
        payload["run"]["result"]["data_contract_hash"] = "0" * 64
    elif kind == "pool":
        payload["run"]["result"]["pool_contract_hash"] = "0" * 64
    else:
        payload["run"]["request"]["fee_rate"] = "0.00016"
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    def unexpected_strategy(*args: object, **kwargs: object) -> object:
        raise AssertionError("strategy must not run for an invalid manifest")

    monkeypatch.setattr(
        "jusik.market_research_replay.run_approximate_market_research",
        unexpected_strategy,
    )
    with pytest.raises(ReplayError):
        asyncio.run(
            replay_manifest(
                manifest,
                _parse_checkpoint("2026-09-15T01:10:31Z"),
                tmp_path.with_name(tmp_path.name + "-output"),
            )
        )


@pytest.mark.skipif(not MANIFEST.is_file(), reason="frozen audit input is unavailable")
def test_cli_rejects_missing_frozen_file(tmp_path: Path) -> None:
    payload = json.loads(MANIFEST.read_bytes())
    payload["artifacts"]["dataset"]["path"] = str(tmp_path / "missing.json")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "jusik.market_research_replay",
            "--manifest",
            str(manifest),
            "--checkpoint-at",
            "2026-09-15T01:10:31Z",
            "--output-dir",
            str(tmp_path.with_name(tmp_path.name + "-output")),
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
    )
    assert process.returncode == 2
    assert "unavailable" in process.stderr
