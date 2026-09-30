from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest

from jusik.research_ecos_fx_comparison import InputError, run_comparison

NOW = datetime(2026, 9, 30, 0, 0, tzinfo=UTC)


def _fixture(tmp_path: Path, body: bytes | None = None) -> tuple[Path, str, Path]:
    content = body or b"observation_date,DEXKOUS\n2025-09-11,1388.97\n2025-09-12,.\n"
    baseline = tmp_path / "baseline.csv"
    baseline.write_bytes(content)
    return baseline, hashlib.sha256(content).hexdigest(), tmp_path / "output"


def _success(day: str = "20250911", **changes: str) -> bytes:
    row = {
        "STAT_CODE": "731Y001",
        "ITEM_CODE1": "0000001",
        "TIME": day,
        "UNIT_NAME": "원",
        "DATA_VALUE": "1390.00",
    }
    row.update(changes)
    return json.dumps(
        {"StatisticSearch": {"list_total_count": 1, "row": [row]}}
    ).encode()


def _run(
    tmp_path: Path,
    body: bytes,
    *,
    dates: list[str] | None = None,
    baseline_body: bytes | None = None,
) -> tuple[dict[str, Any], Path, list[httpx.Request]]:
    baseline, sha, output = _fixture(tmp_path, baseline_body)
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, content=body)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        report = run_comparison(
            baseline=baseline,
            baseline_sha256=sha,
            dates=dates or ["2025-09-11"],
            output_dir=output,
            client=client,
            now=lambda: NOW,
        )
    assert baseline.read_bytes() == (
        baseline_body or b"observation_date,DEXKOUS\n2025-09-11,1388.97\n2025-09-12,.\n"
    )
    return report, output, requests


def test_success_persists_bounded_raw_hash_and_diagnostic_delta(tmp_path: Path) -> None:
    raw = _success()
    report, output, requests = _run(tmp_path, raw)
    assert len(requests) == 1
    assert requests[0].url.scheme == "https"
    assert "/StatisticSearch/sample/json/" in requests[0].url.path
    assert requests[0].url.path.endswith("/731Y001/D/20250911/20250911/0000001")
    row = report["rows"][0]
    assert row["fred_krw_per_usd"] == "1388.97"
    assert row["ecos_krw_per_usd"] == "1390.00"
    assert row["delta_krw_per_usd"] == "1.03"
    assert row["raw_sha256"] == hashlib.sha256(raw).hexdigest()
    assert (output / row["raw_file"]).read_bytes() == raw
    assert row["fetched_at"] == NOW.isoformat()
    assert row["publication_at"] is None and row["vintage"] is None
    assert row["point_in_time_verified"] is False
    assert row["eligible_for_performance"] is False
    assert json.loads((output / "comparison.json").read_text()) == report
    assert "진단값" in (output / "comparison.md").read_text()


@pytest.mark.parametrize(
    "changes",
    [
        {"STAT_CODE": "wrong"},
        {"ITEM_CODE1": "wrong"},
        {"TIME": "20250912"},
        {"UNIT_NAME": "USD"},
        {"DATA_VALUE": "NaN"},
        {"DATA_VALUE": "Infinity"},
        {"DATA_VALUE": "0"},
    ],
)
def test_wrong_identity_or_rate_fails_closed(
    tmp_path: Path, changes: dict[str, str]
) -> None:
    report, output, _ = _run(tmp_path, _success(**changes))
    row = report["rows"][0]
    assert row["ecos_status"] == "error"
    assert row["delta_krw_per_usd"] is None
    assert row["raw_sha256"] is None
    assert not list(output.glob("ecos-*.json"))


@pytest.mark.parametrize(
    ("body", "status"),
    [
        (b'{"RESULT":{"CODE":"INFO-200"}}', "missing"),
        (b'{"RESULT":{"CODE":"ERROR-100"}}', "error"),
        (b'{"StatisticSearch":{"list_total_count":2,"row":[]}}', "error"),
        (b'{"StatisticSearch":{"list_total_count":[],"row":[]}}', "error"),
        (
            b'{"StatisticSearch":{"list_total_count":true,"row":[{}]}}',
            "error",
        ),
    ],
)
def test_missing_and_provider_error_have_no_delta(
    tmp_path: Path, body: bytes, status: str
) -> None:
    report, _, _ = _run(tmp_path, body)
    row = report["rows"][0]
    assert row["ecos_status"] == status
    assert row["delta_pct_vs_fred"] is None


def test_oversize_and_redirect_responses_are_reported_without_raw(
    tmp_path: Path,
) -> None:
    for index, response in enumerate(
        [
            httpx.Response(302, headers={"Location": "https://example.com"}),
            httpx.Response(200, content=b"x" * 65_537),
        ]
    ):
        case = tmp_path / str(index)
        case.mkdir()
        baseline, sha, output = _fixture(case)
        with httpx.Client(
            transport=httpx.MockTransport(lambda _: response), follow_redirects=False
        ) as client:
            report = run_comparison(
                baseline=baseline,
                baseline_sha256=sha,
                dates=["2025-09-11"],
                output_dir=output,
                client=client,
                now=lambda: NOW,
            )
        assert report["rows"][0]["ecos_status"] == "error"
        assert not list(output.glob("ecos-*.json"))


