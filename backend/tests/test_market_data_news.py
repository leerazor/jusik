import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from typing import cast

import httpx

from jusik.config import RegisteredAccount
from jusik.kis import BrokerError, KisClient
from jusik.market_data import MarketDataService
from jusik.models import Holding
from jusik.news import (
    NewsService,
    parse_bok_rate,
    parse_fed_rate,
    parse_truth_archive_rss,
)


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


def truth_feed(*items: str) -> str:
    return (
        '<?xml version="1.0"?><rss xmlns:truthsocial="https://truthsocial.com/ns">'
        f"<channel>{''.join(items)}</channel></rss>"
    )


def truth_item(
    identifier: int,
    *,
    title: str = "[No Title] media",
    archive_url: str | None = None,
    original_url: str | None = None,
    description: str = "<p>Update &amp; context</p>",
) -> str:
    archive = archive_url or f"https://www.trumpstruth.org/statuses/{identifier}"
    original = original_url or f"https://truthsocial.com/@example/{identifier}"
    return (
        "<item>"
        f"<title>{title}</title><link>{archive}</link>"
        f"<description><![CDATA[{description}]]></description>"
        "<pubDate>Sun, 06 Sep 2026 10:00:00 GMT</pubDate>"
        f"<truthsocial:originalUrl>{original}</truthsocial:originalUrl>"
        "</item>"
    )


def test_truth_archive_parser_sanitizes_html_and_validates_both_urls() -> None:
    long_text = "word " * 100
    feed = truth_feed(
        truth_item(
            101,
            description=(
                f"<style>hidden</style><p>{long_text}&amp; visible</p>"
                "<script>private()</script>"
            ),
        ),
        truth_item(
            102,
            archive_url="https://www.trumpstruth.org.evil.invalid/statuses/102",
        ),
        truth_item(
            103,
            title="Policy note",
            original_url="https://truthsocial.com.evil.invalid/@example/103",
        ),
    )

    items = parse_truth_archive_rss(feed)

    assert len(items) == 2
    assert items[0].title == "트럼프 계정 게시물 (제목 없음)"
    assert items[0].original_url == "https://truthsocial.com/@example/101"
    assert items[0].excerpt is not None
    assert len(items[0].excerpt) == 280
    assert "hidden" not in items[0].excerpt
    assert "private" not in items[0].excerpt
    assert items[1].original_url is None
    assert "재게시물" in items[0].assessment
    assert "실제 정책" in items[0].assessment


def test_truth_archive_supports_official_path_shapes_and_rejects_unsafe_urls() -> None:
    feed = truth_feed(
        truth_item(
            201,
            original_url="https://truthsocial.com/users/example/statuses/201",
        ),
        truth_item(
            202,
            original_url="https://truthsocial.com/@example/posts/202",
        ),
        truth_item(
            203,
            original_url="https://user@truthsocial.com/@example/203",
        ),
        truth_item(
            204,
            archive_url="https://trumpstruth.org:443/statuses/204",
        ),
    )

    items = parse_truth_archive_rss(feed)

    assert [item.url for item in items] == [
        "https://www.trumpstruth.org/statuses/201",
        "https://www.trumpstruth.org/statuses/202",
        "https://www.trumpstruth.org/statuses/203",
    ]
    assert items[0].original_url is not None
    assert items[1].original_url is not None
    assert items[2].original_url is None


def test_news_service_keeps_all_five_categories_and_deduplicates_archive() -> None:
    rss = """<?xml version="1.0"?><rss><channel><item>
    <title>{title}</title><link>{url}</link>
    <pubDate>Sun, 06 Sep 2026 10:00:00 GMT</pubDate>
    </item></channel></rss>"""
    bok = """
    <table><caption>한국은행 기준금리 추이</caption><tbody>
    <tr><th>2026</th><td>08월 27일</td><td>3.00</td></tr>
    </tbody></table>
    """
    fed = "observation_date,DFEDTARL,DFEDTARU\n2026-09-06,3.50,3.75\n"
    archive = truth_feed(truth_item(301), truth_item(301, title="Duplicate"))

    def handler(request: httpx.Request) -> httpx.Response:
        if "baseRate" in request.url.path:
            return httpx.Response(200, text=bok)
        if request.url.host == "fred.stlouisfed.org":
            return httpx.Response(200, text=fed)
        if request.url.host == "www.trumpstruth.org":
            return httpx.Response(200, text=archive)
        values = {
            "www.bok.or.kr": ("Korea", "https://example.com/korea"),
            "www.federalreserve.gov": ("US", "https://example.com/us"),
            "feeds.bbci.co.uk": ("World", "https://example.com/world"),
        }
        title, url = values.get(
            request.url.host or "",
            ("Truth report", "https://example.com/truth-report"),
        )
        return httpx.Response(200, text=rss.format(title=title, url=url))

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await NewsService(client).intelligence()
        assert {item.category for item in result.news} == {
            "korea_rate",
            "us_rate",
            "geopolitics",
            "truth_social",
            "truth_social_post",
        }
        assert sum(item.category == "truth_social_post" for item in result.news) == 1
        assert len(result.news) <= 25
        assert len(result.sources) == 7

    asyncio.run(run())


def test_truth_archive_source_failure_uses_stale_cached_feed() -> None:
    generic_rss = """<rss><channel><item><title>Update</title>
    <link>https://example.com/update</link></item></channel></rss>"""
    bok = """<table><caption>한국은행 기준금리 추이</caption><tbody>
    <tr><th>2026</th><td>08월 27일</td><td>3.00</td></tr>
    </tbody></table>"""
    fed = "observation_date,DFEDTARL,DFEDTARU\n2026-09-06,3.50,3.75\n"
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        if "baseRate" in request.url.path:
            return httpx.Response(200, text=bok)
        if request.url.host == "fred.stlouisfed.org":
            return httpx.Response(200, text=fed)
        if request.url.host == "www.trumpstruth.org":
            requests += 1
            if requests == 2:
                return httpx.Response(503)
            return httpx.Response(200, text=truth_feed(truth_item(401)))
        return httpx.Response(200, text=generic_rss)

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            service = NewsService(client, cache_seconds=0)
            first = await service.intelligence()
            second = await service.intelligence()
        assert any(item.category == "truth_social_post" for item in first.news)
        status = next(
            source for source in second.sources if source.id == "truth_archive"
        )
        assert status.status == "error"
        assert status.stale is True
        assert any(item.category == "truth_social_post" for item in second.news)

    asyncio.run(run())
