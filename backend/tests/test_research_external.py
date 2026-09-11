from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from urllib.parse import unquote

import pytest
from pydantic import ValidationError

from jusik.research_external_data import (
    ExternalCollectionError,
    collect_external_sources,
    parse_treasury_xml,
    parse_vix_csv,
    parse_yahoo_chart,
    validate_effr_archive,
    validate_gpr_archive,
)
from jusik.research_external_features import (
    ExternalSignalDiagnostics,
    decision_cutoff,
    evaluate_gate,
    macro_signal,
    validation_coverage,
)
from jusik.research_external_models import ExternalFeatureSnapshot, ExternalObservation
from jusik.research_external_store import ExternalStore
from jusik.research_models import DailyBar
from jusik.research_optimizer import Candidate, _candidate_signal, candidates


def _observation(
    series: str,
    day: date,
    value: str,
    *,
    available_at: datetime | None = None,
    revision: str = "bootstrap",
) -> ExternalObservation:
    return ExternalObservation(
        series=series,
        observed_on=day,
        value=Decimal(value),
        available_at=available_at
        or datetime.combine(day + timedelta(days=1), datetime.min.time(), UTC),
        revision=revision,
    )


def _daily_bars(days: int = 25) -> tuple[DailyBar, ...]:
    first = date(2026, 1, 1)
    return tuple(
        DailyBar(
            date=first + timedelta(days=index),
            open=Decimal(100 + index),
            high=Decimal(101 + index),
            low=Decimal(99 + index),
            close=Decimal(100 + index),
            adjusted_open=Decimal(100 + index),
            adjusted_high=Decimal(101 + index),
            adjusted_low=Decimal(99 + index),
            adjusted_close=Decimal(100 + index),
            volume=100,
        )
        for index in range(days)
    )


def test_original_89_candidates_are_an_exact_prefix() -> None:
    configured = candidates()
    payload = [
        {"id": item.id, "family": item.family, "parameters": item.parameters}
        for item in configured[:89]
    ]

    assert len(configured) == 93
    assert (
        hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        == "5e5ba4660a88e3dfc78f3422f27b48284bd1026c5c0630af32909d4eaa223e9e"
    )
    assert configured[89].id == "external_control-ffdca988e7b2"


def test_decision_cutoffs_follow_exchange_dst() -> None:
    assert decision_cutoff(date(2026, 3, 6), "America/New_York") == datetime(
        2026, 3, 6, 21, tzinfo=UTC
    )
    assert decision_cutoff(date(2026, 3, 9), "America/New_York") == datetime(
        2026, 3, 9, 20, tzinfo=UTC
    )
    assert decision_cutoff(date(2026, 3, 9), "Asia/Seoul") == datetime(
        2026, 3, 9, 6, 30, tzinfo=UTC
    )


def test_point_in_time_gate_ignores_future_revision_and_rejects_stale() -> None:
    first = date(2026, 1, 1)
    observations: list[ExternalObservation] = []
    for index in range(22):
        day = first + timedelta(days=index)
        observations.extend(
            [
                _observation("treasury_2y", day, "4"),
                _observation("treasury_10y", day, "4"),
            ]
        )
    target = first + timedelta(days=21)
    observations.append(
        _observation(
            "treasury_10y",
            target,
            "8",
            available_at=datetime(2026, 2, 1, tzinfo=UTC),
            revision="future-revision",
        )
    )
    snapshot = ExternalFeatureSnapshot(observations=observations)

    assert evaluate_gate("rates", snapshot, target, "America/New_York") == (
        True,
        None,
    )
    stale_day = target + timedelta(days=8)
    allowed, reason = evaluate_gate("rates", snapshot, stale_day, "America/New_York")
    assert allowed is None
    assert reason == "treasury_2y:7일초과"


