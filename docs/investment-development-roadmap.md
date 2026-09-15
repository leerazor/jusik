# 투자 개발 로드맵

- 문서 상태: 제안된 후속 작업 계획
- 기준 커밋: `c2ada5c`
- 작성일: 2026-09-15
- 적용 범위: 미국 손실 진단을 먼저 끝내고, 검증 가능한 경우에만 한국 확장과 PAPER 판단으로 넘어간다.
- 이 문서는 미래 작업의 목표와 완료 조건을 기록한다. 이 커밋으로 어떤 단계도 완료되지 않는다.

## 목적과 우선순위

현재 미국 1년 파일럿은 손실 원인을 분해하고 자료·계산 계약을 바로잡아야 하는 상태다. 한국 확장보다 미국 진단을 앞세우는 이유는 현재 손실이 크고 비교 기준이 아직 고정되지 않았기 때문이다.

1. 미국의 `-16.93%` 결과를 재현 가능한 기준으로 동결한다.
2. 종목 구성, 기업행사, 배당, 환율, 비용, 낙폭 계산의 시간 순서와 단위를 검증한다.
3. 수정된 동일 정책으로 미국 1년을 재실행하고, 자료 게이트를 통과할 때만 같은 정책의 3년을 실행한다.
4. 기존 자료로 화면과 손실 분석을 먼저 제공한다. 화면은 경제적 성공을 의미하지 않는다.
5. 미국 기준과 데이터 계약이 통과한 뒤 한국 수집 실패를 별도 원인으로 해결한다.
6. 사전등록한 후보만 미래 격리 시뮬레이션과 PAPER 검토로 보낸다.

## 완료 판정과 경제적 목표

각 단계에는 기술 완료와 경제적 목표 평가를 별도로 기록한다. 기술 완료는 정한 코드·계약·검사·증거를 충족했다는 뜻이다. 경제적 목표 달성은 고정된 자료와 비용 조건에서 순수익, 낙폭, 회전율을 관찰한 결과이며 기술 완료에서 자동으로 따라오지 않는다.

경제적 평가는 다음을 함께 본다.

- 거래 비용과 FX 비용을 차감한 순수익이 양수인지 확인한다.
- 초기 자본을 포함한 운용 중 최고 NAV에서 내려온 최대 낙폭이 `20%` 목표 안에 드는지 확인한다.
- 거래 횟수·회전율과 비용을 기준선 및 사전등록 후보와 비교한다.
- 벤치마크는 같은 통화, 거래일, 비용 가정으로 계산한다.
- 표본 누락, 상장폐지 처리, 배당·분할 자료의 범위를 결과와 함께 보고한다.

양의 순수익이나 `DD <= 20%`는 보장하지 않는다. 실패한 연구도 정한 재현·검증 조건을 만족하면 기술적으로 완료할 수 있지만, 결과를 제품에 채택하거나 PAPER로 승격하지 않는다. 후보 채택은 별도의 사용자 판단과 PAPER 계약을 요구한다.

## 현재 기준과 확인된 증거

기준 구현은 `main`의 `164ae14` 계열이며, 이 로드맵 작업의 시작점은 등록 커밋 `c2ada5c`다. 아래 항목은 이미 확인한 증거이고, 후속 단계의 기능 체크리스트와 구분한다.

