import asyncio
import json
from collections.abc import Callable
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Protocol
from zoneinfo import ZoneInfo

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from jusik.operations_models import Quote, StreamStatus, utc_now
from jusik.research_config import ResearchSettings

KST = ZoneInfo("Asia/Seoul")
APPROVAL_PATH = "/oauth2/Approval"
H0STCNT0_FIELD_COUNT = 46


class _Approval(BaseModel):
    model_config = ConfigDict(extra="ignore")

    approval_key: str = Field(min_length=1)


class PongSender(Protocol):
    async def pong(self, data: str = "") -> object: ...


async def handle_control_message(
    message: str, websocket: PongSender, symbols: list[str]
) -> str | None:
    payload = json.loads(message)
    if not isinstance(payload, dict):
        raise ValueError("Invalid KIS control message.")
    header = payload.get("header")
    body = payload.get("body")
    if not isinstance(header, dict):
        raise ValueError("Invalid KIS control header.")
    if header.get("tr_id") == "PINGPONG":
        await websocket.pong(message)
        return None
    if header.get("tr_id") != "H0STCNT0" or not isinstance(body, dict):
        return None
    if body.get("rt_cd") != "0":
        raise RuntimeError("KIS rejected an H0STCNT0 subscription")
    tr_key = header.get("tr_key")
    if not isinstance(tr_key, str):
        output = body.get("output")
        if isinstance(output, dict):
            tr_key = output.get("tr_key")
    return tr_key if isinstance(tr_key, str) and tr_key in symbols else None


def parse_h0stcnt0_frame(
    frame: str, *, received_at: datetime | None = None
) -> list[Quote]:
    parts = frame.split("|", 3)
    if len(parts) != 4 or parts[0] != "0" or parts[1] != "H0STCNT0":
        return []
    try:
        record_count = int(parts[2])
    except ValueError as exc:
        raise ValueError("Invalid H0STCNT0 record count.") from exc
    if record_count < 1 or record_count > 100:
        raise ValueError("Invalid H0STCNT0 record count.")
    fields = parts[3].split("^")
    if len(fields) != record_count * H0STCNT0_FIELD_COUNT:
        raise ValueError("H0STCNT0 field count does not match its record count.")
    received = received_at or utc_now()
    result: list[Quote] = []
    for index in range(record_count):
        row = fields[index * H0STCNT0_FIELD_COUNT : (index + 1) * H0STCNT0_FIELD_COUNT]
        try:
            market_at = datetime.strptime(f"{row[33]}{row[1]}", "%Y%m%d%H%M%S").replace(
                tzinfo=KST
            )
            quote = Quote(
                symbol=row[0],
                market_at=market_at,
                price=Decimal(row[2]),
                ask=Decimal(row[10]) if Decimal(row[10]) > 0 else None,
                bid=Decimal(row[11]) if Decimal(row[11]) > 0 else None,
                volume=int(row[12]),
                accumulated_volume=int(row[13]),
                received_at=received,
            )
        except (IndexError, ValueError, ValidationError, ArithmeticError):
            raise ValueError("H0STCNT0 record failed schema validation.") from None
        if quote.market_at > received.astimezone(KST) + timedelta(minutes=5):
            raise ValueError("H0STCNT0 market timestamp is unexpectedly in the future.")
        result.append(quote)
    return result


QuoteHandler = Callable[[Quote], None]


