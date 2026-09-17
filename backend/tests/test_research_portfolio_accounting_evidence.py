from __future__ import annotations

import ast
import json
import os
import shutil
from datetime import datetime
from decimal import Context, Decimal, getcontext, setcontext
from pathlib import Path

import pytest

from jusik.research_portfolio_accounting_evidence import (
    MANIFEST_SHA256,
    AccountingEvidenceError,
    _apply_close_marks,
    _asof_fx,
    _read_engine_source,
    _scan_artifact_paths,
    _split_adjustment,
    _validate_terminal_positions,
    verify_accounting_bundle,
)

BUNDLE = Path(
    "/home/kwl/.local/share/jusik/portfolio-audit/"
    "forward-simulation-time-evidence-run/run-gr68c4/"
    "bundle-continuous-official"
)


def _require_bundle() -> None:
    if not BUNDLE.is_dir():
        pytest.skip("registered audit bundle is not available")


def test_registered_bundle_consumes_every_row() -> None:
    _require_bundle()
    report = verify_accounting_bundle(BUNDLE, expected_manifest_sha256=MANIFEST_SHA256)
    assert report["trade_count"] == 171
    assert report["nav_count"] == 1172
    assert report["consumed_nav_count"] == 1172
    assert report["max_residual_krw"] == "0"
    assert report["economic_evaluation"] == "not-evaluated"


def test_external_decimal_context_is_not_mutated() -> None:
    _require_bundle()
    original = getcontext().copy()
    setcontext(Context(prec=9))
    try:
        first = verify_accounting_bundle(
            BUNDLE, expected_manifest_sha256=MANIFEST_SHA256
        )
        assert getcontext().prec == 9
        setcontext(Context(prec=80))
        second = verify_accounting_bundle(
            BUNDLE, expected_manifest_sha256=MANIFEST_SHA256
        )
        assert first["accounting_digest"] == second["accounting_digest"]
        assert getcontext().prec == 80
    finally:
        setcontext(original)


def test_asof_fx_uses_available_revision_and_observed_date() -> None:
    rows = [
        (
            datetime.fromisoformat("2024-01-01T00:00:00+00:00"),
            "2023-12-29",
            "a",
            Decimal("1300"),
        ),
        (
            datetime.fromisoformat("2024-01-03T00:00:00+00:00"),
            "2024-01-02",
            "a",
            Decimal("1310"),
        ),
    ]
    assert _asof_fx(
        rows, datetime.fromisoformat("2024-01-03T12:00:00+00:00")
    ) == Decimal("1310")


def test_manifest_tamper_fails_closed(tmp_path: Path) -> None:
    _require_bundle()
    copied = tmp_path / "bundle"
    shutil.copytree(BUNDLE, copied)
    manifest = copied / "manifest.json"
    payload = json.loads(manifest.read_text())
    payload["event_plan_sha256"] = "0" * 64
    manifest.write_text(json.dumps(payload, separators=(",", ":")))
    with pytest.raises(AccountingEvidenceError) as error:
        verify_accounting_bundle(copied, expected_manifest_sha256=MANIFEST_SHA256)
    assert error.value.code == "manifest_sha_mismatch"


def test_verifier_has_no_non_stdlib_or_forbidden_imports() -> None:
    source = (
        Path(__file__).parents[1]
        / "jusik"
        / "research_portfolio_accounting_evidence.py"
    )
    tree = ast.parse(source.read_text())
    imports = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imports.update(
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    )
    assert imports <= {
        "argparse",
        "collections",
        "datetime",
        "decimal",
        "hashlib",
        "json",
        "os",
        "pathlib",
        "re",
        "stat",
        "sys",
        "typing",
        "__future__",
    }
    assert not any(
        name in imports for name in {"requests", "httpx", "sqlalchemy", "fastapi"}
    )


def test_directory_scan_rejects_a_seventh_entry_before_collection(
    tmp_path: Path,
) -> None:
    names = {
        "manifest.json",
        "calendar.json",
        "config.json",
        "input.json",
        "simulation.json",
        "time-evidence.json",
    }
    for name in names:
        (tmp_path / name).write_bytes(b"{}")
    (tmp_path / "hostile-extra").write_bytes(b"x")
    with pytest.raises(AccountingEvidenceError) as error:
        _scan_artifact_paths(tmp_path)
    assert error.value.code == "artifact_set_mismatch"


