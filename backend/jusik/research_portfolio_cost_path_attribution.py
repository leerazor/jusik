"""Attribute frozen held-band cost paths without rerunning simulations."""
# The generated markdown table rows intentionally remain readable as one line.
# ruff: noqa: E501

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from jusik.research_entry_attribution import attribute_simulation
from jusik.research_portfolio_models import PortfolioSimulation

PERIODS = tuple([f"fold_{i}" for i in range(1, 8)] + ["continuous"])
ARMS = ("control", "variant")
COSTS = (1, 2, 3)
TOLERANCE = Decimal("0.000001")
RESULTS_SHA256 = "d6e4895eac42625fe6fd0f3278ee98195bc031c7e651cb3d003b3c9fa4d4e2f1"
PREREGISTRATION_SHA256 = (
    "aeae52d4e1a036b2837f39ce879315b03e98023ac4ba6838e7506e7e602ce3f9"
)
MANIFEST_SHA256 = "4c5d3eddc7b1f126dd62e5a5a2d718b31d22c0c93ea5295af36fd6aa7e43171f"


def _json(path: Path, digest: str) -> dict[str, Any]:
    body = path.read_bytes()
    actual = hashlib.sha256(body).hexdigest()
    if actual != digest:
        raise ValueError(f"{path.name} hash mismatch: {actual} != {digest}")
    value = json.loads(body)
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must be an object")
    return value


def _key(name: str) -> tuple[str, str, int]:
    stem = name.removesuffix(".json")
    period, arm_cost = stem.split("-", 1)
    arm, cost = arm_cost.rsplit("_c", 1)
    if period not in PERIODS or arm not in ARMS or cost not in {"1", "2", "3"}:
        raise ValueError(f"unexpected simulation filename: {name}")
    return period, arm, int(cost)


def _dec(value: Any) -> Decimal:
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError("non-finite decimal")
    return result


def _delta(a: Decimal, b: Decimal) -> str:
    return format(b - a, "f")


def _trade_key(trade: Any) -> tuple[Any, ...]:
    return (trade.executed_at.astimezone(UTC), trade.symbol, trade.side, trade.quantity)


def first_trade_path_mismatch(
    left: PortfolioSimulation, right: PortfolioSimulation
) -> dict[str, Any] | None:
    """Return the first differing execution path, sorted in UTC, without prices."""
    a = sorted(_trade_key(t) for t in left.trades)
    b = sorted(_trade_key(t) for t in right.trades)
    for index, pair in enumerate(zip(a, b)):
        if pair[0] != pair[1]:
            return {
                "index": index,
                "left": _json_value(pair[0]),
                "right": _json_value(pair[1]),
            }
    if len(a) != len(b):
        return {
            "index": min(len(a), len(b)),
            "left": _json_value(a[min(len(a), len(b))]) if len(a) > len(b) else None,
            "right": _json_value(b[min(len(a), len(b))]) if len(b) > len(a) else None,
        }
    return None


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    return value


def _validate_simulation(
    sim: PortfolioSimulation, name: str, period: dict[str, Any], row: dict[str, Any]
) -> None:
    if not sim.complete or sim.incomplete_reasons:
        raise ValueError(f"incomplete simulation: {name}")
    p, arm, cost = _key(name)
    if (
        row.get("period") != p
        or row.get("arm") != arm
        or row.get("cost_multiplier") != cost
    ):
        raise ValueError(f"metadata mismatch: {name}")
    if (
        sim.period_start.isoformat() != period["start"]
        or sim.period_end.isoformat() != period["end"]
    ):
        raise ValueError(f"period mismatch: {name}")
    if row.get("complete") is not True:
        raise ValueError(f"evaluation incomplete: {name}")
    for field in (
        "initial_equity_krw",
        "final_equity_krw",
        "total_return_pct",
        "max_drawdown_pct",
        "trade_count",
        "transaction_cost_krw",
        "fx_cost_krw",
        "turnover_pct",
    ):
        if field not in row or _dec(getattr(sim.metrics, field)) != _dec(row[field]):
            raise ValueError(f"stored metric mismatch: {name} {field}")
    if sim.metrics.initial_equity_krw != Decimal("100000000"):
        raise ValueError("frozen initial capital changed")


