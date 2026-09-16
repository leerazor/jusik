from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

import httpx
import pytest

from jusik.market_data_collector import (
    AtomicResponseCache,
    CollectorAuthenticationError,
    CollectorError,
    CollectorSettings,
    FreeMarketDataCollector,
    HttpFetcher,
    NetworkCollectorTransport,
    RequestBudgetExceeded,
    _AlphaProductType,
    _classify_alpha_product,
    _normalize_alpha_exchange,
    collect_market_data,
    completed_collection_is_valid,
    estimate_network_requests,
    load_collector_settings,
    parse_alpha_vantage_listing_status,
    parse_alpha_vantage_listing_status_detailed,
    parse_fred_observations,
    parse_krx_daily_response,
    parse_krx_daily_trade_response,
    parse_yahoo_chart,
)
from jusik.market_history_approximate import (
    US_MEMBERSHIP_NORMALIZATION_VERSION,
    ApproximateMarketHistorySource,
    JsonApproximateProvider,
    run_approximate_market_research,
)
from jusik.market_history_models import MarketResearchRequest
from jusik.market_research_cli import main as market_research_cli
from jusik.research_market_calendar import default_market_calendar


def test_krx_parser_normalizes_all_daily_rows_and_market_board() -> None:
    body = json.dumps(
        {
            "OutBlock_1": [
                {
                    "BAS_DD": "20260914",
                    "ISU_SRT_CD": "005930",
                    "ISU_ABBRV": "삼성전자",
                    "MKT_NM": "KOSPI",
                },
            ]
        }
    ).encode()
    rows = parse_krx_daily_response(body, checkpoint=date(2026, 9, 14))
    assert [(row.session, row.symbol, row.exchange) for row in rows] == [
        (date(2026, 9, 14), "005930", "KOSPI")
    ]
    kosdaq = parse_krx_daily_response(
        json.dumps(
            {
                "OutBlock_1": [
                    {
                        "basDd": "2026-09-14",
                        "symbol": "123456",
                        "name": "Sample",
                        "market": "KOSDAQ",
                    }
                ]
            }
        ).encode(),
        checkpoint=date(2026, 9, 14),
        market_board="KSQ",
    )
    assert kosdaq[0].exchange == "KOSDAQ"
    malformed_rows = {
        "OutBlock_1": [
            {
                "BAS_DD": "20260914",
                "ISU_SRT_CD": "005930",
                "ISU_ABBRV": "삼성전자",
                "MKT_NM": "KOSPI",
            },
            "malformed row",
        ]
    }
    with pytest.raises(CollectorError, match="rows are malformed"):
        parse_krx_daily_response(
            json.dumps(malformed_rows).encode(), checkpoint=date(2026, 9, 14)
        )
    duplicate = {
        "OutBlock_1": [
            {
                "BAS_DD": "20260914",
                "ISU_SRT_CD": "005930",
                "ISU_ABBRV": "삼성전자",
                "MKT_NM": "KOSPI",
                "TDD_OPNPRC": "100",
                "TDD_HGPRC": "110",
                "TDD_LWPRC": "90",
                "TDD_CLSPRC": "105",
                "ACC_TRDVOL": "1000",
            }
        ]
        * 2
    }
    with pytest.raises(CollectorError, match="duplicate"):
        parse_krx_daily_response(
            json.dumps(duplicate).encode(), checkpoint=date(2026, 9, 14)
        )

    parsed = parse_krx_daily_trade_response(
        json.dumps(
            {
                "OutBlock_1": [
                    {
                        "BAS_DD": "20260914",
                        "ISU_CD": "005930",
                        "ISU_NM": "삼성전자",
                        "MKT_NM": "KOSPI",
                        "TDD_OPNPRC": "70,000",
                        "TDD_HGPRC": "71,000",
                        "TDD_LWPRC": "69,000",
                        "TDD_CLSPRC": "70,500",
                        "ACC_TRDVOL": "1,234",
                    }
                ]
            }
        ).encode(),
        checkpoint=date(2026, 9, 14),
    )
    assert parsed.bars[0].close == 70500
    assert parsed.bars[0].volume == 1234


def test_alpha_listing_status_filters_etf_and_future_or_delisted_rows() -> None:
    body = (
        b"symbol,name,exchange,assetType,ipoDate,delistingDate,status\n"
        b"AAA,Active,NASDAQ,Stock,2020-01-01,null,Active\n"
        b"ETF1,Fund,NYSE,ETF,2020-01-01,null,Active\n"
        b"FUT,Future,NASDAQ,Stock,2027-01-01,null,Active\n"
        b"OLD,Old,NASDAQ,Stock,2020-01-01,2026-01-01,Delisted\n"
    )
    rows = parse_alpha_vantage_listing_status(body, as_of=date(2026, 9, 14))
    assert [row.symbol for row in rows] == ["AAA"]
    assert rows[0].exchange == "NAS"


def test_alpha_listing_status_reports_row_exclusions_and_rejects_bad_header() -> None:
    body = (
        b"symbol,name,exchange,assetType,ipoDate,delistingDate,status\n"
        b"AAA,Active,NASDAQ,Stock,2020-01-01,null,Active\n"
        b"W,Company warrant,NASDAQ,Stock,2020-01-01,null,Active\n"
        b"ETF,Fund,NYSE,ETF,2020-01-01,null,Active\n"
        b"BAD,Too late,NASDAQ,Stock,not-a-date,null,Active\n"
        b"AAA,Duplicate,NASDAQ,Stock,2020-01-01,null,Active\n"
    )
    parsed = parse_alpha_vantage_listing_status_detailed(body, as_of=date(2026, 9, 14))
    assert parsed.input_rows == 5
    assert parsed.accepted == 1
    assert dict(parsed.excluded) == {
        "date": 1,
        "duplicate": 1,
        "security_type": 2,
    }
    with pytest.raises(CollectorError, match="header"):
        parse_alpha_vantage_listing_status(
            b"symbol,name\nAAA,Active\n", as_of=date(2026, 9, 14)
        )


