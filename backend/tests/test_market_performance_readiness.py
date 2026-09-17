from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import cast

import pytest

from jusik.market_performance_readiness import (
    CANONICAL_EVIDENCE_PATH,
    CANONICAL_EVIDENCE_SHA256,
    CANONICAL_RUN_SHA256,
    MISSING_CODES,
    ReadinessInputError,
    diagnose_canonical_run,
    diagnose_run,
    main,
    render_report,
)

CANONICAL_RUN_PATH = Path(
    "/home/kwl/.local/share/jusik/portfolio-audit/"
    "20260915-market-data-live-contract-fixes/us-web-pilot-run.json"
)


def _canonical(*, sessions: list[str] | None = None) -> dict[str, object]:
    dates = sessions or ["2025-09-11", "2025-09-12", "2025-09-15"]
    request: dict[str, object] = {
        "market": "US",
        "stage": "pilot",
        "research_grade": "approximate",
        "start_date": "2025-09-11",
        "end_date": "2026-09-11",
        "initial_cash_krw": "100000000",
        "fee_rate": "0.00015",
        "slippage_rate": "0.001",
        "sell_tax_rate": "0.0018",
        "pilot_run_id": None,
    }
    readiness = {
        "market": "US",
        "checked_at": "2026-09-15T00:00:00Z",
        "capabilities": [
            {
                "name": name,
                "status": "ready",
                "detail": "fixture",
                "missing_ranges": [],
            }
            for name in (
                "credentials",
                "entitlement",
                "calendar",
                "membership",
                "bars",
                "actions",
                "fx",
                "policy",
            )
        ],
        "ready": True,
        "simulated": False,
        "research_grade": "approximate",
    }
    equity = [
        {
            "session": session,
            "cash_krw": "100000000",
            "cash_native": "72099.61",
            "invested_krw": "0",
            "nav_krw": str(100000000 - index * 100),
            "fx_krw_per_usd": "1386.97",
            "drawdown_pct": "0",
        }
        for index, session in enumerate(dates)
    ]
    result: dict[str, object] = {
        "market": "US",
        "request": deepcopy(request),
        "readiness": readiness,
        "status": "approximate",
        "completeness": "approximate",
        "candidate_evidence": [],
        "trades": [],
        "equity": equity,
        "limitations": ["approximate"],
        "metrics": {"coverage_sessions": "3"},
        "input_hash": "a" * 64,
        "policy_hash": "b" * 64,
        "stage": "pilot",
        "pilot_run_id": None,
        "data_contract_hash": "c" * 64,
        "warmup_sessions": [],
        "research_grade": "approximate",
        "pool_contract_hash": "d" * 64,
        "provenance": {
            "universe_sources": ["alpha_vantage"],
            "bar_sources": ["yahoo"],
            "fx_sources": ["fred"],
        },
    }
    return {
        "id": "run-12345678",
        "status": "completed",
        "request": request,
        "result": result,
        "input_hash": None,
        "created_at": "2026-09-15T00:00:00Z",
        "updated_at": "2026-09-15T00:00:01Z",
        "error": None,
        "stage": "pilot",
        "pilot_run_id": None,
        "data_contract_hash": "c" * 64,
        "final_promotable": False,
        "final_promotability_reason": "not promotable",
    }


def _write_run(
    tmp_path: Path, payload: dict[str, object], raw: bytes | None = None
) -> tuple[Path, str]:
    path = tmp_path / "run.json"
    body = (
        raw if raw is not None else json.dumps(payload, separators=(",", ":")).encode()
    )
    path.write_bytes(body)
    return path, hashlib.sha256(body).hexdigest()


def test_canonical_run_is_blocked_with_exact_missing_order(tmp_path: Path) -> None:
    path, digest = _write_run(tmp_path, _canonical())
    report = diagnose_run(path, digest)
    assert report["schema"] == "market-performance-readiness/v1"
    assert report["target"] == "market-performance-metrics-input/v1"
    assert report["status"] == "blocked"
    assert report["ready_for_metrics"] is False
    assert report["economic_evaluation"] == "not-evaluated"
    assert report["missing"] == list(MISSING_CODES)


