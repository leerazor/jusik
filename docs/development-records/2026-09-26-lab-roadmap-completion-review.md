# 연구 코드 작업의 독립 완료 검토 연결

- 상태: 진행 — 원인 확인, 제한된 설계 중.
- 기록 시각: 2026-09-26T04:53:00Z.
- 작업 slug: `lab-roadmap-completion-review`
- 조사 기준: `eb9e54f`; 구현·통합은 아직 수행하지 않았다.
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

아직 구현·회귀 검사·독립 검토를 통과했다고 주장하지 않는다. 다음은 제한된 설계 확정,
등록 commit에서 전용 worktree 생성, 실패 재현과 최소 구현이다. 실제 주문·PAPER/LIVE
활성화·원격 push·추가 결제·권한 확대·Windows 종료는 수행하지 않는다.
