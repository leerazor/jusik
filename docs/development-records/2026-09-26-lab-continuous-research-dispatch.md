# 연구 목적에 맞춘 지속 agent 운영 재설계

- 상태: 첫 구현·독립 검토·main 통합 검증 완료. 자동 운영 재개 결과는 외부 RUNTIME에 기록한다.
- 최종 통합 검증 시각: 2026-09-26T01:29:36Z.
- 작업 slug: `lab-continuous-research-dispatch`
- 조사 기준: `1fcf1f9`; 작업 기준 `aee6516`; 구현 `299e274`·보완 `be8e8b6`·타입 정리 `7878667`;
  main 통합 `9fae842`, 최종 `5b86cb0`.
- 범위: agent 활동 감사, 기존 지침의 목표/작업 선택 계약, 연구 준비 planner의 재진입과
  독립 scope 검토. 금융 전략·투자 기준·실제 주문·추가 과금은 변경하지 않는다.

## 활동 감사

2026-09-26 00:42~00:49Z에 Git·운영 DB와 프로세스를 읽기 전용으로 대조했다.

- 자동 제품 `1fcf1f9`가 00:32Z에 완료됐고 독립 review `5035b709b81a42e4b250f880f65c92ad`는
  00:35Z 완료다. 다음 discovery는 제안을 생성했으나 scope review가 거절했다.
- task 집계는 engineering completed 8/blocked 1, research completed 113/blocked 8/
  failed 13이다. completed research 분류 113건 중 101건은 `__planning__`, 실제 research
  task는 12건이었다. failed 13건도 planner 이력이다. planner 완료 attempt의
  `planning_waiting`은 88건이다. 이 집계를 완료된 실험·투자 검증으로 표현하지 않는다.
- paused=0, timer active였으며 실제 child·대기 cycle을 구분했다. timer는 cycle 이후
  120초에 실행하므로 cycle 사이의 inactive service만으로 장애라고 판단하지 않는다.
- `idle_status`의 오래된 `fixed_engineering_backlog_exhausted`와 실제 scope 진행이 달랐다.
- research universe와 prospective monitor도 active였다. 실제 universe 프로세스는 CUDA
  연구 모드이며 collection-only가 아니었다. 기본 optimizer DB의 completed 2,771건과
  insufficient 4건, 마지막 완료 00:07:02Z를 확인했다. 이 과거 탐색 결과는 현재 mandate의
  후보·PIT·prospective 검증으로 간주하지 않는다. 기존 서비스나 설정은 바꾸지 않았다.

## 원인과 재설계

기존 공학 backlog/discovery 분기가 먼저 반환해 `planning_enabled`의 roadmap planner가
호출되지 않는다. 실제 `eligible_areas - reserved_areas`는 r1-05/r2-01/r2-02였으므로
모든 연구 경로가 자료 부족이라서 멈췄다고 설명할 수 없다. 다만 area 적격만으로 실제
입력 준비가 증명되지는 않는다. 이전 조사가 보류한 단순 fallthrough를 하지 않고,
검증된 계획을 pending에 저장한 뒤 별도 scope reviewer PASS와 등록 시점 재검증을 요구한다.

8개 프로필·기존 서비스·planner 포함 active 4개 상한을 유지한다. 판단 기준을 agent
활동량에서 검증된 연구 기회·자료/회계 완전성·비용 차감 지표의 개선으로 연결한다.
설계 정본 `docs/autonomous-trading-lab.md` 17절에 운영 계약과 적용/후속 경계를 추가했다.
AGENTS와 연속 실행/runbook 문서는 이 계약을 참조한다. OpenAI Docs는 독립적이고
범위가 분명한 subagent 작업 및 검증 가능한 단계별 실행 원칙의 참고이며, API 이전이나
새 권한·과금의 근거로 사용하지 않았다.

## 이번 구현의 완료 조건

