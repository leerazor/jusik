# Continuous Development Session

## Session

- status: active
- started_at: 2026-09-23T22:09:53+09:00
- deadline_at: 2026-09-24T01:09:53+09:00
- requested_shutdown: 2026-09-24T01:09:53+09:00 KST (Windows shutdown timer)

The previous bounded session ended at its deadline after the Korea Exim
optional transport slice and regression verification. This continuation is a
new three-hour bounded session; it preserves the same fail-closed gates and
requests Windows shutdown only after the bounded development window.

This is a new bounded session approved by the continuing roadmap objective.
The runner is enabled for repeated bounded cycles; each cycle keeps the same
fail-closed gates and stops at the session deadline.

## Operating policy

Continue the investment-roadmap work until `deadline_at`. When a
task fails, inspect the durable attempt evidence, distinguish an actionable
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

If no existing item is actionable, record the exact reservation, missing
evidence, or safety condition that prevents dispatch, and return that reason to
the operator. Do not fabricate a new roadmap area, weaken a gate, or claim that
an active timer alone means development is progressing. The timer may remain
enabled, but every idle cycle must have a durable reason and a next-check time.

The preferred research path remains: in-sample backtest -> hard filter ->
out-of-sample test -> walk-forward test -> stress test -> paper-trading
candidate. Prioritize CAGR, MDD, Sharpe, and Calmar; also retain Sortino,
Profit Factor, trade count, MDD recovery period, and maximum consecutive losses
when the data supports them.

## Stop conditions

Stop dispatching at `deadline_at`, on a user pause, or when continuing would
require missing external evidence or a safety-policy exception. Before stopping,
write the current status and next evidence requirement to the task register and
durable audit artifacts. When `requested_shutdown` is set, allow the scheduled
Windows shutdown after the bounded window; cancel it if the session ends early.

## Current external evidence requirements

- R1-02: original provider receipts with historical `observed_at` timestamps and
  trading-halt/delist coverage.
- R1-04: initial state, fixed price, entitled quantity, effective/payment UTC
  boundaries, and complete symbol/period coverage.
- R1-05: provider receipts containing symbol, period, exchange, currency,
  request/session identity, cause, observed time, and complete coverage.
