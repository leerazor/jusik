from __future__ import annotations

import hashlib
import sqlite3
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from jusik.research_external_models import ExternalObservation
from jusik.research_external_store import ExternalStore
from jusik.research_fx_provenance import (
    MAX_ARCHIVE_BYTES,
    MAX_CANDIDATE_ROWS,
    FxProvenanceResolver,
    resolve_fx_provenance,
)

SOURCE = "yahoo_usdkrw"
BODY = b'{"chart":"fixture"}'
CAPTURED = datetime(2026, 9, 11, tzinfo=UTC)
CUTOFF = CAPTURED + timedelta(hours=1)


def _database(tmp_path: Path) -> Path:
    database = tmp_path / "external.db"
    store = ExternalStore(database)
    store.save_success(
        SOURCE,
        body=BODY,
        content_type="application/json",
        observations=[
            ExternalObservation(
                series="usdkrw",
                observed_on=date(2026, 9, 10),
                value=Decimal("1355.4100341796875"),
                available_at=CAPTURED,
                revision="z",
            )
        ],
        captured_at=CAPTURED,
    )
    return database


def _dump(database: Path) -> str:
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        return "\n".join(connection.iterdump())


def _archive_id() -> str:
    return hashlib.sha256(SOURCE.encode() + b"\0" + BODY).hexdigest()


def _insert_observation(
    database: Path,
    *,
    observed_on: str,
    value: str,
    available_at: str,
    revision: str,
    captured_at: str | None = None,
    source: str = SOURCE,
    archive_id: str | None = None,
) -> None:
    with sqlite3.connect(database) as connection:
        connection.execute(
            """INSERT INTO external_observations
            (series, observed_on, value, available_at, revision,
             source, raw_archive_id, captured_at)
            VALUES ('usdkrw', ?, ?, ?, ?, ?, ?, ?)""",
            (
                observed_on,
                value,
                available_at,
                revision,
                source,
                archive_id or _archive_id(),
                captured_at or CAPTURED.isoformat(),
            ),
        )


def test_resolves_archive_provenance_in_one_read_only_snapshot(tmp_path: Path) -> None:
    database = _database(tmp_path)
    before = _dump(database)
    clocks = iter([CUTOFF + timedelta(seconds=1), CUTOFF + timedelta(seconds=2)])
    result = FxProvenanceResolver(database, clock=lambda: next(clocks)).resolve(
        "USD", CUTOFF
    )
    assert _dump(database) == before
    assert result.state == "resolved"
    assert result.rate_krw_per_unit == Decimal("1355.4100341796875")
    assert result.age_days == 1
    assert result.observation is not None
    assert result.observation.source == SOURCE
    assert result.observation.raw_archive_id == _archive_id()
    assert result.archive is not None
    assert result.archive.body_bytes == len(BODY)
    assert result.archive.body_sha256 == hashlib.sha256(BODY).hexdigest()
    assert result.read_started_at < result.read_finished_at
    assert result.linked_to_execution is False
    assert result.accepted_nav is False
    assert result.historical_point_in_time_proven is False


def test_resolver_closes_the_read_connection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)

    class TrackingConnection(sqlite3.Connection):
        was_closed = False

        def close(self) -> None:
            self.was_closed = True
            super().close()

    opened: list[TrackingConnection] = []
    real_connect = sqlite3.connect

    def tracked_connect(
        database_name: str, *, uri: bool, timeout: float
    ) -> sqlite3.Connection:
        connection = real_connect(
            database_name,
            uri=uri,
            timeout=timeout,
            factory=TrackingConnection,
        )
        opened.append(connection)
        return connection

    monkeypatch.setattr("jusik.research_fx_provenance.sqlite3.connect", tracked_connect)
    result = resolve_fx_provenance(database, "USD", CUTOFF)
    assert result.state == "resolved"
    assert len(opened) == 1
    assert opened[0].was_closed is True


def test_krw_identity_does_not_require_or_fabricate_a_database(tmp_path: Path) -> None:
    missing = tmp_path / "missing.db"
    result = resolve_fx_provenance(missing, "KRW", CUTOFF)
    assert result.state == "identity_conversion"
    assert result.rate_krw_per_unit == 1
    assert result.observation is None
    assert result.archive is None
    assert not missing.exists()
    with pytest.raises(ValueError, match="currency"):
        resolve_fx_provenance(missing, "EUR", CUTOFF)
    with pytest.raises(ValueError, match="timezone-aware"):
        resolve_fx_provenance(missing, "USD", CUTOFF.replace(tzinfo=None))


@pytest.mark.parametrize("value", ["0", "-1", "NaN", "Infinity"])
def test_invalid_selected_value_fails_without_older_fallback(
    tmp_path: Path, value: str
) -> None:
    database = _database(tmp_path)
    _insert_observation(
        database,
        observed_on="2026-09-11",
        value=value,
        available_at=CUTOFF.isoformat(),
        revision="invalid",
    )
    result = resolve_fx_provenance(database, "USD", CUTOFF)
    assert result.state == "unavailable"
    assert result.reason == "selected_value_invalid"
    assert result.observation is None


