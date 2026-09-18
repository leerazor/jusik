"""Read-only projection for the public research progress dashboard.

The runner database and the published research catalog are private inputs.  This
module deliberately has no dependency on ``RunnerStore``: opening that store can
create directories and migrate its schema, which is not appropriate for a GET
endpoint.
"""

from __future__ import annotations

import json
import re
import sqlite3
import subprocess
from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Literal
from urllib.parse import quote

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)

DEFAULT_RUNNER_CONFIG = Path.home() / ".config/jusik/development-runner.json"
DEFAULT_RUNNER_STATE = Path.home() / ".local/share/jusik/development-runner"
DEFAULT_HISTORY_DIR = Path.home() / ".local/share/jusik/research-history"
RUNNER_SERVICE_UNIT = "jusik-development-runner.service"
RUNNER_TIMER_UNIT = "jusik-development-runner.timer"
HEX64 = re.compile(r"^[a-f0-9]{64}$")
SAFE_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$")
SAFE_SYMBOL = re.compile(r"^[A-Za-z0-9._-]{1,32}$")
UNSAFE_TEXT = re.compile(r"(?:https?://|/|\\)")

type Availability = Literal["available", "unavailable", "invalid"]
type UnitStatus = Literal["active", "inactive", "unknown"]


def _utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
        raise ValueError("timestamp must be UTC and timezone-aware")
    return value.astimezone(UTC)


def _safe_text(value: str) -> str:
    if UNSAFE_TEXT.search(value):
        raise ValueError("text must not contain paths or URLs")
    return value


def _safe_id(value: str) -> str:
    if SAFE_ID.fullmatch(value) is None:
        raise ValueError("unsafe identifier")
    return value


