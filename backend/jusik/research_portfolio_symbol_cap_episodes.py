"""Reconstruct symbol-cap breach episodes from frozen observer cells.

This module only reads the saved observer/simulation archive.  It does not run
the portfolio engine, fetch data, or infer trades, causality, or recovery.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path
from typing import Any

MANDATE_SHA256 = "ceca2ee1d3e86cf79822b6b4a1606ac6699405f93eaf302fcf3842247f5de7ac"
REPORT_SHA256 = "663ea3345b609d76f08676c56783512c943e37437a92cf06e9ac3a390d8253b8"
MANIFEST_SHA256 = "b7306e276f66d773af9b4d029ffdee20c368c474044f1209dadd7852c068df1c"
RESULTS_SHA256 = "cada27b0e5518b8384e521235bc6fc1e4c5a029b9c4f8ff3db173cde41f2670d"
EXPECTED_MANIFEST_ENTRIES = 72
EXPECTED_CELLS = 32
EXPECTED_BREACH_OBSERVATIONS = 351
SYMBOL_CAP = Decimal("0.20")


class EpisodesError(ValueError):
    """Raised when pinned evidence is missing, changed, or malformed."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _strict_json(path: Path) -> Any:
    def reject(value: str) -> Any:
        raise EpisodesError(f"non-finite JSON constant: {value}")

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise EpisodesError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=reject,
            object_pairs_hook=unique,
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise EpisodesError(f"json_unreadable:{path}") from exc


def _decimal(value: Any, field: str) -> Decimal:
    if isinstance(value, bool):
        raise EpisodesError(f"invalid_decimal:{field}")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise EpisodesError(f"invalid_decimal:{field}") from exc
    if not result.is_finite():
        raise EpisodesError(f"non_finite_decimal:{field}")
    return result


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    return value


def _manifest(archive: Path) -> tuple[dict[str, str], str]:
    path = archive / "hash-manifest.json"
    if path.is_symlink() or not path.is_file():
        raise EpisodesError("manifest_missing")
    actual_manifest_sha = _sha256(path)
    if actual_manifest_sha != MANIFEST_SHA256:
        raise EpisodesError("manifest_sha_mismatch")
    body = _strict_json(path)
    if not isinstance(body, dict) or len(body) != EXPECTED_MANIFEST_ENTRIES:
        raise EpisodesError("manifest_entry_count_mismatch")
    result: dict[str, str] = {}
    for relative, expected in body.items():
        if not isinstance(relative, str) or not isinstance(expected, str):
            raise EpisodesError("manifest_entry_invalid")
        candidate = archive / relative
        if candidate.is_symlink() or not candidate.is_file():
            raise EpisodesError(f"manifest_file_missing:{relative}")
        try:
            candidate.resolve().relative_to(archive.resolve())
        except ValueError as exc:
            raise EpisodesError(f"manifest_path_escape:{relative}") from exc
        actual = _sha256(candidate)
        if actual != expected:
            raise EpisodesError(f"manifest_hash_mismatch:{relative}")
        result[relative] = expected
    return result, actual_manifest_sha


def _artifact_parts(artifact: str) -> tuple[str, str, int]:
    stem = artifact.removesuffix(".json")
    try:
        period, arm_cost = stem.split("-", 1)
        arm, cost_text = arm_cost.split("_c", 1)
        cost = int(cost_text)
    except (ValueError, TypeError) as exc:
        raise EpisodesError(f"artifact_name_invalid:{artifact}") from exc
    if period != "continuous" and not period.startswith("fold_"):
        raise EpisodesError(f"artifact_period_invalid:{artifact}")
    if arm not in {"control", "variant"} or cost not in {1, 3}:
        raise EpisodesError(f"artifact_arm_or_cost_invalid:{artifact}")
    return period, arm, cost


