import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from jusik.research_action_review import ExtractedFacts
from jusik.research_sec_evidence import (
    SecFiling,
    SecFilingCandidate,
    build_sec_action_review_input,
    build_sec_review_manifest,
    collect_sec_filing_candidates,
    filing_document_url,
    parse_sec_filing_candidate,
    parse_sec_submissions,
    parse_sec_ticker_map,
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
    candidate = SecFilingCandidate(
        cik="0001045810",
        accession_number="0001045810-24-000144",
        form="8-K",
        source_url="https://www.sec.gov/Archives/edgar/data/1045810/doc.htm",
        observed_at=datetime(2026, 9, 19, 12, tzinfo=UTC),
        raw_sha256="1" * 64,
        candidate_kinds=("dividend",),
        candidate_snippets=("declared a dividend",),
    )
    review = build_sec_action_review_input(
        candidate,
        local_file=tmp_path / "doc.htm",
        extracted_facts=ExtractedFacts(
            amount="0.10",
            currency="USD",
            ex_dividend_date=datetime(2024, 6, 7, tzinfo=UTC).date(),
            comparable_share_basis=True,
        ),
        operator_verified=True,
    )
    assert review.operator_verified is True
    assert review.review_key.endswith(":dividend")

    with pytest.raises(ValueError, match="operator_verification"):
        build_sec_action_review_input(
            candidate,
            local_file=tmp_path / "doc.htm",
            extracted_facts=ExtractedFacts(),
            operator_verified=False,
        )

    unresolved = candidate.model_copy(
        update={"candidate_kinds": ("merger",), "candidate_snippets": ("merger",)}
    )
    with pytest.raises(ValueError, match="action_kind"):
        build_sec_action_review_input(
            unresolved,
            local_file=tmp_path / "doc.htm",
            extracted_facts=ExtractedFacts(),
            operator_verified=True,
        )


def test_sec_review_manifest_requires_complete_manual_inputs(tmp_path: Path) -> None:
    candidate = SecFilingCandidate(
        cik="0001045810",
        accession_number="0001045810-24-000144",
        form="8-K",
        source_url="https://www.sec.gov/Archives/edgar/data/1045810/doc.htm",
        observed_at=datetime(2026, 9, 19, 12, tzinfo=UTC),
        raw_sha256="2" * 64,
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
        local_files={candidate.accession_number: tmp_path / "doc.htm"},
        extracted_facts={candidate.accession_number: facts},
        operator_verified=True,
    )
    assert manifest.schema_version == 1
    assert len(manifest.reviews) == 1

    with pytest.raises(ValueError, match="facts_missing"):
        build_sec_review_manifest(
            (candidate,),
            local_files={},
            extracted_facts={},
            operator_verified=True,
        )