class Metrics(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    label: StrictStr = Field(min_length=1, max_length=120)
    net_return_pct: StrictStr
    cash_pct: StrictStr
    max_drawdown_pct: StrictStr
    max_leverage_pct: StrictStr
    annual_turnover_pct: StrictStr
    total_cost_krw: StrictStr
    trade_days: StrictInt = Field(ge=0)

    @field_validator("label", mode="after")
    @classmethod
    def validate_label(cls, value: str) -> str:
        return _safe_text(value)

    @field_validator(
        "net_return_pct",
        "cash_pct",
        "max_drawdown_pct",
        "max_leverage_pct",
        "annual_turnover_pct",
        "total_cost_krw",
    )
    @classmethod
    def validate_decimal_string(cls, value: str) -> str:
        try:
            number = Decimal(value)
        except (InvalidOperation, ValueError):
            raise ValueError("metric must be a decimal string") from None
        if not number.is_finite():
            raise ValueError("metric must be finite")
        return value

    @model_validator(mode="after")
    def validate_ranges(self) -> Metrics:
        values = {
            name: Decimal(getattr(self, name))
            for name in (
                "cash_pct",
                "max_drawdown_pct",
                "max_leverage_pct",
                "annual_turnover_pct",
                "total_cost_krw",
                "net_return_pct",
            )
        }
        if values["net_return_pct"] < Decimal("-100"):
            raise ValueError("return cannot be below -100 percent")
        for name in ("cash_pct", "max_drawdown_pct", "max_leverage_pct"):
            if not Decimal("0") <= values[name] <= Decimal("100"):
                raise ValueError(f"{name} must be between 0 and 100 percent")
        for name in ("annual_turnover_pct", "total_cost_krw"):
            if values[name] < Decimal("0"):
                raise ValueError(f"{name} must be non-negative")
        return self


class Comparison(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: StrictStr
    period_start: date
    period_end: date
    cost_multiplier: StrictInt = Field(gt=0)
    drawdown_basis: Literal["all_observer_nav", "close_nav"]
    cash_basis: Literal["utc_day_last_nav"]
    cash_statistic: Literal["mean", "median"]
    baseline: Metrics
    candidate: Metrics

    @field_validator("id", mode="after")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return _safe_id(value)

    @model_validator(mode="after")
    def validate_dates(self) -> Comparison:
        if self.period_start > self.period_end:
            raise ValueError("comparison period is reversed")
        return self


class Study(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: StrictStr
    title: StrictStr = Field(min_length=1, max_length=200)
    published_at: datetime
    cohort_id: StrictStr
    universe_symbols: list[StrictStr] = Field(min_length=1, max_length=500)
    source_sha256: StrictStr
    result_sha256: StrictStr
    report_artifact_sha256: StrictStr
    price_only: Literal[True]
    dividends_included: Literal[False]
    taxes_included: Literal[False]
    retrospective_reused_data: Literal[True]
    point_in_time_verified: Literal[False]
    comparisons: list[Comparison] = Field(min_length=1, max_length=100)

    @field_validator("id", "cohort_id", mode="after")
    @classmethod
    def validate_identifier(cls, value: str) -> str:
        return _safe_id(value)

    @field_validator("title", mode="after")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return _safe_text(value)

    @field_validator("published_at", mode="after")
    @classmethod
    def validate_published_at(cls, value: datetime) -> datetime:
        return _utc_datetime(value)

    @field_validator("universe_symbols")
    @classmethod
    def validate_symbols(cls, values: list[str]) -> list[str]:
        if len(set(values)) != len(values) or any(
            SAFE_SYMBOL.fullmatch(value) is None for value in values
        ):
            raise ValueError("universe symbols must be unique safe identifiers")
        return values

    @field_validator("source_sha256", "result_sha256", "report_artifact_sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        if HEX64.fullmatch(value) is None:
            raise ValueError("artifact digest must be a lowercase SHA-256")
        return value


class ResearchCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1]
    published_at: datetime
    featured_comparison_id: StrictStr | None
    task_labels: dict[StrictStr, StrictStr]
    studies: list[Study] = Field(max_length=100)

    @field_validator("published_at", mode="after")
    @classmethod
    def validate_published_at(cls, value: datetime) -> datetime:
        return _utc_datetime(value)

    @field_validator("task_labels")
    @classmethod
    def validate_task_labels(cls, values: dict[str, str]) -> dict[str, str]:
        for key, value in values.items():
            _safe_id(key)
            if not 1 <= len(value) <= 200:
                raise ValueError("task label length is invalid")
            _safe_text(value)
        return values

    @model_validator(mode="after")
    def validate_catalog_references(self) -> ResearchCatalog:
        cohorts: dict[str, tuple[str, frozenset[str]]] = {}
        for study in self.studies:
            inputs = (study.source_sha256, frozenset(study.universe_symbols))
            if cohorts.setdefault(study.cohort_id, inputs) != inputs:
                raise ValueError("cohort inputs must agree")
        study_ids = [item.id for item in self.studies]
        comparison_ids = [
            comparison.id for study in self.studies for comparison in study.comparisons
        ]
        if len(set(study_ids)) != len(study_ids):
            raise ValueError("study ids must be unique")
        if len(set(comparison_ids)) != len(comparison_ids):
            raise ValueError("comparison ids must be globally unique")
        if self.featured_comparison_id is not None:
            _safe_id(self.featured_comparison_id)
            if self.featured_comparison_id not in comparison_ids:
                raise ValueError("featured comparison does not exist")
        return self


class RunnerPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    daily_launch_limit: int | None
    launches_today: int
    task_timeout_seconds: int
    cooldown_seconds: int
    planning_enabled: bool
    scheduled_end_at: None = None


class RunnerCounts(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    queued: int
    running: int
    completed: int
    blocked: int
    failed: int
    interrupted: int
    other: int


class RunnerCurrent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str
    area: str
    title: str
    started_at: datetime


class RunnerTaskPublic(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str
    area: str
    title: str
    status: str
    updated_at: datetime
    next_allowed_at: datetime | None
    depends_on: str | None


class RunnerProgress(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    availability: Availability
    recorded_at: datetime | None
    paused: bool | None
    service: UnitStatus
    timer: UnitStatus
    policy: RunnerPolicy | None
    counts: RunnerCounts | None
    current: RunnerCurrent | None
    tasks: list[RunnerTaskPublic]
    truncated: bool


class ResearchProgress(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    availability: Availability
    published_at: datetime | None
    featured_comparison_id: str | None
    studies: list[Study]


class ResearchProgressResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1]
    observed_at: datetime
    runner: RunnerProgress
    research: ResearchProgress


def load_catalog(history_dir: Path = DEFAULT_HISTORY_DIR) -> ResearchCatalog:
    """Load and validate the public catalog; callers convert failures to invalid."""

    return ResearchCatalog.model_validate_json(
        (history_dir / "progress.json").read_text(encoding="utf-8")
    )


def _parse_utc(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return _utc_datetime(datetime.fromisoformat(value))
    except (TypeError, ValueError):
        return None


def _safe_db_value(value: object, fallback: str = "unknown") -> str:
    if not isinstance(value, str) or not value or UNSAFE_TEXT.search(value):
        return fallback
    return value


def _safe_identifier_value(value: object) -> str:
    if not isinstance(value, str) or SAFE_ID.fullmatch(value) is None:
        return "unknown"
    return value


def _status_value(value: object) -> str:
    if not isinstance(value, str):
        return "other"
    allowed = {
        "queued",
        "running",
        "completed",
        "blocked",
        "failed",
        "interrupted",
        "retryable",
    }
    return value if value in allowed else "other"


def _title_for(
    task_id: object, area: object, labels: dict[str, str]
) -> tuple[str, str]:
    safe_area = _safe_db_value(area)
    title = labels.get(_safe_identifier_value(task_id))
    if title is not None:
        return safe_area, title
    fallback = {
        "entry-amount-distribution": "진입 금액 분포 연구",
        "preregistration-small-entry": "작은 진입 제약 연구",
        "future-observation-protocol": "미래 관찰 프로토콜",
        "paper-signal-evidence": "PAPER 신호 근거",
        "portfolio-stress-robustness": "포트폴리오 스트레스 강건성",
    }
    return safe_area, fallback.get(safe_area, "연구 작업")


def _probe_systemd(unit: str) -> UnitStatus:
    try:
        result = subprocess.run(
            ["systemctl", "--user", "is-active", unit],
            capture_output=True,
            check=False,
            timeout=2,
            text=True,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    state = result.stdout.strip()
    if state == "active":
        return "active"
    if state == "inactive":
        return "inactive"
    return "unknown"


def _unit_status(unit: str, probe: Callable[[str], UnitStatus] | None) -> UnitStatus:
    if probe is None:
        return _probe_systemd(unit)
    try:
        result = probe(unit)
    except Exception:
        return "unknown"
    return result if result in {"active", "inactive"} else "unknown"


def _load_runner_config(config_path: Path) -> dict[str, object] | None:
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    return raw


def _config_int(
    config: dict[str, object], key: str, default: int, minimum: int, maximum: int
) -> int | None:
    value = config.get(key, default)
    if not isinstance(value, int) or isinstance(value, bool):
        return None
    if not minimum <= value <= maximum:
        return None
    return value


def _runner_db_path(config: dict[str, object] | None, injected: Path | None) -> Path:
    if injected is not None:
        return injected
    if config is not None:
        state_dir = config.get("state_dir")
        if isinstance(state_dir, str) and state_dir:
            return Path(state_dir) / "runner.db"
    return DEFAULT_RUNNER_STATE / "runner.db"


def _required_columns(
    connection: sqlite3.Connection, table: str, columns: set[str]
) -> bool:
    rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
    return bool(rows) and columns <= {str(row[1]) for row in rows}


def _read_runner(
    db_path: Path,
    config_path: Path,
    labels: dict[str, str],
    now: datetime,
    service_probe: Callable[[str], UnitStatus] | None,
) -> RunnerProgress:
    service = _unit_status(RUNNER_SERVICE_UNIT, service_probe)
    timer = _unit_status(RUNNER_TIMER_UNIT, service_probe)
    config = _load_runner_config(config_path)
    uri = "file:" + quote(str(db_path.absolute()), safe="/") + "?mode=ro"
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(uri, uri=True, timeout=0.2, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        if not all(
            (
                _required_columns(
                    connection,
                    "runner_meta",
                    {"key", "value"},
                ),
                _required_columns(
                    connection,
                    "tasks",
                    {
                        "id",
                        "area",
                        "prompt",
                        "status",
                        "attempt_count",
                        "next_allowed_at",
                        "last_attempt_id",
                        "created_at",
                        "updated_at",
                        "previous_attempt_id",
                        "depends_on",
                    },
                ),
                _required_columns(
                    connection,
                    "attempts",
                    {
                        "id",
                        "task_id",
                        "status",
                        "started_at",
                        "ended_at",
                        "process_group_id",
                        "output_path",
                        "stderr_path",
                        "evidence_json",
                        "failure_code",
                    },
                ),
                _required_columns(connection, "launch_log", {"launched_at"}),
                _required_columns(
                    connection,
                    "history_outbox",
                    {"id", "task_id", "attempt_id", "outcome", "delivered_at"},
                ),
            )
        ):
            raise ValueError("runner schema is invalid")
        meta = {
            str(row["key"]): str(row["value"])
            for row in connection.execute("SELECT key,value FROM runner_meta")
        }
        raw_tasks = connection.execute(
            "SELECT id,area,status,next_allowed_at,updated_at,depends_on "
            "FROM tasks WHERE area != ? OR area IS NULL",
            ("__planning__",),
        ).fetchall()
        active_rows = connection.execute(
            "SELECT t.id,t.area,t.status,t.updated_at,t.next_allowed_at,t.depends_on,"
            "a.started_at FROM tasks t JOIN attempts a ON a.task_id=t.id "
            "WHERE t.area != ? AND t.status='running' AND a.status='running' "
            "ORDER BY a.started_at,t.id",
            ("__planning__",),
        ).fetchall()
        launch_prefix = now.astimezone(UTC).date().isoformat() + "%"
        launch_row = connection.execute(
            "SELECT COUNT(*) AS count FROM launch_log WHERE launched_at LIKE ?",
            (launch_prefix,),
        ).fetchone()
        stored_times: list[datetime] = []
        for row in connection.execute("SELECT updated_at FROM tasks"):
            value = _parse_utc(row["updated_at"])
            if value is None:
                raise ValueError("invalid stored task timestamp")
            stored_times.append(value)
        for row in connection.execute("SELECT started_at,ended_at FROM attempts"):
            for name in ("started_at", "ended_at"):
                if name == "ended_at" and row[name] is None:
                    continue
                value = _parse_utc(row[name])
                if value is None:
                    raise ValueError("invalid stored attempt timestamp")
                stored_times.append(value)
        for row in raw_tasks:
            for name in ("id", "area"):
                if not isinstance(row[name], str):
                    raise ValueError("invalid task identifier")
                _safe_id(row[name])
            if not isinstance(row["status"], str) or not row["status"]:
                raise ValueError("invalid task status")
            if row["depends_on"] is not None:
                _safe_id(row["depends_on"])
            if (
                row["next_allowed_at"] is not None
                and _parse_utc(row["next_allowed_at"]) is None
            ):
                raise ValueError("invalid next allowed timestamp")
        running_ids = {row["id"] for row in raw_tasks if row["status"] == "running"}
        active_ids = [row["id"] for row in active_rows]
        if running_ids != set(active_ids) or len(active_ids) != len(set(active_ids)):
            raise ValueError("inconsistent running attempt")
        if (
            connection.execute(
                "SELECT 1 FROM attempts a LEFT JOIN tasks t ON t.id=a.task_id "
                "WHERE a.status='running' AND "
                "(t.id IS NULL OR (t.area!='__planning__' AND t.status!='running')) "
                "LIMIT 1"
            ).fetchone()
            is not None
        ):
            raise ValueError("orphaned running attempt")
        connection.commit()
    except (OSError, sqlite3.Error, ValueError, TypeError) as exc:
        if connection is not None:
            try:
                connection.rollback()
            except sqlite3.Error:
                pass
            connection.close()
        return RunnerProgress(
            availability=(
                "invalid" if isinstance(exc, (ValueError, TypeError)) else "unavailable"
            ),
            recorded_at=None,
            paused=None,
            service=service,
            timer=timer,
            policy=None,
            counts=None,
            current=None,
            tasks=[],
            truncated=False,
        )
    finally:
        if connection is not None:
            connection.close()

    def task_projection(row: sqlite3.Row) -> RunnerTaskPublic:
        updated = _parse_utc(row["updated_at"])
        assert updated is not None  # Validated inside the read transaction.
        area, title = _title_for(row["id"], row["area"], labels)
        dependency = row["depends_on"]
        return RunnerTaskPublic(
            task_id=_safe_identifier_value(row["id"]),
            area=area,
            title=title,
            status=_status_value(row["status"]),
            updated_at=updated,
            next_allowed_at=_parse_utc(row["next_allowed_at"]),
            depends_on=(
                _safe_identifier_value(dependency)
                if isinstance(dependency, str)
                else None
            ),
        )

    projected = [task_projection(row) for row in raw_tasks]
    priority = {
        "running": 0,
        "queued": 1,
        "blocked": 2,
        "interrupted": 3,
        "completed": 4,
        "retryable": 5,
        "failed": 5,
    }
    projected.sort(
        key=lambda item: (
            priority.get(item.status, 6),
            -item.updated_at.timestamp(),
            item.task_id,
        )
    )
    truncated = len(projected) > 100
    tasks = projected[:100]
    counts = RunnerCounts(
        queued=sum(item.status == "queued" for item in projected),
        running=sum(item.status == "running" for item in projected),
        completed=sum(item.status == "completed" for item in projected),
        blocked=sum(item.status == "blocked" for item in projected),
        failed=sum(item.status == "failed" for item in projected),
        interrupted=sum(item.status == "interrupted" for item in projected),
        other=sum(
            item.status
            not in {
                "queued",
                "running",
                "completed",
                "blocked",
                "failed",
                "interrupted",
            }
            for item in projected
        ),
    )
    current = None
    if active_rows:
        row = active_rows[0]
        started = _parse_utc(row["started_at"])
        updated = _parse_utc(row["updated_at"])
        if started is not None and updated is not None:
            area, title = _title_for(row["id"], row["area"], labels)
            current = RunnerCurrent(
                task_id=_safe_identifier_value(row["id"]),
                area=area,
                title=title,
                started_at=started,
            )
    policy = None
    if config is not None:
        timeout = _config_int(config, "timeout_seconds", 5400, 60, 5400)
        cooldown = _config_int(config, "cooldown_seconds", 60, 0, 86400)
        daily = config.get("daily_launches", 8)
        daily_is_valid = daily is None or (
            isinstance(daily, int) and not isinstance(daily, bool) and 1 <= daily <= 24
        )
        planning = config.get("planning_enabled", False)
        if (
            timeout is not None
            and cooldown is not None
            and daily_is_valid
            and isinstance(planning, bool)
        ):
            policy = RunnerPolicy(
                daily_launch_limit=daily,
                launches_today=int(launch_row["count"]),
                task_timeout_seconds=timeout,
                cooldown_seconds=cooldown,
                planning_enabled=planning,
            )
    paused = None
    if meta.get("paused") in {"0", "1"}:
        paused = meta["paused"] == "1"
    return RunnerProgress(
        availability="available",
        recorded_at=max(stored_times, default=None),
        paused=paused,
        service=service,
        timer=timer,
        policy=policy,
        counts=counts,
        current=current,
        tasks=tasks,
        truncated=truncated,
    )


def build_research_progress(
    *,
    config_path: Path = DEFAULT_RUNNER_CONFIG,
    history_dir: Path = DEFAULT_HISTORY_DIR,
    runner_db_path: Path | None = None,
    now: datetime | None = None,
    service_probe: Callable[[str], UnitStatus] | None = None,
) -> ResearchProgressResponse:
    """Build one privacy-safe dashboard snapshot without mutating its inputs."""

    observed_at = _utc_datetime(now or datetime.now(UTC))
    catalog: ResearchCatalog | None
    try:
        catalog = load_catalog(history_dir)
    except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError):
        catalog = None
    labels = {} if catalog is None else dict(catalog.task_labels)
    runner = _read_runner(
        _runner_db_path(_load_runner_config(config_path), runner_db_path),
        config_path,
        labels,
        observed_at,
        service_probe,
    )
    if catalog is None:
        research = ResearchProgress(
            availability="unavailable"
            if not (history_dir / "progress.json").exists()
            else "invalid",
            published_at=None,
            featured_comparison_id=None,
            studies=[],
        )
    else:
        research = ResearchProgress(
            availability="available",
            published_at=catalog.published_at,
            featured_comparison_id=catalog.featured_comparison_id,
            studies=catalog.studies,
        )
    return ResearchProgressResponse(
        schema_version=1,
        observed_at=observed_at,
        runner=runner,
        research=research,
    )
