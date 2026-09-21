import hashlib
import json
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from jusik.research_eodhd_evidence import (
    EodhdRequest,
    bind_sec_reference,
    parse_eodhd_response,
)

RETRIEVED = datetime(2026, 9, 21, 6, 40, tzinfo=UTC)
REQUEST = EodhdRequest(
    symbol="BMRC",
    endpoint="div",
    start=date(2025, 1, 1),
    end=date(2026, 9, 11),
)


def encoded(value: object) -> bytes:
    return json.dumps(value, separators=(",", ":")).encode()


def test_dividend_preserves_dates_decimal_values_and_wire_hash() -> None:
    body = encoded(
        [
            {
                "date": "2025-02-06",
                "declarationDate": "2025-01-27",
                "recordDate": "2025-02-06",
                "paymentDate": "2025-02-13",
                "period": "Quarterly",
                "value": "0.25",
                "unadjustedValue": "0.25",
                "currency": "USD",
            }
        ]
    )
    result = parse_eodhd_response(body, REQUEST, RETRIEVED)

    event = result.dividends[0]
    assert event.ex_date == date(2025, 2, 6)
    assert event.declaration_date == date(2025, 1, 27)
    assert event.record_date == date(2025, 2, 6)
    assert event.payment_date == date(2025, 2, 13)
    assert event.value == Decimal("0.25")
    assert event.unadjusted_value == Decimal("0.25")
    assert result.raw_sha256 == hashlib.sha256(body).hexdigest()
    assert result.retrieved_at == RETRIEVED
    assert result.missing_fields == ()
    assert result.automatic_ledger_application is False
    assert result.pit_evaluation == "not-evaluated"
    assert result.coverage == "not-evaluated"
    assert result.economic_evaluation == "not-evaluated"


def test_nullable_auxiliary_dates_block_with_exact_wire_names() -> None:
    body = encoded(
        [
            {
                "date": "2025-02-06",
                "declarationDate": None,
                "recordDate": "2025-02-06",
                "paymentDate": None,
                "value": 0.25,
                "unadjustedValue": 0.25,
                "currency": "USD",
            }
        ]
    )
    result = parse_eodhd_response(body, REQUEST, RETRIEVED)

    assert result.evidence_status == "blocked"
    assert result.blocked is True
    assert result.missing_fields == ("declarationDate", "paymentDate")
    assert result.dividends[0].missing_fields == (
        "declarationDate",
        "paymentDate",
    )


