from __future__ import annotations

import httpx
import pytest

from jusik.research_alpha_price_probe import probe_daily


def test_probe_returns_daily_bounds_without_secret_in_result() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["apikey"] == "secret"
        return httpx.Response(
            200,
            json={
                "Time Series (Daily)": {
                    "2024-01-03": {"4. close": "101"},
                    "2024-01-02": {"4. close": "100"},
                }
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = probe_daily("AAPL", "secret", client=client)

    assert result.status == "ready"
    assert result.rows == 2
    assert result.first_date == "2024-01-02"
    assert result.last_date == "2024-01-03"
    assert "secret" not in repr(result)


@pytest.mark.parametrize(
    ("payload", "status", "error"),
    [
        ({"Information": "premium"}, "unavailable", "alpha_vantage_information"),
        ({"Note": "slow down"}, "unavailable", "alpha_vantage_rate_limited"),
        ({"Error Message": "bad symbol"}, "error", "alpha_vantage_provider_error"),
    ],
)
def test_probe_classifies_provider_envelopes(payload, status, error) -> None:
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
    ) as client:
        result = probe_daily("LIME", "secret", client=client)
    assert result.status == status
    assert result.error == error


def test_probe_fails_closed_without_key() -> None:
    result = probe_daily("AAPL", None)
    assert result.status == "missing_key"
    assert result.error == "key_missing"


def test_probe_rejects_invalid_symbol() -> None:
    with pytest.raises(ValueError, match="symbol"):
        probe_daily("AAPL/SECRET", "secret")
