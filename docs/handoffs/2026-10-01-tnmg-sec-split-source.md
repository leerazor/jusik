# TNMG SEC 분할 원천 인계

- [개발 기록](../development-records/2026-10-01-tnmg-sec-split-source.md), [판정](/home/kwl/.local/share/jusik/portfolio-audit/20261001-tnmg-sec-split-source/assessment.json), [검증](/home/kwl/.local/share/jusik/portfolio-audit/20261001-tnmg-sec-split-source/verification.json)이 진입점이다. 주 문서 2건은 각 1회 조회했고 추가 요청은 없다. 구현 커밋의 main 통합은 감독자 예정.
- 2025 `1-for-20` 비율은 확인됐으나 주 문서의 개장 날짜 **2024-12-23**과 대상 **2025-12-23**이 충돌한다. 2026 `1-for-8` 및 2026-09-08 개장 예정은 확인됐으나 실제 효력은 미확인이다. SEC 접수시각은 최초 공개 시각이 아니며 공급자 `observed_at`, Yahoo quote 가격 기준, 9월 8일 결손 가격은 여전히 미확인이다.
- 다음 독립 조회 후보는 정확히 [2025 Exhibit 99.1](https://www.sec.gov/Archives/edgar/data/2013186/000121390025123776/ea027032301ex99-1_tnlmedia.htm)이다. 현재 문서의 Exhibit 표기는 2025-12-05 보도자료이며 2025-12-18은 주식 수 기준일이다. Exhibit 조회는 이번 범위에서 0회; 새 scope·요청 상한으로만 수행한다.
- 캐시·회계·NAV·전략·성과·PIT 승격 없음. 원본 주 문서 재조회나 날짜 오탈자 추정 대신 별도 충돌 근거를 확보하고, 가격 기준과 사건 관측 근거는 독립적으로 검토한다.
