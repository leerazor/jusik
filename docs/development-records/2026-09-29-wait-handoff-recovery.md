# 대기 진단 인계 복구와 확정 구독 제약 전달

- 상태: 코드 통합·검증 및 운영 대기 복구 완료. 투자 자료 확보는 계속 대기입니다.
- 날짜: 2026-09-29. 작업 slug: `wait-handoff-recovery`.
- 기준: `1c01dbfb2569de84d1984830a59d3a38013c589c`; 등록 `8811192`.
- 구현: `f1b16ec28ce7056487542639ff05c4ea80fb0cc2`, 문장/회귀 보정 `fbd20ef4f5a49d8566da8b67f8598f2e95932c04`.
- event 안내 보강: `3854943c93e1cea1e1357131d4ac7d9ae9376b55`.
- main 통합: `7688e5fb50b5438a04d93da56509e4f5d01af061`, 최종 `c477333b0c22d7f497c7ba605c59494e148369bf`.
- 작업 환경: `/home/kwl/.codex/worktrees/wait-handoff-recovery/jusik`, `codex/wait-handoff-recovery`.

## 원인과 수정

R1-05 진단 attempt `b6af09572cc2405a8aa63be725c27235`는 자료 대사를 끝내고
`waiting_external`을 반환했으나 `blocked_reason`과 `blocker.blocker_reason`이 달라
기존 runtime 검사에서 `completion_invalid`가 됐습니다. 출력 지침에 이 동일성 조건이
명시되지 않았습니다. 생산자 지침에 하나의 사유를 두 필드에 그대로 복사하도록 추가했고,
CLI 출력 경로 안내 뒤 독립 문장으로 전달합니다. validator·schema·상태 선택은 보존합니다.
event 대기는 실제 파일의 canonical 절대경로와 현재 SHA-256을 전달하도록 안내합니다.
파일이 없으면 설명문을 경로로 꾸미지 않고 `blocked`·`retry_policy=none`을 사용합니다.
이는 producer 안내이며 기존 runtime의 재해시·허용 경로 검사·변경 전 재개 거부는 유지됩니다.

공통 실제 dispatch 우선순위에는 사용자가 확인한 2026-10-04 날짜와 추가 지출 미승인,
월 $110 검토는 결제 승인이 아니라는 조건을 전달합니다. 정본은
[세션 정책](../continuous-development-session.md)이며 정확한 청구·종료 시각이나 자동
종료를 추정하지 않습니다. 새 예산·시간 제한 또는 큐 정렬 알고리즘은 구현하지 않았습니다.

## 검증

- 작업자 focused pytest 11 passed: actual fake-child stdin과 저장 prompt 일치, 새 제약,
  `waiting_external`·`waiting_human` 수용과 이유 불일치 거부, 기존 상태 전이·재개 검사.
- 재사용한 검사: roadmap의 `test_wait_states_keep_independent_ready_and_obey_utc_retry_cap`,
  `test_event_wait_releases_only_after_evidence_identity_change`,
  `test_wait_completion_requires_utc_blocker_and_manual_human_release`; runner의
  `test_blocked_failure_code_survives_reopen_as_structured_blocker`.
- 변경 두 파일 Ruff check/format, strict mypy (`--follow-imports=silent`), diff check PASS.
  변경되지 않은 imported roadmap 테스트의 기존 타입 오류를 이번 범위로 확대하지 않았습니다.
- 처음 환경 준비에서 시스템 Python 3.12의 ensurepip 부재를 확인하고 기존 프로젝트와 같은
  Python 3.13.15로 새 작업 venv만 다시 만들었습니다. 기존 `requirements.lock`을 사용했으며
  의존성 선언·시스템 Python·공유 venv는 변경하지 않았습니다.
- 최종 코드 독립 review PASS. 최종 main의 같은 focused pytest **11 passed (4.39s)**,
  Ruff check/format, 변경 두 파일 strict mypy, diff check PASS.
  원문 로그는 audit의 `final-integration.json`에 있습니다.
- explore/plan/code_small/review 사후 routing helper와 실제 model/effort 대조 PASS:
  `routing-final.json`. 실제 모델의 지시 준수는 prompt 검사만으로 보장하지 않습니다.

## 원본 보존과 운영 복구

- 수동 작업 전 기존 unpaused 상태를 확인하고 pause 및 service inactive로 전환했습니다.
  timer는 유지했습니다. 사용자 루트 `HANDOFF.md`는 수정하지 않습니다.
- SQLite online backup: `/home/kwl/.local/share/jusik/portfolio-audit/20260929-wait-handoff-recovery/runner-before.sqlite3`.
  SHA `27b5a7b231b66327c005087ad89bb07fccb89e2f7133ae050644f18fb673e110`.
