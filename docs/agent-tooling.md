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
| Linear plugin | `linear 5.0.1`, installed and enabled | Codex session에서 connector와 권한을 확인한 뒤에만 사용합니다. |

위 버전·경로와 설치·smoke 결과는 [도구 검증 기록](/home/kwl/.local/share/jusik/tooling-audit/20260913-tools/VERIFICATION.md)에서 확인합니다. WSL 기본 Chrome은 `libasound.so.2`가 없어 직접 실행이 실패할 수 있으므로 wrapper가 범위 지정한 browser library와 Chromium 설정을 자식 프로세스에만 적용합니다. 시스템 환경은 변경하지 않습니다. 다른 환경에서는 `command -v`와 각 `--version`을 다시 실행하고, 확인하지 못한 설치를 완료로 보고하지 않습니다. 설치된 공식 skill은 다음 turn 또는 새 Codex 세션에서 로드 여부를 확인한 뒤 사용합니다.

runner가 자식 Codex를 `--ignore-user-config`로 실행할 때 현재 사용자의 config에 등록한 도구가 자동 상속된다는 보장은 없습니다. 따라서 dispatch 전에 해당 실행에서 필요한 MCP·CLI·skill이 실제로 사용 가능한지 확인하고, 불가능하면 도구 의존 작업을 실행하지 않거나 차단 사유를 남깁니다. 이 확인은 사용자 전역 설정을 수정하지 않습니다.

각 작업은 전용 cwd와 worktree에서 실행합니다. Python 환경, frontend 의존성·빌드 출력, 로그·임시 산출물도 작업 경계를 지키며 공유하지 않습니다. 자세한 경로·lock·runner 권한 규칙은 연결된 운영 문서에서 확인합니다.

## Context7와 Linear 사용 경계

Context7는 이 프로젝트가 사용하는 Next.js·React·FastAPI 등 외부 의존성의 현재 API, 마이그레이션, 보안·호환성 규칙을 확인해야 할 때 사용합니다. 구현 전 저장소의 잠긴 버전과 기존 코드를 먼저 확인하고, 지식이 오래됐을 가능성이 있거나 공식 문서 확인이 필요한 쟁점만 `ctx7 library`로 식별한 뒤 `ctx7 docs`로 조회합니다. Context7 결과는 현재 코드·테스트·잠금 파일보다 우선하지 않으며, 조회 자체가 의존성 추가나 업그레이드 승인이 되지 않습니다. `ctx7 skills suggest`는 보조 후보 탐색일 뿐이며, 새 skill 설치는 별도 사용자 요청이 있을 때만 합니다.

Linear는 여러 worktree 작업의 사용자 가시성, 우선순위, 의존성, 완료 상태를 공유할 때 유용합니다. 저장소의 [작업 등록부](worktree-tasks.md)는 worktree 경로·브랜치·검증·통합·handoff를 담는 실행 기록이므로 계속 기준 기록으로 유지합니다. Linear issue가 입력으로 제공되면 시작 전에 범위와 완료 조건을 읽고, 작업 등록부에 issue 식별자 또는 링크만 기록할 수 있습니다. Linear 생성·상태 변경·댓글 작성은 외부 상태 변경이므로 사용자가 요청했거나 해당 작업 지시에 명시된 경우에만 합니다. issue에는 비밀값, 계좌 식별자, 원시 데이터, 내부 절대 경로, 긴 실행 로그를 넣지 않습니다. 작업 종료 후에는 검증 결과·커밋·handoff 경로의 짧은 요약만 남깁니다.

## Roleless CLI routing

설치된 generic skill이 `agent_type`을 요구하더라도 실제 `collaboration.spawn_agent` capability probe가 `role_parameter="NONE"`이고 `model`, `reasoning_effort`, `fork_turns`를 지원하면 이 절차를 적용합니다. native interactive 경로에는 적용하지 않습니다. capability evidence는 실제 도구 probe JSON이어야 하며 추정하거나 role TOML만으로 대체하지 않습니다.

