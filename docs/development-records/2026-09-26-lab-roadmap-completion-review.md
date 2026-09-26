# 연구 코드 작업의 독립 완료 검토 연결

- 상태: 코드·독립 검토·local main 통합 검증 완료. 기존 설정의 운영 재개 결과는 외부 RUNTIME에 기록한다.
- 기록 시각: 2026-09-26T05:33:16Z.
- 작업 slug: `lab-roadmap-completion-review`
- 조사 기준: `eb9e54f`; 구현 기준 `734d296`, 구현 `0a2376e`·보완 `79eab2f`; main 통합 `6739c63`.
- 범위: 기존 자동 runner의 작업 역할과 독립 완료 검토 연결. 연구 성과·투자 단계·승인 기준을 바꾸는 작업이 아니다.

## 원인과 확인한 증거

연구 task `roadmap-r2-02-cost-market-uniqueness-v1`은 입력·scope 검토 뒤
`worker_execution_unavailable`로 BLOCKED다. 전용 worktree는 clean이며 과거 attempt
`1934a7bed2034f0fb815052823c2091f`를 보존한다. 별도 공학 작업은 실제 commit과
host review를 만들며 진행했으므로 전체 서비스 정지로 설명하지 않는다.

`development_runner.py`의 일반 prompt는 독립 구현자와 reviewer를 요구하지만
runtime suffix는 child의 중첩 spawn을 금지한다. non-engineering completion은
`review_passed`를 요구하면서 host 독립 reviewer로 넘기는 경로가 없다.
기존 engineering completion에는 정확한 source/test 소유 범위와 attempt·baseline·
main·파일 hash에 결속한 별도 reviewer가 있다. scope PASS는 등록 허가일 뿐 구현 후
review로 재사용할 수 없다.

과거 승인에 없던 파일 소유 계약을 소급해서 만든 것으로 간주하지 않는다. 새 경로는
명시적 범위·identity 검증을 거치며, 금융 실험이나 자료 부족을 공학 완료로 바꾸지 않는다.

## 구현과 독립 검토

새 v2 scope만 정확한 source/test 한 쌍과 입력 hash를 동결한다. 초기 범위는 R2-01
`market_loss_accounting` 및 R2-02 `broker_cost_profiles` 쌍이다. 별도
`approved_roadmap_code_specs` registry에 원래 proposal/scope provenance를 보존하고
기존 engineering candidate→host 독립 reviewer를 재사용한다. 원래 roadmap area의
예약·queue cap·phase·mandate·필수 입력은 dispatch·완료·최종 transaction에서 검사한다.
단일 구현 child는 `review_passed=false`, host PASS 뒤에만 기술 완료·투자 미평가다.

generic/legacy 연구 완료는 그대로다. 기존 비용 계약 BLOCKED의 복구는 별도
`2026-09-26-r2-02-cost-market-uniqueness.md`에 기록한 실제 구현·독립 검토와 명시적
retry로 처리하며, legacy 승인을 v2로 소급 전환하거나 area 예약을 우회하지 않는다.

`0a2376e`는 runner 소스 3개와 신규 회귀 테스트 1개만 변경했다. 첫 RED에서 새 제안이
generic 연구 경로만 갖는 문제를 재현했다. 이후 fake CLI로 scope→구현 후보→restart→
별도 reviewer PASS→`ENGINEERING_COMPLETE/NOT_EVALUATED`를 검증했다.
v1/self-review·receipt/spec/path/hash/phase 변조 거부, rollback, READY 독립 진행,
queued/running/blocked area 예약, queue cap과 provenance 삭제의 fallback 차단도 확인했다.

첫 전체 검사에서 기존 recovery fixture의 `_select_task` 3인자 seam을 바꾼 회귀 2건을
찾아 원래 시그니처를 보존하도록 수정했다. 고정 `0a2376e`의 전체 runner pytest는
**301 passed**, 107.73초다. 변경 파일 Ruff check/format, 소스 3개 strict mypy,
신규·planning-scope 테스트 2개 strict mypy도 통과했다.

별도 Sol reviewer는 P2 한 건을 재현했다. 기존 승인 단계는 `expanduser().resolve()`로
입력 경로를 정규화하지만 새 완료 gate는 원문 경로를 써서, 상대 owned-source의 정상
수정은 `completion_invalid`, tilde 입력은 dispatch 실패가 된다. 추가 중대 지적은
없다. 같은 구현자의 `79eab2f`는 v2의 원문→canonical 경로 identity를 동결하여 CWD
변경에도 동일 입력만 인정한다. 원래 proposal/evidence digest와 v1은 보존하고,
scope reviewer에도 고정된 입력 위치를 전달한다. symlink 경계·decoy·mapping 변조를
검사한다. 별도 Sol 재검토 PASS와 격리된 경로 회귀 5개 PASS로 P2 해소를 확인했다.

