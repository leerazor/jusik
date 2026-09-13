import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from jusik.research_app import create_research_app
from jusik.research_config import PAPER_BASE_URL, ResearchSettings
from jusik.research_progress import (
    Comparison,
    Metrics,
    ResearchCatalog,
    ResearchProgress,
    Study,
    build_research_progress,
)
from jusik.research_store import ResearchStore

NOW = datetime(2026, 9, 13, 12, 0, tzinfo=UTC)
HASH = "a" * 64


def _metrics(label: str = "CASH MEDIAN") -> Metrics:
    return Metrics(
        label=label,
        net_return_pct="12.5",
        cash_pct="20.0",
        max_drawdown_pct="10.0",
        max_leverage_pct="0",
        annual_turnover_pct="30.0",
        total_cost_krw="1000.00",
        trade_days=12,
    )


def _catalog() -> ResearchCatalog:
    return ResearchCatalog(
        schema_version=1,
        published_at=NOW,
        featured_comparison_id="comparison-1",
        task_labels={"entry-amount-distribution": "진입 금액 분포"},
        studies=[
            Study(
                id="study-1",
                title="비용 조정 비교",
                published_at=NOW,
                cohort_id="core10-lowcash",
                universe_symbols=["005930", "000660"],
                source_sha256=HASH,
                result_sha256="b" * 64,
                report_artifact_sha256="c" * 64,
                price_only=True,
                dividends_included=False,
                taxes_included=False,
                retrospective_reused_data=True,
                point_in_time_verified=False,
                comparisons=[
                    Comparison(
                        id="comparison-1",
                        period_start="2023-09-13",
                        period_end="2026-09-11",
                        cost_multiplier=2,
                        drawdown_basis="all_observer_nav",
                        cash_basis="utc_day_last_nav",
                        cash_statistic="median",
                        baseline=_metrics("BASELINE CASH MEDIAN"),
                        candidate=_metrics("CANDIDATE CASH MEDIAN"),
                    )
                ],
            )
        ],
    )


def _make_db(path: Path) -> None:
    with sqlite3.connect(path) as db:
        db.executescript(
            """
            CREATE TABLE runner_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE tasks (
                id TEXT PRIMARY KEY, area TEXT NOT NULL, prompt TEXT NOT NULL,
                status TEXT NOT NULL, attempt_count INTEGER NOT NULL DEFAULT 0,
                next_allowed_at TEXT, last_attempt_id TEXT,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                previous_attempt_id TEXT, depends_on TEXT
            );
            CREATE TABLE attempts (
                id TEXT PRIMARY KEY, task_id TEXT NOT NULL, status TEXT NOT NULL,
                started_at TEXT NOT NULL, ended_at TEXT, process_group_id INTEGER,
                output_path TEXT, stderr_path TEXT, evidence_json TEXT,
                failure_code TEXT
            );
            CREATE TABLE history_outbox (
                id TEXT PRIMARY KEY, task_id TEXT NOT NULL,
                attempt_id TEXT NOT NULL, outcome TEXT NOT NULL, delivered_at TEXT
            );
            CREATE TABLE launch_log (launched_at TEXT PRIMARY KEY);
            INSERT INTO runner_meta VALUES ('paused', '1');
            INSERT INTO tasks
              (id,area,prompt,status,attempt_count,next_allowed_at,last_attempt_id,
               created_at,updated_at,previous_attempt_id,depends_on)
            VALUES
              ('task-running', 'entry-amount-distribution', 'SECRET PROMPT',
               'running', 1, NULL, NULL, '2026-09-13T10:00:00+00:00',
               '2026-09-13T10:00:00+00:00', NULL, NULL),
              ('task-queued', 'unknown-area', 'PRIVATE PROMPT',
               'queued', 0, '2026-09-13T13:00:00+00:00',
               NULL, '2026-09-13T09:00:00+00:00',
               '2026-09-13T09:00:00+00:00', NULL, 'task-running'),
              ('task-planned', '__planning__', 'PLANNER PROMPT',
               'queued', 0, NULL, NULL, '2026-09-13T08:00:00+00:00',
               '2026-09-13T08:00:00+00:00', NULL, NULL),
              ('task-done', 'entry-amount-distribution', 'OLD SECRET',
               'completed', 1, NULL, NULL, '2026-09-12T08:00:00+00:00',
               '2026-09-12T08:00:00+00:00', NULL, NULL);
            INSERT INTO attempts
              (id,task_id,status,started_at,ended_at,process_group_id,output_path,
               stderr_path,evidence_json,failure_code)
              VALUES ('attempt-1', 'task-running', 'running',
               '2026-09-13T11:00:00+00:00', NULL, NULL, NULL, NULL, NULL, NULL);
            INSERT INTO launch_log VALUES ('2026-09-13T01:00:00+00:00');
            INSERT INTO launch_log VALUES ('2026-09-12T01:00:00+00:00');
            """
        )


def _write_catalog(history_dir: Path, catalog: ResearchCatalog | None = None) -> None:
    history_dir.mkdir()
    (history_dir / "progress.json").write_text(
        (catalog or _catalog()).model_dump_json(), encoding="utf-8"
    )


