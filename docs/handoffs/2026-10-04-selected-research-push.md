# 등록 종목 연구 main 동기화 인계

- 갱신: 2026-10-04T03:41:23.960012+00:00; 저장소 /home/kwl/projects/jusik, main.
- 사용자 요청: 지금까지 작업 commit·main merge·push 및 handoff. 이번 main push는 명시 승인되었다. 이후 자동 실행에는 기존 원격 push 금지를 유지한다.
- 인계 작성 기준 HEAD: e0ed1de. 원격 origin/main fetch 후 remote-only 0/local-only 257 확인. 개발 변경은 이미 커밋되어 main에 통합되었고 codex/selected-kr-comparison도 main의 조상이다.
- 이번 추가 변경은 이 인계와 작업 기록뿐이다. 최종 push 성공과 SHA는 Git 원격 ref 대조 및 대화 최종 응답에서 확인한다. 대상 origin https://github.com/leerazor/jusik.git 의 main, force push 없음.
- 기존 루트 HANDOFF.md는 사용자 소유 미추적 역사 기록이므로 그대로 보존하고 이 인계를 정본 재개 지점으로 사용한다.

## 완료와 검증

- 등록 종목 자료 상태 API/UI, 배당 검토 표시, raw 회계 및 KR 위험 청산·회복·재진입 경로 통합 완료.
- 동일 조건 네 경로 비교: 순수 보유·capcontrol·equal/none·inverse_volatility/none. 비교 통합18513cde7dc73b12abacdc0fcb6755fe99a37be6, 구현62f1a759, 독립 review PASS.
- 해당 코드 검증: 구현268+132검사, main 통합132검사·Ruff·strict mypy·독립 Fraction 8사례 PASS. 이후 문서만 변경하여 같은 검사를 반복하지 않았다. 저장소 전체 최신 테스트 통과를 주장하지 않는다.
- 근거: docs/development-records/2026-10-04-selected-kr-comparison-20261004.md. 영구 audit /home/kwl/.local/share/jusik/portfolio-audit/20261004-selected-kr-comparison.
- 기술 완료와 실제 수익성은 별개다. 실제 투자 적격·미사용 미래구간 검증은 미완료다.

## 유지 조건과 재개

- 등록16/revision1, 초기1억원·레버리지20%·MDD20% hard filter 유지. 자동매매·실주문·PAPER/live·GitHub Pages·추가결제·권한/credential 변경 금지.
- 최근 확인: 개발 runner/service·timer inactive, governance dispatch_enabled=false, 활성 code writer 없음. 이 요청에서 서비스나 automation 설정을 변경하지 않았다.
- 실제 KR 후보487230/487240의93일 raw 및 공식분배 근거는 재사용. 정확한 기간의 공식 거래일/특별세션과 전체 기업행동·분할 완전성, 평가기간·비용 시나리오 동결이 남았다.
- docs/handoffs/2026-10-04-selected-next-evidence-20261004.md 및 selected-us-dividend-next-20261003 인계 참조. KIS HTTP500, KRX timeout, GOOGL 공식 배당락일 검색은 새 근거 없이 반복하지 않는다.
- 작업 checkout /home/kwl/.codex/worktrees/official-dividend-input/jusik 은 clean·main통합 상태이며 다음 승인된 작업에 재사용하도록 보존한다. 다른 작업의 worktree는 건드리지 않는다.
- 다음 시작: 이 인계와 MEMORY.md를 읽고 등록revision·Git·실행중 writer를 새로 확인한다. 새 공식근거가 생기면 기존 cache와 대조하여 자료 공백을 해소한다. 과거 분석구간을 untouched OOS로 바꾸지 말고 같은 상태의 audit를 반복 생성하지 않는다.
