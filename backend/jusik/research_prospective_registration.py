from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from jusik.research_forward import DEFAULT_FORWARD_DB
from jusik.research_forward_models import ForwardConfig
from jusik.research_portfolio import DEFAULT_REPORT_DIR
from jusik.research_portfolio_models import PortfolioCandidate, PortfolioConfig

SOURCE_RUN_ID = "fa0907ecfe86b19836881e5a78a874925fc611978ffe31064eacc82a0a46f687"
EVALUATION_START_AT = datetime(2026, 9, 14, tzinfo=UTC)
EVALUATION_END_AT = datetime(2026, 11, 9, tzinfo=UTC)
DEFAULT_PROSPECTIVE_DIR = Path.home() / ".local/share/jusik/research-prospective"
DEFAULT_CODE_ROOT = Path(__file__).parent
CODE_IDENTITY_PATHS = (
    "research_prospective_registration.py",
    "research_clock_health.py",
    "research_forward.py",
    "research_forward_models.py",
    "research_forward_store.py",
    "research_quote_models.py",
    "kis_stream.py",
    "research_portfolio_engine.py",
    "research_portfolio_models.py",
    "research_risk.py",
    "research_market_calendar.py",
    "research_universe_data.py",
    "research_universe_store.py",
    "research_universe_models.py",
    "research_external_store.py",
    "research_external_models.py",
    "research_external_features.py",
    "data/market_sessions_2023_2026.json",
)
MAX_ARTIFACT_BYTES = 32 * 1024 * 1024
MAX_CODE_FILE_BYTES = 4 * 1024 * 1024
HASH_PATTERN = r"^[a-f0-9]{64}$"


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _read_bounded(path: Path, maximum: int) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError("required file is unavailable")
    with path.open("rb") as source:
        body = source.read(maximum + 1)
    if len(body) > maximum:
        raise ValueError("required file exceeds the size limit")
    return body


class CodeIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    sha256: str = Field(pattern=HASH_PATTERN)
    files: dict[str, str]

    @model_validator(mode="after")
    def validate_files(self) -> Self:
        if set(self.files) != set(CODE_IDENTITY_PATHS):
            raise ValueError("code identity file set is invalid")
        if any(
            len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
            for digest in self.files.values()
        ):
            raise ValueError("code identity file hash is invalid")
        if _sha(_canonical(self.files).encode()) != self.sha256:
            raise ValueError("code identity aggregate hash is invalid")
        return self


class ProspectiveMetricDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: Literal[
        "net_return_pct",
        "nav_max_drawdown_pct",
        "turnover_pct",
        "transaction_cost_krw",
        "fx_cost_krw",
        "execution_quote_evidence",
    ]
    definition: str


class ProspectiveEvaluationDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    metrics: list[ProspectiveMetricDefinition] = Field(min_length=6, max_length=6)
    cash_benchmark_return_pct: Decimal = Field(default=Decimal(0), allow_inf_nan=False)
    start_nav_requirement: str
    end_nav_requirement: str
    incomplete_rule: str


class _ProspectiveRegistrationContent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    session_id: str = Field(pattern=HASH_PATTERN)
    session_activated_at: datetime
    config: ForwardConfig
    policy_hash: str = Field(pattern=HASH_PATTERN)
    source_run_id: str = Field(pattern=HASH_PATTERN)
    source_manifest_sha256: str = Field(pattern=HASH_PATTERN)
    source_result_sha256: str = Field(pattern=HASH_PATTERN)
    input_sha256: str = Field(pattern=HASH_PATTERN)
    registered_at: datetime
    evaluation_start_at: datetime
    evaluation_end_at: datetime
    evaluation_duration_days: Literal[56] = 56
    code_identity: CodeIdentity
    evaluation: ProspectiveEvaluationDefinition
    user_loss_tolerance_pct: Literal[20] = 20
    policy_defense_drawdown_pct: Decimal = Field(
        default=Decimal("10"), allow_inf_nan=False
    )
    paper_only: Literal[True] = True
    automatic_promotion_eligible: Literal[False] = False

    @field_validator(
        "session_activated_at",
        "registered_at",
        "evaluation_start_at",
        "evaluation_end_at",
    )
    @classmethod
    def aware_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("registration timestamps must be timezone-aware")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_content(self) -> Self:
        if self.evaluation_start_at != EVALUATION_START_AT:
            raise ValueError("evaluation start is not the fixed boundary")
        if self.evaluation_end_at != EVALUATION_END_AT:
            raise ValueError("evaluation end is not the fixed boundary")
        if self.registered_at >= self.evaluation_start_at:
            raise ValueError("registration must precede the evaluation start")
        if self.evaluation_end_at <= self.evaluation_start_at:
            raise ValueError("evaluation period is invalid")
        if self.policy_defense_drawdown_pct != Decimal("10"):
            raise ValueError("policy defense threshold is not fixed")
        if self.source_run_id != SOURCE_RUN_ID:
            raise ValueError("source run is not the fixed prospective source")
        return self


