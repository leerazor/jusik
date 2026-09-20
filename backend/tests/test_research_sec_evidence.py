import asyncio
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from jusik.research_action_review import ExtractedFacts
from jusik.research_sec_evidence import (
    SEC_REVIEW_QUEUE_REQUIRED_FIELDS,
    SecActionReviewForm,
    SecActionReviewFormItem,
    SecFiling,
    SecFilingCandidate,
    SecReviewQueue,
    SecReviewQueueItem,
    _main,
    build_sec_action_review_input,
    build_sec_review_manifest,
    build_sec_review_queue,
    collect_sec_filing_candidates,
    filing_document_url,
    load_sec_review_reference_queue,
    parse_sec_filing_candidate,
    parse_sec_submissions,
    parse_sec_ticker_map,
    validate_sec_action_review_form,
    verify_sec_review_queue_sources,
)


def test_parse_sec_submissions_preserves_acceptance_and_raw_hash() -> None:
    body = json.dumps(
        {
            "cik": "1045810",
            "filings": {
                "recent": {
                    "form": ["8-K", "10-Q"],
                    "accessionNumber": [
                        "0001045810-24-000144",
                        "0001045810-24-000100",
                    ],
                    "filingDate": ["2024-06-07", "2024-05-01"],
                    "acceptanceDateTime": ["20240607153000", "20240501120000"],
                    "primaryDocument": ["event.htm", "quarter.htm"],
                }
            },
        }
    ).encode()

    result = parse_sec_submissions(
        body,
        observed_at=datetime(2026, 9, 19, 12, tzinfo=UTC),
        source_url="https://data.sec.gov/submissions/CIK0001045810.json",
    )

    assert len(result) == 2
    assert result[0].cik == "0001045810"
    assert result[0].acceptance_datetime == datetime(2024, 6, 7, 19, 30, tzinfo=UTC)
    assert result[0].primary_document == "event.htm"
    assert len(result[0].raw_sha256) == 64


def test_parse_sec_ticker_map_normalizes_cik_and_filters_symbols() -> None:
    body = (
        b'{"0":{"cik_str":1045810,"ticker":"NVDA","title":"NVIDIA"},'
        b'"1":{"cik_str":789,"ticker":"OTHER","title":"Other"}}'
    )

    result = parse_sec_ticker_map(body, symbols=("NVDA",))

    assert result[0].ticker == "NVDA"
    assert result[0].cik == "0001045810"


def test_filing_document_url_and_candidate_parser_are_fail_closed() -> None:
    filing = SecFiling(
        cik="0001045810",
        accession_number="0001045810-24-000144",
        form="8-K",
        filing_date="2024-06-07",
        primary_document="event.htm",
        source_url="https://data.sec.gov/submissions/CIK0001045810.json",
        observed_at=datetime(2026, 9, 19, 12, tzinfo=UTC),
        raw_sha256="0" * 64,
    )

    source_url = filing_document_url(filing)
    result = parse_sec_filing_candidate(
        b"The company declared a dividend and announced a stock split.",
        filing=filing,
        observed_at=datetime(2026, 9, 19, 12, tzinfo=UTC),
        source_url=source_url,
    )

    assert source_url.endswith("/1045810/000104581024000144/event.htm")
    assert result.candidate_kinds == ("dividend", "split")
    assert len(result.candidate_snippets) == 2
    assert "dividend" in result.candidate_snippets[0].lower()
    assert len(result.raw_sha256) == 64

    missing_document = filing.model_copy(update={"primary_document": None})
    with pytest.raises(ValueError, match="primary_document"):
        filing_document_url(missing_document)


def test_collect_sec_filing_candidates_is_bounded_and_persists_raw(
    tmp_path: Path,
) -> None:
    filing = SecFiling(
        cik="0001045810",
        accession_number="0001045810-24-000144",
        form="8-K",
        filing_date="2024-06-07",
        primary_document="event.htm",
        source_url="https://data.sec.gov/submissions/CIK0001045810.json",
        observed_at=datetime(2026, 9, 19, 12, tzinfo=UTC),
        raw_sha256="0" * 64,
    )
    requests: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        return httpx.Response(200, content=b"dividend", request=request)

    async def run() -> tuple:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            return await collect_sec_filing_candidates(
                filings=(filing, filing, filing),
                output_dir=tmp_path,
                max_documents=1,
                user_agent="test-agent",
                client=client,
            )

    result = asyncio.run(run())
    assert len(result) == 1
    assert result[0].candidate_kinds == ("dividend",)
    assert len(requests) == 1
    assert list(tmp_path.glob("sec-filing-*.html"))


