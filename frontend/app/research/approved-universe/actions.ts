"use server";

import { redirect } from "next/navigation";
import { researchBackendUrl } from "@/lib/research";
import { approvedUniverseSchema, type ApprovedInstrument } from "./contract";

export async function saveApprovedUniverse(formData: FormData): Promise<void> {
  const raw = formData.get("instruments");
  const revision = Number(formData.get("revision"));
  if (typeof raw !== "string" || !Number.isSafeInteger(revision) || revision < 0) {
    redirect("/research/approved-universe?state=invalid");
  }
  const lines = raw.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  if (lines.length === 0 && formData.get("confirm_clear") !== "on") {
    redirect("/research/approved-universe?state=confirm-clear");
  }
  if (lines.length > 100) redirect("/research/approved-universe?state=invalid");
  const instruments: ApprovedInstrument[] = [];
  for (const line of lines) {
    const parts = line.split(",").map((part) => part.trim().toUpperCase());
    if (parts.length === 2 && parts[0] === "KR") {
      instruments.push({ market: "KR", exchange: "KRX", symbol: parts[1] });
    } else if (parts.length === 3 && parts[0] === "US") {
      const exchange = parts[1];
      if (exchange !== "NAS" && exchange !== "NYS" && exchange !== "AMS") {
        redirect("/research/approved-universe?state=invalid");
      }
      instruments.push({ market: "US", exchange, symbol: parts[2] });
    } else {
      redirect("/research/approved-universe?state=invalid");
    }
  }
  const parsed = approvedUniverseSchema.safeParse({ revision, updated_at: null, instruments });
  if (!parsed.success || new Set(instruments.map((item) => `${item.market}:${item.exchange}:${item.symbol}`)).size !== instruments.length) {
    redirect("/research/approved-universe?state=invalid");
  }
  let response: Response;
  try {
    response = await fetch(`${researchBackendUrl()}/api/research/approved-universe`, {
      method: "PUT",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ revision, instruments }),
      cache: "no-store",
      signal: AbortSignal.timeout(15000),
    });
  } catch {
    redirect("/research/approved-universe?state=error");
  }
  if (response.status === 409) redirect("/research/approved-universe?state=stale");
  if (response.status === 422) redirect("/research/approved-universe?state=invalid");
  if (!response.ok) redirect("/research/approved-universe?state=error");
  const saved = approvedUniverseSchema.safeParse(await response.json());
  if (!saved.success) redirect("/research/approved-universe?state=error");
  redirect(`/research/approved-universe?state=saved&revision=${saved.data.revision}`);
}