def test_grade_simulated_sources_and_cost_pointers_are_preserved(
    tmp_path: Path,
) -> None:
    payload = _canonical()
    cast(dict[str, object], cast(dict[str, object], payload["result"])["readiness"])[
        "simulated"
    ] = True
    path, digest = _write_run(tmp_path, payload)
    report = diagnose_run(path, digest)
    source = cast(dict[str, object], report["source"])
    costs = cast(dict[str, object], report["cost_assumptions"])
    assert source["research_grade"] == "approximate"
    assert source["simulated"] is True
    assert source["source"] == {
        "universe_sources": ["alpha_vantage"],
        "bar_sources": ["yahoo"],
        "fx_sources": ["fred"],
    }
    assert costs["fee_rate"] == "0.00015"
    assert costs["slippage_rate"] == "0.001"
    assert costs["sell_tax_rate"] == "0.0018"
    assert costs["pointer"] == "request"


@pytest.mark.parametrize("field", ["created_at", "updated_at"])
def test_timestamps_do_not_supply_missing_anchor(tmp_path: Path, field: str) -> None:
    payload = _canonical()
    payload[field] = "2025-09-11T00:00:00Z"
    path, digest = _write_run(tmp_path, payload)
    assert diagnose_run(path, digest)["missing"] == list(MISSING_CODES)


def test_ready_calendar_and_recorded_rates_do_not_supply_evidence(
    tmp_path: Path,
) -> None:
    payload = _canonical()
    result = cast(dict[str, object], payload["result"])
    readiness = cast(dict[str, object], result["readiness"])
    readiness["ready"] = True
    path, digest = _write_run(tmp_path, payload)
    assert diagnose_run(path, digest)["missing"] == list(MISSING_CODES)


@pytest.mark.parametrize("field", ["fee_rate", "slippage_rate", "sell_tax_rate"])
def test_pilot_mandate_costs_are_strict(tmp_path: Path, field: str) -> None:
    payload = _canonical()
    request = cast(dict[str, object], payload["request"])
    request[field] = "0"
    cast(dict[str, object], payload["result"])["request"] = deepcopy(request)
    path, digest = _write_run(tmp_path, payload)
    with pytest.raises(ReadinessInputError) as error:
        diagnose_run(path, digest)
    assert error.value.code == "malformed_input"


def test_pilot_reference_and_period_are_strict(tmp_path: Path) -> None:
    for mutation in ("pilot_run_id", "period"):
        payload = _canonical()
        request = cast(dict[str, object], payload["request"])
        if mutation == "pilot_run_id":
            request["pilot_run_id"] = "prior-run-123"
        else:
            request["start_date"] = "2025-09-10"
        cast(dict[str, object], payload["result"])["request"] = deepcopy(request)
        path, digest = _write_run(tmp_path, payload)
        with pytest.raises(ReadinessInputError) as error:
            diagnose_run(path, digest)
        assert error.value.code == "malformed_input"


@pytest.mark.parametrize("run_id", ["short", "r" * 65])
def test_run_id_length_is_strict(tmp_path: Path, run_id: str) -> None:
    payload = _canonical()
    payload["id"] = run_id
    path, digest = _write_run(tmp_path, payload)
    with pytest.raises(ReadinessInputError) as error:
        diagnose_run(path, digest)
    assert error.value.code == "malformed_input"


@pytest.mark.parametrize("field", ["stage", "request.research_grade"])
def test_raw_omission_is_rejected(tmp_path: Path, field: str) -> None:
    payload = _canonical()
    if field == "stage":
        payload.pop("stage")
    else:
        cast(dict[str, object], payload["request"]).pop("research_grade")
    path, digest = _write_run(tmp_path, payload)
    with pytest.raises(ReadinessInputError) as error:
        diagnose_run(path, digest)
    assert error.value.code == "missing_required_field"


