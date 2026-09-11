import { z } from "zod";
import { amount } from "./portfolio";

const decimal = z.string().regex(/^-?\d+(\.\d+)?([eE][+-]?\d+)?$/);
const date = z.iso.date();
const timestamp = z.iso.datetime({ offset: true });

const event = z.object({
  kind: z.enum(["circuit_breaker", "sidecar"]),
  market: z.enum(["KOSPI", "KOSDAQ"]),
  direction: z.enum(["up", "down"]).nullable(),
  stage: z.number().int().nullable(),
  occurred_at: timestamp,
  known_at: timestamp,
  resumed_at: timestamp.nullable(),
  source_url: z.string().url(),
});

const request = z.object({
  symbols: z.array(z.string()),
  start_date: date,
  end_date: date,
  initial_cash: decimal,
  fee_rate: decimal,
  slippage_rate: decimal,
  sell_tax_rate: decimal,
  events: z.array(event),
});

const metrics = z.object({
  initial_cash: decimal,
  final_equity: decimal,
  total_return_pct: decimal,
  max_drawdown_pct: decimal,
  trade_count: z.number().int().nonnegative(),
  total_fees: decimal,
  total_tax: decimal,
  total_slippage_cost: decimal,
});

const trade = z.object({
  date,
  signal_date: date,
  symbol: z.string(),
  side: z.enum(["buy", "sell"]),
  quantity: z.number().int().positive(),
  market_open: decimal,
  execution_price: decimal,
  notional: decimal,
  fee: decimal,
  tax: decimal,
  rationale: z.string(),
});

const strategy = z.object({
  strategy_version: z.string(),
  definition: z.string(),
  metrics,
  trades: z.array(trade),
  equity: z.array(z.object({ date, equity: decimal, cash: decimal })),
  affected_decisions: z.array(z.object({
    date,
    symbol: z.string(),
    event_kind: z.enum(["circuit_breaker", "sidecar"]),
    action: z.literal("entry_deferred"),
    reason: z.string(),
    source_url: z.string().url(),
  })),
  unfilled_decisions: z.array(z.object({
    date,
    symbol: z.string(),
    side: z.enum(["buy", "sell"]),
    reason: z.string(),
  })),
  open_positions: z.record(z.string(), z.number().int().positive()),
});

const result = z.object({
  engine_version: z.literal("daily_shared_cash_v1"),
  baseline: strategy,
  candidate: strategy,
  coverage: z.array(z.object({
    symbol: z.string(),
    first_date: date,
    last_date: date,
    bars: z.number().int().positive(),
    warmup_bars: z.number().int().nonnegative(),
    missing_vs_union_dates: z.number().int().nonnegative(),
    missing_expected_sessions: z.number().int().nonnegative().nullable(),
  })),
  coverage_status: z.literal("common_sessions_unverified"),
  limitations: z.array(z.string()),
  event_coverage: z.enum(["provided_partial", "unavailable"]),
  input_hash: z.string(),
  parameters_hash: z.string(),
  specification: z.object({
    engine_version: z.literal("daily_shared_cash_v1"),
    baseline_version: z.literal("trend_20_v1"),
    candidate_version: z.literal("trend_20_60_v1"),
    signal_price: z.literal("adjusted_close"),
    signal_windows: z.tuple([z.number().int(), z.number().int()]),
    warmup_bars: z.literal(60),
    signal_timing: z.literal("close_then_next_available_open"),
    execution_price: z.literal("raw_open_with_symmetric_slippage"),
    cash_model: z.literal("shared_long_only"),
    allocation: z.literal("inverse_universe_equal_cap"),
    order_priority: z.literal("sells_then_symbol_sorted_buys"),
    quantity_rounding: z.literal("integer_floor"),
    decimal_precision: z.literal(40),
    decimal_rounding: z.literal("ROUND_HALF_EVEN"),
    final_valuation: z.literal("raw_close_without_forced_liquidation"),
    event_policy: z.literal("matching_board_known_event_defer_once"),
  }).nullable(),
  implementation_hash: z.string().nullable(),
  live_promotion_eligible: z.literal(false),
  validation: z.object({
    training_start: date,
    training_end: date,
    testing_start: date,
    testing_end: date,
    testing_initial_cash: decimal,
    training_baseline: metrics,
    training_candidate: metrics,
    baseline: metrics,
    candidate: metrics,
    recommended_version: z.string(),
    candidate_passed: z.boolean(),
    reason: z.string(),
  }).nullable(),
});

const strategyDefinition = z.object({
  version: z.string(),
  name: z.string(),
  fast_window: z.number().int(),
  slow_window: z.number().int().nullable(),
  min_volume_ratio: decimal.nullable(),
  definition: z.string(),
});

const quote = z.object({
  symbol: z.string(),
  price: decimal,
  ask: decimal.nullable(),
  bid: decimal.nullable(),
  volume: z.number().int().nonnegative(),
  accumulated_volume: z.number().int().nonnegative(),
  market_at: timestamp,
  received_at: timestamp,
  source: z.literal("KIS H0STCNT0"),
});

const proposal = z.object({
  id: z.string(),
  symbol: z.string(),
  side: z.enum(["buy", "sell"]),
  quantity: z.number().int().positive(),
  limit_price: decimal,
  expires_at: timestamp,
  strategy_version: z.string(),
  signal_date: date,
  source_run_id: z.string(),
  signal_input_hash: z.string(),
  reason: z.string(),
  status: z.enum(["pending", "approved", "rejected", "expired", "filled"]),
  created_at: timestamp,
  decided_at: timestamp.nullable(),
  decision_reason: z.string().nullable(),
});

export const operationsStatusSchema = z.object({
  universe: z.array(z.string()),
  schedule: z.object({
    enabled: z.boolean(),
    interval_hours: z.number().int(),
    lookback_days: z.number().int(),
    next_run_at: timestamp,
    last_started_at: timestamp.nullable(),
    last_run_id: z.string().nullable(),
    last_error: z.string().nullable(),
  }),
  versions: z.array(z.object({
    definition: strategyDefinition,
    created_at: timestamp,
    source: z.enum(["built_in", "openai_suggestion"]),
    recommended: z.boolean(),
    active_for_paper: z.boolean(),
    reason: z.string(),
    last_run_id: z.string().nullable(),
    out_of_sample_return_pct: decimal.nullable(),
    out_of_sample_max_drawdown_pct: decimal.nullable(),
    passed: z.boolean().nullable(),
    proposed_after_date: date.nullable(),
    provenance: z.record(z.string(), z.string()),
    evaluation_start: date.nullable(),
    evaluation_end: date.nullable(),
    evaluation_run_id: z.string().nullable(),
    evaluation_input_hash: z.string().nullable(),
    evaluation_implementation_hash: z.string().nullable(),
  })),
  stream: z.object({
    state: z.enum(["disabled", "connecting", "connected", "stale", "error"]),
    detail: z.string(),
    configured: z.boolean(),
    symbols: z.array(z.string()),
    connected_at: timestamp.nullable(),
    last_message_at: timestamp.nullable(),
    reconnect_count: z.number().int().nonnegative(),
  }),
  quotes: z.array(quote),
  proposals: z.array(proposal),
  paper_account: z.object({
    cash: decimal,
    positions: z.record(z.string(), z.number().int().nonnegative()),
    fills: z.array(z.object({
      id: z.string(),
      proposal_id: z.string(),
      symbol: z.string(),
      side: z.enum(["buy", "sell"]),
      quantity: z.number().int().positive(),
      price: decimal,
      notional: decimal,
      fee: decimal,
      tax: decimal,
      filled_at: timestamp,
      execution: z.literal("app_simulated"),
    })),
    updated_at: timestamp,
  }),
  ai: z.object({
    enabled: z.boolean(),
    configured: z.boolean(),
    model: z.string().nullable(),
    daily_token_budget: z.number().int().nonnegative(),
    used_tokens_today: z.number().int().nonnegative(),
    last_run_at: timestamp.nullable(),
    last_error: z.string().nullable(),
    last_analysis: z.string().nullable(),
    prompt_version: z.string(),
  }),
  execution_mode: z.literal("paper_only"),
  warnings: z.array(z.string()),
});

