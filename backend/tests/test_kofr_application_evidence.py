from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

import pytest

from jusik.kofr_application_evidence import (
    KofrApplicationError,
    validate_application_contract,
    validate_nav_date_application,
)


def _fixture(tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "source.json"
    source.write_text(
        json.dumps(
            {
                "schema": "kofr-source-evidence/v1",
                "rows": [
                    {
                        "RFR_PUBN_DT": "2026.09.11",
                        "RFR_PUBN_MR": " 3.075",
                        "PUBN_DTTM": "2026.09.11 10:50:15",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    manifest = tmp_path / "application.json"
    manifest.write_text(
        json.dumps(
            {
                "schema": "kofr-risk-free-application/v1",
                "source_evidence_sha256": hashlib.sha256(
                    source.read_bytes()
                ).hexdigest(),
                "timezone": "Asia/Seoul",
                "publication_timestamp_semantics": "local_wall_time",
                "coverage_status": "complete",
                "business_dates": ["2026-09-11"],
                "intervals": [
                    {
                        "start": "2026-09-14",
                        "end": "2026-09-15",
                        "source_observed_on": "2026-09-11",
                        "annual_rate": "3.075",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return source, manifest


def test_valid_application_contract(tmp_path: Path) -> None:
    source, manifest = _fixture(tmp_path)
    report = validate_application_contract(source, manifest)
    assert report.timezone == "Asia/Seoul"
    assert str(report.intervals[0].annual_rate) == "3.075"


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("timezone", "UTC", "unsupported_timezone"),
        ("coverage_status", "unknown", "business_date_completeness_unverified"),
        ("publication_timestamp_semantics", "utc", "publication_semantics_required"),
    ],
)
def test_application_contract_fails_closed(
    tmp_path: Path, field: str, value: str, error: str
) -> None:
    source, manifest = _fixture(tmp_path)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload[field] = value
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(KofrApplicationError, match=error):
        validate_application_contract(source, manifest)


def test_application_contract_rejects_publication_after_interval_start(
    tmp_path: Path,
) -> None:
    source, manifest = _fixture(tmp_path)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["intervals"][0]["start"] = "2026-09-11"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(KofrApplicationError, match="publication_after_interval_start"):
        validate_application_contract(source, manifest)


def test_complete_manifest_must_declare_every_source_date(tmp_path: Path) -> None:
    source, manifest = _fixture(tmp_path)
    source_payload = json.loads(source.read_text(encoding="utf-8"))
    source_payload["rows"].append(
        {
            "RFR_PUBN_DT": "2026.09.12",
            "RFR_PUBN_MR": "3.000",
            "PUBN_DTTM": "2026.09.12 10:50:15",
        }
    )
    source.write_text(json.dumps(source_payload), encoding="utf-8")
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["source_evidence_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(KofrApplicationError, match="business_date_manifest_mismatch"):
        validate_application_contract(source, manifest)


def test_nav_date_application_rejects_uncovered_dates(tmp_path: Path) -> None:
    source, manifest = _fixture(tmp_path)
    report = validate_application_contract(source, manifest)
    with pytest.raises(KofrApplicationError, match="nav_date_application_missing"):
        validate_nav_date_application(report, [date(2026, 9, 11), date(2026, 9, 12)])
