# Portfolio candidate strict typing cleanup

- 상태: 완료
- 기록 시각: 2026-09-20T00:00:00Z
- 범위: R5 후보 생성기의 method/gate 문자열을 사전등록 literal 계약에 결속

## 변경

- 후보 method와 gate 목록을 `PortfolioMethod`·`PortfolioGate` typed tuple로 선언해
  `PortfolioCandidate`가 임의 문자열을 받지 않도록 했습니다.
- 후보 수·ID·순서는 변경하지 않았고 자동 winner·가중 합산·승격도 추가하지 않았습니다.

## 검증

- portfolio engine strict mypy — 통과
- Ruff, `git diff --check` — 통과
- portfolio/optimizer/external 관련 테스트 — `59 passed, 2 warnings`

## 제한

- 후보의 경제 성과나 OOS/PAPER 적합성을 평가하지 않았습니다. R5 preregistration과
  자료·비용 게이트는 기존 fail-closed 상태를 유지합니다.
