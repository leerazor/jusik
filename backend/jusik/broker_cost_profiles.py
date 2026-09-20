"""Explicit broker cost profiles for future paper research contracts.

Profiles are evidence-backed inputs only. They are never applied to frozen
historical runs implicitly.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

BrokerMarket = Literal["KRX", "NXT", "US"]


@dataclass(frozen=True)
class BrokerCostProfile:
    broker: str
    account_scope: str
    market: BrokerMarket
    currency: Literal["KRW", "USD"]
    online_fee_rate: Decimal
    sell_tax_rate: Decimal
    source_urls: tuple[str, ...]
    source_as_of: str
    applies_to_frozen_history: bool = False


@dataclass(frozen=True)
class PaperCostContract:
    """Hash-bound broker costs for a new paper study only."""

    contract_id: str
    profile_hash: str
    profiles: tuple[BrokerCostProfile, ...]
    applies_to_frozen_history: bool = False


KIS_BANKIS_ONLINE_PROFILES: tuple[BrokerCostProfile, ...] = (
    BrokerCostProfile(
        broker="Korea Investment & Securities",
        account_scope="BanKIS online",
        market="KRX",
        currency="KRW",
        online_fee_rate=Decimal("0.000140527"),
        sell_tax_rate=Decimal("0.0023"),
        source_urls=(
            "https://m.truefriend.com/main/customer/guide/_static/TF04ae010000.jsp",
            "https://www.truefriend.com/main/customer/guide/_static/TF04ae050000.shtm",
        ),
        source_as_of="2025-10-27",
    ),
    BrokerCostProfile(
        broker="Korea Investment & Securities",
        account_scope="BanKIS online",
        market="NXT",
        currency="KRW",
        online_fee_rate=Decimal("0.000130527"),
        sell_tax_rate=Decimal("0.0023"),
        source_urls=(
            "https://m.truefriend.com/main/customer/guide/_static/TF04ae010000.jsp",
            "https://www.truefriend.com/main/customer/guide/_static/TF04ae050000.shtm",
        ),
        source_as_of="2025-10-27",
    ),
    BrokerCostProfile(
        broker="Korea Investment & Securities",
        account_scope="BanKIS online",
        market="US",
        currency="USD",
        online_fee_rate=Decimal("0.0025"),
        sell_tax_rate=Decimal("0.0000206"),
        source_urls=(
            "https://m.truefriend.com/main/bond/research/_static/TF03ca050000.jsp",
        ),
        source_as_of="2026-09-20",
    ),
)


def kis_bankis_online_profile(market: BrokerMarket) -> BrokerCostProfile:
    """Return the explicit BanKIS profile; never mutate historical settings."""
    for profile in KIS_BANKIS_ONLINE_PROFILES:
        if profile.market == market:
            return profile
    raise ValueError(f"unsupported BanKIS market: {market}")


def build_bankis_paper_cost_contract(
    markets: tuple[BrokerMarket, ...] = ("KRX", "NXT", "US"),
) -> PaperCostContract:
    """Build a deterministic BanKIS contract without changing historical runs."""
    profiles = tuple(kis_bankis_online_profile(market) for market in markets)
    payload = [
        {
            "market": profile.market,
            "currency": profile.currency,
            "fee": str(profile.online_fee_rate),
            "sell_tax": str(profile.sell_tax_rate),
            "source_as_of": profile.source_as_of,
            "source_urls": profile.source_urls,
        }
        for profile in profiles
    ]
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return PaperCostContract(
        contract_id=f"kis-bankis-online-paper-v1:{digest[:16]}",
        profile_hash=digest,
        profiles=profiles,
    )


__all__ = [
    "BrokerCostProfile",
    "PaperCostContract",
    "KIS_BANKIS_ONLINE_PROFILES",
    "build_bankis_paper_cost_contract",
    "kis_bankis_online_profile",
]
