from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ActionKind = Literal["split", "dividend"]
SourceState = Literal["never", "pending", "success", "error", "interrupted"]
CollectorState = Literal["idle", "running", "locked", "error"]


class CollectedActionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    vendor_date: date
    numerator: int | None = Field(default=None, gt=0)
    denominator: int | None = Field(default=None, gt=0)
    amount: str | None = None
    currency: Literal["KRW", "USD"] | None = None


class CollectedAction(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider_key: str = Field(min_length=1, max_length=200)
    kind: ActionKind
    payload: CollectedActionPayload


class ActionRevision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-f0-9]{64}$")
    event_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    provider: Literal["Yahoo chart"] = "Yahoo chart"
    symbol: str
    kind: ActionKind
    provider_key: str
    sequence: int = Field(gt=0)
    content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    first_seen_at: datetime
    attempt_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    payload: CollectedActionPayload

    @field_validator("first_seen_at")
    @classmethod
    def timestamp_is_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Action revision timestamp must be timezone-aware.")
        return value


class ActionEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-f0-9]{64}$")
    provider: Literal["Yahoo chart"] = "Yahoo chart"
    symbol: str
    kind: ActionKind
    provider_key: str
    vendor_date: date
    first_seen_at: datetime
    last_seen_at: datetime
    observation_state: Literal["observed", "not_seen_in_latest_response"]
    latest_revision_sequence: int = Field(gt=0)
    latest_revision: ActionRevision

    @field_validator("first_seen_at", "last_seen_at")
    @classmethod
    def timestamp_is_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Action event timestamp must be timezone-aware.")
        return value


class ActionSourceStatus(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: str
    yahoo_symbol: str
    state: SourceState
    last_attempt_at: datetime | None = None
    last_success_at: datetime | None = None
    next_due_at: datetime
    stale: bool
    error_code: str | None = None
    requested_start: date | None = None
    requested_end: date | None = None
    latest_attempt_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    latest_attempt_raw_available: bool = False
    event_count: int = Field(default=0, ge=0)

    @field_validator("last_attempt_at", "last_success_at", "next_due_at")
    @classmethod
    def timestamp_is_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("Action source timestamp must be timezone-aware.")
        return value


class ActionCollectionStatus(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: Literal["Yahoo chart"] = "Yahoo chart"
    provider_url: Literal["https://query1.finance.yahoo.com"] = (
        "https://query1.finance.yahoo.com"
    )
    collector_state: CollectorState
    error_code: str | None = None
    generated_at: datetime
    sources: list[ActionSourceStatus]
    automatic_ledger_application: Literal[False] = False
    payout_and_tax_known: Literal[False] = False
    official_publication_time_known: Literal[False] = False

    @field_validator("generated_at")
    @classmethod
    def generated_at_is_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Collection status timestamp must be timezone-aware.")
        return value


class ActionEventPage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    items: list[ActionEvent]
    next_cursor: str | None


class ActionRevisionPage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    items: list[ActionRevision]
    next_cursor: str | None


class RawActionAttempt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-f0-9]{64}$")
    symbol: str
    requested_start: date
    requested_end: date
    completed_at: datetime
    http_status: int = Field(ge=100, le=599)
    body_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    body: bytes

    @field_validator("completed_at")
    @classmethod
    def completed_at_is_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Raw attempt timestamp must be timezone-aware.")
        return value
