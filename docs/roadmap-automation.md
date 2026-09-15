# 투자 개발 로드맵 자동 실행기

`development_runner`의 `investment-roadmap` scope는 기존 연구 큐와 상태를 공유하지 않는 전용 실행 흐름입니다. `RunnerConfig.scope`의 기본값은 `research`이며, 투자 scope는 전용 state 디렉터리로 초기화해야 합니다. 기존 연구 state, legacy state, 다른 scope로 만들어진 state를 재사용하면 실행을 차단합니다.

투자 scope의 area는 `docs/investment-development-roadmap.md`에 추적된 checklist ID를 소문자로 정규화한 값입니다. 실행기는 문서를 authoritative completion source로 읽습니다. 문서가 없거나 malformed이면 자식 dispatch를 시작하지 않습니다. 초기화는 빈 queue만 만들며 `roadmap-r1-01-v1` seed는 별도 승인된 준비 단계에서 enqueue해야 합니다.

phase gate는 R0 완료 후 R1·R2·R3를 독립적으로 허용하고, R1과 R2 완료 후 R4를 허용합니다. R3는 R4의 선행 조건이 아닙니다. R4 완료 후 R5·R6를 허용하며 R6에는 R1 조건을 함께 적용합니다. R5 완료 후 R7을 허용합니다. 한 cycle은 한 checklist slice만 처리합니다. slice 완료는 전체 checklist 완료와 다르며, 전체 조건을 충족할 때만 Markdown checkbox를 갱신합니다.

실패·차단·중단된 area는 같은 task ID를 명시적으로 retry할 때까지 격리합니다. 새 task ID로 우회 enqueue할 수 없고, terminal history는 pending queue 상한 8개에 포함하지 않습니다. 의존성은 `completed`만 만족으로 취급합니다. benchmark·future observation 자료가 없으면 작업은 blocked로 남으며 성공으로 가장하지 않습니다.

자동 작업은 worktree 구현·review·local `main` 통합·검사·evidence·handoff·cleanup 경계를 지킵니다. PAPER/live activation, operating ledger, 실제 주문, remote push, 서비스 변경은 허용하지 않습니다. 첫 dispatch 전용 설정 예시는 audit에 보관하며 이 문서가 서비스를 자동 설치하거나 활성화하지 않습니다.
