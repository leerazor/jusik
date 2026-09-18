"""Bounded, one-shot KOFR source collection and offline evidence verifier.

The collector intentionally has no strategy, portfolio, or broker dependency.  It
uses one injected HTTP transport call, then freezes the response as a
content-addressed XML artifact and a separately tracked JSON projection.
"""

from __future__ import annotations

import argparse
import errno
import hashlib
import json
import os
import re
import stat
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, DecimalException
from http.client import HTTPMessage
from pathlib import Path
from typing import Final, Protocol, cast

ENDPOINT: Final = "https://www.kofr.kr/websquare/engine/proworks/callServletService.jsp"
TASK: Final = "ksd.rfr.user.rate.process.RatePTask"
ACTION: Final = "getGridRateExcelList"
SUBMISSION_ID: Final = f"{TASK}.{ACTION}"
REFERER: Final = "https://www.kofr.kr/rate/rate.jsp?sMenuId=002001&sLangCd=01"
LANG: Final = "kor"
START_DATE: Final = "20250911"
END_DATE: Final = "20260911"
START_ISO: Final = "2025-09-11"
END_ISO: Final = "2026-09-11"
AUDIT_DIR: Final = Path(
    "/home/kwl/.local/share/jusik/portfolio-audit/20260917-kofr-risk-free-source-evidence"
)
MAX_RESPONSE_BYTES: Final = 5 * 1024 * 1024
MAX_ROWS: Final = 5_000
MAX_FIELDS: Final = 64
MAX_DEPTH: Final = 32
MAX_JSON_BYTES: Final = 10 * 1024 * 1024
MAX_DECIMAL_DIGITS: Final = 128
MAX_DECIMAL_ADJUSTED_EXPONENT: Final = 128
MAX_NORMALIZED_DECIMAL_LENGTH: Final = 256
MAX_DECIMAL_TEXT_LENGTH: Final = 256
XML_MIME: Final = frozenset({"application/xml", "text/xml"})
DATE_RE: Final = re.compile(r"^(\d{4})([-./])(\d{2})\2(\d{2})$")
PUBN_RE: Final = re.compile(
    r"^(\d{4})([-./])(\d{2})\2(\d{2})[ T](\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,6}))?)?$"
)
SHA_RE: Final = re.compile(r"^[0-9a-f]{64}$")

FIELDS: Final[tuple[str, ...]] = (
    "RFR_PUBN_DT",
    "RFR_PUBN_ISSN",
    "RFR_PUBN_MR",
    "RFR_INDEX",
    "D30_AVG_MR",
    "D90_AVG_MR",
    "D180_AVG_MR",
    "PUBN_MR_STD_DT",
    "PUBN_DTTM",
    "LINK_DTTM",
    "LAST_MODFR_NO",
    "LAST_MODF_DTTM",
)
NUMERIC_FIELDS: Final[frozenset[str]] = frozenset(
    {"RFR_PUBN_MR", "RFR_INDEX", "D30_AVG_MR", "D90_AVG_MR", "D180_AVG_MR"}
)