def test_all_preregistered_thresholds_are_inclusive() -> None:
    first = date(2026, 1, 1)
    decision_day = first + timedelta(days=21)
    observations: list[ExternalObservation] = []
    for index in range(21):
        day = first + timedelta(days=index)
        observations.extend(
            [
                _observation("treasury_2y", day, "4"),
                _observation("treasury_10y", day, "2.5" if index == 0 else "3"),
                _observation("usdkrw", day, "1000" if index == 0 else "1050"),
                _observation("vix", day, "30"),
                _observation("uso", day, "100" if index == 0 else "115"),
                _observation("gld", day, "100" if index == 0 else "110"),
                _observation("hyg", day, "100" if index == 0 else "97"),
            ]
        )
    snapshot = ExternalFeatureSnapshot(observations=observations)

    assert evaluate_gate("rates", snapshot, decision_day, "America/New_York")[0]
    assert evaluate_gate("fx_vix", snapshot, decision_day, "America/New_York")[0]
    assert evaluate_gate("stress", snapshot, decision_day, "America/New_York")[0]


def test_missing_macro_data_is_cash_and_counted_without_zero_fill() -> None:
    diagnostics = ExternalSignalDiagnostics()
    signal = macro_signal("stress", None, "America/New_York", diagnostics)

    assert signal("NVDA", _daily_bars()) is False
    assert diagnostics.as_json() == {
        "decision_date_count": 1,
        "missing_date_count": 1,
        "missing_reasons": {"외부변수스냅샷없음": 1},
        "complete": False,
    }
    complete, detail = validation_coverage(
        "stress", None, [date(2026, 1, 2)], "America/New_York"
    )
    assert complete is False
    assert detail["missing_date_count"] == 1
    with pytest.raises(ValidationError):
        _observation("usdkrw", date(2026, 1, 1), "0")


def test_unfiltered_control_is_exact_baseline_signal() -> None:
    control = candidates()[89]
    bars = _daily_bars()
    signal = _candidate_signal(control, object())  # type: ignore[arg-type]

    assert signal("NVDA", bars) is True
    drifted = Candidate(
        "drifted",
        "external_macro",
        {
            **candidates()[90].parameters,
            "maximum_10y_change_pp": "0.51",
        },
    )
    with pytest.raises(ValueError, match="Invalid external macro"):
        _candidate_signal(  # type: ignore[arg-type]
            drifted, object(), ExternalSignalDiagnostics()
        )


def test_external_store_is_append_only_and_late_backfill_is_not_backdated(
    tmp_path: Path,
) -> None:
    store = ExternalStore(tmp_path / "external.db")
    day = date(2026, 1, 5)
    first_capture = datetime(2026, 1, 20, tzinfo=UTC)
    initial = _observation("vix", day, "20")
    assert (
        store.save_success(
            "vix",
            body=b"first",
            content_type="text/csv",
            observations=[initial],
            captured_at=first_capture,
        )
        == 1
    )
    assert (
        store.save_success(
            "vix",
            body=b"first",
            content_type="text/csv",
            observations=[initial],
            captured_at=first_capture + timedelta(hours=1),
        )
        == 0
    )
    late_day = day - timedelta(days=1)
    second_capture = datetime(2026, 1, 21, tzinfo=UTC)
    late = _observation("vix", late_day, "19")
    store.save_success(
        "vix",
        body=b"second",
        content_type="text/csv",
        observations=[initial, late],
        captured_at=second_capture,
    )
    changed = _observation("vix", day, "21")
    reverted = _observation("vix", day, "20")
    store.save_success(
        "vix",
        body=b"third",
        content_type="text/csv",
        observations=[changed],
        captured_at=second_capture + timedelta(hours=1),
    )
    store.save_success(
        "vix",
        body=b"fourth",
        content_type="text/csv",
        observations=[reverted],
        captured_at=second_capture + timedelta(hours=2),
    )

    snapshot = store.snapshot()
    late_saved = next(
        item for item in snapshot.observations if item.observed_on == late_day
    )
    day_versions = [item for item in snapshot.observations if item.observed_on == day]
    assert late_saved.available_at == second_capture
    assert [item.value for item in day_versions] == [
        Decimal(20),
        Decimal(21),
        Decimal(20),
    ]
    assert len({item.revision for item in day_versions}) == 3


def test_store_retains_success_as_stale_and_freezes_run_binding(tmp_path: Path) -> None:
    store = ExternalStore(tmp_path / "external.db")
    pending = store.statuses(usages={"vix": "feature"})
    assert [(item.source, item.status) for item in pending] == [("vix", "pending")]
    captured = datetime(2026, 1, 10, tzinfo=UTC)
    store.save_success(
        "vix",
        body=b"data",
        content_type="text/csv",
        observations=[_observation("vix", date(2026, 1, 8), "20")],
        captured_at=captured,
    )
    frozen = store.bind_snapshot("batch", store.snapshot())
    store.record_failure(
        "vix", "network failed", attempted_at=captured + timedelta(hours=6)
    )

    status = store.statuses(now=captured + timedelta(hours=7))[0]
    assert status.status == "stale"
    assert status.last_success_at == captured
    assert status.raw_archive_count == 1
    assert store.load_bound_snapshot("batch") == frozen