- [x] **E-01** 미국 1년 실행 `87c94561b6f84bdcb87550fd9844f287`를 2025-09-11부터 2026-09-11까지 실행했다.
- [x] **E-02** 미국 기준 입력은 1억원에서 `83,066,975.13원`으로 끝났고, 수익률은 `-16.933%`, MDD는 `26.463%`, 거래 수는 `106`건이다.
- [x] **E-03** 100개 심볼 중 현재 필터를 통과한 심볼은 40개였고, usable row는 9,754/10,080개, 결측은 326개였다.
- [x] **E-04** 실행 산출물 루트는 `/home/kwl/.local/share/jusik/portfolio-audit/20260915-market-data-live-contract-fixes`다.
- [x] **E-05** `us-web-pilot-run.json`의 SHA-256은 `cc9150f8b77a27ffd6b001449c0475933ff744a37011801923f87cbdc5558275`다.
- [x] **E-06** `us-pilot-1y-stable.json`의 SHA-256은 `e58e69fc19fd89589e5cd5d55a43259f1ad28c9b9f0a87c75dd7617f28906aea`다.
- [x] **E-07** 위 해시와 기준 실행은 현재까지 재확인했으며, 이 문서 작성 중 replay를 다시 실행하지 않았다.
- [x] **E-08** KRX 두 서비스는 이전 smoke에서 HTTP 200을 반환했고 2026-06-29 기준 946/1823행을 받았다.
- [x] **E-09** 저장된 한국 cache에는 KOSPI200이 확인되지만, 일부 행이 O/H/L=0·close>0·volume=0으로 남아 parser가 실패하는 별도 문제가 있다.
- [x] **E-10** 한국 zero-OHLC 문제는 인증 실패로 단정하지 않는다. 저장된 과거 문서의 `401`은 오래된 증거다.

현재 발견은 다음과 같다.

- 미국 collector의 `1270`은 기간 시작 시 historical listing에서 고정한 표본을 사용하며 오늘 후보를 과거로 소급하지 않는다. 다만 이후 membership을 반영하지 않는 한계가 있다.
- `1344` 이후 이벤트를 기준으로 심볼 전체를 제외하는 경로가 있어 미래 사건을 과거 선택에 누출할 수 있다.
- stock type이 문자열 분류에 의존한다.
- actions 모델에 배당이 빠져 있다.
- CLI 상태가 상대 파일·상대 run·상대 DB 경로를 사용한다.
- 프런트엔드에 NAV·수익률·낙폭 curve가 없다.
- 투자자 value analysis는 breakout/SMA20 전략과 같은 개념이 아니다.
- 향후 저평가 방법은 당시 이용 가능한 fundamentals만 사용해야 하며 오늘의 valuation을 과거에 넣지 않는다.

## 단계 추적표

상태는 `예정`, `진행`, `검증`, `완료`, `차단` 중 하나로 기록한다. 단계의 기술 완료와 경제적 목표 평가는 각각 증거가 있어야 바꾼다.

| 단계 | 상태 | 기술 목표 | 경제적 목표 평가 | 의존성 | 주 증거·현재 판단 |
| --- | --- | --- | --- | --- | --- |
| R0 | 예정 | 기준 실행·공통 결과/자료 계약·replay | 평가 불가 | 없음 | E-01~E-07, 손실 원인 진단의 기준 필요 |
| R1 | 예정 | 미국 PIT universe와 기업행사 정책 교정 | 평가 불가 | R0 계약 | 고정 pool·미래 사건 제외·actions 결함 |
| R2 | 예정 | 손실·비용·FX·DD 독립 계산과 NAV 대사 | 평가 불가 | R0 (기존 자료로 독립 착수) | R4에서 R1 보정 자료를 재대사; 비용·단위·세금 가정을 검증해야 함 |
| R3 | 예정 | 기존 자료의 결과 화면과 fixture API | 평가 불가 | R0 계약 | R1/R2와 독립적인 읽기 전용 UI 작업 |
| R4 | 예정 | 고정 정책 미국 1년·조건부 3년 재실행 | 순수익·DD20·회전율 평가 | R1, R2와 독립 review | R3는 결과 게시·UX 검증에만 필요; 같은 정책·통화·비용·달력의 비교 |
| R5 | 예정 | 사전등록 후보와 미래 held-out 검증 | 기준 충족 여부 평가 | R4 | 후보 최대 3개, 기준 선고정 |
| R6 | 예정 | 한국 zero-OHLC 진단 및 분리 자료 경로 | 한국 자료로 별도 평가 | R1, R4 이후 우선 | E-08~E-10, 미국 진단을 막지 않음 |
| R7 | 예정 | 격리 시뮬레이션과 PAPER 결정 | PAPER 승인 여부 평가 | R5, 한국은 R6 | 기존 PAPER 계약 유지, 실주문은 별도 승인 영역 |

## 공통 산출물과 기록 규칙

