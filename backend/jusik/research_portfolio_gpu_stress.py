"""Offline block-bootstrap stress analysis for frozen PortfolioSimulation NAV paths."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import random
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

INITIAL_CAPITAL = Decimal("100000000")
MAX_SCENARIOS = 4096
MAX_OBSERVATIONS = 1172
GPU_MEMORY_CAP_BYTES = 2 * 1024**3


@dataclass(frozen=True)
class Case:
    name: str
    path: Path
    sha256: str


@dataclass(frozen=True)
class Request:
    cases: tuple[Case, ...]
    seed: int
    block_length: int
    scenarios: int
    horizon: int
    initial_capital: Decimal


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, value: object, text: bool = False) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            if text:
                handle.write(str(value))
            else:
                json.dump(value, handle, ensure_ascii=False, indent=2, default=str)
                handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def _decimal(value: object, label: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except Exception as exc:
        raise ValueError(f"{label} must be decimal") from exc
    if not result.is_finite():
        raise ValueError(f"{label} must be finite")
    return result


def load_request(path: Path) -> tuple[Request, dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    entries = raw.get("cases") if isinstance(raw, dict) else None
    if not isinstance(entries, list) or not 1 <= len(entries) <= 4:
        raise ValueError("request must contain one to four cases")
    cases: list[Case] = []
    names: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("each case must be an object")
        name, source, digest = entry.get("name"), entry.get("path"), entry.get("sha256")
        if not isinstance(name, str) or not name or name in names:
            raise ValueError("case names must be unique")
        if (
            not isinstance(source, str)
            or not isinstance(digest, str)
            or len(digest) != 64
        ):
            raise ValueError("case path and 64-character sha256 are required")
        names.add(name)
        cases.append(Case(name, Path(source), digest.lower()))
    if not isinstance(raw, dict):
        raise ValueError("request must be an object")
    seed, block = raw.get("seed"), raw.get("block_length_observations")
    scenarios, horizon = raw.get("scenarios"), raw.get("horizon_observations")
    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        raise ValueError("seed must be non-negative integer")
    if not isinstance(block, int) or isinstance(block, bool) or block < 1:
        raise ValueError("block_length_observations must be positive")
    if (
        not isinstance(scenarios, int)
        or isinstance(scenarios, bool)
        or not 1 <= scenarios <= MAX_SCENARIOS
    ):
        raise ValueError("scenarios must be between 1 and 4096")
    if (
        not isinstance(horizon, int)
        or isinstance(horizon, bool)
        or not 1 <= horizon <= MAX_OBSERVATIONS - 1
    ):
        raise ValueError("horizon_observations must be between 1 and 1171")
    initial = _decimal(raw.get("initial_capital_krw"), "initial_capital_krw")
    if initial != INITIAL_CAPITAL:
        raise ValueError("initial capital must be exactly 100000000")
    return Request(tuple(cases), seed, block, scenarios, horizon, initial), raw


def _load_path(
    case: Case, initial: Decimal
) -> tuple[list[datetime], list[Decimal], dict[str, str]]:
    if case.path.is_symlink() or not case.path.is_file():
        raise ValueError(f"source is not regular file: {case.path}")
    data = case.path.read_bytes()
    if hashlib.sha256(data).hexdigest() != case.sha256:
        raise ValueError(f"source hash mismatch: {case.path}")
    try:
        from jusik.research_portfolio_models import PortfolioSimulation

        simulation = PortfolioSimulation.model_validate(
            json.loads(data.decode("utf-8"))
        )
    except Exception as exc:
        raise ValueError(f"invalid PortfolioSimulation: {case.path}") from exc
    if not simulation.complete or simulation.incomplete_reasons:
        raise ValueError(f"simulation must be complete: {case.path}")
    if simulation.metrics.initial_equity_krw != initial:
        raise ValueError(f"source initial capital mismatch: {case.path}")
    times: list[datetime] = []
    nav: list[Decimal] = []
    previous: datetime | None = None
    for point in simulation.equity:
        if point.at.tzinfo is None or point.at.utcoffset() != UTC.utcoffset(point.at):
            raise ValueError(f"timestamps must be strict UTC-aware: {case.path}")
        if previous is not None and point.at <= previous:
            raise ValueError(
                f"timestamps must be unique and chronological: {case.path}"
            )
        if not point.equity_krw.is_finite() or point.equity_krw <= 0:
            raise ValueError(f"NAV must be finite and positive: {case.path}")
        times.append(point.at)
        nav.append(point.equity_krw)
        previous = point.at
    if not 2 <= len(nav) <= MAX_OBSERVATIONS or nav[0] != initial:
        raise ValueError(f"NAV observations or initial value invalid: {case.path}")
    return (
        times,
        nav,
        {
            "final_equity_krw": str(simulation.metrics.final_equity_krw),
            "max_drawdown_pct": str(simulation.metrics.max_drawdown_pct),
            "total_return_pct": str(simulation.metrics.total_return_pct),
        },
    )


def validate_inputs(
    request: Request,
) -> tuple[list[datetime], list[list[Decimal]], list[dict[str, str]]]:
    aligned: list[datetime] | None = None
    paths: list[list[Decimal]] = []
    metrics: list[dict[str, str]] = []
    for case in request.cases:
        times, nav, source_metrics = _load_path(case, request.initial_capital)
        if aligned is None:
            aligned = times
        elif times != aligned:
            raise ValueError("all case timestamps must be exactly aligned")
        paths.append(nav)
        metrics.append(source_metrics)
    assert aligned is not None
    if request.block_length > len(aligned) - 1 or request.horizon > len(aligned) - 1:
        raise ValueError("block length or horizon exceeds return observations")
    return aligned, paths, metrics


def generate_indices(
    seed: int, scenarios: int, horizon: int, block_length: int, observations: int
) -> list[list[int]]:
    if block_length > observations:
        raise ValueError("block length exceeds return observations")
    rng = random.Random(seed)
    result: list[list[int]] = []
    for _ in range(scenarios):
        row: list[int] = []
        while len(row) < horizon:
            start = rng.randrange(observations - block_length + 1)
            row.extend(range(start, start + block_length))
        result.append(row[:horizon])
    return result


def calculate_metrics(
    nav: list[Decimal], indices: list[int], initial: Decimal = INITIAL_CAPITAL
) -> dict[str, Any]:
    value, peak, maximum_drawdown = initial, initial, Decimal(0)
    for index in indices:
        value *= nav[index + 1] / nav[index]
        peak = max(peak, value)
        maximum_drawdown = max(maximum_drawdown, (peak - value) / peak)
    terminal_return = value / initial - 1
    return {
        "terminal_return_pct": terminal_return * 100,
        "max_drawdown_pct": maximum_drawdown * 100,
        "loss": terminal_return < 0,
        "drawdown_20": maximum_drawdown >= Decimal("0.20"),
        "loss_drawdown_20": terminal_return < 0 and maximum_drawdown >= Decimal("0.20"),
    }


def run(
    request_path: Path,
    output_dir: Path,
    device: Literal["auto", "cpu", "cuda"] = "auto",
) -> dict[str, Any]:
    if output_dir.is_symlink() or output_dir.exists():
        raise ValueError("output directory must be new and not a symlink")
    request, raw = load_request(request_path)
    times, paths, source_metrics = validate_inputs(request)
    if request.scenarios * request.horizon * len(paths) * 64 > GPU_MEMORY_CAP_BYTES:
        raise ValueError("requested GPU memory exceeds 2 GiB cap")
    indices = generate_indices(
        request.seed,
        request.scenarios,
        request.horizon,
        request.block_length,
        len(times) - 1,
    )
    index_payload = {
        "seed": request.seed,
        "block_length_observations": request.block_length,
        "horizon_observations": request.horizon,
        "indices": indices,
    }
    index_hash = hashlib.sha256(
        json.dumps(index_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if device == "cuda":
        try:
            import torch  # type: ignore[import-not-found]

            if not torch.cuda.is_available():
                raise RuntimeError("CUDA device is unavailable")
        except ImportError as exc:
            raise RuntimeError("torch is required for explicit CUDA") from exc
        raise RuntimeError("CUDA implementation requires the optional torch runtime")
    started = time.perf_counter()
    rows = [
        [calculate_metrics(path, row, request.initial_capital) for path in paths]
        for row in indices
    ]
    elapsed = time.perf_counter() - started
    output_dir.mkdir(parents=False)
    _write(output_dir / "request.json", raw)
    _write(
        output_dir / "preregistration.json",
        {
            "request_sha256": sha256(request_path),
            "indices_sha256": index_hash,
            "source_metrics": source_metrics,
            "retrospective_descriptive_only": True,
        },
    )
    _write(output_dir / "indices.json", index_payload)
    _write(output_dir / "indices.sha256", {"sha256": index_hash})
    _write(
        output_dir / "results.json",
        {
            "metrics": [
                {
                    "scenario": s,
                    "case": case.name,
                    **{
                        k: str(v) if isinstance(v, Decimal) else v
                        for k, v in metric.items()
                    },
                }
                for s, row in enumerate(rows)
                for case, metric in zip(request.cases, row, strict=True)
            ]
        },
    )
    _write(
        output_dir / "summary.json",
        {
            case.name: {
                "loss_frequency": sum(row[i]["loss"] for row in rows)
                / request.scenarios,
                "drawdown_20_frequency": sum(row[i]["drawdown_20"] for row in rows)
                / request.scenarios,
                "loss_drawdown_20_frequency": sum(
                    row[i]["loss_drawdown_20"] for row in rows
                )
                / request.scenarios,
            }
            for i, case in enumerate(request.cases)
        },
    )
    _write(
        output_dir / "environment.json",
        {
            "python": sys.version,
            "platform": platform.platform(),
            "device": "cpu",
            "elapsed_seconds": elapsed,
            "peak_gpu_memory_bytes": 0,
            "gpu_memory_cap_bytes": GPU_MEMORY_CAP_BYTES,
            "benchmark": {
                "warmed": False,
                "synchronized": False,
                "includes_host_device_transfers": False,
                "cpu_is_acceptable": True,
            },
        },
    )
    _write(
        output_dir / "report.md",
        """# GPU 포트폴리오 경로 스트레스 보고서

생성 경로의 기술통계이며 예측이나 투자 권고가 아닙니다.
비용·통제는 NAV에 이미 포함되어 재적용하지 않았습니다.
모든 인덱스는 관측값 기준입니다.
""",
        text=True,
    )
    _write(
        output_dir / "hash-manifest.json",
        {
            "request.json": sha256(output_dir / "request.json"),
            "indices.json": sha256(output_dir / "indices.json"),
            "results.json": sha256(output_dir / "results.json"),
            "source_hashes": {case.name: case.sha256 for case in request.cases},
            "code_sha256": sha256(Path(__file__)),
        },
    )
    return {
        "device": "cpu",
        "scenario_count": request.scenarios,
        "indices_sha256": index_hash,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    args = parser.parse_args(argv)
    print(json.dumps(run(args.request, args.output_dir, args.device)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
