# ALFRED vintage FX 근거 조사

- 상태: 완료된 자료 조사 slice; PIT application과 경제 성과 적용은 차단
- 기록 시각: 2026-09-19T23:31:28Z
- 작업 slug: `alfred-vintage-evidence-20260920`
- 기준/통합: `6056c7b` / 문서 커밋 예정
- 범위: ALFRED 공개 graph CSV에서 고정 vintage 4개를 읽기 전용으로 보존하고
  release-lag 관찰을 기록했습니다. collector/readiness/metrics에는 연결하지 않았습니다.

## 변경과 결정

- vintage dates `2025-09-12`, `2025-09-19`, `2026-01-02`, `2026-09-18`을 각각
  별도 raw CSV로 저장했습니다.
- `2025-09-12` vintage에는 `2025-09-11` 관측이 없고, `2025-09-19` vintage에는
  `2025-09-11=1388.97`, `2025-09-12=1394.06`이 나타나는 것을 확인했습니다.
- 이는 FRED public CSV의 현재 snapshot보다 강한 historical vintage 근거지만, 각 관측의
  정확한 intraday publication timestamp·business-date completeness·NAV interval
  적용 정책을 단독으로 증명하지 않습니다.

## 검증

- 각 vintage URL의 HTTP 200과 raw row count/SHA를 `request.json`에 고정했습니다.
- offline 대조: 2025-09-11/12 값의 vintage별 존재·부재를 raw bytes에서 확인했습니다.
- 실행하지 않은 검사: risk-free application/readiness/performance integration. 자료만으로
  carry-forward, publication instant, Sharpe 계산을 추정하지 않았습니다.

## 안전·운영 상태

- 공개 network read-only fetch 4회만 수행했습니다. 주문·PAPER/live·원장·서비스·runner
  설정·remote push·Windows 종료는 없습니다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260920-alfred-vintage-evidence/`;
  manifest-like metadata: `request.json`.
- 남은 작업·차단 조건: 전체 NAV 기간에 대한 per-date vintage/availability receipt,
  publication timezone/instant, calendar/application policy가 필요합니다.
- 다음 시작: 이 vintage 결과를 source evidence로만 유지하고, 필요하면 bounded
  application-evidence 계약을 별도 설계한 뒤 독립 review를 수행합니다.
