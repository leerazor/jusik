import os
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from fastapi import FastAPI, Response

from jusik.investor_analysis import analyze, evaluate_trend
from jusik.investor_api import router as investor_router
from jusik.investor_data import InMemoryInvestorProvider
from jusik.investor_models import (
    Candidate,
    DailyBar,
    DiscoveryCounts,
    DiscoveryResult,
    FundamentalFacts,
    Instrument,
    InstrumentDetail,
    Market,
    QuoteFact,
    RelativeVolumeFacts,
    TrendFacts,
)
from jusik.investor_store import InvestorStore
from jusik.market_history_approximate import FixtureApproximateMarketHistorySource
from jusik.market_history_sources import FixtureMarketHistorySource
from jusik.market_history_store import MarketHistoryStore
from jusik.market_research_api import router as market_research_router
from jusik.market_research_service import MarketResearchService
from jusik.models import (
    AccountResult,
    AggregateSummary,
    Alert,
    AssetSummary,
    AssetSummaryResult,
    ExchangeRate,
    Fundamentals,
    Holding,
    InvestmentAdvice,
    MarketIntelligence,
    MarketResult,
    MonitorStatus,
    NewsItem,
    Portfolio,
    SourceStatus,
    Total,
)

NOW = datetime(2026, 9, 7, 10, 0, tzinfo=UTC)
INVESTOR_NOW = datetime(2026, 9, 7, 10, 0, tzinfo=UTC)


def _holding(
    market: str,
    symbol: str,
    name: str,
    currency: str,
    quantity: str,
    cost: str,
    value: str,
    profit: str,
    per: str | None,
    signal: str,
) -> Holding:
    rate = Decimal("1") if currency == "KRW" else Decimal("1351.44")
    q = Decimal(quantity)
    cost_value = Decimal(cost)
    current_value = Decimal(value)
    profit_value = Decimal(profit)
    return Holding(
        market=market,
        symbol=symbol,
        name=name,
        currency=currency,
        quantity=q,
        average_price=cost_value / q,
        current_price=current_value / q,
        cost=cost_value,
        value=current_value,
        profit=profit_value,
        return_pct=profit_value / cost_value * 100,
        fx_rate=rate,
        fx_source=("원화 기준" if currency == "KRW" else "Frankfurter 일별 기준환율"),
        fx_as_of=date(2026, 9, 7),
        average_price_krw=(cost_value / q * rate).quantize(Decimal("1")),
        current_price_krw=(current_value / q * rate).quantize(Decimal("1")),
        cost_krw=(cost_value * rate).quantize(Decimal("1")),
        value_krw=(current_value * rate).quantize(Decimal("1")),
        profit_krw=(profit_value * rate).quantize(Decimal("1")),
        fundamentals=Fundamentals(
            status="ok" if per else "unavailable",
            per=Decimal(per) if per else None,
            pbr=Decimal("1.1") if per else None,
            eps=Decimal("7.5") if per else None,
            bps=Decimal("100") if per else None,
            source="fixture",
            source_url="https://apiportal.koreainvestment.com/apiservice",
            fetched_at=NOW if per else None,
        ),
        advice=InvestmentAdvice(
            signal=signal,
            label={
                "buy_review": "매수 검토",
                "hold": "보유 검토",
                "sell_review": "매도 검토",
                "insufficient": "판단 보류",
            }[signal],
            reasons=["브라우저 검증용 규칙 평가입니다."],
        ),
        price_fetched_at=NOW,
    )


HOLDINGS = [
    _holding(
        "KRX",
        "005930",
        "삼성전자",
        "KRW",
        "12",
        "900000",
        "960000",
        "60000",
        "12.4",
        "buy_review",
    ),
    _holding(
        "US", "AAPL", "Apple", "USD", "2.5", "450.25", "520.75", "70.50", "28.8", "hold"
    ),
    _holding(
        "US",
        "BIG",
        "큰 정밀도 테스트",
        "USD",
        "9007199254740993.125",
        "18014398509481986.25",
        "16212958658533787.625",
        "-1801439850948198.625",
        None,
        "sell_review",
    ),
]