def test_request_result_mismatch_is_rejected(tmp_path: Path) -> None:
    payload = _canonical()
    cast(dict[str, object], cast(dict[str, object], payload["result"])["request"])[
        "end_date"
    ] = "2026-01-01"
    path, digest = _write_run(tmp_path, payload)
    with pytest.raises(ReadinessInputError) as error:
        diagnose_run(path, digest)
    assert error.value.code == "request_result_mismatch"


@pytest.mark.parametrize("mutation", ["ready_type", "capability_consistency"])
def test_readiness_raw_schema_is_strict(tmp_path: Path, mutation: str) -> None:
    payload = _canonical()
    readiness = cast(
        dict[str, object], cast(dict[str, object], payload["result"])["readiness"]
    )
    if mutation == "ready_type":
        readiness["ready"] = "true"
    else:
        readiness["ready"] = True
        cast(list[object], readiness["capabilities"])[0]["status"] = "partial"
    path, digest = _write_run(tmp_path, payload)
    with pytest.raises(ReadinessInputError) as error:
        diagnose_run(path, digest)
    assert error.value.code == "malformed_input"


@pytest.mark.parametrize("mutation", ["source", "hash"])
def test_emitted_provenance_and_hash_facts_are_strict(
    tmp_path: Path, mutation: str
) -> None:
    payload = _canonical()
    result = cast(dict[str, object], payload["result"])
    if mutation == "source":
        cast(dict[str, object], result["provenance"])["bar_sources"] = ["unknown"]
    else:
        result["policy_hash"] = "not-a-sha"
    path, digest = _write_run(tmp_path, payload)
    with pytest.raises(ReadinessInputError) as error:
        diagnose_run(path, digest)
    assert error.value.code == "malformed_input"


def test_generic_identity_cannot_claim_registered_canonical_acceptance(
    tmp_path: Path,
) -> None:
    path, digest = _write_run(tmp_path, _canonical())
    assert diagnose_run(path, digest)["canonical"] is False
    with pytest.raises(ReadinessInputError) as error:
        diagnose_run(path, CANONICAL_RUN_SHA256)
    assert error.value.code == "source_sha_mismatch"
    with pytest.raises(ReadinessInputError) as error:
        diagnose_run(path, digest, canonical=True)
    assert error.value.code == "canonical_sha_required"
    with pytest.raises(ReadinessInputError) as error:
        diagnose_canonical_run(path)
    assert error.value.code == "source_sha_mismatch"


def test_sha_schema_duplicate_and_nonfinite_errors_are_safe(tmp_path: Path) -> None:
    payload = _canonical()
    path, digest = _write_run(tmp_path, payload)
    with pytest.raises(ReadinessInputError) as error:
        diagnose_run(path, "0" * 64)
    assert error.value.code == "source_sha_mismatch"
    raw = (
        json.dumps(payload, separators=(",", ":"))
        .encode()
        .replace(b'"id":', b'"schema":"bad","id":')
    )
    schema_path, schema_digest = _write_run(tmp_path, payload, raw=raw)
    with pytest.raises(ReadinessInputError) as error:
        diagnose_run(schema_path, schema_digest)
    assert error.value.code == "unsupported_schema"
    duplicate_path, duplicate_digest = _write_run(
        tmp_path,
        payload,
        raw=b'{"id":"run-12345678","id":"run-87654321"}',
    )
    with pytest.raises(ReadinessInputError) as error:
        diagnose_run(duplicate_path, duplicate_digest)
    assert error.value.code == "malformed_input"
    nonfinite = (
        json.dumps(payload, separators=(",", ":"))
        .encode()
        .replace(b'"initial_cash_krw":"100000000"', b'"initial_cash_krw":NaN')
    )
    nonfinite_path, nonfinite_digest = _write_run(tmp_path, payload, raw=nonfinite)
    with pytest.raises(ReadinessInputError) as error:
        diagnose_run(nonfinite_path, nonfinite_digest)
    assert error.value.code == "malformed_input"


