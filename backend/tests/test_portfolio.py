import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx
import pytest
from pydantic import ValidationError
from pydantic_settings import SettingsError

from jusik.config import Settings
from jusik.kis import BrokerError, KisClient, normalize
from jusik.models import MarketResult, Portfolio, percentage, summarize


def domestic(**changes: object) -> dict[str, object]:
    return {
        "pdno": "TEST",
        "prdt_name": "Test holding",
        "hldg_qty": "2",
        "pchs_avg_pric": "100",
        "prpr": "110",
        "pchs_amt": "200",
        "evlu_amt": "220",
        "evlu_pfls_amt": "20",
    } | changes


def overseas(**changes: object) -> dict[str, object]:
    return {
        "ovrs_pdno": "TEST-US",
        "ovrs_item_name": "Test overseas holding",
        "ovrs_cblc_qty": "0.5",
        "pchs_avg_pric": "10",
        "now_pric2": "8",
        "frcr_pchs_amt1": "5",
        "ovrs_stck_evlu_amt": "4",
        "frcr_evlu_pfls_amt": "-1",
        "tr_crcy_cd": "USD",
    } | changes


def assets(**changes: object) -> dict[str, object]:
    return {
        "nass_tot_amt": "1000",
        "evlu_amt_smtl": "500",
        "tot_dncl_amt": "500",
        "evlu_pfls_amt_smtl": "20",
        "ovrs_stck_evlu_amt1": "100",
    } | changes


def settings(**changes: object) -> Settings:
    values: dict[str, Any] = {
        "_env_file": None,
        "kis_app_key": "global-key",
        "kis_app_secret": "global-secret",
        "kis_cano": "00000000",
        "kis_acnt_prdt_cd": "00",
        "kis_base_url": "https://openapi.koreainvestment.com:9443",
    }
    values.update(changes)
    return Settings(**values)


def run_portfolio(
    configured: Settings, handler: httpx.MockTransport
) -> tuple[Portfolio, KisClient]:
    async def run() -> tuple[Portfolio, KisClient]:
        async with httpx.AsyncClient(
            base_url=configured.kis_base_url, transport=handler
        ) as client:
            broker = KisClient(configured, client, request_interval_seconds=0)
            return await broker.portfolio(), broker

    return asyncio.run(run())


def success_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/oauth2/tokenP":
        return httpx.Response(200, json={"access_token": "token", "expires_in": 3600})
    if request.url.path.endswith("inquire-account-balance"):
        net_asset = "2000" if request.url.params["CANO"] == "11111111" else "1000"
        return httpx.Response(
            200,
            json={
                "rt_cd": "0",
                "output1": [],
                "output2": assets(nass_tot_amt=net_asset),
            },
        )
    rows: list[dict[str, object]] = []
    if "domestic-stock" in request.url.path:
        rows = [domestic()]
    elif request.url.params["OVRS_EXCG_CD"] == "NASD":
        rows = [overseas()]
    return httpx.Response(200, json={"rt_cd": "0", "output1": rows})


def test_legacy_configuration_creates_one_registered_account() -> None:
    account = settings().registered_accounts[0]
    assert (account.id, account.label) == ("default", "기본 계좌")
    assert account.cano.get_secret_value() == "00000000"


def test_multiple_accounts_inherit_or_override_credentials() -> None:
    configured = settings(
        kis_cano=None,
        kis_acnt_prdt_cd=None,
        kis_accounts=[
            {
                "id": "general",
                "label": "일반 계좌",
                "cano": "00000000",
                "acnt_prdt_cd": "01",
            },
            {
                "id": "isa",
                "label": "ISA",
                "cano": "11111111",
                "acnt_prdt_cd": "22",
                "app_key": "other-key",
                "app_secret": "other-secret",
            },
        ],
    )
    first, second = configured.registered_accounts
    assert first.app_key.get_secret_value() == "global-key"
    assert second.app_key.get_secret_value() == "other-key"


@pytest.mark.parametrize(
    ("app_key", "app_secret"),
    [("", "visible-secret"), ("   ", "visible-secret"), ("visible-key", "\t")],
)
def test_blank_global_credentials_are_rejected_without_exposure(
    app_key: str, app_secret: str
) -> None:
    with pytest.raises(ValidationError) as caught:
        settings(kis_app_key=app_key, kis_app_secret=app_secret)
    error = str(caught.value)
    assert "visible-key" not in error
    assert "visible-secret" not in error


@pytest.mark.parametrize(
    ("app_key", "app_secret"),
    [("", "account-visible-secret"), ("   ", "account-visible-secret"), ("key", "\n")],
)
def test_blank_account_credentials_are_rejected_before_inheritance(
    app_key: str, app_secret: str
) -> None:
    with pytest.raises(ValidationError) as caught:
        settings(
            kis_cano=None,
            kis_acnt_prdt_cd=None,
            kis_accounts=[
                {
                    "id": "one",
                    "label": "General",
                    "cano": "00000000",
                    "acnt_prdt_cd": "01",
                    "app_key": app_key,
                    "app_secret": app_secret,
                }
            ],
        )
    error = str(caught.value)
    assert "account-visible-secret" not in error
    assert "00000000" not in error


