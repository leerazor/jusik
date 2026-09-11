from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal, Protocol, cast
from zoneinfo import ZoneInfo

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from jusik.operations_models import Quote, StreamStatus, utc_now
from jusik.research_config import ResearchSettings
from jusik.research_quote_models import (
    ResearchFeedItem,
    ResearchFeedStatus,
    ResearchProtocolCounter,
    ResearchQuote,
    ResearchSubscription,
)
from jusik.research_universe_models import ResearchInstrument

KST = ZoneInfo("Asia/Seoul")
NEW_YORK = ZoneInfo("America/New_York")
APPROVAL_PATH = "/oauth2/Approval"
H0STCNT0_FIELD_COUNT = 46
HDFSCNT0_MODERN_FIELD_COUNT = 25
HDFSCNT0_LEGACY_FIELD_COUNT = 26
ALLOWED_RESEARCH_TR_IDS = frozenset({"H0STCNT0", "HDFSCNT0"})
SUBSCRIPTION_INTERVAL_SECONDS = 0.5
ACKNOWLEDGEMENT_TIMEOUT_SECONDS = 10.0
US_EXCHANGE: dict[str, Literal["NAS", "NYS", "AMS"]] = {
    "NMS": "NAS",
    "NGM": "NAS",
    "NYQ": "NYS",
    "PCX": "AMS",
}


class _Approval(BaseModel):
    model_config = ConfigDict(extra="ignore")
    approval_key: str = Field(min_length=1)


class PongSender(Protocol):
    async def pong(self, data: str = "") -> object: ...


class ReadOnlySocket(PongSender, Protocol):
    async def send(self, message: str) -> object: ...

    async def recv(self) -> object: ...


@dataclass
class _SubscriptionEvidence:
    phase: Literal["queued", "awaiting_ack", "approved", "rejected"]
    requested_at: datetime
    sent_at: datetime | None = None
    acknowledged_at: datetime | None = None
    first_quote_at: datetime | None = None


class _ControlResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    tr_id: str
    tr_key: str
    accepted: bool
    error_code: str | None = None


def research_subscriptions(
    instruments: Sequence[ResearchInstrument],
) -> list[ResearchSubscription]:
    result: list[ResearchSubscription] = []
    seen: set[tuple[str, str]] = set()
    for instrument in instruments:
        if instrument.currency == "KRW":
            item = ResearchSubscription(
                symbol=instrument.symbol,
                exchange="KRX",
                currency="KRW",
                tr_id="H0STCNT0",
                tr_key=instrument.symbol,
            )
        else:
            exchange = US_EXCHANGE[instrument.exchange]
            item = ResearchSubscription(
                symbol=instrument.symbol,
                exchange=exchange,
                currency="USD",
                tr_id="HDFSCNT0",
                tr_key=f"D{exchange}{instrument.symbol}",
            )
        key = (item.tr_id, item.tr_key)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


async def _parse_control_message(
    message: str, websocket: PongSender
) -> _ControlResult | None:
    payload = json.loads(message)
    if not isinstance(payload, dict):
        raise ValueError("Invalid KIS control message.")
    header = payload.get("header")
    body = payload.get("body")
    if not isinstance(header, dict):
        raise ValueError("Invalid KIS control header.")
    tr_id = header.get("tr_id")
    if tr_id == "PINGPONG":
        await websocket.pong(message)
        return None
    if tr_id not in ALLOWED_RESEARCH_TR_IDS or not isinstance(body, dict):
        return None
    tr_key = header.get("tr_key")
    output = body.get("output")
    if not isinstance(tr_key, str) and isinstance(output, dict):
        tr_key = output.get("tr_key")
    if not isinstance(tr_key, str):
        return None
    plaintext = header.get("encrypt") in (None, "", "0", "N")
    accepted = body.get("rt_cd") == "0" and plaintext
    code = (
        None
        if accepted
        else (
            "encrypted_payload_rejected"
            if not plaintext
            else str(body.get("rt_cd") or "rejected")[:40]
        )
    )
    return _ControlResult(
        tr_id=tr_id, tr_key=tr_key, accepted=accepted, error_code=code
    )


async def _safe_control_message(
    message: str, websocket: PongSender
) -> _ControlResult | None:
    try:
        return await _parse_control_message(message, websocket)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


