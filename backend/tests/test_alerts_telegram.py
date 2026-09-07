import asyncio
from pathlib import Path

import httpx
from pydantic import SecretStr

from jusik.alert_store import AlertStore
from jusik.models import Alert, Holding, InvestmentAdvice
from jusik.telegram import TelegramNotifier


def holding(signal: str) -> Holding:
    return Holding.model_validate(
        {
            "market": "US",
            "symbol": "TEST",
            "name": "Test",
            "currency": "USD",
            "quantity": "1",
            "average_price": "1",
            "current_price": "1",
            "cost": "1",
            "value": "1",
            "profit": "0",
            "return_pct": "0",
            "advice": InvestmentAdvice(
                signal=signal,
                label="매수 검토" if signal == "buy_review" else "판단 보류",
                reasons=["테스트"],
            ),
        }
    )


def test_alert_dedupe_survives_restart_and_insufficient_does_not_reset(
    tmp_path: Path,
) -> None:
    path = tmp_path / "alerts.db"
    first = AlertStore(path)
    assert first.record("one", holding("buy_review")) is not None
    assert first.record("one", holding("buy_review")) is None
    assert first.record("one", holding("insufficient")) is None
    restarted = AlertStore(path)
    assert restarted.record("one", holding("buy_review")) is None
    assert restarted.record("two", holding("buy_review")) is not None
    assert len(restarted.recent()) == 2


def test_telegram_success_reject_rate_limit_and_timeout_have_distinct_status() -> None:
    statuses = iter(
        [
            httpx.Response(200, json={"ok": True}),
            httpx.Response(403, json={"ok": False}),
            httpx.Response(429, json={"ok": False}),
            httpx.ReadTimeout("unknown"),
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/sendMessage")
        assert b"hidden-account" not in request.read()
        value = next(statuses)
        if isinstance(value, Exception):
            raise value
        return value

    async def run() -> list[str]:
        async with httpx.AsyncClient(
            base_url="https://api.telegram.org",
            transport=httpx.MockTransport(handler),
        ) as client:
            notifier = TelegramNotifier(
                client,
                SecretStr("123456789:" + "A" * 35),
                SecretStr("123456789"),
            )
            payload = Alert(
                id=1,
                account_id="hidden-account",
                market="US",
                symbol="TEST",
                name="Test",
                signal="buy_review",
                title="Test 매수 검토 신호",
                message="테스트",
                created_at="2026-09-07T00:00:00Z",
                delivery="in_app",
            )
            return [await notifier.send(payload) for _ in range(4)]

    assert asyncio.run(run()) == [
        "telegram_sent",
        "telegram_failed",
        "telegram_failed",
        "telegram_unknown",
    ]
