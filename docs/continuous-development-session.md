# Continuous Development Session

## Session

- status: historical_window_closed
- started_at: 2026-09-24T19:28:00+09:00
- deadline_at: 2026-09-24T22:28:00+09:00
- requested_shutdown: none

These timestamps are historical records of a completed three-hour session.
They do not authorize another three-hour session or impose its expired deadline
on later user requests. The current bounded task is the autonomous lab design
and implementation requested on 2026-09-25, plus explicitly registered follow-up
work under the user's continuing development authorization.

## Operating policy

### 현재 사용자 제약 (2026-09-29 확인)

- 현재 구독 요금제를 사용할 수 있는 마지막 날짜는 **2026-10-04**입니다.
  정확한 청구·종료 시각은 확인되지 않았으며 자동 중지 시각으로 추정하지 않습니다.
- 추가 지출 상한은 미결정이고 새 결제는 미승인입니다. 월 $110 요금제 전환 검토는
  결제나 API 크레딧 구매 승인이 아닙니다.
- 이번 집중 작업은 진단 인계 복구, 첫 유효 비교에 필요한 무료 자료 확보,
  비용 포함 비교 또는 근거 있는 기각까지의 경로를 우선합니다. 10월 3일까지
  결과·남은 차단·다음 유료 기간의 구체적 산출물로 연장을 판단할 수 있게 준비합니다.
- 이 일정은 수익 보장, 자료 gate 완화 또는 자동 주문·승격 승인이 아닙니다.
  기존 검증·위험 조건과 과거 실험의 고정 조건을 보존합니다.

Apply the latest explicit user scope and any currently authorized budget or
deadline. The historical `deadline_at` above is not active. When a task fails,
inspect the durable attempt evidence, distinguish an actionable
code/test/tool defect from missing external evidence, and repair actionable
defects before retrying. Do not wait for another manual instruction for bounded
decisions that preserve the project safety rules.

Keep the repository fail-closed: do not invent market data, reuse synthetic or
stale evidence as real observations, weaken hard filters, bypass mandate or
identity checks, place real orders, mutate PAPER/live trading state, push
remotely, or expand permissions. Preserve unrelated user changes and record
decisions, evidence hashes, tests, and handoff artifacts in durable files.

### Continuous execution rule

After every completed, failed, interrupted, or blocked cycle, the runner must
immediately inspect the roadmap and durable attempt evidence for the next
existing actionable item. If a blocked item is safely retryable, rebase it to
the observed current `main` with an explicit identity check, commit any
runner-generated audit record, and enqueue the next bounded attempt. Repair
owned environments and tooling when the repair is reversible and in scope.
Do not leave the runner silently idle merely because the previous cycle ended.

If no existing item is actionable, inspect eligible mandate-bound roadmap
research opportunities before creating fresh engineering work. A proposed
readiness/data/accounting/offline-contract task needs an independent read-only
scope review and current evidence/identity checks before registration. A WAIT,
REJECT, or failed plan is local to that input; continue engineering work instead
of repeatedly asking the same planner. Generic planner prose does not authorize
a new financial experiment, holdout reuse, investment validation, or promotion.
The decision contract and staged implementation are in
[goal-directed continuous operation](autonomous-trading-lab.md#17-목표-기반-지속-운영).

For a newly scope-approved code-only roadmap delivery, the isolated child is
the single implementation owner. It must not recruit nested implementers or
reviewers. Submit an unreviewed candidate; the existing host-side independent
review lane performs completion review against the frozen ownership contract.
Scope approval alone is not completion review. Preserve roadmap prerequisites
and investment status even when the delivery uses the engineering lane.
Legacy approvals without this contract gain no new execution authority.

When no reviewed research opportunity is actionable, use the enabled bounded
engineering discovery path described in `development-runner.md`. A read-only agent proposes
a concrete offline code task inside the reviewed module/test allowlist; an
independent scope reviewer must pass it before deterministic registration.
The user's 2026-09-26 request authorizes this routine next-task discovery without
per-task human confirmation. Missing investment data is not a reason to skip
independent engineering discovery. Do not fabricate a new roadmap area or
weaken an investment gate. If bounded discovery finds no actionable task,
record the inspected alternatives and exact resume condition; do not repeat
unchanged LLM calls or claim that an active timer means development is occurring.

A failed invocation is not a completed search and does not establish `no_work`.
Known temporary discovery/scope transport failures must retain their input
identity and a durable retry deadline under the runner's documented policy.
Before that deadline, select independent READY work instead of polling the
same dependency. After it, retry only through the normal pause, budget,
identity and process-ownership gates. Never change credentials, billing,
models or permissions to bypass a failure. Unknown failures and integrity
violations remain fail-closed and require diagnosis, not blind replay.
Verify these instructions with failure-injection and restart tests; report
the actual child activity or scheduled retry, not merely timer availability.
Completing a bounded worker task and its verification is a handoff to the
dispatcher, not an instruction to discard independent READY work. Do not keep
agents busy with duplicate experiments or cosmetic changes just to avoid idle.

The canonical research sequence is defined by research-mandate.json: bounded
IS, separate validation hard filter, chronological walk-forward, one untouched
OOS go/no-go, stress, isolated simulation and separate PAPER review.
Prioritize CAGR, MDD, Sharpe, and Calmar; also retain Sortino,
Profit Factor, trade count, MDD recovery period, and maximum consecutive losses
when the data supports them.

## Current rapid-results priority

The user has little time and cannot sustain the current subscription plan.
Within the existing mandate and safety gates, favor the fastest credible
cost-inclusive return evidence or a named blocker resolution. Reuse valid
existing work, avoid only redundant optional calls on unchanged inputs, and
keep routine next steps autonomous. Complete required focused checks, independent
review, and post-integration validation; repeat when code, inputs, or environment
changes, a prior check fails, or a gate requires it. A short plan and minimal
delegation suffice for known small changes;
medium or larger work keeps independent review. See
[the canonical priority](autonomous-trading-lab.md#17-목표-기반-지속-운영).
This changes dispatch instructions, not deterministic queue eligibility or a
financial acceptance threshold. No new deadline, budget, or savings is implied.

## Stop conditions

The timestamps above describe the completed historical window, not a new
authorization or an active deadline. The current task is the autonomous lab
architecture and its bounded implementation, authorized on 2026-09-25.

Stop global dispatch on an explicit user pause, an active authorized deadline,
exhausted configured budget, or an infrastructure integrity failure affecting
all tasks. Missing external evidence blocks only tasks that depend on it.
Record structured blocker metadata and select another independent READY task,
following [the lab policy](autonomous-trading-lab.md). An expired historical
window must not silently replace a newer explicit user instruction. Do not
schedule Windows shutdown without a new explicit request.

## Current external evidence requirements

- R1-02: original provider receipts with historical `observed_at` timestamps and
  trading-halt/delist coverage.
- R1-04: initial state, fixed price, entitled quantity, effective/payment UTC
  boundaries, and complete symbol/period coverage.
- R1-05: provider receipts containing symbol, period, exchange, currency,
  request/session identity, cause, observed time, and complete coverage.
