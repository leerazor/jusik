import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from typing import cast

import httpx

from jusik.config import RegisteredAccount
from jusik.kis import BrokerError, KisClient
from jusik.market_data import MarketDataService
from jusik.models import Holding
from jusik.news import NewsService, parse_bok_rate, parse_fed_rate


def make_us_holding(*, market: str = "NASD", symbol: str = "COHR") -> Holding:
    return Holding(
        market=market,
        symbol=symbol,
        name=symbol,
        currency="USD",
        quantity=Decimal("1"),
        average_price=Decimal("10"),
        current_price=Decimal("11"),
        cost=Decimal("10"),
        value=Decimal("11"),
        profit=Decimal("1"),
        return_pct=Decimal("10"),
        price_fetched_at=datetime.now(UTC),
    )


class OverseasQuoteStub:
    def __init__(
        self,
        quotes: dict[str, dict[str, object]],
    ) -> None:
        self.quotes = quotes
        self.quote_calls: list[str] = []

    async def _get(self, *args: object, **kwargs: object) -> httpx.Response:
        path = cast(str, args[2])
        params = cast(dict[str, str], args[4])
        assert path.endswith("/price-detail")
        exchange = params["EXCD"]
        self.quote_calls.append(exchange)
        return httpx.Response(
            200,
            json={"rt_cd": "0", "output": self.quotes.get(exchange, {})},
        )

    @staticmethod
    def _accepted_json(response: httpx.Response) -> dict[str, object]:
        result = cast(dict[str, object], response.json())
        if result.get("rt_cd") != "0":
            raise BrokerError("not found")
        return result


def test_us_quote_skips_empty_quote_for_stale_exchange_listing() -> None:
    quotes = {
        "NAS": {},
        "NYS": {
            "rsym": "DNYSCOHR",
            "curr": "USD",
            "last": "81.25",
            "perx": "12.50",
            "pbrx": "1.20",
            "epsx": "4.50",
            "bpsx": "50.00",
        },
    }

    async def run() -> None:
        broker = OverseasQuoteStub(quotes)
        service = MarketDataService(cast(KisClient, broker))
        result = await service._holding(
            cast(RegisteredAccount, object()), "token", make_us_holding()
        )
        assert result.status == "ok"
        assert result.per == Decimal("12.50")
        assert broker.quote_calls == ["NAS", "NYS"]

    asyncio.run(run())


def test_us_quote_identifies_etf_without_search_ticker() -> None:
    quotes = {
        "AMS": {
            "rsym": "DAMSRAM",
            "curr": "USD",
            "last": "10.00",
            "perx": "0.00",
            "pbrx": "0.00",
            "epsx": "0.00",
            "bpsx": "0.00",
            "etyp_nm": "ETF",
        }
    }

    async def run() -> None:
        broker = OverseasQuoteStub(quotes)
        service = MarketDataService(cast(KisClient, broker))
        result = await service._holding(
            cast(RegisteredAccount, object()),
            "token",
            make_us_holding(symbol="RAM"),
        )
        assert result.status == "unavailable"
        assert result.instrument_type == "ETF"
        assert result.per is None
        assert result.pbr is None
        assert result.eps is None
        assert broker.quote_calls == ["NAS", "NYS", "AMS"]

    asyncio.run(run())


def test_known_exchange_quote_rejects_symbol_and_currency_mismatch() -> None:
    async def run() -> None:
        cases = (
            {"rsym": "DNYSOTHER", "curr": "USD", "last": "10"},
            {"rsym": "DNYSCOHR", "curr": "EUR", "last": "10"},
        )
        for output in cases:
            broker = OverseasQuoteStub({"NYS": output})
            service = MarketDataService(cast(KisClient, broker))
            result = await service._holding(
                cast(RegisteredAccount, object()),
                "token",
                make_us_holding(market="NYSE"),
            )
            assert result.status == "error"
            assert broker.quote_calls == ["NYS"]

    asyncio.run(run())


def test_official_rate_parsers_use_dated_rows_and_reject_future_bok_data() -> None:
    bok = """
    <table><caption>한국은행 기준금리 추이</caption><tbody>
    <tr><th>2026</th><td>08월 27일</td><td>3.00</td></tr>
    </tbody></table>
    """
    rate, observed = parse_bok_rate(bok)
    assert str(rate) == "3.00"
    assert observed.isoformat() == "2026-08-27"
    fed = "observation_date,DFEDTARL,DFEDTARU\n2026-09-06,3.50,3.75\n"
    target, target_date = parse_fed_rate(fed)
    assert target == "3.50%–3.75%"
    assert target_date.isoformat() == "2026-09-06"


def test_news_provider_retains_successful_sources_when_one_source_fails() -> None:
    rss = """<?xml version="1.0"?><rss><channel><item>
    <title>Policy update</title><link>https://example.com/item</link>
    <pubDate>Sun, 06 Sep 2026 10:00:00 GMT</pubDate>
    </item></channel></rss>"""
    bok = """
    <table><caption>한국은행 기준금리 추이</caption><tbody>
    <tr><th>2026</th><td>08월 27일</td><td>3.00</td></tr>
    </tbody></table>
    """
    fed = "observation_date,DFEDTARL,DFEDTARU\n2026-09-06,3.50,3.75\n"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "feeds.bbci.co.uk":
            return httpx.Response(503)
        if request.url.host == "www.bok.or.kr" and "baseRate" in request.url.path:
            return httpx.Response(200, text=bok)
        if request.url.host == "fred.stlouisfed.org":
            return httpx.Response(200, text=fed)
        return httpx.Response(200, text=rss)

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await NewsService(client).intelligence()
        statuses = {source.id: source.status for source in result.sources}
        assert statuses["world"] == "error"
        assert statuses["fed_news"] == "ok"
        assert result.us_target_rate == "3.50%–3.75%"
        assert result.news

    asyncio.run(run())
