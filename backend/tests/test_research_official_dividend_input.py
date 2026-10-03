from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from jusik.approved_universe import (
    ApprovedInstrument,
    ApprovedUniverseStore,
    ApprovedUniverseUpdate,
)
from jusik.research_action_collection_models import (
    CollectedAction,
    CollectedActionPayload,
)
from jusik.research_action_collection_store import ActionCollectionStore
from jusik.research_action_review import (
    EvidenceInput,
    ExtractedFacts,
    ReviewInput,
    ReviewManifest,
)
from jusik.research_action_review_store import ActionReviewStore
from jusik.research_official_dividend_input import freeze

NOW = datetime(2026, 10, 3, tzinfo=UTC)


def prepared(
    tmp_path: Path,
    *,
    vendor: str = "0.750",
    official: str = "0.75",
    exdate: date = date(2025, 2, 20),
    basis: bool = True,
) -> tuple[Path, Path, Path, Path, dict[str, object]]:
    approved = tmp_path / "approved.db"
    actions = tmp_path / "actions.db"
    registry = ApprovedUniverseStore(approved)
    registry.replace(
        ApprovedUniverseUpdate(
            revision=0,
            instruments=[
                ApprovedInstrument(market="US", exchange="NAS", symbol="MSFT")
            ],
        )
    )
    collection = ActionCollectionStore(actions)
    attempt = collection.begin_attempt(
        "MSFT", date(2025, 1, 1), date(2025, 3, 1), NOW - timedelta(days=1)
    )
    collection.complete_success(
        attempt_id=attempt,
        completed_at=NOW - timedelta(days=1),
        http_status=200,
        request_url="https://query1.finance.yahoo.com/x",
        body=b"{}",
        actions=[
            CollectedAction(
                provider_key="dividend-1",
                kind="dividend",
                payload=CollectedActionPayload(
                    vendor_date=date(2025, 2, 20), amount=vendor, currency="USD"
                ),
            )
        ],
    )
    revision = collection.revision_page(None, 100).items[0]
    raw = b"issuer dividend history"
    source = tmp_path / "official.raw"
    source.write_bytes(raw)
    evidence = EvidenceInput(
        local_file=source,
        sha256=hashlib.sha256(raw).hexdigest(),
        source_url="https://issuer.example/dividend",
        publisher="Issuer",
        locator="table row 1",
        captured_at=NOW - timedelta(days=1),
    )
    review = ReviewInput(
        review_key="review-1",
        revision_id=revision.id,
        content_sha256=revision.content_sha256,
        operator_verified=True,
        evidence=evidence,
        extracted_facts=ExtractedFacts(
            amount=official,
            currency="USD",
            comparable_share_basis=basis,
            ex_dividend_date=exdate,
            payment_date=date(2025, 3, 10),
        ),
    )
    ActionReviewStore(actions).import_manifest(
        ReviewManifest(schema_version=1, reviews=[review]), NOW
    )
    with sqlite3.connect(actions) as db:
        review_id = db.execute("SELECT id FROM action_reviews").fetchone()[0]
    identity_raw = b"issuer common shares on NASDAQ"
    identity_path = tmp_path / "identity.raw"
    identity_path.write_bytes(identity_raw)
    identity = {
        "issuer": "Microsoft Corporation",
        "security_type": "common stock",
        "share_class": "common",
        "operator_verified": True,
        "evidence": {
            "local_file": str(identity_path),
            "sha256": hashlib.sha256(identity_raw).hexdigest(),
            "source_url": "https://issuer.example/identity",
            "publisher": "Issuer",
            "locator": "common stock listing",
            "captured_at": (NOW - timedelta(days=1)).isoformat(),
        },
    }
    event = {
        "market": "US",
        "exchange": "NAS",
        "symbol": "MSFT",
        "event_id": revision.event_id,
        "revision_id": revision.id,
        "content_sha256": revision.content_sha256,
        "review_id": review_id,
        "identity": identity,
    }
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({"schema_version": 1, "approved_revision": 1, "events": [event]})
    )
    out = tmp_path / "out"
    out.mkdir()
    return approved, actions, manifest, out, event


def test_matched_idempotent_and_ordered_artifact(tmp_path: Path) -> None:
    approved, actions, manifest, out, _ = prepared(tmp_path)
    first = freeze(approved, actions, manifest, out)
    assert freeze(approved, actions, manifest, out) == first
    assert len(list(out.iterdir())) == 1
    data = json.loads(first.read_text())
    assert data["approved_registry"]["snapshot"]["revision"] == 1
    assert data["events"][0]["official"]["source_conflict_status"] == "matched"
    assert (
        data["events"][0]["official"]["amount_delta_official_minus_vendor"] == "0.000"
    )
    assert data["retrospective"] is True
    assert data["historical_pit_verified"] is False
    assert data["automatic_ledger_application"] is False
    assert data["nav_ready"] is False
    assert hashlib.sha256(first.read_bytes()).hexdigest() in first.name
    first.write_text("tampered")
    with pytest.raises(ValueError, match="Existing artifact"):
        freeze(approved, actions, manifest, out)


