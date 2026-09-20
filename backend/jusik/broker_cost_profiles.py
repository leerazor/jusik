"""Explicit broker cost profiles for future paper research contracts.

Profiles are evidence-backed inputs only. They are never applied to frozen
historical runs implicitly.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
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

    def manifest(self) -> dict[str, object]:
        """Return a JSON-safe manifest for a new PAPER run."""
        return {
            "schema_version": "paper-cost-contract-v1",
            "contract_id": self.contract_id,
            "profile_hash": self.profile_hash,
            "applies_to_frozen_history": self.applies_to_frozen_history,
            "profiles": [
                {
                    "broker": profile.broker,
                    "account_scope": profile.account_scope,
                    "market": profile.market,
                    "currency": profile.currency,
                    "online_fee_rate": str(profile.online_fee_rate),
                    "sell_tax_rate": str(profile.sell_tax_rate),
                    "source_urls": list(profile.source_urls),
                    "source_as_of": profile.source_as_of,
                }
                for profile in self.profiles
            ],
        }


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


def validate_paper_cost_contract_manifest(
    manifest: Mapping[str, object],
) -> PaperCostContract:
    """Validate a saved manifest and reject frozen-history application."""
    if manifest.get("schema_version") != "paper-cost-contract-v1":
        raise ValueError("paper_cost_contract_schema_invalid")
    if manifest.get("applies_to_frozen_history") is not False:
        raise ValueError("paper_cost_contract_frozen_history_forbidden")
    profiles = manifest.get("profiles")
    if not isinstance(profiles, list) or not profiles:
        raise ValueError("paper_cost_contract_profiles_missing")
    parsed: list[BrokerCostProfile] = []
    for raw in profiles:
        if not isinstance(raw, Mapping):
            raise ValueError("paper_cost_contract_profile_invalid")
        try:
            parsed.append(
                BrokerCostProfile(
                    broker=str(raw["broker"]),
                    account_scope=str(raw["account_scope"]),
                    market=raw["market"],
                    currency=raw["currency"],
                    online_fee_rate=Decimal(str(raw["online_fee_rate"])),
                    sell_tax_rate=Decimal(str(raw["sell_tax_rate"])),
                    source_urls=tuple(str(url) for url in raw["source_urls"]),
                    source_as_of=str(raw["source_as_of"]),
                )
            )
        except (KeyError, TypeError, ValueError, ArithmeticError) as exc:
            raise ValueError("paper_cost_contract_profile_invalid") from exc
    contract = PaperCostContract(
        contract_id=str(manifest.get("contract_id", "")),
        profile_hash=str(manifest.get("profile_hash", "")),
        profiles=tuple(parsed),
    )
    expected = build_bankis_paper_cost_contract(
        tuple(profile.market for profile in contract.profiles)
    )
    if contract.profile_hash != expected.profile_hash:
        raise ValueError("paper_cost_contract_hash_mismatch")
    return contract


__all__ = [
    "BrokerCostProfile",
    "PaperCostContract",
    "KIS_BANKIS_ONLINE_PROFILES",
    "build_bankis_paper_cost_contract",
    "kis_bankis_online_profile",
    "validate_paper_cost_contract_manifest",
]
