import hashlib
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

import jusik.research_portfolio_gpu_stress as stress


def _source(path: Path, values: list[str], *, complete: bool = True) -> str:
    start = datetime(2024, 1, 1, tzinfo=UTC)
    equity = [
        {
            "at": (start + timedelta(days=i)).isoformat(),
            "equity_krw": value,
            "cash_krw": value,
            "drawdown_pct": "0",
        }
        for i, value in enumerate(values)
    ]
    peak = Decimal(values[0])
    mdd = Decimal(0)
    for value in map(Decimal, values):
        if not value.is_finite():
            mdd = Decimal("NaN")
            break
        peak = max(peak, value)
        mdd = max(mdd, (peak - value) / peak * 100)
    payload = {
        "candidate": {"id": "x", "method": "equal", "gate": "none"},
        "period_start": "2024-01-01",
        "period_end": "2024-01-31",
        "metrics": {
            "initial_equity_krw": "100000000",
            "final_equity_krw": values[-1],
            "total_return_pct": str(
                (Decimal(values[-1]) / Decimal(values[0]) - 1) * 100
            ),
            "max_drawdown_pct": str(mdd),
            "trade_count": 0,
            "transaction_cost_krw": "0",
            "fx_cost_krw": "0",
            "turnover_pct": "0",
        },
        "complete": complete,
        "incomplete_reasons": [],
        "drawdown_latched": False,
        "drawdown_latched_at": None,
        "equity": equity,
        "trades": [],
        "weekly_targets": [],
        "positions": [],
        "contributions_krw": {},
        "split_cash_in_lieu_krw": {},
        "overlap_diagnostics": {},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _request(
    tmp_path: Path, *, scenarios: int = 2, values: list[str] | None = None
) -> Path:
    values = values or ["100000000", "110000000", "105000000", "120000000"]
    source = tmp_path / "source.json"
    digest = _source(source, values)
    request = {
        "cases": [{"name": "control", "path": str(source), "sha256": digest}],
        "seed": 20260913,
        "block_length_observations": 2,
        "horizon_observations": 3,
        "scenarios": scenarios,
        "initial_capital_krw": "100000000",
    }
    result = tmp_path / "request.json"
    result.write_text(json.dumps(request), encoding="utf-8")
    return result


def test_decimal_metrics_flat_and_drawdown_boundary() -> None:
    flat = stress.calculate_metrics(
        [Decimal("100"), Decimal("100"), Decimal("100")], [0, 1], Decimal("100")
    )
    assert flat["max_drawdown_pct"] == 0
    down = stress.calculate_metrics(
        [Decimal("100"), Decimal("80"), Decimal("80")], [0], Decimal("100")
    )
    assert down["drawdown_20"] is True
    assert down["loss_drawdown_20"] is True


def test_request_rejects_bad_source_hash_and_incomplete(tmp_path: Path) -> None:
    request = _request(tmp_path)
    raw = json.loads(request.read_text())
    raw["cases"][0]["sha256"] = "0" * 64
    request.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="hash mismatch"):
        stress.validate_inputs(stress.load_request(request)[0])

    digest = _source(
        tmp_path / "source.json", ["100000000", "100000001"], complete=False
    )
    raw["cases"][0]["sha256"] = digest
    request.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="complete"):
        stress.validate_inputs(stress.load_request(request)[0])


@pytest.mark.parametrize(
    "values", [["100000000", "0"], ["100000000", "-1"], ["100000000", "NaN"]]
)
def test_request_rejects_invalid_nav(tmp_path: Path, values: list[str]) -> None:
    request = _request(tmp_path, values=values)
    with pytest.raises(ValueError):
        stress.validate_inputs(stress.load_request(request)[0])


def test_request_rejects_non_utc_duplicate_and_misaligned_times(tmp_path: Path) -> None:
    request = _request(tmp_path)
    source = tmp_path / "source.json"
    raw = json.loads(source.read_text())
    raw["equity"][1]["at"] = raw["equity"][0]["at"]
    source.write_text(json.dumps(raw))
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    payload = json.loads(request.read_text())
    payload["cases"][0]["sha256"] = digest
    request.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="chronological"):
        stress.validate_inputs(stress.load_request(request)[0])


def test_run_reuses_joint_indices_and_rejects_collision(tmp_path: Path) -> None:
    request = _request(tmp_path, scenarios=3)
    raw = json.loads(request.read_text())
    source = Path(raw["cases"][0]["path"])
    digest = raw["cases"][0]["sha256"]
    raw["cases"].append({"name": "variant", "path": str(source), "sha256": digest})
    request.write_text(json.dumps(raw))
    output = tmp_path / "output"
    result = stress.run(request, output, "cpu")
    assert result["scenario_count"] == 3
    rows = json.loads((output / "results.json").read_text())["metrics"]
    assert [row["scenario"] for row in rows] == [0, 0, 1, 1, 2, 2]
    with pytest.raises(ValueError, match="new"):
        stress.run(request, output, "cpu")


def test_resource_cap_is_prevalidated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request = _request(tmp_path, scenarios=2)
    monkeypatch.setattr(stress, "GPU_MEMORY_CAP_BYTES", 1)
    with pytest.raises(ValueError, match="memory"):
        stress.run(request, tmp_path / "output", "cpu")


def test_auto_cpu_fallback_and_explicit_cuda_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request = _request(tmp_path)
    monkeypatch.setitem(__import__("sys").modules, "torch", None)
    result = stress.run(request, tmp_path / "auto", "auto")
    assert result["device"] == "cpu"
    with pytest.raises(RuntimeError, match="CUDA"):
        stress.run(request, tmp_path / "cuda", "cuda")
