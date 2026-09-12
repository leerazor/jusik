# 보유 밴드 비용 3배 스트레스 v1

이 문서는 기존 보유 밴드 연구의 저장 결과를 고정 입력으로 재생성한 뒤 비용을 3배로 올려 비교하는 연구 계약이다. 기준 비용은 fee·slippage·FX spread 각각 `0.001`이며, 스트레스 비용은 각각 Decimal `0.003`이다. 보유 밴드는 `0.02`와 `0.04`만 사용하고 초기 자본 `100,000,000 KRW`, gross cap `0.60`, symbol cap `0.20`, leveraged ETF 배분 cap `0.20`, frozen drawdown limit `0.10`을 유지한다. 사용자 최대 손실 허용치는 별도 정책값 `20%`이며 drawdown limit과 같은 값으로 취급하지 않는다.

## 실행 순서와 안전 경계

runner는 실행 전에 prior `results.json`, `preregistration.json`, `hash-manifest.json`, frozen source와 32개 simulation을 SHA-256으로 확인한다. 각 저장 simulation은 기존 `attribute_simulation(sim, cost)`와 held-band `_verify_accounting`으로 다시 계산하고, raw open·strict `decision_at < execution_at`·다음 유효 개장·UTC·split floor/현금·최종 수량·source close terminal mark·현금+보유자산 NAV를 별도로 확인한다. hash, 회계, 시간, completeness 또는 누출 검증이 실패하면 즉시 중단하며 재시도하지 않는다. 저장 결과의 terminal cash에 임의 `+1 KRW`를 더한 복사본도 거부한다.

승인된 실행에서는 먼저 두 band × 두 비용 × 8 period의 32개 full JSON을 순서대로 생성한다. 32개 각 셀은 prior JSON과 full JSON equality 및 SHA-256으로 대조한다. 이 32개가 모두 완료된 뒤에만 두 band × cost 3의 16개를 생성한다. 호출 전 ledger에 셀을 예약하고 전체 cap `48`, in-flight deadline `3600 seconds`를 검사한다. 출력 파일은 exclusive create이며 기존 출력 디렉터리의 재개·덮어쓰기는 허용하지 않는다.

현재 구현은 historical 실행 승인 플래그가 없으면 `simulate`를 호출하지 않는다. 이 작업에서는 Astra의 독립 review 전이 전까지 실제 historical 실행을 수행하지 않았다. PAPER 10% 설정은 유지하고 live trading은 유예한다. PAPER 설정·주문·DB·제품 engine·remote data·GPU는 연구 범위가 아니다.

## 보고할 지표

각 period와 arm에 대해 순손익, 수익률, 실제 equity series의 MDD, 거래 수, turnover, transaction cost, FX cost, 최종 현금, 최종 수량을 기록한다. 비용 3배 순손익의 고정체결 산술값은 다음과 같이 별도 기록한다.

```text
c1_net_pnl - 2 * (c1_transaction_cost + c1_fx_cost)
```

실제 cost 3 결과와 위 산술값의 차이는 체결 수량·경로가 바뀐 효과를 포함할 수 있으므로 별도 필드로 남긴다. band pair는 수익률·MDD·거래 수·turnover·비용·최종 현금과 symbol별 최종 수량 차이를 기록한다. 일곱 독립 fold의 수익률 차이 중앙값과 양수·음수·0 fold 수를 continuous와 분리해 보고한다. 음수 결과는 그대로 보존하며 승자, 승격, 손실 보장을 주장하지 않는다.

레버리지는 equity point에서 관측된 `equity - cash`를 sampled gross exposure로 계산하고, terminal position mark에서 final gross 및 leveraged ETF exposure를 별도로 계산한다. sampled 값은 관측 시점 표본의 지표이고 final 값은 terminal mark의 지표이며, terminal 값이 기간 중 최대치라고 해석하지 않는다.

## 한계

입력은 후향 재사용 자료이며 point-in-time 정확성을 인증하지 않는다. 배당·분배금, 생존·상장 편향과 원천 자료 완전성의 한계가 있다. 실제 조기 폐장과 broker partial/cancel/reject receipt는 고정 연구 모델이 표현하지 않아 지원하지 않는다. 결과는 정책 승격이나 자동 주문 적합성을 의미하지 않는다.

실행 결과와 SHA-256 manifest는 승인된 attempt audit 디렉터리에만 보존한다. 본 문서와 runner의 변경만으로 historical 결과를 새로 만들지 않는다.
