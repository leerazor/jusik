import {
  marketResearchCapabilityStatusLabel,
  marketResearchCompletenessLabel,
  marketResearchCounter,
  marketResearchCoverageLabel,
  marketResearchEquityCurves,
  marketResearchGradeIsConsistent,
  marketResearchKrwReturn,
  marketResearchUsdReturn,
  marketResearchMdd,
  marketResearchNullResultMessage,
  marketResearchProvisionalLabel,
  marketResearchReadinessLabel,
  marketResearchResultStatusLabel,
  marketResearchRunLabel,
  marketResearchRunSchema,
} from "../lib/marketResearch";
import { marketResearchFixtureScenarios } from "./market-research-fixtures";

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
      capabilities: [
        { name: "bars" as const, status: "partial" as const, detail: "fixture partial bars", missing_ranges: ["2025-09-12", "2025-09-13"] },
        { name: "calendar" as const, status: "ready" as const, detail: "fixture calendar", missing_ranges: [] },
      ],
      ready: true,
      simulated: true,
      research_grade: "approximate" as const,
    },
    status: "approximate" as const,
    completeness: "approximate" as const,
    candidate_evidence: [],
    trades: [],
    equity: [],
    limitations: ["보유 종목 AAA은 1세션 전 마지막 가격으로 평가합니다(추정값)."],
    metrics: {
      coverage_sessions: "3",
      expected_candidate_bars: "6",
      usable_candidate_bars: "5",
      excluded_nonheld_bars: "1",
      missing_held_bars: "1",
      trade_count: "0",
    },
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
if (!marketResearchReadinessLabel(current.result.readiness).includes("근사 등급 · 합성 자료")) {
  throw new Error("approximate synthetic readiness label missing");
}
if (!marketResearchRunLabel(current).includes("시뮬레이션 연구 실행 · PAPER 별도")) {
  throw new Error("simulation/PAPER execution label missing");
}
if (marketResearchCapabilityStatusLabel("partial") !== "부분 확인") {
  throw new Error("capability partial label missing");
}
if (!marketResearchProvisionalLabel(current.result).includes("bars 부분 확인")) {
  throw new Error("capability-derived provisional reason missing");
}
if (marketResearchResultStatusLabel("approximate") !== "근사 결과" || marketResearchCompletenessLabel("approximate") !== "근사") {
  throw new Error("result status/completeness labels missing");
}
if (marketResearchCoverageLabel("5", "6") !== "5 / 6 (83.33%)") {
  throw new Error("coverage ratio label missing");
}
if (marketResearchCoverageLabel("0", "0") !== "확인 불가") {
  throw new Error("zero denominator must remain unknown");
}
if (marketResearchCoverageLabel("NaN", "6") !== "확인 불가" || marketResearchCoverageLabel("1.5", "6") !== "확인 불가" || marketResearchCoverageLabel("-1", "6") !== "확인 불가") {
  throw new Error("malformed or negative counters must remain unknown");
}
if (!marketResearchCoverageLabel("7", "6").includes("116.67%")) {
  throw new Error("coverage ratio must not clamp numerator");
}
if (marketResearchCounter("0", "건") !== "0건" || marketResearchCounter("bad", "건") !== "확인 불가") {
  throw new Error("counter zero/unknown labels missing");
}
if (!marketResearchGradeIsConsistent(current)) {
  throw new Error("matching result grades must remain displayable");
}
for (const [label, mismatched] of [
  ["run request", { ...current, request: { ...current.request, research_grade: "strict" as const } }],
  ["result request", { ...current, result: { ...current.result, request: { ...current.result.request, research_grade: "strict" as const } } }],
  ["result", { ...current, result: { ...current.result, research_grade: "strict" as const } }],
  ["readiness", { ...current, result: { ...current.result, readiness: { ...current.result.readiness, research_grade: "strict" as const } } }],
] as const) {
  if (marketResearchGradeIsConsistent(mismatched)) {
    throw new Error(`${label} grade mismatch must be unknown`);
  }
}

