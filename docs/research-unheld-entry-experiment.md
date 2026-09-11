# 미보유 진입 밴드 실험

`research_unheld_entry_experiment.py`는 2026-09-11에 사전 고정한 미보유 진입 가설을 재현하는 실험 전용 runner입니다. 기존 포트폴리오 엔진의 저회전 2%p 밴드 조건에 `positions[symbol] > 0`를 추가한 복사본만 변형군으로 사용합니다. 제품 엔진, API, UI, 주문 경로는 변경하지 않습니다.

## 실행

세 경로를 모두 명시해야 합니다.

```bash
.venv/bin/python -m jusik.research_unheld_entry_experiment \
  --prior-audit /path/to/20260911T060908Z-rebalance-band \
  --engine-source backend/jusik/research_portfolio_engine.py \
  --output-dir /path/to/new-output
```

출력 디렉터리는 새 디렉터리이거나 비어 있어야 합니다. 기존 결과에 덧쓰기·resume은 거부합니다. 원본 audit 입력은 읽기 전용이며 결과와 source copy는 지정한 출력 디렉터리에만 생성됩니다.

## 고정 계약

- 후보: `portfolio_inverse_volatility_fx_vix_v1`
- 정책: `low_turnover_combined`, 4주 cadence, 2%p band
- 자본·한도: 초기 1억원, gross 60%, symbol 20%, leveraged ETF 20%, drawdown 10%
- 기간: 이전 audit의 7개 OOS fold와 continuous `2024-04-24..2026-09-08`
- 비용: fee, slippage, FX spread 각 1배·2배
- 총 실행: 대조군 16개를 완전 JSON 비교한 뒤 변형군 16개

대조군 하나라도 이전 `b2_c1/c2` JSON과 다르면 변형군을 실행하지 않습니다. source manifest/result/control, 승인된 prespecified SHA, core·runner·guard·source copy와 통제 결과를 실행 전후에 재검증합니다.

## 지표와 판정

`actual_unheld_entry_count`는 재생한 pre-trade 수량이 0인 buy만 셉니다. 부분매도는 보유 상태를 유지하고 전량 매도 뒤 buy는 새 진입입니다. NVDA·TQQQ split은 거래가 없는 split day도 다음 거래 전에 적용하며 최종 수량을 simulation 결과와 대조합니다. 불일치하면 결과를 만들지 않고 실패합니다.

`mean_daily_close_invested_percent`는 각 UTC 날짜의 마지막으로 존재하는 equity point에서 `100 * (equity - cash) / equity`를 계산한 평균입니다. 보간하지 않으며 equity point가 없거나 equity가 0이면 `null`과 사유를 남깁니다.

사전 기준은 비용별로 continuous return delta가 양수, MDD delta가 0 이하, fold return delta 중앙값이 양수, variant 최악 fold MDD가 control 이하이고 32회가 모두 완료되는 것입니다. 진입 수·평균 노출은 설명용 지표이며 새 승자 기준이 아닙니다.

결과 디렉터리에는 `preregistration.json`, `results.json`, `results.csv`, `comparisons.json`, `comparisons.csv`, `report.md`, source copies와 32개 simulation JSON이 생성됩니다. 모든 평가는 과거 자료 재사용이며 point-in-time·prospective·autotrading·PAPER 자격을 부여하지 않습니다.
