# 투자 개발 로드맵

- 문서 상태: 진행 — 승인된 전용 runner 자동 실행 (R0 완료, R1 이후 순차 진행)
- 기준 커밋: `c2ada5c`
- 작성일: 2026-09-15
- 적용 범위: 미국 손실 진단을 먼저 끝내고, 검증 가능한 경우에만 한국 확장과 PAPER 판단으로 넘어간다.
- 이 문서는 미래 작업의 목표와 완료 조건을 기록한다. 이 커밋으로 어떤 단계도 완료되지 않는다.
- canonical policy_version: `investment-roadmap-governance-v1`
- 이 문서는 투자 개발의 canonical execution plan이다. 승인 설계와 `docs/research-mandate.json`의 versioned governance가 동기화되었고, dispatcher의 fail-closed 구현·검증이 완료된 뒤 전용 scope runner를 재개한다. 일반 research scope, PAPER/live, 실제 주문과 remote push는 재개하지 않는다.

## 목적과 우선순위

현재 미국 1년 파일럿은 손실 원인을 분해하고 자료·계산 계약을 바로잡아야 하는 상태다. 한국 확장보다 미국 진단을 앞세우는 이유는 현재 손실이 크고 비교 기준이 아직 고정되지 않았기 때문이다.

1. 미국의 `-16.93%` 결과를 재현 가능한 기준으로 동결한다.
2. 종목 구성, 기업행사, 배당, 환율, 비용, 낙폭 계산의 시간 순서와 단위를 검증한다.
3. 수정된 동일 정책으로 미국 1년을 재실행하고, 자료 게이트를 통과할 때만 같은 정책의 3년을 실행한다.
4. 기존 자료로 화면과 손실 분석을 먼저 제공한다. 화면은 경제적 성공을 의미하지 않는다.
5. 미국 기준과 데이터 계약이 통과한 뒤 한국 수집 실패를 별도 원인으로 해결한다.
6. 사전등록한 후보만 미래 격리 시뮬레이션과 PAPER 검토로 보낸다.

## 승인된 설계 기준과 검증 순서

목표는 수익 하나를 최대화하는 것이 아니라 수익·위험·비용을 함께 보는 balanced objective다. 비용을 차감한 `CAGR`, `MDD`, `Sharpe`, `Calmar`를 primary metrics로 같은 조건에서 나란히 보고, 어느 하나의 단일 순위나 암묵적 가중치로 대체하지 않는다. 순수익, 거래 수·회전율, 수수료·FX 비용, `Sortino`, `Profit Factor`, MDD 회복 기간, 최대 연속 손실, coverage·결측·자료 등급과 stress 결과는 diagnostic metrics로 별도 표시한다. `MDD <= 20%`는 soft target이 아닌 hard filter다. 필터를 통과하지 못한 후보는 primary metric이 좋아도 다음 단계로 보내지 않는다.

후보는 최대 3개만 사전등록한다. 후보 간 weighted aggregate, 자동 winner, 자동 승격은 만들지 않으며 사용자가 primary·diagnostic 표와 근거를 보고 선택한다. 같은 holdout을 본 뒤 파라미터나 후보를 retune하지 않는다. 무료 자료와 기존 cache를 먼저 사용하고, 그 자료를 audit한 뒤 부족한 부분에만 최소 수집 경로를 추가한다.

