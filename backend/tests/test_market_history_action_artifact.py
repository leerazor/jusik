from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

from jusik.market_history_action_artifact import (
    MAX_INPUT_BYTES,
    ArtifactError,
    build_artifact,
    main,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures/market_history_action_accounting.json"
FIXTURE = cast(dict[str, object], json.loads(FIXTURE_PATH.read_text(encoding="utf-8")))


def _payload(*steps: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": 1,
        "seed": 0,
        "initial_state": {
            "holdings": [
                {
                    "symbol": "AAA",
                    "quantity": "10",
                    "raw_price": "100",
                    "total_cost": "1000",
                    "currency": "KRW",
                }
            ],
            "cash": "0",
            "currency": "KRW",
            "price_basis": "raw",
            "receivables": [],
            "action_records": [],
        },
        "steps": list(steps),
    }


def _split() -> dict[str, object]:
    return {
        "phase": "split",
        "at": "2026-01-01T00:00:00+00:00",
        "action": {
            "kind": "split",
            "action_id": "split-1",
            "symbol": "AAA",
            "effective_at": "2026-01-01T00:00:00+00:00",
            "ratio": "2",
            "currency": "KRW",
            "price_basis": "raw",
            "before_price": "100",
            "after_price": "50",
        },
    }


def _dividend(phase: str = "accrual") -> dict[str, object]:
    return {
        "phase": phase,
        "at": "2026-01-02T00:00:00+00:00",
        "action": {
            "kind": "dividend",
            "action_id": "div-1",
            "symbol": "AAA",
            "effective_at": "2026-01-02T00:00:00+00:00",
            "payment_at": "2026-01-03T00:00:00+00:00",
            "amount_per_share": "1.25",
            "currency": "KRW",
            "entitled_quantity": "20",
            "entitlement_confirmed": True,
            "price_basis": "raw",
        },
    }


def _fixture_envelope(scenario_id: str, phases: tuple[str, ...]) -> dict[str, object]:
    scenarios = cast(list[object], FIXTURE["scenarios"])
    scenario = next(
        cast(dict[str, object], item)
        for item in scenarios
        if cast(dict[str, object], item)["id"] == scenario_id
    )
    state = cast(dict[str, object], scenario["state"])
    action = cast(dict[str, object], scenario["action"])
    action = {"symbol": "AAA", **action}
    holding = {
        "symbol": "AAA",
        "quantity": state["quantity"],
        "raw_price": state["raw_price"],
        "total_cost": state["total_cost"],
        "currency": state["currency"],
    }
    steps: list[dict[str, object]] = []
    for phase in phases:
        at = action["payment_at"] if phase == "payment" else action["effective_at"]
        steps.append({"phase": phase, "at": at, "action": dict(action)})
    return {
        "schema_version": 1,
        "seed": 0,
        "initial_state": {
            "holdings": [holding],
            "cash": state["cash"],
            "currency": state["currency"],
            "price_basis": "raw",
            "receivables": [],
            "action_records": [],
        },
        "steps": steps,
    }


def _transition(artifact: dict[str, object], index: int) -> dict[str, object]:
    transitions = cast(list[object], artifact["transitions"])
    return cast(dict[str, object], transitions[index])


def _result(artifact: dict[str, object], index: int) -> dict[str, object]:
    return cast(dict[str, object], _transition(artifact, index)["result"])


def test_replay_preserves_exact_decimal_state_and_provenance() -> None:
    assert (
        hashlib.sha256(FIXTURE_PATH.read_bytes()).hexdigest()
        == "8df3220ba47d575dad84ff2146a1e575db461fc06536e032b437698ca81ea0f4"
    )
    payload = _payload(_split(), _dividend())
    source = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    artifact = build_artifact(payload, input_bytes=source)
    assert artifact["coverage"] == "incomplete"
    assert artifact["economic_status"] == "not-evaluated"
    assert artifact["input"] == {
        "action": "read-only-offline-json",
        "sha256": hashlib.sha256(source).hexdigest(),
        "size_bytes": len(source),
    }
    transition = _transition(artifact, 0)
    assert _result(artifact, 0)["nav_before"] == "1000"
    assert _result(artifact, 0)["nav_after"] == "1000"
    assert (
        _result(artifact, 0)["identity_hash"]
        == "45d453790b36896729efb0a66a102063f7fc9102d12e46c45db32800e4947efd"
    )
    state_after = cast(dict[str, object], transition["state_after"])
    holding_after = cast(list[object], state_after["holdings"])[0]
    assert cast(dict[str, object], holding_after)["quantity"] == "20"
    assert cast(dict[str, object], holding_after)["raw_price"] == "50"
    assert state_after["nav"] == "1000"


def test_dividend_payment_replays_and_preserves_failed_state() -> None:
    accrual = _dividend()
    payment = _dividend("payment")
    payment["at"] = "2026-01-03T00:00:00+00:00"
    payload = _payload(accrual, payment, payment)
    artifact = build_artifact(payload)
    assert [_result(artifact, index)["status"] for index in range(3)] == [
        "insufficient",
        "insufficient",
        "insufficient",
    ]
    # The accrual entitlement intentionally does not match the post-split
    # holding, proving diagnostic failures leave the prior state unchanged.
    assert artifact["final_state"] == artifact["initial_state"]


def test_fixture_long_decimal_dividend_payment_and_replay() -> None:
    payload = _fixture_envelope(
        "dividend_long_decimal_accrual_payment", ("accrual", "payment", "payment")
    )
    artifact = build_artifact(payload)
    statuses = [_result(artifact, index)["status"] for index in range(3)]
    assert statuses == ["applied", "applied", "replayed"]
    final_state = cast(dict[str, object], artifact["final_state"])
    assert final_state["cash"] == "2.234567890123456789012345678900"
    assert final_state["nav"] == "1236.734567890123456789012345678900"


def test_fixture_conflict_missing_and_utc_cases_remain_diagnostic() -> None:
    conflict = _fixture_envelope("conflicting_action_id", ("split", "split"))
    steps = cast(list[object], conflict["steps"])
    second = cast(dict[str, object], steps[0])
    # The second event keeps the same identity key while changing semantics.
    changed = (
        dict(cast(dict[str, object], steps[1])) if len(steps) > 1 else dict(second)
    )
    changed_action = dict(cast(dict[str, object], changed["action"]))
    changed_action["ratio"] = "3"
    changed_action["after_price"] = "41.15"
    changed["action"] = changed_action
    conflict["steps"] = [steps[0], changed]
    result = build_artifact(conflict)
    assert _result(result, 1)["reason"] == "action_id_conflict"
    missing = build_artifact(_fixture_envelope("missing_entitlement", ("accrual",)))
    assert _result(missing, 0)["status"] == "insufficient"
    utc = build_artifact(
        _fixture_envelope("utc_boundary_holiday_payment", ("accrual", "payment"))
    )
    assert [_result(utc, index)["status"] for index in range(2)] == [
        "applied",
        "applied",
    ]


def test_unsupported_and_malformed_actions_are_diagnostics() -> None:
    adjusted = _split()
    adjusted_action = adjusted["action"]
    assert isinstance(adjusted_action, dict)
    adjusted_action["price_basis"] = "adjusted"
    malformed = _split()
    malformed_action = malformed["action"]
    assert isinstance(malformed_action, dict)
    malformed_action["ratio"] = 2
    artifact = build_artifact(_payload(adjusted, malformed))
    assert _result(artifact, 0)["status"] == "unsupported"
    assert _result(artifact, 1)["status"] == "rejected"
    assert (
        _transition(artifact, 0)["state_before"]
        == _transition(artifact, 0)["state_after"]
    )


def test_explicit_initial_state_and_caps_are_required() -> None:
    payload = _payload()
    initial = payload["initial_state"]
    assert isinstance(initial, dict)
    initial.pop("price_basis")
    try:
        build_artifact(payload)
    except ArtifactError as exc:
        assert "initial_state" in str(exc)
    else:
        raise AssertionError("missing price basis was accepted")
    oversized = {**_payload(), "steps": [_split()] * 81}
    try:
        build_artifact(oversized)
    except ArtifactError as exc:
        assert "step limit" in str(exc)
    else:
        raise AssertionError("step cap was not enforced")


def test_cli_bounded_input_and_output_collision(tmp_path: Path) -> None:
    payload = _payload()
    source = tmp_path / "input.json"
    source.write_text(json.dumps(payload), encoding="utf-8")
    output = tmp_path / "artifact.json"
    assert main(["--input", str(source), "--output", str(output)]) == 0
    original = output.read_bytes()
    assert main(["--input", str(source), "--output", str(output)]) == 2
    assert output.read_bytes() == original
    oversized = tmp_path / "oversized.json"
    oversized.write_bytes(b" " * (MAX_INPUT_BYTES + 1))
    assert (
        main(["--input", str(oversized), "--output", str(tmp_path / "too-large.json")])
        == 2
    )


def test_cli_rejects_symlink_and_hardlink_aliases(tmp_path: Path) -> None:
    payload_path = tmp_path / "input.json"
    payload_path.write_text(json.dumps(_payload()), encoding="utf-8")
    input_link = tmp_path / "input-link.json"
    input_link.symlink_to(payload_path)
    assert (
        main(["--input", str(input_link), "--output", str(tmp_path / "link.json")]) == 2
    )
    alias = tmp_path / "alias.json"
    alias.hardlink_to(payload_path)
    assert main(["--input", str(payload_path), "--output", str(alias)]) == 2
    assert alias.read_bytes() == payload_path.read_bytes()
    output_link = tmp_path / "output-link.json"
    output_link.symlink_to(tmp_path / "new-target.json")
    assert main(["--input", str(payload_path), "--output", str(output_link)]) == 2
    assert output_link.is_symlink()

    real_parent = tmp_path / "real-parent"
    real_parent.mkdir()
    parent_link = tmp_path / "parent-link"
    parent_link.symlink_to(real_parent, target_is_directory=True)
    parent_input = real_parent / "input.json"
    parent_input.write_bytes(payload_path.read_bytes())
    assert (
        main(
            [
                "--input",
                str(parent_link / "input.json"),
                "--output",
                str(parent_link / "artifact.json"),
            ]
        )
        == 2
    )
    assert (
        main(
            [
                "--input",
                str(payload_path),
                "--output",
                str(parent_link / "artifact-output.json"),
            ]
        )
        == 2
    )


def test_invalid_step_is_exit_zero_diagnostic_and_json_is_strict(
    tmp_path: Path,
) -> None:
    invalid = _split()
    invalid["at"] = "0001-01-01T00:00:00+14:00"
    invalid_payload = _payload(invalid)
    invalid_source = tmp_path / "invalid.json"
    invalid_source.write_text(json.dumps(invalid_payload), encoding="utf-8")
    invalid_output = tmp_path / "invalid-artifact.json"
    assert main(["--input", str(invalid_source), "--output", str(invalid_output)]) == 0
    diagnostic = json.loads(invalid_output.read_text(encoding="utf-8"))
    assert diagnostic["transitions"][0]["result"]["status"] == "rejected"
    assert diagnostic["transitions"][0]["input_at"] == invalid["at"]
    assert (
        diagnostic["transitions"][0]["state_before"]
        == diagnostic["transitions"][0]["state_after"]
    )
    assert diagnostic["transitions"][0]["input_action"] == invalid["action"]

    action_timestamp_variants = [
        (_split(), "effective_at", "2026-01-01T00:00:00+00:00"),
        (_dividend("payment"), "payment_at", "2026-01-03T00:00:00+00:00"),
    ]
    for index, (step, field, step_at) in enumerate(action_timestamp_variants):
        step["at"] = step_at
        action = cast(dict[str, object], step["action"])
        action[field] = "0001-01-01T00:00:00+14:00"
        variant_source = tmp_path / f"invalid-action-{index}.json"
        variant_source.write_text(json.dumps(_payload(step)), encoding="utf-8")
        variant_output = tmp_path / f"invalid-action-{index}-artifact.json"
        assert (
            main(["--input", str(variant_source), "--output", str(variant_output)]) == 0
        )
        variant = json.loads(variant_output.read_text(encoding="utf-8"))
        transition = variant["transitions"][0]
        assert transition["result"]["status"] == "rejected"
        assert transition["state_before"] == transition["state_after"]
        assert transition["input_action"] == action

    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"schema_version":1,"schema_version":1}', encoding="utf-8")
    assert (
        main(
            [
                "--input",
                str(duplicate),
                "--output",
                str(tmp_path / "duplicate-out.json"),
            ]
        )
        == 2
    )
    nan = tmp_path / "nan.json"
    nan.write_text(
        '{"schema_version":1,"seed":0,"initial_state":NaN,"steps":[]}',
        encoding="utf-8",
    )
    assert main(["--input", str(nan), "--output", str(tmp_path / "nan-out.json")]) == 2


