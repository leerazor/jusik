# 지속 개발 실행기

지속 개발 실행기는 systemd user timer가 한 번에 하나의 제한된 연구 작업을 Codex에 전달하고, 결과를 검증한 뒤 다음 실행을 위해 SQLite 큐에 남기는 자동 개발 도구입니다. 작업 상태와 시도별 JSON·JSONL·stderr는 `state_dir` 아래 private 파일로 보관합니다. 실제 주문, 원격 push, GPU 서비스 변경, 전략 엔진 변경은 실행하지 않습니다.

## 초기 설정

백엔드 개발 의존성을 설치한 뒤 저장소 루트에서 설정 파일과 고정 초기 큐를 만듭니다.

```bash
cd backend
.venv/bin/python -m jusik.development_runner init \
  --config ~/.config/jusik/development-runner.json \
  --repo /home/kwl/projects/jusik \
  --state-dir ~/.local/share/jusik/development-runner \
  --history-dir ~/.local/share/jusik/research-history \
  --history-db ~/.local/share/jusik/research-history-journal.db \
  --artifact-dir ~/.local/share/jusik/portfolio-audit
```

설정 파일에는 저장소, Codex 실행 파일, 상태·history·artifact 경로, 시도 제한(기본 90분), UTC 일일 실행 상한(기본 8회, 허용 범위 1~24회), 실행 간 대기(기본 60초)를 명시합니다. `automatic_recovery` 기본값은 `false`이며 설치별로 명시적으로 켜야 합니다. 필드를 생략하면 기본값 8회이며, `daily_launches: null`은 사용자가 승인한 무제한 모드입니다. 무제한 모드에서도 기존 launch history, timeout, pause, lock 동작은 유지됩니다. 일일 상한은 금액·토큰 예산이 아니라 자식 Codex dispatch 횟수 제한입니다. 90분 시도 제한과 실행 간 60초 cooldown은 그대로 유지합니다. 현재 설치 설정은 `null` 무제한으로 운영합니다. history는 연구 화면의 기존 `~/.local/share/jusik/research-history`와 journal DB를 사용해야 기록이 웹에 나타납니다. `artifact_dir`는 `~/.local/share/jusik/portfolio-audit`를 사용해 분석 산출물을 검증하고 Codex named permission profile의 허용 루트로 제공합니다. 큐의 초기 작업은 entry amount distribution, 작은 진입 제약의 선행 조건, 미래 관찰 프로토콜, PAPER 신호 근거, portfolio stress robustness 순서이며 최대 8개의 미완료 작업만 유지합니다.

systemd 파일은 설치 위치에 맞게 검토한 뒤 사용자 단위로 등록합니다. 이 저장소에서는 설치 명령을 자동 실행하지 않습니다.

```bash
cd /home/kwl/projects/jusik
mkdir -p ~/.config/systemd/user
cp deploy/systemd/jusik-development-runner.{service,timer} ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now jusik-development-runner.timer
```

이 절차는 설치 예시이며 실행기가 자동으로 패키지나 systemd unit을 설치하지 않습니다. WSL을 종료하면 user service도 중지되므로 재시작 후 `OnBootSec` 재실행과 상태를 확인합니다. WSL에서 로그인하지 않아도 실행하려면 사용자가 별도로 `loginctl enable-linger "$USER"`를 검토해야 합니다.

## 병렬 개발과 정리