def test_local_loader_rejects_bundle_symlink(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "bundle-link"
    link.symlink_to(target, target_is_directory=True)
    with pytest.raises(AccountingEvidenceError) as error:
        verify_accounting_bundle(link, expected_manifest_sha256=MANIFEST_SHA256)
    assert error.value.code == "unsafe_path"


def test_engine_source_reader_rejects_symlink_and_oversize(tmp_path: Path) -> None:
    target = tmp_path / "engine.py"
    target.write_bytes(b"engine")
    link = tmp_path / "engine-link.py"
    link.symlink_to(target)
    with pytest.raises(AccountingEvidenceError) as symlink_error:
        _read_engine_source(link)
    assert symlink_error.value.code == "unsafe_path"
    oversized = tmp_path / "oversized.py"
    with oversized.open("wb") as stream:
        stream.truncate(20 * 1024 * 1024 + 1)
    with pytest.raises(AccountingEvidenceError) as size_error:
        _read_engine_source(oversized)
    assert size_error.value.code == "file_too_large"


def test_engine_source_reader_rejects_replacement_race(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "engine.py"
    source.write_bytes(b"engine")
    original_open = os.open

    def replacing_open(
        path: str | os.PathLike[str], flags: int, mode: int = 0o777
    ) -> int:
        if Path(path) == source:
            replacement = tmp_path / "replacement.py"
            replacement.write_bytes(b"replacement")
            source.unlink()
            replacement.rename(source)
        return original_open(path, flags, mode)

    monkeypatch.setattr(os, "open", replacing_open)
    with pytest.raises(AccountingEvidenceError) as error:
        _read_engine_source(source)
    assert error.value.code == "file_replaced"


def test_fractional_split_cash_in_lieu_is_decimal_safe() -> None:
    whole, cash = _split_adjustment(
        1, Decimal("1"), Decimal("2"), Decimal("100"), Decimal("2")
    )
    assert whole == 0
    assert cash == Decimal("100")


def test_asof_fx_rejects_stale_and_future_only_observations() -> None:
    stale = [
        (
            datetime.fromisoformat("2024-01-01T00:00:00+00:00"),
            "2023-12-01",
            "a",
            Decimal("1300"),
        )
    ]
    with pytest.raises(AccountingEvidenceError) as stale_error:
        _asof_fx(stale, datetime.fromisoformat("2024-01-15T00:00:00+00:00"))
    assert stale_error.value.code == "stale_fx"
    future = [
        (
            datetime.fromisoformat("2024-01-15T00:00:00+00:00"),
            "2024-01-15",
            "a",
            Decimal("1300"),
        )
    ]
    with pytest.raises(AccountingEvidenceError) as future_error:
        _asof_fx(future, datetime.fromisoformat("2024-01-14T00:00:00+00:00"))
    assert future_error.value.code == "missing_fx"


def test_same_time_close_group_is_applied_before_nav() -> None:
    bars = {
        ("KR", "2024-01-02"): {"close": "105"},
        ("US", "2024-01-02"): {"close": "205"},
    }
    latest: dict[str, Decimal] = {}
    _apply_close_marks([("US", "2024-01-02"), ("KR", "2024-01-02")], bars, latest)
    # This is the NAV boundary: both same-time marks must be present first.
    assert Decimal("2") * latest["KR"] + Decimal("3") * latest["US"] == Decimal("825")


def test_terminal_quantity_mark_and_value_tampering_is_rejected() -> None:
    observations: list[tuple[datetime, str, str, Decimal]] = []
    final_at = datetime.fromisoformat("2024-01-02T20:00:00+00:00")
    positions: list[object] = [
        {
            "symbol": "KR",
            "quantity": 2,
            "local_close": "105",
            "fx_rate": "1",
            "value_krw": "210",
            "valued_at": "2024-01-02T20:00:00Z",
        }
    ]
    assert (
        _validate_terminal_positions(
            positions,
            {"KR": 2},
            {"KR": Decimal("105")},
            {"KR": "KRW"},
            observations,
            final_at,
        )["KR"]["quantity"]
        == 2
    )
    for field, value in (("quantity", 3), ("local_close", "106"), ("value_krw", "211")):
        tampered = [dict(positions[0], **{field: value})]
        with pytest.raises(AccountingEvidenceError):
            _validate_terminal_positions(
                tampered,
                {"KR": 2},
                {"KR": Decimal("105")},
                {"KR": "KRW"},
                observations,
                final_at,
            )
