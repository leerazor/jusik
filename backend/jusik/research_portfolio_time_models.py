"""Versioned, explicit time evidence for an opt-in portfolio simulation.

The models in this module deliberately do not alter the historical portfolio
schemas.  They describe the extra causal evidence produced by the standalone
time-evidence adapter.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

TIME_EVIDENCE_SCHEMA_VERSION: Final[Literal[1]] = 1
TIME_EVIDENCE_POLICY_VERSION: Final[Literal["forward-simulation-time-evidence-v1"]] = (
    "forward-simulation-time-evidence-v1"
)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("time evidence timestamps must include a timezone")
    return value


class InitialCapitalEvent(BaseModel):
    """The initial balance anchored to the first event handled by the engine.

    This is an engine ordering anchor, not a claim that a deposit happened at
    a market open or that a historical deposit was observed at this instant.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = TIME_EVIDENCE_SCHEMA_VERSION
    event_kind: Literal["initial_capital"] = "initial_capital"
    initial_capital_krw: Decimal = Field(gt=0)
    timestamp: datetime
    timestamp_kind: Literal["engine_event_anchor"] = "engine_event_anchor"
    logical_order: Literal["before_first_event"] = "before_first_event"
    first_engine_event_at: datetime
    first_engine_event_kind: Literal["rebalance", "open", "close"]
    not_market_open_or_historical_deposit: Literal[True] = True

    _timestamp_is_aware = field_validator("timestamp", "first_engine_event_at")(_aware)

    @model_validator(mode="after")
    def validate_anchor(self) -> InitialCapitalEvent:
        if self.timestamp != self.first_engine_event_at:
            raise ValueError("initial capital timestamp must equal first engine event")
        return self

    @property
    def amount_krw(self) -> Decimal:
        return self.initial_capital_krw

    @property
    def event_at(self) -> datetime:
        return self.timestamp


class MarketSessionTimeEvidence(BaseModel):
    """An official supplied calendar session linked to one close event."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = TIME_EVIDENCE_SCHEMA_VERSION
    symbol: str = Field(min_length=1)
    calendar: Literal["XKRX", "XNYS"]
    local_date: date
    session_id: str = Field(min_length=1)
    open_at: datetime
    close_at: datetime

    _times_are_aware = field_validator("open_at", "close_at")(_aware)

    @model_validator(mode="after")
    def validate_session(self) -> MarketSessionTimeEvidence:
        expected = f"{self.calendar}:{self.local_date.isoformat()}"
        if self.session_id != expected:
            raise ValueError("session_id must identify calendar and local date")
        if self.open_at >= self.close_at:
            raise ValueError("session open must precede close")
        return self


class CloseEventTimeEvidence(BaseModel):
    """One close event in the engine's same-time close group."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = TIME_EVIDENCE_SCHEMA_VERSION
    symbol: str = Field(min_length=1)
    bar_date: date
    event_at: datetime
    session: MarketSessionTimeEvidence

    _event_time_is_aware = field_validator("event_at")(_aware)

    @model_validator(mode="after")
    def validate_link(self) -> CloseEventTimeEvidence:
        if self.session.symbol != self.symbol:
            raise ValueError("close event and session symbols must match")
        if self.session.local_date != self.bar_date:
            raise ValueError("close event and session dates must match")
        if self.session.close_at > self.event_at:
            raise ValueError("official session close must precede evaluation")
        return self


class NavTimeEvidence(BaseModel):
    """Causal time evidence for one existing engine NAV observation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = TIME_EVIDENCE_SCHEMA_VERSION
    evaluation_at: datetime
    nav_index: int = Field(ge=0)
    nav_krw: Decimal = Field(ge=0)
    triggering_close_group: list[CloseEventTimeEvidence]

    _evaluation_time_is_aware = field_validator("evaluation_at")(_aware)

    @model_validator(mode="after")
    def validate_group(self) -> NavTimeEvidence:
        if not self.triggering_close_group:
            raise ValueError("every NAV must have a triggering close group")
        if any(
            item.event_at != self.evaluation_at for item in self.triggering_close_group
        ):
            raise ValueError("close group event times must equal evaluation_at")
        symbols = [item.symbol for item in self.triggering_close_group]
        if len(symbols) != len(set(symbols)):
            raise ValueError("close group symbols must be unique")
        return self

    @property
    def linked_sessions(self) -> tuple[MarketSessionTimeEvidence, ...]:
        """Compatibility/readability view of sessions linked to this NAV."""

        return tuple(item.session for item in self.triggering_close_group)

    @property
    def sessions(self) -> tuple[MarketSessionTimeEvidence, ...]:
        return self.linked_sessions

    @property
    def close_group(self) -> tuple[CloseEventTimeEvidence, ...]:
        return tuple(self.triggering_close_group)


class PortfolioTimeEvidence(BaseModel):
    """Complete time sidecar for one newly generated simulation bundle."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = TIME_EVIDENCE_SCHEMA_VERSION
    policy_version: Literal["forward-simulation-time-evidence-v1"] = (
        TIME_EVIDENCE_POLICY_VERSION
    )
    initial_capital: InitialCapitalEvent
    nav: list[NavTimeEvidence]

    @model_validator(mode="after")
    def validate_nav_order(self) -> PortfolioTimeEvidence:
        indexes = [item.nav_index for item in self.nav]
        if indexes != list(range(len(indexes))):
            raise ValueError("NAV indexes must be contiguous and ordered")
        times = [item.evaluation_at for item in self.nav]
        if times != sorted(times) or len(times) != len(set(times)):
            raise ValueError("NAV evaluation times must be strictly increasing")
        return self

    @property
    def nav_evidence(self) -> tuple[NavTimeEvidence, ...]:
        return tuple(self.nav)


# Descriptive aliases keep the public contract discoverable without making a
# second schema that could drift from the versioned models above.
InitialCapitalTimeEvidence = InitialCapitalEvent
MarketSessionEvidence = MarketSessionTimeEvidence
CloseGroupEvent = CloseEventTimeEvidence
TimeEvidenceBundle = PortfolioTimeEvidence
