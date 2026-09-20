"""Fail-closed parser for SEC ETF series/class identity evidence."""

from __future__ import annotations

import hashlib
import html
import re
from datetime import UTC, datetime
from urllib.parse import parse_qsl, urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_BYTES = 2 * 1024 * 1024
_CIK_RE = re.compile(r"^\d{10}$")
_ACCESSION_RE = re.compile(r"^\d{10}-\d{2}-\d{6}$")
_TAG_RE = re.compile(r"<[^>]+>")
_SENSITIVE_QUERY_KEYS = {
    "access_token",
    "api_key",
    "apikey",
    "auth",
    "authorization",
    "credential",
    "key",
    "secret",
    "sig",
    "signature",
    "token",
}


class SecEtfIdentity(BaseModel):
    """Identity proven by one bounded SEC filing index response."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: str = Field(pattern=r"^[A-Z][A-Z0-9.]{0,19}$")
    title: str = Field(min_length=1, max_length=300)
    cik: str = Field(pattern=r"^\d{10}$")
    accession_number: str = Field(pattern=r"^\d{10}-\d{2}-\d{6}$")
    source_url: str = Field(min_length=1, max_length=500)
    observed_at: datetime
    raw_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("source_url")
    @classmethod
    def source_url_is_credential_free_https(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or any(
                key.lower() in _SENSITIVE_QUERY_KEYS
                for key, _ in parse_qsl(parsed.query, keep_blank_values=True)
            )
        ):
            raise ValueError("source_url_must_be_credential_free_https")
        return value

    @field_validator("observed_at")
    @classmethod
    def observed_at_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("observed_at_must_be_timezone_aware")
        return value.astimezone(UTC)


def parse_sec_etf_identity(
    body: bytes,
    *,
    symbol: str,
    title: str,
    cik: str,
    accession_number: str,
    source_url: str,
    observed_at: datetime,
) -> SecEtfIdentity:
    """Require the supplied identity fields to be present in one SEC index body."""
    if len(body) > MAX_BYTES:
        raise ValueError("sec_etf_identity_input_too_large")
    try:
        text = body.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError("sec_etf_identity_invalid_utf8") from exc
    if not _CIK_RE.fullmatch(cik):
        raise ValueError("sec_etf_identity_cik_invalid")
    if not _ACCESSION_RE.fullmatch(accession_number):
        raise ValueError("sec_etf_identity_accession_invalid")
    normalized = " ".join(_TAG_RE.sub(" ", html.unescape(text)).split())
    if symbol not in normalized:
        raise ValueError("sec_etf_identity_symbol_missing")
    if title not in normalized:
        raise ValueError("sec_etf_identity_title_missing")
    if cik not in normalized:
        raise ValueError("sec_etf_identity_cik_missing")
    return SecEtfIdentity(
        symbol=symbol,
        title=title,
        cik=cik,
        accession_number=accession_number,
        source_url=source_url,
        observed_at=observed_at,
        raw_sha256=hashlib.sha256(body).hexdigest(),
    )


__all__ = ["SecEtfIdentity", "parse_sec_etf_identity"]