export const researchRunSchema = z.object({
  id: z.string(),
  status: z.enum([
    "queued",
    "collecting",
    "running",
    "completed",
    "insufficient",
    "failed",
  ]),
  request,
  created_at: timestamp,
  updated_at: timestamp,
  replay_of: z.string().nullable(),
  input_hash: z.string().nullable(),
  input_snapshot: z.unknown().nullable(),
  result: result.nullable(),
  error: z.string().nullable(),
});

export const researchRunListSchema = z.array(
  researchRunSchema.omit({ input_snapshot: true, error: true }),
);

export type ResearchRun = z.infer<typeof researchRunSchema>;
export type ResearchRunSummary = z.infer<typeof researchRunListSchema>[number];
export type StrategyResult = z.infer<typeof strategy>;
export type OperationsStatus = z.infer<typeof operationsStatusSchema>;

const portfolioCandidateSchema = z.object({
  id: z.string(),
  method: z.enum(["equal", "inverse_volatility", "momentum_top4"]),
  gate: z.enum(["none", "rates", "fx_vix", "stress"]),
});

const portfolioMetricsSchema = z.object({
  initial_equity_krw: decimal,
  final_equity_krw: decimal,
  total_return_pct: decimal,
  max_drawdown_pct: decimal,
  trade_count: z.number().int().nonnegative(),
  transaction_cost_krw: decimal,
  fx_cost_krw: decimal,
  turnover_pct: decimal,
});

const portfolioPolicySchema = z.enum([
  "corrected_control",
  "reentry_only",
  "volatility_only",
  "combined",
  "low_turnover_combined",
]);

const portfolioPolicyEventSchema = z.object({
  at: timestamp,
  kind: z.enum([
    "risk_exit",
    "liquidation_complete",
    "recovery_confirmation",
    "recovery_reset",
    "reentry_ready",
    "reentry",
    "volatility_scale",
    "frequency_skip",
    "band_skip",
    "cap_constraint_deferred",
  ]),
  detail: z.string(),
  value: decimal.nullable(),
});

const portfolioSimulationSchema = z.object({
  candidate: portfolioCandidateSchema,
  period_start: date,
  period_end: date,
  metrics: portfolioMetricsSchema,
  complete: z.boolean(),
  incomplete_reasons: z.array(z.string()),
  drawdown_latched: z.boolean(),
  drawdown_latched_at: timestamp.nullable(),
  equity: z.array(z.object({
    at: timestamp,
    equity_krw: decimal,
    cash_krw: decimal,
    drawdown_pct: decimal,
  })),
  trades: z.array(z.object({
    decided_at: timestamp,
    executed_at: timestamp,
    symbol: z.string(),
    side: z.enum(["buy", "sell"]),
    quantity: z.number().int().positive(),
    local_price: decimal,
    fx_rate: decimal,
    notional_krw: decimal,
    transaction_cost_krw: decimal,
    fx_cost_krw: decimal,
  })),
  weekly_targets: z.array(z.object({
    decided_at: timestamp,
    symbol: z.string(),
    target_weight: decimal,
    actual_weight_after_open: decimal.nullable(),
  })),
  positions: z.array(z.object({
    symbol: z.string(),
    quantity: z.number().int().nonnegative(),
    currency: z.enum(["KRW", "USD"]),
    local_close: decimal,
    fx_rate: decimal,
    value_krw: decimal,
    weight: decimal,
    valued_at: timestamp,
    fx_observed_on: date.nullable(),
  })),
  contributions_krw: z.record(z.string(), decimal),
  split_cash_in_lieu_krw: z.record(z.string(), decimal),
  overlap_diagnostics: z.record(z.string(), decimal),
  policy: portfolioPolicySchema.default("corrected_control"),
  policy_events: z.array(portfolioPolicyEventSchema).default([]),
});

const portfolioPolicyDiagnosticsSchema = z.object({
  trading_utc_days: z.number().int().nonnegative(),
  invested_days_pct: decimal,
  monthly: z.array(z.object({
    month: z.string().regex(/^\d{4}-\d{2}$/),
    trade_count: z.number().int().nonnegative(),
    turnover_pct: decimal,
    active: z.boolean(),
  })),
  active_month_trade_average: decimal,
  active_month_trade_maximum: z.number().int().nonnegative(),
  reentry_count: z.number().int().nonnegative(),
  exit_count: z.number().int().nonnegative(),
  frequency_skip_count: z.number().int().nonnegative(),
  band_skip_count: z.number().int().nonnegative(),
  volatility_scale_event_count: z.number().int().nonnegative(),
});

const portfolioPolicyExperimentSchema = z.object({
  registered_at: timestamp,
  reference_run_id: z.string().regex(/^[0-9a-f]{64}$/),
  reference_input_hash: z.string().regex(/^[0-9a-f]{64}$/),
  fixed_candidate: portfolioCandidateSchema,
  specification_hash: z.string().regex(/^[0-9a-f]{64}$/),
  evidence: z.literal("retrospective_reused_historical_evaluation"),
  corrected_validation_candidate: portfolioCandidateSchema,
  corrected_selection_changed: z.boolean(),
  comparisons: z.array(z.object({
    policy: portfolioPolicySchema,
    base: portfolioSimulationSchema,
    cost_stress: portfolioSimulationSchema,
    diagnostics: portfolioPolicyDiagnosticsSchema,
  })),
  limitations: z.array(z.string()),
});

