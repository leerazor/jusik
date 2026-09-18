# R1 기업행동 artifact 근거 감사

## 범위

runner planner가 요구한 실제 action 근거를 기존 로컬 artifact에서 read-only로 확인했다. 신규 수집·합성·전략 실행·원장 변경은 하지 않았다.

## 확인된 artifact

- 경로: `/home/kwl/.local/share/jusik/portfolio-audit/20260910T100314Z-dividend-accounting/isolated-output/dividend-overlay-runs/28bb6a8aaf8097a4f41e6bf0e087393111c752daed43a675e5579b68f833597f/result.json`
- result SHA-256: `909e356c8b9588335ee435f636e1c16df4eace81aa7433505b4044cc61d5e9f1`
- source manifest SHA: `1a2934466efa12c09d08e7792b1a5e4b7c0c880d2aaabab9b25919bd0ec5c825`
- source result SHA: `db7ff9f5108e9112a495e2c47f8abf21cde8870f375139930e44ec01056ee8ca`
- review snapshot SHA: `3d740f674f965f48a19ca314dd20cafaababad55aae80a3143dae005ae153d08`

## 결과

artifact에는 stable `event_id`, `revision_id`, `review_id`, `evidence_id/evidence_sha256`, ex-dividend date, payment date, amount, currency가 있다. eligible event는 NVDA 1건이며 2024-06-11 ex, 2024-06-28 payment, USD 0.01, heldout entitled quantity 30이다. overlay entitlement에는 UTC 경계와 scenario별 quantity 30/38이 보존된다.

그러나 107개 dividend revision 중 eligible은 1건, excluded는 106건이고 대부분 `current_revision_unreviewed`이다. `coverage_complete=false`, `prospective_validation_eligible=false`, `automatic_ledger_application=false`이며 assumptions도 세전·후향·비 PIT라고 명시한다.

## 판정

이 artifact는 누락 사실과 partial evidence를 보존하는 진단 근거이지 R1-04/R1-05 전체 완료, strict PIT, prospective validation, 경제 성과 acceptance 근거가 아니다. 따라서 checkbox와 runner task 상태를 변경하지 않는다. 다음 retry 조건은 전체 action coverage와 원문 관측시각·권리 경계가 같은 고정 identity로 연결되는 것이다.

## 2026-09-19 재검증

동일 overlay CLI를 고정 local DB 경로에 대해 read-only로 재실행하려 했으나
SQLite 파일이 현재 존재하지 않아 `OperationalError: unable to open database file`로
fail-closed 종료했다. 기존 overlay artifact는 삭제·덮어쓰기하지 않았고, 이 실패는
새로운 금융 근거가 생겼다는 뜻이 아니다. DB 복구와 원문 SHA 재확인 전에는 R1-04/R1-05
retry나 경제 승격을 만들지 않는다.