def test_empty_response_keeps_all_evaluation_gates_closed() -> None:
    result = parse_eodhd_response(b"[]", REQUEST, RETRIEVED)

    assert result.dividends == ()
    assert result.splits == ()
    assert result.evidence_status == "complete"
    assert result.pit_evaluation == "not-evaluated"
    assert result.coverage == "not-evaluated"
    assert result.economic_evaluation == "not-evaluated"
    assert result.automatic_ledger_application is False


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (
            [
                {
                    "value": "0.25",
                    "unadjustedValue": "0.25",
                    "currency": "USD",
                }
            ],
            "date_invalid",
        ),
        (
            [
                {
                    "date": "2025-02-06",
                    "value": "0.25",
                    "unadjustedValue": "0.25",
                    "currency": "USD",
                    "unexpected": True,
                }
            ],
            "dividend_schema_invalid",
        ),
        (
            [
                {
                    "date": "2025-02-06",
                    "value": "0.25",
                    "unadjustedValue": "0.25",
                    "currency": "USD",
                },
                {
                    "date": "2025-02-06",
                    "value": "0.26",
                    "unadjustedValue": "0.26",
                    "currency": "USD",
                },
            ],
            "eodhd_duplicate_event",
        ),
        (
            [
                {
                    "date": "2024-12-31",
                    "value": "0.25",
                    "unadjustedValue": "0.25",
                    "currency": "USD",
                }
            ],
            "eodhd_row_out_of_period",
        ),
        (
            [
                {
                    "date": "2025-02-06",
                    "value": "0",
                    "unadjustedValue": "0.25",
                    "currency": "USD",
                }
            ],
            "value_invalid",
        ),
    ],
)
def test_invalid_dividend_batches_reject_whole_response(
    payload: object, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        parse_eodhd_response(encoded(payload), REQUEST, RETRIEVED)


def test_split_decimal_ratio_is_exact_and_has_no_legal_effective_time() -> None:
    request = REQUEST.model_copy(update={"endpoint": "splits"})
    with pytest.raises(ValueError, match="retrieved_at_must_be_timezone_aware"):
        parse_eodhd_response(
            encoded([{"date": "2026-03-30", "split": "1.000000/15.000000"}]),
            request,
            RETRIEVED.replace(tzinfo=None),
        )
    result = parse_eodhd_response(
        encoded([{"date": "2026-03-30", "split": "1.000000/15.000000"}]),
        request,
        datetime(2026, 9, 21, 15, 40, tzinfo=timezone(timedelta(hours=9))),
    )

    assert result.retrieved_at == RETRIEVED
    assert result.splits[0].numerator == 1
    assert result.splits[0].denominator == 15
    assert not hasattr(result.splits[0], "legal_effective_at")


def test_request_is_frozen_extra_forbid_and_us_only() -> None:
    with pytest.raises(ValidationError):
        EodhdRequest(
            symbol="BMRC",
            endpoint="div",
            start=date(2025, 1, 1),
            end=date(2026, 9, 11),
            unexpected=True,
        )
    with pytest.raises(ValidationError):
        EodhdRequest(
            symbol="bmrc",
            endpoint="div",
            start=date(2025, 1, 1),
            end=date(2026, 9, 11),
        )


def _sec_inputs() -> tuple[bytes, bytes, str]:
    submissions = encoded(
        {
            "cik": "1403475",
            "filings": {
                "recent": {
                    "form": ["8-K"],
                    "accessionNumber": ["0001403475-25-000068"],
                    "filingDate": ["2025-10-27"],
                    "acceptanceDateTime": ["20251027125325"],
                    "primaryDocument": ["bmrc.htm"],
                }
            },
        }
    )
    filing = b"<html><body>Board dividend declaration</body></html>"
    return submissions, filing, hashlib.sha256(filing).hexdigest()


def test_sec_binding_requires_explicit_existing_event_and_preserves_identity() -> None:
    submissions, filing, filing_sha = _sec_inputs()
    submissions_sha = hashlib.sha256(submissions).hexdigest()
    event = parse_eodhd_response(
        encoded(
            [
                {
                    "date": "2025-02-06",
                    "declarationDate": "2025-01-27",
                    "recordDate": "2025-02-06",
                    "paymentDate": "2025-02-13",
                    "period": "Quarterly",
                    "value": "0.25",
                    "unadjustedValue": "0.25",
                    "currency": "USD",
                }
            ]
        ),
        REQUEST,
        RETRIEVED,
    )
    bound = bind_sec_reference(
        event,
        filing_body=filing,
        submissions_body=submissions,
        expected_raw_sha256=filing_sha,
        expected_submissions_sha256=submissions_sha,
        expected_accession_number="0001403475-25-000068",
        expected_cik="0001403475",
        event_key=event.dividends[0].event_key,
        retrieved_at=datetime(2026, 9, 20, 3, 20, tzinfo=UTC),
        submissions_retrieved_at=datetime(2026, 9, 20, 3, 20, 1, tzinfo=UTC),
        submissions_source_url="https://data.sec.gov/submissions/CIK0001403475.json",
        filing_source_url="https://www.sec.gov/Archives/edgar/data/1403475/000140347525000068/bmrc.htm",
    )

    assert bound.sec_reference is not None
    assert bound.sec_reference.raw_sha256 == filing_sha
    assert (
        bound.sec_reference.submissions_sha256
        == hashlib.sha256(submissions).hexdigest()
    )
    assert bound.sec_reference.submissions_retrieved_at == datetime(
        2026, 9, 20, 3, 20, 1, tzinfo=UTC
    )
    assert bound.sec_reference.accepted_at == datetime(
        2025, 10, 27, 16, 53, 25, tzinfo=UTC
    )
    assert bound.dividends[0].value == Decimal("0.25")


def test_sec_binding_rejects_hash_event_and_future_acceptance() -> None:
    submissions, filing, filing_sha = _sec_inputs()
    submissions_sha = hashlib.sha256(submissions).hexdigest()
    event = parse_eodhd_response(
        encoded(
            [
                {
                    "date": "2025-02-06",
                    "declarationDate": "2025-01-27",
                    "recordDate": "2025-02-06",
                    "paymentDate": "2025-02-13",
                    "period": "Quarterly",
                    "value": "0.25",
                    "unadjustedValue": "0.25",
                    "currency": "USD",
                }
            ]
        ),
        REQUEST,
        RETRIEVED,
    )
    with pytest.raises(ValueError, match="sec_event_key_not_found"):
        bind_sec_reference(
            event,
            filing_body=filing,
            submissions_body=submissions,
            expected_raw_sha256=filing_sha,
            expected_submissions_sha256=submissions_sha,
            expected_accession_number="0001403475-25-000068",
            expected_cik="0001403475",
            event_key="BMRC:div:2025-02-07",
            retrieved_at=RETRIEVED,
            submissions_retrieved_at=RETRIEVED,
            submissions_source_url="https://data.sec.gov/submissions/CIK0001403475.json",
            filing_source_url="https://www.sec.gov/Archives/edgar/data/1403475/000140347525000068/bmrc.htm",
        )

    with pytest.raises(ValueError, match="sec_raw_sha256_mismatch"):
        bind_sec_reference(
            event,
            filing_body=filing,
            submissions_body=submissions,
            expected_raw_sha256="0" * 64,
            expected_submissions_sha256=submissions_sha,
            expected_accession_number="0001403475-25-000068",
            expected_cik="0001403475",
            event_key=event.dividends[0].event_key,
            retrieved_at=RETRIEVED,
            submissions_retrieved_at=RETRIEVED,
            submissions_source_url="https://data.sec.gov/submissions/CIK0001403475.json",
            filing_source_url="https://www.sec.gov/Archives/edgar/data/1403475/000140347525000068/bmrc.htm",
        )

    with pytest.raises(ValueError, match="sec_accepted_after_observed"):
        bind_sec_reference(
            event,
            filing_body=filing,
            submissions_body=submissions,
            expected_raw_sha256=filing_sha,
            expected_submissions_sha256=submissions_sha,
            expected_accession_number="0001403475-25-000068",
            expected_cik="0001403475",
            event_key=event.dividends[0].event_key,
            retrieved_at=RETRIEVED,
            submissions_retrieved_at=datetime(2025, 1, 1, tzinfo=UTC),
            submissions_source_url="https://data.sec.gov/submissions/CIK0001403475.json",
            filing_source_url="https://www.sec.gov/Archives/edgar/data/1403475/000140347525000068/bmrc.htm",
        )


def test_sec_binding_rejects_raw_duplicate_accession_before_legacy_parser() -> None:
    submissions, filing, filing_sha = _sec_inputs()
    payload = json.loads(submissions)
    recent = payload["filings"]["recent"]
    recent["form"].append(None)
    recent["accessionNumber"].append("0001403475-25-000068")
    recent["filingDate"].append("2025-10-27")
    duplicate_submissions = encoded(payload)
    event = parse_eodhd_response(
        encoded(
            [
                {
                    "date": "2025-02-06",
                    "declarationDate": "2025-01-27",
                    "recordDate": "2025-02-06",
                    "paymentDate": "2025-02-13",
                    "period": "Quarterly",
                    "value": "0.25",
                    "unadjustedValue": "0.25",
                    "currency": "USD",
                }
            ]
        ),
        REQUEST,
        RETRIEVED,
    )

    with pytest.raises(ValueError, match="sec_accession_not_unique"):
        bind_sec_reference(
            event,
            filing_body=filing,
            submissions_body=duplicate_submissions,
            expected_raw_sha256=filing_sha,
            expected_submissions_sha256=hashlib.sha256(
                duplicate_submissions
            ).hexdigest(),
            expected_accession_number="0001403475-25-000068",
            expected_cik="0001403475",
            event_key=event.dividends[0].event_key,
            retrieved_at=RETRIEVED,
            submissions_retrieved_at=RETRIEVED,
            submissions_source_url="https://data.sec.gov/submissions/CIK0001403475.json",
            filing_source_url="https://www.sec.gov/Archives/edgar/data/1403475/000140347525000068/bmrc.htm",
        )
