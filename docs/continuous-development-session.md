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