검증은 bounded IS에서 후보·비용·자료 계약을 고정하고, 별도 validation의 hard MDD filter를 거친 뒤, 시간 순서 walk-forward를 수행한다. 최종 untouched OOS는 사전등록한 단회 go/no-go gate다. 후보 선택·튜닝·반복 평가에 사용하지 않으며, `MDD > 20%`, invalid data, 또는 사전등록한 required return 미달을 포함한 실패는 stress와 PAPER를 차단한다. OOS pass 뒤 비용·자료 결측·gap·변동성 stress를 별도 diagnostic으로 기록하고, 조건을 통과한 후보만 격리 simulation과 기존 PAPER 계약 검토로 보낸다. live trading은 이 계획과 PAPER 결정에서 분리하며, 별도의 명시적 승인·권한·안전 검토 없이는 허용하지 않는다.

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
| R0 | 완료 | 기준 실행·공통 결과/자료 계약·replay | not-evaluated | 없음 | main b950266; 테스트61개·두 checkpoint exact replay·독립 review 통과 |
| R1 | 진행 | 미국 PIT universe와 기업행사 정책 교정 | 평가 불가 | R0 계약 | R1-01·03·06과 fail-closed 기술 slices 일부 완료; 실제 PIT 행사·권리/가격·coverage 부족으로 R1-02·04·05 및 경제 acceptance 보류 |
| R2 | 진행 | 손실·비용·FX·DD 독립 계산과 NAV 대사 | not-evaluated | R0 (기존 자료로 독립 착수) | R2-05만 canonical approximate 기술 pass; R2-01~04·06은 미완료이고 readiness는 blocked |
| R3 | 완료 | 기존 자료의 결과 화면과 fixture API | not-evaluated | R0 계약 | R3-01~04 기술 pass; 경제 성과·benchmark는 자료 부족으로 평가하지 않음 |
| R4 | 예정 | 고정 정책 미국 1년·조건부 3년 재실행 | 순수익·DD20·회전율 평가 | R1, R2와 독립 review | R3는 결과 게시·UX 검증에만 필요; 같은 정책·통화·비용·달력의 비교 |
| R5 | 예정 | 사전등록 후보와 미래 held-out 검증 | 기준 충족 여부 평가 | R4 | 후보 최대 3개, 기준 선고정 |
| R6 | 진행 | 한국 zero-OHLC 진단 및 분리 자료 경로 | 한국 자료로 별도 평가 | R1, R4 이후 우선 | R6-01~03 기술 계약 pass; R6-02 zero/missing 29행으로 실제 readiness insufficient, R6-04 benchmark·경제 평가는 보류 |
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

- [x] **R0-01** 기준 main SHA, 파일럿 run ID, 입력 manifest, 결과 hash를 하나의 재현 기록으로 묶는다.
  - 증거 (기술 status: `pass`, 경제 observed: `not-evaluated`): `/home/kwl/.local/share/jusik/portfolio-audit/20260915-r0-baseline/r0-baseline-freeze/baseline-manifest.json` (SHA-256 `03ff5a140138277d2161a0896c7c8aefd64abe0545de7cc33ed9270882481205`); 모델 parse 및 84개 cache raw entry SHA/size 검증 통과; commit은 이 작업 브랜치 결과를 참조하며 supervisor review·main 통합 전에는 완료로 바꾸지 않는다.
- [x] **R0-02** result/data contract에 path, account, unit, timestamp, coverage, error schema를 정의하고 shared `ApproximateDataset`·`MarketResearchResult`의 availability, grade, source, limitation, pool/hash를 단일 계약 소유자가 관리한다.
- [x] **R0-03** 실행 시점과 미래 checkpoint를 포함한 deterministic replay 명령과 run catalogue를 만들고, 실행 시각·run ID를 제외한 metrics·trades·equity가 일치하는지 확인한다.
- [x] **R0-04** USD·KRW·원화 계좌·초기 자본·환전 방향을 결과 schema에서 명시한다.
- [x] **R0-05** strict, approximate, fixture, PAPER 등급을 결과와 화면에서 혼동하지 않도록 표시 규칙을 고정한다.

기술 완료 증거는 계약 문서, fixture, replay 결과, 독립 review다. shared 모델을 소비하는 서비스·UI는 같은 계약의 호환 검사를 통과해야 한다. 경제적 평가는 아직 `not-evaluated`다.

### R0 완료 증거 (2026-09-15 UTC)

