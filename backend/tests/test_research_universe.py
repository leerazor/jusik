import asyncio
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

import jusik.research_universe as universe_module
from jusik.research_data import DataCollectionError, DataInsufficientError
from jusik.research_engine import run_signal_backtest
from jusik.research_external_models import ExternalFeatureSnapshot, ExternalObservation
from jusik.research_external_store import ExternalStore
from jusik.research_models import DailyBar, ResearchRunRequest
from jusik.research_optimizer import (
    SourceSnapshot,
    StopRequested,
    training_examples,
    walk_forward_folds,
)
from jusik.research_risk import ResearchRiskPolicy
from jusik.research_universe import collect_all, universe_status, write_reports
from jusik.research_universe_data import (
    REGISTRY,
    CollectedUniverseSnapshot,
    normalize_chart,
)
from jusik.research_universe_models import (
    CorporateAction,
    ExternalStrategyResult,
    OfflineInstrumentSnapshot,
    OfflineResearchRequest,
    OfflineResearchSnapshot,
    PriceAdjustmentFactor,
    ResearchInstrument,
)
from jusik.research_universe_store import UniverseInputStore, UniverseResultStore

CAPTURED_AT = datetime(2026, 9, 9, 12, tzinfo=UTC)
REQUESTED_START = date(2023, 9, 9)
REQUESTED_END = date(2026, 9, 8)


def _business_days(start: date, end: date, *, limit: int | None = None) -> list[date]:
    result: list[date] = []
    current = start
    while current <= end and (limit is None or len(result) < limit):
        if current.weekday() < 5:
            result.append(current)
        current += timedelta(days=1)
    return result


def _payload(symbol: str) -> dict[str, object]:
    instrument = next(item for item in REGISTRY if item.yahoo_symbol == symbol)
    start = instrument.listed_on or date(2023, 3, 1)
    limit = (
        110
        if instrument.symbol == "0173Y0"
        else 82
        if instrument.symbol == "0190C0"
        else None
    )
    dates = _business_days(start, REQUESTED_END, limit=limit)
    dates.append(date(2026, 9, 9))
    timestamps = [
        int(
            datetime.combine(
                day,
                datetime.min.time().replace(hour=9, minute=30),
                ZoneInfo(instrument.timezone),
            ).timestamp()
        )
        for day in dates
    ]
    quote: dict[str, list[object]] = {
        "open": [],
        "high": [],
        "low": [],
        "close": [],
        "volume": [],
    }
    for index, day in enumerate(dates):
        if day == date(2026, 9, 9):
            for values in quote.values():
                values.append(None)
            continue
        price = 100 + index / 10
        quote["open"].append(price)
        quote["high"].append(price + 1)
        quote["low"].append(price - 1)
        quote["close"].append(price + 0.5)
        quote["volume"].append(1_000_000 + index)
    splits: dict[str, object] = {}
    split = (
        (date(2024, 6, 10), 10, 1)
        if instrument.symbol == "NVDA"
        else (date(2025, 11, 20), 2, 1)
        if instrument.symbol == "TQQQ"
        else None
    )
    if split is not None:
        split_date, numerator, denominator = split
        timestamp = int(
            datetime.combine(
                split_date,
                datetime.min.time().replace(hour=9, minute=30),
                ZoneInfo(instrument.timezone),
            ).timestamp()
        )
        splits[str(timestamp)] = {
            "date": timestamp,
            "numerator": numerator,
            "denominator": denominator,
            "splitRatio": f"{numerator}:{denominator}",
        }
    events: dict[str, object] = {"dividends": {}}
    if splits:
        events["splits"] = splits
    return {
        "chart": {
            "error": None,
            "result": [
                {
                    "meta": {
                        "symbol": instrument.yahoo_symbol,
                        "currency": instrument.currency,
                        "exchangeName": instrument.exchange,
                        "exchangeTimezoneName": instrument.timezone,
                    },
                    "timestamp": timestamps,
                    "events": events,
                    "indicators": {"quote": [quote]},
                }
            ],
        }
    }


