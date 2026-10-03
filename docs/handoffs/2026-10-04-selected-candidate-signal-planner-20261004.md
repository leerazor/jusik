# 선정 후보 신호 계산 인계

- UTC2026-10-03T16:14 전후, main 통합 `4e1ff562aad56ed287762345e3a74e088d35308f`. 구현54fbca8/P2수정a7fc5a6, 독립 재검토PASS.
- 등록16/revision1·100MKRW·leverage20%·lifetimeMDD20% 유지. 주문·PAPER/live·Pages·push 없음.
- 완료: equal/inverse 순수 목표 계산, 인과적 종가/FX, cap/scale, UTC 정규화. 189 tests/Ruff/strictmypy/독립산술 PASS. 기존 UTC 출력·원장6사례 보존.
- 코드/기록: `backend/jusik/selected_candidate_signals.py`, 같은 작업의 development record. 실제자료 적격·수익성·일정/밴드/episode/재진입·다종목 체결 미완료.
- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20261004-selected-signal-planner/`. 동결 source와 차단 flags는 현재 config JSON 정본.
- managed checkout은 다음 작업 재사용 위해 보존. 현재 writer 종료, root 사용자 HANDOFF.md 보존.
- 다음 시작: `/tmp/selected-multi-target-plan-result.txt`의 보수적 NAV 하한 batch 설계로 단일 구현자를 배정한다. 같은 통화·동시 첫 시가만 허용하고 혼합시장/미지원 입력을 거부한다. 연구 성과는 아직 주장하지 않는다.
