import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx

from jusik.fx import FxService, krw
from jusik.models import (
    AccountResult,
    AssetSummaryResult,
    Fundamentals,
    Holding,
    InvestmentAdvice,
    MarketResult,
)
from jusik.signals import evaluate_holding


def holding(**changes: object) -> Holding:
    values: dict[str, object] = {
        "market": "US",
        "symbol": "TEST",
        "name": "Test",
        "currency": "USD",
        "quantity": "1",
        "average_price": "10",
        "current_price": "11",
        "cost": "10",
        "value": "11",
        "profit": "1",
        "return_pct": "10",
    }
    values.update(changes)
    return Holding.model_validate(values)


def account(holdings: list[Holding]) -> AccountResult:
    return AccountResult(
        id="test",
        label="테스트",
        status="ok",
        asset_summary=AssetSummaryResult(status="error", error="fixture"),
        markets=[MarketResult(market="US", status="ok", holdings=holdings)],
        totals=[],
    )


def test_fx_uses_direct_decimal_rate_and_rounds_won_half_up() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v2/rate/USD/KRW"
        return httpx.Response(
            200,
            text=('{"date":"2026-09-07","base":"USD","quote":"KRW","rate":1351.445}'),
        )

    async def run() -> None:
        async with httpx.AsyncClient(
            base_url="https://api.frankfurter.dev",
            transport=httpx.MockTransport(handler),
        ) as client:
            converted, rates, total, completeness = await FxService(
                client
            ).convert_accounts([account([holding(value="1.005", cost="1")])])
        result = converted[0].markets[0].holdings[0]
        assert rates[1].krw_per_unit == Decimal("1351.445")
        assert result.value_krw == Decimal("1358")
        assert total is not None
        assert total.value == Decimal("1358")
        assert completeness == "complete"

    asyncio.run(run())
    assert krw(Decimal("0.5"), Decimal("1")) == Decimal("1")


def test_missing_zero_negative_or_future_rate_never_creates_partial_total() -> None:
    responses = iter(
        [
            httpx.Response(503),
            httpx.Response(
                200,
                text=('{"date":"2026-09-07","base":"USD","quote":"KRW","rate":0}'),
            ),
            httpx.Response(
                200,
                text=('{"date":"2099-01-01","base":"USD","quote":"KRW","rate":1300}'),
            ),
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return next(responses)

    async def run() -> None:
        async with httpx.AsyncClient(
            base_url="https://api.frankfurter.dev",
            transport=httpx.MockTransport(handler),
        ) as client:
            for _ in range(3):
                _, rates, total, completeness = await FxService(
                    client, cache_seconds=0
                ).convert_accounts([account([holding()])])
                assert rates[1].status == "error"
                assert total is None
                assert completeness == "unavailable"

    asyncio.run(run())


def test_weekend_tolerance_keeps_recent_rate_but_rejects_six_day_old_rate() -> None:
    dates = iter(
        [
            (datetime.now(UTC) - timedelta(days=3)).date().isoformat(),
            (datetime.now(UTC) - timedelta(days=6)).date().isoformat(),
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        observed = next(dates)
        return httpx.Response(
            200,
            text=(f'{{"date":"{observed}","base":"USD","quote":"KRW","rate":1300}}'),
        )

    async def run() -> None:
        async with httpx.AsyncClient(
            base_url="https://api.frankfurter.dev",
            transport=httpx.MockTransport(handler),
        ) as client:
            service = FxService(client, cache_seconds=0)
            _, _, recent_total, recent = await service.convert_accounts(
                [account([holding()])]
            )
            _, rates, old_total, old = await service.convert_accounts(
                [account([holding()])]
            )
        assert recent == "complete"
        assert recent_total is not None
        assert rates[1].stale is True
        assert old == "unavailable"
        assert old_total is None

    asyncio.run(run())


def test_broker_validated_conversion_is_not_overwritten_by_reference_rate() -> None:
    async def run() -> None:
        async with httpx.AsyncClient(
            base_url="https://api.frankfurter.dev",
            transport=httpx.MockTransport(
                lambda request: (_ for _ in ()).throw(
                    AssertionError(f"Unexpected reference request: {request.url}")
                )
            ),
        ) as client:
            original = holding(
                fx_rate="1300",
                fx_source="키움 계좌 기준환율",
                average_price_krw="13000",
                current_price_krw="14300",
                cost_krw="13000",
                value_krw="14300",
                profit_krw="1300",
            )
            accounts, rates, total, completeness = await FxService(
                client
            ).convert_accounts([account([original])])
        converted = accounts[0].markets[0].holdings[0]
        assert converted.fx_rate == Decimal("1300")
        assert converted.fx_source == "키움 계좌 기준환율"
        assert converted.value_krw == Decimal("14300")
        assert [rate.currency for rate in rates] == ["KRW"]
        assert total is not None and total.value == Decimal("14300")
        assert completeness == "complete"

    asyncio.run(run())


def test_signal_rules_require_positive_eps_and_fresh_value_metric() -> None:
    now = datetime(2026, 9, 7, tzinfo=UTC)
    good = holding(
        fundamentals=Fundamentals(
            status="ok", per="12", pbr="2", eps="3", fetched_at=now
        )
    )
    assert evaluate_holding(good, now=now).signal == "buy_review"
    negative_eps = good.model_copy(
        update={
            "fundamentals": good.fundamentals.model_copy(update={"eps": Decimal("-1")})
        }
    )
    assert evaluate_holding(negative_eps, now=now).signal == "hold"
    stale = good.model_copy(
        update={
            "fundamentals": good.fundamentals.model_copy(
                update={"fetched_at": now - timedelta(hours=49)}
            )
        }
    )
    assert evaluate_holding(stale, now=now).signal == "insufficient"
    future = good.model_copy(
        update={
            "fundamentals": good.fundamentals.model_copy(
                update={"fetched_at": now + timedelta(hours=1)}
            )
        }
    )
    assert evaluate_holding(future, now=now).signal == "insufficient"


def test_return_thresholds_work_without_fundamentals() -> None:
    assert evaluate_holding(holding(return_pct="-12")).signal == "sell_review"
    assert evaluate_holding(holding(return_pct="25")).signal == "sell_review"
    assert evaluate_holding(holding(return_pct=None)).signal == "insufficient"


def test_etf_skips_value_rule_but_keeps_risk_threshold() -> None:
    now = datetime.now(UTC)
    etf = holding(
        fundamentals=Fundamentals(
            status="ok",
            per="1",
            pbr="0.1",
            eps="100",
            instrument_type="ETF · ETF(실물복제/수익증권)",
            fetched_at=now,
        )
    )
    result = evaluate_holding(etf, now=now)
    assert result.signal == "hold"
    assert "ETF" in result.reasons[0]
    assert (
        evaluate_holding(etf.model_copy(update={"return_pct": Decimal("-12")})).signal
        == "sell_review"
    )


def test_alert_model_keeps_advice_type_explicit() -> None:
    result = holding(advice=InvestmentAdvice(signal="hold", label="보유 검토"))
    assert result.advice.signal == "hold"


def test_decimal_json_never_uses_scientific_notation() -> None:
    result = holding(
        quantity=Decimal("1E-8"),
        average_price=Decimal("1E+3"),
        current_price=Decimal("1E+3"),
        cost=Decimal("1E+3"),
        value=Decimal("1E+3"),
        profit=Decimal("-2.5E-4"),
    ).model_dump(mode="json")
    assert result["quantity"] == "0.00000001"
    assert result["average_price"] == "1000"
    assert result["profit"] == "-0.00025"
