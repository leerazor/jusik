# Entry attribution 회계 분석

`research_entry_attribution.py`는 고정된 unheld-entry 실험 결과 32개를 읽어 종목별 회계 귀속과 control/variant 비교를 계산한다. 전략을 다시 실행하거나 현재 시장 데이터·웹 API를 호출하지 않는다.

## 실행

```bash
.venv/bin/python -m jusik.research_entry_attribution \
  --input-dir /path/to/unheld-entry-real32 \
  --output-dir /path/to/new-output
```

출력 디렉터리는 새 디렉터리이거나 비어 있어야 한다. `attribution.json`, `symbol-attribution.csv`, `monthly-attribution.csv`, `report.md`를 생성하며 Decimal 값은 문자열로 보존한다.

## 고정 입력과 검증

분석은 고정된 `results.json`과 `preregistration.json` SHA를 먼저 확인한 후 각 simulation 파일을 한 번 읽고 바이트 해시를 계산한다. `fold_1`부터 `fold_7`, `continuous`와 cost multiplier 1·2, control·variant의 정확히 32개 파일만 허용한다. 각 simulation은 `PortfolioSimulation`으로 검증하고 frozen row의 기간, candidate, policy, complete 상태, metrics와 대조한다. 누락·중복 평가, 비유한 수치, 불완전 결과, artifact SHA 불일치는 실패한다.

재현에 사용한 엔진의 수수료율과 슬리피지율은 frozen engine 계약에 따라 각각 `0.001 * cost_multiplier`로 고정한다. `preregistration.json`의 core source hashes도 결과에 기록한다.

## 회계식

엔진의 `notional_krw`는 슬리피지가 반영된 체결 notional이며 `transaction_cost_krw`는 수수료와 슬리피지를 합친 값이다. 따라서 현금흐름은 다음 두 식이 같은지 함께 검증한다.

```text
signed execution notional - fee - fx cost
signed raw open notional - transaction cost - fx cost
```

종목 손익은 여기에 terminal position value와 split cash-in-lieu를 한 번씩 더한다. split cash는 엔진 contribution에 이미 포함된 현금흐름이므로 별도의 balancing bucket으로 더하지 않는다. 최종 cash+holdings, 저장 contribution, metrics의 거래수·비용, 종목 손익 합계와 `final_equity - initial_equity`를 모두 `0.000001 KRW` 이내에서 reconciliation한다. 실제 실행의 최대 residual은 `2.437500E-31 KRW`였다.

월별 표는 UTC 기준 equity의 월별 마지막 관측값을 사용하고, 같은 시각은 원래 순서를 유지한다. 기간 안의 모든 월에 equity가 있어야 하며 no-trade month도 보존한다. 월별 trade count와 transaction/FX cost를 `executed_at` 월로 집계하고 월간 PnL 합이 최종 PnL과 맞는지 확인한다. valuation 자료가 없으므로 월별 종목 PnL은 산출하지 않는다.

concentration은 종목별 pair PnL delta에 대해 양수 합과 음수 절대값 합을 각각 분모로 사용한다. 합이 0이면 `null`이며 동률은 symbol 오름차순으로 결정한다. 이 분석은 추가 매매의 회계상 귀속을 보여줄 뿐 인과적 profit attribution이나 MDD 원인 분석, 정책 선택을 의미하지 않는다. 배당 데이터는 입력에 없으므로 price return 범위만 다룬다.