def _kis_rows(symbol: str) -> list[dict[str, object]]:
    instrument = next(item for item in REGISTRY if item.symbol == symbol)
    start = instrument.listed_on or date(2023, 3, 2)
    limit = 110 if symbol == "0173Y0" else 82 if symbol == "0190C0" else None
    return [
        {
            "stck_bsop_date": day.strftime("%Y%m%d"),
            "stck_oprc": str(10_000 + index * 10),
            "stck_hgpr": str(10_100 + index * 10),
            "stck_lwpr": str(9_900 + index * 10),
            "stck_clpr": str(10_050 + index * 10),
            "acml_vol": 1_000_000 + index,
        }
        for index, day in enumerate(_business_days(start, REQUESTED_END, limit=limit))
    ]


def _collected(symbol: str) -> CollectedUniverseSnapshot:
    instrument = next(item for item in REGISTRY if item.symbol == symbol)
    return normalize_chart(
        instrument,
        _payload(instrument.yahoo_symbol),
        captured_at=CAPTURED_AT,
        requested_start=REQUESTED_START,
        requested_end=REQUESTED_END,
        kis_raw_rows=_kis_rows(symbol) if instrument.currency == "KRW" else None,
    )


def test_registry_uses_native_symbols_and_keeps_paper_validation_domestic() -> None:
    assert len(REGISTRY) == 16
    assert len({item.symbol for item in REGISTRY}) == 16
    assert [(item.symbol, item.currency, item.exchange) for item in REGISTRY] == [
        ("005930", "KRW", "KSC"),
        ("000660", "KRW", "KSC"),
        ("487230", "KRW", "KSC"),
        ("487240", "KRW", "KSC"),
        ("0173Y0", "KRW", "KSC"),
        ("0190C0", "KRW", "KSC"),
        ("SOXL", "USD", "PCX"),
        ("NVDA", "USD", "NMS"),
        ("GOOGL", "USD", "NMS"),
        ("COHR", "USD", "NYQ"),
        ("TQQQ", "USD", "NGM"),
        ("MSFT", "USD", "NMS"),
        ("ARM", "USD", "NMS"),
        ("AMD", "USD", "NMS"),
        ("GEV", "USD", "NYQ"),
        ("VRT", "USD", "NYQ"),
    ]
    assert next(item for item in REGISTRY if item.symbol == "0190C0").name == (
        "RISE 현대차고정피지컬AI"
    )
    with pytest.raises(ValidationError):
        ResearchRunRequest(
            symbols=["NVDA"], start_date=REQUESTED_START, end_date=REQUESTED_END
        )


def test_normalization_filters_local_current_bar_and_listing_boundaries() -> None:
    samsung = _collected("005930")
    arm = _collected("ARM")
    gev = _collected("GEV")

    assert samsung.snapshot.instruments[0].bars[-1].date == REQUESTED_END
    assert arm.snapshot.instruments[0].bars[0].date == date(2023, 9, 14)
    assert arm.request.start_date == arm.snapshot.instruments[0].bars[60].date
    assert gev.snapshot.instruments[0].bars[0].date == date(2024, 4, 2)
    assert gev.request.start_date == gev.snapshot.instruments[0].bars[60].date


@pytest.mark.parametrize(
    ("symbol", "evaluation_bars"), [("0173Y0", 50), ("0190C0", 22)]
)
def test_short_etfs_remain_explicitly_insufficient(
    symbol: str, evaluation_bars: int
) -> None:
    collected = _collected(symbol)
    assert (
        sum(
            collected.request.start_date <= bar.date <= collected.request.end_date
            for bar in collected.snapshot.instruments[0].bars
        )
        == evaluation_bars
    )
    with pytest.raises(DataInsufficientError, match="240"):
        walk_forward_folds(
            SourceSnapshot(
                run_id=f"universe:{symbol}",
                request=collected.request,
                snapshot=collected.snapshot,
            )
        )


@pytest.mark.parametrize(
    ("symbol", "action_date", "factor"),
    [
        ("NVDA", date(2024, 6, 10), Decimal(10)),
        ("TQQQ", date(2025, 11, 20), Decimal(2)),
    ],
)
def test_split_adjusted_quote_is_reconstructed_to_raw_prices(
    symbol: str, action_date: date, factor: Decimal
) -> None:
    collected = _collected(symbol)
    item = collected.snapshot.instruments[0]
    before = max(
        (bar for bar in item.bars if bar.date < action_date),
        key=lambda bar: bar.date,
    )
    action_bar = next(bar for bar in item.bars if bar.date == action_date)

    assert before.open == before.adjusted_open * factor
    assert action_bar.open == action_bar.adjusted_open
    assert collected.snapshot.corporate_actions[0].factor == factor