def load_frozen(input_dir: Path) -> dict[tuple[str, str, int], PortfolioSimulation]:
    """Load exactly the pinned 48 simulations and validate metadata/accounting."""
    results = _json(input_dir / "results.json", RESULTS_SHA256)
    prereg = _json(input_dir / "preregistration.json", PREREGISTRATION_SHA256)
    manifest = _json(input_dir / "hash-manifest.json", MANIFEST_SHA256)
    if (
        len(results.get("evaluations", [])) != 48
        or results.get("evaluation_count") != 48
        or prereg.get("evaluation_count") != 48
    ):
        raise ValueError("frozen evaluation count must be 48")
    base = prereg.get("base_config")
    if not isinstance(base, dict) or any(
        base.get(k) != v
        for k, v in {
            "initial_cash_krw": "100000000",
            "symbol_cap": "0.20",
            "gross_cap": "0.60",
            "leveraged_etf_cap": "0.20",
            "drawdown_limit": "0.10",
        }.items()
    ):
        raise ValueError("frozen capital or risk configuration changed")
    configs = prereg.get("validated_configs")
    if not isinstance(configs, dict) or set(configs) != {
        f"{band}-c{cost}" for band in ("0.02", "0.04") for cost in COSTS
    }:
        raise ValueError("validated band/cost configurations are incomplete")
    evaluations = results.get("evaluations")
    periods = prereg.get("periods")
    if (
        not isinstance(evaluations, list)
        or len(evaluations) != 48
        or not isinstance(periods, list)
        or len(periods) != 8
    ):
        raise ValueError("complete frozen metadata is required")
    period_map = {
        str(item["name"]): item
        for item in periods
        if isinstance(item, dict) and "name" in item
    }
    if tuple(period_map) != PERIODS:
        raise ValueError("period ordering is not frozen")
    expected: dict[str, dict[str, Any]] = {
        str(row["artifact"]): row for row in evaluations if isinstance(row, dict)
    }
    names = {f"{p}-{a}_c{c}.json" for p in PERIODS for a in ARMS for c in COSTS}
    if set(expected) != names:
        raise ValueError("frozen result set is not exactly 48 artifacts")
    files = (
        manifest.get("simulations")
        if isinstance(manifest.get("simulations"), dict)
        else {k: v for k, v in manifest.items() if str(k).startswith("simulations/")}
    )
    if not isinstance(files, dict):
        raise ValueError("simulation hash manifest is missing")
    actual_files = {path.name for path in (input_dir / "simulations").glob("*.json")}
    if actual_files != names:
        raise ValueError("simulation filesystem is not exactly 48 files")
    output: dict[tuple[str, str, int], PortfolioSimulation] = {}
    for name in sorted(names):
        rel = f"simulations/{name}"
        digest = files.get(rel)
        if not isinstance(digest, str):
            raise ValueError(f"missing simulation hash: {rel}")
        path = input_dir / rel
        body = path.read_bytes()
        if hashlib.sha256(body).hexdigest() != digest:
            raise ValueError(f"simulation hash mismatch: {name}")
        if expected[name].get("sha256") != digest:
            raise ValueError(f"evaluation/manifest hash mismatch: {name}")
        try:
            sim = PortfolioSimulation.model_validate(json.loads(body))
        except (json.JSONDecodeError, ValidationError) as exc:
            raise ValueError(f"invalid simulation: {name}") from exc
        _validate_simulation(sim, name, period_map[_key(name)[0]], expected[name])
        accounting = attribute_simulation(sim, _key(name)[2])
        if abs(accounting["residual"]) > TOLERANCE:
            raise ValueError(f"accounting residual exceeds tolerance: {name}")
        output[_key(name)] = sim
    return output