def fixture_portfolio() -> Portfolio:
    markets = [
        MarketResult(market="KRX", status="ok", holdings=[HOLDINGS[0]], fetched_at=NOW),
        MarketResult(market="US", status="ok", holdings=HOLDINGS[1:], fetched_at=NOW),
    ]
    total_cost = sum(
        (holding.cost_krw or Decimal(0) for holding in HOLDINGS), Decimal(0)
    )
    total_value = sum(
        (holding.value_krw or Decimal(0) for holding in HOLDINGS), Decimal(0)
    )
    total_profit = sum(
        (holding.profit_krw or Decimal(0) for holding in HOLDINGS), Decimal(0)
    )
    total = Total(
        currency="KRW",
        cost=total_cost,
        value=total_value,
        profit=total_profit,
        return_pct=total_profit / total_cost * 100,
        cost_krw=total_cost,
        value_krw=total_value,
        profit_krw=total_profit,
    )
    account = AccountResult(
        id="fixture",
        label="검증 계좌",
        status="ok",
        asset_summary=AssetSummaryResult(
            status="ok",
            summary=AssetSummary(
                net_asset=total_value + Decimal("1000000000"),
                total_evaluation=total_value,
                cash="1000000000",
                profit_loss=total_profit,
                overseas_evaluation=sum(
                    (holding.value_krw or Decimal(0) for holding in HOLDINGS[1:]),
                    Decimal(0),
                ),
            ),
            fetched_at=NOW,
        ),
        markets=markets,
        totals=[total],
        fetched_at=NOW,
    )
    return Portfolio(
        fetched_at=NOW,
        accounts=[account],
        aggregate=AggregateSummary(
            net_asset=total_value + Decimal("1000000000"),
            completeness="complete",
            included_accounts=1,
            registered_accounts=1,
        ),
        totals=[total],
        exchange_rates=[
            ExchangeRate(
                currency="KRW",
                status="ok",
                krw_per_unit="1",
                as_of=date(2026, 9, 7),
                fetched_at=NOW,
            ),
            ExchangeRate(
                currency="USD",
                status="ok",
                krw_per_unit="1351.44",
                as_of=date(2026, 9, 7),
                fetched_at=NOW,
            ),
        ],
        alerts=[
            Alert(
                id=1,
                account_id="fixture",
                market="US",
                symbol="BIG",
                name="큰 정밀도 테스트",
                signal="sell_review",
                title="큰 정밀도 테스트 매도 검토 신호",
                message="손실률이 위험 기준 이하입니다.",
                created_at=NOW,
                delivery="in_app",
            )
        ],
        intelligence=MarketIntelligence(
            korea_base_rate="3.00",
            korea_rate_as_of=date(2026, 8, 27),
            us_target_rate="3.50%–3.75%",
            us_rate_as_of=date(2026, 9, 6),
            news=[
                NewsItem(
                    id="fixture-news",
                    category="geopolitics",
                    title="검증용 국제 정세 소식",
                    url="https://www.bbc.com/news",
                    source="BBC News",
                    published_at=NOW,
                    assessment="보유 종목의 환율과 업종 노출을 확인하세요.",
                ),
                NewsItem(
                    id="fixture-truth-post",
                    category="truth_social_post",
                    title="트럼프 계정 게시물 (검증용)",
                    url="https://www.trumpstruth.org/statuses/123456789",
                    original_url="https://truthsocial.com/@example/123456789",
                    excerpt=(
                        "브라우저 표시와 안전한 링크 검증을 위한 합성 게시물입니다. "
                        "https://example.invalid/"
                        "continuous-unbroken-mobile-overflow-regression-"
                        "abcdefghijklmnopqrstuvwxyz0123456789abcdefghijklmnopqrstuvwxyz"
                    ),
                    source="Trump's Truth 제3자 보관본",
                    published_at=NOW,
                    assessment=(
                        "제3자 보관본에는 재게시물이 포함될 수 있습니다. "
                        "게시물의 주장을 "
                        "실제 정책으로 간주하지 말고 공식 발표를 교차 확인하세요."
                    ),
                ),
            ],
            sources=[
                SourceStatus(
                    id="world",
                    label="BBC 국제 소식",
                    status="ok",
                    source_url="https://feeds.bbci.co.uk/news/world/rss.xml",
                    fetched_at=NOW,
                ),
                SourceStatus(
                    id="truth_archive",
                    label="트럼프 계정 게시물 · 제3자 보관본",
                    status="ok",
                    source_url="https://www.trumpstruth.org/feed",
                    fetched_at=NOW,
                ),
            ],
            fetched_at=NOW,
        ),
        monitor=MonitorStatus(
            interval_seconds=300,
            telegram_configured=False,
            last_checked_at=NOW,
            last_success_at=NOW,
            next_check_at=datetime(2026, 9, 7, 10, 5, tzinfo=UTC),
        ),
    )


