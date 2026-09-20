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

- `pytest backend/tests/test_research_public_evidence_catalog.py -q` — 10 passed
- Ruff 변경 파일 — 통과
- `git diff --check` — 통과
- strict mypy는 기존 public-evidence 의존 모듈과 catalog builder의 범위 밖 오류가 있어
  non-zero이며, 새 coverage 모델의 추가 오류는 별도로 확인되지 않았습니다.

실제 재구축 catalog(`/home/kwl/.local/share/jusik/portfolio-audit/20260920-public-evidence-catalog-rebuilt-20260920/catalog.json`, semantic SHA
`0ffb17730ad4fe98e808ff6f3973359f67aa6f2665b28dc53ca51fc7b638e03b`)를 새 계약으로 읽어
10개 종목 보고서를 생성했습니다. artifact SHA는
`d76d1980a63dca9074c3576651a5639143dee523a368a2eb13b53daeca05329a`이며, 기존 sparse
표현의 audit report와 관측 건수·누락 source를 대조했습니다. 새 계약은 0건 source도 명시해
누락을 더 직접적으로 보존하며, 요청 기간과 `unresolved_symbols`도 함께 결속합니다.
`write_symbol_coverage()`로 동일 계약 JSON을 재현할 수 있으며 writer 보강은 main
`875b071`에 기록했습니다.

추가로 cached raw receipt만 읽어 source receipt audit을 생성했습니다. 20개 Alpha 요청,
8개 SEC submissions, SEC ticker map 1개, Nasdaq halt response 1개가 모두 parser 성공했고,
SEC target symbol `SOXL`·`TQQQ`는 receipt 자체가 없습니다. audit report SHA는
`33605dd0377840c8460a5a9f915f05b2159a6c819c43e053c5cbdf2265fe41ad`입니다. 이는 raw
응답 존재·파싱 결과만 증명하며 provider 전체 coverage·PIT publication은 증명하지 않습니다.

## 제한

- 이 계약은 source availability 요약일 뿐 provider 전체 coverage, PIT completeness,
  기업행사 권리·가격 증거가 아닙니다.
- R1-05 checkbox와 경제 acceptance, 전략 후보·PAPER/live 승격은 변경하지 않습니다.
