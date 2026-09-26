# 지속 개발 실행기

지속 개발 실행기는 systemd user timer가 한 번에 하나의 제한된 연구 작업을 Codex에 전달하고, 결과를 검증한 뒤 다음 실행을 위해 SQLite 큐에 남기는 자동 개발 도구입니다. 작업 상태와 시도별 JSON·JSONL·stderr는 `state_dir` 아래 private 파일로 보관합니다. 실제 주문, 원격 push, GPU 서비스 변경, 전략 엔진 변경은 실행하지 않습니다.

운영자가 정한 연속 세션의 시작·마감 시각, 자동 복구 원칙, 중단 조건은
[연속 개발 세션 정책](continuous-development-session.md)을 canonical 문서로 사용합니다.
이 문서와 정책을 중복해서 수정하지 말고, 세션별 재개 정보는
[`docs/handoffs/`](handoffs/)에 날짜별로 기록합니다.

## 초기 설정

자율 연구소의 task/strategy 상태와 역할은 [설계 정본](autonomous-trading-lab.md)을
따릅니다. `blocked`·외부/사람 대기는 해당 작업의 상태이며 독립 READY 작업의 종료
조건이 아닙니다. 전역 Git/mandate/lock/명시적 pause 실패는 계속 전체 dispatch를 막습니다.

## Engineering 작업과 호환 상태

기존 투자 roadmap 작업은 체크리스트와 phase gate를 유지합니다. engineering 작업은
기존 고정 spec 또는 아래 자동 발굴 절차가 독립 검토한 spec으로 등록하고 같은
runner의 claim·증거·commit 검증을 사용합니다.
자료 없는 실제 투자 검증을 engineering으로 바꾸어 우회할 수 없습니다. 공학 완료는
독립 review receipt가 검증된 뒤에만 `ENGINEERING_COMPLETE`, 투자 판정은
`NOT_EVALUATED`이며 roadmap checkbox를 올리지 않습니다. 새 공학 후보는 우선
`WAITING_EXTERNAL`로 기록합니다. 별도 읽기 전용 reviewer attempt가 고정된 구현 시도,
시작·현재 main HEAD와 두 소유 파일 hash를 검토하고 PASS receipt를 제출하면 runner가
같은 입력을 재검증한 뒤 원자적으로 완료합니다. 최대 2회 bounded review이며 실패·
불가용·정체 불명 프로세스는 해당 task만 대기/격리하고 다른 READY를 계속 선택합니다.
이 대기는 일반 `retry --event-evidence`로 해제할 수 없습니다. 이전 버전의 검토 없는
대기/차단 기록은 새 경로가 소급 완료하지 않습니다. 실제 Codex reviewer의 운영
PASS는 신규 고정 오프라인 공학 작업에서 확인했으며 과거 차단 기록이나 투자 검증에
소급 적용하지 않습니다. fake CLI·임시 DB 검증 결과는 개발 기록을 확인합니다.

`investment-roadmap` 전용 `automatic_engineering_backlog`는 기본 `false`입니다.
설치 설정에서 명시적으로 켜면 기존 READY·review 후보를 우선 처리하고, 없을 때
`planning_enabled`인 roadmap에서는 아래 독립 scope 검토를 거치는 연구 준비 기회를 먼저
평가합니다. 실행 가능한 연구 제안이 없으면 사전 등록된 오프라인 작업 다섯 개(전략 버전 증거 영수증, paper 계약 재시작 중복 방지,
공유 journal 취소 경합 방지, 체결별 명시적 수수료 보존, receipt revision DB guard)를
각각 한 번만 등록해 같은 주기에 실행합니다. 기존 BLOCKED 작업은 재시도하거나
소급 완료하지 않습니다. 작업별 소유 파일·hash·독립 review가 일치해야 공학 완료이며
투자 검증은 계속 `NOT_EVALUATED`입니다. 고정 목록 소진 후에는
`automatic_engineering_discovery=true`일 때 아래 자동 공학 발굴로 이어집니다.
비활성이면 기존 `fixed_engineering_backlog_exhausted` 대기를 유지합니다.
일반 roadmap planner의 `planning_enabled`와는 별개이며 투자 자료·phase 조건은 유지합니다.
공학 backlog/discovery가 켜져 있다는 이유로 연구 planner 호출을 생략하지 않습니다.
READY 복귀와 소진 기록은 같은 DB 트랜잭션 경계로 관리합니다. 운영 제어는 기존
`resume`(진행)·`pause`(중지) 명령을 사용합니다. 타이머가 active인 것만으로 개발
진행이나 투자 검증을 의미하지 않습니다.

