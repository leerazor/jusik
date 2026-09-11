import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
import pytest

import jusik.kis_stream as kis_stream_module
from jusik.kis_stream import (
    H0STCNT0_FIELD_COUNT,
    KisReadOnlyStream,
    _safe_control_message,
    handle_control_message,
    parse_h0stcnt0_frame,
    parse_research_frame,
    research_subscriptions,
)
from jusik.operations_models import Quote
from jusik.research_config import PAPER_BASE_URL, ResearchSettings
from jusik.research_quote_models import ResearchQuote
from jusik.research_universe_data import REGISTRY


class FakeWebSocket:
    def __init__(self) -> None:
        self.pongs: list[str] = []

    async def pong(self, data: str = "") -> object:
        self.pongs.append(data)
        return None


class ScriptedWebSocket(FakeWebSocket):
    def __init__(self, on_send: Callable[[str], Awaitable[None]] | None = None) -> None:
        super().__init__()
        self.incoming: asyncio.Queue[object] = asyncio.Queue()
        self.sent: list[tuple[float, str]] = []
        self.active_receivers = 0
        self.maximum_receivers = 0
        self.on_send = on_send

    async def send(self, message: str) -> object:
        self.sent.append((asyncio.get_running_loop().time(), message))
        if self.on_send is not None:
            await self.on_send(message)
        return None

    async def recv(self) -> object:
        self.active_receivers += 1
        self.maximum_receivers = max(self.maximum_receivers, self.active_receivers)
        try:
            item = await self.incoming.get()
            if isinstance(item, BaseException):
                raise item
            return item
        finally:
            self.active_receivers -= 1


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


def accepted_ack(tr_id: str, tr_key: str) -> str:
    return json.dumps(
        {
            "header": {"tr_id": tr_id, "tr_key": tr_key, "encrypt": "N"},
            "body": {"rt_cd": "0"},
        }
    )


def us_row(symbol: str, at: datetime, price: str = "150.25") -> list[str]:
    local = at.astimezone(kis_stream_module.NEW_YORK)
    fields = ["0"] * 25
    fields[0] = symbol
    fields[3] = local.strftime("%Y%m%d")
    fields[4] = local.strftime("%H%M%S")
    fields[10] = price
    fields[14] = "150.20"
    fields[15] = "150.30"
    fields[18] = "7"
    fields[19] = "100"
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


def test_research_parsers_accept_documented_domestic_and_us_variants() -> None:
    domestic = row("0173Y0", "090001", "20260908", "12000")
    received = datetime(2026, 9, 8, 13, 30, 2, tzinfo=UTC)
    subscriptions = research_subscriptions(REGISTRY)
    quote = parse_research_frame(
        f"1|H0STCNT0|1|{'^'.join(domestic)}",
        subscriptions,
        received_at=received,
    )[0]
    assert quote.symbol == "0173Y0"
    assert quote.currency == "KRW"

    modern = ["0"] * 25
    modern[0] = "NVDA"
    modern[3] = "20260908"
    modern[4] = "093001"
    modern[10] = "150.25"
    modern[14] = "150.20"
    modern[15] = "150.30"
    modern[18] = "7"
    modern[19] = "100"
    modern_quote = parse_research_frame(
        f"0|HDFSCNT0|1|{'^'.join(modern)}",
        subscriptions,
        received_at=received,
    )[0]
    legacy_quote = parse_research_frame(
        f"1|HDFSCNT0|1|{'^'.join(['DNASNVDA', *modern])}",
        subscriptions,
        received_at=received,
    )[0]
    assert modern_quote.symbol == legacy_quote.symbol == "NVDA"
    assert legacy_quote.realtime_code == "DNASNVDA"
    with pytest.raises(ValueError, match="schema validation"):
        parse_research_frame(
            f"0|HDFSCNT0|1|{'^'.join(['DNYSNVDA', *modern])}",
            subscriptions,
            received_at=received,
        )
    future = row("0173Y0", "235959", "20260909", "12000")
    with pytest.raises(ValueError, match="future"):
        parse_research_frame(
            f"0|H0STCNT0|1|{'^'.join(future)}",
            subscriptions,
            received_at=received,
        )


