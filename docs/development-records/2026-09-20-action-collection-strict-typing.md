# Action collection strict typing cleanup

- 상태: 완료
- 기록 시각: 2026-09-20T00:00:00Z
- 범위: R1-04 action collection parser의 provider kind 매핑을 모델 literal 계약에 결속

## 변경

- `splits -> split`, `dividends -> dividend` 매핑을 `ActionKind` typed tuple로 선언해
  수집 모델에 임의 문자열이 전달되지 않도록 했습니다.
- action 사실 검증, operator review, ledger 적용 정책은 변경하지 않았습니다.

## 검증

- action collection strict mypy — 통과
- Ruff, `git diff --check` — 통과
- action collection/review 테스트 — `23 passed, 2 warnings`

## 제한

- 실제 SEC facts·effective date·권리/가격·PIT 근거는 확보하지 않았으며 자동 ledger
  적용은 계속 금지합니다.
