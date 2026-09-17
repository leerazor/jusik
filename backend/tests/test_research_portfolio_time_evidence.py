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
from jusik.research_market_calendar import DEFAULT_CALENDAR_PATH, load_market_calendar
from jusik.research_models import DailyBar
from jusik.research_portfolio_engine import simulate
from jusik.research_portfolio_models import (
    PortfolioCandidate,
    PortfolioConfig,
    PortfolioInput,
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
    payload = json.loads((output / "simulation.json").read_text())
    direct = simulate(source, candidate, start, end, config)
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
