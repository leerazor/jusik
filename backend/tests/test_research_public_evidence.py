from datetime import UTC, date, datetime

from jusik.research_public_evidence import (
    nasdaq_halt_url,
    parse_nasdaq_halt_rss,
)


def test_parse_nasdaq_halt_rss_preserves_raw_identity_and_observation_time() -> None:
    body = b"""<?xml version='1.0'?><rss><channel><item>
      <title>Security DIVX halted on 10/08/2010</title>
      <description>Reason code T1; halt code T1</description>
    </item></channel></rss>"""

    result = parse_nasdaq_halt_rss(
        body,
        halt_date=date(2010, 10, 8),
        source_url=nasdaq_halt_url(halt_date=date(2010, 10, 8)),
        observed_at=datetime(2026, 9, 19, 12, tzinfo=UTC),
    )

    assert len(result) == 1
    assert result[0].symbol == "DIVX"
    assert result[0].halt_date == date(2010, 10, 8)
    assert result[0].reason_code == "T1"
    assert result[0].observed_at == datetime(2026, 9, 19, 12, tzinfo=UTC)
    assert len(result[0].raw_sha256) == 64


def test_nasdaq_halt_url_supports_resumption_filter() -> None:
    assert nasdaq_halt_url(
        halt_date=date(2010, 10, 8), resumedate=date(2010, 10, 11)
    ) == (
        "https://www.nasdaqtrader.com/rss.aspx?feed=tradehalts&"
        "haltdate=10082010&resumedate=10112010"
    )