class KofrEvidenceError(ValueError):
    """Stable fail-closed error code."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class _DuplicateKey(ValueError):
    pass


def _object_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKey
        result[key] = value
    return result


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes


class HttpTransport(Protocol):
    def post(
        self, url: str, body: bytes, *, timeout: float, headers: Mapping[str, str]
    ) -> HttpResponse: ...


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: object,
        code: int,
        msg: str,
        headers: HTTPMessage,
        new: str,
    ) -> None:
        raise KofrEvidenceError("redirect_blocked")


class StdlibTransport:
    """Direct HTTPS transport with redirects and ambient proxies disabled."""

    def post(
        self, url: str, body: bytes, *, timeout: float, headers: Mapping[str, str]
    ) -> HttpResponse:
        if url != ENDPOINT or timeout > 30.0:
            raise KofrEvidenceError("transport_contract")
        request = urllib.request.Request(url, data=body, method="POST")
        for key, value in headers.items():
            request.add_header(key, value)
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), _NoRedirect()
        )
        try:
            with opener.open(request, timeout=timeout) as response:
                headers_out = {
                    str(k).lower(): str(v) for k, v in response.headers.items()
                }
                body_out = response.read(MAX_RESPONSE_BYTES + 1)
                return HttpResponse(response.status, headers_out, body_out)
        except KofrEvidenceError:
            raise
        except urllib.error.HTTPError as exc:
            return HttpResponse(
                exc.code,
                {str(k).lower(): str(v) for k, v in exc.headers.items()},
                exc.read(MAX_RESPONSE_BYTES + 1),
            )
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise KofrEvidenceError("network_failure") from exc


def request_xml() -> bytes:
    root = ET.Element("reqParam", {"action": ACTION, "task": TASK})
    for name, value in (
        ("LANG", LANG),
        ("SEARCH_START_DATE", START_DATE),
        ("SEARCH_END_DATE", END_DATE),
    ):
        ET.SubElement(root, name, {"value": value})
    return cast(bytes, ET.tostring(root, encoding="utf-8", xml_declaration=True))


def _check_tree_bounds(root: ET.Element) -> None:
    def visit(node: ET.Element, depth: int) -> None:
        if depth > MAX_DEPTH:
            raise KofrEvidenceError("xml_depth_limit")
        if len(node.attrib) > MAX_FIELDS:
            raise KofrEvidenceError("xml_field_limit")
        for child in node:
            visit(child, depth + 1)

    visit(root, 0)


def _parse_date(raw: str) -> str:
    match = DATE_RE.fullmatch(raw)
    if match is None:
        if re.fullmatch(r"\d{8}", raw):
            year, month, day = int(raw[:4]), int(raw[4:6]), int(raw[6:])
        else:
            raise KofrEvidenceError("invalid_date")
    else:
        year, month, day = int(match[1]), int(match[3]), int(match[4])
    try:
        parsed = date(year, month, day)
    except ValueError:
        raise KofrEvidenceError("invalid_date") from None
    normalized = parsed.isoformat()
    if not START_ISO <= normalized <= END_ISO:
        raise KofrEvidenceError("date_out_of_range")
    return normalized


def _decimal_text(raw: str) -> str:
    if not raw or len(raw) > MAX_DECIMAL_TEXT_LENGTH:
        raise KofrEvidenceError("malformed_numeric")
    candidate = raw.strip()
    if not candidate or candidate.lower() in {
        "nan",
        "+nan",
        "-nan",
        "infinity",
        "+infinity",
        "-infinity",
        "inf",
        "+inf",
        "-inf",
    }:
        raise KofrEvidenceError("nonfinite_value")
    if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", candidate):
        raise KofrEvidenceError("malformed_numeric")
    try:
        value = Decimal(candidate)
    except (DecimalException, ValueError):
        raise KofrEvidenceError("malformed_numeric") from None
    if not value.is_finite():
        raise KofrEvidenceError("nonfinite_value")
    sign, digits, exponent = value.as_tuple()
    if len(digits) > MAX_DECIMAL_DIGITS:
        raise KofrEvidenceError("numeric_precision_limit")
    if not isinstance(exponent, int):
        raise KofrEvidenceError("numeric_exponent_limit")
    if value != 0:
        try:
            adjusted = value.adjusted()
        except DecimalException:
            raise KofrEvidenceError("numeric_exponent_limit") from None
        if abs(adjusted) > MAX_DECIMAL_ADJUSTED_EXPONENT:
            raise KofrEvidenceError("numeric_exponent_limit")
    while digits and digits[-1] == 0:
        digits = digits[:-1]
        exponent += 1
    if not digits:
        return "0"
    coefficient = "".join(str(digit) for digit in digits)
    if exponent >= 0:
        normalized = coefficient + ("0" * exponent)
    else:
        split = len(coefficient) + exponent
        if split > 0:
            normalized = coefficient[:split] + "." + coefficient[split:]
        else:
            normalized = "0." + ("0" * -split) + coefficient
    if sign:
        normalized = "-" + normalized
    if len(normalized) > MAX_NORMALIZED_DECIMAL_LENGTH:
        raise KofrEvidenceError("numeric_output_limit")
    return normalized


def _pubn_datetime(raw: str) -> None:
    match = PUBN_RE.fullmatch(raw)
    if match is None:
        raise KofrEvidenceError("invalid_pubn_dttm")
    try:
        datetime(
            int(match[1]),
            int(match[3]),
            int(match[4]),
            int(match[5]),
            int(match[6]),
            int(match[7] or 0),
        )
    except ValueError:
        raise KofrEvidenceError("invalid_pubn_dttm") from None


def parse_response(body: bytes) -> tuple[list[dict[str, str]], list[dict[str, object]]]:
    """Parse and verify the expected WebSquare vector/data/result/value shape."""
    if len(body) > MAX_RESPONSE_BYTES:
        raise KofrEvidenceError("response_too_large")
    if b"<!DOCTYPE" in body.upper() or b"<!ENTITY" in body.upper() or b"<![" in body:
        raise KofrEvidenceError("xml_dtd_or_entity")
    try:
        root = ET.fromstring(body)
    except (ET.ParseError, ValueError, RecursionError):
        raise KofrEvidenceError("malformed_xml") from None
    _check_tree_bounds(root)
    if root.tag != "vector":
        raise KofrEvidenceError("unexpected_xml_root")
    vector = root
    allowed_vector_attributes = {
        "result",
        "beforeServletCall",
        "beforeEJBCall",
        "afterServletCall",
        "afterEJBCall",
    }
    if not set(vector.attrib).issubset(allowed_vector_attributes):
        raise KofrEvidenceError("malformed_vector")
    declared = vector.attrib.get("result")
    if declared is None or not declared.isdecimal() or len(declared) > 6:
        raise KofrEvidenceError("invalid_record_count")
    data_nodes = list(vector)
    if len(data_nodes) > MAX_ROWS:
        raise KofrEvidenceError("row_limit")
    if (vector.text and vector.text.strip()) or (vector.tail and vector.tail.strip()):
        raise KofrEvidenceError("malformed_vector")
    if any(node.tag != "data" for node in data_nodes):
        raise KofrEvidenceError("malformed_data")
    results: list[ET.Element] = []
    for data in data_nodes:
        if (
            set(data.attrib) - {"vectorkey", "type"}
            or data.attrib.get("type") not in {None, "Document"}
            or (data.text and data.text.strip())
            or (data.tail and data.tail.strip())
        ):
            raise KofrEvidenceError("malformed_data")
        children = list(data)
        if len(children) != 1 or children[0].tag != "result":
            raise KofrEvidenceError("malformed_data")
        results.append(children[0])
    if int(declared) != len(results):
        raise KofrEvidenceError("result_count_mismatch")
    rows: list[dict[str, str]] = []
    seen_dates: set[str] = set()
    for result in results:
        if (
            result.attrib
            or (result.text and result.text.strip())
            or (result.tail and result.tail.strip())
        ):
            raise KofrEvidenceError("malformed_result")
        fields: dict[str, str] = {}
        children = list(result)
        if not children or len(children) > MAX_FIELDS:
            raise KofrEvidenceError("malformed_result")
        for field in children:
            name = field.tag
            if (
                name in fields
                or name not in FIELDS
                or set(field.attrib) != {"value"}
                or list(field)
                or (field.text and field.text.strip())
                or (field.tail and field.tail.strip())
            ):
                raise KofrEvidenceError("malformed_result")
            value = field.attrib["value"]
            if not value or len(value) > 512:
                raise KofrEvidenceError("malformed_field")
            fields[name] = value
        if set(fields) != set(FIELDS):
            raise KofrEvidenceError("missing_required_field")
        observed = _parse_date(fields["RFR_PUBN_DT"])
        if observed in seen_dates:
            raise KofrEvidenceError("duplicate_date")
        seen_dates.add(observed)
        for name in NUMERIC_FIELDS:
            _decimal_text(fields[name])
        _pubn_datetime(fields["PUBN_DTTM"])
        rows.append(fields)
    rows.sort(key=lambda row: _parse_date(row["RFR_PUBN_DT"]))
    projection: list[dict[str, object]] = [
        {
            "observed_on": _parse_date(row["RFR_PUBN_DT"]),
            "rate_text": row["RFR_PUBN_MR"],
            "rate_decimal": _decimal_text(row["RFR_PUBN_MR"]),
            "published_at_raw": row["PUBN_DTTM"],
        }
        for row in rows
    ]
    return rows, projection


def _header(headers: Mapping[str, str], name: str) -> str | None:
    for key, value in headers.items():
        if key.lower() == name.lower():
            return value
    return None


def _check_response(response: HttpResponse) -> None:
    if response.status != 200:
        raise KofrEvidenceError("http_status")
    if len(response.body) > MAX_RESPONSE_BYTES:
        raise KofrEvidenceError("response_too_large")
    content_type = _header(response.headers, "content-type")
    if content_type is None:
        raise KofrEvidenceError("xml_mime")
    parts = [part.strip() for part in content_type.split(";")]
    if parts[0].lower() not in XML_MIME:
        raise KofrEvidenceError("xml_mime")
    for part in parts[1:]:
        if (
            part.lower().startswith("charset=")
            and part.split("=", 1)[1].strip().lower() != "utf-8"
        ):
            raise KofrEvidenceError("xml_encoding")
    encoding = _header(response.headers, "content-encoding")
    if encoding and encoding.lower() not in {"identity", ""}:
        raise KofrEvidenceError("compression_blocked")
    if _header(response.headers, "location") or response.status in {
        301,
        302,
        303,
        307,
        308,
    }:
        raise KofrEvidenceError("redirect_blocked")
    if response.status in {401, 407}:
        raise KofrEvidenceError("auth_blocked")
    try:
        response.body.decode("utf-8")
    except UnicodeDecodeError:
        raise KofrEvidenceError("xml_encoding") from None


def _assert_regular(path: Path) -> None:
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise KofrEvidenceError("unsafe_path")


def _assert_directory(path: Path) -> None:
    if path.is_symlink() or (path.exists() and not path.is_dir()):
        raise KofrEvidenceError("unsafe_path")


def _open_secure_directory(path: Path, *, create: bool = True) -> int:
    """Open/create every directory component without following symlinks."""
    absolute = Path(os.path.abspath(path))
    fd = os.open(os.sep, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        for component in absolute.parts[1:]:
            try:
                next_fd = os.open(
                    component,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
                    dir_fd=fd,
                )
            except FileNotFoundError:
                if not create:
                    raise
                try:
                    os.mkdir(component, 0o700, dir_fd=fd)
                except FileExistsError:
                    pass
                next_fd = os.open(
                    component,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
                    dir_fd=fd,
                )
            os.close(fd)
            fd = next_fd
        return fd
    except (OSError, ValueError) as exc:
        os.close(fd)
        raise KofrEvidenceError("unsafe_path") from exc


def _secure_read(path: Path, *, limit: int) -> bytes:
    absolute = Path(os.path.abspath(path))
    parent_fd = _open_secure_directory(absolute.parent, create=False)
    try:
        try:
            fd = os.open(
                absolute.name,
                os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
                dir_fd=parent_fd,
            )
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise KofrEvidenceError("unsafe_path") from exc
            raise KofrEvidenceError("source_unavailable") from exc
        try:
            file_stat = os.fstat(fd)
            if not stat.S_ISREG(file_stat.st_mode):
                raise KofrEvidenceError("unsafe_path")
            chunks: list[bytes] = []
            remaining = limit + 1
            while remaining:
                chunk = os.read(fd, remaining)
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            return b"".join(chunks)
        finally:
            os.close(fd)
    finally:
        os.close(parent_fd)


def _exclusive_write(path: Path, data: bytes) -> None:
    absolute = Path(os.path.abspath(path))
    _assert_regular(absolute)
    parent_fd = _open_secure_directory(absolute.parent)
    temp_name = f".{absolute.name}.{os.getpid()}.tmp"
    try:
        try:
            fd = os.open(
                temp_name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                0o600,
                dir_fd=parent_fd,
            )
        except FileExistsError as exc:
            raise KofrEvidenceError("artifact_exists") from exc
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(
                temp_name,
                absolute.name,
                src_dir_fd=parent_fd,
                dst_dir_fd=parent_fd,
                follow_symlinks=False,
            )
        except FileExistsError as exc:
            raise KofrEvidenceError("artifact_exists") from exc
    finally:
        try:
            os.unlink(temp_name, dir_fd=parent_fd)
        except FileNotFoundError:
            pass
        os.close(parent_fd)


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def verify_evidence(
    evidence_path: Path, audit_root: Path = AUDIT_DIR
) -> dict[str, object]:
    """Verify tracked JSON, request, raw XML, and projection offline."""
    _assert_regular(evidence_path)
    try:
        raw_evidence = _secure_read(evidence_path, limit=MAX_JSON_BYTES)
        if len(raw_evidence) > MAX_JSON_BYTES:
            raise KofrEvidenceError("evidence_too_large")
        evidence = json.loads(
            raw_evidence.decode("utf-8"), object_pairs_hook=_object_pairs
        )
    except KofrEvidenceError:
        raise
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        RecursionError,
        _DuplicateKey,
    ):
        raise KofrEvidenceError("malformed_evidence") from None
    if (
        not isinstance(evidence, dict)
        or evidence.get("schema") != "kofr-source-evidence/v1"
    ):
        raise KofrEvidenceError("malformed_evidence")
    raw_info = evidence.get("raw")
    if (
        not isinstance(raw_info, dict)
        or not isinstance(raw_info.get("path"), str)
        or not isinstance(raw_info.get("sha256"), str)
    ):
        raise KofrEvidenceError("malformed_evidence")
    sha_value = raw_info.get("sha256")
    path_value = raw_info.get("path")
    if not isinstance(sha_value, str) or not isinstance(path_value, str):
        raise KofrEvidenceError("malformed_evidence")
    sha = sha_value
    if not SHA_RE.fullmatch(sha):
        raise KofrEvidenceError("malformed_evidence")
    raw_rel = Path(path_value)
    if raw_rel.parent != Path("raw") or raw_rel.name != f"{sha}.xml":
        raise KofrEvidenceError("unsafe_path")
    raw_path = audit_root / raw_rel
    _assert_directory(audit_root / "raw")
    try:
        body = _secure_read(raw_path, limit=MAX_RESPONSE_BYTES)
    except KofrEvidenceError:
        raise
    except OSError:
        raise KofrEvidenceError("raw_unavailable") from None
    byte_count = raw_info.get("bytes")
    if (
        not isinstance(byte_count, int)
        or isinstance(byte_count, bool)
        or len(body) != byte_count
        or hashlib.sha256(body).hexdigest() != sha
    ):
        raise KofrEvidenceError("raw_sha_mismatch")
    request_info = evidence.get("request")
    expected_request = {
        "endpoint": ENDPOINT,
        "task": TASK,
        "action": ACTION,
        "lang": LANG,
        "start_date": START_ISO,
        "end_date": END_ISO,
        "request_sha256": hashlib.sha256(request_xml()).hexdigest(),
    }
    if request_info != expected_request:
        raise KofrEvidenceError("request_mismatch")
    request_path = audit_root / "request.xml"
    try:
        request_bytes = _secure_read(request_path, limit=MAX_RESPONSE_BYTES)
    except KofrEvidenceError as exc:
        if exc.code == "unsafe_path":
            raise
        raise KofrEvidenceError("request_unavailable") from None
    except OSError:
        raise KofrEvidenceError("request_unavailable") from None
    if (
        hashlib.sha256(request_bytes).hexdigest() != expected_request["request_sha256"]
        or request_bytes != request_xml()
    ):
        raise KofrEvidenceError("request_mismatch")
    rows, projection = parse_response(body)
    if evidence.get("rows") != rows or evidence.get("projection") != projection:
        raise KofrEvidenceError("projection_mismatch")
    observed = evidence.get("observed")
    if not isinstance(observed, dict) or observed.get("count") != len(rows):
        raise KofrEvidenceError("observed_mismatch")
    expected_range = (
        [projection[0]["observed_on"], projection[-1]["observed_on"]]
        if projection
        else [None, None]
    )
    if observed.get("range") != expected_range:
        raise KofrEvidenceError("observed_mismatch")
    return {"verified": True, "rows": len(rows), "raw_sha256": sha}


def collect(
    transport: HttpTransport,
    *,
    audit_root: Path = AUDIT_DIR,
    evidence_output: Path | None = None,
    timeout: float = 30.0,
) -> dict[str, object]:
    if timeout != 30.0:
        raise KofrEvidenceError("timeout_override")
    request = request_xml()
    audit_root = Path(os.path.abspath(audit_root))
    _assert_directory(audit_root)
    if evidence_output is not None:
        _assert_regular(evidence_output)
    audit_fd = _open_secure_directory(audit_root)
    os.close(audit_fd)
    attempt_path = audit_root / "attempt.json"
    _exclusive_write(
        attempt_path,
        _json_bytes(
            {
                "schema": "kofr-source-attempt/v1",
                "created_at_utc": _utc_now(),
                "endpoint": ENDPOINT,
                "request_sha256": hashlib.sha256(request).hexdigest(),
            }
        ),
    )
    _exclusive_write(audit_root / "request.xml", request)
    response = transport.post(
        ENDPOINT,
        request,
        timeout=30.0,
        headers={
            "Content-Type": "application/xml; charset=utf-8",
            "Accept": "application/xml",
            "Accept-Encoding": "identity",
            # Match the WebSquare request context. Without these fields the
            # endpoint can return only an XML declaration with HTTP 200.
            "submissionid": SUBMISSION_ID,
            "Referer": REFERER,
        },
    )
    _check_response(response)
    raw_sha = hashlib.sha256(response.body).hexdigest()
    raw_rel = Path("raw") / f"{raw_sha}.xml"
    _exclusive_write(audit_root / raw_rel, response.body)
    try:
        rows, projection = parse_response(response.body)
    except KofrEvidenceError as exc:
        _exclusive_write(
            audit_root / "failure.json",
            _json_bytes(
                {
                    "schema": "kofr-source-failure/v1",
                    "code": exc.code,
                    "raw": {
                        "path": raw_rel.as_posix(),
                        "sha256": raw_sha,
                        "bytes": len(response.body),
                    },
                    "recorded_at_utc": _utc_now(),
                }
            ),
        )
        raise
    collection_time = _utc_now()
    evidence: dict[str, object] = {
        "schema": "kofr-source-evidence/v1",
        "request": {
            "endpoint": ENDPOINT,
            "task": TASK,
            "action": ACTION,
            "lang": LANG,
            "start_date": START_ISO,
            "end_date": END_ISO,
            "request_sha256": hashlib.sha256(request).hexdigest(),
        },
        "rows": rows,
        "projection": projection,
        "observed": {
            "count": len(rows),
            "range": [projection[0]["observed_on"], projection[-1]["observed_on"]]
            if projection
            else [None, None],
        },
        "raw": {
            "path": raw_rel.as_posix(),
            "sha256": raw_sha,
            "bytes": len(response.body),
        },
        "collected_at_utc": collection_time,
        "limitations": [
            "PUBN_DTTM is preserved as raw source text; "
            "timezone and instant are unverified.",
            "Expected KOFR business-date completeness is unverified; "
            "no rows are synthesized.",
            "This source evidence is not applied to NAV, returns, Sharpe, "
            "readiness, or strategy.",
        ],
    }
    evidence_bytes = _json_bytes(evidence)
    _exclusive_write(audit_root / "evidence.json", evidence_bytes)
    if evidence_output is not None:
        _exclusive_write(evidence_output, evidence_bytes)
    verification = {
        "schema": "kofr-source-verification/v1",
        "verified_at_utc": _utc_now(),
        "evidence_sha256": hashlib.sha256(evidence_bytes).hexdigest(),
        "result": verify_evidence(audit_root / "evidence.json", audit_root),
    }
    _exclusive_write(audit_root / "verification.json", _json_bytes(verification))
    _exclusive_write(
        audit_root / "manifest.json",
        _json_bytes(
            {
                "schema": "kofr-source-manifest/v1",
                "request": "request.xml",
                "raw": raw_rel.as_posix(),
                "evidence": "evidence.json",
                "verification": "verification.json",
            }
        ),
    )
    return evidence


def replay_raw(
    audit_root: Path,
    raw_path: Path,
    *,
    evidence_output: Path | None = None,
) -> dict[str, object]:
    """Build evidence from an already captured raw response without network I/O."""
    audit_root = Path(os.path.abspath(audit_root))
    request_path = audit_root / "request.xml"
    attempt_path = audit_root / "attempt.json"
    _assert_directory(audit_root)
    request = _secure_read(request_path, limit=MAX_JSON_BYTES)
    raw_path = Path(raw_path)
    if raw_path.is_absolute():
        raw_absolute = Path(os.path.abspath(raw_path))
    else:
        raw_absolute = Path(os.path.abspath(audit_root / raw_path))
    try:
        raw_relative = raw_absolute.relative_to(audit_root)
    except ValueError as exc:
        raise KofrEvidenceError("unsafe_path") from exc
    if raw_relative.parent != Path("raw") or raw_relative.suffix != ".xml":
        raise KofrEvidenceError("raw_path")
    body = _secure_read(raw_absolute, limit=MAX_RESPONSE_BYTES)
    raw_sha = hashlib.sha256(body).hexdigest()
    if raw_relative.name != f"{raw_sha}.xml":
        raise KofrEvidenceError("raw_sha_mismatch")
    try:
        attempt = json.loads(
            _secure_read(attempt_path, limit=MAX_JSON_BYTES).decode("utf-8"),
            object_pairs_hook=_object_pairs,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, _DuplicateKey):
        raise KofrEvidenceError("malformed_attempt") from None
    if (
        not isinstance(attempt, dict)
        or attempt.get("request_sha256") != hashlib.sha256(request).hexdigest()
    ):
        raise KofrEvidenceError("request_sha_mismatch")
    rows, projection = parse_response(body)
    evidence: dict[str, object] = {
        "schema": "kofr-source-evidence/v1",
        "request": {
            "endpoint": ENDPOINT,
            "task": TASK,
            "action": ACTION,
            "lang": LANG,
            "start_date": START_ISO,
            "end_date": END_ISO,
            "request_sha256": hashlib.sha256(request).hexdigest(),
        },
        "rows": rows,
        "projection": projection,
        "observed": {
            "count": len(rows),
            "range": [projection[0]["observed_on"], projection[-1]["observed_on"]]
            if projection
            else [None, None],
        },
        "raw": {"path": raw_relative.as_posix(), "sha256": raw_sha, "bytes": len(body)},
        "collected_at_utc": attempt.get("created_at_utc", _utc_now()),
        "limitations": [
            (
                "PUBN_DTTM is preserved as raw source text; "
                "timezone and instant are unverified."
            ),
            (
                "Expected KOFR business-date completeness is unverified; "
                "no rows are synthesized."
            ),
            (
                "This source evidence is not applied to NAV, returns, Sharpe, "
                "readiness, or strategy."
            ),
        ],
    }
    evidence_bytes = _json_bytes(evidence)
    _exclusive_write(audit_root / "evidence.json", evidence_bytes)
    if evidence_output is not None:
        _exclusive_write(evidence_output, evidence_bytes)
    verification = {
        "schema": "kofr-source-verification/v1",
        "verified_at_utc": _utc_now(),
        "evidence_sha256": hashlib.sha256(evidence_bytes).hexdigest(),
        "result": verify_evidence(audit_root / "evidence.json", audit_root),
    }
    _exclusive_write(audit_root / "verification.json", _json_bytes(verification))
    _exclusive_write(
        audit_root / "manifest.json",
        _json_bytes(
            {
                "schema": "kofr-source-manifest/v1",
                "request": "request.xml",
                "raw": raw_relative.as_posix(),
                "evidence": "evidence.json",
                "verification": "verification.json",
            }
        ),
    )
    return evidence


def _cli() -> int:
    parser = argparse.ArgumentParser(
        description="Collect or verify the fixed KOFR source evidence."
    )
    parser.add_argument("--audit-root", type=Path, default=AUDIT_DIR)
    parser.add_argument("--evidence-output", type=Path)
    parser.add_argument(
        "--replay-raw",
        type=Path,
        help="build evidence from a captured raw XML response",
    )
    parser.add_argument(
        "--verify", type=Path, help="verify an existing tracked evidence JSON offline"
    )
    args = parser.parse_args()
    try:
        if args.verify is not None:
            print(
                json.dumps(
                    verify_evidence(args.verify, args.audit_root), sort_keys=True
                )
            )
        elif args.replay_raw is not None:
            result = replay_raw(
                args.audit_root, args.replay_raw, evidence_output=args.evidence_output
            )
            rows = result.get("rows")
            row_count = len(rows) if isinstance(rows, list) else 0
            print(json.dumps({"rows": row_count, "replayed": True}, sort_keys=True))
        else:
            collect(
                StdlibTransport(),
                audit_root=args.audit_root,
                evidence_output=args.evidence_output,
            )
            result = verify_evidence(args.audit_root / "evidence.json", args.audit_root)
            print(json.dumps(result, sort_keys=True))
    except KofrEvidenceError as exc:
        print(exc.code, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
