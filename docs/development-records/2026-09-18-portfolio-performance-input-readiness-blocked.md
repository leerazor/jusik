# Portfolio performance input readiness blocker

- 상태: 차단
- 기록 시각: 2026-09-18T00:00:00Z
- 작업 slug: `portfolio-performance-input-readiness`
- 기준/통합: `e4ccc4d2f8eb9f60c8d372ea226fffbc038d042b` / 없음
- 범위: 사용자 승인 UTC daily sampling policy와 기존 독립 modeled accounting을 성과 입력에 연결할 수 있는지 read-only로 판정했습니다. metrics adapter·성과 계산·readiness 승격은 구현하지 않았습니다.

## 조사와 판정

- UTC 날짜별 마지막 causally completed NAV를 daily CAGR/Sharpe/Calmar 표본으로 사용하고 MDD는 전체 chronology를 보존하는 정책은 사용자 승인으로 고정할 수 있었습니다.
- 그러나 tracked official calendar의 XKRX/XNYS close union은 `1,174`개이고 bundle stored NAV는 `1,172`개입니다.
- 누락 close는 `2026-06-03T06:30:00Z`와 `2026-07-17T06:30:00Z`입니다. 두 날짜 모두 XKRX 한국 6종목 raw bars가 없습니다.
- UTC 날짜 그룹만 대사하면 양쪽 모두 `614`일로 보여 누락이 숨겨집니다. sampling adapter가 이 불일치를 제거할 수 없습니다.
- 기존 metrics evaluator는 required session 누락을 `missing_required_sessions`로 처리해 전체 지표를 unavailable로 유지합니다. 없는 NAV를 보간하거나 이전 값을 복사하면 금융 데이터 합성이 됩니다.

## 문서·계약 영향

- `docs/market-performance-metrics.md`와 기존 evaluator 계약은 변경하지 않았습니다.
- `docs/worktree-tasks.md`에 차단 원인과 재개 조건을 기록했습니다.

## 검증

- 기존 canonical time-evidence CLI: 1,172 NAV와 ordered UTC timestamps 확인.
- official calendar와 sidecar close-group read-only 대사: union 1,174, stored 1,172, 위 두 누락 확인.
- 독립 modeled accounting report: 1,172 stored NAV 대사·잔차 `0 KRW` 유지. 이는 누락 세션의 완전성을 증명하지 않습니다.
- 이번 판정에서 새 simulation, network, provider, metrics 계산, tests 실행, artifact 변경은 하지 않았습니다.

## 안전·운영 상태

- 실제 주문, PAPER/live, runner resume, network/KOFR, DB/service/config/remote 변경 없음.
- 기존 historical/approximate·non-PIT·noncanonical 제한과 `ready_for_metrics=false`, 경제 `not-evaluated`를 유지합니다.

## 재개 조건

- 두 XKRX 세션의 원시 가격·공식 관측 근거가 고정 SHA로 제공되거나, 동일 기간을 포함하는 새 승인 입력이 준비되어야 합니다.
- 그 전에는 CAGR/MDD/Sharpe/Calmar 계산, hard-filter 판정, readiness 승격을 수행하지 않습니다.
- 다음 시작: 누락 세션 원천 자료가 들어오면 먼저 source/calendar/NAV completeness를 재대사하고, 없으면 blocker를 유지합니다.
