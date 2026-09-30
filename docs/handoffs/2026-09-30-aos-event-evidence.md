# AOS source-only 배당락일 근거 인계

- 작업 `aos-event-evidence-20260930`, 기준 `2d049b9`; 구현 `a8c0243`, main 통합 `2776affb78a702614baf59866455ad09284ff547`. [개발 기록](../development-records/2026-09-30-aos-event-evidence.md)과 [audit 결과](/home/kwl/.local/share/jusik/portfolio-audit/20260930-aos-event-evidence/result.json)을 먼저 읽는다.
- [발행사 호스트 배당이력](https://investor.aosmith.com/stocks/dividend-history)의 **검색 렌더링 대상 행**에 2025-10-13 선언, 10-31 배당락·기준, 11-17 지급, USD 0.36이 함께 표시된다. 원문 open은 대상 행 대신 역사 배당정보의 제3자 Mergent 제공 고지를 확인했다. 실제 요청은 지정 검색 1회·원문 open 1회로 종료했다.
- `aos-source-evidence-v1.json`은 조회 전 고정본이라 `ex_date=null`이고, **최종 날짜 판정의 진입점은 `result.json`**이다. 배포분의 명목 구간은 과거 공표·이용가능성 bound가 아니며, Yahoo `13:30Z` 날짜 역할·공급자 관측·vintage·PIT은 여전히 미확인이다. 자료·성과 적격은 false다.
- scope 보호 원본 15개 SHA 일치. 생산 코드·준비 자료·캐시·mandate·서비스·주문 변경 없고 기존 테스트는 코드 불변으로 재실행하지 않았다. 다음 독립 scope는 새 ex-date 근거와 기존 DividendAction effective_at/payment_at 사이의 날짜 경계·시각 정밀도 변환 조건을 검토한다. 공급자 관측과 당시 가용성은 미확인으로 유지한다. 이번 범위는 추가 조회·adapter·회계 실행을 포함하지 않았다.
- 독립 review/main 통합 검증 PASS, audit/환경 보존 후 전용 worktree/branch 정리. 기존24 시세실패와125관측시각 결손·전체자료인수 차단은 유지한다. 새날짜근거만으로 observed_at을 채우지 않으며, 캐시 재사용은 [ICUI 인계](2026-09-30-us-icui-bounded-gap.md)의140개를 따른다.