완료 형식 오류로 `FAILED/completion_invalid`가 된 공학 시도에서 이미 제품 커밋이
`main`에 들어간 경우, 일반 `retry`는 새 시도 baseline 이후 정확한 소유 파일 diff를
요구하므로 같은 커밋을 재사용할 수 없습니다. 제한된 운영자 명령
`recover-failed-candidate TASK_ID --attempt-id ATTEMPT_ID --expected-source-sha256 SHA256`
은 runner를 pause한 상태에서만 사용합니다. 운영 DB를 먼저 SQLite online backup으로
보존하고, 원본 completion JSON의 현재 SHA-256을 읽기 전용으로 확인해야 합니다.
명령은 원본 실패 행을 수정하지 않고 별도 복구 후보를 만듭니다. 원본 출력의 좁은 형식
오류, 실행 transcript의 최종 메시지 일치, 원 시도 baseline→제품 커밋의 정확한 소유
파일 diff, 이후 파일 불변성·증거 hash를 검사합니다. `resume` 뒤 별도 읽기 전용
reviewer의 PASS receipt가 있어야만 `ENGINEERING_COMPLETE/NOT_EVALUATED`가 됩니다.
원본 출력과 transcript에는 과거 실패 시점의 암호학적 해시가 없으므로 이 절차는
복구 시점의 내용 일치와 독립 검토를 증명할 뿐, 과거 파일이 한 번도 바뀌지 않았음을
증명하지 않습니다. 일반 완료·투자 검증·주문 게이트는 완화하지 않습니다.
새 `completion_invalid` 공학 시도는 실패 처리와 같은 SQLite 트랜잭션에서 출력
SHA-256(출력을 읽을 수 없으면 명시적 null)과 첫 적용 시도의 rowid 경계를 기록합니다.
이후 복구는 해당 해시가 반드시 일치해야 하며, 출력이 없거나 기록이 제거되면 거부합니다.
첫 적용 전에 생성된 SQL NULL 실패 기록에만 위 legacy 복구 절차를 허용합니다.
이 기록은 출력 파일의 실패 시점 무결성을 높이지만 DB 자체의 임의 쓰기나 실행
transcript의 과거 불변성까지 증명하지는 않습니다.
공학 자식은 통합 후 canonical `main` 저장소의 지정된 소유 파일에서 SHA-256을 계산해
완료 증거에 그 절대 경로를 넣어야 합니다. 작업용 worktree나 audit 복사본을 소유 파일
증거로 제출하면 검증에 실패합니다. 재시도는 기존 작업 기록과 시도 산출물을 확인하고,
기존 브랜치가 있으며 소유권이 일치할 때만 재사용합니다.

```bash
cd backend
.venv/bin/python -m jusik.development_runner enqueue \
  --config /home/kwl/.config/jusik/roadmap-development-runner.json \
  --kind engineering --spec lab-paper-execution-contract-v1
```

이 spec은 오프라인 execution interface와 fake-broker의 중복/부분체결/취소/거절/재시도/대사
계약만 허용합니다. KIS 호출·계정 변경·PAPER/live activation은 포함하지 않습니다.
이 수동 명령은 계속 고정 spec만 허용합니다. 자동 발굴도 검토된 소스·테스트 쌍 안에서만
spec을 등록하며, 허용 범위 자체의 확대는 별도 코드·문서 검토가 필요합니다.

canonical task state는 READY/RUNNING/BLOCKED/WAITING_EXTERNAL/WAITING_HUMAN/FAILED/DONE이며
legacy 소문자 상태와 과거 attempt를 보존합니다. 구조화된 blocker는 사유, 시도한 조치,
의존성, 재개 조건, retry 정책·최초 허용 시각, 대안 task를 기록합니다. 과거 기록에 없는
정보는 unknown과 빈 attempted_actions로 표현하고 새 사실을 만들지 않습니다.
기존 완료 이력만으로 ENGINEERING_COMPLETE 또는 INVESTMENT_VALIDATED를 추론하지 않습니다.

