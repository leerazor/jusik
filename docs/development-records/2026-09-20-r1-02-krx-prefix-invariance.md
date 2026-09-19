# KRX prefix invariance fixture

- 상태: 완료
- 기록 시각: 2026-09-20T00:00:00Z
- 작업 slug: `r1-02-krx-prefix-invariance-20260920`
- 기준/통합: `6869cc8` / integration pending
- 범위: KRX collector 테스트 fixture와 이 개발 기록만 변경했습니다. production
  collector, 자료, 원장, 서비스, PAPER/live 설정, 원격 상태는 변경하지 않았습니다.

## 변경과 결정

- `_CorporateActionTransport`에 선택적 비대상 KOSPI 종목을 추가했습니다.
- baseline과 미래 `halt`/`delisting` 응답을 같은 기간에 수집해 사건 전
  `universe`·`bars` prefix가 exact equality이고 비대상 종목 전체 행이 동일함을
  검증합니다.
- 대상 종목은 baseline에서 사건 이후 행이 존재하지만 event output에서는 첫 영향일
  이후 제외되며, halt/delisting limitation이 각각 보존되는지 검증합니다.

## 문서·계약 영향

- 사용자 문서: 해당 없음. 테스트 fixture 범위입니다.
- 운영 문서: 해당 없음. 운영 경로를 변경하지 않았습니다.
- API·설정·데이터 계약: 해당 없음. production collector 계약은 변경하지 않았습니다.

## 검증

- `python -m pytest -q tests/test_market_data_collector.py -k 'krx_future_event_preserves_prefix_and_unaffected_symbol or krx_event_forward_exclusion_is_truthful'` — 5 passed
- `python -m pytest -q tests/test_market_data_collector.py` — 131 passed
- `ruff check tests/test_market_data_collector.py` — 통과
- `ruff format --check tests/test_market_data_collector.py` — 기존 파일의 선행 포맷 차이로 실패; 이번 변경 구간은 formatter diff 없음
- `git diff --check` — 통과

## 안전·운영 상태

- fixture-only 검증이며 네트워크 수집, 실제 주문, PAPER/live, 서비스, DB, 원격
  push를 수행하지 않았습니다.

## 증거와 재개

- audit: 없음; manifest: 없음; hash: 없음
- 남은 작업·차단 조건: R1-02 historical provider receipt/PIT coverage와 경제
  acceptance는 이 기술 fixture로 승격하지 않습니다.
- 다음 시작: 통합 agent가 이 커밋을 검토한 뒤 local `main`에 통합합니다.
