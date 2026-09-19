# R2-06 counterfactual 분리 재검증

- 상태: 기술 계약 재검증 완료; 실제 자료 acceptance와 경제 평가는 `not-evaluated`.
- 검증 명령: `backend/.venv/bin/python -m pytest backend/tests/test_market_counterfactual_comparison.py backend/tests/test_research_portfolio_accounting_evidence.py -q`
  — 45 passed.
- 확인: 비용·배당·환율 가정은 scenario별 별도 결과로 보존하며, unavailable을 0으로
  치환하거나 비가산적인 기여를 합산하지 않는 기존 계약을 유지합니다.
- 한계: complete fills/opening positions, corporate-action/dividend evidence와 미래
  benchmark가 없으므로 R2-06 checkbox나 R4 성과 평가를 승격하지 않습니다.
- 안전: 실제 provider 수집·주문·PAPER/live·운영 DB·원격 push 없음.