def test_equal_utc_boundaries_are_accepted() -> None:
    step = _split()
    step["at"] = "2026-01-01T00:00:00+00:00"
    action = cast(dict[str, object], step["action"])
    action["effective_at"] = "2026-01-01T09:00:00+09:00"
    artifact = build_artifact(_payload(step))
    assert _result(artifact, 0)["status"] == "applied"


def test_cli_output_is_deterministic_and_preserves_decimal_strings(
    tmp_path: Path,
) -> None:
    source = tmp_path / "input.json"
    source.write_text(
        json.dumps(
            _fixture_envelope(
                "dividend_long_decimal_accrual_payment", ("accrual", "payment")
            ),
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    assert main(["--input", str(source), "--output", str(first)]) == 0
    assert main(["--input", str(source), "--output", str(second)]) == 0
    assert first.read_bytes() == second.read_bytes()
    result = json.loads(first.read_text(encoding="utf-8"))
    assert result["final_state"]["cash"] == "2.234567890123456789012345678900"


def test_caps_count_union_of_symbols_and_utc_dates() -> None:
    symbols = _payload()
    initial = cast(dict[str, object], symbols["initial_state"])
    initial["holdings"] = [
        {
            "symbol": name,
            "quantity": "1",
            "raw_price": "1",
            "total_cost": "1",
            "currency": "KRW",
        }
        for name in ("AAA", "BBB", "CCC", "DDD")
    ]
    extra = _split()
    extra_action = cast(dict[str, object], extra["action"])
    extra_action["symbol"] = "EEE"
    try:
        build_artifact({**symbols, "steps": [extra]})
    except ArtifactError as exc:
        assert "symbol limit" in str(exc)
    else:
        raise AssertionError("symbol union cap was not enforced")
    dates: list[dict[str, object]] = []
    for day in range(41):
        item = _split()
        item["at"] = (
            datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=day)
        ).isoformat()
        item_action = cast(dict[str, object], item["action"])
        item_action["effective_at"] = item["at"]
        dates.append(item)
    try:
        build_artifact({**_payload(), "steps": dates})
    except ArtifactError as exc:
        assert "UTC date" in str(exc)
    else:
        raise AssertionError("UTC date cap was not enforced")
