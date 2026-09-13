# 잔여 현금 위험 추정 진단

`portfolio-residual-cash-risk-proxy-v1`의 첫 단계는 저장된 dev1/dev2 결과와 관측을 읽는 진단이다. 모듈은 해시가 확인된 private engine copy의 causal helper만 호출하며 full simulation entry point는 호출하지 않는다. 진단 당시 새 historical simulation 호출은 0회다.

진단 결과는 `/home/kwl/.local/share/jusik/portfolio-audit/portfolio-residual-cash-risk-proxy-v1-abecaf881ae842378d77d5a6838040ed/diagnostic-v4/diagnostic.json`에 저장한다. 각 입력 simulation과 observation의 SHA-256, prior `results.json` 해시와 진단 모듈 해시를 함께 기록한다.

결정 시점별 source 재계산 `pre_vol_gross`, `post_vol_gross`, volatility scale/proxy, eligible count와 symbol별 제외 사유를 제공한다. 저장 target에서 역산할 수밖에 없는 행은 `pre_vol_source=inferred_from_saved_target`로 명시한다. volatility, gate eligibility, cadence/band, cap, reentry latch와 unallocated target은 서로 겹치는 설명 단계이므로 현금 비중의 가산 분해로 해석하지 않는다. `unallocated_target`은 gross cap과 post-volatility target 사이의 목표 공백이며 현금 비율 자체가 아니다.

후속 비교 후보의 포트폴리오 변동성은 동일 시점 이전의 정렬된 KRW 수익률로 계산하는 보수적 scalar proxy `max(0.9*S, P)`로 사전등록한다. 원자료의 미래 가격·FX 사용, 누락·중복·비유한 자료의 보간은 허용하지 않는다. 진단 승인과 immutable preregistration 전에는 전체 시뮬레이션을 실행하지 않는다.

최종 유효 결과는 `experiment-v4/results.json`이다. 초기 adapter 미적용 8개 호출은 무효로 보존하고 재실행하지 않았다. 총 호출은 16회(무효 8회 포함)이며 final/continuous heldout 호출은 0회다. `diagnostic-v4/diagnostic.json`이 권위 있는 진단 경로이며 초기 진단은 판정 근거로 사용하지 않는다.

| arm | 기간/비용 | 현금 중앙값(%) | 순수익률(%) | 거래일 | 최대 실제 종목(%) |
|---|---:|---:|---:|---:|---:|
| baseline | dev1/c1 | 32.6150 | 38.1179 | 13 | 29.029 |
| baseline | dev1/c2 | 32.7550 | 35.5584 | 13 | 28.459 |
| H1 | dev1/c1 | 30.5823 | 39.2283 | 13 | 28.982 |
| H1 | dev1/c2 | 30.8551 | 36.6146 | 13 | 28.398 |
| baseline | dev2/c1 | 43.7780 | 25.6763 | 10 | 19.963 |
| baseline | dev2/c2 | 43.9588 | 24.3676 | 10 | 19.564 |
| H1 | dev2/c1 | 38.0094 | 27.8485 | 10 | 19.691 |
| H1 | dev2/c2 | 38.3905 | 26.3239 | 10 | 19.315 |

H1은 네 dev 쌍 모두 현금 중앙값이 낮고 순수익률이 높으며 거래일은 동일했지만 dev1 실제 종목 비중이 20%를 초과해 finalist를 선택하지 않았다. 보존한 설정은 gross 95%, volatility target 30%, cadence 8주, held-band 2%, drawdown latch 10%, symbol/leverage cap 20%다. H1의 22개 adapter 호출 trace는 모두 90% scalar floor가 binding했으므로 covariance 효과와 10% proxy 완화를 분리해 식별할 수 없다.

target_weight 및 band_skip.value serialization 오차는 1e-38 이하, 실제 deviation은 1e-41 이하였고 Python hash-order 차이로 설명된다. 기준안의 모든 trade/equity/metric은 archive와 정확히 일치했으며 fixture observer off/on도 정확히 일치했다. 결과는 과거 재사용 자료이며 배당·세금은 제외했고, prospective/live/PAPER 변경이나 승격을 수행하지 않았다.
