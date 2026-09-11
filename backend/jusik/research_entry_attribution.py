"""Fixed-input accounting attribution for the unheld-entry experiment.

This module reads the frozen result bytes once, verifies their hashes, validates
each simulation through the portfolio models, and produces an accounting report.
It deliberately does not run a strategy or fetch data.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, date, datetime
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from jusik.research_portfolio_models import PortfolioSimulation

PRECISION = 50
TOLERANCE = Decimal("0.000001")
FEE_RATE = Decimal("0.001")
SLIPPAGE_RATE = Decimal("0.001")
RESULTS_SHA256 = "5c2de5987dd099de64736e1d5ebe9a14e25a43f089bc4a1dc60d924a645e7cc4"
PREREGISTRATION_SHA256 = (
    "9bf1a850a74a2c95a58f8b6097aa98bff6012a45eb2b887c9e653cf3352f74e7"
)
PERIODS = tuple([f"fold_{i}" for i in range(1, 8)] + ["continuous"])
ARMS = ("control", "variant")
COSTS = (1, 2)
CORE_FILES = (
    "research_portfolio_engine.py",
    "research_portfolio_models.py",
    "research_external_features.py",
    "research_risk.py",
)


def _decimal(value: Any, field: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except Exception as exc:  # pragma: no cover - defensive parse boundary
        raise ValueError(f"{field} is not a decimal") from exc
    if not result.is_finite():
        raise ValueError(f"{field} is non-finite")
    return result


def _close(actual: Decimal, expected: Decimal, label: str) -> None:
    if abs(actual - expected) > TOLERANCE:
        raise ValueError(f"{label} residual {actual - expected} exceeds tolerance")


def _read_hashed(path: Path, expected: str, label: str) -> tuple[bytes, Any]:
    body = path.read_bytes()
    actual = hashlib.sha256(body).hexdigest()
    if actual != expected:
        raise ValueError(f"{label} hash mismatch: {actual} != {expected}")
    try:
        return body, json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is not valid UTF-8 JSON") from exc


def _expected_artifacts(
    results: dict[str, Any], prereg: dict[str, Any]
) -> dict[str, str]:
    evaluations = results.get("evaluations")
    if not isinstance(evaluations, list) or len(evaluations) != 32:
        raise ValueError("results must contain exactly 32 evaluations")
    expected: dict[str, str] = {}
    for row in evaluations:
        if not isinstance(row, dict):
            raise ValueError("evaluation row must be an object")
        artifact, digest = row.get("artifact"), row.get("sha256")
        if not isinstance(artifact, str) or not isinstance(digest, str):
            raise ValueError("evaluation artifact hash is missing")
        if artifact in expected:
            raise ValueError(f"duplicate evaluation artifact: {artifact}")
        expected[artifact] = digest
    control_hashes = prereg.get("control_hashes")
    if not isinstance(control_hashes, dict):
        raise ValueError("frozen control hashes are missing")
    for artifact, digest in control_hashes.items():
        if artifact not in expected or expected[artifact] != digest:
            raise ValueError(f"control hash disagreement: {artifact}")
    return expected


def _artifact_key(name: str) -> tuple[str, str, int]:
    stem = name.removesuffix(".json")
    parts = stem.split("-")
    if len(parts) != 2 or parts[0] not in PERIODS:
        raise ValueError(f"unexpected artifact filename: {name}")
    period, arm_cost = parts
    if "_c" not in arm_cost:
        raise ValueError(f"unexpected artifact filename: {name}")
    arm, cost_text = arm_cost.rsplit("_c", 1)
    if arm not in ("b2", "variant") or cost_text not in ("1", "2"):
        raise ValueError(f"unexpected artifact filename: {name}")
    return period, ("control" if arm == "b2" else "variant"), int(cost_text)


def _validate_frozen_metadata(
    sim: PortfolioSimulation, row: dict[str, Any], prereg: dict[str, Any]
) -> None:
    period, arm, cost = _artifact_key(str(row["artifact"]))
    if (
        row.get("period") != period
        or row.get("arm") != arm
        or row.get("cost_multiplier") != cost
    ):
        raise ValueError(f"frozen row metadata disagrees with {row['artifact']}")
    frozen_periods = prereg.get("periods")
    if not isinstance(frozen_periods, list):
        raise ValueError("frozen periods are missing")
    periods = {
        str(item["name"]): item
        for item in frozen_periods
        if isinstance(item, dict) and "name" in item
    }
    frozen_period = periods.get(period)
    if (
        frozen_period is None
        or sim.period_start.isoformat() != frozen_period.get("start")
        or sim.period_end.isoformat() != frozen_period.get("end")
    ):
        raise ValueError(f"period metadata mismatch for {period}")
    candidate = prereg.get("candidate")
    if (
        not isinstance(candidate, dict)
        or sim.candidate.model_dump(mode="json") != candidate
    ):
        raise ValueError(f"candidate metadata mismatch for {period}")
    if sim.policy != prereg.get("policy"):
        raise ValueError(f"policy metadata mismatch for {period}")
    if not sim.complete or sim.incomplete_reasons:
        raise ValueError(f"incomplete simulation: {row['artifact']}")
    metric_names = (
        "initial_equity_krw",
        "final_equity_krw",
        "total_return_pct",
        "max_drawdown_pct",
        "trade_count",
        "transaction_cost_krw",
        "fx_cost_krw",
        "turnover_pct",
    )
    for name in metric_names:
        if name not in row:
            raise ValueError(f"frozen metric is missing: {name}")
        expected = _decimal(row[name], f"frozen {name}")
        actual = _decimal(getattr(sim.metrics, name), f"simulation {name}")
        _close(actual, expected, f"{row['artifact']} {name}")


def _symbols(sim: PortfolioSimulation) -> set[str]:
    result = set(sim.contributions_krw) | set(sim.split_cash_in_lieu_krw)
    result |= {trade.symbol for trade in sim.trades}
    result |= {position.symbol for position in sim.positions}
    return result


def _cost_parts(
    sim: PortfolioSimulation, cost: int
) -> tuple[dict[str, dict[str, Decimal]], dict[str, dict[str, int]]]:
    rate = SLIPPAGE_RATE * cost
    fee_rate = FEE_RATE * cost
    amounts: dict[str, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for trade in sim.trades:
        quantity = Decimal(trade.quantity)
        execution = quantity * trade.local_price * trade.fx_rate
        signed = execution if trade.side == "sell" else -execution
        raw_local = trade.local_price / (
            Decimal(1) - rate if trade.side == "sell" else Decimal(1) + rate
        )
        raw = quantity * raw_local * trade.fx_rate
        slippage = abs(raw - execution)
        fee = execution * fee_rate
        _close(
            _decimal(trade.notional_krw, "notional"),
            execution,
            f"{trade.symbol} execution notional",
        )
        _close(
            _decimal(trade.transaction_cost_krw, "transaction cost"),
            fee + slippage,
            f"{trade.symbol} transaction cost",
        )
        amounts[trade.symbol]["execution_notional"] += signed
        amounts[trade.symbol]["raw_notional"] += raw if trade.side == "sell" else -raw
        amounts[trade.symbol]["fee"] += fee
        amounts[trade.symbol]["slippage"] += slippage
        amounts[trade.symbol]["transaction_cost"] += fee + slippage
        amounts[trade.symbol]["fx_cost"] += trade.fx_cost_krw
        counts[trade.symbol]["trade_count"] += 1
    return amounts, counts


def attribute_simulation(
    sim: PortfolioSimulation, cost_multiplier: int
) -> dict[str, Any]:
    """Recompute symbol cashflows, terminal values, and residuals for one run."""
    with localcontext() as context:
        context.prec = PRECISION
        if not sim.equity:
            raise ValueError("equity series is empty")
        amounts, counts = _cost_parts(sim, cost_multiplier)
        rows: dict[str, dict[str, Any]] = {}
        for symbol in sorted(_symbols(sim)):
            item = amounts[symbol]
            terminal = Decimal(0)
            for position in sim.positions:
                if position.symbol == symbol:
                    terminal += (
                        Decimal(position.quantity)
                        * position.local_close
                        * position.fx_rate
                    )
                    _close(position.value_krw, terminal, f"{symbol} position value")
            split = _decimal(sim.split_cash_in_lieu_krw.get(symbol, 0), "split cash")
            cashflow = item["execution_notional"] - item["fee"] - item["fx_cost"]
            net = cashflow + terminal + split
            raw_net = (
                item["raw_notional"]
                - item["transaction_cost"]
                - item["fx_cost"]
                + terminal
                + split
            )
            _close(net, raw_net, f"{symbol} raw/execution accounting")
            stored = _decimal(sim.contributions_krw.get(symbol, 0), "contribution")
            _close(net, stored, f"{symbol} stored contribution")
            row = {
                "symbol": symbol,
                "execution_notional": item["execution_notional"],
                "signed_notional": item["raw_notional"],
                "fee": item["fee"],
                "slippage": item["slippage"],
                "transaction_cost": item["transaction_cost"],
                "fx_cost": item["fx_cost"],
                "terminal": terminal,
                "split_cash_in_lieu": split,
                "net_pnl": net,
                "trade_count": counts[symbol]["trade_count"],
            }
            rows[symbol] = row
        total_initial = _decimal(sim.metrics.initial_equity_krw, "initial equity")
        total_final = _decimal(sim.metrics.final_equity_krw, "final equity")
        total_nav = _decimal(sim.equity[-1].cash_krw, "ending cash") + sum(
            (
                _decimal(position.value_krw, "position value")
                for position in sim.positions
            ),
            Decimal(0),
        )
        _close(total_nav, total_final, "final cash plus holdings")
        _close(
            sum((row["net_pnl"] for row in rows.values()), Decimal(0)),
            total_final - total_initial,
            "sum PnL",
        )
        _close(
            sum((trade.transaction_cost_krw for trade in sim.trades), Decimal(0)),
            sim.metrics.transaction_cost_krw,
            "transaction costs",
        )
        _close(
            sum((trade.fx_cost_krw for trade in sim.trades), Decimal(0)),
            sim.metrics.fx_cost_krw,
            "FX costs",
        )
        residual = sum((row["net_pnl"] for row in rows.values()), Decimal(0)) - (
            total_final - total_initial
        )
        return {
            "rows": rows,
            "total_initial_equity": total_initial,
            "total_final_equity": total_final,
            "total_nav": total_nav,
            "residual": residual,
        }


def _monthly_portfolio(
    sim: PortfolioSimulation, attribution: dict[str, Any]
) -> list[dict[str, Any]]:
    """Build UTC month-end portfolio changes, retaining no-trade months."""
    points = sim.equity
    if not points:
        raise ValueError("equity series is empty")
    ordered = sorted(enumerate(points), key=lambda pair: (pair[1].at, pair[0]))
    if any(point.at.tzinfo is None for _, point in ordered):
        raise ValueError("equity timestamps must be timezone aware")
    by_month: dict[str, Any] = {}
    for _index, point in ordered:
        month = point.at.astimezone(UTC).strftime("%Y-%m")
        by_month[month] = point
    start_month = sim.period_start.strftime("%Y-%m")
    end_month = sim.period_end.strftime("%Y-%m")
    expected: list[str] = []
    cursor = date(sim.period_start.year, sim.period_start.month, 1)
    end = date(sim.period_end.year, sim.period_end.month, 1)
    while cursor <= end:
        expected.append(cursor.strftime("%Y-%m"))
        cursor = date(
            cursor.year + (cursor.month == 12),
            1 if cursor.month == 12 else cursor.month + 1,
            1,
        )
    if (
        set(expected) != set(by_month)
        or start_month not in by_month
        or end_month not in by_month
    ):
        raise ValueError("equity series has a missing UTC month")
    trades: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "trade_count": 0,
            "transaction_cost": Decimal(0),
            "fx_cost": Decimal(0),
        }
    )
    for trade in sim.trades:
        month = trade.executed_at.astimezone(UTC).strftime("%Y-%m")
        trades[month]["trade_count"] += 1
        trades[month]["transaction_cost"] += trade.transaction_cost_krw
        trades[month]["fx_cost"] += trade.fx_cost_krw
    result: list[dict[str, Any]] = []
    previous = _decimal(sim.metrics.initial_equity_krw, "initial equity")
    for month in expected:
        point = by_month[month]
        equity = _decimal(point.equity_krw, "monthly equity")
        data = trades[month]
        result.append(
            {
                "month": month,
                "equity": equity,
                "previous_equity": previous,
                "pnl": equity - previous,
                "trade_count": data["trade_count"],
                "transaction_cost": data["transaction_cost"],
                "fx_cost": data["fx_cost"],
            }
        )
        previous = equity
    _close(
        sum((row["pnl"] for row in result), Decimal(0)),
        _decimal(sim.metrics.final_equity_krw, "final")
        - _decimal(sim.metrics.initial_equity_krw, "initial"),
        "monthly PnL",
    )
    return result


def monthly_portfolio(
    sim: PortfolioSimulation, attribution: dict[str, Any]
) -> list[dict[str, Any]]:
    """Build monthly attribution using the module's fixed Decimal precision."""
    with localcontext() as context:
        context.prec = PRECISION
        return _monthly_portfolio(sim, attribution)


