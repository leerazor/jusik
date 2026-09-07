import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import ValidationError

from jusik.kiwoom import KiwoomClient
from jusik.kiwoom_config import KiwoomSettings, load_kiwoom_settings


def settings(**changes: object) -> KiwoomSettings:
    values: dict[str, Any] = {
        "_env_file": None,
        "APP_ENV": "kiwum",
        "APP_KEY": "key",
        "APP_SECRET": "secret",
        "CANO": "12345678",
        "ACNT_PRDT_CD": "90",
        "BASE_URL": "https://api.kiwoom.com/oauth2/token",
    }
    values.update(changes)
    return KiwoomSettings(**values)


def credential_only_settings(**changes: object) -> KiwoomSettings:
    return settings(CANO=None, ACNT_PRDT_CD=None, **changes)


def domestic_row(**changes: object) -> dict[str, object]:
    return {
        "stk_cd": "A005930",
        "stk_nm": "삼성전자",
        "rmnd_qty": "2",
        "pur_pric": "100",
        "cur_prc": "+110",
        "pur_amt": "200",
        "evlt_amt": "220",
        "evltv_prft": "20",
        "crd_tp": "00",
        "crd_loan_dt": "",
    } | changes


def domestic_page(**changes: object) -> dict[str, object]:
    return {
        "return_code": 0,
        "tot_pur_amt": "200",
        "tot_evlt_amt": "220",
        "tot_evlt_pl": "20",
        "prsm_dpst_aset_amt": "1020",
        "acnt_evlt_remn_indv_tot": [domestic_row()],
    } | changes


def overseas_row(**changes: object) -> dict[str, object]:
    return {
        "crnc_code": "USD",
        "stk_cd": "AAPL",
        "frgn_stk_nm": "Apple",
        "poss_qty": "0.5",
        "frgn_stk_book_uv": "200.10",
        "now_pric": "-210.20",
        "frgn_stk_book_amt": "100.05",
        "evlt_amt": "105.10",
        "pl_amt": "-1.25",
    } | changes


def success_handler(request: httpx.Request) -> httpx.Response:
    api_id = request.headers.get("api-id")
    if api_id == "au10001":
        return httpx.Response(
            200,
            json={
                "return_code": 0,
                "token": "token",
                "token_type": "bearer",
                "expires_dt": "20991231235959",
            },
        )
    if api_id == "ka00001":
        return httpx.Response(200, json={"return_code": 0, "acctNo": "1234567890"})
    if api_id == "kt00018":
        return httpx.Response(200, json=domestic_page())
    if api_id == "kt00001":
        return httpx.Response(200, json={"return_code": 0, "entr": "800"})
    if api_id == "ust21070":
        assert request.read() == b"{}"
        return httpx.Response(
            200, json={"return_code": 0, "result_list": [overseas_row()]}
        )
    raise AssertionError(f"Unexpected API id: {api_id}")


def run_account(
    configured: KiwoomSettings, handler: httpx.MockTransport
) -> tuple[object, KiwoomClient]:
    async def run() -> tuple[object, KiwoomClient]:
        async with httpx.AsyncClient(
            base_url=configured.base_url, transport=handler
        ) as client:
            broker = KiwoomClient(configured, client, request_interval_seconds=0)
            return await broker.account(), broker

    return asyncio.run(run())


def test_settings_normalize_official_token_url_and_optional_file(
    tmp_path: Path,
) -> None:
    assert settings().base_url == "https://api.kiwoom.com"
    assert load_kiwoom_settings(tmp_path / "missing") is None
    with pytest.raises(ValidationError):
        settings(BASE_URL="https://example.com/oauth2/token")
    with pytest.raises(ValidationError):
        settings(BASE_URL="https://api.kiwoom.com.evil.test")


def test_loader_accepts_credential_only_environment(tmp_path: Path) -> None:
    env_file = tmp_path / ".env.kiwum"
    env_file.write_text(
        "\n".join(
            (
                "APP_ENV=kiwum",
                "APP_KEY=credential-only-key",
                "APP_SECRET=credential-only-secret",
                "BASE_URL=https://api.kiwoom.com/oauth2/token",
            )
        ),
        encoding="utf-8",
    )

    configured = load_kiwoom_settings(env_file)

    assert configured is not None
    assert configured.account_number is None
    assert configured.base_url == "https://api.kiwoom.com"


@pytest.mark.parametrize(
    ("changes", "private_value"),
    [
        ({"CANO": "12345678", "ACNT_PRDT_CD": None}, "12345678"),
        ({"CANO": None, "ACNT_PRDT_CD": "90"}, "90"),
        ({"CANO": "", "ACNT_PRDT_CD": "90"}, "90"),
        ({"CANO": "1234567X", "ACNT_PRDT_CD": "90"}, "1234567X"),
        ({"CANO": "12345678", "ACNT_PRDT_CD": ""}, "12345678"),
        ({"CANO": "12345678", "ACNT_PRDT_CD": "9X"}, "12345678"),
    ],
)
def test_optional_account_pair_rejects_incomplete_blank_or_malformed_values(
    changes: dict[str, object], private_value: str
) -> None:
    with pytest.raises(ValidationError) as exc_info:
        settings(**changes)

    assert private_value not in str(exc_info.value)