class ProspectiveRegistration(_ProspectiveRegistrationContent):
    contract_sha256: str = Field(pattern=HASH_PATTERN)

    @model_validator(mode="after")
    def validate_contract_hash(self) -> Self:
        expected = _contract_hash(
            self.model_dump(mode="json", exclude={"contract_sha256"})
        )
        if expected != self.contract_sha256:
            raise ValueError("registration contract hash is invalid")
        return self


class ProspectiveRegistrationStatus(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal[
        "not_registered",
        "planned",
        "observing",
        "window_elapsed",
        "identity_mismatch",
        "invalid_contract",
    ]
    checked_at: datetime
    reason: str | None
    current_session_id: str | None
    app_start_code_identity_sha256: str | None
    current_disk_code_identity_sha256: str | None
    current_source_manifest_sha256: str | None
    current_source_result_sha256: str | None
    registration: ProspectiveRegistration | None

    @field_validator("checked_at")
    @classmethod
    def aware_checked_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("status timestamp must be timezone-aware")
        return value.astimezone(UTC)


class _SessionIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    session_id: str = Field(pattern=HASH_PATTERN)
    activated_at: datetime
    source_run_id: str
    policy_hash: str = Field(pattern=HASH_PATTERN)
    config: ForwardConfig

    @field_validator("activated_at")
    @classmethod
    def aware_activated(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("session activation timestamp must be timezone-aware")
        return value.astimezone(UTC)


class _SourceIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    input_sha256: str = Field(pattern=HASH_PATTERN)
    manifest_sha256: str = Field(pattern=HASH_PATTERN)
    result_sha256: str = Field(pattern=HASH_PATTERN)
    config: PortfolioConfig
    selected_candidate: PortfolioCandidate


def code_identity(code_root: Path = DEFAULT_CODE_ROOT) -> CodeIdentity:
    resolved_root = code_root.resolve()
    hashes: dict[str, str] = {}
    for relative in CODE_IDENTITY_PATHS:
        path = code_root / relative
        resolved = path.resolve()
        if resolved_root not in resolved.parents or path.is_symlink():
            raise ValueError("code identity path is invalid")
        hashes[relative] = _sha(_read_bounded(path, MAX_CODE_FILE_BYTES))
    return CodeIdentity(sha256=_sha(_canonical(hashes).encode()), files=hashes)


def _read_active_session(forward_db: Path) -> _SessionIdentity | None:
    with sqlite3.connect(
        f"file:{forward_db}?mode=ro", uri=True, timeout=0.1
    ) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("BEGIN")
        row = connection.execute(
            """SELECT id, activated_at, source_run_id, policy_hash, config_json
            FROM forward_sessions WHERE active=1 ORDER BY activated_at DESC LIMIT 1"""
        ).fetchone()
    if row is None:
        return None
    config = ForwardConfig.model_validate_json(row["config_json"])
    if _sha(_canonical(config.model_dump(mode="json")).encode()) != row["policy_hash"]:
        raise ValueError("active session policy hash is invalid")
    return _SessionIdentity(
        session_id=row["id"],
        activated_at=row["activated_at"],
        source_run_id=row["source_run_id"],
        policy_hash=row["policy_hash"],
        config=config,
    )


def _json_object(raw: bytes) -> dict[str, object]:
    try:
        payload = json.loads(raw)
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        RecursionError,
        ValueError,
    ) as exc:
        raise ValueError("source artifact JSON is invalid") from exc
    if not isinstance(payload, dict):
        raise ValueError("source artifact root is invalid")
    return payload


def _load_source(source_report_dir: Path, source_run_id: str) -> _SourceIdentity:
    if source_run_id != SOURCE_RUN_ID:
        raise ValueError("active session source run is not the fixed source")
    run_dir = source_report_dir / "portfolio-runs" / source_run_id
    resolved_run = run_dir.resolve()
    if (
        run_dir.is_symlink()
        or resolved_run.parent != (source_report_dir / "portfolio-runs").resolve()
    ):
        raise ValueError("source run path is invalid")
    manifest_raw = _read_bounded(resolved_run / "manifest.json", MAX_ARTIFACT_BYTES)
    result_raw = _read_bounded(resolved_run / "result.json", MAX_ARTIFACT_BYTES)
    manifest = _json_object(manifest_raw)
    result = _json_object(result_raw)
    try:
        manifest_run_id = manifest["run_id"]
        result_run_id = result["run_id"]
        manifest_input = manifest["input_hash"]
        result_input = result["input_hash"]
        manifest_config = PortfolioConfig.model_validate(manifest["config"])
        result_config = PortfolioConfig.model_validate(result["config"])
        manifest_candidate = PortfolioCandidate.model_validate(manifest["selection"])
        result_candidate = PortfolioCandidate.model_validate(
            result["selected_candidate"]
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("source identity fields are invalid") from exc
    if (
        manifest_run_id != source_run_id
        or result_run_id != source_run_id
        or not isinstance(manifest_input, str)
        or manifest_input != result_input
        or manifest_config != result_config
        or manifest_candidate != result_candidate
    ):
        raise ValueError("source manifest and result identity mismatch")
    return _SourceIdentity(
        run_id=source_run_id,
        input_sha256=manifest_input,
        manifest_sha256=_sha(manifest_raw),
        result_sha256=_sha(result_raw),
        config=result_config,
        selected_candidate=result_candidate,
    )


def _validate_session_source(
    session: _SessionIdentity, source: _SourceIdentity
) -> None:
    current = session.config
    historical = source.config
    if (
        session.source_run_id != source.run_id
        or current.candidate_id != source.selected_candidate.id
        or current.method != source.selected_candidate.method
        or current.gate != source.selected_candidate.gate
        or current.policy != "low_turnover_combined"
        or current.initial_cash_krw != historical.initial_cash_krw
        or current.fee_rate != historical.fee_rate
        or current.slippage_rate != historical.slippage_rate
        or current.fx_spread_rate != historical.fx_spread_rate
        or current.symbol_cap != historical.symbol_cap
        or current.gross_cap != historical.gross_cap
        or current.leveraged_cap != historical.leveraged_etf_cap
        or current.drawdown_limit != historical.drawdown_limit
        or current.cadence_days != historical.low_turnover_weeks * 7
        or current.reentry_cooldown_days != historical.reentry_cooldown_days
        or current.recovery_confirmations != historical.recovery_confirmations
        or current.low_turnover_band != historical.low_turnover_band
    ):
        raise ValueError("active session and fixed source policy mismatch")


def _evaluation_definition() -> ProspectiveEvaluationDefinition:
    return ProspectiveEvaluationDefinition(
        metrics=[
            ProspectiveMetricDefinition(
                name="net_return_pct",
                definition=(
                    "(end NAV after recorded KRW costs - start NAV) / start NAV * 100"
                ),
            ),
            ProspectiveMetricDefinition(
                name="nav_max_drawdown_pct",
                definition="maximum peak-to-subsequent-NAV decline inside the window",
            ),
            ProspectiveMetricDefinition(
                name="turnover_pct",
                definition="sum of recorded trade notional KRW / start NAV * 100",
            ),
            ProspectiveMetricDefinition(
                name="transaction_cost_krw",
                definition="sum of recorded PAPER transaction costs in KRW",
            ),
            ProspectiveMetricDefinition(
                name="fx_cost_krw",
                definition="sum of recorded PAPER FX spread costs in KRW",
            ),
            ProspectiveMetricDefinition(
                name="execution_quote_evidence",
                definition="fill linkage to the exact captured execution quote sidecar",
            ),
        ],
        start_nav_requirement=(
            "NAV evidence at the evaluation start is required; current cash or "
            "initial cash must not be substituted"
        ),
        end_nav_requirement=(
            "NAV evidence at the evaluation end is required; the last earlier "
            "checkpoint must not be presented as the end value"
        ),
        incomplete_rule=(
            "missing start/end NAV or required execution evidence makes the future "
            "calculation incomplete"
        ),
    )


def _contract_hash(payload: dict[str, object]) -> str:
    return _sha(_canonical(payload).encode())


def _make_contract(
    session: _SessionIdentity,
    source: _SourceIdentity,
    code: CodeIdentity,
    registered_at: datetime,
) -> ProspectiveRegistration:
    payload: dict[str, object] = {
        "schema_version": 1,
        "session_id": session.session_id,
        "session_activated_at": session.activated_at.isoformat(),
        "config": session.config.model_dump(mode="json"),
        "policy_hash": session.policy_hash,
        "source_run_id": source.run_id,
        "source_manifest_sha256": source.manifest_sha256,
        "source_result_sha256": source.result_sha256,
        "input_sha256": source.input_sha256,
        "registered_at": registered_at.astimezone(UTC).isoformat(),
        "evaluation_start_at": EVALUATION_START_AT.isoformat(),
        "evaluation_end_at": EVALUATION_END_AT.isoformat(),
        "evaluation_duration_days": 56,
        "code_identity": code.model_dump(mode="json"),
        "evaluation": _evaluation_definition().model_dump(mode="json"),
        "user_loss_tolerance_pct": 20,
        "policy_defense_drawdown_pct": "10",
        "paper_only": True,
        "automatic_promotion_eligible": False,
    }
    normalized = _ProspectiveRegistrationContent.model_validate(payload).model_dump(
        mode="json"
    )
    return ProspectiveRegistration.model_validate(
        normalized | {"contract_sha256": _contract_hash(normalized)}
    )


def _registration_identity(registration: ProspectiveRegistration) -> dict[str, object]:
    return registration.model_dump(
        mode="json", exclude={"registered_at", "contract_sha256"}
    )


def _contract_bytes(registration: ProspectiveRegistration) -> bytes:
    return (_canonical(registration.model_dump(mode="json")) + "\n").encode()


def _read_contract(path: Path) -> ProspectiveRegistration:
    raw = _read_bounded(path, 1024 * 1024)
    registration = ProspectiveRegistration.model_validate_json(raw)
    if raw != _contract_bytes(registration):
        raise ValueError("registration file is not canonical")
    return registration


def _same_registration(
    path: Path, requested: ProspectiveRegistration
) -> ProspectiveRegistration:
    existing = _read_contract(path)
    if _registration_identity(existing) != _registration_identity(requested):
        raise ValueError(
            "prospective registration conflicts with the existing contract"
        )
    return existing


def _clock_before_start(clock: Callable[[], datetime]) -> datetime:
    observed_at = clock()
    if observed_at.tzinfo is None:
        raise ValueError("registration clock must be timezone-aware")
    observed_at = observed_at.astimezone(UTC)
    if observed_at >= EVALUATION_START_AT:
        raise ValueError("first registration must precede the evaluation start")
    return observed_at


def register_prospective_evaluation(
    *,
    forward_db: Path = DEFAULT_FORWARD_DB,
    source_report_dir: Path = DEFAULT_REPORT_DIR,
    output_dir: Path = DEFAULT_PROSPECTIVE_DIR,
    code_root: Path = DEFAULT_CODE_ROOT,
    _clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> ProspectiveRegistration:
    session = _read_active_session(forward_db)
    if session is None:
        raise ValueError("active PAPER session is unavailable")
    target = output_dir / f"{session.session_id}.json"
    if not target.exists():
        _clock_before_start(_clock)
    source = _load_source(source_report_dir, session.source_run_id)
    _validate_session_source(session, source)
    code = code_identity(code_root)
    if target.exists():
        existing = _read_contract(target)
        requested = _make_contract(session, source, code, existing.registered_at)
        return _same_registration(target, requested)
    registered_at = _clock_before_start(_clock)
    requested = _make_contract(session, source, code, registered_at)
    output_dir.mkdir(parents=True, exist_ok=True)
    temporary = output_dir / f".{session.session_id}.{uuid.uuid4().hex}.tmp"
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as destination:
            destination.write(_contract_bytes(requested))
            destination.flush()
            os.fsync(destination.fileno())
        _clock_before_start(_clock)
        try:
            os.link(temporary, target)
        except FileExistsError:
            return _same_registration(target, requested)
        directory = os.open(output_dir, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        return requested
    finally:
        temporary.unlink(missing_ok=True)


def prospective_registration_status(
    *,
    forward_db: Path = DEFAULT_FORWARD_DB,
    source_report_dir: Path = DEFAULT_REPORT_DIR,
    output_dir: Path = DEFAULT_PROSPECTIVE_DIR,
    code_root: Path = DEFAULT_CODE_ROOT,
    app_start_code_identity_sha256: str | None,
    now: datetime | None = None,
) -> ProspectiveRegistrationStatus:
    checked_at = (now or datetime.now(UTC)).astimezone(UTC)
    try:
        session = _read_active_session(forward_db)
    except (OSError, sqlite3.Error, ValueError):
        return _status(
            "invalid_contract",
            checked_at,
            "active_session_unreadable",
            None,
            app_start_code_identity_sha256,
            None,
            None,
            None,
            None,
        )
    if session is None:
        return _status(
            "not_registered",
            checked_at,
            "active_session_missing",
            None,
            app_start_code_identity_sha256,
            None,
            None,
            None,
            None,
        )
    target = output_dir / f"{session.session_id}.json"
    if not target.is_file() or target.is_symlink():
        return _status(
            "not_registered",
            checked_at,
            "registration_missing",
            session.session_id,
            app_start_code_identity_sha256,
            None,
            None,
            None,
            None,
        )
    try:
        registration = _read_contract(target)
    except (OSError, ValueError):
        return _status(
            "invalid_contract",
            checked_at,
            "registration_invalid",
            session.session_id,
            app_start_code_identity_sha256,
            None,
            None,
            None,
            None,
        )
    try:
        current_code = code_identity(code_root)
        source = _load_source(source_report_dir, session.source_run_id)
    except (OSError, sqlite3.Error, ValueError):
        return _status(
            "identity_mismatch",
            checked_at,
            "current_identity_unavailable",
            session.session_id,
            app_start_code_identity_sha256,
            None,
            None,
            None,
            registration,
        )
    mismatch = (
        registration.session_id != session.session_id
        or registration.session_activated_at != session.activated_at
        or registration.config != session.config
        or registration.policy_hash != session.policy_hash
        or registration.source_run_id != session.source_run_id
        or registration.source_manifest_sha256 != source.manifest_sha256
        or registration.source_result_sha256 != source.result_sha256
        or registration.input_sha256 != source.input_sha256
        or registration.code_identity.sha256 != current_code.sha256
        or app_start_code_identity_sha256 != registration.code_identity.sha256
    )
    if mismatch:
        return _status(
            "identity_mismatch",
            checked_at,
            "registered_identity_changed",
            session.session_id,
            app_start_code_identity_sha256,
            current_code.sha256,
            source.manifest_sha256,
            source.result_sha256,
            registration,
        )
    if registration.registered_at > checked_at:
        return _status(
            "invalid_contract",
            checked_at,
            "registration_time_is_in_the_future",
            session.session_id,
            app_start_code_identity_sha256,
            current_code.sha256,
            source.manifest_sha256,
            source.result_sha256,
            registration,
        )
    if checked_at < registration.evaluation_start_at:
        state: Literal["planned", "observing", "window_elapsed"] = "planned"
    elif checked_at < registration.evaluation_end_at:
        state = "observing"
    else:
        state = "window_elapsed"
    return _status(
        state,
        checked_at,
        None,
        session.session_id,
        app_start_code_identity_sha256,
        current_code.sha256,
        source.manifest_sha256,
        source.result_sha256,
        registration,
    )


def _status(
    status: Literal[
        "not_registered",
        "planned",
        "observing",
        "window_elapsed",
        "identity_mismatch",
        "invalid_contract",
    ],
    checked_at: datetime,
    reason: str | None,
    session_id: str | None,
    app_start_sha: str | None,
    current_code_sha: str | None,
    source_manifest_sha: str | None,
    source_result_sha: str | None,
    registration: ProspectiveRegistration | None,
) -> ProspectiveRegistrationStatus:
    return ProspectiveRegistrationStatus(
        status=status,
        checked_at=checked_at,
        reason=reason,
        current_session_id=session_id,
        app_start_code_identity_sha256=app_start_sha,
        current_disk_code_identity_sha256=current_code_sha,
        current_source_manifest_sha256=source_manifest_sha,
        current_source_result_sha256=source_result_sha,
        registration=registration,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Register the fixed future PAPER evaluation"
    )
    parser.add_argument("--forward-db", type=Path, default=DEFAULT_FORWARD_DB)
    parser.add_argument("--source-report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_PROSPECTIVE_DIR)
    parser.add_argument("--code-root", type=Path, default=DEFAULT_CODE_ROOT)
    arguments = parser.parse_args()
    try:
        registration = register_prospective_evaluation(
            forward_db=arguments.forward_db,
            source_report_dir=arguments.source_report_dir,
            output_dir=arguments.output_dir,
            code_root=arguments.code_root,
        )
    except (OSError, sqlite3.Error, ValueError):
        print("prospective registration failed", file=sys.stderr)
        return 1
    print(
        _canonical(
            {
                "session_id": registration.session_id,
                "contract_sha256": registration.contract_sha256,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
