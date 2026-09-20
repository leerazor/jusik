import json
from datetime import date

import pytest

from jusik.krx_status_evidence import parse_krx_status_evidence


def test_krx_status_evidence_requires_explicit_target_status_rows() -> None:
    body = json.dumps(
        {
            "rows": [
                {
                    "session": "2026-06-29",
                    "symbol": "000300",
                    "status": "trading_halt",
                }
            ]
        }
    ).encode()
    report = parse_krx_status_evidence(
        body, session=date(2026, 6, 29), target_symbols=("000300", "009440")
    )
    assert report.readiness == "insufficient"
    assert report.missing_symbols == ("009440",)


def test_krx_status_evidence_ready_with_unique_complete_rows() -> None:
    body = json.dumps(
        {
            "OutBlock_1": [
                {"BAS_DD": "20260629", "ISU_CD": "000300", "status": "trading_halt"},
                {"BAS_DD": "20260629", "ISU_CD": "009440", "status": "management"},
            ]
        }
    ).encode()
    report = parse_krx_status_evidence(
        body, session=date(2026, 6, 29), target_symbols=("000300", "009440")
    )
    assert report.readiness == "ready"
    assert report.duplicate_symbols == ()


def test_krx_status_evidence_rejects_implicit_status() -> None:
    body = json.dumps(
        {"rows": [{"session": "2026-06-29", "symbol": "000300", "reason": "halt"}]}
    ).encode()
    with pytest.raises(ValueError, match="explicit_status"):
        parse_krx_status_evidence(
            body, session=date(2026, 6, 29), target_symbols=("000300",)
        )