@pytest.mark.parametrize(
    ("asset_type", "symbol", "name", "expected"),
    [
        (" Stock ", "AAA", "Acme", _AlphaProductType.ORDINARY),
        ("common stock", "AAA", "Acme", _AlphaProductType.ORDINARY),
        ("COMMON_STOCK", "AAA", "Acme", _AlphaProductType.ORDINARY),
        ("ETF", "AAA", "Acme", _AlphaProductType.ETF),
        ("warrants", "AAA", "Acme", _AlphaProductType.WARRANT),
        ("rights", "AAA", "Acme", _AlphaProductType.OTHER),
        ("units", "AAA", "Acme", _AlphaProductType.OTHER),
        ("preferred stock", "AAA", "Acme", _AlphaProductType.OTHER),
        ("ETN", "AAA", "Acme", _AlphaProductType.OTHER),
        ("", "AAA", "Acme", _AlphaProductType.UNKNOWN),
        ("NCM", "AAA", "Acme", _AlphaProductType.UNKNOWN),
        ("", "AAA", "Acme ETF", _AlphaProductType.ETF),
        ("", "AAA", "Acme Warrant", _AlphaProductType.WARRANT),
        ("", "AAA-ws", "Acme", _AlphaProductType.WARRANT),
        ("", "AAA.wt", "Acme", _AlphaProductType.WARRANT),
        ("stock", "AAA", "Acme ETF", _AlphaProductType.ETF),
        ("stock", "AAA", "Acme ETF Warrant", _AlphaProductType.UNKNOWN),
        ("stock", "AAA", "United Therapeutics", _AlphaProductType.ORDINARY),
        ("stock", "AAA", "Community Health", _AlphaProductType.ORDINARY),
        ("stock", "AAA", "Bright Horizons", _AlphaProductType.ORDINARY),
        ("stock", "AAA", "Wright Holdings", _AlphaProductType.ORDINARY),
        ("stock", "AAA", "Preferred Bank", _AlphaProductType.ORDINARY),
        ("stock", "AAA", "Unit Finance Corp", _AlphaProductType.ORDINARY),
        ("stock", "AAA", "Right On Brands", _AlphaProductType.ORDINARY),
        (
            "stock",
            "AAA",
            "Acme Units, each consisting of one share",
            _AlphaProductType.OTHER,
        ),
        ("stock", "AAA", "Acme preferred shares", _AlphaProductType.OTHER),
        (
            "stock",
            "AAA",
            "Acme Rights, each consisting of one right",
            _AlphaProductType.OTHER,
        ),
    ],
)
def test_alpha_listing_product_classification_is_conservative(
    asset_type: str, symbol: str, name: str, expected: _AlphaProductType
) -> None:
    assert _classify_alpha_product(asset_type, symbol=symbol, name=name) is expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("NYSE", "NYS"),
        ("NASDAQ", "NAS"),
        ("NASDAQ CAPITAL MARKET", "NAS"),
        ("NASDAQ GLOBAL SELECT MARKET", "NAS"),
        ("NCM", "NAS"),
        ("NMS", "NAS"),
        ("NGM", "NAS"),
        ("NYSE ARCA", "AMS"),
        (" NYSEARCA ", "AMS"),
    ],
)
def test_alpha_listing_exchange_aliases_are_product_independent(
    raw: str, expected: str
) -> None:
    assert _normalize_alpha_exchange(raw) == expected


def test_alpha_listing_exchange_aliases_do_not_classify_products() -> None:
    body = (
        b"symbol,name,exchange,assetType,ipoDate,delistingDate,status\n"
        b"NCM1,Ordinary NCM,NCM,Stock,2020-01-01,null,Active\n"
        b"NMS1,Ordinary NMS,NMS,Common Stock,2020-01-01,null,Active\n"
        b"NGM1,Unknown NGM,NGM,Unknown,2020-01-01,null,Active\n"
        b"ETF1,ETF NCM,NCM,ETF,2020-01-01,null,Active\n"
    )
    parsed = parse_alpha_vantage_listing_status_detailed(body, as_of=date(2026, 9, 14))
    assert [(row.symbol, row.exchange) for row in parsed.rows] == [
        ("NCM1", "NAS"),
        ("NMS1", "NAS"),
    ]
    assert dict(parsed.excluded) == {"security_type": 2}


def test_yahoo_parser_validates_identity_arrays_and_action_events() -> None:
    timestamps = [
        int(datetime(2026, 9, 11, 20, tzinfo=UTC).timestamp()),
        int(datetime(2026, 9, 14, 20, tzinfo=UTC).timestamp()),
    ]
    body = json.dumps(
        {
            "chart": {
                "result": [
                    {
                        "meta": {
                            "symbol": "AAA",
                            "currency": "USD",
                            "instrumentType": "EQUITY",
                            "exchangeName": "NMS",
                            "exchangeTimezoneName": "America/New_York",
                        },
                        "timestamp": timestamps,
                        "indicators": {
                            "quote": [
                                {
                                    "open": [10, 11],
                                    "high": [12, 13],
                                    "low": [9, 10],
                                    "close": [11, 12],
                                    "volume": [100, 200],
                                }
                            ]
                        },
                        "events": {"splits": {"1": {"numerator": 2}}},
                    }
                ]
            }
        }
    ).encode()
    parsed = parse_yahoo_chart(
        body,
        symbol="AAA",
        exchange="NAS",
        currency="USD",
        start=date(2026, 9, 11),
        end=date(2026, 9, 14),
    )
    assert [item.session for item in parsed.bars] == [
        date(2026, 9, 11),
        date(2026, 9, 14),
    ]
    assert parsed.events == ("splits",)
    for requested_exchange in ("NAS", "NMS"):
        for venue in ("NMS", "NGM", "NCM"):
            candidate = json.loads(body)
            candidate["chart"]["result"][0]["meta"]["exchangeName"] = venue
            result = parse_yahoo_chart(
                json.dumps(candidate).encode(),
                symbol="AAA",
                exchange=requested_exchange,
                currency="USD",
                start=date(2026, 9, 11),
                end=date(2026, 9, 14),
            )
            assert result.bars
        for venue in ("NYQ", "PCX"):
            candidate = json.loads(body)
            candidate["chart"]["result"][0]["meta"]["exchangeName"] = venue
            with pytest.raises(CollectorError, match="identity"):
                parse_yahoo_chart(
                    json.dumps(candidate).encode(),
                    symbol="AAA",
                    exchange=requested_exchange,
                    currency="USD",
                    start=date(2026, 9, 11),
                    end=date(2026, 9, 14),
                )
    broken = json.loads(body)
    broken["chart"]["result"][0]["indicators"]["quote"][0]["volume"] = [100]
    with pytest.raises(CollectorError, match="arrays"):
        parse_yahoo_chart(
            json.dumps(broken).encode(),
            symbol="AAA",
            exchange="NAS",
            currency="USD",
            start=date(2026, 9, 11),
            end=date(2026, 9, 14),
        )
    broken["chart"]["result"][0]["indicators"]["adjclose"] = [{"adjclose": [11]}]
    with pytest.raises(CollectorError, match="arrays"):
        parse_yahoo_chart(
            json.dumps(broken).encode(),
            symbol="AAA",
            exchange="NAS",
            currency="USD",
            start=date(2026, 9, 11),
            end=date(2026, 9, 14),
        )


