from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Mapping
from pathlib import Path

import pytest

from jusik.kofr_source_evidence import (
    ACTION,
    END_DATE,
    ENDPOINT,
    FIELDS,
    LANG,
    REFERER,
    START_DATE,
    SUBMISSION_ID,
    TASK,
    HttpResponse,
    KofrEvidenceError,
    collect,
    parse_response,
    request_xml,
    verify_evidence,
)


def _xml(
    *,
    count: int = 1,
    date_text: str = "2025.09.11",
    rate: str = "3.5000",
    extra: str = "",
) -> bytes:
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
    return (
        f'<vector result="{count}"><data><result>{fields}{extra}</result>'
        "</data></vector>"
    ).encode()


class FakeTransport:
    def __init__(
        self, body: bytes, *, status: int = 200, headers: dict[str, str] | None = None
    ) -> None:
        self.body = body
        self.status = status
        self.headers = headers or {"Content-Type": "application/xml; charset=utf-8"}
        self.calls = 0
        self.seen: tuple[str, bytes, float, dict[str, str]] | None = None

    def post(
        self, url: str, body: bytes, *, timeout: float, headers: Mapping[str, str]
    ) -> HttpResponse:
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
    compact_rows, _ = parse_response(_xml(date_text="20250911"))
    assert compact_rows[0]["RFR_PUBN_DT"] == "20250911"


def test_collection_uses_websquare_request_context(tmp_path: Path) -> None:
    transport = FakeTransport(_xml())
    collect(transport, audit_root=tmp_path / "audit")
    assert transport.seen is not None
    headers = {key.lower(): value for key, value in transport.seen[3].items()}
    assert headers["submissionid"] == SUBMISSION_ID
    assert headers["referer"] == REFERER


@pytest.mark.parametrize(
    ("body", "code"),
    [
        (_xml(count=2), "result_count_mismatch"),
        (_xml(extra='<RFR_PUBN_MR value="3.1"/>'), "malformed_result"),
        (_xml(date_text="2024.12.31"), "date_out_of_range"),
        (_xml(rate="NaN"), "nonfinite_value"),
        (_xml(rate="Infinity"), "nonfinite_value"),
        (_xml(extra='<BROKEN value="x"/>'), "malformed_result"),
        (b"<!DOCTYPE response><response/>", "xml_dtd_or_entity"),
    ],
)
def test_parser_rejects_threats(body: bytes, code: str) -> None:
    with pytest.raises(KofrEvidenceError, match=code):
        parse_response(body)


def test_legacy_wrapper_and_record_count_shape_are_rejected() -> None:
    legacy = (
        _xml()
        .replace(b'<vector result="1">', b'<response><vector RECORD_COUNT="1">')
        .replace(b"</vector>", b"</vector></response>")
    )
    with pytest.raises(KofrEvidenceError, match="unexpected_xml_root"):
        parse_response(legacy)


def test_parser_accepts_official_websquare_metadata() -> None:
    body = (
        _xml()
        .replace(
            b'<vector result="1">',
            b'<vector beforeServletCall="1" beforeEJBCall="2" '
            b'afterServletCall="3" afterEJBCall="3" result="1">',
        )
        .replace(b"<data>", b'<data vectorkey="0" type="Document">')
    )
    rows, _ = parse_response(body)
    assert len(rows) == 1


def test_parser_rejects_unknown_websquare_metadata() -> None:
    body = _xml().replace(b'<vector result="1">', b'<vector unexpected="x" result="1">')
    with pytest.raises(KofrEvidenceError, match="malformed_vector"):
        parse_response(body)


def test_exact_xml_attributes_and_leaf_shape_are_required() -> None:
    with pytest.raises(KofrEvidenceError, match="malformed_vector"):
        parse_response(
            _xml().replace(b'<vector result="1">', b'<vector result="1" extra="x">')
        )
    with pytest.raises(KofrEvidenceError, match="malformed_data"):
        parse_response(_xml().replace(b"<data>", b'<data extra="x">'))
    with pytest.raises(KofrEvidenceError, match="malformed_result"):
        parse_response(_xml().replace(b"<result>", b'<result extra="x">'))
    with pytest.raises(KofrEvidenceError, match="malformed_result"):
        parse_response(
            _xml().replace(
                b'<RFR_INDEX value="105.1234"/>',
                b'<RFR_INDEX value="105.1234"><child/></RFR_INDEX>',
            )
        )


def test_exact_no_namespace_tags_and_whitespace_only_text_tail() -> None:
    namespaced = _xml().replace(
        b"<vector result=", b'<vector xmlns="urn:wrong" result='
    )
    with pytest.raises(KofrEvidenceError, match="unexpected_xml_root"):
        parse_response(namespaced)
    namespaced_field = _xml().replace(
        b'<RFR_INDEX value="105.1234"/>',
        b'<wrong:RFR_INDEX xmlns:wrong="urn:wrong" value="105.1234"/>',
    )
    with pytest.raises(KofrEvidenceError, match="malformed_result"):
        parse_response(namespaced_field)
    field_tail = _xml().replace(
        b'<RFR_INDEX value="105.1234"/>', b'<RFR_INDEX value="105.1234"/>unexpected'
    )
    with pytest.raises(KofrEvidenceError, match="malformed_result"):
        parse_response(field_tail)
    data_text = _xml().replace(b"<data>", b"<data>unexpected")
    with pytest.raises(KofrEvidenceError, match="malformed_data"):
        parse_response(data_text)


