# 정기 재배분 주기 비용 스트레스 통합 기록

## 범위

corrected-entry band `0.02`에서 4주 control과 8주 variant를 비용 배수
`1/2/3`, 7개 독립 fold와 continuous로 비교하는 historical/PIT 연구를 통합했다.
실행 상한은 48회이며 control 24회 exact replay를 먼저 수행한다.

## 구현·검증

- 최신 main 기준 retry worktree에서 기존 구현과 타입 fixture를 이식했다.
- frozen preregistration의 `input_paths`/`source_paths` 차이를 정규화하고,
  `source_paths` synthetic regression을 추가했다.
- 관련 pytest 16개, Ruff check/format, strict mypy, `git diff --check` 통과.
- 독립 검토에서 production scope, exact replay, hash/accounting, side effect
  부재를 확인한다.

## 실행 결과

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/portfolio-rebalance-cadence-cost-stress-v1-e017-retry-20260919c`
- `evaluation_count=48`, `all_complete=true`, control 24 + variant 24.
- hash manifest 55개 일치, 최대 회계 residual `2.4375e-31 KRW`.
- `automatic_trading_eligible=false`; 주문, PAPER/live 승격, DB, remote, GPU 변경 없음.
- 이전 실패 audit은 재사용·삭제하지 않고 보존했다.

## 제한

historical/PIT 결과이며 실시간 신호 검증이나 투자 승자 판정으로 해석하지 않는다.
partial/cancel/reject 체결은 unsupported이고, 결과만으로 retuning·정책 승격을
하지 않는다.
