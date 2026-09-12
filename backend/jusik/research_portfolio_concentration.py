"""Fixed-capital symbol-removal arithmetic sensitivity for frozen attribution."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Any

from jusik.research_entry_attribution import PERIODS, TOLERANCE
from jusik.research_entry_attribution import analyze as entry_analyze

PRECISION = 50
RESULTS_SHA256 = "5c2de5987dd099de64736e1d5ebe9a14e25a43f089bc4a1dc60d924a645e7cc4"
ATTRIBUTION_SHA256 = "3955050f3d29ed42f64988a502705cdfff1c2591bfb084d0c7acb0050dd189d9"
FIXED_INITIAL_CAPITAL = Decimal("100000000")
DEFAULT_ATTRIBUTION = Path(
    "/home/kwl/.local/share/jusik/portfolio-audit/20260911T185925Z-entry-attribution/verified-analysis/attribution.json"
)
SYMBOLS = (
    "000660",
    "005930",
    "0173Y0",
    "0190C0",
    "487230",
    "487240",
    "AMD",
    "ARM",
    "COHR",
    "GEV",
    "GOOGL",
    "MSFT",
    "NVDA",
    "SOXL",
    "TQQQ",
    "VRT",
)


def _dec(value: Any, field: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except Exception as exc:
        raise ValueError(f"{field} is not a decimal") from exc
    if not result.is_finite():
        raise ValueError(f"{field} is non-finite")
    return result


def _json(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, dict):
        return {str(k): _json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json(v) for v in value]
    return value


def _sign(value: Decimal) -> str:
    return "positive" if value > 0 else "negative" if value < 0 else "tie"


def _transition(before: Decimal, after: Decimal) -> str:
    b, a = _sign(before), _sign(after)
    if b == a:
        return "unchanged"
    if b == "positive" and a == "negative" or b == "negative" and a == "positive":
        return "strict_flip"
    if a == "tie":
        return "to_tie"
    if b == "tie":
        return "from_tie"
    return "changed"


def _read_saved(path: Path) -> dict[str, Any]:
    body = path.read_bytes()
    actual = hashlib.sha256(body).hexdigest()
    if actual != ATTRIBUTION_SHA256:
        raise ValueError(
            f"saved attribution hash mismatch: {actual} != {ATTRIBUTION_SHA256}"
        )
    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("saved attribution is not UTF-8 JSON") from exc
    if not isinstance(data, dict):
        raise ValueError("saved attribution must be an object")
    return data


def _canonical(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _canonical(v) for k, v in value.items() if k != "formula"}
    if isinstance(value, list):
        return [_canonical(v) for v in value]
    return value


def analyze(
    input_dir: Path, saved_attribution: Path = DEFAULT_ATTRIBUTION
) -> dict[str, Any]:
    """Reconcile frozen entry attribution and calculate symbol-removal arithmetic."""
    with localcontext() as ctx:
        ctx.prec = PRECISION
        fresh = entry_analyze(input_dir)
        saved = _read_saved(saved_attribution)
        if _canonical(saved) != _canonical(_json(fresh)):
            raise ValueError(
                "saved attribution does not reconcile with recomputed attribution"
            )
        results = json.loads((input_dir / "results.json").read_text(encoding="utf-8"))
        evaluations = results.get("evaluations")
        if not isinstance(evaluations, list) or len(evaluations) != 32:
            raise ValueError("results must contain exactly 32 evaluations")
        capitals: dict[tuple[str, str, int], Decimal] = {}
        for row in evaluations:
            if not isinstance(row, dict):
                raise ValueError("evaluation row must be an object")
            name = str(row.get("artifact", ""))
            stem = name.removesuffix(".json").split("-")
            if len(stem) != 2 or "_c" not in stem[1]:
                raise ValueError("invalid evaluation artifact")
            period, arm_cost = stem
            arm_text, cost_text = arm_cost.rsplit("_c", 1)
            key = (period, "control" if arm_text == "b2" else "variant", int(cost_text))
            if key in capitals:
                raise ValueError("duplicate evaluation key")
            capital = _dec(row.get("initial_equity_krw"), f"{name} initial equity")
            if capital != FIXED_INITIAL_CAPITAL:
                raise ValueError("initial capital must equal frozen 100000000 KRW")
            capitals[key] = capital
        if set(capitals) != {
            (p, a, c) for p in PERIODS for a in ("control", "variant") for c in (1, 2)
        }:
            raise ValueError("evaluation set is incomplete")
        source_rows = {
            (r["period"], int(r["cost_multiplier"]), r["symbol"]): r
            for r in fresh["symbol_rows"]
        }
        rows: list[dict[str, Any]] = []
        pairs: list[dict[str, Any]] = []
        for period in PERIODS:
            for cost in (1, 2):
                ckey = (period, "control", cost)
                capital = capitals[ckey]
                pair = next(
                    p
                    for p in fresh["pairs"]
                    if p["period"] == period and p["cost_multiplier"] == cost
                )
                ctotal = _dec(pair["control_final_equity"], "control final") - capital
                vtotal = _dec(pair["variant_final_equity"], "variant final") - capital
                advantage_before = vtotal - ctotal
                for symbol in SYMBOLS:
                    source = source_rows.get((period, cost, symbol), {})
                    c_pnl = _dec(source.get("control_net_pnl", 0), "control symbol pnl")
                    v_pnl = _dec(source.get("variant_net_pnl", 0), "variant symbol pnl")
                    delta = v_pnl - c_pnl
                    c_remaining, v_remaining = ctotal - c_pnl, vtotal - v_pnl
                    advantage_after = v_remaining - c_remaining
                    if abs(advantage_after - (advantage_before - delta)) > TOLERANCE:
                        raise ValueError("advantage reconciliation failed")
                    rows.append(
                        {
                            "period": period,
                            "cost_multiplier": cost,
                            "symbol": symbol,
                            "fixed_initial_capital": capital,
                            "control_total_pnl": ctotal,
                            "variant_total_pnl": vtotal,
                            "control_symbol_net_pnl": c_pnl,
                            "variant_symbol_net_pnl": v_pnl,
                            "delta_symbol_net_pnl": delta,
                            "control_remaining_pnl": c_remaining,
                            "variant_remaining_pnl": v_remaining,
                            "control_remaining_ratio": c_remaining / capital,
                            "variant_remaining_ratio": v_remaining / capital,
                            "advantage_before": advantage_before,
                            "advantage_after": advantage_after,
                            "advantage_before_sign": _sign(advantage_before),
                            "advantage_after_sign": _sign(advantage_after),
                            "advantage_transition": _transition(
                                advantage_before, advantage_after
                            ),
                            "source_symbol_present": bool(source),
                        }
                    )
                pairs.append(
                    {
                        "period": period,
                        "cost_multiplier": cost,
                        "fixed_initial_capital": capital,
                        "control_total_pnl": ctotal,
                        "variant_total_pnl": vtotal,
                        "advantage_before": advantage_before,
                        "strict_flip_count": sum(
                            r["advantage_transition"] == "strict_flip"
                            for r in rows
                            if r["period"] == period and r["cost_multiplier"] == cost
                        ),
                        "tie_transition_count": sum(
                            r["advantage_transition"] in ("to_tie", "from_tie")
                            for r in rows
                            if r["period"] == period and r["cost_multiplier"] == cost
                        ),
                    }
                )
        return {
            "input": {
                "input_dir": str(input_dir.resolve()),
                "saved_attribution_sha256": ATTRIBUTION_SHA256,
                "results_sha256": RESULTS_SHA256,
                "recomputed_attribution_reconciled": True,
                "symbol_count": 16,
                "pair_count": 16,
            },
            "pairs": pairs,
            "symbol_rows": rows,
            "formula": (
                "remaining_pnl = total_pnl - symbol_net_pnl; "
                "ratio = remaining_pnl / fixed_initial_capital; "
                "advantage = variant - control"
            ),
            "interpretation_limits": (
                "동결 경로의 사후 산술 민감도이며 재배분·재시뮬레이션·"
                "인과 추론·제외 권고가 아닙니다."
            ),
        }


def _write_exclusive(path: Path, body: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(body)
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def write_outputs(result: dict[str, Any], output_dir: Path) -> None:
    if output_dir.exists() and (not output_dir.is_dir() or any(output_dir.iterdir())):
        raise ValueError("output directory must be new or empty")
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_exclusive(
        output_dir / "concentration.json",
        (json.dumps(_json(result), ensure_ascii=False, indent=2) + "\n").encode(),
    )
    rows = result["symbol_rows"]
    with (output_dir / "concentration.csv").open(
        "x", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _json(value) for key, value in row.items()})
    flips = [r for r in rows if r["advantage_transition"] == "strict_flip"]
    lines = [
        "# 종목 제거 산술 민감도",
        "",
        "동결 attribution의 7개 fold와 continuous를 합산하지 않고 각각 계산했습니다.",
        "",
        f"strict flip: {len(flips)}건",
    ]
    lines.extend(
        f"- {r['period']} c{r['cost_multiplier']} {r['symbol']}: "
        f"{r['advantage_before']} -> {r['advantage_after']}"
        for r in flips
    )
    lines += [
        "",
        "이 결과는 재배분·재시뮬레이션·인과 효과·제외 권고가 아닌 "
        "고정 자본 사후 산술입니다.",
    ]
    _write_exclusive(output_dir / "report.md", ("\n".join(lines) + "\n").encode())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--saved-attribution", type=Path, default=DEFAULT_ATTRIBUTION)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    write_outputs(analyze(args.input_dir, args.saved_attribution), args.output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
