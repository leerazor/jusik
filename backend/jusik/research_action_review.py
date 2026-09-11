from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Annotated, Literal, Self
from urllib.parse import parse_qsl, urlsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    ValidationError,
    field_validator,
    model_validator,
)

MAX_MANIFEST_BYTES = 1024 * 1024
MAX_EVIDENCE_BYTES = 4 * 1024 * 1024
SENSITIVE_QUERY_KEYS = {
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
ComparisonStatus = Literal["matched", "partial", "mismatched"]
FieldStatus = Literal["matched", "missing", "mismatched"]


class EvidenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    local_file: Path
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_url: str = Field(min_length=9, max_length=2000)
    publisher: str = Field(min_length=1, max_length=200)
    locator: str = Field(min_length=1, max_length=500)
    captured_at: datetime

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or any(
                key.lower() in SENSITIVE_QUERY_KEYS
                for key, _value in parse_qsl(parsed.query, keep_blank_values=True)
            )
        ):
            raise ValueError("Evidence source URL must be credential-free HTTPS.")
        return value

    @field_validator("captured_at")
    @classmethod
    def captured_at_is_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Evidence capture timestamp must be timezone-aware.")
        return value.astimezone(UTC)


class ExtractedFacts(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    numerator: Annotated[StrictInt, Field(gt=0, le=10**18 - 1)] | None = None
    denominator: Annotated[StrictInt, Field(gt=0, le=10**18 - 1)] | None = None
    adjusted_trading_date: date | None = None
    amount: str | None = Field(default=None, max_length=128)
    currency: Literal["KRW", "USD"] | None = None
    comparable_share_basis: bool | None = None
    ex_dividend_date: date | None = None
    record_date: date | None = None
    payment_date: date | None = None
    legal_effective_date: date | None = None

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            amount = Decimal(value)
        except InvalidOperation:
            raise ValueError("Evidence amount must be a decimal string.") from None
        if not amount.is_finite() or amount <= 0 or len(amount.as_tuple().digits) > 64:
            raise ValueError("Evidence amount must be a bounded positive decimal.")
        exponent = amount.as_tuple().exponent
        if not isinstance(exponent, int) or abs(exponent) > 64:
            raise ValueError("Evidence amount exponent is out of range.")
        return format(amount, "f")


class ReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    review_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
    revision_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    operator_verified: Literal[True]
    evidence: EvidenceInput
    extracted_facts: ExtractedFacts


class ReviewManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1]
    reviews: list[ReviewInput] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique_review_keys(self) -> Self:
        keys = [item.review_key for item in self.reviews]
        if len(keys) != len(set(keys)):
            raise ValueError("Review keys must be unique within a manifest.")
        return self


class ComparedField(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    field: str
    source_value: str | None
    evidence_value: str | None
    status: FieldStatus


class PublicEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-f0-9]{64}$")
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_url: str
    publisher: str
    locator: str
    captured_at: datetime


class ActionReview(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-f0-9]{64}$")
    review_key: str
    revision_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    event_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    sequence: int = Field(gt=0)
    symbol: str
    kind: Literal["split", "dividend"]
    source_content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_payload: dict[str, object]
    extracted_facts: ExtractedFacts
    comparison_status: ComparisonStatus
    compared_fields: list[ComparedField]
    evidence: PublicEvidence
    reviewed_at: datetime
    imported_at: datetime
    current_revision: bool
    needs_review: bool
    automatic_ledger_application: Literal[False] = False


class ActionReviewPage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    items: list[ActionReview]
    next_cursor: str | None
    reviewed_revision_count: int = Field(ge=0)
    current_revision_count: int = Field(ge=0)
    unreviewed_current_revision_count: int = Field(ge=0)


class RawReviewEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-f0-9]{64}$")
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    body: bytes


def _field(name: str, source: object | None, evidence: object | None) -> ComparedField:
    source_text = None if source is None else str(source)
    evidence_text = None if evidence is None else str(evidence)
    if evidence is None:
        status: FieldStatus = "missing"
    elif source_text == evidence_text:
        status = "matched"
    else:
        status = "mismatched"
    return ComparedField(
        field=name,
        source_value=source_text,
        evidence_value=evidence_text,
        status=status,
    )


