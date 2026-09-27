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

- **권고:** 후보 출처별 역할과 시점 증명을 정한다. KR 주식 scope가 선택되면 KRX Open API를 일별 가격의 우선 조사 후보로 둔다. KOSPI·KOSDAQ의 과거 전체 universe 출처로는 아직 인정하지 않는다. US 후보 Alpha Vantage는 date-specific listing/delisting 후보이고, 별도 price·corporate-action·FX source와 조합해도 PIT를 보장하지 않는다. 제공자별 원문·수집 시각·관측 가용 시각·hash와 결측 정책을 기록한다.
- **근거:** KRX 서비스 목록은 KOSPI·KOSDAQ 일별매매 및 종목기본정보의 제공 기간을 2010-01-04부터로 표시한다([KRX 서비스 목록](https://openapi.krx.co.kr/contents/OPP/INFO/service/OPPINFO004.cmd)). 이용 절차는 로그인, 인증키 신청·관리자 승인, API별 활용 신청·승인을 요구한다([KRX 이용 방법](https://openapi.krx.co.kr/contents/OPP/INFO/OPPINFO003.jsp)). 약관은 비상업 이용, 제3자 제공 금지, 키당 하루 10,000회 한도와 정확성·완결성·연속 제공 비보장을 명시한다([KRX 이용약관](https://openapi.krx.co.kr/contents/OPP/INFO/OPPINFO002.jsp)). KRX 공개 문서에는 역사적 종목 집합의 공표·수신 시각, 정정 이력 또는 완전성이 확인되지 않는다. Alpha Vantage는 API key와 2010-01-01 이후 날짜별 active/delisted 목록을 문서화한다([공식 문서](https://www.alphavantage.co/documentation/)). FRED API는 등록 계정의 API key를 요구하며, 기존 US 시도에서 FRED 최신 vintage는 과거 세션 전 가용성을 증명하지 못했다([FRED API key](https://fred.stlouisfed.org/docs/api/fred/v2/api_key.html), [2026-09-22 기록](../development-records/2026-09-22-r1-bounded-us-collection.md)).
- **대안과 영향:** KRX는 KR 일별 가격의 공식 출처 후보로 적합하지만, API별 승인·현재 사용 자격·역사적 membership·정정 및 corporate-action 시점 검증이 필요하다. Alpha Vantage의 과거 listing 상태도 당시 이용 가능 시각·수정 이력을 입증하지 않으며, 독립된 시점별 가격·기업행사·환율 근거를 대체하지 않는다. 현재 보유한 approximate 자료는 이미 노출되어 fixture에만 머문다. KRX 데이터상품/분배 경로는 항목별 가격·이용 목적 심사 또는 별도 계약이 필요하므로 비용·권한을 확인하기 전 대체 source로 선택하지 않는다.
- **임시 적용:** 가능—무료 공식 문서·기존 metadata 조사와 오프라인 기술 source 선택을 계속한다. 실제 수집·네트워크·credential 사용은 하지 않는다.
- **사용자 승인:** 무료 오프라인 source 조사·기술 선택에는 불필요하다. 최종 자료 허용·합격 기준은 사용자 독립 승인을 받는다. 실제 지출·유료 구매 및 필수 권한·credential 제공/사용도 실행 전에 별도 승인받는다.
- **해제 조건:** 최종 자료 허용·합격 기준을 사용자 독립 승인받고 preregistration freeze 전에 source/schema 검증 계약을 고정한다. 정식 자료 수집에는 필요한 접근 권한을 확보하고, 시점 범위와 coverage·기업행동·FX 검증을 통과한 secret-free 자료 manifest를 만든다. 인증키 자체는 문서나 manifest에 기록하지 않는다.

#### KRX Open API 공개 자료 후보 검토 (2026-09-27)

- **관찰된 범위:** 공식 목록은 KOSPI·KOSDAQ 주식 일별매매정보와 종목기본정보를 2010-01-04부터, KONEX는 2013-07-01부터, ETF 일별매매정보를 2010-01-04부터 제공한다고 표시한다([KRX 서비스 목록](https://openapi.krx.co.kr/contents/OPP/INFO/service/OPPINFO004.cmd)). KOSPI·KOSDAQ 개별 일별매매 API는 설명상 같은 시작일을 표시하고 최근 수정일은 2026-01-16이다([KOSPI 일별매매정보](https://openapi.krx.co.kr/contents/OPP/USES/service/OPPUSES002_S2.cmd?BO_ID=JvJFzlAENzZlPBDNGAWC), [KOSDAQ 일별매매정보](https://openapi.krx.co.kr/contents/OPP/USES/service/OPPUSES002_S2.cmd?BO_ID=hZjGpkllgCBCWqeTsYFj)). 비로그인 화면에서는 출력 field와 실제 request/response 명세가 렌더링되지 않았다. 신청 화면에는 1·3·6·12개월 기간 선택이 있으나 이는 API 이용신청 UI의 값이다. 조회 가능한 최대 과거 기간이라고 해석하지 않는다.
- **PIT·universe 한계:** 공개 카탈로그의 과거 제공 시작일은 과거 가격 조회 가능성을 나타내지만, 특정일의 당시 전체 eligible 구성종목을 빠짐없이 복원할 수 있다는 보증은 아니다. 화면 설명의 “상장되어 있는 주권” 및 종목기본정보 이력은 상장일·상장폐지일 정의, 보유 이력, 당시 발표·수신 시각, 과거 수정/정정 원본을 입증하지 않는다. 공표·revision timestamp나 완전한 일별 membership 이력이 확인되지 않아 strict PIT·survivorship-free 자료로 인정하지 않는다.
- **사용권·접근 및 비용 영향:** API 사용은 회원 로그인, 인증키 신청과 관리자 승인, 각 API별 활용 신청 및 별도 승인을 요구한다. 약관상 API는 비상업 목적으로만 쓸 수 있고 결과 대가 청구 및 정보의 제3자 제공은 금지되며, 정확성·완결성·지속 제공도 보장하지 않는다. 사용자 연구 목적이 허용 범위에 해당하는지는 확인되지 않았다([KRX 이용 방법](https://openapi.krx.co.kr/contents/OPP/INFO/OPPINFO003.jsp), [KRX 이용약관](https://openapi.krx.co.kr/contents/OPP/INFO/OPPINFO002.jsp)). 별도 데이터상품은 항목별 가격·기간·필드·포맷을 확인해 구매하고 결제 후 사용 목적 심사를 받는 경로다. 데이터 분배/상용 활용은 별도 이용계약이 필요할 수 있다([데이터 구입안내](https://openapi.krx.co.kr/contents/OPP/DATA/OPPDATA001.jsp), [데이터 수신방법](https://openapi.krx.co.kr/contents/OPP/DATA/OPPDATA003.jsp)). 이번 조사에서 가격표의 구체 금액·구매 또는 사용 자격은 확인하지 않았다.
- **기존 프로젝트 자료:** 기존 KRX 공식 읽기 전용 수집 기록은 2025-09-11 응답 960 universe 행 중 무거래 값 31행을 제외해 929 bars를 만들었고, 2025-09-11~2026-09-11 자료 수집은 완료했다. 그러나 approximate pilot은 `insufficient`, `completeness=incomplete`, `readiness.ready=false`였고 수익률·거래 지표를 만들지 않았다. 당시 문서도 전체 기간의 PIT corporate action·배당·상장폐지·관측 시각 근거 부재를 명시한다([KRX smoke 기록](../development-records/2026-09-19-r6-krx-smoke.md)). 이 노출 자료는 오프라인 파이프라인·fixture 검사에만 쓸 수 있다. 최종 성과, OOS, 신규 후보 승인 근거로는 배제한다. 별도 2026-09-15 수집 기록의 API 인증 거부는 별도 시점의 시도이므로 현재 인증 상태를 확정하지 않는다([시장자료 계약 기록](../development-records/2026-09-15-market-data-live-contract-fixes.md)).
- **권고와 대안 영향:** KR 주식 scope가 추후 선택되면 KRX Open API를 KOSPI·KOSDAQ 일별 가격의 첫 공식 후보로 조사한다. historical membership, 상장·폐지 상태 및 시점 provenance가 검증되기 전에는 구성종목 PIT source로 사용하지 않는다. Alpha Vantage는 US scope에서 날짜별 membership 조사 후보로 유지하고, 현재 로컬 cache는 무료 fixture 대안으로만 둔다. KRX 유료 상품·분배 계약은 명세나 이용 권한이 넓을 수 있으나 구매비와 이용 심사가 생기므로 별도 승인 없이는 조사 목록을 넘지 않는다. 시장, 자산군, 최종 provider 또는 자료등급을 선택·동결하지 않는다.
- **임시 적용과 승인:** 가능—KRX의 공개 endpoint 설명·이력 시작일을 source 후보 metadata와 source-agnostic schema 질문에만 provisional로 기록한다. 기존 KRX 자료는 별도 읽기 전용 fixture 작업에서 기술 검증에 사용할 수 있다. key·계정·관리자 승인 및 비상업 이용 자격을 가정하지 않고 실제 API request를 실행하지 않는다. 무료 문서 조사는 사용자 승인이 필요 없다. 최종 data acceptance·market/source 선택은 사용자 독립 승인이 필요하며, 구매·유료 서비스는 실제 지출 전 사용자 승인을 받는다.
- **해제 조건:** 먼저 시장 scope와 자료 허용 기준을 사용자 승인·정식 preregistration 절차에서 확정한다. 이후 API key·서비스 승인과 사용 목적 적합성을 확인하고, 익명 화면에서 노출되지 않은 명세 및 실제 날짜별 응답·coverage·membership/상장폐지·수정·corporate-action provenance를 제한된 기술 수집으로 검증한다. timestamp와 raw receipt hash가 포함된 manifest가 평가 기준을 만족해도 freeze 전 수집 자료는 OOS가 아니다. KRX 수집 자료는 승인된 freeze 이후 새로 격리해 확보하기 전까지 최종 OOS에 사용하지 않는다.

#### Massive 공개 자료 후보 검토 (2026-09-27)

- **관찰된 범위:** 공식 가격표는 Stocks Basic을 월 $0, 미국 주식 종목·reference/corporate-action 자료, EOD 가격과 2년 이력, 분당 5회 호출로 표시한다. Starter는 $29/월·5년, Developer는 $79/월·10년, Advanced는 $199/월·20년 이상이며 모두 개인용으로 표시된다([공식 요금표](https://massive.com/pricing)). ticker reference는 모든 요금제에 포함되며 `active=false`로 비활성/상장폐지 종목을 조회할 수 있다. Ticker Events는 `ticker_change`만 지원하고 예시 응답은 이벤트 `date`를 제공한다. Basic 이력은 2년, 유료 등급은 전체 이력(문서상 2003-09-10부터)이다([ticker reference와 events 설명](https://www.massive.com/docs/rest/stocks/overview), [Ticker Events endpoint](https://massive.com/docs/rest/stocks/corporate-actions/ticker-events), [ticker 변경 설명](https://massive.com/knowledge-base/article/how-does-massive-handle-ticker-changes-and-acquisitions)).
- **PIT 한계:** 공급자 문서는 특정 날짜 기준 ticker reference와 과거 ticker symbol/event 연결을 설명한다. 이 정보는 역사적 symbol 상태·identity 조사에 유용할 수 있지만, 각 값이 당시 시장 의사결정 전에 언제 공개됐는지, 수정·정정 전 원본이 무엇인지, 과거 전체 universe가 완전하게 포함됐는지는 입증하지 않는다. 이벤트 예시에는 적용일 `date`가 있으나 `announced_at`·`observed_at`·`received_at`은 설명되지 않는다. 상품 페이지의 생존자 편향 없음 주장은 추가 독립 검증 없이 strict PIT 증거로 승격하지 않는다([상품 설명](https://www.massive.com/stocks)).
- **사용권과 비용 영향:** Market Data Terms는 기본 시장자료 권리를 개인·비사업·비상업 용도로 제한하고, 데이터 기반의 비표시 사용 또는 투자전략 등 파생물 작성은 별도 허가 없이 금지한다고 적는다. 따라서 기본 개인 요금제의 데이터는 이 전략 연구·백테스트에 적격하다고 볼 수 없다. 유료 개인 요금제도 이 제한을 해소한다고 문서화돼 있지 않다. 실제 사용 전에 연구 목적의 비표시 분석과 전략 파생물 작성을 명시적으로 허용하는 별도 계약·서면 허가가 확인돼야 한다([Market Data Terms](https://massive.com/legal/market-data-terms-of-service)).
- **권고와 대안 영향:** 현재 Massive를 정식 source로 채택하지 않고, 공개 문서에서 확인되는 endpoint/필드만 source 후보 조사 및 source-agnostic schema 설계의 참고로 둔다. 제한된 문서상 interface는 기존 자료 없이도 기술적으로 검토할 수 있지만, 실제 자료를 요청·저장·분석하는 경로는 사용권 확인 전 차단한다. 이후 허가가 확인돼도 그 자료는 곧바로 적격 PIT가 되지 않는다. KR scope는 KRX 승인·coverage 조사 경로를 계속 검토하고, US scope는 Alpha Vantage 및 독립 FX/vintage 조합의 한계를 포함해 비교한다. 어느 시장에서도 현재 자료 출처 권고를 최종 선택으로 간주하지 않는다.
- **임시 적용과 승인:** 가능—공개 문서로 candidate metadata와 검증 질문을 provisional로 기록하고 synthetic/offline schema 테스트를 계속한다. 실제 API 호출은 계정 credential과 약관상 허용 범위가 필요하며 아직 진행하지 않았다. 유료 요금제·허가 계약의 실제 지출은 사용자 승인 대상이다. 최종 source/data allowlist 및 합격 기준도 사용자 승인 전 동결하지 않는다.
- **해제 조건:** vendor의 현재 원문 계약 또는 별도 서면 허가가 비표시 연구·백테스트 및 해당 결과물 사용을 명시적으로 허용하고, 필요한 credential/비용 승인을 받은 뒤에만 실제 접근 검토를 시작한다. 별도 검증에서 timestamped publication/availability·revision provenance·과거 membership coverage·corporate action 범위·수정 정책을 확인하고, 사용자 승인 최종 자료 기준과 대조하기 전까지 `FINAL_VALIDATION`/OOS에는 쓰지 않는다.

#### Alpha Vantage 공개 자료 후보 검토 (2026-09-27)

- **관찰된 범위:** 공식 `LISTING_STATUS`는 미국 주식·ETF의 active/delisted 목록을 현재 또는 날짜 지정 상태로 반환하며, 날짜는 2010-01-01 이후를 지원하고 API key가 필요하다. 일별 raw 시계열은 25년 이상을 설명하지만 무료 key의 기본 `compact`는 최근 100거래일만 반환하고, `full` 전체 이력은 premium이다. Split/dividend 조정 일별 API와 과거 corporate-action 내용도 25년 이상을 표방하지만 premium endpoint다([API 문서](https://www.alphavantage.co/documentation/)). Free service는 대부분 dataset에 하루 25회이며, verified open-source/educational project만 무제한 사용 가능하다고 안내한다. 이 프로젝트가 예외 대상인지는 미확인이다([공식 지원·rate limit](https://www.alphavantage.co/support/)). Premium 안내는 요금제 선택과 결제를 요구하지만 이번에 확인한 공개 정적 문서에는 금액이 표시되지 않아 비용을 추정하지 않는다([Premium API 안내](https://www.alphavantage.co/premium/)).
- **사용권 범위:** Terms는 개인·비상업 사용을 허가하며 private individual nature의 투자분석·연구·테스트·모니터링을 허용 범위 예시로 둔다. 사용 목적이 이를 넘어가거나 법인·단체를 대신해 사용하거나, 제3자가 정보를 이용하거나, 금융기관과 관련된 사용자가 접근하는 경우 commercial use로 정의하고 문의하도록 한다. 따라서 이 API는 해당 조건을 충족하는 개인 연구에 대해 Massive의 기본 market-data 약관과 달리 명시적인 검토 후보가 될 수 있다. 실제 사용자의 자격·사용 목적은 확인되지 않았으며 임의로 개인용이라고 간주하지 않는다([Terms of Service](https://www.alphavantage.co/terms_of_service/)).
- **PIT·자료 한계:** 특정일 active/delisted 목록은 date-specific universe 재구성 후보로 유용하다. 그러나 API 문서는 역사적 listing 상태를 설명할 뿐, 그 상태·가격·조정 이벤트가 당시 투자 시점 전에 공개·관측된 시각, 과거 수정/정정 버전, 당시 전체 universe의 완전성을 설명하지 않는다. 현재 반환되는 조정계수·시계열과 dividend/split event를 과거 당시의 가용 정보로 취급할 수 없다. 날짜 질의만으로 strict PIT가 증명되지 않는다.
- **권고와 대안 영향:** US 선택 시 Alpha Vantage를 *과거 membership 조사 우선 후보*로 두고, 2010년 이후 날짜별 listing coverage·제외/정지 상태를 실제 검증할 가치를 조사한다. 이 우선순위는 기술·조사 provisional이며 최종 source 선택이 아니다. 무료 한도는 여러 종목의 장기 daily bars·조정 이벤트를 채우기 어렵고 핵심 `full` 이력이 premium이므로, 가용 범위로 즉시 전략을 시험하지 않는다. 유료화하면 비용이 발생하고 데이터 허용도 자동 승인되지 않는다. 별도 가격·기업행동·FX source와 조합하면 provenance·시점·불일치 검증 부담이 늘어난다. KR scope이면 KRX access/coverage 조사가 우선이며, Massive는 현재 사용권 제약 때문에 보조적인 공개 문서 후보로 남긴다.
- **임시 적용과 승인:** 가능—공식 field·`LISTING_STATUS` 날짜 의미, free/premium endpoint 경계를 문서 및 source-agnostic schema 설계에 provisional로 반영하고 synthetic/offline fixture를 계속한다. 실제 응답은 API key와 약관 적격성 검토 전 사용하지 않는다. 계정/API key는 무료여도 사용자 credential·계정 영역이므로 자동 생성·접근하지 않는다. premium subscription의 실제 비용 및 commercial license는 사용자 승인 대상이다. 최종 시장/universe/source, PIT/data acceptance, 사전등록 조건은 그대로 미정이다.
- **해제 조건:** 사용 목적이 현재 Terms의 private individual non-commercial 범위인지 확인하고, API key를 안전하게 제공받은 경우에만 bounded 접근성·coverage 검사를 계획한다. 상업·기관 사용은 provider와 조건/비용을 확인한다. 반환된 membership/bar/action/FX를 시점·수정 이력·범위별로 검증해 secret-free manifest로 남기고, 사용 전 사용자 승인 최종 자료 기준과 대조한다. 이 절차를 통과하기 전 `FINAL_VALIDATION`/OOS 사용은 허용하지 않는다.

#### 기존 US approximate cache의 offline fixture profile (2026-09-27)

- **관찰:** 2025-09-11~2026-09-11 요청은 272개 세션을 대상으로 합니다. 전체 요청 coverage의 27,472 expected는 diagnostics의 101개 고유 심볼×272로 계산됩니다. diagnostics상 25개 제외 심볼의 expected 6,800개를 빼면 포함 universe의 20,672개 중 20,306 bars가 있어, membership bar 결손은 366개입니다(LIME 221, MDA 145). 별도 98 bars는 PTN이며 matching universe row가 없어 합치지 않습니다. 제외 이유는 `unknown` 56, `parse` 3, `identity_mismatch` 2, `partial_history` 2입니다.
- **100 대 101 대조:** completion marker `sample_size=100`은 listing checkpoint별 선택 cap입니다. 보존된 두 Alpha listing snapshot의 결정적 재생은 checkpoint마다 100개를 고르고, 두 번째에서 기존 99개를 유지하며 새 심볼 1개를 추가합니다. 누적 집합 101개는 diagnostics 101개와 sorted-set SHA까지 일치합니다. 기존 collector는 checkpoint별 100개 표본과 누적 최대 400개 source symbol을 따로 둡니다([선택 로직](../../backend/jusik/market_data_collector.py#L2402), [정규화 정책 metadata](../../backend/jusik/market_history_approximate.py#L553), [mandate](../research-mandate.json#L63)). 따라서 같은 checkpoint에서 101개를 선택한 결과가 아닙니다. 기존 audit은 당시 request identity만으로 차이를 설명하지 못했으나, 현재 보존 snapshot·source 재생으로 이 집계 메커니즘을 재현했습니다([기존 audit 기록](../development-records/2026-09-22-roadmap-r1-05-cached-receipt-reconciliation-v1.md), [이번 재현 audit](../development-records/2026-09-27-held-band-sample-size-identity-reconcile.md)).
- **적용 한계:** 100-per-checkpoint/400-cumulative 해석은 기존 pipeline 재현용 provisional assumption입니다. 원 result·completion marker에는 실행 code SHA가 없고 당시 cache manifest 137개 항목에도 `request_descriptor`가 없어 정확한 runtime checkout identity는 입증되지 않습니다. 이 해석을 preregistration sample field나 최종 합격 기준으로 동결하지 않습니다. 전체 연구기간 고유 종목 100개를 뜻하는 해석도 임의 적용하지 않습니다. 최종 자료·표본 기준 또는 mandate 변경은 별도 승인·정식 freeze 전까지 미정입니다.
- **기본 품질과 provenance:** universe 20,574행, bars 20,306행, FX 272행의 중복 key/session은 없고 OHLC 오류·결측 수치·음수 volume도 확인되지 않았습니다. FX 날짜와 timestamp 272행은 parse 가능하며 duplicate session은 없습니다. 그러나 action 121행(배당 111, split 10)은 모두 `observed_at`이 비어 있습니다. universe·bar·FX의 `available_at` 값은 parse 가능해도 공급자 publication timestamp가 아닙니다. collector는 Alpha listing을 역사적 checkpoint 시장 종가로 ([collector](../../backend/jusik/market_data_collector.py#L2380)), Yahoo bars를 각 시장 session 종가로 ([collector](../../backend/jusik/market_data_collector.py#L2671)), FRED FX vintage를 vintage 날짜 다음 날 자정으로 ([collector](../../backend/jusik/market_data_collector.py#L2873)) 표시합니다. approximate provider의 fallback도 session 종가 convention을 씁니다([normalizer](../../backend/jusik/market_history_approximate.py#L889)). 이 시각들은 PIT publication·수정 이력을 입증하지 않습니다.
- **기존 listing receipt:** 2026-09-22에 저장된 Alpha Vantage 날짜별 listing 응답은 HTTP 200, 25개 요청 중 24개 일치·1개 미일치, 일반 행 6,466개와 제외 5개입니다. receipt의 `observed_at`은 실제 시각이 아니라 “provider publication timestamp unavailable”라는 문구입니다. 과거 날짜 기준 응답을 나중에 저장한 자료이므로 당시 공개·관측 증거가 아닙니다.
- **재현·허용 범위:** 원문 137개는 manifest content hash와 일치하고 결과 hash는 completion marker와 일치합니다. 외부 profile `/home/kwl/.local/share/jusik/portfolio-audit/20260927-held-band-local-cache-profile/profile.json`의 SHA-256은 `495e363ebd37fdc7bcbe7f82974df76219b8b995cfed77061adc0aa323723e8e`입니다. 이 자료는 이미 노출된 근사치라 parser·coverage·결손 표시·회귀 fixture를 확인하는 provisional 개발 용도에만 허용합니다. 성과, strict PIT, source/data acceptance, OOS, 후보 승인 또는 실거래 근거로 사용하지 않으며 원본 cache는 변경하지 않았습니다.

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
