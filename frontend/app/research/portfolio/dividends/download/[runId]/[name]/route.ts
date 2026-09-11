import { researchBackendUrl } from "@/lib/research";

const runIdPattern = /^[a-f0-9]{64}$/;
const allowed = new Set(["result.json", "report.md", "entitlements.csv", "ledger.csv", "equity.csv", "coverage.csv", "manifest.json"]);

export async function GET(
  _request: Request,
  context: { params: Promise<{ runId: string; name: string }> },
): Promise<Response> {
  const { runId, name } = await context.params;
  if (!runIdPattern.test(runId) || !allowed.has(name)) return new Response("Not found", { status: 404 });
  try {
    const response = await fetch(`${researchBackendUrl()}/api/research/portfolio/dividends/runs/${runId}/artifacts/${name}`, { cache: "no-store", signal: AbortSignal.timeout(15000) });
    if (!response.ok) return new Response("Not found", { status: 404 });
    return new Response(response.body, { headers: {
      "cache-control": "private, no-store",
      "content-disposition": response.headers.get("content-disposition") ?? `attachment; filename="${name}"`,
      "content-type": "application/octet-stream",
      "x-content-type-options": "nosniff",
    }});
  } catch {
    return new Response("Research backend unavailable", { status: 502 });
  }
}