| ID | status | observed | artifact/hash | command | commit | review/date |
| --- | --- | --- | --- | --- | --- | --- |
| R0-01 | pass | 입력·결과·원본84개 hash 검증 | r0-baseline-freeze/baseline-manifest.json | 모델 parse·SHA/size 검사 | 86beeea | r0_review / 2026-09-15 |
| R0-02 | pass | optional provenance·legacy 호환 | r0-shared-contract verification | pytest46·Ruff·mypy·npm fixture/lint/typecheck/build | 5f91bba | r0_review / 2026-09-15 |
| R0-04 | pass | 독립 KRW 계좌·USD 단위·Decimal 비교 | r0-currency-contract verification | pytest48·Ruff·mypy·npm checks | f949a63 | r0_review / 2026-09-15 |
| R0-05 | pass | 등급/원천·실패/대기/결과없음 구분 | r0-grade-contract/browser/verification.json | npm checks·Playwright visible heading | 01f2d68 | r0_review / 2026-09-15 |
| R0-03 | pass | 두 checkpoint의 106거래·252일 결과 정확히 일치 | r0-deterministic-replay/main-baseline 및 main-future | replay CLI·pytest61·Ruff·mypy | b950266 | r0_review / 2026-09-15 |

증거 경로의 공통 루트는 `/home/kwl/.local/share/jusik/portfolio-audit/20260915-r0-baseline`이며, `integration-verification.json`에 통합 코드·실행 시각·두 catalogue/replay 해시를 기록합니다. 세부 명령은 각 개발 기록과 [replay 사용 문서](market-research-replay.md)에 있습니다. [자료·결과 계약](market-research-contract.md)은 R1/R2/R3의 공통 입력입니다. 원본 생성 코드 후보는 미확인으로 남기며, 현재 통합 코드로 기존 결과의 동등성을 검증했습니다. 수익률은 기존 -16.933% 그대로이고 경제적 목표 달성을 뜻하지 않습니다.

## R1 — 미국 자료와 시간 순서 교정

R1은 데이터가 당시 알 수 있었던 universe를 표현하는지 확인한다. 실패한 심볼을 미래 성과가 좋아 보이는 다른 심볼로 바꾸지 않는다. 목표는 100/100을 강제로 만드는 것이 아니라 올바른 coverage와 결측 정책을 만드는 것이다.

- [x] **R1-01** 시작 시 historical listing에서 고정한 표본과 이후 membership을 구분하고, 이용 가능한 시점 기준으로 eligible universe를 반영한다.
  - 증거: 미국 `approx-us-r1-membership-v1`, 연간 관측·UTC·gap/복구·100/400 상한·event-free 후보 prefix 검증. 통합 `52ef32e7`, pytest111·Ruff·mypy·legacy replay 일치·독립 review 통과. [개발 기록](development-records/2026-09-15-r1-us-membership.md), audit `/home/kwl/.local/share/jusik/portfolio-audit/20260916-r1-01-0406c82a`. 연간 carry-forward는 근사치이며 R1-02~06 및 R1 전체 완료를 뜻하지 않는다.
- [ ] **R1-02** 기업행사·상장폐지·delisting·중단일을 관측 시점에 맞춰 처리하고 미래 사건을 추가해도 사건 전 선택이 불변인지 확인하는 회귀 fixture를 추가한다.
- [x] **R1-03** stock type을 구조화된 분류로 정규화해 보통주, ETF, warrant와 비대상 상품을 구분하고, `NCM`은 상품 종류가 아닌 거래소 alias로 별도 정규화한다.
  - 증거: 내부 5분류·NASDAQ alias, 고정 신규 fixture40개, main pytest63·Ruff·strict mypy·보존37검사 및 Terra 재검토 통과. 통합 `dc59347261e41ca232f2b50dc41dabb0d08e6c63`; `/home/kwl/.local/share/jusik/portfolio-audit/20260916-r1-03-9bd64c13/integration-verification.json` (SHA-256 `0f58bb5d1cc0939c90fd664c2bd4cbd63086d38bcee75328626641212d087c16`). 경제 평가는 `not-evaluated`; R1 전체 완료는 아닙니다.
