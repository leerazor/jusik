"use server";

import { redirect } from "next/navigation";
import { marketResearchRunSchema } from "@/lib/marketResearch";
import { researchBackendUrl } from "@/lib/research";

export async function createMarketResearchRun(formData: FormData): Promise<void> {
  const market = formData.get("market");
  const endDate = formData.get("end_date");
  const stage = formData.get("stage");
  const pilotRunId = formData.get("pilot_run_id");
  const researchGrade = formData.get("research_grade");
  let response: Response;
  try {
    response = await fetch(`${researchBackendUrl()}/api/research/market/runs`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        market,
        end_date: endDate,
        stage,
        pilot_run_id: pilotRunId || null,
        research_grade: researchGrade || "strict",
      }),
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