외부·사람 대기는 active queue 상한을 점유하지 않습니다. 사람 승인은 자동 retry로
만들지 않습니다. 자세한 CLI/DB 검사 결과와 이번 구현 범위는
[개발 기록](development-records/2026-09-25-autonomous-lab.md)을 확인합니다.

## 빈 큐의 자동 공학 과제 발굴

`automatic_engineering_discovery`의 기본값은 `false`입니다. 이 설치에서는 사용자의
2026-09-26 연속 자동개발 요청에 따라 통합 검증 후 활성화합니다. 기존 READY와 구현
review가 먼저이며, 고정 backlog 소진 시 읽기 전용 발굴 agent가 실제 코드의 결함이나
미구현 계약을 근거와 함께 제안합니다. 제안 범위는 별도 읽기 전용 reviewer가 확인합니다.
검토 PASS와 현재 입력의 일치가 확인된 spec만 SQLite transaction에서 등록·enqueue됩니다.
사용자가 일반 공학 과제마다 다시 진행을 승인할 필요는 없습니다.

초기 허용 모듈은 `paper_execution_contract`, `strategy_lifecycle_receipt`,
`research_future_observation_replay`, `research_market_calendar`, `market_performance_metrics`,
`research_portfolio_performance_metrics`, `market_history_action_accounting`,
`market_loss_accounting`입니다. 제안 하나는 `backend/jusik/<module>.py`와
`backend/tests/test_<module>.py` 중 정확히 한 쌍만 소유합니다. 단순 서식·문서·테스트
개수 늘리기가 아니라 재현 가능한 제품 결함이나 필요한 동작을 다룹니다.

발굴과 범위 검토는 repository 읽기 전용·network disabled로 실행합니다. 실행기·설정·의존성·
인증정보·투자 검증 기준·실제 주문·PAPER/live 활성화는 제안으로 바꿀 수 없습니다.
실제 구현은 기존 개발 child의 권한을 재사용합니다. 소유 경로 검증은 완료 검증이며
OS 수준의 파일 쓰기 격리를 새로 보장한다는 뜻은 아닙니다.

오프라인 제품 검증은 provider·주문 API를 사용하지 않는다는 뜻입니다. 이미 커밋된
고정 requirements를 작업 전용 venv에 설치하는 것은 기존에 허용된 설치 네트워크 안에서
가능합니다. 새 의존성 선언·버전 pin·네트워크 권한을 바꾸거나 실제 자료를 조회하는
승인은 아닙니다. 기존 연구 작업에 허용된 자료 수집 정책도 바꾸지 않습니다.
환경 실패를 보고할 때 `dependency_identity`는 알 수 없으면 `null`, 파일 부재이면
`missing`, 확인된 경우에만 SHA-256을 사용합니다. `bounded` retry에는 UTC deadline을
지정하고 나머지 retry 정책의 deadline은 `null`로 둡니다. 잘못된 실패 출력을
사후 수정해 유효한 증거로 바꾸지 않습니다.

제안은 코드·테스트 tree, mandate, 실제 task 상태에 결속됩니다. 등록 직전에 현재 HEAD와
근거 hash도 다시 검사하며 spec과 소유 경로는 재시작 뒤에도 보존됩니다. 같은 입력에서
서로 다른 후보는 최대 3건까지 검토하며 거절 근거를 다음 발굴에 전달합니다.
실행 가능한 작업이 없다는 결과에는 확인한 영역과 구체적인 재개 조건·대안이 필요합니다.
명시적인 `no_work` 이후에는 단순 시각 경과나 discovery 자체 기록 때문에 같은 LLM 검사를 다시 호출하지 않습니다.
기존 quota·cooldown·pause·process 정체 검사를 각 호출에 적용합니다.