- [ ] **R1-04** split와 dividend actions를 가격·현금흐름 모델에 연결해 배당 중복 계상을 0으로 만들고 분할 전후 자산을 보존하며, 자료가 없을 때의 missing 정책을 결과에 남긴다.
  - 2026-09-20 SEC 제출 원문 후보 52건(text 후보 dividend 6·split 6 등)을 확보했지만, ex-date·금액·권리수량을
    operator-verified facts로 추출하지 않았습니다. 후보는 action ledger·성과 계산에 적용하지 않고 R1-04를
    미완료로 유지합니다. queue 원문 52/52의 local SHA 결속은 별도 source gate로 검증했지만
    action 사실·effective date·권리/가격·PIT 근거는 여전히 수동 review 전 확정하지 않습니다.
    [후보 preflight](development-records/2026-09-20-us-action-sec-candidate-preflight.md)
- [ ] **R1-05** 부분 이력·identity 불일치·상장폐지 심볼은 원인과 coverage로 기록하며 조용히 삭제하지 않는다.
- [x] **R1-06** safe provider response fixture로 정상, null, quota, auth, parse, coverage 실패를 서로 다른 오류로 회귀 검증한다.
  - 증거: 합성 provider fixture17개(각1심볼/1세션, seed0), 정상/null/quota/auth/parse/coverage·실패 cache 차단·CLI insufficient 보존. 통합 `e335342829a50cd56f57c782ec12edb25764bb72`, main pytest143·Ruff·configured mypy·Terra 독립 재검토 PASS. [개발 기록](development-records/2026-09-16-r1-provider-response-fixtures.md); audit `/home/kwl/.local/share/jusik/portfolio-audit/20260916-r1-06-518dc0fb/integration-verification.json` (SHA-256 `ac982d059e5ff974572bcc98405d923df4cdc1b91b7f0e13f456bbe4d28688ab`). 기존 format 부채는 동일하며 경제 평가는 `not-evaluated`; R1 전체 완료는 아닙니다.

R1이 배당·분할을 반영한다고 수익률이 개선된다고 가정하지 않는다. 자료 수정은 계산의 정확성을 높이는 작업이고 경제적 결과의 방향은 재실행 후 평가한다.

## R2 — 독립 손실 회계와 위험 대사

R2는 전략 로직과 분리된 계산으로 가격손익, 배당, FX, 비용, 세금, 실현·미실현 손익을 대사한다. 공통 계산을 그대로 믿지 않고 독립 모듈과 real-shaped fixture를 사용한다.

- [ ] **R2-01** 가격손익·배당·FX·수수료·slippage·세금·현금 잔액을 독립 항목으로 계산한다.
- [ ] **R2-02** fee, slippage, `sell_tax_rate`를 KR/US 시장별로 명시하고 매도세·거래세 등 세금 종류와 적용 시점을 검증한다.
  - 공식 source audit 부분 근거: 2026-03-20 시행 `증권거래세법 시행규칙`은 유가증권시장
    5/10,000, 코스닥·K-OTC 20/10,000을 명시합니다. SEC FY2026 Section 31 advisory는
    2026-04-04부터 covered sales 기준 $20.60/백만달러를 명시하지만 SRO/broker 고객 비용과
    동일하지 않다고 설명합니다. 시장 board·broker·계좌·유효기간·거래일 적용을 결과 계약에
    결속하지 못했으므로 R2-02 checkbox와 경제 평가는 유지합니다.
