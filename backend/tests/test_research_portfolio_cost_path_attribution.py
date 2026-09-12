import hashlib
import json
from collections.abc import Generator
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import pytest

import jusik.research_portfolio_cost_path_attribution as attribution
from jusik.research_portfolio_cost_path_attribution import (
    enrich_report,
    first_trade_path_mismatch,
    load_frozen,
)
from jusik.research_portfolio_models import (
    PortfolioCandidate,
    PortfolioEquityPoint,
    PortfolioMetrics,
    PortfolioSimulation,
)


@pytest.fixture(autouse=True)
def restore_pinned_hash_constants(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[None]:
    originals = {
        "RESULTS_SHA256": attribution.RESULTS_SHA256,
        "PREREGISTRATION_SHA256": attribution.PREREGISTRATION_SHA256,
        "MANIFEST_SHA256": attribution.MANIFEST_SHA256,
    }
    for name, value in originals.items():
        monkeypatch.setattr(attribution, name, value)
    yield


def test_first_trade_path_mismatch_is_utc_sorted_and_excludes_price() -> None:
    class Trade:
        def __init__(self, at: datetime, symbol: str, side: str, quantity: int) -> None:
            self.executed_at, self.symbol, self.side, self.quantity = (
                at,
                symbol,
                side,
                quantity,
            )

    class Sim:
        def __init__(self, trades: list[Any]) -> None:
            self.trades = trades

    late = datetime(2024, 1, 1, 1, tzinfo=UTC)
    early = datetime(2024, 1, 1, 0, tzinfo=UTC)
    result = first_trade_path_mismatch(
        cast(Any, Sim([Trade(late, "ZZZ", "buy", 1), Trade(early, "AAA", "sell", 2)])),
        cast(Any, Sim([Trade(late, "ZZZ", "buy", 1), Trade(early, "AAA", "buy", 2)])),
    )
    assert result == {
        "index": 0,
        "left": ["2024-01-01T00:00:00+00:00", "AAA", "sell", 2],
        "right": ["2024-01-01T00:00:00+00:00", "AAA", "buy", 2],
    }


def test_identical_paths_have_no_mismatch() -> None:
    class Trade:
        executed_at = datetime(2024, 1, 1, tzinfo=UTC)
        symbol, side, quantity = "AAA", "buy", 1

    class Sim:
        trades = [Trade()]

    assert first_trade_path_mismatch(cast(Any, Sim()), cast(Any, Sim())) is None


def _saved_report() -> dict[str, Any]:
    rows = []
    for period in [f"fold_{i}" for i in range(1, 8)] + ["continuous"]:
        for arm in ("control", "variant"):
            for high in (2, 3):
                rows.append(
                    {
                        "period": period,
                        "arm": arm,
                        "from_cost": 1,
                        "to_cost": high,
                        "aggregate_delta_net_pnl": "-1.000001"
                        if arm == "variant"
                        else "-1.000000",
                        "aggregate_delta_transaction_fx": "2.000000",
                        "aggregate_delta_pre_cost": "0.999999"
                        if arm == "variant"
                        else "1.000000",
                        "aggregate_reconciliation_residual": "0.000000",
                        "turnover_delta_pp": "-2.5",
                        "max_drawdown_delta_pp": "0.5",
                        "first_trade_path_mismatch": None,
                    }
                )
    return {"cost_comparisons": rows}


def test_enrichment_preserves_negative_and_zero_and_is_deterministic() -> None:
    first = enrich_report(_saved_report())
    second = enrich_report(_saved_report())
    assert first == second
    assert len(first["variant_control_decomposition"]) == 16
    assert (
        first["variant_control_decomposition"][0][
            "variant_minus_control_aggregate_delta_net_pnl"
        ]
        == "-0.000001"
    )
    assert (
        first["variant_control_decomposition"][0][
            "variant_minus_control_aggregate_delta_pre_cost"
        ]
        == "-0.000001"
    )
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


@pytest.mark.parametrize("count", [31, 33])
def test_enrichment_rejects_incomplete_or_extra_comparisons(count: int) -> None:
    report = _saved_report()
    report["cost_comparisons"] = (
        (report["cost_comparisons"][:32] + [report["cost_comparisons"][0]])
        if count == 33
        else report["cost_comparisons"][:count]
    )
    with pytest.raises(ValueError, match="32"):
        enrich_report(report)


def test_known_same_path_cost_only_and_rounding_boundaries() -> None:
    report = _saved_report()
    for row in report["cost_comparisons"]:
        row["aggregate_delta_net_pnl"] = "-2.000000"
        row["aggregate_delta_transaction_fx"] = "2.000000"
        row["aggregate_delta_pre_cost"] = "0.000000"
        row["aggregate_reconciliation_residual"] = "0.000000"
    enriched = enrich_report(report)
    assert (
        enriched["variant_control_decomposition"][0][
            "variant_minus_control_aggregate_delta_net_pnl"
        ]
        == "0.000000"
    )
    report["cost_comparisons"][0]["aggregate_delta_pre_cost"] = "0.000002"
    with pytest.raises(ValueError, match="exceeds tolerance"):
        enrich_report(report)


def test_timezone_same_instant_and_quantity_mismatch_are_path_differences() -> None:
    class Trade:
        def __init__(self, at: datetime, quantity: int) -> None:
            self.executed_at, self.symbol, self.side, self.quantity = (
                at,
                "AAA",
                "buy",
                quantity,
            )

    class Sim:
        def __init__(self, trade: Any) -> None:
            self.trades = [trade]

    instant = datetime(2024, 1, 1, 0, tzinfo=UTC)
    offset = datetime(2024, 1, 1, 9, tzinfo=timezone(timedelta(hours=9)))
    assert (
        first_trade_path_mismatch(
            cast(Any, Sim(Trade(instant, 1))), cast(Any, Sim(Trade(offset, 1)))
        )
        is None
    )
    assert (
        first_trade_path_mismatch(
            cast(Any, Sim(Trade(instant, 1))), cast(Any, Sim(Trade(instant, 2)))
        )
        is not None
    )


def test_synthetic_loader_rejects_extra_file(tmp_path: Path) -> None:
    # The production loader's exact-file guard is exercised without loading real inputs.
    root = tmp_path / "input"
    (root / "simulations").mkdir(parents=True)
    for index in range(48):
        (root / "simulations" / f"fixture-{index}.json").write_text("{}")
    (root / "simulations" / "extra.json").write_text("{}")
    with pytest.raises(
        (FileNotFoundError, ValueError), match="hash|filesystem|evaluation|results"
    ):
        load_frozen(root)


def _synthetic_input(tmp_path: Path) -> Path:
    root = tmp_path / "frozen"
    sim_dir = root / "simulations"
    sim_dir.mkdir(parents=True)
    periods = [f"fold_{i}" for i in range(1, 8)] + ["continuous"]
    candidate = PortfolioCandidate(id="fixture", method="equal", gate="none")
    metrics = PortfolioMetrics(
        initial_equity_krw=Decimal("100000000"),
        final_equity_krw=Decimal("100000000"),
        total_return_pct=Decimal("0"),
        max_drawdown_pct=Decimal("0"),
        trade_count=0,
        transaction_cost_krw=Decimal("0"),
        fx_cost_krw=Decimal("0"),
        turnover_pct=Decimal("0"),
    )
    simulation = PortfolioSimulation(
        candidate=candidate,
        period_start=date(2024, 1, 1),
        period_end=date(2024, 1, 31),
        metrics=metrics,
        complete=True,
        incomplete_reasons=[],
        drawdown_latched=False,
        drawdown_latched_at=None,
        equity=[
            PortfolioEquityPoint(
                at=datetime(2024, 1, 1, tzinfo=UTC),
                equity_krw=Decimal("100000000"),
                cash_krw=Decimal("100000000"),
                drawdown_pct=Decimal("0"),
            )
        ],
        trades=[],
        weekly_targets=[],
        positions=[],
        contributions_krw={},
        split_cash_in_lieu_krw={},
        overlap_diagnostics={},
    )
    payload = simulation.model_dump(mode="json")
    evaluations, hashes = [], {}
    for period in periods:
        for arm in ("control", "variant"):
            for cost in (1, 2, 3):
                name = f"{period}-{arm}_c{cost}.json"
                path = sim_dir / name
                path.write_text(json.dumps(payload, sort_keys=True))
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                hashes[f"simulations/{name}"] = digest
                evaluations.append(
                    {
                        "artifact": name,
                        "period": period,
                        "arm": arm,
                        "cost_multiplier": cost,
                        "complete": True,
                        "initial_equity_krw": "100000000",
                        "final_equity_krw": "100000000",
                        "total_return_pct": "0",
                        "max_drawdown_pct": "0",
                        "trade_count": 0,
                        "transaction_cost_krw": "0",
                        "fx_cost_krw": "0",
                        "turnover_pct": "0",
                        "sha256": digest,
                    }
                )
    periods_meta = [
        {"name": p, "start": "2024-01-01", "end": "2024-01-31"} for p in periods
    ]
    prereg = {
        "evaluation_count": 48,
        "periods": periods_meta,
        "base_config": {
            "initial_cash_krw": "100000000",
            "symbol_cap": "0.20",
            "gross_cap": "0.60",
            "leveraged_etf_cap": "0.20",
            "drawdown_limit": "0.10",
        },
        "validated_configs": {
            f"{band}-c{cost}": {} for band in ("0.02", "0.04") for cost in (1, 2, 3)
        },
    }
    (root / "results.json").write_text(
        json.dumps({"evaluation_count": 48, "evaluations": evaluations}, sort_keys=True)
    )
    (root / "preregistration.json").write_text(json.dumps(prereg, sort_keys=True))
    (root / "hash-manifest.json").write_text(json.dumps(hashes, sort_keys=True))
    attribution.RESULTS_SHA256 = hashlib.sha256(
        (root / "results.json").read_bytes()
    ).hexdigest()
    attribution.PREREGISTRATION_SHA256 = hashlib.sha256(
        (root / "preregistration.json").read_bytes()
    ).hexdigest()
    attribution.MANIFEST_SHA256 = hashlib.sha256(
        (root / "hash-manifest.json").read_bytes()
    ).hexdigest()
    return root


def test_synthetic_loader_accepts_exact_48(tmp_path: Path) -> None:
    assert len(load_frozen(_synthetic_input(tmp_path))) == 48


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "bytes", "config"])
def test_synthetic_loader_rejects_mutations(tmp_path: Path, mutation: str) -> None:
    root = _synthetic_input(tmp_path)
    if mutation == "missing":
        next((root / "simulations").glob("*.json")).unlink()
    elif mutation == "duplicate":
        results = json.loads((root / "results.json").read_text())
        results["evaluations"].append(results["evaluations"][0])
        (root / "results.json").write_text(json.dumps(results, sort_keys=True))
        attribution.RESULTS_SHA256 = hashlib.sha256(
            (root / "results.json").read_bytes()
        ).hexdigest()
    elif mutation == "bytes":
        path = next((root / "simulations").glob("*.json"))
        path.write_text(path.read_text() + " ")
    else:
        prereg = json.loads((root / "preregistration.json").read_text())
        prereg["base_config"]["drawdown_limit"] = "0.20"
        (root / "preregistration.json").write_text(json.dumps(prereg, sort_keys=True))
        attribution.PREREGISTRATION_SHA256 = hashlib.sha256(
            (root / "preregistration.json").read_bytes()
        ).hexdigest()
    with pytest.raises((ValueError, FileNotFoundError)):
        load_frozen(root)
