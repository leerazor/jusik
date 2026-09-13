# Agent 도구 운영

이 문서는 Codex agent 라우팅, 보조 도구, 압축 보고와 supervisor 작업의 경계를 정의합니다. 일반적인 워크트리 생성·통합·정리 규칙은 [워크트리 운영 절차](worktree-workflow.md)를 따르고, 자동 실행기와 수동 실행의 동시성·권한·상태 규칙은 [지속 개발 운영 절차](development-runner.md)를 따릅니다. 두 문서의 규칙을 이 문서에 복사하지 않습니다.

## 역할과 모델

저장소의 역할 이름과 실제 모델 이름을 한 쌍으로 관리합니다. `task_name`은 연구 큐의 작업 식별자이고 `model`은 agent 설정의 모델 식별자이므로 서로 대체하거나 보고서에 혼동해서 쓰지 않습니다.

| 역할 | 모델 | 권한 | 책임 |
| --- | --- | --- | --- |
| `explore` | `gpt-5.6-luna` | read-only | 코드·데이터 흐름·관례를 조사하고 근거를 제시 |
| `plan` | `gpt-6-astra` | read-only | 조사 근거를 제한된 계획과 완료 조건으로 정리 |
| `code` | `gpt-5.6-luna` | workspace-write | 확정 계획을 구현하고 focused 검사를 실행 |
| `review` | `gpt-5.6-terra` | read-only | diff의 회귀·보안·검증 누락을 독립 검토 |
| supervisor | Astra | 감독 | 범위·순서·통합·최종 판단을 조율 |

`code` 설정에 이미 `gpt-5.6-sol`이 로드된 환경이 있으면 라우팅이 자동으로 바뀐 것으로 간주하지 않습니다. 설정을 명시적으로 `gpt-5.6-luna`로 지정하고, 해당 모델을 지정할 수 없는 실행기에서는 Luna 일반 worker fallback을 사용했다는 사실을 보고합니다. role 이름, `task_name`, 모델 이름은 dispatch 전후에 각각 기록하고 일치 여부를 확인합니다.

## 압축 보고 계약

agent는 결과를 다음 다섯 항목으로 짧게 반환합니다. 각 항목은 사실과 명령 결과만 담고, 긴 사고 과정이나 원문 prompt를 복사하지 않습니다.

1. `paths/evidence`: 확인·수정한 `path:line`과 판단의 근거.
2. `changes`: 변경 내용 또는 `none`.
3. `commit`: 결과 commit SHA 또는 `not applicable`.
4. `validation`: 실행한 명령과 통과·실패 결과.
5. `remaining`: 남은 문제·검증 한계·후속 판단.

보고서와 helper 출력에는 prompt, secret, credential, token, certificate, brokerage account identifier를 넣지 않습니다. 증거가 필요하면 파일 경로·줄 번호·해시·명령 결과처럼 재현 가능한 최소 정보만 남깁니다. `code`는 작업 범위의 focused 검사를 통과시킨 뒤 전용 commit SHA를 보고하고, read-only 역할은 commit을 `not applicable`로 표시합니다.

## 보조 도구와 설치 경계

승인된 추천 도구는 Serena MCP, Playwright CLI와 해당 `playwright-cli` skill, Context7 CLI와 해당 `context7-cli` skill입니다. 실제 설치 명령, 버전과 설치 결과는 설치 담당 작업(`/root/install_tools`)이 확인하여 별도로 전달합니다. 확인 전에는 설치 완료나 특정 버전이 준비되었다고 보고하지 않습니다. 정확한 명령이 필요하면 설치 담당자와 조율하고, 이 문서에는 확인되지 않은 명령을 고정하지 않습니다.

runner가 자식 Codex를 `--ignore-user-config`로 실행할 때 현재 사용자의 config에 등록한 도구가 자동 상속된다는 보장은 없습니다. 따라서 dispatch 전에 해당 실행에서 필요한 MCP·CLI·skill이 실제로 사용 가능한지 확인하고, 불가능하면 도구 의존 작업을 실행하지 않거나 차단 사유를 남깁니다. 이 확인은 사용자 전역 설정을 수정하지 않습니다.

각 작업은 전용 cwd와 worktree에서 실행합니다. Python 환경, frontend 의존성·빌드 출력, 로그·임시 산출물도 작업 경계를 지키며 공유하지 않습니다. 자세한 경로·lock·runner 권한 규칙은 연결된 운영 문서에서 확인합니다.

## supervisor 검사와 작업 경계

개인 supervisor skill은 `/home/kwl/.codex/skills/jusik-supervisor`에서 별도 구현·검토 중입니다. 그 skill의 `scripts/check_routing.py`가 제공하는 dispatch 전 사전검사와 실행 후 audit 검사는 사용 가능한 경우 적용하되, 정확한 invocation은 skill 담당자(`/root/skill_tooling`)와 조율합니다. 이 문서는 그 구현을 복제하거나 설치 완료를 주장하지 않습니다.

helper는 prompt와 secret을 출력하지 않고, 호출 전 verifier 결과와 호출 후 audit 결과만 남깁니다. verifier는 실제 spawn hook 자체를 차단하지 않습니다. 즉 helper를 우회한 spawn을 기술적으로 막는 경계가 아니므로 supervisor는 호출 직전 검사와 완료 후 audit를 모두 확인하고, 누락 시 작업을 완료로 표시하지 않습니다.

작업 경계에서 기존 [verify-and-stop skill](/home/kwl/.agents/skills/verify-and-stop/SKILL.md)을 사용해 요구된 검사를 통과한 뒤 종료합니다. 이 종료는 Astra의 local `main` 통합 검사와 handoff를 생략하는 뜻이 아닙니다. 통합이 필요한 개발 작업은 워크트리 절차의 순차 통합 검증을 보존합니다. 세션이 작업 경계에서 끝나거나 재개될 때는 [handoff skill](/home/kwl/.agents/skills/handoff/SKILL.md)의 저장 규칙에 따라 목표·결정·검사·남은 문제·다음 시작점을 기록합니다.

이 작업은 agent 설정과 운영 안내만 다룹니다. backend runner, 제품 코드, 전략·주문 경로와 운영 데이터는 수정하지 않습니다.
