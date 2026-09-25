# 고정 공학 backlog 소진 후 planner 조기 종료 조사

후속 상태(2026-09-26): 사용자가 밤사이 자동개발 중단을 지적하고 다음 과제 발굴을
명시적으로 요청했다. 아래 구현 보류는 당시 판단의 기록이며 현재 개발을 막는 지시가
아니다. `lab-engineering-discovery`가 기존 roadmap 단순 fallthrough와 별도로
읽기 전용 발굴·독립 범위 검토·공학 spec 등록 경로를 구현한다.

- 상태: 완료(조사·안전 결정); 자동 planner fallthrough 구현 보류
- 기록 시각: 2026-09-25T12:26:07Z
- 작업 slug: `lab-runner-backlog-exhaustion-audit`
- 기준/통합: `01a7aa9` / 해당 없음(코드 변경 없음; 이 기록은 별도 문서 커밋)
- 범위: 무인 개발이 고정 공학 spec 소진 뒤 `idle`에 머무는 원인을 읽기 전용으로 조사했다. runner 코드·운영 DB·투자 게이트는 수정하지 않았다.

## 변경과 결정

- `backend/jusik/development_runner.py`의 `run_once`는 READY가 없을 때 고정 공학 spec을 선택하고, 목록 소진 시 planner 분기 전에 바로 `idle`을 반환한다. `planning_enabled=true`만으로 이후 planner가 실행되지 않는다.
- 기존 roadmap planner는 미완료·phase 적격 area와 fingerprint·governance·queue cap을 사용하지만, 각 area의 실제 자료 준비와 제안의 사전 독립 검토를 증명하지 않는다. 단순 fallthrough는 새 작업 등록 권한을 넓히므로 적용하지 않았다.
- 안전한 연속 기획 후속은 검토된 area와 roadmap·mandate identity에 결속한 승인 기록을 정의하고, enqueue 트랜잭션 안에서 재검증해야 한다. 승인 없음·만료·identity 변화·잘못된 area·queue full·pause의 거부와 동일 fingerprint 재호출 0건이 최소 테스트다.

## 문서·계약 영향

- `docs/development-runner.md`에 `planning_enabled`와 고정 backlog 소진의 실제 상호작용을 명시했다. API·DB schema·설정은 바꾸지 않았다.

## 검증

- 대상 코드와 기존 backlog/planner 테스트·운영 status를 읽기 전용으로 확인했다. 실행 상태는 `fixed_engineering_backlog_exhausted`, READY/RUNNING 0건이었다.
- 9개 BLOCKED 중 8개는 `legacy_unknown`, 1개는 과거 독립 reviewer 부재다. 근거 없는 자동 retry를 하지 않았다. 변경 코드가 없으므로 신규 pytest·Ruff·mypy는 실행하지 않았다.

## 안전·운영 상태

- 실주문·PAPER/live activation·추가 결제·권한/credential 변경·원격 push 없음. 운영 runner는 문서 편집 중 pause, timer active이며 tracked main 커밋 뒤 resume한다. 사용자 미추적 `HANDOFF.md`를 보존했다.

## 증거와 재개

- 다음 시작: runner READY와 신규 자료 증거를 확인한다. 자동 기획을 확장한다면 먼저 사전 승인 주체·저장 형식·재검증 계약을 제한된 설계로 정하고, 그 전에는 검토된 유한 공학 spec 경로를 유지한다.