def _delta_rows(
    control: dict[str, Any], variant: dict[str, Any]
) -> list[dict[str, Any]]:
    symbols = sorted(set(control["rows"]) | set(variant["rows"]))
    output = []
    for symbol in symbols:
        c, v = control["rows"].get(symbol, {}), variant["rows"].get(symbol, {})
        row: dict[str, Any] = {"symbol": symbol}
        for field in (
            "net_pnl",
            "signed_notional",
            "execution_notional",
            "fee",
            "slippage",
            "transaction_cost",
            "fx_cost",
            "terminal",
            "split_cash_in_lieu",
            "trade_count",
        ):
            left, right = c.get(field, Decimal(0)), v.get(field, Decimal(0))
            row[f"control_{field}"] = left
            row[f"variant_{field}"] = right
            row[f"delta_{field}"] = right - left
        output.append(row)
    return output


def _concentration(
    rows: Iterable[dict[str, Any]], field: str = "delta_net_pnl"
) -> dict[str, Any]:
    values = [(row["symbol"], row[field]) for row in rows]
    positive = [(symbol, value) for symbol, value in values if value > 0]
    negative = [(symbol, value) for symbol, value in values if value < 0]

    def pick(
        items: list[tuple[str, Decimal]], denominator: Decimal
    ) -> dict[str, Any] | None:
        if not items or denominator == 0:
            return None
        symbol, value = sorted(items, key=lambda pair: (-pair[1], pair[0]))[0]
        return {"symbol": symbol, "value": value, "percent": value / denominator * 100}

    negative_result = pick(
        [(symbol, -value) for symbol, value in negative],
        sum((-value for _, value in negative), Decimal(0)),
    )
    if negative_result is not None:
        negative_result["value"] = -negative_result["value"]
    return {
        "positive": pick(positive, sum((value for _, value in positive), Decimal(0))),
        "negative": negative_result,
    }


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def _money(value: Decimal) -> str:
    with localcontext() as context:
        context.prec = PRECISION
        return format(value.quantize(Decimal("0.01")), ",f")


