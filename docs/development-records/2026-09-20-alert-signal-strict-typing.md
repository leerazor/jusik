# Alert signal strict typing cleanup

- 상태: 완료
- 기록 시각: 2026-09-20T00:00:00Z
- 범위: alert store의 분석 signal과 저장 Alert signal 경계

## 변경

- `hold`·`insufficient` 분석 결과를 alert로 저장하지 않고, runtime 조건 통과 후
  `buy_review | sell_review`로 명시적으로 좁혀 저장하도록 했습니다.
- signal deduplication과 Telegram delivery 흐름은 변경하지 않았습니다.

## 검증

- alert store strict mypy — 통과
- Ruff, `git diff --check` — 통과
- alert store/telegram 테스트 — `2 passed`

## 제한

- alert는 검토 신호일 뿐 자동 주문이나 PAPER/live 승격 근거가 아닙니다.