def test_sec_candidate_adapter_requires_manual_facts_and_rejects_unresolved_kind(
    tmp_path: Path,
) -> None:
    evidence_body = b"declared a dividend"
    evidence_path = tmp_path / "doc.htm"
    evidence_path.write_bytes(evidence_body)
    candidate = SecFilingCandidate(
        cik="0001045810",
        accession_number="0001045810-24-000144",
        form="8-K",
        source_url="https://www.sec.gov/Archives/edgar/data/1045810/doc.htm",
        observed_at=datetime(2026, 9, 19, 12, tzinfo=UTC),
        raw_sha256=hashlib.sha256(evidence_body).hexdigest(),
        candidate_kinds=("dividend",),
        candidate_snippets=("declared a dividend",),
    )
    review = build_sec_action_review_input(
        candidate,
        local_file=evidence_path,
        extracted_facts=ExtractedFacts(
            amount="0.10",
            currency="USD",
            ex_dividend_date=datetime(2024, 6, 7, tzinfo=UTC).date(),
            comparable_share_basis=True,
        ),
        operator_verified=True,
        revision_id="3" * 64,
        content_sha256="4" * 64,
    )
    assert review.operator_verified is True
    assert review.review_key.endswith(":dividend")

    with pytest.raises(ValueError, match="evidence_hash_mismatch"):
        build_sec_action_review_input(
            candidate.model_copy(update={"raw_sha256": "1" * 64}),
            local_file=evidence_path,
            extracted_facts=ExtractedFacts(),
            operator_verified=True,
            revision_id="3" * 64,
            content_sha256="4" * 64,
        )
    with pytest.raises(ValueError, match="evidence_file_missing"):
        build_sec_action_review_input(
            candidate,
            local_file=tmp_path / "missing.htm",
            extracted_facts=ExtractedFacts(),
            operator_verified=True,
            revision_id="3" * 64,
            content_sha256="4" * 64,
        )

    with pytest.raises(ValueError, match="operator_verification"):
        build_sec_action_review_input(
            candidate,
            local_file=evidence_path,
            extracted_facts=ExtractedFacts(),
            operator_verified=False,
            revision_id="3" * 64,
            content_sha256="4" * 64,
        )

    unresolved = candidate.model_copy(
        update={"candidate_kinds": ("merger",), "candidate_snippets": ("merger",)}
    )
    with pytest.raises(ValueError, match="action_kind"):
        build_sec_action_review_input(
            unresolved,
            local_file=evidence_path,
            extracted_facts=ExtractedFacts(),
            operator_verified=True,
            revision_id="3" * 64,
            content_sha256="4" * 64,
        )


def test_sec_action_review_form_is_batch_fail_closed_before_manifest(
    tmp_path: Path,
) -> None:
    accession = "0001045810-24-000144"
    raw = b"declared a cash dividend"
    raw_path = tmp_path / (
        f"sec-filing-{accession}-{hashlib.sha256(raw).hexdigest()}.html"
    )
    raw_path.write_bytes(raw)
    base = {
        "symbol": "TEST",
        "accession_number": accession,
        "review_key": f"sec:{accession}:dividend",
        "source_url": "https://www.sec.gov/Archives/edgar/data/1045810/event.htm",
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
    }
    blank = SecActionReviewForm(
        items=(SecActionReviewFormItem(**base),),
    )
    reference_queue = SecReviewQueue(
        items=(
            SecReviewQueueItem(
                symbol="TEST",
                accession_number=accession,
                source_url=base["source_url"],
                raw_sha256=base["raw_sha256"],
                candidate_kinds=("dividend",),
                candidate_snippets=("declared a cash dividend",),
            ),
        )
    )
    report = validate_sec_action_review_form(
        blank, candidate_dir=tmp_path, reference_queue=reference_queue
    )
    assert report.ready is False
    assert set(report.missing_fields[blank.items[0].review_key]) == {
        "amount",
        "comparable_share_basis",
        "content_sha256",
        "currency",
        "event_type",
        "ex_dividend_date",
        "manual_classification",
        "operator_verified",
        "pit_link",
        "revision_id",
    }

    ready = SecActionReviewForm(
        items=(
            SecActionReviewFormItem(
                **base,
                operator_verified=True,
                revision_id="1" * 64,
                content_sha256="2" * 64,
                manual_classification="direct_cash_dividend",
                event_type="dividend",
                pit_link="sec:0001045810-24-000144",
                extracted_facts=ExtractedFacts(
                    amount="0.10",
                    currency="USD",
                    ex_dividend_date=datetime(2024, 6, 7, tzinfo=UTC).date(),
                    comparable_share_basis=True,
                ),
            ),
        )
    )
    ready_report = validate_sec_action_review_form(
        ready, candidate_dir=tmp_path, reference_queue=reference_queue
    )
    assert ready_report.ready is True
    assert ready_report.automatic_ledger_application is False

    expanded_queue = SecReviewQueue(
        items=reference_queue.items
        + (
            SecReviewQueueItem(
                symbol="TEST2",
                accession_number="0001045810-24-000145",
                source_url=base["source_url"],
                raw_sha256=base["raw_sha256"],
                candidate_kinds=("dividend",),
                candidate_snippets=("declared a cash dividend",),
            ),
        )
    )
    incomplete_report = validate_sec_action_review_form(
        ready, candidate_dir=tmp_path, reference_queue=expanded_queue
    )
    assert incomplete_report.ready is False
    assert incomplete_report.reference_missing_accessions == (
        "0001045810-24-000145",
    )

    tampered = SecActionReviewForm(
        items=(ready.items[0].model_copy(update={"symbol": "EVIL"}),)
    )
    tampered_report = validate_sec_action_review_form(
        tampered, candidate_dir=tmp_path, reference_queue=reference_queue
    )
    assert tampered_report.ready is False
    assert "symbol_reference" in tampered_report.missing_fields[
        tampered.items[0].review_key
    ]


