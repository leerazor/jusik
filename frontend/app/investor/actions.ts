"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { z } from "zod";
import { backendUrl, thesisSchema } from "@/lib/investor";

const formSchema = z.object({
  id: z.string().regex(/^[a-f0-9]{32}$/).nullable(), market: z.enum(["KR", "US"]), exchange: z.string().regex(/^[A-Za-z0-9.-]{1,12}$/), symbol: z.string().regex(/^[A-Za-z0-9.-]{1,16}$/), name: z.string().min(1).max(120), currency: z.enum(["KRW", "USD"]), instrument_type: z.enum(["stock", "etf", "unknown"]),
  state: z.enum(["watch", "holding", "closed"]), entry_kind: z.enum(["value", "trend"]), health: z.enum(["intact", "broken", "unknown"]), why: z.string().min(1).max(2000), invalidation_criteria: z.string().min(1).max(1000), source_references: z.string().max(2000), next_review: z.iso.date(), risk_price: z.string().regex(/^\d+(\.\d+)?$/).nullable(), normalized_eps: z.string().regex(/^\d+(\.\d+)?$/).nullable(), eps_period: z.string().max(32).nullable(), target_pe_lower: z.string().regex(/^\d+(\.\d+)?$/).nullable(), target_pe_upper: z.string().regex(/^\d+(\.\d+)?$/).nullable(), margin_of_safety: z.string().regex(/^0(\.\d+)?$|^1(\.0+)?$/).nullable(), rationale: z.string().max(1000).nullable(), expected_revision: z.coerce.number().int().nonnegative(),
});

function nullable(form: FormData, key: string): string | null { const value = form.get(key); return typeof value === "string" && value.trim() ? value.trim() : null; }
function errorRedirect(form: FormData, message: string): never {
  const market = form.get("market");
  const symbol = form.get("symbol");
  const exchange = form.get("exchange");
  if (typeof market === "string" && /^(KR|US)$/.test(market) && typeof symbol === "string" && /^[A-Za-z0-9.-]{1,16}$/.test(symbol)) {
    const query = typeof exchange === "string" && /^[A-Za-z0-9.-]{1,12}$/.test(exchange) ? `?exchange=${encodeURIComponent(exchange)}&error=${encodeURIComponent(message)}` : `?error=${encodeURIComponent(message)}`;
    redirect(`/investor/${market}/${symbol}${query}`);
  }
  redirect(`/investor?error=${encodeURIComponent(message)}`);
}

export async function saveThesis(form: FormData): Promise<void> {
  const parsed = formSchema.safeParse({ id: nullable(form, "id"), market: form.get("market"), exchange: form.get("exchange"), symbol: form.get("symbol"), name: form.get("name"), currency: form.get("currency"), instrument_type: form.get("instrument_type"), state: form.get("state"), entry_kind: form.get("entry_kind"), health: form.get("health"), why: form.get("why"), invalidation_criteria: form.get("invalidation_criteria"), source_references: form.get("source_references") ?? "", next_review: form.get("next_review"), risk_price: nullable(form, "risk_price"), normalized_eps: nullable(form, "normalized_eps"), eps_period: nullable(form, "eps_period"), target_pe_lower: nullable(form, "target_pe_lower"), target_pe_upper: nullable(form, "target_pe_upper"), margin_of_safety: nullable(form, "margin_of_safety"), rationale: nullable(form, "rationale"), expected_revision: form.get("expected_revision") ?? "0" });
  if (!parsed.success) errorRedirect(form, "입력값을 확인하세요");
  const value = parsed.data;
  const payload = { instrument: { market: value.market, exchange: value.exchange, symbol: value.symbol, name: value.name, currency: value.currency, instrument_type: value.instrument_type }, state: value.state, entry_kind: value.entry_kind, health: value.health, why: value.why, invalidation_criteria: value.invalidation_criteria, source_references: value.source_references.split("\n").map((item) => item.trim()).filter(Boolean), next_review: value.next_review, risk_price: value.risk_price, expected_revision: value.expected_revision, valuation: value.normalized_eps || value.target_pe_lower || value.target_pe_upper || value.margin_of_safety || value.rationale ? { normalized_eps: value.normalized_eps, eps_period: value.eps_period, target_pe_lower: value.target_pe_lower, target_pe_upper: value.target_pe_upper, margin_of_safety: value.margin_of_safety, rationale: value.rationale } : null };
  let response: Response;
  try {
    response = await fetch(`${backendUrl()}/api/investor/theses${value.id ? `/${value.id}` : ""}`, { method: "PUT", headers: { "content-type": "application/json" }, body: JSON.stringify(payload), cache: "no-store" });
  } catch {
    redirect(`/investor/${value.market}/${value.symbol}?exchange=${encodeURIComponent(value.exchange)}&error=연결 실패로 저장하지 못했습니다`);
  }
  if (!response!.ok) redirect(`/investor/${value.market}/${value.symbol}?exchange=${encodeURIComponent(value.exchange)}&error=${response!.status === 409 ? "동시에 수정되어 다시 불러왔습니다" : "저장에 실패했습니다"}`);
  thesisSchema.parse(await response!.json());
  revalidatePath("/investor");
  revalidatePath(`/investor/${value.market}/${value.symbol}`);
  redirect(`/investor/${value.market}/${value.symbol}?exchange=${encodeURIComponent(value.exchange)}&saved=1`);
}