const queued = { ...current, status: "queued" as const, result: null };
marketResearchRunSchema.parse(queued);
if (!marketResearchGradeIsConsistent(queued)) {
  throw new Error("null result must preserve existing display flow");
}
if (marketResearchNullResultMessage(queued).heading !== "실행 대기 중") {
  throw new Error("queued null result must be queued");
}
const running = { ...current, status: "running" as const, result: null };
if (marketResearchNullResultMessage(running).heading !== "연구 실행 중") {
  throw new Error("running null result must be running");
}
const failedRun = { ...current, status: "failed" as const, result: null, error: "hidden fixture error" };
marketResearchRunSchema.parse(failedRun);
if (marketResearchNullResultMessage(failedRun).heading !== "연구 실행 실패") {
  throw new Error("failed null result must show generic failure");
}
const completedLegacy = {
  ...current,
  status: "completed" as const,
  request: { ...current.request, stage: "legacy" as const },
  result: null,
  stage: "legacy" as const,
  error: null,
};
marketResearchRunSchema.parse(completedLegacy);
if (marketResearchNullResultMessage(completedLegacy).heading !== "결과 확인 불가") {
  throw new Error("completed legacy null result must be unknown");
}

const legacy = structuredClone(current);
const legacyResult = { ...legacy.result };
delete (legacyResult as { provenance?: typeof legacy.result.provenance }).provenance;
delete (legacyResult as { account?: typeof legacy.result.account }).account;
legacyResult.metrics = {} as typeof legacyResult.metrics;
legacyResult.limitations = [];
legacyResult.readiness = { ...legacyResult.readiness, capabilities: [] };
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

const strictUnavailableReadiness = {
  ...current.result.readiness,
  research_grade: "strict" as const,
  simulated: false,
  ready: false,
};
if (!marketResearchReadinessLabel(strictUnavailableReadiness).includes("엄격한 PIT 등급 · 원천 자료 · 자료 확인 불충분")) {
  throw new Error("unavailable strict readiness label is overstated");
}
if (!marketResearchRunLabel({ ...current, result: null }).includes("확인 불가")) {
  throw new Error("missing run result must not claim an outcome");
}

const strictRealReadiness = {
  ...current.result.readiness,
  research_grade: "strict" as const,
  simulated: false,
};
if (!marketResearchReadinessLabel(strictRealReadiness).includes("엄격한 PIT 등급 · 원천 자료")) {
  throw new Error("strict real-source readiness label missing");
}
const strictSyntheticReadiness = { ...strictRealReadiness, simulated: true };
if (!marketResearchReadinessLabel(strictSyntheticReadiness).includes("엄격한 PIT 등급 · 합성 자료")) {
  throw new Error("strict synthetic readiness label missing");
}
const approximateRealReadiness = { ...current.result.readiness, simulated: false };
if (!marketResearchReadinessLabel(approximateRealReadiness).includes("근사 등급 · 원천 자료")) {
  throw new Error("approximate real-source readiness label missing");
}

const partial = {
  ...current,
  status: "insufficient" as const,
  result: {
    ...current.result,
    status: "insufficient" as const,
    completeness: "incomplete" as const,
    readiness: { ...strictRealReadiness, ready: false },
  },
};
marketResearchRunSchema.parse(partial);
if (marketResearchReadinessLabel(partial.result.readiness).includes("준비됨")) {
  throw new Error("partial readiness must not claim verified readiness");
}
if (marketResearchResultStatusLabel(partial.result.status) !== "검증 불충분" || marketResearchCompletenessLabel(partial.result.completeness) !== "불완전") {
  throw new Error("insufficient result state labels missing");
}

const ready = {
  ...current,
  result: {
    ...current.result,
    status: "ready" as const,
    completeness: "complete" as const,
    readiness: { ...current.result.readiness, ready: true, capabilities: [{ name: "bars" as const, status: "ready" as const, detail: "complete fixture bars", missing_ranges: [] }] },
  },
};
marketResearchRunSchema.parse(ready);
if (!marketResearchProvisionalLabel(ready.result).includes("잠정 사유 없음")) {
  throw new Error("ready complete result must not invent provisional failure reason");
}

const failed = {
  ...current,
  status: "failed" as const,
  request: { ...current.request, stage: "legacy" as const },
  result: null,
  stage: "legacy" as const,
  error: "safe fixture error",
};
marketResearchRunSchema.parse(failed);

const emptyLegacy = {
  ...failed,
  status: "completed" as const,
  error: null,
};
marketResearchRunSchema.parse(emptyLegacy);

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

