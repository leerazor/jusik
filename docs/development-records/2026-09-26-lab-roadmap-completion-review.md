# 연구 코드 작업의 독립 완료 검토 연결

- 상태: 구현·첫 전체 회귀 통과, 독립 검토 P2 보완 중. 아직 main에 구현을 통합하지 않았다.
- 기록 시각: 2026-09-26T05:24:00Z.
- 작업 slug: `lab-roadmap-completion-review`
- 조사 기준: `eb9e54f`; 구현 기준 `734d296`, 첫 구현 `0a2376e`; 통합은 아직 없음.
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
없다. 같은 구현자가 v2의 원문→canonical 경로 identity를 동결하여 CWD 변경에도
동일 입력만 인정하고 symlink 경계를 유지하는 좁은 보완을 진행한다. 이 보완의 최종
검사·재검토는 아직 완료로 기록하지 않는다. 실제 Codex v2 호출도 아직 미검증이다.

## 안전·운영 상태

실행 중 task/review/discovery child가 없는 구간을 확인한 뒤 runner를 pause하고
service inactive를 확인했다. timer와 기존 데이터 수집·연구·prospective monitor는
유지한다. 완료 뒤 tracked-clean main에서 runner를 재개하고 관측 결과를 외부
`RUNTIME.md`에 기록한다. 사용자 `HANDOFF.md`와 다른 worktree는 수정하지 않는다.

SQLite online backup:
`/home/kwl/.local/share/jusik/portfolio-audit/20260926-roadmap-completion-review/runner-before-review-bridge.db`.
integrity `ok`; 기존 12개 테이블, task 162건, attempt 222건.
SHA-256 `3a376c2e92e05f97b6ae845615846024f376212c6a10b4bd2790f069a692eb6b`.
마이그레이션이 필요하면 이 백업의 전용 복사본으로 보존성을 검사한다. rollback은
dispatch pause와 코드 revert이며 운영 DB를 과거 backup으로 덮어쓰지 않는다.

## 검증·재개

다음은 P2 보완의 고정 SHA 재검토, main 통합·검증과 DB backup 복사본의 보존성 검사다.
최종 문서와 handoff를 저장한 다음 기존 설정으로 재개한다. 실제 주문·PAPER/LIVE
활성화·원격 push·추가 결제·권한 확대·Windows 종료는 수행하지 않는다.
