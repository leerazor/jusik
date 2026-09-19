# Continuous Development Session

## Session

- status: completed
- started_at: 2026-09-19T23:22:09+09:00
- deadline_at: 2026-09-20T02:22:09+09:00
- requested_shutdown: windows

The bounded session ended at `deadline_at`. A later session must update this
document with a new explicit start/deadline before relying on automatic
continuous execution.

## Operating policy

Continue the investment-roadmap work automatically until `deadline_at`. When a
task fails, inspect the durable attempt evidence, distinguish an actionable
code/test/tool defect from missing external evidence, and repair actionable
defects before retrying. Do not wait for another manual instruction for bounded
decisions that preserve the project safety rules.

Keep the repository fail-closed: do not invent market data, reuse synthetic or
stale evidence as real observations, weaken hard filters, bypass mandate or
identity checks, place real orders, mutate PAPER/live trading state, push
remotely, or expand permissions. Preserve unrelated user changes and record
decisions, evidence hashes, tests, and handoff artifacts in durable files.

The preferred research path remains: in-sample backtest -> hard filter ->
out-of-sample test -> walk-forward test -> stress test -> paper-trading
candidate. Prioritize CAGR, MDD, Sharpe, and Calmar; also retain Sortino,
Profit Factor, trade count, MDD recovery period, and maximum consecutive losses
when the data supports them.

## Stop conditions

Stop dispatching at `deadline_at`, on a user pause, or when continuing would
require missing external evidence or a safety-policy exception. Before stopping,
write the current status and next evidence requirement to the task register and
durable audit artifacts. Windows shutdown is requested for this session only and
must occur after final state and validation are recorded.

## Current external evidence requirements

- R1-02: original provider receipts with historical `observed_at` timestamps and
  trading-halt/delist coverage.
- R1-04: initial state, fixed price, entitled quantity, effective/payment UTC
  boundaries, and complete symbol/period coverage.
- R1-05: provider receipts containing symbol, period, exchange, currency,
  request/session identity, cause, observed time, and complete coverage.
