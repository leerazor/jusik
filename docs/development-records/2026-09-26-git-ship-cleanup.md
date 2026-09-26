# Main 동기화와 완료 worktree 정리

- 상태: 완료 worktree 정리 완료. 이 기록의 commit·main 반영·push 결과는 아래 최종 audit에 별도로 기록합니다.
- 기록 시각: 2026-09-26T11:18:00Z
- 작업 slug: `git-ship-cleanup-20260926`
- 기준: `f5b05433e09a85df88fcfccd16af66b015b6a3b9`
- 범위: 기존 개발 커밋의 원격 반영 확인, 완료된 작업 폴더 정리, 결과 기록의 커밋과 main push. 새 제품 구현·미검토 초안 통합·기존 실패 수정은 포함하지 않습니다.

## 변경과 결정

처음 로컬 표시는 `main...origin/main [ahead 169]`였지만 실제 fetch 뒤 로컬과 원격은 이미 기준 SHA로 같았습니다. 정상 push는 `Everything up-to-date`였으며, 이 단계에서 169개 커밋을 새로 전송하지 않았습니다. 기존 제품 작업은 이미 커밋돼 있어 빈 커밋을 만들지 않습니다. 이번 정리 기록만 명시적으로 선택해 `docs/git-ship-cleanup-20260926`에서 커밋한 뒤 main으로 fast-forward하고 push합니다.

모든 worktree의 HEAD ancestry, tracked/untracked 변경, ignored 파일, 작업 기록과 프로세스 사용을 확인했습니다. 완료가 입증된 폴더만 일반 `git worktree remove`로 제거했습니다. 강제 제거와 브랜치 삭제는 하지 않았습니다. 제거된 것은 재생성 가능한 checkout·venv·캐시이며, 커밋·브랜치와 기존 외부 검증 산출물은 보존합니다. 환경 버전과 고정 의존성 해시는 audit에 남겼습니다.

이하 경로는 `/home/kwl/projects/jusik-` 뒤의 suffix입니다.

### 제거한 7개

| Worktree suffix | 보존한 HEAD | 완료 근거 |
| --- | --- | --- |
| `lab-discovery-765902aaadea32298caafb244b05450b` | `62dd1add951f` | 독립 reviewer를 거친 engineering 완료 |
| `lab-engineering-failed-candidate-recovery` | `8aef418038c9` | main 통합·독립 검토·복구 경로 검증 |
| `lab-failed-output-digest` | `c85a1a56c6a9` | main 통합·집중 검사·독립 검토 |
| `lab-independent-review-receipt` | `f954568fa4ca` | main 통합·집중 검사·독립 검토 |
| `lab-lifecycle-receipt-revision-guard-format` | `9926ebb9f365` | AST 동일 서식 변경·최종 독립 검토 |
| `lab-lifecycle-receipt-revision-guard-spec` | `c6d848cf9fc9` | spec·제품 통합과 별도 완료 reviewer |
| `lab-paper-execution-fill-fee-spec` | `8a06611111a7` | spec·제품 통합과 별도 완료 reviewer |

모든 브랜치는 그대로 남아 있으므로 필요하면 해당 브랜치로 worktree를 다시 만들 수 있습니다. 삭제된 가상환경·캐시는 고정된 의존성으로 재생성해야 합니다. 검증 결과는 기술 완료 근거이며 투자 검증을 뜻하지 않습니다.

### 보존한 11개

| Worktree suffix | 보존 이유 |
| --- | --- |
| `lab-discovery-calendar-duplicate-59892f7d` | HEAD가 main의 조상이 아닌 미병합 이력 |
| `lab-paper-execution-cancel-claim-spec` | HEAD가 main의 조상이 아닌 미병합 이력 |
| `lab-paper-execution-restart-journal-v1` | 원본 제품 커밋 이력이 main ancestry에 연결되지 않음 |
| `portfolio-performance-input-readiness-corrected-calendar` | 미병합 이력 |
| `portfolio-rebalance-cadence-e017` | 원본 커밋 이력이 main ancestry에 연결되지 않음 |
| `r7-isolation-hardening` | 미병합 이력 |
| `lab-continuous-engineering-backlog` | 미추적 `backend/tests/test_development_runner_recovery.py` 초안 |
| `public-evidence-coverage` | 미커밋 `backend/jusik/research_public_evidence_catalog.py` 수정 |
| `kofr-risk-free-source-evidence` | 차단된 후속 검증과 기존 환경 재사용 기록 |
| `portfolio-volatility15-cadence-4c25` | 이전 중단 시도에 대한 명시적 보존 기록 |
| `lab-paper-execution-contract-v1` | 운영 task가 여전히 blocked이며 소급 승인하지 않음 |

