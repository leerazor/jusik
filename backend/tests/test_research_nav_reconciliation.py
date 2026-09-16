from __future__ import annotations

import hashlib
import json
import os
from decimal import Decimal, getcontext
from pathlib import Path
from typing import cast

import pytest

from jusik.research_nav_reconciliation import (
    ReconciliationError,
    main,
    reconcile_json_bytes,
    reconcile_run_payload,
)


def payload(rows: list[dict[str, object]]) -> dict[str, object]:
    return {"result": {"equity": rows}}


def row(
    session: str = "2025-01-02",
    *,
    cash: object = "10",
    invested: object = "2",
    nav: object = "12",
) -> dict[str, object]:
    return {
        "session": session,
        "cash_krw": cash,
        "invested_krw": invested,
        "nav_krw": nav,
    }


def encoded(value: object) -> tuple[bytes, str]:
    raw = json.dumps(value, separators=(",", ":")).encode()
    return raw, hashlib.sha256(raw).hexdigest()


def test_exact_components_pass_and_preserve_rows() -> None:
    report = reconcile_run_payload(
        payload([row(), row("2025-01-03", cash="0", invested="0", nav="0")]),
        source_sha256="a" * 64,
    )
    assert report.status == "passed"
    assert report.rows[0].residual_krw == Decimal("0")
    assert report.rows[1].session.isoformat() == "2025-01-03"


@pytest.mark.parametrize(
    ("case", "value"),
    [
        ("signed one", row(cash="1", invested="2", nav="2")),
        ("signed negative one", row(cash="2", invested="2", nav="3")),
        ("excess positive", row(cash="10", invested="2", nav="13.01")),
        ("excess negative", row(cash="10", invested="2", nav="10.9")),
        ("negative cash", row(cash="-1")),
        ("negative invested", row(invested="-1")),
        ("negative nav", row(nav="-1")),
        ("nan", row(nav="NaN")),
        ("infinity", row(nav="Infinity")),
        (
            "missing component",
            {"session": "2025-01-02", "cash_krw": "1", "invested_krw": "2"},
        ),
        ("null component", row(nav=None)),
        ("boolean component", row(nav=True)),
        ("non numeric component", row(nav="wat")),
        ("duplicate session", [row(), row()]),
        ("reversed session", [row("2025-01-03"), row()]),
        ("holiday is observed only", [row("2025-01-03"), row("2025-01-06")]),
        ("date boundary", [row("0001-01-01"), row("9999-12-31")]),
        (
            "rounding independent",
            row(
                cash="0.12345678901234567890123456789",
                invested="0.00000000000000000000000000011",
                nav="0.12345678901234567890123456800",
            ),
        ),
    ],
)
def test_inventory_cases(case: str, value: object) -> None:
    del case
    if isinstance(value, list):
        rows = cast(list[dict[str, object]], value)
        first_session = cast(str, rows[0]["session"])
        second_session = cast(str, rows[1]["session"])
        if first_session == second_session or first_session > second_session:
            with pytest.raises(ReconciliationError):
                reconcile_run_payload(payload(rows), source_sha256="a" * 64)
        else:
            assert (
                reconcile_run_payload(payload(rows), source_sha256="a" * 64).status
                == "passed"
            )
        return
    values = cast(dict[str, object], value)
    nav = values.get("nav_krw")
    if nav in {"13.01", "10.9"}:
        report = reconcile_run_payload(payload([values]), source_sha256="a" * 64)
        assert report.status == "failed"
        assert report.failed_sessions == (report.rows[0].session,)
    elif nav == "0.12345678901234567890123456800":
        old = getcontext().prec
        getcontext().prec = 4
        try:
            assert (
                reconcile_run_payload(payload([values]), source_sha256="a" * 64).status
                == "passed"
            )
        finally:
            getcontext().prec = old
    elif nav in {"2", "3"} and values.get("cash_krw") in {"1", "2"}:
        assert (
            reconcile_run_payload(payload([values]), source_sha256="a" * 64).status
            == "passed"
        )
    else:
        with pytest.raises(ReconciliationError):
            reconcile_run_payload(payload([values]), source_sha256="a" * 64)


def test_missing_result_equity_and_empty_equity_are_rejected() -> None:
    invalid_payloads: tuple[dict[str, object], ...] = (
        {},
        {"result": {}},
        payload([]),
    )
    for value in invalid_payloads:
        with pytest.raises(ReconciliationError):
            reconcile_run_payload(value, source_sha256="a" * 64)


def test_duplicate_json_keys_are_rejected() -> None:
    raw = (
        b'{"result":{"equity":[{"session":"2025-01-02",'
        b'"cash_krw":"1","cash_krw":"1","invested_krw":"0",'
        b'"nav_krw":"1"}]}}'
    )
    with pytest.raises(ReconciliationError, match="duplicate"):
        reconcile_json_bytes(raw, expected_sha256=hashlib.sha256(raw).hexdigest())