def _analyze(input_dir: Path) -> dict[str, Any]:
    """Read and analyze all frozen inputs, without writing any output."""
    input_dir = input_dir.resolve()
    results_body, results = _read_hashed(
        input_dir / "results.json", RESULTS_SHA256, "results.json"
    )
    prereg_body, prereg = _read_hashed(
        input_dir / "preregistration.json",
        PREREGISTRATION_SHA256,
        "preregistration.json",
    )
    if (
        results.get("specification_sha256") != PREREGISTRATION_SHA256
        or prereg.get("evaluation_count") != 32
    ):
        raise ValueError("frozen results/preregistration identity mismatch")
    if set(prereg.get("core_hashes", {})) != set(CORE_FILES):
        raise ValueError("frozen core source hash manifest is incomplete")
    for name in CORE_FILES:
        source = Path(__file__).with_name(name)
        expected_hash = prereg["core_hashes"][name]
        if (
            not source.is_file()
            or hashlib.sha256(source.read_bytes()).hexdigest() != expected_hash
        ):
            raise ValueError(f"current source differs from frozen hash: {name}")
    expected = _expected_artifacts(results, prereg)
    expected_names = {
        f"{period}-{'b2' if arm == 'control' else 'variant'}_c{cost}.json"
        for period in PERIODS
        for arm in ARMS
        for cost in COSTS
    }
    if set(expected) != expected_names:
        raise ValueError("the frozen result set is not exactly 32 artifacts")
    frozen_rows = {str(row["artifact"]): row for row in results["evaluations"]}
    simulations: dict[tuple[str, str, int], PortfolioSimulation] = {}
    accounting: dict[tuple[str, str, int], dict[str, Any]] = {}
    monthly: dict[tuple[str, str, int], list[dict[str, Any]]] = {}
    for name in sorted(expected_names):
        _body, payload = _read_hashed(
            input_dir / "simulations" / name, expected[name], name
        )
        try:
            simulation = PortfolioSimulation.model_validate(payload)
        except ValidationError as exc:
            raise ValueError(f"invalid PortfolioSimulation {name}: {exc}") from exc
        row = frozen_rows[name]
        _validate_frozen_metadata(simulation, row, prereg)
        key = _artifact_key(name)
        simulations[key] = simulation
        accounting[key] = attribute_simulation(simulation, key[2])
        monthly[key] = monthly_portfolio(simulation, accounting[key])
    pairs: list[dict[str, Any]] = []
    symbol_rows: list[dict[str, Any]] = []
    monthly_rows: list[dict[str, Any]] = []
    for period in PERIODS:
        for cost in COSTS:
            key_c, key_v = (period, "control", cost), (period, "variant", cost)
            deltas = _delta_rows(accounting[key_c], accounting[key_v])
            for row in deltas:
                symbol_rows.append({"period": period, "cost_multiplier": cost, **row})
            control_month, variant_month = monthly[key_c], monthly[key_v]
            if [row["month"] for row in control_month] != [
                row["month"] for row in variant_month
            ]:
                raise ValueError(f"monthly month mismatch in {period} c{cost}")
            for c_month, v_month in zip(control_month, variant_month):
                monthly_rows.append(
                    {
                        "period": period,
                        "cost_multiplier": cost,
                        "month": c_month["month"],
                        "control_equity": c_month["equity"],
                        "variant_equity": v_month["equity"],
                        "delta_equity": v_month["equity"] - c_month["equity"],
                        "control_pnl": c_month["pnl"],
                        "variant_pnl": v_month["pnl"],
                        "delta_pnl": v_month["pnl"] - c_month["pnl"],
                        "control_trade_count": c_month["trade_count"],
                        "variant_trade_count": v_month["trade_count"],
                        "delta_trade_count": v_month["trade_count"]
                        - c_month["trade_count"],
                        "control_transaction_cost": c_month["transaction_cost"],
                        "variant_transaction_cost": v_month["transaction_cost"],
                        "delta_transaction_cost": v_month["transaction_cost"]
                        - c_month["transaction_cost"],
                        "control_fx_cost": c_month["fx_cost"],
                        "variant_fx_cost": v_month["fx_cost"],
                        "delta_fx_cost": v_month["fx_cost"] - c_month["fx_cost"],
                    }
                )
            c_metrics, v_metrics = (
                simulations[key_c].metrics,
                simulations[key_v].metrics,
            )
            pairs.append(
                {
                    "period": period,
                    "cost_multiplier": cost,
                    "control_final_equity": c_metrics.final_equity_krw,
                    "variant_final_equity": v_metrics.final_equity_krw,
                    "delta_final_equity": v_metrics.final_equity_krw
                    - c_metrics.final_equity_krw,
                    "delta_pnl": v_metrics.final_equity_krw
                    - v_metrics.initial_equity_krw
                    - (c_metrics.final_equity_krw - c_metrics.initial_equity_krw),
                    "delta_trade_count": v_metrics.trade_count - c_metrics.trade_count,
                    "delta_transaction_cost": v_metrics.transaction_cost_krw
                    - c_metrics.transaction_cost_krw,
                    "delta_fx_cost": v_metrics.fx_cost_krw - c_metrics.fx_cost_krw,
                    "symbol_concentration": _concentration(deltas),
                }
            )
    return {
        "input": {
            "results_sha256": hashlib.sha256(results_body).hexdigest(),
            "preregistration_sha256": hashlib.sha256(prereg_body).hexdigest(),
            "artifact_count": len(expected),
            "input_dir": str(input_dir),
            "fee_rate": FEE_RATE,
            "slippage_rate": SLIPPAGE_RATE,
            "tolerance_krw": TOLERANCE,
        },
        "pairs": pairs,
        "symbol_rows": symbol_rows,
        "monthly_rows": monthly_rows,
        "residuals": {
            f"{period}:{arm}:c{cost}": accounting[(period, arm, cost)]["residual"]
            for period in PERIODS
            for arm in ARMS
            for cost in COSTS
        },
        "source_hashes": prereg.get("core_hashes", {}),
    }


