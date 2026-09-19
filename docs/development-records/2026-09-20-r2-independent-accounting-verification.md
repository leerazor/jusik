# R2 독립 회계 계약 재검증

- 상태: 기술 계약 재검증 완료, 경제 평가는 `not-evaluated`, R2 전체 checklist는 미완료.
- 범위: 기존 `research_portfolio_accounting_evidence`의 독립 NAV/비용/FX/현금 검증과
  `market_history_action_accounting`의 split/dividend 전이 계약을 읽기 전용으로 재실행.
- 검증: `backend/.venv/bin/python -m pytest backend/tests/test_research_portfolio_accounting_evidence.py backend/tests/test_market_history_action_accounting.py -q`
  — 43 passed.
- 확인된 한계: 등록 bundle은 수수료·세금·slippage·일부 FX·현금 잔액을 보존하지만,
  완전한 fill/opening position, symbol-level terminal mark, complete dividend/corporate-action
  evidence가 없어 realized/unrealized PnL과 net PnL을 확정하지 않습니다. 기존
  `20260916-r2-01-2760e570/loss-accounting-pilot.json`의 `status=blocked`와 동일한
  fail-closed 판정을 유지합니다.
- 안전: 실제 주문·PAPER/live 승격·운영 DB·원격 push 없음.
