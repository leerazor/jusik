# 선정 후보 KR 정책 연결 인계

- 완료: 구현856b3c6 → 해시검증 P2 수정4ad0fa5 → 독립PASS → main b992712318e1b9893cfd71124083d6bfb2fcc3b0.
- 검증: 통합240검사/Ruff/strict mypy PASS. 기존11개/KRsequence/probe 전체 출력 보존. 외부 현금·수량·NAV 및 순서 반전4사례 PASS.
- 결과: 두 고정 후보 신호+4주 결정+strictnextopen+수량유지 band를 단일raw원장에 연결. 위험10%·미지원cap수리 요구는 실패. 실제성과/전체위험정책 완료가 아니다.
- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20261004-selected-kr-candidate-policy/`, manifest `e3b9dcbc2fe5c3454c253c762bfe590986d79d8df6dbabfb5b16255c254e4b09`.
- 다음: 같은 구현자/checkout에서 selected-kr-risk-policy-20261004. audit의 위험 explore/plan 결과 재사용, episode청산·pending취소·28일대기·2회확인·재진입·cap 처리 구현 후 독립검토/통합.
- 실제 등록16/rev1, 배당eligible24/111은 배당만의 상태. READYcohort/수익성 미검증. 자동매매·실주문·PAPER/live·원격push 없음. user HANDOFF.md 보존.
