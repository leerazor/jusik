# Agent 도구 운영

이 문서는 Codex agent 라우팅, 보조 도구, 압축 보고와 supervisor 작업의 경계를 정의합니다. 일반적인 워크트리 생성·통합·정리 규칙은 [워크트리 운영 절차](worktree-workflow.md)를 따르고, 자동 실행기와 수동 실행의 동시성·권한·상태 규칙은 [지속 개발 운영 절차](development-runner.md)를 따릅니다. 두 문서의 규칙을 이 문서에 복사하지 않습니다.

## 역할과 모델

저장소의 역할 이름과 실제 모델 이름을 한 쌍으로 관리합니다. `task_name`은 `spawn_agent`에 전달하는 작업 이름이고 모델 선택과 무관하며, `model`은 agent 설정의 모델 식별자입니다. 두 값을 서로 대체하거나 보고서에 혼동해서 쓰지 않습니다.

| 역할 | 모델 | 권한 | 책임 |
| --- | --- | --- | --- |
| `explore` | `gpt-5.6-luna` | read-only | 코드·데이터 흐름·관례를 조사하고 근거를 제시 |
| `plan` | `gpt-6-astra` | read-only | 조사 근거를 제한된 계획과 완료 조건으로 정리 |
| `code` | `gpt-5.6-luna` | workspace-write | 확정 계획을 구현하고 focused 검사를 실행 |
| `review` | `gpt-5.6-terra` | read-only | diff의 회귀·보안·검증 누락을 독립 검토 |
| supervisor | Astra | 감독 | 범위·순서·통합·최종 판단을 조율 |

`code` 설정에 이미 `gpt-5.6-sol`이 로드된 환경이 있으면 라우팅이 자동으로 바뀐 것으로 간주하지 않습니다. loaded agent의 모델을 덮어쓸 수 없을 때는 기존 agent를 Luna라고 부르지 말고, 일반(default) worker에 `model=gpt-5.6-luna`와 `fork_turns=none`을 명시해 실행합니다. 실행기가 모델 자체를 지정할 수 없으면 Luna라고 주장하지 말고 실제 모델을 알 수 없거나 제한된 fallback이라고 보고합니다. role 이름, `task_name`, 모델 이름은 dispatch 전후에 각각 기록하고 일치 여부를 확인합니다.

## 압축 보고 계약

agent는 결과를 다음 다섯 항목으로 짧게 반환합니다. 각 항목은 사실과 명령 결과만 담고, 긴 사고 과정이나 원문 prompt를 복사하지 않습니다.

1. `paths/evidence`: 확인·수정한 `path:line`과 판단의 근거.
2. `changes`: 변경 내용 또는 `none`.
3. `commit`: 결과 commit SHA 또는 `not applicable`.
4. `validation`: 실행한 명령과 통과·실패 결과.
5. `remaining`: 남은 문제·검증 한계·후속 판단.

보고서와 helper 출력에는 prompt, secret, credential, token, certificate, brokerage account identifier를 넣지 않습니다. 증거가 필요하면 파일 경로·줄 번호·해시·명령 결과처럼 재현 가능한 최소 정보만 남깁니다. `code`는 작업 범위의 focused 검사를 통과시킨 뒤 전용 commit SHA를 보고하고, read-only 역할은 commit을 `not applicable`로 표시합니다.

## 보조 도구와 설치 경계

승인된 추천 도구와 현재 확인된 설치 경로·버전은 다음과 같습니다.

| 도구 | 확인 결과 | 사용 경로·명령 |
| --- | --- | --- |
| Serena MCP | `Serena 1.7.0` | `/home/kwl/.local/bin/serena`; Codex MCP command는 `/home/kwl/.local/bin/serena start-mcp-server --context codex --project-from-cwd --enable-web-dashboard=false --open-web-dashboard=false` |
| Playwright CLI + skill | `@playwright/cli 0.1.19` | skill은 `/home/kwl/.codex/skills/playwright-cli/SKILL.md`; WSL 정상 실행은 `/home/kwl/.config/jusik/agent-tools/playwright-cli open <URL>` |
| Context7 CLI + skill | `ctx7 0.5.11` | `ctx7 --version`; skill은 `/home/kwl/.codex/skills/context7-cli/SKILL.md`; 문서 조회는 먼저 `ctx7 library <name> <query>` 후 `ctx7 docs <libraryId> <query>` |

