import type { MarketResearchResult, MarketResearchRun } from "../lib/marketResearch";

type EquityRow = MarketResearchResult["equity"][number];

export type MarketResearchFixtureExpectation = {
  navStatus: "available" | "unavailable";
  drawdownStatus: "available" | "unavailable";
  navValues: Array<number | null>;
  drawdownValues: Array<number | null>;
  krwReturn: string;
  preservesStoredNav: boolean;
  preservesGrade: boolean;
  preservesCoverage: boolean;
  preservesError: boolean;
};

export type MarketResearchFixtureScenario = {
  id: string;
  description: string;
  seed: 0;
  run: MarketResearchRun;
  expected: MarketResearchFixtureExpectation;
};

const request = {
  market: "US" as const,
  start_date: "2026-01-05",
  end_date: "2026-01-09",
  stage: "pilot" as const,
  pilot_run_id: null,
  initial_cash_krw: "100000000",
  fee_rate: "0.00015",
  slippage_rate: "0.001",
  sell_tax_rate: "0.0018",
  research_grade: "approximate" as const,
} satisfies MarketResearchRun["request"];

const readiness = {
  market: "US" as const,
  checked_at: "2026-01-05T01:00:00Z",
  capabilities: [{ name: "bars" as const, status: "ready" as const, detail: "fixture bars", missing_ranges: [] }],
  ready: true,
  simulated: true,
  research_grade: "approximate" as const,
} satisfies MarketResearchResult["readiness"];

const account = {
  account_scope: "market_specific_independent_simulated" as const,
  reporting_currency: "KRW" as const,
  native_currency: "USD" as const,
  initial_cash_krw: "100000000" as const,
  fx_krw_per_usd: "1300" as const,
  initial_cash_conversion: "initial_krw_to_usd" as const,
} satisfies NonNullable<MarketResearchResult["account"]>;

const baseEquity: EquityRow[] = [
  { session: "2026-01-05", cash_krw: "100000000", cash_native: "76923.0769", invested_krw: "0", nav_krw: "100000000", fx_krw_per_usd: "1300", drawdown_pct: "0" },
  { session: "2026-01-06", cash_krw: "0", cash_native: "0", invested_krw: "102000000", nav_krw: "102000000", fx_krw_per_usd: "1300", drawdown_pct: "0" },
  { session: "2026-01-07", cash_krw: "0", cash_native: "0", invested_krw: "99000000", nav_krw: "99000000", fx_krw_per_usd: "1300", drawdown_pct: "2.9411764706" },
];

const baseResult: MarketResearchResult = {
  market: "US",
  request,
  readiness,
  status: "ready",
  completeness: "complete",
  candidate_evidence: [],
  trades: [],
  equity: baseEquity,
  limitations: [],
  metrics: { final_nav_krw: "99000000", return_pct: "-1", trade_count: "0", coverage_sessions: "3" },
  input_hash: null,
  policy_hash: null,
  stage: "pilot",
  pilot_run_id: null,
  data_contract_hash: null,
  warmup_sessions: [],
  research_grade: "approximate",
  pool_contract_hash: null,
  account,
  provenance: null,
};

const baseRun: MarketResearchRun = {
  id: "fixture-r3-equity-base",
  status: "completed",
  request,
  result: baseResult,
  input_hash: null,
  created_at: "2026-01-05T01:00:00Z",
  updated_at: "2026-01-05T01:00:00Z",
  error: null,
  stage: "pilot",
  pilot_run_id: null,
  data_contract_hash: null,
  final_promotable: false,
  final_promotability_reason: "fixture",
};

const krRequest = { ...request, market: "KR" as const, research_grade: "strict" as const };
const krReadiness = { ...readiness, market: "KR" as const, research_grade: "strict" as const, simulated: true };
const krAccount = { ...account, native_currency: "KRW" as const, initial_cash_krw: "100000000" as const, fx_krw_per_usd: "1" as const, initial_cash_conversion: "identity" as const };

