import { z } from "zod";
import { researchBackendUrl } from "@/lib/research";

type CanonicalDecimal = { coefficient: bigint; exponent: bigint };

const decimalPattern = /^([+-]?)(?:(\d+)(?:\.(\d*))?|\.(\d+))(?:[eE]([+-]?\d+))?$/;

function canonicalDecimal(value: string): CanonicalDecimal | null {
  const match = decimalPattern.exec(value);
  if (!match) return null;
  const fraction = match[3] ?? match[4] ?? "";
  let coefficient = BigInt(`${match[2] ?? ""}${fraction}`);
  if (match[1] === "-") coefficient = -coefficient;
  if (coefficient === 0n) return { coefficient: 0n, exponent: 0n };
  let exponent = BigInt(match[5] ?? "0") - BigInt(fraction.length);
  while (coefficient % 10n === 0n) {
    coefficient /= 10n;
    exponent += 1n;
  }
  return { coefficient, exponent };
}

const positiveDecimalStringSchema = z.string().refine((value) => {
  const parsed = canonicalDecimal(value);
  return parsed !== null && parsed.coefficient > 0n;
}, "must be a positive finite Decimal string");

const decimalStringsEqual = (left: string, right: string): boolean => {
  const leftCanonical = canonicalDecimal(left);
  const rightCanonical = canonicalDecimal(right);
  return leftCanonical !== null
    && rightCanonical !== null
    && leftCanonical.coefficient === rightCanonical.coefficient
    && leftCanonical.exponent === rightCanonical.exponent;
};

const capabilitySchema = z.object({
  name: z.enum(["credentials", "entitlement", "calendar", "membership", "bars", "actions", "fx", "policy"]),
  status: z.enum(["ready", "missing", "unsupported", "partial"]),
  detail: z.string(),
  missing_ranges: z.array(z.string()),
});

const researchGradeSchema = z.enum(["strict", "approximate"]);
const sourceNameSchema = z.enum(["fixture", "krx", "massive", "yahoo", "alpha_vantage", "fred", "approximate_file"]);
const capturedAtSchema = z.iso.datetime({ offset: true });

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
  normalization_version: z.string().min(1).max(40).nullable(),
  captured_at: capturedAtSchema.nullable(),
});

