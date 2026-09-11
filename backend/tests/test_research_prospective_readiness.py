from __future__ import annotations

import hashlib
import sqlite3
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Literal

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

import jusik.research_app as research_app_module
from jusik.research_app import create_research_app
from jusik.research_config import PAPER_BASE_URL, ResearchSettings
from jusik.research_forward_models import ForwardConfig, ForwardFill
from jusik.research_forward_store import ForwardStore
from jusik.research_models import ResearchInputSnapshot, ResearchRunRequest
from jusik.research_prospective_readiness import (
    MAX_FILL_INSPECTION,
    prospective_readiness,
)
from jusik.research_prospective_registration import (
    EVALUATION_END_AT,
    EVALUATION_START_AT,
    CodeIdentity,
    ProspectiveRegistration,
    ProspectiveRegistrationStatus,
    _evaluation_definition,
)
from jusik.research_quote_models import ResearchQuote
from jusik.research_store import ResearchStore

SESSION_ID = "1" * 64
POLICY_HASH = "2" * 64
SOURCE_ID = "source"


class _UnusedProvider:
    async def collect(self, request: ResearchRunRequest) -> ResearchInputSnapshot:
        raise AssertionError(f"unexpected collection request: {request}")


def _schema(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE forward_sessions (
                id TEXT PRIMARY KEY, source_run_id TEXT NOT NULL,
                policy_hash TEXT NOT NULL, config_json TEXT NOT NULL,
                active INTEGER NOT NULL
            );
            CREATE TABLE forward_checkpoints (
                id TEXT PRIMARY KEY, session_id TEXT NOT NULL,
                checkpoint_at TEXT NOT NULL, actually_known_at TEXT NOT NULL,
                equity_krw TEXT NOT NULL, cash_krw TEXT NOT NULL,
                positions_json TEXT NOT NULL, UNIQUE(session_id, checkpoint_at)
            );
            CREATE TABLE forward_fills (
                id TEXT PRIMARY KEY, session_id TEXT NOT NULL,
                decision_id TEXT NOT NULL, symbol TEXT NOT NULL,
                side TEXT NOT NULL, quantity INTEGER NOT NULL,
                market_at TEXT NOT NULL, received_at TEXT NOT NULL,
                local_price TEXT NOT NULL, fx_rate TEXT NOT NULL,
                notional_krw TEXT NOT NULL, transaction_cost_krw TEXT NOT NULL,
                fx_cost_krw TEXT NOT NULL, cash_after_krw TEXT NOT NULL,
                quote_id TEXT NOT NULL, payload_json TEXT NOT NULL
            );
            CREATE TABLE forward_execution_quotes (
                fill_id TEXT PRIMARY KEY, quote_json TEXT NOT NULL,
                quote_sha256 TEXT NOT NULL, captured_at TEXT NOT NULL
            );
            """
        )
        connection.execute(
            "INSERT INTO forward_sessions VALUES (?, ?, ?, ?, 1)",
            (SESSION_ID, SOURCE_ID, POLICY_HASH, ForwardConfig().model_dump_json()),
        )


def _status(
    *,
    status: Literal[
        "not_registered",
        "planned",
        "observing",
        "window_elapsed",
        "identity_mismatch",
        "invalid_contract",
    ] = "observing",
    session_id: str = SESSION_ID,
) -> ProspectiveRegistrationStatus:
    registration = ProspectiveRegistration.model_construct(
        schema_version=1,
        session_id=session_id,
        session_activated_at=datetime(2026, 9, 11, tzinfo=UTC),
        source_run_id=SOURCE_ID,
        policy_hash=POLICY_HASH,
        config=ForwardConfig(),
        source_manifest_sha256="5" * 64,
        source_result_sha256="6" * 64,
        input_sha256="7" * 64,
        registered_at=datetime(2026, 9, 11, tzinfo=UTC),
        evaluation_start_at=EVALUATION_START_AT,
        evaluation_end_at=EVALUATION_END_AT,
        evaluation_duration_days=56,
        code_identity=CodeIdentity.model_construct(sha256="8" * 64, files={}),
        evaluation=_evaluation_definition(),
        user_loss_tolerance_pct=20,
        policy_defense_drawdown_pct=Decimal("10"),
        paper_only=True,
        automatic_promotion_eligible=False,
        contract_sha256="9" * 64,
    )
    return ProspectiveRegistrationStatus.model_construct(
        status=status,
        checked_at=datetime(2026, 9, 11, tzinfo=UTC),
        reason=None,
        current_session_id=session_id,
        app_start_code_identity_sha256="8" * 64,
        current_disk_code_identity_sha256="8" * 64,
        current_source_manifest_sha256="5" * 64,
        current_source_result_sha256="6" * 64,
        registration=registration,
    )


def _checkpoint(
    path: Path,
    checkpoint_at: str,
    actually_known_at: str,
    *,
    identity: str = "checkpoint",
) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute(
            "INSERT INTO forward_checkpoints VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                identity,
                SESSION_ID,
                checkpoint_at,
                actually_known_at,
                "999999999",
                "123456789",
                "{}",
            ),
        )


def _quote(at: datetime) -> ResearchQuote:
    return ResearchQuote(
        symbol="NVDA",
        exchange="NAS",
        currency="USD",
        price=Decimal("100"),
        ask=Decimal("100"),
        bid=Decimal("99"),
        volume=1,
        accumulated_volume=1,
        market_at=at,
        received_at=at + timedelta(seconds=1),
        source="KIS HDFSCNT0",
    )


def _fill(path: Path, index: int, at: datetime, evidence: str = "captured") -> str:
    identity = f"{index:064x}"
    quote = _quote(at)
    fill = ForwardFill(
        id=identity,
        session_id=SESSION_ID,
        decision_id="3" * 64,
        symbol="NVDA",
        side="buy",
        quantity=1,
        market_at=quote.market_at,
        received_at=quote.received_at,
        local_price=Decimal("100"),
        fx_rate=Decimal("1300"),
        notional_krw=Decimal("130000"),
        transaction_cost_krw=Decimal(0),
        fx_cost_krw=Decimal(0),
        cash_after_krw=Decimal("99870000"),
        quote_id="4" * 64,
    )
    with sqlite3.connect(path) as connection:
        connection.execute(
            """INSERT INTO forward_fills VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                fill.id,
                fill.session_id,
                fill.decision_id,
                fill.symbol,
                fill.side,
                fill.quantity,
                fill.market_at.isoformat(),
                fill.received_at.isoformat(),
                str(fill.local_price),
                str(fill.fx_rate),
                str(fill.notional_krw),
                str(fill.transaction_cost_krw),
                str(fill.fx_cost_krw),
                str(fill.cash_after_krw),
                fill.quote_id,
                fill.model_dump_json(),
            ),
        )
        if evidence != "missing":
            raw = quote.model_dump_json()
            digest = hashlib.sha256(raw.encode()).hexdigest()
            connection.execute(
                "INSERT INTO forward_execution_quotes VALUES (?, ?, ?, ?)",
                (
                    fill.id,
                    raw,
                    "0" * 64 if evidence == "bad_hash" else digest,
                    fill.received_at.isoformat(),
                ),
            )
    return identity