def _validate_results(archive: Path, manifest: Mapping[str, str]) -> dict[str, Any]:
    results_path = archive / "results.json"
    if _sha256(results_path) != RESULTS_SHA256:
        raise EpisodesError("results_sha_mismatch")
    results = _strict_json(results_path)
    if not isinstance(results, dict):
        raise EpisodesError("results_object_required")
    if results.get("evaluation_count") != EXPECTED_CELLS:
        raise EpisodesError("evaluation_count_mismatch")
    if results.get("evaluation_cap") != EXPECTED_CELLS:
        raise EpisodesError("evaluation_cap_mismatch")
    evaluations = results.get("evaluations")
    order = results.get("execution_order")
    if not isinstance(evaluations, list) or len(evaluations) != EXPECTED_CELLS:
        raise EpisodesError("evaluation_rows_mismatch")
    if not isinstance(order, list) or len(order) != EXPECTED_CELLS:
        raise EpisodesError("execution_order_mismatch")
    expected_order: list[str] = []
    by_artifact: dict[str, dict[str, Any]] = {}
    for item in evaluations:
        if not isinstance(item, dict) or not isinstance(item.get("artifact"), str):
            raise EpisodesError("evaluation_row_invalid")
        artifact = item["artifact"]
        if artifact in by_artifact:
            raise EpisodesError("duplicate_evaluation_artifact")
        if (
            f"simulations/{artifact}" not in manifest
            or f"observations/{artifact}" not in manifest
        ):
            raise EpisodesError(f"evaluation_artifact_not_pinned:{artifact}")
        period, arm, cost = _artifact_parts(artifact)
        if (
            item.get("period") != period
            or item.get("arm") != arm
            or item.get("cost_multiplier") != cost
        ):
            raise EpisodesError(f"evaluation_identity_mismatch:{artifact}")
        if not isinstance(item.get("metrics"), dict):
            raise EpisodesError(f"evaluation_metrics_missing:{artifact}")
        by_artifact[artifact] = item
    for value in order:
        if not isinstance(value, str) or value not in by_artifact:
            raise EpisodesError("execution_order_invalid")
        expected_order.append(value)
    if (
        set(expected_order) != set(by_artifact)
        or len(set(expected_order)) != EXPECTED_CELLS
    ):
        raise EpisodesError("execution_order_set_mismatch")
    return {
        "results": results,
        "evaluations": by_artifact,
        "execution_order": expected_order,
    }


def _validate_mandate(repo_root: Path) -> str:
    path = repo_root / "docs/research-mandate.json"
    if _sha256(path) != MANDATE_SHA256:
        raise EpisodesError("mandate_sha_mismatch")
    return MANDATE_SHA256


