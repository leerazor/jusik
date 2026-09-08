import asyncio
import sqlite3
from datetime import date
from pathlib import Path

import httpx
import pytest

from jusik.research_config import PAPER_BASE_URL, ResearchSettings
from jusik.research_data import (
    DataInsufficientError,
    KisPaperHistoricalData,
    extract_symbol_name,
)


def settings(tmp_path: Path) -> ResearchSettings:
    return ResearchSettings(
        app_key="key",
        app_secret="secret",
        base_url=PAPER_BASE_URL,
        db_path=tmp_path / "research.db",
    )


def row(day: str, price: str, *, volume: str = "100") -> dict[str, str]:
    return {
        "stck_bsop_date": day,
        "stck_oprc": price,
        "stck_hgpr": price,
        "stck_lwpr": price,
        "stck_clpr": price,
        "acml_vol": volume,
    }


def test_daily_history_paginates_backward_and_preserves_zero_volume(
    tmp_path: Path,
) -> None:
    calls: list[str] = []
    names: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.params["FID_INPUT_DATE_2"])
        end = request.url.params["FID_INPUT_DATE_2"]
        output = (
            [row("20250103", "103"), row("20250102", "102", volume="0")]
            if end >= "20250103"
            else [row("20250101", "101")]
        )
        return httpx.Response(
            200,
            json={
                "rt_cd": "0",
                "output1": {
                    "rprs_mrkt_kor_name": "코스피",
                    "hts_kor_isnm": "삼성전자",
                    "stck_shrn_iscd": "005930",
                },
                "output2": output,
            },
        )

    async def run() -> None:
        async with httpx.AsyncClient(
            base_url=PAPER_BASE_URL, transport=httpx.MockTransport(handler)
        ) as client:
            provider = KisPaperHistoricalData(
                settings(tmp_path),
                client,
                request_interval_seconds=0,
                on_symbol_metadata=lambda symbol, name: names.append((symbol, name)),
            )
            rows, market = await provider._series(
                "token",
                "005930",
                date(2025, 1, 1),
                date(2025, 1, 3),
                adjusted=False,
            )
        assert set(rows) == {
            date(2025, 1, 1),
            date(2025, 1, 2),
            date(2025, 1, 3),
        }
        assert rows[date(2025, 1, 2)].acml_vol == 0
        assert market == "코스피"

    asyncio.run(run())
    assert calls == ["20250103", "20250101"]
    assert names == [("005930", "삼성전자"), ("005930", "삼성전자")]


def test_symbol_name_requires_valid_name_and_matching_reported_code() -> None:
    assert (
        extract_symbol_name(
            {"hts_kor_isnm": " 삼성전자 ", "stck_shrn_iscd": "005930"},
            "005930",
        )
        == "삼성전자"
    )
    assert extract_symbol_name({"hts_kor_isnm": "NAVER"}, "035420") == "NAVER"
    assert (
        extract_symbol_name(
            {"hts_kor_isnm": "다른 종목", "stck_shrn_iscd": "000660"},
            "005930",
        )
        is None
    )
    assert extract_symbol_name({"hts_kor_isnm": " \n "}, "005930") is None
    assert extract_symbol_name({}, "005930") is None


def test_symbol_metadata_storage_failure_does_not_fail_valid_daily_data(
    tmp_path: Path,
) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "rt_cd": "0",
                "output1": {
                    "rprs_mrkt_kor_name": "코스피",
                    "hts_kor_isnm": "삼성전자",
                    "stck_shrn_iscd": "005930",
                },
                "output2": [row("20250101", "101")],
            },
        )

    def fail_metadata(_: str, __: str) -> None:
        raise sqlite3.OperationalError("local metadata database unavailable")

    async def run() -> None:
        async with httpx.AsyncClient(
            base_url=PAPER_BASE_URL, transport=httpx.MockTransport(handler)
        ) as client:
            provider = KisPaperHistoricalData(
                settings(tmp_path),
                client,
                request_interval_seconds=0,
                on_symbol_metadata=fail_metadata,
            )
            rows, market = await provider._request_page(
                "token",
                "005930",
                date(2025, 1, 1),
                date(2025, 1, 1),
                adjusted=False,
            )
        assert len(rows) == 1
        assert rows[0].trading_date == date(2025, 1, 1)
        assert market == "코스피"

    asyncio.run(run())


def test_history_rejects_changing_adjustment_ratio(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        adjusted = request.url.params["FID_ORG_ADJ_PRC"] == "0"
        output = [
            row("20250102", "50" if adjusted else "100"),
            row("20250101", "100"),
        ]
        return httpx.Response(200, json={"rt_cd": "0", "output2": output})

    async def run() -> None:
        async with httpx.AsyncClient(
            base_url=PAPER_BASE_URL, transport=httpx.MockTransport(handler)
        ) as client:
            provider = KisPaperHistoricalData(
                settings(tmp_path), client, request_interval_seconds=0
            )
            with pytest.raises(DataInsufficientError, match="수정 비율 변화"):
                await provider._symbol(
                    "token", "005930", date(2025, 1, 1), date(2025, 1, 2)
                )

    asyncio.run(run())


def test_history_rejects_invalid_ohlc_instead_of_coercing_it(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        invalid = row("20250101", "100")
        invalid["stck_hgpr"] = "90"
        return httpx.Response(200, json={"rt_cd": "0", "output2": [invalid]})

    async def run() -> None:
        async with httpx.AsyncClient(
            base_url=PAPER_BASE_URL, transport=httpx.MockTransport(handler)
        ) as client:
            provider = KisPaperHistoricalData(
                settings(tmp_path), client, request_interval_seconds=0
            )
            with pytest.raises(DataInsufficientError, match="응답을 검증"):
                await provider._symbol(
                    "token", "005930", date(2025, 1, 1), date(2025, 1, 1)
                )

    asyncio.run(run())