def test_boundaries_require_exact_normalized_checkpoint_without_nav(
    tmp_path: Path,
) -> None:
    database = tmp_path / "forward.db"
    _schema(database)
    _checkpoint(
        database,
        "2026-09-13T23:59:59+00:00",
        "2026-09-14T00:00:01+00:00",
        identity="old",
    )
    _checkpoint(
        database,
        "2026-09-14T09:00:00+09:00",
        "2026-09-14T00:00:02Z",
        identity="exact",
    )
    before = prospective_readiness(
        forward_db=database,
        registration_status=_status(status="planned"),
        now=EVALUATION_START_AT - timedelta(microseconds=1),
    )
    assert before.start_boundary.state == "not_due"
    at_start = prospective_readiness(
        forward_db=database,
        registration_status=_status(),
        now=EVALUATION_START_AT + timedelta(seconds=3),
    )
    assert at_start.start_boundary.state == "unverified_candidate"
    assert at_start.start_boundary.candidate_checkpoint_at == EVALUATION_START_AT
    assert at_start.start_boundary.candidate_actually_known_at != EVALUATION_START_AT
    assert at_start.end_boundary.state == "not_due"
    assert "999999999" not in at_start.model_dump_json()


def test_missing_duplicate_and_invalid_boundary_candidates_fail_closed(
    tmp_path: Path,
) -> None:
    database = tmp_path / "forward.db"
    _schema(database)
    missing = prospective_readiness(
        forward_db=database,
        registration_status=_status(status="window_elapsed"),
        now=EVALUATION_END_AT,
    )
    assert missing.start_boundary.state == "missing"
    assert missing.end_boundary.state == "missing"
    _checkpoint(
        database, EVALUATION_START_AT.isoformat(), EVALUATION_START_AT.isoformat()
    )
    _checkpoint(
        database,
        "2026-09-14T09:00:00+09:00",
        "2026-09-14T00:00:00Z",
        identity="alias",
    )
    with pytest.raises(ValueError, match="ambiguous"):
        prospective_readiness(
            forward_db=database,
            registration_status=_status(),
            now=EVALUATION_START_AT,
        )

    invalid = tmp_path / "invalid.db"
    _schema(invalid)
    _checkpoint(
        invalid,
        EVALUATION_START_AT.isoformat(),
        (EVALUATION_START_AT - timedelta(seconds=1)).isoformat(),
    )
    with pytest.raises(ValueError, match="knowledge timestamp"):
        prospective_readiness(
            forward_db=invalid,
            registration_status=_status(),
            now=EVALUATION_START_AT,
        )