async def handle_control_message(
    message: str, websocket: PongSender, symbols: list[str]
) -> str | None:
    """Compatibility wrapper for the domestic operations stream."""
    result = await _parse_control_message(message, websocket)
    if result is None or result.tr_id != "H0STCNT0":
        return None
    if not result.accepted:
        raise RuntimeError("KIS rejected an H0STCNT0 subscription")
    return result.tr_key if result.tr_key in symbols else None


def _record_count(parts: list[str], tr_id: str) -> int:
    try:
        count = int(parts[2])
    except ValueError as exc:
        raise ValueError(f"Invalid {tr_id} record count.") from exc
    if count < 1 or count > 100:
        raise ValueError(f"Invalid {tr_id} record count.")
    return count


def parse_h0stcnt0_frame(
    frame: str, *, received_at: datetime | None = None
) -> list[Quote]:
    parts = frame.split("|", 3)
    if len(parts) != 4 or parts[0] not in {"0", "1"} or parts[1] != "H0STCNT0":
        return []
    count = _record_count(parts, "H0STCNT0")
    fields = parts[3].split("^")
    if len(fields) != count * H0STCNT0_FIELD_COUNT:
        raise ValueError("H0STCNT0 field count does not match its record count.")
    received = received_at or utc_now()
    result: list[Quote] = []
    for index in range(count):
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


def parse_research_frame(
    frame: str,
    subscriptions: Sequence[ResearchSubscription],
    *,
    received_at: datetime | None = None,
) -> list[ResearchQuote]:
    parts = frame.split("|", 3)
    if (
        len(parts) != 4
        or parts[0] not in {"0", "1"}
        or parts[1] not in ALLOWED_RESEARCH_TR_IDS
    ):
        return []
    received = received_at or utc_now()
    tr_id = parts[1]
    by_symbol = {item.symbol: item for item in subscriptions if item.tr_id == tr_id}
    if tr_id == "H0STCNT0":
        count = _record_count(parts, "H0STCNT0")
        fields = parts[3].split("^")
        if len(fields) != count * H0STCNT0_FIELD_COUNT:
            raise ValueError("H0STCNT0 field count does not match its record count.")
        result: list[ResearchQuote] = []
        for index in range(count):
            row = fields[
                index * H0STCNT0_FIELD_COUNT : (index + 1) * H0STCNT0_FIELD_COUNT
            ]
            subscription = by_symbol.get(row[0])
            if subscription is None:
                continue
            try:
                market_at = datetime.strptime(
                    f"{row[33]}{row[1]}", "%Y%m%d%H%M%S"
                ).replace(tzinfo=KST)
                result.append(
                    ResearchQuote(
                        symbol=row[0],
                        exchange="KRX",
                        currency="KRW",
                        price=Decimal(row[2]),
                        ask=Decimal(row[10]) if Decimal(row[10]) > 0 else None,
                        bid=Decimal(row[11]) if Decimal(row[11]) > 0 else None,
                        volume=int(row[12]),
                        accumulated_volume=int(row[13]),
                        market_at=market_at,
                        received_at=received,
                        source="KIS H0STCNT0",
                    )
                )
            except (IndexError, ValueError, ValidationError, ArithmeticError):
                raise ValueError("H0STCNT0 record failed schema validation.") from None
            if result[-1].market_at > received.astimezone(KST) + timedelta(minutes=5):
                raise ValueError(
                    "H0STCNT0 market timestamp is unexpectedly in the future."
                )
        return result
    count = _record_count(parts, "HDFSCNT0")
    fields = parts[3].split("^")
    if len(fields) not in {
        count * HDFSCNT0_MODERN_FIELD_COUNT,
        count * HDFSCNT0_LEGACY_FIELD_COUNT,
    }:
        raise ValueError("HDFSCNT0 field count does not match a documented schema.")
    stride = len(fields) // count
    result = []
    for index in range(count):
        original = fields[index * stride : (index + 1) * stride]
        realtime_code = original[0] if stride == HDFSCNT0_LEGACY_FIELD_COUNT else None
        row = original[1:] if realtime_code is not None else original
        try:
            subscription = by_symbol[row[0]]
            if realtime_code is not None and realtime_code != subscription.tr_key:
                raise ValueError("HDFSCNT0 realtime code and ticker disagree.")
            market_at = datetime.strptime(f"{row[3]}{row[4]}", "%Y%m%d%H%M%S").replace(
                tzinfo=NEW_YORK
            )
            quote = ResearchQuote(
                symbol=row[0],
                exchange=subscription.exchange,
                currency="USD",
                price=Decimal(row[10]),
                bid=Decimal(row[14]) if Decimal(row[14]) > 0 else None,
                ask=Decimal(row[15]) if Decimal(row[15]) > 0 else None,
                volume=int(Decimal(row[18])),
                accumulated_volume=int(Decimal(row[19])),
                market_at=market_at,
                received_at=received,
                source="KIS HDFSCNT0",
                realtime_code=realtime_code,
            )
        except (KeyError, IndexError, ValueError, ValidationError, ArithmeticError):
            raise ValueError("HDFSCNT0 record failed schema validation.") from None
        if quote.market_at > received.astimezone(NEW_YORK) + timedelta(minutes=5):
            raise ValueError("HDFSCNT0 market timestamp is unexpectedly in the future.")
        result.append(quote)
    return result


