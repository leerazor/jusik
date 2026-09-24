# Autonomous trading lab 구조와 독립 작업 진행

- 상태: 진행
- 작업 slug: `autonomous-lab`
- 기준: `01d7901`
- 범위: 현재 구조·적용 지침 분석, 역할 설계, 기존 runner의 task starvation 회귀·최소 구현, offline strategy lifecycle guard.

## 확인한 근거

- 운영 task snapshot: blocked 8개, completed 12개, running 0개. CUDA optimizer는 active였다.
- `_next_task`는 blocked dependency를 건너뛰지만 이후 `run_once`의 무효 roadmap 검사가 선두 task를 격리하지 않아 뒤의 READY를 막을 수 있다.
- 기존 PAPER는 내부 simulation이며 KIS 모의주문 submit adapter는 조사한 경계에 없다.
- 역할·통신·상태·모델·소유권·budget·충돌 분석은 [설계 정본](../autonomous-trading-lab.md)을 따른다.

## 실행과 검증

구현 전 재현, 변경 후 focused 검사, 독립 review와 main 통합 결과를 이 절에 기록한다. 아직 실행하지 않은 검사를 통과로 표시하지 않는다.

## 운영 경계

- 수동 변경 시작 전에 roadmap runner pause와 service inactive를 확인했다. timer 설정과 CUDA optimizer는 유지했다.
- 사용자 소유 미추적 `HANDOFF.md`와 기존 worktree는 보존한다.
- 실제 주문, 추가 결제, 권한 확대, credential 정책·투자 기준 완화, Windows 종료는 수행하지 않는다.
- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260925-autonomous-lab-42fsGz`.
