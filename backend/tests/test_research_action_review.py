import hashlib
import json
import sqlite3
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Literal

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from jusik.research_action_collection_models import (
    CollectedAction,
    CollectedActionPayload,
)
from jusik.research_action_collection_store import ActionCollectionStore
from jusik.research_action_review import (
    MAX_EVIDENCE_BYTES,
    EvidenceInput,
    ExtractedFacts,
    ReviewInput,
    ReviewManifest,
)
from jusik.research_action_review_store import ActionReviewStore
from jusik.research_app import create_research_app
from jusik.research_config import PAPER_BASE_URL, ResearchSettings
from jusik.research_models import ResearchInputSnapshot, ResearchRunRequest
from jusik.research_universe_data import REGISTRY

NOW = datetime(2026, 9, 10, 10, tzinfo=UTC)
START = date(2023, 9, 11)
END = date(2026, 9, 10)


def action(
    kind: Literal["split", "dividend"] = "split", value: str = "10"
) -> CollectedAction:
    if kind == "split":
        payload = CollectedActionPayload(
            vendor_date=date(2024, 6, 10), numerator=int(value), denominator=1
        )
    else:
        payload = CollectedActionPayload(
            vendor_date=date(2024, 6, 11), amount=value, currency="USD"
        )
    return CollectedAction(provider_key=f"key-{kind}", kind=kind, payload=payload)


def collect(store: ActionCollectionStore, item: CollectedAction, at: datetime) -> str:
    attempt = store.begin_attempt("NVDA", START, END, at)
    store.complete_success(
        attempt_id=attempt,
        completed_at=at,
        http_status=200,
        request_url="https://query1.finance.yahoo.com/test",
        body=b"{}",
        actions=[item],
    )
    return next(
        revision.id
        for revision in store.revision_page(None, 100).items
        if revision.kind == item.kind and revision.provider_key == item.provider_key
    )


def evidence(path: Path, body: bytes = b"official evidence") -> EvidenceInput:
    path.write_bytes(body)
    return EvidenceInput(
        local_file=path,
        sha256=hashlib.sha256(body).hexdigest(),
        source_url="https://issuer.example/actions/document",
        publisher="Example Issuer",
        locator="page 1, action table",
        captured_at=NOW - timedelta(minutes=1),
    )


def review(
    collection: ActionCollectionStore,
    revision_id: str,
    evidence_input: EvidenceInput,
    facts: ExtractedFacts,
    key: str = "review-1",
) -> ReviewInput:
    revision = next(
        item
        for item in collection.revision_page(None, 100).items
        if item.id == revision_id
    )
    return ReviewInput(
        review_key=key,
        revision_id=revision_id,
        content_sha256=revision.content_sha256,
        operator_verified=True,
        evidence=evidence_input,
        extracted_facts=facts,
    )


def test_comparator_matched_partial_and_mismatched(tmp_path: Path) -> None:
    database = tmp_path / "actions.db"
    collection = ActionCollectionStore(database)
    collection.ensure_sources(REGISTRY, NOW)
    split_revision = collect(collection, action(), NOW)
    dividend_revision = collect(collection, action("dividend", "0.01"), NOW)
    document = evidence(tmp_path / "official.body")
    store = ActionReviewStore(database)
    manifest = ReviewManifest(
        schema_version=1,
        reviews=[
            review(
                collection,
                split_revision,
                document,
                ExtractedFacts(
                    numerator=20,
                    denominator=2,
                    adjusted_trading_date=date(2024, 6, 10),
                    legal_effective_date=date(2024, 6, 7),
                ),
                "split-match",
            ),
            review(
                collection,
                dividend_revision,
                document,
                ExtractedFacts(
                    amount="0.010",
                    currency="USD",
                    comparable_share_basis=True,
                    ex_dividend_date=None,
                    record_date=date(2024, 6, 11),
                    payment_date=date(2024, 6, 28),
                ),
                "dividend-partial",
            ),
        ],
    )
    assert store.import_manifest(manifest, NOW) == {"inserted": 2, "idempotent": 0}
    by_key = {item.review_key: item for item in store.review_page(None, 50).items}
    assert by_key["split-match"].comparison_status == "matched"
    assert by_key["dividend-partial"].comparison_status == "partial"
    assert (
        next(
            item
            for item in by_key["dividend-partial"].compared_fields
            if item.field == "amount"
        ).status
        == "matched"
    )
    basis = next(
        item
        for item in by_key["dividend-partial"].compared_fields
        if item.field == "comparable_share_basis"
    )
    assert basis.status == "matched"
    assert basis.source_value is None

    with sqlite3.connect(database) as connection:
        stored = json.loads(
            connection.execute(
                "SELECT compared_fields_json FROM action_reviews WHERE review_key=?",
                ("dividend-partial",),
            ).fetchone()[0]
        )
        next(field for field in stored if field["field"] == "comparable_share_basis")[
            "source_value"
        ] = "true"
        connection.execute(
            "UPDATE action_reviews SET compared_fields_json=? WHERE review_key=?",
            (json.dumps(stored), "dividend-partial"),
        )
    legacy_basis = next(
        item
        for item in {
            item.review_key: item for item in store.review_page(None, 50).items
        }["dividend-partial"].compared_fields
        if item.field == "comparable_share_basis"
    )
    assert legacy_basis.source_value is None
    assert legacy_basis.status == "matched"

    mismatch = review(
        collection,
        dividend_revision,
        document,
        ExtractedFacts(
            amount="0.02",
            currency="USD",
            comparable_share_basis=True,
            ex_dividend_date=date(2024, 6, 11),
        ),
        "dividend-mismatch",
    )
    store.import_manifest(ReviewManifest(schema_version=1, reviews=[mismatch]), NOW)
    reviews = {item.review_key: item for item in store.review_page(None, 10).items}
    assert reviews["dividend-mismatch"].comparison_status == "mismatched"


