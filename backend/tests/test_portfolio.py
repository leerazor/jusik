import asyncio
from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest
from pydantic import ValidationError

from jusik.config import Settings
from jusik.kis import BrokerError, KisClient, normalize
from jusik.models import MarketResult, percentage, summarize


def domestic(**changes: object) -> dict[str, object]:
    return dict(
        pdno="TEST",
        prdt_name="Test holding",
        hldg_qty="2",
        pchs_avg_pric="100",
        prpr="110",
        pchs_amt="200",
        evlu_amt="220",
        evlu_pfls_amt="20",
        **changes,
    )


def row(**changes: object) -> dict[str, object]:
    return domestic() | changes


def settings() -> Settings:
    return Settings(
        _env_file=None,
        kis_app_key="test",
        kis_app_secret="test",
        kis_cano="00000000",
        kis_acnt_prdt_cd="00",
        kis_base_url="https://openapi.koreainvestment.com:9443",
    )


@pytest.mark.parametrize(
    ("profit", "cost", "expected"),
    [
        ("0", "0", None),
        ("0", "100", "0.00"),
        ("-10", "100", "-10.00"),
        ("1", "32", "3.13"),
        ("-1", "32", "-3.13"),
    ],
)
def test_percentage(profit: str, cost: str, expected: str | None) -> None:
    result = percentage(Decimal(profit), Decimal(cost))
    assert result == (Decimal(expected) if expected is not None else None)


@pytest.mark.parametrize(
    "changes",
    [{"hldg_qty": "-1"}, {"prpr": ""}, {"evlu_amt": "NaN"}, {"pchs_amt": None}],
)
def test_invalid_values_are_not_zero(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        normalize(row(**changes), "KRX", "KRW")


def test_missing_data_rejected() -> None:
    with pytest.raises(ValidationError):
        normalize({"pdno": "TEST"}, "KRX", "KRW")


def test_currency_totals_and_precision() -> None:
    krw = normalize(domestic(), "KRX", "KRW")
    usd = krw.model_copy(
        update={
            "currency": "USD",
            "cost": Decimal("0.1"),
            "value": Decimal("0.3"),
            "profit": Decimal("0.2"),
        }
    )
    totals = summarize(
        [
            MarketResult(market="KRX", status="ok", holdings=[krw]),
            MarketResult(market="NASD", status="ok", holdings=[usd]),
        ]
    )
    assert len(totals) == 2
    assert totals[1].value == Decimal("0.3")
    assert totals[1].return_pct == Decimal("200.00")


def test_weekend_and_timezone_do_not_drop_holdings() -> None:
    # Sunday UTC is Monday in Korea. Snapshots stay valid across market holidays.
    at = datetime(2026, 9, 6, 23, 59, tzinfo=UTC)
    market = MarketResult(
        market="KRX",
        status="ok",
        fetched_at=at,
        holdings=[normalize(domestic(), "KRX", "KRW")],
    )
    assert summarize([market])[0].value == Decimal("220")
    assert market.model_dump(mode="json")["fetched_at"].endswith("Z")


def test_overseas_and_wrong_currency() -> None:
    data: dict[str, object] = dict(
        ovrs_pdno="TEST",
        ovrs_cblc_qty="0.5",
        pchs_avg_pric="10",
        now_pric2="8",
        frcr_pchs_amt1="5",
        ovrs_stck_evlu_amt="4",
        frcr_evlu_pfls_amt="-1",
        tr_crcy_cd="USD",
    )
    assert normalize(data, "NASD", "USD").return_pct == Decimal("-20")
    with pytest.raises(BrokerError):
        normalize(data, "NASD", "JPY")


def test_pagination_deduplicates_and_excludes_zero() -> None:
    async def run() -> None:
        calls = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            assert request.method == "GET"
            assert request.url.path.endswith("inquire-balance")
            if len(calls) == 1:
                return httpx.Response(
                    200,
                    headers={"tr_cont": "M"},
                    json={
                        "rt_cd": "0",
                        "output1": [domestic()],
                        "ctx_area_fk100": "first",
                        "ctx_area_nk100": "next",
                    },
                )
            assert request.headers["tr_cont"] == "N"
            assert request.url.params["CTX_AREA_NK100"] == "next"
            return httpx.Response(
                200,
                json={
                    "rt_cd": "0",
                    "output1": [domestic(), row(pdno="SOLD", hldg_qty="0")],
                },
            )

        async with httpx.AsyncClient(
            base_url=settings().kis_base_url, transport=httpx.MockTransport(handler)
        ) as client:
            result = await KisClient(settings(), client)._market("KRX", "KRW")
        assert len(result.holdings) == 1
        assert len(calls) == 2

    asyncio.run(run())


@pytest.mark.parametrize("conflict", [False, True])
def test_incomplete_or_conflicting_pages_fail(conflict: bool) -> None:
    async def run() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                headers={"tr_cont": "M"},
                json={
                    "rt_cd": "0",
                    "output1": [domestic(), row(prpr="111")] if conflict else [],
                    "ctx_area_fk100": "same",
                    "ctx_area_nk100": "same",
                },
            )

        async with httpx.AsyncClient(
            base_url=settings().kis_base_url, transport=httpx.MockTransport(handler)
        ) as client:
            with pytest.raises(BrokerError):
                await KisClient(settings(), client)._market("KRX", "KRW")

    asyncio.run(run())


def test_partial_failure_cache_and_no_order_calls() -> None:
    async def run() -> None:
        calls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request.url.path)
            if request.url.path == "/oauth2/tokenP":
                assert request.method == "POST"
                return httpx.Response(
                    200, json={"access_token": "test", "expires_in": 3600}
                )
            assert request.method == "GET"
            assert request.url.path.endswith("inquire-balance")
            if "domestic-stock" in request.url.path:
                return httpx.Response(200, json={"rt_cd": "0", "output1": [domestic()]})
            return httpx.Response(200, json={"rt_cd": "1", "msg1": "SECRET"})

        async with httpx.AsyncClient(
            base_url=settings().kis_base_url, transport=httpx.MockTransport(handler)
        ) as client:
            broker = KisClient(settings(), client)
            first, second = await asyncio.gather(broker.portfolio(), broker.portfolio())
            assert first == second
            assert len(calls) == 9
            assert len(first.totals) == 1
            assert sum(m.status == "error" for m in first.markets) == 7
            assert "SECRET" not in first.model_dump_json()

    asyncio.run(run())


def test_unapproved_host_cannot_receive_credentials() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            kis_app_key="test",
            kis_app_secret="test",
            kis_cano="00000000",
            kis_acnt_prdt_cd="00",
            kis_base_url="https://example.com",
        )
