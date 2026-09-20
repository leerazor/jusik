# R3-01 market result curves

- 상태: 기술 UI 계약 완료·benchmark 자료는 확인 불가 유지
- 기록 시각: 2026-09-20T02:30:00Z
- 작업 slug: `r3-01-market-curves-20260920`
- 통합 commit: `e3580e2`
- 사용자 계약 문서도 `docs/market-research-contract.md`에 파생 USD 수익률과 빈
  benchmark 곡선의 fail-closed 표시 규칙으로 갱신했습니다.

## 변경과 결정

- 상세 시장 연구 화면이 같은 요청 기간의 KRW NAV, USD 수익률, 기록된 낙폭과
  benchmark 슬롯을 함께 표시합니다.
- USD 수익률은 US 계좌의 양의 초기 원화 자본·초기 환율·각 equity 행의 양의
  환율과 유효한 NAV가 모두 있을 때만 계산합니다. 그 밖에는 구간을 끊고 `확인 불가`로
  남깁니다.
- MDD는 저장된 `drawdown_pct` 곡선의 최대값을 표시합니다. 회계 재검산이나 DD latch
  판정으로 승격하지 않습니다.
- benchmark 자료 계약은 아직 없으므로 동일 기간의 빈 곡선과 명시적 사유를 표시하며,
  값을 합성하거나 임의 benchmark를 채택하지 않습니다.

## 검증

- `npm run verify:market-research-contract` — PASS
- `npm run lint` — PASS
- `npm run typecheck` — PASS
- `npm run build` — PASS
- `git diff --check` — PASS

## 제한

- 기존 결과 API에는 benchmark series와 PIT 비교 자료가 없습니다. 따라서 이 작업은
  화면 계약·fail-closed 표시를 완료한 것이며 경제적 성과, benchmark 초과, PAPER/live
  승격을 주장하지 않습니다.
- 실제 데이터 계약에 benchmark와 USD 기준 자산 시계열을 추가하는 작업은 별도 R1/R2
  자료 readiness 이후에 수행합니다.
