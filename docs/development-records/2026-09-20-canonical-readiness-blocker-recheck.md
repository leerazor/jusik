# Canonical 성과 readiness blocker 재검증

- 기록 시각: 2026-09-20T01:45:00Z
- 실행: `diagnose_canonical_run()`으로 등록된 canonical run·session evidence·manifest·
  tracked calendar를 현재 main에서 읽기 전용 검증했습니다.

## 결과

- `status`: `blocked`
- `ready_for_metrics`: `false`
- `economic_evaluation`: `not-evaluated`
- 남은 missing codes:
  - `missing_initial_capital_at`
  - `missing_nav_timestamps`
  - `missing_risk_free_evidence`

calendar, session completeness, calculation policy와 modeled cost evidence는 현재
canonical 경로에서 검증되어 readiness 보고서의 missing 목록에서 제거됐습니다.

## 판정

- 초기자본 anchor와 각 NAV의 실제 UTC timestamp가 없으므로 calendar close를 소급해
  채우지 않습니다.
- 공식·구간별 무위험률 원본과 availability/compounding 정책이 없으므로 Sharpe를
  계산하지 않습니다.
- 따라서 CAGR/MDD/Sharpe/Calmar와 `MDD <= 20%` hard filter, R4 재실행, PAPER/live
  승격은 계속 차단합니다.

## 운영

- 읽기 전용 readiness 검증만 수행했습니다. 주문·PAPER/live·원격 push·runner resume·
  Windows 종료는 없습니다.
