# Full regression failure audit

- 기록 시각: 2026-09-20T03:02:00Z
- 범위: 현재 main에서 기존 full-suite에 남아 있던 4개 실패를 개별 재현했습니다. 코드·fixture·historical
  artifact는 수정하지 않았습니다.

## 재현된 실패

1. `test_review_closed_takes_priority_and_watch_is_not_sell_signal`: 현재 시각이 fixture quote보다 오래되어
   `deferred`가 반환됩니다. production의 stale-quote fail-closed 동작과 충돌하는 stale expectation입니다.
2. `test_provider_analyzes_quote_after_yahoo_fetch`: 현재 시각과 fixture quote 간 지연으로 `stale`이 반환됩니다.
3. `test_copy_is_exactly_the_guarded_variant`: 현재 engine copy SHA `a049f76f...`가 historical expected
   `7d9ccd0d...`와 다릅니다. guarded variant provenance를 임의로 재핀하지 않았습니다.
4. `test_frozen_archive_replay`: frozen evidence archive가 현재 `research_market_calendar.py` SHA와 달라
   `imported_code_hash_mismatch`로 fail-closed 됩니다. historical archive를 현재 코드로 소급하지 않았습니다.

## 판정

- 위 실패는 이번 R2/R3/R6 검증과 독립적이며, stale 시간 정책·historical hash provenance 문제입니다.
- 테스트를 통과시키기 위해 production stale guard를 약화하거나 frozen archive/variant pin을 임의 변경하지
  않았습니다. 해당 영역의 별도 승인·새 provenance가 없으면 현재 상태를 보존합니다.

## 후속 전체 회귀 재확인

- `2026-09-20T13:33:00+09:00`에 `backend/.venv/bin/python -m pytest backend/tests -q`를
  다시 실행했습니다.
- 결과: `1695 passed, 4 failed, 2 warnings`; 실패 식별자와 원인은 위 네 항목과 동일했습니다.
  Korea Exim 변경으로 새 실패가 추가되지 않았음을 확인했습니다.
- 따라서 stale 정책, guarded-variant SHA, frozen archive provenance를 이번 작업에서 변경하지
  않고 현재 fail-closed 상태를 유지합니다.
