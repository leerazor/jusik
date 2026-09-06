import { z } from "zod";

const decimal = z.string().regex(/^-?\d+(\.\d+)?$/);
const currency = z.enum(["KRW", "USD", "HKD", "CNY", "JPY", "VND"]);
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
});
const total = z.object({
  currency,
  cost: decimal,
  value: decimal,
  profit: decimal,
  return_pct: decimal.nullable(),
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
});
export const portfolioSchema = z.object({
  source: z.literal("live-registered-accounts-snapshot"),
  fetched_at: z.iso.datetime({ offset: true }),
  accounts: z.array(
    z.object({
      id: z.string(),
      label: z.string(),
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
});
export type Portfolio = z.infer<typeof portfolioSchema>;
export type Account = Portfolio["accounts"][number];
export const marketNames: Record<string, string> = {
  KRX: "국내",
  NASD: "미국",
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
