# 미국 사건 시각 불변성 계약

- 상태: 완료
- 기록 시각: 2026-09-17T00:00:00Z
- 작업 slug: `r1-us-event-time-invariance`
- 기준/통합: `24e66987cba144fa026a7dccc825bd3a2ae6bd35` / 통합 전
- 범위: production pipeline은 변경하지 않고, 기존 `_USEventTransport`를 확장한 synthetic
  collector/source/strategy 계약 테스트와 시장 연구 문서만 갱신했습니다.

## 변경과 결정

- `splits`, `dividends`, 명시적 `delisting`에 대해 관측 선행·효력 선행 두 시각 순서를
  같은 두 ordinary symbol fixture로 검증합니다.
- 사건 전 동일 요청·고정 `captured_at`에서 universe/bars, typed membership, candidate
  evidence, 상태·완전성·등급·누락 범위, collection diagnostics가 정확히 같음을 검증합니다.
- 전체 요청은 독립적으로 고정한 사건 적용 거래일 이전 prefix만 비교하고, 이후에는 대상
  symbol 행만 제외되며 prepared JSON round-trip에 사건 timing/source가 보존됨을 검증합니다.
- 실제 historical observation이나 strict PIT를 주장하지 않으며 `actions=()`와
  `actions_complete=false` 정책을 유지합니다.

## 문서·계약 영향

- 사용자 문서: `docs/market-research.md`에 R1-02 사건 시각 불변성 계약을 추가했습니다.
- 운영 문서: 해당 없음. 서비스·runner·DB는 변경하지 않았습니다.
- API·설정·데이터 계약: production schema/API는 변경하지 않았습니다.

## 검증

- `uv run --offline --project . python -m pytest tests/test_market_data_collector.py tests/test_market_history_approximate.py` — 통과, 167개.
- `uv run --offline ruff check tests/test_market_data_collector.py tests/test_market_history_approximate.py` — 통과.
- `uv run --offline ruff format --check tests/test_market_data_collector.py tests/test_market_history_approximate.py` — 실패. 기존 변경 범위 밖 코드에 이미 존재한 formatting 차이가 남아 있어 파일 전체 자동 포맷은 수행하지 않았습니다.
- `uv run --offline mypy jusik/market_data_collector.py jusik/market_history_approximate.py` — 통과.
- `uv run --offline mypy jusik` — 실패. 기존 `research_optimizer.py`의 선택적 `torch` stub 부재이며 이번 변경과 무관합니다.
- `python -m compileall -q backend/tests/test_market_data_collector.py backend/tests/test_market_history_approximate.py` 및 `git diff --check` — 통과.

## 안전·운영 상태

- fake transport와 prepared JSON만 사용했습니다. 네트워크 수집, 서비스, 운영 DB, PAPER/live,
  실제 주문과 원격 push는 수행하지 않았습니다.
- 비밀값·계정 식별자·인증서·토큰은 생성하거나 기록하지 않았습니다.

## 증거와 재개

- audit: 없음; manifest: 없음; hash: 없음
- 남은 작업·차단 조건: 부모 agent의 diff 검토와 local `main` 통합 검증
- 다음 시작: 부모 agent가 이 브랜치의 commit과 지정 두 테스트 파일 diff를 검토합니다.