def test_engine_applies_split_before_open_and_returns_external_metadata() -> None:
    collected = _collected("NVDA")
    request = collected.request.model_copy(
        update={
            "start_date": date(2024, 6, 7),
            "end_date": date(2024, 6, 11),
            "fee_rate": Decimal(),
            "slippage_rate": Decimal(),
        }
    )

    result = run_signal_backtest(
        request,
        collected.snapshot,
        strategy_version="split-test",
        definition="always hold",
        signal=lambda _symbol, _bars: True,
    )

    assert isinstance(result, ExternalStrategyResult)
    effect = result.corporate_action_effects[0]
    assert effect.date == date(2024, 6, 10)
    assert effect.factor == Decimal(10)
    assert effect.quantity_after == effect.quantity_before * 10
    assert effect.cash_in_lieu == 0
    assert result.currency == "USD"
    assert result.dividend_policy == "excluded_price_return"


def _synthetic_external_snapshot() -> tuple[
    OfflineResearchRequest, OfflineResearchSnapshot
]:
    instrument = ResearchInstrument(
        symbol="TEST",
        yahoo_symbol="TEST",
        name="Synthetic",
        currency="USD",
        exchange="NMS",
        timezone="America/New_York",
    )
    first = date(2025, 1, 1)
    split_date = first + timedelta(days=61)
    bars = []
    factors = []
    for index in range(63):
        day = first + timedelta(days=index)
        factor = Decimal("0.5") if day < split_date else Decimal(1)
        adjusted = Decimal(20 + index) / Decimal(2)
        raw = adjusted * factor
        bars.append(
            DailyBar(
                date=day,
                open=raw,
                high=raw,
                low=raw,
                close=raw,
                volume=1000,
                adjusted_open=adjusted,
                adjusted_high=adjusted,
                adjusted_low=adjusted,
                adjusted_close=adjusted,
            )
        )
        factors.append(PriceAdjustmentFactor(date=day, raw_factor=factor))
    request = OfflineResearchRequest(
        instrument=instrument,
        start_date=first + timedelta(days=60),
        end_date=first + timedelta(days=62),
        initial_cash=Decimal(190),
        fee_rate=Decimal(),
        slippage_rate=Decimal(),
    )
    snapshot = OfflineResearchSnapshot(
        captured_at=datetime(2026, 1, 1, tzinfo=UTC),
        requested_start=request.start_date,
        requested_end=request.end_date,
        evaluation_start=request.start_date,
        instruments=[
            OfflineInstrumentSnapshot(
                instrument=instrument,
                bars=bars,
                provenance={
                    "price_volume_source": "Yahoo chart",
                    "corporate_action_source": "Yahoo chart",
                },
                source_url="https://query1.finance.yahoo.com/v8/finance/chart/TEST",
            )
        ],
        basis_actions=[
            CorporateAction(
                date=split_date, numerator=Decimal(1), denominator=Decimal(2)
            )
        ],
        corporate_actions=[
            CorporateAction(
                date=split_date, numerator=Decimal(1), denominator=Decimal(2)
            )
        ],
        adjustment_factors=factors,
    )
    return request, snapshot


def test_reverse_split_fraction_is_settled_at_action_open() -> None:
    request, snapshot = _synthetic_external_snapshot()
    result = run_signal_backtest(
        request,
        snapshot,
        strategy_version="reverse-split",
        definition="always hold",
        signal=lambda _symbol, _bars: True,
    )

    effect = result.corporate_action_effects[0]
    assert effect.quantity_before > 0
    assert effect.fractional_quantity in {Decimal(), Decimal("0.5")}
    assert effect.cash_in_lieu == effect.fractional_quantity * next(
        bar.open for bar in snapshot.instruments[0].bars if bar.date == effect.date
    )