def test_research_subscription_exchange_mapping_and_encrypted_ack_rejection() -> None:
    mapped = {item.symbol: item for item in research_subscriptions(REGISTRY)}
    assert mapped["NVDA"].tr_key == "DNASNVDA"
    assert mapped["COHR"].tr_key == "DNYSCOHR"
    assert mapped["SOXL"].tr_key == "DAMSSOXL"

    async def scenario() -> None:
        websocket = FakeWebSocket()
        encrypted = (
            '{"header":{"tr_id":"H0STCNT0","tr_key":"005930",'
            '"encrypt":"Y"},"body":{"rt_cd":"0","output":'
            '{"key":"must-not-be-retained","iv":"must-not-be-retained"}}}'
        )
        with pytest.raises(RuntimeError, match="rejected"):
            await handle_control_message(encrypted, websocket, ["005930"])

    asyncio.run(scenario())


def test_paced_sender_and_single_receiver_process_interleaved_protocol(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(kis_stream_module, "SUBSCRIPTION_INTERVAL_SECONDS", 0.001)
    settings = ResearchSettings(
        app_key="key", app_secret="secret", base_url=PAPER_BASE_URL
    )

    async def scenario() -> None:
        subscriptions = research_subscriptions(REGISTRY)
        mapping = {(item.tr_id, item.tr_key): item for item in subscriptions}
        now = datetime.now(UTC)
        socket: ScriptedWebSocket

        async def stop_later() -> None:
            await asyncio.sleep(0.01)
            await socket.incoming.put(RuntimeError("scripted receiver closed"))

        async def on_send(message: str) -> None:
            payload = json.loads(message)
            item = payload["body"]["input"]
            await socket.incoming.put(accepted_ack(item["tr_id"], item["tr_key"]))
            if len(socket.sent) == 1:
                await socket.incoming.put('{"header":{"tr_id":"PINGPONG"}}')
                local = now.astimezone(kis_stream_module.KST)
                domestic = row(
                    "005930",
                    local.strftime("%H%M%S"),
                    local.strftime("%Y%m%d"),
                    "70000",
                )
                await socket.incoming.put(f"0|H0STCNT0|1|{'^'.join(domestic)}")
                # Yield so an ACK can be observed before send() returns.
                await asyncio.sleep(0.002)
            if len(socket.sent) == len(subscriptions):
                modern = us_row("NVDA", now)
                await socket.incoming.put(f"0|HDFSCNT0|1|{'^'.join(modern)}")
                await socket.incoming.put(
                    f"1|HDFSCNT0|1|{'^'.join(['DNASNVDA', *modern])}"
                )
                await socket.incoming.put("0|HDFSCNT0|1|SECRET_SENTINEL_MALFORMED")
                asyncio.create_task(stop_later())

        socket = ScriptedWebSocket(on_send)
        async with httpx.AsyncClient() as client:
            stream = KisReadOnlyStream(
                settings,
                client,
                lambda: [],
                lambda: False,
                lambda _quote: None,
                research_instruments=lambda: REGISTRY,
                forward_enabled=lambda: True,
            )
            stream._reset_subscription_attempt(mapping, subscriptions)
            with pytest.raises(RuntimeError, match="scripted receiver closed"):
                await stream._run_connection(socket, "SECRET_SENTINEL", mapping, [])
            assert len(socket.sent) == 16
            assert (
                len(
                    {
                        (
                            json.loads(message)["body"]["input"]["tr_id"],
                            json.loads(message)["body"]["input"]["tr_key"],
                        )
                        for _sent_at, message in socket.sent
                    }
                )
                == 16
            )
            intervals = [
                later[0] - earlier[0]
                for earlier, later in zip(socket.sent, socket.sent[1:], strict=False)
            ]
            assert min(intervals) >= 0.0008
            assert socket.maximum_receivers == 1
            assert socket.active_receivers == 0
            assert socket.pongs
            status = stream.research_status()
            by_symbol = {item.symbol: item for item in status.items}
            assert by_symbol["005930"].subscription_phase == "approved"
            assert by_symbol["005930"].requested_at is not None
            assert by_symbol["005930"].sent_at is not None
            assert by_symbol["005930"].acknowledged_at is not None
            assert (
                by_symbol["005930"].requested_at
                <= by_symbol["005930"].sent_at
                <= by_symbol["005930"].acknowledged_at
            )
            assert by_symbol["005930"].first_quote_at is not None
            assert by_symbol["NVDA"].first_quote_at is not None
            counters = {item.tr_id: item for item in status.protocol_counters}
            assert counters["H0STCNT0"].data_frame_count == 1
            assert counters["H0STCNT0"].valid_quote_count == 1
            assert counters["HDFSCNT0"].data_frame_count == 3
            assert counters["HDFSCNT0"].valid_quote_count == 2
            assert counters["HDFSCNT0"].parse_failure_count == 1
            assert "SECRET_SENTINEL" not in status.model_dump_json()

    asyncio.run(scenario())


def test_reconnect_resets_current_attempt_quotes_timestamps_and_counters() -> None:
    settings = ResearchSettings(
        app_key="key", app_secret="secret", base_url=PAPER_BASE_URL
    )

    async def scenario() -> None:
        subscriptions = research_subscriptions(REGISTRY)
        mapping = {(item.tr_id, item.tr_key): item for item in subscriptions}
        async with httpx.AsyncClient() as client:
            stream = KisReadOnlyStream(
                settings,
                client,
                lambda: [],
                lambda: False,
                lambda _quote: None,
                research_instruments=lambda: REGISTRY,
                forward_enabled=lambda: True,
            )
            stream._reset_subscription_attempt(mapping, subscriptions)
            key = (subscriptions[0].tr_id, subscriptions[0].tr_key)
            evidence = stream._subscription_evidence[key]
            evidence.phase = "approved"
            evidence.acknowledged_at = datetime.now(UTC)
            evidence.first_quote_at = datetime.now(UTC)
            stream._research_quotes[subscriptions[0].symbol] = ResearchQuote(
                symbol=subscriptions[0].symbol,
                exchange=subscriptions[0].exchange,
                currency=subscriptions[0].currency,
                price="1",
                volume=0,
                accumulated_volume=0,
                market_at=datetime.now(UTC),
                received_at=datetime.now(UTC),
                source="KIS H0STCNT0",
            )
            stream._increment_protocol_counter("H0STCNT0", "data_frame_count")

            stream._reset_subscription_attempt(mapping, subscriptions)
            status = stream.research_status()
            assert status.items[0].subscription_phase == "queued"
            assert status.items[0].acknowledged_at is None
            assert status.items[0].first_quote_at is None
            assert status.items[0].last_received_at is None
            assert all(
                counter.data_frame_count == 0
                and counter.valid_quote_count == 0
                and counter.parse_failure_count == 0
                for counter in status.protocol_counters
            )

    asyncio.run(scenario())


def test_supervisor_disconnect_invalidates_current_research_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = ResearchSettings(
        app_key="key", app_secret="secret", base_url=PAPER_BASE_URL
    )

    async def scenario() -> None:
        subscriptions = research_subscriptions(REGISTRY)
        mapping = {(item.tr_id, item.tr_key): item for item in subscriptions}
        async with httpx.AsyncClient() as client:
            stream = KisReadOnlyStream(
                settings,
                client,
                lambda: [],
                lambda: False,
                lambda _quote: None,
                research_instruments=lambda: REGISTRY,
                forward_enabled=lambda: True,
            )

            async def fail_after_current_attempt() -> None:
                stream._reset_subscription_attempt(mapping, subscriptions)
                key = (subscriptions[0].tr_id, subscriptions[0].tr_key)
                evidence = stream._subscription_evidence[key]
                evidence.phase = "approved"
                evidence.sent_at = datetime.now(UTC)
                evidence.acknowledged_at = datetime.now(UTC)
                evidence.first_quote_at = datetime.now(UTC)
                stream._subscription_states[key] = ("connected", "approved")
                stream._research_quotes[subscriptions[0].symbol] = ResearchQuote(
                    symbol=subscriptions[0].symbol,
                    exchange=subscriptions[0].exchange,
                    currency=subscriptions[0].currency,
                    price="1",
                    volume=0,
                    accumulated_volume=0,
                    market_at=datetime.now(UTC),
                    received_at=datetime.now(UTC),
                    source="KIS H0STCNT0",
                )
                stream._increment_protocol_counter("H0STCNT0", "data_frame_count")
                raise RuntimeError("SECRET_RECEIVER_FAILURE")

            monkeypatch.setattr(stream, "_connect_once", fail_after_current_attempt)
            task = asyncio.create_task(stream._supervise())
            for _ in range(100):
                if stream._state.state == "error":
                    break
                await asyncio.sleep(0.001)
            status = stream.research_status()
            assert status.state == "error"
            assert status.connected_at is None
            assert all(item.subscription_phase == "queued" for item in status.items)
            assert all(
                item.sent_at is None
                and item.acknowledged_at is None
                and item.first_quote_at is None
                and item.last_received_at is None
                for item in status.items
            )
            assert all(
                counter.data_frame_count == 0 for counter in status.protocol_counters
            )
            assert "SECRET_RECEIVER_FAILURE" not in status.model_dump_json()
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(scenario())


def test_partial_and_late_ack_stays_on_same_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(kis_stream_module, "SUBSCRIPTION_INTERVAL_SECONDS", 0.001)
    monkeypatch.setattr(kis_stream_module, "ACKNOWLEDGEMENT_TIMEOUT_SECONDS", 0.01)
    settings = ResearchSettings(
        app_key="key", app_secret="secret", base_url=PAPER_BASE_URL
    )

    async def scenario() -> None:
        subscriptions = research_subscriptions(REGISTRY)[:2]
        mapping = {(item.tr_id, item.tr_key): item for item in subscriptions}
        socket = ScriptedWebSocket()
        await socket.incoming.put(
            accepted_ack(subscriptions[0].tr_id, subscriptions[0].tr_key)
        )
        async with httpx.AsyncClient() as client:
            stream = KisReadOnlyStream(
                settings,
                client,
                lambda: [],
                lambda: False,
                lambda _quote: None,
                research_instruments=lambda: REGISTRY[:2],
                forward_enabled=lambda: True,
            )
            stream._reset_subscription_attempt(mapping, subscriptions)
            task = asyncio.create_task(
                stream._run_connection(socket, "approval", mapping, [])
            )
            await asyncio.sleep(0.03)
            assert not task.done()
            second_key = (subscriptions[1].tr_id, subscriptions[1].tr_key)
            evidence = stream._subscription_evidence[second_key]
            assert evidence.sent_at is not None
            evidence.sent_at -= timedelta(seconds=11)
            assert stream.research_status().items[1].ack_overdue
            await socket.incoming.put(
                accepted_ack(subscriptions[1].tr_id, subscriptions[1].tr_key)
            )
            await asyncio.sleep(0.01)
            assert stream.research_status().items[1].subscription_phase == "approved"
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            assert socket.active_receivers == 0

    asyncio.run(scenario())


def test_ack_and_data_for_unsent_subscription_are_ignored_until_real_send(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(kis_stream_module, "SUBSCRIPTION_INTERVAL_SECONDS", 0.001)
    settings = ResearchSettings(
        app_key="key", app_secret="secret", base_url=PAPER_BASE_URL
    )

    async def scenario() -> None:
        subscriptions = research_subscriptions(REGISTRY)[:2]
        mapping = {(item.tr_id, item.tr_key): item for item in subscriptions}
        now = datetime.now(UTC)
        second = subscriptions[1]
        socket: ScriptedWebSocket
        stream: KisReadOnlyStream

        async def close_later() -> None:
            await asyncio.sleep(0.01)
            await socket.incoming.put(RuntimeError("done"))

        async def on_send(_message: str) -> None:
            if len(socket.sent) == 1:
                await socket.incoming.put(accepted_ack(second.tr_id, second.tr_key))
                local = now.astimezone(kis_stream_module.KST)
                early = row(
                    second.symbol,
                    local.strftime("%H%M%S"),
                    local.strftime("%Y%m%d"),
                    "250000",
                )
                await socket.incoming.put(f"0|H0STCNT0|1|{'^'.join(early)}")
                await socket.incoming.put(
                    accepted_ack(subscriptions[0].tr_id, subscriptions[0].tr_key)
                )
                await asyncio.sleep(0.005)
                assert second.symbol not in stream._research_quotes
            else:
                await socket.incoming.put(accepted_ack(second.tr_id, second.tr_key))
                local = (now + timedelta(seconds=1)).astimezone(kis_stream_module.KST)
                valid = row(
                    second.symbol,
                    local.strftime("%H%M%S"),
                    local.strftime("%Y%m%d"),
                    "250001",
                )
                await socket.incoming.put(f"0|H0STCNT0|1|{'^'.join(valid)}")
                asyncio.create_task(close_later())

        socket = ScriptedWebSocket(on_send)
        async with httpx.AsyncClient() as client:
            stream = KisReadOnlyStream(
                settings,
                client,
                lambda: [],
                lambda: False,
                lambda _quote: None,
                research_instruments=lambda: REGISTRY[:2],
                forward_enabled=lambda: True,
            )
            stream._reset_subscription_attempt(mapping, subscriptions)
            with pytest.raises(RuntimeError, match="done"):
                await stream._run_connection(socket, "approval", mapping, [])
            item = stream.research_status().items[1]
            assert item.subscription_phase == "approved"
            assert item.sent_at is not None
            assert item.acknowledged_at is not None
            assert item.sent_at <= item.acknowledged_at
            assert item.first_quote_at is not None
            assert stream.research_quote(second.symbol) is not None

    asyncio.run(scenario())


def test_no_ack_guard_and_sender_failure_cancel_peer_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(kis_stream_module, "SUBSCRIPTION_INTERVAL_SECONDS", 0.001)
    monkeypatch.setattr(kis_stream_module, "ACKNOWLEDGEMENT_TIMEOUT_SECONDS", 0.01)
    settings = ResearchSettings(
        app_key="key", app_secret="secret", base_url=PAPER_BASE_URL
    )

    async def scenario() -> None:
        subscriptions = research_subscriptions(REGISTRY)[:2]
        mapping = {(item.tr_id, item.tr_key): item for item in subscriptions}
        no_ack = ScriptedWebSocket()

        async def spam_frames() -> None:
            for _ in range(100):
                await no_ack.incoming.put("0|H0STCNT0|1|malformed")
                await asyncio.sleep(0)

        spammer = asyncio.create_task(spam_frames())
        async with httpx.AsyncClient() as client:
            stream = KisReadOnlyStream(
                settings,
                client,
                lambda: [],
                lambda: False,
                lambda _quote: None,
                research_instruments=lambda: REGISTRY[:2],
                forward_enabled=lambda: True,
            )
            stream._reset_subscription_attempt(mapping, subscriptions)
            with pytest.raises(RuntimeError, match="did not acknowledge"):
                await stream._run_connection(no_ack, "approval", mapping, [])
            await spammer
            assert no_ack.active_receivers == 0

            async def fail_second_send(_message: str) -> None:
                if len(failed.sent) == 2:
                    raise RuntimeError("send failed")

            failed = ScriptedWebSocket(fail_second_send)
            stream._reset_subscription_attempt(mapping, subscriptions)
            with pytest.raises(RuntimeError, match="send failed"):
                await stream._run_connection(failed, "approval", mapping, [])
            assert failed.active_receivers == 0

    asyncio.run(scenario())


def test_malformed_control_is_quarantined_without_exposing_payload() -> None:
    async def scenario() -> None:
        websocket = FakeWebSocket()
        assert await _safe_control_message("{malformed", websocket) is None
        assert await _safe_control_message('{"header":[]}', websocket) is None

    asyncio.run(scenario())


def test_all_approved_but_unobserved_research_feeds_are_not_connected() -> None:
    settings = ResearchSettings(
        app_key="key", app_secret="secret", base_url=PAPER_BASE_URL
    )

    async def scenario() -> None:
        async with httpx.AsyncClient() as client:
            stream = KisReadOnlyStream(
                settings,
                client,
                lambda: [],
                lambda: False,
                lambda _quote: None,
                research_instruments=lambda: REGISTRY,
                forward_enabled=lambda: True,
            )
            for item in research_subscriptions(REGISTRY):
                stream._subscription_states[(item.tr_id, item.tr_key)] = (
                    "connected",
                    "approved",
                )
            assert stream.research_status().state == "connecting"
            assert all(
                item.state == "pending" for item in stream.research_status().items
            )
            assert all(
                item.subscription_phase == "approved"
                and item.detail
                == "구독 승인은 확인됐고 첫 실제 체결 데이터를 기다립니다."
                for item in stream.research_status().items
            )

    asyncio.run(scenario())


def test_all_observed_but_old_research_feeds_report_stale() -> None:
    settings = ResearchSettings(
        app_key="key", app_secret="secret", base_url=PAPER_BASE_URL
    )

    async def scenario() -> None:
        async with httpx.AsyncClient() as client:
            stream = KisReadOnlyStream(
                settings,
                client,
                lambda: [],
                lambda: False,
                lambda _quote: None,
                research_instruments=lambda: REGISTRY,
                forward_enabled=lambda: True,
            )
            old = datetime.now(UTC) - timedelta(minutes=1)
            for item in research_subscriptions(REGISTRY):
                stream._subscription_states[(item.tr_id, item.tr_key)] = (
                    "connected",
                    "approved",
                )
                stream._research_quotes[item.symbol] = ResearchQuote(
                    symbol=item.symbol,
                    exchange=item.exchange,
                    currency=item.currency,
                    price="1",
                    volume=0,
                    accumulated_volume=0,
                    market_at=old,
                    received_at=old,
                    source=(
                        "KIS H0STCNT0" if item.currency == "KRW" else "KIS HDFSCNT0"
                    ),
                )
            assert stream.research_status().state == "stale"

    asyncio.run(scenario())


def test_forward_only_never_dispatches_legacy_operations_callback() -> None:
    async def scenario() -> None:
        legacy: list[Quote] = []
        research: list[str] = []
        settings = ResearchSettings(
            app_key="key", app_secret="secret", base_url=PAPER_BASE_URL
        )
        async with httpx.AsyncClient() as client:
            stream = KisReadOnlyStream(
                settings,
                client,
                lambda: ["005930"],
                lambda: False,
                legacy.append,
                signal_interval_seconds=0.01,
                research_instruments=lambda: REGISTRY,
                forward_enabled=lambda: True,
                on_research_quote=lambda quote: research.append(quote.symbol),
            )
            stream._signal_task = asyncio.create_task(stream._signal_loop())
            now = datetime.now(UTC)
            stream._submit_quote(
                Quote(
                    symbol="005930",
                    price="70000",
                    volume=1,
                    accumulated_volume=1,
                    market_at=now,
                    received_at=now,
                ),
                require_enabled=True,
            )
            await asyncio.sleep(0.05)
            assert legacy == []
            assert research == []
            await stream.stop()

    asyncio.run(scenario())
