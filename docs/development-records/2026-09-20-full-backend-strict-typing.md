# Full backend strict typing cleanup

- 상태: 완료
- 기록 시각: 2026-09-20T00:00:00Z
- 범위: fixture app의 화면용 Decimal·currency·signal 입력 계약

## 변경

- fixture holding의 currency/signal을 typed literal로 제한했습니다.
- AssetSummary, ExchangeRate, MarketIntelligence의 숫자 fixture 값을 문자열이 아닌
  `Decimal`로 생성하도록 정리했습니다.
- fixture는 화면·API 검증용이며 broker·주문·PAPER/live 상태를 변경하지 않습니다.

## 검증

- 전체 `backend/jusik` strict mypy — 통과 (기존 6개 오류 포함 모두 해소)
- Ruff, `git diff --check` — 통과
- fixture/market-research/news 관련 테스트 — `38 passed, 2 warnings`

## 제한

- fixture 결과는 strict/PIT/economic evidence가 아니며 성과 승격에 사용하지 않습니다.
