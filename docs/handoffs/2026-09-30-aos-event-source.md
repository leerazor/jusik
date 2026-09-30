# AOS 배당 사건 원문 확인 인계

- 범위와 판정은 [개발 기록](../development-records/2026-09-30-aos-event-source.md), 원본 식별·스냅샷·보호 SHA 결과는 [audit](/home/kwl/.local/share/jusik/portfolio-audit/20260930-aos-event-source/assessment.json)에 있다. 기준 `07461b3`; 구현 `79078e0`, main 통합 `760803d7fa47c68476df64846f6f0dc69755ccca`.
- AOS Yahoo 원문 `dividends` USD 0.36, `2025-10-31T13:30:00Z`, `observed_at=null`. 공식 [발행사 발표](https://investor.aosmith.com/news-releases/news-release-details/o-smith-increases-quarterly-dividend-036-share)는 2025-10-13 승인, 10-31 기준일, 11-17 지급일을 명시한다. 발행사가 연결한 [배포 원문](https://www.prnewswire.com/news-releases/a-o-smith-increases-quarterly-dividend-to-0-36-per-share-302582536.html)은 `2025-10-13 17:54 ET`(EDT 기준 21:54 UTC, 분 단위)를 표시한다. 공식 검색 1회·원문 열기 2회, 추가 시장 요청 0회.
- 금액과 달력일은 연결되지만 Yahoo 사건 시각의 날짜 역할·정확한 `13:30:00Z` 의미·당시 최초 관측시각은 입증되지 않았다. 원문은 배당락일과 초 단위 배포시각도 제시하지 않는다. 배포 표기를 `observed_at`으로 채우거나 PIT·연구 입력·성과 적격으로 승격하지 않는다.
- search/source/distribution snapshot의 SHA는 렌더링 도구 결과의 해시로, 원본 HTML bytehash가 아니다. scope 보호 파일 11개 SHA 일치. 생산 코드·정책·원본·prepared 불변이며 기존 247개 테스트는 코드 변경이 없어 반복하지 않았다.
- 다음 작업은 사건 날짜 역할과 역사 공개/관측시각 원본 근거를 별도 범위로 검토해야 한다. 다른 124개 사건이나 같은 공급자 시세 재조회로 이 결손이 자동 해결되지는 않는다. 독립 review와 main 통합 검증은 PASS이며 worktree/branch는 정리했다. audit와 환경·검증 근거는 보존했다.
- 우선 재개 범위: 기존 `observed_at` 계약이 요구하는 시각과 분 단위 배포근거·사건 날짜 역할의 정합성을 읽기 전용으로 검토한 뒤 필요한 원문을 정한다. 같은AOS검색/시세24재요청/125건일괄조회는 새 scope 없이 반복하지 않는다. 준비자료는 불변이며 캐시 재사용 출발점은 [ICUI 인계](2026-09-30-us-icui-bounded-gap.md)의140개다.