def test_sec_review_queue_binds_symbols_deterministically_without_promotion() -> None:
    candidates = (
        SecFilingCandidate(
            cik="0000000002",
            accession_number="0000000002-25-000002",
            form="8-K",
            source_url="https://www.sec.gov/Archives/edgar/data/2/two.htm",
            observed_at=datetime(2026, 9, 19, 12, tzinfo=UTC),
            raw_sha256="2" * 64,
            candidate_kinds=("split",),
            candidate_snippets=("stock split",),
        ),
        SecFilingCandidate(
            cik="0000000001",
            accession_number="0000000001-25-000001",
            form="8-K",
            source_url="https://www.sec.gov/Archives/edgar/data/1/one.htm",
            observed_at=datetime(2026, 9, 19, 12, tzinfo=UTC),
            raw_sha256="1" * 64,
            candidate_kinds=("dividend",),
            candidate_snippets=("declared a dividend",),
        ),
    )

    queue = build_sec_review_queue(
        candidates, filing_symbols={"0000000001": "ONE", "0000000002": "TWO"}
    )

    assert [item.symbol for item in queue.items] == ["ONE", "TWO"]
    assert all(item.status == "unsupported_candidate" for item in queue.items)
    assert all(item.automatic_ledger_application is False for item in queue.items)
    assert queue.items[0].required_fields == (
        "manual_classification",
        "event_type",
        "effective_date",
        "amount_or_ratio",
        "share_basis",
        "pit_link",
    )


def test_sec_review_queue_rejects_unknown_symbol_and_duplicate_accession() -> None:
    candidate = SecFilingCandidate(
        cik="0000000001",
        accession_number="0000000001-25-000001",
        form="8-K",
        source_url="https://www.sec.gov/Archives/edgar/data/1/one.htm",
        observed_at=datetime(2026, 9, 19, 12, tzinfo=UTC),
        raw_sha256="1" * 64,
        candidate_kinds=("dividend",),
        candidate_snippets=("dividend",),
    )
    with pytest.raises(ValueError, match="symbol_missing"):
        build_sec_review_queue((candidate,), filing_symbols={})
    with pytest.raises(ValueError, match="duplicate_accession"):
        build_sec_review_queue(
            (candidate, candidate), filing_symbols={"0000000001": "ONE"}
        )
    with pytest.raises(ValueError, match="queue_empty"):
        build_sec_review_queue((), filing_symbols={})


