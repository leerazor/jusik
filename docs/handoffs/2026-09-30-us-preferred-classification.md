# 미국 우선주 분류 보정 인계

- 작업: `us-preferred-classification-20260930`; 기준 `584df86c`, 구현 커밋 SHA 및 main 병합 SHA는 감독자 확인 예정. 개발 기록은 [여기](../development-records/2026-09-30-us-preferred-classification.md).
- 새 미국 수집은 `PRF PERPETUAL` 연속 상품명을 제외하는 v3 정규화·별도 pool hash·`completed-us-exclusions-v2.json`을 사용한다. v2 prepared SHA `c1b8220c3ffd5beb548ced1209b75442c8a4077dbeac032c9d4d0b025a3c514d`와 v2 marker는 보존했다. 기존 v2 hash의 golden 값은 audit `legacy-contract-hashes.json`에 있다.
- 시장 연구·runner governance focused 검사 246개 통과; Ruff·소스 strict mypy·governance validation 통과. 문서 변경에 맞춰 checksum의 Markdown 두 행만 갱신하고 JSON·정책 네 행은 보존했다. 독립 review 및 main 통합 후 영향 범위 검증은 감독자 예정. 시장 네트워크·새 v3 수집·전략·NAV·주문·push 0회.
- 추가 runner 검사의 기존 mandate 기대값 1건은 main에서도 동일하게 실패해, 현재 JSON 정책 5필드를 명시 검증하도록 보완했다. [개발 기록](../development-records/2026-09-30-us-preferred-classification.md)에 범위와 근거를 남겼다.
- 기존 pilot 자료는 여전히 불충분하다: 요청 제외 25심볼, 125개 사건 행의 관측시각 결손. audit `event-observation-blocker.json`의 ADAMI·AGX·AOS 원문 3개는 사건 날짜/금액만 있으며 원문 SHA 재확인 완료. 시세 재조회나 fetch 시각 치환으로 해결되지 않는다. 종목·사건별 역사 관측시각 원본 증거가 필요하고 접근·비용은 미확인이다.
- 다음 시작: 기존 cache만으로 v3 표본 선정과 miss 변화를 오프라인 계산해 범위를 고정한다. 기존 Yahoo 27건과 동일 요청은 새 근거 없이 반복하지 않는다. 필요한 사건·역사 자료는 별도 scope 검토 후 수집한다. v3 기술 완료를 데이터 인수·성과 검증으로 승격하지 않는다.
