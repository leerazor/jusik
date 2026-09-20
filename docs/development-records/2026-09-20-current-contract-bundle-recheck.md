# Current contract bundle recheck

- 상태: 현재 코드 회귀 재검증 완료·경제 acceptance 차단 유지
- 기록 시각: 2026-09-20T00:00:00Z

## 검증

- KRX collector, SEC evidence/action review, action collection/corporate actions, cost evidence,
  performance metrics bundle을 현재 main에서 실행해 `243 passed, 2 warnings`를 확인했습니다.
- 기존 KRX zero/missing OHLCV·readiness insufficient, SEC operator facts 대기와
  `automatic_ledger_application=false`, risk-free/cost/PIT evidence 차단은 변경되지 않았습니다.

## 운영 경계

- runner bounded cycle·서비스·timer·자료 수집·원장·PAPER/live·실주문은 실행하지 않았습니다.
- 원격 push 및 Windows 종료는 수행하지 않았습니다.
- 기존 더 넓은 `290 passed` 기록은 당시 실행 범위를 보존하는 역사 기록이며, 이번 수치는 현재
  변경 이후의 명시된 bundle 범위에 대한 최신 결과입니다.
