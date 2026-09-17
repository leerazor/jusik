from __future__ import annotations

import json
import shutil
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from jusik import research_portfolio_engine as engine
from jusik import research_portfolio_time_evidence as evidence
from jusik.research_external_models import ExternalFeatureSnapshot
from jusik.research_market_calendar import (
    DEFAULT_CALENDAR_PATH,
    MarketSession,
    _Day,
    load_market_calendar,
)
from jusik.research_models import DailyBar
from jusik.research_portfolio_models import (
    PortfolioCandidate,
    PortfolioConfig,
    PortfolioInput,
    PortfolioPolicy,
    PortfolioSimulation,
)
from jusik.research_portfolio_time_evidence import (
    generate_bundle,
    verify_bundle,
)
from jusik.research_portfolio_time_models import InitialCapitalEvent
from jusik.research_universe_models import (
    DataProvenance,
    OfflineInstrumentSnapshot,
    OfflineResearchSnapshot,
    PriceAdjustmentFactor,
    ResearchInstrument,
)


def _source() -> PortfolioInput:
    calendar = load_market_calendar()
    days: list[date] = []
    current = date(2024, 1, 2)
    while len(days) < 8:
        session = calendar.lookup("KSC", current).session
        if (
            session is not None
            and session.open_at.astimezone(ZoneInfo("Asia/Seoul")).hour == 9
        ):
            days.append(current)
        current += timedelta(days=1)
    instrument = ResearchInstrument(
        symbol="SYNTH",
        yahoo_symbol="SYNTH",
        name="Synthetic",
        currency="KRW",
        exchange="KSC",
        timezone="Asia/Seoul",
    )
    bars = [
        DailyBar(
            date=day,
            open=Decimal(100 + index),
            high=Decimal(101 + index),
            low=Decimal(99 + index),
            close=Decimal(100 + index),
            volume=1000,
            adjusted_open=Decimal(100 + index),
            adjusted_high=Decimal(101 + index),
            adjusted_low=Decimal(99 + index),
            adjusted_close=Decimal(100 + index),
        )
        for index, day in enumerate(days)
    ]
    snapshot = OfflineResearchSnapshot(
        captured_at=datetime(2024, 2, 1, tzinfo=UTC),
        requested_start=days[0],
        requested_end=days[-1],
        evaluation_start=days[0],
        instruments=[
            OfflineInstrumentSnapshot(
                instrument=instrument,
                bars=bars,
                provenance=DataProvenance(price_volume_source="Yahoo chart"),
                source_url="https://example.invalid/synthetic",
            )
        ],
        adjustment_factors=[
            PriceAdjustmentFactor(date=day, raw_factor=Decimal(1)) for day in days
        ],
    )
    return PortfolioInput(
        captured_at=datetime(2024, 2, 1, tzinfo=UTC),
        stock_snapshot_ids={"SYNTH": "synthetic"},
        instruments=[snapshot],
        external=ExternalFeatureSnapshot(observations=[]),
    )


def _config() -> tuple[PortfolioCandidate, PortfolioConfig, date, date]:
    source = _source()
    return (
        PortfolioCandidate(id="synthetic", method="equal", gate="none"),
        PortfolioConfig(initial_cash_krw=Decimal("1000000")),
        source.instruments[0].requested_start,
        source.instruments[0].requested_end,
    )


def _single_bar_source(day: date) -> PortfolioInput:
    source = _source()
    snapshot = source.instruments[0]
    item = snapshot.instruments[0]
    bar = next(value for value in item.bars if value.date == day)
    filtered_item = item.model_copy(update={"bars": [bar]})
    filtered_snapshot = snapshot.model_copy(
        update={
            "requested_start": day,
            "requested_end": day,
            "evaluation_start": day,
            "instruments": [filtered_item],
            "adjustment_factors": [
                value for value in snapshot.adjustment_factors if value.date == day
            ],
        }
    )
    return source.model_copy(
        update={
            "stock_snapshot_ids": {"KRTEST": "synthetic"},
            "instruments": [filtered_snapshot],
        }
    )