실행기는 supervisor 사이클을 한 번에 하나만 실행합니다. 각 supervisor는 독립적인 하위 작업이 있으면 작업별 워크트리와 Luna 담당자를 배정해 최대 4명까지 병렬로 진행합니다. 선행 결과가 필요한 작업은 순서대로 실행하고, `main` 병합과 통합 검증은 감독이 순차 수행합니다. 병합한 워크트리는 [워크트리 운영 절차](worktree-workflow.md#정리)에 따라 결과물을 보관한 뒤 제거합니다. 이 원칙은 현재 큐와 이후 후속 작업에 동일하게 적용됩니다.

## 상태와 수동 제어

```bash
cd /home/kwl/projects/jusik/backend
.venv/bin/python -m jusik.development_runner status --config ~/.config/jusik/development-runner.json
.venv/bin/python -m jusik.development_runner pause --config ~/.config/jusik/development-runner.json
.venv/bin/python -m jusik.development_runner resume --config ~/.config/jusik/development-runner.json
.venv/bin/python -m jusik.development_runner retry --config ~/.config/jusik/development-runner.json entry-amount-distribution-v1
```

수동으로 저장소를 수정해야 할 때는 반드시 먼저 `pause`를 실행하고, `systemctl --user stop jusik-development-runner.service`를 실행한 다음 `systemctl --user is-active jusik-development-runner.service`가 `inactive`인지 확인합니다. 수동 통합과 검사를 끝내고 tracked worktree를 깨끗하게 만든 뒤 `resume`하고 timer를 다시 확인합니다. 실행기는 스스로 unit을 중지하거나 pause하지 않습니다.

`running` 시도는 재시작 때 `interrupted`로 보존되며 자동으로 다시 실행하지 않습니다. `retry TASK_ID`가 이전 시도 ID를 기록한 뒤 명시적으로 큐에 넣습니다. Codex가 종료 코드 0을 반환해도 commit이 local `main`의 조상인지, evidence 파일의 SHA-256과 허용 경로를 검증하지 못하면 완료로 기록하지 않습니다. `tests_passed`와 `review_passed`는 agent가 보고하는 값이며 runner가 대신 실행하거나 독립 review를 주장하지 않습니다. 미래 데이터가 없으면 `status=blocked`와 사유를 제출할 수 있고, 이 결과는 commit·evidence를 요구하지 않습니다. 실패·중단·blocked 시도는 명시적 retry 전까지 격리합니다.

`automatic_recovery=true`인 설치에서는 completion의 명시적 `recovery_kind=environment`와 고정 label(`dependency_setup`, `cache_permission`, `tool_unavailable`), 또는 고정 label(`code_defect`, `test_defect`, `lint_defect`, `type_defect`, `actionable_review`)인 `implementation`일 때만 blocked attempt를 다시 예약합니다. 이전 attempt는 terminal history로 남고 같은 transaction 안에서 다음 시도의 `next_allowed_at`과 `previous_attempt_id`를 기록합니다. 자동 재시도는 task당 최대 2회이며 backoff는 60초와 120초입니다. marker가 없거나 label이 허용 목록 밖이면 blocked 상태를 유지하고, completion이 `completed`인데 recovery marker를 포함하면 검증에 실패합니다. 새 시도도 매번 tests와 독립 review를 통과해 completion 계약을 충족해야 합니다.

개발 delivery에서 agent가 만든 unit regression fixture 개수나 일반 focused test 호출 횟수는 과학적 실험 상한이 아니며 기술 slice를 영구 차단하는 조건으로 쓰지 않습니다. 현재 감독자는 focused 파일, runtime, artifact budget을 사용하는 prospective replacement를 승인했으며 과거 위반 기록은 보존합니다. 사용자 명시 한도, 연구 표본·기간·가정·seed·실험 횟수, 금융 자료와 계산 예산은 그대로 엄격히 적용합니다. 현재 tracked 문서가 오래된 agent 생성 task의 test-count 제한보다 우선하며, 기술 slice 완료와 전체 금융·자료 acceptance를 구분합니다. identity, hash, review 등 완료 검증은 우회하지 않습니다. 소유한 environment/cache의 일상적 복구에는 새 사용자 승인을 요구하지 않습니다.

연구 task가 Codex 종료 코드 0이 아닌 값으로 끝나면 해당 private attempt에 `exit-diagnostics.json`을 남깁니다. 파일에는 return code, 음수 종료 코드일 때만 계산한 signal number, completion 파일의 존재 여부만 기록하며 stderr·prompt·completion 내용은 복사하지 않습니다. 진단 파일을 쓰지 못해도 기존 `failed`/`codex_exit` 상태는 유지합니다.

실행 기록의 history outbox는 고정된 한국어 상태 제목·요약과 task/attempt ID만 기록합니다. Codex 출력, 오류, 절대 경로는 history에 복사하지 않습니다. history DB가 일시적으로 실패하면 private outbox에 남아 다음 cycle에서 재시도합니다. 완료 결과는 허용된 연구 영역에서 구체적 후속 작업을 하나만 제안할 수 있으며, 미래 데이터가 준비되지 않은 작업은 blocked 근거로 종료해야 합니다.

## 수동 단일 실행

```bash
cd backend
.venv/bin/python -m jusik.development_runner run-once --config ~/.config/jusik/development-runner.json
```

실행 전 local `main` branch와 tracked clean 상태가 필요합니다. untracked `HANDOFF.md`만 허용합니다. 저장소 공통 Git 디렉터리의 고정 lock이 다른 실행을 막아 SQLite와 무관하게 저장소 작업을 직렬화합니다. Codex invocation에는 연구 자료와 의존성 설치를 위한 workspace network 설정을 명시하지만 prompt는 brokerage 주문을 금지합니다. 각 cycle은 한 task만 처리하고, timeout·pause·SIGTERM은 소유한 process group을 정리한 뒤 시도 상태를 남깁니다. 실행 중인 이전 process group을 확인할 수 있으면 새 작업을 시작하지 않고 blocked 상태로 보존합니다.

## Codex 권한 프로필과 산출물 보존

실행기는 사용자 전역 설정을 수정하지 않고, 매 실행 시 `jusik-development` named permission profile을 CLI override로 전달합니다. 실행할 작업이 있고 dirty·quota·cooldown 검사를 통과하면, 자식 dispatch와 task claim 전에 정확히 설정된 `artifact_dir`를 생성·검사합니다. 준비에 실패하면 task나 일일 launch quota를 소비하지 않고 차단합니다. 프로필은 기본 `workspace` 권한을 상속하고(`extends=":workspace"`), 저장소의 실제 공통 Git 디렉터리에만 `write`를 부여하며, 정규화된 저장소·상태·history·artifact 경로를 `workspace_roots`로 명시하고 network를 활성화합니다. 기존 `repo.parent`와 `history_dir.parent` 허용도 유지하지만, 이를 최소 권한 범위라고 주장하지 않습니다. `artifact_dir`의 상위 경로를 추가 허용하지 않습니다. `danger-full-access`, bypass, ignore-rules, 기존 `-s`/`--add-dir` 조합과 전역 설정 변경은 사용하지 않습니다.

자식 실행에는 `--ignore-user-config`를 사용합니다. 이 옵션은 개인 사용자의 Codex 설정을 상속하지 않지만 저장된 인증과 관리형 규칙은 계속 적용합니다. 따라서 개인 설정에 의존하지 않고, 관리 대상 정책과 현재 실행에 필요한 named profile만으로 권한을 재현할 수 있습니다. 권한 프로필은 이 실행의 CLI override일 뿐이며 전역 설정 파일이나 다른 작업의 권한을 변경하지 않습니다.

각 runtime prompt는 통합 검사가 끝난 뒤 병합 worktree를 제거하기 전에 필요한 evidence, SHA-256 hash, handoff를 허용된 durable root에 보관하도록 요구합니다. completion JSON은 worktree 정리 뒤에도 남아 있는 파일만 참조해야 합니다. worktree 생성·통합·검증·정리의 전체 절차는 [워크트리 운영 절차](worktree-workflow.md#정리)를 따릅니다.

실제 spawn CLI가 role 필드를 제공하지 않는 환경의 명시적 model/fork routing과 receipt 기반 parent/child 감사는 [agent tooling의 roleless CLI 절차](agent-tooling.md#roleless-cli-routing)를 따르고 `backend/jusik/agent_routing.py` adapter를 사용합니다.

## 빈 큐 자동 연구 계획

`planning_enabled=true`이고 실행 가능한 연구 작업이 없으며 queued/running 연구 작업도 없을 때, 실행기는 내부 예약 영역 `__planning__`에서 planner를 한 번 dispatch합니다. planner는 기존 연구 task snapshot, 검증된 `main` HEAD, UTC 날짜를 fingerprint로 묶고 cost-adjusted portfolio return/risk/turnover 실험을 우선 검토합니다. planner state/history는 연구 pending 상한 8개에 포함하지 않습니다. 투자 로드맵 scope의 원자적 enqueue cap은 `queued`와 `running`만 계산하므로 과거 `blocked` 8개가 새 roadmap 작업을 막지 않습니다. research scope의 기존 pending 의미는 유지합니다.

planner는 최대 하나의 새 연구 task만 제안하거나, 고정된 한국어 대기 상태를 남깁니다. 제안 prompt에는 Objective, Scope, Inputs, Computation cap, Tests, Stop condition의 6개 섹션을 순서대로 짧게 담고 1600자 이내를 목표로 합니다(검증 hard cap 2000자). 기존 evidence만 SHA-256으로 참조할 수 있습니다. 제안을 검증한 뒤 연구 task enqueue, planner 완료, history outbox 기록을 하나의 SQLite transaction으로 처리합니다. 이 transaction 안에서 연구 task snapshot과 대기 상한을 다시 확인합니다. 입력 fingerprint가 바뀌면 재검토하고, 같은 fingerprint의 failed/interrupted/terminal planner는 자동 재시도하지 않습니다.

planner dispatch는 별도 `jusik-planning` named profile을 사용합니다. profile은 `:read-only`를 상속하고 해당 attempt directory만 write, network는 disabled로 둡니다. planner와 일반 child의 Popen 모두 `XDG_CACHE_HOME`, `UV_CACHE_DIR`, `PIP_CACHE_DIR`, `RUFF_CACHE_DIR`, `MYPY_CACHE_DIR`를 현재 attempt 하위 private cache로 설정합니다. `HOME`, `CODEX_HOME`, 전역 설정과 planner의 repository read-only 범위는 바꾸지 않습니다. planner는 읽기 전용 명령으로 근거를 확인할 수 있지만 repository, DB, config, remote, order API를 변경하거나 subagent를 생성할 수 없습니다. network 제한은 자식 셸 명령에 적용됩니다. 일반 연구 task의 `jusik-development` profile과 PAPER10% contract는 변경하지 않습니다. `planning_enabled` 기본값은 `false`이며 현재 설치 설정에서는 `true`로 활성화했습니다. 출력·schema·bounded length 오류의 재시도에는 안전한 고정 failure label만 다음 planner prompt에 전달하며, identity/hash/stale/permission/종료·중단 오류는 자동 재시도하지 않습니다.

## 투자 개발 로드맵 전용 scope

투자 로드맵 자동 실행은 기존 연구 실행기의 state와 큐를 공유하지 않는 `scope="investment-roadmap"` 전용 설정으로 초기화합니다. 기존 `~/.config/jusik/development-runner.json`과 state는 그대로 보존하며, 전용 설정 예시는 `roadmap-automation` audit에 남깁니다. 이 scope의 `run-once`와 `resume`은 versioned mandate governance, JSON·Markdown·checksum·canonical `policy_version`을 모두 검증하고, `dispatch_enabled=false`이거나 문서가 stale이면 SQLite claim·attempt·launch 전에 고정된 blocked 상태로 종료합니다. 일반 `research` scope의 기존 mandate 호환 경로는 변경하지 않습니다.

```bash
cd /home/kwl/projects/jusik/backend
.venv/bin/python -m jusik.development_runner init \
  --config ~/.config/jusik/roadmap-development-runner.json \
  --repo /home/kwl/projects/jusik \
  --state-dir ~/.local/share/jusik/roadmap-development-runner \
  --history-dir ~/.local/share/jusik/research-history \
  --history-db ~/.local/share/jusik/research-history-journal.db \
  --artifact-dir ~/.local/share/jusik/portfolio-audit \
  --scope investment-roadmap
```

초기화는 빈 큐만 만들며 첫 `r1-01` slice는 별도로 검토한 뒤 `enqueue --id roadmap-r1-01-v1 --area r1-01`로 준비합니다. 한 slice의 기술 완료와 전체 checklist 완료는 다르므로, 전체 조건을 충족하기 전에는 Markdown checkbox를 억지로 갱신하지 않습니다. 실행기는 tracked 로드맵과 mandate가 없거나 malformed이면 자식 dispatch를 하지 않습니다. 자동 child는 runner를 pause하거나 service를 중지하지 않습니다. 수동 변경 전에는 새 config로 `pause`한 다음 동일한 단일 service를 중지하고 `systemctl --user is-active jusik-development-runner.service`가 `inactive`인지 확인합니다. 검사가 끝나고 tracked worktree가 깨끗해진 뒤 같은 config로 `resume`합니다. 실제 주문·PAPER/live activation·운영 원장 변경은 이 scope에서도 금지합니다.
