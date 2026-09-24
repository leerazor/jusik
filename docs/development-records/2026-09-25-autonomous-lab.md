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

- 제품 수정 전 `test_run_once_quarantines_stale_head_and_dispatches_independent_ready`가 1 failed로 결함을 재현했다. 실제 run_once와 fake child를 사용했고, 독립 작업 completed 기대와 달리 오래된 선두에서 blocked를 반환했다.
- 설계 독립 Sol review가 8개 프로필의 16항목·18후보 처리·TOML 7개 파싱을 확인했다. 세션 시각/외부 재시도/PAUSED 그림의 불일치 3건을 지적했고 문서를 수정했다.
- explore 2개와 plan 1개의 native routing 사후 감사는 역할·모델·독립 turn 기준 PASS였다.
- 변경 후 focused 검사, 코드 독립 review와 main 통합 결과는 후속 기록한다. 아직 실행하지 않은 검사를 통과로 표시하지 않는다.
- lifecycle 구현 `fec44e9`, main 통합 `62e229b`: worker/main 각각 focused pytest 16개, Ruff check/format, mypy 통과. 초기 연구/PAUSED/RETIRED 전이, SQL guard와 append-only history를 구현했다. 독립 Sol review에서 IDEA pause 대상의 문서 불일치를 수정한 뒤 통합 가능 판정을 받았다.
- 운영 DB의 변경 전 snapshot을 private audit `runner-before.db`에 보존했다. mandate JSON SHA는 기존 `22efba4714bc0baf65c56bdfd84dcdee91184a760a13d4d30c5a94486c264ab1`과 동일하다.

## 운영 경계

- 수동 변경 시작 전에 roadmap runner pause와 service inactive를 확인했다. timer 설정과 CUDA optimizer는 유지했다.
- 사용자 소유 미추적 `HANDOFF.md`와 기존 worktree는 보존한다.
- 실제 주문, 추가 결제, 권한 확대, credential 정책·투자 기준 완화, Windows 종료는 수행하지 않는다.
- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260925-autonomous-lab-42fsGz`.
