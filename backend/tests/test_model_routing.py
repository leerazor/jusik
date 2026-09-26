from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from test_development_runner import _repo

from jusik.development_runner import (
    RunnerConfig,
    _codex_command,
    _review_command,
    run_once,
)
from jusik.development_runner_store import RunnerStore
from jusik.model_routing import (
    DEFAULT_POLICY,
    ModelRoutingError,
    check_spawn,
    main,
    resolve,
)


def policy_file(tmp_path: Path) -> tuple[Path, dict[str, Any]]:
    policy = json.loads(DEFAULT_POLICY.read_text())
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(policy))
    return path, policy


def test_explicit_selection_never_uses_aa_price_or_retry(tmp_path: Path) -> None:
    path, policy = policy_file(tmp_path)
    original, role, digest = resolve("role.code", path)
    assert (original.model, original.effort, role) == ("gpt-6-sol", "high", "code")
    policy["profiles"]["role.code"]["selected"] = "gpt-6-luna-high"
    path.write_text(json.dumps(policy))
    selected, _, changed = resolve("role.code", path)
    assert selected.model == "gpt-6-luna"
    assert changed != digest
    assert resolve("role.code", path)[0] == selected


@pytest.mark.parametrize(
    "change", ["malformed", "unknown", "unsupported", "diagnostic", "effort", "missing"]
)
def test_invalid_policy_fails_closed(tmp_path: Path, change: str) -> None:
    path, policy = policy_file(tmp_path)
    if change == "unknown":
        policy["profiles"]["role.code"]["selected"] = "absent"
    if change == "unsupported":
        policy["variants"]["gpt-6-sol-high"]["host_supported"] = False
    if change == "diagnostic":
        policy["profiles"]["role.code"]["selected"] = "gpt-6-astra-xhigh"
    if change == "effort":
        policy["variants"]["gpt-6-sol-high"]["effort"] = "unknown"
    path.write_text("invalid" if change == "malformed" else json.dumps(policy))
    if change == "missing":
        path.unlink()
    with pytest.raises(ModelRoutingError):
        resolve("role.code", path)


@pytest.mark.parametrize(
    "field,value",
    [
        ("model", "unknown"),
        ("reasoning_effort", "medium"),
        ("fork_turns", "all"),
        ("agent_type", "review"),
    ],
)
def test_native_check_rejects_wrong_explicit_spawn(
    tmp_path: Path, field: str, value: str
) -> None:
    path, _ = policy_file(tmp_path)
    args = {
        "model": "gpt-6-sol",
        "reasoning_effort": "high",
        "fork_turns": "none",
        "agent_type": "code",
    }
    spawn = tmp_path / "spawn.json"
    spawn.write_text(json.dumps(args))
    check_spawn("role.code", path, spawn)
    args[field] = value
    spawn.write_text(json.dumps(args))
    with pytest.raises(ModelRoutingError):
        check_spawn("role.code", path, spawn)


@pytest.mark.parametrize(
    "profile",
    [
        "runner-general",
        "runner-planning",
        "runner-completion-review",
        "runner-planning-scope",
        "runner-code-scope",
        "runner-discovery",
    ],
)
def test_all_runner_commands_read_repository_selection_without_writes(
    tmp_path: Path, profile: str
) -> None:
    path, policy = policy_file(tmp_path)
    policy["profiles"][profile]["selected"] = "gpt-6-luna-high"
    repo_policy = tmp_path / "repo/.codex/model-routing.json"
    repo_policy.parent.mkdir(parents=True)
    repo_policy.write_text(json.dumps(policy))
    config = RunnerConfig(repo=tmp_path / "repo")
    output = tmp_path / "never-created/output.json"
    schema = tmp_path / "schema.json"
    if profile in {"runner-general", "runner-planning"}:
        command = _codex_command(
            config,
            tmp_path / "common",
            schema,
            output,
            planning=profile == "runner-planning",
        )
    else:
        command = _review_command(config, schema, output, routing_profile=profile)
        assert command[command.index("--sandbox") + 1] == "read-only"
    assert command[command.index("-m") + 1] == "gpt-6-luna"
    assert 'model_reasoning_effort="high"' in command
    assert not output.parent.exists()
    # Explicit policy overrides repository selection.
    override = config.model_copy(update={"model_routing_policy": path})
    command = _review_command(override, schema, output)
    assert command[command.index("-m") + 1] == "gpt-6-sol"


def test_bad_runner_policy_does_not_leave_claimed_attempt(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    config = RunnerConfig(
        repo=repo,
        state_dir=tmp_path / "state",
        history_dir=tmp_path / "history",
        history_db=tmp_path / "history.db",
        artifact_dir=tmp_path / "artifact",
        model_routing_policy=tmp_path / "absent.json",
    )
    store = RunnerStore(config.state_dir / "runner.db")
    store.enqueue("task-a", "entry-amount-distribution", "offline task")
    result = run_once(config)
    assert result.reason == "dispatch_error"
    with sqlite3.connect(store.db_path) as db:
        assert db.execute("SELECT status FROM attempts").fetchall() == [("failed",)]


def test_cli_reports_only_safe_selection(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path, _ = policy_file(tmp_path)
    assert main(["resolve", "--policy", str(path), "--profile", "role.code"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["reasoning_effort"] == "high"
    assert main(["check", "--profile", "role.code"]) == 1
    assert "requires spawn args" in capsys.readouterr().err