@pytest.mark.parametrize(
    ("sessions", "code"),
    [
        (["2025-09-11", "2025-09-11"], "duplicate_session"),
        (["2025-09-12", "2025-09-11"], "reverse_session_order"),
        (["2024-09-11"], "session_out_of_period"),
    ],
)
def test_session_and_nav_boundaries_are_rejected(
    tmp_path: Path, sessions: list[str], code: str
) -> None:
    payload = _canonical(sessions=sessions)
    path, digest = _write_run(tmp_path, payload)
    with pytest.raises(ReadinessInputError) as error:
        diagnose_run(path, digest)
    assert error.value.code == code
    bad = _canonical()
    cast(list[object], cast(dict[str, object], bad["result"])["equity"])[0][
        "nav_krw"
    ] = "0"
    bad_path, bad_digest = _write_run(tmp_path, bad)
    with pytest.raises(ReadinessInputError) as error:
        diagnose_run(bad_path, bad_digest)
    assert error.value.code == "nonpositive_nav"


def test_size_limit_and_cli_are_read_only_and_deterministic(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    payload = _canonical()
    path, digest = _write_run(tmp_path, payload)
    original = path.read_bytes()
    assert main(["--run", str(path), "--expected-sha256", digest]) == 0
    first = capsys.readouterr().out
    assert main(["--run", str(path), "--expected-sha256", digest]) == 0
    second = capsys.readouterr().out
    assert first == second == render_report(diagnose_run(path, digest)) + "\n"
    assert path.read_bytes() == original
    huge = tmp_path / "huge.json"
    huge.write_bytes(b'{"x":"' + b"a" * (10 * 1024 * 1024) + b'"}')
    with pytest.raises(ReadinessInputError) as error:
        diagnose_run(huge, hashlib.sha256(huge.read_bytes()).hexdigest())
    assert error.value.code == "source_too_large"


def test_canonical_session_evidence_removes_exactly_two_codes_and_is_deterministic(
    tmp_path: Path,
) -> None:
    original_run = CANONICAL_RUN_PATH.read_bytes()
    original_evidence = CANONICAL_EVIDENCE_PATH.read_bytes()
    evidence_copy = tmp_path / "evidence.json"
    evidence_copy.write_bytes(original_evidence)

    first = diagnose_canonical_run(CANONICAL_RUN_PATH, evidence_copy)
    second = diagnose_canonical_run(CANONICAL_RUN_PATH, evidence_copy)

    assert first == second
    assert first["missing"] == [
        "missing_initial_capital_at",
        "missing_nav_timestamps",
        "missing_cost_inclusion_evidence",
        "missing_risk_free_evidence",
        "missing_calculation_policy",
    ]
    assert first["status"] == "blocked"
    assert first["ready_for_metrics"] is False
    assert first["economic_evaluation"] == "not-evaluated"
    assert first["session_evidence"]["expected_count"] == 252
    assert first["session_evidence"]["observed_count"] == 252
    assert CANONICAL_RUN_PATH.read_bytes() == original_run
    assert evidence_copy.read_bytes() == original_evidence
    assert hashlib.sha256(original_evidence).hexdigest() == CANONICAL_EVIDENCE_SHA256


def test_canonical_evidence_is_fail_closed_and_generic_never_consumes_it(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "absent-evidence.json"
    with pytest.raises(ReadinessInputError) as error:
        diagnose_canonical_run(CANONICAL_RUN_PATH, missing)
    assert error.value.code == "evidence_unavailable"

    evidence_copy = tmp_path / "tampered-evidence.json"
    evidence_copy.write_bytes(CANONICAL_EVIDENCE_PATH.read_bytes() + b"\n")
    with pytest.raises(ReadinessInputError) as error:
        diagnose_canonical_run(CANONICAL_RUN_PATH, evidence_copy)
    assert error.value.code == "evidence_sha_mismatch"

    run_copy = tmp_path / "run.json"
    run_copy.write_bytes(CANONICAL_RUN_PATH.read_bytes())
    with pytest.raises(ReadinessInputError) as error:
        diagnose_run(
            run_copy,
            CANONICAL_RUN_SHA256,
            evidence_path=CANONICAL_EVIDENCE_PATH,
        )
    assert error.value.code == "canonical_evidence_requires_canonical"
