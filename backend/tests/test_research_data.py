import asyncio
import sqlite3
from datetime import UTC, date, datetime, timedelta
from email.utils import format_datetime
from pathlib import Path

import httpx
import pytest

from jusik.research_config import PAPER_BASE_URL, ResearchSettings
from jusik.research_data import (
    DataCollectionError,
    DataInsufficientError,
    KisPaperHistoricalData,
    extract_symbol_name,
)
from jusik.research_models import ResearchInputSnapshot, ResearchRunRequest
from jusik.research_store import ResearchStore
from jusik.research_worker import ResearchWorker


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


def test_daily_history_recovers_from_retryable_statuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = 0
    delays: list[float] = []

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503, json={"private": "do-not-expose"})
        if calls == 2:
            return httpx.Response(429, headers={"Retry-After": "0.5"})
        return httpx.Response(
            200, json={"rt_cd": "0", "output2": [row("20250101", "101")]}
        )

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr("jusik.research_data.asyncio.sleep", fake_sleep)

    async def run() -> None:
        async with httpx.AsyncClient(
            base_url=PAPER_BASE_URL, transport=httpx.MockTransport(handler)
        ) as client:
            provider = KisPaperHistoricalData(
                settings(tmp_path), client, request_interval_seconds=0
            )
            rows, _ = await provider._request_page(
                "token", "005930", date(2025, 1, 1), date(2025, 1, 1), adjusted=False
            )
        assert len(rows) == 1

    asyncio.run(run())
    assert calls == 3
    assert 1.0 in delays
    assert 0.5 in delays


def test_daily_history_recovers_from_read_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ReadTimeout("private-token", request=request)
        return httpx.Response(
            200, json={"rt_cd": "0", "output2": [row("20250101", "101")]}
        )

    async def fake_sleep(_: float) -> None:
        return None

    monkeypatch.setattr("jusik.research_data.asyncio.sleep", fake_sleep)

    async def run() -> None:
        async with httpx.AsyncClient(
            base_url=PAPER_BASE_URL, transport=httpx.MockTransport(handler)
        ) as client:
            provider = KisPaperHistoricalData(
                settings(tmp_path), client, request_interval_seconds=0
            )
            rows, _ = await provider._request_page(
                "token", "005930", date(2025, 1, 1), date(2025, 1, 1), adjusted=False
            )
        assert len(rows) == 1

    asyncio.run(run())
    assert calls == 2


def test_daily_history_does_not_retry_after_unbounded_server_delay(
    tmp_path: Path,
) -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(429, headers={"Retry-After": "60"})

    async def run() -> str:
        async with httpx.AsyncClient(
            base_url=PAPER_BASE_URL, transport=httpx.MockTransport(handler)
        ) as client:
            provider = KisPaperHistoricalData(
                settings(tmp_path), client, request_interval_seconds=0
            )
            with pytest.raises(DataCollectionError) as captured:
                await provider._request_page(
                    "token",
                    "005930",
                    date(2025, 1, 1),
                    date(2025, 1, 1),
                    adjusted=False,
                )
        return str(captured.value)

    message = asyncio.run(run())
    assert calls == 1
    assert "HTTP 429" in message
    assert "시도 1회" in message