- 원 completion SHA `bf900dde3ae8a96ba5dd990058e92239ae6a1c545196c5a9fa7fb4a0839dc1e5`.
  원 completion·실패 행은 수정하지 않습니다. 기존 `retry TASK_ID`로 새 시도를 만들고,
  한 번의 실제 보고 복구 결과를 원 실패 기록과 구분하여 보존합니다.
- 새 [증권 식별자 증거](2026-09-29-security-identity-evidence.md)는 별도 수집·독립 검토한
  보강 자료입니다. 기존 동결 진단 입력과 금융 승인 기준을 대체하지 않습니다.
- 추가 결제·credential·주문·PAPER/live·원격 push 없음. 새 수익성 증거 없음.

### 실제 재시도와 재개 연결 보정

기존 `retry`로 만든 새 attempt `5e479285de044145baa4ca391863c400`은
`waiting_external`, failure code null로 종료됐습니다. 원 attempt 전체 행과 원 completion
SHA는 불변이며, 실제 저장 prompt에 날짜·지출 제약과 이유 동일성 안내가 들어갔습니다.
`runtime.json`은 이 최초 복구 관측을 보존합니다. 새 completion SHA는
`d385833ad0e4609ecc674d36c42f0da058ad24ca15d3d0cffb1d927e24d340a6`입니다.

이 출력의 dependency는 파일 경로 대신 설명문이어서 기존 `_bind_event_dependency`가
identity를 null로 저장했습니다. 새 검사로 발견했으며, task/attempt/completion SHA를 고정한
일회성 운영 스크립트로 현재 task blocker의 **경로와 identity 두 필드만** 보정했습니다.
대상은 원 completion에 이미 등록되고 해시까지 일치하는
`/home/kwl/.local/share/jusik/portfolio-audit/20260929-security-identity-evidence/profile.json`입니다.
투자 승인·재큐·schema 변경 없이 별도 `runner_meta` 감사 행만 추가했습니다.

- 첫 복제 리허설은 null 정규화를 예상하지 못해 쓰기 전 assert에서 rollback했습니다.
  이후 기존 runtime 바인딩 결과와 저장 blocker 전체를 대조하도록 수정했습니다.
- 독립 검토는 운영 postcheck의 `release_event`가 증거 변경 경합 시 재큐할 수 있다고
  지적했습니다. 그 호출을 복제 리허설로 한정하고 운영 postcheck는 읽기 전용으로 바꿨습니다.
  v3 복제 리허설과 최종 독립 review PASS 후에만 운영 적용했습니다.
- 적용 직전 타이머가 서비스를 깨워 inactive 검사에서 중단됐습니다. 쓰기는 없었으며,
  timer와 service를 잠시 함께 정지하고 비활성을 확인한 뒤 적용했습니다.
- `event-binding-rehearsal-v3.json`: 동일 증거의 event 해제 거부, 모든 원 attempt·기타 행·schema
  보존과 DB 무결성 PASS. `event-binding-production.json`: 실제 적용 후 대기·원 행 보존과
  읽기 전용 postcheck PASS. 운영에서는 재큐 함수를 검증용으로 호출하지 않았습니다.
- `repair_event_binding.py`, 거부된 v2 사본, 전후 DB와 SHA를 같은 audit에 보존했습니다.
  일반 복구 CLI를 추가한 것이 아니며 같은 스크립트의 재적용은 거부됩니다.

## 문서와 실행 상태

세션 정책, runner 운영 문서, 작업 등록부, 이 기록과 별도 handoff를 갱신했습니다.
API·schema·금융 기준·mandate는 바뀌지 않았습니다. 완료된 앱 관리 worktree는 clean이며
다음 작업에 재사용하도록 보존합니다. 사용자 루트 `HANDOFF.md`는 그대로 둡니다.
추적 파일 커밋 후 기존 runner를 `resume`하고 timer를 복원합니다. 최종 실제 상태와 다음
child 관측은 같은 audit의 `resume.json`에서 확인합니다. 타이머만으로 작업 진행을 추정하지
않으며, 확인되지 않은 수익률이나 비용 절감을 보고하지 않습니다.

## 다음 단계

정상 대기 보고 후 실제 자료 dependency 변경 전에는 같은 진단을 자동 반복하지 않습니다.
별도 자료/계산 작업은 기존 planner와 scope 검토를 거치며 R1/R2 선행 조건을 유지합니다.
통합·실행 결과와 재개 지점은 `docs/handoffs/2026-09-29-wait-handoff-recovery.md`에 남깁니다.