def test_fred_parser_rejects_empty_range_and_preserves_decimal_values() -> None:
    body = json.dumps(
        {
            "observations": [
                {"date": "2026-09-11", "value": "1380.125"},
                {"date": "2026-09-14", "value": "."},
            ]
        }
    ).encode()
    rows = parse_fred_observations(body, start=date(2026, 9, 1), end=date(2026, 9, 14))
    assert rows[0].krw_per_usd == 1380.125
    with pytest.raises(CollectorError, match="no requested"):
        parse_fred_observations(body, start=date(2026, 9, 14), end=date(2026, 9, 14))


def test_atomic_cache_verifies_raw_hash_and_does_not_expose_request_secret(
    tmp_path: Path,
) -> None:
    cache = AtomicResponseCache(tmp_path)
    entry = cache.put(
        source="krx",
        endpoint="https://data.krx.co.kr/api",
        request_key='{"source":"krx","apikey":"secret"}',
        body=b"response",
        status_code=200,
        captured_at=datetime(2026, 9, 14, tzinfo=UTC),
        checkpoint="krx:2026-09-14",
    )
    assert entry.content_sha256
    assert cache.get('{"source":"krx","apikey":"secret"}')[1] == b"response"
    raw_manifest = (tmp_path / "manifest.json").read_text(encoding="utf-8")
    assert "secret" not in raw_manifest
    (tmp_path / "raw" / f"{entry.key}.bin").write_bytes(b"tampered")
    with pytest.raises(CollectorError, match="hash mismatch"):
        cache.get('{"source":"krx","apikey":"secret"}')


class _FixtureTransport:
    def __init__(self) -> None:
        self.calendar = default_market_calendar()

    async def krx(self, market_board: str, start: date, end: date) -> bytes:
        symbol = "KOSPI1" if market_board == "STK" else "KOSDAQ1"
        return json.dumps(
            {
                "OutBlock_1": [
                    {
                        "BAS_DD": start.strftime("%Y%m%d"),
                        "ISU_SRT_CD": symbol,
                        "ISU_ABBRV": symbol,
                        "MKT_NM": "KOSPI" if market_board == "STK" else "KOSDAQ",
                        "TDD_OPNPRC": "100",
                        "TDD_HGPRC": "110",
                        "TDD_LWPRC": "90",
                        "TDD_CLSPRC": "105",
                        "ACC_TRDVOL": "1000",
                        "LIST_SHRS": "1000000",
                    }
                ]
            }
        ).encode()

    async def alpha_listing(self, as_of: date) -> bytes:
        return b""

    async def yahoo(self, symbol: str, start: date, end: date) -> bytes:
        sessions = [
            day
            for offset in range((end - start).days + 1)
            if (day := start + timedelta(days=offset))
            and self.calendar.lookup("KSC", day).session is not None
        ]
        timestamps = [
            int(datetime.combine(day, time(6), UTC).timestamp()) for day in sessions
        ]
        values = [str(100 + index) for index in range(len(sessions))]
        return json.dumps(
            {
                "chart": {
                    "result": [
                        {
                            "meta": {
                                "symbol": symbol,
                                "currency": "KRW",
                                "instrumentType": "EQUITY",
                                "exchangeName": "KOE",
                                "exchangeTimezoneName": "Asia/Seoul",
                            },
                            "timestamp": timestamps,
                            "indicators": {
                                "quote": [
                                    {
                                        "open": values,
                                        "high": [
                                            str(101 + i) for i in range(len(sessions))
                                        ],
                                        "low": [
                                            str(99 + i) for i in range(len(sessions))
                                        ],
                                        "close": values,
                                        "volume": [
                                            str(1000 + i) for i in range(len(sessions))
                                        ],
                                    }
                                ]
                            },
                        }
                    ]
                }
            }
        ).encode()

    async def fred(self, start: date, end: date) -> bytes:
        return b""


class _CorporateActionTransport(_FixtureTransport):
    def __init__(self, mode: str) -> None:
        super().__init__()
        self.mode = mode
        self.action_session = date(2026, 1, 5)

    async def krx(self, market_board: str, start: date, end: date) -> bytes:
        if (self.mode == "delisting" and start >= self.action_session) or (
            self.mode == "halt" and start == self.action_session
        ):
            return b'{"OutBlock_1": []}'
        body = await super().krx(market_board, start, end)
        if self.mode == "split" and start >= self.action_session:
            payload = json.loads(body)
            payload["OutBlock_1"][0]["LIST_SHRS"] = "2000000"
            return json.dumps(payload).encode()
        return body


class _USCheckpointTransport:
    def __init__(self, *, fail_later: bool) -> None:
        self.calendar = default_market_calendar()
        self.fail_later = fail_later
        self.alpha_calls = 0

    async def krx(self, market_board: str, start: date, end: date) -> bytes:
        raise AssertionError("KRX must not be used for US collection")

    async def alpha_listing(self, as_of: date) -> bytes:
        self.alpha_calls += 1
        if self.fail_later and self.alpha_calls > 1:
            raise CollectorError("checkpoint unavailable")
        return (
            b"symbol,name,exchange,assetType,ipoDate,delistingDate,status\n"
            b"AAA,Sample,NASDAQ,Stock,2020-01-01,null,Active\n"
        )

    async def yahoo(self, symbol: str, start: date, end: date) -> bytes:
        sessions = [
            day
            for offset in range((end - start).days + 1)
            if (day := start + timedelta(days=offset))
            and self.calendar.lookup("NMS", day).session is not None
        ]
        values = [str(100 + index) for index in range(len(sessions))]
        return json.dumps(
            {
                "chart": {
                    "result": [
                        {
                            "meta": {
                                "symbol": symbol,
                                "currency": "USD",
                                "instrumentType": "EQUITY",
                                "exchangeName": "NMS",
                                "exchangeTimezoneName": "America/New_York",
                            },
                            "timestamp": [
                                int(datetime.combine(day, time(20), UTC).timestamp())
                                for day in sessions
                            ],
                            "indicators": {
                                "quote": [
                                    {
                                        "open": values,
                                        "high": [
                                            str(101 + index)
                                            for index in range(len(sessions))
                                        ],
                                        "low": [
                                            str(99 + index)
                                            for index in range(len(sessions))
                                        ],
                                        "close": values,
                                        "volume": [
                                            str(1000 + index)
                                            for index in range(len(sessions))
                                        ],
                                    }
                                ]
                            },
                        }
                    ]
                }
            }
        ).encode()

    async def fred(self, start: date, end: date) -> bytes:
        return json.dumps(
            {"observations": [{"date": start.isoformat(), "value": "1400"}]}
        ).encode()


