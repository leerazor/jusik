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

설정 파일에는 저장소, Codex 실행 파일, 상태·history·artifact 경로, 시도 제한(기본 90분), UTC 일일 실행 상한(기본 8회), 실행 간 대기(기본 60초)를 명시합니다. history는 연구 화면의 기존 `~/.local/share/jusik/research-history`와 journal DB를 사용해야 기록이 웹에 나타납니다. `artifact_dir`는 `~/.local/share/jusik/portfolio-audit`를 사용해 분석 산출물을 검증하고 Codex named permission profile의 허용 루트로 제공합니다. 큐의 초기 작업은 entry amount distribution, 작은 진입 제약의 선행 조건, 미래 관찰 프로토콜, PAPER 신호 근거, portfolio stress robustness 순서이며 최대 8개의 미완료 작업만 유지합니다.

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

실행 기록의 history outbox는 고정된 한국어 상태 제목·요약과 task/attempt ID만 기록합니다. Codex 출력, 오류, 절대 경로는 history에 복사하지 않습니다. history DB가 일시적으로 실패하면 private outbox에 남아 다음 cycle에서 재시도합니다. 완료 결과는 허용된 연구 영역에서 구체적 후속 작업을 하나만 제안할 수 있으며, 미래 데이터가 준비되지 않은 작업은 blocked 근거로 종료해야 합니다.

## 수동 단일 실행

```bash
cd backend
.venv/bin/python -m jusik.development_runner run-once --config ~/.config/jusik/development-runner.json
```

실행 전 local `main` branch와 tracked clean 상태가 필요합니다. untracked `HANDOFF.md`만 허용합니다. 저장소 공통 Git 디렉터리의 고정 lock이 다른 실행을 막아 SQLite와 무관하게 저장소 작업을 직렬화합니다. Codex invocation에는 연구 자료와 의존성 설치를 위한 workspace network 설정을 명시하지만 prompt는 brokerage 주문을 금지합니다. 각 cycle은 한 task만 처리하고, timeout·pause·SIGTERM은 소유한 process group을 정리한 뒤 시도 상태를 남깁니다. 실행 중인 이전 process group을 확인할 수 있으면 새 작업을 시작하지 않고 blocked 상태로 보존합니다.

## Codex 권한 프로필과 산출물 보존

실행기는 사용자 전역 설정을 수정하지 않고, 매 실행 시 `jusik-development` named permission profile을 CLI override로 전달합니다. 프로필은 기본 `workspace` 권한을 상속하고(`extends=":workspace"`), 저장소의 실제 공통 Git 디렉터리에만 `write`를 부여하며, 존재하는 저장소·상태·history·artifact 루트를 `workspace_roots`로 명시하고 network를 활성화합니다. 이 범위가 공유 `.git` metadata와 연구 파일에 필요한 최소 쓰기 범위입니다. `danger-full-access`, bypass, ignore-rules, 기존 `-s`/`--add-dir` 조합과 전역 설정 변경은 사용하지 않습니다.

자식 실행에는 `--ignore-user-config`를 사용합니다. 이 옵션은 개인 사용자의 Codex 설정을 상속하지 않지만 저장된 인증과 관리형 규칙은 계속 적용합니다. 따라서 개인 설정에 의존하지 않고, 관리 대상 정책과 현재 실행에 필요한 named profile만으로 권한을 재현할 수 있습니다. 권한 프로필은 이 실행의 CLI override일 뿐이며 전역 설정 파일이나 다른 작업의 권한을 변경하지 않습니다.

각 runtime prompt는 통합 검사가 끝난 뒤 병합 worktree를 제거하기 전에 필요한 evidence, SHA-256 hash, handoff를 허용된 durable root에 보관하도록 요구합니다. completion JSON은 worktree 정리 뒤에도 남아 있는 파일만 참조해야 합니다. worktree 생성·통합·검증·정리의 전체 절차는 [워크트리 운영 절차](worktree-workflow.md#정리)를 따릅니다.
