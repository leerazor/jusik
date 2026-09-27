# Dividend accrual 재실행의 receivable 의미 검증

- 상태: 완료 (독립 review 및 local main 통합); 투자 상태 `NOT_EVALUATED`
- 기록 시각: 2026-09-27T10:45:50Z
- 작업 slug: `lab-discovery-dividend-accrual-replay-3d5d5526`
- 기준/통합: `23a4da93616e71390150d946b956caf30b8ce1d9` / `16e30ca6c59ce908aa82e7701c25e828e27053ae`
- 범위: dividend accrual의 replay identity hash가 같더라도 이미 기록된 receivable의 의미가 다르면 거부합니다. 보유 action·데이터의 자동 수리, mandate/투자 기준 변경, 실제 자료 수집, 후보 승인 또는 실거래 판단은 하지 않았습니다.

## 변경과 결정

- 기존 `accrue_dividend()`는 replay record hash만 확인해 기존 receivable의 entitlement quantity, amount, effective/payment 시각이 바뀌어도 replay를 반환할 수 있었습니다.
- `_receivable_matches_action()`으로 기존 payment 의미 비교를 공유하고, accrual replay가 `replayed`인 경우 같은 action의 보유 receivable이 변경됐으면 `ActionConflictError`를 반환합니다. 입력 state는 수정하지 않습니다.
- 가역적 provisional 기술 가정: 동일 action의 accrual replay 의미는 기존 payment contract가 비교하던 동일 필드와 gross amount 곱셈으로 정의합니다. 별도 투자 합격 기준이나 사전등록 조건이 아닙니다.
- discovery에서 먼저 나온 `market_performance_metrics` 후보는 고정 evaluator source SHA policy 변경이 필요해 독립 scope review가 거절했습니다. 이 정책 경계를 우회하지 않았습니다. 이어 발견된 `market_history_action_accounting` 후보는 오프라인 재현과 source/test 쌍으로 한정된 수정 가능성을 독립 scope reviewer가 PASS했습니다.

## 문서·계약 영향

- 사용자 문서: 별도 변경 없음. UI/API 계약 변화는 없습니다.
- 운영·투자 문서: mandate, preregistration, data grade, 투자 기준과 runner 설정은 변경하지 않았습니다. 이 기술 결과와 상태를 `docs/worktree-tasks.md` 및 handoff에 기록했습니다.
- 데이터·회계 동작: 충돌 입력은 거부하고 기존 state를 보존합니다. 계산값·threshold·후보 승인 정책은 추가하지 않았습니다.

## 검증

- main `backend/tests/test_market_history_action_accounting.py` — 39 passed.
- 변경 두 파일 Ruff check — 통과.
- 변경 두 파일 Ruff format check — 이미 format 상태.
- 변경 두 파일 strict mypy — 통과.
- `git diff --check 23a4da9..16e30ca` — 통과.
- scope review PASS; 구현 완료 뒤 별도 host reviewer PASS, finding 0. Receipt는 implementation attempt `203f3dc32fb54680b970171ef5b06f33`, reviewer attempt `dc7061cabeb44637a5b9a05b035a9d12`, baseline/current main과 두 파일 hash에 결속됐습니다.
- 실행하지 않은 검사: 전체 backend suite와 시장 자료 기반 연구는 이 offline code slice에 필요하지 않아 실행하지 않았습니다.

## 안전·운영 상태

- 외부 market/provider/API 수집, credential 사용, 유료 구매·추가 지출, 운영 DB, PAPER/live, 실주문, remote push는 없었습니다. `origin/main` 확인은 read-only `git fetch --no-tags origin main`이었습니다.
- runner의 roadmap queue는 review 완료 전에는 task를 `WAITING_EXTERNAL/independent_review_pending`으로 격리했습니다. 다음 timer cycle의 실제 read-only reviewer PASS 뒤에만 `ENGINEERING_COMPLETE/NOT_EVALUATED`가 됐습니다. service는 최종 reviewer cycle 이후 inactive/success, timer는 active였습니다.
- runner 생성 worktree `/home/kwl/projects/jusik-lab-discovery-dividend-accrual-replay-3d5d5526`는 main 통합 뒤 정리됐고 `fix/lab-discovery-dividend-accrual-replay-3d5d5526` branch와 commit은 보존했습니다.
- 문서 반영을 위해 현재 roadmap queue를 일시 pause하고 service를 inactive로 확인했습니다. tracked 문서 commit 뒤 승인된 기존 설정으로 queue를 재개합니다. generic research queue는 기존 pause를 유지합니다.
- held-band FINAL_VALIDATION/OOS는 승인된 preregistration과 적격 미래 자료까지 task-local BLOCKED/PENDING입니다. 재확인한 draft JSON의 null 23개, `registered=false`, `approved=false`, `execution_allowed=false`는 변경하지 않았습니다. 외부 readiness binding도 producer/validator identity 계약 부재로 PENDING입니다.

## 증거와 재개

- 통합 code commit: `16e30ca6c59ce908aa82e7701c25e828e27053ae`; main focused test와 독립 review receipt는 roadmap runner private state에 보존됩니다. 원문 prompt와 로그는 기록에 복사하지 않았습니다.
- 남은 독립 blocker: 기존 별도 `WAITING_EXTERNAL` review task는 과거 review rejection의 복구 근거가 없어 retry하지 않았습니다. 신규 task는 별도 blocker 없이 완료됐습니다.
- 다음 시작: 이 기록 뒤 docs commit을 마치고 roadmap queue를 재개한 다음, 새 main/task fingerprint에 대한 bounded planner/discovery 상태를 확인합니다. 기존 scope 및 review gate를 통과한 task만 실행합니다.
