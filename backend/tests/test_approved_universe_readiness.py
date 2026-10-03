import sqlite3
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from fastapi import Response

from jusik import approved_universe_readiness as readiness_module
from jusik.approved_universe import (
    ApprovedUniverseSnapshot,
    ApprovedUniverseStore,
    ApprovedUniverseUpdate,
)
from jusik.approved_universe_readiness import (
    ApprovedUniverseReadiness,
    build_approved_universe_readiness,
)
from jusik.research_app import create_research_app
from jusik.research_config import PAPER_BASE_URL, ResearchSettings


def _snapshot() -> ApprovedUniverseSnapshot:
    return ApprovedUniverseSnapshot.model_validate(
        {
            "revision": 4,
            "updated_at": None,
            "instruments": [
                {"market": "US", "exchange": "NAS", "symbol": "NVDA"},
                {"market": "KR", "exchange": "KRX", "symbol": "005930"},
            ],
        }
    )


def _readiness(root: Path) -> ApprovedUniverseReadiness:
    return build_approved_universe_readiness(
        _snapshot(),
        universe_db_path=root / "price.db",
        action_db_path=root / "actions.db",
        external_db_path=root / "fx.db",
    )


def test_missing_databases_never_created(tmp_path: Path) -> None:
    result = _readiness(tmp_path)
    assert result.revision == 4
    assert result.comparison_status == "not_performed"
    assert result.price_source_status == "unavailable"
    assert result.dividend_source_status == "unavailable"
    assert result.fx.status == "unavailable"
    assert all(item.price.status == "unavailable" for item in result.instruments)
    assert all(
        item.dividend.observed_event_count is None for item in result.instruments
    )
    assert list(tmp_path.iterdir()) == []


def test_partial_stale_latest_reviews_and_distinct_fx(tmp_path: Path) -> None:
    with sqlite3.connect(tmp_path / "price.db") as db:
        db.executescript("""
            CREATE TABLE universe_collection_state (
                instrument_id TEXT, status TEXT, snapshot_id TEXT, error TEXT,
                updated_at TEXT, last_success_at TEXT);
            CREATE TABLE universe_snapshots (
                id TEXT, requested_start TEXT, requested_end TEXT,
                actual_start TEXT, actual_end TEXT, evaluation_start TEXT,
                warmup_bars INTEGER, evaluation_bars INTEGER);
            INSERT INTO universe_snapshots VALUES
                ('s1','2023-10-03','2026-10-02','2024-04-02','2026-10-01',
                 '2024-04-10',60,568);
            INSERT INTO universe_collection_state VALUES
                ('NVDA','stale','s1','private /path/error','2026-10-02','2026-10-01');
            INSERT INTO universe_collection_state VALUES
                ('UNREGISTERED','error',NULL,
                 'private unregistered failure','2026-10-02',NULL);
        """)
    with sqlite3.connect(tmp_path / "actions.db") as db:
        db.executescript("""
            CREATE TABLE action_collection_events (
                id TEXT, symbol TEXT, kind TEXT, latest_revision_sequence INTEGER);
            CREATE TABLE action_collection_revisions (
                id TEXT, event_id TEXT, sequence INTEGER);
            CREATE TABLE action_reviews (id TEXT, revision_id TEXT);
            INSERT INTO action_collection_events VALUES ('e1','NVDA','dividend',2);
            INSERT INTO action_collection_events VALUES ('e2','NVDA','dividend',1);
            INSERT INTO action_collection_revisions VALUES ('old','e1',1);
            INSERT INTO action_collection_revisions VALUES ('current','e1',2);
            INSERT INTO action_collection_revisions VALUES ('other','e2',1);
            INSERT INTO action_reviews VALUES ('r1','old');
            INSERT INTO action_reviews VALUES ('r2','other');
        """)
    with sqlite3.connect(tmp_path / "fx.db") as db:
        db.executescript("""
            CREATE TABLE external_observations (series TEXT, observed_on TEXT);
            INSERT INTO external_observations VALUES ('usdkrw','2026-10-01');
            INSERT INTO external_observations VALUES ('usdkrw','2026-10-01');
            INSERT INTO external_observations VALUES ('usdkrw','2026-10-02');
            INSERT INTO external_observations VALUES ('vix','2026-10-03');
        """)
    queries: list[str] = []
    original_connect = readiness_module._connect_read_only

    def recording_connect(path: Path) -> sqlite3.Connection:
        connection = original_connect(path)
        if path.name == "price.db":
            connection.set_trace_callback(queries.append)
        return connection

    with patch.object(readiness_module, "_connect_read_only", recording_connect):
        result = _readiness(tmp_path)
    price_sql = " ".join(queries).lower()
    assert "where c.instrument_id in" in price_sql
    assert "unregistered" not in price_sql
    assert "c.*" not in price_sql and "c.error" not in price_sql
    assert result.price_source_status == "available"
    assert result.instruments[0].price.status == "stale"
    assert result.instruments[0].price.history_warning is True
    assert result.instruments[0].price.warmup_bars == 60
    assert result.instruments[0].price.evaluation_bars == 568
    assert result.instruments[0].price.identity_status == "not_checked"
    assert result.instruments[0].dividend.observed_event_count == 2
    assert result.instruments[0].dividend.reviewed_current_event_count == 1
    assert result.instruments[1].price.status == "missing"
    assert result.instruments[1].dividend.observed_event_count == 0
    assert result.fx.observed_date_count == 2
    assert str(result.fx.first_observed_on) == "2026-10-01"
    assert "/path/error" not in result.model_dump_json()


