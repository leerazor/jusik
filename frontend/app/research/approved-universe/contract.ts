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
export type ApprovedUniverse = z.infer<typeof approvedUniverseSchema>;

const optionalDate = z.iso.date().nullable();
const optionalTime = z.iso.datetime({ offset: true }).nullable();
export const approvedReadinessSchema = z.object({
  revision: z.number().int().nonnegative(),
  updated_at: optionalTime,
  generated_at: z.iso.datetime({ offset: true }),
  comparison_status: z.literal("not_performed"),
  price_source_status: z.enum(["available", "unavailable"]),
  dividend_source_status: z.enum(["available", "unavailable"]),
  fx: z.object({
    status: z.enum(["available", "unavailable"]),
    observed_date_count: z.number().int().nonnegative().nullable(),
    first_observed_on: optionalDate,
    last_observed_on: optionalDate,
  }),
  instruments: z.array(z.object({
    instrument: approvedInstrumentSchema,
    price: z.object({
      status: z.enum(["missing", "success", "stale", "error", "unavailable"]),
      identity_status: z.literal("not_checked"),
      requested_start: optionalDate,
      requested_end: optionalDate,
      actual_start: optionalDate,
      actual_end: optionalDate,
      evaluation_start: optionalDate,
      warmup_bars: z.number().int().nonnegative().nullable(),
      evaluation_bars: z.number().int().nonnegative().nullable(),
      captured_at: optionalTime,
      history_warning: z.boolean().nullable(),
    }),
    dividend: z.object({
      status: z.enum(["available", "unavailable"]),
      identity_status: z.literal("not_checked"),
      observed_event_count: z.number().int().nonnegative().nullable(),
      reviewed_current_event_count: z.number().int().nonnegative().nullable(),
      matched_current_event_count: z.number().int().nonnegative().nullable(),
      partial_current_event_count: z.number().int().nonnegative().nullable(),
      mismatched_current_event_count: z.number().int().nonnegative().nullable(),
    }),
  })).max(100),
});
export type ApprovedReadiness = z.infer<typeof approvedReadinessSchema>;
