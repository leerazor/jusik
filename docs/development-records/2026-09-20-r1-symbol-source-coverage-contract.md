# R1 symbol source coverage contract

- 상태: 기술 계약 완료·coverage incomplete 유지
- 기록 시각: 2026-09-20T03:30:00Z
- 작업 slug: `r1-symbol-source-coverage-contract-20260920`
- 범위: 기존 `PublicEvidenceCatalog`에서 요청 universe 각 종목의 Alpha Vantage,
  Nasdaq Trader, SEC EDGAR 관측 건수와 누락 source를 결정적으로 산출합니다.

## 변경과 결정

- `build_public_evidence_symbol_coverage()`는 catalog item만 집계하며, 요청 universe 밖
  item은 `catalog_item_symbol_not_requested`로 fail-closed 거부합니다.
- source가 비어 있거나 unresolved symbol이어도 삭제·성공 승격하지 않고 모든 source를
  누락으로 기록합니다.
- 결과의 `coverage`는 항상 `incomplete`, `economic_acceptance`와 `pit_proof`는 항상
  `false`입니다. catalog SHA를 결과 identity로 보존합니다.
- 기존 catalog builder·source collector·readiness·runner·원장·성과 계산은 변경하지
  않았습니다.

## 검증

- `pytest backend/tests/test_research_public_evidence_catalog.py -q` — 9 passed
- Ruff 변경 파일 — 통과
- `git diff --check` — 통과
- strict mypy는 기존 public-evidence 의존 모듈과 catalog builder의 범위 밖 오류가 있어
  non-zero이며, 새 coverage 모델의 추가 오류는 별도로 확인되지 않았습니다.

## 제한

- 이 계약은 source availability 요약일 뿐 provider 전체 coverage, PIT completeness,
  기업행사 권리·가격 증거가 아닙니다.
- R1-05 checkbox와 경제 acceptance, 전략 후보·PAPER/live 승격은 변경하지 않습니다.