def test_external_training_labels_use_split_adjusted_opens() -> None:
    request, snapshot = _synthetic_external_snapshot()
    _features, labels = training_examples(snapshot, request)
    assert labels == [1.0]


def test_snapshot_rejects_action_without_daily_bar() -> None:
    _request, snapshot = _synthetic_external_snapshot()
    with pytest.raises(ValidationError, match="action"):
        OfflineResearchSnapshot.model_validate(
            {
                **snapshot.model_dump(),
                "corporate_actions": [
                    CorporateAction(
                        date=date(2030, 1, 1),
                        numerator=Decimal(2),
                        denominator=Decimal(1),
                    )
                ],
            }
        )


def test_split_after_requested_end_is_kept_for_price_basis_only() -> None:
    instrument = next(item for item in REGISTRY if item.symbol == "NVDA")
    payload = _payload("NVDA")
    result = payload["chart"]["result"][0]
    timestamp = int(
        datetime(2026, 9, 9, 9, 30, tzinfo=ZoneInfo(instrument.timezone)).timestamp()
    )
    result["events"]["splits"][str(timestamp)] = {
        "date": timestamp,
        "numerator": 2,
        "denominator": 1,
        "splitRatio": "2:1",
    }

    collected = normalize_chart(
        instrument,
        payload,
        captured_at=CAPTURED_AT,
        requested_start=REQUESTED_START,
        requested_end=REQUESTED_END,
    )

    assert [action.date for action in collected.snapshot.basis_actions][-1] == date(
        2026, 9, 9
    )
    assert all(
        action.date <= REQUESTED_END for action in collected.snapshot.corporate_actions
    )
    assert collected.snapshot.adjustment_factors[-1].raw_factor == Decimal(2)
    folds, _tail = walk_forward_folds(
        SourceSnapshot(
            run_id="post-period-split",
            request=collected.request,
            snapshot=collected.snapshot,
        )
    )
    assert folds


def test_missing_split_date_bar_is_rejected_before_backtest() -> None:
    instrument = next(item for item in REGISTRY if item.symbol == "NVDA")
    payload = _payload("NVDA")
    result = payload["chart"]["result"][0]
    timestamps = result["timestamp"]
    split_index = next(
        index
        for index, timestamp in enumerate(timestamps)
        if datetime.fromtimestamp(timestamp, ZoneInfo(instrument.timezone)).date()
        == date(2024, 6, 10)
    )
    timestamps.pop(split_index)
    quote = result["indicators"]["quote"][0]
    for values in quote.values():
        values.pop(split_index)

    with pytest.raises(DataInsufficientError, match="기업행동일"):
        normalize_chart(
            instrument,
            payload,
            captured_at=CAPTURED_AT,
            requested_start=REQUESTED_START,
            requested_end=REQUESTED_END,
        )


def test_model_requires_execution_action_inside_bar_range() -> None:
    _request, snapshot = _synthetic_external_snapshot()

    with pytest.raises(ValidationError, match="must be executed"):
        OfflineResearchSnapshot.model_validate(
            {**snapshot.model_dump(), "corporate_actions": []}
        )


def test_input_store_deduplicates_and_retains_stale_success(tmp_path: Path) -> None:
    collected = _collected("NVDA")
    store = UniverseInputStore(tmp_path / "input.db")

    assert store.save_success(collected)
    assert not store.save_success(collected)
    store.record_failure("NVDA", "temporary failure")

    status = store.statuses()["NVDA"]
    assert status["status"] == "stale"
    assert status["snapshot_id"] == collected.content_hash
    assert status["error"] == "temporary failure"
    assert store.load_latest("NVDA") is not None


def test_partial_collection_failure_does_not_abort_other_instruments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selected = (REGISTRY[6], REGISTRY[7])
    monkeypatch.setattr(universe_module, "REGISTRY", selected)

    def load(path: Path) -> dict[str, object]:
        if path.name == "NVDA.json":
            raise DataCollectionError("NVDA fixture failure")
        return _payload(path.stem)

    monkeypatch.setattr(universe_module, "_load_json", load)
    store = UniverseInputStore(tmp_path / "input.db")

    rows = asyncio.run(
        collect_all(
            store,
            should_stop=lambda: False,
            fixtures_dir=Path("unused-fixtures"),
            captured_at=CAPTURED_AT,
        )
    )

    assert [row.request.instrument.symbol for row in rows] == ["SOXL"]
    assert store.statuses()["NVDA"]["status"] == "error"


