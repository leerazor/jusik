# Held-band v2 결정 준비

## 목적과 결정 상태

이 문서는 held-band v2의 미결정 항목을 검토 가능한 형태로 정리한다. 권고는 등록 전 논의를 돕는 것이며, 최종 연구 조건이나 실행 승인이 아니다. `docs/research/portfolio-held-band-preregistration-draft-v2.json`의 미결 필드는 계속 `null`, `execution_allowed`는 `false`로 둔다. mandate와 과거 v1 기록도 이 문서로 변경하거나 다시 해석하지 않는다.

현재 mandate JSON의 SHA-256은 `22efba4714bc0baf65c56bdfd84dcdee91184a760a13d4d30c5a94486c264ab1`이다. 비용 차감 CAGR·MDD·Sharpe·Calmar를 나란히 평가하고 MDD 20% 이하를 hard filter로 적용한다. 후보는 최대 3개이며 자동 승자·승격·동일 holdout 재조정은 금지한다. 순서는 제한된 IS, 별도 validation, 시간 순 walk-forward, 1회 untouched OOS다. 후보별 요구수익률과 계산·자료·산출물·평가 예산은 실행 전에 고정한다.

## 지금 가능한 작업

- 고정된 v1 입력과 결과를 regression/debug fixture로 읽고, parser·회계·대조군 동일성·결정 시각/체결 시각 계약을 확인할 수 있다. 문서에 기록된 v1 입력 manifest는 16개 종목을 포함한다.
- 기존 US approximate 100-symbol 수집 자료도 파이프라인 fixture 후보로 읽기 전용 사용할 수 있다: [결과 JSON](/home/kwl/.local/share/jusik/portfolio-audit/20260922-us-vintage-collection-100/result.json), [cache manifest](/home/kwl/.local/share/jusik/portfolio-audit/20260922-us-vintage-collection-100/cache/manifest.json), [completed marker](/home/kwl/.local/share/jusik/portfolio-audit/20260922-us-vintage-collection-100/cache/completed.json). 요청 범위는 2025-09-11~2026-09-11, 종목 76개, bars 20,306/expected 27,472로 7,166개가 빠졌다. 제외 종목은 25개이고 diagnostics는 `unknown` 56, `parse` 3, `identity_mismatch` 2, `partial_history` 2다. dividend/split event 121행은 `observed_at=null`이다([vintage 수집 기록](../development-records/2026-09-22-fred-historical-vintage.md)). 이 자료는 2026-09-24까지 수집·완료되어 이미 노출됐다([request identity 기록](../development-records/2026-09-24-r1-05-request-descriptor.md)). 따라서 일부 날짜가 v1 종료 뒤여도 최종 OOS나 자료 합격 근거가 될 수 없다. 기존 파일을 변경하지 않고 개발·회귀 fixture로만 쓴다. marker가 지정한 output path `/home/kwl/.local/share/jusik/portfolio-audit/20260924-r1-05-receipt/result.json`과 API key 환경변수 명시적 unset 조건에서 실행한 read-only `collect-status`는 `completed=true`, `entries=137`, `ready=false`를 반환했고 누락 항목은 `ALPHA_VANTAGE_API_KEY`, `FRED_API_KEY`였다. 이는 새 수집에 필요한 credential 부재를 뜻하며, 기존 cache를 offline fixture로 읽는 것을 막지 않는다.
- 신규 synthetic fixture를 쓰는 순수 기술 검증과, 기존 자료를 읽기만 하는 결정론적 재생·해시 검증은 별도 허용 범위와 산출물 경로를 정한 뒤 수행할 수 있다. 이들은 데이터 적격성이나 전략 성과를 입증하지 않는다.
- 달력 스트레스 successor는 이미 완료됐고 해당 작업에서 테스트 18개가 통과했다. 같은 구현·검증을 반복하지 않는다.
- 앞선 focused pipeline/held-band 실행은 58개 통과, 1개 기존 frozen-v1 variant SHA 불일치였다. 이는 알려진 역사 고정값 불일치다. 고정 SHA를 현재 코드로 갱신하거나 검증을 약화하지 않는다.
- `market_research_cli status`의 approximate 검사는 실행 당시 CWD의 `approximate-market-data.json`을 확인한다([CLI 구현](../../backend/jusik/market_research_cli.py#L285)). 해당 파일이 없거나 준비되지 않았다는 결과는 그 파일의 상태만 말하며 모든 audit cache가 없다는 뜻은 아니다. 제공된 현재 상태 근거상 KR·US 모두 이 CLI 검사에서 ready가 아니다.

이 결정 문서 작업 범위에는 자료 수집, 네트워크 요청, 성과 실험, OOS 판정, 서비스·DB·runner 변경, PAPER/live 변경 및 주문이 포함되지 않는다. 이는 프로젝트 전체의 금지가 아니다. 기존 cache 품질 조사, 파이프라인·fixture 검증은 별도 bounded 작업의 승인된 범위에서 계속 수행할 수 있다.

## 되돌릴 수 있는 개발 가정

아래 가정은 코드 경로·문서 구조·합성 테스트를 준비하는 데만 쓸 수 있다. 미래 관측, 실제 성과, 연구 적격성 또는 투자 판단의 증거로 승격할 수 없고, formal preregistration의 미결 값을 채울 수 없다.

7개 항목 모두에서 무료 로컬 compute, synthetic fixture, 기존 로컬 자료의 읽기 전용 metadata·회귀 확인을 provisional 기술 기본값으로 계속 진행할 수 있다. 무료 오프라인 source 조사와 기술적 source 선택도 가능하며, 실제 네트워크 수집·필수 권한·credential 접근은 포함하지 않는다. 이 provisional 작업은 사용자 승인이 필요하지 않다. provisional 값은 승인 전 정식 사전등록의 최종 필드로 동결하지 않으며 `execution_allowed=false`를 유지한다. 최종 자료 허용·합격 기준은 mandate 변경 여부와 무관하게 사용자 독립 승인 대상이다. 사용자 승인은 mandate 변경, 신규 투자 정책 동결, 실제 지출·유료 구매, 필수 권한·credential 사용, 정식 사전등록 freeze 및 실험 실행처럼 해당 결정에 승인이 실제 필요한 경우에 한한다. 기존 mandate 안의 가역적 오프라인 개발 기본값은 그 자체로 승인 대상이 아니다.

| 임시 가정 | 허용 범위 | 해제 조건 |
| --- | --- | --- |
| v1 자료와 근사 자료는 비적격 fixture다. | 무료 로컬 fixture를 계속 써서 입출력·회계·회귀·UI의 비적격 표시만 검증한다. 성과 비교, OOS, 후보 선택에는 사용하지 않는다. | 별도 고정한 새 자료 manifest와 최종 등급·자료 허용 기준을 검토한다. 최종 자료 허용·합격 기준은 사용자 독립 승인 후 해제한다. |
| 2%p control과 4%p candidate는 비교 구조 예시다. | 무료 synthetic 경로와 비교 출력 형식을 준비한다. v1 비용·제약·결과는 새 조건으로 복사하지 않는다. | 실행 파라미터와 최종 코드·정책 hash를 연구 검토에서 확인한다. mandate 변경이나 신규 투자 정책이 필요할 때만 사용자 승인을 추가한다. |
| 표본 집계는 독립 거래 세션 수와 유효 band-crossing 기회 수를 함께 보존한다. | 무료 offline counter, 누락 사유, fold 배분 형식을 계속 구현한다. 숫자 기준이나 충분성 판정은 두지 않는다. | 자료 열람 전 수치 최소 기준과 적격성 판정 규칙을 동결한다. 신규 투자/자료 합격 기준이면 사용자 승인 후 해제한다. |
| 평가 단계는 시간 순으로 분리한다. | 무료 synthetic 상태 전이로 IS → 별도 validation → chronological walk-forward → 1회 untouched OOS 순서만 검증한다. 날짜는 설정하지 않는다. | preregistration freeze 시각, 그 이후의 적격 관측, 접근 통제와 경계를 연구 검토에서 고정한다. 정식 실행에는 별도 사용자 실행 승인이 필요하다. |
| 요구수익률 지표 후보는 비용 차감 CAGR의 2%p control 대비 증가분이다. | 무료 문서·화면에서 비확정 metric 후보로만 검토한다. 수치와 기간은 비운다. | 값·단위·horizon이 신규 투자 정책 또는 합격 기준을 만들면 사용자 승인 후 동결한다. 기존 mandate를 바꾸지 않는 나머지 계산 세부는 연구 검토 대상이다. |
| 자료·계산·산출물·평가 예산은 각각 분리해 기록한다. | 무료 offline schema와 미설정 fail-closed 검증을 계속 준비한다. 임의 한도나 실행은 만들지 않는다. | 유료 구매·실제 지출이 있으면 그 지출에 사용자 승인을 받는다. 지출이 없는 무료 로컬 한도는 승인 없이 provisional 설정할 수 있다. 최종 budget은 명시적으로 승인된 preregistration freeze에서 확정한다. |

## 결정별 권고와 차단 조건

아래 7개 결정은 권고가 있어도 미해결이다. 각 대안의 결과와 임시 사용 가능성을 명시한다. 어떤 임시 가정도 승인된 등록 값으로 간주하지 않는다.

### 1. 자료 등급

- **권고:** v1 및 기존 근사 입력은 regression/debug 전용으로 고정한다. 무료 오프라인 조사로 source metadata와 등급 후보를 계속 검토할 수 있다. 성과 검증을 재개하려면 관측 시점별 universe와 가격·기업행동·환율의 point-in-time(PIT) 가용성을 증명하는 자료 등급을 먼저 선택한다. 엄격한 PIT·생존/상장폐지·배당 증명이 현재 확보됐다고 주장하지 않는다.
- **근거:** v1은 이미 알려진 후향 결과이며 PIT가 검증되지 않았다. 2026-09-08 이후 호환 관측은 찾지 못했다([v1 결과](portfolio-held-band-interaction-v1.md), [v2 준비 기록](../development-records/2026-09-27-held-band-preregistration-preparation.md)). mandate는 무료 근사 자료를 개인 판단 참고로만 허용하고 strict PIT 검증으로 표시하지 않는다([mandate](../research-mandate.md), [시장 연구 계약](../market-research.md)).
- **대안과 영향:** 근사 등급을 선택하면 bounded한 개인 판단용 표본은 가능하지만 strict PIT·승격 근거가 되지 않는다. strict PIT를 요구하면 적격 자료가 확보되기 전 실행은 차단된다. 등급 미지정은 적격성을 판단할 기준 자체가 없어 차단된다.
- **임시 적용:** 가능—무료 로컬 fixture/debug 작업을 계속한다. 어떤 성과 해석에도 적용 불가.
- **사용자 승인:** provisional source 조사와 기술적 등급 후보 검토에는 불필요하다. 최종 자료 허용·합격 기준은 기존 mandate 변경 여부와 무관하게 사용자 독립 승인을 받는다.
- **해제 조건:** 등급 정의, 필드별 시점·출처·누락 한계를 제안하고 최종 자료 허용·합격 기준에 대한 사용자 독립 승인을 받는다. 허용 기준과 source/schema 검증 계약은 formal preregistration freeze 전에 고정한다.

### 2. 시장과 universe

- **권고:** KR 또는 US를 임의로 선택하지 않는다. held-band가 적용될 자산 scope부터 확인한다. stocks/universe를 선택하면 mandate의 날짜별 종목 재발굴·eligible membership 규칙이 그 scope에 적용되는지 검토한다. ETF·현금 등 다른 자산을 선택하면 기존 mandate 근거와 비교 가능성을 따로 검토하며 주식 규칙을 자동 적용하지 않는다. 현재 후보를 과거에 소급하지 않는다.
- **근거:** mandate의 시장 PIT 계약은 날짜별 eligible 주식 universe 재발굴 및 ETF 제외를 정하지만, held-band v2의 대상 scope와 시장 선택은 미정이다. 이를 모든 held-band 자산의 규칙으로 확대할 근거는 없다. 기존 입력 16개 종목은 대표 universe나 표본 충분성을 증명하지 않는다.
- **대안과 영향:** KR 주식 단독은 KRX 입력 준비와 해당 PIT 규칙 적용 여부 확인에 의존하며 미국 FX 없이 시작할 수 있다. US 주식 단독은 날짜별 listing status와 PIT 환율·기업행동이 필요하다. 두 시장 동시 실행은 별도 계정·입력·결과를 유지해야 하므로 자료·계산 예산이 늘어난다. ETF·현금 포함 scope는 자산별 membership·가격·평가 계약을 별도로 정의해야 한다. 현재 보유 목록만 사용하는 선택은 해당 scope의 대상 모집단을 과거 시점에 대표한다는 증거가 필요하다.
- **임시 적용:** 가능—무료 synthetic market·asset 식별자 및 v1 fixture로 계속 개발한다. 시장 간 성과를 합치거나 실제 universe로 부를 수 없다.
- **사용자 승인:** provisional 식별자와 무료 offline 기술 검토에는 불필요하다. 최종 자료 허용·합격 기준은 별도 사용자 독립 승인을 받으며, 신규 투자 정책 또는 mandate 변경도 사용자 승인 대상이다.
- **해제 조건:** 선택 scope에 맞는 시장·자산, (주식이면 적용 가능 여부 검토 후) membership 출처·시점, 표본 설계와 제외 기준을 자료 평가 전에 제안한다. 해당 자료 허용 기준은 사용자 독립 승인을 받고 preregistration freeze 전에 고정한다.

### 3. 자료 출처

- **권고:** 후보 출처별 역할과 시점 증명을 정한다. KR 공식 일별 주식 자료는 KRX API 이용 자격·서비스 승인과 날짜별 universe 근거를 확인해야 한다. US 후보로 Alpha Vantage의 날짜 지정 listing/delisting, 일봉 출처, 그리고 환율 vintage를 검토할 수 있으나 조합만으로 PIT를 보장하지 않는다. 제공자별 원문·수집 시각·관측 가용 시각·hash와 결측 정책을 기록한다.
- **근거:** KRX 안내는 로그인 후 인증키 신청 및 관리자 승인, API 활용 신청 후 승인 대기를 명시한다([KRX 이용 방법](https://openapi.krx.co.kr/contents/OPP/INFO/OPPINFO003.jsp)). KRX 서비스 목록은 주식 일별매매정보를 2010-01-04부터 제공한다고 안내한다([KRX 서비스 목록](https://openapi.krx.co.kr/contents/OPP/INFO/service/OPPINFO004.cmd)). Alpha Vantage는 API key를 요구하고, 2010-01-01 뒤의 지정 날짜 기준 active/delisted 목록 조회를 문서화한다([공식 문서](https://www.alphavantage.co/documentation/)). FRED API 요청은 등록 계정으로 발급받는 API key를 요구한다([FRED API key](https://fred.stlouisfed.org/docs/api/fred/v2/api_key.html)). 로컬 KRX smoke는 인증 거부였고, 기존 US 시도는 FRED 최신 vintage가 과거 세션 전 가용성을 증명하지 못해 `insufficient`였다([2026-09-15 기록](../development-records/2026-09-15-market-data-live-contract-fixes.md), [2026-09-22 기록](../development-records/2026-09-22-r1-bounded-us-collection.md)).
- **대안과 영향:** KRX 공식 출처는 적절한 시계열 후보지만 인증·승인 및 universe 완전성 확인이 선행된다. Alpha Vantage의 과거 listing 상태는 후보 근거지만 독립된 시점별 가격·기업행동·환율 근거를 대체하지 않는다. 현재 자료를 유지하면 fixture에 머문다. 공급자 응답을 합치면 provenance 및 충돌 정책까지 고정해야 한다.
- **임시 적용:** 가능—무료 공식 문서·기존 metadata 조사와 오프라인 기술 source 선택을 계속한다. 실제 수집·네트워크·credential 사용은 하지 않는다.
- **사용자 승인:** 무료 오프라인 source 조사·기술 선택에는 불필요하다. 최종 자료 허용·합격 기준은 사용자 독립 승인을 받는다. 실제 지출·유료 구매 및 필수 권한·credential 제공/사용도 실행 전에 별도 승인받는다.
- **해제 조건:** 최종 자료 허용·합격 기준을 사용자 독립 승인받고 preregistration freeze 전에 source/schema 검증 계약을 고정한다. 정식 자료 수집에는 필요한 접근 권한을 확보하고, 시점 범위와 coverage·기업행동·FX 검증을 통과한 secret-free 자료 manifest를 만든다. 인증키 자체는 문서나 manifest에 기록하지 않는다.

### 4. IS·validation·walk-forward·OOS 경계

- **권고:** 제한 IS, 별도 validation, chronological walk-forward fold, 1회 untouched OOS를 시간 순으로 고정한다. v1 종료일 뒤라는 사실만으로 OOS 적격성이 생기지 않는다. preregistration freeze 전에 source·schema·universe·range rule·exposure/access controls·analysis contract와 code/policy identity를 고정하고, 그 freeze의 정확한 timestamp를 기록한다. 미래 data manifest hash는 freeze 전에 요구하지 않는다. freeze 후 OOS 관측을 격리 수집하고, 결과를 열기 전에 data manifest와 artifact hash를 검증·봉인한 뒤 단 한 번 평가한다. freeze 전 관측 또는 노출·격리 실패 관측은 최종 OOS에서 제외한다. 실제 신규 적격 자료가 없으므로 날짜는 선택하지 않는다.
- **근거:** v2 JSON은 각 경계를 `null`로 두고 v1 결과가 이미 알려졌다고 명시한다. v1 자료는 2023-09-09~2026-09-08이며 후향/PIT 미검증이다. 2026-09-08 뒤 호환 관측이 발견되지 않았고, 그 이후라는 날짜만으로 freeze 이후 생성·비노출·접근 통제 상태를 입증할 수 없다. mandate는 독립 validation, chronological walk-forward, one-time untouched OOS를 요구한다.
- **대안과 영향:** 더 긴 IS는 개발 표본을 늘리지만 미래의 untouched 구간을 침범하면 재사용할 수 없다. validation을 fold 선택이나 tuning에 반복 쓰면 최종 OOS 독립성이 줄어든다. 날짜 미정 상태로는 실행 시작점을 검증할 수 없다.
- **임시 적용:** 가능—무료 synthetic 상태 전이와 접근 통제 검사를 계속한다. 날짜·기간·fold 수 및 OOS eligibility는 임시로 동결하지 않는다.
- **사용자 승인:** 오프라인 설계·fixture에는 불필요하다. 정식 preregistration freeze와 성과 실행은 각각 명시적 사용자 승인이 필요하며 위임 승인으로 대체하지 않는다.
- **해제 조건:** freeze 전 analysis contract 및 code/policy identity를 포함한 설계값을 고정하고 preregistration freeze의 명시적 사용자 승인을 받는다. freeze 후 신규 OOS 관측을 격리 수집하고, 결과를 열기 전에 자료 manifest·artifact hash를 검증해 봉인한다. 관측 시점·실제 수신 시점·노출·접근 기록을 보존하고, freeze 전 또는 노출된 관측은 OOS에서 제외한다.

### 5. 최소 표본

- **권고:** 표본 단위는 **독립 거래 세션 수**와 **적격 band-crossing 기회 수**를 함께 세고 둘 다 통과해야 하는 구조로 정한다. 숫자는 데이터를 열람하거나 후보 성과를 평가하기 전에 근거를 들어 고정한다. 표본 숫자를 v1의 7 folds·32회 실행·16개 입력에서 추론하지 않는다.
- **근거:** v1은 고정 후향 실행의 반복 횟수이지 독립 세션/기회 수의 충분성 근거가 아니다. v2는 `minimum_sample`을 미정으로 둔다. 미래 자료도 아직 없다.
- **대안과 영향:** 세션만 세면 비교 대상인 재배분 기회가 거의 없는 표본도 충분하다고 오판할 수 있다. 기회만 세면 같은 시장 국면에 몰린 의존 관측을 독립 증거로 과대평가할 수 있다. 표본을 계속 늘리면 불확실성은 줄 수 있지만 새 자료·계산·평가 예산과 OOS 노출 부담이 커진다.
- **임시 적용:** 가능—무료 offline 두 카운터와 fold별 분포를 계속 기록한다. 수치 기준·통과 판정은 불가.
- **사용자 승인:** 단순 집계·provisional counter는 불필요하다. 최종 표본 최소값이 최종 자료 합격 기준이면 사용자 독립 승인을 받는다. 신규 투자 정책이면 그것도 승인받는다.
- **해제 조건:** 등록 전 blind 설계 근거와 함께 최소 세션·최소 기회·fold 분포 조건을 제안하고, 최종 자료 합격 기준으로 사용자 독립 승인을 받는다. 각 단계의 적격 자료가 기준을 충족하지 못하면 성과값 없이 불충분으로 종료한다.

### 6. 후보별 요구수익률

- **권고:** 후보의 요구수익률 지표 후보는 비용 차감 CAGR의 2%p control 대비 증가분으로 둔다. 이 지표의 값과 평가 horizon은 미정으로 유지하고, 비용 차감 MDD·Sharpe·Calmar와 MDD 20% hard filter를 별도로 표시한다. Control 대비 비교는 후보의 최소 수익 요구를 대체하지 않는다.
- **근거:** v2는 proposed 4%p 후보와 2%p control을 두고 후보별 metric·value·horizon을 null로 둔다. mandate는 balanced objective와 비용 차감 4개 primary metrics, 별도 MDD filter를 지정한다. v1 통계는 새 요구수익률의 근거가 아니다.
- **대안과 영향:** 순수익률 차이를 요구하면 비용·규모효과와 통합 정의가 겹치거나 비용 민감도를 숨길 수 있다. 절대 CAGR hurdle은 control 대비 효과와 목표 절대 수익을 함께 요구할 수 있지만 별도 근거가 필요하다. metric만 정하고 숫자·horizon을 생략하면 진행 기준이 없어 실행 전 차단된다.
- **임시 적용:** 가능—무료 문서·화면에서 비용 차감 CAGR 차이를 토론용 후보로 계속 표시한다. 수치·horizon·합격 판정에는 적용 불가.
- **사용자 승인:** provisional metric에는 불필요하다. 최종 metric·value·horizon이 신규 투자 정책을 만들면 사용자 승인을 받는다. 최종 자료 합격 기준에도 쓰이면 사용자 독립 승인을 받는다.
- **해제 조건:** 독립 근거를 정리하고 값·단위·비용 가정·horizon·실패 시 단계 중단을 제안한다. 신규 투자 정책이면 사용자 승인, 자료 합격 기준이면 사용자 독립 승인을 받은 뒤 preregistration freeze 전에 고정한다. 결과를 본 뒤 기준을 고치지 않는다.

### 7. 실행 예산

- **권고:** `compute_budget`, `data_budget`, `artifact_budget`, `evaluation_budget`을 서로 분리해 한도·측정 단위·초과 시 fail-closed 동작을 정한다. 수치는 추론하지 않는다. 예산은 각 단계와 후보 최대 3개 제한을 반영하고, 승인 없는 추가 결제·원격 compute 없이 완결 가능해야 한다.
- **근거:** v2의 네 예산 항목은 모두 `null`이다. mandate는 bounded compute/data/artifact budget을 실행 전에 요구한다. 자료 수집과 계산량은 시장·기간·표본·fold 수에 따라 달라지며 그 입력 자체가 미정이다.
- **대안과 영향:** 지나치게 낮은 한도는 적격 표본 확보 전 중단을 유발한다. 넓거나 무제한인 한도는 비용·재현성·탐색 폭을 통제하지 못한다. 요청 수만 제한하면 저장 공간·산출물·평가 횟수를 막지 못한다. 큰 총액 한도 하나로 합치면 어떤 자원이 소진됐는지 감추고 단계별 중단을 어렵게 한다.
- **임시 적용:** 가능—네 한도를 구분하는 무료 offline schema와 로컬 fixture 한도를 계속 준비한다. 임시 숫자는 정식 사전등록 필드로 복사하지 않는다.
- **사용자 승인:** 무료 로컬 compute와 synthetic fixture의 가역적 provisional 한도 설정에는 불필요하다. 실제 지출·유료 구매·유료 compute가 있을 때만 해당 지출에 대한 승인을 받는다. 최종 preregistration freeze와 실험 실행은 각각 명시적 사용자 승인이 필요하다.
- **해제 조건:** 시장·자료·기간·최소 표본·후보 수가 정해진 뒤 각 예산의 수치·단위·초과·재시도·중단·보존 정책을 제안한다. 무료 작업만 있으면 지출 승인 단계는 생략한다. 유료 지출이 있으면 실제 지출 전에 승인받는다. 최종 budget은 사용자 승인된 preregistration freeze에서 고정하고, 별도 정식 실행 승인 전에는 실험을 실행하지 않는다.

## 연구 재개 공통 게이트

아래 조건을 모두 만족하기 전까지 v2는 draft로 남기고 어떠한 성과 실험도 실행하지 않는다.

1. 신규 held-band 호환 관측의 provenance·시점 가용성·등급·scope·노출 상태를 확인한다. v1 종료일(2026-09-08) 뒤의 관측은 후보가 될 수 있지만 그것만으로 OOS 적격은 아니다.
2. freeze 전에 source·schema·universe·range rule·exposure/access controls·analysis contract와 code/policy identity를 고정한다. 미래 OOS data manifest/artifact hash는 아직 요구하지 않는다. 최종 자료 허용·합격 기준은 사용자 독립 승인을 받는다.
3. 사용자가 직접 승인한 뒤 formal preregistration을 freeze하고 정확한 timestamp를 기록한다. 위임 승인으로 대체하지 않는다. freeze 전에 생긴 관측은 최종 OOS에서 제외한다.
4. freeze 후 v1 종료일 뒤의 새 eligible OOS 관측을 격리해 수집한다. 결과나 파생 정보를 열기 전 manifest·artifact hash를 검증하고 봉인한다. 노출됐거나 출처·수신 시점·접근 격리가 입증되지 않는 관측은 OOS에서 제외한다.
5. 봉인 후에만 OOS 결과를 단 한 번 평가한다. 별도 정식 실행 승인을 사전에 받는다. 이는 PAPER/live나 자동 승격 승인이 아니며, 그 결정은 계속 별도 절차에 둔다.

현재 차단은 신규 적격 관측 부재, 등급·market·asset scope·source·기간 미결정, IS/validation/walk-forward/OOS와 freeze·노출·접근 경계 및 최소 표본 미결정, 후보별 요구수익률, 네 예산, 최종 hash 미결정이다. 기술적인 무료 오프라인 개발은 계속 가능하다. 위 차단 해제 후에도 투자 성과나 strict PIT 적격성을 미리 보장하지 않는다.
