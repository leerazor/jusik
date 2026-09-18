from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import cast

import pytest

from jusik.market_history_action_receipt_preflight import (
    PreflightError,
    _check_attempts,
    _check_collection,
    _check_reviews,
    _evidence,
    _hash_object,
    _output_path,
    _read_snapshot,
    _review_content_hash,
    _review_representation,
    _sha,
    build_preflight,
)
from jusik.research_action_review import ExtractedFacts, compare_review

NOW = "2026-09-10T09:00:00+00:00"
EVIDENCE_BODY = b"official evidence"
EVIDENCE_SHA256 = hashlib.sha256(EVIDENCE_BODY).hexdigest()


def _fields(*, legacy: bool = False) -> list[dict[str, object]]:
    facts = ExtractedFacts(
        amount="0.01",
        currency="USD",
        comparable_share_basis=True,
        ex_dividend_date="2024-06-11",
    )
    _status, compared = compare_review(
        "dividend",
        {
            "vendor_date": "2024-06-11",
            "numerator": None,
            "denominator": None,
            "amount": "0.01",
            "currency": "USD",
        },
        facts,
    )
    fields = [item.model_dump(mode="json") for item in compared]
    if legacy:
        next(item for item in fields if item["field"] == "comparable_share_basis")[
            "source_value"
        ] = "true"
    return fields


def test_review_representation_accepts_only_canonical_or_legacy_v1() -> None:
    canonical = _fields()
    assert _review_representation(canonical, canonical, kind="dividend") == (
        "canonical-v1",
        None,
    )
    legacy = _fields(legacy=True)
    assert _review_representation(legacy, canonical, kind="dividend") == (
        "legacy-v1",
        "comparable_share_basis.source_value:true-to-null",
    )

    unknown = [*canonical, {"field": "unknown", "source_value": None}]
    with pytest.raises(PreflightError, match="not reproducible"):
        _review_representation(unknown, canonical, kind="dividend")
    with pytest.raises(PreflightError, match="not reproducible"):
        _review_representation(list(reversed(canonical)), canonical, kind="dividend")
    with pytest.raises(PreflightError, match="not reproducible"):
        _review_representation(legacy, canonical, kind="split")
    for value in ("false", False, 1):
        unknown_legacy = [dict(item) for item in canonical]
        share_basis = next(
            item for item in unknown_legacy if item["field"] == "comparable_share_basis"
        )
        share_basis["source_value"] = value
        with pytest.raises(PreflightError, match="not reproducible"):
            _review_representation(unknown_legacy, canonical, kind="dividend")


def test_attempt_requires_raw_sha_and_terminal_timestamp() -> None:
    body = b'{"chart":{"result":[],"error":null}}'
    row: dict[str, object] = {
        "id": "a" * 64,
        "symbol": "NVDA",
        "requested_start": "2024-01-01",
        "requested_end": "2024-12-31",
        "started_at": NOW,
        "completed_at": NOW,
        "state": "success",
        "http_status": 200,
        "request_url": "https://example.test",
        "body_sha256": hashlib.sha256(body).hexdigest(),
        "body": body,
        "error_code": None,
        "next_due_at": NOW,
    }
    checked = _check_attempts([row])
    assert checked["a" * 64]["body"] == body

    missing_sha = {**row, "body_sha256": None}
    with pytest.raises(PreflightError, match="invalid SHA"):
        _check_attempts([missing_sha])
    missing_timestamp = {**row, "completed_at": None}
    with pytest.raises(PreflightError, match="completion timestamp"):
        _check_attempts([missing_timestamp])
    with pytest.raises(PreflightError, match="invalid SHA"):
        _sha("0" * 63 + "g")
    with pytest.raises(PreflightError, match="duplicate collection attempt"):
        _check_attempts([row, row])


def test_fixed_input_sha_and_evidence_timestamp_are_fail_closed(tmp_path: Path) -> None:
    path = tmp_path / "input.db"
    path.write_bytes(b"fixture")
    with pytest.raises(PreflightError, match="fixed manifest"):
        _read_snapshot(path, tables=set(), caps={}, expected_sha256="a" * 64)
    evidence: dict[str, object] = {
        "id": EVIDENCE_SHA256,
        "sha256": EVIDENCE_SHA256,
        "source_url": "https://example.test/evidence",
        "publisher": "Example",
        "captured_at": None,
        "body": EVIDENCE_BODY,
        "created_at": NOW,
    }
    with pytest.raises(PreflightError, match="captured_at"):
        _evidence([evidence])


