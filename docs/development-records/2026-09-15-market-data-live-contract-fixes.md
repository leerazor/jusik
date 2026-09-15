# Live market data contract fixes

- 상태: 완료
- 기록 시각: 2026-09-15T00:42:26Z
- 작업 slug: `market-data-live-contract-fixes`
- 기준/통합: `e608835` / 없음
- 범위: 공식 시장자료 요청·정규화·설정·캐시 상태 계약과 관련 회귀 검증을 보완했습니다. 주문·전략·프런트엔드는 변경하지 않았습니다.

## 변경과 결정

- KRX 일별 자료를 공식 `data-dbg.krx.co.kr` board별 GET endpoint와 `basDd` query, `AUTH_KEY` header로 요청하고 응답 envelope·일자·board를 검증합니다.
- Alpha Vantage CSV 전체 header를 검증하고 상품·거래소·이름·날짜·중복 오류를 행 단위로 제외하며 checkpoint별 입력·허용·제외 사유를 limitation에 기록합니다.
- 명시적 dotenv 파일과 표준/alias 환경변수 precedence를 지원하고 보간·프로세스 환경 변이는 사용하지 않습니다.
- collector cache와 completion contract를 v2로 올려 이전 marker를 재사용하지 않으며, `collect-status`가 손상된 cache를 원시 내용 없이 `ready:false`와 종료 코드 2로 보고합니다.

## 문서·계약 영향

- 사용자 문서: `docs/market-research.md`, `.env.example`, `.env.dev.example`에 provider endpoint·env-file·행 단위 exclusion 계약을 반영했습니다.
- 운영 문서: 외부 provider smoke는 실행하지 않았습니다.
- API·설정·데이터 계약: 손상 캐시는 유효한 완료 수집으로 재사용하지 않으며 normalization·cache·completion 계약 버전을 갱신했습니다.

## 검증

- `backend/.venv-verify/bin/python -m pytest backend/tests/test_market_data_collector.py backend/tests/test_market_history_approximate.py backend/tests/test_market_research.py backend/tests/test_development_runner_planning.py -q` — 통과
- `backend/.venv-verify/bin/ruff format --check ...` 및 `ruff check ...` — 통과
- `backend/.venv-verify/bin/python -m mypy --strict` (관련 8개 source) — 통과
- `git diff --check` — 통과

## 안전·운영 상태

- 실제 provider 호출, 운영 DB 변경, 서비스 배포, 원격 push, 실제 주문은 수행하지 않았습니다.

## 증거와 재개

- audit: 없음; manifest: 없음; hash: 없음
- 남은 작업·차단 조건: 실제 provider 자격증명이 준비된 뒤 별도 제한 smoke가 필요합니다.
- 다음 시작: main 통합 전 동일 focused suite와 독립 review 결과를 대조합니다.
