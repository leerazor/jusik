import { z } from "zod";

const decimal = z.string().regex(/^-?\d+(\.\d+)?$/);
const currency = z.enum(["KRW", "USD", "HKD", "CNY", "JPY", "VND"]);
const fundamentals = z.object({
  status: z.enum(["ok", "unavailable", "error"]),
  per: decimal.nullable(),
  pbr: decimal.nullable(),
  eps: decimal.nullable(),
  bps: decimal.nullable(),
  instrument_type: z.string().nullable(),
  source: z.string().nullable(),
  source_url: z.string().url().nullable(),
  fetched_at: z.iso.datetime({ offset: true }).nullable(),
  error: z.string().nullable(),
});
const advice = z.object({
  signal: z.enum(["buy_review", "hold", "sell_review", "insufficient"]),
  label: z.string(),
  reasons: z.array(z.string()),
  rule_version: z.string(),
});
const holding = z.object({
  market: z.string(),
  symbol: z.string(),
  name: z.string(),
  currency,
  quantity: decimal,
  average_price: decimal,
  current_price: decimal,
  cost: decimal,
  value: decimal,
  profit: decimal,
  return_pct: decimal.nullable(),
  fx_rate: decimal.nullable(),
  fx_source: z.string().nullable(),
  fx_as_of: z.iso.date().nullable(),
  average_price_krw: decimal.nullable(),
  current_price_krw: decimal.nullable(),
  cost_krw: decimal.nullable(),
  value_krw: decimal.nullable(),
  profit_krw: decimal.nullable(),
  fundamentals,
  advice,
  price_fetched_at: z.iso.datetime({ offset: true }).nullable(),
});
const total = z.object({
  currency,
  cost: decimal,
  value: decimal,
  profit: decimal,
  return_pct: decimal.nullable(),
  cost_krw: decimal.nullable(),
  value_krw: decimal.nullable(),
  profit_krw: decimal.nullable(),
});
const market = z.object({
  market: z.string(),
  status: z.enum(["ok", "error"]),
  holdings: z.array(holding),
  error: z.string().nullable(),
  fetched_at: z.iso.datetime({ offset: true }).nullable(),
});
const assetSummary = z.object({
  currency: z.literal("KRW"),
  net_asset: decimal.nullable(),
  total_evaluation: decimal.nullable(),
  cash: decimal.nullable(),
  profit_loss: decimal.nullable(),
  overseas_evaluation: decimal.nullable(),
  estimated_deposit_assets: decimal.nullable(),
  debt: decimal.nullable(),
  scope: z.enum(["account", "domestic", "estimated_account"]),
  basis: z.string(),
  exchange_rates: z.record(z.string(), decimal),
  asset_source: z.string(),
});
export const portfolioSchema = z.object({
  source: z.literal("live-registered-accounts-snapshot"),
  fetched_at: z.iso.datetime({ offset: true }),
  accounts: z.array(
    z.object({
      id: z.string(),
      label: z.string(),
      broker: z.enum(["kis", "kiwoom"]),
      status: z.enum(["ok", "partial", "error"]),
      asset_summary: z.object({
        status: z.enum(["ok", "error"]),
        summary: assetSummary.nullable(),
        error: z.string().nullable(),
        fetched_at: z.iso.datetime({ offset: true }).nullable(),
      }),
      markets: z.array(market),
      totals: z.array(total),
      errors: z.array(z.string()),
      fetched_at: z.iso.datetime({ offset: true }).nullable(),
    }),
  ),
  aggregate: z.object({
    currency: z.literal("KRW"),
    net_asset: decimal.nullable(),
    completeness: z.enum(["complete", "partial", "unavailable"]),
    included_accounts: z.number().int().nonnegative(),
    registered_accounts: z.number().int().positive(),
  }),
  totals: z.array(total),
  exchange_rates: z.array(
    z.object({
      currency,
      krw_per_unit: decimal.nullable(),
      status: z.enum(["ok", "error"]),
      source: z.string(),
      source_url: z.string().url(),
      as_of: z.iso.date().nullable(),
      fetched_at: z.iso.datetime({ offset: true }),
      stale: z.boolean(),
      error: z.string().nullable(),
    }),
  ),
  alerts: z.array(
    z.object({
      id: z.number().int(),
      account_id: z.string(),
      market: z.string(),
      symbol: z.string(),
      name: z.string(),
      signal: z.enum(["buy_review", "sell_review"]),
      title: z.string(),
      message: z.string(),
      created_at: z.iso.datetime({ offset: true }),
      delivery: z.enum([
        "in_app",
        "telegram_sent",
        "telegram_failed",
        "telegram_unknown",
      ]),
    }),
  ),
  intelligence: z.object({
    korea_base_rate: decimal.nullable(),
    korea_rate_as_of: z.iso.date().nullable(),
    us_target_rate: z.string().nullable(),
    us_rate_as_of: z.iso.date().nullable(),
    news: z.array(
      z.object({
        id: z.string(),
        category: z.enum([
          "korea_rate",
          "us_rate",
          "geopolitics",
          "truth_social",
          "truth_social_post",
        ]),
        title: z.string(),
        url: z.string().url(),
        source: z.string(),
        published_at: z.iso.datetime({ offset: true }).nullable(),
        assessment: z.string(),
        original_url: z.string().url().nullable().default(null),
        excerpt: z.string().nullable().default(null),
      }),
    ),
    sources: z.array(
      z.object({
        id: z.string(),
        label: z.string(),
        status: z.enum(["ok", "error"]),
        source_url: z.string().url(),
        fetched_at: z.iso.datetime({ offset: true }).nullable(),
        stale: z.boolean(),
        error: z.string().nullable(),
      }),
    ),
    fetched_at: z.iso.datetime({ offset: true }).nullable(),
  }),
  monitor: z.object({
    enabled: z.boolean(),
    interval_seconds: z.number().int(),
    telegram_configured: z.boolean(),
    last_checked_at: z.iso.datetime({ offset: true }).nullable(),
    last_success_at: z.iso.datetime({ offset: true }).nullable(),
    next_check_at: z.iso.datetime({ offset: true }).nullable(),
    consecutive_failures: z.number().int().nonnegative(),
    error: z.string().nullable(),
  }),
  holding_conversion_completeness: z.enum(["complete", "partial", "unavailable"]),
});
export type Portfolio = z.infer<typeof portfolioSchema>;
export type Account = Portfolio["accounts"][number];
export type Holding = z.infer<typeof holding>;
export const marketNames: Record<string, string> = {
  KRX: "국내",
  NASD: "미국",
  US: "미국",
  NYSE: "뉴욕",
  AMEX: "아멕스",
  SEHK: "홍콩",
  SHAA: "상하이",
  SZAA: "선전",
  TKSE: "일본",
  HASE: "하노이",
  VNSE: "호치민",
};

export function amount(value: string, digits = 2): string {
  // Keep decimal strings exact; truncate only display precision without float conversion.
  const [whole, fraction = ""] = value.split(".");
  const grouped = BigInt(whole).toLocaleString("ko-KR");
  const sign = value.startsWith("-0.") ? "-" : "";
  const tail = fraction.slice(0, digits).replace(/0+$/, "");
  return `${sign}${grouped}${tail ? `.${tail}` : ""}`;
}
export function tone(value: string): string {
  return /^-/.test(value) ? "loss" : /[1-9]/.test(value) ? "gain" : "";
}