def _path_row(
    period: str,
    arm: str,
    low: int,
    high: int,
    sims: dict[tuple[str, str, int], PortfolioSimulation],
    attrs: dict[tuple[str, str, int], dict[str, Any]],
) -> dict[str, Any]:
    a, b = attrs[(period, arm, low)], attrs[(period, arm, high)]
    symbols = sorted(set(a["rows"]) | set(b["rows"]))
    rows = []
    for symbol in symbols:
        x, y = a["rows"].get(symbol, {}), b["rows"].get(symbol, {})
        net_x = (
            x.get("net_pnl", Decimal(0))
            + x.get("transaction_cost", Decimal(0))
            + x.get("fx_cost", Decimal(0))
        )
        net_y = (
            y.get("net_pnl", Decimal(0))
            + y.get("transaction_cost", Decimal(0))
            + y.get("fx_cost", Decimal(0))
        )
        cost_x = x.get("transaction_cost", Decimal(0)) + x.get("fx_cost", Decimal(0))
        cost_y = y.get("transaction_cost", Decimal(0)) + y.get("fx_cost", Decimal(0))
        rows.append(
            {
                "symbol": symbol,
                "delta_net_pnl": _delta(net_x - cost_x, net_y - cost_y),
                "delta_transaction_fx": _delta(cost_x, cost_y),
                "delta_total_before_cost": _delta(net_x, net_y),
            }
        )
    left, right = sims[(period, arm, low)], sims[(period, arm, high)]
    sum_net = sum((Decimal(r["delta_net_pnl"]) for r in rows), Decimal(0))
    sum_cost = sum((Decimal(r["delta_transaction_fx"]) for r in rows), Decimal(0))
    sum_pre = sum((Decimal(r["delta_total_before_cost"]) for r in rows), Decimal(0))
    return {
        "period": period,
        "arm": arm,
        "from_cost": low,
        "to_cost": high,
        "symbols": rows,
        "aggregate_delta_net_pnl": format(sum_net, "f"),
        "aggregate_delta_transaction_fx": format(sum_cost, "f"),
        "aggregate_delta_pre_cost": format(sum_pre, "f"),
        "aggregate_reconciliation_residual": format(sum_pre - sum_cost - sum_net, "f"),
        "final_nav_delta_krw": _delta(
            left.metrics.final_equity_krw, right.metrics.final_equity_krw
        ),
        "turnover_delta_pp": _delta(
            left.metrics.turnover_pct, right.metrics.turnover_pct
        ),
        "max_drawdown_delta_pp": _delta(
            left.metrics.max_drawdown_pct, right.metrics.max_drawdown_pct
        ),
        "first_trade_path_mismatch": first_trade_path_mismatch(left, right),
        "final_holdings_difference": {
            s: [left_q, right_q]
            for s, left_q, right_q in _holdings(left, right)
            if left_q != right_q
        },
    }


def _holdings(
    left: PortfolioSimulation, right: PortfolioSimulation
) -> list[tuple[str, int, int]]:
    a = {p.symbol: p.quantity for p in left.positions}
    b = {p.symbol: p.quantity for p in right.positions}
    return [(s, a.get(s, 0), b.get(s, 0)) for s in sorted(set(a) | set(b))]


def _arm_row(
    period: str,
    cost: int,
    sims: dict[tuple[str, str, int], PortfolioSimulation],
    attrs: dict[tuple[str, str, int], dict[str, Any]],
) -> dict[str, Any]:
    left, right = sims[(period, "control", cost)], sims[(period, "variant", cost)]
    a, b = attrs[(period, "control", cost)], attrs[(period, "variant", cost)]
    symbols = sorted(set(a["rows"]) | set(b["rows"]))
    rows = []
    for symbol in symbols:
        x, y = a["rows"].get(symbol, {}), b["rows"].get(symbol, {})
        rows.append(
            {
                "symbol": symbol,
                "delta_net_pnl": _delta(
                    x.get("net_pnl", Decimal(0)),
                    y.get("net_pnl", Decimal(0)),
                ),
                "delta_transaction_fx": _delta(
                    x.get("transaction_cost", Decimal(0))
                    + x.get("fx_cost", Decimal(0)),
                    y.get("transaction_cost", Decimal(0))
                    + y.get("fx_cost", Decimal(0)),
                ),
            }
        )
    return {
        "period": period,
        "arm_comparison": "control_to_variant",
        "cost": cost,
        "symbols": rows,
        "final_nav_delta_krw": _delta(
            left.metrics.final_equity_krw, right.metrics.final_equity_krw
        ),
        "turnover_delta_pp": _delta(
            left.metrics.turnover_pct, right.metrics.turnover_pct
        ),
        "max_drawdown_delta_pp": _delta(
            left.metrics.max_drawdown_pct, right.metrics.max_drawdown_pct
        ),
        "first_trade_path_mismatch": first_trade_path_mismatch(left, right),
        "final_holdings_difference": {
            s: [x, y] for s, x, y in _holdings(left, right) if x != y
        },
    }