app = FastAPI(title="Jusik deterministic browser fixture")


def _investor_detail(
    instrument: Instrument, *, missing: bool = False
) -> InstrumentDetail:
    quote = QuoteFact(
        price=None
        if missing
        else Decimal("72000" if instrument.market == "KR" else "180.25"),
        currency=instrument.currency,
        as_of=INVESTOR_NOW,
        fetched_at=INVESTOR_NOW,
        source="합성 fixture · 실제 시세 아님",
        unavailable_reason="합성 fixture에서 의도적으로 누락" if missing else None,
    )
    facts = FundamentalFacts(
        eps=None
        if missing or instrument.instrument_type != "stock"
        else Decimal("6000"),
        eps_period=None if missing else "2025-FY",
        per=None if missing or instrument.instrument_type != "stock" else Decimal("12"),
        pbr=None
        if missing or instrument.instrument_type != "stock"
        else Decimal("1.2"),
        source="합성 fixture · 실제 재무자료 아님",
        fetched_at=NOW,
        unavailable_reasons=["합성 fixture에서 의도적으로 누락"] if missing else [],
    )
    sessions: list[date] = []
    cursor = date(2026, 9, 4)
    while len(sessions) < 22:
        if cursor.weekday() < 5:
            sessions.append(cursor)
        cursor -= timedelta(days=1)
    bars = [
        DailyBar(
            session=session,
            close=Decimal("100"),
            volume=Decimal("10"),
            adjusted=True,
        )
        for session in reversed(sessions)
    ]
    if instrument.instrument_type == "stock" and not missing:
        bars[-1] = bars[-1].model_copy(
            update={"close": Decimal("120"), "volume": Decimal("20")}
        )
    trend = evaluate_trend(
        bars,
        today=INVESTOR_NOW.date(),
        expected_latest_session=sessions[0],
        source="합성 fixture · 실제 일봉 아님",
    )
    if missing:
        trend = TrendFacts(
            source="합성 fixture",
            unavailable_reasons=["합성 fixture에서 일봉을 의도적으로 누락"],
        )
    analysis = analyze(instrument, quote, facts, trend, now=NOW)
    return InstrumentDetail(
        instrument=instrument,
        analysis=analysis,
        limitations=[
            "합성 fixture · 실제 계좌·시세·성과가 아닙니다.",
            "후보 순위는 저평가나 품질의 증명이 아닙니다.",
        ],
    )