class _CausalUSCheckpointTransport(_USCheckpointTransport):
    def __init__(
        self,
        later_symbols: tuple[str, ...],
        initial_symbols: tuple[str, ...] = ("AAA", "BBB"),
    ) -> None:
        super().__init__(fail_later=False)
        self.later_symbols = later_symbols
        self.initial_symbols = initial_symbols

    async def alpha_listing(self, as_of: date) -> bytes:
        self.alpha_calls += 1
        symbols = self.initial_symbols if as_of.year == 2025 else self.later_symbols
        rows = [
            f"{symbol},Sample {symbol},NASDAQ,Stock,2020-01-01,null,Active"
            for symbol in symbols
        ]
        return (
            "symbol,name,exchange,assetType,ipoDate,delistingDate,status\n"
            + "\n".join(rows)
            + "\n"
        ).encode()


class _ThreeCheckpointUSCheckpointTransport(_USCheckpointTransport):
    def __init__(self) -> None:
        super().__init__(fail_later=False)

    async def alpha_listing(self, as_of: date) -> bytes:
        self.alpha_calls += 1
        if as_of.year == 2025:
            raise CollectorError("checkpoint unavailable")
        symbols = ("AAA", "BBB") if as_of.year == 2024 else ("AAA", "NEW")
        rows = [
            f"{symbol},Sample {symbol},NASDAQ,Stock,2020-01-01,null,Active"
            for symbol in symbols
        ]
        return (
            "symbol,name,exchange,assetType,ipoDate,delistingDate,status\n"
            + "\n".join(rows)
            + "\n"
        ).encode()


class _CappedUSCheckpointTransport(_USCheckpointTransport):
    async def alpha_listing(self, as_of: date) -> bytes:
        self.alpha_calls += 1
        symbols = tuple(
            f"Y{self.alpha_calls}{index:03d}" for index in range(100)
        )
        rows = [
            f"{symbol},Sample {symbol},NASDAQ,Stock,2020-01-01,null,Active"
            for symbol in symbols
        ]
        return (
            "symbol,name,exchange,assetType,ipoDate,delistingDate,status\n"
            + "\n".join(rows)
            + "\n"
        ).encode()

    async def yahoo(self, symbol: str, start: date, end: date) -> bytes:
        return json.dumps(
            {
                "chart": {
                    "result": [
                        {
                            "meta": {
                                "symbol": symbol,
                                "currency": "USD",
                                "instrumentType": "EQUITY",
                                "exchangeName": "NMS",
                                "exchangeTimezoneName": "America/New_York",
                            },
                            "timestamp": [
                                int(datetime.combine(start, time(20), UTC).timestamp())
                            ],
                            "indicators": {
                                "quote": [
                                    {
                                        "open": [100],
                                        "high": [101],
                                        "low": [99],
                                        "close": [100],
                                        "volume": [1000],
                                    }
                                ]
                            },
                        }
                    ]
                }
            }
        ).encode()


def test_collector_builds_validated_kr_dataset_without_current_universe_fallback() -> (
    None
):
    request_start = date(2025, 9, 14)
    result = asyncio.run(
        FreeMarketDataCollector(_FixtureTransport()).collect(
            market="KR",
            start=request_start,
            end=date(2026, 9, 14),
            sample_size=1,
        )
    )
    assert result.dataset.source == "krx"
    assert len({row.symbol for row in result.dataset.universe}) == 1
    assert result.dataset.bars
    assert result.dataset.bar_source == "krx"
    assert result.dataset.simulated is False


def test_krx_collector_output_round_trips_through_approximate_strategy(
    tmp_path: Path,
) -> None:
    start = date(2025, 9, 14)
    end = date(2026, 9, 14)
    collected = asyncio.run(
        FreeMarketDataCollector(_FixtureTransport()).collect(
            market="KR", start=start, end=end, sample_size=1
        )
    )
    prepared = tmp_path / "prepared.json"
    prepared.write_bytes(collected.dataset.model_dump_json().encode())
    request = MarketResearchRequest(
        market="KR",
        start_date=start,
        end_date=end,
        research_grade="approximate",
    )
    provider = JsonApproximateProvider(prepared)
    source = ApproximateMarketHistorySource(provider)
    snapshot = asyncio.run(source.collect(request))
    readiness = source.readiness("KR", datetime(2026, 9, 14, tzinfo=UTC))
    result = run_approximate_market_research(
        snapshot, request, readiness, default_market_calendar()
    )
    assert snapshot.bars
    assert snapshot.bars[0].source == "krx"
    assert result.research_grade == "approximate"


def test_yahoo_collector_output_round_trips_through_approximate_strategy(
    tmp_path: Path,
) -> None:
    start = date(2025, 9, 14)
    end = date(2026, 9, 14)
    collected = asyncio.run(
        FreeMarketDataCollector(_USCheckpointTransport(fail_later=False)).collect(
            market="US", start=start, end=end, sample_size=1
        )
    )
    prepared = tmp_path / "prepared-us.json"
    prepared.write_bytes(collected.dataset.model_dump_json().encode())
    request = MarketResearchRequest(
        market="US",
        start_date=start,
        end_date=end,
        research_grade="approximate",
    )
    source = ApproximateMarketHistorySource(JsonApproximateProvider(prepared))
    snapshot = asyncio.run(source.collect(request))
    readiness = source.readiness("US", datetime(2026, 9, 14, tzinfo=UTC))
    result = run_approximate_market_research(
        snapshot, request, readiness, default_market_calendar()
    )
    assert snapshot.bars
    assert snapshot.bars[0].source == "yahoo"
    assert snapshot.bars[0].available_at.time() == time(20)
    assert collected.dataset.fx
    assert collected.dataset.fx[0].observation_date is not None
    assert collected.dataset.fx[0].observation_date < collected.dataset.fx[0].session
    assert result.status == "approximate"
    assert result.completeness == "approximate"
    assert result.research_grade == "approximate"
    assert result.trades
    assert result.metrics["coverage_sessions"] > 0