def test_utc_date_and_exact_timestamp_boundaries_are_inclusive(tmp_path: Path) -> None:
    database = _database(tmp_path)
    cutoff = datetime(2026, 9, 11, 9, tzinfo=timezone(timedelta(hours=9)))
    assert cutoff.astimezone(UTC) == CAPTURED
    _insert_observation(
        database,
        observed_on="2026-09-11",
        value="1400",
        available_at=CAPTURED.isoformat(),
        revision="exact",
    )
    exact = resolve_fx_provenance(database, "USD", cutoff)
    assert exact.state == "resolved"
    assert exact.rate_krw_per_unit == 1400

    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE external_observations SET captured_at=? WHERE revision='exact'",
            ((CAPTURED + timedelta(microseconds=1)).isoformat(),),
        )
    excluded = resolve_fx_provenance(database, "USD", cutoff)
    assert excluded.state == "resolved"
    assert excluded.rate_krw_per_unit == Decimal("1355.4100341796875")

    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE external_observations SET captured_at=?",
            ((CAPTURED + timedelta(microseconds=1)).isoformat(),),
        )
    none_eligible = resolve_fx_provenance(database, "USD", cutoff)
    assert none_eligible.state == "unavailable"
    assert none_eligible.reason == "no_candidate"


def test_future_observed_day_is_excluded_and_revision_tie_uses_ascending_key(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path)
    for revision, value in (("b", "1401"), ("a", "1400")):
        _insert_observation(
            database,
            observed_on="2026-09-11",
            value=value,
            available_at=CUTOFF.isoformat(),
            revision=revision,
        )
    _insert_observation(
        database,
        observed_on="2026-09-12",
        value="1500",
        available_at=CUTOFF.isoformat(),
        revision="future-day",
    )
    result = resolve_fx_provenance(database, "USD", CUTOFF)
    assert result.state == "resolved"
    assert result.rate_krw_per_unit == 1400
    assert result.observation is not None
    assert result.observation.revision == "a"


@pytest.mark.parametrize(
    ("age", "state", "reason"),
    [(7, "resolved", None), (8, "unavailable", "selected_stale")],
)
def test_staleness_is_inclusive_through_seven_utc_dates(
    tmp_path: Path, age: int, state: str, reason: str | None
) -> None:
    database = _database(tmp_path)
    cutoff = datetime(2026, 9, 18, tzinfo=UTC)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE external_observations SET observed_on=?",
            ((cutoff.date() - timedelta(days=age)).isoformat(),),
        )
    result = resolve_fx_provenance(database, "USD", cutoff)
    assert result.state == state
    assert result.reason == reason


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        ("missing", "archive_missing"),
        ("source", "archive_source_mismatch"),
        ("body", "archive_identity_mismatch"),
        ("capture", "archive_capture_mismatch"),
    ],
)
def test_archive_linkage_failures_return_bounded_reasons(
    tmp_path: Path, mutation: str, reason: str
) -> None:
    database = _database(tmp_path)
    with sqlite3.connect(database) as connection:
        if mutation == "missing":
            connection.execute(
                "UPDATE external_observations SET raw_archive_id=?", ("f" * 64,)
            )
        elif mutation == "source":
            connection.execute("UPDATE external_observations SET source='other_source'")
        elif mutation == "body":
            connection.execute("UPDATE external_raw_archives SET body=x'00'")
        else:
            connection.execute(
                "UPDATE external_raw_archives SET captured_at=?",
                ((CAPTURED + timedelta(seconds=1)).isoformat(),),
            )
    result = resolve_fx_provenance(database, "USD", CUTOFF)
    assert result.state == "unavailable"
    assert result.reason == reason
    assert result.observation is None
    assert result.archive is None


def test_archive_can_precede_an_observation_that_reuses_the_same_body(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path)
    observation_captured = CAPTURED + timedelta(minutes=10)
    _insert_observation(
        database,
        observed_on="2026-09-11",
        value="1400",
        available_at=observation_captured.isoformat(),
        revision="reused-body",
        captured_at=observation_captured.isoformat(),
    )
    result = resolve_fx_provenance(database, "USD", CUTOFF)
    assert result.state == "resolved"
    assert result.observation is not None
    assert result.observation.captured_at == observation_captured
    assert result.archive is not None
    assert result.archive.captured_at == CAPTURED


def test_archive_text_body_is_rejected_before_body_fetch(tmp_path: Path) -> None:
    database = _database(tmp_path)
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE external_raw_archives SET body='not-a-blob'")
    result = resolve_fx_provenance(database, "USD", CUTOFF)
    assert result.state == "unavailable"
    assert result.reason == "archive_malformed"


def test_archive_size_and_candidate_count_are_bounded_before_body_fetch(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE external_raw_archives SET body=?",
            (b"x" * (MAX_ARCHIVE_BYTES + 1),),
        )
    oversize = resolve_fx_provenance(database, "USD", CUTOFF)
    assert oversize.state == "unavailable"
    assert oversize.reason == "archive_oversize"

    with sqlite3.connect(database) as connection:
        connection.execute("DELETE FROM external_observations")
        connection.executemany(
            """INSERT INTO external_observations VALUES
            ('usdkrw', '2026-09-10', '1', ?, ?, ?, ?, ?)""",
            [
                (
                    CAPTURED.isoformat(),
                    f"r{index:05d}",
                    SOURCE,
                    _archive_id(),
                    CAPTURED.isoformat(),
                )
                for index in range(MAX_CANDIDATE_ROWS + 1)
            ],
        )
    limited = resolve_fx_provenance(database, "USD", CUTOFF)
    assert limited.state == "unavailable"
    assert limited.reason == "candidate_limit"
    assert limited.candidate_count == MAX_CANDIDATE_ROWS
