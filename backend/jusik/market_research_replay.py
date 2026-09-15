"""Offline, bounded replay for the frozen R0 approximate research run.

The replay reads only the four artifacts named by the frozen manifest.  It does
not open a database, call a provider, or use credentials.  A checkpoint changes
the immutable snapshot capture metadata; market availability and all strategy
inputs remain those in the prepared dataset.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import platform
import subprocess
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Final, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from jusik.market_history_approximate import (
    ApproximateDataset,
    ApproximateMarketHistorySource,
    JsonApproximateProvider,
    run_approximate_market_research,
)
from jusik.market_history_models import (
    MarketReadiness,
    MarketResearchRequest,
    MarketResearchResult,
    MarketResearchRun,
)
from jusik.market_history_sources import data_contract_hash
from jusik.market_research_strategy import (
    market_research_policy_for_grade,
    market_research_policy_hash,
)

MANIFEST_SCHEMA: Final = "r0-baseline-freeze-v1"
REPLAY_SCHEMA: Final = "r0-deterministic-replay-v1"
REPLAY_FILE: Final = "replay.json"
CATALOGUE_FILE: Final = "catalogue.json"
SHA256_PATTERN: Final = r"^[0-9a-f]{64}$"
REPLAY_DEPENDENCIES: Final = (
    "backend/jusik/market_research_replay.py",
    "backend/jusik/market_history_approximate.py",
    "backend/jusik/market_research_strategy.py",
    "backend/jusik/market_history_sources.py",
    "backend/jusik/market_history_models.py",
    "backend/jusik/research_market_calendar.py",
    "backend/jusik/data/market_sessions_2023_2026.json",
)


class ReplayError(ValueError):
    """A frozen input or replay output violates the bounded contract."""


class ArtifactManifest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    path: str = Field(min_length=1)
    sha256: str = Field(pattern=SHA256_PATTERN)
    version: str | None = None
    entry_count: int | None = Field(default=None, ge=0)
    checkpoint_count: int | None = Field(default=None, ge=0)
    raw_entry_verification: str | None = None


class CacheEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")

    key: str = Field(pattern=SHA256_PATTERN)
    content_sha256: str = Field(pattern=SHA256_PATTERN)
    byte_count: int = Field(ge=0)


class CacheManifest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    version: str
    entries: tuple[CacheEntry, ...]


class CompletionMarker(BaseModel):
    model_config = ConfigDict(extra="ignore")

    version: str
    market: str
    start: date
    end: date
    sample_size: int = Field(gt=0)
    output_path: str
    output_sha256: str = Field(pattern=SHA256_PATTERN)
    dataset_sha256: str = Field(pattern=SHA256_PATTERN)


class BaselineManifest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    schema_version: str
    repository: dict[str, object]
    artifacts: dict[str, ArtifactManifest]
    dataset: dict[str, object]
    run: dict[str, object]
    environment: dict[str, object]


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _verify_file(path: Path, expected: str, *, label: str) -> bytes:
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise ReplayError(f"{label} is unavailable") from exc
    actual = _sha256_bytes(content)
    if actual != expected:
        raise ReplayError(f"{label} hash does not match the frozen manifest")
    return content


def _require_dict(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ReplayError(f"{label} is not an object")
    return cast(dict[str, object], value)


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()


def _parse_checkpoint(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReplayError("checkpoint-at must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ReplayError("checkpoint-at must be an aware UTC timestamp")
    return parsed.astimezone(UTC)


def _absolute(path: Path, label: str) -> Path:
    if not path.is_absolute():
        raise ReplayError(f"{label} must be an absolute path")
    return path.resolve()


def _manifest_paths(manifest: BaselineManifest) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for name, artifact in manifest.artifacts.items():
        paths[name] = _absolute(Path(artifact.path), f"{name} path")
    required = {"dataset", "run", "cache_manifest", "collection_completion"}
    if set(paths) != required:
        raise ReplayError("the frozen manifest artifact set is invalid")
    return paths


def _assert_no_input_overlap(output_dir: Path, inputs: dict[str, Path]) -> None:
    output = output_dir.resolve()
    roots = {path.parent for path in inputs.values()}
    roots.add(inputs["cache_manifest"].parent)
    for path in inputs.values():
        if output == path or path.is_relative_to(output):
            raise ReplayError("output directory overlaps a frozen input")
    if any(
        output == root or output.is_relative_to(root) or root.is_relative_to(output)
        for root in roots
    ):
        raise ReplayError("output directory overlaps a frozen input directory")


def _validate_cache(
    cache_path: Path, expected: str, freeze: dict[str, object]
) -> dict[str, object]:
    raw = _verify_file(cache_path, expected, label="cache manifest")
    try:
        cache = CacheManifest.model_validate_json(raw)
    except ValidationError as exc:
        raise ReplayError("cache manifest schema is invalid") from exc
    if cache.version != "collector-cache-v2":
        raise ReplayError("cache manifest version is invalid")
    if freeze.get("version") not in {None, cache.version}:
        raise ReplayError("cache manifest version does not match the freeze")
    expected_count = freeze.get("entry_count")
    if not isinstance(expected_count, int) or len(cache.entries) != expected_count:
        raise ReplayError("cache manifest entry count does not match the freeze")
    checkpoint_count = freeze.get("checkpoint_count")
    if checkpoint_count is not None and checkpoint_count != len(cache.entries):
        raise ReplayError("cache manifest checkpoint count does not match the freeze")
    if freeze.get("raw_entry_verification") not in {None, "pass"}:
        raise ReplayError("cache raw entry verification is not marked as passed")
    keys = [item.key for item in cache.entries]
    if len(keys) != len(set(keys)):
        raise ReplayError("cache manifest contains duplicate entries")
    raw_dir = cache_path.parent / "raw"
    for item in cache.entries:
        raw_path = raw_dir / f"{item.key}.bin"
        try:
            content = raw_path.read_bytes()
        except OSError as exc:
            raise ReplayError("a frozen cache entry is unavailable") from exc
        if (
            len(content) != item.byte_count
            or _sha256_bytes(content) != item.content_sha256
        ):
            raise ReplayError("a frozen cache entry hash does not match the manifest")
    return {"version": cache.version, "entry_count": len(cache.entries)}


def _validate_completion(
    completion_path: Path,
    expected: str,
    dataset_path: Path,
    dataset_sha: str,
    freeze: dict[str, object],
) -> CompletionMarker:
    raw = _verify_file(completion_path, expected, label="collection completion marker")
    try:
        completion = CompletionMarker.model_validate_json(raw)
    except ValidationError as exc:
        raise ReplayError("collection completion marker schema is invalid") from exc
    if completion.version != "collector-completed-v2":
        raise ReplayError("collection completion marker version is invalid")
    if (
        completion.output_sha256 != dataset_sha
        or completion.dataset_sha256 != dataset_sha
        or Path(completion.output_path).resolve() != dataset_path
    ):
        raise ReplayError("collection completion marker does not match the dataset")
    if completion.market != freeze.get("market"):
        raise ReplayError("collection completion marker market is invalid")
    period = cast(dict[str, object], freeze["collection_period"])
    if completion.start != date.fromisoformat(
        cast(str, period["start"])
    ) or completion.end != date.fromisoformat(cast(str, period["end"])):
        raise ReplayError("collection completion marker period is invalid")
    return completion


def _validate_dataset(dataset: ApproximateDataset, expected: dict[str, object]) -> None:
    fields = (
        "market",
        "source",
        "bar_source",
        "fx_source",
        "simulated",
        "normalization_version",
    )
    if any(getattr(dataset, field) != expected.get(field) for field in fields):
        raise ReplayError("prepared dataset metadata does not match the freeze")
    counts = cast(dict[str, object], expected["row_counts"])
    actual_counts = {
        "universe": len(dataset.universe),
        "bars": len(dataset.bars),
        "fx": len(dataset.fx),
    }
    expected_counts = {
        key: value for key, value in counts.items() if isinstance(value, int)
    }
    if actual_counts != expected_counts:
        raise ReplayError("prepared dataset row counts do not match the freeze")
    periods = [row.session for row in dataset.universe]
    periods.extend(row.session for row in dataset.bars)
    periods.extend(row.session for row in dataset.fx)
    available = cast(dict[str, object], expected["available_period"])
    if (
        not periods
        or min(periods) != date.fromisoformat(cast(str, available["start"]))
        or max(periods) != date.fromisoformat(cast(str, available["end"]))
    ):
        raise ReplayError("prepared dataset available period does not match the freeze")


def _validate_environment(manifest: BaselineManifest) -> str:
    expected_lock = manifest.environment.get("requirements_lock_sha256")
    if not isinstance(expected_lock, str):
        raise ReplayError("frozen environment lock hash is missing")
    lock_path = Path(__file__).resolve().parents[1] / "requirements.lock"
    try:
        actual_lock = _sha256_bytes(lock_path.read_bytes())
    except OSError as exc:
        raise ReplayError("backend requirements lock is unavailable") from exc
    if actual_lock != expected_lock:
        raise ReplayError("backend requirements lock does not match the freeze")
    return expected_lock


def _validate_baseline(
    manifest: BaselineManifest,
    baseline: MarketResearchRun,
    dataset: ApproximateDataset,
) -> tuple[MarketResearchRequest, MarketReadiness, dict[str, object]]:
    run_meta = _require_dict(manifest.run, "run")
    request_meta = _require_dict(run_meta["request"], "run request")
    result_meta = _require_dict(run_meta["result"], "run result")
    try:
        expected_request = MarketResearchRequest.model_validate(request_meta)
    except ValidationError as exc:
        raise ReplayError("frozen request is invalid") from exc
    if baseline.status != "completed" or baseline.result is None:
        raise ReplayError("frozen run is not a completed run")
    if (
        baseline.request != expected_request
        or baseline.result.request != expected_request
    ):
        raise ReplayError("frozen run request is inconsistent")
    request = baseline.request
    result = baseline.result
    if (
        request.market != "US"
        or request.research_grade != "approximate"
        or request.stage != "pilot"
    ):
        raise ReplayError("frozen replay request has an unsupported grade or stage")
    if (
        result.status != "approximate"
        or result.completeness != "approximate"
        or result.research_grade != request.research_grade
    ):
        raise ReplayError("frozen result grade or completeness is invalid")
    if result.market != dataset.market:
        raise ReplayError("frozen result market does not match the dataset")
    readiness = result.readiness
    if (
        readiness.market != request.market
        or readiness.research_grade != request.research_grade
        or readiness.simulated != dataset.simulated
    ):
        raise ReplayError("frozen readiness does not match the request and dataset")
    expected_policy = market_research_policy_hash(
        market_research_policy_for_grade(request.research_grade)
    )
    if (
        result.policy_hash != expected_policy
        or result_meta.get("policy_hash") != expected_policy
    ):
        raise ReplayError("frozen policy hash does not match the configured policy")
    for key in ("data_contract_hash", "pool_contract_hash"):
        if result_meta.get(key) != getattr(result, key):
            raise ReplayError(f"frozen {key} is inconsistent")
    if result_meta.get("research_grade") != request.research_grade:
        raise ReplayError("frozen result research grade is inconsistent")
    expected_request_dump = expected_request.model_dump(mode="json")
    if request_meta != expected_request_dump:
        raise ReplayError("frozen request contains unsupported or non-canonical fields")
    return request, readiness, result_meta


def _comparison(
    baseline: MarketResearchResult, replay: MarketResearchResult
) -> dict[str, bool]:
    checks = {
        "metrics": replay.metrics == baseline.metrics,
        "candidate_evidence": replay.candidate_evidence == baseline.candidate_evidence,
        "trades": replay.trades == baseline.trades,
        "equity": replay.equity == baseline.equity,
        "readiness": replay.readiness == baseline.readiness,
        "status": replay.status == baseline.status,
        "completeness": replay.completeness == baseline.completeness,
        "limitations": replay.limitations == baseline.limitations,
        "policy_hash": replay.policy_hash == baseline.policy_hash,
        "data_contract_hash": replay.data_contract_hash == baseline.data_contract_hash,
        "pool_contract_hash": replay.pool_contract_hash == baseline.pool_contract_hash,
        "request": replay.request == baseline.request,
        "market": replay.market == baseline.market,
        "research_grade": replay.research_grade == baseline.research_grade,
        "warmup_sessions": replay.warmup_sessions == baseline.warmup_sessions,
        "stage": replay.stage == baseline.stage,
        "pilot_run_id": replay.pilot_run_id == baseline.pilot_run_id,
        "provenance": replay.provenance == baseline.provenance,
        "account": replay.account == baseline.account,
    }
    checks["all"] = all(checks.values())
    return checks


def _git_sha() -> str | None:
    try:
        root = Path(__file__).resolve().parents[2]
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    value = completed.stdout.strip()
    return value if len(value) == 40 else None


def _dependency_provenance(root: Path | None = None) -> tuple[dict[str, object], bool]:
    root = root or Path(__file__).resolve().parents[2]
    dependencies: dict[str, object] = {}
    any_dirty = False
    for relative in REPLAY_DEPENDENCIES:
        path = root / relative
        try:
            digest = _sha256_bytes(path.read_bytes())
        except OSError as exc:
            raise ReplayError("a replay calculation dependency is unavailable") from exc
        try:
            status = subprocess.run(
                ["git", "status", "--porcelain", "--", relative],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        except (OSError, subprocess.CalledProcessError) as exc:
            raise ReplayError(
                "replay dependency working-tree state is unavailable"
            ) from exc
        dirty = bool(status)
        any_dirty = any_dirty or dirty
        dependencies[relative] = {"sha256": digest, "dirty": dirty}
    return dependencies, any_dirty


def _write_outputs(
    output_dir: Path, replay_payload: bytes, catalogue_payload: bytes
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    targets = (output_dir / REPLAY_FILE, output_dir / CATALOGUE_FILE)
    if any(target.exists() for target in targets):
        raise ReplayError("output files already exist; refusing to overwrite them")
    temporary: list[Path] = []
    created: list[Path] = []
    try:
        for payload in (replay_payload, catalogue_payload):
            with NamedTemporaryFile(
                dir=output_dir, prefix=".replay-", suffix=".tmp", delete=False
            ) as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
                temporary.append(Path(handle.name))
        for source, target in zip(temporary, targets, strict=True):
            os.link(source, target)
            created.append(target)
        for source in temporary:
            source.unlink()
    except (OSError, ReplayError) as exc:
        for source in temporary:
            try:
                source.unlink()
            except OSError:
                pass
        for target in created:
            try:
                target.unlink()
            except OSError:
                pass
        raise ReplayError("replay output could not be written atomically") from exc


async def replay_manifest(
    manifest_path: Path, checkpoint_at: datetime, output_dir: Path
) -> dict[str, object]:
    try:
        manifest_raw = manifest_path.read_bytes()
    except OSError as exc:
        raise ReplayError("manifest is unavailable") from exc
    try:
        manifest = BaselineManifest.model_validate_json(manifest_raw)
    except ValidationError as exc:
        raise ReplayError("baseline manifest schema is invalid") from exc
    if manifest.schema_version != MANIFEST_SCHEMA:
        raise ReplayError("baseline manifest schema version is invalid")
    paths = _manifest_paths(manifest)
    _assert_no_input_overlap(output_dir, {"manifest": manifest_path, **paths})
    for target in (output_dir / REPLAY_FILE, output_dir / CATALOGUE_FILE):
        if target.exists():
            raise ReplayError("output files already exist; refusing to overwrite them")

    dataset_artifact = manifest.artifacts["dataset"]
    dataset_raw = _verify_file(
        paths["dataset"], dataset_artifact.sha256, label="prepared dataset"
    )
    try:
        dataset = ApproximateDataset.model_validate_json(dataset_raw)
    except ValidationError as exc:
        raise ReplayError("prepared dataset schema is invalid") from exc
    _validate_dataset(dataset, manifest.dataset)
    requirements_lock_sha256 = _validate_environment(manifest)

    run_artifact = manifest.artifacts["run"]
    run_raw = _verify_file(paths["run"], run_artifact.sha256, label="baseline run")
    try:
        baseline_run = MarketResearchRun.model_validate_json(run_raw)
    except ValidationError as exc:
        raise ReplayError("baseline run schema is invalid") from exc
    run_meta = _require_dict(manifest.run, "run")
    if baseline_run.id != run_meta.get("id"):
        raise ReplayError("baseline run identifier does not match the freeze")
    if (
        run_meta.get("status") != baseline_run.status
        or run_meta.get("stage") != baseline_run.stage
    ):
        raise ReplayError("baseline run status or stage is inconsistent")
    request, readiness, result_meta = _validate_baseline(
        manifest, baseline_run, dataset
    )

    cache_info = _validate_cache(
        paths["cache_manifest"],
        manifest.artifacts["cache_manifest"].sha256,
        manifest.artifacts["cache_manifest"].model_dump(),
    )
    _validate_completion(
        paths["collection_completion"],
        manifest.artifacts["collection_completion"].sha256,
        paths["dataset"],
        dataset_artifact.sha256,
        manifest.dataset,
    )

    source = ApproximateMarketHistorySource(JsonApproximateProvider(paths["dataset"]))
    snapshot = await source.collect(request, captured_at=checkpoint_at)
    calculated_data_hash = data_contract_hash(snapshot, readiness)
    if calculated_data_hash != result_meta.get("data_contract_hash"):
        raise ReplayError("replayed data contract hash does not match the freeze")
    if snapshot.pool_contract_hash != result_meta.get("pool_contract_hash"):
        raise ReplayError("replayed pool contract hash does not match the freeze")
    snapshot = snapshot.model_copy(update={"data_contract_hash": calculated_data_hash})
    policy_hash = market_research_policy_hash(
        market_research_policy_for_grade(request.research_grade)
    )
    replay_result = run_approximate_market_research(
        snapshot, request, readiness, source.calendar, policy_hash=policy_hash
    )
    assert baseline_run.result is not None
    comparison = _comparison(baseline_run.result, replay_result)
    if not comparison["all"]:
        raise ReplayError("replay result does not exactly match the frozen result")

    replay_payload_obj: dict[str, object] = {
        "schema_version": REPLAY_SCHEMA,
        "checkpoint_at": checkpoint_at.isoformat().replace("+00:00", "Z"),
        "result": replay_result.model_dump(mode="json"),
        "comparison": comparison,
    }
    replay_payload = _canonical(replay_payload_obj) + b"\n"
    dependencies, dependencies_dirty = _dependency_provenance()
    catalogue: dict[str, object] = {
        "schema_version": REPLAY_SCHEMA,
        "manifest": {"path": str(manifest_path), "sha256": _sha256_bytes(manifest_raw)},
        "checkpoint_at": checkpoint_at.isoformat().replace("+00:00", "Z"),
        "run_id": baseline_run.id,
        "code": {
            "baseline_sha": manifest.repository.get("current_replay_baseline_sha"),
            "executing_git_sha": _git_sha(),
            "dependencies": dependencies,
            "dependencies_dirty": dependencies_dirty,
        },
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "requirements_lock_sha256": requirements_lock_sha256,
        },
        "input": {
            "dataset_sha256": dataset_artifact.sha256,
            "run_sha256": run_artifact.sha256,
            "cache_manifest_sha256": manifest.artifacts["cache_manifest"].sha256,
            "collection_completion_sha256": manifest.artifacts[
                "collection_completion"
            ].sha256,
            "cache": cache_info,
            "snapshot_input_hash": snapshot.input_hash,
            "data_contract_hash": calculated_data_hash,
            "pool_contract_hash": snapshot.pool_contract_hash,
        },
        "output": {
            "replay_file": REPLAY_FILE,
            "replay_sha256": _sha256_bytes(replay_payload),
        },
        "comparison": comparison,
        "observation_semantics": (
            "checkpoint controls execution capture only; a future checkpoint "
            "does not add a market observation"
        ),
    }
    catalogue_payload = _canonical(catalogue) + b"\n"
    _write_outputs(output_dir, replay_payload, catalogue_payload)
    return catalogue


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(
        description="Offline deterministic market research replay"
    )
    command.add_argument("--manifest", type=Path, required=True)
    command.add_argument("--checkpoint-at", required=True)
    command.add_argument("--output-dir", type=Path, required=True)
    return command


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        manifest_path = _absolute(args.manifest, "manifest")
        output_dir = _absolute(args.output_dir, "output directory")
        checkpoint = _parse_checkpoint(args.checkpoint_at)
        catalogue = asyncio.run(replay_manifest(manifest_path, checkpoint, output_dir))
    except (KeyError, TypeError, ValueError, OSError, ValidationError) as exc:
        print(f"replay failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(catalogue, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
