from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Callable
from contextlib import closing
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_CANDIDATE_ROWS = 10_000
MAX_ARCHIVE_BYTES = 8 * 1024 * 1024
POLICY_VERSION: Literal["usdkrw_provenance_v2"] = "usdkrw_provenance_v2"
UnavailableReason = Literal[
    "database_unavailable",
    "candidate_limit",
    "candidate_malformed",
    "no_candidate",
    "selected_value_invalid",
    "selected_stale",
    "archive_missing",
    "archive_malformed",
    "archive_oversize",
    "archive_source_mismatch",
    "archive_capture_mismatch",
    "archive_after_cutoff",
    "archive_identity_mismatch",
]


def _utc(value: datetime, field: str) -> datetime:
    if value.tzinfo is None:
        raise ValueError(f"{field} must be timezone-aware")
    return value.astimezone(UTC)


class FxObservationProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    series: Literal["usdkrw"] = "usdkrw"
    value: Decimal = Field(gt=0, allow_inf_nan=False)
    observed_on: date
    available_at: datetime
    revision: str = Field(min_length=1, max_length=80)
    source: str = Field(min_length=1, max_length=200)
    raw_archive_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    captured_at: datetime

    @field_validator("available_at", "captured_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        return _utc(value, "observation timestamp")


class FxArchiveProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-f0-9]{64}$")
    source: str = Field(min_length=1, max_length=200)
    captured_at: datetime
    content_type: str = Field(min_length=1, max_length=200)
    body_bytes: int = Field(ge=0, le=MAX_ARCHIVE_BYTES)
    body_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    @field_validator("captured_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        return _utc(value, "archive timestamp")


class FxProvenanceResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[2] = 2
    policy_version: Literal["usdkrw_provenance_v2"] = POLICY_VERSION
    currency: Literal["KRW", "USD"]
    cutoff_at: datetime
    read_started_at: datetime
    read_finished_at: datetime
    state: Literal["resolved", "identity_conversion", "unavailable"]
    reason: UnavailableReason | None = None
    rate_krw_per_unit: Decimal | None = Field(default=None, gt=0, allow_inf_nan=False)
    age_days: int | None = Field(default=None, ge=0)
    candidate_count: int = Field(ge=0, le=MAX_CANDIDATE_ROWS)
    observation: FxObservationProvenance | None = None
    archive: FxArchiveProvenance | None = None
    linked_to_execution: Literal[False] = False
    accepted_nav: Literal[False] = False
    historical_point_in_time_proven: Literal[False] = False
    limitations: list[str]

    @field_validator("cutoff_at", "read_started_at", "read_finished_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        return _utc(value, "resolver timestamp")


class _Unavailable(Exception):
    def __init__(self, reason: UnavailableReason, candidate_count: int = 0) -> None:
        super().__init__(reason)
        self.reason = reason
        self.candidate_count = candidate_count


class _Selected(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    value_text: str = Field(min_length=1, max_length=128)
    observed_on: date
    available_at: datetime
    revision: str = Field(min_length=1, max_length=80)
    source: str = Field(min_length=1, max_length=200)
    raw_archive_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    captured_at: datetime

    @field_validator("available_at", "captured_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        return _utc(value, "selected observation timestamp")


def _parse_candidate(row: sqlite3.Row) -> _Selected:
    values = {
        key: row[key]
        for key in (
            "value_text",
            "observed_on",
            "available_at",
            "revision",
            "source",
            "raw_archive_id",
            "captured_at",
        )
    }
    if any(value is None for value in values.values()):
        raise _Unavailable("candidate_malformed")
    try:
        return _Selected.model_validate(values)
    except (TypeError, ValueError) as exc:
        raise _Unavailable("candidate_malformed") from exc


def _candidate_rows(
    connection: sqlite3.Connection, cutoff: datetime
) -> tuple[_Selected, int]:
    total = int(
        connection.execute(
            "SELECT count(*) FROM external_observations WHERE series='usdkrw'"
        ).fetchone()[0]
    )
    if total > MAX_CANDIDATE_ROWS:
        raise _Unavailable("candidate_limit", MAX_CANDIDATE_ROWS)
    rows = connection.execute(
        """SELECT
        CASE WHEN length(CAST(value AS BLOB))<=128 THEN value END AS value_text,
        CASE WHEN length(CAST(observed_on AS BLOB))<=32 THEN observed_on END
            AS observed_on,
        CASE WHEN length(CAST(available_at AS BLOB))<=64 THEN available_at END
            AS available_at,
        CASE WHEN length(CAST(revision AS BLOB))<=80 THEN revision END AS revision,
        CASE WHEN length(CAST(source AS BLOB))<=200 THEN source END AS source,
        CASE WHEN length(CAST(raw_archive_id AS BLOB))=64 THEN raw_archive_id END
            AS raw_archive_id,
        CASE WHEN length(CAST(captured_at AS BLOB))<=64 THEN captured_at END
            AS captured_at
        FROM external_observations WHERE series='usdkrw' LIMIT ?""",
        (MAX_CANDIDATE_ROWS,),
    ).fetchall()
    try:
        parsed = [_parse_candidate(row) for row in rows]
    except _Unavailable as exc:
        raise _Unavailable(exc.reason, total) from exc
    eligible = [
        item
        for item in parsed
        if item.observed_on <= cutoff.date()
        and item.available_at <= cutoff
        and item.captured_at <= cutoff
    ]
    if not eligible:
        raise _Unavailable("no_candidate", total)
    eligible.sort(key=lambda item: item.revision)
    eligible.sort(key=lambda item: item.available_at, reverse=True)
    eligible.sort(key=lambda item: item.observed_on, reverse=True)
    selected = eligible[0]
    return selected, total


def _archive(
    connection: sqlite3.Connection,
    selected: _Selected,
    cutoff: datetime,
) -> FxArchiveProvenance:
    descriptor = connection.execute(
        """SELECT
        CASE WHEN length(CAST(id AS BLOB))=64 THEN id END AS id,
        CASE WHEN length(CAST(source AS BLOB))<=200 THEN source END AS source,
        CASE WHEN length(CAST(captured_at AS BLOB))<=64 THEN captured_at END
            AS captured_at,
        CASE WHEN length(CAST(content_type AS BLOB))<=200 THEN content_type END
            AS content_type,
        CASE WHEN typeof(body)='blob' THEN length(CAST(body AS BLOB)) END
            AS body_bytes
        FROM external_raw_archives WHERE id=?""",
        (selected.raw_archive_id,),
    ).fetchone()
    if descriptor is None:
        raise _Unavailable("archive_missing")
    if any(
        descriptor[key] is None
        for key in ("id", "source", "captured_at", "content_type", "body_bytes")
    ):
        raise _Unavailable("archive_malformed")
    body_bytes = int(descriptor["body_bytes"])
    if body_bytes > MAX_ARCHIVE_BYTES:
        raise _Unavailable("archive_oversize")
    try:
        archive_captured_at = _utc(
            datetime.fromisoformat(str(descriptor["captured_at"])),
            "archive captured_at",
        )
    except ValueError as exc:
        raise _Unavailable("archive_malformed") from exc
    source = str(descriptor["source"])
    if source != selected.source:
        raise _Unavailable("archive_source_mismatch")
    if archive_captured_at > selected.captured_at:
        raise _Unavailable("archive_capture_mismatch")
    if archive_captured_at > cutoff:
        raise _Unavailable("archive_after_cutoff")
    body_row = connection.execute(
        "SELECT body FROM external_raw_archives WHERE id=?", (selected.raw_archive_id,)
    ).fetchone()
    if body_row is None or not isinstance(body_row["body"], bytes):
        raise _Unavailable("archive_malformed")
    body = body_row["body"]
    body_sha256 = hashlib.sha256(body).hexdigest()
    expected_id = hashlib.sha256(source.encode() + b"\0" + body).hexdigest()
    if expected_id != selected.raw_archive_id or descriptor["id"] != expected_id:
        raise _Unavailable("archive_identity_mismatch")
    try:
        return FxArchiveProvenance(
            id=expected_id,
            source=source,
            captured_at=archive_captured_at,
            content_type=descriptor["content_type"],
            body_bytes=len(body),
            body_sha256=body_sha256,
        )
    except ValueError as exc:
        raise _Unavailable("archive_malformed") from exc


class FxProvenanceResolver:
    def __init__(
        self,
        database: Path,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.database = database
        self._clock = clock

    def resolve(self, currency: str, cutoff_at: datetime) -> FxProvenanceResult:
        if currency not in {"KRW", "USD"}:
            raise ValueError("currency must be KRW or USD")
        cutoff = _utc(cutoff_at, "cutoff_at")
        read_started = _utc(self._clock(), "read_started_at")
        if currency == "KRW":
            return FxProvenanceResult(
                currency="KRW",
                cutoff_at=cutoff,
                read_started_at=read_started,
                read_finished_at=_utc(self._clock(), "read_finished_at"),
                state="identity_conversion",
                rate_krw_per_unit=Decimal(1),
                candidate_count=0,
                limitations=_limitations(),
            )
        candidate_count = 0
        try:
            uri = self.database.resolve().as_uri() + "?mode=ro"
            with closing(sqlite3.connect(uri, uri=True, timeout=0.1)) as connection:
                connection.row_factory = sqlite3.Row
                connection.execute("BEGIN")
                selected, candidate_count = _candidate_rows(connection, cutoff)
                try:
                    value = Decimal(selected.value_text)
                except InvalidOperation as exc:
                    raise _Unavailable(
                        "selected_value_invalid", candidate_count
                    ) from exc
                if not value.is_finite() or value <= 0:
                    raise _Unavailable("selected_value_invalid", candidate_count)
                age_days = (cutoff.date() - selected.observed_on).days
                if age_days > 7:
                    raise _Unavailable("selected_stale", candidate_count)
                archive = _archive(connection, selected, cutoff)
                observation = FxObservationProvenance(
                    value=value,
                    observed_on=selected.observed_on,
                    available_at=selected.available_at,
                    revision=selected.revision,
                    source=selected.source,
                    raw_archive_id=selected.raw_archive_id,
                    captured_at=selected.captured_at,
                )
        except (OSError, sqlite3.Error):
            reason: UnavailableReason = "database_unavailable"
        except _Unavailable as exc:
            reason = exc.reason
            candidate_count = exc.candidate_count or candidate_count
        else:
            return FxProvenanceResult(
                currency="USD",
                cutoff_at=cutoff,
                read_started_at=read_started,
                read_finished_at=_utc(self._clock(), "read_finished_at"),
                state="resolved",
                rate_krw_per_unit=observation.value,
                age_days=age_days,
                candidate_count=candidate_count,
                observation=observation,
                archive=archive,
                limitations=_limitations(),
            )
        return FxProvenanceResult(
            currency="USD",
            cutoff_at=cutoff,
            read_started_at=read_started,
            read_finished_at=_utc(self._clock(), "read_finished_at"),
            state="unavailable",
            reason=reason,
            candidate_count=min(candidate_count, MAX_CANDIDATE_ROWS),
            limitations=_limitations(),
        )


def resolve_fx_provenance(
    database: Path,
    currency: str,
    cutoff_at: datetime,
    *,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> FxProvenanceResult:
    return FxProvenanceResolver(database, clock=clock).resolve(currency, cutoff_at)


def _limitations() -> list[str]:
    return [
        "cutoff UTC 날짜와 observed_on을 비교하는 v2 정책이며 기존 생산자 선택을 "
        "변경하지 않습니다.",
        "선택한 환율과 원문 archive의 연결을 확인하지만 과거 시점 진위를 증명하지 "
        "않습니다.",
        "현재 체결·NAV와 연결하지 않으며 linked_to_execution과 accepted_nav는 "
        "false입니다.",
        "read_started_at과 read_finished_at은 읽기 구간이며 원장 commit 시각이 "
        "아닙니다.",
    ]
