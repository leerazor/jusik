from datetime import UTC, date, datetime

import pytest

from jusik.research_alpha_actions import parse_alpha_actions
from jusik.research_public_evidence import parse_nasdaq_halt_rss
from jusik.research_public_evidence_catalog import build_public_evidence_catalog
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