def test_us_collector_uses_causal_version_and_unknown_gap_after_failed_checkpoint() -> (
    None
):
    checkpoint = date(2026, 1, 2)
    result = asyncio.run(
        FreeMarketDataCollector(_USCheckpointTransport(fail_later=True)).collect(
            market="US",
            start=date(2025, 9, 14),
            end=date(2026, 9, 14),
            sample_size=1,
        )
    )
    assert result.dataset.normalization_version == US_MEMBERSHIP_NORMALIZATION_VERSION
    assert all(row.session < checkpoint for row in result.dataset.universe)
    assert any(
        "current_selected=0" in item and "cumulative_admitted=1" in item
        for item in result.limitations
    )


def test_us_collector_future_newcomer_cannot_change_prior_membership_prefix() -> None:
    kwargs = {
        "market": "US",
        "start": date(2025, 9, 14),
        "end": date(2026, 9, 14),
        "sample_size": 2,
    }
    baseline = asyncio.run(
        FreeMarketDataCollector(
            _CausalUSCheckpointTransport(("AAA", "BBB", "NEW"))
        ).collect(**kwargs)
    )
    permuted = asyncio.run(
        FreeMarketDataCollector(
            _CausalUSCheckpointTransport(("NEW", "BBB", "AAA"))
        ).collect(**kwargs)
    )
    checkpoint = date(2026, 1, 2)
    baseline_prefix = tuple(
        row for row in baseline.dataset.universe if row.session < checkpoint
    )
    permuted_prefix = tuple(
        row for row in permuted.dataset.universe if row.session < checkpoint
    )
    assert baseline_prefix == permuted_prefix
    assert "NEW" not in {row.symbol for row in baseline_prefix}
    assert "NEW" not in {row.symbol for row in permuted_prefix}


def test_us_collector_keeps_warmup_prices_but_admits_new_symbol_at_checkpoint(
    tmp_path: Path,
) -> None:
    result = asyncio.run(
        FreeMarketDataCollector(
            _CausalUSCheckpointTransport(
                ("AAA", "NEW"), initial_symbols=("AAA",)
            )
        ).collect(
            market="US",
            start=date(2025, 9, 14),
            end=date(2026, 9, 14),
            sample_size=2,
        )
    )
    membership_sessions = [
        row.session for row in result.dataset.universe if row.symbol == "NEW"
    ]
    price_sessions = [bar.session for bar in result.dataset.bars if bar.symbol == "NEW"]
    assert membership_sessions
    assert min(membership_sessions) >= date(2026, 1, 2)
    assert price_sessions
    assert min(price_sessions) < min(membership_sessions)
    prepared = tmp_path / "new-symbol.json"
    prepared.write_bytes(result.dataset.model_dump_json().encode())
    request = MarketResearchRequest(
        market="US",
        start_date=date(2025, 9, 14),
        end_date=date(2026, 9, 14),
        research_grade="approximate",
    )
    source = ApproximateMarketHistorySource(JsonApproximateProvider(prepared))
    snapshot = asyncio.run(
        source.collect(request, captured_at=datetime(2026, 9, 16, tzinfo=UTC))
    )
    strategy_result = run_approximate_market_research(
        snapshot,
        request,
        source.readiness("US", datetime(2026, 9, 16, tzinfo=UTC)),
        default_market_calendar(),
    )
    assert strategy_result.status == "approximate"
    assert strategy_result.trades
    assert all(
        trade.symbol != "NEW" or trade.fill_session >= min(membership_sessions)
        for trade in strategy_result.trades
    )


def test_us_collector_three_checkpoint_gap_and_delayed_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from jusik import market_data_collector as collector_module

    original_parser = collector_module.parse_alpha_vantage_listing_status_detailed

    def delayed_parser(
        body: bytes,
        *,
        as_of: date,
        available_at: datetime | None = None,
    ):
        parsed = original_parser(body, as_of=as_of, available_at=available_at)
        if as_of.year == 2026:
            delayed = tuple(
                row.model_copy(
                    update={"available_at": datetime(2026, 10, 1, tzinfo=UTC)}
                )
                for row in parsed.rows
            )
            return replace(parsed, rows=delayed)
        return parsed

    monkeypatch.setattr(
        collector_module,
        "parse_alpha_vantage_listing_status_detailed",
        delayed_parser,
    )
    result = asyncio.run(
        FreeMarketDataCollector(_ThreeCheckpointUSCheckpointTransport()).collect(
            market="US",
            start=date(2024, 9, 14),
            end=date(2026, 9, 14),
            sample_size=2,
        )
    )
    failed_checkpoint = date(2025, 1, 2)
    assert any("checkpoint unavailable" in item for item in result.limitations)
    assert all(row.session < failed_checkpoint for row in result.dataset.universe)
    assert "NEW" not in {row.symbol for row in result.dataset.universe}
    assert "BBB" in {row.symbol for row in result.dataset.universe}
    assert "NEW" in {bar.symbol for bar in result.dataset.bars}


def test_us_collector_recovery_after_gap_retains_incumbent_and_fills_vacancy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from jusik import market_data_collector as collector_module

    original_parser = collector_module.parse_alpha_vantage_listing_status_detailed

    def recovery_parser(
        body: bytes,
        *,
        as_of: date,
        available_at: datetime | None = None,
    ):
        parsed = original_parser(body, as_of=as_of, available_at=available_at)
        if as_of.year == 2026:
            recovered = tuple(
                row.model_copy(
                    update={"available_at": datetime(2026, 1, 7, tzinfo=UTC)}
                )
                for row in parsed.rows
            )
            return replace(parsed, rows=recovered)
        return parsed

    monkeypatch.setattr(
        collector_module,
        "parse_alpha_vantage_listing_status_detailed",
        recovery_parser,
    )
    result = asyncio.run(
        FreeMarketDataCollector(_ThreeCheckpointUSCheckpointTransport()).collect(
            market="US",
            start=date(2024, 9, 14),
            end=date(2026, 9, 14),
            sample_size=2,
        )
    )
    failed_checkpoint = date(2025, 1, 2)
    recovery_session = date(2026, 1, 7)
    recovery_rows = [
        row
        for row in result.dataset.universe
        if row.session >= recovery_session
    ]
    assert {row.symbol for row in recovery_rows} == {"AAA", "NEW"}
    assert all(
        row.session < failed_checkpoint
        or row.session >= recovery_session
        for row in result.dataset.universe
    )
    assert "BBB" not in {row.symbol for row in recovery_rows}


