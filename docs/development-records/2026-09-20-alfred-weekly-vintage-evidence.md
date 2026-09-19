# ALFRED 주간 vintage FX 근거 조사

- 상태: 완료된 자료 조사 slice; PIT application과 경제 성과 적용은 차단
- 기록 시각: 2026-09-19T23:38:09Z
- 작업 slug: `alfred-weekly-vintage-evidence-20260920`
- 범위: ALFRED 공개 graph CSV의 금요일 주간 vintage 54개를 bounded read-only로
  보존하고, 2025-09-11~2026-09-11 요청 범위의 관측일별 최초 sampled vintage를
  offline 대조했습니다. collector/readiness/metrics에는 연결하지 않았습니다.

## 변경과 결정

- `2025-09-12`부터 `2026-09-18`까지의 주간 vintage raw CSV 54개를 저장했습니다.
- 현재 FRED public CSV에서 값이 있는 251개 관측일 모두가 적어도 하나의 sampled
  vintage에서 재현되었습니다(coverage 251/251).
- `first-seen-sampled-vintages.json`의 날짜별 값은 실제 publication instant가 아닌
  주간 snapshot 사이의 상한(upper bound)입니다. 따라서 이를 PIT availability나
  carry-forward 정책으로 해석하지 않습니다.

## 검증

- 각 raw 파일의 bytes, 줄 수, SHA-256을 `request.json`에 고정했습니다.
- offline CSV parser로 baseline의 251개 nonblank 관측일을 추출한 뒤, 각 vintage의
  동적 ALFRED value column을 비교했습니다. 누락 관측일은 0개였습니다.
- 실행하지 않은 검사: publication timezone/instant 검증, business calendar 정책,
  NAV 적용, risk-free application/readiness/performance integration.

## 안전·운영 상태

- 공개 network read-only fetch만 수행했습니다. 주문·PAPER/live·원장·서비스·runner
  설정·remote push·Windows 종료는 없습니다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260920-alfred-weekly-vintages/`;
  `request.json`, `weekly-vintage-summary.json`, `first-seen-sampled-vintages.json`.
- 남은 차단 조건: 관측별 정확한 publication instant와 timezone, 거래일/holiday
  completeness, NAV interval 적용 계약 및 독립 review가 필요합니다.
- 다음 시작: 이 자료를 source evidence로만 유지하고, exact PIT receipt가 확보되기
  전에는 FX/NAV readiness나 Sharpe·Calmar 계산을 활성화하지 않습니다.
