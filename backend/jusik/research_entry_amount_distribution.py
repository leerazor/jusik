# ruff: noqa: E501

"""Audit the frozen unheld-entry simulations' buy amount distribution.

This is a standalone, read-only analysis.  It validates the frozen JSON bytes,
replays quantities with corporate actions, and writes only analysis artifacts
under the requested output directory.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from collections import defaultdict
from datetime import date, datetime
from decimal import ROUND_FLOOR, Decimal, localcontext
from pathlib import Path
from typing import Any

DEFAULT_INPUT = Path(
    "/home/kwl/.local/share/jusik/portfolio-audit/"
    "20260911T132132Z-worktree-development/unheld-entry-real32"
)
DEFAULT_MANIFEST = Path(
    "/home/kwl/.local/share/jusik/portfolio-audit/"
    "20260911T060908Z-rebalance-band/source-manifest.json"
)
RESULTS_SHA256 = "5c2de5987dd099de64736e1d5ebe9a14e25a43f089bc4a1dc60d924a645e7cc4"
PREREG_SHA256 = "9bf1a850a74a2c95a58f8b6097aa98bff6012a45eb2b887c9e653cf3352f74e7"
MANIFEST_SHA256 = "1a2934466efa12c09d08e7792b1a5e4b7c0c880d2aaabab9b25919bd0ec5c825"
INPUT_HASH = "82f31dd7d63e0a73cb44e167080a7e3f6dda90a3385fb5a72daf8bb8bbc378bf"
PERIODS = tuple([f"fold_{i}" for i in range(1, 8)] + ["continuous"])
ARMS = ("control", "variant")
COSTS = (1, 2)
TOLERANCE = Decimal("0.000001")
BUCKETS = (
    ("<10000", None, Decimal(10000)),
    ("[10000,100000)", Decimal(10000), Decimal(100000)),
    ("[100000,1000000)", Decimal(100000), Decimal(1000000)),
    ("[1000000,10000000)", Decimal(1000000), Decimal(10000000)),
    (">=10000000", Decimal(10000000), None),
)


def sha256_bytes(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def read_json_hashed(path: Path, expected: str, label: str) -> tuple[bytes, Any]:
    body = path.read_bytes()
    actual = sha256_bytes(body)
    if actual != expected:
        raise ValueError(f"{label} hash mismatch: {actual} != {expected}")
    try:
        return body, json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is not UTF-8 JSON") from exc


def decimal(value: Any, label: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except Exception as exc:  # pragma: no cover - defensive boundary
        raise ValueError(f"{label} is not decimal") from exc
    if not result.is_finite():
        raise ValueError(f"{label} is not finite")
    return result


def close(actual: Decimal, expected: Decimal, label: str) -> None:
    if abs(actual - expected) > TOLERANCE:
        raise ValueError(f"{label} residual {actual - expected} exceeds tolerance")


def artifact_key(name: str) -> tuple[str, str, int]:
    stem = name.removesuffix(".json")
    period, arm_cost = stem.split("-", 1)
    if period not in PERIODS or "_c" not in arm_cost:
        raise ValueError(f"unexpected artifact filename: {name}")
    arm_text, cost_text = arm_cost.rsplit("_c", 1)
    if arm_text not in ("b2", "variant") or cost_text not in ("1", "2"):
        raise ValueError(f"unexpected artifact filename: {name}")
    return period, ("control" if arm_text == "b2" else "variant"), int(cost_text)


def nearest_rank(values: list[Decimal], percentile: int) -> Decimal | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = math.ceil(Decimal(percentile) * len(ordered) / Decimal(100))
    return ordered[rank - 1]


def bucket_counts(values: list[Decimal]) -> dict[str, int]:
    counts = {label: 0 for label, _low, _high in BUCKETS}
    for value in values:
        if not value.is_finite() or value <= 0:
            raise ValueError(f"amount must be finite and positive: {value}")
        for label, low, high in BUCKETS:
            if (low is None or value >= low) and (high is None or value < high):
                counts[label] += 1
                break
        else:  # pragma: no cover - bucket definitions cover all finite values
            raise ValueError(f"amount does not fit a bucket: {value}")
    return counts


def bucket_sums(values: list[Decimal]) -> dict[str, Decimal]:
    sums = {label: Decimal(0) for label, _low, _high in BUCKETS}
    for value in values:
        if not value.is_finite() or value <= 0:
            raise ValueError(f"amount must be finite and positive: {value}")
        for label, low, high in BUCKETS:
            if (low is None or value >= low) and (high is None or value < high):
                sums[label] += value
                break
    return sums


def summarize(values: list[Decimal]) -> dict[str, Any]:
    ordered = sorted(values)
    total = sum(ordered, Decimal(0))
    counts = bucket_counts(ordered)
    sums = bucket_sums(ordered)
    if sum(counts.values()) != len(ordered) or sum(sums.values(), Decimal(0)) != total:
        raise ValueError("bucket count/sum reconciliation failed")
    return {
        "count": len(ordered),
        "sum_krw": format(total, "f"),
        "min_krw": format(ordered[0], "f") if ordered else None,
        "max_krw": format(ordered[-1], "f") if ordered else None,
        "p25_krw": _format_or_none(nearest_rank(ordered, 25)),
        "p50_krw": _format_or_none(nearest_rank(ordered, 50)),
        "p75_krw": _format_or_none(nearest_rank(ordered, 75)),
        "p90_krw": _format_or_none(nearest_rank(ordered, 90)),
        "buckets": counts,
        "bucket_sums_krw": {label: format(value, "f") for label, value in sums.items()},
    }


def _format_or_none(value: Decimal | None) -> str | None:
    return format(value, "f") if value is not None else None


def report_money(value: Any) -> str:
    if value is None:
        return "null"
    with localcontext() as context:
        context.prec = 50
        return format(decimal(value, "report amount").quantize(Decimal("0.01")), ",f")


def action_map(
    frozen_input: dict[str, Any],
) -> tuple[dict[str, list[tuple[date, Decimal]]], list[dict[str, Any]]]:
    actions: dict[str, list[tuple[date, Decimal]]] = defaultdict(list)
    all_actions: list[dict[str, Any]] = []
    snapshots = frozen_input.get("instruments")
    if not isinstance(snapshots, list) or len(snapshots) != 16:
        raise ValueError("frozen input must contain 16 instrument snapshots")
    symbols: set[str] = set()
    for snapshot in snapshots:
        items = snapshot.get("instruments")
        if not isinstance(items, list) or len(items) != 1:
            raise ValueError("each instrument snapshot must contain one instrument")
        instrument = items[0].get("instrument", {})
        symbol = instrument.get("symbol")
        if not isinstance(symbol, str) or not symbol or symbol in symbols:
            raise ValueError(f"invalid or duplicate source symbol: {symbol}")
        symbols.add(symbol)
        raw_actions = snapshot.get("corporate_actions", [])
        if not isinstance(raw_actions, list):
            raise TypeError(f"corporate actions are not a list for {symbol}")
        for raw in raw_actions:
            if raw.get("kind") != "split":
                raise ValueError(f"unsupported corporate action for {symbol}: {raw}")
            action_date = date.fromisoformat(str(raw["date"]))
            factor = decimal(raw["numerator"], f"{symbol} split numerator") / decimal(
                raw["denominator"], f"{symbol} split denominator"
            )
            if factor <= 0:
                raise ValueError(f"non-positive split factor for {symbol}")
            actions[symbol].append((action_date, factor))
            all_actions.append(
                {
                    "symbol": symbol,
                    "date": action_date.isoformat(),
                    "factor": format(factor, "f"),
                }
            )
        actions[symbol].sort()
    if len(all_actions) != 2:
        raise ValueError(f"expected 2 corporate actions, found {len(all_actions)}")
    return dict(actions), sorted(all_actions, key=lambda x: (x["date"], x["symbol"]))


def replay(
    simulation: Any,
    actions: dict[str, list[tuple[date, Decimal]]],
    artifact: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    start = simulation.period_start
    end = simulation.period_end
    in_period: dict[str, list[tuple[date, Decimal]]] = {
        symbol: [(day, factor) for day, factor in rows if start <= day <= end]
        for symbol, rows in actions.items()
    }
    positions: defaultdict[str, int] = defaultdict(int)
    indexes: defaultdict[str, int] = defaultdict(int)
    events: list[dict[str, Any]] = []

    def apply_through(day: date) -> list[dict[str, Any]]:
        applied: list[dict[str, Any]] = []
        for symbol, rows in in_period.items():
            index = indexes[symbol]
            while index < len(rows) and rows[index][0] <= day:
                action_day, factor = rows[index]
                before = positions[symbol]
                after_decimal = (Decimal(before) * factor).to_integral_value(
                    rounding=ROUND_FLOOR
                )
                after = int(after_decimal)
                positions[symbol] = after
                applied.append(
                    {
                        "symbol": symbol,
                        "date": action_day.isoformat(),
                        "factor": format(factor, "f"),
                        "before_quantity": before,
                        "after_quantity": after,
                    }
                )
                index += 1
            indexes[symbol] = index
        return applied

    ordered = sorted(
        enumerate(simulation.trades), key=lambda item: (item[1].executed_at, item[0])
    )
    for original_index, trade in ordered:
        applied = apply_through(trade.executed_at.date())
        quantity = decimal(trade.quantity, f"{artifact} trade quantity")
        if quantity <= 0 or quantity != quantity.to_integral_value():
            raise ValueError(
                f"invalid quantity in {artifact} trade {original_index}: {quantity}"
            )
        qty = int(quantity)
        symbol = trade.symbol
        before = positions[symbol]
        side = str(trade.side)
        if side == "sell":
            if qty > before:
                raise ValueError(
                    f"oversell in {artifact} trade {original_index}: {symbol} {qty}>{before}"
                )
            positions[symbol] = before - qty
            continue
        if side != "buy":
            raise ValueError(f"unsupported side in {artifact}: {side}")
        execution = (
            quantity
            * decimal(trade.local_price, "local price")
            * decimal(trade.fx_rate, "fx rate")
        )
        notional = decimal(trade.notional_krw, "notional_krw")
        close(execution, notional, f"{artifact} {symbol} notional")
        classification = "new_entry" if before == 0 else "additional_buy"
        after = before + qty
        positions[symbol] = after
        events.append(
            {
                "artifact": artifact,
                "trade_index": original_index,
                "executed_at": trade.executed_at.isoformat(),
                "symbol": symbol,
                "classification": classification,
                "quantity": qty,
                "amount_krw": format(notional, "f"),
                "pre_quantity": before,
                "post_quantity": after,
                "corporate_actions_applied": applied,
            }
        )
    final_applied = apply_through(end)
    if final_applied:
        # A split after the last trade is allowed, but is reflected in final reconciliation.
        pass
    expected = {
        position.symbol: position.quantity
        for position in simulation.positions
        if position.quantity > 0
    }
    actual = {
        symbol: quantity for symbol, quantity in positions.items() if quantity > 0
    }
    if actual != expected:
        raise ValueError(
            f"final position mismatch in {artifact}: tracked={actual}, expected={expected}"
        )
    return events, {
        "final_positions": actual,
        "corporate_actions_applied_at_end": final_applied,
    }


def flatten_summary(row: dict[str, Any]) -> dict[str, Any]:
    output = {
        k: v
        for k, v in row.items()
        if k not in ("all_buy", "new_entry", "additional_buy")
    }
    for kind in ("all_buy", "new_entry", "additional_buy"):
        for key, value in row[kind].items():
            if key in ("buckets", "bucket_sums_krw"):
                suffix = "count" if key == "buckets" else "sum_krw"
                for bucket, count in value.items():
                    output[f"{kind}_{bucket}_{suffix}"] = count
            else:
                output[f"{kind}_{key}"] = value
    return output


def analyze(input_dir: Path, manifest_path: Path) -> dict[str, Any]:
    # Read each frozen byte stream once; all downstream validation uses these parsed values.
    results_body, results = read_json_hashed(
        input_dir / "results.json", RESULTS_SHA256, "results.json"
    )
    prereg_body, prereg = read_json_hashed(
        input_dir / "preregistration.json", PREREG_SHA256, "preregistration.json"
    )
    manifest_body, manifest = read_json_hashed(
        manifest_path, MANIFEST_SHA256, "source-manifest.json"
    )
    if (
        prereg.get("evaluation_count") != 32
        or prereg.get("prior_source_hashes", {}).get("source-manifest.json")
        != MANIFEST_SHA256
    ):
        raise ValueError("preregistration/source-manifest identity mismatch")
    if manifest.get("input_hash") != INPUT_HASH:
        raise ValueError("source-manifest input hash mismatch")
    if len(manifest.get("frozen_input", {}).get("instruments", [])) != 16:
        raise ValueError("source-manifest frozen input instrument count mismatch")
    if (
        results.get("specification_sha256") != PREREG_SHA256
        or results.get("all_complete") is not True
    ):
        raise ValueError("frozen results identity/integrity check failed")
    expected_names = {
        f"{period}-{'b2' if arm == 'control' else 'variant'}_c{cost}.json"
        for period in PERIODS
        for arm in ARMS
        for cost in COSTS
    }
    rows = results.get("evaluations")
    if (
        not isinstance(rows, list)
        or {str(row.get("artifact")) for row in rows} != expected_names
    ):
        raise ValueError("results must contain exactly the expected 32 artifacts")
    frozen_rows = {str(row["artifact"]): row for row in rows}
    actions, action_list = action_map(manifest["frozen_input"])
    from jusik.research_entry_attribution import attribute_simulation
    from jusik.research_portfolio_models import PortfolioSimulation

    all_events: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    accounting_residuals: dict[str, Any] = {}
    artifact_hashes: dict[str, str] = {}
    for artifact in sorted(expected_names):
        expected_hash = str(frozen_rows[artifact]["sha256"])
        body, payload = read_json_hashed(
            input_dir / "simulations" / artifact, expected_hash, artifact
        )
        artifact_hashes[artifact] = sha256_bytes(body)
        try:
            simulation = PortfolioSimulation.model_validate(payload)
        except Exception as exc:
            raise ValueError(f"invalid PortfolioSimulation {artifact}: {exc}") from exc
        period, arm, cost = artifact_key(artifact)
        row = frozen_rows[artifact]
        if (row.get("period"), row.get("arm"), row.get("cost_multiplier")) != (
            period,
            arm,
            cost,
        ):
            raise ValueError(f"evaluation metadata mismatch: {artifact}")
        if row.get("actual_unheld_entry_count") is None:
            raise ValueError(f"actual_unheld_entry_count missing: {artifact}")
        accounting = attribute_simulation(simulation, cost)
        accounting_residuals[artifact] = _json_safe(accounting["residual"])
        events, replay_meta = replay(simulation, actions, artifact)
        new_values = [
            decimal(event["amount_krw"], "new amount")
            for event in events
            if event["classification"] == "new_entry"
        ]
        additional_values = [
            decimal(event["amount_krw"], "additional amount")
            for event in events
            if event["classification"] == "additional_buy"
        ]
        all_values = new_values + additional_values
        if len(new_values) != int(row["actual_unheld_entry_count"]):
            raise ValueError(
                f"entry count mismatch in {artifact}: {len(new_values)} != {row['actual_unheld_entry_count']}"
            )
        if len(all_values) != sum(
            1 for trade in simulation.trades if trade.side == "buy"
        ):
            raise ValueError(f"BUY count mismatch in {artifact}")
        for event in events:
            event.update({"period": period, "arm": arm, "cost_multiplier": cost})
        all_events.extend(events)
        buy_sum = sum(all_values, Decimal(0))
        trade_sum = sum(
            (
                decimal(trade.notional_krw, "buy notional")
                for trade in simulation.trades
                if trade.side == "buy"
            ),
            Decimal(0),
        )
        close(buy_sum, trade_sum, f"{artifact} BUY amount sum")
        summary = {
            "period": period,
            "arm": arm,
            "cost_multiplier": cost,
            "artifact": artifact,
            "all_buy": summarize(all_values),
            "new_entry": summarize(new_values),
            "additional_buy": summarize(additional_values),
            "buy_count_reconciled": True,
            "buy_sum_reconciled": True,
            "actual_unheld_entry_count": len(new_values),
            "final_positions": replay_meta["final_positions"],
        }
        summaries.append(summary)
    return {
        "metadata": {
            "input_dir": str(input_dir.resolve()),
            "source_manifest": str(manifest_path.resolve()),
            "results_sha256": sha256_bytes(results_body),
            "preregistration_sha256": sha256_bytes(prereg_body),
            "source_manifest_sha256": sha256_bytes(manifest_body),
            "source_input_hash": manifest["input_hash"],
            "artifact_count": len(artifact_hashes),
            "instrument_count": 16,
            "corporate_action_count": len(action_list),
            "periods": list(PERIODS),
            "arms": list(ARMS),
            "cost_multipliers": list(COSTS),
            "quantile_method": "nearest-rank; rank=ceil(p*n), one-indexed",
            "amount_definition": "BUY execution notional in KRW (quantity * local_price * fx_rate), validated against notional_krw",
            "buckets_krw": [label for label, _low, _high in BUCKETS],
        },
        "corporate_actions": action_list,
        "artifact_hashes": artifact_hashes,
        "accounting_residuals": accounting_residuals,
        "summaries": summaries,
        "buy_events": all_events,
    }


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def write_outputs(
    result: dict[str, Any], output_dir: Path, allow_overwrite: bool = False
) -> None:
    if output_dir.exists() and any(output_dir.iterdir()) and not allow_overwrite:
        raise ValueError(
            "output directory must be new or empty; use a fresh directory for reproducibility"
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "distribution.json").write_text(
        json.dumps(_json_safe(result), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary_rows = [flatten_summary(row) for row in result["summaries"]]
    with (output_dir / "distribution.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        fields = list(summary_rows[0])
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in summary_rows:
            writer.writerow(
                {
                    field: json.dumps(value, ensure_ascii=False)
                    if isinstance(value, (dict, list))
                    else value
                    for field, value in row.items()
                }
            )
    event_fields = [
        "period",
        "arm",
        "cost_multiplier",
        "artifact",
        "trade_index",
        "executed_at",
        "symbol",
        "classification",
        "quantity",
        "amount_krw",
        "pre_quantity",
        "post_quantity",
        "corporate_actions_applied",
    ]
    with (output_dir / "buy-events.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=event_fields)
        writer.writeheader()
        for event in result["buy_events"]:
            writer.writerow(
                {
                    field: json.dumps(event[field], ensure_ascii=False)
                    if field == "corporate_actions_applied"
                    else event[field]
                    for field in event_fields
                }
            )
    lines = [
        "# 진입 금액 분포 감사 보고서",
        "",
        "- Task: `entry-amount-distribution-v1`",
        "- Attempt: `5ed7695cc0e84c788f5985c9bf22ef3b`",
        "- 상태: 고정 입력에 대한 재현 가능한 읽기 전용 분석",
        "",
        "고정된 32개 결과(8기간 × 2 arm × 2 cost)를 읽기 전용으로 검증하고, 각 BUY를 매수 직전 수량으로 `new_entry`(0)와 `additional_buy`(양수)로 분리했습니다. 32개 strata는 pooling하지 않았습니다.",
        "",
        "모든 32개 strata에서 PortfolioSimulation 모델 검증과 기존 회계 attribution 검증을 통과했고, 16개 입력 종목과 2개 split corporate action을 적용한 최종 보유수량이 결과와 일치했습니다. oversell은 0으로 clamp하지 않고 오류로 중단합니다.",
        "금액은 수량 × local price × FX의 BUY 체결 notional(KRW)이며, 수수료와 FX 비용은 제외하고 체결 가격에 반영된 슬리피지는 포함합니다.",
        "",
        "## 연속 기간 핵심 결과",
        "",
        "| arm | cost | BUY n | BUY 합계(KRW) | 신규 진입 n | 신규 합계(KRW) | 추가 매수 n | 추가 합계(KRW) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in result["summaries"]:
        if row["period"] != "continuous":
            continue
        lines.append(
            f"| {row['arm']} | {row['cost_multiplier']} | {row['all_buy']['count']} | "
            f"{report_money(row['all_buy']['sum_krw'])} | {row['new_entry']['count']} | "
            f"{report_money(row['new_entry']['sum_krw'])} | {row['additional_buy']['count']} | "
            f"{report_money(row['additional_buy']['sum_krw'])} |"
        )
    lines += [
        "",
        "continuous 분포 통계(원자료의 Decimal 값은 JSON/CSV에 보존):",
        "분위수는 nearest-rank 방식으로 p∈{0.25, 0.50, 0.75, 0.90}, rank=ceil(p×n), 1-indexed를 사용했습니다. 빈 표본은 n=0·합계=0·min/max/분위수=null입니다.",
    ]
    for row in result["summaries"]:
        if row["period"] != "continuous":
            continue
        for kind in ("new_entry", "additional_buy"):
            stats = row[kind]
            buckets = ", ".join(
                f"{label}: n={stats['buckets'][label]}, sum={report_money(stats['bucket_sums_krw'][label])}"
                for label, _low, _high in BUCKETS
            )
            lines.append(
                f"- {row['arm']} c{row['cost_multiplier']} {kind}: "
                f"n={stats['count']}, 합계={report_money(stats['sum_krw'])}, "
                f"min={report_money(stats['min_krw'])}, p25={report_money(stats['p25_krw'])}, "
                f"p50={report_money(stats['p50_krw'])}, p75={report_money(stats['p75_krw'])}, "
                f"p90={report_money(stats['p90_krw'])}, max={report_money(stats['max_krw'])}; "
                f"구간({buckets})"
            )
    control_rows = [
        row
        for row in result["summaries"]
        if row["period"] == "continuous" and row["arm"] == "control"
    ]
    for row in control_rows:
        below_million = sum(
            row["all_buy"]["buckets"][label]
            for label in ("<10000", "[10000,100000)", "[100000,1000000)")
        )
        new_below_million = sum(
            row["new_entry"]["buckets"][label]
            for label in ("<10000", "[10000,100000)", "[100000,1000000)")
        )
        lines.append(
            f"- 관찰(control c{row['cost_multiplier']}): 1,000,000 KRW 미만 BUY "
            f"{below_million}건 중 신규 진입 {new_below_million}건, 추가 매수 "
            f"{below_million - new_below_million}건; 이는 기술적 관찰이며 임계값을 권고하지 않습니다."
        )
    lines += [
        "",
        "## 해석과 제한",
        "",
        "분포는 기술통계이며 수익·위험의 인과적 설명이나 거래 임계값 선택 근거가 아닙니다. 이 분석은 후향적으로 재사용한 고정 결과이고, 거래 제약·정책 변경·추가 백테스트·PAPER 또는 실거래를 수행하지 않았습니다.",
        "",
        "입력 증거: `results.json` SHA-256 "
        + result["metadata"]["results_sha256"]
        + ", `preregistration.json` SHA-256 "
        + result["metadata"]["preregistration_sha256"]
        + ", source manifest SHA-256 "
        + result["metadata"]["source_manifest_sha256"]
        + ".",
        "",
        "중단 조건은 입력 해시 불일치, PortfolioSimulation/회계 불일치, 기업행동 적용 후 수량 불일치, oversell입니다. 거래 제약·정책 변경·추가 백테스트·PAPER 또는 실거래는 이 분석의 범위가 아닙니다.",
        "",
        "재현: 새 디렉터리를 만든 뒤 `PYTHONPATH=/home/kwl/projects/jusik/backend PYTHONDONTWRITEBYTECODE=1 /home/kwl/projects/jusik/backend/.venv/bin/python -m jusik.research_entry_amount_distribution --input-dir "
        + str(DEFAULT_INPUT)
        + " --source-manifest "
        + str(DEFAULT_MANIFEST)
        + " --output-dir <fresh-output-dir>`",
    ]
    (output_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--source-manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--allow-overwrite", action="store_true")
    args = parser.parse_args(argv)
    with localcontext() as context:
        context.prec = 50
        result = analyze(args.input_dir, args.source_manifest)
    write_outputs(result, args.output_dir, args.allow_overwrite)
    print(
        json.dumps(
            {
                "artifact_count": result["metadata"]["artifact_count"],
                "buy_event_count": len(result["buy_events"]),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
