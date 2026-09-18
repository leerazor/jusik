"""Fail-closed helpers for repairing preserved offline portfolio research.

The materializer copies preserved legacy source files, verifies their pinned
SHA-256 values, and applies only the two reviewed textual repairs.  It never
imports or executes the copied code.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Protocol

REPAIR_BLOCKED_REASONS_SHA256 = (
    "d9a69255491ef018f8e971b2e9c4adb66ffeff29a9f50bc00a06971f8a5d80a4"
)
PINNED_ORIGINAL_SHA256: Mapping[str, str] = {
    "cadence.py": "ccbd30d159a657c6a93947a4f11e65a067a06f9f051dcb5426bc5ed5ff4b8e9c",
    "calendar.py": "cf5c59736de1b49c423dba46c443c33f6d3cbeab39d52d5454821eb867f6cf5a",
}
REPAIRED_SOURCE_NAMES: Mapping[str, str] = {
    "cadence.py": "research_portfolio_rebalance_cadence_cost_stress.py",
    "calendar.py": "research_portfolio_session_calendar_stress.py",
}
TOLERANCE_KRW = Decimal("0.000001")


class OfflineRepairError(ValueError):
    """A preserved-input, patch, or accounting gate failed."""


class EquityPoint(Protocol):
    @property
    def equity_krw(self) -> Decimal: ...

    @property
    def cash_krw(self) -> Decimal: ...


class Metrics(Protocol):
    @property
    def final_equity_krw(self) -> Decimal: ...


class Simulation(Protocol):
    @property
    def equity(self) -> Sequence[EquityPoint]: ...

    @property
    def metrics(self) -> Metrics: ...


@dataclass(frozen=True)
class SourcePaths:
    """Canonical source paths from a frozen preregistration."""

    paths: dict[str, Path]

    def as_json(self) -> dict[str, str]:
        return {name: str(path) for name, path in self.paths.items()}


@dataclass(frozen=True)
class MaterializedCode:
    """Verified original and repaired source copies."""

    output_dir: Path
    paths: dict[str, Path]
    original_sha256: dict[str, str]
    repaired_sha256: dict[str, str]


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _path_mapping(value: object, key: str) -> dict[str, Path]:
    if not isinstance(value, Mapping) or not value:
        raise OfflineRepairError(f"{key} must be a non-empty object")
    result: dict[str, Path] = {}
    for name, raw_path in value.items():
        if not isinstance(name, str) or not name or Path(name).name != name:
            raise OfflineRepairError(f"{key} contains an invalid source name")
        if not isinstance(raw_path, str) or not raw_path:
            raise OfflineRepairError(f"{key}.{name} must be a non-empty path")
        path = Path(raw_path).expanduser()
        if not path.is_absolute():
            raise OfflineRepairError(f"{key}.{name} must be absolute")
        result[name] = path.resolve()
    return result


def resolve_source_paths(preregistration: Mapping[str, object]) -> SourcePaths:
    """Resolve the ``source_paths`` contract at every metadata boundary.

    ``input_paths`` remains a compatibility alias for preserved metadata.  A
    present but malformed ``source_paths`` is rejected, and both keys must
    agree when present; no fallback can hide a schema mismatch.
    """

    has_source = "source_paths" in preregistration
    has_input = "input_paths" in preregistration
    if not has_source and not has_input:
        raise OfflineRepairError("preregistration has no source_paths")
    source = (
        _path_mapping(preregistration.get("source_paths"), "source_paths")
        if has_source
        else {}
    )
    legacy = (
        _path_mapping(preregistration.get("input_paths"), "input_paths")
        if has_input
        else {}
    )
    if source and legacy and source != legacy:
        raise OfflineRepairError("source_paths and input_paths disagree")
    return SourcePaths(source or legacy)


def _write_exclusive(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise OfflineRepairError(f"materialized file already exists: {path}") from exc
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(body)
            output.flush()
            os.fsync(output.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def _patch_once(body: bytes, old: bytes, new: bytes, label: str) -> bytes:
    count = body.count(old)
    if count != 1:
        raise OfflineRepairError(f"{label} expected one occurrence, found {count}")
    return body.replace(old, new, 1)


def _patch_one_of(body: bytes, olds: Sequence[bytes], new: bytes, label: str) -> bytes:
    matches = [(old, body.count(old)) for old in olds]
    if sum(count for _, count in matches) != 1:
        found = sum(count for _, count in matches)
        raise OfflineRepairError(f"{label} expected one occurrence, found {found}")
    old = next(old for old, count in matches if count == 1)
    return body.replace(old, new, 1)


def _repair_source(name: str, body: bytes) -> bytes:
    if name == "cadence.py":
        import_line = (
            b"from jusik.research_portfolio_offline_repair import "
            b"resolve_source_paths\n"
        )
        body = _patch_once(
            body,
            b"from jusik.research_portfolio_models import (\n",
            import_line + b"from jusik.research_portfolio_models import (\n",
            "cadence helper import",
        )
        body = _patch_one_of(
            body,
            (
                b'    manifest_paths = prereg.get("input_paths")\n',
                (
                    b'    manifest_paths = prereg.get("input_paths") or '
                    b'prereg.get("source_paths")\n'
                ),
            ),
            b"    manifest_paths = resolve_source_paths(prereg).as_json()\n",
            "cadence source resolver",
        )
        body = _patch_once(
            body,
            b'            "source_paths": prereg["input_paths"],\n',
            b'            "source_paths": resolve_source_paths(prereg).as_json(),\n',
            "cadence metadata resolver",
        )
    elif name == "calendar.py":
        import_line = (
            b"from jusik.research_portfolio_offline_repair import "
            b"validate_terminal_accounting\n"
        )
        body = _patch_once(
            body,
            b"from jusik.research_portfolio_models import (\n",
            import_line + b"from jusik.research_portfolio_models import (\n",
            "calendar helper import",
        )
        body = _patch_once(
            body,
            (
                b"    residual += abs(cash + terminal - "
                b"simulation.metrics.final_equity_krw)\n"
            ),
            (
                b"    validate_terminal_accounting(simulation, cash, terminal)\n"
                b"    residual += abs(cash + terminal - "
                b"simulation.metrics.final_equity_krw)\n"
            ),
            "calendar terminal validator",
        )
    else:
        raise OfflineRepairError(f"unsupported preserved source: {name}")
    return body


def materialize_repaired_sources(
    originals_dir: Path,
    output_dir: Path,
) -> MaterializedCode:
    """Verify and copy the preserved cadence/calendar sources with repairs."""

    originals_dir = originals_dir.resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists() and (not output_dir.is_dir() or any(output_dir.iterdir())):
        raise OfflineRepairError("materialization output must be new or empty")
    if not originals_dir.is_dir():
        raise OfflineRepairError("originals directory is unavailable")
    names = tuple(PINNED_ORIGINAL_SHA256)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    original_digests: dict[str, str] = {}
    repaired_digests: dict[str, str] = {}
    try:
        for name in names:
            source = originals_dir / name
            if not source.is_file():
                raise OfflineRepairError(f"preserved source is unavailable: {name}")
            body = source.read_bytes()
            original_digest = hashlib.sha256(body).hexdigest()
            if original_digest != PINNED_ORIGINAL_SHA256[name]:
                raise OfflineRepairError(f"preserved source SHA-256 mismatch: {name}")
            repaired = _repair_source(name, body)
            destination = output_dir / REPAIRED_SOURCE_NAMES[name]
            _write_exclusive(destination, repaired)
            paths[name] = destination
            original_digests[name] = original_digest
            repaired_digests[name] = hashlib.sha256(repaired).hexdigest()
        manifest = {
            "original_sha256": original_digests,
            "repaired_sha256": repaired_digests,
            "files": {name: str(path) for name, path in paths.items()},
        }
        _write_exclusive(
            output_dir / "materialization-manifest.json",
            (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode(),
        )
    except BaseException:
        for path in paths.values():
            path.unlink(missing_ok=True)
        raise
    return MaterializedCode(output_dir, paths, original_digests, repaired_digests)


def _finite(value: Decimal, label: str) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise OfflineRepairError(f"{label} must be finite")
    return value


def validate_terminal_accounting(
    simulation: Simulation,
    reconstructed_cash: Decimal,
    terminal_position_value: Decimal,
    *,
    residuals: Mapping[str, Decimal] | None = None,
) -> None:
    """Compare reconstructed cash and NAV with both terminal representations."""

    if not simulation.equity:
        raise OfflineRepairError("equity must contain a terminal point")
    reconstructed_cash = _finite(reconstructed_cash, "reconstructed cash")
    terminal_position_value = _finite(
        terminal_position_value, "terminal position value"
    )
    terminal = simulation.equity[-1]
    terminal_cash = _finite(terminal.cash_krw, "terminal equity cash")
    terminal_equity = _finite(terminal.equity_krw, "terminal equity NAV")
    metrics_equity = _finite(simulation.metrics.final_equity_krw, "metrics final NAV")
    if abs(reconstructed_cash - terminal_cash) > TOLERANCE_KRW:
        raise OfflineRepairError("terminal cash residual exceeds tolerance")
    reconstructed_nav = reconstructed_cash + terminal_position_value
    if abs(reconstructed_nav - metrics_equity) > TOLERANCE_KRW:
        raise OfflineRepairError("metrics final NAV residual exceeds tolerance")
    if abs(reconstructed_nav - terminal_equity) > TOLERANCE_KRW:
        raise OfflineRepairError("equity final NAV residual exceeds tolerance")
    for label, residual in (residuals or {}).items():
        if abs(_finite(residual, f"{label} residual")) > TOLERANCE_KRW:
            raise OfflineRepairError(f"{label} residual exceeds tolerance")


_resolve_source_paths = resolve_source_paths
_materialize_repaired_sources = materialize_repaired_sources
_validate_terminal_accounting = validate_terminal_accounting


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("originals_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args(argv)
    result = materialize_repaired_sources(args.originals_dir, args.output_dir)
    print(
        json.dumps(
            {"output_dir": str(result.output_dir), "files": sorted(result.paths)}
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
