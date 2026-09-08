"use server";

import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";
import { researchBackendUrl, researchRunSchema } from "@/lib/research";

function value(formData: FormData, key: string): string {
  const entry = formData.get(key);
  if (typeof entry !== "string") throw new Error(`${key} 값이 없습니다.`);
  return entry.trim();
}

export async function createResearchRun(formData: FormData): Promise<void> {
  let events: unknown[] = [];
  const eventJson = value(formData, "events");
  try {
    if (eventJson) {
      const parsed: unknown = JSON.parse(eventJson);
      if (!Array.isArray(parsed)) throw new Error();
      events = parsed;
    }
  } catch {
    redirect("/research?error=event-json");
  }
  const optional = value(formData, "symbols")
    .split(",")
    .map((symbol) => symbol.trim())
    .filter(Boolean);
  const body = {
    symbols: optional,
    start_date: value(formData, "start_date"),
    end_date: value(formData, "end_date"),
    initial_cash: value(formData, "initial_cash"),
    fee_rate: value(formData, "fee_rate"),
    slippage_rate: value(formData, "slippage_rate"),
    sell_tax_rate: value(formData, "sell_tax_rate"),
    events,
  };
  let id: string;
  try {
    const response = await fetch(`${researchBackendUrl()}/api/research/runs`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
      signal: AbortSignal.timeout(15000),
    });
    if (!response.ok) throw new Error();
    id = researchRunSchema.parse(await response.json()).id;
  } catch {
    redirect("/research?error=create-failed");
  }
  redirect(`/research/${id}`);
}

export async function replayResearchRun(formData: FormData): Promise<void> {
  const id = value(formData, "id");
  try {
    const response = await fetch(
      `${researchBackendUrl()}/api/research/runs/${id}/replay`,
      { method: "POST", cache: "no-store", signal: AbortSignal.timeout(15000) },
    );
    if (!response.ok) throw new Error();
    const replay = researchRunSchema.parse(await response.json());
    redirect(`/research/${replay.id}`);
  } catch (error) {
    if (error && typeof error === "object" && "digest" in error) throw error;
    redirect(`/research/${id}?error=replay-failed`);
  }
}

async function updateOperations(path: string, method: "POST" | "PUT", body?: unknown) {
  const response = await fetch(`${researchBackendUrl()}${path}`, {
    method,
    headers: body === undefined ? undefined : { "content-type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
    signal: AbortSignal.timeout(15000),
  });
  if (!response.ok) throw new Error("operation failed");
  revalidatePath("/research");
}

export async function updateUniverse(formData: FormData): Promise<void> {
  const symbols = value(formData, "symbols").split(",").map((item) => item.trim()).filter(Boolean);
  await updateOperations("/api/operations/universe", "PUT", { symbols });
}

export async function updateSchedule(formData: FormData): Promise<void> {
  await updateOperations("/api/operations/schedule", "PUT", {
    enabled: formData.get("enabled") === "on",
    interval_hours: Number(value(formData, "interval_hours")),
    lookback_days: Number(value(formData, "lookback_days")),
  });
}

export async function runScheduledNow(): Promise<void> {
  await updateOperations("/api/operations/schedule/run", "POST");
}

export async function toggleStream(formData: FormData): Promise<void> {
  await updateOperations("/api/operations/stream", "PUT", {
    enabled: value(formData, "enabled") === "true",
  });
}

export async function activatePaperStrategy(formData: FormData): Promise<void> {
  await updateOperations("/api/operations/strategies/activate", "POST", {
    version: value(formData, "version"),
    mode: "paper",
  });
}

export async function decideProposal(formData: FormData): Promise<void> {
  const id = value(formData, "id");
  await updateOperations(`/api/operations/proposals/${id}/decision`, "POST", {
    action: value(formData, "action"),
    expected_version: value(formData, "version"),
    execution_mode: "paper",
  });
}