export const portfolioRunSchema = z.object({
  run_id: z.string().regex(/^[0-9a-f]{64}$/),
  created_at: timestamp,
  status: z.literal("completed"),
  input_hash: z.string(),
  code_hash: z.string(),
  requested_start: date,
  harmonized_end: date,
  preparation_end: date,
  validation_start: date,
  validation_end: date,
  heldout_start: date,
  heldout_end: date,
  selected_candidate: portfolioCandidateSchema,
  validation: z.array(z.object({
    candidate: portfolioCandidateSchema,
    metrics: portfolioMetricsSchema,
    complete: z.boolean(),
    incomplete_reasons: z.array(z.string()),
  })),
  heldout: portfolioSimulationSchema,
  cash_baseline: portfolioMetricsSchema,
  equal_baseline: portfolioSimulationSchema,
  cost_stress: portfolioSimulationSchema,
  config: z.object({
    initial_cash_krw: decimal,
    fee_rate: decimal,
    slippage_rate: decimal,
    fx_spread_rate: decimal,
    symbol_cap: decimal,
    gross_cap: decimal,
    leveraged_etf_cap: decimal,
    drawdown_limit: decimal,
    warmup_sessions: z.number().int(),
    validation_sessions: z.number().int(),
    signal_window: z.number().int(),
    volatility_window: z.number().int(),
    momentum_window: z.number().int(),
    correlation_window: z.number().int(),
    external_max_age_days: z.number().int(),
    reentry_cooldown_days: z.number().int(),
    recovery_confirmations: z.number().int(),
    recovery_minimum_assets: z.number().int(),
    volatility_target: decimal,
    volatility_annualization_sessions: z.number().int(),
    low_turnover_weeks: z.number().int(),
    low_turnover_band: decimal,
  }),
  external_status: z.array(z.object({
    source: z.string(),
    status: z.enum(["pending", "success", "stale", "error"]),
    last_attempt_at: timestamp.nullable(),
    last_success_at: timestamp.nullable(),
    coverage_start: date.nullable(),
    coverage_end: date.nullable(),
    observation_count: z.number().int().nonnegative(),
    raw_archive_count: z.number().int().nonnegative(),
    raw_bytes: z.number().int().nonnegative(),
    age_hours: decimal.nullable(),
    error: z.string().nullable(),
    usage: z.enum(["feature", "diagnostic_only", "archive_only"]),
  })),
  evidence_class: z.literal("reconstructed_historical_exploration"),
  point_in_time_verified: z.literal(false),
  prospective_validation_eligible: z.literal(false),
  automatic_trading_eligible: z.literal(false),
  limitations: z.array(z.string()),
  artifacts: z.array(z.string()),
  policy_experiment: portfolioPolicyExperimentSchema.nullable().default(null),
});

export type PortfolioRun = z.infer<typeof portfolioRunSchema>;

export const portfolioStatusSchema = z.object({
  status: z.enum(["idle", "running", "success", "error"]),
  last_attempt_at: timestamp.nullable(),
  last_success_at: timestamp.nullable(),
  latest_run_id: z.string().nullable(),
  error_code: z.string().nullable(),
  latest_stale: z.boolean(),
  external_status: portfolioRunSchema.shape.external_status,
});

export type PortfolioStatus = z.infer<typeof portfolioStatusSchema>;

const symbolMetadataSchema = z.array(z.object({
  symbol: z.string().regex(/^[0-9]{6}$/),
  name: z.string().min(1).max(80),
  updated_at: timestamp,
}));

export type SymbolNames = Record<string, string>;

export function researchBackendUrl(): string {
  return process.env.JUSIK_RESEARCH_BACKEND_URL ?? "http://127.0.0.1:8001";
}

export function researchAmount(value: string, digits = 2): string {
  const match = /^(-?)(\d+)(?:\.(\d+))?(?:[eE]([+-]?\d+))?$/.exec(value);
  if (!match) return value;
  const [, sign, whole, fraction = "", exponentText = "0"] = match;
  const exponent = Number(exponentText);
  const raw = `${whole}${fraction}`;
  const point = whole.length + exponent;
  const fixed = point <= 0
    ? `0.${"0".repeat(-point)}${raw}`
    : point >= raw.length
      ? `${raw}${"0".repeat(point - raw.length)}`
      : `${raw.slice(0, point)}.${raw.slice(point)}`;
  return amount(`${sign}${fixed}`, digits);
}

export function researchRatePercent(value: string): string {
  const match = /^(-?)(\d+)(?:\.(\d+))?(?:[eE]([+-]?\d+))?$/.exec(value);
  if (!match) return value;
  const [, sign, whole, fraction = "", exponentText = "0"] = match;
  const shifted = `${sign}${whole}${fraction ? `.${fraction}` : ""}e${Number(exponentText) + 2}`;
  return `${researchAmount(shifted, 6)}%`;
}

export async function getResearchRuns(): Promise<ResearchRunSummary[]> {
  const response = await fetch(`${researchBackendUrl()}/api/research/runs`, {
    cache: "no-store",
    signal: AbortSignal.timeout(10000),
  });
  if (!response.ok) throw new Error("research backend unavailable");
  return researchRunListSchema.parse(await response.json());
}

export async function getResearchRun(id: string): Promise<ResearchRun | null> {
  const response = await fetch(`${researchBackendUrl()}/api/research/runs/${id}`, {
    cache: "no-store",
    signal: AbortSignal.timeout(10000),
  });
  if (response.status === 404) return null;
  if (!response.ok) throw new Error("research backend unavailable");
  return researchRunSchema.parse(await response.json());
}

export async function getOperationsStatus(): Promise<OperationsStatus> {
  const response = await fetch(`${researchBackendUrl()}/api/operations`, {
    cache: "no-store",
    signal: AbortSignal.timeout(10000),
  });
  if (!response.ok) throw new Error("research backend unavailable");
  return operationsStatusSchema.parse(await response.json());
}

export async function getLatestPortfolioRun(): Promise<PortfolioRun | null> {
  const response = await fetch(`${researchBackendUrl()}/api/research/portfolio/latest`, {
    cache: "no-store",
    signal: AbortSignal.timeout(10000),
  });
  if (response.status === 404) return null;
  if (!response.ok) throw new Error("research backend unavailable");
  return portfolioRunSchema.parse(await response.json());
}

export async function getPortfolioStatus(): Promise<PortfolioStatus> {
  const response = await fetch(`${researchBackendUrl()}/api/research/portfolio/status`, {
    cache: "no-store",
    signal: AbortSignal.timeout(10000),
  });
  if (!response.ok) throw new Error("research backend unavailable");
  return portfolioStatusSchema.parse(await response.json());
}

export async function getSymbolNames(): Promise<SymbolNames> {
  const response = await fetch(`${researchBackendUrl()}/api/research/symbol-metadata`, {
    cache: "no-store",
    signal: AbortSignal.timeout(10000),
  });
  if (!response.ok) throw new Error("research backend unavailable");
  return Object.fromEntries(
    symbolMetadataSchema.parse(await response.json()).map((item) => [item.symbol, item.name]),
  );
}

export function researchSymbolLabel(symbol: string, names: SymbolNames): string {
  const name = names[symbol];
  return name ? `${name} (${symbol})` : `이름 미확인 (${symbol})`;
}

export const researchQuoteSchema = z.object({
  symbol: z.string(), exchange: z.enum(["KRX", "NAS", "NYS", "AMS"]),
  currency: z.enum(["KRW", "USD"]), price: decimal,
  ask: decimal.nullable(), bid: decimal.nullable(), volume: z.number().int().nonnegative(),
  accumulated_volume: z.number().int().nonnegative(), market_at: timestamp,
  received_at: timestamp, source: z.enum(["KIS H0STCNT0", "KIS HDFSCNT0"]),
  delay_minutes: z.literal(0), realtime_code: z.string().nullable(),
});

