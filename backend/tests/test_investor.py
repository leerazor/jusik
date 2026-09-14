import asyncio
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

import jusik.investor_data as investor_data
from jusik.fixture_app import app as fixture_app
from jusik.investor_analysis import analyze, evaluate_trend, review_thesis
from jusik.investor_data import KisInvestorProvider
from jusik.investor_models import (
    DailyBar,
    FundamentalFacts,
    Instrument,
    QuoteFact,
    Thesis,
    ThesisWrite,
    TrendFacts,
    ValuationAssumptions,
)
from jusik.investor_store import InvestorStore, ThesisConflictError


def _instrument(kind: str = "stock") -> Instrument:
    return Instrument(
        market="KR",
        exchange="KRX",
        symbol="005930",
        currency="KRW",
        name="fixture",
        instrument_type=kind,
    )  # type: ignore[arg-type]


def _bars(*, breakout: bool = False) -> list[DailyBar]:
    start = date(2026, 1, 1)
    rows = [
        DailyBar(
            session=start + timedelta(days=index),
            close=Decimal("100"),
            volume=Decimal("10"),
            adjusted=True,
        )
        for index in range(22)
    ]
    if breakout:
        rows[-1] = DailyBar(
            session=rows[-1].session,
            close=Decimal("120"),
            volume=Decimal("20"),
            adjusted=True,
        )
    return rows


def test_trend_requires_adjusted_completed_unique_bars() -> None:
    result = evaluate_trend(_bars(breakout=True), today=date(2026, 2, 1))
    assert result.breakout_observed is True
    future = _bars()
    future[-1] = future[-1].model_copy(update={"session": date(2027, 1, 1)})
    assert evaluate_trend(future, today=date(2026, 2, 1)).breakout_observed is None
    stale = evaluate_trend(
        _bars(), today=date(2026, 2, 1), expected_latest_session=date(2026, 1, 20)
    )
    assert stale.breakout_observed is None
    assert stale.unavailable_reasons


def test_value_requires_explicit_assumptions_and_etf_is_unassessed() -> None:
    quote = QuoteFact(
        price=Decimal("70"),
        currency="KRW",
        fetched_at="2026-01-01T00:00:00Z",
        source="fixture",
    )
    facts = FundamentalFacts(eps=Decimal("10"), per=Decimal("10"))
    trend = TrendFacts()
    missing = analyze(_instrument(), quote, facts, trend)
    assert missing.value_entry_status == "unassessed"
    assumptions = ValuationAssumptions(
        normalized_eps=Decimal("10"),
        eps_period="2025",
        target_pe_lower=Decimal("10"),
        target_pe_upper=Decimal("12"),
        margin_of_safety=Decimal("0.2"),
        rationale="fixture rationale",
    )
    assert (
        analyze(
            _instrument(), quote, facts, trend, assumptions=assumptions
        ).value_entry_status
        == "review"
    )
    assert (
        analyze(
            _instrument("etf"), quote, facts, trend, assumptions=assumptions
        ).value_entry_status
        == "unassessed"
    )


def test_store_conflict_and_idempotent_revision(tmp_path) -> None:
    store = InvestorStore(tmp_path / "investor.db")
    write = ThesisWrite(
        instrument=_instrument(),
        state="watch",
        entry_kind="value",
        why="확인",
        invalidation_criteria="무효",
        next_review=date(2026, 12, 1),
        health="unknown",
        expected_revision=0,
    )
    saved = store.save(
        None,
        write,
        analyze(
            _instrument(),
            QuoteFact(
                currency="KRW", fetched_at="2026-01-01T00:00:00Z", source="fixture"
            ),
            FundamentalFacts(),
            TrendFacts(),
        ),
    )
    repeated = store.save(
        saved.id, write.model_copy(update={"expected_revision": 1}), saved.evidence
    )
    assert repeated.revision == 1
    with pytest.raises(ThesisConflictError):
        store.save(
            saved.id, write.model_copy(update={"expected_revision": 0}), saved.evidence
        )
    assert len(store.revisions(saved.id)) == 1
    assert saved.review.decision == "deferred"


def test_thesis_review_keeps_value_drop_separate_from_trend_failure() -> None:
    quote = QuoteFact(
        price=Decimal("50"),
        currency="KRW",
        fetched_at="2026-01-01T00:00:00Z",
        source="fixture",
    )
    analysis = analyze(
        _instrument(),
        quote,
        FundamentalFacts(),
        TrendFacts(deterioration_observed=True),
    )
    thesis = ThesisWrite(
        instrument=_instrument(),
        state="holding",
        entry_kind="value",
        why="가치",
        invalidation_criteria="실적",
        next_review=date(2026, 12, 1),
        health="intact",
        expected_revision=0,
    )
    record = Thesis(
        **thesis.model_dump(exclude={"expected_revision"}),
        id="a" * 32,
        revision=1,
        created_at=analysis.analyzed_at,
        updated_at=analysis.analyzed_at,
        evidence=analysis,
    )
    assert (
        review_thesis(record, analysis, today=date(2026, 1, 2)).decision
        == "hold_review"
    )


