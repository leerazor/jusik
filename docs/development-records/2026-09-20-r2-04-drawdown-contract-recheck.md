# R2-04 drawdown contract recheck

- 상태: 기술 계약 재검증 완료; 경제 acceptance·R2 전체 승격은 보류
- 기록 시각: 2026-09-20T05:15:00Z

## 판정

- `evaluate_performance()`는 initial capital을 running peak의 첫 기준점으로 포함하고,
  모든 chronological NAV row를 사용해 maximum drawdown을 계산합니다.
- `MDD <= 0.20` 경계는 hard filter로 적용되며 정확히 20%는 통과, 초과는 실패하는
  fixture가 있습니다.
- canonical corrected bundle read-only 평가 결과 MDD는
  `0.073743511705833131472595651962985278354913344557870`, hard filter는 `passed=true`입니다.

## 제한

이 값은 approximate corrected bundle의 기술 결과이며, KOFR·완전한 PIT 기업행사·비용/FX
계약과 readiness가 확보되지 않아 경제 목표 달성이나 PAPER 승격을 의미하지 않습니다.
drawdown latch의 주문 동작은 별도 simulation/PAPER 계약으로 다루며 이 작업에서 실행하지
않았습니다.

## 검증

- performance metrics/readiness/SEC 관련 회귀: `83 passed`
- strict mypy·Ruff·`git diff --check` 통과
- 네트워크·원장·runner·PAPER/live·실주문은 변경하지 않았습니다.