const forwardIntentSchema = z.object({
  symbol: z.string(), side: z.enum(["buy", "sell"]), target_weight: decimal,
  budget_krw: decimal, state: z.enum(["pending", "filled", "consumed", "expired", "blocked"]),
  reason: z.string(),
});
const forwardStateSchema = z.enum([
  "observing", "waiting_cadence", "decision_recorded", "awaiting_quotes", "completed",
  "partially_completed", "expired", "inputs_blocked", "risk_liquidation", "cooldown",
  "recovery_wait",
  "reentry_ready",
]);
const forwardDecisionSchema = z.object({
  id: z.string(), session_id: z.string(), due_at: timestamp, recorded_at: timestamp,
  input_version: z.string(), state: forwardStateSchema, reason: z.string(),
  expires_at: timestamp.nullable(), target_weights: z.record(z.string(), decimal),
  intents: z.array(forwardIntentSchema), volatility_proxy: decimal.nullable(),
  volatility_scale: decimal.nullable(),
});
const forwardFillSchema = z.object({
  id: z.string(), session_id: z.string(), decision_id: z.string(), symbol: z.string(),
  side: z.enum(["buy", "sell"]), quantity: z.number().int().positive(), market_at: timestamp,
  received_at: timestamp, local_price: decimal, fx_rate: decimal, notional_krw: decimal,
  transaction_cost_krw: decimal, fx_cost_krw: decimal, cash_after_krw: decimal,
  quote_id: z.string(), model: z.literal("hypothetical_integer_full_fill"),
});
const forwardConfigSchema = z.object({
    initial_cash_krw: decimal, candidate_id: z.literal("portfolio_inverse_volatility_fx_vix_v1"),
    method: z.literal("inverse_volatility"), gate: z.literal("fx_vix"),
    policy: z.literal("low_turnover_combined"), fee_rate: decimal, slippage_rate: decimal,
    fx_spread_rate: decimal, symbol_cap: decimal, gross_cap: decimal, leveraged_cap: decimal,
    drawdown_limit: decimal, cadence_days: z.literal(28), normal_intent_expiry_days: z.literal(7),
    restart_catchup_minutes: z.literal(15), quote_fresh_seconds: z.literal(15),
    future_tolerance_seconds: z.literal(2), reentry_cooldown_days: z.literal(28),
    recovery_confirmations: z.literal(2), low_turnover_band: decimal,
});
const forwardSessionSchema = z.object({
  id: z.string(), activated_at: timestamp, next_due_at: timestamp, source_run_id: z.string(),
  policy_hash: z.string(), state: forwardStateSchema, cash_krw: decimal,
  lifetime_high_water_krw: decimal, episode_high_water_krw: decimal,
  liquidation_completed_at: timestamp.nullable(), next_recovery_check_at: timestamp.nullable(),
  recovery_confirmations: z.number().int().nonnegative(), config: forwardConfigSchema,
});
const feedStatusSchema = z.object({
  state: z.enum(["disabled", "connecting", "connected", "partial", "stale", "error"]),
  detail: z.string(), configured: z.boolean(), connected_at: timestamp.nullable(),
  reconnect_count: z.number().int().nonnegative(), provider: z.literal("Korea Investment Open Trading API"),
  provider_url: z.string().url(), data_note: z.string(),
  items: z.array(z.object({
    symbol: z.string(), exchange: z.enum(["KRX", "NAS", "NYS", "AMS"]),
    currency: z.enum(["KRW", "USD"]),
    state: z.enum(["pending", "connected", "stale", "rejected", "unsupported"]),
    subscription_phase: z.enum(["queued", "awaiting_ack", "approved", "rejected"]),
    requested_at: timestamp.nullable(), sent_at: timestamp.nullable(),
    acknowledged_at: timestamp.nullable(), first_quote_at: timestamp.nullable(),
    ack_overdue: z.boolean(),
    detail: z.string(), last_market_at: timestamp.nullable(), last_received_at: timestamp.nullable(),
    delay_minutes: z.literal(0),
  })),
  protocol_counters: z.array(z.object({
    tr_id: z.enum(["H0STCNT0", "HDFSCNT0"]),
    data_frame_count: z.number().int().nonnegative(),
    valid_quote_count: z.number().int().nonnegative(),
    parse_failure_count: z.number().int().nonnegative(),
  })),
});
export const forwardStatusSchema = z.object({
  session: forwardSessionSchema, feed: feedStatusSchema,
  preview: z.object({
    computed_at: timestamp, asof: timestamp, is_decision: z.literal(false),
    target_weights: z.record(z.string(), decimal), blocked_reason: z.string().nullable(),
    input_version: z.string().nullable(),
  }),
  latest_decision: forwardDecisionSchema.nullable(), blocked_reason: z.string().nullable(),
  worker_failures: z.array(z.object({
    channel: z.enum(["tick", "quote"]), code: z.literal("internal_error"), occurred_at: timestamp,
  })),
  latest_clock_health: z.object({
    sample_id: z.string().uuid(), sampled_at: timestamp, source_measurement_at: z.null(),
    state: z.enum(["available", "unknown"]), offset_ms: decimal.nullable(),
    delay_ms: decimal.nullable(), jitter_ms: decimal.nullable(),
    packet_count: z.number().int().nonnegative().nullable(), synced: z.boolean().nullable(),
    persisted: z.boolean(),
    error_code: z.enum(["command_missing", "command_failed", "timeout", "output_oversize", "parse_error", "probe_failed", "persistence_failed"]).nullable(),
  }).nullable().default(null),
  calendar: z.object({
    available: z.boolean(), provider: z.literal("exchange_calendars"), provider_version: z.string(),
    artifact_sha256: z.string().regex(/^[a-f0-9]{64}$/),
    calendars_sha256: z.string().regex(/^[a-f0-9]{64}$/), generated_at: timestamp,
    coverage_start: date, coverage_end: date, error_code: z.string().nullable(),
    exchanges: z.array(z.object({
      calendar: z.enum(["XKRX", "XNYS"]),
      phase: z.enum(["pre_open", "regular_session", "post_close", "closed", "unavailable"]),
      local_date: date, open_at: timestamp.nullable(), close_at: timestamp.nullable(),
      next_session_open_at: timestamp.nullable(), next_session_close_at: timestamp.nullable(),
    })),
  }),
  action_limitations: z.object({
    dividends: z.literal("excluded_cash_dividends"),
    splits: z.literal("verified_integer_forward_splits_only"),
    historical_calendar: z.literal("not_converted"),
  }),
  corporate_actions: z.array(z.object({
    id: z.string().regex(/^[a-f0-9]{64}$/), session_id: z.string().regex(/^[a-f0-9]{64}$/),
    symbol: z.string(), exchange: z.enum(["KRX", "NAS", "NYS", "AMS"]),
    numerator: z.number().int().gt(1),
    denominator: z.literal(1), factor: z.number().int().gt(1),
    source_url: z.string().url().startsWith("https://"), evidence_id: z.string(),
    evidence_sha256: z.string().regex(/^[a-f0-9]{64}$/), operator_verified: z.literal(true),
    observed_at: timestamp, effective_at: timestamp, registered_at: timestamp,
    applied_at: timestamp.nullable(), before_quantity: z.number().int().nonnegative().nullable(),
    after_quantity: z.number().int().nonnegative().nullable(),
    state: z.enum(["registered", "applied", "blocked"]), blocked_reason: z.string().nullable(),
  })),
  paper_only: z.literal(true), broker_orders_enabled: z.literal(false), worker_interval_seconds: z.literal(5),
});
export const forwardLedgerSchema = z.object({
  session: forwardSessionSchema, cash_krw: decimal,
  positions: z.array(z.object({
    symbol: z.string(), currency: z.enum(["KRW", "USD"]), quantity: z.number().int().nonnegative(),
    average_cost_krw: decimal, updated_at: timestamp,
  })),
  fills: z.array(forwardFillSchema), valuated_equity_krw: decimal.nullable(),
  valuation_at: timestamp.nullable(), fx_proxy_observed_on: date.nullable(), limitations: z.array(z.string()),
});
export type ForwardStatus = z.infer<typeof forwardStatusSchema>;
export type ForwardLedger = z.infer<typeof forwardLedgerSchema>;

