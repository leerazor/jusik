# 포트폴리오 종목 제거 산술 민감도

이 연구는 동결된 32개 simulation과 기존 `research_entry_attribution.analyze` 결과를 재검산한 뒤, 7개 fold와 continuous를 합산하지 않고 각각 종목 기여를 차감한다. 각 기간과 cost(1, 2)에 16개 종목을 모두 출력하며, 원래 팔에 없던 종목은 기여 0으로 명시한다.

계산은 `remaining_pnl = total_pnl - symbol_net_pnl`, `ratio = remaining_pnl / fixed_initial_capital`이다. 전후 우위는 `variant - control`이며, 부호는 원시 Decimal 값으로 판정한다. 양수↔음수만 `strict_flip`이고, 0 도달과 0 출발은 별도 상태다.

CLI는 `--input-dir`, `--saved-attribution`, `--output-dir`를 받는다. 저장 attribution의 SHA-256과 fresh 재계산을 대조하고, 결과 32개·16 pair·256 symbol 행의 완전성과 기존 회계 reconciliation을 요구한다. 출력은 결정적인 `concentration.json`, `concentration.csv`, `report.md`다.

이 결과는 이미 실현된 경로의 고정 자본 사후 산술 민감도다. 자금 재배분이나 재시뮬레이션을 수행하지 않으며, 종목을 거래하지 않았을 때의 수익률·인과 효과·제외 권고를 뜻하지 않는다. PAPER 10% 운영 제한은 변경하지 않는다.
