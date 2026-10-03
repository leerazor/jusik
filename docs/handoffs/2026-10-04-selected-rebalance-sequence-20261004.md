# KR 목표 결정열 인계

- UTC2026-10-03T17:10 전후. 로컬 main통합74a55817fbe31b483035142b04d10dbd9c2a201b, 구현022e67f 독립PASS.
- 같은 raw 원장의 초기/추가매수·부분/전량매도·배당 미수금/지급·KRW 현금 재사용을 유한 목표 결정열로 검증했다. 거래 전 위험 위반 이력도 보존한다.
- main208tests/Ruff/strictmypy PASS. 독립 3,870개 작은 입력·3결정 산술·매도/추가매수 배당권리·순열불변 PASS. 기존11사례 전체 출력 보존.
- 기록: 같은 이름 development record. audit `/home/kwl/.local/share/jusik/portfolio-audit/20261004-selected-rebalance/`, manifestc1c270edc2f890486577710f46b36050bbb7e358b3a579a2d6671f0151443877.
- 등록16/revision1·100MKRW·leverage20%·lifetimeMDD20% 유지. 운영DB·서비스·runner·PAPER/live·실주문·push 변경 없음. 실제 성과는 아직 없다.
- 다음: 기존 explore 결과 `/tmp/selected-rebalance-explore-result.txt`와 동결 config/규약을 재사용해 fixedKR 신호+4주 일정+band 연결을 계획한다. band hold와 비용 후 cap의 호환, episode/재진입까지 완료 범위를 명확히 해야 한다. 기존 원장을 중복 구현하지 않는다.
- codewriter 종료, 관리형checkout 보존·다음 작업에 재사용. root 사용자 HANDOFF.md 보존. 다음 계획 확정 후 기존 단일 writer 재개→독립 검토→main 통합.