const actionPayloadSchema = z.object({
  vendor_date: date,
  numerator: z.number().int().positive().nullable(),
  denominator: z.number().int().positive().nullable(),
  amount: decimal.nullable(),
  currency: z.enum(["KRW", "USD"]).nullable(),
});
const actionRevisionSchema = z.object({
  id: z.string().regex(/^[a-f0-9]{64}$/),
  event_id: z.string().regex(/^[a-f0-9]{64}$/),
  provider: z.literal("Yahoo chart"),
  symbol: z.string(),
  kind: z.enum(["split", "dividend"]),
  provider_key: z.string(),
  sequence: z.number().int().positive(),
  content_sha256: z.string().regex(/^[a-f0-9]{64}$/),
  first_seen_at: timestamp,
  attempt_id: z.string().regex(/^[a-f0-9]{64}$/),
  payload: actionPayloadSchema,
});
const actionEventSchema = z.object({
  id: z.string().regex(/^[a-f0-9]{64}$/),
  provider: z.literal("Yahoo chart"),
  symbol: z.string(),
  kind: z.enum(["split", "dividend"]),
  provider_key: z.string(),
  vendor_date: date,
  first_seen_at: timestamp,
  last_seen_at: timestamp,
  observation_state: z.enum(["observed", "not_seen_in_latest_response"]),
  latest_revision_sequence: z.number().int().positive(),
  latest_revision: actionRevisionSchema,
});
export const actionCollectionStatusSchema = z.object({
  provider: z.literal("Yahoo chart"),
  provider_url: z.literal("https://query1.finance.yahoo.com"),
  collector_state: z.enum(["idle", "running", "locked", "error"]),
  error_code: z.string().nullable(),
  generated_at: timestamp,
  sources: z.array(z.object({
    symbol: z.string(), yahoo_symbol: z.string(),
    state: z.enum(["never", "pending", "success", "error", "interrupted"]),
    last_attempt_at: timestamp.nullable(), last_success_at: timestamp.nullable(),
    next_due_at: timestamp, stale: z.boolean(), error_code: z.string().nullable(),
    requested_start: date.nullable(), requested_end: date.nullable(),
    latest_attempt_id: z.string().regex(/^[a-f0-9]{64}$/).nullable(),
    latest_attempt_raw_available: z.boolean(), event_count: z.number().int().nonnegative(),
  })),
  automatic_ledger_application: z.literal(false),
  payout_and_tax_known: z.literal(false),
  official_publication_time_known: z.literal(false),
});
export const actionEventPageSchema = z.object({
  items: z.array(actionEventSchema), next_cursor: z.string().nullable(),
});
export const actionRevisionPageSchema = z.object({
  items: z.array(actionRevisionSchema), next_cursor: z.string().nullable(),
});
const actionReviewSchema = z.object({
  id: z.string().regex(/^[a-f0-9]{64}$/), review_key: z.string(),
  revision_id: z.string().regex(/^[a-f0-9]{64}$/),
  event_id: z.string().regex(/^[a-f0-9]{64}$/), sequence: z.number().int().positive(),
  symbol: z.string(), kind: z.enum(["split", "dividend"]),
  source_content_sha256: z.string().regex(/^[a-f0-9]{64}$/),
  source_payload: z.record(z.string(), z.unknown()), extracted_facts: z.object({
    numerator: z.number().int().positive().nullable(),
    denominator: z.number().int().positive().nullable(),
    adjusted_trading_date: date.nullable(), amount: decimal.nullable(),
    currency: z.enum(["KRW", "USD"]).nullable(),
    comparable_share_basis: z.boolean().nullable(), ex_dividend_date: date.nullable(),
    record_date: date.nullable(), payment_date: date.nullable(),
    legal_effective_date: date.nullable(),
  }),
  comparison_status: z.enum(["matched", "partial", "mismatched"]),
  compared_fields: z.array(z.object({
    field: z.string(), source_value: z.string().nullable(),
    evidence_value: z.string().nullable(),
    status: z.enum(["matched", "missing", "mismatched"]),
  })),
  evidence: z.object({
    id: z.string().regex(/^[a-f0-9]{64}$/),
    sha256: z.string().regex(/^[a-f0-9]{64}$/), source_url: z.string().url(),
    publisher: z.string(), locator: z.string(), captured_at: timestamp,
  }),
  reviewed_at: timestamp, imported_at: timestamp, current_revision: z.boolean(),
  needs_review: z.boolean(), automatic_ledger_application: z.literal(false),
});
export const actionReviewPageSchema = z.object({
  items: z.array(actionReviewSchema), next_cursor: z.string().nullable(),
  reviewed_revision_count: z.number().int().nonnegative(),
  current_revision_count: z.number().int().nonnegative(),
  unreviewed_current_revision_count: z.number().int().nonnegative(),
});
export type ActionCollectionStatus = z.infer<typeof actionCollectionStatusSchema>;
export type ActionEventPage = z.infer<typeof actionEventPageSchema>;
export type ActionRevisionPage = z.infer<typeof actionRevisionPageSchema>;
export type ActionReviewPage = z.infer<typeof actionReviewPageSchema>;

const historyArtifactSchema = z.object({
  artifact_id: z.string().regex(/^[a-f0-9]{64}$/), sha256: z.string().regex(/^[a-f0-9]{64}$/),
  title: z.string(), filename: z.string().regex(/^[a-f0-9]{64}\.md$/),
});
export const historyPageSchema = z.object({
  items: z.array(z.object({
    id: z.string(), occurred_at: timestamp.nullable(), recorded_at: timestamp,
    title: z.string(), summary: z.string(), category: z.enum(["research", "development", "forward", "system"]),
    outcome: z.string(), run_ids: z.array(z.string()),
    checks: z.array(z.object({ name: z.string(), result: z.string(), evidence_id: z.string() })),
    artifacts: z.array(z.object({ artifact_id: z.string(), sha256: z.string() })),
    supersedes: z.string().nullable(),
  })),
  artifacts: z.array(historyArtifactSchema), next_cursor: z.string().nullable(),
});
export type HistoryPage = z.infer<typeof historyPageSchema>;

export async function getForwardStatus(): Promise<ForwardStatus> {
  const response = await fetch(`${researchBackendUrl()}/api/research/forward/status`, {
    cache: "no-store", signal: AbortSignal.timeout(10000),
  });
  if (!response.ok) throw new Error("forward research unavailable");
  return forwardStatusSchema.parse(await response.json());
}

export async function getForwardLedger(): Promise<ForwardLedger> {
  const response = await fetch(`${researchBackendUrl()}/api/research/forward/ledger`, {
    cache: "no-store", signal: AbortSignal.timeout(10000),
  });
  if (!response.ok) throw new Error("forward ledger unavailable");
  return forwardLedgerSchema.parse(await response.json());
}

export async function getActionCollectionStatus(): Promise<ActionCollectionStatus> {
  const response = await fetch(`${researchBackendUrl()}/api/research/actions/status`, {
    cache: "no-store", signal: AbortSignal.timeout(10000),
  });
  if (!response.ok) throw new Error("action collection unavailable");
  return actionCollectionStatusSchema.parse(await response.json());
}

