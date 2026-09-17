# 시장 성과 지표

- 상태: 완료
- 기록 시각: 2026-09-17T00:00:00Z
- 작업 slug: `market-performance-metrics`
- 기준/통합: `487d84e` / 미통합
- 범위: 동결·비용 포함 NAV의 순수 Decimal 성과 평가기, SHA 고정 JSON 어댑터, 독립 oracle 테스트와 계약 문서를 추가했다. 공유 모델·전략·collector·runner·서비스·DB·설정·로드맵은 변경하지 않았다.

## 변경과 결정

- `backend/jusik/market_performance_metrics.py`에 명시적 `initial_capital_at` anchor 기반 total return, actual UTC calendar-day CAGR, initial-capital-inclusive MDD, daily excess-return sample Sharpe, Calmar와 MDD 20% hard filter를 추가했다.
- UTC 날짜 간 irregular holiday gap은 명시적 calendar/completeness evidence가 있을 때만 허용한다. missing session은 추정하지 않는다.
- NAV가 이미 비용을 포함하므로 비용을 다시 차감하지 않는다. strict/approximate/fixture 등급은 보존하며 승격하지 않는다.
- `backend/tests/test_market_performance_metrics.py`에 양·음수, 초기 손실, 정확한 20%, 윤년/간격, invalid NAV/date, evidence 누락, zero variance/MDD, 입력 불변, SHA와 alias guard를 추가했다.
- JSON Decimal 숫자 파싱, bounded nested JSON, metric별 Sharpe unavailable, anchor 경계와 원자적 output 교체 회귀를 추가했다.

## 문서·계약 영향

- 사용자 문서: `docs/market-performance-metrics.md`를 추가하고 `docs/market-research.md`에 연결했다.
- 운영 문서: 해당 없음. 수집·실행·주문 경로를 변경하지 않았다.
- API·설정·데이터 계약: 새 오프라인 `market-performance-metrics-input/v1`와 envelope/result schema를 문서화했다. 공유 schema는 변경하지 않았다.

## 검증

- `backend/.venv/bin/python -m pytest backend/tests/test_market_performance_metrics.py -q` — 12 passed
- `backend/.venv/bin/python -m ruff check backend/jusik/market_performance_metrics.py backend/tests/test_market_performance_metrics.py` — 통과
- `backend/.venv/bin/python -m ruff format --check backend/jusik/market_performance_metrics.py backend/tests/test_market_performance_metrics.py` — 통과
- `backend/.venv/bin/python -m mypy backend/jusik/market_performance_metrics.py backend/tests/test_market_performance_metrics.py` — 통과
- 기존 loss-accounting/counterfactual compatibility tests — 다음 통합 담당자가 main에서 실행할 검사로 남김

## 안전·운영 상태

- 오프라인 fixture만 사용했다. 시장 자료 수집, 연구 재실행, PAPER/live, 실제 주문, 운영 DB, 서비스, remote push는 수행하지 않았다.

## 증거와 재개

- audit: 없음; manifest: 없음; hash: 소스 envelope의 SHA 검증 테스트에 포함
- 남은 작업·차단 조건: main 통합 전 기존 loss-accounting/counterfactual 회귀 검증 필요
- 다음 시작: 부모 agent가 변경을 검토하고 main 통합 전 전체 focused 회귀를 실행한다.
