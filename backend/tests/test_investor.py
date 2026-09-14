import asyncio
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

import jusik.investor_data as investor_data
from jusik.fixture_app import app as fixture_app
from jusik.investor_analysis import analyze, evaluate_trend, quote_status, review_thesis
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
        == "unassessed"
    )
    quote_with_time = quote.model_copy(
        update={
            "as_of": datetime(2026, 1, 2, 6, tzinfo=UTC),
            "fetched_at": datetime(2026, 1, 2, 6, tzinfo=UTC),
        }
    )
    assert (
        analyze(
            _instrument(),
            quote_with_time,
            facts,
            trend,
            assumptions=assumptions,
            now=datetime(2026, 1, 2, 6, tzinfo=UTC),
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
        fetched_at="2026-01-02T06:00:00Z",
        source="fixture",
        as_of="2026-01-02T06:00:00Z",
    )
    analysis = analyze(
        _instrument(),
        quote,
        FundamentalFacts(),
        TrendFacts(deterioration_observed=True),
        now=datetime(2026, 1, 2, 6, tzinfo=UTC),
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
        payload = response.json()
        assert {
            item["instrument"]["instrument_type"] for item in payload["candidates"]
        } == {"stock"}
        assert {
            item["instrument"]["instrument_type"] for item in payload["etf_candidates"]
        } == {"etf"}
        assert payload["counts"]["unknown"] == 1
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
        thesis_id = saved.json()["id"]
        revisions_before = len(fixture_app.state.investor_store.revisions(thesis_id))
        fresh = client.get(f"/api/investor/theses/{thesis_id}")
        assert fresh.status_code == 200
        assert fresh.json()["current_analysis"]["assumed_value_lower"] == "60000"
        detail_obj = fixture_app.state.investor_provider.details[("KR", "005930")]
        changed_quote = detail_obj.analysis.quote.model_copy(
            update={"price": Decimal("50000")}
        )
        changed_detail = detail_obj.model_copy(
            update={
                "analysis": analyze(
                    detail_obj.instrument,
                    changed_quote,
                    detail_obj.analysis.fundamentals,
                    detail_obj.analysis.trend,
                    now=detail_obj.analysis.analyzed_at,
                )
            }
        )
        fixture_app.state.investor_provider.details[("KR", "005930")] = changed_detail
        changed = client.get(f"/api/investor/theses/{thesis_id}")
        assert changed.json()["current_analysis"]["quote"]["price"] == "50000"
        assert changed.json()["current_analysis"]["value_entry_status"] == "unassessed"
        assert (
            len(fixture_app.state.investor_store.revisions(thesis_id))
            == revisions_before
        )
        fixture_app.state.investor_provider.details[("KR", "005930")] = detail_obj
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
            as_of=datetime.now(UTC),
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


def test_quote_status_uses_exchange_sessions_for_freshness() -> None:
    weekend_now = datetime(2026, 9, 12, 15, tzinfo=UTC)
    friday_quote = QuoteFact(
        price=Decimal("100"),
        currency="USD",
        as_of=datetime(2026, 9, 11, 20, tzinfo=UTC),
        fetched_at=weekend_now,
        source="fixture",
    )
    assert (
        quote_status(
            Instrument(
                market="US",
                exchange="NYS",
                symbol="ABC",
                currency="USD",
                name="ABC",
            ),
            friday_quote,
            weekend_now,
        )
        == "usable"
    )
    monday_now = datetime(2026, 9, 14, 15, tzinfo=UTC)
    stale_quote = friday_quote.model_copy(
        update={
            "as_of": datetime(2026, 9, 8, 20, tzinfo=UTC),
            "fetched_at": monday_now,
        }
    )
    us_instrument = Instrument(
        market="US", exchange="NYS", symbol="ABC", currency="USD", name="ABC"
    )
    assert quote_status(us_instrument, stale_quote, monday_now) == "stale"
    kr_now = datetime(2026, 9, 14, 1, tzinfo=UTC)
    kr_quote = QuoteFact(
        price=Decimal("100"),
        currency="KRW",
        as_of=kr_now,
        fetched_at=kr_now,
        source="fixture",
    )
    assert quote_status(_instrument(), kr_quote, kr_now) == "usable"
    coverage_now = datetime(2027, 1, 4, 1, tzinfo=UTC)
    out_of_coverage = kr_quote.model_copy(
        update={"as_of": coverage_now, "fetched_at": coverage_now}
    )
    assert (
        quote_status(_instrument(), out_of_coverage, coverage_now)
        == "calendar_unavailable"
    )


def test_quote_status_limits_active_session_to_one_hour() -> None:
    now = datetime(2026, 9, 14, 15, tzinfo=UTC)
    instrument = Instrument(
        market="US", exchange="NYS", symbol="ABC", currency="USD", name="ABC"
    )
    recent = QuoteFact(
        price=Decimal("100"),
        currency="USD",
        as_of=datetime(2026, 9, 14, 14, 30, tzinfo=UTC),
        fetched_at=now,
        source="fixture",
    )
    delayed = recent.model_copy(
        update={"as_of": datetime(2026, 9, 14, 13, 59, tzinfo=UTC)}
    )
    assert quote_status(instrument, recent, now) == "usable"
    assert quote_status(instrument, delayed, now) == "stale"


def test_quote_status_limits_completed_session_lag_and_fetch_age() -> None:
    now = datetime(2026, 9, 14, 15, tzinfo=UTC)
    instrument = Instrument(
        market="US", exchange="NYS", symbol="ABC", currency="USD", name="ABC"
    )
    close_quote = QuoteFact(
        price=Decimal("100"),
        currency="USD",
        as_of=datetime(2026, 9, 11, 20, tzinfo=UTC),
        fetched_at=now,
        source="fixture",
    )
    delayed = close_quote.model_copy(
        update={"as_of": datetime(2026, 9, 11, 18, 59, tzinfo=UTC)}
    )
    old_fetch = close_quote.model_copy(
        update={"fetched_at": now - timedelta(minutes=16)}
    )
    assert quote_status(instrument, close_quote, now) == "usable"
    assert quote_status(instrument, delayed, now) == "stale"
    assert quote_status(instrument, old_fetch, now) == "stale"


def test_currency_mismatch_cannot_trigger_risk_exit() -> None:
    now = datetime(2026, 9, 14, 1, tzinfo=UTC)
    quote = QuoteFact(
        price=Decimal("10"),
        currency="KRW",
        as_of=now,
        fetched_at=now,
        source="fixture",
    )
    analysis = analyze(
        _instrument().model_copy(
            update={
                "market": "US",
                "currency": "USD",
                "exchange": "NYS",
                "symbol": "ABC",
                "name": "ABC",
            }
        ),
        quote,
        FundamentalFacts(),
        TrendFacts(),
        now=now,
    )
    thesis = Thesis(
        **ThesisWrite(
            instrument=analysis.instrument,
            state="holding",
            entry_kind="value",
            why="확인",
            invalidation_criteria="무효",
            next_review=date(2026, 12, 1),
            health="intact",
            risk_price=Decimal("60"),
            expected_revision=0,
        ).model_dump(exclude={"expected_revision"}),
        id="d" * 32,
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


def test_provider_uses_official_rank_code_and_keeps_financial_periods(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = KisInvestorProvider(None)  # type: ignore[arg-type]

    async def request(
        path: str, _tr_id: str, _params: dict[str, str]
    ) -> dict[str, object]:
        if path.endswith("volume-rank"):
            return {
                "output": [
                    {
                        "mksc_shrn_iscd": "005930",
                        "hts_kor_isnm": "삼성전자",
                        "acml_vol": "100",
                    }
                ]
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

    async def classify(*_args: object, **_kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(
            instrument_type="stock", relative_volume=None, reason=None, failed=False
        )

    monkeypatch.setattr(provider, "_request", request)
    monkeypatch.setattr(provider, "_candidate_chart", classify)
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


def test_rank_rows_attempts_each_us_exchange_and_sorts_decimal_volume() -> None:
    provider = KisInvestorProvider(None)  # type: ignore[arg-type]
    requested: list[str] = []

    async def request(
        path: str, _tr_id: str, params: dict[str, str]
    ) -> dict[str, object]:
        if path.endswith("trade-vol"):
            exchange = params["EXCD"]
            requested.append(exchange)
            if exchange == "NYS":
                raise investor_data.httpx.HTTPError("fixture failure")
            return {
                "output2": [
                    {
                        "symb": "AAA" if exchange == "NAS" else "BBB",
                        "excd": exchange,
                        "tvol": "100" if exchange == "NAS" else "80",
                    }
                ]
            }
        return {}

    provider._request = request  # type: ignore[method-assign]
    rows, source_rows, errors = asyncio.run(
        provider._rank_rows("US", datetime(2026, 9, 7, 10, tzinfo=UTC))
    )
    assert requested == ["NAS", "NYS", "AMS"]
    assert source_rows == 2
    assert [row.instrument.symbol for row in rows] == ["AAA", "BBB"]
    assert [row.volume for row in rows] == [Decimal("100"), Decimal("80")]
    assert errors


def test_us_qualified_symbol_prefix_is_split_only_for_rsym() -> None:
    observed_at = datetime(2026, 9, 7, 10, tzinfo=UTC)
    qualified = investor_data.KisInvestorProvider._parse_rank_row(
        "US",
        "NAS",
        {"rsym": "DNASNVDA", "tvol": "90"},
        observed_at,
    )
    plain = investor_data.KisInvestorProvider._parse_rank_row(
        "US",
        "NAS",
        {"symb": "DIA", "tvol": "80"},
        observed_at,
    )
    conflict = investor_data.KisInvestorProvider._parse_rank_row(
        "US",
        "NAS",
        {"rsym": "DNYSNVDA", "tvol": "90"},
        observed_at,
    )
    assert qualified is not None and qualified.instrument.symbol == "NVDA"
    assert plain is not None and plain.instrument.symbol == "DIA"
    assert conflict is None


def test_classification_caps_each_verified_type_separately_after_sort() -> None:
    provider = KisInvestorProvider(None)  # type: ignore[arg-type]
    observed_at = datetime(2026, 9, 7, 10, tzinfo=UTC)
    rows = [
        investor_data._RankedRow(
            instrument=Instrument(
                market="US",
                exchange="NAS",
                symbol=f"E{index:02d}",
                currency="USD",
                name=f"ETF {index}",
            ),
            volume=Decimal(200 - index),
            observed_at=observed_at,
            source="fixture",
        )
        for index in range(20)
    ] + [
        investor_data._RankedRow(
            instrument=Instrument(
                market="US",
                exchange="NAS",
                symbol=f"S{index:02d}",
                currency="USD",
                name=f"Stock {index}",
            ),
            volume=Decimal(100 - index),
            observed_at=observed_at,
            source="fixture",
        )
        for index in range(20)
    ]

    async def classify(*args: object, **_kwargs: object) -> SimpleNamespace:
        instrument = args[1] if len(args) > 1 else None
        symbol = instrument.symbol if isinstance(instrument, Instrument) else ""
        return SimpleNamespace(
            instrument_type="etf" if symbol.startswith("E") else "stock",
            relative_volume=None,
            reason=None,
            failed=False,
        )

    provider._candidate_chart = classify  # type: ignore[method-assign]
    result = asyncio.run(provider._classify_rows("US", rows, 40, [], observed_at))
    assert len(result.candidates) == 20
    assert len(result.etf_candidates) == 20
    assert result.counts.inspected == 40
    assert result.candidates[0].instrument.instrument_type == "stock"
    assert result.etf_candidates[0].instrument.instrument_type == "etf"


def test_relative_volume_uses_exact_twenty_prior_sessions_and_allows_zero_numerator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instrument = Instrument(
        market="US",
        exchange="NYS",
        symbol="ABC",
        currency="USD",
        name="ABC",
    )
    sessions: list[date] = []
    cursor = date(2026, 9, 11)
    while len(sessions) < 21:
        if cursor.weekday() < 5:
            sessions.append(cursor)
        cursor -= timedelta(days=1)

    def session_for(local_date: date) -> SimpleNamespace:
        opened = datetime(
            local_date.year, local_date.month, local_date.day, 13, 30, tzinfo=UTC
        )
        return SimpleNamespace(
            local_date=local_date,
            open_at=opened,
            close_at=opened + timedelta(hours=6, minutes=30),
        )

    class FakeCalendar:
        coverage_start = date(2026, 1, 1)

        def latest_completed_session(
            self, _exchange: str, _at: datetime
        ) -> SimpleNamespace:
            return session_for(sessions[0])

        def lookup(self, _exchange: str, local_date: date) -> SimpleNamespace:
            if local_date in sessions:
                return SimpleNamespace(state="session", session=session_for(local_date))
            return SimpleNamespace(state="closed", session=None)

    monkeypatch.setattr(investor_data, "default_market_calendar", FakeCalendar)
    anchor = session_for(sessions[0])
    fetched_at = anchor.close_at + timedelta(minutes=30)
    timestamps = [
        int(session_for(local_date).close_at.timestamp())
        for local_date in reversed(sessions)
    ]
    result = {
        "timestamp": timestamps,
        "indicators": {
            "quote": [{"volume": [10 for _ in timestamps]}],
        },
        "events": {"splits": {}},
    }
    meta = {
        "regularMarketVolume": 0,
        "regularMarketTime": int(anchor.close_at.timestamp()),
    }
    facts = KisInvestorProvider(None)._relative_volume(
        instrument, result, meta, fetched_at, "ABC"
    )
    assert facts.numerator == Decimal("0")
    assert facts.average20 == Decimal("10")
    assert facts.ratio == Decimal("0")
    assert facts.sample_count == 20
    assert facts.sample_start == sessions[-1]
    assert facts.sample_end == sessions[1]


def test_relative_volume_rejects_missing_history_and_splits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instrument = Instrument(
        market="US",
        exchange="NYS",
        symbol="ABC",
        currency="USD",
        name="ABC",
    )
    sessions: list[date] = []
    cursor = date(2026, 9, 11)
    while len(sessions) < 21:
        if cursor.weekday() < 5:
            sessions.append(cursor)
        cursor -= timedelta(days=1)

    def session_for(local_date: date) -> SimpleNamespace:
        opened = datetime(
            local_date.year, local_date.month, local_date.day, 13, 30, tzinfo=UTC
        )
        return SimpleNamespace(
            local_date=local_date,
            open_at=opened,
            close_at=opened + timedelta(hours=6, minutes=30),
        )

    class FakeCalendar:
        coverage_start = date(2026, 1, 1)

        def latest_completed_session(
            self, _exchange: str, _at: datetime
        ) -> SimpleNamespace:
            return session_for(sessions[0])

        def lookup(self, _exchange: str, local_date: date) -> SimpleNamespace:
            if local_date in sessions:
                return SimpleNamespace(state="session", session=session_for(local_date))
            return SimpleNamespace(state="closed", session=None)

    monkeypatch.setattr(investor_data, "default_market_calendar", FakeCalendar)
    anchor = session_for(sessions[0])
    fetched_at = anchor.close_at + timedelta(minutes=30)
    timestamps = [
        int(session_for(local_date).close_at.timestamp())
        for local_date in reversed(sessions)
    ]
    base = {
        "timestamp": timestamps,
        "indicators": {"quote": [{"volume": [10 for _ in timestamps]}]},
    }
    meta = {
        "regularMarketVolume": 100,
        "regularMarketTime": int(anchor.close_at.timestamp()),
    }
    missing = dict(base)
    missing["indicators"] = {"quote": [{"volume": [10 for _ in timestamps[:-1]]}]}
    missing_facts = KisInvestorProvider(None)._relative_volume(
        instrument, missing, meta, fetched_at, "ABC"
    )
    split = dict(base)
    split["events"] = {
        "splits": {
            "event": {"date": int(session_for(sessions[1]).close_at.timestamp())}
        }
    }
    split_facts = KisInvestorProvider(None)._relative_volume(
        instrument, split, meta, fetched_at, "ABC"
    )
    assert missing_facts.ratio is None
    assert missing_facts.unavailable_reason
    assert split_facts.ratio is None
    assert "분할" in (split_facts.unavailable_reason or "")


def test_provider_analyzes_quote_after_yahoo_fetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = KisInvestorProvider(None)  # type: ignore[arg-type]

    async def request(
        path: str, _tr_id: str, _params: dict[str, str]
    ) -> dict[str, object]:
        if path.endswith("inquire-price"):
            return {
                "output": {
                    "stck_shrn_iscd": "005930",
                    "stck_prpr": "100",
                    "eps": "10",
                    "per": "10",
                    "pbr": "1",
                }
            }
        return {"output": []}

    async def yahoo_trend(
        instrument: Instrument,
    ) -> tuple[TrendFacts, str, QuoteFact]:
        await asyncio.sleep(0.01)
        fetched_at = datetime.now(UTC)
        return (
            TrendFacts(source="fixture"),
            "stock",
            QuoteFact(
                price=Decimal("100"),
                currency="KRW",
                as_of=fetched_at,
                fetched_at=fetched_at,
                source="fixture",
            ),
        )

    monkeypatch.setattr(provider, "_request", request)
    monkeypatch.setattr(provider, "_yahoo_trend", yahoo_trend)
    instrument = Instrument(
        market="KR",
        exchange="KRX",
        symbol="005930",
        currency="KRW",
        name="삼성전자",
        instrument_type="stock",
    )
    detail = asyncio.run(provider.detail(instrument))
    assert detail.analysis.analyzed_at >= detail.analysis.quote.fetched_at
    assert (
        quote_status(
            detail.analysis.instrument,
            detail.analysis.quote,
            detail.analysis.analyzed_at,
        )
        == "usable"
    )


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
                                "meta": {
                                    "symbol": "NVDA",
                                    "instrumentType": "EQUITY",
                                    "currency": "USD",
                                    "exchangeName": "NMS",
                                    "exchangeTimezoneName": "America/New_York",
                                    "regularMarketPrice": 100,
                                    "regularMarketTime": 1789045200,
                                },
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
    trend, provider_type, quote = asyncio.run(provider._yahoo_trend(instrument))
    assert trend.breakout_observed is None
    assert trend.unavailable_reasons
    assert provider_type == "stock"
    assert quote is not None
    assert quote.price == Decimal("100")
    assert quote.as_of is not None


def test_yahoo_type_conflict_does_not_accept_verified_quote(
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
                                "meta": {
                                    "symbol": "NVDA",
                                    "instrumentType": "ETF",
                                    "currency": "USD",
                                    "exchangeName": "NMS",
                                    "exchangeTimezoneName": "America/New_York",
                                    "regularMarketPrice": 100,
                                    "regularMarketTime": 1789045200,
                                },
                                "timestamp": [],
                                "indicators": {},
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
    _trend, provider_type, quote = asyncio.run(provider._yahoo_trend(instrument))
    assert provider_type is None
    assert quote is None
