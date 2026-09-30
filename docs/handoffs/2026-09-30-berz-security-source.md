# BERZ·TNMG 원천 증거 인계

- [개발 기록](../development-records/2026-09-30-berz-security-source.md), [SEC 평가](/home/kwl/.local/share/jusik/portfolio-audit/20260930-berz-security-source/assessment.json), [TNMG 대사](/home/kwl/.local/share/jusik/portfolio-audit/20260930-berz-security-source/tnmg-basis-result.json), [결속](/home/kwl/.local/share/jusik/portfolio-audit/20260930-berz-security-source/verification.json)이 읽기 진입점이다. 기준 `42b0e4b`; 구현 `f926ae2`, main 통합 `e5499edec2338acaaa7c13657e9a4baf0f720f4b`. 독립 review·main 결속 PASS, 작업 워크트리·브랜치 정리 완료.
- SEC 고정 원문 1회 GET은 BERZ의 ETN·채무증권 유형을 직접 확인했으나 2025-11-03 제출로 평가 시작 2025-09-11 당시의 공개·분류를 입증하지 않는다. 접수 시각은 최초 가용 시각으로 승격하지 않는다.
- TNMG 원문은 분할 2건과 2026-09-08 all-null 가격을 보존한다. quote raw/adjusted 근거가 없어 회계 raw-basis 계약 차단을 유지한다. 분할 이중 적용 위험 때문에 action·ledger·NAV·성과는 실행하지 않았다.
- 다음 범위는 BERZ의 동시대 상품/공개 근거, TNMG 가격 기준과 사건 관측 근거를 각각 확보하는 경우에만 연다. 같은 SEC URL이나 TNMG 원문을 반복 조회하지 않는다. 코드·정책·기존 준비 자료는 불변이며 연구 입력·성과 적격은 모두 false다.

- 재사용 캐시는 `/home/kwl/.local/share/jusik/portfolio-audit/20260930-us-null-bar-recovery/tnmg-cache-copy` 142개로 불변이다. 원문22개 요청 결손은 40419·빈 응답1·상품 종류 불일치2이며 원인을 임의 확정하지 않는다. 기존 사건125 관측 결손 외 TNMG 분할2도 미확인, 최종 prepared 사건 총수는 미평가다.
- 첫 다음 행동: 새 작업 소유권/runner 상태 확인 후 TNMG 가격기준을 직접 명시한 공급자 근거의 확보 가능성을 제한 검토한다. 가격·분할·NAV 재계산을 먼저 실행하지 않는다. 이미 통과한 nullbar/FX 검사와 BERZ URL 요청은 반복하지 않는다.
- audit `integration.json`·`final-review.json`·`cleanup.json`이 통합/검토/정리 근거다. 검증 당시 문서 해시는 구현 커밋에 결속됐으며 이후 종료 기록 추가와 구분한다. 문서별 해시 키는 basename 대신 정확한 상대경로를 사용한다.
