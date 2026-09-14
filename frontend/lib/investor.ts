import { z } from "zod";

const decimal = z.string().regex(/^-?\d+(\.\d+)?$/);
const timestamp = z.iso.datetime({ offset: true });
export const marketSchema = z.enum(["KR", "US"]);
export const instrumentSchema = z.object({
  market: marketSchema,
  exchange: z.string().min(1),
  symbol: z.string().min(1),
  currency: z.enum(["KRW", "USD"]),
  name: z.string().min(1),
  instrument_type: z.enum(["stock", "etf", "unknown"]),
});
const quoteSchema = z.object({
  price: decimal.nullable(), currency: z.enum(["KRW", "USD"]), as_of: timestamp.nullable(),
  fetched_at: timestamp, source: z.string(), source_url: z.string().url().nullable(), unavailable_reason: z.string().nullable(),
});
const factsSchema = z.object({
  eps: decimal.nullable(), eps_period: z.string().nullable(), per: decimal.nullable(), pbr: decimal.nullable(),
  growth: decimal.nullable(), roe: decimal.nullable(), debt_ratio: decimal.nullable(), period_end: z.iso.date().nullable(),
  growth_period_end: z.iso.date().nullable(), roe_period_end: z.iso.date().nullable(), debt_period_end: z.iso.date().nullable(),
  source: z.string().nullable(), source_url: z.string().url().nullable(), fetched_at: timestamp.nullable(), unavailable_reasons: z.array(z.string()),
});
const trendSchema = z.object({
  breakout_observed: z.boolean().nullable(), deterioration_observed: z.boolean().nullable(),
  latest_completed_session: z.iso.date().nullable(), rule_version: z.string(), source: z.string().nullable(), source_url: z.string().url().nullable(), unavailable_reasons: z.array(z.string()),
});
export const analysisSchema = z.object({
  instrument: instrumentSchema, quote: quoteSchema, fundamentals: factsSchema, trend: trendSchema,
  entry_kind: z.enum(["value", "trend"]), value_entry_status: z.enum(["review", "unassessed", "exit_review"]),
  trend_entry_status: z.enum(["review", "unassessed", "exit_review"]), reasons: z.array(z.string()), rule_version: z.string(), analyzed_at: timestamp,
  assumed_value_lower: decimal.nullable(), assumed_value_upper: decimal.nullable(), assumed_safety_price: decimal.nullable(),
});
export const detailSchema = z.object({ instrument: instrumentSchema, analysis: analysisSchema, limitations: z.array(z.string()) });
export const candidateSchema = z.object({ instrument: instrumentSchema, rank: z.number().int().positive(), reason: z.string(), source: z.string(), observed_at: timestamp });
export const discoverySchema = z.object({ market: marketSchema, candidates: z.array(candidateSchema), coverage: z.string(), truncated: z.boolean(), partial: z.boolean(), errors: z.array(z.string()), fetched_at: timestamp });
export const valuationSchema = z.object({ normalized_eps: decimal.nullable(), eps_period: z.string().nullable(), target_pe_lower: decimal.nullable(), target_pe_upper: decimal.nullable(), margin_of_safety: decimal.nullable(), rationale: z.string().nullable() });
export const thesisSchema = z.object({
  instrument: instrumentSchema, state: z.enum(["watch", "holding", "closed"]), entry_kind: z.enum(["value", "trend"]), why: z.string(), source_references: z.array(z.string()), invalidation_criteria: z.string(), next_review: z.iso.date(), health: z.enum(["intact", "broken", "unknown"]), risk_price: decimal.nullable(), valuation: valuationSchema.nullable(), expected_revision: z.number().int().nonnegative().optional(), id: z.string(), revision: z.number().int().positive(), created_at: timestamp, updated_at: timestamp, evidence: analysisSchema, current_analysis: analysisSchema.nullable(), review: z.object({ decision: z.enum(["hold_review", "exit_review", "deferred", "closed"]), reasons: z.array(z.string()), review_overdue: z.boolean() }),
});
export type Discovery = z.infer<typeof discoverySchema>;
export type Detail = z.infer<typeof detailSchema>;
export type Thesis = z.infer<typeof thesisSchema>;

export function backendUrl(): string { return process.env.JUSIK_BACKEND_URL ?? "http://127.0.0.1:8000"; }
export async function getInvestorCandidates(market: "KR" | "US"): Promise<Discovery | null> {
  try { const response = await fetch(`${backendUrl()}/api/investor/candidates?market=${market}`, { cache: "no-store" }); return response.ok ? discoverySchema.parse(await response.json()) : null; } catch { return null; }
}
export async function getInvestorDetail(market: "KR" | "US", symbol: string, exchange?: string): Promise<Detail | null> {
  try { const query = new URLSearchParams({ market, symbol }); if (exchange) query.set("exchange", exchange); const response = await fetch(`${backendUrl()}/api/investor/instrument?${query}`, { cache: "no-store" }); return response.ok ? detailSchema.parse(await response.json()) : null; } catch { return null; }
}
export async function getTheses(): Promise<Thesis[]> {
  try { const response = await fetch(`${backendUrl()}/api/investor/theses`, { cache: "no-store" }); return response.ok ? z.array(thesisSchema).parse(await response.json()) : []; } catch { return []; }
}