def test_progress_is_read_only_and_projects_runner_and_research(tmp_path: Path) -> None:
    db_path = tmp_path / "runner.db"
    _make_db(db_path)
    before = db_path.read_bytes()
    history_dir = tmp_path / "history"
    _write_catalog(history_dir)
    config_path = tmp_path / "runner.json"
    config_path.write_text(
        json.dumps(
            {
                "state_dir": str(tmp_path / "ignored-by-injection"),
                "daily_launches": None,
                "timeout_seconds": 5400,
                "cooldown_seconds": 60,
                "planning_enabled": True,
            }
        ),
        encoding="utf-8",
    )

    result = build_research_progress(
        config_path=config_path,
        history_dir=history_dir,
        runner_db_path=db_path,
        now=NOW,
        service_probe=lambda unit: "active" if unit.endswith("service") else "inactive",
    )

    assert db_path.read_bytes() == before
    assert result.runner.availability == "available"
    assert result.runner.paused is True
    assert result.runner.service == "active"
    assert result.runner.timer == "inactive"
    assert result.runner.policy is not None
    assert result.runner.policy.daily_launch_limit is None
    assert result.runner.policy.launches_today == 1
    assert result.runner.counts is not None
    assert result.runner.counts.queued == 1
    assert result.runner.counts.running == 1
    assert result.runner.counts.completed == 1
    assert all(item.task_id != "task-planned" for item in result.runner.tasks)
    assert "SECRET PROMPT" not in result.model_dump_json()
    assert result.runner.current is not None
    assert result.runner.current.started_at == datetime(2026, 9, 13, 11, tzinfo=UTC)
    assert result.research.availability == "available"
    assert result.research.studies[0].comparisons[0].cash_statistic == "median"


def test_missing_locked_and_bad_schema_are_graceful(tmp_path: Path) -> None:
    missing = build_research_progress(
        runner_db_path=tmp_path / "missing.db",
        history_dir=tmp_path / "missing-history",
        now=NOW,
        service_probe=lambda _unit: "unknown",
    )
    assert missing.runner.availability == "unavailable"
    assert missing.research.availability == "unavailable"

    bad_path = tmp_path / "bad.db"
    with sqlite3.connect(bad_path) as db:
        db.execute("CREATE TABLE not_runner (value TEXT)")
    bad = build_research_progress(
        runner_db_path=bad_path,
        history_dir=tmp_path / "bad-history",
        now=NOW,
        service_probe=lambda _unit: "inactive",
    )
    assert bad.runner.availability == "invalid"
    assert bad.runner.service == "inactive"

    locked_path = tmp_path / "locked.db"
    _make_db(locked_path)
    lock = sqlite3.connect(locked_path)
    lock.execute("BEGIN EXCLUSIVE")
    try:
        locked = build_research_progress(
            runner_db_path=locked_path,
            history_dir=tmp_path / "locked-history",
            now=NOW,
            service_probe=lambda _unit: "active",
        )
    finally:
        lock.rollback()
        lock.close()
    assert locked.runner.availability == "unavailable"
    assert locked.runner.service == "active"


def test_invalid_catalog_does_not_hide_runner(tmp_path: Path) -> None:
    db_path = tmp_path / "runner.db"
    _make_db(db_path)
    history_dir = tmp_path / "history"
    history_dir.mkdir()
    (history_dir / "progress.json").write_text(
        json.dumps({"schema_version": 1, "featured_comparison_id": "missing"}),
        encoding="utf-8",
    )
    result = build_research_progress(
        runner_db_path=db_path,
        history_dir=history_dir,
        now=NOW,
        service_probe=lambda _unit: "inactive",
    )
    assert result.runner.availability == "available"
    assert result.research == ResearchProgress(
        availability="invalid",
        published_at=None,
        featured_comparison_id=None,
        studies=[],
    )


def test_catalog_rejects_duplicate_featured_and_nonfinite_values() -> None:
    catalog = _catalog()
    invalid = catalog.model_dump(mode="json")
    invalid["featured_comparison_id"] = "missing"
    try:
        ResearchCatalog.model_validate(invalid)
    except ValueError:
        pass
    else:
        raise AssertionError("missing featured comparison must be rejected")

    invalid = catalog.model_dump(mode="json")
    invalid["studies"][0]["comparisons"][0]["baseline"]["cash_pct"] = "NaN"
    try:
        ResearchCatalog.model_validate(invalid)
    except ValueError:
        pass
    else:
        raise AssertionError("non-finite metrics must be rejected")


def test_progress_route_has_no_store_side_effects(tmp_path: Path) -> None:
    db_path = tmp_path / "runner.db"
    _make_db(db_path)
    history_dir = tmp_path / "history"
    _write_catalog(history_dir)
    settings = ResearchSettings(
        app_key="key",
        app_secret="secret",
        base_url=PAPER_BASE_URL,
        db_path=tmp_path / "research.db",
    )
    app = create_research_app(
        settings=settings,
        store=ResearchStore(tmp_path / "research.db"),
        action_collection_enabled=False,
        runner_db_path=db_path,
        progress_history_dir=history_dir,
        runner_service_probe=lambda _unit: "unknown",
    )
    with TestClient(app) as client:
        response = client.get("/api/research/progress")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["schema_version"] == 1
    assert response.json()["runner"]["availability"] == "available"
