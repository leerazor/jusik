# 포트폴리오 배분 GPU screen: 데이터 gate 대기 보고서

이 문서는 `portfolio-gpu-allocation-screen-v1` (attempt `42b4b5646fe3467394bd0b37d46eac99`)의 오프라인 연구 기록이다. 현재 상태는 **blocked**다. 확장 universe의 실제 입력이 준비되지 않아 배분 후보를 평가하지 않았다.

## 결과 상태

| 항목 | 상태 |
| --- | --- |
| 평가 후보 수 | 0 |
| finalist 수 | 0 |
| stress scenario 수 | 0 |
| allocation simulator 실행 | 0회 |
| baseline/expanded 성과 | 미산출 |
| PAPER10%·실행 경로 | 변경 없음 |

net-NAV bootstrap은 기존 검증 자료일 뿐 새 배분 simulator의 입력이나 결과로 사용하지 않는다. 이 기록은 투자 승인, 신호 성능, 실주문 또는 PAPER 정책 승격을 의미하지 않는다.

## 고정 비교 설계(A/B 계획)

데이터 gate를 통과한 뒤 동일한 UTC 평가 격자와 비용 함수를 사용해 한 번 비교할 계획이다. A는 기존 REGISTRY 16종목과 현금이다. A의 목표는 `SOXL`과 `TQQQ` 각 10%(합계 20%), 기존 비레버리지 14종목 각 5%, KRW 현금 10%다. B는 여기에 broad-index `IVV`와 short-bond `SGOV`를 추가한 expanded universe로, `SOXL`과 `TQQQ` 각 10%, 기존 비레버리지 14종목 합계 50%(균등), IVV 10%, SGOV 10%, KRW 현금 10%를 계획한다. USD 현금은 별도 결제 장부이며 이자를 부여하지 않는다.

초기자본은 100,000,000 KRW, 중간 인출은 0이다. 투자기간은 미정이며 3년은 historical lookback일 뿐이다. 목표 레버리지 20%는 리밸런싱 목표이지 연속적인 상한 보장이 아니다. 가격 변동·체결 시점에 실제 비중이 20%를 넘을 수 있으므로 향후 검증에서는 실제 비중, 초과 빈도와 최초 시점을 별도로 보고한다. 20% 준수를 주장하려면 연속 cap을 포함한 별도의 validated policy를 정의하고 검증해야 한다.

목표 지표는 비용 조정 net return, peak-NAV drawdown20%, 실제 레버리지 노출, 저회전율이다. 함께 기록할 값은 MDD, 최장·최악 underwater episode, 증권 회전율, FX 회전율, 비용 항목별 합계와 A/B 차이다. 가격·분배·분할·환율·세금 자료가 없으므로 이 지표는 모두 미산출이다.

## 재개 전 사전등록과 자원 경계

후보를 실행하기 전에 allocation/cash/regime 조합을 최대 32개로 고정하고 각 조합의 비중, 현금금리 가정, regime 규칙, 비용, `seed`, held-out chronology를 기록한다. 이번 보고서에는 평가 후보가 없으므로 구체 후보를 실행한 것으로 해석하지 않는다. batched float64 proxy는 결정론적 CPU 결과와 parity를 확인한 뒤에만 사용하며, 최대 2개 finalist만 기존 exact portfolio engine과 held-out chronology로 재검증한다. proxy/GPU 근사값만으로 결과를 승격하지 않는다.

GPU가 유용한 경우에만 다음 요청 형식을 사용한다.

```text
python -m jusik.research_portfolio_gpu_stress \
  --request PATH --output-dir PATH --device auto|cpu|cuda
```

요청 파일에는 pinned input SHA, seed, bounds와 CPU parity를 포함한다. 최대 4,096 stress scenarios, GPU 메모리 2 GiB, GPU 실행 15분을 넘기지 않는다. Python transfer와 Decimal 전 후보 대조 비용을 먼저 줄이며, GPU 사용률을 높이기 위해 범위를 늘리지 않는다.

## 입력 gate와 재개 조건

| gate | 현재 증거/누락 | 재개 조건 및 검증 |
| --- | --- | --- |
| 확장 가격·세션 | IVV/SGOV 3년 실제 daily rows 0, coverage 미검증 | 2023-09-12~2026-09-11의 point-in-time 가격과 세션·휴일 coverage, 결측 및 IPO 예외를 원본 SHA와 함께 고정 |
| venue/symbol | broker venue·ticker master 미검증 | 각 상품의 당시 venue와 심볼을 primary/broker 자료로 대조 |
| 분배·분할 | 배당·분할 timeline 및 no-event completeness 미검증 | 원주가, 실제 split 수량, ex-date 권리와 payable-date 현금 장부를 독립 검증; 수정주가 중복 적용 금지 |
| FX/시간 | point-in-time USDKRW와 달력 provenance 없음 | UTC timestamp, 시장 휴일, staleness 규칙(영업일 24시간·검증된 휴일/주말 96시간)을 검증 |
| 비용·세금 | 비용은 연구 가정(매수/매도 수수료 10bp+slippage 10bp, FX 10bp), 세금·원천징수 미확정 | 기간별 primary/broker 근거를 고정하고 항목별 비용을 재현; 세후 수익률로 표시하지 않음 |
| 엔진·회전율 | 확장 total-return adapter와 exact 입력 미준비; 기존 pipeline은 dividend return을 제외 | cash/FX/NAV, 정수주 내림, 미체결 현금, 최초 배분·환전을 포함한 비용·turnover 테스트 통과 및 검증된 total-return adapter source 고정 |
| chronology/leakage | 실행 없음 | 월말 평가 후 다음 정규 세션 시가만 사용, 미래 가격·환율 차단, held-out 분리와 point-in-time 테스트 통과 |
| 후보·proxy | preregistration 미완료 | 최대 32개를 실행 전에 고정, float64 CPU parity 및 seed 재현 확인 |
| finalists/stress | 0/0 | finalist 최대 2개 exact engine/held-out 검증; stress는 필요 시 위 CLI와 자원 cap 준수 |

