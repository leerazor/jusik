from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]


def _write_executable(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def _free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


@pytest.fixture
def launcher_project(tmp_path: Path) -> tuple[Path, Path, dict[str, str]]:
    backend_port = _free_port()
    frontend_port = _free_port()
    while frontend_port == backend_port:
        frontend_port = _free_port()

    project = tmp_path / "project"
    project.mkdir()
    source = (ROOT / "start.sh").read_text(encoding="utf-8")
    source = source.replace(
        "for port in (8000, 3000):", f"for port in ({backend_port}, {frontend_port}):"
    )
    source = source.replace("--port 8000", f"--port {backend_port}")
    source = source.replace("--port 3000", f"--port {frontend_port}")
    source = source.replace("127.0.0.1:3000", f"127.0.0.1:{frontend_port}")
    _write_executable(project / "start.sh", source)

    log_path = tmp_path / "children.log"
    fake_bin = tmp_path / "bin"
    python_wrapper = f"""#!/usr/bin/env bash
set -eu
record() {{ printf '%s %s\n' "$1" "$$" >> "$LOG_PATH"; }}
if [[ "$1" == */ngrok_launcher.py ]]; then
    case "$2" in
        policy) exit 0 ;;
        inspect)
            if [[ "${{LAUNCHER_MODE}}" == reuse ]]; then
                printf '%s\n' 'https://private.ngrok-free.dev'
                exit 0
            fi
            exit 3
            ;;
        wait)
            if [[ "${{LAUNCHER_MODE}}" == startup-failure ]]; then
                sleep 0.1
                printf '%s\n' 'ngrok tunnel startup failed' >&2
                exit 1
            fi
            printf '%s\n' 'https://private.ngrok-free.dev'
            exit 0
            ;;
    esac
fi
if [[ "$1" == - ]]; then
    exec {sys.executable} -
fi
if [[ "$1" == -m && "$2" == uvicorn ]]; then
    record start-backend
    if [[ "${{EXIT_BACKEND:-0}}" == 1 ]]; then
        sleep 0.1
        exit 7
    fi
    trap 'record stop-backend; exit 0' TERM INT
    while :; do sleep 1 & wait $!; done
fi
exit 2
"""
    _write_executable(project / "backend/.venv/bin/python", python_wrapper)
    (project / "backend/jusik").mkdir(parents=True)

    next_script = """#!/usr/bin/env bash
set -eu
record() { printf '%s %s\n' "$1" "$$" >> "$LOG_PATH"; }
record start-frontend
trap 'record stop-frontend; exit 0' TERM INT
while :; do sleep 1 & wait $!; done
"""
    _write_executable(project / "frontend/node_modules/next/dist/bin/next", next_script)

    _write_executable(fake_bin / "node", '#!/usr/bin/env bash\nexec "$@"\n')
    ngrok_script = """#!/usr/bin/env bash
set -eu
record() { printf '%s %s\n' "$1" "$$" >> "$LOG_PATH"; }
record start-ngrok
trap 'record stop-ngrok; exit 0' TERM INT
while :; do sleep 1 & wait $!; done
"""
    _write_executable(fake_bin / "ngrok", ngrok_script)

    home = tmp_path / "home"
    (home / ".config/ngrok").mkdir(parents=True)
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "LOG_PATH": str(log_path),
            "PATH": f"{fake_bin}:{env['PATH']}",
        }
    )
    return project, log_path, env


def _lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8").splitlines()


def _wait_for_starts(path: Path, expected: set[str]) -> None:
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        started = {
            line.split()[0] for line in _lines(path) if line.startswith("start-")
        }
        if expected <= started:
            return
        time.sleep(0.02)
    raise AssertionError(f"children did not start: {expected}")


def _terminate(process: subprocess.Popen[str]) -> tuple[str, str]:
    os.killpg(process.pid, signal.SIGINT)
    return process.communicate(timeout=5)


def _force_cleanup(process: subprocess.Popen[str], log_path: Path) -> None:
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
    for line in _lines(log_path):
        try:
            os.killpg(int(line.split()[1]), signal.SIGTERM)
        except (ProcessLookupError, ValueError, IndexError):
            pass
    try:
        process.communicate(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()


def _launch(project: Path, env: dict[str, str]) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [str(project / "start.sh")],
        cwd="/",
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )


def test_new_tunnel_is_started_and_all_owned_children_are_cleaned_up(
    launcher_project: tuple[Path, Path, dict[str, str]],
) -> None:
    project, log_path, env = launcher_project
    env["LAUNCHER_MODE"] = "new"
    process = _launch(project, env)
    try:
        _wait_for_starts(log_path, {"start-backend", "start-frontend", "start-ngrok"})
        stdout, _ = _terminate(process)
        lines = _lines(log_path)

        assert "외부 접속: https://private.ngrok-free.dev" in stdout
        assert {"stop-backend", "stop-frontend", "stop-ngrok"} <= {
            line.split()[0] for line in lines
        }
    finally:
        _force_cleanup(process, log_path)


def test_reused_tunnel_is_not_started_or_owned(
    launcher_project: tuple[Path, Path, dict[str, str]],
) -> None:
    project, log_path, env = launcher_project
    env["LAUNCHER_MODE"] = "reuse"
    process = _launch(project, env)
    try:
        _wait_for_starts(log_path, {"start-backend", "start-frontend"})
        _terminate(process)
        events = {line.split()[0] for line in _lines(log_path)}

        assert "start-ngrok" not in events
        assert {"stop-backend", "stop-frontend"} <= events
    finally:
        _force_cleanup(process, log_path)


def test_tunnel_startup_failure_cleans_up_started_children(
    launcher_project: tuple[Path, Path, dict[str, str]],
) -> None:
    project, log_path, env = launcher_project
    env["LAUNCHER_MODE"] = "startup-failure"
    process = _launch(project, env)
    try:
        _, stderr = process.communicate(timeout=5)
        events = {line.split()[0] for line in _lines(log_path)}

        assert process.returncode != 0
        assert "startup failed" in stderr
        assert {"stop-backend", "stop-frontend", "stop-ngrok"} <= events
    finally:
        _force_cleanup(process, log_path)


def test_early_backend_exit_cleans_up_other_owned_children(
    launcher_project: tuple[Path, Path, dict[str, str]],
) -> None:
    project, log_path, env = launcher_project
    env.update({"LAUNCHER_MODE": "new", "EXIT_BACKEND": "1"})
    process = _launch(project, env)
    try:
        process.communicate(timeout=5)
        events = {line.split()[0] for line in _lines(log_path)}

        assert process.returncode == 7
        assert {"stop-frontend", "stop-ngrok"} <= events
    finally:
        _force_cleanup(process, log_path)
