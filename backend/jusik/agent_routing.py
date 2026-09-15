"""Bounded routing adapter for hosts whose spawn tool has no role field.

The adapter is intentionally independent of the Codex runtime.  It reads role
TOML and explicit JSON/JSONL evidence, writes private preparation material, and
prints only fixed metadata.  It does not intercept or perform a spawn.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import sys
import tomllib
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

TRANSPORT = "model-only"
SUPPORTED_ARGS = frozenset(
    {"fork_turns", "message", "model", "reasoning_effort", "task_name"}
)
TASK_FIELDS = ("goal", "ownership", "validation", "stop_condition")


class RoutingError(ValueError):
    """A routing input or audit record cannot be verified."""


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    try:
        return _sha256_bytes(path.read_bytes())
    except (OSError, UnicodeError) as exc:
        raise RoutingError("input file unavailable") from exc


def _canonical(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        + "\n"
    ).encode()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RoutingError("invalid JSON input") from exc
    if not isinstance(value, dict):
        raise RoutingError("JSON input must be an object")
    return value


def _read_role(path: Path) -> tuple[dict[str, Any], str]:
    try:
        raw = path.read_bytes()
        value = tomllib.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise RoutingError("invalid role TOML") from exc
    if not isinstance(value, dict):
        raise RoutingError("role TOML must be an object")
    return value, _sha256_bytes(raw)


def _required_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RoutingError(f"missing {field}")
    return value


def _capability_proof(value: Mapping[str, Any]) -> None:
    names = value.get("parameter_names")
    if not isinstance(names, list) or any(not isinstance(item, str) for item in names):
        raise RoutingError("capability parameter evidence missing")
    if frozenset(names) != SUPPORTED_ARGS or len(names) != len(SUPPORTED_ARGS):
        raise RoutingError("capability parameter evidence does not match transport")
    if value.get("role_parameter") != "NONE":
        raise RoutingError("capability role-field absence is not proven")
    if (
        value.get("supports_model") is not True
        or value.get("supports_fork_turns") is not True
    ):
        raise RoutingError("capability model/fork support is not proven")
    tool_name = value.get("tool_name")
    if tool_name != "collaboration.spawn_agent":
        raise RoutingError("unexpected spawn tool capability")


def _task_input(value: Mapping[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for field in TASK_FIELDS:
        result[field] = _required_string(value.get(field), field)
    return result


def _message(instructions: str, task: Mapping[str, str], nonce: str) -> str:
    body = (
        instructions
        + "\n\nBounded task input:\n"
        + "\n".join(f"{field}: {task[field]}" for field in TASK_FIELDS)
        + "\n"
    )
    receipt = "ROUTING_RECEIPT_" + _sha256_bytes((nonce + body).encode())[:24]
    return body + (
        f"\nRouting nonce: {nonce}\n"
        "Routing receipt: before any tools or substantive response, emit exactly "
        f"{receipt} as the first public assistant response line. This confirms "
        "receipt of the bounded routing message.\n"
    )


def _private_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.is_symlink():
        raise RoutingError("private output is a symlink")
    try:
        with path.open("wb") as handle:
            os.fchmod(handle.fileno(), 0o600)
            handle.write(content)
    except OSError as exc:
        raise RoutingError("private output unavailable") from exc


def _read_manifest(path: Path) -> dict[str, Any]:
    value = _read_json(path)
    if value.get("version") != 1 or value.get("transport") != TRANSPORT:
        raise RoutingError("manifest contract mismatch")
    return value


def _expected_args(manifest: Mapping[str, Any]) -> dict[str, str]:
    args = manifest.get("args")
    if not isinstance(args, dict) or set(args) != SUPPORTED_ARGS:
        raise RoutingError("manifest args are malformed")
    if any(not isinstance(value, str) for value in args.values()):
        raise RoutingError("manifest args are malformed")
    return {key: args[key] for key in SUPPORTED_ARGS}


def _actual_args(path: Path) -> dict[str, Any]:
    value = _read_json(path)
    if set(value) != SUPPORTED_ARGS:
        raise RoutingError("spawn arguments contain unsupported fields")
    return value


@dataclass(frozen=True)
class Prepared:
    manifest_path: Path
    spawn_args_path: Path
    manifest_sha256: str
    args_sha256: str
    message_sha256: str


def prepare_routing(
    role_file: Path,
    capability_file: Path,
    task_file: Path,
    base_commit: str,
    task_name: str,
    manifest_path: Path,
    spawn_args_path: Path,
) -> Prepared:
    role, role_hash = _read_role(role_file)
    capability = _read_json(capability_file)
    _capability_proof(capability)
    task = _task_input(_read_json(task_file))
    logical_role = _required_string(role.get("name"), "role name")
    model = _required_string(role.get("model"), "role model")
    effort = _required_string(role.get("model_reasoning_effort"), "reasoning effort")
    instructions = _required_string(
        role.get("developer_instructions"), "developer instructions"
    )
    commit = _required_string(base_commit, "base commit")
    name = _required_string(task_name, "task name")
    nonce = secrets.token_hex(12)
    message = _message(instructions, task, nonce)
    receipt = next(
        line.split("exactly ", 1)[1].split(" as the first", 1)[0]
        for line in message.splitlines()
        if line.startswith("Routing receipt: ") and "exactly " in line
    )
    args: dict[str, str] = {
        "fork_turns": "none",
        "message": message,
        "model": model,
        "reasoning_effort": effort,
        "task_name": name,
    }
    _private_write(spawn_args_path, (_canonical(args)))
    manifest: dict[str, Any] = {
        "version": 1,
        "transport": TRANSPORT,
        "logical_role": logical_role,
        "model": model,
        "reasoning_effort": effort,
        "fork_turns": "none",
        "role_file": str(role_file.resolve()),
        "role_sha256": role_hash,
        "instruction_sha256": _sha256_bytes(instructions.encode()),
        "message_sha256": _sha256_bytes(message.encode()),
        "receipt": receipt,
        "nonce": nonce,
        "task_input_sha256": _sha256_bytes(_canonical(task)),
        "args_sha256": _sha256_bytes(_canonical(args)),
        "base_commit": commit,
        "task_name": name,
        "args": args,
    }
    _private_write(manifest_path, (_canonical(manifest)))
    return Prepared(
        manifest_path,
        spawn_args_path,
        _sha256_file(manifest_path),
        manifest["args_sha256"],
        manifest["message_sha256"],
    )


def preflight(manifest_path: Path, spawn_args_path: Path) -> dict[str, str]:
    manifest = _read_manifest(manifest_path)
    expected = _expected_args(manifest)
    actual = _actual_args(spawn_args_path)
    role_file_value = manifest.get("role_file")
    role_file = Path(role_file_value) if isinstance(role_file_value, str) else None
    if role_file is None:
        raise RoutingError("role file is missing")
    role, role_hash = _read_role(role_file)
    if role_hash != manifest.get("role_sha256"):
        raise RoutingError("role TOML changed")
    if role.get("name") != manifest.get("logical_role"):
        raise RoutingError("logical role changed")
    instructions = role.get("developer_instructions")
    if not isinstance(instructions, str):
        raise RoutingError("role instructions are missing")
    if _sha256_bytes(instructions.encode()) != manifest.get("instruction_sha256"):
        raise RoutingError("role instructions changed")
    if actual != expected:
        raise RoutingError("spawn arguments do not match manifest")
    if expected["model"] != manifest.get("model"):
        raise RoutingError("model does not match manifest")
    if expected["reasoning_effort"] != manifest.get("reasoning_effort"):
        raise RoutingError("reasoning effort does not match manifest")
    if expected["fork_turns"] != "none" or manifest.get("fork_turns") != "none":
        raise RoutingError("fork_turns must be none")
    message_hash = _sha256_bytes(expected["message"].encode())
    if message_hash != manifest.get("message_sha256"):
        raise RoutingError("role instructions delivery is not verifiable")
    if (
        not expected["message"].startswith(instructions)
        or "Bounded task input:\n" not in expected["message"]
        or "Routing nonce: " not in expected["message"]
        or "Routing receipt: " not in expected["message"]
    ):
        raise RoutingError("role instructions delivery is not verifiable")
    if _sha256_bytes(_canonical(actual)) != manifest.get("args_sha256"):
        raise RoutingError("spawn argument hash mismatch")
    return {
        "status": "PASS",
        "manifest_sha256": _sha256_file(manifest_path),
        "args_sha256": manifest["args_sha256"],
        "transport": TRANSPORT,
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise RoutingError("JSONL unavailable") from exc
    if not lines:
        raise RoutingError("JSONL is empty")
    records: list[dict[str, Any]] = []
    for line in lines:
        if not line.strip():
            raise RoutingError("JSONL contains a blank record")
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RoutingError("JSONL contains malformed record") from exc
        if not isinstance(value, dict):
            raise RoutingError("JSONL record is not an object")
        records.append(value)
    return records


def _walk(value: object) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _session_meta(
    records: list[dict[str, Any]], *, child: bool
) -> tuple[str, str | None, str | None]:
    for record in records:
        if record.get("type") != "session_meta":
            continue
        payload = record.get("payload", record)
        if not isinstance(payload, dict):
            continue
        session_id = payload.get("id", payload.get("thread_id"))
        if isinstance(session_id, str) and session_id:
            parent = payload.get("parent_thread_id", payload.get("parent_id"))
            path = payload.get("agent_path")
            if child and (not isinstance(parent, str) or not parent):
                raise RoutingError("child session parent linkage is missing")
            return (
                session_id,
                parent if isinstance(parent, str) else None,
                path if isinstance(path, str) else None,
            )
    raise RoutingError("session metadata is missing")


def _spawn_call(
    records: list[dict[str, Any]], expected: Mapping[str, str]
) -> tuple[str, str]:
    calls: list[tuple[str, dict[str, Any]]] = []
    outputs: dict[str, str] = {}
    for record in records:
        for item in _walk(record):
            name = item.get("name", item.get("tool_name"))
            if name not in {"collaboration.spawn_agent", "spawn_agent"}:
                continue
            raw = item.get("arguments", item.get("input", item.get("parameters")))
            if isinstance(raw, str):
                try:
                    raw = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise RoutingError("spawn call arguments are malformed") from exc
            if (
                not isinstance(raw, dict)
                or set(raw) != SUPPORTED_ARGS
                or raw != dict(expected)
            ):
                raise RoutingError("actual spawn arguments do not match manifest")
            call_id = item.get("call_id", item.get("id"))
            if not isinstance(call_id, str) or not call_id:
                raise RoutingError("spawn call id is missing")
            calls.append((call_id, raw))
        record_payload = record.get("payload")
        record_call_id = record.get("call_id")
        if isinstance(record_payload, dict) and not isinstance(record_call_id, str):
            record_call_id = record_payload.get("call_id")
        call_id = record_call_id
        if isinstance(call_id, str) and call_id:
            raw_output = record.get("output", record.get("result"))
            if raw_output is None and isinstance(record_payload, dict):
                raw_output = record_payload.get("output", record_payload.get("result"))
            if isinstance(raw_output, str):
                try:
                    raw_output = json.loads(raw_output)
                except json.JSONDecodeError:
                    raw_output = None
            for item in _walk(raw_output):
                child = item.get(
                    "child_id",
                    item.get("child_thread_id", item.get("task_name")),
                )
                if isinstance(child, str) and child:
                    outputs[call_id] = child
    if len(calls) != 1:
        raise RoutingError("exactly one matching spawn call is required")
    call_id, _ = calls[0]
    child_id = outputs.get(call_id)
    if child_id is None:
        raise RoutingError("spawn call output child id is missing")
    return call_id, child_id


def _received_receipt(records: list[dict[str, Any]], receipt: str) -> None:
    """Verify the child-owned receipt without requiring unavailable raw input logs."""
    saw_assistant = False
    for record in records:
        payload = record.get("payload", record)
        if not isinstance(payload, dict):
            continue
        if (
            record.get("type") != "response_item"
            and payload.get("type") != "response_item"
        ):
            continue
        item_type = payload.get("type")
        if payload.get("role") in {"assistant", "agent_message"}:
            saw_assistant = True
        elif item_type in {"function_call", "custom_tool_call"} and not saw_assistant:
            raise RoutingError("child tool call preceded routing receipt")
        else:
            continue
        if saw_assistant and payload.get("role") not in {"assistant", "agent_message"}:
            continue
        texts: list[str] = []
        for item in _walk(payload.get("content", payload.get("text", ""))):
            text = item.get("text")
            if isinstance(text, str):
                texts.append(text)
        text = payload.get("text")
        if isinstance(text, str):
            texts.append(text)
        first_line = next(
            (
                line.strip()
                for value in texts
                for line in value.splitlines()
                if line.strip()
            ),
            "",
        )
        if first_line == receipt:
            return
        raise RoutingError("first child assistant response lacks routing receipt")
    raise RoutingError("child routing receipt is missing")


def _task_started_ids(records: list[dict[str, Any]]) -> set[str]:
    ids: set[str] = set()
    for record in records:
        for item in _walk(record):
            if item.get("type") == "task_started" and isinstance(
                item.get("turn_id"), str
            ):
                ids.add(item["turn_id"])
    return ids


def _own_models(
    records: list[dict[str, Any]], child_id: str, inherited_turns: set[str]
) -> set[str]:
    models: set[str] = set()
    own_turns: set[str] = set()
    for record in records:
        payload = record.get("payload")
        item = payload if isinstance(payload, dict) else record
        if record.get("type") == "task_started" or item.get("type") == "task_started":
            turn_id = item.get("turn_id")
            if isinstance(turn_id, str) and turn_id:
                own_turns.add(turn_id)
    if own_turns & inherited_turns:
        raise RoutingError("child turn is inherited from parent")
    if not own_turns:
        raise RoutingError("child task turn evidence is missing")
    context_models: set[str] = set()
    for record in records:
        payload = record.get("payload")
        item = payload if isinstance(payload, dict) else record
        if record.get("type") != "turn_context" and item.get("type") != "turn_context":
            continue
        turn_id = item.get("turn_id")
        if not isinstance(turn_id, str) or (own_turns and turn_id not in own_turns):
            continue
        model = item.get("model")
        if not isinstance(model, str) or not model:
            raise RoutingError("child turn model is missing")
        context_models.add(model)
    models.update(context_models)
    if not models:
        raise RoutingError("child-owned turn context model is missing")
    return models


def post_audit(
    manifest_path: Path, parent_jsonl: Path, child_jsonl: Path
) -> dict[str, str]:
    manifest = _read_manifest(manifest_path)
    expected = _expected_args(manifest)
    parent = _read_jsonl(parent_jsonl)
    child = _read_jsonl(child_jsonl)
    parent_id, _, _ = _session_meta(parent, child=False)
    child_id, child_parent, child_path = _session_meta(child, child=True)
    if child_parent != parent_id:
        raise RoutingError("child parent linkage mismatch")
    _, output_child_path = _spawn_call(parent, expected)
    if child_path is None or output_child_path != child_path:
        raise RoutingError("spawn output child id mismatch")
    _received_receipt(child, _required_string(manifest.get("receipt"), "receipt"))
    parent_turns = _task_started_ids(parent)
    models = _own_models(child, child_id, parent_turns)
    if models != {manifest.get("model")}:
        raise RoutingError("child model mismatch or changed")
    return {
        "status": "PASS",
        "transport": TRANSPORT,
        "parent_id": parent_id,
        "child_id": child_id,
        "model": next(iter(models)),
        "raw_input_available": "false",
        "delivery_evidence": "assistant_receipt",
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare and audit model-only agent routing"
    )
    subs = parser.add_subparsers(dest="command", required=True)
    prepare = subs.add_parser("prepare")
    prepare.add_argument("--role-file", "--role-toml", type=Path, required=True)
    prepare.add_argument(
        "--capability-file", "--capability-evidence", type=Path, required=True
    )
    prepare.add_argument("--task-file", "--task-input", type=Path, required=True)
    prepare.add_argument("--base-commit", required=True)
    prepare.add_argument("--task-name", required=True)
    prepare.add_argument("--manifest", "--manifest-path", type=Path, required=True)
    prepare.add_argument("--spawn-args", "--spawn-args-path", type=Path, required=True)
    pre = subs.add_parser("pre")
    pre.add_argument("--manifest", "--manifest-path", type=Path, required=True)
    pre.add_argument("--spawn-args", "--spawn-args-path", type=Path, required=True)
    post = subs.add_parser("post")
    post.add_argument("--manifest", "--manifest-path", type=Path, required=True)
    post.add_argument("--parent-jsonl", type=Path, required=True)
    post.add_argument("--child-jsonl", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "prepare":
            prepared = prepare_routing(
                args.role_file,
                args.capability_file,
                args.task_file,
                args.base_commit,
                args.task_name,
                args.manifest,
                args.spawn_args,
            )
            result: Mapping[str, str] = {
                "status": "PASS",
                "transport": TRANSPORT,
                "manifest_path": str(prepared.manifest_path),
                "spawn_args_path": str(prepared.spawn_args_path),
                "manifest_sha256": prepared.manifest_sha256,
                "args_sha256": prepared.args_sha256,
                "message_sha256": prepared.message_sha256,
            }
        elif args.command == "pre":
            result = preflight(args.manifest, args.spawn_args)
        else:
            result = post_audit(args.manifest, args.parent_jsonl, args.child_jsonl)
    except RoutingError:
        print("FAIL verification unavailable or failed")
        return 1
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
