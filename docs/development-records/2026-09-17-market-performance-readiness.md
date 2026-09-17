# 시장 성과 입력 준비 진단

- 상태: 완료
- 기록 시각: 2026-09-17T00:00:00Z
- 작업 slug: `market-performance-readiness`
- 기준/구현/통합: `c549654` / `b170f36` / `6b9355e`
- 범위: SHA 고정 canonical `MarketResearchRun`을 읽기 전용으로 점검하고, 성과
  계산에 필요한 근거 누락을 결정적 JSON으로 보고한다. 공유 모델·전략·collector·runner·API·
  설정·원본 artifact는 변경하지 않았다.

## 변경과 결정

- `backend/jusik/market_performance_readiness.py`에 10MiB bounded JSON loader,
  SHA·중복 key·비유한 수·구조·request/result·세션/NAV 검증과 stdout CLI를 추가했다.
- raw model defaults가 누락을 가리지 않도록 canonical nested schema, readiness capability
  consistency, provenance/source enum, hash·account·trade/equity fact를 검증한다.
- raw-presence gate 뒤 기존 `MarketResearchRun.model_validate`를 호출해 pilot reference,
  정확한 1년 기간, 고정 mandate cost, run ID 길이 제약을 동일하게 적용한다.
- caller SHA generic inspection과 등록 digest를 요구하는 `--canonical` acceptance를 분리했다.
  generic 보고서는 `canonical=false`이며 임의 SHA만으로 canonical provenance를 만들지 않는다.
- 완료된 미국 approximate pilot/result만 지원한다. 유효한 입력도 항상 blocked와
  `economic_evaluation=not-evaluated`를 유지하며 고정된 7개 missing code를 순서대로 반환한다.
- 입력의 approximate/simulated/source facts와 request의 fee/slippage/sell-tax pointer를
  Decimal 문자열로 보존하고 evaluator나 연구 실행 경로를 호출하지 않는다.
- `backend/tests/test_market_performance_readiness.py`에 합성 canonical 입력, 누락 순서,
  보존 facts, SHA/schema/raw omission/duplicate/nonfinite/size/NAV/session/결정성 검사를 추가했다.

## 문서·계약 영향

- 사용자 문서: `docs/market-performance-metrics.md`에 readiness 진단 계약과 CLI를 추가했다.
- 운영 문서: 해당 없음. 서비스·작업 실행·주문 경로를 변경하지 않았다.
- API·설정·데이터 계약: 새 stdout-only `market-performance-readiness/v1` 보고서와
  `market-performance-metrics-input/v1` target을 문서화했다. 기존 공유 schema는 변경하지 않았다.

## 검증

- `backend/.venv/bin/python -m pytest backend/tests/test_market_performance_readiness.py -q` — 24 passed
- `backend/.venv/bin/python -m ruff check backend/jusik/market_performance_readiness.py backend/tests/test_market_performance_readiness.py` — 통과
- `backend/.venv/bin/python -m ruff format --check backend/jusik/market_performance_readiness.py backend/tests/test_market_performance_readiness.py` — 통과
- `backend/.venv/bin/python -m mypy --config-file backend/pyproject.toml backend/jusik/market_performance_readiness.py` — 통과
- main focused·호환 pytest — 96 passed
- `git diff --check c549654..6b9355e` — 통과
- 고정 SHA canonical CLI acceptance — exit 0, blocked, 관측 252개, 고정 missing code 7개
- Terra 최종 독립 review — PASS, P1/P2 없음

## 안전·운영 상태

- 저장 파일과 합성 임시 입력만 읽었다. 시장 수집·연구 재실행·PAPER/live·실제 주문·운영 DB·
  서비스·remote push는 수행하지 않았다.

## 증거와 재개

- audit: 없음; manifest: 없음; hash: 합성 CLI와 local canonical acceptance에서 입력 SHA를 확인했다.
- 남은 작업·차단 조건: 외부 근거가 추가되기 전까지 성과 계산 준비 상태는 blocked다.
  UTC anchor·NAV timestamp·세션 완전성·달력·비용 포함·무위험률·계산정책 근거가 필요하다.
- 다음 시작: canonical readiness의 누락 목록과 로드맵 차단 항목을 대조해, 실제 근거 없이
  진행 가능한 다음 최소 작업이 있는지 다시 조사한다.
