# Autonomous trading lab 진행 인계

- 갱신: 2026-09-25 UTC 기준 최소 구현 통합·검증 완료.
- 저장소: `/home/kwl/projects/jusik`, `main`.
- 목표: 현재 구조와 지침을 토대로 소수의 agent 프로필을 설계하고, BLOCKED/WAITING 작업 뒤의 독립 READY가 실제 진행되는 최소 구현을 검증한다. 실제 주문·PAPER 승격·추가 결제·권한/credential/투자 기준 완화는 포함하지 않는다.

## 검증된 변경

- 설계 정본 `docs/autonomous-trading-lab.md`에 8개 논리 프로필, 기존 18개 후보 처리, 각 프로필 16항목, 통신·task/strategy 상태·모델·예산·충돌·소유권을 기록했다.
- 지침·설정은 총 active 4개(주 agent + 하위 3개), Sol 중심 복잡한 구현, Luna 반복 작업, 선택적 Astra 진단으로 병합했다. 과거 종료 창을 active 지시에서 분리했다.
- `backend/jusik/strategy_lifecycle.py`의 offline SQLite registry를 `62e229b`로 main에 통합했다. 초기 연구/중단/복원/폐기만 지원하고 투자 승격은 차단한다. worker/main focused pytest 16개, Ruff, mypy와 독립 Sol 검토를 통과했다.
- runner A의 최초 실제 `run_once` 재현은 수정 전 1 failed였다. 오래된 선두 영역이 독립 READY를 막았다. 검토 지적을 두 차례 추가 RED로 재현·수정했고 최종 `1c64c13`을 main `e6e90d4`에 병합했다. 독립 Sol 재검토는 최소 범위 PASS였다. 통합 후 focused 140 passed, Ruff check/format, strict mypy와 diff check 통과. 공학 후보는 독립 reviewer receipt 경로가 없으므로 완료가 아닌 검토 대기다.

## 현재 상태와 다음 행동

- 다음 고정 READY 개발 과제: 별도 읽기 전용 reviewer attempt journal/timeout·중단 복구, task·implementation attempt·main HEAD·소유 파일 hash 결속 PASS receipt, 원래 attempt의 원자적 `DONE + ENGINEERING_COMPLETE + NOT_EVALUATED` 전이. 일반 event retry·자기 보고·새 구현 attempt는 review를 대체할 수 없다. 상세 acceptance는 설계 정본 16절을 따른다.
- roadmap runner는 수동 통합 중 `paused=1`, service inactive, timer active였다. `jusik-research-optimizer.service`와 prospective monitor는 active였다. 운영 DB 수정 전 backup은 `/home/kwl/.local/share/jusik/portfolio-audit/20260925-autonomous-lab-42fsGz/runner-before.db`다.
- 운영 DB additive migration 뒤 backup과 task ID/status 132행이 완전히 일치했다(`completed=111, blocked=8, failed=13`). 고정 공학 READY spec의 enqueue와 runner 복구 결과는 아래 운영 확인에 추가한다.
- 사용자 소유 미추적 `HANDOFF.md`와 이전 worktree는 수정·삭제하지 않는다. 전체 backend의 기존 frozen replay 2개 실패를 성공으로 바꾸지 않는다.

다음 세션 시작: 이 파일, `docs/autonomous-trading-lab.md`, `docs/development-records/2026-09-25-autonomous-lab.md`를 읽고 Git/runner 현재 상태·운영 확인을 대조한 뒤 독립 reviewer receipt 구현부터 이어간다. 실제 투자 승격·주문은 여전히 승인되지 않았다.