`backend/jusik/agent_routing.py`가 role TOML을 읽어 `model`, `model_reasoning_effort`, `developer_instructions`와 bounded task input(Goal, Ownership, Validation, Stop condition)을 하나의 private message로 묶습니다. `prepare`는 정확히 `task_name`, `message`, `model`, `reasoning_effort`, `fork_turns` 다섯 인자만 생성하고 `model`과 `reasoning_effort`를 명시하며 `fork_turns=none`을 고정합니다. message에는 nonce·role/task 입력 digest 기반 receipt를 포함하고 child가 도구 호출 전에 첫 public assistant response로 receipt를 출력하도록 요구합니다. TOML의 `sandbox_mode`를 child가 적용했다고 주장하지 않습니다. parent 권한은 상속되며 role instructions는 task message로 전달됩니다.

plaintext message를 기록하는 host에서는 두 명령에서 `--message-mode`를 생략합니다. opaque envelope를 기록하는 host에서만 아래처럼 prepare와 post에 같은 `--message-mode model-only-encrypted-message-v1`를 지정합니다.

```text
python3 backend/jusik/agent_routing.py prepare \
  --role-file .codex/agents/code.toml --capability-file PATH/probe.json \
  --task-file PATH/task.json --base-commit SHA --task-name NAME \
  --manifest PATH/manifest.json --spawn-args PATH/spawn.json \
  --message-mode model-only-encrypted-message-v1
python3 backend/jusik/agent_routing.py pre \
  --manifest PATH/manifest.json --spawn-args PATH/spawn.json
python3 backend/jusik/agent_routing.py post \
  --manifest PATH/manifest.json --capability-file PATH/probe.json \
  --parent-jsonl PATH/parent.jsonl --child-jsonl PATH/child.jsonl \
  --message-mode model-only-encrypted-message-v1
```

`PATH/task.json`은 다음 네 개의 bounded field를 담습니다.

```json
{"goal":"...","ownership":"...","validation":"...","stop_condition":"..."}
```

`pre`는 실제 호출 직전 다섯 인자의 집합·값·hash와 role/task 원본, 준비 message/receipt의 일관성을 확인합니다. 실제 child 전달은 `post`가 검증합니다. `post`는 child가 완료되고 parent가 현재 레코드 쓰기를 마친 안정 시점에 parent/child JSONL을 대상으로 실행합니다. parent 프로세스 자체의 종료는 요구하지 않습니다. JSONL이 아직 기록 중이거나 마지막 줄을 포함해 하나라도 malformed이면 fail closed하고, 안정 시점에 재시도합니다. post는 실제 function call의 다섯 인자, 동일 call id의 child 반환 경로, child `session_meta`의 id·parent link, child 소유 turn context의 모델 불변성과 첫 assistant receipt를 대조합니다. child의 raw initial input이 JSONL에 보존되지 않는 host에서는 receipt를 delivery evidence로 기록하고 raw message가 보존되었다고 주장하지 않습니다. 실패 출력에는 prompt·응답 원문·secret을 포함하지 않습니다.

관찰된 host가 parent log의 `message`를 opaque base64url envelope로 저장하는 경우에만 `--message-mode model-only-encrypted-message-v1`을 명시합니다. capability probe의 정확한 다섯 인자와 envelope 구조(첫 decoded byte와 길이 형태)만 확인하고 해독·키 접근·암호학적 무결성 주장을 하지 않습니다. 이 모드에서도 네 개의 non-message 인자는 정확히 일치해야 하고 plaintext message가 들어오면 실패합니다. opaque 결과에는 `raw_input_available=false`, `raw_call_message_available=false`, `nonmessage_args_verified=true`, `message_integrity_verified=null`, 준비 args·parent/child 원본 log·opaque blob의 별도 hash, `delivery_evidence=assistant_receipt`를 기록합니다. plaintext exact-match 결과에는 `raw_call_message_available=true`, `message_integrity_verified=true`를 기록합니다. 준비 manifest와 spawn args는 새 private 파일로만 생성하며 기존 파일·symlink를 덮어쓰지 않습니다.

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
