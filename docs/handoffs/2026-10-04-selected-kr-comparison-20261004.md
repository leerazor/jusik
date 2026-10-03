# KR 동일 조건 합성 비교 인계

- 로컬 main 통합: 18513cde7dc73b12abacdc0fcb6755fe99a37be6; 구현62f1a7594bead126f223336fe47464039d64a215. 기술 완료, 실제 수익성 미검증.
- 같은 raw/signal/config/기간/비용을 실행 전 동결하여 보유·capcontrol·정확히2후보를 각1회 비교. 일별 지표와 전체 사건순서 MDD를 분리하며 결손 무위험률은 Sharpe만 계산불가.
- worker268+132검사, 독립 code review PASS; main132검사/Ruff/mypy/독립8사례 PASS. 실제 원천/투자적격/OOS/거래 승인 없음.
- 개발 기록: docs/development-records/2026-10-04-selected-kr-comparison-20261004.md. 영구audit20261004-selected-kr-comparison의 manifest095185101e3c62ccccd7eccfd5e7b713fd1472404820ae47fea08e00a197e597.
- checkout /home/kwl/.codex/worktrees/official-dividend-input/jusik, codex/selected-kr-comparison clean, 구현 writer 종료. 다음 작업 재사용 가능.
- 현재 다음단계 탐색: 기존 Luna/medium CLI01a101db-2b98-7813-a412-63418263ff55 exec94065, /tmp/selected-next-evidence-explore-events.jsonl. cache/audit만 읽고 실제 자료 공백/실행가능 작업을 좁힌다. 중복 writer 금지.
- 다음 재개: 위 탐색 결과를 읽고 실행 가능한 자료 수용 검증을 진행. 신규근거 없으면 같은 KIS HTTP500 요청 반복 금지. 등록16/revision1·100M·레버리지20%·MDD20% 유지. 주문·PAPER/live·push·GitHubPages 금지, 사용자 HANDOFF.md 보존.