export const marketResearchAccountSchema = z.object({
  account_scope: z.literal("market_specific_independent_simulated"),
  reporting_currency: z.literal("KRW"),
  native_currency: z.enum(["KRW", "USD"]),
  initial_cash_krw: positiveDecimalStringSchema,
  fx_krw_per_usd: positiveDecimalStringSchema.nullable(),
  initial_cash_conversion: z.enum(["identity", "initial_krw_to_usd"]),
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
  account: marketResearchAccountSchema.nullable().optional(),
}).superRefine((result, context) => {
  if (result.account === undefined || result.account === null) return;
  const expectedNativeCurrency = result.market === "KR" ? "KRW" : "USD";
  if (result.account.native_currency !== expectedNativeCurrency) {
    context.addIssue({
      code: "custom",
      path: ["account", "native_currency"],
      message: "account native currency does not match market",
    });
  }
  if (!decimalStringsEqual(result.account.initial_cash_krw, result.request.initial_cash_krw)) {
    context.addIssue({
      code: "custom",
      path: ["account", "initial_cash_krw"],
      message: "account initial cash does not match request",
    });
  }
  const expectedConversion = result.market === "KR" ? "identity" : "initial_krw_to_usd";
  if (result.account.initial_cash_conversion !== expectedConversion) {
    context.addIssue({
      code: "custom",
      path: ["account", "initial_cash_conversion"],
      message: "account cash conversion does not match market",
    });
  }
  if (result.market === "KR" && result.account.fx_krw_per_usd !== null && !decimalStringsEqual(result.account.fx_krw_per_usd, "1")) {
    context.addIssue({
      code: "custom",
      path: ["account", "fx_krw_per_usd"],
      message: "KR account FX quote must be identity",
    });
  }
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
export type MarketCapability = MarketReadiness["capabilities"][number];
export type MarketResearchProvenance = z.infer<typeof marketResearchProvenanceSchema>;
export type MarketResearchAccount = z.infer<typeof marketResearchAccountSchema>;
export type MarketResearchRun = z.infer<typeof marketResearchRunSchema>;
export type MarketResearchResult = NonNullable<MarketResearchRun["result"]>;

type MarketResearchResultStatus = MarketResearchResult["status"];
type MarketResearchCompleteness = MarketResearchResult["completeness"];

export function marketResearchGradeLabel(grade: "strict" | "approximate"): string {
  return grade === "strict" ? "엄격한 PIT 등급" : "근사 등급";
}

export function marketResearchSourceLabel(simulated: boolean | undefined): string {
  if (simulated === true) return "합성 자료";
  if (simulated === false) return "원천 자료";
  return "자료 성격 확인 불가";
}

export function marketResearchResultStatusLabel(status: MarketResearchResultStatus): string {
  return {
    ready: "계산 준비됨",
    insufficient: "검증 불충분",
    approximate: "근사 결과",
  }[status];
}

export function marketResearchCompletenessLabel(completeness: MarketResearchCompleteness): string {
  return {
    complete: "완전",
    incomplete: "불완전",
    approximate: "근사",
  }[completeness];
}

export function marketResearchCapabilityStatusLabel(status: MarketCapability["status"]): string {
  return {
    ready: "준비됨",
    missing: "없음",
    unsupported: "지원하지 않음",
    partial: "부분 확인",
  }[status];
}

export function marketResearchProvisionalLabel(result: Pick<MarketResearchResult, "status" | "completeness" | "readiness">): string {
  const reasons: string[] = [];
  if (result.status !== "ready") reasons.push(`상태 ${marketResearchResultStatusLabel(result.status)}`);
  if (result.completeness !== "complete") reasons.push(`완전성 ${marketResearchCompletenessLabel(result.completeness)}`);
  if (!result.readiness.ready) reasons.push("자료 준비 불충분");
  if (result.readiness.capabilities.length === 0) reasons.push("capability 확인 없음");
  for (const capability of result.readiness.capabilities) {
    if (capability.status !== "ready") reasons.push(`${capability.name} ${marketResearchCapabilityStatusLabel(capability.status)}`);
  }
  return reasons.length > 0
    ? `잠정 상태 · ${reasons.join(" · ")} · 자료 확정성·최종 승격 가능성은 판단하지 않음`
    : "잠정 사유 없음 · 자료 확정성·최종 승격 가능성은 판단하지 않음";
}

export function marketResearchReadinessLabel(item: MarketReadiness): string {
  const state = item.ready ? "준비됨" : "자료 확인 불충분";
  return `${marketResearchGradeLabel(item.research_grade)} · ${marketResearchSourceLabel(item.simulated)} · ${state}`;
}

export function marketResearchRunLabel(run: MarketResearchRun): string {
  if (run.result === null) return "자료 성격·실행 결과 확인 불가";
  return `${marketResearchGradeLabel(run.request.research_grade)} · ${marketResearchSourceLabel(run.result.readiness.simulated)} · 시뮬레이션 연구 실행 · PAPER 별도`;
}

export function marketResearchNullResultMessage(run: MarketResearchRun): {
  heading: string;
  detail: string;
} {
  if (run.status === "queued") {
    return {
      heading: "실행 대기 중",
      detail: "시장 연구가 대기열에 등록되었으며 아직 실행되지 않았습니다.",
    };
  }
  if (run.status === "running") {
    return {
      heading: "연구 실행 중",
      detail: "시장 연구가 실행 중이며 결과를 아직 만들지 않았습니다.",
    };
  }
  if (run.status === "failed") {
    return {
      heading: "연구 실행 실패",
      detail: "연구 결과를 생성하지 못했습니다. 자세한 오류는 표시하지 않습니다.",
    };
  }
  return {
    heading: "결과 확인 불가",
    detail: "저장된 실행에 결과가 없어 상태를 확인할 수 없습니다.",
  };
}

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

function finiteNumber(value: string | undefined): number | null {
  if (value === undefined || value.trim() === "") return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function nonNegativeInteger(value: string | undefined): number | null {
  if (value === undefined || !/^\+?\d+$/.test(value.trim())) return null;
  const number = Number(value);
  return Number.isSafeInteger(number) && number >= 0 ? number : null;
}

export function marketAmount(value: string | undefined | null): string {
  const number = finiteNumber(value ?? undefined);
  return number === null
    ? "확인 불가"
    : new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 2 }).format(number);
}

export function marketResearchMetric(value: string | undefined, suffix = ""): string {
  const amount = marketAmount(value);
  return amount === "확인 불가" ? amount : `${amount}${suffix}`;
}

export function marketResearchCounter(value: string | undefined, suffix = ""): string {
  const number = nonNegativeInteger(value);
  return number === null ? "확인 불가" : `${marketAmount(String(number))}${suffix}`;
}

export function marketResearchCoverageLabel(usable: string | undefined, expected: string | undefined): string {
  const usableNumber = nonNegativeInteger(usable);
  const expectedNumber = nonNegativeInteger(expected);
  if (usableNumber === null || expectedNumber === null || expectedNumber <= 0) return "확인 불가";
  const percentage = (usableNumber / expectedNumber) * 100;
  return `${marketAmount(String(usableNumber))} / ${marketAmount(String(expectedNumber))} (${marketAmount(String(percentage))}%)`;
}
