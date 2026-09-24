# Autonomous trading lab 진행 인계

- 갱신: 2026-09-25 UTC 기준 진행 중.
- 저장소: `/home/kwl/projects/jusik`, `main`.
- 목표: 현재 구조와 지침을 토대로 소수의 agent 프로필을 설계하고, BLOCKED/WAITING 작업 뒤의 독립 READY가 실제 진행되는 최소 구현을 검증한다. 실제 주문·PAPER 승격·추가 결제·권한/credential/투자 기준 완화는 포함하지 않는다.

## 검증된 변경

- 설계 정본 `docs/autonomous-trading-lab.md`에 8개 논리 프로필, 기존 18개 후보 처리, 각 프로필 16항목, 통신·task/strategy 상태·모델·예산·충돌·소유권을 기록했다.
- 지침·설정은 총 active 4개(주 agent + 하위 3개), Sol 중심 복잡한 구현, Luna 반복 작업, 선택적 Astra 진단으로 병합했다. 과거 종료 창을 active 지시에서 분리했다.
- `backend/jusik/strategy_lifecycle.py`의 offline SQLite registry를 `62e229b`로 main에 통합했다. 초기 연구/중단/복원/폐기만 지원하고 투자 승격은 차단한다. worker/main focused pytest 16개, Ruff, mypy와 독립 Sol 검토를 통과했다.
- runner A의 최초 실제 `run_once` 재현은 수정 전 1 failed였다. 오래된 선두 영역이 독립 READY를 막았다. 첫 수정 `f6000d4`의 focused 119개·Ruff·mypy는 통과했지만 독립 검토에서 P1 2건, P2 3건이 나와 통합을 보류하고 동일 소유자가 수정 중이다.

## 현재 상태와 다음 행동

- A 작업: `/home/kwl/projects/jusik-lab-task-scheduling`, `feat/lab-task-scheduling`. 추가 작업: 독립 review 없이 ENGINEERING_COMPLETE 금지, 새 commit/지정 소유 파일 변경 증명, blocker 원자 기록, event evidence-change 재개, 작업자 수·모델 프롬프트 정정. 수정 검증·독립 재검토 후 local main 병합.
- roadmap runner는 수동 변경 중 `paused=1`, service inactive, timer active이다. CUDA optimizer는 active로 유지한다. 운영 DB 수정 전 backup은 `/home/kwl/.local/share/jusik/portfolio-audit/20260925-autonomous-lab-42fsGz/runner-before.db`다.
- 병합 후 격리된 fake-child 테스트와 main의 focused runner/lifecycle/governance 검사, 실제 운영 DB의 additive migration·원래 작업 보존을 확인한다. 고정 공학 READY spec의 안전한 enqueue·runner 복구 여부는 검토 결과에 따라 결정하고 정확한 상태를 기록한다.
- 사용자 소유 미추적 `HANDOFF.md`와 이전 worktree는 수정·삭제하지 않는다. 전체 backend의 기존 frozen replay 2개 실패를 성공으로 바꾸지 않는다.

다음 세션 시작: 이 파일, `docs/autonomous-trading-lab.md`, `docs/development-records/2026-09-25-autonomous-lab.md`를 읽고 Git/runner 현재 상태와 A 수정·review 결과를 대조한 뒤 독립 READY 재현부터 이어간다.
