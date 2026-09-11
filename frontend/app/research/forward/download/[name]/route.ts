import { researchBackendUrl } from "@/lib/research";

const allowed = new Set(["observations.csv", "decisions.csv", "fills.csv", "events.csv", "equity.csv"]);

export async function GET(_request: Request, context: { params: Promise<{ name: string }> }): Promise<Response> {
  const { name } = await context.params;
  if (!allowed.has(name)) return new Response("Not found", { status: 404 });
  try {
    const response = await fetch(`${researchBackendUrl()}/api/research/forward/export/${name}`, { cache: "no-store", signal: AbortSignal.timeout(15000) });
    if (!response.ok) return new Response("Not found", { status: 404 });
    return new Response(response.body, { headers: { "cache-control": "no-store", "content-disposition": response.headers.get("content-disposition") ?? "attachment", "content-type": "text/csv; charset=utf-8", "x-content-type-options": "nosniff" } });
  } catch { return new Response("Research backend unavailable", { status: 502 }); }
}