모든 단계는 결과를 다음 템플릿으로 남긴다. 결과 파일은 안전한 audit 루트에 보존하고, 문서에는 경로·SHA-256·실행 조건만 적는다.

| 필드 | 기록 내용 |
| --- | --- |
| 단계/실행 ID | `R<n>`과 고유 run ID |
| 정책 fingerprint | universe, 가격, 기업행사, FX, 비용, 세금, 달력의 hash |
| 입력 자료 | source, 기간, coverage, 누락, 준비 등급 |
| 결과 | NAV, 순수익, MDD, 거래, 회전율, benchmark |
| 기술 판정 | `pass`, `fail`, `not-evaluated`, `blocked`와 이유 |
| 경제 판정 | 순수익·DD20·회전율·비용 기준별 관찰값 |
| 증거 | artifact 경로, manifest, hash, 실행 일시(UTC) |
| 다음 조치 | 한 가지 후속 조치와 담당 단계 |
| 검토 | 독립 reviewer, 검토 일시, 지적·해결 상태 |

로드맵 추적표는 목표 상태를 관리하고 `docs/worktree-tasks.md`는 실제 실행 등록부를 관리한다. 둘을 합쳐 별도 JSON 시스템을 만들지 않는다. 이미 확인한 사실은 `E-*`, 미래 작업은 `R*-*` ID로 구분한다.

후속 등록부의 한 작업은 한 checklist ID를 기준으로 쪼갠다. R1 전체를 하나의 거대한 구현 작업으로 등록하지 않으며, 첫 착수 묶음은 R0-01부터 R0-05까지 각각의 문서화·계약 작업으로 등록한다. 이 문서 작업의 완료는 계획을 만드는 데서 끝나고, 해당 R0 작업의 완료를 뜻하지 않는다.

각 checklist의 근거는 단계 기록과 개발 기록에 다음 한 행으로 남긴다. `status`는 기술 상태이며 경제적 관찰값은 `observed`에 적는다.

| ID | status | observed | artifact/hash | command | commit | review/date |
| --- | --- | --- | --- | --- | --- | --- |
| `R<n>-<nn>` | pass/fail/not-evaluated/blocked | 결과·coverage·순수익·MDD·회전율 또는 해당 없음 | 안전한 경로와 SHA-256 | 재현 명령과 결과 | 통합 commit SHA | reviewer와 UTC 날짜 |

## R0 — 기준 고정과 공통 계약

R0는 모든 후속 결과가 같은 입력과 단위를 사용하도록 만드는 순차 게이트다. 기존 미국 파일럿을 새 정책의 성공 증거로 재해석하지 않는다.

- [ ] **R0-01** 기준 main SHA, 파일럿 run ID, 입력 manifest, 결과 hash를 하나의 재현 기록으로 묶는다.
  - 증거 (기술 status: `pass`, 경제 observed: `not-evaluated`): `/home/kwl/.local/share/jusik/portfolio-audit/20260915-r0-baseline/r0-baseline-freeze/baseline-manifest.json` (SHA-256 `03ff5a140138277d2161a0896c7c8aefd64abe0545de7cc33ed9270882481205`); 모델 parse 및 84개 cache raw entry SHA/size 검증 통과; commit은 이 작업 브랜치 결과를 참조하며 supervisor review·main 통합 전에는 완료로 바꾸지 않는다.
- [ ] **R0-02** result/data contract에 path, account, unit, timestamp, coverage, error schema를 정의하고 shared `ApproximateDataset`·`MarketResearchResult`의 availability, grade, source, limitation, pool/hash를 단일 계약 소유자가 관리한다.
- [ ] **R0-03** 실행 시점과 미래 checkpoint를 포함한 deterministic replay 명령과 run catalogue를 만들고, 실행 시각·run ID를 제외한 metrics·trades·equity가 일치하는지 확인한다.
- [ ] **R0-04** USD·KRW·원화 계좌·초기 자본·환전 방향을 결과 schema에서 명시한다.
- [ ] **R0-05** strict, approximate, fixture, PAPER 등급을 결과와 화면에서 혼동하지 않도록 표시 규칙을 고정한다.