위 버전·경로와 설치·smoke 결과는 [도구 검증 기록](/home/kwl/.local/share/jusik/tooling-audit/20260913-tools/VERIFICATION.md)에서 확인합니다. WSL 기본 Chrome은 `libasound.so.2`가 없어 직접 실행이 실패할 수 있으므로 wrapper가 범위 지정한 browser library와 Chromium 설정을 자식 프로세스에만 적용합니다. 시스템 환경은 변경하지 않습니다. 다른 환경에서는 `command -v`와 각 `--version`을 다시 실행하고, 확인하지 못한 설치를 완료로 보고하지 않습니다. 설치된 공식 skill은 다음 turn 또는 새 Codex 세션에서 로드 여부를 확인한 뒤 사용합니다.

runner가 자식 Codex를 `--ignore-user-config`로 실행할 때 현재 사용자의 config에 등록한 도구가 자동 상속된다는 보장은 없습니다. 따라서 dispatch 전에 해당 실행에서 필요한 MCP·CLI·skill이 실제로 사용 가능한지 확인하고, 불가능하면 도구 의존 작업을 실행하지 않거나 차단 사유를 남깁니다. 이 확인은 사용자 전역 설정을 수정하지 않습니다.

각 작업은 전용 cwd와 worktree에서 실행합니다. Python 환경, frontend 의존성·빌드 출력, 로그·임시 산출물도 작업 경계를 지키며 공유하지 않습니다. 자세한 경로·lock·runner 권한 규칙은 연결된 운영 문서에서 확인합니다.

## supervisor 검사와 작업 경계

개인 supervisor skill의 기준 경로는 `/home/kwl/.codex/skills/jusik-supervisor`이고, routing helper는 그 경로의 `scripts/check_routing.py`에 있습니다. helper pre/post 검사는 모델·role·fork만 확인합니다. helper가 없거나 CLI 계약을 확인할 수 없으면 설치된 `SKILL.md`와 `--help`를 먼저 확인하고, 그래도 불명확하면 실행을 보류합니다. cwd·worktree와 필요한 도구의 실제 사용 가능성은 helper 범위가 아니며 supervisor가 수동 검증합니다. runner root의 Astra는 설계상 supervisor 역할이므로 그 역할 매핑을 유지합니다.

helper는 prompt와 secret을 출력하지 않고, 호출 전 verifier 결과와 호출 후 audit 결과만 남깁니다. verifier는 실제 spawn hook 자체를 차단하지 않습니다. 즉 helper를 우회한 spawn을 기술적으로 막는 경계가 아니므로 supervisor가 절차를 지켜야 합니다.

모델·문맥 상속의 불확실성과 불필요한 반복 입력을 줄이기 위해 이 프로젝트 사전검사는 독립 문맥인 `fork_turns='none'`만 지원합니다. role을 지정한 spawn에도 이 값을 명시하며, `all`·생략·부분 fork는 helper 검증 실패로 처리합니다. 이는 이 프로젝트 preflight 정책이며 모든 host가 named role의 모델 상속을 보장한다는 뜻이 아닙니다.

## 사용 흐름

1. `spawn_agent` 직전에 helper preflight로 role, 요청 model, `fork_turns='none'`을 확인합니다. role을 지정한 spawn에도 이 값을 명시하며, `all`·생략·부분 fork는 검증 실패로 처리합니다. supervisor는 별도로 `task_name`, cwd/worktree와 필요한 도구의 실제 사용 가능성을 수동 확인합니다.
2. preflight 반환 결과와 실제 tool 계약을 대조한 뒤에만 spawn을 호출합니다. 계약이 불명확하거나 모델을 지정할 수 없으면 fallback과 제한을 보고하고 작업을 보류합니다.
3. child가 반환한 압축 보고의 `paths/evidence`, `commit`, `validation`을 실제 파일·Git 상태·명령 결과와 대조합니다.
4. 종료 후 child audit에서 model 불일치, role·작업 이름 불일치, 증거 누락 또는 검증 실패가 발견되면 완료 처리를 보류하고 재검토·재실행 조건을 남깁니다.

작업 경계에서 기존 [verify-and-stop skill](/home/kwl/.agents/skills/verify-and-stop/SKILL.md)을 사용해 요구된 검사를 통과한 뒤 종료합니다. 이 종료는 Astra의 local `main` 통합 검사와 handoff를 생략하는 뜻이 아닙니다. 통합이 필요한 개발 작업은 워크트리 절차의 순차 통합 검증을 보존합니다. 세션이 작업 경계에서 끝나거나 재개될 때는 [handoff skill](/home/kwl/.agents/skills/handoff/SKILL.md)의 저장 규칙에 따라 목표·결정·검사·남은 문제·다음 시작점을 기록합니다.
