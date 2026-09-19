import json
from datetime import UTC, datetime

import pytest

from jusik.research_sec_evidence import (
    SecFiling,
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
    assert len(result.raw_sha256) == 64

    missing_document = filing.model_copy(update={"primary_document": None})
    with pytest.raises(ValueError, match="primary_document"):
        filing_document_url(missing_document)
