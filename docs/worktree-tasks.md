# 워크트리 작업 등록부

## canonical-governance-sync-recheck-20260920

- 상태: 완료·운영 dispatch는 계속 paused/inactive
- mandate digest `22efba...c264ab1`, policy version, dispatch flag와 roadmap 40개 checklist/complete
  16개를 parser로 재확인했습니다. runner DB는 blocked 9/completed 75/failed 12/running 0이며
  service inactive, timer not-found입니다.
- 자동 resume·성과 승격·PAPER/live·remote push·Windows 종료는 하지 않았습니다.
- 개발 기록: `docs/development-records/2026-09-20-canonical-governance-sync-recheck.md`

## r6-krx-zero-row-classification-20260920

- 상태: zero-row signature 분류 완료·readiness insufficient 유지
- 기존 2026-06-29 KRX raw의 29 zero/missing 행은 모두 KOSPI이며 종가·시총·상장주식수는 양수지만
  OHLC/거래량/거래대금/전일대비는 0입니다. 무거래/거래정지 가능성을 기록하되 별도 상태 원문 없이
  확정하지 않았습니다.
- 보간·정상 bar 승격·한국 benchmark/경제 평가를 하지 않았습니다.
- 개발 기록: `docs/development-records/2026-09-20-r6-krx-zero-row-classification.md`

## market-data-readiness-recheck-20260920

- 상태: read-only 확인 완료·미국 재실행 blocked 유지
- `.env`를 명시한 `collect-status`에서 기존 US cache 84개 entry와 자격증명 누락 없음은 확인했지만,
  completed marker/output identity가 없어 `completed=false`, `ready=false`, exit 2였습니다.
- FRED는 `.env`에 설정되지 않았고, 기존 frozen 결과·public evidence를 보완자료로 재명명하지 않았습니다.
- 신규 network collection·replay·성과 계산·요율 변경은 하지 않았습니다. FRED 또는 검증된 대체 FX
  원천, completion marker, PIT action coverage, broker cost contract가 준비될 때까지 R4/R2-03은 보류합니다.
- 개발 기록: `docs/development-records/2026-09-20-market-data-readiness-recheck.md`

## regression-failure-audit-20260920

- 상태: 기존 회귀 4개 원인 분류·수정 보류
- 투자자 stale 기대 2개, historical guarded-variant SHA pin 1개, frozen archive calendar hash 1개를
  개별 재현했습니다. 이번 경제 경로와 무관하므로 production guard·historical artifact를 임의 변경하지
  않았습니다.
- 개발 기록: `docs/development-records/2026-09-20-regression-failure-audit.md`

## action-review-state-recheck-20260920

- 상태: read-only 재확인·R1-04/R1-05 blocked 유지
- canonical action DB의 111 revisions와 4 reviews를 확인했습니다. reviews는 matched 3건, partial
  1건이며 NVDA 2026-06-04 dividend의 ex-dividend date가 missing입니다.
- 일부 matched review를 전체 PIT/coverage 근거로 승격하지 않고, action ledger·성과·PAPER 적용은
  계속 차단합니다. DB는 수정하지 않았습니다.
- 개발 기록: `docs/development-records/2026-09-20-action-review-state-recheck.md`

## r2-03-fx-calendar-reconciliation-20260920

- 상태: 날짜 대사 완료·R2-03 blocked 유지
- canonical US equity 252 sessions와 기존 ALFRED sampled FX 251 dates를 비교했습니다. 교집합은
  250/252이며 canonical 누락은 `2025-10-13`, `2025-11-11`, FX-only 날짜는 `2026-04-03`입니다.
- FX first-seen은 exact publication timestamp가 아니므로 carry-forward·삭제·추정을 하지 않았습니다.
  R2-03와 USD/KRW NAV 경제 평가는 달력/application/PIT 근거 확보 전까지 보류합니다.
- 개발 기록: `docs/development-records/2026-09-20-r2-03-fx-calendar-reconciliation.md`

## r2-03-fx-provenance-cutoff-recheck-20260920

- 상태: resolver 재검증 완료·historical PIT blocker 유지
- `research-external.db`의 915개 USDKRW 후보를 기존 read-only resolver로 cutoff별 확인했습니다.
  2025-09-11, 2025-10-13, 2025-11-11, 2026-04-03은 모두 `no_candidate`; 2026-09-11만
  2026-09-09 관측(age 2)으로 resolve됐습니다.
- 행 수만으로 historical availability를 주장하지 않고, R2-03/NAV application은 계속 fail-closed입니다.
- resolver·FRED parser 관련 회귀 테스트는 `29 passed` (128 deselected)입니다.
- 개발 기록: `docs/development-records/2026-09-20-r2-03-fx-provenance-cutoff-recheck.md`

## market-cost-diagnostic-reverification-20260920

- 상태: 독립 산술 pass·법정/체결 자료 unavailable
- frozen US pilot 106 trades/252 sessions를 읽기 전용 Decimal으로 재검증했습니다. 저장값 mismatch는
  0건이고, fee/tax/slippage 독립 집계가 일치했지만 결과 `blocked`, 경제 평가는 `not-evaluated`입니다.
- 휴장일·실제 체결 timestamp/order identity·partial fill·법정 세목/유효기간/공식 세율이 없으므로
  R2-01/02 또는 경제 지표 승격을 하지 않습니다.
- 후속 회귀: `test_market_cost_diagnostics.py`와 `test_market_data_collector.py`에서
  `160 passed` (2026-09-20)이며 collector 계약·비용 진단 회귀는 유지됩니다.
- 개발 기록: `docs/development-records/2026-09-20-market-cost-diagnostic-reverification.md`

## r2-02-official-cost-source-audit-20260920

- 상태: 부분 근거 확보·R2-02 blocked 유지
- 확인: 국가법령정보센터의 2026-03-20 시행 증권거래세법 시행규칙에서 KOSPI
  `5/10,000`, KOSDAQ/K-OTC `20/10,000`을 확인했고, SEC FY2026 advisory에서 2026-04-04
  이후 Section 31 covered-sale rate `$20.60 / $1,000,000`을 확인했습니다.
- 결정: 한국 board별 세금은 현재 `market=KR` 계약만으로 적용하지 않습니다. 미국 Section 31은
  SRO 부담금이며 broker 고객 요율을 직접 정하지 않으므로 `sell_tax_rate=0.0018` 또는
  broker fee를 공식값으로 대체하지 않습니다.
- 남은 조건: broker/계좌 fee schedule, 적용 시장·상품·기간, 체결/결제 시점, 한국 농특세 등
  세목 범위를 별도 계약으로 고정해야 R2-02를 완료할 수 있습니다.
- 개발 기록: `docs/development-records/2026-09-20-r2-02-official-cost-source-audit.md`

## r3-phase-status-sync-20260920

- 상태: 완료
- 근거: R3-01~04의 기술 체크와 개발 기록·검증 artifact가 모두 존재해 단계 요약을
  `예정`에서 `완료`로 동기화했습니다.
- 제한: 단계 완료는 읽기 전용 UI·fixture 계약의 기술 완료이며 경제 성과·benchmark·PAPER
  승격을 의미하지 않습니다.

## mandate-symbol-cap-pin-sync-20260920

- 상태: 완료
- 목표: current `docs/research-mandate.json` SHA와 symbol-cap archive replay의 hard-coded
  mandate pin을 동기화합니다.
- 수정: `research_portfolio_symbol_cap_episodes.py`의 pin을
  `22efba4714bc0baf65c56bdfd84dcdee91184a760a13d4d30c5a94486c264ab1`로 갱신했습니다.
- 검증: fixed archive test, mandate governance 16개, Ruff, diff 검사 통과.
- 제한: historical artifact bytes·전략·성과·runner 실행 상태는 변경하지 않았습니다.
- 개발 기록: `docs/development-records/2026-09-20-mandate-symbol-cap-pin-sync.md`

## r6-prepared-path-contract-sync-20260920

- 상태: 기술 계약 확인·경제 not-evaluated
- 목표: 시장별 prepared path와 원화 초기자본·단위 계약을 roadmap 증거와 동기화합니다.
- 확인: KRX/US collector provider 경로 분리, prepared file market mismatch 거부, KRW reporting
  및 KR/US native currency/account 계약과 `100000000` 초기자본 검증을 기존 테스트와 R6 자료
  경로 기록에서 재확인했습니다. 새 raw 자료나 성과 계산은 수행하지 않았습니다.
- 결과: R6-03 기술 `pass`; R6-02의 zero/missing OHLCV로 한국 readiness insufficient은 유지합니다.
- 개발 기록: `docs/development-records/2026-09-20-r6-krx-path-verification.md`

## r6-service-response-diagnostics-20260920

- 상태: 기술 진단 계약 완료·한국 readiness insufficient
- 목표: KRX cache와 단일 서비스 응답을 분리해 HTTP/auth/parse/coverage/readiness를 진단합니다.
- 구현: `diagnose_krx_response()`와 `diagnose-krx-response` CLI를 추가하고 cache 진단이
  동일 parser 계약을 재사용하도록 연결했습니다. 서비스 진단은 cache integrity를 `null`로
  남겨 과거 cache 성공으로 오인하지 않습니다.
- 검증: KRX focused pytest 3개, Ruff, strict mypy, 실제 cache response CLI, diff 검사 통과.
- artifact: `/home/kwl/.local/share/jusik/portfolio-audit/20260920-r6-krx-diagnostics/service-response.json`
  SHA-256 `ad733e5520027298c8e7f3f4c6966a27409d0d90778772a6a2d184285605873f`; HTTP 200,
  membership 946, valid bars 917, zero/missing 29, readiness exit 2.
- 제한: zero/missing 행은 보간하지 않으며 한국 경제 성과·benchmark·R4/PAPER 승격은 하지 않습니다.
- 개발 기록: `docs/development-records/2026-09-20-r6-service-response-diagnostics.md`

## r6-krx-diagnostics-20260920

- 상태: 기술 진단 계약 완료·readiness insufficient
- 목표: KRX cache와 서비스 응답의 관측 상태를 분리하고 zero-OHLC/volume 0 원인을
  재현 가능한 수치·coverage·readiness로 보존합니다.
- 구현: `KrxCacheDiagnostics`, `diagnose_krx_cache()`와 `diagnose-krx-cache` CLI를
  추가했습니다. raw cache는 읽기 전용이며, zero/missing OHLCV는 membership으로만
  집계하고 readiness를 승격하지 않습니다.
- 검증: focused pytest 2개, Ruff, strict mypy, 실제 cache CLI, diff 검사 통과.
- 실제 artifact `/home/kwl/.local/share/jusik/portfolio-audit/20260920-r6-krx-diagnostics/report.json`
  SHA-256 `8c9fa160e597eba627ae27f7353ccfb8f59f7ff55157c7040f822a79650815bb`.
  HTTP 200 1건, membership 946, valid bars 917, zero/missing 29, readiness insufficient.
- 제한: provider 전체 coverage/PIT·경제 acceptance·한국 benchmark는 미증명이며 R6-03/R6-04와
  미국 결과 결합을 진행하지 않습니다.
- 개발 기록: `docs/development-records/2026-09-20-r6-krx-diagnostics.md`
- 2026-09-20 재검증: KRX/approximate 관련 focused 회귀 `22 passed`(160 deselected, 경고 2건),
  실제 cache CLI는 exit 2·HTTP 200·946 membership·917 valid bar·29 zero/missing·readiness
  `insufficient`을 재현했습니다.

## r3-01-market-curves-20260920

- 상태: 기술 UI 계약 완료·benchmark 자료 확인 불가
- 목표: 기존 결과 계약의 저장 시계열을 같은 기간으로 묶어 KRW NAV, USD 수익률,
  MDD와 benchmark 상태를 읽기 전용 화면에 표시합니다.
- 구현: `frontend/lib/marketResearch.ts`에 fail-closed USD return/MDD/benchmark curve를
  추가하고 `frontend/app/research/market/[id]/page.tsx`에 곡선과 상태를 표시했습니다.
  benchmark는 자료 계약이 없어 빈 곡선으로 남겼습니다.
- 검증: frontend contract verification, lint, typecheck, build, diff 검사 통과.
- 결과 commit: `e3580e2`
- 제한: benchmark PIT 자료와 경제 성과는 확인하지 않으며 R4 재실행·PAPER/live 승격과
  분리합니다.
- 개발 기록: `docs/development-records/2026-09-20-r3-01-market-curves.md`

## r1-symbol-source-coverage-contract-20260920

- 상태: 기술 계약 완료·coverage incomplete 유지
- 목표: 재구축 public-evidence catalog에서 요청 universe 종목별 source 관측 건수와
  누락 원인을 결정적으로 보존하고, 빈 자료·unresolved·out-of-universe를 조용히
  성공시키지 않습니다.
- 구현: `build_public_evidence_symbol_coverage()`와 `SymbolEvidenceCoverage`/
  `PublicEvidenceSymbolCoverage`를 기존 catalog 모듈에 추가했습니다. 결과는 catalog
  SHA에 결속되고 `coverage=incomplete`, `economic_acceptance=false`, `pit_proof=false`
  를 강제합니다.
- 검증: catalog focused pytest 10개, Ruff, diff 검사 통과. strict mypy는 기존 public-
  evidence 의존 모듈의 범위 밖 오류로 non-zero이며 새 계약은 해당 오류를 추가하지
  않았습니다.
- 실제 재구축 catalog 1,570개 item을 새 계약으로 재생성한 artifact
  `/home/kwl/.local/share/jusik/portfolio-audit/20260920-public-evidence-catalog-rebuilt-20260920/symbol-coverage-contract-v1.json`
  의 SHA는 `d76d1980a63dca9074c3576651a5639143dee523a368a2eb13b53daeca05329a`입니다.
- cached raw receipt audit `/home/kwl/.local/share/jusik/portfolio-audit/20260920-public-evidence-receipt-audit-20260920/report.json`
  (SHA `33605dd0377840c8460a5a9f915f05b2159a6c819c43e053c5cbdf2265fe41ad`)에서 Alpha 20건,
  SEC submissions 8건, SEC ticker map 1건, Nasdaq 1건의 parser 성공을 확인했습니다.
  SOXL/TQQQ SEC receipt 부재와 provider 전체 coverage/PIT 미증명은 유지합니다.
- 제한: provider 전체 coverage, PIT, 기업행사 권리·가격 증거는 여전히 없습니다.
  R1-05 checkbox·경제 acceptance·성과/원장/PAPER/live 승격은 변경하지 않습니다.
- 개발 기록: `docs/development-records/2026-09-20-r1-symbol-source-coverage-contract.md`

## r1-public-evidence-catalog-integrity-audit-20260920

- 상태: 기술 재구축 완료·coverage incomplete 유지
- 목표: 현재 v2 public-evidence catalog가 요청 universe 경계를 실제로 지키는지 읽기 전용
  검증하고, unresolved identity와 out-of-universe 항목을 조용히 승격하지 않습니다.
- 입력: `/home/kwl/.local/share/jusik/portfolio-audit/20260920-public-evidence-catalog-v2/catalog.json`
  (source SHA `0c7b6b568ef87e9c752204a8974434767ba0460ead76ac7b4cc3f15a8a2c31f3`)
- 초기 진단: requested 10개·items 1,597개 중 27개가 요청 universe 밖이며 `SOXL`·`TQQQ` identity가
  unresolved였습니다. 기존 catalog는 수정하지 않았습니다.
- 재구축: cached Alpha/SEC/Nasdaq raw를 현재 fail-closed builder로 재생성해 새 catalog는
  1,570개 item, out-of-universe 0, unresolved 0, `coverage=incomplete`입니다. Nasdaq raw의
  27개 비요청 halt는 rejected 목록으로 manifest에 보존했습니다.
- identity mapping: SOXL `0001424958`, TQQQ `0001174610`을 별도 SEC ETF identity evidence로 결속했습니다.
- audit: 진단 `/home/kwl/.local/share/jusik/portfolio-audit/20260920-r1-catalog-integrity-audit/report.json`,
  재구축 `/home/kwl/.local/share/jusik/portfolio-audit/20260920-public-evidence-catalog-rebuilt-20260920/`.
  새 catalog semantic SHA `0ffb17730ad4fe98e808ff6f3973359f67aa6f2665b28dc53ca51fc7b638e03b`.
- symbol coverage: 재구축 catalog의 종목별 source count를 별도 보고서로 고정했습니다.
  report SHA `f3faa820050e150978a3cc78d8792a0dbd17ec6ffb14e5f2f996c8cd85556d49`.
  SEC는 10개 종목 모두 관측됐고 Alpha는 GEV/GOOGL/MSFT/NVDA/SOXL/TQQQ/VRT 등 7개만
  관측됐으며, Nasdaq Trader는 요청 universe에 남은 항목이 없어 10개 모두 누락입니다.
  AMD/ARM/COHR는 Alpha도 누락이고 SOXL/TQQQ는 SEC도 누락입니다.
- 다음: 새 catalog는 identity/symbol boundary만 보강합니다. provider 전체 coverage, PIT, 권리·가격
  경계가 없으므로 R1-05와 경제 acceptance는 계속 보류합니다.

## r2-04-drawdown-chronology-preflight-20260920

- 상태: 기술 preflight 완료·경제 승격 차단
- 목표와 완료 조건: frozen approximate US pilot의 저장 NAV·거래·dataset을 strategy/engine
  재실행 없이 독립 Decimal chronology로 검산하고, 초기자본 포함 peak/MDD·20% latch·다음
  available open liquidation을 기록합니다. MDD가 hard filter를 넘으면 후보 승격을 하지
  않고, calendar/benchmark/future evidence 누락도 명시합니다.
- 담당: Astra read-only preflight
- 워크트리/브랜치: 없음 (기존 production code 변경 없음)
- 입력과 선행 작업: frozen pilot SHA chain, stable dataset, `backend/jusik/drawdown_chronology.py`
- 수정 허용 범위: 외부 audit report와 개발 기록·등록부만. 전략·성과 evaluator·runner·artifact는 변경하지 않습니다.
- 검증: `python -m jusik.drawdown_chronology` 실행 성공; chronology status `success`, independent MDD
  `26.463097776467786...%`, latch `2026-02-12`, 5개 보유 심볼 모두 다음 open `2026-02-13`에 관찰된 매도.
- 결과: audit `/home/kwl/.local/share/jusik/portfolio-audit/20260920-r2-04-drawdown-chronology/report.json`, SHA-256 `ae439ad63585ea075211a1c10e7b0cb527d3da741daf59197f438ccc31248d39`.
- 판정: `blocked`; MDD `>20%` hard filter 실패. 저장 결과의 latch 날짜·release chronology도 없어 `stored_match=false`이며 calendar/benchmark/future evidence는 unavailable입니다.
- 다음: R2-04 경제 완료나 R4 승격을 주장하지 않고, 독립 결과를 후보 비교 입력으로만 보존합니다.
- 개발 기록: `docs/development-records/2026-09-20-r2-04-drawdown-chronology-preflight.md`

## canonical-time-evidence-sidecar-20260920

- 상태: 완료
- 목표와 완료 조건: frozen canonical run을 수정하지 않고, 공식 XNYS calendar에서 파생한
  시간 evidence sidecar를 별도 audit 경로에 생성·검증합니다. canonical run/manifest,
  candidate time-evidence, replay identity와 equity session/NAV를 SHA로 대조하고
  불일치·경로 변조·순서 위반을 fail-closed로 거부합니다. readiness 기본 판정과
  경제 acceptance는 변경하지 않습니다.
- 담당 Luna: canonical_time_sidecar_code
- 워크트리 절대 경로: `/home/kwl/projects/jusik-canonical-time-evidence-sidecar`
- 작업 브랜치: `feat/canonical-time-evidence-sidecar`
- 기준 커밋 SHA: `206e1fa` (기존 작업 등록 기준; 이번 경로 보강 기준 main `0fb382c`)
- 통합 대상 브랜치: `main`
- 입력과 선행 작업: canonical time-evidence candidate 20260920, frozen canonical
  run/manifest, tracked XNYS calendar, existing canonical NAV reconciliation contract
- 수정 허용 범위: 새 sidecar builder/verifier, focused tests, 개발 기록. 기존
  canonical artifact·readiness 정책·runner·network/order/PAPER/live는 변경하지 않습니다.
- 포트·테스트 DB·출력 경로: 별도 audit 디렉터리, DB/서비스 해당 없음
- 검증 명령과 결과: `pytest -q backend/tests/test_research_canonical_time_evidence.py` 6개 통과,
  Ruff·strict mypy·diff check 통과, 실제 252개 sidecar build/verify와 path pin fail-closed 통과
- 결과 커밋 SHA: `3c6dbef`, path pin 보강 `ff980e7`
- 검토 결과와 남은 문제: 독립 review PASS. readiness 연결 및 경제 acceptance는 별도 작업
- 병합 직전 main SHA: `0fb382c`
- 통합 커밋 SHA와 정리 여부: 기존 통합 `fe4b1a5`, 추가 통합 `c6fdf4f`; 전용 워크트리는 검증 후 정리 예정
- 통합 검증 실패 원인과 복구 결과: 해당 없음
- 개발 기록 경로와 갱신 여부: `docs/development-records/2026-09-20-canonical-time-evidence-sidecar.md` 갱신 완료
- handoff 저장 경로와 갱신 여부: `HANDOFF.md` 갱신 완료

## public-evidence-collectors-20260920

- 상태: 기술 slice 완료. Nasdaq Trader RSS, SEC EDGAR submissions, Alpha Vantage
  `DIVIDENDS`/`SPLITS`의 공개 원문 evidence collector를 추가했습니다.
- 구현: `backend/jusik/research_public_evidence.py`,
  `backend/jusik/research_sec_evidence.py`,
  `backend/jusik/research_alpha_actions.py`와 각 focused test.
- 검증: 관련 collector·market collector/history pytest 176개, Ruff, diff 검사 통과.
  실제 Nasdaq RSS 45건, SEC CIK 1045810 1,000 filings, Alpha NVDA 2024–2025
  10 actions를 읽기 전용으로 확인했습니다.
- 범위: 원문·source URL·관측 시각·SHA-256만 보존하며 가격·원장·PAPER/live에 자동
  적용하지 않습니다. 무료 provider의 historical PIT/전체 coverage는 미증명입니다.
- 제한: R1-02/R1-04/R1-05 checklist와 경제 acceptance는 원천 coverage 및 권리·가격
  경계 검증 전까지 미체크로 유지합니다.
- 기록: `docs/development-records/2026-09-19-public-halt-evidence.md`.

## public-evidence-catalog-20260920

- 상태: 기술 slice 완료. SEC·Nasdaq·Alpha 결과를 source-specific identity와 raw
  SHA로 결합하는 읽기 전용 catalog를 추가했습니다.
- 구현: `backend/jusik/research_public_evidence_catalog.py` 및
  `backend/tests/test_research_public_evidence_catalog.py`.
- 계약: 중복을 제거하지만 `coverage=incomplete`를 강제합니다. 원천 전체 coverage,
  PIT completeness, 가격·권리 경계가 확인되기 전에는 R1-02/R1-04/R1-05나 경제
  acceptance를 변경하지 않습니다.
- 검증: catalog focused pytest 1개, Ruff, diff 검사 통과.
- 개발 기록: `docs/development-records/2026-09-19-public-halt-evidence.md`.

## public-evidence-batch-20260920

- 상태: bounded batch 및 parser 교정 완료.
- 입력: registry 미국 10개 심볼, Alpha 2024–2025, Nasdaq 2024-01-02 1일.
- 결과: Alpha 53 actions, Nasdaq raw 45건·catalog 27건. audit
  `/home/kwl/.local/share/jusik/portfolio-audit/20260920-public-evidence-batch/`에
  raw, catalog, request, SHA-256을 보존합니다.
- 교정: HTML `Issue Symbol` 헤더 오인식 재현 테스트를 추가했고 raw 45건 재파싱에서
  `SYMBOL` 오인식 0건을 확인했습니다.
- 판정: 전체 coverage/PIT/권리 가격 경계가 없어 R1 체크와 경제 acceptance는 보류.

## sec-ticker-filing-batch-20260920

- 상태: SEC ticker mapping 및 submissions batch 완료.
- 결과: 미국 registry 10개 중 8개 CIK 매핑, submissions 6,243건, 2024–2025
  catalog 편입 1,517건. SOXL/TQQQ 매핑 누락을 성공으로 숨기지 않고 request에
  기록했습니다.
- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260920-public-evidence-batch/`.
- 제한: filing 접수 시각은 보존하지만 corporate-action 본문 권리·가격 경계와
  전체 PIT/coverage는 아직 증명하지 않았습니다.
- 개발 기록: `docs/development-records/2026-09-19-public-halt-evidence.md`.

## roadmap-planner-wait-20260919

- 상태: 정상 대기. planner attempt `11f1a5101c7649cfabb3a4d35123115e`가 `proposal=null`, `status=waiting`, exit 0으로 종료했습니다.
- 근거: HEAD·roadmap SHA·mandate gate는 일치했으나 R1-04/R1-05의 초기 상태·가격·권리수량·effective/payment UTC 경계·전체 coverage 원천 자료가 없습니다.
- 조치: 합성 자료·임의 retry·경제 acceptance·PAPER/live·주문을 수행하지 않았습니다. fail-closed 재개 조건은 승인된 SHA 고정 원천 자료와 versioned provenance 계약입니다.
- 후속 timer attempt `12f52e007e234686b6cf63c56f918667`도 동일 대기로 정상 종료했습니다.
- 개발 기록: `docs/development-records/2026-09-19-roadmap-planner-wait-r1-evidence.md`.

## metric-diagnostic-contract

- 상태: 완료. primary `CAGR/MDD/Sharpe/Calmar`를 유지하고 `Sortino`, `Profit Factor`, MDD 회복 기간, 최대 연속 손실을 diagnostic metrics로 mandate·roadmap에 명시했습니다.
- 동기화: `docs/research-mandate.json` 전체 SHA `22efba4714bc0baf65c56bdfd84dcdee91184a760a13d4d30c5a94486c264ab1`, governance projection과 Markdown/checksum을 함께 갱신했습니다.
- 검증: mandate governance/planning pytest 35개, `git diff --check` 통과. 계산 실행·후보 승자 선택·자동 PAPER/live 승격은 하지 않았습니다.
- 다음 의존성: KOFR 전체 기간 business-date·publication timezone 근거가 확보되기 전까지 경제 성과 계산은 차단합니다.

## r1-receipt-429bc04a

- 상태: 기술 slice 완료. task `roadmap-r1-04-receipt-preflight-v1`, attempt `0c28fbb501444741a1fa43554e1933af`. R1-04 전체 checkbox는 미체크이며 금융/data acceptance는 차단입니다.
- 목표/변경: 고정 DB 두 개의 읽기 전용 receipt preflight, 원문 문자열·SHA와 canonical 표현을 분리한 명시적 legacy-v1 provenance, 회계 artifact 누락 진단.
- 담당: Astra 감독·통합, Luna 단일 구현, Terra 독립 재검토 PASS.
- 워크트리/브랜치: 기존 `/home/kwl/projects/jusik-r1-receipt-429bc04a`, `feat/r1-receipt-429bc04a` 재사용. 구현 `4605358`·수정 `0088260`, 통합 전 main `89a337d`, 통합 `15d2efb435e9ae4981a04e8c7da7063031848149`.
- 검증: main pytest50·Ruff·configured strict mypy4파일·고정 DB 출력 결정성·원본 전후 SHA 불변 PASS. 공개 SHA override와 SQLite 테스트 누락을 수정한 뒤 재검토했습니다.
- 예산/격리: 단일CPU·seed0·누적 342.263/900초·artifact50MiB 이내. 금융 실험/network/GPU/PAPER/live/주문/원본DB·원장/서비스/설정/remote 변경0.
- 증거/handoff: `/home/kwl/.local/share/jusik/portfolio-audit/r1-receipt-0c28fbb5`; `integration-verification.json`, `evidence-manifest.json`, `HANDOFF.md`. 과거 차단과 위반 기록은 이전 audit·개발 기록에 보존합니다.
- 정리: 소스·패치·검증 로그·기존 미추적 개발 초안과 SHA를 archive·검증한 뒤 소유 worktree와 병합 브랜치를 제거했습니다. `--force`는 사용하지 않았습니다. 최종 상태는 audit `cleanup.json`이며 다른 격리 작업은 재개하지 않았습니다.
- 남은 조건: coverage·가격·권리·effective UTC 경계가 없어 linkage false, strict PIT·경제 acceptance·승격 보류. 성과가 없는 기술 slice로 웹 publication 해당 없음.
- 개발 기록: `docs/development-records/2026-09-18-r1-receipt-429bc04a.md`.

## roadmap-governance-activation

- 상태: 진행·승인된 investment-roadmap 전용 runner와 timer 활성. 첫 cycle은 `idle`/exit 0이며, 신규 큐가 없어 실패·차단 항목은 명시적 retry 전 격리 중입니다. 일반 research scope와 PAPER/live·주문 경로는 계속 비활성입니다.
- 목표: 승인된 경제 목표에 맞춰 governance와 전용 runner를 동기화하고, fail-closed 검증을 통과한 뒤 다음 미완료 roadmap slice를 자동 계획·실행합니다.
- 동기화: `docs/research-mandate.json` dispatch enabled, 전체 JSON SHA-256 `ceca2ee1d3e86cf79822b6b4a1606ac6699405f93eaf302fcf3842247f5de7ac`, governance projection SHA `624599f24864201fce981ed2e1407db3cf53eb3ad2da306bf3e7cc0b25031adb`.
- 전용 설정: `~/.config/jusik/roadmap-development-runner.json`의 `planning_enabled=true`, `scope=investment-roadmap`, `automatic_recovery=false`; user timer는 승인 검증 후 활성화합니다.
- 안전 범위: runner는 git clean·mandate SHA·dispatch gate를 확인하고 roadmap slice만 다룹니다. 실제 주문, PAPER/live 승격, network collection, remote push는 자동화하지 않습니다.
- 보류 해소: 2026-09-17 drain 후 생성된 operator hold는 승인 전 재개 금지 기록이므로 원문과 runner DB 백업을 archive로 보존했습니다. DB의 `operator_hold_no_new_tasks`·`operator_hold_no_requeue` trigger도 승인된 재개 시점에만 제거했고, timer/service와 planner 결과를 확인했습니다.
- 현재 판정: planner attempt `0065eefe2e294823975e75c1e3947349`는 `waiting`입니다. R1-04/R1-05의 실제 원문 SHA·관측시각·권리/가격 근거가 없으므로 성공·retry task를 만들지 않았습니다.
- 개발 기록: `docs/development-records/2026-09-18-roadmap-governance-activation.md`
- fail-closed 보강: legacy operator-hold SQLite trigger가 남아 있으면 `resume`을 거부하고 `run-once`를 `blocked`로 종료하도록 `RunnerStore.operator_hold_triggers`와 회귀 테스트를 추가했습니다. 개발 기록은 `docs/development-records/2026-09-18-runner-hold-trigger-gate.md`입니다.

## r1-action-evidence-audit

- 상태: 부분 근거 확인·경제 acceptance 대기. 기존 dividend overlay artifact에서 stable event/revision/evidence identity, ex/payment UTC 경계, 금액·통화·권리수량을 확인했지만 전체 coverage는 `false`입니다.
- 근거: `/home/kwl/.local/share/jusik/portfolio-audit/20260910T100314Z-dividend-accounting/isolated-output/dividend-overlay-runs/28bb6a8aaf8097a4f41e6bf0e087393111c752daed43a675e5579b68f833597f/result.json`, result SHA `909e356c8b9588335ee435f636e1c16df4eace81aa7433505b4044cc61d5e9f1`.
- 확인: NVDA 1건만 eligible(2024-06-11 ex, 2024-06-28 payment, USD 0.01, entitled quantity 30/38 scenario); 107 revisions 중 106건 excluded/current revision unreviewed. `prospective_validation_eligible=false`, `automatic_ledger_application=false`입니다.
- 판정: 부분 후향 overlay를 R1-04/R1-05 완료나 prospective/PIT acceptance로 승격하지 않습니다. 개발 기록은 `docs/development-records/2026-09-18-r1-action-evidence-audit.md`입니다.
- 추가 확인: review DB에서 공식 근거 3개와 matched review 4개를 확인했습니다. NVDA 2024 split/dividend 및 TQQQ 2025 split은 원문 SHA·capture 시각·provider revision과 연결되지만, NVDA 2026 dividend는 ex-date 누락으로 partial입니다. synthetic mismatch 1건도 별도 보존합니다. 개발 기록은 `docs/development-records/2026-09-18-r1-action-receipt-db-audit.md`입니다.
- 2026-09-19 재검증: 최초 문서 경로(`research-action-collection.sqlite3`)는 존재하지 않아 `OperationalError`로 종료했으나, canonical DB(`/home/kwl/.local/share/jusik/research-action-collection.db`)를 확인해 overlay를 재실행했습니다. 새 run `7b742e9b99a1b809dda225d7feb60d79e4824f4cb4b7b0455e8918406ddd93b3`는 109개 revision 중 1개 eligible·108개 excluded이며 `coverage_complete=false`, `prospective_validation_eligible=false`, `automatic_ledger_application=false`입니다. 경로 문제는 해결했지만 R1-04/R1-05와 경제 승격은 여전히 보류합니다.

## r4-us-pilot-cache-readiness

- 상태: 자료 게이트 차단·pilot 미실행
- 2026-09-19 read-only `collect-status` 재검증: 기존 US approximate cache 84개 entry, `completed=false`, `ready=false`, 누락 자격증명 `ALPHA_VANTAGE_API_KEY`·`FRED_API_KEY`, exit code 2. 기존 cache와 frozen artifact는 변경하지 않았습니다.
- 판정: 기존 frozen pilot의 independent cost/NAV 검증을 현재 R4 pilot 또는 strict/PIT 근거로 재명명하지 않습니다. 자격증명 또는 동등 provenance 응답이 준비되어 coverage·membership·FX·기업행동 계약을 통과하기 전에는 R4-01~R4-05와 경제 승격을 보류합니다. 개발 기록은 `docs/development-records/2026-09-19-r4-us-pilot-cache-readiness.md`입니다.
- 후속 bounded 수집: frozen cache 복사본에서 405회 상한·`--resume` 수집은 exit 0이었으나, 1년 approximate pilot은 `insufficient`/`incomplete`로 종료했습니다. 불확실 기업행동 심볼 때문에 trades/equity/metrics를 생성하지 않았습니다. audit은 `/home/kwl/.local/share/jusik/portfolio-audit/20260919-r4-us-pilot-collection-5e966f4/`이며 pilot run SHA는 `c93ea954610ca0cfb94aeb577b1ebd7a4b343651fdc638e296fca2c8e38d22b1`입니다. R4-02~R4-05와 경제 승격은 보류합니다.
- 추가 대조: dataset의 `observed_at=null` 이벤트 36개 심볼과 canonical review DB의 reviewed symbols(NVDA·TQQQ)는 overlap 0개였습니다. 기존 review를 전이하거나 관측시각을 추정하지 않습니다.

## portfolio-prospective-oos-gate

- 상태: 관찰 중·OOS 판정 대기. 현재 코드와 등록 identity가 다르지만 등록 시점 immutable source snapshot을 재구성해 monitor를 그 snapshot으로 격리 실행합니다. 계약 기간이 아직 종료되지 않아 OOS go/no-go는 실행하지 않았습니다.
- 목표: R5의 bounded IS·validation·walk-forward 이후 최종 untouched OOS를 단회 판정하고, 통과 전에는 stress/PAPER 승격을 금지합니다.
- 고정 계약: `research_prospective_registration`, 평가 구간 `[2026-09-14, 2026-11-09)`, source run `fa0907ecfe86b19836881e5a78a874925fc611978ffe31064eacc82a0a46f687` 및 등록된 session/policy/code/calendar identity.
- 확인 결과: 기존 historical robustness는 7 folds/147 evaluations의 과거 반복 검증이며 새 미래 holdout이 아닙니다. corrected calendar bundle도 2026-09-08에 끝나는 historical approximate simulation이므로 OOS 입력으로 재사용하지 않습니다.
- 차단 사유: 2026-09-18 현재 prospective 구간이 진행 중입니다. 종료 전 수신 `[start, end)` 자료, fill provenance, 시작·종료 raw boundary artifact, 승인된 경계 NAV와 `evaluation_inputs_complete=true`를 확보할 수 없습니다.
- 재개 조건: 2026-11-09 이후 고정 계약의 자료·시각·SHA를 읽기 전용으로 검증하고, 경계 NAV 승인과 completeness를 확인한 뒤 단 한 번 OOS go/no-go를 계산합니다. 실패 시 stress/PAPER를 진행하지 않습니다.
- 자동화: `research_boundary_monitor`는 `BoundaryCaptureMonitor`만 사용해 start/end artifact를 캡처하고 end artifact 생성 뒤 종료합니다. `research_app`, 개발 runner, optimizer, 주문 경로를 시작하지 않습니다. unit 템플릿은 `deploy/systemd/jusik-prospective-boundary-monitor.service`입니다.
- 해결: 등록 시점 identity와 일치하는 immutable snapshot을 `/home/kwl/.local/share/jusik/research-prospective-code/8e716fd339cf44895799f0f0183047b64466b9702fd0bece91bfb2d79ed3fc07/backend/jusik`에 보존했습니다. snapshot identity `19d3622e5b195e52e1e06065d32d771d3e40c4e4c53f8fc25c101f510ca14fd7`가 계약과 일치하며, monitor는 이 snapshot만 provenance 검증에 사용합니다. 현재 corrected code나 계약 bytes는 변경하지 않습니다.
- 금지: historical 결과 재명명, corrected bundle 재사용, holdout 반복 평가·retune, runner/service/network/order/PAPER/live 변경.
- 개발 기록: `docs/development-records/2026-09-18-portfolio-prospective-oos-gate.md`

## portfolio-stress-corrected-calendar

- 상태: 완료. corrected simulation NAV에 고정 block-bootstrap stress를 1회 수행했습니다.
- 입력/설정: `simulation.json` SHA chain, seed `20260918`, block length 20 observations, horizon 1,171, CPU 512 scenarios.
- 결과: loss frequency `0.015625`, drawdown-20% frequency `0.0`, joint frequency `0.0`.
- audit: `/home/kwl/.local/share/jusik/portfolio-audit/portfolio-calendar-2026-krx-holiday-correction/stress-run-v1`; request SHA `1f0f707fe51ac8d2643873c9be53a88f0c021c64ba551fb53158247e3a57f7d6`, indices SHA `6bfee9901e80cb1e6ff09799b2568074d916ed4116f23f3600e7343799e690a7`.
- 제한: historical NAV block-bootstrap 기술통계이며 미래 확률·위험 실행·후보 승격·투자 권고가 아닙니다. PAPER/live·주문·runner는 실행하지 않았습니다.

## portfolio-performance-metrics-secondary

- 상태: 완료. corrected bundle의 simulation SHA를 검증한 뒤 거래 횟수·MDD 회복 기간을 추가하고, 거래별 realized P&L/하방 목표 근거가 없는 Profit Factor·최대 연속 손실·Sortino는 unavailable로 명시했습니다.
- 구현: `backend/jusik/research_portfolio_performance_metrics.py`, 테스트 `backend/tests/test_research_portfolio_performance_metrics.py`, commit `a03e6ba7bf4010875270ca417025b403a8ef76da` / main `2681caa`.
- 결과: trade count `171`, 최대 MDD 회복 기간 `23,707,800` UTC seconds (`P274DT9H30M0S`).
- 검증: focused regression pytest 54개, Ruff, strict mypy, diff 검사 통과. 기존 우선 지표와 envelope 호환성을 유지했습니다.
- 제한: Profit Factor·거래 기준 최대 연속 손실은 `missing_realized_trade_pnl`, Sortino는 `missing_downside_target_policy`입니다.

## portfolio-calendar-2026-krx-holiday-correction

- 상태: 완료. `exchange_calendars==4.12`의 2026년 KRX 임시·복원 공휴일 누락을 versioned XKRX closure override로 교정했습니다.
- 목표와 완료 조건: 2026-06-03(지방선거일)·2026-07-17(제헌절)을 versioned XKRX 휴장 override로 반영하고, 생성기·달력 parser·readiness/accounting 계약·회귀 테스트를 통과시킵니다. 기존 audit bundle은 수정하지 않고 새 calendar/source identity를 사용합니다.
- 담당: Astra 감독·통합, Luna 단일 구현, Terra 독립 review.
- 워크트리/브랜치: 전용 worktree 제거. 구현 `1162889`, main 통합 `91d8d87`.
- 입력과 근거: fixed bundle의 XKRX 2개 누락 close, Yahoo KSC 6종목 bounded probe(두 날짜 모두 no bars), KRX 휴장 공지 근거(한국거래소 공지 보도 및 BOK 2026 holiday schedule).
- 수정 허용: `generate_market_calendar.py`, 직접 관련 parser/readiness tests, 계약 문서·개발 기록. 기존 bundle/canonical artifact·runner·metrics evaluator 정책은 변경하지 않습니다.
- 금지: NAV 보간·bar 합성·날짜 이동, 기존 bundle 덮어쓰기, strategy/engine/replay 변경, network cache/주문/PAPER/live/remote 변경.
- 중단 조건: 두 날짜가 KRX 휴장이라는 권위 근거와 일치하지 않거나, override가 XNYS·기존 session을 바꾸면 중단합니다.
- 검증: generator output hash `5ac707711cb82f7849b7824567515f67dcbaad162452757b6727cccb9e20f2bd`, calendar parser 10 tests 통과. 추가 독립 review와 새 bundle preflight를 다음 단계에서 수행합니다.
- 결과: 기존 bundle은 보존했습니다. 새 calendar SHA로 별도 input preflight·independent accounting을 통과한 뒤에만 metrics adapter를 재개합니다. 개발 기록은 `docs/development-records/2026-09-18-portfolio-calendar-2026-krx-holiday-correction.md`입니다.

## portfolio-performance-input-readiness

- 상태: blocker 원인 교정 완료·재검증 대기. 새 XKRX calendar에서 휴장일을 제외한 required close union과 stored NAV 1,172개가 일치하는지 별도 input preflight로 확인해야 합니다.
- 목표와 완료 조건: 전체 intraday NAV chronology는 MDD용으로 보존하면서 일일 수익률 표본을 사전 정의하고, 171 trades·cash·FX·fee/slippage를 독립 재구성해 1,172 stored NAV와 대사할 수 있는지 판정합니다. 두 근거가 모두 성립해야 후속 metrics adapter를 허용합니다.
- 담당: Astra 감독·계획·통합.
- 워크트리/브랜치: 없음. read-only blocker 기록으로 종료합니다.
- 기준/통합: `deae4acd0bef8b3f2d64a7d445f8f3f922ec7d1f` / local `main` merge `901ac636f93f37ff2b3ab2c6c03ae0bf640572f1`.
- 입력과 선행 작업: bundle manifest `eec4aae8ed3c0366e9d15fa84657004d0e25429e2815b05e8a4870727718520b`, engine/result/time sidecar, 기존 independent modeled-cost ledger와 metrics policy.
- 수정 허용: blocker 개발 기록·계약 문서·등록부만. metrics/evaluator/code는 변경하지 않습니다.
- 금지: 저장 결과를 독립 근거로 자기인증, sampling policy 밖 표본 생성, 배당/세금/FX 실제 타당성 주장, 자동 성과 승격, bundle/canonical 수정, runner/network/KOFR/PAPER/live/주문/DB/service/config/remote 변경.
- 중단 조건: 새 달력에서도 required close/NAV가 불일치하거나 source/accounting SHA chain이 맞지 않으면 metrics adapter를 만들지 않습니다.
- 검증: source/bundle SHA, 독립 Decimal 원장, per-NAV residual, 다시장 날짜 경계·DST·조기/지연 폐장, sampling 결정성·비중복, tamper fail-closed, 독립 review를 요구합니다.
- 원장 계약: strategy/engine/replay를 호출하지 않고 persisted fills를 권위 입력으로 raw open·split·FX·fee/slippage·cash·positions·close marks를 Decimal precision 40으로 재구성합니다. 171 fills, 1,172 cash/NAV, terminal positions를 대사합니다.
- sampling 결정: 사용자 승인으로 UTC 날짜별 마지막 causally completed NAV를 CAGR/Sharpe/Calmar 표본으로 사용합니다. MDD는 1,172개 전체 chronology를 유지하며 UTC/Asia-Seoul 혼용 표본은 만들지 않습니다.
- 원장 결과: Luna 최종 `1845df55ddbebe16739f3ebe3c1d1735b2fd81a4`, Terra review PASS(P1/P2 없음). 171 fills와 1,172 cash/NAV, terminal positions를 독립 재구성해 최대 잔차 `0 KRW`입니다.
- 통합 검증: accounting/time-evidence/metrics pytest 53개, Ruff check/format, strict mypy, fixed bundle CLI, diff 검사 통과. audit report SHA `7390e79432319f834ff92f029833b9afd74839944909c711a60fee888037bad1`.
- 남은 조건: KOFR/risk-free evidence 없이는 Sharpe를 unavailable로 유지합니다. readiness 자동 승격·R4 canonical 주장은 금지합니다. 개발 기록은 `docs/development-records/2026-09-18-portfolio-performance-input-readiness.md`입니다.
- blocker 원인: 두 시각은 KRX 지방선거일·제헌절 휴장으로 확인되어 달력 override로 제거했습니다. 새 bundle 검증 전에는 metrics adapter·성과 계산·readiness 승격을 구현하지 않습니다.

## portfolio-performance-input-readiness-corrected-calendar

- 상태: 완료. corrected bundle manifest/calendar identity를 등록하고 independent accounting을 통과했습니다.
- 목표와 완료 조건: corrected bundle manifest/calendar/source SHA를 별도 등록하고 기존 원장 계약으로 171 fills·1,172 cash/NAV·terminal positions를 재대사합니다. 기존 canonical bundle과 readiness identity는 보존합니다.
- 수정 허용: accounting verifier의 등록 identity 확장, 직접 관련 tests·개발 기록·등록부. metrics 계산/승격은 원장 통과 후 별도 작업입니다.
- 금지: old bundle 덮어쓰기, NAV 보간·세션 합성, evaluator 우회, runner/network/order/PAPER/live/remote 변경.
- 입력: corrected bundle manifest `e5aa5af8a2c3a21696f395987216cae6ca002093a1138127449d09b54cf01600`, calendar bytes `36b64e421192062ff183112d1eef7d441af6e0f73cfaf739310b0b5ab8c281e1`, payload `5ac707711cb82f7849b7824567515f67dcbaad162452757b6727cccb9e20f2bd`.
- 검증: corrected generation/verification 1회씩, accounting `verified`(171 fills·1,172 NAV·residual 0), focused pytest 14개, Ruff/strict mypy 통과. verifier source SHA `0aa01d5cba655220ab6548db3485589c59851974ee09c06463f9bb43b67c73d6`.
- 다음 의존 작업: metrics adapter의 UTC daily sampling 및 CAGR/MDD/Sharpe/Calmar 계산. KOFR 없이는 Sharpe unavailable이며 readiness 승격은 별도 판정입니다.

## portfolio-performance-metrics-corrected-calendar

- 상태: 완료. corrected bundle SHA chain을 검증하고 UTC daily/full chronology projection으로 CAGR·MDD·Calmar를 계산하는 historical approximate envelope를 생성했습니다. Sharpe는 `missing_risk_free_evidence`로 unavailable입니다.
- 구현: `backend/jusik/research_portfolio_performance_metrics.py`, 테스트 `backend/tests/test_research_portfolio_performance_metrics.py`, commit `fb3976b9156d8227f23ab49047ed03a51a102c7d` / main `e9a0524`.
- 입력: corrected manifest/accounting report/calendar identity만 허용. accounting verifier 정확히 1회 호출; old canonical/evaluator/readiness/runner는 변경하지 않았습니다.
- 검증: full NAV 1,172, UTC daily 614, focused 및 회귀 pytest 52개, Ruff, strict mypy, diff 검사 통과.
- 제한: modeled-cost historical approximate 결과입니다. strict/PIT/R4/경제 평가/후보 채택/readiness 승격이 아니며 KOFR·법정 비용·배당·세금 주장은 없습니다.

## portfolio-calendar-aware-time-input

- 상태: 완료. optional 공식 calendar 시간 정책과 bounded lexical 한도를 local `main`에 통합했습니다.
- 목표와 완료 조건: 공식 calendar가 정의한 실제 session open/close를 engine event ordering에 사용하고, 고정 frozen input을 bounded하게 수용할 수 있는 근거 기반 JSON 자원 한도를 적용합니다. 신호·체결·NAV chronology와 기존 합성/일반 동작을 보존한 새 execution identity를 요구합니다.
- 담당: Astra 감독·계획·통합, Luna 단일 구현, Terra 독립 review.
- 워크트리/브랜치: `/home/kwl/projects/jusik-portfolio-calendar-aware-time-input` / `feat/portfolio-calendar-aware-time-input`.
- 기준/통합: `0805c7a07b004d7a53a53b0946c21e7b8a8aa12e` / local `main` merge `81a7377a8a52568dc4d7d9b508138f1959595d76`.
- 입력과 선행 작업: `forward-simulation-time-evidence-run`의 NO-GO 조사, `research_portfolio_engine.py`, `research_portfolio_time_evidence.py`, tracked calendar, fixed rebalance-band source manifest.
- 수정 허용: engine/calendar injection seam, time-evidence adapter의 bounded input policy, 직접 관련 tests·계약 문서·개발 기록. 등록부와 handoff는 Astra만 수정합니다.
- 금지: bar 삭제·시장 제외·날짜 이동·검증 완화, 전략/비용/리밸런싱 정책 변경, 기존 결과 재해석, 실제 simulation 실행, runner/network/KOFR/PAPER/live/주문/DB/service/config/remote 변경.
- 중단 조건: calendar 시각이 event ordering에 결정적으로 주입되지 않거나 자원 한도가 근거 없이 무제한화되거나 기존 replay/result 호환성을 깨야 하면 구현하지 않습니다.
- 검증: 지연 개폐장·일반장·다시장·warmup·DST/조기폐장, lexical/bytes/depth/row 한도 경계, event causality, 결정성, 기존 회귀, 독립 review를 요구합니다.
- 계획: `calendar=None`은 legacy 결과를 exact 보존하고, official mode만 전체 bar session을 선검증해 engine event/known-bar/volatility/target 계산에 같은 시각을 주입합니다. 새 execution identity로 구분합니다.
- 자원 계약: lexical token 상한만 `100,000`에서 `400,000`으로 올리고 기존 1/20/50MiB·depth64·object/list 한도와 사전거부를 유지합니다. fixed input은 parse/event-plan preflight까지만 허용합니다.
- 결과: Luna 최종 `8d02c9638e9b464d1da58d3189355117a57e5999`, Terra review PASS(P1/P2 없음). main focused pytest 68개, Ruff check/format, strict mypy, diff 검사가 통과했습니다.
- preflight: 16 instruments, 11,321 bars, 7,946 external observations, 20,303 events를 0.734초/105,628KiB에 검증했고 simulation은 0회입니다. audit manifest SHA는 `7a2ddb3488d1bc08d155411122e8727c84a67db9b1150a3df7ef504acf207af4`입니다.
- 정리·기록: 통합 검증 후 전용 worktree와 branch를 제거합니다. 개발 기록은 `docs/development-records/2026-09-18-portfolio-calendar-aware-time-input.md`, handoff는 루트 `HANDOFF.md`입니다.

## forward-simulation-time-evidence-run

- 상태: 완료. 동일 고정 입력과 official timing으로 새 historical time-evidence bundle을 정확히 한 번 생성·검증했습니다.
- 목표와 완료 조건: 기존 승인된 입력·정책·달력만 사용한 bounded simulation을 정확히 한 번 실행하고, 새 audit 경로의 bundle/manifest/SHA를 검증합니다. 기존 canonical run은 수정하지 않으며 readiness 연결 여부는 별도 판정합니다.
- 담당: Astra 감독·계획·통합, Luna 단일 실행/필요한 최소 구현, Terra 독립 review.
- 워크트리/브랜치: `/home/kwl/projects/jusik-forward-simulation-time-evidence-run` / `feat/forward-simulation-time-evidence-run`.
- 기준/통합: `818120c92aea5aa929a77c1329a96c827d89c1c7` / local `main` merge `d34f1ad381c32f1981a5d0f757ebbee9dcbec993`.
- 입력과 선행 작업: `research_portfolio_time_evidence.py`, 현재 mandate/governance, 고정 `PortfolioInput`·simulation config·공식 calendar, 기존 time-evidence 계약.
- 수정 허용: 실행 요청 artifact, 격리 audit bundle, 검증/연결에 필요한 최소 adapter·tests·계약 문서·개발 기록. 등록부와 handoff는 Astra만 수정합니다.
- 금지: 기존 canonical run/artifact 수정, 자동 runner resume, 네트워크 수집, KOFR 재요청, PAPER/live/주문/운영 DB/service/config/remote 변경, 자동 성과 승격.
- 중단 조건: 승인된 고정 입력·공식 달력·정책 identity가 없거나 새 simulation이 기존 미래정보/자료등급 계약을 보존하지 못하면 실행하지 않고 필요한 입력을 기록합니다.
- 검증: 입력 SHA·정책 identity·단일 simulate 호출·UTC 인과·manifest 전체 파일 SHA·결정성·no-overwrite·독립 review·main 영향 검사를 요구합니다.
- 차단 근거: source manifest SHA `1a2934466efa12c09d08e7792b1a5e4b7c0c880d2aaabab9b25919bd0ec5c825`, calendar SHA `ba26619a27e066ca32b1aaaf3b7da2b99f0c6658f731a000c5095c057081c1d8`; frozen input 4,557,232 bytes/324,691 lexical tokens, 11,321 bars/7,946 external observations. bundle·request·simulation은 생성하지 않았습니다.
- 재개 조건: 충족. `portfolio-calendar-aware-time-input`이 `81a7377a8a52568dc4d7d9b508138f1959595d76`에 통합되고 fixed input preflight가 통과했습니다. 다음 단계는 새 경로의 단일 generate입니다.
- 결과: Luna 문서 커밋 `d1dd68b2928c00bec0f94bab76316061ce6fca60`, Terra review PASS(P1/P2 없음). bundle manifest SHA는 `eec4aae8ed3c0366e9d15fa84657004d0e25429e2815b05e8a4870727718520b`입니다.
- 실행: generation 1회/exit0/2.75초/132,416KiB, verify 1회/exit0/simulation0회. event 16,824, NAV 1,172, trade 171이며 official UTC 인과가 통과했습니다.
- 제한: historical/approximate technical evidence입니다. prospective/PIT/canonical/R4 경제 근거, 성과 계산, readiness 승격이 아닙니다.
- 정리·기록: 통합 검증 후 전용 worktree와 branch를 제거합니다. 개발 기록은 `docs/development-records/2026-09-18-forward-simulation-time-evidence-run.md`, handoff는 루트 `HANDOFF.md`입니다.

## market-research-mandate-digest-repair

- 상태: 완료. 기준 커밋에서도 재현된 `docs/market-research.md`와 mandate hash manifest의 digest drift를 최소 수정했습니다.
- 목표와 완료 조건: 현재 tracked 문서 bytes의 SHA-256을 manifest에 정확히 반영하고, governance가 invalid가 아닌 원래 disabled/not-ready fail-closed 분기로 돌아가며 관련 전체 테스트가 통과해야 합니다.
- 담당: Astra 감독·통합, Luna 단일 구현, Terra 독립 review.
- 워크트리/브랜치: `/home/kwl/projects/jusik-market-research-mandate-digest-repair` / `fix/market-research-mandate-digest-repair`.
- 수정 허용: `docs/market-research-mandate.sha256`, 신규 개발 기록, 필요한 경우 digest 회귀 test만. 등록부와 handoff는 Astra만 수정합니다.
- 금지: mandate/roadmap 정책·문서 내용 변경, runner enable/resume, queue/DB/service/config/연구/PAPER/live/주문/remote 변경.
- 중단 조건: drift가 단순 tracked document update가 아니거나 새 digest가 다른 manifest entry·policy identity를 무효화하면 hash만 덮지 않고 원인을 기록합니다.
- 검증: governance와 roadmap 전체 관련 test, manifest 직접 SHA 대사, runner 중지 상태, diff 검사.
- 결과: Luna 구현 `a05bc05ea84b8e2e28ef0a108cee8d6df31e310f`, Terra review PASS(P1/P2 없음), local main merge `36a7cff127e34137b5d36eba5918099902e9a887`.
- 통합 검증: governance+roadmap 34개, 인접 runner/planning/approximate 121개, 직접 validator/digest/diff 검사가 통과했습니다. dispatch는 disabled fail-closed입니다.
- 정리·기록: 통합 검증 후 전용 worktree와 branch를 제거합니다. 개발 기록은 `docs/development-records/2026-09-18-market-research-mandate-digest-repair.md`, handoff는 루트 `HANDOFF.md`입니다.

## r2-canonical-nav-reconciliation-decision

- 상태: 완료. 기존 canonical 증거에 따라 `R2-05`만 고정 canonical approximate 범위의 기술 pass로 기록했습니다.
- 목표와 완료 조건: 고정 XNYS 기간의 expected/observed 252/252 ordered sessions, 구성요소 projection 최대 residual `5E-20 KRW`, 독립 modeled ledger residual `0 KRW`를 재검증한 뒤 `R2-05`만 canonical approximate 기술 pass로 기록합니다.
- 담당: Astra 감독·계획·통합, 필요 시 Luna 문서 구현, Terra 독립 review.
- 워크트리/브랜치: `/home/kwl/projects/jusik-r2-canonical-nav-reconciliation-decision` / `docs/r2-canonical-nav-reconciliation-decision`.
- 기준/통합: `8ceaa8a3c02fc405a6522c274dc2e605aa846f44` / local `main` merge `c2a16e87800f8695c70b6b47b7c0bb2a26cc7417`.
- 입력과 선행 작업: `r2-canonical-nav-evidence-connection`, R0 session/cost evidence, R2-05 정확한 roadmap 문구, generic/canonical NAV reconciliation 계약.
- 수정 허용: roadmap의 R2-05 판정·증거 문구, NAV reconciliation 계약 문서, 신규 개발 기록과 focused contract/parser test가 필요할 때만 해당 테스트. 등록부와 handoff는 Astra만 수정합니다.
- 금지: R2-01/02/03/04/06 또는 R2 전체 완료 주장, 배당·FX·실제 비용/세율·timestamp·risk-free·benchmark·미래 검증 추정, 성과 재계산, canonical artifact 변경, 연구/runner/PAPER/live/주문/DB/service/config/remote 변경.
- 중단 조건: `모든 거래일`을 fixed XNYS expected sessions로 해석할 수 없거나 residual 근거가 저장된 구성요소 자기일관성 이상을 주장해야 하면 체크하지 않고 기존 제한을 유지합니다.
- 검증 계약: canonical session/cost/NAV CLI, 관련 pytest와 roadmap parser를 실행하고 실제 `load_roadmap()`에서 `R2-05`만 새로 완료인지 확인합니다.
- 결과: 문서 구현 `004eab545267958882ae42bccc64ccc3ddf56c95`; R2-05만 체크하고 다른 R2·전체 R2·readiness/economic 상태를 보존했습니다.
- 검토·검증: Terra PASS(P1/P2 없음). main에서 focused pytest 114개+roadmap parser 2개, 두 canonical CLI, `load_roadmap()` 직접 판정과 diff 검사가 통과했습니다.
- 기존 실패: 전체 roadmap test의 governance 3건은 기준 커밋에서도 동일하게 재현된 `market-research.md` digest drift이며 별도 작업입니다.
- 정리·기록: 통합 검증 후 전용 worktree와 branch를 제거합니다. 개발 기록은 `docs/development-records/2026-09-18-r2-canonical-nav-reconciliation-decision.md`, handoff는 루트 `HANDOFF.md`입니다.

## r2-canonical-nav-evidence-connection

- 상태: 완료. canonical 전용 adapter와 좁은 session evidence verifier를 local `main`에 통합했습니다.
- 목표와 완료 조건: 동일 run/dataset/기간/SHA임을 먼저 증명하고, canonical 경로에서만 calendar와 independent modeled-accounting availability를 검증된 사실로 바꿉니다. 일반 입력 판정과 residual·누락·경제 평가 의미는 보존합니다.
- 담당: Astra 감독·계획·통합, Luna 단일 구현, Terra 독립 review.
- 워크트리/브랜치: `/home/kwl/projects/jusik-r2-canonical-nav-evidence-connection` / `feat/r2-canonical-nav-evidence-connection`.
- 기준/통합: `ae79f071bece134442e33669b08d2eae9d9530d4` / local `main`.
- 입력과 선행 작업: `research_nav_reconciliation.py`, R0 session evidence, R0 modeled-cost evidence, frozen canonical manifest/run, 기존 drawdown chronology 진단.
- 수정 허용: `market_performance_readiness.py`의 좁은 canonical session verifier, 신규 canonical NAV adapter, focused tests, `docs/research-nav-reconciliation.md`, 신규 개발 기록. 등록부와 handoff는 Astra만 수정합니다.
- 금지: 배당 완전성·실제 비용/세율 타당성 주장, latch/release·benchmark·미래 관찰 합성, 기존 canonical 수정·성과 재계산, strategy/runner/PAPER/live/주문/운영 DB/service/config/remote 변경.
- 중단 조건: 두 R0 evidence가 R2 대상과 동일 SHA·기간·NAV를 증명하지 못하거나 unavailable 항목을 검증 없이 제거해야 하면 통합하지 않습니다.
- 검증 계약: 고정 run bytes를 한 번 대사하고 session/cost verifier를 각각 한 번 호출해 run·manifest·기간·ordered 252 sessions·dataset SHA·106 trades·252 NAV를 fail-closed로 연결합니다. 전체 readiness와 회계 수식을 재실행하지 않습니다.
- 보존 계약: 일반 reconciliation의 calendar/accounting unavailable, residual, approximate, economic not-evaluated와 기존 checkbox를 그대로 유지합니다.
- 결과: Luna 구현 최종 `81ad631ee4e476827deda91a0496e3a311a2a278`. 실제 consumer bounded-read, path alias 거부, source/evidence self-pin과 stable error 분류를 포함합니다.
- 검토·통합: Terra 최종 review PASS(P1/P2 없음), local main merge `3af356aca45361acf3c193f4c71405fd3210233c`. main focused pytest 114개, Ruff check/format, strict mypy, cost/canonical NAV CLI와 diff 검사가 통과했습니다.
- 정리·기록: 통합 검증 후 전용 worktree와 branch를 제거합니다. 개발 기록은 `docs/development-records/2026-09-18-r2-canonical-nav-evidence-connection.md`, handoff는 루트 `HANDOFF.md`입니다.

## r1-corporate-action-accounting-readiness

- 상태: 차단. 현재 고정 자료는 배당 유효·지급 경계와 확정 권리수량을 증명하지 못하며, 기존 회계 엔진·artifact adapter가 누락·중복·실패 상태를 이미 fail-closed로 보존하므로 중복 구현하지 않습니다.
- 목표와 완료 조건: 외부 수집 없이 사용할 수 있는 고정 artifact와 코드 경계를 확인하고, 배당 중복계상 0·분할 전후 자산보존을 검증하기 위한 최소 입력 계약과 명시적 blocker를 확정합니다. 근거 없는 action 금액·지급일·수량은 합성하지 않습니다.
- 담당: Astra 감독·계획·통합, 필요 시 Luna 단일 구현·Terra 독립 review.
- 워크트리/브랜치: 없음. 읽기 전용 조사·계획으로 종료했습니다.
- 입력과 선행 작업: 기존 `r1-artifact-db6987` 기술 slice, market action models, approximate missing policy, independent accounting/cost ledger, frozen R0 artifacts.
- 수정 허용: 차단 결정의 개발 기록과 등록부만. production·test는 변경하지 않습니다.
- 금지: 실제 provider/network 수집, 배당·분할 추정, 기존 canonical run 수정·성과 재계산, 전략 후보 변경, runner/PAPER/live/주문/운영 DB/service/config/remote 변경.
- 중단 조건: 지급일·권리수량·중복 방지 identity를 고정 artifact에서 증명할 수 없고 유용한 fail-closed 계약도 남지 않으면 구현하지 않고 차단 근거만 기록합니다.
- 차단 근거: 공통 model에는 dividend/ex/pay/entitlement가 없고, 별도 collector의 vendor date·amount/currency만으로 지급 경계와 권리수량을 결정할 수 없습니다. 기존 accounting은 이 필드를 명시적으로 요구하며 action identity·semantic replay/conflict를 이미 검증합니다.
- 재개 입력: 원문 SHA·관측시각에 묶인 stable action identity, split ratio와 raw 전후 가격, dividend 금액·통화·유효/지급 UTC 경계, 권리 경계의 확정 보유수량·체결 순서. vendor date나 종가 보유량으로 추정하지 않습니다.
- 결과: 테스트·외부 수집 없이 read-only 근거를 확인했습니다. `R1-04`는 미체크, coverage incomplete/economic not-evaluated를 유지합니다. 개발 기록은 `docs/development-records/2026-09-18-r1-corporate-action-accounting-readiness.md`, handoff는 루트 `HANDOFF.md`입니다.

## r1-us-coverage-retention

- 상태: 완료. 기존 가격 진단에서 누락된 failed membership-checkpoint 구간을 당시 incumbent별 `membership_unknown`으로 보존하는 호환 확장을 통합했습니다. 실제 receipt가 없어 `R1-05` 전체 checkbox는 유지합니다.
- 목표와 완료 조건: universe→수집→정규화→strategy candidate 흐름에서 제외·결측 symbol의 identity, 기간, 원인, 관측시각과 자료 등급이 끝까지 남는지 대사하고, silent drop을 fail-closed로 검출하는 최소 계약을 구현합니다.
- 담당: Astra 감독·계획·통합, Luna 단일 구현, Terra 독립 review.
- 워크트리/브랜치: `/home/kwl/projects/jusik-r1-us-coverage-retention` / `feat/r1-us-coverage-retention`.
- 입력과 선행 작업: R1-01 membership, R1-02 event-time slice, R1-03 product types, R1-06 provider fixtures, 현재 coverage/missing_ranges/candidate evidence 계약.
- 수정 허용: `market_history_approximate.py`의 optional gap 진단 모델, `market_data_collector.py`의 기존 checkpoint 경계 연결, 직접 관련 tests, `docs/market-research.md`, 신규 개발 기록. 전략·snapshot/result/replay schema는 변경하지 않습니다. 등록부는 Astra만 수정합니다.
- 금지: 실제 provider/network 수집, 누락 symbol 대체·가격 합성, 과거 canonical 수정, 전략·성과·후보 선택 변경, 배당/분할 회계, runner/PAPER/live/주문/운영 DB/service/config/remote 변경.
- 중단 조건: upstream identity와 downstream coverage를 결정적으로 연결할 근거가 없거나 통과를 위해 결측을 정상으로 재분류해야 하면 구현하지 않고 blocker를 기록합니다.
- 계약: gap은 실패 checkpoint·기존 달력의 비중첩 session 구간/count·그 시점 incumbent symbols·`alpha_vantage`·`unknown`만 보존합니다. 가격 coverage 수치에는 합산하지 않고, gap symbol union과 `membership_unknown` reason-bearing diagnostics를 exact 대사합니다.
- 호환: 신규 필드 기본값은 빈 tuple이며 빈 값은 직렬화에서 생략해 legacy JSON/replay를 보존합니다. 첫 checkpoint 실패의 기존 중단과 이후 pool·전략 결과는 바꾸지 않습니다.
- 제한: 실제 receipt·실패 원인·delisting/removal/replacement를 합성하지 않으며 자기일관적 진단 삭제는 별도 upstream receipt 없이 검출할 수 없습니다.
- 결과: Luna 구현 `cd70ec6`, exact session tuple/count 무결성 보완 `a47b1a8`. 후속 checkpoint 실패의 비중첩 gap·incumbent·reason 대사와 legacy empty-field 호환을 추가했습니다.
- 검토·통합: Terra 최종 review PASS(P1/P2 없음), local main merge `adb41e1e20c3e8aa92c9f4d939d7d794ab607106`. main에서 collector/approximate/replay pytest 182개, Ruff check, 관련 production mypy, diff 검사가 통과했습니다.
- 정리·기록: 통합 검증 후 전용 worktree와 branch를 제거합니다. 개발 기록은 `docs/development-records/2026-09-18-r1-us-coverage-retention.md`, handoff는 루트 `HANDOFF.md`입니다.

## r1-us-event-time-invariance

- 상태: 완료. production 변경 없이 safe paired fixture와 계약 문서로 사건 전 불변성을 강화했습니다. 실제 historical receipt가 없어 `R1-02` 전체 checkbox는 유지합니다.
- 목표와 완료 조건: 기존 R1 PIT membership과 action/delisting 소비 경로를 조사해 관측시각 cutoff를 하나의 계약으로 고정하고, 미래 event 주입 전후의 사건 전 선택·분류·coverage가 exact equality임을 safe fixture로 증명합니다. 자료가 없는 event 종류는 지원된 것으로 가장하지 않고 명시적 missing/unsupported로 남깁니다.
- 담당: Astra 감독·계획·통합, Luna 단일 구현, Terra 독립 review.
- 워크트리/브랜치: `/home/kwl/projects/jusik-r1-us-event-time-invariance` / `feat/r1-us-event-time-invariance`.
- 입력과 선행 작업: R1-01 PIT membership, R1-03 structured security type, R1-06 provider failure fixture, market history action/delisting models와 현재 selection pipeline.
- 수정 허용: `backend/tests/test_market_data_collector.py`, `backend/tests/test_market_history_approximate.py`, `docs/market-research.md`, 신규 개발 기록만. production code와 roadmap checkbox는 변경하지 않습니다. 등록부는 Astra만 수정합니다.
- 금지: 실제 provider/network 수집, 과거 canonical artifact 수정, 실패 symbol 대체, 배당·분할 현금/가격 회계 구현, 전략·성과·후보 선택 변경, runner/PAPER/live/주문/운영 DB/service/config/remote 변경.
- 중단 조건: 기존 selection 경로에서 event 관측시각을 구분할 근거가 없거나 fixture 통과를 위해 미래 event를 삭제·무시하는 방식이 필요하면 구현하지 않고 정확한 blocker를 기록합니다.
- 검증 계약: 사건 전 동일 종료시각 요청은 universe/bars/membership/non-empty candidate evidence/classification/status/grade/missing/coverage/diagnostics exact equality입니다. 전체 기간은 cutoff 전 prefix equality와 cutoff 뒤 대상 종목만 제외되는 양성 대조를 분리하고, 전체 coverage equality는 요구하지 않습니다.
- 제한: synthetic `observed_at`은 실제 historical receipt가 아니며 suspension·배당/분할 회계와 strict PIT는 미지원입니다.
- 결과: Luna 구현 `a6f8d05`, 비공허 양성 대조 보완 `ea8e7ef`; 3 event kind × 2 timing case에서 사건 전 exact equality와 cutoff 뒤 target-only exclusion을 검증했습니다.
- 검토·통합: Terra 최종 review PASS(P1/P2 없음), local main merge `91cb1bbe5c2290cb661bdb2c5ed04e9b352422d5`. main에서 두 테스트 파일 167개, Ruff check, 관련 production mypy, diff 검사가 통과했습니다. 파일 전체 Ruff format은 기존 범위 밖 차이 때문에 실행 결과를 gate로 사용하지 않았습니다.
- 정리·기록: 통합 검증 후 전용 worktree와 branch를 제거합니다. 개발 기록은 `docs/development-records/2026-09-17-r1-us-event-time-invariance.md`, handoff는 루트 `HANDOFF.md`입니다.

## forward-simulation-time-evidence

- 상태: 완료. 기존 엔진·결과 schema를 바꾸지 않는 opt-in 신규 simulation bundle과 time-evidence sidecar를 local `main`에 통합했습니다.
- 목표와 완료 조건: market calendar의 실제 session open/close UTC와 전략 평가 시점을 명시적으로 연결한 forward-only artifact contract를 추가하고, initial-capital event·per-NAV timestamp·생성 정책·source SHA를 재현 가능하게 검증합니다. 기존 canonical readiness는 바꾸지 않으며 새 run도 자동 canonical 승격하지 않습니다.
- 담당: Astra 감독·계획·통합, Luna 단일 구현, Terra 독립 review.
- 워크트리/브랜치: `/home/kwl/projects/jusik-forward-simulation-time-evidence` / `feat/forward-simulation-time-evidence`.
- 입력과 선행 작업: `MarketSession.open_at/close_at`, 전략 loop의 close-mark NAV 생성 순서, `MarketResearchRun`/replay schema, 기존 session/cost/policy evidence와 blocked readiness.
- 수정 허용: 신규 time evidence model·opt-in generation/verification adapter, focused tests, 신규 계약 문서, 성과지표 문서 링크와 개발 기록. 기존 engine·simulation/result/run/replay schema와 저장소는 수정하지 않습니다. 등록부는 Astra만 수정합니다.
- 금지: 기존 canonical run timestamp 합성·수정, 기존 readiness 누락 제거, 경제 성과 계산·승격, 전략 신호·체결·비용 수식 변경, 신규 연구 자동 실행, runner/PAPER/live/주문/운영 DB/service/config/remote 변경.
- 중단 조건: 실제 NAV 평가 event와 timestamp 의미를 코드 흐름에서 일대일로 정의할 수 없거나 기존 run/replay 호환성을 깨야 하면 구현하지 않고 차단합니다.
- 생성 계약: 초기자본은 earliest engine event와 같은 UTC instant의 `engine_event_anchor`이며 event 처리 전 논리 순서입니다. NAV는 기존 `evaluation_at`을 보존하고 실제 session open/close를 별도 근거로 연결하며 `close_at <= evaluation_at`을 fail-closed 검증합니다.
- 출력·검증: 신규 디렉터리에 입력·설정·calendar bytes·기존 simulation 결과·time sidecar·manifest를 원자적으로 생성하며 덮어쓰지 않습니다. 합성 XNYS/XKRX·DST·조기/지연폐장·다종목 묶음과 변조·경로 공격을 검증합니다. 실제 연구 generation은 실행하지 않습니다.
- 결과: Luna 최종 구현 `d83b204`는 opt-in bundle 생성·검증, strict time model, 달력 인과 검증, 원자적 no-overwrite 게시, bounded JSON·artifact 검증과 45개 worker 회귀를 포함합니다.
- 검토·통합: Terra 최종 review PASS(P1/P2 없음), local main merge `de667503586b7cab025192a2f89b0e57be3b28fb`. main에서 time-evidence/portfolio/calendar/replay pytest 58개, Ruff check/format, focused configured mypy, diff 검사가 통과했습니다. full mypy의 기존 `research_optimizer.py` `torch` stub 부재는 작업 범위 밖입니다.
- 정리·기록: 통합 검증 후 전용 worktree와 branch를 제거합니다. 개발 기록은 `docs/development-records/2026-09-17-forward-simulation-time-evidence.md`, handoff는 루트 `HANDOFF.md`입니다.

## kofr-risk-free-source-evidence

- 상태: source evidence 기술 slice 완료·성과 적용 차단. 공식 원문 245행을 확보하고 parser 보완 후 offline replay로 evidence·verification·manifest를 생성해 local main에 통합했습니다. `missing_risk_free_evidence` 제거와 Sharpe/readiness 승격은 별도 application evidence가 없어 보류합니다.
- 목표와 완료 조건: canonical NAV 통화인 KRW와 일치하는 KOFR 일별 금리의 공식 원문을 bounded하게 수집하고, 요청·응답·공표시각·원문 SHA·정규화 결과를 검증 가능한 evidence로 고정합니다. source evidence만 확정하며 `missing_risk_free_evidence` 제거, Sharpe 계산, readiness 승격은 하지 않습니다.
- 담당: Astra 감독·계획·통합, Luna 단일 구현, Terra 독립 review.
- 워크트리/브랜치: `/home/kwl/projects/jusik-kofr-risk-free-source-evidence` / `feat/kofr-risk-free-source-evidence`.
- 기준 커밋/통합 대상: 이 등록 commit / local `main`.
- 입력과 선행 작업: 한국은행의 KOFR 공식 정의·공표 절차, `https://www.kofr.kr/`의 KSD 공시 화면과 `getGridRateExcelList` 공식 응답, canonical 기간 `2025-09-11~2026-09-11`, 기존 blocked readiness와 계산정책.
- 수정 허용: 신규 bounded KOFR collector/parser/verifier, content-addressed raw·정규화 evidence artifact, focused tests, 성과지표 계약 문서와 신규 개발 기록. 필요할 때 readiness에는 source evidence의 존재만 표시하되 누락 code와 blocked 상태는 보존합니다. 등록부는 Astra만 수정합니다.
- 수집 경계: 공식 `kofr.kr` HTTPS 한 host·한 action만 허용하고, canonical 기간만 요청하며 timeout·응답 크기·MIME·XML entity/DTD·중복 날짜·비유한 값·공표시각을 fail-closed 검증합니다. 자동 재시도와 운영 DB 사용은 금지합니다.
- 금지: 과거 NAV/초기자본 timestamp 합성, KOFR을 interval return에 연결, scalar 축약, CAGR/MDD/Sharpe/Calmar 계산, readiness 누락 제거·등급 승격, 기존 evaluator/전략/runner/API 변경, PAPER/live/주문/서비스/config/remote 변경.
- 중단 조건: 공식 단일 응답의 전체 수신·선언 행수·요청 범위·필수 공표 필드·재정규화를 검증할 수 없거나 source evidence를 적용 근거와 분리할 수 없으면 통합하지 않습니다. 별도 KOFR 영업일 달력이 없으므로 기대 영업일 완전성은 `unverified`로 고정하며 이를 완료 조건으로 주장하지 않습니다.
- 포트·테스트 DB·출력 경로: 포트·DB 해당 없음. 테스트는 fake transport만 사용하고, 실제 bounded 수집은 작업 전용 audit 경로에 저장한 뒤 필요한 불변 artifact만 추적합니다.
- 검증·결과: 최종 후보 `8dc93fc`, main 통합 `d96c609`; 표준 라이브러리 fake harness 25개, 실제 raw offline replay 245행, Ruff check/format, strict mypy, governance 회귀 35개가 통과했습니다. readiness·metrics의 적용 경계와 runner는 변경하지 않았습니다.
- 후속 조사 정정: 공식 `rate/rate.jsp`와 `/js/common.js`에서 화면의 짧은 `rate.process.RatePTask`가 `_doTask`의 `ksd.rfr.user.` prefix로 전송됨을 확인했습니다. 따라서 기존 전체 task는 유효하며 시험 교정 `720f6dc`는 `4b6490f`에서 복구했습니다. 두 번째 bounded 요청은 XML 선언만 반환되어 `malformed_xml`로 fail-closed했고, audit `/home/kwl/.local/share/jusik/portfolio-audit/20260919-kofr-task-correction`에 raw/failure를 보존했습니다. 이후 읽기 전용 브라우저 요청에서 `submissionid`와 `Referer`가 실제 응답을 받는 필수 컨텍스트임을 확인해 후보에 반영했습니다. 조건을 넣은 공식 요청은 245행을 반환했으나 parser 제한으로 `malformed_vector`가 발생했고 raw SHA `cd22f321c16bd95b939c88f141465417cd9f86ba67df8cc538bc1e56be835184`를 보존했습니다. 최종 후보 `8dc93fc`의 offline replay로 evidence SHA `995f963074aa9fe2b83236b27d67f152ec4697780d851ba4ef14e9b3ed180337`를 생성했고 추가 네트워크 요청은 중단합니다.
- 보존·재개: `/home/kwl/projects/jusik-kofr-risk-free-source-evidence`와 `feat/kofr-risk-free-source-evidence`를 보존하며 main 통합은 `d96c609`입니다. source evidence의 application evidence는 별도 작업으로 등록하기 전 자동 성과 계산에 연결하지 않습니다. 개발 기록은 `docs/development-records/2026-09-17-kofr-risk-free-source-evidence.md`, handoff는 루트 `HANDOFF.md`입니다.

## kofr-application-evidence-contract

- 상태: 기술 slice 완료·실제 적용 자료 대기. source evidence와 application evidence를 분리하는 fail-closed manifest 검증을 main에 추가했습니다.
- 구현: `backend/jusik/kofr_application_evidence.py`, 테스트 5개, 개발 기록 `docs/development-records/2026-09-19-kofr-application-evidence-contract.md`.
- 계약: source SHA pin, `Asia/Seoul` local publication time, provider business-date completeness 명시, interval source value 일치, publication-before-interval-start를 요구합니다. 달력·평일 추정, 자동 carry-forward, Sharpe/readiness 연결은 하지 않습니다.
- 검증: focused pytest 5개, Ruff check/format, strict mypy 통과. 실제 KOFR source completeness가 아직 `unverified`이므로 application manifest·성과 계산·`missing_risk_free_evidence` 제거는 보류합니다.
- fail-closed 보강: `coverage_status=complete` manifest의 `business_dates`와 source rows 관측일 집합 exact equality를 요구합니다. 누락·추가 날짜는 `business_date_manifest_mismatch`로 거부하며, provider 전체 영업일 근거 부족 상태는 변경하지 않습니다. 보강 테스트 포함 application pytest 6개, Ruff/format, strict mypy 통과.
- NAV application preflight: `validate_nav_date_application`가 검증된 application report와 NAV 날짜를 exact 비교하고 미포함 NAV 날짜를 `nav_date_application_missing`으로 거부합니다. carry-forward·calendar 추론은 허용하지 않습니다. application pytest 7개, Ruff/format, strict mypy 통과.
- 추가 범위 진단: corrected NAV의 614개 UTC daily date는 `2024-04-24~2026-09-08`인데 현재 KOFR source는 `2025-09-11~2026-09-11`뿐이라 앞쪽 359개 날짜가 없습니다. 기간 축소·0 대체·자동 carry-forward 없이, 전체 기간 source를 별도 bounded 수집하거나 사전등록한 부분기간 평가를 선택해야 합니다.
- 추가 날짜 대사: 겹침 구간 `2025-09-11~2026-09-08`의 NAV daily 255개 중 KOFR 직접 일치일은 242개, 13개는 NAV에만 존재합니다. source 누락과 시장별 휴장 차이를 구분할 근거가 없으므로 Sharpe 표본을 조용히 삭제하거나 carry-forward하지 않고 별도 calendar/application 정책을 요구합니다.
- 원인 분류: 13개 NAV-only 날짜의 triggering close group은 모두 `XNYS` only이며 `XKRX` session은 없습니다. provider 결손으로 단정하지 않되, combined KRW NAV Sharpe에는 미국-only 날짜의 명시적 risk-free 적용 정책과 근거가 추가로 필요합니다.
- 공식자료 판정: KRX 표준 KOFR 설명서의 직전 영업일 대체금리는 산출업무 중단 비상계획 문맥입니다. 일반 XNYS-only 날짜 carry-forward 근거로 확장하지 않고 exact-date fail-closed를 유지합니다.

## r0-us-modeled-cost-evidence

- 상태: 완료. canonical R0 미국 run·dataset·cache의 고정 SHA를 사용해 저장된 모형 fee/slippage/sell-tax가 NAV에 포함됐는지 독립 대사했습니다.
- 목표와 완료 조건: strategy/replay 코드를 호출하지 않는 Decimal 회계로 106개 체결과 252개 세션의 native cash·KRW cash·invested·NAV를 잔차0으로 재구성하고, 검증된 canonical readiness에서만 `missing_cost_inclusion_evidence` 한 code를 제거합니다. 전체 상태는 blocked/metrics-disabled/not-evaluated, approximate 등급과 나머지 3개 누락은 유지합니다.
- 담당: Astra 감독·계획·통합, Luna 단일 구현, Terra 독립 review.
- 워크트리/브랜치: `/home/kwl/projects/jusik-r0-us-modeled-cost-evidence` / `feat/r0-us-modeled-cost-evidence`.
- 기준 커밋/통합 대상: 이 등록 commit / local `main`.
- 수정 허용: 신규 독립 cost verifier·불변 evidence JSON·focused tests, readiness 연결/tests, 성과지표 계약 문서와 신규 개발 기록. 등록부는 Astra만 수정합니다.
- 회계 범위: 최초 KRW를 첫 FX/spread로 환전, 보유0 시작, 저장 순서 체결, dataset open으로 fill/notional/fee/tax 재계산, close×보유수량 평가, slippage는 fill에 포함해 재차감하지 않습니다. 원본 run equity는 비교 대상으로만 사용합니다.
- 검증: manifest→run/dataset/cache/completion/raw84 SHA·경로·크기, 거래/세션/FX/mark/비용/수량/NAV 변조, 누락·중복차감·순서·초과매도·미청산, 환전 spread, Decimal context, evidence/verifier hash 우회, strategy/replay/broker 호출 금지를 검사합니다.
- 금지: 법정 요율·실제 전체 비용·배당/분할·생성 작업트리·체결시각 완전성 주장, 기업행사 추정, 연구/network/PAPER/live/주문/운영 DB/service/config/remote 변경, 로드맵 checkbox 변경.
- 중단 조건: canonical 잔차0이 재현되지 않거나 비용 포함 외 누락 code를 제거해야 하거나 금지 모듈을 재사용해야 하면 통합하지 않습니다.
- 결과: Luna 최종 구현 `ed3a494`, Terra 최종 review PASS, local main 통합 `40336c4`. main에서 cost/readiness/policy/metrics pytest 92개, Ruff/format, configured source mypy, diff 검사와 canonical CLI acceptance가 통과했습니다. 106개 체결·252개 세션 잔차0, 최종 보유0이며 비용 누락 한 code만 제거해 3개가 남았습니다.
- 정리: 통합 검증 후 전용 worktree와 branch를 정상 제거합니다. 개발 기록은 `docs/development-records/2026-09-17-r0-modeled-cost-evidence.md`, handoff는 루트 `HANDOFF.md`입니다.

## market-performance-calculation-policy

- 상태: 완료. 기존 성과 evaluator 수식·상수·Decimal 문맥을 forward re-evaluation용 versioned 정책과 상호 SHA pin으로 고정했습니다.
- 목표와 완료 조건: 정책 artifact bytes SHA와 evaluator 전체 source SHA를 양방향으로 검증하고, canonical readiness에서만 `missing_calculation_policy` 한 code를 제거합니다. 과거 run 적용은 `historical_application_proven=false`, 전체 상태는 blocked/metrics-disabled/not-evaluated, 나머지 4개 누락은 유지합니다.
- 담당: Astra 감독·계획·통합, Luna 단일 구현, Terra 독립 review.
- 워크트리/브랜치: `/home/kwl/projects/jusik-market-performance-calculation-policy` / `feat/market-performance-calculation-policy`.
- 기준 커밋/통합 대상: 이 등록 commit / local `main`.
- 수정 허용: 신규 policy JSON·loader·focused test, 기존 `market_performance_metrics.py`의 Decimal Context 명시, readiness 연결/tests, 성과지표 계약 문서와 신규 개발 기록. 등록부는 Astra만 수정합니다.
- 정책 범위: UTC 날짜 차이 CAGR 연365, 초기자본 포함 MDD, 초기자본→첫 NAV 포함 simple returns, annual RF의 일별 기하 변환·표본분산·연252 Sharpe, Calmar, MDD 0.20 hard filter, Decimal 문자열/null unavailable, 비용 재차감·세션 추정·등급 승격 금지를 고정합니다.
- 검증: 정책/소스 정상 pin, 정책 누락·변조·schema/크기/중복 key, 내부 source SHA만 갱신한 우회, evaluator 소스 drift, 임의 경로 우회, ambient DefaultContext 불변, 독립 oracle·경계, generic 7개/canonical 4개, 기존 세션 SHA chain 회귀를 검사합니다.
- 금지: 새 계산 DSL, 성과 수치 생성, 과거 정책 적용 주장, 기존 input/result 계약 파괴, 연구/network/PAPER/live/주문/운영 DB/service/config/remote 변경, 로드맵 checkbox 변경.
- 중단 조건: 기존 수치가 변하거나 정책 pin을 자동 갱신해야 하거나 남은 4개 근거를 추정해야 하면 통합하지 않습니다.
- 결과: Luna 최종 구현 `7361bf7`, Terra 최종 review PASS, local main 통합 `011e19b`. main에서 policy/metrics/readiness/calendar pytest 77개, Ruff/format, configured source mypy, diff 검사와 canonical CLI acceptance가 통과했습니다. canonical은 정책 근거 한 code만 제거해 남은 4개와 blocked 상태를 유지합니다.
- 정리: 통합 검증 후 전용 worktree와 branch를 정상 제거합니다. 개발 기록은 `docs/development-records/2026-09-17-market-performance-calculation-policy.md`, handoff는 루트 `HANDOFF.md`입니다.

## r0-us-session-evidence

- 상태: 완료. canonical R0 미국 approximate pilot의 요청 기간 NAV 날짜를 tracked XNYS 달력과 SHA 체인으로 대사했습니다.
- 목표와 완료 조건: 요청 기간 `2025-09-11~2026-09-11` 양끝 포함 XNYS 예상 252세션과 canonical equity 252행의 날짜·순서가 일치한다는 불변 증거를 추가하고, 검증된 canonical 경로에서만 readiness의 `missing_calendar_evidence`·`missing_session_completeness_evidence` 두 code를 제거합니다. 전체 상태는 blocked, `ready_for_metrics=false`, 경제 평가는 not-evaluated, 나머지 5개 누락은 유지합니다.
- 담당: Astra 감독·계획·통합, Luna 단일 구현, Terra 독립 review.
- 워크트리/브랜치: `/home/kwl/projects/jusik-r0-us-session-evidence` / `feat/r0-us-session-evidence`.
- 기준 커밋/통합 대상: 이 등록 commit / local `main`.
- 입력: R0 manifest SHA `03ff5a…1205`, canonical run SHA `cc9150…8275`, tracked calendar bytes SHA `ba2661…c1d8`·payload SHA `e9f86c…122d`; 실제 전체 값은 증거 파일과 검증 코드에 기록합니다.
- 수정 허용: 신규 `backend/jusik/data/r0_us_session_evidence_v1.json`, `backend/jusik/market_performance_readiness.py`, 기존 readiness focused tests, `docs/market-performance-metrics.md`, 신규 개발 기록. 등록부는 Astra만 수정합니다.
- 검증: 세 SHA 연결·달력 provider/version/기간·market/timezone·inclusive 날짜 의미·252/252·누락/초과0을 검증합니다. run/evidence/calendar 변조, 기간 변경, 세션 누락·중복·역순·휴장일·unavailable, 내부 hash만 재계산한 달력 변조, generic canonical 우회, 조기폐장/DST, 정확히 두 code 제거, 결정성·원본 불변을 검사합니다.
- 금지: synthetic stress worktree 통합, 달력 close를 NAV timestamp/초기자본 anchor로 사용, strict PIT·가격/기업행사/FX 완전성 주장, evaluator/전략/collector/runner/API 변경, 연구·network·PAPER/live·주문·운영 DB/service/config/remote 변경, 로드맵 checkbox 변경.
- 중단 조건: 고정 SHA나 252일 대사가 재현되지 않거나 두 code 외 준비 상태를 바꿔야 하면 통합하지 않습니다.
- 결과: Luna 최종 구현 `3d82d49`, Terra 최종 review PASS, local main 통합 `5e25aab`. main에서 readiness/calendar/metrics pytest 66개, Ruff/format, configured source mypy, diff 검사와 canonical CLI acceptance가 통과했습니다. 252/252 날짜·순서 일치로 두 누락 code만 제거됐고 나머지 5개 및 blocked 상태를 유지합니다.
- 정리: 통합 검증 후 전용 worktree와 branch를 정상 제거합니다. 개발 기록은 `docs/development-records/2026-09-17-r0-session-evidence.md`, handoff는 루트 `HANDOFF.md`입니다.

## market-performance-readiness

- 상태: 완료. canonical R0 미국 approximate pilot을 성과 입력으로 승격하지 않고, 현재 평가 차단 근거를 결정적 JSON으로 진단합니다.
- 목표와 완료 조건: SHA 고정 `MarketResearchRun`의 schema·NAV·등급·비용 가정을 검증하고 UTC anchor·NAV timestamp·세션 완전성·달력·비용 포함·무위험률·계산정책 근거 누락을 고정 code로 보고합니다. 정상적인 blocked 진단은 exit 0이며 성과 숫자와 hard-filter 판정은 만들지 않습니다.
- 담당: Astra 감독·계획·통합, Luna 단일 구현, Terra 독립 review.
- 워크트리/브랜치: `/home/kwl/projects/jusik-market-performance-readiness` / `feat/market-performance-readiness`.
- 기준 커밋/통합 대상: 이 등록 commit / local `main`.
- 입력: R0 manifest가 지정한 `us-web-pilot-run.json`, SHA-256 `cc9150f8b77a27ffd6b001449c0475933ff744a37011801923f87cbdc5558275`; 외부 audit 파일은 읽기 전용 local acceptance에만 사용합니다.
- 수정 허용: 신규 `backend/jusik/market_performance_readiness.py`, 신규 focused tests, `docs/market-performance-metrics.md`, 신규 개발 기록. 등록부는 Astra만 수정합니다.
- 검증: canonical-shaped 합성 입력의 누락 code·등급·비용 근거 보존, SHA/schema/raw field/중복 key/비유한 수/크기/NAV/session 검증, 입력 불변·결정성을 pytest/Ruff/format/configured source mypy로 확인하고 canonical local acceptance·독립 review·main 통합 재검사합니다.
- 금지: timestamp/calendar/risk-free/cost-inclusion 합성, `ready=true` 경로, 성과 계산·필터 판정, 기존 evaluator/shared model/전략/collector/runner/API 변경, 연구·수집·PAPER/live·주문·운영 DB/service/config/remote 변경, 로드맵 checkbox 변경.
- 중단 조건: 현재 원본을 ready로 만들거나 외부 근거 주입 체계·평가 실행이 필요하면 범위를 넓히지 않고 차단합니다.
- 결과: Luna 최종 구현 `b170f36`, Terra 최종 review PASS, local main 통합 `6b9355e`. main에서 focused·호환 pytest 96개, Ruff/format, configured source mypy, diff 검사와 고정 SHA canonical CLI acceptance가 통과했습니다. canonical 결과는 blocked, 관측 252개, 고정 누락 근거 7개입니다.
- 정리: 통합 검증 후 전용 worktree와 branch를 정상 제거합니다. 개발 기록은 `docs/development-records/2026-09-17-market-performance-readiness.md`, handoff는 루트 `HANDOFF.md`입니다.

## market-performance-metrics

- 상태: 완료. R1-04 실제 기업행사 연결은 지급일·권리수량·명시적 missing 근거 부족으로 계속 차단하며, 기존 동결 NAV 252개를 읽는 순수 평가 계약만 통합했습니다.
- 목표와 완료 조건: 비용 반영 상태를 보존한 frozen NAV에서 CAGR·MDD·Sharpe·Calmar를 Decimal로 결정적으로 계산하고, 입력 근거가 부족한 지표는 0/무한대 대신 unavailable과 이유로 반환합니다. `MDD <= 20%` hard filter만 판정하며 자동 후보 선택·승격은 하지 않습니다.
- 담당: Astra 감독·계획·통합, Luna 단일 구현, Terra 독립 review.
- 워크트리/브랜치: `/home/kwl/projects/jusik-market-performance-metrics` / `feat/market-performance-metrics`.
- 기준 커밋/통합 대상: `487d84e` / local `main`.
- 수정 허용: 신규 `backend/jusik/market_performance_metrics.py`, 신규 focused tests, `docs/market-performance-metrics.md`, 관련 계약 링크와 신규 개발 기록. 공유 모델·전략·collector·runner·로드맵 checkbox는 변경하지 않습니다.
- 계산 계약: CAGR은 실제 UTC 경과일/365, Sharpe는 명시적 무위험률 입력과 일별 단순 초과수익률 표본 표준편차·연252, MDD는 초기 자본 포함 최고 NAV, Calmar는 CAGR/MDD. 첫 NAV 수익도 초기 자본 기준이며 NAV에 반영된 비용을 재차 차감하지 않습니다.
- 검증: 양·음수 수익, 초기 손실, 20% 경계, 윤년·휴장일, 누락·중복·역순, 0·비유한 NAV, 변동성0, MDD0, SHA 불일치, 입력 불변·결정성을 focused pytest/Ruff/format/configured mypy로 검사하고 독립 review/main 통합 재검사합니다.
- 금지: R1-04/R4 완료 표시, 새 연구/수집/network, 후보 탐색, strategy/PAPER/live/주문, 운영 DB·서비스·config·remote 변경.
- 중단 조건: 무위험률·비용 포함·세션 완전성·자료 등급을 입력에서 증명할 수 없으면 해당 지표를 unavailable로 유지합니다. 기존 approximate NAV를 strict 경제 성과로 승격하지 않습니다.
- 결과: Luna 최종 구현 `af3b2d9`, Terra 최종 review PASS, local main 통합 `0ce3bf7`. main에서 focused·호환 pytest 72개, Ruff/format, configured production-source mypy, diff 검사가 통과했습니다. 테스트 파일까지 직접 지정한 비표준 mypy는 테스트 보조 코드 5건을 보고했으며 production source 결과에는 영향이 없습니다.
- 정리: 통합 검증 후 전용 worktree와 branch를 정상 제거합니다. 개발 기록은 `docs/development-records/2026-09-17-market-performance-metrics.md`, handoff는 루트 `HANDOFF.md`입니다.

## mandate-dispatch-gate

- 상태: 완료. 자동 실행기는 pause, service/timer는 inactive/disabled이며 실제 저장소의 신규 governance는 `dispatch_enabled=false`로 유지합니다.
- 목표와 완료 조건: 승인된 balanced 연구 정책을 기존 `research-mandate.json`에 호환 확장하고, JSON/Markdown/checksum/policy version 불일치나 비활성 상태를 investment-roadmap `resume`·queued task·빈 큐 planner의 claim/dispatch 전에 fail-closed 처리합니다.
- 담당: Astra 감독·계획·통합, Luna 단일 구현, Terra 독립 review.
- 워크트리/브랜치: `/home/kwl/projects/jusik-mandate-dispatch-gate` / `feat/mandate-dispatch-gate`.
- 기준 커밋/통합 대상: `7da06b9` / local `main`.
- 수정 허용: mandate governance validator와 runner/roadmap 연결, 직접 관련 tests, `docs/research-mandate.json`, checksum manifest, canonical roadmap marker, runner/research 운영 문서, 신규 개발 기록. 등록부는 Astra만 수정합니다.
- 호환·rollback: 기존 mandate 역사 필드·PAPER10%·일반 research scope·DB schema·큐/attempt를 보존합니다. rollback은 governance `dispatch_enabled=false`로 유지해 이후 roadmap dispatch를 차단합니다.
- 검증: governance 단위·runner roadmap/planning/resume 회귀, Ruff/format, configured strict mypy, JSON/MD/checksum/version·링크·checklist 보존, 독립 review와 main 통합 재검사.
- 금지: 실제 runner resume/dispatch, 연구·수집·PAPER/live·주문, 운영 DB·서비스·user config·remote 변경. 임시 Git/DB와 fake child만 사용합니다.
- 중단 조건: 기존 역사 필드 변경, 일반 research scope 회귀, claim/attempt/launch count 선행 변경, checksum 해석 모호성 또는 실제 운영 상태 변경이 필요하면 통합하지 않습니다.
- 결과: Luna 구현 `3edeaa7`, Terra 최종 review PASS, local main 통합 `0200ff0`. worker 관련 검사 189개, main focused 검사 147개, Ruff/format, configured mypy 124 source, checksum/projection 검증 통과.
- 정리: 통합 검증 후 전용 worktree와 branch를 정상 제거합니다. 개발 기록은 `docs/development-records/2026-09-17-mandate-dispatch-gate.md`, handoff는 루트 `HANDOFF.md`입니다.

## investment-roadmap-refresh

- 상태: 완료. 자동 실행기는 pause, service/timer는 inactive/disabled이며 신규 연구 dispatch를 금지합니다.
- 목표와 완료 조건: `docs/investment-development-roadmap.md`를 단일 실행 정본으로 유지하면서 최신 사용자 목표, 핵심 지표, 과적합 방지 검증 순서와 승격 중단 조건을 통합합니다. 기존 R0~R7 ID·체크 상태·완료 증거는 보존합니다.
- 담당: Astra 감독·통합, Luna 단일 문서 구현, Terra 독립 검토.
- 워크트리/브랜치: `/home/kwl/projects/jusik-investment-roadmap-refresh` / `docs/investment-roadmap-refresh`.
- 기준 커밋/통합 대상: `995797a` / local `main`.
- 수정 허용: `docs/investment-development-roadmap.md`, `docs/research-mandate.md`, `docs/research.md`, 신규 `docs/development-records/2026-09-17-investment-roadmap-refresh.md`. 등록부는 Astra만 수정합니다.
- 불변 범위: 코드, `research-mandate.json`, 기존 개발 기록과 역사 연구 문서, 로드맵 checklist ID·체크값, 운영 DB·설정·서비스·PAPER/live·주문·remote.
- 검증: `git diff --check`, Markdown 링크, 로드맵 parser, 기존 checklist ID·체크값 보존 검사, 독립 review와 main 통합 재검사.
- 중단 조건: 문서 간 정책 적용 범위가 불명확하거나 parser가 기존 checklist를 다르게 읽으면 통합하지 않습니다. 실행 JSON은 후속 연구 재개 전 별도 동기화 게이트로 남깁니다.
- 결과: Luna 구현 `fbf2ebd`, Terra 최종 review PASS, local main 통합 `206d091`. main parser tests 16개, checklist 40/40 보존, 로컬 링크·diff 검사 통과.
- 정리: 통합 검증 후 전용 worktree와 branch를 정상 제거합니다. 개발 기록은 `docs/development-records/2026-09-17-investment-roadmap-refresh.md`, handoff는 루트 `HANDOFF.md`입니다.

## r1-artifact-db6987

- 상태: 기술 slice 완료. task `roadmap-r1-04-accounting-artifact-v2`, attempt `db6987bf670142e2ab2c7e25f4bc1624`. 전체 R1-04는 미체크입니다.
- 담당: Astra 감독·계획·통합, Luna 단일 구현, Terra 독립 review와 추가 실행 감사 PASS. model-only 라우팅 사후 검사 PASS.
- 기준/구현/통합: 요청 `44863a65d07df7546fee4ec699b108e77c53e76b`, 등록 `69eba8e`, 최종 구현 `637198f`, local main 통합 `3cf549574d77527b208830c8583a82ba2dee5f8e`.
- 범위: 신규 오프라인 JSON adapter/CLI, focused tests, 계약 문서3파일. 기존 순수 회계·fixture·공유 모델·collector·cutoff·전략·운영 원장은 그대로입니다.
- 입력 검증: 첨부 evidence5개, 첫 slice evidence6개, R0 동결 artifact4개 SHA 및 선행 통합 ancestry를 확인했습니다. coverage incomplete, economic not-evaluated를 유지합니다.
- 검증: 최종 worker/main 각각 pytest41·Ruff/format·configured strict mypy 통과. 초기 임시 경로/타입 오류, UTC overflow/검증 누락은 같은 Luna가 수정했습니다. 중간 실패와 review를 보존했습니다.
- 예산: seed0·입력1MiB·4심볼/40 UTC날짜/80전이·focused900초·audit50MiB. harness8.084초, 누락 별도 검사까지 포함한 보수적 상한27.751초. 별도 검사는 순차·CPU affinity 미설정, 최종 worker/main harness는 단일 CPU affinity 적용. 호출 횟수 자체는 중단 조건이 아니며 과거 위반을 소급 승인하지 않습니다.
- 정리: `/home/kwl/projects/jusik-r1-artifact-db6987`, `feat/r1-artifact-db6987`를 증거93개·SHA·handoff 보관 후 정상 제거했습니다. 다른 작업은 보존합니다.
- 안전: 연구 engine/pilot/final·수집·GPU·PAPER/live·주문0회, 운영 DB/원장·서비스·설정·remote 변경 없음. 성과 비교가 없어 웹 성과 catalog는 변경하지 않았습니다.
- 증거: `/home/kwl/.local/share/jusik/portfolio-audit/20260917-r1-artifact-db6987`의 integration-final·supplemental-execution-audit·review·source·main-cli-proof·manifest·cleanup. 개발 기록 `docs/development-records/2026-09-17-r1-artifact-db6987.md`; handoff는 루트 `HANDOFF.md`와 audit `HANDOFF-final.md`입니다.

## delivery-recovery

- 상태: 완료. R2-06 비교 모듈·CLI와 개발 지침을 main에 통합하고 각각 통합 검증을 통과했습니다.
- 감독 결정: 새로운 검증에서는 agent가 자체 생성한 단위 테스트 fixture 개수 제한을 종료 조건으로 쓰지 않습니다. 기존 실패 기록은 보존합니다. 사용자 명시 한도와 실제 금융 연구의 표본·기간·가정·계산 예산은 변경하지 않습니다.
- 작업 A: 기존 `/home/kwl/projects/jusik-r2-counterfactual-fe92`, `feat/r2-counterfactual-fe92`를 재사용합니다. 기존 구현 `f4070f2`의 독립 검토·focused 검사·필요한 좁은 결함 수정 후 main 통합까지 수행합니다. 담당 Luna는 단일 소유자로 인계합니다.
- 작업 B: `/home/kwl/projects/jusik-development-delivery-policy`, `fix/development-delivery-policy`. 기준은 main `2f8bb40` 이후 이 등록 커밋입니다. 별도 Luna가 runner의 runtime/planner/roadmap 지침과 운영 문서만 수정합니다. 투자·거래·상태 DB 계약은 그대로입니다.
- 검증: R2 비교/회계 focused pytest·Ruff·strict mypy, runner 관련 focused 검사, 독립 review와 main 통합 검사. 검증 1200초·산출물 50MiB 내에서 수행하며 외부 시장 요청·연구 engine·PAPER/live 주문은 실행하지 않습니다.
- 증거: `/home/kwl/.local/share/jusik/portfolio-audit/20260917-delivery-recovery`의 scope·review·integration·main-cli-proof. 정책 구현3a0eb04/통합6ebfabe, R2 구현8fc46d4/통합5ec8f2f. main 정책95개+R2 52개 테스트, Ruff/format/strict mypy 통과. CLI 결과·원본 SHA 보존 확인.
- 정리: 두 작업 소스·patch·환경·로그 보관 후 해당 worktree/branch 정상 제거. 다른 미완료 작업은 보존합니다. 문서 기록 후 R1-04를 명시적으로 retry하고 실제 재개 증거를 audit/activation.json에 기록합니다.
- 개발 기록: `docs/development-records/2026-09-17-delivery-recovery.md`, 기존 R2 기록과 policy 기록 갱신. handoff: 루트 `HANDOFF.md` 및 audit 복사본.

## r1-actions-bf7b

- 현재 재시도: `33c9cb940ee7486cb40ba692842dc732`, task `roadmap-r1-04-v1`. 같은 worktree/branch와 미커밋 구현을 재사용합니다. 이전 시도 차단 기록은 아래에 역사로 보존합니다.
- 현재 상태: 첫 기술 slice 완료. Astra 감독·Luna 구현·Terra 독립 재검토 PASS. 구현 `5405f37`, main 통합 `c39242ec208d5bac9cdb3d3f2aa0076417e2af74`; worker/main 각각 pytest31·Ruff/format·strict mypy 통과. 전체 R1-04 미체크.
- 이번 범위: 기존 회계 모듈의 전체 NAV·배당 지급 사실 대조·bool 검증 보완과 순수 회귀·계약 문서. 공유 모델·collector·universe·cutoff·전략·PAPER 계약은 불변입니다.
- 검증 예산: 기존 fixture 재사용, 신규 fixture 최대20개·각4심볼/40세션, seed0, 단일 CPU 프로세스·관련 검사 합계900초·audit50MiB. focused 회계 테스트와 사전 검토한 순수 legacy node만 실행합니다. engine/pilot/final/network/GPU 실행은 0회입니다.
- 현재 정리: 필요한 소스·증거·SHA·handoff 보존 후 해당 worktree/branch 정상 제거. 신규 변형13개/20개, 검사12.180초/900초. 개발 기록과 audit HANDOFF에 결과를 저장했습니다. 다른 격리 작업은 보존합니다.
- 현재 증거: `/home/kwl/.local/share/jusik/portfolio-audit/20260917-r1-04-33c9/`. 구현 소유자는 등록부를 수정하지 않습니다. 과거 agent 테스트 호출 횟수 제한은 현재 tracked delivery 정책으로 대체하며 과거 실패를 승인으로 바꾸지 않습니다.

- 이전 시도 상태(역사): 차단. task `roadmap-r1-04-v1`, attempt `bf7be9ff5dd64096848f7599f0c8265f`; 구현·전체 R1-04 미완료, checkbox 미체크.
- 담당: Astra 감독·계획, Luna 단일 구현, Terra 읽기 전용 독립 감사.
- 워크트리/브랜치: `/home/kwl/projects/jusik-r1-actions-bf7b` / `feat/r1-actions-bf7b`; 요청 기준 `5688c38b1f8c091db5e52d495df5262f5d1ed749`, 등록 기준 `e84aa55`. 미커밋 구현 보존, main 구현 통합 없음.
- 범위: 별도 연구용 split/dividend 회계 adapter·순수 Decimal 변환·fixture·문서 초안. 공통 history hash·collector·universe·사건 cutoff·전략·PAPER 계약 불변.
- 차단: 허용된 두 순수 회귀 대신 기존 파일 전체를 두 번 실행해 합성 pilot 연구 경로가 실행됐습니다. 독립 감사에서 변경 입력을 포함한 신규 fixture가 최소21개로 cap20 초과임을 확인했습니다. code routing receipt 불일치로 delivery audit도 실패했습니다. 자동 복구 분류 없음.
- 검증: worker 마지막 pytest60·Ruff·strict mypy 통과는 acceptance로 사용하지 않습니다. 추가 계산 중단, tests/review gate 차단, main 통합 검사 미실행.
- 안전: 실제 자료 수집·실제 연구 성과 평가·PAPER/live·주문·운영 원장/DB·서비스·설정·GPU·remote 변경없음. 기존 차단 작업 보존.
- 증거/handoff: `/home/kwl/.local/share/jusik/portfolio-audit/20260917-r1-04-bf7be9ff/`의 source snapshot·실행 이력·review·manifest·HANDOFF. 미병합 worktree는 삭제하지 않습니다.
- 기록: `docs/development-records/2026-09-17-r1-actions-bf7b.md`. 다음 명시적 재시도는 같은 소유 branch/worktree에서 입력 목록과 검사 범위를 먼저 고정합니다.

## runner-autorecovery

- 상태: 구현·독립 검토·local main 통합 완료. 사용자 자율재개 승인에 따라 roadmap queue cap과 환경/계획/범위 내 구현 오류의 명시적 bounded 자동 복구를 반영했습니다.
- 담당: Astra 감독, loss_recovery_explore 조사·loss_recovery_plan 계획, cost_recovery_code Luna 단일 구현, Terra 독립 검토.
- 워크트리/브랜치: `/home/kwl/projects/jusik-runner-autorecovery` / `fix/runner-autorecovery`; 기준 main7658714 이후 이 등록커밋, 통합 localmain.
- 범위: runner/store 및 필요시 planning/roadmap, 기존test3파일, 운영문서·새개발기록. 거래/전략/자료판정 불변. 자동runner paused/service inactive.
- 검증: fakechild/임시DB focused tests, Ruff/format/strictmypy, 독립review와 main통합검사. 실제주문·자동Codex를 테스트로 실행하지 않습니다.
- 계획·증거: `/home/kwl/.local/share/jusik/portfolio-audit/20260917-runner-autorecovery/PLAN.md`. 기본off설정으로 호환성을 유지하고 설치roadmap만 감독이 활성화합니다.
- 완료: 원자적cap/2회backoff복구/격리cache 검증, 증거/SHA/handoff저장·worktree정리 후 실제R2-06재개확인. 미복구자료부족은 자동성공처리하지 않습니다.
- 결과: 구현 `14eb01f`, stale planner 보완 `2dc1c7d`, 병합 직전 main `2a3e431`, 통합 `360f6af0339df5abfcc83b31ee46caf20c7b5a59`. worker/main focused pytest 95개, Ruff check/format, strict mypy 통과. 독립 review 중요 지적 해소.
- 정리: 소스·초기/최종 patch·환경·검증 로그와 SHA를 외부 audit에 보존한 뒤 이번 worktree와 branch만 정상 제거했습니다. 기존 R2-06 worktree는 보존했습니다.
- 기록: `docs/development-records/2026-09-17-runner-autorecovery.md`, 루트 `HANDOFF.md`. 기록 저장 후 설치 roadmap 설정을 활성화하고 R2-06을 재시도합니다. 실제 실행 여부는 audit의 `activation.json`과 현재 상태를 확인합니다.

## r2-counterfactual-fe92

- 상태: 기술 모듈·CLI 완료, main 통합·검증 완료. 실제 비용/배당/환율 준비 결과의 자료 acceptance와 전체 R2-06은 미완료이며 checkbox는 그대로입니다.
- 구현: 기존 f4070f2를 재사용해 hardlink 원본 보호와 없는 경로/null 혼동을8fc46d4에서 수정했습니다. 독립 Terra review 중요 지적 해소. main 통합5ec8f2f.
- 검증: worker/main focused pytest52개, Ruff check/format·configured strict mypy·diff check PASS. 합성 CLI 결과 동일, input SHA 보존, unavailable dividend/FX 및 economic not-evaluated 유지.
- 감독 결정: 새 검증에서 agent 자체 unit fixture 개수 제한을 제거했습니다. 과거25>24 중단과 모든 이전 실패 기록은 보존하고 소급 성공 처리하지 않습니다. 실제 투자 연구 조건과 사용자 명시 한도는 그대로입니다.
- 증거: `/home/kwl/.local/share/jusik/portfolio-audit/20260917-delivery-recovery/r2-source`, r2-worker 및 main-cli-proof.json. 이전 audit도 보존합니다.
- 정리: 기존 `/home/kwl/projects/jusik-r2-counterfactual-fe92`와 `feat/r2-counterfactual-fe92`는 통합·검증·자료 보관 후 정상 제거했습니다. 과거 runner task의 blocked 이력은 변경하지 않습니다.
- 개발 기록: `docs/development-records/2026-09-16-r2-counterfactual-fe92.md`; 사용 계약: `docs/research/market-counterfactual-comparison.md`.

## r3-value-44f7

- 상태: R3-04 완료·독립 review 및 main 통합 검사 통과. task `roadmap-r3-04-v1`, attempt `44f7dba3fcd04864b951f5987ad58ffe`; 이전 시도에는 소유 worktree/branch/구현이 없어 새 전용 작업을 생성합니다.
- 목표: 현재 투자자 가치 분석과 역사적 breakout/SMA20 설명 및 자료 시점 구분. 미래 valuation 소급 금지. R3-04 하나만 수행합니다.
- 담당: Astra 계획·통합·정적 fixture 검증, Luna 단일 구현, Terra 독립 review.
- 워크트리/브랜치: `/home/kwl/projects/jusik-r3-value-44f7`, `feat/r3-value-44f7`; 기준 main `99346e9062a729b133bafcb68d43880dd8393b43`, 통합 local main.
- 입력: R0 완료, tracked mandate JSON, investor/market 기능 문서와 기존 고정 fixture. 요청 HEAD는 현재 main의 조상입니다.
- 수정 범위: investor·market 홈/상세 설명, 두 기능 문서, 해당 개발 기록. 전략/API/계산 계약 유지.
- 격리·검사: 별도 node_modules/.next, loopback3234/8934, DB없음. frontend contract/lint/typecheck/build, 통합 browser4화면×2뷰포트. 연구엔진·수집·GPU0회.
- 경계: 다른 실패/차단 작업·R3-03 재개 금지; PAPER/live·주문·운영 원장·서비스/설정·remote 변경 금지.
- 계획/증거: `/home/kwl/.local/share/jusik/portfolio-audit/20260916-r3-04-44f7dba3/PLAN.md`.
- 개발 기록: `docs/development-records/2026-09-16-r3-value-44f7.md`; handoff는 같은 audit의 `HANDOFF.md`에 저장합니다.
- 검증: Luna 구현 `4157df3`, Terra 코드/UI review PASS, Astra 통합 `51aec7c`; main contract/lint/typecheck/build PASS; browser4화면×2뷰포트8건 PASS, 오류·외부 요청·overflow0. R3-04만 체크, R3 전체/경제적 성공 주장 없음.
- 정리: 증거87개·SHA·handoff 선보관 및 재검증 후 소유 worktree/branch 정상 제거 완료(`cleanup.json`). 다른6개 미완료 worktree와 기존 루트 HANDOFF.md 보존.

## r2-nav-components-7284

- 상태: 기술 복구 완료·main 통합 검증 완료. 전체 R2-05는 실제 자료 근거 부족으로 미완료이며 runner의 과거 blocked 시도는 보존합니다.
- 변경: JSON UTF-8 오류·입출력 별칭 충돌·strict typing·잔차/산출물 검증을 수정했습니다. 전략·가정 요율·시장 자료·PAPER/live·운영DB·성과 수치 변경 없음.
- 담당: 전용 Luna 구현, Terra 독립 review, Astra 순차 통합. 구현 `b0b57d7`, 통합 `be68400`.
- 검증: main focused pytest27·Ruff check/format·configured strict mypy2파일·diff check PASS. 실제 동결pilot은 복구에서1회 진단했고 소스 동일성 확인 후 통합 증거로 재사용했습니다.
- 증거: `/home/kwl/.local/share/jusik/portfolio-audit/20260916-nav-recovery`의 PLAN·worker·integration.json·source. 과거 실패·범위 위반은 원래 audit와 개발 기록에 보존합니다.
- 정리: 소스·패치·SHA 보관 후 해당 worktree `/home/kwl/projects/jusik-r2-nav-components-7284`와 `feat/r2-nav-components-7284` 정상 제거. 다른 미완료 worktree 보존.
- 개발 기록: `docs/development-records/2026-09-16-r2-nav-components-7284.md`. handoff: 루트 및 recovery audit/HANDOFF.md.
- 다음 단계: 독립회계·calendar 근거를 별도 확보; 저장 구성요소 일관성을 완전한 회계 검증으로 해석하지 않습니다.

## r2-market-cost-b8a5

- 상태: 기술 복구와 원본 파일 보호 후속 보완까지 main 통합 검증 완료. 전체 R2-02는 실제 자료 근거 부족으로 미완료, 과거 blocked 시도 보존.
- 변경: 저장 비용 불일치의 성공 처리·현지 체결일·시간 순서·독립 금액 기대값을 수정했습니다. 전략·가정 요율·시장 자료·PAPER/live·운영DB·성과 수치 변경 없음.
- 담당: 전용 Luna 구현, Terra 독립 review, Astra 순차 통합. 구현 `6e7aab6`, 통합 `79e73c6`.
- 후속 보완: CLI 원본/출력 별칭 거절 구현 `6831e49`, 최종 Terra PASS, 통합 `daf7ba5`, main pytest21·Ruff·mypy PASS. `output-guard/`에 소스와 증거 보관 후 후속 worktree/branch도 정상 제거했습니다.
- 검증: main focused pytest20·Ruff check/format·configured strict mypy2파일·diff check PASS. 실제 동결pilot은 복구에서1회 진단했고 소스 동일성 확인 후 통합 증거로 재사용했습니다.
- 증거: `/home/kwl/.local/share/jusik/portfolio-audit/20260916-cost-recovery`의 PLAN·worker·integration.json·source. 과거 실패·범위 위반은 원래 audit와 개발 기록에 보존합니다.
- 정리: 소스·패치·SHA 보관 후 해당 worktree `/home/kwl/projects/jusik-r2-market-cost-b8a5`와 `feat/r2-market-cost-b8a5` 정상 제거. 다른 미완료 worktree 보존.
- 개발 기록: `docs/development-records/2026-09-16-r2-market-cost-b8a5.md`. handoff: 루트 및 recovery audit/HANDOFF.md.
- 다음 단계: 법정 세목·요율·실제 체결시각/주문 식별 근거를 별도 확보; 기술 대사 성공을 법정 적정성으로 해석하지 않습니다.

## r3-equity-97b2

- 상태: 표시 slice 통합·검증 완료; 전체 R3-01은 benchmark·USD 계약 부재로 차단, 경제 not-evaluated
- task/attempt: roadmap-r3-01-v1 / 97b2a73338204452aec88b17ecb8edf1
- 목표: 기존 KRW NAV·기록 낙폭과 근거 있는 KRW 수익률 표시; USD/benchmark 근거 부재 명시
- 담당: Astra 조사 검토·계획·통합, Luna 단일 구현, Terra 독립 review
- 워크트리·브랜치: /home/kwl/projects/jusik-r3-equity-97b2 / feat/r3-equity-97b2
- 기준 main: 01bc282b885da3dc8bb327755435bded9104aa56; 통합 대상 local main
- 입력: R0 완료 계약, 최신 mandate, marketResearch.ts, 상세 페이지, R3-02 기록
- 범위: frontend 상세·표시 helper·fixture·계약 문서·개발 기록; backend 변경 없음
- 검증: 오프라인 CPU seed0, 신규 scenario≤12·각2심볼/30세션, 전체 검사1200초; contract/lint/typecheck/build 및 desktop/mobile
- 격리: loopback3221/8921, 전용 node_modules/.next, DB 없음
- 경계: 연구 재실행·network 수집·GPU·PAPER/live·주문·운영 원장/서비스/설정·remote 변경 금지
- 계획·증거: /home/kwl/.local/share/jusik/portfolio-audit/20260916-r3-01-97b2a733/PLAN.md
- 개발 기록: docs/development-records/2026-09-16-r3-equity-97b2.md
- handoff: /home/kwl/.local/share/jusik/portfolio-audit/20260916-r3-01-97b2a733/HANDOFF.md
- 완료 조건: 독립 review·local main 통합 검사·증거 SHA/handoff 선보관·소유 worktree 정리. 전체 checkbox는 미체크 유지합니다.


- 구현/수정/통합: `32a0cfb8c4c109ecb0ec68a8bae75b30bef64d23` / `8bf7534d772ca1545f031c615d73d587c92c774c` / `4bb932f3ee58d17060d91ee0f6aad7839e40931a`
- 검토·검사: Terra P2 요청 기간 검증 수정 후 PASS; main contract/lint/typecheck/build PASS; 합성12개×desktop/mobile24개 PASS, 외부 요청·오류·overflow0
- 증거: `integration-verification.json` SHA-256 `544025ab3474ded6baf90eb726fac1f081d6d6361f1a65937319669182ded41d`; 전체 목록은 audit `manifest.json`, 초기 실패와 수정 이력 보존
- 정리: 증거117개·SHA·handoff 선보관 후 소유 서버 종료·worktree/branch 정상 제거. 다른 worktree7개·루트 HANDOFF.md 보존
- 재개 입력: 같은 기간·통화·초기 자본·비용·거래일 기준 benchmark 계약/자료와 USD 초기 자본·평가 시계열 계약. 전체 checkbox는 미체크, 성과 공개·배포 없음

## r2-loss-accounting-2760

- 상태: 기술 복구 완료·main 통합 검증 완료. 전체 R2-01은 실제 배당·완전체결·초기 포지션·기업행사 근거 부족으로 미완료. 과거 blocked 시도 유지.
- 변경: 혼합 통화 거절, 구조화된 currency/unit, Decimal context 고정, 매수세금/배당 현금 반영, 의존 자료 availability, 날짜/중복/metadata 검증.
- 담당: loss_recovery_code Luna, loss_recovery_review Terra, Astra 통합. 최종 구현 `93a6211`, 통합 `20ee636`.
- 검증: main pytest21·Ruff check/format·configured strict mypy2파일·diff check PASS. 최종 소스/입출력 SHA 연결과 코드 동일성 확인. 독립 검토 중요 지적 해소.
- 증거: `/home/kwl/.local/share/jusik/portfolio-audit/20260916-loss-recovery`의 PLAN·REVIEW-1·worker/final-source-manifest.json·integration.json·source. 복구pilot 진단 총3회(검토 지적에 따른 추가2회 승인), 이전 출력 모두 보존. engine/replay/수집 없음.
- 정리: 소스/패치/SHA 보관 후 `/home/kwl/projects/jusik-r2-loss-accounting-2760` 및 `feat/r2-loss-accounting-2760` 정상 제거.
- 개발 기록: `docs/development-records/2026-09-16-r2-loss-accounting-2760.md`. handoff: 루트 및 recovery audit/HANDOFF.md. 전략·웹·성과·PAPER/live·운영DB·원격push 변경 없음.

## r3-market-detail-coverage

- 상태: 완료; R3-02 기술 acceptance·Terra review·main 통합 검사 PASS, 경제 not-evaluated
- task/attempt: roadmap-r3-02-v1 / 981ad0a5f10e493da69b12377ece0917
- 목표: R3-02 상세 coverage·자료 등급·잠정 상태·누락 원인의 수치 표시; 경제 평가 not-evaluated
- 담당: Astra 감독·계획·통합, Luna 조사·단일 구현, Terra 독립 review
- 워크트리·브랜치: /home/kwl/projects/jusik-r3-detail-981a / feat/r3-detail-981a — 증거·SHA·handoff 보관 후 정상 제거
- 기준 main: cbc30512f5bb11ada96b1e48f4ca1cb23c4b6fde; 통합 대상 local main
- 범위: frontend 상세 page·표시 helper·관련 검사, market-research-contract, 개발 기록
- 검증: CPU, 정적 GET fixture≤8·각8심볼/30세션·seed0, desktop/mobile 각1회+수정 후1회 이하, wall1200초
- 출력·계획: /home/kwl/.local/share/jusik/portfolio-audit/20260916-r3-02-981ad0a5/PLAN.md; loopback3218/8918, 전용 node_modules/.next, DB 없음
- 경계: runner 배정 작업; R3-03/04 재개·수집·engine·replay·GPU·PAPER/live·주문·운영 DB·서비스/설정·remote push 금지
- 완료 조건: 독립 review·main 통합 검사·증거/SHA/handoff 보관 후 소유 worktree 정리
- 개발 기록: docs/development-records/2026-09-16-r3-market-detail-coverage.md
- handoff: /home/kwl/.local/share/jusik/portfolio-audit/20260916-r3-02-981ad0a5/HANDOFF.md

- 결과/통합: 최초8be5b7f, 순차 Luna 인계994aab9, grade 수정f57760a, mobile 수정2bb2df7; main `c8cb6e29b038d3724fd3b76d04788270e9221e0a`
- 검증·증거: `integration-verification.json`, `final-review.md`, `browser-results-final.json`, `manifest.json`; 정적8개×desktop/mobile 최종16개 PASS, 초기 mobile 실패·수정 근거 보존
- 라우팅: 초기 plaintext-mode 감사 실패 보존; opaque-mode Luna 소유권 인계와 Terra pre/post PASS. 원문 메시지 무결성은 주장하지 않음
- 정리: 소유 서버3218/8918 종료, 해당 worktree·branch 정상 제거. 기존 worktree6개와 루트 HANDOFF.md 보존

## r1-us-collection-diagnostics

- 상태: 진단 slice 완료; Terra 최종 검토 및 main 통합 pytest155/Ruff/configured mypy PASS. 전체 R1-05 acceptance는 실제 자료 부족으로 차단
- task/attempt: roadmap-r1-05-v1 / eae146bd3ed54a61ae617fad1c425d53
- 목표: 미국 CollectorError 제외 경로의 심볼별 안전한 원인과 coverage를 직렬화 후에도 보존합니다. R1-05 전체 체크는 보류하며 경제 평가는 not-evaluated입니다.
- 담당: Astra 감독·계획, Luna 조사 및 단일 구현, Terra 독립 검토
- 워크트리·브랜치: /home/kwl/projects/jusik-r1-us-diagnostics-eae1 / fix/r1-us-diagnostics-eae1
- 기준 main: ef19498632afce9edddac1f5e8aee8e5bbdeff8e; 통합 대상 local main
- 입력: R0 완료 로드맵, 현재 mandate JSON, collector, R1-06 개발 기록; 입력 hash는 audit inputs.json에 보존합니다.
- 허용 범위: collector, 관련 결과 계약·오프라인 테스트·계약 문서·개발 기록. 표본·membership·사건 시점·실패 cache·매매·회계 정책은 보존합니다.
- 검증: 오프라인 CPU, seed 0, 신규 fixture 최대20개·각8심볼/60세션, pytest/Ruff/configured mypy 합계900초 이내
- 출력: /home/kwl/.local/share/jusik/portfolio-audit/20260916-r1-05-eae146bd; 전용 venv/cache, 서버·DB 없음
- 경계: 자동 runner가 배정한 단일 작업입니다. 네트워크 수집·pilot/final·GPU·PAPER/live·주문·원장·서비스·설정·remote 변경 및 다른 실패 작업 재개는 금지합니다.
- 완료 조건: 독립 review, main 통합 검사, 증거·SHA·handoff 보관 후 해당 worktree 정리
- 개발 기록: docs/development-records/2026-09-16-r1-us-collection-diagnostics.md
- handoff: /home/kwl/.local/share/jusik/portfolio-audit/20260916-r1-05-eae146bd/HANDOFF.md
- 결과/통합: Luna 최종 동작 dbafd64, format-only7e23c8c; main6636fb6 및 212f236eafcc9d6930e6f39e0d994ca299db7a30. 병합 직전 d9ac948
- 검토: Terra 초기 지적3건과 all-failure 대사 지적을 동일 Luna가 수정하고 최종 PASS. 마지막 format-only 수정은 Astra AST 동일성 검토 PASS
- 증거: audit integration-verification.json·final-review.md·format-ast-review.json·manifest.json. 기존 format debt는 기준과 동일하며 전체 mypy는 전용 환경의 기존 torch 의존성 문제로 미완료, 변경3 source 검사는 통과
- 정리: 증거40개·hash·handoff 보관·검증 후 해당 worktree/branch만 정상 제거했습니다. 기존 차단 worktree6개 및 루트 handoff는 보존했습니다.

## r1-provider-response-fixtures

- 상태: R1-06 완료; Terra 재검토·main pytest143/Ruff/configured mypy PASS. 경제 평가 not-evaluated
- task/attempt: roadmap-r1-06-v1 / 518dc0fb997d44c08dab07140154667a; 이전20160a6ae67744da916c84644ef4a484 보존
- 목표: 합성 오프라인 fixture로 정상/null/quota/auth/parse/coverage 구분, 기존 예외 호환성 및 실패 캐시·비밀정보 차단 검증
- 담당: Astra 감독·계획, Luna 조사 및 단일 구현, Terra 독립 review. 최초 Luna receipt 오타로 감사 실패를 보존하고 r106_code_verified로 같은 worktree 소유권을 순차 인계
- 워크트리·브랜치: /home/kwl/projects/jusik-r1-provider-response-518d / fix/r1-provider-response-518d (기준 b805841, 전용 venv 생성)
- 시작 main: bfa3c47455e63822ee44d6f7070daaed9fe7b8dd; 통합 대상 local main
- 입력: R0 통합 증거 SHA 일치, tracked mandate f097fde7874063314e21f8be884b19d2e8cea3e1272c47e5991300c546548a7d; 현재 collector/tests
- 범위: market_data_collector.py, 관련 tests/고정 fixture, 계약 문서·개발 기록. 감독만 해당 checklist·등록부 관리
- 검증: CPU 단일 프로세스, seed0, 신규 fixture24개 이하·각8심볼/30세션 이하; pytest/Ruff/configured mypy 합계900초 이내; HTTP/sleep mock
- 출력: /home/kwl/.local/share/jusik/portfolio-audit/20260916-r1-06-518dc0fb; 전용 venv/cache, 서버·DB 없음
- 경계: 수집·pilot/final·backtest·GPU·PAPER/live·운영 원장/서비스/설정·remote 변경 없음. 경제 평가 not-evaluated
- 완료 조건: 독립 review, local main 통합 검사, 증거·hash·handoff 보존 후 worktree 정리; 다른 checklist 변경 없음
- 개발 기록: docs/development-records/2026-09-16-r1-provider-response-fixtures.md

- 결과/통합: 9749765 및 6cb05a1; 병합 직전 c1e4aa1; 통합 e335342829a50cd56f57c782ec12edb25764bb72. R1-06만 체크
- 증거·handoff: /home/kwl/.local/share/jusik/portfolio-audit/20260916-r1-06-518dc0fb; manifest.json, HANDOFF.md. 증거 보관·hash 검증 후 해당 worktree/branch 정리 완료

## runner-exit-diagnostics

- 상태: 완료; main 통합 및 회귀 검증 PASS
- 목표: codex_exit의 numeric returncode/signal/완료 파일 존재를 private sidecar로 기록, retry 시 기존 소유 worktree 재사용 안내
- 담당: routing_compat_code Luna 구현, routing_compat_review Terra 독립 검토, Astra 통합
- 워크트리·브랜치: /home/kwl/projects/jusik-runner-exit-diagnostics / fix/runner-exit-diagnostics — 통합 검증·증거 보관 후 정리 완료
- 기준/결과/통합: ca493eb / 1278202 / 269a34d3e965e82cb36c9baac4c6eb18b2d2d835
- 검증: main runner3파일 pytest84·Ruff check/format·strict mypy2 source·독립 review PASS
- 복구: live checklist를 읽던 기존 테스트3건은 임시 fixture 상태 고정으로 해결. 실제 로드맵 체크 변경 없음
- 경계: DB schema/status/retry 정책·금융 코드·전역 설정 불변. 과거 CLI 종료 원인 추정 없음
- 개발 기록: docs/development-records/2026-09-16-runner-exit-diagnostics.md
- audit: /home/kwl/.local/share/jusik/portfolio-audit/20260916-roadmap-recovery/runner-integration.json

## r1-us-event-timing

- 현재 재시도: `0fec3e1577aa4ed789ce66b02d87e0aa` — 자료 부족으로 차단. main `816e180`에서 기존 통합과 후속 `91cb1bbe` 포함, R0 입력4개 SHA 일치를 재확인했습니다. 기존 소유 worktree/branch는 정리된 상태이며 중복 생성하지 않았습니다. 실제 historical observed-at receipt·거래중단 coverage가 없고 추가 코드 결함은 확인하지 못했습니다. 이번 pytest/Ruff/mypy/replay·독립 review는 미실행이며 routing post도 검증 불가입니다. R1-02 체크 유지. 상세 기록: `docs/development-records/2026-09-16-r1-us-event-timing.md`; audit/handoff: `/home/kwl/.local/share/jusik/portfolio-audit/20260919-r1-02-0fec3e15/HANDOFF.md`.
- 상태: 기술 slice 복구·통합 완료(bcf34c5); 실제 Yahoo 과거 관측 시각 근거가 없어 R1-02 checkbox는 보류. 이전 codex_exit 이력 보존.
- task/attempt: roadmap-r1-02-v1 / c42012de115c4aed8c8d9348002a47ff
- 목표: 미국 사건 발생일·관측 시점을 보존하고 미래 사건에 대한 과거 선택 불변성을 검증합니다.
- 복구 검증: main pytest134·Ruff·configured mypy2 source·동결 replay all=true·Terra review PASS. 증거 /home/kwl/.local/share/jusik/portfolio-audit/20260916-roadmap-recovery/r102-integrated.
- 담당: Astra 감독, r102_explore Luna, r102_plan Astra, r102_code Luna 단일 구현 소유자와 Terra 독립 검토 예정
- 워크트리·브랜치: /home/kwl/projects/jusik-r1-us-event-timing-c420 / fix/r1-us-event-timing-c420 (복구 통합·증거 보관 후 정리 완료, 작업 기준4385610)
- 조사 기준 main: 3cd2393c38106be0f24859f226e05cad26765b41; 통합 대상 local main
- 범위: 미국 collector·approximate 사건 계약과 회귀 fixture, 관련 계약 문서·개발 기록. KR·전략·배당/분할 회계·R2-04·R3-03 제외
- 입력: R0 완료 계약·동결 artifact4개 SHA 일치, R1-01 membership, 현재 mandate JSON
- 검증: 오프라인 CPU, seed0, 신규 fixture24개 이하·각300세션·8심볼 이하, 전체 검증900초 이내. pytest/Ruff/configured mypy/frozen replay
- 출력: /home/kwl/.local/share/jusik/portfolio-audit/20260916-r1-02-c42012de; 전용 venv/cache, 서버·DB 없음
- 경계: 네트워크 수집·새 pilot/final·GPU·PAPER/live·운영 원장/서비스/설정·remote 변경 금지
- 완료 조건: 독립 review, local main 통합 검사, 영구 증거·handoff 보존 후 정리. 실제 관측 근거 부족은 blocked로 남기고 전체 R1-02 체크하지 않습니다.


## r1-us-product-types

- 상태: 완료; R1-03만 체크, Terra 재검토 및 main 통합 검사 PASS
- task/attempt: roadmap-r1-03-v1 / 9bd64c1361374e3f8414f0b131024715
- 목표: collector 내부 구조화 상품 분류와 NASDAQ alias 정규화; 기존 공개 schema와 membership/사건 시점 보존
- 담당: 감독 Astra; 구현 Luna r103_code, 독립 Terra r103_review
- 워크트리·브랜치: /home/kwl/projects/jusik-r1-us-product-types-9bd6 / feat/r1-us-product-types-9bd6 (생성 완료)
- 조사 기준 main: 1a9dd30a102d4605d5908422adea00c627c3537d; 입력 bf5640f는 현재 HEAD의 조상
- 범위: collector, 관련 fixture tests, docs/market-research.md, 개발 기록. 감독만 이 등록부와 해당 checklist 관리
- 검증 한도: 고정 새 fixture 최대40개, CPU900초; 수집·backtest·GPU·PAPER/live·운영 DB·서비스·설정·remote 변경 없음
- 출력: /home/kwl/.local/share/jusik/portfolio-audit/20260916-r1-03-9bd64c13; 서버·DB 없음, 작업별 venv/cache 사용
- 결과: 0803241 및 6e4bd20; 병합 직전 main ce03cb2; 통합 dc59347261e41ca232f2b50dc41dabb0d08e6c63; 증거/handoff 91파일 SHA 검증 후 해당 worktree 및 병합 브랜치 정리 완료
- 개발 기록: docs/development-records/2026-09-16-r1-us-product-types.md
- 검증: main pytest63·Ruff·strict mypy·원문37검사 PASS; 기존 format 부채 동일성 검증. 신규 fixture40개
- handoff: audit/HANDOFF.md 저장; 기존 루트 HANDOFF.md 보존. 경제 평가 not-evaluated

## runner-routing-compat

- 상태: 코드 통합·검증 완료; 자동 재착수 확인은 외부 activation.json에 기록
- 목표: roleless CLI 호환 경로를 추가하고 기존 차단 작업을 재시도하여 실제 구현 착수를 확인합니다.
- 담당: /root/routing_compat_code (Luna), /root/routing_compat_review (Terra); 부모 통합
- 워크트리·브랜치: /home/kwl/projects/jusik-runner-routing-compat / fix/runner-routing-compat — 검증 후 정리
- 기준/병합 직전 main: d90373b / ecbc83a
- 결과/통합: cf30c906c0b62f387836d550bc5f3b004096a5fb / f9ed8b1f09decdde1c730c1ff37b30880bceff41
- 범위: stdlib 역할 전달·검사 helper, focused tests, runner 안내·운영 문서. 금융 코드·큐 스키마 변경 없음
- 검증: 통합 pytest95, Ruff, strict mypy2 source, 실제 CLI Luna/Terra 감사, native 모델 감사, 독립 review 통과
- 한계: opaque 호출 message 원문·암호학적 무결성·native role sandbox 적용은 주장하지 않음
- 개발 기록: docs/development-records/2026-09-16-runner-routing-compat.md
- audit·운영 확인: /home/kwl/.local/share/jusik/portfolio-audit/20260916-runner-routing/integration-verification.json 및 activation.json
- handoff: HANDOFF.md 갱신, untracked 유지. 자동 재개 후 main 수동 변경 금지

## r3-market-ui-fixture

- 상태: 완료. R3-03 기술 acceptance 충족; 과거 runner blocked 시도는 변경하지 않습니다.
- 목표: R0 기반 목록·상세 loading/empty/partial/error 검증. R3-03 checkbox 완료.
- 담당: 기존 code Luna와 복구 ui_recovery_code Luna; 독립 Terra review P1/P2 없음.
- 기준/구현/복구/통합: `084746f` / `8d5a590` / `6d6b5a2` / `42b75c0`; 병합 직전 main `0d25892`.
- 변경: readiness 부분 실패 보존, runs 오류/빈 상태 분리, queued/running·loading 안내와 계약 문서.
- 검증: 정적 GET fixture 8개×desktop/mobile=16개 PASS. main contract/lint/typecheck/build PASS. 소스 동일성 확인 후 브라우저 증거 재사용.
- 실패와 복구: 기존 insufficient fixture 오류·증거 누락과 한도 일탈은 개발 기록에 보존. 새 복구는 engine/provider/DB 실행 없음. npm CPU 측정, browser/frontend CPU 미측정.
- 증거: `/home/kwl/.local/share/jusik/portfolio-audit/20260916-r3-03-recovery-manual`; 통합·소스 archive는 `20260916-roadmap-recovery/r3-integration.json`, `r3-source/`.
- 정리: 소유 서버 종료, 전용 worktree `/home/kwl/projects/jusik-r3-market-ui-fixture-67c5`와 `fix/r3-market-ui-fixture-67c5` 정상 제거. 다른 미완료 worktree 보존.
- 개발 기록: `docs/development-records/2026-09-15-r3-market-ui-fixture.md`. handoff: 루트 및 recovery audit의 `HANDOFF.md`.
- 한계: 실제 provider·경제 성과 미검증. PAPER/live·주문·운영 DB·remote push 변경 없음. 웹 배포 미수행.

## r2-dd-chronology

- 상태: 차단(필수 증거 부족); 독립 검산 기술 slice는 local main 통합·검사·Terra review PASS
- task/attempt: roadmap-r2-04-v1 / cb6b03f16c8f438cb4c55cfc551fe089
- 목표: 초기 자본 포함 KRW peak/DD/20% latch 독립 Decimal 검산 및 저장 파일럿 대조
- 담당: Astra 감독/계획, r204_explore Luna, 구현 r204_impl Luna, 독립 r204_review Terra
- 워크트리·브랜치: /home/kwl/projects/jusik-r2-dd-chronology-cb6b / feat/r2-dd-chronology-cb6b; 증거64파일 SHA 및 handoff 보존·검증 후 정리 완료
- 조사 기준80cf90a; worktree/병합 직전 main7d91318; 구현a74bf7e; 통합274a48c22175287280c4113c9351de3f3b9d9c38
- 선행: R0 완료, 현재 mandate JSON, 동결 approximate 파일럿252세션·106거래; 원본4개 SHA 일치
- 범위: 신규 독립 검산/test/최종 고정fixture12개·각300세션 이하, 보고서/문서. 초기 inline fixture 일탈은 REVIEW-2.md에 보존
- 출력: /home/kwl/.local/share/jusik/portfolio-audit/20260916-r2-04-cb6b03f1; 포트/DB 없음; CPU 단일 프로세스·저장 파일럿1개
- 결과: DD/MDD/최종 latch flag 일치, 2026-02-12 latch 계산 및02-13 보유5종목 청산 관측. calendar/benchmark/future/저장 latch-date/release 증거 부족으로 blocked
- 검증: main pytest6·Ruff check/format·strict mypy·report byte 일치·원본8개 hash·전략/R1/roadmap/root HANDOFF 보존 PASS
- 안전: 네트워크/GPU/수집/신규 연구/PAPER/live/원장/서비스/설정/remote 변경 없음. R2-04 체크 유지, 새 성과 웹 공개 해당 없음
- 개발 기록: docs/development-records/2026-09-15-r2-dd-chronology.md
- handoff: audit/HANDOFF.md; 해당 merged worktree/branch 정리 완료, 기존 root HANDOFF.md 및 다른 worktree 보존

## r1-us-membership

- 상태: 완료; R1-01만 체크, R1 전체 미완료
- task/attempt: roadmap-r1-01-v1 / 0406c82ad69743049331fa3e1ff08495
- 목표: frozen R1-01 미국 historical membership, legacy replay 보존
- 담당: 감독 Astra; r1_explore (Luna), r1_plan (Astra), r1_code (Luna), r1_review (Terra)
- 워크트리·브랜치: /home/kwl/projects/jusik-r1-us-membership-0406 / feat/r1-us-membership-0406; 증거 보관·검증 후 정리 완료
- 기준/병합 직전 main: a8a2ac8 / 7915813cd597812769dc15c954f5c562bc1e06fe
- 구현/보완: 32815e75f6bbda311d43861954b54c99289925a5 / 897abd46a653c70e93807fc3ea7ef2c55300e5bb
- 통합: 52ef32e7c0990acc900a14a73ef38a166f820ff1
- 검증: main pytest111·Ruff·strict mypy2 source·legacy replay all=true; Terra 독립 재검토 PASS, 라우팅 감사 PASS
- 범위: collector·approximate·관련 tests·계약 문서; 전략·KR·mandate·PAPER/live 보존
- 출력: /home/kwl/.local/share/jusik/portfolio-audit/20260916-r1-01-0406c82a; 서버·DB·네트워크 자료 수집 없음
- 개발 기록: docs/development-records/2026-09-15-r1-us-membership.md
- handoff: /home/kwl/.local/share/jusik/portfolio-audit/20260916-r1-01-0406c82a/HANDOFF.md
- 한계: 연간 근사 carry-forward, R1-02 행사·R1-03 분류·R1-04 회계 별도; 경제적 개선·PAPER 승격 없음

## roadmap-automation

- 상태: 진행 (코드·설정 검증 완료, 사용자 승인으로 자동 운영 전환; 실제 dispatch는 audit/activation.json 참조)
- 목표와 완료 조건: 기존 실행기에 투자 로드맵 전용 범위를 추가하고 별도 큐에서 미완료 체크리스트의 선행 조건을 확인하여 자동 개발을 이어갑니다. 회귀 검사·독립 검토·main 통합 후 첫 실제 dispatch를 확인합니다.
- 담당 Luna: /root/roadmap_automation_code (code, gpt-5.6-luna); 초기 구현 소유자; 재호출 thread limit으로 마지막 mandate gate 복구만 감독 Astra가 인계
- 워크트리 절대 경로: /home/kwl/projects/jusik-roadmap-automation
- 작업 브랜치: feat/roadmap-automation
- 기준 커밋 SHA: 3df0c0c
- 통합 대상 브랜치: 로컬 main
- 입력과 선행 작업: R0 완료 main fa4bb7c; 투자 개발 로드맵; 기존 runner 조사 및 제한된 계획
- 수정 허용 범위: development_runner 관련 코드·테스트, 자동 개발 운영 문서·개발 기록. 투자 계산·PAPER·실주문·사용자 미커밋 문서는 제외
- 포트·테스트 DB·출력 경로: 서버 없음; 작업별 임시 DB·환경; /home/kwl/.local/share/jusik/portfolio-audit/20260915-roadmap-automation
- 검증 명령과 결과: main 통합 runner pytest78·Ruff·strict mypy 통과; 독립 review 최종 중요 지적 없음; 전용 큐 seed 등록·paused smoke 통과
- 결과 커밋 SHA: 0d08b8e (Luna 217a982·85d510a, 감독의 최종 gate 복구 포함)
- 검토 결과와 남은 문제: 독립 review 지적 모두 수정·재검토 통과. 사용자 승인 후 문서 보존 커밋 a4f9760 완료; 추가 의사결정 없이 전용 자동 실행 시작
- 병합 직전 main SHA: 8d4ea489ed183500261ae9669abdf5387cfaa22b
- 통합 커밋 SHA와 정리 여부: 518ddb8b6f048dc4a46f36136fd14469f8f22782; 증거 보존 후 worktree 제거 완료, branch 보존
- 통합 검증 실패 원인과 복구 결과: 해당 없음
- 개발 기록 경로와 갱신 여부: docs/development-records/2026-09-15-roadmap-automation.md 갱신
- handoff 저장 경로와 갱신 여부: /home/kwl/.local/share/jusik/portfolio-audit/20260915-roadmap-automation/HANDOFF.md

## r0-baseline-freeze

- 상태: 완료 (R0-01)
- 목표와 완료 조건: 기존 미국 기준 main·run·입력 manifest·결과 해시를 재현 기록으로 고정. 관련 검사·독립 검토·로컬 main 통합 후에만 완료합니다.
- 담당 Luna: /root/r0_freeze (code, gpt-5.6-luna), 단일 구현 소유자
- 워크트리 절대 경로: /home/kwl/projects/jusik-r0-baseline-freeze
- 작업 브랜치: docs/r0-baseline-freeze
- 기준 커밋 SHA: 008ca02; 원래 연구 실행 SHA와 현재 재현 SHA는 증거에서 구분
- 통합 대상 브랜치: 로컬 main
- 입력과 선행 작업: docs/investment-development-roadmap.md R0-01; 기존 미국 기준 audit; 공통 계약 의존성은 plan 후 순차 확정
- 수정 허용 범위: 해당 체크 ID의 계약·재현 도구·관련 테스트와 문서. 전략·수집 정책·PAPER·실주문·운영 DB 변경 금지
- 포트·테스트 DB·출력 경로: 서버 없음; 작업별 임시 DB·환경; /home/kwl/.local/share/jusik/portfolio-audit/20260915-r0-baseline/r0-baseline-freeze
- 검증 명령과 결과: 입력3개 hash·모델parse·cache84개 hash/size·pytest45개 통과; 통합 main parse/hash/diff 통과
- 결과 커밋 SHA: 2a2de61b26acb73723bc09b1b6a76b42809819d8
- 검토 결과와 남은 문제: /root/r0_review 중요 지적 없음; 경제적 목표 not-evaluated
- 병합 직전 main SHA: 7949c9f
- 통합 커밋 SHA와 정리 여부: 86beeeabf998b4b4e720290ac65019e6486545c0; 증거 보존·worktree 제거 완료, branch 보존
- 통합 검증 실패 원인과 복구 결과: 해당 없음
- 개발 기록 경로와 갱신 여부: docs/development-records/2026-09-15-r0-baseline-freeze.md
- handoff 저장 경로와 갱신 여부: /home/kwl/.local/share/jusik/portfolio-audit/20260915-r0-baseline/HANDOFF.md

## r0-shared-contract

- 상태: 완료 (R0-02)
- 목표와 완료 조건: 자료·결과의 경로·시각·coverage·오류·등급 계약을 단일 소유자로 고정. 관련 검사·독립 검토·로컬 main 통합 후에만 완료합니다.
- 담당 Luna: /root/r0_freeze (code, gpt-5.6-luna), shared 계약 단일 소유자
- 워크트리 절대 경로: /home/kwl/projects/jusik-r0-shared-contract
- 작업 브랜치: feat/r0-shared-contract
- 기준 커밋 SHA: 935a31e
- 통합 대상 브랜치: 로컬 main
- 입력과 선행 작업: docs/investment-development-roadmap.md R0-02; 기존 미국 기준 audit; 공통 계약 의존성은 plan 후 순차 확정
- 수정 허용 범위: 해당 체크 ID의 계약·재현 도구·관련 테스트와 문서. 전략·수집 정책·PAPER·실주문·운영 DB 변경 금지
- 포트·테스트 DB·출력 경로: 서버 없음; 작업별 임시 DB·환경; /home/kwl/.local/share/jusik/portfolio-audit/20260915-r0-baseline/r0-shared-contract
- 검증 명령과 결과: pytest46·Ruff·mypy2개·Zod fixture·frontend lint/typecheck/build·예비 replay·diff 통과
- 결과 커밋 SHA: 176a948a4cdae1ef39b3e4c6ea70ed8692636638
- 검토 결과와 남은 문제: r0_review 중요 지적 없음; 경제적 목표 not-evaluated
- 병합 직전 main SHA: f72743f
- 통합 커밋 SHA와 정리 여부: 5f91bbac41b5ac60a2e97c368c3116e5c6daac29; 증거 보존·worktree 제거 완료
- 통합 검증 실패 원인과 복구 결과: 해당 없음
- 개발 기록 경로와 갱신 여부: docs/development-records/2026-09-15-r0-shared-contract.md
- handoff 저장 경로와 갱신 여부: /home/kwl/.local/share/jusik/portfolio-audit/20260915-r0-baseline/HANDOFF.md

## r0-deterministic-replay

- 상태: 완료 (R0-03)
- 목표와 완료 조건: 격리된 재실행 명령과 catalogue로 metrics·trades·equity 일치 검증. 관련 검사·독립 검토·로컬 main 통합 후에만 완료합니다.
- 담당 Luna: /root/r0_replay (code, gpt-5.6-luna), replay 단일 구현 소유자
- 워크트리 절대 경로: /home/kwl/projects/jusik-r0-deterministic-replay
- 작업 브랜치: feat/r0-deterministic-replay
- 기준 커밋 SHA: cd161ec
- 통합 대상 브랜치: 로컬 main
- 입력과 선행 작업: docs/investment-development-roadmap.md R0-03; 기존 미국 기준 audit; R0-02/04 계약 통합 완료; R0-05 표시 코드는 replay 입력과 독립. 새 replay 문서로 공유 문서 충돌 방지
- 수정 허용 범위: 해당 체크 ID의 계약·재현 도구·관련 테스트와 문서. 전략·수집 정책·PAPER·실주문·운영 DB 변경 금지
- 포트·테스트 DB·출력 경로: 서버 없음; 작업별 임시 DB·환경; /home/kwl/.local/share/jusik/portfolio-audit/20260915-r0-baseline/r0-deterministic-replay
- 검증 명령과 결과: 통합pytest61·Ruff·mypy3개·두checkpoint CLI exact comparisons·diff 통과
- 결과 커밋 SHA: 9cbc8daa0b641dd39c73756a8119c2f37620a4a5
- 검토 결과와 남은 문제: r0_review 중요 지적 없음; 경제적 목표 not-evaluated
- 병합 직전 main SHA: 58b504a
- 통합 커밋 SHA와 정리 여부: b950266983970d32f014f809d51a802eadbf2572; 증거 보존·worktree 제거 완료, branch 보존
- 통합 검증 실패 원인과 복구 결과: 해당 없음
- 개발 기록 경로와 갱신 여부: docs/development-records/2026-09-15-r0-deterministic-replay.md
- handoff 저장 경로와 갱신 여부: /home/kwl/.local/share/jusik/portfolio-audit/20260915-r0-baseline/HANDOFF.md

## r0-currency-contract

- 상태: 완료 (R0-04)
- 목표와 완료 조건: 독립 원화 계좌·초기 자본·USD/KRW 단위·환전 방향 명시. 관련 검사·독립 검토·로컬 main 통합 후에만 완료합니다.
- 담당 Luna: /root/r0_freeze (code, gpt-5.6-luna), shared 계약 단일 소유자
- 워크트리 절대 경로: /home/kwl/projects/jusik-r0-currency-contract
- 작업 브랜치: feat/r0-currency-contract
- 기준 커밋 SHA: 967df2f
- 통합 대상 브랜치: 로컬 main
- 입력과 선행 작업: docs/investment-development-roadmap.md R0-04; 기존 미국 기준 audit; 공통 계약 의존성은 plan 후 순차 확정
- 수정 허용 범위: 해당 체크 ID의 계약·재현 도구·관련 테스트와 문서. 전략·수집 정책·PAPER·실주문·운영 DB 변경 금지
- 포트·테스트 DB·출력 경로: 서버 없음; 작업별 임시 DB·환경; /home/kwl/.local/share/jusik/portfolio-audit/20260915-r0-baseline/r0-currency-contract
- 검증 명령과 결과: pytest48·Ruff·mypy2개·Zod fixture·frontend lint/typecheck/build·diff 통과
- 결과 커밋 SHA: 62ae5ac2dbae4c431cbd1f9d11f806e24d04447c
- 검토 결과와 남은 문제: r0_review 중요 지적 없음; 경제적 목표 not-evaluated
- 병합 직전 main SHA: 96698df
- 통합 커밋 SHA와 정리 여부: f949a635bc6e750b6d2b50a5a0beb889890f0111; 증거 보존·worktree 제거 완료
- 통합 검증 실패 원인과 복구 결과: 해당 없음
- 개발 기록 경로와 갱신 여부: docs/development-records/2026-09-15-r0-currency-contract.md
- handoff 저장 경로와 갱신 여부: /home/kwl/.local/share/jusik/portfolio-audit/20260915-r0-baseline/HANDOFF.md

## r0-grade-contract

- 상태: 완료 (R0-05)
- 목표와 완료 조건: strict·approximate·fixture·PAPER의 결과·화면 표시 규칙과 호환 fixture 고정. 관련 검사·독립 검토·로컬 main 통합 후에만 완료합니다.
- 담당 Luna: /root/r0_freeze (code, gpt-5.6-luna), 단일 구현 소유자
- 워크트리 절대 경로: /home/kwl/projects/jusik-r0-grade-contract
- 작업 브랜치: docs/r0-grade-contract
- 기준 커밋 SHA: 7ea9825
- 통합 대상 브랜치: 로컬 main
- 입력과 선행 작업: docs/investment-development-roadmap.md R0-05; 기존 미국 기준 audit; 공통 계약 의존성은 plan 후 순차 확정
- 수정 허용 범위: 해당 체크 ID의 계약·재현 도구·관련 테스트와 문서. 전략·수집 정책·PAPER·실주문·운영 DB 변경 금지
- 포트·테스트 DB·출력 경로: 서버 없음; 작업별 임시 DB·환경; /home/kwl/.local/share/jusik/portfolio-audit/20260915-r0-baseline/r0-grade-contract
- 검증 명령과 결과: npm fixture·lint·typecheck·build·Playwright등급/상태heading·diff 통과
- 결과 커밋 SHA: 455ccdc76c5289726b22c8b579fed49d27b13ecb
- 검토 결과와 남은 문제: r0_review 중요 지적 없음; 경제적 목표 not-evaluated
- 병합 직전 main SHA: cd161ec
- 통합 커밋 SHA와 정리 여부: 01f2d6850e9a991d8eb0688127cc8f8fec8eb523; 증거 보존·worktree 제거 완료
- 통합 검증 실패 원인과 복구 결과: 해당 없음
- 개발 기록 경로와 갱신 여부: docs/development-records/2026-09-15-r0-grade-contract.md
- handoff 저장 경로와 갱신 여부: /home/kwl/.local/share/jusik/portfolio-audit/20260915-r0-baseline/HANDOFF.md

## investment-development-roadmap

- 상태: 완료 (계획 문서); R0~R7 후속 기능은 미완료
- 목표와 완료 조건: 미국 손실 진단을 우선으로 단계별 목표·체크리스트·증거·병렬 소유권·통합 기준을 문서화하고 다음 개발의 기준 문서로 연결합니다. 이번 범위는 계획 문서이며 후속 기능의 완료를 의미하지 않습니다.
- 담당 Luna: roadmap_code, 문서 단일 구현 소유자. 감독은 등록부만 관리합니다.
- 워크트리 절대 경로: /home/kwl/projects/jusik-investment-development-roadmap
- 작업 브랜치: docs/investment-development-roadmap
- 기준 커밋 SHA: c2ada5c6a8770ac81519a3d41b8aff693e5723d1
- 통합 대상 브랜치: 로컬 main
- 입력과 선행 작업: 미국 1년 파일럿과 KRX 인증 통과 후 zero-OHLC 수집 실패, 현재 mandate, 사용자 계획·체크리스트·병렬 개발 요청
- 수정 허용 범위: docs/investment-development-roadmap.md, docs/architecture.md 안내 링크, 해당 개발 기록. 거래 정책·코드·mandate·사용자 agent-tooling 변경 제외
- 포트·테스트 DB·출력 경로: 서버·DB 미사용. 외부 audit /home/kwl/.local/share/jusik/portfolio-audit/20260915-investment-development-roadmap
- 검증 명령과 결과: 작업/통합 main의 문서 검사에서 40개 고유 미완료 체크 ID·8단계·2개 로컬 링크와 diff 검사를 통과했습니다. 미국 artifact hash를 대조했고, 독립 review에서 의존성과 실제 grade별 final 계약을 확인했습니다. 문서 전용이므로 제품 테스트·lint·typecheck·build는 실행하지 않았습니다.
- 결과 커밋 SHA: 03ce143f51e7ee847ad4d5cacf3ee876a50fdb8f, 08aee0e12dda4fd4282aa3bc370443b0ce9a6777
- 검토 결과와 남은 문제: 독립 review 최종 중요 지적 없음. 후속 실제 구현은 체크리스트에서 미완료로 유지하며 R0 기준 재현·공통 계약부터 착수합니다. 이후 R1/R2/R3 병렬, R4 계산은 UI 완료를 기다리지 않습니다.
- 병합 직전 main SHA: c2ada5c6a8770ac81519a3d41b8aff693e5723d1
- 통합 커밋 SHA와 정리 여부: 1d6ebfce1ecf2620a0c670e24866e5608f67572a; 통합 검증·증거·handoff 보존 후 전용 worktree 제거 완료, branch 보존
- 통합 검증 실패 원인과 복구 결과: 해당 없음
- 개발 기록 경로와 갱신 여부: docs/development-records/2026-09-15-investment-development-roadmap.md 갱신
- handoff 저장 경로와 갱신 여부: /home/kwl/.local/share/jusik/portfolio-audit/20260915-investment-development-roadmap/HANDOFF.md 저장

## market-data-live-contract-fixes

- 상태: 완료
- 목표와 완료 조건: 실제 provider smoke에서 확인한 KRX Open API 요청 계약과 Alpha Vantage 종목 정규화 오류를 수정합니다. 공식 KRX endpoint·`AUTH_KEY` header·`basDd`를 사용하고, 미국 목록에서 보통주가 아닌 상품과 비정상 표시명을 한 행 단위로 제외해 전체 수집을 보존합니다. 사용자가 저장한 안전한 env alias를 지원한 뒤 KR/US 소규모 실제 smoke를 재실행합니다.
- 담당 Luna: /root/luna_investor (code, gpt-5.6-luna), 단일 구현 소유자. explore→plan→code→review 순서로 진행합니다.
- 워크트리 절대 경로: /home/kwl/projects/jusik-market-data-live-contract-fixes
- 작업 브랜치: fix/market-data-live-contract-fixes
- 기준 커밋 SHA: e608835832f2a3f9b3ba0ecfa247ddafd54a93b4
- 통합 대상 브랜치: 로컬 main
- 입력과 선행 작업: free-market-data-collector 완료 main 8521268, durable docs main 8602e3b. 실제 smoke에서 구현 KRX URL은 HTTP 403, 공식 KRX KOSPI·KOSDAQ endpoint는 현재 키로 401, Alpha 응답은 긴 warrant 명칭 때문에 전체 validation 실패했습니다.
- 수정 허용 범위: collector source URL/request/response parser, listing security-type/name normalization, collector env loading·CLI, 관련 테스트·문서·mandate/checksum·개발 기록. 전략·PAPER·broker/order·프런트는 변경하지 않습니다.
- 포트·테스트 DB·출력 경로: 3366/8366, worktree-local test environment. 실제 smoke raw/cache/output은 `/home/kwl/.local/share/jusik/portfolio-audit/20260915-market-data-live-contract-fixes`에 비밀정보 없이 저장합니다. 운영 주문은 사용하지 않습니다.
- 검증 명령과 결과: 작업 및 통합 main에서 관련 pytest 99개, Ruff, strict mypy 9개 source, `git diff --check`, Next.js production build가 통과했습니다. 독립 review는 KRX 손상 envelope, 설정 오류 비노출, 인증 실패 비캐시, Yahoo NASDAQ `NCM` identity를 직접 probe하고 최종 P1/P2 없음으로 판정했습니다. 실제 US 2종목 smoke는 재개 시 manifest 불변과 `ready:true`를 확인했고, 안정 완료일 기준 1년·100종목 수집과 웹 API 파일럿 실행을 완료했습니다.
- 결과 커밋 SHA: 9a3bf3a, e8a7465, feb836f, aeeed81.
- 검토 결과와 남은 문제: KRX KOSPI·KOSDAQ 공식 endpoint는 현재 키를 `krx authentication was rejected`로 거부하므로 한국 자료와 실행은 준비되지 않았습니다. US 1년 표본은 100개 중 40개가 완전한 무배당·무분할 이력으로 남았고 60개는 기업행사·부분/무응답·identity 불일치로 제외됐습니다. 무료 근사 표본의 선택 편향과 배당 미반영 한계를 유지하며 PAPER·실주문에는 사용하지 않습니다.
- 병합 직전 main SHA: e69f85876e4b25f7ba689c228a1ad1bfbee6d59a
- 통합 커밋 SHA와 정리 여부: fee4eddb21e022fe3a89c4d269a7ed53fc03a06d. 통합 검증과 handoff 보존 후 전용 워크트리를 제거했습니다.
- 통합 검증 실패 원인과 복구 결과: 해당 없음
- 개발 기록 경로와 갱신 여부: `docs/development-records/2026-09-15-market-data-live-contract-fixes.md` 갱신 완료
- handoff 저장 경로와 갱신 여부: `/home/kwl/.local/share/jusik/portfolio-audit/20260915-market-data-live-contract-fixes/HANDOFF.md` 및 루트 `HANDOFF.md` 갱신 완료

## free-market-data-collector

- 상태: 완료
- 목표와 완료 조건: 무료·공개 원천에서 한국·미국의 날짜별 종목 구성, 조정 가능한 과거 OHLCV와 미국 KRW/USD 환율을 실제로 수집해 기존 approximate prepared dataset을 생성합니다. 원본 응답과 provenance를 보존하고, 호출 제한·중단 재개·부분 실패를 안전하게 처리하며, 현재 종목을 과거에 소급하지 않습니다.
- 담당 Luna: /root/luna_investor (code, gpt-5.6-luna), 단일 구현 소유자. explore→plan→code→review 순서로 진행합니다.
- 워크트리 절대 경로: /home/kwl/projects/jusik-free-market-data-collector
- 작업 브랜치: feat/free-market-data-collector
- 기준 커밋 SHA: f15a3ffcbedc0355e406277acac2ef4b4d994a06
- 통합 대상 브랜치: 로컬 main
- 입력과 선행 작업: approximate-market-data 완료 main 0d56e251751793543b1e941f9fec474182b27998, 기존 `ApproximateDataset`·`import-file`·readiness 계약, 최신 연구 mandate. 사용자는 무료 데이터 수집기부터 진행하도록 승인했습니다.
- 수정 허용 범위: market-data 수집 adapter·정규화·raw/cache manifest·재개 가능한 CLI, 관련 config·환경 예시·테스트·시장 연구 문서와 mandate. 전략·PAPER·broker/order·프런트 실행 계약은 변경하지 않습니다.
- 포트·테스트 DB·출력 경로: 3365/8365, 워크트리 내부 임시 raw/cache와 pytest tmp_path. 운영 DB·공유 cache·실제 주문은 사용하지 않습니다. 실제 smoke는 비밀값을 기록하지 않고 별도 임시 디렉터리에 제한합니다.
- 검증 명령과 결과: 통합 main에서 collector·approximate·market research·API·mandate 관련 pytest 104개, Ruff와 strict mypy 8개 source가 통과했습니다. 독립 review는 KRX 공식 POST/trdDd 계약, 날짜별 LIST_SHRS 기업행사 proxy, 한국 canonical symbol, 미국 Alpha Vantage membership·Yahoo OHLCV·FRED 사전 관측 환율, 미래 checkpoint 독립성, retry별 호출 예산, cache hash·완료 marker·원자적 출력과 비밀정보 비노출을 probe로 확인하고 최종 P1/P2 없음으로 판정했습니다. 자격증명 없는 CLI smoke는 exit 2, ready false, 기존 출력 보존을 확인했습니다.
- 결과 커밋 SHA: 0102858, a52387e, b43f0ef, 57b27d9, e591f21, 6722606.
- 검토 결과와 남은 문제: KRX는 날짜별 KOSPI·KOSDAQ 일별매매정보를 사용하고 상장주식 수 변화·거래행 누락·종목 소멸을 이벤트 이후 제외합니다. 미국은 시작 시점 historical listing에서 표본을 고정하고 이후 checkpoint를 과거에 소급하지 않으며 Yahoo 가격과 거래 시점 전에 이용 가능한 FRED 환율만 사용합니다. 현재 KRX·Alpha Vantage·FRED 키와 KRX 서비스 승인이 없어 실제 provider smoke와 1년 파일럿 데이터 생성은 아직 실행하지 않았습니다.
- 병합 직전 main SHA: d5b633075f85f871d20bf41311edde0af31860d6
- 통합 커밋 SHA와 정리 여부: 1407d71fe5b4327b8e81c0429a38055e63f30bd0. 통합 검증·배포·handoff 후 전용 워크트리를 정상 제거합니다.
- 통합 검증 실패 원인과 복구 결과: 첫 재배포에서 ngrok 새 터널의 basic-auth 확인이 일시적으로 실패해 전체 프로세스가 안전 종료됐습니다. 같은 정책의 독립 probe에서 1초부터 인증 적용을 확인한 뒤 제품 변경 없이 재시작하여 외부 비인증 401을 재확인했습니다.
- 개발 기록 경로와 갱신 여부: `docs/development-records/2026-09-15-free-market-data-collector.md`에 완료 범위, 계약, 검증, 안전 상태와 재개 조건을 기록합니다.
- handoff 저장 경로와 갱신 여부: `/home/kwl/.local/share/jusik/portfolio-audit/20260915-free-market-data-collector/HANDOFF.md` 및 루트 `HANDOFF.md`를 갱신합니다.

## approximate-market-data

- 상태: 완료
- 목표와 완료 조건: 논문급 전수 PIT 대신 개인 투자 판단용 무료 근사 자료로 한국·미국의 1년 파일럿과 3년 최종 연구를 실행할 수 있게 합니다. 현재 후보의 과거 고정은 금지하고, 과거 연간 종목 목록의 결정적 표본 안에서 거래일마다 거래량 상위 20개를 재발굴합니다. 근사 등급·coverage·누락·배당/상폐/환율 가정을 결과와 웹에 공개하며 strict·fixture·PAPER·실거래와 혼합하지 않습니다.
- 담당 Luna: /root/luna_investor (code, gpt-5.6-luna), 단일 구현 소유자. explore·plan·구현·독립 review와 지적 수정 재검토를 완료했습니다.
- 워크트리 절대 경로: /home/kwl/projects/jusik-approximate-market-data
- 작업 브랜치: feat/approximate-market-data
- 기준 커밋 SHA: b5117e4899a2be37bda6033297034db691ff632d
- 통합 대상 브랜치: 로컬 main
- 입력과 선행 작업: staged-market-validation 완료 main b850984, 사용자 승인 “논문을 쓰는 것이 아니므로 과도하게 정교한 데이터 없이 실용적으로 진행”. 현재 후보를 과거로 소급하지 않는 기존 결정은 유지합니다.
- 수정 허용 범위: approximate market history source·모델·저장소·전략 분기·service/API/CLI/config/cache, 관련 fixture·테스트, `/research/market` coverage UI·타입, `.env.dev.example`, mandate·시장 연구 문서. strict PIT, 기존 PAPER·operations·broker/order 경로는 보존합니다.
- 포트·테스트 DB·출력 경로: 작업 서버 3364/8364, 워크트리 내부 Python/Node 환경, pytest 임시 DB·fixture·cache. 실제 무료 source smoke는 별도 임시 cache/artifact만 사용하고 운영 DB·실제 주문은 사용하지 않습니다.
- 고정 계약: research grade는 strict와 approximate를 분리합니다. approximate 기본 표본은 과거 연간 목록에서 고정 seed로 시장별 최대 100개이며 매일 표본 내 거래량 순위를 재계산합니다. pilot/final은 같은 source·표본·정규화·누락 정책 계약만 연결합니다. 개별 비보유 종목 자료 누락은 제외 수와 coverage를 기록하고 허용하지만, 거래일 전체 모집단·초기 FX·숫자/통화 오류는 차단합니다.
- 검증 명령과 결과: 통합 main에서 관련 pytest 82개, Ruff, strict mypy 8개 모듈, frontend lint/typecheck/production build와 `git diff --check`가 통과했습니다. 독립 review는 일별 membership의 다음 시가 인과성, 수수료·슬리피지·세금·SMA 청산·20종목 한도·낙폭 latch, strict 분리, 파일 import의 provenance·기간 검증을 확인했고 최종 P1/P2 없음으로 판정했습니다. iPad 1024×1366 브라우저에서 네 등급·시장 준비 카드와 실행 폼을 확인했고 console error 0건이었습니다.
- 결과 커밋 SHA: 8228f3c, dd1b1c5, 45eba8f, e09181c, 3044bbe, 1cdd7e2, 96835de, 3f4e822, 12185b7.
- 검토 결과와 남은 문제: 실제 네트워크 수집기를 구현한 것이 아니라 검증된 prepared response file의 `import-file`과 운영 cache 소비 경로를 구현했습니다. 현재 준비 파일과 KRX·Alpha Vantage·Yahoo·FRED 자료가 없어 KR/US approximate readiness는 false이며 실제 1년·3년 수익률을 생성하지 않았습니다. 웹은 파일 부재와 invalid 파일을 구분하고, 근사 표본·coverage·누락·배당/상폐 한계를 표시합니다. PAPER·실주문은 변경하지 않았습니다.
- 병합 직전 main SHA: 60117dcad87682c75c2eb3cc3f252f11ffbcc004
- 통합 커밋 SHA와 정리 여부: 기능 통합 20117bf5b946139c86754ac360376993d7f5c3b1, 검증 수정 통합 7cba46b2b4032b1135264027a5c93aaa8af1f81b, readiness 통합 c9089b893a918d0968b1d52653096bacf9799588. 검증과 handoff 보존 후 이번 워크트리를 정상 제거합니다.
- 통합 검증 실패 원인과 복구 결과: 기준 저장소 가상환경 경로 차이, cwd 상대 checksum 테스트, strict mypy의 불필요 ignore를 수정했습니다. 운영 API에서 발견한 cache·달력·KR/US FX 상태/문구 모순과 invalid 파일 오표시도 수정하고 재배포·재검증했습니다.
- handoff 저장 경로와 갱신 여부: `/home/kwl/.local/share/jusik/portfolio-audit/20260914-approximate-market-data/HANDOFF.md` 및 루트 `HANDOFF.md`를 갱신합니다.

## staged-market-validation

- 상태: 완료
- 목표와 완료 조건: 시장 PIT 연구를 1년 파일럿과 정책 고정 3년 최종 검증으로 분리합니다. 파일럿은 자료·인과성 검증 전용이며 모델 선택이나 PAPER/실거래 활성화 근거가 될 수 없습니다. 최종 실행은 완료된 같은 시장 파일럿을 참조하고 동일 정책·자본·비용·원천 계약을 강제하며, 평가 시작 전 20개 완료 거래일의 준비 자료까지 검증합니다.
- 담당 Luna: /root/luna_investor (code, gpt-5.6-luna), 단일 구현 소유자. explore·plan·구현·독립 review와 지적 수정 재검토를 완료했습니다.
- 워크트리 절대 경로: /home/kwl/projects/jusik-staged-market-validation
- 작업 브랜치: feat/staged-market-validation
- 기준 커밋 SHA: 9a22fd044433aac4a1fd2ce0e432fcf8138c69f3
- 통합 대상 브랜치: 로컬 main
- 입력과 선행 작업: point-in-time-discovery 완료 main 40a022f, 최신 research mandate, 사용자 승인 “1년 파일럿 후 동일 정책 3년 최종 검증”. 실제 provider 자료는 계속 부족하므로 production 실행은 fail-closed입니다.
- 수정 허용 범위: market research request/run/result/store/service/strategy/API, 관련 fixture·테스트, `/research/market` 단계 UI와 타입, mandate·시장 연구 문서. 기존 PAPER·operations·broker/order 경로와 일반 연구 엔진은 변경하지 않습니다.
- 포트·테스트 DB·출력 경로: 작업 서버 3363/8363, 워크트리 내부 Python/Node 환경, pytest 임시 DB와 fixture. 운영 DB·공유 연구 DB·실제 주문·기존 서버는 사용하지 않습니다.
- 고정 계약: pilot은 end date의 정확한 1년 전부터, final은 정확한 3년 전부터 평가하며 윤년 2월29일은 대상연도 2월28일로 맞춥니다. final은 completed·ready·complete pilot ID가 필수이고 market, current policy hash, 자본·수수료·세금·슬리피지, canonical data contract hash가 같아야 합니다. input hash는 기간별로 다릅니다. 시작 전 20개 완료 시장 세션은 지표 warmup이며 거래·equity를 만들지 않고, 신규 상장 전 bar를 요구하지 않습니다.
- 검증 명령과 결과: 통합 main에서 market research·research API·runner planning pytest 51개, Ruff format/check, strict mypy 7개 모듈, frontend lint/typecheck/production build와 `git diff --check`가 통과했습니다. 운영 API는 KR/US 모두 실제 PIT provider 필수 자료 부족을 반환했고, iPad 1024×1366 브라우저에서 1년 파일럿→3년 최종 UI와 console error 0건을 확인했습니다. 외부 ngrok은 기존 인증 정책에 따라 비인증 401입니다.
- 결과 커밋 SHA: 7d33b34, cc78b2e, 318f9d6, fe038fe, 5c2fe6e, cbffc59.
- 검토 결과와 남은 문제: 신규상장 warmup 예외, 고정 가정·legacy 우회, 시장 불일치 UI, 과거 staged 행 읽기 호환성, final 후보 표시 진실성, 중첩 가변 list 역직렬화를 수정했습니다. 독립 최종 검토 P1/P2 없음. 실제 1년·3년 성과 산출은 membership·OHLCV·기업행사·PIT FX 공급원 연결 뒤 별도 실행합니다.
- 병합 직전 main SHA: bfb31f6a13ab081d09a1cb1f48d2116f1268c7ed
- 통합 커밋 SHA와 정리 여부: bb02962fbce5257c47f0ac729c05a337237862c6. 통합 검증과 handoff 보존 후 작업 워크트리를 정상 제거합니다.
- 통합 검증 실패 원인과 복구 결과: 해당 없음
- handoff 저장 경로와 갱신 여부: `/home/kwl/.local/share/jusik/portfolio-audit/20260914-staged-market-validation/HANDOFF.md` 및 루트 `HANDOFF.md`를 갱신합니다.

## point-in-time-discovery

- 상태: 완료
- 목표와 완료 조건: 한국·미국을 각각 1억원의 독립 계좌로 모의 운용합니다. 과거 각 거래일 종가까지 공개된 전체 시장 자료로 개별주 거래량 상위 20개를 다시 산출하고, 진입·청산 신호를 다음 거래일 시가에 체결해 수익률을 계산합니다. 전체 종목 OHLCV·당시 상장 상태·기업행사·환율 중 필수 자료가 누락되면 결과를 만들지 않고 준비 상태와 원인을 표시합니다. 현재 후보를 과거에 고정하는 경로는 허용하지 않습니다.
- 담당 Luna: /root/luna_investor (code, gpt-5.6-luna), 단일 구현 소유자. explore·plan·독립 review와 수정 재검토를 완료했습니다.
- 워크트리 절대 경로: /home/kwl/projects/jusik-point-in-time-discovery
- 작업 브랜치: feat/point-in-time-discovery
- 기준 커밋 SHA: 30c221107d79868cb3605fd0cb6c4c48ab484d95
- 통합 대상 브랜치: 로컬 main
- 입력과 선행 작업: 최신 `docs/research-mandate.json`, 기존 investor 거래량 발굴 규칙과 research portfolio 비용·환율·검증 계약. KRX Open API와 미국 전시장 자료 공급자의 자격증명은 현재 없으므로 실제 3년 성과를 만들지 않습니다.
- 수정 허용 범위: point-in-time 시장 원장·source adapter·동적 발굴/백테스트 모델과 API, investor/research 웹 연결, 설정 예시·사용자 문서·mandate 및 관련 테스트. 기존 PAPER·실주문·operations 실행 계약은 변경하지 않습니다.
- 포트·테스트 DB·출력 경로: 작업 서버 3362/8362, 워크트리 내부 Python/Node 환경, pytest 임시 DB와 fixture. 운영 DB·공유 연구 DB·실제 주문·기존 서버는 사용하지 않습니다.
- 고정 연구 규칙: 시장별 최대 20종목, 신규 진입은 당시 NAV 5%, 거래량 순위 우선, 현금 부족 시 건너뛰고 기록, 기존 보유는 후보 이탈만으로 매도하지 않음. 20일 고점 돌파 및 당일 거래량이 직전 완료 20일 평균 초과 시 다음 시가 진입, 종가가 SMA20 아래인 상태가 2거래일 연속이면 다음 시가 청산. 미국 계좌는 시작 시점 환율과 비용으로 USD를 조성하고 USD 원장과 KRW 평가 곡선을 함께 제공합니다. KRW NAV 기준 최대 낙폭 20%입니다.
- 검증 명령과 결과: main 관련 pytest 43개, 신규·mandate 35개, Ruff check/format, strict mypy 8개 모듈, frontend lint/typecheck/production build 통과. 전체 pytest는 957개 통과·기존 현재 시각 의존 3개 실패였습니다. iPad 크기 운영 브라우저에서 두 시장의 필수 자료 부족 상태, 연구 단계·메뉴와 console error 0개를 확인했습니다.
- 결과 커밋 SHA: 59e5a74, cc54ea5, 706b7ba, 28203a2, 97e8035, 74218f5. 후속 연결 수정은 main에 ae30e0c로 cherry-pick했습니다.
- 검토 결과와 남은 문제: 미래 일봉·FX, 기업행사 무시, 체결일 자료 누락, 시장·통화 혼합, readiness 조작, artifact 불일치, final-day 낙폭 청산 미체결과 잘못된 backend URL을 수정했습니다. 독립 최종 검토 P1/P2 없음. 실제 3년 실행은 KRX 승인 자료와 미국의 검증 가능한 전시장 OHLCV·historical membership/actions·PIT FX가 모두 준비된 뒤 별도 수행합니다.
- 병합 직전 main SHA: 84de414fbb664cd5534d69d65f5c3e8fafd2d120
- 통합 커밋 SHA와 정리 여부: 기능 통합 052ba5f5a1c8b7168c849a7cb7ac68b57183c458, 최종 코드 ae30e0c73e6778c700bf87c3ae4f79af5a1a98cc. 검증·handoff 보존 후 이번 워크트리를 정상 제거합니다.
- 통합 검증 실패 원인과 복구 결과: 운영 브라우저에서 연구 화면이 일반 backend 8000을 조회해 자료를 못 불러오는 문제를 발견했습니다. 기존 `researchBackendUrl`로 수정·추가 통합·재배포 후 한국·미국 readiness 표시를 확인했습니다. 전체 pytest의 3개 실패는 이번 diff 밖의 날짜·현재 시각 의존 기존 테스트입니다.
- handoff 저장 경로와 갱신 여부: `/home/kwl/.local/share/jusik/portfolio-audit/20260914-point-in-time-discovery/HANDOFF.md` 및 루트 `HANDOFF.md`를 갱신합니다.

## volume-discovery

- 상태: 완료
- 목표와 결과: 승인한 거래량 기준으로 한국·미국 개별주 후보를 각각 최대 20개 제공하고 ETF를 별도로 분리했습니다. 미국 NAS/NYS/AMS를 숫자 거래량으로 통합 정렬하고 직전 완료 20거래일 평균 대비 거래량 배수를 웹에 표시합니다.
- 담당: /root/luna_investor (gpt-5.6-luna), 단일 구현 소유자. explore·plan·독립 review 완료. 원본 turn context 대조로 code 11개 turn과 review 9개 turn 모델을 확인했습니다. 사후 helper의 지연 settings marker 한계와 동등 검증 근거는 audit에 보존했습니다.
- 워크트리·브랜치: /home/kwl/projects/jusik-volume-discovery, feat/volume-discovery. 통합 검증 및 산출물 보존 후 정상 제거했습니다. 기존 미완료 워크트리 6개는 보존했습니다.
- 기준 및 병합 직전 main: 11a9e61. 결과 커밋: e3c6dda, 335baee, 5b6cff0. 기능 통합: 2127399afeb26a9cdc6d17fdbf7c4b4616459220. 형식 수정 최종 통합: db11b1ba847570429632e23f97e7980c281fc1c7.
- 변경 범위: investor 후보 데이터·모델·fixture·관련 검사, 웹 후보 목록·계약과 사용자 안내. 실제 동시 조회 실패를 재현한 뒤 kis.py의 credential별 인증 공유까지 범위를 좁혀 추가했습니다. 기존 가치·매도 분석, 논거 저장, 연구·주문 로직과 운영 DB는 보존했습니다.
- 검증: main pytest 99개, strict mypy 8개 모듈, Ruff 6개 파일, frontend lint/typecheck 및 운영 production build 통과. 형식 수정 후 영향 테스트 63개 재통과. 기존 논거 합성 브라우저 20개, 후보 화면 35개, 운영 브라우저 49개 검사 통과.
- 실제 자료: 새 프로세스 첫 동시 조회 8.06초, 한국·미국 주식 각 20개, ETF 18/20개. 미국 주식 NAS 12/NYS 7/AMS 1. NVDA 20일 평균을 별도 원자료로 재계산해 일치 확인했습니다.
- 검토 및 복구: 코스닥 코드 대체 조회 누락, 동시 인증 충돌, 분할 당일 배수 계산, 공유 작업 취소 전파, 미검사 건수와 합성 수치 불일치를 수정했습니다. 독립 최종 검토 P1/P2 없음. main 형식 검사에서 테스트 파일 2개가 실패하여 동일 Luna가 수정했고 재검사가 통과했습니다.
- 한계: KIS 첫 페이지 수집 후보를 정렬하며 전체 시장 순위를 보장하지 않습니다. Yahoo 분류 미확인 후보는 제외하고, 일별 이력·분할 등으로 배수가 불확실하면 사유와 함께 보류합니다. KIS 순위 수량과 Yahoo 배수 분자·시각을 구분해 공개합니다.
- 운영: /investor와 종목 상세를 운영 웹에 반영했습니다. 자동 실행기 paused, service/timer inactive 유지. 테스트 3351/8351 및 브라우저 종료. 실제 주문·원격 push 없음. 기존 사용자 미추적 파일 보존.
- 증거와 handoff: /home/kwl/.local/share/jusik/portfolio-audit/20260914-volume-discovery/HANDOFF.md. 검사 결과·diff·환경 버전·실제 자료·화면·합성 DB를 보존하고 루트 HANDOFF.md 최신 안내를 추가했습니다.

## investor-workflow

- 상태: 완료
- 목표와 완료 조건: 한국·미국 후보 발굴, 가치·추세 진입 판단, 투자 논거 저장과 보유·매도 검토를 코드와 웹에 연결했습니다. local main 통합·독립 검토·운영 웹 반영·handoff와 작업 정리를 완료했습니다.
- 담당 Luna: /root/luna_investor (gpt-5.6-luna), 구현 소유자 한 명. explore·plan·code·review 순서로 진행했습니다. reviewer 사후 helper는 7개 turn을 통과했고 Luna 8개 turn의 원본 child turn_id/model을 별도 확인했습니다. 지연된 settings marker로 인한 helper 오류는 audit에 원문 근거와 함께 기록했습니다.
- 워크트리 절대 경로: /home/kwl/projects/jusik-investor-workflow. 통합 검증·산출물 보존 후 정상 제거했습니다.
- 작업 브랜치: feat/investor-workflow. 모든 결과 커밋 통합 후 정상 삭제했습니다.
- 기준 커밋 SHA: d578bf62bb6bbb98a7ba0c5edddd93d4ba3a12de.
- 통합 대상 브랜치: local main. 첫 병합 직전 9fd1851, 기능 통합 3466db260c190f9d6b0efa3cda4687402112ef8d, 헤더 수정 추가 통합 5b58c5e2e10561d583656f130498a471f41f3f0c.
- 입력과 범위: 사용자 투자자 관점 로직 구현 요청. 기존 KIS 조회와 Yahoo 가격·조정 일봉을 사용하며 시장 전수 평가나 자동 내재가치 산정으로 표시하지 않습니다. 사용자 EPS·목표 PER·안전마진 가정으로 가격 범위를 계산합니다. 연구 결과·PAPER10%·주문 실행 경계를 보존했습니다.
- 결과 커밋 SHA: 4b02b8a, 99f22e2, bd6c589, d733108, af3c077, a53ca4b, 6a756c3. 최초 중간 커밋 b747498은 작업자가 정리했으며, 이후 후속 수정은 별도 커밋으로 보존했습니다.
- 검증 결과: main 관련 pytest 90개, 변경 Python 9개 Ruff/format 및 8개 strict mypy 통과. frontend lint/typecheck와 운영 production build 통과. fixture 브라우저 25개, 운영 화면 14개와 최종 겹침 검사 12개 통과. 실제 KR/US 후보 각 20개, 삼성전자/NVIDIA/코스닥 086520의 사용 가능한 시세와 확정 일봉 확인.
- 검토와 복구: 종목 동일성·회계기간·코스닥·저장 후 최신 재평가·시세 지연·통화·종류 검증·오류 URL 인코딩을 보완했습니다. 운영 이미지에서 발견한 전역 header 높이 상속 겹침도 수정 후 확인했습니다. 최종 독립 검토 중요 지적 없음.
- 포트·테스트 DB·산출물: fixture 8341 및 테스트 웹 3341 종료. 전용 환경·테스트 DB 3개를 정리했으며, 필요한 결과·패치·환경 정보 등 audit 77개 파일의 SHA를 확인했습니다. 영구 audit /home/kwl/.local/share/jusik/portfolio-audit/20260914-investor-workflow.
- 운영 상태: /investor와 기존 /research HTTP 200. 자동 실행기 paused와 service/timer inactive 유지. 기존 미추적 파일과 6개 미완료 워크트리 보존. 원격 push와 실제 주문 없음.
- handoff: /home/kwl/.local/share/jusik/portfolio-audit/20260914-investor-workflow/HANDOFF.md. 루트 HANDOFF.md에 최신 안내를 추가하고 기존 인계를 보존합니다.

## agent-tooling — 2026-09-13

- 상태: 완료
- 목표와 완료 조건: Serena MCP, Playwright CLI와 Context7 도구를 검증하고, Codex 역할 지정과 압축 보고 및 감독 스킬을 적용합니다. 관련 검사와 독립 검토 후 로컬 main에 통합합니다.
- 담당 Luna: 프로젝트 구현 `/root/project_tooling`, 개인 스킬 `/root/skill_tooling`, 사용자 환경 도구 설치 `/root/install_tools`. 파일 소유 범위를 분리했습니다.
- 워크트리 절대 경로: `/home/kwl/projects/jusik-agent-tooling`
- 작업 브랜치: `feat/agent-tooling`
- 기준 커밋 SHA: `a20e766f7e708574b82a14e55c382382eddfc3d8`.
- 통합 대상 브랜치: `main`
- 입력과 선행 작업: 사용자 승인된 추천 도구와 사용량 감사. 자동 runner와 timer는 기존 중지 상태를 유지합니다.
- 수정 허용 범위: 프로젝트 `.codex/agents`, 감독 운영 문서와 AGENTS 안내. 검증 helper와 테스트는 개인 `jusik-supervisor` 스킬에 둡니다. 제품·전략·주문·운영 데이터와 runner 실행 코드는 범위 밖입니다.
- 포트·테스트 DB·출력 경로: 전용 임시 fixture와 `~/.local/share/jusik/tooling-audit/20260913-agent-tooling/`. 도구 설치 smoke는 별도 `20260913-tools/`입니다.
- 검증 명령과 결과: 통합 pytest 14개, 탐색 스킬 Node 테스트 4개, Ruff, strict mypy, 스킬 validator 3개, TOML 역할 매핑과 역할별 preflight 4개를 통과했습니다. 실제 Luna/Terra child audit와 Serena·Playwright·Context7 실행 검증도 통과했습니다. `~/.local/share/jusik/tooling-audit/20260913-agent-tooling/integration-checks.json`과 `../20260913-tools/VERIFICATION.md`에 근거를 보존했습니다.
- 결과 커밋 SHA와 검토 결과: `77aae489da4d895e048592603aeef3a5de0ccbcf`까지 프로젝트 문서를 반영했습니다. 독립 review에서 로그 검증의 정상 세션 거부·근거 없는 turn 허용을 수정한 뒤 최종 PASS를 받았습니다. helper는 사전/사후 검사이며 spawn을 가로채는 장치는 아닙니다.
- 병합 직전 main SHA와 통합 검증: `c6397cad504b40a79b1cbc2ac07460b761fae7e1`. 위 통합 검사 모두 통과했습니다. 제품·프런트엔드 변경이 없어 제품 빌드는 적용 대상이 아닙니다.
- 통합 커밋 SHA와 정리 여부: `13dce8ef52adbc5f9b1e1f3ff3f5d8ac13c375fb`. 필요한 스킬 사본·SHA·검증 로그·인계를 보존한 뒤 이번 워크트리와 병합한 로컬 작업 브랜치를 제거했습니다. 기존 연구 워크트리 6개는 보존했습니다.
- handoff 저장 경로와 갱신 여부: `~/.local/share/jusik/tooling-audit/20260913-agent-tooling/HANDOFF.md`에 저장하고 루트 인계에 링크를 추가합니다. 자동 연구는 paused, service와 timer는 inactive로 유지합니다. 사용자 요청에 따라 모든 저장을 마친 뒤 Windows 종료 명령을 수행합니다.

기준 저장소에서 Astra만 갱신합니다. 작업 배정 시 [운영 절차의 기록 양식](worktree-workflow.md#작업-지시와-기록)을 사용하고, 상태가 바뀔 때 실제 Git 상태와 검증 결과를 반영합니다.

## 활성 작업

없습니다. 자동 개발 큐와 실행 중인 작업은 전용 runner DB와 웹 연구 이력에서 확인합니다.

## 완료 작업

### entry-amount-distribution-v1

- 상태: 완료
- 목표와 완료 조건: 기존 32개 결과의 진입 금액 분포 분석을 재사용해 저장소에 통합하고 재현·독립 리뷰·게시·handoff를 완료합니다. 거래 제약은 구현하지 않습니다.
- 담당 Luna: entry_amount (gpt-5.6-luna), 단일 구현 소유자
- 워크트리: /home/kwl/projects/jusik-entry-amount-distribution-v1; 브랜치 feat/entry-amount-distribution-v1
- 기준: a725004; 통합 대상 로컬 main
- 입력과 계획: b73bef5d 시도의 완료된 explore/plan, analysis/analyze.py·test_analyze.py와 독립 계산을 재사용합니다. 새 조사는 현재 코드 호환성에 한정합니다. 고정 원본 32개·manifest를 읽기 전용으로 검증합니다.
- 수정 허용 범위: backend/jusik/research_entry_amount_distribution.py, 대응 테스트, docs/research/entry-amount-distribution-v1.md. 등록부·게시·handoff는 Astra 소유입니다.
- 환경: 워크트리 전용 .venv 및 validation, 서버·DB 없음. 영구 audit entry-amount-distribution-v1-5ed7695c
- 검증: focused pytest, Ruff, strict mypy, 고정 입력 재현 및 기존 독립 수치 대조, 독립 review, main 재실행
- 중단 조건: 입력 해시·회계·수량 불일치. 임계값 선택·추가 전략 실험은 범위 밖입니다.
- 결과 커밋: 6719c36fe61f09dc134f86d90fe31d6c7c81014c. 병합 직전 main a725004, 통합 f8143f9eb103510c9835e0593264d8e42d557c64
- 검토: 독립 review 통과. 재현 명령 줄 연결 수정 후 재검토 완료
- 통합 검증: 관련 pytest 28개(기존 경고 2개), backend 전체 Ruff check/format, strict mypy 75개 소스 통과. 32개 결과·820 BUY, 독립 1,728개 수치 및 기존 기계 산출물 3개 바이트 일치
- 보존: 원본 36개 JSON·기존 backend 모듈 SHA 동일. 실주문·push·PAPER 엔진/DB·GPU 변경 없음
- 웹: entry-amount-distribution-20260912, 5개 문서·API/웹 다운로드 10개 해시 및 제목 확인. 기존 이력 보존. mount root 교체 실패는 파일 단위 게시로 복구
- 환경·결과·handoff를 영구 audit entry-amount-distribution-v1-5ed7695c에 보존하고 archive-manifest.json 해시 대조 후 worktree remove 완료. 브랜치 보존
- handoff: /home/kwl/.local/share/jusik/portfolio-audit/entry-amount-distribution-v1-5ed7695c/handoff.md 및 루트 HANDOFF.md. 통합 검사 실패 없음. UI 변경 없음으로 frontend build 생략


### 2026-09-12 병합 워크트리 정리

- 사용자 지시에 따라 독립 하위 작업은 최대 4명으로 병렬 진행하고, main 병합·통합 검증 후 완료 워크트리를 제거하는 원칙을 운영 문서에 반영했습니다.
- `development-runner`, `entry-attribution`, `experiment-guard`, `unheld-entry-experiment` 4개가 main의 조상이며 미커밋 변경과 사용 중인 프로세스가 없음을 확인했습니다.
- validation 결과 132개 파일을 SHA-256으로 대조해 `20260911T221657Z-worktree-cleanup/`에 보관했습니다. 각 환경의 패키지 버전도 보관했습니다.
- `git worktree remove`로 4개 폴더와 내부 가상환경·캐시를 제거했습니다. 강제 옵션은 사용하지 않았으며 커밋과 브랜치 이력은 유지했습니다.
- 아래 완료 항목의 워크트리 보존 기록은 당시 상태입니다. 현재 재현 자료의 위치는 위 cleanup audit과 기존 연구 audit입니다.
- 설정 갱신 중 자동 실행기를 일시 중지했으며, 진행 중이던 진입 금액 분석은 이전 시도 기록과 함께 재시도하도록 복구합니다. PAPER와 GPU 서비스는 변경하지 않습니다.

### development-runner

- 상태: 완료
- 목표: 영속 연구 큐를 Codex supervisor에 전달하는 자동 실행기를 설치하고 반복 실행·중단·웹 이력을 검증합니다.
- 담당 Luna: `/root/work_attribution` (새 작업으로 재배정)
- 워크트리: `/home/kwl/projects/jusik-development-runner`, `feat/development-runner`, 기준 `cb075f2b09d2dbbfa55c5c58ba2dfca6dcb72313`
- 결과 커밋: `406a897`, 수정 `312761f`, 최종 `fd2df78`. append-only 이력
- 병합 직전 main: `2c9a7ef`; 로컬 통합: `a49b30a`
- 범위: 신규 runner/store/테스트, systemd service/timer, 운영 문서와 README 안내. 감독이 AGENTS 운영 안내를 추가했습니다.
- 검증: 신규 13개 테스트, 독립 리뷰 통과. main 전체 pytest 523개(기존 경고 2개), Ruff 116개 파일, strict mypy 74개 소스 통과. UI 변경이 없어 frontend build는 미실행
- 실제 검증: Codex Astra 호출·Luna 위임·완료 schema 호환성, 가짜 작업의 systemd 단독 2회 및 타이머 자동 2회, 시작/완료 이력 전송, SIGTERM interrupted 저장과 자식 종료, 분리된 자식의 cgroup timeout 종료를 확인했습니다.
- 설정: 작업당 90분, UTC 하루 8회 시작, 종료 뒤 약 2분 간격. 금액 상한은 아니며 실패/중단 작업은 명시적 retry 전까지 보존합니다.
- 운영 설치: 사용자 `jusik-development-runner.service`와 `.timer`, 별도 상태 DB·비공개 로그, 기존 연구 history journal 연동. 사용자 linger 활성화. 초기 연구 5개 큐와 선행 조건을 등록했습니다.
- 리뷰 수정: 1초 이상 실행의 stdin 재전송 오류, 살아 있는 이전 process group 확인, SIGTERM/SIGINT 중단과 빠른 자식 종료 race를 수정하고 회귀 검증했습니다.
- 완료의 의미: runner는 commit·artifact hash를 확인하며 tests/review 결과는 agent 보고로 구분합니다. 기존 PAPER·GPU·실주문 경로는 변경하지 않습니다. 작업별 자세한 연구 결과는 후속 supervisor가 웹에 게시합니다.
- 증거: `20260911T211748Z-autodev-install/`의 main-pytest.log, timer-fixture-result.json, signal-fixture-result.json, cgroup-smoke-result.json, preservation-latest.json
- 보존·정리: 고정 19개 파일·9개 원장 테이블·GPU 상태 보존 확인. 재현용 워크트리와 독립 `.venv`는 보존하며 임시 검증 unit은 제거했습니다. 운영 unit만 유지합니다.
- handoff: 기준 저장소 `HANDOFF.md` 최신 절 갱신. 원격 push·PR은 이번 범위에서 수행하지 않았습니다.

### entry-attribution

- 상태: 완료
- 목표와 완료 조건: 고정된 미보유 진입 실험 32개의 종목별 회계 손익 및 월별 포트폴리오 손익·거래·비용을 독립 재계산하고 16쌍의 차이를 웹에 공개합니다. 재계산 잔차는 0.000001원 이하여야 합니다.
- 담당 Luna: `/root/work_attribution`
- 워크트리 절대 경로: `/home/kwl/projects/jusik-entry-attribution`
- 작업 브랜치: `feat/entry-attribution`
- 기준 커밋: `ff607a7`
- 통합 대상: 로컬 `main`
- 입력과 선행 작업: 이전 32회 `unheld-entry-real32`의 고정 results/preregistration SHA 및 개별 artifact SHA. explore와 plan 완료
- 수정 허용 범위: 새 `research_entry_attribution.py`, 해당 테스트, `docs/research-entry-attribution.md`만 수정합니다. 전략·엔진·PAPER·API·UI는 변경하지 않습니다.
- 포트·테스트 DB·출력 경로: 서버·DB 없음. 전용 `.venv`와 `validation/` 사용, 기존 입력은 읽기 전용
- 검증 방법: 종목·월 합계와 기존 지표의 일치, split 현금정산·비용·UTC 경계·변조·누락·중복·불완전 입력 테스트, 실제 32개/16쌍 분석, 결정성 비교, Ruff·mypy·독립 review·main 통합 검증
- 보존 증거: `20260911T185925Z-entry-attribution/before.json`
- 결과 커밋: `603d50f61182b939c1d23d1083b135748c285d26`
- 병합 직전 main: `ff607a7`; 코드 통합 `e893698`, 최종 코드 상태 `d59a095a1d5d54421868865f0cb09b4321c880ef`
- 이력 보존: 작업자가 최초 리뷰 커밋 `6040b37`을 amend한 사실을 확인했습니다. 감독은 최종 검토 트리를 유지하면서 최초 스냅샷도 추가 병합의 조상으로 보존했고 이후 수정은 새 커밋으로 남기도록 재지시했습니다. 최종 트리는 검토한 `603d50f`와 동일합니다.
- 검증 결과: 신규 12개·관련 41개 테스트, 독립 리뷰 통과. main 전체 pytest 510개(기존 경고 2개), Ruff check/format 112개 파일, mypy 72개 소스 통과. UI 미변경으로 빌드는 미실행
- 실제 결과: 32개 artifact / 16쌍 / 종목 222행 / 월 126행. 별도 계산과 손익 값 1,044개가 정확히 일치하고 최대 회계 잔차는 `2.4375E-31 KRW`. 전용 두 실행 및 main 재실행의 산출물 4개가 동일
- 해석: 체결 금액에는 슬리피지가 반영돼 있으므로 수수료와 FX 비용만 현금흐름에서 차감합니다. 내재 슬리피지는 별도 표시합니다. 회계 귀속을 추가 매매의 인과적 이익이나 MDD 원인으로 해석하지 않습니다.
- 웹: `/research/history`의 `entry-attribution-20260912`. 판단·상세 보고서·종목/월 전체 CSV·검증 보고서 5개, API/웹 다운로드 10개 SHA와 화면 제목 확인. 이전 51개 이력과 78개 artifact 보존
- 보존: 고정 파일 19개·원장 9개 테이블·계약 mtime·GPU 프로세스 상태 일치. 운영 전략과 PAPER 계약 미변경
- 산출물·정리: 워크트리 `validation/real-run-13`, `real-run-14` 및 영구 audit `20260911T185925Z-entry-attribution/verified-analysis`, `main-analysis`. 독립 환경과 재현 자료를 위해 워크트리를 보존하며 미커밋 소스·작업 서버는 없음
- handoff: 기준 저장소 `HANDOFF.md` 최신 기여 분석 절 갱신. 이번 범위에서 원격 push·PR은 수행하지 않음

## 이전 완료 작업

## experiment-guard

- 상태: 완료
- 목표와 완료 조건: 실험 엔진의 허용된 단일 변경과 대조군 전체 JSON 일치를 검증하는 읽기 전용 helper를 구현하고 독립 검토 및 main 통합 검증을 통과합니다.
- 담당 Luna: `/root/work_guard`
- 워크트리 절대 경로: `/home/kwl/projects/jusik-experiment-guard`
- 작업 브랜치: `feat/experiment-guard`
- 기준 커밋 SHA: `e663641`
- 통합 대상 브랜치: 로컬 `main`
- 입력과 선행 작업: `20260911T060908Z-rebalance-band/next-hypothesis.md`, 조사 및 계획 완료
- 수정 허용 범위: `backend/jusik/research_experiment_guard.py`, 해당 테스트, `docs/research-experiment-guard.md`
- 포트·테스트 DB·출력 경로: 서버와 DB 없음. 전용 워크트리 `.venv` 및 pytest 임시 경로 사용
- 검증 명령과 결과: focused pytest 9개, Ruff check/format, mypy 통과. 독립 review의 두 P2 수정 후 재검토 통과. main 병합 후 같은 검사 통과
- 보존 기준: 운영 엔진·원장·평가 계약·GPU 서비스 미변경. 시작 증거는 `20260911T132132Z-worktree-development/before.json`
- 결과 커밋 SHA: `41e3bbbac8f573a840d53d366cdef543af277792`
- 병합 직전 main SHA: `e663641`
- 통합 커밋 SHA: `8e421e55f2648455f6325b87738c48e12ceb0b79`
- 통합 보존 검사: 고정 파일 19개, 원장 9개 테이블, 계약 mtime, GPU PID·재시작 상태 일치
- 워크트리: 후속 검토에서 독립 가상환경과 구현 이력을 재현하기 위해 보존. 미커밋 소스와 작업 서버 없음
- handoff: 기준 저장소 `HANDOFF.md`의 워크트리 개발 절

## unheld-entry-experiment

- 상태: 완료
- 담당 Luna: `/root/work_unheld`
- 워크트리 절대 경로: `/home/kwl/projects/jusik-unheld-entry-experiment`
- 작업 브랜치: `feat/unheld-entry-experiment`
- 기준 커밋: `ad06daa`
- 통합 대상: 로컬 `main`
- 목표와 완료 조건: 미보유 진입만 2%p 밴드 예외로 처리한 격리 엔진을 32회 비교하고 대조군 16개 전체 결과 일치, 경계 fixture 및 웹 보고서를 검증합니다.
- 입력과 선행 작업: experiment-guard의 첫 운영 검증과 통합 완료. 이전 rebalance-band audit의 고정 입력·대조군·사전 판정식 사용
- 수정 허용 범위: 새 실험 runner, 테스트, 별도 문서와 격리 산출물. 운영 엔진·기존 모델·PAPER 경로는 변경하지 않습니다.
- 포트·테스트 DB·출력 경로: 서버·DB 없음. 전용 `.venv` 및 워크트리 `validation/`, 공유 입력은 읽기 전용
- 검증: 행동·지표 fixture, 32회 비교, 대조군 16개 전체 일치, Ruff·mypy·독립 review·main 통합 검사, 웹 history 산출물 해시 확인
- 종료 조건: 결과를 성공 여부와 무관하게 공개하고 등록부·handoff와 운영 보존 증거를 갱신합니다.
- 결과 커밋: `eb9c0eed84b3657eb1a79af62b5d134457139205`
- 병합 직전 main: `ad06daa`
- 통합 커밋: `78045f84027243390728ef8c796a31f480d43e2b`
- 검증 결과: 신규 10개·기존 포트폴리오 19개 테스트 통과, 독립 리뷰 수정 및 재검토 통과. main 전체 pytest 498개(기존 경고 2개), Ruff check/format 110개 파일, mypy 71개 소스 통과. UI 미변경으로 프런트엔드 빌드는 미실행
- 실험 결과: 32/32 완료, 대조군 16개 전체 JSON 일치. 비용 1배 연속 수익률 16.3268% / 27.8639%, MDD 7.3744% / 7.2249%(대조군 / 변형군). 체결 171 / 308건이며 첫 fold 악화도 공개. 두 비용 조건의 사전 관심 기준 충족은 후향 연구 결과이고 PAPER 승격이 아님
- 웹: `/research/history`의 `unheld-entry-20260911`. 요약·전체 수치·16쌍 비교·검증 보고서 4개를 게시하고 API/웹 다운로드 8개 해시 및 화면 제목 확인. 첫 작업 이력과 모든 이전 이력 보존
- 보존 검증: 고정 파일 19개·원장 9개 테이블·계약 mtime·GPU 서비스 상태 일치. 통합 코드와 실험 runner/helper hash 일치
- 산출물: 워크트리 `validation/real32` 및 영구 audit `20260911T132132Z-worktree-development/unheld-entry-real32`. 최초 `/tmp/jusik-unheld-real32`도 삭제하지 않음
- 워크트리: 독립 가상환경과 실험 재현 자료를 위해 보존. 미커밋 소스와 작업 서버 없음. 원격 push·PR은 이번 범위에서 수행하지 않음
- handoff: 기준 저장소 `HANDOFF.md`의 워크트리 개발 절 갱신

## 첫 운영 검증

`experiment-guard`에서 완료했습니다. 운영 문서와 등록부를 기준 커밋에 포함했고, Luna가 전용 폴더·브랜치·가상환경에서 구현했습니다. 독립 검토, Astra의 로컬 main 병합, 통합 검사와 운영 상태 보존 검사를 통과했으며 handoff를 기록했습니다. 서버·DB·포트는 사용하지 않았습니다.

## runner-git-access

- 상태: 완료
- 목표와 완료 조건: 자동 실행기의 Git 메타데이터 쓰기를 명시적으로 허용하고 실제 Codex의 워크트리 생성·커밋·main 병합·정리 및 보호 경로 차단을 검증한 뒤 기존 작업을 재개합니다.
- 담당 Luna: 별도 Codex CLI `gpt-5.6-luna` (내장 agent의 세션 한도로 대체)
- 워크트리 절대 경로: `/home/kwl/projects/jusik-runner-git-access`
- 작업 브랜치: `fix/runner-git-access`
- 기준 커밋 SHA: `8268a2d`
- 통합 대상 브랜치: 로컬 `main`
- 입력과 선행 작업: 조사·계획 완료. 실제 Codex named permissions profile 쓰기 시험 통과
- 수정 허용 범위: development_runner.py, 관련 테스트, docs/development-runner.md
- 포트·테스트 DB·출력 경로: 전용 venv와 validation. 운영 runner는 pause 상태. 영구 audit `20260911T234908Z-runner-git-access/`
- 검증 명령과 결과: runner 22개, main 전체 pytest 532개(기존 경고 2개), Ruff check/format 115개 파일, strict mypy 74개 소스 통과. 실제 Codex exec 및 통합 helper 설정의 Git lifecycle·보호 경로·artifact 쓰기 검증 통과
- 검토 결과와 남은 문제: 독립 검토의 artifact 경로·기존 권한·테스트 격리 지적 수정 후 재검토 통과. 사용자 설정·quota·기존 산출물·PAPER·GPU 보존. 전용 환경의 선택 PyTorch 미설치로 최초 전체 검사 12개 실패, 최종 main 전체 검사 통과
- 결과 커밋 SHA: `9e0fcb1`, `21a9856`, `f6ba0aa`
- 병합 직전 main SHA: `e054390`
- 통합 커밋 SHA와 정리 여부: `58f5443a8f43428a717b707bb80cbb667db44706`. 검증 로그·환경 버전 보존 및 해시 확인 후 워크트리 제거 완료. 브랜치 보존
- 웹: `/research/history`의 `runner-git-access-20260912`. 기존 seed 52개·artifact 83개 보존, API/웹 다운로드 SHA와 제목 확인
- handoff 저장 경로와 갱신 여부: 기준 저장소 HANDOFF.md 복구 절과 영구 audit activation.json에서 재개 상태 확인


## future-observation-protocol-v1-63c4

- 상태: 완료
- 목표와 완료 조건: 후향 자료와 분리된 미래 관측 설계를 문서화하고 미확보 자료를 구분합니다. 독립 검토, 로컬 main 통합, 검사와 영구 handoff를 완료합니다.
- 담당 Luna: /root/protocol_luna (gpt-5.6-luna)
- 워크트리 절대 경로: /home/kwl/projects/jusik-future-observation-63c4
- 작업 브랜치: docs/future-observation-63c4
- 기준 커밋 SHA: a6863b756e24e0d3549b46f0453583e60070a5d0
- 통합 대상 브랜치: local main
- 입력과 선행 작업: explore·plan 완료, 이전 시도 protocol-draft.md 및 현재 prospective/boundary 코드
- 수정 허용 범위: docs/research-future-observation-protocol.md, docs/research.md의 링크
- 포트·테스트 DB·출력 경로: 서버·운영 DB 사용 없음. 검사는 격리 임시 경로 사용
- 검증 명령과 결과: main 문서 링크·계약 일치·git diff --check·변경 범위·보존 해시 통과. prospective/boundary pytest 40개 통과(기존 경고 2개), Ruff check/format 8개 파일, strict mypy 4개 소스 통과. 문서 변경으로 frontend build 비적용
- 결과 커밋 SHA: d80abd9c8d8bdc0bfb1733891967f5675d18432b
- 검토 결과와 남은 문제: 독립 review 초기 지적 수정 후 최종 통과. 미래 관측·운영 등록·성과 검증은 완료되지 않았으며 설계 범위 밖
- 병합 직전 main SHA: a6863b756e24e0d3549b46f0453583e60070a5d0
- 통합 커밋 SHA와 정리 여부: 69894b0e89b227ae24aa1a15fb0b30c234d7f514. 영구 audit에 증거 16개·SHA-256·handoff 보존 및 해시 확인 후 clean 워크트리 제거 완료. 브랜치 보존
- 통합 검증 실패 원인과 복구 결과: 해당 없음
- handoff 저장 경로와 갱신 여부: /home/kwl/.local/share/jusik/portfolio-audit/future-observation-protocol-v1-63c4e3f2380b4e149d60d17db90459c7/handoff.md 저장 완료
- 웹: runner completion/outbox를 통한 상태 기록 대상. 직접 게시·history 변경은 하지 않았습니다. 기존 미추적 HANDOFF.md를 보존했습니다.


## paper-signal-evidence-v1-722b

- 상태: 완료
- 목표와 완료 조건: 저장된 실시간 PAPER 시세 근거를 읽기 전용 수집하고 출처·제한을 문서화합니다. 독립 검토, main 통합, 검사, 영구 근거와 handoff 보존을 완료합니다.
- 담당 Luna: paper_luna (gpt-5.6-luna), 문서 단일 소유자
- 워크트리 절대 경로: /home/kwl/projects/jusik-paper-signal-722b
- 작업 브랜치: docs/paper-signal-722b
- 기준 커밋 SHA: 0676b70 (작업 등록 준비 커밋)
- 통합 대상 브랜치: local main
- 입력과 선행 작업: explore·plan 순차 완료. 이전 시도 collector와 기존 research_signal_validation 재사용
- 수정 허용 범위: docs/research/paper-signal-evidence-v1.md (Luna); 등록부·영구 audit 수집·검증·handoff (Astra)
- 포트·테스트 DB·출력 경로: 서버 없음. 테스트는 임시 DB, 수집은 audit/private 복사본만 사용
- 영구 산출물: /home/kwl/.local/share/jusik/portfolio-audit/paper-signal-evidence-v1-722bb6f1d10a42318b502092d64dac39
- 검증 계획: snapshot integrity와 재분석 일치, validation/kis_stream pytest, Ruff check/format, strict mypy, 문서 독립 review와 main 통합 재검사
- 중단 조건: 원본 수집 중 변경·무결성 실패·해시 불일치. 운영 DB·engine·broker·주문·GPU·remote 변경 금지

- 결과 커밋 SHA: 4f0542f (Luna)
- 병합 직전 main SHA: 0676b70
- 통합 커밋 SHA: e9d7b5da40218a36a84fd6e7552cfc88f7dc7c1a
- 검토 결과: 독립 snapshot 재분석·별도 집계 일치. 문서 경로·환경 설명 수정 후 독립 검토 통과
- 검증 결과: 통합 전후 pytest 29개 통과(기존 경고 2개), Ruff check/format 4파일, strict mypy 2소스 통과. 문서 hash 일치·diff check·baseline 보존 확인. frontend build 해당 없음
- 관측 결과: 저장 관찰 21,937건, 판단·체결 0건. 선택일 2026-09-11의 6,240분 중 6,164분 관측, 미래 시각 이상 249건. current_feed=null, operational_unproven 유지
- 정리: 필요한 근거 99파일과 SHA-256·handoff를 영구 audit에 먼저 보존·검증했다. clean worktree 제거 완료, 브랜치 보존. 최종 보존 목록은 manifest.json 참조
- 통합 검증 실패 원인과 복구 결과: 해당 없음
- handoff 저장 경로: /home/kwl/.local/share/jusik/portfolio-audit/paper-signal-evidence-v1-722bb6f1d10a42318b502092d64dac39/handoff.md
- 웹: runner completion/outbox의 상태 기록 대상이며 직접 게시하지 않았다. 기존 미추적 HANDOFF.md 보존


## portfolio-stress-e16e

- 상태: 차단 (오프라인 검토·문서 통합 완료, 미래 성과 미확보)
- 목표와 완료 조건: 고정 오프라인 스트레스 재계산과 문서 검토·main 통합·검사·영구 handoff. 미래 성과는 자료 부족으로 차단합니다.
- 담당 Luna: stress_luna (gpt-5.6-luna), 문서 단일 소유자
- 워크트리 절대 경로: /home/kwl/projects/jusik-portfolio-stress-e16e
- 작업 브랜치: docs/portfolio-stress-e16e
- 기준 커밋 SHA: 29c5327768e298a284171cce8ec933e1a274ed29 (등록 준비 전 main; 실제 기준은 준비 커밋)
- 통합 대상 브랜치: local main
- 입력과 선행 작업: explore 조사와 bounded plan 완료. 기존 고정 baseline과 robustness CLI
- 수정 허용 범위: docs/research/portfolio-stress-robustness-v1.md (Luna); 등록부·audit·검사 (Astra)
- 포트·테스트 DB·출력 경로: 서버 없음, 테스트는 임시 DB. 영구 audit /home/kwl/.local/share/jusik/portfolio-audit/portfolio-stress-robustness-v1-e16e783562a544cf8fdef38180db34b0
- 검증 계획: 고정 SHA, 7 folds/147회 평가, 시간 분리, 관련 pytest·Ruff·strict mypy·독립 review
- 중단 조건: 고정 입력 hash 불일치 또는 계산 실패. 엔진·PAPER·주문·remote·GPU 변경 금지

- 결과 커밋 SHA: c52b08d65aa4fda62793b23da3f64f4300c2419e
- 병합 직전 main SHA: a7e18e71d5cd305d0c73e93d978e6c6772dd3834
- 통합 커밋 SHA: a63ef98b8fd46d09a3a5f3e13dc29db0a3fff54c
- 검토 결과: 독립 검토 통과. source/code/spec/산출물 해시, 9개 요약 수치, fold 시간 분리, 이전 결과 일치 검증. 재현 경로와 미래 평가 표현 수정
- 검증 결과: 통합 전후 pytest 31개 통과(기존 경고 2개), Ruff check/format 및 strict mypy 통과. diff check·문서 hash·기존 HANDOFF와 엔진 보존 확인. frontend build 비적용
- 연구 결과: 7/7 folds, 147회 평가, 774 union dates. 생성 시각 외 이전 결과 일치. 2026-09-12 기준 미래 평가 기간이 아직 시작되지 않아 성과 검증 차단
- 정리: 필요한 근거·SHA-256·handoff 26파일을 영구 audit에 보존하고 검증한 후 clean merged worktree 제거 완료. 브랜치 보존
- 통합 검증 실패 원인과 복구 결과: 해당 없음
- handoff 저장 경로: /home/kwl/.local/share/jusik/portfolio-audit/portfolio-stress-robustness-v1-e16e783562a544cf8fdef38180db34b0/handoff.md
- 웹: runner completion/outbox 상태 기록 대상. 직접 게시·PAPER DB 변경 없음. 기존 미추적 HANDOFF.md 보존


## paper-signal-timestamp-forensics-a77e

- 상태: 완료
- 목표와 완료 조건: 동결 snapshot의 6,164개 정규장 표본과 미래 시각 이상 249건을 재현하는 오프라인 CLI, 전체 anomaly CSV, 그룹별 요약, 경계 테스트와 한국어 문서를 구현합니다. 독립 검토, local main 통합 검사, 웹 보고서와 영구 근거 보존 후 종료합니다.
- 담당 Luna: timestamp_luna (gpt-5.6-luna), 신규 모듈·테스트·문서 단일 구현 소유자
- 워크트리 절대 경로: /home/kwl/projects/jusik-signal-timestamp-a77e
- 작업 브랜치: feat/signal-timestamp-a77e
- 기준 커밋 SHA: fa127374e6e3ee351fedb514ffb0db1769615437 (등록 전 main; 실제 worktree 기준은 이 등록의 준비 커밋)
- 통합 대상 브랜치: local main
- 입력과 선행 작업: explore 독립 재계산 완료, plan 순차 검토. paper-signal-evidence-v1-722bb6f1d10a42318b502092d64dac39의 snapshot/provenance/validation만 읽기 전용 입력으로 사용합니다.
- 수정 허용 범위: backend/jusik/research_signal_timestamp_forensics.py, backend/tests/test_research_signal_timestamp_forensics.py, docs/research/paper-signal-timestamp-forensics-v1.md (Luna); 등록부·audit·웹 seed·handoff (Astra)
- 포트·테스트 DB·출력 경로: 신규 서버 없음. worktree 내부 .venv와 .artifacts, pytest tmp 경로를 격리합니다. 운영 DB에 연결하지 않습니다.
- 영구 산출물: /home/kwl/.local/share/jusik/portfolio-audit/paper-signal-timestamp-forensics-v1-a77ec18fbf634b3694afa8da08ef11c6
- 검증 명령과 결과: 새 pytest 및 research_validation 회귀, Ruff check/format, strict mypy, 두 번 frozen replay의 바이트 일치와 입력 SHA 보존, 독립 review, main 통합 후 동일 검사 예정
- 중단 조건: 입력 hash 불일치 또는 구현 범위 밖 변경 필요. 미래 데이터는 본 오프라인 도구 완료의 조건이 아닙니다. PAPER·collector·order·parser·clockmonitor·GPU·runner·quota·remote를 변경하지 않습니다.
- 결과 커밋 SHA: 92527281cdadd5101478987d233db5b5931ec909, ab56a15d80bdc02772a13460c2d1c0588ac99e26
- 병합 직전 main SHA: a6610f047b0c460a61cef0cd7cee9794dd4013f6
- 통합 커밋 SHA: 3f1a0f59edc9643210647e14fc6090918a1bfded
- 검토 결과: Terra 독립 검토 통과. 정확한 -2s-1µs fixture와 URI 인코딩 지적을 회귀 테스트와 함께 수정했습니다.
- 통합 검증 결과: pytest 20개(기존 Starlette/AnyIO 경고 2개), Ruff check/format, 프로젝트 설정 strict mypy 2파일, git diff 검사 통과. 두 main 재생 3출력 바이트 일치, 249개 ID/시각/정확한 지연 및 전 종목 latency/coverage와 독립 집계 일치. frontend build 비적용.
- 결과: 6,164개 정규장 저장 분 표본, future 249건, stale 0건, median -130ms/p95 668ms/max 4939ms. 원 snapshot 및 기존 소스·HANDOFF 해시를 유지했습니다. 원인은 확정하지 않았습니다.
- 웹: /research/history에 한국어 보고서·checks 게시 완료. API/웹 4개 첨부 다운로드 SHA와 페이지 제목 확인. 기존 seed의 54개 이력·89개 첨부를 보존했습니다.
- 정리: evidence·SHA-256·환경·handoff 등 105개 파일을 영구 audit에 보존·검증한 뒤 생성물을 정리하고 git worktree remove로 병합 worktree 제거 완료. 브랜치 보존.
- 통합 검증 실패 원인과 복구 결과: 통합 검사 실패 없음. 사전 감독 mypy의 잘못된 cwd를 backend로 바꾸어 프로젝트 Pydantic plugin 및 strict 설정 적용 후 통과했습니다.
- handoff 저장 경로: /home/kwl/.local/share/jusik/portfolio-audit/paper-signal-timestamp-forensics-v1-a77ec18fbf634b3694afa8da08ef11c6/handoff.md. 기존 루트 미추적 HANDOFF.md는 그대로 보존했습니다.
- 후속 후보: 독립 근거의 68개 다중 종목 이상 분을 이용한 오프라인 동시 발생/연속 episode 분석 1개. 범위·입력·테스트·종료 조건은 영구 followup.json에 기록했습니다.


## small-entry-draft-a55b

- 상태: 완료
- 목표와 완료 조건: 신규 소액 진입 사전등록 초안 명세·검증기·테스트를 만들고 독립 검토, local main 통합 검사, 한국어 웹 게시와 영구 근거 보존을 완료합니다. 금융 승인이나 정책 실행은 포함하지 않습니다.
- 담당 Luna: draft_luna (gpt-5.6-luna), 신규 세 파일 단일 구현 소유자. 초기 작업자는 파일 수정 전에 중단했습니다.
- 워크트리 절대 경로: /home/kwl/projects/jusik-small-entry-draft-a55b
- 작업 브랜치: feat/small-entry-draft-a55b
- 기준 커밋 SHA: 8882bd8287759edc047adc296da129cded8950dc (등록 전 main; 생성 기준은 준비 커밋)
- 통합 대상 브랜치: local main
- 입력과 선행 작업: explore 완료, 순차 bounded plan. 완료 entry amount 분석과 original unheld-band는 역사 맥락으로만 사용합니다. 과거 blocked 작업은 보존합니다.
- 수정 허용 범위: backend/jusik/research_small_entry_preregistration.py, backend/tests/test_research_small_entry_preregistration.py, docs/research/small-entry-preregistration-draft-v1.md. Astra는 등록부·audit·공개 history·handoff를 담당합니다.
- 포트·테스트 DB·출력 경로: 서버/DB 없음. worktree 내부 .venv, .artifacts, tmp 경로 격리.
- 영구 산출물: /home/kwl/.local/share/jusik/portfolio-audit/small-entry-preregistration-draft-v1-a55b6ee8a036463da688fafe04567542
- 검증 방법: threshold/time/period/hash 경계, canonical roundtrip와 별도 identity, populated draft 불변성, pytest·Ruff·strict mypy·독립 review·main 재검사.
- 중단 조건: 세 파일 도구 완료. 임계값 탐색·정책 실행·PAPER 코드/config/DB·collector/order/GPU·runner/quota·remote 변경 금지. 미래 자료 부재는 도구 완료를 막지 않습니다.

- 결과 커밋 SHA: 0f8e1c674bc1535ee80caf500973b143123551e8, 92f3648481a8822a603eedcc82a1213c00d33452
- 병합 직전 main SHA: 03cdafd4b476c55430093d3dad2a6f453e286d80
- 통합 커밋 SHA: 4bd8a85e2d3c482fddaca47a85fe8d64c51d65ad
- 검토 결과: 독립 검토 통과. 추가 금액 계산 helper의 Decimal context 반올림 지적을 helper 제거로 해결하고 위조 상태·중첩 위험 한도의 출력 거부 회귀를 추가했습니다.
- 통합 검증 결과: 신규19개 및 기존 금액 분석6개 pytest 합계25개, Ruff check/format, 설정된 strict mypy 신규 소스·테스트2파일, diff 검사 통과. 기본·합성 완전 입력 반복 canonical 출력/roundtrip/낮은 Decimal context 바이트와 SHA 일치.
- 검사 제한: 전체 backend mypy의 torch 타입 정보 누락·기존 테스트 모듈 중복2오류를 변경 전 main에서도 재현했습니다. frontend build 비적용. 엔진·실험 정책 실행 테스트는 범위에서 제외했습니다.
- 결과: 기본4개 결정은 null, 모든 입력이 있어도 draft 및 활성화 금지. canonical draft SHA 71691f864ccc0e61e351b52298027e6df4e8c864ab9c15f16ae0887bbfe35dbb. PAPER10% 계약과 기존 코드/config/HANDOFF·역사 입력 SHA 보존.
- 웹: /research/history 한국어 보고서·검사 요약 게시 완료. API/웹 제목과4개 첨부 다운로드 SHA 및 기존 seed 이력 보존 확인.
- 정리: 근거62파일·환경·SHA·handoff를 영구 audit에 먼저 보존·검증한 뒤 작업 생성물과 병합 worktree를 git worktree remove로 제거했습니다. 브랜치는 보존했습니다. 최종 manifest.json에 정리 후 추가 기록까지 포함합니다.
- 통합 검증 실패 원인과 복구 결과: 통합 검사 실패 없음.
- handoff 저장 경로: /home/kwl/.local/share/jusik/portfolio-audit/small-entry-preregistration-draft-v1-a55b6ee8a036463da688fafe04567542/handoff.md. 기존 root HANDOFF.md 보존.
- 후속 후보: 초안의 선언 SHA와 실제 보관 출처를 검증하는 신규 오프라인 provenance bundle verifier1개. exact scope/input/tests/stop은 영구 followup.json 참조. 미래 자료·금융 승인 불필요.


## future-observation-replay-0bb3

- 상태: 완료
- 목표와 완료 조건: 합성 fixture 전용 순수 관측 분류기와 오프라인 CLI를 구현하고 독립 기대값·pytest·검토·main 통합·웹 보고 및 영구 증거 보존을 완료합니다.
- 담당 Luna: replay_luna (gpt-5.6-luna), 신규 세 파일 단일 구현 소유자
- 워크트리 절대 경로: /home/kwl/projects/jusik-future-observation-replay-0bb3
- 작업 브랜치: feat/future-observation-replay-0bb3
- 기준 커밋 SHA: de52818e3ec249ef1bd9e42e80ad2304befa1eb1 (등록 전 main; 생성 기준은 준비 커밋)
- 통합 대상 브랜치: local main
- 입력과 선행 작업: 기존 미래 관측 초안, readiness/receipt seam 읽기 전용 조사 완료. 순차 bounded plan과 독립 합성 기대값을 사용합니다.
- 수정 허용 범위: backend/jusik/research_future_observation_replay.py, backend/tests/test_research_future_observation_replay.py, docs/research/future-observation-protocol-replay-v1.md. Astra는 등록부·audit·공개 history·handoff 담당.
- 포트·테스트 DB·출력 경로: 서버/DB 없음. worktree 내부 .venv, .artifacts, tmp와 cache 격리.
- 영구 산출물: /home/kwl/.local/share/jusik/portfolio-audit/future-observation-protocol-replay-v1-0bb3f02db53540c9b6da3e631c76aa9b
- 검증 방법: UTC 반열린 구간, 최초 receipt 불변, 중복·충돌·late, not_due/missing, clock/truncation, 미정 우선순위 보존, 고정 synthetic 불변성. pytest·Ruff·strict mypy·독립 review와 main 재검사.
- 중단 조건: 결정론적 합성 replay 도구까지. 미래 데이터 부재는 blocker가 아닙니다. PAPER 코드/config/contracts/DB·collector·order·GPU·runner/quota·remote 변경 금지.

- 구현 커밋: af61404, 23a425b, 8ad7113, 0bcf2cc, 420d04a, 2f5fecc. 독립 검토에서 미래 receipt 소급·시계 오류 건수·CLI alias 회귀를 발견해 동일 Luna가 수정했습니다.
- 감독 독립 검증: 10 receipt/8 identity fixture, 수신 전후 conflict/provenance/clock 3개 비교 통과. 최종 독립 검토와 main 통합 검사 후 완료 처리합니다.

- 최종 구현 커밋: 2f5fecc (수정 이력 포함). 독립 최종 검토 PASS, 중요 미해결 지적 없음.
- 병합 직전 main SHA: 6f320bd5e40bef99bb7da03e8996e590239744d6
- 통합 커밋 SHA: d83d47f2d289368f1719aff9ed516143cb35b091
- 통합 검증 결과: pytest 49개(신규20, readiness/receipt29), Ruff check/format, 신규 두 파일 strict mypy, diff 통과. 기존 deprecation 경고2개. frontend build 비적용, 전체 backend 타입 검사 미실행.
- 독립 결과: 10 receipt/8 identity 기대값, 두 CLI 출력 바이트, 미래 conflict/provenance/clock의 수신 전후3쌍 비교 통과. 모든 결과 synthetic, registered/accepted_nav/evaluation_inputs_complete=false.
- 웹: /research/history 한국어 보고서·checks 게시 완료. API·웹 제목과4개 첨부 다운로드 SHA, 기존 공개 seed 보존 확인.
- 보존: 기존 tracked 파일은 등록부 외 모두 동일하며 기존 미추적 HANDOFF.md 보존. 비ASCII 경로2개는 원래 기준 커밋 bytes와 추가 비교. 운영 DB·PAPER·collector·order·GPU·runner/quota·remote 변경 없음.
- 정리: 증거·SHA·환경·handoff82파일을 영구 audit에 보관·검증한 뒤 생성물을 제거하고 git worktree remove로 병합 worktree 정리 완료. 브랜치 보존.
- 통합 검증 실패 원인과 복구 결과: 코드 통합 검사 실패 없음. 감독 보존 검사에서 Git 경로 인용으로 비ASCII2파일이 새 파일로 오인되어 -z 경로 읽기와 기준 blob 비교로 검사 도구를 수정하고 통과했습니다.
- handoff 저장 경로: /home/kwl/.local/share/jusik/portfolio-audit/future-observation-protocol-replay-v1-0bb3f02db53540c9b6da3e631c76aa9b/handoff.md
- 후속 후보: 합성 revision-link 구조 감사1개. 프로토콜의 이전 revision·effective 시각 연결 규칙과 현재 replay의 충돌 보존 범위를 근거로 합니다. 범위·입력·테스트·종료 조건은 영구 followup.json에 기록했습니다.

## runner-daily-limit

- 상태: 완료
- 목표와 완료 조건: 기존 실행 이력을 보존하며 일일 설정 상한을 24회까지 지원하고 설치 설정을 24회로 조정해 대기 연구를 재개합니다.
- 담당 Luna: 별도 Codex CLI gpt-5.6-luna
- 워크트리 절대 경로: /home/kwl/projects/jusik-runner-daily-limit
- 작업 브랜치: fix/runner-daily-limit
- 기준 커밋 SHA: 8d9333f
- 통합 대상 브랜치: 로컬 main
- 입력과 선행 작업: UTC 실행 8회/설정8로 quota 대기 확인; 후속3개 queued, timer 정상
- 수정 허용 범위: development_runner.py, 해당 tests, docs/development-runner.md
- 포트·테스트 DB·출력 경로: 전용 venv/임시DB, 영구 audit /home/kwl/.local/share/jusik/portfolio-audit/20260912T061307Z-runner-daily-limit
- 검증 명령과 결과: worker/main focused pytest 28개, Ruff check/format, strict mypy 통과. 독립 review P1/P2 없음
- 보존·종료: store/실행이력/90분제한/cooldown/PAPER/GPU 유지, main 검증 후 archive·worktree 정리·handoff·웹 게시
- 결과 커밋: ffdd7e3fb76a4120f5e05a988f0f2083089b7309
- 통합 커밋: ebc42b29c32734e86bbb71cdc0389171ea5166b1
- 정리: 로그·환경·해시 archive 후 worktree 제거, 브랜치 보존
- 설치: daily_launches 8에서24 변경, 나머지 설정과 과거 launch 행 전체 보존
- 재개·웹·handoff: HANDOFF.md 최신 절 및 audit activation.json 참조

## signal-anomaly-episodes-21ce

- 상태: 완료
- 목표와 완료 조건: 동결 신호의 분별 동시 이상/episodes utility, matching pytest, 한국어 보고서; 249 IDs, 68분, 최대5종목, 65 episodes 및 독립 분모/종목쌍 집계 일치
- 담당 Luna: gpt-5.6-luna 단일 구현 작업자; Astra 감독과 별도 독립 검토
- 워크트리 절대 경로: /home/kwl/projects/jusik-signal-anomaly-episodes-21ce (통합 검사 및 증거 보관 후 제거 완료)
- 작업 브랜치: feat/signal-anomaly-episodes-21ce (보존)
- 기준 커밋 SHA 및 병합 직전 main: 1876d8eb11ac7747dba3a08e90eb0a4486d81ac8
- 통합 대상 브랜치: 로컬 main
- 입력과 선행 작업: 지정 evidence/timestamp archive manifest 전체 검증; explore/plan 완료; offline immutable snapshot만 재선택
- 수정 허용 범위와 결과: backend/jusik/research_signal_anomaly_episodes.py, backend/tests/test_research_signal_anomaly_episodes.py, docs/research/paper-signal-coincident-anomaly-episodes-v1.md
- 포트·테스트 DB·출력 경로: 작업 전용 venv/pytest tmp; 영구 audit /home/kwl/.local/share/jusik/portfolio-audit/paper-signal-coincident-anomaly-episodes-v1-21ce4592e34a4ee78332f2dbff95f994
- 검증 명령과 결과: main pytest 44개, Ruff check/format, strict mypy utility/tests, git diff 통과. 780분 grid·770개 관측 분·6,164행·249 IDs·68분·max5·65 episodes, 독립 observed/active 분모·종목 집합·종목쌍·에피소드 및 반복 출력 바이트 일치
- 결과 커밋 SHA: edc09685cbd6640cbddf8d96bc49500d374d9e4d
- 검토 결과와 남은 문제: 초기 분모/session/manifest/output 보호 누락 수정 후 독립 승인; 중요 잔여 문제 없음. 기존 dependency deprecation warning 2건, frontend 변경 없어 build 해당 없음
- 통합 커밋 SHA: b407810d3822db866dc44d4bd061224d68fe48b3
- 정리 여부: source·환경·로그·SHA·handoff 55파일을 durable archive에 검증·보관한 뒤 git worktree remove 완료. 기존 HANDOFF.md 보존
- 통합 검증 실패 원인과 복구 결과: 통합 실패 없음. worker mypy는 처음 root cwd에서 backend 설정 미적용으로 실패했으나 올바른 cwd에서 통과
- 웹 게시: /research/history sanitized 한국어 보고서와 검사 근거, API/web/download 4개 SHA 검증 및 기존 공개 항목 보존
- 보존: 원본 archive와 기존 handoff 213개 hash, 등록부 외 기존 tracked 196개 파일 불변. 운영 PAPER/DB/orders/GPU/runner/quota·remote 변경 없음
- handoff 저장 경로: /home/kwl/.local/share/jusik/portfolio-audit/paper-signal-coincident-anomaly-episodes-v1-21ce4592e34a4ee78332f2dbff95f994/handoff.md

## small-entry-draft-provenance-4840

- 상태: 완료
- 목표와 완료 조건: 오프라인 bundle의 실제 SHA·canonical SHA·별도 identity·역사 재사용 계약 검증, 결정적인 공개 manifest/보고서, 독립 검토·main 검사·연구 이력 게시.
- 담당 Luna: gpt-5.6-luna 단일 구현 작업자
- 워크트리 절대 경로: /home/kwl/projects/jusik-small-entry-draft-provenance-4840
- 작업 브랜치: feat/small-entry-draft-provenance-4840
- 기준 커밋 SHA: 7c7bee5591affc5a5d2d9ead53a6f5e8e6a14c48; 작업 등록부 준비 커밋을 실제 작업 기준으로 사용한다.
- 통합 대상 브랜치: 로컬 main
- 입력과 선행 작업: 지정된 small-entry-preregistration-draft-v1 archive의 네 파일 읽기 전용; explore/plan 완료.
- 수정 허용 범위: backend/jusik/research_small_entry_draft_provenance.py, 대응 tests, docs/research/small-entry-draft-provenance-audit-v1.md
- 포트·테스트 DB·출력 경로: 서버·DB 없음. 작업 내부 venv/tmp. 영구 audit /home/kwl/.local/share/jusik/portfolio-audit/small-entry-draft-provenance-audit-v1-484028675d0647a0a0b47f86c46a5ca5
- 검증 명령과 결과: 후보 pytest 41개, main 통합 관련 pytest 41개, Ruff check/format, strict mypy, `git diff --check`, 고정 archive CLI replay와 반복 출력 SHA 대조가 모두 통과했습니다. 실제 history backend/frontend를 임시 기동해 API·웹·3개 artifact의 6개 download SHA가 모두 HTTP 200으로 일치했습니다.
- 검토 결과와 남은 문제: 독립 검토 PASS, blocking finding 없음. TOCTOU 경쟁 교체는 범위 밖이며 입력은 고정 archive의 읽기 전용 provenance만 검증합니다.
- 보존 및 제외: 기존 HANDOFF.md 보존. PAPER/DB/orders/collector/GPU/runner/quota/remote 및 과거 blocked 작업 변경 없음.
- 결과 커밋 SHA: `d499309`, `ee4a0f8`. 통합 커밋: `2f729585b3aec107cb28f309a2bac9620e4d1fab`.
- 게시: `/research/history` 항목 `small-entry-draft-provenance-audit-v1-484028675d0647a0a0b47f86c46a5ca5`; 기존 seed 보존. artifact SHA는 `3c610ff4063722f7bfc278e3203c62b467be06ce73b1fa5dd5ac4fb26e313bb8`, `4e37b3ab706d1c7eb2f90954c4c0fb9a8baef9afca7e9a4e96b66d26e983765b`, `a7077e91aef71d4e4bec46c93f1140272bcfc424b510e31b35661f06185eb4bc`입니다.
- 개발 기록: `docs/development-records/2026-09-19-small-entry-draft-provenance.md`. audit `/home/kwl/.local/share/jusik/portfolio-audit/small-entry-draft-provenance-audit-v1-484028675d0647a0a0b47f86c46a5ca5`.
- 워크트리 정리: audit·handoff SHA 확인 후 `/home/kwl/projects/jusik-small-entry-draft-provenance-4840` worktree를 정상 제거했습니다. 루트 `HANDOFF.md`는 보존합니다.

## future-observation-revision-9773

- 상태: 완료
- 목표와 완료 조건: 합성 revision-link 구조 감사, 독립 기대값·검토·main 검사·공개 보고·영구 증거 보존.
- 담당 Luna: revision_luna (gpt-5.6-luna), 단일 구현 소유자
- 워크트리 절대 경로: /home/kwl/projects/jusik-future-observation-revision-9773
- 작업 브랜치: feat/future-observation-revision-9773
- 기준 커밋 SHA: 824f2a357e9b800050138157814f9078525a15f6; 등록 커밋을 생성 기준으로 사용합니다.
- 통합 대상 브랜치: local main
- 입력과 선행 작업: replay·프로토콜 읽기 전용 explore, bounded plan 완료.
- 수정 허용 범위: backend/jusik/research_future_observation_revision_audit.py, backend/tests/test_research_future_observation_revision_audit.py, docs/research/future-observation-revision-link-audit-v1.md
- 포트·테스트 DB·출력 경로: 서버/DB 없음. worktree .venv/tmp/cache 격리. 영구 audit /home/kwl/.local/share/jusik/portfolio-audit/future-observation-revision-link-audit-v1-97739cd36077413eab39ecf6961f673c
- 검증 방법: 신규+replay pytest, Ruff check/format, strict mypy, 독립 review, main 재검사.
- 중단 조건: 합성 구조 감사만 수행하며 selection/temporal policy는 미정. PAPER/실주문/DB/collector/GPU/runner/quota/remote 변경 금지.

- 결과 커밋 SHA: b72e91dcd1f29109746fb00afcc01e3a071b6b8d (초기 검토 수정 이력 보존)
- 병합 직전 main SHA: ea76c5646add58ec714698336c408a88d0d9f4e7
- 통합 커밋 SHA: d87174ac722bbd420f0747624afbc92c5810a240
- 검토 결과: 최종 독립 검토 승인. synthetic 강제·다중 부모 SCC·필수 회귀와 한도 검사 지적 해결.
- 통합 검증: 신규+replay pytest 38개, Ruff check/format, strict mypy 두 파일, diff 통과. 감독 독립 10 fixture·raw/availability/CLI bytes, 검토자 512 graph oracle 일치.
- 검사 제한: frontend 변경 없어 build 비적용. 전체 backend 검사 대신 요청된 집중 검사 수행.
- 웹: /research/history 한국어 보고서와 검사 요약, API/web 제목 및 4개 첨부 다운로드 SHA 검증. 기존 공개 항목 보존.
- 정리: 근거·환경·hash·handoff 65파일을 먼저 영구 보관·검증한 뒤 작업 생성물과 병합 worktree 제거. 브랜치 보존. 기존 HANDOFF와 다른 워크트리 보존.
- 통합 검증 실패 원인과 복구 결과: 통합 실패 없음. 작업 환경 초기 Python 경로 문제는 격리된 Python3.13 venv 재생성으로 해결.
- handoff 저장 경로: /home/kwl/.local/share/jusik/portfolio-audit/future-observation-revision-link-audit-v1-97739cd36077413eab39ecf6961f673c/handoff.md

## small-entry-draft-provenance-d946

- 상태: 완료
- 목표와 완료 조건: 고정 bundle provenance 검증기, 합성 경계와 보관 입력 검증, 독립 검토, main 통합 검사, 연구 이력 게시와 영구 handoff.
- 담당 Luna: provenance_luna (gpt-5.6-luna), 단일 구현 소유자.
- 워크트리 절대 경로: /home/kwl/projects/jusik-small-entry-draft-provenance-d946
- 작업 브랜치: feat/small-entry-draft-provenance-d946
- 기준 커밋 SHA: 2ee7b0a; 등록 커밋을 실제 생성 기준으로 사용합니다.
- 통합 대상 브랜치: local main
- 입력과 선행 작업: explore/plan 완료. 지정 archive 네 파일 읽기 전용. 이전 미통합 커밋 d499309, ee4a0f8의 세 파일만 재사용하며 이전 워크트리는 보존합니다.
- 수정 허용 범위: backend/jusik/research_small_entry_draft_provenance.py, 대응 tests, docs/research/small-entry-draft-provenance-audit-v1.md
- 포트·테스트 DB·출력 경로: 서버/DB 없음. 작업별 venv/tmp. 영구 audit /home/kwl/.local/share/jusik/portfolio-audit/small-entry-draft-provenance-audit-v1-d946e107ca2a46e0a88ea65391331b60
- 검증 방법: 신규+draft+분포 pytest, Ruff check/format, strict mypy, 보관 네 파일 전후 SHA 및 반복 출력 일치, 독립 review, main 재검사, 웹/API 다운로드 SHA 확인.
- 제외: 미래 자료·임계값·정책·PAPER/운영 DB·collector/order/GPU·runner/quota·remote push 변경 및 과거 blocked 큐 재시도 없음.

- 결과 커밋 SHA: f512484d6cf2f06b65d0cf25e7b36de78e83c2e8 (선행 1d5c2dc)
- 검토 결과: 독립 review 통과, 중요 지적 없음. 별도 pytest 41개와 네 파일 변조/symlink probe 통과.
- 병합 직전 main SHA: 35af566e70927fe1f907611b77d888efd674dc88
- 통합 커밋 SHA: a2da7de8848c57a0408e7e9f1515a8078cb4baa0
- 통합 검증: 관련 pytest 47개, Ruff check/format, strict mypy 82개 소스, diff 통과. 원본 네 파일 SHA·반복/relocation 출력 일치. 기존 backend/frontend/deploy 118개 파일 보존. UI 미변경으로 build 생략.
- 게시: /research/history 보고서·공개 manifest·검사 3개 artifact, API/웹 제목 및 다운로드 6건 SHA 검증 완료. 기존 history seed 보존.
- 정리: 증거·환경·SHA·handoff 54개 파일을 영구 audit에 보관/대조한 뒤 이번 워크트리만 제거. 이전 4840 워크트리와 브랜치는 기존 상태·소유권 보존을 위해 유지.
- handoff 저장 경로: /home/kwl/.local/share/jusik/portfolio-audit/small-entry-draft-provenance-audit-v1-d946e107ca2a46e0a88ea65391331b60/handoff-final.md. 기존 root HANDOFF 내용 보존 후 이번 기록 추가.
- 통합 검증 실패: 없음. 남은 작업 없음.

## portfolio-symbol-removal-15a6

- 상태: 완료
- 목표와 완료 조건: 고정 32개 simulation의 모든 종목 기여분 차감 산술 민감도, 부호 반전 식별, 독립 검토, main 통합 검사, 한국어 연구 이력 게시와 영구 증거 보존.
- 담당 Luna: gpt-5.6-luna 단일 구현 소유자.
- 워크트리 절대 경로: /home/kwl/projects/jusik-portfolio-symbol-removal-15a6
- 작업 브랜치: feat/portfolio-symbol-removal-15a6
- 기준 커밋 SHA: da76dd015cf583f73ee3acb4dd525748934dc74a. 등록 커밋을 실제 생성 기준으로 사용합니다.
- 통합 대상 브랜치: local main
- 입력과 선행 작업: 지정 unheld-entry-real32 및 verified-analysis/attribution.json 읽기 전용; explore 후 bounded plan.
- 수정 허용 범위: backend/jusik/research_portfolio_concentration.py, 대응 tests, docs/research/portfolio-symbol-removal-attribution-v1.md
- 포트·테스트 DB·출력 경로: 서버/DB 없음. 작업별 venv/tmp. 영구 audit /home/kwl/.local/share/jusik/portfolio-audit/portfolio-symbol-removal-attribution-v1-15a65c0ea4694f0da1b0c8affd420f65
- 검증 방법: 합성 경계 및 기존 attribution pytest, Ruff check/format, strict mypy, 고정 입력 반복 출력·SHA 대사, 독립 review, main 재검사, 웹/API 다운로드 SHA.
- 제외: 재배분·재시뮬레이션·미래 자료·정책 활성화·PAPER/운영 DB·collector/order/GPU·runner·remote push 변경 없음. PAPER 10% 유지.
- 종료 조건: auditable 결과와 구현 workflow 완료. followup=null, 대기 중 portfolio-next-development-selection-v1이 두 분석을 통합합니다.

- 결과 커밋 SHA: 0b62dc1b9842e47fa196a9074e743f523d0511ab (선행 7029a56, ffd9449 수정 이력 보존).
- 병합 직전 main SHA: 66361d85edfc89a363c0eedaf7f08722e1e2c84e
- 통합 커밋 SHA: 6bf9910ccadf4abd4cc5b1c22ba50b46f73e10f4
- 검토 결과: 독립 review 승인. 초기 SHA 재읽기·회귀 테스트·formula 비교·문서 hash 지적을 해결했고 production 9개 및 synthetic fault 8개 probe 통과.
- 통합 검증: pytest 42개, Ruff check/format, strict mypy 83개 소스, diff check 통과. 동결 입력 256행과 독립 계산의 1,536개 금액·비율, 부호 반전 표시 일치. JSON/CSV/report 반복 byte 동일.
- 검사 제한 및 복구: 격리 venv 전체 mypy는 기존 optimizer의 torch 미설치로 실패했으나 신규 모듈·테스트 strict 통과, GPU 설치 없이 main 기존 환경 전체 검사 통과. 기존 deprecation 경고 2개. UI 미변경으로 frontend build 비적용. 통합 검사 실패 없음.
- 결과: fold_1 c1 000660·AMD·COHR·SOXL, c2 000660·COHR·SOXL에서만 strict flip 7건. fold_2~7 및 continuous 없음. 고정 초기자본 1억 원, 재배분 없는 사후 산술.
- 게시: /research/history 한국어 전체 256행 보고서·manifest·검사 3개 artifact. API/웹 및 6개 다운로드 SHA 검증, 기존 seed 항목 보존.
- 보존·정리: 원본 123개 hash 항목 불변. 증거·환경·소스·hash·handoff 67개 파일 영구 보존 검증 후 git worktree remove로 이번 병합 워크트리 제거. 브랜치, 기존 HANDOFF.md, 이전4840 워크트리 보존.
- handoff 저장 경로: /home/kwl/.local/share/jusik/portfolio-audit/portfolio-symbol-removal-attribution-v1-15a65c0ea4694f0da1b0c8affd420f65/handoff-final.md
- 남은 작업: 없음. followup=null; 대기 중 portfolio-next-development-selection-v1이 두 분석을 통합합니다.

## portfolio-exposure-cost-734e

- 상태: 완료
- 목표와 완료 조건: 동결 32개 시뮬레이션의 노출·실제 비용 비교와 사전 고정 1/2/3배 산술 민감도, 독립 검토, main 통합 검사, 한국어 연구 게시 및 영구 증거 보존.
- 담당 Luna: gpt-5.6-luna 단일 구현 소유자.
- 워크트리 절대 경로: /home/kwl/projects/jusik-portfolio-exposure-cost-734e
- 작업 브랜치: feat/portfolio-exposure-cost-734e
- 기준 커밋 SHA: 292f663527e85ec1f1b901fe6039ea5b24ddddac. 등록 커밋을 실제 생성 기준으로 사용합니다.
- 통합 대상 브랜치: local main
- 입력과 선행 작업: 지정 unheld-entry-real32 읽기 전용. explore 완료, plan 단계 후 구현. 계산 전에 audit/preregistered-diagnostics.json에 1/2/3배와 초기 1억 원 고정.
- 수정 허용 범위: backend/jusik/research_portfolio_exposure_cost.py, 대응 tests, docs/research/portfolio-exposure-cost-tradeoff-v1.md. 등록부는 감독만 관리합니다.
- 포트·테스트 DB·출력 경로: 서버/DB 없음. 독립 venv/tmp. 영구 audit /home/kwl/.local/share/jusik/portfolio-audit/portfolio-exposure-cost-tradeoff-v1-734e493df492407891611c190b42a54b
- 검증 방법: 합성 경계·회계 pytest, Ruff check/format, strict mypy, 동결 입력 전후 SHA, 반복 출력, 독립 review, main 검사, 웹/API 및 다운로드 SHA.
- 제외: 운영 엔진/PAPER/설정/DB/collector/order/GPU 변경, 재수집·정책 활성화·remote push 없음. PAPER 10% 유지. 노출 정규화 승자 선정·탐색·가상 MDD/실현 가능성 주장 없음.
- 종료 조건: 통합 검사와 영구 evidence/hash/handoff 보존 후 병합 worktree 정리. followup=null; 대기 중 portfolio-next-development-selection-v1에서 다음 작업 결정.

- 결과 커밋 SHA: 4620a84fb17dcf1b0eba82b05f012a9fde7d5b6e. 구현 커밋과 후속 회귀 보완 이력 보존.
- 병합 직전 main SHA: a543d79235ffb357b4130b6cf0884da18c079c6f. 최초 통합 후 타입 오류 수정 별도 병합.
- 통합 커밋 SHA: 5022efa9a5cb6f25a64890bf149847935b2a48ff
- 독립 검토: 최종 승인. UTC 정렬 미적용, 구현을 호출하지 않는 테스트와 누락 경계, 입력 manifest 재읽기 문제 해결. 필수 11개 테스트 독립 통과.
- 통합 검사: pytest 52개, Ruff check/format, strict mypy 84개 소스, diff 통과. 기존 deprecation 경고 2개, frontend 미변경으로 build 비적용.
- 통합 실패 및 복구: 첫 전체 mypy에서 frozen PortfolioSimulation에 대입하는 불필요한 fallback 실패. 해당 분기를 제거한 별도 커밋을 검토·병합하고 모든 통합 검사 재통과. 실패 로그 보존.
- 계산 근거: 실제 32행, UTC 마지막 일별 노출 4,696행, 실제 c2-c1 16행, 사전 고정 1/2/3배 산술 48행. 독립 원본 계산 5,080개 값 일치, 최종 7개 산출물 반복 byte 동일.
- 게시: /research/history 한국어 전체 행 보고서·manifest·검사 3개 artifact, 웹/API와 다운로드 6개 SHA 검증. 기존 history 항목 보존.
- 보존: frozen 입력과 기존 backend/frontend/deploy SHA 불변. 초기 작업자 amend 발견 후 원래 검토 커밋912160f를 archive/exposure-cost-original-734e와 patch에 보존하고 이후 수정은 별도 커밋으로 진행.
- 정리: 환경·결과·검사·hash·handoff 영구 보관 및 검증 후 git worktree remove로 이번 병합 워크트리만 제거. force 미사용. 작업 브랜치, 기존 HANDOFF와 이전4840 워크트리 보존.
- handoff 저장 경로: /home/kwl/.local/share/jusik/portfolio-audit/portfolio-exposure-cost-tradeoff-v1-734e493df492407891611c190b42a54b/handoff-final.md
- 남은 작업: 없음. followup=null; 대기 중 portfolio-next-development-selection-v1에서 두 분석을 통합 검토합니다.

## portfolio-next-development-selection-bbbd

- 상태: 완료
- 목표와 완료 조건: 완료 증거를 검증한 뒤 corrected-entry 2%p/4%p 보유 밴드 격리 실험 하나를 실행 가능한 후속 과제로 명세하고 한국어 이력에 게시합니다.
- 담당 Luna: `/root/code_selection`
- 워크트리 절대 경로: `/home/kwl/projects/jusik-portfolio-next-selection-bbbd`
- 작업 브랜치: `docs/portfolio-next-selection-bbbd`
- 기준 커밋 SHA: `863d908b3ba34865b9a5deedf786575e62cdf092` (등록부를 포함한 실제 워크트리 기준)
- 통합 대상 브랜치: 로컬 `main`
- 입력과 선행 작업: explore와 순차 plan 완료. 두 선행 completion의 모든 evidence SHA 및 main 조상 관계를 감독이 검증했습니다.
- 수정 허용 범위: `docs/research/portfolio-next-development-selection-v1.md`만 Luna가 수정합니다. 등록부와 영구 증거 및 게시 기록은 감독이 관리합니다.
- 포트·테스트 DB·출력 경로: 서버와 DB 없음. 독립 워크트리; 영구 audit `/home/kwl/.local/share/jusik/portfolio-audit/portfolio-next-development-selection-v1-bbbd21c0082348b09c073c45d73f3e17`.
- 검증 명령과 결과: 기준 관련 pytest 44 passed. 문서 수치·중복 작업·고정 입력 검토 후 관련 pytest/Ruff/strict mypy를 통합 재검증합니다.
- 종료 조건: 독립 review, main 병합/검사, 웹 게시, 영구 SHA/environment/handoff 저장 후 병합 워크트리를 정리합니다. 코드·PAPER·운영 설정·runner·GPU·기존 연구 자료는 수정하지 않습니다.
- 결과 커밋 SHA: `5beebcf92c131bb45051d640b1a59f7847f04cdb`
- 검토 결과와 남은 문제: 독립 `/root/review` 통과. 대조군 경로, 전체 model exact equality, 동일 corrected engine/hash 및 근거 참조를 수정하고 재검토했습니다. 남은 차단 사항 없음.
- 병합 직전 main SHA: `863d908b3ba34865b9a5deedf786575e62cdf092`
- 통합 커밋 SHA와 정리 여부: `ac238c68238f4304380442aee3c9a0e94731fc3e`. 영구 증거와 handoff 및 SHA를 먼저 보존한 후 워크트리와 병합 브랜치를 제거했습니다.
- 통합 검증: 관련 pytest 44 passed(기존 경고 2개), Ruff 8개 source/test 통과, strict mypy 4개 source 통과, git diff --check 통과. 문서만 변경하여 frontend build는 해당하지 않습니다.
- 게시 결과: `/research/history` 항목 `portfolio-next-development-selection-v1-bbbd21c0082348b09c073c45d73f3e17`. API/웹 다운로드 200 및 문서 SHA 일치, 기존 이력 62개·산출물 108개 보존.
- 통합 검증 실패 원인과 복구 결과: 검사 실패 없음. 게시 directory rename은 mount EBUSY였으나 새 artifact와 seed 파일의 원자적 교체로 완료했습니다. 실패 시 생성된 임시 복사본도 영구 보존본을 확인한 뒤 제거했습니다.
- handoff 저장 경로와 갱신 여부: `/home/kwl/.local/share/jusik/portfolio-audit/portfolio-next-development-selection-v1-bbbd21c0082348b09c073c45d73f3e17/handoff-final.md`. 기존 root HANDOFF.md는 보존했습니다.
- 후속 작업: `portfolio-held-band-interaction-v1` 하나를 completion.followup으로 제출합니다. 기존 corrected-entry 2%p와 새 4%p를 동일 frozen engine에서 32회 비교하는 별도 격리 실험이며 이번 선정 작업에서는 실행하지 않았습니다.

## portfolio-held-band-cce0

- 상태: 완료
- 목표와 완료 조건: corrected-entry 동일 엔진에서 2%p/4%p와 비용 1/2배를 7개 fold 및 continuous에 정확히 32회 실행하고, 16개 전체 exact control 및 Decimal 회계를 검증합니다.
- 담당 Luna: gpt-5.6-luna 단일 구현 소유자. explore 후 순차 plan, 독립 review.
- 워크트리 절대 경로: /home/kwl/projects/jusik-portfolio-held-band-cce0
- 작업 브랜치: feat/portfolio-held-band-cce0
- 기준 커밋 SHA: 9bafb0ce7bfef4f826669045e3ffc428b96fdf8a (이 등록 커밋을 실제 생성 기준으로 사용합니다.)
- 통합 대상 브랜치: 로컬 main
- 입력과 선행 작업: 지정 source 3개, corrected preregistration/results 및 variant simulation 16개. 총 입력 21개와 core 4개 SHA 검증 통과.
- 수정 허용 범위: backend/jusik/research_portfolio_held_band_experiment.py, backend/tests/test_research_portfolio_held_band_experiment.py, docs/research/portfolio-held-band-interaction-v1.md. 등록부는 Astra만 수정합니다.
- 포트·테스트 DB·출력 경로: 서버/DB 없음. 워크트리 전용 venv/tmp. 영구 audit /home/kwl/.local/share/jusik/portfolio-audit/portfolio-held-band-interaction-v1-cce0cdf0e5ea43e4a088f2dfe5c2fa74.
- 검증 명령과 결과: synthetic pytest, 관련 회귀 pytest, Ruff check/format, strict mypy, 전체 exact control 16개, Decimal 회계 32개, 입력 전후 SHA, 독립 review, main 통합 검사.
- 제외: 제품 엔진/DB/PAPER 설정/runner/GPU 변경, 주문, remote push/refetch, 원본 b2 simulation 사용, retuning/winner selection.
- 종료 조건: main 통합·검사·연구 게시·영구 evidence/hash/handoff 저장 후 병합 워크트리 정리. broader engineering gaps를 결과 이후 읽기 전용 확인하여 즉시 실행 가능한 successor 최대 하나만 제안합니다.
- 실행기 확인: 현재 running attempt는 이 task/attempt 하나이며 CLI completion 경로를 읽기 전용 확인했습니다. 실행기 상태는 변경하지 않습니다.

- 결과 커밋 SHA: 구현 `a37cdda51e203226e0127daef5f54556b6ba03df`, 최종 문서 `246d348dbd88b44fec2970acc399180aeb6d7edc`.
- 병합 직전 main SHA: `6fd7346bc6a799a932db17438e377d17196a02ed`.
- 통합 커밋 SHA: 구현 `7486b2c9ac51edff0d36a68dbcb48293a47d32ab`, 검증 문서 `2aba6eb8c433204e384bc44b8f9d2eff2f8a4d8e`.
- 검토 결과: 독립 사전·결과·최종 코드/문서 review 통과. 초기 엔진 선택, JSON tuple key, eager hash fallback, Decimal precision 및 실패 산출물 보존 문제를 실행 전에 수정했습니다. 독립 verifier의 strict next-open/가격 exact 보강은 저장 결과에만 적용했으며 역사 재실행은 없습니다.
- 실제 결과: 정확히 32회 완료, corrected control 16개 전체 typed JSON exact equality. 2,347 trades 원시 개장가·FX·현금·최종 자산 독립 재계산, 최대 금액 잔차 4e-31 KRW. 양 비용 fold return delta 중앙값 0, fold 4 음수, fold 1/2/3/6 전체 결과 동일. continuous delta는 별도로 +1.052528/+0.817125%p이며 승자 선정은 하지 않습니다.
- 검증 결과: main pytest 71 passed(기존 deprecation 경고 2개), strict mypy 84개 소스, Ruff check/format, git diff --check 통과. 별도 입력 경계 26개와 모의 runner 실패/성공 5개 시나리오 통과. frontend 미변경으로 build 비적용. 통합 검사 실패 없음.
- 게시 결과: /research/history 항목 `portfolio-held-band-interaction-v1-cce0cdf0e5ea43e4a088f2dfe5c2fa74`; API/웹 다운로드 200과 문서 SHA 일치. 기존 seed 항목 63개와 artifact 109개 보존, DB 변경 없음.
- 보존·정리: 영구 audit에 실제/모의 산출물, 입력/소스/검사/hash/review/환경을 보존했습니다. 227개 영구 파일과 handoff 및 archive hash 검증 뒤 이번 병합 워크트리와 전용 브랜치를 제거했습니다. 기존 HANDOFF.md와 이전 4840 워크트리는 보존합니다.
- handoff 저장 경로: /home/kwl/.local/share/jusik/portfolio-audit/portfolio-held-band-interaction-v1-cce0cdf0e5ea43e4a088f2dfe5c2fa74/handoff-final.md.
- 남은 실패: 실제 실행·통합 실패 없음. 후향/PIT 미인증, 조기 폐장과 broker receipt 부재는 연구 한계입니다.
- 후속 제안: `portfolio-session-calendar-stress-v1` 하나. 검증된 offline calendar를 쓰는 격리 adapter/복사 엔진과 synthetic 테스트 3개 신규 파일만 허용하며 제품/PAPER/DB/runner/GPU 변경과 역사 재실행을 제외합니다.


## empty-queue-planner

- 상태: 완료
- 목표와 완료 조건: 연구 큐가 비면 기존 결과를 근거로 읽기 전용 Astra 계획을 실행하고 검증된 후속 과제 하나를 원자적으로 등록합니다. 대기·중복·실패·한도·권한 및 다음 주기 실행을 검증합니다.
- 담당 Luna: gpt-5.6-luna, 단일 구현 소유자. 감독 조사와 순차 계획 완료 후 구현, 독립 검토를 수행합니다.
- 워크트리 절대 경로: /home/kwl/projects/jusik-empty-queue-planner
- 작업 브랜치: feat/empty-queue-planner
- 기준 커밋 SHA: 73fdc43de94c39825731002f6f91fea8a764a660 (등록 커밋을 실제 생성 기준으로 사용합니다.)
- 통합 대상 브랜치: 로컬 main
- 입력과 선행 작업: 기존 runner/store 및 history 흐름. 진행 중 held-band 작업 완료 후 pause와 서비스 inactive 확인.
- 수정 허용 범위: backend/jusik/development_runner{,_store,_planning}.py, 관련 runner/planning tests, docs/development-runner.md. 등록부·handoff·운영 설정은 감독만 관리합니다.
- 포트·테스트 DB·출력 경로: 독립 worktree venv와 임시 fixtures. 영구 audit /home/kwl/.local/share/jusik/portfolio-audit/20260912T114934Z-empty-queue-planner.
- 검증 명령과 결과: 관련 pytest, Ruff check/format, strict mypy, 실제 read-only sandbox와 Codex 계획 및 다음 주기 dispatch 검증 예정.
- 종료 조건: 독립 review, main 병합/통합 검사, 웹 기록, 운영 활성화, 증거/hash/handoff 보존 후 이번 worktree 정리.
- 보존 조건: 하루 한도24 및 기존 이력, PAPER/실거래/전략/운영 DB/GPU 설정은 유지합니다. 계획도 기존 quota와 lifecycle을 사용합니다.

- 통합 검증 실패 및 복구: main 병합 6f07ab177b9f6e4fc708f281acebe8e2dfe31f94에서 pytest55·Ruff lint·strict mypy는 통과했고 테스트 파일 한 줄 format 검사만 실패했습니다. Luna의 포맷 수정 및 통합 재검증 전 정리와 운영 재개를 보류합니다.

- 결과 커밋 SHA: 구현 ca4527e, 보완 e68a1b9, 회귀 검증5793462·6869012·631ff2f, 포맷 c1a1d26.
- 병합 직전 main SHA: 66a29ee. 기능 통합6f07ab177b9f6e4fc708f281acebe8e2dfe31f94, 포맷 복구 통합663a643ea90bc09bb08c1a065e3b7e7c5952dcd5.
- 최종 검증: main pytest55·Ruff lint·strict mypy 통과. 포맷 실패는 복구 병합 뒤 format/lint/diff 통과 및 AST 동일성으로 해소했습니다. 독립 소스 검토 통과. 테스트의 gate 허위 통과와 outside-root 해시 혼입은 별도 수정·검증했습니다.
- 실제 실행 증거: 읽기 전용 profile의 attempt 쓰기 허용 및 source/Git/다른 state/artifact/network 차단. 격리 synthetic fixture에서 실제 Astra 제안 등록, 다음 주기의 stub child 선택 확인. 실제 연구/수익 검증으로 혼동하지 않습니다.
- 운영 반영: planning_enabled=true, 하루24회 및 기존 모든 launch/task 기록 보존. queued portfolio-session-calendar-stress-v1부터 재개합니다. 실제 재개 상태는 영구 audit의 activation.json에 기록합니다.
- 통합 커밋 및 정리: 14개 필수 영구 파일의 SHA를 정리 전후 대조한 뒤 이번 워크트리와 전용 브랜치를 force 없이 제거했습니다. 이전4840 워크트리와 기존 HANDOFF 내용을 보존했습니다.
- 문서 통합 보완: 감독이 planning 권한 설명에서 읽기 전용 명령 허용 범위와 transaction 내부 재검증을 명확히 했습니다.
- handoff 저장 경로: /home/kwl/.local/share/jusik/portfolio-audit/20260912T114934Z-empty-queue-planner/handoff-final.md. root HANDOFF.md에서 연결합니다.


## portfolio-held-band-cost3-f9ae

- 상태: 완료
- 목표와 완료 조건: held-band 저장 32개 전체 JSON exact replay 후 비용 3배 16개를 실행하고, 고정체결 산술과 실제 순손익·MDD·회전율 및 현금·수량 차이를 검증합니다.
- 담당 Luna: gpt-5.6-luna 단일 구현 소유자; explore, 순차 plan, 독립 review 후 Astra 통합.
- 워크트리 절대 경로: /home/kwl/projects/jusik-portfolio-held-band-cost3-f9ae
- 작업 브랜치: feat/portfolio-held-band-cost3-f9ae
- 기준 커밋 SHA: 15213cdd353de92193077ce2aef660c807a6d7d4 (이 등록 커밋을 실제 생성 기준으로 사용합니다.)
- 통합 대상 브랜치: 로컬 main
- 입력과 선행 작업: held-band experiment의 고정 results/preregistration/hash-manifest, frozen source와 corrected engine 및 simulation 32개.
- 수정 허용 범위: backend/jusik/research_portfolio_held_band_cost3_stress.py, backend/tests/test_research_portfolio_held_band_cost3_stress.py, docs/research/portfolio-held-band-cost3-stress-v1.md. 등록부는 Astra만 수정합니다.
- 포트·테스트 DB·출력 경로: 서버/DB 없음. 독립 worktree venv/tmp; 영구 audit /home/kwl/.local/share/jusik/portfolio-audit/portfolio-held-band-cost3-stress-v1-f9aecd54dffc4931a6100ac2de8c8cd3.
- 검증 명령과 결과: 관련 pytest·Ruff·strict mypy, 역사 실행 전 +1 KRW 변조 검출, 32 exact replays, 16 stress, Decimal 회계와 cutoff/next-open/UTC, 독립 review, main 통합 검사 예정.
- 종료 조건: 48회 이하·60분 한도; hash/replay/회계/누출 실패 시 즉시 중단·증거 보존·재시도 금지. 성공 시 로컬 통합·검사·handoff와 필요한 게시 후 durable 보존을 확인하고 이번 worktree만 정리합니다.
- 보존 조건: 자본 1억원, 최대 손실 허용20%, leverage 배분 cap20%, frozen drawdown_limit=.10/gross_cap=.60/symbol_cap=.20. PAPER10%와 실거래 유예. 제품/DB/config/remote/주문/GPU 불변.
- 실행기 확인: running attempt는 portfolio-held-band-cost3-stress-v1 / f9aecd54dffc4931a6100ac2de8c8cd3 하나입니다. 실행기 상태를 변경하지 않습니다.

- 결과 커밋 SHA: 구현 `21bbb9adbe7a9fc0dd6322689bbf502eaa36d057`, metadata 보완 `5c53b04ea77956e63e309b273fdd87d0184a1729`, 포맷 `e4782741b6427fe70bcafc5ee5128989a086a2c1`, 보고서 `0ea1fbe86cf349ba464698e2eb9a8382164a2783`.
- 병합 직전 main SHA: `06a8924468811c7adb478aa80e13ad58b4c739b6`. 통합 커밋 SHA: `1698741c1eaab4bda9e9b41301dce3a11ad42177`.
- 실제 결과: 32개 전체 JSON exact replay 뒤 16개 비용3 스트레스, 총48회·30.6658초·재시도0. 초기 +1 KRW 변조32개 거부. 독립48개 회계 최대 오차4e-31 KRW. fold 수익률/MDD/회전율 차이 중앙값 모두0, fold4 수익률 차이는 음수이며 actual3x가 fixed 산술보다 낮은 경우10/16입니다. Continuous는 별도로 보고했습니다.
- 검토 결과: 초기 runtime 변조/FX/helper hash/완전성/중앙값/metadata 지적을 역사 실행 전에 보완하고 독립 코드·결과 review를 통과했습니다. source AST가 동일한 포맷 보완도 확인했습니다. 독립 verifier와 보고서 파서 개발 중 스키마 오류는 증거에 보존했고 실제 입력·replay·회계·누출 실패는 없습니다.
- 통합 검증: pytest75개, strict mypy86개 소스, Ruff lint/format, diff 검사 통과. 기존 tracked215개 보존. 워크트리 전체 mypy는 선택 의존성 torch 부재로 제한됐으나 관련 모듈 및 main 전체 mypy는 통과했습니다. torch 설치나 GPU 변경은 없습니다. frontend 미변경으로 build 비적용.
- 게시: 연구 history 항목 `portfolio-held-band-cost3-stress-v1-f9aecd54dffc4931a6100ac2de8c8cd3`, API/웹 다운로드200 및 SHA 일치. 기존 이력65개와 artifact111개 보존, DB 변경 없음.
- 보존·정리: 입력·소스·실제48개 결과·검사·review·publication·handoff 포함 영구575개 파일을 정리 전후 SHA 대조했습니다. 이번 워크트리·전용 브랜치를 force 없이 제거했고 기존 HANDOFF.md와 이전 두 워크트리를 보존했습니다.
- handoff 저장 경로: /home/kwl/.local/share/jusik/portfolio-audit/portfolio-held-band-cost3-stress-v1-f9aecd54dffc4931a6100ac2de8c8cd3/handoff-final.md.
- 남은 작업: 요청 범위 없음. 후향/PIT 미인증, 조기 폐장·partial/cancel/reject 미지원은 유지합니다. 추가 배수/밴드 탐색, 승자 선정, 정책 승격, 손실 보장은 없습니다.


## portfolio-held-band-cost-path-0f90

- 상태: 완료
- 목표와 완료 조건: 저장48개 hash 및 회계 검증 후32개 비용 비교와16개 밴드 분해 차이, 음수 결과와 결정적 출력 증거를 보존합니다. 역사 실행·외부 수집·튜닝은0회, 분석은2회 이하 및15분 한도입니다.
- 담당 Luna: gpt-5.6-luna 단일 구현 소유자. 감독 explore 후 순차 plan, 별도 review를 수행합니다.
- 워크트리 절대 경로: /home/kwl/projects/jusik-portfolio-held-band-cost-path-0f90
- 작업 브랜치: feat/portfolio-held-band-cost-path-0f90
- 기준 커밋 SHA: cf0db95 (등록부를 포함한 실제 생성 기준)
- 통합 대상 브랜치: local main
- 입력과 선행 작업: portfolio-held-band-cost3-stress-v1-f9aecd54dffc4931a6100ac2de8c8cd3/experiment의 results, preregistration, manifest와 simulations48개. 상위3개 hash 검증 일치.
- 수정 허용 범위: 신규 research_portfolio_cost_path_attribution 모듈, 대응 테스트, 한국어 연구 문서. 기존 attribution 회계를 재사용합니다.
- 포트·테스트 DB·출력 경로: 포트/DB 미사용. worktree 독립 venv. 영구 audit /home/kwl/.local/share/jusik/portfolio-audit/portfolio-held-band-cost-path-attribution-v1-0f907dc6cd5b40cf9604af0bccbb2acd.
- 검증 명령과 결과: 신규 pytest/Ruff/strict mypy 및 회계 residual≤1e-6, 48완전성,32비교, 결정적2회 출력 대조 예정.
- 종료 조건: 검토·main 통합 검사·handoff 및 필요한 웹 게시 후 영구 evidence/hash 확인, worktree 정리.
- 보존 조건: 자본1억원, 사용자 손실20%, leverage cap20%, frozen drawdown.10 및 PAPER10% 불변. 실주문/remote push/PAPER engine·DB/GPU 변경 금지.
- 실행기 확인: 현재 task/attempt 하나만 running이며 CLI output은 해당 attempt/completion.json입니다. runner를 중지하지 않습니다. 기존 HANDOFF.md 및 두 worktree를 보존합니다.

- 실행 결과: 원자료 분석2회, 추가 역사 실행·외부 수집·튜닝0회. 원자료 실행의 보수적 시간 상한534.205초. 32개 비용 비교·16개 밴드 차이를 저장하고 후속 검증과 표 생성은 저장 출력만 사용했습니다.
- 독립 결과 검산: 32개 비교 모두 순손익 감소. 종목 합계와 NAV 차이 최대7.156250e-31 KRW. continuous 비용2에서 .04의 비용 증가가 작아도 경로 악화로 순손익 감소가 더 큰 음수 사례를 보존합니다.
- 검토 보완: manifest 상수, 누락된 분해항, 실제 residual 검산, 합성48 loader, CLI 출력 일치, 테스트 상수 복원 지적을 수정했습니다. 최종 리뷰와 main 통합 검사는 아래에 기록합니다.
- 초기 커밋 보존: 작업자가 초기 커밋95ab4d를 대체하여 원본을 archive/portfolio-cost-path-initial-0f90 및 durable initial-development.bundle에 보존했습니다. 이후 수정은 추가 커밋으로 수행했습니다.

- 결과 커밋 SHA: 최종 `10ff83952e45a788b08432e3daabb4217362876a`.
- 병합 직전 main SHA: `ec0ff7fa4c0a1632e2465cb7a860540740e55921`. 통합 커밋 SHA: `f33e06c54ee5126fc3be3f807822dbdefbddbc64`.
- 검토 결과: 독립 PASS. 추가 합성 fixture7개, 실제 저장 출력32/16 검산, pinned hash 전역 상태 복원 검증 통과.
- 통합 검증: main pytest25개, Ruff lint/format, strict mypy2개 파일, diff 검사 및 기존 코드·48개 입력 hash 보존 통과. frontend 미변경으로 build 비적용.
- 게시: 연구 history 항목 `portfolio-held-band-cost-path-attribution-v1-0f907dc6cd5b40cf9604af0bccbb2acd`, API/웹 다운로드200 및 SHA 일치. 기존 이력66개/artifact112개 보존, DB 미접근. mounted history root의 directory rename은 EBUSY로 실패하여 검증된 seed를 루트 내부 atomic file replace로 게시했습니다.
- 보존·정리: 필수158개 durable 파일을 정리 전후 SHA 대조했습니다. 이번 worktree·전용 작업 브랜치를 force 없이 제거했습니다. 기존56b9·4840 worktree와 기존 HANDOFF.md 내용을 보존했습니다. 초기 커밋 보존용 archive branch와 bundle은 유지합니다.
- handoff 저장 경로: /home/kwl/.local/share/jusik/portfolio-audit/portfolio-held-band-cost-path-attribution-v1-0f907dc6cd5b40cf9604af0bccbb2acd/handoff-final.md.
- 남은 작업: 승인 범위 없음. 부분체결·취소·거절은 unsupported이며 실거래 유예와 기존 제약을 유지합니다.

## portfolio-rebalance-cadence-e017

- 상태: 완료 (새 명시적 retry 실행과 통합 검증 완료)
- 목표와 완료 조건: corrected-entry band 0.02를 고정하여 4/8주 × 비용1/2/3 × 7개 독립 fold 및 continuous의 48회만 실행합니다. 4주 control24 전체 JSON exact replay를 먼저 통과해야 합니다.
- 담당 Luna: gpt-5.6-luna 단일 구현 소유자. explore, plan, 독립 review는 읽기 전용으로 수행합니다.
- 워크트리 절대 경로: /home/kwl/projects/jusik-portfolio-rebalance-cadence-e017
- 작업 브랜치: feat/portfolio-rebalance-cadence-e017
- 기준 커밋 SHA: 5529a54dcd9b7d016586b6bd021d91f7164726ff 이후 이 등록부를 포함한 준비 커밋입니다.
- 통합 대상 브랜치: local main
- 입력과 선행 작업: cost3 f9aecd54 experiment 및 원천 manifest. 54개 artifact와 source/core/helper/runner를 포함한 68개 hash 일치를 input-preflight.json에 기록했습니다.
- 수정 허용 범위: 신규 research_portfolio_rebalance_cadence_cost_stress 모듈, 대응 테스트, 한국어 연구 보고서. 등록부는 Astra만 수정합니다.
- 포트·테스트 DB·출력 경로: 서버/DB 없음. 독립 worktree venv/tmp. 영구 audit /home/kwl/.local/share/jusik/portfolio-audit/portfolio-rebalance-cadence-cost-stress-v1-e017-retry-20260919c. 이전 실패 audit은 보존합니다.
- 검증 명령과 결과: 관련 pytest, Ruff lint/format, strict mypy. control 전체 JSON, hash, temporal cutoff, cadence/holiday/UTC, 위험 청산 및 recovery/cooldown, Decimal residual≤0.000001 KRW를 검사합니다.
- 제한: 최대48회/60분, 재시도·외부 수집 없음. 입력/hash/control/회계 실패 시 중단합니다. 1억원/손실한도20%/leverage20%/frozen drawdown10%를 유지합니다. PAPER/제품엔진/DB/config/주문/remote/GPU 변경 금지.
- 보고 기준: 동일 anchor, reentry_ready부터 reentry까지 시간 및 recovery_reset/기간 말 censoring을 보존합니다. frozen frequency_skip의 four-week cadence 문구는 legacy label임을 명시합니다. 승자 선택·합성·retuning·정책 승격 없음.
- 실행기 확인: 현재 task/attempt가 running인 자동 dispatch입니다. runner를 중지하지 않습니다. 기존 HANDOFF.md와 이전 두 worktree는 보존합니다.
- 종료 조건: 독립 검토, Astra main 병합과 통합 검사, 필요한 게시 및 handoff, 영구 evidence/hash 보존 후 이번 worktree만 정리합니다.

- 실제 실행 결과: 새 retry audit에서 48/48회 완료했습니다. control 24회 전체 JSON exact replay 후 variant 24회를 실행했고, hash manifest 55개와 회계 residual 검사를 통과했습니다.
- 최종 검증: 관련 pytest16개, Ruff lint/format, strict mypy, diff check 통과. 최대 residual `2.4375e-31 KRW`, automatic promotion false입니다.
- 검토 결과: 독립 전체 검토를 완료 조건으로 두며, 결과 지표는 historical/PIT 기술 산출물로만 보존합니다. PAPER/live 승격과 주문은 수행하지 않습니다.
- 통합·정리: 구현·테스트·보고서를 local main에 통합하고 이전 실패 audit 및 root HANDOFF.md는 보존합니다. retry worktree 정리는 검증 기록 후 수행합니다.
- 남은 제한: partial/cancel/reject 체결은 unsupported이며, 본 결과만으로 승자 선택·retuning·정책 승격을 하지 않습니다.
- handoff 저장 경로: /home/kwl/.local/share/jusik/portfolio-audit/portfolio-rebalance-cadence-cost-stress-v1-e017-retry-20260919c/HANDOFF.md.
- runner gate 후속: stale cadence worktree의 검증된 source-path 정리 커밋 `1a7edd6`을 기록하고 main에 `df59edc`·`d806da1`로 통합했습니다. timer 다음 cycle은 dirty gate 없이 idle 종료했습니다.
- planner 후속: timer planner attempt `8234d2559f6e486cb071e529067783a7`는 R1-04/R1-05 실제 근거 부족을 확인하고 `waiting`으로 정상 종료했습니다. 합성 자료·임의 retry·경제 승격은 하지 않았습니다.


## gpu-collector-mode

- 상태: 완료
- 목표와 완료 조건: 사용자가 승인한 GPU 역할 전환. 수집·기존 결과를 유지하면서 GPU를 요청 기반 포트폴리오 스트레스 실험에 사용합니다.
- 담당 Luna: gpt-5.6-luna, 작업별 단일 구현 소유자. 독립 조사·순차 계획 완료.
- 워크트리 절대 경로: /home/kwl/projects/jusik-gpu-collector-mode
- 작업 브랜치: feat/gpu-collector-mode
- 기준 커밋 SHA: 7544e986101d1bcdad166576254cb3836bae8266; 이 등록 커밋을 실제 생성 기준으로 사용합니다.
- 통합 대상 브랜치: local main
- 입력과 선행 작업: 기존 universe daemon 및 보존된 paired continuous NAV 경로. 자동 개발 pause/service inactive 확인.
- 수정 허용 범위: research_universe.py, research_optimizer_store.py, development_runner.py, related tests, docs/research-gpu-role.md, deploy/systemd/jusik-research-optimizer.service. 등록부·handoff·설치 서비스·공개 산출물은 감독 소유.
- 포트·테스트 DB·출력 경로: worktree별 venv/tmp. 영구 audit /home/kwl/.local/share/jusik/portfolio-audit/20260912T212923Z-gpu-role-transition.
- 검증: focused pytest/Ruff check·format/strict mypy, 독립 review, main 통합 검사. GPU 실제512/4096 시나리오·CPU parity 및 collection-only 활성화는 감독 수행.
- 보존: PAPER/live 엔진·DB·동결 계약10% 유지. 기존 GPU 서비스의 CPU 수집 모드 전환은 사용자 명시 승인 범위이며 감독이 원본 unit 보관 후 적용합니다.
- 종료 조건: main 병합·검증, 실제 역할 전환·웹 게시·SHA/handoff 보관, 병합 worktree 정리, 자동 개발 재개.


- 실제 공통 생성 기준: `6ee4be69d3e5d03f40969fee40cae5ca5c308faa`.
- 결과·검증: local main 최종 구현 `844cf6089820815427db03d3baef40d95fa80c9a`; 영향 통합 pytest86개, 후속 stress17개, Ruff check·format 및 변경 파일 strict mypy 통과. 기존 transitive type 오류는 별도 기록. 독립 최종 검토 P1/P2 없음.
- 실제 적용: CPU collection-only 수집·보고서 갱신 확인. CUDA512/4096 parity 최대1.53e-12%p; auto512 CPU/4096 CUDA 확인. 웹 이력·다운로드4경로 검증.
- 복구 기록: 첫 stress 통합에서 torch 설치 환경 타입 오류2개를 발견해635b5ec로 수정 후 재검증했습니다. 초기 CLI 초안은 CUDA·신규 테스트 미완성으로 채택하지 않았습니다.
- 보존·정리: 원본 설정, source patch·환경·SHA manifest·실험·검토·통합 결과를 `/home/kwl/.local/share/jusik/portfolio-audit/20260912T212923Z-gpu-role-transition`에 보관하고 병합 worktree와 branch를 정리했습니다. 기존 미병합3개는 보존합니다.
- handoff: `/home/kwl/.local/share/jusik/portfolio-audit/20260912T212923Z-gpu-role-transition/HANDOFF.md`. 자동 실행 재개 확인은 같은 경로 runner-activation.json을 확인합니다.

## gpu-portfolio-stress

- 상태: 완료
- 목표와 완료 조건: 사용자가 승인한 GPU 역할 전환. 수집·기존 결과를 유지하면서 GPU를 요청 기반 포트폴리오 스트레스 실험에 사용합니다.
- 담당 Luna: 초기 CLI Luna가 CUDA·신규 테스트 미완성 상태로 종료하여 결과를 채택하지 않았습니다. 종료 확인 후 native Luna `collector_transition`에 단일 구현 소유권을 이전했습니다. 동시 구현 담당자는 없습니다.
- 워크트리 절대 경로: /home/kwl/projects/jusik-gpu-portfolio-stress
- 작업 브랜치: feat/gpu-portfolio-stress
- 기준 커밋 SHA: 7544e986101d1bcdad166576254cb3836bae8266; 이 등록 커밋을 실제 생성 기준으로 사용합니다.
- 통합 대상 브랜치: local main
- 입력과 선행 작업: 기존 universe daemon 및 보존된 paired continuous NAV 경로. 자동 개발 pause/service inactive 확인.
- 수정 허용 범위: new research_portfolio_gpu_stress.py, related test, docs/research-portfolio-gpu-stress.md. 등록부·handoff·설치 서비스·공개 산출물은 감독 소유.
- 포트·테스트 DB·출력 경로: worktree별 venv/tmp. 영구 audit /home/kwl/.local/share/jusik/portfolio-audit/20260912T212923Z-gpu-role-transition.
- 검증: focused pytest/Ruff check·format/strict mypy, 독립 review, main 통합 검사. GPU 실제512/4096 시나리오·CPU parity 및 collection-only 활성화는 감독 수행.
- 보존: PAPER/live 엔진·DB·동결 계약10% 유지. 기존 GPU 서비스의 CPU 수집 모드 전환은 사용자 명시 승인 범위이며 감독이 원본 unit 보관 후 적용합니다.
- 종료 조건: main 병합·검증, 실제 역할 전환·웹 게시·SHA/handoff 보관, 병합 worktree 정리, 자동 개발 재개.

- 실제 공통 생성 기준: `6ee4be69d3e5d03f40969fee40cae5ca5c308faa`.
- 결과·검증: local main 최종 구현 `844cf6089820815427db03d3baef40d95fa80c9a`; 영향 통합 pytest86개, 후속 stress17개, Ruff check·format 및 변경 파일 strict mypy 통과. 기존 transitive type 오류는 별도 기록. 독립 최종 검토 P1/P2 없음.
- 실제 적용: CPU collection-only 수집·보고서 갱신 확인. CUDA512/4096 parity 최대1.53e-12%p; auto512 CPU/4096 CUDA 확인. 웹 이력·다운로드4경로 검증.
- 복구 기록: 첫 stress 통합에서 torch 설치 환경 타입 오류2개를 발견해635b5ec로 수정 후 재검증했습니다. 초기 CLI 초안은 CUDA·신규 테스트 미완성으로 채택하지 않았습니다.
- 보존·정리: 원본 설정, source patch·환경·SHA manifest·실험·검토·통합 결과를 `/home/kwl/.local/share/jusik/portfolio-audit/20260912T212923Z-gpu-role-transition`에 보관하고 병합 worktree와 branch를 정리했습니다. 기존 미병합3개는 보존합니다.
- handoff: `/home/kwl/.local/share/jusik/portfolio-audit/20260912T212923Z-gpu-role-transition/HANDOFF.md`. 자동 실행 재개 확인은 같은 경로 runner-activation.json을 확인합니다.

## portfolio-held-band-underwater-38fd

- 상태: 완료
- 목표와 완료 조건: 고정 48개 경로 및 paired 24개 underwater 분석, 검토·main 통합 검사·영구 증거와 handoff 보존.
- 담당 Luna: 단일 gpt-5.6-luna 구현 작업자.
- 워크트리 절대 경로: /home/kwl/projects/jusik-portfolio-held-band-underwater-38fd
- 작업 브랜치: feat/portfolio-held-band-underwater-38fd
- 기준 커밋 SHA: 44bb62b0948545b459d9cd609d1fe5ef1de520d3 이후 이 등록 커밋.
- 통합 대상 브랜치: local main
- 입력과 선행 작업: cost3 stress f9aecd54 experiment, 기존 cost path attribution loader.
- 수정 허용 범위: 새 underwater 분석 모듈·대응 테스트·연구 문서. 등록부는 Astra 소유.
- 포트·테스트 DB·출력 경로: 서버와 DB 없음. worktree 내부 venv/tmp. 영구 audit /home/kwl/.local/share/jusik/portfolio-audit/portfolio-held-band-underwater-duration-v1-38fd7b5ffb304507a1e222205e9d2cac.
- 검증 명령과 결과: pytest/Ruff/strict mypy 및 독립 검토 예정. 실제 분석 48개·paired24개 1회, 단일 CPU 600초 상한, historical simulation 0회.
- 검토 결과와 남은 문제: 진행 전. 기존 HANDOFF와 미병합3개 보존.
- handoff 저장 경로: 위 영구 audit/HANDOFF.md.

- 실제 생성 기준 SHA: `7c96a2a6f9780a4c058e6d5c22a708a314e455ee`.
- 담당 및 결과 커밋: Luna code, `9a471209c21ea49dc4fd180333c29bf3cfe60f74`. 독립 explore/review 최종 승인, material finding 없음.
- 병합 직전 main SHA: `7c96a2a6f9780a4c058e6d5c22a708a314e455ee`.
- 통합 커밋: `2f491ea8f8df1d255638e63ddfcb4b31201095e0`. main pytest47개, Ruff check/format, strict mypy, diff 통과. frontend 변경 없음.
- 실제 분석: 단일 CPU0.3656초, historical simulation0회, 48경로·24paired 한 번. 승인7d04a1e 결과를 보존하고 최종 paired terminal flag는 기존48행에서 복사했다. 추가 경로 분석 없음.
- 결과: fold4 비용1/2/3 모두 MDD 감소와 기간24시간/10.5시간/10.5시간 증가. continuous는3cost 모두 MDD·최장기간 감소, 종료는6경로 모두 미회복. 정책 승격 없음.
- 보존·정리: 영구 audit에359개 파일과 SHA/handoff를 먼저 검증한 후 이번 worktree를 정상 제거했다. 작업 브랜치 및 기존 미병합3개 보존.
- 게시: 기존 연구 이력70개·artifact116개 보존, 보고서 API/웹 다운로드200·SHA 일치. DB 변경 없음. 정확한 통합 SHA는 audit/publication.json에 보존.
- handoff: 위 audit/HANDOFF.md. 기존 루트 handoff 내용 보존. 통합 검증 실패 없음.


## portfolio-expanded-universe-1975

- 상태: 완료
- 목표와 완료 조건: 확정 mandate 추적·planner 읽기 회귀검사, IVV/SGOV+현금 준비도 및 사전등록, independent review·main 통합 검사·웹 게시·증거 보존 후 정리.
- 담당 Luna: 단일 gpt-5.6-luna code 작업자.
- 워크트리 절대 경로: /home/kwl/projects/jusik-portfolio-expanded-universe-1975
- 작업 브랜치: feat/portfolio-expanded-universe-1975
- 기준 커밋 SHA: f87607a337c04c3d8498bed1a465b87d4a5fc78f 이후 이 등록 커밋.
- 통합 대상 브랜치: local main
- 입력과 선행 작업: 사용자 decision SHA30d2108bc082b7d2d9d079fa09548c15f416167174850303c0d852ada269f73c; explore/plan 완료, Astra bounded plan 승인. 현재 runner claim 안에서 실행 중.
- 수정 허용 범위: tracked mandate와 한국어 readiness/prereg 문서, development_runner.py의 최소 planning prompt 변경, 관련 테스트. 등록부·audit·publication·handoff는 Astra 소유.
- 포트·테스트 DB·출력 경로: worktree 전용 venv/tmp; 서버 없음, 운영/PAPER DB 접근·변경 없음. audit /home/kwl/.local/share/jusik/portfolio-audit/portfolio-expanded-universe-mandate-v1-1975c426b9e1436c979e5c4091bfa595.
- 검증 명령과 결과: focused pytest/Ruff/strict mypy 및 독립 review 예정. historical simulation0회, GPU0회, 주문0회.
- 검토 결과와 남은 문제: 진행 중. 기존 HANDOFF와 미병합3개 보존.
- handoff 저장 경로: 위 audit/HANDOFF.md.

- 실제 생성 기준: `8f1a4ec2b96c1a482889d7fb7d88106f084b365f`.
- 담당 및 결과: 단일 Luna code, 최종 `fc2f2034428f834cdff8c25e7c22725fe35fecab`; 독립 review 최종 승인, material finding 없음. 손상 mandate와 실제 proposal enqueue 차단 회귀를 보강한 뒤 통합했습니다.
- 병합 직전 main SHA: `8f1a4ec2b96c1a482889d7fb7d88106f084b365f`.
- 통합 커밋: `d112be8de6f6eb507689936223d6435335dc54ce`. main pytest60개, Ruff check/format, 변경 Python3파일 strict mypy(--follow-imports=silent), diff 통과. frontend 변경 없음.
- 산출물: exact mandate JSON/한국어 요약과 IVV·SGOV+현금 준비도·기존16종목 baseline 대비 A/B 사전등록. 투자기간 미정, 3년은 history만 유지합니다. 가격/action/FX/total-return adapter/실시간 데이터 gate는 미통과이며 simulation0회입니다.
- 게시: 한국어 보고서 API/웹 다운로드200·SHA bea534ed60019d57ba1d680b47161ee6ba2db5e6fc7d92ef8b71fe6d14a1836f 일치. 기존 이력71개·artifact117개와 DB 보존. mounted history root rename EBUSY를 파일 단위 원자적 게시로 복구했습니다.
- 보존·정리: audit에 원문·날짜·환경·패치·검사·검토·handoff와276개 파일의 SHA를 먼저 보존한 후 이번 worktree와 전용 브랜치를 정상 제거했습니다. 기존 미병합3개와 root HANDOFF는 보존했습니다. force/push/PAPER/GPU/실주문/생산 데이터 변경 없음.
- handoff: `/home/kwl/.local/share/jusik/portfolio-audit/portfolio-expanded-universe-mandate-v1-1975c426b9e1436c979e5c4091bfa595/HANDOFF.md`.
- 통합 검증 실패 없음. 초기 가상환경 준비 오류는 격리 Python3.13.15 환경으로 해결했고, 게시 복구 근거는 audit에 보존했습니다.

## runner-unlimited

- 상태: 완료
- 목표: 사용자 요청으로 일일 launch 제한을 명시적 null로 해제하고 기존 유한 설정·timeout·cooldown·lock·실패 격리를 보존합니다.
- 담당 Luna: native collector_transition, 단일 소유자.
- 워크트리: /home/kwl/projects/jusik-runner-unlimited
- 브랜치: feat/runner-unlimited
- 기준: d1d16dfff1e20ade26453fc949b285d53e961ae2; 이 등록 커밋에서 생성합니다. 통합 local main.
- 범위: backend/jusik/development_runner.py, 관련 tests, docs/development-runner.md. 설치 설정·웹 보고·인계·등록부는 감독 소유.
- 격리·근거: 자체 venv/tmp; /home/kwl/.local/share/jusik/portfolio-audit/20260913T004630Z-runner-unlimited.
- 검증·완료: quota초과에서도 unlimited dispatch, 유한quota/중복/cooldown/timeout보존, pytest/Ruff/strictmypy·독립검토·main통합·25건 초과 회귀 테스트와 실제 다음 dispatch 확인·웹·인계·worktree정리.

- 결과: worker380fb56·docs847d006, 구현통합 `617274dd2eb10402e5f9386c70bf37fffe4fdf14`. runner45tests/Ruffcheck·format/strictmypy 통과. 독립검토 P1/P2 없음. 설치daily_launches=null, 다른설정·launchhistory보존.
- 보존·정리: `/home/kwl/.local/share/jusik/portfolio-audit/20260913T004630Z-runner-unlimited`에 archive/checks/설치·연구근거·웹보고서·HANDOFF 저장. 이번worktree/branch정리, 기존미병합3개보존. 실제자동개발기동은 activation.json 확인.

## portfolio-gpu-allocation-screen-42b4

- 상태: 완료 (입력 gate 차단을 문서화한 기술 slice; 배분 연구 자체는 차단 유지)
- 목표와 완료 조건: 고정 입력의 누락 근거를 한국어 보고서로 작성하고 검토·main 통합·웹 게시·handoff로 보존한다. 성능 결과를 만들지 않는다.
- 담당 Luna: code 단일 문서 구현자, explore/plan 완료.
- 워크트리 절대 경로: /home/kwl/projects/jusik-portfolio-gpu-allocation-screen-42b4
- 작업 브랜치: docs/portfolio-gpu-allocation-screen-42b4
- 기준 커밋 SHA: 9945be5d3c8c60c618857b34adb931f0b7e38e1e 이후 이 등록 커밋
- 통합 대상 브랜치: local main
- 입력과 선행 작업: expanded mandate 완료; readiness false. audit/input-manifest.json에 보고서·소스 SHA 고정. 현재 runner attempt 내부 작업.
- 수정 허용 범위: docs/research-portfolio-gpu-allocation-screen.md만. 등록부·audit·게시·handoff는 Astra 소유.
- 포트·테스트 DB·출력 경로: 서버/DB/venv 불필요. audit /home/kwl/.local/share/jusik/portfolio-audit/portfolio-gpu-allocation-screen-v1-42b4b5646fe3467394bd0b37d46eac99
- 검증 명령과 결과: 문서 diff·입력 SHA 9개·독립 review·`git diff --check` 통과. 금융 acceptance tests와 allocation 실행은 입력 부재로 의도적으로 blocked.
- 결과 커밋 SHA·통합 검증·정리: 문서 커밋 `74bcd58`, main 통합 `44f1ff1`. local backend API와 artifact download HTTP 200/SHA 일치 확인. 성과 catalog는 변경하지 않았습니다.
- 게시: history artifact `d43273c15681d0ec8e198fc339a5818ec65f41d062c24f98adf6b0bd9e9e9d43`; 기존 84개 entry·132개 artifact 보존. 기본 history 첫 페이지는 feed pagination으로 해당 entry를 포함하지 않을 수 있으나 API limit100과 직접 artifact 경로에서 확인했습니다.
- 개발 기록: `docs/development-records/2026-09-19-portfolio-gpu-allocation-screen.md`.
- handoff 저장 경로: `/home/kwl/.local/share/jusik/portfolio-audit/portfolio-gpu-allocation-screen-v1-42b4b5646fe3467394bd0b37d46eac99/HANDOFF.md`.
- 정리: audit·handoff 확인 후 `/home/kwl/projects/jusik-portfolio-gpu-allocation-screen-42b4` worktree를 정상 제거합니다.

## portfolio-low-cash

- 상태: 완료
- 목표와 완료 조건: 3년 핵심 종목 자료에서 현금 비중과 거래 빈도를 함께 줄이는 32개 설정을 사전 등록하고 실제 비교, 위험 검증, 웹 보고를 완료한다.
- 담당 Luna: CLI gpt-5.6-luna 단일 구현자. 내장 작업자 스레드 한도로 전용 CLI 세션을 사용했으며 조사·계획·독립 검토를 수행했습니다.
- 워크트리 절대 경로: /home/kwl/projects/jusik-portfolio-low-cash
- 작업 브랜치: feat/portfolio-low-cash
- 기준 커밋 SHA: deab5b2 (등록과 최신 mandate 포함)
- 통합 대상 브랜치: local main
- 입력과 선행 작업: 현재 research-mandate, core 10종목 고정 입력. 신규 ETF 수집은 선행 조건에서 제외한다.
- 수정 허용 범위: 신규 low_cash_experiment 모듈, 대응 테스트, 연구 문서. 기존 engine/PAPER 설정 변경 없음.
- 포트·테스트 DB·출력 경로: 워크트리 자체 가상환경과 임시 테스트 경로. 실제 연구는 별도 audit/experiment.
- 검증 명령과 결과: 관련 통합 pytest 51개, Ruff check/format, 범위를 지정한 strict mypy 통과. 독립 검토의 중요한 지적을 같은 Luna가 수정했습니다. 실제 142회 비교 및 원본 140쌍 독립 산술 검증을 완료했습니다.
- 결과 커밋 SHA·통합 검증·정리: 구현 b7bbb48, 수정 6f22d31·be9227f. 병합 직전 main 5da867e, 통합 60e443c2eba6da6e616b6f0ce4ecfa95b0afcf97. 증거와 환경을 audit에 보존하고 해당 워크트리·브랜치를 정리했습니다. 기존 미병합 워크트리 4개는 보존합니다.
- handoff 저장 경로: /home/kwl/.local/share/jusik/portfolio-audit/20260913T011304Z-low-cash-low-turnover/HANDOFF.md
- 결과: 비용 1배의 연속 3년 비교에서 후보 A 수익률 118.94%, 현금 중앙 비중 41.66%, 거래일 33일, 최대 낙폭 14.96%입니다. 기준은 각각 43.18%, 79.80%, 71일, 6.53%입니다. 거래 빈도는 줄었지만 거래금액 회전율과 비용은 증가했습니다. 두 후보 모두 이번 평가의 전역 낙폭·실제 레버리지 기준을 통과했으며 PAPER 반영은 하지 않았습니다.
- 웹 산출물: `/research/history/download/aceef65a6cf64ac8afddfcc0226827ce3146100651706f2e3cab010008dc70fd`. 기존 게시 이력을 보존하고 API·웹·두 다운로드의 SHA를 확인했습니다.
- 운영 상태: 자동 실행 재개 증거는 audit의 `activation.json`으로 확인합니다. 남은 현금 원인과 위험 추정 개선 작업을 큐에 추가하고 선택적 신규 ETF 수집은 해당 핵심 작업 뒤에 배치했습니다. 과거 중단된 allocation 시도와 미병합 문서는 변경하지 않았습니다.

## portfolio-blocked-research-repair-122f

- 상태: 준비
- 목표와 완료 조건: source_paths/input_paths 불일치와 최종 현금 변조 누락을 오프라인 어댑터·검증기로 복구하고 독립 검토, local main 통합 검사, 한국어 웹 보고 및 handoff를 완료한다.
- 담당 Luna: code 단일 구현자. explore와 plan은 읽기 전용으로 수행한다.
- 워크트리 절대 경로: /home/kwl/projects/jusik-blocked-research-repair-122f
- 작업 브랜치: fix/blocked-research-repair-122f
- 기준 커밋 SHA: 2c4e830 이후 이 등록 커밋. 통합 대상 local main.
- 입력: audit/portfolio-blocked-research-repair-v1-122f67291266410d8706be0ade14e940/input-manifest.json에 기존 감사 자료·실제 입력·보존 모듈 742개 파일을 변경 전에 고정했다.
- 수정 허용 범위: 신규 오프라인 repair adapter/validator, 관련 테스트, 한국어 사용 문서. 보존 연구 모듈은 정확한 SHA 확인 후 새로운 출력 경로의 복사본에만 수정한다.
- 제한: 한 차단 원인씩 순차 복구, 기존 산출물 검증만 수행하며 새 전략 simulation 0회. 기존 워크트리·과거 이력·PAPER·broker·GPU·서비스는 변경하지 않는다.
- 포트·테스트 DB·출력 경로: 자체 venv/tmp, 서버·DB 없음. 영구 audit /home/kwl/.local/share/jusik/portfolio-audit/portfolio-blocked-research-repair-v1-122f67291266410d8706be0ade14e940.
- 검증: 원래 KeyError와 현금 +1 KRW 허점 재현, 실제 자료 정상 통과 및 변조 거부, pytest/Ruff/strict mypy, 독립 review와 main 재검사.
- 종료 조건: 두 기술 gate의 재개 가능 범위와 남은 기존 테스트 의존성을 명시한다. 과거 blocked 시도를 재시도하거나 완료로 바꾸지 않는다.
- handoff 저장 경로: 위 audit/HANDOFF.md. 증거·SHA·handoff 보존 후에만 이번 워크트리를 정리한다.

- 상태: 완료 (요청한 기술결함 2건 수정; calendar 전체 연구는 추가 입력 의존성으로 보류)
- 실제 기준 커밋: `8a4e9aec075cd0e6b6f5804a0b611697127e2de5`. 단일 구현 워커에 `gpt-5.6-luna`를 지정했습니다.
- 결과 커밋: 코드 `871f85c961111c902904570f32420e1a4c1855a3`, 재개 조건 문서 `513122a18197738636489498487e38991815e1bb`. 독립 review 승인, 차단 지적 없음.
- 병합 직전 main: `8a4e9aec075cd0e6b6f5804a0b611697127e2de5`. 통합 커밋: `7bc7c5cb0d7eb17fda61d2fb8d95a90caa96190b`.
- 통합 검증: pytest63개, Ruff check/format, 신규 어댑터·테스트 strict mypy 통과. 생성한 복구 소스2개 strict mypy도 통과. 원본742파일 해시 보존 확인. frontend 변경 없어 build 대상 아님. dependency deprecation warning2건.
- 재현: cadence 원래 KeyError와 수정 metadata 확인. calendar 원래 정상·+1KRW 변조 잔차0, 수정 정상 잔차0 및 변조 거부. 새 simulation0회, 저장 simulation1개를 정상/변조·원본/수정 검증에 사용. 초기 AST·fixture preflight 실패는 ledger 실행 전이며 감사 자료에 보존.
- 재개 경계: cadence 경로 차단은 해소됐으나 기존 테스트 mypy4건은 별도 조건. calendar는 현금 검증 수정에도 기존 normalizer의 bars/adjustment_factors 불일치로 전체 재개 보류. 원본 generator와 normalizer의 결과가 저장 fixture와 완전히 같음을 확인해 현금 결함만 재현했으며 역직렬화 계약을 완화하지 않음.
- 웹: 기존 이력75개·artifact121개 보존. 보고서 SHA `2ce89353738be9f0a8983f7daf70f6feb4cb451276421acf151bfa7f404edebc`; API·웹·두 다운로드200 및 SHA 일치. DB 쓰기 없음.
- 증거·handoff: 위 영구 audit에 원본 복사본, 검증 로그, 생성 소스·diff, 입력 해시, 리뷰, 한국어 보고서·게시 확인, HANDOFF.md를 보존한다. 보존 후 이번 병합 워크트리와 브랜치만 정리한다. 기존 미병합4개와 root HANDOFF.md는 유지한다.
- 변경하지 않은 범위: 과거 blocked 이력·큐 재시도, frozen 엔진·PAPER10%·DB·브로커 실행·서비스·GPU·원격 push.
- 정리 완료: 영구 audit의51개 파일 SHA와 handoff를 검증한 후 이번 worktree·전용 branch를 정상 제거했다. 강제 삭제 없음. 기존4개 worktree와 root HANDOFF.md는 유지했다. 실제 정리 상태는 audit/cleanup.json에 기록한다.


## portfolio-residual-cash-abec

- 상태: 준비
- 목표와 완료 조건: 잔여 현금의 겹치는 원인을 진단하고 단일 제한 가설을 사전등록하여 최대 24회 정확 비교 또는 재현 가능한 부정 결과, 독립 검토, local main 검사, 한국어 웹 보고와 인계를 완료한다.
- 담당 Luna: code 단일 구현자. explore와 plan은 읽기 전용으로 완료했다.
- 워크트리 절대 경로: /home/kwl/projects/jusik-portfolio-residual-cash-abec
- 작업 브랜치: feat/portfolio-residual-cash-abec
- 기준 커밋 SHA: 등록 커밋 직후 SHA를 실제 생성 기준으로 기록한다.
- 통합 대상 브랜치: local main
- 입력: 검증된 low-cash audit의 source, request, 원본 엔진과 개발 구간 raw artifacts. results SHA 71c1e5efac632d6f934d5b411d5f217131d0eb635aae121e90aee0373963e445.
- 수정 허용 범위: 신규 residual_cash 모듈, 대응 테스트와 한국어 연구 문서만. 기존 engine/PAPER/DB/서비스/GPU/원격 변경 금지.
- 격리: 워크트리 자체 .venv; 출력은 /home/kwl/.local/share/jusik/portfolio-audit/portfolio-residual-cash-risk-proxy-v1-abecaf881ae842378d77d5a6838040ed. 포트/DB 없음.
- 검증: 입력·코드 SHA, 과거 가용 가격·FX, 미래 변조, 1KRW 회계 변조, 실제 종목·레버리지 비중, 원본/observer parity, 비용 1/2배, dev/final 분리와 finalist 사전 동결. pytest/Ruff/strict mypy 및 통합 후 재검사.
- 결과·검토·통합 SHA: 진행 후 기록한다.
- 보존: 위 audit에 증거·SHA·HANDOFF.md 보존 후 이번 병합 워크트리만 정상 제거한다. 기존 미병합 4개와 root HANDOFF.md는 유지한다.

- 상태: 통합 대기 (독립 검토 승인)
- 실제 기준 커밋: c9a00a4cb066865e95309de5610532dffb5ec94c. 단일 Luna 구현 워크트리에서 신규 모듈·테스트·문서 3개 파일만 변경했다.
- 결과 커밋: ce0fdbff9914df09d4b7697fcf25f07822f2b7c0. 독립 결과 검토는 audit/review/final-review.json에 저장했다.
- 유효 비교: 개발 8회와 초기 무효 8회, 총 16회. 최종 후보 없음, final/continuous 0회. H1은 현금 감소·순수익 증가·동일 거래일이나 dev1 실제 종목 비중 28.98%/28.40%로 탈락했다.
- 실행 보존: Decimal 끝자리 차이로 중단한 기준 원장 3개를 재검증해 재사용했다. target_weight와 band_skip.value에만 1e-38 허용, 실제 6개 차이 모두 1e-41. 기준 거래·현금·평가액·성과 지표는 보관본과 정확히 일치한다.
- 검증: 작업자 pytest11개·Ruff·strict mypy, 감사 fixture29개와 raw8개·112pins·원자료 회계·전체 관측 위험 독립 검토 통과. local main 검사는 병합 후 기록한다.

- 병합 직전 main: 3e88c352ab55d4ce5be1278ac1520b6b6b284515. 첫 통합: 67a8a81499a6c1f44cd4c501edf54fd4f463d445.
- 첫 통합 검사: pytest92개와 Ruff 통과. strict mypy에서 새 테스트의 _market_time helper 타입 주석 누락 1건이 발생해 정리를 보류하고 동일 Luna에 수정 요청했다. 실패 로그는 audit/integration/mypy-initial-failure.log로 보존한다.

- 통합 검증 복구: 동일 Luna의 타입 주석 수정 8ce05b5를 독립 검토 후 병합했다. 최종 코드 통합 99a7e8506cd6f379014ce2037f2753fdc4dfca23. 영향 테스트11개 재검사·명시적 strict mypy·Ruff·diff 검사 통과. 기존 통합 pytest92개 결과와 함께 보존한다.
- 웹 게시: 기존 이력76개·artifact122개 보존. 보고서 SHA9be03de33391eb2bb1546f26784c46c875785c4b115e0d313fe014090d78f529. API·웹·두 다운로드200과 본문 SHA 일치. DB 변경 없음.
- 보호 검증: 기존 코드·설정303파일과 입력audit333파일 모두 SHA 일치. 실험코드92모듈과 테스트·문서·환경·실패 및 원장 기록을 영구audit로 복사했다.
- 상태: 통합 검증·게시 완료, 영구handoff 및 SHA 확인 후 이번 worktree 정리 대기.

- 상태: 완료. 영구 증거420개와 정리 전 handoff SHA를 검증한 후 이번 worktree·브랜치를 강제 옵션 없이 제거했다. 정리 후 같은420파일이 모두 생존하고 해시가 일치함을 다시 확인했다. 기존 미병합4개와 root HANDOFF.md는 유지했다.
- 최종 handoff: /home/kwl/.local/share/jusik/portfolio-audit/portfolio-residual-cash-risk-proxy-v1-abecaf881ae842378d77d5a6838040ed/HANDOFF.md. 정리 증거는 같은 경로의 cleanup.json, 완료 근거는 archive-sha256.json과 completion.json이다.


## portfolio-expanded-collection-2ea6

- 상태: 완료 (수집·검토·통합 완료, 데이터 gate 8개 미통과로 실제 비교는 차단)
- 목표와 완료 조건: 기존 A/B 사전등록을 유지하고 공식 자료 수집·검증을 한 차례 수행하여 gate별 결손을 보고합니다. 독립 검토, 필요한 main 통합, 영구 evidence/handoff 보존과 정리를 완료합니다.
- 담당 Luna: 단일 gpt-5.6-luna code 작업자.
- 워크트리 절대 경로: /home/kwl/projects/jusik-portfolio-expanded-collection-2ea6
- 작업 브랜치: docs/portfolio-expanded-collection-2ea6
- 기준 커밋 SHA: 02d802e76a9f265e3a38b27de1ddedcb47b4be4c 이후 이 등록 커밋.
- 통합 대상 브랜치: local main
- 입력과 선행 작업: completion ac14fb4d2df2c1f9614136c14a3f2704ff3e634fdc9021e20327e814a70f07a2 및 모든 evidence/source 해시 검증 완료. explore 완료, bounded plan 후 배정.
- 수정 허용 범위: 수집 연구 스크립트와 관련 검사, 한국어 준비도 보고서만 허용합니다. 기존 전략/registry/mandate/PAPER 수정은 금지합니다.
- 포트·테스트 DB·출력 경로: 서버/DB 없음. 전용 venv/tmp 및 /home/kwl/.local/share/jusik/portfolio-audit/portfolio-expanded-universe-collection-gates-v1-2ea67734308a40eda685c1b0839576c6.
- 검증: 고정 입력 해시, 가격·배당·분할·FX·세금·캘린더·venue·coverage gate, 관련 pytest/Ruff/strict typing, 독립 검토.
- 제한: 수집 한 차례, simulation/sweep/GPU/주문/remote push 없음. 원천 또는 entitlement 결손 시 비교를 차단합니다. 기존 HANDOFF와 다른 worktree를 보존합니다.
- 결과 커밋/통합/정리/handoff: 진행 후 기록합니다.

- 담당 결과: Luna `cfc751dc5e3f9484ae9c5b019e78d4d4c435cc78`, Astra 독립 review 승인 후 통합했습니다.
- 병합 직전 main: `2c059be53d92a0b51d177a5606a4602e24d75185`; 통합: `c7dcd0d888243287cec6bd1c904923ff86aa8b37`.
- 검증 결과: main pytest42개·offline 실패 회귀5개·Ruff·strict mypy3개 스크립트·diff 통과. 기존 dependency 경고2개.
- 수집 결과: 공식 HTTP10회, IVV 배당12건·SGOV36건 검증. 가격 추출0건, FX 빈 응답, calendar302. baseline 기업행동/IPO·split completeness·세금·venue 미확인으로 모든 데이터 gate 차단, 비교/simulation0회.
- 검토 수정: 배열 길이·실제 오류 기반 pass 판정, raw hash 실패 종료, 가격 결손 범위·mandate 구분을 수정했습니다. 최초 수집기 source hash 누락은 null로 공개했습니다.
- 게시: 연구 이력 파일 게시, API/웹200·SHA 일치. 기존 항목77개·artifact123개 보존. DB·서비스 변경 없음.
- 보존·정리: audit에 handoff 포함303개 파일의 SHA를 검증한 뒤 이번 worktree와 전용 브랜치를 정상 제거했습니다. 기존 worktree와 root HANDOFF 보존.
- handoff: `/home/kwl/.local/share/jusik/portfolio-audit/portfolio-expanded-universe-collection-gates-v1-2ea67734308a40eda685c1b0839576c6/HANDOFF.md`.
- 통합 검증 실패 없음. completion은 자료 결손으로 blocked, comparison followup은 null입니다.

## portfolio-gross-cap-2643

- 상태: 완료
- 목표와 완료 조건: gross .60/.80 고정 민감도, 대조군16 exact replay 후 신규16. CPU32회/19.058726초, 재시도0, GPU0으로 완료했습니다.
- 담당 Luna: code 작업자1명, 조사·계획·독립 검토는 별도 읽기 전용 작업자.
- 워크트리 절대 경로: /home/kwl/projects/jusik-portfolio-gross-cap-2643 (증거·SHA·handoff 보존 후 제거)
- 작업 브랜치: feat/portfolio-gross-cap-2643 (병합 확인 후 제거)
- 기준 커밋 SHA: c77a186 (작업 등록 포함)
- 통합 대상 브랜치: local main
- 입력과 선행 작업: cost3 f9aecd54 experiment, 최신 mandate; 원천·engine/helper/manifest/mandate69개 SHA 일치. 기존16종목 실제 coverage 및 eligibility 고정.
- 수정 허용 범위: 신규 gross-cap 연구 runner, 해당 테스트, docs/research/portfolio-gross-cap-cash-sensitivity-v1.md. 기존 backend source93개 불변.
- 포트·테스트 DB·출력 경로: 서버/DB 없음. 독립 worktree venv/tmp. 영구 audit /home/kwl/.local/share/jusik/portfolio-audit/portfolio-gross-cap-cash-sensitivity-v1-2643020d4e374d5699187071f552d34d.
- 실행기 확인: task/attempt portfolio-gross-cap-cash-sensitivity-v1 / 2643020d4e374d5699187071f552d34d. dispatcher 상태 변경 없음. 기존 HANDOFF.md와 다른4개 worktree 보존.
- 검증 명령과 결과: worker 최종60pytest/Ruffcheck·format/strictmypy2파일 통과(전체 타입 무시 제거). main 통합86pytest/Ruffcheck·format/strictmypy2파일 통과. 독립 raw32·대조군 JSON16·manifest72 SHA 통과. raw 금액 최대잔차3.21875e-31 KRW.
- 결과 커밋 SHA: e2eb919d57adbf8b6c6a08333145c5b46c01ad43
- 검토 결과와 남은 문제: 최종 독립 review 통과. Historical PIT·배당·receipt·early-close 한계 유지, 추가 연구와 정책 승격 없음.
- 결과: continuous 평균 현금은 비용1x/3x에서 +0.044545/+0.010027 pp, 순수익 -0.314952/-0.100381 pp. MDD·비용은 소폭 감소, 거래수 동일. 현금 대기 감소를 확인하지 못한 결과로 종료했습니다. Fold와 continuous 분리. NVDA symbol cap 초과223 valuation 관측, gross/leveraged 초과0.
- 병합 직전 main SHA: c77a186
- 통합 커밋 SHA와 정리 여부: 6f9778508154488e5b46682ecde88f7f2ecc5787, main 검증과 archive-before-cleanup.json·handoff 보존 후 worktree/branch 제거.
- 통합 검증 실패 원인과 복구 결과: 통합 검사는 모두 통과. 초기 worker 잘못된 명령 경로 로그는 실패로 보존하고 올바른 경로에서 최종 검사했습니다. 게시 seed의 Pydantic timestamp 정규화는 원본 값으로 복구 후 기존 항목 보존을 검증했습니다.
- 게시: API/웹/다운로드200과 보고서SHA 일치. 기존 이력78개·artifact124개 원본 보존, DB 변경 없음.
- handoff 저장 경로와 갱신 여부: audit/handoff-before-cleanup.md 및 handoff-final.md, 영구 보존 완료.

## portfolio-volatility-5171

- 상태: 완료
- 목표와 완료 조건: volatility .10/.15, 고정 gross .60 CPU exact32회/900초; control16 JSON 일치 후 variant16, 독립 검토 및 local main 통합 검증.
- 담당 Luna: code 작업자 한 명.
- 워크트리 절대 경로: /home/kwl/projects/jusik-portfolio-volatility-5171
- 작업 브랜치: feat/portfolio-volatility-5171
- 기준 커밋 SHA: ae87254ea79c6944da2a422be2b5020eae3aa48e (등록 커밋에서 worktree 생성)
- 통합 대상 브랜치: local main
- 입력과 선행 작업: gross-cap 2643020d experiment 및 최신 mandate. 86개 SHA 검증 통과.
- 수정 허용 범위: 새 volatility 연구 runner/test/보고서만.
- 포트·테스트 DB·출력 경로: 서버/DB 없음. worktree 전용 venv/tmp; audit /home/kwl/.local/share/jusik/portfolio-audit/portfolio-volatility-target-cash-sensitivity-v1-51714e900b9b4cd3b94a4cf0f1aae2f4.
- 검증 명령과 결과: main pytest103개(기존 dependency 경고2개), Ruff check/format, strict mypy2파일, diff 통과. worker 전체112 및 최종 대상103개 통과.
- 결과 커밋: c6244b284d0278c5f548964a7fa708cf03cf48c2. 독립 실행 전 및 결과 review 통과.
- 병합 직전 main: 9498876485b01bd12d5a296e76c6a255cb7323e4. 통합 커밋: f38918d3db96b7a749be03ee5ac50d73dc85b9b0. 통합 실패 없음.
- 결과: control16 전체 JSON 일치 후 variant16, CPU exact32회/19.086222초/재시도0/GPU0. Continuous 현금7.641445/7.744083pp 감소, 순수익11.423940/9.100226pp 증가, MDD3.925490/4.147701pp·비용841623/2483668 KRW 증가. 거래수5/4회 감소, turnover 증가. 추가 탐색·승격 없음.
- 독립 검증: raw32 회계 최대잔차3.21875e-31 KRW, manifest72 SHA·observer MDD·paired delta 통과. 최대 MDD10.414050%, symbol 초과463 valuation, 최대MSFT3.131096pp; gross/leverage 초과0. Historical PIT/짧은 ETF 이력/배당·receipt·early-close 한계 유지.
- 검토·환경 보완: helper 중복 제거, gross metadata 및 pre/post SHA 기준·deadline 실패기록 보호 복원, 실제 mutation/휴장 영향 거래 회귀 추가. 초기 Python3.12/기준 venv 사용 로그는 보존했고 전용3.13에서 최종 검사. Worker의 초기 branch commit 재작성은 검토 기록에 남겼으며 이후 append-only 수정. Root main 이력 재작성 없음.
- 게시: API/웹/다운로드200, 보고서 SHA 일치. 기존 이력79개/artifact125개 보존. DB·서비스·remote 변경 없음.
- 보존·정리: 소스/로그/결과/handoff134파일 SHA 검증 후 이번 worktree·브랜치 정상 제거. 기존 backend93개/root HANDOFF/다른4개 worktree 보존.
- handoff: audit/handoff-before-cleanup.md 및 handoff-final.md. archive-before-cleanup.json 및 cleanup.json으로 보존·정리 확인.
- 실행기: 현재 task/attempt dispatch 내 작업이며 dispatcher 상태 변경 없음. 기존 HANDOFF 및 다른 worktree 보존.

## portfolio-volatility15-cadence-4c25

- 상태: 차단 — 이전 시도 중단. 후속 5270 시도에서 완료했으며 기존 worktree는 보존합니다.
- 목표와 완료 조건: target .15 고정 4/8주 CPU exact32회/900초 비교, control16 전체 JSON replay 후 variant16, 독립 회계 및 검토, local main 통합 검사와 handoff.
- 담당 Luna: code 작업자 한 명.
- 워크트리 절대 경로: /home/kwl/projects/jusik-portfolio-volatility15-cadence-4c25
- 작업 브랜치: feat/portfolio-volatility15-cadence-4c25
- 기준 커밋 SHA: f630332562a97b9dd916b03f9b4f65fcb401ed77 (등록 커밋에서 worktree 생성)
- 통합 대상 브랜치: local main
- 입력: volatility target 51714e90 experiment; evidence5/manifest72/source3 SHA 일치.
- 수정 허용 범위: 새 연구 runner/test/report. PAPER/제품/DB/설정/주문/remote/GPU 변경 금지.
- 격리: 전용 worktree venv/tmp, 서버/DB 없음. durable audit /home/kwl/.local/share/jusik/portfolio-audit/portfolio-volatility15-cadence-cost-tradeoff-v1-4c25334c49c2491b8e74d9e16d63dda2.
- 실행기: 해당 task/attempt dispatch 내 작업. dispatcher 상태 변경 없음. 기존 HANDOFF와 다른4개 worktree 보존.
- 검증과 결과: 실행 전.

## portfolio-volatility15-cadence-5270

- 상태: 완료
- 목표와 완료 조건: .15 고정 4/8주 CPU exact 32회/900초 비교, 대조군 16개 전체 JSON 일치 후 변형군 16개, 독립 회계·검토 및 local main 통합 검사 완료.
- 담당 Luna: code 한 명. Astra가 단 한 번의 historical 실행과 통합을 담당했습니다.
- 워크트리와 브랜치: /home/kwl/projects/jusik-portfolio-volatility15-cadence-5270, feat/portfolio-volatility15-cadence-5270. 통합 검증·영구 보존 후 정상 제거했습니다.
- 기준 커밋 SHA와 통합 대상: cdaa6f72f8ef6396246c3c616948dfd3d26eaf09, local main.
- 입력과 선행 작업: 선행 volatility-target variant_c1/c3 16개. 입력 SHA 80개 일치. 이전 시도 4c25의 중단 worktree 및 기존 다른 4개 worktree와 root HANDOFF를 보존했습니다.
- 수정 범위: 새 연구 runner/test/report 3개. PAPER/제품/DB/설정/주문/remote/GPU 변경 없음. 서버/DB 미사용, 전용 venv/tmp 사용.
- 결과: CPU exact32회/18.251010초/재시도0/GPU0. Control16 byte 및 전체 JSON 일치 후 variant16. Continuous 비용1/3배에서 현금+0.607432/+0.608667pp, 순수익-5.551477/-1.999894pp, MDD+5.315978/+5.088576pp, 거래수-134/-140, 총비용-1102154/-3081364 KRW. Fold14개와 continuous2개 분리, 재튜닝·승격 없음.
- 독립 검증: raw32 최대 회계잔차1.734375E-31 KRW. manifest72 SHA, runtime95 SHA, observer 현금/MDD/cap 재계산 통과. Symbol 초과351개는4주에만 관측,8주0; gross/leveraged0.
- 검증 명령과 결과: Astra 실행 전 및 통합 후 pytest99개, Ruff check/format, strict mypy 통과. 프런트엔드 코드 변경 없음. 최초 Astra 검사도구의 tmp 상위 폴더 누락은 수정 후 통과했고 실패 로그 보존.
- 검토: 독립 코드·수치·보고서 검토 통과. 초기 helper SHA 오타·preregistration·실패 중단/경계 테스트 누락은 실행 전에 같은 Luna가 수정했습니다. Historical 실패·재시도 없음.
- 작업자 최종 커밋: b165bbb2292c32f8c66fcae9c310cf1dfb634111. 병합 직전 main: cdaa6f72f8ef6396246c3c616948dfd3d26eaf09. 통합 커밋: 114232eadcc4cac4e66cf14c267f518acdcf4c2a.
- 게시: 기존 file history와 progress catalog에 보고서 및16개 비교를 추가했습니다. 기존 항목과 대표 비교 보존, API/웹/다운로드200 및 보고서 SHA 일치. DB·서비스 변경 없음.
- 영구 보존: /home/kwl/.local/share/jusik/portfolio-audit/portfolio-volatility15-cadence-cost-tradeoff-v1-527025c895ad4d54a9559469434162a8. 삭제 전147개 증거/SHA/handoff 검증, 삭제 후 전부 재검증 및 runtime95개 대체 영구 경로 검증.
- handoff: audit/handoff-before-cleanup.md와 audit/handoff-final.md. 실행기 dispatch 안에서 완료하며 dispatcher 상태는 변경하지 않았습니다.

## progress-api

- 상태: 완료
- 목표와 완료 조건: 자동 개발 상태·종료 조건·같은 조건의 성과 비교·남은 작업을 한눈에 확인하는 읽기 전용 웹 화면을 구현하고 실제 웹에서 검증합니다.
- 담당 Luna: 작업별 CLI Luna 한 명. 조사와 계획을 완료했습니다.
- 워크트리 절대 경로: /home/kwl/projects/jusik-progress-api
- 작업 브랜치: feat/progress-api
- 기준 커밋 SHA: e878263 이후 이 등록 커밋
- 통합 대상 브랜치: local main
- 입력과 선행 작업: 공통 API 계약 /tmp/jusik-progress-contract.md. 공개 비교 catalog는 감독이 실제 근거를 검증해 준비합니다.
- 수정 허용 범위: backend/jusik/research_progress.py, research_app.py 연결, 대응 테스트, docs/research-progress.md. 실행기·거래·원장 변경 없음.
- 포트·테스트 DB·출력 경로: 작업별 가상환경·의존성·임시 데이터·빌드. 실제 배포와 공개 catalog는 감독 소유.
- 검증 명령과 결과: main 관련 pytest 27개, Ruff check/format 및 strict mypy, frontend lint/typecheck/build 통과. 독립 검토 P1/P2 없음. 실제 데스크톱·모바일 표시, 10초 갱신, 보고서 3개 다운로드·SHA 일치 확인. 기존 환율/mandate 테스트 실패 2건은 별도 큐로 등록했습니다.
- 결과 커밋: a395ee3, a3b144b. 통합 커밋: f04d671. 검증·환경·diff·화면 자료를 audit에 보존한 후 이번 워크트리와 브랜치를 정상 제거했습니다. 기존 미완료 워크트리 5개는 보존합니다.
- 게시: /research/progress 및 /api/research/progress 실제 HTTP 200. 공개 catalog 3개 연구·8개 비교와 개발 이력 게시 완료. PAPER·실제 거래·remote 변경 없음.
- 통합 검증 실패: 최초 브라우저 실행은 libasound 부재로 실패하여 별도 임시 라이브러리를 사용했습니다. 표시값 절삭을 반영한 검증 후 통과했습니다.
- handoff: /home/kwl/.local/share/jusik/portfolio-audit/20260913T053914Z-progress-dashboard/HANDOFF.md

## progress-ui

- 상태: 완료
- 목표와 완료 조건: 자동 개발 상태·종료 조건·같은 조건의 성과 비교·남은 작업을 한눈에 확인하는 읽기 전용 웹 화면을 구현하고 실제 웹에서 검증합니다.
- 담당 Luna: 작업별 CLI Luna 한 명. 조사와 계획을 완료했습니다.
- 워크트리 절대 경로: /home/kwl/projects/jusik-progress-ui
- 작업 브랜치: feat/progress-ui
- 기준 커밋 SHA: e878263 이후 이 등록 커밋
- 통합 대상 브랜치: local main
- 입력과 선행 작업: 공통 API 계약 /tmp/jusik-progress-contract.md. 공개 비교 catalog는 감독이 실제 근거를 검증해 준비합니다.
- 수정 허용 범위: frontend/lib/research-progress.ts, app/research/progress/, CSS, research/history 진입 링크. 실행기·거래·원장 변경 없음.
- 포트·테스트 DB·출력 경로: 작업별 가상환경·의존성·임시 데이터·빌드. 실제 배포와 공개 catalog는 감독 소유.
- 검증 명령과 결과: main 관련 pytest 27개, Ruff check/format 및 strict mypy, frontend lint/typecheck/build 통과. 독립 검토 P1/P2 없음. 실제 데스크톱·모바일 표시, 10초 갱신, 보고서 3개 다운로드·SHA 일치 확인. 기존 환율/mandate 테스트 실패 2건은 별도 큐로 등록했습니다.
- 결과 커밋: 431ac8b, ef7e9b4, fb3989c. 통합 커밋: 7e8e498. 검증·환경·diff·화면 자료를 audit에 보존한 후 이번 워크트리와 브랜치를 정상 제거했습니다. 기존 미완료 워크트리 5개는 보존합니다.
- 게시: /research/progress 및 /api/research/progress 실제 HTTP 200. 공개 catalog 3개 연구·8개 비교와 개발 이력 게시 완료. PAPER·실제 거래·remote 변경 없음.
- 통합 검증 실패: 최초 브라우저 실행은 libasound 부재로 실패하여 별도 임시 라이브러리를 사용했습니다. 표시값 절삭을 반영한 검증 후 통과했습니다.
- handoff: /home/kwl/.local/share/jusik/portfolio-audit/20260913T053914Z-progress-dashboard/HANDOFF.md


## baseline-fx-mandate-test-repair-56e8

- 상태: 완료
- 목표와 완료 조건: 기존 mandate 기대값과 FX 날짜 fixture 실패 2개를 테스트 범위에서 수정합니다. 독립 검토, local main pytest·Ruff·mypy, 한국어 개발 이력과 handoff, 근거 보존 후 정리까지 수행합니다.
- 담당 Luna: 전용 Luna 구현 작업자 1명(/root/luna_fix). 읽기 전용 explore와 plan을 순서대로 완료했습니다.
- 워크트리 절대 경로: /home/kwl/projects/jusik-baseline-fx-mandate-56e8
- 작업 브랜치: fix/baseline-fx-mandate-56e8
- 기준 커밋 SHA: a42ab7db0a04110ae9a68dc049c03fe1252098f3
- 통합 대상 브랜치: local main
- 입력과 선행 작업: task baseline-fx-mandate-test-repair-v1, attempt 56e8f44c391947c7bc03f7a891c67f0a. 현재 main에서 지정 테스트 2개 실패를 재현했습니다. 이번 attempt만 running이며 실행기 상태는 변경하지 않습니다.
- 수정 허용 범위: backend/tests/test_development_runner_planning.py, backend/tests/test_fx_signals.py. 운영 코드와 research-mandate.json 변경은 필요하지 않습니다.
- 포트·테스트 DB·출력 경로: 서버와 운영 DB 미사용. 워크트리 자체 .venv와 pytest 임시 데이터 사용. 영구 audit: /home/kwl/.local/share/jusik/portfolio-audit/baseline-fx-mandate-test-repair-v1-56e8f44c391947c7bc03f7a891c67f0a.
- 검증 명령과 결과: 수정 전 지정 pytest 2개 실패. 수정 후 FX·runner·planning·FX provenance pytest, Ruff check/format, strict mypy를 실행합니다. ML·전략 실험·GPU·PAPER·실거래·서비스·원격 변경 없음.
- 검토 결과와 남은 문제: FX 5일 초과 자료 차단은 정상입니다. 테스트 UTC 시계 고정과 Decimal 양·음수·0 반올림, UTC 자정의 5일/6일 경계, mandate 현재 의미와 추가 필드 보존을 검증합니다.

- 결과 커밋 SHA: 634a238157b643fe0a38fa25a308e45533bc3009 및 검토 수정 4ad94d56fbbfd188a7101bd944d94c55b4f8bb42.
- 검토 결과: 독립 pytest 32개, 변경 테스트 strict mypy 및 Ruff 통과. 테스트 datetime override 반환형 오류 1건은 Self 반환으로 수정했습니다.
- 통합 검증: main 관련 pytest 95개, 백엔드 전체 Ruff check/format(160개), strict mypy jusik(96개) 및 변경 테스트(2개) 모두 통과했습니다.
- 환경 제한: 최초 시스템 Python 3.12 ensurepip 실패 후 전용 Python 3.13 환경을 생성했습니다. 기본 lock의 선택 torch 누락으로 전용 환경 전체 mypy만 실패했으나 관련 pytest 95개와 변경 테스트 mypy는 통과했고 기존 main 환경 전체 mypy도 통과했습니다. ML 설치나 전략 실험은 하지 않았습니다.
- 병합 직전 main SHA: a42ab7db0a04110ae9a68dc049c03fe1252098f3.
- 통합 커밋 SHA와 정리 여부: 84225358236dc30573a684ad30bb3dbf609322f9. 삭제 전에 영구 audit의 근거 42개·SHA·handoff를 검증하고 이번 워크트리와 병합 브랜치를 정상 제거했습니다. 삭제 후 42개 해시를 재검증했습니다. 기존 워크트리 5개는 보존했습니다.
- 게시: 한국어 개발 이력을 기존 file history에 추가했습니다. API·웹·보고서 다운로드 HTTP 200과 보고서 SHA를 검증했습니다. 기존 항목과 성과 catalog를 유지했으며 새 성과 수치는 없습니다.
- 통합 검증 실패 원인과 복구 결과: 통합 검증 실패 없음. 구현 단계 타입 오류 및 선택 의존성 제한은 위에 기록했습니다.
- handoff 저장 경로와 갱신 여부: /home/kwl/.local/share/jusik/portfolio-audit/baseline-fx-mandate-test-repair-v1-56e8f44c391947c7bc03f7a891c67f0a/HANDOFF.md. 삭제 전 handoff-before-cleanup.md도 별도로 보존합니다.


## portfolio-symbol-cap-episodes-0e01

- 상태: 완료 (최신 canonical mandate pin으로 재개한 retry)
- 목표와 완료 조건: 저장된 32개 셀의 symbol cap 초과 관측 351회를 종목별 episode로 재구성하고 같은 셀의 비용 반영 성과와 연결합니다. 입력 SHA 검증, 분석 1회와 결정성 재검산 1회, 독립 검토, local main 통합 검사와 영구 handoff를 완료합니다.
- 담당 Luna: 전용 Luna 구현 작업자 1명. explore 완료 후 plan을 진행합니다.
- 워크트리 절대 경로: /home/kwl/projects/jusik-portfolio-symbol-cap-episodes-20260919
- 작업 브랜치: feat/portfolio-symbol-cap-episodes-20260919
- 기준 커밋 SHA: b27126b40cfdadf9b52cc1bd3406bdefc684f7b8
- 통합 대상 브랜치: local main
- 입력과 선행 작업: task portfolio-symbol-cap-breach-episodes-v1, 이전 attempt 0e018f57a6b14e3587dc5dfca65985d8는 등록 mandate pin `197f8e09…`과 canonical SHA drift로 fail-closed 중단했습니다. retry는 현재 승인된 `docs/research-mandate.json` SHA `ceca2ee1d3e86cf79822b6b4a1606ac6699405f93eaf302fcf3842247f5de7ac`를 새 입력 identity로 고정하고, 기존 결과·manifest SHA 72개는 그대로 읽기 전용 검증합니다.
- 수정 허용 범위: 새 분석 모듈, 해당 fixture tests, 한국어 연구 보고서와 전용 audit. 감독만 이 등록부를 갱신합니다.
- 포트·테스트 DB·출력 경로: 포트와 DB 미사용. 워크트리 자체 Python 3.13 venv. 기존 audit `/home/kwl/.local/share/jusik/portfolio-audit/portfolio-symbol-cap-breach-episodes-v1-0e018f57a6b14e3587dc5dfca65985d8`를 보존하고 retry audit은 `/home/kwl/.local/share/jusik/portfolio-audit/portfolio-symbol-cap-episodes-v1-20260919`에 저장합니다.
- 검증 명령과 결과: 관련 pytest, Ruff check/format, strict mypy. 32셀 CPU 분석 1회와 결정성 재검산 1회 합계 900초 이내. Historical simulation·수집·GPU·후보 탐색 0회.
- 검토 결과와 남은 문제: 원본 배열 순서를 보존하며 동일 UTC 시각과 동일 값의 정상 반복도 유지합니다. 거래와 관측의 동일시각 선후 및 관측 사이 회복은 추정하지 않습니다. 기존 PAPER10%, 사용자 MDD20%·레버리지20%, 1억원·인출 없음과 짧은 이력/PIT 한계를 보존합니다.
- 결과 커밋: `220abd1288f069b947ed4246e672682109ce6bbf`, 고정 episode 계약 보완 `ab9eed58feadfdbd26a2bc3c6c4425a952c8c34d`; main 통합 커밋 `2b88c92`.
- 검증 결과: pytest 6개, Ruff check/format, strict mypy, fixed archive 재분석 및 결정성 replay SHA `34a9eeb0c8151067a8bb745f3be4f7f38f26c6f553b13e774417db8ddcf34320` 통과. 독립 review PASS.
- audit/handoff: `/home/kwl/.local/share/jusik/portfolio-audit/portfolio-symbol-cap-episodes-v1-20260919/HANDOFF.md` 및 `analysis-1/analysis.json`, `analysis-2/analysis.json`, `deterministic-replay.json` 보존.
- 워크트리 정리: audit·handoff 확인 후 `/home/kwl/projects/jusik-portfolio-symbol-cap-episodes-20260919`를 정상 제거했습니다. 이전 mandate mismatch worktree와 audit은 이력으로 보존합니다.

## investor-web

- 상태: 완료
- 목표와 완료 조건: 일반 투자자가 목표·현재 단계·성과 의미·한계·다음 판단을 이해하는 통일된 웹 여정을 구현합니다. 실제 브라우저와 독립 과제 검토 후 local main 통합·배포·handoff까지 완료합니다.
- 담당 Luna: frontend 구현 담당자 한 명. Astra는 설계 기준·통합·검증·배포 담당입니다.
- 워크트리 절대 경로: /home/kwl/projects/jusik-investor-web
- 작업 브랜치: feat/investor-web
- 기준 커밋 SHA: f981fa9
- 통합 대상 브랜치: local main
- 입력과 선행 작업: docs/investor-web-design.md, 기존 research progress API 및 연구 화면. explore와 plan 검토를 완료했습니다.
- 수정 허용 범위: frontend의 연구 홈·공통 탐색·성과/관찰/이력 설명·기존 연구 도구 이동·계좌 화면의 연구 안내. 전략·백엔드·주문·인증·공개 성과 수치 변경 없음.
- 포트·테스트 DB·출력 경로: 전용 node_modules 및 build, 임시 fixture 8311/프런트 3311. 운영 서버 변경은 Astra만 수행합니다.
- 검증 명령과 결과: main lint/typecheck/build, Decimal 비교 회귀 9건, 실제 8개 화면 HTTP 200·현재 메뉴 1개·desktop/mobile 가로 넘침 없음·키보드 본문 이동 통과. 실제 Next/브라우저에서 자료·운영 상태 6개 검증, 폼 8개·입력 필드 20개·서버 액션 보존 대조 통과. 독립 화면 과제 7개 확인; 실제 일반인 참가 시험은 수행하지 않았습니다.
- 결과 커밋: e7420ff, 24faf18, 976e58d, dfd09f6. 통합 커밋: 52cfb86 및 1f4f4be. 독립 검토 P1/P2 해소 후 통합, 실제 웹 배포 완료.
- 검토 및 복구: 초기 모바일 넘침, 후보 단독 수치, 공통 탐색 누락, 잘못된 상태 단정, 현재 메뉴 중복, 상세 링크 누락을 같은 Luna가 수정했습니다. 최초 실패와 최종 통과 근거를 audit에 보존했습니다.
- 정리: diff·환경·검증 스크립트·화면·인계 자료를 audit에 보존한 후 이번 워크트리와 브랜치를 정상 제거했습니다. 기존 6개 미완료 워크트리는 보존했습니다.
- 게시: /research를 시작점으로 웹 반영 및 개발 이력 게시 완료. 공개 성과 catalog SHA 불변, 계좌 조회·인증·거래 로직 변경 없음. 원격 push 없음.
- 운영: 사용자 요청으로 runner paused, service/timer inactive. 완료 후에도 자동 재개 금지. 기존 중단 작업과 6개 워크트리 보존.
- handoff: /home/kwl/.local/share/jusik/portfolio-audit/20260913T072036Z-investor-web-remake/HANDOFF.md


## research-ui-redesign

- 상태: 완료
- 목표와 완료 조건: research-ui-redesign.md의 사용자 요구를 바탕으로 전체 목표·운용 조건, 연구 질문·변경점·결론·결정, 별도 PAPER 관찰을 이해할 수 있게 화면을 재설계합니다. 기존 기능과 URL을 보존하고 독립 검토, 브라우저 검증, local main 통합 검사와 handoff까지 완료합니다.
- 담당 Luna: /root/luna_ui (gpt-5.6-luna), 구현 소유자 한 명. explore와 plan 완료.
- 워크트리 절대 경로: /home/kwl/projects/jusik-research-ui-redesign
- 작업 브랜치: feat/research-ui-redesign
- 기준 커밋 SHA: afc2eb4
- 통합 대상 브랜치: local main
- 입력과 선행 작업: docs/research-ui-redesign.md(사용자 미추적 원본 보존), 최신 mandate, 기존 화면/API/공개 연구 원문. 자동 실행기는 paused, service/timer inactive이며 중지를 유지합니다.
- 수정 허용 범위: frontend 연구 화면·표시용 데이터·CSS·관련 검사. 전략·주문·PAPER 정책·공개 성과 수치 변경 없음.
- 포트·테스트 DB·출력 경로: 전용 node_modules/build, frontend 3321 및 fixture 8321, 운영 DB 미사용. 영구 audit /home/kwl/.local/share/jusik/portfolio-audit/20260913-research-ui-redesign.
- 검증 명령과 결과: worker와 main의 lint/typecheck/build 통과. main 실제 Next 브라우저 44개 상태·화면 폭 검사, 비율 변환 12건·원본 식별 20건 통과. 배포된 8개 화면 HTTP 200, desktop/mobile 가로 넘침 없음, 공통 탐색·현재 메뉴·키보드 이동·JavaScript 오류 없음 확인. 기존 연구 도구 파일 9개와 공개 성과 catalog SHA 보존.
- 결과 커밋 SHA: 6aeff89, e891675. 초기 중간 커밋 cc3efff는 작업자가 정리했으며 최종 두 커밋을 통합했습니다. 감독 요청 후 후속 수정은 별도 커밋으로 보존했습니다.
- 검토 결과와 남은 문제: 독립 review의 관찰 검증 기간 누락, 낙폭 측정 기준 혼합, 고정 연구 수, 전체 기간 계산 오류와 브라우저 가로 넘침을 수정했습니다. 최종 독립 review 중요 지적 없음. 실제 일반인 참가 사용자 시험은 수행하지 않았습니다.
- 병합 직전 main SHA: 2ee48a8be641f92eacb68b664a547ae447de1402.
- 통합 커밋 SHA와 정리 여부: fbf97e01429e07e2d2ab5b77911864cd6c3f74ba. 웹 반영 및 통합 검증 후 audit 파일 123개 SHA를 확인하고 이번 워크트리와 병합 브랜치를 정상 제거했습니다. 기존 미완료 워크트리 6개 보존. 자동 실행기 paused, service/timer inactive 유지.
- 통합 검증 실패 원인과 복구 결과: main 통합 검사 실패 없음. 초기 개발본의 모바일·비교 상세 넘침과 정보 표시 오류는 독립 리뷰 후 수정했습니다. 브라우저 실행에 필요한 기존 공유 라이브러리를 LD_LIBRARY_PATH로 지정했으며 새 시스템 패키지는 설치하지 않았습니다.
- handoff 저장 경로와 갱신 여부: /home/kwl/.local/share/jusik/portfolio-audit/20260913-research-ui-redesign/HANDOFF.md. 루트 HANDOFF.md에 최신 안내를 추가하며 기존 내용과 미추적 요구사항 원본을 보존합니다.


## open-ended-decision-study

- 상태: 완료
- 목표와 완료 조건: 종료 시점 없는 계속 운용과 실제 비교 후 사용자 선택이라는 최신 의사를 기록하고, 고정된 4주 대 8주 연구 32개 결과를 재분석해 선택 근거를 제공합니다. PAPER 준비와 미완료 7건을 읽기 전용 점검하고 연구 한 건 후 중지합니다.
- 담당 Luna: /root/luna_decision (gpt-5.6-luna), 구현 소유자 1명. explore·plan·구현·독립 review 완료.
- 워크트리 절대 경로: /home/kwl/projects/jusik-open-ended-decision-study
- 작업 브랜치: feat/open-ended-decision-study
- 기준 커밋 SHA: ed2ae9afff0e60dd59bef8d33d715e087997fb39 이후 이 등록 커밋
- 통합 대상 브랜치: local main
- 입력과 선행 작업: 사용자 1-D 및 2-C 선택. 고정 volatility15-cadence 5270 결과와 manifest. 실제 경계 capture monitor running, 두 경계 scheduled 및 코드 hash 일치. runner paused와 service/timer inactive.
- 수정 허용 범위: 최신 mandate JSON·한국어 안내·해당 테스트, 웹의 현재 조건 표시, 단일 재분석 보고서 및 전용 audit. 전략·PAPER·운영 DB·runner 큐 변경 없음. 감독만 등록부와 공개 catalog를 관리합니다.
- 포트·테스트 DB·출력 경로: 전용 Python 3.13 venv와 node_modules/build. 필요시 웹 3331. 운영 DB 읽기 전용, 영구 audit /home/kwl/.local/share/jusik/portfolio-audit/20260913-open-ended-decision-study.
- 검증 명령과 결과: 관련 pytest·Ruff·strict mypy, frontend lint·typecheck·build, Decimal 재분석과 독립 검증, 원본 SHA·기존 catalog 보존.
- 종료 조건: 32개 저장 셀과 16개 쌍만 분석·재검산하며 historical simulation·새 후보·GPU 실행 0회. local main 통합 검사, 한국어 보고서·같은 조건 catalog 게시, handoff·이번 worktree 정리 후 중지합니다.
- 남은 문제: 일부 원자료의 짧은 이력·PIT·배당·세금 한계를 유지합니다. 실거래나 기존 PAPER 정책에 후보를 채택하지 않습니다.
- 결과 커밋 SHA: a44d402b8c7570c8e48601b86f3f6bbb4c7c42b9, 360cec03be18eb7d3d2ad68bbbf667e18587d094.
- 병합 직전 main SHA: 532450a. 통합 커밋 SHA: 7ed18c1af7919925d06176adad9e330eb66d8ebf.
- 검증 결과: worker와 main pytest 52개, 관련 Ruff·strict mypy 및 frontend lint·typecheck·build 통과. 원본 SHA 72개·raw 32셀·paired 16쌍·catalog 32개 수치 행 독립 검산 통과. 실제 브라우저 2개 화면×2개 너비, 다운로드 2개 SHA·API·PAPER raw collector 실행과 예약 확인.
- 검토와 복구: 공개 중단 후 재실행 불가와 오래된 보고서 sourceReference를 수정했습니다. 임시 공개 디렉터리에서 실패 주입·복구·완료 후 동일 재실행을 확인했고 독립 재검토 추가 P1/P2 없음. 초기 브라우저 검사 selector의 study 접두사를 실제 DOM에 맞춰 고친 뒤 4개 화면 검사가 통과했습니다.
- 게시: cadence-decision-20260913 신규 study·16개 비교와 한국어 보고서 공개. 기존 study 4개 및 featured 비교 보존. runner 전체 snapshot·기존 7건 상태 불변, paused와 service/timer inactive 유지. 웹은 실행 중입니다.
- handoff: /home/kwl/.local/share/jusik/portfolio-audit/20260913-open-ended-decision-study/HANDOFF.md. 기존 6개 미완료 워크트리 및 이번 작업 중 별도 등록된 jusik-agent-tooling 워크트리는 이번 정리 대상에서 제외합니다.
- 정리: 검증·구현 diff·환경 정보·보고서 등 audit 41개 파일의 SHA를 확인한 뒤 이번 워크트리와 병합 브랜치를 정상 제거했습니다. 다른 작업의 등록 내용과 워크트리는 보존했습니다.

## portfolio-kofr-offline-verification-v1

- 현재 재시도: 차단. `4f728844d75b4f829cf64277d6144aab`, Luna `kofr_verify` 단일 검증 담당. 기존 소유 branch/worktree/환경을 재사용하고 입력 SHA를 확인했습니다. 새 audit은 `/home/kwl/.local/share/jusik/portfolio-audit/kofr-offline-4f728844`이며 후보 코드 수정·병합은 하지 않습니다. 아래 이전 차단 기록은 역사 상태로 보존합니다. pytest20 통과 보고 후 Ruff52건 실패, format/mypy 미실행이며 code routing receipt gate도 실패했습니다. 최종 독립 검토와 보충은 새 audit에 보존합니다.

- 상태: 차단. attempt `7b509bb93dcb4e02bbaf6c163f889a8d`. pytest import에서 `py` 의존성 누락으로 실패해 본문·Ruff·mypy는 미실행입니다. code routing post도 transport mode 불일치로 실패했습니다.
- 범위: 후보 `3fcb553a22ba652071503bead96cf43425118a78`의 두 파일 SHA를 고정한 오프라인 검사만 수행합니다. collector 수정·병합과 공식 재요청은 금지합니다.
- 담당: Astra 감독·계획, Luna 단일 검증 담당, Terra 독립 검토 미통과(보고서 근거 누락 지적).
- 워크트리/브랜치: 기존 `/home/kwl/projects/jusik-kofr-risk-free-source-evidence`, `feat/kofr-risk-free-source-evidence`를 검사에 재사용합니다. 새 워크트리는 만들지 않습니다.
- 증거/계획: `/home/kwl/.local/share/jusik/portfolio-audit/kofr-offline-7b509bb9/PLAN.md`, `inputs.json`.
- 완료 조건: fake transport·네트워크 차단·단일 CPU·seed 0으로 지정 pytest, Ruff check/format, configured strict mypy 및 독립 검토 통과. 실패 시 후보를 그대로 보존하고 원인과 재개 조건을 기록합니다.
- 예산: 환경 포함 900초, 신규 환경/cache 1GiB, 보고 artifact 50MiB. 금융 실험·수집·GPU 0회.
- 금융 상태: 공식 성공 raw/evidence 부재, 금융/data acceptance 차단, PAPER 10%를 유지합니다. 웹 publication은 성과 수치가 없어 해당 없습니다.
- 개발 기록: `docs/development-records/2026-09-18-portfolio-kofr-offline-verification-v1.md`. 검사 통과·collector 병합·기술 완료를 주장하지 않습니다. 재개 시 소유 환경 의존성과 routing mode를 확인하고 전체 검사와 독립 검토가 필요합니다.


## portfolio-kofr-offline-quality-repair-v1

- 상태: 예산 초과로 차단. attempt `65f6765444cd46c3866ae6c2eaa4dca2`. 입력 identity와 SHA 검증을 통과했습니다.
- 목표: 기존 후보 두 파일의 Ruff/format/strict mypy 결함을 오프라인으로 수정하고 계약 보존을 검증합니다.
- 담당: Astra 감독·계획, Luna 단일 구현, Terra 독립 검토 PASS.
- 소유 워크트리/브랜치: `/home/kwl/projects/jusik-kofr-risk-free-source-evidence`, `feat/kofr-risk-free-source-evidence` 재사용. 기준 `3fcb553a22ba652071503bead96cf43425118a78`.
- 범위: `backend/jusik/kofr_source_evidence.py`, `backend/tests/test_kofr_source_evidence.py`만 수정합니다. collector main 병합은 금지하며 기록만 main에 반영합니다.
- 검증: 네트워크 namespace 차단과 fake transport, 단일 CPU·seed 0으로 pytest/Ruff check·format/configured strict mypy를 실행하고 원문 출력·exit code·SHA를 저장합니다.
- 예산: 누적 wall time 900초, 환경/cache 증가 1GiB, 신규 audit 50MiB. 금융 실험·network·GPU·PAPER/DB/service/config/remote/주문 변경 0.
- 증거: `/home/kwl/.local/share/jusik/portfolio-audit/kofr-quality-65f67654`. 과거 실패·위반·review 미통과와 금융/data acceptance 차단, PAPER10%를 유지합니다.

- 결과: 후보 `a7c283603415d57da93ff95ac62e96f23da67002`, pytest21/Ruff check·format/configured strict mypy PASS, routing4단계 PASS. collector 미병합·소유 worktree 보존.
- 기록: `docs/development-records/2026-09-18-portfolio-kofr-offline-quality-repair-v1.md`; audit `HANDOFF.md`, `integration-verification.json`, `evidence-manifest.json`.

최종 정정: 검사와 독립 검토는 통과했으나 최종 기록 단계의 누적 실측이 917.630초로 900초를 초과했습니다. 기술 slice 완료를 철회하고 차단으로 기록합니다. 자동 복구 대상이 아니며 새 예산의 명시적 재시도에서 지정 검사·독립 검토·identity gate를 다시 통과해야 합니다. 초과 이후에는 이 차단 정정과 증거 보존만 수행했습니다.

## r6-krx-smoke

- 상태: 차단. KRX 공식 읽기 응답의 무거래 0값 경계를 보완하고 1년 bounded collection을 완료했습니다.
- 변경: `backend/jusik/market_data_collector.py`와 회귀 테스트에서 `-`/0 OHLC·거래량 행은 membership만 보존하고 bar를 만들지 않습니다. 알 수 없는 값은 계속 fail-closed입니다.
- 수집: 2025-09-11~2026-09-11, request budget 532, cache 534건, excluded 0. KRX 단일 응답 960행 중 31행이 0값 무거래였으며 수정 후 929개 bar가 생성됐습니다.
- 동일 cache와 prepared output 경로의 `collect-status`는 `completed=true`, `ready=true`, credentials missing 없음(exit 0)으로 확인했습니다. marker output 경로가 다르면 identity 불일치로 false가 됩니다.
- 파일럿: approximate pilot은 `insufficient/incomplete`, `readiness.ready=false`, trades/equity/metrics 0입니다. PIT 기업행사·배당·상폐·관측 시각 근거가 없어 경제 성과·strict/PAPER 승격을 금지합니다.
- 개발 기록: `docs/development-records/2026-09-19-r6-krx-smoke.md`; audit `/home/kwl/.local/share/jusik/portfolio-audit/20260919-r6-krx-smoke`.
- 검증: `backend/.venv/bin/python -m pytest -q backend/tests/test_market_data_collector.py` — 129 passed. 실주문·브로커 API·PAPER 설정·운영 DB·원격 push 없음.

## timestamp-provenance-path-fix

- 상태: 완료. sanitized provenance의 `source/jusik/...` 경로를 승인 hash 대사에 정확히 연결했습니다.
- 변경: `research_signal_timestamp_forensics.py`가 마지막 `jusik/` 기준으로 경로를 잘못 정규화하던 문제를 `source/jusik` 쌍 기준으로 고쳤습니다. 다른 경로 형식은 계속 fail-closed입니다.
- 검증: timestamp forensics pytest 8개, Ruff check/format 통과. 현재 달력 source hash가 과거 frozen archive 승인 hash와 달라 외부 replay 실패는 의도적으로 유지됩니다.
- 개발 기록: `docs/development-records/2026-09-19-timestamp-provenance-path-fix.md`.

## sec-filing-candidate-parser-20260920

- 상태: 기술 slice 완료; 경제 acceptance/R1 승격 없음.
- 범위: `backend/jusik/research_sec_evidence.py`의 SEC primary document URL 재현과
  본문 키워드 후보 파싱, 관련 회귀 테스트.
- 정책: 후보는 `candidate/incomplete`로만 보존하며 권리·가격·effective/payment date를
  확정하지 않습니다. 원격 push, 주문, PAPER/live 설정 변경은 없습니다.
- 검증: SEC 관련 pytest 4개와 Ruff 통과. 전체 backend pytest는 기존 archive/hash 및
  상태 기대치 불일치 7건으로 실패(1615 passed, 7 failed)했으며 별도 기록했습니다.
- 다음: bounded document fetch와 수동 검토 가능한 후보 audit을 추가하되, 승격 조건과
  PIT 경계를 먼저 고정합니다.

- 후속 bounded fetch: 2024–2025의 8-K/8-K/A 문서 3건을 fetch해 raw HTML·summary·request
  SHA를 `/home/kwl/.local/share/jusik/portfolio-audit/20260920-sec-filing-candidates/`에
  보존했습니다. merger 후보 1건과 빈 후보 2건이며, 문맥 snippet도 저장했지만 XBRL
  false positive 가능성이 있어 경제 acceptance에는 반영하지 않았습니다.
- 승격 경계: SEC 후보를 별도 ledger 경로로 승격하지 않고 기존
  `research_action_review.py`의 `ReviewInput`/`ExtractedFacts`/`ActionReview` 계약을
  통과시키는 후속 작업으로 고정합니다. 자동 원장 적용은 계속 금지합니다.
- adapter `build_sec_action_review_input()`은 operator verification·수동 facts·단일
  split/dividend를 강제하며, merger/미검증 후보를 fail-closed로 거부합니다. 관련
  pytest 14개와 Ruff가 통과했습니다.
- 실제 facts를 추정하지 않고 `review-queue.json`을 생성했습니다. 3건 모두 promotion
  금지 상태이며, 수동 필드가 채워지기 전에는 review manifest·원장·성과 계산으로
  전달하지 않습니다.
- `build_sec_review_manifest()`는 모든 accession에 raw 경로와 수동 facts가 있어야만
  manifest를 생성합니다. 관련 SEC/action-review pytest는 15개로 늘었고 통과했습니다.
- store 계약 검토 후 collection revision/content SHA 매핑을 필수화했습니다. SEC raw SHA는
  evidence 식별자이며 collection revision으로 사용하지 않습니다.

## public-evidence-catalog-unresolved-identity-20260920

- 상태: 기술 slice 완료; `coverage=incomplete`, 경제 acceptance 미승격.
- `PublicEvidenceCatalog.unresolved_symbols`로 requested universe의 SEC CIK mapping 누락을
  catalog에 보존했습니다. v2 audit에서 `SOXL`/`TQQQ`를 기록했으며 catalog SHA는
  `10b6edc5d34c3b2dd0802a0fb77238debc2c3a61fdeeafc1790dcb86916a800f`입니다.
- 검증: catalog/SEC pytest 7개와 Ruff 통과.

## r2-independent-accounting-verification-20260920

- 상태: 기술 계약 재검증 완료; 경제 평가는 `not-evaluated`, R2 전체 미완료.
- 기존 독립 accounting/NAV 및 corporate-action 전이와 mandate governance 테스트 58개를
  2026-09-20 재실행해 통과했습니다.
- 완전한 fills/opening positions/terminal marks/dividend evidence가 없어 PnL 승격은 금지하고,
  기존 R2-01 blocked audit을 유지합니다.

## r2-counterfactual-reverification-20260920

- 상태: 기술 계약 재검증 완료; 실제 자료 acceptance와 경제 평가는 `not-evaluated`.
- counterfactual/independent accounting pytest 45개 통과. scenario별 cost·dividend·FX를
  분리 보존하고 unavailable을 0으로 바꾸지 않는 계약을 재확인했습니다.
- 2026-09-20 재실행 명령도 동일하게 `45 passed`를 확인했습니다.
- complete fills/corporate-action evidence 부재로 R2-06과 R4 승격은 하지 않습니다.

## r2-fx-boundary-verification-20260920

- 상태: 기술 계약 재검증 완료; 경제 평가는 `not-evaluated`.
- accounting evidence/FX provenance/FX signal 테스트 46개 통과. USD/KRW as-of, stale/future
  거부, Decimal 반올림 경계를 확인했습니다.
- 실제 historical FX coverage와 거래 timestamp가 부족해 R2-03 경제 승격은 하지 않습니다.
- ALFRED 주간 vintage 251개도 관측일 이전 availability가 `0/251`이고 first-seen
  upper-bound lag가 7~11일이어서 PIT FX 적용 근거로 승격하지 않습니다.

## r2-dd-chronology-verification-20260920

- 상태: 기술 계약 재검증 완료; 경제 평가는 `not-evaluated`.
- drawdown chronology/underwater-duration 테스트 28개 통과. 초기 자본 고점, DD latch,
  시간순 매수 차단과 malformed chronology 거부를 확인했습니다.
- 관련 underwater-duration/session-calendar stress 전체 회귀를 2026-09-20 재실행해
  `40 passed`(경고 2건)를 확인했습니다.
- complete fills/opening positions와 미래 검증 자료 부족으로 R2-04 및 PAPER 승격은 하지 않습니다.

## r3-market-curve-contract-verification-20260920

- 상태: 기술 계약 재검증 완료; benchmark/USD 자료 부재로 R3-01 경제 승격 보류.
- 시장 결과 화면의 KRW NAV/DD 곡선과 USD/KRW·benchmark 확인 불가 상태를 frontend contract,
  ESLint, TypeScript typecheck, production build로 검증했습니다.
- backend metrics/readiness/NAV reconciliation 회귀를 2026-09-20 재실행해 `88 passed`를
  확인했습니다. unavailable risk-free·FX·benchmark를 0으로 대체하지 않는 경계를 유지합니다.

## r4-readiness-gate-verification-20260920

- 상태: 기술 gate 재검증 완료; 실제 pilot/경제 평가는 실행하지 않음.
- readiness/외부 자료/근사 시장 이력 테스트 90개 통과. strict·approximate grade,
  provenance·coverage·future/FX 누락을 분리하고 approximate→strict 승격을 차단함을 확인했습니다.
- performance/readiness/prospective registration·readiness 묶음도 `88 passed`(경고 2건)로 재검증했습니다.

## r5-preregistration-verification-20260920

- 상태: 기술 계약 검증 완료; 경제 성과·R5 승격은 자료 gate 뒤로 유지.
- 최초 2개 fixture drift를 교정한 뒤 optimizer/preregistration/validation focused 테스트
  52개 통과. signal 날짜와 prospective `observing` 상태가 현재 fixed window와 일치합니다.
- 후보 기간 freeze·MDD hard filter·자동 winner 금지 계약은 유지하며 전략 실행과 PAPER/live
  승격은 하지 않습니다.
- 2026-09-20 재실행에서 registration/readiness와 성과 입력 회귀를 포함해 `88 passed`를 확인했습니다.

## r5-primary-metrics-verification-20260920

- 상태: 기술 계약 재검증 완료; 후보 선택·경제 승격 없음.
- performance metrics/GPU stress 경계 테스트 46개 통과. 비용 차감 수익률·MDD·Sharpe·Calmar,
  zero volatility/drawdown 및 negative outcome을 확인했습니다.

## r6-krx-path-verification-20260920

- 상태: 기술 계약 재검증 완료; 한국 경제 성과는 별도 실행 전까지 `not-evaluated`.
- market data collector/readiness 테스트 167개 통과. zero-OHLC/volume 0·malformed OHLC,
  KRX cache/auth, US/KR prepared path 분리를 확인했습니다.
- 한국 자료는 미국 결과와 혼합하지 않으며 실제 성과·PAPER 승격은 하지 않습니다.

## r7-isolation-safety-verification-20260920

- 상태: 기술 계약 재검증 완료; R7 경제 평가와 PAPER 결정은 `not-evaluated`.
- 범위: prospective registration/readiness, bounded stress, isolated experiment guard,
  calendar stress, forward paper boundary의 fail-closed·격리 계약.
- 보강: `research_r7_isolation.py`와 계약 테스트를 추가해 새
  `market-data/config/database/artifacts` 경로와 manifest를 생성하고, retrospective
  경로 겹침·symlink·재사용·누락 source를 fail-closed로 거부합니다.
- 검증: 관련 pytest 86개 통과(경고 2개). 해시·엄격 JSON·입출력 격리·calendar stress·
  paper-only 경계와 새 workspace 계약을 확인했습니다. source hash mismatch, 권한,
  부모 symlink, `O_NOFOLLOW`/`dir_fd` 생성·정리 경계도 포함합니다.
- `research_r7_gate.py`를 추가해 isolation manifest, prospective readiness, untouched
  OOS, stress, independent review가 모두 충족될 때만 격리 simulation을 허용합니다.
  PAPER 결정은 별도 수동 단계이며 자동 승격은 불변 `false`입니다. 게이트 포함 focused
  pytest는 91개 통과(경고 2개)이며 passed-evidence/result, manifest 변조·symlink
  불변식도 검증합니다.
- 현재 configured 프로젝트 전체 mypy는 기존 범위 밖 오류 104개(27개 파일)로 실패했으며,
  이번 변경이 전체 통과했다고 주장하지 않습니다. R7 변경 범위는 focused pytest와 Ruff로
  검증했습니다.
- 연구 API의 `/api/research/validation/r7/gate`를 연결해 현재 자료가 부족하면 `blocked`
  상태와 `simulation_allowed=false`를 반환하도록 했습니다. 기본 경로는 workspace나
  review evidence를 생성하지 않습니다.
- 수동 검증 충돌을 막기 위해 runner를 pause하고 service/timer를 중지했습니다. 확인 시
  timer도 disable했습니다. `paused=true`, service/timer `inactive`·`disabled`,
  queued/running task 0개이며 자동 재개하지 않습니다.
- 후속 hardening: main `3ccb8ea`에서 parent descriptor와 manifest 경로 exact binding을
  통합했고, 독립 review가 발견한 gate 소비 TOCTOU를 `6db5b16`에서 보강했습니다.
  gate는 root의 모든 구성요소를 `O_NOFOLLOW` held descriptor로 열고 child/manifest를
  root descriptor 기준으로 읽습니다. 조상 symlink alias 회귀를 포함한 R7 isolation/gate
  focused pytest 15개, Ruff, diff 검사가 통과했습니다. 기존 저장소 범위 밖 mypy 오류는
  그대로 기록하며 R7 경제 acceptance는 변경하지 않습니다.
- 제한: untouched OOS 단회 판정과 독립 reviewer 승인 전에는 stress/PAPER 경제 승격을
  하지 않습니다. 실제 연구·network·주문·PAPER/live 설정 변경·remote push는 없습니다.
- 개발 기록: `docs/development-records/2026-09-20-r7-isolation-safety-verification.md`.
- 후속 기록: `docs/development-records/2026-09-20-r7-isolation-hardening-followup.md`,
  `docs/development-records/2026-09-20-r7-isolation-toctou-followup.md`.

## r1-02-krx-prefix-invariance-20260920

- 상태: 완료 (기술 fixture); R1-02 전체와 경제 acceptance는 미완료
- 목표와 완료 조건: KRX daily halt/delisting fixture에서 미래 사건을 추가해도 사건
  적용일 이전의 universe·bars·비대상 symbol이 동일함을 회귀 검증합니다. 이 기술
  slice가 통과해도 historical provider receipt·PIT coverage가 없으면 R1-02 checkbox와
  경제 acceptance는 미체크로 유지합니다.
- 담당: 단일 Luna 구현, Astra 통합, Terra 독립 review
- 워크트리·브랜치: `/home/kwl/projects/jusik-r1-02-krx-prefix-invariance` /
  `feat/r1-02-krx-prefix-invariance`
- 기준 커밋·통합 대상: `6869cc8`, local `main`
- 입력과 선행 작업: 기존 `test_krx_event_forward_exclusion_is_truthful`, `_CorporateActionTransport`,
  R1-02 미국 사건 불변성 계약. runner는 수동 작업 중 pause 상태를 유지합니다.
- 수정 허용 범위: `backend/tests/test_market_data_collector.py`와 이 작업의 개발 기록만.
  production collector·자료·원장·서비스·PAPER/live·remote는 변경하지 않습니다.
- 검증: focused KRX pytest 5개, collector 전체 pytest 131개, Ruff check와 diff check 통과.
  기존 test file 전체 format check는 선행 format 차이로 실패했으며 자동 포맷하지 않았습니다.
- 결과 커밋: 구현 `5273602`, review 수정 `a9dd5ff`, local main 통합 `793792e`.
- 검토 결과: 독립 review의 prefix extension 누락을 수정한 뒤 재검증했습니다. 실제 PIT
  provider receipt와 경제 acceptance는 이 fixture로 주장하지 않습니다.
- 개발 기록: `docs/development-records/2026-09-20-r1-02-krx-prefix-invariance.md`.
- handoff: 별도 세션 handoff 없음; 기존 untracked `HANDOFF.md`를 보존합니다.
- 정리: local `main` 통합 검증 후 작업 worktree와 브랜치를 제거했습니다.
- 중지 조건: 미래 사건이 사건 전 prefix를 변경하거나 자료 의미가 불명확하면 checkbox를
  변경하지 않고 근거와 재개 조건을 남깁니다.

## fred-public-csv-evidence-20260920

- 상태: 완료된 자료 조사 slice; 경제 성과 적용은 차단
- 목표와 완료 조건: FRED API key 없이 공개 DEXKOUS CSV를 bounded read-only로 조회하고
  raw bytes·요청 범위·retrieval 시각·SHA를 보존합니다. 기존 collector/readiness에
  자동 연결하거나 FRED API key 요구를 제거하지 않습니다.
- 담당: Astra 조사·기록
- 입력과 선행 작업: R2 FX/NAV readiness의 `FRED_API_KEY` 및 PIT availability blocker.
- 수정 범위: 저장소 밖 audit raw/request와 개발 기록·등록부만; 코드·원장·서비스·runner
  설정·PAPER/live·remote는 변경하지 않습니다.
- 검증: HTTP 200, raw 4,926 bytes/263 lines, SHA
  `06751750c69089e33aaac8d5bdd0e102887c9c4db2d4d5da529561ad318f8210`.
- 제한: 공개 CSV 관측값은 source evidence일 뿐 PIT availability·NAV 적용·calendar
  completeness를 증명하지 않으므로 R2/R4 readiness와 경제 acceptance는 유지합니다.
- 개발 기록: `docs/development-records/2026-09-20-fred-public-csv-evidence.md`.

## r2-fred-csv-parser-contract-20260920

- 상태: 완료 (기술 parser); 자동 FX/NAV 적용과 R2 경제 acceptance는 미완료
- 목표와 완료 조건: FRED 공개 graph CSV를 기존 JSON parser와 혼동하지 않도록 별도
  fail-closed parser/fixture를 추가합니다. 날짜·중복·결측·범위·Decimal 보존을 검증하고
  transport/readiness/performance에 연결하지 않습니다.
- 담당: 단일 Luna 구현, Astra 통합, Terra 독립 review
- 워크트리·브랜치: `/home/kwl/projects/jusik-r2-fred-csv-parser` /
  `feat/r2-fred-csv-parser`
- 기준 커밋·통합 대상: `22677a8`, local `main`
- 입력과 선행 작업: audit CSV
  `/home/kwl/.local/share/jusik/portfolio-audit/20260920-fred-csv-evidence/`와
  기존 `parse_fred_observations` 계약.
- 수정 허용 범위: `backend/jusik/market_data_collector.py`, 해당 테스트, 개발 기록만.
  네트워크 transport·credentials·원장·서비스·PAPER/live·remote는 변경하지 않습니다.
- 검증: CSV parser focused pytest, collector test subset, Ruff, mypy 변경 모듈, diff check.
- 중지 조건: CSV source semantics가 JSON contract와 동등하지 않거나 결측 의미가 불명확하면
  parser를 연결하지 않고 차단 기록만 남깁니다.
- 결과 커밋: 구현 `13861b0`, duplicate/quoting 보강 `5fb9056`·`b23afe9`, 독립 review
  material finding 없음, local main 통합 `a061838`.
- 개발 기록: `docs/development-records/2026-09-20-r2-fred-csv-parser-contract.md`.
- handoff: 별도 세션 handoff 없음; 기존 untracked `HANDOFF.md`를 보존합니다.
- 정리: local `main` 통합 검증 후 작업 worktree와 브랜치를 제거했습니다.

## alfred-vintage-evidence-20260920

- 상태: 완료된 자료 조사 slice; PIT application과 경제 성과 적용은 차단
- 목표와 완료 조건: ALFRED 공개 vintage CSV 4개를 read-only로 수집하고 raw SHA·vintage
  날짜·관측 존재/부재를 보존합니다. 현재 snapshot을 과거 PIT로 재명명하거나 자동
  성과 계산에 연결하지 않습니다.
- 결과: `2025-09-12` vintage에는 `2025-09-11` 값이 없고 `2025-09-19` vintage에는
  `2025-09-11=1388.97`, `2025-09-12=1394.06`이 존재함을 확인했습니다.
- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260920-alfred-vintage-evidence/`;
  metadata `request.json`에 4개 raw SHA/행 수를 고정했습니다.
- 제한: per-date publication instant, full-period availability, calendar/application
  completeness가 없어 R2/R4 readiness와 Sharpe 계산은 계속 차단합니다.
- 개발 기록: `docs/development-records/2026-09-20-alfred-vintage-evidence.md`.

## alfred-weekly-vintage-evidence-20260920

- 상태: 완료된 자료 조사 slice; PIT application과 경제 성과 적용은 차단
- 목표와 완료 조건: ALFRED 공개 graph CSV의 2025-09-12~2026-09-18 주간 vintage를
  bounded read-only로 수집하고 raw SHA·행 수·관측일별 sampled first-seen 결과를
  보존합니다. 현재 snapshot을 과거 PIT로 재명명하거나 자동 성과 계산에 연결하지
  않습니다.
- 담당: Astra 조사·기록
- 결과: 주간 vintage 54개, 요청 범위 nonblank 관측일 251개, sampled coverage
  251/251. 날짜별 first-seen 결과는 정확한 publication instant가 아닌 upper bound입니다.
- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260920-alfred-weekly-vintages/`;
  `request.json`, `weekly-vintage-summary.json`, `first-seen-sampled-vintages.json`.
- 제한: publication instant/timezone, business calendar completeness, NAV 적용 정책이
  없어 R2/R4 readiness와 Sharpe·Calmar 계산은 유지됩니다.
- 개발 기록: `docs/development-records/2026-09-20-alfred-weekly-vintage-evidence.md`.

## alpha-target-period-action-evidence-20260920

- 상태: 완료된 자료 조사 slice; R1-04/R1-05 경제 acceptance는 차단
- 목표와 완료 조건: 기존 Alpha Vantage raw 응답을 재호출 없이 목표 기간에 대해
  offline 재대조하고 raw SHA·심볼·종류·관측일을 보존합니다. 자동 ledger·성과 계산에는
  연결하지 않습니다.
- 결과: raw 20개, nonempty 8개, 관측 27개. `TQQQ` split 1건과 배당 관측을 확인했습니다.
- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260920-alpha-target-period-evidence/`;
  `target-period-summary.json`, `request.json`.
- 제한: exact PIT publication instant, 완전성, 수동 권리 검토가 없어 action review
  manifest·R1 승격·NAV/성과 계산은 보류합니다.
- 개발 기록: `docs/development-records/2026-09-20-alpha-target-period-action-evidence.md`.

## sec-target-period-filing-evidence-20260920

- 상태: 완료된 자료 조사 slice; 기업행사 확정과 R1 acceptance는 차단
- 목표와 완료 조건: 기존 SEC submissions raw를 재호출 없이 목표 기간의 8-K/8-K/A
  filing·접수 시각으로 재대조하고 accession·items·primary document·원본 SHA를
  보존합니다. filing을 자동 기업행사·원장·성과 근거로 승격하지 않습니다.
- 결과: 8개 매핑 심볼, 89개 filing (`AMD` 14, `COHR` 11, `GEV` 8, `GOOGL` 16,
  `MSFT` 9, `NVDA` 13, `VRT` 18).
- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260920-sec-target-period-evidence/`;
  `target-period-8k-summary.json`, `request.json`.
- 제한: issuer-verified rights/price/effective/payment review가 없어 R1-02/R1-04/R1-05와
  action-review manifest·성과 계산은 보류합니다.
- 개발 기록: `docs/development-records/2026-09-20-sec-target-period-filing-evidence.md`.

## nvda-issuer-action-evidence-20260920

- 상태: 단일 issuer evidence candidate 확보·R1-04/R1-05 승격 보류.
- 결과: SEC 공식 accession `0001045810-25-000207`의 `q2fy26pr.htm`에서 NVDA
  `2025-09-11` record/ex-date, `2025-10-02` payment, USD `0.01`을 확인했고 Alpha
  원문과 일치시켰습니다. raw SHA는
  `caea50c56d2c63a13fe844e165267d038a1649575d1a50e6830c031d58175826`입니다.
- 제한: 전체 coverage, operator verification, 보유수량·가격·세금·다른 action의 근거가
  없으므로 자동 ledger·성과·readiness에는 연결하지 않습니다.
- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260920-nvda-issuer-action-evidence/`.
- 개발 기록: `docs/development-records/2026-09-20-nvda-issuer-action-evidence.md`.

## nvda-issuer-action-evidence-batch-20260920

- 상태: NVDA issuer evidence candidate 3건 확보·자동 적용 보류.
- 결과: SEC `q2fy26pr.htm`, `q3fy26pr.htm`, `q4fy26pr.htm`의 배당 3건을 Alpha
  원문과 amount/date exact match했습니다. audit:
  `/home/kwl/.local/share/jusik/portfolio-audit/20260920-nvda-issuer-action-evidence-batch/`.
- 제한: 전체 심볼/기간 coverage, operator verification, 보유수량·가격·세금 경계가
  없으므로 R1-04/R1-05 checkbox, ledger, 성과, readiness는 변경하지 않습니다.
- 개발 기록: `docs/development-records/2026-09-20-nvda-issuer-action-evidence.md`.

## sec-etf-identity-evidence-20260920

- 상태: SOXL/TQQQ identity candidate 확보·R1-05 승격 보류.
- 결과: SEC 공식 filing index에서 `SOXL→0001424958`(Direxion Daily Semiconductor Bull
  3X Shares), `TQQQ→0001174610`(ProShares UltraPro QQQ)을 확인하고 raw/SHA를 보존했습니다.
- 제한: target-period filing coverage, PIT, 상장폐지·중단일·권리 경계는 아직 미확인입니다.
  기존 catalog `coverage=incomplete`와 unresolved 표시를 유지합니다.
- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260920-sec-etf-identity-evidence/`.
- 개발 기록: `docs/development-records/2026-09-20-sec-etf-identity-evidence.md`.

## sec-etf-identity-parser-20260920

- 상태: 기술 parser 완료·catalog/경제 acceptance 연결 보류.
- 구현: `backend/jusik/research_sec_etf_identity.py`와 focused test를 추가했습니다.
  SEC index raw 하나에서 symbol·title·CIK·accession provenance를 검증하고 credential
  URL·누락·malformed 입력을 fail-closed합니다. 여러 identity의 CIK↔symbol conflict도
  거부합니다.
- 검증: focused pytest 8개, 기존 catalog pytest, Ruff check/format, strict mypy, diff
  check와 보존 raw mapping replay 통과.
- 제한: 기존 SEC ticker map/catalog를 자동 변경하지 않으며 filing coverage, PIT,
  R1-05 acceptance와 원장·성과를 승격하지 않습니다.
- 보존 raw 2개를 새 parser로 offline replay해 identity 2/2 재현을 확인했습니다.
- 개발 기록: `docs/development-records/2026-09-20-sec-etf-identity-evidence.md`.

## sec-etf-submissions-inventory-20260920

- 상태: target-period filing inventory 확보·기업행사 coverage 승격 보류.
- 결과: SOXL CIK `0001424958` 771건, TQQQ CIK `0001174610` 1,063건을
  `2025-09-11~2026-09-11` 범위에서 bounded 수집·파싱했습니다.
- 제한: 제출 유형이 광범위하고 series/class 문서가 섞여 corporate-action/PIT 근거가
  아닙니다. 기존 catalog coverage와 R1-05 상태는 변경하지 않습니다.
- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260920-sec-etf-submissions/`.
- 개발 기록: `docs/development-records/2026-09-20-sec-etf-identity-evidence.md`.

## sec-etf-coverage-report-20260920

- 상태: 기술 inventory report 완료·기업행사/PIT 승격 보류.
- 구현: `research_sec_etf_coverage.py`가 identity와 CIK가 일치하는 submissions만 기간
  내 form/count/date로 집계하고 `inventory_only` 상태를 강제합니다. CIK mismatch, 기간
  역전, source SHA 오류는 fail-closed입니다.
- 결과: 실제 raw replay에서 SOXL 771건, TQQQ 1,063건을 재현했습니다. report와 form
  분포는 `/home/kwl/.local/share/jusik/portfolio-audit/20260920-sec-etf-submissions/coverage-report.json`에 보존합니다.
- 검증: focused coverage/identity/catalog pytest 20개, Ruff check/format, diff check
  통과. configured mypy는 신규 코드 오류 없이 기존 `research_sec_evidence.py`의 선행
  2개 오류를 보고했으며, 그 파일은 변경 범위 밖입니다.
- 제한: filing inventory는 corporate-action coverage·PIT·R1-05 acceptance·원장·성과를
  승격하지 않습니다.
- 개발 기록: `docs/development-records/2026-09-20-sec-etf-identity-evidence.md`.

## sec-evidence-mypy-repair-20260920

- 상태: 완료.
- 변경: `research_sec_evidence.py`의 submissions list narrowing과 CLI argv 타입을
  수정해 기존 strict mypy 오류 2개를 제거했습니다. 수집 의미·raw 계약·재시도 정책은
  변경하지 않았습니다.
- 검증: SEC evidence/ETF identity/coverage/catalog pytest 26개, Ruff check/format,
  strict mypy 3개 source, diff check 통과.
- 제한: 자료 coverage·PIT·기업행사·경제 acceptance는 기존 차단을 유지합니다.
- 개발 기록: `docs/development-records/2026-09-20-sec-etf-identity-evidence.md`.

## tqqq-issuer-split-evidence-20260920

- 상태: 단일 issuer split evidence candidate 확보·R1-04 승격 보류.
- 결과: ProShares release가 TQQQ `2:1`, `2025-11-20` market open 전 effective를
  명시하며 Alpha 원문과 exact match했습니다.
- 제한: 전체 coverage, split 전후 가격·보유수량·세금·fill 경계가 없어 자동 ledger·성과·
  readiness에는 연결하지 않습니다.
- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260920-tqqq-issuer-split-evidence/`.
- 개발 기록: `docs/development-records/2026-09-20-tqqq-issuer-split-evidence.md`.

## soxl-issuer-dividend-evidence-20260920

- 상태: issuer evidence candidate 미확보·R1-04 승격 보류.
- 결과: Direxion 공식 검색 색인에서 SOXL `2025-09-23` record/ex, `2025-09-30`
  pay, `0.01008` 후보를 확인했지만 공식 두 URL의 bounded GET이 Cloudflare
  `403` challenge를 반환해 raw/SHA를 보존하지 못했습니다.
- 판정: 검색 색인은 원문 evidence로 승격하지 않고 operator_verified=false,
  automatic_ledger_application=false를 유지합니다. R1-04/R1-05 checkbox, 원장,
  성과, readiness는 변경하지 않았습니다.
- 후속 조건: credential-free Direxion 원문 또는 SEC/공식 배포 문서 raw 확보 후
  Alpha exact match와 SHA 고정을 재시도합니다.
- 개발 기록: `docs/development-records/2026-09-20-soxl-issuer-dividend-evidence.md`.

## portfolio-session-calendar-stress-v1

- 상태: 완료된 synthetic 기술 검증.
- 결과: 고정 offline calendar adapter로 holiday, early-close, DST, KRX offset,
  completed-session cutoff, strict next-open 및 Decimal 회계를 검증했습니다.
  통합 커밋은 `73134ba46337a2cdc492ae78d0bb3a6691e193a9`입니다.
- 검증: focused pytest 18 passed. completion/review/integration/publication/cleanup/
  handoff/archive evidence는 `/home/kwl/.local/share/jusik/portfolio-audit/portfolio-session-calendar-stress-v1-2cb9ec646e18470a8267ef06742562d2/`에 보존했습니다.
- 제한: synthetic 기술 검증일 뿐 historical PIT·성과·R1 경제 acceptance·PAPER/live를
  승격하지 않습니다. broker partial/cancel/reject와 자료 완전성은 미해결입니다.
- 개발 기록: `docs/development-records/2026-09-20-portfolio-session-calendar-stress.md`.

## r7-source-identity-binding-20260920

- 상태: 완료된 fail-closed 보강.
- 변경: R7 isolation manifest에 canonical source path→SHA-256을 저장하고 gate가
  identity/hash 집합과 실제 source 재해시를 검증하도록 했습니다. 생성 후 source
  변조는 `isolated_workspace_manifest_unavailable`로 차단합니다.
- 검증: R7 isolation/gate pytest 11 passed, Ruff 및 diff check 통과. strict mypy는
  변경 범위 밖 기존 import 오류 10개로 실패했습니다.
- 제한: R7 경제 평가·PAPER 승격·실주문은 수행하지 않았습니다.
- 개발 기록: `docs/development-records/2026-09-20-r7-source-identity-binding.md`.

## continuous-development-session-20260920-1017

- 상태: 진행 중인 bounded session.
- 범위: `2026-09-20T10:17:00+09:00`~`2026-09-20T13:17:00+09:00` 동안 경제 목표에
  직접 기여하는 최소 작업을 순차 수행합니다.
- 운영: runner/service/timer는 pause/inactive를 유지하고 수동 gate·검증을 사용합니다.
  실제 주문, PAPER/live 승격, 원격 push, Windows 종료는 수행하지 않습니다.
- 기준 문서: `docs/continuous-development-session.md`.

## kofr-publication-schedule-evidence-20260920

- 상태: 보조 source evidence 확보·application 승격 보류.
- 결과: 공식 KODEX KOFR 설명서가 KOFR INDEX의 일일 11:00 공시 일정을 명시하는
  raw를 보존했습니다. SHA-256은 `57037e008a62ccfdda91a61f1d86f79fc6a3cdffd1bce0bbac46beca97afd6cd`이며
  audit는 `/home/kwl/.local/share/jusik/portfolio-audit/20260920-kofr-publication-schedule-evidence/`입니다.
- 제한: 운용사 설명서는 KSD 행별 응답의 `PUBN_DTTM` absolute instant와 canonical
  기간의 전체 business-date completeness를 증명하지 않습니다. `missing_risk_free_evidence`,
  Sharpe/readiness 및 자동 적용은 유지합니다.
- 개발 기록: `docs/development-records/2026-09-20-kofr-application-preflight.md`.

## kofr-repeat-response-evidence-20260920

- 상태: 반복 원문 대조 완료·application 승격 보류.
- 결과: 동일 KSD `getGridRateExcelList` 요청이 245행을 반환했고 기존 projection과
  exact match했습니다. repeat raw SHA는 `d35ca9232d1e3ef02af31f667387497476a9b4b6c66e146ecb4744aa0abce142`입니다.
  alternate `getGridRateList`는 malformed XML로 fail-closed 보존했습니다.
- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260920-kofr-repeat-response-evidence/`.
- 제한: provider completeness와 `PUBN_DTTM` absolute instant는 여전히 검증되지 않아
  `missing_risk_free_evidence`와 자동 적용을 유지합니다.
- 개발 기록: `docs/development-records/2026-09-20-kofr-application-preflight.md`.

## kofr-carry-forward-policy-review-20260920

- 상태: 검토 완료·정책 적용 보류.
- 결과: KRX 검색 결과의 “미산출일 직전 KOFR 대리” 문구는 선물 복리 산식 문맥으로
  확인했지만 NAV risk-free application의 carry-forward 근거로 확장하지 않았습니다.
  표준 설명서 직접 URL은 PDF 대신 MenuSearch HTML을 반환해 evidence로 채택하지
  않았습니다.
- 제한: 미국-only 날짜 정책, provider completeness, 행별 publication instant는
  여전히 미확정이며 source/NAV 적용·Sharpe/readiness는 변경하지 않았습니다.
- 개발 기록: `docs/development-records/2026-09-20-kofr-application-preflight.md`.

## kofr-application-policy-proposal-20260920

- 상태: 설계 완료·선택/적용 보류.
- 결정: 현재는 strict exact-date fail-closed(A)를 유지하고, prior-observation
  carry-forward(B)는 provider 규칙·publication instant·NAV ordering·매핑 hash가
  확보된 뒤 별도 승인/구현하도록 정리했습니다.
- 제한: 이 문서는 Sharpe/readiness를 계산하거나 KOFR를 적용하지 않습니다.
- 정본: `docs/research/kofr-application-policy-proposal.md`.

## canonical-time-evidence-attachment-manifest-20260920

- 상태: companion evidence manifest 확보·readiness 연결 보류.
- 결과: canonical run과 동일한 input/data/pool/policy hash·US pilot period의 candidate를
  exact replay(`comparison.all=true`)로 대조했습니다. 252개 NAV timestamp와 initial
  anchor를 별도 manifest에 고정했습니다.
- 제한: canonical artifact/readiness 기본 경로를 변경하지 않았고, KOFR 부족으로
  Sharpe·경제 평가는 여전히 차단됩니다.
- audit: `/home/kwl/.local/share/jusik/portfolio-audit/canonical-time-evidence-candidate-20260920/attachment-manifest.json`.
- 개발 기록: `docs/development-records/2026-09-20-canonical-time-evidence-attachment-manifest.md`.

## r1-action-receipt-time-order-20260920

- 상태: 완료 (기술 slice); R1-04/R1-05 경제 acceptance는 미완료
- 목표와 완료 조건: action receipt preflight가 불가능한 시간 역전(`requested_start > requested_end`,
  `started_at > completed_at`, event/revision 관측 시각 역전)을 fail-closed로 거부하도록
  보강합니다. 정상 동일시각은 허용하고 R1-04/R1-05 경제 acceptance·checkbox는 변경하지 않습니다.
- 담당: 단일 Luna 구현, Astra 통합, 독립 Terra 검토
- 워크트리·브랜치: `/home/kwl/projects/jusik-r1-action-receipt-time-order` /
  `fix/r1-action-receipt-time-order`
- 기준 커밋·통합 대상: `042e87e`, local `main`
- 입력과 선행 작업: `market_history_action_receipt_preflight.py`의 기존 fixed receipt 계약과
  R1 action evidence audit. runner는 pause/service/timer inactive 상태를 유지합니다.
- 수정 허용 범위: `backend/jusik/market_history_action_receipt_preflight.py`,
  해당 테스트, 이 작업의 개발 기록만. 원장·collector·network·PAPER/live·remote는 변경하지 않습니다.
- 검증: 역전 4종 거부와 동일시각 허용 회귀, focused pytest, Ruff, 변경 모듈 strict mypy,
  diff check. 자료 coverage incomplete와 경제 not-evaluated를 유지합니다.
- 중지 조건: 기존 receipt identity/hash가 변하거나 fixed artifact가 재생성되어야 하면 중단하고
  원인과 재개 조건을 기록합니다.
- 결과 커밋: 구현 `2c24b9b`, review 보강 `a2a7405`, 개발 기록 `e936834`·`7bf6e92`.
- 독립 검토: material finding 없음. revision sequence 비감소와 event 전체 시간 범위 검증을
  추가한 뒤 재검토했습니다.
- 통합: local `main` 병합 커밋 `4d2b4809a833fabc92bf2c5b83353050fb1eca4b`.
- 통합 검증: preflight/action-review/SEC/collector `163 passed, 2 warnings`, Ruff
  check/format, 변경 모듈 strict mypy, `git diff --check` 통과.
- 정리: 통합 검증 후 worktree와 브랜치를 제거합니다. 기존 미추적 `HANDOFF.md`는 보존합니다.
- 제한: 실제 receipt coverage·PIT publication·권리/가격 자료는 보강하지 않았고, R1
  checkbox·ledger·NAV·성과·PAPER/live는 변경하지 않았습니다.

## r1-public-evidence-symbol-boundary-20260920

- 상태: 완료 (기술 slice); R1-05 경제 acceptance는 미완료
- 목표와 완료 조건: PublicEvidenceCatalog가 요청 universe 밖의 Nasdaq halt, Alpha
  action, SEC filing을 조용히 포함하지 않고 `evidence_symbol_not_requested`로
  fail-closed 거부하도록 보강합니다. 정상 catalog·unresolved identity·중복 제거
  계약을 보존하며 R1-05 경제 acceptance와 checkbox는 변경하지 않습니다.
- 담당: 단일 Luna 구현, Astra 통합, 독립 Terra 검토
- 워크트리·브랜치: `/home/kwl/projects/jusik-r1-public-evidence-symbol-boundary` /
  `fix/r1-public-evidence-symbol-boundary`
- 기준 커밋·통합 대상: `2292c4c`, local `main`
- 입력과 선행 작업: `research_public_evidence_catalog.py`, 관련 테스트와
  `2026-09-19-public-halt-evidence` 계약. runner는 pause/service/timer inactive를 유지합니다.
- 수정 허용 범위: catalog 구현·해당 테스트·이 작업의 개발 기록만. collector·network·원장·
  PAPER/live·remote는 변경하지 않습니다.
- 검증: source별 요청 외 심볼 거부 회귀, focused pytest, Ruff, strict mypy, diff check.
  `coverage=incomplete`, 경제 `not-evaluated`를 유지합니다.
- 중지 조건: 기존 catalog identity/hash가 바뀌거나 fixed artifact 재생성이 필요하면 중단하고
  원인과 재개 조건을 기록합니다.
- 결과 커밋: 구현 `bf8fd26`, 범위 밖·날짜 필터 순서 회귀 `dcf6510`, 기록 정정 `d1f642e`.
- 독립 검토: material finding 없음. 날짜 필터 이전의 Nasdaq/Alpha/SEC 요청 심볼 검증과
  범위 밖 날짜 회귀를 확인했습니다.
- 통합: local `main` 병합 커밋 `e100372796b28984c2293fe3a4247c963842f50d`.
- 통합 검증: catalog/provider/collector `155 passed`; Ruff check/format과 `git diff --check`
  통과. 변경 catalog 코드 자체의 strict mypy 진단은 없으며, imported 기존 source 모듈의
  기존 진단 5건은 이번 범위 밖입니다.
- 정리: 통합 검증 후 worktree와 브랜치를 제거합니다. 기존 미추적 `HANDOFF.md`는 보존합니다.
- 제한: 자료 coverage/PIT publication/권리·가격 근거는 보강하지 않았고, R1 checkbox·원장·
  NAV·성과·PAPER/live는 변경하지 않았습니다.

## r1-diagnostics-all-failed-boundary-20260920

- 상태: 완료 (기술 slice); R1-05 경제 acceptance는 미완료
- 목표와 완료 조건: `CollectionDiagnostics` 직렬화 입력에서 `all_failed=true`인데
  `symbols`·실패 원인·제외 정보가 모두 비어 있는 payload를 fail-closed로 거부합니다.
  정상 diagnostics와 coverage/incomplete 의미를 보존하며 R1-05 경제 acceptance와
  checkbox는 변경하지 않습니다.
- 담당: 단일 Luna 구현, Astra 통합, 독립 Terra 검토
- 워크트리·브랜치: `/home/kwl/projects/jusik-r1-diagnostics-all-failed-boundary` /
  `fix/r1-diagnostics-all-failed-boundary`
- 기준 커밋·통합 대상: `8554aae`, local `main`
- 입력과 선행 작업: `market_history_approximate.py`의 CollectionDiagnostics validator와
  관련 round-trip tests. runner는 pause/service/timer inactive를 유지합니다.
- 수정 허용 범위: 해당 모델·테스트·개발 기록만. collector/network/원장/PAPER/live/remote는 변경하지 않습니다.
- 검증: 빈 all-failed payload 거부와 정상/aggregate coverage 회귀, focused pytest, Ruff,
  strict mypy, diff check. 자료 coverage와 경제 not-evaluated를 유지합니다.
- 중지 조건: 기존 prepared artifact hash나 R0 계약 변경이 필요하면 중단하고 원인과 재개 조건을 기록합니다.
- 결과 커밋: 구현 `a59d6a0`, local `main` 통합 커밋 `e32e085961cd8d0337b1edbd766f12c21c24c4d7`.
- 독립 검토: material finding 없음. 빈 `all_failed` payload 거부와 유효한 다중 심볼
  round-trip을 확인했습니다.
- 통합 검증: approximate/collector/catalog `187 passed, 2 warnings`, Ruff check,
  변경 모듈 strict mypy, `git diff --check` 통과. 기존 포맷 부채 4곳은 자동 수정하지 않았습니다.
- 정리: 통합 검증 후 worktree와 브랜치를 제거합니다. 기존 미추적 `HANDOFF.md`는 보존합니다.
- 제한: 실제 자료 coverage·PIT·경제 acceptance·R1 checkbox·원장·NAV·성과·PAPER/live는 변경하지 않았습니다.

## r1-roadmap-status-synchronization-20260920

- 상태: 완료 (문서 동기화)
- 목표와 완료 조건: 누적된 R1 기술 slice의 실제 상태를 로드맵 표에 반영하되,
  R1-02/R1-04/R1-05 경제 acceptance와 checkbox는 자료 부족 상태로 유지합니다.
- 변경: `investment-development-roadmap.md`의 R1을 `진행`으로 정정하고 현재 기술
  증거·PIT/coverage 차단 조건을 개발 기록에 고정했습니다.
- 검증: `git diff --check`, mandate/runner 상태 확인. 코드·자료·원장·PAPER/live 변경 없음.
- 개발 기록: `docs/development-records/2026-09-20-r1-roadmap-status-synchronization.md`.

## canonical-readiness-blocker-recheck-20260920

- 상태: 완료 (읽기 전용 재검증)
- 목표와 완료 조건: canonical readiness를 현재 artifact 기준으로 재실행해 실제 남은
  missing code를 고정하고, 오래된 handoff의 누락 세션 설명과 현재 판정을 구분합니다.
- 결과: `blocked`, `ready_for_metrics=false`, `economic_evaluation=not-evaluated`;
  `missing_initial_capital_at`, `missing_nav_timestamps`, `missing_risk_free_evidence`.
- 검증 경로: canonical run·session evidence·manifest·tracked calendar와
  `diagnose_canonical_run()` 직접 호출.
- 제한: anchor/timestamp/무위험률을 추정하거나 성과·hard filter·PAPER/live를 승격하지 않습니다.
- 개발 기록: `docs/development-records/2026-09-20-canonical-readiness-blocker-recheck.md`.

## roadmap-resume-dirty-gate-20260920

- 상태: 완료 (runner 기술 slice)
- 목표와 완료 조건: roadmap scope의 `resume`가 mandate만 확인하고 dirty worktree를
  해제하는 결함을 수정합니다. `_roadmap_documents_ready()`와 `_roadmap_dispatch_gate()`
  및 git readiness를 모두 통과하기 전에는 paused 상태를 유지합니다.
- 담당: 단일 Luna 구현, Astra 통합, 독립 Terra 검토
- 워크트리·브랜치: `/home/kwl/projects/jusik-roadmap-resume-dirty-gate` /
  `fix/roadmap-resume-dirty-gate`
- 기준 커밋·통합 대상: `1af2a1c`, local `main`
- 입력과 선행 작업: `development_runner.py` roadmap resume/run-once 경계와 기존
  mandate/roadmap tests. runner는 실제 운영 상태에서 pause/service/timer inactive를 유지합니다.
- 수정 허용 범위: runner 구현·해당 테스트·이 작업의 개발 기록만. task queue, service,
  network, research, PAPER/live, remote는 변경하지 않습니다.
- 검증: dirty roadmap resume 거부·paused 유지, clean resume 계약, 관련 runner/governance
  pytest, Ruff, strict mypy, diff check.
- 중지 조건: 기존 operator hold·scope binding·mandate identity 의미가 바뀌거나 실제
  runner resume가 필요하면 중단합니다.
- 결과 커밋: 구현 `6ecc577`, local `main` 통합 커밋 `545b26efb2261f2c5ad4e3f06175e87c1d54f4b0`.
- 독립 검토: material finding 없음. tracked dirty, untracked 필수 문서, clean resume과
  paused 상태 보존을 각각 확인했습니다.
- 통합 검증: runner/roadmap/mandate `97 passed`, Ruff check/format, 변경 모듈 strict
  mypy, `git diff --check` 통과. 실제 운영 runner resume/dispatch는 수행하지 않았습니다.
- 정리: 통합 검증 후 worktree와 브랜치를 제거합니다. 기존 미추적 `HANDOFF.md`는 보존합니다.
- 제한: 경제 readiness·R1/R2 checkbox·PAPER/live·원격 push는 변경하지 않았습니다.

## canonical-time-evidence-attachment-audit-20260920

- 상태: 완료 (읽기 전용 대조); canonical readiness 승격은 차단
- 목표: 기존 official time-evidence bundle을 등록된 canonical US run에 연결할 수 있는지
  기간·candidate·policy·input identity를 비교해 재사용 가능성을 판정합니다.
- 결과: 기존 bundle manifest `eec4aae8ed3c0366e9d15fa84657004d0e25429e2815b05e8a4870727718520b`
  은 timestamp/initial-capital 기술 근거를 갖지만 `2024-04-24..2026-09-08` 및 별도
  input/candidate/policy라 canonical `2025-09-11..2026-09-11` run에 연결할 수 없습니다.
- 검증: pinned bundle identity, canonical readiness 직접 진단, manifest/config/request
  read-only 대조. 기존 run·bundle·readiness·runner는 변경하지 않았습니다.
- 남은 조건: canonical과 동일한 frozen input/strategy/period로 생성한 새 bundle과 KOFR
  application evidence가 필요합니다. 개발 기록:
  `docs/development-records/2026-09-20-canonical-time-evidence-attachment-audit.md`.

## market-time-evidence-production-boundary-20260920

- 상태: 기술 slice 완료; 기존 canonical readiness는 차단
- 목표: 새 market research service 결과에 공식 session close 기반 per-NAV timestamp와
  첫 session open 기반 initial-capital anchor를 저장하고, legacy 결과는 보존합니다.
- 구현: `market_time_evidence.py`, optional result fields, readiness fail-closed 검증,
  service boundary 연결과 회귀 테스트.
- 검증: market research/readiness/time-evidence pytest 72개, Ruff, 변경 source strict
  mypy 통과. frozen replay는 commit 후 clean dependency 상태에서 재검증합니다.
- 제한: 기존 canonical artifact에 timestamp를 소급하지 않으며 KOFR evidence·경제 지표·
  PAPER/live·원격 push는 변경하지 않습니다.
- 개발 기록: `docs/development-records/2026-09-20-market-time-evidence-production-boundary.md`.

## canonical-time-evidence-candidate-20260920

- 상태: 완료 (candidate audit); canonical 승격 보류
- 목표: R0 frozen manifest deterministic replay 결과에 공식 NMS timing을 연결해 시간
  blocker 제거 가능성을 검증합니다.
- 결과: replay `comparison.all=true`, 252 NAV/106 trades 일치; candidate initial anchor
  `2025-09-11T13:30:00Z`, NAV 범위 `2025-09-11T20:00:00Z`~`2026-09-11T20:00:00Z`.
  candidate readiness는 시간 두 code만 제거하고 KOFR·기타 evidence에서 blocked입니다.
- audit: `/home/kwl/.local/share/jusik/portfolio-audit/canonical-time-evidence-candidate-20260920/`;
  candidate run SHA `5e4613e2fedad5ecb99f6308686b4e6151df52ba5356d7095dac266a2f4663a3`.
- 제한: 기존 canonical artifact/상수/manifest는 변경하지 않았고, 경제 성과·Sharpe·PAPER/live를
  승격하지 않았습니다. 개발 기록:
  `docs/development-records/2026-09-20-canonical-time-evidence-candidate.md`.

## kofr-application-preflight-20260920

- 상태: 오프라인 진단 완료·실제 적용 차단 유지.
- 입력: KOFR source evidence 245행(SHA `995f9630…0337`)과 canonical time-evidence
  candidate NAV 252개(`2025-09-11~2026-09-11`).
- 결과: application manifest의 provider completeness가 `unknown`이면
  `business_date_completeness_unverified`로 fail-closed 됐습니다. NAV에만 있는 13일과
  source에만 있는 6일을 확인했으며, 기간 축소·carry-forward·0 대체는 하지 않았습니다.
- 제한: `PUBN_DTTM` timezone/instant, provider 전체 business-date 목록, 미국-only 날짜
  적용 정책이 여전히 없습니다. `missing_risk_free_evidence`, Sharpe, readiness 상태는
  변경하지 않습니다.
- 개발 기록: `docs/development-records/2026-09-20-kofr-application-preflight.md`.
