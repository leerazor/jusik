# TNMG SEC 분할 원천 인계

- [개발 기록](../development-records/2026-10-01-tnmg-sec-split-source.md), [판정](/home/kwl/.local/share/jusik/portfolio-audit/20261001-tnmg-sec-split-source/assessment.json), [검증](/home/kwl/.local/share/jusik/portfolio-audit/20261001-tnmg-sec-split-source/verification.json)이 진입점이다. 주 문서 2건은 각 1회 조회했고 추가 요청은 없다. 구현 커밋의 main 통합은 감독자 예정.
- 2025 `1-for-20` 비율은 확인됐으나 주 문서의 개장 날짜 **2024-12-23**과 대상 **2025-12-23**이 충돌한다. 2026 `1-for-8` 및 2026-09-08 개장 예정은 확인됐으나 실제 효력은 미확인이다. SEC 접수시각은 최초 공개 시각이 아니며 공급자 `observed_at`, Yahoo quote 가격 기준, 9월 8일 결손 가격은 여전히 미확인이다.
- [2025 Exhibit 99.1 링크](https://www.sec.gov/Archives/edgar/data/2013186/000121390025123776/ea027032301ex99-1_tnlmedia.htm)는 기록만 했고 본문은 읽지 않았다. 주 문서의 Exhibit 표기일 2025-12-05는 최종 비율 결정일 2025-12-09보다 앞선다. [독립 후속 판정](/home/kwl/.local/share/jusik/portfolio-audit/20261001-tnmg-sec-split-source/followup-scope.json)은 현재 이 Exhibit 조회를 NO_GO로 보며, 내용을 모르므로 충돌 해소 불가능하다는 뜻은 아니다. 2025-12-18은 주식 수 기준일이다.
- 캐시·회계·NAV·전략·성과·PIT 승격 없음. 원본 주 문서 재조회나 날짜 오탈자 추정 대신 후일 정정 또는 공식 거래소·기업행동 자료의 정확 URL과 독립 scope가 생길 때 충돌을 재검토한다. 가격 기준과 사건 관측 근거는 별도로 검토한다.