def test_idempotent_import_and_correction_chain(tmp_path: Path) -> None:
    database = tmp_path / "actions.db"
    collection = ActionCollectionStore(database)
    collection.ensure_sources(REGISTRY, NOW)
    revision = collect(collection, action(), NOW)
    document = evidence(tmp_path / "official.body")
    first = review(
        collection,
        revision,
        document,
        ExtractedFacts(
            numerator=10,
            denominator=1,
            adjusted_trading_date=date(2024, 6, 10),
        ),
    )
    store = ActionReviewStore(database)
    manifest = ReviewManifest(schema_version=1, reviews=[first])
    store.import_manifest(manifest, NOW)
    original = store.review_page(None, 10).items[0]
    assert store.import_manifest(manifest, NOW + timedelta(days=1)) == {
        "inserted": 0,
        "idempotent": 1,
    }
    unchanged = store.review_page(None, 10).items[0]
    assert unchanged.imported_at == original.imported_at

    correction = first.model_copy(
        update={
            "review_key": "review-2",
            "extracted_facts": first.extracted_facts.model_copy(
                update={"adjusted_trading_date": date(2024, 6, 11)}
            ),
        }
    )
    store.import_manifest(
        ReviewManifest(schema_version=1, reviews=[correction]),
        NOW + timedelta(days=1),
    )
    assert sorted(item.sequence for item in store.review_page(None, 10).items) == [
        1,
        2,
    ]


def test_manifest_conflict_rolls_back_whole_batch(tmp_path: Path) -> None:
    database = tmp_path / "actions.db"
    collection = ActionCollectionStore(database)
    collection.ensure_sources(REGISTRY, NOW)
    revision = collect(collection, action(), NOW)
    document = evidence(tmp_path / "official.body")
    base = review(
        collection,
        revision,
        document,
        ExtractedFacts(
            numerator=10,
            denominator=1,
            adjusted_trading_date=date(2024, 6, 10),
        ),
    )
    store = ActionReviewStore(database)
    store.import_manifest(ReviewManifest(schema_version=1, reviews=[base]), NOW)
    new = base.model_copy(update={"review_key": "new-valid"})
    conflict = base.model_copy(
        update={
            "extracted_facts": base.extracted_facts.model_copy(update={"numerator": 2})
        }
    )
    with pytest.raises(ValueError, match="Review key conflicts"):
        store.import_manifest(
            ReviewManifest(schema_version=1, reviews=[new, conflict]),
            NOW + timedelta(hours=1),
        )
    assert [item.review_key for item in store.review_page(None, 10).items] == [
        "review-1"
    ]


@pytest.mark.parametrize("invalid_file", ["different", "missing", "oversize"])
def test_each_evidence_file_is_verified_before_sha_deduplication(
    tmp_path: Path, invalid_file: str
) -> None:
    database = tmp_path / "actions.db"
    collection = ActionCollectionStore(database)
    collection.ensure_sources(REGISTRY, NOW)
    revision = collect(collection, action(), NOW)
    good = evidence(tmp_path / "good.body")
    first = review(
        collection,
        revision,
        good,
        ExtractedFacts(
            numerator=10,
            denominator=1,
            adjusted_trading_date=date(2024, 6, 10),
        ),
        "good-review",
    )
    second_path = tmp_path / "second.body"
    if invalid_file == "different":
        second_path.write_bytes(b"different bytes")
    elif invalid_file == "oversize":
        second_path.write_bytes(b"x" * (MAX_EVIDENCE_BYTES + 1))
    second_evidence = good.model_copy(update={"local_file": second_path})
    second = first.model_copy(
        update={"review_key": "invalid-review", "evidence": second_evidence}
    )
    store = ActionReviewStore(database)

    with pytest.raises(ValueError):
        store.import_manifest(
            ReviewManifest(schema_version=1, reviews=[first, second]), NOW
        )

    assert store.review_page(None, 10).items == []
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM action_review_evidence"
        ).fetchone() == (0,)


