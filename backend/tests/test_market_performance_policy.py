from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal, DefaultContext
from pathlib import Path

import pytest

import jusik.market_performance_metrics as metrics
import jusik.market_performance_policy as policy
from jusik.market_performance_metrics import (
    CompletenessEvidence,
    CostInclusionEvidence,
    DataSource,
    NAVPoint,
    PerformanceInput,
    RiskFreeEvidence,
    evaluate_performance,
)
from jusik.market_performance_policy import (
    PolicyValidationError,
    canonical_policy_bytes,
    load_calculation_policy,
)


def test_registered_policy_is_canonical_and_pinned() -> None:
    body = policy.POLICY_PATH.read_bytes()
    assert len(body) <= policy.MAX_POLICY_BYTES
    assert hashlib.sha256(body).hexdigest() == policy.POLICY_SHA256
    loaded = load_calculation_policy()
    assert canonical_policy_bytes(loaded) == body
    implementation = loaded["implementation"]
    assert isinstance(implementation, dict)
    assert (
        hashlib.sha256(policy.EVALUATOR_PATH.read_bytes()).hexdigest()
        == (implementation["evaluator_source_sha256"])
    )
    scope = loaded["scope"]
    assert scope == {
        "application": "forward-only",
        "historical_application_proven": False,
    }


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        (lambda value: value.__setitem__("id", "changed"), "policy_sha_mismatch"),
        (lambda value: value.__setitem__("extra", True), "policy_sha_mismatch"),
    ],
)
def test_policy_tamper_is_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: Callable[[dict[str, object]], None],
    code: str,
) -> None:
    payload = json.loads(policy.POLICY_PATH.read_bytes())
    assert isinstance(payload, dict)
    mutation(payload)
    tampered = tmp_path / "policy.json"
    tampered.write_bytes(canonical_policy_bytes(payload))
    monkeypatch.setattr(policy, "POLICY_PATH", tampered)
    with pytest.raises(PolicyValidationError) as error:
        load_calculation_policy()
    assert error.value.code == code


def test_policy_rejects_noncanonical_duplicate_and_float_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_bytes(b'{"schema":"x","schema":"y"}')
    monkeypatch.setattr(policy, "POLICY_PATH", duplicate)
    monkeypatch.setattr(
        policy, "POLICY_SHA256", hashlib.sha256(duplicate.read_bytes()).hexdigest()
    )
    with pytest.raises(PolicyValidationError) as error:
        load_calculation_policy()
    assert error.value.code == "policy_malformed"

    floating = tmp_path / "float.json"
    floating.write_bytes(b'{"schema":1.0}')
    monkeypatch.setattr(policy, "POLICY_PATH", floating)
    monkeypatch.setattr(
        policy, "POLICY_SHA256", hashlib.sha256(floating.read_bytes()).hexdigest()
    )
    with pytest.raises(PolicyValidationError) as error:
        load_calculation_policy()
    assert error.value.code == "policy_malformed"


def test_policy_rejects_oversized_bytes_with_stable_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    oversized = tmp_path / "oversized-policy.json"
    body = policy.POLICY_PATH.read_bytes() + b" " * (policy.MAX_POLICY_BYTES + 1)
    oversized.write_bytes(body)
    monkeypatch.setattr(policy, "POLICY_PATH", oversized)
    monkeypatch.setattr(policy, "POLICY_SHA256", hashlib.sha256(body).hexdigest())
    with pytest.raises(PolicyValidationError) as error:
        load_calculation_policy()
    assert error.value.code == "policy_too_large"


def test_policy_rejects_nonfinite_token_after_matching_sha(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "nonfinite-policy.json"
    body = policy.POLICY_PATH.read_bytes().replace(
        b'"historical_application_proven":false',
        b'"historical_application_proven":NaN',
        1,
    )
    path.write_bytes(body)
    monkeypatch.setattr(policy, "POLICY_PATH", path)
    monkeypatch.setattr(policy, "POLICY_SHA256", hashlib.sha256(body).hexdigest())
    with pytest.raises(PolicyValidationError) as error:
        load_calculation_policy()
    assert error.value.code == "policy_malformed"


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        (lambda value: value.__setitem__("extra", True), "policy_unsupported_schema"),
        (lambda value: value.__setitem__("scope", "forward-only"), "policy_malformed"),
    ],
)
def test_policy_schema_guards_are_reached_after_matching_sha(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: Callable[[dict[str, object]], None],
    code: str,
) -> None:
    payload = json.loads(policy.POLICY_PATH.read_bytes())
    assert isinstance(payload, dict)
    mutation(payload)
    path = tmp_path / "schema-policy.json"
    body = canonical_policy_bytes(payload)
    path.write_bytes(body)
    monkeypatch.setattr(policy, "POLICY_PATH", path)
    monkeypatch.setattr(policy, "POLICY_SHA256", hashlib.sha256(body).hexdigest())
    with pytest.raises(PolicyValidationError) as error:
        load_calculation_policy()
    assert error.value.code == code


def test_updated_internal_source_sha_cannot_bypass_pinned_policy_sha(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = json.loads(policy.POLICY_PATH.read_bytes())
    assert isinstance(payload, dict)
    implementation = payload["implementation"]
    assert isinstance(implementation, dict)
    implementation["evaluator_source_sha256"] = "f" * 64
    path = tmp_path / "updated-source-sha-policy.json"
    path.write_bytes(canonical_policy_bytes(payload))
    monkeypatch.setattr(policy, "POLICY_PATH", path)
    with pytest.raises(PolicyValidationError) as error:
        load_calculation_policy()
    assert error.value.code == "policy_sha_mismatch"


def test_evaluator_source_drift_reaches_implementation_sha_guard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    drifted = tmp_path / "drifted-evaluator.py"
    drifted.write_bytes(policy.EVALUATOR_PATH.read_bytes() + b"\n# drift\n")
    monkeypatch.setattr(policy, "EVALUATOR_PATH", drifted)
    with pytest.raises(PolicyValidationError) as error:
        load_calculation_policy()
    assert error.value.code == "evaluator_source_sha_mismatch"


def test_evaluator_uses_explicit_context_without_default_context_dependency() -> None:
    input_value = PerformanceInput(
        initial_capital=Decimal("100"),
        initial_capital_at=datetime(2024, 1, 1, tzinfo=UTC),
        nav_points=(
            NAVPoint(datetime(2024, 1, 1, tzinfo=UTC), Decimal("100")),
            NAVPoint(datetime(2024, 1, 3, tzinfo=UTC), Decimal("105")),
        ),
        data_grade="fixture",
        data_source=DataSource("offline"),
        completeness=CompletenessEvidence("complete", ("coverage",), ("calendar",)),
        cost_inclusion=CostInclusionEvidence(True, ("statement",)),
        risk_free=RiskFreeEvidence(Decimal("0"), ("policy",)),
        calculation_policy=policy.POLICY_ID,
    )
    expected = evaluate_performance(input_value)
    original = DefaultContext.copy()
    try:
        DefaultContext.prec = 6
        actual = evaluate_performance(input_value)
        assert actual.as_dict() == expected.as_dict()
        assert metrics.DECIMAL_CONTEXT.prec == 50
        assert metrics.DECIMAL_CONTEXT.rounding == "ROUND_HALF_EVEN"
    finally:
        DefaultContext.prec = original.prec
        DefaultContext.rounding = original.rounding