def test_sec_review_queue_source_verification_is_hash_bound(tmp_path: Path) -> None:
    candidate = SecFilingCandidate(
        cik="0000000001",
        accession_number="0000000001-25-000001",
        form="8-K",
        source_url="https://www.sec.gov/Archives/edgar/data/1/one.htm",
        observed_at=datetime(2026, 9, 19, 12, tzinfo=UTC),
        raw_sha256="0" * 64,
        candidate_kinds=("dividend",),
        candidate_snippets=("dividend",),
    )
    queue = build_sec_review_queue((candidate,), filing_symbols={"0000000001": "ONE"})
    report = verify_sec_review_queue_sources(queue, candidate_dir=tmp_path)
    assert report.ready is False
    assert report.missing_accessions == (candidate.accession_number,)

    raw = b"declared a dividend"
    candidate = candidate.model_copy(
        update={"raw_sha256": hashlib.sha256(raw).hexdigest()}
    )
    queue = build_sec_review_queue((candidate,), filing_symbols={"0000000001": "ONE"})
    path = tmp_path / f"sec-filing-{candidate.accession_number}-raw.html"
    path.write_bytes(raw)
    report = verify_sec_review_queue_sources(queue, candidate_dir=tmp_path)
    assert report.ready is True
    assert report.verified_items == 1

    path.write_bytes(b"tampered")
    report = verify_sec_review_queue_sources(queue, candidate_dir=tmp_path)
    assert report.ready is False
    assert report.sha_mismatch_accessions == (candidate.accession_number,)


