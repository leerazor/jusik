# Secondary metrics realized-P&L audit

- 상태: 자료 계약 확인 완료; Profit Factor·최대 연속 손실 계산은 계속 unavailable
- 기록 시각: 2026-09-20T05:10:00Z
- 범위: canonical corrected portfolio simulation의 trade schema를 읽기 전용으로 점검해
  secondary metric을 임의로 합성하지 않는 근거를 고정합니다.

## 확인 결과

- 입력: `/home/kwl/.local/share/jusik/portfolio-audit/portfolio-calendar-2026-krx-holiday-correction/run-v3/simulation.json`
- SHA-256: `7d30263562fdab6edb3c27ff5c6812dd66bd0c29b9d3d8ba991bf9204229954e`
- `trades`는 171건(매수 66, 매도 105)이며 `symbol`, `side`, `quantity`, `notional_krw`,
  `transaction_cost_krw`, `fx_cost_krw` 등을 보존합니다.
- 각 trade에 realized P&L, lot/position close identity, realized cost basis가 없습니다.
  따라서 FIFO·평균법·세금·환전 원가를 추정해 Profit Factor나 최대 연속 손실을 만들지
  않습니다.

## 판정과 재개 조건

- 현재 결과는 `profit_factor`와 `max_consecutive_loss`를
  `missing_realized_trade_pnl`로 unavailable 상태로 유지합니다.
- 기존 NAV chronology로 계산 가능한 MDD recovery duration과 trade count만 유지합니다.
- 재개에는 동일 canonical run의 매도별 realized P&L 또는 명시적 lot/position close
  ledger와 원가·비용 배분 규칙이 필요합니다. 자료가 생겨도 독립 회계 대사와 회귀 검증
  전에는 성과·PAPER 승격에 사용하지 않습니다.

## 안전·검증

- 네트워크·원장·전략·PAPER/live·실주문·runner 상태는 변경하지 않았습니다.
- 관련 metrics/readiness/SEC 회귀 묶음은 `95 passed`로 재검증했습니다.
