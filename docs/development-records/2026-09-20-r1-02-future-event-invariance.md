# R1-02 future market-event invariance fixture

- 상태: 기술 slice 완료; R1-02 전체(기업행사·상장폐지·중단일) 미완료
- 기록 시각: 2026-09-20T00:00:00Z
- 작업: `r1-02-future-event-invariance-20260920`
- 범위: 연구 기간 이후에 발생하고 알려진 시장 이벤트를 입력해도 기간 내 과거
  거래·equity·event decision이 변하지 않는 시간순 불변성 회귀 fixture 추가

## 변경

- `test_future_market_event_does_not_change_earlier_trades_or_equity`를 추가했습니다.
- 이벤트의 `occurred_at`·`known_at`을 요청 종료일 다음 날로 설정하고, 이벤트가 없는
  기준 실행과 거래·전체 equity·affected decision을 비교합니다.
- `_validate_execution_window()`도 `known_at <= fill_at`을 요구하도록 보강해, 시가
  이후에 알려진 과거 사건이 시가 체결을 소급 차단하지 않게 했습니다.
- `test_event_known_after_morning_fill_does_not_block_that_fill`로 발생 시각은 이전이어도
  알려진 시각이 이후인 사건의 비소급 동작을 검증합니다.
- 기존 엔진의 체결 시각 기준 event filtering 계약을 고정하며, 실제 SEC 사실이나
  action ledger를 합성하지 않습니다.

## 검증

- `backend/.venv/bin/python -m pytest backend/tests/test_research_engine.py -q` — 14 passed
- `backend/.venv/bin/ruff check backend/tests/test_research_engine.py` — 통과
- `backend/.venv/bin/ruff check backend/jusik/research_engine.py backend/tests/test_research_engine.py` — 통과
- strict mypy는 기존 `research_config.py`·`research_data.py`의 5개 타입 오류로 실패했으며,
  이번 변경 파일의 신규 오류는 확인되지 않았습니다.
- 인접 회귀 묶음 `test_market_loss_accounting.py test_research_engine.py
  test_market_history_approximate.py` — 78 passed, 2 warnings
- `git diff --check` — 통과

## 제한·다음 조건

- 이 fixture는 R1-02의 미래 이벤트 누출 방지만 검증합니다. 기업행사·상장폐지·중단일의
  실제 관측시점, PIT coverage, dividend/split 적용은 별도 증거가 필요합니다.
- SEC operator facts가 준비되기 전에는 action ledger와 경제 성과를 승격하지 않습니다.
