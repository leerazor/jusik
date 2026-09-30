# 신규 미국 제외 정책 파일럿 자료 준비

- 상태: 자료 준비 완료, 데이터 인수 불충분; 독립 검토·main 통합 대기
- 기록 시각: 2026-09-30T05:47:56Z
- 작업 slug: `us-exclusion-pilot-readiness-20260930`
- 기준/통합: `604c6592036cae0eeab1f3872c95e44c04941e25` / 없음 (감독자 확정 예정)
- 범위: 2025-09-11~2026-09-11 미국 sample 100, NMS 완료 20세션 warmup. LIME·MDA 선정 전 제외 v2 자료만 준비·판정; 전략·수익률·OOS·NAV 실행 0회.

## 변경과 결정

- 확정 [scope](../../../../.local/share/jusik/portfolio-audit/20260930-us-exclusion-pilot-readiness/scope.json)와 독립 GO를 따라 원본 137개 cache의 manifest/raw만 `offline-cache`·`working-cache`로 복사했다. 완료 marker는 복사하지 않았고 원본 227개 보호 대상, DB, 기존 결과는 수정하지 않았다. audit의 `offline_probe.py`·`freeze_misses.py`·`live_collect.py`·`assess_readiness.py`가 절차와 검사 코드를 보존한다.
- 오프라인 MockTransport에서 listing·FRED는 cache 재사용, Yahoo 27개만 miss였다. 실패를 symbol별로 격리해 만든 오프라인 output은 연구 입력으로 사용하지 않는다. `frozen-misses.json`에 심볼·기간·cache-safe key를 고정했다.
- 실수집은 해당 miss만 허용하는 HTTPS wrapper와 기존 collector `resume=True`로 한 번 실행했다. 실제 27attempt(200 6, 404 21), allowlist 차단 0, 재시도 추가·예산 증액 없음. 200 중 2건만 검증·cache 저장되어 cache 137→139; 나머지 4건은 identity 불일치 2·parse 실패 2다. 새 `us-1y-exclusions.json`과 US 완료 marker가 생성됐다.
- [결손 판정](../../../../.local/share/jusik/portfolio-audit/20260930-us-exclusion-pilot-readiness/missing-inputs.json): `collect-status`의 완료/자격 증명 기준 ready는 true이나 **data_readiness=insufficient, performance_eligible=false**. 101개 누적 인수 심볼 중 요청 제외 25개(404 21, 유효성 실패 4), 세션별 남은 universe 75~76개로 목표 100을 채우지 못했다. 272세션 전체 요청 창에서 제외된 25개에 해당하는 6,800은 *요청 기회*이며 실측 결손 봉수로 계산하지 않았다.
- collector 진단 coverage 20,672/20,672·missing 0은 요청 제외 25개의 기대 세션을 0으로 둔 분모다. 전체 100종목 이력 완전성을 뜻하지 않는다. FX는 해당 272세션에 행이 있고 membership gap은 0이나, 사건 125행·37심볼에서 `observed_at`이 없어 시점 인수가 막힌다. 이전 fresh의 27,472 기대·7,166 결손과 분모가 달라 수치 감소를 개선으로 해석하지 않는다.
- `MET-P-F`는 cache 명칭의 `PRF PERPETUAL`을 현재 ordinary 분류가 통과시키나 [별도 공식 근거](../../../../.local/share/jusik/portfolio-audit/20260930-us-exclusion-pilot-readiness/preferred-source-notes.json)는 preferred/depositary임을 가리킨다. 현 prepared는 **수정 전 코드 산출물**로 고정한다. v2 의미를 조용히 바꾸지 않고 별도 분류 버전·mandate·consumer 계약으로 후속 검토한다. 이번 코드 수정 0.

## 문서·계약 영향

- 사용자·운영 문서와 프로덕션 API·설정·데이터 계약: 변경 없음. 준비 결과와 차단 조건은 이 기록·인계 및 audit에만 저장했다.

## 검증

- 원본 cache 137개는 기존 해시 근거를 재사용했다. `completed_collection_is_valid`·`collect-status` 동일 범위·output은 통과했고 새 prepared SHA-256 `c1b8220c3ffd5beb548ced1209b75442c8a4077dbeac032c9d4d0b025a3c514d`; working cache 원문 139개와 marker·정책 제외·정규화 v2를 확인했다.
- audit 스크립트 4개에 Ruff check/format·strict mypy 통과. 산출물 사전/사후 약 21.5/33.2MB로 100MiB 점검선 아래였으나 내장 hard limit는 아니다. 기존 backend 코드가 불변이므로 pytest 전체 재실행하지 않았다.
- 과거 frozen run에 묶인 cost/NAV adapter는 새 prepared에 재사용할 수 없다. 신규 run·trade/NAV 및 비용·FX·기업행동 독립 근거 전까지 경제 평가는 `not_evaluated`다.

## 안전·운영 상태

- 실주문·PAPER 승격·결제·Toss·원격 push 없음. `.env`는 설정 로더로만 읽었고 값·URL query·원시 예외를 출력하지 않았다. US 필수 credential 누락 이름은 없었다. 시장 조회는 허용한 27회뿐이며 추가 재수집 없음.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260930-us-exclusion-pilot-readiness/`; `missing-inputs.json` SHA-256 `2b73c7893bf9095386f1ea2823ebf56b4a1b43aac70f297dc3485ce87e9345cc`, `preferred-source-notes.json` SHA-256 `d8eae625896493cf4cfe85531909d1dd20a73665b0b5b90bedfff6f9e440beb8`.
- 남은 조건: 요청 제외 25개 유효 역사 자료 또는 별도 정당화된 재선정 계약, 사건 관측시각·기업행동 근거, 분류 계약 후속 결정. 명시된 기존 무료 cache 범위에는 404의 21심볼을 해결할 재사용 원문이 없었으나 모든 미래 공급원이 소진된 것은 아니다. 같은 입력의 live 재시도는 하지 않는다.
- 다음 시작: audit 원문·hash와 독립 검토를 확인하고, 필요하면 별도 버전 계약의 자료 보완을 계획한다. 전략·NAV·수익성 판정은 데이터 gate 통과 뒤 별도 작업이다.
