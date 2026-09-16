# 준비된 회계 결과의 counterfactual 비교

`market_counterfactual_comparison.py`는 이미 저장된 `LossAccountingReport` 두 개 이상을 오프라인에서 비교합니다. 비교 과정에서 회계 함수, 전략, 시장 자료 수집기, 시뮬레이션, broker를 호출하지 않습니다. 입력 파일의 원본 bytes SHA-256을 JSON 파싱보다 먼저 확인합니다.

## 입력 계약

비교 envelope는 `market-counterfactual-comparison/v1` schema를 사용합니다. envelope에는 시장, 기간, 유일하고 시간순인 세션, 시장과 일치하는 통화, 초기 자본과 단위, `research_grade`, `data_contract`, `policy_contract`, 그리고 공통 실행·자료 조건인 `fixed_assumptions`를 기록합니다. `fixed_assumptions`는 기준 시나리오의 cost/dividend/fx 값이 아니라 모든 시나리오에 고정한 조건을 뜻합니다.

기준과 각 시나리오는 다음처럼 준비 report 경로와 SHA를 참조합니다.

```json
{
  "schema": "market-counterfactual-comparison/v1",
  "market": "US",
  "period": {"start": "2026-01-02", "end": "2026-01-30"},
  "sessions": ["2026-01-02", "2026-01-30"],
  "currency": "USD",
  "initial_capital": {"value": "100000", "currency": "USD", "unit": "currency"},
  "research_grade": "fixture",
  "data_contract": "prepared-contract-sha",
  "policy_contract": "loss-policy-v1",
  "fixed_assumptions": {"cost": "same", "dividend": "same", "fx": "same"},
  "baseline": {
    "id": "baseline",
    "source": {"path": "baseline-loss.json", "sha256": "..."},
    "assumptions": {"cost": {}, "dividend": {}, "fx": {}}
  },
  "scenarios": [
    {
      "id": "higher-cost",
      "source": {"path": "higher-cost-loss.json", "sha256": "..."},
      "change": {"kind": "cost", "description": "fee schedule change"},
      "assumptions": {"cost": {"fee_rate": "2"}, "dividend": {}, "fx": {}}
    }
  ]
}
```

`scenarios`는 1~3개입니다. 각 scenario의 assumptions에는 `cost`, `dividend`, `fx`를 모두 넣고 기준과 정확히 한 key만 달라야 하며, `change.kind`가 그 key와 같아야 합니다. 중복 시나리오 ID, 중복 세션, 여러 assumption 변경, 기간·시장·통화·초기 자본·등급·계약·고정 조건 불일치를 거절합니다.

SHA로 고정한 각 파일은 `prepared-loss-accounting-report/v1` wrapper여야 합니다. wrapper의 `metadata`는 envelope와 완전히 같고 해당 scenario의 assumptions를 포함해야 합니다. `report`에는 `LossAccountingReport.as_dict()`의 모든 accounting component가 들어갑니다. 중복 JSON key도 거절합니다.

## 결과와 해석 경계

결과는 기준 report와 각 준비 report, 원본 SHA·component evidence, 변경 한 가지, 고정 조건을 그대로 보존합니다. `deltas`에는 각 component의 `scenario - baseline` 차이만 넣습니다. 두 값이 모두 `available`이고 통화·단위가 같을 때만 50자리 `Decimal`로 차감합니다. 통화가 없거나 다르면 차이를 `unavailable`로 둡니다.

`unavailable` component의 `value`는 항상 `null`이며 `diagnostic_value`를 delta로 승격하지 않습니다. 배당·FX의 available 값은 evidence가 반드시 있어야 합니다. 근거가 없으면 결과는 `blocked`이고 `resume_inputs`에 재개에 필요한 입력을 남깁니다. 결과에는 component 합계, 기여 가산, 경제적 평가, approximate 승격을 만들지 않습니다. 결과의 `economic_evaluation`은 항상 `not-evaluated`입니다.

CLI:

```bash
python -m jusik.market_counterfactual_comparison \
  --input comparison-envelope.json \
  --output comparison-result.json
```

`--output`은 envelope 또는 참조된 준비 report를 덮어쓸 수 없습니다. 이 기능의 합성 fixture는 CPU·seed 0 범위에서만 검증하며 실제 자료 수집, replay, engine, 주문, 운영 원장을 실행하지 않습니다.