export async function getActionEvents(cursor?: string): Promise<ActionEventPage> {
  const query = new URLSearchParams({ limit: "50" });
  if (cursor) query.set("cursor", cursor);
  const response = await fetch(`${researchBackendUrl()}/api/research/actions/events?${query}`, {
    cache: "no-store", signal: AbortSignal.timeout(10000),
  });
  if (!response.ok) throw new Error("action events unavailable");
  return actionEventPageSchema.parse(await response.json());
}

export async function getActionRevisions(cursor?: string): Promise<ActionRevisionPage> {
  const query = new URLSearchParams({ limit: "50" });
  if (cursor) query.set("cursor", cursor);
  const response = await fetch(`${researchBackendUrl()}/api/research/actions/revisions?${query}`, {
    cache: "no-store", signal: AbortSignal.timeout(10000),
  });
  if (!response.ok) throw new Error("action revisions unavailable");
  return actionRevisionPageSchema.parse(await response.json());
}

export async function getActionReviews(
  cursor?: string,
  eventId?: string,
): Promise<ActionReviewPage> {
  const query = new URLSearchParams({ limit: "50" });
  if (cursor) query.set("cursor", cursor);
  if (eventId) query.set("event_id", eventId);
  const response = await fetch(`${researchBackendUrl()}/api/research/actions/reviews?${query}`, {
    cache: "no-store", signal: AbortSignal.timeout(10000),
  });
  if (!response.ok) throw new Error("action reviews unavailable");
  return actionReviewPageSchema.parse(await response.json());
}

const dividendCoverageSchema = z.object({
  event_id: z.string(), revision_id: z.string(), symbol: z.string(), vendor_date: date,
  status: z.enum(["eligible", "excluded"]), reason: z.string().nullable(),
  review_id: z.string().nullable(), evidence_id: z.string().nullable(),
  evidence_sha256: z.string().nullable(), ex_dividend_date: date.nullable(),
  payment_date: date.nullable(), amount: decimal.nullable(),
  currency: z.enum(["KRW", "USD"]).nullable(),
});

const dividendEntitlementSchema = z.object({
  scenario: z.enum(["heldout", "equal_baseline"]), event_id: z.string(),
  revision_id: z.string(), symbol: z.string(), ex_open_at: timestamp,
  payment_boundary_at: timestamp, entitled_quantity: z.number().int().nonnegative(),
  amount_per_share: decimal, currency: z.enum(["KRW", "USD"]), gross_native: decimal,
});

const dividendLedgerSchema = z.object({
  scenario: z.enum(["heldout", "equal_baseline"]), event_id: z.string(), symbol: z.string(),
  kind: z.enum(["accrual", "payment"]), at: timestamp, currency: z.enum(["KRW", "USD"]),
  amount_native: decimal, receivable_after_native: decimal, cash_after_native: decimal,
});

const dividendEquitySchema = z.object({
  scenario: z.enum(["heldout", "equal_baseline"]), at: timestamp,
  baseline_equity_krw: decimal, dividend_contribution_krw: decimal.nullable(),
  equity_with_known_dividends_krw: decimal.nullable(), fx_rate: decimal.nullable(),
  fx_observed_on: date.nullable(), fx_available_at: timestamp.nullable(),
  fx_revision: z.string().nullable(),
  receivable_native: z.record(z.string(), decimal), cash_native: z.record(z.string(), decimal),
  reason: z.string().nullable(),
});

const dividendComparisonSchema = z.object({
  scenario: z.enum(["heldout", "equal_baseline", "cash_baseline"]),
  baseline_return_pct: decimal, known_dividend_krw: decimal.nullable(),
  return_with_known_dividends_pct: decimal.nullable(),
  increase_percentage_points: decimal.nullable(),
});

export const dividendOverlaySchema = z.object({
  run_id: z.string().regex(/^[a-f0-9]{64}$/), source_run_id: z.string().regex(/^[a-f0-9]{64}$/),
  created_at: timestamp, source_manifest_sha256: z.string(), source_result_sha256: z.string(),
  review_snapshot_sha256: z.string(), calendar_sha256: z.string(), code_sha256: z.string(),
  calculation_complete: z.boolean(), calculation_reasons: z.array(z.string()),
  coverage_complete: z.literal(false), current_dividend_revision_count: z.number().int().nonnegative(),
  eligible_dividend_count: z.number().int().nonnegative(), excluded_dividend_count: z.number().int().nonnegative(),
  in_period_eligible_count: z.number().int().nonnegative(), in_period_excluded_count: z.number().int().nonnegative(),
  coverage: z.array(dividendCoverageSchema), entitlements: z.array(dividendEntitlementSchema),
  ledger: z.array(dividendLedgerSchema), equity: z.array(dividendEquitySchema),
  position_reconciliations: z.array(z.object({
    scenario: z.enum(["heldout", "equal_baseline"]),
    expected_quantities: z.record(z.string(), z.number().int().nonnegative()),
    replayed_quantities: z.record(z.string(), z.number().int().nonnegative()),
    matches: z.boolean(), quantities_sha256: z.string(),
  })),
  comparisons: z.array(dividendComparisonSchema), assumptions: z.array(z.string()),
  retrospective: z.literal(true), prospective_validation_eligible: z.literal(false),
  automatic_ledger_application: z.literal(false), artifacts: z.array(z.string()),
});
export type DividendOverlay = z.infer<typeof dividendOverlaySchema>;

export async function getLatestDividendOverlay(): Promise<DividendOverlay> {
  const response = await fetch(`${researchBackendUrl()}/api/research/portfolio/dividends/latest`, {
    cache: "no-store", signal: AbortSignal.timeout(10000),
  });
  if (!response.ok) throw new Error("dividend overlay unavailable");
  return dividendOverlaySchema.parse(await response.json());
}

const robustnessMetricSchema = z.object({
  total_return_pct: decimal, max_drawdown_pct: decimal,
  trade_count: z.number().int().nonnegative(), turnover_pct: decimal,
  transaction_cost_krw: decimal, fx_cost_krw: decimal,
});
const oosEvaluationSchema = z.object({
  fold: z.number().int().positive(),
  role: z.enum(["selected_base", "selected_cost_2x", "equal_baseline", "fixed_base", "fixed_cost_2x", "signal_window_15", "signal_window_25", "volatility_window_45", "volatility_window_75"]),
  candidate: portfolioCandidateSchema, config_changes: z.record(z.string(), z.number().int()),
  complete: z.boolean(), incomplete_reasons: z.array(z.string()), metrics: robustnessMetricSchema,
});
export const portfolioRobustnessSchema = z.object({
  run_id: z.string().regex(/^[a-f0-9]{64}$/), source_run_id: z.string().regex(/^[a-f0-9]{64}$/),
  created_at: timestamp, source_manifest_sha256: z.string(), source_result_sha256: z.string(),
  code_sha256: z.string(), specification_sha256: z.string(), calculation_complete: z.boolean(),
  fold_count: z.number().int().nonnegative(), failed_fold_count: z.number().int().nonnegative(),
  simulation_evaluation_count: z.number().int().nonnegative(), union_date_count: z.number().int().nonnegative(),
  unused_tail_start: date.nullable(), unused_tail_end: date.nullable(), unused_tail_count: z.number().int().nonnegative(),
  folds: z.array(z.object({
    fold: z.number().int().positive(), selection_start: date, selection_end: date,
    oos_start: date, oos_end: date, status: z.enum(["completed", "failed"]),
    failure_reason: z.string().nullable(), selected_candidate: portfolioCandidateSchema.nullable(),
    selected_before_oos: z.boolean(),
    validation: z.array(z.object({ fold: z.number().int().positive(), candidate: portfolioCandidateSchema,
      complete: z.boolean(), incomplete_reasons: z.array(z.string()), metrics: robustnessMetricSchema })),
    oos: z.array(oosEvaluationSchema),
  })),
  aggregates: z.array(z.object({
    role: z.string(), fold_count: z.number().int().nonnegative(), median_return_pct: decimal.nullable(),
    worst_return_pct: decimal.nullable(), benchmark_beat_count: z.number().int().nonnegative(),
    benchmark_beat_fraction: decimal.nullable(), zero_trade_fold_count: z.number().int().nonnegative(),
    median_cost_drag_percentage_points: decimal.nullable(),
  })),
  retrospective_reused_history: z.literal(true), prospective_validation_eligible: z.literal(false),
  automatic_promotion_eligible: z.literal(false), limitations: z.array(z.string()), artifacts: z.array(z.string()),
});
export type PortfolioRobustness = z.infer<typeof portfolioRobustnessSchema>;

