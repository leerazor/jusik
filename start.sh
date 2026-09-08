#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

if ! command -v node >/dev/null 2>&1 && [[ -s "${NVM_DIR:-$HOME/.nvm}/nvm.sh" ]]; then
    source "${NVM_DIR:-$HOME/.nvm}/nvm.sh"
    nvm use --silent
fi

for dependency in node ngrok setsid lsof ss; do
    if ! command -v "$dependency" >/dev/null 2>&1; then
        echo "필요한 명령이 없습니다: $dependency. README의 초기 설치 안내를 확인하세요." >&2
        exit 1
    fi
done

PYTHON="$PROJECT_DIR/backend/.venv/bin/python"
NEXT="$PROJECT_DIR/frontend/node_modules/next/dist/bin/next"
NGROK_HELPER="$PROJECT_DIR/backend/jusik/ngrok_launcher.py"
NGROK_POLICY="$HOME/.config/ngrok/jusik-policy.yml"
BUILD_DIR_NAME=".next-build-$$"
BUILD_TSCONFIG_NAME=".tsconfig-build-$$.json"
BUILD_NEXT_ENV_BACKUP="$PROJECT_DIR/frontend/.next-env-build-$$.backup"
if [[ ! -x "$PYTHON" || ! -f "$NEXT" ]]; then
    echo "의존성 설치가 필요합니다. README에 따라 backend/.venv와 frontend/node_modules를 준비하세요." >&2
    exit 1
fi

"$PYTHON" "$NGROK_HELPER" policy "$NGROK_POLICY"

restore_next_build_metadata() {
    if [[ -f "$BUILD_NEXT_ENV_BACKUP" ]]; then
        mv -f -- "$BUILD_NEXT_ENV_BACKUP" "$PROJECT_DIR/frontend/next-env.d.ts"
    fi
    rm -f -- "$PROJECT_DIR/frontend/$BUILD_TSCONFIG_NAME"
}

# Next rewrites its TypeScript metadata for a custom dist directory. Build with
# a temporary tsconfig and restore next-env before replacing working listeners.
trap restore_next_build_metadata EXIT
cp -- "$PROJECT_DIR/frontend/tsconfig.json" \
    "$PROJECT_DIR/frontend/$BUILD_TSCONFIG_NAME"
cp -- "$PROJECT_DIR/frontend/next-env.d.ts" "$BUILD_NEXT_ENV_BACKUP"
set +e
(
    cd "$PROJECT_DIR/frontend"
    NEXT_DIST_DIR="$BUILD_DIR_NAME" NEXT_TSCONFIG_PATH="$BUILD_TSCONFIG_NAME" \
        node "$NEXT" build
)
build_status=$?
set -e
restore_next_build_metadata
trap - EXIT
if [[ $build_status -ne 0 ]]; then
    if [[ "$BUILD_DIR_NAME" == .next-build-[0-9]* ]]; then
        rm -rf -- "$PROJECT_DIR/frontend/$BUILD_DIR_NAME"
    fi
    exit 1
fi

set +e
public_url=$("$PYTHON" "$NGROK_HELPER" inspect "$NGROK_POLICY")
ngrok_status=$?
set -e
if [[ $ngrok_status -eq 0 ]]; then
    reuse_ngrok=true
elif [[ $ngrok_status -eq 3 ]]; then
    reuse_ngrok=false
else
    exit "$ngrok_status"
fi

# Stop existing TCP listeners before starting replacement servers.
"$PYTHON" - <<'PYTHON'
import os
import re
import signal
import socket
import subprocess
import sys
import time


def listener_pids(port):
    result = subprocess.run(
        ["lsof", "-nP", "-t", f"-iTCP:{port}", "-sTCP:LISTEN"],
        capture_output=True,
        text=True,
    )
    if result.returncode not in (0, 1) or result.stderr:
        sys.exit(f"포트 {port}의 프로세스를 확인할 수 없습니다.")
    pids = {int(pid) for pid in result.stdout.split()}
    socket_result = subprocess.run(
        ["ss", "-H", "-ltnp", f"sport = :{port}"],
        capture_output=True,
        text=True,
    )
    if socket_result.returncode != 0 or socket_result.stderr:
        sys.exit(f"포트 {port}의 socket 정보를 확인할 수 없습니다.")
    pids.update(int(pid) for pid in re.findall(r"pid=(\d+)", socket_result.stdout))
    if socket_result.stdout.strip() and not pids:
        sys.exit(f"포트 {port}의 listener PID를 확인할 수 없습니다.")
    return pids


