# 외부 readiness producer/validator identity 오프라인 조사

- 상태: 오프라인 조사와 scope review 완료; future producer identity capture·atomic publication·scheduler 결속은 task-local `PENDING`.
- 기록 시각: 2026-09-28T01:48:12Z
- 작업 slug: `lab-external-readiness-producer-contract-investigation`
- 기준/통합: 조사 기준 local `main` `8d3d52298e631c6193257d3d644c3f211ee0e8dd`; 조사 기록은 local `main`에 통합.
- 범위: 기존 repo consumer와 고정 audit artifact를 읽기 전용으로 대조해 producer·validator identity, hash, publication 경계 및 지금 구현 가능한 범위를 확인했습니다. 네트워크·수집·credential·비용·외부 파일 수정·scheduler 변경·투자/데이터 조건 변경은 하지 않았습니다.

## 변경과 결정

- `backend/jusik/development_runner_readiness.py`의 v1 consumer는 task/attempt/scope, request criteria, artifact 원문 hash, producer/validator identity와 caller가 독립적으로 고정한 code hash를 확인합니다. `executed_collector_source_hash=null`은 `unqualified`이며, `bound`도 gate 승인이나 승격을 뜻하지 않습니다.
- expanded-universe audit의 `collector-current.sha256`은 저장된 현재 `collect.py` bytes와 일치하지만, 과거 실행 당시 hash는 증명하지 않습니다. `execution-provenance.json`의 `executed_collector_source_hash`는 `null`이고 사후 복원하지 않았습니다. `offline_validate.py`는 기록된 현재 source hash와 일치하나, v1 `validator_id`가 포함된 receipt는 없습니다.
- `collect.py`와 `offline_validate.py`는 결과를 직접 쓰거나 append합니다. 별도 `publish.py`의 원자 교체는 report/seed 게시이며 readiness receipt 계약이 아닙니다. `validation.json`의 8개 gate는 모두 `BLOCKED`입니다.
- 독립 scope review는 운영 readiness를 위한 producer publisher 구현을 `FAIL/PENDING`으로 판정했습니다. caller-provided hash를 원자적으로 포장하는 untrusted codec은 가능하지만, 기존 테스트 fixture에 synthetic publisher가 있고 실제 독립 사용처가 없어 효용이 낮습니다. 실행된 source identity를 신뢰하려면 실제 실행 전 고정된 source snapshot, trusted execution boundary, independently pinned expectation의 소유 경로가 먼저 필요합니다.
- 별도 roadmap scan은 R1/R2의 실제 자료·coverage·외부 계약 dependency 외에 새로 재현된 offline defect나 독립 READY 후보를 찾지 못했습니다. R2-02 `WAITING_EXTERNAL`의 재시도 조건도 바꾸지 않았습니다. terminal `no_work` 탐색은 반복하지 않았습니다.
- 새 provisional trust identity, pin owner, source allowlist 또는 data/investment condition은 적용·동결하지 않았습니다. 기존 v1 resource cap은 기술적 오프라인 한도로만 유지합니다. 기존 artifact hash와 gate status는 그대로 둡니다.

## 문서·계약 영향

- 사용자 문서: `docs/development-runner.md` 변경 없음. 현재 운영 설명이 trusted producer와 안정적·원자적 publication 경로를 선행조건으로 이미 명시합니다.
- 운영 문서: `docs/worktree-tasks.md`에 조사 완료, publisher scope-review 결과, 실제 blocker와 재개 조건을 추가했습니다.
- API·설정·데이터 계약: 변경 없음. 기존 v1 consumer schema, mandate, preregistration nulls, `execution_allowed=false`, OOS 경계와 8개 BLOCKED gate를 보존합니다.

## 검증

- `git fetch origin`과 `git rev-parse HEAD`, `git rev-parse origin/main` — 조사 전 최신 `main`과 `origin/main`이 `8d3d52298e631c6193257d3d644c3f211ee0e8dd`로 일치함을 확인했습니다.
- `rg`, `sed`, `nl`을 이용해 consumer, tests, roadmap, task registry, development-runner contract, 고정 local audit artifact와 writer 경계를 오프라인 조회했습니다.
- 중앙 routing `resolve/check` 및 reviewer helper preflight — plan·review 모두 설정된 model/role로 PASS했습니다. planner와 독립 scope reviewer는 읽기 전용 작업이었습니다.
- 테스트·린트·타입 검사는 실행하지 않았습니다. 코드 변경이 없는 조사·기록 작업입니다.
- 이 조사에서 network/provider 호출, 자료 수집, 외부 서비스, credential, 실제 지출, scheduler/service/queue 변경, PAPER/live 및 주문은 없었습니다.

## 안전·운영 상태

- 기존 audit는 읽기 전용으로 확인했습니다. 사라진 실행 당시 collector hash를 현재 source hash로 대체하거나 과거 artifact를 재발행하지 않았습니다.
- 별도 구현 worktree를 만들지 않았습니다. scope review가 독립 구현 효용과 신뢰 경계 미비를 이유로 운영 publisher를 보류했습니다. 기존 사용자 소유 루트 `HANDOFF.md`는 수정하지 않았습니다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/portfolio-expanded-universe-collection-gates-v1-2ea67734308a40eda685c1b0839576c6/`; 원시 응답·credential은 복사하지 않았습니다.
- 남은 blocker: trusted producer 실행 경계, producer/validator ID와 code SHA를 독립 pin하는 소유·전달 경로, consumer가 읽을 stable atomic receipt 경로가 실제로 정의되고 검증되어야 합니다. 이는 현 단계에서 사용자/프로젝트 trust-boundary 결정 또는 새로운 검증 가능한 producer artifact에 의존합니다.
- 다음 시작: 해당 trust anchor와 pin source가 제공됐는지 확인한 뒤 그 증거·publication contract만 새 scope review합니다. 그 전에는 external readiness binding과 8개 gate를 PENDING/BLOCKED로 유지하고 같은 no-work 탐색을 반복하지 않습니다.