발굴·범위 검토의 호출 실패는 `no_work`와 다릅니다. 종료된 child의 크기 제한 JSONL에서
구조화된 실패 이벤트로 확인한 capacity·429·네트워크·5xx 오류와 runner가 관측한 timeout은
5분, 15분, 이후 60분 간격으로 재시도합니다. 명확한 401은 기존 인증을 바꾸지 않고
6시간 뒤 재시도합니다. 오류 원문 대신 제한된 분류와 `retry_after`·`transient_failures`를
SQLite에 저장하며 재시작해도 유지합니다. 같은 proposal과 identity를 보존하고 기한 전에는
새 호출을 하지 않습니다. 독립 READY·구현 review는 이 재시도보다 우선합니다.
이는 공급자 호출 복구 정책이지 인증·과금·모델·권한 변경 승인이 아닙니다.
무효 결과·미분류 오류는 기존 2회 실패 제한, 명시적인 `no_work`·후보 소진·무결성 문제는
기존 종료 조건을 유지합니다. 과거 terminal 행을 소급 수정하지 않습니다.

범위 검토 PASS는 작업 등록만 허용합니다. 구현 뒤에도 정확한 변경 파일·증거·커밋과
별도 코드 review가 필요하며, 최종 판정은 `ENGINEERING_COMPLETE/NOT_EVALUATED`입니다.
범위 거절·실패·자료 대기가 독립 READY 작업을 막지 않습니다.

## 기존 연구 큐 초기화

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

설정 파일에는 저장소, Codex 실행 파일, 상태·history·artifact 경로, 시도 제한(기본 90분), 출력 무활동 제한(기본 15분), UTC 일일 실행 상한(기본 8회, 허용 범위 1~24회), 실행 간 대기(기본 60초)를 명시합니다. `automatic_recovery` 기본값은 `false`이며 설치별로 명시적으로 켜야 합니다. 필드를 생략하면 기본값 8회이며, `daily_launches: null`은 사용자가 승인한 무제한 모드입니다. 무제한 모드에서도 기존 launch history, timeout, pause, lock 동작은 유지됩니다. 자식 Codex가 stdout/stderr에 15분 동안 아무 이벤트도 쓰지 않으면 runner는 프로세스 그룹을 정리하고 `idle_timeout` 실패로 기록하며 자동 재실행하지 않습니다. 일일 상한은 금액·토큰 예산이 아니라 자식 Codex dispatch 횟수 제한입니다. 90분 시도 제한과 실행 간 60초 cooldown은 그대로 유지합니다. 현재 설치 설정은 `null` 무제한으로 운영합니다. history는 연구 화면의 기존 `~/.local/share/jusik/research-history`와 journal DB를 사용해야 기록이 웹에 나타납니다. `artifact_dir`는 `~/.local/share/jusik/portfolio-audit`를 사용해 분석 산출물을 검증하고 Codex named permission profile의 허용 루트로 제공합니다. 큐의 초기 작업은 entry amount distribution, 작은 진입 제약의 선행 조건, 미래 관찰 프로토콜, PAPER 신호 근거, portfolio stress robustness 순서이며 최대 8개의 미완료 작업만 유지합니다.

위 `idle_timeout` 자동 재실행 금지는 일반 연구·구현 task의 기본 동작입니다.
읽기 전용 discovery/scope 시도에는 앞서 설명한 지연 재시도 정책을 적용합니다.
프로세스 종료를 확인하지 못한 orphan은 이 예외로 재실행하지 않습니다.

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

