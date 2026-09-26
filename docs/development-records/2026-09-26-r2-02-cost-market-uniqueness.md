# R2-02 비용 계약 market 유일성 검증

- 상태: 진행 — 기존 BLOCKED 작업의 감독하 복구.
- 작업 slug: `r2-02-cost-market-uniqueness`
- 원 task: `roadmap-r2-02-cost-market-uniqueness-v1`
- 기존 worktree 기준: `e61df2fc8c2b2d56f09a6c6ee627900dc2524625`; 통합은 아직 없음.

## 범위와 근거

기존 scope reviewer는 `broker_cost_profiles.py`의 빈·중복 market 계약을 거부하는
오프라인 코드 수정만 승인했다. 실제 요율·계좌 비용·성과 계산·R2-02 완료 승인은 아니다.
현재 main과 기존 worktree source SHA가 승인 당시
`42bc99abab5ae585b5753b5f20fd565267d2aca95127c719096910c2aa4f8f2f`와 같다.

builder는 빈 market tuple 및 중복 market을 받아 계약을 만들고, manifest 검증도
중복 profile을 정상 builder로 재계산한 hash와 함께 받아들일 수 있다. 단일 구현자가
소스와 대응 테스트 두 파일만 수정하며 요율·정상 시장 선정·기존 유효 계약은 유지한다.

## 검증과 복구 조건

먼저 빈·중복 입력 및 hash를 다시 계산한 중복 manifest의 실패를 재현한다. 수정 뒤
focused pytest·Ruff·strict mypy와 독립 Sol review를 실행하고 local main 통합 후
다시 검사한다. 실제 PASS 증거에는 원 task ID, 구현 기준, 최종 commit, 두 파일 hash,
검사와 reviewer 식별을 기록한다. 현재는 검사를 통과했다고 주장하지 않는다.

기존 원 task의 상태는 `blocked`다. 과거 attempt `1934a7bed2034f0fb815052823c2091f`,
scope receipt 및 실패 근거는 불변으로 보존한다. 실제 구현·외부 독립 review 완료 후
기존 명시적 retry를 사용하며, 새 attempt는 새 변경이나 하위 agent 없이 실제 완료
증거를 검증·보고한다. 증거가 불충분하거나 수정이 추가되면 자체 승인하지 않는다.
원 `r2-01` FAILED는 이 작업에서 변경하지 않는다.

## 안전·기록

자동 runner는 별도 runner 수리 동안 pause 상태다. 데이터·금융 실험·실주문·PAPER/LIVE·
권한·credential·비용 정책·원격 push·Windows 종료는 변경하지 않는다.
사용자 `HANDOFF.md`는 보존하고 결과는 완료 시 date-specific handoff에 연결한다.
audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260926-roadmap-completion-review/`.