QuoteHandler = Callable[[Quote], None]
ResearchQuoteHandler = Callable[[ResearchQuote], None]


class KisReadOnlyStream:
    def __init__(
        self,
        settings: ResearchSettings,
        client: httpx.AsyncClient,
        symbols: Callable[[], list[str]],
        enabled: Callable[[], bool],
        on_quote: QuoteHandler,
        signal_interval_seconds: float = 1.0,
        *,
        research_instruments: Callable[[], Sequence[ResearchInstrument]] | None = None,
        forward_enabled: Callable[[], bool] | None = None,
        on_research_quote: ResearchQuoteHandler | None = None,
    ) -> None:
        self.settings = settings
        self.client = client
        self._symbols = symbols
        self._enabled = enabled
        self._on_quote = on_quote
        self._research_instruments = research_instruments or (lambda: ())
        self._forward_enabled = forward_enabled or (lambda: False)
        self._on_research_quote = on_research_quote
        self._task: asyncio.Task[None] | None = None
        self._signal_task: asyncio.Task[None] | None = None
        self._pending_quotes: dict[str, Quote] = {}
        self._operations_requires_enabled: set[str] = set()
        self._pending_research_quotes: dict[str, ResearchQuote] = {}
        self._signal_event = asyncio.Event()
        self._signal_interval_seconds = signal_interval_seconds
        self._quotes: dict[str, Quote] = {}
        self._research_quotes: dict[str, ResearchQuote] = {}
        self._subscription_states: dict[tuple[str, str], tuple[str, str]] = {}
        self._subscription_evidence: dict[tuple[str, str], _SubscriptionEvidence] = {}
        self._research_subscription_keys: set[tuple[str, str]] = set()
        self._protocol_counters: dict[str, dict[str, int]] = {}
        self._research_connected_at: datetime | None = None
        self._reconnect_count = 0
        self._state = StreamStatus(
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
        tasks = [task for task in (self._task, self._signal_task) if task is not None]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._task = None
        self._signal_task = None
        self._pending_quotes.clear()
        self._operations_requires_enabled.clear()
        self._pending_research_quotes.clear()
        self._signal_event.clear()
        self._invalidate_research_attempt()

    async def restart(self) -> None:
        await self.stop()
        self.start()

    def quotes(self) -> list[Quote]:
        return sorted(self._quotes.values(), key=lambda item: item.symbol)

    def quote(self, symbol: str) -> Quote | None:
        return self._quotes.get(symbol)

    def research_quotes(self) -> list[ResearchQuote]:
        return sorted(self._research_quotes.values(), key=lambda item: item.symbol)

    def research_quote(self, symbol: str) -> ResearchQuote | None:
        return self._research_quotes.get(symbol)

    def status(self) -> StreamStatus:
        if not self._enabled():
            return StreamStatus(
                state="disabled",
                detail="사용자가 운영 시세 연결을 켜지 않았습니다.",
                configured=bool(self.settings.app_key and self.settings.app_secret),
                symbols=self._symbols(),
                reconnect_count=self._reconnect_count,
            )
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

    def research_status(self) -> ResearchFeedStatus:
        now = utc_now()
        items: list[ResearchFeedItem] = []
        for subscription in research_subscriptions(self._research_instruments()):
            key = (subscription.tr_id, subscription.tr_key)
            raw_state, stored_detail = self._subscription_states.get(
                (subscription.tr_id, subscription.tr_key),
                ("pending", "구독 승인을 기다립니다."),
            )
            evidence = self._subscription_evidence.get(key)
            phase = (
                evidence.phase
                if evidence is not None
                else (
                    "approved"
                    if raw_state == "connected"
                    else "rejected"
                    if raw_state == "rejected"
                    else "queued"
                )
            )
            ack_overdue = bool(
                evidence is not None
                and phase == "awaiting_ack"
                and evidence.sent_at is not None
                and now - evidence.sent_at > timedelta(seconds=10)
            )
            quote = (
                self._research_quotes.get(subscription.symbol)
                if evidence is None or evidence.first_quote_at is not None
                else None
            )
            if raw_state == "unsupported":
                state, detail = "unsupported", stored_detail
            elif phase == "rejected":
                state, detail = "rejected", "읽기 전용 구독이 거부되었습니다."
            elif phase == "queued":
                state, detail = "pending", "읽기 전용 구독 전송을 기다립니다."
            elif phase == "awaiting_ack":
                state, detail = (
                    "pending",
                    "구독 승인 확인이 10초 넘게 지연되고 있습니다."
                    if ack_overdue
                    else "구독 승인 응답을 기다립니다.",
                )
            elif quote is None:
                state, detail = (
                    "pending",
                    "구독 승인은 확인됐고 첫 실제 체결 데이터를 기다립니다.",
                )
            elif now - quote.received_at.astimezone(UTC) > timedelta(seconds=30):
                state, detail = "stale", "30초 이상 새 체결 데이터가 없습니다."
            else:
                state, detail = "connected", "실제 체결 데이터를 수신 중입니다."
            items.append(
                ResearchFeedItem(
                    symbol=subscription.symbol,
                    exchange=subscription.exchange,
                    currency=subscription.currency,
                    state=state,
                    subscription_phase=phase,
                    detail=detail,
                    requested_at=evidence.requested_at if evidence else None,
                    sent_at=evidence.sent_at if evidence else None,
                    acknowledged_at=evidence.acknowledged_at if evidence else None,
                    first_quote_at=evidence.first_quote_at if evidence else None,
                    ack_overdue=ack_overdue,
                    last_market_at=quote.market_at if quote else None,
                    last_received_at=quote.received_at if quote else None,
                )
            )
        connected = sum(item.state == "connected" for item in items)
        stale = sum(item.state == "stale" for item in items)
        approved_without_quote = sum(
            item.subscription_phase == "approved" and item.first_quote_at is None
            for item in items
        )
        overdue = sum(item.ack_overdue for item in items)
        rejected = sum(item.state == "rejected" for item in items)
        if not self._forward_enabled():
            overall, detail = "disabled", "전진 관찰 세션이 비활성 상태입니다."
        elif self._state.state == "error":
            overall, detail = (
                "error",
                "KIS 시세 연결이 끊어져 새 연결 시도를 기다립니다.",
            )
        elif stale == len(items) and items:
            overall, detail = (
                "stale",
                "모든 연구 종목 시세가 30초 이상 갱신되지 않았습니다.",
            )
        elif connected == len(items) and items:
            overall, detail = (
                "connected",
                "단일 KIS 연결에서 연구 종목을 읽기 전용으로 구독 중입니다.",
            )
        elif connected or stale:
            overall, detail = (
                "partial",
                (
                    "일부 종목은 수신 중이며 승인된 나머지 종목의 첫 실제 "
                    "체결 데이터를 기다립니다."
                    if approved_without_quote
                    else "일부 종목의 시세가 지연됐지만 나머지 수신은 유지됩니다."
                    if stale
                    else "거부된 종목과 별개로 승인된 종목의 수신을 유지합니다."
                    if rejected
                    else "일부 연구 종목의 실제 체결 데이터를 수신 중입니다."
                ),
            )
        elif approved_without_quote:
            overall, detail = (
                "connecting",
                "승인된 연구 종목의 첫 실제 체결 데이터를 기다립니다.",
            )
        elif overdue:
            overall, detail = (
                "connecting",
                "일부 연구 종목의 구독 승인 확인이 10초 넘게 지연되고 있습니다.",
            )
        elif self._task is not None or any(item.state == "pending" for item in items):
            overall, detail = "connecting", "연구 종목 구독 승인을 기다립니다."
        else:
            overall, detail = "error", "연구 시세 스트림이 실행 중이 아닙니다."
        return ResearchFeedStatus(
            state=cast(
                Literal[
                    "disabled", "connecting", "connected", "partial", "stale", "error"
                ],
                overall,
            ),
            detail=detail,
            configured=bool(self.settings.app_key and self.settings.app_secret),
            connected_at=self._research_connected_at,
            reconnect_count=self._reconnect_count,
            items=items,
            protocol_counters=[
                ResearchProtocolCounter(
                    tr_id=tr_id,
                    data_frame_count=self._protocol_counters.get(tr_id, {}).get(
                        "data_frame_count", 0
                    ),
                    valid_quote_count=self._protocol_counters.get(tr_id, {}).get(
                        "valid_quote_count", 0
                    ),
                    parse_failure_count=self._protocol_counters.get(tr_id, {}).get(
                        "parse_failure_count", 0
                    ),
                )
                for tr_id in ("H0STCNT0", "HDFSCNT0")
            ],
        )

    def _submit_quote(self, quote: Quote, *, require_enabled: bool = False) -> None:
        previous = self._pending_quotes.get(quote.symbol)
        if previous is None or quote.market_at >= previous.market_at:
            self._pending_quotes[quote.symbol] = quote
            if require_enabled:
                self._operations_requires_enabled.add(quote.symbol)
            self._signal_event.set()

    def _submit_research_quote(self, quote: ResearchQuote) -> None:
        previous = self._research_quotes.get(quote.symbol)
        if previous is not None and quote.market_at <= previous.market_at:
            return
        self._research_quotes[quote.symbol] = quote
        self._pending_research_quotes[quote.symbol] = quote
        self._signal_event.set()

    @staticmethod
    def _fresh(market_at: datetime, received_at: datetime) -> bool:
        now = utc_now()
        market, received = market_at.astimezone(UTC), received_at.astimezone(UTC)
        return not (
            received > now + timedelta(seconds=2)
            or market > now + timedelta(seconds=2)
            or now - received > timedelta(seconds=15)
            or now - market > timedelta(seconds=15)
        )

    async def _signal_loop(self) -> None:
        while True:
            await self._signal_event.wait()
            self._signal_event.clear()
            await asyncio.sleep(self._signal_interval_seconds)
            operations_pending = list(self._pending_quotes.values())
            require_enabled = self._operations_requires_enabled.copy()
            research_pending = list(self._pending_research_quotes.values())
            self._pending_quotes.clear()
            self._operations_requires_enabled.clear()
            self._pending_research_quotes.clear()
            for quote in operations_pending:
                if quote.symbol in require_enabled and not self._enabled():
                    continue
                if not self._fresh(quote.market_at, quote.received_at):
                    continue
                try:
                    await asyncio.to_thread(self._on_quote, quote)
                except Exception:
                    continue
            if self._on_research_quote is None or not self._forward_enabled():
                continue
            for research_quote in research_pending:
                if not self._fresh(
                    research_quote.market_at, research_quote.received_at
                ):
                    continue
                try:
                    await asyncio.to_thread(self._on_research_quote, research_quote)
                except Exception:
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
            if not (self._enabled() or self._forward_enabled()):
                self._quotes.clear()
                self._pending_quotes.clear()
                self._state = self._state.model_copy(
                    update={"state": "disabled", "symbols": self._symbols()}
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
                self._reconnect_count = reconnects
                self._quotes.clear()
                self._pending_quotes.clear()
                self._invalidate_research_attempt()
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
        operation_symbols = self._symbols() if self._enabled() else []
        research = (
            research_subscriptions(self._research_instruments())
            if self._forward_enabled()
            else []
        )
        subscriptions: dict[tuple[str, str], ResearchSubscription] = {
            (item.tr_id, item.tr_key): item for item in research
        }
        for symbol in operation_symbols:
            subscriptions.setdefault(
                ("H0STCNT0", symbol),
                ResearchSubscription(
                    symbol=symbol,
                    exchange="KRX",
                    currency="KRW",
                    tr_id="H0STCNT0",
                    tr_key=symbol,
                ),
            )
        self._reset_subscription_attempt(subscriptions, research)
        async with connect(
            self.settings.websocket_url,
            open_timeout=15,
            ping_interval=20,
            ping_timeout=20,
            max_size=1_000_000,
        ) as websocket:
            await self._run_connection(
                websocket,
                approval_key,
                subscriptions,
                operation_symbols,
            )

    def _reset_subscription_attempt(
        self,
        subscriptions: dict[tuple[str, str], ResearchSubscription],
        research: Sequence[ResearchSubscription],
    ) -> None:
        requested_at = utc_now()
        self._subscription_states = {
            key: ("pending", "읽기 전용 구독 전송을 기다립니다.")
            for key in subscriptions
        }
        self._subscription_evidence = {
            key: _SubscriptionEvidence("queued", requested_at) for key in subscriptions
        }
        self._research_subscription_keys = {
            (item.tr_id, item.tr_key) for item in research
        }
        self._protocol_counters = {
            tr_id: {
                "data_frame_count": 0,
                "valid_quote_count": 0,
                "parse_failure_count": 0,
            }
            for tr_id in ALLOWED_RESEARCH_TR_IDS
        }
        self._research_connected_at = None
        self._research_quotes.clear()
        self._pending_research_quotes.clear()
        self._quotes.clear()
        self._pending_quotes.clear()
        self._operations_requires_enabled.clear()

    def _invalidate_research_attempt(self) -> None:
        self._subscription_states.clear()
        self._subscription_evidence.clear()
        self._research_subscription_keys.clear()
        self._protocol_counters.clear()
        self._research_connected_at = None
        self._research_quotes.clear()
        self._pending_research_quotes.clear()

    async def _send_subscriptions(
        self,
        websocket: ReadOnlySocket,
        approval_key: str,
        subscriptions: Sequence[ResearchSubscription],
    ) -> float:
        loop = asyncio.get_running_loop()
        last_sent = loop.time()
        for index, item in enumerate(subscriptions):
            key = (item.tr_id, item.tr_key)
            evidence = self._subscription_evidence[key]
            evidence.phase = "awaiting_ack"
            evidence.sent_at = utc_now()
            self._subscription_states[key] = (
                "pending",
                "구독 승인 응답을 기다립니다.",
            )
            await websocket.send(
                json.dumps(
                    {
                        "header": {
                            "approval_key": approval_key,
                            "custtype": "P",
                            "tr_type": "1",
                            "content-type": "utf-8",
                        },
                        "body": {"input": {"tr_id": item.tr_id, "tr_key": item.tr_key}},
                    }
                )
            )
            last_sent = loop.time()
            if index + 1 < len(subscriptions):
                await asyncio.sleep(SUBSCRIPTION_INTERVAL_SECONDS)
        return last_sent

    async def _run_connection(
        self,
        websocket: ReadOnlySocket,
        approval_key: str,
        subscriptions: dict[tuple[str, str], ResearchSubscription],
        operation_symbols: Sequence[str],
    ) -> None:
        if not subscriptions:
            raise RuntimeError("No read-only subscriptions were configured")
        acknowledged: set[tuple[str, str]] = set()
        sender: asyncio.Task[float] | None = asyncio.create_task(
            self._send_subscriptions(
                websocket, approval_key, list(subscriptions.values())
            )
        )
        receiver: asyncio.Task[object] = asyncio.create_task(websocket.recv())
        last_sent: float | None = None
        try:
            while True:
                timeout = None
                if sender is None and not acknowledged and last_sent is not None:
                    remaining = (
                        last_sent
                        + ACKNOWLEDGEMENT_TIMEOUT_SECONDS
                        - asyncio.get_running_loop().time()
                    )
                    if remaining <= 0:
                        raise RuntimeError(
                            "KIS did not acknowledge any read-only subscription"
                        )
                    timeout = remaining
                tasks: set[asyncio.Task[object] | asyncio.Task[float]] = {receiver}
                if sender is not None:
                    tasks.add(sender)
                done, _pending = await asyncio.wait(
                    tasks, timeout=timeout, return_when=asyncio.FIRST_COMPLETED
                )
                if not done:
                    raise RuntimeError(
                        "KIS did not acknowledge any read-only subscription"
                    )
                if sender is not None and sender in done:
                    last_sent = await sender
                    sender = None
                if receiver in done:
                    message = receiver.result()
                    if isinstance(message, str):
                        await self._process_message(
                            message,
                            websocket,
                            subscriptions,
                            acknowledged,
                            operation_symbols,
                        )
                    receiver = asyncio.create_task(websocket.recv())
                if acknowledged and self._state.state != "connected":
                    self._state = self._state.model_copy(
                        update={
                            "state": "connected",
                            "detail": (
                                "KIS 실시간 체결가를 읽기 전용으로 구독 중입니다."
                            ),
                            "connected_at": utc_now(),
                            "symbols": list(operation_symbols),
                        }
                    )
        finally:
            pending_tasks = [receiver]
            if sender is not None:
                pending_tasks.append(sender)
            for task in pending_tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*pending_tasks, return_exceptions=True)

    async def _process_message(
        self,
        message: str,
        websocket: ReadOnlySocket,
        subscriptions: dict[tuple[str, str], ResearchSubscription],
        acknowledged: set[tuple[str, str]],
        operation_symbols: Sequence[str],
    ) -> None:
        if message.startswith("{"):
            control = await _safe_control_message(message, websocket)
            self._apply_control(control, subscriptions, acknowledged)
            return
        self._handle_data(message, subscriptions, acknowledged, operation_symbols)

    def _apply_control(
        self,
        control: _ControlResult | None,
        subscriptions: dict[tuple[str, str], ResearchSubscription],
        acknowledged: set[tuple[str, str]],
    ) -> None:
        if control is None:
            return
        key = (control.tr_id, control.tr_key)
        if key not in subscriptions:
            return
        evidence = self._subscription_evidence.get(key)
        if (
            evidence is None
            or evidence.sent_at is None
            or evidence.phase not in {"awaiting_ack", "approved"}
        ):
            return
        if control.accepted:
            acknowledged.add(key)
            if evidence is not None:
                evidence.phase = "approved"
                evidence.acknowledged_at = utc_now()
            self._subscription_states[key] = (
                "connected",
                "읽기 전용 구독이 승인되었습니다.",
            )
            if (
                key in self._research_subscription_keys
                and self._research_connected_at is None
            ):
                self._research_connected_at = utc_now()
        else:
            acknowledged.discard(key)
            if evidence is not None:
                evidence.phase = "rejected"
                evidence.acknowledged_at = utc_now()
            self._subscription_states[key] = (
                "rejected",
                "읽기 전용 구독이 거부되었습니다.",
            )

    def _handle_data(
        self,
        message: str,
        subscriptions: dict[tuple[str, str], ResearchSubscription],
        acknowledged: set[tuple[str, str]],
        operation_symbols: Sequence[str],
    ) -> None:
        parts = message.split("|", 3)
        tr_id = parts[1] if len(parts) >= 2 else ""
        if tr_id not in ALLOWED_RESEARCH_TR_IDS:
            return
        self._increment_protocol_counter(tr_id, "data_frame_count")
        if tr_id == "H0STCNT0":
            try:
                operation_quotes = parse_h0stcnt0_frame(message)
            except ValueError:
                operation_quotes = []
            for quote in operation_quotes:
                if ("H0STCNT0", quote.symbol) not in acknowledged:
                    continue
                if self._enabled() and quote.symbol in operation_symbols:
                    previous = self._quotes.get(quote.symbol)
                    if previous is None or quote.market_at > previous.market_at:
                        self._quotes[quote.symbol] = quote
                        self._state = self._state.model_copy(
                            update={"last_message_at": quote.received_at}
                        )
                        self._submit_quote(quote, require_enabled=True)
        if self._forward_enabled():
            try:
                research_quotes = parse_research_frame(
                    message,
                    [
                        item
                        for key, item in subscriptions.items()
                        if key in self._research_subscription_keys
                    ],
                )
            except ValueError:
                self._increment_protocol_counter(tr_id, "parse_failure_count")
                return
            self._increment_protocol_counter(
                tr_id, "valid_quote_count", len(research_quotes)
            )
            for research_quote in research_quotes:
                matching = next(
                    (
                        key
                        for key, item in subscriptions.items()
                        if key in self._research_subscription_keys
                        and item.tr_id == tr_id
                        and item.symbol == research_quote.symbol
                    ),
                    None,
                )
                if matching is None or matching not in acknowledged:
                    continue
                evidence = self._subscription_evidence.get(matching)
                if evidence is not None and evidence.first_quote_at is None:
                    evidence.first_quote_at = research_quote.received_at
                self._submit_research_quote(research_quote)

    def _increment_protocol_counter(
        self, tr_id: str, name: str, increment: int = 1
    ) -> None:
        counters = self._protocol_counters.get(tr_id)
        if counters is None or name not in counters:
            return
        counters[name] = min(2_147_483_647, counters[name] + max(0, increment))
