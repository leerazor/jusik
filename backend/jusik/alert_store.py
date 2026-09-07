import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from jusik.models import Alert, Holding


class AlertStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS signal_state (
                    position_key TEXT PRIMARY KEY,
                    signal TEXT NOT NULL,
                    rule_version TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id TEXT NOT NULL,
                    market TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    name TEXT NOT NULL,
                    signal TEXT NOT NULL,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    delivery TEXT NOT NULL
                );
                """
            )

    def record(self, account_id: str, holding: Holding) -> Alert | None:
        signal = holding.advice.signal
        if signal == "insufficient":
            return None
        position_key = f"{account_id}:{holding.market}:{holding.symbol}"
        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            previous = connection.execute(
                "SELECT signal, rule_version FROM signal_state WHERE position_key = ?",
                (position_key,),
            ).fetchone()
            changed = previous is None or (
                previous["signal"],
                previous["rule_version"],
            ) != (signal, holding.advice.rule_version)
            connection.execute(
                "INSERT OR REPLACE INTO signal_state VALUES (?, ?, ?, ?)",
                (position_key, signal, holding.advice.rule_version, now),
            )
            if signal not in {"buy_review", "sell_review"} or not changed:
                return None
            title = f"{holding.name} {holding.advice.label} 신호"
            message = " ".join(holding.advice.reasons)
            cursor = connection.execute(
                """INSERT INTO alerts
                (account_id, market, symbol, name, signal, title, message,
                 created_at, delivery)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'in_app')""",
                (
                    account_id,
                    holding.market,
                    holding.symbol,
                    holding.name,
                    signal,
                    title,
                    message,
                    now,
                ),
            )
            if cursor.lastrowid is None:
                raise RuntimeError("Alert insert did not return an id")
            alert_id = cursor.lastrowid
        return Alert(
            id=alert_id,
            account_id=account_id,
            market=holding.market,
            symbol=holding.symbol,
            name=holding.name,
            signal=signal,
            title=title,
            message=message,
            created_at=datetime.fromisoformat(now),
            delivery="in_app",
        )

    def update_delivery(self, alert_id: int, delivery: str) -> None:
        if delivery not in {"telegram_sent", "telegram_failed", "telegram_unknown"}:
            raise ValueError("Invalid delivery status")
        with self._connect() as connection:
            connection.execute(
                "UPDATE alerts SET delivery = ? WHERE id = ?", (delivery, alert_id)
            )

    def recent(self, limit: int = 30) -> list[Alert]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM alerts ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [Alert.model_validate(dict(row)) for row in rows]
