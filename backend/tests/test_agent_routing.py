from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

import pytest

from jusik.agent_routing import (
    RoutingError,
    _private_write,
    post_audit,
    preflight,
    prepare_routing,
)

CAPABILITY = {
    "tool_name": "collaboration.spawn_agent",
    "parameter_names": [
        "fork_turns",
        "message",
        "model",
        "reasoning_effort",
        "task_name",
    ],
    "role_parameter": "NONE",
    "supports_model": True,
    "supports_fork_turns": True,
}
TASK = {
    "goal": "bounded goal",
    "ownership": "single owner",
    "validation": "focused pytest",
    "stop_condition": "stop after validation",
}


def _jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text("".join(json.dumps(record) + "\n" for record in records))


@pytest.fixture
def prepared(tmp_path: Path) -> tuple[Path, Path, dict[str, object]]:
    role = tmp_path / "code.toml"
    role.write_text(
        'name = "code"\nmodel = "gpt-5.6-luna"\n'
        'model_reasoning_effort = "high"\n'
        'developer_instructions = "Follow the bounded plan."\n'
    )
    capability = tmp_path / "capability.json"
    capability.write_text(json.dumps(CAPABILITY))
    task = tmp_path / "task.json"
    task.write_text(json.dumps(TASK))
    manifest = tmp_path / "manifest.json"
    args = tmp_path / "args.json"
    prepare_routing(role, capability, task, "d90373b", "routing-test", manifest, args)
    return manifest, args, json.loads(manifest.read_text())


def _logs(
    manifest: dict[str, object], args: dict[str, object]
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    call_args = json.dumps(args)
    parent = [
        {"type": "session_meta", "payload": {"id": "parent-id"}},
        {
            "type": "response_item",
            "payload": {
                "type": "function_call",
                "name": "spawn_agent",
                "call_id": "call-1",
                "arguments": call_args,
            },
        },
        {
            "type": "response_item",
            "payload": {
                "type": "function_call_output",
                "call_id": "call-1",
                "output": json.dumps({"task_name": "/root/routing-test"}),
            },
        },
    ]
    child = [
        {
            "type": "session_meta",
            "payload": {
                "id": "child-id",
                "parent_thread_id": "parent-id",
                "agent_path": "/root/routing-test",
            },
        },
        {"type": "event_msg", "payload": {"type": "task_started", "turn_id": "turn-1"}},
        {
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": str(manifest["receipt"])}],
            },
        },
        {
            "type": "turn_context",
            "payload": {"turn_id": "turn-1", "model": manifest["model"]},
        },
    ]
    return parent, child


def test_prepare_has_exact_five_private_args_and_receipt(
    prepared: tuple[Path, Path, dict[str, object]],
) -> None:
    manifest_path, args_path, manifest = prepared
    args = json.loads(args_path.read_text())
    assert set(args) == {
        "fork_turns",
        "message",
        "model",
        "reasoning_effort",
        "task_name",
    }
    assert args["fork_turns"] == "none"
    assert manifest["transport"] == "model-only"
    assert str(manifest["receipt"]).startswith("ROUTING_RECEIPT_")
    assert manifest_path.stat().st_mode & 0o077 == 0
    assert args_path.stat().st_mode & 0o077 == 0


def test_prepare_rejects_missing_role_model(tmp_path: Path) -> None:
    role = tmp_path / "role.toml"
    role.write_text('name = "code"\ndeveloper_instructions = "instructions"\n')
    capability = tmp_path / "capability.json"
    capability.write_text(json.dumps(CAPABILITY))
    task = tmp_path / "task.json"
    task.write_text(json.dumps(TASK))
    with pytest.raises(RoutingError):
        prepare_routing(
            role,
            capability,
            task,
            "d90373b",
            "routing-test",
            tmp_path / "manifest.json",
            tmp_path / "args.json",
        )


def test_private_write_refuses_overwrite_and_symlink(tmp_path: Path) -> None:
    destination = tmp_path / "private.json"
    _private_write(destination, b"first")
    with pytest.raises(RoutingError):
        _private_write(destination, b"second")
    target = tmp_path / "target"
    target.write_bytes(b"target")
    link = tmp_path / "link"
    link.symlink_to(target)
    with pytest.raises(RoutingError):
        _private_write(link, b"replacement")


def test_pre_rejects_wrong_nonce(
    prepared: tuple[Path, Path, dict[str, object]],
) -> None:
    manifest, args_path, data = prepared
    data["nonce"] = "wrong-nonce"
    manifest.write_text(json.dumps(data))
    with pytest.raises(RoutingError):
        preflight(manifest, args_path)