자료·회계·시점 gate와 실행 전 사전등록 검토를 통과한 뒤 단일 CPU A/B를 실행한다. 이후에만 CPU parity를 거쳐 proxy를 사용하고, 최대 2개 finalist를 exact engine/held-out chronology로 검증한다. 하나라도 부족하면 이 문서의 누락 항목과 SHA를 보존한 채 중단한다.

## 고정 입력 및 SHA-256

아래 경로는 attempt audit 디렉터리의 보존 파일이며 worktree 정리 후에도 남는다.

| 자료 | 보존 경로 | SHA-256 |
| --- | --- | --- |
| 최신 expanded-universe readiness report | `/home/kwl/.local/share/jusik/portfolio-audit/portfolio-gpu-allocation-screen-v1-42b4b5646fe3467394bd0b37d46eac99/inputs/research-expanded-universe-readiness.md` | `bea534ed60019d57ba1d680b47161ee6ba2db5e6fc7d92ef8b71fe6d14a1836f` |
| expanded readiness JSON | `/home/kwl/.local/share/jusik/portfolio-audit/portfolio-gpu-allocation-screen-v1-42b4b5646fe3467394bd0b37d46eac99/inputs/readiness.json` | `5f83d4ac08f006a51f18be72cbc00b59b295c0598bae22da8e657d8ddb9f69ca` |
| expanded source manifest | `/home/kwl/.local/share/jusik/portfolio-audit/portfolio-gpu-allocation-screen-v1-42b4b5646fe3467394bd0b37d46eac99/inputs/sources.json` | `f9b69b40947ca55bab32106b311da7edff2245da925fe83e25690d561aae8183` |
| expanded mandate | `/home/kwl/.local/share/jusik/portfolio-audit/portfolio-gpu-allocation-screen-v1-42b4b5646fe3467394bd0b37d46eac99/inputs/research-mandate.json` | `30d2108bc082b7d2d9d079fa09548c15f416167174850303c0d852ada269f73c` |
| expanded comparison protocol | `/home/kwl/.local/share/jusik/portfolio-audit/portfolio-gpu-allocation-screen-v1-42b4b5646fe3467394bd0b37d46eac99/inputs/protocol.md` | `6a61c914a6367088e0e95c5e07c9e0cfc3dbacaa37805389efa62dd383d912d6` |
| expanded universe models source | `/home/kwl/.local/share/jusik/portfolio-audit/portfolio-gpu-allocation-screen-v1-42b4b5646fe3467394bd0b37d46eac99/inputs/research_universe_models.py` | `f5627aac31e19e34a91800a90400e4bc8a130ee93b89f5404240b20eb9cf87c4` |
| GPU role transition report | `/home/kwl/.local/share/jusik/portfolio-audit/portfolio-gpu-allocation-screen-v1-42b4b5646fe3467394bd0b37d46eac99/inputs/e6d362b5dc9a49d8e6038cf1fd704b00aa3510474a15407cd428c106db6c2b90.md` | `e6d362b5dc9a49d8e6038cf1fd704b00aa3510474a15407cd428c106db6c2b90` |
| GPU role transition initial report | `/home/kwl/.local/share/jusik/portfolio-audit/portfolio-gpu-allocation-screen-v1-42b4b5646fe3467394bd0b37d46eac99/inputs/72bfdc05d4436ec88e212aef5714775992e0647f7ef3c2949dbac5ec9d10f5da.md` | `72bfdc05d4436ec88e212aef5714775992e0647f7ef3c2949dbac5ec9d10f5da` |
| GPU stress source | `/home/kwl/.local/share/jusik/portfolio-audit/portfolio-gpu-allocation-screen-v1-42b4b5646fe3467394bd0b37d46eac99/inputs/research_portfolio_gpu_stress.py` | `397e118c6e7f139c98604f566b8dc5c95830a179a56601876c71845190996a79` |

자료 기준일과 retrieval 시각은 manifest 및 원문에 고정된 값을 따른다. 위 증거만으로 historical simulation을 수행했다고 해석하지 않는다.

## 검증 기록과 한계

이번 작업에서 실행한 검증은 문서의 `git diff --check`와 인용 SHA의 read-only 대조뿐이다. 데이터 의존 pytest, exact engine, proxy parity, leakage, turnover, GPU stress는 입력 gate가 닫혀 있어 실행하지 않았다. 재개 후에는 0/음수/비유한 NAV, 중복·결측, 시장 휴일, timezone 경계, rounding, partial fill/cancel/reject와 deterministic CPU parity를 포함해 검증해야 한다.

확장 자료가 준비되기 전에는 A/B 우열, 20% drawdown 준수, 수익성 또는 낮은 회전율을 주장할 수 없다. 본 보고서는 누락 입력, 고정 설계, 자원 제한과 재개 조건을 재현 가능하게 보존하는 문서다.