def test_fixture_investor_routes() -> None:
    with TestClient(fixture_app) as client:
        response = client.get("/api/investor/candidates?market=KR")
        assert response.status_code == 200
        assert {
            item["instrument"]["instrument_type"]
            for item in response.json()["candidates"]
        } == {"stock", "etf", "unknown"}
        detail = client.get("/api/investor/instrument?market=KR&symbol=005930")
        assert detail.status_code == 200
        payload = detail.json()
        assert payload["analysis"]["instrument"]["instrument_type"] == "stock"
        assert (
            client.get(
                "/api/investor/instrument?market=KR&symbol=https://example.com"
            ).status_code
            == 422
        )
        saved = client.put(
            "/api/investor/theses",
            json={
                "instrument": payload["instrument"],
                "state": "watch",
                "entry_kind": "trend",
                "why": "fixture 확인",
                "source_references": ["fixture"],
                "invalidation_criteria": "fixture 무효화",
                "next_review": "2026-12-01",
                "health": "unknown",
                "risk_price": None,
                "valuation": None,
                "expected_revision": 0,
            },
        )
        assert saved.status_code == 200
        assert saved.json()["revision"] == 1
        updated_payload = {
            key: saved.json()[key]
            for key in (
                "instrument",
                "state",
                "entry_kind",
                "why",
                "source_references",
                "invalidation_criteria",
                "next_review",
                "health",
                "risk_price",
            )
        }
        updated_payload["expected_revision"] = 1
        updated_payload["valuation"] = {
            "normalized_eps": "6000",
            "eps_period": "2025-FY",
            "target_pe_lower": "10",
            "target_pe_upper": "12",
            "margin_of_safety": "0.2",
            "rationale": "fixture value range",
        }
        updated = client.put(
            f"/api/investor/theses/{saved.json()['id']}", json=updated_payload
        )
        assert updated.status_code == 200
        assert updated.json()["current_analysis"]["assumed_value_lower"] == "60000"
        assert updated.json()["current_analysis"]["assumed_safety_price"] == "48000.0"
        identity_mismatch = dict(updated_payload)
        identity_mismatch["instrument"] = dict(payload["instrument"])
        identity_mismatch["instrument"]["symbol"] = "069500"
        identity_mismatch["expected_revision"] = 2
        assert (
            client.put(
                f"/api/investor/theses/{saved.json()['id']}", json=identity_mismatch
            ).status_code
            == 409
        )
        forbidden = client.put(
            "/api/investor/theses",
            json={
                "instrument": payload["instrument"],
                "state": "watch",
                "entry_kind": "trend",
                "why": "fixture 확인",
                "source_references": [],
                "invalidation_criteria": "무효",
                "next_review": "2026-12-01",
                "health": "unknown",
                "risk_price": None,
                "valuation": None,
                "expected_revision": 0,
            },
            headers={"Origin": "https://evil.example"},
        )
        assert forbidden.status_code == 403


def test_review_closed_takes_priority_and_watch_is_not_sell_signal() -> None:
    analysis = analyze(
        _instrument(),
        QuoteFact(
            price=Decimal("50"),
            currency="KRW",
            fetched_at=datetime.now(UTC),
            source="fixture",
        ),
        FundamentalFacts(),
        TrendFacts(deterioration_observed=True),
    )
    closed = Thesis(
        **ThesisWrite(
            instrument=_instrument(),
            state="closed",
            entry_kind="trend",
            why="종료",
            invalidation_criteria="무효",
            next_review=date(2026, 12, 1),
            health="broken",
            expected_revision=0,
        ).model_dump(exclude={"expected_revision"}),
        id="b" * 32,
        revision=1,
        created_at=analysis.analyzed_at,
        updated_at=analysis.analyzed_at,
        evidence=analysis,
    )
    assert review_thesis(closed, analysis).decision == "closed"
    watch = closed.model_copy(update={"state": "watch", "health": "intact"})
    assert review_thesis(watch, analysis).decision == "hold_review"


def test_analysis_rejects_future_and_stale_quotes() -> None:
    now = datetime(2026, 9, 7, 10, tzinfo=UTC)
    base = dict(currency="KRW", source="fixture")
    future = QuoteFact(price=Decimal("10"), fetched_at=now.replace(day=8), **base)
    stale = QuoteFact(
        price=Decimal("10"),
        fetched_at=now,
        as_of=datetime(2026, 8, 1, tzinfo=UTC),
        **base,
    )
    for quote in (future, stale):
        result = analyze(
            _instrument(), quote, FundamentalFacts(), TrendFacts(), now=now
        )
        assert result.value_entry_status == "unassessed"
        assert any("보류" in reason for reason in result.reasons)


