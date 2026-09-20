# Mandate SHA pin synchronization

- 상태: 완료
- 기록 시각: 2026-09-20T04:10:00Z
- 범위: `research_portfolio_symbol_cap_episodes.py`의 current mandate pin
- 통합 commit: `18da72e`

## 변경과 결정

- tracked `docs/research-mandate.json`의 현재 SHA-256
  `22efba4714bc0baf65c56bdfd84dcdee91184a760a13d4d30c5a94486c264ab1`와 symbol-cap
  episode replay 코드의 stale 상수(`ceca2…`)가 불일치하던 문제를 수정했습니다.
- historical report/manifest/results SHA와 계산 로직은 변경하지 않았습니다. replay는 현재
  승인된 mandate bytes를 읽고, 과거 결과를 새 경제 결과로 재해석하지 않습니다.

## 검증

- fixed symbol-cap archive test — 통과
- mandate governance tests — 16 passed
- Ruff 및 `git diff --check` — 통과
- `validate_mandate(Path('.'))` — current digest `22efba…` 확인

## 제한

- 이 수정은 거버넌스 identity 정합성만 복구합니다. 전략 성과·PAPER/live·실주문·원격 push를
  수행하지 않습니다.