def test_settings_repr_redacts_credentials_and_optional_account() -> None:
    dumped = repr(settings(APP_KEY="private-key", APP_SECRET="private-secret"))

    assert "private-key" not in dumped
    assert "private-secret" not in dumped
    assert "1234567890" not in dumped


def test_success_maps_domestic_lots_us_decimal_and_asset_scope() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.headers.get("api-id") == "kt00018":
            return httpx.Response(
                200,
                json=domestic_page(
                    tot_pur_amt="500",
                    tot_evlt_amt="550",
                    tot_evlt_pl="-10",
                    acnt_evlt_remn_indv_tot=[
                        domestic_row(),
                        domestic_row(
                            rmnd_qty="3",
                            pur_pric="100",
                            pur_amt="300",
                            evlt_amt="330",
                            evltv_prft="-30",
                            crd_tp="03",
                            crd_loan_dt="20260102",
                        ),
                    ],
                ),
            )
        return success_handler(request)

    result, _ = run_account(settings(), httpx.MockTransport(handler))
    assert result.status == "ok"
    assert result.broker == "kiwoom"
    assert result.asset_summary.summary.net_asset is None
    assert result.asset_summary.summary.scope == "domestic"
    assert result.asset_summary.summary.estimated_deposit_assets == Decimal("1020")
    domestic = result.markets[0].holdings[0]
    assert domestic.symbol == "005930"
    assert domestic.quantity == Decimal("5")
    assert domestic.average_price == Decimal("100")
    assert domestic.current_price == Decimal("110")
    assert domestic.profit == Decimal("-10")
    us = result.markets[1].holdings[0]
    assert us.quantity == Decimal("0.5")
    assert us.current_price == Decimal("210.20")
    assert us.profit == Decimal("-1.25")


def test_discovered_account_is_validated_without_being_stored_or_returned() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.headers["api-id"])
        return success_handler(request)

    result, broker = run_account(
        credential_only_settings(), httpx.MockTransport(handler)
    )

    assert result.status == "ok"
    assert calls[0:2] == ["au10001", "ka00001"]
    assert credential_only_settings().account_number is None
    assert "1234567890" not in result.model_dump_json()
    assert "acctNo" not in repr(broker.__dict__)


def test_invalid_discovered_account_stops_before_balance_queries() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        api_id = request.headers["api-id"]
        calls.append(api_id)
        if api_id == "ka00001":
            return httpx.Response(
                200,
                json={"return_code": 0, "acctNo": "invalid-private-account"},
            )
        return success_handler(request)

    result, _ = run_account(credential_only_settings(), httpx.MockTransport(handler))

    assert result.status == "error"
    assert calls == ["au10001", "ka00001"]
    assert "invalid-private-account" not in result.model_dump_json()


def test_account_mismatch_stops_before_balance_queries() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        api_id = request.headers["api-id"]
        calls.append(api_id)
        if api_id == "ka00001":
            return httpx.Response(200, json={"return_code": 0, "acctNo": "0000000000"})
        return success_handler(request)

    result, _ = run_account(settings(), httpx.MockTransport(handler))
    assert result.status == "error"
    assert calls == ["au10001", "ka00001"]
    assert "1234567890" not in result.model_dump_json()


def test_terminal_auth_error_is_helpful_and_sanitized() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "return_code": 3,
                "return_msg": "8050 PRIVATE TERMINAL DETAIL",
            },
        )

    result, _ = run_account(settings(), httpx.MockTransport(handler))
    dumped = result.model_dump_json()
    assert "지정단말기 인증" in dumped
    assert "PRIVATE TERMINAL DETAIL" not in dumped