실행기는 기본 supervisor(Sol) 사이클을 한 번에 하나만 실행합니다. 대화형 supervisor의 전체 한도는 planner 포함 4명(하위 3명)이며 모델은 [agent tooling](agent-tooling.md)을 따릅니다. 현재 자동 runner child는 host의 검토 호출 정체를 막기 위해 중첩 spawn을 금지합니다. 독립 검토가 확보되지 않으면 스스로 독립 검토를 통과했다고 표시하지 않고 해당 작업만 대기시킵니다. 선행 결과가 필요한 작업과 `main` 병합은 순차 처리합니다. Astra는 선택적인 읽기 전용 진단이며 자동 model-switch가 아닙니다. 병합한 워크트리는 [워크트리 운영 절차](worktree-workflow.md#정리)에 따라 정리합니다.

자동 코드 delivery의 child는 그 작업의 단일 구현자이지 하위 구현자·reviewer를 다시
모으는 supervisor가 아닙니다. 동결된 spec의 소유 파일만 구현·검사하고 미검토 후보를
제출합니다. host가 별도 읽기 전용 완료 reviewer를 호출합니다. 이 역할 분리는
대화형 supervisor의 조사→계획→구현→독립 검토 원칙을 없애는 것이 아니라,
자동 실행에서 각 단계를 실제 제공되는 host 경로에 배치하는 규칙입니다.

## 상태와 수동 제어

```bash
cd /home/kwl/projects/jusik/backend
.venv/bin/python -m jusik.development_runner status --config ~/.config/jusik/development-runner.json
.venv/bin/python -m jusik.development_runner pause --config ~/.config/jusik/development-runner.json
.venv/bin/python -m jusik.development_runner resume --config ~/.config/jusik/development-runner.json
.venv/bin/python -m jusik.development_runner retry --config ~/.config/jusik/development-runner.json entry-amount-distribution-v1
```

수동으로 저장소를 수정해야 할 때는 반드시 먼저 `pause`를 실행하고, `systemctl --user stop jusik-development-runner.service`를 실행한 다음 `systemctl --user is-active jusik-development-runner.service`가 `inactive`인지 확인합니다. 수동 통합과 검사를 끝내고 tracked worktree를 깨끗하게 만든 뒤 `resume`하고 timer를 다시 확인합니다. 실행기는 스스로 unit을 중지하거나 pause하지 않습니다.

`running` 시도는 재시작 때 `interrupted`로 보존되며 자동으로 다시 실행하지 않습니다. `retry TASK_ID`가 이전 시도 ID를 기록한 뒤 명시적으로 큐에 넣습니다. Codex가 종료 코드 0을 반환해도 commit이 local `main`의 조상인지, evidence 파일의 SHA-256과 허용 경로를 검증하지 못하면 완료로 기록하지 않습니다. 기존 generic/legacy research의 `tests_passed`와 `review_passed`는 agent가 보고하는 값이며 runner가 대신 검사하거나 독립 review를 주장하지 않습니다. 동결된 code delivery는 아래 별도 host review 계약을 사용합니다. 미래 데이터가 없으면 `status=blocked`와 사유를 제출할 수 있고, 이 결과는 commit·evidence를 요구하지 않습니다. 실패·중단·blocked 시도는 명시적 retry 전까지 격리합니다.

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

실제 spawn CLI가 role 필드를 제공하지 않는 환경의 명시적 model/fork routing과 receipt 기반 parent/child 감사는 [agent tooling의 roleless CLI 절차](agent-tooling.md#roleless-cli-routing)를 따르고 `backend/jusik/agent_routing.py` adapter를 사용합니다. stale loaded-role fallback에서는 host가 지원하는 경우 `agent_type=default`, 기대 model·reasoning effort, `fork_turns=none`을 명시하며 adapter/helper의 exact-five 계약은 바꾸지 않습니다. 일반 코드 문제는 서로 다른 가설이 두 번 실패한 뒤 Astra 진단을 제한적으로 사용하고, 명백히 복잡한 금융 계산·미래 데이터 누출·설계 충돌은 감독 근거를 남기고 처음부터 한 번 선택할 수 있습니다. 외부 근거 부족은 source alternative 또는 독립 task로 전환합니다.

## 빈 큐 자동 연구 계획

`investment-roadmap`의 새 planner 제안은 직접 연구 task로 등록하지 않습니다.
검증된 단일 제안과 evidence를 pending으로 보존하고, 별도 읽기 전용 scope reviewer가
자료·회계·사전등록 호환성·offline 계약 진단 범위와 실제 입력을 확인합니다.
PASS receipt가 원 proposal/evidence·planner attempt·fingerprint·HEAD·mandate·roadmap에
결속되고 등록 직전 phase/area·예약·중복·queue cap·pause 검사가 통과해야 한 건을 등록합니다.
자료 부재·REJECT·무효 결과는 등록하지 않고 공학 fallback을 계속합니다.
이 범위 검토는 독립 구현 review나 투자 검증을 대신하지 않습니다. 새로운 전략 평가,
OOS 재사용·winner 선정·PAPER/live·실주문 권한을 일반 planner에 주지 않습니다.
기존 generic `research` scope의 계약과 과거 planner 결과는 소급 변경하지 않습니다.

새 roadmap pending 제안은 24시간 뒤 만료하며, 독립 scope 등록 직전에도 현재 입력과
증거를 재검증합니다. DB에 결속된 roadmap scope는 호출 인자를 생략하더라도 기존
`finish_planning`의 직접 등록 경로를 사용할 수 없습니다. 새 scope 승인 task의
`completion.followup`은 `null`이어야 합니다. 후속 아이디어는 다음 planner와 독립
scope 검토를 거쳐야 하며, 완료 출력으로 검토 없는 task를 직접 증식시키지 않습니다.
기존 generic 연구·legacy roadmap task의 후속 계약은 변경하지 않습니다.

### 범위가 승인된 roadmap 코드 산출물

새 scope 검토에서 명시적으로 code-only 실행 계약을 승인한 작업만 기존 engineering
구현·독립 완료 review 경로를 재사용합니다. v2 계약은 정확한 source/test 한 쌍과
host가 확인한 baseline 파일 hash를 proposal/evidence·planner attempt·HEAD·mandate·
roadmap identity에 결속합니다. 초기 허용 범위는 R2-01의 `market_loss_accounting.py`
쌍과 R2-02의 `broker_cost_profiles.py` 쌍입니다. 임의 파일, 실행기·권한·의존성 변경,
새 금융 실험 또는 데이터 부족의 투자 검증 대체를 허용하지 않습니다.

v2의 입력 evidence는 승인 준비 시 원문 경로와 실제 canonical 경로의 대응도 동결합니다.
원래 proposal/evidence digest는 바꾸지 않고, scope 검토·등록·dispatch·완료가 같은
동결 경로를 검사합니다. 재시작이나 CWD 변경으로 상대경로를 다른 파일에 연결하지
않으며 tilde·정규화 경로도 같은 의미를 유지합니다. symlink와 입력 hash 변조는 거부합니다.

scope receipt와 동결 spec, task 등록은 함께 원자적으로 저장합니다. 별도 roadmap
provenance를 보존하며 engineering discovery의 승인 기록으로 위장하지 않습니다.
원래 roadmap area는 유지하고 dispatch와 완료 시 phase·mandate·필수 입력을 다시
검증합니다. delivery가 engineering이라는 이유로 투자 roadmap gate를 우회하지 않습니다.

구현 child는 `review_passed=false`인 후보만 제출하고, 별도 host reviewer의 정확한
task/attempt/baseline/commit/파일 hash PASS 뒤에만 `ENGINEERING_COMPLETE`가 됩니다.
투자 상태는 `NOT_EVALUATED`이며 roadmap 단계 완료·PAPER/LIVE 승격은 별도입니다.
scope PASS는 등록 승인이고, 독립 완료 review를 대신하지 않습니다.

기존 v1 승인에는 파일 소유 계약을 소급 부여하지 않습니다. 과거 BLOCKED/FAILED의
prompt·attempt·receipt는 유지하며 새로운 실행 권한이나 retry로 자동 전환하지 않습니다.
기존 작업의 실제 수동 구현·외부 독립 검토를 마쳤다면 그 task에 한정된 증거를 보존하고
기존 명시적 retry로 확인·보고할 수 있지만, 검토 문서를 만들어 자체 승인하는 일반 복구
방식으로 확대하지 않습니다. reservation·queue cap·투자 검증 기준은 그대로입니다.

`planning_enabled=true`이고 실행 가능한 연구 작업이 없으며 queued/running 연구 작업도 없을 때, 실행기는 내부 예약 영역 `__planning__`에서 planner를 한 번 dispatch합니다. research scope는 기존 task snapshot, 검증된 `main` HEAD, UTC 날짜를 fingerprint로 묶고 cost-adjusted portfolio return/risk/turnover 실험을 우선 검토합니다. investment-roadmap scope는 task snapshot, roadmap SHA-256, mandate governance digest, `main:backend/jusik` tree SHA-256으로 fingerprint를 묶습니다. 이 scope에서는 날짜와 unrelated commit이 planner identity를 바꾸지 않으며, roadmap·mandate·task·backend code 변경은 새 계획 검토를 만듭니다. `--planning-wait`를 붙인 `retry`는 completed 상태의 roadmap planner 중 마지막 결과가 `planning_waiting`인 task만 다시 큐에 넣고 이전 attempt ID를 연결합니다. 제안을 저장할 때는 fingerprint와 별도로 시작 시점의 `main` HEAD가 유지됐는지 확인합니다. planner state/history는 연구 pending 상한 8개에 포함하지 않습니다. 투자 로드맵 scope의 원자적 enqueue cap은 `queued`와 `running`만 계산하므로 과거 `blocked` 8개가 새 roadmap 작업을 막지 않습니다. research scope의 기존 pending 의미는 유지합니다.

로드맵 waiting 계획을 명시적으로 다시 판단하려면 `status`에서 내부 `__planning__` task ID를 확인한 뒤 다음처럼 요청합니다. 보통의 `retry TASK_ID`는 기존 실패·차단·중단 재시도 규칙만 적용합니다.

```bash
.venv/bin/python -m jusik.development_runner retry \
  --config ~/.config/jusik/roadmap-development-runner.json \
  --planning-wait <planner-task-id>
```

planner는 최대 하나의 새 연구 task만 제안하거나, 고정된 한국어 대기 상태를 남깁니다. 제안 prompt에는 Objective, Scope, Inputs, Computation cap, Tests, Stop condition의 6개 섹션을 순서대로 짧게 담고 1600자 이내를 목표로 합니다(검증 hard cap 2000자). 기존 evidence만 SHA-256으로 참조할 수 있습니다. 기존 `research` scope만 제안 검증 뒤 연구 task enqueue, planner 완료, history outbox 기록을 하나의 SQLite transaction으로 처리합니다. `investment-roadmap`은 우선 pending으로 보존하고 독립 scope PASS 후 별도 원자 등록을 수행합니다. 각 등록 transaction 안에서 연구 task snapshot과 대기 상한을 다시 확인합니다. 입력 fingerprint가 바뀌면 재검토하고, 같은 fingerprint의 failed/interrupted/terminal planner는 자동 재시도하지 않습니다.

planner dispatch는 별도 `jusik-planning` named profile을 사용합니다. profile은 `:read-only`를 상속하고 해당 attempt directory만 write, network는 disabled로 둡니다. planner와 일반 child의 Popen 모두 `XDG_CACHE_HOME`, `UV_CACHE_DIR`, `PIP_CACHE_DIR`, `RUFF_CACHE_DIR`, `MYPY_CACHE_DIR`를 현재 attempt 하위 private cache로 설정합니다. `HOME`, `CODEX_HOME`, 전역 설정과 planner의 repository read-only 범위는 바꾸지 않습니다. planner는 읽기 전용 명령으로 근거를 확인할 수 있지만 repository, DB, config, remote, order API를 변경하거나 subagent를 생성할 수 없습니다. network 제한은 자식 셸 명령에 적용됩니다. 일반 연구 task의 `jusik-development` profile과 PAPER10% contract는 변경하지 않습니다. `planning_enabled` 기본값은 `false`이며 현재 설치 설정에서는 `true`로 활성화했습니다. 출력·schema·bounded length 오류의 재시도에는 안전한 고정 failure label만 다음 planner prompt에 전달하며, identity/hash/stale/permission/종료·중단 오류는 자동 재시도하지 않습니다.

## 투자 개발 로드맵 전용 scope

투자 로드맵 자동 실행은 기존 연구 실행기의 state와 큐를 공유하지 않는 `scope="investment-roadmap"` 전용 설정으로 초기화합니다. 기존 `~/.config/jusik/development-runner.json`과 state는 그대로 보존하며, 전용 설정 예시는 `roadmap-automation` audit에 남깁니다. 이 scope의 `run-once`와 `resume`은 versioned mandate governance, JSON·Markdown·checksum·canonical `policy_version`을 모두 검증하고, `dispatch_enabled=false`이거나 문서가 stale이면 SQLite claim·attempt·launch 전에 고정된 blocked 상태로 종료합니다. manifest는 현재 JSON 전체 bytes hash, immutable legacy execution identity projection, canonical governance-object projection을 별도 항목으로 직접 검증합니다. historical execution identity는 기존 policy consumer가 계속 사용하고, roadmap dispatch는 `#governance-object` projection을 사용합니다. planner/task claim 직전에도 git readiness와 같은 governance digest를 재검증하며, uncommitted 문서 교체는 queue·attempt·launch 전에 차단합니다. 일반 `research` scope의 기존 mandate 호환 경로는 변경하지 않습니다.

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