@pytest.mark.parametrize(
    "accounts",
    [
        [
            {"id": "same", "label": "A", "cano": "00000000", "acnt_prdt_cd": "01"},
            {"id": "same", "label": "B", "cano": "11111111", "acnt_prdt_cd": "01"},
        ],
        [
            {"id": "one", "label": "A", "cano": "00000000", "acnt_prdt_cd": "01"},
            {"id": "two", "label": "B", "cano": "00000000", "acnt_prdt_cd": "01"},
        ],
        [
            {
                "id": "one",
                "label": "A",
                "cano": "00000000",
                "acnt_prdt_cd": "01",
                "app_key": "private-key",
            }
        ],
        [{"id": "bad id", "label": "A", "cano": "00000000", "acnt_prdt_cd": "01"}],
        [{"id": "one", "label": "A", "cano": "account-secret", "acnt_prdt_cd": "01"}],
    ],
)
def test_invalid_account_configuration_is_rejected_without_secrets(
    accounts: list[dict[str, str]],
) -> None:
    with pytest.raises(ValidationError) as caught:
        settings(kis_cano=None, kis_acnt_prdt_cd=None, kis_accounts=accounts)
    error = str(caught.value)
    assert "account-secret" not in error
    assert "private-key" not in error


def test_malformed_accounts_json_does_not_expose_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    malformed = '[{"app_secret":"format-secret"'
    monkeypatch.setenv("KIS_ACCOUNTS", malformed)
    with pytest.raises((SettingsError, ValidationError)) as caught:
        settings()
    assert "format-secret" not in str(caught.value)


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
def test_percentage_rounds_half_up(
    profit: str, cost: str, expected: str | None
) -> None:
    result = percentage(Decimal(profit), Decimal(cost))
    assert result == (Decimal(expected) if expected is not None else None)


@pytest.mark.parametrize(
    "changes",
    [{"hldg_qty": "-1"}, {"prpr": ""}, {"evlu_amt": "NaN"}, {"pchs_amt": None}],
)
def test_invalid_holding_values_are_not_coerced_to_zero(
    changes: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        normalize(domestic(**changes), "KRX", "KRW")


def test_missing_holding_data_is_rejected() -> None:
    with pytest.raises(ValidationError):
        normalize({"pdno": "TEST"}, "KRX", "KRW")


def test_currency_totals_keep_decimal_precision_and_negative_profit() -> None:
    krw = normalize(domestic(), "KRX", "KRW")
    usd = krw.model_copy(
        update={
            "currency": "USD",
            "cost": Decimal("0.1"),
            "value": Decimal("0.3"),
            "profit": Decimal("-0.2"),
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
    assert totals[1].return_pct == Decimal("-200.00")


def test_weekend_timezone_stays_utc() -> None:
    at = datetime(2026, 9, 6, 23, 59, tzinfo=UTC)
    market = MarketResult(
        market="KRX",
        status="ok",
        fetched_at=at,
        holdings=[normalize(domestic(), "KRX", "KRW")],
    )
    assert summarize([market])[0].value == Decimal("220")
    assert market.model_dump(mode="json")["fetched_at"].endswith("Z")


def test_pagination_deduplicates_and_excludes_zero_quantity() -> None:
    async def run() -> None:
        calls: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request)
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
            return httpx.Response(
                200,
                json={
                    "rt_cd": "0",
                    "output1": [domestic(), domestic(pdno="SOLD", hldg_qty="0")],
                },
            )

        configured = settings()
        async with httpx.AsyncClient(
            base_url=configured.kis_base_url, transport=httpx.MockTransport(handler)
        ) as client:
            broker = KisClient(configured, client, request_interval_seconds=0)
            account = configured.registered_accounts[0]
            result = await broker._market(account, "token", "KRX", "KRW")
        assert len(result.holdings) == 1
        assert calls[1].headers["tr_cont"] == "N"
        assert calls[1].url.params["CTX_AREA_NK100"] == "next"

    asyncio.run(run())


def test_conflicting_duplicate_holding_fails_market() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "rt_cd": "0",
                "output1": [domestic(), domestic(prpr="111")],
            },
        )

    async def run() -> None:
        configured = settings()
        async with httpx.AsyncClient(
            base_url=configured.kis_base_url,
            transport=httpx.MockTransport(handler),
        ) as client:
            broker = KisClient(configured, client, request_interval_seconds=0)
            with pytest.raises(BrokerError):
                await broker._market(
                    configured.registered_accounts[0], "token", "KRX", "KRW"
                )

    asyncio.run(run())