def test_execution_sidecars_are_verified_over_full_half_open_window(
    tmp_path: Path,
) -> None:
    database = tmp_path / "forward.db"
    _schema(database)
    _fill(database, 1, EVALUATION_START_AT - timedelta(seconds=2))
    _fill(database, 2, EVALUATION_START_AT)
    _fill(database, 3, EVALUATION_START_AT + timedelta(days=20), "missing")
    _fill(database, 4, EVALUATION_START_AT + timedelta(days=40), "bad_hash")
    _fill(database, 5, EVALUATION_END_AT - timedelta(seconds=1))
    result = prospective_readiness(
        forward_db=database,
        registration_status=_status(status="window_elapsed"),
        now=EVALUATION_END_AT + timedelta(days=1),
    )
    evidence = result.execution_evidence
    assert evidence.state == "incomplete"
    assert evidence.window_timestamp == "fill_received_at"
    assert evidence.total_fill_count == 3
    assert evidence.captured_count == 1
    assert evidence.missing_count == 1
    assert evidence.mismatch_count == 1
    assert result.evaluation_inputs_complete is False


def test_corrupt_fill_json_and_timestamp_are_not_silently_dropped(
    tmp_path: Path,
) -> None:
    database = tmp_path / "forward.db"
    _schema(database)
    fill_id = _fill(database, 1, EVALUATION_START_AT)
    complete = prospective_readiness(
        forward_db=database,
        registration_status=_status(),
        now=EVALUATION_START_AT + timedelta(days=1),
    )
    assert complete.execution_evidence.state == "linked_integrity"
    assert complete.execution_evidence.captured_count == 1
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE forward_fills SET payload_json='{' WHERE id=?", (fill_id,)
        )
    result = prospective_readiness(
        forward_db=database,
        registration_status=_status(),
        now=EVALUATION_START_AT + timedelta(days=1),
    )
    assert result.execution_evidence.mismatch_count == 1
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE forward_fills SET received_at='not-a-time' WHERE id=?", (fill_id,)
        )
    with pytest.raises(sqlite3.Error):
        prospective_readiness(
            forward_db=database,
            registration_status=_status(),
            now=EVALUATION_START_AT + timedelta(days=1),
        )


def test_zero_fills_is_unobserved_and_read_does_not_mutate_database(
    tmp_path: Path,
) -> None:
    database = tmp_path / "forward.db"
    _schema(database)
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    result = prospective_readiness(
        forward_db=database,
        registration_status=_status(),
        now=EVALUATION_START_AT + timedelta(days=1),
    )
    after = hashlib.sha256(database.read_bytes()).hexdigest()
    assert result.execution_evidence.state == "unobserved"
    assert result.evaluation_inputs_complete is False
    assert before == after


