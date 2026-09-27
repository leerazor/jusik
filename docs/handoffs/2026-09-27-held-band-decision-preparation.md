# Held-band 결정 준비 handoff

- Updated: 2026-09-27T02:47:15Z
- Workspace: `/home/kwl/projects/jusik`
- Branch / verified feature integration: `main` / `bf18fb6d35604323f81548bd55fe68407df69c24`
- 상태: 결정 준비 문서를 통합했습니다. V2는 draft이며 실행은 비활성입니다.

## 완료한 작업

- [결정 권고 문서](../research/portfolio-held-band-decision-preparation-v1.md)에 7개 미결 항목을 정리했습니다. 무료 가역 설계·test와 최종 정책·자료 승인·비용·credential·등록·실행 승인을 구분합니다.
- 기존 US approximate 100-symbol cache를 read-only로 확인했습니다. 예상 bars 27,472개 중 20,306개가 있고 7,166개가 누락됐습니다. 25개 종목이 제외됐고 corporate-action 121행에는 관측 시각이 없습니다. Cache는 2026-09-24까지 수집되어 preregistration freeze 전에 노출됐습니다. Offline fixture/debug에만 사용합니다.
- 올바른 output path의 cache status 검사 결과는 `completed=true`, entries 137개, `ready=false`였습니다. Alpha Vantage/FRED API key 환경변수는 명시적으로 unset했습니다. 새 수집에는 이 자격증명이 필요합니다. 기존 cache는 offline으로 계속 읽을 수 있습니다.
- Mandate SHA와 v1 archive hash를 보존했습니다. V2 field는 `null`; `registered=false`, `approved=false`, `execution_allowed=false`입니다.
- 독립 final review가 통과했습니다. `git diff --check`, 문서 링크, JSON 불변식, mandate/archive hash, role-routing post audit를 통과했습니다.
- 앞서 focused test 58개 통과, 알려진 frozen-v1 SHA 불일치 1건. 달력 스트레스 test 18개 통과. 후속 오프라인 collector/held-band 경계 8개, PIT·FX·기업행동·universe-timing 8개, synthetic future-observation replay 29개가 통과했습니다. 첫 8개에서만 Starlette/httpx deprecation 경고 2개가 있었습니다. 전체 제품 suite는 재실행하지 않았습니다.
- 공개 source 후보도 추가 조사했습니다. Nasdaq Data Link는 dataset별 접근·가격·key 조건과 교체 안내가 있어 범용 무료 PIT source로 확인되지 않았습니다. SEC ticker/exchange association은 current issuer identity 보조 자료이지 historical universe/price source가 아닙니다. 원문은 개발 기록에 연결했습니다.
- Worktree `/home/kwl/projects/jusik-portfolio-held-band-decision-preparation-v1`는 clean 확인 후 제거했습니다. Branch는 보존했습니다. 사용자 작성 루트 `HANDOFF.md`는 수정하지 않았습니다.

## 남은 차단과 다음 실행

`FINAL_VALIDATION`과 OOS만 승인된 preregistration freeze 뒤 적격 관측이 생기고, 미노출 상태 및 PIT/data-contract 검증을 통과할 때까지 `PENDING/BLOCKED`입니다. 새 외부 수집은 현재 필수 API key가 없어 차단됐고 KRX는 계정·관리자 access가 필요합니다. 유료 data/compute는 지출 승인 전 구매하지 않습니다. 최종 data acceptance, 신규 투자·합격 수치 기준, preregistration freeze·실행에는 사용자 승인이 필요합니다. 이들은 오프라인 조사·pipeline/test를 막지 않습니다.

임시 가정: 무료 로컬 계산과 합성 fixture는 설계·parser·회계·pipeline·회귀 검증에만 사용합니다. v1 및 approximate cache는 디버그/fixture 전용이며 최종 성과·OOS·후보 승인·실거래 근거에서 배제합니다. 각 단계 전 사용자 승인 및 정식 검증 조건과 대조하고, 미충족이면 그 단계만 보류합니다. 근거·적용 범위·해제 조건은 [개발 기록](../development-records/2026-09-27-held-band-decision-preparation-v1.md)의 provisional assumption 표에 남겼습니다.

바로 실행 가능한 cache status, PIT·event timing·universe fixture, synthetic future-observation replay 및 source 문서 검토를 이번 작업에서 수행했습니다. 기존 replay는 synthetic, unregistered, non-accepted 상태를 fail-closed로 보장하지만 held-band preregistration freeze·outcome exposure/access·manifest 봉인·단회 평가를 모델링하지 않습니다. 현재 코드 결함은 찾지 못해 OOS 계약을 임의로 확장하지 않았습니다. V2 미결 field는 null, `execution_allowed=false`로 둡니다. Approximate 자료를 최종 성과나 OOS 증거로 쓰지 않습니다.

구현 근거와 provider 출처: [개발 기록](../development-records/2026-09-27-held-band-decision-preparation-v1.md). Metadata commit `95be807` 뒤 roadmap runner를 `paused=false`로 복구했습니다. timer active, one-shot service inactive, 181 task 중 active 0이며 fixed engineering backlog exhausted입니다. discovery는 `stale_head`로 source/test/mandate/task state 변경을 기다립니다. 원격 push·시장자료 API 수집·지출·주문·DB/service/PAPER/live 변경은 없었습니다.
