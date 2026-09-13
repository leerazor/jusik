from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import pytest

from jusik.research_portfolio_offline_repair import (
    OfflineRepairError,
    _repair_source,
    _write_exclusive,
    materialize_repaired_sources,
    resolve_source_paths,
    validate_terminal_accounting,
)


@dataclass
class _Point:
    equity_krw: Decimal
    cash_krw: Decimal


@dataclass
class _Metrics:
    final_equity_krw: Decimal


@dataclass
class _Simulation:
    equity: list[_Point]
    metrics: _Metrics


def _simulation(cash: str = "900", nav: str = "1000") -> _Simulation:
    return _Simulation(
        equity=[_Point(Decimal(nav), Decimal(cash))],
        metrics=_Metrics(Decimal(nav)),
    )


def test_resolve_source_paths_prefers_canonical_schema() -> None:
    paths = {"source-manifest.json": "/tmp/source-manifest.json"}
    resolved = resolve_source_paths({"source_paths": paths})
    assert resolved.as_json() == paths


def test_resolve_source_paths_accepts_legacy_alias_only() -> None:
    paths = {"source-manifest.json": "/tmp/source-manifest.json"}
    assert resolve_source_paths({"input_paths": paths}).as_json() == paths


def test_resolve_source_paths_rejects_conflicting_aliases() -> None:
    with pytest.raises(OfflineRepairError, match="disagree"):
        resolve_source_paths(
            {
                "source_paths": {"source-manifest.json": "/tmp/a"},
                "input_paths": {"source-manifest.json": "/tmp/b"},
            }
        )


def test_resolve_source_paths_rejects_malformed_present_canonical_key() -> None:
    with pytest.raises(OfflineRepairError, match="source_paths"):
        resolve_source_paths(
            {
                "source_paths": None,
                "input_paths": {"source-manifest.json": "/tmp/a"},
            }
        )


def test_repair_source_patches_each_reviewed_callsite() -> None:
    cadence = (
        b"from jusik.research_portfolio_models import (\n"
        b"    PortfolioConfig,\n"
        b"    PortfolioSimulation,\n"
        b")\n"
        b'    manifest_paths = prereg.get("input_paths") or '
        b'prereg.get("source_paths")\n'
        b'            "source_paths": prereg["input_paths"],\n'
    )
    calendar = (
        b"from jusik.research_portfolio_models import (\n"
        b"    PortfolioConfig,\n"
        b")\n"
        b"    residual += abs(cash + terminal - simulation.metrics.final_equity_krw)\n"
    )
    repaired_cadence = _repair_source("cadence.py", cadence)
    repaired_calendar = _repair_source("calendar.py", calendar)
    assert repaired_cadence.count(b"resolve_source_paths(prereg).as_json()") == 2
    assert b"input_paths" not in repaired_cadence
    assert (
        b"validate_terminal_accounting(simulation, cash, terminal" in repaired_calendar
    )
    assert b"residual += abs(cash + terminal" in repaired_calendar


def test_materialize_repaired_sources_rejects_nonexclusive_output(
    tmp_path: Path,
) -> None:
    output = tmp_path / "materialized"
    output.mkdir()
    (output / "existing").write_text("x", encoding="utf-8")
    with pytest.raises(OfflineRepairError, match="new or empty"):
        materialize_repaired_sources(tmp_path / "missing-originals", output)


def test_materialize_repaired_sources_rejects_unpinned_source(
    tmp_path: Path,
) -> None:
    originals = tmp_path / "originals"
    originals.mkdir()
    (originals / "cadence.py").write_bytes(b"tampered")
    (originals / "calendar.py").write_bytes(b"tampered")
    output = tmp_path / "repaired"
    with pytest.raises(OfflineRepairError, match="SHA-256 mismatch"):
        materialize_repaired_sources(originals, output)
    assert not any(output.iterdir())


def test_exclusive_collision_preserves_existing_file(tmp_path: Path) -> None:
    path = tmp_path / "materialization-manifest.json"
    path.write_bytes(b"foreign\n")
    with pytest.raises(OfflineRepairError, match="already exists"):
        _write_exclusive(path, b"replacement\n")
    assert path.read_bytes() == b"foreign\n"


def test_terminal_accounting_matches_cash_and_both_navs() -> None:
    validate_terminal_accounting(
        _simulation(),
        Decimal("900"),
        Decimal("100"),
        residuals={"existing": Decimal("0.000001")},
    )


def test_terminal_cash_mutation_is_rejected() -> None:
    with pytest.raises(OfflineRepairError, match="terminal cash residual"):
        validate_terminal_accounting(
            _simulation(cash="901"), Decimal("900"), Decimal("100")
        )


def test_terminal_nav_mutations_are_rejected_independently() -> None:
    with pytest.raises(OfflineRepairError, match="metrics final NAV"):
        validate_terminal_accounting(
            _Simulation(
                [_Point(Decimal("1000"), Decimal("900"))], _Metrics(Decimal("1001"))
            ),
            Decimal("900"),
            Decimal("100"),
        )
    with pytest.raises(OfflineRepairError, match="equity final NAV"):
        validate_terminal_accounting(
            _Simulation(
                [_Point(Decimal("1001"), Decimal("900"))], _Metrics(Decimal("1000"))
            ),
            Decimal("900"),
            Decimal("100"),
        )


def test_terminal_accounting_accepts_exact_tolerance_and_zero_values() -> None:
    validate_terminal_accounting(
        _simulation(cash="0", nav="0"),
        Decimal("0"),
        Decimal("0"),
        residuals={"rounding": Decimal("0.000001")},
    )


@pytest.mark.parametrize("field", ["cash", "position", "metrics", "equity"])
def test_terminal_accounting_rejects_nonfinite_compared_values(field: str) -> None:
    simulation = _simulation()
    cash = Decimal("900")
    position = Decimal("100")
    if field == "cash":
        cash = Decimal("NaN")
    elif field == "position":
        position = Decimal("Infinity")
    elif field == "metrics":
        simulation.metrics.final_equity_krw = Decimal("NaN")
    else:
        simulation.equity[-1].equity_krw = Decimal("Infinity")
    with pytest.raises(OfflineRepairError, match="finite"):
        validate_terminal_accounting(simulation, cash, position)


@pytest.mark.parametrize(
    "simulation",
    [
        _Simulation([], _Metrics(Decimal("0"))),
        _Simulation([_Point(Decimal("NaN"), Decimal("0"))], _Metrics(Decimal("0"))),
        _Simulation(
            [_Point(Decimal("0"), Decimal("0"))], _Metrics(Decimal("Infinity"))
        ),
    ],
)
def test_terminal_accounting_rejects_empty_or_nonfinite(
    simulation: _Simulation,
) -> None:
    with pytest.raises(OfflineRepairError):
        validate_terminal_accounting(simulation, Decimal("0"), Decimal("0"))


def test_existing_residual_gate_is_preserved() -> None:
    with pytest.raises(OfflineRepairError, match="trade residual"):
        validate_terminal_accounting(
            _simulation(),
            Decimal("900"),
            Decimal("100"),
            residuals={"trade": Decimal("0.000002")},
        )