def analyze(input_dir: Path) -> dict[str, Any]:
    """Analyze frozen inputs under a deterministic Decimal context."""
    with localcontext() as context:
        context.prec = PRECISION
        return _analyze(input_dir)


def _write_exclusive(path: Path, body: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(body)
            output.flush()
            os.fsync(output.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = list(rows[0]) if rows else []
    with path.open("x", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _json_value(row[field]) for field in fields})


def _report(result: dict[str, Any]) -> str:
    lines = [
        "# Entry attribution 회계 분석",
        "",
        "고정 32개 simulation artifact를 재검산한 결과입니다.",
        "",
        "이 결과는 추가 매매의 회계상 손익 귀속이며, 인과적 profit attribution이나 "
        "MDD 원인 분석이 아닙니다.",
        "",
        "## 16개 pair 요약",
        "",
        "| 기간 | cost | 최종 NAV 변화(KRW) | PnL 변화(KRW) | 거래수 변화 | "
        "transaction cost 변화(KRW) | FX cost 변화(KRW) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for pair in result["pairs"]:
        lines.append(
            f"| {pair['period']} | {pair['cost_multiplier']} | "
            f"{_money(pair['delta_final_equity'])} | "
            f"{_money(pair['delta_pnl'])} | {pair['delta_trade_count']} | "
            f"{_money(pair['delta_transaction_cost'])} | "
            f"{_money(pair['delta_fx_cost'])} |"
        )
    continuous = next(
        pair
        for pair in result["pairs"]
        if pair["period"] == "continuous" and pair["cost_multiplier"] == 1
    )
    lines += ["", "## continuous c1 concentration", ""]
    for kind in ("positive", "negative"):
        item = continuous["symbol_concentration"][kind]
        lines.append(
            f"- {kind}: "
            + (
                "없음"
                if item is None
                else (
                    f"{item['symbol']} {_money(item['value'])} KRW "
                    f"({_money(item['percent'])}%)"
                )
            )
        )
    lines.append(
        "- concentration 분모: positive는 양수 delta 합, "
        "negative는 음수 delta 절대값 합"
    )
    for cost in COSTS:
        continuous_rows = [
            row
            for row in result["symbol_rows"]
            if row["period"] == "continuous" and row["cost_multiplier"] == cost
        ]
        positive = sorted(
            (row for row in continuous_rows if row["delta_net_pnl"] > 0),
            key=lambda row: (-row["delta_net_pnl"], row["symbol"]),
        )
        negative = sorted(
            (row for row in continuous_rows if row["delta_net_pnl"] < 0),
            key=lambda row: (row["delta_net_pnl"], row["symbol"]),
        )
        positive_total = sum((row["delta_net_pnl"] for row in positive), Decimal(0))
        negative_total = sum((-row["delta_net_pnl"] for row in negative), Decimal(0))
        lines.append(
            f"- continuous c{cost} positive top3 (분모 {_money(positive_total)}): "
            + "; ".join(
                f"{row['symbol']} {_money(row['delta_net_pnl'])}"
                for row in positive[:3]
            )
        )
        lines.append(
            f"- continuous c{cost} negative top3 "
            f"(절대값 분모 {_money(negative_total)}): "
            + "; ".join(
                f"{row['symbol']} {_money(row['delta_net_pnl'])}"
                for row in negative[:3]
            )
        )
    adverse = [pair for pair in result["pairs"] if pair["period"] == "fold_1"]
    lines += ["", "## fold_1 adverse comparison", ""]
    for pair in adverse:
        lines.append(
            f"- c{pair['cost_multiplier']}: delta PnL "
            f"{_money(pair['delta_pnl'])} KRW, delta final NAV "
            f"{_money(pair['delta_final_equity'])} KRW"
        )
    fold_rows = [
        row
        for row in result["symbol_rows"]
        if row["period"] == "fold_1" and row["cost_multiplier"] == 1
    ]
    fold_positive = sorted(
        (row for row in fold_rows if row["delta_net_pnl"] > 0),
        key=lambda row: (-row["delta_net_pnl"], row["symbol"]),
    )
    fold_negative = sorted(
        (row for row in fold_rows if row["delta_net_pnl"] < 0),
        key=lambda row: (row["delta_net_pnl"], row["symbol"]),
    )
    lines.append(
        "- fold_1 c1 positive offset: "
        + "; ".join(
            f"{row['symbol']} {_money(row['delta_net_pnl'])}"
            for row in fold_positive[:3]
        )
    )
    lines.append(
        "- fold_1 c1 adverse: "
        + "; ".join(
            f"{row['symbol']} {_money(row['delta_net_pnl'])}"
            for row in fold_negative[:3]
        )
    )
    worst_month = min(
        (
            row
            for row in result["monthly_rows"]
            if row["period"] == "continuous" and row["cost_multiplier"] == 1
        ),
        key=lambda row: (row["delta_pnl"], row["month"]),
    )
    lines.append(
        f"- fold/continuous monthly worst (continuous c1): {worst_month['month']} "
        f"{_money(worst_month['delta_pnl'])} KRW"
    )
    lines += [
        "",
        "## 월별 변화",
        "",
        "월별 equity는 UTC 기준 각 월의 마지막 관측값을 사용했으며, "
        "거래가 없는 달도 포함했습니다.",
    ]
    for row in result["monthly_rows"]:
        if row["period"] == "continuous" and row["cost_multiplier"] == 1:
            lines.append(
                f"- {row['month']}: delta PnL {_money(row['delta_pnl'])} KRW, "
                f"delta trades {row['delta_trade_count']}"
            )
    lines += [
        "",
        "회계식은 체결 notional, 수수료, 내재 슬리피지, FX 비용, terminal "
        "valuation, split cash를 분리해 검증했습니다. 배당 데이터는 없으므로 "
        "price return만 포함합니다.",
    ]
    return "\n".join(lines) + "\n"


def write_outputs(result: dict[str, Any], output_dir: Path) -> None:
    if output_dir.exists() and (not output_dir.is_dir() or any(output_dir.iterdir())):
        raise ValueError("output directory must be new or empty")
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "formula": (
            "signed_raw_notional - transaction_cost - fx_cost + terminal + "
            "split_cash_in_lieu; equivalent to signed_execution_notional - fee "
            "- fx_cost + terminal + split_cash_in_lieu"
        ),
        **result,
    }
    _write_exclusive(
        output_dir / "attribution.json",
        (
            json.dumps(_json_value(payload), ensure_ascii=False, indent=2) + "\n"
        ).encode(),
    )
    _write_csv(output_dir / "symbol-attribution.csv", result["symbol_rows"])
    _write_csv(output_dir / "monthly-attribution.csv", result["monthly_rows"])
    _write_exclusive(output_dir / "report.md", _report(result).encode())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    write_outputs(analyze(args.input_dir), args.output_dir)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
