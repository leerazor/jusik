# 외부 readiness trust-boundary 결정안 준비

- 상태: 준비용 설계와 독립 검토 완료; 사용자 trust-boundary 결정 및 실행 증거 경로는 `PENDING`입니다.
- 기록 시각: 2026-09-28T04:19:30Z
- 작업 slug: `lab-external-readiness-trust-boundary-decision-brief`
- 기준/통합: `a9ba2e4e8784d72fb93512881cf3d3be7b191ee0` / merge commit `cfd3ceb0b649e2b00338a7721b4bef4968d20679`
- 범위: 실행 actor, independently pinned producer/validator hash, task/attempt부터 실제 실행 snapshot과 receipt SHA까지의 증명, key/hash 갱신·철회, failure/recovery, 운영 부담과 결정 항목을 비교하는 미승인 설계 문서를 작성했습니다. publisher, execution attestation, trust pin, scheduler 결속, mandate·투자·자료/OOS 조건은 구현하거나 변경하지 않았습니다.

## 변경과 결정

- `docs/development-runner-readiness-trust-boundary.md`에 B안(보호된 독립 reviewer manifest)을 최소 비용의 조건부 후보로 두고, 실행과 receipt SHA를 인증하는 별도 evidence가 없으면 `PENDING`이라는 결론을 기록했습니다. A안 서명 attestation, C안 분리 host/service, D안 self-report와 trust-root bootstrap, rotation/revocation, 철회 freshness, fail-closed·복구, 검증 fixture, 운영 부담을 비교했습니다.
- 독립 review가 발견한 세 경계를 반영했습니다: v1은 receipt의 hash claim을 독립 기대값과 대조할 뿐 실제 실행 주체를 인증하지 않음; 최초 trust root bootstrap/배포 소유자가 별도로 필요함; offline verifier는 신뢰 가능한 최신 철회 generation/유효기간을 확인해야 하며 stale/missing/rollback이면 실패해야 함.
- `docs/development-runner.md`에서 초안으로 연결하고, `docs/worktree-tasks.md`에 설계 완료·남은 승인과 재개 조건을 기록했습니다.
- provisional 가정은 없습니다. 권고 및 선택지는 운영 신뢰 기준으로 승인·적용되지 않았습니다. v1 `bound`는 gate 승인이 아니며 8개 gate, held-band FINAL_VALIDATION/OOS, null preregistration fields, `execution_allowed=false` 상태를 유지합니다.

## 문서·계약 영향

- 사용자 문서: 해당 없음. 사용자 동작이나 공개 API를 바꾸지 않았습니다.
- 운영 문서: `docs/development-runner.md`에 미승인 설계 링크를 추가하고 작업 등록부를 갱신했습니다.
- API·설정·데이터 계약: 변경 없음. 새 schema, trust root, key, manifest, publisher, queue/config 또는 artifact를 만들지 않았습니다.

## 검증

- 중앙 routing `resolve/check`와 supervisor review preflight — `role.review`, `gpt-6-sol/high`, `fork_turns=none` PASS. Collaboration host가 실제 parent/child JSONL 경로를 제공하지 않아 supervisor helper의 post-log audit은 실행하지 않았으며 통과했다고 주장하지 않습니다.
- 독립 review — 실행/receipt attestation, trust-root bootstrap, 철회 상태 freshness 누락을 단계적으로 지적했고 모두 반영했습니다. 최종 read-only 재검토는 추가 중대 지적 없음.
- `git diff --check`, 변경 문서 내부 링크 대상 — PASS. 코드가 바뀌지 않아 pytest, lint, type check는 실행하지 않았습니다.
- roadmap runner — 191개 task, queued/running 0, `fixed_engineering_backlog_exhausted`, discovery terminal/stale identity. standard runner — 45개 task, queued/running 0 (35 completed, 7 blocked, 2 interrupted, 1 failed). 새 독립 READY task는 확인되지 않았습니다. 같은 discovery를 반복하지 않았습니다.

## 안전·운영 상태

- free local 조사 외 market-data 수집, credential 사용, 비용, 외부 service, PAPER/live, 주문, queue/config/data 변경은 없습니다. 최신 `main` 확인을 위해 `git fetch origin`만 실행했습니다. 작업 중 자동 개발 service는 정지했습니다. tracked 문서 변경을 마치고 나면 roadmap runner의 문서 수정 전 `paused=false`와 timer 상태를 복구하며 standard runner의 기존 paused 상태를 유지합니다.
- 전용 문서 worktree `/home/kwl/projects/jusik-readiness-trust-boundary`, branch `docs/readiness-trust-boundary`를 사용했습니다. 기존 소유 worktree는 수정하지 않았습니다. 사용자 소유 루트 `HANDOFF.md`도 그대로 보존했습니다.

## 증거와 재개

- audit: 기존 offline audit만 참고했으며 새 artifact는 없습니다.
- 남은 결정: 실행 actor와 신뢰 범위, 독립 hash owner와 최초 trust-root bootstrap/update 권한, 실행-결과 attestation 및 v1 bridge 승인 범위, repo reviewer 분리의 충분성, 철회 최대 age와 rollback 대응, key/hash 철회 및 과거 receipt 정책, fail-closed/recovery owner, 검증 뒤 scheduler 재평가 범위.
- 다음 시작: 이 미승인 초안을 읽고 사용자가 trust-boundary 항목을 결정했는지 확인합니다. 결정 또는 새로운 독립 실행 증거가 없으면 publisher/scheduler는 PENDING으로 두고 동일 no-work discovery를 반복하지 않습니다.
