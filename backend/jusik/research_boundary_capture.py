from __future__ import annotations

import asyncio
import fcntl
import hashlib
import json
import os
import sqlite3
import time
import uuid
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from jusik.research_forward_models import (
    ForwardConfig,
    ForwardDecision,
    ForwardFill,
    ForwardIntent,
    ForwardPosition,
    ForwardSession,
)
from jusik.research_portfolio_models import PortfolioInput
from jusik.research_prospective_registration import (
    EVALUATION_END_AT,
    EVALUATION_START_AT,
    ProspectiveRegistration,
    ProspectiveRegistrationStatus,
)
from jusik.research_quote_models import ResearchQuote

CAPTURE_INTERVAL_SECONDS = 5
MAX_TABLE_ROWS = 5_000
MAX_INPUT_ROWS = 100
MAX_ROW_BYTES = 256 * 1024
MAX_INPUT_BYTES = 16 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024
MAX_CAPTURE_BODY_BYTES = 56 * 1024 * 1024
MAX_ARTIFACT_BYTES = MAX_TOTAL_BYTES
MAX_ISSUES = 100
MAX_ISSUE_REFERENCES = 20
DEFAULT_BOUNDARY_CAPTURE_DIR = (
    Path.home() / ".local/share/jusik/research-prospective-captures"
)
BoundaryName = Literal["start", "end"]
BOUNDARIES: tuple[tuple[BoundaryName, datetime], ...] = (
    ("start", EVALUATION_START_AT),
    ("end", EVALUATION_END_AT),
)
CaptureState = Literal[
    "scheduled", "collecting", "captured_raw", "captured_with_issues", "error"
]
CaptureErrorCode = Literal[
    "lock_busy",
    "identity_unavailable",
    "collector_identity_changed",
    "database_unavailable",
    "artifact_invalid",
    "capture_failed",
]


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _aware_utc(value: str | datetime, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
    except ValueError as exc:
        raise ValueError(f"{field} timestamp is invalid") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} timestamp must be timezone-aware")
    return parsed.astimezone(UTC)


def collector_code_sha256(path: Path | None = None) -> str:
    source = path or Path(__file__)
    if source.is_symlink() or not source.is_file():
        raise ValueError("collector source is unavailable")
    body = source.read_bytes()
    if len(body) > MAX_ROW_BYTES:
        raise ValueError("collector source exceeds the size limit")
    return _sha(body)


class BoundaryCaptureIssue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: Literal[
        "row_limit",
        "row_oversize",
        "total_budget",
        "invalid_payload",
        "missing_reference",
        "observation_limit",
    ]
    table: str = Field(min_length=1, max_length=64)
    count: int = Field(gt=0)
    references: list[str] = Field(default_factory=list, max_length=MAX_ISSUE_REFERENCES)


