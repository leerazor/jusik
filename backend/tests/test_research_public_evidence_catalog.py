import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from jusik.research_alpha_actions import parse_alpha_actions
from jusik.research_public_evidence import parse_nasdaq_halt_rss
from jusik.research_public_evidence_catalog import (
    PublicEvidenceItem,
    build_public_evidence_catalog,
    build_public_evidence_symbol_coverage,
    public_evidence_catalog_sha256,
    verify_public_evidence_catalog,
    write_symbol_coverage,
)
from jusik.research_sec_evidence import parse_sec_submissions


def test_catalog_joins_sources_deduplicates_and_stays_incomplete() -> None:
    observed = datetime(2026, 9, 20, 1, tzinfo=UTC)
    halt = parse_nasdaq_halt_rss(
        b"<rss><channel><item><title>Security NVDA halted on 01/02/2024</title>"
        b"<description>Reason code T1</description></item></channel></rss>",
        halt_date=date(2024, 1, 2),
        source_url="https://www.nasdaqtrader.com/rss.aspx?feed=tradehalts",
        observed_at=observed,
    )
    actions = parse_alpha_actions(
        b'{"data":[{"ex_dividend_date":"2024-06-11","payment_date":"2024-06-28","amount":"0.01"}]}',
        symbol="NVDA",
        kind="dividend",
        start=date(2024, 1, 1),
        end=date(2024, 12, 31),
        source_url="https://www.alphavantage.co/query",
        observed_at=observed,
    )
    filing = parse_sec_submissions(
        b'{"cik":"0001045810","filings":{"recent":{"form":["8-K"],'
        b'"accessionNumber":["0001045810-24-000144"],"filingDate":["2024-06-07"],'
        b'"acceptanceDateTime":["20240607153000"],"primaryDocument":["event.htm"]}}}',
        observed_at=observed,
        source_url="https://data.sec.gov/submissions/CIK0001045810.json",
    )

    catalog = build_public_evidence_catalog(
        symbols=("NVDA", "SOXL"),
        start=date(2024, 1, 1),
        end=date(2024, 12, 31),
        halts=halt * 2,
        filings=filing,
        actions=actions,
        filing_symbols={"0001045810": "NVDA"},
        unresolved_symbols=("SOXL",),
    )

    assert catalog.coverage == "incomplete"
    assert catalog.unresolved_symbols == ("SOXL",)
    assert catalog.source_counts == {
        "alpha_vantage": 1,
        "nasdaq_trader": 1,
        "sec_edgar": 1,
    }
    sec_refs = {
        item.instrument_ref for item in catalog.items if item.source == "sec_edgar"
    }
    assert sec_refs == {"NVDA"}
    assert catalog.observed_item_count == 3
    assert len(catalog.catalog_sha256) == 64

    report = build_public_evidence_symbol_coverage(catalog)
    assert report.catalog_sha256 == catalog.catalog_sha256
    assert report.requested_start == date(2024, 1, 1)
    assert report.requested_end == date(2024, 12, 31)
    assert report.coverage == "incomplete"
    assert report.economic_acceptance is False
    assert report.pit_proof is False
    assert report.symbols["NVDA"].missing_sources == ()
    assert report.symbols["SOXL"].missing_sources == (
        "alpha_vantage",
        "nasdaq_trader",
        "sec_edgar",
    )


def test_symbol_coverage_rejects_out_of_universe_items() -> None:
    catalog = build_public_evidence_catalog(
        symbols=("NVDA",),
        start=date(2024, 1, 1),
        end=date(2024, 12, 31),
    )
    item = catalog.model_copy(
        update={
            "items": (
                PublicEvidenceItem(
                    source="sec_edgar",
                    instrument_ref="OTHER",
                    event_kind="8-K",
                    event_date=date(2024, 1, 2),
                    observed_at=datetime(2026, 9, 20, 1, tzinfo=UTC),
                    source_url="https://example.invalid/source",
                    raw_sha256="a" * 64,
                ),
            )
        }
    )
    item = item.model_copy(
        update={
            "observed_item_count": 1,
            "source_counts": {"sec_edgar": 1},
        }
    )
    item = item.model_copy(
        update={"catalog_sha256": public_evidence_catalog_sha256(item)}
    )
    with pytest.raises(ValueError, match="catalog_item_symbol_not_requested"):
        build_public_evidence_symbol_coverage(item)


def test_catalog_integrity_rejects_tampering_before_coverage() -> None:
    catalog = build_public_evidence_catalog(
        symbols=("NVDA",), start=date(2024, 1, 1), end=date(2024, 12, 31)
    )
    tampered = catalog.model_copy(update={"observed_item_count": 1})
    with pytest.raises(ValueError, match="catalog_sha_mismatch"):
        verify_public_evidence_catalog(tampered)
    with pytest.raises(ValueError, match="catalog_sha_mismatch"):
        build_public_evidence_symbol_coverage(tampered)


def test_symbol_coverage_preserves_empty_and_unresolved_sources() -> None:
    catalog = build_public_evidence_catalog(
        symbols=("NVDA", "SOXL"),
        start=date(2024, 1, 1),
        end=date(2024, 12, 31),
        unresolved_symbols=("SOXL",),
    )
    report = build_public_evidence_symbol_coverage(catalog)
    assert report.requested_symbols == ("NVDA", "SOXL")
    assert report.unresolved_symbols == ("SOXL",)
    assert report.symbols["NVDA"].source_counts == {
        "alpha_vantage": 0,
        "nasdaq_trader": 0,
        "sec_edgar": 0,
    }
    assert report.symbols["SOXL"].missing_sources == (
        "alpha_vantage",
        "nasdaq_trader",
        "sec_edgar",
    )


