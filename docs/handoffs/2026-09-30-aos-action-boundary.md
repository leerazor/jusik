# AOS 배당 날짜 경계 인계

- 작업 `aos-action-boundary-20260930`, 기준 `d73d37a`; 구현·main 통합 SHA는 감독자 확정 예정. [개발 기록](../development-records/2026-09-30-aos-action-boundary.md)과 [receipt](/home/kwl/.local/share/jusik/portfolio-audit/20260930-aos-action-boundary/receipt.json)이 변환·결속의 진입점이다.
- 원본 calendar lookup: NYQ(raw)/NYS(prepared) → XNYS·America/New_York. 출처 표기 배당락일 2025-10-31의 개장 경계는 `13:30Z`(EDT), 기존 overlay 지급식의 최소 동등식으로 얻은 2025-11-17 지급일 다음 현지 자정은 2025-11-18 `05:00Z`(EST)다. 전체 overlay는 호출하지 않았다.
- 배당락일은 Mergent 제공 역사 표의 검색 스니펫 근거이며 원문 open에서 대상 행을 직접 확인하지 못했다. 두 경계는 정책 파생 후보일 뿐 source event의 정확 시각, Yahoo `13:30Z` 역할, 과거 관측·vintage를 증명하지 않는다. `provider_observed_at`/`available_at` null; pilot 채택·연구 입력·성과 적격 false.
- 보호 19개·source 4개 SHA 일치, 오프라인 변환 1회. 보유량·action·receivable·ledger·수익률이나 생산 코드·준비 자료·서비스·주문은 만들거나 바꾸지 않았다. 다음 독립 범위는 반복 변환/재조회 대신 관측·버전·배당 자격 replay·raw 가격·사전 비용정책의 새 근거에 한정한다.
