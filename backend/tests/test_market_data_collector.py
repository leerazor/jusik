from __future__ import annotations

import asyncio
import json
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

import httpx
import pytest

from jusik.market_data_collector import (
    AtomicResponseCache,
    CollectorError,
    CollectorSettings,
    FreeMarketDataCollector,
    HttpFetcher,
    NetworkCollectorTransport,
    RequestBudgetExceeded,
    parse_alpha_vantage_listing_status,
    parse_fred_observations,
    parse_krx_daily_response,
    parse_krx_daily_trade_response,
    parse_yahoo_chart,
)
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
                {
                    "basDd": "2026-09-15",
                    "symbol": "123456",
                    "name": "Sample",
                    "market": "KOSDAQ",
                },
            ]
        }
    ).encode()
    rows = parse_krx_daily_response(body, checkpoint=date(2026, 9, 14))
    assert [(row.session, row.symbol, row.exchange) for row in rows] == [
        (date(2026, 9, 14), "005930", "KOSPI"),
        (date(2026, 9, 15), "123456", "KOSDAQ"),
    ]
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


class _RetryingHttpClient:
    def __init__(self) -> None:
        self.calls = 0

    async def request(self, method: str, url: str, **kwargs: object) -> httpx.Response:
        self.calls += 1
        if self.calls == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, content=b"ok")


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


class _RecordingHttpClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, object]]] = []

    async def request(self, method: str, url: str, **kwargs: object) -> httpx.Response:
        self.calls.append((method, url, kwargs))
        return httpx.Response(200, content=b'{"OutBlock_1": []}')


def test_network_krx_uses_official_post_daily_and_basic_shapes(tmp_path: Path) -> None:
    client = _RecordingHttpClient()
    settings = CollectorSettings(krx_auth_key="test-key")
    transport = NetworkCollectorTransport(
        HttpFetcher(
            client=client, cache=AtomicResponseCache(tmp_path), settings=settings
        ),
        settings,
    )
    asyncio.run(transport.krx("STK", date(2026, 9, 14), date(2026, 9, 14)))
    asyncio.run(transport.krx_basic_info("ALL"))
    assert [call[0] for call in client.calls] == ["POST", "POST"]
    daily = client.calls[0][2]["data"]
    assert isinstance(daily, dict)
    assert daily["bld"] == "dbms/MDC/STAT/standard/MDCSTAT01501"
    assert daily["mktId"] == "STK"
    assert daily["trdDd"] == "20260914"
    assert "strtDd" not in daily and "endDd" not in daily
    basic = client.calls[1][2]["data"]
    assert isinstance(basic, dict)
    assert basic["bld"] == "dbms/MDC/STAT/standard/MDCSTAT01901"
    assert basic["mktId"] == "ALL"
