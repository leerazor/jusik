# 성과 지표 진단 계약 갱신

- 상태: 승인 설계·mandate hash 동기화 완료
- 범위: primary metrics는 `CAGR`, `MDD`, `Sharpe`, `Calmar`로 유지하고, 사용자가 요청한 추가 지표를 diagnostic metrics로 명시했습니다.
- 추가 diagnostic metrics: `Sortino`, `Profit Factor`, MDD 회복 기간, 최대 연속 손실. 거래 수·회전율·비용·coverage·결측·stress도 기존처럼 별도 기록합니다.
- 구현 근거: `research_portfolio_performance_metrics.py`가 추가 지표 계산 경로를 이미 보유합니다. 이 변경은 계산 실행·후보 선택·자동 승격을 수행하지 않습니다.
- 동기화: `docs/research-mandate.json`, `research_mandate_governance.py`, `docs/research-mandate.md`, `docs/market-research-mandate.sha256`, `docs/investment-development-roadmap.md`를 같은 설계로 갱신했습니다.
- 검증: mandate governance/planning pytest 35개, `git diff --check` 통과. 새 JSON 전체 SHA는 `22efba4714bc0baf65c56bdfd84dcdee91184a760a13d4d30c5a94486c264ab1`입니다.
- 제한: 실제 성과 수치와 hard-filter 판정은 여전히 KOFR 전체 coverage·시간대 근거 확보 후에만 계산합니다.
