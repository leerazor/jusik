import { z } from "zod";
import { researchBackendUrl } from "@/lib/research";

const capabilitySchema = z.object({
  name: z.enum(["credentials", "entitlement", "calendar", "membership", "bars", "actions", "fx", "policy"]),
  status: z.enum(["ready", "missing", "unsupported", "partial"]),
  detail: z.string(),
  missing_ranges: z.array(z.string()),
});

const researchGradeSchema = z.enum(["strict", "approximate"]);
const sourceNameSchema = z.enum(["fixture", "krx", "massive", "yahoo", "alpha_vantage", "fred", "approximate_file"]);

export const marketReadinessSchema = z.object({
  market: z.enum(["KR", "US"]),
  checked_at: z.string(),
  capabilities: z.array(capabilitySchema),
  ready: z.boolean(),
  simulated: z.boolean(),
  research_grade: researchGradeSchema,
});

const requestSchema = z.object({
  market: z.enum(["KR", "US"]),
  start_date: z.string(),
  end_date: z.string(),
  stage: z.enum(["pilot", "final", "legacy"]),
  pilot_run_id: z.string().nullable(),
  initial_cash_krw: z.string(),
  fee_rate: z.string(),
  slippage_rate: z.string(),
  sell_tax_rate: z.string(),
  research_grade: researchGradeSchema,
});

const tradeSchema = z.object({
  session: z.string(),
  signal_session: z.string(),
  fill_session: z.string(),
  symbol: z.string(),
  side: z.enum(["buy", "sell"]),
  quantity: z.number(),
  currency: z.enum(["KRW", "USD"]),
  market_open: z.string(),
  fill_price: z.string(),
  notional: z.string(),
  fee: z.string(),
  tax: z.string(),
  rationale: z.string(),
});

export const marketResearchProvenanceSchema = z.object({
  universe_sources: z.array(sourceNameSchema).nullable(),
  bar_sources: z.array(sourceNameSchema).nullable(),
  fx_sources: z.array(sourceNameSchema).nullable(),
  artifact_sources: z.array(sourceNameSchema).nullable(),
  normalization_version: z.string().nullable(),
  captured_at: z.string().nullable(),
});

const resultSchema = z.object({
  market: z.enum(["KR", "US"]),
  request: requestSchema,
  readiness: marketReadinessSchema,
  status: z.enum(["ready", "insufficient", "approximate"]),
  completeness: z.enum(["complete", "incomplete", "approximate"]),
  candidate_evidence: z.array(z.object({
    session: z.string(), symbol: z.string(), rank: z.number(), volume: z.string(),
    eligible: z.boolean(), membership_available_at: z.string().nullable(), bar_available_at: z.string().nullable(),
  })),
  trades: z.array(tradeSchema),
  equity: z.array(z.object({
    session: z.string(), cash_krw: z.string(), cash_native: z.string(), invested_krw: z.string(),
    nav_krw: z.string(), fx_krw_per_usd: z.string(), drawdown_pct: z.string(),
  })),
  limitations: z.array(z.string()),
  metrics: z.record(z.string(), z.string()),
  input_hash: z.string().nullable(),
  policy_hash: z.string().nullable(),
  stage: z.enum(["pilot", "final", "legacy"]),
  pilot_run_id: z.string().nullable(),
  data_contract_hash: z.string().nullable(),
  warmup_sessions: z.array(z.string()),
  research_grade: researchGradeSchema,
  pool_contract_hash: z.string().nullable(),
  provenance: marketResearchProvenanceSchema.nullable().optional(),
});

export const marketResearchRunSchema = z.object({
  id: z.string(),
  status: z.enum(["queued", "running", "completed", "insufficient", "failed"]),
  request: requestSchema,
  result: resultSchema.nullable(),
  input_hash: z.string().nullable(),
  created_at: z.string(),
  updated_at: z.string(),
  error: z.string().nullable(),
  stage: z.enum(["pilot", "final", "legacy"]),
  pilot_run_id: z.string().nullable(),
  data_contract_hash: z.string().nullable(),
  final_promotable: z.boolean(),
  final_promotability_reason: z.string(),
});

export type MarketReadiness = z.infer<typeof marketReadinessSchema>;
export type MarketResearchProvenance = z.infer<typeof marketResearchProvenanceSchema>;
export type MarketResearchRun = z.infer<typeof marketResearchRunSchema>;

export async function getMarketReadiness(
  market?: "KR" | "US",
  grade: "strict" | "approximate" = "strict",
): Promise<MarketReadiness[]> {
  const params = new URLSearchParams({ grade });
  if (market) params.set("market", market);
  const response = await fetch(`${researchBackendUrl()}/api/research/market/status?${params.toString()}`, { cache: "no-store" });
  if (!response.ok) throw new Error("market research unavailable");
  return z.array(marketReadinessSchema).parse(await response.json());
}

export async function getMarketResearchRuns(): Promise<MarketResearchRun[]> {
  const response = await fetch(`${researchBackendUrl()}/api/research/market/runs`, { cache: "no-store" });
  if (!response.ok) throw new Error("market research unavailable");
  return z.array(marketResearchRunSchema).parse(await response.json());
}

export async function getMarketResearchRun(id: string): Promise<MarketResearchRun> {
  const response = await fetch(`${researchBackendUrl()}/api/research/market/runs/${encodeURIComponent(id)}`, { cache: "no-store" });
  if (!response.ok) throw new Error("market research unavailable");
  return marketResearchRunSchema.parse(await response.json());
}

export function marketAmount(value: string): string {
  return new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 2 }).format(Number(value));
}
