# Forward intent strict typing cleanup

- 상태: 완료
- 기록 시각: 2026-09-20T00:00:00Z
- 범위: R5 forward observation intent의 side 방향을 모델 literal 계약에 결속

## 변경

- target/current weight 비교 결과를 `Literal["buy", "sell"]`로 명시해
  `ForwardIntent`가 임의 문자열을 받지 않도록 했습니다.
- forward worker는 PAPER 관찰·가상 full-fill 모델만 사용하며 실제 주문 경로는 변경하지
  않았습니다.

## 검증

- `research_forward.py` strict mypy — 통과
- Ruff, `git diff --check` — 통과
- forward/readiness 테스트 — `27 passed, 2 warnings`

## 제한

- forward/PAPER 결과를 경제적 승인이나 live 승격으로 해석하지 않습니다. 기존 독립 승인과
  readiness gates를 유지합니다.