- [ ] **R2-03** 초기 환전, USD/KRW 단위, 원화 기준 NAV, 환율 시점과 반올림 규칙을 고정한다.
- [ ] **R2-04** 초기 자본을 포함한 운용 중 최고 NAV를 갱신하고 그 고점 대비 하락률의 chronology로 DD latch와 해제 조건을 계산한다.
- [x] **R2-05** 모든 거래일의 NAV를 대사해 residual이 `1 KRW` 이하이거나 사전 문서화한 더 엄격한 정밀도인지 확인한다.
  - 증거 (기술 status: `pass`, 자료 grade: `approximate`, 경제 observed: `not-evaluated`): [canonical NAV reconciliation 계약](research-nav-reconciliation.md), [canonical evidence 연결 기록](development-records/2026-09-18-r2-canonical-nav-evidence-connection.md), [이번 결정 기록](development-records/2026-09-18-r2-canonical-nav-reconciliation-decision.md)에 고정한 동일 run/manifest/dataset/기간/session identity를 canonical adapter가 결속합니다. run SHA는 `cc9150f8b77a27ffd6b001449c0475933ff744a37011801923f87cbdc5558275`, manifest SHA는 `03ff5a140138277d2161a0896c7c8aefd64abe0545de7cc33ed9270882481205`, dataset SHA는 `e58e69fc19fd89589e5cd5d55a43259f1ad28c9b9f0a87c75dd7617f28906aea`, session evidence SHA는 `9348e2f3f6d2120e99460e34dd0a20e285bd14daf6c1f45f96df688b7bc1046a`입니다. `2025-09-11`~`2026-09-11` 양끝 포함 XNYS의 expected/observed ordered sessions는 `252/252`이고, component projection 최대 residual은 `5E-20 KRW`, independent modeled ledger residual은 `0 KRW`로 각각 `1 KRW` 이하입니다. 이 evidence-based decision은 R2-05만 canonical approximate 기술 pass로 기록하며, 배당·분할 완전성, 실제 비용·세금·FX, initial-capital/NAV timestamp, DD latch·counterfactual, benchmark·미래 검증은 평가하지 않습니다. 따라서 R2 전체는 미완료이고 readiness는 `blocked`/`ready_for_metrics=false`, 경제 평가는 `not-evaluated`로 유지합니다.
- [ ] **R2-06** 비용·배당·환율 counterfactual은 별도 결과로 남기고 비가산적인 기여를 합산해 주장하지 않는다.

현재 코드의 공통 `sell_tax_rate .0018`은 적정하다고 확정하지 않는다. 시장별 적용은 미확인 가설로 남기고 R2 사전 검증에서 근거를 확인한다. R2 기술 완료 뒤에야 R4의 순수익과 DD를 경제적으로 읽는다.

## R3 — 기존 자료 결과 화면

R3는 R0 계약이 정한 기존 자료만 읽어 화면에 보여주는 작업이다. R1·R2의 실행을 기다릴 필요가 없는 프런트엔드 작업은 독립 worktree에서 병렬 진행할 수 있다.

- [x] **R3-01** asset curve에 NAV, USD/KRW return, MDD와 benchmark를 같은 기간·통화로 표시한다.
  - 기술 `pass`, 경제 `not-evaluated`: main `e3580e2`; 기존 저장 equity의 KRW NAV·기록 낙폭과
    계좌/환율 근거가 있는 US USD return을 동일 요청 기간에 표시하고 MDD를 저장 낙폭의
    최대값으로 계산합니다. benchmark 계약·PIT 자료가 없어 빈 상태와 사유를 표시하며 값을
    합성하지 않습니다. 검증은 frontend contract verification, lint, typecheck, build입니다.
    [개발 기록](development-records/2026-09-20-r3-01-market-curves.md)
- [x] **R3-02** coverage, 자료 등급, provisional 상태, 누락·오류 원인을 수치와 함께 표시한다.
  - 기술 `pass`, 경제 `not-evaluated`: main `c8cb6e29b038d3724fd3b76d04788270e9221e0a`; contract/lint/typecheck/build 및 desktop/mobile 16개 재검증·Terra review PASS. 증거: `/home/kwl/.local/share/jusik/portfolio-audit/20260916-r3-02-981ad0a5/integration-verification.json` (SHA-256 `0fe76bcc80d5e141151c887ab23ffa84e8e22520b42183f9d907454f45cec550`). 기존 상태에서 도출한 잠정 UI이며 자료 확정성·승격을 추정하지 않습니다.
- [x] **R3-03** R0 API fixture contract로 loading, empty, partial, error 응답을 검증한다.
- [x] **R3-04** 화면의 investor value analysis와 breakout/SMA20 전략 설명을 분리하고 미래 valuation 사용을 허용하지 않는다.

