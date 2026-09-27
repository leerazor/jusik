"""Synthetic offline receipts; no external artifact, collection or readiness grant."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import pytest

from jusik.development_runner_readiness import (
    ReadinessBinding,
    ReadinessExpectations,
    bind_external_readiness,
)


def _sha(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _encode(value: object) -> bytes:
    return json.dumps(value, sort_keys=True).encode()


@dataclass
class Audit:
    root: Path
    paths: dict[str, str]
    reports: dict[str, dict[str, object]]
    raw: dict[str, bytes]
    expected: ReadinessExpectations

    def publish(self, *, indent: int | None = None) -> None:
        for name, report in self.reports.items():
            if name != "receipt":
                self.raw[name] = json.dumps(report, indent=indent).encode()
        self.reports["receipt"]["artifact_sha256"] = {
            name: _sha(body) for name, body in self.raw.items()
        }
        for name, body in self.raw.items():
            path = self.root / self.paths[name]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
        receipt_body = json.dumps(self.reports["receipt"], indent=indent).encode()
        (self.root / self.paths["receipt"]).write_bytes(receipt_body)
        self.expected = self.expected.model_copy(
            update={"receipt_sha256": _sha(receipt_body)}
        )

    def bind(self) -> ReadinessBinding:
        return bind_external_readiness(
            artifact_root=self.root,
            artifact_paths=self.paths,
            expected=self.expected,
        )


@pytest.fixture
def audit(tmp_path: Path) -> Audit:
    context = {
        "source_task_id": "synthetic-expanded-universe",
        "source_attempt_id": "offline-attempt",
        "scope": "collection-gates",
    }
    envelope = {"schema_version": 1, **context, "metadata": {"note": "synthetic"}}
    criteria = {"symbols": ["IVV", "SGOV"], "retry": 0, "window": "frozen"}
    raw = {"content:prices": b"<html>not price history</html>", "content:fx": b""}
    reports = {
        "receipt": dict(envelope),
        "request": {**envelope, "criteria": criteria},
        "result": {
            **envelope,
            "contents": [
                {"content_id": key.removeprefix("content:"), "sha256": _sha(body)}
                for key, body in raw.items()
            ],
        },
        "validation": {
            **envelope,
            "gates": [
                {"name": name, "status": "BLOCKED"}
                for name in (
                    "Prices",
                    "Dividends",
                    "Splits",
                    "FX",
                    "Tax",
                    "Calendar",
                    "Venue",
                    "Coverage",
                )
            ],
        },
        "provenance": {
            **envelope,
            "producer_id": "synthetic-collector-v1",
            "executed_collector_source_hash": "a" * 64,
            "validator_id": "synthetic-validator-v1",
            "validator_source_hash": "b" * 64,
        },
    }
    expected = ReadinessExpectations.model_validate(
        {
            **context,
            "receipt_sha256": "0" * 64,
            "request_criteria": criteria,
            "producer_id": "synthetic-collector-v1",
            "producer_code_sha256": "a" * 64,
            "validator_id": "synthetic-validator-v1",
            "validator_code_sha256": "b" * 64,
        }
    )
    fixture = Audit(
        tmp_path,
        {name: name.replace(":", "-") + ".json" for name in [*reports, *raw]},
        reports,
        raw,
        expected,
    )
    fixture.publish()
    return fixture


def test_bound_is_deterministic_and_all_gates_stay_blocked(audit: Audit) -> None:
    first = audit.bind()
    assert first == audit.bind()
    assert first.status == "bound"
    assert first.reason == "verified"
    assert len(first.gates) == 8
    assert {gate.status for gate in first.gates} == {"BLOCKED"}
    assert set(first.model_dump()) == {
        "status",
        "reason",
        "semantic_sha256",
        "artifact_sha256",
        "gates",
    }


def test_current_audit_missing_executed_producer_hash_is_unqualified(
    audit: Audit,
) -> None:
    audit.reports["provenance"]["executed_collector_source_hash"] = None
    audit.publish()
    bound = audit.bind()
    assert bound.status == "unqualified"
    assert bound.reason == "missing_producer_hash"
    assert len(bound.gates) == 8
    assert {gate.status for gate in bound.gates} == {"BLOCKED"}
    assert bound.semantic_sha256
    (audit.root / audit.paths["content:prices"]).write_bytes(b"altered")
    assert audit.bind().status == "invalid"


@pytest.mark.parametrize(
    "report", ["receipt", "request", "result", "validation", "provenance"]
)
@pytest.mark.parametrize("field", ["source_task_id", "source_attempt_id", "scope"])
def test_context_mismatch_fails_closed(audit: Audit, report: str, field: str) -> None:
    audit.reports[report][field] = "different"
    audit.publish()
    assert audit.bind().status == "invalid"


@pytest.mark.parametrize(
    "name",
    [
        "receipt",
        "request",
        "result",
        "validation",
        "provenance",
        "content:prices",
        "content:fx",
    ],
)
def test_every_exact_artifact_hash_is_verified(audit: Audit, name: str) -> None:
    (audit.root / audit.paths[name]).write_bytes(b"changed")
    assert audit.bind().status == "invalid"


@pytest.mark.parametrize(
    "field",
    [
        "producer_id",
        "validator_id",
        "producer_code_sha256",
        "validator_code_sha256",
        "receipt_sha256",
        "request_criteria",
    ],
)
def test_independent_pin_mismatch_fails_closed(audit: Audit, field: str) -> None:
    value: object = "c" * 64 if field.endswith("sha256") else "different"
    if field == "request_criteria":
        value = {"different": True}
    audit.expected = audit.expected.model_copy(update={field: value})
    assert audit.bind().status == "invalid"


@pytest.mark.parametrize(
    "body",
    [
        b'{"duplicate": 1, "duplicate": 2}',
        b'{"nested": {"duplicate": 1, "duplicate": 2}}',
        b"{",
        b"[]",
        b"null",
        b"\xff",
        b'{"bad": NaN}',
        b'{"bad": Infinity}',
        b'{"bad": 1e999}',
    ],
)
@pytest.mark.parametrize(
    "name", ["receipt", "request", "result", "validation", "provenance"]
)
def test_malformed_and_duplicate_json_rejected(
    audit: Audit,
    body: bytes,
    name: str,
) -> None:
    if name != "receipt":
        audit.reports.pop(name)
        audit.raw[name] = body
        audit.publish()
    else:
        (audit.root / audit.paths[name]).write_bytes(body)
        audit.expected = audit.expected.model_copy(
            update={"receipt_sha256": _sha(body)}
        )
    assert audit.bind().status == "invalid"


@pytest.mark.parametrize(
    "name", ["receipt", "request", "result", "validation", "provenance"]
)
@pytest.mark.parametrize("version", [2, "1", True, None])
def test_schema_version_is_strict(audit: Audit, name: str, version: object) -> None:
    audit.reports[name]["schema_version"] = version
    audit.publish()
    assert audit.bind().status == "invalid"


@pytest.mark.parametrize(
    "mutation",
    [
        "unknown_field",
        "unknown_status",
        "duplicate_gate",
        "empty_gate",
        "duplicate_content",
        "wrong_content",
        "empty_gates",
        "extra_artifact",
        "missing_report",
        "criteria",
        "normalized_duplicate_criteria",
    ],
)
def test_structural_corruption_rejected(audit: Audit, mutation: str) -> None:
    gates = cast(list[dict[str, str]], audit.reports["validation"]["gates"])
    contents = cast(list[dict[str, str]], audit.reports["result"]["contents"])
    if mutation == "unknown_field":
        audit.reports["result"]["unknown"] = "no"
    elif mutation == "unknown_status":
        gates[0]["status"] = "APPROVED"
    elif mutation == "duplicate_gate":
        gates.append({"name": " prices ", "status": "PASS"})
    elif mutation == "empty_gate":
        gates[0]["name"] = " "
    elif mutation == "duplicate_content":
        contents.append({**contents[0], "content_id": " prices "})
    elif mutation == "wrong_content":
        contents[0]["sha256"] = "c" * 64
    elif mutation == "empty_gates":
        audit.reports["validation"]["gates"] = []
    elif mutation == "extra_artifact":
        audit.raw["unknown"] = b"extra"
        audit.paths["unknown"] = "unknown.bin"
    elif mutation == "missing_report":
        audit.reports.pop("request")
        audit.raw.pop("request")
        audit.paths.pop("request")
    elif mutation == "criteria":
        audit.reports["request"]["criteria"] = {"retry": True}
    else:
        audit.reports["request"]["criteria"] = {"retry": 0, " retry ": 0}
    audit.publish()
    assert audit.bind().status == "invalid"


@pytest.mark.parametrize(
    "path",
    ["../outside", "/absolute", "a/../file", "a//file", "./file", "", "bad\x00name"],
)
def test_unsafe_paths_rejected(audit: Audit, path: str) -> None:
    audit.paths["request"] = path
    assert audit.bind().status == "invalid"


@pytest.mark.parametrize(
    "kind",
    [
        "root",
        "ancestor",
        "component",
        "final",
        "directory",
        "fifo",
        "alias",
        "absent",
        "relative_root",
    ],
)
def test_unsafe_files_rejected(audit: Audit, kind: str, tmp_path: Path) -> None:
    original = audit.root / audit.paths["request"]
    if kind in {"root", "ancestor"}:
        linked = tmp_path / "link"
        linked.symlink_to(tmp_path, target_is_directory=True)
        audit.root = linked if kind == "root" else linked / "child"
        if kind == "ancestor":
            (tmp_path / "child").mkdir()
    elif kind == "component":
        (tmp_path / "link").symlink_to(tmp_path, target_is_directory=True)
        audit.paths["request"] = "link/" + audit.paths["request"]
    elif kind == "final":
        (tmp_path / "link").symlink_to(original)
        audit.paths["request"] = "link"
    elif kind in {"directory", "fifo"}:
        original.unlink()
        if kind == "directory":
            original.mkdir()
        else:
            os.mkfifo(original)
    elif kind == "alias":
        audit.paths["request"] = audit.paths["result"]
    elif kind == "absent":
        original.unlink()
    else:
        audit.root = Path("relative")
    assert audit.bind().status == "invalid"


@pytest.mark.parametrize(
    "change",
    [
        "producer_id",
        "validator_id",
        "producer_version",
        "validator_version",
        "criteria",
        "raw",
        "gate",
        "task",
        "attempt",
        "scope",
    ],
)
def test_semantic_changes_change_digest(audit: Audit, change: str) -> None:
    original = audit.bind().semantic_sha256
    provenance = audit.reports["provenance"]
    if change in {"producer_id", "validator_id"}:
        provenance[change] = "new-version"
        audit.expected = audit.expected.model_copy(update={change: "new-version"})
    elif change.endswith("version"):
        producer = change.startswith("producer")
        field = (
            "executed_collector_source_hash" if producer else "validator_source_hash"
        )
        pin = "producer_code_sha256" if producer else "validator_code_sha256"
        provenance[field] = "c" * 64
        audit.expected = audit.expected.model_copy(update={pin: "c" * 64})
    elif change == "criteria":
        criteria = {"symbols": ["IVV"], "retry": 0}
        audit.reports["request"]["criteria"] = criteria
        audit.expected = audit.expected.model_copy(
            update={"request_criteria": criteria}
        )
    elif change == "raw":
        audit.raw["content:prices"] = b"new raw content"
        contents = cast(list[dict[str, str]], audit.reports["result"]["contents"])
        contents[0]["sha256"] = _sha(audit.raw["content:prices"])
    elif change == "gate":
        gates = cast(list[dict[str, str]], audit.reports["validation"]["gates"])
        gates[0]["status"] = "PENDING"
    else:
        field = {
            "task": "source_task_id",
            "attempt": "source_attempt_id",
            "scope": "scope",
        }[change]
        for report in audit.reports.values():
            report[field] = "new-context"
        audit.expected = audit.expected.model_copy(update={field: "new-context"})
    audit.publish()
    assert audit.bind().status == "bound"
    assert audit.bind().semantic_sha256 != original


def test_metadata_format_order_and_normalization_do_not_change_digest(
    audit: Audit,
) -> None:
    original = audit.bind()
    for report in audit.reports.values():
        report["metadata"] = {
            "path": "/moved/artifact",
            "timestamp": "later",
            "prose": "new explanation",
        }
        report["scope"] = " collection-gates "
    audit.paths = {name: "moved/" + path for name, path in audit.paths.items()}
    audit.reports["result"]["contents"] = list(
        reversed(cast(list[object], audit.reports["result"]["contents"]))
    )
    gates = cast(list[dict[str, str]], audit.reports["validation"]["gates"])
    for gate in gates:
        gate["name"] = " " + gate["name"].lower() + " "
    audit.reports["validation"]["gates"] = list(reversed(gates))
    audit.reports["request"]["criteria"] = {
        "window": " frozen ",
        "retry": 0,
        "symbols": ["IVV", "SGOV"],
    }
    audit.publish(indent=4)
    current = audit.bind()
    assert current.status == "bound"
    assert current.semantic_sha256 == original.semantic_sha256
    assert current.artifact_sha256 != original.artifact_sha256


def test_gate_statuses_are_preserved_descriptively(audit: Audit) -> None:
    statuses = ["BLOCKED", "PENDING", "PASS", "FAIL", "NOT_EVALUATED"]
    audit.reports["validation"]["gates"] = [
        {"name": f"gate-{index}", "status": status}
        for index, status in enumerate(statuses)
    ]
    audit.publish()
    assert audit.bind().status == "bound"
    assert [gate.status for gate in audit.bind().gates] == statuses


@pytest.mark.parametrize(
    "corruption", ["identity", "gate", "criteria", "path", "content", "schema"]
)
def test_invalid_always_dominates_missing_producer_hash(
    audit: Audit, corruption: str
) -> None:
    audit.reports["provenance"]["executed_collector_source_hash"] = None
    if corruption == "identity":
        audit.reports["provenance"]["validator_source_hash"] = "c" * 64
    elif corruption == "gate":
        audit.reports["validation"]["gates"] = [{"name": "Prices", "status": "unknown"}]
    elif corruption == "criteria":
        audit.reports["request"]["criteria"] = {"changed": True}
    elif corruption == "content":
        audit.reports["result"]["contents"] = [
            {"content_id": "prices", "sha256": "c" * 64}
        ]
    elif corruption == "schema":
        audit.reports["provenance"]["schema_version"] = 2
    audit.publish()
    if corruption == "path":
        audit.paths["request"] = "../outside"
    result = audit.bind()
    assert result.status == "invalid"
    assert result.semantic_sha256 is None
    assert result.gates == []


def test_criteria_boolean_does_not_match_integer_pin(audit: Audit) -> None:
    audit.reports["request"]["criteria"] = {"count": True}
    audit.expected = audit.expected.model_copy(
        update={"request_criteria": {"count": 1}}
    )
    audit.publish()
    assert audit.bind().status == "invalid"


def test_unqualified_digest_includes_independent_producer_version(audit: Audit) -> None:
    audit.reports["provenance"]["executed_collector_source_hash"] = None
    audit.publish()
    first = audit.bind()
    audit.expected = audit.expected.model_copy(
        update={"producer_code_sha256": "c" * 64}
    )
    second = audit.bind()
    assert first.status == second.status == "unqualified"
    assert first.semantic_sha256 != second.semantic_sha256


def test_nonfinite_criteria_json_fails_closed(audit: Audit) -> None:
    audit.reports["request"]["criteria"] = {"count": 0}
    audit.publish()
    body = audit.raw["request"].replace(b'"count": 0', b'"count": 1e999')
    audit.reports.pop("request")
    audit.raw["request"] = body
    audit.publish()
    assert audit.bind().status == "invalid"
