# 미국 우선주 분류 보정 인계

- 갱신: 2026-09-30T06:55:03Z

- 작업: `us-preferred-classification-20260930`; 저장소 `/home/kwl/projects/jusik`, 기준 `584df86c`, 구현 `06862d8`, 보완 `adbe3e524d19996374c9acf42dda39ce672ec8bd`, main 통합 `f8307ae80e8b46827f7f209093d2d4e14c18c91e`. [개발 기록](../development-records/2026-09-30-us-preferred-classification.md)에 전체 근거가 있다. 전용 worktree·브랜치는 통합 검증과 환경 보존 후 정리했다.
- 새 미국 수집은 `PRF PERPETUAL` 연속 상품명을 제외하는 v3 정규화·별도 pool hash·`completed-us-exclusions-v2.json`을 사용한다. v2 prepared SHA `c1b8220c3ffd5beb548ced1209b75442c8a4077dbeac032c9d4d0b025a3c514d`와 v2 marker는 보존했다. 기존 v2 hash의 golden 값은 audit `legacy-contract-hashes.json`에 있다.
- 독립 review 후 parser·v3 reader·v3 완료 검증에서 같은 상품명 판정을 사용한다. `PRF PERPETUAL` 행이 남은 v2 자료를 v3로 재표시한 입력은 거부하고, 원래 v2 입력은 계속 수용한다.
- 독립 재검토의 회귀 2개 PASS, main의 시장 연구·runner governance focused 검사 247개 PASS; Ruff·소스 strict mypy·mandate/dispatch validation PASS. 문서 변경에 맞춰 checksum의 Markdown 두 행만 갱신하고 JSON·정책 네 행은 보존했다. 보호 파일 6개·구 계약 hash 3개·사건 원문 3개도 일치한다. 시장 네트워크·새 v3 수집·전략·NAV·주문·push 0회.
- 추가 runner 검사의 기존 mandate 기대값 1건은 main에서도 동일하게 실패해, 현재 JSON 정책 5필드를 명시 검증하도록 보완했다. [개발 기록](../development-records/2026-09-30-us-preferred-classification.md)에 범위와 근거를 남겼다.
- 기존 pilot 자료는 여전히 불충분하다: 요청 제외 25심볼, 125개 사건 행의 관측시각 결손. audit `event-observation-blocker.json`의 ADAMI·AGX·AOS 원문 3개는 사건 날짜/금액만 있으며 원문 SHA 재확인 완료. 시세 재조회나 fetch 시각 치환으로 해결되지 않는다. 종목·사건별 역사 관측시각 원본 증거가 필요하고 접근·비용은 미확인이다.
- 다음 시작: 기존 cache만으로 v3 표본 선정과 miss 변화를 오프라인 계산해 범위를 고정한다. 기존 Yahoo 27건과 동일 요청은 새 근거 없이 반복하지 않는다. 필요한 사건·역사 자료는 별도 scope 검토 후 수집한다. v3 기술 완료를 데이터 인수·성과 검증으로 승격하지 않는다.
- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260930-us-preferred-classification/`의 `verification-manifest.json`이 검사 명령·결과와 source/test hash를 연결한다. `review-initial.json`과 `review-final.json`에 최초 거절·해결 근거를 남겼다. 입력이 같은 검사는 이를 재사용한다.
- 운영: runner paused, service/timer inactive를 유지한다. 다음 자동 작업은 실제 writer 상태를 다시 확인한다. 루트 사용자 `HANDOFF.md`는 보존했다.