def _parse_at(value: Any) -> str:
    if not isinstance(value, str):
        raise EpisodesError("observation_timestamp_required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EpisodesError("observation_timestamp_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise EpisodesError("observation_timestamp_timezone_required")
    return value


def _episode_record(
    *,
    artifact: str,
    period: str,
    arm: str,
    cost: int,
    symbol: str,
    row_index: int,
    row: Mapping[str, Any],
    nav: Decimal,
    value: Decimal,
) -> dict[str, Any]:
    weight = value / nav
    return {
        "artifact": artifact,
        "period": period,
        "arm": arm,
        "cost_multiplier": cost,
        "symbol": symbol,
        "observation_index": row_index,
        "at": _parse_at(row.get("at")),
        "nav_krw": format(nav, "f"),
        "position_value_krw": format(value, "f"),
        "weight": format(weight, "f"),
        "excess_weight": format(weight - SYMBOL_CAP, "f"),
    }


def _read_cell(
    archive: Path,
    artifact: str,
    evaluation: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    period, arm, cost = _artifact_parts(artifact)
    path = archive / "observations" / artifact
    rows = _strict_json(path)
    if not isinstance(rows, list) or not rows:
        raise EpisodesError(f"observation_rows_invalid:{artifact}")
    records: list[dict[str, Any]] = []
    last_index: dict[str, int] = {}
    episodes: list[dict[str, Any]] = []
    episode_by_symbol: dict[str, dict[str, Any]] = {}
    for row_index, raw_row in enumerate(rows):
        if not isinstance(raw_row, dict):
            raise EpisodesError(f"observation_row_invalid:{artifact}")
        nav = _decimal(raw_row.get("nav_krw"), f"{artifact}.nav")
        if nav <= 0:
            raise EpisodesError(f"observation_nav_invalid:{artifact}")
        positions = raw_row.get("position_values_krw")
        if not isinstance(positions, dict):
            raise EpisodesError(f"position_values_invalid:{artifact}")
        _parse_at(raw_row.get("at"))
        for raw_symbol, raw_value in positions.items():
            if not isinstance(raw_symbol, str) or not raw_symbol:
                raise EpisodesError(f"symbol_invalid:{artifact}")
            value = _decimal(raw_value, f"{artifact}.{raw_symbol}")
            if value <= SYMBOL_CAP * nav:
                continue
            record = _episode_record(
                artifact=artifact,
                period=period,
                arm=arm,
                cost=cost,
                symbol=raw_symbol,
                row_index=row_index,
                row=raw_row,
                nav=nav,
                value=value,
            )
            records.append(record)
            current = episode_by_symbol.get(raw_symbol)
            if current is None or last_index[raw_symbol] != row_index - 1:
                current = {
                    "artifact": artifact,
                    "period": period,
                    "arm": arm,
                    "cost_multiplier": cost,
                    "symbol": raw_symbol,
                    "episode_index": len(
                        [item for item in episodes if item["symbol"] == raw_symbol]
                    ),
                    "observation_indices": [],
                    "observations": [],
                }
                episodes.append(current)
                episode_by_symbol[raw_symbol] = current
            current["observation_indices"].append(row_index)
            current["observations"].append(record)
            last_index[raw_symbol] = row_index
    for episode in episodes:
        episode["observation_count"] = len(episode["observations"])
        episode["start_at"] = episode["observations"][0]["at"]
        episode["end_at"] = episode["observations"][-1]["at"]
        episode["maximum_weight"] = max(
            item["weight"] for item in episode["observations"]
        )
        episode["maximum_excess_weight"] = max(
            item["excess_weight"] for item in episode["observations"]
        )
        episode["boundary_semantics"] = (
            "contiguous stored breach rows; no recovery or causality inferred"
        )
    cell = {
        "artifact": artifact,
        "period": period,
        "arm": arm,
        "cost_multiplier": cost,
        "observation_count": len(rows),
        "breach_observation_count": len(records),
        "episode_count": len(episodes),
        "symbols": list(dict.fromkeys(item["symbol"] for item in records)),
        "performance": {
            "metrics": evaluation["metrics"],
            "global_drawdown_pct": evaluation.get("global_drawdown_pct"),
            "daily_metrics": evaluation.get("daily_metrics"),
        },
        "episodes": episodes,
    }
    return cell, records


def analyze(archive: Path, repo_root: Path) -> dict[str, Any]:
    """Analyze exactly the 32 pinned cells without simulation or network I/O."""
    archive = archive.resolve()
    repo_root = repo_root.resolve()
    if not archive.is_dir():
        raise EpisodesError("archive_missing")
    mandate_sha = _validate_mandate(repo_root)
    manifest, manifest_sha = _manifest(archive)
    report = (
        repo_root / "docs/research/portfolio-volatility15-cadence-cost-tradeoff-v1.md"
    )
    if _sha256(report) != REPORT_SHA256:
        raise EpisodesError("report_sha_mismatch")
    validated = _validate_results(archive, manifest)
    with localcontext() as context:
        context.prec = 80
        cells: list[dict[str, Any]] = []
        all_records: list[dict[str, Any]] = []
        for artifact in validated["execution_order"]:
            cell, records = _read_cell(
                archive, artifact, validated["evaluations"][artifact]
            )
            cells.append(cell)
            all_records.extend(records)
        if len(cells) != EXPECTED_CELLS:
            raise EpisodesError("cell_count_mismatch")
        if len(all_records) != EXPECTED_BREACH_OBSERVATIONS:
            raise EpisodesError("breach_observation_count_mismatch")
        symbols: dict[str, dict[str, Any]] = {}
        for record in all_records:
            item = symbols.setdefault(
                record["symbol"],
                {
                    "symbol": record["symbol"],
                    "observation_count": 0,
                    "episode_count": 0,
                    "maximum_weight": record["weight"],
                    "maximum_excess_weight": record["excess_weight"],
                },
            )
            item["observation_count"] += 1
            item["maximum_weight"] = max(item["maximum_weight"], record["weight"])
            item["maximum_excess_weight"] = max(
                item["maximum_excess_weight"], record["excess_weight"]
            )
        for cell in cells:
            for episode in cell["episodes"]:
                symbols[episode["symbol"]]["episode_count"] += 1
        manifest_after, manifest_sha_after = _manifest(archive)
        if manifest_after != manifest or manifest_sha_after != manifest_sha:
            raise EpisodesError("input_changed_during_analysis")
        if (
            _sha256(archive / "results.json") != RESULTS_SHA256
            or _sha256(report) != REPORT_SHA256
            or _sha256(repo_root / "docs/research-mandate.json") != MANDATE_SHA256
        ):
            raise EpisodesError("input_changed_during_analysis")
        return {
            "analysis": "offline_symbol_cap_breach_episode_reconstruction",
            "symbol_cap": format(SYMBOL_CAP, "f"),
            "cell_count": len(cells),
            "breach_observation_count": len(all_records),
            "episode_count": sum(int(cell["episode_count"]) for cell in cells),
            "cells": cells,
            "symbol_summary": list(symbols.values()),
            "input_pins": {
                "mandate_sha256": mandate_sha,
                "report_sha256": REPORT_SHA256,
                "manifest_sha256": manifest_sha,
                "results_sha256": RESULTS_SHA256,
                "manifest_entry_count": len(manifest),
            },
            "limitations": [
                "Stored observer row order and same-timestamp repeats are preserved.",
                (
                    "Episode boundaries are contiguous stored breach rows only; "
                    "no trade/observation causality or recovery is inferred."
                ),
                (
                    "This is offline reconstruction of saved cells, not historical "
                    "simulation, live trading, or PAPER execution."
                ),
            ],
        }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = analyze(args.archive, args.repo_root)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(
                _json_value(result), ensure_ascii=False, indent=2, sort_keys=True
            )
            + "\n",
            encoding="utf-8",
        )
    except (EpisodesError, OSError) as exc:
        print(f"error: {exc}")
        return 2
    print(
        json.dumps(
            {
                key: result[key]
                for key in ("cell_count", "breach_observation_count", "episode_count")
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