class BoundaryCaptureCount(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    table: str
    total_count: int = Field(ge=0)
    included_count: int = Field(ge=0)
    omitted_count: int = Field(ge=0)

    @model_validator(mode="after")
    def reconciles(self) -> Self:
        if self.included_count + self.omitted_count != self.total_count:
            raise ValueError("capture table counts do not reconcile")
        return self


class BoundaryExecutionQuote(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    fill_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    quote: ResearchQuote
    quote_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    captured_at: datetime

    @field_validator("captured_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        return _aware_utc(value, "execution quote capture")


class BoundaryRiskInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    checkpoint_at: datetime
    actually_known_at: datetime
    equity_krw: Decimal = Field(ge=0, allow_inf_nan=False)
    positions_asof: dict[str, Decimal]
    stock_snapshot_ids: dict[str, str]

    @field_validator("checkpoint_at", "actually_known_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        return _aware_utc(value, "risk input")


class BoundaryInputVersion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-f0-9]{64}$")
    cutoff_at: datetime
    recorded_at: datetime
    payload_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    payload_kind: Literal["portfolio", "risk_checkpoint"]
    payload: PortfolioInput | BoundaryRiskInput

    @field_validator("cutoff_at", "recorded_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        return _aware_utc(value, "input version")


class BoundaryCorporateAction(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    symbol: str
    exchange: str
    numerator: int
    denominator: int
    factor: int
    source_url: str
    evidence_id: str
    evidence_sha256: str
    operator_verified: bool
    observed_at: datetime
    effective_at: datetime
    registered_at: datetime

    @field_validator("observed_at", "effective_at", "registered_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        return _aware_utc(value, "corporate action")


class BoundaryCorporateApplication(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    action_id: str
    applied_at: datetime
    before_quantity: int = Field(ge=0)
    after_quantity: int = Field(ge=0)
    before_average_cost_krw: Decimal = Field(ge=0, allow_inf_nan=False)
    after_average_cost_krw: Decimal = Field(ge=0, allow_inf_nan=False)

    @field_validator("applied_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        return _aware_utc(value, "corporate action application")


class BoundaryCheckpoint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    checkpoint_at: datetime
    actually_known_at: datetime
    equity_krw: Decimal = Field(ge=0, allow_inf_nan=False)
    cash_krw: Decimal = Field(ge=0, allow_inf_nan=False)
    positions: dict[str, Decimal]

    @field_validator("checkpoint_at", "actually_known_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        return _aware_utc(value, "checkpoint")


class BoundaryLatestObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    persisted_reason: str
    quote: ResearchQuote
    scope: Literal["latest_at_read_time"] = "latest_at_read_time"


class BoundaryRawSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    session: ForwardSession
    positions: list[ForwardPosition]
    decisions: list[ForwardDecision]
    fills: list[ForwardFill]
    execution_quotes: list[BoundaryExecutionQuote]
    input_versions: list[BoundaryInputVersion]
    corporate_actions: list[BoundaryCorporateAction]
    corporate_action_applications: list[BoundaryCorporateApplication]
    checkpoints: list[BoundaryCheckpoint]
    latest_observations: list[BoundaryLatestObservation]


class BoundaryCaptureArtifactContent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    session_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    boundary: BoundaryName
    boundary_at: datetime
    read_started_at: datetime
    read_finished_at: datetime
    monotonic_duration_seconds: Decimal = Field(ge=0, allow_inf_nan=False)
    capture_lag_seconds: Decimal = Field(ge=0, allow_inf_nan=False)
    contract_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    policy_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_run_id: str
    collector_startup_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    collector_capture_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    raw_observed_at_capture: Literal[True] = True
    boundary_asof_reconstructed: Literal[False] = False
    accepted_nav: Literal[False] = False
    evaluation_inputs_complete: Literal[False] = False
    snapshot: BoundaryRawSnapshot
    counts: list[BoundaryCaptureCount]
    issues: list[BoundaryCaptureIssue] = Field(max_length=MAX_ISSUES)

    @field_validator("boundary_at", "read_started_at", "read_finished_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        return _aware_utc(value, "capture")

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.read_started_at < self.boundary_at:
            raise ValueError("capture started before its boundary")
        if self.read_finished_at < self.read_started_at:
            raise ValueError("capture wall clock moved backwards")
        if self.collector_startup_sha256 != self.collector_capture_sha256:
            raise ValueError("collector source identity changed")
        return self


class BoundaryCaptureArtifact(BoundaryCaptureArtifactContent):
    artifact_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def valid_hash(self) -> Self:
        payload = self.model_dump(mode="json", exclude={"artifact_sha256"})
        if _sha(_canonical(payload).encode()) != self.artifact_sha256:
            raise ValueError("boundary capture hash is invalid")
        return self


class BoundaryCaptureItemStatus(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    boundary: BoundaryName
    boundary_at: datetime
    state: CaptureState
    artifact_sha256: str | None = None
    read_started_at: datetime | None = None
    read_finished_at: datetime | None = None
    capture_lag_seconds: Decimal | None = Field(default=None, ge=0)
    issue_count: int = Field(ge=0)
    download_available: bool
    error_code: CaptureErrorCode | None = None

    @field_validator("boundary_at", "read_started_at", "read_finished_at")
    @classmethod
    def aware(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _aware_utc(value, "capture status")


class BoundaryCaptureStatus(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    checked_at: datetime
    session_id: str | None
    collector_implemented: Literal[True] = True
    running: bool
    last_poll_at: datetime | None
    collector_startup_sha256: str
    collector_current_sha256: str | None
    boundaries: list[BoundaryCaptureItemStatus] = Field(min_length=2, max_length=2)
    limitations: list[str]

    @field_validator("checked_at", "last_poll_at")
    @classmethod
    def aware(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _aware_utc(value, "capture status")


class _Budget:
    def __init__(self) -> None:
        self.consumed = 0

    def reserve(self, amount: int) -> bool:
        if amount < 0 or self.consumed + amount > MAX_CAPTURE_BODY_BYTES:
            return False
        self.consumed += amount
        return True


class _CaptureBuilder:
    def __init__(self, connection: sqlite3.Connection, session_id: str) -> None:
        self.connection = connection
        self.session_id = session_id
        self.budget = _Budget()
        self.counts: list[BoundaryCaptureCount] = []
        self.issues: list[BoundaryCaptureIssue] = []

    def issue(
        self,
        code: str,
        table: str,
        references: Sequence[str],
        *,
        count: int | None = None,
    ) -> None:
        if len(self.issues) >= MAX_ISSUES:
            return
        self.issues.append(
            BoundaryCaptureIssue(
                code=code,
                table=table,
                count=count if count is not None else len(references),
                references=list(references[:MAX_ISSUE_REFERENCES]),
            )
        )

    def rows[T: BaseModel](
        self,
        *,
        table: str,
        descriptor_sql: str,
        descriptor_params: tuple[object, ...],
        fetch_sql: str,
        fetch_params: Callable[[str], tuple[object, ...]],
        parser: Callable[[sqlite3.Row], T],
        limit: int = MAX_TABLE_ROWS,
        per_row: int = MAX_ROW_BYTES,
        total: int | None = None,
    ) -> list[T]:
        if total is None:
            total = int(
                self.connection.execute(
                    f"SELECT count(*) FROM ({descriptor_sql})", descriptor_params
                ).fetchone()[0]
            )
        descriptors = self.connection.execute(
            f"""SELECT CASE
            WHEN length(CAST(capture_key AS BLOB)) <= 256 THEN capture_key
            ELSE NULL END AS capture_key, capture_bytes
            FROM ({descriptor_sql}) LIMIT ?""",
            (*descriptor_params, limit),
        ).fetchall()
        if total > limit:
            self.issue("row_limit", table, [str(total - limit)], count=total - limit)
        models: list[T] = []
        oversize: list[str] = []
        over_budget: list[str] = []
        invalid: list[str] = []
        for descriptor in descriptors:
            raw_key = descriptor["capture_key"]
            if raw_key is None:
                oversize.append("capture_key_over_256_bytes")
                continue
            key = str(raw_key)
            size = int(descriptor["capture_bytes"])
            if size > per_row:
                oversize.append(key)
                continue
            if not self.budget.reserve(size):
                over_budget.append(key)
                continue
            row = self.connection.execute(fetch_sql, fetch_params(key)).fetchone()
            if row is None:
                invalid.append(key)
                continue
            try:
                model = parser(row)
                serialized_size = len(
                    _canonical(model.model_dump(mode="json")).encode()
                )
                if serialized_size > size and not self.budget.reserve(
                    serialized_size - size
                ):
                    over_budget.append(key)
                    continue
                models.append(model)
            except (RecursionError, TypeError, ValueError, json.JSONDecodeError):
                invalid.append(key)
        if oversize:
            self.issue("row_oversize", table, oversize)
        if over_budget:
            self.issue("total_budget", table, over_budget)
        if invalid:
            self.issue("invalid_payload", table, invalid)
        self.counts.append(
            BoundaryCaptureCount(
                table=table,
                total_count=total,
                included_count=len(models),
                omitted_count=total - len(models),
            )
        )
        return models

    def session(self, registration: ProspectiveRegistration) -> ForwardSession:
        descriptor = self.connection.execute(
            """SELECT
            length(CAST(config_json AS BLOB)) + length(CAST(id AS BLOB)) +
            length(CAST(source_run_id AS BLOB)) + length(CAST(policy_hash AS BLOB)) +
            length(CAST(activated_at AS BLOB)) +
            length(CAST(next_due_at AS BLOB)) +
            length(CAST(state AS BLOB)) + length(CAST(cash_krw AS BLOB)) +
            length(CAST(lifetime_high_water_krw AS BLOB)) +
            length(CAST(episode_high_water_krw AS BLOB)) +
            length(CAST(COALESCE(liquidation_completed_at, '') AS BLOB)) +
            length(CAST(COALESCE(next_recovery_check_at, '') AS BLOB)) +
            length(CAST(recovery_confirmations AS BLOB)) AS capture_bytes
            FROM forward_sessions WHERE active=1"""
        ).fetchall()
        if len(descriptor) != 1:
            raise ValueError("active session is unavailable")
        size = int(descriptor[0]["capture_bytes"])
        if size > MAX_ROW_BYTES or not self.budget.reserve(size):
            raise ValueError("active session exceeds capture limits")
        row = self.connection.execute(
            "SELECT * FROM forward_sessions WHERE id=? AND active=1",
            (registration.session_id,),
        ).fetchone()
        if row is None:
            raise ValueError("registered session is not active")
        session = ForwardSession(
            id=row["id"],
            activated_at=row["activated_at"],
            next_due_at=row["next_due_at"],
            source_run_id=row["source_run_id"],
            policy_hash=row["policy_hash"],
            config=ForwardConfig.model_validate_json(row["config_json"]),
            state=row["state"],
            cash_krw=row["cash_krw"],
            lifetime_high_water_krw=row["lifetime_high_water_krw"],
            episode_high_water_krw=row["episode_high_water_krw"],
            liquidation_completed_at=row["liquidation_completed_at"],
            next_recovery_check_at=row["next_recovery_check_at"],
            recovery_confirmations=row["recovery_confirmations"],
        )
        if (
            session.id != registration.session_id
            or session.source_run_id != registration.source_run_id
            or session.policy_hash != registration.policy_hash
            or session.config != registration.config
        ):
            raise ValueError("registered session identity changed")
        self.counts.append(
            BoundaryCaptureCount(
                table="forward_sessions",
                total_count=1,
                included_count=1,
                omitted_count=0,
            )
        )
        return session


def _byte_sum(columns: Sequence[str]) -> str:
    return " + ".join(
        f"length(CAST(COALESCE({column}, '') AS BLOB))" for column in columns
    )


def _decision(row: sqlite3.Row) -> ForwardDecision:
    return ForwardDecision(
        id=row["id"],
        session_id=row["session_id"],
        due_at=row["due_at"],
        recorded_at=row["recorded_at"],
        input_version=row["input_version"],
        state=row["state"],
        reason=row["reason"],
        expires_at=row["expires_at"],
        target_weights=json.loads(row["target_weights_json"]),
        intents=[
            ForwardIntent.model_validate(item)
            for item in json.loads(row["intents_json"])
        ],
        volatility_proxy=row["volatility_proxy"],
        volatility_scale=row["volatility_scale"],
    )


def _input(row: sqlite3.Row) -> BoundaryInputVersion:
    raw = str(row["payload_json"])
    payload_object = json.loads(raw)
    try:
        payload: PortfolioInput | BoundaryRiskInput = PortfolioInput.model_validate(
            payload_object
        )
        kind: Literal["portfolio", "risk_checkpoint"] = "portfolio"
    except ValueError:
        payload = BoundaryRiskInput.model_validate(payload_object)
        kind = "risk_checkpoint"
    return BoundaryInputVersion(
        id=row["id"],
        cutoff_at=row["cutoff_at"],
        recorded_at=row["recorded_at"],
        payload_sha256=_sha(raw.encode()),
        payload_kind=kind,
        payload=payload,
    )


def _execution_quote(row: sqlite3.Row) -> BoundaryExecutionQuote:
    raw = str(row["quote_json"])
    digest = _sha(raw.encode())
    if digest != row["quote_sha256"]:
        raise ValueError("execution quote hash is invalid")
    return BoundaryExecutionQuote(
        fill_id=row["fill_id"],
        quote=ResearchQuote.model_validate_json(raw),
        quote_sha256=digest,
        captured_at=row["captured_at"],
    )


def _make_content(
    connection: sqlite3.Connection,
    registration: ProspectiveRegistration,
    *,
    boundary: BoundaryName,
    boundary_at: datetime,
    read_started_at: datetime,
    read_finished_at: datetime,
    duration: Decimal,
    startup_sha: str,
    current_sha: str,
) -> BoundaryCaptureArtifactContent:
    builder = _CaptureBuilder(connection, registration.session_id)
    session = builder.session(registration)
    sid = registration.session_id
    position_columns = (
        "symbol",
        "currency",
        "quantity",
        "average_cost_krw",
        "updated_at",
    )
    positions = builder.rows(
        table="forward_positions",
        descriptor_sql=f"""SELECT symbol AS capture_key,
        {_byte_sum(position_columns)}
        AS capture_bytes FROM forward_positions WHERE session_id=? ORDER BY symbol""",
        descriptor_params=(sid,),
        fetch_sql="SELECT * FROM forward_positions WHERE session_id=? AND symbol=?",
        fetch_params=lambda key: (sid, key),
        parser=lambda row: ForwardPosition(
            symbol=row["symbol"],
            currency=row["currency"],
            quantity=row["quantity"],
            average_cost_krw=row["average_cost_krw"],
            updated_at=row["updated_at"],
        ),
    )
    decision_columns = (
        "id",
        "due_at",
        "recorded_at",
        "input_version",
        "state",
        "reason",
        "expires_at",
        "target_weights_json",
        "intents_json",
        "volatility_proxy",
        "volatility_scale",
    )
    decisions = builder.rows(
        table="forward_decisions",
        descriptor_sql=f"""SELECT id AS capture_key,
        {_byte_sum(decision_columns)} AS capture_bytes FROM forward_decisions
        WHERE session_id=? ORDER BY recorded_at, id""",
        descriptor_params=(sid,),
        fetch_sql="SELECT * FROM forward_decisions WHERE session_id=? AND id=?",
        fetch_params=lambda key: (sid, key),
        parser=_decision,
    )
    fills = builder.rows(
        table="forward_fills",
        descriptor_sql=f"""SELECT id AS capture_key,
        {_byte_sum(("id", "payload_json"))} AS capture_bytes FROM forward_fills
        WHERE session_id=? ORDER BY received_at, id""",
        descriptor_params=(sid,),
        fetch_sql="SELECT payload_json FROM forward_fills WHERE session_id=? AND id=?",
        fetch_params=lambda key: (sid, key),
        parser=lambda row: ForwardFill.model_validate_json(row["payload_json"]),
    )
    execution_quotes = builder.rows(
        table="forward_execution_quotes",
        descriptor_sql=f"""SELECT q.fill_id AS capture_key,
        {_byte_sum(("q.fill_id", "q.quote_json", "q.quote_sha256", "q.captured_at"))}
        AS capture_bytes FROM forward_execution_quotes q
        JOIN forward_fills f ON f.id=q.fill_id WHERE f.session_id=?
        ORDER BY q.captured_at, q.fill_id""",
        descriptor_params=(sid,),
        fetch_sql="""SELECT q.* FROM forward_execution_quotes q
        JOIN forward_fills f ON f.id=q.fill_id
        WHERE f.session_id=? AND q.fill_id=?""",
        fetch_params=lambda key: (sid, key),
        parser=_execution_quote,
    )
    fill_ids = {fill.id for fill in fills}
    quote_fill_ids = {quote.fill_id for quote in execution_quotes}
    missing_quotes = sorted(fill_ids - quote_fill_ids)
    if missing_quotes:
        builder.issue("missing_reference", "forward_execution_quotes", missing_quotes)
    decision_ids = {decision.id for decision in decisions}
    missing_decisions = sorted({fill.decision_id for fill in fills} - decision_ids)
    if missing_decisions:
        builder.issue("missing_reference", "forward_decisions", missing_decisions)
    referenced_input_ids = sorted({decision.input_version for decision in decisions})
    selected_input_ids = referenced_input_ids[:MAX_INPUT_ROWS]
    if selected_input_ids:
        placeholders = ",".join("?" for _ in selected_input_ids)
        input_sql = f"""SELECT id AS capture_key,
        {_byte_sum(("id", "cutoff_at", "payload_json", "recorded_at"))}
        AS capture_bytes FROM forward_input_versions
        WHERE session_id=? AND id IN ({placeholders}) ORDER BY id"""
        inputs = builder.rows(
            table="forward_input_versions",
            descriptor_sql=input_sql,
            descriptor_params=(sid, *selected_input_ids),
            fetch_sql="""SELECT * FROM forward_input_versions
            WHERE session_id=? AND id=?""",
            fetch_params=lambda key: (sid, key),
            parser=_input,
            limit=MAX_INPUT_ROWS,
            per_row=MAX_INPUT_BYTES,
            total=len(referenced_input_ids),
        )
        found_inputs = {item.id for item in inputs}
        missing_inputs = [
            item for item in selected_input_ids if item not in found_inputs
        ]
        if missing_inputs:
            builder.issue("missing_reference", "forward_input_versions", missing_inputs)
    else:
        inputs = []
        builder.counts.append(
            BoundaryCaptureCount(
                table="forward_input_versions",
                total_count=0,
                included_count=0,
                omitted_count=0,
            )
        )
    action_columns = (
        "id",
        "symbol",
        "exchange",
        "numerator",
        "denominator",
        "factor",
        "source_url",
        "evidence_id",
        "evidence_sha256",
        "operator_verified",
        "observed_at",
        "effective_at",
        "registered_at",
    )
    actions = builder.rows(
        table="forward_corporate_action_metadata",
        descriptor_sql=f"""SELECT id AS capture_key,
        {_byte_sum(action_columns)}
        AS capture_bytes FROM forward_corporate_action_metadata
        WHERE session_id=? ORDER BY effective_at, id""",
        descriptor_params=(sid,),
        fetch_sql="""SELECT * FROM forward_corporate_action_metadata
        WHERE session_id=? AND id=?""",
        fetch_params=lambda key: (sid, key),
        parser=lambda row: BoundaryCorporateAction(
            id=row["id"],
            symbol=row["symbol"],
            exchange=row["exchange"],
            numerator=row["numerator"],
            denominator=row["denominator"],
            factor=row["factor"],
            source_url=row["source_url"],
            evidence_id=row["evidence_id"],
            evidence_sha256=row["evidence_sha256"],
            operator_verified=bool(row["operator_verified"]),
            observed_at=row["observed_at"],
            effective_at=row["effective_at"],
            registered_at=row["registered_at"],
        ),
    )
    application_columns = (
        "a.action_id",
        "a.applied_at",
        "a.before_quantity",
        "a.after_quantity",
        "a.before_average_cost_krw",
        "a.after_average_cost_krw",
    )
    applications = builder.rows(
        table="forward_corporate_action_applications",
        descriptor_sql=f"""SELECT a.action_id AS capture_key,
        {_byte_sum(application_columns)}
        AS capture_bytes FROM forward_corporate_action_applications a
        JOIN forward_corporate_action_metadata m ON m.id=a.action_id
        WHERE m.session_id=? ORDER BY a.applied_at, a.action_id""",
        descriptor_params=(sid,),
        fetch_sql="""SELECT a.* FROM forward_corporate_action_applications a
        JOIN forward_corporate_action_metadata m ON m.id=a.action_id
        WHERE m.session_id=? AND a.action_id=?""",
        fetch_params=lambda key: (sid, key),
        parser=lambda row: BoundaryCorporateApplication(
            action_id=row["action_id"],
            applied_at=row["applied_at"],
            before_quantity=row["before_quantity"],
            after_quantity=row["after_quantity"],
            before_average_cost_krw=row["before_average_cost_krw"],
            after_average_cost_krw=row["after_average_cost_krw"],
        ),
    )
    action_ids = {action.id for action in actions}
    missing_actions = sorted(
        {application.action_id for application in applications} - action_ids
    )
    if missing_actions:
        builder.issue(
            "missing_reference", "forward_corporate_action_metadata", missing_actions
        )
    checkpoint_columns = (
        "id",
        "checkpoint_at",
        "actually_known_at",
        "equity_krw",
        "cash_krw",
        "positions_json",
    )
    checkpoints = builder.rows(
        table="forward_checkpoints",
        descriptor_sql=f"""SELECT id AS capture_key,
        {_byte_sum(checkpoint_columns)}
        AS capture_bytes FROM forward_checkpoints WHERE session_id=?
        ORDER BY checkpoint_at, id""",
        descriptor_params=(sid,),
        fetch_sql="SELECT * FROM forward_checkpoints WHERE session_id=? AND id=?",
        fetch_params=lambda key: (sid, key),
        parser=lambda row: BoundaryCheckpoint(
            id=row["id"],
            checkpoint_at=row["checkpoint_at"],
            actually_known_at=row["actually_known_at"],
            equity_krw=row["equity_krw"],
            cash_krw=row["cash_krw"],
            positions=json.loads(row["positions_json"]),
        ),
    )
    observation_sql = f"""WITH ranked AS (
        SELECT id, symbol, received_at,
        {_byte_sum(("id", "symbol", "reason", "quote_json"))} AS capture_bytes,
        row_number() OVER (
            PARTITION BY symbol ORDER BY received_at DESC, market_at DESC, id DESC
        ) AS sequence
        FROM forward_observations WHERE session_id=?
    ) SELECT id AS capture_key, capture_bytes FROM ranked
    WHERE sequence=1 ORDER BY received_at DESC, symbol, id"""
    observation_total = int(
        connection.execute(
            """SELECT count(DISTINCT symbol) FROM forward_observations
            WHERE session_id=?""",
            (sid,),
        ).fetchone()[0]
    )
    observations = builder.rows(
        table="latest_forward_observations",
        descriptor_sql=observation_sql,
        descriptor_params=(sid,),
        fetch_sql="""SELECT id, reason, quote_json FROM forward_observations
        WHERE session_id=? AND id=?""",
        fetch_params=lambda key: (sid, key),
        parser=lambda row: BoundaryLatestObservation(
            id=row["id"],
            persisted_reason=row["reason"],
            quote=ResearchQuote.model_validate_json(row["quote_json"]),
        ),
        limit=16,
        total=observation_total,
    )
    if observation_total > 16:
        builder.issue(
            "observation_limit",
            "latest_forward_observations",
            [str(observation_total - 16)],
            count=observation_total - 16,
        )
    return BoundaryCaptureArtifactContent(
        session_id=sid,
        boundary=boundary,
        boundary_at=boundary_at,
        read_started_at=read_started_at,
        read_finished_at=read_finished_at,
        monotonic_duration_seconds=duration,
        capture_lag_seconds=Decimal(
            str((read_started_at - boundary_at).total_seconds())
        ),
        contract_sha256=registration.contract_sha256,
        policy_hash=registration.policy_hash,
        source_run_id=registration.source_run_id,
        collector_startup_sha256=startup_sha,
        collector_capture_sha256=current_sha,
        snapshot=BoundaryRawSnapshot(
            session=session,
            positions=positions,
            decisions=decisions,
            fills=fills,
            execution_quotes=execution_quotes,
            input_versions=inputs,
            corporate_actions=actions,
            corporate_action_applications=applications,
            checkpoints=checkpoints,
            latest_observations=observations,
        ),
        counts=builder.counts,
        issues=builder.issues,
    )


def _artifact(content: BoundaryCaptureArtifactContent) -> BoundaryCaptureArtifact:
    payload = content.model_dump(mode="json")
    return BoundaryCaptureArtifact.model_validate(
        payload | {"artifact_sha256": _sha(_canonical(payload).encode())}
    )


def _artifact_bytes(artifact: BoundaryCaptureArtifact) -> bytes:
    return (_canonical(artifact.model_dump(mode="json")) + "\n").encode()


def _read_bounded(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError("capture artifact is unavailable")
    with path.open("rb") as source:
        body = source.read(MAX_ARTIFACT_BYTES + 1)
    if len(body) > MAX_ARTIFACT_BYTES:
        raise ValueError("capture artifact exceeds the size limit")
    return body


def read_boundary_capture(
    path: Path,
    *,
    registration: ProspectiveRegistration,
    boundary: BoundaryName,
) -> BoundaryCaptureArtifact:
    raw = _read_bounded(path)
    return _validate_boundary_capture(
        raw,
        registration=registration,
        boundary=boundary,
    )


def _validate_boundary_capture(
    raw: bytes,
    *,
    registration: ProspectiveRegistration,
    boundary: BoundaryName,
) -> BoundaryCaptureArtifact:
    artifact = BoundaryCaptureArtifact.model_validate_json(raw)
    if raw != _artifact_bytes(artifact):
        raise ValueError("capture artifact is not canonical")
    expected_at = (
        registration.evaluation_start_at
        if boundary == "start"
        else registration.evaluation_end_at
    )
    if (
        artifact.session_id != registration.session_id
        or artifact.boundary != boundary
        or artifact.boundary_at != expected_at
        or artifact.contract_sha256 != registration.contract_sha256
    ):
        raise ValueError("capture artifact identity is invalid")
    return artifact


async def _thread_call[T](operation: Callable[[], T]) -> T:
    task = asyncio.create_task(asyncio.to_thread(operation))
    cancelled = False
    while True:
        try:
            result = await asyncio.shield(task)
            break
        except asyncio.CancelledError:
            cancelled = True
        except BaseException:
            if cancelled:
                raise asyncio.CancelledError from None
            raise
    if cancelled:
        raise asyncio.CancelledError
    return result


class BoundaryCaptureMonitor:
    def __init__(
        self,
        *,
        forward_db: Path,
        output_dir: Path,
        registration_status: Callable[[datetime], ProspectiveRegistrationStatus],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        collector_sha: Callable[[], str] = collector_code_sha256,
    ) -> None:
        self.forward_db = forward_db
        self.output_dir = output_dir
        self._registration_status = registration_status
        self._clock = clock
        self._monotonic = monotonic
        self._sleep = sleep
        self._collector_sha = collector_sha
        self._startup_sha = collector_sha()
        self._task: asyncio.Task[None] | None = None
        self._collecting: BoundaryName | None = None
        self._errors: dict[BoundaryName, CaptureErrorCode] = {}
        self._completed: set[BoundaryName] = set()
        self._last_poll_at: datetime | None = None

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        await asyncio.gather(self._task, return_exceptions=True)
        self._task = None

    async def _loop(self) -> None:
        while True:
            started = self._monotonic()
            await self.run_once()
            elapsed = self._monotonic() - started
            await self._sleep(max(0, CAPTURE_INTERVAL_SECONDS - elapsed))

    async def run_once(self) -> None:
        current = _aware_utc(self._clock(), "capture clock")
        self._last_poll_at = current
        for boundary, boundary_at in BOUNDARIES:
            if current < boundary_at or boundary in self._completed:
                continue
            self._collecting = boundary
            try:
                captured = await _thread_call(
                    lambda: self._capture(boundary, boundary_at)
                )
            except asyncio.CancelledError:
                raise
            except BlockingIOError:
                self._errors[boundary] = "lock_busy"
            except sqlite3.Error:
                self._errors[boundary] = "database_unavailable"
            except ValueError as exc:
                code: CaptureErrorCode = (
                    "collector_identity_changed"
                    if str(exc) == "collector source identity changed"
                    else "artifact_invalid"
                    if "artifact" in str(exc)
                    else "identity_unavailable"
                )
                self._errors[boundary] = code
            except Exception:
                self._errors[boundary] = "capture_failed"
            else:
                self._errors.pop(boundary, None)
                if captured:
                    self._completed.add(boundary)
            finally:
                self._collecting = None

    def _capture(self, boundary: BoundaryName, boundary_at: datetime) -> bool:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        lock_path = self.output_dir / f".{boundary}.lock"
        descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            checked_at = _aware_utc(self._clock(), "capture clock")
            if checked_at < boundary_at:
                return False
            status = self._registration_status(checked_at)
            registration = _valid_registration(status)
            session_dir = self.output_dir / registration.session_id
            target = session_dir / f"{boundary}.json"
            if target.exists():
                read_boundary_capture(
                    target,
                    registration=registration,
                    boundary=boundary,
                )
                return True
            current_sha = self._collector_sha()
            if current_sha != self._startup_sha:
                raise ValueError("collector source identity changed")
            read_started_at = _aware_utc(self._clock(), "capture read start")
            if read_started_at < boundary_at:
                return False
            monotonic_started = self._monotonic()
            with sqlite3.connect(
                f"file:{self.forward_db}?mode=ro", uri=True, timeout=0.1
            ) as connection:
                connection.row_factory = sqlite3.Row
                connection.execute("BEGIN")
                read_finished_at_holder: list[datetime] = []
                content = _make_content(
                    connection,
                    registration,
                    boundary=boundary,
                    boundary_at=boundary_at,
                    read_started_at=read_started_at,
                    read_finished_at=read_started_at,
                    duration=Decimal(0),
                    startup_sha=self._startup_sha,
                    current_sha=current_sha,
                )
                read_finished_at_holder.append(
                    _aware_utc(self._clock(), "capture read finish")
                )
            finished_at = read_finished_at_holder[0]
            duration = Decimal(str(self._monotonic() - monotonic_started))
            content = content.model_copy(
                update={
                    "read_finished_at": finished_at,
                    "monotonic_duration_seconds": duration,
                }
            )
            validated_content = BoundaryCaptureArtifactContent.model_validate(
                content.model_dump(mode="python")
            )
            artifact = _artifact(validated_content)
            body = _artifact_bytes(artifact)
            if len(body) > MAX_ARTIFACT_BYTES:
                raise ValueError("capture artifact exceeds the size limit")
            session_dir.mkdir(parents=True, exist_ok=True)
            temporary = session_dir / f".{boundary}.{uuid.uuid4().hex}.tmp"
            file_descriptor = os.open(
                temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
            )
            try:
                with os.fdopen(file_descriptor, "wb") as destination:
                    destination.write(body)
                    destination.flush()
                    os.fsync(destination.fileno())
                publish_at = _aware_utc(self._clock(), "capture publish")
                if publish_at < boundary_at:
                    raise ValueError("capture clock moved before boundary")
                try:
                    os.link(temporary, target)
                except FileExistsError:
                    read_boundary_capture(
                        target,
                        registration=registration,
                        boundary=boundary,
                    )
                    return True
                directory = os.open(session_dir, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
                return True
            finally:
                temporary.unlink(missing_ok=True)
        finally:
            os.close(descriptor)

    def status(self) -> BoundaryCaptureStatus:
        checked_at = _aware_utc(self._clock(), "capture status clock")
        try:
            status = self._registration_status(checked_at)
            registration = _valid_registration(status)
            current_sha = self._collector_sha()
        except (OSError, sqlite3.Error, ValueError):
            return BoundaryCaptureStatus(
                checked_at=checked_at,
                session_id=None,
                running=self._task is not None and not self._task.done(),
                last_poll_at=self._last_poll_at,
                collector_startup_sha256=self._startup_sha,
                collector_current_sha256=None,
                boundaries=[
                    _error_status("start", EVALUATION_START_AT, "identity_unavailable"),
                    _error_status("end", EVALUATION_END_AT, "identity_unavailable"),
                ],
                limitations=_limitations(),
            )
        items: list[BoundaryCaptureItemStatus] = []
        registered_boundaries: tuple[tuple[BoundaryName, datetime], ...] = (
            ("start", registration.evaluation_start_at),
            ("end", registration.evaluation_end_at),
        )
        for boundary, boundary_at in registered_boundaries:
            target = self.output_dir / registration.session_id / f"{boundary}.json"
            if self._collecting == boundary:
                items.append(
                    BoundaryCaptureItemStatus(
                        boundary=boundary,
                        boundary_at=boundary_at,
                        state="collecting",
                        issue_count=0,
                        download_available=False,
                    )
                )
                continue
            if target.exists():
                try:
                    artifact = read_boundary_capture(
                        target,
                        registration=registration,
                        boundary=boundary,
                    )
                except (OSError, ValueError):
                    items.append(
                        _error_status(boundary, boundary_at, "artifact_invalid")
                    )
                else:
                    items.append(_captured_status(artifact))
                continue
            error = self._errors.get(boundary)
            if current_sha != self._startup_sha:
                items.append(
                    _error_status(boundary, boundary_at, "collector_identity_changed")
                )
            elif error is not None:
                items.append(_error_status(boundary, boundary_at, error))
            else:
                items.append(
                    BoundaryCaptureItemStatus(
                        boundary=boundary,
                        boundary_at=boundary_at,
                        state="scheduled",
                        issue_count=0,
                        download_available=False,
                    )
                )
        return BoundaryCaptureStatus(
            checked_at=checked_at,
            session_id=registration.session_id,
            running=self._task is not None and not self._task.done(),
            last_poll_at=self._last_poll_at,
            collector_startup_sha256=self._startup_sha,
            collector_current_sha256=current_sha,
            boundaries=items,
            limitations=_limitations(),
        )

    def artifact_body(self, boundary: BoundaryName) -> tuple[bytes, str]:
        checked_at = _aware_utc(self._clock(), "capture artifact clock")
        registration = _valid_registration(self._registration_status(checked_at))
        target = self.output_dir / registration.session_id / f"{boundary}.json"
        raw = _read_bounded(target)
        _validate_boundary_capture(
            raw,
            registration=registration,
            boundary=boundary,
        )
        return raw, _sha(raw)


def _valid_registration(
    status: ProspectiveRegistrationStatus,
) -> ProspectiveRegistration:
    if (
        status.status not in {"planned", "observing", "window_elapsed"}
        or status.reason is not None
        or status.registration is None
        or status.current_session_id != status.registration.session_id
    ):
        raise ValueError("prospective registration identity is unavailable")
    registration = status.registration
    if (
        registration.evaluation_start_at != EVALUATION_START_AT
        or registration.evaluation_end_at != EVALUATION_END_AT
    ):
        raise ValueError("prospective registration boundaries are invalid")
    return registration


def _captured_status(artifact: BoundaryCaptureArtifact) -> BoundaryCaptureItemStatus:
    return BoundaryCaptureItemStatus(
        boundary=artifact.boundary,
        boundary_at=artifact.boundary_at,
        state="captured_with_issues" if artifact.issues else "captured_raw",
        artifact_sha256=artifact.artifact_sha256,
        read_started_at=artifact.read_started_at,
        read_finished_at=artifact.read_finished_at,
        capture_lag_seconds=artifact.capture_lag_seconds,
        issue_count=len(artifact.issues),
        download_available=True,
    )


def _error_status(
    boundary: BoundaryName, boundary_at: datetime, error: CaptureErrorCode
) -> BoundaryCaptureItemStatus:
    return BoundaryCaptureItemStatus(
        boundary=boundary,
        boundary_at=boundary_at,
        state="error",
        issue_count=0,
        download_available=False,
        error_code=error,
    )


def _limitations() -> list[str]:
    return [
        "원시 관측 snapshot은 경계 시점 NAV를 재구성하거나 승인한 값이 아닙니다.",
        "최근 시세는 경계 이전 시세가 아니라 읽기 시점의 종목별 최신 관측입니다.",
        (
            "누락·손상·용량 제한이 있어도 최초 snapshot을 고정하며 개선 "
            "목적으로 다시 수집하지 않습니다."
        ),
    ]
