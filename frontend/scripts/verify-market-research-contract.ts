import { marketResearchRunSchema } from "../lib/marketResearch";

const request = {
  market: "US" as const,
  start_date: "2025-09-11",
  end_date: "2026-09-11",
  stage: "pilot" as const,
  pilot_run_id: null,
  initial_cash_krw: "100000000",
  fee_rate: "0.00015",
  slippage_rate: "0.001",
  sell_tax_rate: "0.0018",
  research_grade: "approximate" as const,
};

const current = {
  id: "fixture-run",
  status: "completed" as const,
  request,
  result: {
    market: "US" as const,
    request,
    readiness: {
      market: "US" as const,
      checked_at: "2026-09-15T01:10:31.457295Z",
      capabilities: [],
      ready: true,
      simulated: true,
      research_grade: "approximate" as const,
    },
    status: "approximate" as const,
    completeness: "approximate" as const,
    candidate_evidence: [],
    trades: [],
    equity: [],
    limitations: [],
    metrics: {},
    input_hash: null,
    policy_hash: null,
    stage: "pilot" as const,
    pilot_run_id: null,
    data_contract_hash: null,
    warmup_sessions: [],
    research_grade: "approximate" as const,
    pool_contract_hash: null,
    provenance: {
      universe_sources: ["fixture" as const],
      bar_sources: ["fixture" as const],
      fx_sources: null,
      artifact_sources: ["fixture" as const],
      normalization_version: "pit-v1",
      captured_at: "2026-09-15T01:10:31.457295Z",
    },
  },
  input_hash: null,
  created_at: "2026-09-15T01:10:31.457295Z",
  updated_at: "2026-09-15T01:10:31.457295Z",
  error: null,
  stage: "pilot" as const,
  pilot_run_id: null,
  data_contract_hash: null,
  final_promotable: false,
  final_promotability_reason: "fixture",
};

const assertRejects = (value: unknown, label: string): void => {
  if (marketResearchRunSchema.safeParse(value).success) {
    throw new Error(`${label} unexpectedly parsed`);
  }
};

marketResearchRunSchema.parse(current);

const legacy = structuredClone(current);
const legacyResult = { ...legacy.result };
delete (legacyResult as { provenance?: typeof legacy.result.provenance }).provenance;
marketResearchRunSchema.parse({ ...legacy, result: legacyResult });

const emptyNormalization = structuredClone(current);
emptyNormalization.result.provenance.normalization_version = "";
assertRejects(emptyNormalization, "empty normalization_version");

const malformedCapturedAt = structuredClone(current);
malformedCapturedAt.result.provenance.captured_at = "2026-09-15T01:10:31.457295";
assertRejects(malformedCapturedAt, "timezone-less captured_at");

console.log("current, legacy, empty normalization, and malformed timestamp checks: PASS");