def test_review_is_exact_revision_and_does_not_follow_a_b_a(tmp_path: Path) -> None:
    database = tmp_path / "actions.db"
    collection = ActionCollectionStore(database)
    collection.ensure_sources(REGISTRY, NOW)
    first_revision = collect(collection, action(value="10"), NOW)
    collect(collection, action(value="20"), NOW + timedelta(hours=25))
    latest_revision = collect(collection, action(value="10"), NOW + timedelta(hours=50))
    assert latest_revision != first_revision
    item = review(
        collection,
        first_revision,
        evidence(tmp_path / "official.body"),
        ExtractedFacts(
            numerator=10,
            denominator=1,
            adjusted_trading_date=date(2024, 6, 10),
        ),
    )
    store = ActionReviewStore(database)
    store.import_manifest(ReviewManifest(schema_version=1, reviews=[item]), NOW)
    page = store.review_page(None, 10)
    assert page.items[0].current_revision is False
    assert page.items[0].needs_review is True
    assert page.current_revision_count == 1
    assert page.unreviewed_current_revision_count == 1


def test_manifest_and_evidence_security_validation(tmp_path: Path) -> None:
    body = b"official"
    path = tmp_path / "official.body"
    path.write_bytes(body)
    with pytest.raises(ValidationError):
        EvidenceInput(
            local_file=path,
            sha256=hashlib.sha256(body).hexdigest(),
            source_url="https://user:secret@issuer.example/file",
            publisher="Issuer",
            locator="page 1",
            captured_at=NOW,
        )
    with pytest.raises(ValidationError):
        ExtractedFacts(amount="1e100000")


def test_review_api_filters_and_verifies_evidence_hash(tmp_path: Path) -> None:
    class UnusedProvider:
        async def collect(self, request: ResearchRunRequest) -> ResearchInputSnapshot:
            raise AssertionError(f"Unexpected collection: {request}")

    database = tmp_path / "actions.db"
    collection = ActionCollectionStore(database)
    collection.ensure_sources(REGISTRY, NOW)
    revision = collect(collection, action(), NOW)
    document = evidence(tmp_path / "official.body")
    item = review(
        collection,
        revision,
        document,
        ExtractedFacts(
            numerator=10,
            denominator=1,
            adjusted_trading_date=date(2024, 6, 10),
        ),
    )
    store = ActionReviewStore(database)
    store.import_manifest(ReviewManifest(schema_version=1, reviews=[item]), NOW)
    event_id = collection.revision_page(None, 10).items[0].event_id
    app = create_research_app(
        settings=ResearchSettings(
            app_key="test-key",
            app_secret="test-secret",
            base_url=PAPER_BASE_URL,
            db_path=tmp_path / "research.db",
        ),
        provider=UnusedProvider(),
        forward_db_path=tmp_path / "forward.db",
        universe_db_path=tmp_path / "universe.db",
        external_db_path=tmp_path / "external.db",
        history_dir=tmp_path / "history",
        history_db_path=tmp_path / "history.db",
        action_collection_db_path=database,
        action_collection_enabled=False,
    )
    with TestClient(app) as client:
        response = client.get(
            "/api/research/actions/reviews", params={"event_id": event_id}
        )
        assert response.status_code == 200
        assert response.json()["items"][0]["source_payload"]["numerator"] == 10
        assert "local_file" not in str(response.json())
        evidence_id = response.json()["items"][0]["evidence"]["id"]
        raw = client.get(f"/api/research/actions/evidence/{evidence_id}")
        assert raw.status_code == 200
        assert raw.headers["content-type"] == "application/octet-stream"
        assert (
            hashlib.sha256(raw.content).hexdigest() == raw.headers["x-content-sha256"]
        )
        assert (
            client.get("/api/research/actions/evidence/..%2Fsecret").status_code == 404
        )
        with sqlite3.connect(database) as connection:
            connection.execute(
                "UPDATE action_review_evidence SET body=? WHERE id=?",
                (b"tampered", evidence_id),
            )
        assert (
            client.get(f"/api/research/actions/evidence/{evidence_id}").status_code
            == 404
        )