def test_explicit_fred_missing_and_absent_are_distinct(tmp_path: Path) -> None:
    baseline = b"observation_date,DEXKOUS\n2025-09-11,1388.97\n2025-09-12,.\n"
    _, sha, output = _fixture(tmp_path, baseline)
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        day = request.url.path.split("/")[-3]
        return httpx.Response(200, content=_success(day))

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        report = run_comparison(
            baseline=tmp_path / "baseline.csv",
            baseline_sha256=sha,
            dates=["2025-09-12", "2025-09-13"],
            output_dir=output,
            client=client,
            now=lambda: NOW,
        )
    assert len(calls) == 2
    assert [row["fred_status"] for row in report["rows"]] == ["missing", "absent"]
    assert all(row["delta_krw_per_usd"] is None for row in report["rows"])


@pytest.mark.parametrize(
    "dates",
    [
        [],
        ["2025-09-11"] * 2,
        ["2025-09-11"] * 11,
        ["2025-09-11", "bad"],
        ["2025-13-11"],
    ],
)
def test_invalid_dates_never_call_provider(tmp_path: Path, dates: list[str]) -> None:
    baseline, sha, output = _fixture(tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        pytest.fail(f"unexpected request: {request.method}")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(InputError):
            run_comparison(
                baseline=baseline,
                baseline_sha256=sha,
                dates=dates,
                output_dir=output,
                client=client,
            )
    assert not output.exists()


def test_more_than_ten_unique_dates_never_call_provider(tmp_path: Path) -> None:
    baseline, sha, output = _fixture(tmp_path)
    dates = [
        (date(2025, 9, 1) + timedelta(days=index)).isoformat() for index in range(11)
    ]
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: pytest.fail("GET"))
    ) as client:
        with pytest.raises(InputError):
            run_comparison(
                baseline=baseline,
                baseline_sha256=sha,
                dates=dates,
                output_dir=output,
                client=client,
            )
    assert not output.exists()


@pytest.mark.parametrize(
    "body",
    [
        b"observation_date,OTHER\n2025-09-11,1388.97\n",
        b"observation_date,DEXKOUS\n2025-09-11,NaN\n",
        b"observation_date,DEXKOUS\n2025-09-11,1388.97\n2025-09-11,.\n",
    ],
)
def test_malformed_baseline_never_calls_provider(tmp_path: Path, body: bytes) -> None:
    baseline, sha, output = _fixture(tmp_path, body)
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: pytest.fail("GET"))
    ) as client:
        with pytest.raises(InputError):
            run_comparison(
                baseline=baseline,
                baseline_sha256=sha,
                dates=["2025-09-11"],
                output_dir=output,
                client=client,
            )
    assert not output.exists()


def test_hash_and_output_collision_are_preflight_failures(tmp_path: Path) -> None:
    baseline, sha, output = _fixture(tmp_path)
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: pytest.fail("GET"))
    ) as client:
        with pytest.raises(InputError):
            run_comparison(
                baseline=baseline,
                baseline_sha256="0" * 64,
                dates=["2025-09-11"],
                output_dir=output,
                client=client,
            )
        output.mkdir()
        sentinel = output / "sentinel"
        sentinel.write_text("untouched")
        with pytest.raises(InputError):
            run_comparison(
                baseline=baseline,
                baseline_sha256=sha,
                dates=["2025-09-11"],
                output_dir=output,
                client=client,
            )
    assert sentinel.read_text() == "untouched"


def test_missing_baseline_is_preflight_failure(tmp_path: Path) -> None:
    output = tmp_path / "output"
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: pytest.fail("GET"))
    ) as client:
        with pytest.raises(InputError):
            run_comparison(
                baseline=tmp_path / "absent.csv",
                baseline_sha256="0" * 64,
                dates=["2025-09-11"],
                output_dir=output,
                client=client,
            )
    assert not output.exists()


def test_partial_transport_failure_keeps_other_observation(tmp_path: Path) -> None:
    baseline, sha, output = _fixture(tmp_path)
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ConnectError("unavailable", request=request)
        return httpx.Response(200, content=_success("20250912"))

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        report = run_comparison(
            baseline=baseline,
            baseline_sha256=sha,
            dates=["2025-09-11", "2025-09-12"],
            output_dir=output,
            client=client,
            now=lambda: NOW,
        )
    assert calls == 2
    assert [row["ecos_status"] for row in report["rows"]] == ["error", "observed"]
    assert all(row["delta_krw_per_usd"] is None for row in report["rows"])
