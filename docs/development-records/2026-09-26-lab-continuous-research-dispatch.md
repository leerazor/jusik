# 연구 목적에 맞춘 지속 agent 운영 재설계

- 상태: 설계 완료·구현 중
- 작업 slug: `lab-continuous-research-dispatch`
- 조사 기준: `1fcf1f9`; 작업 기준 `aee6516`, 통합은 검증 후 기록한다.
- 범위: agent 활동 감사, 기존 지침의 목표/작업 선택 계약, 연구 준비 planner의 재진입과
  독립 scope 검토. 금융 전략·투자 기준·실제 주문·추가 과금은 변경하지 않는다.

## 활동 감사

2026-09-26 00:42~00:49Z에 Git·운영 DB와 프로세스를 읽기 전용으로 대조했다.

- 자동 제품 `1fcf1f9`가 00:32Z에 완료됐고 독립 review `5035b709b81a42e4b250f880f65c92ad`는
  00:35Z 완료다. 다음 discovery는 제안을 생성했으나 scope review가 거절했다.
- task 집계는 engineering completed 8/blocked 1, research completed 113/blocked 8/
  failed 13이다. failed 13건은 planner 이력이며 완료 집계도 투자 검증을 뜻하지 않는다.
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

## 검증

- 첫 RED: `test_eligible_roadmap_planning_precedes_fresh_engineering_discovery`가
  실제 run_once의 `discovery_selected` 조기 반환으로 실패했다.
- 구현/독립 검토/main 검사: 진행 중. 아직 완료로 표시하지 않는다.
- 계획만 한 후속: 구현 review의 일시 오류 재시도 일반화, no_work 경로/hash 증명,
  외부 readiness 변경에 따른 재평가. 이번 slice에 있다고 주장하지 않는다.

## 소유·안전·재개

단일 Sol이 `/home/kwl/projects/jusik-lab-continuous-research-dispatch`의 backend runner,
store, planning 및 전용 scope seam과 테스트를 담당한다. root는 문서·main 통합·운영을
담당한다. 새 수정 전에 실행 중 child가 없음을 확인해 pause했으며 timer는 유지했다.
사용자 `HANDOFF.md`, 다른 worktree·과거 실패·투자 결과는 보존한다.

audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260926-continuous-research-dispatch/`.
SQLite online backup `runner-before-redesign.db`, integrity `ok`, SHA-256
`544d06364846febbced17ef41810f6738d5b8b4d8d2987baa22adc3ba86868c4`.
schema 변경은 additive, rollback은 dispatch pause 뒤 코드 revert이며 운영 DB를 과거
백업으로 덮어쓰지 않는다. 최종 통합 뒤 기존 설정으로 재개하고 실제 planner/scope 또는
공학 fallback을 외부 RUNTIME에 기록한다. 원격 push·Windows 종료는 수행하지 않는다.
