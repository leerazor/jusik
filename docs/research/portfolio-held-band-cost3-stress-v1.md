# 보유 밴드 비용 3배 스트레스 v1

## 실행 결과

Astra 승인 뒤 historical simulation을 총 48회 실행했다. full phase 32회는 두 band(`0.02` control, `0.04` variant)와 cost `1x`, `2x`의 8개 기간을 모두 prior JSON과 exact replay했고, cost `3x` 16회를 그 뒤 실행했다. 총 실행 시간은 30.6658초, 재시도는 0회, 완료 행은 48개다. fee·slippage·FX spread는 cost `1x/2x/3x` 각각 `0.001/0.002/0.003`이다. 초기 자본은 `100,000,000 KRW`이며 frozen gross cap `0.60`, symbol cap `0.20`, leveraged ETF cap `0.20`, drawdown limit `0.10`을 유지했다.

독립 raw verifier는 48개를 모두 통과했고 최대 금액 residual은 `4.000000E-31 KRW`였다. runner preflight는 저장된 32개를 읽기 전용으로 검증했으며 historical call은 0회, terminal cash `+1 KRW` 변조 거부 검사는 32회였다. 결과·사전등록·ledger·manifest·독립 검증 파일은 다음 attempt에 보존되어 있다.

- 결과: `/home/kwl/.local/share/jusik/portfolio-audit/portfolio-held-band-cost3-stress-v1-f9aecd54dffc4931a6100ac2de8c8cd3/experiment/results.json` (SHA-256 `d6e4895eac42625fe6fd0f3278ee98195bc031c7e651cb3d003b3c9fa4d4e2f1`)
- 실행 ledger와 preregistration: 같은 `experiment/ledger.json`, `experiment/preregistration.json`
- 결과 검증: `/home/kwl/.local/share/jusik/portfolio-audit/portfolio-held-band-cost3-stress-v1-f9aecd54dffc4931a6100ac2de8c8cd3/results-verification.json`
- 독립 검증: `/home/kwl/.local/share/jusik/portfolio-audit/portfolio-held-band-cost3-stress-v1-f9aecd54dffc4931a6100ac2de8c8cd3/independent/saved48.json`

## cost 3x 16개 실제 지표

수익률과 MDD는 퍼센트, turnover는 퍼센트, 비용·순손익·최종 현금은 KRW다. 최종 수량은 `symbol:quantity`로 기록했다. 음수 순손익은 원자료 그대로 보존했다.

