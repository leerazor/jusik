import sqlite3
from pathlib import Path
from unittest.mock import patch

from jusik.approved_universe import ApprovedUniverseSnapshot
from jusik.approved_universe_readiness import build_approved_universe_readiness


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


def _readiness(root: Path) -> object:
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
    with patch(
        "jusik.research_universe_store.UniverseInputStore.load_latest",
        side_effect=AssertionError("full price load"),
    ):
        result = _readiness(tmp_path)
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
            INSERT INTO external_observations VALUES ('usdkrw','invalid-date');
        """)
    result = _readiness(tmp_path)
    assert result.fx.status == "unavailable"
    assert result.fx.observed_date_count is None
    assert result.price_source_status == "unavailable"
    assert result.dividend_source_status == "unavailable"
