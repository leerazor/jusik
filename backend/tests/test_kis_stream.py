import asyncio
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
import pytest

from jusik.kis_stream import (
    H0STCNT0_FIELD_COUNT,
    KisReadOnlyStream,
    handle_control_message,
    parse_h0stcnt0_frame,
)
from jusik.operations_models import Quote
from jusik.research_config import PAPER_BASE_URL, ResearchSettings


class FakeWebSocket:
    def __init__(self) -> None:
        self.pongs: list[str] = []

    async def pong(self, data: str = "") -> object:
        self.pongs.append(data)
        return None


def row(symbol: str, time_text: str, date_text: str, price: str) -> list[str]:
    fields = ["0"] * H0STCNT0_FIELD_COUNT
    fields[0] = symbol
    fields[1] = time_text
    fields[2] = price
    fields[10] = str(int(price) + 1)
    fields[11] = str(int(price) - 1)
    fields[12] = "3"
    fields[13] = "100"
    fields[33] = date_text
    return fields


def test_h0stcnt0_parses_multiple_records_and_kst_market_time() -> None:
    first = row("005930", "090001", "20260908", "70000")
    second = row("000660", "090002", "20260908", "250000")
    received = datetime(2026, 9, 8, 0, 0, 3, tzinfo=UTC)

    quotes = parse_h0stcnt0_frame(
        f"0|H0STCNT0|2|{'^'.join(first + second)}", received_at=received
    )

    assert [item.symbol for item in quotes] == ["005930", "000660"]
    assert quotes[0].market_at.isoformat() == "2026-09-08T09:00:01+09:00"
    assert quotes[1].received_at == received


def test_h0stcnt0_rejects_missing_negative_and_mismatched_records() -> None:
    valid = row("005930", "090001", "20260908", "70000")
    with pytest.raises(ValueError, match="field count"):
        parse_h0stcnt0_frame(f"0|H0STCNT0|2|{'^'.join(valid)}")
    valid[2] = "-1"
    with pytest.raises(ValueError, match="schema"):
        parse_h0stcnt0_frame(f"0|H0STCNT0|1|{'^'.join(valid)}")
    assert parse_h0stcnt0_frame('{"header":{"tr_id":"PINGPONG"}}') == []


def test_control_messages_pong_acknowledge_and_reject() -> None:
    websocket = FakeWebSocket()
    heartbeat = '{"header":{"tr_id":"PINGPONG"}}'
    assert asyncio.run(handle_control_message(heartbeat, websocket, ["005930"])) is None
    assert websocket.pongs == [heartbeat]
    accepted = '{"header":{"tr_id":"H0STCNT0","tr_key":"005930"},"body":{"rt_cd":"0"}}'
    assert (
        asyncio.run(handle_control_message(accepted, websocket, ["005930"])) == "005930"
    )
    rejected = '{"header":{"tr_id":"H0STCNT0","tr_key":"005930"},"body":{"rt_cd":"1"}}'
    with pytest.raises(RuntimeError, match="rejected"):
        asyncio.run(handle_control_message(rejected, websocket, ["005930"]))


def test_quote_coalescing_keeps_event_loop_responsive_during_slow_signal_work() -> None:
    async def scenario() -> None:
        received: list[Decimal] = []

        def slow_callback(quote: Quote) -> None:
            time.sleep(0.1)
            received.append(quote.price)

        settings = ResearchSettings(
            app_key="key",
            app_secret="secret",
            base_url=PAPER_BASE_URL,
        )
        async with httpx.AsyncClient() as client:
            stream = KisReadOnlyStream(
                settings,
                client,
                lambda: ["005930"],
                lambda: False,
                slow_callback,
                signal_interval_seconds=0.01,
            )
            stream._signal_task = asyncio.create_task(stream._signal_loop())
            now = datetime.now(UTC)
            stream._submit_quote(
                Quote(
                    symbol="005930",
                    price="1",
                    volume=1,
                    accumulated_volume=1,
                    market_at=now,
                    received_at=now,
                )
            )
            await asyncio.sleep(0.03)
            started = asyncio.get_running_loop().time()
            for price in range(2, 101):
                stream._submit_quote(
                    Quote(
                        symbol="005930",
                        price=price,
                        volume=1,
                        accumulated_volume=price,
                        market_at=now,
                        received_at=now,
                    )
                )
            await asyncio.sleep(0)
            elapsed = asyncio.get_running_loop().time() - started
            assert elapsed < 0.05
            await asyncio.sleep(0.25)
            assert received[-1] == Decimal(100)
            assert len(received) <= 2
            await stream.stop()

    asyncio.run(scenario())


def test_signal_worker_discards_stale_market_timestamp() -> None:
    async def scenario() -> None:
        received: list[Quote] = []
        settings = ResearchSettings(
            app_key="key",
            app_secret="secret",
            base_url=PAPER_BASE_URL,
        )
        async with httpx.AsyncClient() as client:
            stream = KisReadOnlyStream(
                settings,
                client,
                lambda: ["005930"],
                lambda: False,
                received.append,
                signal_interval_seconds=0.01,
            )
            stream._signal_task = asyncio.create_task(stream._signal_loop())
            now = datetime.now(UTC)
            stream._submit_quote(
                Quote(
                    symbol="005930",
                    price="70000",
                    volume=1,
                    accumulated_volume=1,
                    market_at=now - timedelta(minutes=1),
                    received_at=now,
                )
            )
            await asyncio.sleep(0.05)
            assert received == []
            await stream.stop()

    asyncio.run(scenario())
