# 프로젝트 READY 작업 handoff

- Updated: 2026-09-28
- Workspace: `/home/kwl/projects/jusik`
- 이번 추가 작업 직전 local `main`: `bfe477b81bbe7a5736428be0e5eea83b0e5d57df`; `origin/main`: `a9ba2e4e8784d72fb93512881cf3d3be7b191ee0` (fetch 후 local main이 6 commits ahead). 이 handoff와 개발 기록을 closeout commit으로 저장합니다.
- 이전 handoff 작성 직전 local `main`: `254d149898de03c2e32ed9e3ba95e09233fd0c4c`; 당시 remote `main`은 해당 SHA의 조상이며 원격 전용 커밋은 없었습니다.
- 최근 관련 커밋: 코드 `d85f424c03936e5c0c90006f996dab8dbbc97e3c`, 계약 기록 `b294d944aa24ba849afd2e3e6af74e4083c1aa14`, 통합 종료 기록 `254d149898de03c2e32ed9e3ba95e09233fd0c4c`.
- 상태: bounded offline 기술 작업은 `ENGINEERING_COMPLETE/NOT_EVALUATED`입니다. 투자 성과나 자료 적격성을 평가하지 않았습니다.

## 2026-09-28 trust 결정 압축 및 GPU fixture 기술 검증

- 사용자 요청에 따라 trust-boundary 구현은 보류했습니다. [권고안](../development-runner-readiness-trust-boundary.md)은 첫 사용자 결정 하나로 압축되어 있습니다: producer/validator와 분리된 trust-root owner가 신뢰 기준을 통제하고 별도 run controller가 고정된 실행 snapshot과 source/output hash를 결속하도록 하는 역할 분리 권고입니다. 실제 담당자·권한과 독립 control channel은 아직 지정·검증되지 않아 publisher, attestation, pin, scheduler 결속은 계속 `PENDING`입니다. Attestation/publication, v1 bridge, hash/key 갱신·철회와 freshness, 과거 receipt, 실패·복구, scheduler 연결은 각각 후속 승인 결정으로 남겼습니다.
- [trust 결정 개발 기록](../development-records/2026-09-28-trust-boundary-priority-decision.md)과 [등록부](../worktree-tasks.md)의 `trust-boundary-priority-decision-v1`에서 결정 범위·대안·승인 경계를 확인합니다. 독립 문서 review와 routing post audit은 PASS이며 mandate·투자·데이터/OOS 기준은 바꾸지 않았습니다.
- 기존 `backend/tests/test_research_portfolio_gpu_stress.py::_request`의 4-point synthetic fixture와 기존 stress CLI만 이용해 seed `20260913`, block `2`, horizon `3`, 4096 scenario의 동일 request를 CPU와 CUDA에서 각각 한 번 실행했습니다. task-local Python 3.13.15 / PyTorch `2.11.0+cu128` 환경의 focused test는 `17 passed`; CPU/CUDA output 및 hash manifest가 일치했고 둘 다 exit 0입니다. 최종 pair audit SHA는 `35b8983c38a1e1a18c0bffa93b60ace3663bb93899fc5b88e4295190ed65d644`입니다. 독립 isolated-environment/artifact review, 최종 개발 기록·handoff review, explore/plan/code_small/review 두 회차의 routing post audit 모두 PASS했습니다.
- 측정값은 관측치일 뿐입니다: CPU/CUDA elapsed `0.085804s` / `0.361621s`, warmed CPU 2/8-thread `0.001976/0.001908s`, CUDA synchronized transfer-inclusive `0.002719s`. GPU utilization은 전후 `89%` / `46%`로 격리되지 않았고 표본도 3-step 단일 synthetic fixture입니다. 속도 우위나 throughput 결론을 내리지 않았고 OOS, 전략 튜닝, 투자 판단으로 사용하지 않았습니다.
- task-local venv는 worktree 격리를 위해 만들었으며 누락 dependency 보완을 위해 공개 package index에서 무료 패키지를 내려받았습니다. 초기 setup 중 `9 passed, 8 failed`는 Pydantic 누락에 따른 fixture setup 문제로 보존했고 dependency 설치 후 `17 passed`했습니다. 시장자료·유료 service·credential·운영 서비스 설정은 사용 또는 변경하지 않았습니다. `jusik-research-universe.service`는 inactive이며 설정 불변입니다.
- post-log routing audit은 기존 parent/child JSONL 증거로 확인했습니다. 마지막 reviewer audit은 parent `01a0dfc9-d8d7-7240-a2fb-5eeb6fa9e991`, child `01a0e662-1313-7e53-9e7f-873f1be4ba11`, role/model `review`/`gpt-6-sol`, actual type `review`로 PASS했습니다. 미확인 routing 증거 공백은 없습니다.
- 현재 남은 사용자 결정은 실제 independent trust-root owner, run controller, 권한 분리와 통제 채널의 지정·증명입니다. 그 승인 전 구현은 시작하지 않습니다. OOS 및 투자 평가는 이번 task에 포함되지 않았습니다. closeout 후에는 roadmap runner를 기존 `paused=false`로 복원하고, task-local venv와 완료 worktree를 정리합니다. 사용자 소유 루트 `HANDOFF.md`는 그대로 보존하며 이 dated project handoff만 갱신합니다.

