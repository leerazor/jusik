from datetime import UTC, date, datetime

import pytest

from jusik.research_sec_etf_coverage import (
    build_sec_etf_coverage_report,
    build_sec_etf_coverage_reports,
)
from jusik.research_sec_etf_identity import parse_sec_etf_identity
from jusik.research_sec_evidence import parse_sec_submissions


def _identity():
    return parse_sec_etf_identity(
        b"<div>0001424958 Direxion Daily Semiconductor Bull 3X Shares SOXL</div>",
        symbol="SOXL",
        title="Direxion Daily Semiconductor Bull 3X Shares",
        cik="0001424958",
        accession_number="0001133228-26-000012",
        source_url="https://www.sec.gov/index.htm",
        observed_at=datetime(2026, 9, 20, tzinfo=UTC),
    )


def _filings():
    return parse_sec_submissions(
        b'{"cik":"0001424958","filings":{"recent":{"form":["8-K","NPORT-P","8-K"],'
        b'"accessionNumber":["0001424958-26-000001","0001424958-26-000002",'
        b'"0001424958-25-000003"],"filingDate":["2026-09-10","2026-08-01",'
        b'"2025-09-12"],"acceptanceDateTime":["20260910120000",'
        b'"20260801120000","20250912120000"],"primaryDocument":["a.htm",'
        b'"b.htm","c.htm"]}}}',
        observed_at=datetime(2026, 9, 20, tzinfo=UTC),
        source_url="https://data.sec.gov/submissions/CIK0001424958.json",
    )


def test_coverage_report_is_inventory_only() -> None:
    report = build_sec_etf_coverage_report(
        _identity(),
        _filings(),
        start=date(2025, 9, 11),
        end=date(2026, 9, 11),
        source_raw_sha256="a" * 64,
    )
    assert report.inventory_status == "inventory_only"
    assert report.target_filing_count == 3
    assert report.forms == {"8-K": 2, "NPORT-P": 1}
    assert report.first_filing_date == date(2025, 9, 12)
    assert report.last_filing_date == date(2026, 9, 10)


def test_coverage_reports_are_sorted_and_allow_empty_inventory() -> None:
    report = build_sec_etf_coverage_reports(
        (_identity(),),
        {},
        start=date(2025, 9, 11),
        end=date(2026, 9, 11),
        source_hashes_by_cik={"0001424958": "b" * 64},
    )[0]
    assert report.target_filing_count == 0
    assert report.first_filing_date is None
    assert report.last_filing_date is None


def test_coverage_report_rejects_cik_mismatch() -> None:
    other = _identity().model_copy(update={"cik": "0001174610"})
    with pytest.raises(ValueError, match="^sec_etf_filing_cik_mismatch$"):
        build_sec_etf_coverage_report(
            other,
            _filings(),
            start=date(2025, 9, 11),
            end=date(2026, 9, 11),
            source_raw_sha256="a" * 64,
        )


@pytest.mark.parametrize(
    "start,end,message",
    [
        (date(2026, 9, 11), date(2025, 9, 11), "end_before_start"),
        (date(2025, 9, 11), date(2026, 9, 11), "source_raw_sha256_invalid"),
    ],
)
def test_coverage_report_rejects_invalid_bounds_or_hash(
    start: date, end: date, message: str
) -> None:
    source_hash = "bad" if message.endswith("invalid") else "a" * 64
    with pytest.raises(ValueError, match=f"^{message}$"):
        build_sec_etf_coverage_report(
            _identity(),
            (),
            start=start,
            end=end,
            source_raw_sha256=source_hash,
        )