화면에 curve가 생겨도 손실 결과가 개선된 것은 아니다. 기술 완료는 fixture와 build 및 독립 UI review로 판정한다.

## R4 — 고정 정책 재실행과 미국 우선 평가

R4는 R1·R2와 독립 review가 끝난 뒤 동일한 고정 정책으로 미국 1년을 다시 실행한다. 무료 자료·기존 cache를 먼저 audit하고, 자료가 부족할 때만 최소 수집을 추가한다. R3 UI는 연구 계산의 선행 조건이 아니며 새 결과 게시와 UX 검증에 사용한다. 1년 자료 게이트는 등급을 보존해 판정한다. strict pilot은 `run.status=completed`, `result.status=ready`, `result.completeness=complete`가 필요하고, approximate pilot은 `run.status=completed`, `result.status=approximate`, `result.completeness=approximate`이면 같은 시장·등급의 final이 참조할 수 있다. 두 등급 모두 고정 실행 가정, 현재 policy hash와 data contract hash, 자료 공급원의 simulated·grade 일치를 확인한다. strict 완료를 모든 자료에 무조건 요구하지 않는다. 이 단계의 pilot과 3년 final은 bounded 입력·비용·실행 예산을 사전에 고정하며, 최종 untouched OOS를 선택이나 튜닝에 사용하지 않는다.

- [ ] **R4-01** 수정된 policy fingerprint로 정확히 1년 미국 pilot을 bounded 실행하고 기존 결과와 입력 차이를 기록하며, 무료 자료 우선·audit 후 최소 수집 순서를 증거로 남긴다.
  - 2026-09-20 재수집은 별도 audit에서 credentials/collection을 통과했지만, approximate pilot은
    기업행사 관측시각 불확실성으로 `insufficient`/`incomplete`/`ready=false`, trades/equity/metrics
    `0`으로 종료했습니다. R4-01~05 완료나 경제 승격으로 표시하지 않습니다. [재검증 기록](development-records/2026-09-20-us-market-collection-recheck.md)
- [ ] **R4-02** strict pilot은 `run.status=completed`·`result.status=ready`·`result.completeness=complete`, approximate pilot은 `run.status=completed`·`result.status=approximate`·`result.completeness=approximate`인 gate를 기록하고, 후자는 same-market·same-grade final 참조를 허용한다. 고정 실행 가정, 현재 policy hash·data contract hash, 자료 공급원의 simulated·grade 일치도 확인한다. 범위·등급·coverage가 계약을 만족하면 audit한 cache를 재사용하고, 부족한 날짜·심볼만 bounded 수집으로 보완하며 재사용·보완 evidence를 각각 기록한다. 자료 부족이면 차단 사유를 남긴다.
- [ ] **R4-03** 신규 3년 입력이 같은 policy hash, 시장, 자료 등급, 실행 가정, source simulated 조건과 canonical data/result contract 및 data contract hash를 쓰는지 확인하고 benchmark를 같은 통화, 비용, 거래일, 초기 자본 기준으로 계산한다.
- [ ] **R4-04** 비용 차감 `CAGR`, `MDD`, `Sharpe`, `Calmar`를 primary metrics로 기록하고, `MDD <= 20%` hard filter를 적용하며, 순수익 양수 여부·거래 수·회전율·비용은 diagnostic metrics로 별도 기록한다.
- [ ] **R4-05** 3년은 1년 pilot과 기간이 겹친다는 점과 별도 수집 입력임을 표시하고, 기존 1년을 미사용 검증으로 재명명하거나 pilot에서 정책을 고른 뒤 최종 untouched OOS 성과라고 주장하지 않는다.

R4는 결과가 나쁘더라도 고정 정책 재현과 설명이 되면 기술적으로 완료될 수 있다. 양의 순수익이나 DD20을 맞추기 위해 정책을 뒤에서 바꾸지 않는다.

## R5 — 사전등록 후보와 held-out 검증

