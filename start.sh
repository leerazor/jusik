#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

if ! command -v node >/dev/null 2>&1 && [[ -s "${NVM_DIR:-$HOME/.nvm}/nvm.sh" ]]; then
    source "${NVM_DIR:-$HOME/.nvm}/nvm.sh"
    nvm use --silent
fi

for dependency in node ngrok setsid; do
    if ! command -v "$dependency" >/dev/null 2>&1; then
        echo "필요한 명령이 없습니다: $dependency. README의 초기 설치 안내를 확인하세요." >&2
        exit 1
    fi
done

PYTHON="$PROJECT_DIR/backend/.venv/bin/python"
NEXT="$PROJECT_DIR/frontend/node_modules/next/dist/bin/next"
NGROK_HELPER="$PROJECT_DIR/backend/jusik/ngrok_launcher.py"
NGROK_POLICY="$HOME/.config/ngrok/jusik-policy.yml"
if [[ ! -x "$PYTHON" || ! -f "$NEXT" ]]; then
    echo "의존성 설치가 필요합니다. README에 따라 backend/.venv와 frontend/node_modules를 준비하세요." >&2
    exit 1
fi

"$PYTHON" "$NGROK_HELPER" policy "$NGROK_POLICY"

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

# Refuse occupied ports instead of stopping another process or changing ports.
"$PYTHON" - <<'PY'
import socket
import sys

for port in (8000, 3000):
    with socket.socket() as listener:
        try:
            listener.bind(("127.0.0.1", port))
        except OSError:
            print(f"포트 {port}를 사용할 수 없습니다. 기존 서버를 종료한 뒤 다시 실행하세요.", file=sys.stderr)
            sys.exit(1)
PY

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
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

setsid "$PYTHON" -m uvicorn jusik.main:app --app-dir backend \
    --host 127.0.0.1 --port 8000 --no-access-log &
process_groups+=("$!")

(
    cd "$PROJECT_DIR/frontend"
    exec setsid node "$NEXT" dev --hostname 127.0.0.1 --port 3000
) &
process_groups+=("$!")

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
