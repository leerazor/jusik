"""Generate and verify an opt-in, forward-simulation time-evidence bundle.

Generation is intentionally explicit and offline.  It accepts a frozen
``PortfolioInput``, a simulation configuration and exact calendar bytes,
precomputes the engine event plan, calls the public engine exactly once, and
stores a new content-addressed bundle.  Verification only reads that bundle;
it never executes the simulation engine.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from jusik import research_portfolio_engine as engine
from jusik.research_market_calendar import MarketCalendar
from jusik.research_portfolio_models import (
    PortfolioCandidate,
    PortfolioConfig,
    PortfolioInput,
    PortfolioPolicy,
    PortfolioSimulation,
)
from jusik.research_portfolio_time_models import (
    TIME_EVIDENCE_POLICY_VERSION,
    TIME_EVIDENCE_SCHEMA_VERSION,
    CloseEventTimeEvidence,
    InitialCapitalEvent,
    MarketSessionTimeEvidence,
    NavTimeEvidence,
    PortfolioTimeEvidence,
)

SCHEMA_VERSION: Final[Literal[1]] = TIME_EVIDENCE_SCHEMA_VERSION
POLICY_VERSION: Final[str] = TIME_EVIDENCE_POLICY_VERSION
ARTIFACT_NAMES: Final[tuple[str, ...]] = (
    "input.json",
    "config.json",
    "calendar.json",
    "simulation.json",
    "time-evidence.json",
)
MANIFEST_NAME: Final[str] = "manifest.json"
ALL_ARTIFACT_NAMES: Final[tuple[str, ...]] = (*ARTIFACT_NAMES, MANIFEST_NAME)
LiteralOne = Literal[1]


class TimeEvidenceConfig(BaseModel):
    """Frozen simulation inputs stored beside the generated result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: LiteralOne = SCHEMA_VERSION
    candidate: PortfolioCandidate
    period_start: date
    period_end: date
    portfolio_config: PortfolioConfig
    policy: PortfolioPolicy = "corrected_control"

    @classmethod
    def from_values(
        cls,
        candidate: PortfolioCandidate,
        start: date,
        end: date,
        config: PortfolioConfig,
        policy: PortfolioPolicy,
    ) -> TimeEvidenceConfig:
        return cls(
            candidate=candidate,
            period_start=start,
            period_end=end,
            portfolio_config=config,
            policy=policy,
        )


