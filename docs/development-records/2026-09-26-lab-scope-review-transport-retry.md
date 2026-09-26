# 연구 scope reviewer의 일시 호출 장애 복구

- 상태: 완료. 구현 `a58fb6f`·경계 보완 `7ab122d`·별도 Sol 재검토 PASS, main `ee99764`
  집중 282개 검사·Ruff·strict mypy PASS. `ENGINEERING_COMPLETE/NOT_EVALUATED`다.
  선행 구현 완료 review `3814b6f`의 main 242개 검사 PASS 뒤 순차 시작했다.
- 작업: `lab-scope-review-transport-retry`; 3시간 sprint 종료는 2026-09-26T10:56:14Z다.
- 구현 시작: 전용 worktree 기준 `3130718812e75402e4ed8bc5eee1470a18351ccb`,
  09:23Z 무렵. 선행 제품 worktree는 정상 제거했고 branch·증거는 보존했다.
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

root가 보존한 새 운영 online backup은 `scope-transport/runner-before-scope-transport.db`,
SHA-256 `b9ddb708c0595a53676da9319eecc76917746990d0afe2f8782b1154c37670c4`다.
선행 review retry 열만 있고 scope retry 열은 아직 없다. 13개 table·1,322행·integrity
`ok`이며 구현자는 이 backup을 열지 않고 합성 fixture만 사용한다.

## 고정 후보와 독립 검토

제품 `a58fb6fdadcff8ef4f29c1527c38560ba3a3b79b`는 focused 244개와 최종 scope 37개,
Ruff·제품 ordinary strict mypy·소유 테스트 strict silent-import 검사를 통과했다.
독립 검토는 SQLite write lock 전의 시각을 TTL 판정에 사용하는 P2를 실제 잠금과
fake clock으로 재현했다. 잠금 중 만료뿐 아니라 자정 quota와 입력 검사 중 만료를
고려하여 `7ab122db02ce974c21cd1e770d51490e99f0fabc`에서 잠금 후·입력 검사 후 시각을
재확인하고 실제 claim 시각으로 모든 호출 회계를 결속했다. 신규 3개 RED→GREEN,
affected pytest 90개·Ruff·strict mypy PASS 뒤 독립 선별 9개 검사와 재검토를 통과했다.

테스트 helper 전체 import graph의 strict mypy 8개 진단은 실제 frozen 기준 `3130718`과
후보에서 동일함을 `cmp`로 확인했다. 두 비교 로그 SHA-256은
`2be08286323538056e02f92f2360f3a5b8303f9f20e6b09930df75809f98642a`다. 이를 새 오류로
숨기거나 전체 typecheck green으로 주장하지 않는다. 제품 두 파일은 일반 strict를
별도로 통과했으며 소유 테스트만 imported diagnostics를 silent로 검사했다.

root는 최종 후보로 실제 backup의 새 private 복사본을 두 번 초기화했다. 13개 table의
1,322개 기존 행·모든 기존 열과 index/trigger/view를 보존했고, 가산 scope retry 열만
NULL/NULL/0이었다. integrity `ok`, 원 backup SHA 불변이다. 증거는
`scope-transport/DB_PRESERVATION_FINAL.json`, 재현 script는 같은 폴더의
`verify_db_preservation.py`다. 운영 DB는 이 probe에서 열지 않았다.

runner lock·pause·실행 attempt 0·소유 경로 불변을 확인한 뒤 main
`ee997642409bb8b509b95debf5c68f41fca45472`로 통합했다. 병합 직전 main은
`cadb5d96af02bb5df90af551f92e6528b00ab103`이며 병행 UI 완료 변경을 보존했다.
실제 공급자 장애·인증 오류를 유발하지 않았고 과거 승인·실패를 재분류하지 않았다.
UI 감독자는 수동 성능 작업이 마친 뒤 재개하도록 책임을 인계했다.

main의 8개 집중 suite는 282개 PASS(219.62초), 소유 3파일 Ruff check/format PASS,
제품 2파일 ordinary strict mypy와 소유 3파일 strict silent-import 검사 PASS다.
JUnit은 `scope-transport/main-focused.xml`이다. frontend 변경은 없으므로 이 작업의
frontend build는 해당 없다. 넓은 전체 suite의 별도 TestClient 대기는
[성능 sprint 기록](2026-09-26-performance-sprint.md)의 진단·최종 검사를 따르며, 이
집중 검사로 해결됐다고 표시하지 않는다. handoff는
`docs/handoffs/2026-09-26-performance-sprint.md`에 통합한다.

최종 넓은 검사도 완료됐다: `ee99764`에서 전체 2,208개 PASS·기존 역사 hash pin 2개
FAIL·경고 2개, 400.72초. 직전 전체 실행의 대기는 이번에 재현되지 않았으며 원인 해결로
주장하지 않는다. 전용 worktree는 main 소유 blob 일치·ancestry·clean 확인 뒤 정상
제거했고 branch·commit·audit를 보존했다. 이후 운영 상태는 sprint audit `RUNTIME.md`를
확인한다.
