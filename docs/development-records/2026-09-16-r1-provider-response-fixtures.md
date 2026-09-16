# 공급자 응답 분류와 실패 cache 회귀

- 상태: 완료
- 기록 시각: 2026-09-16T04:07:34Z
- 작업 slug: `r1-provider-response-fixtures`
- 기준/통합: `b805841` / 없음
- 범위: collector의 공급자 응답 분류·검증 경계와 오프라인 회귀 fixture를 추가했습니다. 기존 인증·예산·재시도, membership·product·event·accounting 집계 정책과 KRX 빈 거래일 처리를 보존했습니다.

## 변경과 결정

- `CollectorParseError`, `CollectorQuotaError`, `CollectorNullError`, `CollectorCoverageError`를 기존 `CollectorError` 계층 아래에 추가하고 인증·예산 예외 호환성을 유지했습니다.
- 알려진 공급자 오류 envelope는 고정 메시지로 분류하며 parser 경계에서 원문 예외 원인을 제거합니다.
- `HttpFetcher.get`의 validator가 fresh 응답 저장 전과 resume 반환 전에 같은 요청별 parser를 실행합니다. 실패 응답은 manifest와 raw cache에 저장하지 않습니다.
- KRX의 명시적 `OutBlock_1: []`는 NetworkTransport에서 정상 no-trade 자료로 허용합니다. 15개 합성 fixture는 한 종목·한 세션·seed 0으로 고정했습니다.

## 문서·계약 영향

- 사용자 문서: `docs/market-research.md` — 응답 분류, 검증 시점, no-trade 계약을 명시했습니다.
- 운영 문서: 해당 없음 — 수집·서비스·설정·원격 운영은 변경하지 않았습니다.
- API·설정·데이터 계약: collector 예외와 cache 검증 경계만 확장했으며 기존 성공 payload 구조는 유지했습니다.

## 검증

- `backend/.venv/bin/python -m pytest backend/tests/test_market_data_collector.py backend/tests/test_market_history_approximate.py -q` — 140 passed; 2 dependency deprecation warnings.
- `backend/.venv/bin/python -m ruff check backend/jusik/market_data_collector.py backend/tests/test_market_data_collector.py` — 통과.
- `backend/.venv/bin/python -m mypy backend/jusik/market_data_collector.py` — 통과.
- `backend/.venv/bin/python -m ruff format --check ...` — 기존 debt와 동일한 collector 3개·test 8개 hunk로 실패; 신규 hunk는 없습니다.
- 실행하지 않은 검사: 전체 저장소 검사와 실제 provider 수집은 범위 밖입니다.

## 안전·운영 상태

- HTTP와 sleep은 fixture/mock만 사용했습니다. 실제 provider 요청, 주문, PAPER/live, DB, service, 설정, remote push는 수행하지 않았습니다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260916-r1-06-518dc0fb`; manifest: `fixture-manifest.json`.
- 남은 작업·차단 조건: 독립 review와 local main 통합은 감독이 수행합니다.
- 다음 시작: 독립 review 결과를 반영한 뒤 동일 fixture와 focused gate를 다시 실행합니다.
