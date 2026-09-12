# 보유 밴드 비용 경로 attribution v1

이 연구는 `portfolio-held-band-cost3-stress-v1`의 고정 simulation 48개를 입력으로 사용한다. fold 1~7과 continuous를 합산하지 않고, 각 기간과 control/variant arm별로 cost 2−cost 1 및 cost 3−cost 1을 비교한다. 결과는 symbol별 `Decimal` 회계로 계산하며 `Δ(net+transaction+FX) − Δ(transaction+FX)`를 net 변화로 기록한다.

실행은 입력 세 파일과 simulation manifest hash를 검증하고, 기존 `attribute_simulation`을 재사용해 cash/final NAV 및 symbol 합계 residual이 0.000001 KRW 이하인지 확인한다. 거래 경로 차이는 UTC의 `(executed_at, symbol, side, quantity)` 순서에서 첫 mismatch만 기록하며 가격과 slippage를 포함하지 않는다. turnover, saved MDD, final holdings 차이도 기간별 행에 보존한다.

이 결과는 비용 경로 accounting attribution이다. causal effect나 pure-price effect를 주장하지 않는다. 자본 100,000,000 KRW, 사용자 손실 20%, leverage cap 20%, frozen drawdown 10%, PAPER 10% 조건은 변경하지 않았다. partial fill, cancel, reject는 지원하지 않는다.

산출물은 durable audit 디렉터리의 `report.json`과 `report.md`이며, 실제 시뮬레이션을 재실행하지 않는다.