## 2026-09-28 trust-boundary brief 준비

- 작업 기준 `main`/`origin/main`은 `a9ba2e4e8784d72fb93512881cf3d3be7b191ee0`로 같았습니다. 전용 branch commit `656f536201d021fcda35535a12b8e2abddfaf6bb`가 local `main` merge commit `cfd3ceb0b649e2b00338a7721b4bef4968d20679`에 통합됐습니다. 원격 push는 하지 않았습니다.
- [설계 초안](../development-runner-readiness-trust-boundary.md)은 미승인·미적용입니다. 독립 review 뒤 source-hash pin만으로 실제 실행과 receipt SHA를 증명할 수 없고, 최초 trust-root bootstrap 및 오프라인 철회 freshness를 별도 확인해야 한다는 경계를 반영했습니다. 조건부 후보는 독립 reviewer 분리가 확인될 경우의 B안이며, authenticated execution-to-receipt 증거가 없으면 `PENDING`입니다. publisher·trust pin·execution attestation·scheduler/OOS는 구현하지 않았습니다.
- 결과·사용자 결정 목록: [작업 등록부](../worktree-tasks.md)의 `lab-external-readiness-trust-boundary-decision-brief` 및 [개발 기록](../development-records/2026-09-28-lab-external-readiness-trust-boundary-decision-brief.md).
- 독립 review 최종 결과: 추가 중대 지적 없음. routing/preflight, `git diff --check`, 변경 문서 링크 확인은 통과했고, 코드 테스트는 문서 전용 변경이라 실행하지 않았습니다. collaboration host가 parent/child JSONL 경로를 노출하지 않아 post-log helper audit은 미실행입니다.
- 현재 queue 조사: roadmap runner 191 task, queued/running 0, `fixed_engineering_backlog_exhausted`; standard runner 45 task, queued/running 0. 추가 READY는 발견되지 않았으며 동일 discovery를 반복하지 않았습니다. closeout에서 roadmap runner는 기존 `paused=false`로 복구했고, timer active/service inactive입니다. standard runner는 paused로 유지합니다.
- 통합된 SHA를 작업 등록부·개발 기록에 반영했고, 문서 검증과 tracked tree clean 확인을 마쳤습니다. 다음 세션은 현재 runner/service 상태를 확인하고, 사용자 결정 전 trust 선택을 적용하지 않습니다. held-band OOS 및 외부 readiness 결속은 각 task만 `PENDING/BLOCKED`로 유지합니다.

## 2026-09-28 후속 producer/validator 조사

