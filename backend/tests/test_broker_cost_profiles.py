from decimal import Decimal

import pytest

from jusik.broker_cost_profiles import (
    build_bankis_paper_cost_contract,
    kis_bankis_online_profile,
    validate_paper_cost_contract_manifest,
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


def test_paper_contract_manifest_round_trips_and_rejects_tampering() -> None:
    contract = build_bankis_paper_cost_contract(("KRX", "US"))
    restored = validate_paper_cost_contract_manifest(contract.manifest())
    assert restored.profile_hash == contract.profile_hash
    tampered = contract.manifest()
    tampered["profile_hash"] = "0" * 64
    with pytest.raises(ValueError, match="hash_mismatch"):
        validate_paper_cost_contract_manifest(tampered)

    tampered_id = contract.manifest()
    tampered_id["contract_id"] = "kis-bankis-online-paper-v1:wrong"
    with pytest.raises(ValueError, match="id_mismatch"):
        validate_paper_cost_contract_manifest(tampered_id)


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("currency", "USD", "profile_invalid"),
        ("online_fee_rate", "NaN", "profile_invalid"),
        ("source_urls", ["http://insecure.example"], "profile_invalid"),
        ("source_as_of", "not-a-date", "profile_invalid"),
    ],
)
def test_manifest_rejects_invalid_profile_evidence(
    field: str, value: object, error: str
) -> None:
    manifest = build_bankis_paper_cost_contract(("KRX",)).manifest()
    manifest["profiles"][0][field] = value  # type: ignore[index]
    with pytest.raises(ValueError, match=error):
        validate_paper_cost_contract_manifest(manifest)
