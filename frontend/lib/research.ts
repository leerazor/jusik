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