R5는 R4 결과를 본 뒤 임의로 전략을 고르는 단계가 아니다. 다음 batch에서 검토할 후보 가설을 최대 3개로 먼저 제한하고, bounded IS·validation·walk-forward와 최종 untouched OOS의 날짜·비용·자료·낙폭 기준을 실행 전에 동결한다. validation의 `MDD <= 20%` hard filter를 먼저 적용하며 primary metrics를 weighted aggregate로 합치거나 자동 winner를 고르지 않는다.

- [ ] **R5-01** 다음 batch 후보를 최대 3개로 사전등록하고 각 후보의 신호·보유·청산·자료 조건과 bounded IS 범위를 적는다.
- [ ] **R5-02** validation·walk-forward·최종 untouched OOS 기간, 비용, `MDD <= 20%` hard filter, 회전율, missing 정책과 benchmark를 실행 전에 freeze하고, 최종 OOS를 단회 go/no-go gate로 사전등록한다.
- [ ] **R5-03** 당시 이용 가능한 fundamentals만 사용하고 오늘의 저평가 지표를 과거 관측에 넣지 않는다.
- [ ] **R5-04** 후보별 비용 차감 `CAGR`, `MDD`, `Sharpe`, `Calmar`를 primary metrics로 독립 판정하고, 양수 순수익·회전율·비용·coverage와 stress 결과는 diagnostic으로 기록하며 negative outcome도 보고한다.
- [ ] **R5-05** 실패 결과를 force-fit하거나 같은 holdout에 retune하거나 weighted aggregate·자동 winner·자동 승격으로 처리하지 않고 사용자에게 선택 가능한 근거로 남긴다.

투자자 분석에서 얻은 가치 신호를 breakout/SMA20의 검증 결과로 바꾸어 쓰지 않는다. R5의 기술 완료와 경제적 후보 통과는 별도 상태다.

## R6 — 한국 자료 확장

R6는 미국 우선 진단이 끝난 뒤 한국의 zero-OHLC 문제를 별도 자료 경로에서 해결한다. 한국 실패가 미국 원인 분석의 선행 조건은 아니다.

- [x] **R6-01** KRX cache와 서비스 응답을 분리해 HTTP 상태, auth, parse, coverage, readiness를 독립 진단한다.
  - 기술 `pass`, 경제 `not-evaluated`: `diagnose_krx_cache()`와 `diagnose_krx_response()`가
    cache 무결성과 서비스 응답을 서로 다른 경로로 읽고 HTTP status, auth, parse, coverage,
    zero/missing OHLCV, readiness를 fail-closed로 분리합니다. 실제 service-response artifact
    `/home/kwl/.local/share/jusik/portfolio-audit/20260920-r6-krx-diagnostics/service-response.json`
    (SHA-256 `ad733e5520027298c8e7f3f4c6966a27409d0d90778772a6a2d184285605873f`)는 cache
    integrity를 `null`로 남기고 HTTP 200·946 membership·917 valid bars·29 zero/missing·
    readiness exit 2를 기록합니다. auth/parse fixture도 focused test로 검증했습니다. 실제
    한국 자료 readiness와 경제 승격은 R6-02의 `insufficient` 상태로 보류합니다.
- [x] **R6-02** zero-OHLC와 volume 0의 원인을 재현하고 정상 OHLC·행 수·날짜 coverage 계약을 추가한다.
  - 기술 `pass`, 자료 readiness `insufficient`, 경제 `not-evaluated`: `diagnose-krx-cache`가
    실제 cache에서 HTTP status·raw SHA/size·parser·coverage·membership·valid bar·zero/missing
    OHLCV를 분리 기록합니다. artifact `/home/kwl/.local/share/jusik/portfolio-audit/20260920-r6-krx-diagnostics/report.json`
    (SHA-256 `8c9fa160e597eba627ae27f7353ccfb8f59f7ff55157c7040f822a79650815bb`)에서 HTTP 200,
    membership 946, valid bars 917, zero/missing 29, parser/coverage 실패 0, readiness
    `insufficient`을 확인했습니다. zero 행은 보간하지 않으며 R6 전체 완료·한국 성과 승격을 뜻하지 않습니다.
    전후 공식 STK 응답 대조에서도 6/26·6/29 대상 29개가 모두 zero, 6/30에는 28개가 zero로
    반복됐지만, 별도 status 원문 없이 거래정지로 확정하지 않았습니다. [전후 대사 기록](development-records/2026-09-20-r6-krx-zero-adjacent-recheck.md)
    [개발 기록](development-records/2026-09-20-r6-krx-diagnostics.md)
