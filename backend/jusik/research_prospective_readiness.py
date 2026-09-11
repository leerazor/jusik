from __future__ import annotations

import hashlib
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from jusik.research_forward_models import ForwardConfig, ForwardFill
from jusik.research_prospective_registration import ProspectiveRegistrationStatus
from jusik.research_quote_models import ResearchQuote

MAX_FILL_INSPECTION = 5_000


def _aware_utc(value: str | datetime, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
    except ValueError as exc:
        raise ValueError(f"{field} timestamp is invalid") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} timestamp must be timezone-aware")
    return parsed.astimezone(UTC)


def _normalized_utc(value: str) -> str:
    return _aware_utc(value, "database").isoformat(timespec="microseconds")


class ProspectiveBoundaryReadiness(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    boundary: Literal["start", "end"]
    boundary_at: datetime
    state: Literal["not_due", "missing", "unverified_candidate"]
    candidate_checkpoint_at: datetime | None = None
    candidate_actually_known_at: datetime | None = None

    @field_validator(
        "boundary_at", "candidate_checkpoint_at", "candidate_actually_known_at"
    )
    @classmethod
    def normalize_timestamp(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _aware_utc(value, "boundary")


class ProspectiveExecutionEvidenceReadiness(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    state: Literal["unobserved", "linked_integrity", "incomplete"]
    window_timestamp: Literal["fill_received_at"] = "fill_received_at"
    total_fill_count: int = Field(ge=0)
    inspected_fill_count: int = Field(ge=0, le=MAX_FILL_INSPECTION)
    uninspected_fill_count: int = Field(ge=0)
    captured_count: int = Field(ge=0)
    missing_count: int = Field(ge=0)
    mismatch_count: int = Field(ge=0)
    truncated: bool


class ProspectiveReadiness(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    checked_at: datetime
    registration_status: Literal["planned", "observing", "window_elapsed"]
    session_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    evaluation_start_at: datetime
    evaluation_end_at: datetime
    collector_implemented: Literal[False] = False
    start_boundary: ProspectiveBoundaryReadiness
    end_boundary: ProspectiveBoundaryReadiness
    execution_evidence: ProspectiveExecutionEvidenceReadiness
    evaluation_inputs_complete: Literal[False] = False
    limitations: list[str]

    @field_validator("checked_at", "evaluation_start_at", "evaluation_end_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        normalized = _aware_utc(value, "readiness")
        return normalized


def _validate_registration(
    connection: sqlite3.Connection, status: ProspectiveRegistrationStatus
) -> tuple[str, datetime, datetime]:
    registration = status.registration
    if (
        status.status not in {"planned", "observing", "window_elapsed"}
        or registration is None
        or status.reason is not None
        or status.current_session_id != registration.session_id
    ):
        raise ValueError("prospective registration identity is unavailable")
    rows = connection.execute(
        """SELECT id, source_run_id, policy_hash, config_json
        FROM forward_sessions WHERE active=1"""
    ).fetchall()
    if len(rows) != 1:
        raise ValueError("active PAPER session identity is unavailable")
    row = rows[0]
    try:
        config = ForwardConfig.model_validate_json(row["config_json"])
    except ValueError as exc:
        raise ValueError("active PAPER session config is invalid") from exc
    if (
        row["id"] != registration.session_id
        or row["source_run_id"] != registration.source_run_id
        or row["policy_hash"] != registration.policy_hash
        or config != registration.config
    ):
        raise ValueError("active PAPER session identity changed")
    return (
        registration.session_id,
        _aware_utc(registration.evaluation_start_at, "evaluation start"),
        _aware_utc(registration.evaluation_end_at, "evaluation end"),
    )


def _boundary_readiness(
    connection: sqlite3.Connection,
    *,
    session_id: str,
    boundary: Literal["start", "end"],
    boundary_at: datetime,
    checked_at: datetime,
) -> ProspectiveBoundaryReadiness:
    if checked_at < boundary_at:
        return ProspectiveBoundaryReadiness(
            boundary=boundary, boundary_at=boundary_at, state="not_due"
        )
    normalized = boundary_at.isoformat(timespec="microseconds")
    rows = connection.execute(
        """SELECT checkpoint_at, actually_known_at
        FROM forward_checkpoints
        WHERE session_id=? AND normalize_utc(checkpoint_at)=?
        LIMIT 2""",
        (session_id, normalized),
    ).fetchall()
    if not rows:
        return ProspectiveBoundaryReadiness(
            boundary=boundary, boundary_at=boundary_at, state="missing"
        )
    if len(rows) != 1:
        raise ValueError("normalized boundary checkpoint is ambiguous")
    checkpoint_at = _aware_utc(rows[0]["checkpoint_at"], "checkpoint")
    actually_known_at = _aware_utc(rows[0]["actually_known_at"], "actually known")
    if actually_known_at < checkpoint_at or actually_known_at > checked_at:
        raise ValueError("boundary checkpoint knowledge timestamp is invalid")
    return ProspectiveBoundaryReadiness(
        boundary=boundary,
        boundary_at=boundary_at,
        state="unverified_candidate",
        candidate_checkpoint_at=checkpoint_at,
        candidate_actually_known_at=actually_known_at,
    )


def _fill_matches_sidecar(
    row: sqlite3.Row,
) -> Literal["captured", "missing", "mismatch"]:
    if row["quote_json"] is None or row["quote_sha256"] is None:
        return "missing"
    try:
        fill = ForwardFill.model_validate_json(row["payload_json"])
        quote_raw = str(row["quote_json"])
        if hashlib.sha256(quote_raw.encode()).hexdigest() != row["quote_sha256"]:
            return "mismatch"
        quote = ResearchQuote.model_validate_json(quote_raw)
        fill_market_at = _aware_utc(fill.market_at, "fill market")
        fill_received_at = _aware_utc(fill.received_at, "fill received")
        quote_market_at = _aware_utc(quote.market_at, "quote market")
        quote_received_at = _aware_utc(quote.received_at, "quote received")
    except (TypeError, ValueError):
        return "mismatch"
    if (
        fill.id != row["id"]
        or fill.session_id != row["session_id"]
        or fill.symbol != row["symbol"]
        or fill_market_at != _aware_utc(row["market_at"], "stored fill market")
        or fill_received_at != _aware_utc(row["received_at"], "stored fill received")
        or quote.symbol != fill.symbol
        or quote_market_at != fill_market_at
        or quote_received_at != fill_received_at
    ):
        return "mismatch"
    return "captured"


def _execution_readiness(
    connection: sqlite3.Connection,
    *,
    session_id: str,
    start_at: datetime,
    end_at: datetime,
) -> ProspectiveExecutionEvidenceReadiness:
    start = start_at.isoformat(timespec="microseconds")
    end = end_at.isoformat(timespec="microseconds")
    where = (
        "f.session_id=? AND normalize_utc(f.received_at)>=? "
        "AND normalize_utc(f.received_at)<?"
    )
    total = int(
        connection.execute(
            f"SELECT count(*) FROM forward_fills f WHERE {where}",
            (session_id, start, end),
        ).fetchone()[0]
    )
    rows = connection.execute(
        f"""SELECT f.id, f.session_id, f.symbol, f.market_at, f.received_at,
        f.payload_json, q.quote_json, q.quote_sha256
        FROM forward_fills f
        LEFT JOIN forward_execution_quotes q ON q.fill_id=f.id
        WHERE {where}
        ORDER BY normalize_utc(f.received_at), f.id
        LIMIT ?""",
        (session_id, start, end, MAX_FILL_INSPECTION),
    ).fetchall()
    captured = missing = mismatch = 0
    for row in rows:
        evidence = _fill_matches_sidecar(row)
        if evidence == "captured":
            captured += 1
        elif evidence == "missing":
            missing += 1
        else:
            mismatch += 1
    inspected = len(rows)
    truncated = total > inspected
    if total == 0:
        state: Literal["unobserved", "linked_integrity", "incomplete"] = "unobserved"
    elif truncated or missing or mismatch:
        state = "incomplete"
    else:
        state = "linked_integrity"
    return ProspectiveExecutionEvidenceReadiness(
        state=state,
        total_fill_count=total,
        inspected_fill_count=inspected,
        uninspected_fill_count=total - inspected,
        captured_count=captured,
        missing_count=missing,
        mismatch_count=mismatch,
        truncated=truncated,
    )


def prospective_readiness(
    *,
    forward_db: Path,
    registration_status: ProspectiveRegistrationStatus,
    now: datetime | None = None,
) -> ProspectiveReadiness:
    checked_at = _aware_utc(now or datetime.now(UTC), "readiness check")
    with sqlite3.connect(
        f"file:{forward_db}?mode=ro", uri=True, timeout=0.1
    ) as connection:
        connection.row_factory = sqlite3.Row
        connection.create_function(
            "normalize_utc", 1, _normalized_utc, deterministic=True
        )
        connection.execute("BEGIN")
        session_id, start_at, end_at = _validate_registration(
            connection, registration_status
        )
        start_boundary = _boundary_readiness(
            connection,
            session_id=session_id,
            boundary="start",
            boundary_at=start_at,
            checked_at=checked_at,
        )
        end_boundary = _boundary_readiness(
            connection,
            session_id=session_id,
            boundary="end",
            boundary_at=end_at,
            checked_at=checked_at,
        )
        execution = _execution_readiness(
            connection,
            session_id=session_id,
            start_at=start_at,
            end_at=end_at,
        )
    return ProspectiveReadiness(
        checked_at=checked_at,
        registration_status=registration_status.status,
        session_id=session_id,
        evaluation_start_at=start_at,
        evaluation_end_at=end_at,
        start_boundary=start_boundary,
        end_boundary=end_boundary,
        execution_evidence=execution,
        limitations=[
            (
                "경계 checkpoint 수집기는 구현되지 않았으며 exact timestamp 후보도 "
                "검증 완료 NAV가 아닙니다."
            ),
            (
                "체결 sidecar 무결성은 가격·통화·슬리피지 또는 재무 계산의 "
                "정확성을 증명하지 않습니다."
            ),
            (
                "체결이 0건인 상태는 관측 근거가 없다는 뜻이며 증거 완전성을 "
                "통과한 상태가 아닙니다."
            ),
        ],
    )