def _decomposition(
    period: str,
    high: int,
    sims: dict[tuple[str, str, int], PortfolioSimulation],
    attrs: dict[tuple[str, str, int], dict[str, Any]],
) -> dict[str, Any]:
    rows = []
    symbols = sorted(
        set(attrs[(period, "control", 1)]["rows"])
        | set(attrs[(period, "control", high)]["rows"])
        | set(attrs[(period, "variant", 1)]["rows"])
        | set(attrs[(period, "variant", high)]["rows"])
    )
    for symbol in symbols:
        values = []
        for arm in ("control", "variant"):
            lo = (
                attrs[(period, arm, 1)]["rows"]
                .get(symbol, {})
                .get("net_pnl", Decimal(0))
            )
            hi = (
                attrs[(period, arm, high)]["rows"]
                .get(symbol, {})
                .get("net_pnl", Decimal(0))
            )
            values.append(hi - lo)
        rows.append(
            {
                "symbol": symbol,
                "variant_minus_control_cost_delta": format(values[1] - values[0], "f"),
            }
        )
    c = (
        sims[(period, "control", high)].metrics.final_equity_krw
        - sims[(period, "control", 1)].metrics.final_equity_krw
    )
    v = (
        sims[(period, "variant", high)].metrics.final_equity_krw
        - sims[(period, "variant", 1)].metrics.final_equity_krw
    )
    control = _path_row(period, "control", 1, high, sims, attrs)
    variant = _path_row(period, "variant", 1, high, sims, attrs)
    return {
        "period": period,
        "high_cost": high,
        "symbols": rows,
        "variant_minus_control_cost_delta_krw": format(v - c, "f"),
        "variant_minus_control_delta_net_pnl": format(
            Decimal(variant["aggregate_delta_net_pnl"])
            - Decimal(control["aggregate_delta_net_pnl"]),
            "f",
        ),
        "variant_minus_control_delta_transaction_fx": format(
            Decimal(variant["aggregate_delta_transaction_fx"])
            - Decimal(control["aggregate_delta_transaction_fx"]),
            "f",
        ),
        "variant_minus_control_delta_pre_cost": format(
            Decimal(variant["aggregate_delta_pre_cost"])
            - Decimal(control["aggregate_delta_pre_cost"]),
            "f",
        ),
        "aggregate_reconciliation_residual": format(
            Decimal(variant["aggregate_reconciliation_residual"])
            - Decimal(control["aggregate_reconciliation_residual"]),
            "f",
        ),
        "control_cost_path": first_trade_path_mismatch(
            sims[(period, "control", 1)], sims[(period, "control", high)]
        ),
        "variant_cost_path": first_trade_path_mismatch(
            sims[(period, "variant", 1)], sims[(period, "variant", high)]
        ),
        "control_turnover_delta_pp": _delta(
            sims[(period, "control", 1)].metrics.turnover_pct,
            sims[(period, "control", high)].metrics.turnover_pct,
        ),
        "variant_turnover_delta_pp": _delta(
            sims[(period, "variant", 1)].metrics.turnover_pct,
            sims[(period, "variant", high)].metrics.turnover_pct,
        ),
        "control_mdd_delta_pp": _delta(
            sims[(period, "control", 1)].metrics.max_drawdown_pct,
            sims[(period, "control", high)].metrics.max_drawdown_pct,
        ),
        "variant_mdd_delta_pp": _delta(
            sims[(period, "variant", 1)].metrics.max_drawdown_pct,
            sims[(period, "variant", high)].metrics.max_drawdown_pct,
        ),
    }


def enrich_report(report: dict[str, Any]) -> dict[str, Any]:
    """Complete a saved report from its 32 comparison rows; performs no analysis."""
    with localcontext() as context:
        context.prec = 50
        paths = report.get("cost_comparisons")
        if not isinstance(paths, list) or len(paths) != 32:
            raise ValueError("saved report must contain exactly 32 comparisons")
        keys = [(r["period"], r["arm"], r["to_cost"]) for r in paths]
        if len(set(keys)) != len(keys):
            raise ValueError("saved report contains duplicate comparisons")
        for item in paths:
            for symbol_row in item.get("symbols", []):
                symbol_row.pop("cost_path_delta", None)
            residual = (
                Decimal(item["aggregate_delta_pre_cost"])
                - Decimal(item["aggregate_delta_transaction_fx"])
                - Decimal(item["aggregate_delta_net_pnl"])
            )
            if abs(residual) > TOLERANCE:
                raise ValueError(
                    "saved report aggregate reconciliation exceeds tolerance"
                )
            if item.get("symbols"):
                for field, aggregate in (
                    ("delta_net_pnl", "aggregate_delta_net_pnl"),
                    ("delta_transaction_fx", "aggregate_delta_transaction_fx"),
                    ("delta_total_before_cost", "aggregate_delta_pre_cost"),
                ):
                    total = sum(
                        (Decimal(row[field]) for row in item["symbols"]), Decimal(0)
                    )
                    if abs(total - Decimal(item[aggregate])) > TOLERANCE:
                        raise ValueError("saved report symbol sum mismatch")
            if (
                "final_nav_delta_krw" in item
                and abs(
                    Decimal(item["final_nav_delta_krw"])
                    - Decimal(item["aggregate_delta_net_pnl"])
                )
                > TOLERANCE
            ):
                raise ValueError("saved report NAV mismatch")
        index = dict(zip(keys, paths, strict=True))
        decomposition = []
        for period in PERIODS:
            for high in (2, 3):
                control = index[(period, "control", high)]
                variant = index[(period, "variant", high)]
                row = {"period": period, "high_cost": high}
                for name in (
                    "aggregate_delta_net_pnl",
                    "aggregate_delta_transaction_fx",
                    "aggregate_delta_pre_cost",
                ):
                    row[f"variant_minus_control_{name}"] = format(
                        Decimal(variant[name]) - Decimal(control[name]), "f"
                    )
                row["aggregate_reconciliation_residual"] = format(
                    Decimal(variant["aggregate_reconciliation_residual"])
                    - Decimal(control["aggregate_reconciliation_residual"]),
                    "f",
                )
                row["variant_turnover_delta_pp"] = variant["turnover_delta_pp"]
                row["control_turnover_delta_pp"] = control["turnover_delta_pp"]
                row["variant_mdd_delta_pp"] = variant["max_drawdown_delta_pp"]
                row["control_mdd_delta_pp"] = control["max_drawdown_delta_pp"]
                row["variant_cost_path"] = variant["first_trade_path_mismatch"]
                row["control_cost_path"] = control["first_trade_path_mismatch"]
                decomposition.append(row)
    report["variant_control_decomposition"] = decomposition
    report["unsupported"] = ["partial fills", "cancels", "rejects"]
    return report


