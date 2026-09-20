from decimal import Decimal

import pytest

from jusik.broker_cost_profiles import (
    build_bankis_paper_cost_contract,
    kis_bankis_online_profile,
)


def test_bankis_profiles_are_explicit_and_not_historical_overrides() -> None:
    krx = kis_bankis_online_profile("KRX")
    nxt = kis_bankis_online_profile("NXT")
    us = kis_bankis_online_profile("US")
    assert krx.online_fee_rate == Decimal("0.000140527")
    assert nxt.online_fee_rate == Decimal("0.000130527")
    assert krx.sell_tax_rate == Decimal("0.0023")
    assert us.online_fee_rate == Decimal("0.0025")
    assert us.sell_tax_rate == Decimal("0.0000206")
    assert all(not profile.applies_to_frozen_history for profile in (krx, nxt, us))


def test_bankis_profile_rejects_unknown_market() -> None:
    with pytest.raises(ValueError, match="unsupported BanKIS market"):
        kis_bankis_online_profile("OTHER")  # type: ignore[arg-type]


def test_bankis_paper_contract_is_hash_bound_and_history_safe() -> None:
    contract = build_bankis_paper_cost_contract(("KRX", "US"))
    assert contract.contract_id.startswith("kis-bankis-online-paper-v1:")
    assert len(contract.profile_hash) == 64
    assert tuple(profile.market for profile in contract.profiles) == ("KRX", "US")
    assert contract.applies_to_frozen_history is False
