from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Literal, Protocol, cast

from jusik.market_history_models import (
    Capability,
    CapabilityName,
    Currency,
    FXObservation,
    Market,
    MarketBar,
    MarketHistorySnapshot,
    MarketReadiness,
    MarketResearchRequest,
    PITMembership,
    RawArtifact,
)
from jusik.market_research_config import MarketResearchSettings
from jusik.research_market_calendar import default_market_calendar


def _hash(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, default=str
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def data_contract_hash(
    snapshot: MarketHistorySnapshot, readiness: MarketReadiness
) -> str:
    """Hash only the normalized source contract, never dates or raw rows."""
    payload = {
        "version": "pit-data-contract-v1",
        "market": snapshot.market,
        "source_identities": sorted(
            {item.source for item in snapshot.memberships}
            | {item.source for item in snapshot.bars}
            | {item.source for item in snapshot.fx}
            | {item.source for item in snapshot.source_artifacts}
        ),
        "normalization_version": snapshot.normalization_version,
        "research_grade": snapshot.research_grade,
        "pool_contract_hash": snapshot.pool_contract_hash,
        "simulated": readiness.simulated,
        "capabilities": [
            {"name": item.name, "status": item.status}
            for item in sorted(readiness.capabilities, key=lambda item: item.name)
        ],
        "availability_semantics": {
            "daily_bars": "full_bar_available_at_or_after_close_before_next_open",
            "membership": "available_at_or_before_session_close",
            "fx": "available_at_decision_cutoff",
        },
    }
    return _hash(payload)


class MarketHistorySource(Protocol):
    def readiness(self, market: Market, checked_at: datetime) -> MarketReadiness: ...

    async def collect(
        self, request: MarketResearchRequest
    ) -> MarketHistorySnapshot: ...


class UnavailableMarketHistorySource:
    """Production boundary: credentials alone never fabricate historical data."""

    def __init__(self, settings: MarketResearchSettings | None = None) -> None:
        self.settings = settings or MarketResearchSettings()

    def readiness(self, market: Market, checked_at: datetime) -> MarketReadiness:
        configured = (
            self.settings.krx_auth_key is not None
            if market == "KR"
            else self.settings.massive_api_key is not None
        )
        credentials = (
            ("ready", "provider credentials are configured")
            if configured
            else ("missing", "source credentials are not configured")
        )
        fx_capability = (
            ("ready", "KRW market does not require FX conversion")
            if market == "KR"
            else ("missing", "point-in-time FX observations are unavailable")
        )
        capabilities = (
            Capability(
                name="credentials",
                status=cast(Literal["ready", "missing"], credentials[0]),
                detail=credentials[1],
            ),
            Capability(
                name="entitlement",
                status="missing",
                detail="historical entitlement is unverified",
            ),
            Capability(
                name="calendar",
                status="ready",
                detail="bundled exchange calendar is available",
            ),
            Capability(
                name="membership",
                status="missing",
                detail="point-in-time membership source is unavailable",
            ),
            Capability(
                name="bars",
                status="missing",
                detail="point-in-time bars are unavailable",
            ),
            Capability(
                name="actions",
                status="missing",
                detail="corporate actions are unavailable",
            ),
            Capability(
                name="fx",
                status=cast(Literal["ready", "missing"], fx_capability[0]),
                detail=fx_capability[1],
            ),
            Capability(
                name="policy",
                status="ready",
                detail="bounded next-open policy is configured",
            ),
        )
        return MarketReadiness(
            market=market,
            checked_at=checked_at,
            capabilities=capabilities,
            ready=False,
            simulated=False,
        )

    async def collect(self, request: MarketResearchRequest) -> MarketHistorySnapshot:
        checked = datetime.now(UTC)
        readiness = self.readiness(request.market, checked)
        missing = tuple(
            cap.name for cap in readiness.capabilities if cap.status != "ready"
        )
        return MarketHistorySnapshot(
            market=request.market,
            requested_start=request.start_date,
            requested_end=request.end_date,
            captured_at=checked,
            memberships=(),
            bars=(),
            actions=(),
            actions_complete=False,
            fx=(),
            completeness="incomplete",
            missing_ranges=missing,
        )


class FixtureMarketHistorySource:
    """Deterministic simulated source used only for causal UI and engine checks."""

    def readiness(self, market: Market, checked_at: datetime) -> MarketReadiness:
        capabilities = tuple(
            Capability(
                name=cast(CapabilityName, name),
                status="ready",
                detail="합성 자료로 흐름을 확인할 수 있습니다.",
            )
            for name in (
                "credentials",
                "entitlement",
                "calendar",
                "membership",
                "bars",
                "actions",
                "fx",
                "policy",
            )
        )
        return MarketReadiness(
            market=market,
            checked_at=checked_at,
            capabilities=capabilities,
            ready=True,
            simulated=True,
        )

    @staticmethod
    def _sessions(request: MarketResearchRequest) -> list[date]:
        exchange = "KRX" if request.market == "KR" else "NMS"
        calendar = default_market_calendar()
        sessions: list[date] = []
        cursor = request.start_date - timedelta(days=45)
        while cursor <= request.end_date:
            lookup = calendar.lookup(exchange, cursor)
            if lookup.session is not None:
                sessions.append(cursor)
            cursor += timedelta(days=1)
        return sessions

    async def collect(self, request: MarketResearchRequest) -> MarketHistorySnapshot:
        captured = datetime.combine(
            request.end_date + timedelta(days=1), datetime.min.time(), tzinfo=UTC
        )
        sessions = self._sessions(request)
        warmup_sessions = tuple(item for item in sessions if item < request.start_date)[
            -20:
        ]
        symbols = (
            (
                ("KR-A", "합성 한국 주식 A"),
                ("KR-B", "합성 한국 주식 B"),
                ("KR-C", "합성 한국 주식 C"),
            )
            if request.market == "KR"
            else (
                ("US-A", "Synthetic US Stock A"),
                ("US-B", "Synthetic US Stock B"),
                ("US-C", "Synthetic US Stock C"),
            )
        )
        exchange = "KSC" if request.market == "KR" else "NMS"
        currency = "KRW" if request.market == "KR" else "USD"
        memberships: list[PITMembership] = []
        for symbol, name in (*symbols, ("ETF-1", "합성 ETF")):
            membership_payload = {
                "market": request.market,
                "symbol": symbol,
                "type": "etf" if symbol.startswith("ETF") else "stock",
            }
            memberships.append(
                PITMembership(
                    stable_id=f"fixture:{request.market}:{symbol}:1",
                    market=request.market,
                    exchange=exchange,
                    symbol=symbol,
                    name=name,
                    instrument_type="etf" if symbol.startswith("ETF") else "stock",
                    currency=cast(Currency, currency),
                    valid_from=sessions[0] if sessions else request.start_date,
                    available_at=datetime.combine(
                        sessions[0] if sessions else request.start_date,
                        datetime.min.time(),
                        tzinfo=UTC,
                    ),
                    captured_at=captured,
                    source="fixture",
                    source_hash=_hash(membership_payload),
                    normalization_version="pit-v1",
                )
            )
        bars: list[MarketBar] = []
        for symbol_index, (symbol, _) in enumerate((*symbols, ("ETF-1", "합성 ETF"))):
            for index, session_date in enumerate(sessions):
                market_session = (
                    default_market_calendar().lookup(exchange, session_date).session
                )
                if market_session is None:
                    raise ValueError("fixture calendar session disappeared")
                base = Decimal(100 + symbol_index * 10 + index // 20)
                volume = Decimal(1000 + symbol_index * 100 + index)
                if symbol_index == 0 and index % 23 == 0 and index >= 20:
                    volume = Decimal("5000")
                bar_payload = {
                    "symbol": symbol,
                    "session": session_date.isoformat(),
                    "volume": str(volume),
                }
                bars.append(
                    MarketBar(
                        market=request.market,
                        exchange=exchange,
                        symbol=symbol,
                        session=session_date,
                        open=base,
                        high=base + 2,
                        low=base - 2,
                        close=base + 1,
                        volume=volume,
                        currency=cast(Currency, currency),
                        captured_at=captured,
                        available_at=market_session.close_at,
                        source="fixture",
                        source_hash=_hash(bar_payload),
                        normalization_version="pit-v1",
                    )
                )
        fx: list[FXObservation] = []
        if request.market == "US":
            for session_date in sessions:
                market_session = (
                    default_market_calendar().lookup(exchange, session_date).session
                )
                if market_session is None:
                    raise ValueError("fixture calendar session disappeared")
                fx.append(
                    FXObservation(
                        session=session_date,
                        pair="USDKRW",
                        krw_per_usd=Decimal("1350")
                        + Decimal(sessions.index(session_date)) / 100,
                        spread_rate=Decimal("0.001"),
                        available_at=datetime.combine(
                            market_session.open_at.date(),
                            market_session.open_at.timetz().replace(tzinfo=None),
                            tzinfo=market_session.open_at.tzinfo,
                        ),
                        captured_at=captured,
                        source="fixture",
                        source_hash=_hash(
                            {"session": session_date.isoformat(), "pair": "USDKRW"}
                        ),
                    )
                )
        raw_manifest = json.dumps(
            {
                "market": request.market,
                "start_date": request.start_date.isoformat(),
                "end_date": request.end_date.isoformat(),
                "sessions": [session.isoformat() for session in sessions],
                "symbols": [symbol for symbol, _ in (*symbols, ("ETF-1", "합성 ETF"))],
            },
            ensure_ascii=False,
            sort_keys=True,
        ).encode()
        artifact = RawArtifact.from_bytes(
            raw_manifest,
            content_type="application/json",
            captured_at=captured,
            source="fixture",
            source_url=(
                "https://example.invalid/fixture/"
                f"{request.market}/{request.start_date}_{request.end_date}.json"
            ),
        )
        return MarketHistorySnapshot(
            market=request.market,
            requested_start=request.start_date,
            requested_end=request.end_date,
            captured_at=captured,
            memberships=tuple(memberships),
            bars=tuple(bars),
            actions=(),
            actions_complete=True,
            fx=tuple(fx),
            source_artifacts=(artifact,),
            completeness="complete" if sessions else "incomplete",
            missing_ranges=() if sessions else ("calendar", "bars", "membership"),
            warmup_sessions=warmup_sessions,
            evaluation_start=request.start_date,
        )
