# Symbol cap 초과 관측 episode 재구성

이번 작업은 저장된 observer 결과만 읽어 `symbol_cap=0.20` 초과 관측을 종목별 episode로 재구성한 bounded offline 분석이다. 32개 저장 cell의 배열 순서와 같은 UTC 시각의 반복 행을 그대로 보존했으며, 거래·관측의 인과관계나 관측 사이의 회복을 추정하지 않았다. historical simulation, 자료 수집, GPU, PAPER, 주문, DB와 서비스 호출은 수행하지 않았다.

## 입력과 방법

기존 volatility 15% cadence/cost 결과의 `experiment/hash-manifest.json` 72개 항목과 각 파일 SHA를 다시 검증했다. 현재 canonical mandate SHA는 `ceca2ee1d3e86cf79822b6b4a1606ac6699405f93eaf302fcf3842247f5de7ac`이며, 기존 report·manifest·results 입력의 bytes도 선행 audit의 고정 SHA와 일치했다. 결과의 `execution_order`를 따라 각 observation 행을 읽고 `position_value_krw > 0.20 * nav_krw`인 symbol 행만 선택했다. 같은 symbol의 연속된 저장 행을 하나의 관측 episode로 묶었고, 비연속 행은 별도 episode로 남겼다. 이 경계는 저장 배열의 경계일 뿐 회복을 의미하지 않는다.

## 결과

총 351개 cap-breach 관측을 고정 계약 `EXPECTED_EPISODES=13`에 따라 13개 episode로 재구성했다. 초과는 NVDA 158개 관측·10개 episode, MSFT 193개 관측·3개 episode뿐이었다. 최대 비중은 NVDA `0.2058790572161882352`와 MSFT `0.2313109643362605899`였다.

| cell | cap 관측 | episode | 비용 반영 순수익 % | MDD % | 거래비용 KRW | FX 비용 KRW |
|---|---:|---:|---:|---:|---:|---:|
| fold_7 control c1 | 75 | 2 | -1.2374708925 | 6.5895233517 | 203,956.619650 | 74,383.316356 |
| fold_7 control c3 | 50 | 5 | -1.7634030685 | 6.8561865348 | 609,030.942134 | 222,476.967568 |
| continuous control c1 | 127 | 4 | 40.3404110967 | 10.1632455171 | 1,700,615.851343 | 606,761.797029 |
| continuous control c3 | 99 | 2 | 34.2044238935 | 10.4140497308 | 4,959,879.587231 | 1,767,993.294963 |

나머지 28개 cell에는 초과 관측이 없었다. 비용·성과 수치는 해당 저장 cell의 기존 결과 행을 그대로 연결한 것이며, episode 재구성이 성과의 원인이나 거래 시점을 입증한다는 뜻은 아니다.

## 한계와 증거

저장 관측은 후향 결과이며 point-in-time 정확성, 배당·상장폐지 완전성, 거래 receipt와 회복 경로를 새로 검증하지 않는다. 이번 결과는 설정 상한 준수나 실거래 적합성, 자동 승격을 주장하지 않는다.

retry audit은 `/home/kwl/.local/share/jusik/portfolio-audit/portfolio-symbol-cap-episodes-v1-20260919`에 `preflight.json`, `analysis-1/analysis.json`, `analysis-2/analysis.json`, `deterministic-replay.json`과 SHA 기록으로 보존한다. 분석 2회 output bytes가 일치해야 하며 입력 SHA 또는 72개 ledger가 달라지면 fail-closed로 중단한다.
