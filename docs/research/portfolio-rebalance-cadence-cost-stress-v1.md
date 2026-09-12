# 정기 재배분 주기 비용 스트레스 연구

이 문서는 corrected-entry band `0.02`를 고정하고 `low_turnover_weeks=4` 대
`8`을 비용 배수 `1/2/3`에서 비교하는 사전 등록 및 실행 기록이다. 초기 자본은
100,000,000 KRW, 사용자 손실 한도 표기는 20%, `drawdown_limit=0.10`,
`leveraged_etf_cap=0.20` 및 나머지 frozen 설정은 cost3 입력과 동일하게 유지한다.

7개 독립 fold와 continuous를 같은 anchor로 사용한다. fold를 합성하지 않으며,
period별 순수익·MDD·거래 수·turnover·transaction/FX 비용과 ready 이후 reentry
대기 시간을 paired로 기록한다. 위험 close와 recovery/cooldown 감시는 기존 주간
시점을 유지하고 cadence가 위험 청산을 우회하지 않는다. historical/PIT 결과는
실시간 신호 검증으로 해석하지 않으며, partial/cancel/reject 체결 상태는 지원하지
않는 historical fill 의미를 결과에 명시한다.

총 실행은 정확히 48회다. cadence 4 control 24회를 먼저 전체 JSON exact replay한
뒤 cadence 8 variant 24회를 실행한다. 입력 누락, hash 불일치, control replay,
회계 residual(`≤0.000001 KRW`) 실패 시 즉시 중단하며 retry/resume, retuning,
fold 합성, 승자 선택, 정책 승격은 수행하지 않는다.

입력은 다음 durable audit의 cost3 결과·보고서·runner에서 재사용한다.

`/home/kwl/.local/share/jusik/portfolio-audit/portfolio-held-band-cost3-stress-v1-f9aecd54dffc4931a6100ac2de8c8cd3/experiment`

runner는 [`research_portfolio_rebalance_cadence_cost_stress.py`](../../backend/jusik/research_portfolio_rebalance_cadence_cost_stress.py)이며 제품 엔진, PAPER 설정, DB/config, 주문, remote, GPU를 변경하지 않는다.

실행 결과와 각 simulation JSON, ledger, failure record, hash manifest는 전용
`portfolio-rebalance-cadence-cost-stress-v1-e0176881b1d34518805032c279324417`
audit 디렉터리에 보존한다. 결과가 음성이어도 artifact hash와 한계를 보존하고 종료한다.