- offline 조사와 독립 scope review를 마쳤습니다. 결과는 [작업 등록부](../worktree-tasks.md)의 `lab-external-readiness-producer-contract-investigation` 및 [개발 기록](../development-records/2026-09-28-lab-external-readiness-producer-contract-investigation.md)에 남겼습니다.
- 보관된 `collector-current.sha256`은 현재 `collect.py`와 일치하지만 과거 실행 hash가 아닙니다. `executed_collector_source_hash`는 계속 null입니다. 기록된 validator hash는 현재 validator bytes와 일치하지만 v1 `validator_id` receipt가 없습니다. producer/validator 출력은 readiness receipt로 원자 게시되지 않으며 8개 gate 모두 `BLOCKED`입니다.
- Scope review는 운영용 producer publisher 구현을 `FAIL/PENDING`으로 판정했습니다. self-reported identity를 직렬화하는 untrusted helper는 신뢰를 만들지 못하고 현재 synthetic test fixture와 중복됩니다. 신뢰 경계를 정하거나 독립적으로 제공된 producer execution evidence가 생기기 전 scheduler 결속도 진행하지 않습니다.
- 동일한 no-work 탐색을 반복하지 않고 별도 roadmap 범위만 확인했습니다. 새로 재현된 offline defect나 독립 READY 후보는 발견되지 않았습니다. 검토한 R1/R2 자료·coverage 항목과 R2-02 WAITING_EXTERNAL은 각 기존 의존성을 유지합니다.
- 새 trust identity나 pin owner를 provisional로 정하지 않았습니다. 실제 재개에는 trusted execution source/snapshot과 producer·validator 기대값을 독립 pin하는 소유·전달 경계가 필요합니다. 이는 mandate·최종 데이터 정책 변경이 아니라 trust-boundary 선택이므로, 해당 소유자가 정해지면 그 contract만 새 scope review합니다.
- 조사 중 외부 호출·자료 수집·비용·credential·scheduler/queue/service 변경·PAPER/live·주문은 없었습니다. 별도 구현 worktree를 만들지 않았습니다.

## 완료·검증된 작업

- `lab-external-readiness-binding-v1`은 [작업 등록부](../worktree-tasks.md)와 [개발 기록](../development-records/2026-09-27-lab-external-readiness-binding.md)에 정리돼 있습니다. Strict offline receipt parser/validator, safe artifact reader, identity/hash binding 및 자원 상한을 통합했습니다.
- 검증: 집중 pytest 164 passed, Ruff check, Ruff format check, strict mypy, `git diff --check`, 독립 reviewer PASS.
- provisional 기술 resource cap은 receipt 외 artifact 최대 128개, receipt 포함 전체 256 MiB, 파일당 32 MiB, streaming chunk 64 KiB입니다. 이 상한은 프로세스 보호용 기술 값이며 데이터·투자 acceptance 기준이 아닙니다.
- 실제 producer/scheduler 결속은 PENDING입니다. 현재 executed collector source hash가 없고 readiness 8개 gate는 모두 BLOCKED입니다. trusted producer identity와 안정적·원자적 publication 경로가 확보되기 전에는 scheduler 연결을 진행하지 않습니다.

## 남은 검증과 운영 상태

- held-band `FINAL_VALIDATION`/OOS는 승인된 preregistration과 그 뒤에 확보되는 적격 미래 자료가 생길 때까지 PENDING/BLOCKED입니다. 등록·승인·실행 허용 상태를 승격하지 않습니다.
- roadmap priority 4 static prospective mandate audit는 완료됐습니다. 현재 독립 READY registry task는 확인되지 않았습니다. 기존 blocked/review 대기 항목과 그 재개 조건은 그대로 유지합니다.
- 같은 terminal `no_work` discovery를 반복하지 않습니다. 신규 publication evidence 또는 독립 READY task가 생길 때 기존 절차로 재개합니다.
- 개발 과정에서 외부 producer/scheduler, queue/service, mandate, preregistration, 자료 기준, runner 설정은 변경하지 않았습니다. 비용·credential·provider 접근·운영 DB·PAPER/live·주문은 사용하지 않았습니다.

다음 세션은 이 handoff와 `docs/worktree-tasks.md`를 읽고 `git status --short`, `git worktree list`, 최신 local `main`을 확인한 뒤 새 증거 또는 READY 항목이 있는지 판단합니다.