def test_boolean_auth_return_code_is_rejected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "return_code": False,
                "token": "token",
                "token_type": "bearer",
                "expires_dt": "20991231235959",
            },
        )

    result, _ = run_account(settings(), httpx.MockTransport(handler))
    assert result.status == "error"
    assert "키움 인증에 실패" in result.model_dump_json()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("rmnd_qty", "-1"),
        ("pur_amt", "NaN"),
        ("evltv_prft", None),
    ],
)
def test_invalid_domestic_values_fail_only_domestic_part(
    field: str, value: object
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.headers.get("api-id") == "kt00018":
            return httpx.Response(
                200,
                json=domestic_page(
                    acnt_evlt_remn_indv_tot=[domestic_row(**{field: value})]
                ),
            )
        return success_handler(request)

    result, _ = run_account(settings(), httpx.MockTransport(handler))
    assert result.status == "partial"
    assert result.markets[0].status == "error"
    assert result.markets[1].status == "ok"
    assert result.asset_summary.summary.cash == Decimal("800")


def test_failed_later_us_page_discards_partial_rows_and_retains_domestic() -> None:
    us_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal us_calls
        if request.headers.get("api-id") == "ust21070":
            us_calls += 1
            if us_calls == 1:
                return httpx.Response(
                    200,
                    headers={"cont-yn": "Y", "next-key": "us-next"},
                    json={"return_code": 0, "result_list": [overseas_row()]},
                )
            assert request.headers["cont-yn"] == "Y"
            assert request.headers["next-key"] == "us-next"
            return httpx.Response(200, json={"return_code": 1, "return_msg": "PRIVATE"})
        return success_handler(request)

    result, _ = run_account(settings(), httpx.MockTransport(handler))
    assert result.status == "partial"
    assert result.markets[0].status == "ok"
    assert result.markets[1].status == "error"
    assert result.markets[1].holdings == []
    assert us_calls == 2
    assert "PRIVATE" not in result.model_dump_json()


def test_successful_us_pagination_deduplicates_an_identical_position() -> None:
    us_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal us_calls
        if request.headers.get("api-id") == "ust21070":
            assert request.read() == b"{}"
            us_calls += 1
            if us_calls == 1:
                return httpx.Response(
                    200,
                    headers={"cont-yn": "Y", "next-key": "us-next"},
                    json={"return_code": 0, "result_list": [overseas_row()]},
                )
            return httpx.Response(
                200, json={"return_code": 0, "result_list": [overseas_row()]}
            )
        return success_handler(request)

    result, _ = run_account(settings(), httpx.MockTransport(handler))

    assert us_calls == 2
    assert result.markets[1].status == "ok"
    assert len(result.markets[1].holdings) == 1


def test_conflicting_duplicate_us_position_fails_the_us_market() -> None:
    us_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal us_calls
        if request.headers.get("api-id") == "ust21070":
            us_calls += 1
            if us_calls == 1:
                return httpx.Response(
                    200,
                    headers={"cont-yn": "Y", "next-key": "us-next"},
                    json={"return_code": 0, "result_list": [overseas_row()]},
                )
            return httpx.Response(
                200,
                json={
                    "return_code": 0,
                    "result_list": [overseas_row(evlt_amt="999")],
                },
            )
        return success_handler(request)

    result, _ = run_account(settings(), httpx.MockTransport(handler))

    assert result.status == "partial"
    assert result.markets[0].status == "ok"
    assert result.markets[1].status == "error"
    assert result.markets[1].holdings == []


def test_pagination_deduplicates_rows_and_rejects_repeated_cursor() -> None:
    domestic_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal domestic_calls
        if request.headers.get("api-id") == "kt00018":
            domestic_calls += 1
            headers = {"cont-yn": "Y", "next-key": "same"}
            return httpx.Response(200, headers=headers, json=domestic_page())
        return success_handler(request)

    result, _ = run_account(settings(), httpx.MockTransport(handler))
    assert domestic_calls == 2
    assert result.markets[0].status == "error"
    assert result.markets[1].status == "ok"


def test_successful_pagination_deduplicates_an_identical_position() -> None:
    domestic_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal domestic_calls
        if request.headers.get("api-id") == "kt00018":
            domestic_calls += 1
            if domestic_calls == 1:
                return httpx.Response(
                    200,
                    headers={"cont-yn": "Y", "next-key": "next"},
                    json=domestic_page(),
                )
            assert request.headers["cont-yn"] == "Y"
            assert request.headers["next-key"] == "next"
            return httpx.Response(200, json=domestic_page())
        return success_handler(request)

    result, _ = run_account(settings(), httpx.MockTransport(handler))
    assert result.markets[0].status == "ok"
    assert result.markets[0].holdings[0].quantity == Decimal("2")


def test_cache_and_lock_coalesce_concurrent_calls_and_parse_expiry_as_kst() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.headers["api-id"])
        return success_handler(request)

    async def run() -> KiwoomClient:
        configured = settings()
        async with httpx.AsyncClient(
            base_url=configured.base_url, transport=httpx.MockTransport(handler)
        ) as client:
            broker = KiwoomClient(configured, client, request_interval_seconds=0)
            first, second = await asyncio.gather(broker.account(), broker.account())
            assert first == second
            return broker

    broker = asyncio.run(run())
    assert calls.count("au10001") == 1
    assert len(calls) == 5
    assert broker._token is not None
    assert broker._token.expires_at == datetime(2099, 12, 31, 14, 59, 59, tzinfo=UTC)
    assert all(not api_id.startswith(("kt100", "ust200")) for api_id in calls)