def test_us_collector_enforces_cumulative_four_hundred_admission_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from jusik import market_data_collector as collector_module

    checkpoints = (
        date(2023, 8, 15),
        date(2023, 9, 1),
        date(2024, 1, 3),
        date(2025, 1, 3),
        date(2026, 1, 2),
    )
    monkeypatch.setattr(
        collector_module, "_listing_checkpoints", lambda sessions: checkpoints
    )
    result = asyncio.run(
        FreeMarketDataCollector(_CappedUSCheckpointTransport(fail_later=False)).collect(
            market="US",
            start=date(2023, 9, 14),
            end=date(2026, 9, 14),
            sample_size=100,
        )
    )
    symbols_by_session: dict[date, set[str]] = {}
    for row in result.dataset.universe:
        symbols_by_session.setdefault(row.session, set()).add(row.symbol)
    assert max(map(len, symbols_by_session.values())) == 100
    assert len({row.symbol for row in result.dataset.universe}) == 400
    assert any("cumulative_admitted=400" in item for item in result.limitations)


def test_us_collector_source_strategy_prefix_is_invariant_to_future_listing(
    tmp_path: Path,
) -> None:
    async def run(later_symbols: tuple[str, ...], output: Path):
        collected = await FreeMarketDataCollector(
            _CausalUSCheckpointTransport(later_symbols)
        ).collect(
            market="US",
            start=date(2025, 9, 14),
            end=date(2026, 9, 14),
            sample_size=2,
        )
        output.write_bytes(collected.dataset.model_dump_json().encode())
        request = MarketResearchRequest(
            market="US",
            start_date=date(2025, 9, 14),
            end_date=date(2026, 9, 14),
            research_grade="approximate",
        )
        source = ApproximateMarketHistorySource(JsonApproximateProvider(output))
        snapshot = await source.collect(
            request, captured_at=datetime(2026, 9, 16, tzinfo=UTC)
        )
        readiness = source.readiness("US", datetime(2026, 9, 16, tzinfo=UTC))
        result = run_approximate_market_research(
            snapshot, request, readiness, default_market_calendar()
        )
        return snapshot, result

    baseline_snapshot, baseline_result = asyncio.run(
        run(("AAA", "NEW"), tmp_path / "baseline.json")
    )
    changed_snapshot, changed_result = asyncio.run(
        run(("AAA", "OTHER"), tmp_path / "changed.json")
    )
    checkpoint = date(2026, 1, 2)
    baseline_membership_prefix = tuple(
        item
        for item in baseline_snapshot.memberships
        if item.valid_from < checkpoint
    )
    changed_membership_prefix = tuple(
        item
        for item in changed_snapshot.memberships
        if item.valid_from < checkpoint
    )
    baseline_evidence_prefix = tuple(
        item
        for item in baseline_result.candidate_evidence
        if item.session < checkpoint
    )
    changed_evidence_prefix = tuple(
        item
        for item in changed_result.candidate_evidence
        if item.session < checkpoint
    )
    assert baseline_membership_prefix == changed_membership_prefix
    assert baseline_evidence_prefix == changed_evidence_prefix
    assert baseline_result.status == changed_result.status == "approximate"
    assert baseline_evidence_prefix
    assert any(
        item.symbol == "NEW"
        for item in baseline_result.candidate_evidence
        if item.session >= checkpoint
    )
    assert any(
        item.symbol == "OTHER"
        for item in changed_result.candidate_evidence
        if item.session >= checkpoint
    )


def test_alpha_later_checkpoint_failure_preserves_initial_pool_and_reports_gap() -> (
    None
):
    kwargs = {
        "market": "US",
        "start": date(2025, 9, 14),
        "end": date(2026, 9, 14),
        "sample_size": 1,
    }
    present_transport = _USCheckpointTransport(fail_later=False)
    failed_transport = _USCheckpointTransport(fail_later=True)
    present = asyncio.run(FreeMarketDataCollector(present_transport).collect(**kwargs))
    failed = asyncio.run(FreeMarketDataCollector(failed_transport).collect(**kwargs))
    assert {row.symbol for row in present.dataset.universe} == {
        row.symbol for row in failed.dataset.universe
    }
    assert present.dataset.source == failed.dataset.source == "alpha_vantage"
    assert failed_transport.alpha_calls == present_transport.alpha_calls
    assert any(
        "membership checkpoint unavailable" in item for item in failed.limitations
    )


@pytest.mark.parametrize(
    ("mode", "reason"),
    [
        ("split", "listed share count changed"),
        ("halt", "halt or missing trade bar"),
        ("delisting", "delisting"),
    ],
)
def test_krx_event_forward_exclusion_is_truthful(mode: str, reason: str) -> None:
    result = asyncio.run(
        FreeMarketDataCollector(_CorporateActionTransport(mode)).collect(
            market="KR",
            start=date(2025, 9, 14),
            end=date(2026, 9, 14),
            sample_size=1,
        )
    )
    assert any(reason in limitation for limitation in result.limitations)
    assert all(bar.session < date(2026, 1, 5) for bar in result.dataset.bars)


