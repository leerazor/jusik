# 연구 scope reviewer의 일시 호출 장애 복구

- 상태: 조사·계획 완료, 순차 구현 준비. 선행 구현 완료 review `3814b6f`와 main 242개
  검사 PASS 뒤 시작한다. 같은 runner/store를 동시에 수정하지 않는다.
- 작업: `lab-scope-review-transport-retry`; 3시간 sprint 종료는 2026-09-26T10:56:14Z다.
- 범위: runner/store와 새 전용 scope transport 테스트를 단일 Sol이 소유하고 별도 Sol이
  검토한다. root는 문서·등록부·실제 backup 복사본 보존 검사·main 통합·handoff를 맡는다.

## 근거와 결정

기존 scope reviewer의 비정상 종료는 모두 `codex_exit` terminal failure로 끝난다.
discovery의 구조화된 오류 분류기는 재사용할 수 있지만 부모 scope의 24시간 TTL과
정확한 HEAD·snapshot·governance·evidence 계약은 별도다. 단순 pending 유지 방식은
구버전이 새 기한을 무시하고 조기 재호출할 수 있어 쓰지 않는다.

부모 scope에 nullable `retry_kind`, `retry_after`, 기본 0인 `transient_failures`만
가산한다. 확인된 종료와 bounded 구조화 오류만 새 `transport_wait`로 원자 저장한다.
planner task/attempt는 원 `scope_pending`, 제안 JSON/SHA·identity·expiry는 그대로다.
기한 전에는 selector가 이 후보를 건너뛰어 READY·공학 fallback을 계속한다. due claim은
같은 transaction에서 모든 기존 gate와 기한을 재검사하고 pending·active review·running
attempt·launch를 함께 만든다. 공개 상태는 안전한 kind·횟수·기한만 추가한다.

backoff는 5/15/60분 이후 60분, auth 6시간이며 모든 호출은 기존 quota·cooldown을
소비한다. 원 TTL을 연장하지 않고, TTL이 먼저 오면 기한 전에도 stale 정리한다.
독립 작업이 HEAD나 snapshot을 바꾸면 원 제안은 stale이며 호출·승인하지 않는다.
새 fingerprint의 새 계획은 가능하지만 기존 제안이나 승인 근거를 다시 쓰지 않는다.
구현 완료 review의 ancestry 예외는 이 경로에 적용하지 않는다.

## 검증과 되돌리기

fake CLI/clock으로 실패→기한→독립 READY/fallback→재시작→별도 PASS를 증명한다.
연속 장애·auth·TTL·동시 claim·트랜잭션 rollback·pause/quota/cap·변조·무효 metadata와
legacy terminal 보존을 확인한다. 실제 이전 store가 새 wait를 기한 전후 선택하지
않고, due claim 후 crash는 기존 orphan 격리로 처리함을 임시 DB에서 검증한다.
반복 migration 뒤 모든 기존 행·열과 integrity를 검사한다. DB 복원·열 삭제·기존
wait의 일괄 pending 변경·legacy 실패 자동 복구는 하지 않는다.

집중 scope/roadmap-code/discovery/implementation-review pytest, Ruff·strict mypy,
독립 검토·main 검증이 완료 조건이다. 구현 45분을 넘기거나 receipt 재설계·TTL/HEAD
완화가 필요하면 미완료 branch와 정확한 실패를 남기고 검토를 생략하지 않는다.

audit은 성능 sprint의 `SCOPE_REVIEW_RECOVERY_PLAN.md` 및 새 `scope-transport/`다.
실주문·provider·credentials·유료 호출·권한·투자 기준·frontend·원격 push·Windows
종료는 범위 밖이며 UI 수동 작업과 공유한 runner pause를 유지한다.
