# Live market data contract fixes

- 상태: 완료
- 기록 시각: 2026-09-15T00:42:26Z
- 작업 slug: `market-data-live-contract-fixes`
- 기준/통합: `e608835` / 없음
- 범위: 공식 시장자료 요청·정규화·설정·캐시 상태 계약과 관련 회귀 검증을 보완했습니다. 주문·전략·프런트엔드는 변경하지 않았습니다.

## 변경과 결정

- collector CLI의 `collect-status`가 손상된 캐시 manifest 또는 완료 marker를 원시 내용 없이 `ready:false`와 종료 코드 2로 보고하도록 보완했습니다.
- 캐시 검증 오류를 정상적인 준비 안 됨 상태로 처리해 traceback과 비밀정보 노출을 막았습니다.

## 문서·계약 영향

- 사용자 문서: 이번 보완은 기존 CLI 오류 계약을 fail-closed로 구체화한 내부 동작 변경입니다.
- 운영 문서: 외부 provider smoke는 실행하지 않았습니다.
- API·설정·데이터 계약: 손상 캐시는 유효한 완료 수집으로 재사용하지 않습니다.

## 검증

- `backend/.venv-verify/bin/python -m pytest backend/tests/test_market_data_collector.py backend/tests/test_market_history_approximate.py backend/tests/test_market_research.py backend/tests/test_development_runner_planning.py -q` — 85 passed
- `backend/.venv-verify/bin/ruff format --check ...` 및 `ruff check ...` — 통과
- `backend/.venv-verify/bin/python -m mypy --strict` (관련 8개 source) — 통과
- `git diff --check` — 통과

## 안전·운영 상태

- 실제 provider 호출, 운영 DB 변경, 서비스 배포, 원격 push, 실제 주문은 수행하지 않았습니다.

## 증거와 재개

- audit: 없음; manifest: 없음; hash: 없음
- 남은 작업·차단 조건: 실제 provider 자격증명이 준비된 뒤 별도 제한 smoke가 필요합니다.
- 다음 시작: main 통합 전 동일 focused suite와 독립 review 결과를 대조합니다.