def test_cli_collector_missing_keys_is_controlled_and_cache_status_is_truthful(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    for name in ("KRX_AUTH_KEY", "ALPHA_VANTAGE_API_KEY", "FRED_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    assert (
        market_research_cli(
            [
                "collect",
                "--market",
                "KR",
                "--start",
                "2025-01-01",
                "--end",
                "2026-01-01",
                "--output",
                str(tmp_path / "prepared.json"),
                "--cache",
                str(tmp_path / "cache"),
            ]
        )
        == 2
    )
    assert "KRX_AUTH_KEY" in capsys.readouterr().out
    assert (
        market_research_cli(
            ["collect-status", "--market", "KR", "--cache", str(tmp_path / "cache")]
        )
        == 2
    )
    status = json.loads(capsys.readouterr().out)
    assert status["ready"] is False
    assert status["entries"] == 0


def test_collector_settings_explicit_file_alias_precedence_and_no_interpolation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in (
        "KRX_AUTH_KEY",
        "KRX_API_KEY",
        "ALPHA_VANTAGE_API_KEY",
        "ALPHA_VANTAGE_KEY",
        "FRED_API_KEY",
        "FRED_KEY",
        "MARKET_DATA_REQUEST_BUDGET",
    ):
        monkeypatch.delenv(name, raising=False)
    env_file = tmp_path / "collector.env"
    env_file.write_text(
        "KRX_AUTH_KEY=file-standard\n"
        "KRX_API_KEY=file-alias\n"
        "ALPHA_VANTAGE_KEY=file-alpha\n"
        "FRED_KEY=${UNSET_VALUE}\n"
        "MARKET_DATA_REQUEST_BUDGET=123\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("KRX_API_KEY", "process-alias")
    settings = load_collector_settings(env_file)
    assert settings.krx_auth_key is not None
    assert settings.krx_auth_key.get_secret_value() == "file-standard"
    assert settings.alpha_vantage_api_key is not None
    assert settings.alpha_vantage_api_key.get_secret_value() == "file-alpha"
    assert settings.fred_api_key is not None
    assert settings.fred_api_key.get_secret_value() == "${UNSET_VALUE}"
    assert settings.request_budget == 123

    monkeypatch.setenv("KRX_AUTH_KEY", "process-standard")
    process_settings = load_collector_settings(env_file)
    assert process_settings.krx_auth_key is not None
    assert process_settings.krx_auth_key.get_secret_value() == "process-standard"
    with pytest.raises(CollectorError, match="environment file"):
        load_collector_settings(tmp_path / "missing.env")


@pytest.mark.parametrize("budget", ["0", "10001", "not-a-number"])
@pytest.mark.parametrize("command", ["status", "collect", "collect-status"])
def test_cli_rejects_invalid_budget_without_echoing_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    budget: str,
    command: str,
) -> None:
    monkeypatch.delenv("MARKET_DATA_REQUEST_BUDGET", raising=False)
    env_file = tmp_path / "invalid-collector.env"
    env_file.write_text(f"MARKET_DATA_REQUEST_BUDGET={budget}\n", encoding="utf-8")
    if command == "status":
        arguments = ["status", "--market", "KR", "--env-file", str(env_file)]
    elif command == "collect":
        arguments = [
            "collect",
            "--market",
            "KR",
            "--start",
            "2026-01-01",
            "--end",
            "2026-09-14",
            "--output",
            str(tmp_path / "prepared.json"),
            "--cache",
            str(tmp_path / "cache"),
            "--env-file",
            str(env_file),
        ]
    else:
        arguments = [
            "collect-status",
            "--market",
            "KR",
            "--cache",
            str(tmp_path / "cache"),
            "--env-file",
            str(env_file),
        ]

    assert market_research_cli(arguments) == 2
    output = capsys.readouterr().out
    payload = json.loads(output)
    assert payload["reason"] == "environment configuration is invalid"
    assert budget not in output
    assert str(env_file) not in output


class _RetryingHttpClient:
    def __init__(self) -> None:
        self.calls = 0

    async def request(self, method: str, url: str, **kwargs: object) -> httpx.Response:
        self.calls += 1
        if self.calls == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, content=b"ok")


@pytest.mark.parametrize("status", [401, 403])
def test_http_fetcher_auth_failures_are_nonretryable_and_not_cached(
    tmp_path: Path, status: int
) -> None:
    class StatusClient:
        def __init__(self) -> None:
            self.calls = 0

        async def request(
            self, method: str, url: str, **kwargs: object
        ) -> httpx.Response:
            self.calls += 1
            return httpx.Response(status, content=b"sensitive provider response")

    client = StatusClient()
    fetcher = HttpFetcher(
        client=client,
        cache=AtomicResponseCache(tmp_path),
        settings=CollectorSettings(krx_auth_key="configured", request_budget=3),
    )
    with pytest.raises(CollectorAuthenticationError, match="authentication"):
        asyncio.run(
            fetcher.get(
                source="krx",
                url="https://example.test/daily",
                params={"basDd": "20260914"},
            )
        )
    assert client.calls == 1
    assert not (tmp_path / "manifest.json").exists()


def test_http_fetcher_retries_429_and_counts_one_bounded_request(
    tmp_path: Path,
) -> None:
    client = _RetryingHttpClient()
    fetcher = HttpFetcher(
        client=client,
        cache=AtomicResponseCache(tmp_path),
        settings=CollectorSettings(request_budget=2),
    )
    assert (
        asyncio.run(
            fetcher.get(
                source="yahoo",
                url="https://example.test/chart",
                params={"symbol": "AAA", "apikey": "secret"},
            )
        )
        == b"ok"
    )
    assert client.calls == 2
    assert fetcher.requests_used == 2
    assert "secret" not in (tmp_path / "manifest.json").read_text()


def test_http_fetcher_budget_blocks_retry_attempt(tmp_path: Path) -> None:
    client = _RetryingHttpClient()
    fetcher = HttpFetcher(
        client=client,
        cache=AtomicResponseCache(tmp_path),
        settings=CollectorSettings(request_budget=1),
    )
    with pytest.raises(RequestBudgetExceeded, match="budget"):
        asyncio.run(
            fetcher.get(
                source="yahoo",
                url="https://example.test/chart",
                params={"symbol": "AAA"},
            )
        )
    assert client.calls == 1


def test_network_request_estimate_is_bounded_for_one_and_three_year_ranges() -> None:
    one_year = estimate_network_requests(
        market="KR", start=date(2025, 9, 14), end=date(2026, 9, 14)
    )
    three_year = estimate_network_requests(
        market="KR", start=date(2023, 9, 14), end=date(2026, 9, 14)
    )
    assert one_year > 0
    assert three_year > one_year
    assert three_year < 10_000