1. 기존 READY/구현 review를 보존하면서 연구 준비 planner를 fresh engineering discovery보다 먼저 호출한다.
2. 새 roadmap 제안은 독립 scope PASS 전 연구 task를 만들지 않는다.
3. receipt는 제안·evidence·planner attempt·fingerprint·HEAD·mandate·roadmap과 결속한다.
4. 등록 시 현재 입력·phase/area·예약·ID·cap·pause를 다시 검사하고 단 한 건만 원자 등록한다.
5. 거절·자료 부족·무효·같은 입력의 대기는 공학 fallback을 막지 않는다.
6. 상태 표시가 과거 idle과 현재 실행을 혼동하지 않는다. legacy DB와 과거 실패를 보존한다.

새 자동 연구 제안은 readiness·회계·데이터 진단과 offline 계약 개선 범위다.
일반 문구만으로 실험 사전등록, 수익성 평가, 기존 holdout 재사용, 전략 승격을 허용하지 않는다.
prospective 등록의 현재 mandate 호환성은 먼저 확인할 연구 준비 과제이며 OOS 실행이 아니다.

## 별도 읽기 전용 연구 준비 감사

이 세션에서는 scheduling 코드와 독립적으로 prospective 계약도 정적으로 확인했다.
기존 등록은 2026-09-14~2026-11-09의 56일 창과 선택 후보/입력/code identity를 고정한다.
현재 시점에 관측 창이 끝나지 않았으며 이번 감사에서는 OOS·체결·runtime DB를 읽거나
계산하지 않았다. 후보 수 정책·candidate-specific required return·현재 primary metrics
계약은 이 등록 코드에 완전히 표현돼 있지 않다. 기존 등록을 새 mandate에 맞는 것으로
소급 수정하지 않는다.

- `research_prospective_registration.py`: 선택 후보 identity·자동 승격 금지는 있으나
  현재 objective 전체·자료 등급·PIT eligibility를 증명하지 못한다.
- `research_prospective_readiness.py`: boundary 후보는 unverified이며
  `collector_implemented=false`, `evaluation_inputs_complete=false`다.
- `docs/research-future-observation-protocol.md`: 명시적으로 미등록 초안이다.
  원문/읽기 시작·종료·수신 시각 계약을 모든 시장 관측에 충족했다고 볼 수 없다.
- 판정: 현재 mandate의 `INVESTMENT_VALIDATED` 근거로 사용 불가. 코드 계약의 부족한
  항목은 offline 준비 과제로 개선할 수 있지만 기존 관찰 창·입력·평가 결과를 덮어쓰지 않는다.

정적 입력 pin: registration `a1159962bed624ea6ae1b0a0af75070a99066a225e43587a4f591a84b93a8121`,
readiness `94f16f6d682534042ddd5db9aad837201192b7d7c035bf8e53bd27c32824f4d0`,
protocol `72a34a0586232a33c5eb68f828d4284666f751e15ac4f3a3edd20ac7c0c40a35`,
mandate `22efba4714bc0baf65c56bdfd84dcdee91184a760a13d4d30c5a94486c264ab1`.
이 사실만으로 R7 phase를 열거나 새 실제 금융 실험을 enqueue하지 않는다.

## 검증

- 첫 RED: `test_eligible_roadmap_planning_precedes_fresh_engineering_discovery`가
  실제 run_once의 `discovery_selected` 조기 반환으로 실패했다.
- 감독 검토에서 legacy `finish_planning` 직접 등록 우회와 불확실 orphan의 다음 cycle
  소유권 상실 가능성을 찾아 구현자가 fail-closed/영속 hold 및 회귀 테스트로 보강했다.
- 별도 Sol 검토는 DB-bound scope 대신 호출 인자를 신뢰하는 등록 우회와, 승인 task의
  완료 followup이 독립 scope 없이 새 task를 등록하는 P1 두 건을 지적했다. `be8e8b6`에서
  3개 RED 재현을 보완하고 독립 재검토 PASS를 받았다. 기존 generic/legacy 계약은 유지했다.