def test_duplicate_event_and_revision_identities_are_rejected() -> None:
    key = ("Yahoo chart", "NVDA", "dividend", "event-1")
    event_id = _hash_object(
        {
            "provider": key[0],
            "symbol": key[1],
            "kind": key[2],
            "provider_key": key[3],
        }
    )
    event: dict[str, object] = {
        "id": event_id,
        "provider": key[0],
        "symbol": key[1],
        "kind": key[2],
        "provider_key": key[3],
        "vendor_date": "2024-06-11",
        "first_seen_at": NOW,
        "last_seen_at": NOW,
        "observation_state": "observed",
        "latest_revision_sequence": 1,
        "latest_content_sha256": "e" * 64,
    }
    base: dict[str, list[dict[str, object]]] = {
        "action_collection_attempts": [],
        "action_collection_source_status": [],
        "action_collection_events": [event, dict(event)],
        "action_collection_revisions": [],
    }
    with pytest.raises(PreflightError, match="duplicate event identity"):
        _check_collection(base)


def test_compare_statuses_remain_partial_or_mismatched_without_normalization() -> None:
    source: dict[str, object] = {
        "vendor_date": "2024-06-11",
        "numerator": None,
        "denominator": None,
        "amount": "0.01",
        "currency": "USD",
    }
    partial_facts = ExtractedFacts(amount="0.01", currency="USD")
    mismatch_facts = ExtractedFacts(
        amount="0.02",
        currency="USD",
        comparable_share_basis=True,
        ex_dividend_date="2024-06-11",
    )
    partial_status, partial_fields = compare_review("dividend", source, partial_facts)
    mismatch_status, mismatch_fields = compare_review(
        "dividend", source, mismatch_facts
    )
    assert partial_status == "partial"
    assert mismatch_status == "mismatched"
    assert (
        _review_representation(
            [item.model_dump(mode="json") for item in partial_fields],
            [item.model_dump(mode="json") for item in partial_fields],
            kind="dividend",
        )[0]
        == "canonical-v1"
    )
    assert (
        _review_representation(
            [item.model_dump(mode="json") for item in mismatch_fields],
            [item.model_dump(mode="json") for item in mismatch_fields],
            kind="dividend",
        )[0]
        == "canonical-v1"
    )


