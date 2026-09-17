from __future__ import annotations

import ast
import json
import shutil
from datetime import datetime
from decimal import Context, Decimal, getcontext, setcontext
from pathlib import Path

import pytest

from jusik.research_portfolio_accounting_evidence import (
    MANIFEST_SHA256,
    AccountingEvidenceError,
    _asof_fx,
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