def test_identity_mismatch_and_unknown_session_are_unavailable(tmp_path: Path) -> None:
    database = tmp_path / "forward.db"
    _schema(database)
    with pytest.raises(ValueError, match="identity"):
        prospective_readiness(
            forward_db=database,
            registration_status=_status(status="identity_mismatch"),
        )
    with pytest.raises(ValueError, match="identity"):
        prospective_readiness(
            forward_db=database,
            registration_status=_status(session_id="9" * 64),
        )


def test_fill_inspection_is_bounded_and_total_is_accurate(tmp_path: Path) -> None:
    database = tmp_path / "forward.db"
    _schema(database)
    quote = _quote(EVALUATION_START_AT)
    fill = ForwardFill(
        id="0" * 64,
        session_id=SESSION_ID,
        decision_id="3" * 64,
        symbol="NVDA",
        side="buy",
        quantity=1,
        market_at=quote.market_at,
        received_at=quote.received_at,
        local_price=Decimal("100"),
        fx_rate=Decimal("1300"),
        notional_krw=Decimal("130000"),
        transaction_cost_krw=Decimal(0),
        fx_cost_krw=Decimal(0),
        cash_after_krw=Decimal("99870000"),
        quote_id="4" * 64,
    )
    rows = []
    for index in range(MAX_FILL_INSPECTION + 1):
        identity = f"{index:064x}"
        payload = fill.model_copy(update={"id": identity}).model_dump_json()
        rows.append(
            (
                identity,
                SESSION_ID,
                fill.decision_id,
                "NVDA",
                "buy",
                1,
                quote.market_at.isoformat(),
                quote.received_at.isoformat(),
                "100",
                "1300",
                "130000",
                "0",
                "0",
                "99870000",
                fill.quote_id,
                payload,
            )
        )
    with sqlite3.connect(database) as connection:
        connection.executemany(
            """INSERT INTO forward_fills VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
    result = prospective_readiness(
        forward_db=database,
        registration_status=_status(),
        now=EVALUATION_START_AT + timedelta(days=1),
    )
    assert result.execution_evidence.total_fill_count == MAX_FILL_INSPECTION + 1
    assert result.execution_evidence.inspected_fill_count == MAX_FILL_INSPECTION
    assert result.execution_evidence.uninspected_fill_count == 1
    assert result.execution_evidence.truncated is True
    assert result.execution_evidence.state == "incomplete"


def test_readiness_api_is_read_only_and_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "forward.db"
    store = ForwardStore(database)
    session = store.activate(
        activated_at=datetime(2026, 9, 11, tzinfo=UTC),
        next_due_at=datetime(2026, 9, 14, tzinfo=UTC),
        source_run_id=SOURCE_ID,
        config=ForwardConfig(),
    )
    status = _status(session_id=session.id)
    assert status.registration is not None
    status = status.model_copy(
        update={
            "current_session_id": session.id,
            "registration": status.registration.model_copy(
                update={"session_id": session.id, "policy_hash": session.policy_hash}
            ),
        }
    )
    monkeypatch.setattr(
        research_app_module, "prospective_registration_status", lambda **_: status
    )
    settings = ResearchSettings(
        app_key=SecretStr("key"),
        app_secret=SecretStr("secret"),
        base_url=PAPER_BASE_URL,
        db_path=tmp_path / "research.db",
    )
    app = create_research_app(
        settings=settings,
        store=ResearchStore(tmp_path / "research.db"),
        provider=_UnusedProvider(),
        forward_db_path=database,
        action_collection_enabled=False,
    )
    with TestClient(app) as client:
        response = client.get("/api/research/validation/prospective/readiness")
    assert response.status_code == 200
    assert response.json()["execution_evidence"]["state"] == "unobserved"

    monkeypatch.setattr(
        research_app_module,
        "prospective_registration_status",
        lambda **_: _status(status="identity_mismatch", session_id=session.id),
    )
    with TestClient(app) as client:
        unavailable = client.get("/api/research/validation/prospective/readiness")
    assert unavailable.status_code == 503
    assert unavailable.json() == {"detail": "Prospective readiness unavailable."}