def test_symbol_coverage_writer_is_deterministic(tmp_path: Path) -> None:
    catalog = build_public_evidence_catalog(
        symbols=("NVDA",), start=date(2024, 1, 1), end=date(2024, 12, 31)
    )
    report = build_public_evidence_symbol_coverage(catalog)
    path = tmp_path / "coverage.json"
    write_symbol_coverage(report, path)
    assert json.loads(path.read_text(encoding="utf-8")) == report.model_dump(
        mode="json"
    )


def test_catalog_rejects_nasdaq_halt_outside_requested_symbols() -> None:
    observed = datetime(2026, 9, 20, 1, tzinfo=UTC)
    halt = parse_nasdaq_halt_rss(
        b"<rss><channel><item><title>Security OTHER halted on 01/02/2024</title>"
        b"<description>Reason code T1</description></item></channel></rss>",
        halt_date=date(2024, 1, 2),
        source_url="https://www.nasdaqtrader.com/rss.aspx?feed=tradehalts",
        observed_at=observed,
    )

    with pytest.raises(ValueError, match="^evidence_symbol_not_requested$"):
        build_public_evidence_catalog(
            symbols=("NVDA",),
            start=date(2024, 1, 1),
            end=date(2024, 12, 31),
            halts=halt,
        )


def test_catalog_rejects_outside_nasdaq_symbol_before_date_filter() -> None:
    observed = datetime(2026, 9, 20, 1, tzinfo=UTC)
    halt = parse_nasdaq_halt_rss(
        b"<rss><channel><item><title>Security OTHER halted on 01/02/2023</title>"
        b"<description>Reason code T1</description></item></channel></rss>",
        halt_date=date(2023, 1, 2),
        source_url="https://www.nasdaqtrader.com/rss.aspx?feed=tradehalts",
        observed_at=observed,
    )

    with pytest.raises(ValueError, match="^evidence_symbol_not_requested$"):
        build_public_evidence_catalog(
            symbols=("NVDA",),
            start=date(2024, 1, 1),
            end=date(2024, 12, 31),
            halts=halt,
        )


def test_catalog_rejects_alpha_action_outside_requested_symbols() -> None:
    observed = datetime(2026, 9, 20, 1, tzinfo=UTC)
    actions = parse_alpha_actions(
        b'{"data":[{"ex_dividend_date":"2024-06-11",'
        b'"payment_date":"2024-06-28","amount":"0.01"}]}',
        symbol="OTHER",
        kind="dividend",
        start=date(2024, 1, 1),
        end=date(2024, 12, 31),
        source_url="https://www.alphavantage.co/query",
        observed_at=observed,
    )

    with pytest.raises(ValueError, match="^evidence_symbol_not_requested$"):
        build_public_evidence_catalog(
            symbols=("NVDA",),
            start=date(2024, 1, 1),
            end=date(2024, 12, 31),
            actions=actions,
        )


def test_catalog_rejects_outside_alpha_symbol_before_date_filter() -> None:
    observed = datetime(2026, 9, 20, 1, tzinfo=UTC)
    actions = parse_alpha_actions(
        b'{"data":[{"ex_dividend_date":"2023-06-11",'
        b'"payment_date":"2023-06-28","amount":"0.01"}]}',
        symbol="OTHER",
        kind="dividend",
        start=date(2023, 1, 1),
        end=date(2023, 12, 31),
        source_url="https://www.alphavantage.co/query",
        observed_at=observed,
    )

    with pytest.raises(ValueError, match="^evidence_symbol_not_requested$"):
        build_public_evidence_catalog(
            symbols=("NVDA",),
            start=date(2024, 1, 1),
            end=date(2024, 12, 31),
            actions=actions,
        )


def test_catalog_rejects_sec_filing_mapped_outside_requested_symbols() -> None:
    observed = datetime(2026, 9, 20, 1, tzinfo=UTC)
    filing = parse_sec_submissions(
        b'{"cik":"0001045810","filings":{"recent":{"form":["8-K"],'
        b'"accessionNumber":["0001045810-24-000144"],"filingDate":["2024-06-07"],'
        b'"acceptanceDateTime":["20240607153000"],"primaryDocument":["event.htm"]}}}',
        observed_at=observed,
        source_url="https://data.sec.gov/submissions/CIK0001045810.json",
    )

    with pytest.raises(ValueError, match="^evidence_symbol_not_requested$"):
        build_public_evidence_catalog(
            symbols=("NVDA",),
            start=date(2024, 1, 1),
            end=date(2024, 12, 31),
            filings=filing,
            filing_symbols={"0001045810": "OTHER"},
        )


def test_catalog_rejects_outside_sec_symbol_before_date_filter() -> None:
    observed = datetime(2026, 9, 20, 1, tzinfo=UTC)
    filing = parse_sec_submissions(
        b'{"cik":"0001045810","filings":{"recent":{"form":["8-K"],'
        b'"accessionNumber":["0001045810-23-000144"],"filingDate":["2023-06-07"],'
        b'"acceptanceDateTime":["20230607153000"],"primaryDocument":["event.htm"]}}}',
        observed_at=observed,
        source_url="https://data.sec.gov/submissions/CIK0001045810.json",
    )

    with pytest.raises(ValueError, match="^evidence_symbol_not_requested$"):
        build_public_evidence_catalog(
            symbols=("NVDA",),
            start=date(2024, 1, 1),
            end=date(2024, 12, 31),
            filings=filing,
            filing_symbols={"0001045810": "OTHER"},
        )
