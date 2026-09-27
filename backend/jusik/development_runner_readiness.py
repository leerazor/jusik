"""Offline receipt binding only; binding never grants readiness or approval.

Version 1 uses strict JSON envelopes and caller-owned, independently pinned
expectations. Paths are root-relative mapping values, never receipt instructions.
Criteria object keys and strings use NFC and trimmed whitespace; array order is
significant. Metadata is opaque prose and excluded from the semantic identity.
Exact artifact hashes bind serialization separately from semantic identity.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import stat
import unicodedata
from collections.abc import Mapping
from contextlib import ExitStack
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    field_validator,
    model_validator,
)

Sha256 = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Identifier = Annotated[str, Field(min_length=1, max_length=200, pattern=r"\S")]
GateStatus = Literal["BLOCKED", "PENDING", "PASS", "FAIL", "NOT_EVALUATED"]
_REPORTS = frozenset({"request", "result", "validation", "provenance"})
_MAX_BYTES = 32 * 1024 * 1024


def _text(value: str) -> str:
    return unicodedata.normalize("NFC", value).strip()


def _normalize(value: JsonValue) -> JsonValue:
    if isinstance(value, str):
        return _text(value)
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    if isinstance(value, dict):
        normalized: dict[str, JsonValue] = {}
        for key, item in value.items():
            name = _text(key)
            if not name or name in normalized:
                raise ValueError("ambiguous criteria key")
            normalized[name] = _normalize(item)
        return normalized
    return value


def _digest(value: object) -> str:
    body = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ReceiptContext(_StrictModel):
    source_task_id: Identifier
    source_attempt_id: Identifier
    scope: Identifier

    @model_validator(mode="after")
    def nonempty_context(self) -> Self:
        if not all(
            _text(value)
            for value in (
                self.source_task_id,
                self.source_attempt_id,
                self.scope,
            )
        ):
            raise ValueError("empty context")
        return self


class ReadinessExpectations(ReceiptContext):
    """Pins supplied independently of the artifacts being verified."""

    receipt_sha256: Sha256
    request_criteria: dict[str, JsonValue] = Field(min_length=1)
    producer_id: Identifier
    producer_code_sha256: Sha256
    validator_id: Identifier
    validator_code_sha256: Sha256


class _Envelope(ReceiptContext):
    schema_version: Literal[1]

    @field_validator("schema_version", mode="before")
    @classmethod
    def strict_version(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("schema version must be an integer")
        return value

    metadata: dict[str, str] = Field(default_factory=dict)


class ExternalReadinessReceipt(_Envelope):
    artifact_sha256: dict[str, Sha256] = Field(min_length=5)


class _Request(_Envelope):
    criteria: dict[str, JsonValue] = Field(min_length=1)


class ContentIdentity(_StrictModel):
    content_id: Identifier
    sha256: Sha256


class _Result(_Envelope):
    contents: list[ContentIdentity] = Field(min_length=1)


class ReadinessGate(_StrictModel):
    name: Identifier
    status: GateStatus


class _Validation(_Envelope):
    gates: list[ReadinessGate] = Field(min_length=1)


class _Provenance(_Envelope):
    producer_id: Identifier
    executed_collector_source_hash: Sha256 | None
    validator_id: Identifier
    validator_source_hash: Sha256


class ReadinessBinding(_StrictModel):
    """Descriptive binding result, with no readiness or approval capability."""

    status: Literal["bound", "unqualified", "invalid"]
    reason: Literal["verified", "missing_producer_hash", "invalid_receipt"]
    semantic_sha256: Sha256 | None = None
    artifact_sha256: dict[str, Sha256] = Field(default_factory=dict)
    gates: list[ReadinessGate] = Field(default_factory=list)


def _unique_object(pairs: list[tuple[str, JsonValue]]) -> dict[str, JsonValue]:
    result: dict[str, JsonValue] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError("nonfinite JSON number")


def _finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("nonfinite JSON number")
    return number


def _json(body: bytes) -> object:
    return json.loads(
        body.decode("utf-8"),
        object_pairs_hook=_unique_object,
        parse_constant=_reject_constant,
        parse_float=_finite_float,
    )


def _parts(path: str) -> list[str]:
    parts = path.split("/")
    if not path or any(part in {"", ".", ".."} for part in parts):
        raise ValueError("unsafe artifact path")
    return parts


class _ArtifactReader:
    """Walk open directory descriptors with O_NOFOLLOW, including root ancestors."""

    def __init__(self, root: Path, stack: ExitStack) -> None:
        if not root.is_absolute() or ".." in root.parts:
            raise ValueError("artifact root must be absolute")
        self._stack = stack
        self._root_fd = self._directory("/", None)
        for part in root.parts[1:]:
            self._root_fd = self._directory(part, self._root_fd)

    def _directory(self, name: str, parent: int | None) -> int:
        descriptor = os.open(
            name,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
            dir_fd=parent,
        )
        self._stack.callback(os.close, descriptor)
        return descriptor

    def read(self, path: str) -> bytes:
        parts = _parts(path)
        parent = self._root_fd
        for part in parts[:-1]:
            parent = self._directory(part, parent)
        descriptor = os.open(
            parts[-1],
            os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
            dir_fd=parent,
        )
        with os.fdopen(descriptor, "rb") as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_size > _MAX_BYTES:
                raise ValueError("artifact must be a bounded regular file")
            body = stream.read(_MAX_BYTES + 1)
            after = os.fstat(stream.fileno())
            if len(body) > _MAX_BYTES or (
                before.st_size,
                before.st_mtime_ns,
                before.st_ctime_ns,
            ) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                raise ValueError("artifact changed during read")
            return body


def _context(value: ReceiptContext) -> tuple[str, str, str]:
    return value.source_task_id, value.source_attempt_id, _text(value.scope)


def bind_external_readiness(
    *,
    artifact_root: Path,
    artifact_paths: Mapping[str, str],
    expected: ReadinessExpectations,
) -> ReadinessBinding:
    """Validate one offline snapshot; all validation failures dominate missing hash.

    Mapping keys are receipt/request/result/validation/provenance and
    ``content:<content_id>`` for each result content. Content is opaque bytes.
    Every envelope repeats the source task, attempt and scope. The caller must
    obtain expectations through an independent trusted channel; self-reported
    pins do not establish trust. No file is written and no provider is called.
    """
    try:
        # Revalidate even instances made with model_construct/model_copy.
        pins = ReadinessExpectations.model_validate(expected.model_dump())
        paths = dict(artifact_paths)
        if len(set(paths.values())) != len(paths):
            raise ValueError("aliased artifact paths")
        with ExitStack() as stack:
            reader = _ArtifactReader(artifact_root, stack)
            receipt_body = reader.read(paths["receipt"])
            receipt_hash = hashlib.sha256(receipt_body).hexdigest()
            if receipt_hash != pins.receipt_sha256:
                raise ValueError("receipt hash mismatch")
            receipt = ExternalReadinessReceipt.model_validate(_json(receipt_body))
            if set(paths) != {"receipt", *receipt.artifact_sha256}:
                raise ValueError("artifact mapping mismatch")
            if not _REPORTS.issubset(receipt.artifact_sha256):
                raise ValueError("missing report")
            bodies = {}
            hashes = {"receipt": receipt_hash}
            for name, expected_hash in receipt.artifact_sha256.items():
                body = reader.read(paths[name])
                actual = hashlib.sha256(body).hexdigest()
                if actual != expected_hash:
                    raise ValueError("artifact hash mismatch")
                bodies[name] = body
                hashes[name] = actual
        request = _Request.model_validate(_json(bodies["request"]))
        result = _Result.model_validate(_json(bodies["result"]))
        validation = _Validation.model_validate(_json(bodies["validation"]))
        provenance = _Provenance.model_validate(_json(bodies["provenance"]))
        for envelope in (receipt, request, result, validation, provenance):
            if _context(envelope) != _context(pins):
                raise ValueError("context mismatch")
        criteria = _normalize(request.criteria)
        if _digest(criteria) != _digest(_normalize(pins.request_criteria)):
            raise ValueError("criteria mismatch")
        if (
            provenance.producer_id != pins.producer_id
            or provenance.validator_id != pins.validator_id
            or provenance.validator_source_hash != pins.validator_code_sha256
            or (
                provenance.executed_collector_source_hash is not None
                and provenance.executed_collector_source_hash
                != pins.producer_code_sha256
            )
        ):
            raise ValueError("provenance mismatch")
        contents: dict[str, str] = {}
        for content in result.contents:
            name = _text(content.content_id)
            if not name or name in contents:
                raise ValueError("duplicate or empty content identity")
            contents[name] = content.sha256
            if hashes.get(f"content:{name}") != content.sha256:
                raise ValueError("content identity mismatch")
        if set(receipt.artifact_sha256) != _REPORTS | {
            f"content:{name}" for name in contents
        }:
            raise ValueError("unexpected artifact")
        gates: dict[str, str] = {}
        for gate in validation.gates:
            name = _text(gate.name).casefold()
            if not name or name in gates:
                raise ValueError("duplicate or empty gate")
            gates[name] = gate.status
        semantic = _digest(
            {
                "schema_version": 1,
                "context": _context(pins),
                "criteria": criteria,
                "contents": contents,
                "producer": [
                    provenance.producer_id,
                    pins.producer_code_sha256,
                    provenance.executed_collector_source_hash,
                ],
                "validator": [
                    provenance.validator_id,
                    provenance.validator_source_hash,
                ],
                "gates": gates,
            }
        )
        missing = provenance.executed_collector_source_hash is None
        return ReadinessBinding(
            status="unqualified" if missing else "bound",
            reason="missing_producer_hash" if missing else "verified",
            semantic_sha256=semantic,
            artifact_sha256=hashes,
            gates=validation.gates,
        )
    except (ValueError, TypeError, KeyError, OSError, RecursionError):
        # Do not echo artifact paths, arbitrary prose or external identifiers.
        return ReadinessBinding(status="invalid", reason="invalid_receipt")