@pytest.mark.parametrize("field", ["model", "reasoning_effort"])
def test_pre_rejects_manifest_and_args_tamper_against_current_role(
    prepared: tuple[Path, Path, dict[str, object]], field: str
) -> None:
    manifest_path, args_path, data = prepared
    replacement = "gpt-5.6-terra" if field == "model" else "low"
    args = data["args"]
    assert isinstance(args, dict)
    args[field] = replacement
    data[field] = replacement
    canonical = (
        json.dumps(args, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        + "\n"
    )
    data["args_sha256"] = hashlib.sha256(canonical.encode()).hexdigest()
    args_path.write_text(json.dumps(args))
    manifest_path.write_text(json.dumps(data))
    with pytest.raises(RoutingError):
        preflight(manifest_path, args_path)


@pytest.mark.parametrize(
    ("field", "value"),
    [("model", "gpt-5.6-terra"), ("reasoning_effort", "low"), ("fork_turns", "all")],
)
def test_pre_rejects_wrong_routing_values(
    prepared: tuple[Path, Path, dict[str, object]], field: str, value: str
) -> None:
    manifest, args_path, _ = prepared
    args = json.loads(args_path.read_text())
    args[field] = value
    args_path.write_text(json.dumps(args))
    with pytest.raises(RoutingError):
        preflight(manifest, args_path)


def test_pre_rejects_extra_field_and_missing_role_instructions(
    prepared: tuple[Path, Path, dict[str, object]],
) -> None:
    manifest, args_path, _ = prepared
    args = json.loads(args_path.read_text())
    args["agent_type"] = "code"
    args_path.write_text(json.dumps(args))
    with pytest.raises(RoutingError):
        preflight(manifest, args_path)
    args.pop("agent_type")
    args["message"] = "bounded goal"
    args_path.write_text(json.dumps(args))
    with pytest.raises(RoutingError):
        preflight(manifest, args_path)


def test_post_accepts_actual_layout(
    prepared: tuple[Path, Path, dict[str, object]], tmp_path: Path
) -> None:
    manifest_path, args_path, manifest = prepared
    parent, child = _logs(manifest, json.loads(args_path.read_text()))
    parent_path, child_path = tmp_path / "parent.jsonl", tmp_path / "child.jsonl"
    _jsonl(parent_path, parent)
    _jsonl(child_path, child)
    result = post_audit(manifest_path, parent_path, child_path)
    assert result["child_id"] == "child-id"
    assert result["raw_input_available"] is False
    assert result["delivery_evidence"] == "assistant_receipt"
    assert result["raw_call_message_available"] is True
    assert result["message_integrity_verified"] is True


def test_post_accepts_explicit_opaque_message_mode(
    prepared: tuple[Path, Path, dict[str, object]], tmp_path: Path
) -> None:
    manifest_path, args_path, manifest = prepared
    manifest["message_mode"] = "model-only-encrypted-message-v1"
    manifest_path.write_text(json.dumps(manifest))
    parent, child = _logs(manifest, json.loads(args_path.read_text()))
    blob = b"\x80" + b"x" * 72
    parent_args = json.loads(parent[1]["payload"]["arguments"])  # type: ignore[index]
    parent_args["message"] = base64.urlsafe_b64encode(blob).decode()
    parent[1]["payload"]["arguments"] = json.dumps(parent_args)  # type: ignore[index]
    parent_path, child_path = tmp_path / "parent.jsonl", tmp_path / "child.jsonl"
    _jsonl(parent_path, parent)
    _jsonl(child_path, child)
    result = post_audit(manifest_path, parent_path, child_path)
    assert result["raw_call_message_available"] is False
    assert result["nonmessage_args_verified"] is True
    assert result["message_integrity_verified"] is None
    assert isinstance(result["opaque_message_sha256"], str)


def test_post_ignores_other_task_spawn(
    prepared: tuple[Path, Path, dict[str, object]], tmp_path: Path
) -> None:
    manifest_path, args_path, manifest = prepared
    parent, child = _logs(manifest, json.loads(args_path.read_text()))
    unrelated_args = json.loads(args_path.read_text())
    unrelated_args["task_name"] = "other-task"
    parent.insert(
        1,
        {
            "type": "response_item",
            "payload": {
                "type": "function_call",
                "name": "spawn_agent",
                "call_id": "other-call",
                "arguments": json.dumps(unrelated_args),
            },
        },
    )
    parent.insert(
        2,
        {
            "type": "response_item",
            "payload": {
                "type": "function_call_output",
                "call_id": "other-call",
                "output": json.dumps({"task_name": "/root/other-task"}),
            },
        },
    )
    parent_path, child_path = tmp_path / "parent.jsonl", tmp_path / "child.jsonl"
    _jsonl(parent_path, parent)
    _jsonl(child_path, child)
    assert post_audit(manifest_path, parent_path, child_path)["status"] == "PASS"


def test_post_rejects_opaque_mode_plaintext_or_nonmessage_tamper(
    prepared: tuple[Path, Path, dict[str, object]], tmp_path: Path
) -> None:
    manifest_path, args_path, manifest = prepared
    manifest["message_mode"] = "model-only-encrypted-message-v1"
    manifest_path.write_text(json.dumps(manifest))
    parent, child = _logs(manifest, json.loads(args_path.read_text()))
    parent_args = json.loads(parent[1]["payload"]["arguments"])  # type: ignore[index]
    parent_args["message"] = "different plaintext"
    parent_args["model"] = "gpt-5.6-terra"
    parent[1]["payload"]["arguments"] = json.dumps(parent_args)  # type: ignore[index]
    parent_path, child_path = tmp_path / "parent.jsonl", tmp_path / "child.jsonl"
    _jsonl(parent_path, parent)
    _jsonl(child_path, child)
    with pytest.raises(RoutingError):
        post_audit(manifest_path, parent_path, child_path)
    parent_args["model"] = manifest["model"]
    parent[1]["payload"]["arguments"] = json.dumps(parent_args)  # type: ignore[index]
    _jsonl(parent_path, parent)
    with pytest.raises(RoutingError):
        post_audit(manifest_path, parent_path, child_path)


def test_post_rejects_wrong_call_output_child_and_parent_link(
    prepared: tuple[Path, Path, dict[str, object]], tmp_path: Path
) -> None:
    manifest_path, args_path, manifest = prepared
    parent, child = _logs(manifest, json.loads(args_path.read_text()))
    parent[2]["payload"] = {
        "type": "function_call_output",
        "call_id": "other-call",
        "output": json.dumps({"task_name": "/root/routing-test"}),
    }
    parent_path, child_path = tmp_path / "parent.jsonl", tmp_path / "child.jsonl"
    _jsonl(parent_path, parent)
    _jsonl(child_path, child)
    with pytest.raises(RoutingError):
        post_audit(manifest_path, parent_path, child_path)
    parent[2]["payload"]["call_id"] = "call-1"  # type: ignore[index]
    child[0]["payload"]["parent_thread_id"] = "other-parent"  # type: ignore[index]
    _jsonl(parent_path, parent)
    _jsonl(child_path, child)
    with pytest.raises(RoutingError):
        post_audit(manifest_path, parent_path, child_path)


def test_post_rejects_receipt_omission_tool_before_receipt_and_model_change(
    prepared: tuple[Path, Path, dict[str, object]], tmp_path: Path
) -> None:
    manifest_path, args_path, manifest = prepared
    parent, child = _logs(manifest, json.loads(args_path.read_text()))
    child.insert(2, {"type": "response_item", "payload": {"type": "function_call"}})
    parent_path, child_path = tmp_path / "parent.jsonl", tmp_path / "child.jsonl"
    _jsonl(parent_path, parent)
    _jsonl(child_path, child)
    with pytest.raises(RoutingError):
        post_audit(manifest_path, parent_path, child_path)
    child.pop(2)
    child[2]["payload"]["content"][0]["text"] = "wrong receipt"  # type: ignore[index]
    _jsonl(child_path, child)
    with pytest.raises(RoutingError):
        post_audit(manifest_path, parent_path, child_path)
    child[2]["payload"]["content"][0]["text"] = manifest["receipt"]  # type: ignore[index]
    child[3]["payload"]["model"] = "gpt-5.6-terra"  # type: ignore[index]
    _jsonl(child_path, child)
    with pytest.raises(RoutingError):
        post_audit(manifest_path, parent_path, child_path)


def test_post_rejects_malformed_last_line_without_echoing_sentinel(
    prepared: tuple[Path, Path, dict[str, object]],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    manifest_path, args_path, manifest = prepared
    parent, child = _logs(manifest, json.loads(args_path.read_text()))
    parent_path, child_path = tmp_path / "parent.jsonl", tmp_path / "child.jsonl"
    _jsonl(parent_path, parent)
    child_path.write_text(
        "".join(json.dumps(record) + "\n" for record in child) + "SECRET_SENTINEL\n"
    )
    with pytest.raises(RoutingError):
        post_audit(manifest_path, parent_path, child_path)
    assert "SECRET_SENTINEL" not in capsys.readouterr().out