| 기간 | arm | 수익률 | MDD | 거래 | turnover | transaction cost | FX cost | net PnL | 최종 현금 | 최종 수량 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| fold_1 | control | -0.124669 | 4.885273 | 35 | 74.404698 | 446291.279 | 162149.547 | -124669.380 | 84179732.900 | AMD:8, ARM:7, COHR:13, GEV:6, MSFT:7, NVDA:8, TQQQ:16, VRT:13 |
| fold_2 | control | 2.055954 | 1.979088 | 46 | 46.747851 | 280333.606 | 100714.133 | 2055954.216 | 82563181.295 | 000660:9, 005930:44, 487230:137, 487240:221, ARM:10, COHR:6, GEV:2, GOOGL:11, NVDA:11, SOXL:10, VRT:5 |
| fold_3 | control | -2.480741 | 5.366432 | 25 | 91.585333 | 549366.401 | 99201.242 | -2480740.957 | 83173986.132 | 000660:7, 487230:96, 487240:128, AMD:7, ARM:5, COHR:7, GEV:1, GOOGL:7, MSFT:3, NVDA:6, SOXL:23, TQQQ:8, VRT:6 |
| fold_4 | control | 4.602049 | 1.753462 | 50 | 49.500856 | 296800.773 | 110970.898 | 4602048.997 | 76885015.870 | 000660:9, 005930:43, 487240:118, AMD:3, GOOGL:17, MSFT:10, NVDA:17, SOXL:14, TQQQ:13 |
| fold_5 | control | 5.980683 | 2.522408 | 56 | 111.455656 | 668625.153 | 235882.317 | 5980682.944 | 87008500.483 | 005930:23, 487230:119, 487240:87, AMD:5, COHR:4, GEV:1, GOOGL:6, NVDA:10, SOXL:13, VRT:6 |
| fold_6 | control | 6.484222 | 4.344240 | 36 | 82.819528 | 496792.083 | 179122.031 | 6484221.845 | 85425553.642 | 487230:233, AMD:6, ARM:10, COHR:4, GEV:2, SOXL:16, VRT:4 |
| fold_7 | control | -0.390437 | 4.704354 | 34 | 68.118641 | 408538.839 | 158461.629 | -390437.299 | 80210105.462 | NVDA:63 |
| continuous | control | 23.998045 | 7.431864 | 316 | 553.579626 | 3321635.480 | 1176087.174 | 23998045.151 | 113027320.626 | 005930:2, 0173Y0:74, 0190C0:112, 487230:70, 487240:22, AMD:1, ARM:1, COHR:1, MSFT:2, NVDA:6, SOXL:2, TQQQ:9, VRT:2 |
| fold_1 | variant | -0.124669 | 4.885273 | 35 | 74.404698 | 446291.279 | 162149.547 | -124669.380 | 84179732.900 | AMD:8, ARM:7, COHR:13, GEV:6, MSFT:7, NVDA:8, TQQQ:16, VRT:13 |
| fold_2 | variant | 2.055954 | 1.979088 | 46 | 46.747851 | 280333.606 | 100714.133 | 2055954.216 | 82563181.295 | 000660:9, 005930:44, 487230:137, 487240:221, ARM:10, COHR:6, GEV:2, GOOGL:11, NVDA:11, SOXL:10, VRT:5 |
| fold_3 | variant | -2.480741 | 5.366432 | 25 | 91.585333 | 549366.401 | 99201.242 | -2480740.957 | 83173986.132 | 000660:7, 487230:96, 487240:128, AMD:7, ARM:5, COHR:7, GEV:1, GOOGL:7, MSFT:3, NVDA:6, SOXL:23, TQQQ:8, VRT:6 |
| fold_4 | variant | 4.230641 | 1.542880 | 50 | 46.260884 | 277412.250 | 101199.583 | 4230641.031 | 82615403.991 | 000660:9, 005930:43, 487240:118, AMD:3, GOOGL:9, MSFT:10, NVDA:3, SOXL:14, TQQQ:13 |
| fold_5 | variant | 6.076825 | 2.289361 | 55 | 95.391306 | 572236.196 | 219060.721 | 6076825.462 | 86804283.001 | 005930:23, 487230:119, 487240:99, AMD:5, COHR:4, GEV:1, GOOGL:6, NVDA:10, SOXL:13, VRT:6 |
| fold_6 | variant | 6.484222 | 4.344240 | 36 | 82.819528 | 496792.083 | 179122.031 | 6484221.845 | 85425553.642 | 487230:233, AMD:6, ARM:10, COHR:4, GEV:2, SOXL:16, VRT:4 |
| fold_7 | variant | 0.198560 | 4.407036 | 34 | 63.517335 | 380933.159 | 144365.119 | 198559.771 | 80491174.640 | NVDA:64 |
| continuous | variant | 25.104198 | 6.266349 | 316 | 521.686647 | 3130284.060 | 1113920.695 | 25104197.918 | 113997797.000 | 005930:2, 0173Y0:75, 0190C0:113, 487230:71, 487240:22, AMD:1, ARM:1, COHR:1, MSFT:2, NVDA:6, SOXL:2, TQQQ:10, VRT:2 |

full phase의 32행은 control과 variant가 fold 1–3, 6에서 동일했고 fold 4, 5, 7과 continuous에서 variant가 다른 경로를 보였다. 전체 32행과 raw JSON은 결과 artifact에서 확인한다.

## cost 3x 고정체결 비교와 band 차이