class GenerationRequest(BaseModel):
    """CLI request containing only fixed offline file paths and hashes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    input_path: str
    config_path: str
    calendar_path: str
    input_sha256: str | None = None
    config_sha256: str | None = None
    calendar_sha256: str | None = None


class BundleVerification(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    manifest_sha256: str
    source_sha256: str
    simulation_sha256: str
    nav_count: int = Field(ge=0)


def sha256_bytes(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _strict_json(body: bytes, label: str) -> object:
    def parse_int(value: str) -> int:
        if len(value.lstrip("+-")) > 100:
            raise ValueError(f"integer is too large in {label}")
        parsed = int(value)
        if abs(parsed) > 10**100:
            raise ValueError(f"integer is too large in {label}")
        return parsed

    def reject_constant(value: str) -> object:
        raise ValueError(f"non-finite JSON constant in {label}: {value}")

    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key in {label}: {key}")
            result[key] = value
        return result

    try:
        return json.loads(
            body.decode("utf-8"),
            parse_float=Decimal,
            parse_int=parse_int,
            parse_constant=reject_constant,
            object_pairs_hook=reject_duplicates,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid JSON: {label}") from exc


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
            default=str,
        ).encode("utf-8")
        + b"\n"
    )


def _digest(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _regular_file(path: Path, label: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{label} must be a regular file")
    return path.read_bytes()


def _load_model_bytes(body: bytes, model: type[BaseModel], label: str) -> BaseModel:
    try:
        return model.model_validate(_strict_json(body, label))
    except (ValidationError, ValueError) as exc:
        raise ValueError(f"invalid {label}") from exc


def _write_bytes_exclusive(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _staging_dir(path: Path) -> Path:
    parent = path.parent
    if parent.is_symlink() or not parent.is_dir():
        raise ValueError("output parent must be a real directory")
    if path.is_symlink() or path.exists():
        raise ValueError("output directory must be new and not a symlink")
    return Path(tempfile.mkdtemp(prefix=f".{path.name}.staging-", dir=parent))


def _safe_artifact_name(name: object) -> str:
    if (
        not isinstance(name, str)
        or name not in ALL_ARTIFACT_NAMES
        or Path(name).name != name
        or Path(name).is_absolute()
    ):
        raise ValueError("manifest contains an unsafe artifact path")
    return name


def _session_for(
    calendar: MarketCalendar,
    exchange: str,
    local_date: date,
    symbol: str,
) -> MarketSessionTimeEvidence:
    lookup = calendar.lookup(exchange, local_date)
    if lookup.state != "session" or lookup.session is None:
        raise ValueError(
            f"missing official session for {symbol} {exchange} {local_date}"
        )
    session = lookup.session
    return MarketSessionTimeEvidence(
        symbol=symbol,
        calendar=session.calendar,
        local_date=session.local_date,
        session_id=f"{session.calendar}:{session.local_date.isoformat()}",
        open_at=session.open_at,
        close_at=session.close_at,
    )


def _event_plan(
    source: PortfolioInput,
    start: date,
    end: date,
    calendar: MarketCalendar,
) -> tuple[list[engine.MarketEvent], dict[str, engine.InstrumentData]]:
    if not calendar.available:
        raise ValueError("supplied market calendar is unavailable")
    data = engine._instrument_data(source)
    events = engine._events(data, start, end)
    previous: tuple[datetime, int, str, str] | None = None
    seen: set[tuple[datetime, str, str | None, date | None]] = set()
    order = {"rebalance": 0, "open": 1, "close": 2}
    for event in events:
        if event.at.tzinfo is None or event.at.utcoffset() is None:
            raise ValueError("engine event is not timezone-aware")
        key = (event.at, event.kind, event.symbol, event.day)
        if key in seen:
            raise ValueError("engine event plan contains a duplicate event")
        seen.add(key)
        sort_key = (event.at, order[event.kind], event.symbol or "", event.kind)
        if previous is not None and sort_key < previous:
            raise ValueError("engine event plan is not immutable and sorted")
        previous = sort_key
        if event.kind not in {"open", "close"}:
            continue
        if event.symbol is None or event.day is None:
            raise ValueError("price event is missing symbol or date")
        item = data[event.symbol]
        session = _session_for(
            calendar, item.instrument.exchange, event.day, event.symbol
        )
        if event.kind == "open" and event.at < session.open_at:
            raise ValueError("engine open event precedes official session open")
        # This catches delayed KRX closes as well as any source bar that the
        # existing engine would expose before its official close.
        if event.kind == "close" and event.at < session.close_at:
            raise ValueError(
                "engine close event precedes official session close; "
                "source is not causal"
            )

    # Warmup bars are also inputs to target_weights.  Validate their close
    # availability, not merely the bars that happen to produce NAV points.
    for symbol, item in data.items():
        for bar in item.snapshot.instruments[0].bars:
            session = _session_for(calendar, item.instrument.exchange, bar.date, symbol)
            engine_close = engine._market_time(
                bar.date, item.instrument.timezone, opening=False
            )
            if engine_close < session.close_at:
                raise ValueError(
                    f"warmup bar for {symbol} is available before official close"
                )
    if not events:
        raise ValueError("cannot anchor initial capital without engine events")
    return events, data


def _simulation_contract(
    simulation: PortfolioSimulation,
    config: TimeEvidenceConfig,
) -> None:
    try:
        roundtrip = PortfolioSimulation.model_validate(
            simulation.model_dump(mode="json")
        )
    except (ValidationError, ValueError) as exc:
        raise ValueError("simulation is not an existing PortfolioSimulation") from exc
    if roundtrip != simulation:
        raise ValueError("simulation changed during contract serialization")
    if (
        simulation.candidate != config.candidate
        or simulation.period_start != config.period_start
        or simulation.period_end != config.period_end
        or simulation.policy != config.policy
    ):
        raise ValueError("simulation does not match fixed configuration")


def _event_plan_bytes(events: list[engine.MarketEvent]) -> bytes:
    return _json_bytes(
        [
            {
                "at": event.at.isoformat(),
                "kind": event.kind,
                "symbol": event.symbol,
                "day": event.day.isoformat() if event.day is not None else None,
            }
            for event in events
        ]
    )


def _build_sidecar(
    source: PortfolioInput,
    config: TimeEvidenceConfig,
    events: list[engine.MarketEvent],
    data: dict[str, engine.InstrumentData],
    calendar: MarketCalendar,
    simulation: PortfolioSimulation,
) -> PortfolioTimeEvidence:
    first = events[0]
    initial = InitialCapitalEvent(
        initial_capital_krw=config.portfolio_config.initial_cash_krw,
        timestamp=first.at,
        first_engine_event_at=first.at,
        first_engine_event_kind=first.kind,
    )
    by_time: dict[datetime, list[engine.MarketEvent]] = {}
    for event in events:
        if event.kind == "close":
            by_time.setdefault(event.at, []).append(event)
    nav: list[NavTimeEvidence] = []
    for index, point in enumerate(simulation.equity):
        closes = by_time.get(point.at, [])
        if not closes:
            raise ValueError("NAV evaluation_at has no engine close group")
        group: list[CloseEventTimeEvidence] = []
        for event in closes:
            assert event.symbol is not None and event.day is not None
            item = data[event.symbol]
            session = _session_for(
                calendar, item.instrument.exchange, event.day, event.symbol
            )
            group.append(
                CloseEventTimeEvidence(
                    symbol=event.symbol,
                    bar_date=event.day,
                    event_at=event.at,
                    session=session,
                )
            )
        nav.append(
            NavTimeEvidence(
                evaluation_at=point.at,
                nav_index=index,
                nav_krw=point.equity_krw,
                triggering_close_group=group,
            )
        )
    return PortfolioTimeEvidence(initial_capital=initial, nav=nav)


def _config_bytes(config: TimeEvidenceConfig) -> bytes:
    return _json_bytes(config.model_dump(mode="json"))


def _manifest(
    artifact_bytes: dict[str, bytes],
    *,
    source_sha256: str,
    event_plan_sha256: str,
    config: TimeEvidenceConfig,
    calendar: MarketCalendar,
) -> bytes:
    artifacts = {
        name: {"path": name, "size": len(body), "sha256": sha256_bytes(body)}
        for name, body in artifact_bytes.items()
    }
    payload = {
        "schema_version": SCHEMA_VERSION,
        "policy_version": POLICY_VERSION,
        "source_sha256": source_sha256,
        "event_plan_sha256": event_plan_sha256,
        "calendar": {
            "bytes_sha256": sha256_bytes(artifact_bytes["calendar.json"]),
            "payload_sha256": calendar.calendars_sha256,
            "provider": calendar.provider,
            "provider_version": calendar.provider_version,
        },
        "simulation": {
            "candidate_id": config.candidate.id,
            "period_start": config.period_start.isoformat(),
            "period_end": config.period_end.isoformat(),
            "policy": config.policy,
        },
        "artifacts": artifacts,
    }
    return _json_bytes(payload)


def generate_bundle(
    source: PortfolioInput,
    candidate: PortfolioCandidate,
    start: date,
    end: date,
    config: PortfolioConfig,
    calendar_bytes: bytes,
    output_dir: Path,
    *,
    policy: PortfolioPolicy = "corrected_control",
    allow_new_simulation: bool = False,
) -> BundleVerification:
    """Generate one new bundle; refuse unless explicitly opted in."""

    if not allow_new_simulation:
        raise ValueError("generation requires explicit allow_new_simulation")
    calendar = MarketCalendar.from_bytes(calendar_bytes)
    fixed = TimeEvidenceConfig.from_values(candidate, start, end, config, policy)
    events, data = _event_plan(source, start, end, calendar)
    # This is the only engine simulation call in this module's generation path.
    simulation = engine.simulate(source, candidate, start, end, config, policy)
    _simulation_contract(simulation, fixed)
    sidecar = _build_sidecar(source, fixed, events, data, calendar, simulation)
    input_body = _json_bytes(source.model_dump(mode="json"))
    config_body = _config_bytes(fixed)
    calendar_body = bytes(calendar_bytes)
    simulation_body = _json_bytes(simulation.model_dump(mode="json"))
    sidecar_body = _json_bytes(sidecar.model_dump(mode="json"))
    bodies = {
        "input.json": input_body,
        "config.json": config_body,
        "calendar.json": calendar_body,
        "simulation.json": simulation_body,
        "time-evidence.json": sidecar_body,
    }
    manifest_body = _manifest(
        bodies,
        source_sha256=sha256_bytes(input_body),
        event_plan_sha256=sha256_bytes(_event_plan_bytes(events)),
        config=fixed,
        calendar=calendar,
    )
    staging_dir = _staging_dir(output_dir)
    try:
        for name in ARTIFACT_NAMES:
            _write_bytes_exclusive(staging_dir / name, bodies[name])
        # Manifest is deliberately written last after all immutable artifacts.
        _write_bytes_exclusive(staging_dir / MANIFEST_NAME, manifest_body)
        _fsync_directory(staging_dir)
        os.rename(staging_dir, output_dir)
        _fsync_directory(output_dir.parent)
    except BaseException:
        if staging_dir.exists() and not staging_dir.is_symlink():
            shutil.rmtree(staging_dir)
        raise
    return BundleVerification(
        manifest_sha256=sha256_bytes(manifest_body),
        source_sha256=sha256_bytes(input_body),
        simulation_sha256=sha256_bytes(simulation_body),
        nav_count=len(sidecar.nav),
    )


def _load_bundle_files(
    bundle_dir: Path, expected_manifest_sha256: str
) -> tuple[dict[str, bytes], dict[str, object], str]:
    if bundle_dir.is_symlink() or not bundle_dir.is_dir():
        raise ValueError("bundle directory must be a real directory")
    expected = _digest(expected_manifest_sha256, "expected manifest SHA-256")
    manifest_path = bundle_dir / MANIFEST_NAME
    manifest_body = _regular_file(manifest_path, "manifest")
    actual_manifest_sha = sha256_bytes(manifest_body)
    if actual_manifest_sha != expected:
        raise ValueError("manifest SHA-256 does not match explicit expectation")
    raw_manifest = _strict_json(manifest_body, "manifest")
    if not isinstance(raw_manifest, dict):
        raise ValueError("manifest must be an object")
    required = {
        "schema_version",
        "policy_version",
        "source_sha256",
        "event_plan_sha256",
        "calendar",
        "simulation",
        "artifacts",
    }
    if set(raw_manifest) != required:
        raise ValueError("manifest fields are not exact")
    if raw_manifest["schema_version"] != SCHEMA_VERSION:
        raise ValueError("unsupported manifest schema")
    if raw_manifest["policy_version"] != POLICY_VERSION:
        raise ValueError("unsupported time-evidence policy")
    artifacts = raw_manifest["artifacts"]
    if not isinstance(artifacts, dict) or set(artifacts) != set(ARTIFACT_NAMES):
        raise ValueError("manifest artifact set is not exact")
    files: dict[str, bytes] = {}
    for name, row in artifacts.items():
        safe_name = _safe_artifact_name(name)
        if not isinstance(row, dict) or set(row) != {"path", "size", "sha256"}:
            raise ValueError("manifest artifact metadata is invalid")
        if row["path"] != safe_name or not isinstance(row["size"], int):
            raise ValueError("manifest artifact path or size is invalid")
        digest = _digest(row["sha256"], f"artifact {safe_name} SHA-256")
        body = _regular_file(bundle_dir / safe_name, safe_name)
        if len(body) != row["size"] or sha256_bytes(body) != digest:
            raise ValueError(f"artifact hash or size mismatch: {safe_name}")
        files[safe_name] = body
    actual = {path.name for path in bundle_dir.iterdir()}
    if actual != set(ALL_ARTIFACT_NAMES):
        raise ValueError("bundle contains unexpected or missing files")
    return files, raw_manifest, actual_manifest_sha


def verify_bundle(
    bundle_dir: Path, expected_manifest_sha256: str
) -> BundleVerification:
    """Verify a bundle without invoking ``research_portfolio_engine.simulate``."""

    files, manifest, manifest_sha = _load_bundle_files(
        bundle_dir, expected_manifest_sha256
    )
    source = _load_model_bytes(files["input.json"], PortfolioInput, "input.json")
    fixed = _load_model_bytes(files["config.json"], TimeEvidenceConfig, "config.json")
    calendar_body = files["calendar.json"]
    calendar = MarketCalendar.from_bytes(calendar_body)
    simulation = _load_model_bytes(
        files["simulation.json"], PortfolioSimulation, "simulation.json"
    )
    sidecar = _load_model_bytes(
        files["time-evidence.json"], PortfolioTimeEvidence, "time-evidence.json"
    )
    assert isinstance(source, PortfolioInput)
    assert isinstance(fixed, TimeEvidenceConfig)
    assert isinstance(simulation, PortfolioSimulation)
    assert isinstance(sidecar, PortfolioTimeEvidence)
    if manifest["source_sha256"] != sha256_bytes(files["input.json"]):
        raise ValueError("source SHA-256 mismatch")
    event_plan_sha = _digest(manifest["event_plan_sha256"], "event plan SHA-256")
    calendar_meta = manifest["calendar"]
    if not isinstance(calendar_meta, dict):
        raise ValueError("calendar manifest metadata is invalid")
    if (
        calendar_meta.get("bytes_sha256") != sha256_bytes(calendar_body)
        or calendar_meta.get("payload_sha256") != calendar.calendars_sha256
        or calendar_meta.get("provider") != calendar.provider
        or calendar_meta.get("provider_version") != calendar.provider_version
    ):
        raise ValueError("calendar manifest metadata mismatch")
    simulation_meta = manifest["simulation"]
    if not isinstance(simulation_meta, dict):
        raise ValueError("simulation manifest metadata is invalid")
    if simulation_meta != {
        "candidate_id": fixed.candidate.id,
        "period_start": fixed.period_start.isoformat(),
        "period_end": fixed.period_end.isoformat(),
        "policy": fixed.policy,
    }:
        raise ValueError("simulation manifest metadata mismatch")
    _simulation_contract(simulation, fixed)
    events, data = _event_plan(source, fixed.period_start, fixed.period_end, calendar)
    if event_plan_sha != sha256_bytes(_event_plan_bytes(events)):
        raise ValueError("event plan SHA-256 mismatch")
    expected_sidecar = _build_sidecar(source, fixed, events, data, calendar, simulation)
    if expected_sidecar != sidecar:
        raise ValueError("time-evidence sidecar does not match simulation")
    return BundleVerification(
        manifest_sha256=manifest_sha,
        source_sha256=sha256_bytes(files["input.json"]),
        simulation_sha256=sha256_bytes(files["simulation.json"]),
        nav_count=len(sidecar.nav),
    )


def _load_request(path: Path) -> GenerationRequest:
    model = _load_model_bytes(
        _regular_file(path, "request"), GenerationRequest, "request"
    )
    assert isinstance(model, GenerationRequest)
    return model


def generate_from_request(
    request_path: Path,
    output_dir: Path,
    *,
    allow_new_simulation: bool = False,
) -> BundleVerification:
    request = _load_request(request_path)
    input_path = Path(request.input_path)
    config_path = Path(request.config_path)
    calendar_path = Path(request.calendar_path)
    input_body = _regular_file(input_path, "input")
    config_body = _regular_file(config_path, "config")
    calendar_body = _regular_file(calendar_path, "calendar")
    for body, expected, label in (
        (input_body, request.input_sha256, "input"),
        (config_body, request.config_sha256, "config"),
        (calendar_body, request.calendar_sha256, "calendar"),
    ):
        if expected is not None and sha256_bytes(body) != _digest(expected, label):
            raise ValueError(f"{label} SHA-256 mismatch")
    source = _load_model_bytes(input_body, PortfolioInput, "input")
    config_model = _load_model_bytes(config_body, TimeEvidenceConfig, "config")
    assert isinstance(source, PortfolioInput)
    assert isinstance(config_model, TimeEvidenceConfig)
    return generate_bundle(
        source,
        config_model.candidate,
        config_model.period_start,
        config_model.period_end,
        config_model.portfolio_config,
        calendar_body,
        output_dir,
        policy=config_model.policy,
        allow_new_simulation=allow_new_simulation,
    )


def generate(*args: object, **kwargs: object) -> BundleVerification:
    """Short public alias for callers that use the adapter as a library."""

    return generate_bundle(*args, **kwargs)  # type: ignore[arg-type]


def verify(bundle_dir: Path, expected_manifest_sha256: str) -> BundleVerification:
    """Short public alias for the read-only verifier."""

    return verify_bundle(bundle_dir, expected_manifest_sha256)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    generate = subparsers.add_parser("generate")
    generate.add_argument("--request", type=Path)
    generate.add_argument("--input", type=Path)
    generate.add_argument("--config", type=Path)
    generate.add_argument("--calendar", type=Path)
    generate.add_argument("--output-dir", type=Path, required=True)
    generate.add_argument("--allow-new-simulation", action="store_true")
    verify = subparsers.add_parser("verify")
    verify.add_argument("--bundle-dir", type=Path, required=True)
    verify.add_argument("--expected-manifest-sha256", required=True)
    args = parser.parse_args(argv)
    if args.command == "generate":
        if args.request is not None:
            result = generate_from_request(
                args.request,
                args.output_dir,
                allow_new_simulation=args.allow_new_simulation,
            )
        elif (
            args.input is not None
            and args.config is not None
            and args.calendar is not None
        ):
            # Direct paths still go through the same fixed-file loader.
            input_body = _regular_file(args.input, "input")
            config_body = _regular_file(args.config, "config")
            calendar_body = _regular_file(args.calendar, "calendar")
            source = _load_model_bytes(input_body, PortfolioInput, "input")
            fixed = _load_model_bytes(config_body, TimeEvidenceConfig, "config")
            assert isinstance(source, PortfolioInput)
            assert isinstance(fixed, TimeEvidenceConfig)
            result = generate_bundle(
                source,
                fixed.candidate,
                fixed.period_start,
                fixed.period_end,
                fixed.portfolio_config,
                calendar_body,
                args.output_dir,
                policy=fixed.policy,
                allow_new_simulation=args.allow_new_simulation,
            )
        else:
            parser.error(
                "generate requires --request or --input, --config and --calendar"
            )
    else:
        result = verify_bundle(args.bundle_dir, args.expected_manifest_sha256)
    print(json.dumps(result.model_dump(mode="json"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