기술 완료 증거는 계약 문서, fixture, replay 결과, 독립 review다. shared 모델을 소비하는 서비스·UI는 같은 계약의 호환 검사를 통과해야 한다. 경제적 평가는 아직 `not-evaluated`다.

## R1 — 미국 자료와 시간 순서 교정

R1은 데이터가 당시 알 수 있었던 universe를 표현하는지 확인한다. 실패한 심볼을 미래 성과가 좋아 보이는 다른 심볼로 바꾸지 않는다. 목표는 100/100을 강제로 만드는 것이 아니라 올바른 coverage와 결측 정책을 만드는 것이다.

- [ ] **R1-01** 시작 시 historical listing에서 고정한 표본과 이후 membership을 구분하고, 이용 가능한 시점 기준으로 eligible universe를 반영한다.
- [ ] **R1-02** 기업행사·상장폐지·delisting·중단일을 관측 시점에 맞춰 처리하고 미래 사건을 추가해도 사건 전 선택이 불변인지 확인하는 회귀 fixture를 추가한다.
- [ ] **R1-03** stock type을 구조화된 분류로 정규화해 보통주, ETF, warrant와 비대상 상품을 구분하고, `NCM`은 상품 종류가 아닌 거래소 alias로 별도 정규화한다.
- [ ] **R1-04** split와 dividend actions를 가격·현금흐름 모델에 연결해 배당 중복 계상을 0으로 만들고 분할 전후 자산을 보존하며, 자료가 없을 때의 missing 정책을 결과에 남긴다.
- [ ] **R1-05** 부분 이력·identity 불일치·상장폐지 심볼은 원인과 coverage로 기록하며 조용히 삭제하지 않는다.
- [ ] **R1-06** safe provider response fixture로 정상, null, quota, auth, parse, coverage 실패를 서로 다른 오류로 회귀 검증한다.

R1이 배당·분할을 반영한다고 수익률이 개선된다고 가정하지 않는다. 자료 수정은 계산의 정확성을 높이는 작업이고 경제적 결과의 방향은 재실행 후 평가한다.

## R2 — 독립 손실 회계와 위험 대사

R2는 전략 로직과 분리된 계산으로 가격손익, 배당, FX, 비용, 세금, 실현·미실현 손익을 대사한다. 공통 계산을 그대로 믿지 않고 독립 모듈과 real-shaped fixture를 사용한다.

- [ ] **R2-01** 가격손익·배당·FX·수수료·slippage·세금·현금 잔액을 독립 항목으로 계산한다.
- [ ] **R2-02** fee, slippage, `sell_tax_rate`를 KR/US 시장별로 명시하고 매도세·거래세 등 세금 종류와 적용 시점을 검증한다.
- [ ] **R2-03** 초기 환전, USD/KRW 단위, 원화 기준 NAV, 환율 시점과 반올림 규칙을 고정한다.
- [ ] **R2-04** 초기 자본을 포함한 운용 중 최고 NAV를 갱신하고 그 고점 대비 하락률의 chronology로 DD latch와 해제 조건을 계산한다.
- [ ] **R2-05** 모든 거래일의 NAV를 대사해 residual이 `1 KRW` 이하이거나 사전 문서화한 더 엄격한 정밀도인지 확인한다.
- [ ] **R2-06** 비용·배당·환율 counterfactual은 별도 결과로 남기고 비가산적인 기여를 합산해 주장하지 않는다.

현재 코드의 공통 `sell_tax_rate .0018`은 적정하다고 확정하지 않는다. 시장별 적용은 미확인 가설로 남기고 R2 사전 검증에서 근거를 확인한다. R2 기술 완료 뒤에야 R4의 순수익과 DD를 경제적으로 읽는다.

## R3 — 기존 자료 결과 화면

R3는 R0 계약이 정한 기존 자료만 읽어 화면에 보여주는 작업이다. R1·R2의 실행을 기다릴 필요가 없는 프런트엔드 작업은 독립 worktree에서 병렬 진행할 수 있다.