def test_cli_artifacts_include_literal_boundaries_and_coverage(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    raw, sha = encoded(
        payload(
            [
                row("2025-01-02", cash="1", invested="2", nav="3"),
                row("2025-01-03", cash="1", invested="2", nav="4"),
                row("2025-01-04", cash="2", invested="2", nav="3"),
                row("2025-01-05", cash="1", invested="2", nav="4.01"),
                row("2025-01-06", cash="1", invested="2", nav="1.99"),
            ]
        )
    )
    source = tmp_path / "run.json"
    source.write_bytes(raw)
    residual = tmp_path / "residual.json"
    coverage = tmp_path / "coverage.json"

    assert (
        main(
            [
                "--input",
                str(source),
                "--expected-sha256",
                sha,
                "--residual-output",
                str(residual),
                "--coverage-output",
                str(coverage),
            ]
        )
        == 1
    )
    residual_artifact = json.loads(residual.read_text(encoding="utf-8"))
    coverage_artifact = json.loads(coverage.read_text(encoding="utf-8"))
    assert residual_artifact["source_sha256"] == sha
    assert residual_artifact["rows"] == 5
    assert residual_artifact["unique_sessions"] == 5
    assert residual_artifact["max_absolute_residual_krw"] == "1.01"
    assert residual_artifact["failed_sessions"] == ["2025-01-05", "2025-01-06"]
    assert [item["cash_krw"] for item in residual_artifact["residuals"]] == [
        "1",
        "1",
        "2",
        "1",
        "1",
    ]
    assert [item["invested_krw"] for item in residual_artifact["residuals"]] == [
        "2",
        "2",
        "2",
        "2",
        "2",
    ]
    assert [item["nav_krw"] for item in residual_artifact["residuals"]] == [
        "3",
        "4",
        "3",
        "4.01",
        "1.99",
    ]
    assert [item["residual_krw"] for item in residual_artifact["residuals"]] == [
        "0",
        "1",
        "-1",
        "1.01",
        "-1.01",
    ]
    assert [item["passed"] for item in residual_artifact["residuals"]] == [
        True,
        True,
        True,
        False,
        False,
    ]
    assert coverage_artifact["source_sha256"] == sha
    assert coverage_artifact["observed_sessions"] == 5
    assert coverage_artifact["unique_sessions"] == 5
    assert coverage_artifact["first_session"] == "2025-01-02"
    assert coverage_artifact["last_session"] == "2025-01-06"
    assert coverage_artifact["ordered"] is True
    assert coverage_artifact["calendar_completeness"] == "unavailable"
    assert "status" in capsys.readouterr().out


def test_cli_invalid_utf8_returns_exit_two_without_artifacts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    raw = b"\xff"
    source = tmp_path / "run.json"
    source.write_bytes(raw)
    residual = tmp_path / "residual.json"
    coverage = tmp_path / "coverage.json"

    assert (
        main(
            [
                "--input",
                str(source),
                "--expected-sha256",
                hashlib.sha256(raw).hexdigest(),
                "--residual-output",
                str(residual),
                "--coverage-output",
                str(coverage),
            ]
        )
        == 2
    )
    assert not residual.exists()
    assert not coverage.exists()
    captured = capsys.readouterr()
    assert "input is not valid JSON" in captured.err
    assert "Traceback" not in captured.err


def test_cli_rejects_sha_mismatch_without_overwriting_source(tmp_path: Path) -> None:
    raw, _ = encoded(payload([row()]))
    source = tmp_path / "run.json"
    source.write_bytes(raw)
    before = source.read_bytes()
    assert (
        main(
            [
                "--input",
                str(source),
                "--expected-sha256",
                "b" * 64,
                "--residual-output",
                str(source),
                "--coverage-output",
                str(tmp_path / "coverage.json"),
            ]
        )
        == 2
    )
    assert source.read_bytes() == before


def test_cli_prevalidates_source_collision_before_any_artifact_write(
    tmp_path: Path,
) -> None:
    raw, sha = encoded(payload([row()]))
    source = tmp_path / "run.json"
    source.write_bytes(raw)
    residual = tmp_path / "residual.json"
    residual.write_bytes(b"keep")
    coverage = tmp_path / "coverage.json"

    assert (
        main(
            [
                "--input",
                str(source),
                "--expected-sha256",
                sha,
                "--residual-output",
                str(residual),
                "--coverage-output",
                str(source),
            ]
        )
        == 2
    )
    assert residual.read_bytes() == b"keep"
    assert source.read_bytes() == raw
    assert not coverage.exists()


def test_cli_rejects_hardlink_and_symlink_aliases(tmp_path: Path) -> None:
    raw, sha = encoded(payload([row()]))
    source = tmp_path / "run.json"
    source.write_bytes(raw)

    hardlink_output = tmp_path / "hardlink.json"
    os.link(source, hardlink_output)
    assert (
        main(
            [
                "--input",
                str(source),
                "--expected-sha256",
                sha,
                "--residual-output",
                str(hardlink_output),
                "--coverage-output",
                str(tmp_path / "coverage-hardlink.json"),
            ]
        )
        == 2
    )

    nested = tmp_path / "nested"
    nested.mkdir()
    relative_output = nested / ".." / "relative.json"
    canonical_output = tmp_path / "relative.json"
    assert (
        main(
            [
                "--input",
                str(source),
                "--expected-sha256",
                sha,
                "--residual-output",
                str(relative_output),
                "--coverage-output",
                str(canonical_output),
            ]
        )
        == 2
    )

    symlink_output = tmp_path / "symlink.json"
    symlink_output.symlink_to(source)
    assert (
        main(
            [
                "--input",
                str(source),
                "--expected-sha256",
                sha,
                "--residual-output",
                str(tmp_path / "residual-symlink.json"),
                "--coverage-output",
                str(symlink_output),
            ]
        )
        == 2
    )


def test_cli_rejects_output_alias_before_partial_write(tmp_path: Path) -> None:
    raw, sha = encoded(payload([row()]))
    source = tmp_path / "run.json"
    source.write_bytes(raw)
    residual = tmp_path / "residual.json"
    residual.write_bytes(b"keep")
    coverage = tmp_path / "coverage.json"
    os.link(residual, coverage)

    assert (
        main(
            [
                "--input",
                str(source),
                "--expected-sha256",
                sha,
                "--residual-output",
                str(residual),
                "--coverage-output",
                str(coverage),
            ]
        )
        == 2
    )
    assert residual.read_bytes() == b"keep"
    assert coverage.read_bytes() == b"keep"
