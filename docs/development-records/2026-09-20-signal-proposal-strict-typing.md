# Signal proposal and strategy version strict typing cleanup

- 상태: 완료
- 기록 시각: 2026-09-20T00:00:00Z
- 범위: research automation proposal side와 operations strategy-version source 경계

## 변경

- 자동화 제안의 side를 `Literal["buy", "sell"]`로 고정했습니다.
- 저장된 strategy version source를 `built_in | openai_suggestion`으로 runtime 검증 후
  모델에 전달합니다. 알 수 없는 source는 fail-closed 예외가 됩니다.
- 제안 생성은 기존 PAPER 검토 흐름만 사용하며 실제 주문이나 자동 live 승격은 추가하지
  않았습니다.

## 검증

- automation/operations 두 모듈 strict mypy — 통과
- Ruff, `git diff --check` — 통과
- automation/operations 테스트 — `13 passed`

## 제한

- 이 변경은 신호·전략 성과나 PAPER 승인 근거를 만들지 않습니다. 기존 operator 승인과
  경제 게이트를 유지합니다.