고정체결 기준은 `c1_net_pnl - 2 * (c1_transaction_cost + c1_fx_cost)`이며, MDD에는 이 산술을 적용하지 않았다. 아래는 cost3 행의 실제 순손익, 고정 기준, 차이, cost1 대비 최종 현금 변화, 비영(非零) 수량 변화를 요약한 것이다. `quantity delta`가 0인 종목은 생략했다.

| 기간 | arm | 실제 net PnL | 고정 기준 | 실제-고정 | 현금 delta | quantity delta vs c1 |
|---|---|---:|---:|---:|---:|---|
| fold_1 | control | -124669.380 | -177420.962 | 52751.582 | -358030.606 | 0 |
| fold_1 | variant | -124669.380 | -177420.962 | 52751.582 | -358030.606 | 0 |
| fold_2 | control | 2055954.216 | 2251457.077 | -195502.861 | 198297.957 | 005930:-1, 487240:-2, 487230:-2, GEV:-1 |
| fold_2 | variant | 2055954.216 | 2251457.077 | -195502.861 | 198297.957 | 005930:-1, 487240:-2, 487230:-2, GEV:-1 |
| fold_3 | control | -2480740.957 | -2525989.528 | 45248.571 | -246518.409 | 487240:-2, COHR:-1, 487230:-1 |
| fold_3 | variant | -2480740.957 | -2525989.528 | 45248.571 | -246518.409 | 487240:-2, COHR:-1, 487230:-1 |
| fold_4 | control | 4602048.997 | 4715999.066 | -113950.069 | 110752.418 | GOOGL:-1, SOXL:-1, 005930:-1, 487240:-3 |
| fold_4 | variant | 4230641.031 | 4328992.219 | -98351.188 | -177086.384 | SOXL:-1, 005930:-1, 487240:-3 |
| fold_5 | control | 5980682.944 | 6077111.546 | -96428.602 | -656845.294 | 487240:-1, 487230:-1 |
| fold_5 | variant | 6076825.462 | 6213169.537 | -136344.076 | -278230.429 | 487240:-4, COHR:-1, 487230:-1 |
| fold_6 | control | 6484221.845 | 6524612.009 | -40390.164 | -391439.464 | 487230:-4 |
| fold_6 | variant | 6484221.845 | 6524612.009 | -40390.164 | -391439.464 | 487230:-4 |
| fold_7 | control | -390437.299 | -397362.344 | 6925.045 | -66354.128 | NVDA:-1 |
| fold_7 | variant | 198559.771 | 196975.329 | 1584.442 | -43702.868 | NVDA:-1 |
| continuous | control | 23998045.151 | 24776228.111 | -778182.960 | -1940183.430 | 0173Y0:-3, 487240:-1, TQQQ:-1, 0190C0:-4, ARM:-1, 487230:-3, GEV:-1 |
| continuous | variant | 25104197.918 | 25984961.459 | -880763.541 | -1984364.604 | 0173Y0:-3, 487240:-1, 0190C0:-4, ARM:-1, 487230:-3, GEV:-1 |

actual cost3 net PnL은 고정 산술 기준보다 10/16행에서 낮았고, 6행에서 높았다. 실제 3배 결과가 체결 수량·경로에 따라 산술값과 달라진다는 점을 보존한다. continuous에서는 control이 `23,998,045.151 KRW`, variant가 `25,104,197.918 KRW`였고 actual-minus-fixed는 각각 `-778,182.9602 KRW`, `-880,763.5406 KRW`였다.

아래는 cost3의 8개 paired band delta다. `variant - control`이며 수익률·MDD·turnover는 퍼센트, net PnL·최종 현금은 KRW다.