- [x] **R6-03** 한국과 미국 prepared path를 분리하고 각 시장에 원화 `1e8` 초기 자본과 단위를 명시한다.
  - 기술 `pass`, 경제 `not-evaluated`: KRX와 US collector가 서로의 provider 경로를 호출하지
    않고, prepared file import가 요청 시장과 dataset market mismatch를 거부합니다. 결과 계약은
    시장별 native currency(KR=KRW, US=USD), reporting currency(KRW), 독립 simulated account와
    초기 원화 자본 `100000000`을 고정합니다. 관련 collector/approximate/readiness 테스트와
    [R6 자료 경로 재검증 기록](development-records/2026-09-20-r6-krx-path-verification.md)을
    확인했습니다. 실제 한국 성과·benchmark 승격은 R6-02 readiness insufficient 때문에 보류합니다.
- [ ] **R6-04** 같은 정책·비용·달력의 한국 결과를 미국 결과와 섞지 않고 별도 benchmark와 경제 평가로 기록한다.

저장된 KOSPI200 증거가 있다고 한국 OHLC 수집이 준비됐다고 표시하지 않는다. zero-OHLC readiness가 해소될 때까지 한국 단계는 `blocked` 또는 `not-evaluated`로 남긴다.

## R7 — 격리 시뮬레이션과 PAPER 결정

R7은 R5 후보가 사전등록한 최종 untouched OOS를 단회 pass하고 필요한 자료 게이트를 통과한 뒤 시작한다. R7 내부 순서는 R7-01 격리, R7-02 simulation과 stress, R7-03 prospective·stress 독립 review다. 어느 단계라도 실패하면 PAPER로 진행하지 않는다. 한국 확장 후보는 R6의 자료 기준도 통과해야 한다. 기존 PAPER10% 계약과 관찰 결과는 그대로 유지하며, PAPER는 live 승인과 별개의 결정이다.

- [ ] **R7-01** 미래 격리 자료·설정·DB·artifact 경로를 만들고 과거 결과와 쓰기 상태를 분리한다.
- [ ] **R7-02** 후보별 격리 simulation과 비용·자료·gap·변동성 stress를 실행해 신호, 주문 의도, 체결 가정, 비용, DD latch와 primary/diagnostic 결과를 기록한다.
- [ ] **R7-03** R7-02의 stress 결과와 prospective 기준 통과 여부를 독립 reviewer가 확인하고, 어느 하나라도 실패하면 PAPER로 진행하지 않으며 기존 PAPER와 결과를 혼합하지 않는다.
- [ ] **R7-04** PAPER 승격 여부를 별도 결정 기록으로 남기며 후보를 자동으로 live 설정에 넣지 않고, live는 별도 명시적 승인 없이는 논의하지 않는다.
- [ ] **R7-05** 실제 주문은 이 로드맵에 포함하지 않고, 장기 live trading은 별도 설계·권한·안전 검토와 명시적 운영자 승인 뒤에만 논의한다.

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

2026-09-15 사용자가 계획의 자동 개발을 요청했다. [로드맵 자동 개발 절차](roadmap-automation.md)에 따라 전용 큐를 준비하며, 기존 paused 연구 큐와 기존 6개 worktree는 재시작·정리하지 않는다. 실행기 활성화와 실제 dispatch 상태는 작업 등록부와 개발 기록에 별도로 기록한다. 이 로드맵의 체크는 각 작업의 검증 증거가 확보된 뒤에만 바꾼다.

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
