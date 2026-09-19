# SEC 목표 기간 filing 근거 재대조

- 기록 시각: 2026-09-20T00:40:00Z
- 범위: 기존 SEC submissions raw 8개를 재호출 없이 읽어
  `2025-09-11`~`2026-09-11`의 `8-K`/`8-K/A` filing과 접수 시각을 추출했습니다.

## 결과

- 매핑된 SEC submission raw: 8개
- 목표 기간 8-K/8-K/A: 89건
- 심볼별 건수: `AMD` 14, `COHR` 11, `GEV` 8, `GOOGL` 16, `MSFT` 9,
  `NVDA` 13, `VRT` 18
- 각 행에 filing date, `acceptanceDateTime`, accession, items, primary document와
  원본 raw SHA를 보존했습니다.

## 제한

- 8-K filing 존재는 적용 가능한 split/dividend/delisting의 확정 증거가 아닙니다.
- issuer-verified 권리·가격·effective/payment date를 추출하거나 수동 검토하지 않았습니다.
- 따라서 R1-02/R1-04/R1-05, action-review manifest, 원장·NAV·성과 계산과
  PAPER/live 승격에는 사용하지 않습니다.

## 증거·운영

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260920-sec-target-period-evidence/`
  (`target-period-8k-summary.json`, `request.json`)
- 기존 raw 재사용만 수행했고 신규 네트워크 호출·주문·PAPER/live·원격 push·Windows
  종료는 없습니다.