class KisReadOnlyStream:
    def __init__(
        self,
        settings: ResearchSettings,
        client: httpx.AsyncClient,
        symbols: Callable[[], list[str]],
        enabled: Callable[[], bool],
        on_quote: QuoteHandler,
        signal_interval_seconds: float = 1.0,
    ) -> None:
        self.settings = settings
        self.client = client
        self._symbols = symbols
        self._enabled = enabled
        self._on_quote = on_quote
        self._task: asyncio.Task[None] | None = None
        self._signal_task: asyncio.Task[None] | None = None
        self._pending_quotes: dict[str, Quote] = {}
        self._signal_event = asyncio.Event()
        self._signal_interval_seconds = signal_interval_seconds
        self._quotes: dict[str, Quote] = {}
        self._state: StreamStatus = StreamStatus(
            state="disabled",
            detail="사용자가 실시간 시세 연결을 켜지 않았습니다.",
            configured=bool(settings.app_key and settings.app_secret),
            symbols=[],
        )

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._supervise())
            self._signal_task = asyncio.create_task(self._signal_loop())

    async def stop(self) -> None:
        if self._task is None and self._signal_task is None:
            return
        tasks = [task for task in (self._task, self._signal_task) if task is not None]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self._task = None
        self._signal_task = None
        self._pending_quotes.clear()
        self._signal_event.clear()

    async def restart(self) -> None:
        await self.stop()
        self.start()

    def quotes(self) -> list[Quote]:
        return sorted(self._quotes.values(), key=lambda item: item.symbol)

    def quote(self, symbol: str) -> Quote | None:
        return self._quotes.get(symbol)

    def status(self) -> StreamStatus:
        result = self._state.model_copy(update={"symbols": self._symbols()})
        if (
            result.state == "connected"
            and result.last_message_at is not None
            and utc_now() - result.last_message_at > timedelta(seconds=30)
        ):
            return result.model_copy(
                update={
                    "state": "stale",
                    "detail": "30초 동안 새 체결 데이터가 없어 제안 체결을 중지합니다.",
                }
            )
        return result

    def _submit_quote(self, quote: Quote) -> None:
        self._pending_quotes[quote.symbol] = quote
        self._signal_event.set()

    async def _signal_loop(self) -> None:
        while True:
            await self._signal_event.wait()
            self._signal_event.clear()
            await asyncio.sleep(self._signal_interval_seconds)
            pending = list(self._pending_quotes.values())
            self._pending_quotes.clear()
            for quote in pending:
                now = utc_now()
                received_at = quote.received_at.astimezone(now.tzinfo)
                market_at = quote.market_at.astimezone(now.tzinfo)
                if (
                    received_at > now + timedelta(seconds=2)
                    or market_at > now + timedelta(seconds=2)
                    or now - received_at > timedelta(seconds=15)
                    or now - market_at > timedelta(seconds=15)
                ):
                    continue
                try:
                    await asyncio.to_thread(self._on_quote, quote)
                except Exception:
                    # A signal calculation failure must not block market-data reads.
                    continue

    async def _approval_key(self) -> str:
        response = await self.client.post(
            APPROVAL_PATH,
            json={
                "grant_type": "client_credentials",
                "appkey": self.settings.app_key.get_secret_value(),
                "secretkey": self.settings.app_secret.get_secret_value(),
            },
        )
        response.raise_for_status()
        return _Approval.model_validate(response.json()).approval_key

    async def _supervise(self) -> None:
        reconnects = 0
        while True:
            if not self._enabled():
                self._quotes.clear()
                self._pending_quotes.clear()
                self._state = self._state.model_copy(
                    update={
                        "state": "disabled",
                        "detail": "사용자가 실시간 시세 연결을 켜지 않았습니다.",
                        "symbols": self._symbols(),
                    }
                )
                await asyncio.sleep(2)
                continue
            self._state = self._state.model_copy(
                update={
                    "state": "connecting",
                    "detail": "KIS 읽기 전용 체결가 스트림에 연결 중입니다.",
                    "symbols": self._symbols(),
                    "reconnect_count": reconnects,
                }
            )
            try:
                await self._connect_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                reconnects += 1
                self._quotes.clear()
                self._pending_quotes.clear()
                self._state = self._state.model_copy(
                    update={
                        "state": "error",
                        "detail": "KIS 시세 연결이 끊어져 재연결을 기다립니다.",
                        "reconnect_count": reconnects,
                    }
                )
                await asyncio.sleep(min(30, 2 ** min(reconnects, 4)))

    async def _connect_once(self) -> None:
        try:
            from websockets.asyncio.client import connect
        except ImportError as exc:
            raise RuntimeError("websockets package is unavailable") from exc
        approval_key = await self._approval_key()
        symbols = self._symbols()
        self._quotes.clear()
        self._pending_quotes.clear()
        async with connect(
            self.settings.websocket_url,
            open_timeout=15,
            ping_interval=20,
            ping_timeout=20,
            max_size=1_000_000,
        ) as websocket:
            for symbol in symbols:
                await websocket.send(
                    json.dumps(
                        {
                            "header": {
                                "approval_key": approval_key,
                                "custtype": "P",
                                "tr_type": "1",
                                "content-type": "utf-8",
                            },
                            "body": {"input": {"tr_id": "H0STCNT0", "tr_key": symbol}},
                        }
                    )
                )
            acknowledged: set[str] = set()
            while len(acknowledged) < len(symbols):
                message = await asyncio.wait_for(websocket.recv(), timeout=10)
                if not isinstance(message, str) or not message.startswith("{"):
                    continue
                tr_key = await handle_control_message(message, websocket, symbols)
                if tr_key is not None:
                    acknowledged.add(tr_key)
            self._state = self._state.model_copy(
                update={
                    "state": "connected",
                    "detail": ("KIS 실시간 체결가를 읽기 전용으로 구독 중입니다."),
                    "connected_at": utc_now(),
                    "symbols": symbols,
                }
            )
            async for message in websocket:
                if not isinstance(message, str):
                    continue
                if message.startswith("{"):
                    tr_key = await handle_control_message(message, websocket, symbols)
                    if tr_key is not None:
                        acknowledged.add(tr_key)
                    continue
                for quote in parse_h0stcnt0_frame(message):
                    if quote.symbol not in acknowledged:
                        continue
                    previous = self._quotes.get(quote.symbol)
                    if previous is not None and quote.market_at < previous.market_at:
                        continue
                    self._quotes[quote.symbol] = quote
                    self._state = self._state.model_copy(
                        update={"last_message_at": quote.received_at}
                    )
                    self._submit_quote(quote)
