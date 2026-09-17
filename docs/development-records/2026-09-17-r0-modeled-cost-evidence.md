# R0 미국 모형 비용 포함 대사

- 상태: 완료
- 기록 시각: 2026-09-17T00:00:00Z
- 작업 slug: `r0-us-modeled-cost-evidence`
- 기준/구현/통합: `a2f1972` / `ed3a494` / `40336c4`
- 범위: 고정 R0 미국 산출물의 모형 fee/slippage/sell-tax 포함 여부를 독립 대사하고 canonical readiness에 한 누락 code만 연결했습니다.

## 변경과 결정

- `backend/jusik/market_performance_cost_evidence.py`는 표준 라이브러리 JSON/Decimal 검증기로 baseline manifest, run/dataset/cache/completion, raw 84개 SHA·크기·안전 경로를 검증합니다.
- 첫 FX와 spread로 초기 KRW를 환전하고, 저장 순서(매도 후 매수)의 106개 체결을 dataset open 및 request 요율로 재계산했습니다. 252개 세션의 native/KRW cash, invested, close mark, NAV 잔차는 0이며 최종 보유는 0입니다.
- `backend/jusik/data/r0_us_cost_inclusion_evidence_v1.json`은 verifier source/artifact SHA, Decimal 문맥, 세션별 digest와 제한사항을 고정합니다. readiness는 검증된 canonical chain에서만 `missing_cost_inclusion_evidence`를 제거합니다.

## 문서·계약 영향

- 사용자 문서: `docs/market-performance-metrics.md`에 비용 대사 범위와 실행 계약을 추가했습니다.
- 운영 문서: 해당 없음. 연구·네트워크·서비스·DB·설정은 변경하지 않았습니다.
- API·설정·데이터 계약: readiness report에 `cost_evidence` facts가 추가될 수 있으나 상태는 blocked이며 approximate/not-evaluated를 유지합니다.

## 검증

- main cost/readiness/policy/metrics pytest — 92 passed.
- `ruff check`, `ruff format --check`, configured source mypy, `git diff --check a2f1972..40336c4` — 통과.
- canonical cost CLI와 readiness acceptance — 106 trades, 252 sessions, max residual 0, final holdings 0; missing은 초기자본 anchor·NAV timestamp·무위험률 3개로 유지.
- Terra 최종 독립 review — PASS, P1/P2 없음.

## 안전·운영 상태

- 원본 산출물은 읽기만 했습니다. 네트워크, 연구 재실행, PAPER/live, 실제 주문, 운영 DB·서비스·원격 push는 수행하지 않았습니다.
- 법정 요율, 실제 전체 비용, 기업행사/배당/분할 완전성, 체결시각·원본 생성 트리의 진실을 주장하지 않습니다.

## 증거와 재개

- tracked evidence: `backend/jusik/data/r0_us_cost_inclusion_evidence_v1.json`; canonical report의 artifact/accounting digest는 검증기에서 재계산됩니다.
- 남은 작업·차단 조건: 세션 대사 외 초기자본 anchor, NAV timestamp, 무위험률 근거가 없어 전체 성과 평가는 차단됩니다.
- 다음 시작: 초기자본 UTC anchor와 NAV UTC timestamp를 기존 실행 의미에서 고정할 수 있는지 조사하고, 날짜를 임의 시각으로 승격하지 않습니다.