- [ ] **R3-01** asset curve에 NAV, USD/KRW return, MDD와 benchmark를 같은 기간·통화로 표시한다.
- [ ] **R3-02** coverage, 자료 등급, provisional 상태, 누락·오류 원인을 수치와 함께 표시한다.
- [ ] **R3-03** R0 API fixture contract로 loading, empty, partial, error 응답을 검증한다.
- [ ] **R3-04** 화면의 investor value analysis와 breakout/SMA20 전략 설명을 분리하고 미래 valuation 사용을 허용하지 않는다.

화면에 curve가 생겨도 손실 결과가 개선된 것은 아니다. 기술 완료는 fixture와 build 및 독립 UI review로 판정한다.

## R4 — 고정 정책 재실행과 미국 우선 평가

R4는 R1·R2와 독립 review가 끝난 뒤 동일한 고정 정책으로 미국 1년을 다시 실행한다. R3 UI는 연구 계산의 선행 조건이 아니며 새 결과 게시와 UX 검증에 사용한다. 1년 자료 게이트는 등급을 보존해 판정한다. strict pilot은 `run.status=completed`, `result.status=ready`, `result.completeness=complete`가 필요하고, approximate pilot은 `run.status=completed`, `result.status=approximate`, `result.completeness=approximate`이면 같은 시장·등급의 final이 참조할 수 있다. 두 등급 모두 고정 실행 가정, 현재 policy hash와 data contract hash, 자료 공급원의 simulated·grade 일치를 확인한다. strict 완료를 모든 자료에 무조건 요구하지 않는다.

- [ ] **R4-01** 수정된 policy fingerprint로 정확히 1년 미국 pilot을 실행하고 기존 결과와 입력 차이를 기록한다.
- [ ] **R4-02** strict pilot은 `run.status=completed`·`result.status=ready`·`result.completeness=complete`, approximate pilot은 `run.status=completed`·`result.status=approximate`·`result.completeness=approximate`인 gate를 기록하고, 후자는 same-market·same-grade final 참조를 허용한다. 고정 실행 가정, 현재 policy hash·data contract hash, 자료 공급원의 simulated·grade 일치도 확인한 뒤 신규 자료를 별도 수집해 3년을 실행하며 자료 부족이면 차단 사유를 남긴다.
- [ ] **R4-03** 신규 3년 입력이 같은 policy hash, 시장, 자료 등급, 실행 가정, source simulated 조건과 canonical data/result contract 및 data contract hash를 쓰는지 확인하고 benchmark를 같은 통화, 비용, 거래일, 초기 자본 기준으로 계산한다.
- [ ] **R4-04** 순수익 양수 여부, `DD <= 20%`, 거래 수·회전율·비용을 목표표에 관찰값으로 기록한다.
- [ ] **R4-05** 3년은 1년 pilot과 기간이 겹친다는 점과 별도 수집 입력임을 표시하고, 기존 1년을 미사용 검증으로 재명명하거나 pilot에서 정책을 고른 뒤 최종 untouched 성과라고 주장하지 않는다.

R4는 결과가 나쁘더라도 고정 정책 재현과 설명이 되면 기술적으로 완료될 수 있다. 양의 순수익이나 DD20을 맞추기 위해 정책을 뒤에서 바꾸지 않는다.

## R5 — 사전등록 후보와 held-out 검증

R5는 R4 결과를 본 뒤 임의로 전략을 고르는 단계가 아니다. 다음 batch에서 검토할 후보 가설을 먼저 제한하고, 검증 날짜·비용·낙폭·회전율 기준을 실행 전에 동결한다.

- [ ] **R5-01** 다음 batch 후보를 최대 3개로 사전등록하고 각 후보의 신호·보유·청산·자료 조건을 적는다.
- [ ] **R5-02** held-out 기간, 비용, DD20, 회전율, missing 정책과 benchmark를 실행 전에 freeze한다.
- [ ] **R5-03** 당시 이용 가능한 fundamentals만 사용하고 오늘의 저평가 지표를 과거 관측에 넣지 않는다.
- [ ] **R5-04** 후보별 양수 순수익·DD20·회전율 기준을 독립적으로 판정하고 negative outcome도 보고한다.
- [ ] **R5-05** 실패 결과를 force-fit하거나 자동 승격하지 않고 사용자에게 선택 가능한 근거로 남긴다.