def test_kis_auth_failure_retries_per_instrument_and_us_continues(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selected = (REGISTRY[0], REGISTRY[1], REGISTRY[6])
    monkeypatch.setattr(universe_module, "REGISTRY", selected)

    async def yahoo(
        _client: object,
        instrument: ResearchInstrument,
        _start: date,
        _end: date,
    ) -> dict[str, object]:
        return _payload(instrument.yahoo_symbol)

    attempts = 0

    class FailedKisProvider:
        def __init__(self, _settings: object, _client: object) -> None:
            pass

        async def _authenticate(self) -> str:
            nonlocal attempts
            attempts += 1
            raise DataCollectionError("KIS auth unavailable")

    monkeypatch.setattr(universe_module, "fetch_yahoo_chart", yahoo)
    monkeypatch.setattr(
        universe_module,
        "load_research_settings",
        lambda: type("Settings", (), {"base_url": "https://example.com"})(),
    )
    monkeypatch.setattr(universe_module, "KisPaperHistoricalData", FailedKisProvider)
    store = UniverseInputStore(tmp_path / "input.db")

    rows = asyncio.run(
        collect_all(store, should_stop=lambda: False, captured_at=CAPTURED_AT)
    )

    assert attempts == 2
    assert [row.request.instrument.symbol for row in rows] == ["SOXL"]
    assert store.statuses()["005930"]["status"] == "error"
    assert store.statuses()["000660"]["status"] == "error"


def test_status_does_not_mix_new_snapshot_with_old_optimizer_result(
    tmp_path: Path,
) -> None:
    input_store = UniverseInputStore(tmp_path / "input.db")
    previous = _collected("NVDA")
    input_store.save_success(previous)
    optimizer_path = tmp_path / "optimizer.db"
    from jusik.research_optimizer_store import OptimizerStore

    OptimizerStore(optimizer_path)
    result_store = UniverseResultStore(optimizer_path)
    result_store.update(
        "NVDA",
        previous.content_hash,
        batch_id="old-batch",
        status="completed",
    )
    input_store.save_success(replace(previous, content_hash="new-snapshot"))

    status = universe_status(input_store, result_store)
    nvda = next(item for item in status["instruments"] if item["symbol"] == "NVDA")
    assert nvda["optimizer_status"] == "pending_refresh"
    assert nvda["batch_id"] is None
    assert nvda["folds"] == 0
    assert nvda["previous_result"] == {
        "snapshot_id": previous.content_hash,
        "batch_id": "old-batch",
        "status": "completed",
    }


def test_failed_refresh_resumes_saved_unfinished_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selected = REGISTRY[7]
    monkeypatch.setattr(universe_module, "REGISTRY", (selected,))
    input_store = UniverseInputStore(tmp_path / "input.db")
    collected = _collected("NVDA")
    input_store.save_success(collected)
    input_store.record_failure("NVDA", "network unavailable")
    optimizer_path = tmp_path / "optimizer.db"
    from jusik.research_optimizer_store import OptimizerStore

    optimizer_store = OptimizerStore(optimizer_path)
    result_store = UniverseResultStore(optimizer_path)
    result_store.update(
        "NVDA",
        collected.content_hash,
        batch_id="old-batch",
        status="stopped",
    )

    async def failed_collection(*_args: object, **_kwargs: object) -> list[object]:
        return []

    seen: list[str] = []

    def optimize(source: SourceSnapshot, *_args: object, **_kwargs: object) -> bool:
        seen.append(source.run_id)
        return False

    monkeypatch.setattr(universe_module, "collect_all", failed_collection)
    monkeypatch.setattr(
        universe_module,
        "walk_forward_identity",
        lambda *_args: ("new-batch", "content"),
    )
    monkeypatch.setattr(universe_module, "optimize_walk_forward_snapshot", optimize)

    asyncio.run(
        universe_module._run_cycle(
            input_store,
            optimizer_store,
            result_store,
            tmp_path / "artifacts",
            tmp_path / "reports",
            "cpu",
            lambda: False,
            None,
        )
    )

    assert seen == [f"universe:NVDA:{collected.content_hash}"]


def test_failed_refresh_evaluates_new_snapshot_after_old_completed_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selected = REGISTRY[7]
    monkeypatch.setattr(universe_module, "REGISTRY", (selected,))
    input_store = UniverseInputStore(tmp_path / "input.db")
    previous = _collected("NVDA")
    input_store.save_success(previous)
    current = replace(previous, content_hash="new-snapshot")
    input_store.save_success(current)
    input_store.record_failure("NVDA", "refresh failed")
    optimizer_path = tmp_path / "optimizer.db"
    from jusik.research_optimizer_store import OptimizerStore

    optimizer_store = OptimizerStore(optimizer_path)
    result_store = UniverseResultStore(optimizer_path)
    result_store.update(
        "NVDA",
        previous.content_hash,
        batch_id="completed-old-batch",
        status="completed",
    )

    async def failed_collection(*_args: object, **_kwargs: object) -> list[object]:
        return []

    seen: list[str] = []

    def optimize(source: SourceSnapshot, *_args: object, **_kwargs: object) -> bool:
        seen.append(source.run_id)
        return False

    monkeypatch.setattr(universe_module, "collect_all", failed_collection)
    monkeypatch.setattr(
        universe_module, "walk_forward_identity", lambda *_args: ("batch", "content")
    )
    monkeypatch.setattr(universe_module, "optimize_walk_forward_snapshot", optimize)

    asyncio.run(
        universe_module._run_cycle(
            input_store,
            optimizer_store,
            result_store,
            tmp_path / "artifacts",
            tmp_path / "reports",
            "cpu",
            lambda: False,
            None,
        )
    )

    assert seen == ["universe:NVDA:new-snapshot"]


def test_interrupted_optimization_records_stopped_mapping_and_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selected = REGISTRY[7]
    monkeypatch.setattr(universe_module, "REGISTRY", (selected,))
    collected = _collected("NVDA")
    input_store = UniverseInputStore(tmp_path / "input.db")
    optimizer_path = tmp_path / "optimizer.db"
    from jusik.research_optimizer_store import OptimizerStore

    optimizer_store = OptimizerStore(optimizer_path)
    result_store = UniverseResultStore(optimizer_path)

    async def collection(*_args: object, **_kwargs: object) -> list[object]:
        input_store.save_success(collected)
        return [collected]

    def interrupted(
        _source: SourceSnapshot,
        store: OptimizerStore,
        *_args: object,
        **_kwargs: object,
    ) -> bool:
        assert store.begin_batch(
            "batch",
            "source",
            "content",
            validation_mode="walk-forward",
            risk=ResearchRiskPolicy().as_json(),
            fold_count=1,
            tail={"count": 0},
        )
        store.fail_batch("batch", "stopped", stopped=True)
        raise StopRequested

    monkeypatch.setattr(universe_module, "collect_all", collection)
    monkeypatch.setattr(
        universe_module, "walk_forward_identity", lambda *_args: ("batch", "content")
    )
    monkeypatch.setattr(universe_module, "optimize_walk_forward_snapshot", interrupted)

    with pytest.raises(StopRequested):
        asyncio.run(
            universe_module._run_cycle(
                input_store,
                optimizer_store,
                result_store,
                tmp_path / "artifacts",
                tmp_path / "reports",
                "cpu",
                lambda: False,
                None,
            )
        )

    assert result_store.statuses()["NVDA"]["status"] == "stopped"
    assert (tmp_path / "reports" / "NVDA.md").is_file()


def test_status_and_reports_include_all_instruments_without_currency_aggregation(
    tmp_path: Path,
) -> None:
    input_store = UniverseInputStore(tmp_path / "input.db")
    input_store.save_success(_collected("NVDA"))
    optimizer_path = tmp_path / "optimizer.db"
    from jusik.research_optimizer_store import OptimizerStore

    OptimizerStore(optimizer_path)
    result_store = UniverseResultStore(optimizer_path)

    status = universe_status(input_store, result_store)
    assert len(status["instruments"]) == 16
    assert status["currency_aggregation"] == "disabled"
    assert status["automatic_trading_eligible"] is False
    assert status["evidence_class"] == "reconstructed_historical_exploration"
    assert status["point_in_time_verified"] is False
    assert status["prospective_validation_eligible"] is False
    assert all(
        item["prospective_validation_eligible"] is False
        for item in status["instruments"]
    )

    write_reports(tmp_path / "reports", status)
    assert (tmp_path / "reports" / "NVDA.csv").is_file()
    assert "자동매매" in (tmp_path / "reports" / "NVDA.md").read_text()
    csv_report = (tmp_path / "reports" / "NVDA.csv").read_text()
    assert "reconstructed_historical_exploration" in csv_report
    assert "prospective_validation_eligible" in csv_report
    universe_report = (tmp_path / "reports" / "universe.md").read_text()
    external_report = (tmp_path / "reports" / "external.md").read_text()
    for report in (universe_report, external_report):
        assert "reconstructed_historical_exploration" in report
        assert "point_in_time_verified=false" in report
        assert "prospective_validation_eligible=false" in report
        assert "자동매매 승격" in report
    assert (
        "KRW와 USD 성과를 합산하지 않습니다"
        in (tmp_path / "reports" / "universe.md").read_text()
    )


@pytest.mark.parametrize(
    ("prior_status", "uses_latest"), [("completed", True), ("stopped", False)]
)
def test_external_change_reuses_stock_snapshot_and_stopped_run_keeps_binding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    prior_status: str,
    uses_latest: bool,
) -> None:
    selected = REGISTRY[7]
    monkeypatch.setattr(universe_module, "REGISTRY", (selected,))
    input_store = UniverseInputStore(tmp_path / "input.db")
    collected = _collected("NVDA")
    input_store.save_success(collected)
    optimizer_path = tmp_path / "optimizer.db"
    from jusik.research_optimizer_store import OptimizerStore

    optimizer_store = OptimizerStore(optimizer_path)
    result_store = UniverseResultStore(optimizer_path)
    external_store = ExternalStore(tmp_path / "external.db")
    captured = datetime(2026, 1, 10, tzinfo=UTC)
    external_store.save_success(
        "vix",
        body=b"old",
        content_type="text/csv",
        observations=[
            ExternalObservation(
                series="vix",
                observed_on=date(2026, 1, 8),
                value="20",
                available_at=datetime(2026, 1, 9, tzinfo=UTC),
                revision="old",
            )
        ],
        captured_at=captured,
    )
    old_external = external_store.bind_snapshot("old-batch", external_store.snapshot())
    result_store.update(
        "NVDA",
        collected.content_hash,
        batch_id="old-batch",
        status=prior_status,
    )
    external_store.save_success(
        "vix",
        body=b"new",
        content_type="text/csv",
        observations=[
            ExternalObservation(
                series="vix",
                observed_on=date(2026, 1, 8),
                value="21",
                available_at=datetime(2026, 1, 9, tzinfo=UTC),
                revision="new",
            )
        ],
        captured_at=captured + timedelta(hours=1),
    )

    async def no_collection(*_args: object, **_kwargs: object) -> list[object]:
        return []

    seen: list[ExternalFeatureSnapshot] = []

    def optimize(source: SourceSnapshot, *_args: object, **_kwargs: object) -> bool:
        assert source.external is not None
        seen.append(source.external)
        return False

    monkeypatch.setattr(universe_module, "collect_external_sources", no_collection)
    monkeypatch.setattr(universe_module, "collect_all", no_collection)
    monkeypatch.setattr(
        universe_module, "walk_forward_identity", lambda *_args: ("new-batch", "hash")
    )
    monkeypatch.setattr(universe_module, "optimize_walk_forward_snapshot", optimize)

    asyncio.run(
        universe_module._run_cycle(
            input_store,
            optimizer_store,
            result_store,
            tmp_path / "artifacts",
            tmp_path / "reports",
            "cpu",
            lambda: False,
            None,
            external_store,
            refresh_stocks=False,
        )
    )

    assert len(seen) == 1
    assert (seen[0].semantic_hash() != old_external.semantic_hash()) is uses_latest
    assert external_store.load_bound_snapshot("new-batch") == seen[0]
