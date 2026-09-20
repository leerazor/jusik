"""Explicit broker cost profiles for future paper research contracts.

Profiles are evidence-backed inputs only. They are never applied to frozen
historical runs implicitly.
"""

from __future__ import annotations

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


__all__ = [
    "BrokerCostProfile",
    "KIS_BANKIS_ONLINE_PROFILES",
    "kis_bankis_online_profile",
]
