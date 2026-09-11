from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    model_validator,
)

from jusik.kis_stream import US_EXCHANGE
from jusik.research_forward_models import ForwardCorporateAction
from jusik.research_forward_store import CorporateActionRegistration, ForwardStore
from jusik.research_market_calendar import (
    CALENDAR_TIMEZONE,
    EXCHANGE_CALENDAR,
    MarketCalendar,
    default_market_calendar,
)
from jusik.research_universe_data import REGISTRY

MAX_MANIFEST_BYTES = 1_000_000


class VerifiedForwardSplit(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: str = Field(min_length=1, max_length=20)
    exchange: str = Field(min_length=1, max_length=10)
    numerator: int = Field(gt=0, strict=True)
    denominator: int = Field(gt=0, strict=True)
    source_url: AnyHttpUrl
    evidence_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}$")
    evidence_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    operator_verified: Literal[True]
    observed_at: datetime
    effective_at: datetime

    @model_validator(mode="after")
    def validate_split(self) -> VerifiedForwardSplit:
        if self.observed_at.tzinfo is None or self.effective_at.tzinfo is None:
            raise ValueError("timestamps_must_be_timezone_aware")
        if (
            self.source_url.scheme != "https"
            or self.source_url.username is not None
            or self.source_url.password is not None
        ):
            raise ValueError("source_url_must_be_public_https")
        if self.numerator <= self.denominator:
            raise ValueError("only_forward_splits_are_supported")
        if self.numerator % self.denominator:
            raise ValueError("only_integer_split_factors_are_supported")
        if self.numerator // self.denominator <= 1:
            raise ValueError("split_factor_must_exceed_one")
        return self

    @property
    def factor(self) -> int:
        return self.numerator // self.denominator


class CorporateActionManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1]
    events: list[VerifiedForwardSplit] = Field(max_length=100)


def _read_manifest(path: Path) -> CorporateActionManifest:
    if not path.is_file() or path.is_symlink():
        raise ValueError("manifest_file_invalid")
    raw = path.read_bytes()
    if len(raw) > MAX_MANIFEST_BYTES:
        raise ValueError("manifest_too_large")
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("manifest_json_invalid") from exc
    try:
        return CorporateActionManifest.model_validate(payload)
    except ValidationError as exc:
        raise ValueError("manifest_schema_invalid") from exc


def _validate_registry_and_calendar(
    event: VerifiedForwardSplit, calendar: MarketCalendar
) -> None:
    registered = {item.symbol: item for item in REGISTRY}
    instrument = registered.get(event.symbol)
    if instrument is None:
        raise ValueError("manifest_symbol_exchange_mismatch")
    expected_exchange = (
        "KRX" if instrument.exchange == "KSC" else US_EXCHANGE.get(instrument.exchange)
    )
    if expected_exchange != event.exchange:
        raise ValueError("manifest_symbol_exchange_mismatch")
    calendar_name = EXCHANGE_CALENDAR.get(event.exchange)
    if calendar_name is None:
        raise ValueError("manifest_exchange_calendar_unavailable")
    effective = event.effective_at.astimezone(UTC)
    local_date = effective.astimezone(CALENDAR_TIMEZONE[calendar_name]).date()
    lookup = calendar.lookup(event.exchange, local_date)
    if lookup.session is None:
        raise ValueError("manifest_effective_session_unavailable")
    if lookup.session.open_at != effective:
        raise ValueError("manifest_effective_at_not_trading_open")


def register_verified_manifest(
    *,
    db_path: Path,
    session_id: str,
    manifest_path: Path,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    market_calendar: MarketCalendar | None = None,
) -> list[ForwardCorporateAction]:
    manifest = _read_manifest(manifest_path)
    calendar = market_calendar or default_market_calendar()
    registered_at = clock()
    if registered_at.tzinfo is None:
        raise ValueError("registration_clock_must_be_timezone_aware")
    registered_at = registered_at.astimezone(UTC)
    store = ForwardStore(db_path)
    for event in manifest.events:
        _validate_registry_and_calendar(event, calendar)
    return store.register_corporate_actions(
        [
            CorporateActionRegistration(
                session_id=session_id,
                symbol=event.symbol,
                exchange=event.exchange,
                factor=event.factor,
                source_url=str(event.source_url),
                evidence_id=event.evidence_id,
                evidence_sha256=event.evidence_sha256,
                observed_at=event.observed_at,
                effective_at=event.effective_at,
                registered_at=registered_at,
            )
            for event in manifest.events
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Register operator-verified integer forward splits for PAPER"
    )
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--session", required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    try:
        actions = register_verified_manifest(
            db_path=args.db,
            session_id=args.session,
            manifest_path=args.manifest,
        )
    except (OSError, sqlite3.Error, ValueError):
        print("corporate action manifest registration failed", file=sys.stderr)
        return 1
    print(json.dumps({"registered_events": len(actions)}, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
