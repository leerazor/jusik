# ICUI 단일 시세 결손 진단 인계

- 작업 `us-icui-bounded-gap-20260930`; 기준 `59eeac7`, 구현 `00a7cb2`, main 병합 `ff5eb6ebd7bfa5c62481f6ee1a9dfd66915dc0a7`. [개발 기록](../development-records/2026-09-30-us-icui-bounded-gap.md)에 범위와 결과를 남겼다.
- exact key ICUI 1회 GET만 실행해 HTTP 200 원문 30,776 bytes를 검증·복사 cache에 저장했다. 원문 SHA `235e3d73e29b98a6ae6ebbbc88f3a4ca31d4280fff96bd317b4663ffdc1bc417`; 272 예상 거래 세션과 272 bar가 일치하고 사건 0건이다. 이전 실패 24개 key는 요청하지 않았다.
- 시도 전 `attempt-sentinel.json` 원자 기록으로 같은 key 재시도를 차단한다. 10 MiB stream cap/30초 요청·60초 전체 timeout/redirect·retry 없음. scope 보호 원본 9개 hash 일치, 복사 cache 139→140, marker 0. 결과·script 결속은 audit `result.json`·`binding.json`에 있다. 생산 코드·정책·원본 cache는 불변이다.
- 이 응답은 ICUI 원문 진단만이며 준비된 연구 입력이나 성과 적격 증거가 아니다. 기존 요청 제외와 다른 종목의 125 사건 관측시각 결손은 남는다. 전략·NAV·OOS·주문·PAPER·push 없음.
- 다음 시작: 같은 24개 실패 요청을 새 증거 없이 반복하지 않는다. 감독자가 audit에 보존한 `next-source-scope-input.json`·`next-source-scope-review.json`으로 AOS 배당 발표/SEC 접수 원문의 역사 관측시각 범위를 별도 검토한다. 과거 occurrence가 warmup 시작 전인 사례의 날짜 의미도 확인해야 한다. 본 작업의 ICUI cache 성공을 전체 자료 인수로 승격하지 않는다.
- 독립 review/main 통합 검증 PASS. 결과·환경은 audit에 보존했고 작업 worktree/branch는 정리했다. 사용자 루트 HANDOFF와 다른 작업은 보존했다. 새 조회 없이 기존 247 tests 및 원문140 hash 검증을 재사용했다.
- 다음 캐시 출발점: `/home/kwl/.local/share/jusik/portfolio-audit/20260930-us-icui-bounded-gap/cache-copy/` (140개, manifest SHA `2584c27430262169a88154fccd4a598c2cd012b57ed6861975da67e3ebed322e`). ICUI 재조회 금지. AOS 후속은 raw identity 고정 후 공식 검색1/원문2 이내로 승인된 별도 scope이며 아직 실행하지 않았다.
