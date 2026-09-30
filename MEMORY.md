# 프로젝트 공통 메모리

이 파일은 세션·작업자 사이에서 공유하는 짧은 탐색 색인입니다. `AGENTS.md`의 시작 절차로 읽습니다. 별도 메모리 서비스나 Codex 전역 자동 메모리 설정은 사용하지 않습니다.

## 공통 맥락과 원본

| 기억할 맥락 | 판단 전에 확인할 원본 |
| --- | --- |
| 개발 시간·비용을 줄이고 검증 가능한 비용 차감 수익률을 우선합니다. | [목표와 우선순위](docs/autonomous-trading-lab.md#17-목표-기반-지속-운영), [현재 시간·지출 제약](docs/continuous-development-session.md) |
| 작업 순서·경로·유용성 평가는 workflow, 시스템 경계·진입점은 구조 안내에서 찾습니다. | [프로젝트 workflow](docs/project-workflow.md), [구조 안내](docs/architecture.md) |
| 새 연구의 조건과 과거 실험의 고정 조건을 구분합니다. 기술 완료가 투자 검증 완료는 아닙니다. | [현재 연구 조건](docs/research-mandate.md), [조건 JSON](docs/research-mandate.json), [투자 로드맵](docs/investment-development-roadmap.md) |
| 작업 소유권·진행 상태·재개 조건은 작업별 기록을 따릅니다. | [작업 등록부](docs/worktree-tasks.md), [개발 기록 기준](docs/development-records.md) |
| 모델 선택·도구 사용과 실행기 상태는 실행 시 확인합니다. | [agent 도구](docs/agent-tooling.md), [중앙 모델 선택](.codex/model-routing.json), [실행기 운영](docs/development-runner.md) |

## 필요한 맥락만 읽는 순서

1. `git status --short`, `git worktree list`로 현재 checkout과 병행 작업을 확인합니다. 구조 안내와 적용되는 하위 `AGENTS.md`를 읽습니다.
2. 아래 검색으로 등록부의 제목·상태를 훑고 활성·차단 후보와 관련 slug를 고릅니다. 상태 줄의 과거 완료·보류 설명을 현재 진행으로 단정하지 말고, 관련 항목의 소유 경로와 실제 worktree를 대조합니다.
3. 해당 항목부터 다음 `##` 제목 직전까지만 읽고, 연결된 개발 기록·인계에서 결정 이유·검증·다음 행동을 확인합니다. 작업을 지정받았다면 slug 검색부터 시작하되 병행 작업의 소유 경로 확인은 생략하지 않습니다.
4. 코드·정책 변경은 연결된 원본과 필요한 코드·테스트를 확인한 뒤 진행합니다. 같은 세션에서 이미 확인했고 바뀌지 않은 자료는 반복해서 읽지 않습니다.

```bash
rg -n '^## |^- 상태:' docs/worktree-tasks.md
rg -n -F '작업-slug' docs/worktree-tasks.md
```

제목·상태 출력도 길면 `rg -n -B 2 '^- 상태:.*(진행|준비|검증|통합 대기|차단|대기|보류|WAITING|PENDING)' docs/worktree-tasks.md`로 후보를 좁힙니다. 이 검색은 상태 분류기가 아니므로 소유 경로가 겹치는 작업은 제목·관련 경로 검색으로도 확인합니다. 관련 항목이 없을 때만 검색 범위를 넓히며 등록부·개발 기록·인계 전체를 한 번에 출력하지 않습니다.

## 재사용할 결정의 진입점

아래는 전체 활성 작업 목록이 아닙니다. 현재 상태와 새 작업은 항상 등록부에서 확인합니다.

- 새 미국 연구의 `LIME`·`MDA` 제외와 과거 결과 보존: [정책 적용 기록](docs/development-records/2026-09-30-exclude-lime-mda-us-research.md), [해당 인계](docs/handoffs/2026-09-30-exclude-lime-mda-us-research.md). 새 실행의 최종 조건은 현재 연구 조건과 JSON에서 확인합니다.
- 새 제외 정책의 미국 1년 자료는 [준비·결손 판정](docs/development-records/2026-09-30-us-exclusion-pilot-readiness.md)을 재사용합니다. 같은 27개 요청을 반복하지 않으며, 요청 제외 25종목·사건 관측시각 결손·우선주 분류 누락을 [인계의 재개 조건](docs/handoffs/2026-09-30-us-exclusion-pilot-readiness.md)에 따라 해결합니다. collector 완료는 자료·성과 적격이 아닙니다.
- [v3 분류 수정](docs/development-records/2026-09-30-us-preferred-classification.md) 후 [ICUI 보완 인계](docs/handoffs/2026-09-30-us-icui-bounded-gap.md)의 캐시140개를 재사용합니다. ICUI 272세션 확보, 기존 실패24·사건125 관측시각 결손은 유지합니다. 다음은 AOS 배당 원문이며 모의 출력 연구 투입과 같은 요청 반복은 금지합니다.
- 상장 전 결손과 identity 근거를 다시 조사하기 전: [기존 범위 검토](docs/development-records/2026-09-30-listing-identity-scope-review.md). 기존 조사 완료를 데이터 acceptance 완료로 해석하지 않습니다.
- 자동개발 대기·재개 진단을 반복하기 전: [대기 복구 기록](docs/development-records/2026-09-29-wait-handoff-recovery.md), [연속 실행 원칙](docs/continuous-development-session.md#continuous-execution-rule). 실제 실행기 상태는 운영 명령으로 다시 확인합니다.

- ECOS 환율 대조는 공개 sample로 최대 10개 날짜를 확인하는 [진단 CLI](docs/ecos-fx-comparison.md)를 사용합니다. [실제 조회·통합 근거](docs/development-records/2026-09-30-ecos-fx-comparison.md)를 먼저 확인하며, 공표시점·수정 이력 미확인 자료를 과거 성과 입력으로 승격하지 않습니다.
- ECOS 공식 항목·환율 산정 기준은 [원천 계약 기록](docs/development-records/2026-09-30-ecos-fx-source-contract.md)에서 확인합니다. [자동 후속 실행 인계](docs/handoffs/2026-09-30-ecos-fx-source-contract.md)의 중복 실행 방지·재개 조건을 읽고 동일 조사를 반복하지 않습니다.
- 전방 관찰의 `external_status=[]`는 현 소비 경로에서 결함이 확인되지 않았습니다. 현재 집계를 과거 cutoff에 붙이는 변경은 [감사에서 기각](docs/development-records/2026-09-30-external-context-audit.md)했습니다. [재개 사건](docs/handoffs/2026-09-30-external-context-audit.md) 없이 같은 후보를 반복 조사하지 않습니다.

## 최신성과 충돌 처리

- 메모리는 요약·검색 수단이며 새 승인이나 정책 원본이 아닙니다. 현재 사용자 지시·적용 지침과 검증한 Git·코드·계약·실행 상태를 우선하고, 충돌한 요약은 근거를 확인한 뒤 수정합니다. 과거 동결 실험에는 당시 계약을 유지합니다.
- 인계는 해당 slug의 등록부 링크와 기록 시각·대상 커밋을 대조해 고릅니다. 파일명 날짜·수정 시각만으로 최신 작업이나 현재 운영 상태를 판단하지 않습니다.
- 루트 `HANDOFF.md`는 사용자 소유 또는 다른 작업의 과거 기록일 수 있습니다. 현재 작업에 맞는지 먼저 확인하고, 충돌하면 그대로 보존하며 등록부가 연결한 `docs/handoffs/` 인계를 사용합니다.
- 과거 검사 통과는 기록된 범위·커밋에 대한 결과입니다. 재사용 전에 영향 파일·조건이 같은지 확인하고, 달라졌거나 증거가 부족하면 필요한 검사만 다시 실행합니다. 서비스·큐 상태는 저장된 인계로 대신하지 않습니다.

## 갱신과 분량

- 공통 결정이나 탐색 경로가 바뀔 때만 supervisor가 근거 문서와 함께 이 색인을 갱신합니다. 작업자는 자기 작업 기록을 남기고 통합 시 반영할 공통 변경을 전달합니다.
- 이 파일은 80줄·8 KiB 이내로 유지합니다. 결정에는 원본 링크를 붙이고 오래된 항목은 작업별 영구 기록을 보존한 채 색인에서 정리합니다. 모든 완료 이력·검사 로그·실시간 작업 목록을 복제하지 않습니다.
- 비밀값·계좌 식별자·원시 응답은 저장하지 않습니다. 모델명·설치 버전·수익률·runner 상태처럼 변하는 값은 정본이나 조회 방법으로 연결합니다.
