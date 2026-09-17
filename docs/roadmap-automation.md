# 투자 개발 로드맵 자동 실행기

`development_runner`의 `investment-roadmap` scope는 기존 연구 큐와 상태를 공유하지 않는 전용 실행 흐름입니다. `RunnerConfig.scope`의 기본값은 `research`이며, 투자 scope는 전용 state 디렉터리로 초기화해야 합니다. 기존 연구 state, legacy state, 다른 scope로 만들어진 state를 재사용하면 실행을 차단합니다.

투자 scope의 area는 `docs/investment-development-roadmap.md`에 추적된 checklist ID를 소문자로 정규화한 값입니다. 실행기는 문서를 authoritative completion source로 읽습니다. 문서가 없거나 malformed이면 자식 dispatch를 시작하지 않습니다. 초기화는 빈 queue만 만들며 `roadmap-r1-01-v1` seed는 검토된 준비 단계에서 enqueue해야 합니다.

로드맵 scope는 `docs/research-mandate.json`의 versioned `governance` object를 dispatch 계약으로 사용합니다. validator는 중복 JSON key, 비정규 파일, 지원하지 않는 schema/policy version, strict type·정책 상수, JSON·Markdown·manifest checksum 및 canonical roadmap `policy_version`을 fail-closed로 확인합니다. manifest의 `docs/research-mandate.json` 항목은 현재 전체 bytes SHA, `#legacy-execution-identity` 항목은 immutable historical execution identity projection, `#governance-object` 항목은 canonical governance-object projection으로 각각 직접 계산·비교합니다. 따라서 기존 pilot/replay policy hash와 roadmap governance digest는 서로 덮어쓰지 않습니다. `dispatch_enabled=false`인 현재 tracked 상태에서는 `run-once`·`resume`가 claim·attempt·launch보다 먼저 blocked(CLI exit 2)이며, planner fingerprint에는 검증된 mandate digest가 포함됩니다. planner/task claim 직전 git readiness와 동일 digest를 재검증하므로 self-consistent uncommitted 문서 교체도 queue·attempt·launch를 만들지 않습니다. 전체 roadmap SHA는 mandate JSON에 복사하지 않습니다.

phase gate는 R0 완료 후 R1·R2·R3를 독립적으로 허용하고, R1과 R2 완료 후 R4를 허용합니다. R3는 R4의 선행 조건이 아닙니다. R4 완료 후 R5·R6를 허용하며 R6에는 R1 조건을 함께 적용합니다. R5 완료 후 R7을 허용합니다. 한 cycle은 한 checklist slice만 처리합니다. slice 완료는 전체 checklist 완료와 다르며, 전체 조건을 충족할 때만 Markdown checkbox를 갱신합니다.

실패·차단·중단된 area는 같은 task ID를 명시적으로 retry할 때까지 격리합니다. 새 task ID로 우회 enqueue할 수 없고, terminal history는 pending queue 상한 8개에 포함하지 않습니다. 의존성은 `completed`만 만족으로 취급합니다. benchmark·future observation 자료가 없으면 작업은 blocked로 남으며 성공으로 가장하지 않습니다.

자동 작업은 worktree 구현·review·local `main` 통합·검사·evidence·handoff·cleanup 경계를 지킵니다. PAPER/live activation, operating ledger, 실제 주문, remote push, 서비스 변경은 허용하지 않습니다. 첫 dispatch 전용 설정 예시는 audit에 보관하며 이 문서가 서비스를 자동 설치하거나 활성화하지 않습니다.

## 현재 설치 상태와 제어

2026-09-15 기준 전용 config는 `~/.config/jusik/roadmap-development-runner.json`, state는 `~/.local/share/jusik/roadmap-development-runner`입니다. 기존 `jusik-development-runner.service`에 `roadmap.conf` drop-in을 추가해 같은 서비스 하나가 새 config를 읽도록 준비했습니다. 기존 연구 큐는 paused로 보존했습니다. 사용자가 필요한 커밋과 자동 개발 시작을 승인했고 기존 문서 두 개는 `a4f9760`으로 보존했습니다. R1-01 seed로 자동 운영을 시작합니다. 실제 시작 여부·attempt ID·확인 시각은 audit의 `activation.json`을 기준으로 확인합니다. 기존 연구 큐는 재개하지 않습니다.

수동 작업 전에는 backend에서 `.venv/bin/python -m jusik.development_runner pause --config ~/.config/jusik/roadmap-development-runner.json`을 실행하고, `systemctl --user stop jusik-development-runner.service`와 inactive 확인을 수행합니다. `status`, `resume`, `retry`에도 같은 config를 명시합니다. 자동 child는 자기 service를 중지하지 않습니다. WSL이 종료되면 자동 실행도 멈춥니다.
