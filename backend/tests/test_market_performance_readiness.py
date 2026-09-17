from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from typing import cast

import pytest

import jusik.market_performance_policy as readiness_policy
import jusik.market_performance_readiness as readiness
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
CANONICAL_MANIFEST_PATH = Path(
    "/home/kwl/.local/share/jusik/portfolio-audit/"
    "20260915-r0-baseline/r0-baseline-freeze/baseline-manifest.json"
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


def test_canonical_session_evidence_removes_exactly_four_codes_and_is_deterministic(
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
        "missing_risk_free_evidence",
    ]
    assert first["status"] == "blocked"
    assert first["ready_for_metrics"] is False
    assert first["economic_evaluation"] == "not-evaluated"
    assert first["calculation_policy"] == {
        "id": "market-performance-calculation-policy-v1",
        "artifact_sha256": readiness_policy.POLICY_SHA256,
        "evaluator_source_sha256": readiness_policy.load_calculation_policy()[
            "implementation"
        ]["evaluator_source_sha256"],
        "scope": "forward-only",
        "historical_application_proven": False,
    }
    assert first["session_evidence"]["expected_count"] == 252
    assert first["session_evidence"]["observed_count"] == 252
    expected = [
        row["date"]
        for row in json.loads(readiness.TRACKED_CALENDAR_PATH.read_bytes())[
            "calendars"
        ]["XNYS"]
        if row["state"] == "session" and "2025-09-11" <= row["date"] <= "2026-09-11"
    ]
    observed = [row["session"] for row in json.loads(original_run)["result"]["equity"]]
    assert first["session_evidence"]["expected_sessions"] == expected
    assert first["session_evidence"]["observed_sessions"] == observed
    assert expected == observed
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


def test_manifest_bytes_and_calendar_bytes_are_independently_fail_closed(
    tmp_path: Path,
) -> None:
    manifest_copy = tmp_path / "manifest.json"
    manifest_copy.write_bytes(CANONICAL_MANIFEST_PATH.read_bytes() + b"\n")
    with pytest.raises(ReadinessInputError) as error:
        diagnose_canonical_run(
            CANONICAL_RUN_PATH,
            manifest_path=manifest_copy,
        )
    assert error.value.code == "manifest_sha_mismatch"

    calendar_payload = json.loads(readiness.TRACKED_CALENDAR_PATH.read_bytes())
    calendar_payload["calendars"]["XNYS"][0]["state"] = "session"
    calendar_payload["calendars_sha256"] = hashlib.sha256(
        json.dumps(
            calendar_payload["calendars"],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    calendar_copy = tmp_path / "calendar.json"
    calendar_copy.write_text(
        json.dumps(calendar_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ReadinessInputError) as error:
        diagnose_canonical_run(CANONICAL_RUN_PATH, calendar_path=calendar_copy)
    assert error.value.code == "calendar_sha_mismatch"


def _reverse_equity_rows(payload: dict[str, object]) -> None:
    equity = cast(dict[str, object], payload["result"])["equity"]
    rows = cast(list[object], equity)
    rows[10], rows[11] = rows[11], rows[10]


def _trusted_copies(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    mutate_run: Callable[[dict[str, object]], None] | None = None,
    mutate_manifest: Callable[[dict[str, object]], None] | None = None,
    mutate_calendar: Callable[[dict[str, object]], None] | None = None,
) -> tuple[Path, Path, Path | None, Path | None]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    run_payload = json.loads(CANONICAL_RUN_PATH.read_bytes())
    if mutate_run is not None:
        mutate_run(run_payload)
    run_copy = tmp_path / "run.json"
    run_copy.write_text(
        json.dumps(run_payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    run_sha = hashlib.sha256(run_copy.read_bytes()).hexdigest()

    manifest_payload = json.loads(CANONICAL_MANIFEST_PATH.read_bytes())
    manifest_payload["artifacts"]["run"]["path"] = str(run_copy)
    manifest_payload["artifacts"]["run"]["sha256"] = run_sha
    if mutate_manifest is not None:
        mutate_manifest(manifest_payload)
    manifest_copy = tmp_path / "manifest.json"
    manifest_copy.write_text(
        json.dumps(manifest_payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    manifest_sha = hashlib.sha256(manifest_copy.read_bytes()).hexdigest()

    evidence_payload = json.loads(CANONICAL_EVIDENCE_PATH.read_bytes())
    evidence_payload["manifest"]["sha256"] = manifest_sha
    evidence_payload["manifest"]["run_sha256"] = run_sha
    evidence_payload["run_sha256"] = run_sha

    calendar_payload = json.loads(readiness.TRACKED_CALENDAR_PATH.read_bytes())
    calendar_copy: Path | None = None
    if mutate_calendar is not None:
        mutate_calendar(calendar_payload)
        calendar_copy = tmp_path / "calendar.json"
        calendar_copy.write_text(
            json.dumps(calendar_payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        calendar_bytes_sha = hashlib.sha256(calendar_copy.read_bytes()).hexdigest()
        calendar_payload_sha = hashlib.sha256(
            json.dumps(
                calendar_payload["calendars"],
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        evidence_payload["calendar"]["bytes_sha256"] = calendar_bytes_sha
        evidence_payload["calendar"]["payload_sha256"] = calendar_payload_sha
        monkeypatch.setattr(readiness, "CALENDAR_BYTES_SHA256", calendar_bytes_sha)
        monkeypatch.setattr(readiness, "CALENDAR_PAYLOAD_SHA256", calendar_payload_sha)

    _refresh_session_facts(evidence_payload, run_payload, calendar_payload)

    evidence_copy = tmp_path / "evidence.json"
    evidence_copy.write_text(
        json.dumps(evidence_payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    evidence_sha = hashlib.sha256(evidence_copy.read_bytes()).hexdigest()
    monkeypatch.setattr(readiness, "CANONICAL_RUN_SHA256", run_sha)
    monkeypatch.setattr(readiness, "CANONICAL_MANIFEST_SHA256", manifest_sha)
    monkeypatch.setattr(readiness, "CANONICAL_EVIDENCE_SHA256", evidence_sha)
    return run_copy, evidence_copy, manifest_copy, calendar_copy


def _refresh_session_facts(
    evidence: dict[str, object],
    run: dict[str, object],
    calendar: dict[str, object],
) -> None:
    calendars = cast(dict[str, object], calendar["calendars"])
    xnys = cast(list[dict[str, object]], calendars["XNYS"])
    expected = [
        cast(str, row["date"])
        for row in xnys
        if row["state"] == "session"
        and "2025-09-11" <= cast(str, row["date"]) <= "2026-09-11"
    ]
    unavailable = [
        cast(str, row["date"])
        for row in xnys
        if row["state"] == "unavailable"
        and "2025-09-11" <= cast(str, row["date"]) <= "2026-09-11"
    ]
    result = cast(dict[str, object], run["result"])
    equity = cast(list[dict[str, object]], result["equity"])
    observed = [cast(str, row["session"]) for row in equity]

    def digest(values: list[str]) -> str:
        return hashlib.sha256(
            json.dumps(
                values,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()

    sessions = cast(dict[str, object], evidence["sessions"])
    for name, values in (("expected", expected), ("observed", observed)):
        sessions[name] = {
            "count": len(values),
            "sha256": digest(values),
            "first": values[0] if values else None,
            "last": values[-1] if values else None,
        }
    sessions["missing"] = sorted(set(expected) - set(observed))
    sessions["extra"] = sorted(set(observed) - set(expected))
    sessions["duplicates"] = sorted(
        {value for value in observed if observed.count(value) > 1}
    )
    sessions["unavailable"] = unavailable


def _insert_us_holiday(payload: dict[str, object]) -> None:
    equity = cast(dict[str, object], payload["result"])["equity"]
    rows = cast(list[dict[str, object]], equity)
    holiday = "2025-11-27"
    index = next(
        index for index, row in enumerate(rows) if cast(str, row["session"]) > holiday
    )
    rows.insert(index, {**rows[index], "session": holiday})


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        (
            lambda payload: payload["artifacts"]["run"].__setitem__(
                "path", "/tmp/wrong-canonical-run.json"
            ),
            "manifest_run_path_mismatch",
        ),
        (
            lambda payload: payload["artifacts"]["run"].__setitem__("sha256", "0" * 64),
            "manifest_run_sha_mismatch",
        ),
        (
            lambda payload: payload["run"]["period"].__setitem__("start", "2025-09-10"),
            "manifest_period_mismatch",
        ),
        (
            lambda payload: payload["run"]["request"].__setitem__(
                "end_date", "2026-09-10"
            ),
            "manifest_request_mismatch",
        ),
    ],
)
def test_trusted_manifest_internal_guards_are_reached(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: Callable[[dict[str, object]], None],
    expected_code: str,
) -> None:
    run_copy, evidence_copy, manifest_copy, _ = _trusted_copies(
        tmp_path, monkeypatch, mutate_manifest=mutation
    )
    with pytest.raises(ReadinessInputError) as error:
        diagnose_canonical_run(
            run_copy,
            evidence_copy,
            manifest_path=manifest_copy,
        )
    assert error.value.code == expected_code


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        (
            lambda payload: payload["result"]["equity"].pop(10),
            "session_evidence_mismatch",
        ),
        (
            _insert_us_holiday,
            "session_evidence_mismatch",
        ),
        (
            lambda payload: payload["result"]["equity"].__setitem__(
                10, payload["result"]["equity"][9]
            ),
            "duplicate_session",
        ),
        (
            lambda payload: _reverse_equity_rows(payload),
            "reverse_session_order",
        ),
    ],
)
def test_trusted_run_date_reconciliation_is_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: Callable[[dict[str, object]], None],
    expected_code: str,
) -> None:
    run_copy, evidence_copy, manifest_copy, _ = _trusted_copies(
        tmp_path, monkeypatch, mutate_run=mutation
    )
    with pytest.raises(ReadinessInputError) as error:
        diagnose_canonical_run(
            run_copy,
            evidence_copy,
            manifest_path=manifest_copy,
        )
    assert error.value.code == expected_code


def test_trusted_calendar_unavailable_and_clock_mutations_are_scoped(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable(payload: dict[str, object]) -> None:
        calendars = cast(dict[str, object], payload["calendars"])
        xnys = cast(list[dict[str, object]], calendars["XNYS"])
        next(row for row in xnys if row["date"] == "2025-09-12")["state"] = (
            "unavailable"
        )
        payload["calendars_sha256"] = hashlib.sha256(
            json.dumps(
                calendars,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()

    run_copy, evidence_copy, manifest_copy, calendar_copy = _trusted_copies(
        tmp_path, monkeypatch, mutate_calendar=unavailable
    )
    with pytest.raises(ReadinessInputError) as error:
        diagnose_canonical_run(
            run_copy,
            evidence_copy,
            manifest_path=manifest_copy,
            calendar_path=calendar_copy,
        )
    assert error.value.code == "session_evidence_mismatch"

    def clocks(payload: dict[str, object]) -> None:
        calendars = cast(dict[str, object], payload["calendars"])
        xnys = cast(list[dict[str, object]], calendars["XNYS"])
        dst = next(row for row in xnys if row["date"] == "2025-11-03")
        early_close = next(row for row in xnys if row["date"] == "2025-11-28")
        dst["open_at"] = "2025-11-03T13:31:00Z"
        early_close["close_at"] = "2025-11-28T17:59:00Z"
        payload["calendars_sha256"] = hashlib.sha256(
            json.dumps(
                calendars,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()

    run_copy, evidence_copy, manifest_copy, calendar_copy = _trusted_copies(
        tmp_path / "clocks", monkeypatch, mutate_calendar=clocks
    )
    report = diagnose_canonical_run(
        run_copy,
        evidence_copy,
        manifest_path=manifest_copy,
        calendar_path=calendar_copy,
    )
    assert report["missing"] == [
        "missing_initial_capital_at",
        "missing_nav_timestamps",
        "missing_risk_free_evidence",
    ]
