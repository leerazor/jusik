# Optimizer 성과지표 우선순위 gap

## 확인

현재 `backend/jusik/research_optimizer.py`의 후보 점수는 두 경로에서
`total_return_pct - max_drawdown_pct`로 계산된다. 상세 성과 모듈에는 CAGR,
Sharpe, Calmar, Sortino, Profit Factor, 최대 연속 손실, MDD 회복기간 계산과
회귀 테스트가 이미 존재하지만 optimizer 후보 ranking에 연결되지는 않았다.

## 판단

사용자가 승인한 우선순위(CAGR·MDD·Sharpe·Calmar)를 기존 frozen run에 소급해
적용하지 않는다. 다음 prospective optimizer 계약은 최소한 연환산 기간, 위험-free/
downside target, trade-level realized P&L, recovery censoring의 근거를 입력으로
고정하고, hard filter와 OOS/WFA 결과에 multi-metric ranking을 명시해야 한다.

현재는 historical/PIT 자료와 사전등록된 weighting이 없으므로 임의 가중치나 점수
변경을 구현하지 않았다. 이 기록은 다음 planner가 선택할 수 있는 기술·방법론 gap이다.
