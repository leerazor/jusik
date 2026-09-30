# 신규 미국 파일럿 자료 준비 인계

- 갱신: 2026-09-30T05:59:48Z. 기준 저장소 `/home/kwl/projects/jusik`, `main` 통합 `0095c5c9fe33349b536226010364b823ec7812ee`; 구현 `853d253c05c6d9991cc41983cdd9148063dd8e55`, 기준 `604c6592036cae0eeab1f3872c95e44c04941e25`. 작업용 `/home/kwl/projects/jusik-us-exclusion-pilot-readiness`와 브랜치 `research/us-exclusion-pilot-readiness`는 검증 후 정리했다.
- 목표·상태: LIME·MDA를 seed 전에 제외한 미국 1년 sample100 자료를 새 cache로 준비했다. [개발 기록](../development-records/2026-09-30-us-exclusion-pilot-readiness.md)과 audit `missing-inputs.json`에 결과를 보존했다. collector 완료 marker와 `collect-status.ready=true`는 자료·성과 적격이 아니다. data_readiness는 `insufficient`, performance eligibility는 false.
- 실행: 오프라인 miss Yahoo 27개를 고정하고 그 27개만 실제 요청했다(200 6, 404 21; 유효 cache 신규 2). allowlist 외 요청·추가 재시도 0. 준비 JSON SHA-256 `c1b8220c3ffd5beb548ced1209b75442c8a4077dbeac032c9d4d0b025a3c514d`; 원본 cache·과거 결과·backend 코드는 불변이다.
- 차단: 요청 제외 25심볼로 100 목표 대비 세션별 universe 75~76, 사건 125행/37심볼 관측시각 결손. FX 272세션과 collector coverage의 missing 0은 전체 표본 완전성 증거가 아니다. `MET-P-F`의 preferred/depositary 분류 누락은 별도 버전 계약 검토가 필요하며 현재 prepared는 수정 전 산출물이다. 새 수익률·비용/NAV·OOS 실행은 없다.
- 검증·안전: 새 marker/원문 hash·정책 v2·동일 범위 collect-status, audit 스크립트 Ruff/strict mypy 확인. 독립 review는 불충분 진단에 한해 PASS; main 문서 일치·링크·hash·backend/mandate 불변 검증 PASS. 원본 227개와 작업 cache 139개 검증 근거는 `final-review.json`, 통합 근거는 `integration-verification.json`에 있다. 실주문·PAPER·결제·Toss·push 없음. 설정값은 노출하지 않았고 같은 입력의 시장 재조회는 하지 않는다.
- 운영: runner paused, service/timer inactive. 활성 heartbeat는 후속 작업 전 실제 writer 상태를 확인한다. 환경·스크립트 버전은 audit `environment.json`에 보존했고 루트 사용자 `HANDOFF.md`는 건드리지 않았다.
- 재개 순서: (1) `missing-inputs.json`·`preferred-source-notes.json` 및 기존 계획을 재사용해 `PRF PERPETUAL` 분류를 별도 정규화 버전으로 수정하는 최소 범위를 확정한다. v2와 과거 실험을 보존하며 티커 모양만으로 추가 제외하지 않는다. (2) 유효 역사 자료·사건 관측시각 근거를 보완한다. (3) 데이터 gate 통과 후 새 run의 비용/NAV 검증과 고정 조건 비교를 한다. 기존 frozen run의 비용/NAV adapter를 새 prepared에 재사용하지 않으며 동일 27개 요청을 반복하지 않는다.

다음 세션 시작: “이 인계와 저장된 결손·분류 근거를 재사용해 우선주 분류를 별도 버전으로 바로잡는 최소 작업부터 진행하고, 자료 gate를 통과한 뒤 비용/NAV·성과 비교로 이어가줘.”
