# 신규 미국 파일럿 자료 준비 인계

- 갱신: 2026-09-30T05:47:56Z. 작업 트리 `/home/kwl/projects/jusik-us-exclusion-pilot-readiness`, 브랜치 `research/us-exclusion-pilot-readiness`, 기준 `604c6592036cae0eeab1f3872c95e44c04941e25`; main 병합 SHA는 감독자가 확정한다.
- 목표·상태: LIME·MDA를 seed 전에 제외한 미국 1년 sample100 자료를 새 cache로 준비했다. [개발 기록](../development-records/2026-09-30-us-exclusion-pilot-readiness.md)과 audit `missing-inputs.json`에 결과를 보존했다. collector 완료 marker와 `collect-status.ready=true`는 자료·성과 적격이 아니다. data_readiness는 `insufficient`, performance eligibility는 false.
- 실행: 오프라인 miss Yahoo 27개를 고정하고 그 27개만 실제 요청했다(200 6, 404 21; 유효 cache 신규 2). allowlist 외 요청·추가 재시도 0. 준비 JSON SHA-256 `c1b8220c3ffd5beb548ced1209b75442c8a4077dbeac032c9d4d0b025a3c514d`; 원본 cache·과거 결과·backend 코드는 불변이다.
- 차단: 요청 제외 25심볼로 100 목표 대비 세션별 universe 75~76, 사건 125행/37심볼 관측시각 결손. FX 272세션과 collector coverage의 missing 0은 전체 표본 완전성 증거가 아니다. `MET-P-F`의 preferred/depositary 분류 누락은 별도 버전 계약 검토가 필요하며 현재 prepared는 수정 전 산출물이다. 새 수익률·비용/NAV·OOS 실행은 없다.
- 검증·안전: 새 marker/원문 hash·정책 v2·동일 범위 collect-status, audit 스크립트 Ruff/strict mypy 확인. 실주문·PAPER·결제·Toss·push 없음. 설정값은 노출하지 않았고 추가 시장 조회는 금지한다.
- 재개: 독립 review 뒤 유효 역사 자료·사건 observed 시각·분류 버전 근거를 별도 작업으로 결정한다. 기존 frozen run의 비용/NAV adapter를 새 prepared에 재사용하지 않는다. 원본 `missing-inputs.json`과 `preferred-source-notes.json`을 먼저 읽고 동일 27개 요청을 재실행하지 않는다.

다음 세션 시작: “이 인계와 audit 결손 판정을 검토하고, 별도 버전 계약과 자료 보완의 가장 작은 다음 작업을 정해줘.”
