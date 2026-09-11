import { researchBackendUrl } from "@/lib/research";

const runArtifacts = new Set([
  "result.json",
  "report.md",
  "validation.csv",
  "equity.csv",
  "trades.csv",
  "weekly-targets.csv",
  "policy-comparison.csv",
  "policy-monthly.csv",
  "policy-events.csv",
]);
const reports = new Set([
  "external-research.md",
  "external-comparison.md",
  "model-improvement.md",
  "portfolio-next-research.md",
]);

function backendPath(parts: string[]): string | null {
  if (
    parts.length === 2
    && /^[0-9a-f]{64}$/.test(parts[0])
    && runArtifacts.has(parts[1])
  ) {
    return `/api/research/portfolio/runs/${parts[0]}/artifacts/${parts[1]}`;
  }
  if (parts.length === 2 && parts[0] === "reports" && reports.has(parts[1])) {
    return `/api/research/reports/${parts[1]}`;
  }
  return null;
}

export async function GET(
  _request: Request,
  context: { params: Promise<{ path: string[] }> },
): Promise<Response> {
  const { path } = await context.params;
  const target = backendPath(path);
  if (!target) return new Response("Not found", { status: 404 });
  try {
    const response = await fetch(`${researchBackendUrl()}${target}`, {
      cache: "no-store",
      signal: AbortSignal.timeout(15000),
    });
    if (!response.ok) return new Response("Not found", { status: 404 });
    return new Response(response.body, {
      headers: {
        "cache-control": "no-store",
        "content-disposition": response.headers.get("content-disposition") ?? "attachment",
        "content-type": response.headers.get("content-type") ?? "application/octet-stream",
        "x-content-type-options": "nosniff",
      },
    });
  } catch {
    return new Response("Research backend unavailable", { status: 502 });
  }
}