def _causal_pair_source() -> PortfolioInput:
    source = _source()
    calendar = load_market_calendar()
    snapshots = []
    for snapshot in source.instruments:
        item = snapshot.instruments[0]
        bars = [
            bar
            for bar in item.bars
            if (
                (session := calendar.lookup(item.instrument.exchange, bar.date).session)
                is not None
                and engine._market_time(
                    bar.date, item.instrument.timezone, opening=True
                )
                >= session.open_at
                and engine._market_time(
                    bar.date, item.instrument.timezone, opening=False
                )
                >= session.close_at
            )
        ]
        days = {bar.date for bar in bars}
        item = item.model_copy(update={"bars": bars})
        snapshots.append(
            snapshot.model_copy(
                update={
                    "instruments": [item],
                    "adjustment_factors": [
                        value
                        for value in snapshot.adjustment_factors
                        if value.date in days
                    ],
                }
            )
        )
    us = snapshots[0].model_copy(deep=True)
    us_item = us.instruments[0]
    us_instrument = ResearchInstrument(
        symbol="USYNTH",
        yahoo_symbol="USYNTH",
        name="US synthetic",
        currency="USD",
        exchange="NMS",
        timezone="America/New_York",
    )
    us_days = [
        bar.date
        for bar in us_item.bars
        if calendar.lookup("NMS", bar.date).session is not None
    ]
    us_bars = [bar for bar in us_item.bars if bar.date in us_days]
    us = us.model_copy(
        update={
            "instruments": [
                us_item.model_copy(
                    update={"instrument": us_instrument, "bars": us_bars}
                )
            ],
            "adjustment_factors": [
                value for value in us.adjustment_factors if value.date in set(us_days)
            ],
        }
    )
    snapshots.append(us)
    return source.model_copy(
        update={
            "stock_snapshot_ids": {"SYNTH": "synthetic", "USYNTH": "synthetic"},
            "instruments": snapshots,
        }
    )


def _xnys_time_source() -> PortfolioInput:
    source = _source()
    snapshot = source.instruments[0]
    original_item = snapshot.instruments[0]
    dates = [date(2024, 3, 8), date(2024, 3, 11), date(2024, 11, 29)]
    bars = [
        original_item.bars[index].model_copy(update={"date": day})
        for index, day in enumerate(dates)
    ]
    instrument = ResearchInstrument(
        symbol="USYNTH",
        yahoo_symbol="USYNTH",
        name="US time synthetic",
        currency="USD",
        exchange="NMS",
        timezone="America/New_York",
    )
    item = original_item.model_copy(update={"instrument": instrument, "bars": bars})
    filtered = snapshot.model_copy(
        update={
            "requested_start": dates[0],
            "requested_end": dates[-1],
            "evaluation_start": dates[0],
            "instruments": [item],
            "adjustment_factors": [
                PriceAdjustmentFactor(date=day, raw_factor=Decimal(1)) for day in dates
            ],
        }
    )
    return source.model_copy(
        update={
            "stock_snapshot_ids": {"USYNTH": "synthetic"},
            "instruments": [filtered],
        }
    )


def test_initial_capital_is_an_engine_anchor_not_a_market_open() -> None:
    event = InitialCapitalEvent(
        initial_capital_krw=Decimal("100"),
        timestamp=datetime(2024, 1, 2, tzinfo=UTC),
        first_engine_event_at=datetime(2024, 1, 2, tzinfo=UTC),
        first_engine_event_kind="rebalance",
    )
    assert event.timestamp_kind == "engine_event_anchor"
    assert event.logical_order == "before_first_event"
    assert event.amount_krw == Decimal("100")
    with pytest.raises(ValueError, match="must equal first engine event"):
        InitialCapitalEvent(
            initial_capital_krw=Decimal("100"),
            timestamp=datetime(2024, 1, 2, tzinfo=UTC),
            first_engine_event_at=datetime(2024, 1, 3, tzinfo=UTC),
            first_engine_event_kind="rebalance",
        )


