# R3-01 시장 결과 곡선 계약 재검증

- 상태: 기술 계약 재검증 완료; benchmark/USD 근거 부재로 경제 평가는 `not-evaluated`.
- 화면은 저장된 KRW NAV와 drawdown만 곡선으로 표시하고, USD/KRW return과 benchmark는
  자료가 없을 때 `확인 불가`/`비교 불가`로 명시합니다. 없는 benchmark를 추정하지 않습니다.
- 검증: frontend `verify:market-research-contract`, ESLint, TypeScript typecheck,
  production `next build` 통과.
- 한계: 동일 기간·통화 benchmark와 USD 초기 자본 자료가 없으므로 R3-01 checkbox와
  경제 비교 승격은 보류합니다.
- 안전: UI 읽기 검증만 수행했으며 전략·주문·PAPER/live·원격 push 없음.