if (marketResearchFixtureScenarios.length !== 12) {
  throw new Error(`expected 12 bounded equity scenarios, got ${marketResearchFixtureScenarios.length}`);
}
const sameValues = (actual: Array<number | null>, expected: Array<number | null>): boolean =>
  actual.length === expected.length && actual.every((value, index) => value === expected[index]);
for (const scenario of marketResearchFixtureScenarios) {
  const parsed = marketResearchRunSchema.parse(scenario.run);
  if (parsed.result === null) throw new Error(`${scenario.id} fixture result is unexpectedly null`);
  const curves = marketResearchEquityCurves(parsed.result);
  if (curves.nav.status !== scenario.expected.navStatus || curves.drawdown.status !== scenario.expected.drawdownStatus) {
    throw new Error(`${scenario.id} curve status mismatch`);
  }
  if (curves.nav.status === "available" && !sameValues(curves.nav.points.map((point) => point.value), scenario.expected.navValues)) {
    throw new Error(`${scenario.id} stored NAV values changed`);
  }
  if (curves.drawdown.status === "available" && !sameValues(curves.drawdown.points.map((point) => point.value), scenario.expected.drawdownValues)) {
    throw new Error(`${scenario.id} stored drawdown values changed`);
  }
  if (marketResearchKrwReturn(parsed.result) !== scenario.expected.krwReturn) {
    throw new Error(`${scenario.id} KRW return contract mismatch`);
  }
  if (scenario.id === "valid-kr" && marketResearchUsdReturn(parsed.result) !== "확인 불가") {
    throw new Error("KR result must not claim a USD return");
  }
  if (scenario.id === "valid-kr" && marketResearchMdd(parsed.result) !== "2.86%") {
    throw new Error("MDD must be derived from the stored drawdown curve");
  }
  if (scenario.id === "missing-us-fx" && marketResearchUsdReturn(parsed.result) !== "확인 불가") {
    throw new Error("missing US FX must fail closed for USD return");
  }
  if (scenario.id === "signed-nav" && marketResearchUsdReturn(parsed.result) !== "-100%") {
    throw new Error("US return must be derived from NAV and session FX");
  }
  if (!parsed.result.limitations.includes("화면 검사용 합성 fixture, 경제 not-evaluated")) {
    throw new Error(`${scenario.id} synthetic fixture limitation missing`);
  }
  if (scenario.id === "single-point" && (curves.nav.markers.length !== 1 || curves.nav.segments.length !== 0)) {
    throw new Error("single point must render as one marker");
  }
  if (scenario.id === "valid-kr" && !curves.krwReturn.points.map((point) => point.value).every((value, index) => value !== null && Math.abs(value - [0, 5, 2][index]) < 1e-9)) {
    throw new Error("KRW return must be derived at every stored NAV");
  }
  if (scenario.id === "numeric-gaps" && (curves.nav.segments.length !== 1 || curves.drawdown.segments.length !== 1)) {
    throw new Error("numeric gaps must break the curve into segments");
  }
  if (scenario.id === "invalid-calendar-date" && !curves.nav.reason?.includes("날짜")) {
    throw new Error("calendar-invalid session must make the curve unknown");
  }
  if (scenario.id === "reverse-date" && !curves.nav.reason?.includes("증가하지 않아")) {
    throw new Error("reverse session order must make the curve unknown");
  }
  if (["missing-us-fx", "legacy-no-metadata"].includes(scenario.id)
    && (curves.nav.status !== "available" || curves.drawdown.status !== "available" || marketResearchKrwReturn(parsed.result) !== "확인 불가")) {
    throw new Error(`${scenario.id} must preserve stored curves while hiding return`);
  }
  if (scenario.id === "status-error-preserved"
    && (parsed.status !== "insufficient" || parsed.result.status !== "insufficient" || parsed.result.completeness !== "incomplete" || parsed.error !== "safe fixture error"
      || parsed.request.start_date !== "2026-01-00" || parsed.request.end_date !== "2026-02-30"
      || curves.nav.status !== "unavailable" || curves.drawdown.status !== "unavailable" || marketResearchKrwReturn(parsed.result) !== "확인 불가")) {
    throw new Error("status, completeness, and safe error were not preserved");
  }
}

console.log("grade/source labels, null-result states, strict/approximate legacy checks, and bounded equity curves: PASS");
