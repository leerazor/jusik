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
export const portfolioSchema = z.object({
  source: z.literal("live-account-snapshot"),
  fetched_at: z.iso.datetime({ offset: true }),
  markets: z.array(
    z.object({
      market: z.string(),
      status: z.enum(["ok", "error"]),
      holdings: z.array(holding),
      error: z.string().nullable(),
      fetched_at: z.iso.datetime({ offset: true }).nullable(),
    }),
  ),
  totals: z.array(
    z.object({
      currency,
      cost: decimal,
      value: decimal,
      profit: decimal,
      return_pct: decimal.nullable(),
    }),
  ),
});
export type Portfolio = z.infer<typeof portfolioSchema>;
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