function makeScenario(
  id: string,
  description: string,
  equity: EquityRow[],
  options: {
    request?: MarketResearchRun["request"];
    readiness?: MarketResearchResult["readiness"];
    account?: MarketResearchResult["account"];
    status?: MarketResearchRun["status"];
    resultStatus?: MarketResearchResult["status"];
    completeness?: MarketResearchResult["completeness"];
    limitations?: string[];
    error?: string | null;
    removeMetadata?: boolean;
    expected?: Partial<MarketResearchFixtureExpectation>;
  } = {},
): MarketResearchFixtureScenario {
  const result: MarketResearchResult = {
    ...baseResult,
    market: (options.request ?? request).market,
    research_grade: (options.request ?? request).research_grade,
    request: options.request ?? request,
    readiness: options.readiness ?? readiness,
    account: options.removeMetadata ? undefined : options.account === undefined ? account : options.account,
    provenance: options.removeMetadata ? undefined : null,
    equity,
    status: options.resultStatus ?? "ready",
    completeness: options.completeness ?? "complete",
    limitations: ["화면 검사용 합성 fixture, 경제 not-evaluated", ...(options.limitations ?? [])],
  };
  const run: MarketResearchRun = {
    ...baseRun,
    id,
    status: options.status ?? "completed",
    request: result.request,
    result,
    error: options.error ?? null,
    stage: result.stage,
  };
  return {
    id,
    description,
    seed: 0,
    run,
    expected: {
      navStatus: "available",
      drawdownStatus: "available",
      navValues: equity.map((item) => Number(item.nav_krw)),
      drawdownValues: equity.map((item) => Number(item.drawdown_pct)),
      krwReturn: "-1%",
      preservesStoredNav: true,
      preservesGrade: true,
      preservesCoverage: true,
      preservesError: run.error !== null,
      ...options.expected,
    },
  };
}