def test_us_network_request_estimate_includes_cumulative_admission_bound() -> None:
    one_year = estimate_network_requests(
        market="US", start=date(2025, 9, 14), end=date(2026, 9, 14), sample_size=1
    )
    one_year_full = estimate_network_requests(
        market="US", start=date(2025, 9, 14), end=date(2026, 9, 14), sample_size=100
    )
    three_year_full = estimate_network_requests(
        market="US", start=date(2023, 9, 14), end=date(2026, 9, 14), sample_size=100
    )
    assert one_year == 5
    assert one_year_full == 203
    assert three_year_full == 405


@pytest.mark.parametrize("resume", [False, True])
def test_collection_preflight_does_not_subtract_unrelated_cache(
    tmp_path: Path, resume: bool
) -> None:
    cache = AtomicResponseCache(tmp_path / "cache")
    cache.put(
        source="other",
        endpoint="https://example.test/other",
        request_key="unrelated",
        body=b"cached",
        status_code=200,
        captured_at=datetime(2026, 9, 14, tzinfo=UTC),
    )
    with pytest.raises(RequestBudgetExceeded, match="estimated"):
        asyncio.run(
            collect_market_data(
                market="KR",
                start=date(2025, 9, 14),
                end=date(2026, 9, 14),
                output=tmp_path / "prepared.json",
                cache_dir=tmp_path / "cache",
                settings=CollectorSettings(krx_auth_key="configured", request_budget=1),
                resume=resume,
                client=_RecordingHttpClient(),
            )
        )


def test_collect_status_requires_exact_completed_marker_and_valid_hash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cache = AtomicResponseCache(tmp_path / "cache")
    output = tmp_path / "prepared.json"
    content = json.dumps(
        {
            "market": "KR",
            "universe": [
                {
                    "session": "2026-09-14",
                    "symbol": "S1",
                    "name": "Sample",
                    "exchange": "KSC",
                    "currency": "KRW",
                }
            ],
            "bars": [
                {
                    "session": "2026-09-14",
                    "symbol": "S1",
                    "exchange": "KSC",
                    "open": "100",
                    "high": "101",
                    "low": "99",
                    "close": "100",
                    "volume": "1000",
                    "currency": "KRW",
                }
            ],
        }
    ).encode()
    output.write_bytes(content)
    cache.write_completed(
        market="KR",
        start=date(2026, 1, 1),
        end=date(2026, 9, 14),
        sample_size=1,
        output=output,
        content=content,
    )
    assert completed_collection_is_valid(
        cache,
        market="KR",
        start=date(2026, 1, 1),
        end=date(2026, 9, 14),
        sample_size=1,
        output=output,
    )
    monkeypatch.setenv("KRX_AUTH_KEY", "configured")
    status_args = [
        "collect-status",
        "--cache",
        str(tmp_path / "cache"),
        "--market",
        "KR",
        "--start",
        "2026-01-01",
        "--end",
        "2026-09-14",
        "--sample-size",
        "1",
        "--output",
        str(output),
    ]
    assert market_research_cli(status_args) == 0
    assert json.loads(capsys.readouterr().out)["ready"] is True
    assert not completed_collection_is_valid(
        cache,
        market="US",
        start=date(2026, 1, 1),
        end=date(2026, 9, 14),
        sample_size=1,
        output=output,
    )
    output.write_bytes(content + b"corrupt")
    assert not completed_collection_is_valid(
        cache,
        market="KR",
        start=date(2026, 1, 1),
        end=date(2026, 9, 14),
        sample_size=1,
        output=output,
    )
    assert market_research_cli(status_args) == 2
    assert json.loads(capsys.readouterr().out)["ready"] is False


def test_old_completion_marker_is_not_reused(tmp_path: Path) -> None:
    cache = AtomicResponseCache(tmp_path / "cache")
    output = tmp_path / "prepared.json"
    output.write_bytes(b"{}")
    cache.write_completed(
        market="KR",
        start=date(2026, 1, 1),
        end=date(2026, 9, 14),
        sample_size=1,
        output=output,
        content=b"{}",
    )
    marker = json.loads(cache.completed_path.read_text(encoding="utf-8"))
    marker["version"] = "collector-completed-v1"
    cache.completed_path.write_text(json.dumps(marker), encoding="utf-8")
    assert not completed_collection_is_valid(
        cache,
        market="KR",
        start=date(2026, 1, 1),
        end=date(2026, 9, 14),
        sample_size=1,
        output=output,
    )


def test_collect_status_rejects_malformed_manifest_without_dumping_cache_contents(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    (cache_dir / "manifest.json").write_text('{"entries": [', encoding="utf-8")

    result = market_research_cli(
        ["collect-status", "--market", "KR", "--cache", str(cache_dir)]
    )

    assert result == 2
    output = capsys.readouterr().out
    status = json.loads(output)
    assert status["completed"] is False
    assert status["ready"] is False
    assert status["cache_error"] == "cache manifest is invalid"
    assert '{"entries": [' not in output


def test_collect_status_rejects_malformed_completed_marker_without_traceback(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cache_dir = tmp_path / "cache"
    cache = AtomicResponseCache(cache_dir)
    cache_dir.mkdir()
    (cache.completed_path).write_text('{"market":', encoding="utf-8")

    result = market_research_cli(
        ["collect-status", "--market", "KR", "--cache", str(cache_dir)]
    )

    assert result == 2
    status = json.loads(capsys.readouterr().out)
    assert status["completed"] is False
    assert status["ready"] is False


class _RecordingHttpClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, object]]] = []

    async def request(self, method: str, url: str, **kwargs: object) -> httpx.Response:
        self.calls.append((method, url, kwargs))
        return httpx.Response(200, content=b'{"OutBlock_1": []}')


def test_network_krx_uses_official_get_daily_shape(tmp_path: Path) -> None:
    client = _RecordingHttpClient()
    settings = CollectorSettings(krx_auth_key="test-key")
    transport = NetworkCollectorTransport(
        HttpFetcher(
            client=client, cache=AtomicResponseCache(tmp_path), settings=settings
        ),
        settings,
    )
    asyncio.run(transport.krx("STK", date(2026, 9, 14), date(2026, 9, 14)))
    assert [call[0] for call in client.calls] == ["GET"]
    request = client.calls[0][2]
    params = request["params"]
    headers = request["headers"]
    assert isinstance(params, dict)
    assert params == {"basDd": "20260914"}
    assert isinstance(headers, dict)
    assert headers["AUTH_KEY"] == "test-key"
    assert "strtDd" not in params and "endDd" not in params
