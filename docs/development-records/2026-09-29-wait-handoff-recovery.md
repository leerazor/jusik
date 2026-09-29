# 대기 진단 인계 복구와 확정 구독 제약 전달

- 상태: 구현·작업자 focused 검증·독립 검토 완료; 통합·운영 재시도 대기.
- 날짜: 2026-09-29. 작업 slug: `wait-handoff-recovery`.
- 기준: `1c01dbfb2569de84d1984830a59d3a38013c589c`; 등록 `8811192`.
- 구현: `f1b16ec28ce7056487542639ff05c4ea80fb0cc2`, 문장/회귀 보정 `fbd20ef4f5a49d8566da8b67f8598f2e95932c04`.
- 작업 환경: `/home/kwl/.codex/worktrees/wait-handoff-recovery/jusik`, `codex/wait-handoff-recovery`.

## 원인과 수정

R1-05 진단 attempt `b6af09572cc2405a8aa63be725c27235`는 자료 대사를 끝내고
`waiting_external`을 반환했으나 `blocked_reason`과 `blocker.blocker_reason`이 달라
기존 runtime 검사에서 `completion_invalid`가 됐습니다. 출력 지침에 이 동일성 조건이
명시되지 않았습니다. 생산자 지침에 하나의 사유를 두 필드에 그대로 복사하도록 추가했고,
CLI 출력 경로 안내 뒤 독립 문장으로 전달합니다. validator·schema·상태 선택은 보존합니다.

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
- 독립 review PASS, 중대 지적 없음. 실제 모델의 지시 준수는 prompt 검사만으로 보장하지 않으며
  기존 runtime 거부를 유지합니다. 통합 후 검사는 아래 운영 결과와 함께 확정합니다.

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

## 다음 단계

정상 대기 보고 후 실제 자료 dependency 변경 전에는 같은 진단을 자동 반복하지 않습니다.
별도 자료/계산 작업은 기존 planner와 scope 검토를 거치며 R1/R2 선행 조건을 유지합니다.
통합·실행 결과와 재개 지점은 `docs/handoffs/2026-09-29-wait-handoff-recovery.md`에 남깁니다.