def test_daily_history_does_not_retry_after_distant_http_date(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = 0
    now = datetime(2025, 1, 1, tzinfo=UTC)
    monkeypatch.setattr("jusik.research_data._utc_now", lambda: now)

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        retry_at = format_datetime(now + timedelta(seconds=60), usegmt=True)
        return httpx.Response(429, headers={"Retry-After": retry_at})

    async def run() -> None:
        async with httpx.AsyncClient(
            base_url=PAPER_BASE_URL, transport=httpx.MockTransport(handler)
        ) as client:
            provider = KisPaperHistoricalData(
                settings(tmp_path), client, request_interval_seconds=0
            )
            with pytest.raises(DataCollectionError, match="HTTP 429"):
                await provider._request_page(
                    "token",
                    "005930",
                    date(2025, 1, 1),
                    date(2025, 1, 1),
                    adjusted=False,
                )

    asyncio.run(run())
    assert calls == 1


def test_daily_history_honors_short_http_date(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = 0
    delays: list[float] = []
    now = datetime(2025, 1, 1, tzinfo=UTC)
    monkeypatch.setattr("jusik.research_data._utc_now", lambda: now)

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            retry_at = format_datetime(now + timedelta(seconds=3), usegmt=True)
            return httpx.Response(429, headers={"Retry-After": retry_at})
        return httpx.Response(
            200, json={"rt_cd": "0", "output2": [row("20250101", "101")]}
        )

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr("jusik.research_data.asyncio.sleep", fake_sleep)

    async def run() -> None:
        async with httpx.AsyncClient(
            base_url=PAPER_BASE_URL, transport=httpx.MockTransport(handler)
        ) as client:
            provider = KisPaperHistoricalData(
                settings(tmp_path), client, request_interval_seconds=0
            )
            rows, _ = await provider._request_page(
                "token", "005930", date(2025, 1, 1), date(2025, 1, 1), adjusted=False
            )
        assert len(rows) == 1

    asyncio.run(run())
    assert calls == 2
    assert 3.0 in delays


@pytest.mark.parametrize("status_code", [401, 403])
def test_daily_history_does_not_retry_client_errors(
    tmp_path: Path, status_code: int
) -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(status_code, json={"message": "private-account-secret"})

    async def run() -> str:
        async with httpx.AsyncClient(
            base_url=PAPER_BASE_URL, transport=httpx.MockTransport(handler)
        ) as client:
            provider = KisPaperHistoricalData(
                settings(tmp_path), client, request_interval_seconds=0
            )
            with pytest.raises(DataCollectionError) as captured:
                await provider._request_page(
                    "token",
                    "005930",
                    date(2025, 1, 1),
                    date(2025, 1, 1),
                    adjusted=False,
                )
        return str(captured.value)

    message = asyncio.run(run())
    assert calls == 1
    assert f"HTTP {status_code}" in message
    assert "시도 1회" in message
    assert "private-account-secret" not in message


def test_auth_and_business_failures_are_not_retried_or_leaked(tmp_path: Path) -> None:
    auth_calls = 0

    def auth_handler(_: httpx.Request) -> httpx.Response:
        nonlocal auth_calls
        auth_calls += 1
        return httpx.Response(401, json={"error": "private-auth-secret"})

    async def authenticate() -> str:
        async with httpx.AsyncClient(
            base_url=PAPER_BASE_URL, transport=httpx.MockTransport(auth_handler)
        ) as client:
            provider = KisPaperHistoricalData(
                settings(tmp_path), client, request_interval_seconds=0
            )
            with pytest.raises(DataCollectionError) as captured:
                await provider._authenticate()
        return str(captured.value)

    auth_message = asyncio.run(authenticate())
    assert auth_calls == 1
    assert "HTTP 401" in auth_message
    assert "private-auth-secret" not in auth_message

    business_calls = 0

    def business_handler(_: httpx.Request) -> httpx.Response:
        nonlocal business_calls
        business_calls += 1
        return httpx.Response(
            200, json={"rt_cd": "1", "msg1": "private-business-secret"}
        )

    async def request_business() -> str:
        async with httpx.AsyncClient(
            base_url=PAPER_BASE_URL,
            transport=httpx.MockTransport(business_handler),
        ) as client:
            provider = KisPaperHistoricalData(
                settings(tmp_path), client, request_interval_seconds=0
            )
            with pytest.raises(DataCollectionError) as captured:
                await provider._request_page(
                    "token",
                    "005930",
                    date(2025, 1, 1),
                    date(2025, 1, 1),
                    adjusted=False,
                )
        return str(captured.value)

    business_message = asyncio.run(request_business())
    assert business_calls == 1
    assert "code 1" in business_message
    assert "private-business-secret" not in business_message


def test_exhausted_daily_retry_marks_worker_failed_without_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503, json={"detail": "private-token"})

    async def fake_sleep(_: float) -> None:
        return None

    monkeypatch.setattr("jusik.research_data.asyncio.sleep", fake_sleep)

    async def exhaust() -> DataCollectionError:
        async with httpx.AsyncClient(
            base_url=PAPER_BASE_URL, transport=httpx.MockTransport(handler)
        ) as client:
            provider = KisPaperHistoricalData(
                settings(tmp_path), client, request_interval_seconds=0
            )
            with pytest.raises(DataCollectionError) as captured:
                await provider._request_page(
                    "token",
                    "005930",
                    date(2025, 1, 1),
                    date(2025, 1, 1),
                    adjusted=False,
                )
        return captured.value

    error = asyncio.run(exhaust())
    assert calls == 3
    assert "HTTP 503" in str(error)
    assert "시도 3회" in str(error)
    assert "private-token" not in str(error)

    class FailedProvider:
        async def collect(self, _: ResearchRunRequest) -> ResearchInputSnapshot:
            raise error

    store = ResearchStore(tmp_path / "worker.db")
    run = store.create(
        ResearchRunRequest(start_date=date(2025, 1, 1), end_date=date(2025, 1, 2))
    )
    worker = ResearchWorker(store, FailedProvider())
    asyncio.run(worker._process(run.id))

    failed = store.get(run.id)
    assert failed.status == "failed"
    assert failed.input_snapshot is None
    assert failed.error == str(error)


def test_retry_during_pagination_does_not_duplicate_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    failed_first_page = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal failed_first_page
        end = request.url.params["FID_INPUT_DATE_2"]
        calls.append(end)
        if not failed_first_page:
            failed_first_page = True
            return httpx.Response(503)
        output = (
            [row("20250103", "103"), row("20250102", "102")]
            if end == "20250103"
            else [row("20250101", "101")]
        )
        return httpx.Response(200, json={"rt_cd": "0", "output2": output})

    async def fake_sleep(_: float) -> None:
        return None

    monkeypatch.setattr("jusik.research_data.asyncio.sleep", fake_sleep)

    async def run() -> None:
        async with httpx.AsyncClient(
            base_url=PAPER_BASE_URL, transport=httpx.MockTransport(handler)
        ) as client:
            provider = KisPaperHistoricalData(
                settings(tmp_path), client, request_interval_seconds=0
            )
            rows, _ = await provider._series(
                "token", "005930", date(2025, 1, 1), date(2025, 1, 3), adjusted=False
            )
        assert list(sorted(rows)) == [
            date(2025, 1, 1),
            date(2025, 1, 2),
            date(2025, 1, 3),
        ]

    asyncio.run(run())
    assert calls == ["20250103", "20250103", "20250101"]
