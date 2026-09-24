# Autonomous trading lab 구조와 독립 작업 진행

- 상태: 최소 구현 local main 통합·검증 완료; 독립 reviewer 자동 완료 경로는 후속
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
- runner 수정 전 1 failed와 후속 검토 지적의 추가 RED 4 failed·3 failed를 각각 확인했다. 같은 구현 소유자가 경계를 수정하고 독립 Sol reviewer가 최신 `1c64c13`을 재검토해 새 P1/P2 없이 최소 스케줄러 범위 통합 가능 판정을 냈다.
- lifecycle 구현 `fec44e9`, main 통합 `62e229b`: worker/main 각각 focused pytest 16개, Ruff check/format, mypy 통과. 초기 연구/PAUSED/RETIRED 전이, SQL guard와 append-only history를 구현했다. 독립 Sol review에서 IDEA pause 대상의 문서 불일치를 수정한 뒤 통합 가능 판정을 받았다.
- 운영 DB의 변경 전 snapshot을 private audit `runner-before.db`에 보존했다. mandate JSON SHA는 기존 `22efba4714bc0baf65c56bdfd84dcdee91184a760a13d4d30c5a94486c264ab1`과 동일하다.
- runner A 첫 구현 `f6000d4`: RED 실제 run_once 회귀 뒤 focused 119개·Ruff·strict mypy 통과. 독립 Sol review에서 공학 완료의 자기 보고 PASS, 새 commit/소유 경로 증거 부재(P1 2건), blocker 원자 기록·외부 event 재개·공통 프롬프트(P2 3건)을 지적했다. main 통합을 보류하고 같은 구현 소유자에게 수정을 돌렸다. 이 버전의 engineering DONE 결과를 신뢰 가능한 완료로 보고하지 않는다.
- A 최종 `1c64c13`, main 병합 `e6e90d4`: 오래된/완료된 선두를 구조화 blocker로 격리하고 같은 cycle에 독립 READY를 dispatch한다. legacy status는 canonical 7상태로 투영하며 blocker 일곱 필드와 명시적 external evidence identity 재개를 보존한다. 공학 task는 고정 spec만 받고 시작 HEAD 이후 현재 main HEAD의 정확한 소유 파일 변경·hash를 확인한다. rename의 출발 경로도 검사한다. 독립 reviewer가 없으면 `WAITING_EXTERNAL(independent_review_pending)`에 머물고 일반 event 재개로 구현을 반복하지 않는다. 이 상태는 `ENGINEERING_COMPLETE`나 `INVESTMENT_VALIDATED`가 아니다.
- A worker focused 124 passed·Ruff check/format·strict mypy·diff check 통과. main 통합 후 runner/planning/roadmap/lifecycle focused pytest 140 passed, Ruff check/format 8파일, strict mypy 5 모듈, diff check 통과. 프런트 변경은 없다. 전체 backend suite의 기존 frozen replay 실패 2건은 이 검사 범위에 포함하지 않았으며 해결됐다고 주장하지 않는다.
- 운영 roadmap SQLite는 migration 전 private snapshot과 비교해 task ID/status 132행이 동일하고 분포 `completed=111, blocked=8, failed=13`이었다. 새 상태 컬럼은 additive로 열렸고 현재 `paused=True`였다. 첫 조사 메모의 `completed 12`와 집계 범위가 일치하는지는 확인되지 않아 직접 비교하지 않는다.

## 운영 경계

- 수동 변경 시작 전에 roadmap runner pause와 service inactive를 확인했다. timer와 `jusik-research-optimizer.service`, prospective monitor는 유지했다. 검증·문서 커밋 뒤 고정 오프라인 spec 하나를 READY로 등록하고 roadmap runner를 `paused=False`로 재개했다. timer active, 연구 optimizer와 prospective monitor active를 확인했다. 병합된 신규 worktree 두 개는 감사 후 일반 `git worktree remove`로 정리했다.
- 첫 timer 실행은 Codex 요청의 `invalid_json_schema`로 종료 코드 1, 결과 파일 없이 `FAILED(codex_exit)`가 됐다. 비밀값은 출력하지 않았다. `Blocker.dependency_identity`와 top-level nullable 3개가 schema `required`에서 빠진 것이 원인이다. 실제 API 오류와 focused RED 2개를 확인한 뒤 `COMPLETION_SCHEMA`의 필수 목록만 고쳤다. 통합 후 focused pytest 142 passed, 변경 2파일 Ruff check/format, runner strict mypy 통과. 실패 attempt는 보존하고 명시적 retry로만 재개한다.
- 사용자 소유 미추적 `HANDOFF.md`와 기존 worktree는 보존한다.
- 실제 주문, 추가 결제, 권한 확대, credential 정책·투자 기준 완화, Windows 종료는 수행하지 않는다.
- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260925-autonomous-lab-42fsGz`.