투자자 분석에서 얻은 가치 신호를 breakout/SMA20의 검증 결과로 바꾸어 쓰지 않는다. R5의 기술 완료와 경제적 후보 통과는 별도 상태다.

## R6 — 한국 자료 확장

R6는 미국 우선 진단이 끝난 뒤 한국의 zero-OHLC 문제를 별도 자료 경로에서 해결한다. 한국 실패가 미국 원인 분석의 선행 조건은 아니다.

- [ ] **R6-01** KRX cache와 서비스 응답을 분리해 HTTP 상태, auth, parse, coverage, readiness를 독립 진단한다.
- [ ] **R6-02** zero-OHLC와 volume 0의 원인을 재현하고 정상 OHLC·행 수·날짜 coverage 계약을 추가한다.
- [ ] **R6-03** 한국과 미국 prepared path를 분리하고 각 시장에 원화 `1e8` 초기 자본과 단위를 명시한다.
- [ ] **R6-04** 같은 정책·비용·달력의 한국 결과를 미국 결과와 섞지 않고 별도 benchmark와 경제 평가로 기록한다.

저장된 KOSPI200 증거가 있다고 한국 OHLC 수집이 준비됐다고 표시하지 않는다. zero-OHLC readiness가 해소될 때까지 한국 단계는 `blocked` 또는 `not-evaluated`로 남긴다.

## R7 — 격리 시뮬레이션과 PAPER 결정

R7은 R5 후보가 prospective 기준을 통과한 뒤 실행한다. 한국 확장 후보는 R6의 자료 기준도 통과해야 한다. 기존 PAPER10% 계약과 관찰 결과는 그대로 유지한다.

- [ ] **R7-01** 미래 격리 자료·설정·DB·artifact 경로를 만들고 과거 결과와 쓰기 상태를 분리한다.
- [ ] **R7-02** 후보별 simulation을 실행해 신호, 주문 의도, 체결 가정, 비용, DD latch를 기록한다.
- [ ] **R7-03** prospective 기준 통과 여부를 독립 reviewer가 확인하고 기존 PAPER와 결과를 혼합하지 않는다.
- [ ] **R7-04** PAPER 승격 여부를 별도 결정 기록으로 남기며 후보를 자동으로 live 설정에 넣지 않는다.
- [ ] **R7-05** 실제 주문은 이 로드맵에 포함하지 않고, 장기 live trading은 별도 설계·권한·안전 검토 뒤에만 논의한다.

R7의 기술 완료는 격리·simulation·review 증거를 뜻한다. PAPER 결정도 수익 보장이 아니며 실주문 권한을 부여하지 않는다.

## 병렬 개발과 통합 순서

R0 공통 계약은 먼저 한 명이 소유하고 순차적으로 통합한다. 계약이 고정되면 첫 병렬 묶음은 R1 데이터, R2 독립 진단 모듈·읽기 전용 artifact, R3 기존 결과 UI로 나눈다.

| 작업 묶음 | 단일 소유 범위 | 소비 범위와 조건 |
| --- | --- | --- |
| R1 data | `backend/jusik/market_data_collector.py`, `backend/jusik/market_history_approximate.py`, `backend/jusik/market_history_models.py`의 collector·approximate dataset·models/actions를 한 Luna가 소유 | shared source/model을 바꾸는 다른 작업은 소유자 route 후 순차 반영 |
| R2 diagnostics | 신규 손실 회계·단위·비용·DD 모듈과 tests | 기존 strategy는 read-only로 소비하고 R0 기존 자료로 독립 검증 |
| R3 frontend | 기존 결과 page/lib만 수정 | R0 canonical API fixture contract를 소비하며 shared model 수정은 하지 않음 |
| R6 market extension | R1 collector release 뒤 한국 collector와 분리된 CLI/config | 미국 경로와 설정을 덮어쓰지 않고 별도 prepared path를 사용 |

