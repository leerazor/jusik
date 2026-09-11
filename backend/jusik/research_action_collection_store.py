from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import cast

from jusik.research_action_collection_models import (
    ActionCollectionStatus,
    ActionEvent,
    ActionEventPage,
    ActionRevision,
    ActionRevisionPage,
    ActionSourceStatus,
    CollectedAction,
    CollectorState,
    RawActionAttempt,
)
from jusik.research_universe_models import ResearchInstrument

PROVIDER = "Yahoo chart"
SUCCESS_INTERVAL = timedelta(hours=24)
FAILURE_INTERVAL = timedelta(hours=1)


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value: object) -> str:
    return hashlib.sha256(_json(value).encode()).hexdigest()


class ActionCollectionStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS action_collection_attempts (
                    id TEXT PRIMARY KEY, symbol TEXT NOT NULL,
                    requested_start TEXT NOT NULL, requested_end TEXT NOT NULL,
                    started_at TEXT NOT NULL, completed_at TEXT,
                    state TEXT NOT NULL, http_status INTEGER,
                    request_url TEXT, body_sha256 TEXT, body BLOB,
                    error_code TEXT, next_due_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS action_collection_source_status (
                    symbol TEXT PRIMARY KEY, yahoo_symbol TEXT NOT NULL,
                    state TEXT NOT NULL, last_attempt_at TEXT,
                    last_success_at TEXT, next_due_at TEXT NOT NULL,
                    error_code TEXT, requested_start TEXT, requested_end TEXT,
                    latest_attempt_id TEXT
                );
                CREATE TABLE IF NOT EXISTS action_collection_events (
                    id TEXT PRIMARY KEY, provider TEXT NOT NULL,
                    symbol TEXT NOT NULL, kind TEXT NOT NULL,
                    provider_key TEXT NOT NULL, vendor_date TEXT NOT NULL,
                    first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL,
                    observation_state TEXT NOT NULL,
                    latest_revision_sequence INTEGER NOT NULL,
                    latest_content_sha256 TEXT NOT NULL,
                    UNIQUE(provider, symbol, kind, provider_key)
                );
                CREATE TABLE IF NOT EXISTS action_collection_revisions (
                    id TEXT PRIMARY KEY, event_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL, content_sha256 TEXT NOT NULL,
                    first_seen_at TEXT NOT NULL, attempt_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    UNIQUE(event_id, sequence),
                    FOREIGN KEY(event_id) REFERENCES action_collection_events(id),
                    FOREIGN KEY(attempt_id) REFERENCES action_collection_attempts(id)
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=0.1)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=100")
        return connection

    def ensure_sources(
        self, instruments: tuple[ResearchInstrument, ...], now: datetime
    ) -> None:
        current = now.astimezone(UTC).isoformat()
        with self._connect() as connection:
            connection.executemany(
                """INSERT OR IGNORE INTO action_collection_source_status
                (symbol, yahoo_symbol, state, next_due_at)
                VALUES (?, ?, 'never', ?)""",
                [(item.symbol, item.yahoo_symbol, current) for item in instruments],
            )

    def recover_interrupted(self, now: datetime) -> int:
        current = now.astimezone(UTC).isoformat()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                """SELECT id, symbol FROM action_collection_attempts
                WHERE state='pending'"""
            ).fetchall()
            for row in rows:
                connection.execute(
                    """UPDATE action_collection_attempts
                    SET state='interrupted', completed_at=?,
                        error_code='interrupted', next_due_at=? WHERE id=?""",
                    (current, current, row["id"]),
                )
                connection.execute(
                    """UPDATE action_collection_source_status
                    SET state='interrupted', error_code='interrupted', next_due_at=?
                    WHERE symbol=?""",
                    (current, row["symbol"]),
                )
        return len(rows)

    def due_symbols(self, now: datetime) -> list[str]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT symbol FROM action_collection_source_status
                WHERE state!='pending' AND next_due_at<=? ORDER BY symbol""",
                (now.astimezone(UTC).isoformat(),),
            ).fetchall()
        return [str(row["symbol"]) for row in rows]

    def begin_attempt(
        self,
        symbol: str,
        requested_start: date,
        requested_end: date,
        started_at: datetime,
    ) -> str:
        started = started_at.astimezone(UTC)
        attempt_id = _hash(
            {
                "symbol": symbol,
                "started_at": started.isoformat(),
                "nonce": uuid.uuid4().hex,
            }
        )
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """INSERT INTO action_collection_attempts
                (id, symbol, requested_start, requested_end, started_at, state,
                 next_due_at) VALUES (?, ?, ?, ?, ?, 'pending', ?)""",
                (
                    attempt_id,
                    symbol,
                    requested_start.isoformat(),
                    requested_end.isoformat(),
                    started.isoformat(),
                    started.isoformat(),
                ),
            )
            connection.execute(
                """UPDATE action_collection_source_status
                SET state='pending', last_attempt_at=?, error_code=NULL,
                    requested_start=?, requested_end=?, latest_attempt_id=?
                WHERE symbol=?""",
                (
                    started.isoformat(),
                    requested_start.isoformat(),
                    requested_end.isoformat(),
                    attempt_id,
                    symbol,
                ),
            )
        return attempt_id

    def complete_success(
        self,
        *,
        attempt_id: str,
        completed_at: datetime,
        http_status: int,
        request_url: str,
        body: bytes,
        actions: list[CollectedAction],
    ) -> None:
        completed = completed_at.astimezone(UTC)
        body_sha = hashlib.sha256(body).hexdigest()
        next_due = completed + SUCCESS_INTERVAL
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            attempt = self._pending_attempt(connection, attempt_id)
            symbol = str(attempt["symbol"])
            requested_start = str(attempt["requested_start"])
            requested_end = str(attempt["requested_end"])
            connection.execute(
                """UPDATE action_collection_attempts
                SET completed_at=?, state='success', http_status=?, request_url=?,
                    body_sha256=?, body=?, error_code=NULL, next_due_at=?
                WHERE id=?""",
                (
                    completed.isoformat(),
                    http_status,
                    request_url,
                    body_sha,
                    body,
                    next_due.isoformat(),
                    attempt_id,
                ),
            )
            connection.execute(
                """UPDATE action_collection_events
                SET observation_state='not_seen_in_latest_response'
                WHERE symbol=? AND vendor_date>=? AND vendor_date<=?""",
                (symbol, requested_start, requested_end),
            )
            for action in actions:
                self._store_action(connection, symbol, attempt_id, completed, action)
            connection.execute(
                """UPDATE action_collection_source_status
                SET state='success', last_attempt_at=?, last_success_at=?,
                    next_due_at=?, error_code=NULL, latest_attempt_id=?
                WHERE symbol=?""",
                (
                    completed.isoformat(),
                    completed.isoformat(),
                    next_due.isoformat(),
                    attempt_id,
                    symbol,
                ),
            )

    def _store_action(
        self,
        connection: sqlite3.Connection,
        symbol: str,
        attempt_id: str,
        completed_at: datetime,
        action: CollectedAction,
    ) -> None:
        event_id = _hash(
            {
                "provider": PROVIDER,
                "symbol": symbol,
                "kind": action.kind,
                "provider_key": action.provider_key,
            }
        )
        payload_json = action.payload.model_dump_json()
        content_sha = hashlib.sha256(payload_json.encode()).hexdigest()
        existing = connection.execute(
            "SELECT * FROM action_collection_events WHERE id=?", (event_id,)
        ).fetchone()
        if existing is None:
            sequence = 1
            connection.execute(
                """INSERT INTO action_collection_events VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, 'observed', ?, ?)""",
                (
                    event_id,
                    PROVIDER,
                    symbol,
                    action.kind,
                    action.provider_key,
                    action.payload.vendor_date.isoformat(),
                    completed_at.isoformat(),
                    completed_at.isoformat(),
                    sequence,
                    content_sha,
                ),
            )
            self._insert_revision(
                connection,
                event_id,
                sequence,
                content_sha,
                completed_at,
                attempt_id,
                payload_json,
            )
            return
        sequence = int(existing["latest_revision_sequence"])
        if existing["latest_content_sha256"] != content_sha:
            sequence += 1
            self._insert_revision(
                connection,
                event_id,
                sequence,
                content_sha,
                completed_at,
                attempt_id,
                payload_json,
            )
        connection.execute(
            """UPDATE action_collection_events
            SET vendor_date=?, last_seen_at=?, observation_state='observed',
                latest_revision_sequence=?, latest_content_sha256=? WHERE id=?""",
            (
                action.payload.vendor_date.isoformat(),
                completed_at.isoformat(),
                sequence,
                content_sha,
                event_id,
            ),
        )

    @staticmethod
    def _insert_revision(
        connection: sqlite3.Connection,
        event_id: str,
        sequence: int,
        content_sha: str,
        completed_at: datetime,
        attempt_id: str,
        payload_json: str,
    ) -> None:
        revision_id = _hash({"event": event_id, "sequence": sequence})
        connection.execute(
            """INSERT INTO action_collection_revisions VALUES
            (?, ?, ?, ?, ?, ?, ?)""",
            (
                revision_id,
                event_id,
                sequence,
                content_sha,
                completed_at.isoformat(),
                attempt_id,
                payload_json,
            ),
        )

    def complete_failure(
        self,
        *,
        attempt_id: str,
        completed_at: datetime,
        error_code: str,
        http_status: int | None = None,
        request_url: str | None = None,
        body: bytes | None = None,
        interrupted: bool = False,
    ) -> None:
        completed = completed_at.astimezone(UTC)
        next_due = completed if interrupted else completed + FAILURE_INTERVAL
        body_sha = hashlib.sha256(body).hexdigest() if body is not None else None
        state = "interrupted" if interrupted else "failure"
        source_state = "interrupted" if interrupted else "error"
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            attempt = self._pending_attempt(connection, attempt_id)
            connection.execute(
                """UPDATE action_collection_attempts
                SET completed_at=?, state=?, http_status=?, request_url=?,
                    body_sha256=?, body=?, error_code=?, next_due_at=? WHERE id=?""",
                (
                    completed.isoformat(),
                    state,
                    http_status,
                    request_url,
                    body_sha,
                    body,
                    error_code,
                    next_due.isoformat(),
                    attempt_id,
                ),
            )
            connection.execute(
                """UPDATE action_collection_source_status
                SET state=?, last_attempt_at=?, next_due_at=?, error_code=?,
                    latest_attempt_id=? WHERE symbol=?""",
                (
                    source_state,
                    completed.isoformat(),
                    next_due.isoformat(),
                    error_code,
                    attempt_id,
                    attempt["symbol"],
                ),
            )

    @staticmethod
    def _pending_attempt(
        connection: sqlite3.Connection, attempt_id: str
    ) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM action_collection_attempts WHERE id=? AND state='pending'",
            (attempt_id,),
        ).fetchone()
        if row is None:
            raise ValueError("Action collection attempt is not pending.")
        return cast(sqlite3.Row, row)

    def status(
        self,
        instruments: tuple[ResearchInstrument, ...],
        now: datetime,
        *,
        collector_state: CollectorState = "idle",
        error_code: str | None = None,
    ) -> ActionCollectionStatus:
        current = now.astimezone(UTC)
        with self._connect() as connection:
            rows = {
                str(row["symbol"]): row
                for row in connection.execute(
                    """SELECT s.*, COUNT(e.id) AS event_count,
                        CASE WHEN a.body IS NOT NULL AND a.body_sha256 IS NOT NULL
                            THEN 1 ELSE 0 END AS latest_attempt_raw_available
                    FROM action_collection_source_status s
                    LEFT JOIN action_collection_events e ON e.symbol=s.symbol
                    LEFT JOIN action_collection_attempts a
                        ON a.id=s.latest_attempt_id
                    GROUP BY s.symbol ORDER BY s.symbol"""
                ).fetchall()
            }
        sources: list[ActionSourceStatus] = []
        for instrument in instruments:
            row = rows.get(instrument.symbol)
            if row is None:
                sources.append(
                    ActionSourceStatus(
                        symbol=instrument.symbol,
                        yahoo_symbol=instrument.yahoo_symbol,
                        state="never",
                        next_due_at=current,
                        stale=True,
                    )
                )
                continue
            last_success = (
                datetime.fromisoformat(row["last_success_at"]).astimezone(UTC)
                if row["last_success_at"]
                else None
            )
            sources.append(
                ActionSourceStatus(
                    symbol=row["symbol"],
                    yahoo_symbol=row["yahoo_symbol"],
                    state=row["state"],
                    last_attempt_at=row["last_attempt_at"],
                    last_success_at=row["last_success_at"],
                    next_due_at=row["next_due_at"],
                    stale=(
                        last_success is None
                        or current - last_success >= SUCCESS_INTERVAL
                    ),
                    error_code=row["error_code"],
                    requested_start=row["requested_start"],
                    requested_end=row["requested_end"],
                    latest_attempt_id=row["latest_attempt_id"],
                    latest_attempt_raw_available=bool(
                        row["latest_attempt_raw_available"]
                    ),
                    event_count=row["event_count"],
                )
            )
        return ActionCollectionStatus(
            collector_state=collector_state,
            error_code=error_code,
            generated_at=current,
            sources=sources,
        )

    def event_page(self, cursor: str | None, limit: int) -> ActionEventPage:
        bounded = min(max(limit, 1), 100)
        with self._connect() as connection:
            boundary = self._event_boundary(connection, cursor) if cursor else None
            query = """SELECT e.*, r.id AS revision_id, r.content_sha256,
                r.first_seen_at AS revision_first_seen_at, r.attempt_id, r.payload_json
                FROM action_collection_events e
                JOIN action_collection_revisions r
                    ON r.event_id=e.id AND r.sequence=e.latest_revision_sequence"""
            parameters: tuple[object, ...]
            if boundary is None:
                query += " ORDER BY e.first_seen_at DESC, e.id DESC LIMIT ?"
                parameters = (bounded + 1,)
            else:
                query += """ WHERE (e.first_seen_at<? OR
                    (e.first_seen_at=? AND e.id<?))
                    ORDER BY e.first_seen_at DESC, e.id DESC LIMIT ?"""
                parameters = (boundary[0], boundary[0], boundary[1], bounded + 1)
            rows = connection.execute(query, parameters).fetchall()
        items = [self._event(row) for row in rows[:bounded]]
        return ActionEventPage(
            items=items,
            next_cursor=items[-1].id if len(rows) > bounded and items else None,
        )

    @staticmethod
    def _event_boundary(connection: sqlite3.Connection, cursor: str) -> tuple[str, str]:
        row = connection.execute(
            "SELECT first_seen_at, id FROM action_collection_events WHERE id=?",
            (cursor,),
        ).fetchone()
        if row is None:
            raise ValueError("Unknown action event cursor.")
        return str(row["first_seen_at"]), str(row["id"])

    def revision_page(self, cursor: str | None, limit: int) -> ActionRevisionPage:
        bounded = min(max(limit, 1), 100)
        with self._connect() as connection:
            boundary = self._revision_boundary(connection, cursor) if cursor else None
            query = """SELECT r.*, e.provider, e.symbol, e.kind, e.provider_key
                FROM action_collection_revisions r
                JOIN action_collection_events e ON e.id=r.event_id"""
            parameters: tuple[object, ...]
            if boundary is None:
                query += " ORDER BY r.first_seen_at DESC, r.id DESC LIMIT ?"
                parameters = (bounded + 1,)
            else:
                query += """ WHERE (r.first_seen_at<? OR
                    (r.first_seen_at=? AND r.id<?))
                    ORDER BY r.first_seen_at DESC, r.id DESC LIMIT ?"""
                parameters = (boundary[0], boundary[0], boundary[1], bounded + 1)
            rows = connection.execute(query, parameters).fetchall()
        items = [self._revision(row) for row in rows[:bounded]]
        return ActionRevisionPage(
            items=items,
            next_cursor=items[-1].id if len(rows) > bounded and items else None,
        )

    @staticmethod
    def _revision_boundary(
        connection: sqlite3.Connection, cursor: str
    ) -> tuple[str, str]:
        row = connection.execute(
            "SELECT first_seen_at, id FROM action_collection_revisions WHERE id=?",
            (cursor,),
        ).fetchone()
        if row is None:
            raise ValueError("Unknown action revision cursor.")
        return str(row["first_seen_at"]), str(row["id"])

    @classmethod
    def _event(cls, row: sqlite3.Row) -> ActionEvent:
        revision = ActionRevision(
            id=row["revision_id"],
            event_id=row["id"],
            provider=row["provider"],
            symbol=row["symbol"],
            kind=row["kind"],
            provider_key=row["provider_key"],
            sequence=row["latest_revision_sequence"],
            content_sha256=row["content_sha256"],
            first_seen_at=row["revision_first_seen_at"],
            attempt_id=row["attempt_id"],
            payload=json.loads(row["payload_json"]),
        )
        return ActionEvent(
            id=row["id"],
            provider=row["provider"],
            symbol=row["symbol"],
            kind=row["kind"],
            provider_key=row["provider_key"],
            vendor_date=row["vendor_date"],
            first_seen_at=row["first_seen_at"],
            last_seen_at=row["last_seen_at"],
            observation_state=row["observation_state"],
            latest_revision_sequence=row["latest_revision_sequence"],
            latest_revision=revision,
        )

    @staticmethod
    def _revision(row: sqlite3.Row) -> ActionRevision:
        return ActionRevision(
            id=row["id"],
            event_id=row["event_id"],
            provider=row["provider"],
            symbol=row["symbol"],
            kind=row["kind"],
            provider_key=row["provider_key"],
            sequence=row["sequence"],
            content_sha256=row["content_sha256"],
            first_seen_at=row["first_seen_at"],
            attempt_id=row["attempt_id"],
            payload=json.loads(row["payload_json"]),
        )

    def raw_attempt(self, attempt_id: str) -> RawActionAttempt:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT * FROM action_collection_attempts
                WHERE id=? AND completed_at IS NOT NULL AND http_status IS NOT NULL
                    AND body_sha256 IS NOT NULL AND body IS NOT NULL""",
                (attempt_id,),
            ).fetchone()
        if row is None:
            raise KeyError(attempt_id)
        body = bytes(row["body"])
        if hashlib.sha256(body).hexdigest() != row["body_sha256"]:
            raise ValueError("Stored action attempt body hash mismatch.")
        return RawActionAttempt(
            id=row["id"],
            symbol=row["symbol"],
            requested_start=row["requested_start"],
            requested_end=row["requested_end"],
            completed_at=row["completed_at"],
            http_status=row["http_status"],
            body_sha256=row["body_sha256"],
            body=body,
        )