보완 commit의 전체 runner pytest는 **306 passed**, 102.59초다. 소스 3개·테스트
2개의 strict mypy와 Ruff check/format도 통과했다. main `6739c63`에서 다음을 검증했다.

- backend `.venv/bin/python -m pytest tests/test_development_runner*.py tests/test_research_progress.py tests/test_broker_cost_profiles.py -q`: **338 passed**, 121.07초.
- 변경 Python 6개 파일 Ruff check·format check, 소스 4개 strict mypy, 관련 테스트 3개
  strict mypy `--follow-imports=silent`, `git diff --check`: 모두 통과.
- 기존 의존성의 Starlette/httpx·AnyIO deprecation warning 2개가 있다. 의존성은 변경하지 않았다.
- frontend 변경이 없어 build는 실행하지 않았다. 전체 backend·실제 금융 실험·수익성
  평가를 통과했다고 주장하지 않는다. 실제 Codex v2 실행은 운영 재개 후 별도 관측한다.

마이그레이션은 운영 backup의 전용 복사본에서 반복 초기화 2회, integrity `ok`, 기존
**12개 테이블·1,214개 행과 모든 기존 열 값**의 동일성을 확인했다. 추가한 테이블은
`approved_roadmap_code_specs` 하나다. 검증 코드 `79eab2f`의 4개 파일은 통합 main과
byte-for-byte 동일함을 Git diff로 확인했다. audit의 `check_migration.py`와
`runner-migration-check.db`로 재현 근거를 보존한다.

재사용된 Sol code/review는 최신 child-owned turn의 모델·추론 수준을 대조했다.
과거 context가 누락된 full-history routing 검사 전체를 PASS라고 부르지는 않는다.
별도 비용 계약 구현자의 fresh Luna/high pre/post helper는 PASS다.

## 문서·지침 영향

기존 AGENTS를 덮어쓰거나 작업자 수·모델·권한을 바꾸지 않았다. 이미 요구된 운영 문서
링크를 통해 `development-runner.md`, `continuous-development-session.md`,
`architecture.md`, `autonomous-trading-lab.md`에 단일 구현 child와 host 완료 reviewer의
책임을 구분했다. 범위 검토와 완료 검토, 기술 완료와 투자 검증을 분리한다. 새 framework나
유료 API를 추가하지 않고 기존 review 경로를 재사용했다.

## 안전·운영 상태

실행 중 task/review/discovery child가 없는 구간을 확인한 뒤 runner를 pause하고
service inactive를 확인했다. timer와 기존 데이터 수집·연구·prospective monitor는
유지한다. 완료 뒤 tracked-clean main에서 runner를 재개하고 관측 결과를 외부
`RUNTIME.md`에 기록한다. 사용자 `HANDOFF.md`와 다른 worktree는 수정하지 않는다.

검증이 끝난 이번 runner worktree와 비용 계약 worktree는 필요한 `.task-cache`를 audit의
`runner-task-cache`·`cost-task-cache`로 옮긴 뒤 `git worktree remove`로 정상 정리했다.
두 source branch와 commit, 검토 JSON·검증 기록은 보존하고 재생성 가능한 전용 venv와
test/type cache만 함께 제거했다. 다른 기존 worktree는 정리하지 않았다.

SQLite online backup:
`/home/kwl/.local/share/jusik/portfolio-audit/20260926-roadmap-completion-review/runner-before-review-bridge.db`.
integrity `ok`; 기존 12개 테이블, task 162건, attempt 222건.
SHA-256 `3a376c2e92e05f97b6ae845615846024f376212c6a10b4bd2790f069a692eb6b`.
마이그레이션이 필요하면 이 백업의 전용 복사본으로 보존성을 검사한다. rollback은
dispatch pause와 코드 revert이며 운영 DB를 과거 backup으로 덮어쓰지 않는다.

## 검증·재개

최종 문서와 handoff를 저장한 다음 기존 설정으로 재개한다. 원 비용 계약 task만 실제
독립 완료 증거를 확인하는 명시적 retry를 수행하며, old attempt와 v1 receipt는 유지한다.
새 v2 scope/구현/review의 실제 운영과 다음 자동 선택은 audit의 `RUNTIME.md` 및 현재 DB로
구분해서 확인한다. 기존 r2-01 FAILED, 보고 전용 연구의 완료 reviewer 연결, reviewer
transient retry 일반화, no_work 증거 강화는 이번에 해결했다고 주장하지 않는다.
handoff: `docs/handoffs/2026-09-26-roadmap-completion-review.md`. 실제 주문·PAPER/LIVE
활성화·원격 push·추가 결제·권한 확대·Windows 종료는 수행하지 않는다.