def test_amount_mismatch_keeps_exact_official_and_strict_status(tmp_path: Path) -> None:
    approved, actions, manifest, out, _ = prepared(
        tmp_path, vendor="0.010", official="0.01008"
    )
    data = json.loads(freeze(approved, actions, manifest, out).read_text())
    item = data["events"][0]
    assert item["official"]["review_status"] == "mismatched"
    assert item["official"]["source_conflict_status"] == "amount_mismatch"
    assert item["official"]["amount"] == "0.01008"
    assert item["source"]["vendor_amount"] == "0.010"
    assert item["official"]["amount_delta_official_minus_vendor"] == "0.00008"


@pytest.mark.parametrize(
    "change",
    [
        "revision",
        "review",
        "registration",
        "outside",
        "evidence",
        "identity",
        "currency",
        "exdate",
        "basis",
        "duplicate_event",
        "duplicate_exdate",
        "source_hash",
    ],
)
def test_invalid_pins_and_facts_fail(tmp_path: Path, change: str) -> None:
    approved, actions, manifest, out, event = prepared(tmp_path)
    payload = json.loads(manifest.read_text())
    if change == "revision":
        event["revision_id"] = "0" * 64
    elif change == "review":
        event["review_id"] = "0" * 64
    elif change == "registration":
        payload["approved_revision"] = 0
    elif change == "outside":
        event["symbol"] = "NVDA"
    elif change == "identity":
        Path(event["identity"]["evidence"]["local_file"]).write_bytes(b"changed")  # type: ignore[index]
    elif change == "evidence":
        with sqlite3.connect(actions) as db:
            db.execute("UPDATE action_review_evidence SET body=?", (b"changed",))
    elif change == "currency":
        with sqlite3.connect(actions) as db:
            db.execute(
                "UPDATE action_collection_revisions "
                "SET payload_json=replace(payload_json, 'USD', 'KRW')"
            )
    elif change == "exdate":
        with sqlite3.connect(actions) as db:
            db.execute(
                "UPDATE action_reviews SET extracted_facts_json="
                "replace(extracted_facts_json, '2025-02-20', '2025-02-21')"
            )
    elif change == "basis":
        with sqlite3.connect(actions) as db:
            db.execute(
                "UPDATE action_reviews SET extracted_facts_json="
                "replace(extracted_facts_json, 'true', 'false')"
            )
    elif change == "duplicate_event":
        payload["events"].append(event.copy())
    elif change == "duplicate_exdate":
        second = dict(event)
        second["event_id"] = "1" * 64
        payload["events"].append(second)
    elif change == "source_hash":
        event["content_sha256"] = "0" * 64
    payload["events"][0] = event
    manifest.write_text(json.dumps(payload))
    with pytest.raises((ValueError, TypeError)):
        freeze(approved, actions, manifest, out)
    assert not list(out.iterdir())


@pytest.mark.parametrize(
    "exdate,basis", [(date(2025, 2, 21), True), (date(2025, 2, 20), False)]
)
def test_official_exdate_or_share_basis_conflict_fails(
    tmp_path: Path, exdate: date, basis: bool
) -> None:
    approved, actions, manifest, out, _ = prepared(tmp_path, exdate=exdate, basis=basis)
    with pytest.raises(ValueError):
        freeze(approved, actions, manifest, out)


def test_missing_official_exdate_and_share_basis_fail(tmp_path: Path) -> None:
    approved, actions, manifest, out, _ = prepared(tmp_path)
    with sqlite3.connect(actions) as db:
        row = db.execute("SELECT extracted_facts_json FROM action_reviews").fetchone()
        facts = json.loads(row[0])
        facts["ex_dividend_date"] = None
        db.execute(
            "UPDATE action_reviews SET extracted_facts_json=?",
            (json.dumps(facts),),
        )
    with pytest.raises(ValueError):
        freeze(approved, actions, manifest, out)


def test_decimal_delta_remains_exact_at_bounds(tmp_path: Path) -> None:
    official_amount = "9" * 64
    approved, actions, manifest, out, _ = prepared(
        tmp_path,
        vendor="0." + "0" * 63 + "1",
        official=official_amount,
    )
    data = json.loads(freeze(approved, actions, manifest, out).read_text())
    official = data["events"][0]["official"]
    assert official["amount_delta_official_minus_vendor"] == (
        "9" * 63 + "8" + "." + "9" * 64
    )