def test_sec_review_queue_cli_is_fail_closed(tmp_path: Path, capsys) -> None:
    raw = b"declared a dividend"
    candidate = SecFilingCandidate(
        cik="0000000001",
        accession_number="0000000001-25-000001",
        form="8-K",
        source_url="https://www.sec.gov/Archives/edgar/data/1/one.htm",
        observed_at=datetime(2026, 9, 19, 12, tzinfo=UTC),
        raw_sha256=hashlib.sha256(raw).hexdigest(),
        candidate_kinds=("dividend",),
        candidate_snippets=("dividend",),
    )
    queue = build_sec_review_queue((candidate,), filing_symbols={"0000000001": "ONE"})
    queue_path = tmp_path / "queue.json"
    queue_path.write_text(queue.model_dump_json(), encoding="utf-8")
    candidate_dir = tmp_path / "candidates"
    candidate_dir.mkdir()

    assert (
        _main(
            [
                "--verify-queue",
                str(queue_path),
                "--candidate-dir",
                str(candidate_dir),
            ]
        )
        == 2
    )
    assert json.loads(capsys.readouterr().out)["ready"] is False

    (candidate_dir / f"sec-filing-{candidate.accession_number}-raw.html").write_bytes(
        raw
    )
    assert (
        _main(
            [
                "--verify-queue",
                str(queue_path),
                "--candidate-dir",
                str(candidate_dir),
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["ready"] is True


def test_priority_reference_catalog_loads_as_subset_queue(tmp_path: Path) -> None:
    path = tmp_path / "priority.json"
    path.write_text(
        json.dumps(
            {
                "automatic_ledger_application": False,
                "operator_review_required": True,
                "schema_version": 1,
                "status": "unsupported_candidate",
                "items": [
                    {
                        "symbol": "ONE",
                        "accession_number": "0000000001-25-000001",
                        "source_url": "https://www.sec.gov/Archives/one.htm",
                        "raw_sha256": "a" * 64,
                        "candidate_kinds": ["dividend"],
                        "candidate_snippets": ["dividend"],
                        "required_fields": list(SEC_REVIEW_QUEUE_REQUIRED_FIELDS),
                        "status": "unsupported_candidate",
                        "automatic_ledger_application": False,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    queue = load_sec_review_reference_queue(path)
    assert len(queue.items) == 1
    assert queue.items[0].accession_number == "0000000001-25-000001"


def test_sec_action_review_form_cli_requires_reference_queue(
    tmp_path: Path, capsys
) -> None:
    raw = b"declared a cash dividend"
    accession = "0000000001-25-000001"
    source_url = "https://www.sec.gov/Archives/edgar/data/1/one.htm"
    candidate_dir = tmp_path / "candidates"
    candidate_dir.mkdir()
    (candidate_dir / f"sec-filing-{accession}-raw.html").write_bytes(raw)
    form = SecActionReviewForm(
        items=(
            SecActionReviewFormItem(
                symbol="ONE",
                accession_number=accession,
                review_key=f"sec:{accession}:dividend",
                source_url=source_url,
                raw_sha256=hashlib.sha256(raw).hexdigest(),
            ),
        )
    )
    form_path = tmp_path / "form.json"
    form_path.write_text(form.model_dump_json(), encoding="utf-8")
    queue = SecReviewQueue(
        items=(
            SecReviewQueueItem(
                symbol="ONE",
                accession_number=accession,
                source_url=source_url,
                raw_sha256=hashlib.sha256(raw).hexdigest(),
                candidate_kinds=("dividend",),
                candidate_snippets=("declared a cash dividend",),
            ),
        )
    )
    queue_path = tmp_path / "queue.json"
    queue_path.write_text(queue.model_dump_json(), encoding="utf-8")
    assert (
        _main(
            [
                "--validate-review-form",
                str(form_path),
                "--review-candidate-dir",
                str(candidate_dir),
                "--review-reference-queue",
                str(queue_path),
            ]
        )
        == 2
    )
    output = json.loads(capsys.readouterr().out)
    assert output["ready"] is False
    assert output["automatic_ledger_application"] is False


def test_sec_action_review_form_cli_returns_zero_for_complete_manual_review(
    tmp_path: Path, capsys
) -> None:
    raw = b"declared a cash dividend"
    accession = "0000000001-25-000001"
    source_url = "https://www.sec.gov/Archives/edgar/data/1/one.htm"
    candidate_dir = tmp_path / "candidates"
    candidate_dir.mkdir()
    (candidate_dir / f"sec-filing-{accession}-raw.html").write_bytes(raw)
    form = SecActionReviewForm(
        items=(
            SecActionReviewFormItem(
                symbol="ONE",
                accession_number=accession,
                review_key=f"sec:{accession}:dividend",
                source_url=source_url,
                raw_sha256=hashlib.sha256(raw).hexdigest(),
                operator_verified=True,
                revision_id="1" * 64,
                content_sha256="2" * 64,
                manual_classification="direct_cash_dividend",
                event_type="dividend",
                pit_link=f"sec:{accession}",
                extracted_facts=ExtractedFacts(
                    amount="0.10",
                    currency="USD",
                    ex_dividend_date=datetime(2025, 6, 7, tzinfo=UTC).date(),
                    comparable_share_basis=True,
                ),
            ),
        )
    )
    form_path = tmp_path / "form.json"
    form_path.write_text(form.model_dump_json(), encoding="utf-8")
    queue = SecReviewQueue(
        items=(
            SecReviewQueueItem(
                symbol="ONE",
                accession_number=accession,
                source_url=source_url,
                raw_sha256=hashlib.sha256(raw).hexdigest(),
                candidate_kinds=("dividend",),
                candidate_snippets=("declared a cash dividend",),
            ),
        )
    )
    queue_path = tmp_path / "queue.json"
    queue_path.write_text(queue.model_dump_json(), encoding="utf-8")

    assert (
        _main(
            [
                "--validate-review-form",
                str(form_path),
                "--review-candidate-dir",
                str(candidate_dir),
                "--review-reference-queue",
                str(queue_path),
            ]
        )
        == 0
    )
    output = json.loads(capsys.readouterr().out)
    assert output["ready"] is True
    assert output["automatic_ledger_application"] is False


def test_sec_review_manifest_requires_complete_manual_inputs(tmp_path: Path) -> None:
    evidence_body = b"declared a dividend"
    evidence_path = tmp_path / "doc.htm"
    evidence_path.write_bytes(evidence_body)
    candidate = SecFilingCandidate(
        cik="0001045810",
        accession_number="0001045810-24-000144",
        form="8-K",
        source_url="https://www.sec.gov/Archives/edgar/data/1045810/doc.htm",
        observed_at=datetime(2026, 9, 19, 12, tzinfo=UTC),
        raw_sha256=hashlib.sha256(evidence_body).hexdigest(),
        candidate_kinds=("dividend",),
        candidate_snippets=("declared a dividend",),
    )
    facts = ExtractedFacts(
        amount="0.10",
        currency="USD",
        ex_dividend_date=datetime(2024, 6, 7, tzinfo=UTC).date(),
        comparable_share_basis=True,
    )
    manifest = build_sec_review_manifest(
        (candidate,),
        local_files={candidate.accession_number: evidence_path},
        extracted_facts={candidate.accession_number: facts},
        revision_ids={candidate.accession_number: "3" * 64},
        content_hashes={candidate.accession_number: "4" * 64},
        operator_verified=True,
    )
    assert manifest.schema_version == 1
    assert len(manifest.reviews) == 1

    with pytest.raises(ValueError, match="facts_missing"):
        build_sec_review_manifest(
            (candidate,),
            local_files={},
            extracted_facts={},
            revision_ids={},
            content_hashes={},
            operator_verified=True,
        )