def test_stale_quote_cannot_trigger_risk_exit() -> None:
    now = datetime(2026, 9, 7, 10, tzinfo=UTC)
    analysis = analyze(
        _instrument(),
        QuoteFact(
            price=Decimal("10"),
            currency="KRW",
            fetched_at=now,
            as_of=datetime(2026, 8, 1, tzinfo=UTC),
            source="fixture",
        ),
        FundamentalFacts(),
        TrendFacts(),
        now=now,
    )
    write = ThesisWrite(
        instrument=_instrument(),
        state="holding",
        entry_kind="value",
        why="확인",
        invalidation_criteria="무효",
        next_review=date(2026, 12, 1),
        health="intact",
        risk_price=Decimal("20"),
        expected_revision=0,
    )
    thesis = Thesis(
        **write.model_dump(exclude={"expected_revision"}),
        id="c" * 32,
        revision=1,
        created_at=now,
        updated_at=now,
        evidence=analysis,
    )
    assert review_thesis(thesis, analysis, today=now.date()).decision == "deferred"


def test_source_reference_and_incomplete_instrument_bounds() -> None:
    with pytest.raises(ValueError):
        ThesisWrite(
            instrument=_instrument(),
            state="watch",
            entry_kind="value",
            why="확인",
            source_references=["x" * 501],
            invalidation_criteria="무효",
            next_review=date(2026, 12, 1),
            health="unknown",
            expected_revision=0,
        )
    with pytest.raises(ValueError):
        Instrument(
            market="KR",
            exchange="KOSDAQ",
            symbol="005930",
            currency="KRW",
            name="fixture",
        )


def test_provider_uses_official_rank_code_and_keeps_financial_periods() -> None:
    provider = KisInvestorProvider(None)  # type: ignore[arg-type]

    async def request(
        path: str, _tr_id: str, _params: dict[str, str]
    ) -> dict[str, object]:
        if path.endswith("volume-rank"):
            return {
                "output": [{"mksc_shrn_iscd": "005930", "hts_kor_isnm": "삼성전자"}]
            }
        if path.endswith("financial-ratio"):
            return {
                "output": [
                    {
                        "stac_yymm": "202512",
                        "eps": "6000",
                        "roe_val": "10",
                        "lblt_rate": "20",
                    }
                ]
            }
        return {"output": [{"stac_yymm": "202512", "grs": "5"}]}

    provider._request = request  # type: ignore[method-assign]
    result = asyncio.run(provider.discover("KR"))
    assert result.candidates[0].instrument.symbol == "005930"
    facts = asyncio.run(
        provider._kr_financials(
            "005930", FundamentalFacts(eps=Decimal("1"), source="KIS quote")
        )
    )
    assert facts.eps == Decimal("6000")
    assert facts.period_end == date(2025, 12, 31)
    assert facts.growth_period_end == date(2025, 12, 31)


def test_yahoo_mismatched_series_lengths_are_deferred(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.now(UTC)
    local_date = now.astimezone(ZoneInfo("America/New_York")).date()

    class FakeClient:
        def __init__(self, **_kwargs: object) -> None:
            pass

        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def get(self, *_args: object, **_kwargs: object) -> SimpleNamespace:
            return SimpleNamespace(
                status_code=200,
                json=lambda: {
                    "chart": {
                        "result": [
                            {
                                "meta": {"symbol": "NVDA", "instrumentType": "EQUITY"},
                                "timestamp": [1, 2],
                                "indicators": {
                                    "quote": [{"close": [1], "volume": [1, 2]}],
                                    "adjclose": [{"adjclose": [1, 2]}],
                                },
                            }
                        ]
                    }
                },
            )

    class FakeCalendar:
        def latest_completed_session(
            self, _exchange: str, _at: datetime
        ) -> SimpleNamespace:
            return SimpleNamespace(
                local_date=local_date,
                close_at=now - timedelta(hours=1),
            )

    monkeypatch.setattr(investor_data.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(
        investor_data, "default_market_calendar", lambda: FakeCalendar()
    )
    provider = KisInvestorProvider(None)  # type: ignore[arg-type]
    instrument = Instrument(
        market="US",
        exchange="NAS",
        symbol="NVDA",
        currency="USD",
        name="NVIDIA",
        instrument_type="stock",
    )
    trend, provider_type = asyncio.run(provider._yahoo_trend(instrument))
    assert trend.breakout_observed is None
    assert trend.unavailable_reasons
    assert provider_type == "stock"
