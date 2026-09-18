import { z } from "zod";
import { researchBackendUrl } from "./research";

const timestamp = z.iso.datetime({ offset: true });
const date = z.iso.date();
const decimalPattern = /^-?(?:\d+)(?:\.\d+)?(?:[eE][+-]?\d+)?$/;
const decimal = z.string().regex(decimalPattern).refine(
  (value) => Number.isFinite(Number(value)),
  "decimal must be finite",
);
const hash = z.string().regex(/^[a-f0-9]{64}$/);
const safeIdentifier = z.string().regex(/^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$/);

const count = z.number().int().nonnegative();

const runnerTaskSchema = z.object({
  task_id: safeIdentifier,
  area: z.string().min(1),
  title: z.string().min(1),
  status: z.string().min(1),
  updated_at: timestamp,
  next_allowed_at: timestamp.nullable(),
  depends_on: safeIdentifier.nullable(),
}).strict();

const metricsSchema = z.object({
  label: z.string().min(1),
  net_return_pct: decimal.refine((value) => Number(value) >= -100, "return must be >= -100"),
  cash_pct: decimal.refine((value) => Number(value) >= 0 && Number(value) <= 100, "cash must be 0..100"),
  max_drawdown_pct: decimal.refine((value) => Number(value) >= 0 && Number(value) <= 100, "drawdown must be 0..100"),
  max_leverage_pct: decimal.refine((value) => Number(value) >= 0 && Number(value) <= 100, "leverage must be 0..100"),
  annual_turnover_pct: decimal.refine((value) => Number(value) >= 0, "turnover must be non-negative"),
  total_cost_krw: decimal.refine((value) => Number(value) >= 0, "cost must be non-negative"),
  trade_days: z.number().int().nonnegative(),
}).strict();

const comparisonSchema = z.object({
  id: safeIdentifier,
  period_start: date,
  period_end: date,
  cost_multiplier: z.number().int().positive(),
  drawdown_basis: z.enum(["all_observer_nav", "close_nav"]),
  cash_basis: z.literal("utc_day_last_nav"),
  cash_statistic: z.enum(["mean", "median"]),
  baseline: metricsSchema,
  candidate: metricsSchema,
}).strict().superRefine((comparison, context) => {
  if (comparison.period_start > comparison.period_end) {
    context.addIssue({ code: "custom", path: ["period_end"], message: "period_end must not precede period_start" });
  }
});

const studySchema = z.object({
  id: safeIdentifier,
  title: z.string().min(1),
  published_at: timestamp,
  cohort_id: safeIdentifier,
  universe_symbols: z.array(z.string().min(1)),
  source_sha256: hash,
  result_sha256: hash,
  report_artifact_sha256: hash,
  price_only: z.literal(true),
  dividends_included: z.literal(false),
  taxes_included: z.literal(false),
  retrospective_reused_data: z.literal(true),
  point_in_time_verified: z.literal(false),
  comparisons: z.array(comparisonSchema),
}).strict();

const runnerSchema = z.object({
  availability: z.enum(["available", "unavailable", "invalid"]),
  recorded_at: timestamp.nullable(),
  paused: z.boolean().nullable(),
  service: z.enum(["active", "inactive", "unknown"]),
  timer: z.enum(["active", "inactive", "unknown"]),
  policy: z.object({
    daily_launch_limit: z.number().int().nonnegative().nullable(),
    launches_today: z.number().int().nonnegative(),
    task_timeout_seconds: z.number().int().positive(),
    cooldown_seconds: z.number().int().nonnegative(),
    planning_enabled: z.boolean(),
    scheduled_end_at: z.null(),
  }).strict().nullable(),
  counts: z.object({
    queued: count,
    running: count,
    completed: count,
    blocked: count,
    failed: count,
    interrupted: count,
    other: count,
  }).strict().nullable(),
  current: z.object({
    task_id: safeIdentifier,
    area: z.string().min(1),
    title: z.string().min(1),
    started_at: timestamp,
  }).strict().nullable(),
  tasks: z.array(runnerTaskSchema),
  truncated: z.boolean(),
}).strict();

const researchSchema = z.object({
  availability: z.enum(["available", "unavailable", "invalid"]),
  published_at: timestamp.nullable(),
  featured_comparison_id: safeIdentifier.nullable(),
  studies: z.array(studySchema),
}).strict();

export const researchProgressSchema = z.object({
  schema_version: z.literal(1),
  observed_at: timestamp,
  runner: runnerSchema,
  research: researchSchema,
}).strict().superRefine((progress, context) => {
  const comparisonIds = progress.research.studies.flatMap((study) => study.comparisons.map((comparison) => comparison.id));
  if (new Set(comparisonIds).size !== comparisonIds.length) {
    context.addIssue({ code: "custom", path: ["research", "studies"], message: "comparison ids must be globally unique" });
  }
  const featuredId = progress.research.featured_comparison_id;
  if (featuredId !== null && !comparisonIds.includes(featuredId)) {
    context.addIssue({ code: "custom", path: ["research", "featured_comparison_id"], message: "featured comparison does not exist" });
  }
});

export type ResearchProgress = z.infer<typeof researchProgressSchema>;
export type RunnerTask = z.infer<typeof runnerTaskSchema>;
export type Metrics = z.infer<typeof metricsSchema>;
export type Comparison = z.infer<typeof comparisonSchema>;
export type Study = z.infer<typeof studySchema>;

type ExpandedResearchDecimal = { negative: boolean; digits: string; decimalPosition: number };
function expandResearchDecimal(value: string): ExpandedResearchDecimal | null {
  const match = /^(-?)(\d+)(?:\.(\d+))?(?:[eE]([+-]?\d+))?$/.exec(value);
  if (!match) return null;
  const [, sign, whole, fraction = "", exponentText = "0"] = match;
  const rawDigits = `${whole}${fraction}`;
  if (!/[1-9]/.test(rawDigits)) return { negative: false, digits: "0", decimalPosition: 1 };
  const exponent = Number(exponentText);
  if (!Number.isSafeInteger(exponent)) return null;
  const digits = rawDigits.replace(/^0+(?=\d)/, "");
  const leadingZeros = rawDigits.length - rawDigits.replace(/^0+/, "").length;
  return { negative: sign === "-" && /[1-9]/.test(digits), digits, decimalPosition: whole.length + exponent - leadingZeros };
}

export function compareDecimal(left: string, right: string): number | null {
  const a = expandResearchDecimal(left);
  const b = expandResearchDecimal(right);
  if (!a || !b) return null;
  if (a.digits === "0") return b.digits === "0" ? 0 : b.negative ? 1 : -1;
  if (b.digits === "0") return a.negative ? -1 : 1;
  if (a.negative !== b.negative) return a.negative ? -1 : 1;
  const sign = a.negative ? -1 : 1;
  if (a.decimalPosition !== b.decimalPosition) return sign * (a.decimalPosition > b.decimalPosition ? 1 : -1);
  const length = Math.max(a.digits.length, b.digits.length);
  const aDigits = a.digits.padEnd(length, "0");
  const bDigits = b.digits.padEnd(length, "0");
  if (aDigits === bDigits) return 0;
  return sign * (aDigits > bDigits ? 1 : -1);
}

export async function getResearchProgress(): Promise<ResearchProgress> {
  const response = await fetch(`${researchBackendUrl()}/api/research/progress`, {
    cache: "no-store",
    signal: AbortSignal.timeout(10000),
    headers: { accept: "application/json" },
  });
  if (!response.ok) throw new Error("research progress unavailable");
  return researchProgressSchema.parse(await response.json());
}