export const marketResearchFixtureScenarios: MarketResearchFixtureScenario[] = [
  makeScenario("valid-kr", "KRW NAV와 strict KR identity FX의 정상 곡선", [
    { ...baseEquity[0], session: "2026-01-05", nav_krw: "100000000", fx_krw_per_usd: "1", drawdown_pct: "0" },
    { ...baseEquity[1], session: "2026-01-06", nav_krw: "105000000", fx_krw_per_usd: "1", drawdown_pct: "0" },
    { ...baseEquity[2], session: "2026-01-07", nav_krw: "102000000", fx_krw_per_usd: "1", drawdown_pct: "2.8571428571" },
  ], { request: krRequest, readiness: krReadiness, account: krAccount, expected: { navValues: [100000000, 105000000, 102000000], drawdownValues: [0, 0, 2.8571428571], krwReturn: "2%" } }),
  makeScenario("signed-nav", "음수·0 NAV와 100% 초과 기록 낙폭 보존", [
    { ...baseEquity[0], nav_krw: "-100", drawdown_pct: "0" },
    { ...baseEquity[1], nav_krw: "0", drawdown_pct: "150" },
    { ...baseEquity[2], nav_krw: "250", drawdown_pct: "250" },
  ], { expected: { navValues: [-100, 0, 250], drawdownValues: [0, 150, 250], krwReturn: "-100%" } }),
  makeScenario("single-point", "단일 저장점은 점으로 표시", [baseEquity[0]], { expected: { navValues: [100000000], drawdownValues: [0], krwReturn: "0%" } }),
  makeScenario("empty-equity", "빈 평가 시계열은 확인 불가", [], { expected: { navStatus: "unavailable", drawdownStatus: "unavailable", navValues: [], drawdownValues: [], krwReturn: "확인 불가" } }),
  makeScenario("numeric-gaps", "NaN·Infinity·빈 문자열은 null 구간", [
    { ...baseEquity[0], nav_krw: "100", drawdown_pct: "0" },
    { ...baseEquity[1], nav_krw: "NaN", drawdown_pct: "" },
    { ...baseEquity[2], nav_krw: "120", drawdown_pct: "2" },
    { ...baseEquity[0], session: "2026-01-08", nav_krw: "130", drawdown_pct: "3" },
    { ...baseEquity[1], session: "2026-01-09", nav_krw: "Infinity", drawdown_pct: "NaN" },
  ], { expected: { navValues: [100, null, 120, 130, null], drawdownValues: [0, null, 2, 3, null], krwReturn: "확인 불가" } }),
  makeScenario("invalid-calendar-date", "달력에 없는 실제 날짜는 전체 곡선 무효", [
    { ...baseEquity[0], session: "2026-01-05" },
    { ...baseEquity[1], session: "2026-02-30" },
  ], { request: { ...request, end_date: "2026-03-10" }, expected: { navStatus: "unavailable", drawdownStatus: "unavailable", navValues: [], drawdownValues: [], krwReturn: "확인 불가" } }),
  makeScenario("duplicate-date", "중복 날짜는 정렬·복구하지 않음", [
    { ...baseEquity[0], session: "2026-01-06" },
    { ...baseEquity[1], session: "2026-01-06" },
  ], { expected: { navStatus: "unavailable", drawdownStatus: "unavailable", navValues: [], drawdownValues: [], krwReturn: "확인 불가" } }),
  makeScenario("reverse-date", "요청 기간 안 역순 날짜는 전체 곡선 무효", [
    { ...baseEquity[0], session: "2026-01-08" },
    { ...baseEquity[1], session: "2026-01-05" },
  ], { expected: { navStatus: "unavailable", drawdownStatus: "unavailable", navValues: [], drawdownValues: [], krwReturn: "확인 불가" } }),
  makeScenario("invalid-values", "공백·hex·overflow·underflow와 음수 낙폭 구분", [
    { ...baseEquity[0], nav_krw: "", drawdown_pct: "-1" },
    { ...baseEquity[1], nav_krw: " ", drawdown_pct: "Infinity" },
    { ...baseEquity[2], nav_krw: "0x10", drawdown_pct: "text" },
    { ...baseEquity[0], session: "2026-01-08", nav_krw: "1e309", drawdown_pct: "0" },
    { ...baseEquity[1], session: "2026-01-09", nav_krw: "1e-9999", drawdown_pct: "0" },
  ], { expected: { navStatus: "unavailable", navValues: [null, null, null, null, null], drawdownValues: [null, null, null, 0, 0], krwReturn: "확인 불가" } }),
  makeScenario("missing-us-fx", "USD account FX 누락 시 저장 NAV와 수익률을 분리", [
    { ...baseEquity[0], fx_krw_per_usd: "" },
    { ...baseEquity[1], fx_krw_per_usd: "1300" },
  ], { account: { ...account, fx_krw_per_usd: null }, expected: { navValues: [100000000, 102000000], drawdownValues: [0, 0], krwReturn: "확인 불가" } }),
  makeScenario("legacy-no-metadata", "metadata 없는 legacy도 저장 NAV·낙폭은 표시", [baseEquity[0], baseEquity[1]], { removeMetadata: true, expected: { navValues: [100000000, 102000000], drawdownValues: [0, 0], krwReturn: "확인 불가" } }),
  makeScenario("status-error-preserved", "insufficient 상태·등급·coverage·안전한 오류 보존", [baseEquity[0]], {
    status: "insufficient",
    resultStatus: "insufficient",
    completeness: "incomplete",
    limitations: ["fixture coverage unavailable"],
    error: "safe fixture error",
    expected: { navValues: [100000000], drawdownValues: [0], krwReturn: "0%" },
  }),
];

export const marketResearchBrowserFixturePayloads: Record<string, MarketResearchRun> = Object.fromEntries(
  marketResearchFixtureScenarios.map((scenario) => [scenario.id, scenario.run]),
);
