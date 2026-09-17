from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path

import pytest

from jusik.kofr_source_evidence import (
    ACTION,
    ENDPOINT,
    END_DATE,
    FIELDS,
    LANG,
    START_DATE,
    TASK,
    HttpResponse,
    KofrEvidenceError,
    collect,
    parse_response,
    request_xml,
    verify_evidence,
)


def _xml(*, count: int = 1, date_text: str = "2025.09.11", rate: str = "3.5000", extra: str = "") -> bytes:
    values = {
        "RFR_PUBN_DT": date_text,
        "RFR_PUBN_ISSN": "KOFR",
        "RFR_PUBN_MR": rate,
        "RFR_INDEX": "105.1234",
        "D30_AVG_MR": "3.5000",
        "D90_AVG_MR": "3.4000",
        "D180_AVG_MR": "3.3000",
        "PUBN_MR_STD_DT": date_text,
        "PUBN_DTTM": "2025.09.12 09:00:00",
        "LINK_DTTM": "2025.09.12 09:00:00",
        "LAST_MODFR_NO": "1",
        "LAST_MODF_DTTM": "2025.09.12 09:00:00",
    }
    fields = "".join(f'<{key} value="{value}"/>' for key, value in values.items())
    return f'<vector result="{count}"><data><result>{fields}{extra}</result></data></vector>'.encode()


class FakeTransport:
    def __init__(self, body: bytes, *, status: int = 200, headers: dict[str, str] | None = None) -> None:
        self.body = body
        self.status = status
        self.headers = headers or {"Content-Type": "application/xml; charset=utf-8"}
        self.calls = 0
        self.seen: tuple[str, bytes, float, dict[str, str]] | None = None

    def post(self, url: str, body: bytes, *, timeout: float, headers: Mapping[str, str]) -> HttpResponse:
        self.calls += 1
        self.seen = (url, body, timeout, dict(headers))
        return HttpResponse(self.status, self.headers, self.body)


def test_request_is_fixed_and_parser_preserves_decimal_text() -> None:
    request = request_xml().decode()
    assert f'task="{TASK}"' in request
    assert f'action="{ACTION}"' in request
    assert f'<LANG value="{LANG}"' in request
    assert f'<SEARCH_START_DATE value="{START_DATE}"' in request
    assert f'<SEARCH_END_DATE value="{END_DATE}"' in request
    rows, projection = parse_response(_xml(rate="0.000000000000000000123400"))
    assert set(rows[0]) == set(FIELDS)
    assert rows[0]["RFR_PUBN_MR"] == "0.000000000000000000123400"
    assert projection[0]["rate_decimal"] == "0.0000000000000000001234"
    zero_rows, zero_projection = parse_response(_xml(rate="-0.0000"))
    assert zero_rows[0]["RFR_PUBN_MR"] == "-0.0000"
    assert zero_projection[0]["rate_decimal"] == "0"


@pytest.mark.parametrize(
    ("body", "code"),
    [
        (_xml(count=2), "result_count_mismatch"),
        (_xml(extra='<RFR_PUBN_MR value="3.1"/>'), "malformed_result"),
        (_xml(date_text="2024.12.31"), "date_out_of_range"),
        (_xml(rate="NaN"), "nonfinite_value"),
        (_xml(rate="Infinity"), "nonfinite_value"),
        (_xml(extra="<BROKEN value=\"x\"/>"), "malformed_result"),
        (b"<!DOCTYPE response><response/>", "xml_dtd_or_entity"),
    ],
)
def test_parser_rejects_threats(body: bytes, code: str) -> None:
    with pytest.raises(KofrEvidenceError, match=code):
        parse_response(body)


def test_legacy_wrapper_and_record_count_shape_are_rejected() -> None:
    legacy = _xml().replace(b'<vector result="1">', b'<response><vector RECORD_COUNT="1">').replace(
        b"</vector>", b"</vector></response>"
    )
    with pytest.raises(KofrEvidenceError, match="unexpected_xml_root"):
        parse_response(legacy)


def test_duplicate_date_and_missing_field_are_rejected() -> None:
    one = _xml().decode()
    fields = one.split("<result>", 1)[1].split("</result>", 1)[0]
    body = f'<vector result="2"><data><result>{fields}</result></data><data><result>{fields}</result></data></vector>'.encode()
    with pytest.raises(KofrEvidenceError, match="duplicate_date"):
        parse_response(body)
    missing = _xml().replace(b'<RFR_INDEX value="105.1234"/>', b"")
    with pytest.raises(KofrEvidenceError, match="missing_required_field"):
        parse_response(missing)


def test_one_request_and_offline_reproducibility(tmp_path: Path) -> None:
    transport = FakeTransport(_xml())
    output = tmp_path / "evidence.json"
    evidence = collect(transport, audit_root=tmp_path / "audit", evidence_output=output)
    assert transport.calls == 1
    assert transport.seen is not None
    assert transport.seen[0] == ENDPOINT
    assert transport.seen[2] == 30.0
    assert output.exists()
    assert verify_evidence(output, tmp_path / "audit")["verified"] is True
    with pytest.raises(KofrEvidenceError, match="artifact_exists"):
        collect(FakeTransport(_xml()), audit_root=tmp_path / "audit")
    assert transport.calls == 1


def test_semantic_failure_freezes_bounded_raw_and_failure_metadata(tmp_path: Path) -> None:
    transport = FakeTransport(b"<vector result=\"1\"><data/></vector>")
    audit = tmp_path / "audit"
    with pytest.raises(KofrEvidenceError, match="malformed_data"):
        collect(transport, audit_root=audit)
    raw_files = list((audit / "raw").glob("*.xml"))
    assert len(raw_files) == 1
    failure = json.loads((audit / "failure.json").read_text())
    assert failure["code"] == "malformed_data"
    assert failure["raw"]["sha256"] == hashlib.sha256(raw_files[0].read_bytes()).hexdigest()
    assert transport.calls == 1


@pytest.mark.parametrize(
    "headers",
    [
        {"Content-Type": "text/html"},
        {"Content-Type": "application/xml", "Content-Encoding": "gzip"},
        {"Content-Type": "application/xml", "Location": "https://example.invalid"},
    ],
)
def test_http_response_contract(headers: dict[str, str], tmp_path: Path) -> None:
    transport = FakeTransport(_xml(), headers=headers)
    with pytest.raises(KofrEvidenceError):
        collect(transport, audit_root=tmp_path / hashlib.sha256(repr(headers).encode()).hexdigest())
    assert transport.calls == 1