def stop_processes(pids, signum):
    for pid in pids:
        try:
            os.kill(pid, signum)
        except ProcessLookupError:
            pass
        except PermissionError:
            sys.exit(f"프로세스 {pid}를 종료할 권한이 없습니다.")


for port in (8000, 8001, 3000):
    pids = listener_pids(port)
    if pids:
        print(f"포트 {port}의 기존 서버를 종료합니다.", flush=True)
        stop_processes(pids, signal.SIGTERM)
        deadline = time.monotonic() + 5
        while pids & listener_pids(port):
            if time.monotonic() >= deadline:
                print(f"포트 {port}의 기존 서버를 강제 종료합니다.", flush=True)
                stop_processes(pids & listener_pids(port), signal.SIGKILL)
                break
            time.sleep(0.1)

    deadline = time.monotonic() + 2
    while True:
        with socket.socket() as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                listener.bind(("127.0.0.1", port))
            except OSError:
                if time.monotonic() >= deadline:
                    sys.exit(f"포트 {port}를 해제하지 못해 시작을 중단합니다.")
            else:
                break
        time.sleep(0.1)
PYTHON

process_groups=()
cleanup() {
    trap '' INT TERM
    # Each server has its own process group, including its child processes.
    for pid in "${process_groups[@]}"; do
        kill -TERM -- "-$pid" 2>/dev/null || true
    done
    for pid in "${process_groups[@]}"; do
        wait "$pid" 2>/dev/null || true
    done
    if [[ "$BUILD_DIR_NAME" == .next-build-[0-9]* ]]; then
        rm -rf -- "$PROJECT_DIR/frontend/$BUILD_DIR_NAME"
    fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

setsid "$PYTHON" -m uvicorn jusik.main:app --app-dir backend \
    --host 127.0.0.1 --port 8000 --no-access-log &
process_groups+=("$!")

setsid "$PYTHON" -m uvicorn jusik.research_app:app --app-dir backend \
    --host 127.0.0.1 --port 8001 --no-access-log &
process_groups+=("$!")

(
    cd "$PROJECT_DIR/frontend"
    export NEXT_DIST_DIR="$BUILD_DIR_NAME"
    exec setsid node "$NEXT" start --hostname 127.0.0.1 --port 3000
) &
process_groups+=("$!")

if [[ -z "${TEST_PORTS:-}" ]]; then
    "$PYTHON" - <<'PYTHON'
import time
import urllib.error
import urllib.request

urls = (
    "http://127.0.0.1:8000/health",
    "http://127.0.0.1:8001/health",
    "http://127.0.0.1:3000/",
)
deadline = time.monotonic() + 30
pending = set(urls)
while pending and time.monotonic() < deadline:
    for url in tuple(pending):
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status < 500:
                    pending.remove(url)
        except (OSError, urllib.error.URLError):
            pass
    if pending:
        time.sleep(0.25)
if pending:
    raise SystemExit("서비스 준비 확인 실패: " + ", ".join(sorted(pending)))
PYTHON
fi

if [[ $reuse_ngrok == false ]]; then
    setsid ngrok http http://127.0.0.1:3000 \
        --traffic-policy-file "$NGROK_POLICY" --inspect=false --log=false \
        >/dev/null 2>&1 &
    process_groups+=("$!")
    public_url=$("$PYTHON" "$NGROK_HELPER" wait "$NGROK_POLICY" 15)
fi

echo "서버 시작 중: http://localhost:3000"
echo "외부 접속: $public_url"
echo "종료하려면 Ctrl+C를 누르세요. 한 서버가 종료되면 다른 서버도 종료됩니다."

status=0
wait -n "${process_groups[@]}" || status=$?
exit "$status"
