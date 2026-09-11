from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError

from jusik.research_app import create_research_app
from jusik.research_config import PAPER_BASE_URL, ResearchSettings
from jusik.research_forward_models import ForwardConfig
from jusik.research_forward_store import ForwardStore
from jusik.research_models import ResearchInputSnapshot, ResearchRunRequest
from jusik.research_portfolio_models import PortfolioCandidate, PortfolioConfig
from jusik.research_prospective_registration import (
    CODE_IDENTITY_PATHS,
    DEFAULT_CODE_ROOT,
    EVALUATION_END_AT,
    EVALUATION_START_AT,
    SOURCE_RUN_ID,
    ProspectiveRegistration,
    _canonical,
    _contract_hash,
    code_identity,
    prospective_registration_status,
    register_prospective_evaluation,
)
from jusik.research_store import ResearchStore


class _UnusedProvider:
    async def collect(self, request: ResearchRunRequest) -> ResearchInputSnapshot:
        raise AssertionError(f"Unexpected collection request: {request}")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path, str]:
    forward_db = tmp_path / "forward.db"
    session = ForwardStore(forward_db).activate(
        activated_at=datetime(2026, 9, 10, tzinfo=UTC),
        next_due_at=datetime(2026, 9, 14, tzinfo=UTC),
        source_run_id=SOURCE_RUN_ID,
        config=ForwardConfig(),
    )
    source_dir = tmp_path / "source"
    run_dir = source_dir / "portfolio-runs" / SOURCE_RUN_ID
    run_dir.mkdir(parents=True)
    config = PortfolioConfig().model_dump(mode="json")
    candidate = PortfolioCandidate(
        id="portfolio_inverse_volatility_fx_vix_v1",
        method="inverse_volatility",
        gate="fx_vix",
    ).model_dump(mode="json")
    input_sha = "a" * 64
    (run_dir / "manifest.json").write_text(
        _canonical(
            {
                "run_id": SOURCE_RUN_ID,
                "input_hash": input_sha,
                "config": config,
                "selection": candidate,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (run_dir / "result.json").write_text(
        _canonical(
            {
                "run_id": SOURCE_RUN_ID,
                "input_hash": input_sha,
                "config": config,
                "selected_candidate": candidate,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "prospective"
    code_root = tmp_path / "code"
    for relative in CODE_IDENTITY_PATHS:
        target = code_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(DEFAULT_CODE_ROOT / relative, target)
    return forward_db, source_dir, output_dir, code_root, session.id


def _register(
    forward_db: Path,
    source_dir: Path,
    output_dir: Path,
    code_root: Path,
    at: datetime = datetime(2026, 9, 11, tzinfo=UTC),
) -> ProspectiveRegistration:
    return register_prospective_evaluation(
        forward_db=forward_db,
        source_report_dir=source_dir,
        output_dir=output_dir,
        code_root=code_root,
        _clock=lambda: at,
    )


def test_registration_is_read_only_canonical_and_idempotent(tmp_path: Path) -> None:
    forward_db, source_dir, output_dir, code_root, session_id = _fixture(tmp_path)
    database_sha = _sha(forward_db)
    registration = _register(forward_db, source_dir, output_dir, code_root)
    target = output_dir / f"{session_id}.json"
    original = target.read_bytes()
    original_mtime = target.stat().st_mtime_ns

    repeated = _register(
        forward_db,
        source_dir,
        output_dir,
        code_root,
        datetime(2026, 9, 12, tzinfo=UTC),
    )
    assert repeated == registration
    assert target.read_bytes() == original
    assert target.stat().st_mtime_ns == original_mtime
    after_window = _register(
        forward_db,
        source_dir,
        output_dir,
        code_root,
        datetime(2026, 12, 8, tzinfo=UTC),
    )
    assert after_window == registration
    assert target.read_bytes() == original
    assert target.stat().st_mtime_ns == original_mtime
    assert _sha(forward_db) == database_sha
    assert registration.evaluation_start_at == EVALUATION_START_AT
    assert registration.evaluation_end_at == EVALUATION_END_AT
    assert registration.evaluation_duration_days == 56
    assert registration.user_loss_tolerance_pct == 20
    assert registration.policy_defense_drawdown_pct == 10
    assert registration.paper_only is True
    assert registration.automatic_promotion_eligible is False
    assert registration.config.initial_cash_krw == 100_000_000
    assert registration.source_run_id == SOURCE_RUN_ID
    assert registration.input_sha256 == "a" * 64


def test_first_registration_at_start_is_rejected_and_reverse_period_is_invalid(
    tmp_path: Path,
) -> None:
    forward_db, source_dir, output_dir, code_root, _session_id = _fixture(tmp_path)
    with pytest.raises(ValueError, match="precede the evaluation start"):
        _register(
            forward_db,
            source_dir,
            output_dir,
            code_root,
            EVALUATION_START_AT,
        )
    assert not output_dir.exists()

    valid = _register(forward_db, source_dir, output_dir, code_root)
    payload = valid.model_dump(mode="json", exclude={"contract_sha256"})
    payload["evaluation_end_at"] = EVALUATION_START_AT.isoformat()
    payload["contract_sha256"] = _contract_hash(
        {key: value for key, value in payload.items() if key != "contract_sha256"}
    )
    with pytest.raises(ValidationError, match="fixed boundary"):
        ProspectiveRegistration.model_validate(payload)


@pytest.mark.parametrize(
    "clock_values",
    [
        [
            datetime(2026, 9, 13, 23, 59, 59, tzinfo=UTC),
            datetime(2026, 9, 14, 0, 0, 1, tzinfo=UTC),
        ],
        [
            datetime(2026, 9, 13, 23, 59, 58, tzinfo=UTC),
            datetime(2026, 9, 13, 23, 59, 59, tzinfo=UTC),
            datetime(2026, 9, 14, 0, 0, 1, tzinfo=UTC),
        ],
    ],
)
def test_first_registration_rechecks_deadline_before_publish(
    tmp_path: Path, clock_values: list[datetime]
) -> None:
    forward_db, source_dir, output_dir, code_root, session_id = _fixture(tmp_path)
    times = iter(clock_values)

    with pytest.raises(ValueError, match="precede the evaluation start"):
        register_prospective_evaluation(
            forward_db=forward_db,
            source_report_dir=source_dir,
            output_dir=output_dir,
            code_root=code_root,
            _clock=lambda: next(times),
        )

    assert not (output_dir / f"{session_id}.json").exists()
    if output_dir.exists():
        assert list(output_dir.iterdir()) == []


def test_registration_never_creates_a_missing_active_session(tmp_path: Path) -> None:
    forward_db, source_dir, output_dir, code_root, _session_id = _fixture(tmp_path)
    with sqlite3.connect(forward_db) as connection:
        connection.execute("DELETE FROM forward_sessions")
    database_sha = _sha(forward_db)
    with pytest.raises(ValueError, match="active PAPER session is unavailable"):
        _register(forward_db, source_dir, output_dir, code_root)
    assert _sha(forward_db) == database_sha
    assert not output_dir.exists()


def test_concurrent_identical_registration_has_one_immutable_winner(
    tmp_path: Path,
) -> None:
    forward_db, source_dir, output_dir, code_root, session_id = _fixture(tmp_path)

    def run() -> ProspectiveRegistration:
        return _register(forward_db, source_dir, output_dir, code_root)

    with ThreadPoolExecutor(max_workers=2) as executor:
        registrations = list(executor.map(lambda _index: run(), range(2)))
    assert registrations[0] == registrations[1]
    assert [path.name for path in output_dir.iterdir()] == [f"{session_id}.json"]


def test_existing_registration_rejects_changed_identity(tmp_path: Path) -> None:
    forward_db, source_dir, output_dir, code_root, session_id = _fixture(tmp_path)
    _register(forward_db, source_dir, output_dir, code_root)
    target = output_dir / f"{session_id}.json"
    before = target.read_bytes()
    calendar = code_root / "data/market_sessions_2023_2026.json"
    calendar.write_bytes(calendar.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="conflicts"):
        _register(forward_db, source_dir, output_dir, code_root)
    assert target.read_bytes() == before


def test_status_transitions_and_identity_mismatch_precede_window_state(
    tmp_path: Path,
) -> None:
    forward_db, source_dir, output_dir, code_root, _session_id = _fixture(tmp_path)
    app_start_sha = code_identity(code_root).sha256
    _register(forward_db, source_dir, output_dir, code_root)

    planned = prospective_registration_status(
        forward_db=forward_db,
        source_report_dir=source_dir,
        output_dir=output_dir,
        code_root=code_root,
        app_start_code_identity_sha256=app_start_sha,
        now=datetime(2026, 9, 13, 23, 59, 59, 999999, tzinfo=UTC),
    )
    assert planned.status == "planned"
    observing = prospective_registration_status(
        forward_db=forward_db,
        source_report_dir=source_dir,
        output_dir=output_dir,
        code_root=code_root,
        app_start_code_identity_sha256=app_start_sha,
        now=EVALUATION_START_AT.replace(microsecond=0),
    )
    assert observing.status == "observing"
    elapsed = prospective_registration_status(
        forward_db=forward_db,
        source_report_dir=source_dir,
        output_dir=output_dir,
        code_root=code_root,
        app_start_code_identity_sha256=app_start_sha,
        now=EVALUATION_END_AT,
    )
    assert elapsed.status == "window_elapsed"

    result_path = source_dir / "portfolio-runs" / SOURCE_RUN_ID / "result.json"
    changed = json.loads(result_path.read_text(encoding="utf-8"))
    changed["config"]["fee_rate"] = "0.002"
    result_path.write_text(_canonical(changed) + "\n", encoding="utf-8")
    mismatch = prospective_registration_status(
        forward_db=forward_db,
        source_report_dir=source_dir,
        output_dir=output_dir,
        code_root=code_root,
        app_start_code_identity_sha256=app_start_sha,
        now=EVALUATION_END_AT,
    )
    assert mismatch.status == "identity_mismatch"


def test_status_detects_tamper_unregistered_and_app_start_disk_difference(
    tmp_path: Path,
) -> None:
    forward_db, source_dir, output_dir, code_root, session_id = _fixture(tmp_path)
    app_start_sha = code_identity(code_root).sha256
    missing = prospective_registration_status(
        forward_db=forward_db,
        source_report_dir=source_dir,
        output_dir=output_dir,
        code_root=code_root,
        app_start_code_identity_sha256=app_start_sha,
        now=datetime(2026, 9, 11, tzinfo=UTC),
    )
    assert missing.status == "not_registered"

    _register(forward_db, source_dir, output_dir, code_root)
    target = output_dir / f"{session_id}.json"
    original = target.read_text(encoding="utf-8")
    target.write_text(original.replace('"paper_only":true', '"paper_only":false'))
    invalid = prospective_registration_status(
        forward_db=forward_db,
        source_report_dir=source_dir,
        output_dir=output_dir,
        code_root=code_root,
        app_start_code_identity_sha256=app_start_sha,
        now=datetime(2026, 9, 11, tzinfo=UTC),
    )
    assert invalid.status == "invalid_contract"

    target.write_text(original, encoding="utf-8")
    code_file = code_root / "research_forward.py"
    code_file.write_bytes(code_file.read_bytes() + b"\n")
    changed_disk = prospective_registration_status(
        forward_db=forward_db,
        source_report_dir=source_dir,
        output_dir=output_dir,
        code_root=code_root,
        app_start_code_identity_sha256=app_start_sha,
        now=datetime(2026, 9, 11, tzinfo=UTC),
    )
    assert changed_disk.status == "identity_mismatch"
    assert changed_disk.app_start_code_identity_sha256 == app_start_sha
    assert changed_disk.current_disk_code_identity_sha256 != app_start_sha


def test_read_only_status_api_returns_registration_contract(tmp_path: Path) -> None:
    forward_db, source_dir, output_dir, code_root, session_id = _fixture(tmp_path)
    _register(forward_db, source_dir, output_dir, code_root)
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
        forward_db_path=forward_db,
        universe_db_path=tmp_path / "universe.db",
        external_db_path=tmp_path / "external.db",
        history_dir=tmp_path / "history",
        history_db_path=tmp_path / "history.db",
        action_collection_db_path=tmp_path / "actions.db",
        action_collection_enabled=False,
        prospective_dir=output_dir,
        prospective_source_report_dir=source_dir,
        prospective_code_root=code_root,
    )
    with TestClient(app) as client:
        response = client.get("/api/research/validation/prospective")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "planned"
    assert body["registration"]["session_id"] == session_id
    assert body["registration"]["contract_sha256"]
