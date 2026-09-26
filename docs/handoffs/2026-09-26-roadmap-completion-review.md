# 자동 연구 코드 검토 경로 복구 인계

- 갱신: 2026-09-26T05:36:08Z.
- 저장소: `/home/kwl/projects/jusik`, `main`; 통합 코드 `6739c631db98de8ca8eb4fdca2dfc22c146f2032`.
- 목표: 연구 child가 사용할 수 없는 중첩 worker/reviewer를 요구하다 멈추는 문제를 해결하고, BLOCKED가 독립 READY를 막지 않는 자동 흐름을 유지한다.

## 완료한 변경

새 v2 scope가 명시적으로 승인한 R2-01/02 코드 한 쌍만 기존 단일 구현→host 독립 완료
review 경로를 사용한다. 소유 파일·입력 hash·원문/canonical 경로·원래 scope를 동결하고,
dispatch와 완료에서 roadmap·mandate gate를 다시 검사한다. 별도 PASS 전 완료 불가,
완료 후에도 투자 상태는 미평가다. v1·과거 실패·generic 연구는 자동 승격하지 않는다.
구현 `0a2376e`, 독립 검토 P2 경로 보완 `79eab2f`, 최종 별도 Sol review PASS다.

기존 `roadmap-r2-02-cost-market-uniqueness-v1`의 실제 결함도 따로 해결했다.
빈·중복 markets 및 hash/ID를 재계산한 중복 manifest를 거부한다. 구현 `196f8e3`,
main `b125389`, 별도 Sol PASS이며 정상 순서 포함 입력 15개의 비용·hash·ID는 동일하다.
원 BLOCKED attempt와 scope는 보존한다. 실제 검토 증거는 아래 audit의
`cost-market-independent-review.json`이며 task·commit·두 파일 hash와 결속돼 있다.

## 검증과 기록

- 최종 main: runner·research progress·broker cost pytest **338 passed**, 121.07초.
- Python 6개 Ruff check/format, 소스 4개 strict mypy, 관련 테스트 3개 strict mypy PASS.
- DB backup 복사본: 기존 12개 테이블·1,214개 행 보존, 초기화 2회, integrity ok, 새 승인 테이블 하나만 추가.
- 실제 금융 실험·수익성 검증·frontend build·원격 push는 하지 않았다. warning 2개는 기존 의존성 deprecation이다.
- 상세: `docs/development-records/2026-09-26-lab-roadmap-completion-review.md`, `docs/development-records/2026-09-26-r2-02-cost-market-uniqueness.md`.
- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260926-roadmap-completion-review/`의 `VALIDATION.md`, backup·migration copy·검토 JSON.

## 운영·남은 경계

기록 시점은 runner pause·service inactive, timer 유지다. 이 기록 commit 이후 기존
설정으로 재개하고, 비용 계약의 위 실제 완료 증거만 검증·보고하도록 기존 명시적 retry를
사용한다. **재개 이후의 실제 상태는 audit `RUNTIME.md`와 운영 DB를 먼저 확인한다.**
이 handoff의 pause 설명만 보고 실행 중 작업을 중지하거나 재시도하지 않는다.

첫 운영 재시도는 구현 문제가 아니라 legacy JSON 필드 형식 때문에 거절됐다.
`bd2554f446d244c2aed8f281be6c8104`의 실패·출력은 보존한다. 새 attempt에서는
`engineering_status=null`, `investment_status=null`을 명시하고 실제 외부 검토의
`review_passed=true`를 보고한다. 두 필드만 null로 둔 메모리 진단은 검증기를 통과했다.
상세 제출 규칙은 비용 계약 개발 기록에 있으며 실제 후속 결과는 RUNTIME을 확인한다.

두 완료 worktree는 정상 제거했고 source branch·commit과 필요한 task cache는 보존했다.
재시도 child는 새 worktree·수정·중첩 agent 없이 canonical main과 실제 독립 review를
확인한다. 사용자 미추적 `HANDOFF.md`, 다른 worktree·데이터·기존 서비스는 건드리지 않았다.
실주문·PAPER/LIVE 활성화·추가 과금·권한/credential 완화·Windows 종료는 금지 상태다.

실제 v2 Codex scope→구현→review 관측은 fake CLI 검증과 구분한다. 기존 r2-01 FAILED,
보고 전용 연구의 완료 reviewer, transient review retry/no_work 증거 강화는 미해결 경계다.
일반 수정마다 사용자 결정을 다시 요구할 필요는 없지만 투자·권한 경계는 자동 승인하지 않는다.

다음 세션: “이 handoff와 두 개발 기록, audit RUNTIME을 읽고 현재 Git·runner DB 상태를
대조하라. 실행 중 child와 충돌하지 않게 운영 재개·비용 계약 retry 결과를 먼저 확인하고,
새 v2 작업의 별도 scope/완료 검토가 실제로 이어지는지 확인하라. 과거 실패를 지우거나
투자 gate를 완화하지 말라.”
