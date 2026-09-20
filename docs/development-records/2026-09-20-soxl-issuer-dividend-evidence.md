# SOXL issuer dividend evidence follow-up

- 상태: issuer evidence candidate 미확보·R1-04 승격 보류
- 기록 시각: 2026-09-20
- 작업 slug: `soxl-issuer-dividend-evidence-20260920`
- 범위: Direxion 공식 distribution 페이지와 Alpha Vantage SOXL 배당 관측의
  교차 확인을 시도했습니다. 원문 raw를 로컬에 보존하지 못한 경우에는 경제
  원장·성과·readiness에 연결하지 않는 fail-closed 정책을 적용했습니다.

## 확인 결과

- 공식 검색 색인에는 SOXL의 2025-09-23 record/ex date, 2025-09-30 pay date,
  income dividend `0.01008`이 표시됩니다.
- 후보 source: [Direxion SOXL/SOXS product page](https://www.direxion.com/product/daily-semiconductor-bull-bear-3x-etfs?keyword=SOXL)
  및 [2025 ETF Distributions release](https://www.direxion.com/press-release/2025-etf-distributions)
- 이 환경에서 두 공식 URL에 bounded GET을 수행했으나 Cloudflare `403`과
  challenge HTML만 반환되어 issuer raw/SHA를 확보하지 못했습니다.
- 따라서 검색 색인 결과는 재현 가능한 원문 evidence로 승격하지 않았고,
  Alpha 원문과의 exact-match 후보로만 남겼습니다.

## 판정

- `operator_verified=false`, `automatic_ledger_application=false`를 유지합니다.
- R1-04/R1-05 checkbox, action review manifest, ledger, 성과, readiness는 변경하지
  않았습니다.
- 후속 조건: Direxion 원문 또는 SEC/공식 배포 문서의 credential-free raw 확보 후
  SHA를 고정하고 Alpha의 날짜·금액을 재생해야 합니다.

## 검증과 안전

- 공식 URL 2개에 대해 User-Agent를 포함한 bounded GET을 실행했습니다.
- 실제 주문, PAPER/live, runner 재개, 원격 push, Windows 종료는 없습니다.
