# 2026-09-24 full-suite baseline

## 목적

현재 `main`의 백엔드 전체 테스트를 실행해 자동 개발 재개 전의 검증 상태를 확인했다. 이 기록은 고정 실험 산출물의 strict hash 계약과 최근 날짜 경계를 임의로 완화하지 않기 위한 것이다.

## 실행

- 명령: `backend/.venv/bin/python -m pytest -q`
- 결과: `1770 passed, 3 failed`
- 실패는 모두 기존 고정 fixture와 현재 시점/코드 identity의 불일치이며, 실거래·PAPER/live·브로커 API·DB 운영 데이터는 변경하지 않았다.

## 판정

1. `test_copy_is_exactly_the_guarded_variant`
   - `research_portfolio_engine.py`의 현재 SHA-256은 `2e48b0bcedb740210a6dd58f6b15e99e2b2e1c416aacf553569ec0ea98166653`이다.
   - held-band 실험의 고정 variant SHA는 `7d9ccd0d...`로 남아 있다.
   - 2026-09-18 이후 calendar-aware timing, 2026-09-20 strict typing 변경이 있었으므로 고정 실험을 자동으로 새 코드에 재사용하지 않는다.

2. `test_frozen_archive_replay`
   - immutable timestamp-forensics archive가 보존한 `research_market_calendar.py` SHA와 현재 코드 SHA가 다르다.
   - strict replay가 `imported_code_hash_mismatch`로 거부한 것은 archive 오염/미검증 재생을 막는 정상 fail-closed 동작이다.

3. `test_robustness_repository_and_validation_api_are_bounded`
   - fixture가 `2026-09-14`를 요청했으나 현재 날짜 `2026-09-24` 기준 최근 7일 경계를 벗어난다.
   - `validate_signal_store`의 날짜 제한을 완화하지 않고, 날짜를 현재 시점에 맞춘 fresh fixture가 필요하다.

## 후속 조건

- 고정 실험을 재실행하려면 새 pre-registration, source/evidence manifest, code hash와 독립 검토를 새로 생성한다.
- immutable archive는 현재 코드로 덮어쓰지 않는다.
- 날짜 경계 fixture는 production 안전 경계를 유지한 채 실행 시점에 맞춘다.
- 위 세 조건이 충족되기 전에는 전체 suite green 또는 경제 acceptance로 승격하지 않는다.

