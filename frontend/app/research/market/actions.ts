"use server";

import { redirect } from "next/navigation";
import { marketResearchRunSchema } from "@/lib/marketResearch";
import { researchBackendUrl } from "@/lib/research";

export async function createMarketResearchRun(formData: FormData): Promise<void> {
  const market = formData.get("market");
  const startDate = formData.get("start_date");
  const endDate = formData.get("end_date");
  let response: Response;
  try {
    response = await fetch(`${researchBackendUrl()}/api/research/market/runs`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ market, start_date: startDate, end_date: endDate }),
    });
  } catch {
    redirect(`/research/market?error=backend-unavailable`);
  }
  if (!response.ok) redirect(`/research/market?error=create-failed`);
  try {
    const run = marketResearchRunSchema.parse(await response.json());
    redirect(`/research/market/${run.id}`);
  } catch (error) {
    if (error && typeof error === "object" && "digest" in error) throw error;
    redirect(`/research/market?error=create-failed`);
  }
}