def test_decimal_bounds_do_not_use_ambient_precision() -> None:
    rows, projection = parse_response(
        _xml(rate="123456789012345678901234567890.123456789")
    )
    assert rows[0]["RFR_PUBN_MR"].startswith("1234567890")
    assert projection[0]["rate_decimal"] == "123456789012345678901234567890.123456789"
    for value, code in (
        ("1e129", "numeric_exponent_limit"),
        ("1e-129", "numeric_exponent_limit"),
        ("9" * 129, "numeric_precision_limit"),
    ):
        with pytest.raises(KofrEvidenceError, match=code):
            parse_response(_xml(rate=value))


def test_duplicate_date_and_missing_field_are_rejected() -> None:
    one = _xml().decode()
    fields = one.split("<result>", 1)[1].split("</result>", 1)[0]
    body = (
        f'<vector result="2"><data><result>{fields}</result></data>'
        f"<data><result>{fields}</result></data></vector>"
    ).encode()
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
    assert evidence == json.loads(output.read_text())
    assert set(evidence) == {
        "schema",
        "request",
        "rows",
        "projection",
        "observed",
        "raw",
        "collected_at_utc",
        "limitations",
    }
    assert verify_evidence(output, tmp_path / "audit")["verified"] is True
    with pytest.raises(KofrEvidenceError, match="artifact_exists"):
        collect(FakeTransport(_xml()), audit_root=tmp_path / "audit")
    assert transport.calls == 1


def test_semantic_failure_freezes_bounded_raw_and_failure_metadata(
    tmp_path: Path,
) -> None:
    transport = FakeTransport(b'<vector result="1"><data/></vector>')
    audit = tmp_path / "audit"
    with pytest.raises(KofrEvidenceError, match="malformed_data"):
        collect(transport, audit_root=audit)
    raw_files = list((audit / "raw").glob("*.xml"))
    assert len(raw_files) == 1
    failure = json.loads((audit / "failure.json").read_text())
    assert failure["code"] == "malformed_data"
    assert (
        failure["raw"]["sha256"]
        == hashlib.sha256(raw_files[0].read_bytes()).hexdigest()
    )
    assert transport.calls == 1


def test_verifier_rejects_raw_directory_symlink_and_request_mismatch(
    tmp_path: Path,
) -> None:
    audit = tmp_path / "audit"
    output = tmp_path / "evidence.json"
    collect(FakeTransport(_xml()), audit_root=audit, evidence_output=output)
    evidence = json.loads(output.read_text())
    original_raw = (audit / evidence["raw"]["path"]).read_bytes()
    outside = tmp_path / "outside"
    outside.mkdir()
    shutil.rmtree(audit / "raw")
    (audit / "raw").symlink_to(outside, target_is_directory=True)
    with pytest.raises(KofrEvidenceError, match="unsafe_path"):
        verify_evidence(output, audit)

    (audit / "raw").unlink()
    raw_path = audit / "raw"
    raw_path.mkdir()
    raw_file = raw_path / Path(evidence["raw"]["path"]).name
    raw_file.write_bytes(original_raw)
    (audit / "request.xml").write_bytes(b"<tampered/>")
    with pytest.raises(KofrEvidenceError, match="request_mismatch"):
        verify_evidence(output, audit)


def test_verifier_rejects_raw_tampering_and_path_escape(tmp_path: Path) -> None:
    audit = tmp_path / "audit"
    output = tmp_path / "evidence.json"
    collect(FakeTransport(_xml()), audit_root=audit, evidence_output=output)
    evidence = json.loads(output.read_text())
    raw_path = audit / evidence["raw"]["path"]
    raw_path.write_bytes(raw_path.read_bytes() + b" ")
    with pytest.raises(KofrEvidenceError, match="raw_sha_mismatch"):
        verify_evidence(output, audit)

    evidence["raw"]["path"] = "raw/../outside.xml"
    output.write_text(json.dumps(evidence))
    with pytest.raises(KofrEvidenceError, match="unsafe_path"):
        verify_evidence(output, audit)


def test_audit_parent_symlink_is_rejected_before_transport(tmp_path: Path) -> None:
    real_parent = tmp_path / "real-parent"
    real_parent.mkdir()
    symlink_parent = tmp_path / "symlink-parent"
    symlink_parent.symlink_to(real_parent, target_is_directory=True)
    transport = FakeTransport(_xml())
    with pytest.raises(KofrEvidenceError, match="unsafe_path"):
        collect(transport, audit_root=symlink_parent / "audit")
    assert transport.calls == 0


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
        collect(
            transport,
            audit_root=tmp_path / hashlib.sha256(repr(headers).encode()).hexdigest(),
        )
    assert transport.calls == 1
