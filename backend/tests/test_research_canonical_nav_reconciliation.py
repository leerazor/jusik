from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from pathlib import Path

import pytest

import jusik.market_performance_readiness as readiness
import jusik.research_canonical_nav_reconciliation as adapter


def test_canonical_adapter_accepts_registered_chain_and_is_deterministic() -> None:
    run_before = adapter.CANONICAL_RUN_PATH.read_bytes()
    first = adapter.reconcile_canonical_nav()
    second = adapter.reconcile_canonical_nav()

    assert first == second
    assert first["schema"] == adapter.SCHEMA
    assert first["status"] == "passed"
    residual = first["residual"]
    assert residual["source_sha256"] == readiness.CANONICAL_RUN_SHA256
    assert residual["rows"] == 252
    assert residual["failed_sessions"] == []
    assert first["canonical"]["coverage"]["calendar"]["availability"] == "verified"
    assert (
        first["canonical"]["coverage"]["independent_modeled_accounting"]["availability"]
        == "verified"
    )
    assert first["accounting"]["trade_count"] == 106
    assert first["accounting"]["session_count"] == 252
    assert adapter.CANONICAL_RUN_PATH.read_bytes() == run_before


def test_adapter_calls_each_public_evidence_seam_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_facts = deepcopy(adapter.verify_canonical_session_evidence())
    cost_facts = deepcopy(adapter.verify_canonical_cost_evidence())
    calls = {"session": 0, "cost": 0}

    def session() -> dict[str, object]:
        calls["session"] += 1
        return session_facts

    def cost() -> dict[str, object]:
        calls["cost"] += 1
        return cost_facts

    monkeypatch.setattr(adapter, "verify_canonical_session_evidence", session)
    monkeypatch.setattr(adapter, "verify_canonical_cost_evidence", cost)
    result = adapter.reconcile_canonical_nav()

    assert result["status"] == "passed"
    assert calls == {"session": 1, "cost": 1}


def test_session_verifier_does_not_enter_whole_readiness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        readiness,
        "diagnose_run",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected")),
    )
    facts = readiness.verify_canonical_session_evidence()
    assert facts["run_sha256"] == readiness.CANONICAL_RUN_SHA256
    assert facts["observed_count"] == 252


def test_session_verifier_rejects_symlink_and_hardlink_aliases(
    tmp_path: Path,
) -> None:
    symlink = tmp_path / "run-symlink.json"
    symlink.symlink_to(adapter.CANONICAL_RUN_PATH)
    with pytest.raises(readiness.ReadinessInputError) as symlink_error:
        readiness.verify_canonical_session_evidence(symlink)
    assert symlink_error.value.code == "canonical_run_path_required"

    hardlink = tmp_path / "run-hardlink.json"
    try:
        hardlink.hardlink_to(adapter.CANONICAL_RUN_PATH)
    except OSError as error:
        pytest.skip(f"hardlinks unavailable: {error}")
    with pytest.raises(readiness.ReadinessInputError) as hardlink_error:
        readiness.verify_canonical_session_evidence(hardlink)
    assert hardlink_error.value.code == "canonical_run_path_required"


@pytest.mark.parametrize(
    ("limit", "error"),
    [
        (adapter.MAX_COST_MANIFEST_BYTES, "manifest_too_large"),
        (adapter.MAX_COST_DATASET_BYTES, "dataset_too_large"),
        (adapter.MAX_COST_EVIDENCE_BYTES, "evidence_too_large"),
    ],
)
def test_adapter_artifact_reads_are_bounded(
    tmp_path: Path, limit: int, error: str
) -> None:
    path = tmp_path / "oversized.json"
    path.write_bytes(b"x" * (limit + 1))
    with pytest.raises(adapter.CanonicalNavError, match=error):
        adapter._bounded_artifact(path, limit, error)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda facts: facts.__setitem__("run_sha256", "0" * 64),
        lambda facts: facts.__setitem__("manifest_sha256", "0" * 64),
        lambda facts: facts.__setitem__("observed_sessions", []),
        lambda facts: facts.__setitem__(
            "period", {"start_date": "2025-09-10", "end_date": "2026-09-11"}
        ),
    ],
)
def test_identity_mismatch_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    mutation: Callable[[dict[str, object]], None],
) -> None:
    session_facts = deepcopy(adapter.verify_canonical_session_evidence())
    cost_facts = deepcopy(adapter.verify_canonical_cost_evidence())
    mutation(session_facts)
    monkeypatch.setattr(
        adapter, "verify_canonical_session_evidence", lambda: session_facts
    )
    monkeypatch.setattr(adapter, "verify_canonical_cost_evidence", lambda: cost_facts)

    with pytest.raises(adapter.CanonicalNavError):
        adapter.reconcile_canonical_nav()


@pytest.mark.parametrize(
    "mutation",
    [
        lambda facts: facts["artifacts"].__setitem__("run", "0" * 64),
        lambda facts: facts["artifacts"].__setitem__("manifest", "0" * 64),
        lambda facts: facts["artifacts"].__setitem__("dataset", "0" * 64),
        lambda facts: facts.__setitem__("trade_count", 105),
        lambda facts: facts.__setitem__("session_count", 251),
        lambda facts: facts.__setitem__("accounting_digest", "z" * 64),
    ],
)
def test_cost_identity_and_accounting_mismatch_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    mutation: Callable[[dict[str, object]], None],
) -> None:
    session_facts = deepcopy(adapter.verify_canonical_session_evidence())
    cost_facts = deepcopy(adapter.verify_canonical_cost_evidence())
    mutation(cost_facts)
    monkeypatch.setattr(
        adapter, "verify_canonical_session_evidence", lambda: session_facts
    )
    monkeypatch.setattr(adapter, "verify_canonical_cost_evidence", lambda: cost_facts)

    with pytest.raises(adapter.CanonicalNavError):
        adapter.reconcile_canonical_nav()


def test_missing_evidence_is_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing() -> dict[str, object]:
        raise readiness.ReadinessInputError("evidence_unavailable")

    monkeypatch.setattr(adapter, "verify_canonical_session_evidence", missing)
    with pytest.raises(adapter.CanonicalNavError) as error:
        adapter.reconcile_canonical_nav()
    assert error.value.code == "evidence_unavailable"