def render_markdown(report: dict[str, Any]) -> str:
    """Render complete saved comparison tables without reading simulations."""
    lines = [
        "# Portfolio held-band cost-path attribution v1",
        "",
        "고정 입력의 비용 경로 회계 attribution입니다.",
        "",
        "## 비용 비교 32개",
        "",
        "| period | arm | from→to | Δnet | Δtransaction+FX | Δpre-cost | residual | turnover Δpp | MDD Δpp | path |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in report["cost_comparisons"]:
        lines.append(
            f"| {row['period']} | {row['arm']} | {row['from_cost']}→{row['to_cost']} | {row['aggregate_delta_net_pnl']} | {row['aggregate_delta_transaction_fx']} | {row['aggregate_delta_pre_cost']} | {row['aggregate_reconciliation_residual']} | {row['turnover_delta_pp']} | {row['max_drawdown_delta_pp']} | {row['first_trade_path_mismatch']} |"
        )
    lines.extend(
        [
            "",
            "## variant−control 분해 16개",
            "",
            "| period | high | Δnet | Δtransaction+FX | Δpre-cost | residual | turnover control/variant | MDD control/variant |",
            "|---|---:|---:|---:|---:|---:|---|---|",
        ]
    )
    for row in report["variant_control_decomposition"]:
        lines.append(
            f"| {row['period']} | {row['high_cost']} | {row['variant_minus_control_aggregate_delta_net_pnl']} | {row['variant_minus_control_aggregate_delta_transaction_fx']} | {row['variant_minus_control_aggregate_delta_pre_cost']} | {row['aggregate_reconciliation_residual']} | {row['control_turnover_delta_pp']}/{row['variant_turnover_delta_pp']} | {row['control_mdd_delta_pp']}/{row['variant_mdd_delta_pp']} |"
        )
    lines.extend(
        [
            "",
            "지원하지 않음: partial fills, cancels, rejects.",
            "causal effect 또는 pure-price effect를 주장하지 않습니다.",
        ]
    )
    return "\n".join(lines) + "\n"


def analyze(input_dir: Path, output_dir: Path) -> dict[str, Any]:
    with localcontext() as context:
        context.prec = 50
        sims = load_frozen(input_dir)
        attrs = {k: attribute_simulation(v, k[2]) for k, v in sims.items()}
        paths = [
            _path_row(p, a, low, high, sims, attrs)
            for p in PERIODS
            for a in ARMS
            for low, high in ((1, 2), (1, 3))
        ]
        decomposition = [
            _decomposition(p, c, sims, attrs) for p in PERIODS for c in (2, 3)
        ]
        report = {
            "run_id": "portfolio-held-band-cost-path-attribution-v1",
            "simulation_count": 48,
            "cost_comparisons": paths,
            "variant_control_decomposition": decomposition,
            "claims": [
                "cost-path accounting attribution; no causal or pure-price effect claim"
            ],
        }
        enriched = enrich_report(report)
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "report.json").write_text(
            json.dumps(
                _json_value(enriched), ensure_ascii=False, indent=2, sort_keys=True
            )
            + "\n",
            encoding="utf-8",
        )
    (output_dir / "report.md").write_text(render_markdown(enriched), encoding="utf-8")
    return enriched


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    analyze(args.input_dir, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
