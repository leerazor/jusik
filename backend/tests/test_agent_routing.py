from __future__ import annotations

import json
from pathlib import Path

import pytest

from jusik.agent_routing import RoutingError, post_audit, preflight, prepare_routing

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
    assert result["raw_input_available"] == "false"
    assert result["delivery_evidence"] == "assistant_receipt"


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
