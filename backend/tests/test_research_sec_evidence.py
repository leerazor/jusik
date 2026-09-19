import json
from datetime import UTC, datetime

from jusik.research_sec_evidence import parse_sec_submissions


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