원본 commit SHA가 다른 작업은 일부 내용이 후속 커밋에 반영됐더라도 이번 Git 정리에서 임의로 미병합 이력을 지우지 않았습니다. 두 미커밋 초안의 소유권·검토 상태도 이번 요청만으로 확정하지 않았으므로, 현재 main에 섞거나 폐기하지 않았습니다. 루트의 사용자 소유 미추적 `HANDOFF.md`도 그대로 유지합니다.

## 문서·계약 영향

- `docs/worktree-tasks.md`에 현재 정리·보존 결과와 audit 위치를 등록했습니다. 과거 항목은 당시 작업 기록으로 보존합니다.
- 제품·UI·API·DB schema·설정·투자 기준은 바뀌지 않아 별도 사용자 계약 문서 변경은 없습니다.
- 기존 개인 Git skill의 구형 Luna는 제공되지 않아 현재 프로젝트 역할표의 `gpt-6-luna/high`를 명시적으로 선택했습니다. executor는 한 명이며 하위 위임을 하지 않았습니다. 모델·fork preflight와 실제 child metadata를 대조합니다.

## 검증과 한계

- fetch 후 local main과 원격 main SHA 동일, divergence 0/0. 실제 push 명령도 성공한 no-op으로 확인했습니다.
- 제거 후보 7개의 HEAD는 모두 main ancestor, 미커밋·미추적 변경 없음, 프로세스 cwd/명령행 사용 없음, ignored 항목은 venv·캐시·bytecode로 확인했습니다. 제거 뒤 7개 경로는 없고 브랜치는 남아 있습니다. 전체 worktree는 main 포함 19개에서 12개로 줄었습니다.
- backend tree는 `9d9efedea9ee58189fb2f35c66cb2b5bbe832289`로 직전 전체 검사와 같았습니다. XML의 전체 2,210건 중 **2,208 통과·2 실패**이며, 실패는 `test_copy_is_exactly_the_guarded_variant`와 `test_frozen_archive_replay`의 기존 historical hash 검증입니다. 전체 green으로 보고하지 않습니다.
- frontend tree는 `e22860bed34ee9937a92c853cf547d2f1f8cf6ef`입니다. [직전 UI 기록](2026-09-26-research-visual-reading.md)의 lint·typecheck·build·집중 검사·독립 검토를 재사용합니다.
- 새 제품 diff가 없어 전체 pytest·UI build를 반복하지 않았습니다. 이번 문서 commit은 명시적 경로·staged diff·비밀값·`git diff --cached --check`를 검사하고 최종 원격 SHA를 다시 확인합니다. 최종 실행 결과는 audit를 기준으로 합니다.

## 안전·운영 상태와 인계

시작 당시 roadmap runner는 paused=false, 실행 중인 네 종류 attempt 모두 0, service inactive, timer active였습니다. 수동 작업 전에 CLI로 pause하고 service 중지를 확인했습니다. 공통 Git lock을 사용하고 timer는 보존했습니다. commit과 원격 대사를 마치면 tracked-clean main에서 시작 당시의 paused=false로 복원합니다. timer active만으로 실제 개발 진행을 주장하지 않습니다. 기존 `stale_head` 후속 수정은 이번 배송 범위 밖입니다.

실주문·PAPER/live 승격·추가 결제·권한/credential 변경·Windows 종료·새 배포는 하지 않습니다. `.env`와 사용자 handoff, 원시 운영 DB·로그를 커밋하지 않습니다.

- audit: `/home/kwl/.local/share/jusik/git-ship-20260926-Xh7VOg/`
- `phase1-before-cleanup.md`: fetch와 첫 push, 삭제 전 환경·브랜치·기록 검사, 실제 정리 결과.
- `delivery-final.md`: 이번 문서의 최종 commit/main/remote SHA, 명시적 staged 파일, 검사와 실행기 복원 결과.
- `HANDOFF.md`: 최종 상태와 다음 세션 시작점. 기존 사용자 루트 handoff를 덮어쓰지 않습니다.
- 남은 작업: 보존한 초안·미병합 이력은 각 개발 범위에서 검토 후 처리합니다. 자동개발 `stale_head` 개선은 기존 성능 sprint의 계획·진단 증거부터 별도 작업으로 재개합니다.
