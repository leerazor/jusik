# Held-band 결정 준비와 자료 가용성 점검

- 상태: 완료 (권고 문서 준비; preregistration freeze·성과 검증은 미완료)
- 기록 시각: 2026-09-27T02:27:15Z
- 작업 slug: `portfolio-held-band-decision-preparation-v1`
- 기준/통합: `05569736aad06ba67f7d100e2803f65539ee3622` / `bf18fb6d35604323f81548bd55fe68407df69c24` (local `main`, fast-forward)
- 범위: 기존 mandate와 agent orchestration을 유지하면서 7개 미정 결정을 근거·대안·가역적 provisional 범위·승인 필요·해제 조건으로 정리했습니다. 현재 자료 후보의 품질도 오프라인으로 확인했습니다.

## 변경과 권고

- [결정 준비 문서](../research/portfolio-held-band-decision-preparation-v1.md)는 자료 등급, market/universe, source, IS/validation/walk-forward/OOS, minimum sample, candidate hurdle, budget을 권고와 절충 영향으로 정리합니다. 숫자·정책·최종 자료 허용 기준을 임의 동결하지 않습니다.
- 무료 로컬 compute, synthetic fixture, 기존 local cache metadata·회귀 점검은 provisional 기술 작업으로 계속 허용합니다. v1 및 approximate 자료는 개발/debug/fixture 용도로만 씁니다. OOS·final performance·candidate acceptance·실거래 승인에는 사용하지 않습니다.
- 최종 자료 허용·합격 기준, 새 투자 기준, preregistration freeze에는 사용자 승인이 필요합니다. 실제 유료 data/compute·credential/access도 해당할 때 승인을 받아야 합니다. `docs/research/portfolio-held-band-preregistration-draft-v2.json`의 미결 field 20개는 모두 `null`; `registered`, `approved`, `execution_allowed`는 계속 `false`입니다.
- OOS protocol은 freeze 전 source/schema/universe/range/exposure/access/analysis contract를 고정합니다. 사용자가 freeze를 승인한 뒤 future observations를 격리 수집하고, 결과를 공개하기 전에 data manifest/artifact hash를 봉인한 뒤 단회 평가합니다. v1 종료일 이후라는 사실만으로 OOS 적격이 되지 않습니다.
- 로컬 US approximate 100-symbol cache (`/home/kwl/.local/share/jusik/portfolio-audit/20260922-us-vintage-collection-100`)는 fixture 후보입니다. 요청 기간은 2025-09-11~2026-09-11, 고유 종목은 76개, bars는 20,306/27,472개라 7,166개가 빠졌습니다. 25개 종목이 제외됐고 원인은 `unknown=56`, `parse=3`, `identity_mismatch=2`, `partial_history=2`입니다. 배당/split event 121행에는 `observed_at`이 없습니다. 결과 SHA-256은 `a42fd8b4f53f1f05f39637dcff34806fa0fad17de6ad467acc40e0ae2a11ed7f`, cache manifest SHA-256은 `361e8de4fbdc8e66cc683a09109ac980ba5045991a65d93c5315b7dcd142c759`입니다. Cache는 2026-09-24에 수집·완료되어 승인된 freeze보다 앞섭니다. 따라서 OOS나 최종 자료 허용 근거가 될 수 없습니다.
- API key 환경변수를 명시적으로 unset하고 completed marker가 지정한 output path로 실행한 read-only `collect-status`는 `completed=true`, entries 137개, `ready=false`를 반환했습니다. 누락 key는 `ALPHA_VANTAGE_API_KEY`, `FRED_API_KEY`입니다. 이는 현재 환경에서 새 수집을 막지만 기존 cache의 오프라인 조회는 막지 않습니다. Cache와 output은 변경하지 않았습니다.
- Provider 근거: KRX API는 로그인·key 신청·관리자 승인이 필요합니다. Alpha Vantage는 API key를 요구하고 날짜별 active/delisted 목록을 문서화합니다. 기존 free-key full-history 요청은 유료 기능 안내만 반환했습니다. FRED API도 등록 key가 필요합니다. 제공자 조합만으로 strict PIT가 입증되지는 않습니다. 공식 문서와 기존 source 기록은 결정 문서에서 연결했습니다.
- 추가 무료 후보 조사: Nasdaq Data Link는 제품별 데이터 접근·가격과 인증 조건을 확인해야 하는 플랫폼이며, legacy 문서에선 free dataset도 key와 호출 한도를 두고 bulk download는 API key를 요구합니다. 공식 문서는 2026-08-31 이후 구 문서 교체를 안내하므로 특정 상품을 지정하기 전에는 최신 entitlement를 확정할 수 없습니다([Data Link 인증](https://docs.data.nasdaq.com/docs/r-installation), [bulk download 조건](https://docs.data.nasdaq.com/docs/large-table-download)). SEC의 ticker/exchange association 파일은 현재 issuer 식별 연결용 보조 자료지만, SEC가 주기적으로 갱신하며 정확도·범위를 보장하지 않는다고 밝혀 historical universe나 가격 PIT source로 쓸 수 없습니다([SEC EDGAR data access](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data)). 어떤 후보도 추가 선택·접근·구매하지 않았습니다.

## Provisional assumption 기록

| 임시 가정 | 근거와 적용 범위 | 해제 조건·실행 전 대조 |
| --- | --- | --- |
| 무료 로컬 계산과 합성 fixture를 개발 검증에 사용할 수 있습니다. | 외부 지출이나 사용자 데이터 권한이 없고 되돌릴 수 있습니다. 설계·parser·회계·pipeline·회귀 검증에만 적용합니다. | 각 실행 전 등록·승인 상태를 확인합니다. 정식 freeze, 평가 예산, 실행 승인이 필요한 단계는 승인 전 시작하지 않습니다. |
| 기존 v1/approximate 자료는 디버그·fixture 용도로 읽을 수 있습니다. | 자료의 provenance·coverage·시점 한계가 기록돼 있습니다. 현재 cache는 27,472 bars 중 20,306개만 있고 corporate-action 121행에 `observed_at`이 없습니다. | 최종 자료 허용은 사용자 승인과 정식 계약 검증이 필요합니다. 그 전에는 최종 성능·OOS·후보 승인·실거래 근거에서 배제합니다. |
| v2의 2pp control/4pp 후보 표기는 초안 가설로만 유지합니다. | 기존 v2 초안에 있던 제안이며 본 작업에서 승인된 투자 기준이 아닙니다. | 후보 기준·기간·표본·예산을 freeze하기 전에 사용자 승인과 독립 검토를 거칩니다. v2 unresolved 값은 `null`, `execution_allowed=false`로 유지합니다. |

## 문서·계약 영향

- 사용자 문서: 결정 권고 문서 1개를 추가했습니다. 앱 동작과 API 계약은 바뀌지 않았습니다.
- 운영 문서: worktree task registry, 개발 기록, 날짜별 project handoff를 갱신했습니다.
- Research policy, v2 preregistration JSON, v1 archive, services, DB, runner configuration, PAPER/live state, broker APIs는 변경하지 않았습니다.

## 검증

- `git diff --check 05569736aad06ba67f7d100e2803f65539ee3622..bf18fb6d35604323f81548bd55fe68407df69c24` — 통과.
- Python 불변식 검사 — 결정 section 7개, local link 12개, official provider link 4개 확인. Mandate SHA 일치. V2 미결 값은 모두 null이고 registration/approval/execution은 모두 false.
- 보존된 v1 preregistration, hash manifest, results의 `sha256sum` — 각각 `fa5065df2ae70d024656209b0a33b755071c1441ecfa3406db99973fda49277e`, `bba3822f08a648462c8a2634c9402b545c833ad854bcb924fac96adb75d366a2`, `6c20c79552964182d52e5a9ce8571747ddf97a21a9c7b5c46b2dc827e167479b`. 과거 기록과 모두 일치합니다.
- `check_routing.py post` — `explore`, `plan`, `code_small`, `review`가 중앙 선택 model·logical role과 일치합니다. 최종 문서 commit `bf18fb6`에 대한 독립 review — PASS.
- 앞서 실행한 focused regression — 58개 통과, 1개 실패. 실패는 `docs/development-records/2026-09-24-full-suite-baseline.md`에 기록된 frozen-v1 variant SHA 불일치입니다. 역사 hash는 변경하지 않았습니다. 달력 스트레스 suite는 18개 통과했습니다. 문서 전용 통합 뒤 제품 test는 재실행하지 않았습니다.
- 후속 runnable 검증으로 collector credential/완료 marker와 held-band 설정·synthetic 경계 테스트 8개, PIT·FX 가용 시각·기업행동·universe-timing 테스트 8개, future-observation synthetic replay 전체 29개를 실행해 모두 통과했습니다. 앞의 8개에서 Starlette/httpx deprecation 경고 2개가 있었고 실패는 없습니다. 기존 cache의 read-only `collect-status`도 다시 실행해 `completed=true`, entries 137개, `ready=false`를 확인했습니다. 기대한 미준비 상태 때문에 CLI 종료 코드는 2였으며 cache는 수정되지 않았습니다. mandate SHA·v2 미결 값 20개·7개 권고 항목도 다시 확인했습니다.
- `research_future_observation_replay`는 synthetic 관측·수신·읽기 시각, 경계 도래, 중복·충돌 및 잘못된 시계를 분류하며 결과를 항상 `synthetic=true`, `registered=false`, `accepted_nav=false`, `evaluation_inputs_complete=false`로 고정합니다. 이는 PIT·자료 전달 fixture로 재사용 가능하지만 held-band preregistration freeze, 결과 노출/접근 격리, 최종 manifest 봉인·1회 평가를 검증하지 않으므로 OOS gate로 사용하지 않습니다. 이 차이를 남긴 채 신규 정책/코드 계약은 만들지 않았습니다.
- 신규 시장자료 API 요청·수집, credential 접근, 성과 실험, OOS 평가, DB/service/PAPER/live 변경, brokerage order — 수행하지 않았습니다. 공개 공식 provider 문서 조회만 했습니다.

## 안전·운영 상태

- 사용자 작성 루트 `HANDOFF.md`는 수정하지 않았습니다. Worktree가 clean인 것을 확인한 뒤 제거했고 branch `docs/portfolio-held-band-decision-preparation-v1`는 보존했습니다.
- tracked file 통합 중 roadmap runner queue를 pause했다가 metadata commit `95be807` 뒤 원래 상태로 복구했습니다. 확인 시 `paused=false`, timer active, one-shot service inactive, task 181개(완료 156·차단 9·실패 15·외부대기 1), active 0이며 상태 이유는 `fixed_engineering_backlog_exhausted`입니다. discovery는 `stale_head` terminal이고 source/test/mandate/task state change를 기다립니다. 별도 `development-runner.json` queue는 변경하지 않았습니다.
- 원격 push는 하지 않았습니다.

## 증거와 재개

- Audit: local cache와 기존 v1 audit는 read-only로 유지했습니다. 위 hash가 검증된 산출물을 식별합니다.
- 차단: `FINAL_VALIDATION`/OOS는 freeze 뒤 적격·미노출 관측을 기다립니다. 새 수집은 required credential/source access, 유료 service는 지출 승인을 기다립니다. 최종 source/data 허용 및 투자 수치 기준에는 사용자 승인이 필요합니다.
- 지금 가능한 작업: 로컬 cache 품질 분석, source candidate 조사, 합성 경계 fixture, parser/accounting/pipeline 검증, regression check. 이번 점검에서 별도 제품 코드 수정이 필요한 test gap은 찾지 못했습니다.
- 이번 범위의 무료 독립 실행 항목은 cache/readiness 점검, PIT·FX·기업행동·universe fixture, synthetic future-observation replay, 공개 provider 조건 확인까지 완료했습니다. 추가 code gate를 만들면 승인된 data/exposure contract를 미리 정한 것처럼 오인될 수 있어 구현하지 않았습니다. 다음 code 작업은 held-band freeze·노출·manifest 계약이 preregistration 검토에서 정해진 뒤 기존 synthetic replay와 경계를 이어 붙이는 것으로 한정합니다. v2 null field와 `execution_allowed=false`를 유지하고 approximate 결과를 전략 증거로 쓰지 않습니다.