def test_generation_matches_direct_simulation_and_verify_does_not_simulate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _source()
    candidate, config, start, end = _config()
    output = tmp_path / "bundle"
    original_simulate = engine.simulate
    calls = 0

    def counted_simulate(
        source_value: PortfolioInput,
        candidate_value: PortfolioCandidate,
        start_value: date,
        end_value: date,
        config_value: PortfolioConfig,
        policy_value: PortfolioPolicy = "corrected_control",
    ) -> PortfolioSimulation:
        nonlocal calls
        calls += 1
        return original_simulate(
            source_value,
            candidate_value,
            start_value,
            end_value,
            config_value,
            policy_value,
        )

    monkeypatch.setattr(engine, "simulate", counted_simulate)
    result = generate_bundle(
        source,
        candidate,
        start,
        end,
        config,
        DEFAULT_CALENDAR_PATH.read_bytes(),
        output,
        allow_new_simulation=True,
    )
    assert calls == 1
    payload = json.loads((output / "simulation.json").read_text())
    direct = original_simulate(source, candidate, start, end, config)
    assert payload == direct.model_dump(mode="json")
    assert json.loads((output / "time-evidence.json").read_text())["nav"]

    def fail(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("verify must not execute simulation")

    monkeypatch.setattr(engine, "simulate", fail)
    assert verify_bundle(output, result.manifest_sha256).nav_count > 0


def test_generation_requires_opt_in_and_bundle_is_no_overwrite(tmp_path: Path) -> None:
    source = _source()
    candidate, config, start, end = _config()
    with pytest.raises(ValueError, match="allow_new_simulation"):
        generate_bundle(
            source,
            candidate,
            start,
            end,
            config,
            DEFAULT_CALENDAR_PATH.read_bytes(),
            tmp_path / "bundle",
        )
    output = tmp_path / "bundle"
    generate_bundle(
        source,
        candidate,
        start,
        end,
        config,
        DEFAULT_CALENDAR_PATH.read_bytes(),
        output,
        allow_new_simulation=True,
    )
    with pytest.raises(ValueError, match="new"):
        generate_bundle(
            source,
            candidate,
            start,
            end,
            config,
            DEFAULT_CALENDAR_PATH.read_bytes(),
            output,
            allow_new_simulation=True,
        )


def test_manifest_sha_and_artifact_tamper_are_fail_closed(tmp_path: Path) -> None:
    source = _source()
    candidate, config, start, end = _config()
    output = tmp_path / "bundle"
    result = generate_bundle(
        source,
        candidate,
        start,
        end,
        config,
        DEFAULT_CALENDAR_PATH.read_bytes(),
        output,
        allow_new_simulation=True,
    )
    (output / "simulation.json").write_text(
        (output / "simulation.json").read_text() + "\n"
    )
    with pytest.raises(ValueError, match="hash or size"):
        verify_bundle(output, result.manifest_sha256)


def test_strict_json_keeps_long_decimal_exact() -> None:
    raw = evidence._strict_json(
        b'{"value":1234567890.123456789012345678901234567890}', "test"
    )
    assert raw == {"value": Decimal("1234567890.123456789012345678901234567890")}


def test_verify_uses_verified_bytes_after_path_swap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _source()
    candidate, config, start, end = _config()
    output = tmp_path / "bundle"
    result = generate_bundle(
        source,
        candidate,
        start,
        end,
        config,
        DEFAULT_CALENDAR_PATH.read_bytes(),
        output,
        allow_new_simulation=True,
    )
    original = evidence._load_bundle_files

    def swap_after_loading(
        bundle_dir: Path, expected_manifest_sha256: str
    ) -> tuple[dict[str, bytes], dict[str, object], str]:
        loaded = original(bundle_dir, expected_manifest_sha256)
        (output / "simulation.json").write_text("not the verified simulation")
        return loaded

    monkeypatch.setattr(evidence, "_load_bundle_files", swap_after_loading)
    assert verify_bundle(output, result.manifest_sha256).nav_count > 0


def test_failed_generation_cleans_staging_and_never_leaves_partial_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _source()
    candidate, config, start, end = _config()
    output = tmp_path / "bundle"
    original = evidence._write_bytes_exclusive
    calls = 0

    def fail_after_first(path: Path, body: bytes) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("controlled write failure")
        original(path, body)

    monkeypatch.setattr(evidence, "_write_bytes_exclusive", fail_after_first)
    with pytest.raises(OSError, match="controlled"):
        generate_bundle(
            source,
            candidate,
            start,
            end,
            config,
            DEFAULT_CALENDAR_PATH.read_bytes(),
            output,
            allow_new_simulation=True,
        )
    assert not output.exists()
    assert not list(tmp_path.glob(".bundle.staging-*"))


def test_verify_rejects_extra_directory_entry(tmp_path: Path) -> None:
    source = _source()
    candidate, config, start, end = _config()
    output = tmp_path / "bundle"
    result = generate_bundle(
        source,
        candidate,
        start,
        end,
        config,
        DEFAULT_CALENDAR_PATH.read_bytes(),
        output,
        allow_new_simulation=True,
    )
    (output / "unexpected").mkdir()
    with pytest.raises(ValueError, match="unexpected or missing"):
        verify_bundle(output, result.manifest_sha256)
    shutil.rmtree(output / "unexpected")


def test_publish_race_is_rejected_without_replacing_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _source()
    candidate, config, start, end = _config()
    output = tmp_path / "bundle"
    original = evidence._rename_noreplace

    def race(staging: Path, destination: Path) -> None:
        destination.mkdir()
        original(staging, destination)

    monkeypatch.setattr(evidence, "_rename_noreplace", race)
    with pytest.raises(ValueError, match="appeared during publish"):
        generate_bundle(
            source,
            candidate,
            start,
            end,
            config,
            DEFAULT_CALENDAR_PATH.read_bytes(),
            output,
            allow_new_simulation=True,
        )
    assert output.is_dir()
    assert not list(tmp_path.glob(".bundle.staging-*"))


def test_json_depth_and_file_size_limits_are_bounded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    nested = (
        "[" * (evidence.MAX_JSON_DEPTH + 1) + "0" + "]" * (evidence.MAX_JSON_DEPTH + 1)
    )
    with pytest.raises(ValueError, match="nesting"):
        evidence._strict_json(nested.encode(), "nested")
    oversized = tmp_path / "oversized.json"
    oversized.write_bytes(b"0" * (evidence.MAX_REQUEST_BYTES + 1))
    with pytest.raises(ValueError, match="size limit"):
        evidence._regular_file(
            oversized, "request", max_bytes=evidence.MAX_REQUEST_BYTES
        )
    original_loads = json.loads

    def should_not_materialize(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("json.loads must not materialize oversized collection")

    monkeypatch.setattr(json, "loads", should_not_materialize)
    tiny_list = b"[" + b"0," * evidence.MAX_JSON_LIST_ITEMS + b"0]"
    with pytest.raises(ValueError, match="too many array"):
        evidence._strict_json(tiny_list, "large-list")
    tiny_object = b"{" + b'"x":0,' * evidence.MAX_JSON_LIST_ITEMS + b'"x":0}'
    with pytest.raises(ValueError, match="too many object"):
        evidence._strict_json(tiny_object, "large-object")
    monkeypatch.setattr(json, "loads", original_loads)


def test_manifest_declared_total_rejected_before_artifact_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _source()
    candidate, config, start, end = _config()
    output = tmp_path / "bundle"
    generate_bundle(
        source,
        candidate,
        start,
        end,
        config,
        DEFAULT_CALENDAR_PATH.read_bytes(),
        output,
        allow_new_simulation=True,
    )
    manifest = json.loads((output / "manifest.json").read_text())
    for row in manifest["artifacts"].values():
        row["size"] = 13 * 1024 * 1024
    manifest_body = evidence._json_bytes(manifest)
    (output / "manifest.json").write_bytes(manifest_body)
    reads: list[Path] = []
    original_regular_file = evidence._regular_file

    def track_read(
        path: Path, label: str, *, max_bytes: int = evidence.MAX_ARTIFACT_BYTES
    ) -> bytes:
        reads.append(path)
        return original_regular_file(path, label, max_bytes=max_bytes)

    monkeypatch.setattr(evidence, "_regular_file", track_read)
    with pytest.raises(ValueError, match="total file size"):
        verify_bundle(output, evidence.sha256_bytes(manifest_body))
    assert reads == [output / "manifest.json"]


def test_xnys_dst_and_early_close_are_distinct_session_evidence() -> None:
    calendar = load_market_calendar()
    before_dst = calendar.lookup("NMS", date(2024, 3, 8)).session
    after_dst = calendar.lookup("NMS", date(2024, 3, 11)).session
    early = calendar.lookup("NMS", date(2024, 11, 29)).session
    assert before_dst is not None and after_dst is not None and early is not None
    ny = ZoneInfo("America/New_York")
    assert (
        before_dst.close_at.astimezone(ny).utcoffset()
        != after_dst.close_at.astimezone(ny).utcoffset()
    )
    assert (
        early.close_at.astimezone(ny).time() < after_dst.close_at.astimezone(ny).time()
    )
    assert early.close_at != after_dst.close_at


def test_xnys_dst_and_early_close_survive_adapter_bundle_roundtrip(
    tmp_path: Path,
) -> None:
    source = _xnys_time_source()
    output = tmp_path / "xnys-bundle"
    candidate = PortfolioCandidate(id="xnys-time", method="equal", gate="none")
    config = PortfolioConfig(initial_cash_krw=Decimal("1000000"))
    result = generate_bundle(
        source,
        candidate,
        date(2024, 3, 8),
        date(2024, 11, 29),
        config,
        DEFAULT_CALENDAR_PATH.read_bytes(),
        output,
        allow_new_simulation=True,
    )
    assert verify_bundle(output, result.manifest_sha256).nav_count == 3
    sidecar = json.loads((output / "time-evidence.json").read_text())
    rows = {
        close["bar_date"]: (nav["evaluation_at"], close["session"])
        for nav in sidecar["nav"]
        for close in nav["triggering_close_group"]
    }
    assert set(rows) == {"2024-03-08", "2024-03-11", "2024-11-29"}
    before_eval, before = rows["2024-03-08"]
    after_eval, after = rows["2024-03-11"]
    early_eval, early = rows["2024-11-29"]
    assert before["calendar"] == after["calendar"] == early["calendar"] == "XNYS"
    assert before["session_id"] == "XNYS:2024-03-08"
    assert after["session_id"] == "XNYS:2024-03-11"
    assert early["session_id"] == "XNYS:2024-11-29"
    assert before["close_at"] != after["close_at"]
    assert before_eval and before["close_at"]
    assert after_eval and after["close_at"]
    assert early["close_at"].endswith("18:00:00Z")
    assert early_eval != early["close_at"]


def test_xkrx_delayed_close_rejects_close_and_warmup_future_exposure() -> None:
    delayed_day = date(2024, 1, 3)
    source = _single_bar_source(delayed_day)
    calendar = load_market_calendar()
    calendar._days["XKRX"][delayed_day] = _Day(
        "session",
        MarketSession(
            "XKRX",
            delayed_day,
            datetime(2024, 1, 3, 0, tzinfo=UTC),
            datetime(2024, 1, 3, 7, 30, tzinfo=UTC),
        ),
    )
    with pytest.raises(ValueError, match="official session close"):
        evidence._event_plan(source, delayed_day, delayed_day, calendar)
    with pytest.raises(ValueError, match="warmup bar"):
        evidence._event_plan(source, date(2023, 11, 20), date(2023, 11, 20), calendar)


def test_xkrx_and_xnys_close_groups_keep_market_times_separate(tmp_path: Path) -> None:
    source = _causal_pair_source()
    candidate = PortfolioCandidate(id="pair", method="equal", gate="none")
    config = PortfolioConfig(initial_cash_krw=Decimal("1000000"))
    start = source.instruments[0].requested_start
    end = source.instruments[0].requested_end
    output = tmp_path / "pair-bundle"
    result = generate_bundle(
        source,
        candidate,
        start,
        end,
        config,
        DEFAULT_CALENDAR_PATH.read_bytes(),
        output,
        allow_new_simulation=True,
    )
    sidecar = json.loads((output / "time-evidence.json").read_text())
    calendars = {
        session["calendar"]
        for nav in sidecar["nav"]
        for close in nav["triggering_close_group"]
        for session in [close["session"]]
    }
    assert calendars == {"XKRX", "XNYS"}
    assert all(len(nav["triggering_close_group"]) == 1 for nav in sidecar["nav"])
    assert verify_bundle(output, result.manifest_sha256).nav_count == len(
        sidecar["nav"]
    )
