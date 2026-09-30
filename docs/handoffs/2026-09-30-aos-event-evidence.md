# AOS source-only 배당락일 근거 인계

- 작업 `aos-event-evidence-20260930`, 기준 `2d049b9`; 구현·main 통합 SHA는 감독자 확정 예정. [개발 기록](../development-records/2026-09-30-aos-event-evidence.md)과 [audit 결과](/home/kwl/.local/share/jusik/portfolio-audit/20260930-aos-event-evidence/result.json)을 먼저 읽는다.
- [발행사 호스트 배당이력](https://investor.aosmith.com/stocks/dividend-history)의 **검색 렌더링 대상 행**에 2025-10-13 선언, 10-31 배당락·기준, 11-17 지급, USD 0.36이 함께 표시된다. 원문 open은 대상 행 대신 역사 배당정보의 제3자 Mergent 제공 고지를 확인했다. 실제 요청은 지정 검색 1회·원문 open 1회로 종료했다.
- `aos-source-evidence-v1.json`은 조회 전 고정본이라 `ex_date=null`이고, **최종 날짜 판정의 진입점은 `result.json`**이다. 배포분의 명목 구간은 과거 공표·이용가능성 bound가 아니며, Yahoo `13:30Z` 날짜 역할·공급자 관측·vintage·PIT은 여전히 미확인이다. 자료·성과 적격은 false다.
- scope 보호 원본 15개 SHA 일치. 생산 코드·준비 자료·캐시·mandate·서비스·주문 변경 없고 기존 테스트는 코드 불변으로 재실행하지 않았다. 다음은 역사적 공급자 공개 가능성과 사건 날짜 역할의 직접 근거가 있을 때만 좁은 독립 범위를 심사한다. 추가 조회·adapter·회계 실행은 승인되지 않았다.
