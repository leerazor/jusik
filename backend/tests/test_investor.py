from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from jusik.fixture_app import app as fixture_app
from jusik.investor_analysis import analyze, evaluate_trend, review_thesis
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