def compare_review(
    kind: Literal["split", "dividend"],
    source_payload: dict[str, object],
    facts: ExtractedFacts,
) -> tuple[ComparisonStatus, list[ComparedField]]:
    if kind == "split":
        if any(
            value is not None
            for value in (
                facts.amount,
                facts.currency,
                facts.comparable_share_basis,
                facts.ex_dividend_date,
                facts.record_date,
                facts.payment_date,
            )
        ):
            raise ValueError("Dividend facts cannot be attached to a split revision.")
        source_numerator = source_payload.get("numerator")
        source_denominator = source_payload.get("denominator")
        evidence_numerator = facts.numerator
        evidence_denominator = facts.denominator
        ratio_status: FieldStatus
        evidence_ratio = (
            None
            if evidence_numerator is None or evidence_denominator is None
            else f"{evidence_numerator}/{evidence_denominator}"
        )
        source_ratio = (
            None
            if source_numerator is None or source_denominator is None
            else f"{source_numerator}/{source_denominator}"
        )
        if evidence_numerator is None or evidence_denominator is None:
            ratio_status = "missing"
        elif (
            isinstance(source_numerator, bool)
            or not isinstance(source_numerator, int)
            or isinstance(source_denominator, bool)
            or not isinstance(source_denominator, int)
        ):
            ratio_status = "mismatched"
        elif source_numerator * evidence_denominator == (
            evidence_numerator * source_denominator
        ):
            ratio_status = "matched"
        else:
            ratio_status = "mismatched"
        fields = [
            ComparedField(
                field="split_ratio",
                source_value=source_ratio,
                evidence_value=evidence_ratio,
                status=ratio_status,
            ),
            _field(
                "adjusted_trading_date",
                source_payload.get("vendor_date"),
                facts.adjusted_trading_date,
            ),
        ]
    else:
        if any(
            value is not None
            for value in (
                facts.numerator,
                facts.denominator,
                facts.adjusted_trading_date,
                facts.legal_effective_date,
            )
        ):
            raise ValueError("Split facts cannot be attached to a dividend revision.")
        share_basis = ComparedField(
            field="comparable_share_basis",
            source_value=None,
            evidence_value=(
                None
                if facts.comparable_share_basis is None
                else str(facts.comparable_share_basis).lower()
            ),
            status=(
                "missing"
                if facts.comparable_share_basis is None
                else "matched"
                if facts.comparable_share_basis
                else "mismatched"
            ),
        )
        amount_field = _field("amount", source_payload.get("amount"), facts.amount)
        if source_payload.get("amount") is not None and facts.amount is not None:
            try:
                amounts_equal = Decimal(str(source_payload["amount"])) == Decimal(
                    facts.amount
                )
            except InvalidOperation:
                amounts_equal = False
            amount_field = amount_field.model_copy(
                update={"status": "matched" if amounts_equal else "mismatched"}
            )
        fields = [
            amount_field,
            _field("currency", source_payload.get("currency"), facts.currency),
            _field(
                "ex_dividend_date",
                source_payload.get("vendor_date"),
                facts.ex_dividend_date,
            ),
            share_basis,
        ]
    if any(item.status == "mismatched" for item in fields):
        return "mismatched", fields
    if any(item.status == "missing" for item in fields):
        return "partial", fields
    return "matched", fields


def load_manifest(path: Path) -> ReviewManifest:
    if path.stat().st_size > MAX_MANIFEST_BYTES:
        raise ValueError("Review manifest is too large.")
    with path.open("rb") as source:
        body = source.read(MAX_MANIFEST_BYTES + 1)
    if len(body) > MAX_MANIFEST_BYTES:
        raise ValueError("Review manifest is too large.")

    def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Review manifest contains a duplicate key.")
            result[key] = value
        return result

    payload = json.loads(body, object_pairs_hook=unique_object, parse_float=Decimal)
    return ReviewManifest.model_validate(payload)


def main() -> int:
    parser = argparse.ArgumentParser(description="Import official action reviews")
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    try:
        from jusik.research_action_review_store import ActionReviewStore

        result = ActionReviewStore(args.db).import_manifest(
            load_manifest(args.manifest), datetime.now(UTC)
        )
    except (OSError, sqlite3.Error, ValidationError, ValueError):
        print("action review import failed", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