def test_multiple_accounts_preserve_same_symbol_and_reuse_token() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return success_handler(request)

    configured = settings(
        kis_cano=None,
        kis_acnt_prdt_cd=None,
        kis_accounts=[
            {"id": "one", "label": "일반", "cano": "00000000", "acnt_prdt_cd": "01"},
            {"id": "two", "label": "ISA", "cano": "11111111", "acnt_prdt_cd": "22"},
        ],
    )
    result, _ = run_portfolio(configured, httpx.MockTransport(handler))
    portfolio = result
    assert portfolio.aggregate.net_asset == Decimal("3000")
    assert portfolio.aggregate.completeness == "complete"
    assert [
        account.markets[0].holdings[0].symbol for account in portfolio.accounts
    ] == [
        "TEST",
        "TEST",
    ]
    assert sum(call.url.path == "/oauth2/tokenP" for call in calls) == 1
    serialized = portfolio.model_dump_json()
    assert '"net_asset":"3000"' in serialized
    assert (
        next(total.value for total in portfolio.totals if total.currency == "KRW")
        == 440
    )
    assert "00000000" not in serialized
    assert "11111111" not in serialized
    assert "global-secret" not in serialized


def test_partial_account_failure_preserves_success_and_marks_aggregate_partial() -> (
    None
):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth2/tokenP":
            return success_handler(request)
        if request.url.params.get("CANO") == "11111111":
            return httpx.Response(200, json={"rt_cd": "1", "msg1": "PRIVATE DETAIL"})
        return success_handler(request)

    configured = settings(
        kis_cano=None,
        kis_acnt_prdt_cd=None,
        kis_accounts=[
            {"id": "one", "label": "일반", "cano": "00000000", "acnt_prdt_cd": "01"},
            {"id": "two", "label": "ISA", "cano": "11111111", "acnt_prdt_cd": "22"},
        ],
    )
    result, _ = run_portfolio(configured, httpx.MockTransport(handler))
    assert [account.status for account in result.accounts] == ["ok", "error"]
    assert result.aggregate.net_asset == Decimal("1000")
    assert result.aggregate.completeness == "partial"
    assert result.totals
    assert "PRIVATE DETAIL" not in result.model_dump_json()


def test_market_failure_keeps_other_parts_of_same_account() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth2/tokenP" or "domestic-stock" in request.url.path:
            return success_handler(request)
        return httpx.Response(200, json={"rt_cd": "1", "msg1": "PRIVATE DETAIL"})

    result, _ = run_portfolio(settings(), httpx.MockTransport(handler))
    account = result.accounts[0]
    assert account.status == "partial"
    assert account.asset_summary.status == "ok"
    assert account.markets[0].status == "ok"
    assert all(market.status == "error" for market in account.markets[1:])
    assert account.totals[0].currency == "KRW"
    assert "PRIVATE DETAIL" not in result.model_dump_json()


@pytest.mark.parametrize("all_fail", [False, True])
def test_zero_balance_is_distinct_from_all_queries_failing(all_fail: bool) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth2/tokenP":
            return success_handler(request)
        if all_fail:
            return httpx.Response(200, json={"rt_cd": "1"})
        if request.url.path.endswith("inquire-account-balance"):
            return httpx.Response(
                200,
                json={
                    "rt_cd": "0",
                    "output1": [],
                    "output2": assets(
                        nass_tot_amt="0",
                        evlu_amt_smtl="0",
                        tot_dncl_amt="0",
                        evlu_pfls_amt_smtl="0",
                        ovrs_stck_evlu_amt1="0",
                    ),
                },
            )
        return httpx.Response(200, json={"rt_cd": "0", "output1": []})

    result, _ = run_portfolio(settings(), httpx.MockTransport(handler))
    account = result.accounts[0]
    if all_fail:
        assert account.status == "error"
        assert result.aggregate.completeness == "unavailable"
        assert result.aggregate.net_asset is None
    else:
        assert account.status == "ok"
        assert result.aggregate.completeness == "complete"
        assert result.aggregate.net_asset == 0
        assert account.totals == []


def test_asset_summary_missing_fields_stay_null_and_invalid_numbers_fail() -> None:
    responses = iter(
        [
            {"rt_cd": "0", "output1": [], "output2": {"nass_tot_amt": "-10"}},
            {"rt_cd": "0", "output1": [], "output2": {"nass_tot_amt": "NaN"}},
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=next(responses))

    async def run() -> None:
        configured = settings()
        account = configured.registered_accounts[0]
        async with httpx.AsyncClient(
            base_url=configured.kis_base_url, transport=httpx.MockTransport(handler)
        ) as client:
            broker = KisClient(configured, client, request_interval_seconds=0)
            result = await broker._asset_summary(account, "token")
            assert result.summary is not None
            assert result.summary.net_asset == Decimal("-10")
            assert result.summary.cash is None
            with pytest.raises(ValidationError):
                await broker._asset_summary(account, "token")

    asyncio.run(run())


def test_cache_coalesces_requests_and_never_calls_order_api() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return success_handler(request)

    async def run() -> None:
        configured = settings()
        async with httpx.AsyncClient(
            base_url=configured.kis_base_url, transport=httpx.MockTransport(handler)
        ) as client:
            broker = KisClient(configured, client, request_interval_seconds=0)
            first, second = await asyncio.gather(broker.portfolio(), broker.portfolio())
            assert first == second

    asyncio.run(run())
    assert len(calls) == 10
    assert all("order" not in path for path in calls)


def test_unapproved_host_cannot_receive_credentials() -> None:
    with pytest.raises(ValidationError):
        settings(kis_base_url="https://example.com")