def test_provider_parsers_validate_timezone_lengths_and_archives() -> None:
    treasury = b"""<feed xmlns:d='x'><entry><content><m:properties xmlns:m='y'>
      <d:NEW_DATE>2026-01-02T00:00:00</d:NEW_DATE>
      <d:BC_2YEAR>4.25</d:BC_2YEAR><d:BC_10YEAR>4.50</d:BC_10YEAR>
    </m:properties></content></entry></feed>"""
    assert len(parse_treasury_xml(treasury, revision="r")) == 2
    assert parse_vix_csv(b"DATE,CLOSE\n01/02/2026,17.5\n", revision="r")[
        0
    ].value == Decimal("17.5")
    validate_gpr_archive(b"\xd0\xcf\x11\xe0raw")
    validate_effr_archive(b'{"refRates": []}')
    with pytest.raises(ExternalCollectionError):
        validate_gpr_archive(b"not-xls")

    timestamp = datetime(2026, 3, 9, 4, tzinfo=UTC).timestamp()
    body = json.dumps(
        {
            "chart": {
                "error": None,
                "result": [
                    {
                        "meta": {
                            "symbol": "SPY",
                            "exchangeTimezoneName": "America/New_York",
                        },
                        "timestamp": [timestamp],
                        "indicators": {"quote": [{"close": [500]}]},
                    }
                ],
            }
        }
    ).encode()
    item = parse_yahoo_chart(body, series="spy", expected_symbol="SPY", revision="r")[0]
    assert item.observed_on == date(2026, 3, 9)
    assert item.available_at == datetime(2026, 3, 11, tzinfo=UTC)


def test_collection_failure_is_isolated_from_other_sources(tmp_path: Path) -> None:
    treasury = b"""<feed xmlns:d='x'><entry><content><m:properties xmlns:m='y'>
      <d:NEW_DATE>2026-01-02T00:00:00</d:NEW_DATE>
      <d:BC_2YEAR>4.25</d:BC_2YEAR><d:BC_10YEAR>4.50</d:BC_10YEAR>
    </m:properties></content></entry></feed>"""

    async def fetch(url: str, _params: object) -> tuple[bytes, str]:
        if "treasury.gov" in url:
            return treasury, "application/xml"
        if "VIX" in url:
            raise ExternalCollectionError("vix unavailable")
        if "finance/chart" in url:
            symbol = unquote(url.rsplit("/", 1)[-1])
            body = json.dumps(
                {
                    "chart": {
                        "error": None,
                        "result": [
                            {
                                "meta": {
                                    "symbol": symbol,
                                    "exchangeTimezoneName": "America/New_York",
                                },
                                "timestamp": [
                                    datetime(2026, 1, 2, tzinfo=UTC).timestamp()
                                ],
                                "indicators": {"quote": [{"close": [100]}]},
                            }
                        ],
                    }
                }
            ).encode()
            return body, "application/json"
        if "gpr" in url:
            return b"\xd0\xcf\x11\xe0raw", "application/vnd.ms-excel"
        return (
            b'{"refRates": ['
            b'{"effectiveDate": "2026-01-01"},'
            b'{"effectiveDate": "2026-01-03"}]}'
        ), "application/json"

    store = ExternalStore(tmp_path / "external.db")
    outcomes = asyncio.run(
        collect_external_sources(
            store,
            start=date(2026, 1, 1),
            end=date(2026, 1, 3),
            captured_at=datetime(2026, 1, 5, tzinfo=UTC),
            fetch_bytes=fetch,
        )
    )

    assert outcomes["vix"] == "error"
    assert outcomes["treasury"] == "success"
    assert outcomes["yahoo_hyg"] == "success"
    statuses = {item.source: item for item in store.statuses()}
    assert statuses["vix"].status == "error"
    assert statuses["gpr"].raw_bytes > 0
