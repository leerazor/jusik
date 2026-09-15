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
    account: {
      account_scope: "market_specific_independent_simulated" as const,
      reporting_currency: "KRW" as const,
      native_currency: "USD" as const,
      initial_cash_krw: "100000000.00",
      fx_krw_per_usd: "1300.0",
      initial_cash_conversion: "initial_krw_to_usd" as const,
    },
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
delete (legacyResult as { account?: typeof legacy.result.account }).account;
marketResearchRunSchema.parse({ ...legacy, result: legacyResult });

const kr = {
  ...current,
  request: { ...current.request, market: "KR" as const },
  result: {
    ...current.result,
    market: "KR" as const,
    request: { ...current.result.request, market: "KR" as const },
    readiness: { ...current.result.readiness, market: "KR" as const },
    account: {
      ...current.result.account,
      native_currency: "KRW" as const,
      fx_krw_per_usd: "1.0",
      initial_cash_conversion: "identity" as const,
    },
  },
};
marketResearchRunSchema.parse(kr);

const equivalentExponent = {
  ...current,
  result: {
    ...current.result,
    account: {
      ...current.result.account,
      initial_cash_krw: "1e8",
      fx_krw_per_usd: "13e2",
    },
  },
};
marketResearchRunSchema.parse(equivalentExponent);

const emptyNormalization = structuredClone(current);
emptyNormalization.result.provenance.normalization_version = "";
assertRejects(emptyNormalization, "empty normalization_version");

const malformedCapturedAt = structuredClone(current);
malformedCapturedAt.result.provenance.captured_at = "2026-09-15T01:10:31.457295";
assertRejects(malformedCapturedAt, "timezone-less captured_at");

const contradictoryAccount = {
  ...current,
  result: {
    ...current.result,
    account: {
      ...current.result.account,
      native_currency: "KRW" as const,
    },
  },
};
assertRejects(contradictoryAccount, "US account with KRW native currency");

for (const invalid of ["0", "-1", "not-a-number", "NaN", "Infinity"]) {
  const invalidInitial = {
    ...current,
    result: {
      ...current.result,
      account: { ...current.result.account, initial_cash_krw: invalid },
    },
  };
  assertRejects(invalidInitial, `invalid initial_cash_krw ${invalid}`);
  const invalidFx = {
    ...current,
    result: {
      ...current.result,
      account: { ...current.result.account, fx_krw_per_usd: invalid },
    },
  };
  assertRejects(invalidFx, `invalid fx_krw_per_usd ${invalid}`);
}

const precisionNearCapital = {
  ...current,
  result: {
    ...current.result,
    account: {
      ...current.result.account,
      initial_cash_krw: "100000000.0000000000000000001",
    },
  },
};
assertRejects(precisionNearCapital, "precision-near-but-distinct initial cash");

console.log("US, KR, legacy, decimal, and contradictory currency checks: PASS");