- 각 Luna는 전용 worktree, 포트, 테스트 DB, cache, artifact 경로를 사용한다.
- 한 단계의 공통 model·schema 파일은 단일 소유자가 수정한다.
- 독립 작업은 최대 4명의 worker 한도 안에서 진행하고 reviewer 슬롯을 남긴다.
- R4는 R1·R2 완료와 독립 review 뒤 연구 계산을 순차 통합한다. R3는 R4 결과 게시와 UX 검증에만 연결한다.
- R5는 R4의 고정 결과 뒤에만 시작한다. R6는 R1 owner의 자료 계약 release 뒤 진행하되 미국 진단을 막지 않는다.
- R7은 R5 통과 뒤, 한국 후보는 R6 통과 뒤에 시작한다.
- main 병합, 영향 범위 검사, evidence 보존, worktree 정리는 감독이 순차 수행한다.

공통 final publication은 R3와 R4의 증거를 모두 요구하지만, 손실 계산 자체는 UI 완료를 기다리지 않는다.

현재 paused runner나 기존 6개 worktree를 재시작·정리하지 않는다. 이 문서는 향후 작업을 위한 기준이며 실행기 큐를 자동으로 변경하지 않는다.

## 반복 결함 방지와 중단 조건

새 작업은 시작 전에 baseline check와 현재 증거 hash를 확인한다. coordinator가 초기에 제한된 provider probe를 실행할 수 있지만, 키나 인증 응답을 worker에게 전달하지 않는다.

- safe real-shaped fixture에는 KRX zero-OHLC, Alpha의 긴 label·warrant, NASDAQ `NCM`, Yahoo 최근 null, quota/auth 사례를 포함한다.
- UI 작업은 API fixture contract가 먼저 고정된 뒤 시작한다.
- auth, parse, coverage, readiness, performance 실패를 한 가지 오류로 묶지 않는다.
- 수정 시도 두 번이 같은 실패를 반복하면 범위를 넓히지 말고 원인을 격리해 `blocked`와 재개 조건을 기록한다.
- 실패한 symbol을 미래 성과로 대체하거나 자료가 없는 기간을 성공으로 채우지 않는다.
- provider 자료가 없으면 `not-evaluated` 또는 `blocked`를 남기고 결과를 추정해 채우지 않는다.

## 재사용 가능한 작업·인수 기준

후속 작업 지시에는 다음 짧은 양식을 사용한다.

| 항목 | 내용 |
| --- | --- |
| Objective | 한 checklist ID가 바꾸는 결과 |
| Scope | 허용 파일·자료·경로와 금지 범위 |
| Inputs | 고정 SHA, manifest, policy fingerprint |
| Computation cap | 호출 수, 표본, 실행 시간, artifact 상한 |
| Tests | 단위, real-shaped regression, fixture, 독립 review |
| Stop condition | 두 번 반복 실패, 자료 부족, residual 초과 등 |

작업은 다음 조건을 모두 충족할 때만 checklist ID를 완료로 바꾼다.

- 관련 테스트·lint·type check·build가 통과했다.
- real-shaped regression과 필요한 경제 계산 검사가 통과했다.
- 독립 review에서 미래 누출, 단위·비용·coverage 오류가 해소됐다.
- main 통합과 영향 범위 검증이 끝났다.
- 결과 artifact와 hash, 개발 기록, 다음 증거 위치가 남아 있다.

## 단계 종료 보고 표

각 단계 종료 보고는 아래 표를 채워 기술 상태와 경제 상태를 섞지 않는다.

| 보고 필드 | 필수 내용 |
| --- | --- |
| Stage / checklist | 예: `R2`, 완료한 ID와 미완료 ID |
| Technical result | pass/fail/not-evaluated/blocked, 테스트와 review |
| Economic result | 순수익, MDD, DD20, 거래, 회전율, 비용, benchmark |
| Data result | 기간, coverage, 결측, 등급, PIT 조건 |
| Evidence | audit 경로, manifest, SHA-256, UTC 시각 |
| Decision | 유지, 재현, 차단, 후보 검토 또는 사용자 판단 필요 |
| Next step | 후속 checklist 하나와 선행 조건 |

로드맵의 모든 미래 체크리스트는 미완료로 시작한다. 관찰값과 증거가 실제로 생긴 뒤 tracker와 개발 기록을 함께 갱신한다.
