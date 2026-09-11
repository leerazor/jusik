from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ResearchSymbol = Annotated[str, Field(pattern=r"^[A-Z0-9]{1,12}$")]
PositivePrice = Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
ResearchExchange = Literal["KRX", "NAS", "NYS", "AMS"]


class ResearchSubscription(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: ResearchSymbol
    exchange: ResearchExchange
    currency: Literal["KRW", "USD"]
    tr_id: Literal["H0STCNT0", "HDFSCNT0"]
    tr_key: str = Field(min_length=1, max_length=24)


class ResearchQuote(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: ResearchSymbol
    exchange: ResearchExchange
    currency: Literal["KRW", "USD"]
    price: PositivePrice
    ask: PositivePrice | None = None
    bid: PositivePrice | None = None
    volume: int = Field(ge=0)
    accumulated_volume: int = Field(ge=0)
    market_at: datetime
    received_at: datetime
    source: Literal["KIS H0STCNT0", "KIS HDFSCNT0"]
    delay_minutes: Literal[0] = 0
    realtime_code: str | None = Field(default=None, max_length=24)

    @field_validator("market_at", "received_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Research quote timestamps must be timezone-aware.")
        return value


class ResearchFeedItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: ResearchSymbol
    exchange: ResearchExchange
    currency: Literal["KRW", "USD"]
    state: Literal["pending", "connected", "stale", "rejected", "unsupported"]
    subscription_phase: Literal["queued", "awaiting_ack", "approved", "rejected"] = (
        "queued"
    )
    detail: str
    requested_at: datetime | None = None
    sent_at: datetime | None = None
    acknowledged_at: datetime | None = None
    first_quote_at: datetime | None = None
    ack_overdue: bool = False
    last_market_at: datetime | None = None
    last_received_at: datetime | None = None
    delay_minutes: Literal[0] = 0

    @field_validator(
        "requested_at",
        "sent_at",
        "acknowledged_at",
        "first_quote_at",
        "last_market_at",
        "last_received_at",
    )
    @classmethod
    def optional_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("Research feed timestamps must be timezone-aware.")
        return value


class ResearchProtocolCounter(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tr_id: Literal["H0STCNT0", "HDFSCNT0"]
    data_frame_count: int = Field(ge=0, le=2_147_483_647)
    valid_quote_count: int = Field(ge=0, le=2_147_483_647)
    parse_failure_count: int = Field(ge=0, le=2_147_483_647)


class ResearchFeedStatus(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    state: Literal["disabled", "connecting", "connected", "partial", "stale", "error"]
    detail: str
    configured: bool
    connected_at: datetime | None = None
    reconnect_count: int = 0
    items: list[ResearchFeedItem]
    protocol_counters: list[ResearchProtocolCounter] = Field(default_factory=list)
    provider: Literal["Korea Investment Open Trading API"] = (
        "Korea Investment Open Trading API"
    )
    provider_url: Literal["https://github.com/koreainvestment/open-trading-api"] = (
        "https://github.com/koreainvestment/open-trading-api"
    )
    data_note: str = (
        "미국 무료 시세는 현재 지연 0분으로 표시하지만 "
        "실제 전달 지연은 보장하지 않습니다."
    )