def _review_rows(
    *,
    compared_fields: list[dict[str, object]] | None = None,
    review_key: str = "official-example",
) -> dict[str, list[dict[str, object]]]:
    revision_id = "b" * 64
    event_id = "c" * 64
    payload: dict[str, object] = {
        "vendor_date": "2024-06-11",
        "numerator": None,
        "denominator": None,
        "amount": "0.01",
        "currency": "USD",
    }
    facts = ExtractedFacts(
        amount="0.01",
        currency="USD",
        comparable_share_basis=True,
        ex_dividend_date="2024-06-11",
    )
    canonical = _fields()
    fields = canonical if compared_fields is None else compared_fields
    evidence: dict[str, object] = {
        "id": EVIDENCE_SHA256,
        "sha256": EVIDENCE_SHA256,
        "source_url": "https://example.test/evidence",
        "publisher": "Example",
        "captured_at": NOW,
        "body": EVIDENCE_BODY,
        "created_at": NOW,
    }
    row: dict[str, object] = {
        "id": "d" * 64,
        "review_key": review_key,
        "revision_id": revision_id,
        "sequence": 1,
        "source_content_sha256": "e" * 64,
        "evidence_id": EVIDENCE_SHA256,
        "locator": "table-1",
        "extracted_facts_json": facts.model_dump_json(),
        "comparison_status": "matched",
        "compared_fields_json": json.dumps(
            fields, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ),
        "content_sha256": "f" * 64,
        "reviewed_at": NOW,
        "imported_at": NOW,
    }
    revision: dict[str, object] = {
        "id": revision_id,
        "event": {
            "id": event_id,
            "key": ("Yahoo chart", "NVDA", "dividend", "event-1"),
        },
        "sequence": 1,
        "content_sha256": "e" * 64,
        "first_seen_at": NOW,
        "attempt_id": "1" * 64,
        "payload": payload,
        "receipt_body_sha256": "2" * 64,
        "receipt_completed_at": NOW,
    }
    row["content_sha256"] = _review_content_hash(row, facts, evidence)
    row["id"] = hashlib.sha256(
        json.dumps(
            {"review_key": row["review_key"], "content": row["content_sha256"]},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    return {
        "action_review_evidence": [evidence],
        "action_reviews": [row],
        "revisions": [revision],
    }


def test_review_raw_hash_and_identity_are_checked_before_adapter() -> None:
    rows = _review_rows(compared_fields=_fields(legacy=True))
    records, _summary = _check_reviews(
        {
            "action_review_evidence": rows["action_review_evidence"],
            "action_reviews": rows["action_reviews"],
        },
        {"b" * 64: rows["revisions"][0]},
    )
    provenance = cast(dict[str, object], records[0]["compared_fields"])
    assert provenance["normalization_version"] == "legacy-v1"
    raw_json = cast(str, provenance["raw_json"])
    assert raw_json == rows["action_reviews"][0]["compared_fields_json"]
    assert (
        provenance["raw_sha256"] == hashlib.sha256(raw_json.encode("utf-8")).hexdigest()
    )
    assert records[0]["eligibility"] == "blocked"
    assert "coverage_incomplete" in cast(list[object], records[0]["blocked_reasons"])

    spaced = _review_rows()
    spaced_fields = json.dumps(_fields(), indent=2, ensure_ascii=False)
    spaced["action_reviews"][0]["compared_fields_json"] = spaced_fields
    spaced_records, _ = _check_reviews(
        {
            "action_review_evidence": spaced["action_review_evidence"],
            "action_reviews": spaced["action_reviews"],
        },
        {"b" * 64: spaced["revisions"][0]},
    )
    spaced_provenance = cast(dict[str, object], spaced_records[0]["compared_fields"])
    assert spaced_provenance["raw_json"] == spaced_fields

    synthetic = _review_rows(review_key="synthetic-overlay-example")
    synthetic_records, _ = _check_reviews(
        {
            "action_review_evidence": synthetic["action_review_evidence"],
            "action_reviews": synthetic["action_reviews"],
        },
        {"b" * 64: synthetic["revisions"][0]},
    )
    assert synthetic_records[0]["eligibility"] == "excluded"

    bad_hash = dict(rows["action_reviews"][0])
    bad_hash["content_sha256"] = "0" * 64
    with pytest.raises(PreflightError, match="content hash"):
        _check_reviews(
            {
                "action_review_evidence": rows["action_review_evidence"],
                "action_reviews": [bad_hash],
            },
            {"b" * 64: rows["revisions"][0]},
        )

    duplicate = _review_rows()
    duplicate["action_reviews"].append(dict(duplicate["action_reviews"][0]))
    with pytest.raises(PreflightError, match="duplicate review key"):
        _check_reviews(
            {
                "action_review_evidence": duplicate["action_review_evidence"],
                "action_reviews": duplicate["action_reviews"],
            },
            {"b" * 64: duplicate["revisions"][0]},
        )


def test_artifact_linkage_is_explicit_without_synthesizing_replay(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    empty_tables: dict[str, list[dict[str, object]]] = {
        "action_collection_attempts": [],
        "action_collection_source_status": [],
        "action_collection_events": [],
        "action_collection_revisions": [],
        "action_review_evidence": [],
        "action_reviews": [],
    }

    def snapshot(
        *_args: object, **_kwargs: object
    ) -> tuple[dict[str, list[dict[str, object]]], dict[str, object]]:
        return empty_tables, {
            "path": "fixture",
            "sha256": "0" * 64,
            "size_bytes": 0,
            "tables": {},
        }

    monkeypatch.setattr(
        "jusik.market_history_action_receipt_preflight._read_snapshot", snapshot
    )
    result = build_preflight(
        tmp_path / "collection.db",
        tmp_path / "review.db",
        expected_collection_sha256=None,
        expected_review_sha256=None,
    )
    assert result["artifact_replay"] is None
    linkage = cast(dict[str, object], result["artifact_linkage"])
    assert linkage["linked"] is False
    assert "price_inputs" in cast(list[object], linkage["missing_fields"])


def test_output_rejects_symlink_parent(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    with pytest.raises(PreflightError, match="symlink path"):
        _output_path(link / "output.json")