def fixture_investor_provider() -> InMemoryInvestorProvider:
    kr_stock = Instrument(
        market="KR",
        exchange="KRX",
        symbol="005930",
        currency="KRW",
        name="삼성전자",
        instrument_type="stock",
    )
    kr_etf = Instrument(
        market="KR",
        exchange="KRX",
        symbol="069500",
        currency="KRW",
        name="KODEX 200",
        instrument_type="etf",
    )
    kr_unknown = Instrument(
        market="KR",
        exchange="KRX",
        symbol="999999",
        currency="KRW",
        name="타입 미확인 종목",
        instrument_type="unknown",
    )
    us_stock = Instrument(
        market="US",
        exchange="NAS",
        symbol="AAPL",
        currency="USD",
        name="Apple",
        instrument_type="stock",
    )
    us_etf = Instrument(
        market="US",
        exchange="NAS",
        symbol="TQQQ",
        currency="USD",
        name="ProShares UltraPro QQQ",
        instrument_type="etf",
    )
    details = [
        _investor_detail(kr_stock),
        _investor_detail(kr_etf),
        _investor_detail(kr_unknown, missing=True),
        _investor_detail(us_stock),
        _investor_detail(us_etf),
    ]

    def candidate(
        instrument: Instrument, rank: int, volume: str, ratio: str
    ) -> Candidate:
        return Candidate(
            instrument=instrument,
            rank=rank,
            reason="합성 거래량 순위와 직전 20거래일 상대거래량 · 투자 판단 아님",
            source="fixture",
            observed_at=INVESTOR_NOW,
            ranking_volume=Decimal(volume),
            classification_source="합성 Yahoo 종목 유형",
            classification_observed_at=INVESTOR_NOW,
            relative_volume=RelativeVolumeFacts(
                numerator=Decimal(volume),
                average20=Decimal("100000"),
                ratio=Decimal(volume) / Decimal("100000"),
                sample_count=20,
                sample_start=date(2026, 8, 7),
                sample_end=date(2026, 9, 4),
                source="합성 Yahoo 상대거래량",
                as_of=INVESTOR_NOW,
                fetched_at=INVESTOR_NOW,
            ),
        )

    candidates: dict[Market, DiscoveryResult] = {
        "KR": DiscoveryResult(
            market="KR",
            candidates=[candidate(kr_stock, 1, "1200000", "12")],
            etf_candidates=[candidate(kr_etf, 1, "800000", "8")],
            coverage="합성 첫 페이지에서 주식·ETF를 분리한 3건",
            truncated=False,
            fetched_at=NOW,
            counts=DiscoveryCounts(
                source_rows=3,
                valid_rows=3,
                inspected=3,
                stocks=1,
                etfs=1,
                unknown=1,
            ),
        ),
        "US": DiscoveryResult(
            market="US",
            candidates=[candidate(us_stock, 1, "900000", "9")],
            etf_candidates=[candidate(us_etf, 1, "700000", "7")],
            coverage="합성 첫 페이지에서 주식·ETF를 분리한 2건",
            truncated=False,
            fetched_at=NOW,
            counts=DiscoveryCounts(
                source_rows=2,
                valid_rows=2,
                inspected=2,
                stocks=1,
                etfs=1,
            ),
        ),
    }
    return InMemoryInvestorProvider(details, candidates)


app.state.investor_provider = fixture_investor_provider()
app.state.market_research_service = MarketResearchService(
    FixtureMarketHistorySource(),
    MarketHistoryStore(
        Path(
            os.environ.get(
                "JUSIK_MARKET_RESEARCH_DB_PATH", "/tmp/jusik-market-research-fixture.db"
            )
        )
    ),
    approximate_source=FixtureApproximateMarketHistorySource(),
)
fixture_db = Path(
    os.environ.get("JUSIK_INVESTOR_DB_PATH", "/tmp/jusik-investor-fixture.db")
)
app.state.investor_store = InvestorStore(fixture_db)
app.include_router(investor_router)
app.include_router(market_research_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/portfolio", response_model=Portfolio)
async def portfolio(response: Response) -> Portfolio:
    response.headers["Cache-Control"] = "no-store"
    return fixture_portfolio()
