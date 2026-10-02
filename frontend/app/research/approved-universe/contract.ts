import { z } from "zod";

export const approvedInstrumentSchema = z.object({
  market: z.enum(["KR", "US"]),
  exchange: z.enum(["KRX", "NAS", "NYS", "AMS"]),
  symbol: z.string().min(1).max(15),
}).superRefine((item, context) => {
  const valid = item.market === "KR"
    ? item.exchange === "KRX" && /^[0-9A-Z]{6}$/.test(item.symbol)
    : item.exchange !== "KRX" && /^[A-Z][A-Z0-9.-]{0,14}$/.test(item.symbol);
  if (!valid) context.addIssue({ code: "custom", message: "시장·거래소·종목 코드 형식이 맞지 않습니다." });
});

export const approvedUniverseSchema = z.object({
  revision: z.number().int().nonnegative(),
  updated_at: z.string().nullable(),
  instruments: z.array(approvedInstrumentSchema).max(100),
});

export type ApprovedInstrument = z.infer<typeof approvedInstrumentSchema>;
