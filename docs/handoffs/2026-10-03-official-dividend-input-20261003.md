# 공식 배당 입력 완료 후 NAV 검증 계속

- 2026-10-03 UTC, `/home/kwl/projects/jusik`, main 통합 `dd3f01f1b5c0589e0fb0a2ace52c41e6c1213e0e`, 구현 최종 `c509a794`. 사용자 요청은 단계별 지속 진행이며 자동매매·PAPER/live·Pages·remote push 제외.
- [기록](../development-records/2026-10-03-official-dividend-input-20261003.md)과 [입력 계약](../research.md#공식-현금-배당-입력-동결)을 먼저 읽는다. 신규 CLI는 현재 등록/수집/검토 연결과 원문 해시를 검증해 공식 현금 배당 JSON을 동결한다. 금액 충돌은 새 artifact에 남기고 기존 strict review/overlay는 변경하지 않았다.
- 독립 재검토 PASS, main 테스트37/정적 검사 PASS. MSFT12 실자료 사본의 최종 artifact SHA `438bf7e006c6ba6b8bd65bd75ef1452dd3050939f7f4bc25baa3c3ddc6371a3c`; `58c024...`는 검토 전 산출물이므로 재사용 금지.
- audit `/home/kwl/.local/share/jusik/portfolio-audit/20261003-official-dividend-input/`. 원문·DB사본·입력 manifest·검증 결과·해시 보존. SEC8-K로 MSFT common stock/NASDAQ 신원 근거 확보. 차단된 Microsoft FAQ/뉴스 URL 재요청하지 않는다.
- 동결 MSFT 배당 한 건을 읽어 순수 회계 함수에 연결한 가상 계산표 대사도 PASS: 배당락 이후 매도에도 수취권 보존, 지급 시 미수금→현금, 중복 지급 방지. `nav_oracle.py` 참고. 이 검증은 매매 엔진 비용·환율·세금 검증이 아니다. 성과 실험/OOS 소비 없음, `nav_ready=false` 유지.
- 다음 실행은 기존 `research_dividend_overlay.calculate_scenario`와 `market_history_action_accounting`을 재사용하여 환율 가용 시각·거래/FX 비용·현금+주식+배당 미수금 전체 NAV의 독립 계산 대사를 범위 고정한다. 새 입력 경로가 있다고 전체 배당/분할·달력/비용 준비가 끝난 것으로 처리하지 않는다. 그 뒤 같은 기간·종목·비용의 기준선과 사전등록 후보 비교로 간다.
- 등록16/revision1, 기존 배당 적격13/111(이 작업은 운영 DB 변경 없음). runner paused/dispatchfalse·기존 optimizer 중지 유지. 웹 서비스 변경/재배포 없음. heartbeat ACTIVE/30분, 같은 대화에서 최신 이 인계로 이어간다.
- free 관리형 checkout `/home/kwl/.codex/worktrees/official-dividend-input/jusik`, branch `codex/official-dividend-input`, clean/전부 병합/프로세스없음. 후속 작업에서 기존 환경을 재사용하되 main 기준과 새 브랜치를 먼저 준비한다. 중복 writer를 만들지 않는다. 루트 HANDOFF는 사용자 소유 보존.

재개: MEMORY와 이 인계를 읽고 실제 등록 목록·writer·runner 상태를 확인한 뒤, 이미 통과한 입력 검증을 반복하지 말고 환율·거래비용 포함 NAV 검증의 최소 시나리오부터 진행하세요.
