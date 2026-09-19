# R5 primary metrics 계약 재검증

- 상태: 기술 계약 재검증 완료; 후보 선택·경제 승격은 실행하지 않음.
- 검증: market performance metrics, portfolio performance metrics, GPU stress boundary
  테스트 46개 통과.
- 확인: 비용 차감 수익률·MDD·Sharpe·Calmar 계산 경계, zero volatility/drawdown,
  negative outcome과 MDD hard-filter 경계를 보존합니다.
- 안전: 새 후보 생성·winner 선택·network 수집·PAPER/live·주문·원격 push 없음.