- 최종 main `5b86cb0`: backend에서 `.venv/bin/python -m pytest
  tests/test_development_runner*.py tests/test_research_progress.py -q` 실행 결과
  **292 passed**, 81.38초. 의존성의 기존 deprecation warning 2개가 있으며 패키지는 변경하지 않았다.
- 변경 Python 7개 파일의 Ruff check·format check 통과. 변경 소스 3개의 `mypy --strict`,
  변경 테스트 4개의 `mypy --strict --follow-imports=silent` 통과. 기존 planning fixture 타입
  오류 8건도 `7878667`에서 타입 표기만 보완했고 독립 검토 PASS다.
- 운영 backup의 전용 복사본 `runner-migration-check.db`에서 기존 10개 테이블의
  **1,039개 행과 모든 기존 열 값**을 보존했다. main 코드로 반복 초기화도 동일했다.
  `roadmap_planning_scopes`, `roadmap_scope_attempts` 두 테이블만 추가되며 integrity `ok`다.
- code/review의 최신 child-owned turn context는 각각 `gpt-6-sol/high`였다. full-history
  routing helper는 과거 turn context 누락으로 검증 불가여서 PASS로 기록하지 않는다.
- 프런트엔드 변경이 없어 build는 실행하지 않았다. 전체 backend 검사나 실제 금융 실험을
  통과했다고 주장하지 않는다. 명령·결과 요약은 외부 `VALIDATION.md`에도 보존했다.
- 지침 독립 검토 P2: 기존 연구 제안 직접 enqueue 설명이 새 roadmap pending/scope 계약과
  충돌해 `60c3696`에서 generic research와 roadmap 설명을 분리했다.

## 남은 경계

- 구현·연구 scope reviewer의 일시 오류 재시도 일반화, no_work 경로/hash 증명,
  외부 readiness 변경에 따른 재평가는 후속 과제이며 이번 slice에 있다고 주장하지 않는다.
- 추가 확인: generic research completion은 `review_passed`를 요구하지만 자동 child는
  중첩 spawn을 할 수 없다. 이번 scope 검토를 구현 후 독립 review로 재사용하지 않는다.
  새 roadmap 산출물의 별도 완료 reviewer 연결은 후속 우선 과제다. 그 전에는 독립 검토를
  확보하지 못한 해당 task만 WAIT하며 공학 fallback을 계속한다. 전체 연구 lifecycle이
  이미 무인 완성됐다고 주장하지 않는다.
- 새 scope-approved task는 followup을 직접 등록할 수 없다. 다음 아이디어는 planner와
  독립 scope 검토가 다시 담당한다. 기존 prospective 등록과 현재 mandate의 부적합은
  정적 audit로만 확인했으며 이번에는 새로운 수익성 검증 결과가 없다.

## 소유·안전·재개

단일 Sol이 전용 worktree의 backend runner, store, planning scope 및 테스트 7개 파일을
담당했고 root는 문서·main 통합·운영을 담당했다. 새 수정 전에 실행 중 child가 없음을
확인해 pause했으며 timer는 유지했다. 최종 통합 검증과 산출물 보존 후 소유 worktree
`/home/kwl/projects/jusik-lab-continuous-research-dispatch`를 정상 제거했다. 소스 커밋과
`feat/lab-continuous-research-dispatch` 브랜치는 보존했고 전용 venv/cache만 함께 정리했다.
사용자 `HANDOFF.md`, 다른 worktree·과거 실패·투자 결과는 보존한다.

audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260926-continuous-research-dispatch/`.
SQLite online backup `runner-before-redesign.db`, integrity `ok`, SHA-256
`544d06364846febbced17ef41810f6738d5b8b4d8d2987baa22adc3ba86868c4`.
schema 변경은 additive, rollback은 dispatch pause 뒤 코드 revert이며 운영 DB를 과거
백업으로 덮어쓰지 않는다. 최종 통합 뒤 기존 설정으로 재개하고 실제 planner/scope 또는
공학 fallback을 외부 RUNTIME에 기록한다. 원격 push·Windows 종료는 수행하지 않는다.
handoff: `docs/handoffs/2026-09-26-continuous-research-dispatch.md`.