| 기간 | 수익률 delta | MDD delta | 거래 수 delta | turnover delta | net PnL delta | 최종 현금 delta | quantity effect |
|---|---:|---:|---:|---:|---:|---:|---|
| fold_1 | 0.000000 | 0.000000 | 0 | 0.000000 | 0.000 | 0.000 | 0 |
| fold_2 | 0.000000 | 0.000000 | 0 | 0.000000 | 0.000 | 0.000 | 0 |
| fold_3 | 0.000000 | 0.000000 | 0 | 0.000000 | 0.000 | 0.000 | 0 |
| fold_4 | -0.371408 | -0.210581 | 0 | -3.239972 | -371407.966 | 5730388.120 | GOOGL:-8, NVDA:-14 |
| fold_5 | 0.096143 | -0.233046 | -1 | -16.064350 | 96142.518 | -204217.482 | 487240:12 |
| fold_6 | 0.000000 | 0.000000 | 0 | 0.000000 | 0.000 | 0.000 | 0 |
| fold_7 | 0.588997 | -0.297317 | 0 | -4.601306 | 588997.070 | 281069.177 | NVDA:1 |
| continuous | 1.106153 | -1.165516 | 0 | -31.892979 | 1106152.767 | 970476.374 | 0173Y0:1, 0190C0:1, 487230:1, TQQQ:1 |

control과 variant 사이의 cost3 fold 차이 중앙값은 수익률 `0`, MDD `0`, 거래 수 `0`, turnover `0`, transaction cost `0`, FX cost `0`, 최종 현금 `0`, net PnL `0`이다. 이는 fold 1–3, 6의 동일 경로가 포함된 결과다. fold 4의 band 수익률 차이는 `-0.3714079658 pp`였고, fold 5와 7은 양수, fold 1·2·3·6은 0이었다. continuous pair는 variant가 control보다 수익률 `+1.1061527671 pp`, MDD `-1.1655155213 pp`, turnover `-31.8929787818 pp`, 거래 수 차이 `0`, net PnL `+1,106,152.767 KRW`, 최종 현금 `+970,476.374 KRW`였다. continuous quantity effect는 `0173Y0:+1`, `0190C0:+1`, `487230:+1`, `TQQQ:+1`이고 나머지는 0이다.

actual cost3 순손실 fold는 control에서 fold 1·3·7, variant에서 fold 1·3이었다. seven-fold band delta의 결과 수는 양수 2, 음수 1, 0은 4다. 음수 결과는 aggregate에서 숨기지 않았으며 continuous는 fold 중앙값에 포함하지 않고 별도 보고했다.

## 레버리지와 해석 범위

independent raw verifier의 48개 close-sampled leveraged ETF exposure 최대값 범위는 `1.778531%–4.712004%`였다. continuous의 경우 control cost1/2/3이 각각 `4.078563%/4.050079%/4.073477%`, variant가 `4.126578%/4.024103%/4.044797%`였다. 이는 equity 관측 시점에서 계산한 sampled leveraged exposure다. runner의 sampled gross exposure와 terminal mark의 final gross/final leveraged exposure는 별도 지표이며, terminal 값이 기간 중 최대값이라고 주장하지 않는다. continuous cost3 terminal은 control gross `8.847498%`, leveraged `0.979387%`, variant gross `8.877720%`, leveraged `1.048907%`였다.

## 제한사항과 안전 경계

자료는 historical 재사용 자료이고 point-in-time 정확성을 인증하지 않는다. 별도 causal engine 검증은 신호 feature cutoff를 다루지만 독립 raw verifier 자체는 execution·FX timing과 accounting·close-sampled leverage 검증 범위다. 실제 조기 폐장과 broker partial/cancel/reject receipt는 고정 연구 모델이 표현하지 않는다.

사용자 최대 손실 허용치는 별도 정책값 `20%`이며 frozen drawdown limit `10%`와 동일한 기준으로 취급하지 않는다. PAPER `10%` 설정은 변경하지 않았고 live trading은 유예한다. 결과는 정책 승격, 승자 판정, 손실 보장 또는 자동 주문 적합성을 의미하지 않는다. 배당·분배금, 생존·상장 편향, 원천 자료 완전성의 한계도 남는다.

PAPER 주문, DB/config, 제품 engine, remote data, GPU에는 변경이 없다. 실행 결과와 SHA-256 manifest는 승인된 attempt audit 디렉터리에만 보존한다.
