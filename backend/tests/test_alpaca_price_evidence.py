"""Focused offline proof for the fixed Alpaca SIP price evidence contract."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from jusik import alpaca_price_evidence as evidence

AUDIT = Path("/home/kwl/.local/share/jusik/portfolio-audit")
SCOPE = AUDIT / "20261002-alpaca-price-evidence/scope.json"
ASSESSMENT = AUDIT / "20261002-alpaca-sip-feasibility/assessment.json"
BATCH = AUDIT / "20261002-alpaca-sip-feasibility/plain-16-sip-raw.json"
SINGLE = AUDIT / "20261002-alpaca-sip-feasibility/rapt-sip-raw.json"
SESSIONS = AUDIT / "20260930-us-exclusion-pilot-readiness/us-1y-exclusions.json"


@pytest.fixture
def fixed_inputs() -> tuple[Path, Path, Path, Path, Path]:
    files = (SCOPE, ASSESSMENT, BATCH, SINGLE, SESSIONS)
    if not all(path.is_file() for path in files):
        pytest.skip("fixed external audit evidence is unavailable")
    return files


def arguments(paths: tuple[Path, Path, Path, Path, Path], output: Path) -> list[str]:
    scope, assessment, batch, single, sessions = paths
    return [
        "--scope",
        str(scope),
        "--scope-sha256",
        evidence.sha256(scope),
        "--assessment",
        str(assessment),
        "--batch",
        str(batch),
        "--single",
        str(single),
        "--expected-sessions",
        str(sessions),
        "--expected-sha256",
        evidence.EXPECTED_SESSIONS_SHA256,
        "--output-dir",
        str(output),
    ]


def mutable_case(
    tmp_path: Path, fixed: tuple[Path, Path, Path, Path, Path]
) -> tuple[
    tuple[Path, Path, Path, Path, Path],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
]:
    scope_source, assessment_source, batch_source, single_source, sessions = fixed
    copies = tmp_path / "inputs"
    copies.mkdir()
    assessment_path = copies / assessment_source.name
    batch_path = copies / batch_source.name
    single_path = copies / single_source.name
    scope_path = copies / "scope.json"
    scope = json.loads(scope_source.read_text())
    assessment = json.loads(assessment_source.read_text())
    batch = json.loads(batch_source.read_text())
    single = json.loads(single_source.read_text())
    for old_path in (assessment_source, batch_source, single_source):
        del scope["protected_sha256"][str(old_path)]
    paths = (scope_path, assessment_path, batch_path, single_path, sessions)
    return paths, scope, assessment, batch, single


def save_case(
    paths: tuple[Path, Path, Path, Path, Path],
    scope: dict[str, Any],
    assessment: dict[str, Any],
    batch: dict[str, Any],
    single: dict[str, Any],
) -> None:
    scope_path, assessment_path, batch_path, single_path, _ = paths
    for path, value in ((batch_path, batch), (single_path, single)):
        path.write_text(json.dumps(value) + "\n")
        assessment["raw_files"][path.name] = {
            "sha256": evidence.sha256(path),
            "bytes": path.stat().st_size,
        }
    assessment_path.write_text(json.dumps(assessment) + "\n")
    for path in (assessment_path, batch_path, single_path):
        scope["protected_sha256"][str(path)] = evidence.sha256(path)
    scope_path.write_text(json.dumps(scope) + "\n")


def test_fixed_raw_proof_and_determinism(
    tmp_path: Path, fixed_inputs: tuple[Path, Path, Path, Path, Path]
) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    assert evidence.main(arguments(fixed_inputs, first)) == 0
    assert evidence.main(arguments(fixed_inputs, second)) == 0
    for name in (
        "normalized-prices.json",
        "missing-sessions.json",
        "validation.json",
        "binding.json",
    ):
        assert (first / name).read_bytes() == (second / name).read_bytes()
    normalized = json.loads((first / "normalized-prices.json").read_text())
    missing = json.loads((first / "missing-sessions.json").read_text())
    validation = json.loads((first / "validation.json").read_text())
    assert len(normalized["bars"]) == 1683
    assert validation["counts"] == {
        "bars": 1683,
        "expected_sessions": 272,
        "not_queried_individually": 6,
        "queried_symbols": 16,
        "rapt_bars": 138,
        "tracked_symbols": 22,
        "warmup_sessions": 20,
        "with_bars": 9,
        "zero_bars": 7,
        "zero_volume_bars_retained": 84,
    }
    assert all(bar["evidence_only"] for bar in normalized["bars"])
    assert sum(bar["zero_volume"] for bar in normalized["bars"]) == 84
    by_symbol = {row["symbol"]: row for row in missing["per_symbol"]}
    assert len(by_symbol["AVNS"]["after_last_bar"]) == 34
    assert len(by_symbol["ALB-P-A"]["unanchored_no_bar_sessions"]) == 272
    assert by_symbol["BHAC"]["status"] == "zero_bars"
    assert all(value is False for value in validation["gates"].values())
    before = (first / "binding.json").read_bytes()
    assert evidence.main(arguments(fixed_inputs, first)) == 2
    assert (first / "binding.json").read_bytes() == before


@pytest.mark.parametrize(
    "mutation",
    [
        "duplicate",
        "bad_dst",
        "outside_window",
        "nonfinite",
        "bool_price",
        "bad_ohlc",
        "bool_volume",
        "negative_volume",
        "pagination",
        "rapt_mismatch",
        "malformed_status",
    ],
)
def test_mutated_source_rejected_without_output(
    tmp_path: Path,
    fixed_inputs: tuple[Path, Path, Path, Path, Path],
    mutation: str,
) -> None:
    paths, scope, assessment, batch, single = mutable_case(tmp_path, fixed_inputs)
    first = batch["bars"]["HSPT"][0]
    if mutation == "duplicate":
        batch["bars"]["HSPT"].append(dict(first))
        next(row for row in assessment["rows"] if row["symbol"] == "HSPT")["bars"] += 1
        assessment["batch_total_bars"] += 1
    elif mutation == "bad_dst":
        first["t"] = "2025-08-13T05:00:00Z"
    elif mutation == "outside_window":
        first["t"] = "2025-08-12T04:00:00Z"
    elif mutation == "nonfinite":
        first["o"] = "NaN"
    elif mutation == "bool_price":
        first["o"] = True
    elif mutation == "bad_ohlc":
        first["l"] = "10000"
    elif mutation == "bool_volume":
        first["v"] = True
    elif mutation == "negative_volume":
        first["v"] = -1
    elif mutation == "pagination":
        batch["next_page_token"] = "remaining"
    elif mutation == "rapt_mismatch":
        single["bars"][0]["c"] = "999"
    elif mutation == "malformed_status":
        assessment["rows"][0]["status"] = ["bars_found"]
    save_case(paths, scope, assessment, batch, single)
    output = tmp_path / "rejected"
    assert evidence.main(arguments(paths, output)) == 2
    assert not output.exists()


def test_protected_hash_drift(
    tmp_path: Path, fixed_inputs: tuple[Path, Path, Path, Path, Path]
) -> None:
    paths, scope, assessment, batch, single = mutable_case(tmp_path, fixed_inputs)
    save_case(paths, scope, assessment, batch, single)
    paths[2].write_text(paths[2].read_text() + " ")
    assert evidence.main(arguments(paths, tmp_path / "hash-drift")) == 2
    assert not (tmp_path / "hash-drift").exists()


def test_atomic_publish_preserves_racing_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "result"
    real_publish = evidence.publish_no_replace

    def race(staging: Path, output: Path) -> None:
        output.mkdir()
        (output / "owner.txt").write_text("other writer")
        real_publish(staging, output)

    monkeypatch.setattr(evidence, "publish_no_replace", race)
    with pytest.raises(evidence.InputError):
        evidence.write_fresh_output(destination, {"validation.json": {"inputs": {}}})
    assert (destination / "owner.txt").read_text() == "other writer"
    assert not list(tmp_path.glob(".result-*"))


def test_timestamp_and_number_units(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    row: dict[str, Any] = {
        "t": "2025-08-13T04:00:00Z",
        "o": "1.0000000000000000001",
        "h": "2",
        "l": "1",
        "c": "1.5",
        "v": 0,
    }
    bar = evidence.normalized_bar("TEST", row, {date(2025, 8, 13)}, source, "a" * 64)
    assert bar["open"] == "1.0000000000000000001"
    assert bar["zero_volume"] is True
    with pytest.raises(evidence.InputError):
        evidence.normalized_bar(
            "TEST",
            {**row, "t": "2025-08-13T04:00:00"},
            {date(2025, 8, 13)},
            source,
            "a" * 64,
        )
