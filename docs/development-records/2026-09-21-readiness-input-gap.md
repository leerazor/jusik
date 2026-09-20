# Canonical readiness input-gap report

- 상태: 차단 유지·입력 계약 조사 완료
- 기록 시각: 2026-09-21T07:29:59+09:00
- 대상: 등록된 US pilot `us-web-pilot-run.json`
- source SHA-256: `cc9150f8b77a27ffd6b001449c0475933ff744a37011801923f87cbdc5558275`

## 확인 결과

`backend.jusik.market_performance_readiness`의 기존 읽기 전용 진단을 같은
expected SHA로 실행했습니다. 결과는 `status=blocked`, `ready_for_metrics=false`,
`economic_evaluation=not-evaluated`입니다. 기존 artifact와 policy hash는 변경하지
않았습니다.

누락 입력은 다음 7개입니다.

1. `missing_initial_capital_at`: 첫 자본금의 공식 session-open UTC anchor
2. `missing_nav_timestamps`: 각 NAV의 공식 session-close UTC timestamp
3. `missing_session_completeness_evidence`: 전체 세션의 관측·누락·중복 증빙
4. `missing_calendar_evidence`: 해당 run과 결속된 시장 캘린더 증빙
5. `missing_cost_inclusion_evidence`: 비용이 NAV에 포함되었다는 결속 증빙
6. `missing_risk_free_evidence`: 기간·publication/availability가 검증된 KOFR 등 무위험 수익률
7. `missing_calculation_policy`: 해당 run에 결속된 CAGR/MDD/Sharpe/Calmar 계산 정책

## 해석

이는 계산 버그가 아니라 canonical run이 metrics 입력 계약을 충족하지 못한 상태입니다.
환율 값이나 NAV를 보간·carry-forward하거나 기존 다른 run의 timestamp/policy를 재사용하면
point-in-time 및 overfitting 통제가 깨지므로 허용하지 않습니다. 이 보고서만으로 전략의
경제적 실패를 확정하지 않으며, 자료 gate가 닫힌 뒤 같은 정책으로 한 번 재실행해야 합니다.

## 다음 작업

- 동일 frozen input과 기간에 결속된 FX/PIT/회계 evidence를 확보할 수 있는지 계속 조사
- 확보되면 새 candidate artifact로 readiness를 재진단하고, 기존 canonical artifact는 보존
- 자료 gate가 닫힌 뒤에만 동일 정책의 단일 pilot 재실행 검토
- MDD `20%` 초과 시 PAPER 후보에서 제외

실거래·PAPER 승격·원격 push·Windows 종료는 수행하지 않았습니다.

## 검증

- readiness/accounting 관련 pytest: `52 passed, 3 failed`
- readiness 테스트는 통과했습니다. 실패한 3개는 frozen accounting bundle이 등록한
  과거 `research_portfolio_engine.py` SHA와 현재 source SHA가 달라진
  `engine_source_mismatch`입니다. historical bundle 또는 hash를 임의로 갱신하지
  않았으며, 별도 재생성·재등록이 필요한 기존 provenance 문제로 남겼습니다.
