from datetime import UTC, datetime

import pytest

from jusik.research_sec_etf_identity import parse_sec_etf_identity

BODY = b"""
<html><body>
  <div>CIK <a>0001424958</a></div>
  <div>Direxion Daily Semiconductor Bull 3X Shares SOXL</div>
</body></html>
"""


def _parse(body: bytes = BODY):
    return parse_sec_etf_identity(
        body,
        symbol="SOXL",
        title="Direxion Daily Semiconductor Bull 3X Shares",
        cik="0001424958",
        accession_number="0001133228-26-000012",
        source_url="https://www.sec.gov/Archives/edgar/data/1424958/index.htm",
        observed_at=datetime(2026, 9, 20, tzinfo=UTC),
    )


def test_parse_sec_etf_identity_pins_identity_and_raw_hash() -> None:
    result = _parse()
    assert result.symbol == "SOXL"
    assert result.cik == "0001424958"
    assert len(result.raw_sha256) == 64
    assert result.observed_at.tzinfo == UTC


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (BODY.replace(b"SOXL", b"OTHER"), "sec_etf_identity_symbol_missing"),
        (BODY.replace(b"0001424958", b"0000000000"), "sec_etf_identity_cik_missing"),
        (BODY.replace(b"Direxion", b"Unknown"), "sec_etf_identity_title_missing"),
    ],
)
def test_parse_sec_etf_identity_fails_closed(body: bytes, message: str) -> None:
    with pytest.raises(ValueError, match=f"^{message}$"):
        _parse(body)


def test_parse_sec_etf_identity_rejects_credentials_in_url() -> None:
    with pytest.raises(ValueError, match="source_url_must_be_credential_free_https"):
        parse_sec_etf_identity(
            BODY,
            symbol="SOXL",
            title="Direxion Daily Semiconductor Bull 3X Shares",
            cik="0001424958",
            accession_number="0001133228-26-000012",
            source_url="https://user:secret@www.sec.gov/index.htm",
            observed_at=datetime(2026, 9, 20, tzinfo=UTC),
        )