def test_broken_sources_report_unavailable_not_zero(tmp_path: Path) -> None:
    for name in ("price.db", "actions.db", "fx.db"):
        (tmp_path / name).write_text("not sqlite")
    result = _readiness(tmp_path)
    assert result.price_source_status == "unavailable"
    assert result.dividend_source_status == "unavailable"
    assert result.fx.observed_date_count is None


def test_invalid_fx_date_does_not_hide_other_sources(tmp_path: Path) -> None:
    with sqlite3.connect(tmp_path / "fx.db") as db:
        db.executescript("""
            CREATE TABLE external_observations (series TEXT, observed_on TEXT);
            INSERT INTO external_observations VALUES ('usdkrw','2024-01-01');
            INSERT INTO external_observations VALUES ('usdkrw','2025-99-99');
            INSERT INTO external_observations VALUES ('usdkrw','2026-01-01');
        """)
    result = _readiness(tmp_path)
    assert result.fx.status == "unavailable"
    assert result.fx.observed_date_count is None
    assert result.price_source_status == "unavailable"
    assert result.dividend_source_status == "unavailable"


def test_fx_date_limit_fails_closed(tmp_path: Path) -> None:
    with sqlite3.connect(tmp_path / "fx.db") as db:
        db.execute("CREATE TABLE external_observations (series TEXT, observed_on TEXT)")
        db.executemany(
            "INSERT INTO external_observations VALUES ('usdkrw', ?)",
            [
                ((date(2000, 1, 1) + timedelta(days=offset)).isoformat(),)
                for offset in range(10001)
            ],
        )
    assert _readiness(tmp_path).fx.status == "unavailable"


def test_negative_price_counts_affect_only_that_instrument(tmp_path: Path) -> None:
    with sqlite3.connect(tmp_path / "price.db") as db:
        db.executescript("""
            CREATE TABLE universe_collection_state (
                instrument_id TEXT, status TEXT, snapshot_id TEXT,
                last_success_at TEXT);
            CREATE TABLE universe_snapshots (
                id TEXT, requested_start TEXT, requested_end TEXT,
                actual_start TEXT, actual_end TEXT, evaluation_start TEXT,
                warmup_bars INTEGER, evaluation_bars INTEGER);
            INSERT INTO universe_snapshots VALUES
                ('bad','2023-10-03','2026-10-02','2023-04-05','2026-10-01',
                 '2023-10-03',-1,753);
            INSERT INTO universe_snapshots VALUES
                ('good','2023-10-03','2026-10-02','2023-04-05','2026-10-01',
                 '2023-10-03',123,753);
            INSERT INTO universe_collection_state VALUES ('NVDA','success','bad',NULL);
            INSERT INTO universe_collection_state VALUES
                ('005930','success','good',NULL);
        """)
    result = _readiness(tmp_path)
    assert result.price_source_status == "available"
    assert result.instruments[0].price.status == "unavailable"
    assert result.instruments[1].price.status == "success"


def test_readiness_route_returns_revision_order_and_no_store(tmp_path: Path) -> None:
    settings = ResearchSettings(
        app_key="test",
        app_secret="test",
        base_url=PAPER_BASE_URL,
        db_path=tmp_path / "research.db",
    )
    app = create_research_app(
        settings=settings,
        approved_universe_db_path=tmp_path / "approved.db",
        forward_db_path=tmp_path / "forward.db",
        universe_db_path=tmp_path / "price.db",
        external_db_path=tmp_path / "fx.db",
        history_dir=tmp_path / "history",
        history_db_path=tmp_path / "history.db",
        action_collection_db_path=tmp_path / "actions.db",
        portfolio_report_dir=tmp_path / "reports",
        dividend_report_dir=tmp_path / "dividends",
        validation_report_dir=tmp_path / "validation",
        prospective_dir=tmp_path / "prospective",
        prospective_source_report_dir=tmp_path / "reports",
        boundary_capture_dir=tmp_path / "boundary",
        runner_db_path=tmp_path / "runner.db",
        runner_config_path=tmp_path / "runner.json",
        progress_history_dir=tmp_path / "history",
        action_collection_enabled=False,
    )
    store = ApprovedUniverseStore(tmp_path / "approved.db")
    store.replace(
        ApprovedUniverseUpdate(revision=0, instruments=_snapshot().instruments)
    )
    app.state.approved_universe_store = store
    app.state.approved_readiness_paths = (
        tmp_path / "price.db",
        tmp_path / "actions.db",
        tmp_path / "fx.db",
    )

    endpoint = next(
        route.endpoint
        for route in app.routes
        if getattr(route, "path", None) == "/api/research/approved-universe/readiness"
    )
    response = Response()
    with patch.object(store, "read", wraps=store.read) as read:
        body = endpoint(response).model_dump(mode="json")
    assert response.headers["cache-control"] == "no-store"
    assert read.call_count == 1
    assert body["revision"] == 1
    assert body["comparison_status"] == "not_performed"
    assert [row["instrument"]["symbol"] for row in body["instruments"]] == [
        "NVDA",
        "005930",
    ]
    assert body["fx"]["observed_date_count"] is None