const signalLatencySchema = z.object({
  sample_count: z.number().int().nonnegative(), median_milliseconds: decimal.nullable(),
  p95_milliseconds: z.number().int().nullable(), maximum_milliseconds: z.number().int().nullable(),
  over_15_seconds_count: z.number().int().nonnegative(), future_over_2_seconds_count: z.number().int().nonnegative(),
});

export const signalValidationSchema = z.object({
  generated_at: timestamp, session_id: z.string(), local_date: date,
  coverage: z.array(z.object({
    symbol: z.string(), exchange: z.string(), local_date: date,
    session_state: z.enum(["completed", "partial", "not_started", "closed", "unavailable"]),
    expected_completed_minutes: z.number().int().nonnegative(), observed_completed_minutes: z.number().int().nonnegative(),
    missing_minutes: z.number().int().nonnegative(), persisted_rows: z.number().int().nonnegative(),
    outside_regular_rows: z.number().int().nonnegative(), incomplete_minute_rows: z.number().int().nonnegative(),
    gaps: z.array(z.object({ start_at: timestamp, end_at: timestamp, minutes: z.number().int().positive() })),
  })),
  latency: signalLatencySchema,
  symbol_latency: z.array(signalLatencySchema.extend({ symbol: z.string(), exchange: z.string() })),
  latency_anomalies: z.object({
    total_count: z.number().int().nonnegative(), limit: z.literal(50), truncated: z.boolean(),
    items: z.array(z.object({
      observation_id: z.string(), symbol: z.string(), exchange: z.string(), reason: z.string(),
      market_at: timestamp, received_at: timestamp, milliseconds: decimal,
      kind: z.enum(["future", "stale"]),
    })).max(50),
  }),
  decisions: z.array(z.object({
    decision_id: z.string(), due_at: timestamp, recorded_at: timestamp, expires_at: timestamp.nullable(),
    input_version: z.string(), input_cutoff_at: timestamp.nullable(), state: z.string(),
    intent_count: z.number().int().nonnegative(), pending_intent_count: z.number().int().nonnegative(),
    fill_count: z.number().int().nonnegative(),
  })),
  executions: z.array(z.object({
    decision_id: z.string(), decision_due_at: timestamp, decision_recorded_at: timestamp,
    input_version: z.string(), input_cutoff_at: timestamp.nullable(), decision_expires_at: timestamp.nullable(),
    fill_id: z.string(), symbol: z.string(), side: z.enum(["buy", "sell"]), quantity: z.number().int().positive(),
    fill_market_at: timestamp, fill_received_at: timestamp, fill_local_price: z.string(), quote_id: z.string(),
    evidence: z.enum(["captured", "legacy_sample_only", "missing", "mismatch"]),
    execution_quote: z.object({ symbol: z.string(), exchange: z.enum(["KRX", "NAS", "NYS", "AMS"]),
      currency: z.enum(["KRW", "USD"]), price: decimal, ask: decimal.nullable(), bid: decimal.nullable(),
      volume: z.number().int().nonnegative(), accumulated_volume: z.number().int().nonnegative(),
      market_at: timestamp, received_at: timestamp, source: z.enum(["KIS H0STCNT0", "KIS HDFSCNT0"]),
      delay_minutes: z.literal(0), realtime_code: z.string().nullable() }).nullable(),
    quote_sha256: z.string().nullable(),
  })),
  durable_feed: z.object({ event_count: z.number().int().nonnegative(), first_event_at: timestamp.nullable(), last_event_at: timestamp.nullable() }),
  current_feed: feedStatusSchema.nullable(), operational_evidence: z.enum(["captured_fills", "operational_unproven"]),
  limitations: z.array(z.string()),
});
export type SignalValidation = z.infer<typeof signalValidationSchema>;

const sha256 = z.string().regex(/^[a-f0-9]{64}$/);
const prospectiveRegistrationSchema = z.object({
  schema_version: z.literal(1), session_id: sha256, session_activated_at: timestamp,
  config: forwardConfigSchema, policy_hash: sha256,
  source_run_id: z.literal("fa0907ecfe86b19836881e5a78a874925fc611978ffe31064eacc82a0a46f687"),
  source_manifest_sha256: sha256, source_result_sha256: sha256, input_sha256: sha256,
  registered_at: timestamp, evaluation_start_at: timestamp, evaluation_end_at: timestamp,
  evaluation_duration_days: z.literal(56),
  code_identity: z.object({ sha256, files: z.record(z.string(), sha256) }),
  evaluation: z.object({
    metrics: z.array(z.object({
      name: z.enum(["net_return_pct", "nav_max_drawdown_pct", "turnover_pct", "transaction_cost_krw", "fx_cost_krw", "execution_quote_evidence"]),
      definition: z.string(),
    })).length(6),
    cash_benchmark_return_pct: decimal, start_nav_requirement: z.string(),
    end_nav_requirement: z.string(), incomplete_rule: z.string(),
  }),
  user_loss_tolerance_pct: z.literal(20), policy_defense_drawdown_pct: decimal,
  paper_only: z.literal(true), automatic_promotion_eligible: z.literal(false),
  contract_sha256: sha256,
});
export const prospectiveRegistrationStatusSchema = z.object({
  status: z.enum(["not_registered", "planned", "observing", "window_elapsed", "identity_mismatch", "invalid_contract"]),
  checked_at: timestamp, reason: z.string().nullable(), current_session_id: sha256.nullable(),
  app_start_code_identity_sha256: sha256.nullable(), current_disk_code_identity_sha256: sha256.nullable(),
  current_source_manifest_sha256: sha256.nullable(), current_source_result_sha256: sha256.nullable(),
  registration: prospectiveRegistrationSchema.nullable(),
});
export type ProspectiveRegistrationStatus = z.infer<typeof prospectiveRegistrationStatusSchema>;

