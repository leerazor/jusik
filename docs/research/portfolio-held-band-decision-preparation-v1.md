# Held-band v2 결정 준비

## 목적과 결정 상태

이 문서는 held-band v2의 미결정 항목을 검토 가능한 형태로 정리한다. 권고는 등록 전 논의를 돕는 것이며, 최종 연구 조건이나 실행 승인이 아니다. `docs/research/portfolio-held-band-preregistration-draft-v2.json`의 미결 필드는 계속 `null`, `execution_allowed`는 `false`로 둔다. mandate와 과거 v1 기록도 이 문서로 변경하거나 다시 해석하지 않는다.

현재 mandate JSON의 SHA-256은 `22efba4714bc0baf65c56bdfd84dcdee91184a760a13d4d30c5a94486c264ab1`이다. 비용 차감 CAGR·MDD·Sharpe·Calmar를 나란히 평가하고 MDD 20% 이하를 hard filter로 적용한다. 후보는 최대 3개이며 자동 승자·승격·동일 holdout 재조정은 금지한다. 순서는 제한된 IS, 별도 validation, 시간 순 walk-forward, 1회 untouched OOS다. 후보별 요구수익률과 계산·자료·산출물·평가 예산은 실행 전에 고정한다.

## 지금 가능한 작업

- 고정된 v1 입력과 결과를 regression/debug fixture로 읽고, parser·회계·대조군 동일성·결정 시각/체결 시각 계약을 확인할 수 있다. 문서에 기록된 v1 입력 manifest는 16개 종목을 포함한다.
- 신규 synthetic fixture를 쓰는 순수 기술 검증과, 기존 자료를 읽기만 하는 결정론적 재생·해시 검증은 별도 허용 범위와 산출물 경로를 정한 뒤 수행할 수 있다. 이들은 데이터 적격성이나 전략 성과를 입증하지 않는다.
- 달력 스트레스 successor는 이미 완료됐고 해당 작업에서 테스트 18개가 통과했다. 같은 구현·검증을 반복하지 않는다.
- 앞선 focused pipeline/held-band 실행은 58개 통과, 1개 기존 frozen-v1 variant SHA 불일치였다. 이는 알려진 역사 고정값 불일치다. 고정 SHA를 현재 코드로 갱신하거나 검증을 약화하지 않는다.
- `market_research_cli status`의 approximate 검사는 실행 당시 CWD의 `approximate-market-data.json`을 확인한다([CLI 구현](../../backend/jusik/market_research_cli.py#L285)). 해당 파일이 없거나 준비되지 않았다는 결과는 그 파일의 상태만 말하며 모든 audit cache가 없다는 뜻은 아니다. 제공된 현재 상태 근거상 KR·US 모두 이 CLI 검사에서 ready가 아니다.

이 단계의 자료 수집, 네트워크 요청, 성과 실험, OOS 판정, 서비스·DB·runner 변경, PAPER/live 변경 및 주문은 가능한 작업에 포함되지 않는다.

## 되돌릴 수 있는 개발 가정

아래 가정은 코드 경로·문서 구조·합성 테스트를 준비하는 데만 쓸 수 있다. 미래 관측, 실제 성과, 연구 적격성 또는 투자 판단의 증거로 승격할 수 없고, formal preregistration의 미결 값을 채울 수 없다.

| 임시 가정 | 허용 범위 | 해제 조건 |
| --- | --- | --- |
| v1 자료와 근사 자료는 비적격 fixture다. | 입출력·회계·회귀·UI의 fixture 표시만 검증한다. 성과 비교, OOS, 후보 선택에는 사용하지 않는다. | 별도 고정한 새 자료 manifest와 등급 검토가 승인되고 적격성이 확인될 때 해제한다. |
| 2%p control과 4%p candidate는 비교 구조 예시다. | 두 arm을 처리하는 synthetic 경로와 비교 출력 형식을 준비한다. v1 비용·제약·결과는 새 조건으로 복사하지 않는다. | 모든 실행 파라미터와 최종 코드·정책 hash를 등록 전에 독립 검토한다. |
| 표본 집계는 독립 거래 세션 수와 유효 band-crossing 기회 수를 함께 보존한다. | 둘의 카운터·누락 사유·fold 배분 형식만 구현한다. 숫자 기준이나 충분성 판정은 두지 않는다. | 자료를 보기 전에 수치 최소 기준과 집계 규칙을 정하고 승인한다. |
| 평가 단계는 시간 순으로 분리한다. | IS → 별도 validation → chronological walk-forward → 1회 untouched OOS 상태 전이만 검증한다. 날짜는 설정하지 않는다. | 새 관측의 시작 가능일과 독립 검토된 경계가 확보된다. |
| 요구수익률 지표 후보는 비용 차감 CAGR의 2%p control 대비 증가분이다. | 지표 정의를 토론하거나 화면에 비확정 선택지로 표시한다. 수치와 기간은 비운다. | mandate와의 정합성, 후보별 수치·horizon을 자료 평가 전에 승인한다. |
| 자료·계산·산출물·평가 예산은 각각 분리해 기록한다. | 설정 schema와 fail-closed 누락 검증만 준비한다. 임의의 한도나 실행을 만들지 않는다. | 범위별 수치, 초과 처리, 재개 규칙을 정하고 실행 전 승인한다. |

## 결정별 권고와 차단 조건

아래 7개 결정은 권고가 있어도 미해결이다. 각 대안의 결과와 임시 사용 가능성을 명시한다. 어떤 임시 가정도 승인된 등록 값으로 간주하지 않는다.

### 1. 자료 등급

- **권고:** v1 및 기존 근사 입력은 regression/debug 전용으로 고정한다. 성과 검증을 재개하려면 관측 시점별 universe와 가격·기업행동·환율의 point-in-time(PIT) 가용성을 증명하는 자료 등급을 먼저 선택한다. 엄격한 PIT·생존/상장폐지·배당 증명이 현재 확보됐다고 주장하지 않는다.
- **근거:** v1은 이미 알려진 후향 결과이며 PIT가 검증되지 않았다. 2026-09-08 이후 호환 관측은 찾지 못했다([v1 결과](portfolio-held-band-interaction-v1.md), [v2 준비 기록](../development-records/2026-09-27-held-band-preregistration-preparation.md)). mandate는 무료 근사 자료를 개인 판단 참고로만 허용하고 strict PIT 검증으로 표시하지 않는다([mandate](../research-mandate.md), [시장 연구 계약](../market-research.md)).
- **대안과 영향:** 근사 등급을 선택하면 bounded한 개인 판단용 표본은 가능하지만 strict PIT·승격 근거가 되지 않는다. strict PIT를 요구하면 적격 자료가 확보되기 전 실행은 차단된다. 등급 미지정은 적격성을 판단할 기준 자체가 없어 차단된다.
- **임시 적용:** 가능—fixture/debug 표시만. 어떤 성과 해석에도 적용 불가.
- **사용자 승인:** 최종 등급 선택과 그에 따른 연구 해석 범위에 필요하다.
- **해제 조건:** 등급 정의, 각 필드의 시점·출처·누락 한계, manifest 검증을 사전등록 검토에서 승인하고 자료 평가 전에 고정한다.

### 2. 시장과 universe

- **권고:** KR 또는 US를 임의로 선택하지 않는다. 각 시장 실행은 독립 범위로 두고 선택 시장, 거래소·자산 유형, 날짜별 eligible universe 구성법, 생존·상장폐지 처리, 표본 추출 및 제외 규칙을 함께 고정한다. 현재 후보를 과거에 소급하지 않는다.
- **근거:** mandate의 일반 시장 연구 계약은 시장별 1억원 계정, 날짜별 point-in-time 종목 재발굴, ETF 제외, 거래량 상위 20개 규칙을 둔다. held-band v2의 특정 시장 선택은 아직 없다. 기존 입력 16개 종목은 대표 universe나 표본 충분성을 증명하지 않는다.
- **대안과 영향:** KR 단독은 KRX 입력 준비에 의존하며 미국 FX 없이 시작할 수 있다. US 단독은 날짜별 listing status와 PIT 환율·기업행동까지 필요하다. 두 시장 동시 실행은 별도 계정·입력·결과를 유지해야 하므로 자료·계산 예산이 늘어난다. 현재 보유 목록만 쓰면 mandate의 날짜별 universe 재발굴과 생존편향 통제를 충족하지 못한다.
- **임시 적용:** 가능—synthetic market 식별자 또는 v1 fixture만. 시장 간 성과를 합치거나 실제 universe로 부를 수 없다.
- **사용자 승인:** 시장·universe 범위 확정에 필요하다.
- **해제 조건:** 시장, 자산 범위, membership 출처·시점, 표본 설계와 제외 기준을 자료를 보기 전에 승인하고 manifest에 고정한다.

### 3. 자료 출처

- **권고:** 후보 출처별 역할과 시점 증명을 정한다. KR 공식 일별 주식 자료는 KRX API 이용 자격·서비스 승인과 날짜별 universe 근거를 확인해야 한다. US 후보로 Alpha Vantage의 날짜 지정 listing/delisting, 일봉 출처, 그리고 환율 vintage를 검토할 수 있으나 조합만으로 PIT를 보장하지 않는다. 제공자별 원문·수집 시각·관측 가용 시각·hash와 결측 정책을 기록한다.
- **근거:** KRX 안내는 로그인 후 인증키 신청 및 관리자 승인, API 활용 신청 후 승인 대기를 명시한다([KRX 이용 방법](https://openapi.krx.co.kr/contents/OPP/INFO/OPPINFO003.jsp)). KRX 서비스 목록은 주식 일별매매정보를 2010-01-04부터 제공한다고 안내한다([KRX 서비스 목록](https://openapi.krx.co.kr/contents/OPP/INFO/service/OPPINFO004.cmd)). Alpha Vantage는 API key를 요구하고, 2010-01-01 뒤의 지정 날짜 기준 active/delisted 목록 조회를 문서화한다([공식 문서](https://www.alphavantage.co/documentation/)). FRED API 요청은 등록 계정으로 발급받는 API key를 요구한다([FRED API key](https://fred.stlouisfed.org/docs/api/fred/v2/api_key.html)). 로컬 KRX smoke는 인증 거부였고, 기존 US 시도는 FRED 최신 vintage가 과거 세션 전 가용성을 증명하지 못해 `insufficient`였다([2026-09-15 기록](../development-records/2026-09-15-market-data-live-contract-fixes.md), [2026-09-22 기록](../development-records/2026-09-22-r1-bounded-us-collection.md)).
- **대안과 영향:** KRX 공식 출처는 적절한 시계열 후보지만 인증·승인 및 universe 완전성 확인이 선행된다. Alpha Vantage의 과거 listing 상태는 후보 근거지만 독립된 시점별 가격·기업행동·환율 근거를 대체하지 않는다. 현재 자료를 유지하면 fixture에 머문다. 공급자 응답을 합치면 provenance 및 충돌 정책까지 고정해야 한다.
- **임시 적용:** 가능—공식 공개 문서와 이미 저장된 원문 metadata를 설계 근거로 사용 가능. 실제 수집·접속·credential 사용은 불가.
- **사용자 승인:** 최종 공급자 조합, 사용 권한·비용, 출처별 한계 수용에 필요하다.
- **해제 조건:** 필요한 접근 권한이 승인되고, 시점 범위와 coverage·기업행동·FX 검증을 통과한 secret-free 자료 manifest를 확보한다. 인증키 자체는 문서나 manifest에 기록하지 않는다.

### 4. IS·validation·walk-forward·OOS 경계

- **권고:** 모든 구간을 실제 적격 관측 뒤에 시간 순으로 배치한다. 제한 IS, 서로 겹치지 않는 validation, 사전 정의된 chronological walk-forward fold, 마지막의 한 번뿐인 untouched OOS를 고정한다. 미래 자료가 아직 없으므로 날짜는 선택하지 않는다. v1과 2026-09-08까지의 결과는 OOS에서 제외한다.
- **근거:** v2 JSON은 각 경계를 `null`로 두고 v1 결과가 이미 알려졌다고 명시한다. v1 자료는 2023-09-09~2026-09-08이며 후향/PIT 미검증이다. 2026-09-08 뒤의 호환 관측이 발견되지 않았다. mandate는 독립 validation, chronological walk-forward, one-time untouched OOS를 요구한다.
- **대안과 영향:** 더 긴 IS는 개발 표본을 늘리지만 미래의 untouched 구간을 침범하면 재사용할 수 없다. validation을 fold 선택이나 tuning에 반복 쓰면 최종 OOS 독립성이 줄어든다. 날짜 미정 상태로는 실행 시작점을 검증할 수 없다.
- **임시 적용:** 가능—단계 순서와 데이터 접근 권한 상태기계만 synthetic 검증. 날짜·기간·fold 수는 임시값으로 채우지 않는다.
- **사용자 승인:** 기간과 검증 설계의 최종 고정에 필요하다.
- **해제 조건:** 새 적격 관측이 생긴 뒤 각 구간의 날짜, 경계 포함 규칙, fold 수와 OOS 접근 통제를 사전등록에 고정한다. 각 단계 종료 전에 다음 단계 자료가 노출되지 않았음을 입증한다.

### 5. 최소 표본

- **권고:** 표본 단위는 **독립 거래 세션 수**와 **적격 band-crossing 기회 수**를 함께 세고 둘 다 통과해야 하는 구조로 정한다. 숫자는 데이터를 열람하거나 후보 성과를 평가하기 전에 근거를 들어 고정한다. 표본 숫자를 v1의 7 folds·32회 실행·16개 입력에서 추론하지 않는다.
- **근거:** v1은 고정 후향 실행의 반복 횟수이지 독립 세션/기회 수의 충분성 근거가 아니다. v2는 `minimum_sample`을 미정으로 둔다. 미래 자료도 아직 없다.
- **대안과 영향:** 세션만 세면 비교 대상인 재배분 기회가 거의 없는 표본도 충분하다고 오판할 수 있다. 기회만 세면 같은 시장 국면에 몰린 의존 관측을 독립 증거로 과대평가할 수 있다. 표본을 계속 늘리면 불확실성은 줄 수 있지만 새 자료·계산·평가 예산과 OOS 노출 부담이 커진다.
- **임시 적용:** 가능—두 카운터와 fold별 분포를 기록. 수치 기준·통과 판정은 불가.
- **사용자 승인:** 정량 최소값과 미달 시 처리 규칙의 승인에 필요하다.
- **해제 조건:** 등록 전, blind 설계 근거와 함께 최소 세션·최소 기회·fold 분포 조건을 고정한다. 각 단계의 적격 자료가 기준을 충족하지 못하면 성과값 없이 불충분으로 종료한다.

### 6. 후보별 요구수익률

- **권고:** 후보의 요구수익률 지표 후보는 비용 차감 CAGR의 2%p control 대비 증가분으로 둔다. 이 지표의 값과 평가 horizon은 미정으로 유지하고, 비용 차감 MDD·Sharpe·Calmar와 MDD 20% hard filter를 별도로 표시한다. Control 대비 비교는 후보의 최소 수익 요구를 대체하지 않는다.
- **근거:** v2는 proposed 4%p 후보와 2%p control을 두고 후보별 metric·value·horizon을 null로 둔다. mandate는 balanced objective와 비용 차감 4개 primary metrics, 별도 MDD filter를 지정한다. v1 통계는 새 요구수익률의 근거가 아니다.
- **대안과 영향:** 순수익률 차이를 요구하면 비용·규모효과와 통합 정의가 겹치거나 비용 민감도를 숨길 수 있다. 절대 CAGR hurdle은 control 대비 효과와 목표 절대 수익을 함께 요구할 수 있지만 별도 근거가 필요하다. metric만 정하고 숫자·horizon을 생략하면 진행 기준이 없어 실행 전 차단된다.
- **임시 적용:** 가능—비용 차감 CAGR 차이를 토론용 metric 후보로만 사용. 수치·horizon·합격 판정에는 적용 불가.
- **사용자 승인:** 후보별 최소값과 horizon, 목표의 해석 확정에 필요하다.
- **해제 조건:** 독립된 기준 근거를 정리하고 값·단위·비용 가정·horizon·실패 시 단계 중단을 사전등록 전에 승인한다. 결과를 본 뒤 기준을 고치지 않는다.

### 7. 실행 예산

- **권고:** `compute_budget`, `data_budget`, `artifact_budget`, `evaluation_budget`을 서로 분리해 한도·측정 단위·초과 시 fail-closed 동작을 정한다. 수치는 추론하지 않는다. 예산은 각 단계와 후보 최대 3개 제한을 반영하고, 승인 없는 추가 결제·원격 compute 없이 완결 가능해야 한다.
- **근거:** v2의 네 예산 항목은 모두 `null`이다. mandate는 bounded compute/data/artifact budget을 실행 전에 요구한다. 자료 수집과 계산량은 시장·기간·표본·fold 수에 따라 달라지며 그 입력 자체가 미정이다.
- **대안과 영향:** 지나치게 낮은 한도는 적격 표본 확보 전 중단을 유발한다. 넓거나 무제한인 한도는 비용·재현성·탐색 폭을 통제하지 못한다. 요청 수만 제한하면 저장 공간·산출물·평가 횟수를 막지 못한다. 큰 총액 한도 하나로 합치면 어떤 자원이 소진됐는지 감추고 단계별 중단을 어렵게 한다.
- **임시 적용:** 가능—네 한도를 별도 필수 설정으로 검증하고 미지정이면 거부. 숫자나 실제 수집·계산은 적용하지 않는다.
- **사용자 승인:** 금전 비용이 드는 자료나 compute를 포함해 최종 수치와 초과 대응을 명시 승인받는다.
- **해제 조건:** 시장·자료·기간·최소 표본·후보 수로 산출 근거를 만들고, 각 예산의 수치·단위·재시도/중단 정책·산출물 보존 정책을 등록과 실행 전에 검토·승인한다.

## 연구 재개 공통 게이트

아래 조건을 모두 만족하기 전까지 v2는 draft로 남기고 어떠한 성과 실험도 실행하지 않는다.

1. 2026-09-08 뒤에 생긴 held-band 호환 신규 관측이 있고, provenance·시점 가용성·등급·market/universe·노출 상태가 검증된다. 현재 자료로 부족하면 명시적으로 차단한다.
2. 위 7개 결정의 최종값 및 data period, exposure status, final code/policy/data manifest hash를 등록 전에 고정한다. mandate와 archive의 값/hash를 임의 갱신하지 않는다.
3. 한 번도 결과가 공개되지 않은 OOS 구간을 보존하며, 단계별 자료 접근·예산·후보 한도를 기술적으로 확인한다.
4. 별도 사전등록 검토와 명시적 실행 승인을 받는다. 이는 PAPER/live나 자동 승격 승인이 아니며, 그 결정은 계속 별도 절차에 둔다.

현재 차단은 신규 적격 관측 부재, 등급·market·universe·source·기간 미결정, IS/validation/walk-forward/OOS 및 최소 표본 미결정, 후보별 요구수익률 미결정, 네 예산과 최종 hash 미결정이다. 차단 해제 후에도 투자 성과나 strict PIT 적격성을 미리 보장하지 않는다.