const prospectiveBoundaryReadinessSchema = z.object({
  boundary: z.enum(["start", "end"]), boundary_at: timestamp,
  state: z.enum(["not_due", "missing", "unverified_candidate"]),
  candidate_checkpoint_at: timestamp.nullable(), candidate_actually_known_at: timestamp.nullable(),
});
export const prospectiveReadinessSchema = z.object({
  schema_version: z.literal(1), checked_at: timestamp,
  registration_status: z.enum(["planned", "observing", "window_elapsed"]),
  session_id: sha256, evaluation_start_at: timestamp, evaluation_end_at: timestamp,
  collector_implemented: z.literal(false),
  start_boundary: prospectiveBoundaryReadinessSchema,
  end_boundary: prospectiveBoundaryReadinessSchema,
  execution_evidence: z.object({
    state: z.enum(["unobserved", "linked_integrity", "incomplete"]),
    window_timestamp: z.literal("fill_received_at"),
    total_fill_count: z.number().int().nonnegative(),
    inspected_fill_count: z.number().int().nonnegative().max(5000),
    uninspected_fill_count: z.number().int().nonnegative(),
    captured_count: z.number().int().nonnegative(),
    missing_count: z.number().int().nonnegative(),
    mismatch_count: z.number().int().nonnegative(), truncated: z.boolean(),
  }),
  evaluation_inputs_complete: z.literal(false), limitations: z.array(z.string()),
});
export type ProspectiveReadiness = z.infer<typeof prospectiveReadinessSchema>;

export const boundaryCaptureStatusSchema = z.object({
  checked_at: timestamp, session_id: sha256.nullable(), collector_implemented: z.literal(true),
  running: z.boolean(), last_poll_at: timestamp.nullable(),
  collector_startup_sha256: sha256, collector_current_sha256: sha256.nullable(),
  boundaries: z.array(z.object({
    boundary: z.enum(["start", "end"]), boundary_at: timestamp,
    state: z.enum(["scheduled", "collecting", "captured_raw", "captured_with_issues", "error"]),
    artifact_sha256: sha256.nullable(), read_started_at: timestamp.nullable(),
    read_finished_at: timestamp.nullable(), capture_lag_seconds: decimal.nullable(),
    issue_count: z.number().int().nonnegative(), download_available: z.boolean(),
    error_code: z.enum(["lock_busy", "identity_unavailable", "collector_identity_changed", "database_unavailable", "artifact_invalid", "capture_failed"]).nullable(),
  })).length(2),
  limitations: z.array(z.string()),
});
export type BoundaryCaptureStatus = z.infer<typeof boundaryCaptureStatusSchema>;

const boundaryEvidenceCheckSchema = z.object({
  name: z.string(), state: z.enum(["pass", "fail", "unknown", "not_applicable"]), detail: z.string(),
});
export const boundaryEvidenceSchema = z.object({
  schema_version: z.literal(1), boundary: z.enum(["start", "end"]), boundary_at: timestamp,
  state: z.enum(["not_due", "missing", "unavailable", "inspected"]),
  reason: z.enum(["boundary_not_due", "capture_missing", "capture_unavailable"]).nullable(),
  artifact_sha256: sha256.nullable(), session_id: sha256.nullable(),
  checks: z.array(boundaryEvidenceCheckSchema),
  fill_total_count: z.number().int().nonnegative(), fill_detail_count: z.number().int().nonnegative().max(50),
  fill_omitted_count: z.number().int().nonnegative(), fill_failed_count: z.number().int().nonnegative(),
  fill_unknown_count: z.number().int().nonnegative(), post_boundary_fill_count: z.number().int().nonnegative(),
  fills: z.array(z.object({
    fill_id: sha256, symbol: z.string(), side: z.enum(["buy", "sell"]), received_at: timestamp,
    after_boundary: z.boolean(), stored_local_price: decimal, expected_local_price: decimal.nullable(),
    stored_notional_krw: decimal, expected_notional_krw: decimal.nullable(), checks: z.array(boundaryEvidenceCheckSchema),
  })).max(50),
  position_total_count: z.number().int().nonnegative(), position_detail_count: z.number().int().nonnegative().max(50),
  position_omitted_count: z.number().int().nonnegative(),
  positions: z.array(z.object({
    symbol: z.string(), currency: z.enum(["KRW", "USD"]), quantity: z.number().int().nonnegative(),
    checks: z.array(boundaryEvidenceCheckSchema),
  })).max(50),
  accepted_nav: z.literal(false), evaluation_inputs_complete: z.literal(false), limitations: z.array(z.string()),
});
export type BoundaryEvidence = z.infer<typeof boundaryEvidenceSchema>;

export async function getSignalValidation(localDate?: string): Promise<SignalValidation> {
  const query = localDate ? `?local_date=${encodeURIComponent(localDate)}` : "";
  const response = await fetch(`${researchBackendUrl()}/api/research/validation/signal${query}`, {
    cache: "no-store", signal: AbortSignal.timeout(15000),
  });
  if (!response.ok) throw new Error("signal validation unavailable");
  return signalValidationSchema.parse(await response.json());
}

export async function getProspectiveRegistrationStatus(): Promise<ProspectiveRegistrationStatus> {
  const response = await fetch(`${researchBackendUrl()}/api/research/validation/prospective`, {
    cache: "no-store", signal: AbortSignal.timeout(20000),
  });
  if (!response.ok) throw new Error("prospective registration unavailable");
  return prospectiveRegistrationStatusSchema.parse(await response.json());
}

export async function getProspectiveReadiness(): Promise<ProspectiveReadiness> {
  const response = await fetch(`${researchBackendUrl()}/api/research/validation/prospective/readiness`, {
    cache: "no-store", signal: AbortSignal.timeout(20000),
  });
  if (!response.ok) throw new Error("prospective readiness unavailable");
  return prospectiveReadinessSchema.parse(await response.json());
}

export async function getBoundaryCaptureStatus(): Promise<BoundaryCaptureStatus> {
  const response = await fetch(`${researchBackendUrl()}/api/research/validation/prospective/boundary-captures`, {
    cache: "no-store", signal: AbortSignal.timeout(20000),
  });
  if (!response.ok) throw new Error("boundary capture status unavailable");
  return boundaryCaptureStatusSchema.parse(await response.json());
}

export async function getBoundaryEvidence(boundary: "start" | "end"): Promise<BoundaryEvidence> {
  const response = await fetch(`${researchBackendUrl()}/api/research/validation/prospective/boundary-evidence/${boundary}`, {
    cache: "no-store", signal: AbortSignal.timeout(20000),
  });
  if (!response.ok) throw new Error("boundary evidence unavailable");
  return boundaryEvidenceSchema.parse(await response.json());
}

export async function getLatestPortfolioRobustness(): Promise<PortfolioRobustness> {
  const response = await fetch(`${researchBackendUrl()}/api/research/validation/portfolio/latest`, {
    cache: "no-store", signal: AbortSignal.timeout(15000),
  });
  if (!response.ok) throw new Error("portfolio robustness unavailable");
  return portfolioRobustnessSchema.parse(await response.json());
}

export async function getResearchHistory(cursor?: string): Promise<HistoryPage> {
  const query = new URLSearchParams({ limit: "25" });
  if (cursor) query.set("cursor", cursor);
  const response = await fetch(`${researchBackendUrl()}/api/research/history?${query}`, {
    cache: "no-store", signal: AbortSignal.timeout(10000),
  });
  if (!response.ok) throw new Error("research history unavailable");
  return historyPageSchema.parse(await response.json());
}
